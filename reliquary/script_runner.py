# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Runtime executor for milestone-one .rlqs scripts on QEMU/DOS."""

import dataclasses
import os
import re
import time
import uuid
from datetime import datetime, timezone

from qemu.qmp import ConnectError

from .home import scripts_dir
from .library import seed_script
from .lifecycle import Qmp
from .machine import (Machine, _DisplayConsole, char_keys, screenshot,
                      validate_screenshot_name)
from .script import load_script
from . import machines as _machines


_KEY_NAMES = {
    "enter": "ret",
    "esc": "esc",
    "escape": "esc",
    "tab": "tab",
    "space": "spc",
    "backspace": "backspace",
    "down": "down",
    "up": "up",
    "left": "left",
    "right": "right",
    "insert": "insert",
    "delete": "delete",
    "home": "home",
    "end": "end",
    "pageup": "pgup",
    "pagedown": "pgdn",
    "f1": "f1", "f2": "f2", "f3": "f3", "f4": "f4",
    "f5": "f5", "f6": "f6", "f7": "f7", "f8": "f8",
    "f9": "f9", "f10": "f10", "f11": "f11", "f12": "f12",
}

_KEY_RE = re.compile(r"<([a-z0-9+]+)>")


def _normalize_row(text):
    return " ".join(text.split())


def _resolve_key(name):
    if "+" in name:
        parts = name.split("+")
        mapped = tuple(_resolve_key(part) for part in parts
                       if _resolve_key(part) is not None)
        return mapped if mapped else None
    return _KEY_NAMES.get(name, name)


def _normalize_screen_text(screen):
    return [_normalize_row(row) for row in screen]


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
    """Result of a labeled ``script <label>`` invocation."""

    machine_id: str
    run_dir: str
    script_path: str
    created_machine: bool = False


