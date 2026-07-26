# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Tests for the media acquisition convenience surface (media.py).

Parsing, resolution, and fetch-plan execution are covered by
test_document.py / test_resolve.py / test_acquire.py; this module
covers the name-level module surface (fetch/list/clean/delete).
"""

import hashlib
import json
import os
import tempfile
import unittest

from reliquary import media
from reliquary.home import HOME_ASSETS, Context


def _home_with_media(home, media_entries):
    bpdir = os.path.join(home, "blueprints")
    os.makedirs(bpdir, exist_ok=True)
    with open(os.path.join(bpdir, "lib.rlqb"), "w", encoding="utf-8") as h:
        json.dump(list(media_entries), h)
    return Context(home=home, cache=os.path.join(home, "cache"),
                   assets=HOME_ASSETS)


class MediaModuleTests(unittest.TestCase):
    def test_fetch_local_use_media_attaches_in_place(self):
        with tempfile.TemporaryDirectory() as home:
            iso = os.path.join(home, "win.iso")
            with open(iso, "wb") as handle:
                handle.write(b"ISO")
            ctx = _home_with_media(
                home, [{"name": "win", "location": {"local": iso}}])
            self.assertEqual(media.fetch_media("win", context=ctx), iso)

    def test_new_media_fetch_returns_none(self):
        with tempfile.TemporaryDirectory() as home:
            ctx = _home_with_media(
                home, [{"name": "blank", "materialize": "new",
                        "size": "1M"}])
            self.assertIsNone(media.fetch_media("blank", context=ctx))

    def test_list_media_names_the_catalog(self):
        with tempfile.TemporaryDirectory() as home:
            ctx = _home_with_media(home, [
                {"name": "blank", "materialize": "new", "size": "1M"},
                {"name": "win", "location": {"local": "/x.iso"}}])
            self.assertEqual(media.list_media(context=ctx), ["blank", "win"])

    def test_clean_media_reclaims_the_one_cache(self):
        with tempfile.TemporaryDirectory() as home:
            ctx = Context(home=home, cache=os.path.join(home, "cache"),
                          assets=HOME_ASSETS)
            from reliquary.home import media_cache_dir
            cache = media_cache_dir(ctx)
            os.makedirs(cache, exist_ok=True)
            for name in ("junk.iso", "husk.zip"):
                with open(os.path.join(cache, name), "wb") as handle:
                    handle.write(b"x")
            self.assertEqual(media.clean_media(context=ctx),
                             ["husk", "junk"])
            self.assertEqual(os.listdir(cache), [])

    def test_clean_media_targets_just_the_named_payload(self):
        """Naming one leaves the rest of the cache alone."""
        from reliquary.home import media_cache_dir
        with tempfile.TemporaryDirectory() as home:
            ctx = Context(home=home, cache=os.path.join(home, "cache"),
                          assets=HOME_ASSETS)
            cache = media_cache_dir(ctx)
            os.makedirs(cache, exist_ok=True)
            for name in ("win.iso", "husk.zip"):
                with open(os.path.join(cache, name), "wb") as handle:
                    handle.write(b"x")
            self.assertEqual(media.clean_media("win", context=ctx), ["win"])
            self.assertFalse(os.path.exists(os.path.join(cache, "win.iso")))
            self.assertTrue(os.path.exists(os.path.join(cache, "husk.zip")))


class PruneTests(unittest.TestCase):
    """The attachment closure: what a scope still needs cached."""

    def _home(self, specs, cached=()):
        from reliquary.home import media_cache_dir
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        home = tmp.name
        bpdir = os.path.join(home, "blueprints")
        os.makedirs(bpdir)
        with open(os.path.join(bpdir, "lib.rlqb"), "w",
                  encoding="utf-8") as handle:
            json.dump(specs, handle)
        ctx = Context(home=home, cache=os.path.join(home, "cache"),
                      assets=HOME_ASSETS)
        cache = media_cache_dir(ctx)
        os.makedirs(cache, exist_ok=True)
        for filename in cached:
            with open(os.path.join(cache, filename), "wb") as handle:
                handle.write(b"x")
        return ctx, cache

    def _container_and_child(self):
        return [
            {"type": "media", "name": "husk",
             "location": "https://x.test/husk.zip", "sha256": "a" * 64,
             "children": [{"path": "payload.iso", "name": "payload"}]},
        ]

    def test_a_container_goes_once_its_child_is_cached(self):
        """The extracted payload stays; the husk it came out of goes."""
        ctx, cache = self._home(self._container_and_child(),
                                cached=["husk.zip", "payload.iso"])
        self.assertEqual(media.prune_media(context=ctx), ["husk"])
        self.assertFalse(os.path.exists(os.path.join(cache, "husk.zip")))
        self.assertTrue(os.path.exists(os.path.join(cache, "payload.iso")))

    def test_a_container_stays_while_its_child_is_not_cached(self):
        """It is still the only way to produce the child."""
        ctx, cache = self._home(self._container_and_child(),
                                cached=["husk.zip"])
        self.assertEqual(media.prune_media(context=ctx), [])
        self.assertTrue(os.path.exists(os.path.join(cache, "husk.zip")))

    def test_dry_run_reports_without_removing(self):
        ctx, cache = self._home(self._container_and_child(),
                                cached=["husk.zip", "payload.iso"])
        self.assertEqual(
            media.prune_media(context=ctx, dry_run=True), ["husk"])
        self.assertTrue(os.path.exists(os.path.join(cache, "husk.zip")))

    def test_prune_keeps_a_cached_media_the_catalog_declares(self):
        """Nothing derives from it, so it stays in the closure."""
        ctx, cache = self._home(
            [{"type": "media", "name": "payload", "location": "p.iso"}],
            cached=["payload.iso"])
        self.assertEqual(media.prune_media(context=ctx), [])
        self.assertTrue(os.path.exists(os.path.join(cache, "payload.iso")))


class AddMediaTests(unittest.TestCase):
    """`add-media` authors a declaration; it never touches the cache."""

    def _ctx(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return Context(home=tmp.name, cache=os.path.join(tmp.name, "cache"),
                       assets=HOME_ASSETS)

    def _payload(self, ctx, body=b"ISO"):
        path = os.path.join(ctx.home, "win98.iso")
        with open(path, "wb") as handle:
            handle.write(body)
        return path

    def test_it_writes_a_media_spec_pinning_the_computed_hash(self):
        from reliquary import blueprint
        from reliquary.document import load_document
        ctx = self._ctx()
        payload = self._payload(ctx)
        expected = hashlib.sha256(b"ISO").hexdigest()

        written = blueprint.add_media("win98-cd", payload, context=ctx)

        self.assertTrue(written.endswith("win98-cd.rlqb"))
        declared = load_document(written).media["win98-cd"]
        self.assertEqual(declared.sha256, expected)
        self.assertEqual(len(declared.location), 1)
        self.assertEqual(declared.location[0].kind, "local")

    def test_the_file_stays_put_and_the_cache_is_untouched(self):
        from reliquary import blueprint
        from reliquary.home import media_cache_dir
        ctx = self._ctx()
        payload = self._payload(ctx)

        blueprint.add_media("win98-cd", payload, context=ctx)

        self.assertTrue(os.path.exists(payload))
        self.assertFalse(os.path.isdir(media_cache_dir(ctx)))

    def test_the_declaration_resolves_and_fetches_in_place(self):
        """The whole point: the media now works, unpinned from a cache."""
        from reliquary import blueprint
        ctx = self._ctx()
        payload = self._payload(ctx)
        blueprint.add_media("win98-cd", payload, context=ctx)

        fetched = media.fetch_media("win98-cd", context=ctx)
        # Forward slashes in the spec, so compare identity, not spelling.
        self.assertTrue(os.path.samefile(fetched, payload))

    def test_an_existing_blueprint_is_never_rewritten(self):
        from reliquary import blueprint
        ctx = self._ctx()
        payload = self._payload(ctx)
        blueprint.add_media("win98-cd", payload, context=ctx)
        with self.assertRaises(FileExistsError):
            blueprint.add_media("win98-cd", payload, context=ctx)

    def test_a_missing_file_fails_before_writing_anything(self):
        from reliquary import blueprint
        from reliquary.home import blueprints_dir
        ctx = self._ctx()
        with self.assertRaises(FileNotFoundError):
            blueprint.add_media("win98-cd", os.path.join(ctx.home, "nope"),
                                context=ctx)
        self.assertFalse(os.path.exists(
            os.path.join(blueprints_dir(ctx), "win98-cd.rlqb")))


if __name__ == "__main__":
    unittest.main()
