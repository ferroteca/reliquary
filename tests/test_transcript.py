# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Round-trip and reconstruction tests for screen transcripts.

Relies on :mod:`tests.fake_backend` — no unit test launches a real
backend. The interpretation layer runs unmodified above the replay
session, which is what makes the fixtures worth having (F42).
"""

import io
import json
import os
import time

import pytest

from reliquary import transcript
from reliquary.control_display import DisplayConsole
from reliquary.errors import PreflightError
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

    def text_screen(self, font_banks=()):
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
        # The parent flushes the frame it is still holding before it
        # lets go of the file; a double that forgot to would lose
        # every transcript's last frame.
        self._flush_frame()
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


# Attributes are written as runs, and the digest never sees them that way.

def test_attribute_rows_pack_into_runs():
    assert transcript.pack_attributes(
        [[7] * 4 + [112] * 2, [7] * 6]) == [[[4, 7], [2, 112]], [[6, 7]]]


def test_packed_attributes_come_back_whole():
    rows = [[7] * 80, [7] * 10 + [112] * 15 + [7] * 55]
    assert transcript.unpack_attributes(
        transcript.pack_attributes(rows)) == rows


def test_a_keyframe_writes_runs_and_reconstructs_the_screen(target):
    """The encoding is the file's; the screen the digest covers is not.

    Seventy per cent of the first real capture was per-cell attribute
    arrays — eighty tokens a row, twenty-five rows a keyframe, where a
    DOS row is one to four runs. The digest still covers the screen
    expanded, so what a fixture asserts cannot depend on how the file
    spells it.
    """
    attributes = [[0x07] * 80 for _ in range(3)]
    attributes[1] = [0x07] * 10 + [0x70] * 15 + [0x07] * 55
    inner = _FakeInnerSession(rows=["", "  English", ""],
                              attributes=attributes)
    writer = _TranscriptWriter(target, pace=0.05)
    writer.open()
    RecordingSession(inner, writer).text_screen()
    writer.close()
    written = [json.loads(line) for line in open(target, encoding="utf-8")
               if line.strip()]
    assert written[1]["attributes"][1] == [[10, 7], [15, 112], [55, 7]]
    replayed = ReplaySession(
        transcript._TranscriptReader(target).read()).text_screen()
    assert replayed == (["", "  English", ""], attributes)


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
    # Closing first, because a frame is held open until the screen
    # changes, a call interrupts, or the transcript closes — that is
    # what lets it carry the count of reads it absorbed.
    writer.close()
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


# The absorbed sample count: recorded, and honoured on replay.

def test_an_absorbed_sample_is_counted_on_the_frame_it_held():
    """A collapsed frame says how many reads it stood for.

    "This screen held two seconds across forty samples" and "it held
    two seconds with nobody looking" are different facts, and only
    the first says the guest was quiet (P11). Absorbing a read
    without counting it throws away the half that carries the claim.
    """
    out = io.StringIO()
    writer = _StringWriter(out, pace=0.05)
    writer.open()
    session = RecordingSession(_FakeInnerSession(rows=["idle"]), writer)
    for _ in range(3):
        session.text_screen()
    writer.close()
    frames = [json.loads(line) for line in _lines(out)
              if json.loads(line).get("type") == "frame"]
    assert len(frames) == 1, "identical reads collapse to one frame"
    assert frames[0]["samples"] == 3


def test_replay_returns_a_collapsed_frame_once_per_absorbed_sample():
    """Replay reads as many times as the capture was read.

    The recorder collapses identical screens, so a replay that
    advances one entry per read runs out of transcript long before
    the run runs out of statements — which is any real capture, since
    a DOS screen holds still for most of a boot.
    """
    out = io.StringIO()
    writer = _StringWriter(out, pace=0.05)
    writer.open()
    session = RecordingSession(_FakeInnerSession(rows=["idle"]), writer)
    for _ in range(3):
        session.text_screen()
    writer.close()
    entries = [transcript._TranscriptEntry(json.loads(line))
               for line in _lines(out)[1:]]
    replay = ReplaySession(entries)
    for _ in range(3):
        assert replay.text_screen()[0] == ["idle"]


def test_a_frame_changing_only_its_attributes_reconstructs(target):
    """A cursor menu moves its selection by attribute alone.

    The keyframe/delta decision read *rows* while the digest covers
    rows **and** attributes, so a screen whose attributes changed
    under identical text was written as an empty row delta and
    rebuilt from the previous frame's attributes — a digest mismatch.
    The first real capture hit it 29 entries in, on the install's
    first menu.
    """
    rows = ["", "  Select language", "  English", "  Deutsch"]
    plain = [[0x07] * 80 for _ in range(len(rows))]
    highlighted = [list(row) for row in plain]
    highlighted[2] = [0x70] * 80          # the selection bar moves
    inner = _FakeInnerSession(rows=rows, attributes=plain)
    writer = _TranscriptWriter(target, pace=0.05)
    writer.open()
    session = RecordingSession(inner, writer)
    session.text_screen()
    inner.attributes = highlighted
    session.text_screen()
    writer.close()
    entries = transcript._TranscriptReader(target).read()
    assert len(entries) == 2, "two distinct screens, two frames"


def test_a_read_where_the_capture_sent_keys_is_named_there(target):
    """A desync is reported where it happens, not where it surfaces.

    Reading past a recorded call used to be silent, so the replay
    quietly took the *next* call as its answer and every keystroke
    after it was compared against the wrong one — the mismatch then
    landed minutes later, against a screen neither run was looking at.
    """
    writer = _TranscriptWriter(target, pace=0.05)
    writer.open()
    inner = _FakeInnerSession(rows=["MENU"])
    session = RecordingSession(inner, writer)
    session.text_screen()
    session.send_keys([["down"]])
    inner.rows = ["MENU MOVED"]
    session.text_screen()
    writer.close()
    replay = ReplaySession(transcript._TranscriptReader(target).read())
    replay.text_screen()
    with pytest.raises(TranscriptError) as caught:
        replay.text_screen()
    assert caught.value.rule_id == "transcript.read-before-call"


def test_a_screenshot_replays_by_name_and_not_by_directory(target):
    """Where an image lands is the machine's; what it is called is the run's.

    A capture records the absolute path it wrote, and a replay runs
    against a different machine directory every time — comparing the
    whole path would refuse every fixture. The name is the part the
    script chose (`screenshot installed`), and a changed one is a real
    divergence.
    """
    writer = _TranscriptWriter(target, pace=0.05)
    writer.open()
    session = RecordingSession(_FakeInnerSession(), writer)
    session.screenshot(os.path.join("C:", "capture", "machine",
                                    "screenshots", "installed.png"))
    writer.close()
    replay = ReplaySession(transcript._TranscriptReader(target).read())
    replay.screenshot(os.path.join("/tmp", "replay", "installed.png"))
    replay2 = ReplaySession(transcript._TranscriptReader(target).read())
    with pytest.raises(TranscriptError) as caught:
        replay2.screenshot(os.path.join("/tmp", "replay", "verified.png"))
    assert caught.value.rule_id == "transcript.screenshot-mismatch"


def test_a_vanished_vm_replays_as_the_refusal_it_was(target):
    """The shutdown a DOS install ends on, put back where it happened.

    The entry is written by the run rather than by the seam — the
    session refuses to open, so no wrapper exists to record it — and
    reconstruction answers it as the adapter's own refusal, which is
    what a `wait machine=stopped` reads as the machine having stopped.
    """
    writer = _TranscriptWriter(target, pace=0.05)
    writer.open()
    session = RecordingSession(_FakeInnerSession(rows=["C:\\>"]), writer)
    session.text_screen()
    writer.write_gone("the recorded VM is not reachable")
    writer.close()
    entries = transcript._TranscriptReader(target).read()
    replay = ReplaySession(entries)
    replay.text_screen()
    with pytest.raises(PreflightError) as caught:
        replay.text_screen()
    assert caught.value.rule_id == "machine.vm-unreachable"


def test_a_changed_row_is_carried_as_a_delta(target):
    r"""The delta encoding, which the format never actually used.

    The keyframe test read `prev != rows` and took the keyframe
    branch, so deltas were emitted only when the rows were
    *identical* — an empty delta — and every real row change was
    written as a full frame. The format the design argues for on
    reviewability grounds ("row 12 became `C:\>` at 4.35s") had the
    condition backwards, so a re-recording rewrote every line and no
    transcript ever narrated anything.
    """
    inner = _FakeInnerSession(rows=["one", "two"],
                              attributes=[[0x07] * 80] * 2)
    writer = _TranscriptWriter(target, pace=0.05)
    writer.open()
    session = RecordingSession(inner, writer)
    session.text_screen()
    inner.rows = ["one", "CHANGED"]       # attributes untouched
    session.text_screen()
    writer.close()
    written = [json.loads(line) for line in open(target, encoding="utf-8")
               if line.strip()]
    frames = [entry for entry in written if entry.get("type") == "frame"]
    assert len(frames) == 2
    assert frames[0].get("keyframe"), "the first frame has no predecessor"
    assert "deltas" in frames[1], (
        "a row changed under unchanged attributes, which is exactly "
        "what a delta carries; writing a keyframe here is what made "
        "every re-recording touch every line.")
    assert frames[1]["deltas"] == {"1": "CHANGED"}
