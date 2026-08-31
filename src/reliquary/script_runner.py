# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Runtime executor for ``.rlqs`` scripts on QEMU/DOS.

The dynamic semantics this module implements come from
docs/spec/script-spec.md's "Execution model": execution is defined
in terms of **samples** -- discrete readings of the machine -- and
**episodes**, which are runs of consecutive samples where a
condition holds. Dispatch is single-threaded and runs each
statement list to completion, so no sample is ever taken while a
statement list is executing, and every timing clock is only checked
at a boundary: the start of a statement, or a dispatch sample.

Timing values are not recomputed here. :mod:`reliquary.script_timing`
already resolved every bound at parse time, so this module just
looks each one up, and can name which scope supplied it when a
clock expires.
"""

import collections
import contextlib
import dataclasses
import difflib
import mimetypes
import os
import re
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from . import text_recognize
from .binding import bind_properties, console_asker, describe_sources
from .document import load_document
from . import fonts as _fonts
from . import landmarks as _landmarks
from .errors import (PreflightError, ReliquaryError, RunCancelled,
                     RunFailure, StaticError, UnreadableScreen,
                     exit_code, outcome)
from .home import cache_dir as _resolve_cache_dir
from .library import locate_blueprint, locate_script
from .control_display import char_keys, normalize_row
from .machine_handle import Machine, validate_screenshot_name
from .progress import interactive as _interactive, stream_for
from .resolve import load_namespace
from .script_parser import load_script
from .script_timing import (format_plan, parse_duration,
                            resolve as resolve_timing)
from .script_validation import PORTABLE_KEY_NAMES, reach
from . import backends as _backends
from . import events as _events
from . import screen_stability as _stability
from . import machines as _machines
from . import transcript as _transcript
from .machines import DryRun


# Returned by a statement list that ended in `finish`, meaning the
# run is complete. This is distinct from both "fell off the end of
# the list" (None) and a phase name to transfer control to.
_FINISH = object()

# Seconds between dispatch samples. How often to sample is the
# control plane's decision, never something a script controls (G5).
_RECORD_PACE = 0.1

_POLL_INTERVAL = 2.0

#: How often to sample while a screen is still moving (changing).
#: The poll interval above waits out a stable screen cheaply, but it
#: cannot confirm a screen has settled: whether a screen has gone
#: quiet is only observable by sampling closely during that window,
#: and two reads two seconds apart say nothing about the last 200ms
#: of that window. Dense sampling is only used there, never across
#: the whole of a long wait.
_SETTLE_POLL = 0.1

# Maps the language's portable `press` key names onto the carrier
# seam's own key vocabulary, which is QEMU's qcode set (D103). Most
# entries just map a name to itself; the handful that don't
# (`enter`, `space`, `pageup`, `pagedown`) are the entire reason this
# table exists. Every backend receives these mapped names, QEMU and
# VirtualBox alike.
#
# Which key names the language allows at all is decided by static
# validation, not by this table. Keeping this map explicit means an
# unsupported key name fails safely instead of being silently
# passed through.
_QEMU_KEY_NAMES = {
    "enter": "ret",
    "esc": "esc",
    "tab": "tab",
    "space": "spc",
    "backspace": "backspace",
    "up": "up",
    "down": "down",
    "left": "left",
    "right": "right",
    "insert": "insert",
    "delete": "delete",
    "home": "home",
    "end": "end",
    "pageup": "pgup",
    "pagedown": "pgdn",
    "ctrl": "ctrl",
    "alt": "alt",
    "shift": "shift",
    "f1": "f1", "f2": "f2", "f3": "f3", "f4": "f4",
    "f5": "f5", "f6": "f6", "f7": "f7", "f8": "f8",
    "f9": "f9", "f10": "f10", "f11": "f11", "f12": "f12",
}


def _normalize_row(text):
    """Collapse a screen row's whitespace, as matching defines it."""
    return normalize_row(text)


def resolve_key(spelling):
    """Resolve one `press` key or chord to QEMU key names.

    A chord's non-modifier member can be a single printable
    character (as in ``ctrl+c``); a bare key name by itself cannot.

    An unknown key name raises a STATIC ERROR with its own clear
    message. The CLI's `press` command calls this function directly
    (with no script and no line number involved), so letting a bare
    ``KeyError`` escape here would have reported an ordinary user
    typo as if it were a bug in reliquary itself. A script run
    catches and re-raises this error against the statement's actual
    line number.
    """
    parts = spelling.split("+")
    resolved = []
    for part in parts:
        if part in PORTABLE_KEY_NAMES:
            resolved.append(_QEMU_KEY_NAMES[part])
            continue
        if len(parts) > 1 and len(part) == 1:
            resolved.extend(char_keys(part))
            continue
        raise StaticError(f"{part!r} is not a portable key name",
                          rule_id="key.not-portable")
    return resolved


def _seconds(spelling):
    return parse_duration(spelling) if spelling is not None else None


def _describe(condition):
    """Name a condition as the script spelled it."""
    if condition.channel == "machine":
        return f"machine={condition.value}"
    if condition.kind == "regex":
        return f"/{condition.value}/"
    if condition.kind == "landmark":
        return f"@{condition.value}"
    return repr(_literal(condition.value))


def _literal(value):
    """The plain text of an authored string, or the value itself."""
    if isinstance(value, str):
        return value
    if value.interpolated:
        raise _PropertyUnbound(value.keys[0])
    return value.text


def _render_literal(value, bindings):
    """Render an authored string with runtime-owned bindings."""
    if isinstance(value, str):
        return value
    rendered = []
    for part in value.parts:
        if isinstance(part, str):
            rendered.append(part)
            continue
        try:
            rendered.append(bindings[part.key])
        except KeyError:
            raise _PropertyUnbound(part.key) from None
    return "".join(rendered)


@dataclasses.dataclass(frozen=True)
class _HttpResponse:
    """One response body the run-scoped HTTP service can serve."""

    name: str
    path: str
    body: bytes


class _HttpService:
    """Run-scoped static HTTP service for installer answer files."""

    guest_ip = "10.0.2.2"

    def __init__(self, responses, port_min=8000, port_max=9000):
        self._responses = {response.path: response for response in responses}
        self._port_min = port_min
        self._port_max = port_max
        self._server = None
        self._thread = None
        self.port = None

    @property
    def url(self):
        if self.port is None:
            return None
        return f"http://{self.guest_ip}:{self.port}"

    def start(self):
        """Bind a free port in range and start serving responses."""
        if self._server is not None:
            self.stop()
        handler = self._handler()
        last_error = None
        for port in range(self._port_min, self._port_max + 1):
            try:
                server = ThreadingHTTPServer(("", port), handler)
            except OSError as error:
                last_error = error
                continue
            self._server = server
            self.port = port
            self._thread = threading.Thread(
                target=server.serve_forever, daemon=True)
            self._thread.start()
            return
        detail = f": {last_error}" if last_error is not None else ""
        raise RunFailure(
            f"no free HTTP port in range {self._port_min}-"
            f"{self._port_max}{detail}", rule_id="http.no-free-port")

    def stop(self):
        """Stop the server; harmless when it is already stopped."""
        server = self._server
        if server is None:
            self.port = None
            return
        self._server = None
        self.port = None
        server.shutdown()
        server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None

    def _handler(self):
        responses = self._responses

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self._serve(send_body=True)

            def do_HEAD(self):
                self._serve(send_body=False)

            def log_message(self, format, *args):
                return

            def _serve(self, send_body):
                path = urlsplit(self.path).path
                response = responses.get(path)
                if response is None:
                    self.send_error(404)
                    return
                ctype = mimetypes.guess_type(path)[0] or "text/plain"
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(response.body)))
                self.end_headers()
                if send_body:
                    self.wfile.write(response.body)

        return Handler


class _PropertyUnbound(Exception):
    """A ``${key}`` reference reached the runtime without a bound value.

    This is the one deliberate exception in this codebase outside
    reliquary's normal error hierarchy, and that is intentional. It
    is a private internal signal, not a user-facing error: every
    place this is raised, it is caught by the statement dispatcher
    and restated as a located ``ScriptRuntimeError``, so no external
    caller ever actually sees this class. Making it a
    ``ReliquaryError`` would give it a clean exit code and a tidy
    one-line report -- which is exactly what it would get if it ever
    escaped uncaught, and an escape here means a bug in the
    dispatcher, which should show a full traceback instead of a
    tidy error message. So the rule that every user-facing error
    lives in the hierarchy still holds; this exception is just not
    one of those.
    """

    def __init__(self, key):
        super().__init__(key)
        self.key = key


class _Located:
    """A diagnostic that can cite the statement it came from."""

    def __init__(self, message, statement=None, path=None,
                 rule_id=None):
        super().__init__(message, rule_id=rule_id)
        self.statement = statement
        self.path = path

    def __str__(self):
        location = ""
        if self.statement is not None and self.statement.line:
            location = f" at line {self.statement.line}"
        return (f"{self.path or '<script>'}{location}: "
                f"{Exception.__str__(self)}")


class ScriptRuntimeError(_Located, RunFailure):
    """An error that occurred during script execution.

    This is the dynamic (runtime) tier of the error taxonomy -- a
    RUN FAILURE, exit code ``4``. ``clock`` and ``scope`` are set
    when a timing bound expired, so the failure report can name
    which clock ran out and which scope it came from.
    """

    clock = None
    scope = None


class ScriptPreflightError(_Located, PreflightError):
    """A machine rule broken before the first guest input (exit ``3``).

    This has the same diagnostic shape as a runtime error -- it
    cites the statement that would have broken the rule -- but it is
    raised before the run ever touches the guest, so it belongs to
    the preflight tier instead.
    """


@dataclasses.dataclass(frozen=True)
class ScriptRun:
    """The output of a ``run-script <label>`` invocation.

    A run **returns its output** and stores nothing itself (D36):
    ``events`` is the run's entire event stream, in order, with the
    terminal event last. A caller that wants a record of the run has
    to keep this object; reliquary itself keeps no copy.
    """

    machine_id: str
    script_path: str
    created_machine: bool = False
    final_phase: str = "-"
    machine_phase: str = "-"
    events: tuple = ()


@dataclasses.dataclass(frozen=True)
class _Sample:
    """One reading of every channel, taken at a single instant.

    ``rows`` are normalized for matching against conditions;
    ``frame`` is the screen exactly as the carrier seam handed it
    over -- character rows together with their attribute tokens --
    which is what the quiescence (stability) check compares, since
    identity for that check is the whole pair, not just the text.

    ``unreadable`` covers a third kind of sample, alongside a normal
    screen and a stopped machine: the carrier answered, but what it
    handed back was not a text screen at all. It holds the *reason*,
    not just a true/false flag, so a failure report can say exactly
    what shape was captured -- a screen nobody could read is not the
    same thing as a blank screen, and reporting it as blank would
    make a graphics-mode guest indistinguishable from one that was
    actually cleared. No condition can ever hold on a sample like
    this, so a `wait` just keeps looking and eventually expires on
    its own clock.
    """

    rows: tuple = ()
    stopped: bool = False
    frame: tuple = ()
    unreadable: str = None
    #: The captured framebuffer image, read only when a landmark
    #: condition is armed (F65). This holds the pixels a landmark is
    #: matched against, and it is what the quiescence check judges
    #: for a sample like this.
    image: object = None
    #: How many cells of this screen matched no glyph confidently
    #: enough to be trusted, and were read as blank spaces instead.
    #: A screen can be perfectly readable *as a shape* and still be
    #: mostly unrecognized character-by-character, which
    #: `unreadable` above cannot express: `unreadable` means no
    #: screen arrived at all, while this means a screen did arrive
    #: and part of its content is a guess.
    unclear: int = 0
    #: The fonts this read was matched against, in the order they
    #: were tried (F61). Empty for a backend that reads already
    #: resolved characters directly, since that kind of backend
    #: recognizes nothing itself and so consults no font.
    fonts: tuple = ()


