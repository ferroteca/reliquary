# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Generic interaction with and diagnostics for a running QEMU machine."""

import contextlib
import dataclasses
import os
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
