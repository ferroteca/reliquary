# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for the timing model: the placement matrix and the plan."""

import os

import pytest

import reliquary
from reliquary.script_nodes import RULE_OF, ScriptParseError
from reliquary.script_parser import parse_script
from reliquary.script_timing import format_plan, parse_duration, resolve

# The reference script is a shipped builtin, resolved as package
# data so these tests run against an installed artifact too.
_REFERENCE = os.path.join(
    os.path.dirname(os.path.abspath(reliquary.__file__)),
    "codex", "scripts", "freedos-install.rlqs")

_HEAD = "platform dos\n"


def _plan(source):
    return resolve(parse_script(source))


def _rejects(source, reason, rule):
    """Parse `source`, expecting the rule that rejects it for `reason`."""
    with pytest.raises(ScriptParseError) as caught:
        parse_script(source)
    assert reason in caught.value.message, source
    assert RULE_OF[caught.value.rule_id] == rule, source
    return caught.value


# Durations.

def test_every_unit_converts_to_seconds():
    assert [parse_duration(s)
            for s in ("500ms", "2s", "1.5m", "2h", ".5s")] == [
        0.5, 2.0, 90.0, 7200.0, 0.5]


def test_a_duration_is_positive():
    for source in (_HEAD + 'wait "x" timeout=0s\n',
                   _HEAD + "timeout 0ms\nstart\n",
                   _HEAD + 'wait "x" stable=0s\n'):
        _rejects(source, "must be a positive duration", "V5")


# The placement matrix: any placement it rejects is a parse error,
# with why.

def test_deadline_is_not_an_observation_bound():
    _rejects(_HEAD + 'wait "x" deadline=5m\n',
             "exactly what timeout bounds", "V2")
    _rejects(
        _HEAD + 'wait deadline=5m {\n    on "x" {\n        press enter\n'
        '    }\n    on "y" {\n        press enter\n    }\n}\n',
        "a budget belongs to a phase or the run", "V2")


def test_a_handler_does_not_own_its_waiting():
    _rejects(
        _HEAD + 'wait {\n    on "x" timeout=5m {\n        press enter\n'
        '    }\n    on "y" {\n        press enter\n    }\n}\n',
        "write timeout on the wait", "V2")
    _rejects(
        _HEAD + "entry a\nphase a {\n"
        '    always "x" timeout=5m {\n        finish\n    }\n}\n',
        "write timeout on the phase", "V2")


def test_stable_belongs_to_a_match_not_a_container():
    _rejects(
        _HEAD + 'wait stable=1s {\n    on "x" {\n        press enter\n'
        '    }\n    on "y" {\n        press enter\n    }\n}\n',
        "write stable on the on handler", "V2")
    _rejects(_HEAD + "entry a\nphase a stable=1s {\n    finish\n}\n",
             "a phase has no condition of its own", "V2")


def test_the_matrix_admits_what_it_allows():
    script = parse_script(
        _HEAD + "entry a\ntimeout 30s\ndeadline 45m\n"
        "phase a timeout=5m deadline=20m {\n"
        '    wait "x" timeout=90s stable=2s\n'
        "    wait timeout=1m {\n"
        '        on "y" stable=1s {\n            finish\n        }\n'
        '        on "z" {\n            finish\n        }\n    }\n}\n')
    assert script.phases[0].timeout == "5m"


# The timing plan: resolution is innermost-wins and entirely a
# parse-time question.

def test_the_built_in_default_bounds_an_unadorned_script():
    plan = _plan(_HEAD + 'wait "x"\n')
    assert plan.default.spelling == "60s"
    assert plan.default.scope == "built-in"
    assert plan.observations[0].timeout.seconds == 60.0


