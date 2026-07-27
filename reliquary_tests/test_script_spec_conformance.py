# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""The scripting language's inventories, read off its specification.

P24 asks that every interface carry automated tests checking it
**against its specification**, and the cheap half of that is the
inventory comparison: docs/spec/script-spec.md enumerates, the code
enumerates, and a set difference is the whole test. It catches the
failure ordinary behaviour tests cannot — a requirement the spec
states and the code never implemented — because nothing here is
written from knowledge of the code.

The same shape found six divergences in the CLI's command list
(``reliquary_tests.test_cli.ClaimedCommandTests``); writing this
module found S13, specified since the surface was adopted and
enforced nowhere, so a malformed regex reached the guest loop and
failed there as an untyped fault.

Four inventories are compared here. What that leaves uncovered,
named rather than exempted quietly (P24's own clause): the
*content* of every rule — that S11 really is the terminating-
statement rule and not something else — which only conformance
fixtures in the blueprint corpus's manner could check.
"""

import os
import re
import unittest

from reliquary import errors
from reliquary.script_nodes import KEYWORDS, RULE_OF
from reliquary.script_parser import _DISPLAY, _SIGNATURES

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SPEC = os.path.join(_REPO_ROOT, "docs", "spec", "script-spec.md")
_PACKAGE = os.path.join(_REPO_ROOT, "reliquary")

_BACKTICKED = re.compile(r"`([^`]+)`")
_RULE_BULLET = re.compile(r"^- \*\*(S\d+)\*\*", re.M)
_CITATION = re.compile(r"\((S\d+)\)")
_PYTHON_SPELLING = re.compile(r"Python spells it ((?:`\w+`(?: / )?)+)")
_CAMEL_BREAK = re.compile(r"(?<!^)(?=[A-Z])")


def _spec_text():
    with open(_SPEC, encoding="utf-8") as handle:
        return handle.read()


def _section(text, heading, until):
    """The spec text from one heading up to the next named one.

    A missing heading fails loudly rather than as a bare
    ``substring not found``: these tests are anchored to the spec's
    structure, so a renamed section is something to notice, not a
    silently narrower comparison.
    """
    bounds = []
    for mark in (heading, until):
        offset = text.find("\n" + mark + "\n", *bounds[:1])
        if offset < 0:
            raise AssertionError(
                f"docs/spec/script-spec.md has no {mark!r} heading; the "
                "spec-inventory tests read the section it opens.")
        bounds.append(offset)
    return text[bounds[0]:bounds[1]]


def _tables(chunk):
    """Every markdown table in ``chunk`` as (header, rows) pairs."""
    found = []
    header = None
    for line in chunk.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            header = None
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if set("".join(cells)) <= set("-: "):
            continue                    # the alignment row
        if header is None:
            header = cells
            found.append((header, []))
            continue
        found[-1][1].append(cells)
    return found


def _signature_tables():
    """The node tables of "Core grammar", before the EBNF."""
    return _tables(_section(_spec_text(), "## Core grammar",
                            "### Grammar (normative)"))


@unittest.skipUnless(os.path.isfile(_SPEC),
                     "the script spec is source-tree only")
class SpecInventoryCase(unittest.TestCase):
    """Shared skip: the spec ships with the source, not the wheel."""


class StaticRuleIdTests(SpecInventoryCase):
    """The S-ids the spec defines are the S-ids diagnostics cite.

    Not hypothetical: on 2026-07-27 this found **S13** — "watch
    patterns are non-empty and regexes compile" — defined by the
    spec and enforced by nothing. `wait //` parsed and then matched
    every screen; `wait /a(b/` parsed and raised `re.error` from
    the sample loop, exiting 1 for a defect visible in the script
    text alone.
    """

    def _defined(self):
        return set(_RULE_BULLET.findall(_spec_text()))

    def _cited(self):
        """The rules some diagnostic enforces.

        Diagnostics stopped citing `(Sn)` in their text when the
        dotted ids landed; the rule a diagnostic serves is now
        `RULE_OF[id]`, so that mapping is what this reads. Prose
        `(Sn)` mentions in docstrings are deliberately *not* read —
        a comment naming a rule is not an implementation of it,
        and reading them would have let this test pass on
        documentation alone.
        """
        return {rule for rule in RULE_OF.values() if rule is not None}

    def _unidentified(self):
        """Rules whose spec bullet says no id exists for them yet.

        Read from the spec rather than listed here, so the
        exemption retires itself: the day S1's diagnostics gain
        ids, its bullet loses that phrase and the rule rejoins the
        comparison below.
        """
        text = _spec_text()
        start = text.index("- **S1** —")
        end = text.index("\nThe grammar is line-oriented", start)
        found = set()
        for para in text[start:end].split("\n- **"):
            match = re.match(r"(S\d+)\*\*", para.lstrip("- *"))
            # "No ids yet" (plural) marks a rule with none at all.
            # S4 says "No id yet for the header form" and does have
            # one for the node form, so the two must not read alike.
            if match and "No ids yet" in para:
                found.add(match.group(1))
        return found

    def test_every_specified_rule_is_enforced_somewhere(self):
        unenforced = sorted(
            self._defined() - self._cited() - self._unidentified(),
            key=lambda id_: int(id_[1:]))
        self.assertEqual(
            unenforced, [],
            f"docs/spec/script-spec.md defines {unenforced}, no "
            "diagnostic id enforces them, and their bullets do not say "
            "so. A rule nothing enforces is a requirement the code "
            "never implemented, not a rule.")

    def test_a_rule_marked_unidentified_really_has_no_id(self):
        """The other direction, so the marking cannot go stale."""
        wrongly_marked = sorted(self._unidentified() & self._cited())
        self.assertEqual(
            wrongly_marked, [],
            f"{wrongly_marked} carry diagnostic ids and their spec "
            "bullets still say none exists. Remove the phrase — the "
            "note records a gap, and it has closed.")

    def test_no_diagnostic_cites_a_rule_the_spec_does_not_define(self):
        invented = sorted(self._cited() - self._defined(),
                          key=lambda id_: int(id_[1:]))
        self.assertEqual(
            invented, [],
            f"diagnostics cite {invented}, which the spec's syntactic "
            "restrictions do not define. An id is a citation handle; "
            "one that names nothing cannot be looked up.")


class NodeVocabularyTests(SpecInventoryCase):
    """The spec's node tables and the lexer's keywords agree.

    ``KEYWORDS`` is what the lexer treats as a node name where a
    node may start, so it is the code's own answer to "what nodes
    are there" — the set the spec's four signature tables name.
    """

    def _specified(self):
        names = set()
        for _header, rows in _signature_tables():
            names.update(_BACKTICKED.findall(row[0])[0] for row in rows)
        return names

    def test_the_spec_names_no_node_the_language_lacks(self):
        absent = sorted(self._specified() - set(KEYWORDS))
        self.assertEqual(
            absent, [],
            f"the spec's signature tables name {absent}, which the "
            "language does not have. A spec states what exists; "
            "unbuilt vocabulary belongs in planning/proposed/.")

    def test_every_node_is_specified(self):
        unspecified = sorted(set(KEYWORDS) - self._specified())
        self.assertEqual(
            unspecified, [],
            f"{unspecified} are node names the lexer honours and the "
            "spec's signature tables do not list. The scripting "
            "language is a primary interface.")


class NodeSignatureTests(SpecInventoryCase):
    """Each node accepts exactly the modifiers the spec gives it.

    A node may hold more than one signature — `wait` is one shape
    with a condition and another with handlers, `http` a
    declaration and an action — so both sides are compared as the
    *set* of a node's modifier sets rather than one list each. That
    is also why the code's rule names are read through ``_DISPLAY``:
    it is the map back to the spelling an author writes, which is
    the only spelling the spec has.
    """

    def _specified(self):
        signatures = {}
        for header, rows in _signature_tables():
            if "modifiers" not in header:
                continue                # the header-node table
            column = header.index("modifiers")
            for row in rows:
                node = _BACKTICKED.findall(row[0])[0]
                signatures.setdefault(node, set()).add(
                    frozenset(_BACKTICKED.findall(row[column])))
        return signatures

    def _implemented(self):
        signatures = {}
        for rule, modifiers in _SIGNATURES.items():
            node = _DISPLAY.get(rule, rule)
            signatures.setdefault(node, set()).add(frozenset(modifiers))
        return signatures

    def test_the_signatures_match(self):
        specified, implemented = self._specified(), self._implemented()
        self.assertEqual(
            sorted(specified), sorted(implemented),
            "the nodes carrying a modifier signature differ between "
            "docs/spec/script-spec.md and script_parser._SIGNATURES.")
        for node in sorted(specified):
            with self.subTest(node=node):
                self.assertEqual(
                    sorted(map(sorted, specified[node])),
                    sorted(map(sorted, implemented[node])),
                    f"{node} accepts different modifiers than the spec "
                    "gives it. An argument or modifier outside a "
                    "node's signature is a parse error, so this is "
                    "what a script may say.")


class ErrorTaxonomyTests(SpecInventoryCase):
    """The exit codes and classes of "Error classes and exit codes".

    The section states the taxonomy twice — a table of class, tier
    and exit code, and a sentence giving the Python spelling of
    each class — and both halves are read here. What is *not*
    derived from the spec, named rather than left implied: `0`,
    `1`, and `5` appear in that section's prose rather than its
    table, so only their membership is checked here and their
    values stay ``test_errors``'s.
    """

    def _chunk(self):
        return _section(_spec_text(), "### Error classes and exit codes",
                        "## The run's output and failure")

    def _python_names(self):
        # The sentence is prose and wraps, so it is matched over the
        # section with its line breaks flattened to single spaces.
        flat = re.sub(r"\s+", " ", self._chunk())
        sentence = _PYTHON_SPELLING.search(flat)
        self.assertIsNotNone(
            sentence, "the spec no longer spells the classes in Python; "
            "this test reads that sentence.")
        return _BACKTICKED.findall(sentence.group(1))

    def test_the_taxonomy_holds_exactly_the_specified_classes(self):
        specified = set(self._python_names())
        implemented = {class_.__name__
                       for class_, _code, _name in errors._TAXONOMY}
        self.assertEqual(
            specified, implemented,
            "the run surface's exception classes differ from the ones "
            "docs/spec/script-spec.md names. The classes are the CLI's "
            "exit codes and the API's exceptions under one mapping.")

    def test_each_specified_class_is_a_reliquary_error(self):
        for name in self._python_names():
            with self.subTest(class_=name):
                class_ = getattr(errors, name, None)
                self.assertIsNotNone(
                    class_, f"the spec names {name} and errors.py has "
                    "no such class.")
                self.assertTrue(
                    issubclass(class_, errors.ReliquaryError),
                    f"{name} must subclass ReliquaryError: the root is "
                    "what makes `except ReliquaryError` the catch-all.")

    def test_the_tabled_exit_codes_are_the_ones_the_code_returns(self):
        # The table's class column is the prose spelling in capitals
        # ("STATIC ERROR"); the Python name is the same words joined.
        by_words = {_CAMEL_BREAK.sub(" ", name).upper(): name
                    for name in self._python_names()}
        rows = 0
        for header, body in _tables(self._chunk()):
            if "exit code" not in header:
                continue
            column = header.index("exit code")
            for row in body:
                name = by_words.get(row[header.index("class")])
                self.assertIsNotNone(
                    name, f"the table's class {row[0]!r} matches none "
                    "of the classes the same section spells in Python.")
                error = getattr(errors, name)
                self.assertEqual(
                    errors.exit_code(error("")), int(row[column]),
                    f"{name} exits with a code the spec's table does "
                    "not give it.")
                rows += 1
        self.assertTrue(rows, "the spec's exit-code table went missing.")


if __name__ == "__main__":
    unittest.main()
