# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Tests for reliquary."""

import contextlib
import os
import subprocess
import urllib.request


_ORIGINAL_URLOPEN = urllib.request.urlopen
_ORIGINAL_POPEN = subprocess.Popen
_ORIGINAL_RUN = subprocess.run


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


@contextlib.contextmanager
def live_external_effects():
    """Temporarily allow network downloads and QEMU subprocesses.

    Unit tests keep the blocked bindings. Opt-in integration tests
    enter this context so media fetch and QEMU launch can run.
    ``reliquary.media`` binds ``urlopen`` at import, so that name is
    restored alongside ``urllib.request.urlopen``.
    """
    import reliquary.media as media

    previous_urlopen = urllib.request.urlopen
    previous_media_urlopen = media.urlopen
    previous_popen = subprocess.Popen
    previous_run = subprocess.run
    urllib.request.urlopen = _ORIGINAL_URLOPEN
    media.urlopen = _ORIGINAL_URLOPEN
    subprocess.Popen = _ORIGINAL_POPEN
    subprocess.run = _ORIGINAL_RUN
    try:
        yield
    finally:
        urllib.request.urlopen = previous_urlopen
        media.urlopen = previous_media_urlopen
        subprocess.Popen = previous_popen
        subprocess.run = previous_run


def load_tests(loader, standard_tests, pattern):
    """Discover the package's test modules for `unittest reliquary_tests`."""
    this_dir = os.path.dirname(__file__)
    standard_tests.addTests(loader.discover(
        start_dir=this_dir, pattern=pattern or "test_*.py",
        top_level_dir=os.path.dirname(this_dir)))
    return standard_tests
