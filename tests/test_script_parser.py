# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for the typed layer: grammar, vocabulary, and signatures."""

import os

import pytest

import reliquary
from reliquary.script_nodes import ScriptParseError
from reliquary.script_parser import parse_script

# The reference script is a shipped builtin, resolved as package
# data so these tests run against an installed artifact too.
_REFERENCE = os.path.join(
    os.path.dirname(os.path.abspath(reliquary.__file__)),
    "codex", "scripts", "freedos-install.rlqs")

_HEAD = "platform dos\n"
_FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "fixtures")


# The milestone's reference script types end to end.

@pytest.fixture(scope="module")
def reference():
    with open(_REFERENCE, encoding="utf-8") as handle:
        return parse_script(handle.read(), path=_REFERENCE)


def _phase(script, name):
    return next(p for p in script.phases if p.name == name)


def test_headers_carry_their_values(reference):
    assert reference.platform == "dos"
    assert reference.machine == "stopped"
    assert reference.entry == "startup"
    assert reference.timeout == "30s"
    assert reference.deadline == "45m"
    assert reference.description.text == (
        "FreeDOS 1.4 plain install from LiveCD")


def test_the_phases_are_named_in_order(reference):
    assert [phase.name for phase in reference.phases] == [
        "startup", "cd-boot", "partitioning", "formatting", "hd-boot",
        "shutdown"]
    assert reference.statements == ()


def test_a_branching_wait_carries_its_on_handlers(reference):
    phase = _phase(reference, "cd-boot")
    wait = phase.statements[-1]
    assert wait.verb == "wait"
    assert wait.condition is None
    assert [handler.keyword for handler in wait.handlers] == ["on", "on"]
    assert [handler.condition.value.text
            for handler in wait.handlers] == [
        "Drive C: does not appear to be partitioned.",
        "Drive C: does not appear to be formatted."]
    assert [[s.verb for s in handler.statements]
            for handler in wait.handlers] == [["select", "goto"],
                                              ["select", "goto"]]


def test_phase_timing_modifiers_type_as_durations(reference):
    phase = _phase(reference, "formatting")
    assert phase.timeout == "5m"
    assert phase.deadline == "20m"


def test_the_machine_channel_becomes_a_condition(reference):
    wait = _phase(reference, "shutdown").statements[1]
    assert wait.condition.channel == "machine"
    assert wait.condition.kind == "state"
    assert wait.condition.value == "stopped"
    assert wait.timeout == "2m"


def test_a_bare_string_is_a_screen_condition(reference):
    wait = _phase(reference, "cd-boot").statements[0]
    assert wait.condition.channel == "screen"
    assert wait.condition.kind == "text"
    assert wait.condition.value.text == "Welcome to FreeDOS 1.4 (LiveCD)"


def test_insert_and_select_carry_their_typed_arguments(reference):
    insert = _phase(reference, "startup").statements[0]
    assert insert.arguments == ("cdrom0", ("media", "freedos-livecd"))
    select = next(s for s in _phase(reference, "formatting").statements
                  if s.verb == "select" and s.exclude)
    assert select.arguments[0].text == "Plain DOS system"
    assert select.exclude.text == "with sources"


# The vocabulary.

def test_a_keyword_is_a_plain_name_outside_node_position():
    # `enter` is a verb at the start of a line and a key name
    # after `press`; `insert` and `type` likewise.
    script = parse_script(
        _HEAD + "press enter\npress ctrl+alt+delete\n"
        "press insert\nset-boot hdd0 cdrom0\n")
    assert [s.verb for s in script.statements] == [
        "press", "press", "press", "set-boot"]
    assert [s.arguments for s in script.statements] == [
        ("enter",), ("ctrl+alt+delete",), ("insert",), ("hdd0", "cdrom0")]


