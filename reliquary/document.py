# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""The composed blueprint document: parsing specs into one catalog.

A ``.rlqb`` root is an array of **specs** of two types — ``machine``
and ``media`` — with a lone spec object accepted as sugar for the array
of one. ``type`` defaults to ``media``. This module parses one document
into a :class:`Document` without resolving cross-references between
documents; whole-source resolution (binding a drive to its media, a
child to its parent) is ``resolve.py``.

Validation is **two-phase**: shape here, value at resolution. A field
carrying a ``${...}`` reference cannot be coerced until the reference
binds, so it is parsed into a :class:`Deferred` and finished later.

Design: docs/spec/blueprint-model.md (normative).
"""

import collections.abc
import os
import re
import types
import warnings
from dataclasses import dataclass, field
from typing import Mapping, Optional, Tuple, Union

from . import jsonc

_PLATFORMS = {"dos", "openbsd", "win9x", "winnt"}
_BACKENDS = {"qemu", "virtualbox", "vmware", "hyperv"}
_CONTROLLERS = {"ide", "sata", "scsi", "nvme", "virtio"}
_CONTROL_PLANES = {"agentless-display", "vnc", "serial-console", "guest-agent"}
_MATERIALIZE = {"new", "difference", "copy", "use"}
_SPEC_TYPES = {"machine", "media"}
# Retired with the first-round four-component model; named so a stale
# document is diagnosed rather than merely rejected.
_RETIRED_TYPES = {"source", "archive"}
_RETIRED_SECTIONS = {"machines", "media", "sources", "archives"}

_DRIVE_KEY = re.compile(r"(floppy|hdd|cdrom)(\d+)?")
_SLOT_LIMITS = {"floppy": 2, "hdd": 4, "cdrom": 4}
_SIZE = re.compile(r"([1-9][0-9]*)([KMGTkmgt])")
_SHA256 = re.compile(r"[0-9a-fA-F]{64}")
_MIB = 1024 * 1024
_UNIT_BYTES = {"K": 1024, "M": _MIB, "G": 1024 * _MIB, "T": 1024 * 1024 * _MIB}

# The media-name charter (D24): the script `name` production with a
# leading digit allowed. Split from the letter-initial property key,
# which also appears bare at a declaration where a digit would lex as a
# duration. Parens and brackets are out by argv, not grammar: every
# media name is an argument to fetch-media / add-media / clean-media.
_MEDIA_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_PROPERTY_KEY = re.compile(r"[A-Za-z][A-Za-z0-9._-]*")

# The reference closure has two halves and needs both (D26 as corrected
# by D27): this class is the FIRST SCREEN, catching |, (, [, ?, = and
# whitespace; the productions below decide, catching everything built
# from already-legal characters. `${mem:-512M}` passes the class and is
# refused by the production, `mem` not being a qualifier.
_REFERENCE_BODY = re.compile(r"[A-Za-z0-9._:/-]+")

_KNOWN_QUALIFIERS = {"media"}
# A qualifier names a namespace to look in, never an operation: the set
# is open, and these are spoken for.
_RESERVED_QUALIFIERS = {"property", "env", "file", "machine", "script",
                        "landmark", "secret"}

_SCHEME = re.compile(r"([A-Za-z][A-Za-z0-9+.-]*):")
_REMOTE_SCHEMES = {"http", "https"}


class BlueprintWarning(UserWarning):
    """A repaired-but-accepted authoring problem, named at its source."""


# --- the parsed model ------------------------------------------------

@dataclass(frozen=True)
class Reference:
    """One parsed ``${...}``.

    ``qualifier`` is ``None`` for the unqualified property form. A
    qualified media reference may carry a containment ``path``.
    """

    qualifier: Optional[str]
    target: str
    path: Optional[str] = None

    @property
    def text(self):
        body = self.target if self.qualifier is None \
            else f"{self.qualifier}:{self.target}"
        return "${" + body + "}" + (f"/{self.path}" if self.path else "")


@dataclass(frozen=True)
class Deferred:
    """A value carrying references, finished at resolution.

    Shape is checked here; the value cannot be — a reference may resolve
    to anything the field's own parser must then accept, which is what
    two-phase validation means.
    """

    text: str
    references: Tuple[Reference, ...]


@dataclass(frozen=True)
class Location:
    """One rung of a media's location. Exactly one ``kind``.

    ``url`` — a download; ``local`` — a host path relative to the
    referencing file; ``parent`` — a member of another media (the
    containment edge, ``path`` optional: absent means the parent's own
    bytes); ``property`` — supplied by a property; ``deferred`` — a
    string whose references must resolve before it can be dispatched.
    """

    kind: str
    url: Optional[str] = None
    local: Optional[str] = None
    parent: Optional[str] = None
    path: Optional[str] = None
    property_key: Optional[str] = None
    deferred: Optional[Deferred] = None

    @property
    def is_remote(self):
        return self.kind == "url"


@dataclass(frozen=True)
class Media:
    """A media spec: owns content and materialization.

    ``read_only`` is ``None`` when unset (its effective default — true
    on a cdrom, false elsewhere — resolves at materialization).
    ``location`` is the mirror tuple, empty for a ``new`` blank.
    ``anonymous`` marks the content-free blank: in no namespace, named
    for its slot at materialization, unreferenceable from a script.
    """

    name: Optional[str]
    materialize: str = "use"
    size: Optional[Union[str, Deferred]] = None
    location: Tuple[Location, ...] = ()
    sha256: Optional[Union[str, Deferred]] = None
    read_only: Optional[bool] = None
    extension: Optional[str] = None
    description: Optional[Union[str, Deferred]] = None
    notes: Optional[Union[str, Deferred]] = None
    anonymous: bool = False


@dataclass(frozen=True)
class MachineDrive:
    """One drive slot: names a media, or ``None`` for an empty slot.

    ``inline`` carries a media spec written in place at the drive. A
    named inline media is registered in the catalog like any other and
    ``media`` names it; the anonymous blank has no name and lives only
    here.
    """

    key: str
    medium: str
    slot: int
    media: Optional[str] = None
    controller: Optional[str] = None
    enabled: bool = True
    inline: Optional[Media] = None


@dataclass(frozen=True)
class Machine:
    """Machine topology. Drives name media; content lives on the media."""

    name: str
    platform: str
    backend: Optional[str] = None
    memory: Optional[Union[int, Deferred]] = None
    cpus: Optional[Union[int, Deferred]] = None
    drives: Mapping[str, MachineDrive] = field(default_factory=dict)
    boot: Tuple[str, ...] = ()
    description: Optional[Union[str, Deferred]] = None
    scripts: Mapping[str, str] = field(default_factory=dict)
    control_planes: Tuple[str, ...] = ()
    backend_settings: Mapping[str, Mapping] = field(default_factory=dict)
    parameters: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class Document:
    """One parsed ``.rlqb``: the specs it contributes, by name and type."""

    machines: Mapping[str, Machine] = field(default_factory=dict)
    media: Mapping[str, Media] = field(default_factory=dict)


# --- references ------------------------------------------------------

def _reference(body, where):
    """Parse one ``${...}`` body into a :class:`Reference`, or fail.

    The character class screens; the two productions decide. Neither is
    the whole test on its own (D27).
    """
    if not body:
        raise ValueError(
            f"{where}: empty reference '${{}}' — name a property key or a "
            "qualified target")
    if "\\" in body:
        # The Windows author's first guess. Name the rule, not the class.
        raise ValueError(
            f"{where}: '${{{body}}}' uses a backslash — a containment path "
            "is '/'-separated always, following the container formats' own "
            "convention")
    if not _REFERENCE_BODY.fullmatch(body):
        raise ValueError(
            f"{where}: malformed reference '${{{body}}}' — a reference body "
            "is a property key or '<qualifier>:<name>[/<path>]', and carries "
            "no operators")
    if ":" not in body:
        return _property_reference(body, where)

    qualifier, _, rest = body.partition(":")
    if not qualifier:
        raise ValueError(
            f"{where}: malformed reference '${{{body}}}' — nothing before "
            "the qualifier separator")
    if qualifier != qualifier.lower():
        raise ValueError(
            f"{where}: reference qualifier {qualifier!r} must be lowercase")
    if qualifier in _RESERVED_QUALIFIERS:
        if qualifier == "property":
            raise ValueError(
                f"{where}: the 'property:' qualifier is reserved — write the "
                f"bare form '${{{rest}}}' instead")
        raise ValueError(
            f"{where}: the {qualifier!r} qualifier is reserved and not "
            "implemented")
    if qualifier not in _KNOWN_QUALIFIERS:
        known = ", ".join(sorted(_KNOWN_QUALIFIERS))
        raise ValueError(
            f"{where}: unknown reference qualifier {qualifier!r} "
            f"(known: {known})")
    return _media_reference(rest, body, where)


def _property_reference(body, where):
    if body == "media":
        raise ValueError(
            f"{where}: '${{media}}' is not a property — did you mean "
            "'${media:<name>}'?")
    for segment in body.split("."):
        if not _PROPERTY_KEY.fullmatch(segment):
            raise ValueError(
                f"{where}: malformed property key '{body}' — segments start "
                "with a letter and hold letters, digits, '.', '_', '-'")
    return Reference(qualifier=None, target=body)


def _media_reference(rest, body, where):
    name, slash, path = rest.partition("/")
    if not name:
        raise ValueError(
            f"{where}: malformed reference '${{{body}}}' — the media "
            "qualifier takes a name")
    if not _MEDIA_NAME.fullmatch(name):
        raise ValueError(
            f"{where}: {name!r} is not a media name (letters, digits, "
            "'.', '_', '-', starting with a letter or digit)")
    if not slash:
        return Reference(qualifier="media", target=name)
    return Reference(qualifier="media", target=name,
                     path=_containment_path(path, where))


def _containment_path(path, where):
    """Normalize a containment path suffix, refusing every escape."""
    if not path:
        raise ValueError(
            f"{where}: the containment separator '/' is followed by no "
            "path")
    if path.startswith("/"):
        raise ValueError(
            f"{where}: '{path}' is an absolute path — a containment path is "
            "relative to its parent")
    if path.endswith("/"):
        raise ValueError(f"{where}: containment path {path!r} has a trailing "
                         "'/'")
    segments = path.split("/")
    for segment in segments:
        if not segment:
            raise ValueError(
                f"{where}: containment path {path!r} has an empty segment")
        if segment in (".", ".."):
            raise ValueError(
                f"{where}: containment path {path!r} escapes its parent "
                f"with {segment!r}")
    return "/".join(segments)


def _scan(text, where):
    """Split a string into literal spans and references.

    Returns ``(spans, references)`` where ``spans`` is the text with
    escapes resolved and reference sites marked by ``None``. ``\\${`` is
    the literal escape, identical to the script language's.
    """
    spans, references = [], []
    literal, index = [], 0
    while index < len(text):
        char = text[index]
        if char == "\\" and text.startswith("\\${", index):
            literal.append("${")
            index += 3
            continue
        if text.startswith("${", index):
            close = text.find("}", index)
            if close < 0:
                raise ValueError(
                    f"{where}: unterminated reference — '${{' with no "
                    "closing brace")
            body = text[index + 2:close]
            if body.strip() != body or " " in body or "\t" in body:
                raise ValueError(
                    f"{where}: whitespace inside '${{{body}}}'")
            spans.append("".join(literal))
            literal = []
            spans.append(None)
            references.append(_reference(body, where))
            index = close + 1
            continue
        literal.append(char)
        index += 1
    spans.append("".join(literal))
    return spans, tuple(references)


def _text(value, where, *, closed=False, allowed=None):
    """Validate an authored string, applying the reference reach rules.

    ``closed`` marks a closed-vocabulary position, where a reference is
    refused outright: those are where a published schema's completion is
    most valuable and where a reference destroys it (D26). ``allowed``
    is the vocabulary, checked once no reference can be involved.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"{where} must be a non-empty string, got: {value!r}")
    spans, references = _scan(value, where)
    if references and closed:
        raise ValueError(
            f"{where} is a closed vocabulary and takes no reference: "
            f"{value!r} — its values are fixed so editors can complete "
            "them and the published schema can check them")
    if references:
        return Deferred(text=value, references=references)
    resolved = "".join(span for span in spans if span is not None)
    if allowed is not None and resolved not in allowed:
        raise ValueError(
            f"{where} must be one of {', '.join(sorted(allowed))}, "
            f"got: {resolved!r}")
    return resolved


