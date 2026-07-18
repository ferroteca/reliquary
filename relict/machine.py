# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Generic agentless interaction with a running QEMU machine."""

import dataclasses
import os
import re
import struct
import time
import zlib

from qemu.qmp import ExecuteError

from .home import effective_home
from .lifecycle import qmp_session


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


def send_keys(combos, port=None, delay=0.06, home=None):
    """Send a list of qcode combinations to the guest."""
    with qmp_session(port, home) as qmp:
        for combo in combos:
            qmp.cmd("send-key",
                    keys=[{"type": "qcode", "data": key}
                          for key in combo])
            time.sleep(delay)


def send_text(text, port=None, enter=True, home=None):
    combos = [char_keys(character) for character in text]
    if enter:
        combos.append(["ret"])
    if home is None:
        send_keys(combos, port)
    else:
        send_keys(combos, port, home=home)


def screen_text(port=None, home=None):
    """Return the guest's 80x25 VGA text screen."""
    with qmp_session(port, home) as qmp:
        raw = qmp.hmp("xp /4000bx 0xb8000")
    data = []
    for line in raw.splitlines():
        if not re.match(r"^[0-9a-f]+:", line):
            continue
        data.extend(int(token, 16) for token in line.split()[1:])
    rows = []
    for row in range(25):
        chars = data[row * 160:(row + 1) * 160:2]
        rows.append("".join(chr(byte) if 32 <= byte < 127 else " "
                            for byte in chars).rstrip())
    return rows


def wait_screen(pattern, timeout=60, port=None, home=None):
    with qmp_session(port, home) as qmp:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            screen = "\n".join(screen_text(qmp))
            if re.search(pattern, screen):
                return screen
            time.sleep(2)
    raise TimeoutError(
        f"timed out after {timeout}s waiting for screen to match: {pattern}")


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


@dataclasses.dataclass(frozen=True)
class Machine:
    """A running, relict-owned VM passed to generic remote tasks."""

    port: int
    home: str
    deadline: "float | None" = None

    def qmp(self, name, **arguments):
        with qmp_session(self.port, self.home) as qmp:
            return qmp.cmd(name, **arguments)

    def hmp(self, command_line):
        with qmp_session(self.port, self.home) as qmp:
            return qmp.hmp(command_line)

    def send_keys(self, combos, delay=0.06):
        return send_keys(combos, self.port, delay, self.home)

    def send_text(self, text, enter=True):
        return send_text(text, self.port, enter, self.home)

    def screen_text(self):
        return screen_text(self.port, self.home)

    def wait_screen(self, pattern, timeout=60):
        return wait_screen(pattern, timeout, self.port, self.home)

    def screenshot(self, name="screen"):
        return screenshot(name, self.port, self.home)
