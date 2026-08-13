# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for working-directory resolution: the six placeable dirs.

There is no process-global assignment any more (P26): the ``Context``
record a session is opened on carries everything, so what is asserted
here is the record's own resolution — slots, derivation, the
fail-closed refusal — and that nothing ambient stands behind it.
"""

import os
import unittest

from reliquary import home
from reliquary.errors import StaticError


class UnassignedTests(unittest.TestCase):
    """An empty record holds nothing, and asking is an error."""

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


class EnvironmentTests(unittest.TestCase):
    """The variables name themselves; the library reads none of them."""

    def test_the_variable_name_follows_the_flag(self):
        self.assertEqual(home.environment_variable("home"),
                         "RELIQUARY_HOME")
        self.assertEqual(home.environment_variable("blueprints"),
                         "RELIQUARY_BLUEPRINTS_DIR")

    def test_the_environment_is_never_read(self):
        """A library must not acquire a directory from the shell.

        The environment is honoured by the CLI's own construction
        step and nowhere else, so an exported variable changes
        nothing about an engine call's resolution.
        """
        variable = home.environment_variable("home")
        saved = os.environ.get(variable)

        def restore():
            if saved is None:
                os.environ.pop(variable, None)
            else:
                os.environ[variable] = saved

        self.addCleanup(restore)
        os.environ[variable] = os.path.join("env", "home")
        with self.assertRaises(StaticError):
            home.home_dir()


class DerivationTests(unittest.TestCase):
    """A record's slots cascade, and only into what is unassigned."""

    def test_a_home_reaches_all_six(self):
        context = home.Context(home_dir=os.path.join("some", "home"))
        root = os.path.abspath(os.path.join("some", "home"))
        self.assertEqual(home.home_dir(context), root)
        self.assertEqual(home.blueprints_dir(context),
                         os.path.join(root, "blueprints"))
        self.assertEqual(home.scripts_dir(context),
                         os.path.join(root, "scripts"))
        self.assertEqual(home.cache_dir(context),
                         os.path.join(root, "cache"))
        self.assertEqual(home.media_dir(context),
                         os.path.join(root, "cache", "media"))
        self.assertEqual(home.machines_dir(context),
                         os.path.join(root, "cache", "machines"))

    def test_an_explicit_cache_wins_over_the_derived_one(self):
        context = home.Context(home_dir=os.path.join("some", "home"),
                               cache_dir=os.path.join("fast", "disk"))
        fast = os.path.abspath(os.path.join("fast", "disk"))
        self.assertEqual(home.cache_dir(context), fast)
        self.assertEqual(home.media_dir(context),
                         os.path.join(fast, "media"))
        self.assertEqual(home.blueprints_dir(context),
                         os.path.join(os.path.abspath(
                             os.path.join("some", "home")), "blueprints"))

    def test_cache_alone_conjures_no_home(self):
        context = home.Context(cache_dir=os.path.join("only", "cache"))
        self.assertEqual(home.media_dir(context),
                         os.path.join(os.path.abspath(
                             os.path.join("only", "cache")), "media"))
        with self.assertRaises(StaticError):
            home.home_dir(context)
        with self.assertRaises(StaticError):
            home.blueprints_dir(context)

    def test_machines_alone_leaves_media_where_the_rest_puts_it(self):
        context = home.Context(home_dir=os.path.join("some", "home"),
                               machines_dir=os.path.join("big", "disk"))
        self.assertEqual(home.machines_dir(context),
                         os.path.abspath(os.path.join("big", "disk")))
        self.assertEqual(
            home.media_dir(context),
            os.path.join(os.path.abspath(os.path.join("some", "home")),
                         "cache", "media"))

    def test_bare_string_is_sugar_for_the_home(self):
        self.assertEqual(
            home.blueprints_dir(os.path.join("scoped", "home")),
            os.path.join(
                os.path.abspath(os.path.join("scoped", "home")),
                "blueprints"))

    def test_a_context_may_be_built_before_it_is_usable(self):
        """The refusal fires at use, not at record construction."""
        self.assertIsNone(home.Context().media_dir)


