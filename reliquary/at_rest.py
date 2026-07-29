# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Reading and writing a FAT volume in a drive image, on the host.

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

**Writing is the careful half**, and three rules hold it. Every
allocation is made before any byte is written, so a volume without
room refuses with the file untouched rather than half-landing it.
Both FAT copies are put back from one in-memory table, so they
cannot drift apart. And the image this operates on is a scratch
copy that the caller commits over the real disk only after every
write has returned -- which is what makes an interrupted write cost
nothing.

**A name the guest could not type is refused, never mangled**: a
silently truncated ``results.tar.gz`` would land somewhere the
caller never addressed and could not find (P11).

**8.3 names are what a DOS guest sees**, so they are what this
reports (P17). Long-name entries are skipped rather than decoded:
a DOS guest addressing its own file writes the short name, and
reporting a name the guest cannot type would be a listing it could
not use.
"""

import datetime
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

    def __init__(self, path, *, writable=False):
        self.path = os.path.abspath(os.fspath(path))
        self.writable = writable
        self._handle = open(self.path, "r+b" if writable else "rb")
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

    def write(self, offset, data):
        if not self.writable:
            raise UnreadableImage(f"{self.path}: opened for reading only")
        if offset + len(data) > self.size:
            # The image's own bounds are the last guard against a
            # miscomputed offset turning a write into a resize.
            raise UnreadableImage(
                f"{self.path}: a write would run past the image")
        self._handle.seek(offset)
        self._handle.write(data)

    def flush(self):
        self._handle.flush()
        os.fsync(self._handle.fileno())

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
    """One FAT volume inside an image.

    Addressing is by path segments, the same list the guest address
    split into, so nothing here composes or parses a path: the caller
    hands over what the guest wrote and gets back what is there.

    Writing needs the image opened writable; a read-only one refuses
    by name rather than failing somewhere further in.
    """

    def __init__(self, image, offset, length, label):
        self.image = image
        self.offset = offset
        self.length = length
        self.label = label
        self._fat = None
        self._fat_dirty = False
        self._cursor = 2
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
        self.fsinfo_offset = None
        if self.bits == 32 and _u16(boot, 48):
            self.fsinfo_offset = (self.offset
                                  + _u16(boot, 48) * self.bytes_per_sector)
        if self.cluster_bytes == 0:
            raise UnreadableImage(
                f"partition {self.label}: a cluster is zero bytes")

    # -- the FAT ------------------------------------------------------

    def _table(self):
        """The first FAT, held in memory for the life of this volume.

        Read whole rather than two bytes at a time: a chain walk
        otherwise costs one seek per cluster, and the write path needs
        the whole table anyway to put both copies back identical.
        """
        if self._fat is None:
            self._fat = bytearray(
                self.image.read(self.fat_offset, self.fat_bytes))
        return self._fat

    def _fat_entry(self, cluster):
        table = self._table()
        if self.bits == 12:
            index = cluster + cluster // 2
            if index + 1 >= self.fat_bytes:
                raise UnreadableImage(
                    f"partition {self.label}: a chain runs past the FAT")
            value = _u16(table, index)
            return value >> 4 if cluster & 1 else value & 0x0FFF
        width = self.bits // 8
        index = cluster * width
        if index + width > self.fat_bytes:
            raise UnreadableImage(
                f"partition {self.label}: a chain runs past the FAT")
        return (_u16(table, index) if self.bits == 16
                else _u32(table, index) & 0x0FFFFFFF)

    def _set_fat_entry(self, cluster, value):
        table = self._table()
        if self.bits == 12:
            index = cluster + cluster // 2
            current = _u16(table, index)
            if cluster & 1:
                current = (current & 0x000F) | ((value & 0x0FFF) << 4)
            else:
                current = (current & 0xF000) | (value & 0x0FFF)
            struct.pack_into("<H", table, index, current)
        elif self.bits == 16:
            struct.pack_into("<H", table, cluster * 2, value & 0xFFFF)
        else:
            # The top four bits of a FAT32 entry are reserved and
            # belong to whoever set them, not to this write.
            kept = _u32(table, cluster * 4) & 0xF0000000
            struct.pack_into("<I", table, cluster * 4,
                             kept | (value & 0x0FFFFFFF))
        self._fat_dirty = True

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

    # -- writing ------------------------------------------------------
    #
    # The mirror of the read surface, and the half that has to be
    # careful: a reader that is wrong reports nonsense, a writer that
    # is wrong destroys a disk. Three rules hold here. Nothing is
    # written until every allocation has succeeded, so a volume with no
    # room is refused rather than half-filled. Both FAT copies are put
    # back from one in-memory table, so they cannot disagree. And the
    # image this operates on is a scratch copy -- the caller commits it
    # over the real one only after every write returned.

    def write_file(self, segments, source):
        """Write host file ``source`` to the addressed path.

        The parent directory must already exist -- ``make_directory``
        is the verb that creates one, and keeping them apart means a
        misspelled directory in a file address is an error rather than
        a new directory nobody asked for.
        """
        segments = list(segments)
        if not segments:
            raise UnreadableImage("a file address needs a name")
        name = _validated_short_name(segments[-1])
        parent = self._directory_at(segments[:-1])
        payload_size = os.path.getsize(source)
        existing = self._find_record(parent, name)
        if existing is not None and existing[1][11] & _ATTR_DIRECTORY:
            raise UnreadableImage(
                f"{segments[-1]} is a directory in this volume")

        needed = -(-payload_size // self.cluster_bytes)
        # Free the old chain first so an overwrite can reuse its own
        # clusters -- a same-size rewrite of a nearly full volume
        # should not need room for two copies.
        if existing is not None:
            self._release(((_u16(existing[1], 20) << 16)
                           | _u16(existing[1], 26)))
        clusters = self._claim(needed)
        offset = existing[0] if existing is not None \
            else self._free_slot(parent)
        self._store(clusters, source, payload_size)
        self._write_record(offset, name, 0x20,
                           clusters[0] if clusters else 0, payload_size,
                           os.path.getmtime(source))
        self.flush()
        return payload_size

    def make_directory(self, segments):
        """Create the addressed directory and any missing parent."""
        self._directory_at(list(segments), create=True)
        self.flush()

    def flush(self):
        """Put both FAT copies back, and mark a FAT32 hint stale."""
        if not self._fat_dirty:
            return
        for copy in range(self.fat_count):
            self.image.write(self.fat_offset + copy * self.fat_bytes,
                             bytes(self._fat))
        if self.bits == 32 and self.fsinfo_offset is not None:
            # The free count is a hint, and ours is now wrong. Saying
            # "unknown" is the format's own way to retract it; leaving
            # a stale number would have the guest trust it.
            self.image.write(self.fsinfo_offset + 488,
                             struct.pack("<II", 0xFFFFFFFF, 0xFFFFFFFF))
        self._fat_dirty = False

    # -- allocation ---------------------------------------------------

    def _claim(self, count):
        """Reserve ``count`` free clusters and chain them, or refuse.

        Every cluster is found before any is written, so a volume
        without room fails with the file untouched.
        """
        if count == 0:
            return []
        found = []
        cluster = self._cursor
        scanned = 0
        while len(found) < count and scanned <= self.cluster_count:
            if cluster >= self.cluster_count + 2:
                cluster = 2
            if self._fat_entry(cluster) == 0:
                found.append(cluster)
            cluster += 1
            scanned += 1
        if len(found) < count:
            raise UnreadableImage(
                f"partition {self.label} has room for {len(found)} more "
                f"clusters and the file needs {count}")
        self._cursor = cluster
        end = {12: 0x0FFF, 16: 0xFFFF, 32: 0x0FFFFFFF}[self.bits]
        for index, block in enumerate(found):
            self._set_fat_entry(
                block, found[index + 1] if index + 1 < len(found) else end)
        return found

    def _release(self, first):
        """Return a chain's clusters to the free pool."""
        if first < 2:
            return
        for cluster in list(self._chain(first)):
            self._set_fat_entry(cluster, 0)
        self._cursor = 2

    def _store(self, clusters, source, size):
        """Lay a host file down across already-claimed clusters."""
        remaining = size
        with open(source, "rb") as handle:
            for cluster in clusters:
                chunk = handle.read(self.cluster_bytes)
                if len(chunk) < self.cluster_bytes:
                    # The tail cluster is written whole so no stale
                    # bytes from a freed file show past the new end.
                    chunk = chunk.ljust(self.cluster_bytes, b"\0")
                self.image.write(self._cluster_offset(cluster), chunk)
        del size

    # -- directories --------------------------------------------------

    def _directory_at(self, segments, create=False):
        """The first cluster of the addressed directory.

        ``None`` is the FAT12/16 root, which is a fixed area rather
        than a chain and is the one directory that cannot grow.
        """
        here = None if self.bits != 32 else self.root_cluster
        for index, segment in enumerate(segments):
            name = _validated_short_name(segment)
            record = self._find_record(here, name)
            if record is None:
                if not create:
                    raise UnreadableImage(
                        "no such directory in this volume: "
                        + "\\".join(segments[:index + 1]))
                here = self._create_directory(here, name)
                continue
            if not record[1][11] & _ATTR_DIRECTORY:
                raise UnreadableImage(
                    "\\".join(segments[:index + 1]) + " is a file")
            here = (_u16(record[1], 20) << 16) | _u16(record[1], 26)
        return here

    def _create_directory(self, parent, name):
        """Make one directory inside ``parent``, returning its cluster."""
        # The parent's slot is found first: a full root that cannot
        # grow should refuse before anything is allocated.
        slot = self._free_slot(parent)
        cluster = self._claim(1)[0]
        self.image.write(self._cluster_offset(cluster),
                         bytes(self.cluster_bytes))
        base = self._cluster_offset(cluster)
        # A subdirectory's own two links. ".." naming cluster 0 is how
        # the format spells "the root", whichever root that is.
        self._write_record(base, ".", _ATTR_DIRECTORY, cluster, 0, None)
        self._write_record(base + 32, "..", _ATTR_DIRECTORY,
                           parent or 0, 0, None)
        self._write_record(slot, name, _ATTR_DIRECTORY, cluster, 0, None)
        return cluster

    def _blocks(self, first):
        if first is None:
            return [(self.root_offset, self.root_entries * 32)]
        return [(self._cluster_offset(cluster), self.cluster_bytes)
                for cluster in self._chain(first)]

    def _records(self, first):
        """Every ``(offset, record)`` slot of a directory, in order."""
        for base, length in self._blocks(first):
            block = self.image.read(base, length)
            for start in range(0, length - 31, 32):
                yield base + start, block[start:start + 32]

    def _find_record(self, first, name):
        """The slot holding ``name``, or ``None``."""
        for offset, record in self._records(first):
            if record[0] == 0x00:
                return None
            if record[0] == 0xE5 or record[11] & _ATTR_LONG_NAME \
                    == _ATTR_LONG_NAME:
                continue
            if self._short_name(record).upper() == name.upper():
                return offset, record
        return None

    def _free_slot(self, first):
        """A usable directory slot, growing the directory if it can."""
        for offset, record in self._records(first):
            if record[0] in (0x00, 0xE5):
                return offset
        if first is None:
            raise UnreadableImage(
                f"partition {self.label}: the root directory is full "
                f"({self.root_entries} entries), and a FAT12/16 root "
                "cannot grow -- write into a subdirectory")
        added = self._claim(1)[0]
        self.image.write(self._cluster_offset(added),
                         bytes(self.cluster_bytes))
        last = None
        for cluster in self._chain(first):
            last = cluster
        self._set_fat_entry(last, added)
        return self._cluster_offset(added)

    def _write_record(self, offset, name, attributes, cluster, size, stamp):
        """Put one 32-byte directory record down."""
        packed_date, packed_time = _stamp(stamp)
        record = bytearray(32)
        record[0:11] = _short_bytes(name)
        record[11] = attributes
        # 14 created, 16 created date, 18 last accessed, 20 cluster
        # high, 22 written, 24 written date, 26 cluster low, 28 size.
        struct.pack_into("<HHH", record, 14,
                         packed_time, packed_date, packed_date)
        struct.pack_into("<H", record, 20, (cluster >> 16) & 0xFFFF)
        struct.pack_into("<HH", record, 22, packed_time, packed_date)
        struct.pack_into("<H", record, 26, cluster & 0xFFFF)
        struct.pack_into("<I", record, 28, size)
        self.image.write(offset, bytes(record))


