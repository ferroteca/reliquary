# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for the .rlqs runtime: dispatch, episodes, and clocks."""

import contextlib
import http.client
import io
import json
import os
import signal
import socket
from unittest import mock

import pytest

from reliquary import events as _events
from reliquary import text_recognize
from reliquary.binding import BoundProperties
from reliquary.errors import (PreflightError, RunCancelled, StaticError,
                              UnreadableScreen)
from reliquary.script_parser import parse_script
from reliquary.script_runner import (_preflight_machine_rules,
                                     ScriptPreflightError,
                                     ScriptRuntimeError, _normalize_row,
                                     resolve_key, _cancel_on_interrupt,
                                     _HttpResponse,
                                     _HttpService, _ScriptEngine,
                                     execute_script)
from reliquary.script_validation import PORTABLE_KEY_NAMES

_HEAD = "platform dos\n"


class _Clock:
    """A clock that only advances when the engine sleeps."""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class _FakeConsole:
    """A console over scripted screens, recording what it is sent."""

    #: How many reads each scripted screen is held for. A screen is a
    #: *state the guest displays*, not a single read: a guest waiting
    #: at a prompt holds it, and the quiescence gate (F48) will only
    #: judge a condition on a screen that has stopped changing. One
    #: read per entry would mean every sample caught the guest
    #: mid-redraw, which is the one thing a wait must not act on.
    HOLD = 3

    def __init__(self, screens=(), fail=False, hold=HOLD):
        self.screens = list(screens)
        self.fail = fail
        self.hold = hold
        self.commands = []
        self.keys = []
        self.reads = 0
        self._held = 0

    def screen_text(self):
        self.reads += 1
        if self.fail:
            # A carrier whose transport died mid-session: the raw
            # error reaches the runner, which reads it as the stopped
            # observation. The adapter's own converted diagnostic is
            # covered by the unreachable-VM test below.
            raise ConnectionError("machine is gone")
        if not self.screens:
            return []
        current = self.screens[0]
        if len(self.screens) > 1:
            self._held += 1
            if self._held >= self.hold:
                self._held = 0
                self.screens.pop(0)
        return current

    def screen(self, font_banks=()):
        """The same screens, as the seam's (rows, attributes) pair.

        These scripts say what the guest displayed; the attribute half
        is uniform because nothing here turns on a highlight, and a
        screen that stops changing therefore reads as settled.
        ``font_banks`` (F61) is accepted and ignored: nothing here
        recognizes pixels to read a font prefix through.
        """
        rows = self.screen_text()
        return rows, [[0x07] * 80 for _ in range(len(rows))]

    def send_text(self, text, enter=True):
        self.commands.append(("send_text", text, enter))

    def send_keys(self, combos, delay=0.06):
        self.keys.extend(combos)

    def cursor_menu_select(self, item, timeout=30, exclude=()):
        self.commands.append(("select", item, timeout, exclude))


class _FakeHttpService:
    """A fake run-scoped HTTP service for lifecycle tests."""

    guest_ip = "10.0.2.2"
    instances = []

    def __init__(self, responses, port_min=8000, port_max=9000):
        self.responses = tuple(responses)
        self.port_min = port_min
        self.port_max = port_max
        self.port = None
        self.started = 0
        self.stopped = 0
        _FakeHttpService.instances.append(self)

    @property
    def url(self):
        if self.port is None:
            return None
        return f"http://{self.guest_ip}:{self.port}"

    def start(self):
        self.started += 1
        self.port = self.port_min

    def stop(self):
        self.stopped += 1
        self.port = None


class _Runtime:
    """Builds engines over a fake console and a controlled clock."""

    def __init__(self):
        self.console = None
        self.clock = None

    def engine(self, source, screens=(), running=True, fail=False,
               bindings=None, events=None, hold=_FakeConsole.HOLD):
        _FakeHttpService.instances = []
        script = parse_script(_HEAD + source)
        clock = _Clock()
        engine = _ScriptEngine(
            script, "plain-0", "/tmp/home",
            "/tmp/home/cache/machines/plain-0", events=events,
            script_path="demo.rlqs", clock=clock, sleep=clock.sleep,
            http_service_factory=_FakeHttpService, bindings=bindings)
        engine._running = running
        self.console = _FakeConsole(screens, fail, hold=hold)
        self.clock = clock

        @contextlib.contextmanager
        def console():
            yield self.console

        engine._console = console
        return engine

    def run_linear(self, engine):
        with contextlib.redirect_stdout(io.StringIO()):
            return engine._execute(engine._script.statements)

    def run_phases(self, engine):
        with contextlib.redirect_stdout(io.StringIO()):
            engine._run_started = self.clock()
            return engine._run_phases()

    @contextlib.contextmanager
    def whole_run(self):
        """Drive ``engine.run()`` against an already-running machine."""
        with mock.patch("reliquary.script_runner._machines") as machines:
            machines.load_machine_state.return_value = {"phase": "running"}
            machines.read_vm_state.return_value = {
                "backend": "qemu", "backend-id": "reliquary-plain-0",
                "token": "0" * 32, "endpoint": {"port": 5555}}
            yield machines


@pytest.fixture
def runtime():
    return _Runtime()


# The helpers under the runtime.

def test_a_row_normalizes_its_whitespace():
    assert _normalize_row("  Hello   World  ") == "Hello World"


@pytest.mark.parametrize("name", sorted(PORTABLE_KEY_NAMES))
def test_every_portable_key_name_resolves(name):
    """One node per key, so a name the seam stopped mapping is named."""
    assert resolve_key(name)


def test_the_named_keys_map_onto_the_seams_vocabulary():
    assert resolve_key("enter") == ["ret"]
    assert resolve_key("pagedown") == ["pgdn"]
    assert resolve_key("ctrl+alt+delete") == ["ctrl", "alt", "delete"]


def test_a_chord_admits_a_printable_member():
    assert resolve_key("ctrl+c") == ["ctrl", "c"]


def test_a_bare_character_is_not_a_key_name():
    with pytest.raises(StaticError):
        resolve_key("c")


def test_an_unknown_name_is_not_passed_through():
    with pytest.raises(StaticError):
        resolve_key("oem_3")


# Single-condition waits, over samples.

def test_a_screen_condition_matches_a_normalized_row(runtime):
    engine = runtime.engine('wait "Hello World"\n',
                            screens=[["", "  Hello   World  "]])
    runtime.run_linear(engine)
    # Matched on the first *settled* sample. Establishing
    # quiescence costs the window before any condition is judged
    # (F48), which is the guard's stated price.
    assert runtime.console.reads == 3


def test_a_regex_condition_matches_a_row(runtime):
    engine = runtime.engine('wait /installed [0-9]+ packages/\n',
                            screens=[["installed 42 packages"]])
    runtime.run_linear(engine)


def test_a_condition_is_matched_only_at_a_fresh_sample(runtime):
    engine = runtime.engine('wait "second"\n',
                            screens=[["first"], ["second"]])
    runtime.run_linear(engine)
    # Each screen is a state the guest holds, and each is judged
    # only once it has settled.
    assert runtime.console.reads == 6


def test_a_timeout_names_the_clock_and_its_source_scope(runtime):
    engine = runtime.engine('timeout 10s\nwait "never"\n',
                            screens=[["nothing"]])
    with pytest.raises(ScriptRuntimeError) as caught:
        runtime.run_linear(engine)
    message = str(caught.value)
    assert "the observation timeout of 10s expired" in message
    assert "waiting for 'never'" in message
    assert "from the header (line 2)" in message


def test_a_timeout_cannot_expire_before_one_sample(runtime):
    # "A timeout always means samples were taken and none
    # satisfied the condition, never no one looked" -- so a
    # bound already elapsed still gets its sample, and a
    # condition holding there succeeds.
    engine = runtime.engine('timeout 1ms\nwait "ready"\n',
                            screens=[["ready"]])
    runtime.clock.now = 60.0
    runtime.run_linear(engine)
    # And the quiescence gate cannot break that rule: it delays
    # acceptance but never causes a failure by itself, so an
    # already-elapsed bound still evaluates what is on screen
    # rather than expiring on a sample nobody was allowed to read.
    assert runtime.console.reads == 2


def test_the_innermost_bound_is_the_one_enforced(runtime):
    engine = runtime.engine('timeout 1h\nwait "never" timeout=4s\n',
                            screens=[["no"]])
    with pytest.raises(ScriptRuntimeError) as caught:
        runtime.run_linear(engine)
    assert "timeout of 4s" in str(caught.value)
    assert "from the statement" in str(caught.value)


