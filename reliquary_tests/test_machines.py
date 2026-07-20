# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Tests for machine materialization and cached-state management."""

import json
import os
import tempfile
import unittest
from unittest import mock

from reliquary.blueprint import parse_blueprint
from reliquary.machines import (create, load_machine_state,
                                machine_dir_path, machine_drive_args)


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
        return parse_blueprint(value, home=self.home)

    def test_create_populates_the_machine_cache_directory(self):
        """The machine lands under cache/machines/<id>/ with a state
        file and a drives/ subdirectory."""
        blueprint = self._blueprint({
            "platform": "dos",
            "drives": {"hdd": {"size": "20M"}},
        })

        with mock.patch(
                "reliquary.machines.create_hdd_image") as create_hdd:
            machine_id = create(blueprint, home=self.home,
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
            machine_id = create(blueprint, home=self.home,
                                blueprint_name="freedos-plain")

        state = load_machine_state(machine_id, self.home)
        self.assertEqual(state["id"], machine_id)
        self.assertEqual(state["blueprint"], "freedos-plain")
        self.assertIn("created", state)
        self.assertEqual(state["phase"], "ready")
        self.assertEqual(state["platform"], "dos")
        self.assertIsNone(state["memory"])
        self.assertEqual(state["name"], "Test Machine")
        self.assertEqual(state["scripts"], {"install": "install-script"})
        self.assertEqual(state["boot"], ["hdd0"])

    def test_create_writes_state_file_with_optional_fields_absent(self):
        """Omitted optional fields are None/empty in the state."""
        blueprint = self._blueprint({"platform": "dos"})

        with mock.patch("reliquary.machines.create_hdd_image"):
            machine_id = create(blueprint, home=self.home,
                                blueprint_name="minimal")

        state = load_machine_state(machine_id, self.home)
        self.assertIsNone(state["memory"])
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
            machine_id = create(blueprint, home=self.home,
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
            machine_id = create(blueprint, home=self.home,
                                blueprint_name="with-media")

        fetch.assert_called_once_with("freedos-1.4-livecd",
                                      home=self.home)
        state = load_machine_state(machine_id, self.home)
        cdrom = state["drives"]["cdrom0"]
        self.assertEqual(cdrom["medium"], "cdrom")
        self.assertEqual(cdrom["media"], "freedos-1.4-livecd")
        self.assertEqual(
            os.path.normpath(cdrom["path"]),
            os.path.normpath(self.iso_path),
        )

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
            machine_id = create(blueprint, home=self.home,
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
            machine_id = create(blueprint, home=self.home,
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
            load_machine_state("nonexistent", home=self.home)
        self.assertIn("nonexistent", str(caught.exception))

    def test_machine_id_is_unique(self):
        """Two consecutive creates produce distinct ids."""
        blueprint = self._blueprint({"platform": "dos"})

        with mock.patch("reliquary.machines.create_hdd_image"):
            first = create(blueprint, home=self.home)
            second = create(blueprint, home=self.home)

        self.assertNotEqual(first, second)

    def test_create_exposes_public_surface(self):
        """The module's public functions are importable and callable."""
        import reliquary.machines as machines_module
        self.assertTrue(hasattr(machines_module, "create"))
        self.assertTrue(hasattr(machines_module, "load_machine_state"))
        self.assertTrue(hasattr(machines_module, "machine_dir_path"))
        self.assertTrue(hasattr(machines_module, "machine_drive_args"))


if __name__ == "__main__":
    unittest.main()
