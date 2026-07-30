# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for the reliquary command-line interface."""

import contextlib
import io
import json
import os
import re
import sys
import tempfile
import unittest
from unittest import mock

import importlib

home = importlib.import_module("reliquary.home")
from reliquary import cli
from reliquary import backends
from reliquary_tests import fake_backend

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SPEC_DIR = os.path.join(_REPO_ROOT, "docs", "spec")
_CLI_SPEC = os.path.join(_SPEC_DIR, "cli.md")
_COMMAND_WORD = re.compile(r"[a-z][a-z-]+")


def _specified_commands(text):
    """Every command word the CLI spec writes after ``rlq``.

    Synopses and worked examples share one shape — a line starting
    ``rlq``, then the command — so both are read. An alternation
    (``rlq (seed-blueprint | seed-script) <name>``) contributes each
    branch. Anything that is not a bare lowercase word (a flag, a
    placeholder, a shell fragment) is not a command.
    """
    found = set()
    for line in text.splitlines():
        line = line.strip().lstrip("$ ").strip()
        if not line.startswith("rlq "):
            continue
        rest = line[4:].strip()
        if rest.startswith("("):
            inner = rest[1:rest.index(")")] if ")" in rest else ""
            found.update(part.strip() for part in inner.split("|")
                         if _COMMAND_WORD.fullmatch(part.strip()))
            continue
        words = rest.split()
        if words and _COMMAND_WORD.fullmatch(words[0]):
            found.add(words[0])
    return found


@unittest.skipUnless(os.path.isfile(_CLI_SPEC),
                     "the CLI spec is source-tree only")
class ClaimedCommandTests(unittest.TestCase):
    """The CLI spec and the CLI carry the same command inventory.

    P24 asks that every interface be tested against its
    specification, and the CLI's inventory is the part of that a
    machine can check. It is not hypothetical: on 2026-07-27 this
    check found five commands specified and absent
    (`clone-machine`, `export-machine`, `export-drive`,
    `search-media`, `search-scripts`, plus the already-filed
    `clean-archives`) and five present and unspecified
    (`add-media`, `prune-media`, `put-file`, `get-file`,
    `get-machine-var`) — one of which a careful hand audit the same
    day had missed.
    """

    def _spec(self):
        with open(_CLI_SPEC, encoding="utf-8") as handle:
            return _specified_commands(handle.read())

    @staticmethod
    def _every_spec():
        """Command words written after ``rlq`` anywhere in docs/spec.

        Scoped to cli.md, this check had a blind spot that hid a
        second copy of the very defect it was written for: on
        2026-07-27 `instance-model.md` still carried
        `clone-machine`, `export-drive` and `export-machine` in a
        command synopsis, contradicting its own banner, which said
        clone and export were unbuilt. Every spec is read now.
        """
        found = {}
        for name in sorted(os.listdir(_SPEC_DIR)):
            if not name.endswith(".md"):
                continue
            with open(os.path.join(_SPEC_DIR, name),
                      encoding="utf-8") as handle:
                for command in _specified_commands(handle.read()):
                    found.setdefault(command, []).append(name)
        return found

    def test_no_spec_writes_a_command_that_does_not_exist(self):
        # Forward only. The reverse -- that every command is
        # documented -- stays cli.md's below: another spec is free
        # to mention the commands its own subject touches and no
        # more, but none of them may name one that is not there.
        absent = {command: where
                  for command, where in self._every_spec().items()
                  if command not in cli._COMMANDS}
        self.assertEqual(
            absent, {},
            f"these specs write commands the CLI does not have: "
            f"{absent}. A spec states what exists; unbuilt "
            "capability belongs in planning/proposed/FEATURES.md.")

    def test_every_command_is_documented(self):
        undocumented = sorted(set(cli._COMMANDS) - self._spec())
        self.assertEqual(
            undocumented, [],
            "these commands ship undocumented in docs/spec/cli.md: "
            f"{undocumented}. The CLI is a primary interface and the "
            "spec is what it answers to.")


