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
import os
from unittest import mock

import pytest

from reliquary.control_display import DisplayConsole
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