class _ScriptEngine:
    def __init__(self, script, machine_id, home, machine_home,
                 run_dir=None, script_path=None):
        self._script = script
        self._machine_id = machine_id
        self._home = home
        self._machine_home = machine_home
        self._run_dir = run_dir
        self._script_path = script_path
        self._transcript = None
        self._port = None
        self._display = False
        self._current_state = script.initial
        self._step = 0

    @property
    def _default_timeout(self):
        if self._script.timeout is not None:
            return _parse_duration(self._script.timeout)
        return 30.0

    def _error(self, message, statement=None):
        return ScriptRuntimeError(
            message, statement=statement, path=self._script_path)

    def _log(self, message):
        print(message)
        if self._transcript is not None:
            self._transcript.write(message + "\n")
            self._transcript.flush()

    def run(self, display=False):
        self._display = display
        state = _machines.load_machine_state(self._machine_id, self._home)
        phase = state.get("phase")
        if self._script.machine == "stopped":
            # The script expects a stopped machine and performs its
            # own explicit start, typically after inserting media.
            if phase == "running":
                raise self._error(
                    "the script expects a stopped machine, but "
                    f"machine "
                    f"{_machines.short_id(self._machine_id, self._home)} "
                    "is running; stop it first")
            if phase != "ready":
                raise self._error(
                    f"machine "
                    f"{_machines.short_id(self._machine_id, self._home)}"
                    f" cannot execute a script (phase: {phase})")
        elif phase == "ready":
            self._port = _machines.start(
                self._machine_id, display=display, home=self._home)
        elif phase == "running":
            state_path = _machines.machine_dir_path(
                self._machine_id, self._home)
            from .lifecycle import read_vm_state
            vm = read_vm_state(home=state_path)
            if vm is None:
                raise self._error(
                    "machine phase is running but no vm.json found")
            self._port = vm["port"]
        else:
            raise self._error(
                f"machine {_machines.short_id(self._machine_id, self._home)}"
                f" cannot execute a script (phase: {phase})")

        transcript_path = None
        if self._run_dir is not None:
            transcript_path = os.path.join(
                self._run_dir, "transcript.txt")
            self._transcript = open(
                transcript_path, "w", encoding="utf-8", newline="\n")
            self._log(f"script: {self._script_path or '<script>'}")
            self._log(f"machine: {self._machine_id}")
            started = datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ")
            self._log(f"started: {started}")
            if self._current_state is not None:
                self._log(f"initial: {self._current_state}")

        try:
            if self._current_state is not None:
                while self._current_state is not None:
                    if self._transcript is not None:
                        self._log(f"state: {self._current_state}")
                    state = self._script.states[self._current_state]
                    block_mods = dict(state.modifiers)
                    self._execute_block(state.statements, block_mods)
            else:
                self._execute_block(self._script.statements, {})
            if self._transcript is not None:
                self._log("result: ok")
        except (ScriptRuntimeError, TimeoutError, RuntimeError,
                ValueError) as exc:
            if self._transcript is not None:
                self._log(f"result: failed")
                self._log(f"error: {exc}")
            if isinstance(exc, ScriptRuntimeError) and exc.path is None:
                exc.path = self._script_path
            raise
        except Exception as exc:
            if self._transcript is not None:
                self._log("result: failed")
                self._log(f"error: {exc}")
            raise self._error(f"unexpected error: {exc}") from exc
        finally:
            if self._transcript is not None:
                self._transcript.close()
                self._transcript = None

    def _execute_block(self, statements, block_modifiers):
        for statement in statements:
            self._step += 1
            if statement.verb == "wait":
                self._do_wait(statement, block_modifiers)
            elif statement.verb == "expect":
                result_state = self._do_expect(statement, block_modifiers)
                if result_state is not None:
                    self._current_state = result_state
                    return
            elif statement.verb == "enter":
                self._do_enter(statement)
            elif statement.verb == "type":
                self._do_type(statement)
            elif statement.verb == "press":
                self._do_press(statement)
            elif statement.verb == "select":
                self._do_select(statement)
            elif statement.verb == "screenshot":
                self._do_screenshot(statement)
            elif statement.verb == "insert":
                self._do_insert(statement)
            elif statement.verb == "eject":
                self._do_eject(statement)
            elif statement.verb == "boot":
                self._do_boot(statement)
            elif statement.verb == "start":
                self._do_start()
            elif statement.verb == "stop":
                self._do_stop()
            elif statement.verb == "done":
                return
            elif statement.verb == "transition":
                self._current_state = statement.argument
                return

    def _session(self):
        if self._port is None:
            raise self._error(
                "the machine is not running; the script must start "
                "it first")
        try:
            return Qmp(self._port)
        except (OSError, ConnectError):
            raise self._error("machine is no longer reachable")

    def _console(self, qmp):
        return _DisplayConsole(qmp)

    def _machine(self):
        return Machine(self._port, self._machine_home)

    def _is_stopped(self):
        if self._port is None:
            return True
        try:
            with Qmp(self._port):
                pass
            return False
        except (OSError, ConnectError):
            return True

    def _do_wait(self, statement, block_modifiers):
        condition = statement.argument
        timeout = self._resolve_timeout(statement, block_modifiers)
        stable = self._resolve_stable(statement.modifiers)
        self._log(
            f"line {statement.line}: wait "
            f"{_describe_condition(condition)}")

        if condition.kind == "stopped":
            self._wait_stopped(timeout)
            return

        deadline = time.monotonic() + timeout
        stable_deadline = None
        last_match = False
        with self._session() as qmp:
            console = self._console(qmp)
            while time.monotonic() < deadline:
                screen = console.screen_text()
                line, matched = self._match_condition(
                    screen, condition)
                if matched:
                    if stable is not None:
                        if not last_match:
                            last_match = True
                            stable_deadline = (
                                time.monotonic() + stable)
                            time.sleep(1)
                            continue
                        if time.monotonic() < stable_deadline:
                            time.sleep(1)
                            continue
                    return
                else:
                    last_match = False
                time.sleep(2)
        raise self._error(
            f"timed out after {timeout}s waiting for "
            f"{_describe_condition(condition)}",
            statement=statement)

    def _wait_stopped(self, timeout):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._is_stopped():
                self._mark_stopped()
                return
            time.sleep(2)
        raise self._error(
            f"timed out after {timeout}s waiting for machine to stop")

    def _mark_stopped(self):
        """Reconcile state after observing the machine gone.

        The guest powered itself off, so the QEMU process exited
        without a reliquary ``stop``; the machine phase must return
        to ``ready`` for later insert/eject and ``start`` steps.
        """
        self._port = None
        try:
            _machines.mark_stopped(self._machine_id, home=self._home)
        except FileNotFoundError:
            pass

    def _do_expect(self, statement, block_modifiers):
        branches = statement.argument
        timeout = self._resolve_timeout(statement, block_modifiers)
        stable = self._resolve_stable(statement.modifiers)
        self._log(f"line {statement.line}: expect")

        deadline = time.monotonic() + timeout
        stable_deadline = None
        last_matched_branch = None
        with self._session() as qmp:
            console = self._console(qmp)
            while time.monotonic() < deadline:
                screen = console.screen_text()
                matched = None
                for branch in branches:
                    _line, branch_matched = self._match_condition(
                        screen, branch.condition)
                    if branch_matched:
                        matched = branch
                        break
                if matched is not None:
                    if stable is not None:
                        if last_matched_branch != matched:
                            last_matched_branch = matched
                            stable_deadline = (
                                time.monotonic() + stable)
                            time.sleep(1)
                            continue
                        if time.monotonic() < stable_deadline:
                            time.sleep(1)
                            continue
                    for substatement in matched.statements:
                        self._step += 1
                        if substatement.verb == "enter":
                            self._do_enter(substatement)
                        elif substatement.verb == "type":
                            self._do_type(substatement)
                        elif substatement.verb == "press":
                            self._do_press(substatement)
                        elif substatement.verb == "select":
                            self._do_select(substatement)
                        elif substatement.verb == "screenshot":
                            self._do_screenshot(substatement)
                        elif substatement.verb == "insert":
                            self._do_insert(substatement)
                        elif substatement.verb == "eject":
                            self._do_eject(substatement)
                        elif substatement.verb == "boot":
                            self._do_boot(substatement)
                        elif substatement.verb == "start":
                            self._do_start()
                        elif substatement.verb == "stop":
                            self._do_stop()
                        elif substatement.verb == "done":
                            return
                        elif substatement.verb == "transition":
                            return substatement.argument
                        elif substatement.verb == "wait":
                            self._do_wait(substatement, {})
                        elif substatement.verb == "expect":
                            result = self._do_expect(substatement, {})
                            if result is not None:
                                return result
                    return None
                else:
                    last_matched_branch = None
                time.sleep(2)
        raise self._error(
            f"timed out after {timeout}s waiting for any expect "
            f"condition to match",
            statement=statement)

    def _do_enter(self, statement):
        self._log(f"line {statement.line}: enter "
                  f"{statement.argument!r}")
        with self._session() as qmp:
            self._console(qmp).send_text(statement.argument)

    def _do_type(self, statement):
        text = statement.argument
        self._log(f"line {statement.line}: type {text!r}")
        combos = []
        index = 0
        for match in _KEY_RE.finditer(text):
            if match.start() > index:
                for char in text[index:match.start()]:
                    combos.append(char_keys(char))
            index = match.end()
            key_name = match.group(1)
            resolved = _resolve_key(key_name)
            if resolved is None:
                raise self._error(
                    f"unknown key: {key_name}",
                    statement=statement)
            if isinstance(resolved, tuple):
                combos.append(list(resolved))
            else:
                combos.append([resolved])
        if index < len(text):
            for char in text[index:]:
                combos.append(char_keys(char))
        with self._session() as qmp:
            console = self._console(qmp)
            for combo in combos:
                console.send_keys([combo])

    def _do_press(self, statement):
        keys = statement.argument
        self._log(f"line {statement.line}: press {' '.join(keys)}")
        combos = []
        for key_spec in keys:
            resolved = _resolve_key(key_spec)
            if resolved is None:
                raise self._error(
                    f"unknown key: {key_spec}",
                    statement=statement)
            if isinstance(resolved, tuple):
                combos.append(list(resolved))
            else:
                combos.append([resolved])
        with self._session() as qmp:
            self._console(qmp).send_keys(combos)

    def _do_select(self, statement):
        item = statement.argument
        exclude = statement.modifiers.get("exclude")
        detail = f"select {item!r}"
        if exclude:
            detail += f" (exclude: {exclude!r})"
        self._log(f"line {statement.line}: {detail}")
        with self._session() as qmp:
            self._console(qmp).cursor_menu_select(
                item, timeout=60,
                exclude=(exclude,) if exclude else ())

    def _do_screenshot(self, statement):
        name = statement.argument or f"step-{self._step}"
        name = validate_screenshot_name(name)
        self._log(f"line {statement.line}: screenshot {name}")
        if self._run_dir is not None:
            screenshot(name, self._port, self._run_dir)
        else:
            self._machine().screenshot(name)

    def _do_insert(self, statement):
        slot, media_name = statement.argument
        self._log(f"line {statement.line}: insert {slot} {media_name}")
        try:
            _machines.insert_media(
                self._machine_id, slot, media_name, home=self._home)
        except (RuntimeError, ValueError) as exc:
            raise self._error(str(exc), statement=statement) from exc

    def _do_eject(self, statement):
        slot = statement.argument
        self._log(f"line {statement.line}: eject {slot}")
        try:
            _machines.eject_media(
                self._machine_id, slot, home=self._home)
        except (RuntimeError, ValueError) as exc:
            raise self._error(str(exc), statement=statement) from exc

    def _do_boot(self, statement):
        keys = statement.argument
        self._log(f"line {statement.line}: boot {' '.join(keys)}")
        try:
            _machines.set_boot_order(
                self._machine_id, keys, home=self._home)
        except (RuntimeError, ValueError) as exc:
            raise self._error(str(exc), statement=statement) from exc

    def _do_start(self):
        self._log("start machine")
        self._port = _machines.start(
            self._machine_id, display=self._display, home=self._home)

    def _do_stop(self):
        self._log("stop machine")
        _machines.stop(self._machine_id, home=self._home)
        self._port = None

    def _match_condition(self, screen, condition):
        if condition.kind == "text":
            normalized = _normalize_screen_text(screen)
            target = _normalize_row(condition.value)
            for row_idx, row in enumerate(normalized):
                if target in row:
                    return row_idx, True
            return None, False
        elif condition.kind == "regex":
            normalized = _normalize_screen_text(screen)
            for row_idx, row in enumerate(normalized):
                if re.search(condition.value, row):
                    return row_idx, True
            return None, False
        elif condition.kind == "stopped":
            return None, self._is_stopped()
        return None, False

    def _resolve_timeout(self, statement, block_modifiers):
        mod = statement.modifiers.get("timeout")
        if mod is not None:
            return _parse_duration(mod)
        if "timeout" in block_modifiers:
            return _parse_duration(block_modifiers["timeout"])
        return self._default_timeout

    def _resolve_stable(self, modifiers):
        stable = modifiers.get("stable")
        if stable is not None:
            return _parse_duration(stable)
        return None


