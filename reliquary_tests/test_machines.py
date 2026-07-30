# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for machine materialization and cached-state management.

The composed model: a machine's drive names a media, and the media owns
materialization (new/use/difference/copy). Tests write a composed
``.rlqb`` into the home and drive ``create_machine``; ``use`` media point
at a real local ISO (attached in place, no fetch), and blank/differencing
image creation is mocked.
"""

import contextlib
import json
import os
import tempfile
import unittest
from unittest import mock

from reliquary import platform_dos
from reliquary import machines as machines_module
from reliquary.errors import (PreflightError, RunFailure, StaticError,
                              WaitExpired, exit_code)
from reliquary.interaction_agentless import (AgentlessGuestExec,
                                             _command_output)
from reliquary.machines import exec as machines_exec
from reliquary.machines import (apply_blueprint, create_machine,
                                describe_drives,
                                destroy_machine, eject_media, get_file,
                                get_files, get_machine_dir, get_machine_var,
                                insert_media, list_files, list_machines,
                                load_machine_state, machine_dir_path,
                                mark_stopped, put_file, put_files,
                                recreate_machine, refresh_drives,
                                resolve_machine,
                                set_boot_order, set_machine_var,
                                start_machine, stop_machine,
                                wait_machine_var)
from reliquary.backends import Capabilities
from reliquary_tests import fake_backend, fat_image

_BLANK = {"name": "blank", "materialize": "new", "size": "20M"}


class _HomeCase(unittest.TestCase):
    def setUp(self):
        self.workdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.workdir.cleanup)
        self.home = self.workdir.name
        self.iso_path = os.path.join(self.home, "live.iso")
        with open(self.iso_path, "wb") as handle:
            handle.write(b"ISO-CONTENT")
        # The machine model is driven against an adapter double: no
        # hypervisor is probed, no image is written, and nothing is
        # launched. What QEMU's own adapter does with the same calls
        # is test_backend_qemu.py's.
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        self.backend = stack.enter_context(fake_backend.installed())

    def _images(self):
        """(image name, mode, size) for every image materialized."""
        return sorted((os.path.basename(path), mode, size)
                      for path, mode, size, _base in self.backend.images)

    def _livecd(self):
        return {"name": "freedos-livecd", "materialize": "use",
                "read-only": True, "location": {"local": self.iso_path}}

    def _write(self, name, machine, media=None):
        specs = [dict(machine, type="machine", name=name)]
        specs.extend(dict(spec, type="media") for spec in (media or ()))
        bpdir = os.path.join(self.home, "blueprints")
        os.makedirs(bpdir, exist_ok=True)
        with open(os.path.join(bpdir, f"{name}.rlqb"), "w",
                  encoding="utf-8") as handle:
            json.dump(specs, handle)

    def _create(self, name, machine, media=None):
        self._write(name, machine, media)
        return create_machine(name, context=self.home)

    def _state(self, machine_id):
        return load_machine_state(machine_id, self.home)

    def _identity(self, machine_id):
        from reliquary import backends
        return backends.identity(
            "qemu", f"reliquary-{machine_id}", "1" * 32,
            {"port": 54321}, pid=1234)

    def _force(self, machine_id, phase, *, vm=False):
        state = self._state(machine_id)
        state["phase"] = phase
        if vm:
            # The live-VM identity is folded into machine.json now.
            state["vm"] = self._identity(machine_id)
        path = os.path.join(machine_dir_path(machine_id, self.home),
                            "machine.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(state, handle)


class MaterializationTests(_HomeCase):
    def test_create_populates_the_machine_cache_directory(self):
        machine_id = self._create(
            "freedos", {"platform": "dos", "drives": {"hdd0": "blank"}},
            media=[_BLANK])
        root = machine_dir_path(machine_id, self.home)
        self.assertTrue(os.path.isfile(
            os.path.join(root, "machine.json")))
        self.assertTrue(os.path.isdir(os.path.join(root, "media")))

    def test_state_records_bookkeeping_and_defaults(self):
        machine_id = self._create(
            "freedos", {"platform": "dos", "drives": {"hdd0": "blank"},
                        "description": "A description.",
                        "scripts": {"install": "install-script"}},
            media=[_BLANK])
        state = self._state(machine_id)
        self.assertEqual(state["id"], machine_id)
        self.assertEqual(state["blueprint"], "freedos")
        self.assertEqual(state["phase"], "ready")
        self.assertEqual(state["backend"], "qemu")
        self.assertEqual(state["memory"], 16)
        self.assertEqual(state["cpus"], 1)
        self.assertEqual(state["control-planes"], ["agentless-display"])
        self.assertEqual(state["scripts"], {"install": "install-script"})
        self.assertEqual(state["boot"], ["hdd0"])
        self.assertEqual(state["backend-id"], f"reliquary-{machine_id}")
        self.assertTrue(state["blueprint-digest"].startswith("sha256:"))

    def test_optional_fields_absent(self):
        machine_id = self._create("minimal", {"platform": "dos"})
        state = self._state(machine_id)
        self.assertEqual(state["memory"], 16)
        self.assertIsNone(state["description"])
        self.assertEqual(state["scripts"], {})
        self.assertEqual(state["drives"], {})
        self.assertEqual(state["boot"], [])

    def test_new_media_creates_qcow2_image(self):
        self._write("sized", {"platform": "dos",
                              "drives": {"hdd0": "blank", "floppy1": "boot"}},
                   media=[_BLANK,
                          {"name": "boot", "materialize": "new",
                           "size": "720K"}])
        machine_id = create_machine("sized", context=self.home)
        # Per-machine images are named for the media, not the slot,
        # and the adapter names the file — the extension is its
        # native format's, never the machine model's.
        self.assertEqual(self._images(), [("blank.qcow2", "new", "20M"),
                                          ("boot.qcow2", "new", "720K")])
        state = self._state(machine_id)
        self.assertEqual(state["drives"]["hdd0"]["size"], "20M")
        self.assertEqual(state["drives"]["hdd0"]["materialize"], "new")

    def test_use_media_attaches_the_payload_path(self):
        machine_id = self._create(
            "with-media", {"platform": "dos",
                           "drives": {"hdd0": "blank", "cdrom0": "freedos-livecd"},
                           "boot": ["cdrom0", "hdd0"]},
            media=[_BLANK, self._livecd()])
        cdrom = self._state(machine_id)["drives"]["cdrom0"]
        self.assertEqual(cdrom["media"], "freedos-livecd")
        self.assertEqual(cdrom["materialize"], "use")
        self.assertEqual(os.path.normpath(cdrom["path"]),
                         os.path.normpath(self.iso_path))

    def test_difference_media_materializes_an_overlay(self):
        self._write("based", {"platform": "dos", "drives": {"hdd0": "base"}},
                   media=[{"name": "base", "materialize": "difference",
                           "location": {"local": self.iso_path}}])
        machine_id = create_machine("based", context=self.home)
        path, mode, _size, base = self.backend.images[0]
        self.assertEqual(os.path.basename(path), "base.qcow2")
        self.assertEqual(mode, "difference")
        self.assertEqual(base, self.iso_path)
        self.assertEqual(self._state(machine_id)["drives"]["hdd0"][
            "materialize"], "difference")

    def test_copy_media_materializes_a_duplicate(self):
        self._write("dup", {"platform": "dos", "drives": {"hdd0": "base"}},
                   media=[{"name": "base", "materialize": "copy",
                           "location": {"local": self.iso_path}}])
        machine_id = create_machine("dup", context=self.home)
        self.assertEqual([mode for _p, mode, _s, _b in self.backend.images],
                         ["copy"])
        self.assertEqual(self._state(machine_id)["drives"]["hdd0"][
            "materialize"], "copy")

    def test_directory_source_media_attaches_the_directory(self):
        work = os.path.join(self.home, "work")
        os.makedirs(work)
        machine_id = self._create(
            "hd", {"platform": "dos", "drives": {"hdd0": "shared"}},
            media=[{"name": "shared", "materialize": "use",
                    "location": {"local": work}}])
        drive = self._state(machine_id)["drives"]["hdd0"]
        # The state records the host directory itself; rendering it as
        # a vvfat drive is the adapter's (test_backend_qemu.py).
        self.assertEqual(os.path.normpath(drive["path"]),
                         os.path.normpath(work))

    def test_cdrom_rejects_a_new_media(self):
        self._write("bad", {"platform": "dos", "drives": {"cdrom0": "blank"}},
                   media=[_BLANK])
        with self.assertRaises(StaticError) as caught:
            create_machine("bad", context=self.home)
        self.assertIn("cdrom", str(caught.exception))

    def test_a_controller_no_backend_wires_fails_closed(self):
        # Capabilities are reported, never emulated: no available
        # backend claims a scsi controller, so assignment refuses the
        # machine naming the requirement rather than quietly wiring it
        # to ide.
        self._write("scsi", {"platform": "dos",
                            "drives": {"hdd0": {"media": "blank",
                                                "controller": "scsi"}}},
                   media=[_BLANK])
        with self.assertRaises(PreflightError) as caught:
            create_machine("scsi", context=self.home)
        self.assertIn("controller 'scsi'", str(caught.exception))
        self.assertEqual(self.backend.images, [])

    def test_a_pinned_stub_backend_fails_closed(self):
        """A pinned backend whose adapter is a stub is refused by name.

        It used to be recorded and ignored: `backend: virtualbox`
        materialized a qcow2 image and would have launched QEMU, so
        the machine's recorded backend and its real one disagreed with
        nobody told. Now the pin skips the priority walk, that adapter
        alone is asked, and it claims no capability — so the refusal
        names the backend and what it cannot provide.
        """
        for backend in ("virtualbox", "vmware", "hyperv"):
            with self.subTest(backend=backend):
                self._write(backend, {"platform": "dos",
                                      "backend": backend,
                                      "drives": {"hdd0": "blank"}},
                            media=[_BLANK])
                with self.assertRaises(PreflightError) as caught:
                    create_machine(backend, context=self.home)
                self.assertIn(repr(backend), str(caught.exception))
                # Refused before any image work, like the other gates.
                self.assertEqual(self.backend.images, [])
                self.assertFalse(os.path.exists(
                    machine_dir_path(f"{backend}-0", self.home)))

    def test_the_default_backend_is_qemu_and_is_recorded(self):
        # The gate must not refuse what it is meant to allow, whether
        # the blueprint names qemu or leaves it out.
        for declared in ("qemu", None):
            with self.subTest(backend=declared):
                spec = {"platform": "dos", "drives": {"hdd0": "blank"}}
                if declared is not None:
                    spec["backend"] = declared
                name = f"be-{declared or 'default'}"
                self._write(name, spec, media=[_BLANK])
                machine_id = create_machine(name, context=self.home)
                self.assertEqual(
                    load_machine_state(machine_id, self.home)["backend"],
                    "qemu")

    def test_unimplemented_control_plane_fails_closed(self):
        # A wired plane in the list excuses nothing: the policy is
        # every plane Reliquary may use, so each has to exist.
        self._write("vnc", {"platform": "dos",
                            "drives": {"hdd0": "blank"},
                            "control-planes": ["agentless-display", "vnc",
                                               "guest-agent"]},
                   media=[_BLANK])
        with self.assertRaises(PreflightError) as caught:
            create_machine("vnc", context=self.home)
        self.assertIn("'vnc'", str(caught.exception))
        self.assertIn("'guest-agent'", str(caught.exception))
        # Refused before any image work, and no machine left behind.
        self.assertEqual(self.backend.images, [])
        self.assertFalse(os.path.exists(
            machine_dir_path("vnc-0", self.home)))

    def test_declared_agentless_display_is_recorded(self):
        machine_id = self._create(
            "cp", {"platform": "dos", "drives": {"hdd0": "blank"},
                   "control-planes": ["agentless-display"]},
            media=[_BLANK])
        self.assertEqual(self._state(machine_id)["control-planes"],
                         ["agentless-display"])

    def test_a_settings_section_is_validated_against_the_assigned_backend(self):
        # The seam is called with this backend's own section, and a key
        # it does not define is refused before any image work.
        with fake_backend.installed(settings_keys=("machine",)) as adapter:
            self._write("hatch", {"platform": "dos",
                                  "drives": {"hdd0": "blank"},
                                  "backend-settings": {
                                      "qemu": {"machine": "pc"}}},
                       media=[_BLANK])
            machine_id = create_machine("hatch", context=self.home)
            self.assertEqual(adapter.validated, [{"machine": "pc"}])
            self.assertEqual(
                self._state(machine_id)["backend-settings"],
                {"qemu": {"machine": "pc"}})

            self._write("bad", {"platform": "dos",
                                "drives": {"hdd0": "blank"},
                                "backend-settings": {"qemu": {"cpus": 2}}},
                       media=[_BLANK])
            adapter.images.clear()
            with self.assertRaises(StaticError) as caught:
                create_machine("bad", context=self.home)
            self.assertEqual(caught.exception.rule_id,
                             "machine.settings-unknown-key")
            self.assertEqual(adapter.images, [])
            self.assertFalse(os.path.exists(
                machine_dir_path("bad-0", self.home)))

    def test_another_backends_section_is_inert_and_never_judged(self):
        # Preserved verbatim and not validated: no adapter can speak
        # for another's vocabulary, so judging an inert section would
        # refuse a machine over configuration nothing will read.
        with fake_backend.installed(settings_keys=()) as adapter:
            machine_id = self._create(
                "inert", {"platform": "dos", "backend": "qemu",
                          "drives": {"hdd0": "blank"},
                          "backend-settings": {"vmware": {"nonsense": True}}},
                media=[_BLANK])
            self.assertEqual(adapter.validated, [None])
        self.assertEqual(self._state(machine_id)["backend-settings"],
                         {"vmware": {"nonsense": True}})

    def test_a_lone_settings_section_narrows_assignment_to_its_backend(self):
        # No `backend` declared, one section: the blueprint has already
        # said which backend it is written for.
        with fake_backend.installed(name="vmware",
                                    settings_keys=("machine",)) as vmware:
            self._write("narrow", {"platform": "dos",
                                   "drives": {"hdd0": "blank"},
                                   "backend-settings": {
                                       "vmware": {"machine": "x"}}},
                       media=[_BLANK])
            machine_id = create_machine("narrow", context=self.home)
            self.assertEqual(vmware.validated, [{"machine": "x"}])
        state = self._state(machine_id)
        self.assertEqual(state["backend"], "vmware")
        # And qemu — first in the priority order, available, capable —
        # was passed over rather than winning the walk.
        self.assertEqual(self.backend.images, [])

    def test_two_sections_narrow_nothing_and_the_walk_decides(self):
        machine_id = self._create(
            "both", {"platform": "dos", "drives": {"hdd0": "blank"},
                     "backend-settings": {"vmware": {}, "hyperv": {}}},
            media=[_BLANK])
        self.assertEqual(self._state(machine_id)["backend"], "qemu")

    def test_a_declared_backend_outranks_a_narrowing_section(self):
        machine_id = self._create(
            "pinned", {"platform": "dos", "backend": "qemu",
                       "drives": {"hdd0": "blank"},
                       "backend-settings": {"vmware": {}}},
            media=[_BLANK])
        self.assertEqual(self._state(machine_id)["backend"], "qemu")

    def test_disabled_drive_excluded_from_state(self):
        machine_id = self._create(
            "disabled", {"platform": "dos",
                         "drives": {"hdd0": "blank",
                                    "hdd1": {"media": "big", "enabled": False}}},
            media=[_BLANK, {"name": "big", "materialize": "new",
                            "size": "50M"}])
        state = self._state(machine_id)
        self.assertIn("hdd0", state["drives"])
        self.assertNotIn("hdd1", state["drives"])

    def test_blueprint_source_recorded_and_digest_stable(self):
        self._write("twin", {"platform": "dos", "drives": {"hdd0": "blank"}},
                   media=[_BLANK])
        first = create_machine("twin", context=self.home)
        second = create_machine("twin", context=self.home)
        s1, s2 = self._state(first), self._state(second)
        self.assertTrue(s1["blueprint-source"].endswith("twin.rlqb"))
        self.assertEqual(s1["blueprint-digest"], s2["blueprint-digest"])
        self.assertNotEqual(first, second)

    def test_location_property_binds_at_create_and_records_the_path(self):
        # A media located by ${live.iso}, supplied by a blueprint
        # parameter, materializes -- and the resolved path lands in
        # state, so start never re-resolves the reference.
        self._write(
            "param", {"platform": "dos",
                      "drives": {"cdrom0": "livecd"},
                      "parameters": {"live.iso": self.iso_path}},
            media=[{"name": "livecd", "materialize": "use",
                    "read-only": True, "location": "${live.iso}"}])
        machine_id = create_machine("param", context=self.home)
        entry = self._state(machine_id)["drives"]["cdrom0"]
        self.assertEqual(entry["path"], self.iso_path)
        # The recorded location is concrete: no ${...} survives.
        self.assertNotIn("${", json.dumps(entry))

    def test_location_property_from_an_explicit_value(self):
        self._write(
            "explicit", {"platform": "dos",
                         "drives": {"cdrom0": "livecd"}},
            media=[{"name": "livecd", "materialize": "use",
                    "read-only": True, "location": "${live.iso}"}])
        machine_id = create_machine(
            "explicit", context=self.home,
            properties={"live.iso": self.iso_path})
        entry = self._state(machine_id)["drives"]["cdrom0"]
        self.assertEqual(entry["path"], self.iso_path)

    def test_an_unbound_location_property_fails_the_create(self):
        from reliquary.binding import PropertyBindingError
        self._write(
            "needy", {"platform": "dos", "drives": {"cdrom0": "livecd"}},
            media=[{"name": "livecd", "materialize": "use",
                    "read-only": True, "location": "${live.iso}"}])
        with self.assertRaises(PropertyBindingError):
            create_machine("needy", context=self.home)
        # The failed create left no machine behind.
        machines_root = os.path.join(
            self.home, "cache", "machines")
        leftover = (os.path.isdir(machines_root)
                    and [n for n in os.listdir(machines_root)
                         if not n.startswith(".")])
        self.assertFalse(leftover)

    def test_missing_state_raises_filenotfound(self):
        with self.assertRaises(PreflightError):
            load_machine_state("nonexistent", context=self.home)

    def test_machine_id_numbered_and_reused(self):
        self._write("plain", {"platform": "dos"})
        self._write("other", {"platform": "dos"})
        first = create_machine("plain", context=self.home)
        second = create_machine("plain", context=self.home)
        other = create_machine("other", context=self.home)
        self.assertEqual((first, second, other),
                         ("plain-0", "plain-1", "other-0"))
        destroy_machine(second, context=self.home)
        self.assertEqual(create_machine("plain", context=self.home),
                         "plain-1")

    def test_create_machine_unknown_name_errors(self):
        with self.assertRaises(PreflightError):
            create_machine("no-such", context=self.home)


class LifecycleTests(_HomeCase):
    def _ready(self, name="test-bp", **machine):
        # A per-blueprint blank so several blueprints can coexist in one
        # home without a media (name, type) collision.
        machine.setdefault("platform", "dos")
        blank = f"{name}-blank"
        machine.setdefault("drives", {"hdd0": blank})
        return self._create(name, machine,
                            media=[{"name": blank, "materialize": "new",
                                    "size": "20M"}])

    def _start(self, machine_id):
        return start_machine(machine_id, context=self.home)

    def test_list_and_filter_machines(self):
        first = self._ready("alpha")
        second = self._ready("beta")
        ids = {s["id"] for s in list_machines(context=self.home)}
        self.assertEqual(ids, {first, second})
        self.assertEqual(
            [s["id"] for s in list_machines(context=self.home, blueprint="alpha")],
            [first])

    def test_list_orders_by_number(self):
        self._ready("plain")
        self._ready("plain")
        self._ready("plain")
        destroy_machine("plain-1", context=self.home)
        self.assertEqual(
            [s["id"] for s in list_machines(context=self.home, blueprint="plain")],
            ["plain-0", "plain-2"])

    def test_resolve_by_blueprint_sole(self):
        machine_id = self._ready("freedos")
        self.assertEqual(
            resolve_machine(blueprint="freedos", context=self.home), machine_id)

    def test_resolve_by_blueprint_none_suggests_create(self):
        with self.assertRaises(PreflightError) as caught:
            resolve_machine(blueprint="missing", context=self.home)
        self.assertIn("no machine exists", str(caught.exception))

    def test_resolve_by_blueprint_ambiguous(self):
        self._ready("freedos")
        self._ready("freedos")
        with self.assertRaises(PreflightError) as caught:
            resolve_machine(blueprint="freedos", context=self.home)
        self.assertIn("has 2 machines", str(caught.exception))

    def test_resolve_by_full_id_and_rejections(self):
        machine_id = self._ready("freedos")
        self.assertEqual(
            resolve_machine(machine=machine_id, context=self.home), machine_id)
        with self.assertRaises(StaticError):
            resolve_machine(blueprint="freedos", machine=machine_id,
                            context=self.home)
        with self.assertRaises(StaticError):
            resolve_machine(machine="0", context=self.home)
        with self.assertRaises(PreflightError):
            resolve_machine(machine="freedos-", context=self.home)

    def test_start_hands_the_state_to_the_adapter_and_sets_running(self):
        machine_id = self._create(
            "bootable", {"platform": "dos",
                         "drives": {"hdd0": "blank", "cdrom0": "freedos-livecd"},
                         "boot": ["cdrom0", "hdd0"]},
            media=[_BLANK, self._livecd()])
        started = start_machine(machine_id, context=self.home)
        self.assertEqual(started, machine_id)
        # Reliquary vocabulary crosses the seam, never backend
        # arguments: the adapter is handed the resolved state and the
        # directories that are its to write in.
        launch = self.backend.starts[-1]
        self.assertEqual(launch["state"]["boot"], ["cdrom0", "hdd0"])
        self.assertEqual(set(launch["state"]["drives"]), {"hdd0", "cdrom0"})
        self.assertEqual(
            launch["machine_dir"], machine_dir_path(machine_id, self.home))
        self.assertEqual(
            launch["backend_dir"],
            os.path.join(machine_dir_path(machine_id, self.home), "qemu"))
        state = self._state(machine_id)
        self.assertEqual(state["phase"], "running")
        # The live-VM identity is folded into the state, atomic with
        # phase, and it names the backend that owns it.
        self.assertEqual(state["vm"]["backend"], "qemu")
        self.assertEqual(state["vm"]["backend-id"], f"reliquary-{machine_id}")

    def test_start_refuses_when_the_recorded_backend_is_absent(self):
        # A machine carries its backend for life; a host that no
        # longer has it is told so, and nothing is launched.
        machine_id = self._ready()
        self.backend.available = False
        with self.assertRaises(PreflightError) as caught:
            start_machine(machine_id, context=self.home)
        self.assertIn("not available on this host", str(caught.exception))
        self.assertEqual(self.backend.starts, [])
        self.assertEqual(self._state(machine_id)["phase"], "ready")

    def test_start_rejects_already_running(self):
        machine_id = self._ready()
        self._force(machine_id, "running")
        with self.assertRaises(PreflightError) as caught:
            start_machine(machine_id, context=self.home)
        self.assertIn("already running", str(caught.exception))

    def test_stop_returns_phase_to_ready(self):
        machine_id = self._ready()
        self._force(machine_id, "running", vm=True)
        stop_machine(machine_id, context=self.home)
        # The adapter is handed the recorded VM identity, not a home
        # dir — the endpoint behind it is the adapter's own business.
        self.assertEqual(len(self.backend.stops), 1)
        self.assertEqual(self.backend.stops[0]["backend-id"],
                         f"reliquary-{machine_id}")
        state = self._state(machine_id)
        self.assertEqual(state["phase"], "ready")
        self.assertNotIn("vm", state)

    def test_stop_keeps_running_on_identity_mismatch(self):
        machine_id = self._ready()
        self._force(machine_id, "running", vm=True)
        self.backend.stop_error = PreflightError("QMP identity mismatch")
        with self.assertRaisesRegex(PreflightError, "identity mismatch"):
            stop_machine(machine_id, context=self.home)
        state = self._state(machine_id)
        self.assertEqual(state["phase"], "running")
        self.assertIn("vm", state)

    def test_stop_reconciles_when_vm_gone(self):
        machine_id = self._ready()
        self._force(machine_id, "running")
        self.backend.stop_error = PreflightError("no longer reachable")
        with self.assertRaisesRegex(PreflightError, "no longer reachable"):
            stop_machine(machine_id, context=self.home)
        self.assertEqual(self._state(machine_id)["phase"], "ready")

    def test_destroy_removes_directory(self):
        machine_id = self._ready()
        root = machine_dir_path(machine_id, self.home)
        destroy_machine(machine_id, context=self.home)
        self.assertFalse(os.path.exists(root))
        self.assertEqual(list_machines(context=self.home), [])

    def test_destroy_disposes_of_the_backend_object_first(self):
        # The directory is the whole materialization only for QEMU;
        # another backend has its own object to remove, and it goes
        # before the directory that would otherwise strand it.
        machine_id = self._ready()
        root = machine_dir_path(machine_id, self.home)
        destroy_machine(machine_id, context=self.home)
        self.assertEqual(self.backend.disposed, [root])

    def test_destroy_retries_after_failure(self):
        machine_id = self._ready()
        with mock.patch("reliquary.machines.shutil.rmtree",
                        side_effect=PermissionError("locked")):
            with self.assertRaises(PermissionError):
                destroy_machine(machine_id, context=self.home)
        self.assertEqual(self._state(machine_id)["phase"], "ready")
        destroy_machine(machine_id, context=self.home)
        self.assertFalse(os.path.exists(machine_dir_path(machine_id, self.home)))

    def test_destroy_completes_a_stranded_destroy(self):
        machine_id = self._ready()
        self._force(machine_id, "destroying")
        destroy_machine(machine_id, context=self.home)
        self.assertFalse(os.path.exists(machine_dir_path(machine_id, self.home)))

    def test_destroy_rejects_running(self):
        machine_id = self._ready()
        self._force(machine_id, "running")
        with self.assertRaises(PreflightError) as caught:
            destroy_machine(machine_id, context=self.home)
        self.assertIn("stop it before destroying", str(caught.exception))

    def test_generation_advances(self):
        machine_id = self._ready()
        self.assertEqual(self._state(machine_id)["generation"], 0)
        self._start(machine_id)
        gen1 = self._state(machine_id)["generation"]
        self.assertGreater(gen1, 0)
        stop_machine(machine_id, context=self.home)
        self.assertGreater(self._state(machine_id)["generation"], gen1)

    def test_operation_takes_a_lock(self):
        machine_id = self._ready()
        self._start(machine_id)
        self.assertTrue(os.path.exists(os.path.join(
            self.home, "cache", "machines", ".locks", f"{machine_id}.op.lock")))

    def test_interrupted_stop_completed(self):
        machine_id = self._ready()
        self._force(machine_id, "stopping")
        stop_machine(machine_id, context=self.home)
        self.assertEqual(len(self.backend.stops), 1)
        self.assertEqual(self._state(machine_id)["phase"], "ready")

    def test_interrupted_create_rolled_back(self):
        machine_id = self._ready()
        self._force(machine_id, "creating")
        with self.assertRaises(PreflightError) as caught:
            self._start(machine_id)
        self.assertIn("rolled back", str(caught.exception))
        self.assertFalse(os.path.exists(machine_dir_path(machine_id, self.home)))

    def test_interrupted_destroy_completes(self):
        machine_id = self._ready()
        self._force(machine_id, "destroying")
        with self.assertRaises(PreflightError) as caught:
            self._start(machine_id)
        self.assertIn("removed", str(caught.exception))

    def test_failed_materialization_rolls_back(self):
        self._write("doomed", {"platform": "dos", "drives": {"hdd0": "blank"}},
                   media=[_BLANK])
        with mock.patch.object(self.backend, "create_image",
                               side_effect=RunFailure("disk full")):
            with self.assertRaises(RunFailure):
                create_machine("doomed", context=self.home)
        self.assertEqual(
            list_machines(context=self.home, blueprint="doomed"), [])

    def test_get_machine_dir(self):
        machine_id = self._ready()
        result = get_machine_dir(machine=machine_id, context=self.home)
        self.assertTrue(os.path.isabs(result))
        self.assertEqual(os.path.normpath(result),
                         os.path.normpath(machine_dir_path(machine_id, self.home)))

    def test_recreate_reuses_id(self):
        machine_id = self._ready("rc")
        again = recreate_machine(machine=machine_id, context=self.home)
        self.assertEqual(again, machine_id)

    def test_recreate_keeps_id_at_gap(self):
        self._write("g", {"platform": "dos", "drives": {"hdd0": "blank"}},
                   media=[_BLANK])
        create_machine("g", context=self.home)
        create_machine("g", context=self.home)
        two = create_machine("g", context=self.home)
        destroy_machine("g-0", context=self.home)
        again = recreate_machine(machine=two, context=self.home)
        self.assertEqual(again, "g-2")

    def test_apply_absorbs_memory_and_boot(self):
        machine_id = self._create(
            "ap", {"platform": "dos", "memory": "16M",
                   "drives": {"hdd0": "blank", "cdrom0": None},
                   "boot": ["hdd0", "cdrom0"]}, media=[_BLANK])
        digest0 = self._state(machine_id)["blueprint-digest"]
        self._write("ap", {"platform": "dos", "memory": "32M",
                          "drives": {"hdd0": "blank", "cdrom0": None},
                          "boot": ["cdrom0", "hdd0"]}, media=[_BLANK])
        apply_blueprint(machine=machine_id, context=self.home)
        state = self._state(machine_id)
        self.assertEqual(state["memory"], 32)
        self.assertEqual(state["boot"], ["cdrom0", "hdd0"])
        self.assertNotEqual(state["blueprint-digest"], digest0)

    def test_apply_fails_closed_on_size_change(self):
        machine_id = self._create(
            "sz", {"platform": "dos", "drives": {"hdd0": "blank"}},
            media=[_BLANK])
        self._write("sz", {"platform": "dos", "drives": {"hdd0": "blank"}},
                   media=[{"name": "blank", "materialize": "new",
                           "size": "50M"}])
        with self.assertRaises(PreflightError) as caught:
            apply_blueprint(machine=machine_id, context=self.home)
        self.assertIn("recreate", str(caught.exception))

    def test_apply_reconciles_diverged_media(self):
        machine_id = self._create(
            "dv", {"platform": "dos",
                   "drives": {"hdd0": "blank", "cdrom0": None},
                   "boot": ["hdd0", "cdrom0"]},
            media=[_BLANK, self._livecd()])
        insert_media(machine_id, "cdrom0", "freedos-livecd",
                     context=self.home)
        self.assertIsNotNone(
            self._state(machine_id)["drives"]["cdrom0"]["media"])
        apply_blueprint(machine=machine_id, context=self.home)
        self.assertIsNone(
            self._state(machine_id)["drives"]["cdrom0"]["media"])

    def test_apply_adds_and_removes_drives(self):
        machine_id = self._create(
            "ar", {"platform": "dos",
                   "drives": {"hdd0": "blank", "hdd1": "big"}},
            media=[_BLANK, {"name": "big", "materialize": "new",
                            "size": "30M"}])
        media_root = os.path.join(
            machine_dir_path(machine_id, self.home), "media")
        # The dropped drive's per-machine image is named for its media.
        open(os.path.join(media_root, "big.qcow2"), "w").close()
        self._write("ar", {"platform": "dos",
                          "drives": {"hdd0": "blank", "cdrom0": None}},
                   media=[_BLANK])
        apply_blueprint(machine=machine_id, context=self.home)
        state = self._state(machine_id)
        self.assertNotIn("hdd1", state["drives"])
        self.assertIn("cdrom0", state["drives"])
        self.assertFalse(os.path.exists(
            os.path.join(media_root, "big.qcow2")))

    def test_apply_refuses_an_unimplemented_control_plane(self):
        machine_id = self._create(
            "cpa", {"platform": "dos",
                    "drives": {"hdd0": "blank", "hdd1": "big"}},
            media=[_BLANK, {"name": "big", "materialize": "new",
                            "size": "30M"}])
        self._write("cpa", {"platform": "dos",
                           "drives": {"hdd0": "blank"},
                           "control-planes": ["serial-console"]},
                   media=[_BLANK])
        with self.assertRaises(PreflightError) as caught:
            apply_blueprint(machine=machine_id, context=self.home)
        self.assertIn("'serial-console'", str(caught.exception))
        # Refused before the drives are reconciled, so the dropped
        # drive is still there and the machine is as it was.
        state = self._state(machine_id)
        self.assertIn("hdd1", state["drives"])
        self.assertEqual(state["control-planes"], ["agentless-display"])

    def test_apply_absorbs_a_settings_change_and_refuses_a_bad_one(self):
        with fake_backend.installed(settings_keys=("machine",)) as adapter:
            machine_id = self._create(
                "sa", {"platform": "dos",
                       "drives": {"hdd0": "blank", "hdd1": "big"}},
                media=[_BLANK, {"name": "big", "materialize": "new",
                                "size": "30M"}])
            self._write("sa", {"platform": "dos", "backend": "qemu",
                              "drives": {"hdd0": "blank", "hdd1": "big"},
                              "backend-settings": {
                                  "qemu": {"machine": "pc"}}},
                       media=[_BLANK, {"name": "big", "materialize": "new",
                                       "size": "30M"}])
            apply_blueprint(machine=machine_id, context=self.home)
            self.assertEqual(self._state(machine_id)["backend-settings"],
                             {"qemu": {"machine": "pc"}})

            # An edited section this backend cannot honor is refused
            # with the capability gate, before a drive is touched.
            self._write("sa", {"platform": "dos", "backend": "qemu",
                              "drives": {"hdd0": "blank"},
                              "backend-settings": {"qemu": {"cpus": 2}}},
                       media=[_BLANK])
            with self.assertRaises(StaticError) as caught:
                apply_blueprint(machine=machine_id, context=self.home)
        self.assertEqual(caught.exception.rule_id,
                         "machine.settings-unknown-key")
        state = self._state(machine_id)
        self.assertIn("hdd1", state["drives"])
        self.assertEqual(state["backend-settings"], {"qemu": {"machine": "pc"}})

    def test_apply_requires_stopped(self):
        machine_id = self._ready()
        self._force(machine_id, "running")
        with self.assertRaises(PreflightError) as caught:
            apply_blueprint(machine=machine_id, context=self.home)
        self.assertIn("must be stopped", str(caught.exception))


class MediaInsertionTests(_HomeCase):
    def _installer(self):
        return self._create(
            "installer", {"platform": "dos",
                          "drives": {"hdd0": "blank", "cdrom0": None},
                          "boot": ["hdd0", "cdrom0"]},
            media=[_BLANK, self._livecd()])

    def test_create_records_empty_removable_drive(self):
        cdrom = self._state(self._installer())["drives"]["cdrom0"]
        self.assertEqual(cdrom["medium"], "cdrom")
        self.assertIsNone(cdrom["media"])
        self.assertIsNone(cdrom["path"])

    def test_insert_persists_media(self):
        machine_id = self._installer()
        insert_media(machine_id, "cdrom0", "freedos-livecd",
                     context=self.home)
        cdrom = self._state(machine_id)["drives"]["cdrom0"]
        self.assertEqual(cdrom["media"], "freedos-livecd")
        self.assertEqual(os.path.normpath(cdrom["path"]),
                         os.path.normpath(self.iso_path))

    def test_eject_returns_slot_to_empty(self):
        machine_id = self._installer()
        insert_media(machine_id, "cdrom0", "freedos-livecd",
                     context=self.home)
        eject_media(machine_id, "cdrom0", context=self.home)
        cdrom = self._state(machine_id)["drives"]["cdrom0"]
        self.assertIsNone(cdrom["media"])
        self.assertIsNone(cdrom["path"])

    def test_set_boot_order_persists(self):
        machine_id = self._installer()
        set_boot_order(machine_id, ["cdrom0", "hdd0"], context=self.home)
        self.assertEqual(self._state(machine_id)["boot"], ["cdrom0", "hdd0"])

    def test_set_boot_order_rejects_running(self):
        machine_id = self._installer()
        self._force(machine_id, "running")
        with self.assertRaises(PreflightError):
            set_boot_order(machine_id, ["cdrom0"], context=self.home)

    def test_set_boot_order_rejects_undeclared(self):
        machine_id = self._installer()
        with self.assertRaises(PreflightError) as caught:
            set_boot_order(machine_id, ["floppy0"], context=self.home)
        self.assertIn("undeclared drive floppy0", str(caught.exception))

    def test_boot_order_reaches_the_adapter_as_drive_keys(self):
        machine_id = self._installer()
        start_machine(machine_id, context=self.home)
        # Drive keys cross the seam; turning them into a firmware
        # boot order is the adapter's (test_backend_qemu.py).
        self.assertEqual(
            self.backend.starts[-1]["state"]["boot"], ["hdd0", "cdrom0"])

    def test_inserted_media_survives_start(self):
        machine_id = self._installer()
        insert_media(machine_id, "cdrom0", "freedos-livecd",
                     context=self.home)
        start_machine(machine_id, context=self.home)
        cdrom = self.backend.starts[-1]["state"]["drives"]["cdrom0"]
        self.assertEqual(os.path.normpath(cdrom["path"]),
                         os.path.normpath(self.iso_path))

    def test_insert_rejects_undeclared_slot(self):
        with self.assertRaises(PreflightError) as caught:
            insert_media(self._installer(), "floppy0", "freedos-livecd",
                         context=self.home)
        self.assertIn("declares no drive floppy0", str(caught.exception))

    def test_insert_rejects_non_removable(self):
        with self.assertRaises(PreflightError) as caught:
            insert_media(self._installer(), "hdd0", "freedos-livecd",
                         context=self.home)
        self.assertIn("not a removable drive slot", str(caught.exception))

    def test_insert_on_running_changes_live(self):
        machine_id = self._installer()
        self._force(machine_id, "running", vm=True)
        with mock.patch("reliquary.machines._change_media_live") as live:
            insert_media(machine_id, "cdrom0", "freedos-livecd",
                         context=self.home)
        live.assert_called_once()
        self.assertEqual(live.call_args.args[1], "cdrom0")
        self.assertEqual(self._state(machine_id)["drives"]["cdrom0"]["media"],
                         "freedos-livecd")

    def test_eject_on_running_ejects_live(self):
        machine_id = self._installer()
        insert_media(machine_id, "cdrom0", "freedos-livecd",
                     context=self.home)
        self._force(machine_id, "running", vm=True)
        with mock.patch("reliquary.machines._change_media_live") as live:
            eject_media(machine_id, "cdrom0", context=self.home)
        live.assert_called_once()
        self.assertIsNone(live.call_args.args[2])

    def test_a_live_change_goes_through_the_adapter_session(self):
        # The swap the guest sees is one operation with the state
        # change, and it reaches the backend by drive key — never by
        # a monitor command this module composes itself.
        from reliquary import machines as machines_mod
        machine_id = self._installer()
        self._force(machine_id, "running", vm=True)
        machines_mod._change_media_live(
            machine_id, "cdrom0", self.iso_path, self.home)
        machines_mod._change_media_live(
            machine_id, "cdrom0", None, self.home)
        changes = [change for session in self.backend.sessions
                   for change in session.media_changes]
        self.assertEqual(changes,
                         [("cdrom0", self.iso_path), ("cdrom0", None)])

    def test_insert_on_stopped_is_state_only(self):
        machine_id = self._installer()
        with mock.patch("reliquary.machines._change_media_live") as live:
            insert_media(machine_id, "cdrom0", "freedos-livecd",
                         context=self.home)
        live.assert_not_called()
        self.assertEqual(self._state(machine_id)["drives"]["cdrom0"]["media"],
                         "freedos-livecd")

    def test_mark_stopped_reconciles(self):
        machine_id = self._installer()
        self._force(machine_id, "running", vm=True)
        mark_stopped(machine_id, context=self.home)
        state = self._state(machine_id)
        self.assertEqual(state["phase"], "ready")
        self.assertNotIn("vm", state)

    def test_mark_stopped_leaves_ready_alone(self):
        machine_id = self._installer()
        mark_stopped(machine_id, context=self.home)
        self.assertEqual(self._state(machine_id)["phase"], "ready")


class AnonymousImageTests(_HomeCase):
    """``insert-media --file``: the caller's own image, mounted as-is."""

    def _rig(self):
        machine_id = self._create(
            "rig", {"platform": "dos",
                    "drives": {"hdd0": "blank", "floppy0": None}},
            media=[_BLANK])
        image = os.path.join(self.home, "round-1.img")
        with open(image, "wb") as handle:
            handle.write(b"BINARY")
        return machine_id, image

    def test_a_file_mounts_in_place_with_no_catalog_identity(self):
        machine_id, image = self._rig()
        insert_media(machine_id, "floppy0", file=image, context=self.home)
        floppy = self._state(machine_id)["drives"]["floppy0"]
        # Anonymous: no media name, attached ("use") in place.
        self.assertIsNone(floppy["media"])
        self.assertEqual(floppy["materialize"], "use")
        self.assertEqual(os.path.normpath(floppy["path"]),
                         os.path.normpath(image))

    def test_the_image_is_never_copied_into_the_cache(self):
        machine_id, image = self._rig()
        insert_media(machine_id, "floppy0", file=image, context=self.home)
        cache = os.path.join(self.home, "cache", "media")
        self.assertFalse(
            os.path.isdir(cache) and os.listdir(cache))

    def test_a_rebuilt_image_is_picked_up_at_the_next_start(self):
        machine_id, image = self._rig()
        insert_media(machine_id, "floppy0", file=image, context=self.home)
        with open(image, "wb") as handle:
            handle.write(b"ROUND-2")
        start_machine(machine_id, context=self.home)
        # Mutable and unverified: no hash is re-checked, and the path
        # the consumer just rewrote is what the adapter is handed.
        floppy = self.backend.starts[-1]["state"]["drives"]["floppy0"]
        self.assertEqual(os.path.normpath(floppy["path"]),
                         os.path.normpath(image))

    def test_naming_both_a_media_and_a_file_is_refused(self):
        machine_id, image = self._rig()
        with self.assertRaises(StaticError) as caught:
            insert_media(machine_id, "floppy0", "blank", file=image,
                         context=self.home)
        self.assertIn("not both and not neither", str(caught.exception))

    def test_naming_neither_is_refused(self):
        machine_id, _image = self._rig()
        with self.assertRaises(StaticError):
            insert_media(machine_id, "floppy0", context=self.home)

    def test_a_missing_image_fails_closed(self):
        machine_id, _image = self._rig()
        with self.assertRaises(PreflightError):
            insert_media(machine_id, "floppy0",
                         file=os.path.join(self.home, "absent.img"),
                         context=self.home)

    def test_a_directory_names_the_gap(self):
        machine_id, _image = self._rig()
        with self.assertRaises(StaticError) as caught:
            insert_media(machine_id, "floppy0", file=self.home,
                         context=self.home)
        self.assertIn("location is that directory",
                      str(caught.exception))


