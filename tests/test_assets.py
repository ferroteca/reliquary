# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for authored-asset residency: the resolution source seam."""

import contextlib
import importlib
import json
import os
import tempfile
import unittest

import re

import reliquary
from reliquary import Context
from reliquary.assets import (KIND_EXTENSIONS, index_by_name,
                              source_for, stem)
from reliquary.document import parse_document
from reliquary.errors import PreflightError, StaticError
from reliquary.library import list_blueprints, list_codex, locate_blueprint
from reliquary.machines import create_machine, resolve_machine
from reliquary.resolve import load_namespace, resolve_media
from tests import fake_backend

SHA256 = "1" * 64
_SPEC = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "docs", "spec", "asset-resolution.md")


def _write(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(obj, handle)


@unittest.skipUnless(os.path.isfile(_SPEC),
                     "the asset-resolution spec is source-tree only")
class SpecConformanceTests(unittest.TestCase):
    """The asset kinds and home folders the spec names are the real ones.

    P24's inventory pass over asset resolution, and the interface
    where the banner rule paid most directly. This spec carried no
    status banner at all until 2026-07-27 — the one document in
    `docs/spec/` breaking the rule its own directory states, that
    the banner is the marker and shelving proves nothing — and it
    had drifted in six places behind it, including a `.rlqm` media
    kind retired with the composed model and a home `media/`
    folder its own layout diagram did not show.

    Two things are compared. The **kind table** is the extension
    vocabulary a source walks by, which the spec enumerates in
    prose; a kind declared and never requested is the shape of
    defect this sweep has now found four times, so the check runs
    against what the code actually asks for rather than what it
    declares. The **home layout** is a world-facing contract
    (INTERFACES.md), and its folder list is a set on both sides.

    Reserved names are read out of the banner, so a thing that is
    designed but unbuilt stays documented without becoming a claim
    — `.rlql` and `landmarks/` today.
    """

    @staticmethod
    def _spec_text():
        with open(_SPEC, encoding="utf-8") as handle:
            return handle.read()

    @classmethod
    def _reserved(cls):
        """The names the banner marks as designed but not built."""
        text = cls._spec_text()
        banner = text[text.index("> **Status:**"):text.index("\nWhere ")]
        return set(re.findall(r"`([^`]+)`", banner))

    def test_the_kind_table_holds_only_requested_kinds(self):
        # library.py is the only caller; a kind nothing asks for
        # cannot resolve and only advertises that it could.
        requested = set()
        package = os.path.dirname(os.path.abspath(reliquary.__file__))
        for name in sorted(os.listdir(package)):
            if not name.endswith(".py") or name == "assets.py":
                continue
            with open(os.path.join(package, name),
                      encoding="utf-8") as handle:
                requested.update(
                    re.findall(r"candidate_files\(\"([a-z]+)\"\)",
                               handle.read()))
        self.assertEqual(
            sorted(KIND_EXTENSIONS), sorted(requested),
            "KIND_EXTENSIONS declares an asset kind no source is ever "
            "asked for. An unrequested kind cannot resolve, so "
            "declaring it advertises a resolution that cannot happen; "
            "reserve it in docs/spec/asset-resolution.md instead.")

    def test_the_reserved_extensions_are_not_declared(self):
        reserved = {token for token in self._reserved()
                    if token.startswith(".rlq")}
        self.assertTrue(
            reserved, "the banner no longer reserves any extension; "
            "this test reads them from it.")
        declared = {ext for exts in KIND_EXTENSIONS.values()
                    for ext in exts}
        self.assertEqual(
            sorted(reserved & declared), [],
            f"{sorted(reserved & declared)} are reserved by the spec's "
            "banner and declared in KIND_EXTENSIONS. Reserved means "
            "designed and unbuilt; declaring one makes the banner "
            "false.")

    def test_the_home_layout_names_the_folders_the_home_has(self):
        text = self._spec_text()
        block = text[text.index("<reliquary_home>/"):]
        block = block[:block.index("```")]
        # Top level only: nested entries (cache/media, cache/machines)
        # are indented, and belong to the cache, not the home.
        top = set(re.findall(r"^[├└]── ([a-z_.]+)/", block, re.M))
        reserved = {token.rstrip("/") for token in self._reserved()}
        home_mod = importlib.import_module("reliquary.home")
        with tempfile.TemporaryDirectory() as home:
            actual = {
                os.path.basename(home_mod.blueprints_dir(home)),
                os.path.basename(home_mod.scripts_dir(home)),
                os.path.basename(home_mod.cache_dir(home)),
            }
        self.assertEqual(
            sorted(top - reserved), sorted(actual),
            "the spec's home-layout diagram and the folders home.py "
            "resolves disagree. The home layout is a world-facing "
            "contract, so the diagram is the contract's text.")


class AssetSourceTests(unittest.TestCase):
    """Where each kind resolves from, and nothing else.

    One axis, where the asset-root knob answered two questions and the
    autoseed knob that replaced half of it answered the other. The
    directory decides where a name resolves, and a miss is a miss: the
    codex is not a tier behind it (D88).
    """

    def setUp(self):
        self.home_mod = importlib.import_module("reliquary.home")
        saved = dict(self.home_mod._globals)
        self.addCleanup(self.home_mod._globals.update, saved)
        for name in self.home_mod.DIRECTORIES:
            self.home_mod._globals[name] = None
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = self._tmp.name

    def test_an_unassigned_directory_refuses_at_use(self):
        """A bare embedding call with nothing assigned fails closed.

        Building the source never raises — the directories resolve
        lazily — so the refusal lands where the resolution is, naming
        the directory it wanted.
        """
        source = source_for(Context())
        with self.assertRaises(StaticError):
            source.candidate_files("blueprint")

    def test_each_kind_reads_its_own_directory(self):
        blueprints = os.path.join(self.root, "bp")
        scripts = os.path.join(self.root, "sc")
        source = source_for(Context(blueprints_dir=blueprints,
                                    scripts_dir=scripts))
        self.assertEqual(source.describe("blueprint"),
                         os.path.abspath(blueprints))
        self.assertEqual(source.describe("script"),
                         os.path.abspath(scripts))

    def test_a_bare_home_string_derives_both(self):
        home = os.path.join(self.root, "home")
        source = source_for(home)
        self.assertEqual(source.describe("blueprint"),
                         os.path.join(os.path.abspath(home), "blueprints"))
        self.assertEqual(source.describe("script"),
                         os.path.join(os.path.abspath(home), "scripts"))

    def test_a_source_has_no_seeding_axis_at_all(self):
        """The knob is deleted, not defaulted, so nothing reports it."""
        source = source_for(Context(
            blueprints_dir=os.path.join(self.root, "proj")))
        self.assertFalse(hasattr(source, "seeds"))

    def test_the_global_assignment_applies(self):
        proj = os.path.join(self.root, "proj")
        self.home_mod.set_blueprints_dir(proj)
        self.assertEqual(source_for(Context()).describe("blueprint"),
                         os.path.abspath(proj))

    def test_a_per_call_directory_wins_over_the_global(self):
        self.home_mod.set_blueprints_dir(os.path.join(self.root, "g"))
        scoped = os.path.join(self.root, "s")
        self.assertEqual(
            source_for(Context(blueprints_dir=scoped)).describe("blueprint"),
            os.path.abspath(scoped))


class IndexByNameTests(unittest.TestCase):
    """The residency conflict guard."""

    def test_effective_name_falls_back_to_stem(self):
        index = index_by_name(
            ["/a/one.rlqb", "/b/two.rlqb"], lambda _p: None, "blueprint")
        self.assertEqual(set(index), {"one", "two"})

    def test_declared_name_overrides_stem(self):
        index = index_by_name(
            ["/a/file.rlqb"], lambda _p: "identity", "blueprint")
        self.assertEqual(set(index), {"identity"})

    def test_duplicate_effective_name_raises(self):
        with self.assertRaises(PreflightError):
            index_by_name(
                ["/a/x.rlqb", "/b/y.rlqb"], lambda _p: "dup", "blueprint")

    def test_stem_strips_final_extension(self):
        self.assertEqual(stem("/a/b/thing.rlqb"), "thing")


class DirSourceResolutionTests(unittest.TestCase):
    """Resolution against a project asset root (dir mode)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = os.path.join(self._tmp.name, "home")
        self.root = os.path.join(self._tmp.name, "proj")
        os.makedirs(self.root)

    def ctx(self):
        return Context(home_dir=self.home, blueprints_dir=self.root,
                       scripts_dir=self.root)

    def test_walks_recursively_skipping_dotdirs(self):
        _write(os.path.join(self.root, "a.rlqb"),
               {"type": "machine", "name": "a", "platform": "dos"})
        _write(os.path.join(self.root, "sub", "b.rlqb"),
               {"type": "machine", "name": "b", "platform": "dos"})
        _write(os.path.join(self.root, ".git", "c.rlqb"),
               {"type": "machine", "name": "c", "platform": "dos"})
        names = {row["name"] for row in list_blueprints(self.ctx())}
        self.assertEqual(names, {"a", "b"})

    def test_name_field_overrides_stem(self):
        _write(os.path.join(self.root, "file.rlqb"),
               {"type": "machine", "platform": "dos", "name": "identity"})
        self.assertTrue(
            locate_blueprint("identity", context=self.ctx()).endswith(
                "file.rlqb"))
        with self.assertRaises(PreflightError):
            locate_blueprint("file", context=self.ctx())

    def test_duplicate_effective_name_is_error(self):
        _write(os.path.join(self.root, "one.rlqb"),
               {"type": "machine", "platform": "dos", "name": "dup"})
        _write(os.path.join(self.root, "two.rlqb"),
               {"type": "machine", "platform": "dos", "name": "dup"})
        with self.assertRaises(StaticError):
            list_blueprints(self.ctx())

    def test_rlqb_by_extension_but_json_needs_platform(self):
        _write(os.path.join(self.root, "notes.json"), {"items": {}})
        _write(os.path.join(self.root, "real.rlqb"),
                   {"type": "machine", "name": "real", "platform": "dos"})
        names = {row["name"] for row in list_blueprints(self.ctx())}
        self.assertEqual(names, {"real"})

    def test_a_codex_name_never_resolves_and_no_listing_shows_it(self):
        """The directory is the sole source, and the sets never mix.

        The refusal names the fix, because a deleted fallback should
        leave an instruction rather than a silence (P11) — and
        `list-codex` is the only verb that sees the library, so a
        listing of yours reports nothing of its (D88).
        """
        with self.assertRaises(PreflightError) as caught:
            locate_blueprint("freedos", context=self.ctx())
        self.assertIn("rlq seed-blueprint freedos", str(caught.exception))
        self.assertEqual(list_blueprints(self.ctx()), [])
        self.assertIn("freedos", [row["name"] for row in list_codex()])

    def test_media_resolves_from_the_project_root(self):
        _write(os.path.join(self.root, "lib.rlqb"),
               [{"type": "media", "name": "proj-media",
                 "location": {"local": "/X.iso"}}])
        resolved = resolve_media("proj-media", load_namespace(self.ctx()))
        self.assertEqual(resolved.name, "proj-media")

    def test_media_missing_in_dir_mode_does_not_seed(self):
        with self.assertRaises(PreflightError):
            resolve_media("freedos-livecd", load_namespace(self.ctx()))


class SelectionScopingTests(unittest.TestCase):
    """Same-named blueprints in different projects stay separate."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        self.backend = stack.enter_context(fake_backend.installed())
        self.home = os.path.join(self._tmp.name, "home")
        self.a = os.path.join(self._tmp.name, "a")
        self.b = os.path.join(self._tmp.name, "b")
        for root in (self.a, self.b):
            _write(os.path.join(root, "shared.rlqb"),
                   {"type": "machine", "name": "shared", "platform": "dos",
                    "drives": {"cdrom0": None}})

    def _ctx(self, root):
        return Context(home_dir=self.home, blueprints_dir=root,
                       scripts_dir=root)

    def test_projects_do_not_adopt_each_others_machines(self):
        id_a = create_machine("shared", context=self._ctx(self.a))
        id_b = create_machine("shared", context=self._ctx(self.b))
        self.assertNotEqual(id_a, id_b)
        self.assertEqual(
            resolve_machine(blueprint="shared", context=self._ctx(self.a)),
            id_a)
        self.assertEqual(
            resolve_machine(blueprint="shared", context=self._ctx(self.b)),
            id_b)


class BlueprintNameIdentityTests(unittest.TestCase):
    """``name`` is an id-safe identity, not a prose label."""

    def test_id_safe_name_is_accepted(self):
        doc = parse_document(
            {"type": "machine", "platform": "dos", "name": "freedos"}, stem="h")
        self.assertIn("freedos", doc.machines)

    def test_name_with_spaces_is_rejected(self):
        with self.assertRaises(StaticError):
            parse_document({"type": "machine", "platform": "dos", "name": "Not An Id"}, stem="h")

    def test_all_digit_name_is_rejected(self):
        with self.assertRaises(StaticError):
            parse_document({"type": "machine", "platform": "dos", "name": "12"}, stem="h")


if __name__ == "__main__":
    unittest.main()
