# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Tests for the blueprint file-authoring conveniences.

Composed-blueprint parsing is covered by test_document.py; this module
covers the ``new_blueprint`` / ``delete_blueprint`` file surface.
"""

import json
import os
import tempfile
import unittest

from reliquary.blueprint import delete_blueprint, new_blueprint
from reliquary.document import parse_document


class BlueprintFileTestCase(unittest.TestCase):
    def setUp(self):
        self.workdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.workdir.cleanup)
        self.home = self.workdir.name


class NewBlueprintTests(BlueprintFileTestCase):
    def test_scaffolds_a_composed_blueprint(self):
        path = new_blueprint("test-bp", context=self.home)
        self.assertTrue(os.path.exists(path))
        self.assertTrue(path.endswith(".rlqb"))
        with open(path, encoding="utf-8") as handle:
            content = handle.read()
        self.assertIn("// Machine blueprint for test-bp", content)
        data = json.loads(
            "\n".join(line for line in content.splitlines()
                      if not line.strip().startswith("//")))
        self.assertNotIn("version", data)
        # The scaffold parses under the composed model with the given name.
        doc = parse_document(data, stem="test-bp")
        self.assertIn("test-bp", doc.machines)
        self.assertEqual(doc.machines["test-bp"].platform, "dos")

    def test_already_exists_raises(self):
        new_blueprint("test-bp", context=self.home)
        with self.assertRaises(FileExistsError):
            new_blueprint("test-bp", context=self.home)


class DeleteBlueprintTests(BlueprintFileTestCase):
    def test_deletes_rlqb(self):
        path = new_blueprint("test-bp", context=self.home)
        removed = delete_blueprint("test-bp", context=self.home)
        self.assertEqual(removed, path)
        self.assertFalse(os.path.exists(path))

    def test_deletes_legacy_json(self):
        path = os.path.join(self.home, "blueprints", "legacy.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("{}\n")
        removed = delete_blueprint("legacy", context=self.home)
        self.assertEqual(removed, path)
        self.assertFalse(os.path.exists(path))

    def test_missing_raises(self):
        with self.assertRaises(FileNotFoundError) as caught:
            delete_blueprint("missing", context=self.home)
        self.assertIn("blueprint not found", str(caught.exception))

    def test_refuses_while_machines_exist(self):
        new_blueprint("plain", context=self.home)
        machine_dir = os.path.join(
            self.home, "cache", "machines", "plain-0")
        os.makedirs(machine_dir)
        with open(os.path.join(machine_dir, "reliquary-machine.json"),
                  "w", encoding="utf-8") as handle:
            json.dump({"id": "plain-0", "blueprint": "plain",
                       "phase": "ready"}, handle)
        with self.assertRaises(RuntimeError) as caught:
            delete_blueprint("plain", context=self.home)
        message = str(caught.exception)
        self.assertIn("still has 1 machine(s)", message)
        self.assertIn("plain-0", message)
        self.assertTrue(os.path.exists(
            os.path.join(self.home, "blueprints", "plain.rlqb")))

    def test_does_not_delete_codex(self):
        with self.assertRaises(FileNotFoundError):
            delete_blueprint("freedos-1.4-plain", context=self.home)


if __name__ == "__main__":
    unittest.main()
