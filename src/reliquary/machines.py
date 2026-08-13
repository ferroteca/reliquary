# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Machine materialization and cached-state management."""

import contextlib
import dataclasses
import hashlib
import json
import os
import re
import shutil
import time
from datetime import datetime, timezone

from . import acquire
from . import backends
from . import binding
from . import events as _events
from .acquire import fetch_media as _acquire_fetch
from .errors import (InternalError, PreflightError, ReliquaryError,
                     StaticError, WaitExpired)
from .home import machines_dir
from .library import codex_blueprint_available
# The substrate both halves of the machine layer stand on: ids and
# directories, the locks, machine.json, and selector resolution.
#
# **This module stays the machine layer's front door.** `machine_state`
# is the seam `machines` and `drives` share so neither has to import
# the other; it is not a second entrance. A consumer above the layer —
# the session veneer, the script runner, the media family — reaches
# every one of these through `machines`, which is why the names below
# that this module does not itself call are imported anyway. The one
# exception is `machine.py`, which takes `read_vm_state` from the
# substrate directly because importing this module would put the two
# back in a cycle.
from .interaction_agentless import AgentlessGuestExec
from .machine_handle import Machine
from .machine_state import (allocate_machine_id, backend_dir,
                            blueprint_alloc_lock, list_machines,
                            load_machine_state, machine_dir_path,
                            machine_disks_dir, machine_id_for,
                            machine_lock, machines_for_blueprint,
                            read_vm_state, resolve_machine,
                            split_machine_id, write_state)
# The drive layer: what a stopped machine's disks hold and how the
# guest names them. `start_machine` reads a disk's record at its
# first step, and that is the only edge — the drive layer stands on
# `machine_state`, never on the lifecycle. The verbs below it are
# re-exported for the same front-door reason as the substrate's.
from .drives import (describe_drives, get_file, get_files,
                     list_files, put_file, put_files,
                     read_drive_record, refresh_drives)
from .resolve import (load_namespace, location_property_keys,
                      resolve_media, resolve_media_plan)


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


_PLATFORM_MEMORY = {
    "dos": 16,
    "openbsd": 512,
    "win9x": 64,
    "winnt": 256,
}


def _default_control_planes(platform):
    """The platform's default control-plane policy.

    Every current platform defaults to agentless display — the
    universal, cooperation-free plane (blueprint-reference.md).
    Richer per-platform defaults arrive with the planes themselves.
    """
    return ["agentless-display"]


def _resolve_control_planes(machine):
    """The machine's control-plane policy, defaulted.

    Whether a plane can be honored is the backend's answer, not this
    module's: the policy becomes a requirement and the adapter's
    capability report judges it (P11).
    """
    return (list(machine.control_planes)
            or _default_control_planes(machine.platform))


def _backend_choice(machine):
    """Where the blueprint says this machine belongs, and how it said it.

    Three answers, in the order they are consulted. A declared
    ``backend`` **pins**. Failing that, ``backend-settings`` for
    **exactly one** backend narrows assignment to it: sections are the
    one place backend-specific configuration may appear, so a
    blueprint carrying exactly one has already said which backend it is
    written for, and walking past it to another that could never honor
    those settings would be assignment ignoring the blueprint. Two or
    more sections narrow nothing — each is inert until its backend
    wins, and the ordinary walk decides. **Presence is what narrows**,
    not content: an empty section names its backend just as a full one
    does.
    """
    if machine.backend is not None:
        return machine.backend, None, "declared"
    sections = sorted(machine.backend_settings)
    if len(sections) == 1:
        return None, sections[0], "backend-settings"
    return None, None, "priority walk"


def _requirements(machine, namespace):
    """What this blueprint asks of a backend, in the seam's vocabulary.

    Read off the whole machine — its control-plane policy, the media
    kinds and controllers its enabled drives declare, and the
    materialization mode of every media they name — because a backend
    is chosen for the machine and never for a drive.
    """
    planes = _resolve_control_planes(machine)
    media = []
    controllers = []
    modes = []
    for _key, drive in sorted(machine.drives.items()):
        if not drive.enabled:
            continue
        if drive.medium not in media:
            media.append(drive.medium)
        if drive.medium != "floppy":
            controller = drive.controller or "ide"
            if controller not in controllers:
                controllers.append(controller)
        item = _drive_media(drive, namespace)
        if item is not None and item.materialize not in modes:
            modes.append(item.materialize)
    return backends.Requirements(
        control_planes=tuple(planes), media=tuple(media),
        controllers=tuple(controllers), materialize=tuple(modes))


