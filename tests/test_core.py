# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Installed unit tests for agentless helpers and guest program runs."""

import importlib
import json
import os
import sys
import tempfile
import types
import unittest
from unittest import mock

try:
    import qemu.qmp  # noqa: F401
except ModuleNotFoundError:
    qmp = types.ModuleType("qemu.qmp")
    qmp.ConnectError = type("ConnectError", (Exception,), {})
    qmp.ExecuteError = type("ExecuteError", (Exception,), {})
    qmp.QMPClient = object
    qemu = types.ModuleType("qemu")
    qemu.qmp = qmp
    sys.modules["qemu"] = qemu
    sys.modules["qemu.qmp"] = qmp

import contextlib

import reliquary
from reliquary import backend_qemu as qemu_module
from reliquary import control_display as display_module
from reliquary import interaction as interaction_module
from reliquary import interaction_agentless as agentless_module
from reliquary import machine_handle as machine_module
from reliquary import machines as machines_module
from reliquary.errors import InternalError, PreflightError, RunFailure, StaticError
from reliquary import platform_dos as platform_dos_module
from tests import fake_backend


@contextlib.contextmanager
def _yielding(value):
    yield value


def _over(console):
    """Patch `Machine.console` to yield a stub console."""
    return mock.patch.object(
        machine_module.Machine, "console",
        lambda self: _yielding(console))


class HomeTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)

    def test_screenshot_rejects_names_that_are_paths(self):
        invalid_names = ("", ".", "..", "../outside", "..\\outside",
                         "/outside", "C:\\outside")

        with fake_backend.installed() as adapter:
            for name in invalid_names:
                with self.subTest(name=name):
                    with self.assertRaisesRegex(StaticError, "not a path"):
                        reliquary.screenshot(name, home=self.tempdir.name)

        # The name is judged before any session is opened.
        self.assertEqual(adapter.sessions, [])

    def test_screenshot_lands_under_the_machine_directory(self):
        # Where the image goes is Reliquary's policy and stays above
        # the seam; capturing the framebuffer is the adapter's carrier.
        vm = {"backend": "qemu", "backend-id": "reliquary-plain-0",
              "token": "0" * 32, "endpoint": {"port": 54321}}
        expected = os.path.join(
            self.tempdir.name, "screenshots", "release-smoke.png")

        with fake_backend.installed() as adapter, \
                mock.patch.object(machine_module, "read_vm_state",
                                  return_value=vm):
            written = reliquary.screenshot("release-smoke",
                                           home=self.tempdir.name)

        self.assertEqual(written, expected)
        self.assertEqual(adapter.sessions[-1].screenshots, [expected])
        self.assertTrue(os.path.isfile(expected))
    def test_planned_layout_paths_are_contained_by_configured_home(self):
        from reliquary import home
        root = self.tempdir.name
        cache = os.path.join(root, "cache")
        self.assertEqual(home.blueprints_dir(root),
                         os.path.join(root, "blueprints"))
        self.assertEqual(home.scripts_dir(root),
                         os.path.join(root, "scripts"))
        self.assertEqual(home.cache_dir(root), cache)
        self.assertEqual(home.media_dir(root),
                         os.path.join(cache, "media"))
        self.assertEqual(home.machines_dir(root),
                         os.path.join(cache, "machines"))

    def test_planned_layout_paths_honor_explicit_home(self):
        from reliquary import home
        other = tempfile.TemporaryDirectory()
        self.addCleanup(other.cleanup)
        root = other.name
        cache = os.path.join(root, "cache")
        self.assertEqual(home.blueprints_dir(context=root),
                         os.path.join(root, "blueprints"))
        self.assertEqual(home.scripts_dir(context=root),
                         os.path.join(root, "scripts"))
        self.assertEqual(home.cache_dir(context=root), cache)
        self.assertEqual(home.media_dir(context=root),
                         os.path.join(cache, "media"))
        self.assertEqual(home.machines_dir(context=root),
                         os.path.join(cache, "machines"))

    def test_documents_dir_is_absolute_or_none(self):
        """The platform Documents lookup behind the default home."""
        from reliquary import home
        documents = home.documents_dir()
        if documents is not None:
            self.assertTrue(os.path.isabs(documents))

    def _write_state(self, document):
        # The live-VM identity is folded into machine.json's `vm`
        # section; author the machine-state file directly.
        os.makedirs(self.tempdir.name, exist_ok=True)
        with open(os.path.join(self.tempdir.name, "machine.json"), "w",
                  encoding="utf-8") as state:
            json.dump(document, state)

    def _read_vm(self):
        return machines_module.read_vm_state(self.tempdir.name)

    def test_vm_state_round_trip(self):
        vm = {"backend": "qemu", "backend-id": "reliquary-test-0",
              "token": "12345678-1234-1234-1234-123456789012",
              "endpoint": {"port": 54321}, "pid": 1234}
        self._write_state({"id": "reliquary-test-0", "phase": "running",
                           "vm": vm})

        self.assertEqual(self._read_vm(), vm)

    def test_no_vm_section_reads_as_none(self):
        # A stopped machine has no `vm` section — that is
        # not-running, not an error.
        self._write_state({"id": "reliquary-test-0", "phase": "ready"})
        self.assertIsNone(self._read_vm())

    def test_a_vm_record_naming_no_backend_is_rejected(self):
        # Which adapter owns the VM is the first thing the record has
        # to say: without it there is nobody to verify it against.
        self._write_state({"vm": {"backend-id": "reliquary-test-0",
                                  "token": "0" * 32,
                                  "endpoint": {"port": 54321}}})

        with self.assertRaisesRegex(InternalError, "invalid reliquary VM state"):
            self._read_vm()

    def test_vm_state_without_a_token_is_rejected(self):
        # a readable name alone cannot identify a VM instance; a `vm`
        # section without the per-start token is invalid, not
        # grandfathered
        self._write_state({"vm": {"backend": "qemu",
                                  "backend-id": "reliquary-test-0",
                                  "endpoint": {"port": 54321},
                                  "pid": 1234}})

        with self.assertRaisesRegex(InternalError, "invalid reliquary VM state"):
            self._read_vm()

    def test_a_machine_with_no_recorded_vm_fails_closed(self):
        self._write_state({"id": "reliquary-test-0", "phase": "ready"})
        with self.assertRaisesRegex(PreflightError, "no active reliquary VM"):
            machine_module.Machine(self.tempdir.name).screen_text()