def _parse_duration(text):
    if text.endswith("ms"):
        return float(text[:-2]) / 1000.0
    if text.endswith("s"):
        return float(text[:-1])
    if text.endswith("m"):
        return float(text[:-1]) * 60.0
    if text.endswith("h"):
        return float(text[:-1]) * 3600.0
    return float(text)


def _describe_condition(condition):
    if condition.kind == "stopped":
        return "stopped"
    if condition.kind == "regex":
        return f"regex {condition.value!r}"
    return repr(condition.value)


def _resolve_or_create_machine(*, machine=None, blueprint=None,
                               home=None):
    """Resolve a selector, creating a machine when blueprint has none."""
    if machine is not None and blueprint is not None:
        raise ValueError(
            "--blueprint and --machine are mutually exclusive")
    if machine is not None:
        return _machines.resolve_machine(
            machine=machine, home=home), False
    if blueprint is None:
        raise ValueError(
            "select a machine with --blueprint or --machine")
    matches = _machines.list_machines(home, blueprint=blueprint)
    if not matches:
        machine_id = _machines.create_from_blueprint(
            blueprint, home=home)
        return machine_id, True
    return _machines.resolve_machine(
        blueprint=blueprint, home=home), False


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


def _ensure_script_path(stem, home=None):
    """Return the home path for ``stem``, seeding from builtins if needed."""
    path = os.path.join(scripts_dir(home), f"{stem}.rlqs")
    if not os.path.isfile(path):
        seed_script(stem, home=home)
    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"script not found: {stem}.rlqs\n"
            f"expected under {scripts_dir(home)}")
    return path


