# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Built-in library seeding for the composed blueprint model.

Media are components inside the blueprint ``.rlqb`` now, so seeding a
blueprint brings its media along inside the same file — there is no
separate media definition to copy out, and no ``seed_media`` verb
(DECISIONS.md D30).
"""

import contextlib
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
from reliquary.errors import PreflightError, StaticError
from reliquary.library import (codex_blueprint_available, list_codex,
                               list_builtin_blueprints, seed_blueprint,
                               seed_script)
from reliquary.machines import (check_variable_key, create_machine,
                                load_machine_state)
from reliquary.script_parser import load_script
from reliquary.resolve import load_namespace, resolve_media
from tests import fake_backend

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
    """A scratch home the codex can be seeded into.

    These are the codex's own tests — seeding, the closure, the
    never-overwrite rule — and every one of them asks for what it
    wants by name, seeding being the only way the library reaches a
    tree (D88).
    """

    def setUp(self):
        home_mod = importlib.import_module("reliquary.home")
        saved = dict(home_mod._globals)
        self.addCleanup(home_mod._globals.update, saved)
        for name in home_mod.DIRECTORIES:
            home_mod._globals[name] = None
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.home = self._temp.name
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        self.backend = stack.enter_context(fake_backend.installed())

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


class ListCodexTest(_HomeTest):
    """The library's own listing, and the only verb that reads it."""

    def test_it_lists_the_shipped_blueprints_with_descriptions(self):
        rows = list_codex()
        row = next(r for r in rows if r["name"] == BLUEPRINT)
        self.assertIn("FreeDOS", row["description"])
        self.assertEqual([r["name"] for r in rows],
                         sorted(r["name"] for r in rows))

    def test_it_reports_nothing_of_yours(self):
        """No provenance, no tiers: the command *is* the provenance."""
        bp_dir = os.path.join(self.home, "blueprints")
        os.makedirs(bp_dir)
        with open(os.path.join(bp_dir, "mine.rlqb"), "w",
                  encoding="utf-8") as handle:
            json.dump([{"type": "machine", "name": "custom-rig",
                        "platform": "dos",
                        "description": "bespoke widget rig",
                        "drives": {"cdrom0": None}}], handle)
        names = [row["name"] for row in list_codex()]
        self.assertNotIn("custom-rig", names)
        self.assertIn(BLUEPRINT, names)

    def test_seeding_does_not_change_what_it_reports(self):
        before = list_codex()
        seed_blueprint(BLUEPRINT, context=self.home, only=True)
        self.assertEqual(before, list_codex())

    def test_availability_is_a_question_that_reads_nothing(self):
        self.assertTrue(codex_blueprint_available(BLUEPRINT))
        self.assertFalse(codex_blueprint_available("zzzznomatch"))
        self.assertFalse(os.path.exists(self._path("blueprints")))


class FirstReferenceTest(_HomeTest):
    def test_media_travels_with_a_seeded_blueprint(self):
        seed_blueprint(BLUEPRINT, context=self.home)
        self.assertIn(MEDIA, load_namespace(self.home).media)

    def test_resolve_media_unknown_name_errors(self):
        with self.assertRaises(PreflightError):
            resolve_media("no-such-media", load_namespace(self.home))

    def test_create_machine_honors_edits_to_the_seeded_copy(self):
        """The copy is yours, and a create reads it rather than the codex.

        This used to assert that `create_machine` seeded on first
        reference. It does not (D88): the seed is the user's own step,
        and what survives — the point the test was always making — is
        that an edit to the copy reaches the next machine while the one
        already built keeps what it was built from.
        """
        seed_blueprint(BLUEPRINT, context=self.home)
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

    def test_an_unseeded_codex_name_is_refused_with_the_fix(self):
        """A name the library holds and your tree does not.

        The interesting refusal, and the one a first-time user meets:
        it must name the command that resolves it, or the deleted
        fallback reads as the tool not knowing about `freedos` at all.
        """
        with self.assertRaises(PreflightError) as caught:
            create_machine(BLUEPRINT, context=self.home)
        self.assertIn(f"rlq seed-blueprint {BLUEPRINT}",
                      str(caught.exception))


