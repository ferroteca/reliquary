# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Runtime executor for ``.rlqs`` scripts on QEMU/DOS.

The dynamic semantics are planning/design/script-spec.md's
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

import contextlib
import dataclasses
import mimetypes
import os
import re
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from qemu.qmp import ConnectError

from .binding import bind_properties, console_asker, describe_sources
from .library import locate_script, seed_blueprint, seed_script
from .machine import (Machine, _DisplayConsole, char_keys, screenshot,
                      validate_screenshot_name)
from .resolve import load_namespace
from .script_parser import load_script
from .script_timing import (format_plan, parse_duration,
                            resolve as resolve_timing)
from .script_validation import PORTABLE_KEY_NAMES
from . import machines as _machines


# Returned by a statement list that ended in `finish`: the run is
# complete, distinct from both "fell off the end" (None) and a
# phase name to transfer to.
_FINISH = object()

# Seconds between dispatch samples. Cadence is the control plane's
# business, never the script's (G5).
_POLL_INTERVAL = 2.0

# QEMU translations for every portable language key. Membership in
# the closed vocabulary is owned by static validation; keeping the
# backend map explicit makes an unsupported key fail closed.
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


def _resolve_key(spelling):
    """Resolve one `press` key or chord to QEMU key names.

    A chord's non-modifier member may be a single printable
    character (``ctrl+c``); a bare key name may not.
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
        raise KeyError(part)
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
        raise RuntimeError(
            f"no free HTTP port in range {self._port_min}-"
            f"{self._port_max}{detail}")

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
    """A ``${key}`` reference reached the runtime unbound."""

    def __init__(self, key):
        super().__init__(key)
        self.key = key


_HEARTBEAT_INTERVAL = 5.0
_SPINNER = "|/-\\"
_BAR_WIDTH = 20


class _Progress:
    """Live progress for a dispatch loop.

    Two audiences, one clock:

    * An attached terminal gets a colored, in-place spinner + bar
      that redraws every sample — good for someone watching the
      session live.
    * Everyone else — a redirected log a user is ``tail -f``-ing
      against a headless/backgrounded VM, and the transcript file
      itself — gets a plain heartbeat line every
      :data:`_HEARTBEAT_INTERVAL` seconds, so progress is visible
      without needing a live terminal.
    """

    def __init__(self):
        self.isatty = sys.stdout.isatty()
        self._active = False
        self._last_heartbeat = None
        self._tick = 0

    @staticmethod
    def _bar(fraction):
        fraction = min(1.0, max(0.0, fraction))
        filled = round(fraction * _BAR_WIDTH)
        return "#" * filled + "." * (_BAR_WIDTH - filled)

    def _render(self, phase, step, description, elapsed, remaining,
                timeout):
        fraction = elapsed / timeout if timeout > 0 else 1.0
        return (
            f"[{phase}] step {step}: {description}  "
            f"[{self._bar(fraction)}] "
            f"{elapsed:0.0f}s elapsed, {remaining:0.0f}s to timeout"
        )

    def tick(self, phase, step, description, expiry, timeout, now):
        """Advance the animation; return a heartbeat line, or None."""
        remaining = max(0.0, expiry - now)
        elapsed = max(0.0, timeout - remaining)
        line = self._render(
            phase, step, description, elapsed, remaining, timeout)
        if self.isatty:
            spin = _SPINNER[self._tick % len(_SPINNER)]
            self._tick += 1
            sys.stdout.write(f"\r\x1b[K\033[36m{spin} {line}\033[0m")
            sys.stdout.flush()
            self._active = True
        if (self._last_heartbeat is None
                or now - self._last_heartbeat >= _HEARTBEAT_INTERVAL):
            self._last_heartbeat = now
            return line
        return None

    def clear(self):
        if self._active:
            sys.stdout.write("\r\x1b[K")
            sys.stdout.flush()
            self._active = False
        self._last_heartbeat = None
        self._tick = 0


class ScriptRuntimeError(RuntimeError):
    """An error that occurred during script execution."""

    def __init__(self, message, statement=None, path=None):
        super().__init__(message)
        self.statement = statement
        self.path = path

    def __str__(self):
        location = ""
        if self.statement is not None and self.statement.line:
            location = f" at line {self.statement.line}"
        return f"{self.path or '<script>'}{location}: {super().__str__()}"


@dataclasses.dataclass(frozen=True)
class ScriptRun:
    """Result of a labeled ``run-script <label>`` invocation."""

    machine_id: str
    run_dir: str
    script_path: str
    created_machine: bool = False
    final_phase: str = "-"
    machine_phase: str = "-"


@dataclasses.dataclass(frozen=True)
class ScriptCheck:
    """Result of ``check_script``: path, plan, and printable report."""

    script_path: str
    plan: object
    report: str
    machine_id: str = None
    property_sources: dict = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True)
class _Sample:
    """One reading of every channel, taken at one instant."""

    rows: tuple = ()
    stopped: bool = False


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

    def holds(self, sample):
        """Whether the condition holds at this sample."""
        if self.condition.channel == "machine":
            return sample.stopped
        if self.condition.kind == "regex":
            return any(re.search(self.condition.value, row)
                       for row in sample.rows)
        target = _normalize_row(_literal(self.condition.value))
        return any(target in row for row in sample.rows)

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
                 run_dir=None, script_path=None, plan=None,
                 clock=time.monotonic, sleep=time.sleep,
                 http_service_factory=_HttpService, bindings=None):
        self._script = script
        self._plan = plan if plan is not None else resolve_timing(script)
        self._phases = {phase.name: phase for phase in script.phases}
        self._machine_id = machine_id
        self._context = context
        self._machine_home = machine_home
        self._run_dir = run_dir
        self._script_path = script_path
        self._transcript = None
        self._port = None
        self._display = False
        self._now = clock
        self._sleep = sleep
        self._step = 0
        self._status = _Progress()
        self._http_service_factory = http_service_factory
        self._http = None
        self._property_bindings = bindings
        self._bindings = dict(bindings.values) if bindings else {}
        self._secret_values = (
            set(bindings.secret_values()) if bindings else set())
        self._secret_entered = False
        self._phase = None
        self._run_started = None
        self._phase_started = None
        self._phase_budget = None
        self.final_phase = None
        self.machine_phase = None

    # -- diagnostics and records ---------------------------------

    def _error(self, message, statement=None):
        return ScriptRuntimeError(
            message, statement=statement, path=self._script_path)

    def _expired(self, clock, bound, statement=None, detail=""):
        """A timing failure naming the clock and where it came from."""
        return self._error(
            f"{clock} of {bound.spelling} expired{detail} (from the "
            f"{bound.source})", statement)

    def _redact(self, message):
        """Blank any bound secret value out of a record line.

        Protects Reliquary's own records — transcript and diagnostics.
        It cannot reach what a guest installer prints, logs, or shows
        in an explicitly requested screenshot.
        """
        for value in self._secret_values:
            if value and value in message:
                message = message.replace(value, "«secret»")
        return message

    def _log(self, message):
        message = self._redact(message)
        self._status.clear()
        print(message)
        if self._transcript is not None:
            self._transcript.write(message + "\n")
            self._transcript.flush()

    def _progress(self, expiry, timeout, description, now):
        heartbeat = self._status.tick(
            self._phase.name if self._phase is not None else "-",
            self._step, description, expiry, timeout, now)
        if heartbeat is not None:
            if self._transcript is not None:
                self._transcript.write(heartbeat + "\n")
                self._transcript.flush()
            if not self._status.isatty:
                print(heartbeat)

    def _read_machine_phase(self):
        try:
            state = _machines.load_machine_state(
                self._machine_id, self._context)
            return state.get("phase", "-")
        except FileNotFoundError:
            return "-"

    def _report_final(self):
        """Record the phase the script and the machine finished in.

        Called on every exit path — success, script error, or
        unexpected exception — so it is always clear what state the
        machine is left in, not just what happened along the way.
        """
        self.machine_phase = self._read_machine_phase()
        self.final_phase = self._phase.name if self._phase else "-"
        if self._transcript is not None:
            self._log(f"final script phase: {self.final_phase}")
            self._log(f"machine phase: {self.machine_phase}")

    # -- the run -------------------------------------------------

    def run(self, display=False):
        self._display = display
        self._establish_machine(display)
        self._start_transcript()
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
            if self._transcript is not None:
                self._log("result: ok")
        except (ScriptRuntimeError, TimeoutError, RuntimeError,
                ValueError) as exc:
            self._report_final()
            if self._transcript is not None:
                self._log("result: failed")
                self._log(f"error: {exc}")
            if isinstance(exc, ScriptRuntimeError) and exc.path is None:
                exc.path = self._script_path
            raise
        except Exception as exc:
            self._report_final()
            if self._transcript is not None:
                self._log("result: failed")
                self._log(f"error: {exc}")
            raise self._error(f"unexpected error: {exc}") from exc
        finally:
            self._http_stop()
            if self._transcript is not None:
                self._transcript.close()
                self._transcript = None

    def _log_bindings(self):
        """Record each bound property's key and source — never a value.

        The transcript is evidence of provenance, so a run is
        auditable without exposing what any source supplied.
        """
        bindings = self._property_bindings
        if not bindings or not bindings.sources:
            return
        for key in sorted(bindings.sources):
            self._log(f"property {key}: {bindings.sources[key]}")

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
                    f"{self._machine_id} is running; stop it first")
            if phase != "ready":
                raise self._error(
                    f"machine {self._machine_id} cannot execute a "
                    f"script (phase: {phase})")
        elif phase == "ready":
            self._port = _machines.start_machine(
                self._machine_id, display=display, context=self._context)
        elif phase == "running":
            from .lifecycle import read_vm_state
            vm = read_vm_state(home=_machines.machine_dir_path(
                self._machine_id, self._context))
            if vm is None:
                raise self._error(
                    "machine phase is running but no VM identity recorded")
            self._port = vm["port"]
        else:
            raise self._error(
                f"machine {self._machine_id} cannot execute a script "
                f"(phase: {phase})")

    def _start_transcript(self):
        if self._run_dir is None:
            return
        self._transcript = open(
            os.path.join(self._run_dir, "transcript.txt"), "w",
            encoding="utf-8", newline="\n")
        self._log(f"script: {self._script_path or '<script>'}")
        self._log(f"machine: {self._machine_id}")
        started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self._log(f"started: {started}")

    def _run_phases(self):
        """Walk the phase graph from `entry` until a `finish`."""
        name = self._script.entry
        while True:
            phase = self._phases[name]
            self._phase = phase
            self._log(f"phase: {name}")
            # A budget is dynamically scoped to one activation, so
            # each entry to a phase starts a fresh one.
            self._phase_started = self._now()
            self._phase_budget = self._plan.phase_deadlines.get(name)
            result = (self._run_reactive(phase) if phase.handlers
                      else self._execute(phase.statements))
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
            self._log(f"line {statement.line}: goto {statement.arguments[0]}")
            return statement.arguments[0]
        if verb == "finish":
            self._log(f"line {statement.line}: finish")
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
            else:
                raise self._error(f"unknown statement: {verb}", statement)
        except _PropertyUnbound as unbound:
            raise self._unbound(unbound, statement) from None
        return None

    def _unbound(self, unbound, statement):
        return self._error(
            f"the property ${{{unbound.key}}} has no bound value: "
            "property binding arrives with the property family",
            statement)

    # -- observation ---------------------------------------------

    def _wait(self, statement):
        if statement.handlers:
            return self._wait_branching(statement)
        condition = statement.condition
        description = _describe(condition)
        self._log(f"line {statement.line}: wait {description}")
        self._observe(
            [_Observation(condition, _seconds(statement.stable))],
            self._bound(statement), description, statement)
        return None

    def _wait_branching(self, statement):
        self._log(f"line {statement.line}: wait (branching)")
        handlers = statement.handlers
        observations = [_Observation(handler.condition,
                                     _seconds(handler.stable))
                        for handler in handlers]
        index = self._observe(
            observations, self._bound(statement),
            " or ".join(_describe(h.condition) for h in handlers),
            statement)
        handler = handlers[index]
        self._log(f"line {handler.line}: on "
                  f"{_describe(handler.condition)}")
        # The sample loop holds no session, so a handler body is free
        # to open its own: QEMU's QMP server admits one client.
        return self._execute(handler.statements)

    def _run_reactive(self, phase):
        """Dispatch a reactive phase's standing handlers."""
        bound = self._bound(phase)
        observations = [_Observation(handler.condition,
                                     _seconds(handler.stable))
                        for handler in phase.handlers]
        self._require_screen(observations, phase)
        expiry = self._now() + bound.seconds
        while True:
            self._check_clocks()
            sample = self._read()
            now = self._now()
            fired = None
            for index, observation in enumerate(observations):
                # Every armed observation sees every sample, so the
                # episodes of the handlers that did not fire stay
                # honest too.
                if observation.update(sample, now) and fired is None:
                    fired = index
            if fired is None:
                if now >= expiry:
                    self._status.clear()
                    raise self._expired(
                        "the reactive interval", bound,
                        detail=" with no handler firing")
                self._progress(expiry, bound.seconds, "dispatch", now)
                self._sleep(_POLL_INTERVAL)
                continue
            observations[fired].consumed = True
            handler = phase.handlers[fired]
            self._status.clear()
            self._log(f"line {handler.line}: always "
                      f"{_describe(handler.condition)}")
            result = self._execute(handler.statements)
            if result is not None:
                return result
            # Dispatch resumes in the same phase, and the interval
            # clock restarts with it.
            expiry = self._now() + bound.seconds

    def _observe(self, observations, bound, description, statement):
        """Sample until one observation is met; report which."""
        self._require_screen(observations, statement)
        expiry = self._now() + bound.seconds
        while True:
            self._check_clocks(statement)
            sample = self._read()
            now = self._now()
            for index, observation in enumerate(observations):
                if observation.update(sample, now):
                    self._status.clear()
                    return index
            # Checked after a sample: a timeout always means samples
            # were taken and none satisfied the condition.
            if now >= expiry:
                self._status.clear()
                raise self._expired(
                    "the observation timeout", bound, statement,
                    f" waiting for {description}")
            self._progress(expiry, bound.seconds, description, now)
            self._sleep(_POLL_INTERVAL)

    def _bound(self, node):
        """The effective timeout the timing plan resolved for a node."""
        entry = self._plan.at(node)
        return entry.timeout if entry is not None else self._plan.default

    def _check_clocks(self, statement=None):
        """Check the budgets at a boundary."""
        now = self._now()
        run = self._plan.run_deadline
        if (run is not None and self._run_started is not None
                and now - self._run_started > run.seconds):
            raise self._expired("the run deadline", run, statement)
        budget = self._phase_budget
        if budget is not None and now - self._phase_started > budget.seconds:
            raise self._expired("the phase deadline", budget, statement)

    def _require_screen(self, observations, node):
        """A screen observation needs a running machine to read."""
        if self._port is None and any(observation.channel == "screen"
                                      for observation in observations):
            raise self._error(
                "the machine is not running; the script must start it "
                "first", node)

    def _read(self):
        """Take one sample of every channel."""
        if self._port is None:
            return _Sample((), True)
        try:
            with self._console() as console:
                rows = console.screen_text()
        except (OSError, ConnectError, ConnectionError):
            # The QEMU process is gone: the guest powered itself off,
            # so the machine's phase must return to `ready` for any
            # later insert/eject and `start`.
            self._mark_stopped()
            return _Sample((), True)
        except RuntimeError as error:
            # lifecycle.qmp_session wraps connect failures as
            # RuntimeError after clearing vm.json; that sample is
            # the stopped observation (task 5 / AGENTS).
            if "no longer reachable" not in str(error):
                raise
            self._mark_stopped()
            return _Sample((), True)
        return _Sample(tuple(_normalize_row(row) for row in rows), False)

    @contextlib.contextmanager
    def _console(self):
        """Yield a console over an identity-verified session.

        Every sample and every input verb opens its own session, so
        none is ever held while a statement list runs — QEMU's QMP
        server admits one client at a time.
        """
        with Machine(self._port, self._machine_home).qmp() as qmp:
            yield _DisplayConsole(qmp)

    def _mark_stopped(self):
        self._port = None
        try:
            _machines.mark_stopped(self._machine_id, context=self._context)
        except FileNotFoundError:
            pass

    def _requires_running(self, statement):
        if self._port is None:
            raise self._error(
                "the machine is not running; the script must start it "
                "first", statement)

    # -- input verbs ---------------------------------------------

    def _enter(self, statement):
        text = _render_literal(statement.arguments[0], self._bindings)
        self._note_secret(statement.arguments[0])
        self._log(f"line {statement.line}: enter {text!r}")
        self._requires_running(statement)
        with self._console() as console:
            console.send_text(text, True)

    def _type(self, statement):
        text = _render_literal(statement.arguments[0], self._bindings)
        self._note_secret(statement.arguments[0])
        self._log(f"line {statement.line}: type {text!r}")
        self._requires_running(statement)
        with self._console() as console:
            console.send_text(text, False)

    def _note_secret(self, literal):
        """Record that a secret was entered, for later suppression.

        Once a secret reaches the guest, automatic failure screenshots
        are suppressed for the rest of the run (those land with the
        failure report, milestone 9); an explicitly requested
        screenshot is the author's own call and is never suppressed.
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
                return

    def _press(self, statement):
        keys = statement.arguments
        self._log(f"line {statement.line}: press {' '.join(keys)}")
        combos = []
        for spelling in keys:
            try:
                combos.append(_resolve_key(spelling))
            except KeyError as unknown:
                raise self._error(
                    f"{unknown.args[0]!r} is not a portable key name",
                    statement) from None
        self._requires_running(statement)
        with self._console() as console:
            console.send_keys(combos)

    def _select(self, statement):
        item = _render_literal(statement.arguments[0], self._bindings)
        exclude = ((_render_literal(statement.exclude, self._bindings),)
                   if statement.exclude else ())
        detail = f"select {item!r}"
        if exclude:
            detail += f" (exclude: {exclude[0]!r})"
        self._log(f"line {statement.line}: {detail}")
        self._requires_running(statement)
        with self._console() as console:
            console.cursor_menu_select(
                item, timeout=self._bound(statement).seconds,
                exclude=exclude)

    # -- supporting operations -----------------------------------

    def _screenshot(self, statement):
        name = (statement.arguments[0] if statement.arguments
                else f"step-{self._step}")
        name = validate_screenshot_name(name)
        self._log(f"line {statement.line}: screenshot {name}")
        self._requires_running(statement)
        if self._run_dir is not None:
            screenshot(
                name, self._port, self._machine_home,
                directory=os.path.join(self._run_dir, "screenshots"))
        else:
            Machine(self._port, self._machine_home).screenshot(name)

    def _insert(self, statement):
        slot, (kind, name) = statement.arguments
        if kind == "property":
            try:
                name = self._bindings[name]
            except KeyError:
                raise _PropertyUnbound(name) from None
        self._log(f"line {statement.line}: insert {slot} @{name}")
        self._machine_change(
            statement, _machines.insert_media, slot, name)

    def _eject(self, statement):
        slot = statement.arguments[0]
        self._log(f"line {statement.line}: eject {slot}")
        self._machine_change(statement, _machines.eject_media, slot)

    def _set_boot(self, statement):
        keys = statement.arguments
        self._log(f"line {statement.line}: set-boot {' '.join(keys)}")
        self._machine_change(statement, _machines.set_boot_order, keys)

    def _machine_change(self, statement, operation, *arguments):
        """Apply a persistent machine-state change, naming failures."""
        try:
            operation(self._machine_id, *arguments, context=self._context)
        except (RuntimeError, ValueError) as exc:
            raise self._error(str(exc), statement) from exc

    def _start(self, statement):
        self._log(f"line {statement.line}: start")
        self._port = _machines.start_machine(
            self._machine_id, display=self._display, context=self._context)

    def _stop(self, statement):
        self._log(f"line {statement.line}: stop")
        _machines.stop_machine(self._machine_id, context=self._context)
        self._port = None

    # -- run-scoped HTTP -----------------------------------------

    def _http_control(self, statement):
        command = statement.arguments[0]
        self._log(f"line {statement.line}: http {command}")
        if command == "start":
            self._http_start(statement)
        elif command == "stop":
            self._http_stop()
        else:
            raise self._error(f"unknown http action: {command}", statement)

    def _http_start(self, statement):
        self._http_stop()
        responses = self._http_responses(statement)
        plan = self._script.http
        port_min = int(plan.port_min) if plan and plan.port_min else 8000
        port_max = int(plan.port_max) if plan and plan.port_max else 9000
        service = self._http_service_factory(responses, port_min, port_max)
        try:
            service.start()
        except RuntimeError as exc:
            raise self._error(str(exc), statement) from exc
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
                    f"{response.path}", statement)
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


def _preflight_media_slots(script, machine_state, script_path):
    """Fail before any guest input when a script names an
    undeclared slot or boot drive.

    ``insert``/``eject``/``set-boot`` never create or remove a drive
    — the blueprint alone defines machine topology — so every named
    slot must exist in the machine's state.  ``insert``/``eject``
    further require a floppy or cdrom slot.
    """
    drives = machine_state.get("drives", {})
    for statement in _walk(script):
        if statement.verb == "insert":
            slots = (statement.arguments[0],)
            removable_only = True
        elif statement.verb == "eject":
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
                raise ScriptRuntimeError(
                    f"the machine declares no drive {slot}",
                    statement=statement, path=script_path)
            if (removable_only
                    and drive.get("medium") not in _REMOVABLE_MEDIA):
                raise ScriptRuntimeError(
                    f"{slot} is not a removable drive slot "
                    "(insert/eject are floppy and cdrom only)",
                    statement=statement, path=script_path)


def execute_script(script, *, machine_id, context=None, display=False,
                   run_dir=None, script_path=None, bindings=None):
    """Execute a parsed Script against a cached machine.

    The machine state the script's ``machine`` header expects is
    established first: the default ``running`` starts a ready
    machine, while ``stopped`` requires a stopped machine and
    leaves starting to the script itself.  The machine is left in
    whatever state the last executed step produced.

    When ``run_dir`` is set, a transcript is written there and
    screenshots land under ``run_dir/screenshots/``.

    Returns a ``(final_phase, machine_phase)`` pair reporting the
    script phase and machine phase the run finished in.
    """
    if not script.phases and not script.statements:
        try:
            phase = _machines.load_machine_state(
                machine_id, context).get("phase", "-")
        except FileNotFoundError:
            phase = "-"
        return "-", phase

    _preflight_media_slots(
        script, _machines.load_machine_state(machine_id, context),
        script_path)
    engine = _ScriptEngine(
        script, machine_id, context,
        _machines.machine_dir_path(machine_id, context),
        run_dir=run_dir, script_path=script_path, bindings=bindings)
    engine.run(display=display)
    return engine.final_phase, engine.machine_phase


def _existing_machine(*, machine=None, blueprint=None, context=None):
    """Resolve a selector to an existing machine, or None to be created.

    Never creates: the create-if-none decision is deferred so property
    binding can run before it (G3 — binding precedes machine creation).
    The blueprint lookup is scoped to this invocation's source, so a
    same-named machine from another project is never adopted.
    """
    if machine is None and blueprint is None:
        raise ValueError(
            "select a machine with --blueprint or --machine")
    if machine is not None:
        return _machines.resolve_machine(
            machine=machine, blueprint=blueprint, context=context)
    if _machines.machines_for_blueprint(blueprint, context):
        return _machines.resolve_machine(
            blueprint=blueprint, context=context)
    return None


def _blueprint_component(blueprint, context):
    """The blueprint's machine component, seeding in home mode.

    Mirrors ``create_machine``'s own resolution so the parameters and
    scripts map read here are exactly the ones a subsequent create
    would use. Returns None when the name resolves to no component;
    the eventual create then raises the missing-blueprint error.
    """
    from .assets import source_for
    if source_for(context).seeds:
        seed_blueprint(blueprint, context=context)
    namespace = load_namespace(context)
    return namespace.machines.get(blueprint)


def _resolve_script_stem(label, scripts_map):
    """Map a label through the blueprint scripts map, else use bare stem."""
    if not isinstance(label, str) or not label.strip():
        raise ValueError("script label must be a non-empty string")
    label = label.strip()
    if label in (".", "..") or "/" in label or "\\" in label:
        raise ValueError(
            f"script label must be a bare name, got: {label!r}")
    if label.lower().endswith(".rlqs"):
        raise ValueError(
            f"script label must omit the .rlqs suffix, got: {label!r}")
    if isinstance(scripts_map, dict) and label in scripts_map:
        return scripts_map[label]
    return label


def _ensure_script_path(stem, context=None):
    """Resolve ``stem`` through the asset source, seeding in home mode.

    Home mode seeds the script (and its media closure) from the codex
    on first reference; dir mode (``--assets``) is the sole source and
    seeds nothing. Resolution and its diagnostics come from
    ``locate_script``.
    """
    from .assets import source_for
    if source_for(context).seeds:
        seed_script(stem, context=context)
    return locate_script(stem, context=context)


def _create_run_dir(machine_id, context=None):
    """Create ``runs/<timestamp>-<id>/`` under the machine cache."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = uuid.uuid4().hex[:8]
    run_dir = os.path.join(
        _machines.machine_dir_path(machine_id, context),
        "runs",
        f"{timestamp}-{run_id}",
    )
    os.makedirs(os.path.join(run_dir, "screenshots"), exist_ok=True)
    os.makedirs(os.path.join(run_dir, "output"), exist_ok=True)
    return run_dir