class InputAndScreenTests(unittest.TestCase):
    """The display console's own composition, over any adapter."""

    def test_character_key_mappings(self):
        self.assertEqual(display_module.char_keys("a"), ["a"])
        self.assertEqual(display_module.char_keys("A"), ["shift", "a"])
        self.assertEqual(display_module.char_keys(":"),
                         ["shift", "semicolon"])
        self.assertEqual(display_module.char_keys(" "), ["spc"])

    def test_unmapped_character_is_rejected(self):
        with self.assertRaisesRegex(StaticError, "no key mapping"):
            display_module.char_keys("\N{SNOWMAN}")

    def test_send_text_builds_key_combinations(self):
        console = display_module.DisplayConsole(None)
        with mock.patch.object(console, "send_keys") as send_keys:
            console.send_text("A:")

        send_keys.assert_called_once_with(
            [["shift", "a"], ["shift", "semicolon"], ["ret"]])

    def test_the_console_reads_characters_off_the_text_screen(self):
        session = mock.Mock()
        session.text_screen.return_value = (
            ["A:\\>"] + [""] * 24, [[0x07] * 80 for _ in range(25)])

        rows = display_module.DisplayConsole(session).screen_text()

        self.assertEqual(len(rows), 25)
        self.assertEqual(rows[0], "A:\\>")
        self.assertTrue(all(row == "" for row in rows[1:]))

    def test_the_console_sends_keys_through_the_session(self):
        session = mock.Mock()
        display_module.DisplayConsole(session).send_keys([["ret"]])
        session.send_keys.assert_called_once_with([["ret"]], 0.06)

    def test_wait_text_returns_the_matching_screen(self):
        console = mock.Mock()
        console.screen_text.return_value = [
            "Welcome to FreeDOS 1.4 (LiveCD)"]
        with _over(console), mock.patch.object(machine_module.time, "sleep"):
            screen = machine_module.Machine().wait_text(
                r"Welcome to FreeDOS")

        self.assertIn("FreeDOS 1.4", screen)

    def test_wait_text_times_out_without_a_match(self):
        console = mock.Mock()
        console.screen_text.return_value = [""]
        with _over(console), mock.patch.object(machine_module.time, "sleep"):
            with self.assertRaisesRegex(RunFailure, "FreeDOS"):
                machine_module.Machine().wait_text("FreeDOS", timeout=0)


