# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Opt-in FreeDOS install+verify against a live VirtualBox (F52).

Skipped unless ``RELIQUARY_INTEGRATION`` is set and ``VBoxManage`` is
available. Pins ``backend: virtualbox`` on the seeded freedos
blueprint so assignment does not prefer QEMU. The default unit suite
keeps backend process execution blocked; this module lifts those
guards only for the duration of the run.

Optional ``RELIQUARY_INTEGRATION_HOME`` reuses an absolute home so
the LiveCD media cache survives reruns; otherwise a temporary home
is created and removed. Use a *separate* home from the QEMU
integration run — the same machine id cannot span backends.
"""

import json
import os
import tempfile
import unittest

from reliquary.backend_virtualbox import find_vboxmanage
from reliquary.library import seed_blueprint
from reliquary.machines import (get_machine_var, load_machine_state,
                                stop_machine)
from reliquary.script_runner import run_script
from tests import live_external_effects


def _integration_enabled():
    value = os.environ.get("RELIQUARY_INTEGRATION", "").strip().lower()
    return value in ("1", "true", "yes")


def _vbox_available():
    try:
        find_vboxmanage()
    except Exception:
        return False
    return True


def _pin_virtualbox(home):
    """Rewrite the seeded freedos machine to declare VirtualBox."""
    path = os.path.join(home, "blueprints", "freedos.rlqb")
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    # Strip // comments the JSON parser will not accept after we
    # round-trip; the seeded file is JSON5. Parse via a light pass:
    # the document is a JSON array with // line comments.
    lines = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("//"):
            continue
        # Drop trailing // comments carefully (strings may contain //).
        if "//" in line:
            in_string = False
            out = []
            i = 0
            while i < len(line):
                ch = line[i]
                if ch == '"' and (i == 0 or line[i - 1] != "\\"):
                    in_string = not in_string
                if (not in_string and ch == "/" and i + 1 < len(line)
                        and line[i + 1] == "/"):
                    break
                out.append(ch)
                i += 1
            line = "".join(out).rstrip()
        lines.append(line)
    specs = json.loads("\n".join(lines))
    for spec in specs:
        if spec.get("type") == "machine" and spec.get("name") == "freedos":
            spec["backend"] = "virtualbox"
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(specs, handle, indent=2)
        handle.write("\n")


@unittest.skipUnless(
    _integration_enabled(),
    "set RELIQUARY_INTEGRATION=1 to run FreeDOS VirtualBox integration")
@unittest.skipUnless(
    _vbox_available(),
    "VBoxManage required for FreeDOS VirtualBox integration")
class FreeDOSVirtualBoxIntegrationTests(unittest.TestCase):
    """F52 Done-when: FreeDOS install+verify on VirtualBox, unmodified script."""

    def test_freedos_plain_install_and_verify_on_virtualbox(self):
        reuse = os.environ.get("RELIQUARY_INTEGRATION_HOME", "").strip()
        if reuse:
            home = os.path.abspath(reuse)
            os.makedirs(home, exist_ok=True)
            cleanup = None
        else:
            cleanup = tempfile.TemporaryDirectory(
                prefix="reliquary-vbox-integration-")
            home = cleanup.name

        try:
            with live_external_effects():
                seed_blueprint("freedos", context=home)
                _pin_virtualbox(home)
                installed = run_script(
                    "install",
                    blueprint="freedos",
                    context=home)
                self.assertEqual(installed.machine_phase, "ready")
                self.assertEqual(
                    load_machine_state(
                        installed.machine_id, home)["backend"],
                    "virtualbox")

                verified = run_script(
                    "verify",
                    blueprint="freedos",
                    context=home)
                self.assertEqual(verified.machine_phase, "ready")
                self.assertEqual(
                    verified.machine_id, installed.machine_id)

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
                    "running")
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
