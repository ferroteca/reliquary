# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The conformance corpus for the `.rlqs` scripting language.

P24's second conformance corpus, and the answer to the question
the defect actually asked — whether the blueprint corpus's pattern
generalizes. It does, to another document format, and it arrived
**stronger** than its parent: the script language had stable rule
ids, so an invalid fixture could assert *why* it was rejected
rather than only *that* it was, which the blueprint corpus could
not — its own README named the cost, a fixture failing for the
wrong reason being a false pass only a reviewer could catch.

**The parent has caught up** (2026-07-27). Blueprint diagnostics
carry ids now, so that corpus asserts its `// id:` line the same
way and the harness catches the false pass there too. What remains
different is the `# rule:` line: the script rules are V-numbered,
so an id here can be checked against the rule it is *meant* to
serve rather than only the one that fired. That is the assertion
the blueprint corpus still cannot make, and the reason is its
rules have no numbering to check against.

The ids are the dotted scheme D55 required and the static rules
now carry: a fixture names the diagnostic that must reject it —
`obs.two-channels`, the spec's own example — and the harness
compares it against the raised `rule_id`. It began as the
V-numbers, which was weaker in a way worth recording: a V-number
names a *rule* and several diagnostics live under each, so
asserting one could not tell six different failures apart.

Writing the corpus measured how far the ids reach, and drove them
further: it opened with four fixtures carrying `# id: none` and
now has none — every one of the 39 names the diagnostic that
rejects it. The preflight tier followed once D58 gave those
diagnostics a class worth naming a rule for, so
`invalid-at-preflight/` asserts a reason too rather than only
"parses clean" — which is what the bucket was always for.

One fixture carries `# caught-by:` instead. `v8-branching-with-a-
condition` exercises V8 and is rejected by the *grammar*, so its
id is `syn.unexpected-token` and the V8 arm in validation is
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

import collections
import glob
import os
import re
import tempfile
import unittest

import reliquary
from reliquary.binding import bind_properties
from reliquary.errors import PreflightError, ReliquaryError
from reliquary.home import Context
from reliquary.script_nodes import RULE_OF, ScriptParseError
from reliquary.script_parser import load_script
from reliquary.script_runner import _preflight_machine_rules

_CORPUS = os.path.join(os.path.dirname(__file__), "fixtures",
                       "conformance", "script")
_RULE = re.compile(r"^# rule: (V\d+)", re.M)
_ID = re.compile(r"^# id: (\S+)", re.M)
_CAUGHT_BY = re.compile(r"^# caught-by: (V\d+)", re.M)


def _fixtures(bucket):
    return sorted(glob.glob(os.path.join(_CORPUS, bucket, "*.rlqs")))


