# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""The composed blueprint document: parsing into named components.

A ``.rlqb`` document is a bag of named components — ``machine`` /
``media`` / ``source`` / ``archive`` — in plural sections
(``machines``/``media``/``sources``/``archives``), or a bare-root lone
machine. This module parses one document into a :class:`Document` of
typed components without resolving cross-references between them;
whole-source name resolution (binding a drive to its media, a media to
its source, a from-archive locator to its archive) is a separate layer.

Design: planning/design/blueprint-model.md (normative), with the
machine-checkable companion planning/design/blueprint.schema.json.
"""

import collections.abc
import os
import re
import types
from dataclasses import dataclass, field
from typing import Mapping, Optional, Tuple

from . import jsonc

_SECTIONS = ("machines", "media", "sources", "archives")
_PLATFORMS = {"dos", "openbsd", "win9x", "winnt"}
_BACKENDS = {"qemu", "virtualbox", "vmware", "hyperv"}
_CONTROLLERS = {"ide", "sata", "scsi", "nvme", "virtio"}
_CONTROL_PLANES = {"agentless-display", "vnc", "serial-console", "guest-agent"}
_MATERIALIZE = {"new", "difference", "copy", "use"}
# ``new`` has no source; the payload-bearing modes require one.
_SOURCED_MATERIALIZE = {"difference", "copy", "use"}

_DRIVE_KEY = re.compile(r"(floppy|hdd|cdrom)(\d+)?")
_SLOT_LIMITS = {"floppy": 2, "hdd": 4, "cdrom": 4}
_SIZE = re.compile(r"([1-9][0-9]*)([KMGTkmgt])")
_SHA256 = re.compile(r"[0-9a-fA-F]{64}")
_MIB = 1024 * 1024
_UNIT_BYTES = {"K": 1024, "M": _MIB, "G": 1024 * _MIB, "T": 1024 * 1024 * _MIB}


# --- component model -------------------------------------------------

@dataclass(frozen=True)
class Locator:
    """Where bytes come from. Exactly one ``kind``.

    ``url`` — one or more mirror URLs; ``local`` — a host path;
    ``archive`` — a from-archive extraction (``archive`` name + member
    ``path``); ``ref`` — a by-name reference to a source or archive
    component. ``sha256`` may accompany an inline locator.
    """

    kind: str
    urls: Tuple[str, ...] = ()
    local: Optional[str] = None
    archive: Optional[str] = None
    path: Optional[str] = None
    ref: Optional[str] = None
    sha256: Optional[str] = None


@dataclass(frozen=True)
class Source:
    """A named standalone locator (the ``sources`` section)."""

    name: str
    locator: Locator


@dataclass(frozen=True)
class Media:
    """A media component: owns content and materialization.

    ``read_only`` is ``None`` when unset (its effective default —
    true on a cdrom, false elsewhere — is resolved at materialization).
    """

    name: str
    materialize: str = "use"
    size: Optional[str] = None
    source: Optional[Locator] = None
    sha256: Optional[str] = None
    read_only: Optional[bool] = None
    extension: Optional[str] = None


@dataclass(frozen=True)
class Archive:
    """A named container: a ``source`` locator plus an optional hash.

    The recursive ``members`` tree is flattened at parse time into the
    document's media and (nested) archive components; this object is the
    container itself.
    """

    name: str
    source: Locator
    sha256: Optional[str] = None


@dataclass(frozen=True)
class MachineDrive:
    """One drive slot: names a media, or ``None`` for an empty slot."""

    key: str
    medium: str
    slot: int
    media: Optional[str] = None
    controller: Optional[str] = None
    enabled: bool = True


@dataclass(frozen=True)
class Machine:
    """Machine topology. Drives name media; content lives on the media."""

    name: str
    platform: str
    backend: Optional[str] = None
    memory: Optional[int] = None
    cpus: Optional[int] = None
    drives: Mapping[str, MachineDrive] = field(default_factory=dict)
    boot: Tuple[str, ...] = ()
    description: Optional[str] = None
    scripts: Mapping[str, str] = field(default_factory=dict)
    control_planes: Tuple[str, ...] = ()
    backend_settings: Mapping[str, Mapping] = field(default_factory=dict)
    parameters: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class Document:
    """One parsed ``.rlqb`` document: components by name, per type."""

    machines: Mapping[str, Machine] = field(default_factory=dict)
    media: Mapping[str, Media] = field(default_factory=dict)
    sources: Mapping[str, Source] = field(default_factory=dict)
    archives: Mapping[str, Archive] = field(default_factory=dict)


# --- small validators ------------------------------------------------

def _nonempty_string(value, field_name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"{field_name} must be a non-empty string, got: {value!r}")
    return value


def _sha256(value, field_name):
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ValueError(
            f"{field_name} must be a hex SHA-256 (64 hex chars), "
            f"got: {value!r}")
    return value.lower()


def _size(value, field_name):
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a size string, got: {value!r}")
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
            raise ValueError("memory must be a positive integer MiB value")
        return value
    size = _size(value, "memory")
    match = _SIZE.fullmatch(size)
    byte_count = int(match.group(1)) * _UNIT_BYTES[match.group(2)]
    if byte_count % _MIB:
        raise ValueError(
            f"memory must resolve to a whole MiB value, got: {value!r}")
    return byte_count // _MIB


def _stem(name):
    """The identity stem of a filename or member path: basename, no ext."""
    base = name.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
    root, dot, _ext = base.rpartition(".")
    return root if dot else base


def _url_filename(url):
    tail = url.split("#", 1)[0].split("?", 1)[0]
    return tail.rstrip("/").rsplit("/", 1)[-1]


# --- locators --------------------------------------------------------

def _locator(value, where):
    """Parse a locator value (a media/archive ``source``).

    A string is a by-name reference to a source or archive component.
    An object is an inline locator: exactly one of ``url`` / ``local`` /
    (``archive`` + ``path``), with an optional ``sha256``.
    """
    if isinstance(value, str):
        return Locator(kind="ref", ref=_nonempty_string(value, where))
    if not isinstance(value, collections.abc.Mapping):
        raise ValueError(
            f"{where} must be a component name or a locator object, "
            f"got: {value!r}")
    return _inline_locator(value, where)


def _inline_locator(value, where):
    unknown = set(value) - {"url", "local", "archive", "path", "sha256"}
    if unknown:
        raise ValueError(f"unknown locator field: {where}.{sorted(unknown)[0]}")
    forms = [name for name in ("url", "local", "archive") if name in value]
    if len(forms) != 1:
        raise ValueError(
            f"{where} must declare exactly one of url, local, or archive")
    sha = _sha256(value["sha256"], f"{where}.sha256") if "sha256" in value \
        else None
    form = forms[0]
    if form == "url":
        return Locator(kind="url", urls=_urls(value["url"], f"{where}.url"),
                       sha256=sha)
    if form == "local":
        return Locator(kind="local",
                       local=_nonempty_string(value["local"], f"{where}.local"),
                       sha256=sha)
    if "path" not in value:
        raise ValueError(
            f"{where} from-archive locator requires a member path")
    return Locator(
        kind="archive",
        archive=_nonempty_string(value["archive"], f"{where}.archive"),
        path=_nonempty_string(value["path"], f"{where}.path"),
        sha256=sha)


def _urls(value, where):
    if isinstance(value, str):
        return (_nonempty_string(value, where),)
    if isinstance(value, list) and value:
        return tuple(_nonempty_string(entry, f"{where}[{i}]")
                     for i, entry in enumerate(value))
    raise ValueError(
        f"{where} must be a URL string or a non-empty list of mirror URLs")


def _locator_stem(locator, where):
    """Derive a component name from a locator's filename, or fail."""
    if locator.kind == "url":
        return _stem(_url_filename(locator.urls[0]))
    if locator.kind == "local":
        return _stem(locator.local)
    if locator.kind == "archive":
        return _stem(locator.path)
    if locator.kind == "ref":
        return locator.ref
    raise ValueError(
        f"{where} has no filename to derive a name from; give it an "
        "explicit name")


