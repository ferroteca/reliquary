# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Installed tests for the QEMU adapter: ownership, images, rendering.

This file covers everything below the adapter seam that only QEMU
knows about: the owned launch and its identity verification, qcow2
materialization, the drive and boot rendering a machine's state turns
into, and the carriers a session exposes. What every adapter must
provide the same way — the name, the capability report, the image
extension, discovery, the host font, and the refusal to command an
unverified VM — is covered once, in `test_backend_contract`, and run
against this backend and VirtualBox from that one file (F59).
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
from reliquary.errors import (InternalError, PreflightError, RunFailure,
                              StaticError)


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


def test_a_removable_drive_carries_its_key_as_the_launch_id(root):
    drives = {"floppy0": {"medium": "floppy", "slot": 0,
                          "path": _image(root, "boot.img")}}
    values = _drive_values(qemu_module.drive_args(drives))
    assert "id=floppy0" in values[0]


# Share devices (F68): a host directory presented to the guest. Only
# `model: vvfat` renders — the capability report never claims 9pfs or
# virtual-fs yet, so unmet() has already refused those at assignment.

def test_a_vvfat_share_renders_as_a_synthesized_fat_drive(root):
    work = os.path.join(root, "work")
    os.makedirs(work)
    shares = {"share0": {"media": "hostdir", "materialize": "use",
                         "path": work, "model": "vvfat"}}
    values = _drive_values(qemu_module.share_args(shares, {}))
    assert any("fat:rw:" in value for value in values)


def test_a_share_carries_its_slot_key_as_its_id(root):
    work = os.path.join(root, "work")
    os.makedirs(work)
    shares = {"share0": {"media": "hostdir", "materialize": "use",
                         "path": work, "model": "vvfat"}}
    values = _drive_values(qemu_module.share_args(shares, {}))
    assert "id=share0" in values[0]


def test_a_share_continues_the_ide_bus_after_the_last_cdrom(root):
    drives = {
        "hdd0": {"medium": "hdd", "slot": 0,
                 "path": _image(root, "blank.qcow2")},
        "cdrom0": {"medium": "cdrom", "slot": 0,
                   "path": _image(root, "live.iso")},
    }
    work = os.path.join(root, "work")
    os.makedirs(work)
    shares = {"share0": {"media": "hostdir", "materialize": "use",
                         "path": work, "model": "vvfat"}}
    values = _drive_values(qemu_module.share_args(shares, drives))
    assert "if=ide,index=2" in values[0]


def test_a_share_with_an_unsupported_model_is_an_internal_error(root):
    # unmet() refuses this at assignment (F70 not delivered yet), so
    # reaching the renderer at all is a bug, not a blueprint mistake.
    shares = {"share0": {"media": "hostdir", "materialize": "use",
                         "path": root, "model": "virtual-fs"}}
    with pytest.raises(InternalError):
        qemu_module.share_args(shares, {})


# The 9pfs model (F69): an in-process virtio-9p server over a host
# directory, live in both directions, and QEMU's default for a share
# whose blueprint named no model at all.

def _valued(args, option):
    return [args[i + 1] for i, a in enumerate(args) if a == option]


def test_a_9p_share_renders_an_fsdev_and_a_virtio_9p_device(root):
    work = os.path.join(root, "work")
    os.makedirs(work)
    shares = {"share0": {"media": "hostdir", "materialize": "use",
                         "path": work, "model": "9pfs"}}
    args = qemu_module.share_args(shares, {})
    fsdev, = _valued(args, "-fsdev")
    device, = _valued(args, "-device")
    assert fsdev.startswith("local,")
    assert f"path={work}" in fsdev
    assert device.startswith("virtio-9p-pci,")
    assert "fsdev=share0" in device


