# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Round-trip and reconstruction tests for screen transcripts.

Relies on :mod:`tests.fake_backend` — no unit test launches a real
backend. The interpretation layer runs unmodified above the replay
session, which is what makes the fixtures worth having (F42).
"""

import io
import os
import time

import pytest

from reliquary import transcript
from reliquary.control_display import DisplayConsole
from reliquary.transcript import (RecordingSession, ReplaySession,
                                  _TranscriptWriter, TranscriptError,
                                  compute_deltas, compute_digest)


class _FakeInnerSession:
    """A session double whose carriers respond to the recording wrapper."""

    def __init__(self, rows=None, attributes=None):
        self.rows = rows if rows is not None else [""] * 25
        self.attributes = (attributes if attributes is not None
                           else [[0x07] * 80 for _ in range(25)])
        self.keys = []
        self.media_changes = []
        self.screenshots_taken = []
        self.backend = "fake"

    def native(self):
        return object()

    def send_keys(self, combos, delay=0.06):
        self.keys.extend(list(combo) for combo in combos)

    def text_screen(self):
        return list(self.rows), [list(row) for row in self.attributes]

    def screenshot(self, path):
        self.screenshots_taken.append(path)
        return path

    def change_medium(self, drive_key, path=None):
        self.media_changes.append((drive_key, path))


class _StringWriter(_TranscriptWriter):
    """A ``_TranscriptWriter`` that writes to a ``StringIO``.

    Overrides ``open``, ``close``, and ``_write_json`` so the parent
    never touches the filesystem. All three StringIO tests share one
    class.
    """

    def __init__(self, out, pace):
        super().__init__("stringio", pace)
        self._out = out

    def open(self, clock=time.monotonic, now=transcript._utc_now):
        self._started = clock()
        self._file = True  # sentinel: truthy, never None
        # The parent emits a header on open; reproduce that here so
        # the first content line is the header, not the first frame.
        header = {"format": "rlqt-1", "pace": self._pace,
                  "secret-recorded": False}
        self._write_json(header)

    def close(self):
        self._file = None

    def _write_json(self, document):
        self._out.write(transcript.json.dumps(document, default=str) + "\n")


@pytest.fixture
def target(tmp_path):
    """A path for a transcript file the test writes and reads back."""
    return str(tmp_path / "run.rlqt")


def _lines(stream):
    return [line.strip() for line in stream.getvalue().splitlines()
            if line.strip()]


# The frame digest, and what a delta carries.

def test_digest_is_repeatable():
    rows = ["", "C:\\>", ""]
    attributes = [[0x07] * 80 for _ in range(3)]
    assert compute_digest(rows, attributes) == compute_digest(
        rows, attributes)


def test_digest_depends_on_attributes():
    rows = ["hello"]
    assert compute_digest(rows, [[0x07] * 80]) != compute_digest(
        rows, [[0x70] * 80])


def test_deltas():
    assert compute_deltas(["one", "two", "three"],
                          ["one", "TWO", "three"]) == {"1": "TWO"}


def test_deltas_empty():
    assert compute_deltas(["a", "b"], ["a", "b"]) == {}


# Recording through the carrier seam, and reading it back.

def test_write_and_read_full_round_trip():
    stream = io.StringIO()
    writer = _StringWriter(stream, pace=0.1)
    writer.open()

    inner = _FakeInnerSession(rows=["", "", "C:\\>"])
    rec = RecordingSession(inner, writer)

    # First read — a keyframe.
    rows, _attrs = rec.text_screen()
    assert rows[-1] == "C:\\>"

    # Second identical read — absorbed.
    rows2, _attrs2 = rec.text_screen()
    assert rows2 == rows

    # Send keys — a call, then the next frame is a keyframe.
    rec.send_keys([["ret"]], delay=0.06)
    assert len(inner.keys) == 1

    # Change the screen.
    inner.rows = ["", "", "", "A:\\>"]

    # Next read after call — keyframe.
    rec.text_screen()

    writer.close()

    # Parse and verify the transcript.
    lines = _lines(stream)
    assert len(lines) >= 3, (
        f"expected at least header + frame + call, got {len(lines)} lines")

    header = transcript.json.loads(lines[0])
    assert header["format"] == "rlqt-1"
    assert header["pace"] == 0.1
    assert not header["secret-recorded"]

    # First entry is a keyframe.
    frame1 = transcript.json.loads(lines[1])
    assert frame1["type"] == "frame"
    assert frame1.get("keyframe")
    assert frame1["rows"] == ["", "", "C:\\>"]


def test_secret_stops_writing():
    stream = io.StringIO()
    writer = _StringWriter(stream, pace=0.1)
    writer.open()

    inner = _FakeInnerSession()
    rec = RecordingSession(inner, writer)
    rec.text_screen()

    writer.stop("secret entered")
    assert writer.stopped

    # Further writes are suppressed.
    rec.text_screen()
    rec.send_keys([["a"]])

    lines = _lines(stream)
    # header + frame + secret-stopped. No more.
    assert len(lines) == 3, f"expected 3 lines, got {len(lines)}: {lines}"
    assert transcript.json.loads(lines[-1])["type"] == "secret-stopped"


def test_replay_verifies_digests(target):
    writer = _TranscriptWriter(target, pace=0.1)
    writer.open()
    inner = _FakeInnerSession(rows=["", "PROMPT>"])
    rec = RecordingSession(inner, writer)
    rec.text_screen()
    writer.close()

    # Read it back — should pass digest check.
    entries = transcript._TranscriptReader(target).read()
    assert len(entries) >= 1
    assert entries[0].kind == "frame"

    # Replay through the ReplaySession.
    rows, _attrs = ReplaySession(entries).text_screen()
    assert rows[-1] == "PROMPT>"


def test_replay_detects_wrong_call(target):
    writer = _TranscriptWriter(target, pace=0.1)
    writer.open()
    inner = _FakeInnerSession()
    rec = RecordingSession(inner, writer)
    rec.text_screen()
    rec.send_keys([["ret"]])
    writer.close()

    entries = transcript._TranscriptReader(target).read()
    replay = ReplaySession(entries)
    replay.text_screen()  # consume the frame
    # Wrong combo
    with pytest.raises(TranscriptError) as caught:
        replay.send_keys([["esc"]])
    assert "send_keys mismatch" in str(caught.value)


def test_display_console_over_recording():
    """The interpretation layer runs on top of the recording."""
    stream = io.StringIO()
    writer = _StringWriter(stream, pace=0.1)
    writer.open()
    inner = _FakeInnerSession(rows=["", "", "", "A:\\>"])
    rec = RecordingSession(inner, writer)

    # DisplayConsole builds on the session like normal.
    console = DisplayConsole(rec)
    assert console.screen_text()[-1] == "A:\\>"

    # The transcript recorded the frame through the recording
    # wrapper even though the console went through DisplayConsole.
    lines = _lines(stream)
    # header + at least one frame
    assert len(lines) >= 2, (
        f"expected header + frame, got {len(lines)} lines")


def test_empty_transcript_is_error(target):
    with open(target, "w", encoding="utf-8"):
        pass
    with pytest.raises(TranscriptError) as caught:
        transcript._TranscriptReader(target).read()
    assert "empty transcript" in str(caught.value)


def test_bad_digest_is_detected(target):
    writer = _TranscriptWriter(target, pace=0.1)
    writer.open()
    inner = _FakeInnerSession(rows=["HELLO"])
    rec = RecordingSession(inner, writer)
    rec.text_screen()
    writer.close()

    # Tamper with the digest in the file.
    with open(target) as handle:
        content = handle.read()
    with open(target, "w") as handle:
        handle.write(content.replace('"digest": "', '"digest": "0000'))

    with pytest.raises(TranscriptError) as caught:
        transcript._TranscriptReader(target).read()
    assert "digest mismatch" in str(caught.value)


def test_change_medium_recorded_and_replayed(target):
    writer = _TranscriptWriter(target, pace=0.1)
    writer.open()
    inner = _FakeInnerSession()
    rec = RecordingSession(inner, writer)
    rec.text_screen()
    rec.change_medium("fd0", None)
    writer.close()

    entries = transcript._TranscriptReader(target).read()
    calls = [entry for entry in entries if entry.kind == "call"]
    assert len(calls) == 1
    assert calls[0].data["carrier"] == "change_medium"

    replay = ReplaySession(entries)
    replay.text_screen()
    replay.change_medium("fd0", None)
