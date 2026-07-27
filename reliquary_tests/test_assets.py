# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Tests for authored-asset residency: the resolution source seam."""

import importlib
import json
import os
import tempfile
import unittest

import re

from reliquary import Context, HOME_ASSETS
from reliquary.assets import (DirSource, HomeSource, KIND_EXTENSIONS,
                              index_by_name, source_for, stem)
from reliquary.document import parse_document
from reliquary.library import (list_blueprints, locate_blueprint,
                               search_blueprints)
from reliquary.machines import create_machine, resolve_machine
from reliquary.resolve import load_namespace, resolve_media

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
        package = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "reliquary")
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


class AssetModeTests(unittest.TestCase):
    """How the effective source is selected per invocation."""

    def setUp(self):
        # Isolate from the process-global asset mode a CLI run may have
        # left set, so an unconfigured source genuinely refuses.
        self.home_mod = importlib.import_module("reliquary.home")
        saved = self.home_mod._assets
        self.addCleanup(setattr, self.home_mod, "_assets", saved)
        self.home_mod._assets = self.home_mod._UNSET
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = self._tmp.name

    def test_unconfigured_source_refuses(self):
        """A bare embedding call with no source named fails closed."""
        with self.assertRaises(RuntimeError):
            source_for(Context(home=os.path.join(self.root, "home")))

    def test_bare_string_context_is_home_mode(self):
        source = source_for(os.path.join(self.root, "home"))
        self.assertIsInstance(source, HomeSource)
        self.assertTrue(source.seeds)

    def test_explicit_dir_is_dir_mode_and_hermetic(self):
        proj = os.path.join(self.root, "proj")
        os.makedirs(proj)
        source = source_for(Context(home="h", assets=proj))
        self.assertIsInstance(source, DirSource)
        self.assertFalse(source.seeds)
        self.assertEqual(source.root, os.path.abspath(proj))

    def test_global_home_mode_applies(self):
        self.home_mod.set_assets(HOME_ASSETS)
        self.assertIsInstance(source_for(Context(home="h")), HomeSource)

    def test_global_dir_mode_applies(self):
        proj = os.path.join(self.root, "proj")
        os.makedirs(proj)
        self.home_mod.set_assets(proj)
        source = source_for(Context(home="h"))
        self.assertIsInstance(source, DirSource)
        self.assertEqual(source.root, os.path.abspath(proj))

    def test_per_call_assets_win_over_global(self):
        self.home_mod.set_assets(HOME_ASSETS)
        proj = os.path.join(self.root, "proj")
        os.makedirs(proj)
        self.assertIsInstance(
            source_for(Context(home="h", assets=proj)), DirSource)


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
        with self.assertRaises(ValueError):
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
        return Context(home=self.home, assets=self.root)

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
        with self.assertRaises(FileNotFoundError):
            locate_blueprint("file", context=self.ctx())

    def test_duplicate_effective_name_is_error(self):
        _write(os.path.join(self.root, "one.rlqb"),
               {"type": "machine", "platform": "dos", "name": "dup"})
        _write(os.path.join(self.root, "two.rlqb"),
               {"type": "machine", "platform": "dos", "name": "dup"})
        with self.assertRaises(ValueError):
            list_blueprints(self.ctx())

    def test_rlqb_by_extension_but_json_needs_platform(self):
        _write(os.path.join(self.root, "notes.json"), {"items": {}})
        _write(os.path.join(self.root, "real.rlqb"),
                   {"type": "machine", "name": "real", "platform": "dos"})
        names = {row["name"] for row in list_blueprints(self.ctx())}
        self.assertEqual(names, {"real"})

    def test_dir_mode_is_hermetic_no_codex(self):
        """A codex name never resolves in dir mode; search shows no codex."""
        with self.assertRaises(FileNotFoundError):
            locate_blueprint("freedos", context=self.ctx())
        self.assertEqual(search_blueprints("", context=self.ctx()), [])

    def test_media_resolves_from_the_project_root(self):
        _write(os.path.join(self.root, "lib.rlqb"),
               [{"type": "media", "name": "proj-media",
                 "location": {"local": "/X.iso"}}])
        resolved = resolve_media("proj-media", load_namespace(self.ctx()))
        self.assertEqual(resolved.name, "proj-media")

    def test_media_missing_in_dir_mode_does_not_seed(self):
        with self.assertRaises(KeyError):
            resolve_media("freedos-livecd", load_namespace(self.ctx()))


class SelectionScopingTests(unittest.TestCase):
    """Same-named blueprints in different projects stay separate."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = os.path.join(self._tmp.name, "home")
        self.a = os.path.join(self._tmp.name, "a")
        self.b = os.path.join(self._tmp.name, "b")
        for root in (self.a, self.b):
            _write(os.path.join(root, "shared.rlqb"),
                   {"type": "machine", "name": "shared", "platform": "dos",
                    "drives": {"cdrom0": None}})

    def _ctx(self, root):
        return Context(home=self.home, assets=root)

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
        with self.assertRaises(ValueError):
            parse_document({"type": "machine", "platform": "dos", "name": "Not An Id"}, stem="h")

    def test_all_digit_name_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_document({"type": "machine", "platform": "dos", "name": "12"}, stem="h")


if __name__ == "__main__":
    unittest.main()
