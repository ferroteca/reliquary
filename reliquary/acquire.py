# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Execute a resolved fetch plan into the media cache.

A media's :func:`reliquary.resolve.resolve_media_plan` yields a nested
plan of :class:`~reliquary.resolve.Download` / ``LocalFile`` /
``Extract`` / ``Alternatives`` steps; this module runs it,
SHA-256-verifying every file.

Every cached file is keyed by the **name of the media it is**, in the
one ``cache/media/`` directory — a container is a media like any other
now, so there is no second cache for it. ``local`` payloads attach in
place and are never copied in.

Design: planning/design/blueprint-model.md ("The cache").
"""

import hashlib
import os
import shutil
import sys
import time
import zipfile
from urllib.request import urlopen

from . import events as _events, ledger, resolve
from .home import media_cache_dir

_CHUNK = 1024 * 1024
_MISMATCH_POLICIES = ("fail", "prompt", "refetch")

# How often a long transfer reports itself. Honest totals only: a
# byte count appears when the source named one, and hashing and
# extraction report elapsed time alone (media-spec "Fetch progress").
_PROGRESS_INTERVAL = 0.5


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ext(filename):
    return os.path.splitext(os.path.basename(filename))[1].lstrip(".")


def _cached_name(name, extension):
    return name + ("." + extension if extension else "")


def _approve_refetch(name, actual, expected, on_mismatch, source, context):
    """Gate deleting an existing cached file that fails verification.

    The ledger supplies the diagnosis: a bare hash comparison cannot
    tell a version bump from two projects sharing one media name, and
    those want different fixes. A ``supplied`` payload is never
    deleted on a policy — nothing could put it back.
    """
    explanation = ledger.explain(name, expected, actual, source=source,
                                 context=context)
    if ledger.provenance(name, context) == ledger.SUPPLIED:
        raise RuntimeError(explanation)
    if on_mismatch == "refetch":
        print(explanation + "\ndeleting for refetch", file=sys.stderr)
        return
    if on_mismatch == "prompt":
        try:
            answer = input(
                explanation + "\nDelete it and fetch again? [y/N] ")
        except EOFError:
            answer = ""
        if answer.strip().lower() in ("y", "yes"):
            return
    raise RuntimeError(
        explanation
        + "\ndelete it, or pre-approve with on_mismatch='refetch'")


def _content_length(response):
    """The byte total the source named, or ``None`` when it named none."""
    try:
        length = int(response.headers.get("Content-Length"))
    except (AttributeError, TypeError, ValueError):
        return None
    return length if length > 0 else None


def _download(url, destination, name, events):
    """Stream a URL into destination atomically, reporting progress."""
    os.makedirs(os.path.dirname(destination) or ".", exist_ok=True)
    partial = destination + ".part"
    _events.note(events, _events.TRANSFER_START, f"downloading {url}",
                 name=name, source=url, operation="download")
    started = time.monotonic()
    moved = 0
    with urlopen(url) as response, open(partial, "wb") as handle:
        total = _content_length(response)
        last = started
        while True:
            chunk = response.read(_CHUNK)
            if not chunk:
                break
            handle.write(chunk)
            moved += len(chunk)
            now = time.monotonic()
            if events is not None and now - last >= _PROGRESS_INTERVAL:
                last = now
                events.emit(_events.TRANSFER_PROGRESS, name=name,
                            transferred=moved, total=total)
    os.replace(partial, destination)
    if events is not None:
        events.emit(_events.TRANSFER_END, name=name, source=url,
                    operation="download", transferred=moved,
                    elapsed=round(time.monotonic() - started, 3))


def _extract(container_path, member, destination, name, events):
    """Extract one zip member to destination atomically."""
    container = os.path.basename(container_path)
    _events.note(events, _events.TRANSFER_START,
                 f"extracting {member} from {container}",
                 name=name, source=f"{container}/{member}",
                 operation="extract")
    started = time.monotonic()
    os.makedirs(os.path.dirname(destination) or ".", exist_ok=True)
    partial = destination + ".part"
    with zipfile.ZipFile(container_path) as bundle:
        with bundle.open(member) as source, open(partial, "wb") as handle:
            shutil.copyfileobj(source, handle, _CHUNK)
    os.replace(partial, destination)
    if events is not None:
        # Extraction reports elapsed time only: a compressed member
        # has no honest running total to show against.
        events.emit(_events.TRANSFER_END, name=name, operation="extract",
                    source=f"{container}/{member}",
                    elapsed=round(time.monotonic() - started, 3))


def _verify(path, expected, describe, name=None, events=None):
    if expected is None:
        return
    _events.note(events, _events.VERIFY_START, f"verifying {describe}",
                 name=name or describe, algorithm="sha256")
    started = time.monotonic()
    actual = _sha256(path)
    if actual != expected:
        raise RuntimeError(
            f"{describe} at {path} has SHA-256 {actual}, expected {expected}")
    if events is not None:
        events.emit(_events.VERIFY_END, name=name or describe,
                    algorithm="sha256",
                    elapsed=round(time.monotonic() - started, 3))


def _run(plan, name, extension, context, on_mismatch, events=None):
    """Produce the file ``plan`` yields, verified, returning its path."""
    if isinstance(plan, resolve.Alternatives):
        errors = []
        for option in plan.options:
            try:
                return _run(option, name, extension, context, on_mismatch,
                            events)
            except (OSError, RuntimeError) as error:
                # Each mirror attempt is its own event: a fallback that
                # succeeded should not hide the one that did not.
                errors.append(f"{_describe(option)}: {error}")
                if events is not None:
                    events.emit(_events.TRANSFER_END, name=name,
                                source=_describe(option),
                                operation="attempt", error=str(error))
        raise RuntimeError(
            f"every location for {name!r} failed:\n  " + "\n  ".join(errors))

    if isinstance(plan, resolve.LocalFile):
        _verify(plan.path, plan.sha256, f"local file for {name!r}",
                name, events)
        return plan.path

    destination = os.path.join(media_cache_dir(context),
                               _cached_name(name, extension))

    if isinstance(plan, resolve.Download):
        if _cache_hit(destination, name, plan.sha256, on_mismatch,
                      plan.url, context):
            return destination
        _download(plan.url, destination, name, events)
        _verify(destination, plan.sha256, f"downloaded {name!r}", name,
                events)
        ledger.record(name, filename=os.path.basename(destination),
                      sha256=plan.sha256 or _sha256(destination),
                      provenance=ledger.REFETCHABLE, source=plan.url,
                      context=context)
        return destination

    if isinstance(plan, resolve.Extract):
        if _cache_hit(destination, name, plan.sha256, on_mismatch,
                      f"{plan.parent}/{plan.member}", context):
            return destination
        container = _run(plan.inner, plan.parent, _plan_ext(plan.inner),
                         context, on_mismatch, events)
        _extract(container, plan.member, destination, name, events)
        _verify(destination, plan.sha256, f"extracted {name!r}", name,
                events)
        ledger.record(
            name, filename=os.path.basename(destination),
            sha256=plan.sha256 or _sha256(destination),
            provenance=ledger.DERIVED,
            source=f"{plan.parent}/{plan.member}",
            derivation={"parent": plan.parent, "path": plan.member,
                        "parent-sha": _sha256(container)},
            context=context)
        return destination

    raise TypeError(f"unknown plan step: {plan!r}")


def _cache_hit(destination, name, expected, on_mismatch, source, context):
    """Whether the cached file is already the one wanted.

    This is the deterministic preflight identity check: it runs before
    any network or extraction work, and a mismatch is explained from the
    ledger rather than merely reported.
    """
    if not os.path.exists(destination):
        return False
    actual = _sha256(destination)
    if expected is None or actual == expected:
        return True
    _approve_refetch(name, actual, expected, on_mismatch, source, context)
    os.remove(destination)
    ledger.forget(name, context)
    return False


def _describe(plan):
    if isinstance(plan, resolve.Download):
        return plan.url
    if isinstance(plan, resolve.LocalFile):
        return plan.path
    if isinstance(plan, resolve.Extract):
        return f"{plan.parent}/{plan.member}"
    return type(plan).__name__


def _plan_ext(plan):
    """The extension of the file ``plan`` produces."""
    if isinstance(plan, resolve.Download):
        return _ext(plan.url.split("#", 1)[0].split("?", 1)[0])
    if isinstance(plan, resolve.LocalFile):
        return _ext(plan.path)
    if isinstance(plan, resolve.Extract):
        return _ext(plan.member)
    if isinstance(plan, resolve.Alternatives):
        return _plan_ext(plan.options[0])
    return ""


def _payload_ext(media, plan):
    return media.extension or _plan_ext(plan)


def fetch_media(media, namespace, context=None, on_mismatch="fail",
                properties=None, events=None):
    """Return a media's verified payload path, fetching on demand.

    ``media`` is a :class:`reliquary.document.Media`; ``namespace`` a
    :class:`reliquary.resolve.Namespace`. A blank has no payload and
    returns ``None``. A local payload is used in place; everything else
    caches at ``cache/media/<media-name>.<ext>``. ``properties`` binds
    any ``${key}`` in the media's location (milestone 8, T5).
    """
    if on_mismatch not in _MISMATCH_POLICIES:
        raise ValueError(
            f"on_mismatch must be one of {_MISMATCH_POLICIES}, "
            f"got: {on_mismatch!r}")
    plan = resolve.resolve_media_plan(media, namespace, properties)
    if plan is None:
        return None
    return _run(plan, media.name, _payload_ext(media, plan), context,
                on_mismatch, events)
