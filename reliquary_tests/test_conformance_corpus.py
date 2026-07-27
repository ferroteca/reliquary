# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""The shared static-conformance corpus (composed blueprint model).

Every fixture under ``fixtures/conformance/blueprint/`` is run against
the validators that can judge it. Reliquary's own parser
(``document.parse_document``) is the normative one and judges every
fixture; the published JSON Schema
(``reliquary/schemas/blueprint-schema-v1.json``) must accept everything
valid, and catches the structural half of what is invalid.

Three buckets, because two-phase validation is real:

- ``valid/`` — parses, and validates against the schema.
- ``invalid/`` — rejected at parse. Those a schema can also judge carry
  a ``// schema: rejects`` header and must fail it too; the rest are
  semantic rules no schema can express (the reference grammar, name
  derivation, identity across specs, containment paths).
- ``invalid-at-resolution/`` — parses clean and is rejected only when
  resolved, so neither the parse assertion nor the schema applies.

The corpus README documents what single-document fixtures cannot reach.
"""

import glob
import json
import os
import re
import unittest
import warnings
from importlib import resources

from reliquary import document, jsonc

try:
    import jsonschema
    _HAVE_JSONSCHEMA = True
except ImportError:
    _HAVE_JSONSCHEMA = False

_HERE = os.path.dirname(__file__)
_CORPUS = os.path.join(_HERE, "fixtures", "conformance", "blueprint")


def _fixtures(bucket):
    return sorted(glob.glob(os.path.join(_CORPUS, bucket, "*.rlqb")))


def _load(path):
    with open(path, encoding="utf-8") as handle:
        return jsonc.load(handle)


def _header(path):
    with open(path, encoding="utf-8") as handle:
        return [line for line in handle.read().split("\n")
                if line.startswith("//")]


def _declares(path, marker):
    return any(line.startswith(marker) for line in _header(path))


def _parse(path):
    """Parse a fixture, ignoring the warnings some of them declare."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", document.BlueprintWarning)
        return document.parse_document(_load(path))


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
                _parse(path)

    def test_invalid_fixtures_are_rejected(self):
        paths = _fixtures("invalid")
        self.assertTrue(paths, "no invalid blueprint fixtures found")
        for path in paths:
            with self.subTest(fixture=os.path.basename(path)):
                with self.assertRaises((ValueError, KeyError, TypeError)):
                    _parse(path)

    def test_resolution_fixtures_parse_clean(self):
        """These are rejected at resolution, so parse must accept them.

        A fixture failing here would be failing for the wrong reason,
        which costs as much as one passing for the wrong reason.
        """
        paths = _fixtures("invalid-at-resolution")
        self.assertTrue(paths, "no resolution-time fixtures found")
        for path in paths:
            with self.subTest(fixture=os.path.basename(path)):
                _parse(path)

    def test_declared_warnings_are_emitted(self):
        """A fixture declaring `// warns:` must actually warn."""
        for path in _fixtures("valid"):
            if not _declares(path, "// warns:"):
                continue
            with self.subTest(fixture=os.path.basename(path)):
                with self.assertWarns(document.BlueprintWarning):
                    document.parse_document(_load(path))

    def test_fixtures_that_only_warn_do_not_warn_otherwise(self):
        """Every other valid fixture parses silently."""
        for path in _fixtures("valid"):
            if _declares(path, "// warns:"):
                continue
            with self.subTest(fixture=os.path.basename(path)):
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    document.parse_document(_load(path))
                self.assertEqual(
                    [str(w.message) for w in caught
                     if issubclass(w.category, document.BlueprintWarning)],
                    [])

    @unittest.skipUnless(_HAVE_JSONSCHEMA, "jsonschema is required")
    def test_valid_fixtures_match_the_schema(self):
        schema = _blueprint_schema()
        for path in _fixtures("valid"):
            with self.subTest(fixture=os.path.basename(path)):
                jsonschema.validate(_load(path), schema)

    @unittest.skipUnless(_HAVE_JSONSCHEMA, "jsonschema is required")
    def test_schema_rejects_what_it_declares_it_rejects(self):
        schema = _blueprint_schema()
        for path in _fixtures("invalid"):
            if not _declares(path, "// schema: rejects"):
                continue
            with self.subTest(fixture=os.path.basename(path)):
                with self.assertRaises(jsonschema.ValidationError):
                    jsonschema.validate(_load(path), schema)

    @unittest.skipUnless(_HAVE_JSONSCHEMA, "jsonschema is required")
    def test_unmarked_fixtures_really_are_beyond_the_schema(self):
        """The marker records the overlap; it must not go stale.

        An unmarked fixture the schema now catches means the schema grew
        a rule and the corpus did not notice — which is how the two
        validators drift apart.
        """
        schema = _blueprint_schema()
        for path in _fixtures("invalid"):
            if _declares(path, "// schema: rejects"):
                continue
            with self.subTest(fixture=os.path.basename(path)):
                jsonschema.validate(_load(path), schema)

    @unittest.skipUnless(_HAVE_JSONSCHEMA, "jsonschema is required")
    def test_closed_vocabularies_are_schema_enforced(self):
        """What the reach trim buys, asserted rather than assumed.

        A reference in a closed vocabulary must fail the schema, not
        merely the parser: the enums stay plain so an editor can
        complete them, and that is the whole argument for refusing a
        reference there (D26).
        """
        for name in ("platform", "backend", "materialize", "controller",
                     "control-planes"):
            path = os.path.join(_CORPUS, "invalid", f"ref-in-{name}.rlqb")
            with self.subTest(vocabulary=name):
                self.assertTrue(os.path.exists(path), f"missing {path}")
                self.assertTrue(
                    _declares(path, "// schema: rejects"),
                    f"the {name} vocabulary must be schema-enforced")


