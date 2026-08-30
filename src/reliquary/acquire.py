# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Execute a resolved fetch plan into the media cache.

:func:`reliquary.resolve.resolve_media_plan` returns a plan built
from :class:`~reliquary.resolve.Download` / ``LocalFile`` /
``Extract`` / ``Alternatives`` steps, possibly nested. This module
runs that plan, checking every resulting file's SHA-256.

Every cached file is stored under the name of the media it
represents, in one ``cache/media/`` directory — a container (like a
zip a media is extracted from) is just a media like any other, so it
doesn't get a separate cache. A ``local`` payload is used from where
it already sits on disk and is never copied into the cache.

Design: docs/spec/blueprint-model.md ("The cache").
"""

import contextlib
import hashlib
import os
import sys
import time
import zipfile
from urllib.request import urlopen

from . import events as _events, resolve
from .errors import (InternalError, PreflightError, RunCancelled,
                     RunFailure, StaticError)
from .home import media_dir

_CHUNK = 1024 * 1024
_MISMATCH_POLICIES = ("fail", "prompt", "refetch")

# How often (in seconds) a long transfer reports its progress. Byte
# totals are only reported when the source actually gave one; hashing
# and extraction only report elapsed time, since neither has a
# trustworthy total to show (media-spec "Fetch progress").
_PROGRESS_INTERVAL = 0.5

# Socket timeout for one network operation. If a mirror accepts the
# connection and then stalls, that counts as a failed location rather
# than something to wait on forever: the timeout raises an OSError,
# and `_run` already treats an OSError as one location failing, so it
# moves on to try the next mirror.
_SOCKET_TIMEOUT = 30


@contextlib.contextmanager
def _scratch(partial):
    """Delete the ``.part`` scratch file if the transfer doesn't finish.

    A transfer writes to ``<destination>.part`` and only renames it to
    the real destination once the whole file has arrived. If the
    transfer is interrupted, that ``.part`` file is left behind.
    There's no resume support — the next attempt just opens it with
    ``"wb"`` and starts over — so a leftover partial file is useless.
    Without this cleanup, a cancelled LiveCD fetch could leave
    hundreds of megabytes of a half-downloaded file sitting in the
    cache forever. By the time this cleanup runs, the file's write
    handle is already closed.
    """
    try:
        yield
    except BaseException:
        with contextlib.suppress(OSError):
            os.remove(partial)
        raise


def _check_cancelled(cancelled):
    """Stop a host transfer at a chunk boundary if the run was cancelled.

    ``cancelled`` is the run engine's own ``threading.Event``, passed
    down from the caller — a fetch running outside of a run passes
    ``None`` and simply can't be interrupted. This check runs at every
    chunk boundary because that's the granularity the execution model
    promises: input deliveries finish completely once started, but a
    host transfer can be aborted partway through (docs/spec/cli.md,
    "Cancel ends the run, not the machine"). Without this check,
    pressing Ctrl-C during a large download wouldn't take effect until
    the whole statement finished, which could be minutes later.
    """
    if cancelled is not None and cancelled.is_set():
        raise RunCancelled(
            "the run was cancelled during a host transfer")


def sha256(path, cancelled=None):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            _check_cancelled(cancelled)
            digest.update(chunk)
    return digest.hexdigest()


def _ext(filename):
    return os.path.splitext(os.path.basename(filename))[1].lstrip(".")


def _cached_name(name, extension):
    return name + ("." + extension if extension else "")


def _explain_mismatch(name, expected, actual, source):
    """Explain why a cached file's hash doesn't match what the blueprint expects.

    A hash mismatch has two possible causes that look identical from
    the hash alone: the upstream file changed, or two different
    projects happen to use the same media name in a cache they share.
    The message names both possibilities, and the flag that lets the
    user resolve either one.
    """
    return (f"cached {name!r} has SHA-256 {actual}, but this blueprint "
            f"pins {expected}"
            + (f" for {source}" if source else "")
            + ".\nEither the payload changed upstream, or another "
            "project caches a different media under this name — "
            "isolate them with --media-dir")


def _approve_refetch(name, actual, expected, on_mismatch, source, context):
    """Gate deleting an existing cached file that fails verification."""
    del context
    explanation = _explain_mismatch(name, expected, actual, source)
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
    raise RunFailure(
        explanation
        + "\ndelete it, or pre-approve with on_mismatch='refetch'",
        rule_id="media.hash-mismatch")


def _content_length(response):
    """The byte total the source named, or ``None`` when it named none."""
    try:
        length = int(response.headers.get("Content-Length"))
    except (AttributeError, TypeError, ValueError):
        return None
    return length if length > 0 else None


def _download(url, destination, name, events, cancelled=None):
    """Stream a URL into destination atomically, reporting progress."""
    os.makedirs(os.path.dirname(destination) or ".", exist_ok=True)
    partial = destination + ".part"
    _events.note(events, _events.TRANSFER_START, f"downloading {url}",
                 name=name, source=url, operation="download")
    started = time.monotonic()
    moved = 0
    with _scratch(partial):
        with urlopen(url, timeout=_SOCKET_TIMEOUT) as response, \
                open(partial, "wb") as handle:
            total = _content_length(response)
            last = started
            while True:
                _check_cancelled(cancelled)
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


def _extract(container_path, member, destination, name, events,
             cancelled=None):
    """Extract one zip member to destination atomically."""
    container = os.path.basename(container_path)
    _events.note(events, _events.TRANSFER_START,
                 f"extracting {member} from {container}",
                 name=name, source=f"{container}/{member}",
                 operation="extract")
    started = time.monotonic()
    os.makedirs(os.path.dirname(destination) or ".", exist_ok=True)
    partial = destination + ".part"
    with _scratch(partial):
        with zipfile.ZipFile(container_path) as bundle:
            with bundle.open(member) as source, \
                    open(partial, "wb") as handle:
                # Copied a chunk at a time instead of with
                # copyfileobj, so a cancellation check can run between
                # chunks while decompressing a large member.
                while True:
                    _check_cancelled(cancelled)
                    chunk = source.read(_CHUNK)
                    if not chunk:
                        break
                    handle.write(chunk)
    os.replace(partial, destination)
    if events is not None:
        # Only elapsed time is reported for extraction — a compressed
        # member has no reliable byte total to show progress against.
        events.emit(_events.TRANSFER_END, name=name, operation="extract",
                    source=f"{container}/{member}",
                    elapsed=round(time.monotonic() - started, 3))


def _verify(path, expected, describe, name=None, events=None,
            cancelled=None):
    if expected is None:
        return
    _events.note(events, _events.VERIFY_START, f"verifying {describe}",
                 name=name or describe, algorithm="sha256")
    started = time.monotonic()
    actual = sha256(path, cancelled)
    if actual != expected:
        raise RunFailure(
            f"{describe} at {path} has SHA-256 {actual}, expected {expected}",
            rule_id="media.hash-mismatch")
    if events is not None:
        events.emit(_events.VERIFY_END, name=name or describe,
                    algorithm="sha256",
                    elapsed=round(time.monotonic() - started, 3))


def _run(plan, name, extension, context, on_mismatch, events=None,
         cancelled=None):
    """Produce the file ``plan`` yields, verified, returning its path."""
    if isinstance(plan, resolve.Alternatives):
        errors = []
        for option in plan.options:
            # RunCancelled isn't one of the exceptions caught below,
            # so a cancellation propagates straight out of this loop
            # instead of being treated as "this mirror failed, try the
            # next one".
            try:
                return _run(option, name, extension, context, on_mismatch,
                            events, cancelled)
            except (OSError, RunFailure) as error:
                # Record each failed mirror attempt as its own event,
                # so a fallback that succeeds doesn't hide the earlier
                # failure that made it necessary.
                errors.append(f"{_describe(option)}: {error}")
                if events is not None:
                    events.emit(_events.TRANSFER_END, name=name,
                                source=_describe(option),
                                operation="attempt", error=str(error))
        raise RunFailure(
            f"every location for {name!r} failed:\n  " + "\n  ".join(errors),
            rule_id="media.all-locations-failed")

    if isinstance(plan, resolve.LocalFile):
        # A local payload is used in place, so it needs to actually be
        # there. This check runs before verifying the hash: a missing
        # file is a different problem from a wrong one, and catching
        # it here gives a clear error instead of letting the backend
        # fail trying to open a path that doesn't exist.
        # (A directory is a legal source here — a share's payload,
        # F68 — so this checks `exists`, not `isfile`.)
        if not os.path.exists(plan.path):
            raise PreflightError(
                f"media {name!r} is declared at {plan.path}, but nothing "
                "is there.\nRestore the file, or edit the blueprint that "
                "declares it to name where it lives now",
                rule_id="media.file-missing")
        _verify(plan.path, plan.sha256, f"local file for {name!r}",
                name, events, cancelled)
        return plan.path

    destination = os.path.join(media_dir(context),
                               _cached_name(name, extension))

    if isinstance(plan, resolve.Download):
        if _cache_hit(destination, name, plan.sha256, on_mismatch,
                      plan.url, context, cancelled):
            return destination
        _download(plan.url, destination, name, events, cancelled)
        _verify(destination, plan.sha256, f"downloaded {name!r}", name,
                events, cancelled)
        return destination

    if isinstance(plan, resolve.Extract):
        if _cache_hit(destination, name, plan.sha256, on_mismatch,
                      f"{plan.parent}/{plan.member}", context, cancelled):
            return destination
        container = _run(plan.inner, plan.parent, _plan_ext(plan.inner),
                         context, on_mismatch, events, cancelled)
        _extract(container, plan.member, destination, name, events,
                 cancelled)
        _verify(destination, plan.sha256, f"extracted {name!r}", name,
                events, cancelled)
        return destination

    raise InternalError(f"unknown plan step: {plan!r}")


def _cache_hit(destination, name, expected, on_mismatch, source, context,
               cancelled=None):
    """Whether the cached file is already the one wanted.

    This check runs before any network or extraction work, so a media
    that's pinned by hash and already cached only costs computing one
    hash — nothing else.
    """
    if not os.path.exists(destination):
        return False
    actual = sha256(destination, cancelled)
    if expected is None or actual == expected:
        return True
    _approve_refetch(name, actual, expected, on_mismatch, source, context)
    os.remove(destination)
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


def payload_extension(media, plan):
    """The extension the cached payload of ``media`` carries."""
    return _payload_ext(media, plan)


def residency(plan, name, extension, context=None):
    """Report what running ``plan`` would do, without actually doing any of it.

    This is the dry-run counterpart of :func:`_run`. It lives in this
    module because only this module knows the cache's file layout, so
    only it can say whether a given payload is already there. Every
    step the plan would cache becomes one entry in the result,
    outermost step first. Each entry is a dict with ``name`` /
    ``state`` / ``source`` / ``path`` (plus ``sha256`` / ``size`` /
    ``mirrors`` when they're known). The possible states:

    ``cached``
        the cache already holds this payload
    ``would-download``
        it doesn't, and a URL would supply it
    ``would-extract``
        it doesn't, and it comes out of a container — the container's
        own entry follows this one, since the container is only
        fetched if the extracted file turns out to be missing (this
        is also what ``prune`` uses to reclaim space)
    ``local-present`` / ``local-missing``
        a host path outside the cache, used from where it sits

    Nothing gets hashed here. ``cached`` only means the file exists at
    that path, not that it's the correct one — hashing a large file
    like a LiveCD isn't free, so this function doesn't do it. Checking
    whether an already-cached file is actually correct is what a
    future ``--dry-run=verify`` would add.
    """
    entries = []
    _residency(plan, name, extension, context, entries)
    return tuple(entries)


def _residency(plan, name, extension, context, entries):
    if isinstance(plan, resolve.Alternatives):
        _residency(plan.options[0], name, extension, context, entries)
        if len(plan.options) > 1:
            entries[-1]["mirrors"] = len(plan.options)
        return

    if isinstance(plan, resolve.LocalFile):
        # A local payload is used from where it sits and never enters
        # the cache, so all there is to report is whether it's still
        # there — the same check `_run` makes before verifying it.
        present = os.path.exists(plan.path)
        entry = {
            "name": name,
            "state": "local-present" if present else "local-missing",
            "source": plan.path,
            "path": plan.path,
            "sha256": plan.sha256,
        }
        if present and os.path.isfile(plan.path):
            entry["size"] = os.path.getsize(plan.path)
        entries.append(entry)
        return

    destination = os.path.join(media_dir(context),
                               _cached_name(name, extension))
    cached = os.path.exists(destination)
    entry = {"name": name, "path": destination, "sha256": plan.sha256}
    if isinstance(plan, resolve.Download):
        entry["source"] = plan.url
        entry["state"] = "cached" if cached else "would-download"
    elif isinstance(plan, resolve.Extract):
        entry["source"] = f"{plan.parent}/{plan.member}"
        entry["state"] = "cached" if cached else "would-extract"
    else:
        raise InternalError(f"unknown plan step: {plan!r}")
    if cached:
        entry["size"] = os.path.getsize(destination)
    entries.append(entry)
    if isinstance(plan, resolve.Extract) and not cached:
        _residency(plan.inner, plan.parent, _plan_ext(plan.inner),
                   context, entries)


def fetch_media(media, namespace, context=None, on_mismatch="fail",
                properties=None, events=None, cancelled=None):
    """Return a media's verified payload path, fetching on demand.

    ``media`` is a :class:`reliquary.document.Media`; ``namespace`` a
    :class:`reliquary.resolve.Namespace`. A blank media has no
    payload and this returns ``None``. A local payload is used from
    where it sits; everything else is cached at
    ``cache/media/<media-name>.<ext>``. ``properties`` supplies the
    values for any ``${key}`` reference in the media's location
    (milestone 8, T5).

    ``cancelled`` is the run engine's ``threading.Event``. It's
    checked at every transfer chunk, so a cancelled run stops
    mid-fetch instead of only at the end of the current statement.
    Pass ``None`` (for a fetch outside of a run) to leave the transfer
    uninterruptible, as it always was before cancellation support
    existed.
    """
    if on_mismatch not in _MISMATCH_POLICIES:
        raise StaticError(
            f"on_mismatch must be one of {_MISMATCH_POLICIES}, "
            f"got: {on_mismatch!r}", rule_id="value.not-in-vocabulary")
    plan = resolve.resolve_media_plan(media, namespace, properties)
    if plan is None:
        return None
    return _run(plan, media.name, _payload_ext(media, plan), context,
                on_mismatch, events, cancelled)
