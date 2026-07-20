# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Runtime executor for milestone-one .rqs scripts on QEMU/DOS."""

import re
import time

from qemu.qmp import ConnectError

from .lifecycle import Qmp
from .machine import (Machine, _DisplayConsole, char_keys,
                      validate_screenshot_name)
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


class _ScriptEngine:
    def __init__(self, script, machine_id, home, machine_home):
        self._script = script
        self._machine_id = machine_id
        self._home = home
        self._machine_home = machine_home
        self._port = None
        self._current_state = script.initial
        self._step = 0

    @property
    def _default_timeout(self):
        if self._script.timeout is not None:
            return _parse_duration(self._script.timeout)
        return 30.0

    def run(self, display=False):
        state = _machines.load_machine_state(self._machine_id, self._home)
        phase = state.get("phase")
        if phase == "ready":
            self._port = _machines.start(
                self._machine_id, display=display, home=self._home)
        elif phase == "running":
            vm_state = _machines.load_machine_state(
                self._machine_id, self._home)
            state_path = _machines.machine_dir_path(
                self._machine_id, self._home)
            from .lifecycle import read_vm_state
            vm = read_vm_state(home=state_path)
            if vm is None:
                raise ScriptRuntimeError(
                    "machine phase is running but no vm.json found")
            self._port = vm["port"]
        else:
            raise ScriptRuntimeError(
                f"machine {_machines.short_id(self._machine_id, self._home)}"
                f" cannot execute a script (phase: {phase})")

        try:
            if self._current_state is not None:
                while self._current_state is not None:
                    state = self._script.states[self._current_state]
                    block_mods = dict(state.modifiers)
                    self._execute_block(state.statements, block_mods)
            else:
                self._execute_block(self._script.statements, {})
        except (ScriptRuntimeError, TimeoutError, RuntimeError,
                ValueError):
            raise
        except Exception as exc:
            raise ScriptRuntimeError(
                f"unexpected error: {exc}") from exc

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
        try:
            return Qmp(self._port)
        except (OSError, ConnectError):
            raise ScriptRuntimeError("machine is no longer reachable")

    def _console(self, qmp):
        return _DisplayConsole(qmp)

    def _machine(self):
        return Machine(self._port, self._machine_home)

    def _is_stopped(self):
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
        raise ScriptRuntimeError(
            f"timed out after {timeout}s waiting for "
            f"{_describe_condition(condition)}",
            statement=statement)

    def _wait_stopped(self, timeout):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._is_stopped():
                return
            time.sleep(2)
        raise ScriptRuntimeError(
            f"timed out after {timeout}s waiting for machine to stop")

    def _do_expect(self, statement, block_modifiers):
        branches = statement.argument
        timeout = self._resolve_timeout(statement, block_modifiers)
        stable = self._resolve_stable(statement.modifiers)

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
        raise ScriptRuntimeError(
            f"timed out after {timeout}s waiting for any expect "
            f"condition to match",
            statement=statement)

    def _do_enter(self, statement):
        print(f"enter: {statement.argument!r}")
        with self._session() as qmp:
            self._console(qmp).send_text(statement.argument)

    def _do_type(self, statement):
        text = statement.argument
        print(f"type: {text!r}")
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
                raise ScriptRuntimeError(
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
        print(f"press: {' '.join(keys)}")
        combos = []
        for key_spec in keys:
            resolved = _resolve_key(key_spec)
            if resolved is None:
                raise ScriptRuntimeError(
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
        print(f"select: {item!r}"
              + (f" (exclude: {exclude!r})" if exclude else ""))
        with self._session() as qmp:
            self._console(qmp).cursor_menu_select(
                item, timeout=60,
                exclude=(exclude,) if exclude else ())

    def _do_screenshot(self, statement):
        name = statement.argument or f"step-{self._step}"
        name = validate_screenshot_name(name)
        self._machine().screenshot(name)

    def _do_start(self):
        print("start machine")
        self._port = _machines.start(
            self._machine_id, home=self._home)

    def _do_stop(self):
        print("stop machine")
        _machines.stop(self._machine_id, home=self._home)

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


def execute_script(script, *, machine_id, home=None, display=False):
    """Execute a parsed Script against a cached machine.

    The machine must be in ``ready`` or ``running`` phase.  When it
    is ready it is started first; when it is running execution
    connects to its QMP port.  The machine is left running at exit
    unless the script stopped it.
    """
    if not script.states and not script.statements:
        return

    machine_home = _machines.machine_dir_path(machine_id, home)
    engine = _ScriptEngine(script, machine_id, home, machine_home)
    engine.run(display=display)