class SpecifiedPhaseTests(unittest.TestCase):
    """The phase vocabulary is one set across spec, schema, and code.

    P24's inventory pass over the instance model. The phase is a
    closed enum in three places at once — prose in
    `instance-model.md`, an `enum` in `machine-state.schema.json`,
    and the literals `machines.py` writes — and the schema is the
    one AGENTS.md requires to stay synchronized with the normative
    prose. A phase in the schema and not the prose is undocumented
    state a reader would meet in a file; one in the prose and not
    the schema makes a documented state fail validation.
    """

    _SPEC = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "docs", "spec", "instance-model.md")

    @classmethod
    def _specified(cls):
        with open(cls._SPEC, encoding="utf-8") as handle:
            text = handle.read()
        # The sentence that enumerates them, rather than every
        # backticked mention: the state diagram and the narrative
        # name phases too, and a set built from those would drift
        # into whatever prose happens to cite.
        start = text.index("The phase is one of")
        return set(re.findall(r"`([a-z]+)`",
                              text[start:text.index(".", start)]))

    @staticmethod
    def _schema_enum():
        schema = jsonc.loads(
            (resources.files("reliquary") / "schemas"
             / "machine-state.schema.json").read_text(encoding="utf-8"))
        return set(schema["properties"]["phase"]["enum"])

    @unittest.skipUnless(os.path.isfile(_SPEC),
                         "the instance-model spec is source-tree only")
    def test_the_prose_and_the_schema_name_the_same_phases(self):
        self.assertEqual(
            self._specified(), self._schema_enum(),
            "docs/spec/instance-model.md and "
            "reliquary/schemas/machine-state.schema.json disagree "
            "about the lifecycle phases. The prose is normative and "
            "the schema must track it (AGENTS.md).")

    def test_every_schema_phase_is_written_somewhere(self):
        source = (resources.files("reliquary")
                  / "machines.py").read_text(encoding="utf-8")
        unwritten = sorted(phase for phase in self._schema_enum()
                           if f'"{phase}"' not in source)
        self.assertEqual(
            unwritten, [],
            f"{unwritten} are phases the schema admits and machines.py "
            "never writes. A state no operation can produce is "
            "vocabulary the format advertises and never emits.")


class MachineStateSchemaTests(unittest.TestCase):
    """A real materialized state validates against the state schema."""

    @unittest.skipUnless(_HAVE_JSONSCHEMA, "jsonschema is required")
    def test_materialized_state_matches_schema(self):
        import tempfile
        from reliquary import Context
        from reliquary.machines import create_machine, load_machine_state
        schema = jsonc.loads(
            (resources.files("reliquary") / "schemas"
             / "machine-state.schema.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            root = os.path.join(tmp, "proj")
            os.makedirs(root)
            with open(os.path.join(root, "state-bp.rlqb"), "w",
                      encoding="utf-8") as handle:
                handle.write('[{"type": "machine", "name": "state-bp", '
                             '"platform": "dos", '
                             '"drives": {"cdrom0": null}}]')
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
