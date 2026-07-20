# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Tests for the milestone-one .rlqs script runtime."""

import json
import os
import tempfile
import unittest
from unittest import mock

from reliquary.script import parse_script
from reliquary.script_runner import (ScriptRuntimeError, execute_script,
                                     _parse_duration, _normalize_row,
                                     _resolve_key)


class TextNormalizationTests(unittest.TestCase):
    def test_collapses_multiple_spaces(self):
        self.assertEqual(
            _normalize_row("Hello   World"), "Hello World")

    def test_trims_trailing_spaces(self):
        self.assertEqual(
            _normalize_row("Hello   "), "Hello")

    def test_trims_leading_spaces(self):
        self.assertEqual(
            _normalize_row("  Hello"), "Hello")

    def test_preserves_case(self):
        self.assertEqual(
            _normalize_row("Welcome to FreeDOS"), "Welcome to FreeDOS")


class DurationParsingTests(unittest.TestCase):
    def test_seconds(self):
        self.assertEqual(_parse_duration("30s"), 30.0)

    def test_minutes_to_seconds(self):
        self.assertEqual(_parse_duration("2m"), 120.0)

    def test_milliseconds_to_seconds(self):
        self.assertEqual(_parse_duration("500ms"), 0.5)

    def test_hours_to_seconds(self):
        self.assertEqual(_parse_duration("1h"), 3600.0)


class KeyResolutionTests(unittest.TestCase):
    def test_special_keys(self):
        self.assertEqual(_resolve_key("enter"), "ret")
        self.assertEqual(_resolve_key("down"), "down")
        self.assertEqual(_resolve_key("escape"), "esc")

    def test_chord_keys(self):
        self.assertEqual(_resolve_key("ctrl+c"), ("ctrl", "c"))
        self.assertEqual(
            _resolve_key("shift+enter"), ("shift", "ret"))

    def test_unknown_key_passes_through(self):
        self.assertEqual(_resolve_key("oem_3"), "oem_3")


class _FakeQmp:
    def __init__(self, *args, **kwargs):
        self._screen_func = None
        self._keys_sent = []
        self._commands = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass

    def close(self):
        pass

    def screen_text(self):
        if self._screen_func is not None:
            return self._screen_func()
        return []

    def send_text(self, text, enter=True):
        self._commands.append(("send_text", text, enter))

    def send_keys(self, combos, delay=0.06):
        self._keys_sent.extend(combos)

    def cursor_menu_select(self, item, timeout=30, exclude=()):
        self._commands.append(
            ("cursor_menu_select", item, timeout, exclude))

    def screenshot(self, name="screen"):
        self._commands.append(("screenshot", name))


class _FakeConsole:
    def __init__(self, qmp):
        self._qmp = qmp

    def screen_text(self):
        return self._qmp.screen_text()

    def send_text(self, text, enter=True):
        self._qmp.send_text(text, enter)

    def send_keys(self, combos, delay=0.06):
        self._qmp.send_keys(combos, delay)

    def cursor_menu_select(self, item, timeout=30, exclude=()):
        self._qmp.cursor_menu_select(item, timeout, exclude)


