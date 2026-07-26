# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Tests for fetch-plan acquisition (acquire.py), offline."""

import hashlib
import os
import tempfile
import threading
import unittest
import zipfile
from unittest import mock

from reliquary import acquire, resolve
from reliquary.document import parse_document
from reliquary.errors import PreflightError, RunCancelled
from reliquary.home import Context, media_cache_dir


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _read(path):
    with open(path, "rb") as handle:
        return handle.read()


class AcquireTests(unittest.TestCase):
    def test_nested_local_archive_extraction(self):
        with tempfile.TemporaryDirectory() as root:
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
            ctx = Context(cache=cache)

            path = acquire.fetch_media(ns.media["payload"], ns, context=ctx)
            self.assertEqual(_read(path), payload)
            self.assertEqual(os.path.basename(path), "payload.img")
            self.assertTrue(os.path.exists(
                os.path.join(cache, "media", "payload.img")))
            # The container is a media like any other now: one cache,
            # keyed by name, with no second directory for archives.
            self.assertTrue(os.path.exists(
                os.path.join(cache, "media", "inner.zip")))

            # idempotent: a second fetch verifies the cache and reuses it
            self.assertEqual(
                acquire.fetch_media(ns.media["payload"], ns, context=ctx), path)

    def test_new_media_returns_none(self):
        doc = parse_document([
            {"name": "blank", "materialize": "new", "size": "1M"}])
        ns = resolve.namespace_of(doc)
        self.assertIsNone(
            acquire.fetch_media(ns.media["blank"], ns, context=Context(cache=".")))

    def test_local_use_media_attaches_in_place(self):
        with tempfile.TemporaryDirectory() as root:
            iso = os.path.join(root, "win98se.iso")
            with open(iso, "wb") as handle:
                handle.write(b"ISO-CONTENT")
            doc = parse_document([
                {"name": "win", "location": {"local": iso}}])
            ns = resolve.namespace_of(doc)
            path = acquire.fetch_media(
                ns.media["win"], ns, context=Context(cache=os.path.join(root, "c")))
            self.assertEqual(path, iso)  # used in place, not copied to cache

    def test_a_missing_local_payload_names_the_media_and_the_path(self):
        """It must not reach the backend as a failure to open a path."""
        with tempfile.TemporaryDirectory() as root:
            gone = os.path.join(root, "moved-away.iso")
            doc = parse_document([
                {"name": "win98-cd", "location": {"local": gone},
                 "sha256": "a" * 64}])
            ns = resolve.namespace_of(doc)
            with self.assertRaises(PreflightError) as caught:
                acquire.fetch_media(ns.media["win98-cd"], ns,
                                    context=Context(cache=root))
            message = str(caught.exception)
            self.assertIn("win98-cd", message)
            self.assertIn(gone, message)

    def test_a_missing_local_payload_is_caught_without_a_pin(self):
        """Unpinned, it would otherwise pass a dead path straight on."""
        with tempfile.TemporaryDirectory() as root:
            gone = os.path.join(root, "moved-away.img")
            doc = parse_document([
                {"name": "floppy", "location": {"local": gone}}])
            ns = resolve.namespace_of(doc)
            with self.assertRaises(PreflightError):
                acquire.fetch_media(ns.media["floppy"], ns,
                                    context=Context(cache=root))

    def test_a_directory_source_is_not_treated_as_missing(self):
        """A directory location is legal — it attaches as vvfat."""
        with tempfile.TemporaryDirectory() as root:
            staging = os.path.join(root, "staging")
            os.makedirs(staging)
            doc = parse_document([
                {"name": "exchange", "location": {"local": staging}}])
            ns = resolve.namespace_of(doc)
            self.assertEqual(
                acquire.fetch_media(ns.media["exchange"], ns,
                                    context=Context(cache=root)),
                staging)

    def test_remote_without_hash_fails_before_network(self):
        # A remote location with no sha256 parses — the required-once-
        # remote rule is a resolution check, since a referenced rung may
        # resolve to a URL — and resolution refuses it up front, so this
        # never touches the network.
        doc = parse_document([
            {"name": "x", "location": {"url": "https://example/a.iso"}}])
        ns = resolve.namespace_of(doc)
        with self.assertRaises(ValueError):
            acquire.fetch_media(ns.media["x"], ns, context=Context(cache="."))

    def test_extraction_caches_the_child_and_not_a_local_container(self):
        """The derived payload is cached under its own name.

        A local container is used in place, never copied in — so the
        cache holds exactly the media that had to be produced.
        """
        with tempfile.TemporaryDirectory() as root:
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
            ctx = Context(cache=os.path.join(root, "cache"))
            cached = acquire.fetch_media(ns.media["p"], ns, context=ctx)

            self.assertEqual(_read(cached), payload)
            self.assertEqual(
                sorted(os.listdir(media_cache_dir(ctx))), ["p.img"])


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


