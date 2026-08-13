# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for the at-rest translation layer (at_rest.py).

Remanence reads and writes the disks; what is tested here is the
policy reliquary keeps on top of it (P27): the DOS recognition claim
and its refusal wording, the whole-disk-or-none rule, guest-address
validation, the report vocabulary, and the commit semantics the file
verbs stand on. The images come from ``fat_image``, written from the
format's own layout rather than from either implementation, so the
builder, Remanence and this layer agree only where all are right.
What the *verbs* do with a volume end to end is
``test_machines.py``'s; this module is the translation alone.
"""

import os
import struct

import pytest

from reliquary import at_rest
from tests import fat_image

TREE = {
    "AUTOEXEC.BAT": b"@ECHO OFF\r\n",
    "BIG.DAT": bytes(range(256)) * 41,
    "OUT": {"RESULT.LOG": b"pass\r\n",
            "LOGS": {"DEEP.TXT": b"nested"}},
}

#: The claimed widths (D83): FAT12 and FAT16. FAT32 is a refusal, not
#: a width — one node per width, so a check that stopped covering one
#: of them is a missing node rather than a loop nobody counts.
WIDTHS = pytest.mark.parametrize(
    "geometry",
    [{}, {"bits": 16, "sectors": 60000, "per_cluster": 4}],
    ids=["fat12", "fat16"])


def opened(path, *, writable=False):
    """One image, opened where it lies -- the only way in now."""
    return at_rest.Image(path, writable=writable)


class _Images:
    """Images written under one directory, closed with the test."""

    def __init__(self, root):
        self.root = root
        self._serial = 0
        self._opened = []

    def write(self, payload):
        # A fresh name per image: an open image holds Remanence's
        # claim until it is closed, and a case that built two images
        # under one name would be contending with itself.
        self._serial += 1
        path = os.path.join(self.root, f"disk{self._serial}.img")
        with open(path, "wb") as handle:
            handle.write(payload)
        return path

    def open(self, payload, *, writable=False):
        return self.track(opened(self.write(payload), writable=writable))

    def track(self, image):
        self._opened.append(image)
        return image

    def source(self, name, payload):
        path = os.path.join(self.root, name)
        with open(path, "wb") as handle:
            handle.write(payload)
        return path

    def path(self, name):
        return os.path.join(self.root, name)

    def close(self):
        for image in self._opened:
            image.close()


@pytest.fixture
def images(tmp_path):
    helper = _Images(str(tmp_path))
    yield helper
    helper.close()


# Facts about the bytes, asserted without any implementation's help.
#
# The builder existing to check the reader only works while the two
# disagree about nothing *except* what is right. They once shared a
# byte-swapped boot signature — the reader looked for it and the
# builder wrote it, so every test passed and every real disk was
# rejected as unreadable. These assertions state the layout literally,
# so an agreed-upon mistake has nowhere to hide.

def test_the_boot_signature_is_0x55_then_0xaa_on_disk():
    payload = fat_image.volume({"A.TXT": b"a"})
    assert payload[510:512] == b"\x55\xaa"


def test_a_partition_table_ends_the_same_way():
    payload = fat_image.partitioned(
        [fat_image.volume({"A.TXT": b"a"}, bits=16, sectors=20000,
                          per_cluster=4)])
    assert payload[510:512] == b"\x55\xaa"


def test_a_hand_built_mbr_is_accepted(images):
    """An MBR assembled here from the layout, owing nothing to the
    builder: one FAT16 partition at LBA 63, which is what a real
    formatter produces."""
    volume = fat_image.volume({"REAL.TXT": b"real"}, bits=16,
                              sectors=20000, per_cluster=4)
    sector = bytearray(512)
    sector[446] = 0x80                       # bootable
    sector[446 + 4] = 0x06                   # FAT16
    sector[446 + 8:446 + 12] = (63).to_bytes(4, "little")
    sector[446 + 12:446 + 16] = (len(volume) // 512).to_bytes(4, "little")
    sector[510:512] = b"\x55\xaa"
    image = images.open(bytes(sector) + bytes(62 * 512) + volume)
    assert len(image.volumes) == 1
    assert [name for name, _dir, _size
            in image.volumes[0].entries([])] == ["REAL.TXT"]


# Finding the volumes, with and without a partition table.

def test_a_partitionless_image_is_one_volume(images):
    image = images.open(fat_image.volume(TREE))
    assert len(image.volumes) == 1
    assert image.volumes[0].filesystem == "FAT12"


def _two_partitions():
    return fat_image.partitioned([
        fat_image.volume({"ONE.TXT": b"1"}, bits=16, sectors=20000,
                         per_cluster=4),
        fat_image.volume({"TWO.TXT": b"2"}, bits=16, sectors=20000,
                         per_cluster=4)])


def test_a_partitioned_disk_yields_its_partitions(images):
    image = images.open(_two_partitions())
    assert len(image.volumes) == 2
    assert [entry[0] for entry in image.volumes[0].entries([])] == ["ONE.TXT"]
    assert [entry[0] for entry in image.volumes[1].entries([])] == ["TWO.TXT"]


def test_the_fat_width_follows_the_cluster_count(images):
    """Not the size, and not what formatted it -- the count is the
    specification's own test."""
    small = images.open(fat_image.volume(TREE))
    assert small.volumes[0].filesystem == "FAT12"
    larger = images.open(
        fat_image.volume(TREE, bits=16, sectors=60000, per_cluster=1))
    assert larger.volumes[0].filesystem == "FAT16"


