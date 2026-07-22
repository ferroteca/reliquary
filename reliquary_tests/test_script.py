# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Tests for the milestone-one FreeDOS-shaped ``.rlqs`` parser."""

import os
import unittest

import reliquary
from reliquary.script import Script, ScriptParseError, parse_script


class ScriptParserTests(unittest.TestCase):
    def _builtin(self, name):
        path = os.path.join(os.path.dirname(reliquary.__file__), "builtins",
                            "scripts", name)
        with open(path, encoding="utf-8") as handle:
            return handle.read()

    def test_parses_the_shipped_install_state_machine(self):
        result = parse_script(self._builtin("freedos-1.4-plain-install.rlqs"))
        self.assertIsInstance(result, Script)
        self.assertEqual(result.platform, "dos")
        self.assertEqual(result.machine, "stopped")
        self.assertEqual(result.initial, "startup")
        self.assertEqual(
            tuple(result.states),
            ("startup", "cd-boot", "partitioning", "formatting",
             "hd-boot", "shutdown"))
        self.assertEqual(result.states["shutdown"].statements[-1].verb,
                         "done")

    def test_parses_the_shipped_linear_verify_script(self):
        result = parse_script(self._builtin("freedos-1.4-verify.rlqs"))
        self.assertEqual(result.initial, None)
        self.assertEqual(result.machine, "stopped")
        self.assertEqual([statement.verb for statement in result.statements],
                         ["start", "wait", "screenshot", "enter", "wait"])

    def test_bad_syntax_reports_the_line(self):
        with self.assertRaises(ScriptParseError) as caught:
            parse_script('platform: dos\nwait not-quoted\n')
        self.assertEqual(caught.exception.line, 2)
        self.assertEqual(str(caught.exception),
                         "<script>:2:1: error: expected a double-quoted "
                         "string\n2 | wait not-quoted\n    ^")

    def test_state_machine_requires_a_real_initial_state(self):
        source = 'platform: dos\ninitial: missing\nstate ready {\n done\n}\n'
        with self.assertRaises(ScriptParseError) as caught:
            parse_script(source)
        self.assertIn("undeclared", str(caught.exception))

    def test_identifiers_allow_periods_after_the_first_character(self):
        result = parse_script(
            'platform: dos\nmedia freedos-1.4-livecd {\n'
            '"name": "freedos", "file": "freedos.iso",\n'
            '"sha256": "' + "0" * 64 + '"\n}\n')
        self.assertEqual(result.media[0].label, "freedos-1.4-livecd")

    def test_unknown_verbs_and_invalid_durations_fail(self):
        for statement in ('launch now', 'wait "ready", timeout: 3'):
            with self.subTest(statement=statement):
                with self.assertRaises(ScriptParseError):
                    parse_script(f'platform: dos\n{statement}\n')

    def test_transition_error_points_to_the_transition(self):
        source = ('platform: dos\ninitial: ready\nstate ready {\n'
                  ' -> missing\n}\n')
        with self.assertRaises(ScriptParseError) as caught:
            parse_script(source, path="install.rlqs")
        self.assertEqual(caught.exception.line, 4)
        self.assertIn("install.rlqs:4:1: error", str(caught.exception))
        self.assertIn("4 |  -> missing", str(caught.exception))

    def test_machine_header_defaults_to_running(self):
        result = parse_script('platform: dos\nwait "x"\n')
        self.assertEqual(result.machine, "running")

    def test_machine_header_accepts_stopped(self):
        result = parse_script(
            'platform: dos\nmachine: stopped\nstart\nwait "x"\n')
        self.assertEqual(result.machine, "stopped")

    def test_machine_header_rejects_other_values(self):
        with self.assertRaises(ScriptParseError) as caught:
            parse_script('platform: dos\nmachine: paused\nwait "x"\n')
        self.assertIn("running or stopped", str(caught.exception))

    def test_insert_parses_slot_and_media_name(self):
        result = parse_script(
            'platform: dos\ninsert cdrom0 freedos-1.4-livecd\n')
        statement = result.statements[0]
        self.assertEqual(statement.verb, "insert")
        self.assertEqual(statement.argument,
                         ("cdrom0", "freedos-1.4-livecd"))

    def test_insert_normalizes_unindexed_slot(self):
        result = parse_script('platform: dos\ninsert floppy boot-disk\n')
        self.assertEqual(result.statements[0].argument,
                         ("floppy0", "boot-disk"))

    def test_eject_parses_slot(self):
        result = parse_script('platform: dos\neject cdrom0\n')
        statement = result.statements[0]
        self.assertEqual(statement.verb, "eject")
        self.assertEqual(statement.argument, "cdrom0")

    def test_boot_parses_drive_keys(self):
        result = parse_script('platform: dos\nboot hdd0 cdrom0\n')
        statement = result.statements[0]
        self.assertEqual(statement.verb, "boot")
        self.assertEqual(statement.argument, ("hdd0", "cdrom0"))

    def test_boot_normalizes_unindexed_slots(self):
        result = parse_script('platform: dos\nboot hdd cdrom\n')
        self.assertEqual(result.statements[0].argument,
                         ("hdd0", "cdrom0"))

    def test_boot_rejects_duplicates_and_empty(self):
        for statement in ("boot", "boot hdd0 hdd0", "boot hdd0, cdrom0"):
            with self.subTest(statement=statement):
                with self.assertRaises(ScriptParseError):
                    parse_script(f'platform: dos\n{statement}\n')

    def test_insert_rejects_non_removable_slots(self):
        for statement in ("insert hdd0 some-media", "eject hdd0",
                          "eject cdrom4", "insert floppy2 x"):
            with self.subTest(statement=statement):
                with self.assertRaises(ScriptParseError):
                    parse_script(f'platform: dos\n{statement}\n')

    def test_insert_requires_slot_and_media(self):
        for statement in ("insert cdrom0", "insert", "eject",
                          "eject cdrom0 extra"):
            with self.subTest(statement=statement):
                with self.assertRaises(ScriptParseError):
                    parse_script(f'platform: dos\n{statement}\n')