class _MenuClock:
    """A deterministic monotonic clock advanced by sleeping.

    Each reading also advances time a little, so a loop polling
    without sleeping still reaches its deadline instead of hanging
    the test run.
    """

    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        self.now += 0.001
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class _FakeMenu:
    """A cursor-key menu rendered as VGA text and attribute rows."""

    def __init__(self, items, cursor=0, stuck=False):
        self.items = items
        self.cursor = cursor
        self.stuck = stuck
        self.selected = None

    def screen(self):
        rows = ["Welcome menu", ""] + list(self.items)
        rows += [""] * (25 - len(rows))
        attributes = [[0x1B] * 80 for _ in range(25)]
        attributes[2 + self.cursor] = [0x70] * 80
        return rows, attributes

    def press(self, key):
        if key == "ret":
            self.selected = self.cursor
        elif self.stuck:
            pass
        elif key == "down" and self.cursor + 1 < len(self.items):
            self.cursor += 1
        elif key == "up" and self.cursor > 0:
            self.cursor -= 1


class _FakeLanguageMenu(_FakeMenu):
    """Rewrites every row in the newly highlighted language."""

    def __init__(self, rendered):
        self._rendered = rendered
        super().__init__(rendered[0])

    def screen(self):
        self.items = self._rendered[self.cursor]
        return super().screen()


class _SlowLanguageMenu(_FakeLanguageMenu):
    """Repaints over several reads: bar removed, then rows redrawn.

    After each cursor move one screen read still shows the old rows
    with the selection bar already erased; only the next read shows
    the finished screen, like the FreeDOS language chooser slowly
    retranslating itself.
    """

    def __init__(self, rendered):
        super().__init__(rendered)
        self._frames = []

    def press(self, key):
        before = self.cursor
        super().press(key)
        if key != "ret" and self.cursor != before:
            rows = ["Welcome menu", ""] + list(self._rendered[before])
            rows += [""] * (25 - len(rows))
            self._frames.append(
                (rows, [[0x1B] * 80 for _ in range(25)]))

    def screen(self):
        if self._frames:
            return self._frames.pop(0)
        return super().screen()


class _PausingLanguageMenu:
    """Repaints slowly with a mid-repaint pause and flushes type-ahead.

    Mimics the FreeDOS language chooser: a blue backdrop, a grey
    dialog, a selection bar. A cursor move first shows a half-drawn
    screen — bar erased, one dialog row overdrawn with backdrop —
    holds it for several reads (translations loading from CD), then
    paints the finished screen in the new language. Keys pressed
    while the repaint is pending are discarded, like a menu flushing
    its type-ahead buffer.
    """

    BACKDROP = 0x1F
    NORMAL = 0x07
    BAR = 0x70

    def __init__(self, rendered):
        self._rendered = rendered
        self.cursor = 0
        self.selected = None
        self._frames = []

    def _screen(self, items, bar_row):
        rows = ["Welcome menu", ""] + list(items)
        rows += [""] * (25 - len(rows))
        attributes = [[self.BACKDROP] * 80 for _ in range(25)]
        for row in range(2, 2 + len(items)):
            attributes[row] = [self.NORMAL] * 80
        if bar_row is not None:
            attributes[bar_row] = [self.BAR] * 80
        return rows, attributes

    def press(self, key):
        if self._frames:
            return
        if key == "ret":
            self.selected = self.cursor
            return
        before = self.cursor
        if key == "down" and self.cursor + 1 < len(self._rendered):
            self.cursor += 1
        elif key == "up" and self.cursor > 0:
            self.cursor -= 1
        else:
            return
        items = self._rendered[before]
        rows, attributes = self._screen(items, None)
        attributes[2 + len(items) - 1] = [self.BACKDROP] * 80
        self._frames = [(rows, attributes)] * 4

    def screen(self):
        if self._frames:
            return self._frames.pop(0)
        return self._screen(self._rendered[self.cursor],
                            2 + self.cursor)


