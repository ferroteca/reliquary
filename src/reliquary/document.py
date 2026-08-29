# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Parses a blueprint document's specs into one catalog.

A ``.rlqb`` root is an array of **specs**. Each spec is either a
``machine`` or a ``media`` (``type`` defaults to ``media`` when not
given). A single spec object is accepted as shorthand for an array
containing just that one spec. This module parses one document into
a :class:`Document`; it does not resolve references between
documents — binding a drive to its media, or a child to its parent,
happens in ``resolve.py``.

Validation happens in two phases: this module checks shape (is the
field the right type, is the value one of the allowed choices); the
actual value is checked later, at resolution. A field holding a
``${...}`` reference can't be checked yet, because its value depends
on what the reference resolves to — so it's parsed into a
:class:`Deferred` and checked later.

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
_BACKENDS = {"qemu", "virtualbox", "vmware", "hyperv"}
_CONTROLLERS = {"ide", "sata", "scsi", "nvme", "virtio"}
_ATTACHMENTS = {"nat", "bridged"}
_NIC_MODELS = {"pcnet", "ne2k"}
_CONTROL_PLANES = {"agentless-display", "vnc", "serial-console", "guest-agent"}
_POINTING_DEVICES = {"tablet", "mouse"}
_MATERIALIZE = {"new", "difference", "copy", "use"}
_SPEC_TYPES = {"machine", "media"}
# These spec types existed in the original four-component model and
# were retired. They're still named here so a blueprint using them
# gets a specific error message instead of a generic "unknown type".
_RETIRED_TYPES = {"source", "archive"}
_RETIRED_SECTIONS = {"machines", "media", "sources", "archives"}

_DEVICE_KEY = re.compile(r"(floppy|hdd|cdrom|net)(\d+)?")
_SLOT_LIMITS = {"floppy": 2, "hdd": 4, "cdrom": 4, "net": 4}
_DRIVE_MEDIA = {"floppy", "hdd", "cdrom"}
_SIZE = re.compile(r"([1-9][0-9]*)([KMGTkmgt])")
_SHA256 = re.compile(r"[0-9a-fA-F]{64}")
_MIB = 1024 * 1024
_UNIT_BYTES = {"K": 1024, "M": _MIB, "G": 1024 * _MIB, "T": 1024 * 1024 * _MIB}

# The rules for a valid media name (D24): the same as the script
# language's `name` pattern, except a media name may start with a
# digit. _PROPERTY_KEY is kept separate and must start with a letter,
# because a property key can appear bare in a declaration where a
# leading digit would otherwise be read as a duration (like "5m").
# Parentheses and brackets aren't in the character set — not because
# the grammar forbids them, but because every media name is passed as
# a command-line argument to fetch-media / add-media / clean-media,
# where those characters have special meaning to the shell.
_MEDIA_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_PROPERTY_KEY = re.compile(r"[A-Za-z][A-Za-z0-9._-]*")

# Checking a reference body takes two steps, and both are needed (D26,
# corrected by D27). This pattern is the first step: it rejects
# characters that should never appear, like |, (, [, ?, =, and
# whitespace. The second step is the code below, which rejects
# strings that pass this pattern but are still wrong. For example,
# `${mem:-512M}` (bash-style default-value syntax) is made entirely
# of characters this pattern allows, so it passes here — it's the
# code below that rejects it, because "mem" isn't a real qualifier.
_REFERENCE_BODY = re.compile(r"[A-Za-z0-9._:/-]+")

_KNOWN_QUALIFIERS = {"media"}
# A qualifier names which namespace to look a reference up in — never
# an action to perform. More qualifiers may be added later; these
# names are reserved for that even though only "media" is implemented.
_RESERVED_QUALIFIERS = {"property", "env", "file", "machine", "script",
                        "landmark", "secret"}

_SCHEME = re.compile(r"([A-Za-z][A-Za-z0-9+.-]*):")
_REMOTE_SCHEMES = {"http", "https"}


class BlueprintWarning(UserWarning):
    """Warns about an authoring mistake this module repaired instead of rejecting, reported at its source location."""


# --- located diagnostics ---------------------------------------------

