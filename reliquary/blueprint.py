# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Machine blueprint parsing and media-reference resolution."""

import collections.abc
import os
import re
import types
from dataclasses import dataclass, field
from typing import Mapping, Optional, Tuple

from . import jsonc
from .media import ResolvedMedia, resolve_media


_FIELDS = {
    "platform", "backend", "memory", "cpus", "drives", "boot",
    "name", "description", "scripts", "control-planes",
    "backend-settings", "parameters",
}
# State-only fields (reliquary-machine.json); rejected in a blueprint
# with a message naming what they are.
_STATE_ONLY = {"id", "backend-id", "blueprint-digest", "blueprint-source"}
_PLATFORMS = {"dos", "openbsd", "win9x", "winnt"}
_BACKENDS = {"qemu", "virtualbox", "vmware", "hyperv"}
_CONTROLLERS = {"ide", "sata", "scsi", "nvme", "virtio"}
_CONTROL_PLANES = {
    "agentless-display", "vnc", "serial-console", "guest-agent",
}
_BASE_TYPES = {"difference", "duplicate"}
# One of these four sources declares a drive's content; the rest are
# per-drive modifiers.
_DRIVE_SOURCE_FIELDS = ("media", "size", "base", "hostdir")
_DRIVE_MODIFIER_FIELDS = ("controller", "enabled")
_DRIVE_FIELDS = frozenset(_DRIVE_SOURCE_FIELDS + _DRIVE_MODIFIER_FIELDS)
_DRIVE_KEY = re.compile(r"(floppy|hdd|cdrom)(\d+)?")
_SIZE = re.compile(r"([1-9][0-9]*)([KMGTkmgt])")
_SLOT_LIMITS = {"floppy": 2, "hdd": 4, "cdrom": 4}
_MIB = 1024 * 1024
_UNIT_BYTES = {
    "K": 1024,
    "M": _MIB,
    "G": 1024 * _MIB,
    "T": 1024 * 1024 * _MIB,
}


@dataclass(frozen=True)
class BlueprintDrive:
    """One normalized drive in a parsed machine blueprint.

    Exactly one content source is set — ``size`` (a blank image),
    ``media`` (an attached payload), ``base``/``base_type`` (an image
    materialized from a starting-point media item), or ``hostdir`` (a
    host directory served as a FAT drive) — unless the drive is an
    empty removable slot, when all four are ``None``. ``controller``
    and ``enabled`` are the per-drive modifiers.
    """

    key: str
    medium: str
    slot: int
    size: Optional[str] = None
    media: Optional[ResolvedMedia] = None
    base: Optional[ResolvedMedia] = None
    base_type: Optional[str] = None
    hostdir: Optional[str] = None
    controller: Optional[str] = None
    enabled: bool = True


@dataclass(frozen=True)
class Blueprint:
    """The immutable, normalized machine blueprint (full field set).

    ``parameters`` is read at script invocation and is not carried in
    the machine state; every other field resolves into the state.
    """

    platform: str
    backend: Optional[str] = None
    memory: Optional[int] = None
    cpus: Optional[int] = None
    drives: Mapping[str, BlueprintDrive] = field(default_factory=dict)
    boot: Tuple[str, ...] = ()
    name: Optional[str] = None
    description: Optional[str] = None
    scripts: Mapping[str, str] = field(default_factory=dict)
    control_planes: Tuple[str, ...] = ()
    backend_settings: Mapping[str, Mapping] = field(default_factory=dict)
    parameters: Mapping[str, object] = field(default_factory=dict)


def _nonempty_string(value, field_name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"{field_name} must be a non-empty string, got: "
            f"{value!r}")
    return value


def _size(value, field_name):
    if not isinstance(value, str):
        raise ValueError(
            f"{field_name} must be a size string, got: {value!r}")
    match = _SIZE.fullmatch(value)
    if not match:
        raise ValueError(
            f"{field_name} must be a positive integer followed by "
            f"K, M, G, or T, got: {value!r}")
    return f"{int(match.group(1))}{match.group(2).upper()}"


def _memory(value):
    if isinstance(value, bool):
        raise ValueError(
            "memory must be a positive integer MiB value or size string")
    if isinstance(value, int):
        if value <= 0:
            raise ValueError(
                "memory must be a positive integer MiB value")
        return value
    size = _size(value, "memory")
    match = _SIZE.fullmatch(size)
    byte_count = int(match.group(1)) * _UNIT_BYTES[match.group(2)]
    if byte_count % _MIB:
        raise ValueError(
            f"memory must resolve to a whole MiB value, got: {value!r}")
    return byte_count // _MIB


