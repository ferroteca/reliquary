# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The VirtualBox backend adapter: everything that knows VirtualBox.

F50: lifecycle and VDI materialization. Discovery, image creation,
``createvm`` under the machine's ``virtualbox/`` directory, start /
stop with identity verification, and dispose. F52: agentless-display
carriers — ``keyboardputscancode``, ``screenshotpng``, live medium
change, and ``text_screen`` via ``text_recognize``.
"""

import contextlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

from PIL import Image

from . import backends
from . import text_recognize
from .backends import Availability, BackendAdapter, Capabilities
from .errors import PreflightError, RunFailure, StaticError


_VBOX_BIN = "VBoxManage.exe" if os.name == "nt" else "VBoxManage"

#: IDE controller name inside every Reliquary-owned VirtualBox VM.
_IDE = "reliquary-ide"
#: Floppy controller name (absent when the machine has no floppy).
_FLOPPY = "reliquary-floppy"

#: ``VBoxManage --bootN`` values for Reliquary media kinds.
_BOOT_KIND = {"floppy": "floppy", "hdd": "disk", "cdrom": "dvd"}


def _program_files():
    return [
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
    ]


def _which(binary, directories=()):
    found = shutil.which(binary)
    if found:
        return found
    for directory in directories:
        candidate = os.path.join(directory, binary)
        if os.path.isfile(candidate):
            return candidate
    return None


def find_vboxmanage():
    """Locate ``VBoxManage`` on PATH or in a conventional install."""
    directories = []
    if os.name == "nt":
        home = os.environ.get("VBOX_MSI_INSTALL_PATH") or ""
        if home:
            directories.append(home)
        directories += [os.path.join(root, "Oracle", "VirtualBox")
                       for root in _program_files()]
    else:
        directories = ["/usr/bin", "/usr/local/bin"]
    found = _which(_VBOX_BIN, directories)
    if found:
        return found
    raise PreflightError(
        f"{_VBOX_BIN} not found: install VirtualBox, add it to PATH, "
        "or set VBOX_MSI_INSTALL_PATH to its install directory",
        rule_id="machine.backend-not-found")


#: Files shipped with VirtualBox that embed its VGA BIOS, most
#: likely first. The BIOS is not a standalone ROM in current builds,
#: so the bank is carved out of the module that carries it.
_BIOS_CARRIERS = ("VBoxDD2.dll", "VBoxDD.dll", "VBoxDDU.dll",
                  "VBoxDD2.so", "VBoxDD.so")


def guest_glyph_banks(cache=None):
    """Every VGA font this host's VirtualBox paints DOS text with.

    **Read off the host, never shipped.** Reading a VirtualBox screen
    through Reliquary's own bank turns `Welcome` into `Uelcooe` and
    misses every wait on the word; the right glyphs are the installed
    emulator's, and taking them from the installation is also what
    keeps another project's font out of this tree
    (:func:`text_recognize.cached_banks`).

    **Plural, because one run paints in more than one.** A stock
    install offers two 8x16 fonts — the bank as stored, which is what
    a DOS guest ends up drawing with, and the same bank with the
    BIOS's override table applied, which is what the BIOS draws its
    own boot messages with. They differ in 19 glyphs, `W` and `m`
    among them, and no screenshot says which one painted it. Both go
    to the recognizer.
    """
    def extract():
        # Resolved inside the extractor, so a cache hit answers
        # without going near the installation at all.
        home = os.path.dirname(find_vboxmanage())
        return text_recognize.banks_from_files(
            [os.path.join(home, name) for name in _BIOS_CARRIERS],
            "VirtualBox")

    return text_recognize.cached_banks(cache, "virtualbox", extract)


def run_vbox(args, *, action, target=None):
    """Run one ``VBoxManage`` invocation; raise on a non-zero exit.

    Returns the completed process (stdout captured). ``action`` and
    ``target`` shape the failure message.
    """
    executable = find_vboxmanage()
    command = [executable, *args]
    completed = subprocess.run(
        command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        where = f" {target}" if target else ""
        raise RunFailure(
            f"VBoxManage failed {action}{where}"
            + (f": {detail}" if detail else ""),
            rule_id="machine.backend-failed")
    return completed


def size_megabytes(capacity):
    """Blueprint size (``\"20M\"``, ``\"2G\"``, or int MiB) → integer MB.

    ``VBoxManage createmedium --size`` takes megabytes.
    """
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
    match = re.fullmatch(r"(\d+)\s*([KMGT])?", text, re.IGNORECASE)
    if match is None:
        raise StaticError(
            f"capacity is not a size Reliquary understands: {capacity!r}",
            rule_id="value.not-a-size")
    amount = int(match.group(1))
    unit = (match.group(2) or "M").upper()
    multipliers = {"K": 1 / 1024, "M": 1, "G": 1024, "T": 1024 * 1024}
    megabytes = amount * multipliers[unit]
    if megabytes < 1:
        megabytes = 1
    return int(megabytes)


def create_vdi(filename, capacity):
    """Create a dynamic VDI at ``filename`` of ``capacity``."""
    if not isinstance(filename, str) or not filename.strip():
        raise StaticError("filename must be a non-empty path",
            rule_id="value.not-a-string")
    path = os.path.abspath(filename)
    if not path.lower().endswith(".vdi"):
        raise StaticError(
            f"hdd image filename must end with .vdi: {filename}",
            rule_id="image.wrong-extension")
    megabytes = size_megabytes(capacity)
    if os.path.exists(path):
        raise PreflightError(f"image already exists: {path}",
            rule_id="image.already-exists")
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    print(f"rlq: creating VDI image: {path} ({megabytes}M)",
          file=sys.stderr)
    run_vbox(
        ["createmedium", "disk", f"--filename={path}",
         f"--size={megabytes}", "--format=VDI"],
        action="creating", target=path)
    return path


def create_difference_vdi(filename, base):
    """Create a VDI differencing image backed by ``base``."""
    path = os.path.abspath(filename)
    if not path.lower().endswith(".vdi"):
        raise StaticError(
            f"hdd image filename must end with .vdi: {filename}",
            rule_id="image.wrong-extension")
    if os.path.exists(path):
        raise PreflightError(f"image already exists: {path}",
            rule_id="image.already-exists")
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    base_path = os.path.abspath(base)
    print(f"rlq: creating VDI difference: {path} (base {base_path})",
          file=sys.stderr)
    run_vbox(
        ["createmedium", "disk", f"--filename={path}",
         f"--diffparent={base_path}", "--format=VDI"],
        action="creating difference", target=path)
    return path


def create_duplicate_vdi(filename, base):
    """Clone ``base`` into a new VDI at ``filename``."""
    path = os.path.abspath(filename)
    if not path.lower().endswith(".vdi"):
        raise StaticError(
            f"hdd image filename must end with .vdi: {filename}",
            rule_id="image.wrong-extension")
    if os.path.exists(path):
        raise PreflightError(f"image already exists: {path}",
            rule_id="image.already-exists")
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    base_path = os.path.abspath(base)
    print(f"rlq: cloning VDI: {base_path} -> {path}", file=sys.stderr)
    run_vbox(
        ["clonemedium", "disk", base_path, path, "--format=VDI"],
        action="cloning", target=path)
    return path


def _machinereadable(vm_id):
    """``showvminfo --machinereadable`` as a ``{key: value}`` map."""
    completed = run_vbox(
        ["showvminfo", vm_id, "--machinereadable"],
        action="reading", target=vm_id)
    info = {}
    for line in completed.stdout.splitlines():
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        info[key] = value.strip('"')
    return info


#: ``VMState`` values that mean the guest is no longer executing. The
#: VM object survives a power-off, so `showvminfo` keeps answering and
#: only the state tells a live machine from a dead one. Membership is
#: the safe polarity: every other state — including transitional ones
#: like ``starting`` and ``restoring`` — counts as live, so a slow
#: power-on is never mistaken for a power-off.
_STOPPED_STATES = frozenset({
    "poweroff", "aborted", "aborted-saved", "saved", "teleported",
})


def _not_running(vm_id, state=None):
    """The stopped observation, in the shape the runner reads.

    A VM that is registered but not executing is a condition of the
    world rather than a failure of the work, and `script_runner._read`
    turns exactly this rule id into `wait machine=stopped`.
    """
    detail = f"\n  state: {state}" if state else ""
    return PreflightError(
        f"the reliquary VM is not running\n  uuid:  {vm_id}{detail}",
        rule_id="machine.vm-unreachable")


def vm_stopped(vm_id):
    """Whether VirtualBox reports ``vm_id`` as no longer executing.

    Unregistered or unanswerable is not stopped: that is a different
    condition, and the caller's own failure describes it better.
    """
    try:
        info = _machinereadable(vm_id)
    except RunFailure:
        return False
    return info.get("VMState") in _STOPPED_STATES


def verify_vm(vm_id, expected_uuid):
    """Fail closed unless ``vm_id`` resolves to ``expected_uuid``."""
    try:
        info = _machinereadable(vm_id)
    except RunFailure as error:
        raise PreflightError(
            "the recorded reliquary VM is no longer reachable\n"
            f"  expected: {expected_uuid}",
            rule_id="machine.vm-unreachable") from error
    actual = info.get("UUID") or info.get("uuid")
    if (not isinstance(actual, str)
            or actual.casefold() != expected_uuid.casefold()):
        raise PreflightError(
            "VirtualBox VM identity mismatch\n"
            f"  expected: {expected_uuid}\n"
            f"  found:    {actual or '<no uuid>'}",
            rule_id="machine.vm-identity-mismatch")
    return info


def _vm_name(state):
    return state.get("backend-id") or f"reliquary-{state['id']}"


def _boot_order(boot, drives):
    """Map Reliquary ``boot`` keys onto VirtualBox ``--bootN`` kinds."""
    kinds = []
    for key in boot or []:
        drive = drives.get(key) or {}
        kind = _BOOT_KIND.get(drive.get("medium"))
        if kind is not None and kind not in kinds:
            kinds.append(kind)
    while len(kinds) < 4:
        kinds.append("none")
    return kinds[:4]


def _ide_slot(index):
    """IDE (port, device) for the Nth non-floppy drive (0-based)."""
    return index // 2, index % 2


def _attach_args(vm_name, storagectl, port, device, medium_type, path):
    medium = "emptydrive" if path is None else os.path.abspath(path)
    return [
        "storageattach", vm_name,
        f"--storagectl={storagectl}",
        f"--port={port}", f"--device={device}",
        f"--type={medium_type}", f"--medium={medium}",
    ]


def drive_attachments(state):
    """Map each drive key to its VirtualBox storage attachment.

    Mirrors :func:`configure_vm`'s placement so a live
    ``change_medium`` can retarget the same port the guest sees.

    **Hard disks take the IDE slots before cdroms**, which is the
    layout the QEMU renderer already documents — floppies, then hard
    disks, then cdroms after them. Ordering the two kinds together by
    key instead made slot assignment fall out of the *alphabet*: with
    the usual `cdrom0` and `hdd0` names, `cdrom0` sorts first and
    takes the primary master, leaving the boot disk on the slave. A
    PC BIOS told to boot `disk` does not reliably find one there, so
    a machine whose disk had become bootable would still stop at
    `No active partition` — and nothing about the blueprint said to
    put them in that order.
    """
    drives = state.get("drives") or {}
    attachments = {}
    floppies = []
    hdds = []
    cdroms = []
    for key, drive in sorted(drives.items()):
        medium = drive.get("medium")
        if medium == "floppy":
            floppies.append(key)
        elif medium == "hdd":
            hdds.append((key, drive))
        elif medium == "cdrom":
            cdroms.append((key, drive))
    disks = hdds + cdroms
    for index, key in enumerate(floppies[:2]):
        attachments[key] = {
            "storagectl": _FLOPPY, "port": index, "device": 0,
            "type": "fdd",
        }
    for index, (key, drive) in enumerate(disks[:4]):
        port, device = _ide_slot(index)
        attachments[key] = {
            "storagectl": _IDE, "port": port, "device": device,
            "type": ("dvddrive" if drive.get("medium") == "cdrom"
                     else "hdd"),
        }
    return attachments


def configure_vm(state, vm_name):
    """Apply Reliquary drive vocabulary to a registered VirtualBox VM.

    Returns the attachment map :func:`drive_attachments` builds — the
    same placement written into the identity endpoint so a later
    session can change media without re-deriving the layout.
    """
    memory = state.get("memory") or 16
    cpus = state.get("cpus") if state.get("cpus") is not None else 1
    drives = state.get("drives") or {}
    boot = _boot_order(state.get("boot"), drives)
    run_vbox(
        ["modifyvm", vm_name,
         f"--memory={memory}", f"--cpus={cpus}",
         f"--boot1={boot[0]}", f"--boot2={boot[1]}",
         f"--boot3={boot[2]}", f"--boot4={boot[3]}"],
        action="configuring", target=vm_name)

    # Drop controllers we own and rebuild from state, so a restart
    # after apply_blueprint or insert/eject (stopped) matches the
    # recorded drives exactly.
    info = _machinereadable(vm_name)
    for key, value in info.items():
        if key.startswith("storagecontrollername") and value in (
                _IDE, _FLOPPY):
            run_vbox(
                # `--name` is passed as two tokens here and joined by
                # `=` everywhere else, which is not a style choice:
                # VBoxManage 7.2 rejects `--name=X --remove` with
                # "Too few parameters" and accepts `--name X --remove`.
                # The joined form works alongside `--add`, so only the
                # removal is spelled this way.
                ["storagectl", vm_name, "--name", value, "--remove"],
                action="removing controller", target=value)

    attachments = drive_attachments(state)
    if any(a["storagectl"] == _FLOPPY for a in attachments.values()):
        run_vbox(
            ["storagectl", vm_name, f"--name={_FLOPPY}",
             "--add=floppy", "--controller=I82078"],
            action="adding floppy controller", target=vm_name)

    run_vbox(
        ["storagectl", vm_name, f"--name={_IDE}",
         "--add=ide", "--controller=PIIX4"],
        action="adding IDE controller", target=vm_name)

    for key, attach in attachments.items():
        path = (drives.get(key) or {}).get("path")
        run_vbox(
            _attach_args(vm_name, attach["storagectl"], attach["port"],
                         attach["device"], attach["type"], path),
            action="attaching drive", target=key)
    return attachments


def ensure_vm(state, *, backend_dir):
    """Register the VirtualBox machine if absent; return UUID + attachments."""
    name = _vm_name(state)
    os.makedirs(backend_dir, exist_ok=True)
    try:
        info = _machinereadable(name)
        vm_uuid = info.get("UUID") or info.get("uuid")
        if not vm_uuid:
            raise RunFailure(
                f"VirtualBox VM {name!r} has no UUID",
                rule_id="machine.backend-failed")
    except RunFailure:
        vm_uuid = str(uuid.uuid4())
        print(f"rlq: creating VirtualBox VM: {name} ({vm_uuid})",
              file=sys.stderr)
        run_vbox(
            ["createvm", f"--name={name}", f"--uuid={vm_uuid}",
             f"--basefolder={os.path.abspath(backend_dir)}",
             "--platform-architecture=x86", "--ostype=DOS",
             "--register"],
            action="creating VM", target=name)
    attachments = configure_vm(state, name)
    return vm_uuid, attachments


def launch_owned_vm(state, *, backend_dir, display=False, current=None):
    """Ensure the VM, power it on, return the verified identity."""
    if current:
        try:
            verify_vm(current["backend-id"], current["token"])
        except PreflightError:
            pass  # stale identity; overwrite below
        else:
            # showvminfo succeeds for a powered-off VM too, so also
            # refuse when the recorded one is still running.
            info = _machinereadable(current["backend-id"])
            if info.get("VMState") == "running":
                raise PreflightError(
                    "a reliquary VM is already active\n"
                    f"  uuid: {current['backend-id']}\n"
                    "stop it before starting another VM for this machine",
                    rule_id="machine.vm-already-active")

    vm_uuid, attachments = ensure_vm(state, backend_dir=backend_dir)
    name = _vm_name(state)
    start_type = "gui" if display else "headless"
    print(f"rlq: VirtualBox starting: {name} ({vm_uuid})", file=sys.stderr)
    run_vbox(
        ["startvm", vm_uuid, f"--type={start_type}"],
        action="starting", target=name)
    verify_vm(vm_uuid, vm_uuid)
    return backends.identity(
        "virtualbox", vm_uuid, vm_uuid,
        {"name": name, "drives": attachments})


def stop(vm):
    """Power off the identified owned VM (no persistence)."""
    if not vm:
        raise PreflightError("no recorded reliquary VM to stop",
            rule_id="machine.no-active-vm")
    expected = vm["backend-id"]
    token = vm["token"]
    info = verify_vm(expected, token)
    if info.get("VMState") in _STOPPED_STATES:
        # A guest that powered itself off leaves the VM registered and
        # idle. Stop asks for a machine that is off, and this one is:
        # `controlvm poweroff` would refuse, and refusing here would
        # strand the machine as un-stoppable and so un-destroyable.
        return
    run_vbox(
        ["controlvm", expected, "poweroff"],
        action="stopping", target=expected)


# -- F52 agentless-display carriers --------------------------------

#: Seam key names (QEMU qcodes today — see ``control_display`` /
#: ``script_runner``) → PS/2 set-1 make scancodes. Extended keys are
#: a tuple whose first byte is ``0xe0``.
_SCANCODES = {
    "esc": (0x01,),
    "1": (0x02,), "2": (0x03,), "3": (0x04,), "4": (0x05,),
    "5": (0x06,), "6": (0x07,), "7": (0x08,), "8": (0x09,),
    "9": (0x0a,), "0": (0x0b,),
    "minus": (0x0c,), "equal": (0x0d,),
    "backspace": (0x0e,), "tab": (0x0f,),
    "q": (0x10,), "w": (0x11,), "e": (0x12,), "r": (0x13,),
    "t": (0x14,), "y": (0x15,), "u": (0x16,), "i": (0x17,),
    "o": (0x18,), "p": (0x19,),
    "bracket_left": (0x1a,), "bracket_right": (0x1b,),
    "ret": (0x1c,), "ctrl": (0x1d,),
    "a": (0x1e,), "s": (0x1f,), "d": (0x20,), "f": (0x21,),
    "g": (0x22,), "h": (0x23,), "j": (0x24,), "k": (0x25,),
    "l": (0x26,),
    "semicolon": (0x27,), "apostrophe": (0x28,),
    "grave_accent": (0x29,), "shift": (0x2a,),
    "backslash": (0x2b,),
    "z": (0x2c,), "x": (0x2d,), "c": (0x2e,), "v": (0x2f,),
    "b": (0x30,), "n": (0x31,), "m": (0x32,),
    "comma": (0x33,), "dot": (0x34,), "slash": (0x35,),
    "alt": (0x38,), "spc": (0x39,),
    "f1": (0x3b,), "f2": (0x3c,), "f3": (0x3d,), "f4": (0x3e,),
    "f5": (0x3f,), "f6": (0x40,), "f7": (0x41,), "f8": (0x42,),
    "f9": (0x43,), "f10": (0x44,), "f11": (0x57,), "f12": (0x58,),
    "home": (0xe0, 0x47), "up": (0xe0, 0x48), "pgup": (0xe0, 0x49),
    "left": (0xe0, 0x4b), "right": (0xe0, 0x4d),
    "end": (0xe0, 0x4f), "down": (0xe0, 0x50), "pgdn": (0xe0, 0x51),
    "insert": (0xe0, 0x52), "delete": (0xe0, 0x53),
}


def _make_break(make_bytes):
    """PS/2 set-1 break sequence for a make sequence."""
    if make_bytes[0] == 0xe0:
        return (0xe0, make_bytes[1] | 0x80)
    return (make_bytes[0] | 0x80,)


def scancodes_for(combo):
    """Expand one simultaneous key combo into make then break bytes.

    ``combo`` carries **the seam's key names, which are QEMU's qcode
    set** (D103) — so `_SCANCODES` is keyed by `ret`, `spc`, `pgup`
    and `pgdn`, and has no entry for `enter` or `space`. That is the
    contract rather than an accident: the seam is named for the
    reference backend, and this adapter translates from it.
    """
    makes = []
    for name in combo:
        codes = _SCANCODES.get(name)
        if codes is None:
            # Single-character letters/digits already use their name.
            raise StaticError(
                f"no VirtualBox scancode for key {name!r}",
                rule_id="key.no-mapping")
        makes.append(codes)
    sequence = []
    for codes in makes:
        sequence.extend(codes)
    for codes in reversed(makes):
        sequence.extend(_make_break(codes))
    return sequence


class VirtualBoxSession:
    """Identity-verified session with agentless-display carriers (F52)."""

    #: This session's `text_screen` interprets a framebuffer rather
    #: than reading resolved characters, which costs the better part
    #: of a second and sets how coarsely a caller may quantize its
    #: cadence (`screen_stability.GUI_CADENCE_STEP`).
    recognizes_text = True

    def __init__(self, vm_uuid, name, drives=None, cache=None):
        self.backend = "virtualbox"
        self._uuid = vm_uuid
        self._name = name
        self._drives = dict(drives or {})
        self._cache = cache

    def native(self):
        """No portable native hatch: VBoxManage is the whole surface."""
        raise PreflightError(
            "VirtualBox has no native escape hatch equivalent to QMP; "
            "drive the machine through the portable carriers",
            rule_id="machine.backend-no-native")

    def _carry(self, args, *, action, target=None):
        """Run one carrier command, reading a vanished guest as stopped.

        The guest can power itself off at any moment — ``fdapm
        poweroff`` is how a DOS script normally ends — and every
        carrier fails once it has. VirtualBox can say which of the two
        happened, so ask it rather than reading VBoxManage's message:
        a stopped VM is a condition of the world, not a failed command.
        """
        try:
            return run_vbox(args, action=action,
                            target=target or self._uuid)
        except RunFailure as failure:
            if not vm_stopped(self._uuid):
                raise
            raise _not_running(self._uuid) from failure

    def send_keys(self, combos, delay=0.06):
        """Inject key combinations via ``keyboardputscancode``."""
        for combo in combos:
            codes = scancodes_for(combo)
            hex_args = [f"{byte:02x}" for byte in codes]
            self._carry(
                ["controlvm", self._uuid, "keyboardputscancode",
                 *hex_args],
                action="sending keys")
            time.sleep(delay)

    def screenshot(self, path):
        """Capture the guest display to ``path`` as a PNG."""
        png = os.path.abspath(os.fspath(path))
        parent = os.path.dirname(png)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._carry(
            ["controlvm", self._uuid, "screenshotpng", png],
            action="screenshot")
        return png

    def framebuffer(self):
        """The guest display as a Pillow image (F65).

        The landmark matcher's carrier, and the first half of
        :meth:`text_screen` below: this adapter's screen is a
        screenshot either way, so a landmark condition costs exactly
        what a text one costs minus the glyph matching. The image is
        loaded off the temporary file and detached from it, so the
        file can be removed while the caller still holds the pixels.
        """
        with tempfile.NamedTemporaryFile(
                suffix=".png", delete=False) as handle:
            path = handle.name
        try:
            self.screenshot(path)
            with Image.open(path) as opened:
                return opened.convert("RGB")
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

    def text_screen(self, font_banks=()):
        """Screenshot + shared fixed-font recognizer (F51).

        Read through **this host's** VirtualBox fonts rather than the
        bundled bank, which is not what drew the screen — and through
        all of them, since a run paints in more than one.

        ``font_banks`` (F61) are the authored fonts a script's `font`
        statement named, tried **before** the host's own — labelled
        ``"host"`` in the failure report's "fonts tried" rather than
        individually, since a screenshot cannot say which of a host's
        several installed fonts actually painted a cell.
        """
        with tempfile.NamedTemporaryFile(
                suffix=".png", delete=False) as handle:
            path = handle.name
        try:
            self.screenshot(path)
            host_banks = tuple(
                text_recognize.Bank(one, source="host")
                for one in guest_glyph_banks(self._cache))
            return text_recognize.recognize(
                path, bank=tuple(font_banks) + host_banks)
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

    def change_medium(self, drive_key, path=None):
        """Swap or eject a removable medium on the running machine."""
        attach = self._drives.get(drive_key)
        if attach is None:
            raise PreflightError(
                f"drive {drive_key!r} has no recorded VirtualBox "
                "attachment on this VM",
                rule_id="machine.slot-not-declared")
        self._carry(
            _attach_args(self._name, attach["storagectl"],
                         attach["port"], attach["device"],
                         attach["type"], path),
            action="changing medium", target=drive_key)


class VirtualBoxAdapter(BackendAdapter):
    """VirtualBox: lifecycle, VDI, and agentless-display (F50+F52)."""

    name = "virtualbox"
    settings_keys = ()

    def discover(self, platform=None):
        # One host tool whatever the guest is, so the platform the
        # seam offers is not asked for here.
        try:
            executable = find_vboxmanage()
        except PreflightError as missing:
            return Availability("virtualbox", False, detail=str(missing))
        # Availability is the binary on disk — running it is start's
        # job. Unit tests forbid backend subprocesses, and a path
        # check is what the former stub did; a broken install fails
        # closed at create/start with VBoxManage's own message.
        return Availability(
            "virtualbox", True, executable=executable,
            home=os.path.dirname(executable),
            detail=f"found at {executable}")

    def capabilities(self):
        """What this adapter honors today — including agentless-display.

        ``vvfat`` stays false: directory-source drives are QEMU-only.
        """
        return Capabilities(
            backend="virtualbox",
            control_planes=("agentless-display",),
            media=("floppy", "hdd", "cdrom"),
            controllers=("ide",),
            materialize=("new", "difference", "copy", "use"),
            vvfat=False,
        )

    def capture_format(self, plane):
        """This plane's screen *is* a framebuffer, so it states one.

        VirtualBox has no text-memory readback: the display plane
        screenshots the guest and hands the pixels to the shared
        recognizer (F51/F52). The same pixels serve a landmark
        condition unchanged (F65), and ``screenshotpng`` writes
        ordinary 8-bit-per-channel colour, which is ``rgb`` and makes
        the reference-side normalization the identity.
        """
        return "rgb" if plane == "agentless-display" else None

    def image_path(self, root, stem):
        return os.path.join(root, f"{stem}.vdi")

    def create_image(self, path, *, mode, size=None, base=None):
        if mode == "new":
            return create_vdi(path, size)
        if mode == "difference":
            return create_difference_vdi(path, base)
        if mode == "copy":
            return create_duplicate_vdi(path, base)
        raise StaticError(
            f"the virtualbox adapter cannot materialize an image for "
            f"mode {mode!r}", rule_id="image.mode-unsupported")

    def dispose(self, machine_dir):
        """Unregister the VirtualBox machine object, if one exists.

        ``destroy`` deletes the materialization directory afterwards.
        ``--delete`` clears VirtualBox's own registry entries for the
        disks we attached; the directory teardown is still required
        for everything else under the machine home.
        """
        backend_dir = os.path.join(machine_dir, "virtualbox")
        if not os.path.isdir(backend_dir):
            return
        # The VM name is the directory VirtualBox created under
        # basefolder; any single child directory is that machine.
        for entry in os.listdir(backend_dir):
            candidate = os.path.join(backend_dir, entry)
            if not os.path.isdir(candidate):
                continue
            vbox = os.path.join(candidate, f"{entry}.vbox")
            if not os.path.isfile(vbox):
                continue
            try:
                run_vbox(
                    ["unregistervm", entry, "--delete"],
                    action="unregistering", target=entry)
            except RunFailure as error:
                print(f"rlq: warning: {error}", file=sys.stderr)

    def start(self, state, *, machine_dir, backend_dir, display=False,
              current=None):
        return launch_owned_vm(
            state, backend_dir=backend_dir, display=display,
            current=current)

    def stop(self, vm):
        return stop(vm)

    @contextlib.contextmanager
    def session(self, vm, cache=None):
        expected = vm["backend-id"]
        token = vm["token"]
        try:
            info = verify_vm(expected, token)
        except PreflightError:
            raise
        except RunFailure as error:
            raise PreflightError(
                "the recorded reliquary VM is no longer reachable\n"
                f"  expected: {expected}",
                rule_id="machine.vm-unreachable") from error
        state = info.get("VMState")
        if state in _STOPPED_STATES:
            # `showvminfo` answers for a powered-off VM as readily as
            # for a running one, so identity alone proves nothing about
            # whether there is a guest to drive. There is no session to
            # be had here, and saying so is what lets a script wait for
            # the machine to stop.
            raise _not_running(expected, state)
        endpoint = vm.get("endpoint") or {}
        yield VirtualBoxSession(
            expected, endpoint.get("name") or info.get("name", expected),
            drives=endpoint.get("drives"), cache=cache)
