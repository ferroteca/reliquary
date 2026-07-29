# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for the at-rest FAT reader (at_rest.py).

The images come from ``fat_image``, written from the format's own
layout rather than from this reader, so the two agree only where both
are right. What the *verbs* do with a volume is
``test_machines.py``'s; this module is the reader alone.
"""

import os
import struct
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


def opened(path, *, writable=False):
    """One image over a local device: how a raw image is opened now.

    The device is the seam — a served format arrives as an adapter's
    own device instead — so every caller composes the two rather than
    handing :class:`at_rest.Image` a path it would have to open.
    """
    return at_rest.Image(at_rest.LocalDevice(path, writable=writable),
                         writable=writable)


class _ImageCase(unittest.TestCase):
    def setUp(self):
        self.workdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.workdir.cleanup)
        self._serial = 0

    def _image(self, payload):
        # A fresh name per image: the device holds an exclusive lock
        # until it is closed, and a case that built two images under
        # one name would be contending with itself.
        self._serial += 1
        path = os.path.join(self.workdir.name, f"disk{self._serial}.img")
        with open(path, "wb") as handle:
            handle.write(payload)
        image = opened(path)
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
        larger = opened(self._write(
            fat_image.volume(TREE, bits=16, sectors=60000, per_cluster=1)))
        self.addCleanup(larger.close)
        self.assertEqual(larger.volumes[0].bits, 16)

    def _write(self, payload):
        path = os.path.join(self.workdir.name, "second.img")
        with open(path, "wb") as handle:
            handle.write(payload)
        return path

    def test_an_image_that_is_neither_says_so(self):
        """Something is written where a table would be, and it is not
        one — which is different from nothing being written at all."""
        payload = bytearray(4096)
        payload[0:8] = b"NOTADISK"
        with self.assertRaises(at_rest.UnreadableImage) as caught:
            self._image(bytes(payload))
        self.assertIn("cannot tell what is in this image",
                      str(caught.exception))

    def test_a_blank_disk_holds_no_volumes_rather_than_refusing(self):
        """A disk reliquary just materialized, before a guest touches
        it. DOS gives an unpartitioned disk no letter, so zero is the
        answer that lets a letter map be right about the drives behind
        it — refusing would make the whole machine unaddressable."""
        image = self._image(bytes(4096))
        self.assertEqual(image.volumes, [])
        self.assertFalse(image.partitioned)
        self.assertEqual(image.geometry().volumes, 0)

    def test_a_truncated_image_says_so_rather_than_answering(self):
        with self.assertRaises(at_rest.UnreadableImage):
            self._image(b"")


class PartitionTypeTests(_ImageCase):
    """What the table declares is what the reader acts on.

    The type byte is the highest-variability, highest-blast-radius
    input this module takes: one byte decides which filesystem a
    partition holds, and the reader *acts* on that meaning. So the
    mapping is pinned value by value, and the unmapped bytes are
    pinned too.
    """

    def _one(self, kind):
        return fat_image.partitioned(
            [fat_image.volume({"A.TXT": b"a"}, bits=16, sectors=20000,
                              per_cluster=4)], kinds=[kind])

    def test_every_dos_fat_type_is_read(self):
        for kind in (0x01, 0x04, 0x06, 0x0E):
            with self.subTest(kind=f"0x{kind:02X}"):
                image = self._image(self._one(kind))
                self.assertEqual(len(image.volumes), 1)
                self.assertEqual(image.partitions[0].kind, kind)

    def test_fat32_is_recognized_and_refused_by_name(self):
        """The recognition claim stops at FAT16 (D83): a FAT32
        partition is named for what it is and refused, never read —
        and never skipped, which would renumber the volumes after
        it."""
        for kind in (0x0B, 0x0C):
            with self.subTest(kind=f"0x{kind:02X}"):
                with self.assertRaises(at_rest.UnreadableImage) as caught:
                    self._image(self._one(kind))
                self.assertIn("FAT32", str(caught.exception))

    def test_a_foreign_type_is_refused_and_names_what_it_is(self):
        for kind, expected in ((0x07, "NTFS or exFAT"),
                               (0x83, "Linux"),
                               (0x82, "Linux swap"),
                               (0xEE, "GPT")):
            with self.subTest(kind=f"0x{kind:02X}"):
                with self.assertRaises(at_rest.UnreadableImage) as caught:
                    self._image(self._one(kind))
                self.assertIn(expected, str(caught.exception))

    def test_an_unmapped_type_is_refused_by_its_number(self):
        with self.assertRaises(at_rest.UnreadableImage) as caught:
            self._image(self._one(0x3C))
        self.assertIn("0x3C", str(caught.exception))

    def test_a_linux_extended_container_is_not_a_dos_one(self):
        """0x85 is Linux's, and this is the DOS workflow's reader. It
        used to be walked as though DOS had written it."""
        with self.assertRaises(at_rest.UnreadableImage) as caught:
            self._image(self._one(0x85))
        self.assertIn("Linux", str(caught.exception))

    def test_a_foreign_partition_is_refused_and_not_skipped(self):
        """Skipping would renumber every volume after it, so the
        answer would be confident and wrong about which drive is
        which — which is the failure this refusal exists to prevent."""
        payload = fat_image.partitioned(
            [fat_image.volume({"ONE.TXT": b"1"}, bits=16, sectors=20000,
                              per_cluster=4),
             fat_image.volume({"TWO.TXT": b"2"}, bits=16, sectors=20000,
                              per_cluster=4)],
            kinds=[0x83, 0x06])
        with self.assertRaises(at_rest.UnreadableImage):
            self._image(payload)

    def test_an_empty_slot_is_not_a_partition_and_not_an_error(self):
        image = self._image(self._one(0x06))
        self.assertEqual(len(image.partitions), 1)


class ExtendedPartitionTests(_ImageCase):
    """Logical drives behind a DOS extended container."""

    def _disk(self, count=2, container=0x05):
        def volume(name):
            return fat_image.volume({name: name.encode()}, bits=16,
                                    sectors=20000, per_cluster=4)
        return fat_image.extended(
            [volume("PRIMARY.TXT")],
            [volume(f"LOG{index}.TXT") for index in range(count)],
            container=container)

    def test_logical_drives_follow_the_primaries(self):
        image = self._image(self._disk())
        self.assertEqual(len(image.volumes), 3)
        self.assertEqual(
            [entry[0] for entry in image.volumes[0].entries([])],
            ["PRIMARY.TXT"])
        self.assertEqual(
            [entry[0] for entry in image.volumes[1].entries([])],
            ["LOG0.TXT"])
        self.assertEqual(
            [entry[0] for entry in image.volumes[2].entries([])],
            ["LOG1.TXT"])

    def test_the_container_itself_is_not_a_volume(self):
        image = self._image(self._disk())
        containers = [entry for entry in image.partitions
                      if entry.kind in (0x05, 0x0F)]
        self.assertEqual(len(containers), 1)
        self.assertEqual(len(image.volumes), len(image.partitions) - 1)

    def test_the_lba_container_is_walked_the_same_way(self):
        image = self._image(self._disk(container=0x0F))
        self.assertEqual(len(image.volumes), 3)

    def test_a_logical_drive_knows_it_is_one(self):
        image = self._image(self._disk())
        self.assertEqual([entry.logical for entry in image.partitions],
                         [False, False, True, True])


class GeometryTests(_ImageCase):
    """The drive's shape, read on the host (P10's second source)."""

    def test_a_partitionless_floppy_reports_one_volume_and_no_table(self):
        geometry = self._image(fat_image.volume(TREE)).geometry()
        self.assertFalse(geometry.partitioned)
        self.assertEqual(geometry.partitions, ())
        self.assertEqual(geometry.volumes, 1)

    def test_a_partitioned_disk_reports_each_partition(self):
        image = self._image(fat_image.partitioned([
            fat_image.volume({"ONE.TXT": b"1"}, bits=16, sectors=20000,
                             per_cluster=4),
            fat_image.volume({"TWO.TXT": b"2"}, bits=16, sectors=20000,
                             per_cluster=4)]))
        geometry = image.geometry()
        self.assertTrue(geometry.partitioned)
        self.assertEqual(geometry.volumes, 2)
        self.assertEqual([entry.number for entry in geometry.partitions],
                         [1, 2])
        self.assertEqual([entry.description
                          for entry in geometry.partitions],
                         ["FAT16B", "FAT16B"])

    def test_a_partitions_offset_and_length_are_the_tables_own(self):
        volume = fat_image.volume({"A.TXT": b"a"}, bits=16, sectors=20000,
                                  per_cluster=4)
        image = self._image(fat_image.partitioned([volume]))
        entry = image.geometry().partitions[0]
        self.assertEqual(entry.offset, 512)
        self.assertEqual(entry.length, len(volume))

    def test_the_bpbs_geometry_is_reported_when_it_states_one(self):
        geometry = self._image(fat_image.volume(TREE)).geometry()
        self.assertEqual(geometry.heads, 2)
        self.assertEqual(geometry.sectors_per_track, 18)
        self.assertEqual(geometry.bytes_per_sector, 512)

    def test_cylinders_follow_from_the_size_and_the_rest(self):
        geometry = self._image(fat_image.volume(TREE)).geometry()
        self.assertEqual(
            geometry.cylinders,
            geometry.size // (geometry.heads
                              * geometry.sectors_per_track * 512))


class LockingTests(_ImageCase):
    """A drive image is locked for the length of an access."""

    def _file(self, name="locked.img"):
        path = os.path.join(self.workdir.name, name)
        with open(path, "wb") as handle:
            handle.write(fat_image.volume(TREE))
        return path

    def test_a_second_opener_is_refused_while_the_first_holds_it(self):
        path = self._file()
        first = opened(path, writable=True)
        self.addCleanup(first.close)
        with self.assertRaises(at_rest.UnreadableImage) as caught:
            opened(path)
        self.assertIn("locked by another process", str(caught.exception))

    def test_closing_releases_it_for_the_next_caller(self):
        path = self._file()
        opened(path, writable=True).close()
        second = opened(path, writable=True)
        self.addCleanup(second.close)
        self.assertEqual(len(second.volumes), 1)

    def test_the_lock_does_not_block_reading_the_image_itself(self):
        """The regression that made the lock work at all.

        A served image is opened by the *backend*, which reads its
        header — so a lock taken over the image's own bytes would be
        one QEMU trips on, and the first version of this took byte
        zero. The claim has to sit where nothing reads.
        """
        path = self._file()
        held = opened(path, writable=True)
        self.addCleanup(held.close)
        with open(path, "rb") as handle:
            self.assertEqual(handle.read(2), b"\xeb\x3c")

    def test_a_lock_only_alone_still_excludes_a_second_caller(self):
        """What a served image holds: the claim without the device."""
        path = self._file()
        lock = at_rest.ImageLock(path)
        self.addCleanup(lock.close)
        with self.assertRaises(at_rest.UnreadableImage):
            at_rest.ImageLock(path)

    def test_a_refused_lock_leaves_no_handle_behind(self):
        """The failed opener must not keep the file open, or the
        image could never be opened again in this process."""
        path = self._file()
        first = opened(path, writable=True)
        with self.assertRaises(at_rest.UnreadableImage):
            opened(path)
        first.close()
        third = opened(path, writable=True)
        self.addCleanup(third.close)
        self.assertEqual(len(third.volumes), 1)


class ReadingTests(_ImageCase):
    """Listing and retrieval, across both FAT widths."""

    def _volume(self, **geometry):
        return self._image(fat_image.volume(TREE, **geometry)).volumes[0]

    def _widths(self):
        # The claimed widths (D83): FAT12 and FAT16. FAT32 is the
        # refusal case below, not a width here.
        return (("fat12", {}),
                ("fat16", {"bits": 16, "sectors": 60000, "per_cluster": 4}))

    def test_a_fat32_scale_volume_is_refused_by_name(self):
        """The width is the cluster count's answer, so a volume at
        FAT32 scale is refused whatever any type byte said (D83) —
        the claim stops at FAT16."""
        payload = fat_image.volume(TREE, bits=32, sectors=70000,
                                   per_cluster=1)
        with self.assertRaises(at_rest.UnreadableImage) as caught:
            self._image(payload)
        self.assertIn("FAT32", str(caught.exception))

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


class VolumeLabelTests(_ImageCase):
    """The label as DOS maintains it, unanswered when there is none.

    The root directory's label entry is what ``LABEL`` writes and
    ``DIR`` shows, so it outranks the BPB's copy; "NO NAME" is the
    format's own spelling of unlabeled and never reads as a name.
    """

    def _labeled_boot(self, payload, label):
        patched = bytearray(payload)
        patched[38] = 0x29
        patched[43:54] = label.ljust(11).encode("ascii")
        return bytes(patched)

    def test_an_unlabeled_volume_answers_none(self):
        volume = self._image(fat_image.volume(TREE)).volumes[0]
        self.assertIsNone(volume.volume_label())

    def test_the_bpb_label_answers_behind_its_signature(self):
        payload = self._labeled_boot(fat_image.volume(TREE), "RELICS")
        volume = self._image(payload).volumes[0]
        self.assertEqual(volume.volume_label(), "RELICS")

    def test_no_name_reads_as_no_label(self):
        payload = self._labeled_boot(fat_image.volume(TREE), "NO NAME")
        volume = self._image(payload).volumes[0]
        self.assertIsNone(volume.volume_label())

    def test_the_root_entry_outranks_the_bpb(self):
        payload = bytearray(self._labeled_boot(fat_image.volume({}),
                                               "OLDNAME"))
        reserved = struct.unpack_from("<H", payload, 14)[0]
        fat_sectors = struct.unpack_from("<H", payload, 22)[0]
        root_at = (reserved + payload[16] * fat_sectors) * 512
        payload[root_at:root_at + 11] = b"NEWNAME    "
        payload[root_at + 11] = 0x08
        volume = self._image(bytes(payload)).volumes[0]
        self.assertEqual(volume.volume_label(), "NEWNAME")


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
        with opened(path, writable=True) as image:
            work(image.volumes[0])
        with open(path, "rb") as handle:
            payload = handle.read()
        self.assertEqual(fat_image.consistency(payload), [])
        return path

    def _widths(self):
        # The claimed widths (D83): FAT12 and FAT16. The FAT32
        # refusal is ReadingTests' case; nothing writable remains
        # past it.
        return (("fat12", {}),
                ("fat16", {"bits": 16, "sectors": 60000, "per_cluster": 4}))

    def _reads_back(self, path, segments, expected):
        with opened(path) as image:
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
                with opened(path) as image:
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
        with opened(path) as image:
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
        with opened(path, writable=True) as image:
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
        with opened(path) as image:
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
