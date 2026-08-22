# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Installed tests for the QEMU adapter: ownership, images, rendering.

Everything below the adapter seam that **only QEMU knows** — the owned
launch and its identity verification, qcow2 materialization, the drive
and boot rendering a machine's state lowers into, and the carriers a
session exposes. What every adapter owes the seam alike — the name, the
capability report, the image extension, discovery, the host font, and
the refusal to command an unverified VM — is `test_backend_contract`,
driven against this backend and VirtualBox from one text (F59).
"""

import inspect
import os
import sys
import types
import uuid
from unittest import mock

import pytest

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
    vnc_service = None

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
        if name == "query-vnc":
            if self.vnc_service is None:
                return {"enabled": False}
            return {"enabled": True, "host": "127.0.0.1",
                    "service": self.vnc_service}
        return None


def _identity(port=54321, name="reliquary-machine",
              token="00000000-0000-0000-0000-000000000000"):
    return {"backend": "qemu", "backend-id": name, "token": token,
            "endpoint": {"port": port}, "pid": 1234}


@pytest.fixture
def fake_qmp():
    """The scripted monitor, reset to a matching identity."""
    _FakeQmp.commands = []
    _FakeQmp.name = "reliquary-machine"
    _FakeQmp.vm_uuid = "00000000-0000-0000-0000-000000000000"
    _FakeQmp.vnc_service = None
    return _FakeQmp


@pytest.fixture
def root(tmp_path):
    return str(tmp_path)


# VM ownership guarantees over ``launch_owned_qemu`` and ``stop``.

def test_launch_returns_the_generic_verified_identity(fake_qmp, root):
    proc = _FakeProcess()
    with mock.patch.object(qemu_module, "available_port",
                           return_value=54321), \
            mock.patch.object(qemu_module, "port_in_use",
                              return_value=False), \
            mock.patch.object(qemu_module.uuid, "uuid4",
                              return_value=uuid.UUID(int=0)), \
            mock.patch.object(qemu_module, "Qmp", fake_qmp), \
            mock.patch.object(qemu_module.subprocess, "Popen",
                              return_value=proc) as popen:
        identity = qemu_module.launch_owned_qemu(
            ["qemu", "-name", "reliquary-machine"],
            vm_name="reliquary-machine", log_dir=root)

    # The adapter owns no state: it returns the identity for the
    # machine model to persist, in the shape every backend records
    # — only the endpoint inside it is QEMU's own.
    assert identity == {
        "backend": "qemu",
        "backend-id": "reliquary-machine",
        "token": "00000000-0000-0000-0000-000000000000",
        "endpoint": {"port": 54321},
        "pid": 1234,
    }
    args = popen.call_args.args[0]
    assert args[args.index("-name") + 1] == "reliquary-machine"
    assert args[args.index("-uuid") + 1] == (
        "00000000-0000-0000-0000-000000000000")


def test_launch_rejects_explicit_occupied_port_before_launch():
    with mock.patch.object(qemu_module, "port_in_use", return_value=True):
        with pytest.raises(PreflightError, match="explicit"):
            qemu_module.launch_owned_qemu(
                ["qemu", "-name", "reliquary-machine"],
                vm_name="reliquary-machine", port=54321)


def test_launch_terminates_child_on_identity_mismatch(fake_qmp, root):
    proc = _FakeProcess()
    fake_qmp.name = "unrelated-vm"
    with mock.patch.object(qemu_module, "available_port",
                           return_value=54321), \
            mock.patch.object(qemu_module, "port_in_use",
                              return_value=False), \
            mock.patch.object(qemu_module.uuid, "uuid4",
                              return_value=uuid.UUID(int=0)), \
            mock.patch.object(qemu_module, "Qmp", fake_qmp), \
            mock.patch.object(qemu_module.subprocess, "Popen",
                              return_value=proc):
        with pytest.raises(PreflightError, match="identity mismatch"):
            qemu_module.launch_owned_qemu(
                ["qemu", "-name", "reliquary-machine"],
                vm_name="reliquary-machine", log_dir=root)

    assert proc.terminated


def test_stop_does_not_quit_same_named_vm_of_another_home(fake_qmp):
    # two homes materialize same-numbered machines with the same
    # readable backend-id; only the per-start token tells their VMs
    # apart, so a name match alone must never authorize quit
    fake_qmp.name = "reliquary-machine"
    fake_qmp.vm_uuid = "22222222-2222-2222-2222-222222222222"

    with mock.patch.object(qemu_module, "Qmp", fake_qmp):
        with pytest.raises(PreflightError, match="identity mismatch"):
            qemu_module.stop(_identity(
                token="11111111-1111-1111-1111-111111111111"))

    assert "quit" not in fake_qmp.commands


def test_a_session_verifies_before_it_yields_a_carrier(fake_qmp):
    adapter = qemu_module.QemuAdapter()
    fake_qmp.name = "unrelated-vm"
    with mock.patch.object(qemu_module, "Qmp", fake_qmp):
        with pytest.raises(PreflightError, match="identity mismatch"):
            with adapter.session(_identity()):
                pass


def test_a_vm_record_with_no_usable_endpoint_fails_closed():
    adapter = qemu_module.QemuAdapter()
    broken = dict(_identity(), endpoint={"socket": "/tmp/x"})
    with pytest.raises(PreflightError, match="usable QMP port"):
        with adapter.session(broken):
            pass


# ``Qmp`` owns the event loop it creates for the QMP connection.

def test_connect_failure_closes_the_loop():
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

    with mock.patch.object(qemu_module, "QMPClient", _FailingClient), \
            mock.patch.object(qemu_module.asyncio, "new_event_loop",
                              _tracking_new_event_loop):
        with pytest.raises(ConnectionRefusedError):
            qemu_module.Qmp(1234)

    assert len(created_loops) == 1
    assert created_loops[0].is_closed()


# qcow2 materialization.

def _run_create(filename, capacity, *, returncode=0, stderr=""):
    completed = mock.Mock(returncode=returncode, stdout="", stderr=stderr)
    with mock.patch.object(qemu_module, "find_qemu_img",
                           return_value="qemu-img"), \
            mock.patch.object(qemu_module.subprocess, "run",
                              return_value=completed) as run:
        path = qemu_module.create_hdd_image(filename, capacity)
    return path, run


def test_creates_sparse_qcow2_v3_image(root):
    filename = os.path.join(root, "drives", "hdd.qcow2")

    path, run = _run_create(filename, "2G")

    assert path == os.path.abspath(filename)
    assert run.call_args.args[0] == [
        "qemu-img", "create", "-f", "qcow2",
        "-o", "compat=1.1,preallocation=off",
        os.path.abspath(filename), "2G"]
    assert os.path.isdir(os.path.dirname(path))


def test_integer_capacity_is_mib(root):
    filename = os.path.join(root, "disk.qcow2")

    _, run = _run_create(filename, 512)

    assert run.call_args.args[0][-1] == "512M"


def test_rejects_non_qcow2_filename(root):
    with pytest.raises(StaticError, match=r"\.qcow2"):
        qemu_module.create_hdd_image(os.path.join(root, "hdd.img"), "1G")


def test_rejects_existing_image(root):
    filename = os.path.join(root, "hdd.qcow2")
    with open(filename, "wb") as handle:
        handle.write(b"x")

    with pytest.raises(PreflightError):
        qemu_module.create_hdd_image(filename, "1G")


def test_rejects_non_positive_mib_capacity(root):
    filename = os.path.join(root, "hdd.qcow2")
    with pytest.raises(StaticError, match="positive"):
        qemu_module.create_hdd_image(filename, 0)


def test_surfaces_qemu_img_failure(root):
    filename = os.path.join(root, "hdd.qcow2")
    with pytest.raises(RunFailure, match="qemu-img failed"):
        _run_create(filename, "1G", returncode=1, stderr="boom")


def test_the_adapter_routes_each_materialize_mode():
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


# Reliquary drive vocabulary in, QEMU configuration out.

def _drive_values(args):
    return [args[i + 1] for i, a in enumerate(args) if a == "-drive"]


def _image(root, name):
    path = os.path.join(root, name)
    with open(path, "wb") as handle:
        handle.write(b"IMAGE")
    return path


def test_floppies_render_before_hard_disks(root):
    drives = {
        "hdd0": {"medium": "hdd", "slot": 0,
                 "path": _image(root, "blank.qcow2")},
        "floppy0": {"medium": "floppy", "slot": 0,
                    "path": _image(root, "boot.img")},
    }
    values = _drive_values(qemu_module.drive_args(drives))
    floppy = next(i for i, v in enumerate(values) if "if=floppy" in v)
    hdd = next(i for i, v in enumerate(values) if "if=ide,index=0" in v)
    assert floppy < hdd


def test_a_cdrom_takes_the_ide_slot_after_the_last_disk(root):
    drives = {
        "hdd0": {"medium": "hdd", "slot": 0,
                 "path": _image(root, "blank.qcow2")},
        "cdrom0": {"medium": "cdrom", "slot": 0,
                   "path": _image(root, "live.iso")},
    }
    cdrom = [v for v in _drive_values(qemu_module.drive_args(drives))
             if "media=cdrom" in v]
    assert len(cdrom) == 1
    # An .iso is pinned to raw rather than probed.
    assert "format=raw," in cdrom[0]
    assert "if=ide,index=1" in cdrom[0]


def test_every_drive_carries_its_slot_key_as_its_id(root):
    # Floppies and cdroms always did, for a live insert/eject; a hard
    # disk now does too, because the slot key is how the settings
    # hatch addresses one drive's options — `-set drive.hdd0.…` (D118)
    drives = {
        "hdd0": {"medium": "hdd", "slot": 0,
                 "path": _image(root, "blank.qcow2")},
        "floppy0": {"medium": "floppy", "slot": 0, "path": None},
        "cdrom0": {"medium": "cdrom", "slot": 0, "path": None},
    }
    values = _drive_values(qemu_module.drive_args(drives))
    for key in drives:
        assert any(v.endswith(f"id={key}") for v in values), key


def test_an_empty_removable_slot_renders_a_medium_less_drive():
    drives = {"cdrom0": {"medium": "cdrom", "slot": 0, "path": None}}
    assert _drive_values(qemu_module.drive_args(drives)) == [
        "media=cdrom,if=ide,index=0,id=cdrom0"]


def test_a_host_directory_renders_as_vvfat(root):
    # The one capability only knowable after resolution, so it is
    # judged here rather than at assignment.
    work = os.path.join(root, "work")
    os.makedirs(work)
    drives = {"hdd0": {"medium": "hdd", "slot": 0, "path": work}}
    values = _drive_values(qemu_module.drive_args(drives))
    assert any("fat:rw:" in value for value in values)


def test_a_removable_drive_carries_its_key_as_the_launch_id(root):
    drives = {"floppy0": {"medium": "floppy", "slot": 0,
                          "path": _image(root, "boot.img")}}
    values = _drive_values(qemu_module.drive_args(drives))
    assert "id=floppy0" in values[0]


def test_the_boot_order_becomes_firmware_letters():
    drives = {"hdd0": {"medium": "hdd", "slot": 0, "path": None},
              "cdrom0": {"medium": "cdrom", "slot": 0, "path": None}}
    assert qemu_module._boot_order(["cdrom0", "hdd0"], drives) == "dc"
    assert qemu_module._boot_order(["hdd0", "cdrom0"], drives) == "cd"


def test_start_renders_the_state_and_launches_it(root):
    adapter = qemu_module.QemuAdapter()
    state = {
        "id": "plain-0", "backend-id": "reliquary-plain-0",
        "memory": 32, "boot": ["cdrom0"],
        "drives": {"cdrom0": {"medium": "cdrom", "slot": 0,
                              "path": _image(root, "live.iso")}},
    }
    with mock.patch.object(qemu_module, "find_qemu",
                           return_value="qemu-system-i386"), \
            mock.patch.object(qemu_module, "launch_owned_qemu") as launch:
        adapter.start(state, machine_dir=root,
                      backend_dir=os.path.join(root, "qemu"))
    args = launch.call_args.args[0]
    assert args[0] == "qemu-system-i386"
    assert args[args.index("-m") + 1] == "32"
    assert "order=d" in args
    assert launch.call_args.kwargs["vm_name"] == "reliquary-plain-0"
    assert launch.call_args.kwargs["log_dir"] == os.path.join(root, "qemu")


# The escape hatch: honored, bounded, and never a second source.
#
# One function validates and renders, so every assertion here is about
# both at once — what `create` accepts is what `start` puts on the
# command line.

def test_the_documented_keys_render():
    assert qemu_module.settings_args(
        {"machine": "pc", "args": ["-cpu", "486"]}) == [
        "-machine", "pc", "-cpu", "486"]


@pytest.mark.parametrize("section", [None, {}, {"args": []}],
                         ids=["absent", "empty", "no-arguments"])
def test_an_absent_or_empty_section_renders_nothing(section):
    assert qemu_module.settings_args(section) == []


def test_a_key_qemu_does_not_define_is_refused():
    with pytest.raises(StaticError) as caught:
        qemu_module.settings_args({"cpus": 2})
    assert caught.value.rule_id == "machine.settings-unknown-key"
    assert "machine, args" in str(caught.value)


@pytest.mark.parametrize("section,rule", [
    ({"machine": ""}, "value.not-a-string"),
    ({"machine": 42}, "value.not-a-string"),
    ({"args": "-cpu 486"}, "value.not-an-array"),
    ({"args": [486]}, "value.not-a-string"),
], ids=["empty-machine", "machine-not-a-string", "args-not-an-array",
        "argument-not-a-string"])
def test_the_key_shapes_are_checked(section, rule):
    with pytest.raises(StaticError) as caught:
        qemu_module.settings_args(section)
    assert caught.value.rule_id == rule


#: Every argument a blueprint field or the VM identity owns, and its
#: owner. One node per argument: an entry that stopped being refused
#: is a named failure rather than a loop nobody counts.
_OWNED_ARGUMENTS = {
    "-m": "memory", "-smp": "cpus", "-boot": "boot",
    "-drive": "drives", "-hda": "drives", "-fda": "drives",
    "-cdrom": "drives", "-machine": "machine", "-M": "machine",
    "-name": "identity", "-uuid": "identity",
    "-qmp": "control channel", "-display": "display",
    "-nographic": "display",
}


@pytest.mark.parametrize("argument,owner", sorted(_OWNED_ARGUMENTS.items()))
def test_every_reliquary_owned_argument_is_refused_by_its_owner(argument,
                                                                owner):
    with pytest.raises(StaticError) as caught:
        qemu_module.settings_args({"args": [argument, "x"]})
    assert caught.value.rule_id == "machine.settings-reserved-argument"
    assert owner in str(caught.value)


def test_an_option_and_its_value_in_one_element_is_still_caught():
    # `["-m 64"]` is not two arguments and QEMU would refuse it
    # anyway; refusing it here names the actual mistake.
    with pytest.raises(StaticError) as caught:
        qemu_module.settings_args({"args": ["-m 64"]})
    assert caught.value.rule_id == "machine.settings-reserved-argument"


@pytest.mark.parametrize("args", [
    ["-set", "drive.hdd0.cache=none"],
    ["-set drive.hdd0.cache=none"],
    ["-set", "drive.cdrom0.serial=RLQ1"],
    ["-set", "device.x.foo=1"],
], ids=["two-elements", "one-element", "cdrom-serial", "other-group"])
def test_a_per_drive_option_reaches_a_drive_through_set(args):
    # The machine-scoped hatch addresses one drive through QEMU's own
    # `-set drive.<slot>.<property>` — which is why a drive-scoped
    # section was declined (D118)
    assert qemu_module.settings_args({"args": args}) == args


@pytest.mark.parametrize("target", [
    "drive.hdd0.file=C:\\other.img",
    "drive.hdd0.if=scsi",
    "drive.cdrom0.media=disk",
    "drive.hdd0.index=3",
    "drive.floppy0.id=x",
], ids=["file", "if", "media", "index", "id"])
def test_set_on_a_rendered_drive_property_is_refused_naming_drives(target):
    # `-drive` is refused because `drives` renders it; `-set` reaching
    # the same property is the same second source for one fact
    for args in (["-set", target], [f"-set {target}"]):
        with pytest.raises(StaticError) as caught:
            qemu_module.settings_args({"args": args})
        assert caught.value.rule_id == "machine.settings-reserved-argument"
        assert "drives" in str(caught.value)


def test_the_hatch_still_passes_a_device_and_a_cpu_model():
    # The two the reserved set must NOT catch. `-device` is the
    # documented route to a device the curated vocabulary does not
    # name yet (D91), and `-cpu` selects a model where `cpus` owns
    # only the count — the cookbook's own 486 recipe.
    assert qemu_module.settings_args(
        {"args": ["-device", "virtio-net-pci", "-cpu", "486"]}) == [
        "-device", "virtio-net-pci", "-cpu", "486"]


def test_a_value_that_merely_looks_like_an_option_passes():
    assert qemu_module.settings_args(
        {"args": ["-cpu", "486", "-vga", "std"]}) == [
        "-cpu", "486", "-vga", "std"]


def test_validate_settings_is_the_renderer_and_returns_nothing():
    adapter = qemu_module.QemuAdapter()
    assert adapter.settings_keys == ("machine", "args")
    assert adapter.validate_settings({"machine": "pc"}) is None
    with pytest.raises(StaticError):
        adapter.validate_settings({"args": ["-boot", "d"]})


def test_start_renders_this_backends_section_last():
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
    assert args[-4:] == ["-machine", "pc", "-cpu", "486"]
    assert "nonsense" not in args


# The session's carriers, over a scripted monitor.

def test_the_text_screen_reads_characters_and_attribute_tokens():
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

    assert rows[0] == "A:\\>"
    assert attributes[0][:5] == [0x70] * 4 + [0x07]
    assert len(attributes) == 25
    assert all(len(row) == 80 for row in attributes)
    qmp.hmp.assert_called_once_with("xp /4000bx 0xb8000")


def test_key_names_reach_qmp_as_qcode_events():
    qmp = mock.Mock()
    with mock.patch.object(qemu_module.time, "sleep"):
        qemu_module.QemuSession(qmp).send_keys([["shift", "a"]])
    qmp.cmd.assert_called_once_with(
        "send-key",
        keys=[{"type": "qcode", "data": "shift"},
              {"type": "qcode", "data": "a"}])


def test_a_medium_change_targets_the_drive_by_key():
    qmp = mock.Mock()
    session = qemu_module.QemuSession(qmp)
    session.change_medium("cdrom0", "C:\\images\\live.iso")
    session.change_medium("cdrom0")
    lines = [call.args[0] for call in qmp.hmp.call_args_list]
    assert lines[0] == "change cdrom0 C:/images/live.iso raw"
    assert lines[1] == "eject cdrom0"


def test_screenshot_requests_a_png():
    qmp = mock.Mock()
    written = qemu_module.QemuSession(qmp).screenshot("C:\\shots\\a.png")
    qmp.cmd.assert_called_once_with(
        "screendump", filename="C:/shots/a.png", format="png")
    assert written == "C:\\shots\\a.png"


def test_screenshot_converts_a_legacy_ppm(root):
    class UnsupportedPngError(Exception):
        pass

    png = os.path.join(root, "legacy.png")
    ppm = os.path.join(root, "legacy.ppm")

    def screendump(command, **arguments):
        assert command == "screendump"
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

    assert not os.path.exists(ppm)
    with open(png, "rb") as image:
        assert image.read(8) == b"\x89PNG\r\n\x1a\n"


def test_the_native_seam_hands_back_the_monitor_itself():
    qmp = mock.Mock()
    assert qemu_module.QemuSession(qmp).native() is qmp


def test_the_session_ignores_the_cache_it_is_offered():
    """QEMU needs no host font, so the argument is accepted and unused."""
    assert "cache" in inspect.signature(
        qemu_module.QemuAdapter.session).parameters


def test_a_binary_that_will_not_report_a_version_is_still_available():
    """QEMU's probe asks the binary for a version; absence is not fatal."""
    adapter = qemu_module.QemuAdapter()
    with mock.patch.object(qemu_module, "find_qemu",
                           return_value="/usr/bin/qemu-system-i386"), \
            mock.patch.object(qemu_module, "_qemu_version",
                              return_value=None):
        probe = adapter.discover()
    assert probe.available
    assert probe.version is None
    assert probe.executable == "/usr/bin/qemu-system-i386"


