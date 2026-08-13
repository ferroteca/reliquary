# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Every blueprint example in the docs parses and validates.

Prose drifts from the format silently — a stale example is read as
instruction and copied, and nothing fails until a user tries it. So
the examples are executed: every fenced JSON block in the documents
that teach the blueprint format is run through the real parser, and
through the published schema where it applies.

**Every example is a collected node named for its document and
position** — `README.md#0` — so a block that stops being checked is a
missing node rather than a loop nobody counts, and a failing one is
selected by name (F60).

Machine-state documents (`machine.json`) appear in the same prose and
are a different document type with their own schema; they are
identified by their state-only fields and skipped here.
"""

import glob
import json
import os
import re
import warnings
from importlib import resources

import jsonschema
import pytest

from reliquary import document, json5reader, script_parser
from reliquary.errors import StaticError

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

# The documents that teach the authored blueprint format. README.md
# joined them when it grew worked examples: it is the document most
# likely to be read first and copied from, so an example rotting
# there costs more than anywhere else, not less.
_DOCUMENTS = (
    "README.md",
    "docs/blueprint-guide.md",
    "docs/spec/blueprint-model.md",
    "docs/blueprint-reference.md",
    "docs/blueprint-cookbook.md",
    "docs/spec/media-spec.md",
)

# Prose carries fragments as well as documents — one field in
# isolation, or a whole document with its hashes elided to keep the
# point visible. A fragment is not wrong, it is just not a document,
# and running it through a document parser would only teach the test
# to expect the wrong thing. A block counts as a document when the
# format says so: an array of specs, or an object declaring its type.
_ELISION = ("…", "...")

# A machine-state document, not a blueprint.
_STATE_FIELDS = {"id", "phase", "blueprint-digest", "blueprint-source",
                 "backend-id", "created"}

# Blueprint fences are JSON5; ``json`` / legacy ``jsonc`` tags remain
# accepted so older prose still runs through the same gate.
_FENCE = re.compile(r"```(?:json5|jsonc?)\n(.*?)```", re.S)


def _blocks(path):
    full = os.path.join(_REPO_ROOT, path)
    if not os.path.isfile(full):
        return
    with open(full, encoding="utf-8") as handle:
        text = handle.read()
    for index, block in enumerate(_FENCE.findall(text)):
        try:
            value = json5reader.loads(block)
        except StaticError:
            # Prose fences carrying an elided fragment (…) are
            # illustrations, not documents.
            continue
        if isinstance(value, dict) and set(value) & _STATE_FIELDS:
            continue
        if any(mark in block for mark in _ELISION):
            continue
        if not (isinstance(value, list)
                or (isinstance(value, dict) and "type" in value)):
            continue
        yield f"{path}#{index}", value


def _schema():
    text = (resources.files("reliquary") / "schemas"
            / "blueprint-schema-v1.json").read_text(encoding="utf-8")
    return json.loads(text)


#: Every example the documents carry, gathered at collection.
EXAMPLES = [(label, value)
            for path in _DOCUMENTS
            for label, value in _blocks(path)]
SCRIPT_EXAMPLES = sorted(glob.glob(
    os.path.join(_REPO_ROOT, "planning", "design", "script-examples",
                 "*.rlqs")))
SCHEMA = _schema()


# No guard anywhere below: this module ships nowhere
# (`tests/source_tree`), so every document is present wherever it can
# run, and a missing one is the failure it is rather than a
# configuration to tolerate.

@pytest.mark.parametrize("path", _DOCUMENTS)
def test_a_listed_document_is_present(path):
    assert os.path.isfile(os.path.join(_REPO_ROOT, path)), (
        f"{path} is listed here but does not exist")


def test_the_docs_carry_real_examples():
    """The pin behind the parametrisations: an empty sweep passes."""
    assert len(EXAMPLES) > 10, "expected the docs to carry real examples"


@pytest.mark.parametrize("value", [value for _label, value in EXAMPLES],
                         ids=[label for label, _value in EXAMPLES])
def test_an_example_parses(value):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", document.BlueprintWarning)
        document.parse_document(value)


@pytest.mark.parametrize("value", [value for _label, value in EXAMPLES],
                         ids=[label for label, _value in EXAMPLES])
def test_an_example_validates_against_the_schema(value):
    jsonschema.validate(value, SCHEMA)


# Every open script example parses.
#
# No guard, for the reason above: the catalogue is maintainer
# governance and ships nowhere, and neither does this module, so the
# two are only ever present together.
#
# The catalogue holds *unresolved* design problems, demonstrated in
# real script text; lines that are deliberately illegal are commented
# out and marked. So an example that will not parse is drift, not
# intent — and drift is what happened: the five resolved examples were
# deleted in 2026-07-26 partly because one had rotted into syntax the
# language no longer accepts with nobody noticing, the README
# concluding that "a note that cannot fail is not a guard". This is
# that guard. Without it the catalogue is prose claiming to be code.

def test_the_catalogue_holds_examples():
    assert SCRIPT_EXAMPLES, (
        "no examples found under planning/design/script-examples; an "
        "empty catalogue passes the check below vacuously")


@pytest.mark.parametrize("path", SCRIPT_EXAMPLES,
                         ids=[os.path.basename(p) for p in SCRIPT_EXAMPLES])
def test_a_script_example_parses(path):
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    script_parser.parse_script(text)


# The retired four-component shape leaves no live instruction.
#
# Historical records keep their spellings — DECISIONS entries and
# released CHANGELOG sections are the record of their own moment.
# Everything a reader might act on speaks the revised model.

# The JSON keys only. Prose naming `.rlqm` as *retired* is correct,
# and the file kind's absence is guarded separately
# (test_old_surface_purge).
RETIRED = ('"sources"', '"archives"', '"members"')
EXEMPT = {"planning/DECISIONS.md", "CHANGELOG.md",
          "planning/USE-CASE-PROPOSALS.md",
          "planning/PRINCIPLE-PROPOSALS.md"}


def test_no_live_document_teaches_the_retired_shape():
    offenders = []
    for path in (glob.glob(os.path.join(_REPO_ROOT, "docs", "*.md"))
                 + glob.glob(os.path.join(_REPO_ROOT, "planning", "design",
                                          "*.md"))):
        relative = os.path.relpath(path, _REPO_ROOT).replace("\\", "/")
        if relative in EXEMPT:
            continue
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        for token in RETIRED:
            if token in text:
                offenders.append(f"{relative}: {token}")
    assert offenders == [], (
        "these documents still teach the retired component shape:\n"
        + "\n".join(offenders))