def test_a_9p_share_names_the_guest_mount_tag_after_its_slot_key(root):
    # One rule across every mechanism: the slot key is the name the
    # guest sees, so a blueprint never carries a per-backend naming
    # field. Here that name is the 9P mount tag.
    work = os.path.join(root, "work")
    os.makedirs(work)
    shares = {"share1": {"media": "hostdir", "materialize": "use",
                         "path": work, "model": "9pfs"}}
    device, = _valued(qemu_module.share_args(shares, {}), "-device")
    assert "mount_tag=share1" in device


def test_a_9p_share_takes_no_place_on_the_ide_bus(root):
    # It is not a disk. A vvfat share sorted after it still lands on
    # the index it would have had on its own, so mixing the two models
    # never shifts a guest's drive letters.
    work = os.path.join(root, "work")
    os.makedirs(work)
    shares = {
        "share0": {"media": "hostdir", "materialize": "use",
                   "path": work, "model": "9pfs"},
        "share1": {"media": "hostdir", "materialize": "use",
                   "path": work, "model": "vvfat"},
    }
    drives = {"hdd0": {"medium": "hdd", "slot": 0,
                       "path": _image(root, "blank.qcow2")}}
    values = _drive_values(qemu_module.share_args(shares, drives))
    assert values == [f"file=fat:rw:{work},format=raw,if=ide,index=1,"
                      "id=share1"]


def test_a_read_only_share_is_served_read_only(root):
    # The media's own `read-only` (media-spec.md), mapped onto this
    # mechanism's option: the guest can read the host directory and
    # cannot write into it.
    work = os.path.join(root, "work")
    os.makedirs(work)
    shares = {"share0": {"media": "hostdir", "materialize": "use",
                         "path": work, "model": "9pfs",
                         "read-only": True}}
    fsdev, = _valued(qemu_module.share_args(shares, {}), "-fsdev")
    assert "readonly=on" in fsdev


def test_a_writable_share_says_nothing_about_read_only(root):
    work = os.path.join(root, "work")
    os.makedirs(work)
    shares = {"share0": {"media": "hostdir", "materialize": "use",
                         "path": work, "model": "9pfs",
                         "read-only": False}}
    fsdev, = _valued(qemu_module.share_args(shares, {}), "-fsdev")
    assert "readonly" not in fsdev


def test_a_read_only_vvfat_share_is_synthesized_read_only(root):
    # The same media field, mapped onto this mechanism's own option:
    # QEMU's `fat:` prefix without `rw:` is a read-only FAT volume.
    # `read-only` reaches every share model or none of them —
    # media-spec.md states it for shares as a whole.
    work = os.path.join(root, "work")
    os.makedirs(work)
    shares = {"share0": {"media": "hostdir", "materialize": "use",
                         "path": work, "model": "vvfat",
                         "read-only": True}}
    value, = _drive_values(qemu_module.share_args(shares, {}))
    assert value.startswith(f"file=fat:{work},")


# Network devices (D120): attachment and interface in, QEMU
# netdev/device arguments out. The chipset is always the
# platform-resolved model the caller already put in the state entry
# — network_args never chooses one itself.

def test_network_nat_renders_a_user_mode_netdev():
    network = {"net0": {"attachment": "nat", "interface": None,
                        "model": "pcnet"}}
    args = qemu_module.network_args(network)
    assert args == ["-netdev", "user,id=net0",
                    "-device", "pcnet,netdev=net0,id=net0"]


def test_network_model_ne2k_renders_the_isa_variant():
    # D122: an explicit model override selects the QEMU device model
    # directly, bypassing the platform default.
    network = {"net0": {"attachment": "nat", "interface": None,
                        "model": "ne2k"}}
    args = qemu_module.network_args(network)
    assert args == ["-netdev", "user,id=net0",
                    "-device", "ne2k_isa,netdev=net0,id=net0"]


def test_network_model_virtual_net_renders_the_pci_device():
    # D122: same override mechanism as ne2k, targeting the
    # paravirtualized NIC instead.
    network = {"net0": {"attachment": "nat", "interface": None,
                        "model": "virtual-net"}}
    args = qemu_module.network_args(network)
    assert args == ["-netdev", "user,id=net0",
                    "-device", "virtio-net-pci,netdev=net0,id=net0"]