def test_stable_requires_the_episode_to_hold(runtime):
    engine = runtime.engine('wait "ready" stable=4s\n',
                            screens=[["ready"]])
    runtime.run_linear(engine)
    # One *settled* sample arms the episode; the hold is satisfied
    # only once its age reaches the duration. The extra reads are
    # the quiescence window, paid before the episode starts.
    assert runtime.console.reads == 5


def test_an_interrupted_episode_restarts_the_hold(runtime):
    engine = runtime.engine(
        'wait "ready" stable=2s\n',
        screens=[["ready"], ["busy"], ["ready"], ["ready"]])
    runtime.run_linear(engine)
    # "busy" ends the episode and the hold starts over, each state
    # judged once it has settled.
    assert runtime.console.reads == 10


def test_a_machine_condition_observes_the_backend(runtime):
    engine = runtime.engine("wait machine=stopped\n", fail=True)
    with mock.patch("reliquary.script_runner._machines") as machines:
        runtime.run_linear(engine)
        machines.mark_stopped.assert_called_once_with(
            "plain-0", context="/tmp/home")
    assert not engine._running


def test_an_unreachable_vm_runtime_error_is_stopped(runtime):
    # Production path: the adapter reports an unreachable VM as a
    # PREFLIGHT ERROR naming its rule. That must still count as
    # the stopped sample (not escape the wait).
    engine = runtime.engine("wait machine=stopped\n")

    @contextlib.contextmanager
    def unreachable():
        raise PreflightError(
            "the recorded reliquary VM is no longer reachable\n"
            "  expected: reliquary-plain-0 on 127.0.0.1:5555",
            rule_id="machine.vm-unreachable")
        yield  # pragma: no cover

    engine._console = unreachable
    with mock.patch("reliquary.script_runner._machines") as machines:
        runtime.run_linear(engine)
        machines.mark_stopped.assert_called_once_with(
            "plain-0", context="/tmp/home")
    assert not engine._running


def test_identity_mismatch_is_not_treated_as_stopped(runtime):
    engine = runtime.engine("wait machine=stopped\n")

    @contextlib.contextmanager
    def mismatch():
        raise PreflightError(
            "QMP identity mismatch; the unrelated VM was "
            "not modified", rule_id="machine.identity-mismatch")
        yield  # pragma: no cover

    engine._console = mismatch
    with pytest.raises(PreflightError) as caught:
        runtime.run_linear(engine)
    assert "identity mismatch" in str(caught.value)
    assert engine._running


def test_a_stopped_machine_satisfies_without_a_console(runtime):
    engine = runtime.engine("wait machine=stopped\n", running=False)
    runtime.run_linear(engine)
    assert runtime.console.reads == 0


def test_an_unreadable_screen_is_a_sample_the_wait_looks_past(runtime):
    # Every VirtualBox boot paints a graphics-mode BIOS splash
    # before the guest reaches text, and the recognizer can say
    # nothing about it. That is not the end of the run: the wait
    # keeps polling and matches once a text screen arrives.
    engine = runtime.engine('wait "ready"\n', screens=[["ready"]])
    splashes = [2]
    inner = runtime.console.screen

    def screen(font_banks=()):
        if splashes[0]:
            splashes[0] -= 1
            runtime.console.reads += 1
            raise UnreadableScreen(
                "framebuffer 640x480 is not an even 80x25 text grid",
                rule_id="recognize.geometry")
        return inner()

    runtime.console.screen = screen
    runtime.run_linear(engine)
    assert splashes[0] == 0


def test_an_unreadable_screen_is_not_a_stopped_machine(runtime):
    # It is not a blank screen and it is not an absent one: a guest
    # painting in a mode we cannot read is running perfectly well,
    # so `machine=stopped` must not be satisfied by it and the
    # machine must not be marked down.
    engine = runtime.engine('timeout 10s\nwait machine=stopped\n')

    @contextlib.contextmanager
    def unreadable():
        raise UnreadableScreen(
            "framebuffer 640x480 is not an even 80x25 text grid",
            rule_id="recognize.geometry")
        yield  # pragma: no cover

    engine._console = unreadable
    with mock.patch("reliquary.script_runner._machines") as machines:
        with pytest.raises(ScriptRuntimeError):
            runtime.run_linear(engine)
        machines.mark_stopped.assert_not_called()
    assert engine._running


def test_a_screen_observation_needs_a_running_machine(runtime):
    engine = runtime.engine('machine stopped\nwait "x"\n', running=False)
    with pytest.raises(ScriptRuntimeError) as caught:
        runtime.run_linear(engine)
    assert "machine is not running" in str(caught.value)


# The first condition that holds fires its handler.

_FORK = (
    "entry fork\ndeadline 1h\n"
    "phase fork {\n"
    "    wait {\n"
    '        on "partitioned" {\n            goto partitioning\n'
    "        }\n"
    '        on "formatted" {\n            goto formatting\n'
    "        }\n"
    "    }\n}\n"
    'phase partitioning {\n    enter "part"\n    finish\n}\n'
    'phase formatting {\n    enter "form"\n    finish\n}\n')


def test_declaration_order_decides_a_tie(runtime):
    engine = runtime.engine(_FORK, screens=[["partitioned and formatted"]])
    runtime.run_phases(engine)
    assert ("send_text", "part", True) in runtime.console.commands


def test_a_later_handler_fires_when_only_it_holds(runtime):
    engine = runtime.engine(_FORK, screens=[["formatted"]])
    runtime.run_phases(engine)
    assert ("send_text", "form", True) in runtime.console.commands


def test_a_handler_body_runs_with_no_session_held(runtime):
    # QEMU's QMP server admits one client at a time: a body that
    # opens its own session while the sample loop still held one
    # would block forever against a real machine.
    engine = runtime.engine(_FORK, screens=[["formatted"]])
    depth = {"open": 0, "overlap": False}

    @contextlib.contextmanager
    def console():
        depth["open"] += 1
        depth["overlap"] = depth["overlap"] or depth["open"] > 1
        try:
            yield runtime.console
        finally:
            depth["open"] -= 1

    engine._console = console
    runtime.run_phases(engine)
    assert not depth["overlap"]


def test_execution_continues_after_a_falling_handler(runtime):
    engine = runtime.engine(
        'wait {\n    on "go" {\n        press enter\n    }\n'
        '    on "stop" {\n        press esc\n    }\n}\n'
        'enter "after"\n', screens=[["go"]])
    runtime.run_linear(engine)
    assert runtime.console.keys == [["ret"]]
    assert ("send_text", "after", True) in runtime.console.commands


def test_a_branching_timeout_names_every_condition(runtime):
    engine = runtime.engine(
        'timeout 5s\nwait {\n    on "a" {\n        press enter\n'
        '    }\n    on /b/ {\n        press esc\n    }\n}\n',
        screens=[["neither"]])
    with pytest.raises(ScriptRuntimeError) as caught:
        runtime.run_linear(engine)
    assert "waiting for 'a' or /b/" in str(caught.value)


def test_a_handler_condition_may_name_a_channel(runtime):
    engine = runtime.engine(
        'wait {\n    on "up" {\n        press enter\n    }\n'
        "    on machine=stopped {\n        eject cdrom0\n    }\n}\n",
        fail=True)
    with mock.patch("reliquary.script_runner._machines") as machines:
        runtime.run_linear(engine)
        machines.eject_media.assert_called_once_with(
            "plain-0", "cdrom0", context="/tmp/home")
    assert runtime.console.keys == []


# A condition is judged only on a settled screen (F48).

def _painting(count=80):
    """Screens where the awaited text sits on a moving screen.

    Output arrives into a *different* row each frame, which is
    what makes this content rather than decoration: cells that
    churn in place recur, and recurrence is precisely what the
    animation mask exists to set aside (a spinner has no bearing
    on whether the awaited text is really on screen). A row here
    is rewritten only every twenty frames — outside the animation
    window — so nothing is ever masked and the screen is honestly
    still being drawn.
    """
    frames = []
    for step in range(count):
        rows = ["ready"] + [""] * 20
        rows[1 + step % 20] = "X" * 60
        frames.append(rows)
    return frames


def test_a_condition_on_a_painting_screen_is_not_matched(runtime):
    # the text is plainly there — a screenshot taken at the time
    # would show it — but the screen around it is still being
    # drawn, so it is not a sample the condition is judged on
    engine = runtime.engine("timeout 3s\nwait \"ready\"\n",
                            screens=_painting(), hold=1)

    with pytest.raises(ScriptRuntimeError) as caught:
        runtime.run_linear(engine)

    assert "never settled" in str(caught.value)


