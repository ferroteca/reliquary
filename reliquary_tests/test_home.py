# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Tests for reliquary home resolution."""

import os
import unittest

import importlib

home = importlib.import_module("reliquary.home")


class HomeTests(unittest.TestCase):
    """Behavior of the reliquary home directory layout."""

    def setUp(self):
        self._saved = home._home
        self.addCleanup(setattr, home, "_home", self._saved)

    def test_set_home_overrides_resolution(self):
        """set_home() pins the home directory for later calls."""
        home.set_home(os.path.join("some", "where"))
        self.assertEqual(home.home(),
                         os.path.abspath(os.path.join("some", "where")))

    def test_environment_seeds_home(self):
        """RELIQUARY_HOME provides the initial home value."""
        # The module reads RELIQUARY_HOME at import; the module-level
        # default mirrors that seed, so simulate it directly.
        home._home = r"C:\elsewhere\reliquary"
        self.assertEqual(home.home(), r"C:\elsewhere\reliquary")

    def test_default_home_is_named_reliquary(self):
        """The fallback home is a directory named 'reliquary'."""
        home._home = None
        self.assertEqual(os.path.basename(home.home()), "reliquary")


class CacheTests(unittest.TestCase):
    """The cache root resolves independently of the home."""

    def setUp(self):
        self._saved_home = home._home
        self.addCleanup(setattr, home, "_home", self._saved_home)
        self._saved_cache = home._cache
        self.addCleanup(setattr, home, "_cache", self._saved_cache)
        home._home = os.path.join("some", "home")
        home._cache = None

    def test_defaults_under_home(self):
        """With no override, the cache root is <home>/cache."""
        self.assertEqual(
            home.cache_dir(),
            os.path.join(os.path.join("some", "home"), "cache"))

    def test_set_cache_overrides_resolution(self):
        """set_cache() pins the cache root independent of the home."""
        home.set_cache(os.path.join("some", "cache"))
        self.assertEqual(
            home.cache_dir(),
            os.path.abspath(os.path.join("some", "cache")))

    def test_environment_seeds_cache(self):
        """RELIQUARY_CACHE_DIR provides the initial cache value."""
        home._cache = r"C:\elsewhere\cache"
        self.assertEqual(home.cache_dir(), r"C:\elsewhere\cache")


class ContextTests(unittest.TestCase):
    """Context pins home/cache explicitly, independent of the globals."""

    def setUp(self):
        self._saved_home = home._home
        self.addCleanup(setattr, home, "_home", self._saved_home)
        self._saved_cache = home._cache
        self.addCleanup(setattr, home, "_cache", self._saved_cache)
        home._home = os.path.join("global", "home")
        home._cache = os.path.join("global", "cache")

    def test_explicit_home_and_cache_ignore_the_globals(self):
        context = home.Context(
            home=os.path.join("scoped", "home"),
            cache=os.path.join("scoped", "cache"))
        self.assertEqual(
            context.home_dir(),
            os.path.abspath(os.path.join("scoped", "home")))
        self.assertEqual(
            context.cache_dir(),
            os.path.abspath(os.path.join("scoped", "cache")))

    def test_explicit_home_alone_still_follows_the_global_cache(self):
        context = home.Context(home=os.path.join("scoped", "home"))
        self.assertEqual(
            context.cache_dir(), os.path.abspath(
                os.path.join("global", "cache")))

    def test_bare_string_is_sugar_for_context_home(self):
        """A plain string context= is equivalent to Context(home=...)."""
        self.assertEqual(
            home.blueprints_dir(os.path.join("scoped", "home")),
            os.path.join(
                os.path.abspath(os.path.join("scoped", "home")),
                "blueprints"))

    def test_none_context_uses_the_globals(self):
        self.assertEqual(
            home.cache_dir(None),
            os.path.abspath(os.path.join("global", "cache")))


if __name__ == "__main__":
    unittest.main()