class CodexReadinessExampleTests(_HomeTest):
    """The readiness example, and the property that makes it one (T9).

    Every other codex script ends with the guest powered off, because
    each has finished with it. A readiness example has the opposite
    job — it hands a *live* machine to whatever comes next — and that
    is the whole reason it exists, so it is what these guard. A
    plausible example that quietly powered the machine off would
    demonstrate nothing the other two do not.

    Whether it *works* is the integration test's to prove (P18: a
    codex example that does not is a defect). These are its shape.
    """

    LABEL = "ready"
    STEM = "freedos-ready"

    def _path(self):
        seed_blueprint(BLUEPRINT, context=self.home)
        return os.path.join(self.home, "scripts", f"{self.STEM}.rlqs")

    def _script(self):
        return load_script(self._path())

    def _text(self):
        with open(self._path(), encoding="utf-8") as handle:
            return handle.read()

    def test_the_blueprint_names_it_and_seeding_brings_it(self):
        """Wired, not merely shipped: a file nothing names is inert."""
        seed_blueprint(BLUEPRINT, context=self.home)
        component = load_namespace(self.home).machines[BLUEPRINT]
        self.assertEqual(component.scripts[self.LABEL], self.STEM)
        self.assertTrue(os.path.isfile(os.path.join(
            self.home, "scripts", f"{self.STEM}.rlqs")))

    def test_it_leaves_the_machine_running(self):
        script = self._script()
        verbs = [statement.verb for statement in script.statements]
        self.assertIn("start", verbs)
        self.assertNotIn("stop", verbs)
        # The codex's own idiom for "and now it is off" — waiting the
        # machine down after a poweroff — is what this example must
        # not do, and what `freedos-verify` does.
        self.assertNotIn("machine=stopped", self._text())

    def test_the_promise_is_the_last_step(self):
        """Set only once everything it promises has held."""
        last = self._script().statements[-1]
        self.assertEqual(last.verb, "set")
        self.assertEqual(last.arguments[0], self.LABEL)

    def test_the_variable_is_outside_the_reserved_namespaces(self):
        """`rlq.ready` would be a static error, not a nicer spelling.

        The reserved namespaces are reliquary's own (V5), which is why
        the example's key is plain — and why a reader copying it gets
        something that parses.
        """
        check_variable_key(self._script().statements[-1].arguments[0])
        with self.assertRaises(StaticError):
            check_variable_key("rlq.ready")


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

    def test_every_codex_blueprint_is_indexed(self):
        # The reverse of test_builtin_blueprint_index_names_existing_files:
        # that one catches an index entry with no file, this one a file
        # with no entry, which `list-codex` would skip silently.
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
    def test_the_spec_tabulates_no_provenance_vocabulary(self):
        """No column means no vocabulary for one may be specified.

        Its predecessor read the spec's provenance table and asserted
        the emitted words against it, catching a real divergence. The
        successor guards the other direction: with the sets unmixed
        there is nothing to report (D88), so a table describing a
        column would be a norm the code cannot honor. The *word* may
        still appear — the spec uses it to say the command is the
        provenance — which is why this looks for the table and for the
        values, not for the noun.
        """
        with open(_CODEX_SPEC, encoding="utf-8") as handle:
            text = handle.read()
        self.assertNotIn("| PROVENANCE |", text.upper())
        for value in ("| `yes` |", "| `seeded` |", "| `user` |"):
            self.assertNotIn(value, text)
        emitted = set(list_codex()[0])
        self.assertEqual(
            emitted, {"name", "description"},
            "list_codex returns a field the spec does not describe; the "
            "record is the --json contract.")


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