def test_the_renamed_vocabulary_parses():
    script = parse_script(
        "platform dos\nentry go\n"
        "phase go {\n    goto next\n}\n"
        "phase next {\n    finish\n}\n")
    assert [p.name for p in script.phases] == ["go", "next"]
    assert script.phases[0].statements[0].verb == "goto"
    assert script.phases[1].statements[0].verb == "finish"


def test_a_reactive_phase_holds_always_handlers():
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
    assert phase.statements == ()
    assert [h.keyword for h in phase.handlers] == ["always", "always"]
    assert phase.handlers[0].condition.kind == "regex"
    assert phase.handlers[0].condition.value == "copied [0-9]+ files"
    assert phase.handlers[0].stable == "2s"


def test_property_declarations_type_their_kind_and_prompt():
    script = parse_script(
        _HEAD + 'property windows.user\n'
        'property secret windows.license-key prompt="License key"\n'
        'start\n')
    assert [(p.key, p.kind) for p in script.properties] == [
        ("windows.user", "text"), ("windows.license-key", "secret")]
    assert script.properties[1].prompt.text == "License key"


def test_an_unknown_property_kind_is_named():
    with pytest.raises(ScriptParseError) as caught:
        parse_script(_HEAD + "property txt some.key\nstart\n")
    assert "unknown property kind: 'txt'" in str(caught.value)


# The HTTP block and its content bodies.

def test_content_bodies_dedent_by_default():
    script = parse_script(
        _HEAD +
        "http {\n"
        "    content answer \"/answer.txt\" \"\"\"\n"
        "        one\n"
        "          two\n"
        "    \"\"\"\n"
        "}\n"
        "start\n")
    content = script.http.contents[0]
    assert content.name == "answer"
    assert content.path.text == "/answer.txt"
    assert content.indent == "dedent"
    assert content.body.text == "one\n  two\n"


def test_content_can_preserve_literal_indentation():
    script = parse_script(
        _HEAD +
        "http {\n"
        "    content answer \"/answer.txt\" indent=literal \"\"\"\n"
        "        one\n"
        "    \"\"\"\n"
        "}\n"
        "start\n")
    assert script.http.contents[0].body.text == "        one\n"


def test_content_bodies_record_property_references():
    script = parse_script(
        _HEAD +
        "property identity.name\n"
        "http {\n"
        "    content answer \"/answer.txt\" \"\"\"\n"
        "        name=${identity.name}\n"
        "        literal=\\${identity.name}\n"
        "    \"\"\"\n"
        "}\n"
        "start\n")
    body = script.http.contents[0].body
    assert body.keys == ("identity.name",)
    assert body.spelling == (
        "name=${identity.name}\nliteral=${identity.name}\n")


def test_content_can_load_from_relative_file():
    script_path = os.path.join(_FIXTURES, "script.rlqs")
    script = parse_script(
        _HEAD +
        "property identity.name\n"
        "http {\n"
        "    content answer \"/answer.txt\" "
        "from=\"http-answer.txt\"\n"
        "}\n"
        "start\n",
        path=script_path)
    content = script.http.contents[0]
    assert content.source_path == os.path.join(_FIXTURES,
                                               "http-answer.txt")
    assert content.body.keys == ("identity.name",)
    assert content.body.spelling == (
        "name=${identity.name}\nliteral=${identity.name}\n")


def test_file_content_rejects_missing_or_dynamic_source_paths():
    with pytest.raises(ScriptParseError) as caught:
        parse_script(
            _HEAD + 'http {\n    content answer "/answer.txt" '
            'from="missing.txt"\n}\nstart\n',
            path=os.path.join(_FIXTURES, "script.rlqs"))
    assert "content source file not found" in str(caught.value)
    with pytest.raises(ScriptParseError) as caught:
        parse_script(
            _HEAD + 'http {\n    content answer "/answer.txt" '
            'from="${source.path}"\n}\nstart\n')
    assert "from path may not contain property references" in str(
        caught.value)
    with pytest.raises(ScriptParseError) as caught:
        parse_script(
            _HEAD + 'http {\n    content answer "/answer.txt" '
            'from="/tmp/answer.txt"\n}\nstart\n')
    assert "from path must be relative to the script file" in str(
        caught.value)
    with pytest.raises(ScriptParseError) as caught:
        parse_script(
            _HEAD + 'http {\n    content answer "/answer.txt" '
            'from="../answer.txt"\n}\nstart\n')
    assert "from path may not contain . or .. segments" in str(caught.value)