def _plain(value, where):
    """An authored string that may never carry a reference (identity)."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"{where} must be a non-empty string, got: {value!r}")
    if "${" in value.replace("\\${", ""):
        raise ValueError(
            f"{where} takes no reference: {value!r} — identity and the "
            "authored graph stay static, so a name can never depend on a "
            "resolved value")
    return value


# --- names -----------------------------------------------------------

def _media_name(value, where="name"):
    _plain(value, where)
    if not _MEDIA_NAME.fullmatch(value):
        raise ValueError(
            f"{where} must be letters, digits, '.', '_' or '-', starting "
            f"with a letter or digit, got: {value!r}")
    return value


def _machine_name(value, where="name"):
    """A machine name is also an id segment (``<name>-<n>``)."""
    _media_name(value, where)
    if value.isdigit():
        raise ValueError(
            f"{where} must not be all digits: a machine name becomes its "
            f"id segment '<name>-<n>', got: {value!r}")
    return value


def _stem(name):
    """The identity stem of a filename or member path: basename, no ext."""
    base = name.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
    root, dot, _ext = base.rpartition(".")
    return root if dot else base


def _url_filename(url):
    tail = url.split("#", 1)[0].split("?", 1)[0]
    return tail.rstrip("/").rsplit("/", 1)[-1]


def _repair(stem):
    """Repair a stem's character set. Never invents a name."""
    repaired = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-")
    while repaired and not _MEDIA_NAME.match(repaired):
        repaired = repaired[1:]
    return repaired