class LiveFloppyGeometryTests(_HomeCase):
    """A live floppy swap keeps the geometry it launched with.

    The transport spike (milestone 9, T1) proved live media-change and
    eject-flush on QEMU/DOS, and found this one condition: the drive's
    geometry is fixed at attach, so a differently sized medium reaches
    the guest as read and write errors. Reliquary did not choose that
    geometry, so it fails closed rather than build a broken drive.
    """

    def _running_rig(self, launched=None):
        machine_id = self._create(
            "rig", {"platform": "dos",
                    "drives": {"hdd0": "blank", "floppy0": None}},
            media=[_BLANK])
        if launched is not None:
            insert_media(machine_id, "floppy0", file=launched,
                         context=self.home)
        start_machine(machine_id, context=self.home)
        return machine_id

    def _image(self, name, size):
        path = os.path.join(self.home, name)
        with open(path, "wb") as handle:
            handle.write(b"\0" * size)
        return path

    def test_a_same_sized_swap_is_allowed(self):
        first = self._image("round-1.img", 1474560)
        machine_id = self._running_rig(launched=first)
        second = self._image("round-2.img", 1474560)
        with mock.patch("reliquary.machines._change_media_live") as change:
            insert_media(machine_id, "floppy0", file=second,
                         context=self.home)
        change.assert_called_once()
        self.assertEqual(
            os.path.normpath(
                self._state(machine_id)["drives"]["floppy0"]["path"]),
            os.path.normpath(second))

    def test_a_differently_sized_swap_fails_closed(self):
        first = self._image("round-1.img", 1474560)
        machine_id = self._running_rig(launched=first)
        bigger = self._image("round-2.img", 2949120)
        with self.assertRaises(PreflightError) as caught:
            insert_media(machine_id, "floppy0", file=bigger,
                         context=self.home)
        message = str(caught.exception)
        self.assertIn("1474560-byte medium", message)
        self.assertIn("2949120 bytes", message)

    def test_a_slot_launched_empty_names_the_fix(self):
        machine_id = self._running_rig()
        image = self._image("round-1.img", 1474560)
        with self.assertRaises(PreflightError) as caught:
            insert_media(machine_id, "floppy0", file=image,
                         context=self.home)
        self.assertIn("was empty when machine", str(caught.exception))
        self.assertIn("start again", str(caught.exception))

    def test_a_stopped_insert_is_never_geometry_checked(self):
        # Stopped, the drive has not been attached yet, so any size is
        # legitimate — it becomes the geometry at the next start.
        machine_id = self._running_rig()
        self._force(machine_id, "ready")
        image = self._image("round-1.img", 1474560)
        insert_media(machine_id, "floppy0", file=image, context=self.home)
        self.assertEqual(
            os.path.normpath(
                self._state(machine_id)["drives"]["floppy0"]["path"]),
            os.path.normpath(image))

    def test_a_cdrom_swap_is_not_constrained(self):
        machine_id = self._create(
            "rig", {"platform": "dos",
                    "drives": {"hdd0": "blank", "cdrom0": None}},
            media=[_BLANK, self._livecd()])
        start_machine(machine_id, context=self.home)
        with mock.patch("reliquary.machines._change_media_live"):
            insert_media(machine_id, "cdrom0", "freedos-livecd",
                         context=self.home)
        self.assertEqual(
            self._state(machine_id)["drives"]["cdrom0"]["media"],
            "freedos-livecd")