def test_the_volume_id_is_the_inspection_reports_own(images):
    """One identity shared by the report and every file verb
    (P27): the id is Remanence's stable name for the volume, not a
    position that renumbers.

    Its spelling is Remanence's and opaque here, so what is
    asserted is that it identifies rather than counts -- distinct
    per volume, the same on a second open of the same disk, and
    not the position the volume happens to sit at.
    """
    path = images.write(fat_image.volume(TREE))
    with opened(path) as floppy:
        floppy_id = floppy.volumes[0].id
    with opened(path) as reopened:
        assert reopened.volumes[0].id == floppy_id
    disk = images.open(_two_partitions())
    identities = [volume.id for volume in disk.volumes]
    assert len(set(identities)) == 2
    assert floppy_id not in identities
    assert identities != [0, 1]


def test_an_image_that_is_neither_says_so(images):
    """Something is written where a table would be, and it is not
    one — which is different from nothing being written at all."""
    payload = bytearray(4096)
    payload[0:8] = b"NOTADISK"
    with pytest.raises(at_rest.UnreadableImage):
        images.open(bytes(payload))


def test_a_blank_disk_holds_no_volumes_rather_than_refusing(images):
    """A disk reliquary just materialized, before a guest touches
    it. DOS gives an unpartitioned disk no letter, so zero is the
    answer that lets a letter map be right about the drives behind
    it — refusing would make the whole machine unaddressable."""
    image = images.open(bytes(4096))
    assert image.volumes == []
    assert not image.geometry().partitioned
    assert image.geometry().volumes == 0


def test_a_truncated_image_says_so_rather_than_answering(images):
    with pytest.raises(at_rest.UnreadableImage):
        images.open(b"")


# What the table declares is what this layer acts on.
#
# The type byte is the highest-variability, highest-blast-radius input
# the claim judges: one byte decides which filesystem a partition
# holds. So the mapping is pinned value by value here — reliquary's
# own vocabulary, whatever Remanence reports — and the unmapped bytes
# are pinned too.

def _one(kind):
    return fat_image.partitioned(
        [fat_image.volume({"A.TXT": b"a"}, bits=16, sectors=20000,
                          per_cluster=4)], kinds=[kind])


@pytest.mark.parametrize("kind", [0x01, 0x04, 0x06, 0x0E],
                         ids=lambda kind: f"0x{kind:02X}")