def _blueprint_digest(resolved, drives):
    """Digest the resolved blueprint snapshot (the machine baseline).

    Covers the resolved logical shape only — the per-drive cache
    ``path`` (environment-specific) and the recorded observations
    (``volumes``, ``geometry``, ``launch-size``: what a disk was
    *seen* to hold, not what the blueprint asked for) are excluded —
    so the same blueprint resolves to the same digest across homes
    and across boots, which is what ``apply`` compares against.
    """
    observed = {"path", "volumes", "geometry", "launch-size"}
    snapshot = dict(resolved)
    snapshot["drives"] = {
        key: {name: value for name, value in entry.items()
              if name not in observed}
        for key, entry in drives.items()
    }
    canonical = json.dumps(
        snapshot, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(
        canonical.encode("utf-8")).hexdigest()


def _drive_common(key, drive):
    """The medium/slot/controller fields common to every drive entry.

    A controller the assigned backend cannot wire was already refused
    at assignment, by name, against that backend's capability report.
    """
    entry = {"medium": drive.medium, "slot": drive.slot}
    if drive.medium != "floppy":
        entry["controller"] = drive.controller or "ide"
    return entry


def _materialize_drive(key, drive, adapter, disks_root, namespace, context,
                       properties=None, events=None, cancelled=None):
    """Materialize one enabled drive, returning its resolved state entry.

    The drive names a media (or is an empty removable slot); the media
    owns materialization. ``new`` is a fresh blank of its ``size``;
    ``use`` attaches the fetched payload directly (a directory payload
    renders as vvfat); ``difference``/``copy`` build a per-machine image
    over/of the fetched payload. Per-machine images live under
    ``disks/`` keyed by the media name, not the slot, so a media moving
    through a removable slot keeps its own image; the adapter names the
    file, since the native image format is its choice. The entry
    records the realized ``path`` plus the media name and mode.
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
            f"'use' (attach), not '{mode}'", rule_id="drive.cdrom-read-only")
    entry["media"] = media.name
    entry["materialize"] = mode
    if mode == "new":
        path = adapter.image_path(disks_root, _image_stem(media, key))
        adapter.create_image(path, mode="new", size=media.size)
        entry.update(size=media.size, path=path)
    elif mode == "use":
        entry["path"] = _acquire_fetch(
            media, namespace, context, properties=properties, events=events,
            cancelled=cancelled)
    elif mode in ("difference", "copy"):
        base_payload = _acquire_fetch(
            media, namespace, context, properties=properties, events=events,
            cancelled=cancelled)
        dest = adapter.image_path(disks_root, _image_stem(media, key))
        adapter.create_image(dest, mode=mode, base=base_payload)
        entry["path"] = dest
    else:
        raise InternalError(f"unknown materialize mode {mode!r} for {key}")
    return entry


def create(machine, namespace, *, context=None, blueprint_name="",
           source=None, number=None, properties=None, events=None,
           backend=None):
    """Materialize one machine from a parsed composed machine component.

    Assigns the backend (a declared one pins the choice; otherwise the
    priority walk takes the first available and capable one), creates
    the machine cache directory under
    ``cache/machines/<blueprint>-<n>/``, writes ``machine.json`` with
    the fully resolved configuration and its provenance
    (``blueprint-source``, ``blueprint-digest``, ``backend-id``), and
    materializes every enabled drive: a per-machine image under
    ``disks/`` for ``new``/``difference``/``copy`` media, the fetched
    payload attached in place for ``use``. ``source`` is the absolute
    path of the blueprint file this machine resolved from, recorded for
    selection scoping. The machine number is the lowest free
    non-negative integer for that blueprint, unless ``number`` pins a
    specific one (``recreate`` reuses the old id). ``backend``
    overrides the blueprint's backend field, pinning assignment the same
    way a declared ``backend`` does. Returns the generated machine id.
    """
    if not isinstance(blueprint_name, str) or not blueprint_name:
        raise StaticError("create requires a non-empty blueprint_name",
            rule_id="value.not-a-string")

    created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with blueprint_alloc_lock(blueprint_name, context):
        if number is None:
            machine_id = allocate_machine_id(blueprint_name, context)
        else:
            machine_id = machine_id_for(blueprint_name, number)
            if os.path.exists(machine_dir_path(machine_id, context)):
                raise PreflightError(
                    f"machine {machine_id} already exists",
                    rule_id="machine.already-exists")
        disks_root = machine_disks_dir(machine_id, context)
        os.makedirs(disks_root)
        # Mark the machine `creating` before materialization begins, so
        # an interrupted create is detectable and recoverable.
        write_state(machine_id, {
            "id": machine_id,
            "blueprint": blueprint_name,
            "created": created,
            "phase": "creating",
            "generation": 0,
        }, context)

    with machine_lock(machine_id, context):
        try:
            return _materialize_machine(
                machine, namespace, machine_id, blueprint_name, created,
                disks_root, source, context, properties, events, backend)
        except BaseException:
            # Roll back a failed create: the machine never reached a
            # usable phase, so its partial materialization is discarded.
            shutil.rmtree(
                machine_dir_path(machine_id, context), ignore_errors=True)
            raise


def _materialize_machine(machine, namespace, machine_id, blueprint_name,
                         created, disks_root, source, context,
                         properties=None, events=None, backend=None):
    # Assignment happens before anything is materialized, so a machine
    # nothing on this host can build costs no image work — and the
    # backend is fixed before the first image is written in its own
    # native format.
    control_planes = _resolve_control_planes(machine)
    if backend is not None:
        declared, narrowed = backend, None
    else:
        declared, narrowed, _source = _backend_choice(machine)
    backend = backends.assign(_requirements(machine, namespace),
                              declared=declared, narrowed=narrowed)
    adapter = backends.adapter(backend)
    # The section that applies is the assigned backend's, so this
    # follows assignment; the others are inert and stay unjudged, since
    # no adapter can speak for another's vocabulary.
    adapter.validate_settings(machine.backend_settings.get(backend))
    resolved_drives = {}
    for key, drive in sorted(machine.drives.items()):
        if not drive.enabled:
            # `enabled: false` removes the drive from the machine
            # entirely (blueprint-reference.md).
            continue
        resolved_drives[key] = _materialize_drive(
            key, drive, adapter, disks_root, namespace, context,
            properties, events)

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

    write_state(machine_id, state, context)
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
    keys = set()
    for drive in machine.drives.values():
        if not drive.enabled or drive.media is None:
            continue
        media = namespace.media.get(drive.media)
        if media is not None:
            keys.update(location_property_keys(media, namespace))
    if not keys:
        return {}
    return binding.bind_keys(
        keys, parameters=dict(machine.parameters), explicit=explicit,
        properties_file=properties_file, context=context,
        asker=binding.console_asker())


# --- the dry run -----------------------------------------------------
#
# *A dry run performs every step that costs nothing and commits
# nothing, stops at the first step that would, and reports what it
# would have done.* Two invariants carry it. It **leaves no state
# behind** — no machine directory, no ``machine.json``, no fetched
# payload, no seeded blueprint, no lock file — and its **return
# describes the run** rather than impersonating the run's output.
#
# It raises what a real create would raise, where a real create would
# raise it: a dry run whose verdict is "this would fail" fails, and
# the diagnostic is the answer. There are exactly two exceptions, and
# each is something a dry run specifically *cannot do* rather than a
# judgement about how bad a finding is:
#
#   1. It must not prompt, so a media location no concrete source
#      answers is reported unevaluated instead of asked for.
#   2. Under an explicit ``backend=`` the question is what *another*
#      host would do, so that backend's absence here is reported
#      rather than raised. Incapability still raises — that is the
#      answer to the question that was asked.


@dataclasses.dataclass(frozen=True)
class DryRun:
    """What an operation would do, having done none of it.

    The return of every ``dry_run=True`` call, and a **distinct type
    on purpose**: a dry create must not hand back something a caller
    can mistake for the real return — a machine id naming no machine,
    or ``None`` — because that makes misuse a confusing failure three
    layers down, where this makes it a ``TypeError`` at the call site.

    ``operation`` names the verb described, ``report`` is the
    printable human rendering, and ``plan`` is the operation's own
    document, which is the mapping ``--json`` serializes. Three
    fields are the whole type, so a second operation contributes a
    plan shape and no new field.
    """

    operation: str
    report: str
    plan: dict = dataclasses.field(default_factory=dict)


def _seed_hint(name):
    """The fix, where the shipped library holds this blueprint name.

    A deleted fallback should leave an instruction rather than a
    silence (P11, D88): nothing resolves out of the codex any more, so
    the refusal is where a user learns that seeding is the move. Empty
    when the library has no such name, since inventing a suggestion
    that would also fail is worse than saying nothing.

    (A dry run needs no namespace of its own now. It used to read a
    codex blueprint where it lay — the one path by which the library
    reached an operation unasked — and with that gone the dry and live
    halves resolve identically, which is what the rule always said.)
    """
    if codex_blueprint_available(name):
        return f"\nthe codex has one: rlq seed-blueprint {name}"
    return ""


def _describe_location_properties(machine, namespace, *, explicit=None,
                                  properties_file=None, context=None):
    """Name each location key's source without asking for any of them.

    The dry twin of :func:`_bind_location_properties`: a create binds
    these keys, prompting on a terminal for one nothing else answers,
    and a dry run must not — so it takes what the concrete sources
    give and reports the rest as the ask a real create would make.
    """
    keys = set()
    for drive in machine.drives.values():
        if not drive.enabled or drive.media is None:
            continue
        media = namespace.media.get(drive.media)
        if media is not None:
            keys.update(location_property_keys(media, namespace))
    if not keys:
        return binding.BoundProperties({}, {})
    return binding.describe_keys(
        keys, parameters=dict(machine.parameters), explicit=explicit,
        properties_file=properties_file, context=context)


def _record(entries, entry):
    """Append one media entry, a media two drives share appearing once."""
    if any(existing["name"] == entry["name"] for existing in entries):
        return
    entries.append(entry)


def _dry_payload(media, namespace, context, properties, entries):
    """Where this media's payload would come from, fetching nothing.

    Returns the path a create would attach or build over, or ``None``
    when the location cannot be rendered without asking.
    """
    needs = sorted(location_property_keys(media, namespace)
                   - set(properties or ()))
    if needs:
        _record(entries, {
            "name": media.name, "state": "unbound", "needs": needs,
            "source": None, "path": None, "sha256": None})
        return None
    plan = resolve_media_plan(media, namespace, properties)
    if plan is None:
        return None
    residency = acquire.residency(
        plan, media.name, acquire.payload_extension(media, plan), context)
    for entry in residency:
        _record(entries, entry)
    return residency[0]["path"] if residency else None


def _refuse_missing(entries):
    """Refuse a plan whose local payloads are not on the disk.

    A missing local file is an error a dry run can and should
    catch — a create hits it too, and a plan that cannot be executed
    must not report success (P11). It is raised **after** the whole
    plan is walked so every such media is named at once: a validator
    that stops at the first fault costs a fix-and-rerun for each one,
    and enumerating them is exactly what this pass is good at.
    Nothing else is collected this way, so every other refusal still
    lands where a create's would.
    """
    missing = [entry for entry in entries
               if entry["state"] == "local-missing"]
    if not missing:
        return
    named = "\n".join(f"  media {entry['name']!r} is declared at "
                      f"{entry['path']}, but nothing is there"
                      for entry in missing)
    raise PreflightError(
        "this blueprint cannot be built as it stands:\n" + named
        + "\nRestore the files, or edit the blueprint that declares "
          "them to name where they live now",
        rule_id="media.file-missing")


def _dry_drive(key, drive, adapter, disks_root, namespace, context,
               properties, entries):
    """One drive's resolved plan, materializing nothing.

    Mirrors :func:`_materialize_drive` decision for decision — the
    same refusals in the same order — recording what it would have
    written in place of writing it. ``adapter.image_path`` is
    composition, not creation, so asking where an image would land
    costs nothing and says exactly what a create would do.
    """
    entry = dict(key=key, **_drive_common(key, drive))
    media = _drive_media(drive, namespace)
    if media is None:
        entry.update(media=None, materialize=None, path=None)
        return entry
    mode = media.materialize
    if drive.medium == "cdrom" and mode != "use":
        raise StaticError(
            f"drives.{key}: a cdrom is read-only, so its media must "
            f"'use' (attach), not '{mode}'", rule_id="drive.cdrom-read-only")
    entry["media"] = media.name
    entry["materialize"] = mode
    if mode == "new":
        entry.update(size=media.size,
                     path=adapter.image_path(disks_root,
                                             _image_stem(media, key)))
        return entry
    payload = _dry_payload(media, namespace, context, properties, entries)
    if mode == "use":
        entry["path"] = payload
    elif mode in ("difference", "copy"):
        entry["base"] = payload
        entry["path"] = adapter.image_path(disks_root,
                                           _image_stem(media, key))
    else:
        raise InternalError(f"unknown materialize mode {mode!r} for {key}")
    return entry


def _dry_backend(machine, namespace, backend):
    """The backend a create would land on, and why — plus its probe.

    With no ``backend`` this is assignment itself: a declared one
    pins, a lone ``backend-settings`` section narrows, otherwise the
    priority walk. With one it is the other
    question — whether the blueprint would work *there* — so
    availability is reported and only capability decides (P11).
    """
    requirements = _requirements(machine, namespace)
    if backend is None:
        declared, narrowed, source = _backend_choice(machine)
        assigned = backends.assign(requirements, declared=declared,
                                   narrowed=narrowed)
        return assigned, source, None
    verdict = backends.evaluate(backend, requirements)
    if verdict.unmet:
        raise PreflightError(
            f"backend {backend!r} cannot provide: "
            f"{', '.join(verdict.unmet)}",
            rule_id="machine.backend-incapable")
    return backend, "--backend", verdict


def _dry_create(machine, namespace, *, context, blueprint_name, source,
                number, bound, backend):
    """Evaluate one create, committing none of it."""
    if number is None:
        # The directory is read; the allocation lock is not taken,
        # because taking it would create `.locks/` — state left
        # behind — and a predicted number is a prediction either way.
        machine_id = allocate_machine_id(blueprint_name, context)
        numbering = "lowest free"
    else:
        machine_id = machine_id_for(blueprint_name, number)
        if os.path.exists(machine_dir_path(machine_id, context)):
            raise PreflightError(
                f"machine {machine_id} already exists",
                rule_id="machine.already-exists")
        numbering = "pinned"
    assigned, chosen, verdict = _dry_backend(machine, namespace, backend)
    adapter = backends.adapter(assigned)
    # A create would refuse an unhonorable section, so a dry run does
    # too, and in the same place — the settings are authored input,
    # judged identically whether or not the backend is on this host.
    adapter.validate_settings(machine.backend_settings.get(assigned))
    disks_root = machine_disks_dir(machine_id, context)
    entries = []
    drives = [
        _dry_drive(key, drive, adapter, disks_root, namespace, context,
                   bound.values, entries)
        for key, drive in sorted(machine.drives.items()) if drive.enabled]
    _refuse_missing(entries)
    memory = machine.memory
    if memory is None:
        memory = _PLATFORM_MEMORY.get(machine.platform, 16)
    plan = {
        "blueprint": blueprint_name,
        "blueprint-source": (os.path.abspath(os.fspath(source))
                             if source is not None else None),
        "machine": machine_id,
        "machine-number": numbering,
        "machine-dir": machine_dir_path(machine_id, context),
        "backend": assigned,
        "backend-source": chosen,
        "platform": machine.platform,
        "memory": memory,
        "cpus": machine.cpus if machine.cpus is not None else 1,
        "boot": list(machine.boot),
        "control-planes": _resolve_control_planes(machine),
        "drives": drives,
        "media": entries,
        "properties": dict(bound.sources),
    }
    if verdict is not None:
        plan["backend-available"] = verdict.available
        plan["backend-detail"] = verdict.detail
    return DryRun(operation="create-machine", report=_dry_report(plan),
                  plan=plan)


def _drive_line(drive):
    """One drive's line in the report: what it is, and where it lands."""
    where = f"{drive['medium']} slot {drive['slot']}"
    if drive.get("controller"):
        where += f" {drive['controller']}"
    if drive["materialize"] is None:
        # An empty removable slot. The test is the mode and not the
        # media name, because the anonymous inline blank has no name
        # either and is emphatically not an empty slot.
        return f"  {drive['key']} ({where}): empty"
    what = f"{drive['media'] or '(inline)'} {drive['materialize']}"
    if drive.get("size"):
        what += f" {drive['size']}"
    target = drive.get("path") or "(unresolved)"
    return f"  {drive['key']} ({where}): {what} -> {target}"


def _media_line(entry):
    """One media's line: its residency, and what it resolved to."""
    if entry["state"] == "unbound":
        needs = ", ".join("${" + key + "}" for key in entry["needs"])
        return f"  {entry['name']}: unbound -- needs {needs}"
    line = f"  {entry['name']}: {entry['state']} -- {entry['source']}"
    if entry.get("mirrors"):
        line += f" (+{entry['mirrors'] - 1} mirrors)"
    return line


def _dry_report(plan):
    """Render a create's dry run the way the CLI prints it."""
    lines = [f"create-machine {plan['blueprint']} --dry-run", ""]
    lines.append(f"machine: {plan['machine']} ({plan['machine-number']})")
    lines.append(f"directory: {plan['machine-dir']}")
    lines.append(f"backend: {plan['backend']} ({plan['backend-source']})")
    if plan.get("backend-available") is False:
        lines.append(f"  not available on this host: "
                     f"{plan['backend-detail']}")
        lines.append("  capability alone was judged, which is what "
                     "--backend asks")
    lines.append(f"platform: {plan['platform']}")
    lines.append(f"memory: {plan['memory']}")
    lines.append(f"cpus: {plan['cpus']}")
    if plan["boot"]:
        lines.append("boot: " + ", ".join(plan["boot"]))
    lines.append("control planes: " + ", ".join(plan["control-planes"]))
    if plan["drives"]:
        lines.append("drives:")
        lines.extend(_drive_line(drive) for drive in plan["drives"])
    if plan["media"]:
        lines.append("media:")
        lines.extend(_media_line(entry) for entry in plan["media"])
    if plan["properties"]:
        lines.append("properties:")
        for key in sorted(plan["properties"]):
            lines.append(f"  {key}: {plan['properties'][key]}")
    lines.append("")
    lines.append("nothing was created.")
    return "\n".join(lines) + "\n"


def create_machine(name, *, context=None, number=None, properties=None,
                   properties_file=None, events=None, dry_run=False,
                   backend=None):
    """Load ``blueprints/<name>.rlqb`` and materialize one machine.

    A blueprint the home does not contain is seeded from the
    built-in library on this first reference, along with the media
    definitions and scripts it references (never overwriting user
    files). ``number`` pins the machine number (``recreate`` reuses
    the old id); omitted, the lowest free number is allocated.
    ``properties`` / ``properties_file`` bind any ``${key}`` a media
    location references, before materialization.

    ``dry_run=True`` materializes nothing and returns a
    :class:`DryRun` describing what a create would do — the machine
    id it would allocate, the backend it would land on, each drive's
    resolved plan, and where every media would come from. It leaves
    no state behind (nothing is seeded, fetched, locked or written)
    and never prompts. ``backend`` overrides the blueprint's
    ``backend`` field, pinning assignment the same way a declared
    one does: it must be available and capable, and it fails closed
    on either count. With ``dry_run`` it asks the other question —
    whether the blueprint would work *there* — so absence is
    reported rather than raised (P11).
    """
    if dry_run:
        namespace = load_namespace(context)
        if name not in namespace.machines:
            raise PreflightError(
                f"no machine blueprint named {name!r} in the resolution "
                f"source{_seed_hint(name)}", rule_id="blueprint.unknown")
        machine = namespace.machines[name]
        return _dry_create(
            machine, namespace, context=context, blueprint_name=name,
            source=namespace.origin.get(("machine", name)), number=number,
            bound=_describe_location_properties(
                machine, namespace, explicit=properties,
                properties_file=properties_file, context=context),
            backend=backend)
    # The blueprints directory is the sole source: nothing is seeded on
    # first reference, and the codex reaches a tree only when
    # `seed-blueprint` is asked to put it there (D88). A name the codex
    # ships is named in the refusal rather than quietly supplied.
    namespace = load_namespace(context)
    if name not in namespace.machines:
        raise PreflightError(
            f"no machine blueprint named {name!r} in the resolution "
            f"source{_seed_hint(name)}",
            rule_id="blueprint.unknown")
    machine = namespace.machines[name]
    source = namespace.origin.get(("machine", name))
    bound = _bind_location_properties(
        machine, namespace, explicit=properties,
        properties_file=properties_file, context=context)
    return create(machine, namespace, context=context, blueprint_name=name,
                  source=source, number=number, properties=bound,
                  events=events, backend=backend)


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
        raise StaticError(f"cannot parse machine id {machine_id!r}",
            rule_id="machine.id-malformed")
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


def _reconcile_drives(machine, namespace, old_drives, adapter, disks_root,
                      context, properties=None, events=None):
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
                key, drive, adapter, disks_root, namespace, context,
                properties, events)
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
                "instead", rule_id="drive.already-materialized")
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
    with machine_lock(machine_id, context):
        state = _reconcile_phase(machine_id, context)
        phase = state.get("phase")
        if phase != "ready":
            raise PreflightError(
                f"machine {machine_id} must be stopped to apply "
                f"(phase: {phase})", rule_id="machine.must-be-stopped")
        blueprint_name = state["blueprint"]
        namespace = load_namespace(context)
        if blueprint_name not in namespace.machines:
            raise PreflightError(
                f"no machine blueprint named {blueprint_name!r} to apply",
                rule_id="blueprint.unknown")
        parsed = namespace.machines[blueprint_name]
        path = namespace.origin.get(("machine", blueprint_name))
        # Checked before the drives are reconciled, so a refused apply
        # leaves the machine as it was. A machine keeps the backend it
        # was assigned — its images are in that backend's own format —
        # so apply judges the new blueprint against that one rather
        # than re-running assignment; moving backends is `recreate`.
        backend = state.get("backend") or "qemu"
        if parsed.backend is not None and parsed.backend != backend:
            raise PreflightError(
                f"the blueprint now pins backend {parsed.backend!r} and "
                f"machine {machine_id} was materialized on {backend!r}; "
                "apply cannot move a machine between backends — "
                "recreate it instead",
                rule_id="machine.backend-changed")
        adapter = backends.adapter(backend)
        control_planes = _resolve_control_planes(parsed)
        missing = adapter.unmet(_requirements(parsed, namespace))
        if missing:
            raise PreflightError(
                f"machine {machine_id} is on backend {backend!r}, which "
                f"cannot provide: {', '.join(missing)}",
                rule_id="machine.backend-incapable")
        # Checked here with the capability gate, before any drive is
        # touched: an edited section this backend cannot honor leaves
        # the machine exactly as it was.
        adapter.validate_settings(parsed.backend_settings.get(backend))

        bound = _bind_location_properties(
            parsed, namespace, explicit=properties,
            properties_file=properties_file, context=context)
        disks_root = machine_disks_dir(machine_id, context)
        new_drives = _reconcile_drives(
            parsed, namespace, state.get("drives", {}), adapter, disks_root,
            context, bound, events)

        memory = parsed.memory
        if memory is None:
            memory = _PLATFORM_MEMORY.get(parsed.platform, 16)
        resolved = {
            "platform": parsed.platform,
            "backend": backend,
            "memory": memory,
            "cpus": parsed.cpus if parsed.cpus is not None else 1,
            "boot": list(parsed.boot),
            "name": parsed.name,
            "description": parsed.description,
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
        write_state(machine_id, state, context)
    return machine_id


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
    write_state(machine_id, state, context)
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
    write_state(machine_id, state, context)


def _complete_stop(machine_id, context=None):
    """Power off the owned VM and reconcile phase + VM identity.

    On success the machine returns to ``ready`` and its ``vm`` section
    is cleared, written together. If the adapter's stop fails closed,
    the phase is reconciled without lying: a machine whose ``vm``
    section is already gone becomes ``ready``, while one still recorded
    (our VM may yet be running — a stuck port or an identity mismatch)
    restores ``running``; either way the error propagates.
    """
    state = load_machine_state(machine_id, context)
    vm = state.get("vm")
    backend = (vm or {}).get("backend") or state.get("backend") or "qemu"
    try:
        backends.adapter(backend).stop(vm)
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
            "has been rolled back; create it again with create-machine",
            rule_id="machine.interrupted-creation")
    if phase == "destroying":
        shutil.rmtree(machine_home, ignore_errors=True)
        raise PreflightError(
            f"machine {machine_id} was interrupted during destruction "
            "and has now been removed",
            rule_id="machine.interrupted-destruction")
    if phase == "stopping":
        _complete_stop(machine_id, context)
        return load_machine_state(machine_id, context)
    raise InternalError(
        f"machine {machine_id} is in an unrecognized phase {phase!r}")


