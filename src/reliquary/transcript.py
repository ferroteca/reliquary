# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Screen transcript capture and reconstruction.

Internal debugging and corpus tool, not an application surface (D98):
no stability guarantee, no ``docs/spec/`` entry, and a change to the
format is housekeeping. The invocation -- ``--record <path>`` on
``run-script`` and ``run_script(record=)`` on the session -- *is*
surface and lands on S1/S2 in the same change.

The capture wraps the **carrier seam** (the adapter session's
``text_screen()`` / ``send_keys()`` / ``screenshot()`` /
``change_medium()``), so it is backend-neutral by construction.
Reconstruction stands a fake session at that same seam, and the
whole interpretation layer runs unmodified above it.
"""

import hashlib
import json
import os
import time
from datetime import datetime, timezone

from .errors import StaticError

_DIGEST = "sha256"

_FORMAT_VERSION = "rlqt-1"


def _utc_now():
    return datetime.now(timezone.utc)


def _stamp(moment):
    """ISO-8601 UTC with milliseconds, mirroring events.py's spelling."""
    return (moment.strftime("%Y-%m-%dT%H:%M:%S")
            + f".{moment.microsecond // 1000:03d}Z")


def _canonical(rows, attributes):
    """The canonical form for a digest: JSON of (text rows, attribute rows).

    Rows are strings; attribute rows are lists of ints, one per cell.
    Identity is the whole pair — a cursor menu moves its selection by
    attribute alone.
    """
    return json.dumps([list(rows), attributes], sort_keys=True)


def compute_digest(rows, attributes):
    """SHA-256 of the canonical screen representation.

    A few bytes per entry, checked at reconstruction so a bug or a
    hand-edited fixture fails loudly rather than yielding a screen
    that never existed.
    """
    return hashlib.new(_DIGEST,
                       _canonical(rows, attributes).encode()).hexdigest()


def compute_deltas(before, rows):
    """The rows that changed: {row_index: new_text}.

    ``before`` and ``rows`` are character-row sequences. A DOS screen
    typically changes one or two rows of twenty-five.
    """
    return {str(index): text for index, text in enumerate(rows)
            if index >= len(before) or text != before[index]}


