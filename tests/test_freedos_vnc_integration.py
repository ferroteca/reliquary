# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Opt-in FreeDOS install+verify over the VNC control plane (F63).

The `integration` marker is what makes this opt-in: the tier is
deselected unless `pytest --integration` asks for it, and it is never
skipped (`tests/conftest.py`). Pins ``control-planes: ["vnc"]`` on
the seeded freedos blueprint, so the whole install is driven off the
RFB framebuffer through the shared recognizer instead of the VGA
text scrape — the F63 done-when: the codex scripts unmodified, and
the recognizer's reading matching the scrape on the same screens.

The home comes from the `integration_home` fixture, so
`RELIQUARY_INTEGRATION_HOME` reuses an absolute home and keeps the
LiveCD media cache across reruns. Use a *separate* home from the
plain QEMU integration run if both leave machines behind — the two
runs materialize the same blueprint name.
"""

import os

import pytest

from reliquary.backend_qemu import find_qemu, find_qemu_img, vga_screen
from reliquary.home import cache_dir
from reliquary.library import seed_blueprint
from reliquary.machine_handle import Machine
from reliquary.machines import (get_machine_var, load_machine_state,
                                machine_dir_path, stop_machine)
from reliquary.script_runner import run_script
from tests import live_external_effects


pytestmark = pytest.mark.integration


def _pin_vnc(home):
    """Declare the VNC plane on the seeded freedos machine.

    A text edit of the seeded copy, the way an author would make it
    theirs; the codex source stays untouched.
    """
    path = os.path.join(home, "blueprints", "freedos.rlqb")
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    edited = text.replace(
        '"platform": "dos",',
        '"platform": "dos",\n    "control-planes": ["vnc"],', 1)
    assert edited != text, "the seeded blueprint lost its anchor line"
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(edited)


def _differing_cells(rows_a, rows_b):
    """The (row, col) cells where two text screens disagree."""
    cells = []
    for index in range(max(len(rows_a), len(rows_b))):
        line_a = rows_a[index] if index < len(rows_a) else ""
        line_b = rows_b[index] if index < len(rows_b) else ""
        width = max(len(line_a), len(line_b))
        for col in range(width):
            char_a = line_a[col] if col < len(line_a) else " "
            char_b = line_b[col] if col < len(line_b) else " "
            if char_a != char_b:
                cells.append((index, col))
    return cells


def test_freedos_plain_install_and_verify_over_vnc(integration_home):
    """F63 done-when: FreeDOS install+verify over VNC, scripts
    unmodified, and the recognizer agreeing with the VGA scrape."""
    # QEMU is what this tier *is*, so a host without it fails naming
    # the gap (P11) rather than skipping: the tier was asked for.
    find_qemu()
    find_qemu_img()
    home = integration_home

    with live_external_effects():
        seed_blueprint("freedos", context=home)
        _pin_vnc(home)
        installed = run_script("install", blueprint="freedos",
                               context=home)
        assert installed.machine_phase == "ready"
        state = load_machine_state(installed.machine_id, home)
        assert state["control-planes"] == ["vnc"]

        verified = run_script("verify", blueprint="freedos",
                              context=home)
        assert verified.machine_phase == "ready"
        assert verified.machine_id == installed.machine_id

        handed_off = run_script("ready", blueprint="freedos",
                                context=home,
                                expect={"ready": "yes"})
        assert handed_off.machine_id == installed.machine_id
        state = load_machine_state(handed_off.machine_id, home)
        assert state["phase"] == "running"
        assert get_machine_var("ready", machine=handed_off.machine_id,
                               context=home) == "yes"

        # The recorded endpoint carries the plane beside its ports.
        endpoint = state["vm"]["endpoint"]
        assert endpoint["plane"] == "vnc"
        assert isinstance(endpoint["vnc-port"], int)

        # The done-when's second clause, on the live guest the
        # readiness script just handed over: the recognizer's reading
        # of the framebuffer matches the VGA text scrape of the same
        # screen. An idle DOS prompt only blinks its cursor, which
        # the scrape cannot see and the framebuffer can, so exactly
        # that one cell is allowed to disagree.
        machine = Machine(machine_dir_path(handed_off.machine_id, home),
                          cache=cache_dir(home))
        with machine.session() as session:
            assert session.recognizes_text is True
            recognized = session.text_screen()
        with machine.qmp() as qmp:
            scraped = vga_screen(qmp)
        differing = _differing_cells(recognized[0], scraped[0])
        assert len(differing) <= 1, (
            "the recognizer and the VGA scrape disagree beyond the "
            f"cursor cell: {differing}")

        stop_machine(handed_off.machine_id, context=home)
