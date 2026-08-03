# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Installed tests for the VirtualBox adapter: images, lifecycle.

Everything below the adapter seam that only VirtualBox knows — VDI
materialization, createvm under the machine directory, owned start
and stop with identity verification. ``VBoxManage`` is always
mocked; no unit test launches a real hypervisor.
"""

import os
import tempfile
import unittest
import uuid
from unittest import mock

from reliquary import backend_virtualbox as vbox
from reliquary.errors import PreflightError, StaticError


def _completed(stdout="", stderr="", returncode=0):
    result = mock.Mock()
    result.stdout = stdout
    result.stderr = stderr
    result.returncode = returncode
    return result


class SizeTests(unittest.TestCase):
    def test_size_strings_become_megabytes(self):
        self.assertEqual(vbox.size_megabytes("20M"), 20)
        self.assertEqual(vbox.size_megabytes("2G"), 2048)
        self.assertEqual(vbox.size_megabytes(32), 32)

    def test_sub_megabyte_sizes_round_up_to_one(self):
        self.assertEqual(vbox.size_megabytes("512K"), 1)

    def test_a_bad_size_is_static(self):
        with self.assertRaises(StaticError) as caught:
            vbox.size_megabytes("plenty")
        self.assertEqual(caught.exception.rule_id, "value.not-a-size")


class ImageTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = self.tempdir.name

    def test_create_vdi_invokes_createmedium(self):
        path = os.path.join(self.root, "disk.vdi")
        with mock.patch.object(vbox, "find_vboxmanage",
                               return_value="VBoxManage"), \
             mock.patch("subprocess.run",
                        return_value=_completed()) as run:
            result = vbox.create_vdi(path, "20M")
        self.assertEqual(result, os.path.abspath(path))
        args = run.call_args[0][0]
        self.assertEqual(args[0], "VBoxManage")
        self.assertEqual(args[1], "createmedium")
        self.assertIn("--format=VDI", args)
        self.assertIn("--size=20", args)

    def test_create_vdi_refuses_a_non_vdi_path(self):
        with self.assertRaises(StaticError) as caught:
            vbox.create_vdi(os.path.join(self.root, "disk.qcow2"), "20M")
        self.assertEqual(caught.exception.rule_id, "image.wrong-extension")

    def test_create_vdi_refuses_an_existing_file(self):
        path = os.path.join(self.root, "disk.vdi")
        with open(path, "wb") as handle:
            handle.write(b"x")
        with self.assertRaises(PreflightError) as caught:
            vbox.create_vdi(path, "20M")
        self.assertEqual(caught.exception.rule_id, "image.already-exists")

    def test_difference_and_copy_use_the_right_verbs(self):
        base = os.path.join(self.root, "base.vdi")
        with open(base, "wb") as handle:
            handle.write(b"base")
        with mock.patch.object(vbox, "find_vboxmanage",
                               return_value="VBoxManage"), \
             mock.patch("subprocess.run",
                        return_value=_completed()) as run:
            vbox.create_difference_vdi(
                os.path.join(self.root, "diff.vdi"), base)
            diff_args = run.call_args[0][0]
            vbox.create_duplicate_vdi(
                os.path.join(self.root, "copy.vdi"), base)
            copy_args = run.call_args[0][0]
        self.assertEqual(diff_args[1], "createmedium")
        self.assertTrue(any(a.startswith("--diffparent=")
                            for a in diff_args))
        self.assertEqual(copy_args[1], "clonemedium")


class AdapterSurfaceTests(unittest.TestCase):
    def setUp(self):
        self.adapter = vbox.VirtualBoxAdapter()
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)

    def test_image_path_is_vdi(self):
        path = self.adapter.image_path(self.tempdir.name, "hdd0")
        self.assertTrue(path.endswith("hdd0.vdi"))

    def test_capabilities_omit_agentless_display(self):
        report = self.adapter.capabilities()
        self.assertEqual(report.control_planes, ())
        self.assertEqual(report.media, ("floppy", "hdd", "cdrom"))
        self.assertEqual(report.controllers, ("ide",))
        self.assertFalse(report.vvfat)
        self.assertFalse(report.at_rest)

    def test_discover_reports_a_found_binary(self):
        with mock.patch.object(vbox, "find_vboxmanage",
                               return_value="C:/VBoxManage.exe"):
            probe = self.adapter.discover()
        self.assertTrue(probe.available)
        self.assertEqual(probe.executable, "C:/VBoxManage.exe")
        self.assertIsNone(probe.version)
    def test_discover_reports_absence(self):
        with mock.patch.object(
                vbox, "find_vboxmanage",
                side_effect=PreflightError("missing",
                    rule_id="machine.backend-not-found")):
            probe = self.adapter.discover()
        self.assertFalse(probe.available)
        self.assertIn("missing", probe.detail)


class OwnershipTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.backend_dir = os.path.join(self.tempdir.name, "virtualbox")
        os.makedirs(self.backend_dir)
        self.state = {
            "id": "demo-0",
            "backend-id": "reliquary-demo-0",
            "memory": 32,
            "cpus": 1,
            "boot": ["hdd0"],
            "drives": {
                "hdd0": {
                    "medium": "hdd", "path": os.path.join(
                        self.tempdir.name, "disk.vdi"),
                },
            },
        }
        self.vm_uuid = "11111111-2222-3333-4444-555555555555"

    def _info(self, state="poweroff", name="reliquary-demo-0"):
        return (
            f'name="{name}"\n'
            f'UUID="{self.vm_uuid}"\n'
            f'VMState="{state}"\n'
        )

    def test_launch_creates_configures_and_starts(self):
        calls = []

        def run(args, **kwargs):
            calls.append(list(args))
            verb = args[1]
            if verb == "showvminfo":
                # First ensure_vm probe: absent. Later verifies: present.
                if len([c for c in calls if c[1] == "showvminfo"]) == 1:
                    return _completed(returncode=1, stderr="not found")
                return _completed(stdout=self._info())
            return _completed()

        with mock.patch.object(vbox, "find_vboxmanage",
                               return_value="VBoxManage"), \
             mock.patch("subprocess.run", side_effect=run), \
             mock.patch.object(vbox.uuid, "uuid4",
                               return_value=uuid.UUID(self.vm_uuid)):
            identity = vbox.launch_owned_vm(
                self.state, backend_dir=self.backend_dir)

        self.assertEqual(identity["backend"], "virtualbox")
        self.assertEqual(identity["backend-id"], self.vm_uuid)
        self.assertEqual(identity["token"], self.vm_uuid)
        self.assertEqual(identity["endpoint"]["name"], "reliquary-demo-0")
        verbs = [c[1] for c in calls]
        self.assertIn("createvm", verbs)
        self.assertIn("modifyvm", verbs)
        self.assertIn("storagectl", verbs)
        self.assertIn("storageattach", verbs)
        self.assertIn("startvm", verbs)
        create = next(c for c in calls if c[1] == "createvm")
        self.assertIn("--platform-architecture=x86", create)
        self.assertIn("--ostype=DOS", create)
        self.assertTrue(any(a.startswith("--basefolder=") for a in create))

    def test_stop_verifies_identity_before_poweroff(self):
        calls = []

        def run(args, **kwargs):
            calls.append(list(args))
            if args[1] == "showvminfo":
                return _completed(stdout=self._info(state="running"))
            return _completed()

        vm = {"backend": "virtualbox", "backend-id": self.vm_uuid,
              "token": self.vm_uuid, "endpoint": {"name": "x"}}
        with mock.patch.object(vbox, "find_vboxmanage",
                               return_value="VBoxManage"), \
             mock.patch("subprocess.run", side_effect=run):
            vbox.stop(vm)
        self.assertEqual(calls[0][1], "showvminfo")
        self.assertEqual(calls[1][1:], ["controlvm", self.vm_uuid,
                                        "poweroff"])

    def test_stop_refuses_an_identity_mismatch(self):
        def run(args, **kwargs):
            if args[1] == "showvminfo":
                return _completed(stdout=self._info().replace(
                    self.vm_uuid, "00000000-0000-0000-0000-000000000000"))
            return _completed()

        vm = {"backend": "virtualbox", "backend-id": self.vm_uuid,
              "token": self.vm_uuid, "endpoint": {}}
        with mock.patch.object(vbox, "find_vboxmanage",
                               return_value="VBoxManage"), \
             mock.patch("subprocess.run", side_effect=run):
            with self.assertRaises(PreflightError) as caught:
                vbox.stop(vm)
        self.assertEqual(caught.exception.rule_id,
                         "machine.vm-identity-mismatch")

    def test_session_carriers_name_the_unbuilt_plane(self):
        def run(args, **kwargs):
            return _completed(stdout=self._info(state="running"))

        vm = {"backend": "virtualbox", "backend-id": self.vm_uuid,
              "token": self.vm_uuid, "endpoint": {}}
        adapter = vbox.VirtualBoxAdapter()
        with mock.patch.object(vbox, "find_vboxmanage",
                               return_value="VBoxManage"), \
             mock.patch("subprocess.run", side_effect=run):
            with adapter.session(vm) as session:
                with self.assertRaises(PreflightError) as caught:
                    session.send_keys([["ret"]])
        self.assertEqual(caught.exception.rule_id,
                         "machine.control-plane-unbuilt")


class BootOrderTests(unittest.TestCase):
    def test_boot_keys_map_to_vbox_kinds(self):
        drives = {
            "floppy0": {"medium": "floppy"},
            "hdd0": {"medium": "hdd"},
            "cdrom0": {"medium": "cdrom"},
        }
        self.assertEqual(
            vbox._boot_order(["cdrom0", "hdd0", "floppy0"], drives),
            ["dvd", "disk", "floppy", "none"])
