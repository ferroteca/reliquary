# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Media acquisition and cache reclamation.

Media are specs inside a ``.rlqb``, parsed by ``document.py`` and
resolved by ``resolve.py``; the fetch plan they produce is executed by
``acquire.py``. This module is the thin name-level surface the CLI and
its API twins drive: resolve a media by name, fetch its verified
payload, list the catalog, and reclaim the one ``cache/media/``.

The cache holds only what Reliquary can produce again — every payload
arrived by download or extraction, so nothing here is irreplaceable and
no verb needs to ask where a file came from before reclaiming it (D41).
A file a person supplies stays where they put it and is declared by a
media spec (``blueprint.add_media``); it never enters this directory.

The reclamation verbs differ in what they know:

- ``clean_media()`` is **blunt** — it takes everything back.
- ``clean_media(name)`` is **targeted** — the user named it, so it goes.
- ``prune_media()`` is **informed** — it keeps the attachment closure
  and drops what only existed to produce it.

Design: docs/spec/blueprint-model.md ("The cache").
"""

import os
import shutil

from .acquire import fetch_media as _acquire_fetch
from .errors import PreflightError
from .home import media_dir
from .resolve import load_namespace, resolve_media


def fetch_media(name, context=None, on_mismatch="fail", progress="auto"):
    """Return the named media's verified payload path, fetching on demand.

    Resolves the media by name from the active resolution source and
    runs its fetch plan. A blank has no payload and returns ``None``.

    Stream-bearing: ``progress`` selects the live rendering of the
    transfer and verification events (``auto | pretty | plain |
    jsonl``), the same vocabulary and the same event kinds a run's own
    fetches ride (docs/spec/media-spec.md, "Fetch progress").
    The stream is ephemeral — nothing is written down (D36).
    """
    from .progress import stream_for
    namespace = load_namespace(context)
    media = resolve_media(name, namespace)
    events = stream_for(progress)
    try:
        return _acquire_fetch(media, namespace, context, on_mismatch,
                              events=events)
    finally:
        events.close()


def list_media(context=None):
    """Return sorted media names from the catalog.

    Yours alone, from the active resolution source. There is no codex
    mode: media are components inside a ``.rlqb`` and there is no
    ``seed-media``, so listing the library's would enumerate parts
    that cannot be ordered (D88).
    """
    return sorted(load_namespace(context).media)


# --- the cache -------------------------------------------------------

def _cached_files(context=None):
    """Map cached media name -> path from the directory.

    Every payload is written as ``<media-name>.<ext>``, so the stem is
    the name; a file dropped in by hand is identified the same way and
    is reclaimable like any other.
    """
    root = media_dir(context)
    if not os.path.isdir(root):
        return {}
    return {os.path.splitext(item.name)[0]: item.path
            for item in os.scandir(root) if item.is_file()}


def _attached_media(context=None):
    """Media names attached to any existing machine, with their phase."""
    from .machines import list_machines, load_machine_state
    attached = {}
    for machine in list_machines(context):
        try:
            state = load_machine_state(machine["id"], context)
        except (OSError, PreflightError):
            continue
        running = state.get("phase") == "running"
        for drive in state.get("drives", {}).values():
            name = drive.get("media")
            if name:
                attached[name] = attached.get(name, False) or running
    return attached


def _remove(path):
    if os.path.isdir(path):
        shutil.rmtree(path)
    else:
        os.remove(path)


def clean_media(name=None, *, context=None):
    """Reclaim cached payloads. Returns the names reclaimed.

    Blunt with no argument: the cache holds only what can be fetched or
    derived again, so everything goes. A payload attached to a
    *running* machine is skipped, since the guest is holding it open.

    With a name, the eviction is targeted — the same rule, narrowed to
    the one the user named.
    """
    cached = _cached_files(context)
    attached = _attached_media(context)
    if name is not None:
        if name not in cached:
            return []
        targets = {name: cached[name]}
    else:
        targets = dict(cached)
    reclaimed = []
    for candidate, path in sorted(targets.items()):
        if attached.get(candidate):
            continue
        _remove(path)
        reclaimed.append(candidate)
    return reclaimed


def attachment_closure(context=None):
    """The media the active scope still needs cached.

    A media is in the closure when something can *attach* it: a machine
    holds it, or the catalog declares it and nothing else derives from
    it. What falls out is the intermediate container — once its
    children are cached, the husk it was extracted from is not needed
    to run anything, and re-deriving it is a download away.

    A container whose children are **not** cached stays: it is still
    the only way to produce them.
    """
    namespace = load_namespace(context)
    cached = _cached_files(context)
    parents = {}
    for name, media in namespace.media.items():
        for rung in media.location:
            if rung.kind == "parent" and rung.path is not None:
                parents.setdefault(rung.parent, set()).add(name)
    closure = set(_attached_media(context))
    for name in namespace.media:
        children = parents.get(name)
        if not children:
            closure.add(name)
        elif not all(child in cached for child in children):
            closure.add(name)
    return closure


def prune_media(*, context=None, dry_run=False):
    """Drop cached payloads outside the attachment closure.

    Scope-relative: the closure is computed against the media the
    active resolution source declares and the machines that exist, so
    pruning in one project never reasons about another's. Returns the
    names pruned — with ``dry_run``, the names that would be.
    """
    cached = _cached_files(context)
    closure = attachment_closure(context)
    attached = _attached_media(context)
    pruned = []
    for name, path in sorted(cached.items()):
        if name in closure or attached.get(name):
            continue
        if not dry_run:
            _remove(path)
        pruned.append(name)
    return pruned
