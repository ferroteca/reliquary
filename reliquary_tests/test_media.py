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
        json.dump({"media": media_entries}, h)
    return Context(home=home, cache=os.path.join(home, "cache"),
                   assets=HOME_ASSETS)


class MediaModuleTests(unittest.TestCase):
    def test_fetch_local_use_media_attaches_in_place(self):
        with tempfile.TemporaryDirectory() as home:
            iso = os.path.join(home, "win.iso")
            with open(iso, "wb") as handle:
                handle.write(b"ISO")
            ctx = _home_with_media(
                home, [{"name": "win", "source": {"local": iso}}])
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
                {"name": "win", "source": {"local": "/x.iso"}}])
            self.assertEqual(media.list_media(context=ctx), ["blank", "win"])

    def test_clean_media_and_archives(self):
        with tempfile.TemporaryDirectory() as home:
            ctx = Context(home=home, cache=os.path.join(home, "cache"),
                          assets=HOME_ASSETS)
            from reliquary.home import archives_cache_dir, media_cache_dir
            for cache in (media_cache_dir(ctx), archives_cache_dir(ctx)):
                os.makedirs(cache, exist_ok=True)
                with open(os.path.join(cache, "junk"), "wb") as handle:
                    handle.write(b"x")
            media.clean_media(ctx)
            media.clean_archives(ctx)
            self.assertEqual(os.listdir(media_cache_dir(ctx)), [])
            self.assertEqual(os.listdir(archives_cache_dir(ctx)), [])


if __name__ == "__main__":
    unittest.main()
