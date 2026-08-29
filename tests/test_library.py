# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Built-in library seeding for the composed blueprint model.

Media are components inside the blueprint ``.rlqb`` now, so seeding a
blueprint brings its media along inside the same file — there is no
separate media definition to copy out, and no ``seed_media`` verb
(DECISIONS.md D30).
"""

import json
import os
import shutil

import pytest

import reliquary
from reliquary import document, json5reader
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

_CODEX = os.path.join(os.path.dirname(reliquary.__file__), "codex")


def _codex_files(kind, extension):
    """Every shipped artifact of one kind, sorted."""
    root = os.path.join(_CODEX, kind)
    return sorted(os.path.join(root, name) for name in os.listdir(root)
                  if name.endswith(extension))


def _codex_doc(name):
    return document.load_document(
        os.path.join(_CODEX, "blueprints", f"{name}{EXT}"))


def _index():
    with open(os.path.join(_CODEX, "codex.json"), encoding="utf-8") as h:
        return json5reader.loads(h.read())


#: The shipped artifacts, gathered here at collection time rather than
#: inside each test. That way, if the codex ever stops shipping any
#: artifacts, the parametrized test count itself drops to zero,
#: instead of every test silently passing over nothing to check.
CODEX_BLUEPRINTS = _codex_files("blueprints", EXT)
CODEX_SCRIPTS = _codex_files("scripts", ".rlqs")


@pytest.fixture
def home(tmp_path):
    """A scratch home the codex can be seeded into.

    These are the codex's own tests: seeding, the closure it brings,
    and the never-overwrite rule. Every one of them asks for what it
    wants by name — seeding is the only way the library's content
    reaches a tree at all (D88).
    """
    with fake_backend.installed():
        yield str(tmp_path)


def _path(home, *parts):
    return os.path.join(home, *parts)


# Seeding, and the closure it brings.

def test_seed_blueprint_copies_closure(home):
    """Seeding a blueprint brings its scripts along; media ride the
    blueprint file itself."""
    assert seed_blueprint(BLUEPRINT, context=home)
    blueprint_path = _path(home, "blueprints", f"{BLUEPRINT}{EXT}")
    assert os.path.isfile(blueprint_path)
    for stem in SCRIPTS:
        assert os.path.isfile(_path(home, "scripts", f"{stem}.rlqs"))
    # The media travels inside the seeded blueprint.
    assert MEDIA in document.load_document(blueprint_path).media


def test_seed_blueprint_only_skips_closure(home):
    assert seed_blueprint(BLUEPRINT, context=home, only=True)
    assert os.path.isfile(_path(home, "blueprints", f"{BLUEPRINT}{EXT}"))
    assert not os.path.isdir(_path(home, "scripts"))


def test_second_seed_leaves_user_files_alone(home):
    seed_blueprint(BLUEPRINT, context=home)
    # Remove the blueprint so re-seeding runs the closure again; the
    # user-edited script it references must not be overwritten.
    os.remove(_path(home, "blueprints", f"{BLUEPRINT}{EXT}"))
    script_path = _path(home, "scripts", f"{SCRIPTS[0]}.rlqs")
    with open(script_path, "w", encoding="utf-8") as handle:
        handle.write("user edit")
    assert seed_blueprint(BLUEPRINT, context=home)
    with open(script_path, encoding="utf-8") as handle:
        assert handle.read() == "user edit"


@pytest.mark.parametrize("ext", [".json", EXT], ids=["json", "rlqb"])
def test_existing_home_blueprint_is_untouched(home, ext):
    shutil.rmtree(home)
    os.makedirs(home)
    blueprint_path = _path(home, "blueprints", f"{BLUEPRINT}{ext}")
    os.makedirs(os.path.dirname(blueprint_path))
    with open(blueprint_path, "w", encoding="utf-8") as handle:
        handle.write("mine")
    assert not seed_blueprint(BLUEPRINT, context=home)
    with open(blueprint_path, encoding="utf-8") as handle:
        assert handle.read() == "mine"
    assert not os.path.exists(_path(home, "scripts"))


def test_unknown_names_seed_nothing(home):
    assert not seed_blueprint("no-such", context=home)
    assert not seed_script("no-such", context=home)
    assert not os.path.exists(_path(home, "blueprints"))
    assert not os.path.exists(_path(home, "scripts"))


def test_seed_script_copies_once(home):
    assert seed_script(SCRIPTS[0], context=home)
    assert not seed_script(SCRIPTS[0], context=home)


# The library's own listing, and the only verb that reads it.

def test_it_lists_the_shipped_blueprints_with_descriptions():
    rows = list_codex()
    row = next(r for r in rows if r["name"] == BLUEPRINT)
    assert "FreeDOS" in row["description"]
    assert [r["name"] for r in rows] == sorted(r["name"] for r in rows)


def test_it_reports_nothing_of_yours(home):
    """list_codex reports only what's actually shipped in the codex —
    it never scans the user's own tree to guess what might belong
    there too."""
    bp_dir = os.path.join(home, "blueprints")
    os.makedirs(bp_dir)
    with open(os.path.join(bp_dir, "mine.rlqb"), "w",
              encoding="utf-8") as handle:
        json.dump([{"type": "machine", "name": "custom-rig",
                    "platform": "dos",
                    "description": "bespoke widget rig",
                    "devices": {"cdrom0": None}}], handle)
    names = [row["name"] for row in list_codex()]
    assert "custom-rig" not in names
    assert BLUEPRINT in names


def test_seeding_does_not_change_what_it_reports(home):
    before = list_codex()
    seed_blueprint(BLUEPRINT, context=home, only=True)
    assert before == list_codex()


def test_availability_is_a_question_that_reads_nothing(home):
    assert codex_blueprint_available(BLUEPRINT)
    assert not codex_blueprint_available("zzzznomatch")
    assert not os.path.exists(_path(home, "blueprints"))


# What a seeded copy is, once it is yours.

def test_media_travels_with_a_seeded_blueprint(home):
    seed_blueprint(BLUEPRINT, context=home)
    assert MEDIA in load_namespace(home).media


def test_resolve_media_unknown_name_errors(home):
    with pytest.raises(PreflightError):
        resolve_media("no-such-media", load_namespace(home))


def test_create_machine_honors_edits_to_the_seeded_copy(home):
    """The copy is yours, and a create reads it rather than the codex.

    This used to assert that `create_machine` seeded on first
    reference. It does not (D88): the seed is the user's own step,
    and what survives — the point the test was always making — is
    that an edit to the copy reaches the next machine while the one
    already built keeps what it was built from.
    """
    seed_blueprint(BLUEPRINT, context=home)
    machine_id = create_machine(BLUEPRINT, context=home)
    blueprint_path = os.path.join(home, "blueprints", f"{BLUEPRINT}{EXT}")
    assert os.path.isfile(blueprint_path)
    with open(blueprint_path, encoding="utf-8") as handle:
        data = json5reader.load(handle)
    machine = next(spec for spec in data if spec.get("type") == "machine")
    machine["memory"] = 64
    with open(blueprint_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle)
    second_id = create_machine(BLUEPRINT, context=home)
    assert load_machine_state(machine_id, context=home)["memory"] == 32
    assert load_machine_state(second_id, context=home)["memory"] == 64


def test_create_machine_unknown_name_errors(home):
    with pytest.raises(PreflightError):
        create_machine("no-such-blueprint", context=home)


def test_an_unseeded_codex_name_is_refused_with_the_fix(home):
    """A name the library holds and your tree does not.

    The interesting refusal, and the one a first-time user meets:
    it must name the command that resolves it, or the deleted
    fallback reads as the tool not knowing about `freedos` at all.
    """
    with pytest.raises(PreflightError) as caught:
        create_machine(BLUEPRINT, context=home)
    assert f"rlq seed-blueprint {BLUEPRINT}" in str(caught.value)


# The readiness example, and the property that makes it one (T9).
#
# Every other codex script ends with the guest powered off, because
# each one is finished with it by then. A readiness example has the
# opposite job: it hands a *live* machine to whatever comes next, and
# that's the whole reason it exists — so that's what the tests below
# guard. An example that looked right but quietly powered the machine
# off at the end would demonstrate nothing the other two examples
# don't already.
#
# Whether it actually *works* is the integration test's job to prove
# (P18: a codex example that doesn't work is a defect). These tests
# only check its shape.

READY_LABEL = "ready"
READY_STEM = "freedos-ready"


@pytest.fixture
def ready_script(home):
    """The seeded readiness example: its path, text and parsed tree."""
    seed_blueprint(BLUEPRINT, context=home)
    path = os.path.join(home, "scripts", f"{READY_STEM}.rlqs")
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    return load_script(path), text


def test_the_blueprint_names_it_and_seeding_brings_it(home):
    """The blueprint actually references this script by name, not just
    ships it alongside — a file nothing names would just sit there
    unused."""
    seed_blueprint(BLUEPRINT, context=home)
    component = load_namespace(home).machines[BLUEPRINT]
    assert component.scripts[READY_LABEL] == READY_STEM
    assert os.path.isfile(
        os.path.join(home, "scripts", f"{READY_STEM}.rlqs"))


def test_it_leaves_the_machine_running(ready_script):
    script, text = ready_script
    verbs = [statement.verb for statement in script.statements]
    assert "start" in verbs
    assert "stop" not in verbs
    # The codex's own idiom for confirming a machine is off — waiting
    # for `machine=stopped` after a poweroff — is exactly what this
    # example must NOT do; that's `freedos-verify`'s job instead.
    assert "machine=stopped" not in text


def test_the_promise_is_the_last_step(ready_script):
    """Set only once everything it promises has held."""
    script, _text = ready_script
    last = script.statements[-1]
    assert last.verb == "set"
    assert last.arguments[0] == READY_LABEL


def test_the_variable_is_outside_the_reserved_namespaces(ready_script):
    """`rlq.ready` would be a static error, not a nicer spelling.

    The reserved namespaces are reliquary's own (V5), which is why
    the example's key is plain — and why a reader copying it gets
    something that parses.
    """
    script, _text = ready_script
    check_variable_key(script.statements[-1].arguments[0])
    with pytest.raises(StaticError):
        check_variable_key("rlq.ready")


# The shipped codex blueprints carry the pinned media hashes.

def test_freedos_livecd_media_pins_the_iso_hash():
    media = _codex_doc(BLUEPRINT).media[MEDIA]
    assert media.sha256 == (
        "c48a9dcf4b8e22f44e268a9879745f0bd88c061195ac584e"
        "6ef2deb0477f81fb")


def test_openbsd_install_media_pins_the_iso():
    media = _codex_doc(OPENBSD_BLUEPRINT).media[OPENBSD_MEDIA]
    assert media.location[0].kind == "url"
    assert media.sha256 == (
        "7a4a92e953618035097c796a90b54424a0f3ae775552e1e7d102"
        "cf8a5130449f")


# Every shipped codex artifact parses, or the suite fails.
#
# The codex is the worked example users seed and copy from. A
# blueprint or script that does not parse is a defect the default
# suite must catch — not something left to an opt-in integration run
# or a single named reference script. One node per artifact, named for
# its file.

@pytest.mark.parametrize("path", CODEX_BLUEPRINTS,
                         ids=[os.path.basename(p)
                              for p in CODEX_BLUEPRINTS])
def test_a_codex_blueprint_parses(path):
    document.load_document(path)


@pytest.mark.parametrize("path", CODEX_SCRIPTS,
                         ids=[os.path.basename(p) for p in CODEX_SCRIPTS])
def test_a_codex_script_parses(path):
    load_script(path)


def test_the_codex_ships_artifacts_of_both_kinds():
    """The parametrisations above are empty if this ever stops holding."""
    assert CODEX_BLUEPRINTS, "no codex blueprints shipped"
    assert CODEX_SCRIPTS, "no codex scripts shipped"


# The shipped codex tree, checked against its own index.
#
# This compares two machine-readable things against each other, not
# prose: `codex.json` is the index the listing reads, and the tree
# beside it is what actually ships. Whether docs/spec/codex.md
# describes both of these truthfully is a separate question, covered
# by R9's audit instead (planning/RECURRING.md).

def test_every_codex_blueprint_is_indexed():
    # The reverse of test_builtin_blueprint_index_names_existing_files:
    # that one catches an index entry with no file, this one a file
    # with no entry, which `list-codex` would skip silently.
    shipped = {os.path.basename(path)[:-len(EXT)]
               for path in CODEX_BLUEPRINTS}
    assert sorted(shipped - set(_index()["blueprints"])) == [], (
        "these codex blueprints ship with no codex.json entry; "
        "list_builtin_blueprints reads that index, so an unindexed "
        "blueprint is invisible wherever the fallback scan is not "
        "reached.")


def test_the_index_carries_only_the_blocks_that_ship():
    # Trimmed 2026-07-27: a `media` block listing 2 of the 4 media
    # the codex blueprints declare, read by nothing. Media are
    # components inside a blueprint (D30) and are derived from it.
    assert sorted(_index()) == ["blueprints", "version"], (
        "codex.json carries a block the code does not read. The "
        "banner scopes the index to blueprint names and "
        "descriptions; widening it means widening that first.")


def test_list_codex_emits_names_and_descriptions_only():
    assert set(list_codex()[0]) == {"name", "description"}, (
        "list_codex grew a field; the record is the --json contract, "
        "and widening it is a surface change.")


def test_builtin_blueprint_index_names_existing_files():
    for name in list_builtin_blueprints():
        assert os.path.isfile(
            os.path.join(_CODEX, "blueprints", f"{name}{EXT}"))


def test_openbsd_blueprint_seed_copies_closure(tmp_path):
    home = str(tmp_path)
    assert seed_blueprint(OPENBSD_BLUEPRINT, context=home)
    assert os.path.isfile(
        os.path.join(home, "blueprints", f"{OPENBSD_BLUEPRINT}{EXT}"))
    assert os.path.isfile(
        os.path.join(home, "scripts", f"{OPENBSD_SCRIPT}.rlqs"))
