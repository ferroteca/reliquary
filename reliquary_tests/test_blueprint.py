# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Tests for the milestone-1 machine blueprint subset."""

import json
import os
import tempfile
import unittest

import reliquary
from reliquary.blueprint import (Blueprint, BlueprintDrive,
                                 delete_blueprint, load_blueprint,
                                 new_blueprint, parse_blueprint)


SHA256 = "1" * 64


class BlueprintTestCase(unittest.TestCase):
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

    def parse(self, value):
        return parse_blueprint(value, context=self.home)


class ParseBlueprintTests(BlueprintTestCase):
    """Parsing and normalization of the spike-4 subset."""

    def test_package_exposes_blueprint_surface(self):
        self.assertIs(reliquary.Blueprint, Blueprint)
        self.assertIs(reliquary.BlueprintDrive, BlueprintDrive)
        self.assertIs(reliquary.parse_blueprint, parse_blueprint)
        self.assertIs(reliquary.load_blueprint, load_blueprint)
        self.assertIs(reliquary.delete_blueprint, delete_blueprint)
        self.assertIs(reliquary.new_blueprint, new_blueprint)

    def test_parses_freedos_install_shape(self):
        """The complete built-in-library shape parses and resolves."""
        result = self.parse({
            "platform": "dos",
            "memory": "32m",
            "drives": {
                "hdd": {"size": "20m"},
                "cdrom": None,
            },
            "boot": ["hdd", "cdrom"],
            "name": "FreeDOS 1.4 — Plain DOS system",
            "description": "Plain FreeDOS 1.4 system installed "
                           "from the LiveCD",
            "scripts": {
                "install": "freedos-1.4-plain-install",
                "verify": "freedos-1.4-plain-verify",
            },
        })

        self.assertIsInstance(result, Blueprint)
        self.assertEqual(result.platform, "dos")
        self.assertEqual(result.memory, 32)
        self.assertEqual(tuple(result.drives), ("hdd0", "cdrom0"))
        self.assertIsInstance(result.drives["hdd0"], BlueprintDrive)
        self.assertEqual(result.drives["hdd0"].size, "20M")
        self.assertIsNone(result.drives["hdd0"].media)
        self.assertIsNone(result.drives["cdrom0"].media)
        self.assertEqual(result.boot, ("hdd0", "cdrom0"))
        self.assertEqual(result.scripts["install"],
                         "freedos-1.4-plain-install")

    def test_omitted_optional_fields_are_empty(self):
        """Only platform is required by the subset."""
        result = self.parse({"platform": "win9x"})
        self.assertEqual(result.platform, "win9x")
        self.assertIsNone(result.memory)
        self.assertEqual(dict(result.drives), {})
        self.assertEqual(result.boot, ())
        self.assertIsNone(result.name)
        self.assertIsNone(result.description)
        self.assertEqual(dict(result.scripts), {})

    def test_default_boot_prefers_floppy_then_hdd_then_cdrom(self):
        """An omitted boot field follows the documented M1 default."""
        result = self.parse({
            "platform": "dos",
            "drives": {
                "cdrom1": "freedos-1.4-livecd",
                "hdd": {"size": "20M"},
                "floppy": {"size": "1440K"},
            },
        })
        self.assertEqual(result.boot, ("floppy0",))

    def test_memory_integer_is_mib(self):
        result = self.parse({"platform": "winnt", "memory": 256})
        self.assertEqual(result.memory, 256)

    def test_memory_size_must_resolve_to_whole_mib(self):
        with self.assertRaises(ValueError) as caught:
            self.parse({"platform": "dos", "memory": "512K"})
        self.assertIn("whole MiB", str(caught.exception))

    def test_floppy_size_accepts_binary_units(self):
        result = self.parse({
            "platform": "dos",
            "drives": {"floppy1": {"size": "720k"}},
        })
        self.assertEqual(result.drives["floppy1"].size, "720K")

    def test_media_object_form_resolves(self):
        result = self.parse({
            "platform": "dos",
            "drives": {
                "cdrom0": {"media": "freedos-1.4-livecd"},
            },
        })
        self.assertEqual(result.drives["cdrom0"].media.item.file,
                         "FD14LIVE.iso")

    def test_missing_media_name_fails_resolution(self):
        with self.assertRaises(FileNotFoundError) as caught:
            self.parse({
                "platform": "dos",
                "drives": {"cdrom": "missing"},
            })
        self.assertIn("missing", str(caught.exception))

    def test_missing_platform_is_rejected(self):
        with self.assertRaises(KeyError) as caught:
            self.parse({})
        self.assertIn("platform", str(caught.exception))

    def test_unknown_platform_is_rejected(self):
        with self.assertRaises(ValueError) as caught:
            self.parse({"platform": "linux"})
        self.assertIn("platform", str(caught.exception))

    def test_openbsd_platform_is_recognized(self):
        result = self.parse({"platform": "openbsd", "memory": "512M"})
        self.assertEqual(result.platform, "openbsd")
        self.assertEqual(result.memory, 512)

    def test_unknown_top_level_field_is_rejected(self):
        with self.assertRaises(ValueError) as caught:
            self.parse({"platform": "dos", "frobnicate": True})
        self.assertIn("frobnicate", str(caught.exception))

    def test_state_only_field_is_rejected_by_name(self):
        for field_name in ("blueprint-digest", "blueprint-source",
                           "backend-id", "id"):
            with self.subTest(field=field_name):
                with self.assertRaises(ValueError) as caught:
                    self.parse({"platform": "dos", field_name: "x"})
                message = str(caught.exception)
                self.assertIn(field_name, message)
                self.assertIn("state-only", message)

    def test_unknown_drive_field_is_rejected(self):
        with self.assertRaises(ValueError) as caught:
            self.parse({
                "platform": "dos",
                "drives": {"hdd": {"size": "20M", "frobnicate": 1}},
            })
        self.assertIn("drives.hdd0.frobnicate", str(caught.exception))

    def test_drive_requires_exactly_one_source(self):
        for declaration in ({}, {
                "size": "20M", "media": "freedos-1.4-livecd"}):
            with self.subTest(declaration=declaration):
                with self.assertRaises(ValueError) as caught:
                    self.parse({
                        "platform": "dos",
                        "drives": {"hdd": declaration},
                    })
                self.assertIn("exactly one", str(caught.exception))

    def test_cdrom_cannot_be_blank_sized_media(self):
        with self.assertRaises(ValueError) as caught:
            self.parse({
                "platform": "dos",
                "drives": {"cdrom": {"size": "650M"}},
            })
        self.assertIn("cdrom0", str(caught.exception))

    def test_null_removable_drive_is_an_empty_slot(self):
        """An installer-driven blueprint declares the slot empty."""
        result = self.parse({
            "platform": "dos",
            "drives": {"hdd0": {"size": "20M"}, "cdrom0": None},
            "boot": ["hdd0", "cdrom0"],
        })
        cdrom = result.drives["cdrom0"]
        self.assertEqual(cdrom.medium, "cdrom")
        self.assertIsNone(cdrom.size)
        self.assertIsNone(cdrom.media)
        self.assertEqual(result.boot, ("hdd0", "cdrom0"))

    def test_null_floppy_is_an_empty_slot(self):
        result = self.parse({
            "platform": "dos",
            "drives": {"floppy1": None},
        })
        self.assertEqual(result.drives["floppy1"].medium, "floppy")

    def test_null_hdd_is_rejected(self):
        """Only removable drives may be declared empty."""
        with self.assertRaises(ValueError) as caught:
            self.parse({
                "platform": "dos",
                "drives": {"hdd0": None},
            })
        self.assertIn("removable", str(caught.exception))

    def test_drive_alias_clash_is_rejected(self):
        with self.assertRaises(ValueError) as caught:
            self.parse({
                "platform": "dos",
                "drives": {
                    "hdd": {"size": "20M"},
                    "hdd0": {"size": "30M"},
                },
            })
        self.assertIn("clash", str(caught.exception))

    def test_drive_slot_range_is_checked(self):
        with self.assertRaises(ValueError) as caught:
            self.parse({
                "platform": "dos",
                "drives": {"floppy2": {"size": "1440K"}},
            })
        self.assertIn("floppy", str(caught.exception))

    def test_boot_must_reference_declared_drive(self):
        with self.assertRaises(ValueError) as caught:
            self.parse({
                "platform": "dos",
                "drives": {"hdd": {"size": "20M"}},
                "boot": ["cdrom"],
            })
        self.assertIn("cdrom0", str(caught.exception))

    def test_invalid_metadata_and_scripts_are_rejected(self):
        invalid = (
            {"name": ""},
            {"description": 3},
            {"scripts": []},
            {"scripts": {"": "install"}},
            {"scripts": {"install": "../install"}},
            {"scripts": {"install": "install.rlqs"}},
        )
        for fields in invalid:
            with self.subTest(fields=fields):
                with self.assertRaises(ValueError):
                    self.parse({"platform": "dos", **fields})

    def test_null_optional_collections_are_rejected(self):
        for field in ("drives", "boot", "scripts"):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    self.parse({"platform": "dos", field: None})

    def test_result_is_deeply_immutable(self):
        result = self.parse({
            "platform": "dos",
            "drives": {"hdd": {"size": "20M"}},
            "scripts": {"install": "install"},
        })
        with self.assertRaises(TypeError):
            result.drives["hdd1"] = result.drives["hdd0"]
        with self.assertRaises(TypeError):
            result.scripts["verify"] = "verify"


