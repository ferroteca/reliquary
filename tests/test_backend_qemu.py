# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Installed tests for the QEMU adapter: ownership, images, rendering.

Everything below the adapter seam that only QEMU knows — the owned
launch and its identity verification, qcow2 materialization, the
drive and boot rendering a machine's state lowers into, and the
carriers a session exposes.
"""

import io
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
from reliquary import backend_qemu as qemu_module
from reliquary.errors import PreflightError, RunFailure, StaticError
from tests import fat_image


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


def _identity(port=54321, name="reliquary-machine",
              token="00000000-0000-0000-0000-000000000000"):
    return {"backend": "qemu", "backend-id": name, "token": token,
            "endpoint": {"port": port}, "pid": 1234}


class OwnershipTests(unittest.TestCase):
    """VM ownership guarantees over ``launch_owned_qemu`` and ``stop``."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.home = self.tempdir.name
        _FakeQmp.commands = []
        _FakeQmp.name = "reliquary-machine"
        _FakeQmp.vm_uuid = "00000000-0000-0000-0000-000000000000"

    def test_launch_returns_the_generic_verified_identity(self):
        proc = _FakeProcess()
        with mock.patch.object(qemu_module, "available_port",
                               return_value=54321), \
                mock.patch.object(qemu_module, "port_in_use",
                                  return_value=False), \
                mock.patch.object(qemu_module.uuid, "uuid4",
                                  return_value=uuid.UUID(int=0)), \
                mock.patch.object(qemu_module, "Qmp", _FakeQmp), \
                mock.patch.object(qemu_module.subprocess, "Popen",
                                  return_value=proc) as popen:
            identity = qemu_module.launch_owned_qemu(
                ["qemu", "-name", "reliquary-machine"],
                vm_name="reliquary-machine", log_dir=self.home)

        # The adapter owns no state: it returns the identity for the
        # machine model to persist, in the shape every backend records
        # — only the endpoint inside it is QEMU's own.
        self.assertEqual(identity, {
            "backend": "qemu",
            "backend-id": "reliquary-machine",
            "token": "00000000-0000-0000-0000-000000000000",
            "endpoint": {"port": 54321},
            "pid": 1234,
        })
        args = popen.call_args.args[0]
        self.assertEqual(args[args.index("-name") + 1],
                         "reliquary-machine")
        self.assertEqual(args[args.index("-uuid") + 1],
                         "00000000-0000-0000-0000-000000000000")

    def test_launch_rejects_explicit_occupied_port_before_launch(self):
        with mock.patch.object(qemu_module, "port_in_use",
                               return_value=True):
            with self.assertRaisesRegex(PreflightError, "explicit"):
                qemu_module.launch_owned_qemu(
                    ["qemu", "-name", "reliquary-machine"],
                    vm_name="reliquary-machine", port=54321)

    def test_launch_terminates_child_on_identity_mismatch(self):
        proc = _FakeProcess()
        _FakeQmp.name = "unrelated-vm"
        with mock.patch.object(qemu_module, "available_port",
                               return_value=54321), \
                mock.patch.object(qemu_module, "port_in_use",
                                  return_value=False), \
                mock.patch.object(qemu_module.uuid, "uuid4",
                                  return_value=uuid.UUID(int=0)), \
                mock.patch.object(qemu_module, "Qmp", _FakeQmp), \
                mock.patch.object(qemu_module.subprocess, "Popen",
                                  return_value=proc):
            with self.assertRaisesRegex(PreflightError, "identity mismatch"):
                qemu_module.launch_owned_qemu(
                    ["qemu", "-name", "reliquary-machine"],
                    vm_name="reliquary-machine", log_dir=self.home)

        self.assertTrue(proc.terminated)

    def test_stop_does_not_quit_vm_with_wrong_identity(self):
        _FakeQmp.name = "unrelated-vm"

        with mock.patch.object(qemu_module, "Qmp", _FakeQmp):
            with self.assertRaisesRegex(PreflightError, "identity mismatch"):
                qemu_module.stop(_identity(name="reliquary-expected"))

        self.assertEqual(_FakeQmp.commands, ["query-name"])

    def test_stop_does_not_quit_same_named_vm_of_another_home(self):
        # two homes materialize same-numbered machines with the same
        # readable backend-id; only the per-start token tells their VMs
        # apart, so a name match alone must never authorize quit
        _FakeQmp.name = "reliquary-machine"
        _FakeQmp.vm_uuid = "22222222-2222-2222-2222-222222222222"

        with mock.patch.object(qemu_module, "Qmp", _FakeQmp):
            with self.assertRaisesRegex(PreflightError, "identity mismatch"):
                qemu_module.stop(_identity(
                    token="11111111-1111-1111-1111-111111111111"))

        self.assertNotIn("quit", _FakeQmp.commands)

    def test_a_session_verifies_before_it_yields_a_carrier(self):
        adapter = qemu_module.QemuAdapter()
        _FakeQmp.name = "unrelated-vm"
        with mock.patch.object(qemu_module, "Qmp", _FakeQmp):
            with self.assertRaisesRegex(PreflightError, "identity mismatch"):
                with adapter.session(_identity()):
                    pass

    def test_a_vm_record_with_no_usable_endpoint_fails_closed(self):
        adapter = qemu_module.QemuAdapter()
        broken = dict(_identity(), endpoint={"socket": "/tmp/x"})
        with self.assertRaisesRegex(PreflightError, "usable QMP port"):
            with adapter.session(broken):
                pass


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
        real_new_event_loop = qemu_module.asyncio.new_event_loop

        def _tracking_new_event_loop():
            loop = real_new_event_loop()
            created_loops.append(loop)
            return loop

        with mock.patch.object(qemu_module, "QMPClient",
                               _FailingClient), \
                mock.patch.object(qemu_module.asyncio,
                                  "new_event_loop",
                                  _tracking_new_event_loop):
            with self.assertRaises(ConnectionRefusedError):
                qemu_module.Qmp(1234)

        self.assertEqual(len(created_loops), 1)
        self.assertTrue(created_loops[0].is_closed())


class CreateHddImageTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = self.tempdir.name

    def _run_create(self, filename, capacity, *, returncode=0,
                    stderr=""):
        completed = mock.Mock(
            returncode=returncode, stdout="", stderr=stderr)
        with mock.patch.object(qemu_module, "find_qemu_img",
                               return_value="qemu-img"), \
                mock.patch.object(qemu_module.subprocess, "run",
                                  return_value=completed) as run:
            path = qemu_module.create_hdd_image(filename, capacity)
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
            qemu_module.create_hdd_image(
                os.path.join(self.root, "hdd.img"), "1G")

    def test_rejects_existing_image(self):
        filename = os.path.join(self.root, "hdd.qcow2")
        with open(filename, "wb") as handle:
            handle.write(b"x")

        with self.assertRaises(PreflightError):
            qemu_module.create_hdd_image(filename, "1G")

    def test_rejects_non_positive_mib_capacity(self):
        filename = os.path.join(self.root, "hdd.qcow2")
        with self.assertRaisesRegex(StaticError, "positive"):
            qemu_module.create_hdd_image(filename, 0)

    def test_surfaces_qemu_img_failure(self):
        filename = os.path.join(self.root, "hdd.qcow2")
        with self.assertRaisesRegex(RunFailure, "qemu-img failed"):
            self._run_create(filename, "1G", returncode=1,
                             stderr="boom")

    def test_the_adapter_names_images_in_its_native_format(self):
        adapter = qemu_module.QemuAdapter()
        self.assertEqual(adapter.image_path(self.root, "blank"),
                         os.path.join(self.root, "blank.qcow2"))

    def test_the_adapter_routes_each_materialize_mode(self):
        adapter = qemu_module.QemuAdapter()
        with mock.patch.object(qemu_module, "create_hdd_image") as blank, \
                mock.patch.object(qemu_module,
                                  "create_difference_image") as diff, \
                mock.patch.object(qemu_module,
                                  "create_duplicate_image") as copy:
            adapter.create_image("a.qcow2", mode="new", size="20M")
            adapter.create_image("b.qcow2", mode="difference", base="base")
            adapter.create_image("c.qcow2", mode="copy", base="base")
        blank.assert_called_once_with("a.qcow2", "20M")
        diff.assert_called_once_with("b.qcow2", "base")
        copy.assert_called_once_with("c.qcow2", "base")