class _Observation:
    """One armed condition, tracking its episodes.

    An **episode** is the longest run of consecutive samples during
    which the condition holds. ``stable`` is satisfied once the
    current episode's age reaches its required duration. ``consumed``
    implements the reactive re-arm rule: a handler that already
    fired only re-arms after a sample where its condition stops
    holding.
    """

    def __init__(self, condition, stable=None, landmark=None,
                 capture_format=None):
        self.condition = condition
        self.stable = stable
        self.consumed = False
        self._episode = None
        #: The resolved declaration a landmark condition watches
        #: for, bound at preflight so no sample ever has to resolve
        #: an asset itself (F65).
        self.landmark = landmark
        self.capture_format = capture_format
        #: The last verdict this observation reached. This is what
        #: the failure report quotes as the "nearest miss."
        self.result = None

    @property
    def channel(self):
        return self.condition.channel

    @property
    def watches_pixels(self):
        """Whether this condition is judged on a captured framebuffer."""
        return self.condition.kind == "landmark"

    def matches_row(self, row):
        """Whether one screen row satisfies this condition.

        This is the per-row check that the whole-sample test is
        built out of, so a match event can name the specific row
        that satisfied the condition instead of just asserting that
        some row did. A landmark condition matches against a whole
        screen, never a single row, so this always answers no for
        one, and the match event instead names the landmark variant
        that matched.
        """
        if self.condition.channel == "machine" or self.watches_pixels:
            return False
        if self.condition.kind == "regex":
            return re.search(self.condition.value, row) is not None
        return _normalize_row(_literal(self.condition.value)) in row

    def holds(self, sample):
        """Whether the condition holds at this sample."""
        if self.condition.channel == "machine":
            return sample.stopped
        if self.watches_pixels:
            if sample.image is None:
                # Either the machine is stopped or the capture was
                # unreadable: no pixels arrived, so nothing was
                # matched and nothing is claimed here. The wait just
                # keeps looking.
                return False
            self.result = _landmarks.match(self.landmark, sample.image,
                                           self.capture_format)
            return self.result.matched
        return any(self.matches_row(row) for row in sample.rows)

    def update(self, sample, now):
        """Fold one sample in; report whether the condition is met."""
        if not self.holds(sample):
            self._episode = None
            self.consumed = False
            return False
        if self._episode is None:
            self._episode = now
        if self.consumed:
            return False
        return self.stable is None or now - self._episode >= self.stable


@dataclasses.dataclass
class _ActiveScope:
    """One entered ``with`` scope, and the value it will restore on exit.

    ``captured`` is read at entry, before the scope's change is
    applied: a tuple of drive keys for the machine's boot order, or
    a slot's medium as the ``(media, path)`` pair needed to restore
    it -- a declared media by name, an anonymous image by the path
    it was mounted from, or ``(None, None)`` for a slot that was
    empty.
    """

    scope: object
    captured: object