def _derive_name(location, where):
    """Derive a media name from content-intrinsic material, or fail.

    The slot never names anything and neither does the ``.rlqb`` file:
    the stem comes from the payload, so a spec pasted among siblings
    resolves the same. An out-of-charter stem is repaired and warned;
    one that cannot be repaired, or that does not exist at all, fails
    closed demanding an explicit name.
    """
    first = location[0] if location else None
    stem = source = None
    if first is not None:
        if first.kind == "url":
            stem, source = _stem(_url_filename(first.url)), first.url
        elif first.kind == "local":
            stem, source = _stem(first.local), first.local
        elif first.kind == "parent" and first.path:
            stem, source = _stem(first.path), first.path
    if not stem:
        raise ValueError(
            f"{where} has no filename to derive a name from; give it an "
            "explicit name")
    if _MEDIA_NAME.fullmatch(stem):
        return stem
    repaired = _repair(stem)
    if not repaired or not _MEDIA_NAME.fullmatch(repaired):
        raise ValueError(
            f"{where}: the name derived from {source!r} cannot be repaired "
            "into a usable name; give it an explicit name")
    warnings.warn(
        f"{where}: derived the name {repaired!r} from {source!r} "
        "(repaired to the media-name charter); write an explicit name to "
        "choose your own", BlueprintWarning, stacklevel=2)
    return repaired


