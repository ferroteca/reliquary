# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Tests for machine materialization and cached-state management."""

import json
import os
import tempfile
import unittest
from unittest import mock

from reliquary.blueprint import parse_blueprint
from reliquary.machines import (apply_blueprint, insert_media, create,
                                create_machine, destroy_machine,
                                eject_media, get_machine_dir,
                                list_machines,
                                load_machine_state, machine_dir_path,
                                machine_drive_args, mark_stopped,
                                recreate_machine,
                                resolve_machine, set_boot_order,
                                start_machine, stop_machine)


SHA256 = "1" * 64


class MachineMaterializationTests(unittest.TestCase):
    """Shared scaffolding: a temporary home with one media item."""

    def setUp(self):
        self.workdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.workdir.cleanup)
        self.home = self.workdir.name
        library = os.path.join(self.home, "media")
        os.makedirs(library)
        with open(os.path.join(library, "freedos.json"), "w",
                  encoding="utf-8") as handle:
            json.dump({
                "name": "freedos-1.4-livecd",
                "file": "FD14LIVE.iso",
                "sha256": SHA256,
            }, handle)
        self.iso_path = os.path.join(
            self.home, "cache", "media", "freedos-1.4-livecd.iso")

    def _blueprint(self, value):
        return parse_blueprint(value, context=self.home)

    def test_create_populates_the_machine_cache_directory(self):
        """The machine lands under cache/machines/<id>/ with a state
        file and a drives/ subdirectory."""
        blueprint = self._blueprint({
            "platform": "dos",
            "drives": {"hdd": {"size": "20M"}},
        })

        with mock.patch(
                "reliquary.machines.create_hdd_image") as create_hdd:
            machine_id = create(blueprint, context=self.home,
                                blueprint_name="test-bp")

        root = machine_dir_path(machine_id, self.home)
        self.assertTrue(os.path.isdir(root))
        self.assertTrue(os.path.isfile(
            os.path.join(root, "reliquary-machine.json")))
        self.assertTrue(os.path.isdir(os.path.join(root, "drives")))
        create_hdd.assert_called_once()
        args = create_hdd.call_args.args
        self.assertEqual(os.path.basename(args[0]), "hdd0.qcow2")
        self.assertIn(self.home, args[0])

    def test_create_writes_state_file_with_bookkeeping(self):
        """reliquary-machine.json records id, blueprint name, creation
        time, phase, and resolved blueprint fields."""
        blueprint = self._blueprint({
            "platform": "dos",
            "drives": {"hdd": {"size": "20M"}},
            "name": "Test Machine",
            "description": "A description.",
            "scripts": {"install": "install-script"},
        })

        with mock.patch("reliquary.machines.create_hdd_image"):
            machine_id = create(blueprint, context=self.home,
                                blueprint_name="freedos")

        state = load_machine_state(machine_id, self.home)
        self.assertEqual(state["id"], machine_id)
        self.assertEqual(state["blueprint"], "freedos")
        self.assertIn("created", state)
        self.assertEqual(state["phase"], "ready")
        self.assertEqual(state["backend"], "qemu")
        self.assertEqual(state["platform"], "dos")
        # Defaults are materialized into the resolved state.
        self.assertEqual(state["memory"], 16)
        self.assertEqual(state["cpus"], 1)
        self.assertEqual(state["control-planes"], ["agentless-display"])
        self.assertEqual(state["name"], "Test Machine")
        self.assertEqual(state["scripts"], {"install": "install-script"})
        self.assertEqual(state["boot"], ["hdd0"])
        # Provenance.
        self.assertEqual(state["backend-id"], f"reliquary-{machine_id}")
        self.assertTrue(
            state["blueprint-digest"].startswith("sha256:"))

    def test_create_writes_state_file_with_optional_fields_absent(self):
        """Omitted optional fields are None/empty in the state."""
        blueprint = self._blueprint({"platform": "dos"})

        with mock.patch("reliquary.machines.create_hdd_image"):
            machine_id = create(blueprint, context=self.home,
                                blueprint_name="minimal")

        state = load_machine_state(machine_id, self.home)
        self.assertEqual(state["memory"], 16)
        self.assertIsNone(state["name"])
        self.assertIsNone(state["description"])
        self.assertEqual(state["scripts"], {})
        self.assertEqual(state["drives"], {})
        self.assertEqual(state["boot"], [])

    def test_size_drive_creates_qcow2_image(self):
        """Every drive declared with size gets a qcow2 image whose
        filename is the drive key."""
        blueprint = self._blueprint({
            "platform": "dos",
            "drives": {
                "hdd": {"size": "20M"},
                "floppy1": {"size": "720K"},
            },
        })

        with mock.patch(
                "reliquary.machines.create_hdd_image") as create_hdd:
            machine_id = create(blueprint, context=self.home,
                                blueprint_name="sized")

        self.assertEqual(create_hdd.call_count, 2)
        calls = sorted(
            (os.path.basename(c.args[0]), c.args[1])
            for c in create_hdd.call_args_list)
        self.assertEqual(calls, [
            ("floppy1.qcow2", "720K"),
            ("hdd0.qcow2", "20M"),
        ])

        state = load_machine_state(machine_id, self.home)
        self.assertEqual(state["drives"]["hdd0"]["size"], "20M")
        self.assertEqual(state["drives"]["hdd0"]["medium"], "hdd")
        self.assertEqual(state["drives"]["floppy1"]["size"], "720K")
        self.assertEqual(state["drives"]["floppy1"]["medium"], "floppy")

    def test_media_drive_fetches_and_records_payload_path(self):
        """A media drive calls fetch_media and records the returned
        payload path in the state."""
        blueprint = self._blueprint({
            "platform": "dos",
            "drives": {
                "cdrom": "freedos-1.4-livecd",
                "hdd": {"size": "20M"},
            },
            "boot": ["cdrom", "hdd"],
        })

        with mock.patch(
                "reliquary.machines.create_hdd_image") as create_hdd, \
                mock.patch("reliquary.machines.fetch_media",
                           return_value=self.iso_path) as fetch:
            machine_id = create(blueprint, context=self.home,
                                blueprint_name="with-media")

        fetch.assert_called_once_with("freedos-1.4-livecd",
                                      context=self.home)
        state = load_machine_state(machine_id, self.home)
        cdrom = state["drives"]["cdrom0"]
        self.assertEqual(cdrom["medium"], "cdrom")
        self.assertEqual(cdrom["media"], "freedos-1.4-livecd")
        self.assertEqual(
            os.path.normpath(cdrom["path"]),
            os.path.normpath(self.iso_path),
        )

    def test_base_difference_materializes_and_records(self):
        """A base drive (default difference) materializes a qcow2 and
        records its media/type in the state."""
        blueprint = self._blueprint({
            "platform": "dos",
            "drives": {"hdd0": {"base": "freedos-1.4-livecd"}},
        })
        with mock.patch("reliquary.machines.fetch_media",
                        return_value=self.iso_path), \
                mock.patch(
                    "reliquary.machines.create_difference_image") as diff:
            machine_id = create(blueprint, context=self.home,
                                blueprint_name="based")
        dest = diff.call_args.args[0]
        self.assertEqual(os.path.basename(dest), "hdd0.qcow2")
        self.assertEqual(diff.call_args.args[1], self.iso_path)
        state = load_machine_state(machine_id, self.home)
        base = state["drives"]["hdd0"]["base"]
        self.assertEqual(base, {"media": "freedos-1.4-livecd",
                                "type": "difference"})

    def test_base_duplicate_materializes(self):
        blueprint = self._blueprint({
            "platform": "dos",
            "drives": {"hdd0": {"base": {"media": "freedos-1.4-livecd",
                                         "type": "duplicate"}}},
        })
        with mock.patch("reliquary.machines.fetch_media",
                        return_value=self.iso_path), \
                mock.patch(
                    "reliquary.machines.create_duplicate_image") as dup:
            machine_id = create(blueprint, context=self.home,
                                blueprint_name="dup")
        dup.assert_called_once()
        state = load_machine_state(machine_id, self.home)
        self.assertEqual(state["drives"]["hdd0"]["base"]["type"],
                         "duplicate")

    def test_hostdir_resolves_and_renders_vvfat(self):
        work = os.path.join(self.home, "work")
        os.makedirs(work)
        blueprint = self._blueprint({
            "platform": "dos",
            "drives": {"hdd0": {"hostdir": work}},
        })
        machine_id = create(blueprint, context=self.home,
                            blueprint_name="hd")
        state = load_machine_state(machine_id, self.home)
        drive = state["drives"]["hdd0"]
        self.assertEqual(drive["hostdir"], work)
        self.assertEqual(os.path.normpath(drive["path"]),
                         os.path.normpath(work))
        args = machine_drive_args(machine_id, self.home)
        drive_values = [args[i + 1] for i, a in enumerate(args)
                        if a == "-drive"]
        self.assertTrue(any("fat:rw:" in v for v in drive_values))

    def test_hostdir_missing_directory_fails_closed(self):
        blueprint = self._blueprint({
            "platform": "dos",
            "drives": {"hdd0": {"hostdir": os.path.join(self.home, "nope")}},
        })
        with self.assertRaises(FileNotFoundError) as caught:
            create(blueprint, context=self.home, blueprint_name="missing")
        self.assertIn("nope", str(caught.exception))

    def test_nonide_controller_fails_closed(self):
        blueprint = self._blueprint({
            "platform": "dos",
            "drives": {"hdd0": {"size": "20M", "controller": "scsi"}},
        })
        with self.assertRaises(NotImplementedError) as caught:
            create(blueprint, context=self.home, blueprint_name="scsi")
        self.assertIn("scsi", str(caught.exception))

    def test_disabled_drive_excluded_from_state(self):
        blueprint = self._blueprint({
            "platform": "dos",
            "drives": {
                "hdd0": {"size": "20M"},
                "hdd1": {"size": "50M", "enabled": False},
            },
        })
        with mock.patch("reliquary.machines.create_hdd_image"):
            machine_id = create(blueprint, context=self.home,
                                blueprint_name="disabled")
        state = load_machine_state(machine_id, self.home)
        self.assertIn("hdd0", state["drives"])
        self.assertNotIn("hdd1", state["drives"])

    def test_blueprint_source_recorded_and_digest_stable(self):
        """create_machine records the resolved source path, and two
        machines of one blueprint share a digest (path excluded)."""
        bp_dir = os.path.join(self.home, "blueprints")
        os.makedirs(bp_dir)
        source = os.path.join(bp_dir, "twin.rlqb")
        with open(source, "w", encoding="utf-8") as handle:
            json.dump({"platform": "dos",
                       "drives": {"hdd": {"size": "20M"}}}, handle)
        with mock.patch("reliquary.machines.create_hdd_image"):
            first = create_machine("twin", context=self.home)
            second = create_machine("twin", context=self.home)
        s1 = load_machine_state(first, self.home)
        s2 = load_machine_state(second, self.home)
        self.assertEqual(
            os.path.normpath(s1["blueprint-source"]),
            os.path.normpath(source))
        self.assertEqual(s1["blueprint-digest"], s2["blueprint-digest"])
        self.assertNotEqual(first, second)

    def test_machine_drive_args_includes_cdrom_iso(self):
        """machine_drive_args mounts a cdrom media drive after hard
        disks on the IDE bus, with format=raw for .iso files."""
        blueprint = self._blueprint({
            "platform": "dos",
            "drives": {
                "hdd": {"size": "20M"},
                "cdrom": "freedos-1.4-livecd",
            },
            "boot": ["cdrom", "hdd"],
        })

        def _fake_create_hdd(path, size):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as handle:
                handle.write(b"qcow2\x00" * 1024)
            return path

        with mock.patch(
                "reliquary.machines.create_hdd_image",
                side_effect=_fake_create_hdd), \
                mock.patch("reliquary.machines.fetch_media",
                           return_value=self.iso_path):
            machine_id = create(blueprint, context=self.home,
                                blueprint_name="bootable")

        state = load_machine_state(machine_id, self.home)
        hdd_path = state["drives"]["hdd0"]["path"]
        self.assertTrue(os.path.isfile(hdd_path))

        args = machine_drive_args(machine_id, self.home)
        self.assertIn("-drive", args)
        drive_values = [args[i + 1] for i, a in enumerate(args)
                        if a == "-drive"]

        hdd_arg = [v for v in drive_values if "if=ide,index=0" in v]
        self.assertEqual(len(hdd_arg), 1)
        self.assertIn(f"file={hdd_path},", hdd_arg[0])

        cdrom_arg = [v for v in drive_values if "media=cdrom" in v]
        self.assertEqual(len(cdrom_arg), 1)
        self.assertIn(self.iso_path.replace(os.sep, "/"),
                      cdrom_arg[0].replace(os.sep, "/"))
        self.assertIn("format=raw,", cdrom_arg[0])
        self.assertIn("if=ide,index=1", cdrom_arg[0])

    def test_drive_args_floppy_comes_before_hdd(self):
        """Floppy drives are rendered before hard disks."""
        blueprint = self._blueprint({
            "platform": "dos",
            "drives": {
                "floppy": {"size": "1440K"},
                "hdd": {"size": "20M"},
            },
        })

        with mock.patch(
                "reliquary.machines.create_hdd_image") as create_hdd:
            def _fake_create(path, size):
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "wb") as handle:
                    handle.write(b"qcow2\x00" * 1024)
                return path
            create_hdd.side_effect = _fake_create
            machine_id = create(blueprint, context=self.home,
                                blueprint_name="mixed")

        args = machine_drive_args(machine_id, self.home)
        drive_indices = [i for i, a in enumerate(args) if a == "-drive"]
        values = [args[i + 1] for i in drive_indices]
        floppy_idx = next(
            i for i, v in enumerate(values) if "if=floppy" in v)
        hdd_idx = next(
            i for i, v in enumerate(values) if "if=ide,index=0" in v)
        self.assertLess(floppy_idx, hdd_idx)

    def test_missing_state_raises_filenotfound(self):
        """A machine id with no cache directory raises
        FileNotFoundError."""
        with self.assertRaises(FileNotFoundError) as caught:
            load_machine_state("nonexistent", context=self.home)
        self.assertIn("nonexistent", str(caught.exception))

    def test_machine_id_is_numbered_per_blueprint(self):
        """Creates allocate <blueprint>-<n>, reusing the lowest free n."""
        blueprint = self._blueprint({"platform": "dos"})

        with mock.patch("reliquary.machines.create_hdd_image"):
            first = create(blueprint, context=self.home,
                           blueprint_name="plain")
            second = create(blueprint, context=self.home,
                            blueprint_name="plain")
            other = create(blueprint, context=self.home,
                           blueprint_name="other")

        self.assertEqual(first, "plain-0")
        self.assertEqual(second, "plain-1")
        self.assertEqual(other, "other-0")

        destroy_machine(second, context=self.home)
        with mock.patch("reliquary.machines.create_hdd_image"):
            reused = create(blueprint, context=self.home,
                            blueprint_name="plain")
        self.assertEqual(reused, "plain-1")

    def test_create_requires_blueprint_name(self):
        """create rejects an empty blueprint_name."""
        blueprint = self._blueprint({"platform": "dos"})
        with self.assertRaises(ValueError) as caught:
            create(blueprint, context=self.home)
        self.assertIn("blueprint_name", str(caught.exception))

    def test_create_exposes_public_surface(self):
        """The module's public functions are importable and callable."""
        import reliquary.machines as machines_module
        for name in ("create", "create_machine", "destroy_machine",
                     "list_machines", "load_machine_state",
                     "machine_dir_path", "machine_drive_args",
                     "resolve_machine", "start_machine", "stop_machine"):
            self.assertTrue(hasattr(machines_module, name), name)

    def _create_ready(self, blueprint_name="test-bp", **fields):
        value = {"platform": "dos", "drives": {"hdd": {"size": "20M"}}}
        value.update(fields)
        blueprint = self._blueprint(value)
        with mock.patch("reliquary.machines.create_hdd_image"):
            return create(blueprint, context=self.home,
                          blueprint_name=blueprint_name)

    def test_list_machines_returns_created_states(self):
        """list_machines scans the cache and returns state dicts."""
        first = self._create_ready("alpha")
        second = self._create_ready("beta")

        listed = list_machines(context=self.home)
        ids = {state["id"] for state in listed}
        self.assertEqual(ids, {first, second})

        filtered = list_machines(context=self.home, blueprint="alpha")
        self.assertEqual([state["id"] for state in filtered], [first])

    def test_list_machines_orders_by_number(self):
        """Machines of one blueprint list in ascending number order."""
        self._create_ready("plain")
        self._create_ready("plain")
        self._create_ready("plain")
        destroy_machine("plain-1", context=self.home)
        ordered = [state["id"] for state in list_machines(
            context=self.home, blueprint="plain")]
        self.assertEqual(ordered, ["plain-0", "plain-2"])

    def test_resolve_machine_by_blueprint_sole_match(self):
        """--blueprint selects the sole machine of that blueprint."""
        machine_id = self._create_ready("freedos")
        self.assertEqual(
            resolve_machine(blueprint="freedos", context=self.home),
            machine_id)
        self.assertEqual(machine_id, "freedos-0")

    def test_resolve_machine_by_blueprint_none_suggests_create(self):
        """No machine for a blueprint names create-machine in the error."""
        with self.assertRaises(ValueError) as caught:
            resolve_machine(blueprint="missing", context=self.home)
        message = str(caught.exception)
        self.assertIn("no machine exists", message)
        self.assertIn(
            "rlq create-machine --blueprint missing", message)

    def test_resolve_machine_by_blueprint_ambiguous(self):
        """Several machines of one blueprint require --machine <id>."""
        self._create_ready("freedos")
        self._create_ready("freedos")
        with self.assertRaises(ValueError) as caught:
            resolve_machine(blueprint="freedos", context=self.home)
        message = str(caught.exception)
        self.assertIn("has 2 machines", message)
        self.assertIn("--machine <id>", message)

    def test_resolve_machine_by_full_id(self):
        """--machine accepts the full <blueprint>-<n> id."""
        machine_id = self._create_ready("freedos")
        self.assertEqual(
            resolve_machine(machine=machine_id, context=self.home),
            machine_id)

    def test_resolve_machine_rejects_blueprint_and_machine(self):
        """--blueprint and --machine together are rejected."""
        self._create_ready("freedos")
        with self.assertRaises(ValueError) as caught:
            resolve_machine(blueprint="freedos", machine="freedos-0",
                            context=self.home)
        self.assertIn("mutually exclusive", str(caught.exception))

    def test_resolve_machine_rejects_bare_number(self):
        """A bare machine number is never a machine id."""
        self._create_ready("freedos")
        with self.assertRaises(ValueError) as caught:
            resolve_machine(machine="0", context=self.home)
        self.assertIn("<blueprint>-<n>", str(caught.exception))

    def test_resolve_machine_rejects_prefix(self):
        """--machine requires the full id — no prefix matching."""
        self._create_ready("freedos")
        with self.assertRaises(ValueError) as caught:
            resolve_machine(machine="freedos-", context=self.home)
        self.assertIn("no machine", str(caught.exception))

    def test_start_launches_qemu_and_sets_running(self):
        """start re-verifies media, launches QEMU, and sets phase."""
        blueprint = self._blueprint({
            "platform": "dos",
            "drives": {
                "hdd": {"size": "20M"},
                "cdrom": "freedos-1.4-livecd",
            },
            "boot": ["cdrom", "hdd"],
        })
        with mock.patch("reliquary.machines.create_hdd_image"), \
                mock.patch("reliquary.machines.fetch_media",
                           return_value=self.iso_path):
            machine_id = create(blueprint, context=self.home,
                                blueprint_name="bootable")

        with mock.patch("reliquary.machines.find_qemu",
                        return_value="qemu-system-i386"), \
                mock.patch("reliquary.machines.fetch_media",
                           return_value=self.iso_path) as fetch, \
                mock.patch("reliquary.machines.launch_owned_qemu",
                           return_value=4444) as launch:
            port = start_machine(machine_id, context=self.home)

        self.assertEqual(port, 4444)
        fetch.assert_called_with("freedos-1.4-livecd", context=self.home)
        launch.assert_called_once()
        args = launch.call_args.args[0]
        self.assertEqual(args[0], "qemu-system-i386")
        self.assertIn("-m", args)
        self.assertIn("16", args)
        self.assertIn("-boot", args)
        self.assertIn("order=dc", args)
        self.assertEqual(
            launch.call_args.kwargs["home"],
            machine_dir_path(machine_id, self.home))
        self.assertEqual(
            load_machine_state(machine_id, self.home)["phase"],
            "running")

    def test_start_rejects_already_running(self):
        """Starting a running machine fails closed."""
        machine_id = self._create_ready()
        state = load_machine_state(machine_id, self.home)
        state["phase"] = "running"
        with open(os.path.join(machine_dir_path(machine_id, self.home),
                               "reliquary-machine.json"), "w",
                  encoding="utf-8") as handle:
            json.dump(state, handle)
        with self.assertRaises(RuntimeError) as caught:
            start_machine(machine_id, context=self.home)
        self.assertIn("already running", str(caught.exception))

    def test_stop_returns_phase_to_ready(self):
        """stop powers off the owned QEMU and sets phase ready."""
        machine_id = self._create_ready()
        state = load_machine_state(machine_id, self.home)
        state["phase"] = "running"
        with open(os.path.join(machine_dir_path(machine_id, self.home),
                               "reliquary-machine.json"), "w",
                  encoding="utf-8") as handle:
            json.dump(state, handle)

        with mock.patch("reliquary.machines.stop_owned_qemu") as stop_qemu:
            stop_machine(machine_id, context=self.home)

        stop_qemu.assert_called_once_with(
            home=machine_dir_path(machine_id, self.home))
        self.assertEqual(
            load_machine_state(machine_id, self.home)["phase"],
            "ready")

    def test_stop_keeps_phase_running_on_identity_mismatch(self):
        """A refused stop must not lie about the machine's phase.

        When the lifecycle stop fails closed (identity mismatch: the
        server at the recorded port is not our VM), vm.json survives
        and our QEMU may still be running — the phase must stay
        `running` so destroy and a second start stay blocked. Only a
        stop that found the recorded VM gone (stale state removed)
        may reconcile the phase to `ready`.
        """
        machine_id = self._create_ready()
        state = load_machine_state(machine_id, self.home)
        state["phase"] = "running"
        machine_home = machine_dir_path(machine_id, self.home)
        with open(os.path.join(machine_home,
                               "reliquary-machine.json"), "w",
                  encoding="utf-8") as handle:
            json.dump(state, handle)
        with open(os.path.join(machine_home, "vm.json"), "w",
                  encoding="utf-8") as handle:
            json.dump({"port": 54321, "name": f"reliquary-{machine_id}",
                       "uuid": "11111111-1111-1111-1111-111111111111",
                       "pid": 1234}, handle)

        with mock.patch(
                "reliquary.machines.stop_owned_qemu",
                side_effect=RuntimeError("QMP identity mismatch")):
            with self.assertRaisesRegex(RuntimeError,
                                        "identity mismatch"):
                stop_machine(machine_id, context=self.home)

        self.assertEqual(
            load_machine_state(machine_id, self.home)["phase"],
            "running")

    def test_stop_reconciles_phase_when_the_vm_is_gone(self):
        """An unreachable recorded VM (stale state removed by the
        lifecycle stop) returns the machine to `ready`."""
        machine_id = self._create_ready()
        state = load_machine_state(machine_id, self.home)
        state["phase"] = "running"
        machine_home = machine_dir_path(machine_id, self.home)
        with open(os.path.join(machine_home,
                               "reliquary-machine.json"), "w",
                  encoding="utf-8") as handle:
            json.dump(state, handle)

        with mock.patch(
                "reliquary.machines.stop_owned_qemu",
                side_effect=RuntimeError("no longer reachable")):
            with self.assertRaisesRegex(RuntimeError,
                                        "no longer reachable"):
                stop_machine(machine_id, context=self.home)

        self.assertEqual(
            load_machine_state(machine_id, self.home)["phase"],
            "ready")

    def test_destroy_removes_machine_directory(self):
        """destroy deletes a ready machine's cache directory."""
        machine_id = self._create_ready()
        root = machine_dir_path(machine_id, self.home)
        self.assertTrue(os.path.isdir(root))
        destroy_machine(machine_id, context=self.home)
        self.assertFalse(os.path.exists(root))
        self.assertEqual(list_machines(context=self.home), [])

    def test_destroy_retries_an_interrupted_destroy(self):
        """A failed deletion leaves the machine ready for another try."""
        machine_id = self._create_ready()
        root = machine_dir_path(machine_id, self.home)

        with mock.patch("reliquary.machines.shutil.rmtree",
                        side_effect=PermissionError("locked output")):
            with self.assertRaises(PermissionError):
                destroy_machine(machine_id, context=self.home)

        self.assertEqual(load_machine_state(machine_id, self.home)["phase"],
                         "ready")
        destroy_machine(machine_id, context=self.home)
        self.assertFalse(os.path.exists(root))

    def test_destroy_retries_a_previously_interrupted_destroy(self):
        """A legacy destroying phase can be recovered by retrying it."""
        machine_id = self._create_ready()
        state_path = os.path.join(machine_dir_path(machine_id, self.home),
                                  "reliquary-machine.json")
        state = load_machine_state(machine_id, self.home)
        state["phase"] = "destroying"
        with open(state_path, "w", encoding="utf-8") as handle:
            json.dump(state, handle)

        destroy_machine(machine_id, context=self.home)
        self.assertFalse(os.path.exists(machine_dir_path(machine_id,
                                                         self.home)))

    def test_destroy_rejects_running_machine(self):
        """A running machine must be stopped before destroy."""
        machine_id = self._create_ready()
        state = load_machine_state(machine_id, self.home)
        state["phase"] = "running"
        with open(os.path.join(machine_dir_path(machine_id, self.home),
                               "reliquary-machine.json"), "w",
                  encoding="utf-8") as handle:
            json.dump(state, handle)
        with self.assertRaises(RuntimeError) as caught:
            destroy_machine(machine_id, context=self.home)
        self.assertIn("stop it before destroying", str(caught.exception))

    def _force_phase(self, machine_id, phase, **extra):
        """Write a phase directly, simulating an interrupted operation."""
        path = os.path.join(machine_dir_path(machine_id, self.home),
                            "reliquary-machine.json")
        state = load_machine_state(machine_id, self.home)
        state["phase"] = phase
        state.update(extra)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(state, handle)

    def _start(self, machine_id):
        with mock.patch("reliquary.machines.find_qemu",
                        return_value="qemu"), \
                mock.patch("reliquary.machines.launch_owned_qemu",
                           return_value=4444):
            return start_machine(machine_id, context=self.home)

    def test_generation_advances_across_operations(self):
        machine_id = self._create_ready()
        gen0 = load_machine_state(machine_id, self.home)["generation"]
        self.assertEqual(gen0, 0)
        self._start(machine_id)
        gen1 = load_machine_state(machine_id, self.home)["generation"]
        self.assertGreater(gen1, gen0)
        with mock.patch("reliquary.machines.stop_owned_qemu"):
            stop_machine(machine_id, context=self.home)
        gen2 = load_machine_state(machine_id, self.home)["generation"]
        self.assertGreater(gen2, gen1)

    def test_operation_takes_a_per_machine_lock(self):
        machine_id = self._create_ready()
        self._start(machine_id)
        lock = os.path.join(self.home, "cache", "machines", ".locks",
                            f"{machine_id}.op.lock")
        self.assertTrue(os.path.exists(lock))

    def test_interrupted_stop_is_completed_on_next_operation(self):
        """A machine stranded in `stopping` completes its stop when the
        next operation reconciles it."""
        machine_id = self._create_ready()
        self._force_phase(machine_id, "stopping")
        with mock.patch("reliquary.machines.stop_owned_qemu") as stop_qemu:
            stop_machine(machine_id, context=self.home)
        stop_qemu.assert_called_once()
        self.assertEqual(
            load_machine_state(machine_id, self.home)["phase"], "ready")

    def test_interrupted_create_is_rolled_back(self):
        """An operation on a machine stranded in `creating` rolls it
        back (removes it) and fails closed with recovery guidance."""
        machine_id = self._create_ready()
        self._force_phase(machine_id, "creating")
        with self.assertRaises(RuntimeError) as caught:
            self._start(machine_id)
        self.assertIn("rolled back", str(caught.exception))
        self.assertFalse(
            os.path.exists(machine_dir_path(machine_id, self.home)))

    def test_interrupted_destroy_completes_on_other_operation(self):
        machine_id = self._create_ready()
        self._force_phase(machine_id, "destroying")
        with self.assertRaises(RuntimeError) as caught:
            self._start(machine_id)
        self.assertIn("removed", str(caught.exception))
        self.assertFalse(
            os.path.exists(machine_dir_path(machine_id, self.home)))

    def test_failed_materialization_rolls_back_create(self):
        """A create that fails mid-materialization leaves nothing
        behind — no half-made machine, no leaked id."""
        blueprint = self._blueprint({
            "platform": "dos",
            "drives": {"hdd": {"size": "20M"}},
        })
        with mock.patch("reliquary.machines.create_hdd_image",
                        side_effect=RuntimeError("disk full")):
            with self.assertRaises(RuntimeError):
                create(blueprint, context=self.home, blueprint_name="doomed")
        self.assertEqual(
            list_machines(context=self.home, blueprint="doomed"), [])
        self.assertFalse(
            os.path.exists(machine_dir_path("doomed-0", self.home)))

    def _write_blueprint(self, name):
        bp_dir = os.path.join(self.home, "blueprints")
        os.makedirs(bp_dir, exist_ok=True)
        with open(os.path.join(bp_dir, f"{name}.rlqb"), "w",
                  encoding="utf-8") as handle:
            json.dump({"platform": "dos",
                       "drives": {"hdd": {"size": "20M"}}}, handle)

    def test_get_machine_dir_returns_absolute_path(self):
        machine_id = self._create_ready()
        result = get_machine_dir(machine=machine_id, context=self.home)
        self.assertTrue(os.path.isabs(result))
        self.assertEqual(
            os.path.normpath(result),
            os.path.normpath(machine_dir_path(machine_id, self.home)))

    def test_recreate_reuses_the_same_id(self):
        self._write_blueprint("rc")
        with mock.patch("reliquary.machines.create_hdd_image"):
            machine_id = create_machine("rc", context=self.home)
            again = recreate_machine(machine=machine_id, context=self.home)
        self.assertEqual(again, machine_id)
        self.assertEqual(
            [m["id"] for m in list_machines(
                context=self.home, blueprint="rc")],
            [machine_id])

    def test_recreate_keeps_the_id_at_a_gap(self):
        """recreate reuses the exact id even when a lower one is free."""
        self._write_blueprint("g")
        with mock.patch("reliquary.machines.create_hdd_image"):
            create_machine("g", context=self.home)          # g-0
            create_machine("g", context=self.home)          # g-1
            two = create_machine("g", context=self.home)    # g-2
            destroy_machine("g-0", context=self.home)       # frees g-0
            again = recreate_machine(machine=two, context=self.home)
        self.assertEqual(again, "g-2")
        ids = {m["id"] for m in list_machines(
            context=self.home, blueprint="g")}
        self.assertEqual(ids, {"g-1", "g-2"})

    def _write_blueprint_obj(self, name, obj):
        bp_dir = os.path.join(self.home, "blueprints")
        os.makedirs(bp_dir, exist_ok=True)
        with open(os.path.join(bp_dir, f"{name}.rlqb"), "w",
                  encoding="utf-8") as handle:
            json.dump(obj, handle)

    def test_apply_absorbs_memory_and_boot(self):
        self._write_blueprint_obj("ap", {
            "platform": "dos", "memory": "16M",
            "drives": {"hdd0": {"size": "20M"}, "cdrom0": None},
            "boot": ["hdd0", "cdrom0"]})
        with mock.patch("reliquary.machines.create_hdd_image"):
            machine_id = create_machine("ap", context=self.home)
        digest0 = load_machine_state(machine_id, self.home)["blueprint-digest"]
        self._write_blueprint_obj("ap", {
            "platform": "dos", "memory": "32M",
            "drives": {"hdd0": {"size": "20M"}, "cdrom0": None},
            "boot": ["cdrom0", "hdd0"]})
        apply_blueprint(machine=machine_id, context=self.home)
        state = load_machine_state(machine_id, self.home)
        self.assertEqual(state["memory"], 32)
        self.assertEqual(state["boot"], ["cdrom0", "hdd0"])
        self.assertNotEqual(state["blueprint-digest"], digest0)

    def test_apply_fails_closed_on_size_change(self):
        self._write_blueprint_obj("sz", {
            "platform": "dos", "drives": {"hdd0": {"size": "20M"}}})
        with mock.patch("reliquary.machines.create_hdd_image"):
            machine_id = create_machine("sz", context=self.home)
        self._write_blueprint_obj("sz", {
            "platform": "dos", "drives": {"hdd0": {"size": "50M"}}})
        with self.assertRaises(RuntimeError) as caught:
            apply_blueprint(machine=machine_id, context=self.home)
        self.assertIn("recreate", str(caught.exception))

    def test_apply_reconciles_diverged_media(self):
        self._write_blueprint_obj("dv", {
            "platform": "dos",
            "drives": {"hdd0": {"size": "20M"}, "cdrom0": None},
            "boot": ["hdd0", "cdrom0"]})
        with mock.patch("reliquary.machines.create_hdd_image"):
            machine_id = create_machine("dv", context=self.home)
        with mock.patch("reliquary.machines.fetch_media",
                        return_value=self.iso_path):
            insert_media(machine_id, "cdrom0", "freedos-1.4-livecd",
                         context=self.home)
        self.assertIsNotNone(load_machine_state(
            machine_id, self.home)["drives"]["cdrom0"]["media"])
        apply_blueprint(machine=machine_id, context=self.home)
        self.assertIsNone(load_machine_state(
            machine_id, self.home)["drives"]["cdrom0"]["media"])

    def test_apply_adds_and_removes_drives(self):
        self._write_blueprint_obj("ar", {
            "platform": "dos",
            "drives": {"hdd0": {"size": "20M"}, "hdd1": {"size": "30M"}}})
        with mock.patch("reliquary.machines.create_hdd_image"):
            machine_id = create_machine("ar", context=self.home)
        drives_root = os.path.join(
            machine_dir_path(machine_id, self.home), "drives")
        # hdd1's image exists on disk, so its removal deletes it.
        open(os.path.join(drives_root, "hdd1.qcow2"), "w").close()
        self._write_blueprint_obj("ar", {
            "platform": "dos",
            "drives": {"hdd0": {"size": "20M"}, "cdrom0": None}})
        apply_blueprint(machine=machine_id, context=self.home)
        state = load_machine_state(machine_id, self.home)
        self.assertNotIn("hdd1", state["drives"])
        self.assertIn("cdrom0", state["drives"])
        self.assertFalse(
            os.path.exists(os.path.join(drives_root, "hdd1.qcow2")))

    def test_apply_requires_stopped_machine(self):
        machine_id = self._create_ready()
        self._force_phase(machine_id, "running")
        with self.assertRaises(RuntimeError) as caught:
            apply_blueprint(machine=machine_id, context=self.home)
        self.assertIn("must be stopped", str(caught.exception))

    def test_create_machine_loads_blueprints_dir(self):
        """create_machine reads blueprints/<name>.json."""
        blueprints = os.path.join(self.home, "blueprints")
        os.makedirs(blueprints)
        with open(os.path.join(blueprints, "plain.json"), "w",
                  encoding="utf-8") as handle:
            json.dump({
                "platform": "dos",
                "drives": {"hdd": {"size": "20M"}},
            }, handle)
        with mock.patch("reliquary.machines.create_hdd_image"):
            machine_id = create_machine("plain", context=self.home)
        state = load_machine_state(machine_id, self.home)
        self.assertEqual(state["blueprint"], "plain")


