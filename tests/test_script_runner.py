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
import tempfile
import unittest
from unittest import mock


from reliquary import events as _events
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

# The reference script is a shipped builtin, resolved as package
# data so these tests run against an installed artifact too.
import reliquary
_REFERENCE = os.path.join(
    os.path.dirname(os.path.abspath(reliquary.__file__)),
    "codex", "scripts", "freedos-install.rlqs")

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

    def screen(self):
        """The same screens, as the seam's (rows, attributes) pair.

        These scripts say what the guest displayed; the attribute half
        is uniform because nothing here turns on a highlight, and a
        screen that stops changing therefore reads as settled.
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


class _RuntimeCase(unittest.TestCase):
    """Builds engines over a fake console and a controlled clock."""

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
        with mock.patch(
                "reliquary.script_runner._machines") as machines:
            machines.load_machine_state.return_value = {"phase": "running"}
            machines.read_vm_state.return_value = {
                "backend": "qemu", "backend-id": "reliquary-plain-0",
                "token": "0" * 32, "endpoint": {"port": 5555}}
            yield machines


class HelperTests(unittest.TestCase):
    def test_a_row_normalizes_its_whitespace(self):
        self.assertEqual(_normalize_row("  Hello   World  "),
                         "Hello World")

    def test_the_portable_key_names_resolve(self):
        for name in PORTABLE_KEY_NAMES:
            with self.subTest(name=name):
                self.assertTrue(resolve_key(name))
        self.assertEqual(resolve_key("enter"), ["ret"])
        self.assertEqual(resolve_key("pagedown"), ["pgdn"])
        self.assertEqual(resolve_key("ctrl+alt+delete"),
                         ["ctrl", "alt", "delete"])

    def test_a_chord_admits_a_printable_member(self):
        self.assertEqual(resolve_key("ctrl+c"), ["ctrl", "c"])

    def test_a_bare_character_is_not_a_key_name(self):
        with self.assertRaises(StaticError):
            resolve_key("c")

    def test_an_unknown_name_is_not_passed_through(self):
        with self.assertRaises(StaticError):
            resolve_key("oem_3")


class ObservationTests(_RuntimeCase):
    """Single-condition waits, over samples."""

    def test_a_screen_condition_matches_a_normalized_row(self):
        engine = self.engine('wait "Hello World"\n',
                             screens=[["", "  Hello   World  "]])
        self.run_linear(engine)
        # Matched on the first *settled* sample. Establishing
        # quiescence costs the window before any condition is judged
        # (F48), which is the guard's stated price.
        self.assertEqual(self.console.reads, 3)

    def test_a_regex_condition_matches_a_row(self):
        engine = self.engine('wait /installed [0-9]+ packages/\n',
                             screens=[["installed 42 packages"]])
        self.run_linear(engine)

    def test_a_condition_is_matched_only_at_a_fresh_sample(self):
        engine = self.engine('wait "second"\n',
                             screens=[["first"], ["second"]])
        self.run_linear(engine)
        # Each screen is a state the guest holds, and each is judged
        # only once it has settled.
        self.assertEqual(self.console.reads, 6)

    def test_a_timeout_names_the_clock_and_its_source_scope(self):
        engine = self.engine('timeout 10s\nwait "never"\n',
                             screens=[["nothing"]])
        with self.assertRaises(ScriptRuntimeError) as caught:
            self.run_linear(engine)
        message = str(caught.exception)
        self.assertIn("the observation timeout of 10s expired", message)
        self.assertIn("waiting for 'never'", message)
        self.assertIn("from the header (line 2)", message)

    def test_a_timeout_cannot_expire_before_one_sample(self):
        # "A timeout always means samples were taken and none
        # satisfied the condition, never no one looked" -- so a
        # bound already elapsed still gets its sample, and a
        # condition holding there succeeds.
        engine = self.engine('timeout 1ms\nwait "ready"\n',
                             screens=[["ready"]])
        self.clock.now = 60.0
        self.run_linear(engine)
        # And the quiescence gate cannot break that rule: it delays
        # acceptance but never causes a failure by itself, so an
        # already-elapsed bound still evaluates what is on screen
        # rather than expiring on a sample nobody was allowed to read.
        self.assertEqual(self.console.reads, 2)

    def test_the_innermost_bound_is_the_one_enforced(self):
        engine = self.engine(
            'timeout 1h\nwait "never" timeout=4s\n', screens=[["no"]])
        with self.assertRaises(ScriptRuntimeError) as caught:
            self.run_linear(engine)
        self.assertIn("timeout of 4s", str(caught.exception))
        self.assertIn("from the statement", str(caught.exception))

    def test_stable_requires_the_episode_to_hold(self):
        engine = self.engine('wait "ready" stable=4s\n',
                             screens=[["ready"]])
        self.run_linear(engine)
        # One *settled* sample arms the episode; the hold is satisfied
        # only once its age reaches the duration. The extra reads are
        # the quiescence window, paid before the episode starts.
        self.assertEqual(self.console.reads, 5)

    def test_an_interrupted_episode_restarts_the_hold(self):
        engine = self.engine(
            'wait "ready" stable=2s\n',
            screens=[["ready"], ["busy"], ["ready"], ["ready"]])
        self.run_linear(engine)
        # "busy" ends the episode and the hold starts over, each state
        # judged once it has settled.
        self.assertEqual(self.console.reads, 10)

    def test_a_machine_condition_observes_the_backend(self):
        engine = self.engine("wait machine=stopped\n", fail=True)
        with mock.patch(
                "reliquary.script_runner._machines") as machines:
            self.run_linear(engine)
            machines.mark_stopped.assert_called_once_with(
                "plain-0", context="/tmp/home")
        self.assertFalse(engine._running)

    def test_an_unreachable_vm_runtime_error_is_stopped(self):
        # Production path: the adapter reports an unreachable VM as a
        # PREFLIGHT ERROR naming its rule. That must still count as
        # the stopped sample (not escape the wait).
        engine = self.engine("wait machine=stopped\n")

        @contextlib.contextmanager
        def unreachable():
            raise PreflightError(
                "the recorded reliquary VM is no longer reachable\n"
                "  expected: reliquary-plain-0 on 127.0.0.1:5555",
                rule_id="machine.vm-unreachable")
            yield  # pragma: no cover

        engine._console = unreachable
        with mock.patch(
                "reliquary.script_runner._machines") as machines:
            self.run_linear(engine)
            machines.mark_stopped.assert_called_once_with(
                "plain-0", context="/tmp/home")
        self.assertFalse(engine._running)

    def test_identity_mismatch_is_not_treated_as_stopped(self):
        engine = self.engine("wait machine=stopped\n")

        @contextlib.contextmanager
        def mismatch():
            raise PreflightError(
                "QMP identity mismatch; the unrelated VM was "
                "not modified", rule_id="machine.identity-mismatch")
            yield  # pragma: no cover

        engine._console = mismatch
        with self.assertRaises(PreflightError) as caught:
            self.run_linear(engine)
        self.assertIn("identity mismatch", str(caught.exception))
        self.assertTrue(engine._running)

    def test_a_stopped_machine_satisfies_without_a_console(self):
        engine = self.engine("wait machine=stopped\n", running=False)
        self.run_linear(engine)
        self.assertEqual(self.console.reads, 0)

    def test_an_unreadable_screen_is_a_sample_the_wait_looks_past(self):
        # Every VirtualBox boot paints a graphics-mode BIOS splash
        # before the guest reaches text, and the recognizer can say
        # nothing about it. That is not the end of the run: the wait
        # keeps polling and matches once a text screen arrives.
        engine = self.engine('wait "ready"\n', screens=[["ready"]])
        splashes = [2]
        inner = self.console.screen

        def screen():
            if splashes[0]:
                splashes[0] -= 1
                self.console.reads += 1
                raise UnreadableScreen(
                    "framebuffer 640x480 is not an even 80x25 text grid",
                    rule_id="recognize.geometry")
            return inner()

        self.console.screen = screen
        self.run_linear(engine)
        self.assertEqual(splashes[0], 0)

    def test_an_unreadable_screen_is_not_a_stopped_machine(self):
        # It is not a blank screen and it is not an absent one: a guest
        # painting in a mode we cannot read is running perfectly well,
        # so `machine=stopped` must not be satisfied by it and the
        # machine must not be marked down.
        engine = self.engine('timeout 10s\nwait machine=stopped\n')

        @contextlib.contextmanager
        def unreadable():
            raise UnreadableScreen(
                "framebuffer 640x480 is not an even 80x25 text grid",
                rule_id="recognize.geometry")
            yield  # pragma: no cover

        engine._console = unreadable
        with mock.patch(
                "reliquary.script_runner._machines") as machines:
            with self.assertRaises(ScriptRuntimeError):
                self.run_linear(engine)
            machines.mark_stopped.assert_not_called()
        self.assertTrue(engine._running)

    def test_a_screen_observation_needs_a_running_machine(self):
        engine = self.engine('machine stopped\nwait "x"\n', running=False)
        with self.assertRaises(ScriptRuntimeError) as caught:
            self.run_linear(engine)
        self.assertIn("machine is not running", str(caught.exception))


class BranchingWaitTests(_RuntimeCase):
    """The first condition that holds fires its handler."""

    _SOURCE = (
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

    def test_declaration_order_decides_a_tie(self):
        engine = self.engine(
            self._SOURCE, screens=[["partitioned and formatted"]])
        self.run_phases(engine)
        self.assertIn(("send_text", "part", True), self.console.commands)

    def test_a_later_handler_fires_when_only_it_holds(self):
        engine = self.engine(self._SOURCE, screens=[["formatted"]])
        self.run_phases(engine)
        self.assertIn(("send_text", "form", True), self.console.commands)

    def test_a_handler_body_runs_with_no_session_held(self):
        # QEMU's QMP server admits one client at a time: a body that
        # opens its own session while the sample loop still held one
        # would block forever against a real machine.
        engine = self.engine(self._SOURCE, screens=[["formatted"]])
        depth = {"open": 0, "overlap": False}

        @contextlib.contextmanager
        def console():
            depth["open"] += 1
            depth["overlap"] = depth["overlap"] or depth["open"] > 1
            try:
                yield self.console
            finally:
                depth["open"] -= 1

        engine._console = console
        self.run_phases(engine)
        self.assertFalse(depth["overlap"])

    def test_execution_continues_after_a_falling_handler(self):
        engine = self.engine(
            'wait {\n    on "go" {\n        press enter\n    }\n'
            '    on "stop" {\n        press esc\n    }\n}\n'
            'enter "after"\n', screens=[["go"]])
        self.run_linear(engine)
        self.assertEqual(self.console.keys, [["ret"]])
        self.assertIn(("send_text", "after", True), self.console.commands)

    def test_a_branching_timeout_names_every_condition(self):
        engine = self.engine(
            'timeout 5s\nwait {\n    on "a" {\n        press enter\n'
            '    }\n    on /b/ {\n        press esc\n    }\n}\n',
            screens=[["neither"]])
        with self.assertRaises(ScriptRuntimeError) as caught:
            self.run_linear(engine)
        self.assertIn("waiting for 'a' or /b/", str(caught.exception))

    def test_a_handler_condition_may_name_a_channel(self):
        engine = self.engine(
            'wait {\n    on "up" {\n        press enter\n    }\n'
            "    on machine=stopped {\n        eject cdrom0\n    }\n}\n",
            fail=True)
        with mock.patch(
                "reliquary.script_runner._machines") as machines:
            self.run_linear(engine)
            machines.eject_media.assert_called_once_with(
                "plain-0", "cdrom0", context="/tmp/home")
        self.assertEqual(self.console.keys, [])


class StabilityGateTests(_RuntimeCase):
    """A condition is judged only on a settled screen (F48)."""

    def painting(self, count=80):
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

    def test_a_condition_on_a_painting_screen_is_not_matched(self):
        # the text is plainly there — a screenshot taken at the time
        # would show it — but the screen around it is still being
        # drawn, so it is not a sample the condition is judged on
        engine = self.engine("timeout 3s\nwait \"ready\"\n",
                             screens=self.painting(), hold=1)

        with self.assertRaises(ScriptRuntimeError) as caught:
            self.run_linear(engine)

        self.assertIn("never settled", str(caught.exception))

    def test_the_gate_names_itself_when_the_wait_expires(self):
        # a wait now expires two ways that look identical from
        # outside, and the failure has to say which
        engine = self.engine("timeout 3s\nwait \"ready\"\n",
                             screens=self.painting(), hold=1)

        with self.assertRaises(ScriptRuntimeError) as caught:
            self.run_linear(engine)

        self.assertIn("stability", str(caught.exception))

    def test_stability_zero_turns_the_guard_off(self):
        # the escape for a screen the default would refuse, and it
        # must cost nothing at all — not even the window that
        # establishing quiescence would otherwise take
        engine = self.engine(
            "timeout 3s\nwait \"ready\" stability=0\n",
            screens=self.painting(), hold=1)

        self.run_linear(engine)

        self.assertEqual(self.console.reads, 1)

    def test_a_settled_screen_is_matched_normally(self):
        # the same script against a guest that has stopped drawing
        engine = self.engine("timeout 3s\nwait \"ready\"\n",
                             screens=[["ready", "copying done"]])

        self.run_linear(engine)

        self.assertEqual(self.console.reads, 3)


class ReactivePhaseTests(_RuntimeCase):
    """Standing handlers, run to completion, once per episode."""

    def test_a_handler_fires_once_per_appearance(self):
        engine = self.engine(
            "entry copying\ndeadline 1h\n"
            "phase copying timeout=1h {\n"
            '    always "insert disk 2" {\n        press enter\n    }\n'
            '    always "complete" {\n        finish\n    }\n}\n',
            screens=[["insert disk 2"], ["insert disk 2"],
                     ["insert disk 2"], ["copying"], ["insert disk 2"],
                     ["complete"]])
        self.run_phases(engine)
        # However long the prompt stays displayed, it fires once per
        # appearance: twice here, not five times.
        self.assertEqual(self.console.keys, [["ret"], ["ret"]])

    def test_a_handler_transfers_immediately(self):
        engine = self.engine(
            "entry watch\ndeadline 1h\nphase watch {\n"
            '    always "done" {\n        goto after\n    }\n}\n'
            'phase after {\n    enter "next"\n    finish\n}\n',
            screens=[["done"]])
        self.run_phases(engine)
        self.assertIn(("send_text", "next", True), self.console.commands)

    def test_declaration_order_decides_which_handler_fires(self):
        engine = self.engine(
            "entry watch\ndeadline 1h\nphase watch {\n"
            '    always "first" {\n        press enter\n    }\n'
            '    always "second" {\n        finish\n    }\n}\n',
            screens=[["first and second"], ["second"]])
        self.run_phases(engine)
        self.assertEqual(self.console.keys, [["ret"]])

    def test_the_interval_expires_with_no_handler_firing(self):
        engine = self.engine(
            "entry watch\nphase watch timeout=5s {\n"
            '    always "never" {\n        finish\n    }\n}\n',
            screens=[["quiet"]])
        with self.assertRaises(ScriptRuntimeError) as caught:
            self.run_phases(engine)
        message = str(caught.exception)
        self.assertIn("the reactive interval of 5s expired", message)
        self.assertIn("with no handler firing", message)
        self.assertIn("from the phase watch", message)

    def test_a_fired_handler_restarts_the_interval(self):
        engine = self.engine(
            "entry watch\nphase watch timeout=6s {\n"
            '    always "tick" {\n        press enter\n    }\n'
            '    always "done" {\n        finish\n    }\n}\n',
            screens=[["tick"], ["quiet"], ["tick"], ["quiet"],
                     ["tick"], ["done"]])
        self.run_phases(engine)
        self.assertEqual(len(self.console.keys), 3)


class PhaseTransitionTests(_RuntimeCase):
    def test_a_run_walks_the_graph_from_entry_to_finish(self):
        engine = self.engine(
            "entry one\n"
            'phase one {\n    enter "1"\n    goto two\n}\n'
            'phase two {\n    enter "2"\n    finish\n}\n')
        self.run_phases(engine)
        self.assertEqual(
            [command[1] for command in self.console.commands], ["1", "2"])
        self.assertEqual(engine._phase.name, "two")

    def test_a_phase_budget_is_fresh_at_each_entry(self):
        engine = self.engine(
            "entry loop\ndeadline 1h\n"
            "phase loop deadline=10s {\n"
            '    wait "go"\n    goto next\n}\n'
            "phase next {\n    goto loop\n}\n",
            screens=[["go"]])
        # Two activations, each budgeted afresh; without the reset
        # the second entry would expire on the first clock check.
        self.clock.now = 0.0
        transfers = []
        original = engine._execute

        def watched(statements):
            transfers.append(engine._phase.name)
            self.clock.now += 8.0
            if len(transfers) > 3:
                raise AssertionError("the graph never converged")
            return original(statements)

        engine._execute = watched
        with self.assertRaises(AssertionError):
            self.run_phases(engine)
        self.assertEqual(transfers[:3], ["loop", "next", "loop"])

    def test_a_phase_deadline_expires_at_a_boundary(self):
        engine = self.engine(
            "entry slow\ndeadline 1h\n"
            "phase slow deadline=3s {\n"
            '    wait "never" timeout=1h\n    finish\n}\n',
            screens=[["quiet"]])
        with self.assertRaises(ScriptRuntimeError) as caught:
            self.run_phases(engine)
        message = str(caught.exception)
        self.assertIn("the phase deadline of 3s expired", message)
        self.assertIn("from the phase slow", message)

    def test_the_run_deadline_backstops_a_cycle(self):
        engine = self.engine(
            "entry loop\ndeadline 5s\n"
            "phase loop {\n    goto loop\n}\n")
        with self.assertRaises(ScriptRuntimeError) as caught:
            with contextlib.redirect_stdout(io.StringIO()):
                engine._run_started = self.clock()
                self.clock.now = 6.0
                engine._run_phases()
        self.assertIn("the run deadline of 5s expired",
                      str(caught.exception))
        self.assertIn("from the header", str(caught.exception))


class InputVerbTests(_RuntimeCase):
    def test_enter_types_and_presses_enter(self):
        engine = self.engine('enter "fdapm poweroff"\n')
        self.run_linear(engine)
        self.assertEqual(self.console.commands,
                         [("send_text", "fdapm poweroff", True)])

    def test_type_sends_text_with_no_ending(self):
        engine = self.engine('type "A:"\n')
        self.run_linear(engine)
        self.assertEqual(self.console.commands,
                         [("send_text", "A:", False)])

    def test_press_sends_a_sequence_of_keys(self):
        engine = self.engine("press down down enter\n")
        self.run_linear(engine)
        self.assertEqual(self.console.keys,
                         [["down"], ["down"], ["ret"]])

    def test_select_runs_under_its_effective_timeout(self):
        engine = self.engine(
            'timeout 45s\nselect "Plain DOS system" '
            'exclude="with sources"\n')
        self.run_linear(engine)
        self.assertEqual(
            self.console.commands,
            [("select", "Plain DOS system", 45.0, ("with sources",))])

    def test_every_guest_input_verb_pays_the_pacing_gap(self):
        """The pause lands before the first key event, once per verb.

        The fake clock only advances when the engine sleeps, so the
        elapsed time *is* the gap that was taken.
        """
        for source, expected in (('enter "x"\n', 0.1),
                                 ('type "x"\n', 0.1),
                                 ("press enter\n", 0.1),
                                 ('select "Yes"\n', 0.1)):
            with self.subTest(source=source):
                engine = self.engine(source)
                self.run_linear(engine)
                self.assertAlmostEqual(self.clock.now, expected)

    def test_a_host_side_verb_pays_nothing(self):
        engine = self.engine("set answer \"42\"\n")
        with mock.patch("reliquary.script_runner._machines"):
            self.run_linear(engine)
        self.assertEqual(self.clock.now, 0.0)

    def test_the_gap_is_the_one_the_plan_resolved(self):
        engine = self.engine('pacing 2s\nenter "x" pacing=5s\n')
        self.run_linear(engine)
        self.assertAlmostEqual(self.clock.now, 5.0)

    def test_the_header_gap_applies_where_no_statement_says(self):
        engine = self.engine('pacing 2s\nenter "x"\n')
        self.run_linear(engine)
        self.assertAlmostEqual(self.clock.now, 2.0)

    def test_a_zero_gap_does_not_sleep(self):
        """`pacing=0s` is the author saying the guest is ready."""
        engine = self.engine('enter "x" pacing=0s\n')
        self.run_linear(engine)
        self.assertEqual(self.clock.now, 0.0)

    def test_the_gap_precedes_delivery(self):
        """Nothing reaches the console until the guest has settled.

        A gap taken *after* delivery would pace nothing; this is the
        whole point of the feature, so it is asserted directly rather
        than inferred from the elapsed total.
        """
        engine = self.engine('enter "x" pacing=3s\n')
        observed = []
        original = self.clock.sleep

        def watch(seconds):
            observed.append(("sleep", seconds, list(self.console.commands)))
            original(seconds)

        engine._sleep = watch
        self.run_linear(engine)
        self.assertEqual(observed, [("sleep", 3.0, [])])
        self.assertEqual(self.console.commands,
                         [("send_text", "x", True)])

    def test_an_unbound_property_reference_is_a_named_error(self):
        for source in ('enter "setup /owner=${owner}"\n',
                       'wait "welcome ${owner}"\n'):
            engine = self.engine("property owner\n" + source,
                                 screens=[["quiet"]])
            with self.assertRaises(ScriptRuntimeError, msg=source) as caught:
                self.run_linear(engine)
            self.assertIn("${owner} has no bound value",
                          str(caught.exception), msg=source)

    def test_a_bound_property_expands_into_enter(self):
        engine = self.engine(
            'property owner\nenter "setup /owner=${owner}"\n',
            bindings=BoundProperties({"owner": "Paul"}, {"owner": "flag"}))
        self.run_linear(engine)
        self.assertEqual(
            self.console.commands,
            [("send_text", "setup /owner=Paul", True)])

    def test_a_bound_media_property_selects_the_insert_target(self):
        with mock.patch("reliquary.script_runner._machines") as machines:
            engine = self.engine(
                "property media disk\ninsert cdrom0 $disk\n",
                bindings=BoundProperties(
                    {"disk": "supplemental"}, {"disk": "flag"}))
            self.run_linear(engine)
        machines.insert_media.assert_called_once_with(
            "plain-0", "cdrom0", "supplemental", context="/tmp/home",
            events=engine.events, cancelled=engine._cancelled)

    def test_a_secret_value_is_redacted_from_the_event_stream(self):
        bound = BoundProperties(
            {"pw": "swordfish"}, {"pw": "properties file"},
            frozenset({"pw"}))
        engine = self.engine(
            'property secret pw\ntype "${pw}"\n', bindings=bound)
        engine._execute(engine._script.statements)
        # The guest still receives the real value...
        self.assertEqual(
            self.console.commands, [("send_text", "swordfish", False)])
        # ...but the stream shows the marker, never the secret.
        rendered = json.dumps(engine.events.events, ensure_ascii=False)
        self.assertNotIn("swordfish", rendered)
        self.assertIn("«secret»", rendered)


class MachineOperationTests(_RuntimeCase):
    def test_insert_resolves_a_media_reference(self):
        engine = self.engine("insert cdrom0 @freedos-livecd\n")
        with mock.patch(
                "reliquary.script_runner._machines") as machines:
            self.run_linear(engine)
            # The run's own stream and cancel event travel with the
            # insert: an insert can pull hundreds of megabytes, so
            # without the stream the fetch reports nothing (silence
            # reads as a hang) and without the event a Ctrl-C is not
            # seen until the whole statement finishes.
            machines.insert_media.assert_called_once_with(
                "plain-0", "cdrom0", "freedos-livecd",
                context="/tmp/home",
                events=engine.events, cancelled=engine._cancelled)

    def test_insert_from_a_property_reports_the_resolved_media(self):
        # A `$` insert defers the choice to run time, so the page
        # cannot say which media it is. The stream can, and does:
        # the action names the resolved item, spelled `@`, so a
        # reader of the run sees exactly what was mounted.
        stream = _events.EventStream()
        engine = self.engine(
            "property media supplemental\n"
            "insert floppy1 $supplemental\n",
            bindings=BoundProperties({"supplemental": "win98-cd"},
                                     {"supplemental": "flag"}),
            events=stream)
        with mock.patch("reliquary.script_runner._machines"):
            self.run_linear(engine)
        actions = [event for event in stream.events
                   if event["kind"] == _events.ACTION_START
                   and event.get("verb") == "insert"]
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["detail"], "floppy1 @win98-cd")

    def test_insert_from_a_property_is_not_bound_yet(self):
        engine = self.engine(
            "property media supplemental\n"
            "insert floppy1 $supplemental\n")
        with mock.patch("reliquary.script_runner._machines"):
            with self.assertRaises(ScriptRuntimeError) as caught:
                self.run_linear(engine)
        self.assertIn("has no bound value", str(caught.exception))

    def test_set_records_a_machine_variable(self):
        engine = self.engine('set result "PASS"\n')
        with mock.patch(
                "reliquary.script_runner._machines") as machines:
            self.run_linear(engine)
            machines.set_machine_var.assert_called_once_with(
                "plain-0", "result", "PASS", context="/tmp/home")

    def test_a_set_value_interpolates_a_bound_property(self):
        bound = BoundProperties({"tag": "v2"}, {"tag": "--property"})
        engine = self.engine(
            'property tag\nset build "${tag}"\n', bindings=bound)
        with mock.patch(
                "reliquary.script_runner._machines") as machines:
            self.run_linear(engine)
            machines.set_machine_var.assert_called_once_with(
                "plain-0", "build", "v2", context="/tmp/home")

    def test_eject_empties_the_slot(self):
        engine = self.engine("eject cdrom0\n")
        with mock.patch(
                "reliquary.script_runner._machines") as machines:
            self.run_linear(engine)
            machines.eject_media.assert_called_once_with(
                "plain-0", "cdrom0", context="/tmp/home")

    def test_set_boot_replaces_the_boot_order(self):
        engine = self.engine("set-boot hdd0 cdrom0\n")
        with mock.patch(
                "reliquary.script_runner._machines") as machines:
            self.run_linear(engine)
            machines.set_boot_order.assert_called_once_with(
                "plain-0", ("hdd0", "cdrom0"), context="/tmp/home")

    def test_a_machine_change_failure_reports_its_line(self):
        engine = self.engine("insert cdrom0 @freedos-livecd\n")
        with mock.patch(
                "reliquary.script_runner._machines") as machines:
            machines.insert_media.side_effect = PreflightError(
                "machine plain-0 declares no drive cdrom0")
            with self.assertRaises(ScriptRuntimeError) as caught:
                self.run_linear(engine)
        self.assertIn("declares no drive", str(caught.exception))
        self.assertIn("line 2", str(caught.exception))

    def test_start_and_stop_track_whether_the_machine_runs(self):
        engine = self.engine("stop\nstart\n")
        with mock.patch(
                "reliquary.script_runner._machines") as machines:
            self.run_linear(engine)
            machines.stop_machine.assert_called_once_with(
                "plain-0", context="/tmp/home")
        self.assertTrue(engine._running)

    def test_a_screenshot_rests_with_its_machine(self):
        # No run directory exists any more (D36): an author's
        # screenshot lands under the machine it was taken from.
        engine = self.engine("screenshot installed\n")
        with mock.patch("reliquary.script_runner.Machine") as machine:
            self.run_linear(engine)
        machine.assert_called_once_with(
            "/tmp/home/cache/machines/plain-0")
        machine.return_value.screenshot.assert_called_once_with(
            "installed")

    def test_a_screenshot_defaults_to_its_step_number(self):
        engine = self.engine("screenshot\n")
        with mock.patch("reliquary.script_runner.Machine") as machine:
            self.run_linear(engine)
        machine.return_value.screenshot.assert_called_once_with("step-1")


class CancellationTests(_RuntimeCase):
    """A cancellation ends the run at the next event boundary."""

    def test_a_pending_cancel_stops_at_the_next_boundary(self):
        engine = self.engine('wait "a"\nwait "b"\n',
                             screens=[["a"], ["b"]])
        engine.cancel()
        with self.assertRaises(RunCancelled):
            self.run_linear(engine)
        # Nothing was observed: the very first boundary caught it.
        self.assertEqual(self.console.reads, 0)

    def test_an_input_in_flight_completes_before_the_stop(self):
        engine = self.engine('enter "FORMAT C:"\nenter "second"\n')
        original = engine._enter

        def enter_then_cancel(statement):
            original(statement)
            engine.cancel()

        engine._enter = enter_then_cancel
        with self.assertRaises(RunCancelled):
            self.run_linear(engine)
        # The delivery is atomic: the first line reached the guest
        # whole, and the second never started.
        self.assertEqual(
            self.console.commands, [("send_text", "FORMAT C:", True)])

    def test_the_terminal_event_reports_the_cancellation(self):
        engine = self.engine('wait "a"\n', screens=[["a"]])
        engine.cancel()
        with self.whole_run():
            with self.assertRaises(RunCancelled):
                engine.run()
        terminal = engine.events.events[-1]
        self.assertEqual(terminal["kind"], "run.end")
        self.assertEqual(terminal["outcome"], "cancelled")
        self.assertEqual(terminal["exit-code"], 5)


class FailureReportTests(_RuntimeCase):
    """A failure names the route, the clock, and what to try next."""

    def _failed_run(self, source, screens):
        engine = self.engine(source, screens=screens)
        with self.whole_run(), \
                mock.patch("reliquary.script_runner.screenshot"):
            with self.assertRaises(ScriptRuntimeError):
                engine.run()
        by_kind = {event["kind"]: event for event in engine.events.events}
        return engine, by_kind

    def test_the_report_names_the_clock_and_its_scope(self):
        _engine, by_kind = self._failed_run(
            'timeout 10s\nwait "never"\n', [["nothing here"]])
        failure = by_kind["failure"]
        self.assertIn("the observation timeout of 10s", failure["clock"])
        self.assertIn("header", failure["scope"])
        self.assertEqual(failure["pending"], "'never'")

    def test_the_report_names_the_nearest_miss(self):
        _engine, by_kind = self._failed_run(
            'timeout 10s\nwait "Welcome to FreeDOS"\n',
            [["Welcome to FreeDO"]])
        self.assertEqual(by_kind["failure"]["nearest-miss"],
                         "Welcome to FreeDO")

    def test_the_report_names_a_screen_that_could_never_be_read(self):
        # The case the nearest miss cannot answer: with no rows at any
        # sample, nothing was ever near the target, and a silent report
        # would look like a condition that merely never matched.
        engine = self.engine('timeout 10s\nwait "ready"\n')

        @contextlib.contextmanager
        def unreadable():
            raise UnreadableScreen(
                "framebuffer 640x480 is not an even 80x25 text grid",
                rule_id="recognize.geometry")
            yield  # pragma: no cover

        engine._console = unreadable
        with self.whole_run(), \
                mock.patch("reliquary.script_runner.screenshot"):
            with self.assertRaises(ScriptRuntimeError):
                engine.run()
        failure = [event for event in engine.events.events
                   if event["kind"] == "failure"][0]
        self.assertIn("640x480", failure["unreadable-screen"])
        self.assertNotIn("nearest-miss", failure)

    def test_the_report_suggests_a_next_command(self):
        _engine, by_kind = self._failed_run(
            'timeout 10s\nwait "never"\n', [["nothing"]])
        self.assertIn("rlq screen --machine plain-0",
                      by_kind["failure"]["next-command"])

    def test_the_route_and_its_revisits_are_reported(self):
        # Each phase spends one poll interval, so the run deadline
        # trips only after the graph has been walked twice round.
        engine = self.engine(
            'timeout 10s\ndeadline 5s\nentry first\n'
            'phase first {\n    wait "a" stable=1s\n    goto second\n}\n'
            'phase second {\n    wait "a" stable=1s\n    goto first\n}\n',
            screens=[["a"]])
        with self.whole_run(), \
                mock.patch("reliquary.script_runner.screenshot"):
            with self.assertRaises(ScriptRuntimeError):
                engine.run()
        failure = [event for event in engine.events.events
                   if event["kind"] == "failure"][0]
        self.assertEqual(list(failure["route"][:3]),
                         ["first", "second", "first"])
        self.assertGreaterEqual(failure["revisits"]["first"], 2)

    def test_a_screenshot_is_suppressed_after_a_secret_is_typed(self):
        bound = BoundProperties(
            {"pw": "swordfish"}, {"pw": "properties file"},
            frozenset({"pw"}))
        engine = self.engine(
            'timeout 10s\nproperty secret pw\ntype "${pw}"\n'
            'wait "never"\n', screens=[["nothing"]], bindings=bound)
        with self.whole_run(), \
                mock.patch(
                    "reliquary.script_runner.screenshot") as capture:
            with self.assertRaises(ScriptRuntimeError):
                engine.run()
        capture.assert_not_called()
        failure = [event for event in engine.events.events
                   if event["kind"] == "failure"][0]
        self.assertNotIn("screenshot", failure)


class HttpLifecycleTests(_RuntimeCase):
    """Run-scoped HTTP starts, stops, and cleans up predictably."""

    def test_http_start_serves_declared_content_and_binds_url(self):
        engine = self.engine(
            "http port-min=8123 port-max=8123 {\n"
            '    content answer "/answer.txt" """\n'
            "        one\n"
            "    \"\"\"\n"
            "}\n"
            "http start answer\n"
            'enter "${rlq.http.url}/answer.txt"\n')
        self.run_linear(engine)
        service = _FakeHttpService.instances[0]
        self.assertEqual(service.port_min, 8123)
        self.assertEqual([response.path for response in service.responses],
                         ["/answer.txt"])
        self.assertEqual(service.responses[0].body, b"one\n")
        self.assertIn(("send_text",
                       "http://10.0.2.2:8123/answer.txt", True),
                      self.console.commands)

    def test_http_stop_is_noop_when_already_stopped(self):
        engine = self.engine("http stop\n")
        self.run_linear(engine)
        self.assertEqual(_FakeHttpService.instances, [])
        self.assertEqual(engine._bindings, {})

    def test_http_stop_clears_runtime_bindings(self):
        engine = self.engine(
            "http {\n"
            '    content answer "/answer.txt" """\n'
            "        one\n"
            "    \"\"\"\n"
            "}\n"
            "http start\n"
            "http stop\n"
            'enter "${rlq.http.url}/answer.txt"\n')
        with self.assertRaises(ScriptRuntimeError) as caught:
            self.run_linear(engine)
        self.assertIn("${rlq.http.url} has no bound value",
                      str(caught.exception))
        self.assertEqual(_FakeHttpService.instances[0].stopped, 1)

    def test_http_start_without_names_serves_all_declared_content(self):
        engine = self.engine(
            "http {\n"
            '    content one "/one.txt" """\n        one\n    """\n'
            '    content two "/two.txt" """\n        two\n    """\n'
            "}\n"
            "http start\n")
        self.run_linear(engine)
        self.assertEqual(
            [response.path for response in _FakeHttpService.instances[0]
             .responses],
            ["/one.txt", "/two.txt"])

    def test_http_start_names_only_selected_content(self):
        engine = self.engine(
            "http {\n"
            '    content one "/one.txt" """\n        one\n    """\n'
            '    content two "/two.txt" """\n        two\n    """\n'
            "}\n"
            "http start two\n")
        self.run_linear(engine)
        self.assertEqual(
            [response.path for response in _FakeHttpService.instances[0]
             .responses],
            ["/two.txt"])

    def test_http_start_redefines_specific_content_for_that_start(self):
        engine = self.engine(
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
        self.run_linear(engine)
        self.assertEqual(
            _FakeHttpService.instances[0].responses[0].body, b"two\n")

    def test_http_redefinition_must_leave_final_paths_unique(self):
        engine = self.engine(
            "http {\n"
            '    content one "/one.txt" """\n        one\n    """\n'
            '    content two "/two.txt" """\n        two\n    """\n'
            "}\n"
            "http start {\n"
            '    content one "/two.txt" """\n'
            "        replacement\n"
            "    \"\"\"\n"
            "}\n")
        with self.assertRaises(ScriptRuntimeError) as caught:
            self.run_linear(engine)
        self.assertIn("duplicate path: /two.txt", str(caught.exception))

    def test_http_restart_stops_the_previous_server(self):
        engine = self.engine(
            "http {\n"
            '    content answer "/answer.txt" """\n'
            "        one\n"
            "    \"\"\"\n"
            "}\n"
            "http start\n"
            "http start\n")
        self.run_linear(engine)
        self.assertEqual(len(_FakeHttpService.instances), 2)
        self.assertEqual(_FakeHttpService.instances[0].stopped, 1)
        self.assertEqual(_FakeHttpService.instances[1].started, 1)

    def test_http_is_implied_stopped_when_engine_run_succeeds(self):
        engine = self.engine(
            "http {\n"
            '    content answer "/answer.txt" """\n'
            "        one\n"
            "    \"\"\"\n"
            "}\n"
            "http start\n")
        with mock.patch.object(engine, "_establish_machine"), \
                contextlib.redirect_stdout(io.StringIO()):
            engine.run()
        self.assertEqual(_FakeHttpService.instances[0].stopped, 1)
        self.assertEqual(engine._bindings, {})

    def test_http_is_implied_stopped_when_engine_run_fails(self):
        engine = self.engine(
            "http {\n"
            '    content answer "/answer.txt" """\n'
            "        one\n"
            "    \"\"\"\n"
            "}\n"
            "http start\n"
            'enter "${missing.value}"\n')
        with mock.patch.object(engine, "_establish_machine"), \
                self.assertRaises(ScriptRuntimeError), \
                contextlib.redirect_stdout(io.StringIO()):
            engine.run()
        self.assertEqual(_FakeHttpService.instances[0].stopped, 1)
        self.assertEqual(engine._bindings, {})


class HttpServiceIntegrationTests(unittest.TestCase):
    """The real HTTP service serves the response map over a socket."""

    def tearDown(self):
        service = getattr(self, "service", None)
        if service is not None:
            service.stop()
        blocker = getattr(self, "blocker", None)
        if blocker is not None:
            blocker.close()

    def test_get_head_and_404(self):
        port = self._free_port()
        self.service = _HttpService((
            _HttpResponse("answer", "/answer.txt", b"hello\n"),
        ), port, port)
        self.service.start()

        connection = http.client.HTTPConnection(
            "127.0.0.1", self.service.port, timeout=5)
        try:
            connection.request("GET", "/answer.txt")
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(response.read(), b"hello\n")
            self.assertEqual(response.getheader("Content-Length"), "6")

            connection.request("HEAD", "/answer.txt")
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(response.read(), b"")
            self.assertEqual(response.getheader("Content-Length"), "6")

            connection.request("GET", "/missing.txt")
            response = connection.getresponse()
            self.assertEqual(response.status, 404)
            response.read()
        finally:
            connection.close()

    def test_port_selection_skips_occupied_ports(self):
        first, second = self._free_adjacent_pair()
        self.blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.blocker.bind(("", first))
        self.blocker.listen(1)

        self.service = _HttpService((
            _HttpResponse("answer", "/answer.txt", b"hello\n"),
        ), first, second)
        self.service.start()

        self.assertEqual(self.service.port, second)

    def _free_port(self):
        while True:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            if port < 65535:
                return port

    def _free_adjacent_pair(self):
        for _ in range(100):
            first = self._free_port()
            second_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                second_sock.bind(("127.0.0.1", first + 1))
                return first, first + 1
            except OSError:
                continue
            finally:
                second_sock.close()
        self.fail("could not find adjacent free TCP ports")


class ExecutePreflightTests(unittest.TestCase):
    """Static preflight and machine-header checks before guest input."""

    def setUp(self):
        self.workdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.workdir.cleanup)
        self.home = self.workdir.name
        self.machine_id = "plain-0"

    def _write_media(self, *names):
        """Declare media in the home so `@name` preflights."""
        blueprints = os.path.join(self.home, "blueprints")
        os.makedirs(blueprints, exist_ok=True)
        with open(os.path.join(blueprints, "lib.rlqb"), "w",
                  encoding="utf-8") as handle:
            json.dump([{"type": "media", "name": name,
                        "location": {"local": f"/{name}.iso"}}
                       for name in names], handle)

    def _write_state(self, phase="ready", drives=None):
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

    def test_an_empty_script_reports_the_machine_phase(self):
        self._write_state()
        script = parse_script(_HEAD)
        self.assertEqual(
            execute_script(script, machine_id=self.machine_id,
                           context=self.home),
            ("-", "ready"))

    def test_insert_to_an_undeclared_slot_fails_before_execution(self):
        self._write_state()
        script = parse_script(
            _HEAD + "machine stopped\n"
            "insert cdrom0 @freedos-livecd\nstart\n")
        with self.assertRaises(ScriptPreflightError) as caught:
            execute_script(script, machine_id=self.machine_id,
                           context=self.home)
        self.assertIn("declares no drive cdrom0", str(caught.exception))
        self.assertIn("line 3", str(caught.exception))

    def test_an_unknown_media_reference_fails_before_execution(self):
        # script-spec.md, "Validation and preflight": preflight
        # rejects "media references (@name) naming no media the
        # namespace defines".
        self._write_media("freedos-livecd")
        self._write_state(drives={
            "cdrom0": {"medium": "cdrom", "slot": 0},
        })
        script = parse_script(
            _HEAD + "machine stopped\ninsert cdrom0 @freedos-livecdd\n")
        with self.assertRaises(ScriptPreflightError) as caught:
            execute_script(script, machine_id=self.machine_id,
                           context=self.home)
        message = str(caught.exception)
        self.assertIn("no media named 'freedos-livecdd'", message)
        self.assertIn("did you mean 'freedos-livecd'", message)
        self.assertIn("line 3", message)

    def test_a_property_media_reference_is_not_preflighted(self):
        # $name defers to binding by design, so it cannot be
        # checked here and must not be rejected.
        self._write_state(drives={
            "cdrom0": {"medium": "cdrom", "slot": 0},
        })
        script = parse_script(
            _HEAD + "machine stopped\nproperty media disk\n"
            "insert cdrom0 $disk\n")
        state = {"id": self.machine_id, "phase": "ready",
                 "drives": {"cdrom0": {"medium": "cdrom", "slot": 0}}}
        _preflight_machine_rules(script, state, "<script>", self.home)

    def test_the_slot_is_reported_before_the_media(self):
        # Both wrong on one statement: the author reads the slot
        # first, so the slot error is the one raised.
        self._write_state()
        script = parse_script(
            _HEAD + "machine stopped\ninsert cdrom0 @nonesuch\n")
        with self.assertRaises(ScriptPreflightError) as caught:
            execute_script(script, machine_id=self.machine_id,
                           context=self.home)
        self.assertIn("declares no drive cdrom0", str(caught.exception))

    def test_preflight_descends_into_handler_bodies(self):
        self._write_state()
        script = parse_script(
            _HEAD + "entry fork\ndeadline 1h\nphase fork {\n"
            '    wait {\n        on "a" {\n            eject floppy1\n'
            "            finish\n        }\n"
            '        on "b" {\n            finish\n        }\n'
            "    }\n}\n")
        with self.assertRaises(ScriptPreflightError) as caught:
            execute_script(script, machine_id=self.machine_id,
                           context=self.home)
        self.assertIn("declares no drive floppy1", str(caught.exception))

    def test_set_boot_keys_are_preflighted(self):
        self._write_state()
        script = parse_script(
            _HEAD + "machine stopped\nset-boot cdrom0 hdd0\n")
        with self.assertRaises(ScriptPreflightError) as caught:
            execute_script(script, machine_id=self.machine_id,
                           context=self.home)
        self.assertIn("declares no drive cdrom0", str(caught.exception))

    def test_insert_rejects_a_hard_disk_slot(self):
        self._write_state()
        script = parse_script(
            _HEAD + "machine stopped\ninsert hdd0 @some-image\n")
        with self.assertRaises(ScriptPreflightError) as caught:
            execute_script(script, machine_id=self.machine_id,
                           context=self.home)
        self.assertIn("not a removable drive slot", str(caught.exception))

    def test_a_stopped_script_rejects_a_running_machine(self):
        self._write_state(phase="running")
        script = parse_script(
            _HEAD + "machine stopped\nstart\n")
        with self.assertRaises(ScriptRuntimeError) as caught:
            execute_script(script, machine_id=self.machine_id,
                           context=self.home)
        self.assertIn("expects a stopped machine", str(caught.exception))

    def test_a_stopped_script_starts_the_machine_itself(self):
        self._write_media("freedos-livecd")
        self._write_state(drives={
            "cdrom0": {"medium": "cdrom", "slot": 0, "media": None,
                       "path": None},
        })
        script = parse_script(
            _HEAD + "machine stopped\ninsert cdrom0 @freedos-livecd\n")
        with mock.patch(
                "reliquary.script_runner._machines") as machines, \
                contextlib.redirect_stdout(io.StringIO()):
            machines.load_machine_state.return_value = {
                "id": self.machine_id, "phase": "ready",
                "drives": {"cdrom0": {"medium": "cdrom", "slot": 0}},
            }
            execute_script(script, machine_id=self.machine_id,
                           context=self.home)
            machines.start_machine.assert_not_called()
            machines.insert_media.assert_called_once()