# The VNC plane (F63): the launch contribution, the endpoint record,
# and the carriers behind the same seam.

class _FakeRfb:
    """A scripted RFB client standing where the socket one would."""

    def __init__(self, image=None):
        self.events = []
        self.refreshed = 0
        self.closed = False
        self._image = image

    def key_event(self, keysym, down):
        self.events.append((keysym, down))

    def refresh(self, incremental=False):
        self.refreshed += 1

    def image(self):
        return self._image

    def close(self):
        self.closed = True


def _vnc_identity(plane="vnc", vnc_port=5901):
    identity = _identity()
    identity["endpoint"]["vnc-port"] = vnc_port
    if plane is not None:
        identity["endpoint"]["plane"] = plane
    return identity


def test_launch_serves_vnc_and_records_the_endpoint(fake_qmp, root):
    proc = _FakeProcess()
    fake_qmp.vnc_service = "5901"
    with mock.patch.object(qemu_module, "available_port",
                           side_effect=[54321, 5901]), \
            mock.patch.object(qemu_module, "port_in_use",
                              return_value=False), \
            mock.patch.object(qemu_module.uuid, "uuid4",
                              return_value=uuid.UUID(int=0)), \
            mock.patch.object(qemu_module, "Qmp", fake_qmp), \
            mock.patch.object(qemu_module.rfb, "probe") as probe, \
            mock.patch.object(qemu_module.subprocess, "Popen",
                              return_value=proc) as popen:
        identity = qemu_module.launch_owned_qemu(
            ["qemu", "-name", "reliquary-machine"],
            vm_name="reliquary-machine", log_dir=root, vnc=True)

    args = popen.call_args.args[0]
    # QEMU takes a display number; the endpoint records the port.
    assert args[args.index("-vnc") + 1] == "127.0.0.1:1"
    assert identity["endpoint"] == {"port": 54321, "vnc-port": 5901}
    assert "query-vnc" in fake_qmp.commands
    probe.assert_called_once_with("127.0.0.1", 5901)


