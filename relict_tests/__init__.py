# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Installed unit tests for relict."""

import os


def load_tests(loader, tests, pattern):
    """Let ``python -m unittest relict_tests`` discover this suite."""
    return loader.discover(os.path.dirname(__file__), pattern="test_*.py")