class ScriptRuntimeTests(unittest.TestCase):
    def _make_engine(self, source, port=5555):
        script = parse_script(source)
        from reliquary.script_runner import _ScriptEngine
        engine = _ScriptEngine(
            script, "abcd" * 8, "/tmp/home",
            "/tmp/home/cache/machines/test")
        engine._port = port
        return engine

    def test_linear_wait_text_matches(self):
        engine = self._make_engine("""
            platform: dos
            wait "Hello World"
        """.strip())
        qmp = _FakeQmp()
        qmp._screen_func = lambda: ["", "", "Hello World"]
        with mock.patch.object(
                engine, "_session", return_value=qmp), \
                mock.patch.object(
                    engine, "_console", side_effect=_FakeConsole):
            engine._execute_block(engine._script.statements, {})

    def test_linear_wait_text_timeout_raises(self):
        engine = self._make_engine("""
            platform: dos
            timeout: 1s
            wait "Never Appears"
        """.strip())
        qmp = _FakeQmp()
        qmp._screen_func = lambda: ["nothing", "here"]
        with mock.patch.object(
                engine, "_session", return_value=qmp), \
                mock.patch.object(
                    engine, "_console", side_effect=_FakeConsole):
            with self.assertRaises(ScriptRuntimeError) as caught:
                engine._execute_block(engine._script.statements, {})
            self.assertIn("timed out", str(caught.exception))

    def test_linear_wait_stopped(self):
        engine = self._make_engine("""
            platform: dos
            wait stopped, timeout: 10s
        """.strip())
        count = [0]

        def _check():
            count[0] += 1
            return count[0] >= 2

        engine._is_stopped = _check
        engine._execute_block(engine._script.statements, {})

    def test_linear_wait_stopped_timeout(self):
        engine = self._make_engine("""
            platform: dos
            wait stopped, timeout: 1s
        """.strip())
        engine._is_stopped = lambda: False
        with self.assertRaises(ScriptRuntimeError) as caught:
            engine._execute_block(engine._script.statements, {})
        self.assertIn("timed out", str(caught.exception))

    def test_linear_enter_sends_text(self):
        engine = self._make_engine("""
            platform: dos
            enter "yes"
        """.strip())
        qmp = _FakeQmp()
        with mock.patch.object(
                engine, "_session", return_value=qmp), \
                mock.patch.object(
                    engine, "_console", side_effect=_FakeConsole):
            engine._execute_block(engine._script.statements, {})
        self.assertIn(("send_text", "yes", True), qmp._commands)

    def test_linear_press_sends_keys(self):
        engine = self._make_engine("""
            platform: dos
            press enter down down enter
        """.strip())
        qmp = _FakeQmp()
        with mock.patch.object(
                engine, "_session", return_value=qmp), \
                mock.patch.object(
                    engine, "_console", side_effect=_FakeConsole):
            engine._execute_block(engine._script.statements, {})
        self.assertEqual(len(qmp._keys_sent), 4)
        self.assertEqual(qmp._keys_sent[0], ["ret"])
        self.assertEqual(qmp._keys_sent[1], ["down"])

    def test_linear_select_calls_cursor_menu(self):
        engine = self._make_engine("""
            platform: dos
            select "Install to harddisk"
        """.strip())
        qmp = _FakeQmp()
        with mock.patch.object(
                engine, "_session", return_value=qmp), \
                mock.patch.object(
                    engine, "_console", side_effect=_FakeConsole):
            engine._execute_block(engine._script.statements, {})
        self.assertIn(
            ("cursor_menu_select", "Install to harddisk", 60, ()),
            qmp._commands)

    def test_linear_select_with_exclude(self):
        engine = self._make_engine("""
            platform: dos
            select "Plain DOS system", exclude: "with sources"
        """.strip())
        qmp = _FakeQmp()
        with mock.patch.object(
                engine, "_session", return_value=qmp), \
                mock.patch.object(
                    engine, "_console", side_effect=_FakeConsole):
            engine._execute_block(engine._script.statements, {})
        self.assertIn(
            ("cursor_menu_select", "Plain DOS system", 60,
             ("with sources",)),
            qmp._commands)

    def test_state_machine_transitions(self):
        engine = self._make_engine("""
            platform: dos
            initial: first
            state first {
                wait "Hello"
                -> second
            }
            state second {
                enter "goodbye"
                done
            }
        """.strip())
        self.assertEqual(engine._current_state, "first")
        qmp = _FakeQmp()
        qmp._screen_func = lambda: ["Hello"]

        with mock.patch.object(
                engine, "_session", return_value=qmp), \
                mock.patch.object(
                    engine, "_console", side_effect=_FakeConsole):
            engine._execute_block(
                engine._script.states["first"].statements, {})
        self.assertEqual(engine._current_state, "second")

    def test_state_machine_executes_to_completion(self):
        engine = self._make_engine("""
            platform: dos
            initial: ready
            state ready {
                wait "Ready"
                -> finish
            }
            state finish {
                enter "completed"
                done
            }
        """.strip())
        qmp = _FakeQmp()
        qmp._screen_func = lambda: ["Ready"]

        with mock.patch.object(
                engine, "_session", return_value=qmp), \
                mock.patch.object(
                    engine, "_console", side_effect=_FakeConsole):
            engine._current_state = "ready"
            engine._execute_block(
                engine._script.states["ready"].statements, {})
            self.assertEqual(engine._current_state, "finish")
            engine._execute_block(
                engine._script.states["finish"].statements, {})
            self.assertIn(("send_text", "completed", True),
                          qmp._commands)

    def test_expect_branching_first_match_wins(self):
        engine = self._make_engine("""
            platform: dos
            initial: test
            state test {
                press enter
                expect {
                    "Drive C: does not appear to be partitioned.": {
                        select "Yes"
                        -> partitioning
                    }
                    "Drive C: does not appear to be formatted.": {
                        select "No - return to DOS"
                        -> formatting
                    }
                }
            }
            state partitioning {
                enter "partitioning"
                done
            }
            state formatting {
                enter "formatting"
                done
            }
        """.strip())
        qmp = _FakeQmp()
        screen_index = [0]
        screens = [
            ["nothing yet"],
            ["Drive C: does not appear to be partitioned."],
        ]

        def screen_func():
            if screen_index[0] < len(screens):
                result = screens[screen_index[0]]
                screen_index[0] += 1
                return result
            return ["Drive C: does not appear to be partitioned."]

        qmp._screen_func = screen_func

        with mock.patch.object(
                engine, "_session", return_value=qmp), \
                mock.patch.object(
                    engine, "_console", side_effect=_FakeConsole):
            result = engine._do_expect(
                engine._script.states["test"].statements[1], {})
        self.assertEqual(result, "partitioning")
        self.assertIn(
            ("cursor_menu_select", "Yes", 60, ()),
            qmp._commands)

    def test_expect_second_branch_matches(self):
        engine = self._make_engine("""
            platform: dos
            initial: test
            state test {
                expect {
                    "partitioned": {
                        select "Yes"
                        -> done_state
                    }
                    "formatted": {
                        select "No"
                        -> done_state
                    }
                }
            }
            state done_state {
                done
            }
        """.strip())
        qmp = _FakeQmp()
        qmp._screen_func = lambda: ["Drive is formatted"]

        with mock.patch.object(
                engine, "_session", return_value=qmp), \
                mock.patch.object(
                    engine, "_console", side_effect=_FakeConsole):
            result = engine._do_expect(
                engine._script.states["test"].statements[0], {})
        self.assertEqual(result, "done_state")
        self.assertIn(
            ("cursor_menu_select", "No", 60, ()),
            qmp._commands)

    def test_expect_timeout_when_nothing_matches(self):
        engine = self._make_engine("""
            platform: dos
            initial: test
            timeout: 1s
            state test {
                expect {
                    "partitioned": {
                        done
                    }
                }
            }
        """.strip())
        qmp = _FakeQmp()
        qmp._screen_func = lambda: ["something else entirely"]

        with mock.patch.object(
                engine, "_session", return_value=qmp), \
                mock.patch.object(
                    engine, "_console", side_effect=_FakeConsole):
            with self.assertRaises(ScriptRuntimeError) as caught:
                engine._do_expect(
                    engine._script.states["test"].statements[0], {})
            self.assertIn("timed out", str(caught.exception))

    def test_wait_regex_matches_normalized_row(self):
        engine = self._make_engine("""
            platform: dos
            initial: test
            state test {
                wait regex "installed [0-9]+ packages"
                done
            }
        """.strip())
        qmp = _FakeQmp()
        qmp._screen_func = lambda: [
            "installed 42 packages", ""]

        with mock.patch.object(
                engine, "_session", return_value=qmp), \
                mock.patch.object(
                    engine, "_console", side_effect=_FakeConsole):
            engine._execute_block(
                engine._script.states["test"].statements, {})

    def test_screenshot_with_automatic_name(self):
        engine = self._make_engine("""
            platform: dos
            screenshot
        """.strip())
        fake_machine = mock.Mock()
        fake_machine.screenshot = mock.Mock()

        with mock.patch.object(
                engine, "_machine",
                return_value=fake_machine):
            engine._execute_block(engine._script.statements, {})
        fake_machine.screenshot.assert_called_once_with("step-1")

    def test_screenshot_with_named_argument(self):
        engine = self._make_engine("""
            platform: dos
            screenshot installed
        """.strip())
        fake_machine = mock.Mock()
        fake_machine.screenshot = mock.Mock()

        with mock.patch.object(
                engine, "_machine",
                return_value=fake_machine):
            engine._execute_block(engine._script.statements, {})
        fake_machine.screenshot.assert_called_once_with("installed")

    def test_type_with_key_tokens(self):
        engine = self._make_engine("""
            platform: dos
            type "hello<tab>world<enter>"
        """.strip())
        qmp = _FakeQmp()

        with mock.patch.object(
                engine, "_session", return_value=qmp), \
                mock.patch.object(
                    engine, "_console", side_effect=_FakeConsole):
            engine._execute_block(engine._script.statements, {})

        keys_sent = [k for combo in qmp._keys_sent for k in combo]
        self.assertIn("ret", keys_sent)
        self.assertIn("tab", keys_sent)

    def test_spike_9_fixture_linear_statement_count(self):
        source = """
            platform: dos
            timeout: 2s
            wait "Welcome to FreeDOS 1.4 (LiveCD)"
            select "Install to harddisk"
            wait "What is your preferred language"
            select "English (United States)"
            wait "Welcome to the FreeDOS 1.4 installation program"
            press enter
        """.strip()
        script = parse_script(source)
        self.assertEqual(len(script.statements), 6)

    def test_scriptruntimeerror_includes_statement_line(self):
        error = ScriptRuntimeError(
            "test failure",
            statement=parse_script(
                'platform: dos\nwait "x"\n').statements[0])
        message = str(error)
        self.assertIn("line 2", message)
        self.assertIn("test failure", message)

    def test_do_start_starts_the_machine(self):
        engine = self._make_engine("""
            platform: dos
            initial: test
            state test {
                start
                done
            }
        """.strip())
        with mock.patch(
                "reliquary.script_runner._machines") as mock_machines:
            mock_machines.start.return_value = 9999
            engine._do_start()
            mock_machines.start.assert_called_once_with(
                engine._machine_id, display=False, home=engine._home)
            self.assertEqual(engine._port, 9999)

    def test_do_stop_stops_the_machine(self):
        engine = self._make_engine("""
            platform: dos
            initial: test
            state test {
                stop
                done
            }
        """.strip())
        with mock.patch(
                "reliquary.script_runner._machines") as mock_machines:
            engine._do_stop()
            mock_machines.stop.assert_called_once_with(
                engine._machine_id, home=engine._home)
        self.assertIsNone(engine._port)

    def test_do_insert_persists_media_into_machine_state(self):
        engine = self._make_engine("""
            platform: dos
            insert cdrom0 freedos-1.4-livecd
        """.strip())
        with mock.patch(
                "reliquary.script_runner._machines") as mock_machines:
            engine._execute_block(engine._script.statements, {})
            mock_machines.insert_media.assert_called_once_with(
                engine._machine_id, "cdrom0", "freedos-1.4-livecd",
                home=engine._home)

    def test_do_eject_empties_the_slot(self):
        engine = self._make_engine("""
            platform: dos
            eject cdrom0
        """.strip())
        with mock.patch(
                "reliquary.script_runner._machines") as mock_machines:
            engine._execute_block(engine._script.statements, {})
            mock_machines.eject_media.assert_called_once_with(
                engine._machine_id, "cdrom0", home=engine._home)

    def test_do_boot_sets_boot_order(self):
        engine = self._make_engine("""
            platform: dos
            boot cdrom0 hdd0
        """.strip())
        with mock.patch(
                "reliquary.script_runner._machines") as mock_machines:
            engine._execute_block(engine._script.statements, {})
            mock_machines.set_boot_order.assert_called_once_with(
                engine._machine_id, ("cdrom0", "hdd0"),
                home=engine._home)

    def test_insert_failure_reports_the_statement(self):
        engine = self._make_engine("""
            platform: dos
            insert cdrom0 freedos-1.4-livecd
        """.strip())
        with mock.patch(
                "reliquary.script_runner._machines") as mock_machines:
            mock_machines.insert_media.side_effect = ValueError(
                "machine abcd declares no drive cdrom0")
            with self.assertRaises(ScriptRuntimeError) as caught:
                engine._execute_block(engine._script.statements, {})
        self.assertIn("declares no drive", str(caught.exception))
        self.assertIn("line 2", str(caught.exception))

    def test_session_without_running_machine_is_a_named_error(self):
        engine = self._make_engine("""
            platform: dos
            machine: stopped
            enter "too early"
        """.strip(), port=None)
        with self.assertRaises(ScriptRuntimeError) as caught:
            engine._execute_block(engine._script.statements, {})
        self.assertIn("not running", str(caught.exception))

    def test_wait_stopped_reconciles_machine_phase(self):
        engine = self._make_engine("""
            platform: dos
            wait stopped, timeout: 10s
        """.strip())
        engine._port = 5555
        with mock.patch(
                "reliquary.script_runner._machines") as mock_machines, \
                mock.patch.object(engine, "_is_stopped",
                                  return_value=True):
            engine._execute_block(engine._script.statements, {})
            mock_machines.mark_stopped.assert_called_once_with(
                engine._machine_id, home=engine._home)
        self.assertIsNone(engine._port)

    def test_enter_verb_in_state_machine(self):
        engine = self._make_engine("""
            platform: dos
            initial: test
            state test {
                enter "fdapm poweroff"
                wait stopped, timeout: 1s
                done
            }
        """.strip())
        qmp = _FakeQmp()

        with mock.patch.object(
                engine, "_session", return_value=qmp), \
                mock.patch.object(
                    engine, "_console", side_effect=_FakeConsole):
            engine._execute_block(
                engine._script.states["test"].statements[:-1], {})
        self.assertIn(
            ("send_text", "fdapm poweroff", True), qmp._commands)


