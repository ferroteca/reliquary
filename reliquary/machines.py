# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Machine materialization and cached-state management."""

import contextlib
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone

from .blueprint import load_blueprint
from .drives import format_options
from .home import blueprints_dir, machines_cache_dir
from .library import seed_blueprint
from .lifecycle import (create_difference_image, create_duplicate_image,
                        create_hdd_image, find_qemu, launch_owned_qemu,
                        read_vm_state, stop as stop_owned_qemu)
from .media import fetch_media


_BOOT_LETTER = {"floppy": "a", "hdd": "c", "cdrom": "d"}
_PLATFORM_MEMORY = {
    "dos": 16,
    "openbsd": 512,
    "win9x": 64,
    "winnt": 256,
}


def _default_control_planes(platform):
    """The platform's default control-plane policy.

    Every current platform defaults to agentless display — the
    universal, cooperation-free plane (machine-blueprint-reference.md).
    Richer per-platform defaults arrive with the adapter seam.
    """
    return ["agentless-display"]


def _resolve_hostdir(declared, source):
    """Resolve a drive ``hostdir`` to an existing absolute directory.

    A relative path resolves against the blueprint file's directory
    (the invocation asset root supersedes this in the residency work);
    an absolute path is used as given. A missing directory fails
    closed naming the resolved path.
    """
    if os.path.isabs(declared):
        resolved = declared
    else:
        base = os.path.dirname(source) if source else os.getcwd()
        resolved = os.path.join(base, declared)
    resolved = os.path.abspath(resolved)
    if not os.path.isdir(resolved):
        raise FileNotFoundError(
            f"hostdir directory does not exist: {resolved}")
    return resolved


