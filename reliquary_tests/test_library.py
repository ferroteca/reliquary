# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Built-in library seeding: copy-out on first reference."""

import json
import os
import tempfile
import unittest
from unittest import mock

from reliquary.library import seed_blueprint, seed_media, seed_script
from reliquary.machines import (create_from_blueprint,
                                load_machine_state)
from reliquary.media import resolve_media

BLUEPRINT = "freedos-1.4-plain"
MEDIA = "freedos-1.4-livecd"
SCRIPTS = ("freedos-1.4-plain-install", "freedos-1.4-plain-verify")


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
                self._path("scripts", f"{stem}.rqs")))

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


if __name__ == "__main__":
    unittest.main()
