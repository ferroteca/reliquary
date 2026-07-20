# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Tests for the milestone-one FreeDOS-shaped ``.rqs`` parser."""

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
        result = parse_script(self._builtin("freedos-1.4-plain-install.rqs"))
        self.assertIsInstance(result, Script)
        self.assertEqual(result.platform, "dos")
        self.assertEqual(result.initial, "cd-boot")
        self.assertEqual(
            tuple(result.states), ("cd-boot", "partitioning", "formatting"))
        self.assertEqual(result.media[0].definition.items[0].name,
                         "freedos-1.4-livecd")
        self.assertEqual(result.states["formatting"].statements[-1].verb,
                         "done")

    def test_parses_the_shipped_linear_verify_script(self):
        result = parse_script(self._builtin("freedos-1.4-plain-verify.rqs"))
        self.assertEqual(result.initial, None)
        self.assertEqual([statement.verb for statement in result.statements],
                         ["wait", "screenshot", "enter", "wait"])

    def test_bad_syntax_reports_the_line(self):
        with self.assertRaises(ScriptParseError) as caught:
            parse_script('platform: dos\nwait not-quoted\n')
        self.assertEqual(caught.exception.line, 2)
        self.assertEqual(str(caught.exception),
                         "<script>:2:1: error: expected a double-quoted "
                         "string\n2 | wait not-quoted\n    ^")

    def test_state_machine_requires_a_real_initial_state(self):
        source = 'platform: dos\ninitial: missing\nstate boot {\n done\n}\n'
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
        source = ('platform: dos\ninitial: boot\nstate boot {\n'
                  ' -> missing\n}\n')
        with self.assertRaises(ScriptParseError) as caught:
            parse_script(source, path="install.rqs")
        self.assertEqual(caught.exception.line, 4)
        self.assertIn("install.rqs:4:1: error", str(caught.exception))
        self.assertIn("4 |  -> missing", str(caught.exception))


class FreeDOSInstallFlowTests(unittest.TestCase):
    """The shipped install script matches the FreeDOS 1.4 LiveCD flow."""

    @classmethod
    def setUpClass(cls):
        path = os.path.join(os.path.dirname(reliquary.__file__), "builtins",
                            "scripts", "freedos-1.4-plain-install.rqs")
        with open(path, encoding="utf-8") as handle:
            cls.script = parse_script(handle.read())

    def test_embedded_media_pins_livecd_hashes(self):
        """The script embeds the official LiveCD with pinned SHA-256 hashes."""
        media = self.script.media[0]
        self.assertEqual(media.label, "freedos-1.4-livecd")
        self.assertEqual(
            media.definition.url,
            "https://download.freedos.org/1.4/FD14-LiveCD.zip")
        item = media.definition.items[0]
        self.assertEqual(item.name, "freedos-1.4-livecd")
        self.assertEqual(item.file, "FD14LIVE.iso")
        self.assertEqual(
            item.sha256,
            "c48a9dcf4b8e22f44e268a9879745f0bd88c061195ac584e"
            "6ef2deb0477f81fb")

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

    def test_formatting_completes_install_then_powers_off(self):
        """formatting runs the full install sequence and shuts the guest down."""
        stmts = self.script.states["formatting"].statements
        waits = [s.argument.value for s in stmts
                 if s.verb == "wait" and s.argument.kind == "text"]
        self.assertTrue(waits[0].startswith("Press a key"))
        self.assertIn("keyboard layout", waits[1])
        self.assertIn("packages", waits[2])
        self.assertIn("ready to install", waits[3])
        self.assertIn("complete", waits[4])
        self.assertIn("JEMMEX", waits[5])
        self.assertIn("C:\\>", waits[6])
        pkg = next(s for s in stmts
                   if s.verb == "select" and "Plain DOS" in s.argument)
        self.assertIn("sources", pkg.modifiers.get("exclude", ""))
        self.assertEqual(stmts[-1].verb, "done")
        self.assertEqual(stmts[-2].verb, "wait")
        self.assertEqual(stmts[-2].argument.kind, "stopped")


if __name__ == "__main__":
    unittest.main()