def test_every_dos_fat_type_is_read(images, kind):
    image = images.open(_one(kind))
    assert len(image.volumes) == 1
    assert image.geometry().partitions[0].kind == kind


@pytest.mark.parametrize("kind", [0x0B, 0x0C],
                         ids=lambda kind: f"0x{kind:02X}")
def test_fat32_is_recognized_and_refused_by_name(images, kind):
    """The recognition claim stops at FAT16 (D83): a FAT32
    partition is named for what it is and refused, never read —
    and never skipped, which would renumber the volumes after it."""
    with pytest.raises(at_rest.UnreadableImage) as caught:
        images.open(_one(kind))
    assert "FAT32" in str(caught.value)


@pytest.mark.parametrize("kind,expected", [
    (0x07, "NTFS or exFAT"),
    (0x83, "Linux"),
    (0x82, "Linux swap"),
    (0xEE, "GPT"),
], ids=lambda value: f"0x{value:02X}" if isinstance(value, int) else value)
def test_a_foreign_type_is_refused_and_names_what_it_is(images, kind,
                                                        expected):
    with pytest.raises(at_rest.UnreadableImage) as caught:
        images.open(_one(kind))
    assert expected in str(caught.value)


def test_an_unmapped_type_is_refused_by_its_number(images):
    with pytest.raises(at_rest.UnreadableImage) as caught:
        images.open(_one(0x3C))
    assert "0x3C" in str(caught.value)


def test_a_linux_extended_container_is_not_a_dos_one(images):
    """0x85 is Linux's, and this is the DOS workflow's claim. It
    used to be walked as though DOS had written it."""
    with pytest.raises(at_rest.UnreadableImage) as caught:
        images.open(_one(0x85))
    assert "Linux" in str(caught.value)


def test_a_foreign_partition_is_refused_and_not_skipped(images):
    """Skipping would renumber every volume after it, so the
    answer would be confident and wrong about which drive is
    which — which is the failure this refusal exists to prevent.
    Remanence reads past the row it cannot own; the whole-disk
    rule here is reliquary's."""
    payload = fat_image.partitioned(
        [fat_image.volume({"ONE.TXT": b"1"}, bits=16, sectors=20000,
                          per_cluster=4),
         fat_image.volume({"TWO.TXT": b"2"}, bits=16, sectors=20000,
                          per_cluster=4)],
        kinds=[0x83, 0x06])
    with pytest.raises(at_rest.UnreadableImage):
        images.open(payload)


def test_a_declared_fat_that_is_not_one_refuses_the_disk(images):
    """A pinned type whose volume Remanence cannot read carries
    an issue in Remanence's report; under the whole-disk rule the
    issue refuses the disk, naming the partition."""
    payload = bytearray(_one(0x06))
    payload[512:1024] = b"\xde\xad" * 256
    with pytest.raises(at_rest.UnreadableImage) as caught:
        images.open(bytes(payload))
    assert "partition 1" in str(caught.value)


def test_an_empty_slot_is_not_a_partition_and_not_an_error(images):
    image = images.open(_one(0x06))
    assert len(image.geometry().partitions) == 1


# Logical drives behind a DOS extended container.

def _extended_disk(count=2, container=0x05):
    def volume(name):
        return fat_image.volume({name: name.encode()}, bits=16,
                                sectors=20000, per_cluster=4)
    return fat_image.extended(
        [volume("PRIMARY.TXT")],
        [volume(f"LOG{index}.TXT") for index in range(count)],
        container=container)


def test_logical_drives_follow_the_primaries(images):
    image = images.open(_extended_disk())
    assert len(image.volumes) == 3
    assert [entry[0] for entry in image.volumes[0].entries([])] == [
        "PRIMARY.TXT"]
    assert [entry[0] for entry in image.volumes[1].entries([])] == [
        "LOG0.TXT"]
    assert [entry[0] for entry in image.volumes[2].entries([])] == [
        "LOG1.TXT"]


