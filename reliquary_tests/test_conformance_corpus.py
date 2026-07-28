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

import jsonschema

from reliquary import document, jsonc
from reliquary.errors import StaticError

_HERE = os.path.dirname(__file__)
_CORPUS = os.path.join(_HERE, "fixtures", "conformance", "blueprint")

_ID = re.compile(r"^// id: (\S+)", re.M)


def _fixtures(bucket):
    return sorted(glob.glob(os.path.join(_CORPUS, bucket, "*.rlqb")))


def _load(path):
    with open(path, encoding="utf-8") as handle:
        return jsonc.load(handle)


def _header(path):
    with open(path, encoding="utf-8") as handle:
        return [line for line in handle.read().split("\n")
                if line.startswith("//")]


def _head(path):
    """The header block as one string, for marker searches.

    `_header` returns the comment lines without their terminators, so
    the join is what the `re.M` anchors match against.
    """
    return "\n".join(_header(path))


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
                with self.assertRaises(StaticError):
                    _parse(path)

    def test_every_invalid_fixture_declares_its_id(self):
        for path in _fixtures("invalid"):
            with self.subTest(fixture=os.path.basename(path)):
                self.assertIsNotNone(
                    _ID.search(_head(path)),
                    "an invalid fixture names the diagnostic id that must "
                    "reject it, or `none` where no id exists yet.")

    def test_a_rejection_carries_the_id_the_fixture_declares(self):
        """The assertion this corpus could not make until now.

        Its README said in as many words that the headers were
        "documentation, not assertions" and that a fixture failing for
        the *wrong* reason was a false pass a reviewer had to catch.
        Blueprint diagnostics carry ids now, so the harness catches it
        instead — the same assertion the script corpus was built with,
        and the reason that one called itself the stronger pattern.

        Asserted in both directions: `// id: none` records a
        diagnostic with no identifier yet and fails the day it gains
        one, so a marker cannot outlive the gap it records.
        """
        for path in _fixtures("invalid"):
            declared = _ID.search(_head(path)).group(1)
            with self.subTest(fixture=os.path.basename(path)):
                with self.assertRaises(StaticError) as caught:
                    _parse(path)
                actual = caught.exception.rule_id
                if declared == "none":
                    self.assertIsNone(
                        actual,
                        f"this fixture records no id and the diagnostic "
                        f"now carries {actual!r}. Put it in the header — "
                        "the marker records a gap, and it has closed.")
                else:
                    self.assertEqual(
                        actual, declared,
                        "rejected, but not by the rule this fixture "
                        "names. A fixture failing for the wrong reason "
                        "is a false pass: it would keep passing after "
                        "the rule it claims to exercise stopped working.")

    def test_no_invalid_fixture_is_unidentified(self):
        """The measurement, kept honest as the ids landed.

        It reads zero, and moving up means a diagnostic lost its id
        rather than a fixture being added carelessly.
        """
        unidentified = sorted(
            os.path.basename(path) for path in _fixtures("invalid")
            if _ID.search(_head(path)).group(1) == "none")
        self.assertEqual(unidentified, [])

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

    def test_valid_fixtures_match_the_schema(self):
        schema = _blueprint_schema()
        for path in _fixtures("valid"):
            with self.subTest(fixture=os.path.basename(path)):
                jsonschema.validate(_load(path), schema)

    def test_schema_rejects_what_it_declares_it_rejects(self):
        schema = _blueprint_schema()
        for path in _fixtures("invalid"):
            if not _declares(path, "// schema: rejects"):
                continue
            with self.subTest(fixture=os.path.basename(path)):
                with self.assertRaises(jsonschema.ValidationError):
                    jsonschema.validate(_load(path), schema)

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
            context = Context(home_dir=os.path.join(tmp, "home"),
                              blueprints_dir=root,
                              scripts_dir=root, autoseed=False)
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