def test_launch_without_vnc_neither_serves_nor_probes_it(fake_qmp, root):
    proc = _FakeProcess()
    with mock.patch.object(qemu_module, "available_port",
                           return_value=54321), \
            mock.patch.object(qemu_module, "port_in_use",
                              return_value=False), \
            mock.patch.object(qemu_module.uuid, "uuid4",
                              return_value=uuid.UUID(int=0)), \
            mock.patch.object(qemu_module, "Qmp", fake_qmp), \
            mock.patch.object(qemu_module.rfb, "probe") as probe, \
            mock.patch.object(qemu_module.subprocess, "Popen",
                              return_value=proc) as popen:
        identity = qemu_module.launch_owned_qemu(
            ["qemu", "-name", "reliquary-machine"],
            vm_name="reliquary-machine", log_dir=root)

    assert "-vnc" not in popen.call_args.args[0]
    assert identity["endpoint"] == {"port": 54321}
    assert "query-vnc" not in fake_qmp.commands
    probe.assert_not_called()


def test_launch_terminates_child_on_a_vnc_endpoint_mismatch(fake_qmp,
                                                            root):
    proc = _FakeProcess()
    fake_qmp.vnc_service = "5999"  # this QEMU serves VNC elsewhere
    with mock.patch.object(qemu_module, "available_port",
                           side_effect=[54321, 5901]), \
            mock.patch.object(qemu_module, "port_in_use",
                              return_value=False), \
            mock.patch.object(qemu_module.uuid, "uuid4",
                              return_value=uuid.UUID(int=0)), \
            mock.patch.object(qemu_module, "Qmp", fake_qmp), \
            mock.patch.object(qemu_module.subprocess, "Popen",
                              return_value=proc):
        with pytest.raises(PreflightError) as caught:
            qemu_module.launch_owned_qemu(
                ["qemu", "-name", "reliquary-machine"],
                vm_name="reliquary-machine", log_dir=root, vnc=True)

    assert caught.value.rule_id == "machine.vnc-endpoint-mismatch"
    assert "127.0.0.1:5901" in str(caught.value)
    assert proc.terminated