class _AskableEngine:
    """The two members ``_cancel_on_interrupt`` uses."""

    def __init__(self):
        self.cancels = 0

    @property
    def cancelled(self):
        return self.cancels > 0

    def cancel(self):
        self.cancels += 1


class InterruptEscalationTests(unittest.TestCase):
    """Ctrl-C asks once, then insists.

    The graceful stop is a promise, not a trap: a stop that will not
    land must still have a way out that is not killing the terminal.
    """

    def test_the_first_interrupt_requests_a_graceful_stop(self):
        engine = _AskableEngine()
        with _cancel_on_interrupt(engine):
            signal.getsignal(signal.SIGINT)(signal.SIGINT, None)
        self.assertEqual(engine.cancels, 1)

    def test_a_second_interrupt_raises_immediately(self):
        engine = _AskableEngine()
        with _cancel_on_interrupt(engine):
            handler = signal.getsignal(signal.SIGINT)
            handler(signal.SIGINT, None)
            with self.assertRaises(KeyboardInterrupt):
                handler(signal.SIGINT, None)
        # The second press interrupts rather than asking again.
        self.assertEqual(engine.cancels, 1)

    def test_the_previous_handler_is_restored(self):
        before = signal.getsignal(signal.SIGINT)
        with _cancel_on_interrupt(_AskableEngine()):
            pass
        self.assertIs(signal.getsignal(signal.SIGINT), before)


if __name__ == "__main__":
    unittest.main()
