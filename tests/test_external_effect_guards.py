# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Unit-test guards against live external effects.

This module installs the blocking from ``tests/__init__.py``, not
just checks it. Importing that package is what installs the
blocking — but ``unittest discover -s tests`` treats this directory
as the top level and imports every module here under a top-level
name, so nothing imports the package on its own. Before the import
below was added, the blocking was only in place because an
integration module happened to say ``from tests import ...``, on a
line *after* its own ``from reliquary ...`` imports: anything that
broke that import left the whole suite unblocked (T26).

pytest imports every module before it runs any test, so importing
`tests` here covers every test in the suite. What it does not cover
is a module that spawns a subprocess at *import* time, alphabetically
ahead of this one — no module does that, and one that did would be
its own bug.
"""

import subprocess
import urllib.request

import pytest

import tests

#: A name no real host has. The blocking rejects *any* subprocess
#: call, so which name is used here does not matter for what this
#: test checks — but it matters for what happens if the blocking is
#: **not** installed. This test used to name a real hypervisor
#: executable, and when the blocking was missing, the very test
#: meant to prove no unit test starts a VM was the one that started
#: one: a live ``qemu-system-i386`` window, left running, holding the
#: test runner's stdout open so the run hung instead of failing
#: (T26). A name that matches no real executable fails safely no
#: matter what.
ABSENT = "reliquary-no-such-executable"


def _unarmed():
    """Which blocks are missing, as a readable list."""
    missing = []
    if subprocess.Popen is not tests._BlockedPopen:
        missing.append("subprocess.Popen")
    if subprocess.run is not tests._blocked_backend_process:
        missing.append("subprocess.run")
    if urllib.request.urlopen is not tests._blocked_network_download:
        missing.append("urllib.request.urlopen")
    return missing


def _require_armed():
    missing = _unarmed()
    assert missing == [], (
        "the external-effect guard is not installed, so these "
        "names would reach the host: " + ", ".join(missing))


# This checks that the blocking is installed, without starting
# anything itself. Both a direct check and the tests below matter: a
# blocking that is silently missing is worse than no blocking at
# all, because the suite would still report success. So its presence
# is asserted directly here, instead of only being inferred from a
# call elsewhere that happens to be refused.

def test_the_guard_is_armed():
    """Checked on its own, so if the blocking is removed, this test
    is the one that fails, by name."""
    _require_armed()


def test_network_downloads_must_be_mocked():
    _require_armed()
    with pytest.raises(AssertionError, match="network downloads"):
        urllib.request.urlopen("https://example.invalid")


def test_backend_process_execution_must_be_mocked():
    _require_armed()
    with pytest.raises(AssertionError, match="backend"):
        subprocess.Popen([ABSENT])

    with pytest.raises(AssertionError, match="backend"):
        subprocess.run([ABSENT, "info", "disk.img"])
