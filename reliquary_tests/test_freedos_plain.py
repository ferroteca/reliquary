# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Tests for the freedos-plain recipe."""

import hashlib
import io
import os
import tempfile
import unittest
from unittest import mock

from reliquary import home
from reliquary.recipes import freedos_plain

PAYLOAD = b"live cd payload"


class FreeDOSPlainMediaPinTests(unittest.TestCase):
    """The recipe pins the official FreeDOS 1.4 LiveCD media."""

    def test_media_source_is_pinned(self):
        """URL and SHA-256 match the published FreeDOS 1.4 release."""
        self.assertEqual(
            freedos_plain.MEDIA_URL,
            "https://download.freedos.org/1.4/FD14-LiveCD.zip")
        self.assertEqual(
            freedos_plain.MEDIA_SHA256,
            "2020ff6bb681967fd6eff8f51ad2e5cd5ab4421165948cef"
            "4246e4f7fcaf6339")

    def test_target_disk_is_20_mib(self):
        self.assertEqual(freedos_plain.HDD_SIZE_MB, 20)


class FreeDOSPlainInstallTests(unittest.TestCase):
    """install() acquires media and prepares the target disk."""

    def setUp(self):
        self.workdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.workdir.cleanup)
        saved = home._home
        self.addCleanup(setattr, home, "_home", saved)
        home.set_home(self.workdir.name)
        self.expected_hdd = os.path.join(
            self.workdir.name, "machines", "freedos-plain",
            "drives", "hdd.qcow2")

    def _install(self, create_hdd_image):
        digest = hashlib.sha256(PAYLOAD).hexdigest()
        with mock.patch("reliquary.media.urlopen",
                        return_value=io.BytesIO(PAYLOAD)), \
                mock.patch.object(freedos_plain, "create_hdd_image",
                                  create_hdd_image), \
                mock.patch.object(freedos_plain, "MEDIA_SHA256",
                                  digest):
            return freedos_plain.install()

    def test_install_fetches_media_and_creates_disk(self):
        """Media lands in the home cache and relict creates the disk."""
        create_hdd_image = mock.Mock(return_value=self.expected_hdd)
        artifacts = self._install(create_hdd_image)
        expected_media = os.path.join(
            self.workdir.name, "install-media", "freedos",
            "FD14-LiveCD.zip")
        self.assertEqual(artifacts["media"], expected_media)
        self.assertEqual(artifacts["hdd_image"], self.expected_hdd)
        with open(expected_media, "rb") as handle:
            self.assertEqual(handle.read(), PAYLOAD)
        create_hdd_image.assert_called_once_with(
            self.expected_hdd, freedos_plain.HDD_SIZE_MB)

    def test_existing_disk_is_left_untouched(self):
        """A target disk that already exists is not recreated."""
        os.makedirs(os.path.dirname(self.expected_hdd))
        with open(self.expected_hdd, "wb") as handle:
            handle.write(b"guest data")
        create_hdd_image = mock.Mock()
        artifacts = self._install(create_hdd_image)
        create_hdd_image.assert_not_called()
        self.assertEqual(artifacts["hdd_image"], self.expected_hdd)
        with open(self.expected_hdd, "rb") as handle:
            self.assertEqual(handle.read(), b"guest data")


if __name__ == "__main__":
    unittest.main()