def start_machine(machine_id, *, display=False, context=None, events=None,
                  cancelled=None):
    """Start a ready machine and return its id.

    Under the per-machine lock, reconciles any interrupted phase,
    re-verifies every media hash, hands the resolved state to the
    machine's own backend adapter to launch, and records phase
    ``running`` with the identity the adapter returns. Machine
    variables are cleared here: a variable reports what *this* boot
    produced, never what a previous one left behind.
    """
    with machine_lock(machine_id, context):
        state = _reconcile_phase(machine_id, context)
        phase = state.get("phase")
        if phase == "running":
            raise PreflightError(
                f"machine {machine_id} is already running",
                rule_id="machine.already-running")
        if phase != "ready":
            raise PreflightError(
                f"machine {machine_id} cannot start "
                f"(phase: {phase})", rule_id="machine.phase-cannot-start")

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
        # The drive record is refreshed here, as the first step of a
        # start and before the backend is engaged (D83): what the
        # guest is about to boot from is read off each disk, so the
        # record a running machine's `describe-drives` answers from
        # is this boot's own starting state. An unreadable disk
        # records the refusal rather than failing the start — the
        # machine may boot it fine; only at-rest access refuses.
        for key, drive in sorted(drives.items()):
            if drive.get("medium") == "hdd":
                drive["geometry"] = read_drive_record(
                    state.get("backend") or "qemu", drive, key)[0]
        # A recorded volume count belongs to one boot, and is dropped
        # even though the record above was just read: a guest can
        # repartition its disk and can only do it while running, so
        # addressing after this boot must re-read — which refreshes
        # the record with it (D78). Dropped here rather than at stop,
        # so an interrupted run cannot leave a stale one behind.
        for drive in drives.values():
            drive.pop("volumes", None)
        state["drives"] = drives
        # A machine variable belongs to one boot: a script `set` it
        # while the guest ran, so the next start starts empty.
        state.pop("variables", None)
        write_state(machine_id, state, context)

        if state.get("memory") is None:
            state["memory"] = _PLATFORM_MEMORY.get(state.get("platform"), 16)
        backend = state.get("backend") or "qemu"
        adapter = backends.adapter(backend)
        probe = adapter.discover()
        if not probe.available:
            raise PreflightError(
                f"machine {machine_id} was materialized on backend "
                f"{backend!r}, which is not available on this host: "
                f"{probe.detail}", rule_id="machine.backend-unavailable")
        _events.note(events, _events.RUN_PREFLIGHT,
                     f"using {backend}: {probe.executable}",
                     backend=backend,
                     executable=probe.executable,
                     **{"control-planes": state.get("control-planes") or []})

        # The backend's own artifacts (QEMU's captured stderr log) live
        # in the machine's backend subdirectory; the adapter returns the
        # verified VM identity and machines.py persists it into
        # machine.json atomically with the running phase, so the two
        # never disagree.
        artifacts_dir = backend_dir(machine_id, backend, context)
        vm = adapter.start(
            state, machine_dir=machine_dir_path(machine_id, context),
            backend_dir=artifacts_dir, display=display,
            current=state.get("vm"))
        try:
            fresh = load_machine_state(machine_id, context)
            fresh["vm"] = vm
            fresh["phase"] = "running"
            fresh["generation"] = fresh.get("generation", 0) + 1
            write_state(machine_id, fresh, context)
        except BaseException:
            # The VM came up but its identity could not be recorded;
            # stop it rather than orphan an unrecorded process.
            with contextlib.suppress(Exception):
                adapter.stop(vm)
            raise
        return machine_id