class MediaInsertionTests(unittest.TestCase):
    """Persistent insert/eject on declared removable slots."""

    def setUp(self):
        self.workdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.workdir.cleanup)
        self.home = self.workdir.name
        library = os.path.join(self.home, "media")
        os.makedirs(library)
        with open(os.path.join(library, "freedos.json"), "w",
                  encoding="utf-8") as handle:
            json.dump({
                "name": "freedos-1.4-livecd",
                "file": "FD14LIVE.iso",
                "sha256": SHA256,
            }, handle)
        self.iso_path = os.path.join(
            self.home, "cache", "media", "freedos-1.4-livecd.iso")

    def _blueprint(self, value):
        return parse_blueprint(value, context=self.home)

    def _create_installer_shaped(self):
        """A machine with an empty cdrom0 booting hdd-then-cdrom."""
        blueprint = self._blueprint({
            "platform": "dos",
            "drives": {"hdd0": {"size": "20M"}, "cdrom0": None},
            "boot": ["hdd0", "cdrom0"],
        })
        with mock.patch("reliquary.machines.create_hdd_image"):
            return create(blueprint, context=self.home,
                          blueprint_name="installer")

    def test_create_records_empty_removable_drive(self):
        """An empty cdrom0 lands in the state with no media or path."""
        machine_id = self._create_installer_shaped()
        state = load_machine_state(machine_id, self.home)
        cdrom = state["drives"]["cdrom0"]
        self.assertEqual(cdrom["medium"], "cdrom")
        self.assertIsNone(cdrom["media"])
        self.assertIsNone(cdrom["path"])

    def test_empty_cdrom_renders_a_medium_less_qemu_drive(self):
        """The empty slot is still guest-visible hardware."""
        machine_id = self._create_installer_shaped()
        args = machine_drive_args(machine_id, self.home)
        values = [args[i + 1] for i, a in enumerate(args)
                  if a == "-drive"]
        cdrom_arg = [v for v in values if "media=cdrom" in v]
        self.assertEqual(cdrom_arg, ["media=cdrom,if=ide,index=1"])

    def test_insert_persists_media_in_machine_state(self):
        """insert fetches the item and records it on the slot."""
        machine_id = self._create_installer_shaped()
        with mock.patch("reliquary.machines.fetch_media",
                        return_value=self.iso_path) as fetch:
            insert_media(machine_id, "cdrom0", "freedos-1.4-livecd",
                         context=self.home)
        fetch.assert_called_once_with("freedos-1.4-livecd",
                                      context=self.home)
        cdrom = load_machine_state(machine_id, self.home)["drives"][
            "cdrom0"]
        self.assertEqual(cdrom["media"], "freedos-1.4-livecd")
        self.assertEqual(cdrom["path"], self.iso_path)

    def test_eject_returns_the_slot_to_empty(self):
        """eject empties the slot but never removes the drive."""
        machine_id = self._create_installer_shaped()
        with mock.patch("reliquary.machines.fetch_media",
                        return_value=self.iso_path):
            insert_media(machine_id, "cdrom0", "freedos-1.4-livecd",
                         context=self.home)
        eject_media(machine_id, "cdrom0", context=self.home)
        state = load_machine_state(machine_id, self.home)
        cdrom = state["drives"]["cdrom0"]
        self.assertIn("cdrom0", state["drives"])
        self.assertIsNone(cdrom["media"])
        self.assertIsNone(cdrom["path"])

    def test_set_boot_order_persists_on_a_stopped_machine(self):
        """Scripts may reorder boot devices while the machine is stopped."""
        machine_id = self._create_installer_shaped()
        self.assertEqual(
            load_machine_state(machine_id, self.home)["boot"],
            ["hdd0", "cdrom0"])
        set_boot_order(machine_id, ["cdrom0", "hdd0"], context=self.home)
        self.assertEqual(
            load_machine_state(machine_id, self.home)["boot"],
            ["cdrom0", "hdd0"])

    def test_set_boot_order_rejects_a_running_machine(self):
        machine_id = self._create_installer_shaped()
        state = load_machine_state(machine_id, self.home)
        state["phase"] = "running"
        with open(os.path.join(machine_dir_path(machine_id, self.home),
                               "reliquary-machine.json"), "w",
                  encoding="utf-8") as handle:
            json.dump(state, handle)
        with self.assertRaises(RuntimeError) as caught:
            set_boot_order(machine_id, ["cdrom0"], context=self.home)
        self.assertIn("must be stopped", str(caught.exception))

    def test_set_boot_order_rejects_undeclared_drives(self):
        machine_id = self._create_installer_shaped()
        with self.assertRaises(ValueError) as caught:
            set_boot_order(machine_id, ["floppy0"], context=self.home)
        self.assertIn("undeclared drive floppy0", str(caught.exception))

    def test_hdd_then_cdrom_boot_renders_order_cd(self):
        """Blank-disk fallthrough: try the hard disk, then the CD."""
        machine_id = self._create_installer_shaped()
        with mock.patch("reliquary.machines.find_qemu",
                        return_value="qemu"), \
                mock.patch("reliquary.machines.launch_owned_qemu",
                           return_value=4444) as launch:
            start_machine(machine_id, context=self.home)
        args = launch.call_args.args[0]
        self.assertIn("-boot", args)
        self.assertIn("order=cd", args)

    def test_inserted_media_survives_the_next_start(self):
        """A start after insert mounts the inserted medium."""
        machine_id = self._create_installer_shaped()
        with mock.patch("reliquary.machines.fetch_media",
                        return_value=self.iso_path):
            insert_media(machine_id, "cdrom0", "freedos-1.4-livecd",
                         context=self.home)
            with mock.patch("reliquary.machines.find_qemu",
                            return_value="qemu"), \
                    mock.patch("reliquary.machines.launch_owned_qemu",
                               return_value=4444) as launch:
                start_machine(machine_id, context=self.home)
        args = launch.call_args.args[0]
        cdrom_arg = [a for a in args if "media=cdrom" in a]
        self.assertEqual(len(cdrom_arg), 1)
        self.assertIn(self.iso_path, cdrom_arg[0])

    def test_insert_rejects_undeclared_slot(self):
        """insert never creates a drive the blueprint did not declare."""
        machine_id = self._create_installer_shaped()
        with self.assertRaises(ValueError) as caught:
            insert_media(machine_id, "floppy0", "freedos-1.4-livecd",
                         context=self.home)
        self.assertIn("declares no drive floppy0", str(caught.exception))

    def test_insert_rejects_non_removable_slot(self):
        """A hard-disk slot never takes insert/eject."""
        machine_id = self._create_installer_shaped()
        with self.assertRaises(ValueError) as caught:
            insert_media(machine_id, "hdd0", "freedos-1.4-livecd",
                         context=self.home)
        self.assertIn("not a removable drive slot", str(caught.exception))

    def test_insert_requires_a_stopped_machine(self):
        """Changing media on a running machine is not supported yet."""
        machine_id = self._create_installer_shaped()
        state = load_machine_state(machine_id, self.home)
        state["phase"] = "running"
        with open(os.path.join(machine_dir_path(machine_id, self.home),
                               "reliquary-machine.json"), "w",
                  encoding="utf-8") as handle:
            json.dump(state, handle)
        with self.assertRaises(RuntimeError) as caught:
            insert_media(machine_id, "cdrom0", "freedos-1.4-livecd",
                         context=self.home)
        self.assertIn("must be stopped", str(caught.exception))

    def test_mark_stopped_reconciles_a_powered_off_guest(self):
        """mark_stopped returns phase to ready and drops vm.json."""
        machine_id = self._create_installer_shaped()
        root = machine_dir_path(machine_id, self.home)
        state = load_machine_state(machine_id, self.home)
        state["phase"] = "running"
        with open(os.path.join(root, "reliquary-machine.json"), "w",
                  encoding="utf-8") as handle:
            json.dump(state, handle)
        with open(os.path.join(root, "vm.json"), "w",
                  encoding="utf-8") as handle:
            json.dump({"port": 4444, "name": "reliquary-x"}, handle)

        mark_stopped(machine_id, context=self.home)

        self.assertEqual(
            load_machine_state(machine_id, self.home)["phase"], "ready")
        self.assertFalse(os.path.exists(os.path.join(root, "vm.json")))

    def test_mark_stopped_leaves_a_ready_machine_alone(self):
        """A machine that is not running is untouched."""
        machine_id = self._create_installer_shaped()
        mark_stopped(machine_id, context=self.home)
        self.assertEqual(
            load_machine_state(machine_id, self.home)["phase"], "ready")


if __name__ == "__main__":
    unittest.main()
