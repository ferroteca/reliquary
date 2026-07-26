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

import contextlib
import hashlib
import os
import sys
import time
import zipfile
from urllib.request import urlopen

from . import events as _events, resolve
from .errors import PreflightError
from .errors import RunCancelled
from .home import media_cache_dir

_CHUNK = 1024 * 1024
_MISMATCH_POLICIES = ("fail", "prompt", "refetch")

# How often a long transfer reports itself. Honest totals only: a
# byte count appears when the source named one, and hashing and
# extraction report elapsed time alone (media-spec "Fetch progress").
_PROGRESS_INTERVAL = 0.5

# Per-operation socket timeout. A mirror that accepts the connection
# and then stalls is a failed location, not a reason to hang forever:
# the timeout surfaces as an OSError, which ``_run`` already treats as
# one location failing so the next alternative is tried.
_SOCKET_TIMEOUT = 30


@contextlib.contextmanager
def _scratch(partial):
    """Discard the scratch file unless the transfer reaches its replace.

    A transfer writes ``<destination>.part`` and renames it only once
    it is whole, so an interrupted one leaves that file behind. There
    is no resume — the next attempt opens it ``"wb"`` and starts over —
    so an abandoned partial is never anything but garbage, and a
    cancelled LiveCD fetch would otherwise strand hundreds of
    megabytes in the cache. The file is this function's own creation,
    and by the time this runs the writing handle is closed.
    """
    try:
        yield
    except BaseException:
        with contextlib.suppress(OSError):
            os.remove(partial)
        raise


def _check_cancelled(cancelled):
    """Abort a host transfer at a chunk boundary when the run stops.

    Cancellation reaches the transfer loops as the run engine's own
    ``threading.Event``, threaded from the caller — a fetch outside a
    run passes ``None`` and is simply uninterruptible. The check sits
    at every chunk boundary because that is the severability the
    execution model promises: input deliveries are atomic, *host
    transfers abort* (planning/ROADMAP.md, "Cancel ends the run, not
    the machine"). Without it a Ctrl-C during a large fetch is not
    seen until the whole statement finishes, which can be minutes.
    """
    if cancelled is not None and cancelled.is_set():
        raise RunCancelled(
            "the run was cancelled during a host transfer")


def _sha256(path, cancelled=None):
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
    """Why a cached file is not the one this blueprint means.

    Two causes look identical to a hash comparison and want different
    fixes — the payload upstream changed, or two projects share one
    media name across a common cache — so the message names both and
    the flag that separates them.
    """
    return (f"cached {name!r} has SHA-256 {actual}, but this blueprint "
            f"pins {expected}"
            + (f" for {source}" if source else "")
            + ".\nEither the payload changed upstream, or another "
            "project caches a different media under this name — "
            "isolate them with --cache")


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
                # Copied a chunk at a time rather than with copyfileobj
                # so decompressing a large member stays severable.
                while True:
                    _check_cancelled(cancelled)
                    chunk = source.read(_CHUNK)
                    if not chunk:
                        break
                    handle.write(chunk)
    os.replace(partial, destination)
    if events is not None:
        # Extraction reports elapsed time only: a compressed member
        # has no honest running total to show against.
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
    actual = _sha256(path, cancelled)
    if actual != expected:
        raise RuntimeError(
            f"{describe} at {path} has SHA-256 {actual}, expected {expected}")
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
            # A cancellation is not a failed location: RunCancelled sits
            # outside the classes caught here, so it leaves the mirror
            # loop rather than sending the fetch to the next alternative.
            try:
                return _run(option, name, extension, context, on_mismatch,
                            events, cancelled)
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
        # A local payload is used in place, so it has to still be
        # there. Checked before verifying: an absent file is a
        # different problem from a wrong one, and saying so here keeps
        # it from reaching the backend as a failure to open a path.
        # (A directory source is legal — vvfat — so this is `exists`.)
        if not os.path.exists(plan.path):
            raise PreflightError(
                f"media {name!r} is declared at {plan.path}, but nothing "
                "is there.\nRestore the file, or edit the blueprint that "
                "declares it to name where it lives now")
        _verify(plan.path, plan.sha256, f"local file for {name!r}",
                name, events, cancelled)
        return plan.path

    destination = os.path.join(media_cache_dir(context),
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

    raise TypeError(f"unknown plan step: {plan!r}")


def _cache_hit(destination, name, expected, on_mismatch, source, context,
               cancelled=None):
    """Whether the cached file is already the one wanted.

    The preflight identity check: it runs before any network or
    extraction work, so a pinned media that is already cached costs one
    hash and nothing else.
    """
    if not os.path.exists(destination):
        return False
    actual = _sha256(destination, cancelled)
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


def fetch_media(media, namespace, context=None, on_mismatch="fail",
                properties=None, events=None, cancelled=None):
    """Return a media's verified payload path, fetching on demand.

    ``media`` is a :class:`reliquary.document.Media`; ``namespace`` a
    :class:`reliquary.resolve.Namespace`. A blank has no payload and
    returns ``None``. A local payload is used in place; everything else
    caches at ``cache/media/<media-name>.<ext>``. ``properties`` binds
    any ``${key}`` in the media's location (milestone 8, T5).

    ``cancelled`` is the run engine's ``threading.Event``, checked at
    every transfer chunk so a cancelled run stops mid-fetch instead of
    at the end of the statement; ``None`` (a fetch outside a run)
    leaves the transfer uninterruptible, as before.
    """
    if on_mismatch not in _MISMATCH_POLICIES:
        raise ValueError(
            f"on_mismatch must be one of {_MISMATCH_POLICIES}, "
            f"got: {on_mismatch!r}")
    plan = resolve.resolve_media_plan(media, namespace, properties)
    if plan is None:
        return None
    return _run(plan, media.name, _payload_ext(media, plan), context,
                on_mismatch, events, cancelled)
