# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Tests for the media acquisition convenience surface (media.py).

Parsing, resolution, and fetch-plan execution are covered by
test_document.py / test_resolve.py / test_acquire.py; this module
covers the name-level module surface (fetch/list/clean/delete).
"""

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

    def test_clean_media_spares_a_supplied_payload(self):
        """Nothing can put it back, so nothing takes it blindly."""
        from reliquary import ledger
        from reliquary.home import media_cache_dir
        with tempfile.TemporaryDirectory() as home:
            ctx = Context(home=home, cache=os.path.join(home, "cache"),
                          assets=HOME_ASSETS)
            cache = media_cache_dir(ctx)
            os.makedirs(cache, exist_ok=True)
            for name in ("win.iso", "husk.zip"):
                with open(os.path.join(cache, name), "wb") as handle:
                    handle.write(b"x")
            ledger.record("win", filename="win.iso", sha256="a" * 64,
                          provenance=ledger.SUPPLIED, context=ctx)
            self.assertEqual(media.clean_media(context=ctx), ["husk"])
            self.assertTrue(os.path.exists(os.path.join(cache, "win.iso")))
            # Named explicitly, it goes: the user asked for it.
            self.assertEqual(media.clean_media("win", context=ctx), ["win"])
            self.assertFalse(os.path.exists(os.path.join(cache, "win.iso")))


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

    def test_prune_spares_a_supplied_payload(self):
        from reliquary import ledger
        ctx, cache = self._home(
            [{"type": "media", "name": "payload", "location": "p.iso"}],
            cached=["stray.iso"])
        ledger.record("stray", filename="stray.iso", sha256="a" * 64,
                      provenance=ledger.SUPPLIED, context=ctx)
        self.assertEqual(media.prune_media(context=ctx), [])
        self.assertTrue(os.path.exists(os.path.join(cache, "stray.iso")))


class LedgerTests(unittest.TestCase):
    """What the ledger buys: a mismatch that explains itself."""

    def _ctx(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return Context(home=tmp.name, cache=os.path.join(tmp.name, "cache"),
                       assets=HOME_ASSETS)

    def test_records_and_forgets(self):
        from reliquary import ledger
        ctx = self._ctx()
        ledger.record("iso", filename="iso.iso", sha256="a" * 64,
                      provenance=ledger.REFETCHABLE,
                      source="https://x.test/a.iso", context=ctx)
        entry = ledger.entry("iso", ctx)
        self.assertEqual(entry["provenance"], ledger.REFETCHABLE)
        self.assertEqual(entry["source"], "https://x.test/a.iso")
        self.assertTrue(ledger.forget("iso", ctx))
        self.assertIsNone(ledger.entry("iso", ctx))

    def test_a_different_source_reads_as_a_name_collision(self):
        from reliquary import ledger
        ctx = self._ctx()
        ledger.record("iso", filename="iso.iso", sha256="a" * 64,
                      provenance=ledger.REFETCHABLE,
                      source="https://one.test/a.iso", context=ctx)
        message = ledger.explain("iso", "b" * 64, "a" * 64,
                                 source="https://two.test/a.iso", context=ctx)
        self.assertIn("share one name", message)
        self.assertIn("one.test", message)
        self.assertIn("two.test", message)

    def test_the_same_source_reads_as_a_version_bump(self):
        from reliquary import ledger
        ctx = self._ctx()
        url = "https://x.test/a.iso"
        ledger.record("iso", filename="iso.iso", sha256="a" * 64,
                      provenance=ledger.REFETCHABLE, source=url, context=ctx)
        message = ledger.explain("iso", "b" * 64, "a" * 64, source=url,
                                 context=ctx)
        self.assertIn("changed", message)
        self.assertNotIn("share one name", message)

    def test_a_supplied_mismatch_never_suggests_refetching(self):
        from reliquary import ledger
        ctx = self._ctx()
        ledger.record("win", filename="win.iso", sha256="a" * 64,
                      provenance=ledger.SUPPLIED, source="D:/isos/win.iso",
                      context=ctx)
        message = ledger.explain("win", "b" * 64, "a" * 64, context=ctx)
        self.assertIn("supplied by hand", message)
        self.assertIn("clean-media win", message)


if __name__ == "__main__":
    unittest.main()