def test_launch_terminates_child_when_vnc_never_answers(fake_qmp, root):
    proc = _FakeProcess()
    fake_qmp.vnc_service = "5901"
    with mock.patch.object(qemu_module, "available_port",
                           side_effect=[54321, 5901]), \
            mock.patch.object(qemu_module, "port_in_use",
                              return_value=False), \
            mock.patch.object(qemu_module.uuid, "uuid4",
                              return_value=uuid.UUID(int=0)), \
            mock.patch.object(qemu_module, "Qmp", fake_qmp), \
            mock.patch.object(qemu_module.rfb, "probe",
                              side_effect=OSError("refused")), \
            mock.patch.object(qemu_module.time, "sleep"), \
            mock.patch.object(qemu_module.time, "monotonic",
                              side_effect=[0, 10, 20]), \
            mock.patch.object(qemu_module.subprocess, "Popen",
                              return_value=proc):
        with pytest.raises(RunFailure) as caught:
            qemu_module.launch_owned_qemu(
                ["qemu", "-name", "reliquary-machine"],
                vm_name="reliquary-machine", log_dir=root, vnc=True)

    assert "127.0.0.1:5901" in str(caught.value)
    assert proc.terminated


@pytest.mark.parametrize("planes,vnc,plane_recorded", [
    (["vnc"], True, True),
    (["vnc", "agentless-display"], True, True),
    (["agentless-display", "vnc"], True, False),
    (["agentless-display"], False, False),
    (None, False, False),
], ids=["vnc-first", "vnc-then-agentless", "agentless-then-vnc",
        "agentless-only", "defaulted"])