class BlueprintError(StaticError):
    """A blueprint diagnostic that can also report where it happened.

    This is a STATIC ERROR like every other diagnostic this module
    raises, which means it exits with code 2: the document's text
    alone is enough to tell it's invalid, no need to run anything.
    What's new here is a line/column position, the same thing
    :class:`~reliquary.script_nodes.ScriptParseError` has always
    carried for script files, rendered using the same format (D70).

    The position is optional, and having none isn't a bug. A document
    loaded from a file path gets one. A value passed straight into the
    public ``parse_document`` function never does — there's no source
    text to point into — and in that case the error renders exactly
    as it did before positions existed. The field breadcrumb (like
    "machine.drives.hdd0") is present either way and stays in the
    message text itself, rather than being handled only by the
    rendering code, so an error with no position still reads the same
    as it always has.
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
    """Names a field (as a breadcrumb like "machine.drives.hdd0") and
    tracks its position in the source, if there is one.

    It replaces what used to be a plain breadcrumb string, and prints
    the same way, so any message built as ``f"{where}: ..."`` still
    reads the same. The addition is the position, carried alongside
    the breadcrumb text and attached to whatever error the field
    raises.

    Moving to a child field is explicit: ``where.at(container, key)``
    takes the container the key belongs to, rather than storing it in
    advance. A position that quietly gets out of sync with the field
    it's supposed to name is worse than having no position — and a
    value that has to be passed in each time can't drift out of sync.
    """

    __slots__ = ("text", "position")

    def __init__(self, text, position=None):
        self.text = text
        self.position = position

    def __str__(self):
        return self.text

    def at(self, container, key, text=None):
        """The breadcrumb for ``container[key]``, positioned at its key.

        If ``container`` has no position data — a plain ``dict``, from
        a value passed straight into the public entry point — this
        falls back to the parent's own position, so an error deep in
        an unpositioned document still points at the closest thing we
        do know.

        ``text`` overrides the breadcrumb wording for fields that were
        never built from their parent's breadcrumb: the machine side
        writes ``drives.hdd0.media``, while the media side writes
        ``spec[0].location``. That difference predates positions and
        is kept exactly as it was — this change is only about where an
        error points, not what it says.
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


# Default breadcrumbs with no position, used when a caller doesn't
# pass one in. Reaching one of these means the call site never
# threaded a breadcrumb through — which is how every call worked
# before positions were added.
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
    """A value that contains one or more references, checked fully at
    resolution time.

    This module only checks the value's shape (that it's a string with
    references in it). The actual value can't be checked yet, since a
    reference could resolve to anything — the field's own parser has
    to check it once it knows. That's what "two-phase validation"
    means.
    """

    text: str
    references: Tuple[Reference, ...]