class CliEmptyListingTests(unittest.TestCase):
    """list-* report absence, not a bare header."""

    def setUp(self):
        saved = dict(home._globals)
        self.addCleanup(home._globals.update, saved)
        self.workdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.workdir.cleanup)
        self.home = self.workdir.name
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        self.backend = stack.enter_context(fake_backend.installed())

    def test_list_machines_reports_no_machines(self):
        """An empty machine list says so instead of a headerless table."""
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main(["--home-dir", self.home, "list-machines"])
        self.assertEqual(result, 0)
        output = stdout.getvalue()
        self.assertNotIn("BLUEPRINT", output)
        self.assertIn("no machines", output)

    def test_flag_position_independence(self):
        """Flags like --home-dir work before or after the command."""
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main(["list-machines", "--home-dir", self.home])
        self.assertEqual(result, 0)
        self.assertIn("no machines", stdout.getvalue())

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main(["--home-dir", self.home, "list-machines"])
        self.assertEqual(result, 0)
        self.assertIn("no machines", stdout.getvalue())

    def test_list_machines_reports_no_machines_for_blueprint(self):
        """Filtering by a blueprint with no machines names the blueprint."""
        os.makedirs(os.path.join(self.home, "blueprints"))
        with open(os.path.join(self.home, "blueprints", "plain.rlqb"),
                  "w", encoding="utf-8") as handle:
            json.dump([
                {"type": "machine", "name": "plain", "platform": "dos",
                 "drives": {"hdd0": "blank-20m"}},
                {"type": "media", "name": "blank-20m",
                 "materialize": "new", "size": "20M"},
            ], handle)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main([
                "--home-dir", self.home, "list-machines",
                "--blueprint", "plain",
            ])
        self.assertEqual(result, 0)
        output = stdout.getvalue()
        self.assertNotIn("BLUEPRINT", output)
        self.assertIn("no machines", output)
        self.assertIn("plain", output)

    def test_list_blueprints_reports_none_found(self):
        """An empty blueprints directory says so, not silently nothing."""
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main(["--home-dir", self.home, "list-blueprints"])
        self.assertEqual(result, 0)
        self.assertIn("no blueprints", stdout.getvalue())

    def test_list_scripts_reports_none_found(self):
        """An empty scripts directory says so, not a bare header."""
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main(["--home-dir", self.home, "list-scripts"])
        self.assertEqual(result, 0)
        output = stdout.getvalue()
        self.assertNotIn("NAME", output)
        self.assertIn("no scripts", output)

    def test_screen_accepts_home_after_command(self):
        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            result = cli.main(["screen", "--home-dir", self.home])
        # Flags still travel either side of the command word; a
        # guest-console command with no machine selected is refused
        # for the selector, not for the flag order.
        self.assertEqual(result, 2)
        self.assertIn("--blueprint", stderr.getvalue())


class CliReorderArgvTests(unittest.TestCase):
    """Leading flags are moved after the command word."""

    def test_moves_leading_home(self):
        self.assertEqual(
            cli._reorder_argv(["--home-dir", "/tmp", "list-machines"]),
            ["list-machines", "--home-dir", "/tmp"])

    def test_preserves_command_first(self):
        self.assertEqual(
            cli._reorder_argv(["list-machines", "--home-dir", "/tmp"]),
            ["list-machines", "--home-dir", "/tmp"])

    def test_equals_form(self):
        self.assertEqual(
            cli._reorder_argv(["--home-dir=/tmp", "list-machines"]),
            ["list-machines", "--home-dir=/tmp"])

    def test_an_unknown_flag_with_a_value_still_finds_the_command(self):
        # `--qemu` was removed by the spec and lingered in the arity
        # table; deleting it dropped `rlq --qemu foo list-machines`
        # into the unknown-leading-token path, where argparse blamed
        # the *value*: "invalid choice: 'foo'". The scan now looks
        # past an unknown flag's value for a real command word, so
        # the flag that is actually wrong is the one named.
        self.assertEqual(
            cli._reorder_argv(["--qemu", "foo", "list-machines"]),
            ["list-machines", "--qemu", "foo"])

    def test_a_bare_misspelled_command_still_stops_the_scan(self):
        # Only a word *after* an unknown flag is skipped. With no
        # unknown flag ahead of it a bare word is the command, and a
        # misspelling must still be reported as the invalid choice
        # it is rather than scanned past.
        self.assertEqual(
            cli._reorder_argv(["list-machnes", "--home-dir", "/tmp"]),
            ["list-machnes", "--home-dir", "/tmp"])

    def test_removed_globals_are_not_in_the_arity_table(self):
        # docs/spec/cli.md: the old global --qemu, --platform and
        # --port "are removed". --platform and --port stay in the
        # table as live per-command options; --qemu has no subparser
        # anywhere, so its entry named an option that was gone.
        self.assertNotIn("--qemu", cli._FLAG_ARITY)
        self.assertIn("--platform", cli._FLAG_ARITY)
        # --port went with the adapter seam: a QMP port is QEMU's own
        # endpoint detail, and no command takes one any more.
        self.assertNotIn("--port", cli._FLAG_ARITY)


class CliProgNameTests(unittest.TestCase):
    """Usage/help text names whichever entry point was invoked."""

    def test_reliquary_entry_point(self):
        with mock.patch.object(
                sys, "argv", ["/usr/bin/reliquary", "-h"]):
            self.assertEqual(cli._prog_name(), "reliquary")

    def test_rlq_entry_point(self):
        with mock.patch.object(sys, "argv", ["/usr/bin/rlq", "-h"]):
            self.assertEqual(cli._prog_name(), "rlq")

    def test_windows_exe_suffix(self):
        with mock.patch.object(
                sys, "argv", [r"C:\bin\reliquary.exe", "-h"]):
            self.assertEqual(cli._prog_name(), "reliquary")

    def test_unrecognized_invocation_falls_back_to_rlq(self):
        with mock.patch.object(
                sys, "argv", ["/usr/bin/python3", "-m", "reliquary"]):
            self.assertEqual(cli._prog_name(), "rlq")

    def test_help_text_names_invoking_command(self):
        for prog in ("reliquary", "rlq"):
            with mock.patch.object(sys, "argv", [prog]), \
                    contextlib.redirect_stdout(io.StringIO()) as stdout, \
                    self.assertRaises(SystemExit):
                cli.main(["-h"])
            self.assertIn(f"usage: {prog}", stdout.getvalue())


