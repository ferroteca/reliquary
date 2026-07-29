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


class OnDiskLayoutTests(_ImageCase):
    """Facts about the bytes, asserted without either module's help.

    The builder existing to check the reader only works while the two
    disagree about nothing *except* what is right. They once shared a
    byte-swapped boot signature — the reader looked for it and the
    builder wrote it, so every test passed and every real disk was
    rejected as unreadable. These assertions state the layout
    literally, so an agreed-upon mistake has nowhere to hide.
    """

    def test_the_boot_signature_is_0x55_then_0xaa_on_disk(self):
        payload = fat_image.volume({"A.TXT": b"a"})
        self.assertEqual(payload[510:512], b"\x55\xaa")

    def test_a_partition_table_ends_the_same_way(self):
        payload = fat_image.partitioned(
            [fat_image.volume({"A.TXT": b"a"}, bits=16, sectors=20000,
                              per_cluster=4)])
        self.assertEqual(payload[510:512], b"\x55\xaa")

    def test_a_hand_built_mbr_is_accepted(self):
        """An MBR assembled here from the layout, owing nothing to the
        builder: one FAT16 partition at LBA 63, which is what a real
        formatter produces and what this reader once turned away."""
        volume = fat_image.volume({"REAL.TXT": b"real"}, bits=16,
                                  sectors=20000, per_cluster=4)
        sector = bytearray(512)
        sector[446] = 0x80                       # bootable
        sector[446 + 4] = 0x06                   # FAT16
        sector[446 + 8:446 + 12] = (63).to_bytes(4, "little")
        sector[446 + 12:446 + 16] = (
            len(volume) // 512).to_bytes(4, "little")
        sector[510:512] = b"\x55\xaa"
        image = self._image(bytes(sector) + bytes(62 * 512) + volume)
        self.assertEqual(len(image.volumes), 1)
        self.assertEqual([name for name, _dir, _size
                          in image.volumes[0].entries([])], ["REAL.TXT"])


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
        # FAT32 needs 65525 clusters before it *is* FAT32, so its
        # image is the big one: the width is the cluster count's
        # answer and cannot be asked for directly.
        return (("fat12", {}),
                ("fat16", {"bits": 16, "sectors": 60000, "per_cluster": 4}),
                ("fat32", {"bits": 32, "sectors": 70000, "per_cluster": 1}))

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


class WritingTests(_ImageCase):
    """Writing back into a volume, checked structurally after each one.

    ``fat_image.consistency`` is the assertion that matters here: it
    reads the result from the format rather than through the writer,
    so a chain the writer built wrong, two files claiming one cluster,
    or FAT copies drifting apart are caught by something that does not
    share the writer's opinion.
    """

    def _source(self, name, payload):
        path = os.path.join(self.workdir.name, name)
        with open(path, "wb") as handle:
            handle.write(payload)
        return path

    def _written(self, geometry, work):
        """Run ``work`` against a fresh volume, returning its bytes."""
        path = os.path.join(self.workdir.name, "target.img")
        with open(path, "wb") as handle:
            handle.write(fat_image.volume(TREE, **geometry))
        with at_rest.Image(path, writable=True) as image:
            work(image.volumes[0])
        with open(path, "rb") as handle:
            payload = handle.read()
        self.assertEqual(fat_image.consistency(payload), [])
        return path

    def _widths(self):
        # FAT32 needs 65525 clusters before it *is* FAT32, so its
        # image is the big one: the width is the cluster count's
        # answer and cannot be asked for directly.
        return (("fat12", {}),
                ("fat16", {"bits": 16, "sectors": 60000, "per_cluster": 4}),
                ("fat32", {"bits": 32, "sectors": 70000, "per_cluster": 1}))

    def _reads_back(self, path, segments, expected):
        with at_rest.Image(path) as image:
            target = os.path.join(self.workdir.name, "back.bin")
            image.volumes[0].copy_to(segments, target)
        with open(target, "rb") as handle:
            self.assertEqual(handle.read(), expected)

    def test_a_new_file_appears_and_reads_back(self):
        source = self._source("NEW.TXT", b"written from the host\r\n")
        for label, geometry in self._widths():
            with self.subTest(width=label):
                path = self._written(
                    geometry, lambda v: v.write_file(["NEW.TXT"], source))
                self._reads_back(path, ["NEW.TXT"],
                                 b"written from the host\r\n")

    def test_a_file_larger_than_one_cluster_chains(self):
        payload = bytes(range(256)) * 300
        source = self._source("BIG.DAT", payload)
        for label, geometry in self._widths():
            with self.subTest(width=label):
                path = self._written(
                    geometry, lambda v: v.write_file(["BIG.DAT"], source))
                self._reads_back(path, ["BIG.DAT"], payload)

    def test_an_overwrite_replaces_the_content_and_the_size(self):
        """Shrinking matters: the old chain has to go back to the pool
        or the volume leaks clusters an overwrite should have reused."""
        big = self._source("BIG.DAT", b"x" * 40000)
        small = self._source("SMALL.TXT", b"tiny")
        for label, geometry in self._widths():
            with self.subTest(width=label):
                def work(volume):
                    volume.write_file(["OUT", "RESULT.LOG"], big)
                    volume.write_file(["OUT", "RESULT.LOG"], small)
                path = self._written(geometry, work)
                self._reads_back(path, ["OUT", "RESULT.LOG"], b"tiny")

    def test_a_directory_is_created_with_its_parents(self):
        source = self._source("R.TXT", b"deep")
        for label, geometry in self._widths():
            with self.subTest(width=label):
                def work(volume):
                    volume.make_directory(["NEW", "INNER"])
                    volume.write_file(["NEW", "INNER", "R.TXT"], source)
                path = self._written(geometry, work)
                self._reads_back(path, ["NEW", "INNER", "R.TXT"], b"deep")
                with at_rest.Image(path) as image:
                    self.assertEqual(
                        image.volumes[0].kind(["NEW", "INNER"]), "directory")

    def test_a_directory_grows_past_its_first_cluster(self):
        """A subdirectory is a chain like any other, so filling one has
        to extend it rather than run off the end."""
        source = self._source("ONE.TXT", b"1")
        def work(volume):
            volume.make_directory(["MANY"])
            for index in range(48):
                volume.write_file(["MANY", f"F{index:04}.TXT"], source)
        path = self._written({}, work)
        with at_rest.Image(path) as image:
            self.assertEqual(len(image.volumes[0].entries(["MANY"])), 48)

    def test_a_full_root_directory_refuses_rather_than_overrunning(self):
        source = self._source("ONE.TXT", b"1")
        def work(volume):
            for index in range(400):
                volume.write_file([f"F{index:04}.TXT"], source)
        with self.assertRaises(at_rest.UnreadableImage) as caught:
            self._written({"root_entries": 32}, work)
        self.assertIn("root directory is full", str(caught.exception))

    def test_a_volume_without_room_refuses_before_writing_anything(self):
        source = self._source("HUGE.DAT", b"x" * (2 * 1024 * 1024))
        path = os.path.join(self.workdir.name, "small.img")
        with open(path, "wb") as handle:
            handle.write(fat_image.volume({}, sectors=800))
        with at_rest.Image(path, writable=True) as image:
            with self.assertRaises(at_rest.UnreadableImage) as caught:
                image.volumes[0].write_file(["HUGE.DAT"], source)
        self.assertIn("room", str(caught.exception))
        with open(path, "rb") as handle:
            self.assertEqual(fat_image.consistency(handle.read()), [])

    def test_a_name_that_is_not_8_3_is_refused(self):
        source = self._source("x", b"x")
        volume = self._image(fat_image.volume(TREE)).volumes[0]
        for name in ("RESULTS.TAR.GZ", "TOOLONGNAME.TXT", "A.TEXT",
                     "HAS SPACE.TXT", "BAD*.TXT", ""):
            with self.subTest(name=name):
                with self.assertRaises(at_rest.UnreadableImage):
                    volume.write_file([name], source)

    def test_a_lowercase_name_is_stored_as_dos_holds_it(self):
        source = self._source("job.bat", b"GO")
        path = self._written({}, lambda v: v.write_file(["job.bat"], source))
        with at_rest.Image(path) as image:
            self.assertIn(
                "JOB.BAT",
                [name for name, _dir, _size in image.volumes[0].entries([])])

    def test_writing_needs_a_writable_image(self):
        volume = self._image(fat_image.volume(TREE)).volumes[0]
        source = self._source("N.TXT", b"n")
        with self.assertRaises(at_rest.UnreadableImage) as caught:
            volume.write_file(["N.TXT"], source)
        self.assertIn("reading only", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
