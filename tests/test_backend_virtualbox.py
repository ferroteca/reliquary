# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Installed tests for the VirtualBox adapter: images, lifecycle.

Everything below the adapter seam that **only VirtualBox knows** — VDI
materialization, `createvm` under the machine directory, the storage
verbs, scancodes, and the owned start and stop. What every adapter owes
the seam alike — the name, the capability report, the image extension,
discovery, the host font, and the refusal to command an unverified VM —
is `test_backend_contract`, driven against this backend and QEMU from
one text (F59). ``VBoxManage`` is always mocked; no unit test launches a
real hypervisor.
"""

import os
import uuid
from unittest import mock

import pytest

from reliquary import backend_virtualbox as vbox
from tests.vga_bank import vga_bank
from reliquary.errors import PreflightError, RunFailure, StaticError

_VM_UUID = "11111111-2222-3333-4444-555555555555"


def _completed(stdout="", stderr="", returncode=0):
    result = mock.Mock()
    result.stdout = stdout
    result.stderr = stderr
    result.returncode = returncode
    return result


@pytest.fixture
def root(tmp_path):
    return str(tmp_path)


def _install(root, payload):
    """A stand-in VirtualBox install directory carrying ``payload``."""
    with open(os.path.join(root, "VBoxDD2.dll"), "wb") as handle:
        handle.write(payload)
    return mock.patch.object(
        vbox, "find_vboxmanage",
        return_value=os.path.join(root, "VBoxManage.exe"))


def _info(state="poweroff", name="reliquary-demo-0"):
    return (
        f'name="{name}"\n'
        f'UUID="{_VM_UUID}"\n'
        f'VMState="{state}"\n'
    )


def _vm(drives=None):
    return {
        "backend": "virtualbox", "backend-id": _VM_UUID,
        "token": _VM_UUID,
        "endpoint": {"name": "reliquary-demo-0", "drives": drives or {}},
    }


# Sizes, in VirtualBox's own unit.

def test_size_strings_become_megabytes():
    assert vbox.size_megabytes("20M") == 20
    assert vbox.size_megabytes("2G") == 2048
    assert vbox.size_megabytes(32) == 32


def test_sub_megabyte_sizes_round_up_to_one():
    assert vbox.size_megabytes("512K") == 1


def test_a_bad_size_is_static():
    with pytest.raises(StaticError) as caught:
        vbox.size_megabytes("plenty")
    assert caught.value.rule_id == "value.not-a-size"


# VDI materialization.

def test_create_vdi_invokes_createmedium(root):
    path = os.path.join(root, "disk.vdi")
    with mock.patch.object(vbox, "find_vboxmanage",
                           return_value="VBoxManage"), \
            mock.patch("subprocess.run", return_value=_completed()) as run:
        result = vbox.create_vdi(path, "20M")
    assert result == os.path.abspath(path)
    args = run.call_args[0][0]
    assert args[0] == "VBoxManage"
    assert args[1] == "createmedium"
    assert "--format=VDI" in args
    assert "--size=20" in args


def test_create_vdi_refuses_a_non_vdi_path(root):
    with pytest.raises(StaticError) as caught:
        vbox.create_vdi(os.path.join(root, "disk.qcow2"), "20M")
    assert caught.value.rule_id == "image.wrong-extension"


def test_create_vdi_refuses_an_existing_file(root):
    path = os.path.join(root, "disk.vdi")
    with open(path, "wb") as handle:
        handle.write(b"x")
    with pytest.raises(PreflightError) as caught:
        vbox.create_vdi(path, "20M")
    assert caught.value.rule_id == "image.already-exists"


def test_difference_and_copy_use_the_right_verbs(root):
    base = os.path.join(root, "base.vdi")
    with open(base, "wb") as handle:
        handle.write(b"base")
    with mock.patch.object(vbox, "find_vboxmanage",
                           return_value="VBoxManage"), \
            mock.patch("subprocess.run", return_value=_completed()) as run:
        vbox.create_difference_vdi(os.path.join(root, "diff.vdi"), base)
        diff_args = run.call_args[0][0]
        vbox.create_duplicate_vdi(os.path.join(root, "copy.vdi"), base)
        copy_args = run.call_args[0][0]
    assert diff_args[1] == "createmedium"
    assert any(a.startswith("--diffparent=") for a in diff_args)
    assert copy_args[1] == "clonemedium"


# The host's fonts, beyond what the seam contract already holds.

def test_an_override_table_yields_a_second_font(root):
    """A stock install offers two 8x16 fonts, not one.

    The bank as stored is what a DOS guest ends up drawing with;
    the same bank with the BIOS's override table applied is what
    the BIOS draws its own messages with. Both are the host's, and
    a screenshot does not say which painted it.
    """
    own = bytearray(vga_bank())
    patch = bytes([0x57]) + b"\x5a" * 16     # 'W' drawn differently
    payload = b"\x11" * 500 + bytes(own) + patch + b"\x00" + b"\x22" * 30
    with _install(root, payload):
        banks = vbox.guest_glyph_banks()
    assert len(banks) == 2
    assert banks[0] == bytes(own)
    own[0x57 * 16:0x58 * 16] = b"\x5a" * 16
    assert banks[1] == bytes(own)


def test_several_banks_round_trip_through_one_cache_file(tmp_path):
    own = vga_bank()
    other = bytes(own[:0x57 * 16]) + b"\x5a" * 16 + bytes(own[0x58 * 16:])
    cache = str(tmp_path / "cache")
    with mock.patch.object(vbox.text_recognize, "banks_from_files",
                           return_value=(own, other)):
        first = vbox.guest_glyph_banks(cache)
    assert first == (own, other)
    # The second read never touches the install.
    with mock.patch.object(
            vbox, "find_vboxmanage",
            side_effect=AssertionError("must not re-extract")):
        assert vbox.guest_glyph_banks(cache) == (own, other)


def test_a_truncated_cache_file_is_re_extracted(tmp_path):
    own = vga_bank()
    root = str(tmp_path / "install")
    cache = str(tmp_path / "cache")
    os.makedirs(root)
    stale = os.path.join(cache, "support", "virtualbox")
    os.makedirs(stale)
    with open(os.path.join(stale, "cp437-8x16-banks.bin"), "wb") as handle:
        handle.write(b"\x00" * 100)
    with _install(root, b"\x11" * 500 + own + b"\x22" * 30):
        assert vbox.guest_glyph_banks(cache) == (own,)


def test_an_installation_with_no_font_says_it_cannot_read_a_screen(root):
    """The refusal names the consequence, not just the missing file."""
    with _install(root, b"\x00" * 9000):
        with pytest.raises(PreflightError) as caught:
            vbox.guest_glyph_banks()
    assert "cannot read a guest screen" in str(caught.value)


def test_text_screen_reads_through_the_host_fonts():
    marker = (b"\x5a" * 4096, b"\x33" * 4096)
    session = vbox.VirtualBoxSession(
        "uuid-1", "reliquary-plain-0", cache="/tmp/cache")
    with mock.patch.object(vbox, "guest_glyph_banks",
                           return_value=marker) as bank, \
            mock.patch.object(session, "screenshot"), \
            mock.patch.object(vbox.text_recognize, "recognize",
                              return_value=([], [])) as recognize:
        session.text_screen()
    assert recognize.call_args.kwargs["bank"] == marker
    # And the session's cache root is where it is told to keep it.
    assert bank.call_args.args == ("/tmp/cache",)


# The storage verbs, and the slots they attach to.

def test_removing_a_controller_passes_the_name_as_two_tokens():
    """VBoxManage 7.2 refuses `--name=X --remove`.

    It answers "Too few parameters" and exits 2, which broke every
    restart of an existing VM — `configure_vm` drops the
    controllers it owns before rebuilding them from state. The
    joined form still works alongside `--add`, so only the removal
    is spelled apart.
    """
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        if command[1] == "showvminfo":
            return _completed(
                stdout='storagecontrollername0="reliquary-ide"\n')
        return _completed()

    with mock.patch.object(vbox, "find_vboxmanage",
                           return_value="VBoxManage"), \
            mock.patch("subprocess.run", side_effect=run):
        vbox.configure_vm({"drives": {"hdd0": {"medium": "hdd"}}},
                          "reliquary-plain-0")

    removal = next(c for c in calls
                   if c[1] == "storagectl" and "--remove" in c)
    assert removal[2:] == ["reliquary-plain-0", "--name", "reliquary-ide",
                           "--remove"]
    assert "--name=reliquary-ide" not in removal


def test_hard_disks_take_the_ide_slots_before_cdroms():
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

    assert (attachments["hdd0"]["port"],
            attachments["hdd0"]["device"]) == (0, 0)
    assert (attachments["cdrom0"]["port"],
            attachments["cdrom0"]["device"]) == (0, 1)
    assert attachments["hdd0"]["type"] == "hdd"
    assert attachments["cdrom0"]["type"] == "dvddrive"


def test_several_disks_keep_key_order_within_their_kind():
    state = {"drives": {
        "cdrom0": {"medium": "cdrom"},
        "hdd0": {"medium": "hdd"},
        "hdd1": {"medium": "hdd"},
        "floppy0": {"medium": "floppy"},
    }}

    attachments = vbox.drive_attachments(state)

    assert attachments["hdd0"]["port"] == 0
    assert attachments["hdd0"]["device"] == 0
    assert attachments["hdd1"]["port"] == 0
    assert attachments["hdd1"]["device"] == 1
    assert attachments["cdrom0"]["port"] == 1
    assert attachments["cdrom0"]["device"] == 0
    assert attachments["floppy0"]["storagectl"] == vbox._FLOPPY


def test_boot_keys_map_to_vbox_kinds():
    drives = {
        "floppy0": {"medium": "floppy"},
        "hdd0": {"medium": "hdd"},
        "cdrom0": {"medium": "cdrom"},
    }
    assert vbox._boot_order(["cdrom0", "hdd0", "floppy0"], drives) == [
        "dvd", "disk", "floppy", "none"]


def test_scancodes_for_shift_chord():
    codes = vbox.scancodes_for(["shift", "a"])
    # shift make, a make, a break, shift break
    assert codes == [0x2a, 0x1e, 0x9e, 0xaa]


# The owned lifecycle: create, start, stop, and what a session refuses.

@pytest.fixture
def state(tmp_path):
    return {
        "id": "demo-0",
        "backend-id": "reliquary-demo-0",
        "memory": 32,
        "cpus": 1,
        "boot": ["hdd0"],
        "drives": {
            "hdd0": {"medium": "hdd",
                     "path": str(tmp_path / "disk.vdi")},
        },
    }


def test_launch_creates_configures_and_starts(state, tmp_path):
    backend_dir = str(tmp_path / "virtualbox")
    os.makedirs(backend_dir)
    calls = []

    def run(args, **kwargs):
        calls.append(list(args))
        verb = args[1]
        if verb == "showvminfo":
            # First ensure_vm probe: absent. Later verifies: present.
            if len([c for c in calls if c[1] == "showvminfo"]) == 1:
                return _completed(returncode=1, stderr="not found")
            return _completed(stdout=_info())
        return _completed()

    with mock.patch.object(vbox, "find_vboxmanage",
                           return_value="VBoxManage"), \
            mock.patch("subprocess.run", side_effect=run), \
            mock.patch.object(vbox.uuid, "uuid4",
                              return_value=uuid.UUID(_VM_UUID)):
        identity = vbox.launch_owned_vm(state, backend_dir=backend_dir)

    assert identity["backend"] == "virtualbox"
    assert identity["backend-id"] == _VM_UUID
    assert identity["token"] == _VM_UUID
    assert identity["endpoint"]["name"] == "reliquary-demo-0"
    assert "hdd0" in identity["endpoint"]["drives"]
    assert identity["endpoint"]["drives"]["hdd0"]["type"] == "hdd"
    verbs = [c[1] for c in calls]
    for verb in ("createvm", "modifyvm", "storagectl", "storageattach",
                 "startvm"):
        assert verb in verbs
    create = next(c for c in calls if c[1] == "createvm")
    assert "--platform-architecture=x86" in create
    assert "--ostype=DOS" in create
    assert any(a.startswith("--basefolder=") for a in create)


def test_stop_verifies_identity_before_poweroff():
    calls = []

    def run(args, **kwargs):
        calls.append(list(args))
        if args[1] == "showvminfo":
            return _completed(stdout=_info(state="running"))
        return _completed()

    vm = {"backend": "virtualbox", "backend-id": _VM_UUID,
          "token": _VM_UUID, "endpoint": {"name": "x"}}
    with mock.patch.object(vbox, "find_vboxmanage",
                           return_value="VBoxManage"), \
            mock.patch("subprocess.run", side_effect=run):
        vbox.stop(vm)
    assert calls[0][1] == "showvminfo"
    assert calls[1][1:] == ["controlvm", _VM_UUID, "poweroff"]


def test_the_identity_refusal_carries_the_virtualbox_rule_id():
    """The id a consumer switches on, beyond the contract's behaviour."""
    def run(args, **kwargs):
        if args[1] == "showvminfo":
            return _completed(stdout=_info().replace(
                _VM_UUID, "00000000-0000-0000-0000-000000000000"))
        return _completed()

    vm = {"backend": "virtualbox", "backend-id": _VM_UUID,
          "token": _VM_UUID, "endpoint": {}}
    with mock.patch.object(vbox, "find_vboxmanage",
                           return_value="VBoxManage"), \
            mock.patch("subprocess.run", side_effect=run):
        with pytest.raises(PreflightError) as caught:
            vbox.stop(vm)
    assert caught.value.rule_id == "machine.vm-identity-mismatch"


