# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Tests for the at-rest FAT reader (at_rest.py).

The images come from ``fat_image``, written from the format's own
layout rather than from this reader, so the two agree only where both
are right. What the *verbs* do with a volume is
``test_machines.py``'s; this module is the reader alone.
"""

import os
import tempfile
import unittest

from reliquary import at_rest
from reliquary_tests import fat_image

TREE = {
    "AUTOEXEC.BAT": b"@ECHO OFF\r\n",
    "BIG.DAT": bytes(range(256)) * 41,
    "OUT": {"RESULT.LOG": b"pass\r\n",
            "LOGS": {"DEEP.TXT": b"nested"}},
}


class _ImageCase(unittest.TestCase):
    def setUp(self):
        self.workdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.workdir.cleanup)

    def _image(self, payload):
        path = os.path.join(self.workdir.name, "disk.img")
        with open(path, "wb") as handle:
            handle.write(payload)
        image = at_rest.Image(path)
        self.addCleanup(image.close)
        return image


class VolumeDiscoveryTests(_ImageCase):
    """Finding the volumes, with and without a partition table."""

    def test_a_partitionless_image_is_one_volume(self):
        image = self._image(fat_image.volume(TREE))
        self.assertEqual(len(image.volumes), 1)
        self.assertEqual(image.volumes[0].bits, 12)

    def test_a_partitioned_disk_yields_its_partitions(self):
        image = self._image(fat_image.partitioned([
            fat_image.volume({"ONE.TXT": b"1"}, bits=16, sectors=20000,
                             per_cluster=4),
            fat_image.volume({"TWO.TXT": b"2"}, bits=16, sectors=20000,
                             per_cluster=4)]))
        self.assertEqual(len(image.volumes), 2)
        self.assertEqual([entry[0] for entry in image.volumes[0].entries([])],
                         ["ONE.TXT"])
        self.assertEqual([entry[0] for entry in image.volumes[1].entries([])],
                         ["TWO.TXT"])

    def test_the_fat_width_follows_the_cluster_count(self):
        """Not the size, and not what formatted it -- the count is the
        specification's own test."""
        small = self._image(fat_image.volume(TREE))
        self.assertEqual(small.volumes[0].bits, 12)
        larger = at_rest.Image(self._write(
            fat_image.volume(TREE, bits=16, sectors=60000, per_cluster=1)))
        self.addCleanup(larger.close)
        self.assertEqual(larger.volumes[0].bits, 16)

    def _write(self, payload):
        path = os.path.join(self.workdir.name, "second.img")
        with open(path, "wb") as handle:
            handle.write(payload)
        return path

    def test_an_image_that_is_neither_says_so(self):
        with self.assertRaises(at_rest.UnreadableImage) as caught:
            self._image(bytes(4096))
        self.assertIn("cannot tell what is in this image",
                      str(caught.exception))

    def test_a_truncated_image_says_so_rather_than_answering(self):
        with self.assertRaises(at_rest.UnreadableImage):
            self._image(b"")


class ReadingTests(_ImageCase):
    """Listing and retrieval, across both FAT widths."""

    def _volume(self, **geometry):
        return self._image(fat_image.volume(TREE, **geometry)).volumes[0]

    def _widths(self):
        return (("fat12", {}),
                ("fat16", {"bits": 16, "sectors": 60000, "per_cluster": 4}))

    def test_a_root_listing_is_sorted_with_directory_sizes_null(self):
        for label, geometry in self._widths():
            with self.subTest(width=label):
                volume = self._volume(**geometry)
                self.assertEqual(
                    volume.entries([]),
                    [("AUTOEXEC.BAT", False, 11),
                     ("BIG.DAT", False, 10496),
                     ("OUT", True, None)])

    def test_a_nested_directory_is_addressed_by_its_segments(self):
        for label, geometry in self._widths():
            with self.subTest(width=label):
                volume = self._volume(**geometry)
                self.assertEqual(
                    [name for name, _dir, _size
                     in volume.entries(["OUT", "LOGS"])],
                    ["DEEP.TXT"])

    def test_kind_answers_for_a_file_a_directory_and_neither(self):
        volume = self._volume()
        self.assertEqual(volume.kind([]), "directory")
        self.assertEqual(volume.kind(["OUT"]), "directory")
        self.assertEqual(volume.kind(["OUT", "RESULT.LOG"]), "file")
        self.assertIsNone(volume.kind(["NOPE.TXT"]))
        self.assertIsNone(volume.kind(["OUT", "NOPE.TXT"]))

    def test_a_file_cannot_be_descended_into(self):
        volume = self._volume()
        self.assertIsNone(volume.kind(["AUTOEXEC.BAT", "INNER.TXT"]))

    def test_a_name_matches_case_insensitively_as_dos_does(self):
        volume = self._volume()
        self.assertEqual(volume.kind(["autoexec.bat"]), "file")
        self.assertEqual(volume.kind(["out", "result.log"]), "file")

    def test_a_file_reads_back_byte_for_byte(self):
        for label, geometry in self._widths():
            with self.subTest(width=label):
                volume = self._volume(**geometry)
                target = os.path.join(self.workdir.name, "out.bin")
                volume.copy_to(["AUTOEXEC.BAT"], target)
                with open(target, "rb") as handle:
                    self.assertEqual(handle.read(), TREE["AUTOEXEC.BAT"])

    def test_a_file_spanning_many_clusters_reads_whole(self):
        """The cluster chain walked, and the tail truncated to the
        recorded size rather than padded out to the last cluster."""
        for label, geometry in self._widths():
            with self.subTest(width=label):
                volume = self._volume(**geometry)
                target = os.path.join(self.workdir.name, "big.bin")
                volume.copy_to(["BIG.DAT"], target)
                with open(target, "rb") as handle:
                    self.assertEqual(handle.read(), TREE["BIG.DAT"])

    def test_a_nested_file_reads_back(self):
        volume = self._volume()
        target = os.path.join(self.workdir.name, "deep.bin")
        volume.copy_to(["OUT", "LOGS", "DEEP.TXT"], target)
        with open(target, "rb") as handle:
            self.assertEqual(handle.read(), b"nested")

    def test_reading_what_is_not_there_says_so(self):
        volume = self._volume()
        with self.assertRaises(at_rest.UnreadableImage):
            volume.copy_to(["NOPE.TXT"], os.path.join(self.workdir.name, "x"))
        with self.assertRaises(at_rest.UnreadableImage):
            volume.copy_to(["OUT"], os.path.join(self.workdir.name, "x"))
        with self.assertRaises(at_rest.UnreadableImage):
            volume.entries(["NOPE"])


if __name__ == "__main__":
    unittest.main()
