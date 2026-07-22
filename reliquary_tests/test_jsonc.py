# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause

import json
import unittest
from reliquary import jsonc


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
        with self.assertRaises(json.JSONDecodeError) as caught:
            jsonc.loads(content)
        self.assertEqual(caught.exception.lineno, 5)

    def test_nested_trailing_comma(self):
        content = '{"a": [1,], "b": {"c": 2,},}'
        expected = {"a": [1], "b": {"c": 2}}
        self.assertEqual(jsonc.loads(content), expected)


if __name__ == '__main__':
    unittest.main()
