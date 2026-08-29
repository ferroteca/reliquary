# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for the reliquary command-line interface."""

import argparse
import contextlib
import inspect
import io
import json
import os
import re
import sys
from unittest import mock

import pytest
from rich import box
from rich.cells import cell_len

from reliquary import cli
from reliquary import backends
from reliquary.backends import Availability
from reliquary.errors import InternalError, exit_code
from tests import fake_backend

_PLAIN = [
    {"type": "machine", "name": "plain", "platform": "dos",
     "devices": {"hdd0": "blank-20m"}},
    {"type": "media", "name": "blank-20m", "materialize": "new",
     "size": "20M"},
]


@pytest.fixture
def bare_home(tmp_path):
    """A home with nothing in it and no backend installed."""
    return str(tmp_path)


@pytest.fixture
def home(tmp_path):
    """A home with the fake backend installed."""
    with fake_backend.installed():
        yield str(tmp_path)


@pytest.fixture
def plain_home(home):
    """A home holding the `plain` blueprint and its blank media."""
    os.makedirs(os.path.join(home, "blueprints"))
    _write_blueprint(home, "plain", _PLAIN)
    return home


def _write_blueprint(home, name, specs):
    path = os.path.join(home, "blueprints", f"{name}.rlqb")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(specs, handle)
    return path


