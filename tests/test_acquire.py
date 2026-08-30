# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for fetch-plan acquisition (acquire.py), offline."""

import hashlib
import os
import threading
import zipfile
from unittest import mock

import pytest

from reliquary import acquire, resolve
from reliquary.document import parse_document
from reliquary.errors import PreflightError, RunCancelled
from reliquary.home import Context, media_dir


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _read(path):
    with open(path, "rb") as handle:
        return handle.read()


@pytest.fixture
def root(tmp_path):
    return str(tmp_path)


# Fetching a plan, offline.

def test_nested_local_archive_extraction(root):
    payload = b"PAYLOAD-BYTES-" * 1000
    payload_sha = _sha(payload)

    inner_zip = os.path.join(root, "inner.zip")
    with zipfile.ZipFile(inner_zip, "w") as bundle:
        bundle.writestr("144m/payload.img", payload)
    inner_sha = _sha(_read(inner_zip))

    outer_zip = os.path.join(root, "outer.zip")
    with zipfile.ZipFile(outer_zip, "w") as bundle:
        bundle.writestr("inner.zip", _read(inner_zip))
    outer_sha = _sha(_read(outer_zip))

    doc = parse_document([{
        "name": "outer",
        "location": {"local": outer_zip}, "sha256": outer_sha,
        "children": [{
            "path": "inner.zip", "sha256": inner_sha,
            "children": [{"path": "144m/payload.img",
                          "name": "payload",
                          "sha256": payload_sha}]}]}])
    ns = resolve.namespace_of(doc)
    cache = os.path.join(root, "cache")
    context = Context(cache_dir=cache)

    path = acquire.fetch_media(ns.media["payload"], ns, context=context)
    assert _read(path) == payload
    assert os.path.basename(path) == "payload.img"
    assert os.path.exists(os.path.join(cache, "media", "payload.img"))
    # The container is a media like any other now: one cache,
    # keyed by name, with no second directory for archives.
    assert os.path.exists(os.path.join(cache, "media", "inner.zip"))

    # Fetching the same media again checks the cache and reuses it,
    # instead of downloading it a second time.
    assert acquire.fetch_media(ns.media["payload"], ns,
                               context=context) == path


def test_new_media_returns_none():
    doc = parse_document([{"name": "blank", "materialize": "new",
                           "size": "1M"}])
    ns = resolve.namespace_of(doc)
    assert acquire.fetch_media(ns.media["blank"], ns,
                               context=Context(cache_dir=".")) is None


def test_local_use_media_attaches_in_place(root):
    iso = os.path.join(root, "win98se.iso")
    with open(iso, "wb") as handle:
        handle.write(b"ISO-CONTENT")
    doc = parse_document([{"name": "win", "location": {"local": iso}}])
    ns = resolve.namespace_of(doc)
    path = acquire.fetch_media(
        ns.media["win"], ns,
        context=Context(cache_dir=os.path.join(root, "c")))
    assert path == iso  # used in place, not copied to cache


def test_a_missing_local_payload_names_the_media_and_the_path(root):
    """The missing file must be caught here, not surface later as a
    generic "failed to open path" error from the backend."""
    gone = os.path.join(root, "moved-away.iso")
    doc = parse_document([{"name": "win98-cd", "location": {"local": gone},
                           "sha256": "a" * 64}])
    ns = resolve.namespace_of(doc)
    with pytest.raises(PreflightError) as caught:
        acquire.fetch_media(ns.media["win98-cd"], ns,
                            context=Context(cache_dir=root))
    message = str(caught.value)
    assert "win98-cd" in message
    assert gone in message


def test_a_missing_local_payload_is_caught_without_a_pin(root):
    """Without a sha256 pin, the missing path would otherwise be
    passed straight through unchecked."""
    gone = os.path.join(root, "moved-away.img")
    doc = parse_document([{"name": "floppy", "location": {"local": gone}}])
    ns = resolve.namespace_of(doc)
    with pytest.raises(PreflightError):
        acquire.fetch_media(ns.media["floppy"], ns,
                            context=Context(cache_dir=root))


def test_a_directory_source_is_not_treated_as_missing(root):
    """A directory location is legal media content at this layer —
    whether it's legal to *attach* (share only, F68) is decided where
    the device that names it materializes, not here."""
    staging = os.path.join(root, "staging")
    os.makedirs(staging)
    doc = parse_document([{"name": "exchange",
                           "location": {"local": staging}}])
    ns = resolve.namespace_of(doc)
    assert acquire.fetch_media(ns.media["exchange"], ns,
                               context=Context(cache_dir=root)) == staging


def test_remote_without_hash_fails_before_network():
    # A remote location with no sha256 still parses fine. The
    # required-once-remote rule is checked later, during resolution,
    # because a referenced rung might resolve to a URL that parsing
    # alone can't see. Resolution refuses it before any download
    # starts, so this test never touches the network.
    doc = parse_document([{"name": "x",
                           "location": {"url": "https://example/a.iso"}}])
    ns = resolve.namespace_of(doc)
    with pytest.raises(PreflightError):
        acquire.fetch_media(ns.media["x"], ns,
                            context=Context(cache_dir="."))


