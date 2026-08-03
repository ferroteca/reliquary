# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The VirtualBox backend adapter: everything that knows VirtualBox.

F50: lifecycle and VDI materialization. Discovery, image creation,
``createvm`` under the machine's ``virtualbox/`` directory, start /
stop with identity verification, and dispose. Agentless-display
carriers land with F52 — this adapter claims none of that plane
(P11), and a session refuses them by name until then.
"""

import contextlib
import os
import re
import shutil
import subprocess
import sys
import uuid

from . import backends
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


def configure_vm(state, vm_name):
    """Apply Reliquary drive vocabulary to a registered VirtualBox VM."""
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
                ["storagectl", vm_name, f"--name={value}", "--remove"],
                action="removing controller", target=value)

    floppies = []
    disks = []
    for key, drive in sorted(drives.items()):
        medium = drive.get("medium")
        if medium == "floppy":
            floppies.append((key, drive))
        elif medium in ("hdd", "cdrom"):
            disks.append((key, drive))

    if floppies:
        run_vbox(
            ["storagectl", vm_name, f"--name={_FLOPPY}",
             "--add=floppy", "--controller=I82078"],
            action="adding floppy controller", target=vm_name)
        for index, (_key, drive) in enumerate(floppies[:2]):
            run_vbox(
                _attach_args(vm_name, _FLOPPY, index, 0, "fdd",
                             drive.get("path")),
                action="attaching floppy", target=_key)

    run_vbox(
        ["storagectl", vm_name, f"--name={_IDE}",
         "--add=ide", "--controller=PIIX4"],
        action="adding IDE controller", target=vm_name)
    for index, (_key, drive) in enumerate(disks[:4]):
        port, device = _ide_slot(index)
        medium_type = "dvddrive" if drive.get("medium") == "cdrom" else "hdd"
        run_vbox(
            _attach_args(vm_name, _IDE, port, device, medium_type,
                         drive.get("path")),
            action="attaching drive", target=_key)


def ensure_vm(state, *, backend_dir):
    """Register the VirtualBox machine if absent; return its UUID.

    Images already live under ``media/`` from create. This creates
    the ``.vbox`` under ``backend_dir`` on first start and reuses it
    afterwards.
    """
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
    configure_vm(state, name)
    return vm_uuid


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

    vm_uuid = ensure_vm(state, backend_dir=backend_dir)
    name = _vm_name(state)
    start_type = "gui" if display else "headless"
    print(f"rlq: VirtualBox starting: {name} ({vm_uuid})", file=sys.stderr)
    run_vbox(
        ["startvm", vm_uuid, f"--type={start_type}"],
        action="starting", target=name)
    verify_vm(vm_uuid, vm_uuid)
    return backends.identity(
        "virtualbox", vm_uuid, vm_uuid, {"name": name})


def stop(vm):
    """Power off the identified owned VM (no persistence)."""
    if not vm:
        raise PreflightError("no recorded reliquary VM to stop",
            rule_id="machine.no-active-vm")
    expected = vm["backend-id"]
    token = vm["token"]
    verify_vm(expected, token)
    run_vbox(
        ["controlvm", expected, "poweroff"],
        action="stopping", target=expected)


class VirtualBoxSession:
    """Identity-verified session; carriers land with F52."""

    def __init__(self, vm_uuid, name):
        self.backend = "virtualbox"
        self._uuid = vm_uuid
        self._name = name

    def native(self):
        """No portable native hatch: VBoxManage is the whole surface."""
        raise PreflightError(
            "VirtualBox has no native escape hatch equivalent to QMP; "
            "drive the machine through the portable carriers",
            rule_id="machine.backend-no-native")

    def send_keys(self, combos, delay=0.06):
        raise PreflightError(
            "the virtualbox agentless-display carriers are unbuilt "
            "(F52); keyboard input is not available yet",
            rule_id="machine.control-plane-unbuilt")

    def text_screen(self):
        raise PreflightError(
            "the virtualbox agentless-display carriers are unbuilt "
            "(F52); text-screen readback is not available yet",
            rule_id="machine.control-plane-unbuilt")

    def screenshot(self, path):
        raise PreflightError(
            "the virtualbox agentless-display carriers are unbuilt "
            "(F52); screenshots are not available yet",
            rule_id="machine.control-plane-unbuilt")

    def change_medium(self, drive_key, path=None):
        raise PreflightError(
            "the virtualbox agentless-display carriers are unbuilt "
            "(F52); live medium change is not available yet",
            rule_id="machine.control-plane-unbuilt")


class VirtualBoxAdapter(BackendAdapter):
    """VirtualBox: lifecycle and VDI; display plane still claimed empty."""

    name = "virtualbox"
    settings_keys = ()

    def discover(self):
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
            detail=f"found at {executable}")

    def capabilities(self):
        """What this adapter honors today — no agentless-display yet.

        Media, controllers and materialization modes are real under
        F50. Claiming ``agentless-display`` before the carriers exist
        would promise what nothing can honor (P11); that claim is
        F52's. ``vvfat`` and at-rest stay false: VDI is outside
        Remanence's claim, and directory-source drives are QEMU-only.
        """
        return Capabilities(
            backend="virtualbox",
            control_planes=(),
            media=("floppy", "hdd", "cdrom"),
            controllers=("ide",),
            materialize=("new", "difference", "copy", "use"),
            vvfat=False,
            at_rest=False,
            at_rest_write=False,
        )

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
    def session(self, vm):
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
        yield VirtualBoxSession(expected, info.get("name", expected))
