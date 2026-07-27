# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Tests for the static rules S3, S5, S7-S11 over the typed tree."""

import unittest

from reliquary.script_nodes import ScriptParseError
from reliquary.script_parser import parse_script

_HEAD = "platform dos\n"


class _ValidationCase(unittest.TestCase):
    def rejects(self, source, message, rule):
        """Assert that a script fails, naming its problem and rule."""
        with self.assertRaises(ScriptParseError, msg=source) as caught:
            parse_script(source)
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

    def test_a_phase_may_not_be_named_a_node_name(self):
        # script-spec.md, "Grammar": reserved node names cannot name
        # phases. The lexer makes a word a keyword only where a node
        # may start, so these parse cleanly and validation is what
        # refuses them.
        for word in ("enter", "timeout", "phase", "goto", "set-boot"):
            with self.subTest(name=word):
                self.rejects(
                    _HEAD + f"entry {word}\nphase {word} {{\n"
                    "    finish\n}\n",
                    f"a phase may not be a reserved node name: {word}",
                    "S5")

    def test_a_property_key_may_not_be_a_node_name(self):
        self.rejects(
            _HEAD + 'property text press\nwait "x"\n',
            "a property key may not be a reserved node name: press",
            "S5")

    def test_the_closed_vocabularies_stay_contextual(self):
        # D53 refused reserving key names and drive slots globally:
        # syntax words are reserved, domain vocabularies are not, which
        # is the line Java and C# draw. So a phase may still be named
        # for a key or a slot, and `press enter` still means the key.
        for source in (
            _HEAD + "entry cdrom0\nphase cdrom0 {\n    finish\n}\n",
            _HEAD + "entry esc\nphase esc {\n    finish\n}\n",
            _HEAD + "press enter\n",
            _HEAD + "screenshot end\n",
        ):
            with self.subTest(source=source):
                parse_script(source)

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
        script = parse_script(_HEAD + 'wait "C:\\\\>"\nscreenshot booted\n')
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
        script = parse_script(
            _HEAD + "entry a\ndeadline 10m\nphase a {\n    wait {\n"
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
        script = parse_script(
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
            parse_script(
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
        script = parse_script(
            _HEAD + "entry a\ndeadline 10m\nphase a {\n    wait timeout=5m {\n"
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
        script = parse_script(
            _HEAD + 'wait "C:\\\\>"\nwait /[0-9]+ files/\n'
            "wait machine=stopped timeout=2m\n")
        self.assertEqual(
            [(s.condition.channel, s.condition.kind)
             for s in script.statements],
            [("screen", "text"), ("screen", "regex"), ("machine", "state")])


class WatchPatternTests(_ValidationCase):
    """S13: a watch pattern is non-empty, and a regex compiles.

    The rule was specified when the surface was adopted and
    enforced by nothing until the spec-inventory comparison found
    it (`test_script_spec_conformance`). Each case below parsed
    cleanly before that: an empty pattern made a `wait` a no-op
    that passed on its first sample, and a malformed regex reached
    `re.search` in the sample loop, where it raised `re.error` —
    exit 1, a fault outside the taxonomy, for a defect the script
    text alone shows.
    """

    def test_an_empty_string_condition_is_not_a_pattern(self):
        self.rejects(_HEAD + 'wait ""\n',
                     "an empty watch pattern matches every screen", "S13")

    def test_an_empty_regex_condition_is_not_a_pattern(self):
        self.rejects(_HEAD + "wait //\n",
                     "an empty watch pattern matches every screen", "S13")

    def test_a_malformed_regex_is_refused_before_the_run(self):
        error = self.rejects(_HEAD + "wait /a(b/\n",
                             "the regex does not compile", "S13")
        self.assertIn("Python's re syntax", error.message)
        self.assertEqual(error.line, 2)

    def test_handler_conditions_carry_the_rule_too(self):
        self.rejects(
            _HEAD + 'wait {\n    on /x[/ {\n        press enter\n    }\n'
            '    on "y" {\n        press enter\n    }\n}\n',
            "the regex does not compile", "S13")
        self.rejects(
            _HEAD + "entry a\nphase a {\n"
            '    always "" {\n        finish\n    }\n}\n',
            "an empty watch pattern", "S13")

    def test_an_interpolation_alone_is_a_pattern(self):
        # `${key}` is text the run binds, so the authored pattern
        # is not empty even though it carries no literal character.
        script = parse_script(
            _HEAD + 'property text target\nwait "${target}"\n')
        self.assertEqual(script.statements[0].condition.kind, "text")

    def test_a_machine_state_carries_no_pattern_rule(self):
        script = parse_script(_HEAD + "wait machine=stopped\n")
        self.assertEqual(script.statements[0].condition.value, "stopped")


class HttpValidationTests(_ValidationCase):
    """Milestone 5 HTTP declarations are statically checkable."""

    def test_content_paths_are_absolute_and_normalized(self):
        self.rejects(
            _HEAD + 'http {\n    content answer "answer.txt" """\n'
            '        one\n    """\n}\nstart\n',
            "content path must begin with '/'", "content")
        self.rejects(
            _HEAD + 'http {\n    content answer "/../answer.txt" """\n'
            '        one\n    """\n}\nstart\n',
            "content path may not contain . or ..", "content")

    def test_content_paths_are_unique(self):
        self.rejects(
            _HEAD + 'http {\n    content answer "/answer.txt" """\n'
            '        one\n    """\n    content other "/answer.txt" """\n'
            '        two\n    """\n}\nstart\n',
            "duplicate content path: /answer.txt", "content")

    def test_content_names_are_unique_within_one_set(self):
        self.rejects(
            _HEAD + 'http {\n    content answer "/answer.txt" """\n'
            '        one\n    """\n    content answer "/other.txt" """\n'
            '        two\n    """\n}\nstart\n',
            "duplicate content name: answer", "content")
        self.rejects(
            _HEAD + 'http start {\n    content answer "/answer.txt" """\n'
            '        one\n    """\n    content answer "/other.txt" """\n'
            '        two\n    """\n}\n',
            "duplicate content name: answer", "content")

    def test_content_body_may_not_be_empty(self):
        self.rejects(
            _HEAD + 'http {\n    content answer "/answer.txt" """\n'
            '    """\n}\nstart\n',
            "has an empty body", "content")

    def test_port_range_is_checked(self):
        self.rejects(
            _HEAD + 'http port-min=9000 port-max=8000 {\n'
            '    content answer "/answer.txt" """\n        one\n    """\n'
            '}\nstart\n',
            "port-min must be less than or equal to port-max", "port")
        self.rejects(
            _HEAD + 'http port-min=70000 {\n'
            '    content answer "/answer.txt" """\n        one\n    """\n'
            '}\nstart\n',
            "port-min is not a TCP port", "port")

    def test_reserved_property_namespaces_are_rejected(self):
        self.rejects(_HEAD + "property rlq.http.url\nstart\n",
                     "rlq namespace", "S5")
        self.rejects(_HEAD + "property reliquary.http.url\nstart\n",
                     "reliquary namespace", "S5")

    def test_rlq_http_reference_requires_http_block(self):
        self.rejects(_HEAD + 'enter "${rlq.http.url}/answer.txt"\n',
                     "rlq.http.* properties require an http block", "S6")

    def test_http_start_requires_declared_content(self):
        self.rejects(_HEAD + "http start\n",
                     "http start requires declared or inline content",
                     "http")

    def test_http_action_names_are_closed(self):
        self.rejects(
            _HEAD + 'http {\n    content answer "/answer.txt" """\n'
            '        one\n    """\n}\nhttp begin\n',
            "http action must be start or stop", "http")

    def test_http_stop_is_allowed_without_declared_content(self):
        script = parse_script(_HEAD + "http stop\n")
        self.assertEqual(script.statements[0].arguments, ("stop",))

    def test_http_start_names_declared_content(self):
        self.rejects(
            _HEAD + 'http {\n    content answer "/answer.txt" """\n'
            '        one\n    """\n}\nhttp start missing\n',
            "http start names undeclared content: missing", "http")

    def test_http_start_can_define_inline_content_without_declaration(self):
        script = parse_script(
            _HEAD + 'http start {\n    content answer "/answer.txt" """\n'
            '        one\n    """\n}\n'
            'enter "${rlq.http.url}/answer.txt"\n')
        self.assertEqual(script.statements[0].contents[0].name, "answer")

    def test_http_start_can_redefine_declared_content_inline(self):
        script = parse_script(
            _HEAD + 'http {\n    content answer "/answer.txt" """\n'
            '        one\n    """\n}\n'
            'http start {\n    content answer "/answer.txt" """\n'
            '        two\n    """\n}\n')
        self.assertEqual(script.statements[0].contents[0].body.text,
                         "two\n")

    def test_http_stop_takes_no_names_or_block(self):
        self.rejects(_HEAD + "http stop answer\n",
                     "http stop takes no content names", "http")


class PortableKeyTests(_ValidationCase):
    """S14: ``press`` uses the language's closed portable key set."""

    def test_every_portable_key_name_is_valid(self):
        names = (
            "enter esc tab space backspace up down left right insert delete "
            "home end pageup pagedown f1 f2 f3 f4 f5 f6 f7 f8 f9 f10 f11 "
            "f12 ctrl alt shift"
        )
        script = parse_script(_HEAD + "press " + names + "\n")
        self.assertEqual(script.statements[0].arguments,
                         tuple(names.split()))

    def test_a_chord_may_contain_a_printable_character(self):
        script = parse_script(_HEAD + "press ctrl+c ctrl+alt+delete\n")
        self.assertEqual(script.statements[0].arguments,
                         ("ctrl+c", "ctrl+alt+delete"))

    def test_an_unknown_key_name_is_a_static_error(self):
        self.rejects(_HEAD + "press wingding\n",
                     "'wingding' is not a portable key name", "S14")

    def test_a_bare_character_is_text_not_a_key_name(self):
        self.rejects(_HEAD + "press c\n",
                     "'c' is not a portable key name", "S14")

    def test_an_empty_chord_member_is_invalid(self):
        self.rejects(_HEAD + "press ctrl++c\n",
                     "'' is not a portable key name", "S14")


class MachineVariableTests(_ValidationCase):
    """A machine-variable key is the consumer's, but not reliquary's."""

    def test_an_ordinary_key_is_accepted(self):
        parse_script(_HEAD + 'set suite.result "PASS"\n')

    def test_the_reserved_namespaces_are_refused(self):
        self.rejects(_HEAD + 'set rlq.ready "yes"\n',
                     "rlq namespace are reserved", "S5")
        self.rejects(_HEAD + 'set reliquary "yes"\n',
                     "reliquary namespace are reserved", "S5")

    def test_a_reserved_key_inside_a_handler_is_found(self):
        self.rejects(
            _HEAD + 'wait {\n    on "a" {\n        set rlq.x "1"\n'
            "        finish\n    }\n"
            '    on "b" {\n        finish\n    }\n}\n',
            "rlq namespace are reserved", "S5")


class DiagnosticContextTests(_ValidationCase):
    """A static error carries the same context as a parse error."""

    def test_a_static_error_renders_its_source_line(self):
        with self.assertRaises(ScriptParseError) as caught:
            parse_script(_HEAD + "wait stopped\n", path="verify.rlqs")
        rendered = str(caught.exception)
        self.assertIn("verify.rlqs:2:6: error:", rendered)
        self.assertIn("wait stopped", rendered)
        self.assertIn("^", rendered)


if __name__ == "__main__":
    unittest.main()