def _out(*argv):
    """Run the CLI, returning (code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(list(argv))
    return code, out.getvalue(), err.getvalue()


def _json_out(home, args):
    code, out, _err = _out("--home-dir", home, *args, "--json")
    return code, out.strip()


def _running_machine(home, name="plain"):
    """Materialize a machine and record a running VM identity."""
    _out("--home-dir", home, "create-machine", "--blueprint", name)
    machine_id = f"{name}-0"
    state_path = os.path.join(home, "cache", "machines", machine_id,
                              "machine.json")
    with open(state_path, encoding="utf-8") as handle:
        state = json.load(handle)
    state["phase"] = "running"
    state["vm"] = backends.identity(
        "qemu", f"reliquary-{machine_id}", "1" * 32, {"port": 4321}, pid=5)
    with open(state_path, "w", encoding="utf-8") as handle:
        json.dump(state, handle)
    return os.path.dirname(state_path)


# list-* report absence, not a bare header.

def test_list_machines_reports_no_machines(home):
    """An empty machine list says so instead of a headerless table."""
    result, out, _err = _out("--home-dir", home, "list-machines")
    assert result == 0
    assert "BLUEPRINT" not in out
    assert "no machines" in out


def test_flag_position_independence(home):
    """Flags like --home-dir work before or after the command."""
    result, out, _err = _out("list-machines", "--home-dir", home)
    assert result == 0
    assert "no machines" in out

    result, out, _err = _out("--home-dir", home, "list-machines")
    assert result == 0
    assert "no machines" in out


def test_list_machines_reports_no_machines_for_blueprint(home):
    """Filtering by a blueprint with no machines names the blueprint."""
    _write_blueprint(home, "plain", _PLAIN)
    result, out, _err = _out("--home-dir", home, "list-machines",
                             "--blueprint", "plain")
    assert result == 0
    assert "BLUEPRINT" not in out
    assert "no machines" in out
    assert "plain" in out


def test_list_blueprints_reports_none_found(home):
    """An empty blueprints directory says so, not silently nothing."""
    result, out, _err = _out("--home-dir", home, "list-blueprints")
    assert result == 0
    assert "no blueprints" in out


def test_list_backends_reports_only_discovered_backends():
    probes = (
        Availability("qemu", True, executable="/opt/qemu/bin/qemu",
                     home="/opt/qemu"),
        Availability("virtualbox", False, detail="not installed"),
    )
    with mock.patch.object(backends, "discover", return_value=probes):
        result, out, _err = _out("list-backends")
    assert result == 0
    assert "qemu" in out
    assert "/opt/qemu" in out
    assert "virtualbox" not in out


def test_list_backends_json_is_the_discovered_records():
    probes = (Availability("qemu", True, home="/opt/qemu"),)
    with mock.patch.object(backends, "discover", return_value=probes):
        result, out, _err = _out("list-backends", "--json")
    assert result == 0
    assert json.loads(out) == [{"backend": "qemu", "home": "/opt/qemu"}]


def test_list_tables_fold_wide_values_on_terminal_cell_boundaries():
    """Rich keeps wide Unicode data readable instead of truncating it."""
    value = "C:\\資料\\" + "ファイル" * 24
    with contextlib.redirect_stdout(io.StringIO()) as stdout:
        cli._print_table(("NAME", "PATH"), [("wide", value)])
    lines = stdout.getvalue().splitlines()
    assert len(lines) > 2
    assert "…" not in stdout.getvalue()
    assert all(cell_len(line) <= 80 for line in lines)


def test_list_tables_use_ascii_borders_without_a_unicode_encoding():
    assert cli._table_box("utf-8") == box.ROUNDED
    assert cli._table_box("cp437") == box.ASCII
    assert cli._table_box(None) == box.ASCII


def test_list_scripts_reports_none_found(home):
    """An empty scripts directory says so, not a bare header."""
    result, out, _err = _out("--home-dir", home, "list-scripts")
    assert result == 0
    assert "NAME" not in out
    assert "no scripts" in out


def test_screen_accepts_home_after_command(home):
    result, _out_text, err = _out("screen", "--home-dir", home)
    # Flags still travel either side of the command word; a
    # guest-console command with no machine selected is refused
    # for the selector, not for the flag order.
    assert result == 2
    assert "--blueprint" in err


# Leading flags are moved after the command word.

def test_moves_leading_home():
    assert cli._reorder_argv(["--home-dir", "/tmp", "list-machines"]) == [
        "list-machines", "--home-dir", "/tmp"]


def test_preserves_command_first():
    assert cli._reorder_argv(["list-machines", "--home-dir", "/tmp"]) == [
        "list-machines", "--home-dir", "/tmp"]


def test_equals_form():
    assert cli._reorder_argv(["--home-dir=/tmp", "list-machines"]) == [
        "list-machines", "--home-dir=/tmp"]


def test_an_unknown_flag_with_a_value_still_finds_the_command():
    # `--qemu` was removed by the spec and lingered in the arity
    # table; deleting it dropped `rlq --qemu foo list-machines`
    # into the unknown-leading-token path, where argparse blamed
    # the *value*: "invalid choice: 'foo'". The scan now looks
    # past an unknown flag's value for a real command word, so
    # the flag that is actually wrong is the one named.
    assert cli._reorder_argv(["--qemu", "foo", "list-machines"]) == [
        "list-machines", "--qemu", "foo"]


def test_a_bare_misspelled_command_still_stops_the_scan():
    # Only a word *after* an unknown flag is skipped. With no
    # unknown flag ahead of it a bare word is the command, and a
    # misspelling must still be reported as the invalid choice
    # it is rather than scanned past.
    assert cli._reorder_argv(["list-machnes", "--home-dir", "/tmp"]) == [
        "list-machnes", "--home-dir", "/tmp"]


def test_removed_globals_are_not_in_the_arity_table():
    # docs/spec/cli.md: the old global --qemu, --platform and
    # --port "are removed". --platform and --port stay in the
    # table as live per-command options; --qemu has no subparser
    # anywhere, so its entry named an option that was gone.
    assert "--qemu" not in cli._FLAG_ARITY
    assert "--platform" in cli._FLAG_ARITY
    # --port went away with the backend adapter boundary: a QMP port
    # is QEMU's own endpoint detail, and no command takes one any
    # more.
    assert "--port" not in cli._FLAG_ARITY


# Usage/help text names whichever entry point was invoked.

def test_reliquary_entry_point():
    with mock.patch.object(sys, "argv", ["/usr/bin/reliquary", "-h"]):
        assert cli._prog_name() == "reliquary"


def test_rlq_entry_point():
    with mock.patch.object(sys, "argv", ["/usr/bin/rlq", "-h"]):
        assert cli._prog_name() == "rlq"


def test_windows_exe_suffix():
    with mock.patch.object(sys, "argv", [r"C:\bin\reliquary.exe", "-h"]):
        assert cli._prog_name() == "reliquary"


def test_unrecognized_invocation_falls_back_to_rlq():
    with mock.patch.object(sys, "argv",
                           ["/usr/bin/python3", "-m", "reliquary"]):
        assert cli._prog_name() == "rlq"


def test_help_text_names_invoking_command():
    for prog in ("reliquary", "rlq"):
        with mock.patch.object(sys, "argv", [prog]), \
                contextlib.redirect_stdout(io.StringIO()) as stdout, \
                pytest.raises(SystemExit):
            cli.main(["-h"])
        assert f"usage: {prog}" in stdout.getvalue()


# create-machine / start-machine / stop-machine / destroy-machine.

def test_create_machine(plain_home):
    result, out, _err = _out("--home-dir", plain_home, "create-machine",
                             "--blueprint", "plain")
    assert result == 0
    assert out.strip() == "plain-0"


def test_create_machine_flags_before_command(plain_home):
    result, out, _err = _out("--home-dir", plain_home,
                             "--blueprint", "plain", "create-machine")
    assert result == 0
    assert out.strip() == "plain-0"


def test_create_machine_dry_run_reports_and_builds_nothing(plain_home):
    result, out, _err = _out("--home-dir", plain_home, "create-machine",
                             "--blueprint", "plain", "--dry-run")
    assert result == 0
    assert "machine: plain-0" in out
    assert "nothing was created." in out
    assert not os.path.exists(os.path.join(plain_home, "cache")), (
        "a dry run at the CLI wrote to the cache")


def test_create_machine_dry_run_json_is_the_document(plain_home):
    result, out = _json_out(
        plain_home, ["create-machine", "--blueprint", "plain", "--dry-run"])
    assert result == 0
    document = json.loads(out)
    assert document["operation"] == "create-machine"
    assert document["plan"]["machine"] == "plain-0"
    assert "report" in document


def test_backend_overrides_the_blueprint_field(plain_home):
    # --backend without --dry-run pins assignment, exactly as a
    # declared backend does: it must be available and capable.
    # The stub vmware claims no capability, so it fails
    # preflight (exit 3) rather than at the static gate (exit 2).
    result, _out_text, err = _out("--home-dir", plain_home,
                                  "create-machine", "--blueprint", "plain",
                                  "--backend", "vmware")
    assert result == 3
    assert "vmware" in err


def test_dry_run_flags_before_command(plain_home):
    result, out, _err = _out("--home-dir", plain_home, "--dry-run",
                             "--blueprint", "plain", "create-machine")
    assert result == 0
    assert "nothing was created." in out


def test_get_machine_dir(plain_home):
    _out("--home-dir", plain_home, "create-machine", "--blueprint", "plain")
    result, out, _err = _out("--home-dir", plain_home, "get-machine-dir",
                             "--machine", "plain-0")
    assert result == 0
    assert "plain-0" in out


def test_recreate_machine(plain_home):
    _out("--home-dir", plain_home, "create-machine", "--blueprint", "plain")
    result, out, _err = _out("--home-dir", plain_home, "recreate-machine",
                             "--machine", "plain-0")
    assert result == 0
    assert out.strip() == "plain-0"


def test_json_create_returns_id_scalar(plain_home):
    result, out = _json_out(plain_home,
                            ["create-machine", "--blueprint", "plain"])
    assert result == 0
    assert json.loads(out) == "plain-0"


def test_json_list_machines_is_array(plain_home):
    _json_out(plain_home, ["create-machine", "--blueprint", "plain"])
    result, out = _json_out(plain_home, ["list-machines"])
    assert result == 0
    data = json.loads(out)
    assert isinstance(data, list)
    assert data[0]["id"] == "plain-0"


def test_json_void_twin_is_empty_object(plain_home):
    _json_out(plain_home, ["create-machine", "--blueprint", "plain"])
    result, out = _json_out(plain_home,
                            ["destroy-machine", "--machine", "plain-0"])
    assert result == 0
    assert json.loads(out) == {}


def test_json_list_codex_carries_the_description(plain_home):
    """The JSON record carries the same field the human-readable
    listing wraps (D97) — both are views of the same data."""
    result, out = _json_out(plain_home, ["list-codex"])
    assert result == 0
    row = next(r for r in json.loads(out) if r["name"] == "freedos")
    assert "FreeDOS" in row["description"]


def test_json_rejected_on_stream_command(plain_home):
    result, _out_text, err = _out("--home-dir", plain_home, "fetch-media",
                                  "x", "--json")
    assert result == 2
    assert "jsonl" in err


def test_json_flag_before_command(plain_home):
    # --json before the command word must reorder correctly.
    result, out, _err = _out("--home-dir", plain_home, "--json",
                             "list-machines")
    assert result == 0
    assert isinstance(json.loads(out), list)


def test_apply_blueprint(plain_home):
    _out("--home-dir", plain_home, "create-machine", "--blueprint", "plain")
    result, out, _err = _out("--home-dir", plain_home, "apply-blueprint",
                             "--machine", "plain-0")
    assert result == 0
    assert out.strip() == "plain-0"


def test_list_machines_table(plain_home):
    """list-machines leads with each machine's durable id."""
    _out("--home-dir", plain_home, "create-machine", "--blueprint", "plain")
    result, out, _err = _out("--home-dir", plain_home, "list-machines")
    assert result == 0
    assert "ID" in out
    assert "BLUEPRINT" not in out
    assert "NUMBER" not in out
    assert "plain-0" in out
    assert "ready" in out


