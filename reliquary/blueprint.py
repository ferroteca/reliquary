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
    "platform", "memory", "drives", "boot", "name",
    "description", "scripts",
}
_PLATFORMS = {"dos", "openbsd", "win9x", "winnt"}
_DRIVE_FIELDS = {"size", "media"}
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
    """One normalized drive in a parsed machine blueprint."""

    key: str
    medium: str
    slot: int
    size: Optional[str] = None
    media: Optional[ResolvedMedia] = None


@dataclass(frozen=True)
class Blueprint:
    """The immutable, normalized milestone-1 blueprint subset."""

    platform: str
    memory: Optional[int] = None
    drives: Mapping[str, BlueprintDrive] = field(default_factory=dict)
    boot: Tuple[str, ...] = ()
    name: Optional[str] = None
    description: Optional[str] = None
    scripts: Mapping[str, str] = field(default_factory=dict)


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
    sources = [name for name in _DRIVE_FIELDS if name in value]
    if len(sources) != 1:
        raise ValueError(
            f"drives.{key} must declare exactly one of media or size")
    if sources[0] == "size":
        if medium == "cdrom":
            raise ValueError(
                f"drives.{key}.size is invalid: a blank image may "
                "only be a floppy or hard disk")
        return BlueprintDrive(
            key=key, medium=medium, slot=slot,
            size=_size(value["size"], f"drives.{key}.size"))
    media_name = _nonempty_string(
        value["media"], f"drives.{key}.media")
    return BlueprintDrive(
        key=key, medium=medium, slot=slot,
        media=resolve_media(media_name, context=context))


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
    for key in ("floppy0", "hdd0"):
        if key in drives:
            return (key,)
    cdroms = [drive.key for drive in drives.values()
              if drive.medium == "cdrom"]
    if cdroms:
        return (min(cdroms, key=lambda key: drives[key].slot),)
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


def parse_blueprint(value, context=None):
    """Parse, validate, and resolve one machine blueprint object.

    This implements the milestone-1 subset. Media references resolve
    against the effective home's media library but are not fetched.
    Fields reserved for later milestones are rejected as unknown.
    """
    if not isinstance(value, collections.abc.Mapping):
        raise ValueError(
            "machine blueprint must be a JSON object, got "
            f"{type(value).__name__}")
    unknown = set(value) - _FIELDS
    if unknown:
        raise ValueError(f"unknown blueprint field: {sorted(unknown)[0]}")
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
    memory = (_memory(value["memory"])
              if "memory" in value else None)
    name = (_nonempty_string(value["name"], "name")
            if "name" in value else None)
    description = (
        _nonempty_string(value["description"], "description")
        if "description" in value else None)
    return Blueprint(
        platform=platform,
        memory=memory,
        drives=drives,
        boot=(_boot(value["boot"], drives)
              if "boot" in value else _default_boot(drives)),
        name=name,
        description=description,
        scripts=(_scripts(value["scripts"])
                 if "scripts" in value
                 else types.MappingProxyType({})),
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

    # Scaffolding default (ROADMAP milestone 5)
    # In a future step, this could load a template based on the platform.
    data = {
        "version": 1,
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
