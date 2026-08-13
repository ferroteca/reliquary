# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for whole-source catalog + fetch-plan resolution.

This is where the second phase of validation lives, so it is where the
rules a single document cannot express are tested: identity across
files, containment through the catalog, and the value checks that need
a resolved reference.
"""

import os

import pytest

from reliquary import resolve
from reliquary.errors import PreflightError
from reliquary.document import parse_document
from reliquary.resolve import Alternatives, Download, Extract, LocalFile

SHA = "a" * 64
SHB = "b" * 64


def _write(root, name, text):
    path = os.path.join(root, name)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return path


def _namespace(value):
    return resolve.namespace_of(parse_document(value))


@pytest.fixture
def root(tmp_path):
    return str(tmp_path)


# One namespace out of many files.

def test_merges_specs_across_files(root):
    a = _write(root, "machine.rlqb",
               '[{"type": "machine", "name": "m", "platform": "dos"}]')
    b = _write(root, "media.rlqb",
               '[{"name": "blank", "materialize": "new", "size": "1M"}]')
    ns = resolve.build_namespace([a, b])
    assert set(ns.machines) == {"m"}
    assert set(ns.media) == {"blank"}


def test_identical_specs_across_files_dedup(root):
    """What lets a self-contained blueprint be pasted around."""
    spec = ('[{"name": "iso", "location": "https://x.test/p.iso",'
            ' "sha256": "%s"}]' % SHA)
    a = _write(root, "a.rlqb", spec)
    b = _write(root, "b.rlqb", spec)
    ns = resolve.build_namespace([a, b])
    assert set(ns.media) == {"iso"}


def test_differing_specs_of_one_name_collide_naming_both_files(root):
    a = _write(root, "a.rlqb",
               '[{"name": "x", "materialize": "new", "size": "1M"}]')
    b = _write(root, "b.rlqb",
               '[{"name": "x", "materialize": "new", "size": "2M"}]')
    with pytest.raises(PreflightError) as caught:
        resolve.build_namespace([a, b])
    message = str(caught.value)
    assert "x" in message
    assert "a.rlqb" in message
    assert "b.rlqb" in message


def test_names_collide_case_insensitively_across_files(root):
    a = _write(root, "a.rlqb",
               '[{"name": "FDBOOT", "location": "a.img"}]')
    b = _write(root, "b.rlqb",
               '[{"name": "fdboot", "location": "b.img"}]')
    with pytest.raises(PreflightError) as caught:
        resolve.build_namespace([a, b])
    assert "case" in str(caught.value)


# Local media resolve against the referencing file, never the CWD.

def test_the_plan_is_cwd_independent(root, tmp_path, monkeypatch):
    blueprint = _write(root, "b.rlqb",
                       '[{"name": "iso", "location": "x.iso"}]')
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    ns = resolve.build_namespace([blueprint])
    plan = resolve.resolve_media_plan(resolve.resolve_media("iso", ns), ns)
    assert isinstance(plan, LocalFile)
    assert plan.path == os.path.join(root, "x.iso")


def test_one_relative_spelling_in_two_directories_collides(root):
    """Anchored, the two specs name different bytes: different
    media, so they collide rather than silently resolving through
    whichever file was read first."""
    spec = '[{"name": "iso", "location": "x.iso"}]'
    os.mkdir(os.path.join(root, "a"))
    os.mkdir(os.path.join(root, "b"))
    a = _write(os.path.join(root, "a"), "a.rlqb", spec)
    b = _write(os.path.join(root, "b"), "b.rlqb", spec)
    with pytest.raises(PreflightError) as caught:
        resolve.build_namespace([a, b])
    message = str(caught.value)
    assert "a.rlqb" in message
    assert "b.rlqb" in message


def test_one_relative_spelling_in_one_directory_still_dedups(root):
    spec = '[{"name": "iso", "location": "x.iso"}]'
    a = _write(root, "a.rlqb", spec)
    b = _write(root, "b.rlqb", spec)
    ns = resolve.build_namespace([a, b])
    assert set(ns.media) == {"iso"}
    rung = ns.media["iso"].location[0]
    assert rung.local == os.path.join(root, "x.iso")


# Lowering a media to its fetch plan.

def test_nested_containment_plan():
    ns = _namespace([{
        "name": "PaulsFreedos",
        "location": "https://paul.com/PaulsFreedos.zip", "sha256": SHA,
        "children": [{"path": "FD14-FloppyEdition.zip",
                      "children": ["144m/FDBOOT.img"]}]}])
    plan = resolve.resolve_media_plan(ns.media["FDBOOT"], ns)
    # outermost extract: FDBOOT.img out of the floppy edition
    assert isinstance(plan, Extract)
    assert plan.parent == "FD14-FloppyEdition"
    assert plan.member == "144m/FDBOOT.img"
    # next: the floppy edition out of the outer download
    assert isinstance(plan.inner, Extract)
    assert plan.inner.parent == "PaulsFreedos"
    assert plan.inner.member == "FD14-FloppyEdition.zip"
    # root: the download itself
    assert isinstance(plan.inner.inner, Download)
    assert plan.inner.inner.url == "https://paul.com/PaulsFreedos.zip"
    assert plan.inner.inner.sha256 == SHA


def test_bare_parent_reference_is_the_parents_own_bytes():
    """How a difference overlay names what it sits on."""
    ns = _namespace([
        {"name": "golden", "location": "golden.qcow2"},
        {"name": "scratch", "materialize": "difference",
         "location": "${media:golden}"}])
    plan = resolve.resolve_media_plan(ns.media["scratch"], ns)
    assert isinstance(plan, LocalFile)
    assert plan.path == "golden.qcow2"


def test_mirror_list_becomes_alternatives():
    ns = _namespace([{"name": "iso", "sha256": SHA,
                      "location": ["https://a.test/p.iso",
                                   "vendor/p.iso"]}])
    plan = resolve.resolve_media_plan(ns.media["iso"], ns)
    assert isinstance(plan, Alternatives)
    assert isinstance(plan.options[0], Download)
    assert isinstance(plan.options[1], LocalFile)


def test_blank_has_no_plan():
    ns = _namespace([{"name": "blank", "materialize": "new",
                      "size": "1M"}])
    assert resolve.resolve_media_plan(ns.media["blank"], ns) is None


def test_missing_parent_names_both_media():
    ns = _namespace([{"name": "x", "location": "${media:gone/a.img}"}])
    with pytest.raises(PreflightError) as caught:
        resolve.resolve_media_plan(ns.media["x"], ns)
    assert "gone" in str(caught.value)


def test_containment_cycle_is_named():
    ns = _namespace([{"name": "loop", "location": "${media:loop/p.img}"}])
    with pytest.raises(PreflightError) as caught:
        resolve.resolve_media_plan(ns.media["loop"], ns)
    assert "cycle" in str(caught.value)


def test_remote_without_a_hash_fails_at_resolution():
    """Parse cannot know: a referenced rung may resolve to a URL."""
    ns = _namespace([{"name": "iso",
                      "location": "https://x.test/p.iso"}])
    with pytest.raises(PreflightError) as caught:
        resolve.resolve_media_plan(ns.media["iso"], ns)
    assert "sha256" in str(caught.value)


def test_unsupported_container_names_its_format():
    ns = _namespace([
        {"name": "disk", "location": "disk.img"},
        {"name": "inside", "location": "${media:disk/p.txt}"}])
    with pytest.raises(PreflightError) as caught:
        resolve.resolve_media_plan(ns.media["inside"], ns)
    message = str(caught.value)
    assert "img" in message
    assert "zip" in message


def test_property_location_fails_closed_naming_properties():
    """Never a milestone number: name the channel it waits on."""
    ns = _namespace([{"name": "win", "location": "${windows.iso}"}])
    with pytest.raises(PreflightError) as caught:
        resolve.resolve_media_plan(ns.media["win"], ns)
    message = str(caught.value)
    assert "propert" in message
    assert "milestone" not in message


# `${key}` in a location binds through a supplied properties map (T5).

def test_a_property_location_binds_to_a_url():
    ns = _namespace([{"name": "win", "location": "${windows.iso}",
                      "sha256": SHA}])
    plan = resolve.resolve_media_plan(
        ns.media["win"], ns, {"windows.iso": "https://vendor.test/win.iso"})
    assert isinstance(plan, Download)
    assert plan.url == "https://vendor.test/win.iso"
    assert plan.sha256 == SHA


def test_a_property_location_binds_to_a_local_path():
    ns = _namespace([{"name": "win", "location": "${windows.iso}"}])
    plan = resolve.resolve_media_plan(
        ns.media["win"], ns, {"windows.iso": "C:/isos/win.iso"})
    assert isinstance(plan, LocalFile)
    assert plan.path == "C:/isos/win.iso"


def test_a_deferred_string_interpolates_bound_values():
    ns = _namespace([{
        "name": "win",
        "location": "https://vendor.test/${edition}/win.iso",
        "sha256": SHA}])
    plan = resolve.resolve_media_plan(ns.media["win"], ns,
                                      {"edition": "pro"})
    assert isinstance(plan, Download)
    assert plan.url == "https://vendor.test/pro/win.iso"


def test_an_unbound_key_names_the_media_and_the_key():
    ns = _namespace([{"name": "win", "location": "${windows.iso}"}])
    with pytest.raises(PreflightError) as caught:
        resolve.resolve_media_plan(ns.media["win"], ns, {})
    message = str(caught.value)
    assert "win" in message
    assert "windows.iso" in message


def test_a_value_that_is_itself_a_reference_fails_closed():
    ns = _namespace([{"name": "win", "location": "${windows.iso}"}])
    with pytest.raises(PreflightError) as caught:
        resolve.resolve_media_plan(ns.media["win"], ns,
                                   {"windows.iso": "${other}"})
    assert "chain" in str(caught.value)


def test_a_value_naming_another_media_is_refused():
    ns = _namespace([{"name": "win", "location": "${windows.iso}"}])
    with pytest.raises(PreflightError) as caught:
        resolve.resolve_media_plan(ns.media["win"], ns,
                                   {"windows.iso": "${media:other}"})
    assert "chain" in str(caught.value)


def test_a_deferred_sha256_binds():
    ns = _namespace([{"name": "win",
                      "location": "https://vendor.test/win.iso",
                      "sha256": "${win.hash}"}])
    plan = resolve.resolve_media_plan(ns.media["win"], ns,
                                      {"win.hash": SHA})
    assert plan.sha256 == SHA


def test_location_property_keys_walks_the_closure():
    # A child inherits its parent's location keys: to extract inner,
    # the outer download's ${outer.zip} must bind first.
    ns = _namespace([{
        "name": "outer", "location": "${outer.zip}", "sha256": SHA,
        "children": ["inner.img"]}])
    inner = next(m for name, m in ns.media.items() if name != "outer")
    assert resolve.location_property_keys(inner, ns) == {"outer.zip"}
