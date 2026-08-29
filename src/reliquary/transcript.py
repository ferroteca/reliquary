# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Screen transcript capture and reconstruction.

This is an internal debugging and test-corpus tool, not a public
application surface (D98): there is no stability guarantee, no
``docs/spec/`` entry for it, and a change to the file format is just
housekeeping. The command-line invocation, though -- ``--record
<path>`` on ``run-script`` and ``run_script(record=)`` on the
session -- *is* a public surface, and lands on S1/S2 in the same
change as everything else here.

Capture wraps the **carrier seam**: the adapter session's
``text_screen()``, ``send_keys()``, ``screenshot()``,
``change_medium()``, and ``pointer_event()`` methods. Wrapping at
that seam is what makes capture work the same regardless of
backend. Reconstruction stands up a fake session at that same seam,
and the entire interpretation layer above it runs completely
unmodified.
"""

import hashlib
import json
import os
import time
from datetime import datetime, timezone

from .errors import PreflightError, StaticError

_DIGEST = "sha256"

#: Bumped whenever the encoding changes, so a transcript captured
#: before the change is refused with a clear name rather than just
#: failing its digest checks. There is no compatibility parsing
#: here, and no reader for an older format version (D98, and the
#: pre-1.0 rule): a stale capture just gets re-recorded.
_FORMAT_VERSION = "rlqt-2"


def _utc_now():
    return datetime.now(timezone.utc)


def _stamp(moment):
    """ISO-8601 UTC with milliseconds, mirroring events.py's spelling."""
    return (moment.strftime("%Y-%m-%dT%H:%M:%S")
            + f".{moment.microsecond // 1000:03d}Z")


def _canonical(rows, attributes):
    """The canonical form used for computing a digest: JSON of (text rows, attribute rows).

    Rows are strings; attribute rows are lists of ints, one per cell.
    Both together decide identity -- a cursor menu can move its
    selection using attributes alone, with the text unchanged.
    """
    return json.dumps([list(rows), attributes], sort_keys=True)


def pack_attributes(attributes):
    """Pack attribute rows into runs: ``[[count, token], ...]`` for each row.

    Storing one attribute value per cell made up seventy percent of
    the size of the first real capture: eighty tokens per row,
    twenty-five rows per keyframe, where a typical DOS row actually
    only has one to four distinct runs of attributes. The space
    saved is worth having, but the real reason this format was
    chosen is readability, the same reason deltas were chosen: a
    reviewer now reads "normal, then a highlight from column ten for
    fifteen cells" instead of eighty sevens in a row.

    A token is treated as opaque and only ever compared for
    equality, so this works with whatever vocabulary the carrier
    seam happens to use.
    """
    packed = []
    for row in attributes:
        runs = []
        for token in row:
            if runs and runs[-1][1] == token:
                runs[-1][0] += 1
            else:
                runs.append([1, token])
        packed.append(runs)
    return packed


def unpack_attributes(packed):
    """The rows a packed attribute grid stands for."""
    return [[token for count, token in runs for _ in range(count)]
            for runs in packed]


