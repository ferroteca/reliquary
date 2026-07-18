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

import relict


class HomeTests(unittest.TestCase):
    def setUp(self):
        self.previous_home = relict._home
        self.tempdir = tempfile.TemporaryDirectory()
        relict.set_home(self.tempdir.name)

    def tearDown(self):
        relict._home = self.previous_home
        self.tempdir.cleanup()

    def test_paths_are_contained_by_configured_home(self):
        self.assertEqual(relict.drives_dir(),
                         os.path.join(self.tempdir.name, "drives"))

    def test_staged_drive_letters_are_validated(self):
        for letter in ("A", "B", "CC", "1", ""):
            with self.assertRaisesRegex(ValueError, "staged_drive",
                                        msg=letter):
                relict._check_staged_drive(letter)

    def test_vm_state_round_trip(self):
        relict._write_vm_state(54321, "relict-test", 1234)

        self.assertEqual(relict._read_vm_state(), {
            "port": 54321,
            "name": "relict-test",
            "pid": 1234,
        })
        self.assertFalse(os.path.exists(relict._state_path() + ".part"))

    def test_invalid_vm_state_is_rejected(self):
        os.makedirs(self.tempdir.name, exist_ok=True)
        with open(relict._state_path(), "w", encoding="utf-8") as state:
            json.dump({"port": True, "name": "relict-test"}, state)

        with self.assertRaisesRegex(RuntimeError, "invalid relict VM state"):
            relict._read_vm_state()

    def test_remove_vm_state_requires_matching_identity(self):
        relict._write_vm_state(54321, "relict-test", 1234)

        relict._remove_vm_state(54321, "another-vm")
        self.assertIsNotNone(relict._read_vm_state())

        relict._remove_vm_state(54321, "relict-test")
        self.assertIsNone(relict._read_vm_state())

    def test_resolve_vm_rejects_unrecorded_explicit_port(self):
        with self.assertRaisesRegex(RuntimeError, "not the recorded"):
            relict._resolve_vm(54321)

    def _write_drive_file(self, name, data=b"dos"):
        os.makedirs(relict.drives_dir(), exist_ok=True)
        path = os.path.join(relict.drives_dir(), name)
        with open(path, "wb") as f:
            f.write(data)
        return path

    def _make_drive_dir(self, name):
        path = os.path.join(relict.drives_dir(), name)
        os.makedirs(path)
        return path

    def test_download_keeps_existing_boot_floppy(self):
        floppy = self._write_drive_file("floppy.img", b"custom dos")

        with mock.patch.object(relict.urllib.request,
                               "urlretrieve") as retrieve:
            relict.download()

        retrieve.assert_not_called()
        with open(floppy, "rb") as image:
            self.assertEqual(image.read(), b"custom dos")

    def test_download_keeps_existing_bootable_hdd_image(self):
        self._write_drive_file("hdd.qcow2", b"custom hdd dos")

        with mock.patch.object(relict.urllib.request,
                               "urlretrieve") as retrieve:
            relict.download()

        retrieve.assert_not_called()

    def test_download_refuses_a_staged_directory_on_floppy_slot_0(self):
        self._make_drive_dir("floppy")

        with self.assertRaisesRegex(RuntimeError, "floppy slot 0"):
            relict.download()

    def test_scan_recognizes_media_by_stem_and_slot(self):
        floppy = self._write_drive_file("floppy.qcow2")
        hdd = self._make_drive_dir("hdd_1")
        cdrom = self._write_drive_file("cdrom.iso")
        # download leftovers and unrelated names never count
        self._write_drive_file("floppy.img.part")
        self._write_drive_file("FD14-FloppyEdition.zip")
        self._write_drive_file("other.img")

        media = relict._scan_drives(relict.drives_dir())

        self.assertEqual(media["floppy"], {0: (floppy, False)})
        self.assertEqual(media["hdd"], {1: (hdd, True)})
        self.assertEqual(media["cdrom"], {0: (cdrom, False)})

    def test_unindexed_and_slot_0_names_clash(self):
        self._write_drive_file("hdd.qcow2")
        self._write_drive_file("hdd_0.vmdk")

        with self.assertRaisesRegex(RuntimeError, "slot clash"):
            relict._scan_drives(relict.drives_dir())

    def test_an_image_and_a_directory_clash_on_the_same_slot(self):
        self._write_drive_file("floppy.img")
        self._make_drive_dir("floppy_0")

        with self.assertRaisesRegex(RuntimeError, "slot clash"):
            relict._scan_drives(relict.drives_dir())

    def test_cdrom_directories_are_rejected(self):
        self._make_drive_dir("cdrom")

        with self.assertRaisesRegex(RuntimeError, "ISO9660"):
            relict._scan_drives(relict.drives_dir())

    def test_out_of_range_slots_are_rejected(self):
        self._write_drive_file("floppy_2.img")

        with self.assertRaisesRegex(RuntimeError, "slots run"):
            relict._scan_drives(relict.drives_dir())