class _ScriptEngine:
    """One run of one script against one cached machine."""

    def __init__(self, script, machine_id, context, machine_home,
                 events=None, script_path=None, plan=None,
                 clock=time.monotonic, sleep=time.sleep,
                 http_service_factory=_HttpService, bindings=None,
                 record_pace=None, recording_writer=None,
                 landmarks=None, capture_format=None):
        self._script = script
        self._plan = plan if plan is not None else resolve_timing(script)
        self._phases = {phase.name: phase for phase in script.phases}
        self._machine_id = machine_id
        self._context = context
        self._machine_home = machine_home
        self._script_path = script_path
        self._running = False
        self._display = False
        #: The font banks a `font` statement's names resolved to,
        #: tried before the host's own default banks. Empty until a
        #: script actually names one.
        self._font_prefix = ()
        #: ``{name: LandmarkDeclaration}`` for every `@name` this
        #: script watches, along with the capture format the
        #: machine's driving plane reports. Both are resolved once,
        #: at preflight (F65), so no individual sample needs to
        #: resolve an asset or ask the carrier seam anything.
        self._landmarks = dict(landmarks or {})
        self._capture_format = capture_format
        self._now = clock
        self._sleep = sleep
        self._step = 0
        self._http_service_factory = http_service_factory
        self._http = None
        self._property_bindings = bindings
        self._bindings = dict(bindings.values) if bindings else {}
        self._secret_values = (
            set(bindings.secret_values()) if bindings else set())
        self._secret_entered = False
        self._secret_recorded = False
        self._record_pace = record_pace
        self._recording_writer = recording_writer
        # A recording pace can only shorten the sampling interval,
        # never lengthen it: recording exists to close the
        # two-second gaps between samples, so it can only make the
        # run sample more often than it otherwise would.
        self._pace_settle = min(_SETTLE_POLL, record_pace or _SETTLE_POLL)
        self._pace_idle = min(_POLL_INTERVAL, record_pace or _POLL_INTERVAL)
        self._phase = None
        self._run_started = None
        self._phase_started = None
        self._phase_budget = None
        # Raw material for the failure report, kept up to date as
        # the run goes: what is currently pending, the route taken
        # through the script, how often each phase was revisited,
        # and the last screen that was read.
        self._pending = None
        self._pending_literal = None
        #: The currently armed landmark observations, kept for the
        #: failure report: their verdicts describe how close the
        #: nearest miss actually was.
        self._pending_landmarks = ()
        self._route = []
        self._revisits = collections.Counter()
        self._last_sample = None
        #: Learned from the first console that gets opened, since
        #: only the adapter's session actually knows whether its
        #: screens are recognized from pixels. Assuming the cheap
        #: path until then costs nothing: a sampling cadence needs
        #: at least two samples before it even exists.
        self._recognized_screens = False
        self._guard_reported = False
        #: The `with` scopes control is currently inside, outermost
        #: first, and what each one will restore on exit.
        self._scopes = []
        #: What the run has already restored, kept for the failure
        #: report: a scope changed state that whoever is debugging a
        #: failure would otherwise expect to still see, so the run
        #: has to say what it already put back.
        self._restored = []
        self._cancelled = threading.Event()
        self.events = (events if events is not None
                       else _events.EventStream(redact=self._redact))
        self.final_phase = None
        self.machine_phase = None

    # -- diagnostics and the stream ------------------------------

    def cancel(self):
        """Request a stop; the run ends at the next event boundary.

        Boundaries are statement starts, dispatch samples, and the
        chunk boundaries within a host file transfer, so an input
        delivery already in flight completes atomically, while a
        large media fetch can abort wherever it currently stands --
        this is the execution model's severability guarantee
        (script-spec "The run's output and failure").
        """
        self._cancelled.set()

    @property
    def cancelled(self):
        """Whether a stop has already been requested."""
        return self._cancelled.is_set()

    def _error(self, message, statement=None, rule_id=None):
        return ScriptRuntimeError(
            message, statement=statement, path=self._script_path,
            rule_id=rule_id)

    def _expired(self, clock, bound, statement=None, detail="",
                 rule_id=None):
        """A timing failure naming the clock and where it came from."""
        failure = self._error(
            f"{clock} of {bound.spelling} expired{detail} (from the "
            f"{bound.source})", statement, rule_id=rule_id)
        failure.clock = f"{clock} of {bound.spelling}"
        failure.scope = bound.source
        return failure

    def _poll_interval(self, settled):
        """Return the sleep interval to use between samples.

        While recording, neither interval is allowed to exceed the
        record pace: the recorder cannot run its own separate
        sampler (QEMU only allows one QMP client at a time), so the
        run's own polls *are* the capture, and a two-second idle
        poll would leave a two-second gap in the recording through
        most of a boot. If the pace were instead used as a floor (a
        minimum), the normal sampling cadence would stay exactly as
        it was, which would be the same as recording having no pace
        setting at all.
        """
        return self._pace_idle if settled else self._pace_settle

    def _redact(self, message):
        """Blank any bound secret value out of a rendered line of text.

        This protects reliquary's own output -- the event stream and
        its diagnostic messages. It has no way to reach what a guest
        installer itself prints, logs, or shows in a screenshot the
        script explicitly requested.
        """
        for value in self._secret_values:
            if value and value in message:
                message = message.replace(value, "\u00absecret\u00bb")
        return message

    def _emit(self, kind, **fields):
        return self.events.emit(kind, **fields)

    def _progress(self, expiry, timeout, description, now):
        """Advance the live display, showing elapsed time against its limit."""
        self.events.tick(
            phase=self._phase.name if self._phase is not None else "-",
            step=self._step, description=description,
            elapsed=max(0.0, timeout - max(0.0, expiry - now)),
            limit=timeout)

    def _read_machine_phase(self):
        try:
            state = _machines.load_machine_state(
                self._machine_id, self._context)
            return state.get("phase", "-")
        except PreflightError:
            return "-"

    def _report_final(self):
        """Record which phase the script and the machine each finished in.

        Called on every exit path -- success, a script error, or an
        unexpected exception -- so it is always clear what state the
        machine was left in, not just what happened along the way.
        """
        self.machine_phase = self._read_machine_phase()
        self.final_phase = self._phase.name if self._phase else "-"

    # -- the run -------------------------------------------------

    def run(self, display=False):
        self._display = display
        self._emit(_events.RUN_START,
                   script=self._script_path or "<script>",
                   machine=self._machine_id,
                   platform=self._script.platform or "dos")
        self._establish_machine(display)
        self._log_bindings()
        self._run_started = self._now()
        try:
            if self._script.phases:
                self._run_phases()
            else:
                # A linear script's one ending: reaching end of file
                # completes the run.
                self._execute(self._script.statements)
            # The run reached its end while still inside whatever
            # scopes were open, and the last thing it does is close
            # them. If a restore cannot be made, it fails the run
            # right here -- a cost D104 identified and accepted,
            # handled through the same failure path as any other
            # error below.
            self._unwind(None)
            self._report_final()
            self._terminal(None)
        except RunCancelled as exc:
            self._unwind(exc)
            self._report_final()
            self._terminal(exc)
            raise
        except ReliquaryError as exc:
            self._unwind(exc)
            self._report_final()
            if isinstance(exc, ScriptRuntimeError) and exc.path is None:
                exc.path = self._script_path
            self._fail(exc)
            raise
        except Exception as exc:
            self._unwind(exc)
            self._report_final()
            wrapped = self._error(f"unexpected error: {exc}")
            self._fail(wrapped)
            raise wrapped from exc
        finally:
            self._http_stop()
            self.events.clear()

    def _terminal(self, error):
        """Emit the last event in the stream: how the run concluded."""
        self._emit(
            _events.RUN_END, outcome=outcome(error),
            **{"exit-code": exit_code(error) if error else 0,
               "final-phase": self.final_phase or "-",
               "machine-phase": self.machine_phase or "-",
               "error": str(error) if error is not None else None})

    def _fail(self, error):
        """Emit the failure report, then the terminal event.

        Everything in the report comes from the run itself: the
        pending condition or action, which clock expired and which
        scope supplied it, the route taken with revisit counts, the
        closest match found on the last screen read, an automatic
        screenshot, the command to try next -- and **what a scope
        already put back**. That last item is not just decoration: a
        scoped change is state that whoever debugs the failure would
        otherwise expect to still find on the machine, so a run that
        already undid it has to say so.
        """
        self.events.clear()
        self._emit(
            _events.FAILURE, error=str(error), pending=self._pending,
            clock=getattr(error, "clock", None),
            scope=getattr(error, "scope", None),
            restored=tuple(self._restored) or None,
            route=tuple(self._route) or None,
            revisits={name: count for name, count
                      in self._revisits.items() if count > 1} or None,
            **{"nearest-miss": self._nearest_miss(),
               "landmark-miss": self._landmark_miss(),
               "unreadable-screen": self._unreadable_screen(),
               "unreadable-cells": self._unreadable_cells(),
               "fonts-tried": self._fonts_tried(),
               "screenshot": self._failure_screenshot(),
               "next-command": self._next_command()})
        self._terminal(error)

    def _nearest_miss(self):
        """The screen row that came closest to matching the pending literal.

        Only a plain-text condition has a meaningful "nearest miss":
        a regex describes a shape, not a literal string, so there is
        nothing honest to measure a row's similarity against.
        """
        target = self._pending_literal
        if not target or not self._last_sample:
            return None
        rows = [row for row in self._last_sample.rows if row.strip()]
        if not rows:
            return None
        best = max(rows, key=lambda row: difflib.SequenceMatcher(
            None, target, row).ratio())
        return self._redact(best)

    def _landmark_miss(self):
        """The nearest miss of every landmark this expiry was watching.

        This is the landmark equivalent of `nearest-miss` above, and
        it needs its own separate field because the two measure
        different things: a text miss is the row closest to a
        literal string, while this is the *variant* of the landmark
        closest to what was captured, along with which regions
        failed to match and the percentage each one achieved. This
        is reported per-region rather than as one pooled score,
        because a small failing region would otherwise get drowned
        out by a large screen's overall matching average, and the
        report would lose the exact detail that makes it actionable.

        Returns nothing where no landmark was armed, which covers
        every run of every script that only watches text.
        """
        misses = [observation.result.describe()
                  for observation in self._pending_landmarks
                  if observation.result is not None
                  and not observation.result.matched]
        return tuple(misses) or None

    def _unreadable_screen(self):
        """Why the last read produced no screen, in cases where it produced none.

        This covers the case `_nearest_miss` cannot: when every
        sample was unreadable, there are no rows to compare against
        the target at all, so a silent report here would make an
        expiry look like a plain condition that simply never
        matched. Naming the actual shape that was captured turns
        that into a real answer -- for example, that the guest never
        reached a text mode.
        """
        if not self._last_sample:
            return None
        return self._last_sample.unreadable

    def _unreadable_cells(self):
        """How much of the last screen was a guess, in cases where any of it was.

        `_nearest_miss` compares the target against rows that may
        never have actually been read correctly: a cell that matches
        no glyph gets substituted with a space, so a screen drawn in
        a font this host does not have ends up looking merely
        sparse, and a `wait` on a word within it expires with
        nothing useful to show. Reporting how many cells were
        substituted turns "it never appeared" into "it may have been
        there and just unreadable" -- two different problems with
        two different fixes.

        Returns nothing when the count is zero, and for a backend
        that reads already resolved characters directly, since that
        backend recognizes nothing, so it can never misrecognize
        anything either.
        """
        if not self._last_sample or not self._last_sample.unclear:
            return None
        return self._last_sample.unclear

    def _fonts_tried(self):
        """The fonts the last read was matched against, in the order they were tried.

        This is reported alongside the `unreadable-cells` count: an
        author who named the wrong font in a `font` statement is
        told exactly which fonts were actually consulted, instead of
        being left with just a silent timeout (F61, P11). Returns
        nothing when the list is empty, which is the ordinary case,
        and always the case for a scraped read.
        """
        if not self._last_sample or not self._last_sample.fonts:
            return None
        return self._last_sample.fonts

    def _failure_screenshot(self):
        """Capture the failing screen, unless a secret has already been typed.

        Once a secret reaches the guest, automatic screenshots are
        suppressed for the rest of the run: an installer might echo
        back what it was given, and taking an automatic screenshot
        is not a deliberate choice made by the script author the way
        an explicit `screenshot` statement is.
        """
        if not self._running or self._secret_entered:
            return None
        name = f"failure-step-{self._step}"
        try:
            self._machine().screenshot(name)
        except Exception:
            # A failure report must never itself fail; the machine
            # may already be gone by this point.
            return None
        return os.path.join(self._machine_home, "screenshots",
                            f"{name}.png")

    def _next_command(self):
        """The command most likely to move the user forward."""
        if self._read_machine_phase() == "running":
            return f"rlq screen --machine {self._machine_id}"
        return f"rlq list-machines --machine {self._machine_id}"

    def _log_bindings(self):
        """Report each bound property's key and source -- never its value.

        The event stream serves as evidence of where each value came
        from, so a run stays auditable without ever exposing what
        any source actually supplied.
        """
        bindings = self._property_bindings
        if not bindings or not bindings.sources:
            return
        for key in sorted(bindings.sources):
            self._emit(_events.PROPERTY_BOUND, key=key,
                       source=bindings.sources[key],
                       secret=key in bindings.secret_keys or None)

    def _establish_machine(self, display):
        """Meet the `machine` header's precondition, then bind a port."""
        state = _machines.load_machine_state(
            self._machine_id, self._context)
        phase = state.get("phase")
        if self._script.machine == "stopped":
            # The script expects a stopped machine and performs its
            # own explicit start, typically after inserting media.
            if phase == "running":
                raise self._error(
                    "the script expects a stopped machine, but machine "
                    f"{self._machine_id} is running; stop it first",
                    rule_id="machine.expected-stopped")
            if phase != "ready":
                raise self._error(
                    f"machine {self._machine_id} cannot execute a "
                    f"script (phase: {phase})",
                    rule_id="machine.phase-cannot-run")
        elif phase == "ready":
            _machines.start_machine(
                self._machine_id, display=display, context=self._context,
                events=self.events)
            self._running = True
        elif phase == "running":
            vm = _machines.read_vm_state(_machines.machine_dir_path(
                self._machine_id, self._context))
            if vm is None:
                raise self._error(
                    "machine phase is running but no VM identity "
                    "recorded", rule_id="machine.no-vm-identity")
            self._running = True
        else:
            raise self._error(
                f"machine {self._machine_id} cannot execute a script "
                f"(phase: {phase})",
                rule_id="machine.phase-cannot-run")

    # -- scoped machine-state changes ----------------------------

    def _enter_scope(self, scope):
        """Capture what a scope owns, then apply its change.

        Entering a scope is a boundary, just like the start of a
        statement, so a cancellation lands here rather than partway
        between the capture and the change -- a scope whose change
        never got applied owns nothing yet and is never pushed onto
        the active scope stack.
        """
        self._check_clocks(scope.action)
        captured = self._capture(scope)
        self._emit(_events.SCOPE_ENTER, head=scope.head,
                   target=scope.target, detail=self._detail(scope.action),
                   line=scope.line)
        self._apply(scope)
        # Only pushed once the change has actually been made: a
        # scope whose entry failed owns nothing yet, and must not be
        # unwound later.
        self._scopes.append(_ActiveScope(scope, captured))

    def _capture(self, scope):
        """Read the value this scope's exit will put back."""
        state = _machines.load_machine_state(self._machine_id,
                                             self._context)
        if scope.head == "boot":
            return tuple(state.get("boot") or ())
        drive = (state.get("devices") or {}).get(
            scope.action.arguments[0]) or {}
        return (drive.get("media"), drive.get("path"))

    def _apply(self, scope):
        """Make the change a scope's head names."""
        if scope.head == "insert":
            self._insert(scope.action)
        elif scope.head == "eject":
            self._eject(scope.action)
        else:
            self._set_boot_prefix(scope.action)

    def _set_boot_prefix(self, action):
        """Put the named drives first in the boot order, keeping the rest of the order unchanged.

        This is the difference from `set-boot`, and the entire
        reason this `with` head is spelled `boot` rather than
        `set-boot` (D104): a script typically just wants to say
        "boot the CD first," and an author should not have to
        restate the whole order just to change one part of it.
        """
        keys = list(action.arguments)
        state = _machines.load_machine_state(self._machine_id,
                                             self._context)
        order = keys + [key for key in (state.get("boot") or ())
                        if key not in keys]
        self._action(action, "boot", " ".join(order))
        self._machine_change(action, _machines.set_boot_order, order)
        self._completed(action, "boot")

    def _leave_scopes(self, depth):
        """Restore every scope deeper than ``depth``, innermost first.

        Raises if a restore cannot be made, and that is a run
        failure like any other: the run is still going at this
        point, so there is no earlier error for this new one to be
        overshadowed by.
        """
        while len(self._scopes) > depth:
            self._restore(self._scopes.pop())

    def _unwind(self, failing):
        """Close every open scope as the run ends.

        ``failing`` is the error the run is already ending with, or
        ``None`` for a run that otherwise succeeded. It decides what
        happens if a restore fails: on a clean run, that restore
        failure becomes the run's failure; on a run that was already
        failing, the restore failure is only reported and the
        original error still stands -- a failed restore is never
        the more useful of the two diagnostics to surface.
        """
        problem = None
        while self._scopes:
            try:
                self._restore(self._scopes.pop())
            except ReliquaryError as exc:
                problem = problem or exc
        if problem is not None and failing is None:
            raise problem

    def _restore(self, active):
        """Put back what one scope captured, reporting the outcome either way.

        If a restore cannot be made, the error says **what it could
        not undo**, not just why: the machine layer's own refusal
        names the rule that blocked it (for example, a boot order
        can only be set while stopped), but only the run itself
        knows which scope was open and what value it was holding to
        restore.
        """
        scope = active.scope
        wanted = self._wanted(scope, active.captured)
        try:
            self._put_back(scope, active.captured)
        except ReliquaryError as exc:
            self._emit(_events.SCOPE_RESTORE, head=scope.head,
                       target=scope.target, detail=wanted,
                       error=str(exc), line=scope.line)
            raise self._error(
                f"{scope.target} could not be restored to {wanted}: {exc}",
                scope.action, rule_id=exc.rule_id) from exc
        self._restored.append(f"{scope.target}: {wanted}")
        self._emit(_events.SCOPE_RESTORE, head=scope.head,
                   target=scope.target, detail=wanted, line=scope.line)

    @staticmethod
    def _wanted(scope, captured):
        """What a restore will put back, as a phrase, before it runs."""
        if scope.head == "boot":
            # A machine always has a boot order, so the empty case
            # here cannot actually happen -- it is not a deliberate
            # policy choice. There is simply nothing to put back,
            # and `set_boot_order` refuses an empty order anyway.
            return " ".join(captured) if captured else "no recorded order"
        media, path = captured
        if media is not None:
            return f"@{media}"
        # An anonymous image that the slot held when the run started
        # is mounted in place by path, so putting it back just names
        # that same path again instead of resolving anything.
        return path if path is not None else "empty"

    def _put_back(self, scope, captured):
        """Reinstate one captured value, or raise saying it could not be restored.

        The underlying machine calls here are made directly, not
        through :meth:`_machine_change`: the caller states which
        change failed, and a diagnostic that gets located twice
        reads worse than one located just once.
        """
        if scope.head == "boot":
            if captured:
                _machines.set_boot_order(self._machine_id, list(captured),
                                         context=self._context)
            return
        slot = scope.action.arguments[0]
        media, path = captured
        state = _machines.load_machine_state(self._machine_id,
                                             self._context)
        drive = (state.get("devices") or {}).get(slot) or {}
        if drive.get("path") is not None:
            _machines.eject_media(self._machine_id, slot,
                                  context=self._context)
        if media is None and path is None:
            return
        # No cancel event here: a run ending on a Ctrl-C still owes
        # the machine whatever it took from it, and a fetch that
        # aborted partway through would leave the slot empty
        # instead of as it was originally found.
        _machines.insert_media(
            self._machine_id, slot, media, file=None if media else path,
            context=self._context, events=self.events)

    @staticmethod
    def _detail(action):
        """How a head's change reads on the stream, as authored."""
        if action.verb != "insert":
            return " ".join(action.arguments if action.verb == "boot"
                            else (action.arguments[0],))
        kind, name = action.arguments[1]
        sigil = "@" if kind == "media" else "$"
        return f"{action.arguments[0]} {sigil}{name}"

    def _cross_into(self, name):
        """Leave the scopes a phase sits outside; enter the ones it sits inside.

        **A scope tracks where control currently is, not where the
        text is positioned** (D104): a phase counts as inside a
        scope group however control actually reached it, so this
        compares the two scope chains rather than the two phases'
        text positions. Their shared prefix is left untouched;
        whatever the old phase had beyond that prefix gets restored
        innermost first, and whatever the new phase has beyond it
        gets applied outermost first -- which means re-entering the
        same phase re-applies its scopes, with no special case
        needed for that.
        """
        chain = self._script.phase_scopes.get(name, ())
        depth = 0
        while (depth < len(chain) and depth < len(self._scopes)
               and self._scopes[depth].scope is chain[depth]):
            depth += 1
        self._leave_scopes(depth)
        for scope in chain[depth:]:
            self._enter_scope(scope)

    def _run_phases(self):
        """Walk the phase graph from `entry` until a `finish`."""
        name = self._script.entry
        self._cross_into(name)
        while True:
            phase = self._phases[name]
            self._phase = phase
            self._route.append(name)
            self._revisits[name] += 1
            activation = self._revisits[name]
            self._emit(_events.PHASE_START, phase=name,
                       activation=activation, line=phase.line)
            # A budget is dynamically scoped to one activation, so
            # each entry to a phase starts a fresh one.
            self._phase_started = self._now()
            self._phase_budget = self._plan.phase_deadlines.get(name)
            result = (self._run_reactive(phase) if phase.handlers
                      else self._execute(phase.statements))
            self._emit(_events.PHASE_END, phase=name,
                       activation=activation,
                       elapsed=round(self._now() - self._phase_started, 3))
            if result is _FINISH or result is None:
                return
            self._cross_into(result)
            name = result

    # -- statements ----------------------------------------------

    def _execute(self, statements):
        """Run a statement list, and report how control left it.

        A ``with`` scope in a linear script brackets a run of the
        list: control is only considered inside it for exactly the
        statements it wraps, so entering and leaving happen exactly
        where the script text says. A failure inside the scope
        leaves it on the scope stack, where the run's unwind step
        restores it -- the same path every other outcome takes too.
        """
        for statement in statements:
            units = getattr(statement, "units", None)
            if units is not None:
                depth = len(self._scopes)
                self._enter_scope(statement)
                result = self._execute(units)
                self._leave_scopes(depth)
                if result is not None:
                    return result
                continue
            self._step += 1
            self._check_clocks(statement)
            result = self._statement(statement)
            if result is not None:
                return result
        return None

    def _statement(self, statement):
        verb = statement.verb
        if verb == "goto":
            self._emit(_events.TRANSITION, transition="goto",
                       target=statement.arguments[0], line=statement.line)
            return statement.arguments[0]
        if verb == "finish":
            self._emit(_events.TRANSITION, transition="finish",
                       line=statement.line)
            return _FINISH
        try:
            # An unbound `${key}` can reach the runtime from a
            # condition just as easily as from an argument, so one
            # handler here covers every kind of statement that could
            # carry one.
            if verb == "wait":
                return self._wait(statement)
            if verb == "enter":
                self._enter(statement)
            elif verb == "type":
                self._type(statement)
            elif verb == "press":
                self._press(statement)
            elif verb == "select":
                self._select(statement)
            elif verb == "click":
                self._click(statement)
            elif verb == "screenshot":
                self._screenshot(statement)
            elif verb == "insert":
                self._insert(statement)
            elif verb == "eject":
                self._eject(statement)
            elif verb == "set-boot":
                self._set_boot(statement)
            elif verb == "http":
                self._http_control(statement)
            elif verb == "start":
                self._start(statement)
            elif verb == "stop":
                self._stop(statement)
            elif verb == "set":
                self._set(statement)
            elif verb == "font":
                self._font(statement)
            else:
                raise self._error(f"unknown statement: {verb}",
                                  statement,
                                  rule_id="node.unknown-verb")
        except _PropertyUnbound as unbound:
            raise self._unbound(unbound, statement) from None
        return None

    def _unbound(self, unbound, statement):
        return self._error(
            f"the property ${{{unbound.key}}} has no bound value",
            statement, rule_id="prop.unbound-at-runtime")

    def _set(self, statement):
        """Record a machine variable -- the script's channel for sending a value to the host."""
        key = statement.arguments[0]
        value = _render_literal(statement.arguments[1], self._bindings)
        self._action(statement, "set", f"{key}={value!r}")
        try:
            _machines.set_machine_var(
                self._machine_id, key, value, context=self._context)
        except ReliquaryError as exc:
            raise self._error(str(exc), statement,
                              rule_id=exc.rule_id) from exc
        self._completed(statement, "set")

    def _font(self, statement):
        """Replace the font prefix (F61, D109).

        `font @name...` applies from this point forward: the named
        fonts are tried, in the order given, before the host's own
        default fonts. A second `font` statement **replaces** this
        prefix rather than adding to it -- it does not build up an
        accumulating list, so an author who wants several fonts
        together has to name them all together on the same
        statement.
        """
        names = []
        for kind, name in statement.arguments:
            if kind == "property":
                try:
                    name = self._bindings[name]
                except KeyError:
                    raise _PropertyUnbound(name) from None
            names.append(name)
        self._action(statement, "font", " ".join(f"@{n}" for n in names))
        try:
            self._font_prefix = tuple(
                _fonts.load_font_bank(name, self._context) for name in names)
        except ReliquaryError as exc:
            raise self._error(str(exc), statement,
                              rule_id=exc.rule_id) from exc
        self._completed(statement, "font")

    # -- observation ---------------------------------------------

    def _observation(self, condition, stable):
        """Arm one condition, using what preflight has already resolved.

        A landmark observation carries its declaration and the
        plane's capture format from here, rather than resolving
        either one mid-run: both were already answered during
        preflight (G3), and a sample that had to read a file to
        decide something would mean a refusal could show up after
        the first guest input, which is exactly what preflight
        exists to prevent.
        """
        landmark = (self._landmarks.get(condition.value)
                    if condition.kind == "landmark" else None)
        return _Observation(condition, _seconds(stable), landmark,
                            self._capture_format)

    def _arm(self, statement, observations, description):
        """Announce an observation and remember it as pending."""
        bound = self._bound(statement)
        self._pending = description
        literal = None
        if len(observations) == 1:
            condition = observations[0].condition
            if condition.channel == "screen" and condition.kind == "text":
                literal = _normalize_row(_literal(condition.value))
        self._pending_literal = literal
        self._pending_landmarks = tuple(
            observation for observation in observations
            if observation.watches_pixels)
        self._emit(_events.OBSERVATION_ARM, description=description,
                   timeout=bound.seconds, line=getattr(statement, "line", 0),
                   **{"timeout-source": bound.source})
        return bound

    def _wait(self, statement):
        if statement.handlers:
            return self._wait_branching(statement)
        condition = statement.condition
        description = _describe(condition)
        observations = [self._observation(condition, statement.stable)]
        bound = self._arm(statement, observations, description)
        self._observe(observations, bound, description, statement)
        return None

    def _wait_branching(self, statement):
        handlers = statement.handlers
        observations = [self._observation(handler.condition, handler.stable)
                        for handler in handlers]
        description = " or ".join(
            _describe(handler.condition) for handler in handlers)
        bound = self._arm(statement, observations, description)
        index = self._observe(observations, bound, description, statement)
        handler = handlers[index]
        self._emit(_events.HANDLER_FIRE, keyword="on",
                   description=_describe(handler.condition),
                   line=handler.line)
        # The sample loop holds no session open of its own, so a
        # handler body is free to open one: QEMU's QMP server only
        # allows one client at a time.
        return self._execute(handler.statements)

    def _run_reactive(self, phase):
        """Dispatch a reactive phase's standing handlers."""
        observations = [self._observation(handler.condition, handler.stable)
                        for handler in phase.handlers]
        description = " or ".join(
            _describe(handler.condition) for handler in phase.handlers)
        bound = self._arm(phase, observations, description)
        self._require_screen(observations, phase)
        started = self._now()
        expiry = started + bound.seconds
        gate = self._gate(phase)
        monitor = _stability.ScreenStability() if gate is None else (
            _stability.ScreenStability(threshold=gate.value))
        self._gated = None
        self._measured = False
        text, pixels = self._reads(observations)
        while True:
            self._check_clocks()
            sample = self._read(text, pixels)
            now = self._now()
            # An unstable (still-changing) frame is not evaluated
            # against *any* of the handlers, which is why the
            # stability gate belongs to the container (the phase),
            # not to any single handler.
            settled = self._settled(gate, monitor, sample, now)
            expired = now >= expiry
            if not (settled or (expired and not self._measured)):
                if expired:
                    self._expire_interval(description, bound, phase)
                self._sleep(self._poll_interval(False))
                continue
            fired = None
            for index, observation in enumerate(observations):
                # Every armed observation sees every sample, so the
                # episode tracking for handlers that did not fire
                # this time stays accurate too.
                if observation.update(sample, now) and fired is None:
                    fired = index
            if fired is None:
                if expired:
                    self._expire_interval(description, bound, phase)
                self._progress(expiry, bound.seconds, "dispatch", now)
                self._sleep(self._poll_interval(settled))
                continue
            observations[fired].consumed = True
            handler = phase.handlers[fired]
            self.events.clear()
            self._matched(_describe(handler.condition), sample,
                          observations[fired], now - started, handler.line)
            self._emit(_events.HANDLER_FIRE, keyword="always",
                       description=_describe(handler.condition),
                       line=handler.line)
            result = self._execute(handler.statements)
            if result is not None:
                return result
            # Dispatch resumes in the same phase, and the interval
            # clock restarts with it.
            self._arm(phase, observations, description)
            started = self._now()
            expiry = started + bound.seconds

    def _observe(self, observations, bound, description, statement):
        """Sample until one observation is met; report which."""
        self._require_screen(observations, statement)
        started = self._now()
        expiry = started + bound.seconds
        gate = self._gate(statement)
        monitor = _stability.ScreenStability() if gate is None else (
            _stability.ScreenStability(threshold=gate.value))
        self._gated = None
        self._measured = False
        text, pixels = self._reads(observations)
        while True:
            self._check_clocks(statement)
            sample = self._read(text, pixels)
            now = self._now()
            # An unsettled (still-changing) sample is not one the
            # condition gets judged against, and sampling tightens
            # while the screen keeps moving: whether a screen has
            # gone quiet is only observable by sampling closely
            # during that window.
            # **The stability gate only delays acceptance and never
            # causes a failure by itself** -- at expiry, the
            # condition is evaluated against whatever screen is
            # currently there, so a timeout still means samples were
            # taken and none of them satisfied the condition, never
            # that nobody actually looked.
            settled = self._settled(gate, monitor, sample, now)
            expired = now >= expiry
            if not (settled or (expired and not self._measured)):
                if expired:
                    self._expire_observation(description, bound, statement)
                self._sleep(self._poll_interval(False))
                continue
            for index, observation in enumerate(observations):
                if observation.update(sample, now):
                    self.events.clear()
                    self._matched(
                        _describe(observation.condition), sample,
                        observation, now - started,
                        getattr(statement, "line", 0))
                    self._pending = None
                    self._pending_literal = None
                    self._pending_landmarks = ()
                    return index
            # Checked after a sample: a timeout always means samples
            # were taken and none satisfied the condition.
            if expired:
                self._expire_observation(description, bound, statement)
            self._progress(expiry, bound.seconds, description, now)
            self._sleep(self._poll_interval(settled))

    def _expire_interval(self, description, bound, phase):
        """Declare a reactive interval expiry, naming which clock lost."""
        self.events.clear()
        self._emit(_events.OBSERVATION_TIMEOUT,
                   description=description, timeout=bound.seconds,
                   line=phase.line,
                   **{"timeout-source": bound.source})
        raise self._expired(
            "the reactive interval", bound,
            detail=f" with no handler firing{self._gate_note()}",
            rule_id="time.reactive-interval-expired")

    def _expire_observation(self, description, bound, statement):
        """Declare an observation timeout, naming which clock lost."""
        self.events.clear()
        self._emit(_events.OBSERVATION_TIMEOUT,
                   description=description, timeout=bound.seconds,
                   line=getattr(statement, "line", 0),
                   **{"timeout-source": bound.source})
        raise self._expired(
            "the observation timeout", bound, statement,
            f" waiting for {description}{self._gate_note()}",
            rule_id="time.observation-expired")

    def _matched(self, description, sample, observation, elapsed, line):
        """Report a match, naming the evidence that satisfied it.

        A text condition is satisfied by a specific row, and this
        names it. A landmark condition is satisfied by a *variant*,
        and this names that instead, since which rendering actually
        matched is the fact an author needs when several variants
        are being tried.
        """
        row = None
        for candidate in sample.rows:
            if observation.matches_row(candidate):
                row = candidate
                break
        variant = None
        if observation.result is not None and observation.result.matched:
            variant = observation.result.nearest.filename
        self._emit(_events.OBSERVATION_MATCH, description=description,
                   row=row, elapsed=round(elapsed, 3), line=line,
                   variant=variant)

    def _bound(self, node):
        """The effective timeout the timing plan resolved for a node."""
        entry = self._plan.at(node)
        return entry.timeout if entry is not None else self._plan.default

    def _gate(self, node):
        """The stability gate the timing plan resolved for this observation.

        Returns ``None`` when the gate is turned off --
        ``stability=0`` is the author's escape hatch for a screen
        the default threshold would otherwise reject, and turning it
        off has to cost nothing at all, not even the time it would
        otherwise take to establish that the screen has settled.
        """
        entry = self._plan.at(node)
        level = (entry.stability if entry is not None
                 else self._plan.default_stability)
        if level is None or level.value <= 0:
            return None
        return level

    def _settled(self, gate, monitor, sample, now):
        """Whether this sample is one a condition is allowed to be judged on.

        A condition can hold perfectly well against a screen that is
        still being painted, and that is exactly the screen a wait
        must not act on -- so an unsettled sample is skipped rather
        than evaluated, and the wait just keeps looking. A stopped
        machine has no screen to judge at all, and the machine
        channel still needs to be answerable in that case.
        """
        # A landmark sample is judged on the pixels it was matched
        # against -- the same rule as for text, just one level more
        # precise (F65): the gate reads whatever capture actually
        # arrived, and only falls back to the text frame when no
        # capture did.
        reading_of = sample.image if sample.image is not None else (
            sample.frame)
        if gate is None or sample.stopped or not reading_of:
            return True
        # Round timing to the resolution this reading path's noise
        # actually justifies: a text scrape's timing varies by a
        # few milliseconds, while an interpreted framebuffer's
        # varies by hundreds of them, and a window sized to match
        # that noise would otherwise judge two identical runs
        # differently.
        monitor.cadence_step = (
            _stability.TEXT_CADENCE_STEP
            if sample.image is None and not self._recognized_screens
            else _stability.GUI_CADENCE_STEP)
        reading = monitor.observe(reading_of, now=now)
        self._report_guard(monitor, reading)
        if reading.stability is not None:
            # The window was actually observed, so there is a real
            # verdict here, not just an absence of evidence. Which
            # of those two this is decides what an expiry is allowed
            # to do.
            self._measured = True
        if reading.stable:
            return True
        if reading.blind:
            # The sampling cadence cannot even see the screen's
            # decoration at this rate, so the stability gate has no
            # verdict to give -- and a gate with no verdict must not
            # block. Blocking here would not be caution, it would be
            # a deadlock: no later sample can improve on what the
            # poll rate itself forbids, so the wait would spend its
            # entire clock skipping frames it was never able to
            # judge in the first place. Standing down returns this
            # observation to how it behaved before the gate existed
            # at all, which is the honest fallback, and it keeps
            # "the gate never causes a failure on its own" true at
            # every sampling cadence.
            return True
        self._gated = reading
        return False

    def _report_guard(self, monitor, reading):
        """Report, once, what sampling cadence was measured and what it achieves.

        This is emitted at the first sample that actually has a
        cadence to report -- which takes two reads -- rather than
        during preflight, because nothing before the run starts has
        actually read a screen, and this value is measured, never
        just configured. It is only emitted once per run: cadence is
        a property of the host and the reading path, not of
        whichever statement happens to be judged at the time.
        """
        if self._guard_reported:
            return
        cadence = monitor.cadence()
        if cadence is None:
            return
        self._guard_reported = True
        self._emit(
            _events.GUARD_CADENCE,
            cadence=round(cadence, 3),
            window=round(monitor.animation_window(), 2),
            viable=round(_stability.viable_cadence(), 3),
            blind=reading.blind,
            recognized=self._recognized_screens)

    def _gate_note(self):
        """What to add to an expiry message when unsettled samples got skipped.

        A wait can now expire in two ways that look identical from
        the outside: the condition genuinely never matched, or it
        only matched on frames the stability gate skipped over. The
        second case is baffling without an explanation -- the text
        is plainly visible in any screenshot taken at the time -- so
        the failure message says which case happened, and naming the
        animated region is what lets the message actually point at
        the problem instead of just restating that the wait expired.
        """
        reading = self._gated
        if reading is None:
            return ""
        note = "; the screen never settled enough to compare against"
        if reading.stability is None:
            return f"{note} (never sampled densely enough to tell)"
        note += f" (stability {reading.stability:.3f}"
        if reading.animated:
            note += (f", outside a {len(reading.animated)}-"
                     f"{reading.unit} animated region")
        return f"{note})"

    def _pace(self, statement):
        """Let the guest settle before the first key event of this statement.

        Without an agent inside the guest, whether the guest is
        ready for *input* cannot be observed the way its output can,
        so a control plane that starts typing the instant a screen
        finishes painting is asserting something it cannot actually
        know (G1). This is the gap the timing plan already resolved
        for this statement -- it is never recomputed here, so a
        report can name which scope supplied it.

        This is control-plane pacing, not a `delay` verb an author
        writes: the pause is a property of *delivering* input, not a
        step the author sequences explicitly. `send_keys` already
        paces *between* key events; this fills in the missing pause
        before the very first one.

        The gap is taken before delivery happens, so a cancellation
        that arrives during it ends the run cleanly at this
        boundary, rather than in the middle of delivering input.
        """
        gap = self._plan.pacing_at(statement)
        if gap is None or gap.seconds <= 0:
            return
        self._sleep(gap.seconds)
        self._check_clocks(statement)

    def _check_clocks(self, statement=None):
        """Check the timing budgets, and whether a cancellation was requested, at this boundary."""
        if self._cancelled.is_set():
            # "Left as it stands" is the entire promise a
            # cancellation makes, so an open scope is the one thing
            # that has to be called out explicitly: its restore is
            # about to run, and reporting a machine that ends up
            # different from the one the interrupt actually left is
            # only honest if the message says so first.
            left = "is left as it stands"
            if self._scopes:
                left += (", apart from the scoped changes being put "
                         "back: " + ", ".join(active.scope.target
                                              for active in self._scopes))
            raise RunCancelled(
                f"the run was cancelled at step {self._step}; machine "
                f"{self._machine_id} {left}")
        now = self._now()
        run = self._plan.run_deadline
        if (run is not None and self._run_started is not None
                and now - self._run_started > run.seconds):
            raise self._expired("the run deadline", run, statement,
                                rule_id="time.run-deadline-expired")
        budget = self._phase_budget
        if budget is not None and now - self._phase_started > budget.seconds:
            raise self._expired(
                "the phase deadline", budget, statement,
                rule_id="time.phase-deadline-expired")

    def _require_screen(self, observations, node):
        """A screen observation needs a running machine to read."""
        if not self._running and any(observation.channel == "screen"
                                      for observation in observations):
            raise self._error(
                "the machine is not running; the script must start it "
                "first", node, rule_id="machine.not-running")

    @staticmethod
    def _reads(observations):
        """What one sample of this observation set has to capture.

        There are two separate reading paths, and an observation set
        that spans both pays the cost of both: a landmark condition
        needs the plane's pixels, and a text condition needs the
        recognized screen, and these are two separate carrier calls
        (`control_display.DisplayConsole`). A wait with only
        landmark conditions skips the character recognizer entirely,
        which is the whole point on a GUI screen -- matching
        individual glyphs there would be wasted work.

        An observation set with no screen condition at all still
        reads the text screen, exactly as it did before landmarks
        ever existed: that read is what notices a machine that
        stopped underneath a `machine=stopped` wait.
        """
        pixels = any(one.watches_pixels for one in observations)
        text = not pixels or any(
            one.channel == "screen" and not one.watches_pixels
            for one in observations)
        return text, pixels

    def _read(self, text=True, pixels=False):
        """Take one sample of every channel."""
        if not self._running:
            return self._sampled(_Sample((), True))
        unreadable = None
        try:
            with self._console() as console:
                self._recognized_screens = getattr(
                    console, "recognizes_text", False)
                capture = console.framebuffer() if pixels else None
                frame = ((), ())
                if text:
                    try:
                        frame = console.screen(self._font_prefix)
                    except UnreadableScreen as error:
                        # **A capture already in hand survives a text
                        # read that failed**, and on a landmark's own
                        # screen that is the ordinary case: a GUI page
                        # is not an 80x25 text grid, so the character
                        # recognizer refuses it while the pixels a
                        # landmark is matched against still arrived
                        # perfectly. Discarding the sample here would
                        # mean a branching wait that mixes a text arm
                        # with a landmark arm could never fire the
                        # landmark arm.
                        if capture is None:
                            raise
                        unreadable = str(error)
            rows = frame[0]
        except (OSError, ConnectionError):
            # The QEMU process is gone: the guest powered itself off,
            # so the machine's phase must return to `ready` for any
            # later insert/eject and `start`.
            self._mark_stopped()
            return self._sampled(_Sample((), True))
        except PreflightError as error:
            # The adapter reports an unreachable VM as a PREFLIGHT
            # ERROR rather than a transport exception; that sample is
            # the stopped observation (task 5 / AGENTS).
            if error.rule_id != "machine.vm-unreachable":
                raise
            self._mark_stopped()
            return self._sampled(_Sample((), True))
        except UnreadableScreen as error:
            # The guest is painting something the 80x25 text
            # contract cannot describe -- a graphics-mode BIOS
            # splash on every VirtualBox boot, before the guest
            # reaches text mode. This is a sample the wait just
            # looks past, never the end of the run: the machine is
            # healthy and the screen the script is waiting for has
            # simply not been drawn yet.
            return self._sampled(_Sample((), False, (), str(error)))
        return self._sampled(
            _Sample(tuple(_normalize_row(row) for row in rows), False,
                    frame, unreadable,
                    unclear=len(text_recognize.unreadable_cells(frame)),
                    fonts=getattr(frame, "fonts_tried", ()),
                    image=capture))

    def _sampled(self, sample):
        """Keep the latest reading, which the failure report needs."""
        self._last_sample = sample
        return sample

    @staticmethod
    def _cache_root_or_none(context):
        """The resolved cache root directory, or None if it cannot be resolved.

        The adapters keep host-extracted support files there, and a
        run that cannot name the directory simply does without one
        -- re-extracting those files just costs time, never
        correctness, so this must never be the thing that fails a
        run.
        """
        try:
            return _resolve_cache_dir(context)
        except ReliquaryError:
            return None

    def _machine(self):
        """Return the handle **every** carrier call goes through.

        This is one constructor used everywhere, instead of three
        separate ones, because the recorder gets installed right
        here: a caller that built its own handle instead would make
        a carrier call the transcript never sees, which is exactly
        what the `screenshot` verb used to do -- and both codex
        scripts also depend on going through this one path.

        The recorder is passed in at construction time rather than
        assigned onto the object afterward: `Machine` is a frozen
        object, so the assignment this replaced used to raise an
        error on every recorded run, the first time it tried to read
        a screen.
        """
        wrapper = None
        if self._recording_writer is not None:
            wrapper = (lambda session: _transcript.RecordingSession(
                session, self._recording_writer))
        return Machine(self._machine_home,
                       cache=self._cache_root_or_none(self._context),
                       _session_wrapper=wrapper)

    @contextlib.contextmanager
    def _console(self):
        """Yield a console over an identity-verified session.

        Every sample and every input verb opens its own session, so
        no session is ever held open while a statement list is
        running -- QEMU's QMP server only allows one client to be
        connected at a time.
        """
        try:
            with self._machine().console() as console:
                yield console
        except (OSError, ConnectionError) as gone:
            self._note_vm_gone(gone)
            raise
        except PreflightError as gone:
            if gone.rule_id == "machine.vm-unreachable":
                self._note_vm_gone(gone)
            raise

    def _note_vm_gone(self, error):
        """Record the moment the carrier went away, if recording is active.

        The carrier seam itself cannot record this event: the
        session refuses to open in the first place, so the recording
        wrapper that would normally write it never gets created.
        This is the guest powering itself off -- the exact event a
        `wait machine=stopped` is waiting for -- so a capture missing
        this entry can only replay up to the shutdown, and no
        further.
        """
        writer = self._recording_writer
        if writer is not None:
            writer.write_gone(str(error))

    def _mark_stopped(self):
        self._running = False
        try:
            _machines.mark_stopped(self._machine_id, context=self._context)
        except PreflightError:
            pass

    def _requires_running(self, statement):
        if not self._running:
            raise self._error(
                "the machine is not running; the script must start it "
                "first", statement, rule_id="machine.not-running")

    # -- input verbs ---------------------------------------------

    def _action(self, statement, verb, detail=None):
        """Announce an action and remember it as the pending one."""
        self.events.clear()
        self._pending = verb + (f" {detail}" if detail else "")
        self._pending_literal = None
        self._emit(_events.ACTION_START, verb=verb, detail=detail,
                   line=getattr(statement, "line", 0))

    def _completed(self, statement, verb):
        self._emit(_events.ACTION_END, verb=verb,
                   line=getattr(statement, "line", 0))
        self._pending = None

    def _enter(self, statement):
        text = _render_literal(statement.arguments[0], self._bindings)
        self._note_secret(statement.arguments[0])
        self._action(statement, "enter", repr(text))
        self._requires_running(statement)
        self._pace(statement)
        with self._console() as console:
            console.send_text(text, True)
        self._completed(statement, "enter")

    def _type(self, statement):
        text = _render_literal(statement.arguments[0], self._bindings)
        self._note_secret(statement.arguments[0])
        self._action(statement, "type", repr(text))
        self._requires_running(statement)
        self._pace(statement)
        with self._console() as console:
            console.send_text(text, False)
        self._completed(statement, "type")

    def _note_secret(self, literal):
        """Record that a secret was entered, so later output can suppress it.

        Once a secret reaches the guest, automatic failure
        screenshots are suppressed for the rest of the run; an
        explicitly requested screenshot is the author's own
        deliberate choice and is never suppressed. Recording stops
        too: a raw captured screen carries the typed password in
        plain text, and a frame is a grid of cells, not a line of
        text, so the event stream's redaction cannot reach into it.
        """
        if self._secret_entered or not self._secret_values:
            return
        if not hasattr(literal, "parts"):
            return
        for part in literal.parts:
            key = getattr(part, "key", None)
            if key and self._property_bindings and \
                    key in self._property_bindings.secret_keys:
                self._secret_entered = True
                writer = self._recording_writer
                if writer is not None:
                    writer.stop(
                        "a bound secret reached the guest; recording "
                        "stopped for the rest of the run")
                return

    def _press(self, statement):
        keys = statement.arguments
        self._action(statement, "press", " ".join(keys))
        combos = []
        for spelling in keys:
            try:
                combos.append(resolve_key(spelling))
            except StaticError as unknown:
                raise self._error(str(unknown), statement,
                                  rule_id=unknown.rule_id) from None
        self._requires_running(statement)
        self._pace(statement)
        with self._console() as console:
            console.send_keys(combos)
        self._completed(statement, "press")

    def _select(self, statement):
        item = _render_literal(statement.arguments[0], self._bindings)
        exclude = ((_render_literal(statement.exclude, self._bindings),)
                   if statement.exclude else ())
        detail = repr(item)
        if exclude:
            detail += f" (exclude: {exclude[0]!r})"
        self._action(statement, "select", detail)
        self._requires_running(statement)
        self._pace(statement)
        with self._console() as console:
            console.cursor_menu_select(
                item, timeout=self._bound(statement).seconds,
                exclude=exclude)
        self._completed(statement, "select")

    def _resolve_spot(self, statement, landmark):
        """The spot a `click` targets: the one named, or the single spot if there is only one (F66).

        Preflight already proved this succeeds for a literal `spot=`
        value (or for no `spot=` at all -- the default of using the
        single spot, which is only legal when exactly one spot
        exists). An interpolated `spot=` value is instead checked
        here, for the same reason a `$property` media reference
        resolves at runtime rather than preflight: its actual value
        cannot be known before binding happens.
        """
        if statement.spot is not None:
            name = _render_literal(statement.spot, self._bindings)
            try:
                return landmark.spots[name]
            except KeyError:
                raise self._error(
                    f"@{landmark.name} has no spot named {name!r} "
                    f"(has: {', '.join(sorted(landmark.spots)) or 'none'})",
                    statement, rule_id="landmark.spot-unknown") from None
        return next(iter(landmark.spots.values()))

    def _click(self, statement):
        """Find a landmark, then deliver a click at one of its spots.

        This has two halves, like `select`: the *search* reuses
        `wait`'s exact machinery (`_observation`/`_arm`/`_observe`),
        since a `click`'s target is a real landmark pixel match, not
        a text scan -- a timeout here names the statement's own
        clock, with no pointer event ever having been delivered. The
        *delivery* -- pacing, then the combined click-and-park
        motion -- only happens once the search has actually matched.
        """
        name = statement.arguments[0]
        condition = statement.conditions[0]
        description = _describe(condition)
        observations = [self._observation(condition, None)]
        bound = self._arm(statement, observations, description)
        self._observe(observations, bound, description, statement)
        landmark = self._landmarks[name]
        spot = self._resolve_spot(statement, landmark)
        detail = f"@{name}"
        if statement.spot is not None:
            detail += (f" spot="
                       f"{_render_literal(statement.spot, self._bindings)!r}")
        self._action(statement, "click", detail)
        self._pace(statement)
        with self._console() as console:
            console.click(spot.x, spot.y,
                          _landmarks.park_position(landmark.width,
                                                   landmark.height))
        self._completed(statement, "click")

    # -- supporting operations -----------------------------------

    def _screenshot(self, statement):
        name = (statement.arguments[0] if statement.arguments
                else f"step-{self._step}")
        name = validate_screenshot_name(name)
        self._action(statement, "screenshot", name)
        self._requires_running(statement)
        # There is no run directory any more (D36), so an author's
        # screenshot is kept with the machine it was taken from.
        # This goes through `_machine()` like every other carrier
        # call, so a recorded run's transcript captures it too.
        self._machine().screenshot(name)
        self._completed(statement, "screenshot")

    def _insert(self, statement):
        slot, (kind, name) = statement.arguments
        if kind == "property":
            try:
                name = self._bindings[name]
            except KeyError:
                raise _PropertyUnbound(name) from None
        self._action(statement, "insert", f"{slot} @{name}")
        # The event stream carries the fetch's transfer/verify
        # events (an insert can pull down hundreds of megabytes, and
        # silence there would read as a hang); the cancel event lets
        # that fetch be interrupted cleanly.
        self._machine_change(
            statement, _machines.insert_media, slot, name,
            events=self.events, cancelled=self._cancelled)
        self._completed(statement, "insert")

    def _eject(self, statement):
        slot = statement.arguments[0]
        self._action(statement, "eject", slot)
        self._machine_change(statement, _machines.eject_media, slot)
        self._completed(statement, "eject")

    def _set_boot(self, statement):
        keys = statement.arguments
        self._action(statement, "set-boot", " ".join(keys))
        self._machine_change(statement, _machines.set_boot_order, keys)
        self._completed(statement, "set-boot")

    def _machine_change(self, statement, operation, *arguments, **options):
        """Apply a persistent machine-state change, naming the statement if it fails.

        ``options`` are passed through to the operation unchanged,
        so a change that fetches media can be given the run's event
        stream and cancel event, without every other kind of change
        having to grow parameters it has no use for. A
        ``RunCancelled`` raised inside is deliberately not caught
        here: that means the run is stopping, not that this
        particular change failed.
        """
        try:
            operation(self._machine_id, *arguments, context=self._context,
                      **options)
        except RunCancelled:
            raise
        except ReliquaryError as exc:
            raise self._error(str(exc), statement,
                              rule_id=exc.rule_id) from exc

    def _start(self, statement):
        self._action(statement, "start")
        _machines.start_machine(
            self._machine_id, display=self._display, context=self._context,
            events=self.events, cancelled=self._cancelled)
        self._running = True
        self._completed(statement, "start")

    def _stop(self, statement):
        self._action(statement, "stop")
        _machines.stop_machine(self._machine_id, context=self._context)
        self._running = False
        self._completed(statement, "stop")

    # -- run-scoped HTTP -----------------------------------------

    def _http_control(self, statement):
        command = statement.arguments[0]
        self._action(statement, "http", command)
        if command == "start":
            self._http_start(statement)
        elif command == "stop":
            self._http_stop()
        else:
            raise self._error(f"unknown http action: {command}",
                              statement,
                              rule_id="http.unknown-action")
        self._completed(statement, "http")

    def _http_start(self, statement):
        self._http_stop()
        responses = self._http_responses(statement)
        plan = self._script.http
        port_min = int(plan.port_min) if plan and plan.port_min else 8000
        port_max = int(plan.port_max) if plan and plan.port_max else 9000
        service = self._http_service_factory(responses, port_min, port_max)
        try:
            service.start()
        except RunFailure as exc:
            raise self._error(str(exc), statement,
                              rule_id=exc.rule_id) from exc
        self._http = service
        self._bindings.update({
            "rlq.http.ip": service.guest_ip,
            "rlq.http.port": str(service.port),
            "rlq.http.url": service.url,
        })

    def _http_stop(self):
        if self._http is not None:
            self._http.stop()
            self._http = None
        for key in ("rlq.http.ip", "rlq.http.port", "rlq.http.url"):
            self._bindings.pop(key, None)

    def _http_responses(self, statement):
        selected = {}
        if self._script.http is not None:
            declared = {content.name: content
                        for content in self._script.http.contents}
            names = statement.arguments[1:] or tuple(declared)
            selected.update((name, declared[name]) for name in names)
        for content in statement.contents:
            selected[content.name] = content
        responses = []
        paths = set()
        for content in selected.values():
            response = self._http_response(content)
            if response.path in paths:
                raise self._error(
                    f"http content produces duplicate path: "
                    f"{response.path}", statement,
                    rule_id="http.duplicate-path")
            paths.add(response.path)
            responses.append(response)
        return tuple(responses)

    def _http_response(self, content):
        path = _literal(content.path)
        body = _render_literal(content.body, self._bindings)
        return _HttpResponse(
            content.name, path, body.encode("utf-8"))


