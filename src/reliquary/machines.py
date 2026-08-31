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
from . import document
from . import events as _events
from .acquire import fetch_media as _acquire_fetch
from .errors import (InternalError, PreflightError, ReliquaryError,
                     StaticError, WaitExpired)
from .home import machines_dir
from .library import codex_blueprint_available
# machine_state.py is the foundation this module is built on: machine
# ids and directories, the locks, machine.json, and selector
# resolution.
#
# Other code always reaches these through `machines` — the session
# layer, the script runner, the media-handling code — which is why
# this module imports names below that it never calls itself; it is
# just re-exporting them. The one exception is `machine.py`, which
# imports `read_vm_state` straight from `machine_state` instead,
# because importing this module from there would create an import
# cycle between the two.
from .interaction_agentless import AgentlessGuestExec
from .machine_handle import Machine
from .machine_state import (allocate_machine_id, backend_dir,
                            blueprint_alloc_lock,
                            list_machines as _list_machines_state,
                            load_machine_state, machine_dir_path,
                            machine_disks_dir, machine_id_for,
                            machine_lock, machines_for_blueprint,
                            read_vm_state, resolve_machine,
                            split_machine_id, write_state)
from .resolve import (load_namespace, location_property_keys,
                      render_text, resolve_media, resolve_media_plan)


def _drive_media(drive, namespace):
    """The media a drive or share carries: from the catalog, or
    declared inline (both shapes carry ``inline``/``media`` the same
    way, so this serves ``MachineDrive`` and ``MachineShare`` alike).

    A media declared directly on the device (inline) is used as-is —
    an anonymous blank drive has no catalog name to look up, since it
    was never given one (a share never has an anonymous inline media
    at all: F68 refuses one at parse time).
    """
    if drive.inline is not None:
        return drive.inline
    if drive.media is None:
        return None
    return resolve_media(drive.media, namespace)


def _image_stem(media, key):
    """The per-machine image name: the media's name, or the slot's key
    for a blank.

    Images are keyed by media name so that different media passing
    through one shared removable slot never overwrite each other's
    image. The anonymous blank is the one exception, and the one case
    where the slot's key is used instead: a blank has no catalog name
    to be keyed by.
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

#: The NIC chipset each platform gets by default (D120), when a
#: `devices` NIC doesn't name one itself (`model`, D122). Every
#: current platform gets `pcnet`, since it's the one chipset both
#: built backends actually emulate — the same reasoning that makes
#: `ide` the universal `controller` default.
_PLATFORM_NIC = {
    "dos": "pcnet",
    "openbsd": "pcnet",
    "win9x": "pcnet",
    "winnt": "pcnet",
}


def _resolve_nic_model(platform):
    return _PLATFORM_NIC.get(platform, "pcnet")


def _resolve_network(network, platform, bound_values):
    """This machine's ``network`` slots, resolved into state entries.

    ``model`` is whatever the blueprint named (D122), or the platform
    default (D120) when it named none. ``interface`` is substituted
    from ``bound_values`` when it's a property reference; a plain
    string or an omitted interface passes through unchanged.
    """
    resolved = {}
    for key, net in sorted(network.items()):
        interface = net.interface
        if isinstance(interface, document.Deferred):
            interface = render_text(
                interface, bound_values, f"network.{key}.interface")
        resolved[key] = {
            "attachment": net.attachment, "interface": interface,
            "model": net.model or _resolve_nic_model(platform),
        }
    return resolved


def _dry_network(network, platform, bound_values):
    """Mirrors :func:`_resolve_network`, but never raises on an unbound
    interface — a dry run must never fail on a key nothing answered,
    the same leniency :func:`_dry_payload` already gives a location.
    """
    resolved = {}
    for key, net in sorted(network.items()):
        interface = net.interface
        if isinstance(interface, document.Deferred):
            interface = next(
                (bound_values[ref.target] for ref in interface.references
                 if ref.target in bound_values), None)
        resolved[key] = {
            "attachment": net.attachment, "interface": interface,
            "model": net.model or _resolve_nic_model(platform),
        }
    return resolved


def _default_control_planes(platform):
    """The platform's default control-plane policy.

    Every current platform defaults to agentless display — the one
    control plane that works on any guest without needing anything
    installed or running inside it (blueprint-reference.md). Richer
    per-platform defaults will arrive as those other control planes
    are added.
    """
    return ["agentless-display"]


def _resolve_control_planes(machine):
    """The machine's control-plane policy, with the default filled in.

    Whether a control plane can actually be provided is answered by
    the backend, not by this module: the policy becomes a
    requirement, and the backend adapter's capability report judges
    whether it can meet it (P11).
    """
    return (list(machine.control_planes)
            or _default_control_planes(machine.platform))


def _pointer_value(machine):
    """The machine's pointer input device, with the default filled in.

    ``emulated-mouse`` (a standard relative-motion device) is what
    every platform's default machine already carries anyway, so this
    default just states what is already true rather than choosing
    something new (F66). A platform from the GUI era will eventually
    get a more specific default, the same way `_default_control_planes`
    will eventually get richer per-platform defaults of its own.
    """
    device = machine.pointer.get("pointer0")
    return device.value if device is not None else "emulated-mouse"


def _resolve_pointer(machine):
    """This machine's `pointer0` slot, resolved into a state entry
    (D124). Always present, unlike `net`/`share`/`rng`, which are
    absent entirely when undeclared: every machine has a pointer
    device whether or not one was named, so the default is filled in
    here rather than by leaving the slot out.
    """
    return {"pointer0": {"value": _pointer_value(machine)}}


def _resolve_rng(rng):
    """This machine's `rng` slots, resolved into state entries (D125).

    ``rng-model`` — not ``model`` — is the entry's key: a share entry
    also carries a ``model`` key in the same merged `devices` state
    map, and the two must stay tellable apart by key alone the way a
    drive's ``medium`` and a NIC's ``attachment`` already are.
    """
    return {key: {"rng-model": device.model}
            for key, device in sorted(rng.items())}


def _backend_choice(machine):
    """Where the blueprint says this machine belongs, and how it said so.

    There are three possible answers, checked in this order:

    1. A declared ``backend`` field pins the choice outright.
    2. Otherwise, if the blueprint has ``backend-settings`` for
       exactly one backend, that narrows the choice to it: settings
       sections are the only place backend-specific configuration can
       appear, so a blueprint with exactly one section has already
       said which backend it was written for. Picking a different
       backend that could never use those settings would mean
       ignoring what the blueprint said.
    3. Two or more sections narrow nothing — each stays unused until
       its backend is actually picked, and the normal priority walk
       decides instead.

    What matters is whether a section is present, not what is in it:
    an empty section names its backend just as clearly as a full one
    does.
    """
    if machine.backend is not None:
        return machine.backend, None, "declared"
    sections = sorted(machine.backend_settings)
    if len(sections) == 1:
        return None, sections[0], "backend-settings"
    return None, None, "priority walk"


def _requirements(machine, namespace):
    """What this blueprint asks of a backend, as a `backends.Requirements`.

    Read off the whole machine — its control-plane policy, the media
    kinds and controllers its enabled drives declare, and the
    materialization mode of every media they name — because a backend
    is chosen for the whole machine, never for one drive at a time.
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
    network_attachments = sorted(
        {net.attachment for net in machine.network.values()})
    network_models = sorted({
        net.model or _resolve_nic_model(machine.platform)
        for net in machine.network.values()})
    enabled_shares = [share for share in machine.shares.values()
                      if share.enabled]
    share_models = sorted({share.model for share in enabled_shares
                           if share.model is not None})
    share_unstated = any(share.model is None for share in enabled_shares)
    rng_models = sorted({device.model for device in machine.rng.values()})
    return backends.Requirements(
        control_planes=tuple(planes), media=tuple(media),
        controllers=tuple(controllers), materialize=tuple(modes),
        platform=machine.platform,
        pointing_device=_pointer_value(machine),
        rng_models=tuple(rng_models),
        network_attachments=tuple(network_attachments),
        network_models=tuple(network_models),
        share_models=tuple(share_models),
        share_unstated=share_unstated)