class CliMachineLifecycleTests(unittest.TestCase):
    """create-machine / start-machine / stop-machine / destroy-machine."""

    def setUp(self):
        saved = dict(home._globals)
        self.addCleanup(home._globals.update, saved)
        self.workdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.workdir.cleanup)
        self.home = self.workdir.name
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        self.backend = stack.enter_context(fake_backend.installed())
        os.makedirs(os.path.join(self.home, "blueprints"))
        with open(os.path.join(self.home, "blueprints", "plain.rlqb"),
                  "w", encoding="utf-8") as handle:
            json.dump([
                {"type": "machine", "name": "plain", "platform": "dos",
                 "drives": {"hdd0": "blank-20m"}},
                {"type": "media", "name": "blank-20m",
                 "materialize": "new", "size": "20M"},
            ], handle)

    def _running_machine(self, name="plain"):
        """Materialize a machine and record a running VM identity."""
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            cli.main(["--home-dir", self.home, "create-machine",
                      "--blueprint", name])
        machine_id = f"{name}-0"
        state_path = os.path.join(
            self.home, "cache", "machines", machine_id, "machine.json")
        with open(state_path, encoding="utf-8") as handle:
            state = json.load(handle)
        state["phase"] = "running"
        state["vm"] = backends.identity(
            "qemu", f"reliquary-{machine_id}", "1" * 32, {"port": 4321},
            pid=5)
        with open(state_path, "w", encoding="utf-8") as handle:
            json.dump(state, handle)
        return os.path.dirname(state_path)

    def test_create_machine(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main([
                "--home-dir", self.home,
                "create-machine",
                "--blueprint", "plain",
            ])
        self.assertEqual(result, 0)
        self.assertEqual(stdout.getvalue().strip(), "plain-0")

    def test_create_machine_flags_before_command(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main([
                "--home-dir", self.home,
                "--blueprint", "plain",
                "create-machine",
            ])
        self.assertEqual(result, 0)
        self.assertEqual(stdout.getvalue().strip(), "plain-0")

    def test_create_machine_dry_run_reports_and_builds_nothing(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main([
                "--home-dir", self.home,
                "create-machine", "--blueprint", "plain", "--dry-run",
            ])
        self.assertEqual(result, 0)
        printed = stdout.getvalue()
        self.assertIn("machine: plain-0", printed)
        self.assertIn("nothing was created.", printed)
        self.assertFalse(
            os.path.exists(os.path.join(self.home, "cache")),
            "a dry run at the CLI wrote to the cache")

    def test_create_machine_dry_run_json_is_the_document(self):
        result, out = self._json_out(
            ["create-machine", "--blueprint", "plain", "--dry-run"])
        self.assertEqual(result, 0)
        document = json.loads(out)
        self.assertEqual("create-machine", document["operation"])
        self.assertEqual("plain-0", document["plan"]["machine"])
        self.assertIn("report", document)

    def test_backend_needs_dry_run(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            result = cli.main([
                "--home-dir", self.home,
                "create-machine", "--blueprint", "plain",
                "--backend", "vmware",
            ])
        self.assertEqual(result, 2)
        self.assertIn("--dry-run", stderr.getvalue())

    def test_dry_run_flags_before_command(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main([
                "--home-dir", self.home, "--dry-run",
                "--blueprint", "plain", "create-machine",
            ])
        self.assertEqual(result, 0)
        self.assertIn("nothing was created.", stdout.getvalue())

    def test_get_machine_dir(self):
        with contextlib.redirect_stdout(io.StringIO()):
            cli.main(["--home-dir", self.home, "create-machine",
                      "--blueprint", "plain"])
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main(["--home-dir", self.home, "get-machine-dir",
                               "--machine", "plain-0"])
        self.assertEqual(result, 0)
        self.assertIn("plain-0", stdout.getvalue())

    def test_recreate_machine(self):
        with contextlib.redirect_stdout(io.StringIO()):
            cli.main(["--home-dir", self.home, "create-machine",
                      "--blueprint", "plain"])
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main(["--home-dir", self.home, "recreate-machine",
                               "--machine", "plain-0"])
        self.assertEqual(result, 0)
        self.assertEqual(stdout.getvalue().strip(), "plain-0")

    def _json_out(self, args):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main(["--home-dir", self.home] + args + ["--json"])
        return result, stdout.getvalue().strip()

    def test_json_create_returns_id_scalar(self):
        result, out = self._json_out(
            ["create-machine", "--blueprint", "plain"])
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(out), "plain-0")

    def test_json_list_machines_is_array(self):
        self._json_out(["create-machine", "--blueprint", "plain"])
        result, out = self._json_out(["list-machines"])
        self.assertEqual(result, 0)
        data = json.loads(out)
        self.assertIsInstance(data, list)
        self.assertEqual(data[0]["id"], "plain-0")

    def test_json_void_twin_is_empty_object(self):
        self._json_out(["create-machine", "--blueprint", "plain"])
        result, out = self._json_out(
            ["destroy-machine", "--machine", "plain-0"])
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(out), {})

    def test_json_list_codex_carries_the_description(self):
        """The human table prints names; the record keeps the rest.

        Which is the whole of the deferral (T8): a description is data
        the JSON has always been able to carry, and only the column is
        unspecified.
        """
        result, out = self._json_out(["list-codex"])
        self.assertEqual(result, 0)
        rows = json.loads(out)
        row = next(r for r in rows if r["name"] == "freedos")
        self.assertIn("FreeDOS", row["description"])

    def test_json_rejected_on_stream_command(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            result = cli.main(["--home-dir", self.home, "fetch-media",
                               "x", "--json"])
        self.assertEqual(result, 2)
        self.assertIn("jsonl", stderr.getvalue())

    def test_json_flag_before_command(self):
        # --json before the command word must reorder correctly.
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            rc = cli.main(["--home-dir", self.home, "--json", "list-machines"])
        self.assertEqual(rc, 0)
        self.assertIsInstance(json.loads(stdout.getvalue()), list)

    def test_apply_blueprint(self):
        with contextlib.redirect_stdout(io.StringIO()):
            cli.main(["--home-dir", self.home, "create-machine",
                      "--blueprint", "plain"])
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main(["--home-dir", self.home, "apply-blueprint",
                               "--machine", "plain-0"])
        self.assertEqual(result, 0)
        self.assertEqual(stdout.getvalue().strip(), "plain-0")

    def test_list_machines_table(self):
        """list-machines prints blueprint, number, phase, and backend."""
        with contextlib.redirect_stdout(io.StringIO()):
            cli.main([
                "--home-dir", self.home,
                "create-machine",
                "--blueprint", "plain",
            ])
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main([
                "--home-dir", self.home, "list-machines",
            ])
        self.assertEqual(result, 0)
        output = stdout.getvalue()
        self.assertIn("BLUEPRINT", output)
        self.assertIn("plain", output)
        self.assertIn("ready", output)

    def test_list_codex_names_the_library_and_nothing_of_yours(self):
        """Which command you ran is the provenance, so no column is.

        `plain` is this fixture's own blueprint; the library's listing
        must not mention it, and there is no value anywhere saying
        where a row came from.
        """
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main(["--home-dir", self.home, "list-codex"])
        self.assertEqual(result, 0)
        output = stdout.getvalue()
        self.assertIn("freedos", output)
        self.assertNotIn("plain", output)
        self.assertNotIn("PROVENANCE", output.upper())

    def test_seed_blueprint_only_flag(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main(["--home-dir", self.home, "seed-blueprint",
                               "freedos", "--only"])
        self.assertEqual(result, 0)
        self.assertTrue(os.path.isfile(os.path.join(
            self.home, "blueprints", "freedos.rlqb")))
        self.assertFalse(os.path.isdir(os.path.join(self.home, "media")))

    def test_the_builtin_flag_is_gone_from_both_listings(self):
        """One verb, one set: `--builtin` no longer turns yours into its.

        A flag that flipped a listing of what you have into a listing
        of what you do not was the same mixing the provenance column
        carried, one layer down (D88).
        """
        for command in ("list-blueprints", "list-media"):
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr), \
                    contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    cli.main([
                        "--home-dir", self.home, command, "--builtin"])
            self.assertEqual(caught.exception.code, 2, command)
            self.assertIn("--builtin", stderr.getvalue(), command)

    def test_list_blueprints_default_is_local(self):
        """Default list-blueprints shows the local blueprint and its path."""
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main([
                "--home-dir", self.home, "list-blueprints",
            ])
        self.assertEqual(result, 0)
        output = stdout.getvalue()
        self.assertIn("plain", output)
        self.assertIn(
            os.path.join(self.home, "blueprints", "plain.rlqb"), output)
        header = output.splitlines()[0]
        self.assertTrue(header.startswith("NAME"))
        self.assertTrue(header.endswith("PATH"))

    def test_list_blueprints_empty_has_no_column_headers(self):
        """An empty home reports absence, not a headerless table."""
        empty_home = tempfile.TemporaryDirectory()
        self.addCleanup(empty_home.cleanup)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main([
                "--home-dir", empty_home.name, "list-blueprints",
            ])
        self.assertEqual(result, 0)
        output = stdout.getvalue()
        self.assertNotIn("NAME", output)
        self.assertIn("no blueprints", output)

    def test_list_blueprints_scans_the_blueprints_folder_recursively(self):
        """A blueprint nested within blueprints/ is found (home mode)."""
        nested = os.path.join(self.home, "blueprints", "vendor")
        os.makedirs(nested)
        nested_path = os.path.join(nested, "nested.rlqb")
        with open(nested_path, "w", encoding="utf-8") as handle:
            json.dump({
                "platform": "dos",
                "drives": {"hdd": {"size": "20M"}},
            }, handle)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main([
                "--home-dir", self.home, "list-blueprints",
            ])
        self.assertEqual(result, 0)
        self.assertIn(nested_path, stdout.getvalue())

    def test_list_blueprints_ignores_cache_dir(self):
        """A JSON file under cache/ is never reported as a blueprint."""
        cache_machine_dir = os.path.join(
            self.home, "cache", "machines", "plain-0")
        os.makedirs(cache_machine_dir)
        with open(os.path.join(cache_machine_dir, "state.json"),
                  "w", encoding="utf-8") as handle:
            json.dump({"platform": "dos"}, handle)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main([
                "--home-dir", self.home, "list-blueprints",
            ])
        self.assertEqual(result, 0)
        self.assertNotIn("cache", stdout.getvalue())

    def test_list_blueprints_scans_only_the_blueprints_folder(self):
        """Home mode lists blueprints/ only — files elsewhere are ignored."""
        # A .rlqb outside the canonical folder (here under home root and
        # under a decoy cache/) is never listed: home mode resolves from
        # blueprints/, not by walking the whole home.
        with open(os.path.join(self.home, "loose.rlqb"),
                  "w", encoding="utf-8") as handle:
            json.dump({"platform": "dos"}, handle)
        decoy_cache = os.path.join(self.home, "cache")
        os.makedirs(decoy_cache)
        with open(os.path.join(decoy_cache, "cached.rlqb"),
                  "w", encoding="utf-8") as handle:
            json.dump({"platform": "dos"}, handle)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main([
                "--home-dir", self.home, "list-blueprints",
            ])
        self.assertEqual(result, 0)
        output = stdout.getvalue()
        self.assertIn("plain", output)
        self.assertNotIn("loose", output)
        self.assertNotIn("cached", output)

    def test_list_blueprints_ignores_unrelated_json(self):
        """A same-extension file without a platform field is skipped."""
        with open(os.path.join(self.home, "blueprints", "notes.json"),
                  "w", encoding="utf-8") as handle:
            json.dump({"items": {}}, handle)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main([
                "--home-dir", self.home, "list-blueprints",
            ])
        self.assertEqual(result, 0)
        self.assertNotIn("notes", stdout.getvalue())

    def test_delete_blueprint(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main([
                "--home-dir", self.home,
                "delete-blueprint", "plain",
            ])
        self.assertEqual(result, 0)
        self.assertIn("plain.rlqb", stdout.getvalue())
        self.assertFalse(os.path.exists(
            os.path.join(self.home, "blueprints", "plain.rlqb")))

    def test_delete_blueprint_refuses_while_machines_exist(self):
        with contextlib.redirect_stdout(io.StringIO()):
            cli.main([
                "--home-dir", self.home,
                "create-machine",
                "--blueprint", "plain",
            ])
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            result = cli.main([
                "--home-dir", self.home,
                "delete-blueprint", "plain",
            ])
        self.assertEqual(result, 3)
        self.assertIn("still has 1 machine(s)", stderr.getvalue())
        self.assertIn("plain-0", stderr.getvalue())

    def test_list_media(self):
        blueprints = os.path.join(self.home, "blueprints")
        with open(os.path.join(blueprints, "media-lib.rlqb"), "w",
                  encoding="utf-8") as handle:
            json.dump([
                {"type": "media", "name": "livecd",
                 "location": {"local": "/x.iso"}}], handle)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main(["--home-dir", self.home, "list-media"])
        self.assertEqual(result, 0)
        # The namespace lists every media component in the source —
        # yours, and only yours. The codex's media are components of
        # blueprints you have not seeded, and there is no `seed-media`,
        # so nothing lists parts that cannot be ordered (D88).
        self.assertIn("livecd", stdout.getvalue())
        self.assertNotIn("freedos-livecd", stdout.getvalue())

    def test_start_and_stop_via_blueprint_selector(self):
        """--blueprint start/stop resolve the sole machine.

        The process-global home is pointed elsewhere before each call:
        a global --home-dir must overwrite it via set_home_dir()
        before dispatch, not leave a stale global in place — a
        dropped --home-dir must never let stop target a machine in
        another home (the identity name alone cannot tell
        same-numbered machines of two homes apart). The CLI drives
        the process-global assignments only (never a per-call
        context= override), so the guarantee now rests on
        set_home_dir() actually having run.
        """
        with contextlib.redirect_stdout(io.StringIO()):
            cli.main([
                "--home-dir", self.home,
                "create-machine",
                "--blueprint", "plain",
            ])
        decoy = os.path.join(self.home, "elsewhere")
        home.set_home_dir(decoy)
        with mock.patch("reliquary.cli.start_machine") as start, \
                contextlib.redirect_stdout(io.StringIO()):
            result = cli.main([
                "--home-dir", self.home,
                "start-machine",
                "--blueprint", "plain",
            ])
        self.assertEqual(result, 0)
        start.assert_called_once()
        self.assertNotIn("home", start.call_args.kwargs)
        self.assertNotIn("context", start.call_args.kwargs)
        self.assertEqual(home.home_dir(), self.home)

        home.set_home_dir(decoy)
        with mock.patch("reliquary.cli.stop_machine") as stop, \
                contextlib.redirect_stdout(io.StringIO()):
            result = cli.main([
                "--home-dir", self.home,
                "stop-machine",
                "--blueprint", "plain",
            ])
        self.assertEqual(result, 0)
        stop.assert_called_once()
        self.assertNotIn("home", stop.call_args.kwargs)
        self.assertNotIn("context", stop.call_args.kwargs)
        self.assertEqual(home.home_dir(), self.home)

    def test_destroy_via_machine_id(self):
        """--machine <blueprint>-<n> destroy deletes the machine."""
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            cli.main([
                "--home-dir", self.home,
                "create-machine",
                "--blueprint", "plain",
            ])
        machine_id = stdout.getvalue().split()[-1].strip()
        with mock.patch("reliquary.cli.destroy_machine") as destroy, \
                contextlib.redirect_stdout(io.StringIO()):
            result = cli.main([
                "--home-dir", self.home,
                "destroy-machine",
                "--machine", machine_id,
            ])
        self.assertEqual(result, 0)
        destroy.assert_called_once_with(machine_id)

    def test_destroy_rejects_blueprint_and_machine_together(self):
        """--blueprint and --machine are mutually exclusive."""
        with contextlib.redirect_stdout(io.StringIO()):
            cli.main([
                "--home-dir", self.home,
                "create-machine",
                "--blueprint", "plain",
            ])
            cli.main([
                "--home-dir", self.home,
                "create-machine",
                "--blueprint", "plain",
            ])
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), \
                contextlib.redirect_stdout(io.StringIO()):
            result = cli.main([
                "--home-dir", self.home,
                "destroy-machine",
                "--blueprint", "plain",
                "--machine", "plain-1",
            ])
        self.assertEqual(result, 2)
        self.assertIn("mutually exclusive", stderr.getvalue())

    def test_list_scripts_default_lists_shared_dir(self):
        """list-scripts without --blueprint lists scripts/ directory."""
        scripts = os.path.join(self.home, "scripts")
        os.makedirs(scripts)
        with open(os.path.join(scripts, "alpha.rlqs"), "w",
                  encoding="utf-8") as handle:
            handle.write(
                'description "Alpha script"\n'
                'platform dos\n'
                'type "hello"\n'
            )
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main([
                "--home-dir", self.home, "list-scripts",
            ])
        self.assertEqual(result, 0)
        output = stdout.getvalue()
        self.assertIn("NAME", output)
        self.assertIn("PATH", output)
        self.assertIn("alpha", output)
        # No description column on any noun; the field rides --json
        # until T8 settles how a person should see one (D88).
        self.assertNotIn("DESCRIPTION", output)
        self.assertNotIn("Alpha script", output)
        result, out = self._json_out(["list-scripts"])
        self.assertEqual(result, 0)
        self.assertEqual("Alpha script",
                         json.loads(out)[0]["description"])

    def test_list_scripts_with_blueprint_uses_scripts_map(self):
        """list-scripts --blueprint reads the blueprint's scripts map."""
        blueprints = os.path.join(self.home, "blueprints")
        scripts = os.path.join(self.home, "scripts")
        os.makedirs(scripts)
        with open(os.path.join(blueprints, "cust.rlqb"), "w",
                  encoding="utf-8") as handle:
            json.dump([
                {"type": "machine", "name": "cust", "platform": "dos",
                 "drives": {"hdd0": "blank"},
                 "scripts": {"setup": "cust-setup",
                             "teardown": "cust-teardown"}},
                {"type": "media", "name": "blank", "materialize": "new",
                 "size": "20M"},
            ], handle)
        with open(os.path.join(scripts, "cust-setup.rlqs"), "w",
                  encoding="utf-8") as handle:
            handle.write(
                'description "Custom setup"\n'
                'platform dos\n'
                'type "hello"\n'
            )
        with open(os.path.join(scripts, "cust-teardown.rlqs"), "w",
                  encoding="utf-8") as handle:
            handle.write(
                'platform dos\n'
                'type "bye"\n'
            )
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main([
                "--home-dir", self.home,
                "list-scripts",
                "--blueprint", "cust",
            ])
        self.assertEqual(result, 0)
        output = stdout.getvalue()
        self.assertIn("LABEL", output)
        self.assertIn("STEM", output)
        self.assertIn("setup", output)
        self.assertIn("cust-setup", output)
        self.assertIn("teardown", output)
        # The label's own map is what this command answers; the
        # description rides --json, on this noun as on every other.
        self.assertNotIn("DESCRIPTION", output)
        self.assertNotIn("Custom setup", output)

    def test_start_without_selector_errors(self):
        """The legacy root-home start path is gone: a selector is required."""
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            result = cli.main(["--home-dir", self.home, "start-machine"])
        self.assertEqual(result, 2)
        self.assertIn("--blueprint", stderr.getvalue())

    def test_type_sends_without_enter(self):
        machine_home = self._running_machine()
        with mock.patch("reliquary.cli.send_text") as send:
            result = cli.main(["--home-dir", self.home, "type", "A:",
                               "--machine", "plain-0"])
        self.assertEqual(result, 0)
        send.assert_called_once_with("A:", enter=False, home=machine_home)

    def test_enter_sends_with_enter(self):
        machine_home = self._running_machine()
        with mock.patch("reliquary.cli.send_text") as send:
            result = cli.main(["--home-dir", self.home, "enter", "dir",
                               "--machine", "plain-0"])
        self.assertEqual(result, 0)
        send.assert_called_once_with("dir", enter=True, home=machine_home)

    def test_press_translates_portable_keys(self):
        machine_home = self._running_machine()
        with mock.patch("reliquary.cli.send_keys") as send:
            result = cli.main(["--home-dir", self.home, "press", "enter",
                               "ctrl+c", "--machine", "plain-0"])
        self.assertEqual(result, 0)
        send.assert_called_once_with(
            [["ret"], ["ctrl", "c"]], home=machine_home)

    def test_a_selected_machine_carries_its_directory(self):
        """The machine's own directory is the whole address.

        It is where the recorded VM identity lives, so without it a
        guest-console command could not verify the machine it claims
        to be talking to — and there is no port to pass instead: that
        is the adapter's, on the far side of the seam.
        """
        machine_home = self._running_machine()
        with mock.patch("reliquary.cli.screen_text",
                        return_value=["ok"]) as screen, \
                contextlib.redirect_stdout(io.StringIO()):
            result = cli.main(["--home-dir", self.home, "screen",
                               "--machine", "plain-0"])
        self.assertEqual(result, 0)
        self.assertEqual(screen.call_args.kwargs, {"home": machine_home})
        self.assertTrue(machine_home.endswith("plain-0"))

    def test_clean_media_passes_an_optional_name(self):
        with mock.patch("reliquary.cli.clean_media",
                        return_value=[]) as clean, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(
                cli.main(["clean-media", "--home-dir", self.home]), 0)
            clean.assert_called_once_with(None)
            clean.reset_mock()
            self.assertEqual(
                cli.main(["clean-media", "livecd", "--home-dir", self.home]), 0)
            clean.assert_called_once_with("livecd")

    def test_prune_media_dry_run_reports_without_pruning(self):
        with mock.patch("reliquary.cli.prune_media",
                        return_value=["husk"]) as prune, \
                contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(
                cli.main(["prune-media", "--dry-run", "--home-dir", self.home]),
                0)
        prune.assert_called_once_with(dry_run=True)
        self.assertIn("husk", out.getvalue())

    def test_add_media_writes_a_declaration_for_a_local_file(self):
        payload = os.path.join(self.home, "supplied.iso")
        with open(payload, "wb") as handle:
            handle.write(b"ISO")
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(
                cli.main(["add-media", "win", payload,
                          "--home-dir", self.home]), 0)
        written = out.getvalue().strip()
        self.assertTrue(written.endswith("win.rlqb"))
        self.assertTrue(os.path.isfile(written))
        # The file it declares is left exactly where the user had it.
        self.assertTrue(os.path.isfile(payload))


class CliExecRunTests(unittest.TestCase):
    """The exec-run commands: machine variables and file exchange."""

    def setUp(self):
        saved = dict(home._globals)
        self.addCleanup(home._globals.update, saved)
        self.workdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.workdir.cleanup)
        self.home = self.workdir.name
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        self.backend = stack.enter_context(fake_backend.installed())
        self.exchange = os.path.join(self.home, "exchange")
        os.makedirs(self.exchange)
        os.makedirs(os.path.join(self.home, "blueprints"))
        with open(os.path.join(self.home, "blueprints", "rig.rlqb"),
                  "w", encoding="utf-8") as handle:
            json.dump([
                {"type": "machine", "name": "rig", "platform": "dos",
                 "drives": {"hdd0": "blank-20m",
                            "floppy0": "exchange-dir"}},
                {"type": "media", "name": "blank-20m",
                 "materialize": "new", "size": "20M"},
                {"type": "media", "name": "exchange-dir",
                 "materialize": "use",
                 "location": {"local": self.exchange}},
            ], handle)
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            cli.main(["--home-dir", self.home, "create-machine",
                      "--blueprint", "rig"])

    def _run(self, args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err):
            code = cli.main(["--home-dir", self.home] + args)
        return code, out.getvalue(), err.getvalue()

    def test_get_machine_var_reads_what_a_script_set(self):
        from reliquary.machines import set_machine_var
        set_machine_var("rig-0", "result", "PASS", context=self.home)
        code, out, _err = self._run(
            ["get-machine-var", "result", "--machine", "rig-0"])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "PASS")

    def test_an_unset_variable_prints_nothing_and_succeeds(self):
        code, out, _err = self._run(
            ["get-machine-var", "ready", "--machine", "rig-0"])
        self.assertEqual(code, 0)
        self.assertEqual(out, "")

    def test_an_unset_variable_is_null_under_json(self):
        code, out, _err = self._run(
            ["get-machine-var", "ready", "--machine", "rig-0", "--json"])
        self.assertEqual(code, 0)
        self.assertIsNone(json.loads(out))

    def test_put_and_get_round_trip_by_guest_address(self):
        source = os.path.join(self.home, "TEST.EXE")
        with open(source, "wb") as handle:
            handle.write(b"MZ")
        code, out, _err = self._run(
            ["put-file", source, r"A:\TEST.EXE", "--machine", "rig-0"])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), r"A:\TEST.EXE")
        back = os.path.join(self.home, "back.exe")
        code, out, _err = self._run(
            ["get-file", r"A:\TEST.EXE", back, "--machine", "rig-0"])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), os.path.abspath(back))
        with open(back, "rb") as handle:
            self.assertEqual(handle.read(), b"MZ")

    def test_an_unformatted_image_target_exits_three(self):
        # hdd0 in this rig is a blank the fake adapter never wrote, so
        # there is no filesystem to reach. PREFLIGHT ERROR: the gap
        # names itself rather than answering as though it were empty
        # (P11).
        source = os.path.join(self.home, "x.txt")
        with open(source, "w", encoding="ascii") as handle:
            handle.write("x")
        code, _out, err = self._run(
            ["put-file", source, r"C:\X.TXT", "--machine", "rig-0"])
        self.assertEqual(code, 3)
        self.assertIn("cannot be read at rest", err)

    def test_put_files_and_get_files_move_a_whole_tree(self):
        suite = os.path.join(self.home, "suite")
        os.makedirs(os.path.join(suite, "CASES"))
        for path, text in ((os.path.join(suite, "RUN.BAT"), "GO"),
                           (os.path.join(suite, "CASES", "ONE.DAT"), "1")):
            with open(path, "w", encoding="ascii") as handle:
                handle.write(text)
        code, out, _err = self._run(
            ["put-files", suite, "A:\\", "--machine", "rig-0"])
        self.assertEqual(code, 0)
        self.assertEqual(out.split(),
                         [r"A:\CASES\ONE.DAT", r"A:\RUN.BAT"])
        results = os.path.join(self.home, "back")
        code, out, _err = self._run(
            ["get-files", "A:\\", results, "--machine", "rig-0"])
        self.assertEqual(code, 0)
        self.assertIn(os.path.join(results, "CASES", "ONE.DAT"), out)
        with open(os.path.join(results, "RUN.BAT"),
                  encoding="ascii") as handle:
            self.assertEqual(handle.read(), "GO")

    def test_list_files_prints_addresses_and_serializes_entries(self):
        os.makedirs(os.path.join(self.exchange, "OUT"))
        with open(os.path.join(self.exchange, "OUT", "RESULT.TXT"), "w",
                  encoding="ascii") as handle:
            handle.write("PASS")
        code, out, _err = self._run(
            ["list-files", "A:\\", "--recursive", "--machine", "rig-0"])
        self.assertEqual(code, 0)
        self.assertIn(r"A:\OUT\RESULT.TXT", out)
        self.assertIn("<DIR>", out)
        code, out, _err = self._run(
            ["list-files", r"A:\OUT", "--machine", "rig-0", "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(
            json.loads(out),
            [{"address": r"A:\OUT\RESULT.TXT", "name": "RESULT.TXT",
              "kind": "file", "size": 4}])

    def test_an_empty_guest_directory_says_so(self):
        os.makedirs(os.path.join(self.exchange, "EMPTY"))
        code, out, _err = self._run(
            ["list-files", r"A:\EMPTY", "--machine", "rig-0"])
        self.assertEqual(code, 0)
        self.assertIn("no files", out)

    def test_insert_media_mounts_a_file_by_path(self):
        image = os.path.join(self.home, "round-1.img")
        with open(image, "wb") as handle:
            handle.write(b"BINARY")
        code, out, err = self._run(
            ["insert-media", "floppy0", "--file", image,
             "--machine", "rig-0"])
        self.assertEqual(code, 0)
        # A void twin: the narration is stderr, stdout stays empty.
        self.assertEqual(out, "")
        self.assertIn(image, err)
        from reliquary.machines import load_machine_state
        floppy = load_machine_state("rig-0", self.home)["drives"]["floppy0"]
        self.assertIsNone(floppy["media"])
        self.assertEqual(os.path.normpath(floppy["path"]),
                         os.path.normpath(image))


class CliProgressTests(unittest.TestCase):
    """--progress selects the rendering; jsonl owns stdout alone."""

    def setUp(self):
        saved = dict(home._globals)
        self.addCleanup(home._globals.update, saved)
        self.workdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.workdir.cleanup)
        self.home = self.workdir.name
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        self.backend = stack.enter_context(fake_backend.installed())

    def test_fetch_media_forwards_the_mode(self):
        with mock.patch("reliquary.cli.fetch_media") as fetch, \
                contextlib.redirect_stdout(io.StringIO()):
            code = cli.main(["--home-dir", self.home, "fetch-media", "livecd",
                             "--progress", "jsonl"])
        self.assertEqual(code, 0)
        fetch.assert_called_once_with("livecd", progress="jsonl")

    def test_fetch_media_rejects_json(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = cli.main(["--home-dir", self.home, "fetch-media", "livecd",
                             "--json"])
        self.assertEqual(code, 2)
        self.assertIn("--progress jsonl", err.getvalue())

    def test_an_unknown_mode_is_refused_by_the_parser(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                cli.main(["--home-dir", self.home, "fetch-media", "x",
                          "--progress", "fancy"])


if __name__ == "__main__":
    unittest.main()