@dataclass(frozen=True)
class Location:
    """One entry in a media's location list (a "rung"). Exactly one
    ``kind`` applies.

    ``url`` — download from a URL. ``local`` — a path on the host,
    relative to the file it was written in (made absolute when the
    document is loaded from a file). ``parent`` — a member inside
    another media (``path`` is optional; no path means the parent's
    own bytes, unextracted). ``property`` — supplied by a property.
    ``deferred`` — a string containing references that must resolve
    before this location can be used.
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
    """A media spec: describes content, and how to materialize it.

    ``read_only`` is ``None`` when not set explicitly; its actual
    default (true for a cdrom, false otherwise) is decided later, at
    materialization. ``location`` is the tuple of mirrors to try, and
    is empty for a ``new`` blank disk. ``anonymous`` marks a
    content-free blank that has no name of its own: it's named after
    its drive slot at materialization time, and a script can't refer
    to it by name.
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

    ``inline`` holds a media spec written directly at the drive
    instead of declared separately. If that inline media has a name,
    it's registered in the catalog like any other media and ``media``
    names it; an anonymous blank has no name and only exists here, on
    this drive.
    """

    key: str
    medium: str
    slot: int
    media: Optional[str] = None
    controller: Optional[str] = None
    enabled: bool = True
    inline: Optional[Media] = None


@dataclass(frozen=True)
class MachineNetwork:
    """One NIC slot: an attachment, and optional hardware attributes.

    ``interface`` only ever matters for ``bridged`` — ``nat`` needs
    nothing host-specific. ``model`` overrides the platform-resolved
    chipset (D122) — omitted, it resolves per platform at
    materialization (D120), orthogonal to attachment, the same way a
    drive's ``controller`` defaults to ``ide`` without being named.
    """

    key: str
    slot: int
    attachment: str
    interface: Optional[Union[str, Deferred]] = None
    model: Optional[str] = None


@dataclass(frozen=True)
class Machine:
    """Machine topology. A device names a medium (a drive) or an
    attachment (a NIC); content lives on the media a drive names.

    ``devices`` is the one authoritative field, matching the
    blueprint's own merged shape (D121) — a slot-keyed map of
    :class:`MachineDrive` and :class:`MachineNetwork` values sharing
    one keyspace. ``drives`` and ``network`` are read-only computed
    views over it, filtered by type: most of the engine only ever
    wants one kind or the other (materialization only touches
    drives; requirements-gathering wants both, separately), and a
    view keeps that filter in one place instead of repeated inline
    ``isinstance`` checks at every call site.
    """

    name: str
    platform: str
    backend: Optional[str] = None
    memory: Optional[Union[int, Deferred]] = None
    cpus: Optional[Union[int, Deferred]] = None
    devices: Mapping[str, Union[MachineDrive, MachineNetwork]] = \
        field(default_factory=dict)

    @property
    def drives(self):
        return types.MappingProxyType({
            key: device for key, device in self.devices.items()
            if isinstance(device, MachineDrive)})

    @property
    def network(self):
        return types.MappingProxyType({
            key: device for key, device in self.devices.items()
            if isinstance(device, MachineNetwork)})
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

    ``_REFERENCE_BODY`` filters out characters that should never
    appear; the checks below then decide whether what's left is
    actually valid. Neither check alone is sufficient on its own (D27).
    """
    if not body:
        raise where.error(
            f"{where}: empty reference '${{}}' — name a property key or a "
            "qualified target", rule_id="ref.empty")
    if "\\" in body:
        # A Windows user's natural first guess is a backslash path.
        # Give a specific error naming the actual rule, instead of the
        # generic "malformed reference" message below.
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
    """Validate an authored string, and check whether it's allowed to
    contain a reference.

    ``closed`` marks a field with a fixed set of allowed values, where
    a reference is refused outright — that's exactly where an editor's
    autocomplete is most useful and a reference would break it (D26).
    ``allowed`` is that fixed set of values, checked only once we know
    the value has no reference in it.
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
    """An authored string that must never contain a reference (used for identity fields like names)."""
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
    """Derive a media name from the media's own content, or fail.

    Neither the drive slot nor the ``.rlqb`` filename is ever used to
    name a media — the name always comes from the payload itself, so
    copying a spec into a different file gives the same result. A stem
    with invalid characters is repaired and a warning is raised; a
    stem that can't be repaired, or doesn't exist at all, is a hard
    failure that requires an explicit name instead.
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

    This is the function T5 uses to re-interpret a location value that
    came from a resolved property: a path, a URL, or — refused, since
    chaining isn't allowed — another reference.
    """
    return _location_string(value, where)


def _location_string(value, where):
    """Interpret one location string by its scheme (bare path, URL, or reference).

    A string location is shorthand: every string this function accepts
    has an equivalent, more explicit object form, which is the
    canonical form the string is being translated into.
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
        # A single letter followed by ':' is a Windows drive letter,
        # not a URL scheme — "C:/isos/x.iso" is a local path.
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
        # The parent is written inline: a container that exists only
        # to hold this media doesn't need to be declared as its own
        # separate spec.
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
_MACHINE_VOCABULARY = {"platform", "backend", "memory", "cpus", "devices",
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

    ``path`` is set when parsing a ``children`` entry: that media's
    location is its parent plus this path, instead of a ``location``
    field of its own.
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
        # A spec with a size but no location can only be a blank disk
        # — there's nothing else it could mean. That's what lets an
        # inline blank on a drive be written as just {"size": "20M"}.
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
    """Expand a ``children`` list into individual media specs, each
    pointing back at ``parent``.

    ``where`` names the ``children`` array itself, so each entry's
    breadcrumb is built from it rather than starting over.
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
    """If a nested spec repeats its own ``type``, check that it matches ``expected``."""
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
    "type", "name", "platform", "backend", "memory", "cpus", "devices",
    "boot", "description", "scripts", "control-planes",
    "pointing-device", "backend-settings", "parameters",
}
_STATE_ONLY = {"id", "backend-id", "blueprint-digest", "blueprint-source"}
_DRIVE_FIELDS = {"media", "controller", "enabled"}
_NETWORK_FIELDS = {"attachment", "interface", "model"}


def _device_key(value, where):
    """Parse one authored device key: any medium sharing the keyspace
    (D121) — floppy/hdd/cdrom (a drive) or net (a NIC)."""
    if not isinstance(value, str):
        raise where.error(f"device keys must be strings, got: {value!r}",
            rule_id="value.not-a-string")
    if "${" in value:
        raise where.error(
            f"device key {value!r} takes no reference: an object key is "
            "authored graph, and the graph stays static",
            rule_id="ref.not-allowed-here")
    match = _DEVICE_KEY.fullmatch(value)
    if not match:
        raise where.error(
            f"invalid device key {value!r}: expected floppy[0..1], "
            "hdd[0..3], cdrom[0..3], or net[0..3]",
            rule_id="device.key-invalid")
    medium = match.group(1)
    slot = int(match.group(2) or 0)
    if slot >= _SLOT_LIMITS[medium]:
        raise where.error(
            f"invalid device key {value!r}: {medium} slots run from "
            f"0 to {_SLOT_LIMITS[medium] - 1}",
            rule_id="device.slot-out-of-range")
    return medium, slot, f"{medium}{slot}"


def _controller(value, key, medium, where):
    if medium == "floppy":
        raise where.error(
            f"devices.{key}.controller is invalid: floppies take no "
            "controller key", rule_id="drive.controller-on-floppy")
    return _text(value, where, closed=True, allowed=_CONTROLLERS)


def _drive(value, key, medium, slot, register, where):
    if value is None:
        if medium == "hdd":
            raise where.error(
                f"devices.{key} cannot be null: only removable drives "
                "(floppy, cdrom) may be declared empty",
                rule_id="drive.null-not-removable")
        return MachineDrive(key=key, medium=medium, slot=slot)
    if isinstance(value, str):
        return MachineDrive(key=key, medium=medium, slot=slot,
                            media=_media_name(value, where))
    if not isinstance(value, collections.abc.Mapping):
        raise where.error(
            f"devices.{key} must be a media name, null, a drive object, or "
            "an inline media", rule_id="value.not-a-drive")
    if set(value) - _DRIVE_FIELDS:
        # This object has fields _DRIVE_FIELDS doesn't recognize, so
        # it isn't a drive-attribute object — it's an inline media
        # spec instead (a full spec, or a {"size": ...} blank).
        inline = _media(value, register, where=where, allow_anonymous=True)
        return MachineDrive(key=key, medium=medium, slot=slot,
                            media=inline.name, inline=inline)
    if "media" not in value:
        raise where.error(
            f"devices.{key} must name a media (or be null for an empty "
            "removable slot)", rule_id="drive.without-media")
    controller = (_controller(
        value["controller"], key, medium,
        where.at(value, "controller", f"devices.{key}.controller"))
        if "controller" in value else None)
    return MachineDrive(
        key=key, medium=medium, slot=slot,
        media=_media_name(value["media"],
                          where.at(value, "media", f"devices.{key}.media")),
        controller=controller,
        enabled=_flag(value.get("enabled", True),
                      where.at(value, "enabled", f"devices.{key}.enabled")))


def _interface(value, attachment, where):
    if attachment != "bridged":
        raise where.error(
            f"{where} is invalid: only a bridged attachment takes an "
            "interface", rule_id="network.interface-on-nat")
    return _text(value, where)


def _network_device(value, key, slot, where):
    if isinstance(value, str):
        return MachineNetwork(
            key=key, slot=slot,
            attachment=_text(value, where, closed=True,
                             allowed=_ATTACHMENTS))
    if not isinstance(value, collections.abc.Mapping):
        raise where.error(
            f"devices.{key} must be an attachment name or an object "
            "carrying attachment/interface/model",
            rule_id="value.not-a-network")
    if set(value) - _NETWORK_FIELDS:
        raise where.error(
            f"devices.{key} carries unknown keys; expected attachment, "
            "interface, model", rule_id="field.unknown")
    if "attachment" not in value:
        raise where.error(f"devices.{key} must name an attachment",
            rule_id="network.without-attachment")
    attachment = _text(value["attachment"],
                       where.at(value, "attachment",
                                f"devices.{key}.attachment"),
                       closed=True, allowed=_ATTACHMENTS)
    interface = (_interface(
        value["interface"], attachment,
        where.at(value, "interface", f"devices.{key}.interface"))
        if "interface" in value else None)
    model = (_text(value["model"],
                   where.at(value, "model", f"devices.{key}.model"),
                   closed=True, allowed=_NIC_MODELS)
            if "model" in value else None)
    return MachineNetwork(key=key, slot=slot, attachment=attachment,
                          interface=interface, model=model)


def _devices(value, register, where):
    """Parse the merged ``devices`` map: drives and NICs share one
    keyspace and one key-clash check (D121), dispatched by medium
    once the key itself is parsed."""
    if not isinstance(value, collections.abc.Mapping):
        raise where.error("devices must be an object",
            rule_id="value.not-an-object")
    normalized, claimed = {}, {}
    for authored_key, declaration in value.items():
        site = where.at(value, authored_key, f"devices.{authored_key}")
        medium, slot, key = _device_key(authored_key, site)
        if key in claimed:
            raise site.error(
                f"device key clash: {claimed[key]!r} and {authored_key!r} "
                f"both mean {key}", rule_id="device.key-clash")
        claimed[key] = authored_key
        site = where.at(value, authored_key, f"devices.{key}")
        if medium == "net":
            normalized[key] = _network_device(declaration, key, slot, site)
        else:
            normalized[key] = _drive(declaration, key, medium, slot,
                                     register, site)
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


def _boot(value, devices, where):
    """Validate ``boot`` against the drive-shaped subset of ``devices``
    — a NIC is never bootable, so ``net0`` is refused here exactly
    like a genuinely undeclared key (D121)."""
    drives = {key: device for key, device in devices.items()
             if isinstance(device, MachineDrive)}
    if not isinstance(value, list):
        raise where.error("boot must be an array of drive keys",
            rule_id="value.not-an-array")
    normalized, seen = [], set()
    for index, authored_key in enumerate(value):
        site = where.at(value, index, f"boot[{index}]")
        _, _, key = _device_key(authored_key, site)
        if key not in drives:
            raise site.error(
                f"boot[{index}] references {key}, which is not a "
                "declared, bootable drive", rule_id="drive.boot-undeclared")
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
        """This machine's field, using the same breadcrumb wording as before positions were added."""
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
    devices = _devices(value["devices"], register, at("devices")) \
        if "devices" in value else types.MappingProxyType({})
    device_drives = {key: device for key, device in devices.items()
                     if isinstance(device, MachineDrive)}
    empty = types.MappingProxyType({})
    register("machine", name, Machine(
        name=name,
        platform=platform,
        backend=_text(value["backend"], at("backend"), closed=True,
                      allowed=_BACKENDS) if "backend" in value else None,
        memory=_memory(value["memory"], at("memory"))
        if "memory" in value else None,
        cpus=_cpus(value["cpus"], at("cpus")) if "cpus" in value else None,
        devices=devices,
        boot=_boot(value["boot"], devices, at("boot")) if "boot" in value
        else _default_boot(device_drives),
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

    The root is normally an array of specs. A single spec object is
    accepted as shorthand for a one-element array, following the same
    rules — so an untyped lone object counts as a *media* spec, since
    ``type`` defaults to media everywhere. A bare string is shorthand
    for a media spec of ``{"location": ...}``. Two specs of the same
    type and name in one document are always an error, even if
    they're identical.

    ``stem`` is accepted but ignored: the ``.rlqb`` file's own filename
    stem is never used as an identity.
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
    # Tracks the spec currently being parsed. `register` only sees
    # names, not field breadcrumbs, so it uses this to point a
    # name-clash error at the spec that tried to claim the name.
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
        # When the root was a lone spec object, `entries` is a
        # one-element list this function built, not the original
        # parsed document, so it has no position data. The lookup on
        # it misses and falls back to root's own position, which is
        # correct here since root *is* that one spec.
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

    This function has an actual file to point errors at, so it's the
    one that asks the JSON5 reader for positions and attaches the
    source line to any error. ``parse_document``, called on a value
    that didn't come from a file, still works exactly as before: with
    no file to cite, it just doesn't cite one.

    Having a file also means this function can anchor relative paths:
    every relative ``local`` location is made absolute against the
    directory the file is in, which is what "relative to the
    referencing file" means. A value parsed through ``parse_document``
    directly keeps its paths exactly as written — there's no file to
    anchor them to.
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

    This happens right when the document is loaded, before any
    cross-document work runs, so every later step sees exactly what a
    spec actually points at. That matters for name deduplication too:
    two specs with the same name but the same relative path written in
    two different directories are actually different media, and this
    ensures they're treated as a name collision rather than silently
    resolving to whichever file happened to load first.
    """
    media = {name: _anchored_media(spec, base)
             for name, spec in doc.media.items()}
    machines = {name: _anchored_machine(spec, base)
                for name, spec in doc.machines.items()}
    return Document(machines=types.MappingProxyType(machines),
                    media=types.MappingProxyType(media))


def _anchored_machine(machine, base):
    """The machine with its drives' inline media anchored."""
    if not any(isinstance(device, MachineDrive) and device.inline is not None
               for device in machine.devices.values()):
        return machine
    devices = {
        key: (replace(device, inline=_anchored_media(device.inline, base))
              if isinstance(device, MachineDrive) and device.inline is not None
              else device)
        for key, device in machine.devices.items()}
    return replace(machine, devices=types.MappingProxyType(devices))


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
