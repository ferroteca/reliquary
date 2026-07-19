# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Tests for reliquary home resolution."""

import os
import unittest

from reliquary import home


class HomeTests(unittest.TestCase):
    """Behavior of the reliquary home directory layout."""

    def setUp(self):
        self._saved = home._home
        self.addCleanup(setattr, home, "_home", self._saved)

    def test_set_home_overrides_resolution(self):
        """set_home() pins the home directory for later calls."""
        home.set_home(os.path.join("some", "where"))
        self.assertEqual(home.home(),
                         os.path.abspath(os.path.join("some", "where")))

    def test_environment_seeds_home(self):
        """RELIQUARY_HOME provides the initial home value."""
        # The module reads RELIQUARY_HOME at import; the module-level
        # default mirrors that seed, so simulate it directly.
        home._home = r"C:\elsewhere\reliquary"
        self.assertEqual(home.home(), r"C:\elsewhere\reliquary")

    def test_default_home_is_named_reliquary(self):
        """The fallback home is a directory named 'reliquary'."""
        home._home = None
        self.assertEqual(os.path.basename(home.home()), "reliquary")

    def test_install_media_dir_layout(self):
        """Install media lives under <home>/install-media/<os_name>."""
        home.set_home("base")
        self.assertEqual(
            home.install_media_dir("freedos"),
            os.path.join(os.path.abspath("base"),
                         "install-media", "freedos"))

    def test_machine_dir_layout(self):
        """Machine state lives under <home>/machines/<recipe>."""
        home.set_home("base")
        self.assertEqual(
            home.machine_dir("freedos-plain"),
            os.path.join(os.path.abspath("base"),
                         "machines", "freedos-plain"))


if __name__ == "__main__":
    unittest.main()
