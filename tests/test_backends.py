# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for the backend adapter seam: capability, discovery, assignment.

These test the logic itself, without any real hypervisor involved:
what a requirement means when checked against a capability report,
what the priority walk picks, and what the unbuilt adapters claim
(nothing).
"""

from unittest import mock

import pytest

from reliquary import backend_stubs, backend_virtualbox, backends
from reliquary.backends import Capabilities, Requirements
from reliquary.errors import PreflightError, StaticError
from tests import fake_backend


def _requirements(**kwargs):
    return Requirements(**kwargs)


@pytest.fixture
def install():
    """Install adapters for a walk, and put the real ones back."""
    stack = []

    def installer(**adapters):
        for name, adapter in adapters.items():
            stack.append((name, backends._set_adapter(name, adapter)))

    yield installer
    for name, previous in stack:
        backends._set_adapter(name, previous)


# A capability is only ever reported, never faked — and when a
# requirement is unmet, the error names exactly what's missing.

def test_a_satisfiable_blueprint_leaves_nothing_unmet():
    adapter = fake_backend.FakeAdapter()
    assert adapter.unmet(_requirements(
        control_planes=("agentless-display",),
        media=("hdd", "cdrom"), controllers=("ide",),
        materialize=("new", "use"))) == ()


def test_each_unmet_requirement_is_named_one_by_one():
    adapter = fake_backend.FakeAdapter()
    missing = adapter.unmet(_requirements(
        control_planes=("vnc", "guest-agent"),
        controllers=("nvme",), materialize=("difference",)))
    assert missing == (
        "control plane 'vnc'",
        "control plane 'guest-agent'",
        "controller 'nvme'",
    )


def test_a_media_kind_the_backend_lacks_is_named():
    report = Capabilities(backend="hyperv", media=("hdd", "cdrom"))
    adapter = fake_backend.FakeAdapter("hyperv", capabilities=report)
    assert adapter.unmet(_requirements(media=("floppy",))) == (
        "floppy drives",)


def test_a_pointing_device_the_backend_lacks_is_named():
    report = Capabilities(backend="hyperv", pointing_devices=("mouse",))
    adapter = fake_backend.FakeAdapter("hyperv", capabilities=report)
    assert adapter.unmet(
        _requirements(pointing_device="tablet")) == (
        "pointing device 'tablet'",)


def test_no_declared_pointing_device_asks_nothing():
    # `pointing_device=None` is "the blueprint left it to its
    # default", never "the backend must supply nothing" — an empty
    # report still leaves this unmet.
    report = Capabilities(backend="hyperv")
    adapter = fake_backend.FakeAdapter("hyperv", capabilities=report)
    assert adapter.unmet(_requirements()) == ()


def test_a_network_model_the_backend_lacks_is_named():
    report = Capabilities(backend="hyperv", network_models=("pcnet",))
    adapter = fake_backend.FakeAdapter("hyperv", capabilities=report)
    assert adapter.unmet(_requirements(network_models=("ne2k",))) == (
        "network device 'ne2k'",)


def test_a_network_attachment_the_backend_lacks_is_named():
    report = Capabilities(backend="hyperv", network_attachments=("nat",))
    adapter = fake_backend.FakeAdapter("hyperv", capabilities=report)
    assert adapter.unmet(_requirements(network_attachments=("bridged",))) == (
        "network attachment 'bridged'",)


def test_no_declared_network_asks_nothing():
    report = Capabilities(backend="hyperv")
    adapter = fake_backend.FakeAdapter("hyperv", capabilities=report)
    assert adapter.unmet(_requirements()) == ()


def test_a_share_model_the_backend_lacks_is_named():
    report = Capabilities(backend="hyperv", share_models=("vvfat",))
    adapter = fake_backend.FakeAdapter("hyperv", capabilities=report)
    assert adapter.unmet(_requirements(share_models=("9pfs",))) == (
        "share model '9pfs'",)


def test_an_unstated_share_needs_a_live_default():
    # `share_models` alone doesn't cover this: an unstated share is
    # judged against `share_default`, never silently matched to
    # whatever the backend happens to render (vvfat included).
    report = Capabilities(backend="hyperv", share_models=("vvfat",))
    adapter = fake_backend.FakeAdapter("hyperv", capabilities=report)
    assert adapter.unmet(_requirements(share_unstated=True)) == (
        "a share with no stated model (this backend has no live "
        "default)",)


def test_an_unstated_share_is_satisfied_by_a_live_default():
    report = Capabilities(backend="hyperv", share_default="9pfs")
    adapter = fake_backend.FakeAdapter("hyperv", capabilities=report)
    assert adapter.unmet(_requirements(share_unstated=True)) == ()


def test_no_declared_share_asks_nothing():
    report = Capabilities(backend="hyperv")
    adapter = fake_backend.FakeAdapter("hyperv", capabilities=report)
    assert adapter.unmet(_requirements()) == ()


def test_the_capability_check_asks_about_the_guest_platform():
    """A backend whose tooling differs by guest architecture has to be
    asked about the right one (F69).

    QEMU's live share transports are build options, so which of them
    exist is a property of one installed binary — and QEMU installs
    one binary per architecture. Asking the report without saying
    which guest this is for would judge a machine against a binary it
    will never launch on.
    """
    adapter = fake_backend.FakeAdapter("hyperv")
    adapter.unmet(_requirements(platform="winnt"))
    assert adapter.capability_platforms == ["winnt"]


def test_pointer_capable_defaults_to_false():
    # The honest default, matching `capture_format`'s default of
    # `None`: until a backend is actually built, it claims no
    # capability at all (P11).
    adapter = backends.BackendAdapter()
    assert adapter.pointer_capable("vnc") is False


# A settings section is either honored or refused — never silently
# carried along and ignored.
#
# This covers only the adapter's declared key set. What an adapter
# does with the keys it defines is its own business (QEMU's is
# covered in `test_backend_qemu.py`); what this file guarantees is
# that a key no adapter defines never reaches a machine.

def test_an_adapter_reading_no_settings_refuses_every_key():
    # The honest default (P11): a settings section the adapter
    # cannot honor is refused, instead of being silently kept as
    # configuration that nothing will ever apply. VirtualBox still
    # reads no settings keys (F50); neither do the stubs.
    adapter = backend_virtualbox.VirtualBoxAdapter()
    assert adapter.settings_keys == ()
    with pytest.raises(StaticError) as caught:
        adapter.validate_settings({"machine": "pc"})
    assert caught.value.rule_id == "machine.settings-unknown-key"
    assert "reads no settings" in str(caught.value)
    assert "virtualbox" in str(caught.value)


def test_a_key_outside_the_vocabulary_names_the_vocabulary():
    adapter = fake_backend.FakeAdapter(settings_keys=("machine",))
    with pytest.raises(StaticError) as caught:
        adapter.validate_settings({"cpus": 4})
    assert caught.value.rule_id == "machine.settings-unknown-key"
    assert "'cpus'" in str(caught.value)
    assert "the qemu keys are machine" in str(caught.value)


@pytest.mark.parametrize("section", [{"machine": "pc"}, {}, None],
                         ids=["declared-key", "empty", "absent"])
def test_a_declared_key_and_an_empty_section_are_accepted(section):
    adapter = fake_backend.FakeAdapter(settings_keys=("machine",))
    assert adapter.validate_settings(section) is None


# Assignment walks the priority order and takes the first fit.

def test_the_priority_order_is_the_decided_one():
    # D66: ranked by agentless scriptability, not host ubiquity.
    assert backends.PRIORITY == ("qemu", "virtualbox", "vmware", "hyperv")


def test_the_first_available_and_capable_backend_wins(install):
    install(qemu=fake_backend.FakeAdapter("qemu", available=False),
            virtualbox=fake_backend.FakeAdapter("virtualbox"))
    assert backends.assign(_requirements()) == "virtualbox"


def test_availability_alone_never_wins_a_walk(install):
    # An available backend that cannot serve the blueprint is
    # passed over; the order breaks ties among the capable, it
    # does not stand in for a capability check (P11).
    able = fake_backend.FakeAdapter("virtualbox")
    unable = fake_backend.FakeAdapter(
        "qemu", capabilities=Capabilities(backend="qemu"))
    install(qemu=unable, virtualbox=able)
    assert backends.assign(_requirements(media=("floppy",))) == "virtualbox"


def test_nothing_capable_fails_closed_listing_every_refusal(install):
    install(
        qemu=fake_backend.FakeAdapter("qemu", available=False),
        virtualbox=fake_backend.FakeAdapter(
            "virtualbox", capabilities=Capabilities(backend="virtualbox")),
        vmware=fake_backend.FakeAdapter("vmware", available=False),
        hyperv=fake_backend.FakeAdapter("hyperv", available=False))
    with pytest.raises(PreflightError) as caught:
        backends.assign(_requirements(media=("floppy",)))
    message = str(caught.value)
    for name in backends.PRIORITY:
        assert name in message
    assert "floppy drives" in message


def test_a_declared_backend_pins_the_choice_and_skips_the_walk(install):
    qemu = fake_backend.FakeAdapter("qemu")
    install(qemu=qemu, virtualbox=fake_backend.FakeAdapter("virtualbox"))
    assert backends.assign(_requirements(),
                           declared="virtualbox") == "virtualbox"
    # The pinned backend alone is probed.
    assert qemu.sessions == []


def test_a_pinned_unavailable_backend_fails_closed(install):
    install(vmware=fake_backend.FakeAdapter("vmware", available=False))
    with pytest.raises(PreflightError) as caught:
        backends.assign(_requirements(), declared="vmware")
    assert "'vmware'" in str(caught.value)
    assert "not available" in str(caught.value)


def test_a_pinned_incapable_backend_names_what_it_cannot_do(install):
    install(hyperv=fake_backend.FakeAdapter(
        "hyperv", capabilities=Capabilities(backend="hyperv")))
    with pytest.raises(PreflightError) as caught:
        backends.assign(
            _requirements(control_planes=("agentless-display",)),
            declared="hyperv")
    assert "control plane 'agentless-display'" in str(caught.value)


def test_a_narrowed_backend_skips_the_walk_like_a_declared_one(install):
    qemu = fake_backend.FakeAdapter("qemu")
    install(qemu=qemu, virtualbox=fake_backend.FakeAdapter("virtualbox"))
    assert backends.assign(_requirements(),
                           narrowed="virtualbox") == "virtualbox"


def test_a_narrowed_backend_that_cannot_serve_says_what_narrowed_it(install):
    # The diagnostic has to distinguish the two ways a walk becomes
    # a walk of one: this blueprint declared no backend, so telling
    # the author it "pins" one would send them looking for a field
    # that is not there.
    install(vmware=fake_backend.FakeAdapter("vmware", available=False))
    with pytest.raises(PreflightError) as caught:
        backends.assign(_requirements(), narrowed="vmware")
    message = str(caught.value)
    assert "backend-settings" in message
    assert "narrows assignment" in message
    assert "pins" not in message


def test_a_declared_backend_outranks_a_narrowing_section(install):
    install(qemu=fake_backend.FakeAdapter("qemu"),
            virtualbox=fake_backend.FakeAdapter("virtualbox"))
    assert backends.assign(_requirements(), declared="qemu",
                           narrowed="virtualbox") == "qemu"


def test_an_unknown_backend_name_is_a_static_error():
    with pytest.raises(StaticError) as caught:
        backends.adapter("bochs")
    assert "bochs" in str(caught.value)


# Discovery: what this host has, and what each adapter claims.

def test_discovery_reports_every_backend_in_priority_order():
    # QEMU's probe runs a binary, which unit tests never do; the
    # remaining stubs probe the filesystem alone, so they answer
    # for real here. VirtualBox is faked so discovery stays
    # hypervisor-free.
    with fake_backend.installed():
        with fake_backend.installed(
                fake_backend.FakeAdapter("virtualbox"),
                name="virtualbox"):
            probes = backends.discover()
    assert [probe.backend for probe in probes] == list(backends.PRIORITY)


def test_a_stub_claims_no_capability_even_where_it_is_installed():
    # P11 at this seam: an untested capability is an unclaimed
    # one, so an installed VMware is still passed over by the
    # walk until its adapter is built.
    adapter = backend_stubs.VMwareAdapter()
    with mock.patch.object(backend_stubs, "_which",
                           return_value="C:/vmrun.exe"):
        probe = adapter.discover()
    assert probe.available
    assert "unbuilt" in probe.detail
    assert adapter.capabilities().control_planes == ()
    assert adapter.unmet(_requirements(
        control_planes=("agentless-display",))) == (
        "control plane 'agentless-display'",)


def test_virtualbox_claims_agentless_display():
    # F52: the carriers are real, so the capability is claimed.
    adapter = backend_virtualbox.VirtualBoxAdapter()
    assert adapter.capabilities().control_planes == ("agentless-display",)
    assert adapter.unmet(_requirements(
        control_planes=("agentless-display",),
        media=("hdd",), controllers=("ide",),
        materialize=("new",))) == ()


def test_an_absent_stub_backend_says_what_it_looked_for():
    adapter = backend_stubs.VMwareAdapter()
    with mock.patch.object(backend_stubs, "_which", return_value=None):
        probe = adapter.discover()
    assert not probe.available
    assert "vmrun" in probe.detail


def test_the_unbuilt_operations_raise_the_abstract_method_error():
    # Assignment should never actually call these on an unbuilt
    # backend, but they still enforce Python's own abstract-method
    # contract; a *reachable* gap is instead a preflight failure
    # naming the backend (see the assignment checks above).
    adapter = backend_stubs.HyperVAdapter()
    with pytest.raises(NotImplementedError):
        adapter.start({}, machine_dir="x", backend_dir="y")
    with pytest.raises(NotImplementedError):
        adapter.image_path("root", "stem")


# Every adapter records a VM the same way (the ownership doctrine).

def test_the_record_names_backend_id_token_and_endpoint():
    record = backends.identity(
        "qemu", "reliquary-plain-0", "token-1", {"port": 4321}, pid=99)
    assert record == {
        "backend": "qemu",
        "backend-id": "reliquary-plain-0",
        "token": "token-1",
        "endpoint": {"port": 4321},
        "pid": 99,
    }


def test_a_backend_with_no_process_records_none():
    record = backends.identity(
        "hyperv", "{9f2c-...}", "token-2", {"vmid": "{9f2c-...}"})
    assert "pid" not in record