def stop_machine(machine_id, context=None):
    """Stop a running machine and return it to phase ``ready``.

    Under the per-machine lock: reconciles any interrupted phase
    (an already-completed stop returns quietly), records the
    transitional ``stopping`` phase, then powers off the owned VM.
    """
    with machine_lock(machine_id, context):
        state = _reconcile_phase(machine_id, context)
        phase = state.get("phase")
        if phase == "ready":
            # A reconciled interrupted stop already returned it here.
            return
        if phase != "running":
            raise PreflightError(
                f"machine {machine_id} is not running "
                f"(phase: {phase})",
                rule_id="machine.not-running")
        _write_phase(machine_id, "stopping", context, bump=True)
        _complete_stop(machine_id, context)


_REMOVABLE_MEDIA = {"floppy", "cdrom"}


def _removable_drive(state, slot):
    """Return the mutable state entry for a removable drive slot."""
    drive = state.get("drives", {}).get(slot)
    if drive is None:
        raise PreflightError(
            f"machine {state['id']} declares no "
            f"drive {slot}", rule_id="machine.slot-not-declared")
    if drive.get("medium") not in _REMOVABLE_MEDIA:
        raise PreflightError(
            f"{slot} is not a removable drive slot",
            rule_id="machine.slot-not-removable")
    return drive


