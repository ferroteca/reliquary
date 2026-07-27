# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Tests for labeled script wiring: the returned output and the CLI."""

import contextlib
import io
import json
import os
import tempfile
import unittest
from unittest import mock

from reliquary import cli
from reliquary.errors import PreflightError, StaticError
from reliquary.events import RUN_END, RUN_START
from reliquary.script_parser import parse_script
from reliquary.script_runner import (
    ScriptRun, _ScriptEngine,
    _existing_machine, _resolve_script_stem, run_script,
)


class ResolveScriptStemTests(unittest.TestCase):
    def test_label_maps_through_scripts_map(self):
        self.assertEqual(
            _resolve_script_stem(
                "install",
                {"install": "freedos-install"}),
            "freedos-install")

    def test_unknown_label_is_bare_stem(self):
        self.assertEqual(
            _resolve_script_stem("my-script", {"install": "x"}),
            "my-script")

    def test_rejects_path_components(self):
        with self.assertRaises(StaticError) as caught:
            _resolve_script_stem("../escape", {})
        self.assertIn("bare name", str(caught.exception))

    def test_rejects_rlqs_suffix(self):
        with self.assertRaises(StaticError) as caught:
            _resolve_script_stem("install.rlqs", {})
        self.assertIn(".rlqs", str(caught.exception))


class ResolveOrCreateMachineTests(unittest.TestCase):
    def setUp(self):
        self.workdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.workdir.cleanup)
        self.home = self.workdir.name
        blueprints = os.path.join(self.home, "blueprints")
        os.makedirs(blueprints)
        with open(os.path.join(blueprints, "plain.rlqb"), "w",
                  encoding="utf-8") as handle:
            json.dump([
                {"type": "machine", "name": "plain", "platform": "dos",
                 "drives": {"hdd0": "blank-20m"},
                 "scripts": {"install": "install-script"}},
                {"type": "media", "name": "blank-20m",
                 "materialize": "new", "size": "20M"},
            ], handle)

    def test_no_machine_yet_is_reported_as_none(self):
        # _existing_machine never creates; None means "would create".
        self.assertIsNone(
            _existing_machine(blueprint="plain", context=self.home))

    def test_reuses_sole_machine(self):
        from reliquary.machines import create_machine
        with mock.patch("reliquary.machines.create_hdd_image"):
            first = create_machine("plain", context=self.home)
        second = _existing_machine(blueprint="plain", context=self.home)
        self.assertEqual(first, second)

    def test_machine_id_resolves_to_itself(self):
        from reliquary.machines import create_machine
        with mock.patch("reliquary.machines.create_hdd_image"):
            machine_id = create_machine("plain", context=self.home)
        resolved = _existing_machine(machine=machine_id, context=self.home)
        self.assertEqual(resolved, machine_id)

    def test_a_specific_machine_id_selects_among_several(self):
        from reliquary.machines import create_machine
        with mock.patch("reliquary.machines.create_hdd_image"):
            first = create_machine("plain", context=self.home)
            second = create_machine("plain", context=self.home)
        resolved = _existing_machine(machine="plain-1", context=self.home)
        self.assertEqual(first, "plain-0")
        self.assertEqual(resolved, second)
        self.assertEqual(resolved, "plain-1")


class BindingBeforeCreationTests(unittest.TestCase):
    """A noninteractive unbound property fails before any machine."""

    def setUp(self):
        self.workdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.workdir.cleanup)
        self.home = self.workdir.name
        os.makedirs(os.path.join(self.home, "blueprints"))
        os.makedirs(os.path.join(self.home, "scripts"))
        with open(os.path.join(self.home, "blueprints", "plain.rlqb"),
                  "w", encoding="utf-8") as handle:
            json.dump(
                {"type": "machine", "name": "plain", "platform": "dos"},
                handle)
        with open(os.path.join(self.home, "scripts", "needs.rlqs"),
                  "w", encoding="utf-8") as handle:
            handle.write('property owner\nenter "${owner}"\n')

    def test_unbound_property_fails_without_creating_a_machine(self):
        from reliquary.binding import PropertyBindingError
        with mock.patch(
                "reliquary.script_runner.console_asker",
                return_value=None), \
                mock.patch(
                    "reliquary.machines.create_machine") as create:
            with self.assertRaises(PropertyBindingError):
                run_script("needs", blueprint="plain", context=self.home)
        create.assert_not_called()
        machines_root = os.path.join(self.home, "cache", "machines")
        created = (os.path.isdir(machines_root)
                   and [name for name in os.listdir(machines_root)
                        if not name.startswith(".")])
        self.assertFalse(created)