def _blueprint_parameters(state, context):
    """The blueprint's `parameters` map, read live at invocation.

    Parameters configure script binding, not machine shape: they carry
    no state, `apply`, or baseline-digest involvement (ROADMAP "The
    machine model"), so they are read from the blueprint file each run
    rather than from the machine snapshot. A machine whose blueprint
    file has since moved simply contributes no parameters — its own
    state remains authoritative for shape.
    """
    source = state.get("blueprint-source")
    if not source or not os.path.exists(source):
        return {}
    from .document import load_document
    try:
        document = load_document(source)
    except (OSError, ValueError):
        return {}
    name = state.get("blueprint")
    component = document.machines.get(name)
    if component is None and len(document.machines) == 1:
        component = next(iter(document.machines.values()))
    return dict(component.parameters) if component is not None else {}


def run_script(label, *, blueprint=None, machine=None, context=None,
               display=False, properties=None, properties_file=None):
    """Resolve ``label``, ensure a machine, and execute under ``runs/``.

    Looks up ``label`` in the machine's blueprint ``scripts`` map
    first; when absent, treats ``label`` as a bare script stem under
    ``scripts/``.  With ``--blueprint`` and no machine yet, creates
    one.  Declared properties bind before the machine starts, from
    ``properties`` (explicit ``--property`` values), the blueprint
    parameters, the environment, the properties file, or — on a
    terminal — an interactive ask.  Returns a :class:`ScriptRun`
    naming the run directory.
    """
    # Resolve to an existing machine (or None) without creating, so
    # declared properties bind before any machine or media is made.
    machine_id = _existing_machine(
        machine=machine, blueprint=blueprint, context=context)
    if machine_id is not None:
        state = _machines.load_machine_state(machine_id, context)
        scripts_map = state.get("scripts") or {}
        parameters = _blueprint_parameters(state, context)
    else:
        component = _blueprint_component(blueprint, context)
        scripts_map = dict(component.scripts) if component is not None else {}
        parameters = (dict(component.parameters)
                      if component is not None else {})
    stem = _resolve_script_stem(label, scripts_map)
    script_path = _ensure_script_path(stem, context=context)
    script = load_script(script_path)
    bindings = bind_properties(
        script, parameters=parameters, explicit=properties,
        properties_file=properties_file, context=context,
        asker=console_asker())

    # Binding passed: now create the machine if the blueprint had none.
    created = machine_id is None
    if created:
        machine_id = _machines.create_machine(
            blueprint, context=context, properties=properties,
            properties_file=properties_file)
    run_dir = _create_run_dir(machine_id, context=context)
    final_phase, machine_phase = execute_script(
        script, machine_id=machine_id, context=context, display=display,
        run_dir=run_dir, script_path=script_path, bindings=bindings)
    return ScriptRun(
        machine_id=machine_id,
        run_dir=run_dir,
        script_path=script_path,
        created_machine=created,
        final_phase=final_phase,
        machine_phase=machine_phase,
    )