def test_file_content_has_no_heredoc_indentation_modifiers():
    with pytest.raises(ScriptParseError) as caught:
        parse_script(
            _HEAD + 'http {\n    content answer "/answer.txt" '
            'indent=literal from="http-answer.txt"\n}\nstart\n',
            path=os.path.join(_FIXTURES, "script.rlqs"))
    assert "indent applies only to triple-quoted content bodies" in str(
        caught.value)
    with pytest.raises(ScriptParseError) as caught:
        parse_script(
            _HEAD + 'http {\n    content answer "/answer.txt" '
            'from="http-answer.txt" """\n        one\n    """\n'
            '}\nstart\n',
            path=os.path.join(_FIXTURES, "script.rlqs"))
    assert "may not combine from= with a triple-quoted body" in str(
        caught.value)


def test_http_port_modifiers_are_typed():
    script = parse_script(
        _HEAD +
        "http port-min=8000 port-max=8000 {\n"
        "    content answer \"/answer.txt\" \"\"\"\n"
        "        one\n"
        "    \"\"\"\n"
        "}\n"
        "start\n")
    assert script.http.port_min == "8000"
    assert script.http.port_max == "8000"


def test_http_start_and_stop_are_statements():
    script = parse_script(
        _HEAD +
        "http {\n"
        "    content answer \"/answer.txt\" \"\"\"\n"
        "        one\n"
        "    \"\"\"\n"
        "}\n"
        "http start answer\n"
        "enter \"${rlq.http.url}/answer.txt\"\n"
        "http stop\n")
    assert [s.verb for s in script.statements] == ["http", "enter", "http"]
    assert [s.arguments for s in script.statements
            if s.verb == "http"] == [("start", "answer"), ("stop",)]


def test_http_start_can_redefine_inline_content():
    script = parse_script(
        _HEAD +
        "http {\n"
        "    content answer \"/answer.txt\" \"\"\"\n"
        "        one\n"
        "    \"\"\"\n"
        "}\n"
        "http start {\n"
        "    content answer \"/answer.txt\" \"\"\"\n"
        "        two\n"
        "    \"\"\"\n"
        "}\n")
    start = script.statements[0]
    assert start.arguments == ("start",)
    assert start.contents[0].name == "answer"
    assert start.contents[0].body.text == "two\n"


def test_content_rejects_unknown_modifiers():
    with pytest.raises(ScriptParseError) as caught:
        parse_script(
            _HEAD +
            "http {\n"
            "    content answer \"/answer.txt\" mode=raw \"\"\"\n"
            "        one\n"
            "    \"\"\"\n"
            "}\n"
            "start\n")
    assert "content does not accept the modifier 'mode'" in str(caught.value)


# Node signatures.

def test_a_node_rejects_a_modifier_outside_its_signature():
    with pytest.raises(ScriptParseError) as caught:
        parse_script(_HEAD + 'enter "x" timeout=5m\n')
    assert "enter does not accept the modifier 'timeout'" in str(
        caught.value)
    # The listing is what the node *does* accept: `enter` is a
    # guest-input verb, so it takes pacing and nothing else.
    assert "accepts: pacing" in str(caught.value)


def test_a_node_accepting_no_modifier_says_so():
    with pytest.raises(ScriptParseError) as caught:
        parse_script(_HEAD + 'eject floppy0 timeout=5m\n')
    assert "accepts: none" in str(caught.value)