class _RecognizedLanguageMenu:
    """The FreeDOS language chooser as a *recognizer* reports it.

    The other fakes here render VGA attribute bytes, where a row wears
    one attribute and the selection bar is that row's alone. A
    screenshot backend has no such bytes: tokens come from each cell's
    foreground/background pixels, and a blank cell shows only one
    colour — so nothing can tell its foreground from its background
    and it cannot carry a lettered cell's token. The bar is painted
    across the dialog, so its own padding reads as the *backdrop*
    token, the most common on screen.

    That is the screen the frequency reading cannot classify: the
    dominant token among the newly highlighted row's changed cells is
    the backdrop's. Every row is also retranslated per keypress, which
    is what the real chooser does.
    """

    BACKDROP = 0xB10CC     # blue on blue: the bar's padding, and the
    DIALOG = 0xD1A106      # whole screen outside the dialog
    NORMAL_TEXT = 0x7E77
    BAR_TEXT = 0xBA12

    _LEFT, _RIGHT = 10, 51

    def __init__(self, rendered):
        self._rendered = rendered
        self.cursor = 0
        self.selected = None

    def screen(self):
        items = self._rendered[self.cursor]
        rows = ["Welcome menu", ""] + list(items)
        rows += [""] * (25 - len(rows))
        attributes = [[self.BACKDROP] * 80 for _ in range(25)]
        for number in range(2, 2 + len(items)):
            highlighted = number == 2 + self.cursor
            text = rows[number]
            for column in range(self._LEFT, self._RIGHT):
                lettered = (column - self._LEFT) < len(text.strip())
                if lettered:
                    attributes[number][column] = (
                        self.BAR_TEXT if highlighted
                        else self.NORMAL_TEXT)
                else:
                    # The pathology: a blank cell inside the bar is
                    # indistinguishable from the backdrop outside it.
                    attributes[number][column] = (
                        self.BACKDROP if highlighted else self.DIALOG)
        return rows, attributes

    def press(self, key):
        if key == "ret":
            self.selected = self.cursor
        elif key == "down" and self.cursor + 1 < len(self._rendered):
            self.cursor += 1
        elif key == "up" and self.cursor > 0:
            self.cursor -= 1


class _PaintingMenu(_FakeMenu):
    """Still painting its dialog when selection starts.

    For the first reads the selection bar flickers as the menu
    draws itself; only after `frames` reads does the screen hold
    still. Sampling for the animation mask during that paint used
    to blind highlight tracking to the bar's own cells.
    """

    def __init__(self, items, frames):
        super().__init__(items)
        self._painting = frames

    def screen(self):
        rows, attributes = super().screen()
        if self._painting > 0:
            self._painting -= 1
            if self._painting % 2:
                attributes[2 + self.cursor] = [0x1B] * 80
        return rows, attributes


class _BlinkingClockMenu(_FakeMenu):
    """A menu with a status-line clock that repaints on every read."""

    def __init__(self, items):
        super().__init__(items)
        self._tick = 0

    def screen(self):
        rows, attributes = super().screen()
        self._tick += 1
        rows[24] = "12:0%d" % (self._tick % 10)
        attributes[24] = list(attributes[24])
        attributes[24][0] = 0x8E if self._tick % 2 else 0x0E
        return rows, attributes


