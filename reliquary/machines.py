# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Machine materialization and cached-state management."""

import contextlib
import hashlib
import json
import os
import re
import shutil
from datetime import datetime, timezone

from . import events as _events
from .acquire import fetch_media as _acquire_fetch
from .errors import (InternalError, PreflightError, ReliquaryError,
                     StaticError)
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


def _fetch(media_name, context, *, namespace=None, on_mismatch="fail",
           events=None, cancelled=None):
    """Resolve a media by name against the source namespace and fetch
    its verified payload path (or ``None`` for a ``new`` blank)."""
    namespace = namespace if namespace is not None else load_namespace(context)
    media = resolve_media(media_name, namespace)
    return _acquire_fetch(media, namespace, context, on_mismatch,
                          events=events, cancelled=cancelled)


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
    universal, cooperation-free plane (blueprint-reference.md).
    Richer per-platform defaults arrive with the adapter seam.
    """
    return ["agentless-display"]


# The parser accepts the model's whole control-plane vocabulary; this
# is the subset that exists.
_IMPLEMENTED_CONTROL_PLANES = ("agentless-display",)

# Likewise for backends. The blueprint model's vocabulary is qemu,
# virtualbox, vmware and hyperv; one adapter exists (F2 owns the seam,
# F3 the second backend).
_IMPLEMENTED_BACKENDS = ("qemu",)


def _resolve_backend(machine):
    """The machine's backend, defaulted and checked.

    A blueprint naming a backend Reliquary has not built fails closed
    naming it, exactly as an unwired control plane or controller does
    (P11). It used to be recorded and then ignored, which was the
    worst of the three outcomes: `backend: virtualbox` materialized a
    **qcow2** image and would have launched QEMU, so a machine's
    recorded backend and its actual one disagreed with nobody told.
    The field reference's backend/format table promised VDI for that
    same declaration, so the document and the code contradicted each
    other and the code was the one in the wrong.
    """
    backend = machine.backend or "qemu"
    if backend not in _IMPLEMENTED_BACKENDS:
        raise PreflightError(
            f"backend {backend!r} is not wired; only 'qemu' is built so "
            "far (the adapter seam owns the others). Its image format, "
            "lifecycle and control planes would all be QEMU's, which is "
            "not what this blueprint asks for",
            rule_id="machine.backend-not-wired")
    return backend


def _resolve_control_planes(machine):
    """The machine's control-plane policy, defaulted and checked.

    A blueprint naming a plane Reliquary has not built fails closed
    naming it, rather than materializing a machine whose recorded
    policy promises a plane nothing can probe (P11).
    """
    planes = (list(machine.control_planes)
              or _default_control_planes(machine.platform))
    missing = [plane for plane in planes
               if plane not in _IMPLEMENTED_CONTROL_PLANES]
    if missing:
        names = ", ".join(repr(plane) for plane in missing)
        raise PreflightError(
            f"control-planes names {names}; only 'agentless-display' "
            "is wired so far (the adapter seam owns the other planes)")
    return planes


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
    ``media/`` and ``screenshots/`` directories. For QEMU it holds
    just the captured ``qemu-stderr.log``.
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
            raise PreflightError(
                f"drive {key!r} declares controller {controller!r}; "
                "only ide is wired on QEMU so far (the adapter seam "
                "owns richer controller topology)")
        entry["controller"] = controller
    return entry


def _materialize_drive(key, drive, media_root, namespace, context,
                       properties=None, events=None, cancelled=None):
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
        raise StaticError(
            f"drives.{key}: a cdrom is read-only, so its media must "
            f"'use' (attach), not '{mode}'")
    entry["media"] = media.name
    entry["materialize"] = mode
    if mode == "new":
        path = os.path.join(media_root, f"{_image_stem(media, key)}.qcow2")
        create_hdd_image(path, media.size)
        entry.update(size=media.size, path=path)
    elif mode == "use":
        entry["path"] = _acquire_fetch(
            media, namespace, context, properties=properties, events=events,
            cancelled=cancelled)
    elif mode in ("difference", "copy"):
        base_payload = _acquire_fetch(
            media, namespace, context, properties=properties, events=events,
            cancelled=cancelled)
        dest = os.path.join(media_root, f"{_image_stem(media, key)}.qcow2")
        if mode == "copy":
            create_duplicate_image(dest, base_payload)
        else:
            create_difference_image(dest, base_payload)
        entry["path"] = dest
    else:
        raise InternalError(f"unknown materialize mode {mode!r} for {key}")
    return entry


def create(machine, namespace, *, context=None, blueprint_name="",
           source=None, number=None, properties=None, events=None):
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
        raise StaticError("create requires a non-empty blueprint_name")

    created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with _blueprint_alloc_lock(blueprint_name, context):
        if number is None:
            machine_id = _allocate_machine_id(blueprint_name, context)
        else:
            machine_id = machine_id_for(blueprint_name, number)
            if os.path.exists(machine_dir_path(machine_id, context)):
                raise PreflightError(
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
                media_root, source, context, properties, events)
        except BaseException:
            # Roll back a failed create: the machine never reached a
            # usable phase, so its partial materialization is discarded.
            shutil.rmtree(
                machine_dir_path(machine_id, context), ignore_errors=True)
            raise


def _materialize_machine(machine, namespace, machine_id, blueprint_name,
                         created, media_root, source, context,
                         properties=None, events=None):
    # Checked before anything is materialized, so a refusal costs no
    # image work.
    backend = _resolve_backend(machine)
    control_planes = _resolve_control_planes(machine)
    resolved_drives = {}
    for key, drive in sorted(machine.drives.items()):
        if not drive.enabled:
            # `enabled: false` removes the drive from the machine
            # entirely (blueprint-reference.md).
            continue
        resolved_drives[key] = _materialize_drive(
            key, drive, media_root, namespace, context, properties, events)

    memory = machine.memory
    if memory is None:
        memory = _PLATFORM_MEMORY.get(machine.platform, 16)
    resolved = {
        "platform": machine.platform,
        "backend": backend,
        "memory": memory,
        "cpus": machine.cpus if machine.cpus is not None else 1,
        "boot": list(machine.boot),
        "name": machine.name,
        "description": machine.description,
        "scripts": dict(machine.scripts),
        "control-planes": control_planes,
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


def _bind_location_properties(machine, namespace, *, parameters=None,
                              explicit=None, properties_file=None,
                              context=None):
    """Bind every ``${key}`` a machine's media locations reference.

    Collected across the drives' containment closure and bound through
    the property source order at create/apply time, so a media located
    by ``${license-iso}`` materializes from the value a parameter, the
    environment, the file, or an interactive ask supplies. Returns
    ``{key: value}`` (empty when no location references any property).
    """
    from . import binding, resolve
    keys = set()
    for drive in machine.drives.values():
        if not drive.enabled or drive.media is None:
            continue
        media = namespace.media.get(drive.media)
        if media is not None:
            keys.update(resolve.location_property_keys(media, namespace))
    if not keys:
        return {}
    return binding.bind_keys(
        keys, parameters=dict(machine.parameters), explicit=explicit,
        properties_file=properties_file, context=context,
        asker=binding.console_asker())


def create_machine(name, *, context=None, number=None, properties=None,
                   properties_file=None, events=None):
    """Load ``blueprints/<name>.rlqb`` and materialize one machine.

    A blueprint the home does not contain is seeded from the
    built-in library on this first reference, along with the media
    definitions and scripts it references (never overwriting user
    files). ``number`` pins the machine number (``recreate`` reuses
    the old id); omitted, the lowest free number is allocated.
    ``properties`` / ``properties_file`` bind any ``${key}`` a media
    location references, before materialization.
    """
    from .assets import source_for
    # Home mode seeds the blueprint (and the media/scripts it carries)
    # from the codex on first reference (idempotent, never overwriting);
    # dir mode (``--assets``) is hermetic and seeds nothing.
    if source_for(context).seeds:
        seed_blueprint(name, context=context)
    namespace = load_namespace(context)
    if name not in namespace.machines:
        raise PreflightError(
            f"no machine blueprint named {name!r} in the resolution source")
    machine = namespace.machines[name]
    source = namespace.origin.get(("machine", name))
    bound = _bind_location_properties(
        machine, namespace, explicit=properties,
        properties_file=properties_file, context=context)
    return create(machine, namespace, context=context, blueprint_name=name,
                  source=source, number=number, properties=bound,
                  events=events)


def recreate_machine(*, machine=None, blueprint=None, context=None,
                     properties=None, properties_file=None, events=None):
    """Destroy the selected machine and recreate it under the same id.

    Exactly ``destroy`` + ``create`` (instance model): the current
    blueprint is re-resolved and backend assignment re-runs, so drives
    regenerate as declared and the machine may land differently than
    before. ``properties`` / ``properties_file`` bind any ``${key}`` a
    media location references, as for ``create``. Returns the reused
    machine id.
    """
    machine_id = resolve_machine(
        machine=machine, blueprint=blueprint, context=context)
    parsed = split_machine_id(machine_id)
    if parsed is None:
        raise StaticError(f"cannot parse machine id {machine_id!r}")
    blueprint_name, number = parsed
    destroy_machine(machine_id, context)
    return create_machine(
        blueprint_name, context=context, number=number,
        properties=properties, properties_file=properties_file,
        events=events)


def get_machine_dir(*, machine=None, blueprint=None, context=None):
    """Return the absolute cache directory of the selected machine.

    The out-of-band door (instance model): a query valid in any
    phase, touching nothing.
    """
    machine_id = resolve_machine(
        machine=machine, blueprint=blueprint, context=context)
    return os.path.abspath(machine_dir_path(machine_id, context))


_OWNED_MODES = ("new", "difference", "copy")


def _reconcile_drives(machine, namespace, old_drives, media_root, context,
                      properties=None, events=None):
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
                key, drive, media_root, namespace, context, properties,
                events)
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
            raise PreflightError(
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


def apply_blueprint(*, machine=None, blueprint=None, context=None,
                    properties=None, properties_file=None, events=None):
    """Adopt the current blueprint into a stopped machine.

    Re-resolves the blueprint the machine was created from (never at
    ``start``) and reconciles the machine to it: memory, cpus, boot,
    control-planes, backend-settings, metadata, and the absorbable
    drive changes are applied; a changed ``size`` or ``base`` on an
    already-materialized image fails closed (``recreate`` is the
    alternative). The new resolved snapshot becomes the baseline
    (``blueprint-digest`` / ``blueprint-source`` re-recorded).
    ``properties`` / ``properties_file`` bind any ``${key}`` a
    re-materialized media location references. Returns the machine id.
    """
    machine_id = resolve_machine(
        machine=machine, blueprint=blueprint, context=context)
    with _machine_lock(machine_id, context):
        state = _reconcile_phase(machine_id, context)
        phase = state.get("phase")
        if phase != "ready":
            raise PreflightError(
                f"machine {machine_id} must be stopped to apply "
                f"(phase: {phase})")
        blueprint_name = state["blueprint"]
        namespace = load_namespace(context)
        if blueprint_name not in namespace.machines:
            raise PreflightError(
                f"no machine blueprint named {blueprint_name!r} to apply")
        parsed = namespace.machines[blueprint_name]
        path = namespace.origin.get(("machine", blueprint_name))
        # Checked before the drives are reconciled, so a refused apply
        # leaves the machine as it was.
        _resolve_backend(parsed)
        control_planes = _resolve_control_planes(parsed)

        bound = _bind_location_properties(
            parsed, namespace, explicit=properties,
            properties_file=properties_file, context=context)
        media_root = _machine_media_dir(machine_id, context)
        new_drives = _reconcile_drives(
            parsed, namespace, state.get("drives", {}), media_root, context,
            bound, events)

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
            "control-planes": control_planes,
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
        raise PreflightError(
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
            raise InternalError(
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
        raise StaticError(
            "select a machine with --blueprint or --machine")
    if machine is not None and blueprint is not None:
        raise StaticError(
            "--blueprint and --machine are mutually exclusive; "
            "pass --machine <id> or --blueprint <name>")
    if machine is not None:
        return _resolve_by_id(machine, context)
    return _resolve_by_blueprint(blueprint, context)


def _resolve_by_id(selector, context):
    """Resolve a full machine id — exact match only."""
    if not isinstance(selector, str) or not selector:
        raise StaticError(
            f"machine id must be a non-empty string, got: {selector!r}")
    if selector.isdigit():
        raise StaticError(
            f"machine id must be the full <blueprint>-<n> form, "
            f"got: {selector!r}")
    for state in list_machines(context):
        if state["id"] == selector:
            return selector
    raise PreflightError(f"no machine {selector!r}")


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
    except PreflightError:
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
        raise PreflightError(
            f"no machine exists for blueprint {name!r}\n"
            f"create one: rlq create-machine --blueprint {name}")
    if len(matches) > 1:
        lines = [
            f"blueprint {name!r} has {len(matches)} machines; "
            "pick one with --machine <id>:",
        ]
        for state in matches:
            lines.append(f"  {state['id']}  ({state.get('phase', '?')})")
        raise PreflightError("\n".join(lines))
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
    except ReliquaryError:
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
        raise PreflightError(
            f"machine {machine_id} was interrupted during creation and "
            "has been rolled back; create it again with create-machine")
    if phase == "destroying":
        shutil.rmtree(machine_home, ignore_errors=True)
        raise PreflightError(
            f"machine {machine_id} was interrupted during destruction "
            "and has now been removed")
    if phase == "stopping":
        _complete_stop(machine_id, context)
        return load_machine_state(machine_id, context)
    raise InternalError(
        f"machine {machine_id} is in an unrecognized phase {phase!r}")


def start_machine(machine_id, *, display=False, context=None, events=None,
                  cancelled=None):
    """Start a ready machine and return its QMP port.

    Under the per-machine lock, reconciles any interrupted phase,
    re-verifies every media hash, launches QEMU under the machine's
    cache directory, and records phase ``running``. Machine variables
    are cleared here: a variable reports what *this* boot produced,
    never what a previous one left behind.
    """
    with _machine_lock(machine_id, context):
        state = _reconcile_phase(machine_id, context)
        phase = state.get("phase")
        if phase == "running":
            raise PreflightError(
                f"machine {machine_id} is already running")
        if phase != "ready":
            raise PreflightError(
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
                    media_name, context, namespace=namespace, events=events,
                    cancelled=cancelled)
        # The backend fixes a floppy drive's geometry from whatever
        # medium is attached at launch, so record it: a later live
        # swap must match, and this is the only moment the fact is
        # knowable.
        for drive in drives.values():
            if drive.get("medium") == "floppy":
                drive["launch-size"] = _medium_size(drive.get("path"))
        state["drives"] = drives
        # A machine variable belongs to one boot: a script `set` it
        # while the guest ran, so the next start starts empty.
        state.pop("variables", None)
        _write_state(machine_id, state, context)

        memory = state.get("memory")
        if memory is None:
            memory = _PLATFORM_MEMORY.get(state.get("platform"), 16)
        qemu = find_qemu()
        _events.note(events, _events.RUN_PREFLIGHT,
                     f"using QEMU: {qemu}",
                     backend=state.get("backend", "qemu"),
                     executable=qemu,
                     **{"control-planes": state.get("control-planes") or []})
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
            raise PreflightError(
                f"machine {machine_id} is not running "
                f"(phase: {phase})")
        _write_phase(machine_id, "stopping", context, bump=True)
        _complete_stop(machine_id, context)


_REMOVABLE_MEDIA = {"floppy", "cdrom"}


def _removable_drive(state, slot):
    """Return the mutable state entry for a removable drive slot."""
    drive = state.get("drives", {}).get(slot)
    if drive is None:
        raise PreflightError(
            f"machine {state['id']} declares no "
            f"drive {slot}")
    if drive.get("medium") not in _REMOVABLE_MEDIA:
        raise PreflightError(
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
        raise PreflightError(
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


def _medium_size(path):
    """The byte size of an attached medium, or ``None`` for an empty
    slot or a directory-source (vvfat) drive, which has no image."""
    if not path or os.path.isdir(path):
        return None
    try:
        return os.path.getsize(path)
    except OSError:
        return None


def _check_live_geometry(state, slot, drive, path):
    """Refuse a live floppy swap the drive's geometry cannot serve.

    A floppy drive's geometry is fixed when the backend attaches it at
    launch, and a live ``change`` does not revise it — so a medium of
    a different size reaches the guest as read and write errors rather
    than as a new disk. Reliquary did not choose that geometry, so it
    says what it cannot do instead of producing a broken drive (P11).
    Proven on QEMU/DOS, milestone 9's transport spike.
    """
    if drive.get("medium") != "floppy":
        return
    launch = drive.get("launch-size")
    size = _medium_size(path)
    if launch is None:
        raise PreflightError(
            f"{slot} was empty when machine {state['id']} started, so "
            "the backend chose the drive's geometry and a live insert "
            "cannot change it; stop the machine, insert this medium, "
            "and start again. After that, live swaps of the same size "
            "work")
    if size is not None and size != launch:
        raise PreflightError(
            f"{slot} was launched with a {launch}-byte medium and this "
            f"one is {size} bytes; a live swap keeps the drive's "
            "geometry, so the guest would see read and write errors. "
            "Build every round's image at the launched size, or stop "
            "the machine to change it")


def _anonymous_local(file):
    """The path an ``insert_media(file=)`` mounts, or fail closed.

    ``--file`` mounts an **anonymous** ``local`` + ``use`` media (U20):
    mutable, unverified, attached in place. It has no catalog name, no
    ``sha256`` to pin, and reliquary never copies it — the consumer
    owns the image it just built and is free to rebuild it for the
    next round.
    """
    path = os.path.abspath(os.fspath(file))
    if os.path.isdir(path):
        raise StaticError(
            f"{path} is a directory; --file mounts an image file. A "
            "directory reaches a guest as a declared media whose "
            "location is that directory, which is stopped-only")
    if not os.path.isfile(path):
        raise PreflightError(f"no such image file: {path}")
    return path


def insert_media(machine_id, slot, media=None, *, file=None, context=None,
                 events=None, cancelled=None):
    """Insert a medium into a floppy or cdrom slot.

    Exactly one of ``media`` (a defined media item, fetched and
    hash-verified) or ``file`` (an anonymous ``local`` + ``use``
    image, mounted in place, mutable and unverified — U20's live
    iteration transport).

    Hard-disk slots are rejected.  The slot must already exist in
    the machine's state — drives are guest-visible hardware the
    blueprint declares, so ``insert`` never creates one.  Running or
    stopped: on a running machine the medium is changed live over QMP
    (a change the guest observes); on a stopped machine it is present
    at the next ``start``.  The change persists in ``machine.json``
    across stop/start — the machine diverges from its blueprint until a
    later ``insert``/``eject`` or ``apply``.
    """
    if (media is None) == (file is None):
        raise StaticError(
            "insert-media takes a media name or --file <path>, "
            "not both and not neither")
    with _machine_lock(machine_id, context):
        state = _reconcile_phase(machine_id, context)
        _removable_drive(state, slot)
        path = (_anonymous_local(file) if file is not None
                else _fetch(media, context, events=events,
                            cancelled=cancelled))
        drive = state["drives"][slot]
        if state.get("phase") == "running":
            _check_live_geometry(state, slot, drive, path)
            _change_media_live(machine_id, slot, path, context)
        drive["path"] = path
        drive["media"] = media
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
            raise PreflightError(
                f"machine {machine_id} must be stopped "
                f"to change boot order (phase: {phase})")
        drives = state.get("drives", {})
        if not isinstance(boot_keys, (list, tuple)) or not boot_keys:
            raise StaticError("boot order requires at least one drive key")
        normalized = []
        seen = set()
        for index, key in enumerate(boot_keys):
            if not isinstance(key, str) or not key:
                raise StaticError(
                    f"boot[{index}] must be a non-empty drive key")
            if key not in drives:
                raise PreflightError(
                    f"boot[{index}] references undeclared drive {key}")
            if key in seen:
                raise StaticError(f"boot contains duplicate drive {key}")
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


# -- machine variables -------------------------------------------
#
# The script -> host scalar channel (U14/U20): a script `set`s a
# variable, any process reads it with `get-machine-var`. It lives in
# `machine.json` under the operation lock, and `start` clears it, so a
# variable always reports what the current boot produced.

_VARIABLE_KEY = re.compile(r"[A-Za-z][A-Za-z0-9._-]*\Z")
_RESERVED_VARIABLE = ("rlq", "reliquary")


def check_variable_key(key):
    """Validate a machine-variable key, or raise ``ValueError``.

    The property key rules, for the same reason: the ``rlq`` and
    ``reliquary`` namespaces stay reliquary's, so a consumer's own
    names can never collide with one the project later introduces.
    """
    if not isinstance(key, str) or not key:
        raise StaticError("a machine-variable key is required")
    if not _VARIABLE_KEY.match(key):
        raise StaticError(
            f"invalid machine-variable key {key!r}: letter-initial, "
            "then letters, digits, dot, dash, or underscore")
    if key.split(".", 1)[0].lower() in _RESERVED_VARIABLE:
        raise StaticError(
            f"the {key.split('.', 1)[0]!r} namespace is reserved: {key!r}")
    return key


def set_machine_var(machine_id, key, value, *, context=None):
    """Record a machine variable on a machine, in any phase.

    Its world-facing spelling is the script ``set`` verb — the
    scripting language is a primary interface, so this capability is
    reachable without a command of its own. ``value`` is text;
    reliquary attaches no meaning to it (G2, P18).
    """
    check_variable_key(key)
    if not isinstance(value, str):
        raise StaticError(
            f"a machine variable holds text; {key!r} got "
            f"{type(value).__name__}")
    with _machine_lock(machine_id, context):
        state = load_machine_state(machine_id, context)
        variables = dict(state.get("variables") or {})
        variables[key] = value
        state["variables"] = variables
        _write_state(machine_id, state, context)


def get_machine_var(key, *, machine=None, blueprint=None, context=None):
    """Read one machine variable — ``None`` when it is not set.

    A query: valid in any phase, touching nothing. An unset variable
    and a machine that never ran read the same, which is what makes
    polling a consumer-authored readiness script (P18) a plain loop.
    """
    check_variable_key(key)
    machine_id = resolve_machine(
        machine=machine, blueprint=blueprint, context=context)
    state = load_machine_state(machine_id, context)
    return (state.get("variables") or {}).get(key)


def exec(command, *, machine=None, blueprint=None, timeout=120,
         context=None):
    """Run one command in a running guest and return its output.

    The run family's one-shot member: like ``run_script`` it drives
    the machine and **returns its output** to the caller, storing
    nothing (D36). The output is the text the command left on the
    guest's screen, as a tuple of rows — reliquary reads no meaning
    into it (G2), and a caller wanting structure retrieves a file
    instead (:func:`get_file`) or reads a machine variable.

    The platform workflow owns command syntax and completion
    detection, so anything but DOS fails closed rather than
    borrowing DOS assumptions.

    (The name shadows the Python builtin inside this module, which is
    the price of the twin-name identity rule: the CLI command *is*
    ``exec``. Nothing here calls the builtin.)
    """
    from .interaction_agentless import AgentlessGuestExec
    from .machine import Machine

    machine_id = resolve_machine(
        machine=machine, blueprint=blueprint, context=context)
    state = load_machine_state(machine_id, context)
    platform = state.get("platform")
    if platform != "dos":
        raise PreflightError(
            f"exec is not implemented for platform {platform!r}; DOS "
            "is the delivered workflow")
    phase = state.get("phase")
    if phase != "running":
        raise PreflightError(
            f"machine {machine_id} is not running (phase: {phase}); "
            f"start it first: rlq start-machine --machine {machine_id}")
    machine_home = machine_dir_path(machine_id, context)
    vm = read_vm_state(machine_home)
    if vm is None:
        raise PreflightError(
            f"machine {machine_id} is running but has no recorded VM "
            "identity")
    return AgentlessGuestExec(
        Machine(vm["port"], machine_home)).execute(command, timeout)


# -- in-band file exchange ---------------------------------------

def _addressing(platform):
    """The platform module that maps guest addresses to drives.

    Guest paths are guest knowledge, so each platform workflow owns
    its own mapping (P17), built from declared facts only — never by
    inspecting a guest (P10). Anything but DOS fails closed rather
    than borrowing DOS assumptions.
    """
    if platform != "dos":
        raise PreflightError(
            f"in-band file exchange is not implemented for platform "
            f"{platform!r}; DOS is the delivered workflow")
    from . import platform_dos
    return platform_dos


def _host_path(machine_id, address, context):
    """Resolve a guest-terms address to a host path under a vvfat drive.

    The whole of P17 in one function: the caller writes ``A:\\FOO.TXT``
    and never learns which host directory backs it. Stopped-only, and
    a drive that is not a host directory fails closed naming the gap
    (P11) — an image drive has no in-band route until one is built.
    """
    state = load_machine_state(machine_id, context)
    phase = state.get("phase")
    if phase != "ready":
        raise PreflightError(
            f"machine {machine_id} must be stopped for in-band file "
            f"exchange (phase: {phase}); the backend snapshots a host "
            "directory when the drive is attached, so a running "
            "machine would neither see a put nor have flushed a get")
    platform = _addressing(state.get("platform"))
    drives = state.get("drives", {})
    letters = platform.drive_letters(drives)
    letter, segments = platform.split_address(address)
    key = letters.get(letter)
    if key is None:
        known = ", ".join(f"{name}: ({letters[name]})"
                          for name in sorted(letters)) or "none"
        # Two different failures wear one shape, and saying "no such
        # drive" for the second would be a lie: the machine may well
        # have a drive there, and reliquary simply cannot say which
        # letter it took (P17). Reading volume layout off the images
        # would let it -- that is unbuilt, not forbidden.
        undetermined = platform.undetermined_letters(drives)
        if undetermined:
            raise PreflightError(
                f"{address}: reliquary cannot determine which drive "
                f"is {letter}: on this machine. Its letter depends on "
                "how many volumes the disks before it carry, which a "
                "blueprint does not declare and reliquary does not "
                "yet read from the drive images. "
                f"Determined letters: {known}. Undetermined drives: "
                f"{', '.join(undetermined)} — address one of the "
                "determined letters, or give the exchange drive a "
                "floppy slot, whose letter no disk can shift")
        raise PreflightError(
            f"{address}: the machine declares no drive at {letter}:; "
            f"declared letters: {known}")
    root = drives[key].get("path")
    if not root or not os.path.isdir(root):
        raise PreflightError(
            f"{address}: drive {key} ({letter}:) is an image, not a "
            "host directory; in-band file exchange needs a "
            "directory-source drive there")
    resolved = os.path.abspath(os.path.join(root, *segments))
    root = os.path.abspath(root)
    if os.path.commonpath([root, resolved]) != root:
        raise PreflightError(
            f"{address} escapes drive {key}; a guest address stays "
            "inside its own drive")
    return resolved


def put_file(source, destination, *, machine=None, blueprint=None,
             context=None):
    """Copy a host file into the guest, addressed in the guest's terms.

    ``destination`` is what the guest's own user would write —
    ``A:\\RESULTS\\RUN.TXT`` on DOS — never a host path, an image, or
    a staging directory (P17). Stopped-only. Returns the guest address
    written, which is the address the guest will read it at.
    """
    machine_id = resolve_machine(
        machine=machine, blueprint=blueprint, context=context)
    origin = os.path.abspath(os.fspath(source))
    if not os.path.isfile(origin):
        raise PreflightError(f"no such file: {origin}")
    with _machine_lock(machine_id, context):
        target = _host_path(machine_id, destination, context)
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
        shutil.copyfile(origin, target)
    return destination


def get_file(source, destination, *, machine=None, blueprint=None,
             context=None):
    """Retrieve a guest file to the host, addressed in the guest's terms.

    ``source`` is the guest address; ``destination`` a host path. The
    counterpart of :func:`put_file`, and the U14 half that makes the
    retrieved file the caller's product. Stopped-only, so the guest's
    writes have been flushed. Returns the host path written.
    """
    machine_id = resolve_machine(
        machine=machine, blueprint=blueprint, context=context)
    target = os.path.abspath(os.fspath(destination))
    with _machine_lock(machine_id, context):
        origin = _host_path(machine_id, source, context)
        if not os.path.isfile(origin):
            raise PreflightError(
                f"the guest has no file at {source}")
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
        shutil.copyfile(origin, target)
    return target


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
            raise PreflightError(
                f"machine {machine_id} is running; "
                "stop it before destroying")
        if phase not in ("ready", "destroying", "creating"):
            raise PreflightError(
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
