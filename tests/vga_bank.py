# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""A stand-in for the glyph bank a real VGA BIOS carries.

Tests that simulate reading a font out of a hypervisor's binaries
need a bank the locator can actually find, and the locator's anchor
is the classic IBM `A` every CP437 BIOS font shares
(`text_recognize.CLASSIC_A`). Reliquary's **own** bank is drawn
rather than dumped, so its `A` is its own and the anchor is not
there — correctly, since nothing about a bank the project authored
should have to match somebody's ROM.

Building the stand-in here rather than vendoring one keeps the suite
carrying no other project's font, which is the same rule the runtime
obeys. What arrives is Reliquary's bank with the anchor patched in:
the shape a *real* one has, made from bytes the project owns.
"""

from reliquary import text_recognize


def vga_bank(bank=None):
    """``bank`` (default Reliquary's own) with the classic ``A``."""
    data = bytearray(text_recognize.glyph_bank() if bank is None else bank)
    data[0x41 * 16:0x42 * 16] = text_recognize.CLASSIC_A
    return bytes(data)
