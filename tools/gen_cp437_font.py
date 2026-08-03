# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Generate Reliquary's original CP437 8x16 glyph bank.

Original work: a fixed-width bitmap font in the CP437 code layout,
drawn for Reliquary's text-screen recognizer (F51). It is *not* a
dump of an IBM ROM or a third-party font file — shapes are authored
here so the project owns every byte it ships.
"""

from __future__ import annotations

import os
import zlib


W, H = 8, 16
N = 256


def _blank():
    return [0] * H


def _set(rows, x, y):
    if 0 <= x < W and 0 <= y < H:
        rows[y] |= 1 << (7 - x)


def _hline(rows, y, x0, x1):
    for x in range(x0, x1 + 1):
        _set(rows, x, y)


def _vline(rows, x, y0, y1):
    for y in range(y0, y1 + 1):
        _set(rows, x, y)


def _rect(rows, x0, y0, x1, y1, fill=False):
    if fill:
        for y in range(y0, y1 + 1):
            _hline(rows, y, x0, x1)
    else:
        _hline(rows, y0, x0, x1)
        _hline(rows, y1, x0, x1)
        _vline(rows, x0, y0, y1)
        _vline(rows, x1, y0, y1)


def _plot_points(rows, points):
    for x, y in points:
        _set(rows, x, y)


# Stroke descriptions for ASCII 0x20-0x7E: lists of (x, y) pixels,
# authored for an 8x16 cell with a 1-pixel margin.
_ASCII = {}


def _define_ascii():
    """Populate ``_ASCII`` with hand-drawn printable glyphs."""
    # Space stays blank.
    _ASCII[0x20] = []

    def dig(code, strokes):
        _ASCII[code] = strokes

    # Digits 0-9
    dig(0x30, _oval(2, 3, 5, 12) + _vline_pts(2, 4, 11) + _vline_pts(5, 4, 11))
    dig(0x31, _vline_pts(4, 3, 12) + [(3, 4)] + _hline_pts(2, 12, 6))
    dig(0x32, (_hline_pts(2, 3, 5) + [(5, 4), (5, 5), (4, 6), (3, 7),
                (2, 8), (2, 9)] + _hline_pts(2, 12, 5)))
    dig(0x33, (_hline_pts(2, 3, 5) + [(5, 4), (5, 5)] + _hline_pts(3, 7, 5)
               + [(5, 8), (5, 9), (5, 10), (5, 11)] + _hline_pts(2, 12, 5)))
    dig(0x34, (_vline_pts(2, 3, 8) + _hline_pts(2, 8, 5) + _vline_pts(5, 3, 12)))
    dig(0x35, (_hline_pts(2, 3, 5) + _vline_pts(2, 3, 7) + _hline_pts(2, 7, 5)
               + [(5, 8), (5, 9), (5, 10), (5, 11)] + _hline_pts(2, 12, 5)))
    dig(0x36, (_hline_pts(3, 3, 5) + [(2, 4), (2, 5), (2, 6), (2, 7), (2, 8),
                (2, 9), (2, 10), (2, 11)] + _hline_pts(2, 7, 5)
               + [(5, 8), (5, 9), (5, 10), (5, 11)] + _hline_pts(2, 12, 5)))
    dig(0x37, _hline_pts(2, 3, 5) + [(5, 4), (4, 6), (4, 7), (3, 9),
                                    (3, 10), (3, 12)])
    dig(0x38, (_oval(2, 3, 5, 7) + _oval(2, 7, 5, 12)))
    dig(0x39, (_hline_pts(2, 3, 5) + [(2, 4), (2, 5), (2, 6), (5, 4), (5, 5),
                (5, 6)] + _hline_pts(2, 7, 5) + [(5, 8), (5, 9), (5, 10),
                (5, 11)] + _hline_pts(2, 12, 4)))

    # Uppercase A-Z (simplified but distinctive)
    dig(0x41, [(2, 12), (2, 11), (2, 10), (3, 9), (3, 8), (4, 7), (4, 6),
               (4, 5), (4, 4), (3, 3), (5, 3), (5, 4), (5, 5), (5, 6),
               (5, 7), (6, 8), (6, 9), (6, 10), (6, 11), (6, 12)]
              + _hline_pts(2, 8, 6))
    dig(0x42, (_vline_pts(2, 3, 12) + _hline_pts(2, 3, 5) + [(5, 4), (5, 5)]
               + _hline_pts(2, 6, 5) + [(5, 7), (5, 8)] + _hline_pts(2, 9, 5)
               + [(5, 10), (5, 11)] + _hline_pts(2, 12, 5)))
    dig(0x43, (_hline_pts(3, 3, 5) + [(2, 4), (2, 5), (2, 6), (2, 7), (2, 8),
                (2, 9), (2, 10), (2, 11)] + _hline_pts(3, 12, 5) + [(6, 4),
                (6, 11)]))
    dig(0x44, (_vline_pts(2, 3, 12) + _hline_pts(2, 3, 4) + [(5, 4), (6, 5),
                (6, 6), (6, 7), (6, 8), (6, 9), (6, 10), (5, 11)]
               + _hline_pts(2, 12, 4)))
    dig(0x45, (_vline_pts(2, 3, 12) + _hline_pts(2, 3, 6) + _hline_pts(2, 7, 5)
               + _hline_pts(2, 12, 6)))
    dig(0x46, (_vline_pts(2, 3, 12) + _hline_pts(2, 3, 6) + _hline_pts(2, 7, 5)))
    dig(0x47, (_hline_pts(3, 3, 5) + [(2, 4), (2, 5), (2, 6), (2, 7), (2, 8),
                (2, 9), (2, 10), (2, 11)] + _hline_pts(3, 12, 5) + [(6, 4),
                (6, 8), (6, 9), (6, 10), (6, 11), (5, 8)]))
    dig(0x48, (_vline_pts(2, 3, 12) + _vline_pts(6, 3, 12) + _hline_pts(2, 7, 6)))
    dig(0x49, (_hline_pts(3, 3, 5) + _vline_pts(4, 3, 12) + _hline_pts(3, 12, 5)))
    dig(0x4A, (_hline_pts(4, 3, 6) + _vline_pts(5, 3, 11) + [(2, 10), (2, 11),
                (3, 12), (4, 12)]))
    dig(0x4B, (_vline_pts(2, 3, 12) + [(6, 3), (5, 4), (4, 5), (3, 6), (3, 7),
                (4, 8), (5, 9), (6, 10), (6, 11), (6, 12)]))
    dig(0x4C, (_vline_pts(2, 3, 12) + _hline_pts(2, 12, 6)))
    dig(0x4D, (_vline_pts(2, 3, 12) + _vline_pts(6, 3, 12) + [(3, 4), (3, 5),
                (4, 6), (4, 7), (5, 4), (5, 5)]))
    dig(0x4E, (_vline_pts(2, 3, 12) + _vline_pts(6, 3, 12) + [(3, 5), (3, 6),
                (4, 7), (4, 8), (5, 9), (5, 10)]))
    dig(0x4F, _oval(2, 3, 6, 12))
    dig(0x50, (_vline_pts(2, 3, 12) + _hline_pts(2, 3, 5) + [(5, 4), (5, 5),
                (5, 6)] + _hline_pts(2, 7, 5)))
    dig(0x51, _oval(2, 3, 6, 12) + [(5, 10), (6, 11), (6, 12)])
    dig(0x52, (_vline_pts(2, 3, 12) + _hline_pts(2, 3, 5) + [(5, 4), (5, 5),
                (5, 6)] + _hline_pts(2, 7, 5) + [(4, 8), (5, 9), (6, 10),
                (6, 11), (6, 12)]))
    dig(0x53, (_hline_pts(3, 3, 5) + [(2, 4), (2, 5), (2, 6)] + _hline_pts(2, 7, 5)
               + [(5, 8), (5, 9), (5, 10), (5, 11)] + _hline_pts(2, 12, 4)
               + [(6, 4), (2, 11)]))
    dig(0x54, (_hline_pts(2, 3, 6) + _vline_pts(4, 3, 12)))
    dig(0x55, (_vline_pts(2, 3, 11) + _vline_pts(6, 3, 11) + _hline_pts(3, 12, 5)))
    dig(0x56, ([(2, 3), (2, 4), (2, 5), (2, 6), (3, 7), (3, 8), (3, 9),
                (4, 10), (4, 11), (4, 12), (5, 9), (5, 8), (5, 7), (6, 6),
                (6, 5), (6, 4), (6, 3)]))
    dig(0x57, (_vline_pts(1, 3, 10) + _vline_pts(6, 3, 10) + [(2, 11), (3, 12),
                (3, 8), (3, 9), (4, 7), (4, 8), (5, 11), (4, 12), (5, 9)]))
    dig(0x58, ([(2, 3), (3, 4), (3, 5), (4, 6), (4, 7), (4, 8), (3, 9), (3, 10),
                (2, 11), (2, 12), (6, 3), (5, 4), (5, 5), (5, 9), (5, 10),
                (6, 11), (6, 12)]))
    dig(0x59, ([(2, 3), (2, 4), (3, 5), (3, 6), (4, 7), (4, 8), (4, 9), (4, 10),
                (4, 11), (4, 12), (6, 3), (6, 4), (5, 5), (5, 6)]))
    dig(0x5A, (_hline_pts(2, 3, 6) + [(6, 4), (5, 5), (5, 6), (4, 7), (4, 8),
                (3, 9), (3, 10), (2, 11)] + _hline_pts(2, 12, 6)))

    # Lowercase: shift uppercase strokes down two rows and trim the
    # cap height so a/A stay distinguishable under matching.
    for upper in range(0x41, 0x5B):
        shifted = []
        for x, y in _ASCII[upper]:
            ny = y + 2
            if ny <= 14:
                shifted.append((x, ny))
        _ASCII[upper + 0x20] = shifted

    # Punctuation essentials
    dig(0x21, _vline_pts(4, 3, 9) + [(4, 11), (4, 12)])  # !
    dig(0x22, [(2, 3), (2, 4), (2, 5), (5, 3), (5, 4), (5, 5)])  # "
    dig(0x23, (_vline_pts(3, 4, 11) + _vline_pts(5, 4, 11) + _hline_pts(2, 6, 6)
               + _hline_pts(2, 9, 6)))  # #
    dig(0x24, (_vline_pts(4, 2, 13) + _hline_pts(3, 4, 5) + [(2, 5), (2, 6)]
               + _hline_pts(2, 7, 5) + [(5, 8), (5, 9)] + _hline_pts(2, 10, 4)))
    dig(0x25, ([(2, 3), (3, 3), (2, 4), (3, 4), (6, 3), (5, 5), (4, 7), (3, 9),
                (2, 11), (5, 11), (6, 11), (5, 12), (6, 12)]))  # %
    dig(0x26, ([(5, 3), (4, 4), (3, 5), (3, 6), (4, 7), (3, 8), (2, 9), (2, 10),
                (2, 11), (3, 12), (4, 12), (5, 11), (5, 10), (6, 12), (6, 8),
                (5, 7)]))  # &
    dig(0x27, [(4, 3), (4, 4), (4, 5)])  # '
    dig(0x28, [(5, 3), (4, 4), (4, 5), (3, 6), (3, 7), (3, 8), (3, 9),
               (4, 10), (4, 11), (5, 12)])  # (
    dig(0x29, [(3, 3), (4, 4), (4, 5), (5, 6), (5, 7), (5, 8), (5, 9),
               (4, 10), (4, 11), (3, 12)])  # )
    dig(0x2A, ([(4, 5), (4, 6), (4, 7), (4, 8), (4, 9), (2, 7), (3, 7), (5, 7),
                (6, 7), (3, 5), (5, 5), (3, 9), (5, 9)]))  # *
    dig(0x2B, (_vline_pts(4, 5, 11) + _hline_pts(2, 8, 6)))  # +
    dig(0x2C, [(4, 11), (4, 12), (3, 13)])  # ,
    dig(0x2D, _hline_pts(2, 8, 6))  # -
    dig(0x2E, [(4, 11), (4, 12)])  # .
    dig(0x2F, ([(6, 3), (5, 4), (5, 5), (4, 6), (4, 7), (3, 8), (3, 9),
                (2, 10), (2, 11), (2, 12)]))  # /
    dig(0x3A, [(4, 5), (4, 6), (4, 10), (4, 11)])  # :
    dig(0x3B, [(4, 5), (4, 6), (4, 10), (4, 11), (3, 12)])  # ;
    dig(0x3C, [(5, 4), (4, 5), (3, 6), (2, 7), (2, 8), (3, 9), (4, 10),
               (5, 11)])  # <
    dig(0x3D, (_hline_pts(2, 6, 6) + _hline_pts(2, 10, 6)))  # =
    dig(0x3E, [(2, 4), (3, 5), (4, 6), (5, 7), (5, 8), (4, 9), (3, 10),
               (2, 11)])  # >
    dig(0x3F, (_hline_pts(3, 3, 5) + [(6, 4), (6, 5), (5, 6), (4, 7), (4, 8),
                (4, 11), (4, 12)]))  # ?
    dig(0x40, (_oval(2, 3, 6, 12) + [(4, 6), (5, 6), (5, 7), (5, 8), (4, 8),
                (3, 8), (3, 7)]))  # @
    dig(0x5B, (_vline_pts(3, 3, 12) + _hline_pts(3, 3, 5) + _hline_pts(3, 12, 5)))
    dig(0x5C, ([(2, 3), (2, 4), (3, 5), (3, 6), (4, 7), (4, 8), (5, 9),
                (5, 10), (6, 11), (6, 12)]))  # \
    dig(0x5D, (_vline_pts(5, 3, 12) + _hline_pts(3, 3, 5) + _hline_pts(3, 12, 5)))
    dig(0x5E, [(2, 5), (3, 4), (4, 3), (5, 4), (6, 5)])  # ^
    dig(0x5F, _hline_pts(1, 14, 6))  # _
    dig(0x60, [(3, 3), (4, 4)])  # `
    dig(0x7B, ([(4, 3), (3, 4), (3, 5), (3, 6), (2, 7), (3, 8), (3, 9),
                (3, 10), (3, 11), (4, 12)]))  # {
    dig(0x7C, _vline_pts(4, 3, 12))  # |
    dig(0x7D, ([(3, 3), (4, 4), (4, 5), (4, 6), (5, 7), (4, 8), (4, 9),
                (4, 10), (4, 11), (3, 12)]))  # }
    dig(0x7E, ([(2, 7), (3, 6), (4, 6), (5, 7), (6, 8)]))  # ~


def _hline_pts(x0, y, x1):
    return [(x, y) for x in range(x0, x1 + 1)]


def _vline_pts(x, y0, y1):
    return [(x, y) for y in range(y0, y1 + 1)]


def _oval(x0, y0, x1, y1):
    pts = []
    for x in range(x0, x1 + 1):
        pts.append((x, y0))
        pts.append((x, y1))
    for y in range(y0 + 1, y1):
        pts.append((x0, y))
        pts.append((x1, y))
    return pts


def _box_drawing(code):
    """CP437 box-drawing and block elements (0xB0-0xDF), geometric."""
    rows = _blank()
    # Shade blocks
    if code == 0xB0:  # light shade
        for y in range(H):
            for x in range(W):
                if (x + y) % 4 == 0:
                    _set(rows, x, y)
        return rows
    if code == 0xB1:  # medium shade
        for y in range(H):
            for x in range(W):
                if (x + y) % 2 == 0:
                    _set(rows, x, y)
        return rows
    if code == 0xB2:  # dark shade
        for y in range(H):
            for x in range(W):
                if (x + y) % 2 == 0 or x % 2 == 0:
                    _set(rows, x, y)
        return rows
    if code == 0xDB:  # full block
        _rect(rows, 0, 0, 7, 15, fill=True)
        return rows
    if code == 0xDC:  # lower half
        _rect(rows, 0, 8, 7, 15, fill=True)
        return rows
    if code == 0xDD:  # left half
        _rect(rows, 0, 0, 3, 15, fill=True)
        return rows
    if code == 0xDE:  # right half
        _rect(rows, 4, 0, 7, 15, fill=True)
        return rows
    if code == 0xDF:  # upper half
        _rect(rows, 0, 0, 7, 7, fill=True)
        return rows

    # Single-line box pieces — mid at (3..4, 7..8)
    cx, cy = 3, 7
    # Map common CP437 box codes to N/E/S/W arms
    arms = {
        0xB3: "NS",      # │
        0xB4: "NSW",     # ┤
        0xBF: "SW",      # ┐
        0xC0: "NE",      # └
        0xC1: "NEW",     # ┴
        0xC2: "ESW",     # ┬
        0xC3: "NES",     # ├
        0xC4: "EW",      # ─
        0xC5: "NESW",    # ┼
        0xD9: "NW",      # ┘
        0xDA: "ES",      # ┌
    }
    which = arms.get(code)
    if which is None:
        return rows
    if "N" in which:
        _vline(rows, cx, 0, cy)
        _vline(rows, cx + 1, 0, cy)
    if "S" in which:
        _vline(rows, cx, cy, 15)
        _vline(rows, cx + 1, cy, 15)
    if "W" in which:
        _hline(rows, cy, 0, cx)
        _hline(rows, cy + 1, 0, cx)
    if "E" in which:
        _hline(rows, cy, cx, 7)
        _hline(rows, cy + 1, cx, 7)
    return rows


def build_font():
    """Return 4096 bytes: 256 glyphs × 16 row bytes."""
    _define_ascii()
    out = bytearray(N * H)
    for code in range(N):
        if 0x20 <= code <= 0x7E and code in _ASCII:
            rows = _blank()
            _plot_points(rows, _ASCII[code])
        elif 0xB0 <= code <= 0xDF:
            rows = _box_drawing(code)
        else:
            # Distinct placeholder so unknown codes don't collapse to space
            rows = _blank()
            if code != 0:
                _set(rows, code % 8, (code // 8) % 16)
        for y, byte in enumerate(rows):
            out[code * H + y] = byte & 0xFF
    return bytes(out)


def main():
    data = build_font()
    assert len(data) == 4096
    root = os.path.join(os.path.dirname(__file__), "..",
                        "src", "reliquary", "fonts")
    os.makedirs(root, exist_ok=True)
    path = os.path.join(root, "cp437_8x16.bin")
    with open(path, "wb") as handle:
        handle.write(data)
    print(f"wrote {path} ({len(data)} bytes, zlib={len(zlib.compress(data))})")


if __name__ == "__main__":
    main()
