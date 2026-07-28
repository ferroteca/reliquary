# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Tests for the backend adapter seam: capability, discovery, assignment.

The seam's own arithmetic, judged without any hypervisor: what a
requirement means against a capability report, what the priority walk
picks, and what the three unbuilt adapters claim (nothing).
"""

import unittest
from unittest import mock

from reliquary import backend_stubs, backends
from reliquary.backends import Capabilities, Requirements
from reliquary.errors import PreflightError, StaticError
from reliquary_tests import fake_backend


def _requirements(**kwargs):
    return Requirements(**kwargs)


class CapabilityReportTests(unittest.TestCase):
    """Reported, never emulated — and the refusal names the gap."""

    def setUp(self):
        self.adapter = fake_backend.FakeAdapter()

    def test_a_satisfiable_blueprint_leaves_nothing_unmet(self):
        self.assertEqual(
            self.adapter.unmet(_requirements(
                control_planes=("agentless-display",),
                media=("hdd", "cdrom"), controllers=("ide",),
                materialize=("new", "use"))),
            ())

    def test_each_unmet_requirement_is_named_one_by_one(self):
        missing = self.adapter.unmet(_requirements(
            control_planes=("vnc", "guest-agent"),
            controllers=("nvme",), materialize=("difference",)))
        self.assertEqual(missing, (
            "control plane 'vnc'",
            "control plane 'guest-agent'",
            "controller 'nvme'",
        ))

    def test_a_media_kind_the_backend_lacks_is_named(self):
        report = Capabilities(backend="hyperv", media=("hdd", "cdrom"))
        adapter = fake_backend.FakeAdapter("hyperv", capabilities=report)
        self.assertEqual(adapter.unmet(_requirements(media=("floppy",))),
                         ("floppy drives",))


class AssignmentTests(unittest.TestCase):
    """Assignment walks the priority order and takes the first fit."""

    def _install(self, **adapters):
        stack = []
        for name, adapter in adapters.items():
            previous = backends._set_adapter(name, adapter)
            stack.append((name, previous))
        self.addCleanup(
            lambda: [backends._set_adapter(name, previous)
                     for name, previous in stack])

    def test_the_priority_order_is_the_decided_one(self):
        # D66: ranked by agentless scriptability, not host ubiquity.
        self.assertEqual(backends.PRIORITY,
                         ("qemu", "virtualbox", "vmware", "hyperv"))

    def test_the_first_available_and_capable_backend_wins(self):
        self._install(qemu=fake_backend.FakeAdapter("qemu",
                                                    available=False),
                      virtualbox=fake_backend.FakeAdapter("virtualbox"))
        self.assertEqual(backends.assign(_requirements()), "virtualbox")

    def test_availability_alone_never_wins_a_walk(self):
        # An available backend that cannot serve the blueprint is
        # passed over; the order breaks ties among the capable, it
        # does not stand in for a capability check (P11).
        able = fake_backend.FakeAdapter("virtualbox")
        unable = fake_backend.FakeAdapter(
            "qemu", capabilities=Capabilities(backend="qemu"))
        self._install(qemu=unable, virtualbox=able)
        self.assertEqual(
            backends.assign(_requirements(media=("floppy",))),
            "virtualbox")

    def test_nothing_capable_fails_closed_listing_every_refusal(self):
        self._install(
            qemu=fake_backend.FakeAdapter("qemu", available=False),
            virtualbox=fake_backend.FakeAdapter(
                "virtualbox", capabilities=Capabilities(
                    backend="virtualbox")),
            vmware=fake_backend.FakeAdapter("vmware", available=False),
            hyperv=fake_backend.FakeAdapter("hyperv", available=False))
        with self.assertRaises(PreflightError) as caught:
            backends.assign(_requirements(media=("floppy",)))
        message = str(caught.exception)
        for name in backends.PRIORITY:
            self.assertIn(name, message)
        self.assertIn("floppy drives", message)

    def test_a_declared_backend_pins_the_choice_and_skips_the_walk(self):
        qemu = fake_backend.FakeAdapter("qemu")
        self._install(qemu=qemu,
                      virtualbox=fake_backend.FakeAdapter("virtualbox"))
        self.assertEqual(
            backends.assign(_requirements(), declared="virtualbox"),
            "virtualbox")
        # The pinned backend alone is probed.
        self.assertEqual(qemu.sessions, [])

    def test_a_pinned_unavailable_backend_fails_closed(self):
        self._install(vmware=fake_backend.FakeAdapter("vmware",
                                                      available=False))
        with self.assertRaises(PreflightError) as caught:
            backends.assign(_requirements(), declared="vmware")
        self.assertIn("'vmware'", str(caught.exception))
        self.assertIn("not available", str(caught.exception))

    def test_a_pinned_incapable_backend_names_what_it_cannot_do(self):
        self._install(hyperv=fake_backend.FakeAdapter(
            "hyperv", capabilities=Capabilities(backend="hyperv")))
        with self.assertRaises(PreflightError) as caught:
            backends.assign(
                _requirements(control_planes=("agentless-display",)),
                declared="hyperv")
        self.assertIn("control plane 'agentless-display'",
                      str(caught.exception))

    def test_an_unknown_backend_name_is_a_static_error(self):
        with self.assertRaises(StaticError) as caught:
            backends.adapter("bochs")
        self.assertIn("bochs", str(caught.exception))


class DiscoveryTests(unittest.TestCase):
    def test_discovery_reports_every_backend_in_priority_order(self):
        # QEMU's probe runs a binary, which unit tests never do; the
        # three stubs probe the filesystem alone, so they answer for
        # real here.
        with fake_backend.installed():
            probes = backends.discover()
        self.assertEqual([probe.backend for probe in probes],
                         list(backends.PRIORITY))

    def test_a_stub_claims_no_capability_even_where_it_is_installed(self):
        # P11 at this seam: an untested capability is an unclaimed
        # one, so an installed VirtualBox is still passed over by the
        # walk until its adapter is built.
        adapter = backend_stubs.VirtualBoxAdapter()
        with mock.patch.object(backend_stubs, "_which",
                               return_value="C:/VBoxManage.exe"):
            probe = adapter.discover()
        self.assertTrue(probe.available)
        self.assertIn("unbuilt", probe.detail)
        self.assertEqual(adapter.capabilities().control_planes, ())
        self.assertEqual(
            adapter.unmet(_requirements(
                control_planes=("agentless-display",))),
            ("control plane 'agentless-display'",))

    def test_an_absent_stub_backend_says_what_it_looked_for(self):
        adapter = backend_stubs.VMwareAdapter()
        with mock.patch.object(backend_stubs, "_which", return_value=None):
            probe = adapter.discover()
        self.assertFalse(probe.available)
        self.assertIn("vmrun", probe.detail)

    def test_the_unbuilt_operations_raise_the_abstract_method_error(self):
        # The operations assignment can never reach keep the
        # language's own invariant; a *reachable* gap is a preflight
        # failure naming the backend (see AssignmentTests).
        adapter = backend_stubs.HyperVAdapter()
        with self.assertRaises(NotImplementedError):
            adapter.start({}, machine_dir="x", backend_dir="y")
        with self.assertRaises(NotImplementedError):
            adapter.image_path("root", "stem")


class IdentityRecordTests(unittest.TestCase):
    """Every adapter records a VM the same way (the ownership doctrine)."""

    def test_the_record_names_backend_id_token_and_endpoint(self):
        record = backends.identity(
            "qemu", "reliquary-plain-0", "token-1", {"port": 4321},
            pid=99)
        self.assertEqual(record, {
            "backend": "qemu",
            "backend-id": "reliquary-plain-0",
            "token": "token-1",
            "endpoint": {"port": 4321},
            "pid": 99,
        })

    def test_a_backend_with_no_process_records_none(self):
        record = backends.identity(
            "hyperv", "{9f2c-...}", "token-2", {"vmid": "{9f2c-...}"})
        self.assertNotIn("pid", record)


if __name__ == "__main__":
    unittest.main()