def test_the_gate_names_itself_when_the_wait_expires(runtime):
    # a wait now expires two ways that look identical from
    # outside, and the failure has to say which
    engine = runtime.engine("timeout 3s\nwait \"ready\"\n",
                            screens=_painting(), hold=1)

    with pytest.raises(ScriptRuntimeError) as caught:
        runtime.run_linear(engine)

    assert "stability" in str(caught.value)


def test_stability_zero_turns_the_guard_off(runtime):
    # the escape for a screen the default would refuse, and it
    # must cost nothing at all — not even the window that
    # establishing quiescence would otherwise take
    engine = runtime.engine("timeout 3s\nwait \"ready\" stability=0\n",
                            screens=_painting(), hold=1)

    runtime.run_linear(engine)

    assert runtime.console.reads == 1


def test_a_settled_screen_is_matched_normally(runtime):
    # the same script against a guest that has stopped drawing
    engine = runtime.engine("timeout 3s\nwait \"ready\"\n",
                            screens=[["ready", "copying done"]])

    runtime.run_linear(engine)

    assert runtime.console.reads == 3


# Standing handlers, run to completion, once per episode.

def test_a_handler_fires_once_per_appearance(runtime):
    engine = runtime.engine(
        "entry copying\ndeadline 1h\n"
        "phase copying timeout=1h {\n"
        '    always "insert disk 2" {\n        press enter\n    }\n'
        '    always "complete" {\n        finish\n    }\n}\n',
        screens=[["insert disk 2"], ["insert disk 2"],
                 ["insert disk 2"], ["copying"], ["insert disk 2"],
                 ["complete"]])
    runtime.run_phases(engine)
    # However long the prompt stays displayed, it fires once per
    # appearance: twice here, not five times.
    assert runtime.console.keys == [["ret"], ["ret"]]


def test_a_handler_transfers_immediately(runtime):
    engine = runtime.engine(
        "entry watch\ndeadline 1h\nphase watch {\n"
        '    always "done" {\n        goto after\n    }\n}\n'
        'phase after {\n    enter "next"\n    finish\n}\n',
        screens=[["done"]])
    runtime.run_phases(engine)
    assert ("send_text", "next", True) in runtime.console.commands


def test_declaration_order_decides_which_handler_fires(runtime):
    engine = runtime.engine(
        "entry watch\ndeadline 1h\nphase watch {\n"
        '    always "first" {\n        press enter\n    }\n'
        '    always "second" {\n        finish\n    }\n}\n',
        screens=[["first and second"], ["second"]])
    runtime.run_phases(engine)
    assert runtime.console.keys == [["ret"]]


def test_the_interval_expires_with_no_handler_firing(runtime):
    engine = runtime.engine(
        "entry watch\nphase watch timeout=5s {\n"
        '    always "never" {\n        finish\n    }\n}\n',
        screens=[["quiet"]])
    with pytest.raises(ScriptRuntimeError) as caught:
        runtime.run_phases(engine)
    message = str(caught.value)
    assert "the reactive interval of 5s expired" in message
    assert "with no handler firing" in message
    assert "from the phase watch" in message


def test_a_fired_handler_restarts_the_interval(runtime):
    engine = runtime.engine(
        "entry watch\nphase watch timeout=6s {\n"
        '    always "tick" {\n        press enter\n    }\n'
        '    always "done" {\n        finish\n    }\n}\n',
        screens=[["tick"], ["quiet"], ["tick"], ["quiet"],
                 ["tick"], ["done"]])
    runtime.run_phases(engine)
    assert len(runtime.console.keys) == 3


# Phase transitions, and the clocks that bound them.

def test_a_run_walks_the_graph_from_entry_to_finish(runtime):
    engine = runtime.engine(
        "entry one\n"
        'phase one {\n    enter "1"\n    goto two\n}\n'
        'phase two {\n    enter "2"\n    finish\n}\n')
    runtime.run_phases(engine)
    assert [command[1] for command in runtime.console.commands] == ["1", "2"]
    assert engine._phase.name == "two"


def test_a_phase_budget_is_fresh_at_each_entry(runtime):
    engine = runtime.engine(
        "entry loop\ndeadline 1h\n"
        "phase loop deadline=10s {\n"
        '    wait "go"\n    goto next\n}\n'
        "phase next {\n    goto loop\n}\n",
        screens=[["go"]])
    # Two activations, each budgeted afresh; without the reset
    # the second entry would expire on the first clock check.
    runtime.clock.now = 0.0
    transfers = []
    original = engine._execute

    def watched(statements):
        transfers.append(engine._phase.name)
        runtime.clock.now += 8.0
        if len(transfers) > 3:
            raise AssertionError("the graph never converged")
        return original(statements)

    engine._execute = watched
    with pytest.raises(AssertionError):
        runtime.run_phases(engine)
    assert transfers[:3] == ["loop", "next", "loop"]


def test_a_phase_deadline_expires_at_a_boundary(runtime):
    engine = runtime.engine(
        "entry slow\ndeadline 1h\n"
        "phase slow deadline=3s {\n"
        '    wait "never" timeout=1h\n    finish\n}\n',
        screens=[["quiet"]])
    with pytest.raises(ScriptRuntimeError) as caught:
        runtime.run_phases(engine)
    message = str(caught.value)
    assert "the phase deadline of 3s expired" in message
    assert "from the phase slow" in message


def test_the_run_deadline_backstops_a_cycle(runtime):
    engine = runtime.engine(
        "entry loop\ndeadline 5s\n"
        "phase loop {\n    goto loop\n}\n")
    with pytest.raises(ScriptRuntimeError) as caught:
        with contextlib.redirect_stdout(io.StringIO()):
            engine._run_started = runtime.clock()
            runtime.clock.now = 6.0
            engine._run_phases()
    assert "the run deadline of 5s expired" in str(caught.value)
    assert "from the header" in str(caught.value)


# The input verbs, and the gap each pays before delivering.

def test_enter_types_and_presses_enter(runtime):
    engine = runtime.engine('enter "fdapm poweroff"\n')
    runtime.run_linear(engine)
    assert runtime.console.commands == [
        ("send_text", "fdapm poweroff", True)]


def test_type_sends_text_with_no_ending(runtime):
    engine = runtime.engine('type "A:"\n')
    runtime.run_linear(engine)
    assert runtime.console.commands == [("send_text", "A:", False)]


def test_press_sends_a_sequence_of_keys(runtime):
    engine = runtime.engine("press down down enter\n")
    runtime.run_linear(engine)
    assert runtime.console.keys == [["down"], ["down"], ["ret"]]


def test_select_runs_under_its_effective_timeout(runtime):
    engine = runtime.engine(
        'timeout 45s\nselect "Plain DOS system" '
        'exclude="with sources"\n')
    runtime.run_linear(engine)
    assert runtime.console.commands == [
        ("select", "Plain DOS system", 45.0, ("with sources",))]


@pytest.mark.parametrize("source", ['enter "x"\n', 'type "x"\n',
                                    "press enter\n", 'select "Yes"\n'],
                         ids=["enter", "type", "press", "select"])
def test_every_guest_input_verb_pays_the_pacing_gap(runtime, source):
    """The pause lands before the first key event, once per verb.

    The fake clock only advances when the engine sleeps, so the
    elapsed time *is* the gap that was taken.
    """
    engine = runtime.engine(source)
    runtime.run_linear(engine)
    assert runtime.clock.now == pytest.approx(0.1)


def test_a_host_side_verb_pays_nothing(runtime):
    engine = runtime.engine("set answer \"42\"\n")
    with mock.patch("reliquary.script_runner._machines"):
        runtime.run_linear(engine)
    assert runtime.clock.now == 0.0


def test_the_gap_is_the_one_the_plan_resolved(runtime):
    engine = runtime.engine('pacing 2s\nenter "x" pacing=5s\n')
    runtime.run_linear(engine)
    assert runtime.clock.now == pytest.approx(5.0)


def test_the_header_gap_applies_where_no_statement_says(runtime):
    engine = runtime.engine('pacing 2s\nenter "x"\n')
    runtime.run_linear(engine)
    assert runtime.clock.now == pytest.approx(2.0)


def test_a_zero_gap_does_not_sleep(runtime):
    """`pacing=0s` is the author saying the guest is ready."""
    engine = runtime.engine('enter "x" pacing=0s\n')
    runtime.run_linear(engine)
    assert runtime.clock.now == 0.0


