# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Machine materialization and cached-state management."""

import json
import os
import re
import shutil
import uuid
from datetime import datetime, timezone

from .blueprint import load_blueprint
from .drives import format_options
from .home import blueprints_dir, machines_cache_dir
from .library import seed_blueprint
from .lifecycle import (create_hdd_image, find_qemu, launch_owned_qemu,
                        stop as stop_owned_qemu)
from .media import fetch_media


_MIN_PREFIX = 4
_HEX_ID = re.compile(r"[0-9a-f]+")
_BOOT_LETTER = {"floppy": "a", "hdd": "c", "cdrom": "d"}
_PLATFORM_MEMORY = {
    "dos": 16,
    "win9x": 64,
    "winnt": 256,
}


def machine_dir_path(machine_id, home=None):
    """Return the machine's cache directory path."""
    return os.path.join(machines_cache_dir(home), machine_id)


def _machine_drives_dir(machine_id, home=None):
    return os.path.join(machine_dir_path(machine_id, home), "drives")


def _state_path(machine_id, home=None):
    return os.path.join(machine_dir_path(machine_id, home),
                        "reliquary-machine.json")


def create(blueprint, *, home=None, blueprint_name=""):
    """Materialize one machine from a parsed Blueprint.

    Creates the machine cache directory under ``cache/machines/<id>/``,
    writes ``reliquary-machine.json``, creates qcow2 images for
    every drive declared with ``size``, and fetches every media
    item to the shared cache (the machine's drives record the
    payload path).  Returns the generated machine id.
    """
    machine_id = uuid.uuid4().hex
    drives_root = _machine_drives_dir(machine_id, home)
    os.makedirs(drives_root)

    resolved_drives = {}
    for key, drive in sorted(blueprint.drives.items()):
        if drive.size is not None:
            filename = f"{key}.qcow2"
            path = os.path.join(drives_root, filename)
            create_hdd_image(path, drive.size)
            resolved_drives[key] = {
                "medium": drive.medium,
                "slot": drive.slot,
                "size": drive.size,
                "path": path,
            }
        elif drive.media is not None:
            payload = fetch_media(drive.media.item.name, home=home)
            resolved_drives[key] = {
                "medium": drive.medium,
                "slot": drive.slot,
                "media": drive.media.item.name,
                "path": payload,
            }
        else:
            # An empty removable drive: guest-visible hardware with
            # no medium until a script inserts one.
            resolved_drives[key] = {
                "medium": drive.medium,
                "slot": drive.slot,
                "media": None,
                "path": None,
            }

    state = {
        "id": machine_id,
        "blueprint": blueprint_name,
        "created": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "phase": "ready",
        "backend": "qemu",
        "platform": blueprint.platform,
        "memory": blueprint.memory,
        "drives": resolved_drives,
        "boot": list(blueprint.boot),
        "name": blueprint.name,
        "description": blueprint.description,
        "scripts": dict(blueprint.scripts),
    }

    _write_state(machine_id, state, home)
    return machine_id


def create_from_blueprint(name, *, home=None):
    """Load ``blueprints/<name>.json`` and materialize one machine.

    A blueprint the home does not contain is seeded from the
    built-in library on this first reference, along with the media
    definitions and scripts it references (never overwriting user
    files).
    """
    path = os.path.join(blueprints_dir(home), f"{name}.json")
    if not os.path.exists(path):
        seed_blueprint(name, home=home)
    blueprint = load_blueprint(path, home=home)
    return create(blueprint, home=home, blueprint_name=name)