def _create_run_dir(machine_id, home=None):
    """Create ``runs/<timestamp>-<id>/`` under the machine cache."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = uuid.uuid4().hex[:8]
    run_dir = os.path.join(
        _machines.machine_dir_path(machine_id, home),
        "runs",
        f"{timestamp}-{run_id}",
    )
    os.makedirs(os.path.join(run_dir, "screenshots"), exist_ok=True)
    os.makedirs(os.path.join(run_dir, "output"), exist_ok=True)
    return run_dir


def _walk_statements(statements):
    """Yield every statement, descending into expect branches."""
    for statement in statements:
        yield statement
        if statement.verb == "expect":
            for branch in statement.argument:
                yield from _walk_statements(branch.statements)


def _iter_statements(script):
    """Yield every statement of a linear or state-machine script."""
    yield from _walk_statements(script.statements)
    for state in script.states.values():
        yield from _walk_statements(state.statements)


_REMOVABLE_MEDIA = frozenset({"floppy", "cdrom"})


def _preflight_media_slots(script, machine_state, script_path):
    """Fail before any guest input when a script names an
    undeclared slot or boot drive.

    ``insert``/``eject``/``boot`` never create or remove a drive —
    the blueprint alone defines machine topology — so every named
    slot must exist in the machine's state.  ``insert``/``eject``
    further require a floppy or cdrom slot.
    """
    drives = machine_state.get("drives", {})
    for statement in _iter_statements(script):
        if statement.verb == "insert":
            slots = (statement.argument[0],)
            removable_only = True
        elif statement.verb == "eject":
            slots = (statement.argument,)
            removable_only = True
        elif statement.verb == "boot":
            slots = statement.argument
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


def execute_script(script, *, machine_id, home=None, display=False,
                   run_dir=None, script_path=None):
    """Execute a parsed Script against a cached machine.

    The machine state the script's ``machine:`` header expects is
    established first: the default ``running`` starts a ready
    machine, while ``stopped`` requires a stopped machine and
    leaves starting to the script itself.  The machine is left in
    whatever state the last executed step produced.

    When ``run_dir`` is set, a transcript is written there and
    screenshots land under ``run_dir/screenshots/``.
    """
    if not script.states and not script.statements:
        return

    _preflight_media_slots(
        script, _machines.load_machine_state(machine_id, home),
        script_path)
    machine_home = _machines.machine_dir_path(machine_id, home)
    engine = _ScriptEngine(
        script, machine_id, home, machine_home,
        run_dir=run_dir, script_path=script_path)
    engine.run(display=display)


def run_script(label, *, blueprint=None, machine=None, home=None,
               display=False):
    """Resolve ``label``, ensure a machine, and execute under ``runs/``.

    Looks up ``label`` in the machine's blueprint ``scripts`` map
    first; when absent, treats ``label`` as a bare script stem under
    ``scripts/``.  With ``--blueprint`` and no machine yet, creates
    one.  Returns a :class:`ScriptRun` naming the run directory.
    """
    machine_id, created = _resolve_or_create_machine(
        machine=machine, blueprint=blueprint, home=home)
    state = _machines.load_machine_state(machine_id, home)
    stem = _resolve_script_stem(label, state.get("scripts") or {})
    script_path = _ensure_script_path(stem, home=home)
    script = load_script(script_path)
    run_dir = _create_run_dir(machine_id, home=home)
    execute_script(
        script, machine_id=machine_id, home=home, display=display,
        run_dir=run_dir, script_path=script_path)
    return ScriptRun(
        machine_id=machine_id,
        run_dir=run_dir,
        script_path=script_path,
        created_machine=created,
    )
