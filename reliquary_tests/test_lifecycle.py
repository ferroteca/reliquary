# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Installed tests for QEMU lifecycle ownership and state."""

import os
import sys
import tempfile
import types
import unittest
import uuid
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

import reliquary
from reliquary import lifecycle as lifecycle_module
from reliquary import workflows as workflows_module


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
    name = "reliquary-machine"
    vm_uuid = "00000000-0000-0000-0000-000000000000"

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
        if name == "query-uuid":
            return {"UUID": self.vm_uuid}
        return None


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.home = self.tempdir.name
        reliquary.set_home(self.home)
        _FakeQmp.commands = []
        _FakeQmp.name = "reliquary-machine"
        _FakeQmp.vm_uuid = "00000000-0000-0000-0000-000000000000"
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
        fake_uuid = uuid.UUID(int=0)
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
            port = reliquary.start(reliquary.MachineConfig(qemu="qemu"))

        self.assertEqual(port, 54321)
        self.assertEqual(lifecycle_module.read_vm_state(), {
            "port": 54321,
            "name": "reliquary-machine",
            "uuid": "00000000-0000-0000-0000-000000000000",
            "pid": 1234,
        })
        args = popen.call_args.args[0]
        self.assertEqual(args[args.index("-name") + 1],
                         "reliquary-machine")
        self.assertEqual(args[args.index("-uuid") + 1],
                         "00000000-0000-0000-0000-000000000000")

    def _start_qemu_args(self, image_name, **start_kwargs):
        image = self._write_boot_image(image_name)
        fake_uuid = uuid.UUID(int=0)
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
            config = reliquary.MachineConfig(qemu="qemu", **start_kwargs)
            reliquary.start(config)

        return image, popen.call_args.args[0]

    def _start_configured_args(self, drives, machine=None, memory=None):
        fake_uuid = uuid.UUID(int=0)
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
            config = reliquary.MachineConfig(
                qemu="qemu", drives=drives, machine=machine,
                memory=memory)
            reliquary.start(config)
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
            reliquary.start(reliquary.MachineConfig(
                qemu="qemu", memory=32, qemu_args=("-m", "64")))

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

    def test_stop_does_not_quit_vm_with_wrong_identity(self):
        lifecycle_module.write_vm_state(
            54321, "reliquary-expected",
            "00000000-0000-0000-0000-000000000000", 1234)
        _FakeQmp.name = "unrelated-vm"

        with mock.patch.object(lifecycle_module, "Qmp", _FakeQmp):
            with self.assertRaisesRegex(RuntimeError, "identity mismatch"):
                reliquary.stop()

        self.assertEqual(_FakeQmp.commands, ["query-name"])
        self.assertIsNotNone(lifecycle_module.read_vm_state())

    def test_stop_does_not_quit_same_named_vm_of_another_home(self):
        # two homes materialize same-numbered machines with the same
        # readable name; only the per-start uuid tells their VMs
        # apart, so a name match alone must never authorize quit
        lifecycle_module.write_vm_state(
            54321, "reliquary-machine",
            "11111111-1111-1111-1111-111111111111", 1234)
        _FakeQmp.name = "reliquary-machine"
        _FakeQmp.vm_uuid = "22222222-2222-2222-2222-222222222222"

        with mock.patch.object(lifecycle_module, "Qmp", _FakeQmp):
            with self.assertRaisesRegex(RuntimeError, "identity mismatch"):
                reliquary.stop()

        self.assertNotIn("quit", _FakeQmp.commands)
        self.assertIsNotNone(lifecycle_module.read_vm_state())

    def test_start_rejects_explicit_occupied_port_before_launch(self):
        with mock.patch.object(lifecycle_module, "port_in_use",
                               return_value=True):
            with self.assertRaisesRegex(RuntimeError, "explicit"):
                reliquary.start(
                    reliquary.MachineConfig(qemu="qemu"), port=54321)

        self.assertIsNone(lifecycle_module.read_vm_state())

    def test_start_terminates_child_on_identity_mismatch(self):
        self._write_boot_image()
        proc = _FakeProcess()
        _FakeQmp.name = "unrelated-vm"
        fake_uuid = uuid.UUID(int=0)

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
                reliquary.start(reliquary.MachineConfig(qemu="qemu"))

        self.assertTrue(proc.terminated)
        self.assertIsNone(lifecycle_module.read_vm_state())