def _blueprint_digest(resolved, devices):
    """Hash the resolved blueprint into the digest `apply` compares
    against.

    Covers only the resolved logical shape of the machine — the
    per-drive cache ``path`` (which depends on this environment) and
    the recorded observation ``launch-size`` (the size a floppy drive
    was *launched* with, not what the blueprint asked for) are left
    out — so the same blueprint produces the same digest across
    different homes and across different boots.
    """
    observed = {"path", "launch-size"}
    snapshot = dict(resolved)
    snapshot["devices"] = {
        key: {name: value for name, value in entry.items()
              if name not in observed}
        for key, entry in devices.items()
    }
    canonical = json.dumps(
        snapshot, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(
        canonical.encode("utf-8")).hexdigest()


def _drive_common(key, drive):
    """The medium/slot/controller fields common to every drive entry.

    A controller the assigned backend can't support would already
    have been refused during backend assignment, by checking its name
    against that backend's capability report.
    """
    entry = {"medium": drive.medium, "slot": drive.slot}
    if drive.medium != "floppy":
        entry["controller"] = drive.controller or "ide"
    return entry


def _refuse_drive_directory(path, key):
    """Fail closed if a drive's resolved payload is a host directory.

    A directory payload is legal only on a share slot now (F68) — the
    old per-medium carve-out (silently rendered as vvfat on a floppy
    or hard disk, quietly mishandled on a cdrom) is gone. This can
    only be checked once the payload has actually been fetched or
    verified, which is why it lives here rather than at parse time.
    """
    if path is not None and os.path.isdir(path):
        raise PreflightError(
            f"devices.{key} resolves to a directory ({path}); a "
            "directory payload is legal only on a share slot, not a "
            "drive", rule_id="drive.directory-not-allowed")


def _materialize_drive(key, drive, adapter, disks_root, namespace, context,
                       properties=None, events=None, cancelled=None):
    """Materialize one enabled drive, returning its resolved state entry.

    The drive names a media (or is an empty removable slot); which
    materialization mode applies is decided by the media, not the
    drive. ``new`` creates a fresh blank of the given ``size``;
    ``use`` attaches the fetched payload directly; ``difference``/
    ``copy`` build a per-machine image over, or as a copy of, the
    fetched payload. Per-machine images live under ``disks/``, keyed
    by the media name rather than the slot, so a medium moving through
    a removable slot keeps its own image; the adapter names the actual
    file, since the native image format is its choice. The returned
    entry records the resulting ``path`` plus the media name and mode.
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
        path = _acquire_fetch(
            media, namespace, context, properties=properties, events=events,
            cancelled=cancelled)
        _refuse_drive_directory(path, key)
        entry["path"] = path
    elif mode in ("difference", "copy"):
        base_payload = _acquire_fetch(
            media, namespace, context, properties=properties, events=events,
            cancelled=cancelled)
        _refuse_drive_directory(base_payload, key)
        dest = adapter.image_path(disks_root, _image_stem(media, key))
        adapter.create_image(dest, mode=mode, base=base_payload)
        entry["path"] = dest
    else:
        raise InternalError(f"unknown materialize mode {mode!r} for {key}")
    return entry


def _materialize_share(key, share, adapter, platform, namespace, context,
                       properties=None, events=None, cancelled=None):
    """Materialize one enabled share, returning its resolved state entry.

    A share always names a directory-payload media whose materialize
    mode must be ``use`` — it presents the directory in place, live,
    for as long as the machine runs (design:
    planning/pledged/design/share-devices.md). The model is whatever
    the blueprint named, or the assigned backend's own default when it
    named none (D122) — resolving that default here, after
    assignment, is what keeps an unstated share from ever silently
    landing on ``vvfat``; ``backends.assign`` already refused this
    machine if the assigned backend has no live default to fall back
    on, so ``share_default`` is never ``None`` by the time this runs.
    The report is asked about this machine's own ``platform`` for the
    same reason assignment was: a backend can serve different models
    from the tool one guest architecture needs than from another's
    (F69), and the two questions must be answered by the same tool.

    ``read-only`` is read off the media and recorded here, because the
    renderer is given the state entry and never sees the media. It
    means the same thing it means on a drive: present the payload —
    here, the host directory — so the guest cannot write to it.
    """
    media = _drive_media(share, namespace)
    mode = media.materialize
    if mode != "use":
        raise StaticError(
            f"devices.{key}: a share always presents its directory in "
            f"place, so its media must 'use' (attach), not '{mode}'",
            rule_id="share.materialize-not-use")
    path = _acquire_fetch(
        media, namespace, context, properties=properties, events=events,
        cancelled=cancelled)
    if not os.path.isdir(path):
        raise PreflightError(
            f"devices.{key} names {media.name!r}, which resolves to a "
            f"file ({path}); a share always presents a directory",
            rule_id="share.directory-required")
    return {
        "media": media.name,
        "materialize": mode,
        "path": path,
        "model": share.model or adapter.capabilities(platform).share_default,
        "read-only": bool(media.read_only),
    }


def create(machine, namespace, *, context=None, blueprint_name="",
           source=None, number=None, properties=None, events=None,
           backend=None):
    """Materialize one machine from a parsed composed machine component.

    Assigns the backend (a declared one pins the choice; otherwise the
    priority walk picks the first backend that is both available and
    capable), creates the machine's cache directory under
    ``cache/machines/<blueprint>-<n>/``, and writes ``machine.json``
    with the fully resolved configuration plus its provenance
    (``blueprint-source``, ``blueprint-digest``, ``backend-id``).
    Every enabled drive is materialized: a per-machine image under
    ``disks/`` for ``new``/``difference``/``copy`` media, or the
    fetched payload attached in place for ``use``. ``source`` is the
    absolute path of the blueprint file this machine resolved from,
    recorded so machine selection can be scoped to it. The machine
    number is the lowest free non-negative integer for that
    blueprint, unless ``number`` pins a specific one (``recreate``
    reuses the old id). ``backend`` overrides the blueprint's own
    ``backend`` field, pinning the choice the same way a declared
    ``backend`` field does. Returns the generated machine id.
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
    # Backend assignment happens before anything is materialized, so
    # a machine nothing on this host can build costs no image work —
    # and the backend is fixed before the first image is written in
    # its own native format.
    control_planes = _resolve_control_planes(machine)
    if backend is not None:
        declared, narrowed = backend, None
    else:
        declared, narrowed, _source = _backend_choice(machine)
    backend = backends.assign(_requirements(machine, namespace),
                              declared=declared, narrowed=narrowed)
    adapter = backends.adapter(backend)
    # Only the assigned backend's settings section applies, so
    # validation happens after assignment; sections for other
    # backends are simply ignored, since one backend's adapter has no
    # way to validate settings meant for a different backend.
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
    resolved_network = _resolve_network(machine.network, machine.platform,
                                        properties or {})
    resolved_shares = {}
    for key, share in sorted(machine.shares.items()):
        if not share.enabled:
            continue
        resolved_shares[key] = _materialize_share(
            key, share, adapter, machine.platform, namespace, context,
            properties, events)
    resolved_devices = {**resolved_drives, **resolved_network,
                        **resolved_shares, **_resolve_pointer(machine),
                        **_resolve_rng(machine.rng)}

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
        "blueprint-digest": _blueprint_digest(resolved, resolved_devices),
        **resolved,
        "devices": resolved_devices,
    }
    if source is not None:
        state["blueprint-source"] = os.path.abspath(os.fspath(source))

    write_state(machine_id, state, context)
    return machine_id