def test_send_keys_emits_make_then_break_scancodes():
    calls = []

    def run(args, **kwargs):
        calls.append(list(args))
        return _completed(stdout=_info(state="running"))

    adapter = vbox.VirtualBoxAdapter()
    with mock.patch.object(vbox, "find_vboxmanage",
                           return_value="VBoxManage"), \
            mock.patch("subprocess.run", side_effect=run), \
            mock.patch.object(vbox.time, "sleep"):
        with adapter.session(_vm()) as session:
            session.send_keys([["ret"]], delay=0)
    key_call = next(c for c in calls
                    if c[1:][:2] == ["controlvm", _VM_UUID]
                    and "keyboardputscancode" in c)
    # enter make 1c, break 9c
    assert key_call[-2:] == ["1c", "9c"]


def test_change_medium_retargets_the_recorded_attachment(root):
    calls = []

    def run(args, **kwargs):
        calls.append(list(args))
        return _completed(stdout=_info(state="running"))

    drives = {
        "cdrom0": {
            "storagectl": "reliquary-ide", "port": 1, "device": 0,
            "type": "dvddrive",
        },
    }
    iso = os.path.join(root, "live.iso")
    with open(iso, "wb") as handle:
        handle.write(b"ISO")
    adapter = vbox.VirtualBoxAdapter()
    with mock.patch.object(vbox, "find_vboxmanage",
                           return_value="VBoxManage"), \
            mock.patch("subprocess.run", side_effect=run):
        with adapter.session(_vm(drives)) as session:
            session.change_medium("cdrom0", iso)
            session.change_medium("cdrom0", None)
    attaches = [c for c in calls if c[1] == "storageattach"]
    assert len(attaches) == 2
    assert any(iso in a for a in attaches[0])
    assert any("emptydrive" in a for a in attaches[1])