def test_start_serves_vnc_when_named_and_the_first_plane_drives(
        planes, vnc, plane_recorded, root):
    """The resolved policy reaches the launch and the endpoint.

    A named plane is served; the *first* one drives the session's
    carriers, recorded in the endpoint beside the ports — and the
    default plane needs no record.
    """
    adapter = qemu_module.QemuAdapter()
    state = {"id": "plain-0", "backend-id": "reliquary-plain-0",
             "memory": 32, "boot": [], "drives": {}}
    if planes is not None:
        state["control-planes"] = planes
    launched = {"backend": "qemu", "backend-id": "reliquary-plain-0",
                "token": "t", "endpoint": {"port": 54321}}
    if vnc:
        launched["endpoint"]["vnc-port"] = 5901
    with mock.patch.object(qemu_module, "find_qemu",
                           return_value="qemu-system-i386"), \
            mock.patch.object(qemu_module, "launch_owned_qemu",
                              return_value=launched) as launch:
        identity = adapter.start(state, machine_dir=root,
                                 backend_dir=os.path.join(root, "qemu"))
    assert launch.call_args.kwargs["vnc"] is vnc
    assert identity["endpoint"].get("plane") == (
        "vnc" if plane_recorded else None)


def test_a_session_serves_the_recorded_driving_plane(fake_qmp):
    adapter = qemu_module.QemuAdapter()
    fake_qmp.vnc_service = "5901"
    client = _FakeRfb()
    with mock.patch.object(qemu_module, "Qmp", fake_qmp), \
            mock.patch.object(qemu_module.rfb, "RfbClient",
                              return_value=client) as connect:
        with adapter.session(_vnc_identity(), cache="cache") as session:
            assert isinstance(session, qemu_module.QemuVncSession)
            assert session.recognizes_text is True
    connect.assert_called_once_with("127.0.0.1", 5901)
    assert "query-vnc" in fake_qmp.commands
    assert client.closed