def compute_digest(rows, attributes):
    """Compute the SHA-256 digest of a screen's canonical representation.

    This costs only a few bytes per entry, and it is checked during
    reconstruction so a bug or a hand-edited fixture fails loudly
    instead of quietly producing a screen that never actually
    existed.
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


def script_identity(script_path):
    """What a capture is a capture *of*, as a set of header fields.

    A transcript is replayed by standing the same script back up
    over it, and the script file itself is the only thing that
    records which script that was. The digest fields cover the
    other half of the problem: if the script was edited after the
    capture was taken, a replay would diverge partway through, and
    "this capture was taken against a different version of
    freedos-install.rlqs" is a much better error than a keystroke
    mismatch eleven minutes into a replay.

    Returns an empty dict when there is no readable script file
    behind the run -- for example, a caller holding a parsed tree
    but no file path -- because a header field that is sometimes
    just a guess is worse than one that is sometimes missing
    entirely (P11).
    """
    if not script_path:
        return {}
    try:
        with open(script_path, "rb") as handle:
            content = handle.read()
    except OSError:
        return {}
    stem = os.path.splitext(os.path.basename(os.fspath(script_path)))[0]
    return {"script": stem,
            "script_digest": hashlib.new(_DIGEST, content).hexdigest()}


class _TranscriptWriter:

    def __init__(self, path, pace, script=None, script_digest=None,
                 command=None, timeout=None):
        self._path = os.fspath(path)
        self._file = None
        self._pace = pace
        self._script = script
        self._script_digest = script_digest
        #: The command an `exec` capture ran. A capture always states
        #: what its input was, whatever kind of run it recorded: a
        #: script by name and digest, or a command by its literal
        #: text -- which *is* the entire input, so there is nothing
        #: else to check a replay against.
        self._command = command
        #: The timeout the run was given. A wait that expires reaches
        #: its conclusion because of the timeout, so replaying the
        #: same capture under a different timeout would be asking it
        #: a different question.
        self._timeout = timeout
        self._written_header = False
        self._started = None
        self._last_wall = None
        self._stopped = False
        #: The frame that has not been written yet, held open so
        #: later reads of the same screen can be counted onto it. A
        #: frame's final read count is not known when the frame
        #: first arrives -- only once the screen changes again -- so
        #: writing it out immediately would throw that count away.
        self._pending = None

    def open(self, clock=time.monotonic, now=_utc_now):
        """Begin the transcript by writing its one header line."""
        self._file = open(self._path, "w", encoding="utf-8")
        self._started = clock()
        self._last_wall = now()
        header = {"format": _FORMAT_VERSION, "pace": self._pace,
                  "secret-recorded": False}
        if self._script is not None:
            header["script"] = self._script
        if self._script_digest is not None:
            header["script-sha256"] = self._script_digest
        if self._command is not None:
            header["command"] = self._command
        if self._timeout is not None:
            header["timeout"] = self._timeout
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
        """Record one screen reading, collapsing it onto the previous one if identical.

        A read that is identical to the frame still pending is
        **absorbed onto it** rather than dropped entirely: the
        frame's sample count is what tells "this screen held for two
        seconds across forty samples" apart from "it held for two
        seconds with nobody looking," and only the first of those
        actually says the guest was quiet (P11).

        Because of this, a frame is held open until the screen
        changes, a call interrupts it, or the transcript closes --
        its final count is not knowable any earlier than that. Its
        timestamps stay those of the read it was first seen on,
        which is when the screen actually appeared.
        """
        if self._stopped or self._file is None:
            return
        rows = list(rows)
        attributes = [list(row) for row in attributes]
        pending = self._pending
        if pending is not None and pending["rows"] == rows and \
                pending["attributes"] == attributes:
            pending["samples"] += samples
            # This also records *when* each read happened. The count
            # alone only shows that the guest was quiet; the actual
            # moments show at what cadence someone was reading, and a
            # reconstruction has to reproduce that too -- every
            # window-based measurement in the layer above operates on
            # wall-clock time, so answering a read at a moment nobody
            # actually read at would make it a different run.
            pending["absorbed"].append(round(clock() - self._started, 3))
            return
        self._flush_frame()
        self._pending = {
            "rows": rows,
            "attributes": attributes,
            "samples": samples,
            "absorbed": [],
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
        if pending["absorbed"]:
            entry["absorbed"] = pending["absorbed"]
        prev = getattr(self, "_last_frame", None)
        prev_attributes = getattr(self, "_last_attributes", None)
        if prev is None or prev_attributes != attributes:
            # Two things force writing a full frame here, and a
            # changed *row* is not one of them -- a changed row is
            # exactly what a delta is for.
            #
            # The first is a gap in sampling (a call, or this being
            # the very first frame): continuity cannot be assumed
            # across a gap, so the next entry has to restate the
            # whole screen.
            #
            # The second is changed attributes, which is exactly what
            # a delta cannot express: a delta only records row text,
            # while the digest covers rows *and* attributes. So a
            # selection bar moving under otherwise identical text
            # would be written as an empty row delta and then
            # rebuilt with the wrong attributes if this were not a
            # keyframe. A cursor menu can move by attribute alone,
            # with no text change at all.
            entry["keyframe"] = True
            entry["rows"] = rows
            entry["attributes"] = pack_attributes(attributes)
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
        # A call ends whatever frame it interrupted: that frame's
        # absorbed count is now final, and whatever comes next is a
        # new screen.
        self._flush_frame()
        entry = {
            "type": "call",
            "elapsed": round(clock() - self._started, 3),
            "wall": _stamp(now()),
            "carrier": carrier,
        }
        if fields:
            entry.update(fields)
        # A call creates a sampling gap, so the next frame recorded
        # must be a keyframe.
        self._last_frame = None
        self._last_attributes = None
        self._write_json(entry)

    def write_gone(self, reason, clock=time.monotonic, now=_utc_now):
        """Record the carrier going away -- the machine is no longer there.

        This is the one entry the seam cannot write for itself:
        identity gets verified while a session is being opened, so a
        machine that has powered itself off refuses the session
        *before* the recording wrapper even exists to see it happen.
        A capture that lost this moment could not replay a ``wait
        machine=stopped``, which is exactly how a DOS install script
        ends.
        """
        if self._stopped or self._file is None:
            return
        self._flush_frame()
        entry = {
            "type": "vm-gone",
            "elapsed": round(clock() - self._started, 3),
            "wall": _stamp(now()),
            "reason": reason,
        }
        # Nothing carries over across a machine stopping: whatever
        # gets read next is a screen this transcript has never seen
        # before.
        self._last_frame = None
        self._last_attributes = None
        self._write_json(entry)

    def write_outcome(self, result, clock=time.monotonic, now=_utc_now,
                      **fields):
        """Record what the run concluded -- the part the carrier seam itself cannot show.

        At the carrier seam, a run that returned the right answer
        and one that returned the wrong text look identical: the
        same keys go out, the same screens come back, and *which
        rows counted as the answer* is decided above the seam, not
        at it. A capture of a run that failed tells the same story
        -- the failure is a conclusion drawn above the seam, not
        something the carrier reported.

        So the driver records its conclusion once, as the last
        entry, and a replay is checked against it. ``result`` is
        either ``ok`` or ``failed``; everything else is up to the
        driver, since what counts as "the conclusion" differs by
        what was run -- output rows for a command, a phase name for
        a script, a rule id for either one when it failed.
        """
        if self._stopped or self._file is None:
            return
        self._flush_frame()
        entry = {
            "type": "outcome",
            "elapsed": round(clock() - self._started, 3),
            "wall": _stamp(now()),
            "result": result,
        }
        entry.update(fields)
        self._write_json(entry)

    def stop(self, reason, clock=time.monotonic, now=_utc_now):
        """End recording mid-run because a bound secret value reached the guest."""
        if self._stopped or self._file is None:
            return
        # Everything captured before the secret is kept intact,
        # counts and all -- it is only what comes after that stops
        # being recorded.
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

    Sits at the carrier seam -- between the adapter session and
    ``DisplayConsole`` -- so the entire interpretation layer above
    it runs completely unmodified. Consecutive identical frames get
    collapsed together, with their sample counts combined; a
    keyframe is written after every sampling gap.
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

    def text_screen(self, font_banks=()):
        """Return the screen, and offer every read to the transcript writer.

        **Every** read gets offered to the writer, including one
        identical to the last: collapsing identical reads together
        is the writer's job, not this method's, because a frame's
        absorbed sample count is only knowable once the screen
        actually changes. A read dropped here would be a sample the
        transcript could never count at all. A keyframe written
        after every sampling gap (a call) limits how much damage a
        missing entry can do. ``font_banks`` (F61) passes straight
        through unchanged -- the recording only ever carries rows
        and attributes, never which fonts produced them.
        """
        rows, attributes = self._inner.text_screen(font_banks)
        # Copy the mutable lists the adapter hands back, so what the
        # transcript holds cannot be edited from underneath it.
        rows = list(rows)
        attributes = [list(row) for row in attributes]
        writer = self._writer
        if writer is not None and not writer.stopped:
            writer.write_frame(rows, attributes)
        return rows, attributes

    def framebuffer(self):
        """Pass the framebuffer read through unchanged; the transcript holds no pixels.

        A transcript only stores a *text-screen* format -- rows and
        attribute tokens (planning/design/screen-transcripts.md) --
        so a framebuffer read has nothing here it could record.
        Recording a run that watches a landmark still works, but
        produces a capture that cannot reconstruct that particular
        wait; :meth:`ReplaySession.framebuffer` says that plainly
        when replay is attempted, instead of making up a screen
        (P11).
        """
        return self._inner.framebuffer()

    def pointer_event(self, x, y, buttons):
        """Pass the pointer event through unchanged; the transcript holds no pixels.

        Same reasoning as :meth:`framebuffer`: a `click`'s landmark
        search already made this capture unreplayable, so recording
        the pointer event that followed the search would just
        promise a reconstruction it cannot actually deliver (F66).
        """
        self._inner.pointer_event(x, y, buttons)

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
        self.script = None
        self.script_digest = None
        self.command = None
        self.timeout = None
        #: What the recorded run concluded, or ``None`` when the run
        #: never reached a conclusion -- a capture cut short by a
        #: secret reaching the guest, or one whose driver crashed. A
        #: fixture that wants to assert a conclusion can, and a
        #: reader gets an honest ``None`` when there is not one.
        self.outcome = None
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
        self.script = header.get("script")
        self.script_digest = header.get("script-sha256")
        self.command = header.get("command")
        self.timeout = header.get("timeout")
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
                    packed = entry_data.get("attributes")
                    reconstructed_rows = rows
                    reconstructed_attrs = (
                        None if packed is None else unpack_attributes(packed))
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
            elif kind == "outcome":
                self.outcome = entry_data
            entries.append(_TranscriptEntry(entry_data))
        self._entries = entries
        return entries


class ReplaySession:
    """A fake adapter session that replays from a transcript.

    Stands at the carrier seam -- the same place the recording
    wrapped around -- so the interpretation layer above it runs
    completely unmodified. A request the transcript does not cover
    produces an error naming exactly what was asked for (P11): never
    an improvised answer, and never an empty one.
    """

    backend = "transcript"

    def __init__(self, entries, advance=None):
        self._entries = entries
        self._index = 0
        #: Called with each consumed entry's recorded ``elapsed``
        #: value. Reconstruction advances time based on ``elapsed``,
        #: not on the recorded wall-clock time, which is kept only
        #: as provenance. A reader whose own clock ticks based on
        #: its own sleeps would place frames 200ms apart that the
        #: guest actually drew a third of a second apart, and the
        #: stability measure -- which deliberately judges over
        #: wall-clock windows so that polling more densely can never
        #: change its verdict -- would then reach a different
        #: verdict than it did during the real run.
        self._advance = advance
        # The current reconstructed screen.
        self._rows = None
        self._attributes = None
        #: How many more reads the current frame can still answer
        #: before the replay has to advance to the next entry. A
        #: capture collapses a screen that was read repeatedly into
        #: one entry carrying the count of reads it absorbed, so a
        #: replay that advanced to a new entry on every read would
        #: run out of transcript long before the run ran out of
        #: statements.
        self._remaining = 0
        #: The moments the currently standing frame was read again
        #: at, with one taken off the front for each repeat read.
        self._absorbed = []

    def native(self):
        raise TranscriptError(
            "a transcript has no native backend session",
            rule_id="transcript.no-native-session")

    def _at(self, data):
        """Put the reader's clock where the recording was, if it has one."""
        elapsed = data.get("elapsed")
        if self._advance is not None and elapsed is not None:
            self._advance(elapsed)

    def _pace_absorbed(self, data):
        """The moments a held frame's absorbed reads were originally taken at.

        A collapsed frame stands in for every read that happened
        between it and whatever entry came after it, and the
        transcript file records exactly when each of those reads
        happened. Answering all of them at the frame's own single
        instant would bunch all of a screen's samples right at its
        start and leave a gap right before the next entry -- and
        every window-based measurement above this layer would read
        that as a sampling cadence the run never actually had.
        """
        self._absorbed = list(data.get("absorbed") or ())

    def remaining_calls(self):
        """Count the carrier calls the capture holds that the replay never actually made.

        A run that ends early does not raise anything -- it just
        stops asking, and an unread transcript stays silent about
        that -- so "the replay finished without error" and "the
        replay did everything the capture recorded" are two
        different claims. This checks the second one.
        """
        return sum(1 for entry in self._entries[self._index:]
                   if entry.kind == "call")

    def text_screen(self, font_banks=()):
        # A replay reproduces the captured rows no matter what a live
        # font prefix would currently be -- the recognizer already
        # ran once, when the capture was originally taken.
        if self._remaining > 0:
            # The current frame is still standing: it was read this
            # many more times when it was originally captured, at the
            # moments the transcript recorded.
            self._remaining -= 1
            if self._absorbed and self._advance is not None:
                self._advance(self._absorbed.pop(0))
            return (list(self._rows),
                    [list(row) for row in self._attributes])
        while self._index < len(self._entries):
            entry = self._entries[self._index]
            if entry.kind == "vm-gone":
                # Reproduced as the same refusal the adapter made at
                # capture time, not as a transcript error: the run
                # above is meant to encounter exactly what it
                # encountered when the capture was taken, and a
                # `wait machine=stopped` is answered by exactly this
                # refusal.
                self._index += 1
                raise PreflightError(
                    entry.data.get("reason")
                    or "the recorded VM is not reachable",
                    rule_id="machine.vm-unreachable")
            if entry.kind == "call":
                # The capture had already sent something at this
                # point, but the replay tried to read the screen
                # instead. Silently stepping over the call is exactly
                # what would turn a one-read difference here into a
                # keystroke mismatch minutes later, against a screen
                # neither run was actually looking at -- so this is
                # where the real divergence gets reported.
                raise TranscriptError(
                    f"the capture's next event is a "
                    f"{entry.data.get('carrier', '?')} call at "
                    f"{entry.data.get('elapsed', '?')}s and the run read "
                    "the screen instead",
                    rule_id="transcript.read-before-call")
            if entry.kind != "frame":
                self._index += 1
                continue
            data = entry.data
            self._index += 1
            self._at(data)
            self._remaining = max(0, int(data.get("samples", 1)) - 1)
            self._pace_absorbed(data)
            if data.get("keyframe"):
                self._rows = data["rows"]
                packed = data.get("attributes")
                self._attributes = (
                    None if packed is None else unpack_attributes(packed))
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

    def framebuffer(self):
        """Refuse: a transcript records screens, never pixels.

        The format only holds character rows and attribute tokens,
        which no landmark can be matched against. A reconstruction
        that made up a framebuffer would report a match or a miss
        that the recorded run never actually made, so instead the
        replay states exactly what was asked for and stops there
        (P11).
        """
        raise TranscriptError(
            "a transcript records text screens and holds no "
            "framebuffer; a landmark condition cannot be replayed",
            rule_id="transcript.no-framebuffer")

    def pointer_event(self, x, y, buttons):
        """Refuse: replaying `click`'s landmark search already failed first.

        A `click`'s landmark search reads :meth:`framebuffer`, which
        a transcript refuses by name before the pointer event
        delivery here would ever be reached. This method exists so a
        caller that somehow gets past that earlier refusal is told
        plainly what it asked for, instead of hitting an
        ``AttributeError`` (F66).
        """
        raise TranscriptError(
            "a transcript records text screens and holds no "
            "framebuffer; a pointer event cannot be replayed",
            rule_id="transcript.no-framebuffer")

    def screenshot(self, path):
        """Check the image's *filename*, which is the part the script actually chose.

        The directory in a captured path belongs to the machine that
        recorded the capture, and a reconstruction by definition
        runs somewhere else -- checking the whole path would make
        every replay of every capture fail. What the script actually
        decided is the filename: `screenshot installed` from the
        script text, or `failure-step-31` from a failure report.
        """
        entry = self._next_call("screenshot")
        expected_path = os.fspath(path)
        got = entry.data.get("path")
        if got is not None and \
                os.path.basename(got) != os.path.basename(expected_path):
            raise TranscriptError(
                f"screenshot name mismatch at "
                f"{entry.data.get('elapsed', '?')}s: "
                f"expected {os.path.basename(expected_path)!r}, got "
                f"{os.path.basename(got)!r}",
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
            self._at(entry.data)
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