class _TranscriptWriter:

    def __init__(self, path, pace):
        self._path = os.fspath(path)
        self._file = None
        self._pace = pace
        self._written_header = False
        self._started = None
        self._last_wall = None
        self._stopped = False
        #: The frame not yet written, held open so the reads it goes
        #: on to absorb can be counted onto it. A frame's count is not
        #: known when the frame arrives — only when the screen next
        #: changes — so writing eagerly is what threw the count away.
        self._pending = None

    def open(self, clock=time.monotonic, now=_utc_now):
        """Begin the transcript — one header line."""
        self._file = open(self._path, "w", encoding="utf-8")
        self._started = clock()
        self._last_wall = now()
        header = {"format": _FORMAT_VERSION, "pace": self._pace,
                  "secret-recorded": False}
        self._write_json(header)
        self._written_header = True

    def close(self):
        """Close the transcript; harmless when already closed."""
        self._flush_frame()
        file = self._file
        self._file = None
        if file is not None:
            file.close()

    def write_frame(self, rows, attributes, samples=1,
                    clock=time.monotonic, now=_utc_now):
        """Record one screen reading, collapsing it onto the last.

        A read identical to the one still pending is **absorbed onto
        it** rather than dropped: the frame's sample count is what
        separates "this screen held two seconds across forty samples"
        from "it held two seconds with nobody looking", and only the
        first says the guest was quiet (P11).

        The frame is therefore held until the screen changes, a call
        interrupts, or the transcript closes — its count is not
        knowable any earlier. Its timestamps stay those of the read it
        first appeared on, which is when the screen actually arrived.
        """
        if self._stopped or self._file is None:
            return
        rows = list(rows)
        attributes = [list(row) for row in attributes]
        pending = self._pending
        if pending is not None and pending["rows"] == rows and \
                pending["attributes"] == attributes:
            pending["samples"] += samples
            return
        self._flush_frame()
        self._pending = {
            "rows": rows,
            "attributes": attributes,
            "samples": samples,
            "elapsed": round(clock() - self._started, 3),
            "wall": _stamp(now()),
        }

    def _flush_frame(self):
        """Write the held frame out, with the count it absorbed."""
        pending = self._pending
        self._pending = None
        if pending is None or self._stopped or self._file is None:
            return
        rows, attributes = pending["rows"], pending["attributes"]
        entry = {
            "type": "frame",
            "elapsed": pending["elapsed"],
            "wall": pending["wall"],
            "samples": pending["samples"],
            "digest": compute_digest(rows, attributes),
        }
        prev = getattr(self, "_last_frame", None)
        prev_attributes = getattr(self, "_last_attributes", None)
        if prev is None or prev_attributes != attributes:
            # Two things force a full frame, and a changed *row* is
            # not one of them — a changed row is what a delta is for.
            #
            # A gap in sampling (a call, or the first frame) is the
            # first: continuity cannot be claimed across one, so the
            # next entry restates the screen whole.
            #
            # Changed attributes are the second, and they are the
            # whole of what a delta cannot carry: deltas are rows, the
            # digest covers rows *and* attributes, so a selection bar
            # moving under identical text would otherwise be written
            # as an empty row delta and rebuilt from the wrong
            # attributes. A cursor menu moves by attribute alone.
            entry["keyframe"] = True
            entry["rows"] = rows
            entry["attributes"] = attributes
        else:
            entry["deltas"] = compute_deltas(prev, rows)
        self._last_frame = list(rows)
        self._last_attributes = [list(row) for row in attributes]
        self._write_json(entry)

    def write_call(self, carrier, fields=None, clock=time.monotonic,
                   now=_utc_now):
        """Record a carrier call the run made."""
        if self._stopped or self._file is None:
            return
        # A call ends the frame it interrupted: the count that frame
        # absorbed is complete, and what follows is a new screen.
        self._flush_frame()
        entry = {
            "type": "call",
            "elapsed": round(clock() - self._started, 3),
            "wall": _stamp(now()),
            "carrier": carrier,
        }
        if fields:
            entry.update(fields)
        # A call is a sampling gap: the next frame must be a keyframe.
        self._last_frame = None
        self._last_attributes = None
        self._write_json(entry)

    def stop(self, reason, clock=time.monotonic, now=_utc_now):
        """End recording mid-run — a bound secret reached the guest."""
        if self._stopped or self._file is None:
            return
        # What was captured before the secret is kept whole, count
        # and all; it is everything after that stops.
        self._flush_frame()
        entry = {
            "type": "secret-stopped",
            "elapsed": round(clock() - self._started, 3),
            "wall": _stamp(now()),
            "reason": reason,
        }
        self._write_json(entry)
        self._stopped = True

    @property
    def path(self):
        return self._path

    @property
    def stopped(self):
        return self._stopped

    def _write_json(self, document):
        self._file.write(json.dumps(document, default=str) + "\n")
        self._file.flush()

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *exc):
        self.close()


class RecordingSession:
    """Wraps an adapter session, recording every carrier call.

    Sits at the carrier seam — between the adapter session and
    ``DisplayConsole`` — so the entire interpretation layer runs
    unmodified above it. Consecutive identical frames are collapsed,
    absorbing their sample count; a keyframe is written after every
    sampling gap.
    """

    def __init__(self, inner_session, writer):
        self._inner = inner_session
        self._writer = writer
        self._frame_added = False

    @property
    def backend(self):
        return self._inner.backend

    def native(self):
        return self._inner.native()

    def send_keys(self, combos, delay=0.06):
        self._inner.send_keys(combos, delay)
        self._writer.write_call(
            "send_keys",
            fields={"combos": list(list(c) for c in combos)})

    def text_screen(self):
        """Return the screen, and offer every read to the transcript.

        **Every** read is offered, including one identical to the
        last: collapsing is the writer's, because a frame's absorbed
        sample count is only known once the screen changes, and a read
        dropped here would be a sample the transcript could never
        count. A keyframe after every sampling gap (a call) bounds the
        damage when a reporter is missing.
        """
        rows, attributes = self._inner.text_screen()
        # Copy the mutable lists the adapter hands back, so what the
        # transcript holds cannot be edited from underneath it.
        rows = list(rows)
        attributes = [list(row) for row in attributes]
        writer = self._writer
        if writer is not None and not writer.stopped:
            writer.write_frame(rows, attributes)
        return rows, attributes

    def screenshot(self, path):
        result = self._inner.screenshot(path)
        self._writer.write_call("screenshot",
                                fields={"path": os.fspath(path)})
        return result

    def change_medium(self, drive_key, path=None):
        self._inner.change_medium(drive_key, path)
        fields = {"drive_key": drive_key}
        if path is not None:
            fields["path"] = os.fspath(path)
        self._writer.write_call("change_medium", fields=fields)


