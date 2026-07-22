# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Tests for the typed layer: grammar, vocabulary, and signatures."""

import os
import unittest

import reliquary
from reliquary.script_nodes import ScriptParseError
from reliquary.script_parser import parse_script

# The reference script is a shipped builtin, resolved as package
# data so these tests run against an installed artifact too.
_REFERENCE = os.path.join(
    os.path.dirname(os.path.abspath(reliquary.__file__)),
    "codex", "scripts", "freedos-1.4-plain-install.rlqs")

_HEAD = "platform dos\n"


class ReferenceScriptTests(unittest.TestCase):
    """The milestone's reference script types end to end."""

    def setUp(self):
        with open(_REFERENCE, encoding="utf-8") as handle:
            self.script = parse_script(handle.read(), path=_REFERENCE)

    def test_headers_carry_their_values(self):
        self.assertEqual(self.script.platform, "dos")
        self.assertEqual(self.script.machine, "stopped")
        self.assertEqual(self.script.entry, "startup")
        self.assertEqual(self.script.timeout, "30s")
        self.assertEqual(self.script.deadline, "45m")
        self.assertEqual(self.script.description.text,
                         "FreeDOS 1.4 plain install from LiveCD")

    def test_the_phases_are_named_in_order(self):
        self.assertEqual([phase.name for phase in self.script.phases],
                         ["startup", "cd-boot", "partitioning",
                          "formatting", "hd-boot", "shutdown"])
        self.assertEqual(self.script.statements, ())

    def test_a_branching_wait_carries_its_on_handlers(self):
        phase = self._phase("cd-boot")
        wait = phase.statements[-1]
        self.assertEqual(wait.verb, "wait")
        self.assertIsNone(wait.condition)
        self.assertEqual([handler.keyword for handler in wait.handlers],
                         ["on", "on"])
        self.assertEqual(
            [handler.condition.value.text for handler in wait.handlers],
            ["Drive C: does not appear to be partitioned.",
             "Drive C: does not appear to be formatted."])
        self.assertEqual(
            [[s.verb for s in handler.statements]
             for handler in wait.handlers],
            [["select", "goto"], ["select", "goto"]])

    def test_phase_timing_modifiers_type_as_durations(self):
        phase = self._phase("formatting")
        self.assertEqual(phase.timeout, "5m")
        self.assertEqual(phase.deadline, "20m")

    def test_the_machine_channel_becomes_a_condition(self):
        wait = self._phase("shutdown").statements[1]
        self.assertEqual(wait.condition.channel, "machine")
        self.assertEqual(wait.condition.kind, "state")
        self.assertEqual(wait.condition.value, "stopped")
        self.assertEqual(wait.timeout, "2m")

    def test_a_bare_string_is_a_screen_condition(self):
        wait = self._phase("cd-boot").statements[0]
        self.assertEqual(wait.condition.channel, "screen")
        self.assertEqual(wait.condition.kind, "text")
        self.assertEqual(wait.condition.value.text,
                         "Welcome to FreeDOS 1.4 (LiveCD)")

    def test_insert_and_select_carry_their_typed_arguments(self):
        insert = self._phase("startup").statements[0]
        self.assertEqual(insert.arguments,
                         ("cdrom0", ("media", "freedos-1.4-livecd")))
        select = next(s for s in self._phase("formatting").statements
                      if s.verb == "select" and s.exclude)
        self.assertEqual(select.arguments[0].text, "Plain DOS system")
        self.assertEqual(select.exclude.text, "with sources")

    def _phase(self, name):
        return next(p for p in self.script.phases if p.name == name)


class VocabularyTests(unittest.TestCase):
    def test_a_keyword_is_a_plain_name_outside_node_position(self):
        # `enter` is a verb at the start of a line and a key name
        # after `press`; `insert` and `type` likewise.
        script = parse_script(
            _HEAD + "press enter\npress ctrl+alt+delete\n"
            "press insert\nset-boot hdd0 cdrom0\n")
        self.assertEqual([s.verb for s in script.statements],
                         ["press", "press", "press", "set-boot"])
        self.assertEqual([s.arguments for s in script.statements],
                         [("enter",), ("ctrl+alt+delete",), ("insert",),
                          ("hdd0", "cdrom0")])

    def test_the_renamed_vocabulary_parses(self):
        script = parse_script(
            "platform dos\nentry go\n"
            "phase go {\n    goto next\n}\n"
            "phase next {\n    finish\n}\n")
        self.assertEqual([p.name for p in script.phases], ["go", "next"])
        self.assertEqual(script.phases[0].statements[0].verb, "goto")
        self.assertEqual(script.phases[1].statements[0].verb, "finish")

    def test_a_reactive_phase_holds_always_handlers(self):
        script = parse_script(
            "platform dos\nentry watch\ndeadline 10m\n"
            "phase watch {\n"
            "    always /copied [0-9]+ files/ stable=2s {\n"
            "        screenshot progress\n"
            "        goto watch\n"
            "    }\n"
            "    always \"Setup complete\" {\n        finish\n    }\n"
            "}\n")
        phase = script.phases[0]
        self.assertEqual(phase.statements, ())
        self.assertEqual([h.keyword for h in phase.handlers],
                         ["always", "always"])
        self.assertEqual(phase.handlers[0].condition.kind, "regex")
        self.assertEqual(phase.handlers[0].condition.value,
                         "copied [0-9]+ files")
        self.assertEqual(phase.handlers[0].stable, "2s")

    def test_property_declarations_type_their_kind_and_prompt(self):
        script = parse_script(
            _HEAD + 'property windows.user\n'
            'property secret windows.license-key prompt="License key"\n'
            'start\n')
        self.assertEqual([(p.key, p.kind) for p in script.properties],
                         [("windows.user", "text"),
                          ("windows.license-key", "secret")])
        self.assertEqual(script.properties[1].prompt.text, "License key")

    def test_an_unknown_property_kind_is_named(self):
        with self.assertRaises(ScriptParseError) as caught:
            parse_script(_HEAD + "property txt some.key\nstart\n")
        self.assertIn("unknown property kind: 'txt'",
                      str(caught.exception))


