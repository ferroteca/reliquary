# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""The shared static-conformance corpus (composed blueprint model).

Every fixture under ``fixtures/conformance/blueprint/{valid,invalid}/``
is run against two validators that must agree: reliquary's own parser
(``document.parse_document`` — the normative validator) and the published
JSON Schema (``reliquary/schemas/blueprint-schema-v1.json``). A valid
document parses and validates; an invalid document is rejected by both.
The parser side always runs; the schema side runs when ``jsonschema`` is
available (the schema ships in the package, so it validates even on an
installed artifact).
"""

import glob
import json
import os
import unittest
from importlib import resources

from reliquary import document, jsonc

try:
    import jsonschema
    _HAVE_JSONSCHEMA = True
except ImportError:
    _HAVE_JSONSCHEMA = False

_HERE = os.path.dirname(__file__)
_CORPUS = os.path.join(_HERE, "fixtures", "conformance", "blueprint")
_STATE_SCHEMA_DIR = os.path.join(
    os.path.dirname(_HERE), "planning", "design")
_HAVE_STATE_SCHEMA = os.path.isdir(_STATE_SCHEMA_DIR)


def _fixtures(verdict):
    return sorted(glob.glob(os.path.join(_CORPUS, verdict, "*.rlqb")))


def _load(path):
    with open(path, encoding="utf-8") as handle:
        return jsonc.load(handle)


def _stem(path):
    return os.path.splitext(os.path.basename(path))[0]


def _blueprint_schema():
    text = (resources.files("reliquary") / "schemas"
            / "blueprint-schema-v1.json").read_text(encoding="utf-8")
    return json.loads(text)


class BlueprintCorpusTests(unittest.TestCase):
    def test_valid_fixtures_parse(self):
        paths = _fixtures("valid")
        self.assertTrue(paths, "no valid blueprint fixtures found")
        for path in paths:
            with self.subTest(fixture=os.path.basename(path)):
                document.parse_document(_load(path), stem=_stem(path))

    def test_invalid_fixtures_are_rejected(self):
        paths = _fixtures("invalid")
        self.assertTrue(paths, "no invalid blueprint fixtures found")
        for path in paths:
            with self.subTest(fixture=os.path.basename(path)):
                with self.assertRaises((ValueError, KeyError, TypeError)):
                    document.parse_document(_load(path), stem=_stem(path))

    @unittest.skipUnless(_HAVE_JSONSCHEMA, "jsonschema is required")
    def test_valid_fixtures_match_the_schema(self):
        schema = _blueprint_schema()
        for path in _fixtures("valid"):
            with self.subTest(fixture=os.path.basename(path)):
                jsonschema.validate(_load(path), schema)

    @unittest.skipUnless(_HAVE_JSONSCHEMA, "jsonschema is required")
    def test_invalid_fixtures_fail_the_schema(self):
        schema = _blueprint_schema()
        for path in _fixtures("invalid"):
            with self.subTest(fixture=os.path.basename(path)):
                with self.assertRaises(jsonschema.ValidationError):
                    jsonschema.validate(_load(path), schema)


class MachineStateSchemaTests(unittest.TestCase):
    """A real materialized state validates against the state schema."""

    @unittest.skipUnless(
        _HAVE_JSONSCHEMA and _HAVE_STATE_SCHEMA,
        "jsonschema and the repo state schema are required")
    def test_materialized_state_matches_schema(self):
        import tempfile
        from reliquary import Context
        from reliquary.machines import create_machine, load_machine_state
        with open(os.path.join(_STATE_SCHEMA_DIR,
                               "machine-state.schema.json"),
                  encoding="utf-8") as handle:
            schema = jsonc.load(handle)
        with tempfile.TemporaryDirectory() as tmp:
            root = os.path.join(tmp, "proj")
            os.makedirs(root)
            with open(os.path.join(root, "state-bp.rlqb"), "w",
                      encoding="utf-8") as handle:
                handle.write('{"machines": [{"name": "state-bp", '
                             '"platform": "dos", '
                             '"drives": {"cdrom0": null}}]}')
            context = Context(home=os.path.join(tmp, "home"), assets=root)
            machine_id = create_machine("state-bp", context=context)
            state = load_machine_state(machine_id, context)
            jsonschema.validate(state, schema)
            # A running machine folds the live-VM identity into the same
            # document as a `vm` section — validate that shape too.
            running = dict(state, phase="running", vm={
                "port": 5555, "name": f"reliquary-{machine_id}",
                "uuid": "0" * 32, "pid": 4242})
            jsonschema.validate(running, schema)


if __name__ == "__main__":
    unittest.main()
