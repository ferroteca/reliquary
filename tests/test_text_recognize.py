# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for the fixed-font text-screen recognizer (F51).

Fixtures are rendered with the same glyph bank the recognizer
reads — no hypervisor, and a failing round-trip is a defect.
"""

import os

import pytest
from PIL import Image

from reliquary import text_recognize as recognize
from tests import corpus
from tests.vga_bank import vga_bank
from reliquary.errors import (PreflightError, StaticError, UnreadableScreen,
                              exit_code)


_FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
#: The golden PNGs, counted at collection: a fixture directory that
#: stopped loading is a collection error rather than a green run over
#: nothing (`tests/corpus.py`).
GOLDEN = corpus.fixtures(_FIXTURES, "text_recognize", ".png", count=3)


def _screen(*lines, rows=25):
    """Pad ``lines`` to a full ``rows``-row text screen."""
    out = list(lines)
    while len(out) < rows:
        out.append("")
    return out[:rows]


# The glyph bank.

def test_bank_is_4096_bytes():
    assert len(recognize.glyph_bank()) == 4096


def test_space_is_blank():
    assert not any(recognize._glyph_bits(0x20))


def test_letter_a_is_not_blank():
    assert any(recognize._glyph_bits(0x41))


# Attribute tokens are opaque, and compare.

def test_equal_colours_compare_equal():
    a = recognize.attribute_token((170, 170, 170), (0, 0, 0))
    b = recognize.attribute_token((170, 170, 170), (0, 0, 0))
    assert a == b


def test_different_pairs_differ():
    plain = recognize.attribute_token((170, 170, 170), (0, 0, 0))
    highlight = recognize.attribute_token((0, 0, 0), (170, 170, 170))
    assert plain != highlight


# Render, then recognize: the round trip.

def test_ascii_prompt_round_trips():
    rows = _screen("", "", "C:\\>")
    image = recognize.render(rows)
    text, attrs = recognize.recognize(image)
    assert text[2] == "C:\\>"
    assert len(attrs) == 25
    assert len(attrs[2]) == 80


def test_freedos_welcome_line_round_trips():
    # The string FreeDOS install waits for (freedos-install.rlqs).
    line = "Welcome to FreeDOS 1.4 (LiveCD)"
    rows = _screen(line)
    image = recognize.render(rows)
    text, _attrs = recognize.recognize(image)
    assert text[0] == line


def test_highlight_row_tokens_differ():
    rows = _screen("Install to harddisk", "Return to DOS")
    grey = (170, 170, 170)
    black = (0, 0, 0)
    attrs = [[(grey, black)] * 80 for _ in range(25)]
    # Invert the first menu row — the cursor bar.
    attrs[0] = [(black, grey)] * 80
    image = recognize.render(rows, attrs)
    _text, tokens = recognize.recognize(image)
    assert tokens[0][0] != tokens[1][0]
    # Letter cells on the bar share a token; a space cell cannot
    # show its foreground in the framebuffer, so it is not asked.
    assert tokens[0][0] == tokens[0][1]  # 'I' and 'n'


def test_nine_dot_cells_still_recognize():
    rows = _screen("Ready.")
    image = recognize.render(rows, cell_w=9, cell_h=16)
    assert image.size == (720, 400)
    text, _attrs = recognize.recognize(image)
    assert text[0] == "Ready."


# Golden PNGs under tests/fixtures/text_recognize/.

@corpus.parametrize(GOLDEN)
def test_a_fixture_matches_its_expected_text(fixture):
    with open(fixture[:-4] + ".txt", encoding="utf-8") as handle:
        expected = handle.read().splitlines()
    # The expected file omits trailing blank rows, so only the lines
    # it states are compared.
    text, _attrs = recognize.recognize(fixture)
    for index, line in enumerate(expected):
        assert text[index] == line, f"row {index}"


# A guest's video mode is never the author's mistake.

def test_bad_geometry_is_an_unreadable_screen():
    image = Image.new("RGB", (100, 100), (0, 0, 0))
    with pytest.raises(UnreadableScreen) as caught:
        recognize.recognize(image)
    assert caught.value.rule_id == "recognize.geometry"
    assert not isinstance(caught.value, StaticError)
    assert exit_code(caught.value) == 4


def test_a_bios_splash_resolution_is_refused_by_name():
    """The 640x480 mode every VirtualBox boot passes through."""
    image = Image.new("RGB", (640, 480), (0, 0, 0))
    with pytest.raises(UnreadableScreen) as caught:
        recognize.recognize(image)
    assert "640x480" in str(caught.value)


def _swapped_bank(first, second):
    """The shipped bank with two glyphs exchanged."""
    data = bytearray(recognize.glyph_bank())
    a, b = first * 16, second * 16
    data[a:a + 16], data[b:b + 16] = data[b:b + 16], data[a:a + 16]
    return bytes(data)


# A backend's font is read off the host, never vendored here. These
# build their fixtures from the *shipped* bank, so the suite carries
# no other project's font — which is the same rule the runtime obeys.

def test_a_supplied_bank_decides_what_a_glyph_reads_as():
    image = recognize.render(_screen("W"))
    assert recognize.recognize(image)[0][0] == "W"
    # 0x55 'U' now holds the W bitmap, so that is what matches.
    swapped = _swapped_bank(0x55, 0x57)
    assert recognize.recognize(image, bank=swapped)[0][0] == "U"


def test_a_bank_is_carved_out_of_a_binary_by_the_classic_a():
    embedded = vga_bank()
    binary = (b"\x00" * 1234) + embedded + (b"\xa5" * 77)
    assert recognize.bank_from_binary(binary, "fake.dll") == embedded


def test_reliquarys_own_bank_carries_no_borrowed_anchor():
    """The locator's anchor is a real BIOS's, and ours is not one.

    `CLASSIC_A` is in the source because a bank cannot be found in
    a binary without knowing what to look for. Reliquary's own
    bank is drawn rather than dumped, so its `A` is its own — and
    a test that wanted a *findable* bank had to say so, which is
    what `vga_bank` is for.
    """
    assert recognize.CLASSIC_A not in recognize.glyph_bank()


def test_a_binary_without_the_anchor_fails_closed():
    with pytest.raises(PreflightError) as caught:
        recognize.bank_from_binary(b"\x00" * 8192, "fake.dll")
    assert caught.value.rule_id == "recognize.font-not-found"


def test_a_truncated_bank_fails_closed():
    shipped = vga_bank()
    with pytest.raises(PreflightError) as caught:
        recognize.bank_from_binary(shipped[:2048], "fake.dll")
    assert caught.value.rule_id == "recognize.font-not-found"


def _patch_table(entries, height=16):
    """An override table: ``(code, rows...)`` runs closed by a zero."""
    out = bytearray()
    for code, fill in entries:
        out.append(code)
        out.extend(bytes([fill]) * height)
    out.append(0x00)
    return bytes(out)


# More than one font is painted per run, and pixels do not say which.
#
# A VGA BIOS installs its bank with an override table applied and
# draws its own messages that way; a DOS guest loads its own font and
# draws with that. The recognizer is given every font a host offers
# and matches against all of them, which is why a screen drawn in
# *one* of them reads correctly either way. Fixtures are built from
# the shipped bank, so the suite still vendors no other project's
# font.

#: A coarse checkerboard: the shape measured **furthest** from every
#: glyph in the bank — 56 of 128 pixels from its nearest, where 24 is
#: the most that is still believed — so a cell drawn with it is
#: unmistakably unread rather than merely mismatched.
#:
#: Distance matters more than novelty here, and both polarities
#: count, because `_match_cell` tries the cell inverted too. A
#: diagonal is novel and sits 14 away from something; alternating
#: single columns is novel and its *complement* is 1 away from a
#: constructed glyph. Either would come back as a wrong character
#: rather than an unreadable one, which is the opposite of what this
#: fixture is for.
#:
#: An override table gives a code a *different drawing of the same
#: character* — never another code's shape — so a fixture that merely
#: exchanged two glyphs would make one bitmap legitimately mean two
#: codes and prove nothing.
DISTINCT = bytes([0xCC, 0xCC, 0x33, 0x33] * 4)


def _two_fonts():
    stored = recognize.glyph_bank()
    installed = stored[:0x57 * 16] + DISTINCT + stored[0x58 * 16:]
    return stored, installed


@pytest.mark.parametrize("drawn_with", [0, 1], ids=["stored", "installed"])
def test_a_screen_reads_through_whichever_font_drew_it(drawn_with):
    fonts = _two_fonts()
    image = recognize.render(_screen("W"), bank=fonts[drawn_with])
    rows, _ = recognize.recognize(image, bank=fonts)
    assert rows[0][0] == "W"


def test_one_font_alone_misreads_a_screen_the_other_drew():
    """The defect being fixed, stated as the reason for the above.

    *How* it fails depends on the shape: a glyph far from anything
    in the font read through falls past the distance threshold and
    blanks, while the real 19 sit close enough to other letters to
    come back as the wrong one — `Welcome` as `Uelcooe`. Either
    way the word a script waits for is not there, which is the
    only part worth pinning.
    """
    stored, installed = _two_fonts()
    image = recognize.render(_screen("W"), bank=installed)
    rows, _ = recognize.recognize(image, bank=stored)
    assert "W" not in rows[0]


def test_shared_glyphs_are_scored_once():
    """Supporting several fonts costs only where they disagree."""
    stored, installed = _two_fonts()
    one = recognize._all_glyph_bits((stored,))
    both = recognize._all_glyph_bits((stored, installed))
    assert len(one) == 256
    assert len(both) == 256 + 1


def test_an_override_table_behind_a_bank_yields_a_second_font():
    stored = vga_bank()
    binary = (b"\x00" * 64 + stored
              + _patch_table([(0x57, 0x5a)]) + b"\xa5" * 40)
    banks = recognize.banks_from_binary(binary, "fake.dll")
    assert len(banks) == 2
    assert banks[0] == stored
    assert banks[1][0x57 * 16:0x58 * 16] == b"\x5a" * 16


def test_a_table_for_another_glyph_height_is_stepped_over():
    """A BIOS carries a table per size; only 8x16 is this reader's."""
    stored = vga_bank()
    binary = (b"\x00" * 64 + stored
              + _patch_table([(0x1d, 0x11), (0x22, 0x11)], height=14)
              + _patch_table([(0x57, 0x5a)])
              + b"\xa5" * 40)
    banks = recognize.banks_from_binary(binary, "fake.dll")
    assert len(banks) == 2
    assert banks[1][0x57 * 16:0x58 * 16] == b"\x5a" * 16


