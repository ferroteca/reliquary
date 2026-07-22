# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Tests for the .rlqs runtime: dispatch, episodes, and clocks."""

import contextlib
import io
import json
import os
import tempfile
import unittest
from unittest import mock

from qemu.qmp import ConnectError

from reliquary.script_parser import parse_script
from reliquary.script_runner import (ScriptRuntimeError, _normalize_row,
                                     _resolve_key, _ScriptEngine,
                                     execute_script)
from reliquary.script_validation import PORTABLE_KEY_NAMES

# The reference script is a shipped builtin, resolved as package
# data so these tests run against an installed artifact too.
import reliquary
_REFERENCE = os.path.join(
    os.path.dirname(os.path.abspath(reliquary.__file__)),
    "codex", "scripts", "freedos-1.4-plain-install.rlqs")

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

    def __init__(self, screens=(), fail=False):
        self.screens = list(screens)
        self.fail = fail
        self.commands = []
        self.keys = []
        self.reads = 0

    def screen_text(self):
        self.reads += 1
        if self.fail:
            raise ConnectError("machine is gone", OSError("gone"))
        if not self.screens:
            return []
        if len(self.screens) > 1:
            return self.screens.pop(0)
        return self.screens[0]

    def send_text(self, text, enter=True):
        self.commands.append(("send_text", text, enter))

    def send_keys(self, combos, delay=0.06):
        self.keys.extend(combos)

    def cursor_menu_select(self, item, timeout=30, exclude=()):
        self.commands.append(("select", item, timeout, exclude))


class _RuntimeCase(unittest.TestCase):
    """Builds engines over a fake console and a controlled clock."""

    def engine(self, source, screens=(), port=5555, fail=False,
               run_dir=None):
        script = parse_script(_HEAD + source)
        clock = _Clock()
        engine = _ScriptEngine(
            script, "plain-0", "/tmp/home",
            "/tmp/home/cache/machines/plain-0", run_dir=run_dir,
            script_path="demo.rlqs", clock=clock, sleep=clock.sleep)
        engine._port = port
        self.console = _FakeConsole(screens, fail)
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


class HelperTests(unittest.TestCase):
    def test_a_row_normalizes_its_whitespace(self):
        self.assertEqual(_normalize_row("  Hello   World  "),
                         "Hello World")

    def test_the_portable_key_names_resolve(self):
        for name in PORTABLE_KEY_NAMES:
            with self.subTest(name=name):
                self.assertTrue(_resolve_key(name))
        self.assertEqual(_resolve_key("enter"), ["ret"])
        self.assertEqual(_resolve_key("pagedown"), ["pgdn"])
        self.assertEqual(_resolve_key("ctrl+alt+delete"),
                         ["ctrl", "alt", "delete"])

    def test_a_chord_admits_a_printable_member(self):
        self.assertEqual(_resolve_key("ctrl+c"), ["ctrl", "c"])

    def test_a_bare_character_is_not_a_key_name(self):
        with self.assertRaises(KeyError):
            _resolve_key("c")

    def test_an_unknown_name_is_not_passed_through(self):
        with self.assertRaises(KeyError):
            _resolve_key("oem_3")