def _drive_values(args):
    return [args[i + 1] for i, a in enumerate(args) if a == "-drive"]


class DriveRenderingTests(unittest.TestCase):
    """Reliquary drive vocabulary in, QEMU configuration out."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = self.tempdir.name

    def _image(self, name):
        path = os.path.join(self.root, name)
        with open(path, "wb") as handle:
            handle.write(b"IMAGE")
        return path

    def test_floppies_render_before_hard_disks(self):
        drives = {
            "hdd0": {"medium": "hdd", "slot": 0,
                     "path": self._image("blank.qcow2")},
            "floppy0": {"medium": "floppy", "slot": 0,
                        "path": self._image("boot.img")},
        }
        values = _drive_values(qemu_module.drive_args(drives))
        floppy = next(i for i, v in enumerate(values) if "if=floppy" in v)
        hdd = next(i for i, v in enumerate(values) if "if=ide,index=0" in v)
        self.assertLess(floppy, hdd)

    def test_a_cdrom_takes_the_ide_slot_after_the_last_disk(self):
        drives = {
            "hdd0": {"medium": "hdd", "slot": 0,
                     "path": self._image("blank.qcow2")},
            "cdrom0": {"medium": "cdrom", "slot": 0,
                       "path": self._image("live.iso")},
        }
        cdrom = [v for v in _drive_values(qemu_module.drive_args(drives))
                 if "media=cdrom" in v]
        self.assertEqual(len(cdrom), 1)
        # An .iso is pinned to raw rather than probed.
        self.assertIn("format=raw,", cdrom[0])
        self.assertIn("if=ide,index=1", cdrom[0])

    def test_an_empty_removable_slot_renders_a_medium_less_drive(self):
        drives = {"cdrom0": {"medium": "cdrom", "slot": 0, "path": None}}
        self.assertEqual(
            _drive_values(qemu_module.drive_args(drives)),
            ["media=cdrom,if=ide,index=0,id=cdrom0"])

    def test_a_host_directory_renders_as_vvfat(self):
        # The one capability only knowable after resolution, so it is
        # judged here rather than at assignment.
        work = os.path.join(self.root, "work")
        os.makedirs(work)
        drives = {"hdd0": {"medium": "hdd", "slot": 0, "path": work}}
        values = _drive_values(qemu_module.drive_args(drives))
        self.assertTrue(any("fat:rw:" in value for value in values))

    def test_a_removable_drive_carries_its_key_as_the_launch_id(self):
        drives = {"floppy0": {"medium": "floppy", "slot": 0,
                              "path": self._image("boot.img")}}
        values = _drive_values(qemu_module.drive_args(drives))
        self.assertIn("id=floppy0", values[0])

    def test_the_boot_order_becomes_firmware_letters(self):
        drives = {"hdd0": {"medium": "hdd", "slot": 0, "path": None},
                  "cdrom0": {"medium": "cdrom", "slot": 0, "path": None}}
        self.assertEqual(
            qemu_module._boot_order(["cdrom0", "hdd0"], drives), "dc")
        self.assertEqual(
            qemu_module._boot_order(["hdd0", "cdrom0"], drives), "cd")

    def test_start_renders_the_state_and_launches_it(self):
        adapter = qemu_module.QemuAdapter()
        state = {
            "id": "plain-0", "backend-id": "reliquary-plain-0",
            "memory": 32, "boot": ["cdrom0"],
            "drives": {"cdrom0": {"medium": "cdrom", "slot": 0,
                                  "path": self._image("live.iso")}},
        }
        with mock.patch.object(qemu_module, "find_qemu",
                               return_value="qemu-system-i386"), \
                mock.patch.object(qemu_module, "launch_owned_qemu") as launch:
            adapter.start(state, machine_dir=self.root,
                          backend_dir=os.path.join(self.root, "qemu"))
        args = launch.call_args.args[0]
        self.assertEqual(args[0], "qemu-system-i386")
        self.assertEqual(args[args.index("-m") + 1], "32")
        self.assertIn("order=d", args)
        self.assertEqual(launch.call_args.kwargs["vm_name"],
                         "reliquary-plain-0")
        self.assertEqual(launch.call_args.kwargs["log_dir"],
                         os.path.join(self.root, "qemu"))


class BackendSettingsTests(unittest.TestCase):
    """The escape hatch: honored, bounded, and never a second source.

    One function validates and renders, so every assertion here is
    about both at once — what `create` accepts is what `start` puts on
    the command line.
    """

    def test_the_documented_keys_render(self):
        self.assertEqual(
            qemu_module.settings_args({"machine": "pc",
                                       "args": ["-cpu", "486"]}),
            ["-machine", "pc", "-cpu", "486"])

    def test_an_absent_or_empty_section_renders_nothing(self):
        for section in (None, {}, {"args": []}):
            with self.subTest(section=section):
                self.assertEqual(qemu_module.settings_args(section), [])

    def test_a_key_qemu_does_not_define_is_refused(self):
        with self.assertRaises(StaticError) as caught:
            qemu_module.settings_args({"cpus": 2})
        self.assertEqual(caught.exception.rule_id,
                         "machine.settings-unknown-key")
        self.assertIn("machine, args", str(caught.exception))

    def test_the_key_shapes_are_checked(self):
        for section, rule in (
                ({"machine": ""}, "value.not-a-string"),
                ({"machine": 42}, "value.not-a-string"),
                ({"args": "-cpu 486"}, "value.not-an-array"),
                ({"args": [486]}, "value.not-a-string")):
            with self.subTest(section=section):
                with self.assertRaises(StaticError) as caught:
                    qemu_module.settings_args(section)
                self.assertEqual(caught.exception.rule_id, rule)

    def test_every_reliquary_owned_argument_is_refused_by_its_owner(self):
        owners = {
            "-m": "memory", "-smp": "cpus", "-boot": "boot",
            "-drive": "drives", "-hda": "drives", "-fda": "drives",
            "-cdrom": "drives", "-machine": "machine", "-M": "machine",
            "-name": "identity", "-uuid": "identity",
            "-qmp": "control channel", "-display": "display",
            "-nographic": "display",
        }
        for argument, owner in owners.items():
            with self.subTest(argument=argument):
                with self.assertRaises(StaticError) as caught:
                    qemu_module.settings_args({"args": [argument, "x"]})
                self.assertEqual(caught.exception.rule_id,
                                 "machine.settings-reserved-argument")
                self.assertIn(owner, str(caught.exception))

    def test_an_option_and_its_value_in_one_element_is_still_caught(self):
        # `["-m 64"]` is not two arguments and QEMU would refuse it
        # anyway; refusing it here names the actual mistake.
        with self.assertRaises(StaticError) as caught:
            qemu_module.settings_args({"args": ["-m 64"]})
        self.assertEqual(caught.exception.rule_id,
                         "machine.settings-reserved-argument")

    def test_the_hatch_still_passes_a_device_and_a_cpu_model(self):
        # The two the reserved set must NOT catch. `-device` is the
        # documented route to a device the curated vocabulary does not
        # name yet (D91), and `-cpu` selects a model where `cpus` owns
        # only the count — the cookbook's own 486 recipe.
        self.assertEqual(
            qemu_module.settings_args(
                {"args": ["-device", "virtio-net-pci", "-cpu", "486"]}),
            ["-device", "virtio-net-pci", "-cpu", "486"])

    def test_a_value_that_merely_looks_like_an_option_passes(self):
        self.assertEqual(
            qemu_module.settings_args({"args": ["-cpu", "486", "-vga", "std"]}),
            ["-cpu", "486", "-vga", "std"])

    def test_validate_settings_is_the_renderer_and_returns_nothing(self):
        adapter = qemu_module.QemuAdapter()
        self.assertEqual(adapter.settings_keys, ("machine", "args"))
        self.assertIsNone(adapter.validate_settings({"machine": "pc"}))
        with self.assertRaises(StaticError):
            adapter.validate_settings({"args": ["-boot", "d"]})

    def test_start_renders_this_backends_section_last(self):
        adapter = qemu_module.QemuAdapter()
        state = {
            "id": "hatch-0", "backend-id": "reliquary-hatch-0",
            "memory": 32, "boot": [], "drives": {},
            "backend-settings": {
                "qemu": {"machine": "pc", "args": ["-cpu", "486"]},
                # Another backend's section is inert, and reading it
                # here would put VMware configuration on QEMU's line.
                "vmware": {"nonsense": True},
            },
        }
        with mock.patch.object(qemu_module, "find_qemu",
                               return_value="qemu-system-i386"), \
                mock.patch.object(qemu_module, "launch_owned_qemu") as launch:
            adapter.start(state, machine_dir=".", backend_dir="qemu")
        args = launch.call_args.args[0]
        self.assertEqual(args[-4:], ["-machine", "pc", "-cpu", "486"])
        self.assertNotIn("nonsense", args)


class CarrierTests(unittest.TestCase):
    """The session's carriers, over a scripted monitor."""

    def test_the_text_screen_reads_characters_and_attribute_tokens(self):
        cells = []
        for index, char in enumerate("A:\\>" + " " * (80 * 25 - 4)):
            cells.extend((ord(char), 0x70 if index < 4 else 0x07))
        lines = []
        for offset in range(0, len(cells), 16):
            payload = " ".join(f"0x{value:02x}" for value in
                               cells[offset:offset + 16])
            lines.append(f"00000000000b{offset:04x}: {payload}")
        qmp = mock.Mock()
        qmp.hmp.return_value = "\n".join(lines)

        rows, attributes = qemu_module.QemuSession(qmp).text_screen()

        self.assertEqual(rows[0], "A:\\>")
        self.assertEqual(attributes[0][:5], [0x70] * 4 + [0x07])
        self.assertEqual(len(attributes), 25)
        self.assertTrue(all(len(row) == 80 for row in attributes))
        qmp.hmp.assert_called_once_with("xp /4000bx 0xb8000")

    def test_key_names_reach_qmp_as_qcode_events(self):
        qmp = mock.Mock()
        with mock.patch.object(qemu_module.time, "sleep"):
            qemu_module.QemuSession(qmp).send_keys([["shift", "a"]])
        qmp.cmd.assert_called_once_with(
            "send-key",
            keys=[{"type": "qcode", "data": "shift"},
                  {"type": "qcode", "data": "a"}])

    def test_a_medium_change_targets_the_drive_by_key(self):
        qmp = mock.Mock()
        session = qemu_module.QemuSession(qmp)
        session.change_medium("cdrom0", "C:\\images\\live.iso")
        session.change_medium("cdrom0")
        lines = [call.args[0] for call in qmp.hmp.call_args_list]
        self.assertEqual(lines[0], "change cdrom0 C:/images/live.iso raw")
        self.assertEqual(lines[1], "eject cdrom0")

    def test_screenshot_requests_a_png(self):
        qmp = mock.Mock()
        written = qemu_module.QemuSession(qmp).screenshot("C:\\shots\\a.png")
        qmp.cmd.assert_called_once_with(
            "screendump", filename="C:/shots/a.png", format="png")
        self.assertEqual(written, "C:\\shots\\a.png")

    def test_screenshot_converts_a_legacy_ppm(self):
        class UnsupportedPngError(Exception):
            pass

        with tempfile.TemporaryDirectory() as root:
            png = os.path.join(root, "legacy.png")
            ppm = os.path.join(root, "legacy.ppm")

            def screendump(command, **arguments):
                self.assertEqual(command, "screendump")
                if arguments.get("format") == "png":
                    raise UnsupportedPngError()
                with open(arguments["filename"], "wb") as image:
                    image.write(b"P6\n1 1\n255\n\x01\x02\x03")

            qmp = mock.Mock()
            qmp.cmd.side_effect = screendump
            with mock.patch.object(qemu_module, "ExecuteError",
                                   UnsupportedPngError), \
                    mock.patch.object(qemu_module.time, "sleep"):
                qemu_module.QemuSession(qmp).screenshot(png)

            self.assertFalse(os.path.exists(ppm))
            with open(png, "rb") as image:
                self.assertEqual(image.read(8), b"\x89PNG\r\n\x1a\n")

    def test_the_native_seam_hands_back_the_monitor_itself(self):
        qmp = mock.Mock()
        self.assertIs(qemu_module.QemuSession(qmp).native(), qmp)


