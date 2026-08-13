# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for authoring the files a user owns.

Composed-blueprint parsing is covered by test_document.py; this
module covers the ``new_blueprint`` / ``add_media`` /
``delete_blueprint`` / ``delete_script`` file surface — and in
particular the refusal both removals share, each answering from its
own place: a blueprint while machines of it exist, a script while
blueprints reference it.
"""

import json
import os
import tempfile
import unittest

from reliquary.authoring import (delete_blueprint, delete_script,
                                 new_blueprint)
from reliquary.document import parse_document
from reliquary.errors import PreflightError


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
        with self.assertRaises(PreflightError):
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
        with self.assertRaises(PreflightError) as caught:
            delete_blueprint("missing", context=self.home)
        self.assertIn("blueprint not found", str(caught.exception))

    def test_refuses_while_machines_exist(self):
        new_blueprint("plain", context=self.home)
        machine_dir = os.path.join(
            self.home, "cache", "machines", "plain-0")
        os.makedirs(machine_dir)
        with open(os.path.join(machine_dir, "machine.json"),
                  "w", encoding="utf-8") as handle:
            json.dump({"id": "plain-0", "blueprint": "plain",
                       "phase": "ready"}, handle)
        with self.assertRaises(PreflightError) as caught:
            delete_blueprint("plain", context=self.home)
        message = str(caught.exception)
        self.assertIn("still has 1 machine(s)", message)
        self.assertIn("plain-0", message)
        self.assertTrue(os.path.exists(
            os.path.join(self.home, "blueprints", "plain.rlqb")))

    def test_does_not_delete_codex(self):
        with self.assertRaises(PreflightError):
            delete_blueprint("freedos", context=self.home)


class ScriptAuthoringTestCase(unittest.TestCase):
    def setUp(self):
        self.workdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.workdir.cleanup)
        self.home = self.workdir.name

    def _write_script(self, name, content="description \"test\"\nplatform dos\n"):
        path = os.path.join(self.home, "scripts", f"{name}.rlqs")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        return path

    def _write_blueprint(self, name, scripts=None):
        from reliquary.home import blueprints_dir
        path = os.path.join(blueprints_dir(self.home), f"{name}.rlqb")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = [
            {
                "type": "machine",
                "name": name,
                "platform": "dos",
                "scripts": scripts or {}
            }
        ]
        import json
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
        return path

class DeleteScriptTests(ScriptAuthoringTestCase):
    def test_deletes_rlqs(self):
        path = self._write_script("test-script")
        removed = delete_script("test-script", context=self.home)
        self.assertEqual(removed, path)
        self.assertFalse(os.path.exists(path))

    def test_missing_raises(self):
        with self.assertRaises(PreflightError) as caught:
            delete_script("missing", context=self.home)
        self.assertIn("script not found", str(caught.exception).lower())
        self.assertEqual(caught.exception.rule_id, "script.unknown")

    def test_refuses_while_blueprints_refer_to_it(self):
        self._write_script("useful")
        self._write_blueprint("my-machine", scripts={"run": "useful"})
        
        with self.assertRaises(PreflightError) as caught:
            delete_script("useful", context=self.home)
        
        message = str(caught.exception)
        self.assertIn("still has 1 blueprint(s)", message)
        self.assertIn("my-machine", message)
        self.assertEqual(caught.exception.rule_id, "script.has-blueprints")
        self.assertTrue(os.path.exists(os.path.join(self.home, "scripts", "useful.rlqs")))

    def test_does_not_delete_codex(self):
        # freedos-install is in the codex
        with self.assertRaises(PreflightError):
            delete_script("freedos-install", context=self.home)


if __name__ == "__main__":
    unittest.main()
