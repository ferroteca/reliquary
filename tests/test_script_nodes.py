# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for the structural node layer of the script language."""

import os

import pytest

import reliquary
from reliquary.errors import InternalError
from reliquary.script_nodes import (Interpolation, ScriptParseError,
                                    parse_nodes, tokenize)

# The reference script is a shipped builtin, resolved as package
# data so these tests run against an installed artifact too.
_REFERENCE = os.path.join(
    os.path.dirname(os.path.abspath(reliquary.__file__)),
    "codex", "scripts", "freedos-install.rlqs")


def _kinds(text):
    return [token.kind for token in tokenize(text, 1)]


def _values(text):
    return [token.value for token in tokenize(text, 1)]


# The tokenizer.

def test_the_five_spellings_each_lex_to_their_own_class():
    assert _kinds('goto x "text" /re/ @medium $key mod=1s') == [
        "word", "word", "string", "regex", "media", "property",
        "modifier"]


def test_a_string_decodes_its_three_escapes():
    literal, = _values(r'"C:\> \"q\" \\ \${literal}"')
    assert literal.text == r'C:\> "q" \ ${literal}'
    assert not literal.interpolated


def test_a_string_records_interpolations_as_parts():
    literal, = _values('"disk ${supplemental.disk} in"')
    assert literal.keys == ("supplemental.disk",)
    assert literal.parts == ("disk ", Interpolation("supplemental.disk"),
                             " in")
    with pytest.raises(InternalError):
        literal.text


def test_a_lone_dollar_sign_is_literal_text():
    literal, = _values('"100$ and $x"')
    assert literal.text == "100$ and $x"


def test_a_regex_unescapes_only_its_slash():
    pattern, = _values(r"/[0-9]+ \/ \d files/")
    assert pattern == r"[0-9]+ / \d files"


def test_comments_end_a_line_but_not_a_string_or_regex():
    assert _kinds("press enter # then wait") == ["word", "word"]
    literal, = _values('"# not a comment"')
    assert literal.text == "# not a comment"
    assert _kinds("/a#b/") == ["regex"]


def test_a_blank_or_comment_only_line_yields_no_tokens():
    assert tokenize("   ", 1) == ()
    assert tokenize("  # just a comment", 1) == ()


def test_braces_are_their_own_tokens():
    assert _kinds("phase startup {") == ["word", "word", "open"]
    assert _kinds("}") == ["close"]


def test_a_key_chord_is_one_token():
    assert _values("press ctrl+alt+delete") == ["press",
                                                "ctrl+alt+delete"]


def test_durations_carry_a_unit_and_munch_maximally():
    assert _values("timeout 500ms") == ["timeout", "500ms"]
    assert [token.kind for token in tokenize("wait 1.5h", 1)] == [
        "word", "duration"]
    with pytest.raises(ScriptParseError) as caught:
        tokenize("timeout 30", 1)
    assert "durations carry a unit" in str(caught.value)


def test_a_modifier_admits_no_space_around_its_equals():
    modifier, = _values("exclude=\"with sources\"")
    assert modifier.name == "exclude"
    assert modifier.value.value.text == "with sources"
    for source in ("timeout = 5m", "timeout =5m", "timeout= 5m"):
        with pytest.raises(ScriptParseError):
            tokenize(source, 1)


def test_unterminated_strings_and_regexes_report_their_opening():
    with pytest.raises(ScriptParseError) as caught:
        tokenize('wait "unclosed', 1)
    assert caught.value.column == 6
    assert "unterminated string" in str(caught.value)
    with pytest.raises(ScriptParseError) as caught:
        tokenize("wait /unclosed", 1)
    assert "unterminated regex" in str(caught.value)


def test_a_malformed_reference_is_named():
    with pytest.raises(ScriptParseError) as caught:
        tokenize("insert cdrom0 @", 1)
    assert "invalid media reference" in str(caught.value)


def test_a_media_name_may_lead_with_a_digit():
    # The `@` sigil marks this token as a media reference, so
    # `@86Box` is unambiguous even though a bare `86Box` would lex
    # as a duration. A property key also appears bare elsewhere (in
    # a `property` declaration), so it still has to start with a
    # letter (D24).
    assert tokenize("insert cdrom0 @86Box", 1)[-1].value == "86Box"
    with pytest.raises(ScriptParseError) as caught:
        tokenize("wait $86key", 1)
    assert "invalid property reference" in str(caught.value)


# Node shapes.

def test_a_node_carries_arguments_then_modifiers():
    node, = parse_nodes('select "Plain DOS" exclude="with sources"\n')
    assert node.name == "select"
    assert node.arguments[0].value.text == "Plain DOS"
    assert node.modifiers["exclude"].value.value.text == "with sources"
    assert node.block is None


def test_a_modifier_cannot_be_followed_by_an_argument():
    with pytest.raises(ScriptParseError) as caught:
        parse_nodes('wait timeout=5m "late"\n')
    assert "arguments precede modifiers" in str(caught.value)


def test_a_repeated_modifier_is_an_error():
    with pytest.raises(ScriptParseError) as caught:
        parse_nodes("phase p timeout=5m timeout=6m {\nfinish\n}\n")
    assert "duplicate modifier: timeout" in str(caught.value)


def test_blocks_nest_and_close():
    nodes = parse_nodes(
        'phase cd-boot {\n'
        '    wait {\n'
        '        on "a" {\n'
        '            goto x\n'
        '        }\n'
        '    }\n'
        '}\n')
    phase, = nodes
    assert phase.name == "phase"
    wait, = phase.block
    handler, = wait.block
    assert handler.name == "on"
    assert handler.block[0].name == "goto"


