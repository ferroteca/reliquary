# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Opt-in FreeDOS install+verify against a live QEMU.

The `integration` marker is what makes this opt-in: the tier is
deselected unless `pytest --integration` asks for it, and it is never
skipped (`tests/conftest.py`). The default unit suite keeps network
and backend process execution blocked; this module lifts those guards
only for the duration of the run.

The home comes from the `integration_home` fixture, so
`RELIQUARY_INTEGRATION_HOME` reuses an absolute home and keeps the
LiveCD media cache across reruns.
"""

import pytest

from reliquary.backend_qemu import find_qemu, find_qemu_img
from reliquary.library import seed_blueprint
from reliquary.machines import (get_machine_var, load_machine_state,
                                stop_machine)
from reliquary.script_runner import run_script
from tests import live_external_effects


pytestmark = pytest.mark.integration


def test_freedos_plain_install_and_verify(integration_home):
    """Milestone-gate path: install, verify, then hand off on freedos.

    The third step is what makes the codex's readiness example a
    claim rather than a file (P18, T9): an example that does not work
    is a defect, and nothing but a real guest can say whether this one
    does. It exercises `--expect` against that guest at the same time,
    which is exactly how a harness would use it.
    """
    # QEMU is what this tier *is*, so a host without it fails naming
    # the gap (P11) rather than skipping: the tier was asked for.
    find_qemu()
    find_qemu_img()
    home = integration_home

    with live_external_effects():
        # The user's own first step, and now a required one: nothing
        # resolves out of the codex, so the blueprint and the scripts
        # it names are copied out by name before anything references
        # them (U1, D88).
        seed_blueprint("freedos", context=home)
        installed = run_script("install", blueprint="freedos",
                               context=home)
        assert installed.machine_phase == "ready"

        verified = run_script("verify", blueprint="freedos",
                              context=home)
        assert verified.machine_phase == "ready"
        assert verified.machine_id == installed.machine_id

        # The handoff: the codex's readiness example leaves the
        # machine running with `ready` set, and `--expect` contracts
        # the run on it in one call rather than reading the variable
        # back in a second.
        handed_off = run_script("ready", blueprint="freedos",
                                context=home,
                                expect={"ready": "yes"})
        assert handed_off.machine_id == installed.machine_id
        assert load_machine_state(
            handed_off.machine_id, home)["phase"] == "running", (
            "the readiness example must hand over a live machine; "
            "every other codex script ends with the guest powered off")
        assert get_machine_var("ready", machine=handed_off.machine_id,
                               context=home) == "yes"
        stop_machine(handed_off.machine_id, context=home)
