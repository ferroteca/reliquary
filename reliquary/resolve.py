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

Design: planning/design/blueprint-model.md ("Resolution", "Containment",
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


def _deferred_failure(where, deferred):
    names = ", ".join(sorted(
        {reference.text for reference in deferred.references}))
    return RuntimeError(
        f"{where} needs {names}, and property binding is not implemented "
        "yet — properties are the channel these resolve through, and "
        "nothing supplies them today")


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


def _rung_plan(rung, media, namespace, seen):
    if rung.kind == "url":
        return Download(url=rung.url, sha256=_hash_of(media))
    if rung.kind == "local":
        return LocalFile(path=rung.local, sha256=_hash_of(media))
    if rung.kind == "property":
        raise RuntimeError(
            f"media {media.name!r} is located by ${{{rung.property_key}}}, "
            "and property binding is not implemented yet — properties are "
            "the channel these resolve through, and nothing supplies them "
            "today")
    if rung.kind == "deferred":
        raise _deferred_failure(f"media {media.name!r}", rung.deferred)
    if rung.kind == "parent":
        return _parent_plan(rung, media, namespace, seen)
    raise ValueError(f"unresolvable location kind {rung.kind!r}")


def _parent_plan(rung, media, namespace, seen):
    name = rung.parent
    if name in seen:
        cycle = " -> ".join(seen + (name,))
        raise ValueError(f"containment cycle: {cycle}")
    parent = namespace.media.get(name)
    if parent is None:
        raise KeyError(
            f"no media named {name!r} for {media.name!r} to come from")
    inner = _media_plan(parent, namespace, seen + (name,))
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
                   sha256=_hash_of(media))


def _hash_of(media):
    if isinstance(media.sha256, document.Deferred):
        raise _deferred_failure(f"the sha256 of media {media.name!r}",
                                media.sha256)
    return media.sha256


def _media_plan(media, namespace, seen=()):
    if not media.location:
        return None
    plans = tuple(_rung_plan(rung, media, namespace, seen)
                  for rung in media.location)
    if any(isinstance(plan, Download) for plan in plans) \
            and _hash_of(media) is None:
        raise ValueError(
            f"media {media.name!r} has a remote location and must carry a "
            "sha256: the hash is what verifies the payload is the exact "
            "build the scripts target")
    return plans[0] if len(plans) == 1 else Alternatives(options=plans)


def resolve_media_plan(media, namespace):
    """The fetch plan for a media's payload, or ``None`` for a blank."""
    return _media_plan(media, namespace)