def test_network_bridged_with_an_interface_names_it():
    network = {"net0": {"attachment": "bridged", "interface": "eth0",
                        "model": "pcnet"}}
    args = qemu_module.network_args(network)
    assert args[1] == "bridge,id=net0,br=eth0"


def test_network_bridged_without_an_interface_omits_br():
    # QEMU's own default (the conventional bridge name br0) applies;
    # Reliquary does not probe the host for one (D120, T32).
    network = {"net0": {"attachment": "bridged", "interface": None,
                        "model": "pcnet"}}
    args = qemu_module.network_args(network)
    assert args[1] == "bridge,id=net0"


def test_network_devices_render_in_slot_order():
    network = {
        "net1": {"attachment": "nat", "interface": None, "model": "pcnet"},
        "net0": {"attachment": "nat", "interface": None, "model": "pcnet"},
    }
    args = qemu_module.network_args(network)
    ids = [a for a in args if a.startswith("user,id=")]
    assert ids == ["user,id=net0", "user,id=net1"]


def test_the_boot_order_becomes_firmware_letters():
    drives = {"hdd0": {"medium": "hdd", "slot": 0, "path": None},
              "cdrom0": {"medium": "cdrom", "slot": 0, "path": None}}
    assert qemu_module._boot_order(["cdrom0", "hdd0"], drives) == "dc"
    assert qemu_module._boot_order(["hdd0", "cdrom0"], drives) == "cd"


# The system binary is chosen by the machine's declared platform,
# because the wrong one is not a degraded run but a reboot loop: an
# amd64 kernel triple-faults on the 32-bit binary, and the loop looks
# exactly like a guest that never got going. Declared, never read off
# an image (P10), and DOS stays on the binary its delivered workflow
# is tested against.

@pytest.mark.parametrize("platform, stem", [
    ("dos", "qemu-system-i386"),
    ("win9x", "qemu-system-i386"),
    ("winnt", "qemu-system-x86_64"),
    ("openbsd", "qemu-system-x86_64"),
])
def test_the_platform_chooses_the_system_binary(platform, stem):
    assert qemu_module._platform_binary(platform).startswith(stem)


def test_an_unstated_platform_keeps_the_compatibility_default():
    # A machine caught mid-create carries no platform yet, and DOS is
    # the compatibility default: the binary is the one it always was.
    assert qemu_module._platform_binary(None).startswith("qemu-system-i386")


def test_an_unmapped_platform_refuses_rather_than_guessing():
    # The defect this table exists to prevent was a silent wrong
    # binary, so a platform the schema gains and this table misses
    # names itself instead of triple-faulting in the guest (P11).
    with pytest.raises(InternalError, match="plan9"):
        qemu_module._platform_binary("plan9")


def test_start_asks_for_the_binary_its_platform_needs(root):
    adapter = qemu_module.QemuAdapter()
    state = {
        "id": "openbsd-0", "backend-id": "reliquary-openbsd-0",
        "platform": "openbsd", "memory": 512, "boot": ["hdd0"],
        "devices": {"hdd0": {"medium": "hdd", "slot": 0,
                            "path": _image(root, "disk.qcow2")}},
    }
    with mock.patch.object(qemu_module, "_find_qemu_tool",
                           side_effect=lambda binary: binary), \
            mock.patch.object(qemu_module, "launch_owned_qemu") as launch:
        adapter.start(state, machine_dir=root,
                      backend_dir=os.path.join(root, "qemu"))

    assert launch.call_args.args[0][0].startswith("qemu-system-x86_64")