class ReturnedOutputTests(unittest.TestCase):
    """The run returns its output and writes nothing (D36)."""

    def _run_engine(self):
        workdir = tempfile.TemporaryDirectory()
        self.addCleanup(workdir.cleanup)
        home = workdir.name
        machine_id = "abcd" * 8
        machine_home = os.path.join(
            home, "cache", "machines", machine_id)
        os.makedirs(machine_home)
        script = parse_script('platform dos\nentry only\n'
                              'phase only {\n    wait "Hello"\n'
                              "    finish\n}\n")
        engine = _ScriptEngine(
            script, machine_id, home, machine_home,
            script_path="/tmp/demo.rlqs")
        engine._port = 5555

        class _Console:
            def screen_text(self):
                return ["Hello"]

        @contextlib.contextmanager
        def console():
            yield _Console()

        engine._console = console

        with mock.patch(
                "reliquary.script_runner._machines") as machines:
            machines.load_machine_state.return_value = {
                "phase": "running"}
            machines.machine_dir_path.return_value = machine_home
            with mock.patch(
                    "reliquary.lifecycle.read_vm_state",
                    return_value={"port": 5555}):
                engine.run()
        return engine, home, machine_home

    def test_the_stream_carries_the_run_and_ends_with_its_outcome(self):
        engine, _home, _machine_home = self._run_engine()
        events = engine.events.events
        self.assertEqual(events[0]["kind"], RUN_START)
        self.assertEqual(events[0]["script"], "/tmp/demo.rlqs")
        self.assertEqual(events[-1]["kind"], RUN_END)
        self.assertEqual(events[-1]["outcome"], "ok")
        self.assertEqual(events[-1]["exit-code"], 0)
        # Sequence numbers are dense and ordered.
        self.assertEqual([event["seq"] for event in events],
                         list(range(1, len(events) + 1)))
        kinds = [event["kind"] for event in events]
        self.assertIn("observation.arm", kinds)
        self.assertIn("observation.match", kinds)

    def test_the_run_writes_nothing_to_disk(self):
        _engine, _home, machine_home = self._run_engine()
        self.assertEqual(sorted(os.listdir(machine_home)), [])


