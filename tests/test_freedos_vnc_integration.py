# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Opt-in FreeDOS install+verify over the VNC control plane (F63, F65).

The `integration` marker is what makes this opt-in: the tier is
deselected unless `pytest --integration` asks for it, and it is never
skipped (`tests/conftest.py`). Pins ``control-planes: ["vnc"]`` on
the seeded freedos blueprint, so the whole install is driven off the
RFB framebuffer through the shared recognizer instead of the VGA
text scrape — the F63 done-when: the codex scripts unmodified, and
the recognizer's reading matching the scrape on the same screens.

It carries F65's proof too, and for the same reason: the landmark
matcher reads *this* plane's framebuffer capture, so the only honest
place to prove it is against a real guest screen over a real plane.
The landmark is authored from the live screen the way a recorder
would author one, watched by name, and then deliberately missed so
the nearest-miss geography is read off a real failure rather than a
constructed one.

The home comes from the `integration_home` fixture, so
`RELIQUARY_INTEGRATION_HOME` reuses an absolute home and keeps the
LiveCD media cache across reruns. Use a *separate* home from the
plain QEMU integration run if both leave machines behind — the two
runs materialize the same blueprint name.
"""

import json
import os

import pytest
from PIL import Image

from reliquary import events as _events
from reliquary.backend_qemu import find_qemu, find_qemu_img, vga_screen
from reliquary.errors import RunFailure
from reliquary.home import cache_dir
from reliquary.library import seed_blueprint
from reliquary.machine_handle import Machine
from reliquary.machines import (get_machine_var, load_machine_state,
                                machine_dir_path, stop_machine)
from reliquary.script_parser import load_script
from reliquary.script_runner import execute_script, run_script
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


def _write_landmark(home, name, capture, rendering, similarity="99%"):
    """Author one landmark from a live screen, as a recorder would.

    The declaration covers the whole screen with a single fuzzy
    region rather than leaving a bare exact match: an idle DOS prompt
    blinks its cursor, which is one 8x16 cell of a 640x480 screen and
    would fail a residual that demands every pixel. That is the
    authored answer to a screen with furniture on it, and it is the
    one this proof needs.
    """
    root = os.path.join(home, "landmarks")
    os.makedirs(root, exist_ok=True)
    width, height = capture.size
    document = {
        "screen": {"width": width, "height": height},
        "regions": [{"kind": "fuzzy", "x": 0, "y": 0, "width": width,
                     "height": height, "similarity": similarity}],
    }
    with open(os.path.join(root, f"{name}.rlql"), "w",
              encoding="utf-8") as handle:
        json.dump(document, handle)
    rendering.save(os.path.join(root, f"{name}.1.png"))


def _write_script(home, name, source):
    path = os.path.join(home, "scripts", f"{name}.rlqs")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(source)
    return path


def test_freedos_plain_install_and_verify_over_vnc(integration_home):
    """F63 done-when: FreeDOS install+verify over VNC, scripts
    unmodified, and the recognizer agreeing with the VGA scrape.

    F65's, on the same guest and in the same run: a real `.rlql`
    landmark of a FreeDOS screen matched over this plane, and a
    variant miss reported with its nearest-miss geography. One test
    rather than two because the install is what costs, and both
    done-whens want the same running guest."""
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

        # F65's done-when, on the same live guest. The landmark is
        # authored from the screen this plane is actually showing, so
        # what is proved is the whole path: capture, the .rlql read
        # off the landmarks directory, the matcher over the plane's
        # own pixels.
        with machine.session() as session:
            capture = session.framebuffer()
        assert capture.size[0] > 0 and capture.size[1] > 0
        _write_landmark(home, "dos-prompt", capture, capture)
        _write_script(home, "watch-landmark",
                      "platform dos\nwait @dos-prompt timeout=30s\n")
        watched = run_script("watch-landmark",
                             machine=handed_off.machine_id, context=home)
        assert watched.machine_id == handed_off.machine_id
        matched = [event for event in watched.events
                   if event["kind"] == _events.OBSERVATION_MATCH]
        assert matched[-1]["description"] == "@dos-prompt"
        assert matched[-1]["variant"] == "dos-prompt.1.png"

        # And a variant that is not this screen: the wait expires and
        # the report names the closest rendering, the region it failed
        # on, and the percentage that region achieved.
        wrong = Image.new("RGB", capture.size, (255, 0, 255))
        _write_landmark(home, "not-this-screen", capture, wrong)
        missed = _write_script(
            home, "miss-landmark",
            "platform dos\nwait @not-this-screen timeout=5s\n")
        stream = _events.EventStream()
        with pytest.raises(RunFailure):
            execute_script(load_script(missed),
                           machine_id=handed_off.machine_id,
                           context=home, script_path=missed,
                           events=stream)
        report = [event for event in stream.events
                  if event["kind"] == _events.FAILURE][-1]
        misses = report["landmark-miss"]
        assert misses, "the expiry named no nearest miss"
        assert "not-this-screen.1.png" in misses[0]
        assert "% of 99% required" in misses[0]

        stop_machine(handed_off.machine_id, context=home)
