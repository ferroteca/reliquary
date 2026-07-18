# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Installed tests for the Runner surface: config-carrying machines
whose operations take the home directory explicitly, never touching
the process-global home."""

import dataclasses
import importlib
import json
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

    def test_memory_is_a_positive_integer_mib_value(self):
        self.assertEqual(relict.MachineConfig(memory=32).memory, 32)
        for value in (True, 0, -1, 1.5, "32"):
            with self.subTest(value=value):
                with self.assertRaises((TypeError, ValueError)):
                    relict.MachineConfig(memory=value)

    def test_memory_default_depends_on_platform(self):
        self.assertEqual(relict.MachineConfig().memory, 16)
        self.assertEqual(
            relict.MachineConfig(platform="win9x").memory, 64)
        self.assertEqual(
            relict.MachineConfig(platform="winnt").memory, 256)

    def test_memory_conflicts_with_raw_memory_argument(self):
        with self.assertRaisesRegex(ValueError, "conflicts"):
            relict.MachineConfig(memory=32, qemu_args=("-m", "64"))

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


class MachineConfigLoadingTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = self.tempdir.name

    def tearDown(self):
        self.tempdir.cleanup()

    def _write_json(self, relative, payload):
        path = os.path.join(self.root, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        return path

    def _touch(self, relative):
        path = os.path.join(self.root, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(b"image")
        return path

    def test_from_file_loads_a_versioned_machine_document(self):
        path = self._write_json("machine.json", {
            "version": 1,
            "platform": "win9x",
            "timeout": 90,
            "memory": 32,
            "qemu": "qemu-system-i386",
            "machine": {"type": "pc", "accel": "tcg"},
            "qemu_args": ["-cpu", "pentium"],
        })

        config = relict.MachineConfig.from_file(path)

        self.assertEqual(config.platform, "win9x")
        self.assertEqual(config.timeout, 90)
        self.assertEqual(config.memory, 32)
        self.assertEqual(config.qemu, "qemu-system-i386")
        self.assertEqual(dict(config.machine), {
            "type": "pc",
            "accel": "tcg",
        })
        self.assertEqual(config.qemu_args, ("-cpu", "pentium"))
        self.assertFalse(hasattr(config, "version"))

    def test_from_file_requires_version_one(self):
        path = self._write_json("machine.json", {"platform": "dos"})
        with self.assertRaisesRegex(ValueError, r"version"):
            relict.MachineConfig.from_file(path)

        path = self._write_json("machine.json", {"version": 2})
        with self.assertRaisesRegex(ValueError, r"version"):
            relict.MachineConfig.from_file(path)

    def test_from_mapping_rejects_unknown_fields_with_paths(self):
        with self.assertRaisesRegex(ValueError, r"unknown field: boot"):
            relict.MachineConfig.from_mapping({
                "version": 1,
                "boot": "a",
            })

    def test_from_file_resolves_relative_drive_sources_from_file_dir(self):
        image = self._touch("images/dos.img")
        path = self._write_json("machines/dos.json", {
            "version": 1,
            "drives": {
                "hdd_0": {
                    "source": "../images/dos.img",
                    "options": {"snapshot": True},
                },
            },
        })

        config = relict.MachineConfig.from_file(path)

        self.assertEqual(config.drives["hdd_0"]["source"],
                         os.path.abspath(image))
        self.assertEqual(dict(config.drives["hdd_0"]["options"]),
                         {"snapshot": True})

    def test_from_mapping_resolves_relative_sources_from_base_dir(self):
        image = self._touch("media/boot.img")
        base = os.path.join(self.root, "cfg")
        os.makedirs(base)

        config = relict.MachineConfig.from_mapping({
            "version": 1,
            "drives": {"floppy_0": "../media/boot.img"},
        }, base_dir=base)

        self.assertEqual(config.drives["floppy_0"]["source"],
                         os.path.abspath(image))

    def test_from_mapping_without_base_dir_uses_the_current_directory(self):
        image = self._touch("cwd-boot.img")
        previous = os.getcwd()
        try:
            os.chdir(self.root)
            config = relict.MachineConfig.from_mapping({
                "version": 1,
                "drives": {"floppy_0": "cwd-boot.img"},
            })
        finally:
            os.chdir(previous)

        self.assertEqual(config.drives["floppy_0"]["source"],
                         os.path.abspath(image))

    def test_explicit_overrides_replace_scalars_and_qemu_args(self):
        path = self._write_json("machine.json", {
            "version": 1,
            "platform": "win9x",
            "timeout": 30,
            "qemu_args": ["-cpu", "486"],
            "machine": "pc-i440fx-2.12",
        })

        config = relict.MachineConfig.from_file(
            path,
            platform="dos",
            timeout=None,
            qemu_args=("-cpu", "pentium"),
            machine={"type": "pc", "accel": "tcg"},
        )

        self.assertEqual(config.platform, "dos")
        self.assertIsNone(config.timeout)
        self.assertEqual(config.qemu_args, ("-cpu", "pentium"))
        self.assertEqual(dict(config.machine), {
            "type": "pc",
            "accel": "tcg",
        })

    def test_drive_overrides_merge_by_slot_and_option_name(self):
        image = self._touch("images/base.img")
        path = self._write_json("machines/base.json", {
            "version": 1,
            "drives": {
                "hdd_0": {
                    "source": "../images/base.img",
                    "options": {
                        "snapshot": True,
                        "cache": "writeback",
                    },
                },
            },
        })
        override_image = self._touch("override.img")

        config = relict.MachineConfig.from_file(
            path,
            drives={
                "hdd_0": {
                    "options": {"cache": "unsafe"},
                },
                "floppy_0": override_image,
            },
        )

        self.assertEqual(config.drives["hdd_0"]["source"],
                         os.path.abspath(image))
        self.assertEqual(dict(config.drives["hdd_0"]["options"]), {
            "snapshot": True,
            "cache": "unsafe",
        })
        self.assertEqual(config.drives["floppy_0"]["source"],
                         os.path.abspath(override_image))

    def test_missing_explicit_machine_file_is_an_error(self):
        missing = os.path.join(self.root, "missing.json")
        with self.assertRaises(FileNotFoundError):
            relict.MachineConfig.from_file(missing)


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
            timeout=45, memory=32, qemu="qemu",
            qemu_args=("-nodefaults",)))

        with mock.patch.object(workflows_module, "run_guest_program",
                               return_value="guest output") as run:
            log = machine.run(self.exe, "-v")

        run.assert_called_once_with(
            self.exe, "-v", timeout=45, staged_drive=None,
            qemu_args=("-nodefaults",),
            qemu="qemu", home=os.path.abspath(self.home),
            drives=machine.config.drives, machine=None, memory=32)
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