class FullFieldReferenceTests(BlueprintTestCase):
    """The fields beyond the milestone-1 subset (T1)."""

    def test_backend_enum(self):
        self.assertEqual(
            self.parse({"platform": "dos", "backend": "qemu"}).backend,
            "qemu")
        with self.assertRaises(ValueError) as caught:
            self.parse({"platform": "dos", "backend": "kvm"})
        self.assertIn("backend", str(caught.exception))

    def test_backend_omitted_is_none(self):
        self.assertIsNone(self.parse({"platform": "dos"}).backend)

    def test_cpus_positive_integer(self):
        self.assertEqual(
            self.parse({"platform": "dos", "cpus": 4}).cpus, 4)
        for bad in (0, -1, True, "2", 1.5):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    self.parse({"platform": "dos", "cpus": bad})

    def test_controller_on_hdd_and_cdrom(self):
        result = self.parse({
            "platform": "dos",
            "drives": {"hdd0": {"size": "20M", "controller": "scsi"}},
        })
        self.assertEqual(result.drives["hdd0"].controller, "scsi")

    def test_controller_rejected_on_floppy(self):
        with self.assertRaises(ValueError) as caught:
            self.parse({
                "platform": "dos",
                "drives": {"floppy0": {"size": "1440K",
                                       "controller": "ide"}},
            })
        self.assertIn("controller", str(caught.exception))

    def test_controller_unknown_value_rejected(self):
        with self.assertRaises(ValueError):
            self.parse({
                "platform": "dos",
                "drives": {"hdd0": {"size": "20M", "controller": "usb"}},
            })

    def test_base_string_shorthand_defaults_to_difference(self):
        result = self.parse({
            "platform": "dos",
            "drives": {"hdd0": {"base": "freedos-1.4-livecd"}},
        })
        drive = result.drives["hdd0"]
        self.assertEqual(drive.base.item.name, "freedos-1.4-livecd")
        self.assertEqual(drive.base_type, "difference")
        self.assertIsNone(drive.size)

    def test_base_object_with_type(self):
        result = self.parse({
            "platform": "dos",
            "drives": {"hdd0": {"base": {"media": "freedos-1.4-livecd",
                                         "type": "duplicate"}}},
        })
        self.assertEqual(result.drives["hdd0"].base_type, "duplicate")

    def test_base_bad_type_rejected(self):
        with self.assertRaises(ValueError) as caught:
            self.parse({
                "platform": "dos",
                "drives": {"hdd0": {"base": {"media": "freedos-1.4-livecd",
                                             "type": "snapshot"}}},
            })
        self.assertIn("type", str(caught.exception))

    def test_base_rejected_on_cdrom(self):
        with self.assertRaises(ValueError) as caught:
            self.parse({
                "platform": "dos",
                "drives": {"cdrom0": {"base": "freedos-1.4-livecd"}},
            })
        self.assertIn("cdrom0", str(caught.exception))

    def test_hostdir_string(self):
        result = self.parse({
            "platform": "dos",
            "drives": {"hdd1": {"hostdir": "work/"}},
        })
        self.assertEqual(result.drives["hdd1"].hostdir, "work/")

    def test_hostdir_rejected_on_cdrom(self):
        with self.assertRaises(ValueError) as caught:
            self.parse({
                "platform": "dos",
                "drives": {"cdrom0": {"hostdir": "work/"}},
            })
        self.assertIn("cdrom0", str(caught.exception))

    def test_disabled_drive_excluded_from_default_boot(self):
        result = self.parse({
            "platform": "dos",
            "drives": {
                "hdd0": {"size": "20M", "enabled": False},
                "cdrom0": "freedos-1.4-livecd",
            },
        })
        self.assertFalse(result.drives["hdd0"].enabled)
        # Default boot skips the disabled hdd0 and falls to the cdrom.
        self.assertEqual(result.boot, ("cdrom0",))

    def test_boot_naming_disabled_drive_is_rejected(self):
        with self.assertRaises(ValueError) as caught:
            self.parse({
                "platform": "dos",
                "drives": {"hdd0": {"size": "20M", "enabled": False}},
                "boot": ["hdd0"],
            })
        self.assertIn("disabled", str(caught.exception))

    def test_enabled_must_be_boolean(self):
        with self.assertRaises(ValueError):
            self.parse({
                "platform": "dos",
                "drives": {"hdd0": {"size": "20M", "enabled": "no"}},
            })

    def test_control_planes(self):
        result = self.parse({
            "platform": "dos",
            "control-planes": ["guest-agent", "agentless-display"],
        })
        self.assertEqual(result.control_planes,
                         ("guest-agent", "agentless-display"))

    def test_control_planes_duplicate_rejected(self):
        with self.assertRaises(ValueError) as caught:
            self.parse({
                "platform": "dos",
                "control-planes": ["vnc", "vnc"],
            })
        self.assertIn("duplicate", str(caught.exception))

    def test_control_planes_unknown_rejected(self):
        with self.assertRaises(ValueError):
            self.parse({
                "platform": "dos",
                "control-planes": ["telepathy"],
            })

    def test_backend_settings(self):
        result = self.parse({
            "platform": "dos",
            "backend-settings": {"qemu": {"machine": "pc"}},
        })
        self.assertEqual(result.backend_settings["qemu"]["machine"], "pc")

    def test_backend_settings_unknown_backend_rejected(self):
        with self.assertRaises(ValueError) as caught:
            self.parse({
                "platform": "dos",
                "backend-settings": {"parallels": {}},
            })
        self.assertIn("parallels", str(caught.exception))

    def test_parameters_direct_value_and_redirect(self):
        result = self.parse({
            "platform": "dos",
            "parameters": {
                "identity.full-name": "testuser",
                "os.install-key": {"property": "products.win98.key"},
            },
        })
        self.assertEqual(result.parameters["identity.full-name"],
                         "testuser")
        self.assertEqual(
            result.parameters["os.install-key"]["property"],
            "products.win98.key")

    def test_parameters_invalid_binding_rejected(self):
        for binding in ([], {"property": ""}, {"property": "x", "y": 1},
                        {"nope": "x"}, 3):
            with self.subTest(binding=binding):
                with self.assertRaises(ValueError):
                    self.parse({
                        "platform": "dos",
                        "parameters": {"k": binding},
                    })

    def test_parameters_not_carried_by_result_is_a_mapping(self):
        result = self.parse({"platform": "dos"})
        self.assertEqual(dict(result.parameters), {})