class CursorMenuTests(unittest.TestCase):
    def _select(self, menu, item, timeout=30, exclude=()):
        console = display_module.DisplayConsole(None)
        console.screen = menu.screen
        console.send_keys = lambda combos, delay=0.06: [
            menu.press(combo[0]) for combo in combos]
        clock = _MenuClock()
        with mock.patch.object(display_module.time, "monotonic",
                               clock.monotonic), \
                mock.patch.object(display_module.time, "sleep",
                                  clock.sleep):
            return console.cursor_menu_select(item, timeout, exclude)

    def test_select_moves_down_to_the_matching_item(self):
        menu = _FakeMenu(["Use FreeDOS 1.4 in Live Environment mode",
                          "Boot from system harddisk",
                          "Install to harddisk"])

        selected = self._select(menu, "install TO harddisk")

        self.assertEqual(menu.selected, 2)
        self.assertEqual(selected, "Install to harddisk")

    def test_select_probes_upward_from_the_bottom_of_the_menu(self):
        menu = _FakeMenu(["First item", "Second item", "Third item"],
                         cursor=2)

        selected = self._select(menu, "First item")

        self.assertEqual(menu.selected, 0)
        self.assertEqual(selected, "First item")

    def test_missing_item_is_rejected_before_any_keypress(self):
        menu = _FakeMenu(["Boot from system harddisk"])

        with self.assertRaisesRegex(RunFailure, "not on screen"):
            self._select(menu, "Boot from floppy")

        self.assertEqual(menu.cursor, 0)
        self.assertIsNone(menu.selected)

    def test_exact_item_beats_rows_that_merely_contain_it(self):
        menu = _FakeMenu([
            "Plain DOS system",
            "Plain DOS system, with sources",
            "Full installation including applications and games",
            "Full installation with sources",
        ], cursor=2)

        selected = self._select(menu, "plain dos system")

        self.assertEqual(menu.selected, 0)
        self.assertEqual(selected, "Plain DOS system")

    def test_the_longer_sibling_row_stays_selectable(self):
        menu = _FakeMenu(["Plain DOS system",
                          "Plain DOS system, with sources"])

        selected = self._select(menu, "Plain DOS system, with sources")

        self.assertEqual(menu.selected, 1)
        self.assertEqual(selected, "Plain DOS system, with sources")

    def test_rows_rewritten_per_highlight_navigate_by_row(self):
        menu = _FakeLanguageMenu([
            ["English", "German", "Spanish"],
            ["Englisch", "Deutsch", "Spanisch"],
            ["Inglés", "Alemán", "Español"],
        ])

        selected = self._select(menu, "Spanish")

        self.assertEqual(menu.selected, 2)
        self.assertEqual(selected, "Español")

    def test_a_slow_redraw_does_not_select_the_probed_neighbor(self):
        # the first read after a cursor move catches the bar already
        # erased but the new bar not yet drawn; concluding from that
        # half-drawn screen selected the wrong language
        menu = _SlowLanguageMenu([
            ["English", "German"],
            ["Englisch", "Deutsch"],
        ])

        selected = self._select(menu, "English")

        self.assertEqual(menu.selected, 0)
        self.assertEqual(selected, "English")

    def test_a_repaint_pause_does_not_pass_for_a_settled_screen(self):
        # the chooser pauses mid-repaint while loading translations;
        # concluding from the half-drawn screen pressed ENTER into a
        # busy menu that flushed it, reporting success while the
        # guest still sat unselected at the menu
        menu = _PausingLanguageMenu([
            ["English", "German", "Spanish", "French"],
            ["Englisch", "Deutsch", "Spanisch", "Franz sisch"],
            ["Ingl s", "Alem n", "Espa ol", "Franc s"],
            ["Anglais", "Allemand", "Espagnol", "Fran ais"],
        ])

        selected = self._select(menu, "English")

        self.assertEqual(menu.selected, 0)
        self.assertEqual(selected, "English")

    def test_selection_waits_out_the_menus_own_initial_paint(self):
        # sampling for the animation mask while the menu was still
        # painting masked the bar's cells as "animation" and blinded
        # the tracking to every later bar movement
        menu = _PaintingMenu(["First item", "Second item"], frames=4)

        selected = self._select(menu, "First item")

        self.assertEqual(menu.selected, 0)
        self.assertEqual(selected, "First item")

    def test_a_self_updating_clock_cell_is_ignored(self):
        menu = _BlinkingClockMenu(["First item", "Second item"])

        selected = self._select(menu, "Second item")

        self.assertEqual(menu.selected, 1)
        self.assertEqual(selected, "Second item")

    def test_a_lone_unhighlight_is_not_a_new_cursor_position(self):
        before = [[0x1B] * 80 for _ in range(25)]
        before[2] = [0x70] * 80
        after = [[0x1B] * 80 for _ in range(25)]

        self.assertEqual(display_module._bar_move(before, after),
                         (None, None))

    def test_the_bar_is_followed_on_a_recognized_framebuffer(self):
        # F52's live failure: cell tokens recovered from pixels rather
        # than VGA bytes, on a menu that retranslates every row.
        menu = _RecognizedLanguageMenu([
            ["English", "German", "Esperanto"],
            ["Englisch", "Deutsch", "Esperanto"],
            ["angla", "germana", "esperanto"],
        ])

        selected = self._select(menu, "German")

        self.assertEqual(menu.selected, 1)
        self.assertEqual(selected, "Deutsch")

    def test_the_frequency_reading_alone_cannot_place_that_bar(self):
        """Why the rule is confinement and not rarity.

        The dominant token among the newly highlighted row's changed
        cells is the backdrop's — the most common on screen — so the
        frequency reading discards it, and the bar has to be found as
        the row-unique attribute that moved.
        """
        menu = _RecognizedLanguageMenu([
            ["English", "German", "Esperanto"],
            ["Englisch", "Deutsch", "Esperanto"],
            ["angla", "germana", "esperanto"],
        ])
        _rows, before = menu.screen()
        menu.press("down")
        _rows, after = menu.screen()

        dominant = display_module._changed_attribute(before, after, 3)
        self.assertEqual(dominant, _RecognizedLanguageMenu.BACKDROP)
        occurrences = sum(row.count(dominant) for row in after)
        self.assertGreater(occurrences, 160)

        row, attribute = display_module._bar_move(before, after)
        self.assertEqual(row, 3)
        self.assertEqual(attribute, _RecognizedLanguageMenu.BAR_TEXT)

    def test_a_two_item_menu_is_settled_by_the_key_direction(self):
        """Confinement ties; the bar is the one that went down.

        With exactly one unhighlighted row, its token is row-unique
        too, so two attributes make an equally good move. They move in
        opposite directions, and the key just pressed says which one
        the bar is.
        """
        menu = _RecognizedLanguageMenu([
            ["English", "German"], ["Englisch", "Deutsch"]])
        _rows, before = menu.screen()
        menu.press("down")
        _rows, after = menu.screen()

        self.assertEqual(
            display_module._relocated_bar(before, after), (None, None))
        self.assertEqual(
            display_module._relocated_bar(before, after, direction=1),
            (3, _RecognizedLanguageMenu.BAR_TEXT))

    def test_a_two_item_recognized_menu_selects_end_to_end(self):
        menu = _RecognizedLanguageMenu([
            ["English", "German"], ["Englisch", "Deutsch"]])

        selected = self._select(menu, "German")

        self.assertEqual(menu.selected, 1)
        self.assertEqual(selected, "Deutsch")

    def test_a_neighbor_rewritten_by_the_probe_is_still_selected(self):
        # moving off "English" rewrites the list in French, and the
        # accented "Français" renders through VGA text as "Fran ais"
        menu = _FakeLanguageMenu([
            ["English", "French"],
            ["Anglais", "Fran ais"],
        ])

        selected = self._select(menu, "French")

        self.assertEqual(menu.selected, 1)
        self.assertEqual(selected, "Fran ais")

    def test_excluded_text_resolves_an_ambiguous_item(self):
        menu = _FakeMenu(["Install to harddisk",
                          "Install using Floppy Edition"])

        selected = self._select(menu, "Install", exclude="Floppy")

        self.assertEqual(menu.selected, 0)
        self.assertEqual(selected, "Install to harddisk")

    def test_an_item_matching_only_excluded_rows_is_rejected(self):
        menu = _FakeMenu(["Plain DOS system, with sources",
                          "Full installation with sources"])

        with self.assertRaisesRegex(RunFailure, "excluded rows"):
            self._select(menu, "Plain DOS system",
                         exclude=["sources"])

        self.assertIsNone(menu.selected)

    def test_ambiguous_item_is_rejected(self):
        menu = _FakeMenu(["Install to harddisk",
                          "Install using Floppy Edition"])

        with self.assertRaisesRegex(RunFailure, "multiple rows"):
            self._select(menu, "Install")

        self.assertIsNone(menu.selected)

    def test_unresponsive_menu_raises(self):
        menu = _FakeMenu(["First item", "Second item"], stuck=True)

        with self.assertRaisesRegex(RunFailure,
                                    "no menu highlight responded"):
            self._select(menu, "Second item")

        self.assertIsNone(menu.selected)

    def test_unselectable_row_raises_when_the_cursor_cannot_reach_it(self):
        menu = _FakeMenu(["First item", "Second item"])

        with self.assertRaisesRegex(RunFailure, "stopped responding"):
            self._select(menu, "Welcome menu")

        self.assertIsNone(menu.selected)


