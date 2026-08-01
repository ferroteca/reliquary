# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Reading and writing a FAT volume in a drive image, on the host.

The at-rest half of in-band file exchange (P16's residue): a machine
is stopped, its disk is a file the host owns, and what is written in
it can be read without asking the guest anything. That is no more
guest inspection than probing an image's format is -- it is the
**read on the host** source P10 names.

**Remanence is the one deep module beneath this file** (P27). It
opens a raw or qcow2 image where it lies, claims it and any backing
chain, discovers the partition and volume geometry, reads and writes
the FAT volumes, and stands a durable commit point under every
write -- an interrupted commit is reconciled at the image's next
open, wholly the old bytes or wholly the new ones (D77). Nothing
here reads a sector.

What this module keeps is the policy Remanence cannot own:

- **The recognition claim** (D83): FAT12, FAT16 and FAT16B over
  standard MBR primary/extended partitioning, and everything else --
  FAT32 included -- is a named refusal. The claim is enforced on the
  partition table Remanence reports, with reliquary's own vocabulary
  for what each type byte declares, so a report and a refusal read
  exactly as they always have.
- **The whole disk or none of it.** Remanence reports a partition it
  cannot read as a row carrying its issue and reads the rest;
  reliquary refuses the disk instead, because a disk with a
  partition it cannot account for is a disk whose volume ordering it
  cannot vouch for either.
- **Guest addresses**: a name a DOS guest could not type is refused,
  never mangled (P11) -- a silently truncated ``results.tar.gz``
  would land somewhere the caller never addressed -- and segments
  are uppercased here because 8.3 names are what a DOS guest sees
  and types (P17).
- **The error vocabulary**: Remanence's stable categories land on
  the standing rule ids -- contention on ``image.locked`` through
  :class:`ImageLocked`, everything else unreadable on
  ``drive.image-unreadable`` through :class:`UnreadableImage`.
"""

import dataclasses
import os
from typing import Optional, Tuple

import remanence

#: The FAT partition types a DOS guest makes and this build reads.
#: The type byte is what a partition declares itself to be, and the
#: table is pinned value by value rather than derived from a range:
#: one byte's difference is a different filesystem, and the reader
#: acts on the meaning. **FAT32 is deliberately absent** (owner,
#: D83): the recognized filesystems are FAT12, FAT16 and FAT16B --
#: CHS or LBA typed, the same filesystem either way -- and FAT32 is
#: refused by name with the rest.
_FAT_TYPES = {
    0x01: "FAT12",
    0x04: "FAT16 (under 32 MB)",
    0x06: "FAT16B",
    0x0E: "FAT16B (LBA)",
}

#: Partition types that hold a chain of logical drives rather than a
#: filesystem. Both are DOS's; which one a tool wrote does not change
#: how the chain is walked. ``0x85`` is *not* here -- it is Linux's
#: extended container, and this is the DOS workflow's reader.
_EXTENDED = {0x05: "extended (CHS)", 0x0F: "extended (LBA)"}

#: Types worth naming in a refusal because a user meeting one is
#: owed better than a hex byte. Anything absent is reported as its
#: number, which is still a refusal that names what it refused.
_KNOWN_FOREIGN = {
    0x05: "an extended container",
    0x07: "NTFS or exFAT",
    0x0B: "FAT32 (CHS)",
    0x0C: "FAT32 (LBA)",
    0x0F: "an extended container",
    0x82: "Linux swap",
    0x83: "Linux",
    0x85: "a Linux extended container",
    0xA5: "FreeBSD",
    0xEE: "a GPT protective partition — this disk is GPT, not MBR",
    0xEF: "an EFI system partition",
}


class UnreadableImage(Exception):
    """The image, or a volume in it, is not something this can read.

    Raised rather than guessed past. The caller turns it into the
    capability refusal the user sees, naming what could not be read
    (P11) -- an unreadable filesystem is a gap to report, never a
    reason to answer as though the drive were empty.
    """


class ImageLocked(UnreadableImage):
    """Another process holds the image's claim.

    Kept apart from the rest of unreadable because its remedy is
    different -- the disk is fine, someone else has it -- and the
    caller names it with its own rule id (``image.locked``).
    """


@dataclasses.dataclass(frozen=True)
class Partition:
    """One partition-table entry, as the table declares it.

    ``kind`` is the type byte verbatim and ``description`` is what
    this build reads it as, so a report says both what was on the
    disk and what reliquary made of it.
    """

    number: int
    kind: int
    description: str
    offset: int
    length: int
    logical: bool = False


@dataclasses.dataclass(frozen=True)
class Geometry:
    """A drive's shape, read from the host (P10's second source).

    Declared facts and observations are the other two; nothing here
    is inferred. ``cylinders`` is the BPB's own answer from the first
    volume that states one -- present only where the stated track
    geometry divides the volume's sector count exactly, and ``None``
    otherwise: unanswered rather than guessed.
    """

    partitioned: bool
    partitions: Tuple[Partition, ...]
    volumes: int
    cylinders: Optional[int] = None


def _describe(kind, number, path):
    """What a type byte declares, or a refusal naming what it was.

    The DOS workflow's reader reads DOS's own partitions: the FAT
    types and the two extended containers. Anything else is refused
    here rather than further in, where the failure would read as an
    unreadable filesystem instead of a partition this build was never
    going to open (P11).
    """
    if kind in _FAT_TYPES:
        return _FAT_TYPES[kind]
    if kind in _EXTENDED:
        return _EXTENDED[kind]
    named = _KNOWN_FOREIGN.get(kind)
    holds = named if named else f"partition type 0x{kind:02X}"
    raise UnreadableImage(
        f"{path}: partition {number} holds {holds}, and reliquary's "
        "DOS workflow reads FAT12 and FAT16 partitions and DOS "
        "extended containers only")


def _refuse(path, error):
    """Raise a Remanence error as the refusal reliquary's callers
    catch.

    The category is Remanence's stable vocabulary and the message is
    its diagnostic -- the evidence; which exception class carries it
    is reliquary's rule-id policy, settled where the drive seam
    restates the refusal.
    """
    if getattr(error, "category", None) == "locked":
        raise ImageLocked(
            f"{path} is locked by another process — reliquary will "
            "not read or write a drive image something else may be "
            "writing") from error
    raise UnreadableImage(str(error)) from error


class Image:
    """A drive image opened where it lies, and the volumes in it.

    One Remanence session over the image's whole path -- raw or
    qcow2 decided by the bytes, a backing chain composed and claimed
    immutable, the image locked for the length of the access, and an
    interrupted commit from an earlier life reconciled before
    anything is exposed. ``writable=True`` takes the exclusive
    claim; a busy image is refused by name rather than waited for.
    """

    def __init__(self, path, *, writable=False):
        self.path = os.path.abspath(os.fspath(path))
        self.writable = writable
        try:
            self._disk = remanence.Disk(self.path, writable=writable)
        except remanence.RemanenceError as error:
            _refuse(self.path, error)
        try:
            #: ``"raw"`` or ``"qcow2"`` -- the recorded ``backing``
            #: fact the drive report carries (D83).
            self.format = self._disk.format
            self.size = self._disk.size
            self._geometry, found = self._read_geometry()
            self.volumes = [Volume(self._disk, info, writable)
                            for info in found]
        except remanence.RemanenceError as error:
            self._disk.close()
            _refuse(self.path, error)
        except Exception:
            self._disk.close()
            raise

    def _read_geometry(self):
        """The disk's shape under the recognition claim (D83).

        Remanence answers with everything the disk holds -- blank as
        an answer, every declared partition row, an unreadable row
        carrying its issue. The claim is enforced here: a row whose
        type is outside the pinned set, or one Remanence could not
        read, refuses the whole disk, because a partial answer would
        vouch for an ordering nothing verified.
        """
        report = self._disk.geometry()
        partitions = []
        for entry in report.partitions:
            description = _describe(entry.type_byte, entry.number,
                                    self.path)
            if entry.issue is not None:
                raise UnreadableImage(
                    f"{self.path}: partition {entry.number} "
                    f"({description}) could not be read — {entry.issue}")
            partitions.append(Partition(
                number=entry.number, kind=entry.type_byte,
                description=description, offset=entry.start_bytes,
                length=entry.length_bytes,
                logical=entry.kind == "logical"))
        # ``partitioned`` is what sector 0 held: a partition table,
        # even one declaring nothing, and neither a blank disk nor a
        # bare volume's boot record.
        partitioned = bool(partitions) or (not report.blank
                                           and not report.volumes)
        cylinders = next(
            (info.cylinders for info in report.volumes
             if info.cylinders is not None), None)
        return Geometry(
            partitioned=partitioned, partitions=tuple(partitions),
            volumes=len(report.volumes),
            cylinders=cylinders), report.volumes

    def geometry(self):
        """The drive's shape, for a caller that must know it.

        Read on the host -- P10's second source, and the reason a
        letter map need never assume what a disk holds.
        """
        return self._geometry

    def commit(self):
        """Make the buffered writes permanent, durably (D77).

        Remanence journals what the commit will overwrite before the
        first byte lands, so a crash anywhere leaves a state the next
        open reconciles -- the old image or the new one, never a
        third.
        """
        try:
            self._disk.commit()
        except remanence.RemanenceError as error:
            _refuse(self.path, error)

    def close(self):
        """Release the image, undoing a write that never committed."""
        self._disk.close()

    def __enter__(self):
        return self

    def __exit__(self, *_exception):
        self.close()


class Volume:
    """One FAT volume inside an image.

    Addressing is by path segments, the same list the guest address
    split into, so nothing here composes or parses a guest path: the
    caller hands over what the guest wrote and gets back what is
    there. The volume is named to Remanence by its stable id, the
    identity every file verb shares with the geometry report.

    Writing needs the image opened writable; a read-only one refuses
    by name rather than failing somewhere further in.
    """

    def __init__(self, disk, info, writable):
        self._disk = disk
        self.id = info.id
        #: ``"FAT12"`` or ``"FAT16"`` -- what the volume declares
        #: itself to be, the cluster count deciding the width.
        self.filesystem = info.kind
        self._label = info.label
        self.length = info.length_bytes
        # The BPB's own geometry words, where DOS itself looks. None
        # means the formatter stated none, which is reported as
        # unanswered rather than filled in with a plausible number.
        self.heads = info.heads
        self.sectors_per_track = info.sectors_per_track
        self.cylinders = info.cylinders
        self.writable = writable

    def _call(self, verb, *arguments):
        try:
            return verb(*arguments)
        except remanence.RemanenceError as error:
            _refuse(self.id, error)

    @staticmethod
    def _path(segments, *, validated):
        """Guest segments as the one path string Remanence takes.

        Reading uppercases and passes through -- a name no guest
        could type simply matches nothing. Writing validates every
        segment first (P11): the refusal belongs to the address, with
        reliquary's own wording, before any allocation is attempted.
        """
        if validated:
            segments = [_validated_short_name(segment)
                        for segment in segments]
        else:
            segments = [str(segment).upper() for segment in segments]
        return "/".join(segments)

    def volume_label(self):
        """The volume's label, or ``None`` when it has none.

        The root directory's own label entry is what DOS's ``LABEL``
        command maintains and ``DIR`` shows. Unlabeled is ``None`` --
        "NO NAME" is the format's own spelling of it, so it reads as
        no label rather than as a name.
        """
        if self._label and self._label.upper() != "NO NAME":
            return self._label
        return None

    def kind(self, segments):
        """``"directory"``, ``"file"``, or ``None`` when nothing is
        there."""
        segments = list(segments)
        if not segments:
            return "directory"
        entry = self._call(self._disk.stat, self.id,
                           self._path(segments, validated=False))
        return None if entry is None else entry.kind

    def entries(self, segments):
        """One directory level as ``(name, is_dir, size)``, sorted."""
        segments = list(segments)
        if segments and self.kind(segments) != "directory":
            raise UnreadableImage("no such directory in this volume")
        listed = self._call(self._disk.entries, self.id,
                            self._path(segments, validated=False))
        return sorted(
            (entry.name, entry.kind == "directory",
             None if entry.kind == "directory" else entry.size_bytes)
            for entry in listed)

    def copy_to(self, segments, destination):
        """Write the addressed file out to ``destination``."""
        segments = list(segments)
        if self.kind(segments) != "file":
            raise UnreadableImage("no such file in this volume")
        payload = self._call(self._disk.read_file, self.id,
                             self._path(segments, validated=False))
        with open(destination, "wb") as handle:
            handle.write(bytes(payload))
        return destination

    def write_file(self, segments, source):
        """Write host file ``source`` to the addressed path.

        The parent directory must already exist -- ``make_directory``
        is the verb that creates one, and keeping them apart means a
        misspelled directory in a file address is an error rather
        than a new directory nobody asked for.
        """
        segments = list(segments)
        if not segments:
            raise UnreadableImage("a file address needs a name")
        if not self.writable:
            raise UnreadableImage(
                f"volume {self.id}: opened for reading only")
        with open(source, "rb") as handle:
            payload = handle.read()
        self._call(self._disk.write_file, self.id,
                   self._path(segments, validated=True), payload)
        return len(payload)

    def make_directory(self, segments):
        """Create the addressed directory and any missing parent."""
        if not self.writable:
            raise UnreadableImage(
                f"volume {self.id}: opened for reading only")
        self._call(self._disk.make_directory, self.id,
                   self._path(list(segments), validated=True))


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
