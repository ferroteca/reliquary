# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Tests for the freedos-plain recipe."""

import hashlib
import io
import os
import tempfile
import unittest
import zipfile
from unittest import mock

from reliquary import home
from reliquary.recipes import freedos_plain


def _livecd_zip():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as bundle:
        bundle.writestr("FD14BOOT.img", b"boot floppy")
        bundle.writestr("FD14LIVE.iso", b"live cd iso")
    return buffer.getvalue()


PAYLOAD = _livecd_zip()


class FreeDOSPlainMediaPinTests(unittest.TestCase):
    """The recipe pins the official FreeDOS 1.4 LiveCD media."""

    def test_media_source_is_pinned(self):
        """URL and ISO SHA-256 match the FreeDOS 1.4 release."""
        self.assertEqual(
            freedos_plain.MEDIA_URL,
            "https://download.freedos.org/1.4/FD14-LiveCD.zip")
        self.assertEqual(
            freedos_plain.ISO_SHA256,
            "c48a9dcf4b8e22f44e268a9879745f0bd88c061195ac584e"
            "6ef2deb0477f81fb")

    def test_target_disk_is_20_mib(self):
        self.assertEqual(freedos_plain.HDD_SIZE_MB, 20)


class FreeDOSPlainInstallTests(unittest.TestCase):
    """install() acquires media, prepares the disk, and boots the CD."""

    def setUp(self):
        self.workdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.workdir.cleanup)
        saved = home._home
        self.addCleanup(setattr, home, "_home", saved)
        home.set_home(self.workdir.name)
        self.machine_home = os.path.join(
            self.workdir.name, "machines", "freedos-plain")
        self.expected_hdd = os.path.join(
            self.machine_home, "drives", "hdd.qcow2")
        self.expected_iso = os.path.join(
            self.workdir.name, "install-media", "freedos",
            "FD14LIVE.iso")

    def _install(self, create_hdd_image, start, stop,
                 vm_exited=mock.Mock(side_effect=OSError),
                 machine=None, **kwargs):
        digest = hashlib.sha256(b"live cd iso").hexdigest()
        if machine is None:
            machine = mock.Mock()
        self.machine = machine
        with mock.patch("reliquary.media.urlopen",
                        return_value=io.BytesIO(PAYLOAD)), \
                mock.patch.object(freedos_plain, "create_hdd_image",
                                  create_hdd_image), \
                mock.patch.object(freedos_plain, "start", start), \
                mock.patch.object(freedos_plain, "stop", stop), \
                mock.patch.object(freedos_plain, "Machine",
                                  return_value=machine) as Machine, \
                mock.patch("reliquary.recipes.freedos_plain.socket."
                           "create_connection", vm_exited), \
                mock.patch.object(freedos_plain, "ISO_SHA256",
                                  digest):
            self.Machine = Machine
            return freedos_plain.install(**kwargs)

    def test_install_prepares_artifacts_and_boots_from_cd(self):
        """Media is cached, the ISO extracted, and the CD booted."""
        create_hdd_image = mock.Mock(return_value=self.expected_hdd)
        start = mock.Mock(return_value=4242)
        artifacts = self._install(create_hdd_image, start, mock.Mock())
        transient_zip = os.path.join(
            self.workdir.name, "install-media", "freedos",
            "FD14-LiveCD.zip")
        self.assertFalse(os.path.exists(transient_zip))
        self.assertEqual(artifacts["iso"], self.expected_iso)
        self.assertEqual(artifacts["hdd_image"], self.expected_hdd)
        with open(self.expected_iso, "rb") as handle:
            self.assertEqual(handle.read(), b"live cd iso")
        create_hdd_image.assert_called_once_with(
            self.expected_hdd, freedos_plain.HDD_SIZE_MB)
        start.assert_called_once()
        config = start.call_args.args[0]
        self.assertEqual(start.call_args.kwargs, {
            "display": False, "home": self.machine_home})
        self.assertEqual(config.drives["cdrom_0"]["source"],
                         self.expected_iso)
        self.assertEqual(config.qemu_args, ("-boot", "d"))
        self.assertEqual(config.platform, "dos")
        self.Machine.assert_called_once_with(4242, self.machine_home)
        self.machine.wait_screen.assert_called_once_with(
            r"Welcome to FreeDOS 1\.4 \(LiveCD\)")

    def test_install_display_mode_is_forwarded(self):
        """display=True reaches relict's start()."""
        create_hdd_image = mock.Mock(return_value=self.expected_hdd)
        start = mock.Mock(return_value=4242)
        self._install(create_hdd_image, start, mock.Mock(),
                      display=True)
        self.assertTrue(start.call_args.kwargs["display"])

    def test_machine_is_stopped_after_it_exits(self):
        """The started machine is always shut down when install ends."""
        stop = mock.Mock()
        self._install(mock.Mock(return_value=self.expected_hdd),
                      mock.Mock(return_value=4242), stop)
        stop.assert_called_once_with(4242, self.machine_home)

    def test_interrupt_still_shuts_the_machine_down(self):
        """Ctrl-C while the machine runs triggers the stop failsafe."""
        stop = mock.Mock()
        with self.assertRaises(KeyboardInterrupt):
            self._install(
                mock.Mock(return_value=self.expected_hdd),
                mock.Mock(return_value=4242), stop,
                vm_exited=mock.Mock(side_effect=KeyboardInterrupt))
        stop.assert_called_once_with(4242, self.machine_home)

    def test_vanished_machine_is_tolerated_at_shutdown(self):
        """A machine that already exited does not fail install()."""
        stop = mock.Mock(side_effect=RuntimeError(
            "the recorded relict VM is no longer reachable"))
        artifacts = self._install(
            mock.Mock(return_value=self.expected_hdd),
            mock.Mock(return_value=4242), stop)
        self.assertEqual(artifacts["hdd_image"], self.expected_hdd)

    def test_existing_disk_is_left_untouched(self):
        """A target disk that already exists is not recreated."""
        os.makedirs(os.path.dirname(self.expected_hdd))
        with open(self.expected_hdd, "wb") as handle:
            handle.write(b"guest data")
        create_hdd_image = mock.Mock()
        artifacts = self._install(create_hdd_image,
                                  mock.Mock(return_value=4242),
                                  mock.Mock())
        create_hdd_image.assert_not_called()
        self.assertEqual(artifacts["hdd_image"], self.expected_hdd)
        with open(self.expected_hdd, "rb") as handle:
            self.assertEqual(handle.read(), b"guest data")


if __name__ == "__main__":
    unittest.main()