def _walk(script):
    """Yield every statement of a script, including statements inside nested bodies.

    The validation and timing layers each walk the tree too, but
    each of them threads its own scope context, and neither can
    import this module. This is the plain traversal used by this
    module.

    A ``with`` head is yielded as the action it is written as, so a
    scoped `insert` answers to the same preflight rules as an
    ordinary written `insert`; the pseudo-verb ``boot`` is the
    third, head-only case.
    """

    def statements(items, handlers=()):
        for handler in handlers:
            yield from statements(handler.statements)
        for item in items:
            units = getattr(item, "units", None)
            if units is not None:
                yield item.action
                yield from statements(units)
                continue
            if not hasattr(item, "verb"):
                continue              # a phase, reached below
            yield item
            yield from statements((), item.handlers)

    yield from statements(script.statements)
    for phase in script.phases:
        yield from statements(phase.statements, phase.handlers)


_REMOVABLE_MEDIA = frozenset({"floppy", "cdrom"})

#: The two absolute-position pointer devices (D127): `click` accepts
#: either, since both report a screen position rather than relative
#: motion, unlike `emulated-mouse` or `virtual-mouse`.
_ABSOLUTE_POINTERS = frozenset({"emulated-tablet", "virtual-tablet"})


def _no_such_media(name, namespace):
    """The diagnostic for a media reference the namespace lacks."""
    close = difflib.get_close_matches(name, namespace.media, n=3,
                                      cutoff=0.6)
    hint = ("; did you mean " + ", ".join(repr(other) for other in close)
            if close else "")
    return f"no media named {name!r} in the active source{hint}"