def test_a_wait_takes_the_timing_modifiers_that_are_its_own():
    # Only the timing set is a wait's own; every other modifier
    # names a channel, and V7 owns that diagnostic.
    with pytest.raises(ScriptParseError) as caught:
        parse_script(_HEAD + 'wait "x" exclude="y"\n')
    assert "unknown observation channel: exclude" in str(caught.value)


def test_a_timing_modifier_requires_a_duration():
    with pytest.raises(ScriptParseError) as caught:
        parse_script(_HEAD + 'wait "x" timeout=soon\n')
    assert "timeout must be a duration" in str(caught.value)


def test_select_accepts_only_exclude():
    script = parse_script(_HEAD + 'select "a" exclude="b"\n')
    assert script.statements[0].exclude.text == "b"
    with pytest.raises(ScriptParseError):
        parse_script(_HEAD + 'select "a" stable=2s\n')


def test_a_repeated_header_is_rejected():
    with pytest.raises(ScriptParseError) as caught:
        parse_script("platform dos\nplatform win9x\nstart\n")
    assert "platform may appear only once" in str(caught.value)


# The lexer's authored messages survive the lark layer.

def test_modifier_spacing_keeps_its_message_in_any_context():
    for source in (_HEAD + 'wait "x" timeout = 5m\n',
                   _HEAD + "phase p timeout = 5m {\n}\n",
                   _HEAD + 'select "a" exclude = "b"\n'):
        with pytest.raises(ScriptParseError) as caught:
            parse_script(source)
        assert "modifiers are written name=value" in str(caught.value), source


def test_a_duration_without_a_unit_keeps_its_message():
    for source in (_HEAD + 'wait "x" timeout=30\n',
                   _HEAD + "deadline 45\n"):
        with pytest.raises(ScriptParseError) as caught:
            parse_script(source)
        assert "durations carry a unit" in str(caught.value), source


def test_an_unterminated_string_keeps_its_message():
    for source in (_HEAD + 'wait "unclosed\n',
                   _HEAD + 'type "unclosed\n'):
        with pytest.raises(ScriptParseError) as caught:
            parse_script(source)
        assert "unterminated string" in str(caught.value), source


def test_a_syntax_error_reports_a_line_and_renders_a_caret():
    with pytest.raises(ScriptParseError) as caught:
        parse_script(_HEAD + "goto\n", path="x.rlqs")
    assert caught.value.line == 2
    assert "x.rlqs:2:" in str(caught.value)
    assert "^" in str(caught.value)


# ``set <key> "<value>"`` — the script's channel to the host.

def test_a_set_carries_its_key_and_value():
    script = parse_script('platform dos\nset result "PASS"\n')
    statement = script.statements[0]
    assert statement.verb == "set"
    assert statement.arguments[0] == "result"
    assert statement.arguments[1].text == "PASS"


def test_a_value_may_interpolate_a_property():
    script = parse_script(
        'platform dos\nproperty tag\nset build "${tag}"\n')
    assert script.statements[0].arguments[1].interpolated


def test_set_is_distinct_from_set_boot():
    script = parse_script(
        'platform dos\nmachine stopped\nset-boot hdd0\n'
        'set stage "booted"\n')
    assert [s.verb for s in script.statements] == ["set-boot", "set"]


def test_a_bare_value_is_not_a_set():
    # The value is text, so it is written as a string: a bare
    # word would be indistinguishable from a second key.
    with pytest.raises(ScriptParseError):
        parse_script("platform dos\nset result PASS\n")


def test_set_takes_no_modifiers():
    with pytest.raises(ScriptParseError) as caught:
        parse_script('platform dos\nset result "x" timeout=5s\n')
    assert "set does not accept" in str(caught.value)


# The milestone-one spellings are gone, not bridged.

def test_the_old_surface_no_longer_parses():
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
        try:
            parse_script(source)
        except ScriptParseError:
            continue
        raise AssertionError(f"the {label} spelling still parses")
