# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The QEMU backend adapter: everything that knows QEMU.

The backend interface in `backends.py` was designed by writing this
adapter first and generalizing from it, rather than the other way
around (F2). Binary discovery, image creation, configuration
rendering, launching an owned process, monitor sessions, identity
verification, input injection, and screen capture and readback all
live here. Nothing outside this file mentions QEMU, qcow2, QMP, or a
port number.

QMP (QEMU's management protocol) is a private implementation detail
of this adapter — it is never exposed as a control plane
(planning/design/guest-communication.md). The only way to reach it
from outside is the explicitly backend-specific escape hatch,
``QemuSession.native()``.

QEMU serves two display planes through one shared set of carrier
methods: the agentless-display plane reads characters by scraping VGA
text memory over QMP, and the VNC plane reads pixels from the RFB
framebuffer (:mod:`reliquary.rfb`) through the shared fixed-font
recognizer. Media changes go over QMP either way. The machine state's
resolved ``control-planes`` list decides which plane a session serves
— whichever plane is listed first is the one used.
"""

import asyncio
import contextlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import uuid

from PIL import Image
from qemu.qmp import ConnectError, ExecuteError, QMPClient

from . import backends
from . import rfb
from . import text_recognize
from .backends import Availability, BackendAdapter, Capabilities
from .errors import (InternalError, PreflightError, ReliquaryError,
                     RunFailure, StaticError)
from .home import effective_home


def _system_binary(arch):
    """QEMU's system binary for one CPU architecture, host-spelled."""
    return f"qemu-system-{arch}.exe" if os.name == "nt" else f"qemu-system-{arch}"


#: Which CPU architecture's QEMU system binary each guest platform
#: needs. QEMU's system binaries are not interchangeable, and using
#: the wrong one doesn't just run worse — a 64-bit kernel triple-
#: faults on the 32-bit binary and the machine loops through its
#: firmware forever, which looks like a guest that never boots rather
#: than a configuration mistake. DOS uses `i386`, the binary its
#: tested workflow runs on. None of this is detected by inspecting an
#: image or a screen — the platform used here is always the one the
#: blueprint declared (P10).
_PLATFORM_ARCH = {
    "dos": "i386",
    "win9x": "i386",
    "winnt": "x86_64",
    "openbsd": "x86_64",
}

#: The architecture used when no platform is given yet. A machine
#: that's mid-create has no resolved platform, and DOS is the
#: compatibility default (AGENTS.md, "Platform selection"), so this
#: is the binary this adapter has always launched in that case.
_DEFAULT_ARCH = "i386"

_QEMU_BIN = _system_binary(_DEFAULT_ARCH)
_QEMU_IMG_BIN = "qemu-img.exe" if os.name == "nt" else "qemu-img"


def _platform_binary(platform):
    """The QEMU system binary a guest platform needs.

    If the schema allows a platform that isn't in ``_PLATFORM_ARCH``
    yet, this raises an internal error naming the gap instead of
    guessing. Guessing is exactly what produces the reboot loop this
    table exists to prevent, and silently picking the wrong binary is
    exactly what P11 forbids.
    """
    if platform is None:
        return _system_binary(_DEFAULT_ARCH)
    try:
        return _system_binary(_PLATFORM_ARCH[platform])
    except KeyError:
        raise InternalError(
            f"no QEMU system binary is mapped for platform "
            f"{platform!r}; the qemu adapter cannot choose one, and "
            "guessing would boot the guest on the wrong emulator"
        ) from None


_BOOT_LETTER = {"floppy": "a", "hdd": "c", "cdrom": "d"}

#: The keys ``backend-settings.qemu`` may carry. ``machine`` names a
#: QEMU machine type; ``args`` is a list of arguments appended to the
#: launch command line as-is. This is the entire escape hatch on
#: purpose: adding a second way to say the same thing below would
#: create two sources of truth for one fact.
SETTINGS_KEYS = ("machine", "args")

#: QEMU arguments the ``args`` escape hatch may not carry, each mapped
#: to what already owns it. These fall into two groups: things a
#: blueprint already declares through its own fields, and things
#: reserved by VM identity tracking — the readable name, the
#: per-start token, and the QMP channel are how a session proves it's
#: talking to the right machine, so a caller can't override those.
#: Keys are compared case-sensitively, since ``-m`` (memory) and
#: ``-M`` (machine type) are different QEMU options. Deliberately
#: NOT reserved: ``-device`` — passing a backend-specific device is
#: exactly what this hatch is for (D93, P25) — and ``-cpu``, which
#: selects a CPU *model*, since ``cpus`` only controls the count.
RESERVED_ARGUMENTS = {
    "m": "the machine's `memory`",
    "smp": "the machine's `cpus`",
    "boot": "the machine's `boot` order",
    "drive": "the machine's `devices`",
    "hda": "the machine's `devices`",
    "hdb": "the machine's `devices`",
    "hdc": "the machine's `devices`",
    "hdd": "the machine's `devices`",
    "fda": "the machine's `devices`",
    "fdb": "the machine's `devices`",
    "cdrom": "the machine's `devices`",
    "machine": "this section's own `machine` key",
    "M": "this section's own `machine` key",
    "name": "the recorded VM identity",
    "uuid": "the recorded VM identity",
    "qmp": "reliquary's own control channel",
    "vnc": "the machine's `control-planes` policy",
    "display": "the display choice a start is given",
    "nographic": "the display choice a start is given",
    "netdev": "the machine's `devices`",
    "net": "the machine's `devices`",
}

#: The blueprint's NIC model names — the platform default
#: (`machines._PLATFORM_NIC`, D120) or an explicit `model` override
#: (D122) — mapped to the QEMU device model that renders them.
#: `ne2k` renders as the ISA-bus part (`ne2k_isa`), the historically
#: appropriate bus for a card real NE2000s shipped on — QEMU also has
#: a PCI variant (`ne2k_pci`), but nothing in the blueprint
#: vocabulary names it, and DOS-era platforms have no PCI bus to put
#: it on anyway. `virtio` renders as `virtio-net-pci`, QEMU's
#: paravirtualized NIC — real to the guest only in the sense that
#: `controller`'s own `virtio` value already is, and just as reliant
#: on the guest actually carrying a virtio driver.
_NIC_QEMU_MODELS = {"pcnet": "pcnet", "ne2k": "ne2k_isa",
                    "virtio": "virtio-net-pci"}

#: The `-drive` properties Reliquary already renders for every drive.
#: These are refused through ``-set drive.<slot>.<property>`` for the
#: same reason ``-drive`` itself is refused: it would be a second way
#: to set something already set, reached through QEMU's own per-drive
#: addressing (D118). Any other drive property — ``cache``, ``aio``,
#: ``discard``, ``serial``, and so on — belongs to the caller, and
#: QEMU validates its value the same way it validates the rest of the
#: escape hatch.
RESERVED_DRIVE_PROPERTIES = frozenset(
    {"file", "if", "index", "media", "id", "format", "bus", "unit"})


def _qemu_fallback_dirs():
    if os.name == "nt":
        pf = os.environ.get("ProgramFiles", r"C:\Program Files")
        pf86 = os.environ.get("ProgramFiles(x86)",
                              r"C:\Program Files (x86)")
        scoop = os.environ.get("SCOOP", os.path.expanduser(r"~\scoop"))
        choco = os.environ.get("ChocolateyInstall",
                               r"C:\ProgramData\chocolatey")
        return [
            os.path.join(pf, "qemu"),
            os.path.join(pf86, "qemu"),
            os.path.join(scoop, "apps", "qemu", "current"),
            os.path.join(choco, "bin"),
            r"C:\msys64\ucrt64\bin",
            r"C:\msys64\mingw64\bin",
        ]
    dirs = ["/usr/bin", "/usr/local/bin", "/opt/qemu/bin"]
    if sys.platform == "darwin":
        dirs += ["/opt/homebrew/bin", "/opt/local/bin"]
    return dirs


def _find_qemu_tool(binary):
    """Locate a QEMU tool from configuration and common paths."""
    for variable in ("RELIQUARY_QEMU_HOME", "QEMU_HOME"):
        qemu_home = os.environ.get(variable)
        if not qemu_home:
            continue
        for directory in (qemu_home, os.path.join(qemu_home, "bin")):
            candidate = os.path.join(directory, binary)
            if os.path.isfile(candidate):
                return candidate
        raise PreflightError(
            f"{binary} not found under {variable}={qemu_home}",
            rule_id="machine.backend-not-found")
    found = shutil.which(binary)
    if found:
        return found
    for directory in _qemu_fallback_dirs():
        candidate = os.path.join(directory, binary)
        if os.path.isfile(candidate):
            return candidate
    raise PreflightError(
        f"{binary} not found: install QEMU, add it to PATH, or set "
        "RELIQUARY_QEMU_HOME to its install directory",
        rule_id="machine.backend-not-found")


def find_qemu(platform=None):
    """Locate the QEMU system binary from configuration and common paths.

    ``platform`` is the guest platform the machine declared; it
    decides which system binary is needed (see
    :data:`_PLATFORM_ARCH`). Omit it to get the compatibility default,
    which is what a plain availability check wants.
    """
    return _find_qemu_tool(_platform_binary(platform))


#: Where QEMU keeps the VGA BIOS file that holds the font a guest
#: paints text with, relative to the directory holding the binary.
#: Some distributions put it under `share/qemu/` instead of `bin/`;
#: the Windows build keeps both together.
_VGABIOS_NAMES = ("vgabios-stdvga.bin", "vgabios.bin")


def guest_glyph_banks(cache=None):
    """Every VGA font this host's installed QEMU paints DOS text with.

    Read directly from the host's QEMU install, never shipped with
    Reliquary — the same reasoning as
    `backend_virtualbox.guest_glyph_banks`: these glyphs belong to the
    installed emulator, not to Reliquary
    (:func:`text_recognize.cached_banks`).

    QEMU's own agentless-display plane never needs this, since it
    reads characters the guest has already resolved out of VGA text
    memory. This exists for recognizing text in a QEMU *screenshot*
    instead, and to answer the font question the same way for both
    backends rather than only where it actually caused a problem.

    What this host's install actually has is the limit on what can be
    returned. QEMU ships its font bank with the BIOS's overrides
    already merged in, and carries no separate override table, so a
    stock install yields exactly one font — the one the BIOS itself
    draws with. The font a DOS guest loads afterward differs in 19
    glyphs and can't be recovered from these files, so a QEMU
    screenshot of guest-drawn text could still misread it. This
    returns every font the install actually has, which is the best
    available answer, not a complete one.
    """
    def extract():
        # Look up the QEMU path inside this function, so a cache hit
        # can answer without touching the install at all.
        home = os.path.dirname(find_qemu())
        roots = [home,
                 os.path.join(home, "share"),
                 os.path.join(home, "share", "qemu"),
                 os.path.join(os.path.dirname(home), "share", "qemu"),
                 "/usr/share/qemu", "/usr/share/seabios"]
        return text_recognize.banks_from_files(
            [os.path.join(root, name)
             for root in roots for name in _VGABIOS_NAMES],
            "QEMU")

    return text_recognize.cached_banks(cache, "qemu", extract)


def find_qemu_img():
    """Locate ``qemu-img`` from configuration and common paths."""
    return _find_qemu_tool(_QEMU_IMG_BIN)


def create_hdd_image(filename, capacity):
    """Create a sparse qcow2 v3 hard-disk image at ``filename``.

    ``capacity`` is a qemu-img size string such as ``"512M"`` or ``"2G"``,
    or a positive integer MiB value. The image uses ``compat=1.1``
    (qcow2 v3) with no preallocation. Existing files are not overwritten.
    Returns the absolute path of the created image.
    """
    if not isinstance(filename, str) or not filename.strip():
        raise StaticError("filename must be a non-empty path",
            rule_id="value.not-a-string")
    path = os.path.abspath(filename)
    if not path.lower().endswith(".qcow2"):
        raise StaticError(
            f"hdd image filename must end with .qcow2: {filename}",
            rule_id="image.wrong-extension")
    if isinstance(capacity, bool) or not isinstance(capacity, (int, str)):
        raise StaticError(
            "capacity must be a qemu-img size string or positive "
            "integer MiB value", rule_id="value.not-a-size")
    if isinstance(capacity, int):
        if capacity <= 0:
            raise StaticError(
                "capacity must be a positive integer MiB value",
                rule_id="value.not-a-size")
        size = f"{capacity}M"
    else:
        size = capacity.strip()
        if not size:
            raise StaticError("capacity must be a non-empty size",
                rule_id="value.not-a-size")
    if os.path.exists(path):
        raise PreflightError(f"image already exists: {path}",
            rule_id="image.already-exists")
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    qemu_img = find_qemu_img()
    command = [
        qemu_img, "create", "-f", "qcow2",
        "-o", "compat=1.1,preallocation=off",
        path, size,
    ]
    print(f"rlq: creating qcow2 image: {path} ({size})", file=sys.stderr)
    completed = subprocess.run(
        command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RunFailure(
            f"qemu-img failed creating {path}"
            + (f": {detail}" if detail else ""),
            rule_id="image.creation-failed")
    return path


def _run_qemu_img(args, action, target):
    completed = subprocess.run(
        [find_qemu_img(), *args], capture_output=True, text=True,
        check=False)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RunFailure(
            f"qemu-img failed {action} {target}"
            + (f": {detail}" if detail else ""),
            rule_id="image.operation-failed")
    return completed


def probe_image_format(path):
    """Return the qemu-detected format string of an existing image."""
    completed = _run_qemu_img(
        ["info", "--output=json", os.fspath(path)], "probing", path)
    return json.loads(completed.stdout)["format"]


def create_difference_image(filename, base):
    """Create a qcow2 differencing image backed by ``base``.

    Writes go to the difference image, so the base image stays
    unchanged — this is what a drive's ``materialize: difference``
    setting produces. The base's format is probed first so the
    backing reference is explicit. Existing files are not
    overwritten. Returns the created path.
    """
    path = os.path.abspath(os.fspath(filename))
    if not path.lower().endswith(".qcow2"):
        raise StaticError(
            f"difference image filename must end with .qcow2: {filename}",
            rule_id="image.wrong-extension")
    if os.path.exists(path):
        raise PreflightError(f"image already exists: {path}",
            rule_id="image.already-exists")
    base = os.path.abspath(os.fspath(base))
    base_format = probe_image_format(base)
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    print(f"rlq: creating qcow2 difference: {path} (backing {base})",
          file=sys.stderr)
    _run_qemu_img(
        ["create", "-f", "qcow2", "-o", "compat=1.1",
         "-b", base, "-F", base_format, path],
        "creating difference", path)
    return path


def create_duplicate_image(filename, base):
    """Create a standalone qcow2 copy of ``base``.

    This is what a drive's ``materialize: copy`` setting produces:
    the base is converted in full, leaving the new drive independent
    of any backing file. Existing files are not overwritten. Returns
    the created path.
    """
    path = os.path.abspath(os.fspath(filename))
    if not path.lower().endswith(".qcow2"):
        raise StaticError(
            f"duplicate image filename must end with .qcow2: {filename}",
            rule_id="image.wrong-extension")
    if os.path.exists(path):
        raise PreflightError(f"image already exists: {path}",
            rule_id="image.already-exists")
    base = os.path.abspath(os.fspath(base))
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    print(f"rlq: creating qcow2 duplicate: {path} (from {base})",
          file=sys.stderr)
    _run_qemu_img(
        ["convert", "-O", "qcow2", base, path],
        "duplicating", path)
    return path


class Qmp:
    """Synchronous facade over the official asyncio qemu.qmp library."""

    def __init__(self, port):
        self._loop = asyncio.new_event_loop()
        self._client = QMPClient("reliquary")
        try:
            self._loop.run_until_complete(
                self._client.connect(("127.0.0.1", port)))
        except BaseException:
            self._loop.close()
            raise

    def cmd(self, name, **arguments):
        return self._loop.run_until_complete(
            self._client.execute(name, arguments or None))

    def hmp(self, command_line):
        return self.cmd("human-monitor-command",
                        **{"command-line": command_line})

    def close(self):
        try:
            self._loop.run_until_complete(self._client.disconnect())
        except Exception:
            pass
        self._loop.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def verify_vm(qmp, port, expected_name, expected_token):
    """Raise an error unless the server is the exact VM instance recorded.

    The name alone can't identify a VM: two homes with the same
    machine number use the same readable name, so the per-start
    token (QEMU's ``-uuid``) also has to match before any command is
    allowed to target the server.
    """
    reply = qmp.cmd("query-name")
    actual_name = reply.get("name") if isinstance(reply, dict) else None
    if actual_name != expected_name:
        raise PreflightError(
            "QMP identity mismatch; the unrelated VM was not modified\n"
            f"  expected: {expected_name} on 127.0.0.1:{port}\n"
            f"  found:    {actual_name or '<unnamed QMP server>'}",
            rule_id="machine.identity-mismatch")
    reply = qmp.cmd("query-uuid")
    actual_uuid = reply.get("UUID") if isinstance(reply, dict) else None
    if (not isinstance(actual_uuid, str)
            or actual_uuid.casefold() != expected_token.casefold()):
        raise PreflightError(
            "QMP identity mismatch; the unrelated VM was not modified\n"
            f"  expected: {expected_name} ({expected_token}) "
            f"on 127.0.0.1:{port}\n"
            f"  found:    {actual_name} "
            f"({actual_uuid or '<no uuid>'})",
            rule_id="machine.identity-mismatch")


def available_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def port_in_use(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def _startup_error(proc, stderr_log, port, automatic, detail, args):
    try:
        with open(stderr_log, errors="replace") as stderr_file:
            stderr = stderr_file.read().strip()
    except OSError:
        stderr = ""
    selection = "automatic" if automatic else "explicit"
    message = (f"{detail}\n"
               f"  QMP port: 127.0.0.1:{port} ({selection})\n"
               f"  stderr log: {stderr_log}")
    if proc.returncode is not None:
        message += f"\n  QEMU exit status: {proc.returncode}"
    if stderr:
        message += f"\n  QEMU error: {stderr}"
    message += f"\n  command line: {subprocess.list2cmdline(args)}"
    return RunFailure(message, rule_id="machine.backend-failed-to-start")


def _terminate_started_process(proc):
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def _endpoint_port(vm):
    """The recorded QMP port of a QEMU VM record, or raise an error."""
    endpoint = (vm or {}).get("endpoint")
    port = endpoint.get("port") if isinstance(endpoint, dict) else None
    if (not isinstance(port, int) or isinstance(port, bool)
            or not 1 <= port <= 65535):
        raise PreflightError(
            f"the recorded QEMU endpoint is not a usable QMP port: "
            f"{endpoint!r}", rule_id="machine.endpoint-invalid")
    return port


def _allocate_vnc_port(host="127.0.0.1"):
    """A free loopback port for QEMU's VNC server, above port 5900.

    Allocated the same way as the QMP port — an ephemeral port handed
    out by the OS — with one extra requirement: QEMU takes a *display
    number* and serves it on port ``5900 + display``, so a port at or
    below 5900 would produce a negative display number and has to be
    retried. In practice the OS's ephemeral port range starts well
    above 5900 on every supported host, so this retry never actually
    triggers.
    """
    for _ in range(64):
        port = available_port()
        if port > 5900:
            return port
    raise InternalError(
        f"could not allocate a VNC port above 5900 on {host}")


def _check_vnc_endpoint(qmp, vnc_port):
    """Raise an error unless this QEMU serves VNC on the recorded port.

    Asked over a QMP session whose identity has already been
    verified: RFB itself carries no machine identity, so
    ``query-vnc`` is what ties the recorded VNC port to the VM the
    QMP identity check just confirmed.
    """
    reply = qmp.cmd("query-vnc")
    enabled = reply.get("enabled") if isinstance(reply, dict) else None
    service = reply.get("service") if isinstance(reply, dict) else None
    if enabled is not True or service != str(vnc_port):
        found = (f"port {service}" if enabled
                 else "no enabled VNC server")
        raise PreflightError(
            "QEMU's VNC endpoint does not match the recorded one\n"
            f"  expected: 127.0.0.1:{vnc_port}\n"
            f"  found:    {found}",
            rule_id="machine.vnc-endpoint-mismatch")


def launch_owned_qemu(args, *, vm_name, display=False, port=None,
                      vnc=False, current_vm=None, log_dir=None):
    """Launch an owned QEMU process and return its verified identity.

    ``args`` is the command line, including the QEMU binary and
    ``-name``, but not ``-qmp`` / ``-display`` / ``-uuid`` / ``-vnc``
    — those are added here. ``vnc`` requests a loopback VNC server on
    an allocated display: its port is added to the endpoint alongside
    the QMP port, ``query-vnc`` cross-checks it once identity is
    verified, and the readiness probe waits for it under the same
    startup deadline as everything else. ``current_vm`` is the
    machine's previously recorded VM identity, or ``None``. If it's
    still reachable, the launch is refused so a live VM is never
    orphaned; if it's stale, it's ignored and the caller overwrites
    the recorded identity. ``log_dir`` is where ``qemu-stderr.log``
    is written — the machine's backend subdirectory. Returns the
    generic identity record built by :func:`backends.identity`, whose
    endpoint is this QEMU's QMP port; the caller saves it together
    with the machine phase in one atomic write.
    """
    automatic_port = port is None
    port = available_port() if automatic_port else port
    if not 1 <= port <= 65535:
        raise StaticError(f"QMP port must be between 1 and 65535: {port}",
            rule_id="value.not-a-port")
    if port_in_use(port):
        selection = "automatically selected" if automatic_port else "explicit"
        raise PreflightError(
            f"QMP port 127.0.0.1:{port} is already in use "
            f"({selection}); choose another port or stop its owner",
            rule_id="machine.port-in-use")
    if current_vm:
        current_port = _endpoint_port(current_vm)
        try:
            with Qmp(current_port) as old_qmp:
                verify_vm(old_qmp, current_port,
                          current_vm["backend-id"], current_vm["token"])
        except (OSError, ConnectError):
            pass  # The recorded identity is stale; overwrite it below.
        else:
            raise PreflightError(
                "a reliquary VM is already active\n"
                f"  name: {current_vm['backend-id']}\n"
                f"  QMP port: 127.0.0.1:{current_port}\n"
                "stop it before starting another VM for this machine",
                rule_id="machine.vm-already-active")
    # The readable -name is not unique by itself: two homes can each
    # have a machine with the same number from the same blueprint. The
    # per-start uuid is what makes this exact QEMU instance
    # verifiable.
    token = str(uuid.uuid4())
    command = list(args)
    command += ["-uuid", token]
    command += ["-qmp", f"tcp:127.0.0.1:{port},server,nowait"]
    vnc_port = None
    if vnc:
        vnc_port = _allocate_vnc_port()
        command += ["-vnc", f"127.0.0.1:{vnc_port - 5900}"]
    if not display:
        command += ["-display", "none"]
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = (subprocess.DETACHED_PROCESS
                                   | subprocess.CREATE_NEW_PROCESS_GROUP)
    base = effective_home(log_dir)
    os.makedirs(base, exist_ok=True)
    stderr_log = os.path.join(base, "qemu-stderr.log")
    with open(stderr_log, "wb") as error_file:
        proc = subprocess.Popen(command, stderr=error_file, **kwargs)
    deadline = time.monotonic() + 15
    while True:
        if proc.poll() is not None:
            raise _startup_error(
                proc, stderr_log, port, automatic_port,
                "QEMU exited during startup", command)
        try:
            with Qmp(port) as qmp:
                verify_vm(qmp, port, vm_name, token)
                if vnc_port is not None:
                    _check_vnc_endpoint(qmp, vnc_port)
            if proc.poll() is not None:
                raise _startup_error(
                    proc, stderr_log, port, automatic_port,
                    "QEMU exited while establishing its QMP connection",
                    command)
            break
        except (OSError, ConnectError):
            if time.monotonic() > deadline:
                _terminate_started_process(proc)
                raise _startup_error(
                    proc, stderr_log, port, automatic_port,
                    "QEMU did not come up; QMP was unreachable after 15s",
                    command)
            time.sleep(0.5)
        except ReliquaryError:
            _terminate_started_process(proc)
            raise
    while vnc_port is not None:
        # Wait for the VNC endpoint to become reachable before
        # returning, using the same startup deadline as the rest of
        # the launch.
        try:
            rfb.probe("127.0.0.1", vnc_port)
            break
        except OSError:
            if time.monotonic() > deadline:
                _terminate_started_process(proc)
                raise _startup_error(
                    proc, stderr_log, port, automatic_port,
                    "QEMU did not serve its VNC endpoint "
                    f"127.0.0.1:{vnc_port} before the startup deadline",
                    command)
            time.sleep(0.5)
        except ReliquaryError:
            _terminate_started_process(proc)
            raise
    endpoint = {"port": port}
    if vnc_port is not None:
        endpoint["vnc-port"] = vnc_port
    print(f"rlq: QEMU started: {vm_name} (QMP on 127.0.0.1:{port})",
          file=sys.stderr)
    print(f"rlq: command line: {subprocess.list2cmdline(command)}",
          file=sys.stderr)
    return backends.identity(
        "qemu", vm_name, token, endpoint, pid=proc.pid)


def stop(vm):
    """Power off the identified owned VM. Does not save any state.

    ``vm`` is the recorded identity record. The QMP session's
    identity is verified before sending ``quit``, so an unrelated VM
    on the same port is never touched. Raises an error on an identity
    mismatch or an unreachable VM; the caller is responsible for
    updating the machine's ``phase`` and clearing the ``vm`` section.
    """
    if not vm:
        # No recorded VM identity: treat this the same as already
        # stopped, so the caller can move the machine to a resting
        # phase.
        raise PreflightError("no recorded reliquary VM to stop",
            rule_id="machine.no-active-vm")
    port = _endpoint_port(vm)
    expected_name = vm["backend-id"]
    expected_token = vm["token"]
    try:
        with Qmp(port) as qmp:
            verify_vm(qmp, port, expected_name, expected_token)
            try:
                qmp.cmd("quit")
            except Exception:
                pass
    except (OSError, ConnectError):
        raise PreflightError(
            "the recorded reliquary VM is no longer reachable\n"
            f"  expected: {expected_name} on 127.0.0.1:{port}",
            rule_id="machine.vm-unreachable")
    deadline = time.monotonic() + 15
    while True:
        try:
            Qmp(port).close()
        except (OSError, ConnectError):
            break
        if time.monotonic() > deadline:
            raise RunFailure(
                "QEMU is still holding the QMP port 15s after quit; "
                "a following start() on the same port would collide",
                rule_id="machine.port-not-released")
        time.sleep(0.5)
    print("rlq: VM stopped", file=sys.stderr)


# -- carriers -----------------------------------------------------

def format_options(image):
    """The QEMU ``format=`` option for an image, chosen by extension.

    ``.img`` and ``.iso`` files always get ``format=raw``, which
    avoids a warning QEMU prints when it has to probe the format
    itself. Any other extension is left for QEMU to identify on its
    own.
    """
    extension = os.path.splitext(image)[1].lower()
    return "format=raw," if extension in (".img", ".iso") else ""


def vga_screen(qmp):
    """Return the 80x25 VGA text screen as (text rows, attribute rows).

    Text rows are right-stripped strings; attribute rows keep the raw
    VGA attribute byte for all 80 cells in the row. Those attribute
    bytes are opaque tokens the caller can only compare for equality —
    the only promise made about them is that two equal tokens mean
    two identically rendered cells.
    """
    raw = qmp.hmp("xp /4000bx 0xb8000")
    data = []
    for line in raw.splitlines():
        if not re.match(r"^[0-9a-f]+:", line):
            continue
        data.extend(int(token, 16) for token in line.split()[1:])
    rows = []
    attributes = []
    for row in range(25):
        cells = data[row * 160:(row + 1) * 160]
        rows.append("".join(
            chr(byte) if 32 <= byte < 127 else " "
            for byte in cells[0::2]).rstrip())
        attributes.append(cells[1::2])
    return rows, attributes


class QemuSession:
    """The carriers a running QEMU offers, over one verified session.

    A control plane calls these methods; it never opens its own
    connection and never learns the port they use.
    """

    backend = "qemu"

    #: `text_screen` here reads characters the guest has already
    #: resolved out of VGA text memory — no image interpretation
    #: involved — so it's cheap enough that a caller can poll it
    #: fairly often (`screen_stability.TEXT_CADENCE_STEP`).
    recognizes_text = False

    def __init__(self, qmp):
        self._qmp = qmp

    def native(self):
        """The QEMU-specific escape hatch: this QEMU's QMP session.

        Always explicitly QEMU-specific, never made generic — a
        caller reaching for this has deliberately stepped outside the
        portable, backend-independent methods.
        """
        return self._qmp

    def send_keys(self, combos, delay=0.06):
        """Inject key combinations, each a list of key names.

        The key names used throughout Reliquary are QEMU's own
        "qcode" names (D103), so this mapping is the identity function
        — not a coincidence, but because this backend's names *are*
        the set everything else is built from. Naming the shared key
        vocabulary after QEMU, the reference backend, avoids inventing
        a third vocabulary that no backend actually speaks natively.

        A backend whose input API uses different key names does the
        translation in its own adapter, never in the control plane;
        VirtualBox's `scancodes_for` is that translation, and it's
        keyed by these same QEMU names rather than by its own.
        """
        for combo in combos:
            self._qmp.cmd(
                "send-key",
                keys=[{"type": "qcode", "data": key} for key in combo])
            time.sleep(delay)

    def text_screen(self, font_banks=()):
        """The native text readback: (character rows, attribute rows).

        ``font_banks`` (F61) is accepted but ignored here: reading
        native text memory involves no pixel recognition, so a
        script's `font` statement has nothing to change
        (`recognizes_text` below reports this to the caller).
        """
        return vga_screen(self._qmp)

    def framebuffer(self):
        """Refused: this plane reads text memory, not pixels.

        The landmark matcher compares the pixels a plane's screen
        carrier hands it, and this plane hands over characters the
        guest has already resolved — there's no framebuffer here to
        compare. `screendump` still captures a diagnostic image
        (see :meth:`screenshot` above, the `screenshot` verb, and the
        automatic failure capture), but that's a separate carrier on
        a separate schedule, not part of the sampling path.

        Not reachable in an ordinary run: `capture_format` already
        reports ``None`` for this plane, so preflight refuses a
        landmark condition before any guest input runs (F65). This
        method still raises the same error so a caller that somehow
        gets past that check sees a clear message instead of an
        ``AttributeError``.
        """
        raise PreflightError(
            "the agentless-display plane reads QEMU's VGA text memory "
            "and captures no framebuffer; a landmark condition needs a "
            "plane that does (control-planes: [\"vnc\"])",
            rule_id="machine.plane-no-framebuffer")

    def pointer_event(self, x, y, buttons):
        """Refused: aiming a pointer event needs a framebuffer to aim at.

        A `click` locates its target by matching a landmark, which
        this plane already refuses in :meth:`framebuffer`, so this
        method fails for the same reason. It's not reachable in an
        ordinary run, since the `framebuffer` refusal above already
        blocks it (F66).
        """
        raise PreflightError(
            "the agentless-display plane reads QEMU's VGA text memory "
            "and captures no framebuffer, so it has no pixel space a "
            "pointer event could aim at (control-planes: [\"vnc\"])",
            rule_id="machine.plane-no-pointer-input")

    def screenshot(self, path):
        """Capture the framebuffer to ``path`` as a PNG.

        QEMU writes PNG directly when its build supports it, and PPM
        otherwise; when it's PPM, this converts it to PNG, so the
        result is always a PNG either way.
        """
        png = os.fspath(path)
        try:
            self._qmp.cmd("screendump", filename=png.replace("\\", "/"),
                          format="png")
            return png
        except ExecuteError:
            pass
        ppm = os.path.splitext(png)[0] + ".ppm"
        self._qmp.cmd("screendump", filename=ppm.replace("\\", "/"))
        time.sleep(0.3)
        try:
            with Image.open(ppm) as image:
                image.save(png)
        except OSError as error:
            raise RunFailure(
                f"unexpected screendump format in {ppm}: {error}",
                rule_id="screen.screendump-unreadable") from error
        os.remove(ppm)
        return png

    def change_medium(self, drive_key, path=None):
        """Swap or eject a removable medium on the running machine.

        The drive is addressed by its launch id, which is the same
        key used for it in the state, so the change the guest sees
        and the change saved to the state stay in sync as one
        operation.
        """
        if path is None:
            self._qmp.hmp(f"eject {drive_key}")
            return
        target = os.fspath(path).replace("\\", "/")
        extension = os.path.splitext(target)[1].lower()
        fmt = " raw" if extension in (".img", ".iso") else ""
        self._qmp.hmp(f"change {drive_key} {target}{fmt}")


#: Maps Reliquary's shared key names (QEMU qcodes — see
#: ``control_display`` / ``script_runner``) to X11 keysyms, for RFB's
#: ``KeyEvent`` (D103). This is the VNC plane's own key-name mapping,
#: the same role VirtualBox's ``scancodes_for`` plays for that
#: backend: keyed by `ret`, `spc`, `pgup`, and `pgdn` — there's no
#: entry for `enter` or `space`. Letters and digits aren't listed
#: here because their keysym is just their character code, which
#: :func:`keysym_for` computes directly.
_KEYSYMS = {
    "esc": 0xff1b, "ret": 0xff0d, "tab": 0xff09, "backspace": 0xff08,
    "ctrl": 0xffe3, "shift": 0xffe1, "alt": 0xffe9,
    "spc": 0x0020, "minus": 0x002d, "equal": 0x003d,
    "bracket_left": 0x005b, "bracket_right": 0x005d,
    "semicolon": 0x003b, "apostrophe": 0x0027,
    "grave_accent": 0x0060, "backslash": 0x005c,
    "comma": 0x002c, "dot": 0x002e, "slash": 0x002f,
    "f1": 0xffbe, "f2": 0xffbf, "f3": 0xffc0, "f4": 0xffc1,
    "f5": 0xffc2, "f6": 0xffc3, "f7": 0xffc4, "f8": 0xffc5,
    "f9": 0xffc6, "f10": 0xffc7, "f11": 0xffc8, "f12": 0xffc9,
    "home": 0xff50, "up": 0xff52, "pgup": 0xff55,
    "left": 0xff51, "right": 0xff53,
    "end": 0xff57, "down": 0xff54, "pgdn": 0xff56,
    "insert": 0xff63, "delete": 0xffff,
}


def keysym_for(name):
    """The X11 keysym for one key name, or raise an error naming it."""
    keysym = _KEYSYMS.get(name)
    if keysym is not None:
        return keysym
    if len(name) == 1 and (name.islower() or name.isdigit()):
        # For Latin-1 characters, the keysym is just the character code.
        return ord(name)
    raise StaticError(f"no VNC keysym for key {name!r}",
                      rule_id="key.no-mapping")


def _endpoint_vnc_port(vm):
    """The recorded VNC port of a QEMU VM record, or raise an error."""
    endpoint = (vm or {}).get("endpoint") or {}
    port = endpoint.get("vnc-port")
    if (not isinstance(port, int) or isinstance(port, bool)
            or not 1 <= port <= 65535):
        raise PreflightError(
            "the recorded endpoint selects the VNC plane but carries "
            f"no usable VNC port: {endpoint!r}",
            rule_id="machine.endpoint-invalid")
    return port


class QemuVncSession(QemuSession):
    """The VNC plane's carriers: RFB screen and keys, QMP for the rest.

    Implements the same methods :class:`QemuSession` does, so any
    code written against that interface works unchanged here too. The
    screen carriers read the RFB framebuffer — `text_screen` runs it
    through the shared fixed-font recognizer, the same approach the
    VirtualBox display plane uses — and `send_keys` sends RFB
    ``KeyEvent`` messages. `change_medium` and the native escape hatch
    are inherited unchanged: changing media is a machine-level
    operation, not a display one, and it always goes over QMP no
    matter which plane is driving the screen.
    """

    #: Like the VirtualBox display plane, this `text_screen`
    #: interprets a captured framebuffer rather than reading resolved
    #: characters, which takes the better part of a second and limits
    #: how often a caller should poll it
    #: (`screen_stability.GUI_CADENCE_STEP`).
    recognizes_text = True

    def __init__(self, qmp, client, cache=None):
        super().__init__(qmp)
        self._rfb = client
        self._cache = cache

    def send_keys(self, combos, delay=0.06):
        """Inject key combinations as RFB key events.

        A combo's keys are pressed down in order and released in
        reverse order, the same sequence VirtualBox's scancode
        carrier uses.
        """
        for combo in combos:
            keysyms = [keysym_for(name) for name in combo]
            for keysym in keysyms:
                self._rfb.key_event(keysym, True)
            for keysym in reversed(keysyms):
                self._rfb.key_event(keysym, False)
            time.sleep(delay)

    def pointer_event(self, x, y, buttons):
        """Move/press/release as one RFB ``PointerEvent`` (F66).

        No coordinate translation needed: RFB's own coordinates are
        already framebuffer pixels, which is exactly what a caller
        composing a click already has from a landmark's position.
        """
        self._rfb.pointer_event(x, y, buttons)

    def text_screen(self, font_banks=()):
        """Framebuffer + shared fixed-font recognizer.

        Recognized using **this host's** QEMU font — the merged bank
        its BIOS draws with — which is also close enough to the
        classic font a DOS guest loads that it stays within the
        recognizer's match threshold. ``font_banks`` are the fonts a
        script's `font` statement named explicitly; they're tried
        *before* the host's own font, which is labelled ``"host"`` in
        the failure report's "fonts tried" list.
        """
        self._rfb.refresh()
        host_banks = tuple(
            text_recognize.Bank(one, source="host")
            for one in guest_glyph_banks(self._cache))
        return text_recognize.recognize(
            self._rfb.image(), bank=tuple(font_banks) + host_banks)

    def framebuffer(self):
        """The RFB framebuffer as a Pillow image (F65).

        This is the carrier the landmark matcher uses, and it's the
        same refresh-and-read that :meth:`text_screen` does, just
        without running the recognizer afterward. So a landmark-only
        sample costs one framebuffer read and no glyph matching at
        all — which is the point on a GUI screen, where there's no
        text to recognize anyway.

        RFB is configured to force 32-bit true-colour, so what comes
        back already matches this plane's stated ``rgb`` capture
        format (see :meth:`QemuAdapter.capture_format`).
        """
        self._rfb.refresh()
        return self._rfb.image()

    def screenshot(self, path):
        """Capture the framebuffer to ``path`` as a PNG."""
        png = os.path.abspath(os.fspath(path))
        parent = os.path.dirname(png)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._rfb.refresh()
        self._rfb.image().save(png)
        return png


class QemuAdapter(BackendAdapter):
    """QEMU: the fully built backend, and the one the interface was
    designed around."""

    name = "qemu"
    settings_keys = SETTINGS_KEYS

    # -- discovery and capability ---------------------------------

    def discover(self, platform=None):
        """Probe for the system binary this guest's architecture needs.

        This checks for the binary the *machine's* platform actually
        needs, rather than a fixed one, to keep preflight accurate:
        QEMU ships a separate system binary per architecture, so
        checking one binary and launching a different one could
        report a host as ready and then fail — or refuse a host that
        actually has the exact binary the machine needs.
        """
        try:
            executable = find_qemu(platform)
        except (PreflightError, InternalError) as missing:
            return Availability("qemu", False, detail=str(missing))
        return Availability("qemu", True, version=_qemu_version(executable),
                            executable=executable,
                            home=os.path.dirname(executable),
                            detail=f"found at {executable}")

    def capabilities(self):
        """What QEMU actually provides today, not what's merely planned.

        ``agentless-display`` and ``vnc`` are listed because both are
        implemented here. The blueprint vocabulary also names
        serial-console and guest-agent planes, but those aren't built
        yet, so they're left out — claiming them would promise
        something nothing can deliver (P11). The same reasoning
        applies to controllers: only ``ide`` is listed, since that's
        the only one the drive renderer supports.
        """
        return Capabilities(
            backend="qemu",
            control_planes=("agentless-display", "vnc"),
            media=("floppy", "hdd", "cdrom"),
            controllers=("ide",),
            materialize=("new", "difference", "copy", "use"),
            vvfat=True,
            pointing_devices=("tablet", "mouse"),
            network_models=("pcnet", "ne2k", "virtio"),
            network_attachments=("nat", "bridged"),
        )

    def capture_format(self, plane):
        """Only the VNC plane reads a framebuffer here (F65).

        The two planes differ in what their screen carrier actually
        reads: the agentless-display plane reads resolved characters
        out of VGA text memory over QMP, while the VNC plane reads
        the RFB framebuffer. A landmark condition, which compares
        pixels, works on the VNC plane and is refused by name on the
        agentless-display plane. RFB is forced to 32-bit true colour,
        which is ``rgb``, so the reference-image normalization ends
        up being a no-op.
        """
        return "rgb" if plane == "vnc" else None

    def pointer_capable(self, plane):
        """QMP delivers pointer events on either plane (F66).

        Unlike the framebuffer, this is a property of the management
        interface, not the screen carrier: ``input-send-event`` and
        RFB's ``PointerEvent`` both reach the same emulated tablet no
        matter which plane is driving the display. Whether a `click`
        can actually *aim* the pointer is a separate, plane-specific
        question that :meth:`capture_format` already answers — an
        agentless-display machine still refuses `click`, just because
        it has no framebuffer to aim at, not because the wire can't
        carry the event.
        """
        return plane in ("agentless-display", "vnc")

    def validate_settings(self, settings):
        """Check this machine's ``qemu`` section, without rendering anything.

        The function that renders the arguments, :func:`settings_args`,
        is also the validator — it's called here and the result
        discarded. So whatever a create accepts is exactly what a
        start later puts on the command line, unknown-key check
        included. This is why validation here doesn't call the shared
        base-class rule instead.
        """
        settings_args(settings)

    # -- materialize and dispose ----------------------------------

    def image_path(self, root, stem):
        """QEMU's native per-machine image: a qcow2 file named for its drive."""
        return os.path.join(root, f"{stem}.qcow2")

    def create_image(self, path, *, mode, size=None, base=None):
        if mode == "new":
            return create_hdd_image(path, size)
        if mode == "difference":
            return create_difference_image(path, base)
        if mode == "copy":
            return create_duplicate_image(path, base)
        raise StaticError(
            f"the qemu adapter cannot materialize an image for "
            f"mode {mode!r}", rule_id="image.mode-unsupported")

    # -- start, stop, liveness ------------------------------------

    def start(self, state, *, machine_dir, backend_dir, display=False,
              current=None):
        """Render the machine's state into a QEMU command line and launch.

        Turns Reliquary's own drive and network vocabulary into QEMU
        configuration: memory, drive arguments, NIC arguments, and the
        firmware boot order are all rendered here, so no caller ever
        has to build a backend argument by hand.

        This machine's own ``backend-settings.qemu`` section is
        rendered **last**, after everything Reliquary itself sets: the
        escape hatch only adds arguments on top of the rest of the
        configuration, so in the logged command line, the caller's own
        arguments always appear at the end. Sections for other
        backends are ignored and never read.
        """
        memory = state.get("memory") or 16
        vm_name = state.get("backend-id") or f"reliquary-{state['id']}"
        # The binary is chosen based on the guest's architecture,
        # rather than fixed, since that decides which system emulator
        # can run it at all (_PLATFORM_ARCH).
        args = [find_qemu(state.get("platform")), "-name", vm_name,
                "-m", str(memory)]
        devices = state.get("devices", {})
        drives = {key: entry for key, entry in devices.items()
                 if "medium" in entry}
        network = {key: entry for key, entry in devices.items()
                  if "attachment" in entry}
        args += drive_args(drives)
        args += network_args(network)
        boot = _boot_order(state.get("boot", []), drives)
        if boot is not None:
            args += ["-boot", f"order={boot}"]
        if state.get("pointing-device") == "tablet":
            # An absolute pointing device (F66): a PS/2 mouse reports
            # relative motion and its guest driver applies
            # acceleration the host can't observe, so `click` needs
            # the tablet rather than the default relative mouse (P10).
            args += ["-usb", "-device", "usb-tablet,id=pointer0"]
        args += settings_args(
            (state.get("backend-settings") or {}).get(self.name))
        planes = state.get("control-planes") or ["agentless-display"]
        identity = launch_owned_qemu(
            args, vm_name=vm_name, display=display, current_vm=current,
            log_dir=backend_dir, vnc="vnc" in planes)
        if planes[0] == "vnc":
            # The first plane listed in control-planes is the one a
            # session serves (blueprint-model.md); recording it here
            # alongside the ports lets the session use it without
            # re-reading the policy. The default plane needs no record.
            identity["endpoint"]["plane"] = "vnc"
        return identity

    def stop(self, vm):
        return stop(vm)

    @contextlib.contextmanager
    def session(self, vm, cache=None):
        """Yield an identity-verified session over the recorded VM.

        The endpoint's recorded ``plane`` decides which carriers are
        used: the VNC plane's when start recorded VNC as the driving
        plane, and the agentless-display plane's otherwise. Either
        way, QMP checks identity first — a VNC connection never
        authorizes a command on its own, and the RFB socket is only
        opened after the machine behind it is verified, with
        ``query-vnc`` cross-checking that the recorded endpoint is
        the one this QEMU actually serves.

        ``cache`` reaches the VNC plane's recognizer as the host-font
        cache. The agentless-display plane reads VGA text memory,
        where the guest has already resolved its characters, so it
        ignores ``cache``.
        """
        port = _endpoint_port(vm)
        name = vm["backend-id"]
        token = vm["token"]
        plane = (vm.get("endpoint") or {}).get("plane")
        if plane not in (None, "agentless-display", "vnc"):
            raise PreflightError(
                "the recorded endpoint names a control plane this "
                f"adapter does not serve: {plane!r}",
                rule_id="machine.endpoint-invalid")
        try:
            with Qmp(port) as qmp:
                verify_vm(qmp, port, name, token)
                if plane != "vnc":
                    yield QemuSession(qmp)
                else:
                    vnc_port = _endpoint_vnc_port(vm)
                    _check_vnc_endpoint(qmp, vnc_port)
                    try:
                        client = rfb.RfbClient("127.0.0.1", vnc_port)
                    except OSError as refused:
                        raise PreflightError(
                            "the recorded VNC endpoint is not "
                            "reachable\n"
                            f"  expected: 127.0.0.1:{vnc_port}",
                            rule_id="machine.vnc-unreachable"
                        ) from refused
                    try:
                        yield QemuVncSession(qmp, client, cache=cache)
                    finally:
                        client.close()
        except (OSError, ConnectError) as error:
            # The recorded VM is gone. This adapter doesn't own any
            # persisted state, so it doesn't clear anything here — the
            # caller (a lifecycle operation, or ``mark_stopped``)
            # updates the phase and the ``vm`` section on its next
            # operation.
            raise PreflightError(
                "the recorded reliquary VM is no longer reachable\n"
                f"  expected: {name} on 127.0.0.1:{port}",
                rule_id="machine.vm-unreachable") from error


def _qemu_version(executable):
    """The version string QEMU reports, or ``None`` if it won't say.

    Discovery never fails because of this: a binary that can't be run
    just means Reliquary doesn't know its version, not that the
    backend is unavailable — the launch itself will report what's
    actually wrong.
    """
    try:
        completed = subprocess.run(
            [executable, "--version"], capture_output=True, text=True,
            check=False, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    line = (completed.stdout or "").strip().splitlines()
    return line[0] if line else None


def _boot_order(boot_keys, drives):
    letters = []
    for key in boot_keys:
        drive = drives.get(key)
        if drive is None:
            continue
        letter = _BOOT_LETTER.get(drive["medium"])
        if letter is not None and letter not in letters:
            letters.append(letter)
    return "".join(letters) or None


def _option(item):
    """An argv element as ``(name, inline_value)``, or ``(None, None)``.

    Reads the option name the way QEMU would: strips leading dashes,
    and treats anything after a ``=`` or a space as the inline value.
    That means ``-m 64`` written as a single string is recognized as
    option ``-m``, instead of being handed to QEMU as one malformed
    argument it can't parse.
    """
    if not item.startswith("-"):
        return None, None
    parts = re.split(r"[=\s]", item.lstrip("-"), maxsplit=1)
    name = parts[0] or None
    inline = parts[1] if len(parts) > 1 and parts[1] else None
    return name, inline


def _reserved_argument(item):
    """What owns ``item``'s option, or ``None`` if it's the caller's."""
    name, _inline = _option(item)
    return RESERVED_ARGUMENTS.get(name) if name else None


def _reserved_set(value):
    """What owns a ``-set`` target, or ``None`` if it's the caller's.

    ``-set group.id.property=value`` is QEMU's own way to address a
    specific object's property, and for the ``drive`` group it can
    reach exactly what ``-drive`` sets — so any property Reliquary
    already renders is refused here the same way ``-drive`` itself is
    refused, naming ``devices`` as the owner (D118). Any value that
    isn't shaped like that is left for QEMU itself to reject.
    """
    if not isinstance(value, str):
        return None
    target = value.split("=", 1)[0]
    parts = target.split(".")
    if len(parts) != 3 or parts[0] != "drive":
        return None
    if parts[2] in RESERVED_DRIVE_PROPERTIES:
        return (f"the machine's `devices` (`{parts[2]}` of drive "
                f"{parts[1]!r} is what `devices` renders)")
    return None


def settings_args(settings):
    """Validate ``backend-settings.qemu`` and render it into arguments.

    This is the only path that does both, so a section that passes
    validation is a section that renders correctly:
    :meth:`QemuAdapter.validate_settings` calls this and discards the
    result, while the launch calls it to get the actual arguments. A
    separate validator function could drift out of sync with the
    renderer, which would show up as configuration accepted at create
    time and then silently missing at start.

    The section is the escape hatch, so its *values* belong to the
    caller — if QEMU refuses a machine type it doesn't have, that's
    the caller's error to read. What this function checks is the set
    of allowed keys, each key's shape, and overlap: an argument that
    Reliquary already owns through a first-class field or through VM
    identity is refused, naming the owner, because letting the hatch
    set the same thing two different ways is exactly what it must not
    become.
    """
    settings = settings or {}
    unknown = sorted(key for key in settings if key not in SETTINGS_KEYS)
    if unknown:
        raise StaticError(
            f"backend-settings.qemu does not define {unknown[0]!r}; the "
            f"qemu keys are {', '.join(SETTINGS_KEYS)}",
            rule_id="machine.settings-unknown-key")
    args = []
    machine = settings.get("machine")
    if machine is not None:
        if not isinstance(machine, str) or not machine.strip():
            raise StaticError(
                "backend-settings.qemu.machine must be a non-empty "
                f"string naming a QEMU machine type, got: {machine!r}",
                rule_id="value.not-a-string")
        args += ["-machine", machine]
    extra = settings.get("args")
    if extra is not None:
        if not isinstance(extra, list):
            raise StaticError(
                "backend-settings.qemu.args must be an array of "
                f"arguments, got: {extra!r}", rule_id="value.not-an-array")
        for index, item in enumerate(extra):
            if not isinstance(item, str) or not item:
                raise StaticError(
                    f"backend-settings.qemu.args[{index}] must be a "
                    f"non-empty string, got: {item!r}",
                    rule_id="value.not-a-string")
            owner = _reserved_argument(item)
            if owner is None:
                name, inline = _option(item)
                if name == "set":
                    # The target can be inline (`-set drive.x.cache=none`
                    # as one element) or given as the next element.
                    following = extra[index + 1] if index + 1 < len(
                        extra) else None
                    owner = _reserved_set(inline or following)
            if owner is not None:
                raise StaticError(
                    f"backend-settings.qemu.args[{index}] is {item!r}, "
                    f"which reliquary owns through {owner} — settings may "
                    "not restate what the blueprint already says",
                    rule_id="machine.settings-reserved-argument")
            args.append(item)
    return args


def drive_args(drives):
    """Build QEMU ``-drive`` arguments from a machine's resolved drives.

    Returns a list of tokens for a QEMU command line (``-drive``
    alternating with its value), with floppies first, hard disks
    next, and cdroms placed on the IDE bus after the last hard disk.
    A drive whose resolved path is a host directory is rendered as
    vvfat — this can only be known once resolution has already run,
    which is why it's checked here rather than at assignment time.
    """
    args = []

    floppies = [(k, v) for k, v in drives.items()
                if v["medium"] == "floppy"]
    for key, drive in sorted(floppies, key=lambda kv: kv[1]["slot"]):
        path = drive["path"]
        # id=<key> names the drive so a running insert/eject can
        # target it over QMP later (the drive's key is its launch id).
        if path is None:
            args += ["-drive",
                     f"if=floppy,index={drive['slot']},id={key}"]
            continue
        is_dir = os.path.isdir(path)
        source = (f"fat:floppy:rw:{path},format=raw,"
                  if is_dir else path + ",")
        args += ["-drive",
                 f"file={source}if=floppy,index={drive['slot']},id={key}"]

    hdds = [(k, v) for k, v in drives.items()
            if v["medium"] == "hdd"]
    for key, drive in sorted(hdds, key=lambda kv: kv[1]["slot"]):
        path = drive["path"]
        is_dir = os.path.isdir(path)
        source = (f"fat:rw:{path},format=raw,"
                  if is_dir else path + ",")
        inferred = "" if is_dir else format_options(path)
        # id=<key>, same as every other drive: a hard disk is never
        # swapped live, but its key is still how the settings hatch
        # addresses that drive's options — `-set drive.hdd0.cache=…`
        # (D118) — so every drive is addressable the same way.
        args += ["-drive",
                 f"file={source}{inferred}if=ide,index={drive['slot']},"
                 f"id={key}"]

    cdroms = [(k, v) for k, v in drives.items()
              if v["medium"] == "cdrom"]
    if cdroms:
        next_ide = max(
            (d["slot"] for k, d in drives.items() if d["medium"] == "hdd"),
            default=-1,
        ) + 1
        for ordinal, (key, drive) in enumerate(
                sorted(cdroms, key=lambda kv: kv[1]["slot"])):
            path = drive["path"]
            index = next_ide + ordinal
            if path is None:
                args += ["-drive",
                         f"media=cdrom,if=ide,index={index},id={key}"]
                continue
            inferred = format_options(path)
            args += ["-drive",
                     f"file={path},{inferred}media=cdrom,if=ide,"
                     f"index={index},id={key}"]

    return args


def network_args(network):
    """Build QEMU ``-netdev``/``-device`` arguments from a machine's NICs.

    Each slot gets a netdev matching its declared attachment and a
    device of the platform-resolved model (D120), both addressed by
    the slot's own key — ``id=net0`` — the same addressing convention
    every drive already uses. A ``bridged`` slot with no ``interface``
    omits ``br=`` entirely, which is QEMU's own default (the
    conventional bridge name ``br0``) — Reliquary does not probe the
    host for one (T32 tracks adding that detection later).
    """
    args = []
    for key, entry in sorted(network.items()):
        if entry["attachment"] == "bridged":
            interface = entry.get("interface")
            netdev = f"bridge,id={key}"
            if interface:
                netdev += f",br={interface}"
        else:
            netdev = f"user,id={key}"
        model = _NIC_QEMU_MODELS[entry["model"]]
        args += ["-netdev", netdev,
                 "-device", f"{model},netdev={key},id={key}"]
    return args