def _write_state(machine_id, state, home=None):
    path = _state_path(machine_id, home)
    part = path + ".part"
    with open(part, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(state, handle, indent=2)
        handle.write("\n")
    os.replace(part, path)


def load_machine_state(machine_id, home=None):
    """Read and return the machine's ``reliquary-machine.json``."""
    path = _state_path(machine_id, home)
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"machine state not found: {path}")
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def list_machines(home=None, blueprint=None):
    """Return state dicts for machines under the cache, oldest first.

    When ``blueprint`` is set, only machines of that blueprint are
    returned.
    """
    root = machines_cache_dir(home)
    if not os.path.isdir(root):
        return []
    machines = []
    for entry in sorted(os.listdir(root)):
        path = os.path.join(root, entry, "reliquary-machine.json")
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as handle:
            state = json.load(handle)
        if state.get("id") != entry:
            raise RuntimeError(
                f"machine id mismatch: directory {entry!r} "
                f"contains id {state.get('id')!r}")
        if blueprint is not None and state.get("blueprint") != blueprint:
            continue
        machines.append(state)
    return machines


def short_id(machine_id, home=None):
    """Return the shortest unambiguous prefix (at least four hex chars)."""
    ids = [state["id"] for state in list_machines(home)]
    if machine_id not in ids:
        ids.append(machine_id)
    for length in range(_MIN_PREFIX, len(machine_id) + 1):
        prefix = machine_id[:length]
        matches = [item for item in ids if item.startswith(prefix)]
        if len(matches) == 1:
            return prefix
    return machine_id


def resolve_machine(*, machine=None, blueprint=None, home=None):
    """Resolve a ``--machine`` / ``--blueprint`` selector to one id.

    Exactly one of ``machine`` or ``blueprint`` must be provided.
    """
    if machine is not None and blueprint is not None:
        raise ValueError(
            "--blueprint and --machine are mutually exclusive")
    if machine is None and blueprint is None:
        raise ValueError(
            "select a machine with --blueprint or --machine")
    if machine is not None:
        return _resolve_by_prefix(machine, home)
    return _resolve_by_blueprint(blueprint, home)


def _resolve_by_prefix(prefix, home):
    prefix = prefix.lower()
    if len(prefix) < _MIN_PREFIX:
        raise ValueError(
            f"machine id prefix must be at least {_MIN_PREFIX} "
            f"hex characters, got: {prefix!r}")
    if not _HEX_ID.fullmatch(prefix):
        raise ValueError(
            f"machine id prefix must be hexadecimal, got: {prefix!r}")
    matches = [state for state in list_machines(home)
               if state["id"].startswith(prefix)]
    if not matches:
        raise ValueError(f"no machine matches id prefix {prefix!r}")
    if len(matches) > 1:
        lines = [f"{prefix!r} matches {len(matches)} machines:"]
        for state in matches:
            sid = short_id(state["id"], home)
            lines.append(
                f"  {sid}  {state.get('blueprint') or '-'} "
                f"({state.get('phase', '?')})")
        raise ValueError("\n".join(lines))
    return matches[0]["id"]


def _resolve_by_blueprint(name, home):
    matches = list_machines(home, blueprint=name)
    if not matches:
        raise ValueError(
            f"no machine exists for blueprint {name!r}\n"
            f"create one: rlq --blueprint {name} create")
    if len(matches) > 1:
        lines = [
            f"blueprint {name!r} has {len(matches)} machines; "
            "pick one with --machine:",
        ]
        for state in matches:
            sid = short_id(state["id"], home)
            lines.append(f"  {sid}  ({state.get('phase', '?')})")
        raise ValueError("\n".join(lines))
    return matches[0]["id"]


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


def _set_phase(machine_id, phase, home=None):
    state = load_machine_state(machine_id, home)
    state["phase"] = phase
    _write_state(machine_id, state, home)
    return state


