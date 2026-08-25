# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Installed tests for the DOSBox-X adapter: drives, images, the wire.

Everything below the adapter seam that **only DOSBox-X knows** — drive
letter assignment, the ``IMGMOUNT``/``BOOT`` and ``VHDMAKE`` rendering,
the ``args`` settings hatch, and the control-channel key-name mapping.
What every adapter owes the seam alike is `test_backend_contract`,
driven against this backend, QEMU and VirtualBox from one text (F59).

No test here opens a real socket or launches a real ``dosbox-x`` binary
— every control-channel interaction rides a fake double, the same
seam `tests/fake_backend.py` and the QEMU/VirtualBox suites already
drive their own adapters through.
"""

import os
from unittest import mock

import pytest

from reliquary import backend_dosbox_x as dosboxx
from reliquary import dosboxx_control
from reliquary.errors import PreflightError, RunFailure, StaticError

_OUR_TOKEN = "11111111-2222-3333-4444-555555555555"


# -- drive layout and launch rendering -------------------------------

def test_floppies_take_a_and_b_by_slot():
    drives = {
        "floppy1": {"medium": "floppy", "slot": 1, "path": None},
        "floppy0": {"medium": "floppy", "slot": 0, "path": "a.img"},
    }
    layout = dosboxx._drive_layout(drives)
    assert layout["floppy0"]["letter"] == "a"
    assert layout["floppy1"]["letter"] == "b"
    assert layout["floppy0"]["mounted"] is True
    assert layout["floppy1"]["mounted"] is False


def test_hdds_take_c_onward_and_cdroms_continue_the_alphabet():
    drives = {
        "hdd0": {"medium": "hdd", "slot": 0, "path": "c.vhd"},
        "hdd1": {"medium": "hdd", "slot": 1, "path": "d.vhd"},
        "cdrom0": {"medium": "cdrom", "slot": 0, "path": "e.iso"},
    }
    layout = dosboxx._drive_layout(drives)
    assert layout["hdd0"]["letter"] == "c"
    assert layout["hdd1"]["letter"] == "d"
    assert layout["cdrom0"]["letter"] == "e"


def test_mount_commands_skip_empty_drives():
    drives = {
        "hdd0": {"medium": "hdd", "slot": 0, "path": "C:\\image.vhd"},
        "cdrom0": {"medium": "cdrom", "slot": 0, "path": None},
    }
    layout = dosboxx._drive_layout(drives)
    commands = dosboxx._mount_commands(drives, layout)
    assert commands == ["IMGMOUNT C: C:\\image.vhd -t hdd"]


def test_boot_command_picks_the_first_bootable_candidate():
    drives = {
        "floppy0": {"medium": "floppy", "slot": 0, "path": None},
        "hdd0": {"medium": "hdd", "slot": 0, "path": "c.vhd"},
    }
    layout = dosboxx._drive_layout(drives)
    # floppy0 is declared but empty, so it is skipped even though it
    # is named first.
    assert dosboxx._boot_command(["floppy0", "hdd0"], drives, layout) == \
        "BOOT C:"


def test_boot_command_is_none_with_nothing_to_boot():
    drives = {"floppy0": {"medium": "floppy", "slot": 0, "path": None}}
    layout = dosboxx._drive_layout(drives)
    assert dosboxx._boot_command(["floppy0"], drives, layout) is None


# -- backend-settings.dosbox-x: the args escape hatch -----------------

def test_settings_args_renders_extra_arguments():
    assert dosboxx.settings_args({"args": ["-fullscreen"]}) == \
        ["-fullscreen"]


def test_settings_args_refuses_an_unknown_key():
    with pytest.raises(StaticError) as caught:
        dosboxx.settings_args({"nonsense": True})
    assert caught.value.rule_id == "machine.settings-unknown-key"


@pytest.mark.parametrize("item", ["-headless", "-c", "-conf"])
def test_settings_args_refuses_reserved_flags(item):
    with pytest.raises(StaticError) as caught:
        dosboxx.settings_args({"args": [item]})
    assert caught.value.rule_id == "machine.settings-reserved-argument"


def test_settings_args_refuses_a_reserved_set_target():
    with pytest.raises(StaticError) as caught:
        dosboxx.settings_args({"args": ["-set", "control token=x"]})
    assert caught.value.rule_id == "machine.settings-reserved-argument"


def test_settings_args_refuses_the_memory_set_target():
    with pytest.raises(StaticError) as caught:
        dosboxx.settings_args({"args": ["-set", "dosbox memsize=64"]})
    assert caught.value.rule_id == "machine.settings-reserved-argument"


def test_settings_args_permits_an_unreserved_set_target():
    assert dosboxx.settings_args(
        {"args": ["-set", "cpu core=normal"]}) == ["-set", "cpu core=normal"]


# -- key-name mapping -------------------------------------------------

def test_seam_letters_and_digits_pass_through():
    assert dosboxx_control.key_name_for("a") == "a"
    assert dosboxx_control.key_name_for("5") == "5"


@pytest.mark.parametrize("seam,expected", [
    ("ret", "enter"), ("spc", "space"), ("backspace", "bspace"),
    ("alt", "lalt"), ("dot", "period"), ("pgup", "pageup"),
])
def test_seam_names_translate_to_dosboxx_names(seam, expected):
    assert dosboxx_control.key_name_for(seam) == expected


def test_an_unmapped_key_fails_closed():
    with pytest.raises(StaticError) as caught:
        dosboxx_control.key_name_for("kp_enter")
    assert caught.value.rule_id == "key.no-mapping"


# -- discovery ----------------------------------------------------

def test_find_dosbox_x_honors_the_home_variable(tmp_path, monkeypatch):
    binary = dosboxx._DOSBOXX_BIN
    (tmp_path / binary).write_bytes(b"")
    monkeypatch.setenv("RELIQUARY_DOSBOXX_HOME", str(tmp_path))
    assert dosboxx.find_dosbox_x() == str(tmp_path / binary)


def test_find_dosbox_x_fails_closed_naming_the_variable(tmp_path,
                                                        monkeypatch):
    monkeypatch.setenv("RELIQUARY_DOSBOXX_HOME", str(tmp_path))
    with pytest.raises(PreflightError) as caught:
        dosboxx.find_dosbox_x()
    assert "RELIQUARY_DOSBOXX_HOME" in str(caught.value)


# -- image materialization --------------------------------------------

def test_create_dynamic_vhd_refuses_the_wrong_extension(tmp_path):
    with pytest.raises(StaticError) as caught:
        dosboxx.create_dynamic_vhd(str(tmp_path / "blank.qcow2"), "10M")
    assert caught.value.rule_id == "image.wrong-extension"


def test_create_dynamic_vhd_refuses_an_existing_file(tmp_path):
    path = tmp_path / "blank.vhd"
    path.write_bytes(b"")
    with pytest.raises(PreflightError) as caught:
        dosboxx.create_dynamic_vhd(str(path), "10M")
    assert caught.value.rule_id == "image.already-exists"


def test_create_dynamic_vhd_runs_vhdmake_and_returns_the_path(tmp_path):
    path = tmp_path / "blank.vhd"

    def fake_run(commands, *, action, target):
        assert commands == [f"VHDMAKE {path} 10M"]
        path.write_bytes(b"fake vhd")

    with mock.patch.object(dosboxx, "_run_dosbox_x_headless", fake_run):
        result = dosboxx.create_dynamic_vhd(str(path), "10M")
    assert result == str(path)


def test_create_dynamic_vhd_fails_closed_when_no_file_appears(tmp_path):
    path = tmp_path / "blank.vhd"
    with mock.patch.object(dosboxx, "_run_dosbox_x_headless",
                           lambda *a, **k: None):
        with pytest.raises(RunFailure) as caught:
            dosboxx.create_dynamic_vhd(str(path), "10M")
    assert caught.value.rule_id == "image.creation-failed"


def test_create_duplicate_vhd_is_a_plain_copy(tmp_path):
    base = tmp_path / "base.vhd"
    base.write_bytes(b"base contents")
    target = tmp_path / "copy.vhd"
    with mock.patch.object(dosboxx, "_run_dosbox_x_headless") as run:
        dosboxx.create_duplicate_vhd(str(target), str(base))
        run.assert_not_called()
    assert target.read_bytes() == b"base contents"


# -- carriers: change_medium's asymmetric refusals ---------------------

class _FakeClient:
    def __init__(self):
        self.calls = []

    def mount(self, drive, path):
        self.calls.append(("mount", drive, path))
        return 2

    def swap(self, drive, position=None):
        self.calls.append(("swap", drive, position))

    def eject(self, drive):
        self.calls.append(("eject", drive))


def _session(drives):
    return dosboxx.DosboxXSession(_FakeClient(), drives=drives)


def test_change_medium_ejects_a_cdrom():
    session = _session({"cdrom0": {"letter": "e", "medium": "cdrom",
                                   "mounted": True}})
    session.change_medium("cdrom0", path=None)
    assert session._client.calls == [("eject", "E")]


def test_change_medium_refuses_a_new_cdrom_image():
    session = _session({"cdrom0": {"letter": "e", "medium": "cdrom",
                                   "mounted": True}})
    with pytest.raises(PreflightError) as caught:
        session.change_medium("cdrom0", path="new.iso")
    assert caught.value.rule_id == "machine.change-medium-unsupported"


def test_change_medium_refuses_ejecting_a_floppy():
    session = _session({"floppy0": {"letter": "a", "medium": "floppy",
                                    "mounted": True}})
    with pytest.raises(PreflightError) as caught:
        session.change_medium("floppy0", path=None)
    assert caught.value.rule_id == "machine.change-medium-unsupported"


def test_change_medium_refuses_inserting_into_a_drive_that_started_empty():
    session = _session({"floppy0": {"letter": "a", "medium": "floppy",
                                    "mounted": False}})
    with pytest.raises(PreflightError) as caught:
        session.change_medium("floppy0", path="new.img")
    assert caught.value.rule_id == "machine.change-medium-unsupported"


def test_change_medium_mounts_then_swaps_an_already_mounted_floppy():
    session = _session({"floppy0": {"letter": "a", "medium": "floppy",
                                    "mounted": True}})
    session.change_medium("floppy0", path="new.img")
    assert session._client.calls == [
        ("mount", "A", "new.img"), ("swap", "A", 2)]


def test_change_medium_refuses_an_undeclared_drive():
    session = _session({})
    with pytest.raises(PreflightError) as caught:
        session.change_medium("floppy0", path="x.img")
    assert caught.value.rule_id == "machine.slot-not-declared"


# -- identity verification --------------------------------------------

class _IdentifyClient:
    def __init__(self, backend_id, auth_ok):
        self._backend_id = backend_id
        self._auth_ok = auth_ok

    def identify(self):
        return {"backend-id": self._backend_id}

    def auth(self, token):
        if not self._auth_ok:
            raise RunFailure("wrong token", rule_id="dosboxx.auth-failed")


def test_verify_vm_accepts_a_matching_authenticated_instance():
    dosboxx.verify_vm(_IdentifyClient("m", True), "m", _OUR_TOKEN)


def test_verify_vm_refuses_a_mismatched_backend_id():
    with pytest.raises(PreflightError) as caught:
        dosboxx.verify_vm(_IdentifyClient("other", True), "m", _OUR_TOKEN)
    assert caught.value.rule_id == "machine.identity-mismatch"


def test_verify_vm_refuses_a_failed_auth():
    with pytest.raises(PreflightError) as caught:
        dosboxx.verify_vm(_IdentifyClient("m", False), "m", _OUR_TOKEN)
    assert caught.value.rule_id == "machine.identity-mismatch"


# -- cpus: refused rather than silently dropped ------------------------

def test_more_than_one_cpu_is_refused_before_any_launch_work():
    state = {"id": "m-0", "cpus": 2, "drives": {}, "boot": []}
    with mock.patch.object(dosboxx, "find_dosbox_x",
                           side_effect=AssertionError(
                               "must not reach discovery")):
        with pytest.raises(PreflightError) as caught:
            dosboxx.launch_owned_dosbox_x(state, backend_dir="unused")
    assert caught.value.rule_id == "machine.cpus-unsupported"