class RunScriptWiringTests(unittest.TestCase):
    def setUp(self):
        self.workdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.workdir.cleanup)
        self.home = self.workdir.name
        blueprints = os.path.join(self.home, "blueprints")
        scripts = os.path.join(self.home, "scripts")
        os.makedirs(blueprints)
        os.makedirs(scripts)
        with open(os.path.join(blueprints, "plain.rlqb"), "w",
                  encoding="utf-8") as handle:
            json.dump([
                {"type": "machine", "name": "plain", "platform": "dos",
                 "drives": {"hdd0": "blank-20m"},
                 "scripts": {"install": "install-script"}},
                {"type": "media", "name": "blank-20m",
                 "materialize": "new", "size": "20M"},
            ], handle)
        with open(os.path.join(scripts, "install-script.rlqs"), "w",
                  encoding="utf-8", newline="\n") as handle:
            handle.write("platform dos\n")
            handle.write('wait "ready" timeout=1s\n')

    def test_run_script_resolves_label_and_returns_its_output(self):
        with mock.patch("reliquary.machines.create_hdd_image"), \
                mock.patch(
                    "reliquary.script_runner.execute_script",
                    return_value=("-", "ready")) as execute:
            result = run_script(
                "install", blueprint="plain", context=self.home,
                progress="plain")
        self.assertIsInstance(result, ScriptRun)
        self.assertTrue(result.created_machine)
        self.assertTrue(result.script_path.endswith(
            "install-script.rlqs"))
        self.assertEqual(result.final_phase, "-")
        self.assertEqual(result.machine_phase, "ready")
        self.assertIsInstance(result.events, tuple)
        execute.assert_called_once()
        kwargs = execute.call_args.kwargs
        self.assertEqual(kwargs["machine_id"], result.machine_id)
        self.assertEqual(kwargs["script_path"], result.script_path)
        self.assertEqual(kwargs["context"], self.home)
        self.assertFalse(kwargs["display"])
        self.assertIsNotNone(kwargs["events"])

    def test_run_script_creates_no_run_directory(self):
        with mock.patch("reliquary.machines.create_hdd_image"), \
                mock.patch(
                    "reliquary.script_runner.execute_script",
                    return_value=("-", "ready")):
            result = run_script(
                "install", blueprint="plain", context=self.home,
                progress="plain")
        machine_dir = os.path.join(
            self.home, "cache", "machines", result.machine_id)
        self.assertFalse(os.path.exists(os.path.join(machine_dir, "runs")))

    def test_run_script_bare_stem_when_label_absent(self):
        scripts = os.path.join(self.home, "scripts")
        with open(os.path.join(scripts, "extra.rlqs"), "w",
                  encoding="utf-8", newline="\n") as handle:
            handle.write("platform dos\n")
        with mock.patch("reliquary.machines.create_hdd_image"), \
                mock.patch(
                    "reliquary.script_runner.execute_script",
                    return_value=("-", "ready")):
            result = run_script(
                "extra", blueprint="plain", context=self.home)
        self.assertTrue(result.script_path.endswith("extra.rlqs"))

    def test_run_script_seeds_missing_script(self):
        os.remove(os.path.join(
            self.home, "scripts", "install-script.rlqs"))

        def fake_seed(stem, context=None):
            path = os.path.join(self.home, "scripts", f"{stem}.rlqs")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("platform dos\n")
            return True

        with mock.patch("reliquary.machines.create_hdd_image"), \
                mock.patch(
                    "reliquary.script_runner.seed_script",
                    side_effect=fake_seed) as seed, \
                mock.patch(
                    "reliquary.script_runner.execute_script",
                    return_value=("-", "ready")):
            result = run_script(
                "install", blueprint="plain", context=self.home)
        seed.assert_called_once_with("install-script", context=self.home)
        self.assertTrue(os.path.isfile(result.script_path))

    def test_run_script_missing_script_fails(self):
        os.remove(os.path.join(
            self.home, "scripts", "install-script.rlqs"))
        with mock.patch("reliquary.machines.create_hdd_image"), \
                mock.patch(
                    "reliquary.script_runner.seed_script",
                    return_value=False):
            with self.assertRaises(PreflightError) as caught:
                run_script(
                    "install", blueprint="plain", context=self.home)
        self.assertIn("install-script.rlqs", str(caught.exception))

    def test_run_script_forwards_display(self):
        with mock.patch("reliquary.machines.create_hdd_image"), \
                mock.patch(
                    "reliquary.script_runner.execute_script",
                    return_value=("-", "ready")) as execute:
            run_script(
                "install", blueprint="plain", context=self.home,
                display=True)
        self.assertTrue(execute.call_args.kwargs["display"])

    def test_cli_run_script_invokes_runtime_end_to_end(self):
        """rlq run-script install --blueprint … wires through."""
        stdout = io.StringIO()
        with mock.patch("reliquary.machines.create_hdd_image"), \
                mock.patch(
                    "reliquary.cli.run_script",
                    return_value=ScriptRun(
                        machine_id="abcd" * 8,
                        script_path=os.path.join(
                            self.home, "scripts",
                            "install-script.rlqs"),
                        created_machine=True,
                    )) as run, \
                contextlib.redirect_stdout(stdout):
            result = cli.main([
                "--home", self.home,
                "--blueprint", "plain",
                "run-script", "install",
            ])
        self.assertEqual(result, 0)
        run.assert_called_once_with(
            "install",
            blueprint="plain",
            machine=None,
            display=False,
            properties=None,
            properties_file=None,
            progress="auto",
        )
        # A stream-bearing command's human modes leave stdout empty:
        # the outcome travels by exit code.
        self.assertEqual(stdout.getvalue(), "")

    def test_jsonl_puts_the_stream_on_stdout_and_nothing_else(self):
        def emit(script, **kwargs):
            stream = kwargs["events"]
            stream.emit("action.start", verb="enter", detail="'DIR'")
            stream.emit("run.end", outcome="ok",
                        **{"exit-code": 0, "final-phase": "-",
                           "machine-phase": "ready"})
            return "-", "ready"

        out, err = io.StringIO(), io.StringIO()
        with mock.patch("reliquary.machines.create_hdd_image"), \
                mock.patch("reliquary.script_runner.execute_script",
                           side_effect=emit), \
                contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err):
            code = cli.main([
                "--home", self.home, "--blueprint", "plain",
                "run-script", "install", "--progress", "jsonl",
            ])
        self.assertEqual(code, 0)
        lines = out.getvalue().splitlines()
        documents = [json.loads(line) for line in lines]
        self.assertEqual(documents[0]["kind"], "action.start")
        # The last line is the terminal event: the machine-readable
        # result, with no separate result mode.
        self.assertEqual(documents[-1]["kind"], RUN_END)
        self.assertEqual(documents[-1]["outcome"], "ok")

    def test_the_run_returns_the_stream_it_rendered(self):
        def emit(script, **kwargs):
            kwargs["events"].emit(RUN_START, script="demo.rlqs")
            return "-", "ready"

        with mock.patch("reliquary.machines.create_hdd_image"), \
                mock.patch("reliquary.script_runner.execute_script",
                           side_effect=emit), \
                contextlib.redirect_stderr(io.StringIO()):
            result = run_script(
                "install", blueprint="plain", context=self.home,
                progress="plain")
        self.assertEqual([event["kind"] for event in result.events],
                         [RUN_START])

    def test_cli_script_requires_selector(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            result = cli.main([
                "--home", self.home, "run-script", "install",
            ])
        self.assertEqual(result, 2)
        self.assertIn("--blueprint or --machine", stderr.getvalue())

    def test_cli_script_rejects_json(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            result = cli.main([
                "--home", self.home, "--blueprint", "plain",
                "run-script", "install", "--json",
            ])
        self.assertEqual(result, 2)
        self.assertIn("--progress jsonl", stderr.getvalue())

    def test_cli_script_forwards_display_and_progress(self):
        with mock.patch(
                "reliquary.cli.run_script",
                return_value=ScriptRun(
                    machine_id="abcd" * 8,
                    script_path="/tmp/x.rlqs",
                )) as run, \
                contextlib.redirect_stdout(io.StringIO()):
            result = cli.main([
                "--home", self.home,
                "--blueprint", "plain",
                "run-script", "install",
                "--display", "--progress", "jsonl",
            ])
        self.assertEqual(result, 0)
        self.assertTrue(run.call_args.kwargs["display"])
        self.assertEqual(run.call_args.kwargs["progress"], "jsonl")


if __name__ == "__main__":
    unittest.main()
