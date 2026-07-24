# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Opt-in FreeDOS install+verify against a live QEMU.

Skipped unless ``RELIQUARY_INTEGRATION`` is set and QEMU tools are
on ``PATH``. The default unit suite keeps network and backend
process execution blocked; this module lifts those guards only for
the duration of the run.

Optional ``RELIQUARY_INTEGRATION_HOME`` reuses an absolute home so
the LiveCD media cache survives reruns; otherwise a temporary home
is created and removed.
"""

import os
import tempfile
import unittest

from reliquary.lifecycle import find_qemu, find_qemu_img
from reliquary.script_runner import run_script
from reliquary_tests import live_external_effects


def _integration_enabled():
    value = os.environ.get("RELIQUARY_INTEGRATION", "").strip().lower()
    return value in ("1", "true", "yes")


def _qemu_tools_available():
    try:
        find_qemu()
        find_qemu_img()
    except Exception:
        return False
    return True


@unittest.skipUnless(
    _integration_enabled(),
    "set RELIQUARY_INTEGRATION=1 to run FreeDOS QEMU integration")
@unittest.skipUnless(
    _qemu_tools_available(),
    "qemu-system-i386 and qemu-img required for FreeDOS integration")
class FreeDOSInstallIntegrationTests(unittest.TestCase):
    """Milestone-gate path: install then verify on freedos."""

    def test_freedos_plain_install_and_verify(self):
        reuse = os.environ.get("RELIQUARY_INTEGRATION_HOME", "").strip()
        if reuse:
            home = os.path.abspath(reuse)
            os.makedirs(home, exist_ok=True)
            cleanup = None
        else:
            cleanup = tempfile.TemporaryDirectory(
                prefix="reliquary-integration-")
            home = cleanup.name

        try:
            with live_external_effects():
                installed = run_script(
                    "install",
                    blueprint="freedos",
                    context=home)
                self.assertEqual(installed.machine_phase, "ready")

                verified = run_script(
                    "verify",
                    blueprint="freedos",
                    context=home)
                self.assertEqual(verified.machine_phase, "ready")
                self.assertEqual(
                    verified.machine_id, installed.machine_id)
        finally:
            if cleanup is not None:
                cleanup.cleanup()


if __name__ == "__main__":
    unittest.main()
