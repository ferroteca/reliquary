# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Tests for machine materialization and cached-state management.

The composed model: a machine's drive names a media, and the media owns
materialization (new/use/difference/copy). Tests write a composed
``.rlqb`` into the home and drive ``create_machine``; ``use`` media point
at a real local ISO (attached in place, no fetch), and blank/differencing
image creation is mocked.
"""

import json
import os
import tempfile
import unittest
from unittest import mock

from reliquary.machines import (apply_blueprint, create_machine,
                                destroy_machine, eject_media,
                                get_machine_dir, insert_media, list_machines,
                                load_machine_state, machine_dir_path,
                                machine_drive_args, mark_stopped,
                                recreate_machine, resolve_machine,
                                set_boot_order, start_machine, stop_machine)

_BLANK = {"name": "blank", "materialize": "new", "size": "20M"}


class _HomeCase(unittest.TestCase):
    def setUp(self):
        self.workdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.workdir.cleanup)
        self.home = self.workdir.name
        self.iso_path = os.path.join(self.home, "live.iso")
        with open(self.iso_path, "wb") as handle:
            handle.write(b"ISO-CONTENT")

    def _livecd(self):
        return {"name": "freedos-1.4-livecd", "materialize": "use",
                "read-only": True, "source": {"local": self.iso_path}}

    def _write(self, name, machine, media=None, archives=None):
        obj = {"machines": [dict(machine, name=name)]}
        if media is not None:
            obj["media"] = media
        if archives is not None:
            obj["archives"] = archives
        bpdir = os.path.join(self.home, "blueprints")
        os.makedirs(bpdir, exist_ok=True)
        with open(os.path.join(bpdir, f"{name}.rlqb"), "w",
                  encoding="utf-8") as handle:
            json.dump(obj, handle)

    def _create(self, name, machine, media=None, archives=None):
        self._write(name, machine, media, archives)
        with mock.patch("reliquary.machines.create_hdd_image"):
            return create_machine(name, context=self.home)

    def _state(self, machine_id):
        return load_machine_state(machine_id, self.home)

    def _identity(self, machine_id, port=4444):
        return {"port": port, "name": f"reliquary-{machine_id}",
                "uuid": "1" * 32, "pid": 1234}

    def _force(self, machine_id, phase, *, vm=False):
        state = self._state(machine_id)
        state["phase"] = phase
        if vm:
            # The live-VM identity is folded into machine.json now.
            state["vm"] = {"port": 54321, "name": f"reliquary-{machine_id}",
                           "uuid": "1" * 32, "pid": 1234}
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
        with mock.patch("reliquary.machines.create_hdd_image") as create_hdd:
            machine_id = create_machine("sized", context=self.home)
        calls = sorted((os.path.basename(c.args[0]), c.args[1])
                       for c in create_hdd.call_args_list)
        # Per-machine images are named for the media, not the slot.
        self.assertEqual(calls, [("blank.qcow2", "20M"),
                                 ("boot.qcow2", "720K")])
        state = self._state(machine_id)
        self.assertEqual(state["drives"]["hdd0"]["size"], "20M")
        self.assertEqual(state["drives"]["hdd0"]["materialize"], "new")

    def test_use_media_attaches_the_payload_path(self):
        machine_id = self._create(
            "with-media", {"platform": "dos",
                           "drives": {"hdd0": "blank", "cdrom0": "freedos-1.4-livecd"},
                           "boot": ["cdrom0", "hdd0"]},
            media=[_BLANK, self._livecd()])
        cdrom = self._state(machine_id)["drives"]["cdrom0"]
        self.assertEqual(cdrom["media"], "freedos-1.4-livecd")
        self.assertEqual(cdrom["materialize"], "use")
        self.assertEqual(os.path.normpath(cdrom["path"]),
                         os.path.normpath(self.iso_path))

    def test_difference_media_materializes_an_overlay(self):
        self._write("based", {"platform": "dos", "drives": {"hdd0": "base"}},
                   media=[{"name": "base", "materialize": "difference",
                           "source": {"local": self.iso_path}}])
        with mock.patch(
                "reliquary.machines.create_difference_image") as diff:
            machine_id = create_machine("based", context=self.home)
        self.assertEqual(os.path.basename(diff.call_args.args[0]),
                         "base.qcow2")
        self.assertEqual(diff.call_args.args[1], self.iso_path)
        self.assertEqual(self._state(machine_id)["drives"]["hdd0"][
            "materialize"], "difference")

    def test_copy_media_materializes_a_duplicate(self):
        self._write("dup", {"platform": "dos", "drives": {"hdd0": "base"}},
                   media=[{"name": "base", "materialize": "copy",
                           "source": {"local": self.iso_path}}])
        with mock.patch(
                "reliquary.machines.create_duplicate_image") as dupe:
            machine_id = create_machine("dup", context=self.home)
        dupe.assert_called_once()
        self.assertEqual(self._state(machine_id)["drives"]["hdd0"][
            "materialize"], "copy")

    def test_hostdir_media_renders_vvfat(self):
        work = os.path.join(self.home, "work")
        os.makedirs(work)
        machine_id = self._create(
            "hd", {"platform": "dos", "drives": {"hdd0": "shared"}},
            media=[{"name": "shared", "materialize": "use",
                    "source": {"local": work}}])
        drive = self._state(machine_id)["drives"]["hdd0"]
        self.assertEqual(os.path.normpath(drive["path"]),
                         os.path.normpath(work))
        values = _drive_values(machine_drive_args(machine_id, self.home))
        self.assertTrue(any("fat:rw:" in v for v in values))

    def test_cdrom_rejects_a_new_media(self):
        self._write("bad", {"platform": "dos", "drives": {"cdrom0": "blank"}},
                   media=[_BLANK])
        with self.assertRaises(ValueError) as caught:
            create_machine("bad", context=self.home)
        self.assertIn("cdrom", str(caught.exception))

    def test_nonide_controller_fails_closed(self):
        self._write("scsi", {"platform": "dos",
                            "drives": {"hdd0": {"media": "blank",
                                                "controller": "scsi"}}},
                   media=[_BLANK])
        with mock.patch("reliquary.machines.create_hdd_image"):
            with self.assertRaises(NotImplementedError) as caught:
                create_machine("scsi", context=self.home)
        self.assertIn("scsi", str(caught.exception))

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
        with mock.patch("reliquary.machines.create_hdd_image"):
            first = create_machine("twin", context=self.home)
            second = create_machine("twin", context=self.home)
        s1, s2 = self._state(first), self._state(second)
        self.assertTrue(s1["blueprint-source"].endswith("twin.rlqb"))
        self.assertEqual(s1["blueprint-digest"], s2["blueprint-digest"])
        self.assertNotEqual(first, second)

    def test_drive_args_cdrom_iso_after_hdd(self):
        def _fake_hdd(path, size):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as handle:
                handle.write(b"qcow2\x00" * 8)
            return path
        self._write("bootable", {"platform": "dos",
                               "drives": {"hdd0": "blank",
                                          "cdrom0": "freedos-1.4-livecd"},
                               "boot": ["cdrom0", "hdd0"]},
                   media=[_BLANK, self._livecd()])
        with mock.patch("reliquary.machines.create_hdd_image",
                        side_effect=_fake_hdd):
            machine_id = create_machine("bootable", context=self.home)
        values = _drive_values(machine_drive_args(machine_id, self.home))
        cdrom_arg = [v for v in values if "media=cdrom" in v]
        self.assertEqual(len(cdrom_arg), 1)
        self.assertIn("format=raw,", cdrom_arg[0])
        self.assertIn("if=ide,index=1", cdrom_arg[0])

    def test_drive_args_floppy_before_hdd(self):
        def _fake_hdd(path, size):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as handle:
                handle.write(b"qcow2\x00" * 8)
            return path
        self._write("mixed", {"platform": "dos",
                            "drives": {"floppy0": "flp", "hdd0": "blank"}},
                   media=[_BLANK, {"name": "flp", "materialize": "new",
                                   "size": "1440K"}])
        with mock.patch("reliquary.machines.create_hdd_image",
                        side_effect=_fake_hdd):
            machine_id = create_machine("mixed", context=self.home)
        values = _drive_values(machine_drive_args(machine_id, self.home))
        floppy_idx = next(i for i, v in enumerate(values) if "if=floppy" in v)
        hdd_idx = next(i for i, v in enumerate(values)
                       if "if=ide,index=0" in v)
        self.assertLess(floppy_idx, hdd_idx)

    def test_missing_state_raises_filenotfound(self):
        with self.assertRaises(FileNotFoundError):
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
        with self.assertRaises(FileNotFoundError):
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
        with mock.patch("reliquary.machines.find_qemu", return_value="qemu"), \
                mock.patch("reliquary.machines.launch_owned_qemu",
                           return_value=self._identity(machine_id)):
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
        with self.assertRaises(ValueError) as caught:
            resolve_machine(blueprint="missing", context=self.home)
        self.assertIn("no machine exists", str(caught.exception))

    def test_resolve_by_blueprint_ambiguous(self):
        self._ready("freedos")
        self._ready("freedos")
        with self.assertRaises(ValueError) as caught:
            resolve_machine(blueprint="freedos", context=self.home)
        self.assertIn("has 2 machines", str(caught.exception))

    def test_resolve_by_full_id_and_rejections(self):
        machine_id = self._ready("freedos")
        self.assertEqual(
            resolve_machine(machine=machine_id, context=self.home), machine_id)
        with self.assertRaises(ValueError):
            resolve_machine(blueprint="freedos", machine=machine_id,
                            context=self.home)
        with self.assertRaises(ValueError):
            resolve_machine(machine="0", context=self.home)
        with self.assertRaises(ValueError):
            resolve_machine(machine="freedos-", context=self.home)

    def test_start_launches_qemu_and_sets_running(self):
        machine_id = self._create(
            "bootable", {"platform": "dos",
                         "drives": {"hdd0": "blank", "cdrom0": "freedos-1.4-livecd"},
                         "boot": ["cdrom0", "hdd0"]},
            media=[_BLANK, self._livecd()])
        with mock.patch("reliquary.machines.find_qemu",
                        return_value="qemu-system-i386"), \
                mock.patch("reliquary.machines.launch_owned_qemu",
                           return_value=self._identity(machine_id)) as launch:
            port = start_machine(machine_id, context=self.home)
        self.assertEqual(port, 4444)
        args = launch.call_args.args[0]
        self.assertEqual(args[0], "qemu-system-i386")
        self.assertIn("order=dc", args)
        # QEMU's stderr log lands in the machine's backend subdirectory.
        self.assertEqual(
            launch.call_args.kwargs["log_dir"],
            os.path.join(machine_dir_path(machine_id, self.home), "qemu"))
        state = self._state(machine_id)
        self.assertEqual(state["phase"], "running")
        # The live-VM identity is folded into the state, atomic with phase.
        self.assertEqual(state["vm"]["port"], 4444)

    def test_start_rejects_already_running(self):
        machine_id = self._ready()
        self._force(machine_id, "running")
        with self.assertRaises(RuntimeError) as caught:
            start_machine(machine_id, context=self.home)
        self.assertIn("already running", str(caught.exception))

    def test_stop_returns_phase_to_ready(self):
        machine_id = self._ready()
        self._force(machine_id, "running", vm=True)
        with mock.patch("reliquary.machines.stop_owned_qemu") as stop_qemu:
            stop_machine(machine_id, context=self.home)
        # Lifecycle is handed the recorded VM identity, not a home dir.
        stop_qemu.assert_called_once()
        self.assertEqual(stop_qemu.call_args.args[0]["port"], 54321)
        state = self._state(machine_id)
        self.assertEqual(state["phase"], "ready")
        self.assertNotIn("vm", state)

    def test_stop_keeps_running_on_identity_mismatch(self):
        machine_id = self._ready()
        self._force(machine_id, "running", vm=True)
        with mock.patch("reliquary.machines.stop_owned_qemu",
                        side_effect=RuntimeError("QMP identity mismatch")):
            with self.assertRaisesRegex(RuntimeError, "identity mismatch"):
                stop_machine(machine_id, context=self.home)
        state = self._state(machine_id)
        self.assertEqual(state["phase"], "running")
        self.assertIn("vm", state)

    def test_stop_reconciles_when_vm_gone(self):
        machine_id = self._ready()
        self._force(machine_id, "running")
        with mock.patch("reliquary.machines.stop_owned_qemu",
                        side_effect=RuntimeError("no longer reachable")):
            with self.assertRaisesRegex(RuntimeError, "no longer reachable"):
                stop_machine(machine_id, context=self.home)
        self.assertEqual(self._state(machine_id)["phase"], "ready")

    def test_destroy_removes_directory(self):
        machine_id = self._ready()
        root = machine_dir_path(machine_id, self.home)
        destroy_machine(machine_id, context=self.home)
        self.assertFalse(os.path.exists(root))
        self.assertEqual(list_machines(context=self.home), [])

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
        with self.assertRaises(RuntimeError) as caught:
            destroy_machine(machine_id, context=self.home)
        self.assertIn("stop it before destroying", str(caught.exception))

    def test_generation_advances(self):
        machine_id = self._ready()
        self.assertEqual(self._state(machine_id)["generation"], 0)
        self._start(machine_id)
        gen1 = self._state(machine_id)["generation"]
        self.assertGreater(gen1, 0)
        with mock.patch("reliquary.machines.stop_owned_qemu"):
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
        with mock.patch("reliquary.machines.stop_owned_qemu") as stop_qemu:
            stop_machine(machine_id, context=self.home)
        stop_qemu.assert_called_once()
        self.assertEqual(self._state(machine_id)["phase"], "ready")

    def test_interrupted_create_rolled_back(self):
        machine_id = self._ready()
        self._force(machine_id, "creating")
        with self.assertRaises(RuntimeError) as caught:
            self._start(machine_id)
        self.assertIn("rolled back", str(caught.exception))
        self.assertFalse(os.path.exists(machine_dir_path(machine_id, self.home)))

    def test_interrupted_destroy_completes(self):
        machine_id = self._ready()
        self._force(machine_id, "destroying")
        with self.assertRaises(RuntimeError) as caught:
            self._start(machine_id)
        self.assertIn("removed", str(caught.exception))

    def test_failed_materialization_rolls_back(self):
        self._write("doomed", {"platform": "dos", "drives": {"hdd0": "blank"}},
                   media=[_BLANK])
        with mock.patch("reliquary.machines.create_hdd_image",
                        side_effect=RuntimeError("disk full")):
            with self.assertRaises(RuntimeError):
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
        with mock.patch("reliquary.machines.create_hdd_image"):
            again = recreate_machine(machine=machine_id, context=self.home)
        self.assertEqual(again, machine_id)

    def test_recreate_keeps_id_at_gap(self):
        self._write("g", {"platform": "dos", "drives": {"hdd0": "blank"}},
                   media=[_BLANK])
        with mock.patch("reliquary.machines.create_hdd_image"):
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
        with self.assertRaises(RuntimeError) as caught:
            apply_blueprint(machine=machine_id, context=self.home)
        self.assertIn("recreate", str(caught.exception))

    def test_apply_reconciles_diverged_media(self):
        machine_id = self._create(
            "dv", {"platform": "dos",
                   "drives": {"hdd0": "blank", "cdrom0": None},
                   "boot": ["hdd0", "cdrom0"]},
            media=[_BLANK, self._livecd()])
        insert_media(machine_id, "cdrom0", "freedos-1.4-livecd",
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

    def test_apply_requires_stopped(self):
        machine_id = self._ready()
        self._force(machine_id, "running")
        with self.assertRaises(RuntimeError) as caught:
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

    def test_empty_cdrom_renders_medium_less_drive(self):
        args = machine_drive_args(self._installer(), self.home)
        cdrom_arg = [v for v in _drive_values(args) if "media=cdrom" in v]
        self.assertEqual(cdrom_arg, ["media=cdrom,if=ide,index=1,id=cdrom0"])

    def test_insert_persists_media(self):
        machine_id = self._installer()
        insert_media(machine_id, "cdrom0", "freedos-1.4-livecd",
                     context=self.home)
        cdrom = self._state(machine_id)["drives"]["cdrom0"]
        self.assertEqual(cdrom["media"], "freedos-1.4-livecd")
        self.assertEqual(os.path.normpath(cdrom["path"]),
                         os.path.normpath(self.iso_path))

    def test_eject_returns_slot_to_empty(self):
        machine_id = self._installer()
        insert_media(machine_id, "cdrom0", "freedos-1.4-livecd",
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
        with self.assertRaises(RuntimeError):
            set_boot_order(machine_id, ["cdrom0"], context=self.home)

    def test_set_boot_order_rejects_undeclared(self):
        machine_id = self._installer()
        with self.assertRaises(ValueError) as caught:
            set_boot_order(machine_id, ["floppy0"], context=self.home)
        self.assertIn("undeclared drive floppy0", str(caught.exception))

    def test_hdd_then_cdrom_boot_order(self):
        machine_id = self._installer()
        with mock.patch("reliquary.machines.find_qemu", return_value="qemu"), \
                mock.patch("reliquary.machines.launch_owned_qemu",
                           return_value=self._identity(machine_id)) as launch:
            start_machine(machine_id, context=self.home)
        self.assertIn("order=cd", launch.call_args.args[0])

    def test_inserted_media_survives_start(self):
        machine_id = self._installer()
        insert_media(machine_id, "cdrom0", "freedos-1.4-livecd",
                     context=self.home)
        with mock.patch("reliquary.machines.find_qemu", return_value="qemu"), \
                mock.patch("reliquary.machines.launch_owned_qemu",
                           return_value=self._identity(machine_id)) as launch:
            start_machine(machine_id, context=self.home)
        cdrom_arg = [a for a in launch.call_args.args[0] if "media=cdrom" in a]
        self.assertEqual(len(cdrom_arg), 1)
        self.assertIn(self.iso_path, cdrom_arg[0])

    def test_insert_rejects_undeclared_slot(self):
        with self.assertRaises(ValueError) as caught:
            insert_media(self._installer(), "floppy0", "freedos-1.4-livecd",
                         context=self.home)
        self.assertIn("declares no drive floppy0", str(caught.exception))

    def test_insert_rejects_non_removable(self):
        with self.assertRaises(ValueError) as caught:
            insert_media(self._installer(), "hdd0", "freedos-1.4-livecd",
                         context=self.home)
        self.assertIn("not a removable drive slot", str(caught.exception))

    def test_insert_on_running_changes_live(self):
        machine_id = self._installer()
        self._force(machine_id, "running", vm=True)
        with mock.patch("reliquary.machines._change_media_live") as live:
            insert_media(machine_id, "cdrom0", "freedos-1.4-livecd",
                         context=self.home)
        live.assert_called_once()
        self.assertEqual(live.call_args.args[1], "cdrom0")
        self.assertEqual(self._state(machine_id)["drives"]["cdrom0"]["media"],
                         "freedos-1.4-livecd")

    def test_eject_on_running_ejects_live(self):
        machine_id = self._installer()
        insert_media(machine_id, "cdrom0", "freedos-1.4-livecd",
                     context=self.home)
        self._force(machine_id, "running", vm=True)
        with mock.patch("reliquary.machines._change_media_live") as live:
            eject_media(machine_id, "cdrom0", context=self.home)
        live.assert_called_once()
        self.assertIsNone(live.call_args.args[2])

    def test_change_media_live_hmp_commands(self):
        from reliquary import machines as machines_mod
        machine_id = self._installer()
        self._force(machine_id, "running", vm=True)
        fake_qmp = mock.MagicMock()
        session = mock.MagicMock()
        session.__enter__.return_value = fake_qmp
        session.__exit__.return_value = False
        with mock.patch("reliquary.machine.Machine.qmp", return_value=session):
            machines_mod._change_media_live(
                machine_id, "cdrom0", self.iso_path, self.home)
            machines_mod._change_media_live(
                machine_id, "cdrom0", None, self.home)
        lines = [c.args[0] for c in fake_qmp.hmp.call_args_list]
        self.assertTrue(any(line.startswith("change cdrom0 ")
                            and line.endswith(" raw") for line in lines))
        self.assertIn("eject cdrom0", lines)

    def test_insert_on_stopped_is_state_only(self):
        machine_id = self._installer()
        with mock.patch("reliquary.machines._change_media_live") as live:
            insert_media(machine_id, "cdrom0", "freedos-1.4-livecd",
                         context=self.home)
        live.assert_not_called()
        self.assertEqual(self._state(machine_id)["drives"]["cdrom0"]["media"],
                         "freedos-1.4-livecd")

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


def _drive_values(args):
    return [args[i + 1] for i, a in enumerate(args) if a == "-drive"]


if __name__ == "__main__":
    unittest.main()
