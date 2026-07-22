# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Tests for reliquary."""

import os
import subprocess
import urllib.request


_ORIGINAL_POPEN = subprocess.Popen


def _blocked_network_download(*args, **kwargs):
    raise AssertionError(
        "unit tests must mock network downloads explicitly")


class _BlockedPopen(_ORIGINAL_POPEN):
    def __init__(self, *args, **kwargs):
        _blocked_backend_process(*args, **kwargs)


def _blocked_backend_process(*args, **kwargs):
    raise AssertionError(
        "unit tests must mock backend virtualization/process execution")


urllib.request.urlopen = _blocked_network_download
subprocess.Popen = _BlockedPopen
subprocess.run = _blocked_backend_process


def load_tests(loader, standard_tests, pattern):
    """Discover the package's test modules for `unittest reliquary_tests`."""
    this_dir = os.path.dirname(__file__)
    standard_tests.addTests(loader.discover(
        start_dir=this_dir, pattern=pattern or "test_*.py",
        top_level_dir=os.path.dirname(this_dir)))
    return standard_tests