# --- media, sources, archives ----------------------------------------

_MEDIA_FIELDS = {"name", "materialize", "size", "source", "sha256",
                 "read-only", "extension"}


def _read_only(value, where):
    if not isinstance(value, bool):
        raise ValueError(f"{where} must be true or false, got: {value!r}")
    return value


def _media(value, register):
    if not isinstance(value, collections.abc.Mapping):
        raise ValueError(f"media entry must be an object, got: {value!r}")
    unknown = set(value) - _MEDIA_FIELDS
    if unknown:
        raise ValueError(f"unknown media field: {sorted(unknown)[0]}")
    materialize = value.get("materialize", "use")
    if materialize not in _MATERIALIZE:
        allowed = ", ".join(sorted(_MATERIALIZE))
        raise ValueError(
            f"media materialize must be one of {allowed}, got: "
            f"{materialize!r}")
    source = _locator(value["source"], "media source") \
        if "source" in value else None
    if materialize == "new":
        if source is not None:
            raise ValueError("a 'new' media takes a size, not a source")
        if "size" not in value:
            raise ValueError("a 'new' media requires a size")
    else:
        if source is None:
            raise ValueError(
                f"a '{materialize}' media requires a source")
        if "size" in value:
            raise ValueError(
                f"a '{materialize}' media takes a source, not a size")
    if "name" in value:
        name = _nonempty_string(value["name"], "media name")
    elif source is not None:
        name = _locator_stem(source, "media source")
    else:
        raise ValueError("a 'new' media has no source and requires a name")
    register("media", name, Media(
        name=name,
        materialize=materialize,
        size=_size(value["size"], "media size") if "size" in value else None,
        source=source,
        sha256=_sha256(value["sha256"], "media sha256")
        if "sha256" in value else None,
        read_only=_read_only(value["read-only"], "media read-only")
        if "read-only" in value else None,
        extension=_nonempty_string(value["extension"], "media extension")
        if "extension" in value else None))