def test_list_codex_names_the_library_and_nothing_of_yours(plain_home):
    """Which command you ran already says where a row came from, so there is no separate provenance column.

    `plain` is this fixture's own blueprint; the library's listing
    must not mention it, and nothing in the output should say where
    a row came from.
    """
    result, out, _err = _out("--home-dir", plain_home, "list-codex")
    assert result == 0
    assert "freedos" in out
    assert "plain" not in out
    assert "PROVENANCE" not in out.upper()


def test_seed_blueprint_only_flag(plain_home):
    result, _out_text, _err = _out("--home-dir", plain_home,
                                   "seed-blueprint", "freedos", "--only")
    assert result == 0
    assert os.path.isfile(
        os.path.join(plain_home, "blueprints", "freedos.rlqb"))
    assert not os.path.isdir(os.path.join(plain_home, "media"))


def test_the_builtin_flag_is_gone_from_both_listings(plain_home):
    """One verb, one set of results: `--builtin` can no longer swap a listing of what you have for a listing of what you do not.

    A flag that flipped between those two listings caused the same
    mixing of "yours" and "the library's" that the provenance column
    caused, one layer down (D88).
    """
    for command in ("list-blueprints", "list-media"):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), \
                contextlib.redirect_stdout(io.StringIO()):
            with pytest.raises(SystemExit) as caught:
                cli.main(["--home-dir", plain_home, command, "--builtin"])
        assert caught.value.code == 2, command
        assert "--builtin" in stderr.getvalue(), command


def test_list_blueprints_default_is_local(plain_home):
    """Default list-blueprints shows the local blueprint and its path."""
    result, out, _err = _out("--home-dir", plain_home, "list-blueprints")
    assert result == 0
    assert "plain" in out
    assert "NAME" in out
    assert "PATH" in out
    # The path itself is asserted through --json: the human table
    # folds a long one across lines, so a contiguous substring is not
    # promised (the same reading the recursive-scan check applies).
    result, listed = _json_out(plain_home, ["list-blueprints"])
    assert result == 0
    assert {row["path"] for row in json.loads(listed)} == {
        os.path.join(plain_home, "blueprints", "plain.rlqb")}


