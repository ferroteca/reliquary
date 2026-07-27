# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""The conformance corpus for the `.rlqs` scripting language.

P24's second conformance corpus, and the answer to the question
the defect actually asked — whether the blueprint corpus's pattern
generalizes. It does, to another document format, and it arrives
**stronger** than its parent: the script language has stable rule
ids, so an invalid fixture can assert *why* it was rejected rather
than only *that* it was. The blueprint corpus cannot, and its own
README names the cost — "an invalid fixture that fails for the
wrong reason is a false pass, and the header is what lets a
reviewer catch that". Here the harness catches it instead of a
reviewer.

The ids are the dotted scheme D55 required and the static rules
now carry: a fixture names the diagnostic that must reject it —
`obs.two-channels`, the spec's own example — and the harness
compares it against the raised `rule_id`. It began as the
S-numbers, which was weaker in a way worth recording: an S-number
names a *rule* and several diagnostics live under each, so
asserting one could not tell six different failures apart.

Writing the corpus measured how far the ids reach. Four of the 39
invalid fixtures still cannot name one and carry `# id: none`:
the two lexical/grammar rejections, the header-cardinality
diagnostic, and the branching-wait shape the grammar catches
before validation. Those are D55's remainder, measured rather
than estimated.

Every marker is asserted in **both** directions. A fixture
naming an id must be rejected by exactly that id; a fixture
saying `none` must be rejected by a diagnostic that still has
none — so the day an id lands, this suite fails until the header
is updated. An exemption cannot outlive the gap it records, which
is the difference between naming a gap and quietly keeping one.
"""

import glob
import os
import re
import unittest

from reliquary.script_nodes import RULE_OF, ScriptParseError
from reliquary.script_parser import load_script

_CORPUS = os.path.join(os.path.dirname(__file__), "fixtures",
                       "conformance", "script")
_RULE = re.compile(r"^# rule: (S\d+)", re.M)
_ID = re.compile(r"^# id: (\S+)", re.M)
_SPEC = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "docs", "spec", "script-spec.md")
_DOTTED = re.compile(r"`([a-z]+\.[a-z-]+)`")


def _fixtures(bucket):
    return sorted(glob.glob(os.path.join(_CORPUS, bucket, "*.rlqs")))


def _header(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class ValidCorpusTests(unittest.TestCase):
    def test_every_valid_fixture_parses(self):
        paths = _fixtures("valid")
        self.assertTrue(paths, "no valid script fixtures found")
        for path in paths:
            with self.subTest(fixture=os.path.basename(path)):
                load_script(path)


class InvalidCorpusTests(unittest.TestCase):
    def test_every_invalid_fixture_is_rejected(self):
        paths = _fixtures("invalid")
        self.assertTrue(paths, "no invalid script fixtures found")
        for path in paths:
            with self.subTest(fixture=os.path.basename(path)):
                with self.assertRaises(ScriptParseError):
                    load_script(path)

    def test_every_fixture_declares_the_rule_and_id_it_exercises(self):
        for path in _fixtures("invalid"):
            text = _header(path)
            with self.subTest(fixture=os.path.basename(path)):
                self.assertIsNotNone(
                    _RULE.search(text),
                    "an invalid fixture names the rule it exercises, so "
                    "a reader can tell a true rejection from a lucky one.")
                self.assertIsNotNone(
                    _ID.search(text),
                    "an invalid fixture names the diagnostic id that must "
                    "reject it, or `none` where no id exists yet.")

    def test_a_rejection_carries_the_id_the_fixture_declares(self):
        """The assertion the blueprint corpus could not make.

        `# id: none` is how a fixture records a diagnostic with no
        identifier yet, and it is asserted in the same breath as
        its opposite: a fixture claiming `none` whose diagnostic
        has since gained an id fails here until its header is
        updated. The marker cannot outlive the gap it records.
        """
        for path in _fixtures("invalid"):
            declared = _ID.search(_header(path)).group(1)
            with self.subTest(fixture=os.path.basename(path)):
                with self.assertRaises(ScriptParseError) as caught:
                    load_script(path)
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

    def test_every_declared_id_is_listed_under_its_rule_in_the_spec(self):
        """The id and the S-number it serves are one mapping.

        Ids are finer than the S-rules — S7 is one restriction and
        `obs.two-channels` is one of six diagnostics under it — so
        the spec's rule list carries the mapping and this holds the
        two together. Without it the prefixes would drift into
        whatever each new diagnostic felt like.
        """
        with open(_SPEC, encoding="utf-8") as handle:
            spec = handle.read()
        for path in _fixtures("invalid"):
            text = _header(path)
            declared = _ID.search(text).group(1)
            if declared == "none":
                continue
            rule = _RULE.search(text).group(1)
            start = spec.index(f"- **{rule}** —")
            end = spec.index("\n- **", start + 1) if f"\n- **" in \
                spec[start + 1:] else len(spec)
            with self.subTest(id=declared, rule=rule):
                self.assertIn(
                    f"`{declared}`", spec[start:end],
                    f"{declared} is not listed under {rule} in "
                    "docs/spec/script-spec.md. An id names one "
                    "diagnostic of one rule, and the rule list is "
                    "where a reader crosses between them.")

    def test_the_spec_lists_no_id_the_code_does_not_raise(self):
        """The reverse: a listed id that nothing raises is fiction."""
        with open(_SPEC, encoding="utf-8") as handle:
            spec = handle.read()
        start = spec.index("- **S1** —")
        end = spec.index("\nThe grammar is line-oriented", start)
        listed = set(_DOTTED.findall(spec[start:end]))
        raised = set()
        package = os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))
        for name in ("script_validation.py", "script_parser.py",
                     "script_nodes.py"):
            with open(os.path.join(package, "reliquary", name),
                      encoding="utf-8") as handle:
                raised.update(re.findall(r'rule_id="([^"]+)"',
                                         handle.read()))
        self.assertEqual(
            sorted(listed - raised), [],
            "these ids are listed under an S-rule and no diagnostic "
            "raises them. A rule list naming ids that cannot occur is "
            "the same defect as a spec naming a command that does not "
            "exist.")

    def test_rule_of_holds_exactly_the_ids_the_code_raises(self):
        """The id-to-rule map is neither short nor imaginary.

        `RULE_OF` is what a consumer switching on an id reads, and
        what the unit tests assert through. An id raised but
        unmapped would report no rule; a mapped id nothing raises
        is an entry naming a diagnostic that cannot occur.
        """
        raised = set()
        package = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "reliquary")
        for name in ("script_validation.py", "script_parser.py",
                     "script_nodes.py"):
            with open(os.path.join(package, name),
                      encoding="utf-8") as handle:
                raised.update(re.findall(r'rule_id="([^"]+)"',
                                         handle.read()))
        self.assertEqual(sorted(raised), sorted(RULE_OF))

    def test_the_unidentified_count_is_what_the_readme_records(self):
        """The measurement is the point; a silent drift in it is not.

        D55 is open against the missing identifier scheme and this
        number is the evidence under it. It moves down as ids land;
        moving up means a diagnostic lost one.
        """
        unidentified = sorted(
            os.path.basename(path) for path in _fixtures("invalid")
            if _ID.search(_header(path)).group(1) == "none")
        self.assertEqual(
            len(unidentified), 4,
            f"the unidentified fixtures are now {unidentified}. Update "
            "this count and the tally in the corpus README together — "
            "the README states it as evidence for D55.")


class PreflightCorpusTests(unittest.TestCase):
    """These parse clean and are rejected later, with more in scope.

    Exactly the blueprint corpus's third bucket, for exactly its
    reason: a fixture whose rule needs a machine, a namespace or an
    invocation would fail a parse-time assertion for the wrong
    reason, and separating it is honester than weakening it.
    """

    def test_preflight_fixtures_parse_clean(self):
        paths = _fixtures("invalid-at-preflight")
        self.assertTrue(paths, "no preflight fixtures found")
        for path in paths:
            with self.subTest(fixture=os.path.basename(path)):
                load_script(path)


if __name__ == "__main__":
    unittest.main()