def start(machine_id, *, display=False, home=None):
    """Start a ready machine and return its QMP port.

    Re-verifies every media hash, launches QEMU under the machine's
    cache directory, and records phase ``running``.
    """
    state = load_machine_state(machine_id, home)
    phase = state.get("phase")
    if phase == "running":
        raise RuntimeError(
            f"machine {short_id(machine_id, home)} is already running")
    if phase != "ready":
        raise RuntimeError(
            f"machine {short_id(machine_id, home)} cannot start "
            f"(phase: {phase})")

    drives = state.get("drives", {})
    for drive in drives.values():
        media_name = drive.get("media")
        if media_name is not None:
            drive["path"] = fetch_media(media_name, home=home)
    state["drives"] = drives
    _write_state(machine_id, state, home)

    memory = state.get("memory")
    if memory is None:
        memory = _PLATFORM_MEMORY.get(state.get("platform"), 16)
    qemu = find_qemu()
    print(f"using QEMU: {qemu}")
    vm_name = f"reliquary-{machine_id[:12]}"
    args = [qemu, "-name", vm_name, "-m", str(memory)]
    args += machine_drive_args(machine_id, home)
    boot = _boot_order(state.get("boot", []), drives)
    if boot is not None:
        args += ["-boot", f"order={boot}"]

    machine_home = machine_dir_path(machine_id, home)
    port = launch_owned_qemu(
        args, vm_name=vm_name, display=display, home=machine_home)
    _set_phase(machine_id, "running", home)
    return port


def stop(machine_id, home=None):
    """Stop a running machine and return it to phase ``ready``."""
    state = load_machine_state(machine_id, home)
    phase = state.get("phase")
    if phase != "running":
        raise RuntimeError(
            f"machine {short_id(machine_id, home)} is not running "
            f"(phase: {phase})")
    machine_home = machine_dir_path(machine_id, home)
    try:
        stop_owned_qemu(home=machine_home)
    except RuntimeError:
        _set_phase(machine_id, "ready", home)
        raise
    _set_phase(machine_id, "ready", home)


_REMOVABLE_MEDIA = {"floppy", "cdrom"}


def _removable_drive(state, slot, home):
    """Return the mutable state entry for a removable drive slot."""
    phase = state.get("phase")
    if phase != "ready":
        raise RuntimeError(
            f"machine {short_id(state['id'], home)} must be stopped "
            f"to change media (phase: {phase})")
    drive = state.get("drives", {}).get(slot)
    if drive is None:
        raise ValueError(
            f"machine {short_id(state['id'], home)} declares no "
            f"drive {slot}")
    if drive.get("medium") not in _REMOVABLE_MEDIA:
        raise ValueError(
            f"{slot} is not a removable drive slot")
    return drive


def insert_media(machine_id, slot, media_name, *, home=None):
    """Insert a defined media item into a floppy or cdrom slot.

    Hard-disk slots are rejected.  The slot must already exist in
    the machine's state — drives are guest-visible hardware the
    blueprint declares, so ``insert`` never creates one.  The
    change persists in ``reliquary-machine.json`` across
    stop/start: the machine diverges from its blueprint until a
    later ``insert``/``eject`` changes the slot again.  The
    machine must be stopped; changing the medium of a running
    machine is not supported yet.
    """
    state = load_machine_state(machine_id, home)
    drive = _removable_drive(state, slot, home)
    drive["path"] = fetch_media(media_name, home=home)
    drive["media"] = media_name
    _write_state(machine_id, state, home)


def eject_media(machine_id, slot, *, home=None):
    """Empty a declared removable slot, persisting the change.

    The drive itself remains — the blueprint alone defines machine
    topology — but the next ``start`` presents it without a medium.
    The machine must be stopped, as for :func:`insert_media`.
    """
    state = load_machine_state(machine_id, home)
    drive = _removable_drive(state, slot, home)
    drive["media"] = None
    drive["path"] = None
    _write_state(machine_id, state, home)


def set_boot_order(machine_id, boot_keys, *, home=None):
    """Persist a new boot order on a stopped machine.

    Every key must name a drive the machine already declares.
    Duplicates are rejected.  The change lives in
    ``reliquary-machine.json`` and takes effect on the next
    ``start``; the machine diverges from its blueprint until
    ``apply`` (or another ``set_boot_order``) restores it.
    """
    state = load_machine_state(machine_id, home)
    phase = state.get("phase")
    if phase != "ready":
        raise RuntimeError(
            f"machine {short_id(machine_id, home)} must be stopped "
            f"to change boot order (phase: {phase})")
    drives = state.get("drives", {})
    if not isinstance(boot_keys, (list, tuple)) or not boot_keys:
        raise ValueError("boot order requires at least one drive key")
    normalized = []
    seen = set()
    for index, key in enumerate(boot_keys):
        if not isinstance(key, str) or not key:
            raise ValueError(
                f"boot[{index}] must be a non-empty drive key")
        if key not in drives:
            raise ValueError(
                f"boot[{index}] references undeclared drive {key}")
        if key in seen:
            raise ValueError(f"boot contains duplicate drive {key}")
        seen.add(key)
        normalized.append(key)
    state["boot"] = normalized
    _write_state(machine_id, state, home)