class InputAndScreenTests(unittest.TestCase):
    def test_character_key_mappings(self):
        self.assertEqual(relict._char_keys("a"), ["a"])
        self.assertEqual(relict._char_keys("A"), ["shift", "a"])
        self.assertEqual(relict._char_keys(":"), ["shift", "semicolon"])
        self.assertEqual(relict._char_keys(" "), ["spc"])

    def test_unmapped_character_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "no key mapping"):
            relict._char_keys("\N{SNOWMAN}")

    def test_send_text_builds_qcode_combinations(self):
        with mock.patch.object(relict, "send_keys") as send_keys:
            relict.send_text("A:", port=54321)

        send_keys.assert_called_once_with(
            [["shift", "a"], ["shift", "semicolon"], ["ret"]],
            54321)

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

        with mock.patch.object(relict, "_qmp") as connection:
            connection.return_value.__enter__.return_value = qmp
            rows = relict.screen_text()

        self.assertEqual(len(rows), 25)
        self.assertEqual(rows[0], "A:\\>")
        self.assertTrue(all(row == "" for row in rows[1:]))
        qmp.hmp.assert_called_once_with("xp /4000bx 0xb8000")


class BootToDosTests(unittest.TestCase):
    def test_reaches_an_existing_prompt_without_typing(self):
        with mock.patch.object(relict, "_qmp") as connection, \
                mock.patch.object(
                    relict, "screen_text",
                    return_value=["A:\\>"] + [""] * 24), \
                mock.patch.object(relict, "send_keys") as send_keys, \
                mock.patch.object(relict.time, "sleep"):
            connection.return_value.__enter__.return_value = mock.Mock()
            relict.boot_to_dos()

        send_keys.assert_not_called()

    def test_declines_the_freedos_installer(self):
        qmp = mock.Mock()
        screens = [
            ["Welcome to the FreeDOS 1.4 installation program.",
             "Do you want to proceed [Y,N]?"],
            ["Do you want to proceed [Y,N]?N",
             "The installation of FreeDOS 1.4 has been aborted.",
             "A:\\>"],
        ]
        with mock.patch.object(relict, "_qmp") as connection, \
                mock.patch.object(relict, "screen_text",
                                  side_effect=screens), \
                mock.patch.object(relict, "send_text") as send_text, \
                mock.patch.object(relict.time, "sleep"):
            connection.return_value.__enter__.return_value = qmp
            relict.boot_to_dos()

        send_text.assert_called_once_with("n", qmp)

    def test_times_out_without_a_prompt(self):
        with mock.patch.object(relict, "_qmp") as connection, \
                mock.patch.object(relict.time, "sleep"):
            connection.return_value.__enter__.return_value = mock.Mock()
            with self.assertRaisesRegex(TimeoutError, "DOS prompt"):
                relict.boot_to_dos(timeout=0)