class EmptyScriptTests(unittest.TestCase):
    def test_execute_empty_script_returns_silently(self):
        script = parse_script('platform: dos\n')
        result = execute_script(
            script, machine_id="abcd" * 8, home="/tmp/home")
        self.assertIsNone(result)


class ExecutePreflightTests(unittest.TestCase):
    """Static preflight and machine-header checks before guest input."""

    def setUp(self):
        self.workdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.workdir.cleanup)
        self.home = self.workdir.name
        self.machine_id = "abcd" * 8

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

    def test_insert_to_undeclared_slot_fails_before_execution(self):
        """A slot the machine does not declare fails static preflight."""
        self._write_state()
        script = parse_script(
            'platform: dos\nmachine: stopped\n'
            'insert cdrom0 freedos-1.4-livecd\nstart\nwait "x"\n')
        with self.assertRaises(ScriptRuntimeError) as caught:
            execute_script(script, machine_id=self.machine_id,
                           home=self.home)
        self.assertIn("declares no drive cdrom0", str(caught.exception))
        self.assertIn("line 3", str(caught.exception))

    def test_eject_inside_expect_branch_is_preflighted(self):
        """Preflight descends into expect branches."""
        self._write_state()
        script = parse_script(
            'platform: dos\ninitial: fork\n'
            'state fork {\n'
            'expect {\n"a": {\neject floppy1\ndone\n}\n}\n'
            '}\n')
        with self.assertRaises(ScriptRuntimeError) as caught:
            execute_script(script, machine_id=self.machine_id,
                           home=self.home)
        self.assertIn("declares no drive floppy1", str(caught.exception))

    def test_boot_undeclared_drive_fails_before_execution(self):
        """boot keys are preflighted against the machine's drives."""
        self._write_state()
        script = parse_script(
            'platform: dos\nmachine: stopped\n'
            'boot cdrom0 hdd0\n')
        with self.assertRaises(ScriptRuntimeError) as caught:
            execute_script(script, machine_id=self.machine_id,
                           home=self.home)
        self.assertIn("declares no drive cdrom0", str(caught.exception))

    def test_stopped_script_rejects_a_running_machine(self):
        """machine: stopped never implicitly powers a machine off."""
        self._write_state(phase="running")
        script = parse_script(
            'platform: dos\nmachine: stopped\nstart\nwait "x"\n')
        with self.assertRaises(ScriptRuntimeError) as caught:
            execute_script(script, machine_id=self.machine_id,
                           home=self.home)
        self.assertIn("expects a stopped machine", str(caught.exception))

    def test_stopped_script_does_not_auto_start(self):
        """The script itself starts the machine, not the runner."""
        self._write_state(drives={
            "cdrom0": {"medium": "cdrom", "slot": 0, "media": None,
                       "path": None},
        })
        script = parse_script(
            'platform: dos\nmachine: stopped\n'
            'insert cdrom0 freedos-1.4-livecd\n')
        with mock.patch(
                "reliquary.script_runner._machines") as mock_machines:
            mock_machines.load_machine_state.return_value = {
                "id": self.machine_id, "phase": "ready",
                "drives": {"cdrom0": {"medium": "cdrom", "slot": 0}},
            }
            execute_script(script, machine_id=self.machine_id,
                           home=self.home)
            mock_machines.start.assert_not_called()
            mock_machines.insert_media.assert_called_once()


if __name__ == "__main__":
    unittest.main()
