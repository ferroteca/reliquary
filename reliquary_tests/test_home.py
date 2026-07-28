# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Tests for working-directory resolution: the six placeable dirs."""

import os
import unittest

import importlib

from reliquary.errors import StaticError

home = importlib.import_module("reliquary.home")


class _Isolated(unittest.TestCase):
    """Every test starts with all six directories unassigned."""

    def setUp(self):
        saved = dict(home._globals)
        self.addCleanup(home._globals.update, saved)
        for name in home.DIRECTORIES:
            home._globals[name] = None
        self.addCleanup(home.set_autoseed, home._autoseed)


class UnassignedTests(_Isolated):
    """Nothing has a value at startup, and asking is an error."""

    def test_every_directory_starts_unassigned(self):
        for name in home.DIRECTORIES:
            self.assertFalse(home.is_assigned(name), name)

    def test_each_directory_fails_closed_naming_itself(self):
        resolvers = {
            "home": home.home_dir, "blueprints": home.blueprints_dir,
            "scripts": home.scripts_dir, "cache": home.cache_dir,
            "media": home.media_dir, "machines": home.machines_dir,
        }
        for name, resolve in resolvers.items():
            with self.subTest(name):
                with self.assertRaises(StaticError) as caught:
                    resolve()
                self.assertIn("'%s'" % name, str(caught.exception))
                self.assertEqual(caught.exception.rule_id, "dir.unassigned")

    def test_the_error_names_the_directory_asked_for(self):
        """Not the unassigned ancestor, which nobody asked about."""
        with self.assertRaises(StaticError) as caught:
            home.media_dir()
        message = str(caught.exception)
        self.assertIn("no directory assigned for 'media'", message)
        self.assertIn("--media-dir", message)
        self.assertIn("RELIQUARY_MEDIA_DIR", message)
        # The ancestors appear as the other way to supply it.
        self.assertIn("'cache' or 'home'", message)


class DerivationTests(_Isolated):
    """Assignment cascades, and only into what is still unassigned."""

    def test_home_reaches_all_six(self):
        home.set_home_dir(os.path.join("some", "home"))
        root = os.path.abspath(os.path.join("some", "home"))
        self.assertEqual(home.home_dir(), root)
        self.assertEqual(home.blueprints_dir(),
                         os.path.join(root, "blueprints"))
        self.assertEqual(home.scripts_dir(),
                         os.path.join(root, "scripts"))
        self.assertEqual(home.cache_dir(), os.path.join(root, "cache"))
        self.assertEqual(home.media_dir(),
                         os.path.join(root, "cache", "media"))
        self.assertEqual(home.machines_dir(),
                         os.path.join(root, "cache", "machines"))

    def test_an_explicit_cache_wins_over_the_derived_one(self):
        home.set_home_dir(os.path.join("some", "home"))
        home.set_cache_dir(os.path.join("fast", "disk"))
        fast = os.path.abspath(os.path.join("fast", "disk"))
        self.assertEqual(home.cache_dir(), fast)
        self.assertEqual(home.media_dir(), os.path.join(fast, "media"))
        self.assertEqual(home.blueprints_dir(),
                         os.path.join(os.path.abspath(
                             os.path.join("some", "home")), "blueprints"))

    def test_cache_alone_conjures_no_home(self):
        home.set_cache_dir(os.path.join("only", "cache"))
        self.assertEqual(home.media_dir(),
                         os.path.join(os.path.abspath(
                             os.path.join("only", "cache")), "media"))
        with self.assertRaises(StaticError):
            home.home_dir()
        with self.assertRaises(StaticError):
            home.blueprints_dir()

    def test_machines_alone_leaves_media_where_the_rest_puts_it(self):
        home.set_home_dir(os.path.join("some", "home"))
        home.set_machines_dir(os.path.join("big", "disk"))
        self.assertEqual(home.machines_dir(),
                         os.path.abspath(os.path.join("big", "disk")))
        self.assertEqual(
            home.media_dir(),
            os.path.join(os.path.abspath(os.path.join("some", "home")),
                         "cache", "media"))