#: What DOS refuses in a name, plus the control characters. Space is
#: absent on purpose: it pads a short name and is caught by the length
#: and strip checks rather than by this set.
_ILLEGAL = set('"*+,/:;<=>?[' + chr(92) + ']|') | {
    chr(code) for code in range(0x20)}


def _validated_short_name(name):
    """``NAME.EXT`` uppercased, or a refusal naming what is wrong.

    A DOS guest cannot see a name it cannot type, so a host file whose
    name is not 8.3 is **refused rather than mangled** (P11): a
    silently truncated ``results.tar.gz`` would land somewhere the
    caller never addressed and could not find.
    """
    if not name or name in (".", ".."):
        raise UnreadableImage(f"{name!r} is not a file name")
    stem, dot, suffix = name.partition(".")
    if "." in suffix:
        raise UnreadableImage(
            f"{name!r} is not a DOS 8.3 name: it has more than one dot")
    if not stem or len(stem) > 8 or len(suffix) > 3 or (dot and not suffix):
        raise UnreadableImage(
            f"{name!r} is not a DOS 8.3 name: up to eight characters, "
            "then an optional dot and up to three more")
    for character in name:
        if character in _ILLEGAL or character == " ":
            raise UnreadableImage(
                f"{name!r} is not a DOS 8.3 name: {character!r} is not "
                "allowed in one")
    return f"{stem.upper()}.{suffix.upper()}" if suffix else stem.upper()


def _short_bytes(name):
    """A validated name as the 11 padded bytes a record holds."""
    if name in (".", ".."):
        return name.ljust(11).encode("cp437")
    stem, _dot, suffix = name.partition(".")
    return (stem.ljust(8) + suffix.ljust(3)).encode("cp437")


def _stamp(when):
    """FAT's packed ``(date, time)`` for a POSIX timestamp.

    The epoch is 1980 and there is nothing below it, so anything
    earlier -- and the ``None`` a directory's own links carry -- lands
    on the first day the format can express.
    """
    moment = (datetime.datetime(1980, 1, 1) if when is None
              else datetime.datetime.fromtimestamp(when))
    if moment.year < 1980:
        moment = datetime.datetime(1980, 1, 1)
    return (((moment.year - 1980) << 9) | (moment.month << 5) | moment.day,
            (moment.hour << 11) | (moment.minute << 5) | (moment.second // 2))
