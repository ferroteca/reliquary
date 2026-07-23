# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Machine materialization and cached-state management."""

import contextlib
import json
import os
import shutil
from datetime import datetime, timezone

from .blueprint import load_blueprint
from .drives import format_options
from .home import blueprints_dir, machines_cache_dir
from .library import seed_blueprint
from .lifecycle import (create_hdd_image, find_qemu, launch_owned_qemu,
                        read_vm_state, stop as stop_owned_qemu)
from .media import fetch_media


_BOOT_LETTER = {"floppy": "a", "hdd": "c", "cdrom": "d"}
_PLATFORM_MEMORY = {
    "dos": 16,
    "openbsd": 512,
    "win9x": 64,
    "winnt": 256,
}


def machine_dir_path(machine_id, context=None):
    """Return the machine's cache directory path."""
    return os.path.join(machines_cache_dir(context), machine_id)


def _machine_drives_dir(machine_id, context=None):
    return os.path.join(machine_dir_path(machine_id, context), "drives")


def _state_path(machine_id, context=None):
    return os.path.join(machine_dir_path(machine_id, context),
                        "reliquary-machine.json")


def machine_id_for(blueprint_name, number):
    """Return the canonical machine id for a blueprint and number."""
    return f"{blueprint_name}-{number}"


def split_machine_id(machine_id):
    """Return ``(blueprint_name, number)`` for a well-formed id.

    The number is the trailing decimal after the final ``-``.  Returns
    ``None`` when the id is not ``<blueprint>-<n>``.
    """
    if not isinstance(machine_id, str) or "-" not in machine_id:
        return None
    blueprint, sep, number = machine_id.rpartition("-")
    if not sep or not blueprint or not number.isdigit():
        return None
    if len(number) > 1 and number.startswith("0"):
        return None
    return blueprint, int(number)


def _locks_dir(context=None):
    return os.path.join(machines_cache_dir(context), ".locks")


def _lock_file(handle):
    if os.name == "nt":
        import msvcrt
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        while True:
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                return
            except OSError:
                # LK_LOCK retries ~10s then raises; keep waiting.
                continue
    import fcntl
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)


def _unlock_file(handle):
    if os.name == "nt":
        import msvcrt
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return
    import fcntl
    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextlib.contextmanager
def _blueprint_alloc_lock(blueprint_name, context=None):
    """Serialize machine-number allocation for one blueprint."""
    lock_root = _locks_dir(context)
    os.makedirs(lock_root, exist_ok=True)
    lock_path = os.path.join(lock_root, f"{blueprint_name}.lock")
    with open(lock_path, "a+b") as handle:
        _lock_file(handle)
        try:
            yield
        finally:
            _unlock_file(handle)


def _allocate_machine_id(blueprint_name, context=None):
    """Return the lowest free ``<blueprint>-<n>`` id (directories count)."""
    number = 0
    while True:
        machine_id = machine_id_for(blueprint_name, number)
        if not os.path.exists(machine_dir_path(machine_id, context)):
            return machine_id
        number += 1


def create(blueprint, *, context=None, blueprint_name=""):
    """Materialize one machine from a parsed Blueprint.

    Creates the machine cache directory under
    ``cache/machines/<blueprint>-<n>/``, writes
    ``reliquary-machine.json``, creates qcow2 images for every drive
    declared with ``size``, and fetches every media item to the shared
    cache (the machine's drives record the payload path).  The machine
    number is the lowest free non-negative integer for that blueprint.
    Returns the generated machine id.
    """
    if not isinstance(blueprint_name, str) or not blueprint_name:
        raise ValueError("create requires a non-empty blueprint_name")

    with _blueprint_alloc_lock(blueprint_name, context):
        machine_id = _allocate_machine_id(blueprint_name, context)
        drives_root = _machine_drives_dir(machine_id, context)
        os.makedirs(drives_root)

    resolved_drives = {}
    for key, drive in sorted(blueprint.drives.items()):
        if not drive.enabled:
            # `enabled: false` removes the drive from the machine
            # entirely (machine-blueprint-reference.md).
            continue
        if drive.base is not None or drive.hostdir is not None:
            raise NotImplementedError(
                f"drive {key!r} uses base/hostdir; materialization of "
                "base and hostdir drives lands later in milestone 6")
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
            payload = fetch_media(drive.media.item.name, context=context)
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

    _write_state(machine_id, state, context)
    return machine_id


def create_machine(name, *, context=None):
    """Load ``blueprints/<name>.rlqb`` and materialize one machine.

    A blueprint the home does not contain is seeded from the
    built-in library on this first reference, along with the media
    definitions and scripts it references (never overwriting user
    files).
    """
    from .library import locate_blueprint
    paths = [
        os.path.join(blueprints_dir(context), f"{name}.rlqb"),
        os.path.join(blueprints_dir(context), f"{name}.json"),
    ]
    if not any(os.path.exists(path) for path in paths):
        seed_blueprint(name, context=context)
    path = locate_blueprint(name, context=context)
    blueprint = load_blueprint(path, context=context)
    return create(blueprint, context=context, blueprint_name=name)