class SignatureTests(unittest.TestCase):
    def test_a_node_rejects_a_modifier_outside_its_signature(self):
        with self.assertRaises(ScriptParseError) as caught:
            parse_script(_HEAD + 'enter "x" timeout=5m\n')
        self.assertIn("enter does not accept the modifier 'timeout'",
                      str(caught.exception))
        self.assertIn("accepts: none", str(caught.exception))

    def test_a_wait_takes_the_timing_modifiers_that_are_its_own(self):
        # Only the timing set is a wait's own; every other modifier
        # names a channel, and S7 owns that diagnostic.
        with self.assertRaises(ScriptParseError) as caught:
            parse_script(_HEAD + 'wait "x" exclude="y"\n')
        self.assertIn("unknown observation channel: exclude",
                      str(caught.exception))

    def test_a_timing_modifier_requires_a_duration(self):
        with self.assertRaises(ScriptParseError) as caught:
            parse_script(_HEAD + 'wait "x" timeout=soon\n')
        self.assertIn("timeout must be a duration", str(caught.exception))

    def test_select_accepts_only_exclude(self):
        script = parse_script(_HEAD + 'select "a" exclude="b"\n')
        self.assertEqual(script.statements[0].exclude.text, "b")
        with self.assertRaises(ScriptParseError):
            parse_script(_HEAD + 'select "a" stable=2s\n')

    def test_a_repeated_header_is_rejected(self):
        with self.assertRaises(ScriptParseError) as caught:
            parse_script("platform dos\nplatform win9x\nstart\n")
        self.assertIn("platform may appear only once",
                      str(caught.exception))


class LexicalDiagnosticsTests(unittest.TestCase):
    """The lexer's authored messages survive the lark layer."""

    def test_modifier_spacing_keeps_its_message_in_any_context(self):
        for source in (_HEAD + 'wait "x" timeout = 5m\n',
                       _HEAD + "phase p timeout = 5m {\n}\n",
                       _HEAD + 'select "a" exclude = "b"\n'):
            with self.assertRaises(ScriptParseError, msg=source) as caught:
                parse_script(source)
            self.assertIn("modifiers are written name=value",
                          str(caught.exception))

    def test_a_duration_without_a_unit_keeps_its_message(self):
        for source in (_HEAD + 'wait "x" timeout=30\n',
                       _HEAD + "deadline 45\n"):
            with self.assertRaises(ScriptParseError, msg=source) as caught:
                parse_script(source)
            self.assertIn("durations carry a unit", str(caught.exception))

    def test_an_unterminated_string_keeps_its_message(self):
        for source in (_HEAD + 'wait "unclosed\n',
                       _HEAD + 'type "unclosed\n'):
            with self.assertRaises(ScriptParseError, msg=source) as caught:
                parse_script(source)
            self.assertIn("unterminated string", str(caught.exception))

    def test_a_syntax_error_reports_a_line_and_renders_a_caret(self):
        with self.assertRaises(ScriptParseError) as caught:
            parse_script(_HEAD + "goto\n", path="x.rlqs")
        self.assertEqual(caught.exception.line, 2)
        self.assertIn("x.rlqs:2:", str(caught.exception))
        self.assertIn("^", str(caught.exception))


class SupersededSurfaceTests(unittest.TestCase):
    """The milestone-one spellings are gone, not bridged."""

    def test_the_old_surface_no_longer_parses(self):
        for label, source in (
                ("colon headers", 'platform: dos\nstart\n'),
                ("state", "platform dos\nstate ready {\n done\n}\n"),
                ("arrow", "platform dos\nentry a\n"
                          "phase a {\n    -> b\n}\n"),
                ("done", "platform dos\nentry a\n"
                         "phase a {\n    done\n}\n"),
                ("expect", 'platform dos\nexpect "x" {\n}\n'),
                ("regex keyword", 'platform dos\nwait regex "x"\n'),
                ("comma modifiers", 'platform dos\n'
                                    'wait "x", timeout: 5m\n'),
                ("bare stopped", "platform dos\nwait stopped\n"),
                ("boot verb", "platform dos\nboot hdd0\n")):
            with self.assertRaises(ScriptParseError, msg=label):
                parse_script(source)


if __name__ == "__main__":
    unittest.main()
