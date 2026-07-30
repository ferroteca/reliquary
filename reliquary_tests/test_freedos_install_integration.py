# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
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

from reliquary.backend_qemu import find_qemu, find_qemu_img
from reliquary.library import seed_blueprint
from reliquary.machines import (get_machine_var, load_machine_state,
                                stop_machine)
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
    """Milestone-gate path: install, verify, then hand off on freedos.

    The third step is what makes the codex's readiness example a
    claim rather than a file (P18, T9): an example that does not work
    is a defect, and nothing but a real guest can say whether this one
    does. It exercises `--expect` against that guest at the same time,
    which is exactly how a harness would use it.
    """

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
                # The user's own first step, and now a required one:
                # nothing resolves out of the codex, so the blueprint
                # and the scripts it names are copied out by name
                # before anything references them (U1, D88).
                seed_blueprint("freedos", context=home)
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

                # The handoff: the codex's readiness example leaves the
                # machine running with `ready` set, and `--expect`
                # contracts the run on it in one call rather than
                # reading the variable back in a second.
                handed_off = run_script(
                    "ready",
                    blueprint="freedos",
                    context=home,
                    expect={"ready": "yes"})
                self.assertEqual(
                    handed_off.machine_id, installed.machine_id)
                self.assertEqual(
                    load_machine_state(
                        handed_off.machine_id, home)["phase"],
                    "running",
                    "the readiness example must hand over a live "
                    "machine; every other codex script ends with the "
                    "guest powered off")
                self.assertEqual(
                    get_machine_var(
                        "ready", machine=handed_off.machine_id,
                        context=home),
                    "yes")
                stop_machine(handed_off.machine_id, context=home)
        finally:
            if cleanup is not None:
                cleanup.cleanup()


if __name__ == "__main__":
    unittest.main()