def test_the_gap_precedes_delivery(runtime):
    """Nothing reaches the console until the guest has settled.

    A gap taken *after* delivery would pace nothing; this is the
    whole point of the feature, so it is asserted directly rather
    than inferred from the elapsed total.
    """
    engine = runtime.engine('enter "x" pacing=3s\n')
    observed = []
    original = runtime.clock.sleep

    def watch(seconds):
        observed.append(("sleep", seconds, list(runtime.console.commands)))
        original(seconds)

    engine._sleep = watch
    runtime.run_linear(engine)
    assert observed == [("sleep", 3.0, [])]
    assert runtime.console.commands == [("send_text", "x", True)]


@pytest.mark.parametrize("source", ['enter "setup /owner=${owner}"\n',
                                    'wait "welcome ${owner}"\n'],
                         ids=["enter", "wait"])
def test_an_unbound_property_reference_is_a_named_error(runtime, source):
    engine = runtime.engine("property owner\n" + source,
                            screens=[["quiet"]])
    with pytest.raises(ScriptRuntimeError) as caught:
        runtime.run_linear(engine)
    assert "${owner} has no bound value" in str(caught.value)


def test_a_bound_property_expands_into_enter(runtime):
    engine = runtime.engine(
        'property owner\nenter "setup /owner=${owner}"\n',
        bindings=BoundProperties({"owner": "Paul"}, {"owner": "flag"}))
    runtime.run_linear(engine)
    assert runtime.console.commands == [
        ("send_text", "setup /owner=Paul", True)]


def test_a_bound_media_property_selects_the_insert_target(runtime):
    with mock.patch("reliquary.script_runner._machines") as machines:
        engine = runtime.engine(
            "property media disk\ninsert cdrom0 $disk\n",
            bindings=BoundProperties(
                {"disk": "supplemental"}, {"disk": "flag"}))
        runtime.run_linear(engine)
    machines.insert_media.assert_called_once_with(
        "plain-0", "cdrom0", "supplemental", context="/tmp/home",
        events=engine.events, cancelled=engine._cancelled)


def test_a_secret_value_is_redacted_from_the_event_stream(runtime):
    bound = BoundProperties(
        {"pw": "swordfish"}, {"pw": "properties file"},
        frozenset({"pw"}))
    engine = runtime.engine(
        'property secret pw\ntype "${pw}"\n', bindings=bound)
    engine._execute(engine._script.statements)
    # The guest still receives the real value...
    assert runtime.console.commands == [("send_text", "swordfish", False)]
    # ...but the stream shows the marker, never the secret.
    rendered = json.dumps(engine.events.events, ensure_ascii=False)
    assert "swordfish" not in rendered
    assert "«secret»" in rendered


# The verbs that change the machine rather than the guest.

def test_insert_resolves_a_media_reference(runtime):
    engine = runtime.engine("insert cdrom0 @freedos-livecd\n")
    with mock.patch("reliquary.script_runner._machines") as machines:
        runtime.run_linear(engine)
        # The run's own stream and cancel event travel with the
        # insert: an insert can pull hundreds of megabytes, so
        # without the stream the fetch reports nothing (silence
        # reads as a hang) and without the event a Ctrl-C is not
        # seen until the whole statement finishes.
        machines.insert_media.assert_called_once_with(
            "plain-0", "cdrom0", "freedos-livecd",
            context="/tmp/home",
            events=engine.events, cancelled=engine._cancelled)


def test_insert_from_a_property_reports_the_resolved_media(runtime):
    # A `$` insert defers the choice to run time, so the page
    # cannot say which media it is. The stream can, and does:
    # the action names the resolved item, spelled `@`, so a
    # reader of the run sees exactly what was mounted.
    stream = _events.EventStream()
    engine = runtime.engine(
        "property media supplemental\n"
        "insert floppy1 $supplemental\n",
        bindings=BoundProperties({"supplemental": "win98-cd"},
                                 {"supplemental": "flag"}),
        events=stream)
    with mock.patch("reliquary.script_runner._machines"):
        runtime.run_linear(engine)
    actions = [event for event in stream.events
               if event["kind"] == _events.ACTION_START
               and event.get("verb") == "insert"]
    assert len(actions) == 1
    assert actions[0]["detail"] == "floppy1 @win98-cd"


def test_insert_from_a_property_is_not_bound_yet(runtime):
    engine = runtime.engine(
        "property media supplemental\n"
        "insert floppy1 $supplemental\n")
    with mock.patch("reliquary.script_runner._machines"):
        with pytest.raises(ScriptRuntimeError) as caught:
            runtime.run_linear(engine)
    assert "has no bound value" in str(caught.value)


def test_font_resolves_named_banks_and_sets_the_prefix(runtime):
    engine = runtime.engine("font @guest @second\n")
    with mock.patch("reliquary.script_runner._fonts") as fonts:
        fonts.load_font_bank.side_effect = lambda name, context: f"bank-{name}"
        runtime.run_linear(engine)
    assert engine._font_prefix == ("bank-guest", "bank-second")
    fonts.load_font_bank.assert_any_call("guest", "/tmp/home")
    fonts.load_font_bank.assert_any_call("second", "/tmp/home")


def test_a_second_font_replaces_rather_than_appends(runtime):
    # D109: a prefix in force from that point forward, not an
    # accumulating list — an author who wants both names them
    # together on the one statement.
    engine = runtime.engine("font @a\nfont @b\n")
    with mock.patch("reliquary.script_runner._fonts") as fonts:
        fonts.load_font_bank.side_effect = lambda name, context: f"bank-{name}"
        runtime.run_linear(engine)
    assert engine._font_prefix == ("bank-b",)


def test_font_from_a_property_resolves_at_run_time(runtime):
    engine = runtime.engine(
        "property media chosen\nfont $chosen\n",
        bindings=BoundProperties({"chosen": "guest"}, {"chosen": "flag"}))
    with mock.patch("reliquary.script_runner._fonts") as fonts:
        fonts.load_font_bank.side_effect = lambda name, context: name
        runtime.run_linear(engine)
    fonts.load_font_bank.assert_called_once_with("guest", "/tmp/home")


def test_font_from_an_unbound_property_fails_at_run_time(runtime):
    engine = runtime.engine("property media chosen\nfont $chosen\n")
    with mock.patch("reliquary.script_runner._fonts"):
        with pytest.raises(ScriptRuntimeError) as caught:
            runtime.run_linear(engine)
    assert "has no bound value" in str(caught.value)


def test_the_font_action_is_reported_with_at_sigils(runtime):
    stream = _events.EventStream()
    engine = runtime.engine("font @guest @second\n", events=stream)
    with mock.patch("reliquary.script_runner._fonts") as fonts:
        fonts.load_font_bank.side_effect = lambda name, context: name
        runtime.run_linear(engine)
    actions = [event for event in stream.events
              if event["kind"] == _events.ACTION_START
              and event.get("verb") == "font"]
    assert actions[0]["detail"] == "@guest @second"


def test_set_records_a_machine_variable(runtime):
    engine = runtime.engine('set result "PASS"\n')
    with mock.patch("reliquary.script_runner._machines") as machines:
        runtime.run_linear(engine)
        machines.set_machine_var.assert_called_once_with(
            "plain-0", "result", "PASS", context="/tmp/home")


def test_a_set_value_interpolates_a_bound_property(runtime):
    bound = BoundProperties({"tag": "v2"}, {"tag": "--property"})
    engine = runtime.engine(
        'property tag\nset build "${tag}"\n', bindings=bound)
    with mock.patch("reliquary.script_runner._machines") as machines:
        runtime.run_linear(engine)
        machines.set_machine_var.assert_called_once_with(
            "plain-0", "build", "v2", context="/tmp/home")


def test_eject_empties_the_slot(runtime):
    engine = runtime.engine("eject cdrom0\n")
    with mock.patch("reliquary.script_runner._machines") as machines:
        runtime.run_linear(engine)
        machines.eject_media.assert_called_once_with(
            "plain-0", "cdrom0", context="/tmp/home")


def test_set_boot_replaces_the_boot_order(runtime):
    engine = runtime.engine("machine stopped\nset-boot hdd0 cdrom0\n")
    with mock.patch("reliquary.script_runner._machines") as machines:
        runtime.run_linear(engine)
        machines.set_boot_order.assert_called_once_with(
            "plain-0", ("hdd0", "cdrom0"), context="/tmp/home")


def test_a_machine_change_failure_reports_its_line(runtime):
    engine = runtime.engine("insert cdrom0 @freedos-livecd\n")
    with mock.patch("reliquary.script_runner._machines") as machines:
        machines.insert_media.side_effect = PreflightError(
            "machine plain-0 declares no drive cdrom0")
        with pytest.raises(ScriptRuntimeError) as caught:
            runtime.run_linear(engine)
    assert "declares no drive" in str(caught.value)
    assert "line 2" in str(caught.value)