class MachineVariableTests(_HomeCase):
    """The script -> host scalar channel."""

    def _rig(self):
        return self._create(
            "rig", {"platform": "dos", "drives": {"hdd0": "blank"}},
            media=[_BLANK])

    def test_a_set_variable_reads_back_from_any_process(self):
        machine_id = self._rig()
        set_machine_var(machine_id, "result", "42", context=self.home)
        self.assertEqual(
            get_machine_var("result", machine=machine_id,
                            context=self.home),
            "42")

    def test_an_unset_variable_reads_as_none(self):
        machine_id = self._rig()
        self.assertIsNone(
            get_machine_var("ready", machine=machine_id,
                            context=self.home))

    def test_start_clears_the_variables_of_the_previous_boot(self):
        machine_id = self._rig()
        set_machine_var(machine_id, "ready", "yes", context=self.home)
        start_machine(machine_id, context=self.home)
        self.assertIsNone(
            get_machine_var("ready", machine=machine_id,
                            context=self.home))

    def test_the_reserved_namespaces_are_refused(self):
        machine_id = self._rig()
        for key in ("rlq.ready", "reliquary", "9lives", ""):
            with self.subTest(key=key):
                with self.assertRaises(StaticError):
                    set_machine_var(machine_id, key, "x",
                                    context=self.home)

    def test_a_variable_holds_text(self):
        machine_id = self._rig()
        with self.assertRaises(StaticError):
            set_machine_var(machine_id, "count", 3, context=self.home)


