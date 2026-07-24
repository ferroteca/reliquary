# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Tests for fetch-plan acquisition (acquire.py), offline."""

import hashlib
import os
import tempfile
import unittest
import zipfile

from reliquary import acquire, resolve
from reliquary.document import parse_document
from reliquary.home import Context


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

    def test_extraction_records_its_derivation_in_the_ledger(self):
        """A derived payload records what produced it, not just its hash.

        The derivation key is what lets the cache answer "is this the
        file this blueprint means?" without re-deriving it.
        """
        from reliquary import ledger

        with tempfile.TemporaryDirectory() as root:
            payload = b"PAYLOAD"
            container = os.path.join(root, "outer.zip")
            with zipfile.ZipFile(container, "w") as bundle:
                bundle.writestr("inner/p.img", payload)
            container_sha = _sha(_read(container))

            doc = parse_document([{
                "name": "outer", "location": {"local": container},
                "sha256": container_sha,
                "children": [{"path": "inner/p.img", "name": "p",
                              "sha256": _sha(payload)}]}])
            ns = resolve.namespace_of(doc)
            ctx = Context(cache=os.path.join(root, "cache"))
            acquire.fetch_media(ns.media["p"], ns, context=ctx)

            entry = ledger.entry("p", ctx)
            self.assertEqual(entry["provenance"], ledger.DERIVED)
            self.assertEqual(entry["sha256"], _sha(payload))
            self.assertEqual(entry["derivation"]["parent"], "outer")
            self.assertEqual(entry["derivation"]["path"], "inner/p.img")
            self.assertEqual(entry["derivation"]["parent-sha"], container_sha)
            # The container here is local: used in place, never copied
            # into the cache, so there is nothing for the ledger to
            # describe. Only cached files get entries.
            self.assertIsNone(ledger.entry("outer", ctx))


if __name__ == "__main__":
    unittest.main()