def _blueprint_digest(resolved, drives):
    """Digest the resolved blueprint snapshot (the machine baseline).

    Covers the resolved logical shape only — the per-drive cache
    ``path`` (environment-specific) is excluded — so the same blueprint
    resolves to the same digest across homes, which is what ``apply``
    compares against.
    """
    snapshot = dict(resolved)
    snapshot["drives"] = {
        key: {name: value for name, value in entry.items()
              if name != "path"}
        for key, entry in drives.items()
    }
    canonical = json.dumps(
        snapshot, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(
        canonical.encode("utf-8")).hexdigest()


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


@contextlib.contextmanager
def _machine_lock(machine_id, context=None):
    """Hold the exclusive per-machine operation lock.

    Every mutating operation on one machine (create materialization,
    start, stop, destroy, media/boot changes) takes this before
    inspecting or changing backend state, so operations on one
    machine never interleave. The lock file lives beside the
    allocation locks; its ``.op.lock`` suffix keeps it distinct from
    any blueprint's allocation lock.
    """
    lock_root = _locks_dir(context)
    os.makedirs(lock_root, exist_ok=True)
    lock_path = os.path.join(lock_root, f"{machine_id}.op.lock")
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


def _materialize_drive(key, drive, drives_root, source, context):
    """Materialize one enabled drive, returning its resolved state entry.

    The entry carries the drive's logical shape plus the cache
    ``path`` reliquary realized (an image file, a host directory, or
    ``None`` for an empty removable slot). ``source`` is the blueprint
    file path a relative ``hostdir`` resolves against.
    """
    entry = {"medium": drive.medium, "slot": drive.slot}
    if drive.medium != "floppy":
        controller = drive.controller or "ide"
        if controller != "ide":
            raise NotImplementedError(
                f"drive {key!r} declares controller {controller!r}; "
                "only ide is wired on QEMU so far (the adapter seam "
                "owns richer controller topology)")
        entry["controller"] = controller
    if drive.size is not None:
        path = os.path.join(drives_root, f"{key}.qcow2")
        create_hdd_image(path, drive.size)
        entry.update(size=drive.size, path=path)
    elif drive.media is not None:
        entry.update(
            media=drive.media.item.name,
            path=fetch_media(drive.media.item.name, context=context))
    elif drive.base is not None:
        base_payload = fetch_media(drive.base.item.name, context=context)
        dest = os.path.join(drives_root, f"{key}.qcow2")
        if drive.base_type == "duplicate":
            create_duplicate_image(dest, base_payload)
        else:
            create_difference_image(dest, base_payload)
        entry.update(
            base={"media": drive.base.item.name, "type": drive.base_type},
            path=dest)
    elif drive.hostdir is not None:
        entry.update(
            hostdir=drive.hostdir,
            path=_resolve_hostdir(drive.hostdir, source))
    else:
        # An empty removable drive: guest-visible hardware with no
        # medium until a script inserts one.
        entry.update(media=None, path=None)
    return entry


def create(blueprint, *, context=None, blueprint_name="", source=None):
    """Materialize one machine from a parsed Blueprint.

    Creates the machine cache directory under
    ``cache/machines/<blueprint>-<n>/``, writes
    ``reliquary-machine.json`` with the fully resolved configuration
    and its provenance (``blueprint-source``, ``blueprint-digest``,
    ``backend-id``), and materializes every enabled drive: qcow2 for
    ``size`` and ``base`` (differencing or duplicated), the fetched
    payload for ``media``, a resolved host directory for ``hostdir``.
    ``source`` is the absolute path of the blueprint file this machine
    resolved from, recorded for selection scoping. The machine number
    is the lowest free non-negative integer for that blueprint.
    Returns the generated machine id.
    """
    if not isinstance(blueprint_name, str) or not blueprint_name:
        raise ValueError("create requires a non-empty blueprint_name")

    created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with _blueprint_alloc_lock(blueprint_name, context):
        machine_id = _allocate_machine_id(blueprint_name, context)
        drives_root = _machine_drives_dir(machine_id, context)
        os.makedirs(drives_root)
        # Mark the machine `creating` before materialization begins, so
        # an interrupted create is detectable and recoverable.
        _write_state(machine_id, {
            "id": machine_id,
            "blueprint": blueprint_name,
            "created": created,
            "phase": "creating",
            "generation": 0,
        }, context)

    with _machine_lock(machine_id, context):
        try:
            return _materialize_machine(
                blueprint, machine_id, blueprint_name, created,
                drives_root, source, context)
        except BaseException:
            # Roll back a failed create: the machine never reached a
            # usable phase, so its partial materialization is discarded.
            shutil.rmtree(
                machine_dir_path(machine_id, context), ignore_errors=True)
            raise


def _materialize_machine(blueprint, machine_id, blueprint_name, created,
                         drives_root, source, context):
    resolved_drives = {}
    for key, drive in sorted(blueprint.drives.items()):
        if not drive.enabled:
            # `enabled: false` removes the drive from the machine
            # entirely (machine-blueprint-reference.md).
            continue
        resolved_drives[key] = _materialize_drive(
            key, drive, drives_root, source, context)

    memory = blueprint.memory
    if memory is None:
        memory = _PLATFORM_MEMORY.get(blueprint.platform, 16)
    resolved = {
        "platform": blueprint.platform,
        "backend": blueprint.backend or "qemu",
        "memory": memory,
        "cpus": blueprint.cpus if blueprint.cpus is not None else 1,
        "boot": list(blueprint.boot),
        "name": blueprint.name,
        "description": blueprint.description,
        "scripts": dict(blueprint.scripts),
        "control-planes": (list(blueprint.control_planes)
                           or _default_control_planes(blueprint.platform)),
        "backend-settings": {
            name: dict(section)
            for name, section in blueprint.backend_settings.items()},
    }

    state = {
        "id": machine_id,
        "blueprint": blueprint_name,
        "created": created,
        "phase": "ready",
        "generation": 0,
        "backend-id": f"reliquary-{machine_id}",
        "blueprint-digest": _blueprint_digest(resolved, resolved_drives),
        **resolved,
        "drives": resolved_drives,
    }
    if source is not None:
        state["blueprint-source"] = os.path.abspath(os.fspath(source))

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
    return create(blueprint, context=context, blueprint_name=name,
                  source=path)


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


def _write_phase(machine_id, phase, context=None, *, bump=False):
    """Set a machine's phase, optionally advancing its generation.

    The operation generation is a monotonic counter bumped once when
    an operation begins (entering its transitional or target phase),
    so an interrupted operation is detectable by phase and generation.
    Completing steps within an operation write ``bump=False``.
    """
    state = load_machine_state(machine_id, context)
    state["phase"] = phase
    if bump:
        state["generation"] = state.get("generation", 0) + 1
    _write_state(machine_id, state, context)
    return state


def _complete_stop(machine_id, context=None):
    """Power off the owned VM and reconcile the phase.

    On success the phase becomes ``ready``. If the lifecycle stop
    fails closed, the phase is reconciled without lying: a recorded VM
    found already gone (``vm.json`` cleared) becomes ``ready``, while
    an identity mismatch (``vm.json`` intact — our VM may still be
    running) restores ``running``; either way the error propagates.
    """
    machine_home = machine_dir_path(machine_id, context)
    try:
        stop_owned_qemu(home=machine_home)
    except RuntimeError:
        if read_vm_state(machine_home) is None:
            _write_phase(machine_id, "ready", context)
        else:
            _write_phase(machine_id, "running", context)
        raise
    _write_phase(machine_id, "ready", context)


def _reconcile_phase(machine_id, context=None):
    """Recover a machine found in an interrupted transitional phase.

    Called under the machine lock at the start of each mutating
    operation (``destroy`` handles its own phases). A resting phase
    (``ready``/``running``) returns unchanged. ``stopping`` completes
    the interrupted stop; ``creating`` and ``destroying`` are rolled
    forward by removing the incomplete materialization, then the
    caller fails closed with recovery guidance.
    """
    state = load_machine_state(machine_id, context)
    phase = state.get("phase")
    if phase in ("ready", "running"):
        return state
    machine_home = machine_dir_path(machine_id, context)
    if phase == "creating":
        shutil.rmtree(machine_home, ignore_errors=True)
        raise RuntimeError(
            f"machine {machine_id} was interrupted during creation and "
            "has been rolled back; create it again with create-machine")
    if phase == "destroying":
        shutil.rmtree(machine_home, ignore_errors=True)
        raise RuntimeError(
            f"machine {machine_id} was interrupted during destruction "
            "and has now been removed")
    if phase == "stopping":
        _complete_stop(machine_id, context)
        return load_machine_state(machine_id, context)
    raise RuntimeError(
        f"machine {machine_id} is in an unrecognized phase {phase!r}")


def start_machine(machine_id, *, display=False, context=None):
    """Start a ready machine and return its QMP port.

    Under the per-machine lock, reconciles any interrupted phase,
    re-verifies every media hash, launches QEMU under the machine's
    cache directory, and records phase ``running``.
    """
    with _machine_lock(machine_id, context):
        state = _reconcile_phase(machine_id, context)
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
        _write_phase(machine_id, "running", context, bump=True)
        return port


def stop_machine(machine_id, context=None):
    """Stop a running machine and return it to phase ``ready``.

    Under the per-machine lock: reconciles any interrupted phase
    (an already-completed stop returns quietly), records the
    transitional ``stopping`` phase, then powers off the owned VM.
    """
    with _machine_lock(machine_id, context):
        state = _reconcile_phase(machine_id, context)
        phase = state.get("phase")
        if phase == "ready":
            # A reconciled interrupted stop already returned it here.
            return
        if phase != "running":
            raise RuntimeError(
                f"machine {machine_id} is not running "
                f"(phase: {phase})")
        _write_phase(machine_id, "stopping", context, bump=True)
        _complete_stop(machine_id, context)


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
    with _machine_lock(machine_id, context):
        state = _reconcile_phase(machine_id, context)
        drive = _removable_drive(state, slot, context)
        drive["path"] = fetch_media(media_name, context=context)
        drive["media"] = media_name
        state["generation"] = state.get("generation", 0) + 1
        _write_state(machine_id, state, context)


def eject_media(machine_id, slot, *, context=None):
    """Empty a declared removable slot, persisting the change.

    The drive itself remains — the blueprint alone defines machine
    topology — but the next ``start`` presents it without a medium.
    The machine must be stopped, as for :func:`insert_media`.
    """
    with _machine_lock(machine_id, context):
        state = _reconcile_phase(machine_id, context)
        drive = _removable_drive(state, slot, context)
        drive["media"] = None
        drive["path"] = None
        state["generation"] = state.get("generation", 0) + 1
        _write_state(machine_id, state, context)


def set_boot_order(machine_id, boot_keys, *, context=None):
    """Persist a new boot order on a stopped machine.

    Every key must name a drive the machine already declares.
    Duplicates are rejected.  The change lives in
    ``reliquary-machine.json`` and takes effect on the next
    ``start``; the machine diverges from its blueprint until
    ``apply`` (or another ``set_boot_order``) restores it.
    """
    with _machine_lock(machine_id, context):
        state = _reconcile_phase(machine_id, context)
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
        state["generation"] = state.get("generation", 0) + 1
        _write_state(machine_id, state, context)


def mark_stopped(machine_id, context=None):
    """Reconcile the phase of a machine whose QEMU process has gone.

    Used when the guest powers itself off (the script observed
    ``stopped``): the phase returns to ``ready`` and the stale
    ``vm.json`` is removed.  A machine not in phase ``running`` is
    left untouched.
    """
    with _machine_lock(machine_id, context):
        state = load_machine_state(machine_id, context)
        if state.get("phase") != "running":
            return
        vm_path = os.path.join(
            machine_dir_path(machine_id, context), "vm.json")
        try:
            os.remove(vm_path)
        except FileNotFoundError:
            pass
        _write_phase(machine_id, "ready", context, bump=True)


def destroy_machine(machine_id, context=None):
    """Delete a machine's cache directory entirely.

    Under the per-machine lock. A ``ready`` machine passes through the
    transitional ``destroying`` phase; a machine already ``destroying``
    or rolled-back-from ``creating`` completes its removal. A running
    machine is refused. A deletion interrupted by a host lock can be
    retried — a failure from ``ready`` restores ``ready`` so it does
    not strand the machine in ``destroying``.
    """
    with _machine_lock(machine_id, context):
        state = load_machine_state(machine_id, context)
        phase = state.get("phase")
        if phase == "running":
            raise RuntimeError(
                f"machine {machine_id} is running; "
                "stop it before destroying")
        if phase not in ("ready", "destroying", "creating"):
            raise RuntimeError(
                f"machine {machine_id} cannot be destroyed "
                f"(phase: {phase})")
        if phase == "ready":
            _write_phase(machine_id, "destroying", context, bump=True)
        try:
            shutil.rmtree(machine_dir_path(machine_id, context))
        except OSError:
            # Leave the machine in a retry-able phase.
            if phase == "ready":
                _write_phase(machine_id, "ready", context)
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
