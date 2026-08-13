# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Unit-test guards against live external effects.

**This module arms the guard as well as checking it.** The blocking
lives in ``tests/__init__.py``, and importing that package is what
installs it — but ``unittest discover -s tests`` treats this
directory as the top level and imports every module here under a
top-level name, so nothing imports the package on its own account.
Until the import below, the guard was armed only because an
integration module happened to say ``from tests import ...``, on a
line *after* its own ``from reliquary ...`` imports: anything that
broke the package left the whole suite unguarded (T26).

Discovery imports every module before it runs any test, so arming
here covers every test in the suite. What it does not cover is a
module that spawns a subprocess at *import* time, alphabetically
ahead of this one — nothing does, and one that did would be its own
defect. Running the suite as ``unittest tests`` arms it earlier
still, through the package's own ``load_tests``.
"""

import subprocess
import unittest
import urllib.request

import tests


class ExternalEffectGuardTests(unittest.TestCase):
    """The guard is checked, and checking it starts nothing.

    Both halves matter. A guard that can be silently absent is worse
    than none, because the suite still reports success — so its
    presence is asserted directly rather than inferred from a call
    that happens to be refused.
    """

    #: A name no host has. The guard refuses *any* subprocess, so
    #: what is named here is irrelevant to what is being tested — but
    #: it decides what happens when the guard is **absent**. Naming a
    #: real hypervisor meant the test written to prove that no unit
    #: test starts a VM was the one that started it: a live
    #: ``qemu-system-i386`` window, orphaned, holding the runner's
    #: stdout open so the run hung instead of failing (T26). An
    #: executable that cannot exist fails closed on every path.
    ABSENT = "reliquary-no-such-executable"

    def _unarmed(self):
        """Which blocks are missing, as a readable list."""
        missing = []
        if subprocess.Popen is not tests._BlockedPopen:
            missing.append("subprocess.Popen")
        if subprocess.run is not tests._blocked_backend_process:
            missing.append("subprocess.run")
        if urllib.request.urlopen is not tests._blocked_network_download:
            missing.append("urllib.request.urlopen")
        return missing

    def _require_armed(self):
        missing = self._unarmed()
        self.assertEqual(
            missing, [],
            "the external-effect guard is not installed, so these "
            "names would reach the host: " + ", ".join(missing))

    def test_the_guard_is_armed(self):
        """Asserted on its own, so disarming fails here and by name."""
        self._require_armed()

    def test_network_downloads_must_be_mocked(self):
        self._require_armed()
        with self.assertRaisesRegex(AssertionError, "network downloads"):
            urllib.request.urlopen("https://example.invalid")

    def test_backend_process_execution_must_be_mocked(self):
        self._require_armed()
        with self.assertRaisesRegex(AssertionError, "backend"):
            subprocess.Popen([self.ABSENT])

        with self.assertRaisesRegex(AssertionError, "backend"):
            subprocess.run([self.ABSENT, "info", "disk.img"])


if __name__ == "__main__":
    unittest.main()
