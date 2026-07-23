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

            doc = parse_document({"archives": [{
                "name": "outer",
                "source": {"local": outer_zip, "sha256": outer_sha},
                "members": [{
                    "path": "inner.zip", "sha256": inner_sha,
                    "members": [{"path": "144m/payload.img", "name": "payload",
                                 "sha256": payload_sha}]}]}]})
            ns = resolve.namespace_of(doc)
            cache = os.path.join(root, "cache")
            ctx = Context(cache=cache)

            path = acquire.fetch_media(ns.media["payload"], ns, context=ctx)
            self.assertEqual(_read(path), payload)
            self.assertEqual(os.path.basename(path), "payload.img")
            self.assertTrue(os.path.exists(
                os.path.join(cache, "media", "payload.img")))
            self.assertTrue(os.path.exists(
                os.path.join(cache, "archives", "inner.zip")))

            # idempotent: a second fetch verifies the cache and reuses it
            self.assertEqual(
                acquire.fetch_media(ns.media["payload"], ns, context=ctx), path)

    def test_new_media_returns_none(self):
        doc = parse_document({"media": [
            {"name": "blank", "materialize": "new", "size": "1M"}]})
        ns = resolve.namespace_of(doc)
        self.assertIsNone(
            acquire.fetch_media(ns.media["blank"], ns, context=Context(cache=".")))

    def test_local_use_media_attaches_in_place(self):
        with tempfile.TemporaryDirectory() as root:
            iso = os.path.join(root, "win98se.iso")
            with open(iso, "wb") as handle:
                handle.write(b"ISO-CONTENT")
            doc = parse_document({"media": [
                {"name": "win", "source": {"local": iso}}]})
            ns = resolve.namespace_of(doc)
            path = acquire.fetch_media(
                ns.media["win"], ns, context=Context(cache=os.path.join(root, "c")))
            self.assertEqual(path, iso)  # used in place, not copied to cache

    def test_url_source_without_hash_fails_before_network(self):
        # A url with no sha256 parses (the schema/parser defer the
        # required-on-url rule), but acquisition refuses it up front —
        # so this never touches the network.
        doc = parse_document({"media": [
            {"name": "x", "source": {"url": "https://example/a.iso"}}]})
        ns = resolve.namespace_of(doc)
        with self.assertRaises(RuntimeError):
            acquire.fetch_media(ns.media["x"], ns, context=Context(cache="."))


if __name__ == "__main__":
    unittest.main()