def _network_interface_keys(machine):
    """Every property key a machine's ``network`` slots reference (D120).

    A bridged interface name is exactly the kind of host-specific
    fact a media ``location`` already keeps out of the blueprint
    (U21), bound the same way.
    """
    keys = set()
    for net in machine.network.values():
        if isinstance(net.interface, document.Deferred):
            keys.update(ref.target for ref in net.interface.references)
    return keys


def _bind_location_properties(machine, namespace, *, parameters=None,
                              explicit=None, properties_file=None,
                              context=None):
    """Bind every ``${key}`` a machine's media locations and network
    interfaces reference.

    Collected across all of the machine's drives, shares, and network
    slots, and bound through the usual property-source order at
    create/apply time, so that a media located by ``${license-iso}``
    — a share's ``${exchange-dir}`` (U21) — or a bridged NIC's
    ``${host-nic}`` — gets materialized using whichever value a
    parameter, the environment, the properties file, or an interactive
    prompt supplies. Returns ``{key: value}`` (empty when nothing
    references a property).
    """
    keys = set()
    for drive in machine.drives.values():
        if not drive.enabled or drive.media is None:
            continue
        media = namespace.media.get(drive.media)
        if media is not None:
            keys.update(location_property_keys(media, namespace))
    for share in machine.shares.values():
        if not share.enabled or share.media is None:
            continue
        media = namespace.media.get(share.media)
        if media is not None:
            keys.update(location_property_keys(media, namespace))
    keys.update(_network_interface_keys(machine))
    if not keys:
        return {}
    return binding.bind_keys(
        keys, parameters=dict(machine.parameters), explicit=explicit,
        properties_file=properties_file, context=context,
        asker=binding.console_asker())


# --- the dry run -----------------------------------------------------
#
# A dry run performs every step that costs nothing and commits
# nothing, stops at the first step that would cost or commit
# something, and reports what it would have done. Two rules hold
# throughout. It leaves no state behind — no machine directory, no
# ``machine.json``, no fetched payload, no seeded blueprint, no lock
# file — and what it returns describes the run, rather than
# pretending to be the run's actual output.
#
# It raises whatever a real create would raise, at the same point a
# real create would raise it: if a dry run's verdict is "this would
# fail", it fails, and the error message is the answer. There are
# exactly two exceptions, and each is something a dry run specifically
# cannot do, not a judgment call about how bad a finding is:
#
#   1. It must never prompt, so a media location that no concrete
#      source can answer is reported as unresolved instead of being
#      asked for.
#   2. Under an explicit ``backend=``, the question being asked is
#      what *another* host would do, so that backend simply being
#      unavailable here is reported rather than raised as an error.
#      The backend being incapable of the request still raises —
#      that is the actual answer to the question that was asked.


@dataclasses.dataclass(frozen=True)
class DryRun:
    """What an operation would do, having done none of it.

    Returned by every ``dry_run=True`` call. It is a distinct type on
    purpose: a dry create must not hand back something a caller could
    mistake for the real return value — a machine id that names no
    real machine, or ``None`` — because that would turn a misuse into
    a confusing failure several layers down. Returning this type
    instead turns misuse into an immediate ``TypeError`` at the call
    site.

    ``operation`` names the verb being described, ``report`` is the
    printable, human-readable rendering, and ``plan`` is the
    operation's own data, which is the mapping ``--json`` serializes.
    These three fields are the whole type, so a second kind of
    dry-run operation only needs its own ``plan`` shape, never a new
    field.
    """

    operation: str
    report: str
    plan: dict = dataclasses.field(default_factory=dict)


def _seed_hint(name):
    """The suggested fix, if the shipped library has a blueprint by
    this name.

    Since blueprints are no longer resolved from the codex
    automatically, this is where a user learns seeding is the fix,
    when a lookup fails (P11, D88). Empty when the library has no
    blueprint of this name, since suggesting a fix that would also
    fail is worse than saying nothing.

    (A dry run no longer needs its own way to load a namespace. It
    used to read a codex blueprint directly — the one path by which
    the codex could affect an operation without being explicitly
    asked for — and now that's gone, dry runs and real creates
    resolve blueprints identically, which is what the rule always
    intended.)
    """
    if codex_blueprint_available(name):
        return f"\nthe codex has one: rlq seed-blueprint {name}"
    return ""


