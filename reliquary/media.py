# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Media acquisition and cache reclamation.

Media are specs inside a ``.rlqb``, parsed by ``document.py`` and
resolved by ``resolve.py``; the fetch plan they produce is executed by
``acquire.py``. This module is the thin name-level surface the CLI and
its API twins drive: resolve a media by name, fetch its verified
payload, list the catalog, and reclaim the one ``cache/media/``.

The reclamation verbs differ in what they know:

- ``clean_media()`` is **blunt** — it takes back everything it can,
  sparing only what nothing could put back.
- ``clean_media(name)`` is **targeted** — the user named it, so it goes.
- ``prune_media()`` is **informed** — it keeps the attachment closure
  and drops what only existed to produce it.
- ``add_media(name, file)`` is the **guarded door**: a pinned media
  nothing can locate resolves by cache hit once a person supplies it.

Design: planning/design/blueprint-model.md ("The cache").
"""

import os
import shutil

from . import ledger
from .acquire import fetch_media as _acquire_fetch
from .home import media_cache_dir
from .resolve import load_namespace, resolve_media


def fetch_media(name, context=None, on_mismatch="fail", progress="auto"):
    """Return the named media's verified payload path, fetching on demand.

    Resolves the media by name from the active resolution source and
    runs its fetch plan. A blank has no payload and returns ``None``.

    Stream-bearing: ``progress`` selects the live rendering of the
    transfer and verification events (``auto | pretty | plain |
    jsonl``), the same vocabulary and the same event kinds a run's own
    fetches ride (planning/design/media-spec.md, "Fetch progress").
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


def list_media(context=None, *, builtin=False):
    """Return sorted media names from the catalog.

    The active resolution source by default; with ``builtin=True``, the
    package codex (never seeds or writes).
    """
    if builtin:
        from .library import list_builtin_media
        return list(list_builtin_media())
    return sorted(load_namespace(context).media)


# --- the cache -------------------------------------------------------

def _cached_files(context=None):
    """Map cached media name -> path, from the ledger and the directory."""
    root = media_cache_dir(context)
    if not os.path.isdir(root):
        return {}
    entries = ledger.load(context)
    by_file = {entry.get("file"): name for name, entry in entries.items()}
    found = {}
    for item in os.scandir(root):
        if not item.is_file() or item.name == os.path.basename(
                ledger.path(context)):
            continue
        # A file the ledger knows takes its recorded name; one it does
        # not is identified by its stem, so a cache predating the
        # ledger — or hand-dropped into it — is still reclaimable.
        found[by_file.get(item.name, os.path.splitext(item.name)[0])] = \
            item.path
    return found


def _attached_media(context=None):
    """Media names attached to any existing machine, with their phase."""
    from .machines import list_machines, load_machine_state
    attached = {}
    for machine in list_machines(context):
        try:
            state = load_machine_state(machine["id"], context)
        except (OSError, ValueError):
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

    Blunt with no argument: everything the project can get back on its
    own goes, and a ``supplied`` payload never does — nothing could
    re-fetch it. A payload attached to a *running* machine is skipped,
    since the guest is holding it open.

    With a name, the eviction is targeted: the user named it, so it
    goes whatever its provenance — except out from under a running
    machine.
    """
    cached = _cached_files(context)
    attached = _attached_media(context)
    if name is not None:
        if name not in cached:
            return []
        targets = {name: cached[name]}
    else:
        targets = {
            candidate: path for candidate, path in cached.items()
            if ledger.provenance(candidate, context) != ledger.SUPPLIED}
    reclaimed = []
    for candidate, path in sorted(targets.items()):
        if attached.get(candidate):
            continue
        _remove(path)
        ledger.forget(candidate, context)
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
        if ledger.provenance(name, context) == ledger.SUPPLIED:
            continue
        if not dry_run:
            _remove(path)
            ledger.forget(name, context)
        pruned.append(name)
    return pruned


def add_media(name, path, *, context=None):
    """Supply a payload nothing can locate. Returns the cached path.

    The guarded door: a media may pin a ``sha256`` and name a location
    nothing supplies — the licensed, non-redistributable case — and
    resolution fails closed until someone provides the file. This puts
    it in the cache under the media's own name, verified against the
    pin, so the blueprint never has to be edited.

    The payload is recorded ``supplied``: nothing can reproduce it, so
    no reclamation takes it back without being told to by name.
    """
    from .acquire import _sha256

    source = os.path.abspath(os.fspath(path))
    if not os.path.isfile(source):
        raise FileNotFoundError(f"no such file: {source}")
    namespace = load_namespace(context)
    media = resolve_media(name, namespace)
    if media.anonymous:
        raise ValueError(
            f"{name!r} is a blank and has no payload to supply")

    actual = _sha256(source)
    expected = media.sha256
    if isinstance(expected, str) and actual != expected:
        raise RuntimeError(
            f"{source} has SHA-256 {actual}, but media {name!r} pins "
            f"{expected}; this is not the build the blueprint means")

    extension = media.extension or os.path.splitext(source)[1].lstrip(".")
    filename = name + ("." + extension if extension else "")
    destination = os.path.join(media_cache_dir(context), filename)
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    shutil.copyfile(source, destination)
    ledger.record(name, filename=filename, sha256=actual,
                  provenance=ledger.SUPPLIED, source=source, context=context)
    return destination
