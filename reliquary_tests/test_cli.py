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
                "create",
            ])
        self.assertEqual(result, 0)
        self.assertRegex(stdout.getvalue(),
                         r"created machine [0-9a-f]{32}")

    def test_create_requires_blueprint(self):
        """create without --blueprint fails cleanly."""
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            result = cli.main(["--home", self.home, "create"])
        self.assertEqual(result, 1)
        self.assertIn("create requires --blueprint", stderr.getvalue())

    def test_list_machines_shows_created_machine(self):
        """list machines prints id, blueprint, phase, and backend."""
        with mock.patch("reliquary.machines.create_hdd_image"), \
                contextlib.redirect_stdout(io.StringIO()):
            cli.main([
                "--home", self.home,
                "--blueprint", "plain",
                "create",
            ])
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main([
                "--home", self.home, "list", "machines",
            ])
        self.assertEqual(result, 0)
        output = stdout.getvalue()
        self.assertIn("BLUEPRINT", output)
        self.assertIn("plain", output)
        self.assertIn("ready", output)
        self.assertIn("qemu", output)

    def test_start_and_stop_via_blueprint_selector(self):
        """--blueprint start/stop resolve the sole machine."""
        with mock.patch("reliquary.machines.create_hdd_image"), \
                contextlib.redirect_stdout(io.StringIO()):
            cli.main([
                "--home", self.home,
                "--blueprint", "plain",
                "create",
            ])
        with mock.patch("reliquary.cli.start_machine") as start, \
                contextlib.redirect_stdout(io.StringIO()):
            result = cli.main([
                "--home", self.home,
                "--blueprint", "plain",
                "start",
            ])
        self.assertEqual(result, 0)
        start.assert_called_once()
        self.assertEqual(start.call_args.kwargs["home"], self.home)

        with mock.patch("reliquary.cli.stop_machine") as stop, \
                contextlib.redirect_stdout(io.StringIO()):
            result = cli.main([
                "--home", self.home,
                "--blueprint", "plain",
                "stop",
            ])
        self.assertEqual(result, 0)
        stop.assert_called_once()

    def test_destroy_via_machine_prefix(self):
        """--machine PREFIX destroy deletes the resolved machine."""
        stdout = io.StringIO()
        with mock.patch("reliquary.machines.create_hdd_image"), \
                contextlib.redirect_stdout(stdout):
            cli.main([
                "--home", self.home,
                "--blueprint", "plain",
                "create",
            ])
        machine_id = stdout.getvalue().split()[-1].strip()
        with mock.patch("reliquary.cli.destroy") as destroy, \
                contextlib.redirect_stdout(io.StringIO()):
            result = cli.main([
                "--home", self.home,
                "--machine", machine_id[:4],
                "destroy",
            ])
        self.assertEqual(result, 0)
        destroy.assert_called_once_with(machine_id, home=self.home)

    def test_start_without_selector_uses_legacy_path(self):
        """Bare start still loads the root-home MachineConfig path."""
        with mock.patch("reliquary.cli.start_legacy") as start, \
                contextlib.redirect_stdout(io.StringIO()):
            result = cli.main(["--home", self.home, "start"])
        self.assertEqual(result, 0)
        start.assert_called_once()


if __name__ == "__main__":
    unittest.main()
