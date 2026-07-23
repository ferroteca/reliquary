# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""The shared static-conformance corpus (ROADMAP milestone 6, del. 6).

Every fixture under ``fixtures/conformance/<kind>/{valid,invalid}/`` is
run against two validators that must agree: reliquary's own parser (the
normative validator) and the authored JSON Schema. A valid document
parses and validates; an invalid document is rejected by both. The
parser side always runs (parser and fixtures are packaged); the schema
side runs only when ``jsonschema`` and the repo's ``planning/design``
schemas are both available — an installed artifact ships neither.
"""

import glob
import os
import unittest

from reliquary import jsonc
from reliquary.blueprint import parse_blueprint
from reliquary.media import parse_definition

try:
    import jsonschema
    _HAVE_JSONSCHEMA = True
except ImportError:
    _HAVE_JSONSCHEMA = False

_HERE = os.path.dirname(__file__)
_CORPUS = os.path.join(_HERE, "fixtures", "conformance")
_SCHEMA_DIR = os.path.join(
    os.path.dirname(_HERE), "planning", "design")
_HAVE_SCHEMAS = os.path.isdir(_SCHEMA_DIR)


def _fixtures(kind, verdict, extension):
    pattern = os.path.join(_CORPUS, kind, verdict, f"*{extension}")
    return sorted(glob.glob(pattern))


def _load(path):
    with open(path, encoding="utf-8") as handle:
        return jsonc.load(handle)


def _load_schema(name):
    with open(os.path.join(_SCHEMA_DIR, name), encoding="utf-8") as handle:
        return jsonc.load(handle)


class _CorpusCase(unittest.TestCase):
    kind = extension = schema_name = None

    @staticmethod
    def _parse(document):
        raise NotImplementedError

    def test_valid_fixtures_parse(self):
        paths = _fixtures(self.kind, "valid", self.extension)
        self.assertTrue(paths, f"no valid {self.kind} fixtures found")
        for path in paths:
            with self.subTest(fixture=os.path.basename(path)):
                self._parse(_load(path))

    def test_invalid_fixtures_are_rejected(self):
        paths = _fixtures(self.kind, "invalid", self.extension)
        self.assertTrue(paths, f"no invalid {self.kind} fixtures found")
        for path in paths:
            with self.subTest(fixture=os.path.basename(path)):
                with self.assertRaises((ValueError, KeyError, TypeError)):
                    self._parse(_load(path))

    @unittest.skipUnless(
        _HAVE_JSONSCHEMA and _HAVE_SCHEMAS,
        "jsonschema and the repo schemas are required")
    def test_valid_fixtures_match_the_schema(self):
        schema = _load_schema(self.schema_name)
        for path in _fixtures(self.kind, "valid", self.extension):
            with self.subTest(fixture=os.path.basename(path)):
                jsonschema.validate(_load(path), schema)

    @unittest.skipUnless(
        _HAVE_JSONSCHEMA and _HAVE_SCHEMAS,
        "jsonschema and the repo schemas are required")
    def test_invalid_fixtures_fail_the_schema(self):
        schema = _load_schema(self.schema_name)
        for path in _fixtures(self.kind, "invalid", self.extension):
            with self.subTest(fixture=os.path.basename(path)):
                with self.assertRaises(jsonschema.ValidationError):
                    jsonschema.validate(_load(path), schema)


class BlueprintCorpusTests(_CorpusCase):
    kind = "blueprint"
    extension = ".rlqb"
    schema_name = "machine-blueprint.schema.json"

    @staticmethod
    def _parse(document):
        # Valid fixtures carry no media/base drives, so parsing needs no
        # asset source or media catalog.
        return parse_blueprint(document)


class MediaCorpusTests(_CorpusCase):
    kind = "media"
    extension = ".rlqm"
    schema_name = "media-definition.schema.json"

    @staticmethod
    def _parse(document):
        return parse_definition(document)


class MachineStateSchemaTests(unittest.TestCase):
    """A real materialized state validates against the state schema."""

    @unittest.skipUnless(
        _HAVE_JSONSCHEMA and _HAVE_SCHEMAS,
        "jsonschema and the repo schemas are required")
    def test_materialized_state_matches_schema(self):
        import tempfile
        from reliquary import Context
        from reliquary.machines import create_machine, load_machine_state
        schema = _load_schema("machine-state.schema.json")
        with tempfile.TemporaryDirectory() as tmp:
            root = os.path.join(tmp, "proj")
            os.makedirs(root)
            with open(os.path.join(root, "state-bp.rlqb"), "w",
                      encoding="utf-8") as handle:
                handle.write('{"platform": "dos", "name": "state-bp", '
                             '"drives": {"cdrom0": null}}')
            context = Context(home=os.path.join(tmp, "home"), assets=root)
            machine_id = create_machine("state-bp", context=context)
            jsonschema.validate(
                load_machine_state(machine_id, context), schema)


# _CorpusCase itself is an abstract base — keep unittest from collecting
# it (its kind/extension are None).
del _CorpusCase


if __name__ == "__main__":
    unittest.main()