class ObservationTests(_RuntimeCase):
    """Single-condition waits, over samples."""

    def test_a_screen_condition_matches_a_normalized_row(self):
        engine = self.engine('wait "Hello World"\n',
                             screens=[["", "  Hello   World  "]])
        self.run_linear(engine)
        self.assertEqual(self.console.reads, 1)

    def test_a_regex_condition_matches_a_row(self):
        engine = self.engine('wait /installed [0-9]+ packages/\n',
                             screens=[["installed 42 packages"]])
        self.run_linear(engine)

    def test_a_condition_is_matched_only_at_a_fresh_sample(self):
        engine = self.engine('wait "second"\n',
                             screens=[["first"], ["second"]])
        self.run_linear(engine)
        self.assertEqual(self.console.reads, 2)

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
        self.assertEqual(self.console.reads, 1)

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
        # One sample arms the episode; the hold is satisfied only
        # once its age reaches the duration.
        self.assertEqual(self.console.reads, 3)

    def test_an_interrupted_episode_restarts_the_hold(self):
        engine = self.engine(
            'wait "ready" stable=2s\n',
            screens=[["ready"], ["busy"], ["ready"], ["ready"]])
        self.run_linear(engine)
        self.assertEqual(self.console.reads, 4)

    def test_a_machine_condition_observes_the_backend(self):
        engine = self.engine("wait machine=stopped\n", fail=True)
        with mock.patch(
                "reliquary.script_runner._machines") as machines:
            self.run_linear(engine)
            machines.mark_stopped.assert_called_once_with(
                "plain-0", home="/tmp/home")
        self.assertIsNone(engine._port)

    def test_a_stopped_machine_satisfies_without_a_console(self):
        engine = self.engine("wait machine=stopped\n", port=None)
        self.run_linear(engine)
        self.assertEqual(self.console.reads, 0)

    def test_a_screen_observation_needs_a_running_machine(self):
        engine = self.engine('machine stopped\nwait "x"\n', port=None)
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
                "plain-0", "cdrom0", home="/tmp/home")
        self.assertEqual(self.console.keys, [])


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

    def test_an_unbound_property_reference_is_a_named_error(self):
        for source in ('enter "setup /owner=${owner}"\n',
                       'wait "welcome ${owner}"\n'):
            engine = self.engine("property owner\n" + source,
                                 screens=[["quiet"]])
            with self.assertRaises(ScriptRuntimeError, msg=source) as caught:
                self.run_linear(engine)
            self.assertIn("${owner} has no bound value",
                          str(caught.exception), msg=source)


class MachineOperationTests(_RuntimeCase):
    def test_insert_resolves_a_media_reference(self):
        engine = self.engine("insert cdrom0 @freedos-1.4-livecd\n")
        with mock.patch(
                "reliquary.script_runner._machines") as machines:
            self.run_linear(engine)
            machines.insert_media.assert_called_once_with(
                "plain-0", "cdrom0", "freedos-1.4-livecd",
                home="/tmp/home")

    def test_insert_from_a_property_is_not_bound_yet(self):
        engine = self.engine(
            "property media supplemental\n"
            "insert floppy1 $supplemental\n")
        with mock.patch("reliquary.script_runner._machines"):
            with self.assertRaises(ScriptRuntimeError) as caught:
                self.run_linear(engine)
        self.assertIn("has no bound value", str(caught.exception))

    def test_eject_empties_the_slot(self):
        engine = self.engine("eject cdrom0\n")
        with mock.patch(
                "reliquary.script_runner._machines") as machines:
            self.run_linear(engine)
            machines.eject_media.assert_called_once_with(
                "plain-0", "cdrom0", home="/tmp/home")

    def test_set_boot_replaces_the_boot_order(self):
        engine = self.engine("set-boot hdd0 cdrom0\n")
        with mock.patch(
                "reliquary.script_runner._machines") as machines:
            self.run_linear(engine)
            machines.set_boot_order.assert_called_once_with(
                "plain-0", ("hdd0", "cdrom0"), home="/tmp/home")

    def test_a_machine_change_failure_reports_its_line(self):
        engine = self.engine("insert cdrom0 @freedos-1.4-livecd\n")
        with mock.patch(
                "reliquary.script_runner._machines") as machines:
            machines.insert_media.side_effect = ValueError(
                "machine plain-0 declares no drive cdrom0")
            with self.assertRaises(ScriptRuntimeError) as caught:
                self.run_linear(engine)
        self.assertIn("declares no drive", str(caught.exception))
        self.assertIn("line 2", str(caught.exception))

    def test_start_and_stop_bind_and_clear_the_port(self):
        engine = self.engine("stop\nstart\n", port=5555)
        with mock.patch(
                "reliquary.script_runner._machines") as machines:
            machines.start_machine.return_value = 9999
            self.run_linear(engine)
            machines.stop_machine.assert_called_once_with(
                "plain-0", home="/tmp/home")
        self.assertEqual(engine._port, 9999)

    def test_screenshot_lands_in_the_run_directory(self):
        engine = self.engine("screenshot installed\n",
                             run_dir="/tmp/home/runs/r1")
        with mock.patch(
                "reliquary.script_runner.screenshot") as capture:
            self.run_linear(engine)
        capture.assert_called_once_with(
            "installed", 5555, "/tmp/home/cache/machines/plain-0",
            directory=os.path.join("/tmp/home/runs/r1", "screenshots"))

    def test_a_screenshot_defaults_to_its_step_number(self):
        engine = self.engine("screenshot\n")
        with mock.patch("reliquary.script_runner.Machine") as machine:
            self.run_linear(engine)
        machine.return_value.screenshot.assert_called_once_with("step-1")


