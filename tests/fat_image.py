# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
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

#: The boot signature, in the byte order a real formatter
#: writes it: 0x55 then 0xAA.
SIGNATURE = b"\x55\xaa"


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
        return {12: 0xFF8, 16: 0xFFF8, 32: 0x0FFFFFF8}[self.bits]

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
        if self.bits == 32:
            table = bytearray(entries * 4)
            struct.pack_into("<II", table, 0, 0x0FFFFFF8, 0x0FFFFFFF)
            for cluster, value in self.chains.items():
                struct.pack_into("<I", table, cluster * 4, value)
            return bytes(table)
        table = bytearray(entries * 2)
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
    is FAT12; pass ``bits=16`` or ``bits=32`` with more sectors for a
    disk. FAT32 has no fixed root area -- its root is a cluster chain
    like any other directory, which is the shape the reader has to
    handle differently and so the shape worth building.
    """
    builder = _Builder(bits, sectors, per_cluster)
    if bits == 32:
        root_entries = 0
        # Cluster 2 is the root, claimed before anything else so the
        # children below it allocate from 3 upwards.
        builder.next_cluster = 3
        builder.data += bytes(builder.cluster_bytes)
        root = builder.directory(tree)
        if len(root) > builder.cluster_bytes:
            raise ValueError("the root directory does not fit one cluster")
        builder.data[0:len(root)] = root
        builder.chains[2] = builder._end()
        root = b""
    else:
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
    reserved = 32 if bits == 32 else 1

    boot = bytearray(SECTOR)
    boot[0:3] = b"\xeb\x3c\x90"
    boot[3:11] = b"RELIQARY"
    struct.pack_into("<HBHBHHBHHHII", boot, 11,
                     SECTOR, per_cluster, reserved, 2, root_entries,
                     sectors if sectors < 0x10000 else 0,
                     0xF8, 0 if bits == 32 else fat_sectors, 18, 2, 0,
                     sectors if sectors >= 0x10000 else 0)
    if bits == 32:
        # The FAT32 header: its own FAT size, the root's cluster, and
        # the FSInfo sector the writer marks stale.
        struct.pack_into("<I", boot, 36, fat_sectors)
        struct.pack_into("<I", boot, 44, 2)
        struct.pack_into("<H", boot, 48, 1)
    boot[510:512] = SIGNATURE

    image = bytearray(boot)
    if bits == 32:
        fsinfo = bytearray(SECTOR)
        struct.pack_into("<I", fsinfo, 0, 0x41615252)
        struct.pack_into("<I", fsinfo, 484, 0x61417272)
        struct.pack_into("<II", fsinfo, 488, 0xFFFFFFFF, 0xFFFFFFFF)
        fsinfo[510:512] = SIGNATURE
        image += fsinfo
    image += bytes((reserved - len(image) // SECTOR) * SECTOR)
    for _copy in range(2):
        image += table.ljust(fat_sectors * SECTOR, b"\0")
    image += root.ljust(root_sectors * SECTOR, b"\0")
    image += builder.data
    return bytes(image).ljust(sectors * SECTOR, b"\0")


def consistency(payload, *, offset=0):
    """Structural problems in a FAT volume, as a list of strings.

    Written from the format rather than from ``at_rest``, so it is an
    independent opinion on what that module's *writer* produced —
    which matters more here than for the reader, because a reader that
    is wrong reports nonsense and a writer that is wrong leaves a disk
    the guest cannot mount.

    It checks what a wrong writer actually breaks: the two FAT copies
    disagreeing, a cluster claimed by two files, a chain that runs off
    the end or never terminates, and a file whose chain is shorter
    than its recorded size.
    """
    problems = []
    boot = payload[offset:offset + SECTOR]
    if boot[510:512] != SIGNATURE:
        return ["no boot signature"]
    per_sector = struct.unpack_from("<H", boot, 11)[0]
    per_cluster = boot[13]
    reserved = struct.unpack_from("<H", boot, 14)[0]
    fat_count = boot[16]
    root_entries = struct.unpack_from("<H", boot, 17)[0]
    fat_sectors = (struct.unpack_from("<H", boot, 22)[0]
                   or struct.unpack_from("<I", boot, 36)[0])
    total = (struct.unpack_from("<H", boot, 19)[0]
             or struct.unpack_from("<I", boot, 32)[0])
    fat_at = offset + reserved * per_sector
    fat_bytes = fat_sectors * per_sector
    root_sectors = -(-root_entries * 32 // per_sector)
    root_at = fat_at + fat_count * fat_bytes
    data_at = offset + (reserved + fat_count * fat_sectors
                        + root_sectors) * per_sector
    cluster_bytes = per_cluster * per_sector
    clusters = (total - (reserved + fat_count * fat_sectors
                         + root_sectors)) // per_cluster
    bits = 12 if clusters < 4085 else (16 if clusters < 65525 else 32)

    first_fat = payload[fat_at:fat_at + fat_bytes]
    for copy in range(1, fat_count):
        other = payload[fat_at + copy * fat_bytes:
                        fat_at + (copy + 1) * fat_bytes]
        if other != first_fat:
            problems.append(f"FAT copy {copy} differs from copy 0")

    def entry(cluster):
        if bits == 12:
            index = cluster + cluster // 2
            value = struct.unpack_from("<H", first_fat, index)[0]
            return value >> 4 if cluster & 1 else value & 0x0FFF
        if bits == 16:
            return struct.unpack_from("<H", first_fat, cluster * 2)[0]
        return struct.unpack_from("<I", first_fat, cluster * 4)[0] & 0x0FFFFFFF

    end = {12: 0x0FF8, 16: 0xFFF8, 32: 0x0FFFFFF8}[bits]
    owner = {}

    def chain(start, who):
        visited = []
        cluster = start
        while 2 <= cluster < clusters + 2:
            if cluster in owner:
                problems.append(
                    f"cluster {cluster} is claimed by {owner[cluster]} "
                    f"and by {who}")
                return visited
            owner[cluster] = who
            visited.append(cluster)
            if len(visited) > clusters:
                problems.append(f"{who}: the chain never ends")
                return visited
            value = entry(cluster)
            if value >= end:
                return visited
            cluster = value
        problems.append(f"{who}: the chain leaves the volume at {cluster}")
        return visited

    def walk(first, where):
        if first is None:
            block = payload[root_at:root_at + root_entries * 32]
        else:
            block = b"".join(
                payload[data_at + (cluster - 2) * cluster_bytes:
                        data_at + (cluster - 1) * cluster_bytes]
                for cluster in chain(first, where or "root"))
        for start in range(0, len(block) - 31, 32):
            record = block[start:start + 32]
            if record[0] == 0x00:
                return
            if record[0] == 0xE5 or record[11] & 0x0F == 0x0F:
                continue
            stem = record[0:8].decode("cp437").rstrip()
            extension = record[8:11].decode("cp437").rstrip()
            name = stem + ("." + extension if extension else "")
            if name in (".", ".."):
                # The self and parent links, whose clusters belong to
                # the directories they name and not to these records.
                continue
            here = (where + "\\" if where else "") + name
            cluster = (struct.unpack_from("<H", record, 20)[0] << 16
                       | struct.unpack_from("<H", record, 26)[0])
            size = struct.unpack_from("<I", record, 28)[0]
            if record[11] & 0x10:
                walk(cluster, here)
            elif cluster:
                held = len(chain(cluster, here)) * cluster_bytes
                if held < size:
                    problems.append(
                        f"{here}: {size} bytes recorded, {held} held")
            elif size:
                problems.append(f"{here}: {size} bytes but no cluster")

    walk(None if bits != 32 else struct.unpack_from("<I", boot, 44)[0], "")
    return problems


def partitioned(volumes, *, gap=SECTOR, kinds=None):
    """An MBR disk holding ``volumes`` as primary partitions.

    ``kinds`` overrides the type byte per slot, which is how a test
    puts a partition the DOS reader must refuse on an otherwise
    ordinary disk.
    """
    table = bytearray(SECTOR)
    body = b""
    start = gap
    for slot, payload in enumerate(volumes):
        sectors = len(payload) // SECTOR
        kind = 0x06 if kinds is None else kinds[slot]
        entry = (bytes(4) + bytes([kind]) + bytes(3)
                 + struct.pack("<II", start // SECTOR, sectors))
        table[446 + 16 * slot:462 + 16 * slot] = entry
        body += bytes(start - gap - len(body)) + payload
        start += len(payload)
    table[510:512] = SIGNATURE
    return bytes(table).ljust(gap, b"\0") + body


def _entry(kind, start_sector, sectors):
    return (bytes(4) + bytes([kind]) + bytes(3)
            + struct.pack("<II", start_sector, sectors))


def extended(primaries, logicals, *, gap=SECTOR, container=0x05):
    """An MBR disk whose second slot is an extended container.

    The EBR chain is written the way DOS writes it, and the two
    bases differ on purpose: a logical drive's own entry counts from
    **its EBR**, while the link to the next EBR counts from the
    **container's start**. Getting those two the same way round is
    most of what walking a chain is, so the builder states them
    separately rather than sharing one number.
    """
    table = bytearray(SECTOR)
    body = b""
    start = gap
    for slot, payload in enumerate(primaries):
        sectors = len(payload) // SECTOR
        table[446 + 16 * slot:462 + 16 * slot] = _entry(
            0x06, start // SECTOR, sectors)
        body += payload
        start += len(payload)

    container_at = start
    chain = b""
    places = []
    for payload in logicals:
        places.append(container_at + len(chain))
        chain += bytes(SECTOR) + payload
    for index, payload in enumerate(logicals):
        ebr = bytearray(SECTOR)
        ebr[446:462] = _entry(0x06, 1, len(payload) // SECTOR)
        if index + 1 < len(logicals):
            following = places[index + 1] - container_at
            ebr[462:478] = _entry(
                container, following // SECTOR,
                (len(logicals[index + 1]) + SECTOR) // SECTOR)
        ebr[510:512] = SIGNATURE
        offset = places[index] - container_at
        chain = chain[:offset] + bytes(ebr) + chain[offset + SECTOR:]

    slot = len(primaries)
    table[446 + 16 * slot:462 + 16 * slot] = _entry(
        container, container_at // SECTOR, len(chain) // SECTOR)
    table[510:512] = SIGNATURE
    return bytes(table).ljust(gap, b"\0") + body + chain
