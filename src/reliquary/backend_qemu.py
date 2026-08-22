# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The QEMU backend adapter: everything that knows QEMU.

The seam was read off this implementation rather than designed ahead
of one (F2): binary discovery, image creation, configuration
rendering, owned process launch, monitor sessions, identity
verification, input injection, screen capture and readback all live
here, and nothing above the seam names QEMU, qcow2, QMP or a port.

The management interface is QMP — a private tool of this adapter, and
never a control plane (planning/design/guest-communication.md). It
reaches the world only through the named native escape hatch,
``QemuSession.native()``, which is explicitly backend-scoped.

Two display planes are served over one carrier seam: the agentless
display's carriers scrape VGA text memory over QMP, and the VNC
plane's read the RFB framebuffer (:mod:`reliquary.rfb`) through the
shared fixed-font recognizer, with media movement riding QMP either
way. The machine state's resolved ``control-planes`` policy decides
which set a session serves — the first declared plane drives.
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


_QEMU_BIN = "qemu-system-i386.exe" if os.name == "nt" else "qemu-system-i386"
_QEMU_IMG_BIN = "qemu-img.exe" if os.name == "nt" else "qemu-img"

_BOOT_LETTER = {"floppy": "a", "hdd": "c", "cdrom": "d"}

#: The keys ``backend-settings.qemu`` may carry. ``machine`` is a QEMU
#: machine type, ``args`` a list of arguments appended to the launch
#: verbatim — the documented escape hatch, and deliberately the whole
#: of it: a second spelling for anything below would be a second
#: source for one fact.
SETTINGS_KEYS = ("machine", "args")

#: QEMU arguments the escape hatch may not carry, each naming what
#: owns it. Two populations, and the second is not a first-class field:
#: what a blueprint declares through its own vocabulary, and what the
#: **VM ownership doctrine** owns — the readable name, the per-start
#: token and the QMP channel are how a session verifies it is talking
#: to this machine, so a caller-supplied one is refused rather than
#: silently overridden. Keys are compared **case-sensitively**, since
#: ``-m`` (memory) and ``-M`` (machine type) are different options.
#: NOT here, deliberately: ``-device`` — a backend-specific device is
#: exactly what this hatch exists to carry (D93, P25) — and ``-cpu``,
#: which selects a CPU *model* where ``cpus`` owns the count alone.
RESERVED_ARGUMENTS = {
    "m": "the machine's `memory`",
    "smp": "the machine's `cpus`",
    "boot": "the machine's `boot` order",
    "drive": "the machine's `drives`",
    "hda": "the machine's `drives`",
    "hdb": "the machine's `drives`",
    "hdc": "the machine's `drives`",
    "hdd": "the machine's `drives`",
    "fda": "the machine's `drives`",
    "fdb": "the machine's `drives`",
    "cdrom": "the machine's `drives`",
    "machine": "this section's own `machine` key",
    "M": "this section's own `machine` key",
    "name": "the recorded VM identity",
    "uuid": "the recorded VM identity",
    "qmp": "reliquary's own control channel",
    "vnc": "the machine's `control-planes` policy",
    "display": "the display choice a start is given",
    "nographic": "the display choice a start is given",
}

#: The `-drive` properties Reliquary renders for every drive, and so
#: refuses through ``-set drive.<slot>.<property>`` as it refuses
#: ``-drive`` itself: the same second source for one fact, reached
#: by QEMU's own per-drive addressing (D118). Every other drive
#: property — ``cache``, ``aio``, ``discard``, ``serial``, … — is
#: the caller's, and QEMU judges its value as it judges the rest of
#: the hatch.
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


def find_qemu():
    """Locate the QEMU system binary from configuration and common paths."""
    return _find_qemu_tool(_QEMU_BIN)


#: Where QEMU keeps the VGA BIOS whose font a guest paints with,
#: relative to the directory holding the binary. Distributions split
#: `bin/` from `share/qemu/`; the Windows build keeps both together.
_VGABIOS_NAMES = ("vgabios-stdvga.bin", "vgabios.bin")