class WaitMachineVarTests(_HomeCase):
    """The polling half, for a variable another actor sets (F30).

    Every case here uses a tiny interval and a tiny timeout: what is
    under test is the loop's logic and its refusals, not how long a
    real wait takes.
    """

    def _rig(self):
        return self._create(
            "rig", {"platform": "dos", "drives": {"hdd0": "blank"}},
            media=[_BLANK])

    def test_a_value_already_there_returns_at_once(self):
        machine_id = self._rig()
        set_machine_var(machine_id, "ready", "yes", context=self.home)
        self.assertEqual(
            wait_machine_var("ready", machine=machine_id, timeout=0.2,
                             interval=0.01, context=self.home),
            "yes")

    def test_without_a_value_any_value_will_do(self):
        """What the readiness idiom actually wants: presence."""
        machine_id = self._rig()
        set_machine_var(machine_id, "ready", "whatever", context=self.home)
        self.assertEqual(
            wait_machine_var("ready", machine=machine_id, timeout=0.2,
                             interval=0.01, context=self.home),
            "whatever")

    def test_a_different_value_is_not_the_one_waited_for(self):
        machine_id = self._rig()
        set_machine_var(machine_id, "ready", "no", context=self.home)
        with self.assertRaises(WaitExpired) as caught:
            wait_machine_var("ready", "yes", machine=machine_id,
                             timeout=0.05, interval=0.01,
                             context=self.home)
        # The diagnostic says what it found, not just what it wanted:
        # "still 'no'" and "never arrived" are different situations.
        self.assertIn("'no'", str(caught.exception))

    def test_a_variable_arriving_mid_wait_is_returned(self):
        machine_id = self._rig()
        state = {"reads": 0}
        real = machines_module.get_machine_var

        def arrive_on_third_read(key, **keywords):
            state["reads"] += 1
            if state["reads"] >= 3:
                set_machine_var(machine_id, key, "yes", context=self.home)
            return real(key, **keywords)

        with mock.patch.object(machines_module, "get_machine_var",
                               side_effect=arrive_on_third_read):
            value = wait_machine_var(
                "ready", "yes", machine=machine_id, timeout=2,
                interval=0.01, context=self.home)
        self.assertEqual(value, "yes")
        self.assertGreaterEqual(state["reads"], 3)

    def test_an_expired_wait_is_a_failure_and_a_timeout_at_once(self):
        """Both readings are true, which is why it has both bases.

        A caller holding the loop catches `TimeoutError` and asks
        again; the CLI's taxonomy arm sees a `RunFailure` and exits 4.
        A bare builtin would have exited 1 and blamed reliquary.
        """
        machine_id = self._rig()
        with self.assertRaises(RunFailure):
            wait_machine_var("ready", machine=machine_id, timeout=0.05,
                             interval=0.01, context=self.home)
        with self.assertRaises(TimeoutError):
            wait_machine_var("ready", machine=machine_id, timeout=0.05,
                             interval=0.01, context=self.home)
        self.assertEqual(exit_code(WaitExpired("x")), 4)

    def test_a_nonpositive_bound_is_refused_before_any_read(self):
        machine_id = self._rig()
        for timeout, interval in ((0, 1), (1, 0), (-1, 1)):
            with self.subTest(timeout=timeout, interval=interval):
                with self.assertRaises(StaticError):
                    wait_machine_var("ready", machine=machine_id,
                                     timeout=timeout, interval=interval,
                                     context=self.home)

    def test_the_reserved_namespaces_are_refused_here_too(self):
        machine_id = self._rig()
        with self.assertRaises(StaticError):
            wait_machine_var("rlq.ready", machine=machine_id,
                             timeout=0.05, interval=0.01,
                             context=self.home)