class QmpTests(unittest.TestCase):
    """``Qmp`` owns the event loop it creates for the QMP connection."""

    def test_connect_failure_closes_the_loop(self):
        """A failed connect must not leak the event loop it created."""
        class _FailingClient:
            def __init__(self, name):
                pass

            async def connect(self, address):
                raise ConnectionRefusedError("refused")

        created_loops = []
        real_new_event_loop = lifecycle_module.asyncio.new_event_loop

        def _tracking_new_event_loop():
            loop = real_new_event_loop()
            created_loops.append(loop)
            return loop

        with mock.patch.object(lifecycle_module, "QMPClient",
                               _FailingClient), \
                mock.patch.object(lifecycle_module.asyncio,
                                  "new_event_loop",
                                  _tracking_new_event_loop):
            with self.assertRaises(ConnectionRefusedError):
                lifecycle_module.Qmp(1234)

        self.assertEqual(len(created_loops), 1)
        self.assertTrue(created_loops[0].is_closed())


class CreateHddImageTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = self.tempdir.name

    def tearDown(self):
        self.tempdir.cleanup()

    def _run_create(self, filename, capacity, *, returncode=0,
                    stderr=""):
        completed = mock.Mock(
            returncode=returncode, stdout="", stderr=stderr)
        with mock.patch.object(lifecycle_module, "find_qemu_img",
                               return_value="qemu-img"), \
                mock.patch.object(lifecycle_module.subprocess, "run",
                                  return_value=completed) as run:
            path = reliquary.create_hdd_image(filename, capacity)
        return path, run

    def test_creates_sparse_qcow2_v3_image(self):
        filename = os.path.join(self.root, "drives", "hdd.qcow2")

        path, run = self._run_create(filename, "2G")

        self.assertEqual(path, os.path.abspath(filename))
        self.assertEqual(
            run.call_args.args[0],
            ["qemu-img", "create", "-f", "qcow2",
             "-o", "compat=1.1,preallocation=off",
             os.path.abspath(filename), "2G"])
        self.assertTrue(os.path.isdir(os.path.dirname(path)))

    def test_integer_capacity_is_mib(self):
        filename = os.path.join(self.root, "disk.qcow2")

        _, run = self._run_create(filename, 512)

        self.assertEqual(run.call_args.args[0][-1], "512M")

    def test_rejects_non_qcow2_filename(self):
        with self.assertRaisesRegex(ValueError, r"\.qcow2"):
            reliquary.create_hdd_image(
                os.path.join(self.root, "hdd.img"), "1G")

    def test_rejects_existing_image(self):
        filename = os.path.join(self.root, "hdd.qcow2")
        with open(filename, "wb") as handle:
            handle.write(b"x")

        with self.assertRaises(FileExistsError):
            reliquary.create_hdd_image(filename, "1G")

    def test_rejects_non_positive_mib_capacity(self):
        filename = os.path.join(self.root, "hdd.qcow2")
        with self.assertRaisesRegex(ValueError, "positive"):
            reliquary.create_hdd_image(filename, 0)

    def test_surfaces_qemu_img_failure(self):
        filename = os.path.join(self.root, "hdd.qcow2")
        with self.assertRaisesRegex(RuntimeError, "qemu-img failed"):
            self._run_create(filename, "1G", returncode=1,
                             stderr="boom")


if __name__ == "__main__":
    unittest.main()
