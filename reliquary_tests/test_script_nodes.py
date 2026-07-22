# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Tests for the structural node layer of the script language."""

import os
import unittest

import reliquary
from reliquary.script_nodes import (Interpolation, ScriptParseError,
                                    parse_nodes, tokenize)

# The reference script is a shipped builtin, resolved as package
# data so these tests run against an installed artifact too.
_REFERENCE = os.path.join(
    os.path.dirname(os.path.abspath(reliquary.__file__)),
    "codex", "scripts", "freedos-1.4-plain-install.rlqs")


def _kinds(text):
    return [token.kind for token in tokenize(text, 1)]


def _values(text):
    return [token.value for token in tokenize(text, 1)]


class TokenizerTests(unittest.TestCase):
    def test_the_five_spellings_each_lex_to_their_own_class(self):
        self.assertEqual(
            _kinds('goto x "text" /re/ @medium $key mod=1s'),
            ["word", "word", "string", "regex", "media", "property",
             "modifier"])

    def test_a_string_decodes_its_three_escapes(self):
        literal, = _values(r'"C:\> \"q\" \\ \${literal}"')
        self.assertEqual(literal.text, r'C:\> "q" \ ${literal}')
        self.assertFalse(literal.interpolated)

    def test_a_string_records_interpolations_as_parts(self):
        literal, = _values('"disk ${supplemental.disk} in"')
        self.assertEqual(literal.keys, ("supplemental.disk",))
        self.assertEqual(literal.parts,
                         ("disk ", Interpolation("supplemental.disk"), " in"))
        with self.assertRaises(ValueError):
            literal.text

    def test_a_lone_dollar_sign_is_literal_text(self):
        literal, = _values('"100$ and $x"')
        self.assertEqual(literal.text, "100$ and $x")

    def test_a_regex_unescapes_only_its_slash(self):
        pattern, = _values(r"/[0-9]+ \/ \d files/")
        self.assertEqual(pattern, r"[0-9]+ / \d files")

    def test_comments_end_a_line_but_not_a_string_or_regex(self):
        self.assertEqual(_kinds("press enter # then wait"),
                         ["word", "word"])
        literal, = _values('"# not a comment"')
        self.assertEqual(literal.text, "# not a comment")
        self.assertEqual(_kinds("/a#b/"), ["regex"])

    def test_a_blank_or_comment_only_line_yields_no_tokens(self):
        self.assertEqual(tokenize("   ", 1), ())
        self.assertEqual(tokenize("  # just a comment", 1), ())

    def test_braces_are_their_own_tokens(self):
        self.assertEqual(_kinds("phase startup {"),
                         ["word", "word", "open"])
        self.assertEqual(_kinds("}"), ["close"])

    def test_a_key_chord_is_one_token(self):
        self.assertEqual(_values("press ctrl+alt+delete"),
                         ["press", "ctrl+alt+delete"])

    def test_durations_carry_a_unit_and_munch_maximally(self):
        self.assertEqual(_values("timeout 500ms"), ["timeout", "500ms"])
        self.assertEqual([token.kind for token in tokenize("wait 1.5h", 1)],
                         ["word", "duration"])
        with self.assertRaises(ScriptParseError) as caught:
            tokenize("timeout 30", 1)
        self.assertIn("durations carry a unit", str(caught.exception))

    def test_a_modifier_admits_no_space_around_its_equals(self):
        modifier, = _values("exclude=\"with sources\"")
        self.assertEqual(modifier.name, "exclude")
        self.assertEqual(modifier.value.value.text, "with sources")
        for source in ("timeout = 5m", "timeout =5m", "timeout= 5m"):
            with self.assertRaises(ScriptParseError, msg=source):
                tokenize(source, 1)

    def test_unterminated_strings_and_regexes_report_their_opening(self):
        with self.assertRaises(ScriptParseError) as caught:
            tokenize('wait "unclosed', 1)
        self.assertEqual(caught.exception.column, 6)
        self.assertIn("unterminated string", str(caught.exception))
        with self.assertRaises(ScriptParseError) as caught:
            tokenize("wait /unclosed", 1)
        self.assertIn("unterminated regex", str(caught.exception))

    def test_a_malformed_reference_is_named(self):
        with self.assertRaises(ScriptParseError) as caught:
            tokenize("insert cdrom0 @", 1)
        self.assertIn("invalid media reference", str(caught.exception))