class DiscoveryTests(unittest.TestCase):
    """Discovery reports availability, and never raises."""

    def test_a_missing_binary_reports_unavailable_with_the_reason(self):
        adapter = qemu_module.QemuAdapter()
        with mock.patch.object(
                qemu_module, "find_qemu",
                side_effect=PreflightError(
                    "qemu-system-i386 not found",
                    rule_id="machine.backend-not-found")):
            probe = adapter.discover()
        self.assertFalse(probe.available)
        self.assertIn("not found", probe.detail)
        self.assertEqual(probe.backend, "qemu")

    def test_a_binary_that_will_not_report_a_version_is_still_available(self):
        adapter = qemu_module.QemuAdapter()
        with mock.patch.object(qemu_module, "find_qemu",
                               return_value="/usr/bin/qemu-system-i386"), \
                mock.patch.object(qemu_module, "_qemu_version",
                                  return_value=None):
            probe = adapter.discover()
        self.assertTrue(probe.available)
        self.assertIsNone(probe.version)
        self.assertEqual(probe.executable, "/usr/bin/qemu-system-i386")

    def test_qemu_reports_only_the_capabilities_it_has_built(self):
        report = qemu_module.QemuAdapter().capabilities()
        self.assertEqual(report.control_planes, ("agentless-display",))
        self.assertEqual(report.controllers, ("ide",))
        self.assertTrue(report.vvfat)
        self.assertIn("floppy", report.media)


