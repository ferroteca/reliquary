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

The dependency's own shape is a session holding media: an image is
identified, loaded into a session as one medium, and its content is
reached through the partitions the medium bears -- the table's own
rows on a partitioned disk, and the single direct partition where
the volume fills the whole of it. Releasing the medium ends the
claim.

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

#: What this build declares recorded a drive image. A raw or qcow2
#: image says nothing about the drive behind it, so Remanence takes
#: the caller's declaration and reads the layout under that device's
#: own discipline. Reliquary's drives are DOS's: MBR-partitioned,
#: addressed by cylinder, head and sector -- which is what
#: ``mbr-sector-hd`` names. The block-addressed sibling reads the
#: same table under a different addressing story, and declaring it
#: would state something about the disk that nothing here observed.
_DEVICE = "mbr-sector-hd"

#: The filesystem reading declared over a volume that fills its own
#: disk. A partition's type byte determines the reading; the direct
#: partition an unpartitioned image bears has no type byte to
#: determine one, so the FAT claim is stated here instead -- the same
#: claim ``_FAT_TYPES`` makes for a typed row.
_FAT_READING = "fat"

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


def _names(partition, description):
    """What to call the volume a refusal is about.

    A partitioned disk names the row, because that is what a user
    looks at; an unpartitioned one has no row to name.
    """
    if partition.is_direct:
        return "the volume filling the disk"
    return f"partition {partition.ordinal} ({description})"


