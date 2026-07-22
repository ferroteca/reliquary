# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Tests for the static rules S3, S5, S7-S11 over the typed tree."""

import unittest

from reliquary.script_nodes import ScriptParseError
from reliquary.script_parser import parse_document

_HEAD = "platform dos\n"


class _ValidationCase(unittest.TestCase):
    def rejects(self, source, message, rule):
        """Assert that a script fails, naming its problem and rule."""
        with self.assertRaises(ScriptParseError, msg=source) as caught:
            parse_document(source)
        self.assertIn(message, caught.exception.message, msg=source)
        self.assertIn(rule, caught.exception.message, msg=source)
        return caught.exception


class ScriptShapeTests(_ValidationCase):
    """S3 and S10: the two shapes, and what belongs to each."""

    def test_a_linear_script_cannot_declare_an_entry_phase(self):
        self.rejects(_HEAD + "entry somewhere\nstart\n",
                     "entry is invalid in a linear script", "S3")

    def test_a_phased_script_requires_an_entry_phase(self):
        self.rejects(_HEAD + "phase a {\n    finish\n}\n",
                     "declares the entry phase", "S3")

    def test_entry_names_a_declared_phase(self):
        self.rejects(_HEAD + "entry b\nphase a {\n    finish\n}\n",
                     "entry names an undeclared phase: b", "S10")

    def test_goto_names_a_declared_phase(self):
        error = self.rejects(
            _HEAD + "entry a\nphase a {\n    goto elsewhere\n}\n",
            "goto names an undeclared phase: elsewhere", "S10")
        self.assertEqual(error.line, 4)

    def test_a_phase_name_is_declared_once(self):
        self.rejects(
            _HEAD + "entry a\nphase a {\n    finish\n}\n"
            "phase a {\n    finish\n}\n", "duplicate phase: a", "S5")

    def test_transfers_are_invalid_in_a_linear_script(self):
        self.rejects(_HEAD + 'wait "x"\nfinish\n',
                     "finish is invalid in a linear script", "S10")
        self.rejects(_HEAD + "goto a\n",
                     "goto is invalid in a linear script", "S10")

    def test_a_transfer_nested_in_a_linear_handler_is_found(self):
        self.rejects(
            _HEAD + 'wait {\n    on "a" {\n        finish\n    }\n'
            '    on "b" {\n        press enter\n    }\n}\n',
            "finish is invalid in a linear script", "S10")

    def test_a_linear_script_needs_no_terminator(self):
        script = parse_document(_HEAD + 'wait "C:\\\\>"\nscreenshot booted\n')
        self.assertEqual([s.verb for s in script.statements],
                         ["wait", "screenshot"])


class PhaseShapeTests(_ValidationCase):
    """S9 and S11: sequential or reactive, and how each ends."""

    def test_a_phase_may_not_mix_statements_with_handlers(self):
        error = self.rejects(
            _HEAD + "entry a\nphase a {\n    press enter\n"
            '    always "x" {\n        finish\n    }\n}\n',
            "sequential or reactive, never both", "S9")
        self.assertEqual(error.line, 5)

    def test_on_is_not_a_standing_rule(self):
        self.rejects(
            _HEAD + 'entry a\nphase a {\n    on "x" {\n        finish\n'
            "    }\n}\n", "on is legal only inside a branching wait", "S9")

    def test_always_is_not_a_branch_of_a_wait(self):
        self.rejects(
            _HEAD + 'entry a\nphase a {\n    wait {\n'
            '        always "x" {\n            finish\n        }\n'
            '        on "y" {\n            finish\n        }\n    }\n}\n',
            "always is legal only directly inside a reactive phase", "S9")

    def test_a_sequential_phase_ends_in_a_transfer(self):
        error = self.rejects(
            _HEAD + "entry a\nphase a {\n    press enter\n}\n",
            "does not end in goto or finish", "S11")
        self.assertEqual(error.line, 4)

    def test_a_branching_wait_terminates_when_every_handler_does(self):
        script = parse_document(
            _HEAD + "entry a\nphase a {\n    wait {\n"
            '        on "x" {\n            finish\n        }\n'
            '        on "y" {\n            goto a\n        }\n    }\n}\n')
        self.assertEqual(script.phases[0].statements[0].verb, "wait")

    def test_a_branching_wait_with_a_falling_handler_does_not_terminate(self):
        self.rejects(
            _HEAD + "entry a\nphase a {\n    wait {\n"
            '        on "x" {\n            finish\n        }\n'
            '        on "y" {\n            press enter\n        }\n'
            "    }\n}\n", "does not end in goto or finish", "S11")

    def test_nothing_follows_a_terminating_statement(self):
        error = self.rejects(
            _HEAD + "entry a\nphase a {\n    finish\n    press enter\n}\n",
            "unreachable statement: finish ends its statement list", "S11")
        self.assertEqual(error.line, 5)

    def test_a_reactive_phase_needs_no_terminator(self):
        script = parse_document(
            _HEAD + "entry a\ndeadline 10m\nphase a {\n"
            '    always "x" {\n        press enter\n    }\n}\n')
        self.assertEqual(len(script.phases[0].handlers), 1)


