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
from reliquary import text_recognize
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

    def test_capabilities_include_agentless_display(self):
        report = self.adapter.capabilities()
        self.assertEqual(report.control_planes, ("agentless-display",))
        self.assertEqual(report.media, ("floppy", "hdd", "cdrom"))
        self.assertEqual(report.controllers, ("ide",))
        self.assertFalse(report.vvfat)
        self.assertFalse(report.at_rest)

    def _install(self, root, payload):
        """A stand-in VirtualBox install directory carrying ``payload``."""
        with open(os.path.join(root, "VBoxDD2.dll"), "wb") as handle:
            handle.write(payload)
        return mock.patch.object(
            vbox, "find_vboxmanage",
            return_value=os.path.join(root, "VBoxManage.exe"))

    def test_the_glyph_bank_is_read_from_the_installation(self):
        """The font comes off the host; none is vendored here.

        The fixture embeds Reliquary's *own* bank in a stand-in
        binary, so the suite carries no other project's font while
        still proving the adapter reads one out of its install.
        """
        own = text_recognize.glyph_bank()
        with tempfile.TemporaryDirectory() as home:
            with self._install(home, b"\x11" * 500 + own + b"\x22" * 30):
                self.assertEqual(vbox.guest_glyph_bank(), own)

    def test_the_bank_is_cached_under_the_backend_support_dir(self):
        own = text_recognize.glyph_bank()
        with tempfile.TemporaryDirectory() as home, \
                tempfile.TemporaryDirectory() as cache:
            with self._install(home, b"\x11" * 500 + own + b"\x22" * 30):
                self.assertEqual(vbox.guest_glyph_bank(cache), own)
            expected = os.path.join(cache, "support", "virtualbox",
                                    "cp437-8x16.bin")
            self.assertTrue(os.path.isfile(expected))
            with open(expected, "rb") as handle:
                self.assertEqual(handle.read(), own)
            # Served from the cache now: the install is gone and the
            # answer is unchanged.
            with mock.patch.object(
                    vbox, "find_vboxmanage",
                    side_effect=AssertionError("must not re-extract")):
                self.assertEqual(vbox.guest_glyph_bank(cache), own)

    def test_a_truncated_cache_file_is_re_extracted(self):
        own = text_recognize.glyph_bank()
        with tempfile.TemporaryDirectory() as home, \
                tempfile.TemporaryDirectory() as cache:
            stale = os.path.join(cache, "support", "virtualbox")
            os.makedirs(stale)
            with open(os.path.join(stale, "cp437-8x16.bin"), "wb") as handle:
                handle.write(b"\x00" * 100)
            with self._install(home, b"\x11" * 500 + own + b"\x22" * 30):
                self.assertEqual(vbox.guest_glyph_bank(cache), own)

    def test_an_installation_with_no_font_fails_closed(self):
        with tempfile.TemporaryDirectory() as home:
            with self._install(home, b"\x00" * 9000):
                with self.assertRaises(PreflightError) as caught:
                    vbox.guest_glyph_bank()
        self.assertEqual(caught.exception.rule_id,
                         "recognize.font-not-found")
        self.assertIn("cannot read a guest screen", str(caught.exception))

    def test_text_screen_reads_through_the_host_font(self):
        marker = b"\x5a" * 4096
        session = vbox.VirtualBoxSession(
            "uuid-1", "reliquary-plain-0", cache="/tmp/cache")
        with mock.patch.object(vbox, "guest_glyph_bank",
                               return_value=marker) as bank, \
                mock.patch.object(session, "screenshot"), \
                mock.patch.object(vbox.text_recognize, "recognize",
                                  return_value=([], [])) as recognize:
            session.text_screen()
        self.assertEqual(recognize.call_args.kwargs["bank"], marker)
        # And the session's cache root is where it is told to keep it.
        self.assertEqual(bank.call_args.args, ("/tmp/cache",))

    def test_hard_disks_take_the_ide_slots_before_cdroms(self):
        """The boot disk must be the primary master, not the slave.

        Ordering the two kinds together by key made the slot fall out
        of the alphabet: `cdrom0` sorts before `hdd0` and took the
        master, stranding the boot disk on the slave, where a PC BIOS
        told to boot `disk` stops at `No active partition`.
        """
        state = {"drives": {
            "cdrom0": {"medium": "cdrom"},
            "hdd0": {"medium": "hdd"},
        }}

        attachments = vbox.drive_attachments(state)

        self.assertEqual(
            (attachments["hdd0"]["port"], attachments["hdd0"]["device"]),
            (0, 0))
        self.assertEqual(
            (attachments["cdrom0"]["port"],
             attachments["cdrom0"]["device"]),
            (0, 1))
        self.assertEqual(attachments["hdd0"]["type"], "hdd")
        self.assertEqual(attachments["cdrom0"]["type"], "dvddrive")

    def test_several_disks_keep_key_order_within_their_kind(self):
        state = {"drives": {
            "cdrom0": {"medium": "cdrom"},
            "hdd0": {"medium": "hdd"},
            "hdd1": {"medium": "hdd"},
            "floppy0": {"medium": "floppy"},
        }}

        attachments = vbox.drive_attachments(state)

        self.assertEqual(attachments["hdd0"]["port"], 0)
        self.assertEqual(attachments["hdd0"]["device"], 0)
        self.assertEqual(attachments["hdd1"]["port"], 0)
        self.assertEqual(attachments["hdd1"]["device"], 1)
        self.assertEqual(attachments["cdrom0"]["port"], 1)
        self.assertEqual(attachments["cdrom0"]["device"], 0)
        self.assertEqual(attachments["floppy0"]["storagectl"],
                         vbox._FLOPPY)

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
        self.assertIn("hdd0", identity["endpoint"]["drives"])
        self.assertEqual(
            identity["endpoint"]["drives"]["hdd0"]["type"], "hdd")
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

    def test_send_keys_emits_make_then_break_scancodes(self):
        calls = []

        def run(args, **kwargs):
            calls.append(list(args))
            return _completed(stdout=self._info(state="running"))

        vm = {
            "backend": "virtualbox", "backend-id": self.vm_uuid,
            "token": self.vm_uuid,
            "endpoint": {"name": "reliquary-demo-0", "drives": {}},
        }
        adapter = vbox.VirtualBoxAdapter()
        with mock.patch.object(vbox, "find_vboxmanage",
                               return_value="VBoxManage"), \
             mock.patch("subprocess.run", side_effect=run), \
             mock.patch.object(vbox.time, "sleep"):
            with adapter.session(vm) as session:
                session.send_keys([["ret"]], delay=0)
        key_call = next(c for c in calls
                        if c[1:][:2] == ["controlvm", self.vm_uuid]
                        and "keyboardputscancode" in c)
        # enter make 1c, break 9c
        self.assertEqual(key_call[-2:], ["1c", "9c"])

    def test_change_medium_retargets_the_recorded_attachment(self):
        calls = []

        def run(args, **kwargs):
            calls.append(list(args))
            return _completed(stdout=self._info(state="running"))

        drives = {
            "cdrom0": {
                "storagectl": "reliquary-ide", "port": 1, "device": 0,
                "type": "dvddrive",
            },
        }
        vm = {
            "backend": "virtualbox", "backend-id": self.vm_uuid,
            "token": self.vm_uuid,
            "endpoint": {"name": "reliquary-demo-0", "drives": drives},
        }
        iso = os.path.join(self.tempdir.name, "live.iso")
        with open(iso, "wb") as handle:
            handle.write(b"ISO")
        adapter = vbox.VirtualBoxAdapter()
        with mock.patch.object(vbox, "find_vboxmanage",
                               return_value="VBoxManage"), \
             mock.patch("subprocess.run", side_effect=run):
            with adapter.session(vm) as session:
                session.change_medium("cdrom0", iso)
                session.change_medium("cdrom0", None)
        attaches = [c for c in calls if c[1] == "storageattach"]
        self.assertEqual(len(attaches), 2)
        self.assertTrue(any(iso in a for a in attaches[0]))
        self.assertTrue(any("emptydrive" in a for a in attaches[1]))

    def test_scancodes_for_shift_chord(self):
        codes = vbox.scancodes_for(["shift", "a"])
        # shift make, a make, a break, shift break
        self.assertEqual(codes, [0x2a, 0x1e, 0x9e, 0xaa])


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
