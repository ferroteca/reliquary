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

Writing the corpus measured how far the ids reach, and drove them
further: it opened with four fixtures carrying `# id: none` and
now has none — every one of the 39 names the diagnostic that
rejects it. What remains unidentified is the preflight and
runtime tiers, which no parse fixture can reach.

One fixture carries `# caught-by:` instead. `s8-branching-with-a-
condition` exercises S8 and is rejected by the *grammar*, so its
id is `syn.unexpected-token` and the S8 arm in validation is
unreachable. That is a defect the corpus found and now asserts
rather than describes.

Every marker is asserted in **both** directions. A fixture naming
an id must be rejected by exactly that id; one saying `none` must
be rejected by a diagnostic that still has none; one claiming a
layer catches it early must still be caught early. So the day the
gap closes, this suite fails until the marker goes. An exemption
cannot outlive what it records, which is the difference between
naming a gap and quietly keeping one.
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
_CAUGHT_BY = re.compile(r"^# caught-by: (S\d+)", re.M)


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

    def test_the_id_serves_the_rule_the_fixture_exercises(self):
        """The rule a fixture exercises is the rule its id enforces.

        `# rule:` is what the script violates; `# id:` is what
        rejected it. They normally agree, and where they do not the
        fixture says so with `# caught-by:` — a layer caught the
        script before the rule's own diagnostic could. That is a
        real defect, not a labelling convenience, so the marker is
        asserted in both directions and retires itself when the
        layers are fixed.
        """
        for path in _fixtures("invalid"):
            text = _header(path)
            declared, rule = _ID.search(text).group(1), \
                _RULE.search(text).group(1)
            caught = _CAUGHT_BY.search(text)
            with self.subTest(fixture=os.path.basename(path)):
                serves = RULE_OF.get(declared)
                if caught:
                    self.assertNotEqual(
                        serves, rule,
                        f"this fixture says {rule} cannot catch it and "
                        f"{declared} now serves {rule}. Delete the "
                        "`# caught-by:` line — it records a defect, "
                        "and the defect is fixed.")
                    self.assertEqual(serves, caught.group(1))
                else:
                    self.assertEqual(
                        serves, rule,
                        f"{declared} enforces {serves}, and this "
                        f"fixture exercises {rule}. Either the id is "
                        "filed under the wrong rule, or a layer is "
                        "catching this before the rule can — which "
                        "is a `# caught-by:` finding, not a mismatch "
                        "to shrug at.")

    def test_every_declared_id_is_listed_in_the_spec(self):
        """Every id the corpus names appears in the spec's rule list.

        Ids are finer than the S-rules — S7 is one restriction and
        `obs.two-channels` is one of six diagnostics under it — so
        the spec's rule list carries the mapping and this holds the
        two together. Without it the prefixes would drift into
        whatever each new diagnostic felt like.
        """
        with open(_SPEC, encoding="utf-8") as handle:
            spec = handle.read()
        start = spec.index("- **S1** —")
        end = spec.index("\nThe grammar is line-oriented", start)
        listed = set(_DOTTED.findall(spec[start:end]))
        for path in _fixtures("invalid"):
            declared = _ID.search(_header(path)).group(1)
            with self.subTest(id=declared):
                self.assertIn(
                    declared, listed,
                    f"{declared} rejects a corpus fixture and appears "
                    "in no S-rule's id list in "
                    "docs/spec/script-spec.md.")

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
                raised.update(re.findall(r'rule_id\s*=\s*"([^"]+)"',
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
                raised.update(re.findall(r'rule_id\s*=\s*"([^"]+)"',
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
            len(unidentified), 0,
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