def test_the_container_itself_is_not_a_volume(images):
    image = images.open(_extended_disk())
    partitions = image.geometry().partitions
    containers = [entry for entry in partitions
                  if entry.kind in (0x05, 0x0F)]
    assert len(containers) == 1
    assert len(image.volumes) == len(partitions) - 1


def test_the_lba_container_is_walked_the_same_way(images):
    image = images.open(_extended_disk(container=0x0F))
    assert len(image.volumes) == 3


def test_a_logical_drive_knows_it_is_one(images):
    image = images.open(_extended_disk())
    assert [entry.logical
            for entry in image.geometry().partitions] == [
        False, False, True, True]


# The drive's shape, read on the host (P10's second source).

def test_a_partitionless_floppy_reports_one_volume_and_no_table(images):
    geometry = images.open(fat_image.volume(TREE)).geometry()
    assert not geometry.partitioned
    assert geometry.partitions == ()
    assert geometry.volumes == 1


def test_a_partitioned_disk_reports_each_partition(images):
    image = images.open(_two_partitions())
    geometry = image.geometry()
    assert geometry.partitioned
    assert geometry.volumes == 2
    assert [entry.number for entry in geometry.partitions] == [1, 2]
    assert [entry.description for entry in geometry.partitions] == [
        "FAT16B", "FAT16B"]


def test_a_partitions_offset_and_length_are_the_tables_own(images):
    volume = fat_image.volume({"A.TXT": b"a"}, bits=16, sectors=20000,
                              per_cluster=4)
    image = images.open(fat_image.partitioned([volume]))
    entry = image.geometry().partitions[0]
    assert entry.offset == 512
    assert entry.length == len(volume)


def test_the_bpbs_geometry_is_reported_when_it_states_one(images):
    volume = images.open(fat_image.volume(TREE)).volumes[0]
    assert volume.heads == 2
    assert volume.sectors_per_track == 18


def test_cylinders_are_the_bpbs_own_answer(images):
    """Present where the stated track geometry divides the
    volume's sector count exactly, and unanswered otherwise --
    never invented (P10). A 1.44M floppy states 2 heads and 18
    sectors over 2880 sectors: 80 cylinders."""
    geometry = images.open(fat_image.volume(TREE)).geometry()
    assert geometry.cylinders == 80


# A drive image is claimed for the length of an access (P27).
#
# The claim is Remanence's, taken at the open under its declared
# intent; what is reliquary's is the vocabulary — contention is
# `at_rest.ImageLocked`, apart from the rest of unreadable because its
# rule id is `image.locked`.

@pytest.mark.parametrize("writable", [False, True],
                         ids=["reader", "writer"])
def test_a_writer_excludes_every_second_opener(images, writable):
    path = images.write(fat_image.volume(TREE))
    images.track(opened(path, writable=True))
    with pytest.raises(at_rest.ImageLocked) as caught:
        opened(path, writable=writable)
    assert "locked by another process" in str(caught.value)


def test_a_reader_admits_readers_and_refuses_a_writer(images):
    path = images.write(fat_image.volume(TREE))
    images.track(opened(path))
    second = images.track(opened(path))
    assert len(second.volumes) == 1
    with pytest.raises(at_rest.ImageLocked):
        opened(path, writable=True)


def test_closing_releases_it_for_the_next_caller(images):
    path = images.write(fat_image.volume(TREE))
    opened(path, writable=True).close()
    second = images.track(opened(path, writable=True))
    assert len(second.volumes) == 1


def test_a_refused_open_leaves_no_claim_behind(images):
    """The failed opener must not keep the image held, or it
    could never be opened again in this process."""
    path = images.write(fat_image.volume(TREE))
    first = opened(path, writable=True)
    with pytest.raises(at_rest.ImageLocked):
        opened(path, writable=True)
    first.close()
    third = images.track(opened(path, writable=True))
    assert len(third.volumes) == 1


# Listing and retrieval, across both FAT widths.