class PinnedTests(unittest.TestCase):
    """The record-only resolution the session pins at its door."""

    def test_a_home_alone_fills_all_six(self):
        pinned = home.pinned(os.path.join("some", "home"))
        root = os.path.abspath(os.path.join("some", "home"))
        self.assertEqual(pinned.home_dir, root)
        self.assertEqual(pinned.blueprints_dir,
                         os.path.join(root, "blueprints"))
        self.assertEqual(pinned.scripts_dir,
                         os.path.join(root, "scripts"))
        self.assertEqual(pinned.cache_dir, os.path.join(root, "cache"))
        self.assertEqual(pinned.media_dir,
                         os.path.join(root, "cache", "media"))
        self.assertEqual(pinned.machines_dir,
                         os.path.join(root, "cache", "machines"))

    def test_an_explicit_slot_wins_over_derivation(self):
        pinned = home.pinned(home.Context(
            home_dir=os.path.join("some", "home"),
            cache_dir=os.path.join("fast", "disk")))
        fast = os.path.abspath(os.path.join("fast", "disk"))
        self.assertEqual(pinned.cache_dir, fast)
        self.assertEqual(pinned.media_dir, os.path.join(fast, "media"))

    def test_what_the_record_cannot_derive_stays_none(self):
        pinned = home.pinned(home.Context(
            cache_dir=os.path.join("only", "cache")))
        self.assertIsNone(pinned.home_dir)
        self.assertIsNone(pinned.blueprints_dir)
        self.assertEqual(
            pinned.media_dir,
            os.path.join(os.path.abspath(os.path.join("only", "cache")),
                         "media"))

    def test_the_properties_file_rides_along(self):
        pinned = home.pinned(home.Context(
            home_dir=os.path.join("some", "home"),
            properties_file=os.path.join("some", "project.properties")))
        self.assertEqual(
            pinned.properties_file,
            os.path.abspath(os.path.join("some", "project.properties")))


class NoSeedingAxisTests(unittest.TestCase):
    """There is no seeding axis at all: a miss is a miss (D88).

    The knob these tests used to exercise is deleted rather than
    defaulted, so what is left to assert is its absence — a context
    carries the working directories and the selected properties file
    (P26's cargo) and nothing that decides where a name may come
    from.
    """

    def test_the_record_carries_no_seeding_slot(self):
        self.assertEqual(
            ("home_dir", "blueprints_dir", "scripts_dir", "cache_dir",
             "media_dir", "machines_dir", "properties_file"),
            home.Context.__slots__)

    def test_no_seeding_switch_survives(self):
        for gone in ("autoseed", "set_autoseed", "_autoseed"):
            self.assertFalse(hasattr(home, gone), gone)


class NoGlobalsTests(unittest.TestCase):
    """The carrier mechanism P26 retired is gone, not dormant.

    The directory globals, their setters, the environment adoption
    and the assignment probe were deleted with the surface move; a
    survivor here would be a second carrier waiting to disagree with
    the record.
    """

    def test_the_global_machinery_is_deleted(self):
        for gone in ("_globals", "_assign", "set_home_dir",
                     "set_blueprints_dir", "set_scripts_dir",
                     "set_cache_dir", "set_media_dir",
                     "set_machines_dir", "is_assigned",
                     "adopt_environment"):
            self.assertFalse(hasattr(home, gone), gone)


class DefaultHomeTests(unittest.TestCase):
    """The value the CLI assigns when the caller named no home."""

    def test_default_home_is_named_reliquary(self):
        self.assertEqual(os.path.basename(home.default_home_dir()),
                         "reliquary")

    def test_default_home_is_absolute(self):
        self.assertTrue(os.path.isabs(home.default_home_dir()))


if __name__ == "__main__":
    unittest.main()
