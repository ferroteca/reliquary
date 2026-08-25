# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The DOSBox-X backend adapter: everything that knows DOSBox-X.

Built against a personal fork, ``pgalbraith/dosbox-x`` branch
``control-channel`` (planning/design/dosbox-x.md), which adds the one
thing stock DOSBox-X lacks and this seam requires: a host-side control
channel against an *already-booted* guest (:mod:`dosboxx_control`). The
machine half — boot, media, image formats — was always a good fit; the
control half is this module's reason to exist.

DOSBox-X's own external surface before ``BOOT`` is the command line and
its built-in DOS shell (``Z:``), so materialization and launch compose a
command line and a short ``-c`` command sequence the same way
``backend_qemu`` composes a QEMU one — Reliquary drive vocabulary in,
DOSBox-X configuration out. After ``BOOT`` the *only* surface is the
control channel, which is why every carrier here rides it.

Three honest, documented gaps this backend reports rather than emulates
(P11), all traced to what the control channel's ``MOUNT``/``EJECT``
commands can actually do to a *running* instance:

- floppy/hdd have no eject-to-empty;
- a drive that started the machine empty can never receive a live
  ``insert`` (``MOUNT`` only appends to a drive that already holds a
  mounted image);
- a cdrom can only cycle among images given at launch — ``MOUNT``
  explicitly excludes ``isoDrive`` — never receive a new, never-mounted
  one while running.

See :meth:`DosboxXSession.change_medium`.

