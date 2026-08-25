# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
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
from dataclasses import dataclass, field, replace
from typing import Mapping, Optional, Tuple, Union

from . import json5reader
from .errors import PreflightError, StaticError

_PLATFORMS = {"dos", "openbsd", "win9x", "winnt"}
_BACKENDS = {"qemu", "virtualbox", "dosbox-x", "vmware", "hyperv"}
_CONTROLLERS = {"ide", "sata", "scsi", "nvme", "virtio"}
_CONTROL_PLANES = {"agentless-display", "vnc", "serial-console", "guest-agent"}
_POINTING_DEVICES = {"tablet", "mouse"}
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


# --- located diagnostics ---------------------------------------------

class BlueprintError(StaticError):
    """A blueprint diagnostic that can say *where* it happened.

    The legality tier of the error taxonomy, like every other diagnostic
    this module raises: it is decided from the document text alone, so
    it is a STATIC ERROR and exits ``2``. What it adds is the position
    :class:`~reliquary.script_nodes.ScriptParseError` has always carried
    on the script surface, rendered by the same skeleton (D70).

    **Position is optional and its absence is not a defect.** A document
    parsed from a path has one; a value handed to the public
    ``parse_document`` never did -- there is no text to point into --
    and renders exactly as this module rendered before positions
    existed. The breadcrumb is what both cases share, and it stays in
    the message rather than moving into the rendering, so an unlocated
    diagnostic reads today as it read yesterday.
    """

    def __init__(self, message, *, rule_id=None, position=None):
        super().__init__(message, rule_id=rule_id)
        self.message = message
        self.line, self.column = position if position else (None, None)
        self.path = None
        self.source_line = None

    def _set_context(self, path, source_lines):
        """Attach source context once the loader knows the file."""
        self.path = path
        if self.line is not None and 1 <= self.line <= len(source_lines):
            self.source_line = source_lines[self.line - 1]

    def __str__(self):
        if self.line is None:
            return self.message
        location = f"{self.path or '<blueprint>'}:{self.line}:{self.column}"
        cited = f" ({self.rule_id})" if self.rule_id else ""
        result = f"{location}: error: {self.message}{cited}"
        if self.source_line is not None:
            gutter = f"{self.line} | "
            caret = " " * (len(gutter) + self.column - 1) + "^"
            result = f"{result}\n{gutter}{self.source_line}\n{caret}"
        return result


class Where:
    """A field breadcrumb, and the source position it names.

    It stands where a plain breadcrumb string used to, and renders as
    that string, so every message built with ``f"{where}: ..."`` reads
    exactly as it did. What it adds is the position, carried alongside
    the text and attached to whatever diagnostic the field raises.

    Descent is explicit -- ``where.at(container, key)`` takes the
    container the key belongs to rather than remembering it -- because
    a position that silently drifts from the field it claims to name is
    worse than no position at all, and an argument that has to be
    passed cannot drift.
    """

    __slots__ = ("text", "position")

    def __init__(self, text, position=None):
        self.text = text
        self.position = position

    def __str__(self):
        return self.text

    def at(self, container, key, text=None):
        """The breadcrumb for ``container[key]``, positioned at its key.

        A container with no positions -- a plain ``dict`` from the
        public entry point -- yields the parent's position, so a
        diagnostic deep in an unlocated document still cites the
        nearest thing anyone knows.

        ``text`` overrides the composed wording, for the fields whose
        breadcrumb has never been composed from its parent's: the
        machine half says ``drives.hdd0.media`` where the media half
        says ``spec[0].location``. That difference is older than
        positions and is left exactly as it was, this change being
        about where a diagnostic points and not what it says.
        """
        if text is None:
            text = f"{self.text}[{key}]" if isinstance(key, int) \
                else f"{self.text}.{key}"
        return Where(text, json5reader.position_of(container, key) or self.position)

    def error(self, message, *, rule_id=None):
        """The located diagnostic for this field."""
        return BlueprintError(message, rule_id=rule_id,
                              position=self.position)


def _rooted(value, text):
    """The root breadcrumb for a document or spec, positioned at it."""
    return Where(text, json5reader.position(value))


