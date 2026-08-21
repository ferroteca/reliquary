# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""One contract over the adapter seam, driven against every backend.

**P25**: a seam requirement honored by one backend's tests and quietly
missing from the other's is a requirement nobody holds. These are the
*shared* expectations — what the seam states rather than what any
hypervisor knows — written once and parametrised over every built
adapter, so each check is a collected node named for the backend it
judged and a third backend inherits the whole contract by adding one
driver rather than by copying a file (F59).

**A driver is how a backend is stood up on a fake host**, and nothing
more: where its executable is found, where its font lives, and how a
stop is aimed at a VM whose identity does not match. The mechanics
differ completely — QMP against `VBoxManage` — which is the point:
the expectations do not.

What stays in `test_backend_qemu` and `test_backend_virtualbox` is
what only that backend knows — qcow2 against VDI, the argv or the
verbs each renders, QMP carriers against scancodes.
"""

import contextlib
import os
from unittest import mock

import pytest

from reliquary import backend_qemu as qemu_module
from reliquary import backend_virtualbox as vbox
from reliquary import backends
from reliquary.errors import PreflightError, StaticError
from tests.vga_bank import vga_bank

_OTHER_UUID = "99999999-9999-9999-9999-999999999999"
_OUR_UUID = "11111111-2222-3333-4444-555555555555"


def _completed(stdout="", stderr="", returncode=0):
    result = mock.Mock()
    result.stdout = stdout
    result.stderr = stderr
    result.returncode = returncode
    return result


class _QemuDriver:
    """QEMU on a fake host: a binary path and a vgabios beside it."""

    name = "qemu"
    extension = ".qcow2"
    vvfat = True
    control_planes = ("agentless-display", "vnc")
    #: The command that would reach a VM the identity check must stop
    #: short of.
    destructive = "quit"

    def executable(self, root):
        return os.path.join(root, "qemu-system-i386")

    @contextlib.contextmanager
    def found(self, root):
        # The version probe runs the binary, which no unit test does;
        # what a QEMU that will not report one does is QEMU's own
        # check rather than the seam's.
        with mock.patch.object(qemu_module, "find_qemu",
                               return_value=self.executable(root)), \
                mock.patch.object(qemu_module, "_qemu_version",
                                  return_value=None):
            yield

    def absent(self):
        return mock.patch.object(
            qemu_module, "find_qemu",
            side_effect=PreflightError(
                "qemu-system-i386 not found",
                rule_id="machine.backend-not-found"))

    def unreachable(self):
        """Fail loudly if the install is consulted at all."""
        return mock.patch.object(
            qemu_module, "find_qemu",
            side_effect=AssertionError("must not re-extract"))

    def install_font(self, root, payload):
        share = os.path.join(root, "share", "qemu")
        os.makedirs(share, exist_ok=True)
        with open(os.path.join(share, "vgabios-stdvga.bin"), "wb") as handle:
            handle.write(payload)

    def glyph_banks(self, cache=None):
        return qemu_module.guest_glyph_banks(cache)

    @contextlib.contextmanager
    def mismatched_stop(self):
        """A stop aimed at a QMP server that is not our VM."""
        commands = []

        class _Qmp:
            def __init__(self, port):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                pass

            def cmd(self, name, **arguments):
                commands.append(name)
                if name == "query-name":
                    return {"name": "unrelated-vm"}
                if name == "query-uuid":
                    return {"UUID": _OTHER_UUID}
                return None

        identity = {"backend": "qemu",
                    "backend-id": "reliquary-plain-0",
                    "token": _OUR_UUID,
                    "endpoint": {"port": 54321}, "pid": 1234}
        with mock.patch.object(qemu_module, "Qmp", _Qmp):
            yield (lambda: qemu_module.stop(identity)), commands


class _VirtualBoxDriver:
    """VirtualBox on a fake host: VBoxManage and the DLL beside it."""

    name = "virtualbox"
    extension = ".vdi"
    vvfat = False
    control_planes = ("agentless-display",)
    destructive = "controlvm"

    def executable(self, root):
        return os.path.join(root, "VBoxManage.exe")

    def found(self, root):
        return mock.patch.object(vbox, "find_vboxmanage",
                                 return_value=self.executable(root))

    def absent(self):
        return mock.patch.object(
            vbox, "find_vboxmanage",
            side_effect=PreflightError(
                "VBoxManage not found",
                rule_id="machine.backend-not-found"))

    def unreachable(self):
        return mock.patch.object(
            vbox, "find_vboxmanage",
            side_effect=AssertionError("must not re-extract"))

    def install_font(self, root, payload):
        with open(os.path.join(root, "VBoxDD2.dll"), "wb") as handle:
            handle.write(payload)

    def glyph_banks(self, cache=None):
        return vbox.guest_glyph_banks(cache)

    @contextlib.contextmanager
    def mismatched_stop(self):
        """A stop aimed at a registered VM carrying another UUID."""
        commands = []

        def run(args, **kwargs):
            commands.append(args[1])
            if args[1] == "showvminfo":
                return _completed(
                    stdout=f'name="reliquary-plain-0"\n'
                           f'UUID="{_OTHER_UUID}"\n'
                           f'VMState="running"\n')
            return _completed()

        vm = {"backend": "virtualbox", "backend-id": _OUR_UUID,
              "token": _OUR_UUID, "endpoint": {"name": "reliquary-plain-0"}}
        with mock.patch.object(vbox, "find_vboxmanage",
                               return_value="VBoxManage"), \
                mock.patch("subprocess.run", side_effect=run):
            yield (lambda: vbox.stop(vm)), commands


DRIVERS = (_QemuDriver(), _VirtualBoxDriver())


@pytest.fixture(params=DRIVERS, ids=[driver.name for driver in DRIVERS])
def driver(request):
    return request.param


@pytest.fixture
def adapter(driver):
    return backends.adapter(driver.name)


def test_the_adapter_answers_to_one_name_everywhere(driver, adapter):
    """The registry, the report and the probe agree on the name."""
    assert adapter.name == driver.name
    assert adapter.capabilities().backend == driver.name
    with driver.absent():
        assert adapter.discover().backend == driver.name


def test_the_capability_report_claims_only_what_is_built(driver, adapter):
    # Both adapters serve the same DOS machine today; where they
    # genuinely differ — vvfat, and the VNC plane QEMU alone wires —
    # the driver states the claim so a backend cannot quietly widen it.
    report = adapter.capabilities()
    assert report.control_planes == driver.control_planes
    assert report.media == ("floppy", "hdd", "cdrom")
    assert report.controllers == ("ide",)
    assert report.materialize == ("new", "difference", "copy", "use")
    assert report.vvfat is driver.vvfat


def test_an_image_is_named_in_the_backends_own_format(driver, adapter,
                                                      tmp_path):
    root = str(tmp_path)
    path = adapter.image_path(root, "blank")
    assert path == os.path.join(root, "blank" + driver.extension)


def test_a_settings_key_the_adapter_does_not_define_is_refused(adapter):
    # Whatever an adapter's vocabulary is — QEMU's two keys or
    # VirtualBox's none — a key outside it never reaches a machine.
    with pytest.raises(StaticError) as caught:
        adapter.validate_settings({"nonsense": True})
    assert caught.value.rule_id == "machine.settings-unknown-key"
    assert "nonsense" in str(caught.value)


def test_discovery_reports_the_binary_it_found(driver, adapter, tmp_path):
    root = str(tmp_path)
    with driver.found(root):
        probe = adapter.discover()
    assert probe.available
    assert probe.executable == driver.executable(root)
    assert probe.home == root
    assert driver.executable(root) in probe.detail


def test_discovery_reports_absence_with_its_reason_and_never_raises(
        driver, adapter):
    with driver.absent():
        probe = adapter.discover()
    assert not probe.available
    assert "not found" in probe.detail


def test_the_guest_font_is_read_off_the_installation(driver, tmp_path):
    """The glyphs belong to the installed emulator, not to Reliquary.

    The fixture embeds Reliquary's *own* bank in a stand-in binary, so
    the suite carries no other project's font while still proving the
    adapter reads one out of its install.
    """
    own = vga_bank()
    root = str(tmp_path)
    driver.install_font(root, b"\x11" * 500 + own + b"\x22" * 30)
    with driver.found(root):
        assert driver.glyph_banks() == (own,)


def test_the_font_is_cached_under_the_backends_support_dir(driver,
                                                           tmp_path):
    own = vga_bank()
    root = str(tmp_path / "install")
    cache = str(tmp_path / "cache")
    os.makedirs(root)
    driver.install_font(root, b"\x11" * 500 + own + b"\x22" * 30)
    with driver.found(root):
        assert driver.glyph_banks(cache) == (own,)

    written = os.path.join(cache, "support", driver.name,
                           "cp437-8x16-banks.bin")
    assert os.path.isfile(written)
    with open(written, "rb") as handle:
        assert handle.read() == own

    # Served from the cache now: the install is not consulted at all.
    with driver.unreachable():
        assert driver.glyph_banks(cache) == (own,)


def test_an_installation_with_no_font_fails_closed(driver, tmp_path):
    root = str(tmp_path)
    driver.install_font(root, b"\x00" * 9000)
    with driver.found(root):
        with pytest.raises(PreflightError) as caught:
            driver.glyph_banks()
    assert caught.value.rule_id == "recognize.font-not-found"


def test_a_stop_never_reaches_a_vm_whose_identity_differs(driver):
    """The ownership doctrine, stated once for every backend.

    An addressable endpoint outlives its owner, so the recorded
    identity is verified before any command is sent — and the refusal
    happens *before* the destructive one.

    The two adapters raise different ids here today
    (`machine.identity-mismatch` against
    `machine.vm-identity-mismatch`), so the contract judges the
    behavior and the wording rather than the id; whether one rule
    should keep one id across the seam is a surface question, not this
    check's.
    """
    with driver.mismatched_stop() as (stop, commands):
        with pytest.raises(PreflightError) as caught:
            stop()
    assert "identity mismatch" in str(caught.value)
    assert driver.destructive not in commands
