# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Whole-source resolution over composed blueprint documents.

Parses every ``.rlqb`` in the active asset source into one catalog —
specs identified by ``(name, type)`` — and resolves a media's location
down to an executable **fetch plan**: a nested download/extract tree the
acquisition layer runs.

This is the second half of two-phase validation. Shape was checked at
parse; value is checked here, where references have bound: the
``sha256``-required-once-remote rule (a referenced rung may resolve to a
URL, so parse could not know) and every deferred coercion land at this
layer, as does containment — parents exist, cycles are named, and the
container-format roster is enforced.

Design: docs/spec/blueprint-model.md ("Resolution", "Containment",
"Two-phase validation").
"""

import os
import types
from dataclasses import dataclass
from typing import Mapping, Optional, Tuple

from . import assets, document

# Container reading is roster-gated by format: zip this milestone.
# ISO9660 and its [BOOT] El Torito virtual paths are the recorded
# follow-on; reading filesystem images is out pre-beta.
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

    Identity is ``(name, type)``. Canonically identical specs of one
    identity **coexist** — which is what lets a self-contained blueprint
    be pasted around — while differing specs **collide**, naming both
    files. In-file duplicates were already refused at parse.
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
                    raise ValueError(
                        f"two different {kind} specs are both named "
                        f"{name!r}:\n  {origin[(kind, name)]}\n  {path}\n"
                        "identical specs may coexist; differing ones must "
                        "be renamed")
                folded = {existing.lower(): existing for existing in bucket}
                if name.lower() in folded:
                    other = folded[name.lower()]
                    raise ValueError(
                        f"{kind} names {name!r} and {other!r} differ only by "
                        f"case:\n  {origin[(kind, other)]}\n  {path}\n"
                        "names match exactly but the media cache is "
                        "name-keyed on filesystems that do not")
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
        raise KeyError(f"no media named {name!r}")


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
    """Mirror rungs, tried in order. The hash is the arbiter, not the URL."""

    options: Tuple[object, ...]


def _unbound_failure(where, keys):
    names = ", ".join("${" + key + "}" for key in sorted(keys))
    return RuntimeError(
        f"{where} needs {names}, and no property supplies it; bind it with "
        "--property, a blueprint parameter, the environment, the properties "
        "file, or (on a terminal) interactively")


def _render_deferred(deferred, properties, where):
    """Substitute a deferred string's references with bound values.

    A reference resolving to a value that is itself a reference fails
    closed — a location binds once, it does not chain.
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


def _chaining_failure(where, key, value):
    return RuntimeError(
        f"{where}: the property ${{{key}}} resolved to {value!r}, which is "
        "itself a reference; a location binds once and does not chain")


def _location_from_value(value, where):
    """Interpret a bound location string as a concrete url/local rung.

    A resolved value naming another media or property is chaining and
    is refused; a location must bind to bytes, not to another edge.
    """
    location = document.location_from_string(value, where)
    if location.kind not in ("url", "local"):
        raise RuntimeError(
            f"{where}: the bound location {value!r} is a "
            f"{location.kind} reference; a location must resolve to a "
            "path or URL, not to another media or property")
    return location


def _container_format(plan, parent):
    """The parent's container format, or fail naming what was asked."""
    if isinstance(plan, Download):
        source = plan.url
    elif isinstance(plan, LocalFile):
        source = plan.path
    elif isinstance(plan, Extract):
        source = plan.member
    elif isinstance(plan, Alternatives):
        return _container_format(plan.options[0], parent)
    else:
        source = ""
    extension = os.path.splitext(source)[1].lstrip(".").lower()
    if extension not in _CONTAINER_FORMATS:
        supported = ", ".join(sorted(_CONTAINER_FORMATS))
        raise ValueError(
            f"media {parent!r} is read as a container but its format "
            f"{extension or 'unknown'!r} is not supported (supported: "
            f"{supported})")
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
    raise ValueError(f"unresolvable location kind {rung.kind!r}")


def _parent_plan(rung, media, namespace, seen, properties):
    name = rung.parent
    if name in seen:
        cycle = " -> ".join(seen + (name,))
        raise ValueError(f"containment cycle: {cycle}")
    parent = namespace.media.get(name)
    if parent is None:
        raise KeyError(
            f"no media named {name!r} for {media.name!r} to come from")
    inner = _media_plan(parent, namespace, seen + (name,), properties)
    if inner is None:
        raise ValueError(
            f"media {name!r} is a blank and has no bytes for {media.name!r} "
            "to come from")
    if rung.path is None:
        # A bare ${media:X}: the parent's own bytes, which is how a
        # difference overlay names what it sits on.
        return inner
    _container_format(inner, name)
    # Each plan node carries the hash of the file *it* produces: this
    # one yields the child, and the parent's own hash rode down with
    # ``inner``.
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
        raise ValueError(
            f"media {media.name!r} has a remote location and must carry a "
            "sha256: the hash is what verifies the payload is the exact "
            "build the scripts target")
    return plans[0] if len(plans) == 1 else Alternatives(options=plans)


def resolve_media_plan(media, namespace, properties=None):
    """The fetch plan for a media's payload, or ``None`` for a blank.

    ``properties`` binds any ``${key}`` location or ``sha256``
    reference (milestone 8, T5); without it, a referenced rung fails
    closed naming the media and the key.
    """
    return _media_plan(media, namespace, properties=properties)


def location_property_keys(media, namespace, _seen=()):
    """Every property key a media's location/sha256 closure references.

    Walks the containment closure so a create knows which keys to bind
    before materializing. Qualified ``${media:…}`` edges are structure,
    not property references, and contribute nothing here.
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
