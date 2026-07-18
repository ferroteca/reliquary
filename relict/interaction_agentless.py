# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Agentless DOS interaction through QMP keyboard input and VGA text."""

import re
import time

from .machine import Machine


_PROMPT_RE = re.compile(r"^[A-Z]:(\\[^>]*)?>$")
_SHIFTED = {
    ":": "semicolon", "_": "minus", "?": "slash", '"': "apostrophe",
    "!": "1", "@": "2", "#": "3", "$": "4", "%": "5", "^": "6",
    "&": "7", "*": "8", "(": "9", ")": "0", "+": "equal",
    "<": "comma", ">": "dot", "{": "bracket_left", "}": "bracket_right",
    "|": "backslash", "~": "grave_accent",
}
_PLAIN = {
    " ": "spc", ".": "dot", "-": "minus", "=": "equal",
    "\\": "backslash", "/": "slash", ";": "semicolon", ",": "comma",
    "'": "apostrophe", "[": "bracket_left", "]": "bracket_right",
    "`": "grave_accent", "\n": "ret",
}


def char_keys(character):
    """Map one character to a simultaneous QEMU qcode combination."""
    if character in _PLAIN:
        return [_PLAIN[character]]
    if character in _SHIFTED:
        return ["shift", _SHIFTED[character]]
    if character.islower() or character.isdigit():
        return [character]
    if character.isupper():
        return ["shift", character.lower()]
    raise ValueError(f"no key mapping for {character!r}")


class _DisplayConsole:
    """Keyboard-input and VGA-text composition used by the adapter."""

    def __init__(self, qmp):
        self._qmp = qmp

    def send_keys(self, combos, delay=0.06):
        """Send a list of qcode combinations to the guest."""
        for combo in combos:
            self._qmp.cmd(
                "send-key",
                keys=[{"type": "qcode", "data": key}
                      for key in combo])
            time.sleep(delay)

    def send_text(self, text, enter=True):
        combos = [char_keys(character) for character in text]
        if enter:
            combos.append(["ret"])
        self.send_keys(combos)

    def screen_text(self):
        """Return the guest's 80x25 VGA text screen."""
        raw = self._qmp.hmp("xp /4000bx 0xb8000")
        data = []
        for line in raw.splitlines():
            if not re.match(r"^[0-9a-f]+:", line):
                continue
            data.extend(int(token, 16) for token in line.split()[1:])
        rows = []
        for row in range(25):
            chars = data[row * 160:(row + 1) * 160:2]
            rows.append("".join(
                chr(byte) if 32 <= byte < 127 else " "
                for byte in chars).rstrip())
        return rows


class AgentlessGuestExec:
    """Concrete GuestExec adapter for an agentless DOS guest."""

    def __init__(self, machine: Machine):
        self._machine = machine

    def wait_ready(self, timeout: float = 90) -> None:
        """Wait for a DOS prompt, declining the FreeDOS installer."""
        print("waiting for a DOS prompt...")
        installer_seen = False
        with self._machine.qmp() as qmp:
            console = _DisplayConsole(qmp)
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                rows = [row for row in console.screen_text() if row]
                if rows and _PROMPT_RE.match(rows[-1]):
                    print(f"at DOS prompt: {rows[-1]}")
                    return
                if (not installer_seen
                        and any("Do you want to proceed" in row
                                for row in rows)):
                    installer_seen = True
                    print("FreeDOS installer detected; "
                          "declining the install...")
                    console.send_text("n")
                time.sleep(2)
        raise TimeoutError(
            f"timed out after {timeout}s waiting for a DOS prompt")

    def execute(self, command: str, timeout: float = 120) -> None:
        """Type a DOS command and wait for the prompt to return."""
        with self._machine.qmp() as qmp:
            console = _DisplayConsole(qmp)
            console.send_text(command)
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                rows = [row for row in console.screen_text() if row]
                if rows and _PROMPT_RE.match(rows[-1]):
                    return
                time.sleep(2)
        raise TimeoutError(
            f"timed out after {timeout}s waiting for command to finish: "
            f"{command}")


def send_keys(combos, port=None, delay=0.06, home=None):
    """Send a list of qcode combinations to the guest."""
    with Machine(port, home).qmp() as qmp:
        return _DisplayConsole(qmp).send_keys(combos, delay)


def send_text(text, port=None, enter=True, home=None):
    with Machine(port, home).qmp() as qmp:
        return _DisplayConsole(qmp).send_text(text, enter)


def screen_text(port=None, home=None):
    """Return the guest's 80x25 VGA text screen."""
    with Machine(port, home).qmp() as qmp:
        return _DisplayConsole(qmp).screen_text()


def wait_screen(pattern, timeout=60, port=None, home=None):
    with Machine(port, home).qmp() as qmp:
        console = _DisplayConsole(qmp)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            screen = "\n".join(console.screen_text())
            if re.search(pattern, screen):
                return screen
            time.sleep(2)
    raise TimeoutError(
        f"timed out after {timeout}s waiting for screen to match: {pattern}")