def test_a_session_without_a_recorded_plane_stays_agentless(fake_qmp):
    adapter = qemu_module.QemuAdapter()
    with mock.patch.object(qemu_module, "Qmp", fake_qmp), \
            mock.patch.object(qemu_module.rfb, "RfbClient") as connect:
        with adapter.session(_vnc_identity(plane=None)) as session:
            assert type(session) is qemu_module.QemuSession
    connect.assert_not_called()


def test_a_vnc_session_still_verifies_identity_first(fake_qmp):
    """A VNC connection never authorizes a command: QMP verifies
    before the RFB socket is even opened."""
    adapter = qemu_module.QemuAdapter()
    fake_qmp.name = "unrelated-vm"
    with mock.patch.object(qemu_module, "Qmp", fake_qmp), \
            mock.patch.object(qemu_module.rfb, "RfbClient") as connect:
        with pytest.raises(PreflightError, match="identity mismatch"):
            with adapter.session(_vnc_identity()):
                pass
    connect.assert_not_called()


def test_a_session_refuses_a_moved_vnc_endpoint(fake_qmp):
    adapter = qemu_module.QemuAdapter()
    fake_qmp.vnc_service = "5999"
    with mock.patch.object(qemu_module, "Qmp", fake_qmp), \
            mock.patch.object(qemu_module.rfb, "RfbClient") as connect:
        with pytest.raises(PreflightError) as caught:
            with adapter.session(_vnc_identity()):
                pass
    assert caught.value.rule_id == "machine.vnc-endpoint-mismatch"
    connect.assert_not_called()


