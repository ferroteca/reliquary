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

**Every run here records a screen transcript**, into `captures/` under
that home. It is where F43's corpus fixtures come from — this tier is
the only place a real guest draws a real screen — and it is evidence
on the runs that fail, which are the ones worth a frame-by-frame read.
Promotion to a fixture stays a deliberate copy: no test writes into
the source tree, and a capture is looked at before it becomes an
assertion (`tests/fixtures/conformance/transcript/README.md`).
"""

import os

import pytest

from reliquary.backend_qemu import find_qemu, find_qemu_img
from reliquary.errors import RunFailure
from reliquary.home import blueprints_dir
from reliquary.interaction_agentless import AgentlessGuestExec
from reliquary.library import seed_blueprint, seed_script
from reliquary.machine_handle import Machine
from reliquary.machines import (apply_blueprint, get_machine_var,
                                load_machine_state, machine_dir_path,
                                stop_machine)
from reliquary.script_runner import resolve_key, run_script
from reliquary.transcript import RecordingSession, _TranscriptWriter
from tests import live_external_effects


pytestmark = pytest.mark.integration


def _capture(home, label):
    """Where this run's transcript is written — the home, never the tree."""
    captures = os.path.join(home, "captures")
    os.makedirs(captures, exist_ok=True)
    return os.path.join(captures, f"freedos-{label}.rlqt")


#: A file planted in the guest whose **last line is the echo of the
#: command that reads it**. Nothing about it is malformed: it is a
#: text file a user could write, and it is what a heuristic that
#: scans backwards for "a row ending with the command, with a prompt
#: before it" cannot tell from the real thing.
_ECHO_LOOKALIKE = (
    "THE FIRST LINE OF THE FILE",
    "THE SECOND LINE OF THE FILE",
    r"C:\>TYPE C:\ECHOLIKE.TXT",
)

#: The screens worth capturing here are all screens a real guest
#: actually draws, not a staged defect. What the layer *does* with
#: each one is what the fixture pins down — the right answer where
#: the layer handles it correctly, and the wrong answer where it
#: doesn't — so that once the gap is closed, the fixture starts
#: failing loudly instead of staying silently out of date.
_HAZARDS = (
    # An 85-column command wraps its echo across two rows, so no row
    # *ends* with it.
    ("wrapped-echo", "ECHO " + "X" * 80, 30),
    # Output whose own last line is indistinguishable from the echo.
    ("echo-lookalike", r"TYPE C:\ECHOLIKE.TXT", 30),
    # More output than a screen holds: agentless capture's documented
    # limit, and the prompt arriving after a long scroll.
    ("scrolling-output", r"DIR /S C:\FREEDOS", 90),
    # A command that changes the prompt to a shape exec has no
    # evidence for: the stated limit (D112), pinned. It leaves the
    # guest at `[C:\]>` for the session, which is what the last
    # capture needs.
    ("custom-prompt", "PROMPT [$P]$G", 20),
    # An ordinary command at that customized prompt: the prompt the
    # guest was at is completion evidence in its own right.
    ("at-custom-prompt", "VER", 30),
)


def _plant_echo_lookalike(home, machine_id):
    """Have the running guest write the lookalike file itself.

    `COPY CON` and nothing else, because the guest has to be the one
    that writes it: reliquary places no file on a machine's drives
    (D108), and DOS redirection cannot emit the `>` the third line
    turns on — there is no escape for it in any DOS shell. Typing it
    at the guest costs a few keystrokes and needs no capability
    beyond the one this whole tier is about.

    The Ctrl-Z that ends `COPY CON` goes through `resolve_key`
    because this goes over the **carrier** seam, whose key names are
    QEMU's own qcode set: a key combo is a *list* of those names, and
    the ordinary `ctrl+z` spelling reaches QEMU as a key literally
    named `+` (D103 describes the three layers this can be entered
    at, and this is the wrong one).
    """
    machine = Machine(machine_dir_path(machine_id, home))
    machine.send_text(r"COPY CON C:\ECHOLIKE.TXT")
    for line in _ECHO_LOOKALIKE:
        machine.send_text(line)
    machine.send_keys([resolve_key("ctrl+z"), resolve_key("enter")])


