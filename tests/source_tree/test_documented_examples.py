# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Every blueprint example in the docs parses and validates.

Docs can drift out of sync with the format without anyone noticing —
a reader copies a stale example as if it were still correct, and
nothing fails until they actually try it. So this module runs the
examples for real: every fenced JSON block in the documents that teach
the blueprint format goes through the real parser, and through the
published schema wherever the schema applies.

**Every example becomes its own collected test node, named for its
document and position** — for example `README.md#0` — so a block that
stops being checked shows up as a missing node instead of vanishing
into an uncounted loop, and a failing block can be selected by name
(F60).

Machine-state documents (`machine.json`) show up in the same prose but
are a different document type with their own schema. They're
identified by their state-only fields and skipped here.

**Landmark declarations get the same treatment** (F65): checked from
their own document, against their own schema and parser. `.rlql` is a
second authored JSON5 format, and its spec teaches it by example, so an
example that goes stale there is exactly the kind of thing this module
exists to catch. Its parser needs an image to go with the declaration,
so one is generated at the declared size — the example is being
checked for what it *says*, and a real screenshot in the prose
wouldn't test that.
"""

import glob
import json
import os
import re
import warnings
from importlib import resources

import jsonschema
import pytest
from PIL import Image

from reliquary import document, json5reader, landmarks, script_parser
from reliquary.errors import StaticError

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

# The documents that teach the authored blueprint format. README.md
# was added to this list once it grew worked examples of its own: it's
# the document most likely to be read first and copied from, so a
# stale example there does more damage than a stale example anywhere
# else.
_DOCUMENTS = (
    "README.md",
    "docs/blueprint-guide.md",
    "docs/spec/blueprint-model.md",
    "docs/blueprint-reference.md",
    "docs/blueprint-cookbook.md",
    "docs/spec/media-spec.md",
)

# Prose contains fragments as well as full documents — one field shown
# in isolation, or a whole document with its hashes cut out to keep the
# point visible. A fragment isn't wrong, it's just not a document, and
# running it through the document parser would only teach this test to
# expect the wrong thing. A block counts as a document when its shape
# says so: an array of specs, or an object that declares its type.
_ELISION = ("…", "...")

# The fields that identify a machine-state document, not a blueprint.
_STATE_FIELDS = {"id", "phase", "blueprint-digest", "blueprint-source",
                 "backend-id", "created"}

# Blueprint fences are JSON5; the ``json`` and legacy ``jsonc`` tags are
# still accepted too, so older prose keeps running through this check.
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
            # A fenced block containing an elided fragment (…) is an
            # illustration, not a real document.
            continue
        if isinstance(value, dict) and set(value) & _STATE_FIELDS:
            continue
        if any(mark in block for mark in _ELISION):
            continue
        if not (isinstance(value, list)
                or (isinstance(value, dict) and "type" in value)):
            continue
        yield f"{path}#{index}", value


def _schema(name):
    text = (resources.files("reliquary") / "schemas"
            / name).read_text(encoding="utf-8")
    return json.loads(text)


#: The document that teaches the `.rlql` landmark declaration format.
_LANDMARK_DOCUMENT = "docs/spec/landmarks.md"


def _landmark_blocks(path):
    """Every fenced JSON5 block in the landmark spec, in file order."""
    full = os.path.join(_REPO_ROOT, path)
    if not os.path.isfile(full):
        return
    with open(full, encoding="utf-8") as handle:
        text = handle.read()
    for index, block in enumerate(_FENCE.findall(text)):
        try:
            value = json5reader.loads(block)
        except StaticError:
            continue
        if not (isinstance(value, dict) and "screen" in value):
            continue
        yield f"{path}#{index}", block, value


#: Every example found across the documents, gathered at test collection.
EXAMPLES = [(label, value)
            for path in _DOCUMENTS
            for label, value in _blocks(path)]
SCRIPT_EXAMPLES = sorted(glob.glob(
    os.path.join(_REPO_ROOT, "planning", "design", "script-examples",
                 "*.rlqs")))
SCHEMA = _schema("blueprint-schema-v1.json")
LANDMARK_SCHEMA = _schema("landmark-schema-v1.json")
LANDMARK_EXAMPLES = list(_landmark_blocks(_LANDMARK_DOCUMENT))


# No guard is needed below: this module ships nowhere
# (`tests/source_tree`), so every document listed here is present
# wherever this test can even run, and a missing document is a real
# failure, not something to work around.

@pytest.mark.parametrize("path", _DOCUMENTS)
def test_a_listed_document_is_present(path):
    assert os.path.isfile(os.path.join(_REPO_ROOT, path)), (
        f"{path} is listed here but does not exist")


def test_the_docs_carry_real_examples():
    """Guard for the parametrized tests below: an empty sweep would pass."""
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


def test_the_landmark_spec_carries_a_real_example():
    """Guard for the parametrized tests below: an empty list would pass."""
    assert LANDMARK_EXAMPLES, (
        f"{_LANDMARK_DOCUMENT} teaches the .rlql format and carries no "
        "declaration to check")


@pytest.mark.parametrize(
    "value", [value for _label, _block, value in LANDMARK_EXAMPLES],
    ids=[label for label, _block, _value in LANDMARK_EXAMPLES])
def test_a_landmark_example_validates_against_its_schema(value):
    jsonschema.validate(value, LANDMARK_SCHEMA)


@pytest.mark.parametrize(
    "block,value",
    [(block, value) for _label, block, value in LANDMARK_EXAMPLES],
    ids=[label for label, _block, _value in LANDMARK_EXAMPLES])
def test_a_landmark_example_parses(block, value, tmp_path):
    path = tmp_path / "example.rlql"
    path.write_text(block, encoding="utf-8")
    size = (value["screen"]["width"], value["screen"]["height"])
    Image.new("RGB", size, (0, 0, 0)).save(tmp_path / "example.1.png")
    landmarks.load_landmark_declaration(str(path))


# Every open script example parses.
#
# No guard needed, for the same reason as above: this catalogue is
# maintainer-only material and ships nowhere, and neither does this
# module, so the two are always present together or not at all.
#
# The catalogue holds *unresolved* design problems, shown as real
# script text; lines that are deliberately illegal are commented out
# and marked as such. So an example that fails to parse means the
# catalogue has drifted, not that the drift was intended — and that's
# exactly what happened once: five examples for problems that had
# since been resolved were deleted on 2026-07-26, partly because one of
# them had quietly rotted into syntax the language no longer accepts.
# The catalogue's own README concluded that "a note that cannot fail is
# not a guard." This test is that guard. Without it, the catalogue is
# just prose pretending to be code.

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


# No live document still teaches the retired four-component shape.
#
# Historical records keep their old spellings as-is — DECISIONS entries
# and released CHANGELOG sections are the record of what happened at
# the time. Everything a reader might actually act on now describes the
# current, revised model instead.

# The JSON keys only. It's fine for prose to describe `.rlqm` as
# *retired* — that's accurate. The file kind's actual absence is
# checked separately, in test_old_surface_purge.
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