class LoadBlueprintTests(BlueprintTestCase):
    """Loading a blueprint JSON document from disk."""

    def test_loads_and_resolves_with_explicit_home(self):
        path = os.path.join(self.workdir.name, "freedos.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({
                "platform": "dos",
                "drives": {"cdrom": "freedos-1.4-livecd"},
            }, handle)
        result = load_blueprint(path, context=self.home)
        self.assertEqual(result.drives["cdrom0"].media.item.name,
                         "freedos-1.4-livecd")

    def test_missing_file_has_actionable_error(self):
        path = os.path.join(self.workdir.name, "missing.json")
        with self.assertRaises(FileNotFoundError) as caught:
            load_blueprint(path, context=self.home)
        self.assertIn(path, str(caught.exception))


class NewBlueprintTests(BlueprintTestCase):
    def test_new_blueprint_creates_rlqb_with_scaffolding(self):
        from reliquary.blueprint import new_blueprint
        new_blueprint("test-bp", context=self.home)
        path = os.path.join(self.home, "blueprints", "test-bp.rlqb")
        self.assertTrue(os.path.exists(path))
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("// Machine blueprint for test-bp", content)
            data = json.loads("\n".join(line for line in content.splitlines() if not line.strip().startswith("//")))
            self.assertNotIn("version", data)
            self.assertEqual(data["platform"], "dos")
        # The scaffold must parse under the full field reference.
        self.assertIsInstance(self.parse(data), Blueprint)

    def test_new_blueprint_already_exists_raises(self):
        from reliquary.blueprint import new_blueprint
        new_blueprint("test-bp", context=self.home)
        with self.assertRaises(FileExistsError):
            new_blueprint("test-bp", context=self.home)

    def test_new_blueprint_legacy_json_exists_raises(self):
        from reliquary.blueprint import new_blueprint
        path = os.path.join(self.home, "blueprints", "test-bp.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f: f.write("{}")
        with self.assertRaises(FileExistsError) as caught:
            new_blueprint("test-bp", context=self.home)
        self.assertIn("legacy blueprint already exists", str(caught.exception))


class DeleteBlueprintTests(BlueprintTestCase):
    def test_deletes_rlqb(self):
        path = new_blueprint("test-bp", context=self.home)
        removed = delete_blueprint("test-bp", context=self.home)
        self.assertEqual(removed, path)
        self.assertFalse(os.path.exists(path))

    def test_deletes_legacy_json(self):
        path = os.path.join(self.home, "blueprints", "legacy.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("{}\n")
        removed = delete_blueprint("legacy", context=self.home)
        self.assertEqual(removed, path)
        self.assertFalse(os.path.exists(path))

    def test_missing_raises(self):
        with self.assertRaises(FileNotFoundError) as caught:
            delete_blueprint("missing", context=self.home)
        self.assertIn("blueprint not found", str(caught.exception))

    def test_refuses_while_machines_exist(self):
        new_blueprint("plain", context=self.home)
        machine_dir = os.path.join(
            self.home, "cache", "machines", "plain-0")
        os.makedirs(machine_dir)
        with open(os.path.join(machine_dir, "reliquary-machine.json"),
                  "w", encoding="utf-8") as handle:
            json.dump({
                "id": "plain-0",
                "blueprint": "plain",
                "phase": "ready",
            }, handle)
        with self.assertRaises(RuntimeError) as caught:
            delete_blueprint("plain", context=self.home)
        message = str(caught.exception)
        self.assertIn("still has 1 machine(s)", message)
        self.assertIn("plain-0", message)
        self.assertTrue(os.path.exists(
            os.path.join(self.home, "blueprints", "plain.rlqb")))

    def test_does_not_delete_builtin(self):
        # No home file; builtin-only name must not be removed from
        # the package.
        with self.assertRaises(FileNotFoundError):
            delete_blueprint("freedos-1.4-plain", context=self.home)


if __name__ == "__main__":
    unittest.main()
