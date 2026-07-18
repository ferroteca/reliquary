# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Installed tests for the Runner surface: config-carrying machines
whose operations take the home directory explicitly, never touching
the process-global home."""

import dataclasses
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
        machine = relict.Runner()

        self.assertEqual(machine.platform, "dos")
        self.assertEqual(machine.config, relict.RunnerConfig())

    def test_machine_exposes_its_immutable_config(self):
        config = relict.RunnerConfig(timeout=45)
        machine = relict.Runner(config)

        self.assertIs(machine.config, config)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            machine.config.timeout = 60

    def test_staged_drive_defaults_to_matching_the_boot_medium(self):
        # None: resolved per home against the boot image at run time
        self.assertIsNone(relict.RunnerConfig().staged_drive)
        self.assertEqual(
            relict.RunnerConfig(staged_drive="d").staged_drive, "D")
        with self.assertRaisesRegex(ValueError, "staged_drive"):
            relict.RunnerConfig(staged_drive="A")

    def test_boot_images_are_mutually_exclusive(self):
        with self.assertRaisesRegex(ValueError, "not both"):
            relict.RunnerConfig(boot_floppy_image="floppy.img",
                                  boot_hdd_image="hdd.img")

    def test_staged_drive_c_is_rejected_with_a_hdd_boot_image(self):
        with self.assertRaisesRegex(ValueError, "claims C:"):
            relict.RunnerConfig(boot_hdd_image="hdd.img",
                                  staged_drive="c")

    def test_platform_defaults_to_dos_and_normalizes(self):
        self.assertEqual(relict.RunnerConfig().platform, "dos")
        self.assertEqual(relict.RunnerConfig(platform="DOS").platform,
                         "dos")

    def test_non_dos_platform_rejects_dos_drive_configuration(self):
        with self.assertRaisesRegex(ValueError, "DOS-specific"):
            relict.RunnerConfig(platform="win9x", staged_drive="E")

    def test_non_dos_runner_workflow_is_an_explicit_stub(self):
        machine = relict.Runner(relict.RunnerConfig(platform="win9x"))
        with self.assertRaisesRegex(NotImplementedError, "win9x"):
            machine.run(lambda running: None, home="run-home")


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

    def test_present_image_is_never_overwritten(self):
        os.makedirs(self.drives)
        with open(os.path.join(self.drives, "floppy.img"),
                  "wb") as image:
            image.write(b"existing dos")
        ready = os.path.join(self.tempdir.name, "custom.img")
        with open(ready, "wb") as image:
            image.write(b"custom dos")
        machine = relict.Runner(
            relict.RunnerConfig(boot_floppy_image=ready))

        with mock.patch.object(relict,
                               "_download_boot_image") as download:
            machine.provision(self.drives)

        download.assert_not_called()
        self.assertEqual(self._image_bytes(), b"existing dos")

    def test_configured_floppy_image_is_copied(self):
        ready = os.path.join(self.tempdir.name, "custom.img")
        with open(ready, "wb") as image:
            image.write(b"custom dos")
        machine = relict.Runner(
            relict.RunnerConfig(boot_floppy_image=ready))

        with mock.patch.object(relict,
                               "_download_boot_image") as download:
            machine.provision(self.drives)

        download.assert_not_called()
        self.assertEqual(self._image_bytes(), b"custom dos")

    def test_configured_floppy_image_keeps_its_idiomatic_extension(self):
        ready = os.path.join(self.tempdir.name, "custom.qcow2")
        with open(ready, "wb") as image:
            image.write(b"custom qcow2 floppy")
        machine = relict.Runner(
            relict.RunnerConfig(boot_floppy_image=ready))

        with mock.patch.object(relict,
                               "_download_boot_image") as download:
            machine.provision(self.drives)

        download.assert_not_called()
        with open(os.path.join(self.drives, "floppy.qcow2"),
                  "rb") as image:
            self.assertEqual(image.read(), b"custom qcow2 floppy")

    def test_configured_hdd_image_keeps_its_idiomatic_extension(self):
        ready = os.path.join(self.tempdir.name, "custom.qcow2")
        with open(ready, "wb") as image:
            image.write(b"custom hdd dos")
        machine = relict.Runner(
            relict.RunnerConfig(boot_hdd_image=ready))

        with mock.patch.object(relict,
                               "_download_boot_image") as download:
            machine.provision(self.drives)

        download.assert_not_called()
        self.assertFalse(
            os.path.exists(os.path.join(self.drives, "floppy.img")))
        with open(os.path.join(self.drives, "hdd.qcow2"),
                  "rb") as image:
            self.assertEqual(image.read(), b"custom hdd dos")

    def test_default_provision_installs_the_downloaded_image(self):
        with mock.patch.object(relict,
                               "_download_boot_image") as download:
            relict.Runner().provision(self.drives)

        download.assert_called_once_with(self.drives)


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
        machine = relict.Runner(relict.RunnerConfig(
            timeout=45, qemu="qemu", qemu_args=("-nodefaults",)))

        with mock.patch.object(relict, "run_guest_program",
                               return_value="guest output") as run:
            log = machine.run(self.exe, "-v", self.home)

        run.assert_called_once_with(
            self.exe, "-v", timeout=45, staged_drive=None,
            qemu_args=("-nodefaults",),
            qemu="qemu", home=os.path.abspath(self.home))
        self.assertEqual(log, "guest output")

    def test_run_defaults_the_timeout(self):
        self._stage_boot_image()

        with mock.patch.object(relict, "run_guest_program",
                               return_value="") as run:
            relict.Runner().run(self.exe, "", self.home)

        self.assertEqual(run.call_args.kwargs["timeout"], 180)

    def test_run_provisions_a_missing_boot_image(self):
        ready = os.path.join(self.home, "custom.img")
        with open(ready, "wb") as image:
            image.write(b"custom dos")
        machine = relict.Runner(
            relict.RunnerConfig(boot_floppy_image=ready))

        with mock.patch.object(relict, "run_guest_program",
                               return_value=""):
            machine.run(self.exe, "", self.home)

        staged = os.path.join(self.home, "drives", "floppy.img")
        with open(staged, "rb") as image:
            self.assertEqual(image.read(), b"custom dos")

    def test_explicit_home_run_never_consults_the_global_home(self):
        # the concurrency guarantee: with home explicit end to end,
        # nothing may fall back to the process-global home
        self._stage_boot_image()
        relict._write_vm_state(54321, _FakeQmp.name, 1234,
                                 home=self.home)
        staging = os.path.join(relict.drives_dir(home=self.home),
                               "hdd")
        log_path = os.path.join(staging, "SUITE.log")

        def run_guest_command(command, *args):
            if command != "c:":
                with open(log_path, "w", encoding="utf-8") as log:
                    log.write("guest output")

        with mock.patch.object(
                relict, "home",
                side_effect=AssertionError(
                    "process-global home was consulted")), \
                mock.patch.object(relict, "start",
                                  return_value=54321) as start, \
                mock.patch.object(relict, "Qmp", _FakeQmp), \
                mock.patch.object(relict, "boot_to_dos"), \
                mock.patch.object(relict, "run_command",
                                  side_effect=run_guest_command), \
                mock.patch.object(relict, "stop") as stop, \
                mock.patch.object(relict.time, "sleep"):
            log = relict.Runner().run(self.exe, "-v", self.home)

        self.assertEqual(log, "guest output")
        expected_home = os.path.abspath(self.home)
        self.assertEqual(start.call_args.kwargs["home"], expected_home)
        stop.assert_called_once_with(54321, expected_home)

    def test_machines_with_distinct_homes_keep_separate_vm_state(self):
        with tempfile.TemporaryDirectory() as other:
            relict._write_vm_state(1111, "relict-first", 1,
                                     home=self.home)
            relict._write_vm_state(2222, "relict-second", 2,
                                     home=other)

            first = relict._read_vm_state(self.home)
            second = relict._read_vm_state(other)

        self.assertEqual(first["port"], 1111)
        self.assertEqual(second["port"], 2222)


if __name__ == "__main__":
    unittest.main()