def _change_media_live(machine_id, slot, path, context):
    """Change a removable drive's medium on a running machine.

    The medium is swapped through the machine's identity-verified
    backend session, against the drive's launch id (the slot key), so
    the change the guest sees and the change persisted to the state
    stay one operation.
    """
    machine_home = machine_dir_path(machine_id, context)
    if read_vm_state(machine_home) is None:
        raise PreflightError(
            f"machine {machine_id} is running but has no recorded VM "
            "identity", rule_id="machine.no-vm-identity")
    with Machine(machine_home).session() as session:
        session.change_medium(slot, path)


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
            "work", rule_id="drive.live-insert-geometry")
    if size is not None and size != launch:
        raise PreflightError(
            f"{slot} was launched with a {launch}-byte medium and this "
            f"one is {size} bytes; a live swap keeps the drive's "
            "geometry, so the guest would see read and write errors. "
            "Build every round's image at the launched size, or stop "
            "the machine to change it", rule_id="drive.live-swap-size")


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
            "location is that directory, which is stopped-only",
            rule_id="value.not-an-image-file")
    if not os.path.isfile(path):
        raise PreflightError(f"no such image file: {path}",
            rule_id="media.file-missing")
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
            "not both and not neither", rule_id="media.name-or-file")
    with machine_lock(machine_id, context):
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
        write_state(machine_id, state, context)


