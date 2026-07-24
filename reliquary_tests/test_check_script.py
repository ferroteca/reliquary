# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""check_script: static analysis and the resolved timing plan."""

import os
import tempfile
import unittest
from unittest import mock

import reliquary
from reliquary.script_nodes import ScriptParseError
from reliquary.script_parser import parse_script
from reliquary.script_runner import check_script
from reliquary.script_timing import format_plan, resolve

_REFERENCE = os.path.join(
    os.path.dirname(os.path.abspath(reliquary.__file__)),
    "codex", "scripts", "freedos-install.rlqs")

_HEAD = "platform dos\n"


class FormatPlanTests(unittest.TestCase):
    """The plan report names every observation's timeout and source."""

    def test_the_report_lists_defaults_budgets_and_observations(self):
        script = parse_script(
            _HEAD + "entry a\ntimeout 30s\ndeadline 45m\n"
            "phase a timeout=5m deadline=20m {\n"
            '    wait "x"\n'
            '    wait "y" timeout=90s\n'
            "    finish\n}\n")
        report = format_plan(resolve(script), name="sample.rlqs")
        self.assertIn("timing plan for sample.rlqs", report)
        self.assertIn("default timeout: 30s from the header", report)
        self.assertIn("run deadline: 45m from the header", report)
        self.assertIn("phase a: 20m from the phase a", report)
        self.assertIn("wait: 5m from the phase a", report)
        self.assertIn("wait: 90s from the statement", report)

    def test_a_built_in_default_is_named(self):
        report = format_plan(resolve(parse_script(_HEAD + 'wait "x"\n')))
        self.assertIn("default timeout: 60s from the built-in", report)


class CheckScriptTests(unittest.TestCase):
    """check_script parses, validates, and returns the timing plan."""

    def test_a_bare_name_reads_a_builtin_without_writing(self):
        with tempfile.TemporaryDirectory() as home:
            result = check_script(
                "freedos-install", context=home)
            self.assertEqual(result.plan.run_deadline.spelling, "45m")
            self.assertFalse(os.path.isdir(
                os.path.join(home, "scripts")))
            self.assertIn("timing plan for", result.report)
            self.assertIn("45m", result.report)

    def test_a_home_script_wins_over_the_builtin(self):
        with tempfile.TemporaryDirectory() as home:
            scripts = os.path.join(home, "scripts")
            os.makedirs(scripts)
            path = os.path.join(scripts, "mine.rlqs")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(_HEAD + 'timeout 12s\nwait "x"\n')
            result = check_script("mine", context=home)
            self.assertEqual(result.script_path, path)
            self.assertEqual(result.plan.default.spelling, "12s")

    def test_a_blueprint_label_resolves_without_creating_a_machine(self):
        with tempfile.TemporaryDirectory() as home:
            result = check_script(
                "install", blueprint="freedos", context=home)
            self.assertIn("freedos-install", result.script_path)
            self.assertFalse(os.path.isdir(
                os.path.join(home, "cache")))
            self.assertEqual(result.plan.run_deadline.spelling, "45m")

    def test_a_static_error_propagates(self):
        with tempfile.TemporaryDirectory() as home:
            scripts = os.path.join(home, "scripts")
            os.makedirs(scripts)
            with open(os.path.join(scripts, "bad.rlqs"),
                      "w", encoding="utf-8") as handle:
                handle.write(_HEAD + "entry a\nphase a {\n    goto a\n}\n")
            with self.assertRaises(ScriptParseError) as caught:
                check_script("bad", context=home)
            self.assertIn("S12", caught.exception.message)

    def test_with_a_machine_media_slots_are_preflighted(self):
        with tempfile.TemporaryDirectory() as home:
            scripts = os.path.join(home, "scripts")
            os.makedirs(scripts)
            with open(os.path.join(scripts, "use-cd.rlqs"),
                      "w", encoding="utf-8") as handle:
                handle.write(
                    _HEAD + 'insert cdrom0 @freedos-livecd\n'
                    'wait "x"\n')
            with mock.patch(
                    "reliquary.script_runner._machines") as machines:
                machines.resolve_machine.return_value = "plain-0"
                machines.load_machine_state.return_value = {
                    "scripts": {},
                    "drives": {"hdd0": {"medium": "hdd"}},
                }
                with self.assertRaises(reliquary.ScriptRuntimeError) as caught:
                    check_script("use-cd", machine="plain-0", context=home)
            self.assertIn("no drive cdrom0", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
