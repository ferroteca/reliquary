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
now has none — every one of the 46 names the diagnostic that
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

**Every fixture is a collected node**, through `tests/corpus.py` —
the helper the blueprint corpus reads through, because the
guarantee belongs to the harness rather than to a document format
(D106). A node carries its file's name, so a failing fixture is
run alone with `-k v7-two-channels.rlqs`, and the bucket counts
are pinned where the fixtures are gathered.
"""

import collections
import os
import re

import pytest

import reliquary
from reliquary.binding import bind_properties
from reliquary.errors import PreflightError, ReliquaryError
from reliquary.home import Context
from reliquary.script_nodes import RULE_OF, ScriptParseError
from reliquary.script_parser import load_script
from reliquary.script_runner import _preflight_machine_rules
from tests import corpus

_CORPUS = os.path.join(os.path.dirname(__file__), "fixtures",
                       "conformance", "script")
_RULE = re.compile(r"^# rule: (V\d+)", re.M)
_ID = re.compile(r"^# id: (\S+)", re.M)
_CAUGHT_BY = re.compile(r"^# caught-by: (V\d+)", re.M)

VALID = corpus.fixtures(_CORPUS, "valid", ".rlqs", count=21)
INVALID = corpus.fixtures(_CORPUS, "invalid", ".rlqs", count=52)
AT_PREFLIGHT = corpus.fixtures(
    _CORPUS, "invalid-at-preflight", ".rlqs", count=6)

#: A machine declaring one slot of each kind, each carrying the
#: `medium` its removability is read from. The fixtures name
#: `cdrom7`, `hdd6` and the like precisely because nothing
#: plausible declares them.
MACHINE = {"drives": {"floppy0": {"medium": "floppy"},
                      "cdrom0": {"medium": "cdrom"},
                      "hdd0": {"medium": "hdd"}}}


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


@corpus.parametrize(VALID)
def test_a_valid_fixture_parses(fixture):
    load_script(fixture)


@corpus.parametrize(INVALID)
def test_an_invalid_fixture_is_rejected(fixture):
    with pytest.raises(ScriptParseError):
        load_script(fixture)


@corpus.parametrize(INVALID)
def test_an_invalid_fixture_declares_the_rule_and_id_it_exercises(fixture):
    text = _header(fixture)
    assert _RULE.search(text) is not None, (
        "an invalid fixture names the rule it exercises, so a reader "
        "can tell a true rejection from a lucky one.")
    assert _ID.search(text) is not None, (
        "an invalid fixture names the diagnostic id that must reject "
        "it, or `none` where no id exists yet.")


@corpus.parametrize(INVALID)
def test_a_rejection_carries_the_id_the_fixture_declares(fixture):
    """The assertion the blueprint corpus could not make.

    `# id: none` is how a fixture records a diagnostic with no
    identifier yet, and it is asserted in the same breath as
    its opposite: a fixture claiming `none` whose diagnostic
    has since gained an id fails here until its header is
    updated. The marker cannot outlive the gap it records.
    """
    declared = _ID.search(_header(fixture)).group(1)
    with pytest.raises(ScriptParseError) as caught:
        load_script(fixture)
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


@corpus.parametrize(INVALID)
def test_the_id_serves_the_rule_the_fixture_exercises(fixture):
    """The rule a fixture exercises is the rule its id enforces.

    `# rule:` is what the script violates; `# id:` is what
    rejected it. They normally agree, and where they do not the
    fixture says so with `# caught-by:` — a layer caught the
    script before the rule's own diagnostic could. That is a
    real defect, not a labelling convenience, so the marker is
    asserted in both directions and retires itself when the
    layers are fixed.
    """
    text = _header(fixture)
    declared, rule = _ID.search(text).group(1), _RULE.search(text).group(1)
    caught = _CAUGHT_BY.search(text)
    serves = RULE_OF.get(declared)
    if caught:
        assert serves != rule, (
            f"this fixture says {rule} cannot catch it and {declared} "
            f"now serves {rule}. Delete the `# caught-by:` line — it "
            "records a defect, and the defect is fixed.")
        assert serves == caught.group(1)
    else:
        assert serves == rule, (
            f"{declared} enforces {serves}, and this fixture exercises "
            f"{rule}. Either the id is filed under the wrong rule, or "
            "a layer is catching this before the rule can — which is a "
            "`# caught-by:` finding, not a mismatch to shrug at.")


@corpus.parametrize(INVALID)
def test_an_exercised_rule_is_one_the_code_enforces(fixture):
    """The reverse: a fixture may not exercise a phantom rule.

    A `# rule:` naming a V-number nothing serves is either a
    typo or a rule whose enforcement was deleted; `# caught-by:`
    is the one sanctioned exception, and it is the exception
    *inside* this assertion rather than a fixture filtered out of
    it — a check nothing collects reports nothing. What that
    marker means is asserted in both directions above.
    """
    text = _header(fixture)
    rule = _RULE.search(text).group(1)
    served = {served_rule for served_rule in RULE_OF.values() if served_rule}
    assert rule in served or _CAUGHT_BY.search(text), (
        f"{rule} is exercised here and no diagnostic serves it.")


def test_every_enforced_rule_has_a_fixture_exercising_it():
    """Rule coverage, measured from the corpus rather than the spec.

    `RULE_OF`'s range is the static tier's rule universe: every
    V-number some diagnostic enforces. A rule with no invalid
    fixture is enforcement nothing exercises — the V13 class,
    which reached the guest loop as an untyped fault because
    nothing had ever driven the rule it violated. (Whether the
    code enforces every rule the *prose spec* states is R3's
    audit, planning/RECURRING.md.)
    """
    exercised = {_RULE.search(_header(path)).group(1) for path in INVALID}
    served = {rule for rule in RULE_OF.values() if rule}
    unexercised = sorted(served - exercised)
    assert unexercised == [], (
        f"{unexercised} are enforced rules no invalid fixture "
        "exercises. Add one per rule — a rejection nothing drives is "
        "enforcement only by reading the code.")


#: Each of these is one rule raised from more than one module, with
#: the number of sites the id must still cover.
SHARED_IDS = {
    # V17 put a *static* site on the machine layer's own rule rather
    # than inventing a second name for it, which is the pattern this
    # check exists to hold: one condition, one answer, whichever
    # layer noticed.
    "machine.must-be-stopped": 5,
    "machine.not-running": 3,
    "machine.no-selector": 3,
    "machine.no-vm-identity": 3,
    "media.unknown": 2,
    "name.duplicate-property": 2,
    "name.property-reserved-namespace": 2,
}


@pytest.mark.parametrize("rule_id,least", sorted(SHARED_IDS.items()))
def test_one_rule_keeps_one_id_across_surfaces(rule_id, least):
    """The subject rule's payoff, asserted rather than described.

    Each of these is one rule raised from more than one module, and
    the id is the rule's rather than the site's. If a future change
    gives any of them a second id, a consumer switching on it starts
    having to know which layer noticed — which is exactly what the id
    was for.
    """
    counts = _package_ids()
    assert counts[rule_id] >= least, (
        f"{rule_id} is raised from {counts[rule_id]} place(s) and "
        f"should reach at least {least}. If a site was renamed to its "
        "own id, one rule now has two names.")


def test_rule_of_holds_exactly_the_ids_the_static_tier_raises():
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
        with open(os.path.join(package, name), encoding="utf-8") as handle:
            raised.update(re.findall(r'rule_id\s*=\s*"([^"]+)"',
                                     handle.read()))
    assert sorted(raised) == sorted(RULE_OF)


def test_the_unidentified_count_is_what_the_readme_records():
    """The measurement is the point; a silent drift in it is not.

    D55 is open against the missing identifier scheme and this
    number is the evidence under it. It moves down as ids land;
    moving up means a diagnostic lost one.
    """
    unidentified = sorted(
        os.path.basename(path) for path in INVALID
        if _ID.search(_header(path)).group(1) == "none")
    assert len(unidentified) == 0, (
        f"the unidentified fixtures are now {unidentified}. Update "
        "this count and the tally in the corpus README together — the "
        "README states it as evidence for D55.")


# The preflight bucket. These parse clean and are rejected later, with
# more in scope — exactly the blueprint corpus's third bucket, for
# exactly its reason: a fixture whose rule needs a machine, a namespace
# or an invocation would fail a parse-time assertion for the wrong
# reason, and separating it is honester than weakening it.
#
# It used to assert only that a fixture *parses* — all it could, while
# preflight diagnostics carried no ids. They do now, so it asserts the
# reason as well, which is the whole point of the bucket: a fixture
# that parses clean and is then rejected for the wrong reason was
# previously indistinguishable from one rejected for the right one.


def _preflight(path, empty):
    """Run preflight over a fixture, returning what it raised.

    Both halves run, in the order a real invocation does: the
    machine rules first, then property binding with no asker,
    which is what `--progress plain` and every program driving
    the CLI get. A fixture declares the one id that must come
    out, so which half noticed is the harness's business rather
    than the fixture's.
    """
    script = load_script(path)
    context = Context(home_dir=empty, blueprints_dir=empty,
                      scripts_dir=empty)
    try:
        _preflight_machine_rules(script, MACHINE, path, context)
        bind_properties(script, context=context, asker=None)
    except ReliquaryError as raised:
        return raised
    return None


@corpus.parametrize(AT_PREFLIGHT)
def test_a_preflight_fixture_parses_clean(fixture):
    load_script(fixture)


@corpus.parametrize(AT_PREFLIGHT)
def test_a_preflight_fixture_names_its_id(fixture):
    assert _ID.search(_header(fixture)) is not None, (
        "a preflight fixture names the diagnostic id that must reject "
        "it, or `none` where none exists yet.")


@corpus.parametrize(AT_PREFLIGHT)
def test_a_preflight_rejection_carries_the_declared_id(fixture, tmp_path):
    """The assertion this bucket could not make until D58.

    Asserted in both directions, like the parse bucket's: a
    fixture claiming `none` whose diagnostic has since gained an
    id fails here until its header catches up.
    """
    declared = _ID.search(_header(fixture)).group(1)
    raised = _preflight(fixture, str(tmp_path))
    assert raised is not None, (
        "this fixture is in the preflight bucket and preflight "
        "accepted it. Either it belongs in `valid/`, or the rule it "
        "exercises is unenforced.")
    if declared == "none":
        assert raised.rule_id is None, (
            f"this fixture records no id and the diagnostic now "
            f"carries {raised.rule_id!r}. Put it in the header — the "
            "marker records a gap that closed.")
    else:
        assert raised.rule_id == declared, (
            "rejected by preflight, but not by the rule this fixture "
            "names. Failing for the wrong reason is a false pass.")


@corpus.parametrize(AT_PREFLIGHT)
def test_a_preflight_rejection_is_the_preflight_class(fixture, tmp_path):
    """Rejected *at preflight* is the bucket's claim, not just late.

    A fixture rejected by a RUN FAILURE would be in the wrong
    bucket, and one rejected by a STATIC ERROR would mean the
    parse bucket should have caught it.
    """
    assert isinstance(_preflight(fixture, str(tmp_path)), PreflightError)