def test_list_blueprints_shows_a_description_in_its_row(plain_home):
    """Descriptions occupy a wrapping cell beside their blueprint."""
    _write_blueprint(plain_home, "told", [
        {"type": "machine", "name": "told", "platform": "dos",
         "description": ("A described machine whose text is long enough "
                         "that the listing has to wrap it across more "
                         "than one indented line beneath the row"),
         "devices": {"hdd0": "blank-20m"}},
        {"type": "media", "name": "blank-20m", "materialize": "new",
         "size": "20M"},
    ])
    result, out, _err = _out("--home-dir", plain_home, "list-blueprints")
    assert result == 0
    assert "DESCRIPTION" in out
    told = next(line for line in out.splitlines() if "told" in line)
    assert "A described machine" in told


def test_json_list_blueprints_carries_description_and_platform(plain_home):
    """The record holds what the human view shows (D97; P6)."""
    result, out = _json_out(plain_home, ["list-blueprints"])
    assert result == 0
    row = next(r for r in json.loads(out) if r["name"] == "plain")
    assert "description" in row
    assert row["description"] is None
    assert row["platform"] == "dos"


def test_list_codex_prints_the_description_in_the_name_row(plain_home):
    """The library table pairs each name with its description."""
    result, out, _err = _out("--home-dir", plain_home, "list-codex")
    assert result == 0
    assert "DESCRIPTION" in out
    freedos = next(line for line in out.splitlines() if "freedos" in line)
    assert "FreeDOS" in freedos


def test_list_blueprints_empty_has_no_column_headers(tmp_path):
    """An empty home reports absence, not a headerless table."""
    result, out, _err = _out("--home-dir", str(tmp_path / "empty"),
                             "list-blueprints")
    assert result == 0
    assert "NAME" not in out
    assert "no blueprints" in out


def test_list_blueprints_scans_the_blueprints_folder_recursively(plain_home):
    """A blueprint nested within blueprints/ is found (home mode)."""
    nested = os.path.join(plain_home, "blueprints", "vendor")
    os.makedirs(nested)
    nested_path = os.path.join(nested, "nested.rlqb")
    with open(nested_path, "w", encoding="utf-8") as handle:
        json.dump({"platform": "dos",
                   "devices": {"hdd": {"size": "20M"}}}, handle)
    # Assert via --json: the human table may fold a long path across
    # lines, so a contiguous "nested.rlqb" substring is not promised.
    result, out = _json_out(plain_home, ["list-blueprints"])
    assert result == 0
    rows = json.loads(out)
    assert os.path.abspath(nested_path) in {row["path"] for row in rows}
    assert "nested" in {row["name"] for row in rows}


def test_list_blueprints_ignores_cache_dir(plain_home):
    """A JSON file under cache/ is never reported as a blueprint."""
    cache_machine_dir = os.path.join(plain_home, "cache", "machines",
                                     "plain-0")
    os.makedirs(cache_machine_dir)
    with open(os.path.join(cache_machine_dir, "state.json"), "w",
              encoding="utf-8") as handle:
        json.dump({"platform": "dos"}, handle)
    result, out, _err = _out("--home-dir", plain_home, "list-blueprints")
    assert result == 0
    assert "cache" not in out


def test_list_blueprints_scans_only_the_blueprints_folder(plain_home):
    """Home mode lists blueprints/ only — files elsewhere are ignored."""
    # A .rlqb outside the canonical folder (here under home root and
    # under a decoy cache/) is never listed: home mode resolves from
    # blueprints/, not by walking the whole home.
    with open(os.path.join(plain_home, "loose.rlqb"), "w",
              encoding="utf-8") as handle:
        json.dump({"platform": "dos"}, handle)
    decoy_cache = os.path.join(plain_home, "cache")
    os.makedirs(decoy_cache)
    with open(os.path.join(decoy_cache, "cached.rlqb"), "w",
              encoding="utf-8") as handle:
        json.dump({"platform": "dos"}, handle)
    result, out, _err = _out("--home-dir", plain_home, "list-blueprints")
    assert result == 0
    assert "plain" in out
    assert "loose" not in out
    assert "cached" not in out


def test_list_blueprints_ignores_unrelated_json(plain_home):
    """A same-extension file without a platform field is skipped."""
    with open(os.path.join(plain_home, "blueprints", "notes.json"), "w",
              encoding="utf-8") as handle:
        json.dump({"items": {}}, handle)
    result, out, _err = _out("--home-dir", plain_home, "list-blueprints")
    assert result == 0
    assert "notes" not in out


def test_delete_blueprint(plain_home):
    result, out, _err = _out("--home-dir", plain_home, "delete-blueprint",
                             "plain")
    assert result == 0
    assert "plain.rlqb" in out
    assert not os.path.exists(
        os.path.join(plain_home, "blueprints", "plain.rlqb"))


def test_delete_blueprint_refuses_while_machines_exist(plain_home):
    _out("--home-dir", plain_home, "create-machine", "--blueprint", "plain")
    result, _out_text, err = _out("--home-dir", plain_home,
                                  "delete-blueprint", "plain")
    assert result == 3
    assert "still has 1 machine(s)" in err
    assert "plain-0" in err


