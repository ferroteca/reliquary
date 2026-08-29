# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The conformance corpus for the `.rlqs` scripting language.

P24's second conformance corpus. It answers the question the
defect actually raised: whether the blueprint corpus's approach
generalizes to another document format. It does, and it went
further than the blueprint corpus could: the script language has
stable rule ids, so an invalid fixture can assert why it was
rejected, not just that it was. The blueprint corpus's own README
named the cost of not doing this — a fixture failing for the wrong
reason is a false pass that only a human reviewer would catch.

The blueprint corpus has since caught up (2026-07-27): its
diagnostics carry ids now too, so it asserts its `// id:` line the
same way and catches the same false pass. What is still different
is the `# rule:` line. Script rules are V-numbered, so an id here
can be checked against the specific rule it is meant to serve, not
just whichever rule happened to fire. The blueprint corpus still
cannot make that check, because its rules have no numbering to
check against.

The ids follow the dotted naming scheme D55 required, which the
static rules now carry: a fixture names the specific diagnostic
that must reject it — `obs.two-channels`, the spec's own example —
and the harness compares that against the raised `rule_id`. Before
this, fixtures asserted against V-numbers instead, which was
weaker: a V-number names a rule, and several diagnostics can live
under one rule, so asserting the V-number alone could not tell six
different failures under it apart.

Writing the corpus measured how many diagnostics had ids, and
pushed that further: it opened with four fixtures carrying `# id:
none` and now has none — all 46 name the diagnostic that rejects
them. The preflight tier followed the same pattern once D58 gave
those diagnostics rule ids worth naming, so `invalid-at-preflight/`
now asserts a reason too, instead of only "parses clean" — which is
what the bucket was always meant to check.

One fixture carries `# caught-by:` instead. `v8-branching-with-a-
condition` exercises V8, but is rejected by the grammar, so its id
is `syn.unexpected-token` and the V8 arm in validation is
unreachable. This is a real defect the corpus found, and now
asserts rather than just describes.

Every marker is asserted in **both** directions. A fixture naming
an id must be rejected by exactly that id; one saying `none` must
be rejected by a diagnostic that still has none; one claiming a
layer catches it early must still be caught early. So the day the
gap closes, this suite fails until the marker goes. An exemption
cannot outlive what it records, which is the difference between
naming a gap and quietly keeping one.

Every fixture is collected as its own pytest node, through
`tests/corpus.py` — the same helper the blueprint corpus reads
through, because this guarantee belongs to the harness rather than
to any one document format (D106). A node carries its file's name,
so a failing fixture can be run alone with `-k
v7-two-channels.rlqs`, and the bucket counts are pinned where the
fixtures are gathered.
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

VALID = corpus.fixtures(_CORPUS, "valid", ".rlqs", count=22)
INVALID = corpus.fixtures(_CORPUS, "invalid", ".rlqs", count=53)
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
    """Check the id a rejected fixture declares against the id actually raised.

    `# id: none` is how a fixture records a diagnostic with no
    identifier yet, and both directions are checked here: a fixture
    claiming `none` whose diagnostic has since gained an id fails
    until its header is updated. The marker cannot outlive the gap
    it records.
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
    """The reverse: a fixture may not exercise a rule nothing enforces.

    A `# rule:` naming a V-number that nothing serves is either a
    typo, or a rule whose enforcement was deleted. `# caught-by:` is
    the one allowed exception, and it is handled inside this
    assertion rather than by filtering that fixture out beforehand —
    a fixture excluded from the check could never fail it. What
    `# caught-by:` means is asserted in both directions above.
    """
    text = _header(fixture)
    rule = _RULE.search(text).group(1)
    served = {served_rule for served_rule in RULE_OF.values() if served_rule}
    assert rule in served or _CAUGHT_BY.search(text), (
        f"{rule} is exercised here and no diagnostic serves it.")


def test_every_enforced_rule_has_a_fixture_exercising_it():
    """Rule coverage, measured from the corpus rather than the spec.

    `RULE_OF`'s range is the static tier's whole rule universe:
    every V-number some diagnostic enforces. A rule with no invalid
    fixture is enforcement that nothing exercises in tests — this is
    exactly what happened with the V13 class, which reached the
    guest loop as an untyped fault because nothing had ever tested
    the rule it violated. (Whether the code enforces every rule the
    prose spec states is a separate audit, R3, tracked in
    planning/RECURRING.md.)
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
    # When V17 added a static-tier check for a rule that already
    # belonged to the machine layer, it reused the machine layer's
    # existing id instead of inventing a second one. That is the
    # pattern this check exists to hold: one condition, one id,
    # whichever layer notices it. `destroy_machine` used to be a
    # fifth site raising this id, until `destroy` started stopping a
    # running machine itself instead of refusing to.
    "machine.must-be-stopped": 4,
    "machine.not-running": 3,
    "machine.no-selector": 3,
    "machine.no-vm-identity": 3,
    "media.unknown": 2,
    "name.duplicate-property": 2,
    "name.property-reserved-namespace": 2,
}