def _source(value, register):
    if not isinstance(value, collections.abc.Mapping):
        raise ValueError(f"source entry must be an object, got: {value!r}")
    body = {k: v for k, v in value.items() if k != "name"}
    locator = _inline_locator(body, "source")
    name = _nonempty_string(value["name"], "source name") \
        if "name" in value else _locator_stem(locator, "source")
    register("sources", name, Source(name=name, locator=locator))


_ARCHIVE_FIELDS = {"name", "source", "sha256", "members"}
_MEMBER_LEAF_FIELDS = {"materialize", "read-only", "extension"}


def _archive(value, register):
    if not isinstance(value, collections.abc.Mapping):
        raise ValueError(f"archive entry must be an object, got: {value!r}")
    unknown = set(value) - _ARCHIVE_FIELDS
    if unknown:
        raise ValueError(f"unknown archive field: {sorted(unknown)[0]}")
    if "source" not in value:
        raise ValueError("an archive requires a source")
    locator = _locator(value["source"], "archive source")
    name = _nonempty_string(value["name"], "archive name") \
        if "name" in value else _locator_stem(locator, "archive source")
    sha = _sha256(value["sha256"], "archive sha256") \
        if "sha256" in value else None
    register("archives", name, Archive(name=name, source=locator, sha256=sha))
    for member in _member_list(value.get("members", []), name):
        _member(member, name, register)


def _member_list(value, archive_name):
    if not isinstance(value, list):
        raise ValueError(
            f"archive {archive_name!r} members must be an array")
    return value


def _member(value, parent, register):
    if not isinstance(value, collections.abc.Mapping):
        raise ValueError(f"archive member must be an object, got: {value!r}")
    allowed = {"path", "name", "members"} | _MEMBER_LEAF_FIELDS | {"sha256"}
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(f"unknown member field: {sorted(unknown)[0]}")
    if "path" not in value:
        raise ValueError("an archive member requires a path")
    path = _nonempty_string(value["path"], "member path")
    source = Locator(kind="archive", archive=parent, path=path)
    name = _nonempty_string(value["name"], "member name") \
        if "name" in value else _stem(path)
    sha = _sha256(value["sha256"], "member sha256") \
        if "sha256" in value else None
    if "members" in value:
        leaf = _MEMBER_LEAF_FIELDS & set(value)
        if leaf:
            raise ValueError(
                f"archive member {name!r} has members, so it is a nested "
                f"archive and cannot take {sorted(leaf)[0]!r}")
        register("archives", name, Archive(name=name, source=source, sha256=sha))
        for sub in _member_list(value["members"], name):
            _member(sub, name, register)
        return
    materialize = value.get("materialize", "use")
    if materialize not in _SOURCED_MATERIALIZE:
        allowed = ", ".join(sorted(_SOURCED_MATERIALIZE))
        raise ValueError(
            f"archive-member media materialize must be one of {allowed}, "
            f"got: {materialize!r}")
    register("media", name, Media(
        name=name, materialize=materialize, source=source, sha256=sha,
        read_only=_read_only(value["read-only"], "member read-only")
        if "read-only" in value else None,
        extension=_nonempty_string(value["extension"], "member extension")
        if "extension" in value else None))


# --- machine ---------------------------------------------------------