class GuestProgramTests(unittest.TestCase):
    def setUp(self):
        self.previous_home = relict._home
        self.tempdir = tempfile.TemporaryDirectory()
        relict.set_home(self.tempdir.name)
        self.exe = os.path.join(self.tempdir.name, "SUITE.EXE")
        with open(self.exe, "wb") as executable:
            executable.write(b"test executable")

    def tearDown(self):
        relict._home = self.previous_home
        self.tempdir.cleanup()

    def test_program_requires_dos_83_executable_name(self):
        path = os.path.join(self.tempdir.name, "TOO-LONG-NAME.EXE")

        with self.assertRaisesRegex(ValueError, "DOS 8.3"):
            relict.run_guest_program(path)

    def test_guest_program_stages_runs_stops_and_returns_log(self):
        qmp = mock.Mock()
        stage = os.path.join(relict.drives_dir(), "hdd")
        log_path = os.path.join(stage, "SUITE.log")

        def run_guest_command(command, *args):
            if command != "c:":
                with open(log_path, "w", encoding="utf-8") as log:
                    log.write("guest output")

        with mock.patch.object(relict, "start", return_value=54321) \
                as start, \
                mock.patch.object(relict, "_qmp") as connection, \
                mock.patch.object(relict, "boot_to_dos") as boot, \
                mock.patch.object(
                    relict, "run_command",
                    side_effect=run_guest_command) as run, \
                mock.patch.object(relict, "stop") as stop, \
                mock.patch.object(relict.time, "sleep"):
            connection.return_value.__enter__.return_value = qmp
            log = relict.run_guest_program(
                self.exe, args="-v", timeout=45, qemu="qemu", port=54321)

        self.assertTrue(os.path.isdir(stage))
        start.assert_called_once_with(
            qemu="qemu", port=54321, qemu_args=(), home=None)
        boot.assert_called_once_with(port=qmp)
        self.assertEqual(run.call_args_list, [
            mock.call("c:", 15, qmp),
            mock.call("SUITE -v > SUITE.log", 45, qmp),
        ])
        stop.assert_called_once_with(54321, None)
        self.assertEqual(log, "guest output")

    def test_guest_program_switches_to_the_declared_staged_drive(self):
        log_path = os.path.join(relict.drives_dir(), "hdd",
                                "SUITE.log")

        def run_guest_command(command, *args):
            if command != "d:":
                with open(log_path, "w", encoding="utf-8") as log:
                    log.write("guest output")

        with mock.patch.object(relict, "start", return_value=54321) \
                as start, \
                mock.patch.object(relict, "_qmp") as connection, \
                mock.patch.object(relict, "boot_to_dos"), \
                mock.patch.object(
                    relict, "run_command",
                    side_effect=run_guest_command) as run, \
                mock.patch.object(relict, "stop"), \
                mock.patch.object(relict.time, "sleep"):
            connection.return_value.__enter__.return_value = mock.Mock()
            log = relict.run_guest_program(self.exe, staged_drive="d")

        self.assertEqual(run.call_args_list[0].args[0], "d:")
        self.assertEqual(log, "guest output")

    def _stage_hdd_boot_image(self):
        os.makedirs(relict.drives_dir(), exist_ok=True)
        path = os.path.join(relict.drives_dir(), "hdd.qcow2")
        with open(path, "wb") as image:
            image.write(b"hdd dos")

    def test_staged_drive_defaults_to_d_behind_a_hdd_boot_image(self):
        # the hard-disk image claims slot 0, so staging goes to the
        # next free slot (drives/hdd_1) and defaults one letter on
        self._stage_hdd_boot_image()
        log_path = os.path.join(relict.drives_dir(), "hdd_1",
                                "SUITE.log")

        def run_guest_command(command, *args):
            if command != "d:":
                with open(log_path, "w", encoding="utf-8") as log:
                    log.write("guest output")

        with mock.patch.object(relict, "start", return_value=54321) \
                as start, \
                mock.patch.object(relict, "_qmp") as connection, \
                mock.patch.object(relict, "boot_to_dos"), \
                mock.patch.object(
                    relict, "run_command",
                    side_effect=run_guest_command) as run, \
                mock.patch.object(relict, "stop"), \
                mock.patch.object(relict.time, "sleep"):
            connection.return_value.__enter__.return_value = mock.Mock()
            log = relict.run_guest_program(self.exe)

        self.assertTrue(
            os.path.isdir(os.path.join(relict.drives_dir(),
                                       "hdd_1")))
        self.assertEqual(run.call_args_list[0].args[0], "d:")
        self.assertEqual(log, "guest output")

    def test_staged_drive_c_is_rejected_behind_a_hdd_boot_image(self):
        self._stage_hdd_boot_image()

        with mock.patch.object(relict, "start") as start:
            with self.assertRaisesRegex(ValueError, "claim C:"):
                relict.run_guest_program(self.exe, staged_drive="C")

        start.assert_not_called()

    def test_staging_reuses_a_declared_staged_directory(self):
        staged = os.path.join(relict.drives_dir(), "hdd_2")
        os.makedirs(staged)
        self._stage_hdd_boot_image()
        log_path = os.path.join(staged, "SUITE.log")

        def run_guest_command(command, *args):
            if command != "d:":
                with open(log_path, "w", encoding="utf-8") as log:
                    log.write("guest output")

        with mock.patch.object(relict, "start", return_value=54321), \
                mock.patch.object(relict, "_qmp") as connection, \
                mock.patch.object(relict, "boot_to_dos"), \
                mock.patch.object(
                    relict, "run_command",
                    side_effect=run_guest_command) as run, \
                mock.patch.object(relict, "stop"), \
                mock.patch.object(relict.time, "sleep"):
            connection.return_value.__enter__.return_value = mock.Mock()
            log = relict.run_guest_program(self.exe)

        # only the slot-0 image precedes the staged slot 2 (slot 1
        # is undeclared and claims no letter), so the default is D:
        self.assertEqual(run.call_args_list[0].args[0], "d:")
        self.assertEqual(log, "guest output")

    def test_guest_program_stops_when_guest_command_fails(self):
        with mock.patch.object(relict, "start", return_value=54321), \
                mock.patch.object(relict, "_qmp") as connection, \
                mock.patch.object(relict, "boot_to_dos"), \
                mock.patch.object(
                    relict, "run_command",
                    side_effect=RuntimeError("guest failed")), \
                mock.patch.object(relict, "stop") as stop:
            connection.return_value.__enter__.return_value = mock.Mock()
            with self.assertRaisesRegex(RuntimeError, "guest failed"):
                relict.run_guest_program(self.exe)

        stop.assert_called_once_with(54321, None)


