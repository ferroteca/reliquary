# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Agentless DOS interaction through QMP keyboard input and VGA text."""

import difflib
import re
import time

from .machine import Machine, vga_screen, vga_text


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


def _normalize(text):
    """Fold case and whitespace for tolerant menu-text comparison."""
    return " ".join(text.split()).casefold()


def _match_menu_row(rows, item):
    """Return the single screen row whose text contains the item."""
    target = _normalize(item)
    matches = [row for row, text in enumerate(rows)
               if target in _normalize(text)]
    if len(matches) == 1:
        return matches[0]
    if matches:
        listed = ", ".join(repr(rows[row].strip()) for row in matches)
        raise ValueError(
            f"menu item {item!r} matches multiple rows: {listed}")
    candidates = {_normalize(text): text.strip()
                  for text in rows if text.strip()}
    close = difflib.get_close_matches(target, candidates, n=3,
                                      cutoff=0.5)
    hint = ("; closest rows: "
            + ", ".join(repr(candidates[text]) for text in close)
            if close else "")
    raise ValueError(f"menu item {item!r} is not on screen{hint}")


def _cursor_row(before, attributes):
    """Locate the menu highlight from an observed attribute change.

    The rows whose attributes changed after a cursor keypress are the
    old and new cursor positions. Of those, the newly highlighted row
    is the one whose changed cells now carry the rarest attribute on
    screen: the normal menu color covers many rows, the selection bar
    exactly one. Returns None when nothing changed.
    """
    changed = [row for row in range(len(attributes))
               if attributes[row] != before[row]]
    if not changed:
        return None
    frequency = {}
    for row_attributes in attributes:
        for attribute in row_attributes:
            frequency[attribute] = frequency.get(attribute, 0) + 1

    def rarity(row):
        counts = {}
        for old, new in zip(before[row], attributes[row]):
            if old != new:
                counts[new] = counts.get(new, 0) + 1
        return frequency[max(counts, key=counts.get)]

    return min(changed, key=rarity)


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
        return vga_text(self._qmp)

    def screen(self):
        """Return the VGA screen as (text rows, attribute rows)."""
        return vga_screen(self._qmp)

    def cursor_menu_select(self, item, timeout=30):
        """Steer a cursor-key menu onto a matching item and press ENTER.

        Presses up/down and observes the VGA attribute bytes to follow
        the selection highlight, so the choice is confirmed by what the
        guest displays rather than by counting keystrokes. Returns the
        selected row's text.
        """
        if not _normalize(item):
            raise ValueError("menu item text must be non-empty")
        deadline = time.monotonic() + timeout
        rows, attributes = self.screen()
        target_row = _match_menu_row(rows, item)
        current = None
        for key in ("down", "up"):
            self.send_keys([[key]])
            observed = self._settled_screen(attributes, deadline)
            if observed is not None:
                rows, changed = observed
                current = _cursor_row(attributes, changed)
                attributes = changed
                break
        if current is None:
            raise RuntimeError(
                "no menu highlight responded to cursor keys; cannot "
                f"select {item!r}")
        while current != target_row:
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"menu highlight never reached {item!r} within "
                    f"{timeout}s; is it a selectable menu item?")
            key = "down" if current < target_row else "up"
            self.send_keys([[key]])
            observed = self._settled_screen(attributes, deadline)
            if observed is None:
                raise RuntimeError(
                    "menu highlight stopped responding before "
                    f"reaching {item!r}")
            rows, changed = observed
            moved = _cursor_row(attributes, changed)
            attributes = changed
            if moved is not None:
                current = moved
            target_row = _match_menu_row(rows, item)
        selected = rows[target_row].strip()
        self.send_keys([["ret"]])
        return selected

    def _settled_screen(self, before, deadline, wait=1.5):
        """Poll until the screen attributes change, or return None."""
        end = min(deadline, time.monotonic() + wait)
        while True:
            rows, attributes = self.screen()
            if attributes != before:
                return rows, attributes
            if time.monotonic() >= end:
                return None
            time.sleep(0.1)


class AgentlessGuestExec:
    """Concrete GuestExec adapter for an agentless DOS guest."""

    def __init__(self, machine: Machine):
        self._machine = machine

    def wait_ready(self, timeout: float = 90) -> None:
        """Wait for a DOS prompt."""
        print("waiting for a DOS prompt...")
        with self._machine.qmp() as qmp:
            console = _DisplayConsole(qmp)
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                rows = [row for row in console.screen_text() if row]
                if rows and _PROMPT_RE.match(rows[-1]):
                    print(f"at DOS prompt: {rows[-1]}")
                    return
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


def cursor_menu_select(item, timeout=30, port=None, home=None):
    """Select a matching item in a cursor-key menu and press ENTER."""
    with Machine(port, home).qmp() as qmp:
        return _DisplayConsole(qmp).cursor_menu_select(item, timeout)


def screen_text(port=None, home=None):
    """Return the guest's 80x25 VGA text screen."""
    return Machine(port, home).screen_text()


def wait_text(pattern, timeout=60, port=None, home=None):
    """Wait until the VGA text screen matches a regular expression."""
    return Machine(port, home).wait_text(pattern, timeout)
