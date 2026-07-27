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

That difference is not free, and it is not free here either.
Writing the corpus measured exactly how far the ids reach: six of
the thirty-nine invalid fixtures cannot name their rule, and each
carries a `# cites: no` line saying why. Five are the D55 defect —
parse errors, header cardinality, and duplicate modifiers carry no
identifier at all, though script-spec.md requires one of *every*
diagnostic. The sixth is a different finding, recorded in the
corpus README.

The markers are asserted in **both** directions. A fixture without
`# cites: no` must name its rule, and a fixture with it must
*not* — so the day an id lands, this suite fails and the marker
has to be removed. The exemption cannot outlive the gap it
records, which is the difference between naming a gap and
quietly keeping one.
"""

import glob
import os
import re
import unittest

from reliquary.script_nodes import ScriptParseError
from reliquary.script_parser import load_script

_CORPUS = os.path.join(os.path.dirname(__file__), "fixtures",
                       "conformance", "script")
_RULE = re.compile(r"^# rule: (S\d+)", re.M)
_UNCITED = re.compile(r"^# cites: no\b", re.M)


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

    def test_every_fixture_declares_the_rule_it_exercises(self):
        for path in _fixtures("invalid"):
            with self.subTest(fixture=os.path.basename(path)):
                self.assertIsNotNone(
                    _RULE.search(_header(path)),
                    "an invalid fixture names the rule it exercises, so "
                    "a reader can tell a true rejection from a lucky one.")

    def test_a_rejection_cites_the_rule_the_fixture_declares(self):
        """The assertion the blueprint corpus could not make."""
        for path in _fixtures("invalid"):
            text = _header(path)
            if _UNCITED.search(text):
                continue
            rule = _RULE.search(text).group(1)
            with self.subTest(fixture=os.path.basename(path), rule=rule):
                with self.assertRaises(ScriptParseError) as caught:
                    load_script(path)
                self.assertIn(
                    f"({rule})", caught.exception.message,
                    f"rejected, but not by {rule}. A fixture failing for "
                    "the wrong reason is a false pass: it would keep "
                    "passing after the rule it names stopped working.")

    def test_an_uncited_marker_still_describes_the_truth(self):
        """`# cites: no` retires itself when the id arrives.

        Asserted in the same breath as its opposite so the marker
        can never become a permanent exemption: a fixture claiming
        its rule is uncited, whose diagnostic has since learned to
        cite it, fails here until the marker goes.
        """
        for path in _fixtures("invalid"):
            text = _header(path)
            if not _UNCITED.search(text):
                continue
            rule = _RULE.search(text).group(1)
            with self.subTest(fixture=os.path.basename(path), rule=rule):
                with self.assertRaises(ScriptParseError) as caught:
                    load_script(path)
                self.assertNotIn(
                    f"({rule})", caught.exception.message,
                    f"this fixture is marked as unable to cite {rule} and "
                    "now cites it. Delete the `# cites: no` line — the "
                    "marker records a gap, and the gap has closed.")

    def test_the_uncited_count_is_what_the_corpus_readme_records(self):
        """The measurement is the point; a silent drift in it is not.

        D55 is open against the missing identifier scheme, and this
        number is the evidence under it. It moves in one direction
        as ids land; it moving the other way means a diagnostic lost
        its id.
        """
        uncited = sorted(
            os.path.basename(path) for path in _fixtures("invalid")
            if _UNCITED.search(_header(path)))
        self.assertEqual(
            len(uncited), 6,
            f"the uncited fixtures are now {uncited}. Update the count "
            "here and the tally in the corpus README together — the "
            "README states it as evidence for D55.")


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
