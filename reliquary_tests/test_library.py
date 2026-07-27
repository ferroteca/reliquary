# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Built-in library seeding for the composed blueprint model.

Media are components inside the blueprint ``.rlqb`` now, so seeding a
blueprint brings its media along inside the same file — there is no
separate media definition to copy out, and no ``seed_media`` verb
(DECISIONS.md D30).
"""

import importlib
import json
import os
import re
import shutil
import tempfile
import unittest
from unittest import mock

import reliquary
from reliquary import document, jsonc
from reliquary.errors import PreflightError
from reliquary.library import (list_builtin_blueprints, search_blueprints,
                               seed_blueprint, seed_script)
from reliquary.machines import create_machine, load_machine_state
from reliquary.resolve import load_namespace, resolve_media

BLUEPRINT = "freedos"
MEDIA = "freedos-livecd"
SCRIPTS = ("freedos-install", "freedos-verify")
OPENBSD_BLUEPRINT = "openbsd"
OPENBSD_MEDIA = "openbsd-installer"
OPENBSD_SCRIPT = "openbsd-install"
EXT = ".rlqb"
_CODEX_SPEC = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(reliquary.__file__))),
    "docs", "spec", "codex.md")


class _HomeTest(unittest.TestCase):
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


class SeedingTest(_HomeTest):
    def test_seed_blueprint_copies_closure(self):
        """Seeding a blueprint brings its scripts along; media ride the
        blueprint file itself."""
        self.assertTrue(seed_blueprint(BLUEPRINT, context=self.home))
        blueprint_path = self._path("blueprints", f"{BLUEPRINT}{EXT}")
        self.assertTrue(os.path.isfile(blueprint_path))
        for stem in SCRIPTS:
            self.assertTrue(os.path.isfile(self._path("scripts", f"{stem}.rlqs")))
        # The media travels inside the seeded blueprint.
        doc = document.load_document(blueprint_path)
        self.assertIn(MEDIA, doc.media)

    def test_seed_blueprint_only_skips_closure(self):
        self.assertTrue(seed_blueprint(BLUEPRINT, context=self.home, only=True))
        self.assertTrue(os.path.isfile(self._path("blueprints", f"{BLUEPRINT}{EXT}")))
        self.assertFalse(os.path.isdir(self._path("scripts")))

    def test_second_seed_leaves_user_files_alone(self):
        seed_blueprint(BLUEPRINT, context=self.home)
        # Remove the blueprint so re-seeding runs the closure again; the
        # user-edited script it references must not be overwritten.
        os.remove(self._path("blueprints", f"{BLUEPRINT}{EXT}"))
        script_path = self._path("scripts", f"{SCRIPTS[0]}.rlqs")
        with open(script_path, "w", encoding="utf-8") as handle:
            handle.write("user edit")
        self.assertTrue(seed_blueprint(BLUEPRINT, context=self.home))
        with open(script_path, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "user edit")

    def test_existing_home_blueprint_is_untouched(self):
        for ext in (".json", EXT):
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
                self.assertFalse(os.path.exists(self._path("scripts")))

    def test_unknown_names_seed_nothing(self):
        self.assertFalse(seed_blueprint("no-such", context=self.home))
        self.assertFalse(seed_script("no-such", context=self.home))
        self.assertFalse(os.path.exists(self._path("blueprints")))
        self.assertFalse(os.path.exists(self._path("scripts")))

    def test_seed_script_copies_once(self):
        self.assertTrue(seed_script(SCRIPTS[0], context=self.home))
        self.assertFalse(seed_script(SCRIPTS[0], context=self.home))


class SearchBlueprintsTest(_HomeTest):
    def test_codex_blueprint_is_available(self):
        rows = search_blueprints("freedos", context=self.home)
        row = next(r for r in rows if r["name"] == BLUEPRINT)
        self.assertEqual(row["provenance"], "yes")
        self.assertEqual(row["platform"], "dos")
        self.assertIsNone(row["path"])

    def test_seeded_blueprint_reports_seeded_provenance(self):
        seed_blueprint(BLUEPRINT, context=self.home, only=True)
        row = next(r for r in search_blueprints(BLUEPRINT, context=self.home)
                   if r["name"] == BLUEPRINT)
        self.assertEqual(row["provenance"], "seeded")
        self.assertIsNotNone(row["path"])

    def test_user_blueprint_matches_by_description(self):
        bp_dir = os.path.join(self.home, "blueprints")
        os.makedirs(bp_dir)
        with open(os.path.join(bp_dir, "mine.rlqb"), "w",
                  encoding="utf-8") as handle:
            json.dump([{"type": "machine", "name": "custom-rig",
                        "platform": "dos",
                        "description": "bespoke widget rig",
                        "drives": {"cdrom0": None}}], handle)
        rows = search_blueprints("bespoke", context=self.home)
        self.assertEqual([r["name"] for r in rows], ["custom-rig"])
        self.assertEqual(rows[0]["provenance"], "user")
        self.assertEqual(rows[0]["description"], "bespoke widget rig")

    def test_empty_term_matches_all(self):
        self.assertGreaterEqual(
            len(search_blueprints("", context=self.home)), 2)

    def test_no_match_returns_empty(self):
        self.assertEqual(
            search_blueprints("zzzznomatch", context=self.home), [])


class FirstReferenceTest(_HomeTest):
    def test_media_travels_with_a_seeded_blueprint(self):
        seed_blueprint(BLUEPRINT, context=self.home)
        self.assertIn(MEDIA, load_namespace(self.home).media)

    def test_resolve_media_unknown_name_errors(self):
        with self.assertRaises(PreflightError):
            resolve_media("no-such-media", load_namespace(self.home))

    def test_create_machine_seeds_and_honors_edits(self):
        with mock.patch("reliquary.machines.create_hdd_image"):
            machine_id = create_machine(BLUEPRINT, context=self.home)
            blueprint_path = os.path.join(
                self.home, "blueprints", f"{BLUEPRINT}{EXT}")
            self.assertTrue(os.path.isfile(blueprint_path))
            with open(blueprint_path, encoding="utf-8") as handle:
                data = jsonc.load(handle)
            machine = next(spec for spec in data
                           if spec.get("type") == "machine")
            machine["memory"] = 64
            with open(blueprint_path, "w", encoding="utf-8") as handle:
                json.dump(data, handle)
            second_id = create_machine(BLUEPRINT, context=self.home)
        self.assertEqual(
            load_machine_state(machine_id, context=self.home)["memory"], 32)
        self.assertEqual(
            load_machine_state(second_id, context=self.home)["memory"], 64)

    def test_create_machine_unknown_name_errors(self):
        with self.assertRaises(PreflightError):
            create_machine("no-such-blueprint", context=self.home)


class CodexMediaTests(unittest.TestCase):
    """The shipped codex blueprints carry the pinned media hashes."""

    @classmethod
    def _codex_doc(cls, name):
        path = os.path.join(os.path.dirname(reliquary.__file__),
                            "codex", "blueprints", f"{name}.rlqb")
        return document.load_document(path)

    def test_freedos_livecd_media_pins_the_iso_hash(self):
        media = self._codex_doc(BLUEPRINT).media[MEDIA]
        self.assertEqual(
            media.sha256,
            "c48a9dcf4b8e22f44e268a9879745f0bd88c061195ac584e"
            "6ef2deb0477f81fb")

    def test_openbsd_install_media_pins_the_iso(self):
        media = self._codex_doc(OPENBSD_BLUEPRINT).media[OPENBSD_MEDIA]
        self.assertEqual(media.location[0].kind, "url")
        self.assertEqual(
            media.sha256,
            "7a4a92e953618035097c796a90b54424a0f3ae775552e1e7d102"
            "cf8a5130449f")


class CodexSpecConformanceTests(_HomeTest):
    """The codex against docs/spec/codex.md.

    P24's inventory pass over the codex. Its checkable claims are
    the index (a set the spec scopes and the tree fills) and the
    provenance vocabulary (a closed table the `--json` form of
    `search-blueprints` emits). The tests above assert each
    provenance value one at a time, which is the pattern P24
    names: they would all still pass if the spec said something
    else entirely, because none of them reads it.

    The banner was the gate, and it was wrong: it called
    `search-`, `seed-` and the provenance column "still planned"
    while all three shipped, so by the banner-is-the-marker rule
    those sections were not claims and nothing could be tested
    against them. Corrected 2026-07-27, which is what let the
    provenance divergence below become visible: the spec's table
    was headed `CODEX` and gave a **blank** third value where the
    code emits the word `user`, so a consumer switching on the
    field would have matched nothing.
    """

    @staticmethod
    def _codex_root():
        return os.path.join(os.path.dirname(reliquary.__file__), "codex")

    @classmethod
    def _index(cls):
        with open(os.path.join(cls._codex_root(), "codex.json"),
                  encoding="utf-8") as handle:
            return jsonc.loads(handle.read())

    @staticmethod
    def _specified_provenance():
        """The words the spec's provenance table admits."""
        with open(_CODEX_SPEC, encoding="utf-8") as handle:
            text = handle.read()
        start = text.index("| PROVENANCE | meaning |")
        words = set()
        for line in text[start:].splitlines()[2:]:
            if not line.startswith("|"):
                break
            words.update(re.findall(r"`([^`]+)`", line.split("|")[1]))
        return words

    def test_every_codex_blueprint_is_indexed(self):
        # The reverse of test_builtin_blueprint_index_names_existing_files:
        # that one catches an index entry with no file, this one a file
        # with no entry, which `--builtin` listings would skip silently.
        root = os.path.join(self._codex_root(), "blueprints")
        shipped = {name[:-len(EXT)] for name in os.listdir(root)
                   if name.endswith(EXT)}
        self.assertEqual(
            sorted(shipped - set(self._index()["blueprints"])), [],
            "these codex blueprints ship with no codex.json entry; "
            "list_builtin_blueprints reads that index, so an unindexed "
            "blueprint is invisible wherever the fallback scan is not "
            "reached.")

    def test_the_index_carries_only_the_blocks_that_ship(self):
        # Trimmed 2026-07-27: a `media` block listing 2 of the 4 media
        # the codex blueprints declare, read by nothing. Media are
        # components inside a blueprint (D30) and are derived from it.
        self.assertEqual(
            sorted(self._index()), ["blueprints", "version"],
            "codex.json carries a block the code does not read. The "
            "banner scopes the index to blueprint names and "
            "descriptions; widening it means widening that first.")

    @unittest.skipUnless(os.path.isfile(_CODEX_SPEC),
                         "the codex spec is source-tree only")
    def test_the_provenance_vocabulary_is_the_specified_one(self):
        seed_blueprint(BLUEPRINT, context=self.home, only=True)
        bp_dir = os.path.join(self.home, "blueprints")
        with open(os.path.join(bp_dir, "mine.rlqb"), "w",
                  encoding="utf-8") as handle:
            json.dump([{"type": "machine", "name": "mine",
                        "platform": "dos", "drives": {"cdrom0": None}}],
                      handle)
        emitted = {row["provenance"]
                   for row in search_blueprints("", context=self.home)}
        self.assertEqual(
            emitted, self._specified_provenance(),
            "the provenance words search reports are not the ones "
            "docs/spec/codex.md tabulates. The column is part of the "
            "--json return, so its vocabulary is a machine contract.")


class BuiltinCodexTests(unittest.TestCase):
    def test_builtin_blueprint_index_names_existing_files(self):
        root = os.path.join(os.path.dirname(reliquary.__file__), "codex")
        for name in list_builtin_blueprints():
            self.assertTrue(os.path.isfile(
                os.path.join(root, "blueprints", f"{name}{EXT}")))

    def test_openbsd_blueprint_seed_copies_closure(self):
        with tempfile.TemporaryDirectory() as home:
            self.assertTrue(seed_blueprint(OPENBSD_BLUEPRINT, context=home))
            self.assertTrue(os.path.isfile(os.path.join(
                home, "blueprints", f"{OPENBSD_BLUEPRINT}{EXT}")))
            self.assertTrue(os.path.isfile(os.path.join(
                home, "scripts", f"{OPENBSD_SCRIPT}.rlqs")))


if __name__ == "__main__":
    unittest.main()