def test_list_media(plain_home):
    _write_blueprint(plain_home, "media-lib", [
        {"type": "media", "name": "livecd",
         "location": {"local": "/x.iso"}}])
    result, out, _err = _out("--home-dir", plain_home, "list-media")
    assert result == 0
    # The namespace lists every media component in the source —
    # yours, and only yours. The codex's media are components of
    # blueprints you have not seeded, and there is no `seed-media`,
    # so nothing lists parts that cannot be ordered (D88).
    assert "livecd" in out
    assert "freedos-livecd" not in out


def test_start_and_stop_via_blueprint_selector(plain_home):
    """--blueprint on start/stop resolves to the one machine that blueprint made.

    The CLI resolves this against the record built from its own flags
    for this one invocation (P26) — there are no process-wide globals
    to fall back on. So a missing --home-dir can never make stop
    target a machine in a different home: same-numbered machines in
    two different homes have the same id, and nothing but the
    session's own record tells them apart.
    """
    _out("--home-dir", plain_home, "create-machine", "--blueprint", "plain")
    with mock.patch("reliquary.session.Session.start_machine") as start:
        result, _out_text, _err = _out("--home-dir", plain_home,
                                       "start-machine",
                                       "--blueprint", "plain")
    assert result == 0
    # The --blueprint selector resolved to plain-0 using --home-dir.
    # The session's own record carries that resolution through.
    start.assert_called_once()
    assert start.call_args.args == ("plain-0",)

    with mock.patch("reliquary.session.Session.stop_machine") as stop:
        result, _out_text, _err = _out("--home-dir", plain_home,
                                       "stop-machine",
                                       "--blueprint", "plain")
    assert result == 0
    stop.assert_called_once_with("plain-0")


def test_stop_via_positional_machine_id(plain_home):
    """stop-machine <id> is a short alias for --machine <id>."""
    _running_machine(plain_home)
    with mock.patch("reliquary.session.Session.stop_machine") as stop:
        result, _out_text, _err = _out("--home-dir", plain_home,
                                       "stop-machine", "plain-0")
    assert result == 0
    stop.assert_called_once_with("plain-0")


def test_destroy_via_machine_id(plain_home):
    """--machine <blueprint>-<n> destroy deletes the machine."""
    _code, out, _err = _out("--home-dir", plain_home, "create-machine",
                            "--blueprint", "plain")
    machine_id = out.split()[-1].strip()
    with mock.patch("reliquary.session.Session.destroy_machine") as destroy:
        result, _out_text, _err = _out("--home-dir", plain_home,
                                       "destroy-machine",
                                       "--machine", machine_id)
    assert result == 0
    destroy.assert_called_once_with(machine_id)


def test_destroy_via_positional_machine_id(plain_home):
    """destroy-machine <id> is a short alias for --machine <id>."""
    _code, out, _err = _out("--home-dir", plain_home, "create-machine",
                            "--blueprint", "plain")
    machine_id = out.split()[-1].strip()
    with mock.patch("reliquary.session.Session.destroy_machine") as destroy:
        result, _out_text, _err = _out("--home-dir", plain_home,
                                       "destroy-machine", machine_id)
    assert result == 0
    destroy.assert_called_once_with(machine_id)


def test_destroy_rejects_blueprint_and_machine_together(plain_home):
    """--blueprint and --machine are mutually exclusive."""
    _out("--home-dir", plain_home, "create-machine", "--blueprint", "plain")
    _out("--home-dir", plain_home, "create-machine", "--blueprint", "plain")
    result, _out_text, err = _out("--home-dir", plain_home,
                                  "destroy-machine",
                                  "--blueprint", "plain",
                                  "--machine", "plain-1")
    assert result == 2
    assert "mutually exclusive" in err


def test_list_scripts_default_lists_shared_dir(plain_home):
    """list-scripts without --blueprint lists scripts/ directory."""
    scripts = os.path.join(plain_home, "scripts")
    os.makedirs(scripts)
    with open(os.path.join(scripts, "alpha.rlqs"), "w",
              encoding="utf-8") as handle:
        handle.write('description "Alpha script"\n'
                     'platform dos\n'
                     'type "hello"\n')
    result, out, _err = _out("--home-dir", plain_home, "list-scripts")
    assert result == 0
    assert "NAME" in out
    assert "PATH" in out
    assert "alpha" in out
    assert "DESCRIPTION" in out
    alpha = next(line for line in out.splitlines() if "alpha" in line)
    assert "Alpha script" in alpha
    result, listed = _json_out(plain_home, ["list-scripts"])
    assert result == 0
    assert json.loads(listed)[0]["description"] == "Alpha script"