def mark_stopped(machine_id, home=None):
    """Reconcile the phase of a machine whose QEMU process has gone.

    Used when the guest powers itself off (the script observed
    ``stopped``): the phase returns to ``ready`` and the stale
    ``vm.json`` is removed.  A machine not in phase ``running`` is
    left untouched.
    """
    state = load_machine_state(machine_id, home)
    if state.get("phase") != "running":
        return
    vm_path = os.path.join(machine_dir_path(machine_id, home), "vm.json")
    try:
        os.remove(vm_path)
    except FileNotFoundError:
        pass
    _set_phase(machine_id, "ready", home)


def destroy(machine_id, home=None):
    """Delete a stopped machine's cache directory entirely."""
    state = load_machine_state(machine_id, home)
    phase = state.get("phase")
    if phase == "running":
        raise RuntimeError(
            f"machine {short_id(machine_id, home)} is running; "
            "stop it before destroy")
    if phase != "ready":
        raise RuntimeError(
            f"machine {short_id(machine_id, home)} cannot be destroyed "
            f"(phase: {phase})")
    _set_phase(machine_id, "destroying", home)
    shutil.rmtree(machine_dir_path(machine_id, home))


def machine_drive_args(machine_id, home=None):
    """Build QEMU ``-drive`` arguments from a machine's state.

    Returns a list of tokens suitable for a QEMU command line
    (``-drive`` alternating with its value), with floppies first,
    hard disks next, and cdroms placed on the IDE bus after the
    last hard disk.
    """
    state = load_machine_state(machine_id, home)
    drives = state.get("drives", {})
    args = []

    floppies = [(k, v) for k, v in drives.items()
                 if v["medium"] == "floppy"]
    for _key, drive in sorted(floppies, key=lambda kv: kv[1]["slot"]):
        path = drive["path"]
        if path is None:
            args += ["-drive", f"if=floppy,index={drive['slot']}"]
            continue
        is_dir = os.path.isdir(path)
        source = (f"fat:floppy:rw:{path},format=raw,"
                  if is_dir else path + ",")
        args += ["-drive",
                 f"file={source}if=floppy,index={drive['slot']}"]

    hdds = [(k, v) for k, v in drives.items()
            if v["medium"] == "hdd"]
    for _key, drive in sorted(hdds, key=lambda kv: kv[1]["slot"]):
        path = drive["path"]
        is_dir = os.path.isdir(path)
        source = (f"fat:rw:{path},format=raw,"
                  if is_dir else path + ",")
        inferred = "" if is_dir else format_options(path)
        args += ["-drive",
                 f"file={source}{inferred}if=ide,index={drive['slot']}"]

    cdroms = [(k, v) for k, v in drives.items()
              if v["medium"] == "cdrom"]
    if cdroms:
        next_ide = max(
            (d["slot"] for k, d in drives.items() if d["medium"] == "hdd"),
            default=-1,
        ) + 1
        for ordinal, (_key, drive) in enumerate(
                sorted(cdroms, key=lambda kv: kv[1]["slot"])):
            path = drive["path"]
            index = next_ide + ordinal
            if path is None:
                args += ["-drive",
                         f"media=cdrom,if=ide,index={index}"]
                continue
            inferred = format_options(path)
            args += ["-drive",
                     f"file={path},{inferred}media=cdrom,if=ide,index={index}"]

    return args