# --- scalars ---------------------------------------------------------

def _sha256(value, where):
    checked = _text(value, where)
    if isinstance(checked, Deferred):
        return checked
    if not _SHA256.fullmatch(checked):
        raise ValueError(
            f"{where} must be a hex SHA-256 (64 hex chars), got: {value!r}")
    return checked.lower()


def _size(value, where):
    checked = _text(value, where) if isinstance(value, str) else value
    if isinstance(checked, Deferred):
        return checked
    if not isinstance(checked, str):
        raise ValueError(f"{where} must be a size string, got: {value!r}")
    match = _SIZE.fullmatch(checked)
    if not match:
        raise ValueError(
            f"{where} must be a positive integer followed by K, M, G, or T, "
            f"got: {value!r}")
    return f"{int(match.group(1))}{match.group(2).upper()}"


def _memory(value):
    if isinstance(value, str):
        checked = _text(value, "memory")
        if isinstance(checked, Deferred):
            return checked
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


def _cpus(value):
    if isinstance(value, str):
        checked = _text(value, "cpus")
        if isinstance(checked, Deferred):
            return checked
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"cpus must be a positive integer, got: {value!r}")
    return value


def _flag(value, where):
    if not isinstance(value, bool):
        raise ValueError(f"{where} must be true or false, got: {value!r}")
    return value


# --- locations -------------------------------------------------------

def location_from_string(value, where):
    """Public: interpret a location string into a :class:`Location`.

    The seam T5 uses to re-interpret a property-bound location value
    (a path, a URL, or — refused as chaining — another reference).
    """
    return _location_string(value, where)


def _location_string(value, where):
    """Interpret one location string by scheme.

    Strings are interpreted, objects are explicit: every accepted string
    has exactly one object desugaring, which is the canonical form.
    """
    spans, references = _scan(value, where)
    qualified = [ref for ref in references if ref.qualifier is not None]
    if qualified:
        if len(references) != 1 or [s for s in spans if s]:
            raise ValueError(
                f"{where}: a '${{{qualified[0].qualifier}:…}}' reference is "
                "whole-value only — it names a location, it does not build "
                "one by interpolation")
        reference = qualified[0]
        return Location(kind="parent", parent=reference.target,
                        path=reference.path)
    if references:
        if len(references) == 1 and not [s for s in spans if s]:
            return Location(kind="property", property_key=references[0].target)
        return Location(kind="deferred",
                        deferred=Deferred(text=value, references=references))
    return _location_scheme(value, where)