class _ExitedProcess:
    """A server that gave up, and what it said on the way out."""

    def __init__(self, complaint):
        self.returncode = 1
        self.stdout = None
        self.stderr = io.StringIO(complaint)

    def poll(self):
        return self.returncode

    def terminate(self):
        pass

    def wait(self, timeout=None):
        return self.returncode

    def kill(self):
        pass


class AtRestAccessTests(unittest.TestCase):
    """Opening a stopped machine's disk, short of launching a server.

    The served path itself needs ``qemu-nbd``, which no unit test
    launches. What *is* reachable here is every refusal around it —
    and those are what a caller acts on.
    """

    def setUp(self):
        self.workdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.workdir.cleanup)
        self.adapter = qemu_module.QemuAdapter()

    def _image(self, name="disk.img", payload=b""):
        path = os.path.join(self.workdir.name, name)
        with open(path, "wb") as handle:
            handle.write(payload or fat_image.volume({"A.TXT": b"a"}))
        return path

    def _as_format(self, found):
        return mock.patch.object(qemu_module, "probe_image_format",
                                 lambda _path: found)

    def test_a_format_that_is_neither_qcow2_nor_raw_is_refused(self):
        """Serving an untested format would be claiming a capability
        nobody exercised, which P11 makes a refusal."""
        path = self._image("payload.vmdk")
        for found in ("vmdk", "vdi", "vhdx", "vpc"):
            with self.subTest(format=found):
                with self._as_format(found):
                    with self.assertRaises(PreflightError) as caught:
                        self.adapter.open_drive(path)
                self.assertEqual(caught.exception.rule_id,
                                 "image.format-not-at-rest")
                self.assertIn(found, str(caught.exception))

    def test_a_raw_image_is_read_where_it_lies(self):
        path = self._image()
        before = os.path.getsize(path)
        with self._as_format("raw"):
            access = self.adapter.open_drive(path)
        self.addCleanup(access.close)
        self.assertEqual(access.device.size, before)
        self.assertEqual(access.device.read_at(510, 2), b"\x55\xaa")

    def test_a_raw_write_is_staged_and_lands_only_on_commit(self):
        path = self._image()
        with self._as_format("raw"):
            access = self.adapter.open_drive(path, writable=True)
        access.device.write_at(0x2000, b"STAGED")
        with open(path, "rb") as handle:
            handle.seek(0x2000)
            self.assertNotEqual(handle.read(6), b"STAGED")
        access.commit()
        access.close()
        with open(path, "rb") as handle:
            handle.seek(0x2000)
            self.assertEqual(handle.read(6), b"STAGED")

    def test_a_raw_write_closed_without_committing_never_lands(self):
        path = self._image()
        with self._as_format("raw"):
            access = self.adapter.open_drive(path, writable=True)
        access.device.write_at(0x2000, b"GHOST")
        access.close()
        with open(path, "rb") as handle:
            handle.seek(0x2000)
            self.assertNotEqual(handle.read(5), b"GHOST")

    def test_an_image_another_caller_holds_is_refused_by_name(self):
        path = self._image()
        with self._as_format("raw"):
            held = self.adapter.open_drive(path, writable=True)
            self.addCleanup(held.close)
            with self.assertRaises(PreflightError) as caught:
                self.adapter.open_drive(path, writable=True)
        self.assertEqual(caught.exception.rule_id, "image.locked")

    def test_a_server_refusing_the_lock_reads_as_contention(self):
        """QEMU leaves the same exit status behind for every startup
        failure, so its wording is what separates them."""
        path = self._image("disk.qcow2")
        complaint = ('qemu-nbd: Failed to get "write" lock\n'
                     "Is another process using the image?")
        with self._as_format("qcow2"), \
                mock.patch.object(qemu_module, "find_qemu_nbd",
                                  lambda: "qemu-nbd"), \
                mock.patch.object(qemu_module.subprocess, "Popen",
                                  lambda *a, **k: _ExitedProcess(complaint)):
            with self.assertRaises(PreflightError) as caught:
                self.adapter.open_drive(path)
        self.assertEqual(caught.exception.rule_id, "image.locked")

    def test_a_server_failing_for_any_other_reason_says_so(self):
        path = self._image("disk.qcow2")
        with self._as_format("qcow2"), \
                mock.patch.object(qemu_module, "find_qemu_nbd",
                                  lambda: "qemu-nbd"), \
                mock.patch.object(
                    qemu_module.subprocess, "Popen",
                    lambda *a, **k: _ExitedProcess("no such format")):
            with self.assertRaises(RunFailure) as caught:
                self.adapter.open_drive(path)
        self.assertEqual(caught.exception.rule_id, "image.serve-failed")

    def test_a_failed_open_leaves_no_lock_behind(self):
        """A refusal that kept the claim would make the disk
        unopenable for the rest of the process."""
        path = self._image("disk.qcow2")
        with self._as_format("qcow2"), \
                mock.patch.object(qemu_module, "find_qemu_nbd",
                                  lambda: "qemu-nbd"), \
                mock.patch.object(
                    qemu_module.subprocess, "Popen",
                    lambda *a, **k: _ExitedProcess("no such format")):
            with self.assertRaises(RunFailure):
                self.adapter.open_drive(path)
        with self._as_format("raw"):
            access = self.adapter.open_drive(path)
        self.addCleanup(access.close)
        self.assertTrue(access.device.size)


class PackageSurfaceTests(unittest.TestCase):
    def test_the_package_root_exposes_the_seam_and_not_the_backend(self):
        # The adapter API is an internal engineering contract, not one
        # of the world-facing interfaces: the seam's own vocabulary is
        # importable, QEMU's helpers are not.
        self.assertIsInstance(reliquary.adapter("qemu"),
                              qemu_module.QemuAdapter)
        for gone in ("find_qemu", "find_qemu_img", "create_hdd_image",
                     "Qmp", "stop", "machine_drive_args"):
            with self.subTest(name=gone):
                self.assertNotIn(gone, reliquary.__all__)


if __name__ == "__main__":
    unittest.main()
