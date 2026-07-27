# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Every blueprint example in the docs parses and validates.

Prose drifts from the format silently — a stale example is read as
instruction and copied, and nothing fails until a user tries it. So
the examples are executed: every fenced JSON block in the documents
that teach the blueprint format is run through the real parser, and
through the published schema where it applies.

Machine-state documents (`machine.json`) appear in the same prose and
are a different document type with their own schema; they are
identified by their state-only fields and skipped here.
"""

import glob
import json
import os
import re
import unittest
import warnings
from importlib import resources

from reliquary import document, jsonc, script_parser
from reliquary.errors import StaticError

try:
    import jsonschema
    _HAVE_JSONSCHEMA = True
except ImportError:
    _HAVE_JSONSCHEMA = False

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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

_FENCE = re.compile(r"```jsonc?\n(.*?)```", re.S)


def _blocks(path):
    full = os.path.join(_REPO_ROOT, path)
    if not os.path.isfile(full):
        return
    with open(full, encoding="utf-8") as handle:
        text = handle.read()
    for index, block in enumerate(_FENCE.findall(text)):
        try:
            value = jsonc.loads(block)
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


class DocumentedExampleTests(unittest.TestCase):
    def test_documents_are_present(self):
        for path in _DOCUMENTS:
            with self.subTest(document=path):
                self.assertTrue(
                    os.path.isfile(os.path.join(_REPO_ROOT, path)),
                    f"{path} is listed here but does not exist")

    def test_every_example_parses(self):
        checked = 0
        for path in _DOCUMENTS:
            for label, value in _blocks(path):
                with self.subTest(example=label):
                    with warnings.catch_warnings():
                        warnings.simplefilter(
                            "ignore", document.BlueprintWarning)
                        document.parse_document(value)
                    checked += 1
        self.assertGreater(checked, 10,
                           "expected the docs to carry real examples")

    @unittest.skipUnless(_HAVE_JSONSCHEMA, "jsonschema is required")
    def test_every_example_validates_against_the_schema(self):
        schema = _schema()
        for path in _DOCUMENTS:
            for label, value in _blocks(path):
                with self.subTest(example=label):
                    jsonschema.validate(value, schema)


_SCRIPT_EXAMPLES = os.path.join(
    _REPO_ROOT, "planning", "design", "script-examples")


@unittest.skipUnless(os.path.isdir(_SCRIPT_EXAMPLES),
                     "the script-example catalogue is source-tree only")
class ScriptExampleTests(unittest.TestCase):
    """Every open script example parses.

    The catalogue holds *unresolved* design problems, demonstrated
    in real script text; lines that are deliberately illegal are
    commented out and marked. So an example that will not parse is
    drift, not intent — and drift is what happened: the five
    resolved examples were deleted in 2026-07-26 partly because one
    had rotted into syntax the language no longer accepts with
    nobody noticing, the README concluding that "a note that cannot
    fail is not a guard". This is that guard. Without it the
    catalogue is prose claiming to be code.
    """

    def test_every_example_parses(self):
        paths = sorted(glob.glob(os.path.join(_SCRIPT_EXAMPLES, "*.rlqs")))
        for path in paths:
            with self.subTest(example=os.path.basename(path)):
                with open(path, encoding="utf-8") as handle:
                    text = handle.read()
                script_parser.parse_script(text)


class RetiredVocabularyTests(unittest.TestCase):
    """The retired four-component shape leaves no live instruction.

    Historical records keep their spellings — DECISIONS entries and
    released CHANGELOG sections are the record of their own moment.
    Everything a reader might act on speaks the revised model.
    """

    # The JSON keys only. Prose naming `.rlqm` as *retired* is
    # correct, and the file kind's absence is guarded separately
    # (test_old_surface_purge).
    RETIRED = ('"sources"', '"archives"', '"members"')
    EXEMPT = {"planning/DECISIONS.md", "CHANGELOG.md",
              "planning/USE-CASE-PROPOSALS.md",
              "planning/PRINCIPLE-PROPOSALS.md"}

    def test_no_live_document_teaches_the_retired_shape(self):
        offenders = []
        for path in glob.glob(os.path.join(_REPO_ROOT, "docs", "*.md")) + \
                glob.glob(os.path.join(_REPO_ROOT, "planning", "design",
                                       "*.md")):
            relative = os.path.relpath(path, _REPO_ROOT).replace("\\", "/")
            if relative in self.EXEMPT:
                continue
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
            for token in self.RETIRED:
                if token in text:
                    offenders.append(f"{relative}: {token}")
        self.assertEqual(
            offenders, [],
            "these documents still teach the retired component shape:\n"
            + "\n".join(offenders))


if __name__ == "__main__":
    unittest.main()