def _location_scheme(value, where):
    match = _SCHEME.match(value)
    if match is None:
        return Location(kind="local", local=value)
    scheme = match.group(1)
    if scheme.lower() in _REMOTE_SCHEMES:
        return Location(kind="url", url=value)
    if len(scheme) == 1:
        # The drive-letter exemption: C:/isos/x.iso is a path.
        return Location(kind="local", local=value)
    raise ValueError(
        f"{where}: unrecognized location scheme {scheme + ':'!r} in "
        f"{value!r} — write a bare path, an http(s) URL, or the object form")


_LOCATION_OBJECT_FORMS = ("url", "local", "parent", "property")


def _location_object(value, where, register):
    unknown = set(value) - set(_LOCATION_OBJECT_FORMS) - {"path"}
    if unknown:
        raise ValueError(f"unknown location field: {where}.{sorted(unknown)[0]}")
    forms = [name for name in _LOCATION_OBJECT_FORMS if name in value]
    if len(forms) != 1:
        allowed = ", ".join(_LOCATION_OBJECT_FORMS)
        raise ValueError(
            f"{where} must declare exactly one of {allowed}")
    form = forms[0]
    if form != "parent" and "path" in value:
        raise ValueError(
            f"{where}.path belongs to the parent form, not {form!r}")
    if form == "url":
        return Location(kind="url", url=_text(value["url"], f"{where}.url"))
    if form == "local":
        return Location(kind="local",
                        local=_text(value["local"], f"{where}.local"))
    if form == "property":
        return Location(
            kind="property",
            property_key=_plain(value["property"], f"{where}.property"))
    parent = value["parent"]
    if isinstance(parent, collections.abc.Mapping):
        # An inline parent: a container that exists only to be descended
        # into need not be declared separately.
        inline = _media(parent, register, where=f"{where}.parent")
        parent_name = inline.name
        if parent_name is None:
            raise ValueError(
                f"{where}.parent must be a named media: an inline parent is "
                "a container to descend into, so it needs an identity")
    else:
        parent_name = _media_name(parent, f"{where}.parent")
    path = None
    if "path" in value:
        path = _containment_path(
            _plain(value["path"], f"{where}.path"), f"{where}.path")
    return Location(kind="parent", parent=parent_name, path=path)


def _location(value, where, register):
    """Parse a media's ``location``: one rung, or a mirror list."""
    if isinstance(value, list):
        if not value:
            raise ValueError(
                f"{where} must not be an empty list — a mirror list holds "
                "the locations to try in order")
        rungs = []
        for index, entry in enumerate(value):
            if isinstance(entry, list):
                raise ValueError(
                    f"{where}[{index}] must not be a nested list — a mirror "
                    "list is flat")
            rungs.extend(_location(entry, f"{where}[{index}]", register))
        return tuple(rungs)
    if isinstance(value, str):
        return (_location_string(value, where),)
    if isinstance(value, collections.abc.Mapping):
        return (_location_object(value, where, register),)
    raise ValueError(
        f"{where} must be a location string, a location object, or a list "
        f"of them, got: {value!r}")


# --- media -----------------------------------------------------------

_MEDIA_FIELDS = {"type", "name", "materialize", "size", "location", "sha256",
                 "read-only", "extension", "description", "notes", "children"}
_CHILD_FIELDS = (_MEDIA_FIELDS - {"location"}) | {"path"}
_MACHINE_VOCABULARY = {"platform", "backend", "memory", "cpus", "drives",
                       "boot", "scripts", "control-planes",
                       "backend-settings", "parameters"}


def _unknown_media_field(unknown, where):
    bad = sorted(unknown)[0]
    if bad in _MACHINE_VOCABULARY:
        raise ValueError(
            f"unknown media field: {where}.{bad} — {bad!r} is machine "
            "vocabulary; did you mean to declare \"type\": \"machine\"? "
            "(type defaults to media)")
    raise ValueError(f"unknown media field: {where}.{bad}")


