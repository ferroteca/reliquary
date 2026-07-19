# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Tests for reliquary."""

import os


def load_tests(loader, standard_tests, pattern):
    """Discover the package's test modules for `unittest reliquary_tests`."""
    this_dir = os.path.dirname(__file__)
    standard_tests.addTests(loader.discover(
        start_dir=this_dir, pattern=pattern or "test_*.py",
        top_level_dir=os.path.dirname(this_dir)))
    return standard_tests