def _write_state(machine_id, state, context=None):
    path = _state_path(machine_id, context)
    part = path + ".part"
    with open(part, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(state, handle, indent=2)
        handle.write("\n")
    os.replace(part, path)


def load_machine_state(machine_id, context=None):
    """Read and return the machine's ``reliquary-machine.json``."""
    path = _state_path(machine_id, context)
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"machine state not found: {path}")
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _machine_sort_key(state):
    """Sort by blueprint name, then machine number, then id."""
    machine_id = state.get("id") or ""
    parsed = split_machine_id(machine_id)
    if parsed is not None:
        return (parsed[0], parsed[1], machine_id)
    return (state.get("blueprint") or "", -1, machine_id)


def list_machines(context=None, blueprint=None):
    """Return state dicts for machines under the cache.

    Ordered by blueprint name, then ascending machine number.  When
    ``blueprint`` is set, only machines of that blueprint are returned.
    """
    root = machines_cache_dir(context)
    if not os.path.isdir(root):
        return []
    machines = []
    for entry in os.listdir(root):
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
    machines.sort(key=_machine_sort_key)
    return machines


def resolve_machine(*, machine=None, blueprint=None, context=None):
    """Resolve a ``--machine`` / ``--blueprint`` selector to one id.

    Selectors are mutually exclusive:

    - ``--blueprint NAME``: the sole machine of that blueprint
    - ``--machine NAME-N``: the full machine id, exactly
    """
    if machine is None and blueprint is None:
        raise ValueError(
            "select a machine with --blueprint or --machine")
    if machine is not None and blueprint is not None:
        raise ValueError(
            "--blueprint and --machine are mutually exclusive; "
            "pass --machine <id> or --blueprint <name>")
    if machine is not None:
        return _resolve_by_id(machine, context)
    return _resolve_by_blueprint(blueprint, context)


def _resolve_by_id(selector, context):
    """Resolve a full machine id — exact match only."""
    if not isinstance(selector, str) or not selector:
        raise ValueError(
            f"machine id must be a non-empty string, got: {selector!r}")
    if selector.isdigit():
        raise ValueError(
            f"machine id must be the full <blueprint>-<n> form, "
            f"got: {selector!r}")
    for state in list_machines(context):
        if state["id"] == selector:
            return selector
    raise ValueError(f"no machine {selector!r}")


def _resolve_by_blueprint(name, context):
    matches = list_machines(context, blueprint=name)
    if not matches:
        raise ValueError(
            f"no machine exists for blueprint {name!r}\n"
            f"create one: rlq create-machine --blueprint {name}")
    if len(matches) > 1:
        lines = [
            f"blueprint {name!r} has {len(matches)} machines; "
            "pick one with --machine <id>:",
        ]
        for state in matches:
            lines.append(f"  {state['id']}  ({state.get('phase', '?')})")
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


def _set_phase(machine_id, phase, context=None):
    state = load_machine_state(machine_id, context)
    state["phase"] = phase
    _write_state(machine_id, state, context)
    return state


def start_machine(machine_id, *, display=False, context=None):
    """Start a ready machine and return its QMP port.

    Re-verifies every media hash, launches QEMU under the machine's
    cache directory, and records phase ``running``.
    """
    state = load_machine_state(machine_id, context)
    phase = state.get("phase")
    if phase == "running":
        raise RuntimeError(
            f"machine {machine_id} is already running")
    if phase != "ready":
        raise RuntimeError(
            f"machine {machine_id} cannot start "
            f"(phase: {phase})")

    drives = state.get("drives", {})
    for drive in drives.values():
        media_name = drive.get("media")
        if media_name is not None:
            drive["path"] = fetch_media(media_name, context=context)
    state["drives"] = drives
    _write_state(machine_id, state, context)

    memory = state.get("memory")
    if memory is None:
        memory = _PLATFORM_MEMORY.get(state.get("platform"), 16)
    qemu = find_qemu()
    print(f"using QEMU: {qemu}")
    vm_name = f"reliquary-{machine_id}"
    args = [qemu, "-name", vm_name, "-m", str(memory)]
    args += machine_drive_args(machine_id, context)
    boot = _boot_order(state.get("boot", []), drives)
    if boot is not None:
        args += ["-boot", f"order={boot}"]

    # launch_owned_qemu's home= is a plain directory, not a Context —
    # here it's repurposed as the machine's own cache subdirectory.
    machine_home = machine_dir_path(machine_id, context)
    port = launch_owned_qemu(
        args, vm_name=vm_name, display=display, home=machine_home)
    _set_phase(machine_id, "running", context)
    return port


