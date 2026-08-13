# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Runtime executor for ``.rlqs`` scripts on QEMU/DOS.

The dynamic semantics are docs/spec/script-spec.md's
"Execution model": execution is defined over **samples** — discrete
readings of the machine — and over the **episodes** a condition's
consecutive holding samples form. Dispatch is single-threaded and
run to completion, so no sample is taken while a statement list is
executing, and every clock is checked at a boundary: a statement
start or a dispatch sample.

Timing is not re-derived here. :mod:`reliquary.script_timing`
resolved every bound at parse time, so this module looks each one
up and can name the scope that supplied it when a clock expires.
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

from .binding import bind_properties, console_asker, describe_sources
from .errors import (PreflightError, ReliquaryError, RunCancelled,
                     RunFailure, StaticError)
from .library import locate_script
from .control_display import char_keys
from .machine_handle import (Machine, screenshot,
                            validate_screenshot_name)
from .progress import interactive as _interactive, stream_for
from .resolve import load_namespace
from .script_parser import load_script
from .script_timing import (format_plan, parse_duration,
                            resolve as resolve_timing)
from .script_validation import PORTABLE_KEY_NAMES, reach
from . import events as _events
from . import screen_stability as _stability
from . import machines as _machines
from . import transcript as _transcript
from .machines import DryRun


# Returned by a statement list that ended in `finish`: the run is
# complete, distinct from both "fell off the end" (None) and a
# phase name to transfer to.
_FINISH = object()

# Seconds between dispatch samples. Cadence is the control plane's
# business, never the script's (G5).
_RECORD_PACE = 0.1

_POLL_INTERVAL = 2.0

#: And how often while a screen is still moving. The poll above waits
#: a screen out cheaply, but it cannot confirm one has settled: a
#: quiescence window is only observable by sampling inside it, and two
#: reads two seconds apart say nothing about the last 200ms. Dense
#: reads are spent only there, never for the whole of a long wait.
_SETTLE_POLL = 0.1

# The language's portable `press` names, mapped onto the seam's key
# vocabulary — which is QEMU's qcode set (D103), so most entries are
# the identity and the handful that are not (`enter`, `space`,
# `pageup`, `pagedown`) are why this table exists at all. Every
# backend receives these names, QEMU and VirtualBox alike.
#
# Membership in the language's closed vocabulary is owned by static
# validation; keeping this map explicit makes an unsupported key fail
# closed.
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
    return " ".join(text.split())