class ExecTests(_HomeCase):
    """The run family's one-shot member returns its output."""

    def _rig(self):
        return self._create(
            "rig", {"platform": "dos", "drives": {"hdd0": "blank"}},
            media=[_BLANK])

    def test_a_stopped_machine_is_refused(self):
        machine_id = self._rig()
        with self.assertRaises(PreflightError) as caught:
            machines_exec("DIR", machine=machine_id, context=self.home)
        self.assertIn("is not running", str(caught.exception))

    def test_the_command_output_is_returned(self):
        machine_id = self._rig()
        self._force(machine_id, "running", vm=True)
        with mock.patch(
                "reliquary.interaction_agentless.AgentlessGuestExec"
                ".execute", return_value=("VOL SERIAL", "2 FILES")) as run:
            rows = machines_exec(
                "DIR", machine=machine_id, timeout=30, context=self.home)
        self.assertEqual(rows, ("VOL SERIAL", "2 FILES"))
        # The outcome check is opt-in, so the twin passes it through
        # explicitly rather than leaving the adapter to assume.
        run.assert_called_once_with("DIR", 30, check=False)


class CommandOutputTests(unittest.TestCase):
    """Agentless capture: the rows between the echo and the prompt."""

    def test_the_rows_between_echo_and_prompt_are_the_output(self):
        rows = _command_output(
            ["C:\\>DIR", "VOL SERIAL IS 1234", "2 FILE(S)", "C:\\>"],
            "DIR", echoed=True)
        self.assertEqual(rows, ("VOL SERIAL IS 1234", "2 FILE(S)"))

    def test_a_command_with_no_output_returns_nothing(self):
        self.assertEqual(
            _command_output(["C:\\>CLS", "C:\\>"], "CLS", echoed=True), ())

    def test_a_scrolled_echo_yields_what_is_still_visible(self):
        # The honest limit of screen scraping: the echo scrolled off,
        # so what remains on screen is what the caller gets. `echoed`
        # is what says it scrolled rather than never arrived.
        rows = _command_output(["LINE 1", "LINE 2", "C:\\>"],
                               "TYPE BIG.TXT", echoed=True)
        self.assertEqual(rows, ("LINE 1", "LINE 2"))

    def test_an_echo_never_seen_is_a_failure_not_a_tuple(self):
        # The same screen, and the opposite answer: with no echo ever
        # observed, the rows above the prompt belong to something else
        # and returning them would pass one command's text off as
        # another's (P11).
        with self.assertRaises(RunFailure) as caught:
            _command_output(["LINE 1", "LINE 2", "C:\\>"],
                            "TYPE BIG.TXT", echoed=False)
        self.assertEqual(caught.exception.rule_id, "screen.no-echo")
        self.assertIn("never echoed", str(caught.exception))


class _ScriptedConsole:
    """A console playing a fixed sequence of screens."""

    def __init__(self, frames):
        self.frames = list(frames)
        self.sent = []

    def send_text(self, text, enter=True):
        del enter
        self.sent.append(text)

    def screen_text(self):
        return list(self.frames[0] if len(self.frames) == 1
                    else self.frames.pop(0))


class _ScriptedMachine:
    def __init__(self, frames):
        self.console_double = _ScriptedConsole(frames)

    @contextlib.contextmanager
    def console(self):
        yield self.console_double


class CommandCompletionTests(unittest.TestCase):
    """A prompt alone does not mean *this* command finished.

    `wait_ready` returns because a prompt is on screen, so a
    completion test that asks only for a prompt is satisfied by the
    one already there — and hands back the boot's output as though it
    were the command's. These are the cases that tell the two apart.
    """

    PROMPT = "C:\\>"
    BOOT = ["UDVD2 CD driver, success",
            "Modules using memory below 1 MB:", PROMPT]

    def _run(self, frames, command="VER", timeout=1):
        guest = AgentlessGuestExec(_ScriptedMachine(frames))
        return guest.execute(command, timeout)

    def test_the_prompt_wait_ready_left_is_not_completion(self):
        # The reported failure: the guest is still finishing its boot
        # script, the echo has not landed, and the screen is exactly
        # what wait_ready saw. Nothing here is this command's.
        with self.assertRaises(RunFailure) as caught:
            self._run([self.BOOT, self.BOOT])
        self.assertIn("timed out", str(caught.exception))

    def test_output_is_returned_once_the_echo_lands(self):
        rows = self._run([
            self.BOOT, self.BOOT,
            ["C:\\>VER"],
            ["C:\\>VER", "FreeCom version 0.86", self.PROMPT]])
        self.assertEqual(rows, ("FreeCom version 0.86",))

    def test_a_scrolled_echo_still_completes_with_the_tail(self):
        # Seen once, gone later: that is scrolling, and the tail is
        # the documented answer rather than an error.
        rows = self._run([
            [self.PROMPT],
            ["C:\\>TYPE BIG.TXT"],
            ["LINE 24", "LINE 25", self.PROMPT]], "TYPE BIG.TXT")
        self.assertEqual(rows, ("LINE 24", "LINE 25"))

    def test_a_changed_screen_without_an_echo_still_refuses_to_guess(self):
        # The screen moved, so something happened and the wait ends —
        # but nothing ties it to this command, so it fails rather than
        # returning rows it cannot place.
        with self.assertRaises(RunFailure) as caught:
            self._run([[self.PROMPT],
                       ["SOMETHING ELSE ENTIRELY", self.PROMPT]])
        self.assertEqual(caught.exception.rule_id, "screen.no-echo")

    def test_the_command_is_sent_exactly_once(self):
        guest = AgentlessGuestExec(_ScriptedMachine([
            [self.PROMPT], ["C:\\>VER", "FreeCom version", self.PROMPT]]))
        guest.execute("VER", 1)
        self.assertEqual(guest._machine.console_double.sent, ["VER"])


class CheckedCommandTests(unittest.TestCase):
    """`check=True`: whether the command signalled failure (F26).

    The rows a command leaves cannot answer "did it work?" — a setup
    command's output is nothing and its success is everything — so the
    verdict comes from a probe reliquary composes and reads back,
    which is why this reads no meaning into the guest's own output
    (G2, P18): the sentinel is a word reliquary said, not one the
    command did.
    """

    PROMPT = "C:\\>"
    PROBE = "IF ERRORLEVEL 1 ECHO RLQ-EXEC-FAILED"

    def _guest(self, frames):
        return AgentlessGuestExec(_ScriptedMachine(frames))

    def _frames(self, *, failed):
        """The screens for one command plus its probe.

        Each `execute` opens its own console and the double replays one
        sequence, so the probe's frames simply follow the command's.
        """
        probe_output = (["RLQ-EXEC-FAILED"] if failed else [])
        return [
            [self.PROMPT],
            ["C:\\>DRIVER.EXE", "loading", self.PROMPT],
            [self.PROMPT],
            [f"C:\\>{self.PROBE}"] + probe_output + [self.PROMPT],
        ]

    def test_a_failing_command_raises_naming_it(self):
        with self.assertRaises(RunFailure) as caught:
            self._guest(self._frames(failed=True)).execute(
                "DRIVER.EXE", 1, check=True)
        self.assertEqual(caught.exception.rule_id,
                         "command.signalled-failure")
        self.assertIn("DRIVER.EXE", str(caught.exception))

    def test_a_succeeding_command_returns_its_rows_unchanged(self):
        rows = self._guest(self._frames(failed=False)).execute(
            "DRIVER.EXE", 1, check=True)
        self.assertEqual(rows, ("loading",))

    def test_the_probe_is_asked_after_the_command_and_only_when_checked(self):
        guest = self._guest(self._frames(failed=False))
        guest.execute("DRIVER.EXE", 1, check=True)
        self.assertEqual(guest._machine.console_double.sent,
                         ["DRIVER.EXE", self.PROBE])

        unchecked = self._guest(self._frames(failed=True))
        unchecked.execute("DRIVER.EXE", 1)
        self.assertEqual(unchecked._machine.console_double.sent,
                         ["DRIVER.EXE"],
                         "an unchecked exec must cost no extra command")

    def test_the_sentinel_in_the_probes_own_echo_is_not_the_answer(self):
        # The probe's echo contains the sentinel because the command
        # text does. Reading the echo as output would make every
        # checked command fail, so the answer is the rows *after* it.
        rows = self._guest(self._frames(failed=False)).execute(
            "DRIVER.EXE", 1, check=True)
        self.assertEqual(rows, ("loading",))

    def test_an_unreadable_probe_refuses_rather_than_passing(self):
        # The probe never echoed, so its verdict cannot be read. An
        # unknown outcome is not a success (P11).
        frames = [
            [self.PROMPT],
            ["C:\\>DRIVER.EXE", "loading", self.PROMPT],
            [self.PROMPT],
            ["SOMETHING ELSE ENTIRELY", self.PROMPT],
        ]
        with self.assertRaises(RunFailure) as caught:
            self._guest(frames).execute("DRIVER.EXE", 1, check=True)
        self.assertEqual(caught.exception.rule_id,
                         "command.outcome-unreadable")
        self.assertIn("DRIVER.EXE", str(caught.exception))


