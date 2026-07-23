# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Whole-source resolution over composed blueprint documents.

Parses every ``.rlqb`` in the active asset source into one
``(name, type)`` component namespace, and resolves a media's ``source``
down to an executable **fetch plan** — a nested download/extract tree —
that the acquisition layer runs. Cross-document ``(name, type)``
collisions are errors naming both files.

Design: planning/design/blueprint-model.md ("Components, identity,
resolution").
"""

import types
from dataclasses import dataclass
from typing import Mapping, Optional, Tuple

from . import assets, document

_KINDS = ("machines", "media", "sources", "archives")


@dataclass(frozen=True)
class Namespace:
    """The merged component namespace of a resolution source."""

    machines: Mapping[str, document.Machine]
    media: Mapping[str, document.Media]
    sources: Mapping[str, document.Source]
    archives: Mapping[str, document.Archive]
    # (kind, name) -> file path the component was authored in.
    origin: Mapping[Tuple[str, str], str] = types.MappingProxyType({})


def build_namespace(paths):
    """Parse each ``.rlqb`` path and merge into one namespace.

    Two components of one kind and name — across any files in the
    source — are a collision error naming both files.
    """
    buckets = {kind: {} for kind in _KINDS}
    origin = {}
    for path in paths:
        doc = document.load_document(path)
        sections = {"machines": doc.machines, "media": doc.media,
                    "sources": doc.sources, "archives": doc.archives}
        for kind, components in sections.items():
            bucket = buckets[kind]
            for name, component in components.items():
                if name in bucket:
                    raise ValueError(
                        f"two {kind[:-1]} components both named {name!r}:\n"
                        f"  {origin[(kind, name)]}\n  {path}")
                bucket[name] = component
                origin[(kind, name)] = path
    return Namespace(
        machines=types.MappingProxyType(buckets["machines"]),
        media=types.MappingProxyType(buckets["media"]),
        sources=types.MappingProxyType(buckets["sources"]),
        archives=types.MappingProxyType(buckets["archives"]),
        origin=types.MappingProxyType(origin))


def load_namespace(context=None):
    """Build the namespace from the active asset source."""
    return build_namespace(assets.source_for(context).document_files())


def namespace_of(doc):
    """A single-document namespace (no cross-file provenance)."""
    return Namespace(machines=doc.machines, media=doc.media,
                     sources=doc.sources, archives=doc.archives)


def resolve_media(name, namespace):
    """Return the :class:`document.Media` named ``name``, or raise."""
    try:
        return namespace.media[name]
    except KeyError:
        raise KeyError(f"no media named {name!r}")


# --- fetch plan ------------------------------------------------------

@dataclass(frozen=True)
class Download:
    """Fetch bytes from one of the given mirror URLs."""

    urls: Tuple[str, ...]
    sha256: Optional[str] = None


@dataclass(frozen=True)
class LocalFile:
    """Use bytes from a host file (outside the cache)."""

    path: str
    sha256: Optional[str] = None


@dataclass(frozen=True)
class Extract:
    """Extract ``member`` from the archive produced by ``inner``."""

    archive: str
    member: str
    inner: object
    sha256: Optional[str] = None


def resolve_plan(locator, namespace, _seen=()):
    """Resolve a locator to a nested download/extract fetch plan."""
    if locator.kind == "url":
        return Download(urls=locator.urls, sha256=locator.sha256)
    if locator.kind == "local":
        return LocalFile(path=locator.local, sha256=locator.sha256)
    if locator.kind == "ref":
        name = locator.ref
        if ("source", name) in _seen:
            raise ValueError(f"source reference cycle at {name!r}")
        source = namespace.sources.get(name)
        if source is None:
            raise KeyError(
                f"no source named {name!r} to resolve this reference")
        return resolve_plan(
            source.locator, namespace, _seen + (("source", name),))
    if locator.kind == "archive":
        name = locator.archive
        if ("archive", name) in _seen:
            raise ValueError(f"archive reference cycle at {name!r}")
        archive = namespace.archives.get(name)
        if archive is None:
            raise KeyError(f"no archive named {name!r} to extract from")
        inner = resolve_plan(
            archive.source, namespace, _seen + (("archive", name),))
        return Extract(archive=name, member=locator.path,
                       inner=inner, sha256=archive.sha256)
    raise ValueError(f"unresolvable locator kind {locator.kind!r}")


def resolve_media_plan(media, namespace):
    """The fetch plan for a media's payload, or ``None`` for ``new``."""
    if media.source is None:
        return None
    return resolve_plan(media.source, namespace)