class FreeDOSInstallFlowTests(unittest.TestCase):
    """The shipped install script matches the FreeDOS 1.4 LiveCD flow."""

    @classmethod
    def setUpClass(cls):
        path = os.path.join(os.path.dirname(reliquary.__file__), "builtins",
                            "scripts", "freedos-1.4-plain-install.rlqs")
        with open(path, encoding="utf-8") as handle:
            cls.script = parse_script(handle.read())

    def test_startup_inserts_livecd_then_starts(self):
        """startup supplies the installer medium, then boots into it."""
        stmts = self.script.states["startup"].statements
        self.assertEqual(stmts[0].verb, "insert")
        self.assertEqual(stmts[0].argument,
                         ("cdrom0", "freedos-1.4-livecd"))
        self.assertEqual(stmts[1].verb, "start")
        self.assertEqual(stmts[-1].verb, "transition")
        self.assertEqual(stmts[-1].argument, "cd-boot")

    def test_script_expects_a_stopped_machine(self):
        """The installer medium must be inserted before first boot."""
        self.assertEqual(self.script.machine, "stopped")

    def test_cd_boot_navigates_installer_from_livecd_menu(self):
        """cd-boot picks the installer from the LiveCD menu and accepts English."""
        stmts = self.script.states["cd-boot"].statements
        self.assertEqual(stmts[0].verb, "wait")
        self.assertEqual(stmts[0].argument.value,
                         "Welcome to FreeDOS 1.4 (LiveCD)")
        self.assertEqual(stmts[1].verb, "select")
        self.assertEqual(stmts[1].argument, "Install to harddisk")
        self.assertEqual(stmts[2].verb, "wait")
        self.assertIn("preferred language", stmts[2].argument.value)
        self.assertEqual(stmts[3].verb, "select")
        self.assertIn("English", stmts[3].argument)
        self.assertEqual(stmts[4].verb, "wait")
        self.assertIn("installation program", stmts[4].argument.value)
        self.assertEqual(stmts[5].verb, "press")
        self.assertIn("enter", stmts[5].argument)

    def test_cd_boot_forks_on_partition_then_format(self):
        """expect dispatches to partitioning on a blank disk, formatting after."""
        expect = self.script.states["cd-boot"].statements[-1]
        self.assertEqual(expect.verb, "expect")
        part_branch, fmt_branch = expect.argument
        self.assertIn("partitioned", part_branch.condition.value)
        self.assertEqual(part_branch.statements[-1].argument, "partitioning")
        self.assertIn("formatted", fmt_branch.condition.value)
        self.assertEqual(fmt_branch.statements[-1].argument, "formatting")

    def test_partitioning_reboots_to_cd_boot(self):
        """The partitioning state confirms the reboot and returns to cd-boot."""
        stmts = self.script.states["partitioning"].statements
        self.assertTrue(any("reboot" in s.argument.value.lower()
                            for s in stmts if s.verb == "wait"))
        self.assertEqual(stmts[-1].verb, "transition")
        self.assertEqual(stmts[-1].argument, "cd-boot")

    def test_formatting_completes_the_install_sequence(self):
        """formatting runs the installer through to completion."""
        stmts = self.script.states["formatting"].statements
        waits = [s.argument.value for s in stmts
                 if s.verb == "wait" and s.argument.kind == "text"]
        self.assertTrue(waits[0].startswith("Press a key"))
        self.assertIn("keyboard layout", waits[1])
        self.assertIn("packages", waits[2])
        self.assertIn("ready to install", waits[3])
        self.assertIn("complete", waits[4])
        pkg = next(s for s in stmts
                   if s.verb == "select" and "Plain DOS" in s.argument)
        self.assertIn("sources", pkg.modifiers.get("exclude", ""))
        self.assertEqual(stmts[-1].verb, "transition")
        self.assertEqual(stmts[-1].argument, "hd-boot")

    def test_hd_boot_loads_the_installed_system(self):
        """hd-boot boots from disk and records the installed screen."""
        stmts = self.script.states["hd-boot"].statements
        waits = [s.argument.value for s in stmts
                 if s.verb == "wait" and s.argument.kind == "text"]
        self.assertIn("Load FreeDOS", waits[0])
        self.assertIn("C:\\>", waits[1])
        jemmex = next(s for s in stmts if s.verb == "select")
        self.assertIn("JEMMEX", jemmex.argument)
        self.assertTrue(any(s.verb == "screenshot" for s in stmts))
        self.assertEqual(stmts[-1].verb, "transition")
        self.assertEqual(stmts[-1].argument, "shutdown")

    def test_shutdown_powers_off_then_ejects(self):
        """shutdown powers the guest off and removes the installer medium."""
        stmts = self.script.states["shutdown"].statements
        self.assertEqual(stmts[0].verb, "enter")
        self.assertIn("poweroff", stmts[0].argument)
        self.assertEqual(stmts[-1].verb, "done")
        self.assertEqual(stmts[-2].verb, "eject")
        self.assertEqual(stmts[-2].argument, "cdrom0")
        self.assertEqual(stmts[-3].verb, "wait")
        self.assertEqual(stmts[-3].argument.kind, "stopped")


if __name__ == "__main__":
    unittest.main()