def _issue(report, partition, facts):
    """Why Remanence could not read the volume, in its own words.

    The filesystem seam answers first, because a volume that composed
    and did not recognize is the ordinary case; the volume's own
    issues answer where nothing was recognized at all.
    """
    if facts is not None and facts.issues:
        return facts.issues[0]
    volume = report.volume(partition.volume_id)
    if volume is not None and volume.issues:
        return volume.issues[0]
    return "no filesystem was recognized in it"


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

    One Remanence session holding one medium -- raw or qcow2 decided
    by the bytes, a backing chain composed and claimed immutable, the
    image locked for the length of the access, and an interrupted
    commit from an earlier life reconciled before anything is
    exposed. ``writable=True`` takes the exclusive claim; a busy
    image is refused by name rather than waited for.
    """

    def __init__(self, path, *, writable=False):
        self.path = os.path.abspath(os.fspath(path))
        self.writable = writable
        self._session = remanence.Session()
        self._medium = None
        try:
            discovery = remanence.discover_media(self.path,
                                                 writable=writable)
            self._medium = self._session.load_discovery_as(discovery,
                                                           _DEVICE)
        except remanence.RemanenceError as error:
            _refuse(self.path, error)
        try:
            #: ``"raw"`` or ``"qcow2"`` -- the recorded ``backing``
            #: fact the drive report carries (D83).
            self.format = self._medium.format
            self.size = self._medium.size
            self._geometry, self.volumes = self._read()
        except remanence.RemanenceError as error:
            self.close()
            _refuse(self.path, error)
        except Exception:
            self.close()
            raise

    def _read(self):
        """The disk's shape and its volumes, under the recognition
        claim (D83).

        Remanence answers with everything the disk holds -- what
        sector 0 was, every declared partition row, a row it could
        not read carrying its issue, and the filesystem it recognized
        on each composed volume. The claim is enforced here: a row
        whose type is outside the pinned set, one Remanence could not
        read, and a declared FAT that yielded no readable volume each
        refuse the whole disk, because a partial answer would vouch
        for an ordering nothing verified.
        """
        report = self._medium.inspect()
        if report.content == "unknown-nonblank":
            raise UnreadableImage(
                f"{self.path}: {report.content_evidence}")
        partitions = []
        volumes = []
        for entry in self._medium.partitions():
            description = None
            if not entry.is_direct:
                description = _describe(entry.type_byte, entry.ordinal,
                                        self.path)
                if entry.issue is not None:
                    raise UnreadableImage(
                        f"{self.path}: partition {entry.ordinal} "
                        f"({description}) could not be read — "
                        f"{entry.issue}")
                partitions.append(Partition(
                    number=entry.ordinal, kind=entry.type_byte,
                    description=description, offset=entry.start_bytes,
                    length=entry.length_bytes,
                    logical=entry.placement == "logical"))
            if entry.volume_id is None:
                # A blank disk holds no volume, and an extended
                # container holds a chain rather than one. A row
                # declaring a filesystem this build reads and
                # composing nothing is the third case, and it is a
                # gap in the ordering rather than an empty disk.
                if entry.is_direct or entry.type_byte in _EXTENDED:
                    continue
                raise UnreadableImage(
                    f"{self.path}: partition {entry.ordinal} "
                    f"({description}) declares a filesystem this "
                    "build reads, and no volume was composed from it")
            names = _names(entry, description)
            facts = report.filesystem_on(entry.volume_id)
            if facts is None or facts.issues:
                raise UnreadableImage(
                    f"{self.path}: {names} could not be read — "
                    f"{_issue(report, entry, facts)}")
            volumes.append(Volume(self.path, names, entry, facts,
                                  self.writable))
        # ``partitioned`` is what sector 0 held, as Remanence
        # classified it: a partition scheme, even one declaring
        # nothing, and neither a blank disk nor a bare volume's boot
        # record.
        cylinders = next((volume.cylinders for volume in volumes
                          if volume.cylinders is not None), None)
        return Geometry(
            partitioned=self._medium.partition_scheme is not None,
            partitions=tuple(partitions), volumes=len(volumes),
            cylinders=cylinders), volumes

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
            self._medium.commit()
        except remanence.RemanenceError as error:
            _refuse(self.path, error)

    def close(self):
        """Release the image, undoing a write that never committed.

        Releasing the medium is Remanence's one state-ending verb and
        never a commit, so whatever was buffered goes with it.
        """
        if self._medium is not None:
            self._session.release_media(self._medium.id)
            self._medium = None

    def __enter__(self):
        return self

    def __exit__(self, *_exception):
        self.close()


class Volume:
    """One FAT volume inside an image.

    Addressing is by path segments, the same list the guest address
    split into, so nothing here composes or parses a guest path: the
    caller hands over what the guest wrote and gets back what is
    there. The volume carries the stable id the inspection report
    issued for it, and its file verbs stand on the namespace the
    partition composing it opens -- one seam, named once at the open
    rather than looked up per call.

    Writing needs the image opened writable; a read-only one refuses
    by name rather than failing somewhere further in.
    """

    def __init__(self, path, names, partition, facts, writable):
        self._path_of_image = path
        self.id = partition.volume_id
        #: Which volume this is, in words a refusal can carry: the
        #: id is stable but says nothing a reader would recognize.
        self.where = names
        # A typed row determines its own reading; the direct
        # partition has no type byte, so the FAT claim is declared.
        self._space = (partition.filesystem() if partition.bears_namespace
                       else partition.filesystem_as(_FAT_READING))
        #: ``"FAT12"`` or ``"FAT16"`` -- what the volume declares
        #: itself to be, the cluster count deciding the width.
        self.filesystem = facts.kind
        self._label = facts.label
        self.length = self._space.length_bytes
        # The BPB's own geometry words, where DOS itself looks. None
        # means the formatter stated none, which is reported as
        # unanswered rather than filled in with a plausible number.
        self.heads = facts.heads
        self.sectors_per_track = facts.sectors_per_track
        self.cylinders = facts.cylinders
        self.writable = writable

    def _call(self, verb, *arguments):
        try:
            return verb(*arguments)
        except remanence.RemanenceError as error:
            _refuse(self._path_of_image, error)

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
        command maintains and ``DIR`` shows, and the boot record's
        copy answers where the root directory carries none.
        Remanence reads the label whole -- both readings, and "NO
        NAME" as the format's own spelling of unlabeled rather than
        as a name -- so what arrives here is already the answer.
        """
        return self._label.name if self._label is not None else None

    def kind(self, segments):
        """``"directory"``, ``"file"``, or ``None`` when nothing is
        there."""
        segments = list(segments)
        if not segments:
            return "directory"
        entry = self._call(self._space.stat,
                           self._path(segments, validated=False))
        return None if entry is None else entry.kind

    def entries(self, segments):
        """One directory level as ``(name, is_dir, size)``, sorted."""
        segments = list(segments)
        if segments and self.kind(segments) != "directory":
            raise UnreadableImage("no such directory in this volume")
        listed = self._call(self._space.entries,
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
        payload = self._call(self._space.read_file,
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
                f"{self.where}: opened for reading only")
        with open(source, "rb") as handle:
            payload = handle.read()
        self._call(self._space.write_file,
                   self._path(segments, validated=True), payload)
        return len(payload)

    def make_directory(self, segments):
        """Create the addressed directory and any missing parent."""
        if not self.writable:
            raise UnreadableImage(
                f"{self.where}: opened for reading only")
        self._call(self._space.make_directory,
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
