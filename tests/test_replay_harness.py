# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The replay harness's own round trip: record a run, then replay it.

F43's corpus is captured rather than authored, so this module cannot
be the corpus — it is the proof that the path the corpus will run on
works, taken against a transcript this test records itself. What it
pins is the claim `screen-transcripts.md` makes and nothing above the
seam can check on its own: a recorded run, replayed, drives the real
interpretation layer to the same carrier calls in the same order.
"""

import contextlib
import json
import os
from unittest import mock

import pytest

from reliquary.control_display import DisplayConsole
from reliquary.errors import PreflightError
from reliquary.interaction_agentless import AgentlessGuestExec
from reliquary.script_parser import parse_script
from reliquary.script_runner import _ScriptEngine
from reliquary.transcript import (RecordingSession, TranscriptError,
                                  _TranscriptWriter)
from tests import fake_backend, replay

_SCRIPT = ('platform dos\n'
           'entry only\n'
           'phase only {\n'
           '    wait "C:\\>"\n'
           '    enter "DIR"\n'
           '    finish\n'
           '}\n')

#: A screen holding a DOS prompt, which is what `wait` is looking for
#: and what the echo scan reads back from.
_ROWS = ["C:\\>"] + [""] * 24


def _engine(home, machine_home, console, **rest):
    engine = _ScriptEngine(parse_script(_SCRIPT), "abcd" * 8, home,
                           machine_home, script_path="/tmp/demo.rlqs",
                           **rest)
    engine._port = 5555
    engine._console = console
    return engine


@contextlib.contextmanager
def _machine_state():
    """The lifecycle stubbed out; the interpretation layer is not."""
    with mock.patch("reliquary.script_runner._machines") as machines:
        machines.load_machine_state.return_value = {"phase": "running"}
        machines.read_vm_state.return_value = {
            "backend": "qemu", "backend-id": "reliquary-plain-0",
            "token": "0" * 32, "endpoint": {"port": 5555}}
        yield machines


def _record(tmp_path):
    """Run once against a fake session, capturing a transcript."""
    home = str(tmp_path)
    machine_home = os.path.join(home, "machine")
    os.makedirs(machine_home, exist_ok=True)
    path = os.path.join(home, "run.rlqt")
    writer = _TranscriptWriter(path, pace=0.05)
    writer.open()
    with fake_backend.installed() as adapter:
        session = RecordingSession(
            fake_backend.FakeSession(adapter, {}, rows=_ROWS), writer)
        engine = _engine(home, machine_home,
                         replay.console_over(session), record_pace=0.05,
                         recording_writer=writer)
        with _machine_state():
            engine.run()
    writer.close()
    return path, machine_home, home


def test_a_recorded_run_replays_through_the_interpretation_layer(tmp_path):
    """The tracer bullet: capture, then drive the real layer off it.

    Nothing here is stubbed between the transcript and the runner —
    `DisplayConsole`, the prompt reading and the dispatch are the
    shipped ones. A divergence surfaces as a `TranscriptError` from
    the replay session rather than as a quiet pass.
    """
    path, machine_home, home = _record(tmp_path)
    console, session = replay.replay_console(path)
    engine = _engine(home, machine_home, console)
    with _machine_state():
        engine.run()
    assert engine.events.events[-1]["outcome"] == "ok"


def test_a_transcript_refuses_a_call_it_never_captured(tmp_path):
    """The fails-loudly rule, which is what makes a fixture an assertion.

    A run that sends different keys than the capture recorded is a
    regression in the layer under test, and the replay session names
    it (P11) instead of improvising an answer. Without this the corpus
    would report a pass for any run that merely got to the end.
    """
    path, machine_home, home = _record(tmp_path)
    diverged = parse_script(_SCRIPT.replace('enter "DIR"', 'enter "VER"'))
    console, _session = replay.replay_console(path)
    engine = _ScriptEngine(diverged, "abcd" * 8, home, machine_home,
                           script_path="/tmp/demo.rlqs")
    engine._port = 5555
    engine._console = console
    with _machine_state():
        with pytest.raises(TranscriptError) as caught:
            engine.run()
    assert caught.value.rule_id == "transcript.send-keys-mismatch"


class _EchoingGuest:
    """A DOS screen that echoes a command, answers it, and prompts again.

    Enough of a guest for the exec adapter to have something to
    interpret: the echo it scans back for, output between it and the
    prompt, and the prompt itself. The real screens are the corpus's
    job — what is under test here is that a captured command replays
    to the same conclusion.
    """

    backend = "fake"

    def __init__(self):
        self.rows = ["C:\\>"] + [""] * 24
        self._reads_since_command = None

    def native(self):
        raise AssertionError("no native session in a fake guest")

    def text_screen(self):
        if self._reads_since_command is not None:
            self._reads_since_command += 1
            if self._reads_since_command == 3:
                self.rows = ["C:\\>VER", "FreeDOS 1.4", "C:\\>"] + [""] * 22
        return list(self.rows), [[0x07] * 80 for _ in range(25)]

    def send_keys(self, combos, delay=0.06):
        self.rows = ["C:\\>VER"] + [""] * 24
        self._reads_since_command = 0

    def screenshot(self, path):
        return path

    def change_medium(self, drive_key, path=None):
        pass


def test_an_exec_run_replays_to_the_conclusion_it_reached(tmp_path):
    """The second kind of fixture: a command rather than a script.

    Prompt detection and echo scanning are the exec adapter's, so a
    script capture never touches them — and at the seam a run that
    returned the right rows and one that returned somebody else's are
    the same file. The capture therefore states its conclusion, and
    that is what the replay is held to.
    """
    path = os.path.join(str(tmp_path), "exec.rlqt")
    writer = _TranscriptWriter(path, pace=0.05, command="VER", timeout=30)
    writer.open()
    guest = RecordingSession(_EchoingGuest(), writer)
    recorded = AgentlessGuestExec(replay.machine_handle(guest)).execute(
        "VER", 30)
    writer.write_outcome("ok", rows=list(recorded))
    writer.close()
    assert recorded == ("FreeDOS 1.4",)

    with replay.replaying_exec(path) as (guest, session, header):
        replayed = guest.execute(header.command, header.timeout)
    assert list(replayed) == header.outcome["rows"]
    assert session.remaining_calls() == 0


_LIFECYCLE = ('platform dos\n'
              'machine stopped\n'
              'entry only\n'
              'phase only {\n'
              '    start\n'
              '    wait "C:\\>"\n'
              '    screenshot installed\n'
              '    enter "fdapm poweroff"\n'
              '    wait machine=stopped\n'
              '    finish\n'
              '}\n')


def test_a_whole_lifecycle_replays_off_a_capture(tmp_path):
    """The shape every codex script has, with no hypervisor in it.

    A capture holds the carrier and nothing above it, so the two
    halves the harness supplies are exercised here rather than only by
    the corpus: `MachineLayer` answers the phase a script starts in and
    the `start` it makes, and the machine going away — recorded by the
    run, because the seam refuses the session before the wrapper
    exists — is what answers the closing `wait machine=stopped`. The
    `screenshot` goes through the same handle as every other carrier
    call, which is how it reaches the transcript at all.
    """
    home = str(tmp_path)
    machine_home = os.path.join(home, "machine")
    os.makedirs(machine_home, exist_ok=True)
    path = os.path.join(home, "run.rlqt")
    script = parse_script(_LIFECYCLE)
    # The recording side reaches the carrier through the real handle,
    # which resolves the adapter from the recorded VM identity; only
    # the replay stands a machine up from nothing.
    with open(os.path.join(machine_home, "machine.json"), "w",
              encoding="utf-8") as handle:
        json.dump({"id": "plain-0", "phase": "running",
                   "vm": {"backend": "qemu",
                          "backend-id": "reliquary-plain-0",
                          "token": "0" * 32,
                          "endpoint": {"port": 5555}}}, handle)
    writer = _TranscriptWriter(path, pace=0.05)
    writer.open()
    recording = replay.MachineLayer(machine_id="plain-0",
                                    machine_home=machine_home)
    with fake_backend.installed() as adapter:
        adapter.session_rows = _ROWS

        def takes_it_and_stops_answering(self, combos, delay=0.06):
            """The `enter` is `fdapm poweroff`: the guest goes down.

            At the seam that has exactly one form — the next session
            refuses to open, because identity cannot be verified
            against a machine that is gone.
            """
            adapter.session_error = PreflightError(
                "the recorded VM is not reachable",
                rule_id="machine.vm-unreachable")

        engine = _ScriptEngine(script, "plain-0", home, machine_home,
                               script_path="/tmp/demo.rlqs",
                               record_pace=0.05, recording_writer=writer)
        with mock.patch("reliquary.script_runner._machines", recording), \
                mock.patch.object(fake_backend.FakeSession, "send_keys",
                                  takes_it_and_stops_answering):
            engine.run()
    writer.close()

    replayed = replay.MachineLayer(machine_id="plain-0",
                                   machine_home=machine_home)
    with replay.replaying(path, machines=replayed) as (
            session, layer, clock, header):
        engine = replay.engine_for(script, home, machine_home, clock,
                                   header)
        engine._machine_id = "plain-0"
        engine.run()
    assert engine.events.events[-1]["outcome"] == "ok"
    assert session.remaining_calls() == 0
    assert [call[0] for call in layer.calls] == ["start", "mark-stopped"]
