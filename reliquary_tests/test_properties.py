# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause

import os
import shutil
import tempfile
import unittest
from reliquary import properties


class TestProperties(unittest.TestCase):
    def setUp(self):
        self.test_home = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_home)

    def test_get_unset(self):
        # Missing file
        self.assertIsNone(
            properties.get_property("missing", context=self.test_home))

    def test_set_get(self):
        properties.set_property("key1", "value1", context=self.test_home)
        self.assertEqual(
            properties.get_property("key1", context=self.test_home),
            "value1")

        # Persistence
        self.assertEqual(
            properties.list_properties(context=self.test_home),
            {"key1": "value1"})

    def test_unset(self):
        properties.set_property("key1", "value1", context=self.test_home)
        properties.unset_property("key1", context=self.test_home)
        self.assertIsNone(
            properties.get_property("key1", context=self.test_home))

    def test_malformed_json(self):
        path = properties._properties_path(context=self.test_home)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("{ invalid json")

        # Should return empty dict/None instead of crashing
        self.assertIsNone(properties.get_property("key1", context=self.test_home))
        self.assertEqual(properties.list_properties(context=self.test_home), {})

    def test_non_object_json_is_ignored(self):
        path = properties._properties_path(context=self.test_home)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write('["not", "a", "property", "map"]')

        self.assertIsNone(properties.get_property("key1", context=self.test_home))
        self.assertEqual(properties.list_properties(context=self.test_home), {})

    def test_jsonc_support(self):
        path = properties._properties_path(context=self.test_home)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write('{"key1": "value1", // comment\n "key2": "value2",}')

        self.assertEqual(
            properties.get_property("key1", context=self.test_home),
            "value1")
        self.assertEqual(
            properties.get_property("key2", context=self.test_home),
            "value2")


if __name__ == '__main__':
    unittest.main()