class EnvironmentTests(_Isolated):
    """The environment assigns, and only what nothing else has."""

    def _pin(self, name, value):
        variable = home.environment_variable(name)
        saved = os.environ.get(variable)

        def restore():
            if saved is None:
                os.environ.pop(variable, None)
            else:
                os.environ[variable] = saved

        self.addCleanup(restore)
        os.environ[variable] = value

    def test_the_variable_name_follows_the_flag(self):
        self.assertEqual(home.environment_variable("home"),
                         "RELIQUARY_HOME_DIR")
        self.assertEqual(home.environment_variable("blueprints"),
                         "RELIQUARY_BLUEPRINTS_DIR")

    def test_adopting_assigns_every_named_directory(self):
        for name in home.DIRECTORIES:
            self._pin(name, os.path.join("env", name))
        home.adopt_environment()
        self.assertEqual(home.machines_dir(),
                         os.path.abspath(os.path.join("env", "machines")))
        self.assertEqual(home.blueprints_dir(),
                         os.path.abspath(os.path.join("env", "blueprints")))

    def test_an_explicit_assignment_wins_over_the_environment(self):
        self._pin("home", os.path.join("env", "home"))
        home.set_home_dir(os.path.join("flag", "home"))
        home.adopt_environment()
        self.assertEqual(home.home_dir(),
                         os.path.abspath(os.path.join("flag", "home")))

    def test_nothing_is_read_at_import(self):
        """A library must not acquire a directory from the shell.

        The environment is honoured by the CLI's own step, so an
        embedding call is unaffected by whatever the developer has
        exported. Isolation here has already cleared the globals; what
        this asserts is that resolution does not consult the
        environment behind them.
        """
        self._pin("home", os.path.join("env", "home"))
        with self.assertRaises(StaticError):
            home.home_dir()


class ContextTests(_Isolated):
    """A Context pins slots per call, independent of the globals."""

    def setUp(self):
        super().setUp()
        home.set_home_dir(os.path.join("global", "home"))
        home.set_cache_dir(os.path.join("global", "cache"))

    def test_explicit_slots_ignore_the_globals(self):
        context = home.Context(
            home_dir=os.path.join("scoped", "home"),
            cache_dir=os.path.join("scoped", "cache"))
        self.assertEqual(home.home_dir(context),
                         os.path.abspath(os.path.join("scoped", "home")))
        self.assertEqual(home.cache_dir(context),
                         os.path.abspath(os.path.join("scoped", "cache")))

    def test_an_unfilled_slot_falls_through_to_the_globals(self):
        context = home.Context(home_dir=os.path.join("scoped", "home"))
        self.assertEqual(home.cache_dir(context),
                         os.path.abspath(os.path.join("global", "cache")))

    def test_a_scoped_slot_derives_for_its_children(self):
        context = home.Context(cache_dir=os.path.join("scoped", "cache"))
        self.assertEqual(
            home.media_dir(context),
            os.path.join(os.path.abspath(os.path.join("scoped", "cache")),
                         "media"))

    def test_bare_string_is_sugar_for_the_home(self):
        self.assertEqual(
            home.blueprints_dir(os.path.join("scoped", "home")),
            os.path.join(
                os.path.abspath(os.path.join("scoped", "home")),
                "blueprints"))

    def test_none_context_uses_the_globals(self):
        self.assertEqual(home.cache_dir(None),
                         os.path.abspath(os.path.join("global", "cache")))

    def test_a_context_may_be_built_before_it_is_usable(self):
        """The error fires at first use, not at construction."""
        self.assertIsNone(home.Context().media_dir)


class AutoseedTests(_Isolated):
    """Codex autoseeding is its own axis: off unless something says on."""

    def test_off_by_default_in_the_library(self):
        home.set_autoseed(False)
        self.assertFalse(home.autoseed())

    def test_the_global_applies(self):
        home.set_autoseed(True)
        self.assertTrue(home.autoseed())

    def test_a_context_pins_it_per_call(self):
        home.set_autoseed(True)
        self.assertFalse(home.autoseed(home.Context(autoseed=False)))
        home.set_autoseed(False)
        self.assertTrue(home.autoseed(home.Context(autoseed=True)))

    def test_a_bare_home_string_decides_nothing_about_seeding(self):
        """One shorthand answers one question.

        The bare string used to select home *mode*, which carried codex
        seeding with it. Placement and seeding are separate axes now,
        so it assigns the home and leaves seeding to whoever owns it.
        """
        home.set_autoseed(False)
        self.assertFalse(home.autoseed(os.path.join("some", "home")))


class DefaultHomeTests(unittest.TestCase):
    """The value the CLI assigns when the caller named no home."""

    def test_default_home_is_named_reliquary(self):
        self.assertEqual(os.path.basename(home.default_home_dir()),
                         "reliquary")

    def test_default_home_is_absolute(self):
        self.assertTrue(os.path.isabs(home.default_home_dir()))


if __name__ == "__main__":
    unittest.main()