class InBandFileTests(_HomeCase):
    """Guest-terms addressing over a vvfat drive (U14)."""

    def _rig(self):
        exchange = os.path.join(self.home, "exchange")
        os.makedirs(exchange)
        machine_id = self._create(
            "rig", {"platform": "dos",
                    "drives": {"hdd0": "blank",
                               "floppy0": "exchange-dir"}},
            media=[_BLANK,
                   {"name": "exchange-dir", "materialize": "use",
                    "location": {"local": exchange}}])
        return machine_id, exchange

    #: What an installed C: holds, for the at-rest tests.
    INSTALLED = {"AUTOEXEC.BAT": b"@ECHO OFF\r\n",
                 "OUT": {"RESULT.LOG": b"pass\r\n"}}

    def _image_rig(self):
        """The same rig, with a real filesystem on the hard disk."""
        self.backend.image_payload = fat_image.volume(self.INSTALLED)
        return self._rig()

    def _problems(self, machine_id):
        """Structural problems in the machine's disk, read independently."""
        path = self._state(machine_id)["drives"]["hdd0"]["path"]
        with open(path, "rb") as handle:
            return fat_image.consistency(handle.read())

    def test_an_exchange_disk_behind_an_installed_c_is_addressable(self):
        # The shape P16 was failing on: results live on an installed
        # C: and the exchange drive is the second disk. Its letter is
        # D: because the installed disk really does hold one volume —
        # read, now, rather than assumed.
        self.backend.image_payload = fat_image.volume(self.INSTALLED)
        exchange = os.path.join(self.home, "exchange2")
        os.makedirs(exchange)
        machine_id = self._create(
            "two-disks", {"platform": "dos",
                          "drives": {"hdd0": "blank",
                                     "hdd1": "exchange-dir"}},
            media=[_BLANK,
                   {"name": "exchange-dir", "materialize": "use",
                    "location": {"local": exchange}}])
        source = os.path.join(self.home, "X.TXT")
        with open(source, "w", encoding="ascii") as handle:
            handle.write("x")
        self.assertEqual(
            put_file(source, r"D:\X.TXT", machine=machine_id,
                     context=self.home), r"D:\X.TXT")
        with open(os.path.join(exchange, "X.TXT"), encoding="ascii") as h:
            self.assertEqual(h.read(), "x")

    def test_a_put_lands_where_the_guest_will_read_it(self):
        machine_id, exchange = self._rig()
        source = os.path.join(self.home, "TEST.EXE")
        with open(source, "wb") as handle:
            handle.write(b"MZ")
        address = put_file(source, r"A:\TEST.EXE", machine=machine_id,
                           context=self.home)
        self.assertEqual(address, r"A:\TEST.EXE")
        with open(os.path.join(exchange, "TEST.EXE"), "rb") as handle:
            self.assertEqual(handle.read(), b"MZ")

    def test_a_get_retrieves_by_guest_address(self):
        machine_id, exchange = self._rig()
        os.makedirs(os.path.join(exchange, "OUT"))
        with open(os.path.join(exchange, "OUT", "RESULT.TXT"), "w",
                  encoding="ascii") as handle:
            handle.write("PASS")
        target = os.path.join(self.home, "result.txt")
        written = get_file(r"A:\OUT\RESULT.TXT", target,
                           machine=machine_id, context=self.home)
        self.assertEqual(written, os.path.abspath(target))
        with open(target, encoding="ascii") as handle:
            self.assertEqual(handle.read(), "PASS")

    def test_a_running_machine_is_refused(self):
        machine_id, _exchange = self._rig()
        self._force(machine_id, "running", vm=True)
        with self.assertRaises(PreflightError) as caught:
            get_file(r"A:\X.TXT", os.path.join(self.home, "x"),
                     machine=machine_id, context=self.home)
        self.assertIn("must be stopped", str(caught.exception))

    def test_an_empty_removable_slot_says_it_is_empty(self):
        # Now reachable, because the letter map places a cdrom behind
        # a disk. It is neither an image nor a directory, and calling
        # it an image would be the lie the old message told. The disk
        # carries a real volume, which is what puts the cdrom at D:.
        self.backend.image_payload = fat_image.volume(self.INSTALLED)
        exchange = os.path.join(self.home, "exchange3")
        os.makedirs(exchange)
        machine_id = self._create(
            "with-cdrom", {"platform": "dos",
                           "drives": {"hdd0": "blank",
                                      "cdrom0": None,
                                      "floppy0": "exchange-dir"}},
            media=[_BLANK,
                   {"name": "exchange-dir", "materialize": "use",
                    "location": {"local": exchange}}])
        with self.assertRaises(PreflightError) as caught:
            list_files(r"D:\\", machine=machine_id, context=self.home)
        self.assertEqual(caught.exception.rule_id, "drive.slot-empty")
        self.assertIn("cdrom0", str(caught.exception))

    def test_an_image_drive_is_read_at_rest(self):
        # P16's residue closing: the results are on the installed C:,
        # the machine is stopped, and the disk is a file the host owns.
        machine_id, _exchange = self._image_rig()
        target = os.path.join(self.home, "got.txt")
        self.assertEqual(
            get_file(r"C:\OUT\RESULT.LOG", target, machine=machine_id,
                     context=self.home), target)
        with open(target, "rb") as handle:
            self.assertEqual(handle.read(), b"pass\r\n")

    def test_a_file_written_into_an_image_lands_in_the_volume(self):
        # The write half: the guest will read this at next boot, and
        # the volume is left structurally sound — checked by a reader
        # written from the format rather than by the one that wrote it.
        machine_id, _exchange = self._image_rig()
        source = os.path.join(self.home, "JOB.BAT")
        with open(source, "wb") as handle:
            handle.write(b"ECHO hello\r\n")
        self.assertEqual(
            put_file(source, r"C:\JOB.BAT", machine=machine_id,
                     context=self.home), r"C:\JOB.BAT")
        back = os.path.join(self.home, "back.bat")
        get_file(r"C:\JOB.BAT", back, machine=machine_id, context=self.home)
        with open(back, "rb") as handle:
            self.assertEqual(handle.read(), b"ECHO hello\r\n")
        self.assertEqual(self._problems(machine_id), [])

    def test_a_write_creates_the_directories_its_address_names(self):
        machine_id, _exchange = self._image_rig()
        source = os.path.join(self.home, "R.TXT")
        with open(source, "wb") as handle:
            handle.write(b"deep")
        put_file(source, r"C:\OUT\LOGS\R.TXT", machine=machine_id,
                 context=self.home)
        listed = list_files(r"C:\OUT\LOGS", machine=machine_id,
                            context=self.home)
        self.assertEqual([entry["address"] for entry in listed],
                         [r"C:\OUT\LOGS\R.TXT"])
        self.assertEqual(self._problems(machine_id), [])

    def test_a_name_the_guest_could_not_type_is_refused(self):
        # 8.3 or nothing: a silently truncated name would land
        # somewhere the caller never addressed (P11, P17).
        machine_id, _exchange = self._image_rig()
        source = os.path.join(self.home, "long.txt")
        with open(source, "wb") as handle:
            handle.write(b"x")
        with self.assertRaises(PreflightError) as caught:
            put_file(source, r"C:\RESULTS.TAR.GZ", machine=machine_id,
                     context=self.home)
        self.assertEqual(caught.exception.rule_id, "drive.image-unreadable")
        self.assertIn("8.3", str(caught.exception))

    def test_a_backend_that_cannot_rebuild_an_image_refuses_the_write(self):
        with fake_backend.installed(capabilities=Capabilities(
                backend="qemu",
                control_planes=("agentless-display",),
                media=("floppy", "hdd", "cdrom"),
                controllers=("ide",),
                materialize=("new", "difference", "copy", "use"),
                vvfat=True, at_rest=True)) as adapter:
            adapter.image_payload = fat_image.volume({"A.TXT": b"a"})
            machine_id = self._create(
                "read-only", {"platform": "dos",
                              "drives": {"hdd0": "blank"}},
                media=[_BLANK])
            source = os.path.join(self.home, "X.TXT")
            with open(source, "wb") as handle:
                handle.write(b"x")
            with self.assertRaises(PreflightError) as caught:
                put_file(source, r"C:\X.TXT", machine=machine_id,
                         context=self.home)
        self.assertEqual(caught.exception.rule_id, "drive.no-at-rest-write")

    def test_the_original_image_is_untouched_when_a_write_fails(self):
        # The safety property the scratch copy buys: a refusal partway
        # through leaves the machine's disk exactly as it was.
        machine_id, _exchange = self._image_rig()
        image = self._state(machine_id)["drives"]["hdd0"]["path"]
        with open(image, "rb") as handle:
            before = handle.read()
        source = os.path.join(self.home, "X.TXT")
        with open(source, "wb") as handle:
            handle.write(b"x")
        with self.assertRaises(PreflightError):
            put_file(source, r"C:\NOT A NAME.TXT", machine=machine_id,
                     context=self.home)
        with open(image, "rb") as handle:
            self.assertEqual(handle.read(), before)

    def test_a_backend_that_cannot_flatten_its_images_says_so(self):
        # Capability honesty at the seam: an adapter reporting no
        # at-rest access is refused before anything is copied, and the
        # message names the backend (P11).
        with fake_backend.installed(capabilities=Capabilities(
                backend="qemu",
                control_planes=("agentless-display",),
                media=("floppy", "hdd", "cdrom"),
                controllers=("ide",),
                materialize=("new", "difference", "copy", "use"),
                vvfat=True)) as adapter:
            adapter.image_payload = fat_image.volume({"A.TXT": b"a"})
            machine_id = self._create(
                "opaque", {"platform": "dos", "drives": {"hdd0": "blank"}},
                media=[_BLANK])
            with self.assertRaises(PreflightError) as caught:
                list_files("C:\\", machine=machine_id, context=self.home)
        self.assertEqual(caught.exception.rule_id, "drive.no-at-rest-access")
        self.assertIn("qemu", str(caught.exception))

    def test_a_disk_holding_two_volumes_gives_each_its_own_letter(self):
        """D71's defect, closed end to end.

        Two volumes on one disk used to be refused, because the letter
        map assumed one and could not say which letter the second
        took. It reads the count now, so both are addressable and
        each answers for itself.
        """
        self.backend.image_payload = fat_image.partitioned([
            fat_image.volume({"ONE.TXT": b"1"}, bits=16, sectors=20000,
                             per_cluster=4),
            fat_image.volume({"TWO.TXT": b"2"}, bits=16, sectors=20000,
                             per_cluster=4)])
        machine_id = self._create(
            "two-volumes", {"platform": "dos", "drives": {"hdd0": "blank"}},
            media=[_BLANK])
        self.assertEqual(
            [entry["name"] for entry in
             list_files("C:\\", machine=machine_id, context=self.home)],
            ["ONE.TXT"])
        self.assertEqual(
            [entry["name"] for entry in
             list_files("D:\\", machine=machine_id, context=self.home)],
            ["TWO.TXT"])

    def test_a_volume_count_is_recorded_and_cleared_by_a_start(self):
        """The cache and its invalidation, which is what makes reading
        the disk affordable *and* correct: a guest can only repartition
        while it runs, so a count cannot outlive the boot after it."""
        machine_id, _exchange = self._image_rig()
        list_files("C:\\", machine=machine_id, context=self.home)
        self.assertEqual(
            self._state(machine_id)["drives"]["hdd0"]["volumes"], 1)
        start_machine(machine_id=machine_id, context=self.home)
        self.assertNotIn(
            "volumes", self._state(machine_id)["drives"]["hdd0"])

    def test_an_undeclared_letter_names_the_ones_that_exist(self):
        # The disk is readable here on purpose: a letter nothing could
        # ever take is a different failure from one reliquary cannot
        # place, and this asserts the first.
        machine_id, _exchange = self._image_rig()
        with self.assertRaises(PreflightError) as caught:
            get_file(r"Z:\X.TXT", os.path.join(self.home, "x"),
                     machine=machine_id, context=self.home)
        self.assertIn("no drive at Z:", str(caught.exception))
        self.assertIn("A:", str(caught.exception))

    def test_an_address_may_not_escape_its_drive(self):
        machine_id, _exchange = self._rig()
        with self.assertRaises(StaticError):
            get_file(r"A:\..\..\secret.txt",
                     os.path.join(self.home, "x"),
                     machine=machine_id, context=self.home)

    def test_a_host_path_is_not_a_guest_address(self):
        machine_id, _exchange = self._rig()
        with self.assertRaises(StaticError) as caught:
            get_file("/etc/passwd", os.path.join(self.home, "x"),
                     machine=machine_id, context=self.home)
        self.assertIn("is not a DOS path", str(caught.exception))

    def test_a_missing_guest_file_fails_closed(self):
        machine_id, _exchange = self._rig()
        with self.assertRaises(PreflightError) as caught:
            get_file(r"A:\ABSENT.TXT", os.path.join(self.home, "x"),
                     machine=machine_id, context=self.home)
        self.assertIn(r"A:\ABSENT.TXT", str(caught.exception))