def test_list_scripts_with_blueprint_uses_scripts_map(plain_home):
    """list-scripts --blueprint reads the blueprint's scripts map."""
    scripts = os.path.join(plain_home, "scripts")
    os.makedirs(scripts)
    _write_blueprint(plain_home, "cust", [
        {"type": "machine", "name": "cust", "platform": "dos",
         "devices": {"hdd0": "blank"},
         "scripts": {"setup": "cust-setup", "teardown": "cust-teardown"}},
        {"type": "media", "name": "blank", "materialize": "new",
         "size": "20M"},
    ])
    with open(os.path.join(scripts, "cust-setup.rlqs"), "w",
              encoding="utf-8") as handle:
        handle.write('description "Custom setup"\n'
                     'platform dos\n'
                     'type "hello"\n')
    with open(os.path.join(scripts, "cust-teardown.rlqs"), "w",
              encoding="utf-8") as handle:
        handle.write('platform dos\n'
                     'type "bye"\n')
    result, out, _err = _out("--home-dir", plain_home, "list-scripts",
                             "--blueprint", "cust")
    assert result == 0
    assert "LABEL" in out
    assert "STEM" in out
    assert "setup" in out
    assert "cust-setup" in out
    assert "teardown" in out
    assert "DESCRIPTION" in out
    setup = next(line for line in out.splitlines() if "setup" in line)
    assert "Custom setup" in setup
    lines = out.splitlines()
    teardown_at = next(index for index, line in enumerate(lines)
                       if "teardown" in line)
    assert "Custom setup" not in lines[teardown_at]


def test_start_without_selector_errors(plain_home):
    """The legacy root-home start path is gone: a selector is required."""
    result, _out_text, err = _out("--home-dir", plain_home, "start-machine")
    assert result == 2
    assert "--blueprint" in err


def test_type_sends_without_enter(plain_home):
    machine_home = _running_machine(plain_home)
    with mock.patch("reliquary.cli.send_text") as send:
        result, _out_text, _err = _out("--home-dir", plain_home, "type",
                                       "A:", "--machine", "plain-0")
    assert result == 0
    send.assert_called_once_with("A:", enter=False, home=machine_home)


def test_enter_sends_with_enter(plain_home):
    machine_home = _running_machine(plain_home)
    with mock.patch("reliquary.cli.send_text") as send:
        result, _out_text, _err = _out("--home-dir", plain_home, "enter",
                                       "dir", "--machine", "plain-0")
    assert result == 0
    send.assert_called_once_with("dir", enter=True, home=machine_home)


def test_press_translates_portable_keys(plain_home):
    machine_home = _running_machine(plain_home)
    with mock.patch("reliquary.cli.send_keys") as send:
        result, _out_text, _err = _out("--home-dir", plain_home, "press",
                                       "enter", "ctrl+c",
                                       "--machine", "plain-0")
    assert result == 0
    send.assert_called_once_with([["ret"], ["ctrl", "c"]],
                                 home=machine_home)


def test_a_selected_machine_carries_its_directory(plain_home):
    """The machine's own directory is the whole address needed.

    It is where the recorded VM identity lives, so without it a
    guest-console command could not verify which machine it is
    actually talking to. There is no port to pass instead — that is
    the backend adapter's own detail, on the other side of that
    boundary.
    """
    machine_home = _running_machine(plain_home)
    with mock.patch("reliquary.cli.screen_text",
                    return_value=["ok"]) as screen:
        result, _out_text, _err = _out("--home-dir", plain_home, "screen",
                                       "--machine", "plain-0")
    assert result == 0
    assert screen.call_args.kwargs == {"home": machine_home}
    assert machine_home.endswith("plain-0")


# `wait` is the script language's verb: its conditions are parsed by
# the language's own parser and translated down to calls on the
# machine handle (D116).

@pytest.mark.parametrize("text,expected", [
    ("C:\\>", ("screen", re.escape("C:\\>"))),
    ("Welcome    to   FreeDOS", ("screen", re.escape("Welcome to FreeDOS"))),
    ('say "hi"', ("screen", re.escape('say "hi"'))),
    ('"C:\\>"', ("screen", re.escape("C:\\>"))),
    ("/installed [0-9]+ of [0-9]+/", ("screen", "installed [0-9]+ of [0-9]+")),
    ("machine=stopped", ("machine", None)),
], ids=["bare-literal", "normalized", "embedded-quote", "quoted-through",
        "regex", "machine-channel"])
def test_a_wait_condition_is_the_languages_spelling_less_the_shells_quotes(
        text, expected):
    assert cli._wait_condition(text) == expected


def test_a_wait_condition_refuses_what_the_language_refuses():
    with pytest.raises(cli.StaticError, match="not a wait condition"):
        cli._wait_condition("/unterminated")
    with pytest.raises(cli.StaticError, match="property reference"):
        cli._wait_condition("${prompt}")


def test_wait_lowers_a_literal_and_drives_the_handle(plain_home):
    machine_home = _running_machine(plain_home)
    with mock.patch("reliquary.cli.wait_text") as wait:
        result, _o, err = _out("--home-dir", plain_home, "wait", "C:\\>",
                               "--machine", "plain-0", "--timeout", "30")
    assert result == 0
    wait.assert_called_once_with(re.escape("C:\\>"), 30, home=machine_home)
    assert "matched" in err


def test_an_expired_wait_names_the_condition_as_typed(plain_home):
    from reliquary.errors import WaitExpired
    _running_machine(plain_home)
    lowered = re.escape("NOT ON SCREEN")
    with mock.patch("reliquary.cli.wait_text",
                    side_effect=WaitExpired(
                        f"timed out after 3s waiting for screen to match: "
                        f"{lowered}", rule_id="screen.no-match")):
        result, _o, err = _out("--home-dir", plain_home, "wait",
                               "NOT ON SCREEN", "--machine", "plain-0")
    assert result == 4
    assert "match: NOT ON SCREEN" in err
    assert lowered not in err