def test_start_and_stop_track_whether_the_machine_runs(runtime):
    engine = runtime.engine("stop\nstart\n")
    with mock.patch("reliquary.script_runner._machines") as machines:
        runtime.run_linear(engine)
        machines.stop_machine.assert_called_once_with(
            "plain-0", context="/tmp/home")
    assert engine._running


def test_a_screenshot_rests_with_its_machine(runtime):
    # No run directory exists any more (D36): an author's
    # screenshot lands under the machine it was taken from.
    engine = runtime.engine("screenshot installed\n")
    with mock.patch("reliquary.script_runner.Machine") as machine:
        runtime.run_linear(engine)
    assert machine.call_args.args[0] == "/tmp/home/cache/machines/plain-0"
    machine.return_value.screenshot.assert_called_once_with("installed")


def test_a_screenshot_defaults_to_its_step_number(runtime):
    engine = runtime.engine("screenshot\n")
    with mock.patch("reliquary.script_runner.Machine") as machine:
        runtime.run_linear(engine)
    machine.return_value.screenshot.assert_called_once_with("step-1")


# A cancellation ends the run at the next event boundary.

def test_a_pending_cancel_stops_at_the_next_boundary(runtime):
    engine = runtime.engine('wait "a"\nwait "b"\n',
                            screens=[["a"], ["b"]])
    engine.cancel()
    with pytest.raises(RunCancelled):
        runtime.run_linear(engine)
    # Nothing was observed: the very first boundary caught it.
    assert runtime.console.reads == 0


def test_an_input_in_flight_completes_before_the_stop(runtime):
    engine = runtime.engine('enter "FORMAT C:"\nenter "second"\n')
    original = engine._enter

    def enter_then_cancel(statement):
        original(statement)
        engine.cancel()

    engine._enter = enter_then_cancel
    with pytest.raises(RunCancelled):
        runtime.run_linear(engine)
    # The delivery is atomic: the first line reached the guest
    # whole, and the second never started.
    assert runtime.console.commands == [("send_text", "FORMAT C:", True)]


def test_the_terminal_event_reports_the_cancellation(runtime):
    engine = runtime.engine('wait "a"\n', screens=[["a"]])
    engine.cancel()
    with runtime.whole_run():
        with pytest.raises(RunCancelled):
            engine.run()
    terminal = engine.events.events[-1]
    assert terminal["kind"] == "run.end"
    assert terminal["outcome"] == "cancelled"
    assert terminal["exit-code"] == 5


# A failure names the route, the clock, and what to try next.

def _failed_run(runtime, source, screens):
    engine = runtime.engine(source, screens=screens)
    with runtime.whole_run(), \
            mock.patch("reliquary.script_runner.Machine"):
        with pytest.raises(ScriptRuntimeError):
            engine.run()
    by_kind = {event["kind"]: event for event in engine.events.events}
    return engine, by_kind


def test_the_report_names_the_clock_and_its_scope(runtime):
    _engine, by_kind = _failed_run(
        runtime, 'timeout 10s\nwait "never"\n', [["nothing here"]])
    failure = by_kind["failure"]
    assert "the observation timeout of 10s" in failure["clock"]
    assert "header" in failure["scope"]
    assert failure["pending"] == "'never'"


def test_the_report_names_the_nearest_miss(runtime):
    _engine, by_kind = _failed_run(
        runtime, 'timeout 10s\nwait "Welcome to FreeDOS"\n',
        [["Welcome to FreeDO"]])
    assert by_kind["failure"]["nearest-miss"] == "Welcome to FreeDO"


def test_the_report_says_how_much_of_the_screen_was_a_guess(runtime):
    """The nearest miss measures rows that may never have been read.

    A cell matching no glyph becomes a space, so a screen drawn in
    an unknown font arrives looking sparse and the wait expires
    with nothing to show. Saying how many cells were substituted
    turns "it never appeared" into "it may have been there and
    unreadable" — different problems, different fixes.
    """
    engine = runtime.engine('timeout 10s\nwait "ready"\n')
    rows = ["nothing here"]
    attributes = [[0x07] * 80 for _ in rows]

    def screen(font_banks=()):
        runtime.console.reads += 1
        return text_recognize.Screen(
            rows, attributes, unreadable=((0, 4), (0, 5), (3, 9)))

    with mock.patch.object(runtime.console, "screen", screen), \
            runtime.whole_run(), \
            mock.patch("reliquary.script_runner.Machine"):
        with pytest.raises(ScriptRuntimeError):
            engine.run()
    failure = {event["kind"]: event
               for event in engine.events.events}["failure"]
    assert failure["unreadable-cells"] == 3


def test_a_fully_read_screen_reports_no_unreadable_cells(runtime):
    """Silent at zero: a clean read must not carry a confidence line."""
    _engine, by_kind = _failed_run(
        runtime, 'timeout 10s\nwait "never"\n', [["nothing here"]])
    assert by_kind["failure"].get("unreadable-cells") is None


def test_the_report_names_a_screen_that_could_never_be_read(runtime):
    # The case the nearest miss cannot answer: with no rows at any
    # sample, nothing was ever near the target, and a silent report
    # would look like a condition that merely never matched.
    engine = runtime.engine('timeout 10s\nwait "ready"\n')

    @contextlib.contextmanager
    def unreadable():
        raise UnreadableScreen(
            "framebuffer 640x480 is not an even 80x25 text grid",
            rule_id="recognize.geometry")
        yield  # pragma: no cover

    engine._console = unreadable
    with runtime.whole_run(), \
            mock.patch("reliquary.script_runner.Machine"):
        with pytest.raises(ScriptRuntimeError):
            engine.run()
    failure = [event for event in engine.events.events
               if event["kind"] == "failure"][0]
    assert "640x480" in failure["unreadable-screen"]
    assert "nearest-miss" not in failure


def test_the_guard_reports_its_cadence_once(runtime):
    """A guard that stood down must not look like one that passed."""
    engine = runtime.engine('timeout 10s\nwait "never"\n',
                            screens=[["nothing"]])
    with runtime.whole_run(), \
            mock.patch("reliquary.script_runner.Machine"):
        with pytest.raises(ScriptRuntimeError):
            engine.run()
    guards = [event for event in engine.events.events
              if event["kind"] == "guard.cadence"]

    assert len(guards) == 1
    assert "cadence" in guards[0]
    assert "window" in guards[0]
    assert not guards[0]["blind"]
    assert not guards[0]["recognized"]


def test_the_report_suggests_a_next_command(runtime):
    _engine, by_kind = _failed_run(
        runtime, 'timeout 10s\nwait "never"\n', [["nothing"]])
    assert "rlq screen --machine plain-0" in (
        by_kind["failure"]["next-command"])


def test_the_route_and_its_revisits_are_reported(runtime):
    # Each phase spends one poll interval, so the run deadline
    # trips only after the graph has been walked twice round.
    engine = runtime.engine(
        'timeout 10s\ndeadline 5s\nentry first\n'
        'phase first {\n    wait "a" stable=1s\n    goto second\n}\n'
        'phase second {\n    wait "a" stable=1s\n    goto first\n}\n',
        screens=[["a"]])
    with runtime.whole_run(), \
            mock.patch("reliquary.script_runner.Machine"):
        with pytest.raises(ScriptRuntimeError):
            engine.run()
    failure = [event for event in engine.events.events
               if event["kind"] == "failure"][0]
    assert list(failure["route"][:3]) == ["first", "second", "first"]
    assert failure["revisits"]["first"] >= 2


def test_a_screenshot_is_suppressed_after_a_secret_is_typed(runtime):
    bound = BoundProperties(
        {"pw": "swordfish"}, {"pw": "properties file"},
        frozenset({"pw"}))
    engine = runtime.engine(
        'timeout 10s\nproperty secret pw\ntype "${pw}"\n'
        'wait "never"\n', screens=[["nothing"]], bindings=bound)
    with runtime.whole_run(), \
            mock.patch("reliquary.script_runner.Machine") as capture:
        with pytest.raises(ScriptRuntimeError):
            engine.run()
    # The handle itself is built for every read; what must not happen
    # is the capture.
    capture.return_value.screenshot.assert_not_called()
    failure = [event for event in engine.events.events
               if event["kind"] == "failure"][0]
    assert "screenshot" not in failure


# Run-scoped HTTP starts, stops, and cleans up predictably.

