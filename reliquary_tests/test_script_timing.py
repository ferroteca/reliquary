# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Tests for the timing model: the placement matrix and the plan."""

import os
import unittest

import reliquary
from reliquary.script_nodes import ScriptParseError
from reliquary.script_parser import parse_script
from reliquary.script_timing import parse_duration, resolve

# The reference script is a shipped builtin, resolved as package
# data so these tests run against an installed artifact too.
_REFERENCE = os.path.join(
    os.path.dirname(os.path.abspath(reliquary.__file__)),
    "codex", "scripts", "freedos-install.rlqs")

_HEAD = "platform dos\n"


class DurationTests(unittest.TestCase):
    def test_every_unit_converts_to_seconds(self):
        self.assertEqual(
            [parse_duration(s) for s in ("500ms", "2s", "1.5m", "2h", ".5s")],
            [0.5, 2.0, 90.0, 7200.0, 0.5])

    def test_a_duration_is_positive(self):
        for source in (_HEAD + 'wait "x" timeout=0s\n',
                       _HEAD + "timeout 0ms\nstart\n",
                       _HEAD + 'wait "x" stable=0s\n'):
            with self.assertRaises(ScriptParseError, msg=source) as caught:
                parse_script(source)
            self.assertIn("must be a positive duration",
                          caught.exception.message)
            self.assertIn("S5", caught.exception.message)


class PlacementMatrixTests(unittest.TestCase):
    """Any placement the matrix rejects is a parse error, with why."""

    def rejects(self, source, reason):
        with self.assertRaises(ScriptParseError, msg=source) as caught:
            parse_script(source)
        self.assertIn(reason, caught.exception.message, msg=source)
        self.assertIn("S2", caught.exception.message, msg=source)

    def test_deadline_is_not_an_observation_bound(self):
        self.rejects(_HEAD + 'wait "x" deadline=5m\n',
                     "exactly what timeout bounds")
        self.rejects(
            _HEAD + 'wait deadline=5m {\n    on "x" {\n        press enter\n'
            '    }\n    on "y" {\n        press enter\n    }\n}\n',
            "a budget belongs to a phase or the run")

    def test_a_handler_does_not_own_its_waiting(self):
        self.rejects(
            _HEAD + 'wait {\n    on "x" timeout=5m {\n        press enter\n'
            '    }\n    on "y" {\n        press enter\n    }\n}\n',
            "write timeout on the wait")
        self.rejects(
            _HEAD + "entry a\nphase a {\n"
            '    always "x" timeout=5m {\n        finish\n    }\n}\n',
            "write timeout on the phase")

    def test_stable_belongs_to_a_match_not_a_container(self):
        self.rejects(
            _HEAD + 'wait stable=1s {\n    on "x" {\n        press enter\n'
            '    }\n    on "y" {\n        press enter\n    }\n}\n',
            "write stable on the on handler")
        self.rejects(_HEAD + "entry a\nphase a stable=1s {\n    finish\n}\n",
                     "a phase has no condition of its own")

    def test_the_matrix_admits_what_it_allows(self):
        script = parse_script(
            _HEAD + "entry a\ntimeout 30s\ndeadline 45m\n"
            "phase a timeout=5m deadline=20m {\n"
            '    wait "x" timeout=90s stable=2s\n'
            "    wait timeout=1m {\n"
            '        on "y" stable=1s {\n            finish\n        }\n'
            '        on "z" {\n            finish\n        }\n    }\n}\n')
        self.assertEqual(script.phases[0].timeout, "5m")


