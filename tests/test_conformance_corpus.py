# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
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

**Every fixture is a collected node**, through ``tests/corpus.py``, and
the bucket counts are pinned there: this is the corpus that ran against
the parser and not the schema while claiming the two cannot drift, and
a loop of 135 fixtures is what let it (D106). A node is named for its
file — ``test_a_valid_fixture_parses[machine-drives.rlqb]`` — which is
how one is selected while it is being fixed.

The corpus README documents what single-document fixtures cannot reach.
"""

import json
import os
import re
import warnings
from importlib import resources

import jsonschema
import pytest

from reliquary import Context, document, json5reader
from reliquary.errors import StaticError
from reliquary.machines import create_machine, load_machine_state
from tests import corpus, fake_backend

_HERE = os.path.dirname(__file__)
_CORPUS = os.path.join(_HERE, "fixtures", "conformance", "blueprint")

_ID = re.compile(r"^// id: (\S+)", re.M)

VALID = corpus.fixtures(_CORPUS, "valid", ".rlqb", count=24)
INVALID = corpus.fixtures(_CORPUS, "invalid", ".rlqb", count=48)
AT_RESOLUTION = corpus.fixtures(
    _CORPUS, "invalid-at-resolution", ".rlqb", count=2)


def _load(path):
    with open(path, encoding="utf-8") as handle:
        return json5reader.load(handle)


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


_SCHEMA = _blueprint_schema()


@corpus.parametrize(VALID)
def test_a_valid_fixture_parses(fixture):
    _parse(fixture)


@corpus.parametrize(VALID)
def test_a_valid_fixture_matches_the_schema(fixture):
    jsonschema.validate(_load(fixture), _SCHEMA)


@corpus.parametrize(VALID)
def test_a_valid_fixture_warns_exactly_when_it_declares_it(fixture):
    """A `// warns:` fixture must warn, and every other one must not.

    One check over the whole bucket rather than two over its halves:
    partitioned, the fixtures a check skips are invisible, which is the
    shape this corpus was caught in.
    """
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        document.parse_document(_load(fixture))
    warned = [str(warning.message) for warning in caught
              if issubclass(warning.category, document.BlueprintWarning)]
    if _declares(fixture, "// warns:"):
        assert warned, ("this fixture declares `// warns:` and parsed "
                        "silently.")
    else:
        assert warned == []


@corpus.parametrize(INVALID)
def test_an_invalid_fixture_is_rejected(fixture):
    with pytest.raises(StaticError):
        _parse(fixture)


@corpus.parametrize(INVALID)
def test_an_invalid_fixture_declares_its_id(fixture):
    assert _ID.search(_head(fixture)) is not None, (
        "an invalid fixture names the diagnostic id that must reject "
        "it, or `none` where no id exists yet.")


@corpus.parametrize(INVALID)
def test_a_rejection_carries_the_id_the_fixture_declares(fixture):
    """The assertion this corpus could not make until now.

    Its README said in as many words that the headers were
    "documentation, not assertions" and that a fixture failing for the
    *wrong* reason was a false pass a reviewer had to catch. Blueprint
    diagnostics carry ids now, so the harness catches it instead — the
    same assertion the script corpus was built with, and the reason
    that one called itself the stronger pattern.

    Asserted in both directions: `// id: none` records a diagnostic
    with no identifier yet and fails the day it gains one, so a marker
    cannot outlive the gap it records.
    """
    declared = _ID.search(_head(fixture)).group(1)
    with pytest.raises(StaticError) as caught:
        _parse(fixture)
    actual = caught.value.rule_id
    if declared == "none":
        assert actual is None, (
            f"this fixture records no id and the diagnostic now "
            f"carries {actual!r}. Put it in the header — the marker "
            "records a gap, and it has closed.")
    else:
        assert actual == declared, (
            "rejected, but not by the rule this fixture names. A "
            "fixture failing for the wrong reason is a false pass: it "
            "would keep passing after the rule it claims to exercise "
            "stopped working.")


def test_no_invalid_fixture_is_unidentified():
    """The measurement, kept honest as the ids landed.

    It reads zero, and moving up means a diagnostic lost its id rather
    than a fixture being added carelessly. Aggregate on purpose: the
    number is the finding, and it names every offender at once.
    """
    unidentified = sorted(
        os.path.basename(path) for path in INVALID
        if _ID.search(_head(path)).group(1) == "none")
    assert unidentified == []


@corpus.parametrize(INVALID)
def test_the_schema_rejects_exactly_what_the_fixture_declares(fixture):
    """The schema half, one node per fixture — the check that vanished.

    A `// schema: rejects` fixture must fail the published schema; an
    unmarked one must pass it, because the marker records the overlap
    between the two validators and a stale marker is how they drift
    apart. Both directions in one check, so no fixture is filtered out
    of the only place it would have been counted.
    """
    if _declares(fixture, "// schema: rejects"):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(_load(fixture), _SCHEMA)
    else:
        jsonschema.validate(_load(fixture), _SCHEMA)


@pytest.mark.parametrize("vocabulary", [
    "platform", "backend", "materialize", "controller", "control-planes",
    "pointing-device"])
def test_a_closed_vocabulary_is_schema_enforced(vocabulary):
    """What the reach trim buys, asserted rather than assumed.

    A reference in a closed vocabulary must fail the schema, not merely
    the parser: the enums stay plain so an editor can complete them,
    and that is the whole argument for refusing a reference there
    (D26).
    """
    path = os.path.join(_CORPUS, "invalid", f"ref-in-{vocabulary}.rlqb")
    assert os.path.exists(path), f"missing {path}"
    assert _declares(path, "// schema: rejects"), (
        f"the {vocabulary} vocabulary must be schema-enforced")


@corpus.parametrize(AT_RESOLUTION)
def test_a_resolution_fixture_parses_clean(fixture):
    """These are rejected at resolution, so parse must accept them.

    A fixture failing here would be failing for the wrong reason, which
    costs as much as one passing for the wrong reason.
    """
    _parse(fixture)


# The machine-state schema, which is the other norm this module holds
# the code to. It has no fixture directory: what it validates is a
# state the machine layer writes and a vocabulary the schema itself
# declares, so these parametrise over the package rather than over a
# corpus.

_STATE_SCHEMA = json5reader.loads(
    (resources.files("reliquary") / "schemas"
     / "machine-state.schema.json").read_text(encoding="utf-8"))
_PHASES = sorted(_STATE_SCHEMA["properties"]["phase"]["enum"])


@pytest.mark.parametrize("phase", _PHASES)
def test_a_schema_phase_is_written_somewhere(phase):
    """The phase vocabulary is one set across schema and code.

    The phase is a closed enum: `machine-state.schema.json` is its
    machine-readable norm, and the literals `machines.py` writes must
    be members. A phase the schema admits and no operation can produce
    is vocabulary the format advertises and never emits. Whether the
    prose in `instance-model.md` matches the schema is R8's audit
    (planning/RECURRING.md) — the schema is the artifact this suite
    consumes.
    """
    source = (resources.files("reliquary")
              / "machines.py").read_text(encoding="utf-8")
    assert f'"{phase}"' in source, (
        f"{phase!r} is a phase the schema admits and machines.py never "
        "writes.")


@pytest.fixture
def materialized_state(tmp_path):
    """A real machine's `machine.json`, as the machine layer writes it."""
    root = tmp_path / "proj"
    root.mkdir()
    (root / "state-bp.rlqb").write_text(
        '[{"type": "machine", "name": "state-bp", "platform": "dos", '
        '"drives": {"cdrom0": null}}]', encoding="utf-8")
    context = Context(home_dir=str(tmp_path / "home"),
                      blueprints_dir=str(root), scripts_dir=str(root))
    with fake_backend.installed():
        machine_id = create_machine("state-bp", context=context)
    return load_machine_state(machine_id, context)


def test_a_materialized_state_matches_the_schema(materialized_state):
    jsonschema.validate(materialized_state, _STATE_SCHEMA)


def test_a_running_state_matches_the_schema(materialized_state):
    """A running machine folds the live-VM identity into the same
    document as a `vm` section — that shape is the schema's too."""
    running = dict(materialized_state, phase="running", vm={
        "backend": "qemu",
        "backend-id": f"reliquary-{materialized_state['id']}",
        "token": "0" * 32,
        "endpoint": {"port": 5555},
        "pid": 4242})
    jsonschema.validate(running, _STATE_SCHEMA)
