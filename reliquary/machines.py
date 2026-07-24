# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Machine materialization and cached-state management."""

import contextlib
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone

from .acquire import fetch_media as _acquire_fetch
from .home import machines_cache_dir
from .library import seed_blueprint
from .lifecycle import (create_difference_image, create_duplicate_image,
                        create_hdd_image, find_qemu, launch_owned_qemu,
                        read_vm_state, stop as stop_owned_qemu)
from .resolve import load_namespace, resolve_media


def _drive_media(drive, namespace):
    """The media a drive carries: from the catalog, or written in place.

    An inline media declared at the drive is used directly — the
    anonymous blank has no catalog name to look up, being in no
    namespace at all.
    """
    if drive.inline is not None:
        return drive.inline
    if drive.media is None:
        return None
    return resolve_media(drive.media, namespace)


def _image_stem(media, key):
    """The per-machine image name: the media, or the slot for the blank.

    Images are keyed by media so that media moving through a shared
    removable slot never clobber one another. The anonymous blank is the
    one exception and the one place a slot names anything: it has no
    catalog identity to be keyed by.
    """
    return media.name or key


def _fetch(media_name, context, *, namespace=None, on_mismatch="fail"):
    """Resolve a media by name against the source namespace and fetch
    its verified payload path (or ``None`` for a ``new`` blank)."""
    namespace = namespace if namespace is not None else load_namespace(context)
    media = resolve_media(media_name, namespace)
    return _acquire_fetch(media, namespace, context, on_mismatch)


_BOOT_LETTER = {"floppy": "a", "hdd": "c", "cdrom": "d"}
_PLATFORM_MEMORY = {
    "dos": 16,
    "openbsd": 512,
    "win9x": 64,
    "winnt": 256,
}


def format_options(image):
    """The QEMU ``format=`` option for an image, by extension.

    ``.img`` / ``.iso`` are pinned to ``format=raw`` (avoiding QEMU's
    format-probing warning); any other extension is left for QEMU to
    identify.
    """
    extension = os.path.splitext(image)[1].lower()
    return "format=raw," if extension in (".img", ".iso") else ""


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


def _machine_media_dir(machine_id, context=None):
    """Per-machine materialized-image directory, keyed by media item.

    Images are named for the media (``<media-name>.<ext>``), not the
    slot, so media swapping through one removable slot each keep their
    own materialization and a re-insert reuses the existing image.
    """
    return os.path.join(machine_dir_path(machine_id, context), "media")


def _backend_dir(machine_id, backend, context=None):
    """The backend's own-artifacts subdirectory (``<backend>/``).

    reliquary quarantines each backend's files in a backend-named
    subdir so the machine root holds only ``machine.json`` and the
    ``media/`` and ``runs/`` directories. For QEMU it holds just the
    captured ``qemu-stderr.log``.
    """
    return os.path.join(machine_dir_path(machine_id, context),
                        backend or "qemu")


def _state_path(machine_id, context=None):
    return os.path.join(machine_dir_path(machine_id, context),
                        "machine.json")


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


def _drive_common(key, drive):
    """The medium/slot/controller fields common to every drive entry."""
    entry = {"medium": drive.medium, "slot": drive.slot}
    if drive.medium != "floppy":
        controller = drive.controller or "ide"
        if controller != "ide":
            raise NotImplementedError(
                f"drive {key!r} declares controller {controller!r}; "
                "only ide is wired on QEMU so far (the adapter seam "
                "owns richer controller topology)")
        entry["controller"] = controller
    return entry


def _materialize_drive(key, drive, media_root, namespace, context):
    """Materialize one enabled drive, returning its resolved state entry.

    The drive names a media (or is an empty removable slot); the media
    owns materialization. ``new`` is a fresh blank of its ``size``;
    ``use`` attaches the fetched payload directly (a directory payload
    renders as vvfat); ``difference``/``copy`` build a per-machine image
    over/of the fetched payload. Per-machine images live under
    ``media/`` keyed by the media name (``<media-name>.qcow2``), not the
    slot, so a media moving through a removable slot keeps its own
    image. The entry records the realized ``path`` plus the media name
    and mode.
    """
    entry = _drive_common(key, drive)
    media = _drive_media(drive, namespace)
    if media is None:
        # An empty removable slot: guest-visible hardware with no medium
        # until a script inserts one.
        entry.update(media=None, materialize=None, path=None)
        return entry
    mode = media.materialize
    if drive.medium == "cdrom" and mode != "use":
        raise ValueError(
            f"drives.{key}: a cdrom is read-only, so its media must "
            f"'use' (attach), not '{mode}'")
    entry["media"] = media.name
    entry["materialize"] = mode
    if mode == "new":
        path = os.path.join(media_root, f"{_image_stem(media, key)}.qcow2")
        create_hdd_image(path, media.size)
        entry.update(size=media.size, path=path)
    elif mode == "use":
        entry["path"] = _acquire_fetch(media, namespace, context)
    elif mode in ("difference", "copy"):
        base_payload = _acquire_fetch(media, namespace, context)
        dest = os.path.join(media_root, f"{_image_stem(media, key)}.qcow2")
        if mode == "copy":
            create_duplicate_image(dest, base_payload)
        else:
            create_difference_image(dest, base_payload)
        entry["path"] = dest
    else:
        raise ValueError(f"unknown materialize mode {mode!r} for {key}")
    return entry