class CancellationTests(unittest.TestCase):
    """A cancelled run aborts a host transfer where it stands.

    The execution model's severability: input deliveries are atomic,
    host transfers abort (planning/ROADMAP.md, "Cancel ends the run,
    not the machine"). Before this, cancellation was only observed at
    statement boundaries, so a Ctrl-C during a large fetch was not
    seen until the download, its hash, the extraction, and *its* hash
    had all finished.
    """

    def _extract_case(self, root, member_size=1):
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

    def test_a_cancelled_run_stops_a_hash_verification(self):
        with tempfile.TemporaryDirectory() as root:
            payload = b"PAYLOAD-BYTES-" * 1000
            local = os.path.join(root, "p.img")
            with open(local, "wb") as handle:
                handle.write(payload)
            doc = parse_document([{
                "name": "p", "location": {"local": local},
                "sha256": _sha(payload)}])
            ns = resolve.namespace_of(doc)
            cancelled = threading.Event()
            cancelled.set()
            with self.assertRaises(RunCancelled):
                acquire.fetch_media(
                    ns.media["p"], ns, context=Context(cache=root),
                    cancelled=cancelled)

    def test_a_cancelled_run_stops_an_extraction(self):
        with tempfile.TemporaryDirectory() as root:
            ns, _ = self._extract_case(root)
            cache = os.path.join(root, "cache")
            cancelled = threading.Event()
            cancelled.set()
            with self.assertRaises(RunCancelled):
                acquire.fetch_media(
                    ns.media["p"], ns, context=Context(cache=cache),
                    cancelled=cancelled)
            # Nothing half-extracted is ever presented as the payload:
            # the destination only appears on the atomic replace.
            media = os.path.join(cache, "media")
            self.assertFalse(os.path.exists(os.path.join(media, "p.img")))
            # Nor is the scratch file left behind. There is no resume,
            # so an abandoned partial is only garbage — and cancelling
            # a LiveCD fetch would otherwise strand hundreds of
            # megabytes in the cache.
            self.assertEqual(
                [entry for entry in os.listdir(media)
                 if entry.endswith(".part")], [])

    def test_the_transfer_loops_check_at_every_chunk(self):
        """Not merely once before the work begins.

        A single up-front check would leave a multi-gigabyte member
        just as uninterruptible as before.
        """
        with tempfile.TemporaryDirectory() as root:
            # Comfortably more than one _CHUNK, so the loop iterates.
            ns, _ = self._extract_case(root, member_size=acquire._CHUNK * 3)
            cancelled = _CancelAfter(1)
            with self.assertRaises(RunCancelled):
                acquire.fetch_media(
                    ns.media["p"], ns,
                    context=Context(cache=os.path.join(root, "cache")),
                    cancelled=cancelled)
            self.assertGreater(cancelled.checks, 1)

    def test_a_failed_download_leaves_no_scratch_file(self):
        """Not only cancellation: a dropped connection tidies up too.

        The scratch file is garbage on every incomplete path, so the
        cleanup belongs to the transfer, not to one way of ending it.
        """
        with tempfile.TemporaryDirectory() as root:
            destination = os.path.join(root, "p.img")
            with mock.patch.object(acquire, "urlopen",
                                   return_value=_FailingResponse()):
                with self.assertRaises(OSError):
                    acquire._download(
                        "http://example.invalid/p.img", destination,
                        "p", None)
            self.assertFalse(os.path.exists(destination + ".part"))
            self.assertFalse(os.path.exists(destination))

    def test_an_uncancelled_run_fetches_normally(self):
        """The event being present changes nothing while it is unset."""
        with tempfile.TemporaryDirectory() as root:
            ns, payload = self._extract_case(root)
            path = acquire.fetch_media(
                ns.media["p"], ns,
                context=Context(cache=os.path.join(root, "cache")),
                cancelled=threading.Event())
            self.assertEqual(_read(path), payload)


if __name__ == "__main__":
    unittest.main()