_MACHINE_FIELDS = {
    "name", "platform", "backend", "memory", "cpus", "drives", "boot",
    "description", "scripts", "control-planes", "backend-settings",
    "parameters",
}
_STATE_ONLY = {"id", "backend-id", "blueprint-digest", "blueprint-source"}
_DRIVE_FIELDS = {"media", "controller", "enabled"}


def _drive_key(value):
    if not isinstance(value, str):
        raise ValueError(f"drive keys must be strings, got: {value!r}")
    match = _DRIVE_KEY.fullmatch(value)
    if not match:
        raise ValueError(
            f"invalid drive key {value!r}: expected floppy[0..1], "
            "hdd[0..3], or cdrom[0..3]")
    medium = match.group(1)
    slot = int(match.group(2) or 0)
    if slot >= _SLOT_LIMITS[medium]:
        raise ValueError(
            f"invalid drive key {value!r}: {medium} slots run from "
            f"0 to {_SLOT_LIMITS[medium] - 1}")
    return medium, slot, f"{medium}{slot}"


def _controller(value, key, medium):
    if medium == "floppy":
        raise ValueError(
            f"drives.{key}.controller is invalid: floppies take no "
            "controller key")
    if not isinstance(value, str) or value not in _CONTROLLERS:
        allowed = ", ".join(sorted(_CONTROLLERS))
        raise ValueError(
            f"drives.{key}.controller must be one of {allowed}, "
            f"got: {value!r}")
    return value


def _drive(value, key, medium, slot):
    if value is None:
        if medium == "hdd":
            raise ValueError(
                f"drives.{key} cannot be null: only removable drives "
                "(floppy, cdrom) may be declared empty")
        return MachineDrive(key=key, medium=medium, slot=slot)
    if isinstance(value, str):
        value = {"media": value}
    if not isinstance(value, collections.abc.Mapping):
        raise ValueError(
            f"drives.{key} must be a media name, null, or a drive object")
    unknown = set(value) - _DRIVE_FIELDS
    if unknown:
        raise ValueError(f"unknown drive field: drives.{key}.{sorted(unknown)[0]}")
    if "media" not in value:
        raise ValueError(
            f"drives.{key} must name a media (or be null for an empty "
            "removable slot)")
    controller = (_controller(value["controller"], key, medium)
                  if "controller" in value else None)
    enabled = value.get("enabled", True)
    if not isinstance(enabled, bool):
        raise ValueError(
            f"drives.{key}.enabled must be true or false, got: {enabled!r}")
    return MachineDrive(
        key=key, medium=medium, slot=slot,
        media=_nonempty_string(value["media"], f"drives.{key}.media"),
        controller=controller, enabled=enabled)


def _drives(value):
    if not isinstance(value, collections.abc.Mapping):
        raise ValueError("drives must be an object")
    normalized = {}
    claimed = {}
    for authored_key, declaration in value.items():
        medium, slot, key = _drive_key(authored_key)
        if key in claimed:
            raise ValueError(
                f"drive key clash: {claimed[key]!r} and {authored_key!r} "
                f"both mean {key}")
        claimed[key] = authored_key
        normalized[key] = _drive(declaration, key, medium, slot)
    return types.MappingProxyType(normalized)


def _default_boot(drives):
    enabled = {key: drive for key, drive in drives.items() if drive.enabled}
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
    normalized, seen = [], set()
    for index, authored_key in enumerate(value):
        _, _, key = _drive_key(authored_key)
        if key not in drives:
            raise ValueError(f"boot[{index}] references undeclared drive {key}")
        if not drives[key].enabled:
            raise ValueError(f"boot[{index}] references disabled drive {key}")
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
                f"scripts.{label} must be the file stem under scripts/, "
                f"got: {script!r}")
        normalized[label] = script
    return types.MappingProxyType(normalized)


def _backend(value):
    if not isinstance(value, str) or value not in _BACKENDS:
        allowed = ", ".join(sorted(_BACKENDS))
        raise ValueError(f"backend must be one of {allowed}, got: {value!r}")
    return value


def _cpus(value):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"cpus must be a positive integer, got: {value!r}")
    return value


def _control_planes(value):
    if not isinstance(value, list):
        raise ValueError("control-planes must be an array of strings")
    normalized, seen = [], set()
    for entry in value:
        if not isinstance(entry, str) or entry not in _CONTROL_PLANES:
            allowed = ", ".join(sorted(_CONTROL_PLANES))
            raise ValueError(
                f"control-planes entries must be one of {allowed}, "
                f"got: {entry!r}")
        if entry in seen:
            raise ValueError(f"control-planes contains duplicate {entry!r}")
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
                f"backend-settings names unknown backend {backend_name!r}; "
                f"expected one of {allowed}")
        if not isinstance(section, collections.abc.Mapping):
            raise ValueError(
                f"backend-settings.{backend_name} must be an object")
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
            normalized[key] = types.MappingProxyType(
                {"property": _nonempty_string(
                    binding["property"], f"parameters.{key}.property")})
        else:
            raise ValueError(
                f"parameters.{key} must be a string or a "
                '{"property": "<key>"} redirect')
    return types.MappingProxyType(normalized)