def guest_glyph_banks(cache=None):
    """Every VGA font this host's QEMU paints DOS text with.

    **Read off the host, never shipped** — the counterpart of
    `backend_virtualbox.guest_glyph_banks`, and the same reasoning:
    the glyphs belong to the installed emulator, not to Reliquary
    (:func:`text_recognize.cached_banks`).

    QEMU's own control plane never needs this — it scrapes VGA text
    memory, where the guest has already resolved its characters — so
    this exists for a caller recognizing a QEMU *screenshot*, and to
    keep the font question answered the same way for both backends
    rather than only where it happened to bite.

    **What this host can offer is the limit.** QEMU ships its bank
    with the BIOS's overrides already merged in and carries no
    override table, so a stock install yields exactly one font — the
    one the BIOS draws with. The font a DOS guest loads afterwards
    differs in 19 glyphs and is not recoverable from these binaries,
    so a QEMU screenshot of a guest-drawn screen would misread them.
    Every font the installation actually holds is returned, which is
    the best available answer rather than a complete one.
    """
    def extract():
        # Resolved inside the extractor, so a cache hit answers
        # without going near the installation at all.
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

    Writes land in the difference; the base image stays pristine
    (the drive ``base`` triad's default ``difference`` type). The
    base's format is probed so the backing reference is explicit.
    Existing files are not overwritten. Returns the created path.
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
    """Materialize a standalone qcow2 copy of ``base``.

    The base is converted in full (``duplicate`` base type), leaving
    the drive independent of any backing file. Existing files are not
    overwritten. Returns the created path.
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
    """Fail closed unless the server is the exact VM instance recorded.

    The name alone cannot identify a VM: same-numbered machines of
    two homes share their readable name, so the per-start token (the
    QEMU ``-uuid``) must match as well before any command may target
    the server.
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
    """The recorded QMP port of a QEMU VM record, or fail closed."""
    endpoint = (vm or {}).get("endpoint")
    port = endpoint.get("port") if isinstance(endpoint, dict) else None
    if (not isinstance(port, int) or isinstance(port, bool)
            or not 1 <= port <= 65535):
        raise PreflightError(
            f"the recorded QEMU endpoint is not a usable QMP port: "
            f"{endpoint!r}", rule_id="machine.endpoint-invalid")
    return port


def _allocate_vnc_port(host="127.0.0.1"):
    """A free loopback port for QEMU's VNC server, above the VNC base.

    Allocated the way the QMP port is — an ephemeral port the OS
    hands out — with one extra demand: QEMU takes a *display number*
    and serves port ``5900 + display``, so a port at or below 5900
    would render as a negative display and is re-drawn. Ephemeral
    ranges start far above 5900 on every supported host, so the
    retry never triggers in practice.
    """
    for _ in range(64):
        port = available_port()
        if port > 5900:
            return port
    raise InternalError(
        f"could not allocate a VNC port above 5900 on {host}")


def _check_vnc_endpoint(qmp, vnc_port):
    """Fail closed unless this QEMU serves VNC where it was recorded.

    Asked over the already identity-verified QMP session: RFB carries
    no machine identity, so ``query-vnc`` is what ties the recorded
    VNC endpoint to the VM the QMP identity check just proved.
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

    ``args`` is the command line including the QEMU binary and
    ``-name``, but excluding ``-qmp`` / ``-display`` / ``-uuid`` /
    ``-vnc`` (added here). ``vnc`` asks for a loopback VNC server on
    an allocated display: its port lands in the endpoint beside the
    QMP port, ``query-vnc`` cross-checks it once the identity is
    verified, and the readiness probe waits it out under the same
    startup deadline. ``current_vm`` is the machine's previously
    recorded VM identity (or ``None``): a still-reachable one refuses
    the launch so a live VM is never orphaned; a stale one is ignored
    (the caller overwrites the recorded identity). ``log_dir``
    receives ``qemu-stderr.log`` — the machine's backend
    subdirectory. Returns the generic identity record
    (:func:`backends.identity`) whose endpoint is this QEMU's QMP
    port; the caller persists it, atomically with the machine phase.
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
            pass  # stale identity; the caller overwrites it
        else:
            raise PreflightError(
                "a reliquary VM is already active\n"
                f"  name: {current_vm['backend-id']}\n"
                f"  QMP port: 127.0.0.1:{current_port}\n"
                "stop it before starting another VM for this machine",
                rule_id="machine.vm-already-active")
    # The readable -name repeats across homes (same-numbered machines
    # of one blueprint); the per-start uuid is the token that makes
    # this exact QEMU instance verifiable.
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
        # The readiness probe the VNC endpoint owes before the launch
        # is called up, bounded by the same startup deadline.
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
    """Power off the identified owned VM (no persistence).

    ``vm`` is the recorded identity record. The QMP session is
    identity-verified before ``quit``, so an unrelated VM on the same
    port is never touched. Fails closed on an identity mismatch or an
    unreachable VM; the caller reconciles the machine ``phase`` and
    clears the ``vm`` section.
    """
    if not vm:
        # A machine caught with no recorded VM identity — treat as
        # already gone so the caller reconciles it to a resting phase.
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
    """The QEMU ``format=`` option for an image, by extension.

    ``.img`` / ``.iso`` are pinned to ``format=raw`` (avoiding QEMU's
    format-probing warning); any other extension is left for QEMU to
    identify.
    """
    extension = os.path.splitext(image)[1].lower()
    return "format=raw," if extension in (".img", ".iso") else ""


def vga_screen(qmp):
    """Return the 80x25 VGA text screen as (text rows, attribute rows).

    Text rows are right-stripped strings; attribute rows keep the raw
    VGA attribute byte of all 80 cells. Those bytes are the adapter's
    contribution to the seam's text-screen contract: opaque,
    equality-comparable per-cell tokens, promising nothing except
    that equal tokens mean identically rendered cells.
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

    A control plane composes these; it never opens a connection of its
    own and never learns the port behind them.
    """

    backend = "qemu"

    #: `text_screen` here reads characters the guest already resolved
    #: out of VGA text memory — no interpretation, and cheap enough
    #: that a caller may quantize its cadence finely
    #: (`screen_stability.TEXT_CADENCE_STEP`).
    recognizes_text = False

    def __init__(self, qmp):
        self._qmp = qmp

    def native(self):
        """The named native escape hatch: this QEMU's QMP session.

        Always explicitly backend-scoped, never generalized — a
        caller reaching for it has left the portable surface
        deliberately.
        """
        return self._qmp

    def send_keys(self, combos, delay=0.06):
        """Inject key combinations, each a list of seam key names.

        **The seam's key vocabulary is QEMU's qcode set** (D103), so
        the mapping here is the identity — not by coincidence but
        because this backend's names *are* the set. Naming the seam
        after the reference backend is the cost of not inventing a
        third vocabulary that no backend speaks natively.

        A backend whose input API names keys differently translates in
        its own adapter, never in the control plane; VirtualBox's
        `scancodes_for` is that translation, and it is keyed by these
        names rather than by the language's.
        """
        for combo in combos:
            self._qmp.cmd(
                "send-key",
                keys=[{"type": "qcode", "data": key} for key in combo])
            time.sleep(delay)

    def text_screen(self, font_banks=()):
        """The native text readback: (character rows, attribute rows).

        ``font_banks`` (F61) is accepted and ignored: a native
        text-memory read recognizes no pixels, so a script's `font`
        statement has nothing to change here (`recognizes_text` below
        is what tells a caller so).
        """
        return vga_screen(self._qmp)

    def screenshot(self, path):
        """Capture the framebuffer to ``path`` as a PNG.

        QEMU writes PNG directly where its build supports it, and PPM
        otherwise — converted here, so the carrier's product is a PNG
        either way.
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

        The drive is addressed by its launch id, which is the state's
        drive key, so the change the guest sees and the change
        persisted to the state stay one operation.
        """
        if path is None:
            self._qmp.hmp(f"eject {drive_key}")
            return
        target = os.fspath(path).replace("\\", "/")
        extension = os.path.splitext(target)[1].lower()
        fmt = " raw" if extension in (".img", ".iso") else ""
        self._qmp.hmp(f"change {drive_key} {target}{fmt}")


#: Seam key names (QEMU qcodes — see ``control_display`` /
#: ``script_runner``) → X11 keysyms for RFB ``KeyEvent``. The VNC
#: plane's own third layer of key mapping (D103), exactly as
#: VirtualBox owns ``scancodes_for``: keyed by `ret`, `spc`, `pgup`
#: and `pgdn`, with no entry for `enter` or `space`. Letters and
#: digits are not listed — their keysym is their character code,
#: which :func:`keysym_for` computes.
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
    """The X11 keysym for one seam key name, or fail closed naming it."""
    keysym = _KEYSYMS.get(name)
    if keysym is not None:
        return keysym
    if len(name) == 1 and (name.islower() or name.isdigit()):
        # Latin-1 keysyms are the character codes themselves.
        return ord(name)
    raise StaticError(f"no VNC keysym for key {name!r}",
                      rule_id="key.no-mapping")


def _endpoint_vnc_port(vm):
    """The recorded VNC port of a QEMU VM record, or fail closed."""
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

    Behind the same seam :class:`QemuSession` serves, so everything
    above it is untouched by construction. The screen carriers read
    the RFB framebuffer — `text_screen` through the shared fixed-font
    recognizer, the composition the VirtualBox display plane built —
    and `send_keys` speaks RFB ``KeyEvent``. `change_medium` and the
    native escape hatch stay inherited: media movement is a machine
    operation, not a display one, and it rides the management
    interface whatever plane drives the screen.
    """

    #: Like the VirtualBox display plane, this `text_screen`
    #: interprets a framebuffer rather than reading resolved
    #: characters, which costs the better part of a second and sets
    #: how coarsely a caller may quantize its cadence
    #: (`screen_stability.GUI_CADENCE_STEP`).
    recognizes_text = True

    def __init__(self, qmp, client, cache=None):
        super().__init__(qmp)
        self._rfb = client
        self._cache = cache

    def send_keys(self, combos, delay=0.06):
        """Inject key combinations as RFB key events.

        A combo's keys go down in order and up in reverse, the same
        expansion VirtualBox's scancode carrier performs.
        """
        for combo in combos:
            keysyms = [keysym_for(name) for name in combo]
            for keysym in keysyms:
                self._rfb.key_event(keysym, True)
            for keysym in reversed(keysyms):
                self._rfb.key_event(keysym, False)
            time.sleep(delay)

    def text_screen(self, font_banks=()):
        """Framebuffer + shared fixed-font recognizer.

        Read through **this host's** QEMU font — the merged bank its
        BIOS draws with, which is also near enough to the classic
        design a DOS guest loads to stay inside the recognizer's
        match threshold. ``font_banks`` are the authored fonts a
        script's `font` statement named, tried **before** the host's
        own, labelled ``"host"`` in the failure report's "fonts
        tried".
        """
        self._rfb.refresh()
        host_banks = tuple(
            text_recognize.Bank(one, source="host")
            for one in guest_glyph_banks(self._cache))
        return text_recognize.recognize(
            self._rfb.image(), bank=tuple(font_banks) + host_banks)

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
    """QEMU: the delivered backend, and the seam's source."""

    name = "qemu"
    settings_keys = SETTINGS_KEYS

    # -- discovery and capability ---------------------------------

    def discover(self):
        try:
            executable = find_qemu()
        except PreflightError as missing:
            return Availability("qemu", False, detail=str(missing))
        return Availability("qemu", True, version=_qemu_version(executable),
                            executable=executable,
                            home=os.path.dirname(executable),
                            detail=f"found at {executable}")

    def capabilities(self):
        """What QEMU provides today — built, not merely intended.

        ``agentless-display`` and ``vnc`` are listed because both are
        built here; the serial-console and guest-agent planes are
        named in the blueprint vocabulary and unbuilt, so claiming
        them would promise what nothing can honor (P11). The same
        reading governs controllers: the drive renderer wires ``ide``
        alone.
        """
        return Capabilities(
            backend="qemu",
            control_planes=("agentless-display", "vnc"),
            media=("floppy", "hdd", "cdrom"),
            controllers=("ide",),
            materialize=("new", "difference", "copy", "use"),
            vvfat=True,
        )

    def validate_settings(self, settings):
        """Judge this machine's ``qemu`` section, rendering nothing.

        The renderer *is* the validator (:func:`settings_args`), so
        what a create accepts is exactly what a start puts on the
        command line — including the unknown-key rule, which is why
        this does not defer to the seam's shared one.
        """
        settings_args(settings)

    # -- materialize and dispose ----------------------------------

    def image_path(self, root, stem):
        """QEMU's native per-machine image: qcow2, named for its media."""
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

        Reliquary drive vocabulary in, QEMU configuration out: memory,
        the drive arguments, and the firmware boot order are all
        rendered here, so no caller ever composes a backend argument.

        **This machine's own ``backend-settings.qemu`` section renders
        last**, after everything Reliquary owns: the hatch adds to the
        configuration rather than sitting inside it, and reading the
        logged command line, a caller's own arguments are the tail.
        Sections for other backends are inert and never read.
        """
        memory = state.get("memory") or 16
        vm_name = state.get("backend-id") or f"reliquary-{state['id']}"
        args = [find_qemu(), "-name", vm_name, "-m", str(memory)]
        args += drive_args(state.get("drives", {}))
        boot = _boot_order(state.get("boot", []), state.get("drives", {}))
        if boot is not None:
            args += ["-boot", f"order={boot}"]
        args += settings_args(
            (state.get("backend-settings") or {}).get(self.name))
        planes = state.get("control-planes") or ["agentless-display"]
        identity = launch_owned_qemu(
            args, vm_name=vm_name, display=display, current_vm=current,
            log_dir=backend_dir, vnc="vnc" in planes)
        if planes[0] == "vnc":
            # The first declared plane drives the session's carriers
            # (blueprint-model.md); recording it beside the ports is
            # what lets a session serve it without re-reading the
            # policy. The default plane needs no record.
            identity["endpoint"]["plane"] = "vnc"
        return identity

    def stop(self, vm):
        return stop(vm)

    @contextlib.contextmanager
    def session(self, vm, cache=None):
        """Yield an identity-verified session over the recorded VM.

        The endpoint's recorded ``plane`` picks the carriers: the VNC
        plane's where the start recorded it as the driving plane, and
        the agentless display's otherwise. Either way identity is
        QMP's job and comes first — a VNC connection never authorizes
        a command, and the RFB socket is opened only after the
        machine behind it is verified, with ``query-vnc``
        cross-checking that the recorded endpoint is the one this
        QEMU serves.

        ``cache`` reaches the VNC plane's recognizer as the host-font
        cache; the agentless plane reads VGA text memory, where the
        guest has already resolved its characters, and ignores it.
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
            # The recorded VM is gone. The adapter owns no state, so
            # it does not clear it here — the caller (a lifecycle
            # operation, or ``mark_stopped``) reconciles the phase and
            # the ``vm`` section on the next operation.
            raise PreflightError(
                "the recorded reliquary VM is no longer reachable\n"
                f"  expected: {name} on 127.0.0.1:{port}",
                rule_id="machine.vm-unreachable") from error


def _qemu_version(executable):
    """The version string QEMU reports, or ``None`` if it will not say.

    Discovery never fails on this: a binary that cannot be run is a
    version Reliquary does not know, not an unavailable backend — the
    launch itself will report what is actually wrong.
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

    Reads the option name the way QEMU would: leading dashes
    stripped, and anything past a ``=`` or a space the inline value —
    so ``-m 64`` written as a single element is caught as ``-m``
    rather than handed to QEMU as an argument it cannot parse.
    """
    if not item.startswith("-"):
        return None, None
    parts = re.split(r"[=\s]", item.lstrip("-"), maxsplit=1)
    name = parts[0] or None
    inline = parts[1] if len(parts) > 1 and parts[1] else None
    return name, inline


def _reserved_argument(item):
    """What owns ``item``'s option, or ``None`` if the caller does."""
    name, _inline = _option(item)
    return RESERVED_ARGUMENTS.get(name) if name else None


def _reserved_set(value):
    """What owns a ``-set`` target, or ``None`` if the caller does.

    ``-set group.id.property=value`` is QEMU's own per-item addressing,
    and for the ``drive`` group it reaches exactly what ``-drive`` would
    have — so a property Reliquary renders is refused here as ``-drive``
    is refused, naming ``drives``; the rest is the caller's (D118). A
    value that is not of that shape is left to QEMU to refuse.
    """
    if not isinstance(value, str):
        return None
    target = value.split("=", 1)[0]
    parts = target.split(".")
    if len(parts) != 3 or parts[0] != "drive":
        return None
    if parts[2] in RESERVED_DRIVE_PROPERTIES:
        return (f"the machine's `drives` (`{parts[2]}` of drive "
                f"{parts[1]!r} is what `drives` renders)")
    return None


def settings_args(settings):
    """Validate ``backend-settings.qemu`` and render it into arguments.

    **One path, so a section that validates is a section that
    renders**: :meth:`QemuAdapter.validate_settings` calls this and
    discards the result, and the launch calls it for the arguments. A
    separate checker would be free to drift from the renderer, and the
    drift would surface as configuration accepted at create time and
    quietly missing at start.

    The section is the escape hatch, so its *values* are the caller's
    own — QEMU refuses a machine type it does not have, and that
    refusal is the caller's to read. What is judged here is the key
    set, each key's shape, and **overlap**: an argument Reliquary owns
    through a first-class field or through VM identity is refused
    naming the owner, because two sources for one fact is the one
    thing a hatch must not become.
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
                    # The target is inline (`-set drive.x.cache=none` in
                    # one element) or the next element.
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
    alternating with its value), with floppies first, hard disks next,
    and cdroms placed on the IDE bus after the last hard disk. A drive
    whose realized path is a host directory renders as vvfat — the
    one capability only knowable once resolution has run, so it is
    judged here rather than at assignment.
    """
    args = []

    floppies = [(k, v) for k, v in drives.items()
                if v["medium"] == "floppy"]
    for key, drive in sorted(floppies, key=lambda kv: kv[1]["slot"]):
        path = drive["path"]
        # id=<key> names the drive so a running insert/eject can target
        # it over QMP (the slot key is the launch id).
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
        # id=<key> as on every other drive: a hard disk is never
        # swapped live, but the slot key is how the settings hatch
        # addresses one drive's options — `-set drive.hdd0.cache=…`
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