def _capture_exec(home, machine_id, name, command, timeout):
    """Run one command through the exec adapter, recording the
    transcript.

    `machines.exec` normally builds its own machine handle internally.
    To capture a transcript here, this instead builds the handle
    itself with the recorder wired into its session — the same
    mechanism `--record` uses for a script, without adding a CLI flag
    just for this fixture's sake.

    **The final outcome is written explicitly here** because the raw
    transcript alone cannot show it: which rows the adapter decided
    counted as output, or which error it raised, is decided above the
    low-level session, and a success and a failure could otherwise
    produce the same-looking transcript file.
    """
    path = _capture(home, f"exec-{name}")
    writer = _TranscriptWriter(path, pace=None, command=command,
                               timeout=timeout)
    writer.open()
    guest = AgentlessGuestExec(Machine(
        machine_dir_path(machine_id, home),
        _session_wrapper=lambda session: RecordingSession(session, writer)))
    try:
        try:
            rows = guest.execute(command, timeout)
        except RunFailure as refused:
            writer.write_outcome("failed", rule=refused.rule_id)
        else:
            writer.write_outcome("ok", rows=list(rows))
    finally:
        writer.close()
    return path


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
                               context=home,
                               record=_capture(home, "install"))
        assert installed.machine_phase == "ready"

        verified = run_script("verify", blueprint="freedos",
                              context=home,
                              record=_capture(home, "verify"))
        assert verified.machine_phase == "ready"
        assert verified.machine_id == installed.machine_id

        # The handoff: the codex's readiness example leaves the
        # machine running with `ready` set, and `--expect` checks
        # that condition as part of this same call, instead of a
        # second call to read the variable back afterward.
        handed_off = run_script("ready", blueprint="freedos",
                                context=home,
                                expect={"ready": "yes"},
                                record=_capture(home, "ready"))
        assert handed_off.machine_id == installed.machine_id
        assert load_machine_state(
            handed_off.machine_id, home)["phase"] == "running", (
            "the readiness example must hand over a live machine; "
            "every other codex script ends with the guest powered off")
        assert get_machine_var("ready", machine=handed_off.machine_id,
                               context=home) == "yes"

        # And the machine the readiness example just handed over is
        # what the pathological captures need: a guest at a prompt,
        # which is expensive to reach and already standing here — and
        # is also the only thing that can plant the lookalike file,
        # now that nothing writes a machine's drives from the host.
        _plant_echo_lookalike(home, handed_off.machine_id)

        for name, command, timeout in _HAZARDS:
            written = _capture_exec(home, handed_off.machine_id, name,
                                    command, timeout)
            assert os.path.getsize(written) > 0, (
                f"the {name} capture is empty, so the recorder was "
                "never installed on the exec adapter's session")

        stop_machine(handed_off.machine_id, context=home)


def _add_font_dump_drive(home, exchange_dir):
    """Give the seeded freedos blueprint the slot F62's script writes
    through.

    The codex blueprint declares none (D108, P16) — a host directory
    is the author's own path — so a real test supplies one exactly as
    the docs tell an author to: editing the seeded copy rather than
    the codex source, which stays untouched.
    """
    path = os.path.join(blueprints_dir(home), "freedos.rlqb")
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    location = exchange_dir.replace("\\", "/")
    text = text.replace(
        '"cdrom0": null',
        '"cdrom0": null,\n      "floppy0": {\n        "type": "media",\n'
        f'        "location": "{location}",\n        "materialize": "use"\n'
        '      }',
        1)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def test_freedos_dump_font(integration_home):
    """F62: the guest is asked for the live font it loaded.

    A fresh install rather than a reused machine: the drive this
    script needs is not part of the codex shape, so the blueprint is
    changed and adopted (`apply-blueprint`) before the machine ever
    starts, which the shape baseline only accepts from stopped.
    """
    find_qemu()
    find_qemu_img()
    home = integration_home

    with live_external_effects():
        seed_blueprint("freedos", context=home)
        seed_script("freedos-dump-font", context=home)

        exchange = os.path.join(home, "font-dump-exchange")
        os.makedirs(exchange, exist_ok=True)
        _add_font_dump_drive(home, exchange)

        installed = run_script("install", blueprint="freedos", context=home,
                               record=_capture(home, "dump-font-install"))
        assert installed.machine_phase == "ready"

        apply_blueprint(machine=installed.machine_id, context=home)

        run_script("freedos-dump-font", machine=installed.machine_id,
                  context=home, record=_capture(home, "dump-font"))

        written = os.listdir(exchange)
        assert len(written) == 1, (
            f"expected one dumped file in {exchange}, found {written}")
        assert os.path.getsize(os.path.join(exchange, written[0])) == 4096

        stop_machine(installed.machine_id, context=home)