def _header(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _package_ids():
    """Every `rule_id="..."` in the package, with its occurrence count."""
    root = os.path.dirname(os.path.abspath(reliquary.__file__))
    counts = collections.Counter()
    for folder, _dirs, names in os.walk(root):
        for name in sorted(names):
            if not name.endswith(".py"):
                continue
            with open(os.path.join(folder, name), encoding="utf-8") as handle:
                counts.update(
                    re.findall(r'rule_id\s*=\s*"([^"]+)"', handle.read()))
    return counts


def _raised_counts():
    return _package_ids()


def _raised_subjects():
    return {rule_id.split(".", 1)[0] for rule_id in _package_ids()}


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

    def test_every_enforced_rule_has_a_fixture_exercising_it(self):
        """Rule coverage, measured from the corpus rather than the spec.

        `RULE_OF`'s range is the static tier's rule universe: every
        V-number some diagnostic enforces. A rule with no invalid
        fixture is enforcement nothing exercises — the V13 class,
        which reached the guest loop as an untyped fault because
        nothing had ever driven the rule it violated. (Whether the
        code enforces every rule the *prose spec* states is R3's
        audit, planning/RECURRING.md.)
        """
        exercised = {_RULE.search(_header(path)).group(1)
                     for path in _fixtures("invalid")}
        served = {rule for rule in RULE_OF.values() if rule}
        unexercised = sorted(served - exercised)
        self.assertEqual(
            unexercised, [],
            f"{unexercised} are enforced rules no invalid fixture "
            "exercises. Add one per rule — a rejection nothing "
            "drives is enforcement only by reading the code.")

    def test_every_exercised_rule_is_one_the_code_enforces(self):
        """The reverse: a fixture may not exercise a phantom rule.

        A `# rule:` naming a V-number nothing serves is either a
        typo or a rule whose enforcement was deleted; `# caught-by:`
        is the one sanctioned exception, asserted above.
        """
        served = {rule for rule in RULE_OF.values() if rule}
        for path in _fixtures("invalid"):
            text = _header(path)
            rule = _RULE.search(text).group(1)
            if _CAUGHT_BY.search(text):
                continue
            with self.subTest(fixture=os.path.basename(path)):
                self.assertIn(
                    rule, served,
                    f"{rule} is exercised here and no diagnostic "
                    "serves it.")

    def test_one_rule_keeps_one_id_across_surfaces(self):
        """The subject rule's payoff, asserted rather than described.

        Each of these is one rule raised from more than one module,
        and the id is the rule's rather than the site's. If a future
        change gives any of them a second id, a consumer switching
        on it starts having to know which layer noticed — which is
        exactly what the id was for.
        """
        shared = {
            "machine.not-running": 3,
            "machine.no-selector": 3,
            "machine.no-vm-identity": 3,
            "media.unknown": 2,
            "name.duplicate-property": 2,
            "name.property-reserved-namespace": 2,
            "platform.verb-not-implemented": 2,
        }
        counts = _raised_counts()
        for rule_id, least in sorted(shared.items()):
            with self.subTest(id=rule_id):
                self.assertGreaterEqual(
                    counts[rule_id], least,
                    f"{rule_id} is raised from {counts[rule_id]} "
                    f"place(s) and should reach at least {least}. If a "
                    "site was renamed to its own id, one rule now has "
                    "two names.")

    def test_rule_of_holds_exactly_the_ids_the_static_tier_raises(self):
        """The id-to-rule map is neither short nor imaginary.

        `RULE_OF` is what a consumer switching on an id reads, and
        what the unit tests assert through. An id raised but
        unmapped would report no rule; a mapped id nothing raises
        is an entry naming a diagnostic that cannot occur.

        The three modules scanned are the **static tier**, and that
        is the whole map by construction: `RULE_OF` maps an id to
        the V-numbered restriction it enforces, and V-numbers name
        syntactic restrictions only. A preflight or runtime id —
        `machine.slot-not-declared`, `media.unknown` — enforces a
        machine rule or the dynamic semantics, which have no
        V-number to map to. Absent from `RULE_OF` is therefore
        correct for them rather than a gap, and widening this scan
        would demand entries that could only be invented.
        """
        raised = set()
        package = os.path.dirname(os.path.abspath(reliquary.__file__))
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

    This bucket used to assert only that a fixture *parses* — all it
    could, while preflight diagnostics carried no ids. They do now, so
    it asserts the reason as well, which is the whole point of the
    bucket: a fixture that parses clean and is then rejected for the
    wrong reason was previously indistinguishable from one rejected
    for the right one.
    """

    #: A machine declaring one slot of each kind, each carrying the
    #: `medium` its removability is read from. The fixtures name
    #: `cdrom7`, `hdd6` and the like precisely because nothing
    #: plausible declares them.
    MACHINE = {"drives": {"floppy0": {"medium": "floppy"},
                          "cdrom0": {"medium": "cdrom"},
                          "hdd0": {"medium": "hdd"}}}

    def _preflight(self, path):
        """Run preflight over a fixture, returning what it raised.

        Both halves run, in the order a real invocation does: the
        machine rules first, then property binding with no asker,
        which is what `--progress plain` and every program driving
        the CLI get. A fixture declares the one id that must come
        out, so which half noticed is the harness's business rather
        than the fixture's.
        """
        script = load_script(path)
        with tempfile.TemporaryDirectory() as empty:
            context = Context(home_dir=empty, blueprints_dir=empty,
                              scripts_dir=empty)
            try:
                _preflight_machine_rules(
                    script, self.MACHINE, path, context)
                bind_properties(script, context=context, asker=None)
            except ReliquaryError as raised:
                return raised
        return None

    def test_preflight_fixtures_parse_clean(self):
        paths = _fixtures("invalid-at-preflight")
        self.assertTrue(paths, "no preflight fixtures found")
        for path in paths:
            with self.subTest(fixture=os.path.basename(path)):
                load_script(path)

    def test_every_preflight_fixture_names_its_id(self):
        for path in _fixtures("invalid-at-preflight"):
            with self.subTest(fixture=os.path.basename(path)):
                self.assertIsNotNone(
                    _ID.search(_header(path)),
                    "a preflight fixture names the diagnostic id that "
                    "must reject it, or `none` where none exists yet.")

    def test_a_preflight_rejection_carries_the_declared_id(self):
        """The assertion this bucket could not make until D58.

        Asserted in both directions, like the parse bucket's: a
        fixture claiming `none` whose diagnostic has since gained an
        id fails here until its header catches up.
        """
        for path in _fixtures("invalid-at-preflight"):
            declared = _ID.search(_header(path)).group(1)
            with self.subTest(fixture=os.path.basename(path)):
                raised = self._preflight(path)
                self.assertIsNotNone(
                    raised,
                    "this fixture is in the preflight bucket and "
                    "preflight accepted it. Either it belongs in "
                    "`valid/`, or the rule it exercises is unenforced.")
                if declared == "none":
                    self.assertIsNone(
                        raised.rule_id,
                        f"this fixture records no id and the diagnostic "
                        f"now carries {raised.rule_id!r}. Put it in the "
                        "header — the marker records a gap that closed.")
                else:
                    self.assertEqual(
                        raised.rule_id, declared,
                        "rejected by preflight, but not by the rule this "
                        "fixture names. Failing for the wrong reason is "
                        "a false pass.")

    def test_a_preflight_rejection_is_the_preflight_class(self):
        """Rejected *at preflight* is the bucket's claim, not just late.

        A fixture rejected by a RUN FAILURE would be in the wrong
        bucket, and one rejected by a STATIC ERROR would mean the
        parse bucket should have caught it.
        """
        for path in _fixtures("invalid-at-preflight"):
            with self.subTest(fixture=os.path.basename(path)):
                self.assertIsInstance(self._preflight(path), PreflightError)


if __name__ == "__main__":
    unittest.main()