def test_extraction_caches_the_child_and_not_a_local_container(root):
    """The derived payload is cached under its own name.

    A local container is used in place, never copied in — so the
    cache holds exactly the media that had to be produced.
    """
    payload = b"PAYLOAD"
    container = os.path.join(root, "outer.zip")
    with zipfile.ZipFile(container, "w") as bundle:
        bundle.writestr("inner/p.img", payload)

    doc = parse_document([{
        "name": "outer", "location": {"local": container},
        "sha256": _sha(_read(container)),
        "children": [{"path": "inner/p.img", "name": "p",
                      "sha256": _sha(payload)}]}])
    ns = resolve.namespace_of(doc)
    context = Context(cache_dir=os.path.join(root, "cache"))
    cached = acquire.fetch_media(ns.media["p"], ns, context=context)

    assert _read(cached) == payload
    assert sorted(os.listdir(media_dir(context))) == ["p.img"]


class _CancelAfter:
    """Reports cancelled only once ``after`` checks have happened.

    Duck-typed for the one method ``_check_cancelled`` uses, so a test
    can prove the transfer loops ask at *every* chunk rather than once
    before the work starts.
    """

    def __init__(self, after):
        self.after = after
        self.checks = 0

    def is_set(self):
        self.checks += 1
        return self.checks > self.after


class _FailingResponse:
    """A response that delivers one chunk and then drops the connection."""

    headers = {}

    def __init__(self, chunks=1):
        self.chunks = chunks

    def read(self, size):
        if self.chunks <= 0:
            raise OSError("connection reset by peer")
        self.chunks -= 1
        return b"X" * size

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _extract_case(root, member_size=1):
    payload = b"P" * member_size
    container = os.path.join(root, "outer.zip")
    with zipfile.ZipFile(container, "w") as bundle:
        bundle.writestr("inner/p.img", payload)
    # The container declares no sha256, so verification is skipped
    # and the extraction itself is the work under test.
    doc = parse_document([{
        "name": "outer", "location": {"local": container},
        "children": [{"path": "inner/p.img", "name": "p"}]}])
    return resolve.namespace_of(doc), payload


# A cancelled run stops a host transfer wherever it currently is.
#
# Input deliveries finish completely once started; host transfers can
# stop partway through (docs/spec/cli.md, "Cancel ends the run, not
# the machine"). Before this change, cancellation was only checked
# between statements, so pressing Ctrl-C during a large fetch did
# nothing until the download, its hash check, the extraction, and its
# hash check had all finished.

def test_a_cancelled_run_stops_a_hash_verification(root):
    payload = b"PAYLOAD-BYTES-" * 1000
    local = os.path.join(root, "p.img")
    with open(local, "wb") as handle:
        handle.write(payload)
    doc = parse_document([{"name": "p", "location": {"local": local},
                           "sha256": _sha(payload)}])
    ns = resolve.namespace_of(doc)
    cancelled = threading.Event()
    cancelled.set()
    with pytest.raises(RunCancelled):
        acquire.fetch_media(ns.media["p"], ns,
                            context=Context(cache_dir=root),
                            cancelled=cancelled)


def test_a_cancelled_run_stops_an_extraction(root):
    ns, _payload = _extract_case(root)
    cache = os.path.join(root, "cache")
    cancelled = threading.Event()
    cancelled.set()
    with pytest.raises(RunCancelled):
        acquire.fetch_media(ns.media["p"], ns,
                            context=Context(cache_dir=cache),
                            cancelled=cancelled)
    # Nothing half-extracted is ever presented as the payload:
    # the destination only appears on the atomic replace.
    media = os.path.join(cache, "media")
    assert not os.path.exists(os.path.join(media, "p.img"))
    # Nor is the scratch file left behind. There is no resume,
    # so an abandoned partial is only garbage — and cancelling
    # a LiveCD fetch would otherwise strand hundreds of
    # megabytes in the cache.
    assert [entry for entry in os.listdir(media)
            if entry.endswith(".part")] == []


def test_the_transfer_loops_check_at_every_chunk(root):
    """Not merely once before the work begins.

    A single up-front check would leave a multi-gigabyte member
    just as uninterruptible as before.
    """
    # Comfortably more than one _CHUNK, so the loop iterates.
    ns, _payload = _extract_case(root, member_size=acquire._CHUNK * 3)
    cancelled = _CancelAfter(1)
    with pytest.raises(RunCancelled):
        acquire.fetch_media(
            ns.media["p"], ns,
            context=Context(cache_dir=os.path.join(root, "cache")),
            cancelled=cancelled)
    assert cancelled.checks > 1


def test_a_failed_download_leaves_no_scratch_file(root):
    """Not only cancellation: a dropped connection tidies up too.

    The scratch file is garbage on every incomplete path, so the
    cleanup belongs to the transfer, not to one way of ending it.
    """
    destination = os.path.join(root, "p.img")
    with mock.patch.object(acquire, "urlopen",
                           return_value=_FailingResponse()):
        with pytest.raises(OSError):
            acquire._download("http://example.invalid/p.img", destination,
                              "p", None)
    assert not os.path.exists(destination + ".part")
    assert not os.path.exists(destination)


def test_an_uncancelled_run_fetches_normally(root):
    """The event being present changes nothing while it is unset."""
    ns, payload = _extract_case(root)
    path = acquire.fetch_media(
        ns.media["p"], ns,
        context=Context(cache_dir=os.path.join(root, "cache")),
        cancelled=threading.Event())
    assert _read(path) == payload
