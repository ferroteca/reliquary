# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Recognize text on screen from a framebuffer, using a fixed font
(F51).

When a backend cannot read text directly out of VGA memory, the
agentless-display control plane runs one recognizer over a captured
PNG instead. It returns the standard snapshot format every backend
must produce — rows of characters plus one opaque, comparable
attribute token per cell — so ``DisplayConsole`` and the script
language do not need separate code per backend (see
planning/design/backend-adapter.md, "The text-screen contract").

The built-in font (``fonts/cp437_8x16.bin``) is drawn by
``tools/gen_cp437_font.py``, not copied from anywhere, so the project
never ships glyphs it did not create itself. It is the default font,
and the one test fixtures are rendered with, so the test suite can
round-trip without a real hypervisor. It is not the font used to read
a live guest, though — a live guest's screen is drawn with whatever
fonts the host itself has installed, and read back through those
(see :func:`banks_from_binary`, :func:`cached_banks`).

Recognition tries more than one font on purpose. A single guest run
can paint text with more than one font: the VGA BIOS installs its own
bank (possibly with some glyphs patched by an override table) and
draws its own messages with that, while a DOS guest later loads a
font of its own and draws with that instead. A framebuffer only
records pixels, so nothing in a screenshot says which font was
actually loaded at the time — so every font the host offers is
collected, and each screen cell is matched against them in order: the
first bank whose best match falls inside the distance threshold wins
(F61, D109). This is deliberately not a single scan across every font
looking for the overall best match — trying the fonts in order, and
stopping at the first good-enough match, is what makes the order (set
by :class:`Bank`, which pairs an authored font's declaration with its
bytes — see ``fonts.py``) an actual priority rather than just one more
shape to compare.
"""

from __future__ import annotations

import os
from functools import lru_cache

from PIL import Image

from .errors import PreflightError, StaticError, UnreadableScreen

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


#: The classic IBM VGA 8×16 capital A. Every VGA BIOS font shares it,
#: which is what makes it a reliable anchor for locating a 4096-byte
#: bank inside a larger binary — see :func:`bank_from_binary`.
CLASSIC_A = bytes([
    0x00, 0x00, 0x10, 0x38, 0x6c, 0xc6, 0xc6, 0xfe,
    0xc6, 0xc6, 0xc6, 0xc6, 0x00, 0x00, 0x00, 0x00,
])


class Bank(bytes):
    """A glyph bank, plus the extra facts plain bytes cannot carry
    (F61, D109).

    This subclasses ``bytes``, so every existing caller that treats a
    bank as plain bytes (slicing, :func:`check_bank`,
    :func:`glyph_bitmap`) still works unmodified. A bare ``bytes``
    bank compares and hashes equal to a :class:`Bank` wrapping the
    same data with the same geometry and codepage. A :class:`Bank`
    carries three extra facts that an authored font's declaration
    states explicitly, and that a host-extracted bank leaves at their
    defaults: ``cell_rows`` (16 or 8 — the same 4096 bytes read as
    either 256 or 512 glyphs), ``codepage`` (``None`` keeps the
    current :func:`_cp437_char` mapping; a codepage name is decoded
    through Python's own codec registry instead), and ``source`` (a
    label used in the failure report's "fonts tried" list).

    Equality and hashing take ``cell_rows`` and ``codepage`` into
    account, not just the raw bytes: two authored fonts that happen to
    ship the exact same bytes under different codepages must not
    collide in the per-bank glyph cache and get silently decoded
    through the wrong one. ``source`` is left out of equality and
    hashing on purpose — it is only a display label, and must not
    split the cache or change matching identity.
    """

    def __new__(cls, data, cell_rows=16, codepage=None, source=None):
        self = super().__new__(cls, data)
        self.cell_rows = cell_rows
        self.codepage = codepage
        self.source = source
        return self

    def __eq__(self, other):
        if isinstance(other, Bank):
            return (bytes(self) == bytes(other)
                    and self.cell_rows == other.cell_rows
                    and self.codepage == other.codepage)
        if isinstance(other, (bytes, bytearray)):
            return bytes(self) == bytes(other)
        return NotImplemented

    def __ne__(self, other):
        result = self.__eq__(other)
        return result if result is NotImplemented else not result

    def __hash__(self):
        return hash((bytes(self), self.cell_rows, self.codepage))


def check_bank(data, source):
    """Return ``data`` if it is a whole bank, else fail closed."""
    if len(data) != _GLYPHS * _CELL_H:
        raise StaticError(
            f"glyph bank {source} is {len(data)} bytes; expected "
            f"{_GLYPHS * _CELL_H}",
            rule_id="recognize.font-corrupt")
    return bytes(data)


#: Glyph heights whose override tables a VGA BIOS may carry. A table
#: is a run of (code, rows...) entries ending in a zero code byte, and
#: the BIOS applies whichever one matches the video mode it is
#: setting. Heights other than 8x16 are listed here only so a table
#: for one of them can be skipped over to reach the next table: this
#: recognizer does not use glyphs of those heights, and only reads
#: their entries to know how many bytes to skip.
_ALT_HEIGHTS = (_CELL_H, 14, 8)

#: Limits on what counts as a plausible override table. A real
#: override table patches only a handful of glyphs and sits right
#: after its bank. Without these limits, unrelated bytes further into
#: the file could accidentally look like a table and contribute glyph
#: shapes that were never part of any real font.
_MAX_OVERRIDES = 64
_MAX_OVERRIDE_TABLES = 4


def _bank_bases(data):
    """Find the byte offset of every 8x16 glyph bank in ``data``, in
    the order they appear.

    Each one is located by searching for :data:`CLASSIC_A`, since a
    font that did not share that classic 'A' shape would not be the
    CP437 bank a DOS guest actually draws with.
    """
    bases = []
    index = data.find(CLASSIC_A)
    while index >= 0:
        base = index - 0x41 * _CELL_H
        if base >= 0 and base + _GLYPHS * _CELL_H <= len(data):
            bases.append(base)
        index = data.find(CLASSIC_A, index + 1)
    return bases


def _override_run(data, start, height):
    """Parse one override table starting at ``start``, returning
    ``(entries, end)``, or None if there isn't a valid one there.

    This only checks the table's structure — it doesn't know a
    table's name, or how many entries any particular BIOS actually
    ships. A run of bytes counts as a real table only if its codes
    are strictly increasing, none of its glyphs is entirely blank,
    and it ends with a zero code byte. Those checks are what
    distinguish a real table from the same bytes read at the wrong
    stride, which is how tables for different glyph heights are told
    apart when several follow one bank.
    """
    stride = 1 + height
    entries = []
    off = start
    while off < len(data) and data[off] != 0x00:
        if off + stride > len(data):
            return None
        code = data[off]
        if entries and code <= entries[-1][0]:
            return None
        rows = bytes(data[off + 1:off + stride])
        if not any(rows):
            return None
        entries.append((code, rows))
        if len(entries) > _MAX_OVERRIDES:
            return None
        off += stride
    if not entries or off >= len(data):
        return None
    return entries, off + 1


def _patched_variants(data, bank, start):
    """Build the banks that the override tables following ``bank``
    would produce once applied.

    The bank as stored in the binary, and the bank a BIOS actually
    installs after applying its override table, are two different
    fonts — and nothing in a screenshot says which one painted a
    given character. So this collects both, and lets the recognizer
    try matching against each. Tables for glyph heights other than
    8x16 are skipped rather than applied, since this recognizer never
    uses them.
    """
    variants = []
    off = start
    for _ in range(_MAX_OVERRIDE_TABLES):
        for height in _ALT_HEIGHTS:
            parsed = _override_run(data, off, height)
            if parsed is None:
                continue
            entries, off = parsed
            if height == _CELL_H:
                patched = bytearray(bank)
                for code, rows in entries:
                    patched[code * _CELL_H:(code + 1) * _CELL_H] = rows
                variants.append(bytes(patched))
            break
        else:
            break
    return variants


def banks_from_binary(data, source):
    """Find every distinct 8x16 font embedded in a binary that carries
    a VGA BIOS.

    A backend's fonts are always read off the host, never shipped
    with Reliquary. The glyphs a guest paints belong to whatever BIOS
    the host has installed, not to Reliquary, which is also why no
    bank is bundled in this repository for this purpose: copying
    another project's font in would be third-party material, and the
    project's licensing policy does not allow that (CONTRIBUTING.md).

    A single run can paint text with more than one font, and there is
    no way to tell from a framebuffer which one is currently loaded in
    the VGA: a BIOS installs its own bank, possibly with an override
    table applied, and draws its own messages with that; a guest that
    loads its own font afterward paints with something different
    again. So this function returns every font it finds — every bank
    located, plus every variant that an override table behind a bank
    would produce — and :func:`recognize` matches each screen cell
    against all of them rather than guessing which one is active.
    Duplicate banks are collapsed, so the extra cost of trying more
    fonts stays proportional to how much they actually differ from
    each other.
    """
    banks = []
    for base in _bank_bases(data):
        bank = check_bank(data[base:base + _GLYPHS * _CELL_H], source)
        end = base + _GLYPHS * _CELL_H
        for candidate in [bank, *_patched_variants(data, bank, end)]:
            if candidate not in banks:
                banks.append(candidate)
    if not banks:
        raise PreflightError(
            f"no VGA 8x16 glyph bank found in {source}",
            rule_id="recognize.font-not-found")
    return tuple(banks)


def bank_from_binary(data, source):
    """The first 8×16 bank in ``data``, as stored.

    The single-font view of :func:`banks_from_binary`, kept for
    callers that want the bank a binary ships rather than every font
    it can install.
    """
    return banks_from_binary(data, source)[0]


def banks_from_files(candidates, source):
    """Every font from the first of ``candidates`` that holds any."""
    examined = []
    for path in candidates:
        if not os.path.isfile(path):
            continue
        examined.append(path)
        with open(path, "rb") as handle:
            data = handle.read()
        try:
            return banks_from_binary(data, path)
        except PreflightError:
            continue
    raise PreflightError(
        f"no VGA glyph bank found in this {source} installation; the "
        "agentless display plane cannot read a guest screen without "
        "the font it is drawn with\n"
        f"  examined: {', '.join(examined) or 'no candidate files'}",
        rule_id="recognize.font-not-found")


def bank_from_files(candidates, source):
    """First of ``candidates`` that yields a bank, else fail closed."""
    return banks_from_files(candidates, source)[0]


#: Where a backend's host-extracted support files live, under the
#: cache root: ``cache/support/<backend>/``. Everything here is taken
#: from an installation on this host and is wholly regenerable, which
#: is what makes the cache root the right home for it.
SUPPORT_DIR = "support"

#: The glyph banks' filename inside a backend's support directory —
#: every font that installation offers, concatenated. The name says
#: *banks* because the count is the backend's business and not fixed:
#: a file holding one is as valid as a file holding four.
BANK_FILE = "cp437-8x16-banks.bin"


def support_dir(cache_dir, backend):
    """The directory holding ``backend``'s host-extracted support files."""
    return os.path.join(cache_dir, SUPPORT_DIR, backend)


def cached_banks(cache_dir, backend, extract):
    """Return a backend's glyph banks, extracting them once and
    caching the result under ``cache_dir``.

    The font belongs to the host, so it is cached rather than shipped
    with the project. Reliquary vendors no emulator's glyphs: the
    bytes a guest paints belong to whatever BIOS the host installed,
    and copying another project's font into this tree would be
    third-party material the project's licensing policy does not
    allow (CONTRIBUTING.md). Extracting the font on first use and
    caching the result costs one scan of the installed binary per
    home directory, not one scan per run.

    The cache file lives under ``cache/support/<backend>/`` because
    it is completely regenerable — that is the rule for everything
    under that cache root: delete the file and the next read just
    extracts it again. So a cache file that isn't a complete bank is
    re-extracted rather than treated as an error: the file belongs to
    Reliquary, and a truncated one just means the last write was
    interrupted, not that the caller did anything wrong.

    ``cache_dir`` of ``None`` extracts the font every time, which is
    what an embedding caller with no cache directory assigned gets.
    """
    size = _GLYPHS * _CELL_H
    path = None
    if cache_dir:
        path = os.path.join(support_dir(cache_dir, backend), BANK_FILE)
        if os.path.isfile(path):
            with open(path, "rb") as handle:
                data = handle.read()
            if data and len(data) % size == 0:
                return tuple(bytes(data[at:at + size])
                             for at in range(0, len(data), size))
    banks = tuple(extract())
    if path:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        pending = f"{path}.{os.getpid()}.tmp"
        with open(pending, "wb") as handle:
            handle.write(b"".join(banks))
        os.replace(pending, path)
    return banks


@lru_cache(maxsize=1)
def glyph_bank():
    """Return Reliquary's own built-in glyph bank: 256 glyphs of 16
    row bytes each, most significant bit is the leftmost pixel.

    This bank is drawn by ``tools/gen_cp437_font.py``, not copied
    from anywhere: the script draws the ASCII and box-drawing shapes
    by hand, and computes a distinct glyph for every remaining code
    that has no hand-drawn shape. It is the default font, and the one
    :func:`render` draws with, so the test suite can round-trip
    without a real hypervisor. It is not the font used to read a live
    guest, though — that is drawn using the host's own installed
    fonts and read back through those (:func:`cached_banks`).

    The one hard requirement on this bank is that all 256 codes
    produce distinct glyphs. A bank of only hand-drawn glyphs did not
    manage that on its own: any code left undrawn came out blank,
    which is identical to a space and could never be told apart from
    one. This bank does not have to look like a real VGA font, and
    does not — the fonts a guest actually paints with always come
    from the host.
    """
    path = _font_path()
    with open(path, "rb") as handle:
        data = handle.read()
    return check_bank(data, path)


def glyph_bitmap(code, bank=None):
    """Return the 8x16 boolean pixel rows for CP437 code ``code``
    (0-255).

    ``bank.cell_rows`` decides how the 4096 bytes are sliced into
    glyphs (a plain ``bytes`` bank is always 16 rows, matching every
    host-extracted and shipped font): 16 rows read directly as 256
    glyphs, or 8 rows read as 512 glyphs, of which only the first 256
    are addressed (Reliquary's codes are always in the 8-bit CP437
    range). An 8-row glyph is doubled here so it still compares
    against the fixed 8x16 cell size every match is run against.
    """
    data = glyph_bank() if bank is None else bank
    cell_rows = getattr(bank, "cell_rows", 16) if bank is not None else 16
    base = (code & 0xFF) * cell_rows
    rows = []
    for y in range(cell_rows):
        byte = data[base + y]
        rows.append([(byte >> (7 - x)) & 1 for x in range(_CELL_W)])
    if cell_rows < _CELL_H:
        scale = _CELL_H // cell_rows
        rows = [row for row in rows for _ in range(scale)]
    return rows


def attribute_token(fg, bg):
    """Return an opaque token for one foreground/background color
    pair, comparable for equality.

    ``fg`` and ``bg`` are each an ``(r, g, b)`` triple. The token is
    packed the same way on every run (unlike Python's ``hash()``,
    which varies between runs), so a recorded transcript and a live
    run agree on which cells share the same highlight color.
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


def _glyph_bits(code, bank=None):
    flat = []
    for row in glyph_bitmap(code, bank):
        flat.extend(row)
    return flat


def as_banks(bank):
    """Normalize a ``bank`` argument into a tuple of whole banks.

    A caller may pass one font, several fonts, or ``None`` for
    Reliquary's own built-in font. Passing several is the realistic
    case for a live guest: a single run can paint text in more than
    one font, and a framebuffer doesn't say which one was used where
    (see :func:`banks_from_binary`). A :class:`Bank` instance passes
    through unchanged rather than being converted to plain ``bytes``
    — converting it would throw away the geometry and codepage that
    an authored font's declaration attached to it.
    """
    if bank is None:
        return (glyph_bank(),)
    if isinstance(bank, Bank):
        return (bank,)
    if isinstance(bank, (bytes, bytearray)):
        return (bytes(bank),)
    return tuple(one if isinstance(one, Bank) else bytes(one) for one in bank)


@lru_cache(maxsize=32)
def _bank_glyph_bits(bank):
    """Return one bank's 256 glyphs as flat bit lists, as
    ``(code, bits)`` pairs.

    This is cached per bank, not merged across banks: font order is a
    real priority (F61, D109) — the first bank whose best match falls
    inside the threshold wins, so a later bank's glyph shapes must
    never get mixed in with an earlier bank's. The cache key is the
    bank's full identity — its bytes, plus its declared
    ``cell_rows``/``codepage`` via :class:`Bank`'s own equality check
    — so a host running two backends with different fonts in the same
    process never mixes their glyphs, and two authored fonts that
    happen to share the same bytes under different codepages never
    collide in the cache either.
    """
    return tuple((code, tuple(_glyph_bits(code, bank)))
                 for code in range(_GLYPHS))


def _match_in_bank(bits, bank):
    """Best CP437 code and its Hamming distance, within one bank alone."""
    best_code = 0x20
    best_dist = _CELL_W * _CELL_H + 1
    for code, glyph in _bank_glyph_bits(bank):
        dist = sum(a != b for a, b in zip(bits, glyph))
        if dist < best_dist:
            best_dist = dist
            best_code = code
            if dist == 0:
                break
    return best_code, best_dist


def _match_glyph_with_distance(bits, banks):
    """Return the best matching code, the bank it came from, and its
    Hamming distance.

    The first bank whose best match falls inside the distance
    threshold wins (F61, D109): banks are tried in the given order,
    and once an earlier bank has produced a match inside the
    threshold, later banks are not tried. Only when every bank misses
    does this fall through all of them, and even then the closest
    guess found across all banks is returned — it is never treated as
    a real match (:func:`_match_cell` substitutes a space once the
    distance is past the threshold, regardless of what code was
    guessed), but returning it is honest about how close the nearest
    wrong answer actually was.
    """
    if not any(bits):
        return 0x20, banks[0] if banks else None, 0
    best_code, best_bank, best_dist = 0x20, None, _CELL_W * _CELL_H + 1
    for bank in banks:
        code, dist = _match_in_bank(bits, bank)
        if dist < best_dist:
            best_code, best_bank, best_dist = code, bank, dist
        if dist <= _MAX_DISTANCE:
            break
    return best_code, best_bank, best_dist


def _match_cell(pixels, width, height, banks):
    """Recognize one cell, returning
    ``(cp437_code, fg, bg, matched, bank)``.

    ``matched`` is False when the nearest glyph found was too far
    away to be trusted, and a space was substituted instead. That is
    a different fact from "this cell is actually blank" — treating
    the two as the same is how a screen drawn in a font this
    recognizer doesn't have ends up silently read as ordinary text
    (see :func:`recognize`). ``bank`` is the bank the winning match
    came from, or ``None`` when nothing matched, since a substituted
    space decodes the same way regardless of codepage.
    """
    primary, secondary = _cell_colours(pixels)
    if primary == secondary:
        return 0x20, primary, primary, True, banks[0] if banks else None
    # Try both polarities: glyph ink may be the minority colour
    # (normal text) or the majority (an inverted highlight bar).
    candidates = []
    for fg, bg in ((secondary, primary), (primary, secondary)):
        bits = _binarize_as(pixels, fg, bg, width, height)
        code, bank, dist = _match_glyph_with_distance(bits, banks)
        candidates.append((dist, code, fg, bg, bank))
    candidates.sort(key=lambda item: item[0])
    dist, code, fg, bg, bank = candidates[0]
    if dist > _MAX_DISTANCE:
        return 0x20, secondary, primary, False, None
    return code, fg, bg, True, bank


def _cp437_char(code):
    """Character for a matched code — printable ASCII, else Latin-1."""
    if 32 <= code < 127:
        return chr(code)
    if code == 0x20 or code == 0:
        return " "
    # High CP437: expose as Latin-1 so fixtures can round-trip box
    # drawing as the same code points the bank uses.
    return chr(code)


def _decode(code, bank):
    """Return the character for a matched code, decoded through
    ``bank``'s own codepage.

    When ``bank``'s codepage is ``None`` (true for every
    host-extracted or shipped bank, and for the unmatched-cell case),
    this keeps :func:`_cp437_char`'s mapping unconditionally —
    nothing already recorded changes meaning (D109). A :class:`Bank`
    with an explicit ``codepage`` is decoded through Python's own
    codec registry instead. The codepage name was already validated
    when the font's declaration was read, so a lookup failure here
    would be a bug in this module, not a mistake by the caller.
    """
    codepage = getattr(bank, "codepage", None) if bank is not None else None
    if codepage is None:
        return _cp437_char(code)
    return bytes([code & 0xFF]).decode(codepage, errors="replace")


class Screen(tuple):
    """``(text_rows, attribute_rows)``, plus how well the screen was
    actually read.

    To every caller that unpacks or indexes it, this behaves as a
    plain 2-tuple — that is the contract every backend must honor,
    and it stays unchanged — but it also carries one extra fact for
    anyone who asks: ``unreadable``, the ``(row, col)`` of every cell
    whose nearest glyph match was too far away to be trusted.

    This fact travels attached to the reading itself, rather than
    being returned as a separate value, because it gets asked for far
    away from where it could otherwise be answered — a script's
    failure report and `rlq screen` both need it, and neither is
    anywhere near the pixel data by the time they ask.
    """

    def __new__(cls, text_rows, attribute_rows, unreadable=(),
               fonts_tried=()):
        screen = super().__new__(cls, (text_rows, attribute_rows))
        screen.unreadable = tuple(unreadable)
        #: The banks this read was matched against, in try order —
        #: each bank's ``source`` label, or ``"default"`` for a bank
        #: that has none. Empty for a screen built without this
        #: information (the plain ``(rows, attrs)`` tuple form other
        #: callers still construct directly).
        screen.fonts_tried = tuple(fonts_tried)
        return screen


def unreadable_cells(screen):
    """Return the cells a screen could not read, for any kind of
    screen.

    A backend that reads characters directly out of text memory has
    nothing to report here, so asking it this question returns none —
    correctly, since a direct read never recognizes glyphs and so can
    never misrecognize one.
    """
    return getattr(screen, "unreadable", ())


def _geometry(width, height, cols, rows):
    """Compute the cell size for this framebuffer, or report that it
    is not a text screen at all.

    Both failure cases raise :class:`UnreadableScreen` rather than
    being treated as a bug in the caller: a guest picks its own video
    mode, and every VirtualBox boot passes through a graphics-mode
    BIOS splash screen before reaching a text mode. What a caller
    gets back is the reason nothing could be read — the actual shape
    that was captured — never just a bare failure with no explanation
    (P10).
    """
    if width % cols != 0 or height % rows != 0:
        raise UnreadableScreen(
            f"framebuffer {width}x{height} is not an even {cols}x{rows} "
            f"text grid",
            rule_id="recognize.geometry")
    cell_w = width // cols
    cell_h = height // rows
    if cell_w < _CELL_W or cell_h < _CELL_H:
        raise UnreadableScreen(
            f"cell size {cell_w}x{cell_h} is smaller than the "
            f"{_CELL_W}x{_CELL_H} glyph bank",
            rule_id="recognize.geometry")
    return cell_w, cell_h


def recognize(source, *, cols=_COLS, rows=_ROWS, bank=None):
    """Recognize a text screen from a PNG path or a ``PIL.Image``.

    Returns a :class:`Screen` — which behaves as ``(text_rows,
    attribute_rows)`` to anyone unpacking it. Text rows are
    right-stripped, matching QEMU's VGA scrape; attribute rows hold
    one opaque token per cell from :func:`attribute_token`, each row
    ``cols`` cells long and not stripped.

    A cell that matches no glyph closely enough is reported as a
    space, and marked as such. The nearest glyph is only accepted
    when it is close enough to trust; past `_MAX_DISTANCE`, a space
    is substituted instead, because giving a script's `wait` a wrong
    character is worse than giving it a blank. This substitution used
    to happen silently, which meant a screen drawn in a font the host
    doesn't have got misread as ordinary text — a plausible-looking
    but wrong reading, indistinguishable from a screen that really
    was blank there. Those cells now show up in the returned screen's
    ``unreadable`` list, so a caller can tell how much of what it got
    back was actually read correctly.

    ``bank`` is the font (or fonts) to read through: one 4096-byte
    bank, or any number of them. A caller reading a live guest should
    supply every font that guest could plausibly be painting with
    (see :func:`banks_from_binary`), because one font is rarely
    enough — the BIOS draws its own messages with its own installed
    bank, a DOS guest later draws with whatever font it loaded, and a
    framebuffer just records pixels without saying which font was
    active in the VGA at the time. The two fonts a stock VirtualBox
    install offers differ in nineteen glyphs, including `W` and `m` —
    enough to make every `wait` on a word containing either letter
    fail if only one font is tried.
    """
    if isinstance(source, Image.Image):
        image = source.convert("RGB")
    else:
        with Image.open(source) as opened:
            image = opened.convert("RGB")
    cell_w, cell_h = _geometry(image.width, image.height, cols, rows)
    banks = as_banks(bank)
    pixels = list(image.get_flattened_data())
    text_rows = []
    attr_rows = []
    unreadable = []
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
            code, fg, bg, matched, cell_bank = _match_cell(
                cell, cell_w, cell_h, banks)
            if not matched:
                unreadable.append((row, col))
            chars.append(_decode(code, cell_bank))
            attrs.append(attribute_token(fg, bg))
        text_rows.append("".join(chars).rstrip())
        attr_rows.append(attrs)
    fonts_tried = tuple(getattr(one, "source", None) or "default"
                        for one in banks)
    return Screen(text_rows, attr_rows, unreadable, fonts_tried)


def render(text_rows, attribute_rows=None, *,
           cols=_COLS, rows=_ROWS, cell_w=_CELL_W, cell_h=_CELL_H,
           fg=(170, 170, 170), bg=(0, 0, 0), bank=None):
    """Render character rows into an RGB ``PIL.Image``, using a glyph
    bank.

    This is the test counterpart of :func:`recognize`: test fixtures
    are produced here so the test suite never needs a real
    hypervisor. ``attribute_rows``, when given, supplies a per-cell
    ``(fg, bg)`` RGB pair; otherwise every cell uses the single
    ``fg``/``bg`` pair given. Cells wider than 8 pixels leave the
    extra columns blank (matching real 9-dot VGA cells); taller cells
    pad the extra rows with background color.

    ``bank`` draws with a font other than the default — exactly one
    font, because whatever draws a real screen has exactly one font
    loaded at a time; it is only the *reader* (:func:`recognize`)
    that cannot know which font that was. This asymmetry is what
    makes it possible to test a screen painted in one font and read
    back through several fonts, without needing a real hypervisor.
    """
    if cell_w < _CELL_W or cell_h < _CELL_H:
        raise StaticError(
            f"cell size {cell_w}x{cell_h} is smaller than the "
            f"{_CELL_W}x{_CELL_H} glyph bank",
            rule_id="recognize.geometry")
    image = Image.new("RGB", (cols * cell_w, rows * cell_h), bg)
    pixels = image.load()
    bank = glyph_bank() if bank is None else check_bank(bank, "render")
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