def test_wait_on_the_machine_channel_observes_then_marks(plain_home):
    _running_machine(plain_home)
    with mock.patch("reliquary.machine_handle.Machine.wait_stopped") as gone, \
            mock.patch("reliquary.session.Session.mark_stopped") as mark:
        result, _o, err = _out("--home-dir", plain_home, "wait",
                               "machine=stopped", "--machine", "plain-0")
    assert result == 0
    gone.assert_called_once_with(60)
    mark.assert_called_once_with("plain-0")
    assert "stopped" in err


def test_wait_on_the_machine_channel_is_satisfied_by_a_stopped_machine(
        plain_home):
    # a shell that starts the wait a moment late is answered, not
    # refused: the machine *is* stopped
    _out("--home-dir", plain_home, "create-machine", "--blueprint", "plain")
    with mock.patch("reliquary.machine_handle.Machine.wait_stopped") as gone:
        result, _o, err = _out("--home-dir", plain_home, "wait",
                               "machine=stopped", "--blueprint", "plain")
    assert result == 0
    gone.assert_not_called()
    assert "stopped" in err


def test_clean_media_passes_an_optional_name(plain_home):
    with mock.patch("reliquary.session.Session.clean_media",
                    return_value=[]) as clean:
        assert _out("clean-media", "--home-dir", plain_home)[0] == 0
        clean.assert_called_once_with(None)
        clean.reset_mock()
        assert _out("clean-media", "livecd",
                    "--home-dir", plain_home)[0] == 0
        clean.assert_called_once_with("livecd")


def test_prune_media_dry_run_reports_without_pruning(plain_home):
    with mock.patch("reliquary.session.Session.prune_media",
                    return_value=["husk"]) as prune:
        code, out, _err = _out("prune-media", "--dry-run",
                               "--home-dir", plain_home)
    assert code == 0
    prune.assert_called_once_with(dry_run=True)
    assert "husk" in out


def test_add_media_writes_a_declaration_for_a_local_file(plain_home):
    payload = os.path.join(plain_home, "supplied.iso")
    with open(payload, "wb") as handle:
        handle.write(b"ISO")
    code, out, _err = _out("add-media", "win", payload,
                           "--home-dir", plain_home)
    assert code == 0
    written = out.strip()
    assert written.endswith("win.rlqb")
    assert os.path.isfile(written)
    # The file it declares is left exactly where the user had it.
    assert os.path.isfile(payload)


# The exec-run commands: machine variables and live media.

@pytest.fixture
def rig_home(home):
    """A created `rig` machine with a directory-source floppy."""
    exchange = os.path.join(home, "exchange")
    os.makedirs(exchange)
    os.makedirs(os.path.join(home, "blueprints"))
    _write_blueprint(home, "rig", [
        {"type": "machine", "name": "rig", "platform": "dos",
         "devices": {"hdd0": "blank-20m", "floppy0": "exchange-dir"}},
        {"type": "media", "name": "blank-20m", "materialize": "new",
         "size": "20M"},
        {"type": "media", "name": "exchange-dir", "materialize": "use",
         "location": {"local": exchange}},
    ])
    _out("--home-dir", home, "create-machine", "--blueprint", "rig")
    return home, exchange


def test_get_machine_var_reads_what_a_script_set(rig_home):
    from reliquary.machines import set_machine_var
    home, _exchange = rig_home
    set_machine_var("rig-0", "result", "PASS", context=home)
    code, out, _err = _out("--home-dir", home, "get-machine-var", "result",
                           "--machine", "rig-0")
    assert code == 0
    assert out.strip() == "PASS"


def test_an_unset_variable_prints_nothing_and_succeeds(rig_home):
    home, _exchange = rig_home
    code, out, _err = _out("--home-dir", home, "get-machine-var", "ready",
                           "--machine", "rig-0")
    assert code == 0
    assert out == ""


def test_an_unset_variable_is_null_under_json(rig_home):
    home, _exchange = rig_home
    code, out, _err = _out("--home-dir", home, "get-machine-var", "ready",
                           "--machine", "rig-0", "--json")
    assert code == 0
    assert json.loads(out) is None


def test_insert_media_mounts_a_file_by_path(rig_home):
    from reliquary.machines import load_machine_state
    home, _exchange = rig_home
    image = os.path.join(home, "round-1.img")
    with open(image, "wb") as handle:
        handle.write(b"BINARY")
    code, out, err = _out("--home-dir", home, "insert-media", "floppy0",
                          "--file", image, "--machine", "rig-0")
    assert code == 0
    # A void twin: the narration is stderr, stdout stays empty.
    assert out == ""
    assert image in err
    floppy = load_machine_state("rig-0", home)["devices"]["floppy0"]
    assert floppy["media"] is None
    assert os.path.normpath(floppy["path"]) == os.path.normpath(image)


# The invocation's record: flags, then environment, then default.
#
# ``adopt_environment()`` no longer runs on the CLI path — the CLI
# builds one ``Context`` per invocation and opens a session on it
# (P26) — so the environment-handling behavior this suite used to
# verify through home.py is tested here instead, directly against
# ``main()``.

