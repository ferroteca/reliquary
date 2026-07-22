# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Tests for the reliquary command-line interface."""

import contextlib
import io
import json
import os
import tempfile
import unittest
from unittest import mock

import importlib

home = importlib.import_module("reliquary.home")
from reliquary import cli


class CliEmptyListingTests(unittest.TestCase):
    """list machines/blueprints/scripts report absence, not a bare header."""

    def setUp(self):
        saved = home._home
        self.addCleanup(setattr, home, "_home", saved)
        self.workdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.workdir.cleanup)
        self.home = self.workdir.name

    def test_list_machines_reports_no_machines(self):
        """An empty machine list says so instead of a headerless table."""
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main(["--home", self.home, "list", "machines"])
        self.assertEqual(result, 0)
        output = stdout.getvalue()
        self.assertNotIn("BLUEPRINT", output)
        self.assertIn("no machines", output)

    def test_list_machines_dashed_alias(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main(["--home", self.home, "list-machines"])
        self.assertEqual(result, 0)
        self.assertIn("no machines", stdout.getvalue())

    def test_flag_position_independence(self):
        """Global flags like --home work before or after the command."""
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            # After command
            result = cli.main(["list-machines", "--home", self.home])
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
                "--home", self.home, "list", "machines",
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
            result = cli.main(["--home", self.home, "list", "blueprints"])
        self.assertEqual(result, 0)
        self.assertIn("no blueprints", stdout.getvalue())

    def test_list_scripts_reports_none_found(self):
        """An empty scripts directory says so, not a bare header."""
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main(["--home", self.home, "list", "scripts"])
        self.assertEqual(result, 0)
        output = stdout.getvalue()
        self.assertNotIn("NAME", output)
        self.assertIn("no scripts", output)

    def test_text_accepts_home_after_command(self):
        with mock.patch("reliquary.cli.screen_text",
                        return_value=["hello"]) as screen, \
                contextlib.redirect_stdout(io.StringIO()) as stdout:
            result = cli.main(["text", "--home", self.home])
        self.assertEqual(result, 0)
        screen.assert_called_once_with(None)
        self.assertEqual(stdout.getvalue(), "hello\n")


class CliCodexAndPropertyTests(unittest.TestCase):
    """CLI coverage for the new codex and property command families."""

    def setUp(self):
        saved = home._home
        self.addCleanup(setattr, home, "_home", saved)
        self.workdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.workdir.cleanup)
        self.home = self.workdir.name

    def test_seed_blueprint_command_copies_codex_closure(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main([
                "--home", self.home,
                "seed-blueprint", "freedos-1.4-plain",
            ])
        self.assertEqual(result, 0)
        self.assertIn("seeded blueprint freedos-1.4-plain",
                      stdout.getvalue())
        self.assertTrue(os.path.isfile(os.path.join(
            self.home, "blueprints", "freedos-1.4-plain.rlqb")))
        self.assertTrue(os.path.isfile(os.path.join(
            self.home, "media", "freedos-1.4-livecd.rlqm")))
        self.assertTrue(os.path.isfile(os.path.join(
            self.home, "scripts", "freedos-1.4-plain-install.rlqs")))

    def test_seed_media_and_script_commands_report_no_match(self):
        for command, expected in [
                ("seed-media", "media no-such already exists or not found"),
                ("seed-script", "script no-such already exists or not found"),
        ]:
            with self.subTest(command=command):
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    result = cli.main([
                        "--home", self.home, command, "no-such",
                    ])
                self.assertEqual(result, 0)
                self.assertIn(expected, stdout.getvalue())

    def test_property_commands_round_trip_and_list_sorted(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main([
                "--home", self.home, "set-property", "zeta", "last",
            ]), 0)
            self.assertEqual(cli.main([
                "--home", self.home, "set-property", "alpha", "first",
                "--secret",
            ]), 0)

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main([
                "--home", self.home, "get-property", "alpha",
            ])
        self.assertEqual(result, 0)
        self.assertEqual(stdout.getvalue(), "first\n")

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main(["--home", self.home, "list-properties"])
        self.assertEqual(result, 0)
        self.assertLess(
            stdout.getvalue().index("alpha"),
            stdout.getvalue().index("zeta"))

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main([
                "--home", self.home, "unset-property", "alpha",
            ]), 0)
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main([
                "--home", self.home, "get-property", "alpha",
            ])
        self.assertEqual(result, 0)
        self.assertEqual(stdout.getvalue(), "")

    def test_new_blueprint_command_writes_jsonc_scaffold(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main([
                "--home", self.home, "new-blueprint", "scratch",
                "--platform", "win9x",
            ])
        self.assertEqual(result, 0)
        self.assertIn("created blueprint scratch", stdout.getvalue())
        with open(os.path.join(self.home, "blueprints", "scratch.rlqb"),
                  encoding="utf-8") as handle:
            content = handle.read()
        self.assertIn("// Machine blueprint for scratch", content)
        self.assertIn('"platform": "win9x"', content)

    def test_fetch_media_command_reports_requested_item(self):
        stdout = io.StringIO()
        with mock.patch("reliquary.cli.fetch_media",
                        return_value="payload.iso") as fetch, \
                contextlib.redirect_stdout(stdout):
            result = cli.main([
                "--home", self.home, "fetch-media",
                "freedos-1.4-livecd",
            ])
        self.assertEqual(result, 0)
        fetch.assert_called_once_with(
            "freedos-1.4-livecd", home=self.home)
        self.assertIn("fetched freedos-1.4-livecd", stdout.getvalue())


class CliMachineLifecycleTests(unittest.TestCase):
    """create / start / stop / destroy / list machines CLI."""

    def setUp(self):
        saved = home._home
        self.addCleanup(setattr, home, "_home", saved)
        self.workdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.workdir.cleanup)
        self.home = self.workdir.name
        blueprints = os.path.join(self.home, "blueprints")
        os.makedirs(blueprints)
        with open(os.path.join(blueprints, "plain.json"), "w",
                  encoding="utf-8") as handle:
            json.dump({
                "platform": "dos",
                "drives": {"hdd": {"size": "20M"}},
            }, handle)

    def test_create_prints_machine_id(self):
        """--blueprint NAME create materializes and prints the id."""
        stdout = io.StringIO()
        with mock.patch("reliquary.machines.create_hdd_image"), \
                contextlib.redirect_stdout(stdout):
            result = cli.main([
                "--home", self.home,
                "--blueprint", "plain",
                "create-machine",
            ])
        self.assertEqual(result, 0)
        self.assertRegex(stdout.getvalue(),
                         r"created machine plain-0")

    def test_create_requires_blueprint(self):
        """create-machine without --blueprint fails cleanly."""
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            result = cli.main(["--home", self.home, "create-machine"])
        self.assertEqual(result, 1)
        self.assertIn("create-machine requires --blueprint", stderr.getvalue())

    def test_list_machines_shows_created_machine(self):
        """list machines prints blueprint, number, phase, and backend."""
        with mock.patch("reliquary.machines.create_hdd_image"), \
                contextlib.redirect_stdout(io.StringIO()):
            cli.main([
                "--home", self.home,
                "--blueprint", "plain",
                "create-machine",
            ])
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main([
                "--home", self.home, "list", "machines",
            ])
        self.assertEqual(result, 0)
        output = stdout.getvalue()
        self.assertIn("BLUEPRINT", output)
        self.assertIn("NUMBER", output)
        self.assertIn("plain", output)
        self.assertIn("0", output)
        self.assertIn("ready", output)
        self.assertIn("qemu", output)

    def test_list_blueprints_builtin_lists_builtins(self):
        """--builtin lists only built-in blueprint names."""
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main([
                "--home", self.home, "list", "blueprints",
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
        """Default list blueprints shows only local blueprints."""
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main([
                "--home", self.home, "list", "blueprints",
            ])
        self.assertEqual(result, 0)
        output = stdout.getvalue().strip().splitlines()
        self.assertIn("plain", output,
                      "default must include local blueprint 'plain'")

    def test_list_blueprint_alias_produces_same_output(self):
        """'list blueprint' alias produces identical output to 'list blueprints'."""
        stdout_plural = io.StringIO()
        with contextlib.redirect_stdout(stdout_plural):
            cli.main(["--home", self.home, "list", "blueprints"])
        stdout_singular = io.StringIO()
        with contextlib.redirect_stdout(stdout_singular):
            cli.main(["--home", self.home, "list", "blueprint"])
        self.assertEqual(
            stdout_plural.getvalue(), stdout_singular.getvalue())

    def test_list_machine_alias_produces_same_output(self):
        """'list machine' alias produces identical output to 'list machines'."""
        with mock.patch("reliquary.machines.create_hdd_image"), \
                contextlib.redirect_stdout(io.StringIO()):
            cli.main([
                "--home", self.home,
                "--blueprint", "plain",
                "create-machine",
            ])
        stdout_plural = io.StringIO()
        with contextlib.redirect_stdout(stdout_plural):
            cli.main(["--home", self.home, "list", "machines"])
        stdout_singular = io.StringIO()
        with contextlib.redirect_stdout(stdout_singular):
            cli.main(["--home", self.home, "list", "machine"])
        self.assertEqual(
            stdout_plural.getvalue(), stdout_singular.getvalue())

    def test_list_machine_alias_filters_by_blueprint(self):
        """'list machine --blueprint NAME' filters machines."""
        with mock.patch("reliquary.machines.create_hdd_image"), \
                contextlib.redirect_stdout(io.StringIO()):
            cli.main([
                "--home", self.home,
                "--blueprint", "plain",
                "create-machine",
            ])
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main([
                "--home", self.home,
                "list", "machine",
                "--blueprint", "plain",
            ])
        self.assertEqual(result, 0)
        output = stdout.getvalue()
        self.assertIn("plain", output)
        self.assertIn("ready", output)

    def test_start_and_stop_via_blueprint_selector(self):
        """--blueprint start/stop resolve the sole machine.

        The process-global home is pointed elsewhere before each call:
        the global --home must reach the subcommand on its own, not by
        leaking through earlier set_home calls — a global --home that
        gets dropped must never let stop target a machine in another
        home (the identity name alone cannot tell same-numbered
        machines of two homes apart).
        """
        with mock.patch("reliquary.machines.create_hdd_image"), \
                contextlib.redirect_stdout(io.StringIO()):
            cli.main([
                "--home", self.home,
                "--blueprint", "plain",
                "create-machine",
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
        self.assertEqual(start.call_args.kwargs["home"], self.home)

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
        self.assertEqual(stop.call_args.kwargs["home"], self.home)

    def test_destroy_via_machine_id(self):
        """--machine <blueprint>-<n> destroy deletes the machine."""
        stdout = io.StringIO()
        with mock.patch("reliquary.machines.create_hdd_image"), \
                contextlib.redirect_stdout(stdout):
            cli.main([
                "--home", self.home,
                "--blueprint", "plain",
                "create-machine",
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
        destroy.assert_called_once_with(machine_id, home=self.home)

    def test_destroy_via_blueprint_and_number(self):
        """--blueprint with --machine <n> selects that machine."""
        with mock.patch("reliquary.machines.create_hdd_image"), \
                contextlib.redirect_stdout(io.StringIO()):
            cli.main([
                "--home", self.home,
                "--blueprint", "plain",
                "create-machine",
            ])
            cli.main([
                "--home", self.home,
                "--blueprint", "plain",
                "create-machine",
            ])
        with mock.patch("reliquary.cli.destroy_machine") as destroy, \
                contextlib.redirect_stdout(io.StringIO()):
            result = cli.main([
                "--home", self.home,
                "--blueprint", "plain",
                "--machine", "1",
                "destroy-machine",
            ])
        self.assertEqual(result, 0)
        destroy.assert_called_once_with("plain-1", home=self.home)

    def test_list_scripts_default_lists_shared_dir(self):
        """list scripts without --blueprint lists scripts/ directory."""
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
                "--home", self.home, "list", "scripts",
            ])
        self.assertEqual(result, 0)
        output = stdout.getvalue()
        self.assertIn("NAME", output)
        self.assertIn("DESCRIPTION", output)
        self.assertIn("alpha", output)
        self.assertIn("Alpha script", output)

    def test_list_scripts_with_blueprint_uses_scripts_map(self):
        """list scripts --blueprint reads the blueprint's scripts map."""
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
                "list", "scripts",
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

    def test_list_script_alias_produces_same_output(self):
        """'list script' alias produces identical output to 'list scripts'."""
        scripts = os.path.join(self.home, "scripts")
        os.makedirs(scripts)
        with open(os.path.join(scripts, "task.rlqs"), "w",
                  encoding="utf-8") as handle:
            handle.write(
                'description: "A task"\n'
                'platform: dos\n'
                'type "hello"\n'
            )
        stdout_plural = io.StringIO()
        with mock.patch("reliquary.machines.create_hdd_image"), \
                contextlib.redirect_stdout(stdout_plural):
            cli.main([
                "--home", self.home, "list", "scripts",
            ])
        stdout_singular = io.StringIO()
        with mock.patch("reliquary.machines.create_hdd_image"), \
                contextlib.redirect_stdout(stdout_singular):
            cli.main([
                "--home", self.home, "list", "scripts",
            ])
        self.assertEqual(
            stdout_plural.getvalue(), stdout_singular.getvalue())

    def test_start_without_selector_uses_legacy_path(self):
        """Bare start still loads the root-home MachineConfig path."""
        with mock.patch("reliquary.cli.start_legacy") as start, \
                contextlib.redirect_stdout(io.StringIO()):
            result = cli.main(["--home", self.home, "start-machine"])
        self.assertEqual(result, 0)
        start.assert_called_once()


if __name__ == "__main__":
    unittest.main()