class BootToDosTests(unittest.TestCase):
    def test_reaches_an_existing_prompt_without_typing(self):
        console = mock.Mock()
        console.screen_text.return_value = ["A:\\>"] + [""] * 24
        with _over(console), \
                mock.patch.object(agentless_module.time, "sleep"):
            agentless_module.AgentlessGuestExec(
                machine_module.Machine()).wait_ready()

        console.send_text.assert_not_called()

    def test_times_out_without_a_prompt(self):
        console = mock.Mock()
        console.screen_text.return_value = [""] * 25
        with _over(console), \
                mock.patch.object(agentless_module.time, "sleep"):
            with self.assertRaisesRegex(RunFailure, "DOS prompt"):
                agentless_module.AgentlessGuestExec(
                    machine_module.Machine()).wait_ready(timeout=0)

class InteractionAdapterTests(unittest.TestCase):
    def test_a_machine_session_comes_from_its_recorded_backend(self):
        vm = {"backend": "qemu", "backend-id": "reliquary-plain-0",
              "token": "0" * 32, "endpoint": {"port": 54321}}
        adapter = fake_backend.FakeAdapter()
        with fake_backend.installed(adapter), \
                mock.patch.object(machine_module, "read_vm_state",
                                  return_value=vm) as recorded:
            with machine_module.Machine("run-home").session() as session:
                self.assertIs(session, adapter.sessions[-1])
                self.assertEqual(session.vm, vm)
        recorded.assert_called_once_with("run-home")

    def test_the_qmp_seam_is_refused_on_another_backend(self):
        # The native escape hatch is explicitly backend-scoped: a
        # machine that is not QEMU's says so rather than offering an
        # approximation of a QMP monitor.
        vm = {"backend": "virtualbox", "backend-id": "vbox-uuid",
              "token": "0" * 32, "endpoint": {}}
        with fake_backend.installed(name="virtualbox"), \
                mock.patch.object(machine_module, "read_vm_state",
                                  return_value=vm):
            with self.assertRaisesRegex(PreflightError, "no QMP monitor"):
                with machine_module.Machine("run-home").qmp():
                    pass

    def test_package_exposes_the_protocol_and_agentless_adapter(self):
        self.assertIs(reliquary.GuestExec, interaction_module.GuestExec)
        self.assertIs(reliquary.AgentlessGuestExec,
                      agentless_module.AgentlessGuestExec)
        self.assertIs(reliquary.cursor_menu_select,
                      machine_module.cursor_menu_select)

    def test_agentless_adapter_satisfies_guest_exec_protocol(self):
        adapter = agentless_module.AgentlessGuestExec(
            machine_module.Machine())

        self.assertIsInstance(adapter, interaction_module.GuestExec)


