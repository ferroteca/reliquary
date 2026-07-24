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
import zipfile
from urllib.request import urlopen

from . import resolve
from .home import media_cache_dir

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


def _download(url, destination):
    """Stream a URL into destination atomically."""
    os.makedirs(os.path.dirname(destination) or ".", exist_ok=True)
    partial = destination + ".part"
    print(f"downloading {url}", file=sys.stderr)
    with urlopen(url) as response, open(partial, "wb") as handle:
        shutil.copyfileobj(response, handle, _CHUNK)
    os.replace(partial, destination)


def _extract(container_path, member, destination):
    """Extract one zip member to destination atomically."""
    print(f"extracting {member} from {os.path.basename(container_path)}",
          file=sys.stderr)
    os.makedirs(os.path.dirname(destination) or ".", exist_ok=True)
    partial = destination + ".part"
    with zipfile.ZipFile(container_path) as bundle:
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


def _run(plan, name, extension, context, on_mismatch):
    """Produce the file ``plan`` yields, verified, returning its path."""
    if isinstance(plan, resolve.Alternatives):
        errors = []
        for option in plan.options:
            try:
                return _run(option, name, extension, context, on_mismatch)
            except (OSError, RuntimeError) as error:
                errors.append(f"{_describe(option)}: {error}")
        raise RuntimeError(
            f"every location for {name!r} failed:\n  " + "\n  ".join(errors))

    if isinstance(plan, resolve.LocalFile):
        _verify(plan.path, plan.sha256, f"local file for {name!r}")
        return plan.path

    destination = os.path.join(media_cache_dir(context),
                               _cached_name(name, extension))

    if isinstance(plan, resolve.Download):
        if os.path.exists(destination):
            actual = _sha256(destination)
            if plan.sha256 is None or actual == plan.sha256:
                return destination
            _approve_refetch(destination, actual, plan.sha256, on_mismatch)
            os.remove(destination)
        _download(plan.url, destination)
        _verify(destination, plan.sha256, f"downloaded {name!r}")
        return destination

    if isinstance(plan, resolve.Extract):
        if os.path.exists(destination):
            actual = _sha256(destination)
            if plan.sha256 is None or actual == plan.sha256:
                return destination
            _approve_refetch(destination, actual, plan.sha256, on_mismatch)
            os.remove(destination)
        container = _run(plan.inner, plan.parent, _plan_ext(plan.inner),
                         context, on_mismatch)
        _extract(container, plan.member, destination)
        _verify(destination, plan.sha256, f"extracted {name!r}")
        return destination

    raise TypeError(f"unknown plan step: {plan!r}")


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


def fetch_media(media, namespace, context=None, on_mismatch="fail"):
    """Return a media's verified payload path, fetching on demand.

    ``media`` is a :class:`reliquary.document.Media`; ``namespace`` a
    :class:`reliquary.resolve.Namespace`. A blank has no payload and
    returns ``None``. A local payload is used in place; everything else
    caches at ``cache/media/<media-name>.<ext>``.
    """
    if on_mismatch not in _MISMATCH_POLICIES:
        raise ValueError(
            f"on_mismatch must be one of {_MISMATCH_POLICIES}, "
            f"got: {on_mismatch!r}")
    plan = resolve.resolve_media_plan(media, namespace)
    if plan is None:
        return None
    return _run(plan, media.name, _payload_ext(media, plan), context,
                on_mismatch)