def test_innermost_wins_across_every_scope():
    plan = _plan(
        _HEAD + "entry a\ntimeout 30s\ndeadline 45m\n"
        "phase a timeout=5m {\n"
        '    wait "phase default"\n'
        '    wait "own bound" timeout=90s\n'
        "    wait timeout=2m {\n"
        '        on "branch" {\n'
        '            wait "inherits the branching wait"\n'
        '            wait "own bound" timeout=10s\n'
        "            finish\n        }\n"
        '        on "other" {\n            finish\n        }\n'
        "    }\n}\n"
        "phase b {\n"
        '    wait "header default"\n'
        "    finish\n}\n")
    resolved = [(o.kind, o.timeout.spelling, o.timeout.scope)
                for o in plan.observations]
    assert resolved == [
        ("wait", "5m", "phase"),
        ("wait", "90s", "statement"),
        ("branching wait", "2m", "branching wait"),
        ("on", "2m", "branching wait"),
        ("wait", "2m", "branching wait"),
        ("wait", "10s", "statement"),
        ("on", "2m", "branching wait"),
        ("wait", "30s", "header"),
    ]


def test_a_bound_names_the_scope_that_supplied_it():
    plan = _plan(
        _HEAD + "entry a\ndeadline 45m\nphase a timeout=5m {\n"
        '    wait "x"\n    finish\n}\n')
    bound = plan.observations[0].timeout
    assert bound.source == "phase a (line 4)"
    assert str(bound) == "5m from the phase a (line 4)"


def test_budgets_are_never_inherited():
    plan = _plan(
        _HEAD + "entry a\ndeadline 45m\nphase a deadline=20m {\n"
        '    wait "x"\n    goto b\n}\n'
        "phase b {\n    finish\n}\n")
    assert plan.run_deadline.spelling == "45m"
    assert plan.run_deadline.scope == "header"
    assert plan.phase_deadlines["a"].spelling == "20m"
    assert "b" not in plan.phase_deadlines


def test_a_reactive_phase_bounds_its_own_interval():
    plan = _plan(
        _HEAD + "entry a\ntimeout 30s\nphase a timeout=5m {\n"
        '    always "x" stable=2s {\n        finish\n    }\n}\n')
    interval, handler = plan.observations
    assert (interval.kind, interval.timeout.spelling) == (
        "reactive interval", "5m")
    assert handler.kind == "always"
    assert handler.stable.spelling == "2s"
    assert handler.timeout.spelling == "5m"


def test_select_is_bounded_by_its_effective_timeout():
    plan = _plan(_HEAD + "timeout 20s\nselect \"Yes\"\n")
    assert (plan.observations[0].kind,
            plan.observations[0].timeout.spelling) == ("select", "20s")


def test_a_plan_entry_is_found_from_its_parsed_node():
    script = parse_script(_HEAD + 'wait "x" timeout=90s\n')
    plan = resolve(script)
    entry = plan.at(script.statements[0])
    assert entry.timeout.seconds == 90.0


def test_the_reference_script_resolves():
    with open(_REFERENCE, encoding="utf-8") as handle:
        plan = resolve(parse_script(handle.read(), path=_REFERENCE))
    assert plan.default.spelling == "30s"
    assert plan.run_deadline.spelling == "45m"
    assert plan.phase_deadlines["formatting"].spelling == "20m"
    formatting = [o for o in plan.observations if o.phase == "formatting"]
    assert all(o.timeout.spelling == "5m" for o in formatting)
    shutdown = [o for o in plan.observations if o.phase == "shutdown"]
    assert [o.timeout.spelling for o in shutdown] == ["2m"]


# Pacing resolves on its own ladder, one rung shorter.

def test_the_built_in_gap_paces_an_unadorned_script():
    plan = _plan(_HEAD + 'enter "x"\n')
    assert plan.default_pacing.spelling == "0.1s"
    assert plan.default_pacing.scope == "built-in"
    assert plan.inputs[0].pacing.seconds == 0.1


