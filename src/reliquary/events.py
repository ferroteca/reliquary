# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The run event stream: live output only, never written to a file.

A run produces one official stream of events (docs/spec/script-spec.md,
"The run event stream"): JSON Lines, one event per line, each one
carrying a sequence number, a timestamp, elapsed time, and a kind. This
is **live output only** — it's rendered to the run's display and
handed back to whoever started the run, but nothing about it is ever
written to disk (D36). The pretty and plain displays just render this
same stream, so nothing shown on screen says anything the stream
itself doesn't already carry.

The same transfer and verification event kinds are emitted everywhere
media moves: inside a run they travel on the run's stream, and the
standalone ``fetch-media`` command renders the identical kinds on its
own.

The stream is a supported interface for other programs to consume:
starting from version 1.0, new event kinds and fields can be added,
but nothing already there changes meaning. Consumers should ignore any
kind or field they don't recognize.
"""

import dataclasses
import json
import sys
import time
from datetime import datetime, timezone


# -- the event kinds -----------------------------------------
#
# Dotted names, all in one namespace. New kinds can be added in any
# release; an existing kind never changes what it means.

RUN_START = "run.start"
RUN_PREFLIGHT = "run.preflight"
RUN_END = "run.end"
PROPERTY_BOUND = "property.bound"
PHASE_START = "phase.start"
PHASE_END = "phase.end"
TRANSITION = "transition"
OBSERVATION_ARM = "observation.arm"
OBSERVATION_MATCH = "observation.match"
OBSERVATION_TIMEOUT = "observation.timeout"
HANDLER_FIRE = "handler.fire"
ACTION_START = "action.start"
ACTION_END = "action.end"
TRANSFER_START = "transfer.start"
TRANSFER_PROGRESS = "transfer.progress"
TRANSFER_END = "transfer.end"
VERIFY_START = "verify.start"
VERIFY_END = "verify.end"
#: Reports the screen-sampling cadence the quiescence guard measured
#: and the stability window that cadence allows. Emitted once, the
#: first time a run has these numbers. This is the one thing about the
#: guard a reader can't work out on their own: the script author
#: writes `stability=`, but whether the host can actually keep up with
#: it is only discovered at run time. Without this event, a guard that
#: silently gave up would look no different from one that succeeded.
GUARD_CADENCE = "guard.cadence"
#: Reports a scoped machine-state change taking effect, and being
#: undone again. These two events are the only record that a `with`
#: block happened: the underlying change is an ordinary
#: `insert`/`eject`/boot action and is reported as one either way, but
#: whether it was inside a `with` block, and what state it was
#: restored to on exit, is recorded only here (P5).
SCOPE_ENTER = "scope.enter"
SCOPE_RESTORE = "scope.restore"
FAILURE = "failure"

#: Every event kind defined above, so a test can check that what's
#: declared here matches what actually gets emitted. A kind that's
#: designed but not implemented yet is called out only in the spec
#: document, not listed here — this tuple is a claim that the stream
#: really does carry each of these kinds.
KINDS = (
    RUN_START, RUN_PREFLIGHT, RUN_END, PROPERTY_BOUND,
    PHASE_START, PHASE_END, TRANSITION,
    OBSERVATION_ARM, OBSERVATION_MATCH, OBSERVATION_TIMEOUT,
    HANDLER_FIRE, ACTION_START, ACTION_END,
    TRANSFER_START, TRANSFER_PROGRESS, TRANSFER_END,
    VERIFY_START, VERIFY_END, GUARD_CADENCE,
    SCOPE_ENTER, SCOPE_RESTORE, FAILURE,
)

_TIMESTAMP = "%Y-%m-%dT%H:%M:%S"


def _utc_now():
    return datetime.now(timezone.utc)


def _stamp(moment):
    """Format ``moment`` as ISO-8601 UTC with milliseconds.

    This is the timestamp format the stream uses for every event.
    """
    return (moment.strftime(_TIMESTAMP)
            + f".{moment.microsecond // 1000:03d}Z")


@dataclasses.dataclass(frozen=True)
class Event:
    """One event in a run's stream.

    ``fields`` holds the data specific to this event's kind.
    :meth:`as_dict` merges those fields alongside the envelope fields
    (seq, time, elapsed, kind) into the flat JSON Lines shape a
    consumer actually reads.
    """

    seq: int
    time: str
    elapsed: float
    kind: str
    fields: dict = dataclasses.field(default_factory=dict)

    def as_dict(self):
        """Return the flat dict this event serializes to as JSON."""
        document = {"seq": self.seq, "time": self.time,
                    "elapsed": round(self.elapsed, 3), "kind": self.kind}
        document.update(self.fields)
        return document

    def as_json(self):
        """Return this event as one JSON Lines record, no newline."""
        return json.dumps(self.as_dict(), default=str)


class EventStream:
    """The live event stream for one run, and the events it hands back.

    Every event is sent to ``sink`` as it happens (the live half) and
    also saved up for the caller to retrieve later (the returned
    half). ``redact`` runs on every string field before an event is
    recorded, so a bound secret value can never appear in either half.

    Ticks are live-only and never saved: a renderer that shows
    "elapsed / limit" while an observation is waiting gets them, but
    they never appear in the saved list of events, keeping it free of
    that repeating heartbeat noise.
    """

    def __init__(self, sink=None, *, redact=None, clock=time.monotonic,
                 now=_utc_now):
        self._sink = sink
        self._redact = redact
        self._clock = clock
        self._now = now
        self._started = clock()
        self._seq = 0
        self._events = []

    @property
    def events(self):
        """Return every event recorded so far, as flat dicts, in order."""
        return tuple(event.as_dict() for event in self._events)

    def emit(self, kind, **fields):
        """Record one event, send it to the renderer, and return it."""
        self._seq += 1
        event = Event(self._seq, _stamp(self._now()),
                      self._clock() - self._started, kind,
                      self._clean(fields))
        self._events.append(event)
        if self._sink is not None:
            self._sink.event(event)
        return event

    def tick(self, **fields):
        """Update the renderer's live display; record nothing."""
        if self._sink is not None:
            self._sink.tick(**fields)

    def clear(self):
        """Tell the renderer to remove any in-place live display."""
        if self._sink is not None:
            self._sink.clear()

    def close(self):
        """Release the renderer. The recorded events are kept."""
        if self._sink is not None:
            self._sink.close()

    def _clean(self, fields):
        """Drop fields whose value is None, and redact every string."""
        cleaned = {}
        for name, value in fields.items():
            if value is None:
                continue
            cleaned[name] = self._scrub(value)
        return cleaned

    def _scrub(self, value):
        if self._redact is None:
            return value
        if isinstance(value, str):
            return self._redact(value)
        if isinstance(value, (list, tuple)):
            return type(value)(self._scrub(item) for item in value)
        if isinstance(value, dict):
            return {key: self._scrub(item) for key, item in value.items()}
        return value


def note(events, kind, message, **fields):
    """Emit ``kind`` on ``events``, or print ``message`` to stderr if
    ``events`` is None.

    Media can move both inside a run, which has an event stream to
    write to, and outside one — for example ``create-machine``'s
    implicit fetch of media, which has no stream. This function
    handles both cases correctly without needing to add a
    ``--progress`` flag to every machine command that might trigger a
    media fetch.
    """
    if events is not None:
        events.emit(kind, message=message, **fields)
        return
    print(f"rlq: {message}", file=sys.stderr)