# The unlocated defaults, for a caller that names no field: reaching one
# means nobody threaded a breadcrumb to that call, which is the state
# every one of these was in before positions existed.
_MACHINE = Where("machine")
_MEDIA = Where("media")
_NAME = Where("name")


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
    referencing file (made absolute when the document is loaded from
    one); ``parent`` — a member of another media (the
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
    pointing_device: Optional[str] = None
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
        raise where.error(
            f"{where}: empty reference '${{}}' — name a property key or a "
            "qualified target", rule_id="ref.empty")
    if "\\" in body:
        # The Windows author's first guess. Name the rule, not the class.
        raise where.error(
            f"{where}: '${{{body}}}' uses a backslash — a containment path "
            "is '/'-separated always, following the container formats' own "
            "convention", rule_id="ref.backslash")
    if not _REFERENCE_BODY.fullmatch(body):
        raise where.error(
            f"{where}: malformed reference '${{{body}}}' — a reference body "
            "is a property key or '<qualifier>:<name>[/<path>]', and carries "
            "no operators", rule_id="ref.malformed")
    if ":" not in body:
        return _property_reference(body, where)

    qualifier, _, rest = body.partition(":")
    if not qualifier:
        raise where.error(
            f"{where}: malformed reference '${{{body}}}' — nothing before "
            "the qualifier separator", rule_id="ref.qualifier-empty")
    if qualifier != qualifier.lower():
        raise where.error(
            f"{where}: reference qualifier {qualifier!r} must be lowercase",
            rule_id="ref.qualifier-not-lowercase")
    if qualifier in _RESERVED_QUALIFIERS:
        if qualifier == "property":
            raise where.error(
                f"{where}: the 'property:' qualifier is reserved — write the "
                f"bare form '${{{rest}}}' instead",
                rule_id="ref.qualifier-reserved")
        raise where.error(
            f"{where}: the {qualifier!r} qualifier is reserved and not "
            "implemented", rule_id="ref.qualifier-reserved")
    if qualifier not in _KNOWN_QUALIFIERS:
        known = ", ".join(sorted(_KNOWN_QUALIFIERS))
        raise where.error(
            f"{where}: unknown reference qualifier {qualifier!r} "
            f"(known: {known})", rule_id="ref.qualifier-unknown")
    return _media_reference(rest, body, where)


def _property_reference(body, where):
    if body == "media":
        raise where.error(
            f"{where}: '${{media}}' is not a property — did you mean "
            "'${media:<name>}'?", rule_id="ref.media-without-name")
    for segment in body.split("."):
        if not _PROPERTY_KEY.fullmatch(segment):
            raise where.error(
                f"{where}: malformed property key '{body}' — segments start "
                "with a letter and hold letters, digits, '.', '_', '-'",
                rule_id="ref.property-key-malformed")
    return Reference(qualifier=None, target=body)


def _media_reference(rest, body, where):
    name, slash, path = rest.partition("/")
    if not name:
        raise where.error(
            f"{where}: malformed reference '${{{body}}}' — the media "
            "qualifier takes a name", rule_id="ref.media-without-name")
    if not _MEDIA_NAME.fullmatch(name):
        raise where.error(
            f"{where}: {name!r} is not a media name (letters, digits, "
            "'.', '_', '-', starting with a letter or digit)",
            rule_id="name.media-charter")
    if not slash:
        return Reference(qualifier="media", target=name)
    return Reference(qualifier="media", target=name,
                     path=_containment_path(path, where))


def _containment_path(path, where):
    """Normalize a containment path suffix, refusing every escape."""
    if not path:
        raise where.error(
            f"{where}: the containment separator '/' is followed by no "
            "path", rule_id="ref.path-empty")
    if path.startswith("/"):
        raise where.error(
            f"{where}: '{path}' is an absolute path — a containment path is "
            "relative to its parent", rule_id="ref.path-absolute")
    if path.endswith("/"):
        raise where.error(f"{where}: containment path {path!r} has a trailing "
                         "'/'", rule_id="ref.path-trailing-slash")
    segments = path.split("/")
    for segment in segments:
        if not segment:
            raise where.error(
                f"{where}: containment path {path!r} has an empty segment",
                rule_id="ref.path-empty-segment")
        if segment in (".", ".."):
            raise where.error(
                f"{where}: containment path {path!r} escapes its parent "
                f"with {segment!r}", rule_id="ref.path-escapes-parent")
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
                raise where.error(
                    f"{where}: unterminated reference — '${{' with no "
                    "closing brace", rule_id="ref.unterminated")
            body = text[index + 2:close]
            if body.strip() != body or " " in body or "\t" in body:
                raise where.error(
                    f"{where}: whitespace inside '${{{body}}}'",
                    rule_id="ref.whitespace")
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
        raise where.error(
            f"{where} must be a non-empty string, got: {value!r}",
            rule_id="value.not-a-string")
    spans, references = _scan(value, where)
    if references and closed:
        raise where.error(
            f"{where} is a closed vocabulary and takes no reference: "
            f"{value!r} — its values are fixed so editors can complete "
            "them and the published schema can check them",
            rule_id="ref.not-allowed-here")
    if references:
        return Deferred(text=value, references=references)
    resolved = "".join(span for span in spans if span is not None)
    if allowed is not None and resolved not in allowed:
        raise where.error(
            f"{where} must be one of {', '.join(sorted(allowed))}, "
            f"got: {resolved!r}", rule_id="value.not-in-vocabulary")
    return resolved


def _plain(value, where):
    """An authored string that may never carry a reference (identity)."""
    if not isinstance(value, str) or not value.strip():
        raise where.error(
            f"{where} must be a non-empty string, got: {value!r}",
            rule_id="value.not-a-string")
    if "${" in value.replace("\\${", ""):
        raise where.error(
            f"{where} takes no reference: {value!r} — identity and the "
            "authored graph stay static, so a name can never depend on a "
            "resolved value", rule_id="ref.not-allowed-here")
    return value


# --- names -----------------------------------------------------------

def _media_name(value, where=_NAME):
    _plain(value, where)
    if not _MEDIA_NAME.fullmatch(value):
        raise where.error(
            f"{where} must be letters, digits, '.', '_' or '-', starting "
            f"with a letter or digit, got: {value!r}",
            rule_id="name.machine-charter")
    return value


def _machine_name(value, where=_NAME):
    """A machine name is also an id segment (``<name>-<n>``)."""
    _media_name(value, where)
    if value.isdigit():
        raise where.error(
            f"{where} must not be all digits: a machine name becomes its "
            f"id segment '<name>-<n>', got: {value!r}",
            rule_id="name.machine-all-digits")
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
        raise where.error(
            f"{where} has no filename to derive a name from; give it an "
            "explicit name", rule_id="name.not-derivable")
    if _MEDIA_NAME.fullmatch(stem):
        return stem
    repaired = _repair(stem)
    if not repaired or not _MEDIA_NAME.fullmatch(repaired):
        raise where.error(
            f"{where}: the name derived from {source!r} cannot be repaired "
            "into a usable name; give it an explicit name",
            rule_id="name.not-repairable")
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
        raise where.error(
            f"{where} must be a hex SHA-256 (64 hex chars), got: {value!r}",
            rule_id="value.not-a-sha256")
    return checked.lower()


def _size(value, where):
    checked = _text(value, where) if isinstance(value, str) else value
    if isinstance(checked, Deferred):
        return checked
    if not isinstance(checked, str):
        raise where.error(f"{where} must be a size string, got: {value!r}",
            rule_id="value.not-a-size")
    match = _SIZE.fullmatch(checked)
    if not match:
        raise where.error(
            f"{where} must be a positive integer followed by K, M, G, or T, "
            f"got: {value!r}", rule_id="value.not-a-size")
    return f"{int(match.group(1))}{match.group(2).upper()}"


def _memory(value, where):
    if isinstance(value, str):
        checked = _text(value, where)
        if isinstance(checked, Deferred):
            return checked
    if isinstance(value, bool):
        raise where.error(
            "memory must be a positive integer MiB value or size string",
            rule_id="value.not-a-memory")
    if isinstance(value, int):
        if value <= 0:
            raise where.error("memory must be a positive integer MiB value",
                rule_id="value.not-a-memory")
        return value
    size = _size(value, where)
    match = _SIZE.fullmatch(size)
    byte_count = int(match.group(1)) * _UNIT_BYTES[match.group(2)]
    if byte_count % _MIB:
        raise where.error(
            f"memory must resolve to a whole MiB value, got: {value!r}",
            rule_id="value.not-a-memory")
    return byte_count // _MIB


def _cpus(value, where):
    if isinstance(value, str):
        checked = _text(value, where)
        if isinstance(checked, Deferred):
            return checked
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise where.error(f"cpus must be a positive integer, got: {value!r}",
            rule_id="value.not-a-count")
    return value


def _flag(value, where):
    if not isinstance(value, bool):
        raise where.error(f"{where} must be true or false, got: {value!r}",
            rule_id="value.not-a-boolean")
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
            raise where.error(
                f"{where}: a '${{{qualified[0].qualifier}:…}}' reference is "
                "whole-value only — it names a location, it does not build "
                "one by interpolation", rule_id="ref.not-whole-value")
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
    raise where.error(
        f"{where}: unrecognized location scheme {scheme + ':'!r} in "
        f"{value!r} — write a bare path, an http(s) URL, or the object form",
        rule_id="value.unknown-scheme")


_LOCATION_OBJECT_FORMS = ("url", "local", "parent", "property")


def _location_object(value, where, register):
    unknown = set(value) - set(_LOCATION_OBJECT_FORMS) - {"path"}
    if unknown:
        bad = sorted(unknown)[0]
        raise where.at(value, bad).error(
            f"unknown location field: {where}.{bad}",
            rule_id="field.unknown")
    forms = [name for name in _LOCATION_OBJECT_FORMS if name in value]
    if len(forms) != 1:
        allowed = ", ".join(_LOCATION_OBJECT_FORMS)
        raise where.error(
            f"{where} must declare exactly one of {allowed}",
            rule_id="field.not-exactly-one")
    form = forms[0]
    if form != "parent" and "path" in value:
        raise where.error(
            f"{where}.path belongs to the parent form, not {form!r}",
            rule_id="field.not-for-this-form")
    if form == "url":
        return Location(kind="url",
                        url=_text(value["url"], where.at(value, "url")))
    if form == "local":
        return Location(kind="local",
                        local=_text(value["local"],
                                    where.at(value, "local")))
    if form == "property":
        return Location(
            kind="property",
            property_key=_plain(value["property"],
                                where.at(value, "property")))
    parent = value["parent"]
    if isinstance(parent, collections.abc.Mapping):
        # An inline parent: a container that exists only to be descended
        # into need not be declared separately.
        inline = _media(parent, register, where=where.at(value, "parent"))
        parent_name = inline.name
        if parent_name is None:
            raise where.error(
                f"{where}.parent must be a named media: an inline parent is "
                "a container to descend into, so it needs an identity",
                rule_id="media.inline-parent")
    else:
        parent_name = _media_name(parent, where.at(value, "parent"))
    path = None
    if "path" in value:
        path = _containment_path(
            _plain(value["path"], where.at(value, "path")),
            where.at(value, "path"))
    return Location(kind="parent", parent=parent_name, path=path)


def _location(value, where, register):
    """Parse a media's ``location``: one rung, or a mirror list."""
    if isinstance(value, list):
        if not value:
            raise where.error(
                f"{where} must not be an empty list — a mirror list holds "
                "the locations to try in order", rule_id="value.empty-mirror")
        rungs = []
        for index, entry in enumerate(value):
            if isinstance(entry, list):
                raise where.at(value, index).error(
                    f"{where}[{index}] must not be a nested list — a mirror "
                    "list is flat", rule_id="value.nested-mirror")
            rungs.extend(_location(entry, where.at(value, index), register))
        return tuple(rungs)
    if isinstance(value, str):
        return (_location_string(value, where),)
    if isinstance(value, collections.abc.Mapping):
        return (_location_object(value, where, register),)
    raise where.error(
        f"{where} must be a location string, a location object, or a list "
        f"of them, got: {value!r}", rule_id="value.not-a-location")


# --- media -----------------------------------------------------------

_MEDIA_FIELDS = {"type", "name", "materialize", "size", "location", "sha256",
                 "read-only", "extension", "description", "notes", "children"}
_CHILD_FIELDS = (_MEDIA_FIELDS - {"location"}) | {"path"}
_MACHINE_VOCABULARY = {"platform", "backend", "memory", "cpus", "drives",
                       "boot", "scripts", "control-planes",
                       "pointing-device", "backend-settings", "parameters"}


def _unknown_media_field(unknown, where, container):
    bad = sorted(unknown)[0]
    site = where.at(container, bad)
    if bad in _MACHINE_VOCABULARY:
        raise site.error(
            f"unknown media field: {where}.{bad} — {bad!r} is machine "
            "vocabulary; did you mean to declare \"type\": \"machine\"? "
            "(type defaults to media)", rule_id="field.unknown")
    raise site.error(f"unknown media field: {where}.{bad}",
        rule_id="field.unknown")


def _media(value, register, *, where=_MEDIA, path=None, allow_anonymous=False):
    """Parse one media spec, registering it and any children it declares.

    ``path`` marks a ``children`` entry, whose location is its parent
    plus that path rather than a ``location`` of its own.
    """
    if isinstance(value, str) and path is None:
        value = {"location": value}
    if not isinstance(value, collections.abc.Mapping):
        raise where.error(f"{where} must be an object, got: {value!r}",
            rule_id="value.not-an-object")
    fields = _CHILD_FIELDS if path is not None else _MEDIA_FIELDS
    unknown = set(value) - fields
    if unknown:
        if path is not None and "location" in unknown:
            raise where.error(
                f"{where}: a children entry takes a path, not a location — "
                "its location is its parent plus that path",
                rule_id="media.child-takes-a-path")
        _unknown_media_field(unknown, where, value)
    _check_type_echo(value, "media", where)

    location = ()
    if path is not None:
        location = (path,)
    elif "location" in value:
        location = _location(value["location"], where.at(value, "location"),
                             register)

    materialize = _text(value["materialize"], where.at(value, "materialize"),
                        closed=True, allowed=_MATERIALIZE) \
        if "materialize" in value else None
    size = _size(value["size"], where.at(value, "size")) \
        if "size" in value else None
    if materialize is None:
        # A spec carrying a size and no location is a blank: there is
        # nothing else it could be, which is what lets the drive-inline
        # blank be written {"size": "20M"}.
        materialize = "new" if size is not None and not location else "use"
    if materialize == "new":
        if location:
            raise where.error(
                f"{where}: a 'new' blank takes a size, not a location",
                rule_id="media.new-with-location")
        if size is None:
            raise where.error(f"{where}: a 'new' blank requires a size",
                rule_id="media.new-without-size")
    else:
        if not location:
            raise where.error(
                f"{where}: a '{materialize}' media requires a location",
                rule_id="media.without-location")
        if size is not None:
            raise where.error(
                f"{where}: a '{materialize}' media takes a location, not a "
                "size", rule_id="media.size-not-allowed")

    if "name" in value:
        name = _media_name(value["name"], where.at(value, "name"))
    elif materialize == "new" and allow_anonymous:
        name = None
    else:
        name = _derive_name(location, where)

    media = Media(
        name=name,
        materialize=materialize,
        size=size,
        location=location,
        sha256=_sha256(value["sha256"], where.at(value, "sha256"))
        if "sha256" in value else None,
        read_only=_flag(value["read-only"], where.at(value, "read-only"))
        if "read-only" in value else None,
        extension=_plain(value["extension"], where.at(value, "extension"))
        if "extension" in value else None,
        description=_text(value["description"], where.at(value, "description"))
        if "description" in value else None,
        notes=_text(value["notes"], where.at(value, "notes"))
        if "notes" in value else None,
        anonymous=name is None)
    if name is not None:
        register("media", name, media)
    if "children" in value:
        if name is None:
            raise where.error(
                f"{where}: a container with children needs a name for them "
                "to hang from", rule_id="media.container-unnamed")
        _children(value["children"], name, register,
                  where.at(value, "children"))
    return media


def _children(value, parent, register, where):
    """Desugar a ``children`` batch into child-declares-parent specs.

    ``where`` names the ``children`` array itself, so each entry's
    breadcrumb is composed from it rather than rebuilt.
    """
    if not isinstance(value, list):
        raise where.error(f"{where} must be an array",
            rule_id="value.not-an-array")
    for index, entry in enumerate(value):
        site = where.at(value, index)
        if isinstance(entry, str):
            entry = {"path": entry}
        if not isinstance(entry, collections.abc.Mapping):
            raise site.error(
                f"{site} must be a path string or a media object, "
                f"got: {entry!r}", rule_id="value.not-a-child")
        if "path" not in entry:
            raise site.error(f"{site} requires a path",
                rule_id="media.child-without-path")
        location = Location(
            kind="parent", parent=parent,
            path=_containment_path(
                _plain(entry["path"], site.at(entry, "path")),
                site.at(entry, "path")))
        _media(entry, register, where=site, path=location)


def _check_type_echo(value, expected, where):
    """An optional ``type`` at a nested position is a checked echo."""
    if "type" not in value:
        return
    declared = _plain(value["type"], where.at(value, "type"))
    if declared in _RETIRED_TYPES:
        raise where.error(
            f"{where}: the {declared!r} spec type is retired — a source is "
            "now a media's location, and an archive is a media other media "
            "name as their parent", rule_id="field.type-retired")
    if declared not in _SPEC_TYPES:
        allowed = ", ".join(sorted(_SPEC_TYPES))
        raise where.error(
            f"{where}.type must be one of {allowed}, got: {declared!r}",
            rule_id="field.type-unknown")
    if declared != expected:
        raise where.error(
            f"{where}.type says {declared!r} but this position is a "
            f"{expected}", rule_id="field.type-mismatch")


# --- machine ---------------------------------------------------------

_MACHINE_FIELDS = {
    "type", "name", "platform", "backend", "memory", "cpus", "drives", "boot",
    "description", "scripts", "control-planes", "pointing-device",
    "backend-settings", "parameters",
}
_STATE_ONLY = {"id", "backend-id", "blueprint-digest", "blueprint-source"}
_DRIVE_FIELDS = {"media", "controller", "enabled"}


def _drive_key(value, where):
    if not isinstance(value, str):
        raise where.error(f"drive keys must be strings, got: {value!r}",
            rule_id="value.not-a-string")
    if "${" in value:
        raise where.error(
            f"drive key {value!r} takes no reference: an object key is "
            "authored graph, and the graph stays static",
            rule_id="ref.not-allowed-here")
    match = _DRIVE_KEY.fullmatch(value)
    if not match:
        raise where.error(
            f"invalid drive key {value!r}: expected floppy[0..1], "
            "hdd[0..3], or cdrom[0..3]", rule_id="drive.key-invalid")
    medium = match.group(1)
    slot = int(match.group(2) or 0)
    if slot >= _SLOT_LIMITS[medium]:
        raise where.error(
            f"invalid drive key {value!r}: {medium} slots run from "
            f"0 to {_SLOT_LIMITS[medium] - 1}",
            rule_id="drive.slot-out-of-range")
    return medium, slot, f"{medium}{slot}"


def _controller(value, key, medium, where):
    if medium == "floppy":
        raise where.error(
            f"drives.{key}.controller is invalid: floppies take no "
            "controller key", rule_id="drive.controller-on-floppy")
    return _text(value, where, closed=True, allowed=_CONTROLLERS)


def _drive(value, key, medium, slot, register, where):
    if value is None:
        if medium == "hdd":
            raise where.error(
                f"drives.{key} cannot be null: only removable drives "
                "(floppy, cdrom) may be declared empty",
                rule_id="drive.null-not-removable")
        return MachineDrive(key=key, medium=medium, slot=slot)
    if isinstance(value, str):
        return MachineDrive(key=key, medium=medium, slot=slot,
                            media=_media_name(value, where))
    if not isinstance(value, collections.abc.Mapping):
        raise where.error(
            f"drives.{key} must be a media name, null, a drive object, or "
            "an inline media", rule_id="value.not-a-drive")
    if set(value) - _DRIVE_FIELDS:
        # Not the hardware-attribute object, so it is an inline media:
        # a full spec, or the {"size": ...} blank.
        inline = _media(value, register, where=where, allow_anonymous=True)
        return MachineDrive(key=key, medium=medium, slot=slot,
                            media=inline.name, inline=inline)
    if "media" not in value:
        raise where.error(
            f"drives.{key} must name a media (or be null for an empty "
            "removable slot)", rule_id="drive.without-media")
    controller = (_controller(
        value["controller"], key, medium,
        where.at(value, "controller", f"drives.{key}.controller"))
        if "controller" in value else None)
    return MachineDrive(
        key=key, medium=medium, slot=slot,
        media=_media_name(value["media"],
                          where.at(value, "media", f"drives.{key}.media")),
        controller=controller,
        enabled=_flag(value.get("enabled", True),
                      where.at(value, "enabled", f"drives.{key}.enabled")))


def _drives(value, register, where):
    if not isinstance(value, collections.abc.Mapping):
        raise where.error("drives must be an object",
            rule_id="value.not-an-object")
    normalized, claimed = {}, {}
    for authored_key, declaration in value.items():
        site = where.at(value, authored_key, f"drives.{authored_key}")
        medium, slot, key = _drive_key(authored_key, site)
        if key in claimed:
            raise site.error(
                f"drive key clash: {claimed[key]!r} and {authored_key!r} "
                f"both mean {key}", rule_id="drive.key-clash")
        claimed[key] = authored_key
        normalized[key] = _drive(declaration, key, medium, slot, register,
                                 where.at(value, authored_key,
                                          f"drives.{key}"))
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


def _boot(value, drives, where):
    if not isinstance(value, list):
        raise where.error("boot must be an array of drive keys",
            rule_id="value.not-an-array")
    normalized, seen = [], set()
    for index, authored_key in enumerate(value):
        site = where.at(value, index, f"boot[{index}]")
        _, _, key = _drive_key(authored_key, site)
        if key not in drives:
            raise site.error(
                f"boot[{index}] references undeclared drive {key}",
                rule_id="drive.boot-undeclared")
        if not drives[key].enabled:
            raise site.error(f"boot[{index}] references disabled drive {key}",
                rule_id="drive.boot-disabled")
        if key in seen:
            raise site.error(f"boot contains duplicate drive {key}",
                rule_id="drive.boot-duplicate")
        seen.add(key)
        normalized.append(key)
    return tuple(normalized)


def _scripts(value, where):
    if not isinstance(value, collections.abc.Mapping):
        raise where.error("scripts must be an object",
            rule_id="value.not-an-object")
    normalized = {}
    for label, script in value.items():
        site = where.at(value, label, f"scripts.{label}")
        label = _plain(label, where.at(value, label, "scripts label"))
        script = _plain(script, site)
        if (script in (".", "..") or "/" in script or "\\" in script
                or script.lower().endswith(".rlqs")):
            raise site.error(
                f"scripts.{label} must be the file stem under scripts/, "
                f"got: {script!r}", rule_id="value.not-a-script-stem")
        normalized[label] = script
    return types.MappingProxyType(normalized)


def _control_planes(value, where):
    if not isinstance(value, list):
        raise where.error("control-planes must be an array of strings",
            rule_id="value.not-an-array")
    normalized, seen = [], set()
    for index, entry in enumerate(value):
        site = where.at(value, index, f"control-planes[{index}]")
        plane = _text(entry, site, closed=True, allowed=_CONTROL_PLANES)
        if plane in seen:
            raise site.error(f"control-planes contains duplicate {plane!r}",
                rule_id="machine.control-plane-duplicate")
        seen.add(plane)
        normalized.append(plane)
    return tuple(normalized)


def _backend_settings(value, where):
    if not isinstance(value, collections.abc.Mapping):
        raise where.error("backend-settings must be an object",
            rule_id="value.not-an-object")
    normalized = {}
    for backend_name, section in value.items():
        site = where.at(value, backend_name,
                        f"backend-settings.{backend_name}")
        if backend_name not in _BACKENDS:
            allowed = ", ".join(sorted(_BACKENDS))
            raise site.error(
                f"backend-settings names unknown backend {backend_name!r}; "
                f"expected one of {allowed}",
                rule_id="machine.backend-unknown")
        if not isinstance(section, collections.abc.Mapping):
            raise site.error(
                f"backend-settings.{backend_name} must be an object",
                rule_id="value.not-an-object")
        normalized[backend_name] = types.MappingProxyType(dict(section))
    return types.MappingProxyType(normalized)


def _parameters(value, where):
    if not isinstance(value, collections.abc.Mapping):
        raise where.error("parameters must be an object",
            rule_id="value.not-an-object")
    normalized = {}
    for key, binding in value.items():
        site = where.at(value, key, f"parameters.{key}")
        key = _plain(key, where.at(value, key, "parameters key"))
        if isinstance(binding, str):
            normalized[key] = _text(binding, site)
        elif isinstance(binding, collections.abc.Mapping):
            if set(binding) != {"property"}:
                raise site.error(
                    f"parameters.{key} must be a string or a "
                    '{"property": "<key>"} redirect',
                    rule_id="value.not-a-parameter")
            normalized[key] = types.MappingProxyType(
                {"property": _plain(
                    binding["property"],
                    site.at(binding, "property",
                            f"parameters.{key}.property"))})
        else:
            raise site.error(
                f"parameters.{key} must be a string or a "
                '{"property": "<key>"} redirect',
                rule_id="value.not-a-parameter")
    return types.MappingProxyType(normalized)


def _machine(value, register, *, where=_MACHINE):
    if not isinstance(value, collections.abc.Mapping):
        raise where.error(f"{where} must be a JSON object",
            rule_id="value.not-an-object")

    def at(key, text=None):
        """This machine's field, under the breadcrumb it has always had."""
        return where.at(value, key, text if text is not None else key)

    unknown = set(value) - _MACHINE_FIELDS
    if unknown:
        bad = sorted(unknown)[0]
        if bad in _STATE_ONLY:
            raise at(bad).error(
                f"{bad} is a state-only field and is not valid in a blueprint",
                rule_id="field.state-only")
        raise at(bad).error(f"unknown machine field: {bad}",
            rule_id="field.unknown")
    if "platform" not in value:
        raise where.error("platform is required", rule_id="field.required")
    platform = _text(value["platform"], at("platform"), closed=True,
                     allowed=_PLATFORMS)
    if "name" not in value:
        raise where.error(f"{where} requires a name", rule_id="field.required")
    name = _machine_name(value["name"], at("name"))
    drives = _drives(value["drives"], register, at("drives")) \
        if "drives" in value else types.MappingProxyType({})
    empty = types.MappingProxyType({})
    register("machine", name, Machine(
        name=name,
        platform=platform,
        backend=_text(value["backend"], at("backend"), closed=True,
                      allowed=_BACKENDS) if "backend" in value else None,
        memory=_memory(value["memory"], at("memory"))
        if "memory" in value else None,
        cpus=_cpus(value["cpus"], at("cpus")) if "cpus" in value else None,
        drives=drives,
        boot=_boot(value["boot"], drives, at("boot")) if "boot" in value
        else _default_boot(drives),
        description=_text(value["description"], at("description"))
        if "description" in value else None,
        scripts=_scripts(value["scripts"], at("scripts"))
        if "scripts" in value else empty,
        control_planes=_control_planes(value["control-planes"],
                                       at("control-planes"))
        if "control-planes" in value else (),
        pointing_device=_text(value["pointing-device"],
                              at("pointing-device"), closed=True,
                              allowed=_POINTING_DEVICES)
        if "pointing-device" in value else None,
        backend_settings=_backend_settings(value["backend-settings"],
                                           at("backend-settings"))
        if "backend-settings" in value else empty,
        parameters=_parameters(value["parameters"], at("parameters"))
        if "parameters" in value else empty))


# --- document --------------------------------------------------------

def _spec_type(value, where):
    """The declared type, or the ``media`` default."""
    if not isinstance(value, collections.abc.Mapping):
        return "media"
    if "type" not in value:
        return "media"
    declared = _plain(value["type"], where.at(value, "type"))
    if declared in _RETIRED_TYPES:
        raise where.error(
            f"{where}: the {declared!r} spec type is retired — a source is "
            "now a media's location, and an archive is a media that other "
            "media name as their parent", rule_id="field.type-retired")
    if declared not in _SPEC_TYPES:
        allowed = ", ".join(sorted(_SPEC_TYPES))
        raise where.error(
            f"{where}.type must be one of {allowed}, got: {declared!r}",
            rule_id="field.type-unknown")
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
    root = _rooted(value, "blueprint")
    if isinstance(value, collections.abc.Mapping):
        sections = set(value) & _RETIRED_SECTIONS
        if sections and "type" not in value:
            bad = sorted(sections)[0]
            raise root.at(value, bad).error(
                f"the plural {bad!r} section is retired: a "
                "blueprint root is an array of specs (a lone spec object is "
                "the array of one)", rule_id="blueprint.section-retired")
        entries = [value]
    elif isinstance(value, list):
        entries = value
    else:
        raise root.error(
            "a blueprint must be an array of specs or a lone spec object, "
            f"got {type(value).__name__}", rule_id="blueprint.not-a-document")

    buckets = {"machine": {}, "media": {}}
    # The site of the spec being parsed, so a clash raised from inside
    # `register` -- which sees names and not fields -- still points at
    # the spec that tried to claim the name.
    site = root

    def register(kind, name, spec):
        bucket = buckets[kind]
        if name in bucket:
            raise site.error(
                f"duplicate {kind} name {name!r} in one document",
                rule_id="name.duplicate-in-document")
        folded = {existing.lower() for existing in bucket}
        if name.lower() in folded:
            raise site.error(
                f"{kind} name {name!r} collides case-insensitively with "
                "another in this document: names match exactly but the "
                "media cache is name-keyed on filesystems that do not",
                rule_id="name.case-collision")
        bucket[name] = spec

    for index, entry in enumerate(entries):
        text = f"spec[{index}]" if len(entries) > 1 else "spec"
        # The lone-object sugar puts the spec in a list this function
        # made, which carries no positions -- so the lookup misses and
        # falls back to the root, which *is* that spec.
        where = root.at(entries, index, text)
        site = where
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
        raise where.error(
            f"{where}: a bare remote location has nowhere to carry its "
            f"sha256 — write the object form: "
            f'{{"location": {entry!r}, "sha256": "…"}}',
            rule_id="media.remote-without-hash")


def load_document(path):
    """Load and parse one ``.rlqb`` document.

    This is the entry point that has a *file* to point into, so it is
    the one that asks for positions and hands the diagnostic its source
    line. ``parse_document`` on a bare value stays exactly as it was:
    there is nothing to cite, and citing nothing is honest.

    Having the file also makes this the anchor point: every relative
    ``local`` location is made absolute against the file's own
    directory, which is what "relative to the referencing file" means.
    A bare value parsed through ``parse_document`` keeps its paths as
    authored — there is no file to anchor to.
    """
    path = os.path.abspath(os.fspath(path))
    if not os.path.exists(path):
        raise PreflightError(f"blueprint not found: {path}",
            rule_id="blueprint.unknown")
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()
    value = json5reader.loads(text, positions=True)
    try:
        parsed = parse_document(value)
    except BlueprintError as error:
        error._set_context(path, text.split("\n"))
        raise
    return _anchored_document(parsed, os.path.dirname(path))


def _anchored_document(doc, base):
    """The document with every relative ``local`` path made absolute.

    Anchoring happens at load, before any cross-document work, so
    downstream layers only ever see what a spec actually points at.
    That includes the namespace's identity dedup: two same-named specs
    carrying one relative spelling in two directories are different
    media, and they collide instead of silently resolving through
    whichever file was read first.
    """
    media = {name: _anchored_media(spec, base)
             for name, spec in doc.media.items()}
    machines = {name: _anchored_machine(spec, base)
                for name, spec in doc.machines.items()}
    return Document(machines=types.MappingProxyType(machines),
                    media=types.MappingProxyType(media))


def _anchored_machine(machine, base):
    """The machine with its drives' inline media anchored."""
    if not any(drive.inline is not None
               for drive in machine.drives.values()):
        return machine
    drives = {key: (replace(drive, inline=_anchored_media(drive.inline, base))
                    if drive.inline is not None else drive)
              for key, drive in machine.drives.items()}
    return replace(machine, drives=types.MappingProxyType(drives))


def _anchored_media(media, base):
    """The media with each relative ``local`` rung made absolute."""
    location = tuple(_anchored_location(rung, base)
                     for rung in media.location)
    if location == media.location:
        return media
    return replace(media, location=location)


def _anchored_location(rung, base):
    if rung.kind != "local" or os.path.isabs(rung.local):
        return rung
    return replace(rung,
                   local=os.path.normpath(os.path.join(base, rung.local)))
