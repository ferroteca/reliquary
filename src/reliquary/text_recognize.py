# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Fixed-font text-screen recognition over a framebuffer (F51).

Where a backend has no native VGA text scrape, the agentless-display
control plane runs **one** recognizer over a captured PNG. The
output is the seam's portable snapshot contract — character rows
plus opaque, equality-comparable per-cell attribute tokens — so
``DisplayConsole`` and the script language need no backend branch
(planning/design/backend-adapter.md "The text-screen contract").

The glyph bank is the standard VGA 8×16 CP437 bit pattern, curated
into ``fonts/cp437_8x16.bin`` by ``tools/extract_vga_font.py`` from
the host's QEMU ``vgabios-stdvga.bin`` so recognition matches what a
DOS guest paints. Fixtures are rendered with the same bank.
"""

from __future__ import annotations

import os
from functools import lru_cache

from PIL import Image

from .errors import StaticError

_COLS = 80
_ROWS = 25
_CELL_W = 8
_CELL_H = 16
_GLYPHS = 256

#: Maximum Hamming distance (of 128 bits) still accepted as a match.
#: Above this the cell is reported as a space — wrong matches are
#: worse for script waits than a blank.
_MAX_DISTANCE = 24


def _font_path():
    return os.path.join(os.path.dirname(__file__), "fonts", "cp437_8x16.bin")


@lru_cache(maxsize=1)
def glyph_bank():
    """256 glyphs × 16 row bytes (MSB = leftmost pixel)."""
    path = _font_path()
    with open(path, "rb") as handle:
        data = handle.read()
    if len(data) != _GLYPHS * _CELL_H:
        raise StaticError(
            f"glyph bank {path} is {len(data)} bytes; expected "
            f"{_GLYPHS * _CELL_H}",
            rule_id="recognize.font-corrupt")
    return data


def glyph_bitmap(code):
    """8×16 boolean rows for CP437 code ``code`` (0..255)."""
    data = glyph_bank()
    base = (code & 0xFF) * _CELL_H
    rows = []
    for y in range(_CELL_H):
        byte = data[base + y]
        rows.append([(byte >> (7 - x)) & 1 for x in range(_CELL_W)])
    return rows


def attribute_token(fg, bg):
    """Opaque equality-comparable token for a foreground/background pair.

    ``fg`` / ``bg`` are ``(r, g, b)`` triples. The packing is stable
    across runs (unlike ``hash()``), which is what keeps a recorded
    transcript and a live run agreeing on highlight identity.
    """
    fr, fg_, fb = fg
    br, bg_, bb = bg
    return (((fr & 255) << 16) | ((fg_ & 255) << 8) | (fb & 255)
            | (((br & 255) << 16) | ((bg_ & 255) << 8) | (bb & 255)) << 24)


def _quantize(pixel):
    """Round channel noise so near-black / near-white collapse."""
    return tuple(0 if c < 16 else (255 if c > 239 else c) for c in pixel[:3])


def _cell_colours(pixels):
    """The two dominant colours in a cell (majority first)."""
    counts = {}
    for pixel in pixels:
        key = _quantize(pixel)
        counts[key] = counts.get(key, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: -item[1])
    primary = ranked[0][0]
    secondary = ranked[1][0] if len(ranked) > 1 else primary
    return primary, secondary


def _binarize_as(pixels, fg, bg, width, height):
    """Cell pixels → 8×16 bits treating ``fg`` as on and ``bg`` as off."""
    if fg == bg:
        return [0] * (_CELL_W * _CELL_H)
    bits = []
    for y in range(_CELL_H):
        src_y = min(y, height - 1)
        for x in range(_CELL_W):
            src_x = min(x, width - 1)
            pixel = _quantize(pixels[src_y * width + src_x])
            df = sum(abs(pixel[i] - fg[i]) for i in range(3))
            db = sum(abs(pixel[i] - bg[i]) for i in range(3))
            bits.append(1 if df <= db else 0)
    return bits


def _glyph_bits(code):
    flat = []
    for row in glyph_bitmap(code):
        flat.extend(row)
    return flat


@lru_cache(maxsize=1)
def _all_glyph_bits():
    return tuple(_glyph_bits(code) for code in range(_GLYPHS))


def _match_glyph_with_distance(bits):
    """Best CP437 code and its Hamming distance for ``bits``."""
    if not any(bits):
        return 0x20, 0
    best_code = 0x20
    best_dist = _CELL_W * _CELL_H + 1
    for code, glyph in enumerate(_all_glyph_bits()):
        dist = sum(a != b for a, b in zip(bits, glyph))
        if dist < best_dist:
            best_dist = dist
            best_code = code
            if dist == 0:
                break
    return best_code, best_dist


def _match_cell(pixels, width, height):
    """Return ``(cp437_code, fg, bg)`` for one cell."""
    primary, secondary = _cell_colours(pixels)
    if primary == secondary:
        return 0x20, primary, primary
    # Try both polarities: glyph ink may be the minority colour
    # (normal text) or the majority (an inverted highlight bar).
    candidates = []
    for fg, bg in ((secondary, primary), (primary, secondary)):
        bits = _binarize_as(pixels, fg, bg, width, height)
        code, dist = _match_glyph_with_distance(bits)
        candidates.append((dist, code, fg, bg))
    candidates.sort(key=lambda item: item[0])
    dist, code, fg, bg = candidates[0]
    if dist > _MAX_DISTANCE:
        return 0x20, secondary, primary
    return code, fg, bg


def _cp437_char(code):
    """Character for a matched code — printable ASCII, else Latin-1."""
    if 32 <= code < 127:
        return chr(code)
    if code == 0x20 or code == 0:
        return " "
    # High CP437: expose as Latin-1 so fixtures can round-trip box
    # drawing as the same code points the bank uses.
    return chr(code)


def _geometry(width, height, cols, rows):
    if width % cols != 0 or height % rows != 0:
        raise StaticError(
            f"framebuffer {width}x{height} is not an even {cols}x{rows} "
            f"text grid",
            rule_id="recognize.geometry")
    cell_w = width // cols
    cell_h = height // rows
    if cell_w < _CELL_W or cell_h < _CELL_H:
        raise StaticError(
            f"cell size {cell_w}x{cell_h} is smaller than the "
            f"{_CELL_W}x{_CELL_H} glyph bank",
            rule_id="recognize.geometry")
    return cell_w, cell_h


def recognize(source, *, cols=_COLS, rows=_ROWS):
    """Recognize a text screen from a PNG path or ``PIL.Image``.

    Returns ``(text_rows, attribute_rows)`` — text rows right-stripped
    like QEMU's VGA scrape; attribute rows are per-cell opaque tokens
    from :func:`attribute_token`, length ``cols`` each (not stripped).
    """
    if isinstance(source, Image.Image):
        image = source.convert("RGB")
    else:
        with Image.open(source) as opened:
            image = opened.convert("RGB")
    cell_w, cell_h = _geometry(image.width, image.height, cols, rows)
    pixels = list(image.get_flattened_data())
    text_rows = []
    attr_rows = []
    for row in range(rows):
        chars = []
        attrs = []
        for col in range(cols):
            x0 = col * cell_w
            y0 = row * cell_h
            cell = []
            for y in range(cell_h):
                base = (y0 + y) * image.width + x0
                cell.extend(pixels[base:base + cell_w])
            code, fg, bg = _match_cell(cell, cell_w, cell_h)
            chars.append(_cp437_char(code))
            attrs.append(attribute_token(fg, bg))
        text_rows.append("".join(chars).rstrip())
        attr_rows.append(attrs)
    return text_rows, attr_rows


def render(text_rows, attribute_rows=None, *,
           cols=_COLS, rows=_ROWS, cell_w=_CELL_W, cell_h=_CELL_H,
           fg=(170, 170, 170), bg=(0, 0, 0)):
    """Render character rows into a RGB ``PIL.Image`` using the glyph bank.

    The test twin of :func:`recognize`: fixtures are produced here so
    the suite never needs a hypervisor. ``attribute_rows``, when
    given, supplies per-cell ``(fg, bg)`` RGB pairs; otherwise every
    cell uses ``fg`` / ``bg``. Cells wider than 8 leave the extra
    columns blank (9-dot VGA); taller cells pad with background.
    """
    if cell_w < _CELL_W or cell_h < _CELL_H:
        raise StaticError(
            f"cell size {cell_w}x{cell_h} is smaller than the "
            f"{_CELL_W}x{_CELL_H} glyph bank",
            rule_id="recognize.geometry")
    image = Image.new("RGB", (cols * cell_w, rows * cell_h), bg)
    pixels = image.load()
    bank = glyph_bank()
    for row in range(rows):
        line = text_rows[row] if row < len(text_rows) else ""
        for col in range(cols):
            ch = line[col] if col < len(line) else " "
            code = ord(ch) & 0xFF
            if attribute_rows is not None:
                cell_fg, cell_bg = attribute_rows[row][col]
            else:
                cell_fg, cell_bg = fg, bg
            base = code * _CELL_H
            x0 = col * cell_w
            y0 = row * cell_h
            for y in range(cell_h):
                byte = bank[base + y] if y < _CELL_H else 0
                for x in range(cell_w):
                    if y < _CELL_H and x < _CELL_W:
                        on = (byte >> (7 - x)) & 1
                        pixels[x0 + x, y0 + y] = (
                            cell_fg if on else cell_bg)
                    else:
                        pixels[x0 + x, y0 + y] = cell_bg
    return image


def save_screen(path, text_rows, **kwargs):
    """Render ``text_rows`` and write a PNG to ``path``."""
    image = render(text_rows, **kwargs)
    image.save(path)
    return path
