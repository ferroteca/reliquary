# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Tests for labeled script wiring (milestone-1 spike 10)."""

import contextlib
import io
import json
import os
import tempfile
import unittest
from unittest import mock

from reliquary import cli
from reliquary.script import parse_script
from reliquary.script_runner import (
    ScriptRun, _ScriptEngine, _create_run_dir,
    _resolve_or_create_machine, _resolve_script_stem, run_script,
)


class ResolveScriptStemTests(unittest.TestCase):
    def test_label_maps_through_scripts_map(self):
        self.assertEqual(
            _resolve_script_stem(
                "install",
                {"install": "freedos-1.4-plain-install"}),
            "freedos-1.4-plain-install")

    def test_unknown_label_is_bare_stem(self):
        self.assertEqual(
            _resolve_script_stem("my-script", {"install": "x"}),
            "my-script")

    def test_rejects_path_components(self):
        with self.assertRaises(ValueError) as caught:
            _resolve_script_stem("../escape", {})
        self.assertIn("bare name", str(caught.exception))

    def test_rejects_rlqs_suffix(self):
        with self.assertRaises(ValueError) as caught:
            _resolve_script_stem("install.rlqs", {})
        self.assertIn(".rlqs", str(caught.exception))


class ResolveOrCreateMachineTests(unittest.TestCase):
    def setUp(self):
        self.workdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.workdir.cleanup)
        self.home = self.workdir.name
        blueprints = os.path.join(self.home, "blueprints")
        os.makedirs(blueprints)
        with open(os.path.join(blueprints, "plain.json"), "w",
                  encoding="utf-8") as handle:
            json.dump({
                "platform": "dos",
                "drives": {"hdd": {"size": "20M"}},
                "scripts": {"install": "plain-install"},
            }, handle)

    def test_creates_when_blueprint_has_no_machine(self):
        with mock.patch("reliquary.machines.create_hdd_image"):
            machine_id, created = _resolve_or_create_machine(
                blueprint="plain", home=self.home)
        self.assertTrue(created)
        self.assertRegex(machine_id, r"^[0-9a-f]{32}$")

    def test_reuses_sole_machine(self):
        with mock.patch("reliquary.machines.create_hdd_image"):
            first, created = _resolve_or_create_machine(
                blueprint="plain", home=self.home)
            self.assertTrue(created)
            second, created = _resolve_or_create_machine(
                blueprint="plain", home=self.home)
        self.assertFalse(created)
        self.assertEqual(first, second)

    def test_machine_prefix_resolves(self):
        with mock.patch("reliquary.machines.create_hdd_image"):
            machine_id, _ = _resolve_or_create_machine(
                blueprint="plain", home=self.home)
        resolved, created = _resolve_or_create_machine(
            machine=machine_id[:4], home=self.home)
        self.assertFalse(created)
        self.assertEqual(resolved, machine_id)


class CreateRunDirTests(unittest.TestCase):
    def setUp(self):
        self.workdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.workdir.cleanup)
        self.home = self.workdir.name
        self.machine_id = "abcd" * 8
        root = os.path.join(
            self.home, "cache", "machines", self.machine_id)
        os.makedirs(root)

    def test_creates_transcript_layout(self):
        run_dir = _create_run_dir(self.machine_id, home=self.home)
        self.assertTrue(os.path.isdir(run_dir))
        self.assertTrue(
            os.path.isdir(os.path.join(run_dir, "screenshots")))
        self.assertTrue(
            os.path.isdir(os.path.join(run_dir, "output")))
        parent = os.path.basename(os.path.dirname(run_dir))
        self.assertEqual(parent, "runs")
        name = os.path.basename(run_dir)
        self.assertRegex(name, r"^\d{8}T\d{6}Z-[0-9a-f]{8}$")