def test_stop_is_satisfied_by_an_already_stopped_vm():
    """A guest that powered itself off leaves stop nothing to do."""
    calls = []

    def run(args, **kwargs):
        calls.append(list(args))
        if args[1] == "showvminfo":
            return _completed(stdout=_info(state="poweroff"))
        return _completed(returncode=1,
                          stderr="Machine is not currently running.")

    with mock.patch.object(vbox, "find_vboxmanage",
                           return_value="VBoxManage"), \
            mock.patch("subprocess.run", side_effect=run):
        vbox.stop(_vm())
    assert [c[1] for c in calls] == ["showvminfo"]


def test_a_session_refuses_a_vm_that_is_not_running():
    """The runner reads this rule id as the stopped observation."""
    def run(args, **kwargs):
        if args[1] == "showvminfo":
            return _completed(stdout=_info(state="poweroff"))
        return _completed()

    adapter = vbox.VirtualBoxAdapter()
    with mock.patch.object(vbox, "find_vboxmanage",
                           return_value="VBoxManage"), \
            mock.patch("subprocess.run", side_effect=run):
        with pytest.raises(PreflightError) as caught:
            with adapter.session(_vm()):
                pass
    assert caught.value.rule_id == "machine.vm-unreachable"
    assert "poweroff" in str(caught.value)