def test_http_start_serves_declared_content_and_binds_url(runtime):
    engine = runtime.engine(
        "http port-min=8123 port-max=8123 {\n"
        '    content answer "/answer.txt" """\n'
        "        one\n"
        "    \"\"\"\n"
        "}\n"
        "http start answer\n"
        'enter "${rlq.http.url}/answer.txt"\n')
    runtime.run_linear(engine)
    service = _FakeHttpService.instances[0]
    assert service.port_min == 8123
    assert [response.path for response in service.responses] == [
        "/answer.txt"]
    assert service.responses[0].body == b"one\n"
    assert ("send_text", "http://10.0.2.2:8123/answer.txt",
            True) in runtime.console.commands


def test_http_stop_is_noop_when_already_stopped(runtime):
    engine = runtime.engine("http stop\n")
    runtime.run_linear(engine)
    assert _FakeHttpService.instances == []
    assert engine._bindings == {}


def test_http_stop_clears_runtime_bindings(runtime):
    engine = runtime.engine(
        "http {\n"
        '    content answer "/answer.txt" """\n'
        "        one\n"
        "    \"\"\"\n"
        "}\n"
        "http start\n"
        "http stop\n"
        'enter "${rlq.http.url}/answer.txt"\n')
    with pytest.raises(ScriptRuntimeError) as caught:
        runtime.run_linear(engine)
    assert "${rlq.http.url} has no bound value" in str(caught.value)
    assert _FakeHttpService.instances[0].stopped == 1


def test_http_start_without_names_serves_all_declared_content(runtime):
    engine = runtime.engine(
        "http {\n"
        '    content one "/one.txt" """\n        one\n    """\n'
        '    content two "/two.txt" """\n        two\n    """\n'
        "}\n"
        "http start\n")
    runtime.run_linear(engine)
    assert [response.path
            for response in _FakeHttpService.instances[0].responses] == [
        "/one.txt", "/two.txt"]


def test_http_start_names_only_selected_content(runtime):
    engine = runtime.engine(
        "http {\n"
        '    content one "/one.txt" """\n        one\n    """\n'
        '    content two "/two.txt" """\n        two\n    """\n'
        "}\n"
        "http start two\n")
    runtime.run_linear(engine)
    assert [response.path
            for response in _FakeHttpService.instances[0].responses] == [
        "/two.txt"]


def test_http_start_redefines_specific_content_for_that_start(runtime):
    engine = runtime.engine(
        "http {\n"
        '    content answer "/answer.txt" """\n'
        "        one\n"
        "    \"\"\"\n"
        "}\n"
        "http start {\n"
        '    content answer "/answer.txt" """\n'
        "        two\n"
        "    \"\"\"\n"
        "}\n")
    runtime.run_linear(engine)
    assert _FakeHttpService.instances[0].responses[0].body == b"two\n"


def test_http_redefinition_must_leave_final_paths_unique(runtime):
    engine = runtime.engine(
        "http {\n"
        '    content one "/one.txt" """\n        one\n    """\n'
        '    content two "/two.txt" """\n        two\n    """\n'
        "}\n"
        "http start {\n"
        '    content one "/two.txt" """\n'
        "        replacement\n"
        "    \"\"\"\n"
        "}\n")
    with pytest.raises(ScriptRuntimeError) as caught:
        runtime.run_linear(engine)
    assert "duplicate path: /two.txt" in str(caught.value)


def test_http_restart_stops_the_previous_server(runtime):
    engine = runtime.engine(
        "http {\n"
        '    content answer "/answer.txt" """\n'
        "        one\n"
        "    \"\"\"\n"
        "}\n"
        "http start\n"
        "http start\n")
    runtime.run_linear(engine)
    assert len(_FakeHttpService.instances) == 2
    assert _FakeHttpService.instances[0].stopped == 1
    assert _FakeHttpService.instances[1].started == 1


def test_http_is_implied_stopped_when_engine_run_succeeds(runtime):
    engine = runtime.engine(
        "http {\n"
        '    content answer "/answer.txt" """\n'
        "        one\n"
        "    \"\"\"\n"
        "}\n"
        "http start\n")
    with mock.patch.object(engine, "_establish_machine"), \
            contextlib.redirect_stdout(io.StringIO()):
        engine.run()
    assert _FakeHttpService.instances[0].stopped == 1
    assert engine._bindings == {}


def test_http_is_implied_stopped_when_engine_run_fails(runtime):
    engine = runtime.engine(
        "http {\n"
        '    content answer "/answer.txt" """\n'
        "        one\n"
        "    \"\"\"\n"
        "}\n"
        "http start\n"
        'enter "${missing.value}"\n')
    with mock.patch.object(engine, "_establish_machine"), \
            pytest.raises(ScriptRuntimeError), \
            contextlib.redirect_stdout(io.StringIO()):
        engine.run()
    assert _FakeHttpService.instances[0].stopped == 1
    assert engine._bindings == {}


# The real HTTP service serves the response map over a socket.

def _free_port():
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        if port < 65535:
            return port


def _free_adjacent_pair():
    for _ in range(100):
        first = _free_port()
        second_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            second_sock.bind(("127.0.0.1", first + 1))
            return first, first + 1
        except OSError:
            continue
        finally:
            second_sock.close()
    raise AssertionError("could not find adjacent free TCP ports")


@pytest.fixture
def serve():
    """Start a real `_HttpService`, and stop it with the test."""
    started = []

    def start(responses, port_min, port_max):
        service = _HttpService(responses, port_min, port_max)
        started.append(service)
        service.start()
        return service

    yield start
    for service in started:
        service.stop()


def test_get_head_and_404(serve):
    port = _free_port()
    service = serve(
        (_HttpResponse("answer", "/answer.txt", b"hello\n"),), port, port)

    connection = http.client.HTTPConnection(
        "127.0.0.1", service.port, timeout=5)
    try:
        connection.request("GET", "/answer.txt")
        response = connection.getresponse()
        assert response.status == 200
        assert response.read() == b"hello\n"
        assert response.getheader("Content-Length") == "6"

        connection.request("HEAD", "/answer.txt")
        response = connection.getresponse()
        assert response.status == 200
        assert response.read() == b""
        assert response.getheader("Content-Length") == "6"

        connection.request("GET", "/missing.txt")
        response = connection.getresponse()
        assert response.status == 404
        response.read()
    finally:
        connection.close()


def test_port_selection_skips_occupied_ports(serve):
    first, second = _free_adjacent_pair()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as blocker:
        blocker.bind(("", first))
        blocker.listen(1)

        service = serve(
            (_HttpResponse("answer", "/answer.txt", b"hello\n"),),
            first, second)

        assert service.port == second


# Static preflight and machine-header checks before guest input.

class _Preflight:
    """A home holding one machine's state, and the media it names."""

    machine_id = "plain-0"

    def __init__(self, home):
        self.home = home

    def write_media(self, *names):
        """Declare media in the home so `@name` preflights."""
        blueprints = os.path.join(self.home, "blueprints")
        os.makedirs(blueprints, exist_ok=True)
        with open(os.path.join(blueprints, "lib.rlqb"), "w",
                  encoding="utf-8") as handle:
            json.dump([{"type": "media", "name": name,
                        "location": {"local": f"/{name}.iso"}}
                       for name in names], handle)

    def write_font(self, name, cell_rows=16, codepage="cp437"):
        """Declare an authored font in the home so `@name` preflights."""
        fonts_dir = os.path.join(self.home, "fonts")
        os.makedirs(fonts_dir, exist_ok=True)
        with open(os.path.join(fonts_dir, f"{name}.rlqf"), "w",
                  encoding="utf-8") as handle:
            json.dump({"cell-rows": cell_rows, "codepage": codepage}, handle)
        with open(os.path.join(fonts_dir, f"{name}.bin"), "wb") as handle:
            handle.write(bytes(4096))

    def write_state(self, phase="ready", drives=None):
        root = os.path.join(self.home, "cache", "machines",
                            self.machine_id)
        os.makedirs(root)
        state = {
            "id": self.machine_id,
            "phase": phase,
            "drives": drives if drives is not None else {
                "hdd0": {"medium": "hdd", "slot": 0, "size": "20M",
                         "path": "blank.qcow2"},
            },
        }
        with open(os.path.join(root, "machine.json"), "w",
                  encoding="utf-8") as handle:
            json.dump(state, handle)

    def execute(self, source):
        return execute_script(parse_script(source),
                              machine_id=self.machine_id,
                              context=self.home)


@pytest.fixture
def preflight(tmp_path):
    return _Preflight(str(tmp_path))


def test_an_empty_script_reports_the_machine_phase(preflight):
    preflight.write_state()
    assert preflight.execute(_HEAD) == ("-", "ready")


def test_insert_to_an_undeclared_slot_fails_before_execution(preflight):
    preflight.write_state()
    with pytest.raises(ScriptPreflightError) as caught:
        preflight.execute(_HEAD + "machine stopped\n"
                          "insert cdrom0 @freedos-livecd\nstart\n")
    assert "declares no drive cdrom0" in str(caught.value)
    assert "line 3" in str(caught.value)