def _no_such_font(name, namespace):
    """The diagnostic for a font reference the namespace lacks."""
    close = difflib.get_close_matches(name, namespace, n=3, cutoff=0.6)
    hint = ("; did you mean " + ", ".join(repr(other) for other in close)
            if close else "")
    return f"no font named {name!r} in the active source{hint}"


def _no_such_landmark(name, namespace):
    """The diagnostic for a landmark reference the namespace lacks."""
    close = difflib.get_close_matches(name, namespace, n=3, cutoff=0.6)
    hint = ("; did you mean " + ", ".join(repr(other) for other in close)
            if close else "")
    return f"no landmark named {name!r} in the active source{hint}"


def _observed(script):
    """Yield every node that carries an observation condition.

    ``_walk`` above is the plain statement traversal, and it drops
    the handlers it descends through. A condition sits on the
    handler itself just as often as on a `wait`, so this needs its
    own separate walk rather than generalizing `_walk` to yield both
    kinds. `click` (F66) carries a condition too -- its search is a
    landmark match, just like `wait`'s -- so it is included alongside
    `wait` here instead of needing a second walk for the same three
    landmark checks.
    """

    def walk(items, handlers=()):
        for handler in handlers:
            yield handler
            yield from walk(handler.statements)
        for item in items:
            units = getattr(item, "units", None)
            if units is not None:
                yield from walk(units)
                continue
            if not hasattr(item, "verb"):
                continue              # a phase, reached below
            if item.verb in ("wait", "click"):
                yield item
            yield from walk((), item.handlers)

    yield from walk(script.statements)
    for phase in script.phases:
        yield from walk(phase.statements, phase.handlers)