def _describe_location_properties(machine, namespace, *, explicit=None,
                                  properties_file=None, context=None):
    """Name each location key's source without asking for any of them.

    The dry-run counterpart of :func:`_bind_location_properties`: a
    real create binds these keys, prompting at the terminal for any
    one that nothing else answers, and a dry run must never prompt —
    so it takes whatever the concrete sources already supply, and
    reports the rest as the question a real create would have asked.
    """
    keys = set()
    for drive in machine.drives.values():
        if not drive.enabled or drive.media is None:
            continue
        media = namespace.media.get(drive.media)
        if media is not None:
            keys.update(location_property_keys(media, namespace))
    for share in machine.shares.values():
        if not share.enabled or share.media is None:
            continue
        media = namespace.media.get(share.media)
        if media is not None:
            keys.update(location_property_keys(media, namespace))
    keys.update(_network_interface_keys(machine))
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
    """Refuse a plan whose local payloads are not on disk.

    A missing local file is an error a dry run can and should catch —
    a real create would hit it too, and a plan that can't actually be
    executed must not report success (P11). This is raised only
    after the whole plan has been walked, so every missing media is
    named at once: stopping at the first one found would cost the
    user a fix-and-rerun cycle for each missing file, and collecting
    them all here avoids that. Nothing else is collected this way —
    every other kind of refusal still happens at the same point a
    real create would hit it.
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
    same refusals, in the same order — recording what it would have
    written instead of actually writing it. ``adapter.image_path``
    only builds a path string, it doesn't create anything, so asking
    where an image would land costs nothing and matches exactly what
    a real create would do.
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
        _refuse_drive_directory(payload, key)
        entry["path"] = payload
    elif mode in ("difference", "copy"):
        _refuse_drive_directory(payload, key)
        entry["base"] = payload
        entry["path"] = adapter.image_path(disks_root,
                                           _image_stem(media, key))
    else:
        raise InternalError(f"unknown materialize mode {mode!r} for {key}")
    return entry


def _dry_share(key, share, adapter, platform, namespace, context, properties,
               entries):
    """One share's resolved plan, materializing nothing.

    Mirrors :func:`_materialize_share` decision for decision.
    """
    media = _drive_media(share, namespace)
    mode = media.materialize
    if mode != "use":
        raise StaticError(
            f"devices.{key}: a share always presents its directory in "
            f"place, so its media must 'use' (attach), not '{mode}'",
            rule_id="share.materialize-not-use")
    payload = _dry_payload(media, namespace, context, properties, entries)
    if payload is not None and not os.path.isdir(payload):
        raise PreflightError(
            f"devices.{key} names {media.name!r}, which resolves to a "
            f"file ({payload}); a share always presents a directory",
            rule_id="share.directory-required")
    return {
        "key": key,
        "media": media.name,
        "materialize": mode,
        "path": payload,
        "model": share.model or adapter.capabilities(platform).share_default,
        "read-only": bool(media.read_only),
    }


def _dry_backend(machine, namespace, backend):
    """The backend a create would land on, and why — plus the
    capability check for it.

    With no ``backend`` argument given, this performs backend
    assignment itself: a declared ``backend`` pins the choice, a lone
    ``backend-settings`` section narrows it, otherwise the priority
    walk decides. With a ``backend`` argument given, it answers a
    different question instead — whether the blueprint would work
    *there* — so that backend simply being unavailable is reported,
    and only whether it is capable decides the outcome (P11).
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
    # A real create would refuse a settings section it cannot honor,
    # so a dry run does too, at the same point — the settings are
    # user-written input, judged the same way whether or not the
    # backend is actually available on this host.
    adapter.validate_settings(machine.backend_settings.get(assigned))
    disks_root = machine_disks_dir(machine_id, context)
    entries = []
    drives = [
        _dry_drive(key, drive, adapter, disks_root, namespace, context,
                   bound.values, entries)
        for key, drive in sorted(machine.drives.items()) if drive.enabled]
    _refuse_missing(entries)
    network = [
        {**entry, "key": key} for key, entry in sorted(
            _dry_network(machine.network, machine.platform,
                        bound.values).items())]
    shares = [
        _dry_share(key, share, adapter, machine.platform, namespace, context,
                  bound.values, entries)
        for key, share in sorted(machine.shares.items()) if share.enabled]
    pointer = [{"key": "pointer0", **_resolve_pointer(machine)["pointer0"]}]
    rng = [{**entry, "key": key}
          for key, entry in sorted(_resolve_rng(machine.rng).items())]
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
        "devices": drives + network + shares + pointer + rng,
        "media": entries,
        "properties": dict(bound.sources),
    }
    if verdict is not None:
        plan["backend-available"] = verdict.available
        plan["backend-detail"] = verdict.detail
    return DryRun(operation="create-machine", report=_dry_report(plan),
                  plan=plan)


def _network_line(entry):
    """One NIC's line in the report: its attachment, model, and interface."""
    line = f"  {entry['key']} ({entry['attachment']}, {entry['model']})"
    if entry["attachment"] == "bridged":
        line += f": {entry['interface'] or '(qemu default / backend default)'}"
    return line


def _drive_line(drive):
    """One drive's line in the report: what it is, and where it lands."""
    where = f"{drive['medium']} slot {drive['slot']}"
    if drive.get("controller"):
        where += f" {drive['controller']}"
    if drive["materialize"] is None:
        # An empty removable slot. The check is on the mode, not the
        # media name, because an anonymous inline blank also has no
        # name — but it is definitely not an empty slot.
        return f"  {drive['key']} ({where}): empty"
    what = f"{drive['media'] or '(inline)'} {drive['materialize']}"
    if drive.get("size"):
        what += f" {drive['size']}"
    target = drive.get("path") or "(unresolved)"
    return f"  {drive['key']} ({where}): {what} -> {target}"


def _share_line(entry):
    """One share's line in the report: its model, and where it lands."""
    target = entry.get("path") or "(unresolved)"
    return f"  {entry['key']} ({entry['model']}): {entry['media']} -> {target}"