def test_identical_fonts_collapse_to_one():
    """Three copies of a BIOS image are not three fonts."""
    stored = vga_bank()
    binary = b"".join([b"\x00" * 8 + stored] * 3)
    assert recognize.banks_from_binary(binary, "fake.dll") == (stored,)


def test_bytes_that_are_not_a_table_add_no_font():
    """Arbitrary bytes behind a bank must not become glyph shapes."""
    stored = vga_bank()
    # Descending codes: a real override table ascends.
    noise = bytes([0x90]) + b"\x11" * 16 + bytes([0x10]) + b"\x11" * 16
    binary = b"\x00" * 64 + stored + noise + b"\x00"
    assert recognize.banks_from_binary(binary, "fake.dll") == (stored,)


def test_a_cell_that_matches_nothing_says_so():
    """A substituted space must not pass for a read one.

    Past the distance threshold a space is written, because a
    wrong character is worse for a `wait` than a blank — but a
    screen drawn in a font this host lacks then arrives looking
    merely sparse, and a wait on a word in it expires with
    nothing to show. The cells are reported so the difference is
    visible.
    """
    stored, installed = _two_fonts()
    image = recognize.render(_screen("W"), bank=installed)

    blind = recognize.recognize(image, bank=stored)
    assert recognize.unreadable_cells(blind) == ((0, 0),)

    seeing = recognize.recognize(image, bank=(stored, installed))
    assert recognize.unreadable_cells(seeing) == ()
    assert seeing[0][0] == "W"