def stop_machine(machine_id, context=None):
    """Stop a running machine and return it to phase ``ready``."""
    state = load_machine_state(machine_id, context)
    phase = state.get("phase")
    if phase != "running":
        raise RuntimeError(
            f"machine {machine_id} is not running "
            f"(phase: {phase})")
    machine_home = machine_dir_path(machine_id, context)
    try:
        stop_owned_qemu(home=machine_home)
    except RuntimeError:
        # A stop that found the recorded VM gone removed the stale
        # vm.json; only then is `ready` true. A stop that failed
        # closed (identity mismatch) left vm.json in place — our QEMU
        # may still be running, so the phase must not change.
        if read_vm_state(machine_home) is None:
            _set_phase(machine_id, "ready", context)
        raise
    _set_phase(machine_id, "ready", context)


_REMOVABLE_MEDIA = {"floppy", "cdrom"}


def _removable_drive(state, slot, context):
    """Return the mutable state entry for a removable drive slot."""
    phase = state.get("phase")
    if phase != "ready":
        raise RuntimeError(
            f"machine {state['id']} must be stopped "
            f"to change media (phase: {phase})")
    drive = state.get("drives", {}).get(slot)
    if drive is None:
        raise ValueError(
            f"machine {state['id']} declares no "
            f"drive {slot}")
    if drive.get("medium") not in _REMOVABLE_MEDIA:
        raise ValueError(
            f"{slot} is not a removable drive slot")
    return drive


def insert_media(machine_id, slot, media_name, *, context=None):
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
    state = load_machine_state(machine_id, context)
    drive = _removable_drive(state, slot, context)
    drive["path"] = fetch_media(media_name, context=context)
    drive["media"] = media_name
    _write_state(machine_id, state, context)


def eject_media(machine_id, slot, *, context=None):
    """Empty a declared removable slot, persisting the change.

    The drive itself remains — the blueprint alone defines machine
    topology — but the next ``start`` presents it without a medium.
    The machine must be stopped, as for :func:`insert_media`.
    """
    state = load_machine_state(machine_id, context)
    drive = _removable_drive(state, slot, context)
    drive["media"] = None
    drive["path"] = None
    _write_state(machine_id, state, context)


def set_boot_order(machine_id, boot_keys, *, context=None):
    """Persist a new boot order on a stopped machine.

    Every key must name a drive the machine already declares.
    Duplicates are rejected.  The change lives in
    ``reliquary-machine.json`` and takes effect on the next
    ``start``; the machine diverges from its blueprint until
    ``apply`` (or another ``set_boot_order``) restores it.
    """
    state = load_machine_state(machine_id, context)
    phase = state.get("phase")
    if phase != "ready":
        raise RuntimeError(
            f"machine {machine_id} must be stopped "
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
    _write_state(machine_id, state, context)


def mark_stopped(machine_id, context=None):
    """Reconcile the phase of a machine whose QEMU process has gone.

    Used when the guest powers itself off (the script observed
    ``stopped``): the phase returns to ``ready`` and the stale
    ``vm.json`` is removed.  A machine not in phase ``running`` is
    left untouched.
    """
    state = load_machine_state(machine_id, context)
    if state.get("phase") != "running":
        return
    vm_path = os.path.join(machine_dir_path(machine_id, context), "vm.json")
    try:
        os.remove(vm_path)
    except FileNotFoundError:
        pass
    _set_phase(machine_id, "ready", context)


def destroy_machine(machine_id, context=None):
    """Delete a stopped machine's cache directory entirely.

    A deletion interrupted by a host lock can be retried.  New failed
    deletions restore the machine to ``ready`` so they do not strand it
    in the transient ``destroying`` phase.
    """
    state = load_machine_state(machine_id, context)
    phase = state.get("phase")
    if phase == "running":
        raise RuntimeError(
            f"machine {machine_id} is running; "
            "stop it before destroying")
    if phase not in ("ready", "destroying"):
        raise RuntimeError(
            f"machine {machine_id} cannot be destroyed "
            f"(phase: {phase})")
    if phase == "ready":
        _set_phase(machine_id, "destroying", context)
    try:
        shutil.rmtree(machine_dir_path(machine_id, context))
    except OSError:
        _set_phase(machine_id, "ready", context)
        raise


def machine_drive_args(machine_id, context=None):
    """Build QEMU ``-drive`` arguments from a machine's state.

    Returns a list of tokens suitable for a QEMU command line
    (``-drive`` alternating with its value), with floppies first,
    hard disks next, and cdroms placed on the IDE bus after the
    last hard disk.
    """
    state = load_machine_state(machine_id, context)
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
