# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Tests for the stubbed runner surface: the config-carrying machine
shape, the guest-environment choice validation, and the explicit
not-implemented state of every operation."""

import dataclasses
import unittest

import relict


class RunnerConstructionTests(unittest.TestCase):
    def test_default_machine_targets_win9x_with_default_config(self):
        machine = relict.Runner()

        self.assertEqual(machine.platform, "win9x")
        self.assertEqual(machine.config, relict.RunnerConfig())

    def test_machine_exposes_its_immutable_config(self):
        config = relict.RunnerConfig(timeout=45)
        machine = relict.Runner(config)

        self.assertIs(machine.config, config)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            machine.config.timeout = 90


class EnvironmentChoiceTests(unittest.TestCase):
    def test_ready_image_does_not_combine_with_install_media(self):
        with self.assertRaisesRegex(ValueError, "ready environment"):
            relict.RunnerConfig(boot_image="win98.img",
                                install_media="win98.iso")

    def test_ready_image_does_not_combine_with_product_key(self):
        with self.assertRaisesRegex(ValueError, "ready environment"):
            relict.RunnerConfig(boot_image="win98.img",
                                product_key="KEY-123")

    def test_media_url_requires_its_hash(self):
        with self.assertRaisesRegex(ValueError, "media_sha256"):
            relict.RunnerConfig(media_url="https://example.test/w98.iso")

    def test_valid_choices_construct(self):
        relict.RunnerConfig()
        relict.RunnerConfig(boot_image="win98.img")
        relict.RunnerConfig(install_media="win98.iso",
                            product_key="KEY-123")
        relict.RunnerConfig(media_url="https://example.test/w98.iso",
                            media_sha256="0" * 64)

    def test_install_validates_the_same_choice(self):
        with self.assertRaisesRegex(ValueError, "media_sha256"):
            relict.install(media_url="https://example.test/w98.iso")


class StagedDriveTests(unittest.TestCase):
    def test_staged_drive_defaults_to_e(self):
        self.assertEqual(relict.RunnerConfig().staged_drive, "E")

    def test_staged_drive_letter_is_normalized_uppercase(self):
        self.assertEqual(relict.RunnerConfig(staged_drive="f")
                         .staged_drive, "F")

    def test_reserved_and_invalid_letters_are_rejected(self):
        for letter in ("A", "B", "C", "EE", "1", ""):
            with self.assertRaisesRegex(ValueError, "staged_drive",
                                        msg=letter):
                relict.RunnerConfig(staged_drive=letter)

    def test_d_is_allowed_for_machines_without_a_cdrom(self):
        self.assertEqual(relict.RunnerConfig(staged_drive="D")
                         .staged_drive, "D")

    def test_run_guest_program_validates_the_same_letter(self):
        with self.assertRaisesRegex(ValueError, "staged_drive"):
            relict.run_guest_program("SUITE.EXE", staged_drive="C")

    def test_run_guest_program_accepts_d(self):
        with self.assertRaises(NotImplementedError):
            relict.run_guest_program("SUITE.EXE", staged_drive="D")


class StubSurfaceTests(unittest.TestCase):
    """Every operation exists with its agreed signature and states
    plainly that it is not implemented yet."""

    def test_operations_are_explicit_stubs(self):
        machine = relict.Runner()
        stubs = [
            lambda: relict.set_home("somewhere"),
            relict.home,
            relict.dist_dir,
            relict.boot_image,
            relict.staging_dir,
            relict.drive_staging,
            lambda: relict.install(install_media="win98.iso"),
            lambda: relict.run_guest_program("SUITE.EXE"),
            lambda: machine.provision("dist"),
            lambda: machine.run("SUITE.EXE", "-v", "run-home"),
        ]
        for stub in stubs:
            with self.assertRaises(NotImplementedError):
                stub()


class CliTests(unittest.TestCase):
    def test_help_describes_the_planned_commands(self):
        with self.assertRaises(SystemExit) as caught:
            relict.main(["--help"])

        self.assertEqual(caught.exception.code, 0)

    def test_run_command_reaches_the_stub(self):
        with self.assertRaises(NotImplementedError):
            relict.main(["run", "SUITE.EXE"])


if __name__ == "__main__":
    unittest.main()