def test_the_environment_names_the_home(bare_home, monkeypatch):
    monkeypatch.setenv("RELIQUARY_HOME", bare_home)
    result, out, _err = _out("list-blueprints")
    assert result == 0
    assert "(no blueprints)" in out


def test_the_former_home_variable_is_accepted_as_a_fallback(bare_home,
                                                            monkeypatch):
    # Clear the documented spelling so this actually exercises the
    # former name — otherwise a process-level RELIQUARY_HOME would
    # beat it and the assertion would be about the wrong home.
    monkeypatch.delenv("RELIQUARY_HOME", raising=False)
    monkeypatch.setenv("RELIQUARY_HOME_DIR", bare_home)
    result, out, _err = _out("list-blueprints")
    assert result == 0
    assert "(no blueprints)" in out


def test_the_documented_home_variable_beats_the_former_spelling(
        bare_home, monkeypatch):
    former = os.path.join(bare_home, "former-home")
    monkeypatch.setenv("RELIQUARY_HOME", bare_home)
    monkeypatch.setenv("RELIQUARY_HOME_DIR", former)
    result, _out_text, _err = _out("new-blueprint", "documented")
    assert result == 0
    assert os.path.isfile(
        os.path.join(bare_home, "blueprints", "documented.rlqb"))
    assert not os.path.exists(former)


def test_a_flag_beats_the_environment(bare_home, monkeypatch):
    decoy = os.path.join(bare_home, "env-home")
    monkeypatch.setenv("RELIQUARY_HOME", decoy)
    result, _out_text, _err = _out("--home-dir", bare_home,
                                   "new-blueprint", "flagged")
    assert result == 0
    assert os.path.isfile(
        os.path.join(bare_home, "blueprints", "flagged.rlqb"))
    assert not os.path.exists(decoy)


def test_the_environment_selects_the_properties_file(bare_home,
                                                     monkeypatch):
    selected = os.path.join(bare_home, "proj.properties")
    monkeypatch.setenv("RELIQUARY_PROPERTIES", selected)
    result, _out_text, _err = _out("--home-dir", bare_home, "set-property",
                                   "env.selected", "yes")
    assert result == 0
    assert os.path.isfile(selected)
    assert not os.path.isfile(os.path.join(bare_home, "user.properties"))


# --progress selects the rendering; jsonl owns stdout alone.

def test_fetch_media_forwards_the_mode(home):
    with mock.patch("reliquary.session.Session.fetch_media") as fetch:
        code, _out_text, _err = _out("--home-dir", home, "fetch-media",
                                     "livecd", "--progress", "jsonl")
    assert code == 0
    fetch.assert_called_once_with("livecd", progress="jsonl")


def test_fetch_media_rejects_json(home):
    code, _out_text, err = _out("--home-dir", home, "fetch-media",
                                "livecd", "--json")
    assert code == 2
    assert "--progress jsonl" in err


def test_an_unknown_mode_is_refused_by_the_parser(home):
    with contextlib.redirect_stderr(io.StringIO()):
        with pytest.raises(SystemExit):
            cli.main(["--home-dir", home, "fetch-media", "x",
                      "--progress", "fancy"])


# A registered command with no dispatch arm is loud, not silent.
#
# The routing is a chain of literal command names, kept in step with
# the registered parsers by hand. A command that lost its arm used to
# fall through to ``return 0`` — success reported for work that never
# happened, which is worse than any refusal.

def test_an_unrouted_command_is_an_internal_error():
    arguments = argparse.Namespace(command="not-a-command")
    with mock.patch.object(cli, "_interaction_target",
                           return_value="unused"):
        with pytest.raises(InternalError) as caught:
            cli._dispatch(arguments, session=None, context=None)
    assert "not-a-command" in str(caught.value)


def test_the_fault_exits_one():
    """It is a fault, so it takes the code faults take."""
    assert exit_code(InternalError("x")) == 1


# The registered commands and the routed commands must always match.
#
# Two lists of the same roughly 48 command names exist in this
# module, and only one is generated: ``_COMMANDS`` is read directly
# off the built parser, while ``_dispatch`` routes by comparing
# literal strings that nothing else checks against the parser. A
# command registered with no matching arm in ``_dispatch`` reaches
# the fall-through and raises — better than the silent success it
# used to report, but still something someone running the command
# would only discover the hard way. These tests catch the mismatch
# earlier, before anyone runs the command.
#
# Walking the source to find the arms follows the same approach as
# ``test_errors.py``, which walks every ``raise`` in the package for
# the same reason.

def _routed():
    source = inspect.getsource(cli._dispatch)
    return set(re.findall(r'arguments\.command == "([a-z-]+)"', source))


def test_every_registered_command_is_routed():
    unrouted = sorted(set(cli._COMMANDS) - _routed())
    assert unrouted == [], (
        f"{unrouted} are registered commands _dispatch does not route; "
        "each would reach the fall-through and raise.")


def test_every_routed_command_is_registered():
    unregistered = sorted(_routed() - set(cli._COMMANDS))
    assert unregistered == [], (
        f"{unregistered} are routed by _dispatch and registered by no "
        "parser — dead arms, or a command word that moved.")
