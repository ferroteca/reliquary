# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Installed tests for the Runner surface: config-carrying machines
whose operations take the home directory explicitly, never touching
the process-global home."""

import dataclasses
import importlib
import os
import sys
import tempfile
import types
import unittest
from unittest import mock

try:
    import qemu.qmp  # noqa: F401
except ModuleNotFoundError:
    qmp = types.ModuleType("qemu.qmp")
    qmp.ConnectError = type("ConnectError", (Exception,), {})
    qmp.ExecuteError = type("ExecuteError", (Exception,), {})
    qmp.QMPClient = object
    qemu = types.ModuleType("qemu")
    qemu.qmp = qmp
    sys.modules["qemu"] = qemu
    sys.modules["qemu.qmp"] = qmp

import relict
from relict import lifecycle as lifecycle_module
from relict import workflows as workflows_module

home_module = importlib.import_module("relict.home")


class _FakeQmp:
    name = "relict-0123456789ab"

    def __init__(self, port):
        self.port = port

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass

    def cmd(self, name, **arguments):
        if name == "query-name":
            return {"name": self.name}
        return None


class RunnerConstructionTests(unittest.TestCase):
    def test_default_machine_targets_dos_with_default_config(self):
        machine = relict.Runner("run-home")

        self.assertEqual(machine.platform, "dos")
        self.assertEqual(machine.config, relict.MachineConfig())
        self.assertEqual(machine.home, os.path.abspath("run-home"))

    def test_omitted_home_uses_the_established_default(self):
        expected = os.path.abspath("default-home")
        with mock.patch.object(workflows_module, "effective_home",
                               return_value=expected) as resolve:
            machine = relict.Runner()

        resolve.assert_called_once_with(None)
        self.assertEqual(machine.home, expected)

    def test_machine_exposes_its_immutable_config(self):
        config = relict.MachineConfig(timeout=45)
        machine = relict.Runner("run-home", config)

        self.assertIs(machine.config, config)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            machine.config.timeout = 60

    def test_machine_string_is_normalized_to_immutable_mapping(self):
        config = relict.MachineConfig(machine="pc-i440fx-9.2")

        self.assertEqual(dict(config.machine), {
            "type": "pc-i440fx-9.2",
        })
        with self.assertRaises(TypeError):
            config.machine["type"] = "pc"

    def test_machine_mapping_requires_type_and_normalizes_options(self):
        config = relict.MachineConfig(machine={
            "type": "pc",
            "accel": "tcg",
            "usb": False,
        })

        self.assertEqual(dict(config.machine), {
            "type": "pc",
            "accel": "tcg",
            "usb": False,
        })
        with self.assertRaisesRegex(ValueError, "machine.type"):
            relict.MachineConfig(machine={"accel": "tcg"})

    def test_machine_conflicts_with_raw_machine_argument(self):
        with self.assertRaisesRegex(ValueError, "conflicts"):
            relict.MachineConfig(
                machine="pc", qemu_args=("-machine", "q35"))

    def test_drive_specs_normalize_aliases_and_freeze_values(self):
        with tempfile.TemporaryDirectory() as root:
            floppy = os.path.join(root, "boot.img")
            with open(floppy, "wb") as image:
                image.write(b"dos")
            staging = os.path.join(root, "staging")
            os.makedirs(staging)

            config = relict.MachineConfig(drives={
                "floppy": floppy,
                "hdd": {
                    "source": staging,
                    "options": {"snapshot": True},
                },
            })

        self.assertEqual(set(config.drives), {"floppy_0", "hdd_0"})
        self.assertEqual(config.drives["floppy_0"]["source"],
                         os.path.abspath(floppy))
        self.assertEqual(dict(config.drives["hdd_0"]["options"]),
                         {"snapshot": True})
        with self.assertRaises(TypeError):
            config.drives["hdd_0"] = {}

    def test_drive_alias_cannot_duplicate_canonical_slot(self):
        with tempfile.NamedTemporaryFile() as image:
            with self.assertRaisesRegex(ValueError, "both mean floppy_0"):
                relict.MachineConfig(drives={
                    "floppy": image.name,
                    "floppy_0": image.name,
                })

    def test_cdrom_drive_source_cannot_be_a_directory(self):
        with tempfile.TemporaryDirectory() as source:
            with self.assertRaisesRegex(ValueError, "ISO9660"):
                relict.MachineConfig(drives={"cdrom_0": source})

    def test_staged_drive_defaults_to_matching_the_boot_medium(self):
        # None: resolved per home against the boot image at run time
        self.assertIsNone(relict.MachineConfig().staged_drive)
        self.assertEqual(
            relict.MachineConfig(staged_drive="d").staged_drive, "D")
        with self.assertRaisesRegex(ValueError, "staged_drive"):
            relict.MachineConfig(staged_drive="A")

    def test_platform_defaults_to_dos_and_normalizes(self):
        self.assertEqual(relict.MachineConfig().platform, "dos")
        self.assertEqual(relict.MachineConfig(platform="DOS").platform,
                         "dos")

    def test_non_dos_platform_rejects_dos_drive_configuration(self):
        with self.assertRaisesRegex(ValueError, "DOS-specific"):
            relict.MachineConfig(platform="win9x", staged_drive="E")

    def test_non_dos_runner_workflow_is_an_explicit_stub(self):
        machine = relict.Runner(
            "run-home", relict.MachineConfig(platform="win9x"))
        with self.assertRaisesRegex(NotImplementedError, "win9x"):
            machine.run(lambda running: None)

    def test_provisioning_is_not_public(self):
        self.assertFalse(hasattr(relict.Runner("run-home"), "provision"))


class ProvisionTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.drives = os.path.join(self.tempdir.name, "drives")

    def tearDown(self):
        self.tempdir.cleanup()

    def _image_bytes(self):
        with open(os.path.join(self.drives, "floppy.img"),
                  "rb") as image:
            return image.read()

    def _run(self, machine):
        with mock.patch.object(workflows_module, "run_guest_program",
                               return_value=""):
            machine.run("SUITE.EXE")

    def test_present_image_is_never_overwritten(self):
        os.makedirs(self.drives)
        with open(os.path.join(self.drives, "floppy.img"),
                  "wb") as image:
            image.write(b"existing dos")
        machine = relict.Runner(self.tempdir.name)

        with mock.patch.object(workflows_module,
                               "prepare_drives") as prepare:
            self._run(machine)

        prepare.assert_not_called()
        self.assertEqual(self._image_bytes(), b"existing dos")

    def test_empty_home_installs_the_freedos_fallback(self):
        with mock.patch.object(workflows_module,
                               "prepare_drives") as prepare:
            self._run(relict.Runner(self.tempdir.name))

        prepare.assert_called_once_with(self.drives, mock.ANY)

    def test_configured_boot_source_suppresses_fallback(self):
        source = os.path.join(self.tempdir.name, "boot.img")
        with open(source, "wb") as image:
            image.write(b"dos")
        machine = relict.Runner(
            self.tempdir.name,
            relict.MachineConfig(drives={"floppy": source}))

        with mock.patch.object(workflows_module,
                               "prepare_drives") as prepare:
            self._run(machine)

        prepare.assert_not_called()


class RunnerRunTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.home = self.tempdir.name
        self.exe = os.path.join(self.home, "SUITE.EXE")
        with open(self.exe, "wb") as executable:
            executable.write(b"test executable")

    def tearDown(self):
        self.tempdir.cleanup()

    def _stage_boot_image(self):
        drives = os.path.join(self.home, "drives")
        os.makedirs(drives, exist_ok=True)
        with open(os.path.join(drives, "floppy.img"), "wb") as image:
            image.write(b"staged dos")

    def test_run_forwards_home_and_config(self):
        self._stage_boot_image()
        machine = relict.Runner(self.home, relict.MachineConfig(
            timeout=45, qemu="qemu", qemu_args=("-nodefaults",)))

        with mock.patch.object(workflows_module, "run_guest_program",
                               return_value="guest output") as run:
            log = machine.run(self.exe, "-v")

        run.assert_called_once_with(
            self.exe, "-v", timeout=45, staged_drive=None,
            qemu_args=("-nodefaults",),
            qemu="qemu", home=os.path.abspath(self.home),
            drives=machine.config.drives, machine=None)
        self.assertEqual(log, "guest output")

    def test_run_defaults_the_timeout(self):
        self._stage_boot_image()

        with mock.patch.object(workflows_module, "run_guest_program",
                               return_value="") as run:
            relict.Runner(self.home).run(self.exe)

        self.assertEqual(run.call_args.kwargs["timeout"], 180)

    def test_explicit_home_run_never_consults_the_global_home(self):
        # the concurrency guarantee: with home explicit end to end,
        # nothing may fall back to the process-global home
        self._stage_boot_image()
        lifecycle_module.write_vm_state(
            54321, _FakeQmp.name, 1234, home=self.home)
        staging = os.path.join(relict.drives_dir(home=self.home),
                               "hdd")
        log_path = os.path.join(staging, "SUITE.log")

        def run_guest_command(command, *args):
            if command != "c:":
                with open(log_path, "w", encoding="utf-8") as log:
                    log.write("guest output")

        guest = mock.Mock()
        guest.execute.side_effect = run_guest_command

        with mock.patch.object(
                home_module, "home",
                side_effect=AssertionError(
                    "process-global home was consulted")), \
                mock.patch.object(workflows_module, "start",
                                  return_value=54321) as start, \
                mock.patch.object(workflows_module, "AgentlessGuestExec",
                                  return_value=guest), \
                mock.patch.object(workflows_module, "stop") as stop, \
                mock.patch.object(workflows_module.time, "sleep"):
            log = relict.Runner(self.home).run(self.exe, "-v")

        self.assertEqual(log, "guest output")
        expected_home = os.path.abspath(self.home)
        self.assertEqual(start.call_args.kwargs["home"], expected_home)
        stop.assert_called_once_with(54321, expected_home)

    def test_machines_with_distinct_homes_keep_separate_vm_state(self):
        with tempfile.TemporaryDirectory() as other:
            first_runner = relict.Runner(self.home)
            second_runner = relict.Runner(other)
            lifecycle_module.write_vm_state(
                1111, "relict-first", 1, home=first_runner.home)
            lifecycle_module.write_vm_state(
                2222, "relict-second", 2, home=second_runner.home)

            first = lifecycle_module.read_vm_state(first_runner.home)
            second = lifecycle_module.read_vm_state(second_runner.home)

        self.assertEqual(first["port"], 1111)
        self.assertEqual(second["port"], 2222)


if __name__ == "__main__":
    unittest.main()