def _pool_kind(name, context, want):
    """Which *other* kind in the one ``@`` pool holds ``name``, if any.

    The `@` pool is one shared namespace across media, fonts, and
    landmarks, so a reference that misses its own kind has usually
    matched a different kind instead -- and saying *which* one is
    the difference between an error that says "no landmark named
    'freedos'" and one that says "'freedos' is a media". This is
    only consulted after a miss, so an ordinary successful run never
    resolves a namespace it had no use for, and never re-resolves
    the kind that just failed to match.
    """
    lookups = {
        "media": lambda: load_namespace(context).media,
        "font": lambda: _fonts.load_font_namespace(context),
        "landmark": lambda: _landmarks.load_landmark_namespace(context),
    }
    try:
        for kind, holds in lookups.items():
            if kind != want and name in holds():
                return kind
    except ReliquaryError:
        # This lookup is only being done to *improve* a refusal
        # that has already happened. A second failure that occurs
        # while looking must not replace the original one.
        return None
    return None


def _wrong_kind(name, want, used_for, context, statement, script_path):
    """The refusal for a `@name` that resolved to the wrong kind, or ``None`` if nothing else holds that name.

    This is one rule applied in three directions: how a `@name` is
    used decides which kind it must be, so a reference that actually
    landed on a different kind in the same pool is told exactly
    what it hit and where it was used, instead of just being
    reported as an undeclared name.
    """
    other = _pool_kind(name, context, want)
    if other is None:
        return None
    return ScriptPreflightError(
        f"@{name} is a {other}, and a {want} is what {used_for}; the "
        "one @ pool holds all three kinds, so the use decides which "
        "is meant", statement=statement, path=script_path,
        rule_id=f"{want}.wrong-kind")


@dataclasses.dataclass(frozen=True)
class _Resolved:
    """What preflight already settled, that a run then needs to have in hand.

    Both fields hold answers a sample must never go looking for
    itself: the landmark declaration is read off disk, and the
    capture format comes from the carrier seam, and either one
    arriving mid-run instead of at preflight would mean a refusal
    could happen after the first guest input (G3).
    """

    landmarks: dict = dataclasses.field(default_factory=dict)
    capture_format: str = None


def _capture_format(machine_state):
    """The pixel format the machine's driving control plane captures in.

    The first declared control plane is the one that drives the
    session (F63), so it is the one asked here. Returning ``None``
    -- meaning the plane reads no framebuffer at all -- is what
    turns a landmark condition into a named refusal below.
    """
    plane = (machine_state.get("control-planes")
             or ["agentless-display"])[0]
    backend = machine_state.get("backend")
    if not backend:
        # A state with no backend recorded cannot be asked at all,
        # but the plane's name is still an honest half of the
        # answer, so it is still returned.
        return plane, None
    return plane, _backends.adapter(backend).capture_format(plane)


