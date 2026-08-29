# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Opt-in FreeDOS install+verify against a live VirtualBox (F52).

The `integration` marker is what makes this opt-in: the tier is
deselected unless `pytest --integration` asks for it, and it is never
skipped (`tests/conftest.py`). Pins ``backend: virtualbox`` on the
seeded freedos blueprint so assignment does not prefer QEMU. The
default unit suite keeps backend process execution blocked; this
module lifts those guards only for the duration of the run.

The home comes from the `integration_home` fixture, so
`RELIQUARY_INTEGRATION_HOME` reuses an absolute home and keeps the
LiveCD media cache across reruns. Use a *separate* home from the QEMU
integration run — the same machine id cannot span backends.
"""

import json
import os

import pytest

from reliquary.backend_virtualbox import find_vboxmanage
from reliquary.library import seed_blueprint
from reliquary.machines import (get_machine_var, load_machine_state,
                                stop_machine)
from reliquary.script_runner import run_script
from tests import live_external_effects


pytestmark = pytest.mark.integration


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


def test_freedos_plain_install_and_verify_on_virtualbox(integration_home):
    """F52 Done-when: FreeDOS install+verify on VirtualBox, unmodified
    script."""
    # VirtualBox is what this integration tier tests, so a host
    # without it should fail with a clear message naming the gap
    # (P11), rather than skip: running this tier was explicitly asked
    # for.
    find_vboxmanage()
    home = integration_home

    with live_external_effects():
        seed_blueprint("freedos", context=home)
        _pin_virtualbox(home)
        installed = run_script("install", blueprint="freedos",
                               context=home)
        assert installed.machine_phase == "ready"
        assert load_machine_state(
            installed.machine_id, home)["backend"] == "virtualbox"

        verified = run_script("verify", blueprint="freedos",
                              context=home)
        assert verified.machine_phase == "ready"
        assert verified.machine_id == installed.machine_id

        handed_off = run_script("ready", blueprint="freedos",
                                context=home,
                                expect={"ready": "yes"})
        assert handed_off.machine_id == installed.machine_id
        assert load_machine_state(
            handed_off.machine_id, home)["phase"] == "running"
        assert get_machine_var("ready", machine=handed_off.machine_id,
                               context=home) == "yes"
        stop_machine(handed_off.machine_id, context=home)