def _volume(images, **geometry):
    return images.open(fat_image.volume(TREE, **geometry)).volumes[0]


def test_a_fat32_scale_volume_is_refused_by_name(images):
    """The width is the cluster count's answer, so a volume at
    FAT32 scale is refused whatever any type byte said (D83) —
    the claim stops at FAT16."""
    payload = fat_image.volume(TREE, bits=32, sectors=70000,
                               per_cluster=1)
    with pytest.raises(at_rest.UnreadableImage) as caught:
        images.open(payload)
    assert "FAT32" in str(caught.value)


@WIDTHS
def test_a_root_listing_is_sorted_with_directory_sizes_null(images,
                                                            geometry):
    volume = _volume(images, **geometry)
    assert volume.entries([]) == [
        ("AUTOEXEC.BAT", False, 11),
        ("BIG.DAT", False, 10496),
        ("OUT", True, None)]


@WIDTHS
def test_a_nested_directory_is_addressed_by_its_segments(images, geometry):
    volume = _volume(images, **geometry)
    assert [name for name, _dir, _size
            in volume.entries(["OUT", "LOGS"])] == ["DEEP.TXT"]


def test_kind_answers_for_a_file_a_directory_and_neither(images):
    volume = _volume(images)
    assert volume.kind([]) == "directory"
    assert volume.kind(["OUT"]) == "directory"
    assert volume.kind(["OUT", "RESULT.LOG"]) == "file"
    assert volume.kind(["NOPE.TXT"]) is None
    assert volume.kind(["OUT", "NOPE.TXT"]) is None


def test_a_file_cannot_be_descended_into(images):
    volume = _volume(images)
    assert volume.kind(["AUTOEXEC.BAT", "INNER.TXT"]) is None


def test_a_name_matches_case_insensitively_as_dos_does(images):
    volume = _volume(images)
    assert volume.kind(["autoexec.bat"]) == "file"
    assert volume.kind(["out", "result.log"]) == "file"


@WIDTHS
def test_a_file_reads_back_byte_for_byte(images, geometry):
    volume = _volume(images, **geometry)
    target = images.path("out.bin")
    volume.copy_to(["AUTOEXEC.BAT"], target)
    with open(target, "rb") as handle:
        assert handle.read() == TREE["AUTOEXEC.BAT"]


@WIDTHS
def test_a_file_spanning_many_clusters_reads_whole(images, geometry):
    """The cluster chain walked, and the tail truncated to the
    recorded size rather than padded out to the last cluster."""
    volume = _volume(images, **geometry)
    target = images.path("big.bin")
    volume.copy_to(["BIG.DAT"], target)
    with open(target, "rb") as handle:
        assert handle.read() == TREE["BIG.DAT"]


def test_a_nested_file_reads_back(images):
    volume = _volume(images)
    target = images.path("deep.bin")
    volume.copy_to(["OUT", "LOGS", "DEEP.TXT"], target)
    with open(target, "rb") as handle:
        assert handle.read() == b"nested"


def test_reading_what_is_not_there_says_so(images):
    volume = _volume(images)
    with pytest.raises(at_rest.UnreadableImage):
        volume.copy_to(["NOPE.TXT"], images.path("x"))
    with pytest.raises(at_rest.UnreadableImage):
        volume.copy_to(["OUT"], images.path("x"))
    with pytest.raises(at_rest.UnreadableImage):
        volume.entries(["NOPE"])


# The label as DOS maintains it, unanswered when there is none.
#
# The root directory's label entry is what `LABEL` writes and `DIR`
# shows, and the boot record's copy answers where the root directory
# carries none; "NO NAME" is the format's own spelling of unlabeled
# and never reads as a name. Remanence reads all of that at the
# filesystem seam now and this layer restates none of it, so what is
# pinned here is the answer reliquary passes on.