def eject_media(machine_id, slot, *, context=None):
    """Empty a declared removable slot, persisting the change.

    The drive itself remains — the blueprint alone defines machine
    topology.  Running or stopped, as for :func:`insert_media`: on a
    running machine the medium is ejected live over QMP; on a stopped
    machine the next ``start`` presents it without a medium.
    """
    with machine_lock(machine_id, context):
        state = _reconcile_phase(machine_id, context)
        _removable_drive(state, slot)
        if state.get("phase") == "running":
            _change_media_live(machine_id, slot, None, context)
        drive = state["drives"][slot]
        drive["media"] = None
        drive["materialize"] = None
        drive["path"] = None
        state["generation"] = state.get("generation", 0) + 1
        write_state(machine_id, state, context)


def set_boot_order(machine_id, boot_keys, *, context=None):
    """Persist a new boot order on a stopped machine.

    Every key must name a drive the machine already declares.
    Duplicates are rejected.  The change lives in ``machine.json`` and
    takes effect on the next ``start``; the machine diverges from its
    blueprint until ``apply`` (or another ``set_boot_order``) restores
    it.
    """
    with machine_lock(machine_id, context):
        state = _reconcile_phase(machine_id, context)
        phase = state.get("phase")
        if phase != "ready":
            raise PreflightError(
                f"machine {machine_id} must be stopped "
                f"to change boot order (phase: {phase})",
                rule_id="machine.must-be-stopped")
        drives = state.get("drives", {})
        if not isinstance(boot_keys, (list, tuple)) or not boot_keys:
            raise StaticError("boot order requires at least one drive key",
                rule_id="drive.boot-empty")
        normalized = []
        seen = set()
        for index, key in enumerate(boot_keys):
            if not isinstance(key, str) or not key:
                raise StaticError(
                    f"boot[{index}] must be a non-empty drive key",
                    rule_id="drive.boot-key-empty")
            if key not in drives:
                raise PreflightError(
                    f"boot[{index}] references undeclared drive {key}",
                    rule_id="drive.boot-undeclared")
            if key in seen:
                raise StaticError(f"boot contains duplicate drive {key}",
                    rule_id="drive.boot-duplicate")
            seen.add(key)
            normalized.append(key)
        state["boot"] = normalized
        state["generation"] = state.get("generation", 0) + 1
        write_state(machine_id, state, context)