def _rng_line(entry):
    """One RNG device's line in the report (D125)."""
    return f"  {entry['key']} ({entry['rng-model']})"


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
    drives = [d for d in plan["devices"] if "medium" in d]
    network = [d for d in plan["devices"] if "attachment" in d]
    pointer = [d for d in plan["devices"] if "value" in d]
    rng = [d for d in plan["devices"] if "rng-model" in d]
    shares = [d for d in plan["devices"]
             if "medium" not in d and "attachment" not in d
             and "value" not in d and "rng-model" not in d]
    lines.append(f"pointer: {pointer[0]['value']}")
    if network:
        lines.append("network:")
        lines.extend(_network_line(entry) for entry in network)
    if drives:
        lines.append("drives:")
        lines.extend(_drive_line(drive) for drive in drives)
    if shares:
        lines.append("shares:")
        lines.extend(_share_line(entry) for entry in shares)
    if rng:
        lines.append("rng:")
        lines.extend(_rng_line(entry) for entry in rng)
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

    A blueprint the home directory does not contain is never seeded
    automatically — run ``rlq seed-blueprint <name>`` first to copy
    it (and the media/scripts it references) from the built-in
    library into the home directory (D88); this raises
    ``PreflightError`` naming that command if the blueprint is
    missing. ``number`` pins the machine number
    (``recreate`` reuses the old id); if omitted, the lowest free
    number is allocated. ``properties`` / ``properties_file`` bind
    any ``${key}`` a media location references, before materialization
    happens.

    ``dry_run=True`` materializes nothing and returns a
    :class:`DryRun` describing what a create would do — the machine
    id it would allocate, the backend it would land on, each drive's
    resolved plan, and where every media would come from. It leaves
    no state behind (nothing is seeded, fetched, locked, or written)
    and never prompts. ``backend`` overrides the blueprint's own
    ``backend`` field, pinning assignment the same way a declared one
    does: the backend must be both available and capable, and this
    raises an error if either is false. With ``dry_run``, it asks the
    other question instead — whether the blueprint would work
    *there* — so a backend simply being unavailable is reported
    rather than raised as an error (P11).
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
    # The blueprints directory is the only place searched: nothing is
    # seeded automatically on first reference, and the codex only
    # reaches a project's tree when `seed-blueprint` is explicitly
    # asked to put it there (D88). If the codex ships a blueprint by
    # this name, the refusal says so instead of silently supplying it.
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

    Under the instance model, this is a query valid in any phase — it
    reads the directory path without touching or requiring anything
    about the machine's state.
    """
    machine_id = resolve_machine(
        machine=machine, blueprint=blueprint, context=context)
    return os.path.abspath(machine_dir_path(machine_id, context))


_OWNED_MODES = ("new", "difference", "copy")


def _reconcile_drives(machine, namespace, old_drives, adapter, disks_root,
                      context, properties=None, events=None):
    """Reconcile a machine's drives to a re-resolved machine component.

    Changes that can be applied safely are applied: drives added,
    removed, or enabled/disabled, and every ``use`` or empty-slot
    drive is re-fetched or emptied to match the blueprint (this also
    undoes any live media change a script made with insert/eject). A
    drive whose image reliquary already materialized
    (``new``/``difference``/``copy``) is kept only when its media
    name and mode (and, for ``new``, its size) are unchanged; any
    other change to it raises an error, naming ``recreate`` as the
    way to make that change. Returns the new drive-state mapping; a
    materialized image for a removed drive is deleted.
    """
    new_drives = {}
    enabled = {key: drive for key, drive in machine.drives.items()
               if drive.enabled}
    for key, drive in sorted(enabled.items()):
        old = old_drives.get(key)
        old_owns = old is not None and old.get("materialize") in _OWNED_MODES
        if not old_owns:
            # No image here that reliquary already owns: freely
            # (re)materialize or re-point it (a media re-fetch, an
            # empty slot, or a brand-new image).
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

    Re-resolves the blueprint the machine was created from (this
    never happens automatically at ``start``) and reconciles the
    machine to it: memory, cpus, boot, control-planes,
    backend-settings, metadata, and any drive change that can be
    applied safely are all applied. A changed ``size`` or ``base`` on
    an image reliquary already materialized raises an error instead
    (``recreate`` is the alternative). The newly resolved snapshot
    becomes the new baseline (``blueprint-digest`` /
    ``blueprint-source`` are re-recorded). ``properties`` /
    ``properties_file`` bind any ``${key}`` a re-materialized media
    location references. Returns the machine id.
    """
    machine_id = resolve_machine(
        machine=machine, blueprint=blueprint, context=context)
    with machine_lock(machine_id, context):
        state = _corroborate_locked(
            machine_id, _reconcile_phase(machine_id, context), context)
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
        # Checked here, right after the capability check above and
        # before any drive is touched: a settings section this
        # backend cannot honor leaves the machine exactly as it was.
        adapter.validate_settings(parsed.backend_settings.get(backend))

        bound = _bind_location_properties(
            parsed, namespace, explicit=properties,
            properties_file=properties_file, context=context)
        disks_root = machine_disks_dir(machine_id, context)
        old_devices = state.get("devices", {})
        old_drives = {key: entry for key, entry in old_devices.items()
                     if "medium" in entry}
        new_drives = _reconcile_drives(
            parsed, namespace, old_drives, adapter, disks_root,
            context, bound, events)
        new_network = _resolve_network(parsed.network, parsed.platform,
                                       bound)
        # A share has no materialized image the way an owned drive
        # does (F68), so unlike `_reconcile_drives` it's simply
        # re-resolved fresh every apply — there's nothing to keep
        # unchanged or refuse to regenerate.
        new_shares = {}
        for key, share in sorted(parsed.shares.items()):
            if not share.enabled:
                continue
            new_shares[key] = _materialize_share(
                key, share, adapter, parsed.platform, namespace, context,
                bound, events)
        new_devices = {**new_drives, **new_network, **new_shares,
                       **_resolve_pointer(parsed), **_resolve_rng(parsed.rng)}

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
        state["devices"] = new_devices
        state["blueprint-digest"] = _blueprint_digest(resolved, new_devices)
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
    """Power off the owned VM and reconcile the phase and VM identity.

    On success, the machine returns to ``ready`` and its ``vm``
    section is cleared, both written together. If the adapter's
    ``stop`` call raises an error, the phase is still updated to
    match reality instead of being left stale: if the ``vm`` section
    is already gone, the machine becomes ``ready``; if it is still
    recorded (our VM may still be running — a stuck port, or an
    identity mismatch), the phase is restored to ``running``. Either
    way, the error is re-raised.

    An unreachable VM is the one exception, and counts as a completed
    stop rather than a failed one: the adapter looked for this
    machine's VM and found none to power off, which is exactly the
    state ``stop`` was asked to produce. `script_runner._read`
    already treats that same rule id as meaning "stopped" when it
    shows up mid-run, so a run recovers on its own; without the same
    handling here, a guest that powered itself off between runs would
    leave the machine impossible to stop, and therefore impossible to
    destroy, with no way out but deleting its directory by hand
    (T19). The check is exactly that rule id — an identity mismatch,
    or a port that answers with something wrong, is a different
    situation and still raises an error.
    """
    state = load_machine_state(machine_id, context)
    vm = state.get("vm")
    backend = (vm or {}).get("backend") or state.get("backend") or "qemu"
    try:
        backends.adapter(backend).stop(vm)
    except ReliquaryError as error:
        if error.rule_id == "machine.vm-unreachable":
            _clear_vm(machine_id, "ready", context)
            return
        if load_machine_state(machine_id, context).get("vm") is None:
            _write_phase(machine_id, "ready", context)
        else:
            _write_phase(machine_id, "running", context)
        raise
    _clear_vm(machine_id, "ready", context)


