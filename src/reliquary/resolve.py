# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Whole-source resolution over composed blueprint documents.

Parses every ``.rlqb`` file in the active asset source into one
catalog — specs identified by ``(name, type)`` — and turns a media's
location into an executable **fetch plan**: a tree of downloads and
extracts that the acquisition layer runs.

This is the second half of two-phase validation. `document.py`
checks each field's shape at parse time; this module checks the
actual values once references have resolved. That includes: the rule
that a remote location must carry a sha256 (parse time can't know a
referenced rung will resolve to a URL, so this has to be checked
here), finishing every deferred value, and checking containment —
that a referenced parent media actually exists, naming any cycle
found, and checking the container format is one this build supports.

Design: docs/spec/blueprint-model.md ("Resolution", "Containment",
"Two-phase validation").
"""

import os
import types
from dataclasses import dataclass
from typing import Mapping, Optional, Tuple

from . import assets, document
from .errors import InternalError, PreflightError

# Only these container formats can be read from. Currently just zip;
# ISO9660 (including its El Torito [BOOT] virtual paths) is planned
# as a follow-on. Reading other filesystem image formats is out of
# scope before beta.
_CONTAINER_FORMATS = {"zip"}


@dataclass(frozen=True)
class Namespace:
    """The merged catalog of a resolution source."""

    machines: Mapping[str, document.Machine]
    media: Mapping[str, document.Media]
    # (kind, name) -> the file the spec was authored in.
    origin: Mapping[Tuple[str, str], str] = types.MappingProxyType({})


def build_namespace(paths):
    """Parse each ``.rlqb`` path and merge into one catalog.

    A spec's identity is its ``(name, type)`` pair. Two specs with the
    same identity are allowed to coexist if they're identical — that's
    what lets a self-contained blueprint be copied into another
    project without conflict — but if they differ, that's an error
    naming both files. Duplicate specs within a single file were
    already rejected when that file was parsed.
    """
    buckets = {"machine": {}, "media": {}}
    origin = {}
    for path in paths:
        doc = document.load_document(path)
        for kind, specs in (("machine", doc.machines), ("media", doc.media)):
            bucket = buckets[kind]
            for name, spec in specs.items():
                if name in bucket:
                    if bucket[name] == spec:
                        continue  # identity-dedup: the same spec twice
                    raise PreflightError(
                        f"two different {kind} specs are both named "
                        f"{name!r}:\n  {origin[(kind, name)]}\n  {path}\n"
                        "identical specs may coexist; differing ones "
                        "must be renamed",
                        rule_id="name.duplicate-spec")
                folded = {existing.lower(): existing for existing in bucket}
                if name.lower() in folded:
                    other = folded[name.lower()]
                    raise PreflightError(
                        f"{kind} names {name!r} and {other!r} differ only by "
                        f"case:\n  {origin[(kind, other)]}\n  {path}\n"
                        "names match exactly but the media cache is "
                        "name-keyed on filesystems that do not",
                        rule_id="name.case-collision")
                bucket[name] = spec
                origin[(kind, name)] = path
    return Namespace(
        machines=types.MappingProxyType(buckets["machine"]),
        media=types.MappingProxyType(buckets["media"]),
        origin=types.MappingProxyType(origin))


def load_namespace(context=None):
    """Build the catalog from the active asset source."""
    return build_namespace(assets.source_for(context).document_files())


def namespace_of(doc):
    """A single-document catalog (no cross-file provenance)."""
    return Namespace(machines=doc.machines, media=doc.media)


def resolve_media(name, namespace):
    """Return the :class:`document.Media` named ``name``, or raise."""
    try:
        return namespace.media[name]
    except KeyError:
        raise PreflightError(f"no media named {name!r}",
                             rule_id="media.unknown")


# --- fetch plan ------------------------------------------------------

@dataclass(frozen=True)
class Download:
    """Fetch bytes from the given URL."""

    url: str
    sha256: Optional[str] = None


@dataclass(frozen=True)
class LocalFile:
    """Use bytes from a host path (outside the cache)."""

    path: str
    sha256: Optional[str] = None


@dataclass(frozen=True)
class Extract:
    """Extract ``member`` from the container ``inner`` produces."""

    parent: str
    member: str
    inner: object
    sha256: Optional[str] = None


@dataclass(frozen=True)
class Alternatives:
    """Mirror locations to try in order. Whichever one succeeds must match the hash — the URL itself doesn't need to."""

    options: Tuple[object, ...]