def _media(value, register, *, where="media", path=None, allow_anonymous=False):
    """Parse one media spec, registering it and any children it declares.

    ``path`` marks a ``children`` entry, whose location is its parent
    plus that path rather than a ``location`` of its own.
    """
    if isinstance(value, str) and path is None:
        value = {"location": value}
    if not isinstance(value, collections.abc.Mapping):
        raise ValueError(f"{where} must be an object, got: {value!r}")
    fields = _CHILD_FIELDS if path is not None else _MEDIA_FIELDS
    unknown = set(value) - fields
    if unknown:
        if path is not None and "location" in unknown:
            raise ValueError(
                f"{where}: a children entry takes a path, not a location — "
                "its location is its parent plus that path")
        _unknown_media_field(unknown, where)
    _check_type_echo(value, "media", where)

    location = ()
    if path is not None:
        location = (path,)
    elif "location" in value:
        location = _location(value["location"], f"{where}.location", register)

    materialize = _text(value["materialize"], f"{where}.materialize",
                        closed=True, allowed=_MATERIALIZE) \
        if "materialize" in value else None
    size = _size(value["size"], f"{where}.size") if "size" in value else None
    if materialize is None:
        # A spec carrying a size and no location is a blank: there is
        # nothing else it could be, which is what lets the drive-inline
        # blank be written {"size": "20M"}.
        materialize = "new" if size is not None and not location else "use"
    if materialize == "new":
        if location:
            raise ValueError(
                f"{where}: a 'new' blank takes a size, not a location")
        if size is None:
            raise ValueError(f"{where}: a 'new' blank requires a size")
    else:
        if not location:
            raise ValueError(
                f"{where}: a '{materialize}' media requires a location")
        if size is not None:
            raise ValueError(
                f"{where}: a '{materialize}' media takes a location, not a "
                "size")

    if "name" in value:
        name = _media_name(value["name"], f"{where}.name")
    elif materialize == "new" and allow_anonymous:
        name = None
    else:
        name = _derive_name(location, where)

    media = Media(
        name=name,
        materialize=materialize,
        size=size,
        location=location,
        sha256=_sha256(value["sha256"], f"{where}.sha256")
        if "sha256" in value else None,
        read_only=_flag(value["read-only"], f"{where}.read-only")
        if "read-only" in value else None,
        extension=_plain(value["extension"], f"{where}.extension")
        if "extension" in value else None,
        description=_text(value["description"], f"{where}.description")
        if "description" in value else None,
        notes=_text(value["notes"], f"{where}.notes")
        if "notes" in value else None,
        anonymous=name is None)
    if name is not None:
        register("media", name, media)
    if "children" in value:
        if name is None:
            raise ValueError(
                f"{where}: a container with children needs a name for them "
                "to hang from")
        _children(value["children"], name, register, where)
    return media


def _children(value, parent, register, where):
    """Desugar a ``children`` batch into child-declares-parent specs."""
    if not isinstance(value, list):
        raise ValueError(f"{where}.children must be an array")
    for index, entry in enumerate(value):
        site = f"{where}.children[{index}]"
        if isinstance(entry, str):
            entry = {"path": entry}
        if not isinstance(entry, collections.abc.Mapping):
            raise ValueError(
                f"{site} must be a path string or a media object, "
                f"got: {entry!r}")
        if "path" not in entry:
            raise ValueError(f"{site} requires a path")
        location = Location(
            kind="parent", parent=parent,
            path=_containment_path(
                _plain(entry["path"], f"{site}.path"), f"{site}.path"))
        _media(entry, register, where=site, path=location)


def _check_type_echo(value, expected, where):
    """An optional ``type`` at a nested position is a checked echo."""
    if "type" not in value:
        return
    declared = _plain(value["type"], f"{where}.type")
    if declared in _RETIRED_TYPES:
        raise ValueError(
            f"{where}: the {declared!r} spec type is retired — a source is "
            "now a media's location, and an archive is a media other media "
            "name as their parent")
    if declared not in _SPEC_TYPES:
        allowed = ", ".join(sorted(_SPEC_TYPES))
        raise ValueError(
            f"{where}.type must be one of {allowed}, got: {declared!r}")
    if declared != expected:
        raise ValueError(
            f"{where}.type says {declared!r} but this position is a "
            f"{expected}")


# --- machine ---------------------------------------------------------

_MACHINE_FIELDS = {
    "type", "name", "platform", "backend", "memory", "cpus", "drives", "boot",
    "description", "scripts", "control-planes", "backend-settings",
    "parameters",
}
_STATE_ONLY = {"id", "backend-id", "blueprint-digest", "blueprint-source"}
_DRIVE_FIELDS = {"media", "controller", "enabled"}