# -- reconstruction ---------------------------------------------------


class _TranscriptEntry:
    """One entry from a transcript file, typed by its ``type`` field."""

    __slots__ = ("data",)

    def __init__(self, data):
        self.data = data

    @property
    def kind(self):
        return self.data.get("type")


class _TranscriptReader:

    def __init__(self, path):
        self._path = os.fspath(path)
        self.format = None
        self.pace = None
        self.secret_recorded = False
        self._entries = None

    def read(self):
        """Parse and validate the whole transcript; return entries.

        Raises :class:`TranscriptError` on a malformed or
        digest-failing file.
        """
        if self._entries is not None:
            return self._entries
        with open(self._path, encoding="utf-8") as handle:
            lines = [line.strip() for line in handle if line.strip()]
        if not lines:
            raise TranscriptError(
                f"empty transcript: {self._path}",
                rule_id="transcript.empty")
        header = json.loads(lines[0])
        if header.get("format") != _FORMAT_VERSION:
            raise TranscriptError(
                f"unknown transcript format {header.get('format')!r}; "
                f"expected {_FORMAT_VERSION!r}",
                rule_id="transcript.unknown-format")
        self.format = header["format"]
        self.pace = header.get("pace")
        self.secret_recorded = header.get("secret-recorded", False)
        entries = []
        reconstructed_rows = None
        reconstructed_attrs = None
        for index, line in enumerate(lines[1:], start=1):
            entry_data = json.loads(line)
            kind = entry_data.get("type")
            if kind is None:
                raise TranscriptError(
                    f"entry on line {index + 1} has no type",
                    rule_id="transcript.entry-no-type")
            if kind == "frame":
                digest = entry_data.get("digest")
                if entry_data.get("keyframe"):
                    rows = entry_data["rows"]
                    attrs = entry_data.get("attributes")
                    reconstructed_rows = rows
                    reconstructed_attrs = attrs
                elif "deltas" in entry_data:
                    if reconstructed_rows is None:
                        raise TranscriptError(
                            f"delta entry on line {index + 1} with no "
                            "prior keyframe",
                            rule_id="transcript.delta-without-keyframe")
                    rows = list(reconstructed_rows)
                    for key, text in entry_data["deltas"].items():
                        rows[int(key)] = text
                else:
                    raise TranscriptError(
                        f"frame entry on line {index + 1} has neither "
                        "keyframe nor deltas",
                        rule_id="transcript.frame-no-content")
                if reconstructed_attrs is None:
                    raise TranscriptError(
                        f"frame entry on line {index + 1} before any "
                        "keyframe with attributes",
                        rule_id="transcript.frame-no-attributes")
                expected = compute_digest(rows, reconstructed_attrs)
                if digest != expected:
                    raise TranscriptError(
                        f"digest mismatch on line {index + 1}: "
                        f"expected {expected}, got {digest}",
                        rule_id="transcript.digest-mismatch")
                reconstructed_rows = rows
            entries.append(_TranscriptEntry(entry_data))
        self._entries = entries
        return entries