def test_a_vnc_plane_without_a_recorded_port_fails_closed(fake_qmp):
    adapter = qemu_module.QemuAdapter()
    identity = _identity()
    identity["endpoint"]["plane"] = "vnc"
    with mock.patch.object(qemu_module, "Qmp", fake_qmp):
        with pytest.raises(PreflightError) as caught:
            with adapter.session(identity):
                pass
    assert caught.value.rule_id == "machine.endpoint-invalid"


def test_an_unknown_recorded_plane_fails_closed():
    adapter = qemu_module.QemuAdapter()
    identity = _identity()
    identity["endpoint"]["plane"] = "serial-console"
    with pytest.raises(PreflightError) as caught:
        with adapter.session(identity):
            pass
    assert caught.value.rule_id == "machine.endpoint-invalid"


def test_an_unreachable_vnc_endpoint_names_itself(fake_qmp):
    adapter = qemu_module.QemuAdapter()
    fake_qmp.vnc_service = "5901"
    with mock.patch.object(qemu_module, "Qmp", fake_qmp), \
            mock.patch.object(qemu_module.rfb, "RfbClient",
                              side_effect=ConnectionRefusedError()):
        with pytest.raises(PreflightError) as caught:
            with adapter.session(_vnc_identity()):
                pass
    assert caught.value.rule_id == "machine.vnc-unreachable"
    assert "127.0.0.1:5901" in str(caught.value)