def resolve_key(spelling):
    """Resolve one `press` key or chord to QEMU key names.

    A chord's non-modifier member may be a single printable
    character (``ctrl+c``); a bare key name may not.

    An unknown name is a STATIC ERROR carrying its own message: the
    CLI's `press` calls this directly (no script, no line number), so
    a bare ``KeyError`` here reported an ordinary typo as reliquary's
    own fault. A run re-raises it against the statement's line.
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
    """A ``${key}`` reference reached the runtime unbound.

    The one deliberate raise outside the hierarchy, and deliberately
    so. It is a private signal rather than an error: every raise is
    caught by the statement dispatcher, which restates it as a located
    ``ScriptRuntimeError``, so no caller ever sees this class. Making
    it a ``ReliquaryError`` would give it an exit code and a tidy
    one-line report — which is what it would get if it ever escaped,
    and an escape is a bug in the dispatcher that should show a
    traceback instead. So the rule that every deliberate *error* is in
    the hierarchy holds; this is not one.
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

    The dynamic tier of the taxonomy — a RUN FAILURE, exit ``4``.
    ``clock`` and ``scope`` are set when a timing bound expired, so
    the failure report can name which clock ran out and where it came
    from.
    """

    clock = None
    scope = None


class ScriptPreflightError(_Located, PreflightError):
    """A machine rule broken before the first guest input (exit ``3``).

    Same diagnostic shape as a runtime error — it cites the statement
    that would have broken the rule — but it is raised before the run
    touches the guest, so it belongs to the preflight tier.
    """


@dataclasses.dataclass(frozen=True)
class ScriptRun:
    """The output of a ``run-script <label>`` invocation.

    The run **returns its output** and stores nothing (D36):
    ``events`` is the run's whole event stream, in order, the
    terminal event last. A caller that wants a record keeps this;
    reliquary keeps none.
    """

    machine_id: str
    script_path: str
    created_machine: bool = False
    final_phase: str = "-"
    machine_phase: str = "-"
    events: tuple = ()


@dataclasses.dataclass(frozen=True)
class _Sample:
    """One reading of every channel, taken at one instant.

    ``rows`` are normalized for matching; ``frame`` is the screen as
    the seam handed it over — character rows and their attribute
    tokens — which is what the quiescence gate compares, identity
    being the whole pair.
    """

    rows: tuple = ()
    stopped: bool = False
    frame: tuple = ()


class _Observation:
    """One armed condition, tracking its episodes.

    An **episode** is a maximal run of consecutive samples at which
    the condition holds. ``stable`` is satisfied once the current
    episode's age reaches its duration; ``consumed`` implements the
    reactive rearm rule — a fired handler re-arms only after a
    sample at which its condition does not hold.
    """

    def __init__(self, condition, stable=None):
        self.condition = condition
        self.stable = stable
        self.consumed = False
        self._episode = None

    @property
    def channel(self):
        return self.condition.channel

    def matches_row(self, row):
        """Whether one screen row satisfies this condition.

        The per-row form the whole-sample test is built from, so a
        match event can name the row that satisfied it rather than
        merely asserting that one did.
        """
        if self.condition.channel == "machine":
            return False
        if self.condition.kind == "regex":
            return re.search(self.condition.value, row) is not None
        return _normalize_row(_literal(self.condition.value)) in row

    def holds(self, sample):
        """Whether the condition holds at this sample."""
        if self.condition.channel == "machine":
            return sample.stopped
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


class _ScriptEngine:
    """One run of one script against one cached machine."""

    def __init__(self, script, machine_id, context, machine_home,
                 events=None, script_path=None, plan=None,
                 clock=time.monotonic, sleep=time.sleep,
                 http_service_factory=_HttpService, bindings=None,
                 record_pace=None, recording_writer=None):
        self._script = script
        self._plan = plan if plan is not None else resolve_timing(script)
        self._phases = {phase.name: phase for phase in script.phases}
        self._machine_id = machine_id
        self._context = context
        self._machine_home = machine_home
        self._script_path = script_path
        self._running = False
        self._display = False
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
        self._pace_settle = max(_SETTLE_POLL, record_pace or 0)
        self._pace_idle = max(_POLL_INTERVAL, record_pace or 0)
        self._phase = None
        self._run_started = None
        self._phase_started = None
        self._phase_budget = None
        # The failure report's raw material, kept as the run goes:
        # what is pending, the route taken and how often each phase
        # was revisited, and the last screen read.
        self._pending = None
        self._pending_literal = None
        self._route = []
        self._revisits = collections.Counter()
        self._last_sample = None
        self._cancelled = threading.Event()
        self.events = (events if events is not None
                       else _events.EventStream(redact=self._redact))
        self.final_phase = None
        self.machine_phase = None

    # -- diagnostics and the stream ------------------------------

    def cancel(self):
        """Request a stop; the run ends at the next event boundary.

        Boundaries are statement starts, dispatch samples, and the
        chunk boundaries of a host transfer, so an input delivery in
        flight completes atomically while a large media fetch aborts
        where it stands — the execution model's severability
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
        """Return the sleep interval between samples.

        When recording, both intervals are floored against the record
        pace so a captured run polls at least as hard as the recording
        cadence — a steady interval is simpler to replay and an
        undersampled transcript misses frames.
        """
        return self._pace_idle if settled else self._pace_settle

    def _redact(self, message):
        """Blank any bound secret value out of a rendered line.

        Protects reliquary's own output — the event stream and its
        diagnostics. It cannot reach what a guest installer prints,
        logs, or shows in an explicitly requested screenshot.
        """
        for value in self._secret_values:
            if value and value in message:
                message = message.replace(value, "\u00absecret\u00bb")
        return message

    def _emit(self, kind, **fields):
        return self.events.emit(kind, **fields)

    def _progress(self, expiry, timeout, description, now):
        """Advance the live display — elapsed against its limit."""
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
        """Record the phase the script and the machine finished in.

        Called on every exit path — success, script error, or
        unexpected exception — so it is always clear what state the
        machine is left in, not just what happened along the way.
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
            self._report_final()
            self._terminal(None)
        except RunCancelled as exc:
            self._report_final()
            self._terminal(exc)
            raise
        except ReliquaryError as exc:
            self._report_final()
            if isinstance(exc, ScriptRuntimeError) and exc.path is None:
                exc.path = self._script_path
            self._fail(exc)
            raise
        except Exception as exc:
            self._report_final()
            wrapped = self._error(f"unexpected error: {exc}")
            self._fail(wrapped)
            raise wrapped from exc
        finally:
            self._http_stop()
            self.events.clear()

    def _terminal(self, error):
        """Emit the stream's last word: what the run came to."""
        from .errors import exit_code, outcome
        self._emit(
            _events.RUN_END, outcome=outcome(error),
            **{"exit-code": exit_code(error) if error else 0,
               "final-phase": self.final_phase or "-",
               "machine-phase": self.machine_phase or "-",
               "error": str(error) if error is not None else None})

    def _fail(self, error):
        """Emit the failure report, then the terminal event.

        Everything the report can name comes from the run itself: the
        pending condition or action, the clock that expired and the
        scope that supplied it, the route with its revisit counts, the
        nearest miss on the last screen read, an automatic screenshot,
        and the command to try next.
        """
        self.events.clear()
        self._emit(
            _events.FAILURE, error=str(error), pending=self._pending,
            clock=getattr(error, "clock", None),
            scope=getattr(error, "scope", None),
            route=tuple(self._route) or None,
            revisits={name: count for name, count
                      in self._revisits.items() if count > 1} or None,
            **{"nearest-miss": self._nearest_miss(),
               "screenshot": self._failure_screenshot(),
               "next-command": self._next_command()})
        self._terminal(error)

    def _nearest_miss(self):
        """The screen row that came closest to the pending literal.

        Only a text condition has a nearest miss: a regex names a
        shape rather than a string, and there is nothing honest to
        measure against.
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

    def _failure_screenshot(self):
        """Capture the failing screen, unless a secret has been typed.

        Once a secret reaches the guest, automatic screenshots are
        suppressed for the rest of the run: an installer may echo what
        it was given, and an automatic capture is not the author's own
        deliberate call.
        """
        if not self._running or self._secret_entered:
            return None
        name = f"failure-step-{self._step}"
        try:
            screenshot(name, self._machine_home)
        except Exception:
            # A failure report must never fail; the machine may
            # already be gone.
            return None
        return os.path.join(self._machine_home, "screenshots",
                            f"{name}.png")

    def _next_command(self):
        """The command most likely to move the user forward."""
        if self._read_machine_phase() == "running":
            return f"rlq screen --machine {self._machine_id}"
        return f"rlq list-machines --machine {self._machine_id}"

    def _log_bindings(self):
        """Report each bound property's key and source — never a value.

        The stream is evidence of provenance, so a run is auditable
        without exposing what any source supplied.
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

    def _run_phases(self):
        """Walk the phase graph from `entry` until a `finish`."""
        name = self._script.entry
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
            name = result

    # -- statements ----------------------------------------------

    def _execute(self, statements):
        """Run a statement list; report how control left it."""
        for statement in statements:
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
            # A `${key}` reaches the runtime unbound from a condition
            # as easily as from an argument, so one handler covers
            # every statement that can carry one.
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
        """Record a machine variable — the script's channel to the host."""
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

    # -- observation ---------------------------------------------

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
        self._emit(_events.OBSERVATION_ARM, description=description,
                   timeout=bound.seconds, line=getattr(statement, "line", 0),
                   **{"timeout-source": bound.source})
        return bound

    def _wait(self, statement):
        if statement.handlers:
            return self._wait_branching(statement)
        condition = statement.condition
        description = _describe(condition)
        observations = [_Observation(condition, _seconds(statement.stable))]
        bound = self._arm(statement, observations, description)
        self._observe(observations, bound, description, statement)
        return None

    def _wait_branching(self, statement):
        handlers = statement.handlers
        observations = [_Observation(handler.condition,
                                     _seconds(handler.stable))
                        for handler in handlers]
        description = " or ".join(
            _describe(handler.condition) for handler in handlers)
        bound = self._arm(statement, observations, description)
        index = self._observe(observations, bound, description, statement)
        handler = handlers[index]
        self._emit(_events.HANDLER_FIRE, keyword="on",
                   description=_describe(handler.condition),
                   line=handler.line)
        # The sample loop holds no session, so a handler body is free
        # to open its own: QEMU's QMP server admits one client.
        return self._execute(handler.statements)

    def _run_reactive(self, phase):
        """Dispatch a reactive phase's standing handlers."""
        observations = [_Observation(handler.condition,
                                     _seconds(handler.stable))
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
        while True:
            self._check_clocks()
            sample = self._read()
            now = self._now()
            # An unstable frame evaluates *none* of the handlers,
            # which is why the gate belongs to the container rather
            # than to any one of them.
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
                # episodes of the handlers that did not fire stay
                # honest too.
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
        while True:
            self._check_clocks(statement)
            sample = self._read()
            now = self._now()
            # An unsettled sample is not one the condition is judged
            # on, and sampling tightens while the screen moves: a
            # quiescence window is only observable from inside it.
            # **The gate delays acceptance and never causes failure by
            # itself** — at expiry the condition is evaluated on
            # whatever is there, so a timeout still means samples were
            # taken and none satisfied it, never that nobody looked.
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
        """Report a match, naming the row that satisfied it."""
        row = None
        for candidate in sample.rows:
            if observation.matches_row(candidate):
                row = candidate
                break
        self._emit(_events.OBSERVATION_MATCH, description=description,
                   row=row, elapsed=round(elapsed, 3), line=line)

    def _bound(self, node):
        """The effective timeout the timing plan resolved for a node."""
        entry = self._plan.at(node)
        return entry.timeout if entry is not None else self._plan.default

    def _gate(self, node):
        """The quiescence gate the plan resolved for this observation.

        ``None`` where the guard is off — ``stability=0`` is the
        author's escape for a screen the default would refuse, and it
        must cost nothing at all, not even the window that
        establishing quiescence would otherwise take.
        """
        entry = self._plan.at(node)
        level = (entry.stability if entry is not None
                 else self._plan.default_stability)
        if level is None or level.value <= 0:
            return None
        return level

    def _settled(self, gate, monitor, sample, now):
        """Whether this sample is one a condition may be judged on.

        A condition can hold perfectly on a screen that is still
        painting, and that is the screen a wait must not act on — so
        an unsettled sample is skipped rather than evaluated, and the
        wait keeps looking. A stopped machine has no screen to judge,
        and the machine channel still has to be answerable there.
        """
        if gate is None or sample.stopped or not sample.frame:
            return True
        reading = monitor.observe(sample.frame, now=now)
        if reading.stability is not None:
            # The window was observed, so there is a verdict here
            # rather than merely an absence of evidence. Which of
            # those two it is decides what an expiry may do.
            self._measured = True
        if reading.stable:
            return True
        self._gated = reading
        return False

    def _gate_note(self):
        """What to add to an expiry that skipped unsettled samples.

        A wait now expires two ways that look identical from outside:
        the condition never matched, or it matched only on frames the
        guard skipped. The second is baffling without help — the text
        is plainly there in any screenshot taken at the time — so the
        failure says which, and the animated region is what makes the
        message locate the problem rather than restate the expiry.
        """
        reading = self._gated
        if reading is None:
            return ""
        note = "; the screen never settled enough to compare against"
        if reading.stability is None:
            return f"{note} (never sampled densely enough to tell)"
        note += f" (stability {reading.stability:.3f}"
        if reading.animated:
            note += (f", outside a {len(reading.animated)}-cell "
                     "animated region")
        return f"{note})"

    def _pace(self, statement):
        """Let the guest settle before the first key event.

        Agentlessly the guest's *input* readiness is unobservable
        where its output is not, so a control plane that types the
        instant a screen paints asserts something it cannot know
        (G1). This is the gap the plan resolved for this statement —
        never re-derived here, so a report can name the scope that
        supplied it.

        It is control-plane pacing and not a `delay` verb: the pause
        is a property of delivering input, not a step an author
        sequences. `send_keys` already paces *between* key events;
        this is the missing pause before the first.

        The gap is taken before delivery, so a cancellation arriving
        during it ends the run cleanly at this boundary rather than
        mid-delivery.
        """
        gap = self._plan.pacing_at(statement)
        if gap is None or gap.seconds <= 0:
            return
        self._sleep(gap.seconds)
        self._check_clocks(statement)

    def _check_clocks(self, statement=None):
        """Check the budgets — and a cancellation — at a boundary."""
        if self._cancelled.is_set():
            raise RunCancelled(
                f"the run was cancelled at step {self._step}; machine "
                f"{self._machine_id} is left as it stands")
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

    def _read(self):
        """Take one sample of every channel."""
        if not self._running:
            return self._sampled(_Sample((), True))
        try:
            with self._console() as console:
                frame = console.screen()
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
        return self._sampled(
            _Sample(tuple(_normalize_row(row) for row in rows), False,
                    frame))

    def _sampled(self, sample):
        """Keep the latest reading, which the failure report needs."""
        self._last_sample = sample
        return sample

    @contextlib.contextmanager
    def _console(self):
        """Yield a console over an identity-verified session.

        Every sample and every input verb opens its own session, so
        none is ever held while a statement list runs — QEMU's QMP
        server admits one client at a time.
        """
        machine = Machine(self._machine_home)
        if self._recording_writer is not None:
            machine._session_wrapper = (
                lambda session: _transcript.RecordingSession(
                    session, self._recording_writer))
        with machine.console() as console:
            yield console

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
        """Record that a secret was entered, for later suppression.

        Once a secret reaches the guest, automatic failure screenshots
        are suppressed for the rest of the run; an explicitly
        requested screenshot is the author's own call and is never
        suppressed. Recording stops too: a raw screen carries a typed
        password in plain text, and a frame is a grid so event-stream
        redaction cannot reach it.
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

    # -- supporting operations -----------------------------------

    def _screenshot(self, statement):
        name = (statement.arguments[0] if statement.arguments
                else f"step-{self._step}")
        name = validate_screenshot_name(name)
        self._action(statement, "screenshot", name)
        self._requires_running(statement)
        # No run directory exists any more (D36), so an author's
        # screenshot rests with the machine it was taken from.
        Machine(self._machine_home).screenshot(name)
        self._completed(statement, "screenshot")

    def _insert(self, statement):
        slot, (kind, name) = statement.arguments
        if kind == "property":
            try:
                name = self._bindings[name]
            except KeyError:
                raise _PropertyUnbound(name) from None
        self._action(statement, "insert", f"{slot} @{name}")
        # The stream carries the fetch's transfer/verify events (an
        # insert can pull hundreds of megabytes, and silence reads as
        # a hang); the cancel event makes that fetch severable.
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
        """Apply a persistent machine-state change, naming failures.

        ``options`` reach the operation unchanged, so a change that
        fetches media can be given the run's stream and cancel event
        without every other change growing parameters it has no use
        for. A ``RunCancelled`` raised inside is deliberately not
        caught here: it is the run stopping, not this change failing.
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
    """Yield every statement of a script, nested bodies included.

    The validation and timing layers walk the tree too, but each
    threads its own scope context and neither may import this
    module's; this is the plain traversal.
    """

    def statements(items, handlers=()):
        for handler in handlers:
            yield from statements(handler.statements)
        for item in items:
            yield item
            yield from statements((), item.handlers)

    yield from statements(script.statements)
    for phase in script.phases:
        yield from statements(phase.statements, phase.handlers)


_REMOVABLE_MEDIA = frozenset({"floppy", "cdrom"})


def _no_such_media(name, namespace):
    """The diagnostic for a media reference the namespace lacks."""
    close = difflib.get_close_matches(name, namespace.media, n=3,
                                      cutoff=0.6)
    hint = ("; did you mean " + ", ".join(repr(other) for other in close)
            if close else "")
    return f"no media named {name!r} in the active source{hint}"


def _preflight_machine_rules(script, machine_state, script_path,
                             context=None):
    """Fail before any guest input when a script names something the
    machine or the namespace does not define.

    Two of the machine rules preflight owes (script-spec.md,
    "Validation and preflight"): a media reference naming no media
    the namespace defines, and an undeclared slot or boot drive.

    ``insert``/``eject``/``set-boot`` never create or remove a drive
    — the blueprint alone defines machine topology — so every named
    slot must exist in the machine's state.  ``insert``/``eject``
    further require a floppy or cdrom slot.

    A ``$property`` media argument resolves at binding, not here, so
    only a literal ``@name`` is checked. The namespace is loaded
    lazily: a script inserting nothing by name never pays for it.
    The slot is checked before the media on the same statement, in
    the order the author wrote them.
    """
    drives = machine_state.get("drives", {})
    namespace = None
    for statement in _walk(script):
        if statement.verb in ("insert", "eject"):
            slots = (statement.arguments[0],)
            removable_only = True
        elif statement.verb == "set-boot":
            slots = statement.arguments
            removable_only = False
        else:
            continue
        for slot in slots:
            drive = drives.get(slot)
            if drive is None:
                raise ScriptPreflightError(
                    f"the machine declares no drive {slot}",
                    statement=statement, path=script_path,
                    rule_id="machine.slot-not-declared")
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
            raise ScriptPreflightError(
                _no_such_media(name, namespace),
                statement=statement, path=script_path,
                rule_id="media.unknown")


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

    _preflight_machine_rules(
        script, _machines.load_machine_state(machine_id, context),
        script_path, context)
    record_pace = None
    recording_writer = None
    if record is not None:
        record_pace = _RECORD_PACE
        recording_writer = _transcript._TranscriptWriter(
            record, pace=record_pace)
        recording_writer.open()
    engine = _ScriptEngine(
        script, machine_id, context,
        _machines.machine_dir_path(machine_id, context),
        events=events, script_path=script_path, bindings=bindings,
        record_pace=record_pace, recording_writer=recording_writer)
    try:
        with _cancel_on_interrupt(engine):
            engine.run(display=display)
        return engine.final_phase, engine.machine_phase
    finally:
        if recording_writer is not None:
            recording_writer.close()


@contextlib.contextmanager
def _cancel_on_interrupt(engine):
    """Turn Ctrl-C into a cancellation the runner ends cleanly on.

    A foreground Ctrl-C requests a stop; the run ends at the next
    event boundary with a ``cancelled`` terminal event and exit ``5``,
    leaving the machine as-is (no implicit teardown). Installing a
    handler is what makes the stop land *at a boundary* rather than
    wherever the interrupt happened to arrive — an input delivery in
    flight completes.

    Signal handlers belong to the main thread; a run driven from any
    other thread simply keeps Python's default behavior, and the
    ``KeyboardInterrupt`` is translated below instead.

    A *second* Ctrl-C restores the default handler and interrupts at
    once. The graceful stop is the promise, not a trap: without an
    escalation the only way out of a stop that will not land is
    killing the terminal.
    """
    installed = False
    previous = None

    def _interrupt(*_):
        if engine.cancelled:
            # Asked twice: the caller wants out now, not at the next
            # boundary. Hand the signal back to Python and let this
            # one raise.
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
    """Resolve a selector to an existing machine, or None to be created.

    Never creates: the create-if-none decision is deferred so property
    binding can run before it (G3 — binding precedes machine creation).
    The blueprint lookup is scoped to this invocation's source, so a
    same-named machine from another project is never adopted.
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
    """The blueprint's machine component, from the blueprints directory.

    Mirrors ``create_machine``'s own resolution so the parameters and
    scripts map read here are exactly the ones a subsequent create
    would use — which now means seeding nothing (D88). Returns None
    when the name resolves to no component; the eventual create then
    raises the missing-blueprint error, naming the seed command where
    the codex ships that name.
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
    """Resolve ``stem`` from the scripts directory, seeding nothing.

    The directory is the sole source (D88); resolution and its
    diagnostics come from ``locate_script``, which names the seed
    command where the codex ships that script.
    """
    return locate_script(stem, context=context)


def _blueprint_invocation(state, context):
    """The blueprint's `scripts` and `parameters`, read live.

    Neither configures what a machine *is*: `parameters` feed script
    binding and `scripts` name which instructions to run, so both sit
    outside the shape baseline — no state, no `apply`, no digest
    involvement (docs/spec/instance-model.md) — and are read from the
    blueprint file each run rather than from the machine snapshot.
    Recording the label map made a machine unable to run a label its
    blueprint gained after creation until an `apply` it had no shape
    reason to need, which is the asymmetry this resolves (D101).

    A machine whose blueprint file has since moved contributes
    neither — its own state remains authoritative for shape.
    """
    source = state.get("blueprint-source")
    if not source or not os.path.exists(source):
        return {}, {}
    from .document import load_document
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
    """Resolve ``label``, ensure a machine, run it, and return its output.

    Looks up ``label`` in the machine's blueprint ``scripts`` map
    first; when absent, treats ``label`` as a bare script stem under
    ``scripts/``.  With ``--blueprint`` and no machine yet, creates
    one.  Declared properties bind before the machine starts, from
    ``properties`` (explicit ``--property`` values), the blueprint
    parameters, the environment, the properties file, or — on a
    terminal under an interactive ``progress`` mode — an interactive
    ask.

    The run **returns its output** and stores nothing (D36): the
    returned :class:`ScriptRun` carries the whole event stream, which
    ``progress`` also renders live (``auto | pretty | plain |
    jsonl``). A failure raises by error class; a Ctrl-C ends the run
    at the next event boundary and raises
    :class:`~reliquary.errors.RunCancelled`.

    ``expect`` **contracts the run on what it leaves behind**: a
    mapping of machine-variable key to the value the run is expected
    to have `set`. Every key is read once the run completes, and one
    that is unset or holds something else raises
    :class:`~reliquary.errors.RunFailure` naming key, wanted and got.
    Without it the caller reads the variable afterwards and the join
    is theirs to get right — an unset variable and a machine that
    never ran read alike, deliberately, so a script that failed to
    reach its `set` is silent. This makes that silence loud, in one
    call rather than two.

    It is a **postcondition and not a wait**, which is what the
    surface can honestly offer: this function blocks and only a
    running script's `set` writes a variable, so by the time it
    returns the value is final and there is nothing left to poll. A
    wait belongs where the setter is somebody else — another thread
    running this same call, or a detached run — which is
    :func:`~reliquary.machines.wait_machine_var`.

    ``dry_run=True`` returns a :class:`~reliquary.machines.DryRun`
    instead — a document, not a stream — having started no machine
    and delivered no guest input. It is the only mode in which the
    selector is optional, because its presence chooses which tier is
    checked; ``display``, a non-default ``progress``, ``expect`` and
    ``record`` are refused with it — a plan has no window to show, no
    stream to render, no run whose outcome could be contracted, and
    no screens to capture.
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
    """Hold the finished run to what it was expected to leave.

    Read once each, in the caller's own key order so a diagnostic is
    reproducible, and the *first* mismatch raises: a run that missed
    its first postcondition has already gone wrong, and listing the
    rest would report consequences beside the cause.

    Nothing polls. The run is over, so every variable it was going to
    set is set (D90) — an unset key here means the script never
    reached that `set`, which is exactly the silence this exists to
    break.
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
    """Evaluate a script run, committing none of it.

    The script half of the dry run whose rule is stated in
    docs/spec/cli.md. Read-only throughout: it seeds nothing, creates
    no machine, executes no guest step, never prompts and never reads
    a secret's value — it stops before the machine starts and before
    any statement reaches a guest.

    **The selector chooses the tier**, which is why it is optional
    here and required for a real run. Without one, ``label`` is a
    bare script stem and every legality rule applies. With
    ``blueprint=`` or ``machine=`` it resolves through that
    blueprint's ``scripts`` map first and the machine rules apply as
    well — the two modes script-spec.md specifies, preserved by the
    respelling rather than collapsed into one.
    """
    machine_id = None
    scripts_map = {}
    parameters = {}
    if machine is not None or blueprint is not None:
        # Resolved exactly as a live run resolves it, and stopping
        # where a run would create: `--blueprint` naming a blueprint
        # with no machine yet leaves nothing to apply the machine
        # rules against, which the report says rather than implying
        # the tier it could not reach.
        machine_id = _existing_machine(
            machine=machine, blueprint=blueprint, context=context)
    if machine_id is not None:
        state = _machines.load_machine_state(machine_id, context)
        scripts_map, parameters = _blueprint_invocation(state, context)
    elif blueprint is not None:
        from .library import locate_blueprint
        from .document import load_document
        # Read-only: locate resolves the codex file directly in home
        # mode without seeding, so a dry run never writes.
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
        # The selector chose the preflight tier and there is nothing
        # to apply it against. A run would create the machine here;
        # a dry run says so instead of reporting the tier it reached
        # as though it were the tier that was asked for.
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
        # Said outright rather than left to be inferred: a plan can
        # only ever be a plan, and a report that implied otherwise
        # would be claiming a completeness it cannot have.
        lines.append(f"  {unreached} depend on what the guest does, so "
                     "no static pass can promise they run")
    lines.append("")
    lines.append("nothing was run.")
    return "\n".join(lines) + "\n"