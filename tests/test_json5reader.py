# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The JSON5 document reader (D102): the grammar, and source positions."""

import pytest

from reliquary import json5reader
from reliquary.errors import StaticError


# The published grammar, as `.rlqb` documents use it.

def test_basic():
    assert json5reader.loads('{"a": 1}') == {"a": 1}


def test_line_comment():
    assert json5reader.loads('{"a": 1 // comment\n}') == {"a": 1}


def test_block_comment():
    assert json5reader.loads('{"a": /* comment */ 1}') == {"a": 1}


def test_trailing_comma_array():
    assert json5reader.loads('[1, 2,]') == [1, 2]


def test_trailing_comma_object():
    assert json5reader.loads('{"a": 1,}') == {"a": 1}


def test_string_protection():
    content = ('{"a": "//not a comment", '
               '"b": "/*not a block*/", "c": "comma,"}')
    assert json5reader.loads(content) == {
        "a": "//not a comment",
        "b": "/*not a block*/",
        "c": "comma,",
    }


def test_single_quoted_string_hides_comment_markers():
    content = "{a: '//not a comment', b: '/*not a block*/'}"
    assert json5reader.loads(content) == {
        "a": "//not a comment", "b": "/*not a block*/"}


def test_multiline_block_comment():
    assert json5reader.loads('{"a": /* line 1\n line 2 */ 1}') == {"a": 1}


def test_multiline_block_comments_preserve_error_lines():
    with pytest.raises(StaticError) as caught:
        json5reader.loads('{\n/* first\nsecond */\n"missing":\n}\n')
    assert caught.value.lineno == 5


def test_nested_trailing_comma():
    assert json5reader.loads('{"a": [1,], "b": {"c": 2,},}') == {
        "a": [1], "b": {"c": 2}}


def test_unquoted_keys():
    assert json5reader.loads("{name: 'box', cpus: 1}") == {
        "name": "box", "cpus": 1}


def test_single_quoted_strings():
    assert json5reader.loads("{'a': 'x'}") == {"a": "x"}


def test_hex_and_signed_and_bare_decimal():
    assert json5reader.loads("{a: 0x10, b: +1, c: .5, d: 5.}") == {
        "a": 16, "b": 1, "c": 0.5, "d": 5.0}


def test_multiline_string_continuation():
    assert json5reader.loads('{"a": "line\\\nbreak"}') == {"a": "linebreak"}


def test_nan_is_refused():
    with pytest.raises(StaticError) as caught:
        json5reader.loads("{a: NaN}")
    assert "NaN" in str(caught.value)
    assert "ordinary JSON" in str(caught.value)


def test_infinity_is_refused():
    with pytest.raises(StaticError) as caught:
        json5reader.loads("{a: Infinity}")
    assert "Infinity" in str(caught.value)


def test_negative_infinity_is_refused():
    with pytest.raises(StaticError) as caught:
        json5reader.loads("{a: -Infinity}")
    assert "-Infinity" in str(caught.value)


# ``positions=True`` records where each value was written.
#
# The positions are what lets a blueprint diagnostic cite a line and
# column (D70). They are asked for rather than always paid for, so the
# default is asserted to be unchanged in both what it returns and what
# it carries.

DOCUMENT = (
    '[\n'
    '  {\n'
    '    "type": "machine",\n'
    '    // a comment, which must shift nothing below it\n'
    '    "name": "box",\n'
    '    "drives": {\n'
    '      "hdd0": { "media": "disk", "bogus": 1 }\n'
    '    },\n'
    '    "boot": ["hdd0", "cdrom0"]\n'
    '  }\n'
    ']\n')


@pytest.fixture
def located():
    return json5reader.loads(DOCUMENT, positions=True)


@pytest.fixture
def spec(located):
    return located[0]


def test_the_value_is_the_same_value(located):
    assert located == json5reader.loads(DOCUMENT)


def test_a_member_is_located_at_its_key(spec):
    assert json5reader.position_of(spec, "name") == (5, 5)
    assert json5reader.position_of(spec, "drives") == (6, 5)


def test_every_recorded_position_lands_on_its_own_key(located, spec):
    """The general form, and the reason comments are blanked rather
    than removed: a recorded position indexes the *original* text,
    so the key has to be there when you look."""
    lines = DOCUMENT.split("\n")

    def check(node):
        positions = getattr(node, "positions", {})
        for key, (line, column) in positions.items():
            if isinstance(key, str):
                snippet = lines[line - 1][column - 1:]
                assert (snippet.startswith(f'"{key}"')
                        or snippet.startswith(f"'{key}'")
                        or snippet.startswith(key)), (
                    f"{key} is not at {line}:{column}: {snippet!r}")
            check(node[key])

    check(located)
    # And the document really does have a comment above a checked
    # key, or the assertion above proves nothing about comments.
    assert "//" in lines[3]
    assert json5reader.position_of(spec, "name")[0] == 5


def test_a_nested_member_is_located(spec):
    drive = spec["drives"]["hdd0"]
    assert json5reader.position_of(drive, "bogus") == (7, 34)


def test_an_array_element_is_located_at_its_own_start(spec):
    assert json5reader.position_of(spec["boot"], 1) == (9, 22)


def test_a_container_is_located_at_its_bracket(located, spec):
    assert json5reader.position(located) == (1, 1)
    assert json5reader.position(spec) == (2, 3)


def test_positions_are_off_by_default():
    plain = json5reader.loads(DOCUMENT)
    assert json5reader.position(plain) is None
    assert json5reader.position_of(plain[0], "name") is None
    assert type(plain) is list
    assert type(plain[0]) is dict


def test_an_unlocatable_key_answers_none_rather_than_raising(spec):
    assert json5reader.position_of(spec, "absent") is None
    assert json5reader.position_of("not a container", "key") is None


def test_a_repeated_key_is_located_where_json_takes_it():
    """Last wins in both passes, or the caret would point at a value
    the document does not have."""
    value = json5reader.loads('{\n"a": 1,\n"a": 2\n}', positions=True)
    assert value["a"] == 2
    assert json5reader.position_of(value, "a") == (3, 1)


def test_an_escaped_key_matches_the_key_json_produced():
    value = json5reader.loads('{\n  "a\\"b": 1\n}', positions=True)
    assert json5reader.position_of(value, 'a"b') == (2, 3)


def test_a_trailing_comma_does_not_derail_the_scan():
    value = json5reader.loads('{\n  "a": [1,],\n  "b": 2,\n}',
                              positions=True)
    assert json5reader.position_of(value, "b") == (3, 3)


def test_an_unquoted_key_is_located():
    source = '{\n  name: "box",\n}'
    value = json5reader.loads(source, positions=True)
    assert json5reader.position_of(value, "name") == (2, 3)
    lines = source.split("\n")
    line, column = json5reader.position_of(value, "name")
    assert lines[line - 1][column - 1:column - 1 + 4] == "name"