def _drive_key(value):
    if not isinstance(value, str):
        raise ValueError(
            f"drive keys must be strings, got: {value!r}")
    match = _DRIVE_KEY.fullmatch(value)
    if not match:
        raise ValueError(
            f"invalid drive key {value!r}: expected floppy[0..1], "
            "hdd[0..3], or cdrom[0..3]")
    medium = match.group(1)
    slot = int(match.group(2) or 0)
    limit = _SLOT_LIMITS[medium]
    if slot >= limit:
        raise ValueError(
            f"invalid drive key {value!r}: {medium} slots run from "
            f"0 to {limit - 1}")
    return medium, slot, f"{medium}{slot}"


def _controller(value, key, medium):
    if medium == "floppy":
        raise ValueError(
            f"drives.{key}.controller is invalid: floppies attach to "
            "the floppy controller and take no controller key")
    if not isinstance(value, str) or value not in _CONTROLLERS:
        allowed = ", ".join(sorted(_CONTROLLERS))
        raise ValueError(
            f"drives.{key}.controller must be one of {allowed}, "
            f"got: {value!r}")
    return value


def _enabled(value, key):
    if not isinstance(value, bool):
        raise ValueError(
            f"drives.{key}.enabled must be true or false, "
            f"got: {value!r}")
    return value


def _base(value, key, medium, context):
    """Return ``(ResolvedMedia, base_type)`` for a base drive source."""
    if medium == "cdrom":
        raise ValueError(
            f"drives.{key}.base is invalid: optical media is "
            "read-only, so a cdrom takes only a media reference "
            "or an empty slot")
    if isinstance(value, str):
        media_name, base_type = value, "difference"
    elif isinstance(value, collections.abc.Mapping):
        unknown = set(value) - {"media", "type"}
        if unknown:
            raise ValueError(
                f"unknown base field: drives.{key}.base."
                f"{sorted(unknown)[0]}")
        if "media" not in value:
            raise ValueError(
                f"drives.{key}.base requires a media name")
        media_name = value["media"]
        base_type = value.get("type", "difference")
        if base_type not in _BASE_TYPES:
            allowed = ", ".join(sorted(_BASE_TYPES))
            raise ValueError(
                f"drives.{key}.base.type must be one of {allowed}, "
                f"got: {base_type!r}")
    else:
        raise ValueError(
            f"drives.{key}.base must be a media name or an object")
    media_name = _nonempty_string(media_name, f"drives.{key}.base.media")
    return resolve_media(media_name, context=context), base_type


def _hostdir(value, key, medium):
    if medium == "cdrom":
        raise ValueError(
            f"drives.{key}.hostdir is invalid: a cdrom cannot present "
            "a host directory (no ISO9660 synthesis)")
    return _nonempty_string(value, f"drives.{key}.hostdir")


def _drive(value, key, medium, slot, context):
    if value is None:
        if medium == "hdd":
            raise ValueError(
                f"drives.{key} cannot be null: only removable drives "
                "(floppy, cdrom) may be declared empty")
        return BlueprintDrive(key=key, medium=medium, slot=slot)
    if isinstance(value, str):
        value = {"media": value}
    if not isinstance(value, collections.abc.Mapping):
        raise ValueError(
            f"drives.{key} must be a media name or drive object")
    unknown = set(value) - _DRIVE_FIELDS
    if unknown:
        field_name = sorted(unknown)[0]
        raise ValueError(f"unknown drive field: drives.{key}.{field_name}")
    sources = [name for name in _DRIVE_SOURCE_FIELDS if name in value]
    if len(sources) != 1:
        raise ValueError(
            f"drives.{key} must declare exactly one of "
            "media, size, base, or hostdir")
    controller = (_controller(value["controller"], key, medium)
                  if "controller" in value else None)
    enabled = (_enabled(value["enabled"], key)
               if "enabled" in value else True)
    common = dict(key=key, medium=medium, slot=slot,
                  controller=controller, enabled=enabled)
    source = sources[0]
    if source == "size":
        if medium == "cdrom":
            raise ValueError(
                f"drives.{key}.size is invalid: optical media is "
                "read-only, so a cdrom takes only a media reference "
                "or an empty slot")
        return BlueprintDrive(
            size=_size(value["size"], f"drives.{key}.size"), **common)
    if source == "base":
        media, base_type = _base(value["base"], key, medium, context)
        return BlueprintDrive(base=media, base_type=base_type, **common)
    if source == "hostdir":
        return BlueprintDrive(
            hostdir=_hostdir(value["hostdir"], key, medium), **common)
    media_name = _nonempty_string(value["media"], f"drives.{key}.media")
    return BlueprintDrive(
        media=resolve_media(media_name, context=context), **common)


