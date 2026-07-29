# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""A minimal FAT image builder, for testing the at-rest reader.

Cross-cutting on purpose, like ``fake_backend``: the reader in
``reliquary.at_rest`` needs images to read, and neither a checked-in
binary fixture nor an external ``mkfs`` belongs in this suite. Writing
the format from the specification is also the sharper test — a reader
and a writer that agree only because they share a bug would have to
share it twice, and this builder was written from the layout rather
than from the reader.

It builds what the reader must handle and no more: FAT12 and FAT16,
partitionless or behind an MBR, with subdirectories. It is not a FAT
implementation — there is no free-space management, no deletion, and
files are laid down in one pass.
"""

import struct

SECTOR = 512


def _short(name):
    """``NAME.EXT`` as the 11 padded bytes a directory record holds."""
    if name in (".", ".."):
        # The self and parent links are the one pair that is not a
        # stem-and-suffix: the dots sit in the stem.
        return name.ljust(11).encode("cp437")
    stem, _, suffix = name.partition(".")
    return (stem.upper().ljust(8)[:8] + suffix.upper().ljust(3)[:3]).encode(
        "cp437")


def _record(name, attributes, cluster, size):
    # 11 name, 1 attributes, 8 reserved and times, 2 cluster high,
    # 4 write time and date, 2 cluster low, 4 size -- 32 exactly.
    return (_short(name) + bytes([attributes]) + bytes(8)
            + struct.pack("<H", (cluster >> 16) & 0xFFFF)
            + bytes(4)
            + struct.pack("<HI", cluster & 0xFFFF, size))


class _Builder:
    def __init__(self, bits, sectors, per_cluster):
        self.bits = bits
        self.sectors = sectors
        self.per_cluster = per_cluster
        self.cluster_bytes = per_cluster * SECTOR
        self.chains = {}                 # cluster -> next, or 0xFFF/0xFFFF
        self.data = bytearray()
        self.next_cluster = 2

    def _allocate(self, payload):
        """Lay ``payload`` down in fresh clusters, returning the first."""
        if not payload:
            return 0
        count = max(1, -(-len(payload) // self.cluster_bytes))
        first = self.next_cluster
        for index in range(count):
            cluster = first + index
            chunk = payload[index * self.cluster_bytes:
                            (index + 1) * self.cluster_bytes]
            self.data += chunk.ljust(self.cluster_bytes, b"\0")
            self.chains[cluster] = (cluster + 1 if index + 1 < count
                                    else self._end())
        self.next_cluster = first + count
        return first

    def _end(self):
        return 0xFF8 if self.bits == 12 else 0xFFF8

    def directory(self, tree, *, parent=None, own=None):
        """Build one directory's records, allocating what it contains.

        Depth first, because a record has to carry its child's first
        cluster and the child does not have one until it is laid down.
        """
        records = b""
        if own is not None:
            records += _record(".", 0x10, own, 0)
            records += _record("..", 0x10, parent or 0, 0)
        for name in sorted(tree):
            payload = tree[name]
            if isinstance(payload, dict):
                cluster = self.next_cluster
                self.next_cluster += 1
                # Claim the cluster before descending, so a child's
                # ".." names it.
                self.data += bytes(self.cluster_bytes)
                self.chains[cluster] = self._end()
                inner = self.directory(payload, parent=own or 0, own=cluster)
                start = (cluster - 2) * self.cluster_bytes
                self.data[start:start + len(inner)] = inner
                records += _record(name, 0x10, cluster, 0)
            else:
                records += _record(name, 0x20, self._allocate(payload),
                                   len(payload))
        return records

    def fat(self, entries):
        """The FAT itself, sized to the volume."""
        table = bytearray(entries * (2 if self.bits == 16 else 2))
        if self.bits == 16:
            struct.pack_into("<HH", table, 0, 0xFFF8, 0xFFFF)
            for cluster, value in self.chains.items():
                struct.pack_into("<H", table, cluster * 2, value)
            return bytes(table)
        packed = bytearray(-(-entries * 3 // 2) + 2)
        cells = dict(self.chains)
        cells[0], cells[1] = 0xFF8, 0xFFF
        for cluster, value in cells.items():
            index = cluster + cluster // 2
            current = struct.unpack_from("<H", packed, index)[0]
            if cluster & 1:
                current = (current & 0x000F) | ((value & 0x0FFF) << 4)
            else:
                current = (current & 0xF000) | (value & 0x0FFF)
            struct.pack_into("<H", packed, index, current)
        return bytes(packed)


def volume(tree, *, bits=12, sectors=2880, per_cluster=1, root_entries=224):
    """A whole FAT volume as bytes.

    ``tree`` maps a name to ``bytes`` for a file or to a nested dict
    for a directory. The geometry defaults to a 1.44 MB floppy, which
    is FAT12; pass ``bits=16`` with more sectors for a small disk.
    """
    builder = _Builder(bits, sectors, per_cluster)
    root = builder.directory(tree)
    if len(root) > root_entries * 32:
        raise ValueError("the root directory does not fit")

    # The FAT has to cover every cluster the volume could hold, which
    # depends on the FAT's own size -- so it is sized once against the
    # whole volume and the small over-count is left alone, exactly as
    # a real formatter's rounding does.
    clusters = sectors // per_cluster + 2
    table = builder.fat(clusters)
    fat_sectors = -(-len(table) // SECTOR)
    root_sectors = -(-root_entries * 32 // SECTOR)

    boot = bytearray(SECTOR)
    boot[0:3] = b"\xeb\x3c\x90"
    boot[3:11] = b"RELIQARY"
    struct.pack_into("<HBHBHHBHHHII", boot, 11,
                     SECTOR, per_cluster, 1, 2, root_entries,
                     sectors if sectors < 0x10000 else 0,
                     0xF8, fat_sectors, 18, 2, 0,
                     sectors if sectors >= 0x10000 else 0)
    struct.pack_into("<H", boot, 510, 0x55AA)

    image = bytearray(boot)
    for _copy in range(2):
        image += table.ljust(fat_sectors * SECTOR, b"\0")
    image += root.ljust(root_sectors * SECTOR, b"\0")
    image += builder.data
    return bytes(image).ljust(sectors * SECTOR, b"\0")


def partitioned(volumes, *, gap=SECTOR):
    """An MBR disk holding ``volumes`` as primary partitions."""
    table = bytearray(SECTOR)
    body = b""
    start = gap
    for slot, payload in enumerate(volumes):
        sectors = len(payload) // SECTOR
        entry = (bytes(4) + bytes([0x06]) + bytes(3)
                 + struct.pack("<II", start // SECTOR, sectors))
        table[446 + 16 * slot:462 + 16 * slot] = entry
        body += bytes(start - gap - len(body)) + payload
        start += len(payload)
    struct.pack_into("<H", table, 510, 0x55AA)
    return bytes(table).ljust(gap, b"\0") + body
