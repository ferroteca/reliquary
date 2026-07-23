# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Built-in library seeding: copy-out on first reference."""

import json
import importlib
import os
import shutil
import tempfile
import unittest
from unittest import mock

import reliquary
from reliquary.library import seed_blueprint, seed_media, seed_script
from reliquary.machines import (create_machine,
                                load_machine_state)
from reliquary.media import parse_definition, resolve_media

BLUEPRINT = "freedos-1.4-plain"
MEDIA = "freedos-1.4-livecd"
SCRIPTS = ("freedos-1.4-plain-install", "freedos-1.4-verify")
OPENBSD_BLUEPRINT = "openbsd-7.9-amd64"
OPENBSD_MEDIA = "openbsd-7.9-amd64-install"
OPENBSD_SCRIPT = "openbsd-7.9-install"

BLUEPRINT_EXT = ".rlqb"
MEDIA_EXT = ".rlqm"


class SeedingTest(unittest.TestCase):
    """seed_blueprint / seed_media / seed_script behavior."""

    def setUp(self):
        home_mod = importlib.import_module("reliquary.home")
        saved = home_mod._home
        self.addCleanup(setattr, home_mod, "_home", saved)
        home_mod._home = None
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.home = self._temp.name

    def _path(self, *parts):
        return os.path.join(self.home, *parts)

    def test_seed_blueprint_copies_closure(self):
        """Seeding a blueprint brings its media and scripts along."""
        self.assertTrue(seed_blueprint(BLUEPRINT, context=self.home))
        self.assertTrue(os.path.isfile(
            self._path("blueprints", f"{BLUEPRINT}{BLUEPRINT_EXT}")))
        self.assertTrue(os.path.isfile(
            self._path("media", f"{MEDIA}{MEDIA_EXT}")))
        for stem in SCRIPTS:
            self.assertTrue(os.path.isfile(
                self._path("scripts", f"{stem}.rlqs")))

    def test_second_seed_leaves_user_files_alone(self):
        """A seeded file that the user edited is never overwritten."""
        seed_blueprint(BLUEPRINT, context=self.home)
        blueprint_path = self._path("blueprints", f"{BLUEPRINT}{BLUEPRINT_EXT}")
        media_path = self._path("media", f"{MEDIA}{MEDIA_EXT}")
        with open(blueprint_path, "w", encoding="utf-8") as handle:
            handle.write("user edit")
        os.remove(blueprint_path)
        with open(media_path, "w", encoding="utf-8") as handle:
            handle.write("user media")
        self.assertTrue(seed_blueprint(BLUEPRINT, context=self.home))
        with open(media_path, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "user media")

    def test_existing_home_blueprint_is_untouched(self):
        """A present home blueprint suppresses seeding entirely."""
        for ext in [".json", BLUEPRINT_EXT]:
            with self.subTest(ext=ext):
                shutil.rmtree(self.home)
                os.makedirs(self.home)
                blueprint_path = self._path("blueprints", f"{BLUEPRINT}{ext}")
                os.makedirs(os.path.dirname(blueprint_path))
                with open(blueprint_path, "w", encoding="utf-8") as handle:
                    handle.write("mine")
                self.assertFalse(seed_blueprint(BLUEPRINT, context=self.home))
                with open(blueprint_path, encoding="utf-8") as handle:
                    self.assertEqual(handle.read(), "mine")
                self.assertFalse(os.path.exists(self._path("media")))
                self.assertFalse(os.path.exists(self._path("scripts")))

    def test_seed_media_skips_home_definition_of_same_name(self):
        """A home definition supplying the item name wins."""
        media_root = self._path("media")
        os.makedirs(media_root)
        definition = {
            "name": MEDIA, "file": "mine.iso",
            "sha256": "0" * 64,
        }
        for ext in [".json", MEDIA_EXT]:
            with self.subTest(ext=ext):
                shutil.rmtree(media_root)
                os.makedirs(media_root)
                with open(os.path.join(media_root, f"mine{ext}"), "w",
                          encoding="utf-8") as handle:
                    json.dump(definition, handle)
                self.assertFalse(seed_media(MEDIA, context=self.home))
                self.assertFalse(os.path.exists(
                    os.path.join(media_root, f"{MEDIA}{MEDIA_EXT}")))

    def test_unknown_names_seed_nothing(self):
        self.assertFalse(seed_blueprint("no-such", context=self.home))
        self.assertFalse(seed_media("no-such", context=self.home))
        self.assertFalse(seed_script("no-such", context=self.home))
        self.assertFalse(os.path.exists(self._path("blueprints")))
        self.assertFalse(os.path.exists(self._path("media")))
        self.assertFalse(os.path.exists(self._path("scripts")))

    def test_seed_script_copies_once(self):
        self.assertTrue(seed_script(SCRIPTS[0], context=self.home))
        self.assertFalse(seed_script(SCRIPTS[0], context=self.home))

    def test_seed_script_brings_its_referenced_media(self):
        """`insert cdrom0 @name` seeds the definition it names."""
        self.assertTrue(seed_script(SCRIPTS[0], context=self.home))
        self.assertTrue(os.path.isfile(
            self._path("media", f"{MEDIA}{MEDIA_EXT}")))

    def test_seed_script_brings_its_referenced_openbsd_media(self):
        """The OpenBSD script seeds the ISO its install inserts."""
        self.assertTrue(seed_script(OPENBSD_SCRIPT, context=self.home))
        self.assertTrue(os.path.isfile(
            self._path("scripts", f"{OPENBSD_SCRIPT}.rlqs")))
        self.assertTrue(os.path.isfile(
            self._path("media", f"{OPENBSD_MEDIA}{MEDIA_EXT}")))