@pytest.mark.parametrize("rule_id,least", sorted(SHARED_IDS.items()))
def test_one_rule_keeps_one_id_across_surfaces(rule_id, least):
    """Each shared rule keeps exactly one id across every module that raises it.

    Each of these is one rule raised from more than one module, and
    the id belongs to the rule, not to the site that raised it. If a
    future change gives any of them a second id, code that switches
    on the id would have to start knowing which layer noticed —
    which is exactly what having one shared id was meant to prevent.
    """
    counts = _package_ids()
    assert counts[rule_id] >= least, (
        f"{rule_id} is raised from {counts[rule_id]} place(s) and "
        f"should reach at least {least}. If a site was renamed to its "
        "own id, one rule now has two names.")


def test_rule_of_holds_exactly_the_ids_the_static_tier_raises():
    """`RULE_OF` is complete, and every entry in it is real.

    `RULE_OF` is what code switching on an id reads, and what the
    unit tests assert through. An id that is raised but has no entry
    in `RULE_OF` would report no rule — a gap. An entry with no id
    that ever raises it would be naming a diagnostic that cannot
    happen.

    The three modules scanned here are the static tier, and that is
    the whole map by construction: `RULE_OF` maps an id to the
    V-numbered restriction it enforces, and V-numbers name only
    syntactic restrictions. A preflight or runtime id —
    `machine.slot-not-declared`, `media.unknown` — enforces a
    machine rule or the dynamic semantics instead, and those have no
    V-number to map to. So their absence from `RULE_OF` is correct,
    not a gap, and widening this scan would mean inventing entries
    for them that could not correspond to anything real.
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
    """This count is tracked evidence, not a number that can silently drift.

    D55 is open against the missing identifier scheme, and this
    count is the evidence tracked under it. It moves down as ids are
    added; if it moves up, a diagnostic lost its id.
    """
    unidentified = sorted(
        os.path.basename(path) for path in INVALID
        if _ID.search(_header(path)).group(1) == "none")
    assert len(unidentified) == 0, (
        f"the unidentified fixtures are now {unidentified}. Update "
        "this count and the tally in the corpus README together — the "
        "README states it as evidence for D55.")


# The preflight bucket. These fixtures parse clean and are rejected
# later, once more context is available — exactly the blueprint
# corpus's third bucket, for the same reason: a fixture whose rule
# needs a machine, a namespace, or an invocation to check would fail
# a parse-time assertion for the wrong reason, so it is kept
# separate instead of weakening the parse-time check.
#
# This bucket used to assert only that a fixture parses — all it
# could check while preflight diagnostics carried no ids. Now that
# they do, it also asserts the specific reason for rejection, which
# is the whole point of the bucket: a fixture that parsed clean and
# was rejected for the wrong reason used to be indistinguishable
# from one rejected for the right reason.


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
    """Check the id a preflight-rejected fixture declares — this bucket could not do that until D58.

    Checked in both directions, like the parse bucket's: a fixture
    claiming `none` whose diagnostic has since gained an id fails
    here until its header catches up.
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