def _reconcile_phase(machine_id, context=None):
    """Recover a machine found in an interrupted transitional phase.

    Called under the machine lock at the start of each mutating
    operation (``destroy`` handles its own phases separately). A
    resting phase (``ready``/``running``) is returned unchanged.
    ``stopping`` completes the interrupted stop; ``creating`` and
    ``destroying`` are finished by removing the incomplete
    materialization, and then this raises an error that tells the
    caller how to recover.
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
        return _start_locked(machine_id, display=display, context=context,
                             events=events, cancelled=cancelled)


def _start_locked(machine_id, *, display=False, context=None, events=None,
                  cancelled=None):
    """`start_machine`'s body, with the machine lock already held.

    Split out for `restart_machine`, which must not let go between
    stopping and starting. The lock is a file lock and not
    re-entrant, so a caller already holding it cannot simply call the
    public function.
    """
    state = _corroborate_locked(
        machine_id, _reconcile_phase(machine_id, context), context)
    phase = state.get("phase")
    if phase == "running":
        raise PreflightError(
            f"machine {machine_id} is already running",
            rule_id="machine.already-running")
    if phase != "ready":
        raise PreflightError(
            f"machine {machine_id} cannot start "
            f"(phase: {phase})", rule_id="machine.phase-cannot-start")

    devices = state.get("devices", {})
    drives = [entry for entry in devices.values() if "medium" in entry]
    # A pointer entry carries "value" and an rng entry carries
    # "rng-model" (never "model" — a share already owns that key in
    # this same merged map, D124/D125), so both are excluded here the
    # same way a NIC's "attachment" already is: neither needs the
    # re-fetch/re-verify a `use` drive or a share gets below.
    shares = [entry for entry in devices.values()
             if "medium" not in entry and "attachment" not in entry
             and "value" not in entry and "rng-model" not in entry]
    namespace = load_namespace(context)
    for drive in drives:
        media_name = drive.get("media")
        # Re-resolve attached (`use`) payloads and re-verify their
        # hashes; per-machine images (new/difference/copy) keep their
        # recorded path.
        if media_name is not None and drive.get("materialize") == "use":
            path = _fetch(
                media_name, context, namespace=namespace, events=events,
                cancelled=cancelled)
            _refuse_drive_directory(path, drive["medium"] + str(drive["slot"]))
            drive["path"] = path
    for share in shares:
        # A share is always `use` (F68), so this always re-resolves —
        # the same re-verification a `use` drive gets above.
        share["path"] = _fetch(
            share["media"], context, namespace=namespace, events=events,
            cancelled=cancelled)
    # The backend fixes a floppy drive's geometry from whatever
    # medium is attached at launch, so record it: a later live
    # swap must match, and this is the only moment the fact is
    # knowable.
    for drive in drives:
        if drive.get("medium") == "floppy":
            drive["launch-size"] = _medium_size(drive.get("path"))
    state["devices"] = devices
    # A machine variable belongs to one boot: a script `set` it
    # while the guest ran, so the next start starts empty.
    state.pop("variables", None)
    write_state(machine_id, state, context)

    if state.get("memory") is None:
        state["memory"] = _PLATFORM_MEMORY.get(state.get("platform"), 16)
    backend = state.get("backend") or "qemu"
    adapter = backends.adapter(backend)
    # Probed for *this machine's* platform: QEMU's system binary is
    # one per guest architecture, so a bare probe would judge a
    # different binary than the start is about to launch.
    probe = adapter.discover(state.get("platform"))
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
        _stop_locked(machine_id, context)


def _stop_locked(machine_id, context=None):
    """`stop_machine`'s body, with the machine lock already held.

    The counterpart of `_start_locked`, and split out for the same
    reason: `restart_machine` holds the lock across both halves.
    """
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


def restart_machine(machine_id, *, display=False, context=None, events=None,
                    cancelled=None):
    """Stop a machine if it is running, then start it. Returns its id.

    The lock is held across both halves, which is the whole
    difference from just running the two commands separately. That
    isn't a new kind of lock — it's the same per-machine lock every
    mutating operation already takes, simply not released in between.
    What that buys is that nothing else can start the machine, swap
    its media, or apply a blueprint in the gap: a restart that
    released the lock in the middle could come back to find someone
    else had already started the machine, and fail with
    `machine.already-running` — a race the caller never asked for.

    A stopped machine is started rather than refused. The end state
    being asked for is *running*, and "stop" is already satisfied by
    a machine that's already off, so refusing here would make the
    command's outcome depend on a phase the caller usually neither
    knows nor cares about. A machine caught mid-``stopping`` is
    reconciled by `_reconcile_phase` first, exactly as running the
    two commands separately would do.
    """
    with machine_lock(machine_id, context):
        _stop_locked(machine_id, context)
        return _start_locked(machine_id, display=display, context=context,
                             events=events, cancelled=cancelled)


_REMOVABLE_MEDIA = {"floppy", "cdrom"}


def _removable_drive(state, slot):
    """Return the mutable state entry for a removable drive slot."""
    drive = state.get("devices", {}).get(slot)
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
    backend session, addressed by the drive's slot key, so the change
    the guest sees and the change persisted to the state happen as
    one operation.
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
    slot. A drive can no longer resolve to a directory (F68), but the
    ``isdir`` guard stays as a defensive no-op rather than assuming
    that invariant holds all the way down to this helper."""
    if not path or os.path.isdir(path):
        return None
    try:
        return os.path.getsize(path)
    except OSError:
        return None