class FirstReferenceTest(unittest.TestCase):
    """Implicit seeding through the resolution seams."""

    def setUp(self):
        home_mod = importlib.import_module("reliquary.home")
        saved = home_mod._home
        self.addCleanup(setattr, home_mod, "_home", saved)
        home_mod._home = None
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.home = self._temp.name

    def test_resolve_media_seeds_builtin_definition(self):
        resolved = resolve_media(MEDIA, context=self.home)
        self.assertEqual(resolved.item.file, "FD14LIVE.iso")
        self.assertTrue(os.path.isfile(
            os.path.join(self.home, "media", f"{MEDIA}{MEDIA_EXT}")))

    def test_resolve_media_unknown_name_still_errors(self):
        with self.assertRaises(FileNotFoundError):
            resolve_media("no-such-media", context=self.home)

    def test_create_machine_seeds_and_honors_edits(self):
        """create seeds once; a user edit governs later creates."""
        with mock.patch("reliquary.machines.create_hdd_image"), \
                mock.patch("reliquary.machines.fetch_media",
                           return_value="payload.iso"):
            machine_id = create_machine(BLUEPRINT,
                                               context=self.home)
            # It should have seeded as .rlqb because codex has it.
            blueprint_path = os.path.join(
                self.home, "blueprints", f"{BLUEPRINT}{BLUEPRINT_EXT}")

            self.assertTrue(
                os.path.isfile(blueprint_path),
                f"Blueprint should have been seeded at {blueprint_path}")
            with open(blueprint_path, encoding="utf-8") as handle:
                from reliquary import jsonc
                data = jsonc.load(handle)
            data["memory"] = 64
            with open(blueprint_path, "w",
                      encoding="utf-8") as handle:
                json.dump(data, handle)
            second_id = create_machine(BLUEPRINT,
                                              context=self.home)
        first = load_machine_state(machine_id, context=self.home)
        second = load_machine_state(second_id, context=self.home)
        self.assertEqual(first["memory"], 32)
        self.assertEqual(second["memory"], 64)

    def test_create_machine_unknown_name_errors(self):
        with self.assertRaises(FileNotFoundError):
            create_machine("no-such-blueprint", context=self.home)