class ExecutePreflightTests(unittest.TestCase):
    """Static preflight and machine-header checks before guest input."""

    def setUp(self):
        self.workdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.workdir.cleanup)
        self.home = self.workdir.name
        self.machine_id = "plain-0"

    def _write_state(self, phase="ready", drives=None):
        root = os.path.join(self.home, "cache", "machines",
                            self.machine_id)
        os.makedirs(root)
        state = {
            "id": self.machine_id,
            "phase": phase,
            "drives": drives if drives is not None else {
                "hdd0": {"medium": "hdd", "slot": 0, "size": "20M",
                         "path": "hdd0.qcow2"},
            },
        }
        with open(os.path.join(root, "reliquary-machine.json"), "w",
                  encoding="utf-8") as handle:
            json.dump(state, handle)

    def test_an_empty_script_reports_the_machine_phase(self):
        self._write_state()
        script = parse_script(_HEAD)
        self.assertEqual(
            execute_script(script, machine_id=self.machine_id,
                           home=self.home),
            ("-", "ready"))

    def test_insert_to_an_undeclared_slot_fails_before_execution(self):
        self._write_state()
        script = parse_script(
            _HEAD + "machine stopped\n"
            "insert cdrom0 @freedos-1.4-livecd\nstart\n")
        with self.assertRaises(ScriptRuntimeError) as caught:
            execute_script(script, machine_id=self.machine_id,
                           home=self.home)
        self.assertIn("declares no drive cdrom0", str(caught.exception))
        self.assertIn("line 3", str(caught.exception))

    def test_preflight_descends_into_handler_bodies(self):
        self._write_state()
        script = parse_script(
            _HEAD + "entry fork\ndeadline 1h\nphase fork {\n"
            '    wait {\n        on "a" {\n            eject floppy1\n'
            "            finish\n        }\n"
            '        on "b" {\n            finish\n        }\n'
            "    }\n}\n")
        with self.assertRaises(ScriptRuntimeError) as caught:
            execute_script(script, machine_id=self.machine_id,
                           home=self.home)
        self.assertIn("declares no drive floppy1", str(caught.exception))

    def test_set_boot_keys_are_preflighted(self):
        self._write_state()
        script = parse_script(
            _HEAD + "machine stopped\nset-boot cdrom0 hdd0\n")
        with self.assertRaises(ScriptRuntimeError) as caught:
            execute_script(script, machine_id=self.machine_id,
                           home=self.home)
        self.assertIn("declares no drive cdrom0", str(caught.exception))

    def test_insert_rejects_a_hard_disk_slot(self):
        self._write_state()
        script = parse_script(
            _HEAD + "machine stopped\ninsert hdd0 @some-image\n")
        with self.assertRaises(ScriptRuntimeError) as caught:
            execute_script(script, machine_id=self.machine_id,
                           home=self.home)
        self.assertIn("not a removable drive slot", str(caught.exception))

    def test_a_stopped_script_rejects_a_running_machine(self):
        self._write_state(phase="running")
        script = parse_script(
            _HEAD + "machine stopped\nstart\n")
        with self.assertRaises(ScriptRuntimeError) as caught:
            execute_script(script, machine_id=self.machine_id,
                           home=self.home)
        self.assertIn("expects a stopped machine", str(caught.exception))

    def test_a_stopped_script_starts_the_machine_itself(self):
        self._write_state(drives={
            "cdrom0": {"medium": "cdrom", "slot": 0, "media": None,
                       "path": None},
        })
        script = parse_script(
            _HEAD + "machine stopped\ninsert cdrom0 @freedos-1.4-livecd\n")
        with mock.patch(
                "reliquary.script_runner._machines") as machines, \
                contextlib.redirect_stdout(io.StringIO()):
            machines.load_machine_state.return_value = {
                "id": self.machine_id, "phase": "ready",
                "drives": {"cdrom0": {"medium": "cdrom", "slot": 0}},
            }
            execute_script(script, machine_id=self.machine_id,
                           home=self.home)
            machines.start_machine.assert_not_called()
            machines.insert_media.assert_called_once()


if __name__ == "__main__":
    unittest.main()