def check_script(name, *, blueprint=None, machine=None, context=None,
                 properties=None, properties_file=None):
    """Parse and statically check a script; return its timing plan.

    Read-only: does not seed the home, create a machine, write a run
    record, execute guest steps, prompt, or read a secret's value.
    Without a selector, ``name`` is a bare script stem. With
    ``--blueprint`` or ``--machine``, ``name`` resolves through that
    blueprint's ``scripts`` map first. When a machine is selected,
    media-slot preflight runs as well. The result names each declared
    property's supplying source without binding it.
    """
    machine_id = None
    scripts_map = {}
    parameters = {}
    if machine is not None:
        machine_id = _machines.resolve_machine(
            machine=machine, blueprint=blueprint, context=context)
        state = _machines.load_machine_state(machine_id, context)
        scripts_map = state.get("scripts") or {}
        parameters = _blueprint_parameters(state, context)
    elif blueprint is not None:
        from .library import locate_blueprint
        from .document import load_document
        # Read-only: locate resolves the codex file directly in home mode
        # without seeding, so check-script never writes.
        doc = load_document(locate_blueprint(blueprint, context=context))
        machine_component = doc.machines.get(blueprint)
        if machine_component is None and len(doc.machines) == 1:
            machine_component = next(iter(doc.machines.values()))
        scripts_map = (dict(machine_component.scripts)
                       if machine_component is not None else {})
        parameters = (dict(machine_component.parameters)
                      if machine_component is not None else {})
    stem = _resolve_script_stem(name, scripts_map)
    script_path = locate_script(stem, context=context)
    script = load_script(script_path)
    if machine_id is not None:
        _preflight_media_slots(
            script, _machines.load_machine_state(machine_id, context),
            script_path)
    property_sources = describe_sources(
        script, parameters=parameters, explicit=properties,
        properties_file=properties_file, context=context)
    plan = resolve_timing(script)
    report = format_plan(plan, name=os.path.basename(script_path))
    if property_sources:
        report += "\n\nproperties:\n" + "\n".join(
            f"  {key}: {property_sources[key]}"
            for key in sorted(property_sources))
    return ScriptCheck(
        script_path=script_path, plan=plan, report=report,
        machine_id=machine_id, property_sources=property_sources)
