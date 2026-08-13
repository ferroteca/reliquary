# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for authored-asset residency: the resolution source seam."""

import json
import os
import re

import pytest

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


def _write(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(obj, handle)


@pytest.fixture
def root(tmp_path):
    return str(tmp_path)


# The extension vocabulary against what the code asks for.
#
# Code against code: `KIND_EXTENSIONS` declares the asset kinds and
# `candidate_files(...)` call sites are what actually request them.
# Whether the spec's prose names the same kinds and home folders is
# R7's audit (planning/RECURRING.md).

def test_the_kind_table_holds_only_requested_kinds():
    # library.py is the only caller; a kind nothing asks for
    # cannot resolve and only advertises that it could.
    requested = set()
    package = os.path.dirname(os.path.abspath(reliquary.__file__))
    for name in sorted(os.listdir(package)):
        if not name.endswith(".py") or name == "assets.py":
            continue
        with open(os.path.join(package, name), encoding="utf-8") as handle:
            requested.update(
                re.findall(r"candidate_files\(\"([a-z]+)\"\)",
                           handle.read()))
    assert sorted(KIND_EXTENSIONS) == sorted(requested), (
        "KIND_EXTENSIONS declares an asset kind no source is ever "
        "asked for. An unrequested kind cannot resolve, so declaring "
        "it advertises a resolution that cannot happen; reserve it in "
        "docs/spec/asset-resolution.md instead.")


# Where each kind resolves from, and nothing else.
#
# One axis, where the asset-root knob answered two questions and the
# autoseed knob that replaced half of it answered the other. The
# directory decides where a name resolves, and a miss is a miss: the
# codex is not a tier behind it (D88).

def test_an_unassigned_directory_refuses_at_use():
    """A bare embedding call with nothing assigned fails closed.

    Building the source never raises — the directories resolve
    lazily — so the refusal lands where the resolution is, naming
    the directory it wanted.
    """
    source = source_for(Context())
    with pytest.raises(StaticError):
        source.candidate_files("blueprint")


def test_each_kind_reads_its_own_directory(root):
    blueprints = os.path.join(root, "bp")
    scripts = os.path.join(root, "sc")
    source = source_for(Context(blueprints_dir=blueprints,
                                scripts_dir=scripts))
    assert source.describe("blueprint") == os.path.abspath(blueprints)
    assert source.describe("script") == os.path.abspath(scripts)


def test_a_bare_home_string_derives_both(root):
    home = os.path.join(root, "home")
    source = source_for(home)
    assert source.describe("blueprint") == os.path.join(
        os.path.abspath(home), "blueprints")
    assert source.describe("script") == os.path.join(
        os.path.abspath(home), "scripts")


def test_a_source_has_no_seeding_axis_at_all(root):
    """The knob is deleted, not defaulted, so nothing reports it."""
    source = source_for(Context(blueprints_dir=os.path.join(root, "proj")))
    assert not hasattr(source, "seeds")


def test_a_record_slot_places_the_source(root):
    # The record is the only assignment there is (P26): a slot
    # places the source, and nothing ambient stands behind it.
    scoped = os.path.join(root, "s")
    assert source_for(
        Context(blueprints_dir=scoped)).describe("blueprint") == (
        os.path.abspath(scoped))


# The residency conflict guard.

def test_effective_name_falls_back_to_stem():
    index = index_by_name(["/a/one.rlqb", "/b/two.rlqb"],
                          lambda _p: None, "blueprint")
    assert set(index) == {"one", "two"}


def test_declared_name_overrides_stem():
    index = index_by_name(["/a/file.rlqb"], lambda _p: "identity",
                          "blueprint")
    assert set(index) == {"identity"}


def test_duplicate_effective_name_raises():
    with pytest.raises(PreflightError):
        index_by_name(["/a/x.rlqb", "/b/y.rlqb"], lambda _p: "dup",
                      "blueprint")


def test_stem_strips_final_extension():
    assert stem("/a/b/thing.rlqb") == "thing"


# Resolution against a project asset root (dir mode).

@pytest.fixture
def project(tmp_path):
    """A context whose blueprints and scripts live in one project root."""
    home = str(tmp_path / "home")
    project_root = str(tmp_path / "proj")
    os.makedirs(project_root)
    context = Context(home_dir=home, blueprints_dir=project_root,
                      scripts_dir=project_root)
    return context, project_root


def test_walks_recursively_skipping_dotdirs(project):
    context, root = project
    _write(os.path.join(root, "a.rlqb"),
           {"type": "machine", "name": "a", "platform": "dos"})
    _write(os.path.join(root, "sub", "b.rlqb"),
           {"type": "machine", "name": "b", "platform": "dos"})
    _write(os.path.join(root, ".git", "c.rlqb"),
           {"type": "machine", "name": "c", "platform": "dos"})
    assert {row["name"] for row in list_blueprints(context)} == {"a", "b"}


def test_name_field_overrides_stem(project):
    context, root = project
    _write(os.path.join(root, "file.rlqb"),
           {"type": "machine", "platform": "dos", "name": "identity"})
    assert locate_blueprint("identity",
                            context=context).endswith("file.rlqb")
    with pytest.raises(PreflightError):
        locate_blueprint("file", context=context)


def test_duplicate_effective_name_is_error(project):
    context, root = project
    _write(os.path.join(root, "one.rlqb"),
           {"type": "machine", "platform": "dos", "name": "dup"})
    _write(os.path.join(root, "two.rlqb"),
           {"type": "machine", "platform": "dos", "name": "dup"})
    with pytest.raises(StaticError):
        list_blueprints(context)


def test_rlqb_by_extension_but_json_needs_platform(project):
    context, root = project
    _write(os.path.join(root, "notes.json"), {"items": {}})
    _write(os.path.join(root, "real.rlqb"),
           {"type": "machine", "name": "real", "platform": "dos"})
    assert {row["name"] for row in list_blueprints(context)} == {"real"}


def test_a_codex_name_never_resolves_and_no_listing_shows_it(project):
    """The directory is the sole source, and the sets never mix.

    The refusal names the fix, because a deleted fallback should
    leave an instruction rather than a silence (P11) — and
    `list-codex` is the only verb that sees the library, so a
    listing of yours reports nothing of its (D88).
    """
    context, _root = project
    with pytest.raises(PreflightError) as caught:
        locate_blueprint("freedos", context=context)
    assert "rlq seed-blueprint freedos" in str(caught.value)
    assert list_blueprints(context) == []
    assert "freedos" in [row["name"] for row in list_codex()]


def test_media_resolves_from_the_project_root(project):
    context, root = project
    _write(os.path.join(root, "lib.rlqb"),
           [{"type": "media", "name": "proj-media",
             "location": {"local": "/X.iso"}}])
    resolved = resolve_media("proj-media", load_namespace(context))
    assert resolved.name == "proj-media"


def test_media_missing_in_dir_mode_does_not_seed(project):
    context, _root = project
    with pytest.raises(PreflightError):
        resolve_media("freedos-livecd", load_namespace(context))


# Same-named blueprints in different projects stay separate.

def test_projects_do_not_adopt_each_others_machines(tmp_path):
    home = str(tmp_path / "home")
    roots = [str(tmp_path / "a"), str(tmp_path / "b")]
    for root in roots:
        _write(os.path.join(root, "shared.rlqb"),
               {"type": "machine", "name": "shared", "platform": "dos",
                "drives": {"cdrom0": None}})

    def context(root):
        return Context(home_dir=home, blueprints_dir=root,
                       scripts_dir=root)

    with fake_backend.installed():
        id_a = create_machine("shared", context=context(roots[0]))
        id_b = create_machine("shared", context=context(roots[1]))
        assert id_a != id_b
        assert resolve_machine(blueprint="shared",
                               context=context(roots[0])) == id_a
        assert resolve_machine(blueprint="shared",
                               context=context(roots[1])) == id_b


# ``name`` is an id-safe identity, not a prose label.

def test_id_safe_name_is_accepted():
    doc = parse_document(
        {"type": "machine", "platform": "dos", "name": "freedos"}, stem="h")
    assert "freedos" in doc.machines


def test_name_with_spaces_is_rejected():
    with pytest.raises(StaticError):
        parse_document({"type": "machine", "platform": "dos",
                        "name": "Not An Id"}, stem="h")


def test_all_digit_name_is_rejected():
    with pytest.raises(StaticError):
        parse_document({"type": "machine", "platform": "dos",
                        "name": "12"}, stem="h")
