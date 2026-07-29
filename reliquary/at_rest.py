# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Reading a FAT volume out of a drive image, on the host.

The at-rest half of in-band file exchange (P16's residue): a machine
is stopped, its disk is a file the host owns, and what is written in
it can be read without asking the guest anything. That is no more
guest inspection than probing an image's format is -- it is the
**read on the host** source P10 names, and the reader that closes
both halves of the letter question eventually.

Two layers, and this module is the portable one. It reads a **raw**
byte image: the partition table if there is one, and past it a
FAT12/16/32 volume. Turning a backend's own image format into raw
bytes belongs to that backend's adapter, since the format is its
choice -- QEMU's qcow2 is not this module's business.

**Read-only, deliberately.** Every entry point here answers what is
in a volume and copies bytes out of one. Writing a FAT volume is a
larger and much less forgiving job -- free-cluster search, chain
building, directory growth, two FAT copies to keep identical, and a
bug corrupts a disk the user cannot rebuild -- so it is refused by
name at the seam rather than half-built here, and stays filed.

**8.3 names are what a DOS guest sees**, so they are what this
reports (P17). Long-name entries are skipped rather than decoded:
a DOS guest addressing its own file writes the short name, and
reporting a name the guest cannot type would be a listing it could
not use.
"""

import os
import struct

_SIGNATURE = 0x55AA
_SECTOR = 512

#: Partition types that hold a chain of logical drives rather than a
#: filesystem. DOS made all three; which one a tool wrote does not
#: change how the chain is walked.
_EXTENDED = {0x05, 0x0F, 0x85}

#: Directory-entry attribute bits, of the six only these three matter
#: to a reader: a long-name fragment is skipped, a volume label is not
#: a file, and a subdirectory is walked rather than read.
_ATTR_LONG_NAME = 0x0F
_ATTR_VOLUME_LABEL = 0x08
_ATTR_DIRECTORY = 0x10

#: A guard against a cyclic cluster chain in a damaged image: a chain
#: may not visit more clusters than the volume has.
_CHAIN_LIMIT = 1 << 24


class UnreadableImage(Exception):
    """The image, or a volume in it, is not something this can read.

    Raised rather than guessed past. The caller turns it into the
    capability refusal the user sees, naming what could not be read
    (P11) -- an unreadable filesystem is a gap to report, never a
    reason to answer as though the drive were empty.
    """


def _u16(data, offset):
    return struct.unpack_from("<H", data, offset)[0]


def _u32(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


def _looks_like_a_bpb(sector):
    """Whether ``sector`` is a FAT boot sector rather than a partition
    table.

    Checked before the partition table, not after: a boot sector also
    carries the ``0x55AA`` signature, so its boot code read as
    partition entries can look plausible. The jump instruction and the
    sector size are what tell them apart.
    """
    if len(sector) < _SECTOR or _u16(sector, 510) != _SIGNATURE:
        return False
    if sector[0] not in (0xEB, 0xE9):
        return False
    bytes_per_sector = _u16(sector, 11)
    if bytes_per_sector not in (512, 1024, 2048, 4096):
        return False
    per_cluster = sector[13]
    return per_cluster != 0 and per_cluster & (per_cluster - 1) == 0


class Image:
    """A raw disk image, opened for reading, and the volumes in it."""

    def __init__(self, path):
        self.path = os.path.abspath(os.fspath(path))
        self._handle = open(self.path, "rb")
        try:
            self.size = os.path.getsize(self.path)
            self.volumes = self._volumes()
        except Exception:
            self._handle.close()
            raise

    def close(self):
        self._handle.close()

    def __enter__(self):
        return self

    def __exit__(self, *_exception):
        self.close()

    def read(self, offset, length):
        self._handle.seek(offset)
        data = self._handle.read(length)
        if len(data) != length:
            raise UnreadableImage(
                f"{self.path}: the image ends before offset {offset}")
        return data

    def _volumes(self):
        first = self.read(0, _SECTOR)
        if _looks_like_a_bpb(first):
            # A partitionless image -- a floppy, or a disk formatted
            # as one whole volume. There is nothing to walk.
            return [Volume(self, 0, self.size, "1")]
        if _u16(first, 510) != _SIGNATURE:
            raise UnreadableImage(
                f"{self.path}: no partition table and no FAT boot "
                "sector; reliquary cannot tell what is in this image")
        volumes = []
        for index, (start, length, kind) in enumerate(
                self._partitions(first), start=1):
            if kind in _EXTENDED:
                continue
            volumes.append(Volume(self, start, length, str(index)))
        return volumes

    def _partitions(self, mbr):
        """Every primary partition, and the logical drives behind an
        extended one, in the order DOS walks them."""
        found = []
        extended_at = None
        for slot in range(4):
            entry = mbr[446 + 16 * slot:462 + 16 * slot]
            kind = entry[4]
            if kind == 0:
                continue
            start = _u32(entry, 8) * _SECTOR
            length = _u32(entry, 12) * _SECTOR
            if length == 0 or start >= self.size:
                continue
            found.append((start, length, kind))
            if kind in _EXTENDED and extended_at is None:
                extended_at = start
        if extended_at is not None:
            found.extend(self._logical(extended_at))
        return found

    def _logical(self, extended_at):
        """Walk the EBR chain inside an extended partition."""
        found = []
        here = extended_at
        seen = set()
        while here and here not in seen and here < self.size:
            seen.add(here)
            record = self.read(here, _SECTOR)
            if _u16(record, 510) != _SIGNATURE:
                break
            entry = record[446:462]
            if entry[4] and _u32(entry, 12):
                found.append((here + _u32(entry, 8) * _SECTOR,
                              _u32(entry, 12) * _SECTOR, entry[4]))
            nxt = record[462:478]
            here = (extended_at + _u32(nxt, 8) * _SECTOR
                    if nxt[4] and _u32(nxt, 12) else None)
        return found


class Volume:
    """One FAT volume inside an image, read-only.

    Addressing is by path segments, the same list the guest address
    split into, so nothing here composes or parses a path: the caller
    hands over what the guest wrote and gets back what is there.
    """

    def __init__(self, image, offset, length, label):
        self.image = image
        self.offset = offset
        self.length = length
        self.label = label
        self._read_boot_sector()

    def _read_boot_sector(self):
        boot = self.image.read(self.offset, _SECTOR)
        if not _looks_like_a_bpb(boot):
            raise UnreadableImage(
                f"partition {self.label} holds no FAT filesystem "
                "reliquary can read")
        self.bytes_per_sector = _u16(boot, 11)
        self.sectors_per_cluster = boot[13]
        reserved = _u16(boot, 14)
        self.fat_count = boot[16]
        self.root_entries = _u16(boot, 17)
        sectors_per_fat = _u16(boot, 22) or _u32(boot, 36)
        total_sectors = _u16(boot, 19) or _u32(boot, 32)
        if not (self.fat_count and sectors_per_fat and total_sectors):
            raise UnreadableImage(
                f"partition {self.label}: the FAT header is not "
                "self-consistent")
        self.fat_offset = self.offset + reserved * self.bytes_per_sector
        self.fat_bytes = sectors_per_fat * self.bytes_per_sector
        root_sectors = ((self.root_entries * 32 + self.bytes_per_sector - 1)
                        // self.bytes_per_sector)
        self.root_offset = (self.fat_offset
                            + self.fat_count * self.fat_bytes)
        first_data = (reserved + self.fat_count * sectors_per_fat
                      + root_sectors)
        self.data_offset = self.offset + first_data * self.bytes_per_sector
        self.cluster_bytes = self.sectors_per_cluster * self.bytes_per_sector
        clusters = (total_sectors - first_data) // self.sectors_per_cluster
        self.cluster_count = max(clusters, 0)
        # The cluster count alone decides the width, and the two
        # boundaries are the specification's, not a heuristic: a
        # volume is FAT12/16/32 by how many clusters it has and by
        # nothing else -- not its size, and not what formatted it.
        self.bits = 12 if clusters < 4085 else (16 if clusters < 65525
                                                else 32)
        self.root_cluster = _u32(boot, 44) if self.bits == 32 else 0
        if self.cluster_bytes == 0:
            raise UnreadableImage(
                f"partition {self.label}: a cluster is zero bytes")

    # -- the FAT ------------------------------------------------------

    def _fat_entry(self, cluster):
        if self.bits == 12:
            index = cluster + cluster // 2
            if index + 1 >= self.fat_bytes:
                raise UnreadableImage(
                    f"partition {self.label}: a chain runs past the FAT")
            pair = self.image.read(self.fat_offset + index, 2)
            value = _u16(pair, 0)
            return value >> 4 if cluster & 1 else value & 0x0FFF
        width = self.bits // 8
        index = cluster * width
        if index + width > self.fat_bytes:
            raise UnreadableImage(
                f"partition {self.label}: a chain runs past the FAT")
        raw = self.image.read(self.fat_offset + index, width)
        return (_u16(raw, 0) if self.bits == 16
                else _u32(raw, 0) & 0x0FFFFFFF)

    def _is_end(self, value):
        return value >= {12: 0x0FF8, 16: 0xFFF8, 32: 0x0FFFFFF8}[self.bits]

    def _chain(self, first):
        """Every cluster of a chain, in order."""
        cluster = first
        seen = set()
        while 2 <= cluster < self.cluster_count + 2:
            if cluster in seen or len(seen) > _CHAIN_LIMIT:
                raise UnreadableImage(
                    f"partition {self.label}: a cluster chain loops")
            seen.add(cluster)
            yield cluster
            value = self._fat_entry(cluster)
            if self._is_end(value):
                return
            cluster = value

    def _cluster_offset(self, cluster):
        return self.data_offset + (cluster - 2) * self.cluster_bytes

    # -- directories --------------------------------------------------

    def _root_records(self):
        if self.bits == 32:
            return self._chained_records(self.root_cluster)
        return [self.image.read(self.root_offset, self.root_entries * 32)]

    def _chained_records(self, first):
        return [self.image.read(self._cluster_offset(cluster),
                                self.cluster_bytes)
                for cluster in self._chain(first)]

    @staticmethod
    def _short_name(record):
        """The 8.3 name a DOS guest would type for this entry."""
        raw = bytearray(record[0:11])
        if raw[0] == 0x05:
            # KANJI's escape for a leading 0xE5, which would otherwise
            # read as the deleted marker.
            raw[0] = 0xE5
        stem = bytes(raw[0:8]).decode("cp437", "replace").rstrip(" ")
        suffix = bytes(raw[8:11]).decode("cp437", "replace").rstrip(" ")
        return f"{stem}.{suffix}" if suffix else stem

    def _entries(self, records):
        """Parse directory records into ``(name, is_dir, size, cluster)``."""
        found = []
        for block in records:
            for start in range(0, len(block) - 31, 32):
                record = block[start:start + 32]
                marker = record[0]
                if marker == 0x00:
                    return found          # nothing is written past here
                attributes = record[11]
                if marker == 0xE5 or attributes & _ATTR_LONG_NAME \
                        == _ATTR_LONG_NAME:
                    continue
                if attributes & _ATTR_VOLUME_LABEL and not \
                        attributes & _ATTR_DIRECTORY:
                    continue
                name = self._short_name(record)
                if name in (".", ".."):
                    continue
                found.append((
                    name,
                    bool(attributes & _ATTR_DIRECTORY),
                    _u32(record, 28),
                    (_u16(record, 20) << 16) | _u16(record, 26)))
        return found

    def _locate(self, segments):
        """Find one entry, returning ``(is_dir, size, cluster)``.

        ``None`` when nothing is at that address -- the caller decides
        whether an absence is an error, exactly as it does for a
        host directory.
        """
        entries = self._entries(self._root_records())
        found = (True, 0, self.root_cluster)
        for index, segment in enumerate(segments):
            match = next((entry for entry in entries
                          if entry[0].upper() == segment.upper()), None)
            if match is None:
                return None
            _name, is_dir, size, cluster = match
            found = (is_dir, size, cluster)
            if index + 1 < len(segments):
                if not is_dir:
                    return None           # a file cannot be descended into
                entries = self._entries(self._chained_records(cluster))
            elif is_dir:
                pass
        return found

    # -- the read-only surface ----------------------------------------

    def kind(self, segments):
        """``"directory"``, ``"file"``, or ``None`` when nothing is there."""
        if not segments:
            return "directory"
        found = self._locate(list(segments))
        if found is None:
            return None
        return "directory" if found[0] else "file"

    def entries(self, segments):
        """One directory level as ``(name, is_dir, size)``, sorted."""
        segments = list(segments)
        if not segments:
            records = self._root_records()
        else:
            found = self._locate(segments)
            if found is None or not found[0]:
                raise UnreadableImage(
                    "no such directory in this volume")
            records = self._chained_records(found[2])
        return sorted((name, is_dir, None if is_dir else size)
                      for name, is_dir, size, _cluster
                      in self._entries(records))

    def copy_to(self, segments, destination):
        """Write the addressed file out to ``destination``.

        Cluster by cluster rather than whole: a guest's file is
        usually small and occasionally is not, and the reader should
        not decide which by holding it all in memory.
        """
        found = self._locate(list(segments))
        if found is None or found[0]:
            raise UnreadableImage("no such file in this volume")
        _is_dir, size, cluster = found
        remaining = size
        with open(destination, "wb") as handle:
            for block in self._chain(cluster):
                if remaining <= 0:
                    break
                chunk = self.image.read(self._cluster_offset(block),
                                        self.cluster_bytes)
                handle.write(chunk[:remaining])
                remaining -= len(chunk)
        if remaining > 0:
            raise UnreadableImage(
                "the file's cluster chain ends before its recorded size")
        return destination
