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


if __name__ == "__main__":
    unittest.main()
