# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Ways of showing the run event stream to a person or a program.

``--progress`` picks one of ``auto``, ``pretty``, ``plain``, or
``jsonl`` (docs/spec/cli.md, "Running scripts"); the equivalent API
functions take the same values through their own ``progress=``
argument. Every renderer reads events from the single
:mod:`reliquary.events` stream, so none of them can show anything the
stream doesn't actually carry.

Per the output rules in docs/spec/cli.md ("Output discipline"), the
two human-facing modes (``pretty`` and ``plain``) write everything to
stderr and leave stdout empty — the caller finds out whether the run
succeeded from the exit code, not from stdout. ``jsonl`` is the one
exception: its events on stdout *are* the result, with the last line
being the terminal event, while diagnostics still go to stderr.

``plain`` and ``jsonl`` never prompt the user for input, by design:
if something needed were never supplied, that's a PREFLIGHT ERROR
raised before the machine even starts, rather than the program
silently hanging while it waits on a question nobody can see.
"""

import os
import sys

from . import events as _events
from .errors import StaticError

MODES = ("auto", "pretty", "plain", "jsonl")

#: Modes that never prompt the user, so the program can't hang waiting
#: on a question nobody can see.
NONINTERACTIVE = frozenset({"plain", "jsonl"})

_HEARTBEAT_INTERVAL = 5.0
_SPINNER = "|/-\\"
_BAR_WIDTH = 20


def resolve_mode(progress, *, stream=None):
    """Turn ``auto`` into ``pretty`` or ``plain``; validate anything else.

    ``progress`` defaults to ``auto`` (the same default name BuildKit
    uses) and picks ``pretty`` or ``plain`` by checking whether the
    stream being rendered to — stderr, for the human modes — is
    connected to a terminal.
    """
    if progress is None:
        progress = "auto"
    if progress not in MODES:
        raise StaticError(
            f"--progress must be one of {', '.join(MODES)}, "
            f"got: {progress!r}", rule_id="progress.unknown-mode")
    if progress != "auto":
        return progress
    handle = stream if stream is not None else sys.stderr
    return "pretty" if _isatty(handle) else "plain"


def interactive(progress):
    """Return whether ``progress`` allows prompting the user at all."""
    return resolve_mode(progress) not in NONINTERACTIVE


def renderer(progress, *, out=None, err=None):
    """Build the renderer object for the ``progress`` mode named."""
    mode = resolve_mode(progress, stream=err)
    if mode == "jsonl":
        return JsonlRenderer(out if out is not None else sys.stdout)
    stream = err if err is not None else sys.stderr
    if mode == "pretty":
        return PrettyRenderer(stream)
    return PlainRenderer(stream)


def stream_for(progress, *, redact=None, out=None, err=None):
    """Build an :class:`~reliquary.events.EventStream` in the mode asked for."""
    return _events.EventStream(
        renderer(progress, out=out, err=err), redact=redact)


def _isatty(handle):
    try:
        return bool(handle.isatty())
    except (AttributeError, ValueError):
        return False


def _color_ok(handle):
    """Return whether to emit ANSI color codes to ``handle``.

    Color is decided separately for each stream: only when that
    stream is a terminal, and never when ``NO_COLOR`` is set.
    """
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
    """Return one line of human-readable text for ``event``, or None.

    A renderer is allowed to leave out some of what the stream
    carries, but it must never show something the stream doesn't
    actually carry.
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
        # A text condition is matched by a screen row, and names that
        # row; a landmark condition is matched by a variant instead,
        # which is what a script author needs to know when several
        # renderings of the same landmark are in play (F65).
        row = fields.get("row")
        variant = fields.get("variant")
        seen = f": {row!r}" if row else f": {variant}" if variant else ""
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
    if kind == _events.SCOPE_ENTER:
        return prefix + (f"with {fields.get('head')} "
                         f"{fields.get('detail')}")
    if kind == _events.SCOPE_RESTORE:
        error = fields.get("error")
        target = fields.get("target")
        if error:
            return f"could not restore {target}: {error}"
        return f"restored {target} to {fields.get('detail')}"
    if kind == _events.GUARD_CADENCE:
        return _guard_report(fields)
    if kind == _events.FAILURE:
        return _failure_report(fields)
    if kind == _events.RUN_END:
        return _terminal_report(fields)
    return None


def _guard_report(fields):
    """Return one line naming the cadence measured and what it bought.

    This is stated explicitly because the alternative is silence: a
    run whose quiescence guard gave up looks exactly like one whose
    guard succeeded, and the script author who wrote `stability=` has
    no other way to find out the host couldn't actually honor it.
    """
    cadence = fields.get("cadence")
    window = fields.get("window")
    reading = "interpreted" if fields.get("recognized") else "scraped"
    if fields.get("blind"):
        return (f"quiescence guard inactive: screens {reading} every "
                f"{cadence}s, too slow to tell decoration from content "
                f"(needs one every {fields.get('viable')}s); "
                "waits judge every sample")
    return (f"quiescence guard: screens {reading} every {cadence}s, "
            f"decoration measured over {window}s")


def _failure_report(fields):
    """Return the failure report: what was pending, which clock, what to try."""
    lines = [f"FAILED: {fields.get('error')}"]
    for label, key in (("pending", "pending"),
                       ("clock", "clock"),
                       ("scope", "scope"),
                       ("nearest miss", "nearest-miss"),
                       ("unreadable screen", "unreadable-screen"),
                       ("screenshot", "screenshot")):
        value = fields.get(key)
        if value:
            lines.append(f"  {label}: {value}")
    for miss in fields.get("landmark-miss") or ():
        # The landmark half of the nearest-miss report (F65): names
        # the variant that came closest to matching, and the regions
        # it failed on along with the percentage each one matched.
        # One line per variant, because a wait with several branches
        # may have been watching more than one landmark at once.
        lines.append(f"  landmark miss: {miss}")
    unclear = fields.get("unreadable-cells")
    if unclear:
        # Shown alongside the nearest-miss report, not instead of it:
        # the nearest miss is measured against screen rows that may
        # include cells that were never actually readable, so this
        # line says how far to trust that measurement.
        lines.append(
            f"  unreadable: {unclear} cells matched no glyph and were "
            "read as spaces; the screen may use a font this host "
            "does not have")
    restored = fields.get("restored")
    if restored:
        # Lists what a `with` scope put back before this failure
        # report was written. The machine itself no longer shows the
        # old state, so this line is the only record of it.
        lines.append("  restored: " + "; ".join(restored))
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
    """Base class for stderr rendering: one line per event, plus heartbeats."""

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
        """Return the 'elapsed / limit' text a tick shows. Never a progress bar.

        Phases and observations have no meaningful measure of how much
        of the work is done, only of how much time has passed, so
        they're shown as these two numbers rather than as a filled-in
        bar that would imply a fraction complete.
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
    """Rendering for a redirected log: no ANSI colors, a periodic heartbeat line."""

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
    """Rendering for an attached terminal: one live line updated in place."""

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
    """Rendering for programs: the raw event stream on stdout, nothing else."""

    def __init__(self, stream):
        self.stream = stream

    def event(self, event):
        self.stream.write(event.as_json() + "\n")
        self.stream.flush()

    def tick(self, **fields):
        # Ticks are only for live human display; the jsonl stream
        # carries recorded events and nothing else, so this is a
        # no-op.
        return

    def clear(self):
        return

    def close(self):
        return
