# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""The media cache's identity ledger.

``cache/media/`` is keyed by media **name**, which is what makes it
legible — the cache is not an interface, but a user who looks in it
should recognize what they see. Name-keying has one gap: two different
media of one name, in different projects, address the same slot. The
ledger closes it by recording what each cached file actually *is*.

Per entry: the sha256 observed when it was written, its **provenance**
— ``refetchable`` (a remote rung can fetch it again), ``derived`` (a
container yielded it), ``supplied`` (a person put it there, and nothing
can reproduce it) — the source it came from, and for a derived payload
its **derivation key**, the ``(parent-sha, path)`` that produced it.

Two things this buys:

- **A deterministic preflight check.** Before any fetch, the ledger
  says whether the cached file is the one this blueprint means, and if
  not, *why* — a version bump and a cross-project name collision look
  identical to a bare hash comparison and are distinguishable here at a
  glance.
- **A prune that knows what it may drop.** ``supplied`` is
  irreplaceable and is never reclaimed blindly.

Design: planning/design/blueprint-model.md ("The cache").
"""

import json
import os

from .home import media_cache_dir

_LEDGER = ".ledger.json"
_VERSION = 1

REFETCHABLE = "refetchable"
DERIVED = "derived"
SUPPLIED = "supplied"


def path(context=None):
    return os.path.join(media_cache_dir(context), _LEDGER)


def load(context=None):
    """Return the ledger as ``{name: entry}``; absent reads as empty."""
    try:
        with open(path(context), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict) or data.get("version") != _VERSION:
        return {}
    entries = data.get("media")
    return entries if isinstance(entries, dict) else {}


def _write(entries, context=None):
    destination = path(context)
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    partial = destination + ".part"
    with open(partial, "w", encoding="utf-8") as handle:
        json.dump({"version": _VERSION, "media": entries}, handle,
                  indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(partial, destination)


def record(name, *, filename, sha256, provenance, source=None,
           derivation=None, context=None):
    """Record what the cached file for ``name`` is."""
    entries = load(context)
    entry = {"file": filename, "provenance": provenance}
    if sha256:
        entry["sha256"] = sha256
    if source:
        entry["source"] = source
    if derivation:
        entry["derivation"] = derivation
    entries[name] = entry
    _write(entries, context)
    return entry


def entry(name, context=None):
    return load(context).get(name)


def forget(name, context=None):
    entries = load(context)
    if entries.pop(name, None) is None:
        return False
    _write(entries, context)
    return True


def provenance(name, context=None):
    recorded = entry(name, context)
    return recorded.get("provenance") if recorded else None


def explain(name, expected, actual, source=None, context=None):
    """Explain a cached file that is not what a blueprint now means.

    A bare hash comparison says only "these differ". The ledger knows
    where the cached bytes came from, which separates the two cases a
    user actually has to tell apart.
    """
    recorded = entry(name, context)
    if recorded is None:
        return (f"cached {name!r} has SHA-256 {actual}, but this blueprint "
                f"pins {expected}; nothing is recorded about where the "
                "cached file came from")
    was = recorded.get("source")
    how = recorded.get("provenance")
    if how == SUPPLIED:
        return (f"cached {name!r} was supplied by hand"
                + (f" from {was}" if was else "")
                + f" and has SHA-256 {actual}, but this blueprint pins "
                f"{expected}. Nothing can re-fetch it: check you supplied "
                "the build the blueprint means, or evict it deliberately "
                f"with 'clean-media {name}'")
    if was and source and was != source:
        return (f"cached {name!r} came from {was}, but this blueprint "
                f"locates it at {source}. Two different media share one "
                "name across projects — give one of them an explicit "
                "name, or isolate them with --cache")
    if was and source and was == source:
        return (f"cached {name!r} came from the same location ({was}) but "
                f"has SHA-256 {actual}, not the pinned {expected}. The "
                "payload upstream changed, or the pin was bumped without "
                "the cache being cleared")
    return (f"cached {name!r} has SHA-256 {actual}, but this blueprint "
            f"pins {expected} (recorded provenance: {how})")