def test_an_unclosed_block_names_what_opened_it():
    with pytest.raises(ScriptParseError) as caught:
        parse_nodes("phase startup {\n    start\n")
    assert caught.value.line == 1
    assert "unclosed block opened by 'phase'" in str(caught.value)


def test_an_unmatched_close_is_an_error():
    with pytest.raises(ScriptParseError) as caught:
        parse_nodes("start\n}\n")
    assert "unmatched '}'" in str(caught.value)


def test_a_block_opens_only_at_the_end_of_its_line():
    with pytest.raises(ScriptParseError) as caught:
        parse_nodes("phase p { start\n}\n")
    assert "a block opens at the end of its line" in str(caught.value)


def test_a_closing_brace_stands_alone():
    with pytest.raises(ScriptParseError) as caught:
        parse_nodes("phase p {\nfinish\n} phase q {\n}\n")
    assert "stands alone" in str(caught.value)


def test_a_line_must_begin_with_a_node_name():
    with pytest.raises(ScriptParseError) as caught:
        parse_nodes('"orphan text"\n')
    assert "expected a node name" in str(caught.value)


def test_diagnostics_render_with_a_caret():
    # The rendered message ends with the diagnostic's id in
    # parentheses — the same position V-numbers used to sit in. The
    # id is the stable value code can switch on; the wording of the
    # message is not.
    with pytest.raises(ScriptParseError) as caught:
        parse_nodes("start\nwait 30\n", path="x.rlqs")
    assert str(caught.value) == (
        "x.rlqs:2:6: error: invalid duration: '30' (durations carry a "
        "unit: ms, s, m, or h) (lex.invalid-duration)"
        "\n2 | wait 30\n         ^")


# A script never has a block of raw JSON embedded inside an
# ordinary block. Authored assets — media definitions and landmarks
# — live in their own files beside the script, so every block holds
# nodes. The HTTP content body is raw text attached to one node, not
# a block.

def test_every_block_holds_nodes():
    phase, = parse_nodes("phase p {\n    finish\n}\n")
    assert [child.name for child in phase.block] == ["finish"]


def test_a_json_object_does_not_parse_as_script_content():
    with pytest.raises(ScriptParseError) as caught:
        parse_nodes(
            'media freedos-livecd {\n'
            '  "url": "https://example.test/FD14-LiveCD.zip"\n'
            '}\n')
    assert caught.value.line == 2
    assert "expected a node name" in str(caught.value)


def test_a_comment_inside_a_block_is_still_a_comment():
    phase, = parse_nodes("phase p {\n    # a note\n    finish\n}\n")
    assert [child.name for child in phase.block] == ["finish"]


def test_a_content_body_is_not_parsed_as_nodes():
    http, = parse_nodes(
        'http {\n'
        '    content answer "/answer.txt" """\n'
        '        not a node\n'
        '    """\n'
        '}\n')
    assert [child.name for child in http.block] == ["content"]


# The milestone's reference script parses structurally.

@pytest.fixture(scope="module")
def reference_nodes():
    with open(_REFERENCE, encoding="utf-8") as handle:
        return parse_nodes(handle.read(), path=_REFERENCE)


def _phases(nodes):
    """Every phase node, at whatever depth a scope puts it.

    The node layer knows nothing of `with` beyond its shape — a name,
    arguments and a block, like every other node — so the reference
    script's phases are one block deeper than they used to be and
    otherwise unchanged. That is the claim these tests make.
    """
    found = []
    for node in nodes:
        if node.name == "phase":
            found.append(node)
        elif node.block is not None:
            found.extend(_phases(node.block))
    return found


def test_the_headers_and_the_scope_are_the_top_level_nodes(reference_nodes):
    assert [node.name for node in reference_nodes] == [
        "description", "platform", "machine", "entry", "timeout",
        "deadline", "with"]


def test_the_scope_names_its_head_and_holds_the_phases(reference_nodes):
    scope = reference_nodes[-1]
    assert [argument.value for argument in scope.arguments] == [
        "boot", "cdrom0"]
    assert [node.name for node in scope.block] == ["phase"] * 6


def test_every_phase_opens_a_block_of_statements(reference_nodes):
    phases = _phases(reference_nodes)
    assert [phase.arguments[0].value for phase in phases] == [
        "startup", "cd-boot", "partitioning", "formatting", "hd-boot",
        "shutdown"]
    for phase in phases:
        assert phase.block is not None


def test_the_branching_wait_holds_two_handlers(reference_nodes):
    cd_boot = next(node for node in _phases(reference_nodes)
                   if node.arguments[0].value == "cd-boot")
    wait = cd_boot.block[-1]
    assert wait.name == "wait"
    assert wait.arguments == ()
    assert [handler.name for handler in wait.block] == ["on", "on"]
    assert [handler.block[-1].arguments[0].value
            for handler in wait.block] == ["partitioning", "formatting"]


def test_phase_timing_modifiers_are_read(reference_nodes):
    formatting = next(node for node in _phases(reference_nodes)
                      if node.arguments[0].value == "formatting")
    assert formatting.modifiers["timeout"].value.value == "5m"
    assert formatting.modifiers["deadline"].value.value == "20m"


def test_the_machine_channel_reads_as_a_modifier(reference_nodes):
    shutdown = next(node for node in _phases(reference_nodes)
                    if node.arguments[0].value == "shutdown")
    wait = shutdown.block[1]
    assert wait.name == "wait"
    assert wait.arguments == ()
    assert wait.modifiers["machine"].value.value == "stopped"
    assert wait.modifiers["timeout"].value.value == "2m"