def _preflight_spot(node, landmark, script_path):
    """Refuse an invalid `click` `spot=` before the machine starts (F66).

    A landmark that declares exactly one spot needs no `spot=`
    modifier at all; a landmark with more spots (or none) makes
    writing `spot=` required, and a name the landmark declaration
    does not actually have is refused by name. An interpolated
    `spot=` value cannot be checked here -- its actual value cannot
    be known before binding happens, the same reason a `$property`
    media reference is resolved later rather than here -- so that
    case is left to runtime (`_ScriptEngine._resolve_spot`).
    """
    spot = node.spot
    if spot is not None and spot.interpolated:
        return
    if spot is None:
        if len(landmark.spots) != 1:
            raise ScriptPreflightError(
                f"click @{landmark.name} needs spot=: the landmark "
                f"declares {len(landmark.spots)} spots and the lone-spot "
                "default only applies where exactly one exists",
                statement=node, path=script_path,
                rule_id="landmark.spot-required")
        return
    name = spot.text
    if name not in landmark.spots:
        raise ScriptPreflightError(
            f"@{landmark.name} has no spot named {name!r} (has: "
            f"{', '.join(sorted(landmark.spots)) or 'none'})",
            statement=node, path=script_path,
            rule_id="landmark.spot-unknown")


def _preflight_landmarks(script, machine_state, script_path, context):
    """Bind every `@name` a condition watches, or refuse by name (F65).

    Three refusals apply to every landmark condition, and all of
    them happen before the machine is touched at all (G3): the name
    resolves to nothing; the name resolves to a different kind in
    the one `@` pool, which is the kind check done at binding time
    -- a media or font name used in condition position names both
    the use and the kind involved; and the machine's driving control
    plane captures no framebuffer at all, which is a capability
    check done at the *condition's* granularity rather than the
    whole script's, since a script that watches no landmark makes no
    demand on the plane at all. `click` (F66) adds three more checks
    that apply only to it: the machine's pointer device
    (`devices.pointer0`, D124) must be `tablet`; the driving plane
    must be able to deliver a pointer event even if it captures one (a
    plane can have one capability without the other); and the `spot=`
    check above.
    """
    namespace = None
    resolved = {}
    plane, capture = None, None
    pointing_device, pointer_capable = None, None
    for node in _observed(script):
        for condition in node.conditions:
            if condition.kind != "landmark":
                continue
            name = condition.value
            if namespace is None:
                namespace = _landmarks.load_landmark_namespace(context)
                plane, capture = _capture_format(machine_state)
            if name not in namespace:
                raise _wrong_kind(
                    name, "landmark", "a screen condition watches",
                    context, node, script_path) or ScriptPreflightError(
                    _no_such_landmark(name, namespace), statement=node,
                    path=script_path, rule_id="landmark.unknown")
            if capture is None:
                raise ScriptPreflightError(
                    f"the {plane!r} control plane captures no "
                    f"framebuffer, so the landmark condition @{name} "
                    "cannot be watched on this machine",
                    statement=node, path=script_path,
                    rule_id="machine.plane-no-framebuffer")
            resolved[name] = namespace[name]
            if node.verb != "click":
                continue
            if pointer_capable is None:
                pointing_device = machine_state.get("devices", {}).get(
                    "pointer0", {}).get("value", "emulated-mouse")
                pointer_capable = _backends.adapter(
                    machine_state["backend"]).pointer_capable(plane)
            if pointing_device not in _ABSOLUTE_POINTERS:
                raise ScriptPreflightError(
                    "click needs an absolute pointing device and this "
                    f"machine's is {pointing_device!r}; declare "
                    '"devices": {"pointer0": "emulated-tablet"} (no '
                    'guest driver needed) or "virtual-tablet" '
                    "(paravirtualized) in the blueprint",
                    statement=node, path=script_path,
                    rule_id="machine.pointing-device-not-tablet")
            if not pointer_capable:
                raise ScriptPreflightError(
                    f"the {plane!r} control plane cannot deliver a "
                    f"pointer event, so the click @{name} cannot be "
                    "delivered on this machine",
                    statement=node, path=script_path,
                    rule_id="machine.plane-no-pointer-input")
            _preflight_spot(node, resolved[name], script_path)
    return _Resolved(resolved, capture)


def _preflight_machine_rules(script, machine_state, script_path,
                             context=None):
    """Fail before any guest input when a script names something the machine or the namespace does not define.

    Returns the :class:`_Resolved` bundle the run then holds onto:
    the landmark declarations it will match against, and the
    capture format of the plane driving it, both settled here so no
    sample has to resolve an asset itself later.

    Two of the machine rules preflight is responsible for
    (script-spec.md, "Validation and preflight"): a media reference
    naming no media the namespace defines, and an undeclared boot
    drive or slot.

    ``insert``, ``eject``, and ``set-boot`` never create or remove a
    drive -- the blueprint alone defines a machine's drive topology
    -- so every named slot must already exist in the machine's
    state. ``insert`` and ``eject`` additionally require a floppy or
    cdrom slot. A ``with`` head is checked as whichever action it
    actually spells, with the scoped ``boot`` prefix following the
    same rule as ``set-boot``: every key must name a declared drive.

    A ``$property`` media argument is resolved at binding, not here,
    so only a literal ``@name`` is checked here. The media namespace
    is loaded lazily, so a script that inserts nothing by name never
    pays the cost of loading it. The slot is checked before the
    media on the same statement, in the order the author actually
    wrote them.

    There is a third rule too: a ``font`` statement naming no font
    the source defines (F61) -- checked the same way, only for a
    literal ``@name``, with its own namespace loaded lazily and
    separately from media's, since a script that names no font never
    has to resolve one.
    """
    devices = machine_state.get("devices", {})
    namespace = None
    font_namespace = None
    for statement in _walk(script):
        if statement.verb == "font":
            for kind, name in statement.arguments:
                if kind != "media":
                    continue
                if font_namespace is None:
                    font_namespace = _fonts.load_font_namespace(context)
                if name not in font_namespace:
                    raise _wrong_kind(
                        name, "font", "the font statement names",
                        context, statement,
                        script_path) or ScriptPreflightError(
                        _no_such_font(name, font_namespace),
                        statement=statement, path=script_path,
                        rule_id="font.unknown")
            continue
        if statement.verb in ("insert", "eject"):
            slots = (statement.arguments[0],)
            removable_only = True
        elif statement.verb in ("set-boot", "boot"):
            slots = statement.arguments
            removable_only = False
        else:
            continue
        for slot in slots:
            drive = devices.get(slot)
            if drive is None:
                raise ScriptPreflightError(
                    f"the machine declares no drive {slot}",
                    statement=statement, path=script_path,
                    rule_id="machine.slot-not-declared")
            if "medium" not in drive:
                raise ScriptPreflightError(
                    f"{slot} is not a drive slot", statement=statement,
                    path=script_path, rule_id="machine.slot-not-declared")
            if (removable_only
                    and drive.get("medium") not in _REMOVABLE_MEDIA):
                raise ScriptPreflightError(
                    f"{slot} is not a removable drive slot "
                    "(insert/eject are floppy and cdrom only)",
                    statement=statement, path=script_path,
                    rule_id="machine.slot-not-removable")
        if statement.verb != "insert":
            continue
        kind, name = statement.arguments[1]
        if kind != "media":
            continue
        if namespace is None:
            namespace = load_namespace(context)
        if name not in namespace.media:
            raise _wrong_kind(
                name, "media", "insert mounts", context, statement,
                script_path) or ScriptPreflightError(
                _no_such_media(name, namespace),
                statement=statement, path=script_path,
                rule_id="media.unknown")
    return _preflight_landmarks(script, machine_state, script_path,
                                context)


def execute_script(script, *, machine_id, context=None, display=False,
                   script_path=None, bindings=None, events=None,
                   record=None):
    """Execute a parsed Script against a cached machine.

    The machine state the script's ``machine`` header expects is
    established first: the default ``running`` starts a ready
    machine, while ``stopped`` requires a stopped machine and
    leaves starting to the script itself.  The machine is left in
    whatever state the last executed step produced.

    ``events`` is the run's live :class:`~reliquary.events.EventStream`;
    nothing is written to disk (D36).

    Returns a ``(final_phase, machine_phase)`` pair reporting the
    script phase and machine phase the run finished in.
    """
    if not script.phases and not script.statements:
        try:
            phase = _machines.load_machine_state(
                machine_id, context).get("phase", "-")
        except PreflightError:
            phase = "-"
        return "-", phase

    resolved = _preflight_machine_rules(
        script, _machines.load_machine_state(machine_id, context),
        script_path, context)
    record_pace = None
    recording_writer = None
    if record is not None:
        record_pace = _RECORD_PACE
        recording_writer = _transcript._TranscriptWriter(
            record, pace=record_pace,
            **_transcript.script_identity(script_path))
        recording_writer.open()
    engine = _ScriptEngine(
        script, machine_id, context,
        _machines.machine_dir_path(machine_id, context),
        events=events, script_path=script_path, bindings=bindings,
        record_pace=record_pace, recording_writer=recording_writer,
        landmarks=resolved.landmarks,
        capture_format=resolved.capture_format)
    try:
        with _cancel_on_interrupt(engine):
            engine.run(display=display)
        _record_outcome(recording_writer, None, engine)
        return engine.final_phase, engine.machine_phase
    except ReliquaryError as failure:
        _record_outcome(recording_writer, failure, engine)
        raise
    finally:
        if recording_writer is not None:
            recording_writer.close()


def _record_outcome(writer, failure, engine):
    """Tell the transcript what the run concluded, if recording is active.

    The carrier seam itself cannot show this: a run that reached its
    `finish` and one that expired against the same screens make
    exactly the same carrier calls, and which of those actually
    happened is decided above the seam. A capture is checked against
    this recorded outcome, so a fixture of a run that *failed* works
    exactly like any other fixture.
    """
    if writer is None:
        return
    if failure is None:
        writer.write_outcome("ok", phase=engine.final_phase)
        return
    writer.write_outcome("failed", rule=failure.rule_id,
                         phase=engine.final_phase)


@contextlib.contextmanager
def _cancel_on_interrupt(engine):
    """Turn Ctrl-C into a cancellation the runner can end cleanly on.

    A foreground Ctrl-C requests a stop; the run ends at the next
    event boundary with a ``cancelled`` terminal event and exit code
    ``5``, leaving the machine as-is (with no implicit teardown).
    Installing a signal handler is what makes the stop land *at a
    boundary*, instead of wherever the interrupt happened to arrive
    -- an input delivery already in flight still completes.

    Signal handlers can only be installed on the main thread; a run
    driven from any other thread simply keeps Python's default
    behavior, and the resulting ``KeyboardInterrupt`` is translated
    below instead.

    A *second* Ctrl-C restores the default signal handler and
    interrupts immediately. The graceful stop is meant to be a
    promise, not a trap: without this escalation, the only way out
    of a stop that will not land would be killing the terminal.
    """
    installed = False
    previous = None

    def _interrupt(*_):
        if engine.cancelled:
            # Asked twice: the caller wants out immediately, not at
            # the next boundary. Hand the signal back to Python and
            # let this one raise normally.
            with contextlib.suppress(ValueError, OSError, TypeError):
                signal.signal(signal.SIGINT, previous)
            raise KeyboardInterrupt
        engine.cancel()

    try:
        previous = signal.signal(signal.SIGINT, _interrupt)
        installed = True
    except (ValueError, AttributeError, OSError):
        pass
    try:
        yield
    except KeyboardInterrupt as interrupt:
        raise RunCancelled(
            "the run was cancelled; the machine is left as it stands"
        ) from interrupt
    finally:
        if installed:
            with contextlib.suppress(ValueError, OSError, TypeError):
                signal.signal(signal.SIGINT, previous)


def _existing_machine(*, machine=None, blueprint=None, context=None):
    """Resolve a selector to an existing machine, or None if one should be created.

    This never creates a machine itself: the decision to create one
    is deferred so that property binding can run before it does (G3
    -- binding always precedes machine creation). The blueprint
    lookup is scoped to this invocation's own source, so a
    same-named machine from a different project is never mistakenly
    adopted.
    """
    if machine is None and blueprint is None:
        raise StaticError(
            "select a machine with --blueprint or --machine",
            rule_id="machine.no-selector")
    if machine is not None:
        return _machines.resolve_machine(
            machine=machine, blueprint=blueprint, context=context)
    if _machines.machines_for_blueprint(blueprint, context):
        return _machines.resolve_machine(
            blueprint=blueprint, context=context)
    return None


def _blueprint_component(blueprint, context):
    """The blueprint's machine component, read from the blueprints directory.

    This mirrors ``create_machine``'s own resolution, so the
    parameters and scripts map read here are exactly the ones a
    later create call would use -- which means seeding nothing on
    its own (D88). Returns None when the name resolves to no
    component; a later create call then raises the missing-blueprint
    error, naming the seed command for wherever the codex ships that
    name.
    """
    namespace = load_namespace(context)
    return namespace.machines.get(blueprint)


def _resolve_script_stem(label, scripts_map):
    """Map a label through the blueprint scripts map, else use bare stem."""
    if not isinstance(label, str) or not label.strip():
        raise StaticError("script label must be a non-empty string",
                          rule_id="name.label-empty")
    label = label.strip()
    if label in (".", "..") or "/" in label or "\\" in label:
        raise StaticError(
            f"script label must be a bare name, got: {label!r}",
            rule_id="name.label-not-bare")
    if label.lower().endswith(".rlqs"):
        raise StaticError(
            f"script label must omit the .rlqs suffix, got: "
            f"{label!r}", rule_id="name.label-has-suffix")
    if isinstance(scripts_map, dict) and label in scripts_map:
        return scripts_map[label]
    return label