class ScreenshotTests(unittest.TestCase):
    def setUp(self):
        self.previous_home = relict._home
        self.tempdir = tempfile.TemporaryDirectory()
        relict.set_home(self.tempdir.name)

    def tearDown(self):
        relict._home = self.previous_home
        self.tempdir.cleanup()

    def test_screenshot_rejects_names_that_are_paths(self):
        invalid_names = ("", ".", "..", "../outside", "..\\outside",
                         "/outside", "C:\\outside")

        with mock.patch.object(relict, "_qmp") as connection:
            for name in invalid_names:
                with self.subTest(name=name):
                    with self.assertRaisesRegex(ValueError, "not a path"):
                        relict.screenshot(name)

        connection.assert_not_called()

    def test_screenshot_requests_png_under_home(self):
        qmp = mock.Mock()
        expected = os.path.join(
            self.tempdir.name, "screenshots", "release-smoke.png")

        with mock.patch.object(relict, "_qmp") as connection:
            connection.return_value.__enter__.return_value = qmp
            relict.screenshot("release-smoke")

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
        with mock.patch.object(relict, "_qmp") as connection, \
                mock.patch.object(relict, "ExecuteError",
                                  UnsupportedPngError), \
                mock.patch.object(relict.time, "sleep"):
            connection.return_value.__enter__.return_value = qmp
            relict.screenshot("legacy")

        self.assertFalse(os.path.exists(ppm))
        with open(png, "rb") as image:
            self.assertEqual(image.read(8), b"\x89PNG\r\n\x1a\n")


if __name__ == "__main__":
    unittest.main()
