# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Generic interaction with and diagnostics for a running QEMU machine."""

import contextlib
import dataclasses
import difflib
import os
import re
import struct
import time
import zlib

from qemu.qmp import ExecuteError

from .home import effective_home
from .lifecycle import qmp_session


def _write_png(path, width, height, rgb):
    def chunk(kind, payload):
        output = struct.pack(">I", len(payload)) + kind + payload
        return output + struct.pack(">I", zlib.crc32(kind + payload))

    raw = b"".join(b"\x00" + rgb[row * width * 3:(row + 1) * width * 3]
                   for row in range(height))
    with open(path, "wb") as png_file:
        png_file.write(b"\x89PNG\r\n\x1a\n")
        png_file.write(chunk(
            b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)))
        png_file.write(chunk(b"IDAT", zlib.compress(raw)))
        png_file.write(chunk(b"IEND", b""))


def validate_screenshot_name(name):
    """Return a filename-only screenshot name that cannot escape home."""
    name = os.fspath(name)
    if (not isinstance(name, str) or not name or name in (".", "..")
            or os.path.basename(name) != name
            or "/" in name or "\\" in name):
        raise ValueError(
            "screenshot name must be a non-empty filename, not a path")
    return name


def screenshot(name="screen", port=None, home=None):
    name = validate_screenshot_name(name)
    screenshots = os.path.join(effective_home(home), "screenshots")
    os.makedirs(screenshots, exist_ok=True)
    ppm = os.path.join(screenshots, f"{name}.ppm")
    with qmp_session(port, home) as qmp:
        try:
            png = os.path.join(screenshots, f"{name}.png")
            qmp.cmd("screendump", filename=png.replace("\\", "/"),
                    format="png")
            print(f"saved {png}")
            return
        except ExecuteError:
            pass
        qmp.cmd("screendump", filename=ppm.replace("\\", "/"))
    time.sleep(0.3)
    with open(ppm, "rb") as ppm_file:
        data = ppm_file.read()
    tokens = []
    position = 0
    while len(tokens) < 4:
        while chr(data[position]).isspace():
            position += 1
        end = position
        while not chr(data[end]).isspace():
            end += 1
        tokens.append(data[position:end].decode())
        position = end
    position += 1
    if tokens[0] != "P6":
        raise ValueError("unexpected screendump format")
    width, height = int(tokens[1]), int(tokens[2])
    png = os.path.join(screenshots, f"{name}.png")
    _write_png(png, width, height,
               data[position:position + width * height * 3])
    os.remove(ppm)
    print(f"saved {png}")


def vga_screen(qmp):
    """Return the 80x25 VGA text screen as (text rows, attribute rows).

    Text rows are right-stripped strings; attribute rows keep the raw
    VGA attribute byte of all 80 cells, so callers can observe color
    effects such as a menu selection highlight.
    """
    raw = qmp.hmp("xp /4000bx 0xb8000")
    data = []
    for line in raw.splitlines():
        if not re.match(r"^[0-9a-f]+:", line):
            continue
        data.extend(int(token, 16) for token in line.split()[1:])
    rows = []
    attributes = []
    for row in range(25):
        cells = data[row * 160:(row + 1) * 160]
        rows.append("".join(
            chr(byte) if 32 <= byte < 127 else " "
            for byte in cells[0::2]).rstrip())
        attributes.append(cells[1::2])
    return rows, attributes


def vga_text(qmp):
    """Return the guest's 80x25 VGA text screen over an open session."""
    return vga_screen(qmp)[0]


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
    """Keyboard input and VGA-text composition over an open session.

    Shared by `Machine` methods and interaction adapters that hold a
    session across several exchanges.
    """

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


@dataclasses.dataclass(frozen=True)
class Machine:
    """A running, relict-owned VM passed to generic remote tasks."""

    port: "int | None" = None
    home: "str | None" = None
    deadline: "float | None" = None

    @contextlib.contextmanager
    def qmp(self):
        """Yield an identity-verified QMP session for this machine."""
        with qmp_session(self.port, self.home) as qmp:
            yield qmp

    def screenshot(self, name="screen"):
        return screenshot(name, self.port, self.home)

    def send_keys(self, combos, delay=0.06):
        """Send a list of qcode combinations to the guest."""
        with self.qmp() as qmp:
            return _DisplayConsole(qmp).send_keys(combos, delay)

    def send_text(self, text, enter=True):
        """Type text on the guest keyboard, with Enter by default."""
        with self.qmp() as qmp:
            return _DisplayConsole(qmp).send_text(text, enter)

    def cursor_menu_select(self, item, timeout=30):
        """Select a matching item in a cursor-key menu and press ENTER."""
        with self.qmp() as qmp:
            return _DisplayConsole(qmp).cursor_menu_select(item, timeout)

    def screen_text(self):
        """Return the guest's 80x25 VGA text screen."""
        with self.qmp() as qmp:
            return vga_text(qmp)

    def wait_text(self, pattern, timeout=60):
        """Wait until the VGA text screen matches a regular expression.

        Returns the matching screen as one newline-joined string.
        """
        with self.qmp() as qmp:
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                screen = "\n".join(vga_text(qmp))
                if re.search(pattern, screen):
                    return screen
                time.sleep(2)
        raise TimeoutError(
            f"timed out after {timeout}s waiting for screen to match: "
            f"{pattern}")


def send_keys(combos, port=None, delay=0.06, home=None):
    """Send a list of qcode combinations to the guest."""
    return Machine(port, home).send_keys(combos, delay)


def send_text(text, port=None, enter=True, home=None):
    """Type text on the guest keyboard, with Enter by default."""
    return Machine(port, home).send_text(text, enter)


def cursor_menu_select(item, timeout=30, port=None, home=None):
    """Select a matching item in a cursor-key menu and press ENTER."""
    return Machine(port, home).cursor_menu_select(item, timeout)


def screen_text(port=None, home=None):
    """Return the guest's 80x25 VGA text screen."""
    return Machine(port, home).screen_text()


def wait_text(pattern, timeout=60, port=None, home=None):
    """Wait until the VGA text screen matches a regular expression."""
    return Machine(port, home).wait_text(pattern, timeout)
