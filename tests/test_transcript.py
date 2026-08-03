# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Round-trip and reconstruction tests for screen transcripts.

Relies on :mod:`tests.fake_backend` — no unit test launches a real
backend. The interpretation layer runs unmodified above the replay
session, which is what makes the fixtures worth having (F42).
"""

import io
import os
import sys
import tempfile
import time
import unittest

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
        self._out.write(transcript.json.dumps(
            document, default=str) + "\n")


class DigestTests(unittest.TestCase):

    def test_digest_is_repeatable(self):
        rows = ["", "C:\\>", ""]
        attributes = [[0x07] * 80 for _ in range(3)]
        first = compute_digest(rows, attributes)
        second = compute_digest(rows, attributes)
        self.assertEqual(first, second)

    def test_digest_depends_on_attributes(self):
        rows = ["hello"]
        attr_a = [[0x07] * 80]
        attr_b = [[0x70] * 80]
        self.assertNotEqual(
            compute_digest(rows, attr_a),
            compute_digest(rows, attr_b))

    def test_deltas(self):
        before = ["one", "two", "three"]
        after = ["one", "TWO", "three"]
        self.assertEqual(compute_deltas(before, after), {"1": "TWO"})

    def test_deltas_empty(self):
        before = ["a", "b"]
        after = ["a", "b"]
        self.assertEqual(compute_deltas(before, after), {})


class RecordingTests(unittest.TestCase):

    def test_write_and_read_full_round_trip(self):
        stream = io.StringIO()
        writer = _StringWriter(stream, pace=0.1)
        writer.open()

        inner = _FakeInnerSession(rows=["", "", "C:\\>"])
        rec = RecordingSession(inner, writer)

        # First read — a keyframe.
        rows, attrs = rec.text_screen()
        self.assertEqual(rows[-1], "C:\\>")

        # Second identical read — absorbed.
        rows2, attrs2 = rec.text_screen()
        self.assertEqual(rows2, rows)

        # Send keys — a call, then the next frame is a keyframe.
        rec.send_keys([["ret"]], delay=0.06)
        self.assertEqual(len(inner.keys), 1)

        # Change the screen.
        inner.rows = ["", "", "", "A:\\>"]

        # Next read after call — keyframe.
        rec.text_screen()

        writer.close()

        # Parse and verify the transcript.
        content = stream.getvalue()
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        self.assertTrue(len(lines) >= 3,
                        f"expected at least header + frame + call, got "
                        f"{len(lines)} lines")

        header = transcript.json.loads(lines[0])
        self.assertEqual(header["format"], "rlqt-1")
        self.assertEqual(header["pace"], 0.1)
        self.assertFalse(header["secret-recorded"])

        # First entry is a keyframe.
        frame1 = transcript.json.loads(lines[1])
        self.assertEqual(frame1["type"], "frame")
        self.assertTrue(frame1.get("keyframe"))
        self.assertEqual(frame1["rows"], ["", "", "C:\\>"])

    def test_secret_stops_writing(self):
        stream = io.StringIO()
        writer = _StringWriter(stream, pace=0.1)
        writer.open()

        inner = _FakeInnerSession()
        rec = RecordingSession(inner, writer)
        rec.text_screen()

        writer.stop("secret entered")
        self.assertTrue(writer.stopped)

        # Further writes are suppressed.
        rec.text_screen()
        rec.send_keys([["a"]])

        content = stream.getvalue()
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        # header + frame + secret-stopped. No more.
        self.assertEqual(len(lines), 3,
                         f"expected 3 lines, got {len(lines)}: {lines}")
        last = transcript.json.loads(lines[-1])
        self.assertEqual(last["type"], "secret-stopped")

    def test_replay_verifies_digests(self):
        # Write a minimal valid transcript to disk.
        with tempfile.NamedTemporaryFile(
                mode="w", suffix=".rlqt", delete=False) as handle:
            path = handle.name

        try:
            writer = _TranscriptWriter(path, pace=0.1)
            writer.open()
            inner = _FakeInnerSession(rows=["", "PROMPT>"])
            rec = RecordingSession(inner, writer)
            rec.text_screen()
            writer.close()

            # Read it back — should pass digest check.
            reader = transcript._TranscriptReader(path)
            entries = reader.read()
            self.assertTrue(len(entries) >= 1)
            self.assertEqual(entries[0].kind, "frame")

            # Replay through the ReplaySession.
            replay = ReplaySession(entries)
            rows, attrs = replay.text_screen()
            self.assertEqual(rows[-1], "PROMPT>")
        finally:
            os.unlink(path)

    def test_replay_detects_wrong_call(self):
        with tempfile.NamedTemporaryFile(
                mode="w", suffix=".rlqt", delete=False) as handle:
            path = handle.name

        try:
            writer = _TranscriptWriter(path, pace=0.1)
            writer.open()
            inner = _FakeInnerSession()
            rec = RecordingSession(inner, writer)
            rec.text_screen()
            rec.send_keys([["ret"]])
            writer.close()

            reader = transcript._TranscriptReader(path)
            entries = reader.read()
            replay = ReplaySession(entries)
            replay.text_screen()  # consume the frame
            # Wrong combo
            with self.assertRaises(TranscriptError) as ctx:
                replay.send_keys([["esc"]])
            self.assertIn("send_keys mismatch", str(ctx.exception))
        finally:
            os.unlink(path)

    def test_display_console_over_recording(self):
        """The interpretation layer runs on top of the recording."""
        stream = io.StringIO()
        writer = _StringWriter(stream, pace=0.1)
        writer.open()
        inner = _FakeInnerSession(rows=["", "", "", "A:\\>"])
        rec = RecordingSession(inner, writer)

        # DisplayConsole builds on the session like normal.
        console = DisplayConsole(rec)
        text_rows = console.screen_text()
        self.assertEqual(text_rows[-1], "A:\\>")

        # The transcript recorded the frame through the recording
        # wrapper even though the console went through DisplayConsole.
        content = stream.getvalue()
        lines = [l for l in content.splitlines() if l.strip()]
        # header + at least one frame
        self.assertTrue(len(lines) >= 2,
                        f"expected header + frame, got {len(lines)} lines")

    def test_empty_transcript_is_error(self):
        with tempfile.NamedTemporaryFile(
                mode="w", suffix=".rlqt", delete=False) as handle:
            path = handle.name
        try:
            reader = transcript._TranscriptReader(path)
            with self.assertRaises(TranscriptError) as ctx:
                reader.read()
            self.assertIn("empty transcript", str(ctx.exception))
        finally:
            os.unlink(path)

    def test_bad_digest_is_detected(self):
        with tempfile.NamedTemporaryFile(
                mode="w", suffix=".rlqt", delete=False) as handle:
            path = handle.name

        try:
            writer = _TranscriptWriter(path, pace=0.1)
            writer.open()
            inner = _FakeInnerSession(rows=["HELLO"])
            rec = RecordingSession(inner, writer)
            rec.text_screen()
            writer.close()

            # Tamper with the digest in the file.
            with open(path) as fh:
                content = fh.read()
            content = content.replace(
                '"digest": "', '"digest": "0000')
            with open(path, "w") as fh:
                fh.write(content)

            reader = transcript._TranscriptReader(path)
            with self.assertRaises(TranscriptError) as ctx:
                reader.read()
            self.assertIn("digest mismatch", str(ctx.exception))
        finally:
            os.unlink(path)

    def test_change_medium_recorded_and_replayed(self):
        with tempfile.NamedTemporaryFile(
                mode="w", suffix=".rlqt", delete=False) as handle:
            path = handle.name

        try:
            writer = _TranscriptWriter(path, pace=0.1)
            writer.open()
            inner = _FakeInnerSession()
            rec = RecordingSession(inner, writer)
            rec.text_screen()
            rec.change_medium("fd0", None)
            writer.close()

            reader = transcript._TranscriptReader(path)
            entries = reader.read()
            calls = [e for e in entries if e.kind == "call"]
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0].data["carrier"], "change_medium")

            replay = ReplaySession(entries)
            replay.text_screen()
            replay.change_medium("fd0", None)
        finally:
            os.unlink(path)