A fourth, unrelated gap: this build's ``IMGMOUNT -bootcd`` cannot boot
the actual FreeDOS LiveCD ISO the shipped ``freedos-install`` codex
recipe boots directly (a no-emulation El Torito boot record; DOSBox-X's
El Torito handling supports floppy emulation only). That is core
boot-handling, predates this adapter, and is not this module's to fix —
so the codex's worked FreeDOS example does not run on this backend yet,
and no integration test claims otherwise (planning/DECISIONS.md D120).
"""

import contextlib
import os
import shutil
import socket
import subprocess
import sys
import time
import uuid

from PIL import Image

from . import backends
from . import dosboxx_control
from .backends import Availability, BackendAdapter, Capabilities
from .dosboxx_control import ControlClient
from .errors import PreflightError, ReliquaryError, RunFailure, StaticError
from .home import effective_home


def _system_binary():
    return "dosbox-x.exe" if os.name == "nt" else "dosbox-x"


_DOSBOXX_BIN = _system_binary()

#: The keys ``backend-settings.dosbox-x`` may carry. A single escape
#: hatch (raw extra argv, appended last) rather than a second one for a
#: config-file body, for the reason ``backend_qemu.SETTINGS_KEYS``'s own
#: comment gives: a second spelling for anything below would be a second
#: source for one fact.
SETTINGS_KEYS = ("args",)

#: Flags this backend's own launch composition owns outright; naming the
#: reason mirrors ``backend_qemu.RESERVED_ARGUMENTS``.
_RESERVED_FLAGS = {
    "-headless": "the display choice a start is given",
    "-c": "the machine's drives and boot target",
    "-conf": "reliquary's own per-launch configuration",
    "-defaultdir": "reliquary's own per-machine working directory",
    "-savedir": "reliquary's own per-machine working directory",
}


def _dosboxx_fallback_dirs():
    if os.name == "nt":
        pf = os.environ.get("ProgramFiles", r"C:\Program Files")
        pf86 = os.environ.get("ProgramFiles(x86)",
                              r"C:\Program Files (x86)")
        scoop = os.environ.get("SCOOP", os.path.expanduser(r"~\scoop"))
        choco = os.environ.get("ChocolateyInstall",
                               r"C:\ProgramData\chocolatey")
        return [
            r"C:\DOSBox-X",
            os.path.join(pf, "DOSBox-X"),
            os.path.join(pf86, "DOSBox-X"),
            os.path.join(scoop, "apps", "dosbox-x", "current"),
            os.path.join(choco, "bin"),
        ]
    return ["/usr/bin", "/usr/local/bin", "/opt/dosbox-x/bin"]


def _find_dosbox_x_tool(binary):
    for variable in ("RELIQUARY_DOSBOXX_HOME", "DOSBOXX_HOME"):
        home = os.environ.get(variable)
        if not home:
            continue
        for directory in (home, os.path.join(home, "bin")):
            candidate = os.path.join(directory, binary)
            if os.path.isfile(candidate):
                return candidate
        raise PreflightError(
            f"{binary} not found under {variable}={home}",
            rule_id="machine.backend-not-found")
    found = shutil.which(binary)
    if found:
        return found
    for directory in _dosboxx_fallback_dirs():
        candidate = os.path.join(directory, binary)
        if os.path.isfile(candidate):
            return candidate
    raise PreflightError(
        f"{binary} not found: build a DOSBox-X carrying the "
        "control-channel patch (planning/design/dosbox-x.md) and set "
        "RELIQUARY_DOSBOXX_HOME to its install directory — a stock "
        "DOSBox-X on PATH has no control channel and fails at start "
        "rather than here", rule_id="machine.backend-not-found")


def find_dosbox_x():
    """Locate the DOSBox-X binary from configuration and common paths.

    Presence only — matching :func:`backend_qemu.find_qemu`'s honesty
    tier for QMP, this never proves the *control channel* exists. A
    stock, unpatched binary on ``PATH`` is found here and fails later,
    at :func:`launch_owned_dosbox_x`'s verified-launch loop, with a
    diagnostic naming the gap — the same place a QEMU with no QMP
    support would fail, never at discovery.
    """
    return _find_dosbox_x_tool(_DOSBOXX_BIN)


def _available_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _port_in_use(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def _size_megabytes(capacity):
    """Blueprint size (``\"20M\"``, ``\"2G\"``, or int MiB) -> integer MB."""
    if isinstance(capacity, bool) or not isinstance(capacity, (int, str)):
        raise StaticError(
            "capacity must be a size string or positive integer MiB value",
            rule_id="value.not-a-size")
    if isinstance(capacity, int):
        if capacity <= 0:
            raise StaticError(
                "capacity must be a positive integer MiB value",
                rule_id="value.not-a-size")
        return capacity
    text = capacity.strip()
    if not text:
        raise StaticError("capacity must be a non-empty size",
            rule_id="value.not-a-size")
    import re
    match = re.fullmatch(r"(\d+)\s*([KMGT])?", text, re.IGNORECASE)
    if match is None:
        raise StaticError(
            f"capacity is not a size Reliquary understands: {capacity!r}",
            rule_id="value.not-a-size")
    amount = int(match.group(1))
    unit = (match.group(2) or "M").upper()
    multipliers = {"K": 1 / 1024, "M": 1, "G": 1024, "T": 1024 * 1024}
    megabytes = amount * multipliers[unit]
    return int(megabytes) if megabytes >= 1 else 1


def _run_dosbox_x_headless(commands, *, action, target):
    """Run DOSBox-X headless through a short ``-c`` command sequence.

    Used for image materialization (``VHDMAKE`` is a ``Z:`` program, not
    a separate host tool). DOS-side ``WriteOut`` never reaches the
    host's stdout/stderr, so a caller cannot read *why* a DOS-side
    command failed from this call alone — it can only tell that
    DOSBox-X ran and exited. Callers verify success by checking the
    image file they expected actually appeared.
    """
    args = [find_dosbox_x(), "-headless"]
    for command in commands:
        args += ["-c", command]
    args += ["-c", "exit"]
    try:
        subprocess.run(args, capture_output=True, text=True,
                       check=False, timeout=60)
    except subprocess.TimeoutExpired as error:
        raise RunFailure(f"dosbox-x timed out {action} {target}",
                         rule_id="image.operation-failed") from error


def create_dynamic_vhd(filename, capacity):
    """Create a dynamic VHD at ``filename`` of ``capacity`` via ``VHDMAKE``."""
    if not isinstance(filename, str) or not filename.strip():
        raise StaticError("filename must be a non-empty path",
            rule_id="value.not-a-string")
    path = os.path.abspath(filename)
    if not path.lower().endswith(".vhd"):
        raise StaticError(
            f"hdd image filename must end with .vhd: {filename}",
            rule_id="image.wrong-extension")
    if os.path.exists(path):
        raise PreflightError(f"image already exists: {path}",
            rule_id="image.already-exists")
    megabytes = _size_megabytes(capacity)
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    print(f"rlq: creating VHD image: {path} ({megabytes}M)", file=sys.stderr)
    _run_dosbox_x_headless([f"VHDMAKE {path} {megabytes}M"],
                           action="creating", target=path)
    if not os.path.isfile(path):
        raise RunFailure(f"dosbox-x's VHDMAKE did not produce {path}",
                         rule_id="image.creation-failed")
    return path


def create_difference_vhd(filename, base):
    """Create a VHD differencing image chained to ``base`` via ``VHDMAKE -l``.

    ``base`` must itself be a VHD (:func:`create_dynamic_vhd` always
    produces one, so a base this adapter created qualifies).
    """
    path = os.path.abspath(os.fspath(filename))
    if not path.lower().endswith(".vhd"):
        raise StaticError(
            f"difference image filename must end with .vhd: {filename}",
            rule_id="image.wrong-extension")
    if os.path.exists(path):
        raise PreflightError(f"image already exists: {path}",
            rule_id="image.already-exists")
    base_path = os.path.abspath(os.fspath(base))
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    print(f"rlq: creating VHD difference: {path} (backing {base_path})",
          file=sys.stderr)
    _run_dosbox_x_headless([f"VHDMAKE -l {base_path} {path}"],
                           action="creating difference", target=path)
    if not os.path.isfile(path):
        raise RunFailure(f"dosbox-x's VHDMAKE did not produce {path}",
                         rule_id="image.creation-failed")
    return path


def create_duplicate_vhd(filename, base):
    """Materialize a standalone copy of ``base``.

    A plain byte copy — format-agnostic, so no DOSBox-X invocation is
    needed regardless of what format ``base`` actually holds.
    """
    path = os.path.abspath(os.fspath(filename))
    if not path.lower().endswith(".vhd"):
        raise StaticError(
            f"duplicate image filename must end with .vhd: {filename}",
            rule_id="image.wrong-extension")
    if os.path.exists(path):
        raise PreflightError(f"image already exists: {path}",
            rule_id="image.already-exists")
    base_path = os.path.abspath(os.fspath(base))
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    print(f"rlq: copying VHD: {base_path} -> {path}", file=sys.stderr)
    shutil.copyfile(base_path, path)
    return path


# -- drive layout: Reliquary keys <-> DOS drive letters -------------

def _drive_layout(drives):
    """Assign DOS drive letters to Reliquary's resolved drives.

    Floppies take ``A``/``B`` (by slot, up to 2), hard disks ``C``
    onward (by slot, up to 4), cdroms continue the alphabet after the
    last hard disk — the same floppy/hdd/cdrom ordering
    ``backend_qemu.drive_args`` renders. Returns ``{key: {"letter":,
    "medium":, "mounted": bool}}``, ``mounted`` recording whether the
    drive holds an image at launch — a drive that starts empty can
    never receive a live ``insert`` on this backend (:meth:`
    DosboxXSession.change_medium`), so the distinction is recorded once
    here rather than re-derived at every carrier call.
    """
    layout = {}
    floppies = sorted((k for k, v in drives.items() if v["medium"] == "floppy"),
                      key=lambda k: drives[k]["slot"])
    for index, key in enumerate(floppies[:2]):
        layout[key] = {"letter": chr(ord("a") + index), "medium": "floppy",
                       "mounted": drives[key]["path"] is not None}

    hdds = sorted((k for k, v in drives.items() if v["medium"] == "hdd"),
                  key=lambda k: drives[k]["slot"])
    for index, key in enumerate(hdds[:4]):
        layout[key] = {"letter": chr(ord("c") + index), "medium": "hdd",
                       "mounted": drives[key]["path"] is not None}

    next_letter = ord("c") + min(len(hdds), 4)
    cdroms = sorted((k for k, v in drives.items() if v["medium"] == "cdrom"),
                    key=lambda k: drives[k]["slot"])
    for index, key in enumerate(cdroms):
        layout[key] = {"letter": chr(next_letter + index), "medium": "cdrom",
                       "mounted": drives[key]["path"] is not None}
    return layout


_IMGMOUNT_TYPE = {"floppy": "floppy", "hdd": "hdd", "cdrom": "iso"}


def _mount_commands(drives, layout):
    """The ``-c "IMGMOUNT ..."`` sequence for every drive holding media."""
    commands = []
    for key, info in sorted(layout.items(), key=lambda kv: kv[1]["letter"]):
        drive = drives[key]
        if drive["path"] is None:
            continue
        letter = info["letter"].upper()
        kind = _IMGMOUNT_TYPE[info["medium"]]
        commands.append(f"IMGMOUNT {letter}: {drive['path']} -t {kind}")
    return commands


def _boot_command(boot_keys, drives, layout):
    """The one ``BOOT <letter>:`` command, or ``None`` with nothing to boot.

    DOSBox-X's ``BOOT`` boots the named drive directly rather than
    walking a BIOS-style fallback order, so only Reliquary's first
    resolved boot candidate applies here — an honest narrowing of the
    ``boot`` list's fuller meaning on QEMU/VirtualBox.
    """
    for key in boot_keys:
        info = layout.get(key)
        if info is not None and drives.get(key, {}).get("path") is not None:
            return f"BOOT {info['letter'].upper()}:"
    return None


# -- backend-settings.dosbox-x: the args escape hatch ---------------

def _reserved_argument(item, extra, index):
    """What owns ``item``, or ``None`` if the caller does."""
    if item in _RESERVED_FLAGS:
        return _RESERVED_FLAGS[item]
    if item == "-set":
        following = extra[index + 1] if index + 1 < len(extra) else None
        if following:
            section, _, rest = following.partition(" ")
            prop = rest.split("=", 1)[0].strip()
            if section == "control":
                return "the recorded VM identity"
            if section == "dosbox" and prop == "memsize":
                return "the machine's `memory`"
    return None


def settings_args(settings):
    """Validate ``backend-settings.dosbox-x`` and render it into arguments.

    One path, as ``backend_qemu.settings_args`` is for the same reason:
    :meth:`DosboxXAdapter.validate_settings` calls this and discards the
    result, and the launch calls it for the arguments.
    """
    settings = settings or {}
    unknown = sorted(key for key in settings if key not in SETTINGS_KEYS)
    if unknown:
        raise StaticError(
            f"backend-settings.dosbox-x does not define {unknown[0]!r}; "
            f"the dosbox-x keys are {', '.join(SETTINGS_KEYS)}",
            rule_id="machine.settings-unknown-key")
    args = []
    extra = settings.get("args")
    if extra is not None:
        if not isinstance(extra, list):
            raise StaticError(
                "backend-settings.dosbox-x.args must be an array of "
                f"arguments, got: {extra!r}", rule_id="value.not-an-array")
        for index, item in enumerate(extra):
            if not isinstance(item, str) or not item:
                raise StaticError(
                    f"backend-settings.dosbox-x.args[{index}] must be a "
                    f"non-empty string, got: {item!r}",
                    rule_id="value.not-a-string")
            owner = _reserved_argument(item, extra, index)
            if owner is not None:
                raise StaticError(
                    f"backend-settings.dosbox-x.args[{index}] is {item!r}, "
                    f"which reliquary owns through {owner} — settings may "
                    "not restate what the blueprint already says",
                    rule_id="machine.settings-reserved-argument")
            args.append(item)
    return args


# -- identity, start, stop -------------------------------------------

def verify_vm(client, expected_name, expected_token):
    """Fail closed unless ``client`` is authenticated as the exact instance.

    Two checks stand in for QMP's name+uuid pair: ``IDENTIFY``'s
    ``backend-id`` is the readable name (repeats across homes, same as
    QEMU's ``-name``), and a successful ``AUTH`` with the per-start
    token is the proof no name comparison alone could give — a wrong
    token drops the connection rather than answering, so *reaching*
    "authenticated" is itself the identity check.
    """
    info = client.identify()
    actual_name = info.get("backend-id")
    if actual_name != expected_name:
        raise PreflightError(
            "dosbox-x control channel identity mismatch; the unrelated "
            "VM was not modified\n"
            f"  expected: {expected_name}\n"
            f"  found:    {actual_name or '<no backend-id>'}",
            rule_id="machine.identity-mismatch")
    try:
        client.auth(expected_token)
    except RunFailure as error:
        raise PreflightError(
            "dosbox-x control channel identity mismatch; the unrelated "
            "VM was not modified\n"
            f"  expected: {expected_name} (token authentication failed)",
            rule_id="machine.identity-mismatch") from error


def _endpoint_port(vm):
    endpoint = (vm or {}).get("endpoint")
    port = endpoint.get("port") if isinstance(endpoint, dict) else None
    if (not isinstance(port, int) or isinstance(port, bool)
            or not 1 <= port <= 65535):
        raise PreflightError(
            "the recorded dosbox-x endpoint is not a usable control "
            f"port: {endpoint!r}", rule_id="machine.endpoint-invalid")
    return port


def _startup_error(proc, stderr_log, port, detail, args):
    try:
        with open(stderr_log, errors="replace") as stderr_file:
            stderr = stderr_file.read().strip()
    except OSError:
        stderr = ""
    message = f"{detail}\n  control port: 127.0.0.1:{port}"
    if proc.returncode is not None:
        message += f"\n  dosbox-x exit status: {proc.returncode}"
    if stderr:
        message += f"\n  dosbox-x output: {stderr}"
    message += f"\n  command line: {subprocess.list2cmdline(args)}"
    return RunFailure(message, rule_id="machine.backend-failed-to-start")


def _terminate_started_process(proc):
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def launch_owned_dosbox_x(state, *, backend_dir, display=False, current=None):
    """Render the machine state into a DOSBox-X launch and verify it.

    Reliquary drive vocabulary in, DOSBox-X configuration out: memory,
    the ``IMGMOUNT``/``BOOT`` sequence, and the control-channel identity
    are all rendered here. **Verify-then-return**, exactly like
    :func:`backend_qemu.launch_owned_qemu`'s QMP retry loop: the process
    is launched, then the control channel is connected to, ``PING``ed,
    ``IDENTIFY``ed and ``AUTH``ed within the startup deadline — a
    stock/unpatched binary fails here, naming the gap, rather than
    appearing to have started with nothing listening behind it.
    """
    memory = state.get("memory") or 16
    cpus = state.get("cpus")
    if cpus is not None and cpus > 1:
        raise PreflightError(
            f"dosbox-x cannot emulate more than one CPU (cpus={cpus}): "
            "its local APIC is faked, not emulated (planning/design/"
            "dosbox-x.md)", rule_id="machine.cpus-unsupported")
    vm_name = state.get("backend-id") or f"reliquary-{state['id']}"

    if current:
        current_port = _endpoint_port(current)
        try:
            with ControlClient("127.0.0.1", current_port,
                               timeout=2) as old_client:
                verify_vm(old_client, current["backend-id"],
                         current["token"])
        except (OSError, PreflightError):
            pass  # stale identity; the caller overwrites it
        else:
            raise PreflightError(
                "a reliquary VM is already active\n"
                f"  name: {current['backend-id']}\n"
                f"  control port: 127.0.0.1:{current_port}\n"
                "stop it before starting another VM for this machine",
                rule_id="machine.vm-already-active")

    token = str(uuid.uuid4())
    port = _available_port()
    drives = state.get("drives", {})
    layout = _drive_layout(drives)

    args = [find_dosbox_x()]
    if not display:
        args.append("-headless")
    args += ["-set", "control enabled=true",
             "-set", f"control port={port}",
             "-set", f"control token={token}",
             "-set", f"control backend-id={vm_name}",
             "-set", f"dosbox memsize={memory}"]
    for command in _mount_commands(drives, layout):
        args += ["-c", command]
    boot = _boot_command(state.get("boot", []), drives, layout)
    if boot is not None:
        args += ["-c", boot]
    args += settings_args((state.get("backend-settings") or {}).get("dosbox-x"))

    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = (subprocess.DETACHED_PROCESS
                                   | subprocess.CREATE_NEW_PROCESS_GROUP)
    base = effective_home(backend_dir)
    os.makedirs(base, exist_ok=True)
    stderr_log = os.path.join(base, "dosbox-x-stderr.log")
    with open(stderr_log, "wb") as error_file:
        proc = subprocess.Popen(args, stdout=error_file,
                                stderr=subprocess.STDOUT, **kwargs)

    deadline = time.monotonic() + 15
    while True:
        if proc.poll() is not None:
            raise _startup_error(
                proc, stderr_log, port,
                "dosbox-x exited during startup", args)
        try:
            with ControlClient("127.0.0.1", port, timeout=2) as client:
                client.ping()
                verify_vm(client, vm_name, token)
            break
        except (OSError, RunFailure):
            if time.monotonic() > deadline:
                _terminate_started_process(proc)
                raise _startup_error(
                    proc, stderr_log, port,
                    "dosbox-x's control channel did not come up before "
                    "the startup deadline — a stock/unpatched dosbox-x "
                    "has no control channel at all; check "
                    "RELIQUARY_DOSBOXX_HOME", args)
            time.sleep(0.3)
        except ReliquaryError:
            _terminate_started_process(proc)
            raise
    print(f"rlq: DOSBox-X started: {vm_name} "
          f"(control channel on 127.0.0.1:{port})", file=sys.stderr)
    print(f"rlq: command line: {subprocess.list2cmdline(args)}",
          file=sys.stderr)
    return backends.identity(
        "dosbox-x", vm_name, token, {"port": port, "drives": layout},
        pid=proc.pid)


def stop(vm):
    """Power off the identified owned VM (no persistence)."""
    if not vm:
        raise PreflightError("no recorded reliquary VM to stop",
            rule_id="machine.no-active-vm")
    port = _endpoint_port(vm)
    expected_name = vm["backend-id"]
    expected_token = vm["token"]
    try:
        with ControlClient("127.0.0.1", port, timeout=5) as client:
            verify_vm(client, expected_name, expected_token)
            client.stop()
    except OSError as error:
        raise PreflightError(
            "the recorded reliquary VM is no longer reachable\n"
            f"  expected: {expected_name} on 127.0.0.1:{port}",
            rule_id="machine.vm-unreachable") from error
    deadline = time.monotonic() + 15
    while _port_in_use(port):
        if time.monotonic() > deadline:
            raise RunFailure(
                "dosbox-x is still holding the control port 15s after "
                "STOP; a following start() on the same port would "
                "collide", rule_id="machine.port-not-released")
        time.sleep(0.5)
    print("rlq: VM stopped", file=sys.stderr)


# -- carriers -----------------------------------------------------

class DosboxXSession:
    """The carriers a running DOSBox-X offers, over one verified session."""

    backend = "dosbox-x"

    #: Native character readback out of VGA text memory, same tier as
    #: QEMU's agentless-display plane — cheap, and recognizing no
    #: pixels.
    recognizes_text = False

    def __init__(self, client, drives=None):
        self._client = client
        self._drives = dict(drives or {})

    def native(self):
        """No portable native hatch beyond the control channel itself."""
        raise PreflightError(
            "DOSBox-X has no native escape hatch beyond the control "
            "channel's own commands; drive the machine through the "
            "portable carriers", rule_id="machine.backend-no-native")

    def send_keys(self, combos, delay=0.06):
        """Inject key combinations as ``KEYDOWN``/``KEYUP`` pairs.

        A combo's keys go down in order and up in reverse, the same
        expansion the RFB and VirtualBox carriers use for a
        press-then-release sequence with no native "chord" primitive.
        """
        for combo in combos:
            names = [dosboxx_control.key_name_for(key) for key in combo]
            for name in names:
                self._client.keydown(name)
            for name in reversed(names):
                self._client.keyup(name)
            time.sleep(delay)

    def text_screen(self, font_banks=()):
        """The native text readback: (character rows, attribute rows).

        ``font_banks`` (F61) is accepted and ignored, for the reason
        ``QemuSession.text_screen`` gives: a native text-memory read
        recognizes no pixels.
        """
        rows = [row.rstrip() for row in self._client.screen()]
        attributes = [list(row) for row in self._client.attributes()]
        return rows, attributes

    def framebuffer(self):
        """Refused: this plane's screen is text memory, not pixels."""
        raise PreflightError(
            "the agentless-display plane reads DOSBox-X's VGA text "
            "memory and captures no framebuffer; a landmark condition "
            "needs a plane that does",
            rule_id="machine.plane-no-framebuffer")

    def pointer_event(self, x, y, buttons):
        """Refused: the control channel carries no pointer-event command."""
        raise PreflightError(
            "the dosbox-x control channel has no pointer-event command, "
            "so this plane cannot deliver one",
            rule_id="machine.plane-no-pointer-input")

    def screenshot(self, path):
        """Capture the framebuffer to ``path`` as a PNG (diagnostic only).

        Independent of the sampling path :meth:`text_screen` uses —
        ``SCREENSHOT`` reads the same persistent render buffer DOSBox-X's
        own capture feature does, whatever mode the guest is in.
        """
        width, height, data = self._client.screenshot()
        png = os.path.abspath(os.fspath(path))
        parent = os.path.dirname(png)
        if parent:
            os.makedirs(parent, exist_ok=True)
        Image.frombytes("RGB", (width, height), data).save(png)
        return png

    def change_medium(self, drive_key, path=None):
        """Swap or eject a removable medium on the running machine.

        **Asymmetric by medium kind, reported honestly rather than
        emulated** — see the module docstring for the three gaps this
        reflects:

        - cdrom: ``path=None`` ejects (confirmed working); a *new*,
          never-mounted path is refused (``MOUNT`` excludes CD images).
        - floppy/hdd: a drive that started the machine empty can never
          receive a live insert (``MOUNT`` requires an already-mounted
          image to append to); an already-mounted drive accepts a new
          path via ``MOUNT`` then ``SWAP`` to the position ``MOUNT``
          reports, but ejecting to empty (``path=None``) is refused —
          this branch has no floppy/hdd eject-to-empty.
        """
        info = self._drives.get(drive_key)
        if info is None:
            raise PreflightError(
                f"drive {drive_key!r} has no recorded DOSBox-X letter "
                "on this VM", rule_id="machine.slot-not-declared")
        letter = info["letter"].upper()
        medium = info["medium"]
        if medium == "cdrom":
            if path is None:
                self._client.eject(letter)
                return
            raise PreflightError(
                f"the dosbox-x control channel cannot attach a new, "
                f"never-mounted CD-ROM image to drive {letter}: while "
                "running, MOUNT works for floppy/hdd only, and EJECT "
                "only removes — cycling among images given at launch "
                "is the one live cdrom change this backend can honor",
                rule_id="machine.change-medium-unsupported")
        if path is None:
            raise PreflightError(
                f"the dosbox-x control channel cannot eject drive "
                f"{letter} to empty; floppy/hdd eject-to-empty is not "
                "implemented on this control channel (planning/design/"
                "dosbox-x.md)",
                rule_id="machine.change-medium-unsupported")
        if not info["mounted"]:
            raise PreflightError(
                f"the dosbox-x control channel cannot insert into "
                f"drive {letter}: it started this machine empty, and "
                "MOUNT can only append to a drive that already holds a "
                "mounted image", rule_id="machine.change-medium-unsupported")
        position = self._client.mount(letter, path)
        self._client.swap(letter, position=position)


class DosboxXAdapter(BackendAdapter):
    """DOSBox-X: lifecycle, VHD materialization, and the control channel."""

    name = "dosbox-x"
    settings_keys = SETTINGS_KEYS

    def discover(self, platform=None):
        # One host tool whatever the guest platform is, as VirtualBox's
        # discover() reads: platform is accepted for the seam's
        # uniform signature and not asked for here.
        try:
            executable = find_dosbox_x()
        except PreflightError as missing:
            return Availability("dosbox-x", False, detail=str(missing))
        return Availability(
            "dosbox-x", True, executable=executable,
            home=os.path.dirname(executable),
            detail=f"found at {executable}")

    def capabilities(self):
        """What this control channel provides today.

        No ``vvfat`` (``MOUNT`` of a host directory is a built-in-DOS,
        pre-``BOOT`` feature — the same distinction that governs every
        gap this module documents), and no pointing devices (the
        protocol carries no pointer event at all).
        """
        return Capabilities(
            backend="dosbox-x",
            control_planes=("agentless-display",),
            media=("floppy", "hdd", "cdrom"),
            controllers=("ide",),
            materialize=("new", "difference", "copy", "use"),
            vvfat=False,
            pointing_devices=(),
        )

    def validate_settings(self, settings):
        settings_args(settings)

    # -- materialize and dispose ----------------------------------

    def image_path(self, root, stem):
        """DOSBox-X's native per-machine image: a dynamic VHD."""
        return os.path.join(root, f"{stem}.vhd")

    def create_image(self, path, *, mode, size=None, base=None):
        if mode == "new":
            return create_dynamic_vhd(path, size)
        if mode == "difference":
            return create_difference_vhd(path, base)
        if mode == "copy":
            return create_duplicate_vhd(path, base)
        raise StaticError(
            f"the dosbox-x adapter cannot materialize an image for "
            f"mode {mode!r}", rule_id="image.mode-unsupported")

    # -- start, stop, liveness ------------------------------------

    def start(self, state, *, machine_dir, backend_dir, display=False,
              current=None):
        return launch_owned_dosbox_x(
            state, backend_dir=backend_dir, display=display,
            current=current)

    def stop(self, vm):
        return stop(vm)

    @contextlib.contextmanager
    def session(self, vm, cache=None):
        """Yield an identity-verified session over the recorded VM.

        ``cache`` is accepted for the seam's uniform signature and
        ignored: this plane reads native character memory, where the
        guest has already resolved its characters, so there is no host
        font to extract or cache (as QEMU's agentless plane ignores it
        for the same reason).
        """
        port = _endpoint_port(vm)
        name = vm["backend-id"]
        token = vm["token"]
        try:
            client = ControlClient("127.0.0.1", port, timeout=5)
        except OSError as error:
            raise PreflightError(
                "the recorded reliquary VM is no longer reachable\n"
                f"  expected: {name} on 127.0.0.1:{port}",
                rule_id="machine.vm-unreachable") from error
        try:
            verify_vm(client, name, token)
            drives = (vm.get("endpoint") or {}).get("drives")
            yield DosboxXSession(client, drives=drives)
        finally:
            client.close()