class BranchingWaitTests(_ValidationCase):
    """S8: what a branching wait is, and where it may stand."""

    def test_a_branching_wait_requires_two_handlers(self):
        self.rejects(
            _HEAD + 'wait {\n    on "x" {\n        press enter\n    }\n}\n',
            "at least two handlers", "S8")

    def test_a_branching_wait_carries_no_condition_of_its_own(self):
        self.rejects(
            _HEAD + 'wait machine=stopped {\n'
            '    on "x" {\n        press enter\n    }\n'
            '    on "y" {\n        press enter\n    }\n}\n',
            "carries no condition of its own", "S8")

    def test_a_branching_wait_may_not_nest_in_a_handler(self):
        self.rejects(
            _HEAD + 'wait {\n    on "x" {\n        wait {\n'
            '            on "y" {\n                press enter\n'
            "            }\n"
            '            on "z" {\n                press enter\n'
            "            }\n        }\n    }\n"
            '    on "w" {\n        press enter\n    }\n}\n',
            "may not appear inside a handler body", "S8")

    def test_a_branching_wait_may_not_nest_in_a_standing_handler(self):
        self.rejects(
            _HEAD + "entry a\nphase a {\n"
            '    always "x" {\n        wait {\n'
            '            on "y" {\n                finish\n            }\n'
            '            on "z" {\n                finish\n            }\n'
            "        }\n    }\n}\n",
            "may not appear inside a handler body", "S8")

    def test_an_empty_handler_body_is_not_a_shape_error(self):
        # The grammar requires a statement in a handler body; the
        # explicit no-action branch is the spec's, not S8's.
        with self.assertRaises(ScriptParseError):
            parse_document(
                _HEAD + 'wait {\n    on "x" {\n    }\n'
                '    on "y" {\n        press enter\n    }\n}\n')


class ObservationChannelTests(_ValidationCase):
    """S7: one condition, on a known channel, of the right kind."""

    def test_an_observation_carries_exactly_one_condition(self):
        self.rejects(_HEAD + 'wait "x" machine=stopped\n',
                     "carries more than one condition", "S7")
        self.rejects(_HEAD + "wait machine=stopped machine=stopped\n",
                     "carries more than one condition", "S7")

    def test_a_wait_requires_a_condition(self):
        self.rejects(_HEAD + "wait timeout=5m\n",
                     "wait requires a condition", "S7")

    def test_a_bare_state_word_is_not_a_condition(self):
        error = self.rejects(_HEAD + "wait stopped\n",
                             "machine state is spelled machine=stopped", "S7")
        self.assertIn("'stopped' is not a condition", error.message)

    def test_a_bare_word_is_not_a_screen_condition(self):
        self.rejects(_HEAD + "wait ready\n",
                     "the screen is observed by a bare string or regex", "S7")

    def test_the_screen_channel_has_no_named_spelling(self):
        self.rejects(_HEAD + 'wait screen="C:\\\\>"\n',
                     "the screen channel has no named spelling", "S7")

    def test_an_unknown_channel_is_named(self):
        self.rejects(_HEAD + 'wait serial="login:"\n',
                     "unknown observation channel: serial", "S7")

    def test_the_machine_channel_takes_a_state_word(self):
        self.rejects(_HEAD + 'wait machine="stopped"\n',
                     "machine observes the state stopped", "S7")
        self.rejects(_HEAD + "wait machine=running\n",
                     "machine observes the state stopped", "S7")

    def test_handler_conditions_take_the_same_channels(self):
        self.rejects(
            _HEAD + 'wait {\n    on "x" machine=stopped {\n'
            "        press enter\n    }\n"
            '    on "y" {\n        press enter\n    }\n}\n',
            "on carries more than one condition", "S7")
        self.rejects(
            _HEAD + "entry a\nphase a {\n"
            '    always disk=full {\n        finish\n    }\n}\n',
            "unknown observation channel: disk", "S7")

    def test_a_handler_names_a_non_default_channel(self):
        script = parse_document(
            _HEAD + "entry a\nphase a {\n    wait timeout=5m {\n"
            '        on "Press a key..." {\n            press enter\n'
            "        }\n"
            "        on machine=stopped {\n            goto a\n        }\n"
            "    }\n    finish\n}\n")
        handlers = script.phases[0].statements[0].handlers
        self.assertEqual([h.condition.channel for h in handlers],
                         ["screen", "machine"])

    def test_a_handler_requires_a_condition(self):
        self.rejects(
            _HEAD + "entry a\nphase a {\n"
            "    always stable=1s {\n        finish\n    }\n}\n",
            "always requires a condition", "S7")

    def test_the_screen_and_machine_channels_validate(self):
        script = parse_document(
            _HEAD + 'wait "C:\\\\>"\nwait /[0-9]+ files/\n'
            "wait machine=stopped timeout=2m\n")
        self.assertEqual(
            [(s.condition.channel, s.condition.kind)
             for s in script.statements],
            [("screen", "text"), ("screen", "regex"), ("machine", "state")])


class DiagnosticContextTests(_ValidationCase):
    """A static error carries the same context as a parse error."""

    def test_a_static_error_renders_its_source_line(self):
        with self.assertRaises(ScriptParseError) as caught:
            parse_document(_HEAD + "wait stopped\n", path="verify.rlqs")
        rendered = str(caught.exception)
        self.assertIn("verify.rlqs:2:6: error:", rendered)
        self.assertIn("wait stopped", rendered)
        self.assertIn("^", rendered)


if __name__ == "__main__":
    unittest.main()
