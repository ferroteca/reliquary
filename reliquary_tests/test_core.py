# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Installed unit tests for agentless helpers and guest program runs."""

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

import reliquary
from reliquary import interaction as interaction_module
from reliquary import interaction_agentless as agentless_module
from reliquary import lifecycle as lifecycle_module
from reliquary import machine as machine_module
from reliquary import drives as media_module
from reliquary import platform_dos as platform_dos_module
from reliquary import workflows as workflows_module


class HomeTests(unittest.TestCase):
    def setUp(self):
        self.previous_home = reliquary.home()
        self.tempdir = tempfile.TemporaryDirectory()
        reliquary.set_home(self.tempdir.name)

    def tearDown(self):
        reliquary.set_home(self.previous_home)
        self.tempdir.cleanup()

    def test_paths_are_contained_by_configured_home(self):
        self.assertEqual(reliquary.drives_dir(),
                         os.path.join(self.tempdir.name, "drives"))

    def test_planned_layout_paths_are_contained_by_configured_home(self):
        root = self.tempdir.name
        cache = os.path.join(root, "cache")
        self.assertEqual(reliquary.blueprints_dir(),
                         os.path.join(root, "blueprints"))
        self.assertEqual(reliquary.media_dir(),
                         os.path.join(root, "media"))
        self.assertEqual(reliquary.scripts_dir(),
                         os.path.join(root, "scripts"))
        self.assertEqual(reliquary.cache_dir(), cache)
        self.assertEqual(reliquary.downloads_cache_dir(),
                         os.path.join(cache, "downloads"))
        self.assertEqual(reliquary.media_cache_dir(),
                         os.path.join(cache, "media"))
        self.assertEqual(reliquary.machines_cache_dir(),
                         os.path.join(cache, "machines"))

    def test_planned_layout_paths_honor_explicit_home(self):
        other = tempfile.TemporaryDirectory()
        self.addCleanup(other.cleanup)
        root = other.name
        cache = os.path.join(root, "cache")
        self.assertEqual(reliquary.blueprints_dir(context=root),
                         os.path.join(root, "blueprints"))
        self.assertEqual(reliquary.media_dir(context=root),
                         os.path.join(root, "media"))
        self.assertEqual(reliquary.scripts_dir(context=root),
                         os.path.join(root, "scripts"))
        self.assertEqual(reliquary.cache_dir(context=root), cache)
        self.assertEqual(reliquary.downloads_cache_dir(context=root),
                         os.path.join(cache, "downloads"))
        self.assertEqual(reliquary.media_cache_dir(context=root),
                         os.path.join(cache, "media"))
        self.assertEqual(reliquary.machines_cache_dir(context=root),
                         os.path.join(cache, "machines"))

    def test_documents_dir_is_public_and_absolute_or_none(self):
        """documents_dir() reports the platform Documents folder."""
        documents = reliquary.documents_dir()
        if documents is not None:
            self.assertTrue(os.path.isabs(documents))

    def test_staged_drive_letters_are_validated(self):
        for letter in ("A", "B", "CC", "1", ""):
            with self.assertRaisesRegex(ValueError, "staged_drive",
                                        msg=letter):
                media_module.check_staged_drive(letter)

    def test_vm_state_round_trip(self):
        lifecycle_module.write_vm_state(
            54321, "reliquary-test",
            "12345678-1234-1234-1234-123456789012", 1234)

        self.assertEqual(lifecycle_module.read_vm_state(), {
            "port": 54321,
            "name": "reliquary-test",
            "uuid": "12345678-1234-1234-1234-123456789012",
            "pid": 1234,
        })
        self.assertFalse(os.path.exists(
            lifecycle_module.state_path() + ".part"))

    def test_invalid_vm_state_is_rejected(self):
        os.makedirs(self.tempdir.name, exist_ok=True)
        with open(lifecycle_module.state_path(), "w",
                  encoding="utf-8") as state:
            json.dump({"port": True, "name": "reliquary-test"}, state)

        with self.assertRaisesRegex(RuntimeError, "invalid reliquary VM state"):
            lifecycle_module.read_vm_state()

    def test_vm_state_without_uuid_is_rejected(self):
        # a name alone cannot identify a VM instance; state files
        # predating the per-start uuid are invalid, not grandfathered
        os.makedirs(self.tempdir.name, exist_ok=True)
        with open(lifecycle_module.state_path(), "w",
                  encoding="utf-8") as state:
            json.dump({"port": 54321, "name": "reliquary-test",
                       "pid": 1234}, state)

        with self.assertRaisesRegex(RuntimeError, "invalid reliquary VM state"):
            lifecycle_module.read_vm_state()

    def test_remove_vm_state_requires_matching_identity(self):
        lifecycle_module.write_vm_state(
            54321, "reliquary-test",
            "12345678-1234-1234-1234-123456789012", 1234)

        lifecycle_module.remove_vm_state(54321, "another-vm")
        self.assertIsNotNone(lifecycle_module.read_vm_state())

        lifecycle_module.remove_vm_state(54321, "reliquary-test")
        self.assertIsNone(lifecycle_module.read_vm_state())

    def test_resolve_vm_rejects_unrecorded_explicit_port(self):
        with self.assertRaisesRegex(RuntimeError, "not the recorded"):
            lifecycle_module.resolve_vm(54321)

    def _write_drive_file(self, name, data=b"dos"):
        os.makedirs(reliquary.drives_dir(), exist_ok=True)
        path = os.path.join(reliquary.drives_dir(), name)
        with open(path, "wb") as f:
            f.write(data)
        return path

    def _make_drive_dir(self, name):
        path = os.path.join(reliquary.drives_dir(), name)
        os.makedirs(path)
        return path

    def test_scan_recognizes_media_by_stem_and_slot(self):
        floppy = self._write_drive_file("floppy.qcow2")
        hdd = self._make_drive_dir("hdd_1")
        cdrom = self._write_drive_file("cdrom.iso")
        # leftover temp files and unrelated names never count
        self._write_drive_file("floppy.img.part")
        self._write_drive_file("other.img")

        media = media_module.scan_drives(reliquary.drives_dir())

        self.assertEqual(media["floppy"], {
            0: media_module.Drive(floppy, False),
        })
        self.assertEqual(media["hdd"], {
            1: media_module.Drive(hdd, True),
        })
        self.assertEqual(media["cdrom"], {
            0: media_module.Drive(cdrom, False),
        })

    def test_unindexed_and_slot_0_names_clash(self):
        self._write_drive_file("hdd.qcow2")
        self._write_drive_file("hdd_0.vmdk")

        with self.assertRaisesRegex(RuntimeError, "slot clash"):
            media_module.scan_drives(reliquary.drives_dir())

    def test_an_image_and_a_directory_clash_on_the_same_slot(self):
        self._write_drive_file("floppy.img")
        self._make_drive_dir("floppy_0")

        with self.assertRaisesRegex(RuntimeError, "slot clash"):
            media_module.scan_drives(reliquary.drives_dir())

    def test_cdrom_directories_are_rejected(self):
        self._make_drive_dir("cdrom")

        with self.assertRaisesRegex(RuntimeError, "ISO9660"):
            media_module.scan_drives(reliquary.drives_dir())

    def test_out_of_range_slots_are_rejected(self):
        self._write_drive_file("floppy_2.img")

        with self.assertRaisesRegex(RuntimeError, "slots run"):
            media_module.scan_drives(reliquary.drives_dir())

    def test_enabled_false_disables_autodiscovered_drive(self):
        self._write_drive_file("hdd_0.qcow2")
        self._make_drive_dir("hdd_1")

        media = media_module.resolve_media(
            reliquary.drives_dir(),
            {"hdd_1": {"enabled": False}})

        self.assertEqual(media["hdd"], {
            0: media_module.Drive(
                os.path.join(reliquary.drives_dir(), "hdd_0.qcow2"), False),
        })
        self.assertNotIn(1, media["hdd"])

    def test_enabled_true_allows_configured_drive_override(self):
        self._write_drive_file("hdd_0.qcow2")
        override = os.path.join(self.tempdir.name, "override.qcow2")
        with open(override, "wb") as f:
            f.write(b"override")

        media = media_module.resolve_media(
            reliquary.drives_dir(),
            {"hdd_0": {"source": override, "enabled": True}})

        self.assertEqual(media["hdd"], {
            0: media_module.Drive(override, False),
        })

    def test_options_without_source_uses_autodiscovered_drive(self):
        self._write_drive_file("hdd_0.qcow2")

        media = media_module.resolve_media(
            reliquary.drives_dir(),
            {"hdd_0": {"options": {"cache": "writeback"}}})

        self.assertEqual(media["hdd"], {
            0: media_module.Drive(
                os.path.join(reliquary.drives_dir(), "hdd_0.qcow2"),
                False,
                (("cache", "writeback"),)),
        })