class NodeShapeTests(unittest.TestCase):
    def test_a_node_carries_arguments_then_modifiers(self):
        node, = parse_nodes('select "Plain DOS" exclude="with sources"\n')
        self.assertEqual(node.name, "select")
        self.assertEqual(node.arguments[0].value.text, "Plain DOS")
        self.assertEqual(node.modifiers["exclude"].value.value.text,
                         "with sources")
        self.assertIsNone(node.block)

    def test_a_modifier_cannot_be_followed_by_an_argument(self):
        with self.assertRaises(ScriptParseError) as caught:
            parse_nodes('wait timeout=5m "late"\n')
        self.assertIn("arguments precede modifiers", str(caught.exception))

    def test_a_repeated_modifier_is_an_error(self):
        with self.assertRaises(ScriptParseError) as caught:
            parse_nodes("phase p timeout=5m timeout=6m {\nfinish\n}\n")
        self.assertIn("duplicate modifier: timeout", str(caught.exception))

    def test_blocks_nest_and_close(self):
        nodes = parse_nodes(
            'phase cd-boot {\n'
            '    wait {\n'
            '        on "a" {\n'
            '            goto x\n'
            '        }\n'
            '    }\n'
            '}\n')
        phase, = nodes
        self.assertEqual(phase.name, "phase")
        wait, = phase.block
        handler, = wait.block
        self.assertEqual(handler.name, "on")
        self.assertEqual(handler.block[0].name, "goto")

    def test_an_unclosed_block_names_what_opened_it(self):
        with self.assertRaises(ScriptParseError) as caught:
            parse_nodes("phase startup {\n    start\n")
        self.assertEqual(caught.exception.line, 1)
        self.assertIn("unclosed block opened by 'phase'",
                      str(caught.exception))

    def test_an_unmatched_close_is_an_error(self):
        with self.assertRaises(ScriptParseError) as caught:
            parse_nodes("start\n}\n")
        self.assertIn("unmatched '}'", str(caught.exception))

    def test_a_block_opens_only_at_the_end_of_its_line(self):
        with self.assertRaises(ScriptParseError) as caught:
            parse_nodes("phase p { start\n}\n")
        self.assertIn("a block opens at the end of its line",
                      str(caught.exception))

    def test_a_closing_brace_stands_alone(self):
        with self.assertRaises(ScriptParseError) as caught:
            parse_nodes("phase p {\nfinish\n} phase q {\n}\n")
        self.assertIn("stands alone", str(caught.exception))

    def test_a_line_must_begin_with_a_node_name(self):
        with self.assertRaises(ScriptParseError) as caught:
            parse_nodes('"orphan text"\n')
        self.assertIn("expected a node name", str(caught.exception))

    def test_diagnostics_render_with_a_caret(self):
        with self.assertRaises(ScriptParseError) as caught:
            parse_nodes("start\nwait 30\n", path="x.rlqs")
        self.assertEqual(
            str(caught.exception),
            "x.rlqs:2:6: error: invalid duration: '30' (durations carry a "
            "unit: ms, s, m, or h)\n2 | wait 30\n         ^")


class NoJsonInScriptsTests(unittest.TestCase):
    """A script carries no JSON island inside ordinary blocks.

    Authored assets — media definitions and landmarks — live in
    their own files beside the script, so every block holds nodes.
    The HTTP content body is a raw text body attached to one node,
    not a block.
    """

    def test_every_block_holds_nodes(self):
        phase, = parse_nodes("phase p {\n    finish\n}\n")
        self.assertEqual([child.name for child in phase.block], ["finish"])

    def test_a_json_object_does_not_parse_as_script_content(self):
        with self.assertRaises(ScriptParseError) as caught:
            parse_nodes(
                'media freedos-livecd {\n'
                '  "url": "https://example.test/FD14-LiveCD.zip"\n'
                '}\n')
        self.assertEqual(caught.exception.line, 2)
        self.assertIn("expected a node name", str(caught.exception))

    def test_a_comment_inside_a_block_is_still_a_comment(self):
        phase, = parse_nodes("phase p {\n    # a note\n    finish\n}\n")
        self.assertEqual([child.name for child in phase.block], ["finish"])

    def test_a_content_body_is_not_parsed_as_nodes(self):
        http, = parse_nodes(
            'http {\n'
            '    content answer "/answer.txt" """\n'
            '        not a node\n'
            '    """\n'
            '}\n')
        self.assertEqual([child.name for child in http.block], ["content"])


class ReferenceScriptTests(unittest.TestCase):
    """The milestone's reference script parses structurally."""

    def setUp(self):
        with open(_REFERENCE, encoding="utf-8") as handle:
            self.nodes = parse_nodes(handle.read(), path=_REFERENCE)

    def test_the_headers_and_phases_are_the_top_level_nodes(self):
        self.assertEqual(
            [node.name for node in self.nodes],
            ["description", "platform", "machine", "entry", "timeout",
             "deadline", "phase", "phase", "phase", "phase", "phase",
             "phase"])

    def test_every_phase_opens_a_block_of_statements(self):
        phases = [node for node in self.nodes if node.name == "phase"]
        self.assertEqual(
            [phase.arguments[0].value for phase in phases],
            ["startup", "cd-boot", "partitioning", "formatting", "hd-boot",
             "shutdown"])
        for phase in phases:
            self.assertIsNotNone(phase.block)

    def test_the_branching_wait_holds_two_handlers(self):
        cd_boot = next(node for node in self.nodes
                       if node.name == "phase"
                       and node.arguments[0].value == "cd-boot")
        wait = cd_boot.block[-1]
        self.assertEqual(wait.name, "wait")
        self.assertEqual(wait.arguments, ())
        self.assertEqual([handler.name for handler in wait.block],
                         ["on", "on"])
        self.assertEqual(
            [handler.block[-1].arguments[0].value for handler in wait.block],
            ["partitioning", "formatting"])

    def test_phase_timing_modifiers_are_read(self):
        formatting = next(node for node in self.nodes
                          if node.name == "phase"
                          and node.arguments[0].value == "formatting")
        self.assertEqual(formatting.modifiers["timeout"].value.value, "5m")
        self.assertEqual(formatting.modifiers["deadline"].value.value, "20m")

    def test_the_machine_channel_reads_as_a_modifier(self):
        shutdown = next(node for node in self.nodes
                        if node.name == "phase"
                        and node.arguments[0].value == "shutdown")
        wait = shutdown.block[1]
        self.assertEqual(wait.name, "wait")
        self.assertEqual(wait.arguments, ())
        self.assertEqual(wait.modifiers["machine"].value.value, "stopped")
        self.assertEqual(wait.modifiers["timeout"].value.value, "2m")


if __name__ == "__main__":
    unittest.main()