def mark_stopped(machine_id, context=None):
    """Reconcile the phase of a machine whose QEMU process has gone.

    Used when the guest powers itself off (the script observed
    ``stopped``): the phase returns to ``ready`` and the stale ``vm``
    section is cleared, written together.  A machine not in phase
    ``running`` is left untouched.
    """
    with machine_lock(machine_id, context):
        state = load_machine_state(machine_id, context)
        if state.get("phase") != "running":
            return
        state.pop("vm", None)
        state["phase"] = "ready"
        state["generation"] = state.get("generation", 0) + 1
        write_state(machine_id, state, context)


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
        raise StaticError("a machine-variable key is required",
            rule_id="name.variable-empty")
    if not _VARIABLE_KEY.match(key):
        raise StaticError(
            f"invalid machine-variable key {key!r}: letter-initial, "
            "then letters, digits, dot, dash, or underscore",
            rule_id="name.variable-charter")
    if key.split(".", 1)[0].lower() in _RESERVED_VARIABLE:
        raise StaticError(
            f"the {key.split('.', 1)[0]!r} namespace is reserved: {key!r}",
            rule_id="name.variable-reserved-namespace")
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
            f"{type(value).__name__}", rule_id="value.not-a-string")
    with machine_lock(machine_id, context):
        state = load_machine_state(machine_id, context)
        variables = dict(state.get("variables") or {})
        variables[key] = value
        state["variables"] = variables
        write_state(machine_id, state, context)


#: How often :func:`wait_machine_var` re-reads, and how long it waits
#: by default. The read is a small JSON file under no lock, so the
#: interval is about not spinning rather than about cost.
_VAR_POLL = 1.0
_VAR_TIMEOUT = 120.0