def _unbound_failure(where, keys):
    names = ", ".join("${" + key + "}" for key in sorted(keys))
    return PreflightError(
        f"{where} needs {names}, and no property supplies it; bind it with "
        "--property, a blueprint parameter, the environment, the properties "
        "file, or (on a terminal) interactively",
        rule_id="prop.unbound-reference")


def _render_deferred(deferred, properties, where):
    """Substitute a deferred string's references with bound values.

    If a reference resolves to a value that is itself another
    reference, this raises an error instead of resolving further — a
    location can only bind once; it cannot chain through another
    reference.
    """
    text = deferred.text
    for reference in deferred.references:
        key = reference.target
        value = properties.get(key)
        if value is None:
            raise _unbound_failure(where, [key])
        if "${" in value:
            raise _chaining_failure(where, key, value)
        text = text.replace(reference.text, value)
    return text


def render_text(deferred, properties, where):
    """Substitute a deferred string's references with bound values.

    The same substitution `_hash_of`/`_rung_plan` already apply to
    media fields, exposed for a Deferred-carrying field that doesn't
    go through a media plan at all — a network device's `interface`
    (D120).
    """
    return _render_deferred(deferred, properties, where)


def _chaining_failure(where, key, value):
    return PreflightError(
        f"{where}: the property ${{{key}}} resolved to {value!r}, which is "
        "itself a reference; a location binds once and does not "
        "chain", rule_id="prop.reference-chains")


def _location_from_value(value, where):
    """Interpret a bound location string as a concrete url/local rung.

    If the resolved value names another media or property, that's
    chaining, and it's refused: a location has to bind directly to
    bytes, not point at another reference.
    """
    location = document.location_from_string(value, where)
    if location.kind not in ("url", "local"):
        raise PreflightError(
            f"{where}: the bound location {value!r} is a "
            f"{location.kind} reference; a location must resolve to a "
            "path or URL, not to another media or property",
            rule_id="media.location-not-a-path")
    return location


def _container_format(plan, parent_media):
    """The parent media's container format (e.g. "zip"), or raise an
    error naming what format was expected.

    If the media declares an ``extension`` field, that wins — the same
    way it does when naming the cached payload file
    (``acquire.payload_extension``). This matters because a download
    URL doesn't always end in a recognizable extension: a SourceForge
    "/download" link, for example, or any other URL with no filename
    in it. Without a declared ``extension``, the format is guessed
    from the plan instead: the URL's path (ignoring any "?" query or
    "#" fragment) for a download, the file path for a local file, the
    member name for an extracted file, or — for a list of mirrors —
    by checking the first one.
    """
    extension = (parent_media.extension or "").lower()
    if not extension:
        if isinstance(plan, Download):
            source = plan.url.split("#", 1)[0].split("?", 1)[0]
        elif isinstance(plan, LocalFile):
            source = plan.path
        elif isinstance(plan, Extract):
            source = plan.member
        elif isinstance(plan, Alternatives):
            return _container_format(plan.options[0], parent_media)
        else:
            source = ""
        extension = os.path.splitext(source)[1].lstrip(".").lower()
    if extension not in _CONTAINER_FORMATS:
        supported = ", ".join(sorted(_CONTAINER_FORMATS))
        raise PreflightError(
            f"media {parent_media.name!r} is read as a container but its "
            f"format {extension or 'unknown'!r} is not supported "
            f"(supported: {supported})",
            rule_id="media.container-unsupported")
    return extension


