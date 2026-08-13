# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for reliquary.

Importing this package **arms the guard** against live external
effects: no unit test reaches a hypervisor or the network, because
the names that would are replaced below at import time.

That makes the import itself load-bearing, and it is not guaranteed
by every way of running the suite. ``unittest tests`` imports the
package and then discovers through `load_tests`; ``unittest discover
-s tests`` treats this directory as the top level and imports the
modules under top-level names, reaching this file only if something
asks for it. `test_external_effect_guards` asks, deliberately and
with no dependency on `reliquary` importing, and then asserts that
the arming took (T26).
"""

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
    ``reliquary.acquire`` binds ``urlopen`` at import, so that name is
    restored alongside ``urllib.request.urlopen``.
    """
    import reliquary.acquire as acquire

    previous_urlopen = urllib.request.urlopen
    previous_acquire_urlopen = acquire.urlopen
    previous_popen = subprocess.Popen
    previous_run = subprocess.run
    urllib.request.urlopen = _ORIGINAL_URLOPEN
    acquire.urlopen = _ORIGINAL_URLOPEN
    subprocess.Popen = _ORIGINAL_POPEN
    subprocess.run = _ORIGINAL_RUN
    try:
        yield
    finally:
        urllib.request.urlopen = previous_urlopen
        acquire.urlopen = previous_acquire_urlopen
        subprocess.Popen = previous_popen
        subprocess.run = previous_run


def load_tests(loader, standard_tests, pattern):
    """Discover the package's test modules for `unittest tests`."""
    this_dir = os.path.dirname(__file__)
    standard_tests.addTests(loader.discover(
        start_dir=this_dir, pattern=pattern or "test_*.py",
        top_level_dir=os.path.dirname(this_dir)))
    return standard_tests
