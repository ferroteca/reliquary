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

from reliquary import cli
from reliquary import backends
from tests import fake_backend

class CliEmptyListingTests(unittest.TestCase):
    """list-* report absence, not a bare header."""

    def setUp(self):
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

    def test_backend_overrides_the_blueprint_field(self):
        # --backend without --dry-run pins assignment, exactly as a
        # declared backend does: it must be available and capable.
        # The stub vmware claims no capability, so it fails
        # preflight (exit 3) rather than at the static gate (exit 2).
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            result = cli.main([
                "--home-dir", self.home,
                "create-machine", "--blueprint", "plain",
                "--backend", "vmware",
            ])
        self.assertEqual(result, 3)
        self.assertIn("vmware", stderr.getvalue())

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
        """The record carries the field the human listing wraps (D97):
        the two presentations show one surface."""
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

    def test_list_blueprints_shows_a_description_beneath_its_row(self):
        """The display D97 settled: never a column — an indented,
        wrapped line beneath the entry, and a row without one
        contributes no line."""
        with open(os.path.join(self.home, "blueprints", "told.rlqb"),
                  "w", encoding="utf-8") as handle:
            json.dump([
                {"type": "machine", "name": "told", "platform": "dos",
                 "description": (
                     "A described machine whose text is long enough "
                     "that the listing has to wrap it across more "
                     "than one indented line beneath the row"),
                 "drives": {"hdd0": "blank-20m"}},
                {"type": "media", "name": "blank-20m",
                 "materialize": "new", "size": "20M"},
            ], handle)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main(["--home-dir", self.home,
                               "list-blueprints"])
        self.assertEqual(result, 0)
        lines = stdout.getvalue().splitlines()
        wrapped = [line for line in lines if line.startswith("  ")]
        self.assertGreater(len(wrapped), 1)     # it wrapped
        self.assertIn("A described machine", wrapped[0])
        self.assertTrue(all(len(line) <= 72 for line in wrapped))
        # The undescribed row contributes no line: `plain` sorts
        # first, and the line after its row is `told`'s row.
        plain_at = next(index for index, line in enumerate(lines)
                        if line.startswith("plain"))
        self.assertFalse(lines[plain_at + 1].startswith("  "))

    def test_json_list_blueprints_carries_description_and_platform(self):
        """The record holds what the human view shows (D97; P6)."""
        result, out = self._json_out(["list-blueprints"])
        self.assertEqual(result, 0)
        row = next(r for r in json.loads(out) if r["name"] == "plain")
        self.assertIn("description", row)
        self.assertIsNone(row["description"])
        self.assertEqual(row["platform"], "dos")

    def test_list_codex_prints_the_description_beneath_the_name(self):
        """U11's "read a description", at the keyboard (D97)."""
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main(["--home-dir", self.home, "list-codex"])
        self.assertEqual(result, 0)
        lines = stdout.getvalue().splitlines()
        at = lines.index("freedos")
        self.assertTrue(lines[at + 1].startswith("  "))
        self.assertIn("FreeDOS", lines[at + 1])

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

        The CLI resolves against the record built from its own flags
        — one session per invocation (P26), no process globals left
        to consult — so a dropped --home-dir can never let stop
        target a machine in another home (the identity name alone
        cannot tell same-numbered machines of two homes apart): the
        guarantee rests on the session's record alone.
        """
        with contextlib.redirect_stdout(io.StringIO()):
            cli.main([
                "--home-dir", self.home,
                "create-machine",
                "--blueprint", "plain",
            ])
        with mock.patch(
                "reliquary.session.Session.start_machine") as start, \
                contextlib.redirect_stdout(io.StringIO()):
            result = cli.main([
                "--home-dir", self.home,
                "start-machine",
                "--blueprint", "plain",
            ])
        self.assertEqual(result, 0)
        # The selector resolved live, under --home-dir: the record
        # is the carrier.
        start.assert_called_once()
        self.assertEqual(start.call_args.args, ("plain-0",))

        with mock.patch(
                "reliquary.session.Session.stop_machine") as stop, \
                contextlib.redirect_stdout(io.StringIO()):
            result = cli.main([
                "--home-dir", self.home,
                "stop-machine",
                "--blueprint", "plain",
            ])
        self.assertEqual(result, 0)
        stop.assert_called_once_with("plain-0")

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
        with mock.patch(
                "reliquary.session.Session.destroy_machine") as destroy, \
                contextlib.redirect_stdout(io.StringIO()):
            result = cli.main([
                "--home-dir", self.home,
                "destroy-machine",
                "--machine", machine_id,
            ])
        self.assertEqual(result, 0)
        destroy.assert_called_once_with(machine_id)

    def test_destroy_via_positional_machine_id(self):
        """destroy-machine <id> is a short alias for --machine <id>."""
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            cli.main([
                "--home-dir", self.home,
                "create-machine",
                "--blueprint", "plain",
            ])
        machine_id = stdout.getvalue().split()[-1].strip()
        with mock.patch(
                "reliquary.session.Session.destroy_machine") as destroy, \
                contextlib.redirect_stdout(io.StringIO()):
            result = cli.main([
                "--home-dir", self.home,
                "destroy-machine", machine_id,
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
        # Never a column (D97): the description prints beneath its
        # row, indented and wrapped.
        self.assertNotIn("DESCRIPTION", output)
        self.assertIn("\n  Alpha script", output)
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
        # Never a column (D97): the described label carries its
        # indented line, and the undescribed one contributes none.
        self.assertNotIn("DESCRIPTION", output)
        self.assertIn("\n  Custom setup", output)
        lines = output.splitlines()
        teardown_at = next(index for index, line in enumerate(lines)
                           if line.startswith("teardown"))
        self.assertTrue(teardown_at == len(lines) - 1
                        or not lines[teardown_at + 1].startswith("  "))

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
        with mock.patch("reliquary.session.Session.clean_media",
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
        with mock.patch("reliquary.session.Session.prune_media",
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


class CliContextConstructionTests(unittest.TestCase):
    """The invocation's record: flags, then environment, then default.

    ``adopt_environment()`` no longer runs on the CLI path — the CLI
    builds one ``Context`` per invocation and opens a session on it
    (P26) — so the environment honoring the suite used to certify
    through home.py is stated here, against ``main()`` itself.
    """

    def setUp(self):
        self.workdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.workdir.cleanup)
        self.home = self.workdir.name

    def _pin_env(self, variable, value):
        saved = os.environ.get(variable)

        def restore():
            if saved is None:
                os.environ.pop(variable, None)
            else:
                os.environ[variable] = saved

        self.addCleanup(restore)
        os.environ[variable] = value

    def test_the_environment_names_the_home(self):
        self._pin_env("RELIQUARY_HOME", self.home)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main(["list-blueprints"])
        self.assertEqual(result, 0)
        self.assertIn("(no blueprints)", stdout.getvalue())

    def test_the_former_home_variable_is_accepted_as_a_fallback(self):
        self._pin_env("RELIQUARY_HOME_DIR", self.home)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main(["list-blueprints"])
        self.assertEqual(result, 0)
        self.assertIn("(no blueprints)", stdout.getvalue())

    def test_the_documented_home_variable_beats_the_former_spelling(self):
        former = os.path.join(self.home, "former-home")
        self._pin_env("RELIQUARY_HOME", self.home)
        self._pin_env("RELIQUARY_HOME_DIR", former)
        with contextlib.redirect_stdout(io.StringIO()):
            result = cli.main(["new-blueprint", "documented"])
        self.assertEqual(result, 0)
        self.assertTrue(os.path.isfile(os.path.join(
            self.home, "blueprints", "documented.rlqb")))
        self.assertFalse(os.path.exists(former))

    def test_a_flag_beats_the_environment(self):
        decoy = os.path.join(self.home, "env-home")
        self._pin_env("RELIQUARY_HOME", decoy)
        with contextlib.redirect_stdout(io.StringIO()):
            result = cli.main(["--home-dir", self.home,
                               "new-blueprint", "flagged"])
        self.assertEqual(result, 0)
        self.assertTrue(os.path.isfile(os.path.join(
            self.home, "blueprints", "flagged.rlqb")))
        self.assertFalse(os.path.exists(decoy))

    def test_the_environment_selects_the_properties_file(self):
        selected = os.path.join(self.home, "proj.properties")
        self._pin_env("RELIQUARY_PROPERTIES", selected)
        with contextlib.redirect_stdout(io.StringIO()):
            result = cli.main(["--home-dir", self.home, "set-property",
                               "env.selected", "yes"])
        self.assertEqual(result, 0)
        self.assertTrue(os.path.isfile(selected))
        self.assertFalse(os.path.isfile(
            os.path.join(self.home, "user.properties")))


class CliProgressTests(unittest.TestCase):
    """--progress selects the rendering; jsonl owns stdout alone."""

    def setUp(self):
        self.workdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.workdir.cleanup)
        self.home = self.workdir.name
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        self.backend = stack.enter_context(fake_backend.installed())

    def test_fetch_media_forwards_the_mode(self):
        with mock.patch("reliquary.session.Session.fetch_media") as fetch, \
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