def test_an_unknown_media_reference_fails_before_execution(preflight):
    # script-spec.md, "Validation and preflight": preflight
    # rejects "media references (@name) naming no media the
    # namespace defines".
    preflight.write_media("freedos-livecd")
    preflight.write_state(drives={"cdrom0": {"medium": "cdrom", "slot": 0}})
    with pytest.raises(ScriptPreflightError) as caught:
        preflight.execute(
            _HEAD + "machine stopped\ninsert cdrom0 @freedos-livecdd\n")
    message = str(caught.value)
    assert "no media named 'freedos-livecdd'" in message
    assert "did you mean 'freedos-livecd'" in message
    assert "line 3" in message


def test_a_property_media_reference_is_not_preflighted(preflight):
    # $name defers to binding by design, so it cannot be
    # checked here and must not be rejected.
    preflight.write_state(drives={"cdrom0": {"medium": "cdrom", "slot": 0}})
    script = parse_script(
        _HEAD + "machine stopped\nproperty media disk\n"
        "insert cdrom0 $disk\n")
    state = {"id": preflight.machine_id, "phase": "ready",
             "drives": {"cdrom0": {"medium": "cdrom", "slot": 0}}}
    _preflight_machine_rules(script, state, "<script>", preflight.home)


def test_an_unknown_font_reference_fails_before_execution(preflight):
    preflight.write_font("guest")
    preflight.write_state()
    with pytest.raises(ScriptPreflightError) as caught:
        preflight.execute(_HEAD + "machine stopped\nfont @guestt\n")
    message = str(caught.value)
    assert "no font named 'guestt'" in message
    assert "did you mean 'guest'" in message


def test_a_property_font_reference_is_not_preflighted(preflight):
    preflight.write_state()
    script = parse_script(
        _HEAD + "machine stopped\nproperty media chosen\n"
        "font $chosen\n")
    state = {"id": preflight.machine_id, "phase": "ready", "drives": {}}
    _preflight_machine_rules(script, state, "<script>", preflight.home)


def test_the_slot_is_reported_before_the_media(preflight):
    # Both wrong on one statement: the author reads the slot
    # first, so the slot error is the one raised.
    preflight.write_state()
    with pytest.raises(ScriptPreflightError) as caught:
        preflight.execute(
            _HEAD + "machine stopped\ninsert cdrom0 @nonesuch\n")
    assert "declares no drive cdrom0" in str(caught.value)


def test_preflight_descends_into_handler_bodies(preflight):
    preflight.write_state()
    with pytest.raises(ScriptPreflightError) as caught:
        preflight.execute(
            _HEAD + "entry fork\ndeadline 1h\nphase fork {\n"
            '    wait {\n        on "a" {\n            eject floppy1\n'
            "            finish\n        }\n"
            '        on "b" {\n            finish\n        }\n'
            "    }\n}\n")
    assert "declares no drive floppy1" in str(caught.value)


def test_set_boot_keys_are_preflighted(preflight):
    preflight.write_state()
    with pytest.raises(ScriptPreflightError) as caught:
        preflight.execute(_HEAD + "machine stopped\nset-boot cdrom0 hdd0\n")
    assert "declares no drive cdrom0" in str(caught.value)


def test_insert_rejects_a_hard_disk_slot(preflight):
    preflight.write_state()
    with pytest.raises(ScriptPreflightError) as caught:
        preflight.execute(_HEAD + "machine stopped\ninsert hdd0 @some-image\n")
    assert "not a removable drive slot" in str(caught.value)


def test_a_stopped_script_rejects_a_running_machine(preflight):
    preflight.write_state(phase="running")
    with pytest.raises(ScriptRuntimeError) as caught:
        preflight.execute(_HEAD + "machine stopped\nstart\n")
    assert "expects a stopped machine" in str(caught.value)


def test_a_stopped_script_starts_the_machine_itself(preflight):
    preflight.write_media("freedos-livecd")
    preflight.write_state(drives={
        "cdrom0": {"medium": "cdrom", "slot": 0, "media": None,
                   "path": None},
    })
    with mock.patch("reliquary.script_runner._machines") as machines, \
            contextlib.redirect_stdout(io.StringIO()):
        machines.load_machine_state.return_value = {
            "id": preflight.machine_id, "phase": "ready",
            "drives": {"cdrom0": {"medium": "cdrom", "slot": 0}},
        }
        preflight.execute(
            _HEAD + "machine stopped\ninsert cdrom0 @freedos-livecd\n")
        machines.start_machine.assert_not_called()
        machines.insert_media.assert_called_once()


# Ctrl-C asks once, then insists.
#
# The graceful stop is a promise, not a trap: a stop that will not
# land must still have a way out that is not killing the terminal.

class _AskableEngine:
    """The two members ``_cancel_on_interrupt`` uses."""

    def __init__(self):
        self.cancels = 0

    @property
    def cancelled(self):
        return self.cancels > 0

    def cancel(self):
        self.cancels += 1


def test_the_first_interrupt_requests_a_graceful_stop():
    engine = _AskableEngine()
    with _cancel_on_interrupt(engine):
        signal.getsignal(signal.SIGINT)(signal.SIGINT, None)
    assert engine.cancels == 1


def test_a_second_interrupt_raises_immediately():
    engine = _AskableEngine()
    with _cancel_on_interrupt(engine):
        handler = signal.getsignal(signal.SIGINT)
        handler(signal.SIGINT, None)
        with pytest.raises(KeyboardInterrupt):
            handler(signal.SIGINT, None)
    # The second press interrupts rather than asking again.
    assert engine.cancels == 1


def test_the_previous_handler_is_restored():
    before = signal.getsignal(signal.SIGINT)
    with _cancel_on_interrupt(_AskableEngine()):
        pass
    assert signal.getsignal(signal.SIGINT) is before


# Scoped machine-state changes — the `with` block (F54).
#
# The construct's whole claim is that the scope undoes itself on every
# outcome, so what these drive is the *pairing*: what entry applied
# and what exit put back, over a machine layer that records its calls.

_SCOPED_MACHINE = {
    "phase": "ready",
    "boot": ["hdd0", "cdrom0"],
    "drives": {"hdd0": {"medium": "hdd"},
               "cdrom0": {"medium": "cdrom", "media": None, "path": None}},
}


class _ScopedRun:
    """A whole run over a machine layer that answers and records.

    The double **applies** what it is told, because a scope reads the
    machine twice — once to capture and once to decide what putting a
    slot back involves — and a state frozen between those two reads
    would answer the second question with the first one's world.
    """

    def __init__(self, machines, state):
        self.machines = machines
        self.state = state
        self.phase = state.get("phase", "ready")
        self.engine = None

    def snapshot(self, *_args, **_kwargs):
        state = json.loads(json.dumps(self.state))
        state["phase"] = self.phase
        return state

    def insert(self, _machine, slot, media=None, *, file=None, **_kwargs):
        self.state["drives"][slot].update(
            {"media": media, "path": file or f"/cache/media/{media}.iso"})

    def eject(self, _machine, slot, **_kwargs):
        self.state["drives"][slot].update({"media": None, "path": None})

    @property
    def boot_orders(self):
        return [list(call.args[1])
                for call in self.machines.set_boot_order.call_args_list]


@contextlib.contextmanager
def _scoped(source, state=None, machine="freedos-0", screens=None):
    """Run a script whole against a recording machine layer.

    ``screens`` gives the run a console, for the scripts whose route
    is the guest's to choose — which is the only kind that can reach a
    scope exit V17 could not rule on.
    """
    script = parse_script(source)
    with mock.patch("reliquary.script_runner._machines") as machines:
        run = _ScopedRun(machines, state or _SCOPED_MACHINE)
        machines.load_machine_state.side_effect = run.snapshot
        machines.insert_media.side_effect = run.insert
        machines.eject_media.side_effect = run.eject
        machines.start_machine.side_effect = (
            lambda *a, **k: setattr(run, "phase", "running"))
        machines.stop_machine.side_effect = (
            lambda *a, **k: setattr(run, "phase", "ready"))
        clock = _Clock()
        run.engine = _ScriptEngine(
            script, machine, "/tmp/home", "/tmp/home/machines/" + machine,
            script_path="demo.rlqs", clock=clock, sleep=clock.sleep)
        if screens is not None:
            console = _FakeConsole(screens)

            @contextlib.contextmanager
            def opened():
                yield console

            run.engine._console = opened
        yield run