def create(machine, namespace, *, context=None, blueprint_name="",
           source=None, number=None):
    """Materialize one machine from a parsed composed machine component.

    Creates the machine cache directory under
    ``cache/machines/<blueprint>-<n>/``, writes ``machine.json`` with
    the fully resolved configuration and its provenance
    (``blueprint-source``, ``blueprint-digest``, ``backend-id``), and
    materializes every enabled drive: a per-machine qcow2 under
    ``media/`` for ``new``/``difference``/``copy`` media, the fetched
    payload attached in place for ``use``. ``source`` is the absolute
    path of the blueprint file this machine resolved from, recorded for
    selection scoping. The machine number is the lowest free
    non-negative integer for that blueprint, unless ``number`` pins a
    specific one (``recreate`` reuses the old id). Returns the
    generated machine id.
    """
    if not isinstance(blueprint_name, str) or not blueprint_name:
        raise ValueError("create requires a non-empty blueprint_name")

    created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with _blueprint_alloc_lock(blueprint_name, context):
        if number is None:
            machine_id = _allocate_machine_id(blueprint_name, context)
        else:
            machine_id = machine_id_for(blueprint_name, number)
            if os.path.exists(machine_dir_path(machine_id, context)):
                raise RuntimeError(
                    f"machine {machine_id} already exists")
        media_root = _machine_media_dir(machine_id, context)
        os.makedirs(media_root)
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
                machine, namespace, machine_id, blueprint_name, created,
                media_root, source, context)
        except BaseException:
            # Roll back a failed create: the machine never reached a
            # usable phase, so its partial materialization is discarded.
            shutil.rmtree(
                machine_dir_path(machine_id, context), ignore_errors=True)
            raise