def wait_machine_var(key, value=None, *, machine=None, blueprint=None,
                     timeout=_VAR_TIMEOUT, interval=_VAR_POLL,
                     context=None):
    """Wait until a machine variable arrives, and return it.

    The polling half of the value channel, for the case
    ``run_script(expect=)`` cannot serve: **the setter is somebody
    else.** A blocking run leaves its variables final by the time it
    returns, so a wait after one can never poll — but a caller running
    that same blocking form on another thread, or following a run it
    did not start, has a variable that genuinely arrives later, and
    the loop it would otherwise write by hand is this (D90).

    ``value`` is the value to wait *for*; omitted, any value will do,
    so the readiness idiom — a script whose last step is ``set
    ready``, and a driver that waits for it — says only what it means.

    Expiry raises :class:`~reliquary.errors.WaitExpired`, which is a
    ``RunFailure`` *and* a ``TimeoutError``: the wait not finishing is
    the work not happening (exit ``4`` at the CLI), while nothing about
    the machine went wrong and the value may still arrive, so a caller
    holding the loop catches the ordinary ``TimeoutError`` and asks
    again (D90).
    """
    check_variable_key(key)
    machine_id = resolve_machine(
        machine=machine, blueprint=blueprint, context=context)
    if timeout <= 0 or interval <= 0:
        raise StaticError(
            "a wait needs a positive timeout and interval, got "
            f"timeout={timeout!r} interval={interval!r}",
            rule_id="time.non-positive")
    deadline = time.monotonic() + timeout
    while True:
        current = get_machine_var(key, machine=machine_id, context=context)
        if current is not None and (value is None or current == value):
            return current
        if time.monotonic() >= deadline:
            raise WaitExpired(
                f"{key!r} did not "
                + ("arrive" if value is None else f"reach {value!r}")
                + f" on {machine_id} within {timeout}s"
                + ("" if current is None else f" (it is {current!r})"),
                rule_id="script.wait-expired")
        time.sleep(min(interval, max(0.0, deadline - time.monotonic())))


def get_machine_var(key, *, machine=None, blueprint=None, context=None):
    """Read one machine variable — ``None`` when it is not set.

    A query: valid in any phase, touching nothing. An unset variable
    and a machine that never ran read the same, which is what keeps
    :func:`wait_machine_var` a plain loop over this.
    """
    check_variable_key(key)
    machine_id = resolve_machine(
        machine=machine, blueprint=blueprint, context=context)
    state = load_machine_state(machine_id, context)
    return (state.get("variables") or {}).get(key)


def exec(command, *, machine=None, blueprint=None, timeout=120,
         check=False, context=None):
    """Run one command in a running guest and return its output.

    The run family's one-shot member: like ``run_script`` it drives
    the machine and **returns its output** to the caller, storing
    nothing (D36). The output is the text the command left on the
    guest's screen, as a tuple of rows — reliquary reads no meaning
    into it (G2), and a caller wanting structure retrieves a file
    instead (:func:`get_file`) or reads a machine variable.

    ``check=True`` adds the channel the rows cannot carry: **whether
    the command worked.** A setup command — load a driver, install a
    TSR — produces no output worth reading and its success is the
    whole point, so without this success and failure both come back
    as rows and a refused loader is discovered later, as every
    subsequent command failing strangely. With it, a command that
    signalled failure raises :class:`RunFailure` naming the command
    (exit ``4`` at the CLI) and the return is unchanged otherwise.

    How the question is asked belongs to the platform workflow, and
    on DOS it is an ERRORLEVEL probe reliquary composes and reads
    back — text of its own, not the guest's, so the no-meaning rule
    is untouched. Its scope is commands that *ran* and signalled
    failure: a mistyped one leaves ERRORLEVEL alone and escapes the
    probe (:meth:`AgentlessGuestExec._refuse_if_failed`).

    The platform workflow owns command syntax and completion
    detection, so anything but DOS fails closed rather than
    borrowing DOS assumptions.

    (The name shadows the Python builtin inside this module, which is
    the price of the twin-name identity rule: the CLI command *is*
    ``exec``. Nothing here calls the builtin.)
    """
    machine_id = resolve_machine(
        machine=machine, blueprint=blueprint, context=context)
    state = load_machine_state(machine_id, context)
    platform = state.get("platform")
    if platform != "dos":
        raise PreflightError(
            f"exec is not implemented for platform {platform!r}; DOS "
            "is the delivered workflow",
            rule_id="platform.verb-not-implemented")
    phase = state.get("phase")
    if phase != "running":
        raise PreflightError(
            f"machine {machine_id} is not running (phase: {phase}); "
            f"start it first: rlq start-machine --machine "
            f"{machine_id}", rule_id="machine.not-running")
    machine_home = machine_dir_path(machine_id, context)
    if read_vm_state(machine_home) is None:
        raise PreflightError(
            f"machine {machine_id} is running but has no recorded VM "
            "identity", rule_id="machine.no-vm-identity")
    return AgentlessGuestExec(
        Machine(machine_home)).execute(command, timeout, check=check)


def destroy_machine(machine_id, context=None):
    """Delete a machine's cache directory entirely.

    Under the per-machine lock. A ``ready`` machine passes through the
    transitional ``destroying`` phase; a machine already ``destroying``
    or rolled-back-from ``creating`` completes its removal. A running
    machine is refused. A deletion interrupted by a host lock can be
    retried — a failure from ``ready`` restores ``ready`` so it does
    not strand the machine in ``destroying``.
    """
    with machine_lock(machine_id, context):
        state = load_machine_state(machine_id, context)
        phase = state.get("phase")
        if phase == "running":
            raise PreflightError(
                f"machine {machine_id} is running; "
                "stop it before destroying", rule_id="machine.must-be-stopped")
        if phase not in ("ready", "destroying", "creating"):
            raise PreflightError(
                f"machine {machine_id} cannot be destroyed "
                f"(phase: {phase})", rule_id="machine.phase-cannot-destroy")
        if phase == "ready":
            _write_phase(machine_id, "destroying", context, bump=True)
        machine_home = machine_dir_path(machine_id, context)
        # The backend disposes of its own machine object first; the
        # directory is deleted after. For QEMU the directory *is* the
        # whole materialization, so its adapter has nothing to do.
        backends.adapter(state.get("backend") or "qemu").dispose(
            machine_home)
        try:
            shutil.rmtree(machine_home)
        except OSError:
            # Leave the machine in a retry-able phase.
            if phase == "ready":
                _write_phase(machine_id, "ready", context)
            raise


# Rendering a machine's drives into backend configuration used to
# live here as `machine_drive_args`, and is now the adapter's
# (`backend_qemu.drive_args`): Reliquary drive vocabulary in, backend
# configuration out, on the far side of the seam.