def test_innermost_wins_across_every_scope_that_carries_it():
    plan = _plan(
        _HEAD + "entry a\npacing 300ms\n"
        "phase a pacing=250ms {\n"
        '    enter "phase default"\n'
        '    type "own gap" pacing=1s\n'
        "    wait timeout=2m {\n"
        '        on "branch" {\n'
        '            press enter\n'
        "            finish\n        }\n"
        '        on "other" {\n            finish\n        }\n'
        "    }\n}\n"
        "phase b {\n"
        '    select "header default"\n'
        "    finish\n}\n")
    assert [(i.verb, i.pacing.spelling, i.pacing.scope)
            for i in plan.inputs] == [
        ("enter", "250ms", "phase"),
        ("type", "1s", "statement"),
        # A branching wait is no rung for pacing, so the handler
        # body inherits the phase straight through.
        ("press", "250ms", "phase"),
        ("select", "300ms", "header")]


def test_a_gap_names_the_scope_that_supplied_it():
    plan = _plan(
        _HEAD + "entry a\nphase a pacing=250ms {\n"
        '    enter "x"\n    finish\n}\n')
    gap = plan.inputs[0].pacing
    assert gap.source == "phase a (line 3)"
    assert str(gap) == "250ms from the phase a (line 3)"


def test_select_appears_in_both_lists():
    """It observes *and* delivers, so it carries both clocks."""
    plan = _plan(_HEAD + 'timeout 20s\npacing 2s\nselect "Yes"\n')
    assert (plan.observations[0].kind,
            plan.observations[0].timeout.spelling) == ("select", "20s")
    assert (plan.inputs[0].verb, plan.inputs[0].pacing.spelling) == (
        "select", "2s")


def test_click_appears_in_both_lists():
    """Like `select`, it observes *and* delivers (F66)."""
    plan = _plan(_HEAD + 'timeout 20s\npacing 2s\nclick @welcome\n')
    assert (plan.observations[0].kind,
            plan.observations[0].timeout.spelling,
            plan.observations[0].landmark) == ("click", "20s", "welcome")
    assert (plan.inputs[0].verb, plan.inputs[0].pacing.spelling) == (
        "click", "2s")


def test_a_host_side_verb_is_absent_from_the_plan():
    plan = _plan(_HEAD + 'screenshot\nstart\nset answer "42"\n')
    assert plan.inputs == ()


def test_a_gap_is_found_from_its_parsed_node():
    script = parse_script(_HEAD + 'press enter pacing=1s\n')
    gap = resolve(script).pacing_at(script.statements[0])
    assert gap.seconds == 1.0


def test_the_report_names_the_gap_beside_the_bounds():
    report = format_plan(_plan(_HEAD + 'pacing 2s\nenter "x"\n'))
    assert "default pacing: 2s from the header" in report
    assert "guest input:" in report
    assert "enter: pacing 2s from the header" in report


# V12: a cyclable phase graph declares the run's backstop.

def _rejects_cycle(source, route):
    return _rejects(source, f"the phase graph can cycle ({route})", "V12")


def test_a_self_loop_needs_a_deadline():
    error = _rejects_cycle(
        _HEAD + "entry a\nphase a {\n    goto a\n}\n", "a -> a")
    assert error.line == 4


def test_a_longer_cycle_names_its_route():
    _rejects_cycle(
        _HEAD + "entry a\nphase a {\n    goto b\n}\n"
        "phase b {\n    goto c\n}\n"
        "phase c {\n    goto a\n}\n", "a -> b -> c -> a")


def test_a_cycle_through_a_handler_is_found():
    _rejects_cycle(
        _HEAD + "entry a\nphase a {\n"
        '    always "x" {\n        goto a\n    }\n}\n', "a -> a")


def test_a_header_deadline_admits_the_cycle():
    script = parse_script(
        _HEAD + "entry a\ndeadline 45m\nphase a {\n    goto a\n}\n")
    assert len(script.phases) == 1


def test_an_acyclic_graph_needs_no_deadline():
    script = parse_script(
        _HEAD + "entry a\nphase a {\n    goto b\n}\n"
        "phase b {\n    goto c\n}\n"
        "phase c {\n    finish\n}\n")
    assert len(script.phases) == 3