def _materialize_machine(machine, namespace, machine_id, blueprint_name,
                         created, media_root, source, context):
    resolved_drives = {}
    for key, drive in sorted(machine.drives.items()):
        if not drive.enabled:
            # `enabled: false` removes the drive from the machine
            # entirely (machine-blueprint-reference.md).
            continue
        resolved_drives[key] = _materialize_drive(
            key, drive, media_root, namespace, context)

    memory = machine.memory
    if memory is None:
        memory = _PLATFORM_MEMORY.get(machine.platform, 16)
    resolved = {
        "platform": machine.platform,
        "backend": machine.backend or "qemu",
        "memory": memory,
        "cpus": machine.cpus if machine.cpus is not None else 1,
        "boot": list(machine.boot),
        "name": machine.name,
        "description": machine.description,
        "scripts": dict(machine.scripts),
        "control-planes": (list(machine.control_planes)
                           or _default_control_planes(machine.platform)),
        "backend-settings": {
            name: dict(section)
            for name, section in machine.backend_settings.items()},
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


def create_machine(name, *, context=None, number=None):
    """Load ``blueprints/<name>.rlqb`` and materialize one machine.

    A blueprint the home does not contain is seeded from the
    built-in library on this first reference, along with the media
    definitions and scripts it references (never overwriting user
    files). ``number`` pins the machine number (``recreate`` reuses
    the old id); omitted, the lowest free number is allocated.
    """
    from .assets import source_for
    # Home mode seeds the blueprint (and the media/scripts it carries)
    # from the codex on first reference (idempotent, never overwriting);
    # dir mode (``--assets``) is hermetic and seeds nothing.
    if source_for(context).seeds:
        seed_blueprint(name, context=context)
    namespace = load_namespace(context)
    if name not in namespace.machines:
        raise FileNotFoundError(
            f"no machine blueprint named {name!r} in the resolution source")
    machine = namespace.machines[name]
    source = namespace.origin.get(("machine", name))
    return create(machine, namespace, context=context, blueprint_name=name,
                  source=source, number=number)


def recreate_machine(*, machine=None, blueprint=None, context=None):
    """Destroy the selected machine and recreate it under the same id.

    Exactly ``destroy`` + ``create`` (instance model): the current
    blueprint is re-resolved and backend assignment re-runs, so drives
    regenerate as declared and the machine may land differently than
    before. Returns the reused machine id.
    """
    machine_id = resolve_machine(
        machine=machine, blueprint=blueprint, context=context)
    parsed = split_machine_id(machine_id)
    if parsed is None:
        raise ValueError(f"cannot parse machine id {machine_id!r}")
    blueprint_name, number = parsed
    destroy_machine(machine_id, context)
    return create_machine(blueprint_name, context=context, number=number)


def get_machine_dir(*, machine=None, blueprint=None, context=None):
    """Return the absolute cache directory of the selected machine.

    The out-of-band door (instance model): a query valid in any
    phase, touching nothing.
    """
    machine_id = resolve_machine(
        machine=machine, blueprint=blueprint, context=context)
    return os.path.abspath(machine_dir_path(machine_id, context))


_OWNED_MODES = ("new", "difference", "copy")


def _reconcile_drives(machine, namespace, old_drives, media_root, context):
    """Reconcile a machine's drives to a re-resolved machine component.

    Absorbable changes are applied: added, removed, enabled/disabled
    drives, and every ``use``/empty-slot drive (re-fetched or emptied —
    this also reconciles away a script's divergence). A drive whose
    image reliquary already materialized (``new``/``difference``/``copy``)
    is kept only when its media name and mode (and ``new`` size) are
    unchanged; any change to it fails closed, naming ``recreate`` as the
    honest alternative. Returns the new drive-state mapping; a removed
    materialized image is deleted.
    """
    new_drives = {}
    enabled = {key: drive for key, drive in machine.drives.items()
               if drive.enabled}
    for key, drive in sorted(enabled.items()):
        old = old_drives.get(key)
        old_owns = old is not None and old.get("materialize") in _OWNED_MODES
        if not old_owns:
            # No reliquary-owned image here: (re)materialize/re-point
            # freely (media re-fetch, empty slot, or a new image).
            new_drives[key] = _materialize_drive(
                key, drive, media_root, namespace, context)
            continue
        # An existing materialized image may only be kept unchanged.
        media = _drive_media(drive, namespace)
        unchanged = (
            media is not None
            and media.name == old.get("media")
            and media.materialize == old.get("materialize")
            and (media.materialize != "new" or media.size == old.get("size")))
        if unchanged:
            entry = _drive_common(key, drive)
            entry.update(media=media.name, materialize=media.materialize,
                         path=old.get("path"))
            if media.materialize == "new":
                entry["size"] = media.size
            new_drives[key] = entry
        else:
            raise RuntimeError(
                f"drive {key} changes an already-materialized image; "
                "apply cannot regenerate drives — recreate the machine "
                "instead")
    # Delete materialized images for drives the blueprint dropped.
    for key, old in old_drives.items():
        if key in new_drives:
            continue
        path = old.get("path")
        if path and old.get("materialize") in _OWNED_MODES:
            try:
                os.remove(path)
            except OSError:
                pass
    return new_drives


def apply_blueprint(*, machine=None, blueprint=None, context=None):
    """Adopt the current blueprint into a stopped machine.

    Re-resolves the blueprint the machine was created from (never at
    ``start``) and reconciles the machine to it: memory, cpus, boot,
    control-planes, backend-settings, metadata, and the absorbable
    drive changes are applied; a changed ``size`` or ``base`` on an
    already-materialized image fails closed (``recreate`` is the
    alternative). The new resolved snapshot becomes the baseline
    (``blueprint-digest`` / ``blueprint-source`` re-recorded). Returns
    the machine id.
    """
    machine_id = resolve_machine(
        machine=machine, blueprint=blueprint, context=context)
    with _machine_lock(machine_id, context):
        state = _reconcile_phase(machine_id, context)
        phase = state.get("phase")
        if phase != "ready":
            raise RuntimeError(
                f"machine {machine_id} must be stopped to apply "
                f"(phase: {phase})")
        blueprint_name = state["blueprint"]
        namespace = load_namespace(context)
        if blueprint_name not in namespace.machines:
            raise FileNotFoundError(
                f"no machine blueprint named {blueprint_name!r} to apply")
        parsed = namespace.machines[blueprint_name]
        path = namespace.origin.get(("machine", blueprint_name))

        media_root = _machine_media_dir(machine_id, context)
        new_drives = _reconcile_drives(
            parsed, namespace, state.get("drives", {}), media_root, context)

        memory = parsed.memory
        if memory is None:
            memory = _PLATFORM_MEMORY.get(parsed.platform, 16)
        resolved = {
            "platform": parsed.platform,
            "backend": parsed.backend or "qemu",
            "memory": memory,
            "cpus": parsed.cpus if parsed.cpus is not None else 1,
            "boot": list(parsed.boot),
            "name": parsed.name,
            "description": parsed.description,
            "scripts": dict(parsed.scripts),
            "control-planes": (list(parsed.control_planes)
                               or _default_control_planes(parsed.platform)),
            "backend-settings": {
                name: dict(section)
                for name, section in parsed.backend_settings.items()},
        }
        state.update(resolved)
        state["drives"] = new_drives
        state["blueprint-digest"] = _blueprint_digest(resolved, new_drives)
        if path is not None:
            state["blueprint-source"] = os.path.abspath(path)
        state["generation"] = state.get("generation", 0) + 1
        _write_state(machine_id, state, context)
    return machine_id


def _write_state(machine_id, state, context=None):
    path = _state_path(machine_id, context)
    part = path + ".part"
    with open(part, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(state, handle, indent=2)
        handle.write("\n")
    os.replace(part, path)


def load_machine_state(machine_id, context=None):
    """Read and return the machine's ``machine.json``."""
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
        path = os.path.join(root, entry, "machine.json")
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


def machines_for_blueprint(name, context=None):
    """Machines of blueprint ``name`` scoped to this invocation's source.

    Selection scoping (instance model): a machine matches when its
    recorded ``blueprint-source`` equals the invocation's own
    resolution of ``name``, so same-named blueprints in different
    projects never select each other's machines — and ``apply`` never
    adopts them. A machine with no recorded source matches by name
    alone (there is nothing to scope it against); when ``name`` does
    not resolve in this invocation, only such sourceless machines can
    match. Ordered like :func:`list_machines`.
    """
    from .library import locate_blueprint
    matches = list_machines(context, blueprint=name)
    try:
        resolved = os.path.abspath(locate_blueprint(name, context=context))
    except FileNotFoundError:
        resolved = None
    scoped = []
    for state in matches:
        source = state.get("blueprint-source")
        if source is None:
            scoped.append(state)
        elif resolved is not None and os.path.abspath(source) == resolved:
            scoped.append(state)
    return scoped


def _resolve_by_blueprint(name, context):
    matches = machines_for_blueprint(name, context)
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


def _clear_vm(machine_id, phase, context=None):
    """Drop the running ``vm`` section and set a resting phase, one write.

    Phase and VM identity live in the same ``machine.json`` and are
    written together, so a stopped machine can never carry a stale VM
    identity beside a ``ready`` phase.
    """
    state = load_machine_state(machine_id, context)
    state.pop("vm", None)
    state["phase"] = phase
    _write_state(machine_id, state, context)


def _complete_stop(machine_id, context=None):
    """Power off the owned VM and reconcile phase + VM identity.

    On success the machine returns to ``ready`` and its ``vm`` section
    is cleared, written together. If the lifecycle stop fails closed,
    the phase is reconciled without lying: a machine whose ``vm``
    section is already gone becomes ``ready``, while one still recorded
    (our VM may yet be running — a stuck port or an identity mismatch)
    restores ``running``; either way the error propagates.
    """
    state = load_machine_state(machine_id, context)
    vm = state.get("vm")
    try:
        stop_owned_qemu(vm)
    except RuntimeError:
        if load_machine_state(machine_id, context).get("vm") is None:
            _write_phase(machine_id, "ready", context)
        else:
            _write_phase(machine_id, "running", context)
        raise
    _clear_vm(machine_id, "ready", context)


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
        namespace = load_namespace(context)
        for drive in drives.values():
            media_name = drive.get("media")
            # Re-resolve attached (`use`) payloads and re-verify their
            # hashes; per-machine images (new/difference/copy) keep their
            # recorded path.
            if media_name is not None and drive.get("materialize") == "use":
                drive["path"] = _fetch(
                    media_name, context, namespace=namespace)
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

        # QEMU's own artifacts (the captured stderr log) live in the
        # machine's backend subdirectory; lifecycle returns the VM
        # identity and machines.py persists it into machine.json
        # atomically with the running phase, so the two never disagree.
        backend_dir = _backend_dir(
            machine_id, state.get("backend", "qemu"), context)
        vm = launch_owned_qemu(
            args, vm_name=vm_name, display=display,
            current_vm=state.get("vm"), log_dir=backend_dir)
        try:
            fresh = load_machine_state(machine_id, context)
            fresh["vm"] = vm
            fresh["phase"] = "running"
            fresh["generation"] = fresh.get("generation", 0) + 1
            _write_state(machine_id, fresh, context)
        except BaseException:
            # The VM came up but its identity could not be recorded;
            # stop it rather than orphan an unrecorded process.
            with contextlib.suppress(Exception):
                stop_owned_qemu(vm)
            raise
        return vm["port"]


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


def _removable_drive(state, slot):
    """Return the mutable state entry for a removable drive slot."""
    drive = state.get("drives", {}).get(slot)
    if drive is None:
        raise ValueError(
            f"machine {state['id']} declares no "
            f"drive {slot}")
    if drive.get("medium") not in _REMOVABLE_MEDIA:
        raise ValueError(
            f"{slot} is not a removable drive slot")
    return drive


def _change_media_live(machine_id, slot, path, context):
    """Change a removable drive's medium on a running machine over QMP.

    The medium is swapped through the machine's identity-verified QMP
    session (HMP ``eject`` / ``change`` against the drive's launch id,
    which is the slot key), so the change the guest sees and the change
    persisted to the state stay one operation.
    """
    from .machine import Machine
    machine_home = machine_dir_path(machine_id, context)
    vm = read_vm_state(machine_home)
    if vm is None:
        raise RuntimeError(
            f"machine {machine_id} is running but has no recorded VM "
            "identity")
    with Machine(port=vm["port"], home=machine_home).qmp() as qmp:
        if path is None:
            qmp.hmp(f"eject {slot}")
        else:
            target = os.fspath(path).replace("\\", "/")
            extension = os.path.splitext(target)[1].lower()
            fmt = " raw" if extension in (".img", ".iso") else ""
            qmp.hmp(f"change {slot} {target}{fmt}")


def insert_media(machine_id, slot, media_name, *, context=None):
    """Insert a defined media item into a floppy or cdrom slot.

    Hard-disk slots are rejected.  The slot must already exist in
    the machine's state — drives are guest-visible hardware the
    blueprint declares, so ``insert`` never creates one.  Running or
    stopped: on a running machine the medium is changed live over QMP
    (a change the guest observes); on a stopped machine it is present
    at the next ``start``.  The change persists in ``machine.json``
    across stop/start — the machine diverges from its blueprint until a
    later ``insert``/``eject`` or ``apply``.
    """
    with _machine_lock(machine_id, context):
        state = _reconcile_phase(machine_id, context)
        _removable_drive(state, slot)
        path = _fetch(media_name, context)
        if state.get("phase") == "running":
            _change_media_live(machine_id, slot, path, context)
        drive = state["drives"][slot]
        drive["path"] = path
        drive["media"] = media_name
        drive["materialize"] = "use"
        state["generation"] = state.get("generation", 0) + 1
        _write_state(machine_id, state, context)


def eject_media(machine_id, slot, *, context=None):
    """Empty a declared removable slot, persisting the change.

    The drive itself remains — the blueprint alone defines machine
    topology.  Running or stopped, as for :func:`insert_media`: on a
    running machine the medium is ejected live over QMP; on a stopped
    machine the next ``start`` presents it without a medium.
    """
    with _machine_lock(machine_id, context):
        state = _reconcile_phase(machine_id, context)
        _removable_drive(state, slot)
        if state.get("phase") == "running":
            _change_media_live(machine_id, slot, None, context)
        drive = state["drives"][slot]
        drive["media"] = None
        drive["materialize"] = None
        drive["path"] = None
        state["generation"] = state.get("generation", 0) + 1
        _write_state(machine_id, state, context)


def set_boot_order(machine_id, boot_keys, *, context=None):
    """Persist a new boot order on a stopped machine.

    Every key must name a drive the machine already declares.
    Duplicates are rejected.  The change lives in ``machine.json`` and
    takes effect on the next ``start``; the machine diverges from its
    blueprint until ``apply`` (or another ``set_boot_order``) restores
    it.
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
    ``stopped``): the phase returns to ``ready`` and the stale ``vm``
    section is cleared, written together.  A machine not in phase
    ``running`` is left untouched.
    """
    with _machine_lock(machine_id, context):
        state = load_machine_state(machine_id, context)
        if state.get("phase") != "running":
            return
        state.pop("vm", None)
        state["phase"] = "ready"
        state["generation"] = state.get("generation", 0) + 1
        _write_state(machine_id, state, context)


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
