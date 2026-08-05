# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
import unittest
from reliquary import json5reader
from reliquary.errors import StaticError


class TestJSON5(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(json5reader.loads('{"a": 1}'), {"a": 1})

    def test_line_comment(self):
        content = '{"a": 1 // comment\n}'
        self.assertEqual(json5reader.loads(content), {"a": 1})

    def test_block_comment(self):
        content = '{"a": /* comment */ 1}'
        self.assertEqual(json5reader.loads(content), {"a": 1})

    def test_trailing_comma_array(self):
        self.assertEqual(json5reader.loads('[1, 2,]'), [1, 2])

    def test_trailing_comma_object(self):
        self.assertEqual(json5reader.loads('{"a": 1,}'), {"a": 1})

    def test_string_protection(self):
        content = (
            '{"a": "//not a comment", '
            '"b": "/*not a block*/", "c": "comma,"}')
        expected = {
            "a": "//not a comment",
            "b": "/*not a block*/",
            "c": "comma,",
        }
        self.assertEqual(json5reader.loads(content), expected)

    def test_single_quoted_string_hides_comment_markers(self):
        content = "{a: '//not a comment', b: '/*not a block*/'}"
        self.assertEqual(
            json5reader.loads(content),
            {"a": "//not a comment", "b": "/*not a block*/"})

    def test_multiline_block_comment(self):
        content = '{"a": /* line 1\n line 2 */ 1}'
        self.assertEqual(json5reader.loads(content), {"a": 1})

    def test_multiline_block_comments_preserve_error_lines(self):
        content = '{\n/* first\nsecond */\n"missing":\n}\n'
        with self.assertRaises(StaticError) as caught:
            json5reader.loads(content)
        self.assertEqual(caught.exception.lineno, 5)

    def test_nested_trailing_comma(self):
        content = '{"a": [1,], "b": {"c": 2,},}'
        expected = {"a": [1], "b": {"c": 2}}
        self.assertEqual(json5reader.loads(content), expected)

    def test_unquoted_keys(self):
        self.assertEqual(json5reader.loads("{name: 'box', cpus: 1}"),
                         {"name": "box", "cpus": 1})

    def test_single_quoted_strings(self):
        self.assertEqual(json5reader.loads("{'a': 'x'}"), {"a": "x"})

    def test_hex_and_signed_and_bare_decimal(self):
        self.assertEqual(
            json5reader.loads("{a: 0x10, b: +1, c: .5, d: 5.}"),
            {"a": 16, "b": 1, "c": 0.5, "d": 5.0})

    def test_multiline_string_continuation(self):
        self.assertEqual(
            json5reader.loads('{"a": "line\\\nbreak"}'),
            {"a": "linebreak"})

    def test_nan_is_refused(self):
        with self.assertRaises(StaticError) as caught:
            json5reader.loads("{a: NaN}")
        self.assertIn("NaN", str(caught.exception))
        self.assertIn("ordinary JSON", str(caught.exception))

    def test_infinity_is_refused(self):
        with self.assertRaises(StaticError) as caught:
            json5reader.loads("{a: Infinity}")
        self.assertIn("Infinity", str(caught.exception))

    def test_negative_infinity_is_refused(self):
        with self.assertRaises(StaticError) as caught:
            json5reader.loads("{a: -Infinity}")
        self.assertIn("-Infinity", str(caught.exception))


class PositionTests(unittest.TestCase):
    """``positions=True`` records where each value was written.

    The positions are what lets a blueprint diagnostic cite a line and
    column (D70). They are asked for rather than always paid for, so
    the default is asserted to be unchanged in both what it returns and
    what it carries.
    """

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

    def setUp(self):
        self.value = json5reader.loads(self.DOCUMENT, positions=True)
        self.spec = self.value[0]

    def test_the_value_is_the_same_value(self):
        self.assertEqual(self.value, json5reader.loads(self.DOCUMENT))

    def test_a_member_is_located_at_its_key(self):
        self.assertEqual(json5reader.position_of(self.spec, "name"), (5, 5))
        self.assertEqual(json5reader.position_of(self.spec, "drives"), (6, 5))

    def test_every_recorded_position_lands_on_its_own_key(self):
        """The general form, and the reason comments are blanked rather
        than removed: a recorded position indexes the *original* text,
        so the key has to be there when you look."""
        lines = self.DOCUMENT.split("\n")

        def check(node):
            positions = getattr(node, "positions", {})
            for key, (line, column) in positions.items():
                if isinstance(key, str):
                    snippet = lines[line - 1][column - 1:]
                    self.assertTrue(
                        snippet.startswith(f'"{key}"')
                        or snippet.startswith(f"'{key}'")
                        or snippet.startswith(key),
                        f"{key} is not at {line}:{column}: {snippet!r}")
                check(node[key])

        check(self.value)
        # And the document really does have a comment above a checked
        # key, or the assertion above proves nothing about comments.
        self.assertIn("//", lines[3])
        self.assertEqual(json5reader.position_of(self.spec, "name")[0], 5)

    def test_a_nested_member_is_located(self):
        drive = self.spec["drives"]["hdd0"]
        self.assertEqual(json5reader.position_of(drive, "bogus"), (7, 34))

    def test_an_array_element_is_located_at_its_own_start(self):
        self.assertEqual(json5reader.position_of(self.spec["boot"], 1), (9, 22))

    def test_a_container_is_located_at_its_bracket(self):
        self.assertEqual(json5reader.position(self.value), (1, 1))
        self.assertEqual(json5reader.position(self.spec), (2, 3))

    def test_positions_are_off_by_default(self):
        plain = json5reader.loads(self.DOCUMENT)
        self.assertIsNone(json5reader.position(plain))
        self.assertIsNone(json5reader.position_of(plain[0], "name"))
        self.assertIs(type(plain), list)
        self.assertIs(type(plain[0]), dict)

    def test_an_unlocatable_key_answers_none_rather_than_raising(self):
        self.assertIsNone(json5reader.position_of(self.spec, "absent"))
        self.assertIsNone(json5reader.position_of("not a container", "key"))

    def test_a_repeated_key_is_located_where_json_takes_it(self):
        """Last wins in both passes, or the caret would point at a value
        the document does not have."""
        value = json5reader.loads('{\n"a": 1,\n"a": 2\n}', positions=True)
        self.assertEqual(value["a"], 2)
        self.assertEqual(json5reader.position_of(value, "a"), (3, 1))

    def test_an_escaped_key_matches_the_key_json_produced(self):
        value = json5reader.loads('{\n  "a\\"b": 1\n}', positions=True)
        self.assertEqual(json5reader.position_of(value, 'a"b'), (2, 3))

    def test_a_trailing_comma_does_not_derail_the_scan(self):
        value = json5reader.loads('{\n  "a": [1,],\n  "b": 2,\n}', positions=True)
        self.assertEqual(json5reader.position_of(value, "b"), (3, 3))

    def test_an_unquoted_key_is_located(self):
        value = json5reader.loads('{\n  name: "box",\n}', positions=True)
        self.assertEqual(json5reader.position_of(value, "name"), (2, 3))
        lines = '{\n  name: "box",\n}'.split("\n")
        line, column = json5reader.position_of(value, "name")
        self.assertEqual(
            lines[line - 1][column - 1:column - 1 + 4], "name")


if __name__ == '__main__':
    unittest.main()
