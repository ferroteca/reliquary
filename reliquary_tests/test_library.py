# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Built-in library seeding: copy-out on first reference."""

import json
import os
import tempfile
import unittest
from unittest import mock

import reliquary
from reliquary.library import seed_blueprint, seed_media, seed_script
from reliquary.machines import (create_from_blueprint,
                                load_machine_state)
from reliquary.media import parse_definition, resolve_media

BLUEPRINT = "freedos-1.4-plain"
MEDIA = "freedos-1.4-livecd"
SCRIPTS = ("freedos-1.4-plain-install", "freedos-1.4-verify")


class SeedingTest(unittest.TestCase):
    """seed_blueprint / seed_media / seed_script behavior."""

    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.home = self._temp.name

    def _path(self, *parts):
        return os.path.join(self.home, *parts)

    def test_seed_blueprint_copies_closure(self):
        """Seeding a blueprint brings its media and scripts along."""
        self.assertTrue(seed_blueprint(BLUEPRINT, home=self.home))
        self.assertTrue(os.path.isfile(
            self._path("blueprints", f"{BLUEPRINT}.json")))
        self.assertTrue(os.path.isfile(
            self._path("media", f"{MEDIA}.json")))
        for stem in SCRIPTS:
            self.assertTrue(os.path.isfile(
                self._path("scripts", f"{stem}.rlqs")))

    def test_second_seed_leaves_user_files_alone(self):
        """A seeded file that the user edited is never overwritten."""
        seed_blueprint(BLUEPRINT, home=self.home)
        blueprint_path = self._path("blueprints", f"{BLUEPRINT}.json")
        media_path = self._path("media", f"{MEDIA}.json")
        with open(blueprint_path, "w", encoding="utf-8") as handle:
            handle.write("user edit")
        os.remove(blueprint_path)
        with open(media_path, "w", encoding="utf-8") as handle:
            handle.write("user media")
        self.assertTrue(seed_blueprint(BLUEPRINT, home=self.home))
        with open(media_path, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "user media")

    def test_existing_home_blueprint_is_untouched(self):
        """A present home blueprint suppresses seeding entirely."""
        blueprint_path = self._path("blueprints", f"{BLUEPRINT}.json")
        os.makedirs(os.path.dirname(blueprint_path))
        with open(blueprint_path, "w", encoding="utf-8") as handle:
            handle.write("mine")
        self.assertFalse(seed_blueprint(BLUEPRINT, home=self.home))
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
        with open(os.path.join(media_root, "mine.json"), "w",
                  encoding="utf-8") as handle:
            json.dump(definition, handle)
        self.assertFalse(seed_media(MEDIA, home=self.home))
        self.assertFalse(os.path.exists(
            os.path.join(media_root, f"{MEDIA}.json")))

    def test_unknown_names_seed_nothing(self):
        self.assertFalse(seed_blueprint("no-such", home=self.home))
        self.assertFalse(seed_media("no-such", home=self.home))
        self.assertFalse(seed_script("no-such", home=self.home))
        self.assertFalse(os.path.exists(self._path("blueprints")))

    def test_seed_script_copies_once(self):
        self.assertTrue(seed_script(SCRIPTS[0], home=self.home))
        self.assertFalse(seed_script(SCRIPTS[0], home=self.home))

    def test_seed_script_brings_its_referenced_media(self):
        """`insert cdrom0 @name` seeds the definition it names."""
        self.assertTrue(seed_script(SCRIPTS[0], home=self.home))
        self.assertTrue(os.path.isfile(
            self._path("media", f"{MEDIA}.json")))


class FirstReferenceTest(unittest.TestCase):
    """Implicit seeding through the resolution seams."""

    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.home = self._temp.name

    def test_resolve_media_seeds_builtin_definition(self):
        resolved = resolve_media(MEDIA, home=self.home)
        self.assertEqual(resolved.item.file, "FD14LIVE.iso")
        self.assertTrue(os.path.isfile(
            os.path.join(self.home, "media", f"{MEDIA}.json")))

    def test_resolve_media_unknown_name_still_errors(self):
        with self.assertRaises(FileNotFoundError):
            resolve_media("no-such-media", home=self.home)

    def test_create_from_blueprint_seeds_and_honors_edits(self):
        """create seeds once; a user edit governs later creates."""
        with mock.patch("reliquary.machines.create_hdd_image"), \
                mock.patch("reliquary.machines.fetch_media",
                           return_value="payload.iso"):
            machine_id = create_from_blueprint(BLUEPRINT,
                                               home=self.home)
            blueprint_path = os.path.join(
                self.home, "blueprints", f"{BLUEPRINT}.json")
            self.assertTrue(os.path.isfile(blueprint_path))
            with open(blueprint_path, encoding="utf-8") as handle:
                data = json.load(handle)
            data["memory"] = 64
            with open(blueprint_path, "w",
                      encoding="utf-8") as handle:
                json.dump(data, handle)
            second_id = create_from_blueprint(BLUEPRINT,
                                              home=self.home)
        first = load_machine_state(machine_id, home=self.home)
        second = load_machine_state(second_id, home=self.home)
        self.assertEqual(first["memory"], 32)
        self.assertEqual(second["memory"], 64)

    def test_create_from_blueprint_unknown_name_errors(self):
        with self.assertRaises(FileNotFoundError):
            create_from_blueprint("no-such-blueprint", home=self.home)


class BuiltinMediaDefinitionTests(unittest.TestCase):
    """The shipped freedos-1.4-livecd definition carries correct content."""

    @classmethod
    def setUpClass(cls):
        path = os.path.join(
            os.path.dirname(reliquary.__file__),
            "builtins", "media", "freedos-1.4-livecd.json")
        with open(path, encoding="utf-8") as handle:
            cls._raw = json.load(handle)
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


if __name__ == "__main__":
    unittest.main()
