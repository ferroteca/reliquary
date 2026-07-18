# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Installed tests for QEMU lifecycle ownership and state."""

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


class _FakeProcess:
    pid = 1234

    def __init__(self):
        self.returncode = None
        self.terminated = False

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = 1

    def wait(self, timeout=None):
        return self.returncode

    def kill(self):
        self.returncode = 1


class _FakeQmp:
    commands = []
    name = "relict-0123456789ab"

    def __init__(self, port):
        self.port = port

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass

    def cmd(self, name, **arguments):
        self.commands.append(name)
        if name == "query-name":
            return {"name": self.name}
        return None


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.home = self.tempdir.name
        relict.set_home(self.home)
        _FakeQmp.commands = []
        _FakeQmp.name = "relict-0123456789ab"
        self._remove_generated_files()

    def tearDown(self):
        self._remove_generated_files()
        self.tempdir.cleanup()

    def _remove_generated_files(self):
        for name in ("vm.json", "vm.json.part", "qemu-stderr.log"):
            try:
                os.remove(os.path.join(self.home, name))
            except FileNotFoundError:
                pass

    def _write_boot_image(self, name="floppy.img", data=b"dos"):
        drives = os.path.join(self.home, "drives")
        os.makedirs(drives, exist_ok=True)
        path = os.path.join(drives, name)
        with open(path, "wb") as img:
            img.write(data)
        return path

    def _make_drive_dir(self, name):
        path = os.path.join(self.home, "drives", name)
        os.makedirs(path)
        return path

    def test_start_returns_port_and_records_identity(self):
        self._write_boot_image()
        fake_uuid = types.SimpleNamespace(hex="0123456789abcdef")
        proc = _FakeProcess()

        with mock.patch.object(lifecycle_module, "available_port",
                               return_value=54321), \
                mock.patch.object(lifecycle_module, "port_in_use",
                                  return_value=False), \
                mock.patch.object(lifecycle_module.uuid, "uuid4",
                                  return_value=fake_uuid), \
                mock.patch.object(lifecycle_module, "Qmp", _FakeQmp), \
                mock.patch.object(lifecycle_module.subprocess, "Popen",
                                  return_value=proc) as popen:
            port = relict.start(qemu="qemu")

        self.assertEqual(port, 54321)
        self.assertEqual(lifecycle_module.read_vm_state(), {
            "port": 54321,
            "name": "relict-0123456789ab",
            "pid": 1234,
        })
        args = popen.call_args.args[0]
        self.assertEqual(args[args.index("-name") + 1],
                         "relict-0123456789ab")

    def _start_qemu_args(self, image_name, **start_kwargs):
        image = self._write_boot_image(image_name)
        fake_uuid = types.SimpleNamespace(hex="0123456789abcdef")
        proc = _FakeProcess()

        with mock.patch.object(lifecycle_module, "available_port",
                               return_value=54321), \
                mock.patch.object(lifecycle_module, "port_in_use",
                                  return_value=False), \
                mock.patch.object(lifecycle_module.uuid, "uuid4",
                                  return_value=fake_uuid), \
                mock.patch.object(lifecycle_module, "Qmp", _FakeQmp), \
                mock.patch.object(lifecycle_module.subprocess, "Popen",
                                  return_value=proc) as popen:
            relict.start(qemu="qemu", **start_kwargs)

        return image, popen.call_args.args[0]

    def _start_configured_args(self, drives, machine=None, memory=None):
        fake_uuid = types.SimpleNamespace(hex="0123456789abcdef")
        proc = _FakeProcess()
        with mock.patch.object(lifecycle_module, "available_port",
                               return_value=54321), \
                mock.patch.object(lifecycle_module, "port_in_use",
                                  return_value=False), \
                mock.patch.object(lifecycle_module.uuid, "uuid4",
                                  return_value=fake_uuid), \
                mock.patch.object(lifecycle_module, "Qmp", _FakeQmp), \
                mock.patch.object(lifecycle_module.subprocess, "Popen",
                                  return_value=proc) as popen:
            relict.start(qemu="qemu", drives=drives, machine=machine,
                         memory=memory)
        return popen.call_args.args[0]

    def test_start_boots_the_floppy_image_as_drive_a(self):
        image, args = self._start_qemu_args("floppy.img")

        self.assertIn(f"file={image},format=raw,if=floppy,index=0",
                      args)
        self.assertEqual(args[args.index("-boot") + 1], "a")

    def test_start_leaves_a_non_img_floppy_format_to_qemu(self):
        image, args = self._start_qemu_args("floppy.qcow2")

        self.assertIn(f"file={image},if=floppy,index=0", args)
        self.assertEqual(args[args.index("-boot") + 1], "a")

    def test_start_pins_a_raw_img_hdd_image_to_format_raw(self):
        image, args = self._start_qemu_args("hdd.img")

        self.assertIn(f"file={image},format=raw,if=ide,index=0", args)
        self.assertEqual(args[args.index("-boot") + 1], "c")

    def test_start_boots_a_cdrom_image(self):
        image, args = self._start_qemu_args("cdrom.iso")

        self.assertIn(
            f"file={image},format=raw,media=cdrom,if=ide,index=0",
            args)
        self.assertEqual(args[args.index("-boot") + 1], "d")

    def test_start_places_cdroms_after_the_hard_disks(self):
        hdd = self._write_boot_image("hdd.qcow2")
        image, args = self._start_qemu_args("cdrom.iso")

        self.assertIn(f"file={hdd},if=ide,index=0", args)
        self.assertIn(
            f"file={image},format=raw,media=cdrom,if=ide,index=1",
            args)
        self.assertEqual(args[args.index("-boot") + 1], "c")

    def test_start_mounts_directories_as_virtual_fat_drives(self):
        staged_hdd = self._make_drive_dir("hdd")
        staged_floppy = self._make_drive_dir("floppy_1")

        image, args = self._start_qemu_args("floppy.img")

        self.assertIn(f"file={image},format=raw,if=floppy,index=0",
                      args)
        self.assertIn(
            f"file=fat:floppy:rw:{staged_floppy},format=raw,"
            "if=floppy,index=1", args)
        self.assertIn(f"file=fat:rw:{staged_hdd},format=raw,"
                      "if=ide,index=0", args)

    def test_start_mounts_configured_file_source(self):
        source = os.path.join(self.home, "external.img")
        with open(source, "wb") as image:
            image.write(b"dos")

        args = self._start_configured_args({
            "floppy": {
                "source": source,
                "options": {"snapshot": True},
            },
        })

        self.assertIn(
            f"file={source},format=raw,snapshot=on,"
            "if=floppy,index=0", args)
        self.assertEqual(args[args.index("-boot") + 1], "a")

    def test_start_renders_one_machine_argument(self):
        source = os.path.join(self.home, "boot.img")
        with open(source, "wb") as image:
            image.write(b"dos")

        args = self._start_configured_args(
            {"floppy": source},
            machine={"type": "pc", "accel": "tcg", "usb": False})

        self.assertEqual(args.count("-machine"), 1)
        self.assertEqual(
            args[args.index("-machine") + 1],
            "pc,accel=tcg,usb=off")

    def test_start_renders_configured_memory(self):
        source = os.path.join(self.home, "boot.img")
        with open(source, "wb") as image:
            image.write(b"dos")

        args = self._start_configured_args(
            {"floppy": source}, memory=32)

        self.assertEqual(args.count("-m"), 1)
        self.assertEqual(args[args.index("-m") + 1], "32")

    def test_start_rejects_configured_and_raw_memory(self):
        with self.assertRaisesRegex(ValueError, "conflicts"):
            relict.start(qemu="qemu", memory=32,
                         qemu_args=("-m", "64"))

    def test_start_mounts_configured_directory_as_vvfat(self):
        source = os.path.join(self.home, "external-drive")
        os.makedirs(source)
        self._write_boot_image("floppy.img")

        args = self._start_configured_args({"hdd": source})

        self.assertIn(
            f"file=fat:rw:{source},format=raw,if=ide,index=0", args)

    def test_configured_source_clashes_with_filesystem_drive(self):
        self._write_boot_image("floppy.img")
        source = os.path.join(self.home, "external.img")
        with open(source, "wb") as image:
            image.write(b"dos")

        with self.assertRaisesRegex(RuntimeError, "slot clash"):
            self._start_configured_args({"floppy_0": source})

    def test_start_rejects_a_drive_slot_clash(self):
        self._write_boot_image("floppy.img")

        with self.assertRaisesRegex(RuntimeError, "slot clash"):
            self._start_qemu_args("floppy_0.img")

    def test_start_defaults_memory_and_boot_order(self):
        _, args = self._start_qemu_args("floppy.img")

        self.assertEqual(args[args.index("-m") + 1], "16")
        self.assertEqual(args[args.index("-boot") + 1], "a")

    def test_start_uses_the_platform_memory_default(self):
        for platform, expected in (("win9x", "64"),
                                   ("winnt", "256")):
            with self.subTest(platform=platform):
                self._remove_generated_files()
                _, args = self._start_qemu_args(
                    "floppy.img", platform=platform)
                self.assertEqual(args[args.index("-m") + 1], expected)

    def test_start_defers_to_user_memory_and_boot_order(self):
        _, args = self._start_qemu_args(
            "floppy.img", qemu_args=("-m", "64", "-boot", "c"))

        self.assertEqual(args.count("-m"), 1)
        self.assertEqual(args[args.index("-m") + 1], "64")
        self.assertEqual(args.count("-boot"), 1)
        self.assertEqual(args[args.index("-boot") + 1], "c")

    def test_start_downloads_missing_boot_image(self):
        fake_uuid = types.SimpleNamespace(hex="0123456789abcdef")
        proc = _FakeProcess()

        def fake_download(drives, media):
            self._write_boot_image(data=b"freedos")

        with mock.patch.object(workflows_module, "prepare_drives",
                               side_effect=fake_download) as download, \
                mock.patch.object(lifecycle_module, "available_port",
                                  return_value=54321), \
                mock.patch.object(lifecycle_module, "port_in_use",
                                  return_value=False), \
                mock.patch.object(lifecycle_module.uuid, "uuid4",
                                  return_value=fake_uuid), \
                mock.patch.object(lifecycle_module, "Qmp", _FakeQmp), \
                mock.patch.object(lifecycle_module.subprocess, "Popen",
                                  return_value=proc):
            port = relict.start(qemu="qemu")

        download.assert_called_once_with(
            os.path.join(self.home, "drives"), mock.ANY)
        self.assertEqual(port, 54321)

    def test_stop_does_not_quit_vm_with_wrong_identity(self):
        lifecycle_module.write_vm_state(
            54321, "relict-expected", 1234)
        _FakeQmp.name = "unrelated-vm"

        with mock.patch.object(lifecycle_module, "Qmp", _FakeQmp):
            with self.assertRaisesRegex(RuntimeError, "identity mismatch"):
                relict.stop()

        self.assertEqual(_FakeQmp.commands, ["query-name"])
        self.assertIsNotNone(lifecycle_module.read_vm_state())

    def test_start_rejects_explicit_occupied_port_before_launch(self):
        with mock.patch.object(lifecycle_module, "port_in_use",
                               return_value=True):
            with self.assertRaisesRegex(RuntimeError, "explicit"):
                relict.start(qemu="qemu", port=54321)

        self.assertIsNone(lifecycle_module.read_vm_state())

    def test_start_terminates_child_on_identity_mismatch(self):
        self._write_boot_image()
        proc = _FakeProcess()
        _FakeQmp.name = "unrelated-vm"
        fake_uuid = types.SimpleNamespace(hex="0123456789abcdef")

        with mock.patch.object(lifecycle_module, "available_port",
                               return_value=54321), \
                mock.patch.object(lifecycle_module, "port_in_use",
                                  return_value=False), \
                mock.patch.object(lifecycle_module.uuid, "uuid4",
                                  return_value=fake_uuid), \
                mock.patch.object(lifecycle_module, "Qmp", _FakeQmp), \
                mock.patch.object(lifecycle_module.subprocess, "Popen",
                                  return_value=proc):
            with self.assertRaisesRegex(RuntimeError, "identity mismatch"):
                relict.start(qemu="qemu")

        self.assertTrue(proc.terminated)
        self.assertIsNone(lifecycle_module.read_vm_state())


if __name__ == "__main__":
    unittest.main()