class InputAndScreenTests(unittest.TestCase):
    def test_character_key_mappings(self):
        self.assertEqual(machine_module.char_keys("a"), ["a"])
        self.assertEqual(machine_module.char_keys("A"), ["shift", "a"])
        self.assertEqual(machine_module.char_keys(":"),
                         ["shift", "semicolon"])
        self.assertEqual(machine_module.char_keys(" "), ["spc"])

    def test_unmapped_character_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "no key mapping"):
            machine_module.char_keys("\N{SNOWMAN}")

    def test_send_text_builds_qcode_combinations(self):
        console = machine_module._DisplayConsole(54321)
        with mock.patch.object(console, "send_keys") as send_keys:
            console.send_text("A:")

        send_keys.assert_called_once_with(
            [["shift", "a"], ["shift", "semicolon"], ["ret"]])

    def test_screen_text_extracts_characters_and_ignores_attributes(self):
        cells = []
        for char in "A:\\>" + " " * (80 * 25 - 4):
            cells.extend((ord(char), 0x07))
        lines = []
        for offset in range(0, len(cells), 16):
            payload = " ".join(f"0x{value:02x}" for value in
                               cells[offset:offset + 16])
            lines.append(f"00000000000b{offset:04x}: {payload}")
        qmp = mock.Mock()
        qmp.hmp.return_value = "\n".join(lines)

        with mock.patch.object(machine_module, "qmp_session") as connection:
            connection.return_value.__enter__.return_value = qmp
            rows = reliquary.screen_text()

        self.assertEqual(len(rows), 25)
        self.assertEqual(rows[0], "A:\\>")
        self.assertTrue(all(row == "" for row in rows[1:]))
        qmp.hmp.assert_called_once_with("xp /4000bx 0xb8000")

    def test_vga_screen_exposes_attribute_bytes(self):
        cells = []
        for index, char in enumerate("A:\\>" + " " * (80 * 25 - 4)):
            cells.extend((ord(char), 0x70 if index < 4 else 0x07))
        lines = []
        for offset in range(0, len(cells), 16):
            payload = " ".join(f"0x{value:02x}" for value in
                               cells[offset:offset + 16])
            lines.append(f"00000000000b{offset:04x}: {payload}")
        qmp = mock.Mock()
        qmp.hmp.return_value = "\n".join(lines)

        rows, attributes = machine_module.vga_screen(qmp)

        self.assertEqual(rows[0], "A:\\>")
        self.assertEqual(attributes[0][:5], [0x70] * 4 + [0x07])
        self.assertEqual(len(attributes), 25)
        self.assertTrue(all(len(row) == 80 for row in attributes))

    def test_wait_text_returns_the_matching_screen(self):
        with mock.patch.object(machine_module, "qmp_session") as connection, \
                mock.patch.object(
                    machine_module, "vga_text",
                    return_value=["Welcome to FreeDOS 1.4 (LiveCD)"]), \
                mock.patch.object(machine_module.time, "sleep"):
            connection.return_value.__enter__.return_value = mock.Mock()
            screen = machine_module.Machine().wait_text(
                r"Welcome to FreeDOS")

        self.assertIn("FreeDOS 1.4", screen)

    def test_wait_text_times_out_without_a_match(self):
        with mock.patch.object(machine_module, "qmp_session") as connection, \
                mock.patch.object(
                    machine_module, "vga_text", return_value=[""]), \
                mock.patch.object(machine_module.time, "sleep"):
            connection.return_value.__enter__.return_value = mock.Mock()
            with self.assertRaisesRegex(TimeoutError, "FreeDOS"):
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
        console = machine_module._DisplayConsole(None)
        console.screen = menu.screen
        console.send_keys = lambda combos, delay=0.06: [
            menu.press(combo[0]) for combo in combos]
        clock = _MenuClock()
        with mock.patch.object(machine_module.time, "monotonic",
                               clock.monotonic), \
                mock.patch.object(machine_module.time, "sleep",
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

        with self.assertRaisesRegex(ValueError, "not on screen"):
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

        self.assertIsNone(machine_module._cursor_row(before, after))

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

        with self.assertRaisesRegex(ValueError, "excluded rows"):
            self._select(menu, "Plain DOS system",
                         exclude=["sources"])

        self.assertIsNone(menu.selected)

    def test_ambiguous_item_is_rejected(self):
        menu = _FakeMenu(["Install to harddisk",
                          "Install using Floppy Edition"])

        with self.assertRaisesRegex(ValueError, "multiple rows"):
            self._select(menu, "Install")

        self.assertIsNone(menu.selected)

    def test_unresponsive_menu_raises(self):
        menu = _FakeMenu(["First item", "Second item"], stuck=True)

        with self.assertRaisesRegex(RuntimeError,
                                    "no menu highlight responded"):
            self._select(menu, "Second item")

        self.assertIsNone(menu.selected)

    def test_unselectable_row_raises_when_the_cursor_cannot_reach_it(self):
        menu = _FakeMenu(["First item", "Second item"])

        with self.assertRaisesRegex(RuntimeError, "stopped responding"):
            self._select(menu, "Welcome menu")

        self.assertIsNone(menu.selected)


class BootToDosTests(unittest.TestCase):
    def test_reaches_an_existing_prompt_without_typing(self):
        console = mock.Mock()
        console.screen_text.return_value = ["A:\\>"] + [""] * 24
        with mock.patch.object(machine_module, "qmp_session") as connection, \
                mock.patch.object(
                    agentless_module, "_DisplayConsole",
                    return_value=console), \
                mock.patch.object(agentless_module.time, "sleep"):
            connection.return_value.__enter__.return_value = mock.Mock()
            agentless_module.AgentlessGuestExec(
                machine_module.Machine()).wait_ready()

        console.send_text.assert_not_called()

    def test_times_out_without_a_prompt(self):
        with mock.patch.object(machine_module, "qmp_session") as connection, \
                mock.patch.object(agentless_module.time, "sleep"):
            connection.return_value.__enter__.return_value = mock.Mock()
            with self.assertRaisesRegex(TimeoutError, "DOS prompt"):
                agentless_module.AgentlessGuestExec(
                    machine_module.Machine()).wait_ready(timeout=0)


class InteractionAdapterTests(unittest.TestCase):
    def test_machine_exposes_an_identity_verified_qmp_session(self):
        qmp = mock.Mock()
        machine = machine_module.Machine(54321, "run-home")
        with mock.patch.object(machine_module, "qmp_session") as connection:
            connection.return_value.__enter__.return_value = qmp

            with machine.qmp() as session:
                self.assertIs(session, qmp)

        connection.assert_called_once_with(54321, "run-home")

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


class RunCommandTests(unittest.TestCase):
    def test_agentless_adapter_executes_through_display_console(self):
        qmp = mock.Mock()
        console = mock.Mock()
        console.screen_text.return_value = ["C:\\>"] + [""] * 24
        with mock.patch.object(machine_module, "qmp_session") as connection, \
                mock.patch.object(
                    agentless_module, "_DisplayConsole",
                    return_value=console), \
                mock.patch.object(agentless_module.time, "sleep"):
            connection.return_value.__enter__.return_value = qmp
            agentless_module.AgentlessGuestExec(
                machine_module.Machine()).execute("dir")

        console.send_text.assert_called_once_with("dir")


class GuestProgramTests(unittest.TestCase):
    def setUp(self):
        self.previous_home = reliquary.home()
        self.tempdir = tempfile.TemporaryDirectory()
        reliquary.set_home(self.tempdir.name)
        self.exe = os.path.join(self.tempdir.name, "SUITE.EXE")
        with open(self.exe, "wb") as executable:
            executable.write(b"test executable")

    def tearDown(self):
        reliquary.set_home(self.previous_home)
        self.tempdir.cleanup()

    def test_dos_program_requires_dos_83_executable_name(self):
        path = os.path.join(self.tempdir.name, "TOO-LONG-NAME.EXE")

        with self.assertRaisesRegex(ValueError, "DOS 8.3"):
            reliquary.run_guest_program(path)

    def test_unimplemented_platform_does_not_apply_dos_name_policy(self):
        path = os.path.join(self.tempdir.name, "TOO-LONG-NAME.EXE")

        with self.assertRaisesRegex(NotImplementedError, "win9x"):
            reliquary.run_guest_program(
                path, machine_config=reliquary.MachineConfig(
                    platform="win9x"))

    def test_guest_program_stages_runs_stops_and_returns_log(self):
        guest = mock.Mock()
        stage = os.path.join(reliquary.drives_dir(), "hdd")
        log_path = os.path.join(stage, "SUITE.log")

        def run_guest_command(command, *args):
            if command != "c:":
                with open(log_path, "w", encoding="utf-8") as log:
                    log.write("guest output")

        guest.execute.side_effect = run_guest_command

        with mock.patch.object(workflows_module, "_start_configured_machine",
                               return_value=54321) as start, \
                mock.patch.object(
                    workflows_module, "AgentlessGuestExec",
                    return_value=guest) as adapter, \
                mock.patch.object(workflows_module, "stop") as stop, \
                mock.patch.object(workflows_module.time, "sleep"):
            config = reliquary.MachineConfig(timeout=45, qemu="qemu")
            log = reliquary.run_guest_program(
                self.exe, args="-v", machine_config=config, port=54321)

        self.assertTrue(os.path.isdir(stage))
        start.assert_called_once_with(
            mock.ANY, display=False, port=54321, home=None)
        config = start.call_args.args[0]
        self.assertIsInstance(config, reliquary.MachineConfig)
        self.assertEqual(config.qemu, "qemu")
        self.assertEqual(config.timeout, 45)
        adapter.assert_called_once_with(machine_module.Machine(54321, None))
        guest.wait_ready.assert_called_once_with()
        self.assertEqual(guest.execute.call_args_list, [
            mock.call("c:", 15),
            mock.call("SUITE -v > SUITE.log", 45),
        ])
        stop.assert_called_once_with(54321, None)
        self.assertEqual(log, "guest output")

    def test_guest_program_switches_to_the_declared_staged_drive(self):
        guest = mock.Mock()
        log_path = os.path.join(reliquary.drives_dir(), "hdd",
                                "SUITE.log")

        def run_guest_command(command, *args):
            if command != "d:":
                with open(log_path, "w", encoding="utf-8") as log:
                    log.write("guest output")

        guest.execute.side_effect = run_guest_command

        with mock.patch.object(workflows_module, "_start_configured_machine",
                               return_value=54321), \
                mock.patch.object(
                    workflows_module, "AgentlessGuestExec",
                    return_value=guest), \
                mock.patch.object(workflows_module, "stop"), \
                mock.patch.object(workflows_module.time, "sleep"):
            config = reliquary.MachineConfig(staged_drive="d")
            log = reliquary.run_guest_program(
                self.exe, machine_config=config)

        self.assertEqual(guest.execute.call_args_list[0].args[0], "d:")
        self.assertEqual(log, "guest output")

    def _stage_hdd_boot_image(self):
        os.makedirs(reliquary.drives_dir(), exist_ok=True)
        path = os.path.join(reliquary.drives_dir(), "hdd.qcow2")
        with open(path, "wb") as image:
            image.write(b"hdd dos")

    def test_staged_drive_defaults_to_d_behind_a_hdd_boot_image(self):
        # the hard-disk image claims slot 0, so staging goes to the
        # next free slot (drives/hdd_1) and defaults one letter on
        self._stage_hdd_boot_image()
        guest = mock.Mock()
        log_path = os.path.join(reliquary.drives_dir(), "hdd_1",
                                "SUITE.log")

        def run_guest_command(command, *args):
            if command != "d:":
                with open(log_path, "w", encoding="utf-8") as log:
                    log.write("guest output")

        guest.execute.side_effect = run_guest_command

        with mock.patch.object(workflows_module, "_start_configured_machine",
                               return_value=54321), \
                mock.patch.object(
                    workflows_module, "AgentlessGuestExec",
                    return_value=guest), \
                mock.patch.object(workflows_module, "stop"), \
                mock.patch.object(workflows_module.time, "sleep"):
            log = reliquary.run_guest_program(self.exe)

        self.assertTrue(
            os.path.isdir(os.path.join(reliquary.drives_dir(),
                                       "hdd_1")))
        self.assertEqual(guest.execute.call_args_list[0].args[0], "d:")
        self.assertEqual(log, "guest output")

    def test_configured_hdd_source_claims_a_slot_before_staging(self):
        source = os.path.join(self.tempdir.name, "boot.qcow2")
        with open(source, "wb") as image:
            image.write(b"hdd dos")
        guest = mock.Mock()
        log_path = os.path.join(reliquary.drives_dir(), "hdd_1",
                                "SUITE.log")

        def run_guest_command(command, *args):
            if command != "d:":
                with open(log_path, "w", encoding="utf-8") as log:
                    log.write("guest output")

        guest.execute.side_effect = run_guest_command
        specs = {"hdd": source}
        with mock.patch.object(workflows_module, "_start_configured_machine",
                               return_value=54321) as start, \
                mock.patch.object(
                    workflows_module, "AgentlessGuestExec",
                    return_value=guest), \
                mock.patch.object(workflows_module, "stop"), \
                mock.patch.object(workflows_module.time, "sleep"):
            config = reliquary.MachineConfig(drives=specs)
            log = reliquary.run_guest_program(
                self.exe, machine_config=config)

        self.assertEqual(guest.execute.call_args_list[0].args[0], "d:")
        config = start.call_args.args[0]
        self.assertEqual(config.drives["hdd_0"]["source"],
                         os.path.abspath(source))
        self.assertEqual(log, "guest output")

    def test_staged_drive_c_is_rejected_behind_a_hdd_boot_image(self):
        self._stage_hdd_boot_image()

        with mock.patch.object(workflows_module, "_start_configured_machine") \
                as start:
            with self.assertRaisesRegex(ValueError, "claim C:"):
                config = reliquary.MachineConfig(staged_drive="C")
                reliquary.run_guest_program(
                    self.exe, machine_config=config)

        start.assert_not_called()

    def test_staging_reuses_a_declared_staged_directory(self):
        staged = os.path.join(reliquary.drives_dir(), "hdd_2")
        os.makedirs(staged)
        self._stage_hdd_boot_image()
        guest = mock.Mock()
        log_path = os.path.join(staged, "SUITE.log")

        def run_guest_command(command, *args):
            if command != "d:":
                with open(log_path, "w", encoding="utf-8") as log:
                    log.write("guest output")

        guest.execute.side_effect = run_guest_command

        with mock.patch.object(workflows_module, "_start_configured_machine",
                               return_value=54321), \
                mock.patch.object(
                    workflows_module, "AgentlessGuestExec",
                    return_value=guest), \
                mock.patch.object(workflows_module, "stop"), \
                mock.patch.object(workflows_module.time, "sleep"):
            log = reliquary.run_guest_program(self.exe)

        # only the slot-0 image precedes the staged slot 2 (slot 1
        # is undeclared and claims no letter), so the default is D:
        self.assertEqual(guest.execute.call_args_list[0].args[0], "d:")
        self.assertEqual(log, "guest output")

    def test_guest_program_stops_when_guest_command_fails(self):
        guest = mock.Mock()
        guest.execute.side_effect = RuntimeError("guest failed")
        with mock.patch.object(workflows_module, "_start_configured_machine",
                               return_value=54321), \
                mock.patch.object(
                    workflows_module, "AgentlessGuestExec",
                    return_value=guest), \
                mock.patch.object(workflows_module, "stop") as stop:
            with self.assertRaisesRegex(RuntimeError, "guest failed"):
                reliquary.run_guest_program(self.exe)

        stop.assert_called_once_with(54321, None)


class ScreenshotTests(unittest.TestCase):
    def setUp(self):
        self.previous_home = reliquary.home()
        self.tempdir = tempfile.TemporaryDirectory()
        reliquary.set_home(self.tempdir.name)

    def tearDown(self):
        reliquary.set_home(self.previous_home)
        self.tempdir.cleanup()

    def test_screenshot_rejects_names_that_are_paths(self):
        invalid_names = ("", ".", "..", "../outside", "..\\outside",
                         "/outside", "C:\\outside")

        with mock.patch.object(machine_module, "qmp_session") as connection:
            for name in invalid_names:
                with self.subTest(name=name):
                    with self.assertRaisesRegex(ValueError, "not a path"):
                        reliquary.screenshot(name)

        connection.assert_not_called()

    def test_screenshot_requests_png_under_home(self):
        qmp = mock.Mock()
        expected = os.path.join(
            self.tempdir.name, "screenshots", "release-smoke.png")

        with mock.patch.object(machine_module, "qmp_session") as connection:
            connection.return_value.__enter__.return_value = qmp
            reliquary.screenshot("release-smoke")

        qmp.cmd.assert_called_once_with(
            "screendump", filename=expected.replace("\\", "/"),
            format="png")

    def test_screenshot_converts_legacy_ppm_under_home(self):
        class UnsupportedPngError(Exception):
            pass

        qmp = mock.Mock()
        screenshots = os.path.join(self.tempdir.name, "screenshots")
        ppm = os.path.join(screenshots, "legacy.ppm")
        png = os.path.join(screenshots, "legacy.png")

        def screendump(command, **arguments):
            self.assertEqual(command, "screendump")
            if arguments.get("format") == "png":
                raise UnsupportedPngError()
            with open(arguments["filename"], "wb") as image:
                image.write(b"P6\n1 1\n255\n\x01\x02\x03")

        qmp.cmd.side_effect = screendump
        with mock.patch.object(machine_module, "qmp_session") as connection, \
                mock.patch.object(machine_module, "ExecuteError",
                                  UnsupportedPngError), \
                mock.patch.object(machine_module.time, "sleep"):
            connection.return_value.__enter__.return_value = qmp
            reliquary.screenshot("legacy")

        self.assertFalse(os.path.exists(ppm))
        with open(png, "rb") as image:
            self.assertEqual(image.read(8), b"\x89PNG\r\n\x1a\n")


if __name__ == "__main__":
    unittest.main()
