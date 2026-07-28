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
from reliquary.errors import PreflightError, RunFailure, StaticError


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
    """VM ownership guarantees over ``launch_owned_qemu`` and ``stop``."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.home = self.tempdir.name
        reliquary.set_home_dir(self.home)
        _FakeQmp.commands = []
        _FakeQmp.name = "reliquary-machine"
        _FakeQmp.vm_uuid = "00000000-0000-0000-0000-000000000000"
        self._remove_generated_files()

    def tearDown(self):
        self._remove_generated_files()
        self.tempdir.cleanup()

    def _remove_generated_files(self):
        for name in ("machine.json", "machine.json.part", "qemu-stderr.log"):
            try:
                os.remove(os.path.join(self.home, name))
            except FileNotFoundError:
                pass

    def test_launch_returns_verified_identity(self):
        proc = _FakeProcess()
        with mock.patch.object(lifecycle_module, "available_port",
                               return_value=54321), \
                mock.patch.object(lifecycle_module, "port_in_use",
                                  return_value=False), \
                mock.patch.object(lifecycle_module.uuid, "uuid4",
                                  return_value=uuid.UUID(int=0)), \
                mock.patch.object(lifecycle_module, "Qmp", _FakeQmp), \
                mock.patch.object(lifecycle_module.subprocess, "Popen",
                                  return_value=proc) as popen:
            identity = lifecycle_module.launch_owned_qemu(
                ["qemu", "-name", "reliquary-machine"],
                vm_name="reliquary-machine", log_dir=self.home)

        # Lifecycle no longer owns a state file: it returns the verified
        # identity for the caller (machines.py) to persist.
        self.assertEqual(identity, {
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

    def test_launch_rejects_explicit_occupied_port_before_launch(self):
        with mock.patch.object(lifecycle_module, "port_in_use",
                               return_value=True):
            with self.assertRaisesRegex(PreflightError, "explicit"):
                lifecycle_module.launch_owned_qemu(
                    ["qemu", "-name", "reliquary-machine"],
                    vm_name="reliquary-machine", port=54321)
        self.assertIsNone(lifecycle_module.read_vm_state())

    def test_launch_terminates_child_on_identity_mismatch(self):
        proc = _FakeProcess()
        _FakeQmp.name = "unrelated-vm"
        with mock.patch.object(lifecycle_module, "available_port",
                               return_value=54321), \
                mock.patch.object(lifecycle_module, "port_in_use",
                                  return_value=False), \
                mock.patch.object(lifecycle_module.uuid, "uuid4",
                                  return_value=uuid.UUID(int=0)), \
                mock.patch.object(lifecycle_module, "Qmp", _FakeQmp), \
                mock.patch.object(lifecycle_module.subprocess, "Popen",
                                  return_value=proc):
            with self.assertRaisesRegex(PreflightError, "identity mismatch"):
                lifecycle_module.launch_owned_qemu(
                    ["qemu", "-name", "reliquary-machine"],
                    vm_name="reliquary-machine")

        self.assertTrue(proc.terminated)
        self.assertIsNone(lifecycle_module.read_vm_state())

    def test_stop_does_not_quit_vm_with_wrong_identity(self):
        vm = {"port": 54321, "name": "reliquary-expected",
              "uuid": "00000000-0000-0000-0000-000000000000", "pid": 1234}
        _FakeQmp.name = "unrelated-vm"

        with mock.patch.object(lifecycle_module, "Qmp", _FakeQmp):
            with self.assertRaisesRegex(PreflightError, "identity mismatch"):
                lifecycle_module.stop(vm)

        self.assertEqual(_FakeQmp.commands, ["query-name"])

    def test_stop_does_not_quit_same_named_vm_of_another_home(self):
        # two homes materialize same-numbered machines with the same
        # readable name; only the per-start uuid tells their VMs
        # apart, so a name match alone must never authorize quit
        vm = {"port": 54321, "name": "reliquary-machine",
              "uuid": "11111111-1111-1111-1111-111111111111", "pid": 1234}
        _FakeQmp.name = "reliquary-machine"
        _FakeQmp.vm_uuid = "22222222-2222-2222-2222-222222222222"

        with mock.patch.object(lifecycle_module, "Qmp", _FakeQmp):
            with self.assertRaisesRegex(PreflightError, "identity mismatch"):
                lifecycle_module.stop(vm)

        self.assertNotIn("quit", _FakeQmp.commands)


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
        with self.assertRaisesRegex(StaticError, r"\.qcow2"):
            reliquary.create_hdd_image(
                os.path.join(self.root, "hdd.img"), "1G")

    def test_rejects_existing_image(self):
        filename = os.path.join(self.root, "hdd.qcow2")
        with open(filename, "wb") as handle:
            handle.write(b"x")

        with self.assertRaises(PreflightError):
            reliquary.create_hdd_image(filename, "1G")

    def test_rejects_non_positive_mib_capacity(self):
        filename = os.path.join(self.root, "hdd.qcow2")
        with self.assertRaisesRegex(StaticError, "positive"):
            reliquary.create_hdd_image(filename, 0)

    def test_surfaces_qemu_img_failure(self):
        filename = os.path.join(self.root, "hdd.qcow2")
        with self.assertRaisesRegex(RunFailure, "qemu-img failed"):
            self._run_create(filename, "1G", returncode=1,
                             stderr="boom")


if __name__ == "__main__":
    unittest.main()
