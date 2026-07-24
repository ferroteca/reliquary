# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""The run event stream — live output, never a file.

A run emits one normative event stream (planning/design/script-spec.md,
"The run event stream"): JSON Lines, each event carrying a sequence
number, timestamp, elapsed time, and kind. It is **live output**
rendered to the run's driver and returned to whoever started the run;
nothing is written to disk (D36). The pretty and plain displays are
*renderers* of this stream, so no surface reports anything the stream
does not carry.

The same transfer and verification kinds are emitted wherever media
moves — inside a run they ride the run's stream, and standalone
``fetch-media`` renders them the same way.

The stream is a contracted machine surface: from 1.0 it grows
additively only, and consumers must ignore unknown kinds and fields.
"""

import dataclasses
import json
import sys
import time
from datetime import datetime, timezone


# -- the kind vocabulary -----------------------------------------
#
# Dotted names in one namespace. New kinds may appear in any
# release; an existing kind never changes meaning.

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
SCREEN_READ = "screen.read"
FAILURE = "failure"

#: The event kinds carrying no ``line``, for renderers that cite one.
_TIMESTAMP = "%Y-%m-%dT%H:%M:%S"


def _utc_now():
    return datetime.now(timezone.utc)


def _stamp(moment):
    """ISO-8601 UTC with milliseconds, the stream's time spelling."""
    return (moment.strftime(_TIMESTAMP)
            + f".{moment.microsecond // 1000:03d}Z")


@dataclasses.dataclass(frozen=True)
class Event:
    """One event of a run's stream.

    ``fields`` are the kind's own; :meth:`as_dict` flattens them
    beside the envelope, which is the JSON Lines shape a consumer
    reads.
    """

    seq: int
    time: str
    elapsed: float
    kind: str
    fields: dict = dataclasses.field(default_factory=dict)

    def as_dict(self):
        """The flat JSON-shaped mapping this event serializes as."""
        document = {"seq": self.seq, "time": self.time,
                    "elapsed": round(self.elapsed, 3), "kind": self.kind}
        document.update(self.fields)
        return document

    def as_json(self):
        """One JSON Lines record — no newline."""
        return json.dumps(self.as_dict(), default=str)


class EventStream:
    """The live stream of one run, and the output it returns.

    Events are handed to ``sink`` as they happen (the live half) and
    accumulated for the caller (the returned half). ``redact`` is
    applied to every string field before an event is recorded, so a
    bound secret can never reach either half.

    Ticks are live-only: a renderer showing "elapsed / limit" while an
    observation waits gets them, and the recorded stream stays free of
    heartbeat noise.
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
        """Every event so far, as flat dicts, in order."""
        return tuple(event.as_dict() for event in self._events)

    def emit(self, kind, **fields):
        """Record and render one event; return it."""
        self._seq += 1
        event = Event(self._seq, _stamp(self._now()),
                      self._clock() - self._started, kind,
                      self._clean(fields))
        self._events.append(event)
        if self._sink is not None:
            self._sink.event(event)
        return event

    def tick(self, **fields):
        """Advance a renderer's live display; record nothing."""
        if self._sink is not None:
            self._sink.tick(**fields)

    def clear(self):
        """Ask the renderer to retire any in-place live display."""
        if self._sink is not None:
            self._sink.clear()

    def close(self):
        """Release the renderer; the stream itself keeps its events."""
        if self._sink is not None:
            self._sink.close()

    def _clean(self, fields):
        """Drop empty optional fields and redact every string."""
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
    """Emit ``kind`` on ``events``, or print the human line to stderr.

    Media movement happens inside a run (which has a stream) and
    outside one (``create-machine``'s implicit fetch, which does not).
    This keeps both honest without giving every machine command a
    ``--progress`` flag it does not have.
    """
    if events is not None:
        events.emit(kind, message=message, **fields)
        return
    print(f"rlq: {message}", file=sys.stderr)