def _check_live_geometry(state, slot, drive, path):
    """Refuse a live floppy swap the drive's geometry cannot serve.

    A floppy drive's geometry is fixed by the backend when it
    attaches the drive at launch, and a live ``change`` does not
    revise it — so a medium of a different size reaches the guest as
    read and write errors, not as a new disk. Reliquary did not
    choose that geometry, so this reports what it cannot do instead
    of producing a broken drive (P11). Verified on QEMU/DOS during
    milestone 9's investigation into floppy-based transport.
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
    """The path an ``insert_media(file=)`` mounts, or an error if it
    can't.

    ``--file`` mounts an anonymous ``local`` + ``use`` media (U20):
    mutable, unverified, and attached in place. It has no catalog
    name, no ``sha256`` to check it against, and reliquary never
    copies it — the caller owns the image it just built and is free
    to rebuild it for the next round.
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
        state = _corroborate_locked(
            machine_id, _reconcile_phase(machine_id, context), context)
        _removable_drive(state, slot)
        path = (_anonymous_local(file) if file is not None
                else _fetch(media, context, events=events,
                            cancelled=cancelled))
        _refuse_drive_directory(path, slot)
        drive = state["devices"][slot]
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
        state = _corroborate_locked(
            machine_id, _reconcile_phase(machine_id, context), context)
        _removable_drive(state, slot)
        if state.get("phase") == "running":
            _change_media_live(machine_id, slot, None, context)
        drive = state["devices"][slot]
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
        state = _corroborate_locked(
            machine_id, _reconcile_phase(machine_id, context), context)
        phase = state.get("phase")
        if phase != "ready":
            raise PreflightError(
                f"machine {machine_id} must be stopped "
                f"to change boot order (phase: {phase})",
                rule_id="machine.must-be-stopped")
        drives = {key: entry for key, entry in state.get("devices", {}).items()
                 if "medium" in entry}
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


def list_machines(context=None, blueprint=None):
    """Return machine states, double-checking a recorded ``running``
    phase.

    ``machine.json`` records whichever phase reliquary itself last
    set a machine to; only ``stop``/``mark_stopped`` update it, so if
    a guest powers itself off, its process gets killed, or the host
    crashes between runs, a stale ``running`` phase is left behind
    with nothing to notice it. Every machine reported ``running``
    here is checked against its actual backend first (opening the
    same identity-verified ``session()`` a script run already opens),
    and is corrected to ``ready`` if the backend confirms the VM is
    gone (``machine.vm-unreachable``) before being handed back — so
    the phase this returns always reflects reality, not just whatever
    was last written to disk, no matter what actually stopped the
    machine. A check that can't confirm either way (some other kind
    of backend error) reports the recorded phase as-is, rather than
    raising an error and failing the whole list.
    """
    return [_corroborated(state, context)
           for state in _list_machines_state(context, blueprint)]


def _vm_confirmed_gone(vm):
    """Check ``vm``'s backend without changing anything.

    Returns ``True`` only when the backend raises a confirmed
    ``machine.vm-unreachable`` — the one error `stop` and
    `mark_stopped` already treat as meaning "the VM is gone", as
    opposed to merely unreachable for some other reason (a wrong VNC
    port, an identity mismatch). Those other cases return ``False``:
    the check couldn't confirm the VM is actually gone, so it isn't
    treated as gone.
    """
    backend = vm.get("backend") or "qemu"
    try:
        with backends.adapter(backend).session(vm):
            pass
    except ReliquaryError as error:
        return error.rule_id == "machine.vm-unreachable"
    return False


def _corroborated(state, context):
    """One machine's ``running`` phase, checked against the backend
    and corrected if needed.

    Used by callers that hold no lock of their own (``list_machines``,
    and the shared precheck `exec` and `wait_ready` both run): a
    confirmed-gone VM is corrected through :func:`mark_stopped`,
    which takes the per-machine lock itself.
    """
    vm = state.get("vm")
    if (state.get("phase") != "running" or not vm
            or not _vm_confirmed_gone(vm)):
        return state
    mark_stopped(state["id"], context)
    return load_machine_state(state["id"], context)


def _corroborate_locked(machine_id, state, context):
    """The same check and correction, for a caller that already holds
    the lock.

    ``start``, ``apply``, ``set-boot-order``, and insert/eject-media
    all check the recorded phase before ever touching the backend,
    under the per-machine lock — so without this check, a stale
    ``running`` left behind by a VM that died some other way would
    make them refuse or misbehave, without reliquary ever actually
    looking. Calling :func:`mark_stopped` here would deadlock, since
    it tries to acquire the same per-machine lock the caller already
    holds and the lock isn't reentrant — so a confirmed-gone VM is
    instead corrected with the same direct write :func:`_complete_stop`
    already uses while holding the lock.
    """
    vm = state.get("vm")
    if (state.get("phase") != "running" or not vm
            or not _vm_confirmed_gone(vm)):
        return state
    _clear_vm(machine_id, "ready", context)
    return load_machine_state(machine_id, context)


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
# The way a script inside the guest passes a single text value back
# out to the host (U14/U20): a script `set`s a variable, and any
# process on the host can read it with `get-machine-var`. It lives in
# `machine.json` under the operation lock, and `start` clears it, so a
# variable always reports what the current boot produced.

_VARIABLE_KEY = re.compile(r"[A-Za-z][A-Za-z0-9._-]*\Z")
_RESERVED_VARIABLE = ("rlq", "reliquary")