def test_a_diamond_is_not_a_cycle():
    script = parse_script(
        _HEAD + "entry a\nphase a {\n    wait {\n"
        '        on "x" {\n            goto b\n        }\n'
        '        on "y" {\n            goto c\n        }\n    }\n}\n'
        "phase b {\n    goto d\n}\n"
        "phase c {\n    goto d\n}\n"
        "phase d {\n    finish\n}\n")
    assert len(script.phases) == 4


def test_an_unreachable_cycle_is_not_budgeted():
    # Unreachable phases are static analysis's warning, not a
    # run the deadline has to bound.
    script = parse_script(
        _HEAD + "entry a\nphase a {\n    finish\n}\n"
        "phase b {\n    goto c\n}\n"
        "phase c {\n    goto b\n}\n")
    assert len(script.phases) == 3


# `stability` guards the frame a compare runs on (F48).

def test_a_wait_carries_the_stability_written_on_it():
    plan = resolve(parse_script(_HEAD + 'wait "x" stability=0.98\n'))
    assert plan.observations[0].stability.spelling == "0.98"
    assert plan.observations[0].stability.scope == "statement"


def test_stability_is_refused_where_nothing_is_compared():
    # stability is checked the same way as pacing: each guard applies
    # to exactly the statement kinds whose hazard it addresses, not
    # to where the statement sits in the tree, so neither needs a
    # position-sensitive rule
    for source in (_HEAD + 'enter "DIR" stability=0.99\n',
                   _HEAD + "press enter stability=0.99\n",
                   _HEAD + 'select "Install" stability=0.99\n',
                   _HEAD + "screenshot stability=0.99\n"):
        _rejects(source, "compares nothing", "V2")


def test_every_observation_rung_may_carry_it():
    # `stability` differs from `stable` for a real reason: a frame
    # exists at every sample, so it is also meaningful on the
    # container rungs (wait, phase, header), not just the statement
    for source in (_HEAD + "stability 0.98\nstart\n",
                   _HEAD + "entry p\nphase p stability=0.98 {\n"
                           '  wait "x"\n  finish\n}\n',
                   _HEAD + 'wait "x" stability=0.98\n',
                   _HEAD + 'wait stability=0.98 {\n'
                           '  on "a" {\n    press enter\n  }\n'
                           '  on "b" {\n    press enter\n  }\n}\n',
                   _HEAD + 'wait {\n  on "a" stability=0.98 {\n'
                           '    press enter\n  }\n'
                           '  on "b" {\n    press enter\n  }\n}\n'):
        parse_script(source)


def test_a_proportion_outside_zero_to_one_is_refused():
    for spelling in ("1.5", "2"):
        with pytest.raises(ScriptParseError) as caught:
            parse_script(_HEAD + f'wait "x" stability={spelling}\n')
        assert "between 0 and 1" in caught.value.message


# A `with` scope is transparent to the timing model (F54).

def test_a_scope_resolves_its_statements_as_if_it_were_not_there():
    """The construct carries no timing modifier, so it is no scope.

    Written as a test rather than trusted because the plan is
    positional: a wrapped statement that fell out of the walk would
    still run, and would silently take the built-in default instead
    of the phase's.
    """
    scoped = _plan(
        _HEAD + "entry p\nphase p timeout=9s {\n"
        '    wait "x"\n    finish\n}\n')
    plan = _plan(
        _HEAD + "machine stopped\nentry p\nwith boot cdrom0 {\n"
        "    phase p timeout=9s {\n"
        '        wait "x"\n        finish\n    }\n}\n')
    wait = next(entry for entry in plan.observations
                if entry.kind == "wait")
    assert wait.timeout.spelling == "9s"
    unscoped = scoped.observations[0].timeout
    assert (wait.timeout.scope, wait.timeout.scope_name) == (
        unscoped.scope, unscoped.scope_name)


def test_a_linear_scope_contributes_its_wrapped_input_verbs():
    plan = _plan(
        _HEAD + "pacing 2s\nwith eject cdrom0 {\n    press enter\n}\n")
    delivery, = plan.inputs
    assert delivery.verb == "press"
    assert delivery.pacing.spelling == "2s"
