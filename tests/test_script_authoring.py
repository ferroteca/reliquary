# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for the script file-authoring conveniences.
"""

import os
import tempfile
import unittest

from reliquary.script import delete_script
from reliquary.errors import PreflightError
from reliquary.blueprint import new_blueprint

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