class _GuestClock:
    """A deterministic clock advanced only by sleeping."""

    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class _PaintingGuest:
    """A guest that hands back one frame per read, then holds.

    Frames are given as row lists; the console contract's attribute
    half is supplied uniformly, so a test says what the guest drew
    without spelling out a second grid.
    """

    def __init__(self, frames):
        self._frames = [list(rows) + [""] * (25 - len(rows))
                        for rows in frames]
        self._index = 0

    def screen(self):
        rows = self._frames[min(self._index, len(self._frames) - 1)]
        self._index += 1
        return list(rows), [[0x07] * 80 for _ in range(25)]

    def screen_text(self):
        return self.screen()[0]


def _run_against(frames, command="dir", timeout=120):
    guest = _PaintingGuest(frames)
    console = mock.Mock()
    console.screen.side_effect = guest.screen
    console.screen_text.side_effect = guest.screen_text
    clock = _GuestClock()
    with _over(console), \
            mock.patch.object(agentless_module.time, "sleep",
                              clock.sleep), \
            mock.patch.object(agentless_module.time, "monotonic",
                              clock.monotonic):
        rows = agentless_module.AgentlessGuestExec(
            machine_module.Machine()).execute(command, timeout)
    return rows, console


class RunCommandTests(unittest.TestCase):
    def test_agentless_adapter_executes_through_display_console(self):
        # The screen has to *move*: a command completes when there is
        # evidence it ran, not when a prompt is visible, so a console
        # frozen at the prompt wait_ready left would wait out the whole
        # timeout — which is the behaviour, not a fixture quirk.
        rows, console = _run_against([
            ["C:\\>"],
            ["C:\\>dir", "2 FILE(S)", "C:\\>"],
        ])

        console.send_text.assert_called_once_with("dir")
        self.assertEqual(rows, ("2 FILE(S)",))

    def test_a_prompt_that_never_settles_says_so_when_it_expires(self):
        # a wait now expires two ways that look identical from
        # outside, and the second is baffling without help: a
        # screenshot taken at the time shows the prompt plainly
        frames = []
        for step in range(120):
            rows = ["C:\\>dir"] + [""] * 20 + ["C:\\>"]
            rows[1 + step % 18] = "x" * 40 + str(step)
            frames.append(rows)

        with self.assertRaises(RunFailure) as expired:
            _run_against(frames, timeout=5)

        message = str(expired.exception)
        self.assertIn("never settled", message)
        self.assertIn("stability", message)

    def test_waiting_out_a_long_command_keeps_the_slow_ramp(self):
        # dense reads are spent confirming a prompt, never waiting for
        # one: a long command must not be polled at settle pace for
        # its whole runtime just because the confirmation needs it
        guest = _PaintingGuest([["C:\\>fmt", "working..."]])
        console = mock.Mock()
        console.screen.side_effect = guest.screen
        console.screen_text.side_effect = guest.screen_text
        clock = _GuestClock()
        with _over(console), \
                mock.patch.object(agentless_module.time, "sleep",
                                  clock.sleep), \
                mock.patch.object(agentless_module.time, "monotonic",
                                  clock.monotonic):
            with self.assertRaises(RunFailure):
                agentless_module.AgentlessGuestExec(
                    machine_module.Machine()).execute("fmt", 13)

        # 3s of echo-catching at 0.1s, then 10s of waiting at 2.0s
        self.assertLess(console.screen.call_count, 60)
        self.assertGreater(console.screen.call_count, 25)

    def test_a_wait_that_never_saw_a_prompt_says_only_that(self):
        # the other expiry, and it must not borrow the first's
        # explanation: nothing was seen, so there is nothing to
        # explain about what was under it
        with self.assertRaises(RunFailure) as expired:
            _run_against([["C:\\>dir", "working..."]] * 120, timeout=5)

        self.assertNotIn("never settled", str(expired.exception))

    def test_a_prompt_on_a_still_painting_screen_is_not_completion(self):
        # the listing is still arriving when the prompt is already at
        # the bottom row; returning there slices at a boundary that
        # never existed and hands back a short, plausible, wrong tuple
        rows, _ = _run_against([
            ["C:\\>"],
            ["C:\\>dir", "FILE1", "C:\\>"],
            ["C:\\>dir", "FILE1", "FILE2", "FILE3", "C:\\>"],
        ])

        self.assertEqual(rows, ("FILE1", "FILE2", "FILE3"))

if __name__ == "__main__":
    unittest.main()
