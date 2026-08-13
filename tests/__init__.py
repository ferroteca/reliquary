# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for reliquary.

Importing this package **arms the guard** against live external
effects: no unit test reaches a hypervisor or the network, because
the names that would are replaced below at import time.

That makes the import itself load-bearing. pytest, the runner
(D106), imports each module as ``tests.test_*`` because this file
makes the directory a package, so the arming runs before any test
does. `test_external_effect_guards` asks for the package by name
anyway — deliberately, and with no dependency on `reliquary`
importing — and then asserts that the arming took (T26).
"""

import contextlib
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


# `load_tests` lived here for `python -m unittest tests`, and went
# with the last `TestCase` (F60): with every module pytest-native
# that entry point collects nothing at all and reports success —
# the green-run-over-nothing failure this whole conversion was for.