def _labelled(payload, label):
    """Write ``label`` into the root directory's label entry."""
    reserved = struct.unpack_from("<H", payload, 14)[0]
    fat_sectors = struct.unpack_from("<H", payload, 22)[0]
    root_at = (reserved + payload[16] * fat_sectors) * 512
    payload[root_at:root_at + 11] = label
    payload[root_at + 11] = 0x08
    return bytes(payload)


def test_an_unlabeled_volume_answers_none(images):
    volume = images.open(fat_image.volume(TREE)).volumes[0]
    assert volume.volume_label() is None


def test_the_root_entry_answers(images):
    payload = _labelled(bytearray(fat_image.volume({})), b"RELICS     ")
    volume = images.open(payload).volumes[0]
    assert volume.volume_label() == "RELICS"


def test_no_name_reads_as_no_label(images):
    payload = _labelled(bytearray(fat_image.volume({})), b"NO NAME    ")
    volume = images.open(payload).volumes[0]
    assert volume.volume_label() is None


def test_the_boot_records_copy_answers_where_the_root_has_none(images):
    """The fallback DOS itself keeps: a volume whose root
    directory carries no label entry still answers with the boot
    record's own copy, where the extended boot record states one.
    It was the residue P27 named until the dependency's report
    carried the field."""
    payload = bytearray(fat_image.volume({}))
    payload[38] = 0x29                      # extended boot record
    payload[43:54] = b"BOOTCOPY   "
    volume = images.open(bytes(payload)).volumes[0]
    assert volume.volume_label() == "BOOTCOPY"


# Writing back into a volume, checked structurally after each one.
#
# `fat_image.consistency` is the assertion that matters here: it reads
# the result from the format rather than through the writer, so a
# chain the writer built wrong, two files claiming one cluster, or FAT
# copies drifting apart are caught by something that does not share
# the writer's opinion — and the writer is Remanence's now, which
# makes the independent check worth more, not less.

def _written(images, geometry, work):
    """Run ``work`` against a fresh volume and commit, returning
    the image's path with its structure verified."""
    path = images.write(fat_image.volume(TREE, **geometry))
    with opened(path, writable=True) as image:
        work(image.volumes[0])
        image.commit()
    with open(path, "rb") as handle:
        payload = handle.read()
    assert fat_image.consistency(payload) == []
    return path


def _reads_back(images, path, segments, expected):
    with opened(path) as image:
        target = images.path("back.bin")
        image.volumes[0].copy_to(segments, target)
    with open(target, "rb") as handle:
        assert handle.read() == expected


@WIDTHS
def test_a_new_file_appears_and_reads_back(images, geometry):
    source = images.source("NEW.TXT", b"written from the host\r\n")
    path = _written(images, geometry,
                    lambda v: v.write_file(["NEW.TXT"], source))
    _reads_back(images, path, ["NEW.TXT"], b"written from the host\r\n")


@WIDTHS
def test_a_file_larger_than_one_cluster_chains(images, geometry):
    payload = bytes(range(256)) * 300
    source = images.source("BIG.DAT", payload)
    path = _written(images, geometry,
                    lambda v: v.write_file(["BIG.DAT"], source))
    _reads_back(images, path, ["BIG.DAT"], payload)


@WIDTHS
def test_an_overwrite_replaces_the_content_and_the_size(images, geometry):
    """Shrinking matters: the old chain has to go back to the pool
    or the volume leaks clusters an overwrite should have reused."""
    big = images.source("BIG.DAT", b"x" * 40000)
    small = images.source("SMALL.TXT", b"tiny")

    def work(volume):
        volume.write_file(["OUT", "RESULT.LOG"], big)
        volume.write_file(["OUT", "RESULT.LOG"], small)

    path = _written(images, geometry, work)
    _reads_back(images, path, ["OUT", "RESULT.LOG"], b"tiny")


