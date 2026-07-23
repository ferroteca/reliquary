# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Execute a resolved fetch plan into the payload and archive caches.

A media's :func:`reliquary.resolve.resolve_media_plan` yields a nested
plan of :class:`~reliquary.resolve.Download` / ``LocalFile`` / ``Extract``
steps; this module runs it, caching each archive under ``cache/archives/``
by its component name and the final payload under ``cache/media/`` by the
media's name, SHA-256-verifying every file. ``local`` sources attach in
place (never cached). Design: planning/design/blueprint-model.md.
"""

import hashlib
import os
import shutil
import sys
import zipfile
from urllib.request import urlopen

from . import resolve
from .home import archives_cache_dir, media_cache_dir

_CHUNK = 1024 * 1024
_MISMATCH_POLICIES = ("fail", "prompt", "refetch")


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


def _approve_refetch(path, actual, expected, on_mismatch):
    """Gate deleting an existing cached file that fails verification."""
    if on_mismatch == "refetch":
        print(f"existing file {path} does not match its defined hash; "
              "deleting for refetch", file=sys.stderr)
        return
    if on_mismatch == "prompt":
        try:
            answer = input(
                f"Existing file {path} does not match its defined hash "
                f"(SHA-256 {actual}, expected {expected}). Delete it and "
                f"fetch again? [y/N] ")
        except EOFError:
            answer = ""
        if answer.strip().lower() in ("y", "yes"):
            return
    raise RuntimeError(
        f"existing file {path} has SHA-256 {actual}, expected {expected}; "
        "delete it, or pre-approve with on_mismatch='refetch'")


def _download(urls, destination):
    """Stream the first working mirror into destination atomically."""
    os.makedirs(os.path.dirname(destination) or ".", exist_ok=True)
    partial = destination + ".part"
    errors = []
    for url in urls:
        try:
            print(f"downloading {url}", file=sys.stderr)
            with urlopen(url) as response, open(partial, "wb") as handle:
                shutil.copyfileobj(response, handle, _CHUNK)
            os.replace(partial, destination)
            return
        except OSError as error:  # try the next mirror
            errors.append(f"{url}: {error}")
    raise RuntimeError(
        "all mirrors failed:\n  " + "\n  ".join(errors))


def _extract(archive_path, member, destination):
    """Extract one zip member to destination atomically."""
    print(f"extracting {member} from {os.path.basename(archive_path)}",
          file=sys.stderr)
    os.makedirs(os.path.dirname(destination) or ".", exist_ok=True)
    partial = destination + ".part"
    with zipfile.ZipFile(archive_path) as bundle:
        with bundle.open(member) as source, open(partial, "wb") as handle:
            shutil.copyfileobj(source, handle, _CHUNK)
    os.replace(partial, destination)


def _verify(path, expected, describe):
    if expected is None:
        return
    actual = _sha256(path)
    if actual != expected:
        raise RuntimeError(
            f"{describe} at {path} has SHA-256 {actual}, expected {expected}")


def _run(plan, name, extension, expected_sha, cache_dir, context, on_mismatch):
    """Produce the file ``plan`` yields, verified, returning its path."""
    if isinstance(plan, resolve.LocalFile):
        sha = expected_sha or plan.sha256
        _verify(plan.path, sha, f"local file for {name!r}")
        return plan.path

    destination = os.path.join(cache_dir, _cached_name(name, extension))

    if isinstance(plan, resolve.Download):
        sha = expected_sha or plan.sha256
        if sha is None:
            raise RuntimeError(
                f"a url source ({name!r}) must carry a sha256")
        if os.path.exists(destination):
            actual = _sha256(destination)
            if actual == sha:
                return destination
            _approve_refetch(destination, actual, sha, on_mismatch)
            os.remove(destination)
        _download(plan.urls, destination)
        _verify(destination, sha, f"downloaded {name!r}")
        return destination

    if isinstance(plan, resolve.Extract):
        sha = expected_sha
        if os.path.exists(destination):
            actual = _sha256(destination)
            if sha is None or actual == sha:
                return destination
            _approve_refetch(destination, actual, sha, on_mismatch)
            os.remove(destination)
        archive_path = _run(
            plan.inner, plan.archive, _archive_ext(plan.inner), plan.sha256,
            archives_cache_dir(context), context, on_mismatch)
        _extract(archive_path, plan.member, destination)
        _verify(destination, sha, f"extracted {name!r}")
        return destination

    raise TypeError(f"unknown plan step: {plan!r}")


def _archive_ext(plan):
    """The extension of the archive file ``plan`` produces."""
    if isinstance(plan, resolve.Download):
        return _ext(plan.urls[0])
    if isinstance(plan, resolve.LocalFile):
        return _ext(plan.path)
    if isinstance(plan, resolve.Extract):
        return _ext(plan.member)
    return ""


def _payload_ext(media, plan):
    if media.extension:
        return media.extension
    if isinstance(plan, resolve.Extract):
        return _ext(plan.member)
    if isinstance(plan, resolve.Download):
        return _ext(plan.urls[0])
    if isinstance(plan, resolve.LocalFile):
        return _ext(plan.path)
    return ""


def fetch_media(media, namespace, context=None, on_mismatch="fail"):
    """Return a media's verified payload path, fetching on demand.

    ``media`` is a :class:`reliquary.document.Media`; ``namespace`` a
    :class:`reliquary.resolve.Namespace`. A ``new`` media has no payload
    and returns ``None``. A ``local`` source is used in place; otherwise
    the payload is cached at ``cache/media/<media-name>.<ext>``.
    """
    if on_mismatch not in _MISMATCH_POLICIES:
        raise ValueError(
            f"on_mismatch must be one of {_MISMATCH_POLICIES}, "
            f"got: {on_mismatch!r}")
    plan = resolve.resolve_media_plan(media, namespace)
    if plan is None:
        return None
    return _run(plan, media.name, _payload_ext(media, plan), media.sha256,
                media_cache_dir(context), context, on_mismatch)