def _drive_key(value):
    if not isinstance(value, str):
        raise ValueError(f"drive keys must be strings, got: {value!r}")
    if "${" in value:
        raise ValueError(
            f"drive key {value!r} takes no reference: an object key is "
            "authored graph, and the graph stays static")
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
    return _text(value, f"drives.{key}.controller", closed=True,
                 allowed=_CONTROLLERS)


def _drive(value, key, medium, slot, register):
    if value is None:
        if medium == "hdd":
            raise ValueError(
                f"drives.{key} cannot be null: only removable drives "
                "(floppy, cdrom) may be declared empty")
        return MachineDrive(key=key, medium=medium, slot=slot)
    if isinstance(value, str):
        return MachineDrive(key=key, medium=medium, slot=slot,
                            media=_media_name(value, f"drives.{key}"))
    if not isinstance(value, collections.abc.Mapping):
        raise ValueError(
            f"drives.{key} must be a media name, null, a drive object, or "
            "an inline media")
    if set(value) - _DRIVE_FIELDS:
        # Not the hardware-attribute object, so it is an inline media:
        # a full spec, or the {"size": ...} blank.
        inline = _media(value, register, where=f"drives.{key}",
                        allow_anonymous=True)
        return MachineDrive(key=key, medium=medium, slot=slot,
                            media=inline.name, inline=inline)
    if "media" not in value:
        raise ValueError(
            f"drives.{key} must name a media (or be null for an empty "
            "removable slot)")
    controller = (_controller(value["controller"], key, medium)
                  if "controller" in value else None)
    return MachineDrive(
        key=key, medium=medium, slot=slot,
        media=_media_name(value["media"], f"drives.{key}.media"),
        controller=controller,
        enabled=_flag(value.get("enabled", True), f"drives.{key}.enabled"))


def _drives(value, register):
    if not isinstance(value, collections.abc.Mapping):
        raise ValueError("drives must be an object")
    normalized, claimed = {}, {}
    for authored_key, declaration in value.items():
        medium, slot, key = _drive_key(authored_key)
        if key in claimed:
            raise ValueError(
                f"drive key clash: {claimed[key]!r} and {authored_key!r} "
                f"both mean {key}")
        claimed[key] = authored_key
        normalized[key] = _drive(declaration, key, medium, slot, register)
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
        label = _plain(label, "scripts label")
        script = _plain(script, f"scripts.{label}")
        if (script in (".", "..") or "/" in script or "\\" in script
                or script.lower().endswith(".rlqs")):
            raise ValueError(
                f"scripts.{label} must be the file stem under scripts/, "
                f"got: {script!r}")
        normalized[label] = script
    return types.MappingProxyType(normalized)


def _control_planes(value):
    if not isinstance(value, list):
        raise ValueError("control-planes must be an array of strings")
    normalized, seen = [], set()
    for index, entry in enumerate(value):
        plane = _text(entry, f"control-planes[{index}]", closed=True,
                      allowed=_CONTROL_PLANES)
        if plane in seen:
            raise ValueError(f"control-planes contains duplicate {plane!r}")
        seen.add(plane)
        normalized.append(plane)
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
        key = _plain(key, "parameters key")
        if isinstance(binding, str):
            normalized[key] = _text(binding, f"parameters.{key}")
        elif isinstance(binding, collections.abc.Mapping):
            if set(binding) != {"property"}:
                raise ValueError(
                    f"parameters.{key} must be a string or a "
                    '{"property": "<key>"} redirect')
            normalized[key] = types.MappingProxyType(
                {"property": _plain(
                    binding["property"], f"parameters.{key}.property")})
        else:
            raise ValueError(
                f"parameters.{key} must be a string or a "
                '{"property": "<key>"} redirect')
    return types.MappingProxyType(normalized)