class TranscriptTests(unittest.TestCase):
    def test_execute_writes_transcript_under_run_dir(self):
        workdir = tempfile.TemporaryDirectory()
        self.addCleanup(workdir.cleanup)
        home = workdir.name
        machine_id = "abcd" * 8
        machine_home = os.path.join(
            home, "cache", "machines", machine_id)
        run_dir = os.path.join(machine_home, "runs", "t-1")
        os.makedirs(os.path.join(run_dir, "screenshots"))
        os.makedirs(os.path.join(run_dir, "output"))
        script = parse_script("""
            platform: dos
            wait "Hello"
        """.strip())
        engine = _ScriptEngine(
            script, machine_id, home, machine_home,
            run_dir=run_dir, script_path="/tmp/demo.rlqs")
        engine._port = 5555

        class _Qmp:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                pass

            def screen_text(self):
                return ["Hello"]

        class _Console:
            def __init__(self, qmp):
                self._qmp = qmp

            def screen_text(self):
                return self._qmp.screen_text()

        with mock.patch(
                "reliquary.script_runner._machines") as machines, \
                mock.patch.object(
                    engine, "_session", return_value=_Qmp()), \
                mock.patch.object(
                    engine, "_console", side_effect=_Console), \
                contextlib.redirect_stdout(io.StringIO()):
            machines.load_machine_state.return_value = {
                "phase": "running"}
            machines.machine_dir_path.return_value = machine_home
            with mock.patch(
                    "reliquary.lifecycle.read_vm_state",
                    return_value={"port": 5555}):
                engine.run()

        transcript = os.path.join(run_dir, "transcript.txt")
        self.assertTrue(os.path.isfile(transcript))
        with open(transcript, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("script: /tmp/demo.rlqs", text)
        self.assertIn("wait 'Hello'", text)
        self.assertIn("result: ok", text)


class RunScriptWiringTests(unittest.TestCase):
    def setUp(self):
        self.workdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.workdir.cleanup)
        self.home = self.workdir.name
        blueprints = os.path.join(self.home, "blueprints")
        scripts = os.path.join(self.home, "scripts")
        os.makedirs(blueprints)
        os.makedirs(scripts)
        with open(os.path.join(blueprints, "plain.json"), "w",
                  encoding="utf-8") as handle:
            json.dump({
                "platform": "dos",
                "drives": {"hdd": {"size": "20M"}},
                "scripts": {"install": "plain-install"},
            }, handle)
        with open(os.path.join(scripts, "plain-install.rlqs"), "w",
                  encoding="utf-8", newline="\n") as handle:
            handle.write("platform: dos\n")
            handle.write('wait "ready", timeout: 1s\n')

    def test_run_script_resolves_label_and_records_run(self):
        with mock.patch("reliquary.machines.create_hdd_image"), \
                mock.patch(
                    "reliquary.script_runner.execute_script") as execute:
            result = run_script(
                "install", blueprint="plain", home=self.home)
        self.assertIsInstance(result, ScriptRun)
        self.assertTrue(result.created_machine)
        self.assertTrue(result.script_path.endswith(
            "plain-install.rlqs"))
        self.assertTrue(os.path.isdir(result.run_dir))
        execute.assert_called_once()
        kwargs = execute.call_args.kwargs
        self.assertEqual(kwargs["machine_id"], result.machine_id)
        self.assertEqual(kwargs["run_dir"], result.run_dir)
        self.assertEqual(kwargs["script_path"], result.script_path)
        self.assertEqual(kwargs["home"], self.home)
        self.assertFalse(kwargs["display"])

    def test_run_script_bare_stem_when_label_absent(self):
        scripts = os.path.join(self.home, "scripts")
        with open(os.path.join(scripts, "extra.rlqs"), "w",
                  encoding="utf-8", newline="\n") as handle:
            handle.write("platform: dos\n")
        with mock.patch("reliquary.machines.create_hdd_image"), \
                mock.patch("reliquary.script_runner.execute_script"):
            result = run_script(
                "extra", blueprint="plain", home=self.home)
        self.assertTrue(result.script_path.endswith("extra.rlqs"))

    def test_run_script_seeds_missing_script(self):
        os.remove(os.path.join(
            self.home, "scripts", "plain-install.rlqs"))

        def fake_seed(stem, home=None):
            path = os.path.join(self.home, "scripts", f"{stem}.rlqs")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("platform: dos\n")
            return True

        with mock.patch("reliquary.machines.create_hdd_image"), \
                mock.patch(
                    "reliquary.script_runner.seed_script",
                    side_effect=fake_seed) as seed, \
                mock.patch("reliquary.script_runner.execute_script"):
            result = run_script(
                "install", blueprint="plain", home=self.home)
        seed.assert_called_once_with("plain-install", home=self.home)
        self.assertTrue(os.path.isfile(result.script_path))

    def test_run_script_missing_script_fails(self):
        os.remove(os.path.join(
            self.home, "scripts", "plain-install.rlqs"))
        with mock.patch("reliquary.machines.create_hdd_image"), \
                mock.patch(
                    "reliquary.script_runner.seed_script",
                    return_value=False):
            with self.assertRaises(FileNotFoundError) as caught:
                run_script(
                    "install", blueprint="plain", home=self.home)
        self.assertIn("plain-install.rlqs", str(caught.exception))

    def test_run_script_forwards_display(self):
        with mock.patch("reliquary.machines.create_hdd_image"), \
                mock.patch(
                    "reliquary.script_runner.execute_script") as execute:
            run_script(
                "install", blueprint="plain", home=self.home,
                display=True)
        self.assertTrue(execute.call_args.kwargs["display"])

    def test_spike_10_cli_invokes_runtime_end_to_end(self):
        """Exit criterion: rlq --blueprint … script install wires through."""
        stdout = io.StringIO()
        with mock.patch("reliquary.machines.create_hdd_image"), \
                mock.patch(
                    "reliquary.cli.run_script",
                    return_value=ScriptRun(
                        machine_id="abcd" * 8,
                        run_dir=os.path.join(
                            self.home, "cache", "machines",
                            "abcd" * 8, "runs",
                            "20260101T000000Z-deadbeef"),
                        script_path=os.path.join(
                            self.home, "scripts",
                            "plain-install.rlqs"),
                        created_machine=True,
                    )) as run, \
                contextlib.redirect_stdout(stdout):
            result = cli.main([
                "--home", self.home,
                "--blueprint", "plain",
                "script", "install",
            ])
        self.assertEqual(result, 0)
        run.assert_called_once_with(
            "install",
            blueprint="plain",
            machine=None,
            home=self.home,
            display=False,
        )
        output = stdout.getvalue()
        self.assertIn("created machine", output)
        self.assertIn("plain-install.rlqs", output)
        self.assertIn("run:", output)

    def test_cli_script_requires_selector(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            result = cli.main([
                "--home", self.home, "script", "install",
            ])
        self.assertEqual(result, 1)
        self.assertIn("--blueprint or --machine", stderr.getvalue())

    def test_cli_script_forwards_display(self):
        with mock.patch(
                "reliquary.cli.run_script",
                return_value=ScriptRun(
                    machine_id="abcd" * 8,
                    run_dir="/tmp/run",
                    script_path="/tmp/x.rlqs",
                )) as run, \
                contextlib.redirect_stdout(io.StringIO()):
            result = cli.main([
                "--home", self.home,
                "--blueprint", "plain",
                "script", "install",
                "--display",
            ])
        self.assertEqual(result, 0)
        self.assertTrue(run.call_args.kwargs["display"])


if __name__ == "__main__":
    unittest.main()
