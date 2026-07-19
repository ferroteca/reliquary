# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Tests for the reliquary command-line interface."""

import contextlib
import io
import os
import unittest
from unittest import mock

import importlib

home = importlib.import_module("reliquary.home")
from reliquary import cli


class CliInstallTests(unittest.TestCase):
    """Behavior of the install subcommand."""

    def setUp(self):
        saved = home._home
        self.addCleanup(setattr, home, "_home", saved)

    def test_install_runs_named_recipe(self):
        """install <recipe> invokes the recipe module's install()."""
        artifacts = {"media": "m.zip", "hdd_image": "hdd.qcow2"}
        stdout = io.StringIO()
        with mock.patch(
                "reliquary.recipes.freedos_plain.install",
                return_value=artifacts) as install:
            with contextlib.redirect_stdout(stdout):
                result = cli.main(["install", "freedos-plain"])
        install.assert_called_once_with(display=False)
        self.assertEqual(result, 0)
        self.assertIn("hdd.qcow2", stdout.getvalue())

    def test_install_display_flag_is_forwarded(self):
        """--display asks the recipe for a visible QEMU window."""
        with mock.patch(
                "reliquary.recipes.freedos_plain.install",
                return_value={}) as install:
            with contextlib.redirect_stdout(io.StringIO()):
                result = cli.main(["install", "freedos-plain",
                                   "--display"])
        install.assert_called_once_with(display=True)
        self.assertEqual(result, 0)

    def test_install_unknown_recipe_fails_cleanly(self):
        """An unknown recipe name reports an error without a traceback."""
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            result = cli.main(["install", "no-such-os"])
        self.assertEqual(result, 2)
        self.assertIn("no-such-os", stderr.getvalue())

    def test_interrupt_exits_cleanly(self):
        """Ctrl-C reports interruption instead of a traceback."""
        stderr = io.StringIO()
        with mock.patch("reliquary.recipes.freedos_plain.install",
                        side_effect=KeyboardInterrupt):
            with contextlib.redirect_stderr(stderr):
                result = cli.main(["install", "freedos-plain"])
        self.assertEqual(result, 130)
        self.assertIn("interrupted", stderr.getvalue())

    def test_install_home_flag_overrides_home(self):
        """--home relocates the reliquary home for the run."""
        with mock.patch("reliquary.recipes.freedos_plain.install",
                        return_value={}):
            with contextlib.redirect_stdout(io.StringIO()):
                cli.main(["--home", "elsewhere",
                          "install", "freedos-plain"])
        self.assertEqual(home.home(), os.path.abspath("elsewhere"))


if __name__ == "__main__":
    unittest.main()