def test_start_renders_the_state_and_launches_it(root):
    adapter = qemu_module.QemuAdapter()
    state = {
        "id": "plain-0", "backend-id": "reliquary-plain-0",
        "memory": 32, "boot": ["cdrom0"],
        "devices": {"cdrom0": {"medium": "cdrom", "slot": 0,
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


# The settings hatch: passed through to QEMU, but bounded -- it can
# never become a second way to set something a reliquary field
# already owns (drives, memory, and so on).
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


#: Every argument that belongs to a blueprint field or to the VM
#: identity, and which field owns it. Each argument gets its own
#: parametrized test case, so if one stops being refused, the
#: specific failing case is named rather than lost inside one loop
#: over all arguments.
_OWNED_ARGUMENTS = {
    "-m": "memory", "-smp": "cpus", "-boot": "boot",
    "-drive": "devices", "-hda": "devices", "-fda": "devices",
    "-cdrom": "devices", "-fsdev": "devices", "-virtfs": "devices",
    "-machine": "machine", "-M": "machine",
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
def test_set_on_a_rendered_drive_property_is_refused_naming_devices(target):
    # `-drive` is refused because `devices` renders it; `-set` reaching
    # the same property is the same second source for one fact
    for args in (["-set", target], [f"-set {target}"]):
        with pytest.raises(StaticError) as caught:
            qemu_module.settings_args({"args": args})
        assert caught.value.rule_id == "machine.settings-reserved-argument"
        assert "devices" in str(caught.value)


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
        "memory": 32, "boot": [], "devices": {},
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

def test_pointing_device_tablet_renders_the_usb_device():
    adapter = qemu_module.QemuAdapter()
    state = {
        "id": "tab-0", "backend-id": "reliquary-tab-0", "memory": 32,
        "boot": [], "devices": {"pointer0": {"value": "virtual-tablet"}},
    }
    with mock.patch.object(qemu_module, "find_qemu",
                           return_value="qemu-system-i386"), \
            mock.patch.object(qemu_module, "launch_owned_qemu") as launch:
        adapter.start(state, machine_dir=".", backend_dir="qemu")
    args = launch.call_args.args[0]
    assert args[-3:] == ["-usb", "-device", "usb-tablet,id=pointer0"]


def test_pointing_device_mouse_renders_nothing_extra():
    adapter = qemu_module.QemuAdapter()
    state = {
        "id": "mouse-0", "backend-id": "reliquary-mouse-0", "memory": 32,
        "boot": [], "devices": {"pointer0": {"value": "emulated-mouse"}},
    }
    with mock.patch.object(qemu_module, "find_qemu",
                           return_value="qemu-system-i386"), \
            mock.patch.object(qemu_module, "launch_owned_qemu") as launch:
        adapter.start(state, machine_dir=".", backend_dir="qemu")
    args = launch.call_args.args[0]
    assert "usb-tablet" not in " ".join(args)
    assert "virtio-mouse" not in " ".join(args)


def test_pointing_device_virtio_mouse_renders_the_virtio_device():
    adapter = qemu_module.QemuAdapter()
    state = {
        "id": "vmouse-0", "backend-id": "reliquary-vmouse-0", "memory": 32,
        "boot": [], "devices": {"pointer0": {"value": "virtual-mouse"}},
    }
    with mock.patch.object(qemu_module, "find_qemu",
                           return_value="qemu-system-i386"), \
            mock.patch.object(qemu_module, "launch_owned_qemu") as launch:
        adapter.start(state, machine_dir=".", backend_dir="qemu")
    args = launch.call_args.args[0]
    assert args[-2:] == ["-device", "virtio-mouse-pci,id=pointer0"]
    assert "-usb" not in args


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


def test_pointer_events_are_refused_off_the_vnc_plane():
    # No coordinate space without a framebuffer (F66) — unreachable in
    # an ordinary run, since `capture_format` already refuses a
    # landmark condition (and so a `click`) on this plane.
    qmp = mock.Mock()
    with pytest.raises(PreflightError) as caught:
        qemu_module.QemuSession(qmp).pointer_event(1, 2, 1)
    assert caught.value.rule_id == "machine.plane-no-pointer-input"


def test_the_qemu_adapter_reports_the_pointing_devices_it_renders():
    with mock.patch.object(qemu_module, "probe_share_models",
                           return_value=()):
        report = qemu_module.QemuAdapter().capabilities()
    assert report.pointing_devices == ("virtual-tablet", "emulated-mouse",
                                       "virtual-mouse")


def test_the_qemu_adapter_reports_the_network_devices_it_renders():
    with mock.patch.object(qemu_module, "probe_share_models",
                           return_value=()):
        report = qemu_module.QemuAdapter().capabilities()
    assert report.network_models == ("pcnet", "ne2k", "virtual-net")
    assert report.network_attachments == ("nat", "bridged")


def test_the_qemu_adapter_reports_the_rng_models_it_renders():
    with mock.patch.object(qemu_module, "probe_share_models",
                           return_value=()):
        report = qemu_module.QemuAdapter().capabilities()
    assert report.rng_models == ("virtual-rng",)


def test_an_rng_device_renders_as_virtio_rng_pci():
    adapter = qemu_module.QemuAdapter()
    state = {
        "id": "rng-0", "backend-id": "reliquary-rng-0", "memory": 32,
        "boot": [], "devices": {"rng0": {"rng-model": "virtual-rng"}},
    }
    with mock.patch.object(qemu_module, "find_qemu",
                           return_value="qemu-system-i386"), \
            mock.patch.object(qemu_module, "launch_owned_qemu") as launch:
        adapter.start(state, machine_dir=".", backend_dir="qemu")
    args = launch.call_args.args[0]
    assert args[-2:] == ["-device", "virtio-rng-pci,id=rng0"]


def test_no_rng_device_renders_nothing_extra():
    adapter = qemu_module.QemuAdapter()
    state = {
        "id": "no-rng-0", "backend-id": "reliquary-no-rng-0", "memory": 32,
        "boot": [], "devices": {},
    }
    with mock.patch.object(qemu_module, "find_qemu",
                           return_value="qemu-system-i386"), \
            mock.patch.object(qemu_module, "launch_owned_qemu") as launch:
        adapter.start(state, machine_dir=".", backend_dir="qemu")
    args = launch.call_args.args[0]
    assert "virtio-rng" not in " ".join(args)


def test_a_share_a_pointer_and_an_rng_dont_get_mixed_up(root):
    # A pointer entry carries "value" and an rng entry carries
    # "rng-model" — this is the actual boundary D124/D125 added inside
    # the merged devices map, so it's worth checking directly, not
    # just in isolation: a share must not swallow either one, and
    # neither must be classified as the other.
    adapter = qemu_module.QemuAdapter()
    work = os.path.join(root, "work")
    os.makedirs(work)
    state = {
        "id": "mixed-0", "backend-id": "reliquary-mixed-0", "memory": 32,
        "boot": [], "devices": {
            "share0": {"media": "hostdir", "materialize": "use",
                      "path": work, "model": "vvfat"},
            "pointer0": {"value": "virtual-tablet"},
            "rng0": {"rng-model": "virtual-rng"},
        },
    }
    with mock.patch.object(qemu_module, "find_qemu",
                           return_value="qemu-system-i386"), \
            mock.patch.object(qemu_module, "launch_owned_qemu") as launch:
        adapter.start(state, machine_dir=".", backend_dir="qemu")
    joined = " ".join(launch.call_args.args[0])
    assert "id=share0" in joined
    assert "usb-tablet,id=pointer0" in joined
    assert "virtio-rng-pci,id=rng0" in joined


def test_the_qemu_adapter_adds_the_share_models_the_binary_actually_has():
    # vvfat is in every QEMU build and needs no probe; 9pfs is there
    # only if the binary was built with fsdev support, and once it is,
    # it is also what an unstated-model share resolves to (F69) --
    # never vvfat, whose snapshot trade only arrives by name.
    with mock.patch.object(qemu_module, "probe_share_models",
                           return_value=("9pfs",)):
        report = qemu_module.QemuAdapter().capabilities("dos")
    assert report.share_models == ("vvfat", "9pfs")
    assert report.share_default == "9pfs"


def test_a_qemu_without_9pfs_offers_vvfat_and_no_live_default():
    # The stock Windows build: an authored `vvfat` share still works,
    # and an unstated-model share is refused by name here instead of
    # silently landing on the snapshot model.
    with mock.patch.object(qemu_module, "probe_share_models",
                           return_value=()):
        report = qemu_module.QemuAdapter().capabilities("dos")
    assert report.share_models == ("vvfat",)
    assert report.share_default is None


def test_the_qemu_adapter_can_deliver_a_pointer_event_on_either_plane():
    adapter = qemu_module.QemuAdapter()
    assert adapter.pointer_capable("agentless-display")
    assert adapter.pointer_capable("vnc")
    assert not adapter.pointer_capable("serial-console")


def _device_help(stdout):
    """What `qemu-system-* -device help` hands back."""
    return mock.Mock(stdout=stdout, stderr="", returncode=0)


# The live share transports (F69): which of them a QEMU can serve is a
# property of how that binary was *built*, not of what this adapter's
# code implements, so the report has to come from probing the very
# binary a machine will launch.

def test_a_qemu_built_with_fsdev_reports_the_9pfs_share_model():
    with mock.patch.object(qemu_module, "find_qemu",
                           return_value="/fake/qemu-system-i386"), \
         mock.patch.object(qemu_module.subprocess, "run") as run:
        run.return_value = _device_help(
            'name "virtio-9p-pci", bus PCI, alias "virtio-9p"\n')
        qemu_module.probe_share_models.cache_clear()
        assert qemu_module.probe_share_models("dos") == ("9pfs",)
    assert run.call_args.args[0][1:] == ["-device", "help"]


def test_a_qemu_built_without_fsdev_reports_no_live_share_model():
    # The official Windows binaries: `-device help` lists no 9P device
    # at all, so the probe finds nothing and the report says nothing.
    with mock.patch.object(qemu_module, "find_qemu",
                           return_value="/fake/qemu-system-i386"), \
         mock.patch.object(qemu_module.subprocess, "run") as run:
        run.return_value = _device_help('name "pcnet", bus PCI\n')
        qemu_module.probe_share_models.cache_clear()
        assert qemu_module.probe_share_models("dos") == ()


def test_a_qemu_that_cannot_be_probed_claims_no_live_share_model():
    # A probe that never happened is not evidence of a capability
    # (P11): no binary to ask means no live model is claimed.
    with mock.patch.object(
            qemu_module, "find_qemu",
            side_effect=PreflightError("qemu-system-i386 not found",
                                       rule_id="machine.backend-not-found")):
        qemu_module.probe_share_models.cache_clear()
        assert qemu_module.probe_share_models("dos") == ()


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
        self.pointer_events = []
        self.refreshed = 0
        self.closed = False
        self._image = image

    def key_event(self, keysym, down):
        self.events.append((keysym, down))

    def pointer_event(self, x, y, button_mask):
        self.pointer_events.append((x, y, button_mask))

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
             "memory": 32, "boot": [], "devices": {}}
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


def test_vnc_pointer_events_reach_rfb_with_no_translation():
    client = _FakeRfb()
    session = qemu_module.QemuVncSession(mock.Mock(), client)
    session.pointer_event(50, 40, 1)
    assert client.pointer_events == [(50, 40, 1)]


def test_the_keysym_table_covers_the_seam_vocabulary():
    """Every seam key VirtualBox translates, the VNC plane translates.

    D103 settled the key-name boundary as QEMU's own qcode set, but
    each adapter still owns its own translation into that set. This
    test is what keeps the two adapters covering the same key names
    instead of drifting apart one key at a time.
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