def _drives(value, context):
    if not isinstance(value, collections.abc.Mapping):
        raise ValueError("drives must be an object")
    normalized = {}
    claimed = {}
    for authored_key, declaration in value.items():
        medium, slot, key = _drive_key(authored_key)
        if key in claimed:
            raise ValueError(
                f"drive key clash: {claimed[key]!r} and "
                f"{authored_key!r} both mean {key}")
        claimed[key] = authored_key
        normalized[key] = _drive(
            declaration, key, medium, slot, context)
    return types.MappingProxyType(normalized)


def _default_boot(drives):
    enabled = {key: drive for key, drive in drives.items()
               if drive.enabled}
    for key in ("floppy0", "hdd0"):
        if key in enabled:
            return (key,)
    cdroms = [drive.key for drive in enabled.values()
              if drive.medium == "cdrom"]
    if cdroms:
        return (min(cdroms, key=lambda key: enabled[key].slot),)
    return ()


def _boot(value, drives):
    if not isinstance(value, list):
        raise ValueError("boot must be an array of drive keys")
    normalized = []
    seen = set()
    for index, authored_key in enumerate(value):
        _, _, key = _drive_key(authored_key)
        if key not in drives:
            raise ValueError(
                f"boot[{index}] references undeclared drive {key}")
        if not drives[key].enabled:
            raise ValueError(
                f"boot[{index}] references disabled drive {key}")
        if key in seen:
            raise ValueError(f"boot contains duplicate drive {key}")
        seen.add(key)
        normalized.append(key)
    return tuple(normalized)


def _scripts(value):
    if not isinstance(value, collections.abc.Mapping):
        raise ValueError("scripts must be an object")
    normalized = {}
    for label, script in value.items():
        label = _nonempty_string(label, "scripts label")
        script = _nonempty_string(script, f"scripts.{label}")
        if (script in (".", "..") or "/" in script or "\\" in script
                or script.lower().endswith(".rlqs")):
            raise ValueError(
                f"scripts.{label} must be the file stem under "
                f"scripts/, got: {script!r}")
        normalized[label] = script
    return types.MappingProxyType(normalized)


def _backend(value):
    if not isinstance(value, str) or value not in _BACKENDS:
        allowed = ", ".join(sorted(_BACKENDS))
        raise ValueError(
            f"backend must be one of {allowed}, got: {value!r}")
    return value


def _cpus(value):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(
            f"cpus must be a positive integer, got: {value!r}")
    if value <= 0:
        raise ValueError(
            f"cpus must be a positive integer, got: {value!r}")
    return value


def _control_planes(value):
    if not isinstance(value, list):
        raise ValueError("control-planes must be an array of strings")
    normalized = []
    seen = set()
    for entry in value:
        if not isinstance(entry, str) or entry not in _CONTROL_PLANES:
            allowed = ", ".join(sorted(_CONTROL_PLANES))
            raise ValueError(
                f"control-planes entries must be one of {allowed}, "
                f"got: {entry!r}")
        if entry in seen:
            raise ValueError(
                f"control-planes contains duplicate entry {entry!r}")
        seen.add(entry)
        normalized.append(entry)
    return tuple(normalized)


def _backend_settings(value):
    if not isinstance(value, collections.abc.Mapping):
        raise ValueError("backend-settings must be an object")
    normalized = {}
    for backend_name, section in value.items():
        if backend_name not in _BACKENDS:
            allowed = ", ".join(sorted(_BACKENDS))
            raise ValueError(
                f"backend-settings names unknown backend "
                f"{backend_name!r}; expected one of {allowed}")
        if not isinstance(section, collections.abc.Mapping):
            raise ValueError(
                f"backend-settings.{backend_name} must be an object")
        # Each backend adapter defines and validates its own section's
        # keys (machine-blueprint-reference.md); the parser preserves
        # the structure and defers key-level checks to the adapter seam
        # (ROADMAP milestone 9).
        normalized[backend_name] = types.MappingProxyType(dict(section))
    return types.MappingProxyType(normalized)


def _parameters(value):
    if not isinstance(value, collections.abc.Mapping):
        raise ValueError("parameters must be an object")
    normalized = {}
    for key, binding in value.items():
        key = _nonempty_string(key, "parameters key")
        if isinstance(binding, str):
            normalized[key] = binding
        elif isinstance(binding, collections.abc.Mapping):
            if set(binding) != {"property"}:
                raise ValueError(
                    f"parameters.{key} must be a string or a "
                    '{"property": "<key>"} redirect')
            target = _nonempty_string(
                binding["property"], f"parameters.{key}.property")
            normalized[key] = types.MappingProxyType({"property": target})
        else:
            raise ValueError(
                f"parameters.{key} must be a string or a "
                '{"property": "<key>"} redirect')
    return types.MappingProxyType(normalized)