def test_a_blank_cell_is_read_rather_than_unread():
    """Nothing to recognize is not the same as failing to."""
    image = recognize.render(_screen(""))
    screen = recognize.recognize(image)
    assert recognize.unreadable_cells(screen) == ()


def test_a_screen_is_still_the_pair_the_seam_promises():
    """The report rides along; it does not widen the contract."""
    screen = recognize.recognize(recognize.render(_screen("ok")))
    text, attributes = screen
    assert len(screen) == 2
    assert text[0] == "ok"
    assert len(attributes[0]) == 80
    assert screen[0] == text


def test_a_scraped_screen_reports_nothing_unread():
    """A backend reading resolved characters cannot misread one."""
    assert recognize.unreadable_cells((["ready"], [[0x07] * 80])) == ()


def test_a_single_bank_may_be_given_as_bytes_or_a_sequence():
    stored = recognize.glyph_bank()
    assert recognize.as_banks(stored) == (stored,)
    assert recognize.as_banks([stored]) == (stored,)
    assert recognize.as_banks(None) == (stored,)


def test_save_screen_writes_a_png(tmp_path):
    path = os.path.join(str(tmp_path), "screen.png")
    recognize.save_screen(path, _screen("ok"))
    assert os.path.isfile(path)
    text, _attrs = recognize.recognize(path)
    assert text[0] == "ok"