# The VNC carriers, over scripted RFB and QMP doubles.

def test_vnc_keys_go_down_in_order_and_up_in_reverse():
    client = _FakeRfb()
    session = qemu_module.QemuVncSession(mock.Mock(), client)
    with mock.patch.object(qemu_module.time, "sleep"):
        session.send_keys([["shift", "a"]])
    shift, a = 0xffe1, ord("a")
    assert client.events == [(shift, True), (a, True),
                             (a, False), (shift, False)]


def test_the_keysym_table_covers_the_seam_vocabulary():
    """Every seam key VirtualBox translates, the VNC plane translates.

    The two adapters own D103's third layer each; this is what keeps
    them covering the same seam names rather than drifting apart one
    key at a time.
    """
    from reliquary import backend_virtualbox as vbox
    for name in vbox._SCANCODES:
        assert isinstance(qemu_module.keysym_for(name), int)


@pytest.mark.parametrize("wrong", ["enter", "space"])
def test_a_language_key_name_is_not_a_seam_key_name(wrong):
    # The seam speaks qcodes (`ret`, `spc`); the language's portable
    # names never reach it (D103).
    with pytest.raises(StaticError) as caught:
        qemu_module.keysym_for(wrong)
    assert caught.value.rule_id == "key.no-mapping"


def test_the_vnc_text_screen_recognizes_through_the_hosts_fonts():
    from reliquary import text_recognize
    rows = ["C:\\>", "", "Welcome to FreeDOS"]
    client = _FakeRfb(image=text_recognize.render(rows))
    session = qemu_module.QemuVncSession(mock.Mock(), client,
                                         cache="cache-root")
    with mock.patch.object(
            qemu_module, "guest_glyph_banks",
            return_value=(text_recognize.glyph_bank(),)) as banks:
        screen = session.text_screen()
    banks.assert_called_once_with("cache-root")
    assert client.refreshed == 1
    assert screen[0][:3] == rows
    assert screen.fonts_tried == ("host",)


def test_the_vnc_screenshot_writes_the_framebuffer_as_png(root):
    from PIL import Image
    client = _FakeRfb(image=Image.new("RGB", (4, 2), (7, 8, 9)))
    session = qemu_module.QemuVncSession(mock.Mock(), client)
    png = os.path.join(root, "shots", "a.png")
    written = session.screenshot(png)
    assert written == png
    assert client.refreshed == 1
    with Image.open(png) as image:
        assert image.size == (4, 2)
        assert image.getpixel((0, 0)) == (7, 8, 9)


def test_the_vnc_session_moves_media_over_qmp():
    """`change_medium` is a machine operation and stays on the
    management interface whatever plane drives the screen."""
    qmp = mock.Mock()
    client = _FakeRfb()
    session = qemu_module.QemuVncSession(qmp, client)
    session.change_medium("cdrom0", "C:\\images\\live.iso")
    assert qmp.hmp.call_args.args[0] == (
        "change cdrom0 C:/images/live.iso raw")
    assert session.native() is qmp


# The package root exposes the seam and not the backend: the adapter
# API is an internal engineering contract, not one of the world-facing
# interfaces, so the seam's own vocabulary is importable and QEMU's
# helpers are not.

def test_the_package_root_exposes_the_seam():
    assert isinstance(reliquary.adapter("qemu"), qemu_module.QemuAdapter)


@pytest.mark.parametrize("gone", ["find_qemu", "find_qemu_img",
                                  "create_hdd_image", "Qmp", "stop",
                                  "machine_drive_args"])
def test_a_qemu_helper_is_not_in_the_package_surface(gone):
    assert gone not in reliquary.__all__