def _machine(value, register, *, name=None):
    if not isinstance(value, collections.abc.Mapping):
        raise ValueError("a machine must be a JSON object")
    unknown = set(value) - _MACHINE_FIELDS
    if unknown:
        bad = sorted(unknown)[0]
        if bad in _STATE_ONLY:
            raise ValueError(
                f"{bad} is a state-only field and is not valid in a blueprint")
        raise ValueError(f"unknown machine field: {bad}")
    if "platform" not in value:
        raise KeyError("platform is required")
    platform = _nonempty_string(value["platform"], "platform")
    if platform not in _PLATFORMS:
        allowed = ", ".join(sorted(_PLATFORMS))
        raise ValueError(f"platform must be one of {allowed}, got: {platform!r}")
    if "name" in value:
        name = _nonempty_string(value["name"], "name")
    if name is None:
        raise ValueError("a machine in a machines[] list requires a name")
    drives = _drives(value["drives"]) if "drives" in value \
        else types.MappingProxyType({})
    empty = types.MappingProxyType({})
    register("machines", name, Machine(
        name=name,
        platform=platform,
        backend=_backend(value["backend"]) if "backend" in value else None,
        memory=_memory(value["memory"]) if "memory" in value else None,
        cpus=_cpus(value["cpus"]) if "cpus" in value else None,
        drives=drives,
        boot=_boot(value["boot"], drives) if "boot" in value
        else _default_boot(drives),
        description=_nonempty_string(value["description"], "description")
        if "description" in value else None,
        scripts=_scripts(value["scripts"]) if "scripts" in value else empty,
        control_planes=_control_planes(value["control-planes"])
        if "control-planes" in value else (),
        backend_settings=_backend_settings(value["backend-settings"])
        if "backend-settings" in value else empty,
        parameters=_parameters(value["parameters"])
        if "parameters" in value else empty))


# --- document --------------------------------------------------------

_SECTION_PARSERS = {
    "machines": _machine,
    "media": _media,
    "sources": _source,
    "archives": _archive,
}


def parse_document(value, *, stem=None):
    """Parse one ``.rlqb`` document into typed, named components.

    A bare-root object (no section keys) is a single machine; ``stem``
    supplies its name when it declares none. A sectioned object holds
    plural component lists. Cross-references are recorded by name and
    resolved by a later whole-source pass, not here. Two components of
    one type and name in this document are an error.
    """
    if not isinstance(value, collections.abc.Mapping):
        raise ValueError(
            f"a blueprint must be a JSON object, got {type(value).__name__}")
    buckets = {section: {} for section in _SECTIONS}

    def register(section, name, component):
        bucket = buckets[section]
        if name in bucket:
            raise ValueError(
                f"duplicate {section[:-1]} name {name!r} in one document")
        bucket[name] = component

    if set(value) & set(_SECTIONS):
        unknown = set(value) - set(_SECTIONS)
        if unknown:
            raise ValueError(f"unknown document section: {sorted(unknown)[0]}")
        for section in _SECTIONS:
            entries = value.get(section)
            if entries is None:
                continue
            if not isinstance(entries, list):
                raise ValueError(f"{section} must be an array")
            parser = _SECTION_PARSERS[section]
            for entry in entries:
                parser(entry, register)
    else:
        _machine(value, register, name=stem)

    return Document(
        machines=types.MappingProxyType(buckets["machines"]),
        media=types.MappingProxyType(buckets["media"]),
        sources=types.MappingProxyType(buckets["sources"]),
        archives=types.MappingProxyType(buckets["archives"]))


def load_document(path):
    """Load and parse one ``.rlqb`` document; the file stem names a
    bare-root machine that declares no name of its own."""
    path = os.path.abspath(os.fspath(path))
    if not os.path.exists(path):
        raise FileNotFoundError(f"blueprint not found: {path}")
    with open(path, "r", encoding="utf-8") as handle:
        value = jsonc.load(handle)
    return parse_document(value, stem=_stem(os.path.basename(path)))