def _kinds(engine, *kinds):
    return [event for event in engine.events.events
            if event["kind"] in kinds]


def test_a_boot_scope_puts_its_drives_first_and_keeps_the_rest():
    """The difference from `set-boot`, which is the point of `boot`.

    A stage says "boot the CD first"; the order behind it is the
    machine's own, and the author never restated it.
    """
    with _scoped("platform dos\nmachine stopped\nentry a\n"
                 "with boot cdrom0 {\n    phase a {\n"
                 "        finish\n    }\n}\n") as run:
        run.engine.run()
    assert run.boot_orders == [["cdrom0", "hdd0"], ["hdd0", "cdrom0"]]


def test_the_exit_returns_the_target_to_what_it_held_on_entry():
    with _scoped("platform dos\nmachine stopped\nentry a\n"
                 "with boot cdrom0 {\n    phase a {\n"
                 "        finish\n    }\n}\n") as run:
        run.engine.run()
    restore, = _kinds(run.engine, _events.SCOPE_RESTORE)
    assert restore["target"] == "the boot order"
    assert restore["detail"] == "hdd0 cdrom0"
    assert "error" not in restore


def test_a_goto_inside_the_group_neither_restores_nor_reapplies():
    """The scope holds while control is inside it, and no longer.

    Every phase body ends in a transition, so a scope that closed at
    each one would express nothing — which is why the reading is
    dynamic rather than lexical (D104).
    """
    with _scoped("platform dos\nmachine stopped\nentry a\n"
                 "with boot cdrom0 {\n"
                 "    phase a {\n        goto b\n    }\n"
                 "    phase b {\n        finish\n    }\n}\n") as run:
        run.engine.run()
    assert run.boot_orders == [["cdrom0", "hdd0"], ["hdd0", "cdrom0"]]


def test_leaving_the_group_restores_and_returning_reapplies():
    """A scope is entered by reaching any phase in it, `goto` from
    outside included."""
    with _scoped("platform dos\nmachine stopped\nentry a\n"
                 "with boot cdrom0 {\n"
                 "    phase a {\n        goto outside\n    }\n}\n"
                 "phase outside {\n    goto back\n}\n"
                 "with boot cdrom0 {\n"
                 "    phase back {\n        finish\n    }\n}\n") as run:
        run.engine.run()
    assert run.boot_orders == [["cdrom0", "hdd0"], ["hdd0", "cdrom0"],
                               ["cdrom0", "hdd0"], ["hdd0", "cdrom0"]]


def test_a_failure_inside_the_scope_still_restores_and_says_so():
    """What the author gave up by scoping is the state a
    diagnostician would have found, so the report has to name it."""
    with _scoped("platform dos\nmachine stopped\nentry a\n"
                 "with boot cdrom0 {\n    phase a {\n"
                 '        wait "never" timeout=1ms\n        finish\n'
                 "    }\n}\n") as run:
        with pytest.raises(ScriptRuntimeError):
            run.engine.run()
    assert run.boot_orders[-1] == ["hdd0", "cdrom0"]
    failure, = _kinds(run.engine, _events.FAILURE)
    assert failure["restored"] == ("the boot order: hdd0 cdrom0",)


def test_a_cancellation_restores_and_the_message_says_so():
    """A cancellation leaves the machine as it stands — and a scope is
    the one thing that does not, so the message names it."""
    with _scoped("platform dos\nmachine stopped\nentry a\n"
                 "with boot cdrom0 {\n    phase a {\n"
                 "        screenshot one\n        screenshot two\n"
                 "        finish\n    }\n}\n") as run:
        with mock.patch.object(_ScriptEngine, "_screenshot",
                               lambda self, statement: self.cancel()):
            with pytest.raises(RunCancelled) as caught:
                run.engine.run()
    assert run.boot_orders == [["cdrom0", "hdd0"], ["hdd0", "cdrom0"]]
    assert "apart from the scoped changes being put back: the boot " \
           "order" in str(caught.value)


def test_a_boot_restore_reached_running_fails_the_run_naming_it():
    """The cost D104 weighed and accepted, and what V17 cannot take.

    A boot order is stopped-only as a property of the machine, and a
    restore is not exempted from it: a second writer under a different
    rule is how such a guarantee erodes. So a run that hands back a
    live machine fails at its last act, saying what it could not undo.

    **The route here is the guest's**, which is the whole reason this
    check still exists at run time. V17 moves the verdict to parse
    time wherever the plan can promise the exit is reached running;
    here one branch stops the machine and the other does not, so the
    static pass answers `unknown` and says nothing — deliberately,
    a false refusal being far worse than this late failure.
    """
    with _scoped("platform dos\nmachine stopped\n"
                 "with boot cdrom0 {\n    start\n"
                 '    wait {\n        on "done" {\n            stop\n'
                 '        }\n        on "failed" {\n'
                 "            screenshot bad\n        }\n    }\n}\n",
                 screens=[["failed"]]) as run:
        def refuse(machine_id, keys, **_kwargs):
            if run.phase == "running":
                raise PreflightError(
                    f"machine {machine_id} must be stopped to change "
                    "boot order (phase: running)",
                    rule_id="machine.must-be-stopped")

        run.machines.set_boot_order.side_effect = refuse
        with mock.patch.object(_ScriptEngine, "_screenshot"):
            with pytest.raises(ScriptRuntimeError) as caught:
                run.engine.run()
    assert "the boot order could not be restored to hdd0 cdrom0" in str(
        caught.value)
    assert caught.value.rule_id == "machine.must-be-stopped"


def test_a_media_restore_needs_no_stopped_machine():
    """`insert` and `eject` are running-or-stopped, so the restore is
    live where the machine is up: the stopped rule the other half
    carries is the boot order's, not the construct's."""
    with _scoped("platform dos\nentry a\n"
                 "with insert cdrom0 @livecd {\n    phase a {\n"
                 "        finish\n    }\n}\n",
                 state=dict(_SCOPED_MACHINE, phase="running")) as run:
        run.engine.run()
    assert run.machines.insert_media.call_args_list[0].args[1:] == (
        "cdrom0", "livecd")
    # The slot was empty when the run arrived, so putting it back is
    # an eject and nothing else.
    run.machines.eject_media.assert_called_once()
    assert not run.machines.set_boot_order.called


def test_a_media_restore_reinstates_the_medium_it_found():
    occupied = json.loads(json.dumps(_SCOPED_MACHINE))
    occupied["phase"] = "running"
    occupied["drives"]["cdrom0"].update(
        {"media": "tools", "path": "/cache/media/tools.iso"})
    with _scoped("platform dos\nentry a\n"
                 "with eject cdrom0 {\n    phase a {\n"
                 "        finish\n    }\n}\n", state=occupied) as run:
        run.engine.run()
    restore, = _kinds(run.engine, _events.SCOPE_RESTORE)
    assert restore["detail"] == "@tools"
    assert run.machines.insert_media.call_args.args[1:] == ("cdrom0", "tools")


def test_a_linear_scope_brackets_exactly_what_it_wraps():
    with _scoped("platform dos\n"
                 "with eject cdrom0 {\n    screenshot one\n}\n"
                 "screenshot two\n",
                 state=dict(_SCOPED_MACHINE, phase="running")) as run:
        with mock.patch.object(_ScriptEngine, "_screenshot"):
            run.engine.run()
    bracket = [event["kind"] for event in run.engine.events.events
               if event["kind"] in (_events.SCOPE_ENTER,
                                    _events.ACTION_START,
                                    _events.SCOPE_RESTORE)]
    assert bracket == [_events.SCOPE_ENTER, _events.ACTION_START,
                       _events.SCOPE_RESTORE]


def test_a_scoped_head_answers_to_the_same_preflight_rules():
    """A `with boot` key is checked where `set-boot`'s already is."""
    script = parse_script(
        "platform dos\nmachine stopped\nentry a\nwith boot cdrom7 {\n"
        "    phase a {\n        finish\n    }\n}\n")
    with pytest.raises(ScriptPreflightError) as caught:
        _preflight_machine_rules(script, {"drives": {"hdd0": {}}}, "s.rlqs")
    assert "the machine declares no drive cdrom7" in str(caught.value)
    assert caught.value.rule_id == "machine.slot-not-declared"


def test_a_scoped_insert_head_must_name_a_removable_slot():
    script = parse_script(
        "platform dos\nwith insert hdd0 @livecd {\n    start\n}\n")
    with pytest.raises(ScriptPreflightError) as caught:
        _preflight_machine_rules(
            script, {"drives": {"hdd0": {"medium": "hdd"}}}, "s.rlqs")
    assert caught.value.rule_id == "machine.slot-not-removable"
