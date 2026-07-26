# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Live renderings of the run event stream.

``--progress (auto | pretty | plain | jsonl)`` selects one
(docs/spec/cli.md, "Running scripts"); the API twins take the
same ``progress=`` value under parity. Every renderer reads the one
:mod:`reliquary.events` stream, so none can report what the stream
does not carry.

The output discipline (docs/spec/cli.md, "Output discipline"):
the human modes render **everything** to stderr and leave stdout
empty — the outcome travels by exit code. ``jsonl`` is the named
exception: its stdout events *are* the result, the last line being
the terminal event, with diagnostics still on stderr.

``plain`` and ``jsonl`` are noninteractive by construction: nothing
prompts, so a missing input is a PREFLIGHT ERROR before the machine
starts rather than a program hanging on a hidden question.
"""

import os
import sys

from . import events as _events

MODES = ("auto", "pretty", "plain", "jsonl")

#: Modes that never prompt — a program can never hang on a question.
NONINTERACTIVE = frozenset({"plain", "jsonl"})

_HEARTBEAT_INTERVAL = 5.0
_SPINNER = "|/-\\"
_BAR_WIDTH = 20


def resolve_mode(progress, *, stream=None):
    """Resolve ``auto`` against the terminal; validate the rest.

    ``auto`` is the BuildKit vocabulary's default and resolves by
    whether the *rendering* stream is a tty, which for the human modes
    is stderr.
    """
    if progress is None:
        progress = "auto"
    if progress not in MODES:
        raise ValueError(
            f"--progress must be one of {', '.join(MODES)}, "
            f"got: {progress!r}")
    if progress != "auto":
        return progress
    handle = stream if stream is not None else sys.stderr
    return "pretty" if _isatty(handle) else "plain"


def interactive(progress):
    """Whether ``progress`` permits prompting at all."""
    return resolve_mode(progress) not in NONINTERACTIVE


def renderer(progress, *, out=None, err=None):
    """Build the renderer ``progress`` names."""
    mode = resolve_mode(progress, stream=err)
    if mode == "jsonl":
        return JsonlRenderer(out if out is not None else sys.stdout)
    stream = err if err is not None else sys.stderr
    if mode == "pretty":
        return PrettyRenderer(stream)
    return PlainRenderer(stream)


def stream_for(progress, *, redact=None, out=None, err=None):
    """An :class:`~reliquary.events.EventStream` rendering as asked."""
    return _events.EventStream(
        renderer(progress, out=out, err=err), redact=redact)


def _isatty(handle):
    try:
        return bool(handle.isatty())
    except (AttributeError, ValueError):
        return False


def _color_ok(handle):
    """ANSI is emitted per stream, only to a tty, and never under
    ``NO_COLOR``."""
    return _isatty(handle) and not os.environ.get("NO_COLOR")


def _seconds(value):
    return f"{value:0.0f}s"


def _bytes(count):
    for unit in ("B", "KB", "MB", "GB"):
        if count < 1024 or unit == "GB":
            return f"{count:0.0f}{unit}" if unit == "B" \
                else f"{count:0.1f}{unit}"
        count /= 1024.0
    return f"{count:0.1f}GB"


def describe(event):
    """One human line for an event, or ``None`` to render nothing.

    Renderers may omit what the stream carries; they may never add to
    it.
    """
    kind = event.kind
    fields = event.fields
    line = fields.get("line")
    prefix = f"line {line}: " if line else ""
    if kind == _events.RUN_START:
        return (f"run {fields.get('script') or '<script>'} "
                f"on machine {fields.get('machine')}")
    if kind == _events.RUN_PREFLIGHT:
        planes = ", ".join(fields.get("control-planes") or ()) or "-"
        return (f"backend {fields.get('backend')}; "
                f"control planes: {planes}")
    if kind == _events.PROPERTY_BOUND:
        return f"property {fields.get('key')}: {fields.get('source')}"
    if kind == _events.PHASE_START:
        return f"phase: {fields.get('phase')}"
    if kind == _events.TRANSITION:
        target = fields.get("target")
        return prefix + (f"goto {target}" if target else "finish")
    if kind == _events.OBSERVATION_ARM:
        return prefix + f"wait {fields.get('description')}"
    if kind == _events.OBSERVATION_MATCH:
        row = fields.get("row")
        seen = f": {row!r}" if row else ""
        return (f"matched {fields.get('description')} after "
                f"{_seconds(fields.get('elapsed', 0.0))}{seen}")
    if kind == _events.OBSERVATION_TIMEOUT:
        return prefix + f"timed out waiting for {fields.get('description')}"
    if kind == _events.HANDLER_FIRE:
        return prefix + (f"{fields.get('keyword', 'on')} "
                         f"{fields.get('description')}")
    if kind == _events.ACTION_START:
        detail = fields.get("detail")
        return prefix + fields.get("verb", "") + (f" {detail}" if detail
                                                  else "")
    if kind in (_events.TRANSFER_START, _events.VERIFY_START):
        return fields.get("message")
    if kind == _events.TRANSFER_END:
        error = fields.get("error")
        if error:
            return f"{fields.get('source')} failed: {error}"
        moved = fields.get("transferred")
        size = f" ({_bytes(moved)})" if moved else ""
        return (f"{fields.get('operation', 'transfer')}ed "
                f"{fields.get('name')}{size} in "
                f"{_seconds(fields.get('elapsed', 0.0))}")
    if kind == _events.VERIFY_END:
        return (f"verified {fields.get('name')} in "
                f"{_seconds(fields.get('elapsed', 0.0))}")
    if kind == _events.TRANSFER_PROGRESS:
        total = fields.get("total")
        moved = fields.get("transferred", 0)
        if total:
            return (f"{fields.get('name')}: {_bytes(moved)} / "
                    f"{_bytes(total)}")
        return f"{fields.get('name')}: {_bytes(moved)}"
    if kind == _events.SCREEN_READ:
        return None
    if kind == _events.FAILURE:
        return _failure_report(fields)
    if kind == _events.RUN_END:
        return _terminal_report(fields)
    return None


def _failure_report(fields):
    """The failure report: what was pending, which clock, what to try."""
    lines = [f"FAILED: {fields.get('error')}"]
    for label, key in (("pending", "pending"),
                       ("clock", "clock"),
                       ("scope", "scope"),
                       ("nearest miss", "nearest-miss"),
                       ("screenshot", "screenshot")):
        value = fields.get(key)
        if value:
            lines.append(f"  {label}: {value}")
    route = fields.get("route")
    if route:
        lines.append("  route: " + " -> ".join(route))
    revisits = fields.get("revisits")
    if revisits:
        lines.append("  revisited: " + ", ".join(
            f"{name} x{count}" for name, count in sorted(revisits.items())))
    suggestion = fields.get("next-command")
    if suggestion:
        lines.append(f"  try next: {suggestion}")
    return "\n".join(lines)


def _terminal_report(fields):
    outcome = fields.get("outcome", "ok")
    detail = (f"; script phase {fields.get('final-phase')}, "
              f"machine {fields.get('machine-phase')}")
    if outcome == "ok":
        return "run complete" + detail
    error = fields.get("error")
    return (f"run {outcome}" + detail
            + (f"\n{error}" if error and outcome != "run-failure" else ""))


class _HumanRenderer:
    """Shared stderr rendering: one line per event, plus heartbeats."""

    color = False

    def __init__(self, stream):
        self.stream = stream
        self._last_heartbeat = None

    def event(self, event):
        text = describe(event)
        if text is None:
            return
        self.clear()
        self._write(self._paint(event, text) + "\n")
        self._last_heartbeat = None

    def tick(self, **fields):
        raise NotImplementedError

    def clear(self):
        return

    def close(self):
        self.clear()

    def _write(self, text):
        self.stream.write(text)
        self.stream.flush()

    def _paint(self, event, text):
        if not self.color:
            return text
        if event.kind == _events.FAILURE:
            return f"\033[31m{text}\033[0m"
        if event.kind == _events.RUN_END:
            ok = event.fields.get("outcome") == "ok"
            return f"\033[{32 if ok else 31}m{text}\033[0m"
        return text

    @staticmethod
    def _line(fields):
        """The 'elapsed / limit' pair a tick shows — never a bar.

        Phases and observations have no honest denominator of
        *progress*, only of time, so they are rendered as the two
        numbers rather than as a filled bar.
        """
        phase = fields.get("phase") or "-"
        step = fields.get("step")
        elapsed = fields.get("elapsed", 0.0)
        limit = fields.get("limit")
        where = f"[{phase}]" + (f" step {step}" if step else "")
        bound = f" / {_seconds(limit)}" if limit else ""
        return (f"{where} {fields.get('description', 'waiting')}  "
                f"{_seconds(elapsed)}{bound}")


class PlainRenderer(_HumanRenderer):
    """A redirected log's rendering: no ANSI, a periodic heartbeat."""

    def __init__(self, stream, *, interval=_HEARTBEAT_INTERVAL):
        super().__init__(stream)
        self._interval = interval

    def tick(self, **fields):
        now = fields.get("elapsed", 0.0)
        if (self._last_heartbeat is not None
                and now - self._last_heartbeat < self._interval):
            return
        self._last_heartbeat = now
        self._write(self._line(fields) + "\n")


class PrettyRenderer(_HumanRenderer):
    """An attached terminal's rendering: an in-place live line."""

    def __init__(self, stream):
        super().__init__(stream)
        self.color = _color_ok(stream)
        self._active = False
        self._tick = 0

    def tick(self, **fields):
        spin = _SPINNER[self._tick % len(_SPINNER)]
        self._tick += 1
        text = f"{spin} {self._line(fields)}"
        if self.color:
            text = f"\033[36m{text}\033[0m"
        self._write(f"\r\x1b[K{text}")
        self._active = True

    def clear(self):
        if not self._active:
            return
        self._write("\r\x1b[K")
        self._active = False
        self._tick = 0


class JsonlRenderer:
    """The programmatic rendering: the event stream on stdout, alone."""

    def __init__(self, stream):
        self.stream = stream

    def event(self, event):
        self.stream.write(event.as_json() + "\n")
        self.stream.flush()

    def tick(self, **fields):
        # A tick is a display concern; the stream carries only events.
        return

    def clear(self):
        return

    def close(self):
        return