@WIDTHS
def test_a_directory_is_created_with_its_parents(images, geometry):
    source = images.source("R.TXT", b"deep")

    def work(volume):
        volume.make_directory(["NEW", "INNER"])
        volume.write_file(["NEW", "INNER", "R.TXT"], source)

    path = _written(images, geometry, work)
    _reads_back(images, path, ["NEW", "INNER", "R.TXT"], b"deep")
    with opened(path) as image:
        assert image.volumes[0].kind(["NEW", "INNER"]) == "directory"


def test_a_missing_parent_refuses_rather_than_creating_it(images):
    """``make_directory`` is the verb that creates one; a
    misspelled directory in a file address is an error rather
    than a new directory nobody asked for."""
    source = images.source("R.TXT", b"r")
    image = images.open(fat_image.volume(TREE), writable=True)
    with pytest.raises(at_rest.UnreadableImage):
        image.volumes[0].write_file(["NOPE", "R.TXT"], source)


def test_a_directory_grows_past_its_first_cluster(images):
    """A subdirectory is a chain like any other, so filling one has
    to extend it rather than run off the end."""
    source = images.source("ONE.TXT", b"1")

    def work(volume):
        volume.make_directory(["MANY"])
        for index in range(48):
            volume.write_file(["MANY", f"F{index:04}.TXT"], source)

    path = _written(images, {}, work)
    with opened(path) as image:
        assert len(image.volumes[0].entries(["MANY"])) == 48


def test_a_full_root_directory_refuses_rather_than_overrunning(images):
    source = images.source("ONE.TXT", b"1")
    image = images.open(fat_image.volume(TREE, root_entries=32),
                        writable=True)
    with pytest.raises(at_rest.UnreadableImage):
        for index in range(400):
            image.volumes[0].write_file([f"F{index:04}.TXT"], source)


def test_a_volume_without_room_refuses_the_file(images):
    source = images.source("HUGE.DAT", b"x" * (2 * 1024 * 1024))
    path = images.write(fat_image.volume({}, sectors=800))
    with opened(path, writable=True) as image:
        with pytest.raises(at_rest.UnreadableImage):
            image.volumes[0].write_file(["HUGE.DAT"], source)
    with open(path, "rb") as handle:
        assert fat_image.consistency(handle.read()) == []


@pytest.mark.parametrize("name", ["RESULTS.TAR.GZ", "TOOLONGNAME.TXT",
                                  "A.TEXT", "HAS SPACE.TXT", "BAD*.TXT",
                                  ""],
                         ids=["two-dots", "too-long", "long-extension",
                              "space", "wildcard", "empty"])
def test_a_name_that_is_not_8_3_is_refused(images, name):
    """Refused with reliquary's own wording (P11): the address
    policy stays here, whatever Remanence would have said."""
    source = images.source("x", b"x")
    image = images.open(fat_image.volume(TREE), writable=True)
    with pytest.raises(at_rest.UnreadableImage) as caught:
        image.volumes[0].write_file([name], source)
    assert "name" in str(caught.value)


def test_a_lowercase_name_is_stored_as_dos_holds_it(images):
    source = images.source("job.bat", b"GO")
    path = _written(images, {},
                    lambda v: v.write_file(["job.bat"], source))
    with opened(path) as image:
        assert "JOB.BAT" in [name for name, _dir, _size
                             in image.volumes[0].entries([])]


def test_writing_needs_a_writable_image(images):
    volume = images.open(fat_image.volume(TREE)).volumes[0]
    source = images.source("N.TXT", b"n")
    with pytest.raises(at_rest.UnreadableImage) as caught:
        volume.write_file(["N.TXT"], source)
    assert "reading only" in str(caught.value)


def test_a_close_without_commit_undoes_the_write(images):
    """The commit point is real (D77): everything before it costs
    nothing, and only ``commit`` makes a write permanent."""
    source = images.source("NEW.TXT", b"never lands")
    path = images.write(fat_image.volume(TREE))
    with open(path, "rb") as handle:
        before = handle.read()
    with opened(path, writable=True) as image:
        image.volumes[0].write_file(["NEW.TXT"], source)
    with open(path, "rb") as handle:
        assert handle.read() == before
