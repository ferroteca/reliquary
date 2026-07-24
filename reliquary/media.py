# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Media acquisition over the composed blueprint model.

Media, sources, and archives are components parsed by
``document.py`` and resolved by ``resolve.py``; the fetch plan they
produce is executed by ``acquire.py``. This module is the thin
name-level convenience the CLI/API drive: resolve a media name against
the active source namespace, fetch its verified payload, list the
catalog, and reclaim the caches.
"""

import os

from .acquire import fetch_media as _acquire_fetch
from .home import archives_cache_dir, media_cache_dir
from .resolve import load_namespace, resolve_media


def fetch_media(name, context=None, on_mismatch="fail"):
    """Return the named media's verified payload path, fetching on demand.

    Resolves the media component by name from the active resolution
    source and runs its fetch plan (planning/design/blueprint-model.md).
    A ``new`` media has no payload and returns ``None``.
    """
    namespace = load_namespace(context)
    media = resolve_media(name, namespace)
    return _acquire_fetch(media, namespace, context, on_mismatch)


def list_media(context=None, *, builtin=False):
    """Return sorted media component names from the catalog.

    The active resolution source by default; with ``builtin=True``, the
    package codex (never seeds or writes).
    """
    if builtin:
        from .library import list_builtin_media
        return list(list_builtin_media())
    return sorted(load_namespace(context).media)


def _clean(cache):
    if not os.path.isdir(cache):
        return
    for entry in os.scandir(cache):
        if entry.is_file():
            os.remove(entry.path)


def clean_archives(context=None):
    """Delete all cached source archives (``cache/archives/``)."""
    _clean(archives_cache_dir(context))


def clean_media(context=None):
    """Delete all cached media payloads (``cache/media/``)."""
    _clean(media_cache_dir(context))