class ReplaySession:
    """A fake adapter session that replays from a transcript.

    Stands at the carrier seam — the same place the recording
    wrapped — so the interpretation layer runs unmodified above it.
    A request the transcript does not cover is an error naming what
    was asked (P11): never an improvised answer, never an empty one.
    """

    backend = "transcript"

    def __init__(self, entries, clock=time.monotonic):
        self._entries = entries
        self._index = 0
        self._clock = clock
        self._started = clock()
        # The current reconstructed screen.
        self._rows = None
        self._attributes = None
        #: Reads the current frame still answers before the replay
        #: advances. A capture collapses a held screen into one entry
        #: carrying the count it absorbed, so a replay that advanced
        #: once per read would run out of transcript long before the
        #: run ran out of statements.
        self._remaining = 0

    def native(self):
        raise TranscriptError(
            "a transcript has no native backend session",
            rule_id="transcript.no-native-session")

    def text_screen(self):
        if self._remaining > 0:
            # The frame is still standing: it was read this many more
            # times when it was captured.
            self._remaining -= 1
            return (list(self._rows),
                    [list(row) for row in self._attributes])
        while self._index < len(self._entries):
            entry = self._entries[self._index]
            if entry.kind != "frame":
                self._index += 1
                continue
            data = entry.data
            self._index += 1
            self._remaining = max(0, int(data.get("samples", 1)) - 1)
            if data.get("keyframe"):
                self._rows = data["rows"]
                self._attributes = data.get("attributes")
            elif "deltas" in data and self._rows is not None:
                rows = list(self._rows)
                for key, text in data["deltas"].items():
                    rows[int(key)] = text
                self._rows = rows
            if self._rows is None:
                raise TranscriptError(
                    "transcript has no keyframe before frame read",
                    rule_id="transcript.no-keyframe")
            if self._attributes is None:
                raise TranscriptError(
                    "transcript has no attributes before frame read",
                    rule_id="transcript.no-attributes")
            return (list(self._rows),
                    [list(row) for row in self._attributes])
        raise TranscriptError(
            "transcript exhausted: no more frames to read",
            rule_id="transcript.exhausted")

    def send_keys(self, combos, delay=0.06):
        entry = self._next_call("send_keys")
        expected = list(list(c) for c in combos)
        got = entry.data.get("combos")
        if got != expected:
            raise TranscriptError(
                f"send_keys mismatch at "
                f"{entry.data.get('elapsed', '?')}s: "
                f"expected {expected!r}, got {got!r}",
                rule_id="transcript.send-keys-mismatch")

    def screenshot(self, path):
        entry = self._next_call("screenshot")
        expected_path = os.fspath(path)
        got = entry.data.get("path")
        if got is not None and got != expected_path:
            raise TranscriptError(
                f"screenshot path mismatch at "
                f"{entry.data.get('elapsed', '?')}s: "
                f"expected {expected_path!r}, got {got!r}",
                rule_id="transcript.screenshot-mismatch")
        return expected_path

    def change_medium(self, drive_key, path=None):
        entry = self._next_call("change_medium")
        got_drive = entry.data.get("drive_key")
        if got_drive != drive_key:
            raise TranscriptError(
                f"change_medium drive_key mismatch: "
                f"expected {drive_key!r}, got {got_drive!r}",
                rule_id="transcript.change-medium-mismatch")
        got_path = entry.data.get("path")
        expected_path = os.fspath(path) if path is not None else None
        if got_path != expected_path:
            raise TranscriptError(
                f"change_medium path mismatch: "
                f"expected {expected_path!r}, got {got_path!r}",
                rule_id="transcript.change-medium-path-mismatch")

    def _next_call(self, carrier):
        while self._index < len(self._entries):
            entry = self._entries[self._index]
            self._index += 1
            if entry.kind != "call":
                continue
            if entry.data.get("carrier") != carrier:
                raise TranscriptError(
                    f"expected {carrier} call at "
                    f"{entry.data.get('elapsed', '?')}s, got "
                    f"{entry.data.get('carrier', '?')!r}",
                    rule_id="transcript.call-mismatch")
            return entry
        raise TranscriptError(
            f"transcript exhausted before {carrier} call was "
            "reached",
            rule_id="transcript.call-exhausted")


class TranscriptError(StaticError):
    """A transcript file could not be read or replayed."""