class BuiltinMediaDefinitionTests(unittest.TestCase):
    """The shipped freedos-1.4-livecd definition carries correct content."""

    @classmethod
    def setUpClass(cls):
        path = os.path.join(
            os.path.dirname(reliquary.__file__),
            "codex", "media", f"{MEDIA}{MEDIA_EXT}")
        from reliquary import jsonc
        with open(path, encoding="utf-8") as handle:
            cls._raw = jsonc.load(handle)
        cls._parsed = parse_definition(cls._raw)

    def test_url_carrying_definition_has_redistribution_assertion(self):
        """Built-in definitions with a URL must assert redistribution rights."""
        self.assertIn("url", self._raw)
        self.assertIn("redistribution", self._raw)
        self.assertIsInstance(self._raw["redistribution"], str)
        self.assertTrue(self._raw["redistribution"].strip())

    def test_livecd_item_identifies_correct_file(self):
        self.assertEqual(self._parsed.items[0].name, "freedos-1.4-livecd")
        self.assertEqual(self._parsed.items[0].file, "FD14LIVE.iso")

    def test_iso_sha256_matches_known_good_hash(self):
        """The ISO hash is the known-good FreeDOS 1.4 LiveCD payload hash."""
        self.assertEqual(
            self._parsed.items[0].sha256,
            "c48a9dcf4b8e22f44e268a9879745f0bd88c061195ac584e"
            "6ef2deb0477f81fb")


class BuiltinOpenBsdDefinitionTests(unittest.TestCase):
    """The shipped OpenBSD 7.9 definition pins the official ISO."""

    @classmethod
    def setUpClass(cls):
        path = os.path.join(
            os.path.dirname(reliquary.__file__),
            "codex", "media", f"{OPENBSD_MEDIA}{MEDIA_EXT}")
        from reliquary import jsonc
        with open(path, encoding="utf-8") as handle:
            cls._raw = jsonc.load(handle)
        cls._parsed = parse_definition(cls._raw)

    def test_url_carrying_definition_has_redistribution_assertion(self):
        self.assertIn("url", self._raw)
        self.assertIn("redistribution", self._raw)
        self.assertIsInstance(self._raw["redistribution"], str)
        self.assertTrue(self._raw["redistribution"].strip())

    def test_install_iso_item_identifies_correct_file(self):
        self.assertEqual(self._parsed.items[0].name, OPENBSD_MEDIA)
        self.assertEqual(self._parsed.items[0].file, "install79.iso")

    def test_install_iso_sha256_matches_openbsd_7_9_amd64(self):
        self.assertEqual(
            self._parsed.items[0].sha256,
            "7a4a92e953618035097c796a90b54424a0f3ae775552e1e7d102"
            "cf8a5130449f")


class BuiltinCodexTests(unittest.TestCase):
    """The packaged codex index and files agree."""

    def test_builtin_blueprint_index_names_existing_blueprint_files(self):
        from reliquary.library import list_builtin_blueprints

        root = os.path.join(os.path.dirname(reliquary.__file__), "codex")
        for name in list_builtin_blueprints():
            self.assertTrue(os.path.isfile(
                os.path.join(root, "blueprints", f"{name}{BLUEPRINT_EXT}")))

    def test_openbsd_blueprint_seed_copies_closure(self):
        with tempfile.TemporaryDirectory() as home:
            self.assertTrue(seed_blueprint(OPENBSD_BLUEPRINT, context=home))
            self.assertTrue(os.path.isfile(os.path.join(
                home, "blueprints", f"{OPENBSD_BLUEPRINT}{BLUEPRINT_EXT}")))
            self.assertTrue(os.path.isfile(os.path.join(
                home, "scripts", f"{OPENBSD_SCRIPT}.rlqs")))
            self.assertTrue(os.path.isfile(os.path.join(
                home, "media", f"{OPENBSD_MEDIA}{MEDIA_EXT}")))


if __name__ == "__main__":
    unittest.main()
