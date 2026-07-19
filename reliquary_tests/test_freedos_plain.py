# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Tests for the FreeDOS recipe."""

import unittest


class FreeDOSRecipeTests(unittest.TestCase):
    """Smoke tests for the FreeDOS recipe module."""

    def test_module_imports(self):
        """The freedos recipe module exists and is importable."""
        from reliquary.recipes import freedos  # noqa: F401

    def test_install_raises_not_implemented(self):
        """install() raises NotImplementedError until implemented."""
        from reliquary.recipes.freedos import install
        with self.assertRaises(NotImplementedError):
            install(None, None, None)