class DescribeDrivesTests(_HomeCase):
    """The drive report (D83): the record, its refresh, and the map."""

    def _two_volumes(self):
        return fat_image.partitioned([
            fat_image.volume({"ONE.TXT": b"1"}, bits=16, sectors=20000,
                             per_cluster=4),
            fat_image.volume({"TWO.TXT": b"2"}, bits=16, sectors=20000,
                             per_cluster=4)])

    def _geo(self, drives=None, media=None):
        return self._create(
            "geo", {"platform": "dos",
                    "drives": drives or {"hdd0": "blank"}},
            media=media or [_BLANK])

    def _entry(self, report, key):
        return next(drive for drive in report["drives"]
                    if drive["key"] == key)

    def test_a_create_records_nothing_and_describe_reads_once(self):
        """The one automatic read outside a start: no record yet, the
        machine down, and the report user-requested — the window
        between create and first start (D83)."""
        self.backend.image_payload = self._two_volumes()
        machine_id = self._geo()
        drive = self._state(machine_id)["drives"]["hdd0"]
        self.assertNotIn("geometry", drive)
        self.assertNotIn("volumes", drive)
        report = describe_drives(machine=machine_id, context=self.home)
        self.assertFalse(report["recorded"])
        record = self._entry(report, "hdd0")["geometry"]
        self.assertEqual(record["backing"], "raw")
        self.assertTrue(record["partitioned"])
        self.assertEqual(
            [volume["filesystem"] for volume in record["volumes"]],
            ["FAT16", "FAT16"])
        self.assertEqual(
            [entry["declares"] for entry in record["partitions"]],
            ["FAT16B", "FAT16B"])
        drive = self._state(machine_id)["drives"]["hdd0"]
        self.assertEqual(drive["volumes"], 2)
        self.assertIn("geometry", drive)

    def test_a_start_reads_this_boots_starting_state(self):
        """The automatic read is the first step of a start (D83), so
        the record a running machine answers from describes what the
        guest actually booted from — not what create materialized."""
        self.backend.image_payload = fat_image.volume(
            {"A.TXT": b"a"}, bits=16, sectors=20000, per_cluster=4)
        machine_id = self._geo()
        path = self._state(machine_id)["drives"]["hdd0"]["path"]
        with open(path, "wb") as handle:
            handle.write(self._two_volumes())
        start_machine(machine_id, context=self.home)
        record = self._state(machine_id)["drives"]["hdd0"]["geometry"]
        self.assertEqual(len(record["volumes"]), 2)

    def test_an_offline_describe_stands_on_the_record(self):
        """A recorded disk is not re-read by describe: a layout
        changed behind the record waits for the next start, or for
        an explicit refresh (D83)."""
        self.backend.image_payload = self._two_volumes()
        machine_id = self._geo()
        describe_drives(machine=machine_id, context=self.home)
        path = self._state(machine_id)["drives"]["hdd0"]["path"]
        with open(path, "wb") as handle:
            handle.write(b"\x01" * 4096)
        report = describe_drives(machine=machine_id, context=self.home)
        self.assertTrue(report["recorded"])
        record = self._entry(report, "hdd0")["geometry"]
        self.assertEqual(len(record["volumes"]), 2)

    def test_refresh_rereads_and_is_stopped_only(self):
        self.backend.image_payload = self._two_volumes()
        machine_id = self._geo()
        describe_drives(machine=machine_id, context=self.home)
        path = self._state(machine_id)["drives"]["hdd0"]["path"]
        with open(path, "wb") as handle:
            handle.write(b"\x01" * 4096)
        report = refresh_drives(machine=machine_id, context=self.home)
        self.assertFalse(report["recorded"])
        unread = self._entry(report, "hdd0")["geometry"]["unread"]
        self.assertEqual(unread["id"], "drive.image-unreadable")
        self._force(machine_id, "running", vm=True)
        with self.assertRaises(PreflightError) as caught:
            refresh_drives(machine=machine_id, context=self.home)
        self.assertEqual(caught.exception.rule_id,
                         "machine.must-be-stopped")

    def test_the_report_maps_letters_from_the_records(self):
        self.backend.image_payload = self._two_volumes()
        machine_id = self._geo(
            drives={"floppy0": None, "hdd0": "blank"})
        report = describe_drives(machine=machine_id, context=self.home)
        self.assertFalse(report["recorded"])
        self.assertEqual(report["platform"], "dos")
        self.assertEqual(report["mapping"]["letters"], {
            "A": {"drive": "floppy0", "volume": 0},
            "C": {"drive": "hdd0", "volume": 0},
            "D": {"drive": "hdd0", "volume": 1}})
        self.assertEqual(report["mapping"]["undetermined"], [])

    def test_the_lazy_read_reports_an_unreadable_disk(self):
        self.backend.image_payload = self._two_volumes()
        machine_id = self._geo()
        path = self._state(machine_id)["drives"]["hdd0"]["path"]
        with open(path, "wb") as handle:
            handle.write(b"\x01" * 4096)
        report = describe_drives(machine=machine_id, context=self.home)
        self.assertFalse(report["recorded"])
        unread = self._entry(report, "hdd0")["geometry"]["unread"]
        self.assertEqual(unread["id"], "drive.image-unreadable")
        self.assertEqual(
            [entry["drive"]
             for entry in report["mapping"]["undetermined"]],
            ["hdd0"])

    def test_a_running_machine_answers_from_the_record(self):
        self.backend.image_payload = self._two_volumes()
        machine_id = self._geo()
        start_machine(machine_id, context=self.home)
        path = self._state(machine_id)["drives"]["hdd0"]["path"]
        # The disk changes under the record; a running machine's
        # report must answer from the record, not the disk.
        with open(path, "wb") as handle:
            handle.write(b"\x01" * 4096)
        report = describe_drives(machine=machine_id, context=self.home)
        self.assertTrue(report["recorded"])
        self.assertEqual(report["phase"], "running")
        record = self._entry(report, "hdd0")["geometry"]
        self.assertEqual(len(record["volumes"]), 2)
        self.assertEqual(report["mapping"]["letters"]["C"],
                         {"drive": "hdd0", "volume": 0})

    def test_a_start_drops_the_count_and_keeps_the_record(self):
        self.backend.image_payload = self._two_volumes()
        machine_id = self._geo()
        start_machine(machine_id, context=self.home)
        drive = self._state(machine_id)["drives"]["hdd0"]
        self.assertNotIn("volumes", drive)
        self.assertIn("geometry", drive)

    def test_a_blocking_disk_answers_for_the_drives_behind_it(self):
        self.backend.image_payload = fat_image.volume(
            {"A.TXT": b"a"}, bits=16, sectors=20000, per_cluster=4)
        machine_id = self._geo(
            drives={"hdd0": "blank", "hdd1": "blank2"},
            media=[_BLANK, dict(_BLANK, name="blank2")])
        path = self._state(machine_id)["drives"]["hdd0"]["path"]
        with open(path, "wb") as handle:
            handle.write(b"\x01" * 4096)
        report = describe_drives(machine=machine_id, context=self.home)
        undetermined = report["mapping"]["undetermined"]
        self.assertEqual([entry["drive"] for entry in undetermined],
                         ["hdd0", "hdd1"])
        self.assertEqual(undetermined[0]["id"], "drive.image-unreadable")
        # The drive behind the blocker carries the blocker's reason,
        # not its own absence — the specific cause outranks the
        # symptom (P11).
        self.assertEqual(undetermined[1]["id"], "drive.image-unreadable")
        self.assertIn("hdd0", undetermined[1]["reason"])
        self.assertEqual(report["mapping"]["letters"], {})

    def test_a_directory_disk_reports_its_backing_unread(self):
        exchange = os.path.join(self.home, "exchange")
        os.makedirs(exchange)
        machine_id = self._geo(
            drives={"hdd0": "exchange-dir"},
            media=[{"name": "exchange-dir", "materialize": "use",
                    "location": {"local": exchange}}])
        report = describe_drives(machine=machine_id, context=self.home)
        record = self._entry(report, "hdd0")["geometry"]
        self.assertEqual(record["backing"], "directory")
        self.assertEqual(
            record["volumes"],
            [{"index": 0, "filesystem": None, "label": None,
              "size": None, "heads": None, "sectors-per-track": None}])
        self.assertEqual(report["mapping"]["letters"],
                         {"C": {"drive": "hdd0", "volume": 0}})


class InBandDirectoryTests(_HomeCase):
    """Listing and whole-tree transfer, the two P16 owed (F23)."""

    def _rig(self):
        exchange = os.path.join(self.home, "exchange")
        os.makedirs(exchange)
        machine_id = self._create(
            "rig", {"platform": "dos",
                    "drives": {"hdd0": "blank",
                               "floppy0": "exchange-dir"}},
            media=[_BLANK,
                   {"name": "exchange-dir", "materialize": "use",
                    "location": {"local": exchange}}])
        return machine_id, exchange

    @staticmethod
    def _place(path, text="x"):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="ascii") as handle:
            handle.write(text)

    def test_a_listing_reports_one_level_in_guest_terms(self):
        machine_id, exchange = self._rig()
        self._place(os.path.join(exchange, "JOB.BAT"), "ECHO")
        self._place(os.path.join(exchange, "OUT", "RESULT.TXT"), "PASS")
        entries = list_files("A:\\", machine=machine_id, context=self.home)
        self.assertEqual(
            entries,
            [{"address": r"A:\JOB.BAT", "name": "JOB.BAT",
              "kind": "file", "size": 4},
             {"address": r"A:\OUT", "name": "OUT",
              "kind": "directory", "size": None}])

    def test_a_recursive_listing_walks_the_tree(self):
        machine_id, exchange = self._rig()
        self._place(os.path.join(exchange, "OUT", "RESULT.TXT"), "PASS")
        addresses = [entry["address"] for entry
                     in list_files("A:\\", recursive=True,
                                   machine=machine_id, context=self.home)]
        self.assertEqual(addresses, [r"A:\OUT", r"A:\OUT\RESULT.TXT"])

    def test_a_listed_address_is_one_get_file_takes(self):
        # The point of reporting full addresses: no consumer composes
        # a guest path of its own (P17).
        machine_id, exchange = self._rig()
        self._place(os.path.join(exchange, "OUT", "RESULT.TXT"), "PASS")
        entry = [e for e in list_files(r"A:\OUT", machine=machine_id,
                                       context=self.home)][0]
        target = os.path.join(self.home, "result.txt")
        get_file(entry["address"], target, machine=machine_id,
                 context=self.home)
        with open(target, encoding="ascii") as handle:
            self.assertEqual(handle.read(), "PASS")

    def test_listing_a_file_says_it_is_a_file(self):
        machine_id, exchange = self._rig()
        self._place(os.path.join(exchange, "JOB.BAT"))
        with self.assertRaises(PreflightError) as caught:
            list_files(r"A:\JOB.BAT", machine=machine_id, context=self.home)
        self.assertIn("is a file, not a directory", str(caught.exception))

    def test_a_missing_guest_directory_is_not_an_empty_listing(self):
        machine_id, _exchange = self._rig()
        with self.assertRaises(PreflightError) as caught:
            list_files(r"A:\ABSENT", machine=machine_id, context=self.home)
        self.assertIn(r"A:\ABSENT", str(caught.exception))

    def test_a_put_places_the_trees_contents_at_the_address(self):
        machine_id, exchange = self._rig()
        source = os.path.join(self.home, "suite")
        self._place(os.path.join(source, "RUN.BAT"), "GO")
        self._place(os.path.join(source, "CASES", "ONE.DAT"), "1")
        written = put_files(source, "A:\\", machine=machine_id,
                            context=self.home)
        self.assertEqual(written, [r"A:\CASES\ONE.DAT", r"A:\RUN.BAT"])
        with open(os.path.join(exchange, "CASES", "ONE.DAT"),
                  encoding="ascii") as handle:
            self.assertEqual(handle.read(), "1")

    def test_a_put_makes_the_guest_directory_it_names(self):
        # put_file already creates the directories its address names,
        # so the plural verb refusing to would be arbitrary.
        machine_id, exchange = self._rig()
        source = os.path.join(self.home, "suite")
        self._place(os.path.join(source, "RUN.BAT"), "GO")
        written = put_files(source, r"A:\NEW\DEEP", machine=machine_id,
                            context=self.home)
        self.assertEqual(written, [r"A:\NEW\DEEP\RUN.BAT"])
        self.assertTrue(os.path.isfile(
            os.path.join(exchange, "NEW", "DEEP", "RUN.BAT")))

    def test_a_get_retrieves_the_whole_tree(self):
        machine_id, exchange = self._rig()
        self._place(os.path.join(exchange, "OUT", "RESULT.TXT"), "PASS")
        self._place(os.path.join(exchange, "OUT", "LOGS", "RUN.LOG"), "ok")
        target = os.path.join(self.home, "results")
        written = get_files(r"A:\OUT", target, machine=machine_id,
                            context=self.home)
        self.assertEqual(
            written,
            sorted([os.path.join(target, "LOGS", "RUN.LOG"),
                    os.path.join(target, "RESULT.TXT")]))
        with open(os.path.join(target, "LOGS", "RUN.LOG"),
                  encoding="ascii") as handle:
            self.assertEqual(handle.read(), "ok")

    def test_a_get_overwrites_rather_than_mirroring(self):
        # A copy, never a mirror: what was already at the destination
        # and is not in the guest survives.
        machine_id, exchange = self._rig()
        self._place(os.path.join(exchange, "OUT", "RESULT.TXT"), "NEW")
        target = os.path.join(self.home, "results")
        self._place(os.path.join(target, "RESULT.TXT"), "OLD")
        self._place(os.path.join(target, "MINE.TXT"), "keep")
        get_files(r"A:\OUT", target, machine=machine_id, context=self.home)
        with open(os.path.join(target, "RESULT.TXT"),
                  encoding="ascii") as handle:
            self.assertEqual(handle.read(), "NEW")
        self.assertTrue(os.path.isfile(os.path.join(target, "MINE.TXT")))

    def test_a_running_machine_is_refused(self):
        machine_id, _exchange = self._rig()
        self._force(machine_id, "running", vm=True)
        with self.assertRaises(PreflightError) as caught:
            list_files("A:\\", machine=machine_id, context=self.home)
        self.assertIn("must be stopped", str(caught.exception))

    def test_an_image_drive_lists_and_retrieves_at_rest(self):
        # The two read verbs over a drive image, in guest terms: the
        # listing's addresses are what get-files takes back.
        self.backend.image_payload = fat_image.volume(
            {"AUTOEXEC.BAT": b"@ECHO OFF\r\n",
             "OUT": {"RESULT.LOG": b"pass\r\n"}})
        machine_id, _exchange = self._rig()
        listed = list_files("C:\\", machine=machine_id, context=self.home)
        self.assertEqual([entry["address"] for entry in listed],
                         [r"C:\AUTOEXEC.BAT", r"C:\OUT"])
        self.assertEqual(listed[0]["size"], 11)
        self.assertIsNone(listed[1]["size"])
        deep = list_files("C:\\", recursive=True, machine=machine_id,
                          context=self.home)
        self.assertIn(r"C:\OUT\RESULT.LOG",
                      [entry["address"] for entry in deep])
        out = os.path.join(self.home, "retrieved")
        written = get_files("C:\\", out, machine=machine_id,
                            context=self.home)
        self.assertEqual(
            sorted(os.path.relpath(path, out) for path in written),
            ["AUTOEXEC.BAT", os.path.join("OUT", "RESULT.LOG")])

    def test_a_whole_tree_is_written_into_an_image(self):
        self.backend.image_payload = fat_image.volume({"A.TXT": b"a"})
        machine_id, _exchange = self._rig()
        suite = os.path.join(self.home, "suite")
        os.makedirs(os.path.join(suite, "CASES"))
        for path, text in ((os.path.join(suite, "RUN.BAT"), b"GO\r\n"),
                           (os.path.join(suite, "CASES", "ONE.TXT"), b"1")):
            with open(path, "wb") as handle:
                handle.write(text)
        written = put_files(suite, "C:\\", machine=machine_id,
                            context=self.home)
        self.assertEqual(written, [r"C:\CASES\ONE.TXT", r"C:\RUN.BAT"])
        listed = [entry["address"] for entry in
                  list_files("C:\\", recursive=True, machine=machine_id,
                             context=self.home)]
        self.assertEqual(listed, [r"C:\A.TXT", r"C:\CASES",
                                  r"C:\CASES\ONE.TXT", r"C:\RUN.BAT"])
        path = self._state(machine_id)["drives"]["hdd0"]["path"]
        with open(path, "rb") as handle:
            self.assertEqual(fat_image.consistency(handle.read()), [])

    def test_a_missing_host_directory_fails_closed(self):
        machine_id, _exchange = self._rig()
        with self.assertRaises(PreflightError) as caught:
            put_files(os.path.join(self.home, "absent"), "A:\\",
                      machine=machine_id, context=self.home)
        self.assertIn("no such directory", str(caught.exception))

    def test_a_host_destination_that_is_a_file_fails_closed(self):
        machine_id, exchange = self._rig()
        self._place(os.path.join(exchange, "OUT", "RESULT.TXT"))
        target = os.path.join(self.home, "results")
        self._place(target)
        with self.assertRaises(PreflightError) as caught:
            get_files(r"A:\OUT", target, machine=machine_id,
                      context=self.home)
        self.assertIn("is a file", str(caught.exception))

    def test_a_directory_address_may_not_escape_its_drive(self):
        machine_id, _exchange = self._rig()
        with self.assertRaises(StaticError):
            list_files(r"A:\..\..", machine=machine_id, context=self.home)