class TimingPlanTests(unittest.TestCase):
    """Resolution is innermost-wins and entirely a parse-time question."""

    def plan(self, source):
        return resolve(parse_script(source))

    def test_the_built_in_default_bounds_an_unadorned_script(self):
        plan = self.plan(_HEAD + 'wait "x"\n')
        self.assertEqual(plan.default.spelling, "60s")
        self.assertEqual(plan.default.scope, "built-in")
        self.assertEqual(plan.observations[0].timeout.seconds, 60.0)

    def test_innermost_wins_across_every_scope(self):
        plan = self.plan(
            _HEAD + "entry a\ntimeout 30s\ndeadline 45m\n"
            "phase a timeout=5m {\n"
            '    wait "phase default"\n'
            '    wait "own bound" timeout=90s\n'
            "    wait timeout=2m {\n"
            '        on "branch" {\n'
            '            wait "inherits the branching wait"\n'
            '            wait "own bound" timeout=10s\n'
            "            finish\n        }\n"
            '        on "other" {\n            finish\n        }\n'
            "    }\n}\n"
            "phase b {\n"
            '    wait "header default"\n'
            "    finish\n}\n")
        resolved = [(o.kind, o.timeout.spelling, o.timeout.scope)
                    for o in plan.observations]
        self.assertEqual(resolved, [
            ("wait", "5m", "phase"),
            ("wait", "90s", "statement"),
            ("branching wait", "2m", "branching wait"),
            ("on", "2m", "branching wait"),
            ("wait", "2m", "branching wait"),
            ("wait", "10s", "statement"),
            ("on", "2m", "branching wait"),
            ("wait", "30s", "header"),
        ])

    def test_a_bound_names_the_scope_that_supplied_it(self):
        plan = self.plan(
            _HEAD + "entry a\ndeadline 45m\nphase a timeout=5m {\n"
            '    wait "x"\n    finish\n}\n')
        bound = plan.observations[0].timeout
        self.assertEqual(bound.source, "phase a (line 4)")
        self.assertEqual(str(bound), "5m from the phase a (line 4)")

    def test_budgets_are_never_inherited(self):
        plan = self.plan(
            _HEAD + "entry a\ndeadline 45m\nphase a deadline=20m {\n"
            '    wait "x"\n    goto b\n}\n'
            "phase b {\n    finish\n}\n")
        self.assertEqual(plan.run_deadline.spelling, "45m")
        self.assertEqual(plan.run_deadline.scope, "header")
        self.assertEqual(plan.phase_deadlines["a"].spelling, "20m")
        self.assertNotIn("b", plan.phase_deadlines)

    def test_a_reactive_phase_bounds_its_own_interval(self):
        plan = self.plan(
            _HEAD + "entry a\ntimeout 30s\nphase a timeout=5m {\n"
            '    always "x" stable=2s {\n        finish\n    }\n}\n')
        interval, handler = plan.observations
        self.assertEqual((interval.kind, interval.timeout.spelling),
                         ("reactive interval", "5m"))
        self.assertEqual(handler.kind, "always")
        self.assertEqual(handler.stable.spelling, "2s")
        self.assertEqual(handler.timeout.spelling, "5m")

    def test_select_is_bounded_by_its_effective_timeout(self):
        plan = self.plan(_HEAD + "timeout 20s\nselect \"Yes\"\n")
        self.assertEqual((plan.observations[0].kind,
                          plan.observations[0].timeout.spelling),
                         ("select", "20s"))

    def test_a_plan_entry_is_found_from_its_parsed_node(self):
        script = parse_script(_HEAD + 'wait "x" timeout=90s\n')
        plan = resolve(script)
        entry = plan.at(script.statements[0])
        self.assertEqual(entry.timeout.seconds, 90.0)

    def test_the_reference_script_resolves(self):
        with open(_REFERENCE, encoding="utf-8") as handle:
            plan = resolve(parse_script(handle.read(), path=_REFERENCE))
        self.assertEqual(plan.default.spelling, "30s")
        self.assertEqual(plan.run_deadline.spelling, "45m")
        self.assertEqual(plan.phase_deadlines["formatting"].spelling, "20m")
        formatting = [o for o in plan.observations
                      if o.phase == "formatting"]
        self.assertTrue(all(o.timeout.spelling == "5m" for o in formatting))
        shutdown = [o for o in plan.observations if o.phase == "shutdown"]
        self.assertEqual([o.timeout.spelling for o in shutdown], ["2m"])


class CycleTests(unittest.TestCase):
    """S12: a cyclable phase graph declares the run's backstop."""

    def rejects(self, source, route):
        with self.assertRaises(ScriptParseError, msg=source) as caught:
            parse_script(source)
        self.assertIn(f"the phase graph can cycle ({route})",
                      caught.exception.message)
        self.assertIn("S12", caught.exception.message)
        return caught.exception

    def test_a_self_loop_needs_a_deadline(self):
        error = self.rejects(
            _HEAD + "entry a\nphase a {\n    goto a\n}\n", "a -> a")
        self.assertEqual(error.line, 4)

    def test_a_longer_cycle_names_its_route(self):
        self.rejects(
            _HEAD + "entry a\nphase a {\n    goto b\n}\n"
            "phase b {\n    goto c\n}\n"
            "phase c {\n    goto a\n}\n", "a -> b -> c -> a")

    def test_a_cycle_through_a_handler_is_found(self):
        self.rejects(
            _HEAD + "entry a\nphase a {\n"
            '    always "x" {\n        goto a\n    }\n}\n', "a -> a")

    def test_a_header_deadline_admits_the_cycle(self):
        script = parse_script(
            _HEAD + "entry a\ndeadline 45m\nphase a {\n    goto a\n}\n")
        self.assertEqual(len(script.phases), 1)

    def test_an_acyclic_graph_needs_no_deadline(self):
        script = parse_script(
            _HEAD + "entry a\nphase a {\n    goto b\n}\n"
            "phase b {\n    goto c\n}\n"
            "phase c {\n    finish\n}\n")
        self.assertEqual(len(script.phases), 3)

    def test_a_diamond_is_not_a_cycle(self):
        script = parse_script(
            _HEAD + "entry a\nphase a {\n    wait {\n"
            '        on "x" {\n            goto b\n        }\n'
            '        on "y" {\n            goto c\n        }\n    }\n}\n'
            "phase b {\n    goto d\n}\n"
            "phase c {\n    goto d\n}\n"
            "phase d {\n    finish\n}\n")
        self.assertEqual(len(script.phases), 4)

    def test_an_unreachable_cycle_is_not_budgeted(self):
        # Unreachable phases are static analysis's warning, not a
        # run the deadline has to bound.
        script = parse_script(
            _HEAD + "entry a\nphase a {\n    finish\n}\n"
            "phase b {\n    goto c\n}\n"
            "phase c {\n    goto b\n}\n")
        self.assertEqual(len(script.phases), 3)


if __name__ == "__main__":
    unittest.main()