def _machine(value, register, *, where="machine"):
    if not isinstance(value, collections.abc.Mapping):
        raise ValueError(f"{where} must be a JSON object")
    unknown = set(value) - _MACHINE_FIELDS
    if unknown:
        bad = sorted(unknown)[0]
        if bad in _STATE_ONLY:
            raise ValueError(
                f"{bad} is a state-only field and is not valid in a blueprint")
        raise ValueError(f"unknown machine field: {bad}")
    if "platform" not in value:
        raise KeyError("platform is required")
    platform = _text(value["platform"], "platform", closed=True,
                     allowed=_PLATFORMS)
    if "name" not in value:
        raise ValueError(f"{where} requires a name")
    name = _machine_name(value["name"], "name")
    drives = _drives(value["drives"], register) if "drives" in value \
        else types.MappingProxyType({})
    empty = types.MappingProxyType({})
    register("machine", name, Machine(
        name=name,
        platform=platform,
        backend=_text(value["backend"], "backend", closed=True,
                      allowed=_BACKENDS) if "backend" in value else None,
        memory=_memory(value["memory"]) if "memory" in value else None,
        cpus=_cpus(value["cpus"]) if "cpus" in value else None,
        drives=drives,
        boot=_boot(value["boot"], drives) if "boot" in value
        else _default_boot(drives),
        description=_text(value["description"], "description")
        if "description" in value else None,
        scripts=_scripts(value["scripts"]) if "scripts" in value else empty,
        control_planes=_control_planes(value["control-planes"])
        if "control-planes" in value else (),
        backend_settings=_backend_settings(value["backend-settings"])
        if "backend-settings" in value else empty,
        parameters=_parameters(value["parameters"])
        if "parameters" in value else empty))


# --- document --------------------------------------------------------

def _spec_type(value, where):
    """The declared type, or the ``media`` default."""
    if not isinstance(value, collections.abc.Mapping):
        return "media"
    if "type" not in value:
        return "media"
    declared = _plain(value["type"], f"{where}.type")
    if declared in _RETIRED_TYPES:
        raise ValueError(
            f"{where}: the {declared!r} spec type is retired — a source is "
            "now a media's location, and an archive is a media that other "
            "media name as their parent")
    if declared not in _SPEC_TYPES:
        allowed = ", ".join(sorted(_SPEC_TYPES))
        raise ValueError(
            f"{where}.type must be one of {allowed}, got: {declared!r}")
    return declared


def parse_document(value, *, stem=None):
    """Parse one ``.rlqb`` document into its named specs.

    The root is an array of specs; a lone spec object is sugar for the
    array of one, under the same rules — so an untyped lone object is a
    *media*, ``type`` defaulting to media everywhere. A bare string is a
    media desugaring to ``{"location": ...}``. Two specs of one type and
    name in this document are an error, identical or not.

    ``stem`` is accepted and ignored: the ``.rlqb`` file's own stem is
    never an identity.
    """
    del stem
    if isinstance(value, collections.abc.Mapping):
        sections = set(value) & _RETIRED_SECTIONS
        if sections and "type" not in value:
            raise ValueError(
                f"the plural {sorted(sections)[0]!r} section is retired: a "
                "blueprint root is an array of specs (a lone spec object is "
                "the array of one)")
        entries = [value]
    elif isinstance(value, list):
        entries = value
    else:
        raise ValueError(
            "a blueprint must be an array of specs or a lone spec object, "
            f"got {type(value).__name__}")

    buckets = {"machine": {}, "media": {}}

    def register(kind, name, spec):
        bucket = buckets[kind]
        if name in bucket:
            raise ValueError(
                f"duplicate {kind} name {name!r} in one document")
        folded = {existing.lower() for existing in bucket}
        if name.lower() in folded:
            raise ValueError(
                f"{kind} name {name!r} collides case-insensitively with "
                "another in this document: names match exactly but the "
                "media cache is name-keyed on filesystems that do not")
        bucket[name] = spec

    for index, entry in enumerate(entries):
        where = f"spec[{index}]" if len(entries) > 1 else "spec"
        if isinstance(entry, str):
            _bare_string_spec(entry, where, register)
            continue
        if _spec_type(entry, where) == "machine":
            _machine(entry, register, where=where)
        else:
            _media(entry, register, where=where)

    return Document(machines=types.MappingProxyType(buckets["machine"]),
                    media=types.MappingProxyType(buckets["media"]))


def _bare_string_spec(entry, where, register):
    """A bare-string root element: a media located by that string."""
    media = _media({"location": entry}, register, where=where)
    if any(rung.is_remote for rung in media.location) and media.sha256 is None:
        raise ValueError(
            f"{where}: a bare remote location has nowhere to carry its "
            f"sha256 — write the object form: "
            f'{{"location": {entry!r}, "sha256": "…"}}')


def load_document(path):
    """Load and parse one ``.rlqb`` document."""
    path = os.path.abspath(os.fspath(path))
    if not os.path.exists(path):
        raise FileNotFoundError(f"blueprint not found: {path}")
    with open(path, "r", encoding="utf-8") as handle:
        value = jsonc.load(handle)
    return parse_document(value)
