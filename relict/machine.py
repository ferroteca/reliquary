# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Generic interaction with and diagnostics for a running QEMU machine."""

import contextlib
import dataclasses
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