def check_variable_key(key):
    """Validate a machine-variable key, or raise ``StaticError``.

    Same rules as property keys, for the same reason: the ``rlq`` and
    ``reliquary`` namespaces stay reserved for reliquary's own use, so
    a caller's own variable names can never collide with one the
    project introduces later.
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

    The user-facing name for this capability is the script ``set``
    statement — the scripting language is a primary interface in its
    own right, so this is reachable that way without needing a CLI
    command of its own. ``value`` is plain text; reliquary attaches no
    meaning to it (G2, P18).
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
#: by default. The read is of a small JSON file with no lock held, so
#: the interval exists just to avoid a busy-wait loop, not because the
#: read itself is costly.
_VAR_POLL = 1.0
_VAR_TIMEOUT = 120.0


def wait_machine_var(key, value=None, *, machine=None, blueprint=None,
                     timeout=_VAR_TIMEOUT, interval=_VAR_POLL,
                     context=None):
    """Wait until a machine variable arrives, and return it.

    This is the polling counterpart to machine variables, for cases
    `run_script(expect=)` can't handle: cases where whoever sets the
    variable is a different caller. A blocking run has all its
    variables final by the time it returns, so waiting after it
    finishes would have nothing left to poll for — but a caller
    running that same blocking form on another thread, or watching a
    run it did not start, genuinely sees the variable arrive later,
    and this function is the polling loop such a caller would
    otherwise have to write by hand (D90).

    ``value`` is the value to wait *for*; if omitted, any value will
    do, so the readiness idiom — a script whose last step is ``set
    ready``, and a driver that waits for it — says exactly what it
    means and nothing more.

    Expiry raises :class:`~reliquary.errors.WaitExpired`, which is
    both a ``RunFailure`` and a ``TimeoutError``: the wait not
    finishing means the work didn't happen (exit code ``4`` at the
    CLI), but nothing about the machine necessarily went wrong and the
    value may still arrive later, so a caller running its own retry
    loop can catch the plain ``TimeoutError`` and ask again (D90).
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

    A read-only query, valid in any phase. An unset variable and a
    machine that has never run read exactly the same way, which is
    what lets :func:`wait_machine_var` be a plain loop around this.
    """
    check_variable_key(key)
    machine_id = resolve_machine(
        machine=machine, blueprint=blueprint, context=context)
    state = load_machine_state(machine_id, context)
    return (state.get("variables") or {}).get(key)


def exec(command, *, machine=None, blueprint=None, timeout=120,
         check=False, context=None):
    """Run one command in a running guest and return its output.

    The one-shot member of the run family: like ``run_script``, it
    drives the machine and returns the output to the caller rather
    than storing it anywhere (D36). The output is the text the
    command left on the guest's screen, as a tuple of rows — reliquary
    does not interpret it (G2); a caller that wants structured data
    should use a machine variable instead, or read a file off a drive
    directly (an exception P16 carves out for file contents).

    ``check=True`` adds something the output rows can't tell you on
    their own: whether the command actually worked. A setup command —
    loading a driver, installing a TSR — produces no output worth
    reading, and its success is the whole point; without
    ``check=True``, success and failure both come back as ordinary
    rows, so a driver that failed to load is only discovered later,
    when every following command starts failing in strange ways. With
    ``check=True``, a command that reported failure raises
    :class:`RunFailure` naming the command (exit code ``4`` at the
    CLI), and the return value is otherwise unchanged.

    How "did it work" is determined depends on the platform. On DOS,
    it is an ERRORLEVEL check that reliquary itself types in and
    reads back — text reliquary generated itself, not something read
    out of the guest's own output, so this doesn't break the rule
    above about not interpreting guest output. It only catches
    commands that actually ran and then reported failure: a mistyped
    command never runs, so it leaves ERRORLEVEL unchanged and slips
    past this check (:meth:`AgentlessGuestExec._refuse_if_failed`).

    Which command syntax to use, and how to detect completion, is
    decided by the platform. Any platform other than DOS raises an
    error rather than incorrectly reusing DOS's own assumptions.

    (The name shadows the Python builtin inside this module, which is
    the price of keeping the CLI command and this function under the
    same name — the CLI command really is called ``exec``. Nothing
    here calls the builtin.)
    """
    guest = _running_guest("exec", machine, blueprint, context)
    return guest.execute(command, timeout, check=check)


def wait_ready(*, machine=None, blueprint=None, timeout=90, prompt=None,
               context=None):
    """Wait until a running guest is ready for commands.

    The precondition `exec` needs, implemented as its own companion
    function (D114): ``start_machine`` returns once the backend is
    up, not once the guest itself is, and the boot process is what
    stands between the two. This waits for the platform's own
    evidence of readiness — on DOS, the standard prompt on the bottom
    row, or exactly the text ``prompt`` declares for a guest whose
    ``AUTOEXEC.BAT`` customized it (D113) — so a test harness just
    needs one call between ``start_machine`` and its first ``exec``,
    without writing its own screen-pattern matching. A workflow where
    "ready" means more than just a prompt appearing should have its
    script set a variable instead; this function is the version of
    that same handoff that doesn't require writing a script.

    Expiry raises :class:`~reliquary.errors.WaitExpired`, both a
    ``RunFailure`` and a ``TimeoutError`` (D90): the prompt not
    arriving means the work didn't happen (exit code ``4`` at the
    CLI), but the boot may still finish, so a caller running its own
    retry loop can ask again.

    Which evidence counts as "ready" is decided by the platform, so
    any platform other than DOS raises an error rather than
    incorrectly reusing DOS's own assumptions.
    """
    guest = _running_guest("wait-ready", machine, blueprint, context)
    return guest.wait_ready(timeout, prompt=prompt)


def _running_guest(verb, machine, blueprint, context):
    """The agentless guest handle for a running DOS machine, or an
    error.

    The checks ``exec`` and ``wait_ready`` share before either one
    actually touches the guest's screen: the selector resolves to a
    machine, the machine's platform is one with an implemented
    workflow (DOS), the machine is running, and there is a recorded
    VM identity to verify the connection against. The error messages
    name whichever of the two operations was being attempted.
    """
    machine_id = resolve_machine(
        machine=machine, blueprint=blueprint, context=context)
    state = _corroborated(load_machine_state(machine_id, context), context)
    platform = state.get("platform")
    if platform != "dos":
        raise PreflightError(
            f"{verb} is not implemented for platform {platform!r}; DOS "
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
    return AgentlessGuestExec(Machine(machine_home))


def destroy_machine(machine_id, context=None):
    """Stop a machine if it is running, then delete its cache directory
    entirely.

    Held under the per-machine lock across both halves, for the same
    reason `restart_machine` holds it across stop and start: nothing
    else can start the machine, swap its media, or apply a blueprint
    in the gap between the stop and the removal. A ``running``
    machine is stopped first (`_stop_locked`); a ``ready`` machine
    then passes through the transitional ``destroying`` phase; a
    machine that is already ``destroying``, or was rolled back from
    ``creating``, just finishes being removed. If a deletion is
    interrupted by a host file lock it can be retried — a failure
    that started from ``ready`` restores ``ready``, so the machine
    isn't left stranded in ``destroying``.
    """
    with machine_lock(machine_id, context):
        state = load_machine_state(machine_id, context)
        phase = state.get("phase")
        if phase == "running":
            _stop_locked(machine_id, context)
            state = load_machine_state(machine_id, context)
            phase = state.get("phase")
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


# Turning a machine's drives into backend configuration used to live
# here as `machine_drive_args`, and now lives in the adapter instead
# (`backend_qemu.drive_args`): it takes reliquary's own drive
# vocabulary in and produces backend-specific configuration out, on
# the backend's side of the boundary between the two.