def _ensure_script_path(stem, context=None):
    """Resolve ``stem`` from the scripts directory, without seeding anything.

    The scripts directory is the sole source (D88); resolution and
    its error messages both come from ``locate_script``, which names
    the seed command for wherever the codex ships that script.
    """
    return locate_script(stem, context=context)


def _blueprint_invocation(state, context):
    """The blueprint's `scripts` and `parameters`, read live from the blueprint file.

    Neither one configures what a machine actually *is*: `parameters`
    feed script binding, and `scripts` name which instructions to
    run, so both sit outside the machine's shape baseline entirely
    -- no state, no `apply` step, no digest involvement
    (docs/spec/instance-model.md) -- and both are read fresh from
    the blueprint file on every run, rather than from the machine's
    snapshot. Recording the label map into the machine snapshot
    instead would have meant a machine could not run a script label
    its blueprint gained after the machine was created, not until an
    `apply` it had no shape-related reason to need -- and resolving
    that asymmetry is exactly what this does (D101).

    A machine whose blueprint file has since moved contributes
    neither `scripts` nor `parameters` -- its own recorded state
    remains the authority for shape.
    """
    source = state.get("blueprint-source")
    if not source or not os.path.exists(source):
        return {}, {}
    try:
        document = load_document(source)
    except (OSError, StaticError, PreflightError):
        return {}, {}
    name = state.get("blueprint")
    component = document.machines.get(name)
    if component is None and len(document.machines) == 1:
        component = next(iter(document.machines.values()))
    if component is None:
        return {}, {}
    return dict(component.scripts), dict(component.parameters)


def run_script(label, *, blueprint=None, machine=None, context=None,
               display=False, properties=None, properties_file=None,
               progress="auto", dry_run=False, expect=None,
               record=None):
    """Resolve ``label``, ensure a machine exists, run it, and return its output.

    Looks up ``label`` in the machine's blueprint ``scripts`` map
    first; when it is absent there, treats ``label`` as a bare
    script stem under ``scripts/``. With ``--blueprint`` given and no
    machine yet, creates one. Declared properties bind before the
    machine starts, from ``properties`` (explicit ``--property``
    values), the blueprint parameters, the environment, the
    properties file, or -- on a terminal, under an interactive
    ``progress`` mode -- an interactive ask.

    A run **returns its output** and stores nothing itself (D36):
    the returned :class:`ScriptRun` carries the whole event stream,
    which ``progress`` also renders live (``auto | pretty | plain |
    jsonl``). A failure raises using the appropriate error class; a
    Ctrl-C ends the run at the next event boundary and raises
    :class:`~reliquary.errors.RunCancelled`.

    ``expect`` **checks the run against what it should leave
    behind**: a mapping from a machine-variable key to the value the
    run is expected to have `set`. Every key is read once the run
    completes, and any key that is unset or holds something else
    raises :class:`~reliquary.errors.RunFailure`, naming the key,
    the wanted value, and the value it actually got. Without
    ``expect``, the caller has to read the variable afterward and
    connect the dots themselves -- an unset variable and a machine
    that never ran read identically, on purpose, so a script that
    failed to reach its `set` fails silently. ``expect`` turns that
    silence into a loud failure, in one call instead of two.

    This is a **postcondition check, not a wait**, which is the most
    this function can honestly promise: this function blocks until
    the run finishes, and only a running script's `set` writes a
    variable, so by the time this function returns, the value is
    already final and there is nothing left to poll for. A real wait
    belongs where the setter is a different actor -- another thread
    running this same call, or a detached run -- which is what
    :func:`~reliquary.machines.wait_machine_var` is for.

    ``dry_run=True`` returns a :class:`~reliquary.machines.DryRun`
    instead -- a document, not a stream -- having started no machine
    and delivered no guest input at all. This is the only mode where
    the selector is optional, because whether one is given decides
    which tier of checking applies; ``display``, a non-default
    ``progress``, ``expect``, and ``record`` are all refused together
    with it -- a plan has no window to show, no stream to render, no
    run whose outcome could be checked, and no screens to capture.
    """
    if dry_run:
        if expect:
            raise StaticError(
                "--expect contracts what a run leaves behind, and "
                "--dry-run runs nothing; there is no variable to read",
                rule_id="progress.expect-on-a-dry-run")
        if display:
            raise StaticError(
                "--display shows a running machine's window, and "
                "--dry-run starts none",
                rule_id="progress.display-on-a-dry-run")
        if progress not in (None, "auto"):
            raise StaticError(
                "--dry-run returns a document, not a stream, so there "
                "is no progress to render; read it with --json",
                rule_id="progress.stream-on-a-document")
        if record is not None:
            raise StaticError(
                "--record captures the screens a run reads, and "
                "--dry-run starts no machine and reads none; there "
                "would be nothing to write",
                rule_id="progress.record-on-a-dry-run")
        return _dry_run_script(
            label, blueprint=blueprint, machine=machine, context=context,
            properties=properties, properties_file=properties_file)
    # Resolve to an existing machine (or None) without creating, so
    # declared properties bind before any machine or media is made.
    machine_id = _existing_machine(
        machine=machine, blueprint=blueprint, context=context)
    if machine_id is not None:
        state = _machines.load_machine_state(machine_id, context)
        scripts_map, parameters = _blueprint_invocation(state, context)
    else:
        component = _blueprint_component(blueprint, context)
        scripts_map = dict(component.scripts) if component is not None else {}
        parameters = (dict(component.parameters)
                      if component is not None else {})
    stem = _resolve_script_stem(label, scripts_map)
    script_path = _ensure_script_path(stem, context=context)
    script = load_script(script_path)
    # `plain` and `jsonl` never prompt, so a missing value fails
    # preflight before the machine starts rather than hanging a
    # program on a question it cannot see.
    bindings = bind_properties(
        script, parameters=parameters, explicit=properties,
        properties_file=properties_file, context=context,
        asker=console_asker() if _interactive(progress) else None)

    events = stream_for(progress, redact=_redactor(bindings))
    try:
        # Binding passed: now create the machine if the blueprint had
        # none.
        created = machine_id is None
        if created:
            machine_id = _machines.create_machine(
                blueprint, context=context, properties=properties,
                properties_file=properties_file, events=events)
        final_phase, machine_phase = execute_script(
            script, machine_id=machine_id, context=context, display=display,
            script_path=script_path, bindings=bindings, events=events,
            record=record)
        _check_expectations(expect, machine_id, context)
        return ScriptRun(
            machine_id=machine_id,
            script_path=script_path,
            created_machine=created,
            final_phase=final_phase,
            machine_phase=machine_phase,
            events=events.events,
        )
    finally:
        events.close()


def _check_expectations(expect, machine_id, context):
    """Check the finished run against what it was expected to leave behind.

    Each key is read once, in the caller's own key order, so a
    diagnostic is reproducible, and the *first* mismatch raises
    immediately: a run that missed its first postcondition has
    already gone wrong, and listing the rest of the mismatches would
    just report downstream consequences alongside the actual cause.

    Nothing here polls. The run is already over, so every variable
    it was ever going to set has been set by now (D90) -- an unset
    key at this point means the script never actually reached that
    `set`, which is exactly the kind of silence this function exists
    to break.
    """
    for key, wanted in (expect or {}).items():
        got = _machines.get_machine_var(
            key, machine=machine_id, context=context)
        if got == wanted:
            continue
        raise RunFailure(
            f"the run did not leave {key!r} as expected: wanted "
            f"{wanted!r}, "
            + ("it is unset" if got is None else f"got {got!r}"),
            rule_id="script.expectation-unmet")


def _redactor(bindings):
    """A redaction function over the bound secrets, or ``None``."""
    values = [value for value in (bindings.secret_values() if bindings
                                  else ()) if value]
    if not values:
        return None

    def redact(text):
        for value in values:
            if value in text:
                text = text.replace(value, "\u00absecret\u00bb")
        return text

    return redact


def _dry_run_script(label, *, blueprint=None, machine=None, context=None,
                    properties=None, properties_file=None):
    """Evaluate what a script run would do, without committing any of it.

    This is the script half of the dry run, whose rule is stated in
    docs/spec/cli.md. It stays read-only throughout: it seeds
    nothing, creates no machine, executes no guest step, never
    prompts, and never reads a secret's actual value -- it stops
    before the machine would start and before any statement would
    reach a guest.

    **The selector decides which checking tier applies**, which is
    why it is optional here even though it is required for a real
    run. Without one, ``label`` is treated as a bare script stem and
    every legality rule is checked. With ``blueprint=`` or
    ``machine=`` given, it resolves through that blueprint's
    ``scripts`` map first, and the machine-specific rules are
    checked as well -- these are the two modes script-spec.md
    specifies, kept distinct here rather than collapsed into one.
    """
    machine_id = None
    scripts_map = {}
    parameters = {}
    if machine is not None or blueprint is not None:
        # Resolved exactly the way a live run would resolve it, and
        # stopping exactly where a live run would instead create a
        # machine: a `--blueprint` naming a blueprint with no
        # machine yet leaves nothing to apply the machine rules
        # against, and the report says so explicitly rather than
        # silently implying a checking tier it could not actually
        # reach.
        machine_id = _existing_machine(
            machine=machine, blueprint=blueprint, context=context)
    if machine_id is not None:
        state = _machines.load_machine_state(machine_id, context)
        scripts_map, parameters = _blueprint_invocation(state, context)
    elif blueprint is not None:
        # Read-only: this locates the codex file directly in home
        # mode without seeding anything, so a dry run never writes.
        doc = load_document(locate_blueprint(blueprint, context=context))
        machine_component = doc.machines.get(blueprint)
        if machine_component is None and len(doc.machines) == 1:
            machine_component = next(iter(doc.machines.values()))
        scripts_map = (dict(machine_component.scripts)
                       if machine_component is not None else {})
        parameters = (dict(machine_component.parameters)
                      if machine_component is not None else {})
    stem = _resolve_script_stem(label, scripts_map)
    script_path = locate_script(stem, context=context)
    script = load_script(script_path)
    if machine_id is not None:
        _preflight_machine_rules(
            script, _machines.load_machine_state(machine_id, context),
            script_path, context)
    property_sources = describe_sources(
        script, parameters=parameters, explicit=properties,
        properties_file=properties_file, context=context)
    timing = resolve_timing(script)
    reachable, total = reach(script)
    plan = {
        "script": script_path,
        "label": label,
        "machine": machine_id,
        "tier": "preflight" if machine_id is not None else "static",
        "selector": ("machine" if machine is not None
                     else "blueprint" if blueprint is not None else None),
        "statements": {"total": total, "statically-reachable": reachable},
        "timing": dataclasses.asdict(timing),
        "properties": dict(property_sources),
    }
    return DryRun(operation="run-script",
                  report=_dry_script_report(plan, timing, script_path),
                  plan=plan)


def _dry_script_report(plan, timing, script_path):
    """Render a script's dry run the way the CLI prints it."""
    lines = [f"run-script {plan['label']} --dry-run", ""]
    lines.append(f"script: {script_path}")
    if plan["machine"] is not None:
        lines.append(f"machine: {plan['machine']}")
        lines.append("tier: preflight -- every legality rule, and the "
                     "machine rules with it")
    elif plan["selector"] is None:
        lines.append("tier: static -- every legality rule; no machine "
                     "was selected, so the machine rules were not "
                     "applied")
    else:
        # The selector asked for the preflight tier, but there is
        # nothing yet to apply it against. A real run would create
        # the machine at this point; a dry run says so explicitly
        # instead of reporting the tier it actually reached as if it
        # were the tier that was asked for.
        lines.append("tier: static -- that blueprint has no machine "
                     "yet, so the machine rules had nothing to apply "
                     "to; a run would create one")
    lines.append("")
    lines.append(format_plan(timing,
                             name=os.path.basename(script_path)).rstrip())
    if plan["properties"]:
        lines.append("")
        lines.append("properties:")
        for key in sorted(plan["properties"]):
            lines.append(f"  {key}: {plan['properties'][key]}")
    counts = plan["statements"]
    lines.append("")
    lines.append(f"statements: {counts['statically-reachable']} of "
                 f"{counts['total']} statically reachable")
    unreached = counts["total"] - counts["statically-reachable"]
    if unreached:
        # Stated outright rather than left for the reader to infer:
        # a plan can only ever be a plan, and a report that implied
        # otherwise would be claiming a completeness it does not
        # actually have.
        lines.append(f"  {unreached} depend on what the guest does, so "
                     "no static pass can promise they run")
    lines.append("")
    lines.append("nothing was run.")
    return "\n".join(lines) + "\n"