# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause

import unittest
from reliquary import jsonc
from reliquary.errors import StaticError


class TestJSONC(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(jsonc.loads('{"a": 1}'), {"a": 1})

    def test_line_comment(self):
        content = '{"a": 1 // comment\n}'
        self.assertEqual(jsonc.loads(content), {"a": 1})

    def test_block_comment(self):
        content = '{"a": /* comment */ 1}'
        self.assertEqual(jsonc.loads(content), {"a": 1})

    def test_trailing_comma_array(self):
        self.assertEqual(jsonc.loads('[1, 2,]'), [1, 2])

    def test_trailing_comma_object(self):
        self.assertEqual(jsonc.loads('{"a": 1,}'), {"a": 1})

    def test_string_protection(self):
        content = (
            '{"a": "//not a comment", '
            '"b": "/*not a block*/", "c": "comma,"}')
        expected = {
            "a": "//not a comment",
            "b": "/*not a block*/",
            "c": "comma,",
        }
        self.assertEqual(jsonc.loads(content), expected)

    def test_multiline_block_comment(self):
        content = '{"a": /* line 1\n line 2 */ 1}'
        self.assertEqual(jsonc.loads(content), {"a": 1})

    def test_multiline_block_comments_preserve_error_lines(self):
        content = '{\n/* first\nsecond */\n"missing":\n}\n'
        with self.assertRaises(StaticError) as caught:
            jsonc.loads(content)
        self.assertEqual(caught.exception.lineno, 5)

    def test_nested_trailing_comma(self):
        content = '{"a": [1,], "b": {"c": 2,},}'
        expected = {"a": [1], "b": {"c": 2}}
        self.assertEqual(jsonc.loads(content), expected)


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
        self.value = jsonc.loads(self.DOCUMENT, positions=True)
        self.spec = self.value[0]

    def test_the_value_is_the_same_value(self):
        self.assertEqual(self.value, jsonc.loads(self.DOCUMENT))

    def test_a_member_is_located_at_its_key(self):
        self.assertEqual(jsonc.position_of(self.spec, "name"), (5, 5))
        self.assertEqual(jsonc.position_of(self.spec, "drives"), (6, 5))

    def test_every_recorded_position_lands_on_its_own_key(self):
        """The general form, and the reason comments are blanked rather
        than removed: a recorded position indexes the *original* text,
        so the key has to be there when you look."""
        lines = self.DOCUMENT.split("\n")

        def check(node):
            positions = getattr(node, "positions", {})
            for key, (line, column) in positions.items():
                if isinstance(key, str):
                    self.assertEqual(
                        lines[line - 1][column - 1:column - 1 + len(key) + 2],
                        f'"{key}"', f"{key} is not at {line}:{column}")
                check(node[key])

        check(self.value)
        # And the document really does have a comment above a checked
        # key, or the assertion above proves nothing about comments.
        self.assertIn("//", lines[3])
        self.assertEqual(jsonc.position_of(self.spec, "name")[0], 5)

    def test_a_nested_member_is_located(self):
        drive = self.spec["drives"]["hdd0"]
        self.assertEqual(jsonc.position_of(drive, "bogus"), (7, 34))

    def test_an_array_element_is_located_at_its_own_start(self):
        self.assertEqual(jsonc.position_of(self.spec["boot"], 1), (9, 22))

    def test_a_container_is_located_at_its_bracket(self):
        self.assertEqual(jsonc.position(self.value), (1, 1))
        self.assertEqual(jsonc.position(self.spec), (2, 3))

    def test_positions_are_off_by_default(self):
        plain = jsonc.loads(self.DOCUMENT)
        self.assertIsNone(jsonc.position(plain))
        self.assertIsNone(jsonc.position_of(plain[0], "name"))
        self.assertIs(type(plain), list)
        self.assertIs(type(plain[0]), dict)

    def test_an_unlocatable_key_answers_none_rather_than_raising(self):
        self.assertIsNone(jsonc.position_of(self.spec, "absent"))
        self.assertIsNone(jsonc.position_of("not a container", "key"))

    def test_a_repeated_key_is_located_where_json_takes_it(self):
        """Last wins in both passes, or the caret would point at a value
        the document does not have."""
        value = jsonc.loads('{\n"a": 1,\n"a": 2\n}', positions=True)
        self.assertEqual(value["a"], 2)
        self.assertEqual(jsonc.position_of(value, "a"), (3, 1))

    def test_an_escaped_key_matches_the_key_json_produced(self):
        value = jsonc.loads('{\n  "a\\"b": 1\n}', positions=True)
        self.assertEqual(jsonc.position_of(value, 'a"b'), (2, 3))

    def test_a_trailing_comma_does_not_derail_the_scan(self):
        value = jsonc.loads('{\n  "a": [1,],\n  "b": 2,\n}', positions=True)
        self.assertEqual(jsonc.position_of(value, "b"), (3, 3))


if __name__ == '__main__':
    unittest.main()
