# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for the fixed-font text-screen recognizer (F51).

Fixtures are rendered with the same glyph bank the recognizer
reads — no hypervisor, and a failing round-trip is a defect.
"""

import os
import tempfile
import unittest

from PIL import Image

from reliquary import text_recognize as recognize
from vga_bank import vga_bank
from reliquary.errors import (PreflightError, StaticError, UnreadableScreen,
                              exit_code)


_FIX = os.path.join(os.path.dirname(__file__), "fixtures", "text_recognize")


def _screen(*lines, rows=25):
    """Pad ``lines`` to a full ``rows``-row text screen."""
    out = list(lines)
    while len(out) < rows:
        out.append("")
    return out[:rows]


class GlyphBankTests(unittest.TestCase):
    def test_bank_is_4096_bytes(self):
        self.assertEqual(len(recognize.glyph_bank()), 4096)

    def test_space_is_blank(self):
        bits = recognize._glyph_bits(0x20)
        self.assertFalse(any(bits))

    def test_letter_a_is_not_blank(self):
        self.assertTrue(any(recognize._glyph_bits(0x41)))


class AttributeTokenTests(unittest.TestCase):
    def test_equal_colours_compare_equal(self):
        a = recognize.attribute_token((170, 170, 170), (0, 0, 0))
        b = recognize.attribute_token((170, 170, 170), (0, 0, 0))
        self.assertEqual(a, b)

    def test_different_pairs_differ(self):
        plain = recognize.attribute_token((170, 170, 170), (0, 0, 0))
        highlight = recognize.attribute_token((0, 0, 0), (170, 170, 170))
        self.assertNotEqual(plain, highlight)


class RoundTripTests(unittest.TestCase):
    def test_ascii_prompt_round_trips(self):
        rows = _screen("", "", "C:\\>")
        image = recognize.render(rows)
        text, attrs = recognize.recognize(image)
        self.assertEqual(text[2], "C:\\>")
        self.assertEqual(len(attrs), 25)
        self.assertEqual(len(attrs[2]), 80)

    def test_freedos_welcome_line_round_trips(self):
        # The string FreeDOS install waits for (freedos-install.rlqs).
        line = "Welcome to FreeDOS 1.4 (LiveCD)"
        rows = _screen(line)
        image = recognize.render(rows)
        text, _attrs = recognize.recognize(image)
        self.assertEqual(text[0], line)

    def test_highlight_row_tokens_differ(self):
        rows = _screen("Install to harddisk", "Return to DOS")
        grey = (170, 170, 170)
        black = (0, 0, 0)
        attrs = [[(grey, black)] * 80 for _ in range(25)]
        # Invert the first menu row — the cursor bar.
        attrs[0] = [(black, grey)] * 80
        image = recognize.render(rows, attrs)
        _text, tokens = recognize.recognize(image)
        self.assertNotEqual(tokens[0][0], tokens[1][0])
        # Letter cells on the bar share a token; a space cell cannot
        # show its foreground in the framebuffer, so it is not asked.
        self.assertEqual(tokens[0][0], tokens[0][1])  # 'I' and 'n'

    def test_nine_dot_cells_still_recognize(self):
        rows = _screen("Ready.")
        image = recognize.render(rows, cell_w=9, cell_h=16)
        self.assertEqual(image.size, (720, 400))
        text, _attrs = recognize.recognize(image)
        self.assertEqual(text[0], "Ready.")


class FixtureTests(unittest.TestCase):
    """Golden PNGs under tests/fixtures/text_recognize/."""

    def test_each_fixture_matches_its_expected_text(self):
        self.assertTrue(os.path.isdir(_FIX), f"missing {_FIX}")
        fixtures = sorted(
            name for name in os.listdir(_FIX) if name.endswith(".png"))
        self.assertGreaterEqual(len(fixtures), 1)
        for name in fixtures:
            with self.subTest(fixture=name):
                png = os.path.join(_FIX, name)
                expected_path = os.path.join(
                    _FIX, name[:-4] + ".txt")
                with open(expected_path, encoding="utf-8") as handle:
                    expected = handle.read().splitlines()
                # Pad expected to 25 for comparison of present lines.
                text, _attrs = recognize.recognize(png)
                for index, line in enumerate(expected):
                    self.assertEqual(
                        text[index], line,
                        f"{name} row {index}")


class GeometryTests(unittest.TestCase):
    def test_bad_geometry_is_an_unreadable_screen(self):
        """A guest's video mode is never the author's mistake."""
        image = Image.new("RGB", (100, 100), (0, 0, 0))
        with self.assertRaises(UnreadableScreen) as caught:
            recognize.recognize(image)
        self.assertEqual(caught.exception.rule_id, "recognize.geometry")
        self.assertNotIsInstance(caught.exception, StaticError)
        self.assertEqual(exit_code(caught.exception), 4)

    def test_a_bios_splash_resolution_is_refused_by_name(self):
        """The 640x480 mode every VirtualBox boot passes through."""
        image = Image.new("RGB", (640, 480), (0, 0, 0))
        with self.assertRaises(UnreadableScreen) as caught:
            recognize.recognize(image)
        self.assertIn("640x480", str(caught.exception))


def _swapped_bank(first, second):
    """The shipped bank with two glyphs exchanged."""
    data = bytearray(recognize.glyph_bank())
    a, b = first * 16, second * 16
    data[a:a + 16], data[b:b + 16] = data[b:b + 16], data[a:a + 16]
    return bytes(data)


class GlyphBankSourceTests(unittest.TestCase):
    """A backend's font is read off the host, never vendored here.

    These build their fixtures from the *shipped* bank, so the suite
    carries no other project's font — which is the same rule the
    runtime obeys.
    """

    def test_a_supplied_bank_decides_what_a_glyph_reads_as(self):
        image = recognize.render(_screen("W"))
        self.assertEqual(recognize.recognize(image)[0][0], "W")
        # 0x55 'U' now holds the W bitmap, so that is what matches.
        swapped = _swapped_bank(0x55, 0x57)
        self.assertEqual(
            recognize.recognize(image, bank=swapped)[0][0], "U")

    def test_a_bank_is_carved_out_of_a_binary_by_the_classic_a(self):
        embedded = vga_bank()
        binary = (b"\x00" * 1234) + embedded + (b"\xa5" * 77)
        self.assertEqual(
            recognize.bank_from_binary(binary, "fake.dll"), embedded)

    def test_reliquarys_own_bank_carries_no_borrowed_anchor(self):
        """The locator's anchor is a real BIOS's, and ours is not one.

        `CLASSIC_A` is in the source because a bank cannot be found in
        a binary without knowing what to look for. Reliquary's own
        bank is drawn rather than dumped, so its `A` is its own — and
        a test that wanted a *findable* bank had to say so, which is
        what `vga_bank` is for.
        """
        self.assertNotIn(recognize.CLASSIC_A, recognize.glyph_bank())

    def test_a_binary_without_the_anchor_fails_closed(self):
        with self.assertRaises(PreflightError) as caught:
            recognize.bank_from_binary(b"\x00" * 8192, "fake.dll")
        self.assertEqual(caught.exception.rule_id,
                         "recognize.font-not-found")

    def test_a_truncated_bank_fails_closed(self):
        shipped = vga_bank()
        with self.assertRaises(PreflightError) as caught:
            recognize.bank_from_binary(shipped[:2048], "fake.dll")
        self.assertEqual(caught.exception.rule_id,
                         "recognize.font-not-found")


def _patch_table(entries, height=16):
    """An override table: ``(code, rows...)`` runs closed by a zero."""
    out = bytearray()
    for code, fill in entries:
        out.append(code)
        out.extend(bytes([fill]) * height)
    out.append(0x00)
    return bytes(out)


class SeveralFontsTests(unittest.TestCase):
    """More than one font is painted per run, and pixels do not say which.

    A VGA BIOS installs its bank with an override table applied and
    draws its own messages that way; a DOS guest loads its own font
    and draws with that. The recognizer is given every font a host
    offers and matches against all of them, which is why a screen
    drawn in *one* of them reads correctly either way. Fixtures are
    built from the shipped bank, so the suite still vendors no other
    project's font.
    """

    #: A shape no CP437 glyph has, so that a cell drawn with it is
    #: unambiguous. An override table gives a code a *different
    #: drawing of the same character* — never another code's shape —
    #: so a fixture that merely exchanged two glyphs would make one
    #: bitmap legitimately mean two codes and prove nothing.
    DISTINCT = bytes([0x80, 0x40, 0x20, 0x10, 0x08, 0x04, 0x02, 0x01] * 2)

    def _two_fonts(self):
        stored = recognize.glyph_bank()
        installed = (stored[:0x57 * 16] + self.DISTINCT
                     + stored[0x58 * 16:])
        return stored, installed

    def test_a_screen_reads_through_whichever_font_drew_it(self):
        stored, installed = self._two_fonts()
        for drawn_with, name in ((stored, "stored"),
                                 (installed, "installed")):
            image = recognize.render(_screen("W"), bank=drawn_with)
            rows, _ = recognize.recognize(image, bank=(stored, installed))
            self.assertEqual(rows[0][0], "W", f"drawn with the {name} font")

    def test_one_font_alone_misreads_a_screen_the_other_drew(self):
        """The defect being fixed, stated as the reason for the above.

        *How* it fails depends on the shape: a glyph far from anything
        in the font read through falls past the distance threshold and
        blanks, while the real 19 sit close enough to other letters to
        come back as the wrong one — `Welcome` as `Uelcooe`. Either
        way the word a script waits for is not there, which is the
        only part worth pinning.
        """
        stored, installed = self._two_fonts()
        image = recognize.render(_screen("W"), bank=installed)
        rows, _ = recognize.recognize(image, bank=stored)
        self.assertNotIn("W", rows[0])

    def test_shared_glyphs_are_scored_once(self):
        """Supporting several fonts costs only where they disagree."""
        stored, installed = self._two_fonts()
        one = recognize._all_glyph_bits((stored,))
        both = recognize._all_glyph_bits((stored, installed))
        self.assertEqual(len(one), 256)
        self.assertEqual(len(both), 256 + 1)

    def test_an_override_table_behind_a_bank_yields_a_second_font(self):
        stored = vga_bank()
        binary = (b"\x00" * 64 + stored
                  + _patch_table([(0x57, 0x5a)]) + b"\xa5" * 40)
        banks = recognize.banks_from_binary(binary, "fake.dll")
        self.assertEqual(len(banks), 2)
        self.assertEqual(banks[0], stored)
        self.assertEqual(banks[1][0x57 * 16:0x58 * 16], b"\x5a" * 16)

    def test_a_table_for_another_glyph_height_is_stepped_over(self):
        """A BIOS carries a table per size; only 8x16 is this reader's."""
        stored = vga_bank()
        binary = (b"\x00" * 64 + stored
                  + _patch_table([(0x1d, 0x11), (0x22, 0x11)], height=14)
                  + _patch_table([(0x57, 0x5a)])
                  + b"\xa5" * 40)
        banks = recognize.banks_from_binary(binary, "fake.dll")
        self.assertEqual(len(banks), 2)
        self.assertEqual(banks[1][0x57 * 16:0x58 * 16], b"\x5a" * 16)

    def test_identical_fonts_collapse_to_one(self):
        """Three copies of a BIOS image are not three fonts."""
        stored = vga_bank()
        binary = b"".join([b"\x00" * 8 + stored] * 3)
        self.assertEqual(recognize.banks_from_binary(binary, "fake.dll"),
                         (stored,))

    def test_bytes_that_are_not_a_table_add_no_font(self):
        """Arbitrary bytes behind a bank must not become glyph shapes."""
        stored = vga_bank()
        # Descending codes: a real override table ascends.
        noise = bytes([0x90]) + b"\x11" * 16 + bytes([0x10]) + b"\x11" * 16
        binary = b"\x00" * 64 + stored + noise + b"\x00"
        self.assertEqual(recognize.banks_from_binary(binary, "fake.dll"),
                         (stored,))

    def test_a_single_bank_may_be_given_as_bytes_or_a_sequence(self):
        stored = recognize.glyph_bank()
        self.assertEqual(recognize.as_banks(stored), (stored,))
        self.assertEqual(recognize.as_banks([stored]), (stored,))
        self.assertEqual(recognize.as_banks(None), (stored,))


class RenderSaveTests(unittest.TestCase):
    def test_save_screen_writes_a_png(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "screen.png")
            recognize.save_screen(path, _screen("ok"))
            self.assertTrue(os.path.isfile(path))
            text, _attrs = recognize.recognize(path)
            self.assertEqual(text[0], "ok")