def parse_blueprint(value, context=None):
    """Parse, validate, and resolve one machine blueprint object.

    Enforces the full field-reference format checks (planning/design/
    machine-blueprint-reference.md). Media references (``media`` and
    ``base.media``) resolve against the effective home's media library
    but are not fetched. State-only fields are rejected; unknown fields
    are rejected. Backend-specific capability checks belong with
    backend assignment at materialization (ROADMAP milestone 9); QEMU,
    the only implemented backend, satisfies the whole vocabulary.
    """
    if not isinstance(value, collections.abc.Mapping):
        raise ValueError(
            "machine blueprint must be a JSON object, got "
            f"{type(value).__name__}")
    unknown = set(value) - _FIELDS
    if unknown:
        bad = sorted(unknown)[0]
        if bad in _STATE_ONLY:
            raise ValueError(
                f"{bad} is a state-only field and is not valid in a "
                "blueprint")
        raise ValueError(f"unknown blueprint field: {bad}")
    if "platform" not in value:
        raise KeyError("platform is required")
    platform = _nonempty_string(value["platform"], "platform")
    if platform not in _PLATFORMS:
        supported = ", ".join(sorted(_PLATFORMS))
        raise ValueError(
            f"platform must be one of {supported}, got: {platform!r}")
    drives = (_drives(value["drives"], context)
              if "drives" in value
              else types.MappingProxyType({}))
    empty = types.MappingProxyType({})
    return Blueprint(
        platform=platform,
        backend=(_backend(value["backend"])
                 if "backend" in value else None),
        memory=(_memory(value["memory"])
                if "memory" in value else None),
        cpus=(_cpus(value["cpus"]) if "cpus" in value else None),
        drives=drives,
        boot=(_boot(value["boot"], drives)
              if "boot" in value else _default_boot(drives)),
        name=(_nonempty_string(value["name"], "name")
              if "name" in value else None),
        description=(_nonempty_string(value["description"], "description")
                     if "description" in value else None),
        scripts=(_scripts(value["scripts"])
                 if "scripts" in value else empty),
        control_planes=(_control_planes(value["control-planes"])
                        if "control-planes" in value else ()),
        backend_settings=(_backend_settings(value["backend-settings"])
                          if "backend-settings" in value else empty),
        parameters=(_parameters(value["parameters"])
                    if "parameters" in value else empty),
    )


def load_blueprint(path, context=None):
    """Load, parse, and resolve one machine blueprint JSON file."""
    path = os.path.abspath(os.fspath(path))
    if not os.path.exists(path):
        raise FileNotFoundError(f"Machine blueprint not found: {path}")
    with open(path, "r", encoding="utf-8") as handle:
        value = jsonc.load(handle)
    return parse_blueprint(value, context=context)


def new_blueprint(name, *, platform="dos", context=None):
    """Create a new blueprint file with reasonable defaults.

    Returns the path to the created file. Raises FileExistsError if
    the blueprint already exists.
    """
    from .home import blueprints_dir
    path = os.path.join(blueprints_dir(context), f"{name}.rlqb")
    if os.path.exists(path):
        raise FileExistsError(f"blueprint already exists: {path}")
    # Check for legacy home .json
    if os.path.exists(os.path.join(blueprints_dir(context), f"{name}.json")):
        raise FileExistsError(f"legacy blueprint already exists: {name}.json")

    # Scaffolding default. Blueprints carry no version field
    # (machine-blueprint.md "Format stability"); the fields written
    # here must all be valid per the field reference.
    data = {
        "platform": platform,
        "memory": 16 if platform == "dos" else 64,
        "drives": {
            "hdd": {"size": "256M"}
        },
        "scripts": {}
    }

    import json
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        # Add a helpful header comment if the user is using it as a template
        handle.write("// Machine blueprint for " + name + "\n")
        json.dump(data, handle, indent=4)
        handle.write("\n")

    return path


def delete_blueprint(name, *, context=None):
    """Remove the home blueprint file for ``name``.

    Fails closed while any machine of the blueprint exists,
    naming their ids. Never deletes package builtins — only a
    file under ``blueprints/``. Returns the removed path.
    """
    from .home import blueprints_dir
    from .machines import list_machines

    machines = list_machines(context, blueprint=name)
    if machines:
        ids = ", ".join(machine["id"] for machine in machines)
        raise RuntimeError(
            f"blueprint {name!r} still has "
            f"{len(machines)} machine(s):\n"
            f"  {ids}\n"
            "destroy them first, then delete the blueprint")

    path = None
    for extension in (".rlqb", ".json"):
        candidate = os.path.join(
            blueprints_dir(context), f"{name}{extension}")
        if os.path.isfile(candidate):
            path = candidate
            break
    if path is None:
        raise FileNotFoundError(
            f"blueprint not found: {name}.rlqb\n"
            f"expected under {blueprints_dir(context)}")
    os.remove(path)
    return path