def test_a_guest_that_powers_off_mid_session_reads_as_stopped(root):
    """The state query, not the message, tells the two apart."""
    states = ["running", "poweroff"]

    def run(args, **kwargs):
        if args[1] == "showvminfo":
            return _completed(stdout=_info(
                state=states.pop(0) if states else "poweroff"))
        return _completed(returncode=1,
                          stderr="Machine is not currently running.")

    adapter = vbox.VirtualBoxAdapter()
    with mock.patch.object(vbox, "find_vboxmanage",
                           return_value="VBoxManage"), \
            mock.patch("subprocess.run", side_effect=run):
        with adapter.session(_vm()) as session:
            with pytest.raises(PreflightError) as caught:
                session.screenshot(os.path.join(root, "shot.png"))
    assert caught.value.rule_id == "machine.vm-unreachable"


def test_a_carrier_failure_on_a_live_vm_stays_a_run_failure(root):
    """Only a stopped VM is reclassified; a broken command is not."""
    def run(args, **kwargs):
        if args[1] == "showvminfo":
            return _completed(stdout=_info(state="running"))
        return _completed(returncode=1, stderr="something else broke")

    adapter = vbox.VirtualBoxAdapter()
    with mock.patch.object(vbox, "find_vboxmanage",
                           return_value="VBoxManage"), \
            mock.patch("subprocess.run", side_effect=run):
        with adapter.session(_vm()) as session:
            with pytest.raises(RunFailure) as caught:
                session.screenshot(os.path.join(root, "shot.png"))
    assert caught.value.rule_id == "machine.backend-failed"


def test_a_transitional_state_is_not_read_as_stopped():
    """A slow power-on must never look like a power-off."""
    def run(args, **kwargs):
        if args[1] == "showvminfo":
            return _completed(stdout=_info(state="starting"))
        return _completed()

    adapter = vbox.VirtualBoxAdapter()
    with mock.patch.object(vbox, "find_vboxmanage",
                           return_value="VBoxManage"), \
            mock.patch("subprocess.run", side_effect=run):
        with adapter.session(_vm()) as session:
            assert session.recognizes_text