def _rung_plan(rung, media, namespace, seen, properties):
    if rung.kind == "url":
        return Download(url=rung.url, sha256=_hash_of(media, properties))
    if rung.kind == "local":
        return LocalFile(path=rung.local, sha256=_hash_of(media, properties))
    if rung.kind == "property":
        where = f"media {media.name!r}"
        value = properties.get(rung.property_key)
        if value is None:
            raise _unbound_failure(where, [rung.property_key])
        if "${" in value:
            raise _chaining_failure(where, rung.property_key, value)
        return _rung_plan(_location_from_value(value, where),
                          media, namespace, seen, properties)
    if rung.kind == "deferred":
        where = f"media {media.name!r}"
        value = _render_deferred(rung.deferred, properties, where)
        return _rung_plan(_location_from_value(value, where),
                          media, namespace, seen, properties)
    if rung.kind == "parent":
        return _parent_plan(rung, media, namespace, seen, properties)
    raise InternalError(f"unresolvable location kind {rung.kind!r}")


def _parent_plan(rung, media, namespace, seen, properties):
    name = rung.parent
    if name in seen:
        cycle = " -> ".join(seen + (name,))
        raise PreflightError(f"containment cycle: {cycle}",
                             rule_id="media.containment-cycle")
    parent = namespace.media.get(name)
    if parent is None:
        raise PreflightError(
            f"no media named {name!r} for {media.name!r} to come "
            "from", rule_id="media.unknown-parent")
    inner = _media_plan(parent, namespace, seen + (name,), properties)
    if inner is None:
        raise PreflightError(
            f"media {name!r} is a blank and has no bytes for "
            f"{media.name!r} to come from",
            rule_id="media.parent-has-no-bytes")
    if rung.path is None:
        # A bare ${media:X} with no path means the parent's own bytes
        # — this is how a difference overlay names the media it's
        # built on top of.
        return inner
    _container_format(inner, parent)
    # Each plan node's sha256 is the hash of the file it produces.
    # This Extract node produces the child, so it gets the child's
    # hash; the parent's own hash is already attached to `inner`.
    return Extract(parent=name, member=rung.path, inner=inner,
                   sha256=_hash_of(media, properties))


def _hash_of(media, properties):
    if isinstance(media.sha256, document.Deferred):
        value = _render_deferred(
            media.sha256, properties, f"the sha256 of media {media.name!r}")
        return value
    return media.sha256


def _media_plan(media, namespace, seen=(), properties=None):
    if properties is None:
        properties = {}
    if not media.location:
        return None
    plans = tuple(_rung_plan(rung, media, namespace, seen, properties)
                  for rung in media.location)
    if any(isinstance(plan, Download) for plan in plans) \
            and _hash_of(media, properties) is None:
        raise PreflightError(
            f"media {media.name!r} has a remote location and must carry a "
            "sha256: the hash is what verifies the payload is the exact "
            "build the scripts target",
            rule_id="media.remote-without-hash")
    return plans[0] if len(plans) == 1 else Alternatives(options=plans)


def resolve_media_plan(media, namespace, properties=None):
    """The fetch plan for a media's payload, or ``None`` for a blank.

    ``properties`` supplies the values for any ``${key}`` reference in
    a location or sha256 field (milestone 8, T5). Without it, a
    location that has such a reference raises an error naming the
    media and the missing key.
    """
    return _media_plan(media, namespace, properties=properties)


def location_property_keys(media, namespace, _seen=()):
    """Every property key referenced by a media's location or sha256,
    including those on any parent it's contained in.

    This walks the whole containment chain, so a create command knows
    every key it needs to bind before it can materialize the media.
    A qualified ``${media:…}`` reference points at structure (a parent
    media), not a property, so it doesn't add anything to the result.
    """
    keys = set()
    if media.name in _seen:
        return keys
    seen = _seen + (media.name,)
    if isinstance(media.sha256, document.Deferred):
        keys.update(ref.target for ref in media.sha256.references)
    for rung in media.location or ():
        if rung.kind == "property":
            keys.add(rung.property_key)
        elif rung.kind == "deferred":
            keys.update(ref.target for ref in rung.deferred.references)
        elif rung.kind == "parent":
            parent = namespace.media.get(rung.parent)
            if parent is not None:
                keys.update(
                    location_property_keys(parent, namespace, seen))
    return keys
