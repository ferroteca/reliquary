# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Tests for the reliquary command-line interface."""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

import importlib

home = importlib.import_module("reliquary.home")
from reliquary import cli


class CliEmptyListingTests(unittest.TestCase):
    """list-* report absence, not a bare header."""

    def setUp(self):
        saved = home._home
        self.addCleanup(setattr, home, "_home", saved)
        saved_cache = home._cache
        self.addCleanup(setattr, home, "_cache", saved_cache)
        self.workdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.workdir.cleanup)
        self.home = self.workdir.name

    def test_list_machines_reports_no_machines(self):
        """An empty machine list says so instead of a headerless table."""
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main(["--home", self.home, "list-machines"])
        self.assertEqual(result, 0)
        output = stdout.getvalue()
        self.assertNotIn("BLUEPRINT", output)
        self.assertIn("no machines", output)

    def test_flag_position_independence(self):
        """Flags like --home work before or after the command."""
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main(["list-machines", "--home", self.home])
        self.assertEqual(result, 0)
        self.assertIn("no machines", stdout.getvalue())

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main(["--home", self.home, "list-machines"])
        self.assertEqual(result, 0)
        self.assertIn("no machines", stdout.getvalue())

    def test_list_machines_reports_no_machines_for_blueprint(self):
        """Filtering by a blueprint with no machines names the blueprint."""
        os.makedirs(os.path.join(self.home, "blueprints"))
        with open(os.path.join(self.home, "blueprints", "plain.json"),
                  "w", encoding="utf-8") as handle:
            json.dump({
                "platform": "dos",
                "drives": {"hdd": {"size": "20M"}},
            }, handle)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main([
                "--home", self.home, "list-machines",
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
            result = cli.main(["--home", self.home, "list-blueprints"])
        self.assertEqual(result, 0)
        self.assertIn("no blueprints", stdout.getvalue())

    def test_list_scripts_reports_none_found(self):
        """An empty scripts directory says so, not a bare header."""
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main(["--home", self.home, "list-scripts"])
        self.assertEqual(result, 0)
        output = stdout.getvalue()
        self.assertNotIn("NAME", output)
        self.assertIn("no scripts", output)

    def test_screen_accepts_home_after_command(self):
        with mock.patch("reliquary.cli.screen_text",
                        return_value=["hello"]) as screen, \
                contextlib.redirect_stdout(io.StringIO()) as stdout:
            result = cli.main(["screen", "--home", self.home])
        self.assertEqual(result, 0)
        screen.assert_called_once_with(None)
        self.assertEqual(stdout.getvalue(), "hello\n")


class CliReorderArgvTests(unittest.TestCase):
    """Leading flags are moved after the command word."""

    def test_moves_leading_home(self):
        self.assertEqual(
            cli._reorder_argv(["--home", "/tmp", "list-machines"]),
            ["list-machines", "--home", "/tmp"])

    def test_preserves_command_first(self):
        self.assertEqual(
            cli._reorder_argv(["list-machines", "--home", "/tmp"]),
            ["list-machines", "--home", "/tmp"])

    def test_equals_form(self):
        self.assertEqual(
            cli._reorder_argv(["--home=/tmp", "list-machines"]),
            ["list-machines", "--home=/tmp"])


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
        saved = home._home
        self.addCleanup(setattr, home, "_home", saved)
        saved_cache = home._cache
        self.addCleanup(setattr, home, "_cache", saved_cache)
        self.workdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.workdir.cleanup)
        self.home = self.workdir.name
        os.makedirs(os.path.join(self.home, "blueprints"))
        with open(os.path.join(self.home, "blueprints", "plain.json"),
                  "w", encoding="utf-8") as handle:
            json.dump({
                "platform": "dos",
                "drives": {"hdd": {"size": "20M"}},
            }, handle)

    def test_create_machine(self):
        stdout = io.StringIO()
        with mock.patch("reliquary.machines.create_hdd_image"), \
                contextlib.redirect_stdout(stdout):
            result = cli.main([
                "--home", self.home,
                "create-machine",
                "--blueprint", "plain",
            ])
        self.assertEqual(result, 0)
        self.assertIn("created machine plain-0", stdout.getvalue())

    def test_create_machine_flags_before_command(self):
        stdout = io.StringIO()
        with mock.patch("reliquary.machines.create_hdd_image"), \
                contextlib.redirect_stdout(stdout):
            result = cli.main([
                "--home", self.home,
                "--blueprint", "plain",
                "create-machine",
            ])
        self.assertEqual(result, 0)
        self.assertIn("created machine plain-0", stdout.getvalue())

    def test_list_machines_table(self):
        """list-machines prints blueprint, number, phase, and backend."""
        with mock.patch("reliquary.machines.create_hdd_image"), \
                contextlib.redirect_stdout(io.StringIO()):
            cli.main([
                "--home", self.home,
                "create-machine",
                "--blueprint", "plain",
            ])
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main([
                "--home", self.home, "list-machines",
            ])
        self.assertEqual(result, 0)
        output = stdout.getvalue()
        self.assertIn("BLUEPRINT", output)
        self.assertIn("plain", output)
        self.assertIn("ready", output)

    def test_list_blueprints_builtin(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main([
                "--home", self.home, "list-blueprints",
                "--builtin",
            ])
        self.assertEqual(result, 0)
        output = stdout.getvalue().strip().splitlines()
        self.assertTrue(output)
        for name in output:
            self.assertNotIn(
                name, ["plain"],
                "--builtin must not include local blueprints")

    def test_list_blueprints_default_is_local(self):
        """Default list-blueprints shows the local blueprint and its path."""
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main([
                "--home", self.home, "list-blueprints",
            ])
        self.assertEqual(result, 0)
        output = stdout.getvalue()
        self.assertIn("plain", output)
        self.assertIn(
            os.path.join(self.home, "blueprints", "plain.json"), output)
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
                "--home", empty_home.name, "list-blueprints",
            ])
        self.assertEqual(result, 0)
        output = stdout.getvalue()
        self.assertNotIn("NAME", output)
        self.assertIn("no blueprints", output)

    def test_list_blueprints_scans_home_recursively(self):
        """A blueprint nested outside blueprints/ is still found."""
        nested = os.path.join(self.home, "archive", "nested")
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
                "--home", self.home, "list-blueprints",
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
                "--home", self.home, "list-blueprints",
            ])
        self.assertEqual(result, 0)
        self.assertNotIn("cache", stdout.getvalue())

    def test_list_blueprints_ignores_redirected_cache_dir(self):
        """--cache pointed outside home is still excluded from the scan."""
        redirected_cache = tempfile.TemporaryDirectory()
        self.addCleanup(redirected_cache.cleanup)
        cache_machine_dir = os.path.join(
            redirected_cache.name, "machines", "plain-0")
        os.makedirs(cache_machine_dir)
        with open(os.path.join(cache_machine_dir, "state.json"),
                  "w", encoding="utf-8") as handle:
            json.dump({"platform": "dos"}, handle)
        # A same-named "cache" directory under home that is NOT the
        # configured cache root must still be scanned normally.
        decoy_cache = os.path.join(self.home, "cache")
        os.makedirs(decoy_cache)
        with open(os.path.join(decoy_cache, "decoy.rlqb"),
                  "w", encoding="utf-8") as handle:
            json.dump({"platform": "dos"}, handle)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main([
                "--home", self.home, "--cache", redirected_cache.name,
                "list-blueprints",
            ])
        self.assertEqual(result, 0)
        output = stdout.getvalue()
        self.assertNotIn("state.json", output)
        self.assertNotIn("plain-0", output)
        self.assertIn("decoy", output)

    def test_list_blueprints_ignores_unrelated_json(self):
        """A same-extension file without a platform field is skipped."""
        with open(os.path.join(self.home, "blueprints", "notes.json"),
                  "w", encoding="utf-8") as handle:
            json.dump({"items": {}}, handle)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main([
                "--home", self.home, "list-blueprints",
            ])
        self.assertEqual(result, 0)
        self.assertNotIn("notes", stdout.getvalue())

    def test_delete_blueprint(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main([
                "--home", self.home,
                "delete-blueprint", "plain",
            ])
        self.assertEqual(result, 0)
        self.assertIn("deleted blueprint plain", stdout.getvalue())
        self.assertFalse(os.path.exists(
            os.path.join(self.home, "blueprints", "plain.json")))

    def test_delete_blueprint_refuses_while_machines_exist(self):
        with mock.patch("reliquary.machines.create_hdd_image"), \
                contextlib.redirect_stdout(io.StringIO()):
            cli.main([
                "--home", self.home,
                "create-machine",
                "--blueprint", "plain",
            ])
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            result = cli.main([
                "--home", self.home,
                "delete-blueprint", "plain",
            ])
        self.assertEqual(result, 1)
        self.assertIn("still has 1 machine(s)", stderr.getvalue())
        self.assertIn("plain-0", stderr.getvalue())

    def test_list_media_and_delete_media(self):
        media_path = os.path.join(self.home, "media")
        os.makedirs(media_path)
        definition = os.path.join(media_path, "livecd.rlqm")
        with open(definition, "w", encoding="utf-8") as handle:
            json.dump({
                "name": "livecd",
                "file": "live.iso",
                "sha256": "1" * 64,
            }, handle)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main([
                "--home", self.home, "list-media",
            ])
        self.assertEqual(result, 0)
        self.assertEqual(stdout.getvalue().strip(), "livecd")

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main([
                "--home", self.home, "list-media", "--builtin",
            ])
        self.assertEqual(result, 0)
        self.assertIn("freedos-1.4-livecd", stdout.getvalue())

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main([
                "--home", self.home, "delete-media", "livecd",
            ])
        self.assertEqual(result, 0)
        self.assertIn("deleted media livecd", stdout.getvalue())
        self.assertFalse(os.path.exists(definition))

    def test_start_and_stop_via_blueprint_selector(self):
        """--blueprint start/stop resolve the sole machine.

        The process-global home is pointed elsewhere before each call:
        a global --home must overwrite it via set_home() before
        dispatch, not leave a stale global in place — a dropped
        --home must never let stop target a machine in another home
        (the identity name alone cannot tell same-numbered machines
        of two homes apart). The CLI drives the process-global home
        only (never a per-call context= override), so the guarantee
        now rests on set_home() actually having run.
        """
        with mock.patch("reliquary.machines.create_hdd_image"), \
                contextlib.redirect_stdout(io.StringIO()):
            cli.main([
                "--home", self.home,
                "create-machine",
                "--blueprint", "plain",
            ])
        decoy = os.path.join(self.home, "elsewhere")
        home._home = decoy
        with mock.patch("reliquary.cli.start_machine") as start, \
                contextlib.redirect_stdout(io.StringIO()):
            result = cli.main([
                "--home", self.home,
                "start-machine",
                "--blueprint", "plain",
            ])
        self.assertEqual(result, 0)
        start.assert_called_once()
        self.assertNotIn("home", start.call_args.kwargs)
        self.assertNotIn("context", start.call_args.kwargs)
        self.assertEqual(home._home, self.home)

        home._home = decoy
        with mock.patch("reliquary.cli.stop_machine") as stop, \
                contextlib.redirect_stdout(io.StringIO()):
            result = cli.main([
                "--home", self.home,
                "stop-machine",
                "--blueprint", "plain",
            ])
        self.assertEqual(result, 0)
        stop.assert_called_once()
        self.assertNotIn("home", stop.call_args.kwargs)
        self.assertNotIn("context", stop.call_args.kwargs)
        self.assertEqual(home._home, self.home)

    def test_destroy_via_machine_id(self):
        """--machine <blueprint>-<n> destroy deletes the machine."""
        stdout = io.StringIO()
        with mock.patch("reliquary.machines.create_hdd_image"), \
                contextlib.redirect_stdout(stdout):
            cli.main([
                "--home", self.home,
                "create-machine",
                "--blueprint", "plain",
            ])
        machine_id = stdout.getvalue().split()[-1].strip()
        with mock.patch("reliquary.cli.destroy_machine") as destroy, \
                contextlib.redirect_stdout(io.StringIO()):
            result = cli.main([
                "--home", self.home,
                "destroy-machine",
                "--machine", machine_id,
            ])
        self.assertEqual(result, 0)
        destroy.assert_called_once_with(machine_id)

    def test_destroy_rejects_blueprint_and_machine_together(self):
        """--blueprint and --machine are mutually exclusive."""
        with mock.patch("reliquary.machines.create_hdd_image"), \
                contextlib.redirect_stdout(io.StringIO()):
            cli.main([
                "--home", self.home,
                "create-machine",
                "--blueprint", "plain",
            ])
            cli.main([
                "--home", self.home,
                "create-machine",
                "--blueprint", "plain",
            ])
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), \
                contextlib.redirect_stdout(io.StringIO()):
            result = cli.main([
                "--home", self.home,
                "destroy-machine",
                "--blueprint", "plain",
                "--machine", "plain-1",
            ])
        self.assertEqual(result, 1)
        self.assertIn("mutually exclusive", stderr.getvalue())

    def test_list_scripts_default_lists_shared_dir(self):
        """list-scripts without --blueprint lists scripts/ directory."""
        scripts = os.path.join(self.home, "scripts")
        os.makedirs(scripts)
        with open(os.path.join(scripts, "alpha.rlqs"), "w",
                  encoding="utf-8") as handle:
            handle.write(
                'description: "Alpha script"\n'
                'platform: dos\n'
                'type "hello"\n'
            )
        stdout = io.StringIO()
        with mock.patch("reliquary.machines.create_hdd_image"), \
                contextlib.redirect_stdout(stdout):
            result = cli.main([
                "--home", self.home, "list-scripts",
            ])
        self.assertEqual(result, 0)
        output = stdout.getvalue()
        self.assertIn("NAME", output)
        self.assertIn("DESCRIPTION", output)
        self.assertIn("alpha", output)
        self.assertIn("Alpha script", output)

    def test_list_scripts_with_blueprint_uses_scripts_map(self):
        """list-scripts --blueprint reads the blueprint's scripts map."""
        blueprints = os.path.join(self.home, "blueprints")
        scripts = os.path.join(self.home, "scripts")
        os.makedirs(scripts)
        with open(os.path.join(blueprints, "cust.json"), "w",
                  encoding="utf-8") as handle:
            json.dump({
                "platform": "dos",
                "drives": {"hdd": {"size": "20M"}},
                "scripts": {
                    "setup": "cust-setup",
                    "teardown": "cust-teardown",
                },
            }, handle)
        with open(os.path.join(scripts, "cust-setup.rlqs"), "w",
                  encoding="utf-8") as handle:
            handle.write(
                'description: "Custom setup"\n'
                'platform: dos\n'
                'type "hello"\n'
            )
        with open(os.path.join(scripts, "cust-teardown.rlqs"), "w",
                  encoding="utf-8") as handle:
            handle.write(
                'platform: dos\n'
                'type "bye"\n'
            )
        stdout = io.StringIO()
        with mock.patch("reliquary.machines.create_hdd_image"), \
                contextlib.redirect_stdout(stdout):
            result = cli.main([
                "--home", self.home,
                "list-scripts",
                "--blueprint", "cust",
            ])
        self.assertEqual(result, 0)
        output = stdout.getvalue()
        self.assertIn("LABEL", output)
        self.assertIn("DESCRIPTION", output)
        self.assertIn("setup", output)
        self.assertIn("Custom setup", output)
        self.assertIn("teardown", output)
        self.assertIn("-", output)

    def test_start_without_selector_uses_legacy_path(self):
        """Bare start-machine still loads the root-home MachineConfig path."""
        with mock.patch("reliquary.cli.start_legacy") as start, \
                contextlib.redirect_stdout(io.StringIO()):
            result = cli.main(["--home", self.home, "start-machine"])
        self.assertEqual(result, 0)
        start.assert_called_once()

    def test_type_sends_without_enter(self):
        with mock.patch("reliquary.cli.send_text") as send:
            result = cli.main(["type", "A:", "--port", "1234"])
        self.assertEqual(result, 0)
        send.assert_called_once_with("A:", enter=False, port=1234)

    def test_enter_sends_with_enter(self):
        with mock.patch("reliquary.cli.send_text") as send:
            result = cli.main(["enter", "dir", "--port", "1234"])
        self.assertEqual(result, 0)
        send.assert_called_once_with("dir", enter=True, port=1234)

    def test_press_translates_portable_keys(self):
        with mock.patch("reliquary.cli.send_keys") as send:
            result = cli.main(["press", "enter", "ctrl+c",
                               "--port", "1234"])
        self.assertEqual(result, 0)
        send.assert_called_once_with(
            [["ret"], ["ctrl", "c"]], 1234)

    def test_clean_downloads(self):
        with mock.patch("reliquary.cli.clean_downloads") as clean, \
                contextlib.redirect_stdout(io.StringIO()):
            result = cli.main(["clean-downloads", "--home", self.home])
        self.assertEqual(result, 0)
        clean.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