class DosAddressingTests(unittest.TestCase):
    """The letter map comes from declared facts alone (P10/P17)."""

    def test_mixed_controller_types_unfix_every_disk_letter(self):
        """The second thing that unfixes a letter, after volume count.

        Slot order is authoritative only within a controller type;
        across types the guest's firmware decides how the controllers
        enumerate, so even the *first* disk is not a declared fact.
        Unreachable today — only `ide` is wired — which is exactly why
        it is asserted here rather than left to the capability gate.
        """
        drives = {
            "floppy0": {"medium": "floppy", "slot": 0},
            "hdd0": {"medium": "hdd", "slot": 0, "controller": "ide"},
            "hdd1": {"medium": "hdd", "slot": 1, "controller": "scsi"},
        }
        counts = {"hdd0": 1, "hdd1": 1}
        self.assertEqual(platform_dos.drive_letters(drives, counts),
                         {"A": ("floppy0", 0)})
        # Both disks, named as undetermined rather than absent.
        self.assertEqual(platform_dos.undetermined_letters(drives, counts),
                         ["hdd0", "hdd1"])

    def test_one_controller_type_places_every_disk(self):
        # The guard must not fire on the single-type machines that
        # actually exist, floppies carrying no controller field.
        drives = {
            "floppy0": {"medium": "floppy", "slot": 0},
            "hdd0": {"medium": "hdd", "slot": 0, "controller": "ide"},
            "hdd1": {"medium": "hdd", "slot": 1, "controller": "ide"},
        }
        self.assertEqual(
            platform_dos.drive_letters(drives, {"hdd0": 1, "hdd1": 1}),
            {"A": ("floppy0", 0), "C": ("hdd0", 0), "D": ("hdd1", 0)})

    def test_every_drive_is_placed_from_the_volumes_each_disk_holds(self):
        # Disks from C: in slot order, then the CD-ROMs after them,
        # which is the order DOS assigns in.
        drives = {
            "floppy0": {"medium": "floppy", "slot": 0},
            "floppy1": {"medium": "floppy", "slot": 1},
            "hdd0": {"medium": "hdd", "slot": 0},
            "hdd1": {"medium": "hdd", "slot": 1},
            "cdrom0": {"medium": "cdrom", "slot": 0},
        }
        counts = {"hdd0": 1, "hdd1": 1}
        self.assertEqual(
            platform_dos.drive_letters(drives, counts),
            {"A": ("floppy0", 0), "B": ("floppy1", 0), "C": ("hdd0", 0),
             "D": ("hdd1", 0), "E": ("cdrom0", 0)})
        self.assertEqual(platform_dos.undetermined_letters(drives, counts),
                         [])

    def test_a_disk_of_two_volumes_takes_two_letters(self):
        """D71's defect, closed: the count places the letters.

        Under the assumption this returned C: and D: for the two
        disks, which is what a guest that repartitioned `hdd0` made
        silently wrong. Both volumes of `hdd0` are now addressable and
        `hdd1` is where DOS actually puts it.
        """
        drives = {
            "hdd0": {"medium": "hdd", "slot": 0},
            "hdd1": {"medium": "hdd", "slot": 1},
            "cdrom0": {"medium": "cdrom", "slot": 0},
        }
        self.assertEqual(
            platform_dos.drive_letters(drives, {"hdd0": 2, "hdd1": 1}),
            {"C": ("hdd0", 0), "D": ("hdd0", 1), "E": ("hdd1", 0),
             "F": ("cdrom0", 0)})

    def test_an_unpartitioned_disk_takes_no_letter(self):
        """DOS gives letters to volumes, not to disks.

        A blank reliquary just materialized holds nothing until a
        guest partitions it, so the drive behind it is C: — which the
        one-volume-per-disk assumption used to call D:.
        """
        drives = {
            "hdd0": {"medium": "hdd", "slot": 0},
            "hdd1": {"medium": "hdd", "slot": 1},
        }
        self.assertEqual(
            platform_dos.drive_letters(drives, {"hdd0": 0, "hdd1": 1}),
            {"C": ("hdd1", 0)})

    def test_a_disk_whose_volumes_are_unknown_stops_the_walk(self):
        """An unreadable disk moves everything behind it by an unknown
        amount, so nothing behind it is placed rather than guessed."""
        drives = {
            "hdd0": {"medium": "hdd", "slot": 0},
            "hdd1": {"medium": "hdd", "slot": 1},
            "floppy0": {"medium": "floppy", "slot": 0},
        }
        self.assertEqual(platform_dos.drive_letters(drives, {"hdd1": 1}),
                         {"A": ("floppy0", 0)})
        self.assertEqual(
            platform_dos.undetermined_letters(drives, {"hdd1": 1}),
            ["hdd0", "hdd1"])

    def test_cdroms_are_determined_when_no_hard_disk_shifts_them(self):
        # With no disk to carry volumes, nothing can move a cdrom's
        # letter, so they follow the floppies and are knowable.
        drives = {
            "floppy0": {"medium": "floppy", "slot": 0},
            "cdrom0": {"medium": "cdrom", "slot": 0},
            "cdrom1": {"medium": "cdrom", "slot": 1},
        }
        self.assertEqual(
            platform_dos.drive_letters(drives),
            {"A": ("floppy0", 0), "C": ("cdrom0", 0), "D": ("cdrom1", 0)})
        self.assertEqual(platform_dos.undetermined_letters(drives), [])

    def test_a_cdrom_takes_c_when_there_is_no_hard_disk(self):
        letters = platform_dos.drive_letters(
            {"cdrom0": {"medium": "cdrom", "slot": 0}})
        self.assertEqual(letters, {"C": ("cdrom0", 0)})

    def test_a_cdrom_follows_the_disk_it_sits_behind(self):
        drives = {
            "hdd0": {"medium": "hdd", "slot": 0},
            "cdrom0": {"medium": "cdrom", "slot": 0},
        }
        counts = {"hdd0": 1}
        self.assertEqual(platform_dos.drive_letters(drives, counts),
                         {"C": ("hdd0", 0), "D": ("cdrom0", 0)})
        self.assertEqual(platform_dos.undetermined_letters(drives, counts),
                         [])

    def test_an_address_splits_into_letter_and_segments(self):
        self.assertEqual(platform_dos.split_address(r"c:\DOS\FOO.TXT"),
                         ("C", ["DOS", "FOO.TXT"]))
        self.assertEqual(platform_dos.split_address("A:BAR.TXT"),
                         ("A", ["BAR.TXT"]))

    def test_a_drive_with_no_file_is_not_an_address(self):
        with self.assertRaises(StaticError):
            platform_dos.split_address("A:\\")

    def test_a_drive_root_is_a_directory_address(self):
        # The one thing a directory may say that a file may not: the
        # drive itself, spelled either way.
        self.assertEqual(platform_dos.split_directory_address("A:\\"),
                         ("A", []))
        self.assertEqual(platform_dos.split_directory_address("a:"),
                         ("A", []))

    def test_a_trailing_separator_is_the_same_directory(self):
        self.assertEqual(platform_dos.split_directory_address(r"A:\OUT"),
                         platform_dos.split_directory_address("A:\\OUT\\"))

    def test_a_directory_address_refuses_dot_segments(self):
        with self.assertRaises(StaticError):
            platform_dos.split_directory_address(r"A:\..\..")

    def test_an_address_renders_back_as_the_guest_writes_it(self):
        # What a listing reports is what the file verbs accept: one
        # vocabulary, not two spellings of it (P17).
        rendered = platform_dos.join_address("A", ["OUT", "RESULT.TXT"])
        self.assertEqual(rendered, r"A:\OUT\RESULT.TXT")
        self.assertEqual(platform_dos.split_address(rendered),
                         ("A", ["OUT", "RESULT.TXT"]))

    def test_a_non_dos_platform_fails_closed(self):
        from reliquary.machines import _addressing
        with self.assertRaises(PreflightError) as caught:
            _addressing("openbsd")
        self.assertIn("openbsd", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
