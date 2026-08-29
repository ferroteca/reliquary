# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Media acquisition and cache reclamation.

Media are specs inside a ``.rlqb`` file, parsed by ``document.py``
and resolved by ``resolve.py``; ``acquire.py`` executes the fetch
plan they produce. This module is the simple, name-based interface
the CLI and its API equivalents use: look up a media by name, fetch
its verified payload, list what's in the catalog, and clear space in
the one ``cache/media/`` directory.

The cache only ever holds files Reliquary can produce again — every
payload in it arrived by download or extraction, so nothing there is
irreplaceable, and none of the functions below need to check where a
file came from before deleting it (D41). A file the user supplies
themselves stays exactly where they put it, declared by a media spec
(``blueprint.add_media``); it's never copied into this directory.

The three functions that clear cache space differ in how much they
know about what's safe to remove:

- ``clean_media()`` with no argument is blunt — it clears everything.
- ``clean_media(name)`` is targeted — the user named exactly what to
  remove, so that's what goes.
- ``prune_media()`` is selective — it keeps everything the current
  project still needs and removes only what was there solely to
  produce something else.

Design: docs/spec/blueprint-model.md ("The cache").
"""

import os
import shutil

from .acquire import fetch_media as _acquire_fetch
from .errors import PreflightError
from .home import media_dir
from .machines import list_machines, load_machine_state
from .progress import stream_for
from .resolve import load_namespace, resolve_media


def fetch_media(name, context=None, on_mismatch="fail", progress="auto"):
    """Return the named media's verified payload path, fetching on demand.

    Looks up the media by name in the active resolution source and
    runs its fetch plan. A blank media has no payload and this
    returns ``None``.

    ``progress`` picks how transfer and verification events are shown
    live (``auto | pretty | plain | jsonl``) — the same choices and
    the same event types a run uses for its own fetches
    (docs/spec/media-spec.md, "Fetch progress"). Nothing about this
    progress display is saved anywhere; it's shown and then gone (D36).
    """
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

    Only from the active resolution source — the user's own project.
    There's no library/codex equivalent: media are pieces declared
    inside a ``.rlqb`` file, not standalone things you can seed like a
    blueprint, so listing the library's would just enumerate pieces
    that can't be used on their own (D88).
    """
    return sorted(load_namespace(context).media)


# --- the cache -------------------------------------------------------

def _cached_files(context=None):
    """Map cached media name -> path from the directory.

    Every payload is written as ``<media-name>.<ext>``, so the media
    name is just the filename without its extension. A file someone
    drops into the cache directory by hand is identified the same
    way, and can be removed like any other cached file.
    """
    root = media_dir(context)
    if not os.path.isdir(root):
        return {}
    return {os.path.splitext(item.name)[0]: item.path
            for item in os.scandir(root) if item.is_file()}


def _attached_media(context=None):
    """Media names attached to any existing machine, mapped to whether that machine is running."""
    attached = {}
    for machine in list_machines(context):
        try:
            state = load_machine_state(machine["id"], context)
        except (OSError, PreflightError):
            continue
        running = state.get("phase") == "running"
        for drive in state.get("devices", {}).values():
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
    """Delete cached payloads. Returns the names that were deleted.

    With no argument, this deletes everything in the cache: since the
    cache only holds files that can be fetched or derived again,
    that's safe. A payload currently attached to a *running* machine
    is skipped, since the running guest still has it open.

    With a name, only that one media is deleted, following the same
    running-machine exception.
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
    """The set of media names the current project still needs cached.

    A media belongs in this set if something could actually attach
    it: either a machine already has it on a drive, or it's declared
    in the catalog and nothing else is extracted from it. What's
    excluded is a container media that's only there to produce other
    media: once everything extracted from it is cached, the container
    itself isn't needed to run anything, and it can always be
    downloaded again later if needed.

    A container is kept, though, if any of its children are *not yet*
    cached — it's still the only way to produce them.
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
    """Delete cached payloads that aren't in the attachment closure.

    The closure is computed from the media declared in the active
    resolution source and the machines that currently exist, so
    pruning in one project never touches media that belong to
    another. Returns the names deleted — or, with ``dry_run``, the
    names that would have been deleted.
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
