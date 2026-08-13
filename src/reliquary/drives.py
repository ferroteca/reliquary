# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""What a stopped machine's disks hold, and how the guest names them.

One module for one question, asked two ways. `describe_drives`
reports the answer and the five in-band file verbs act on it, and
both stand on the same three facts: what each disk holds, read at
rest on the host; the letter map the platform derives from those
counts; and the refusal vocabulary a disk that cannot be read
answers with.

**That is why they are one module.** The rule that the first
unreadable disk answers for every letter behind it (P11, P17) used
to be written twice — once for the report and once for the file
verbs, the first carrying a comment admitting it was the second's
copy. Two implementations of one rule that must agree is a defect
waiting; here it is written once.

The drive seam is `_HostDirectory` and `_ImageVolume`: two adapters
behind one interface — `writable`, `path`, `kind`, `entries`,
`copy_out`, `write_file`, `make_directory`, `commit`, `close` —
which the verbs are written against and `_resolve_address` chooses
between. A directory-source (vvfat) drive *is* its host directory;
a drive image is opened where it lies through `at_rest` (P27), and
never copied to be read.

Everything here is stopped-only except the report, which answers
from the record (D83). This module stands on `machine_state` alone
and never on the lifecycle: `machines.start_machine` calls
`read_drive_record` at its first step, and that edge runs one way.
"""

import os
import shutil
from datetime import datetime, timezone

from . import at_rest
from . import backends
from .errors import InternalError, PreflightError, ReliquaryError
from .machine_state import (load_machine_state, machine_lock,
                            resolve_machine, write_state)


def describe_drives(*, machine=None, blueprint=None, context=None):
    """Report the selected machine's drives and what they hold.

    One machine-level report for a created machine (D83): per drive
    the declared and chosen facts (key, medium, slot, media,
    materialization); per hard disk what was read at rest — the
    backing standing behind it, the partitions as the table declares
    them, and per volume the filesystem it declares itself to be
    (the claim stops at FAT16), its label where one exists, and the
    BPB's own geometry where it states one; and the platform's
    derivation over that — for DOS the letter map, letter to
    (drive key, volume index), with unplaced drives named as
    undetermined carrying the blocking disk's own reason and id, the
    same words the file verbs use, because they are the same facts
    (P11, P17).

    **The report answers from the record** in the machine's own
    state, and is never phase-refused. The record is read at every
    start — the first step, before the backend is engaged, so a
    running machine's answer is this boot's own starting state — and
    by the file verbs' stopped re-reads (D78's counts force those,
    and the record refreshes with them). This call reads a disk in
    exactly one case: the machine is down and the disk has no record
    yet, which covers the window between create and first start.
    Anything else standing answers as recorded (``recorded: true``,
    each disk's ``read-at`` saying when) — a change made behind the
    record, a guest session's repartitioning included, is picked up
    at the next start or by an explicit :func:`refresh_drives`.
    """
    machine_id = resolve_machine(
        machine=machine, blueprint=blueprint, context=context)
    state = load_machine_state(machine_id, context)
    if state.get("phase") == "ready":
        drives = state.get("drives", {})
        missing = {key: drive for key, drive in sorted(drives.items())
                   if drive.get("medium") == "hdd"
                   and not isinstance(drive.get("geometry"), dict)}
        if missing:
            # The one automatic read outside a start (D83): a disk
            # that has never been recorded, on a machine that is
            # down, for a report the user asked for.
            for key, drive in missing.items():
                record, count = read_drive_record(
                    state.get("backend") or "qemu", drive, key)
                drive["geometry"] = record
                if count is not None:
                    drive["volumes"] = count
            state["drives"] = drives
            write_state(machine_id, state, context)
            return _compose_drive_report(machine_id, state,
                                         recorded=False)
    return _compose_drive_report(machine_id, state, recorded=True)


def refresh_drives(*, machine=None, blueprint=None, context=None):
    """Re-read a stopped machine's disks and return the fresh report.

    The explicit refresh (D83): the record otherwise moves only at a
    start, so a drive layout changed while the machine was last up —
    a guest session's repartitioning, an out-of-band edit — is
    invisible to :func:`describe_drives` until the next boot. This
    is the offline way to pick it up now. Stopped-only, because a
    running guest owns its disks; the return is the same report
    ``describe_drives`` gives, read fresh.
    """
    machine_id = resolve_machine(
        machine=machine, blueprint=blueprint, context=context)
    state = load_machine_state(machine_id, context)
    phase = state.get("phase")
    if phase != "ready":
        raise PreflightError(
            f"machine {machine_id} must be stopped to refresh its "
            f"drive record (phase: {phase}): a running guest owns "
            "its disks, and a running machine's report answers from "
            "the record", rule_id="machine.must-be-stopped")
    drives = state.get("drives", {})
    for drive in drives.values():
        if drive.get("medium") == "hdd":
            drive.pop("volumes", None)
            drive.pop("geometry", None)
    _disk_volumes(machine_id, state, drives, context)
    return _compose_drive_report(machine_id, state, recorded=False)


_MEDIUM_ORDER = {"floppy": 0, "hdd": 1, "cdrom": 2}


def _blocking_disk(undetermined, reasons):
    """Which unread disk accounts for the letters nobody can place.

    **The specific cause outranks the symptom** (P11, P17): a disk
    whose volumes could not be read is *why* the letters behind it
    are unknown, and naming that is more use than naming the
    consequence. The first undetermined drive carrying a reason of
    its own is that cause; everything after it is downstream of it.

    Returns ``(key, rule_id, reason)``, or ``None`` when no disk is
    to blame — a machine mixing controller types, where the symptom
    answers for itself.

    The report and the file verbs both ask this and answer it
    differently: one lists every unplaced drive, the other refuses
    one address. **What must not differ is which disk is named**, so
    the choosing lives here and only the wording is each caller's.
    """
    for key in undetermined:
        if key in reasons:
            return (key, *reasons[key])
    return None


def _compose_drive_report(machine_id, state, recorded):
    """The drive report document, composed from the drive records.

    The mapping section derives from the same records the drive
    section shows, so the two cannot disagree (D83). The platform's
    section speaks that platform's own vocabulary — DOS is the
    delivered platform and its letter map the delivered content; any
    other platform's mapping is a named gap rather than a guess
    (P11).
    """
    drives = state.get("drives", {})
    counts = {}
    reasons = {}
    entries = []
    for key, drive in sorted(
            drives.items(),
            key=lambda item: (_MEDIUM_ORDER.get(item[1].get("medium"), 3),
                              item[1].get("slot", 0), item[0])):
        entry = {
            "key": key,
            "medium": drive.get("medium"),
            "slot": drive.get("slot"),
            "media": drive.get("media"),
            "materialize": drive.get("materialize"),
        }
        if drive.get("medium") == "hdd":
            record = drive.get("geometry")
            if record is None:
                # A machine whose state predates the record, read
                # while running: nothing was extracted, and nothing
                # may be read now.
                record = _unread_record(
                    None, "drive.geometry-unrecorded",
                    f"drive {key} has no recorded geometry — describe "
                    "the machine while it is stopped to read one")[0]
            entry["geometry"] = record
            unread = record.get("unread")
            if unread is None:
                counts[key] = len(record.get("volumes") or [])
            else:
                reasons[key] = (unread["id"], unread["reason"])
        entries.append(entry)
    platform_name = state.get("platform") or "dos"
    if platform_name == "dos":
        from . import platform_dos
        letters = platform_dos.drive_letters(drives, counts)
        undetermined_keys = platform_dos.undetermined_letters(
            drives, counts)
        cause = _blocking_disk(undetermined_keys, reasons)
        undetermined = []
        for key in undetermined_keys:
            if key in reasons:
                rule, detail = reasons[key]
            elif cause is not None:
                _blocked_key, rule, detail = cause
                detail = (f"{detail}. Drive {key}'s letter depends on "
                          "that disk: its volumes are what place every "
                          "letter behind it")
            else:
                rule = "drive.letter-undetermined"
                detail = (f"drive {key}'s letter cannot be determined "
                          "on this machine, which mixes controller "
                          "types: slot order is authoritative only "
                          "within a type")
            undetermined.append({"drive": key, "id": rule,
                                 "reason": detail})
        mapping = {
            "letters": {
                letter: {"drive": placed[0], "volume": placed[1]}
                for letter, placed in sorted(letters.items())},
            "undetermined": undetermined,
        }
    else:
        mapping = {"unmapped": {
            "id": "platform.verb-not-implemented",
            "reason": f"the guest namespace mapping is not implemented "
                      f"for platform {platform_name!r}; DOS is the "
                      "delivered workflow"}}
    return {
        "machine": machine_id,
        "blueprint": state.get("blueprint"),
        "platform": platform_name,
        "phase": state.get("phase"),
        "recorded": recorded,
        "drives": entries,
        "mapping": mapping,
    }



# -- in-band file exchange ---------------------------------------

def _addressing(platform):
    """The platform module that maps guest addresses to drives.

    Guest paths are guest knowledge, so each platform workflow owns
    its own mapping (P17), built from declared facts only — never by
    inspecting a guest (P10). Anything but DOS fails closed rather
    than borrowing DOS assumptions.
    """
    if platform != "dos":
        raise PreflightError(
            f"in-band file exchange is not implemented for platform "
            f"{platform!r}; DOS is the delivered workflow",
            rule_id="platform.verb-not-implemented")
    from . import platform_dos
    return platform_dos


def _resolve_address(machine_id, address, context, *, directory=False):
    """Resolve a guest-terms address to a host path under a vvfat drive.

    The whole of P17 in one function, and the one place all five file
    verbs go through: the caller writes ``A:\\FOO.TXT`` — or
    ``A:\\OUT`` for a tree, or ``A:\\`` for the drive itself — and
    never learns which host directory backs it.

    Stopped-only, and reachable for a **directory-source (vvfat)
    drive** at any letter: the letter map places every disk on the
    one-volume-per-disk assumption (D71), so an exchange drive behind
    an installed ``C:`` is addressable where it used to be
    unreachable. A drive image at the addressed letter is the
    capability refusal — reliquary cannot read one at rest, and says
    so by name rather than guessing (P11).

    Returns ``(host path, letter, segments, platform module)``; the
    last two are what lets a listing render its own results back as
    guest addresses.
    """
    state = load_machine_state(machine_id, context)
    phase = state.get("phase")
    if phase != "ready":
        raise PreflightError(
            f"machine {machine_id} must be stopped for in-band file "
            f"exchange (phase: {phase}); the backend snapshots a host "
            "directory when the drive is attached, so a running "
            "machine would neither see a put nor have flushed a get",
            rule_id="machine.must-be-stopped")
    platform = _addressing(state.get("platform"))
    drives = state.get("drives", {})
    volumes, unreadable = _disk_volumes(machine_id, state, drives, context)
    letters = platform.drive_letters(drives, volumes)
    letter, segments = (platform.split_directory_address(address)
                        if directory else platform.split_address(address))
    placed = letters.get(letter)
    if placed is None:
        known = ", ".join(f"{name}: ({letters[name][0]})"
                          for name in sorted(letters)) or "none"
        # Two different failures wear one shape, and saying "no such
        # drive" for the second would be a lie: the machine may well
        # have a drive there, and reliquary simply cannot say which
        # letter it took (P17).
        undetermined = platform.undetermined_letters(drives, volumes)
        if undetermined:
            # Two different failures wear one shape here too: the
            # blocking disk answers where there is one, and only a
            # machine mixing controller types leaves the symptom to
            # answer for itself (`_blocking_disk`).
            cause = _blocking_disk(undetermined, unreadable)
            if cause is not None:
                _blocked_key, rule, detail = cause
                raise PreflightError(
                    f"{address}: {detail}. Reliquary cannot say which "
                    f"drive is {letter}: while that disk is unread, "
                    "because its volumes are what place every letter "
                    f"behind it. Determined letters: {known}",
                    rule_id=rule)
            raise PreflightError(
                f"{address}: reliquary cannot determine which drive "
                f"is {letter}: on this machine, which mixes controller "
                "types: slot order is authoritative only within a type, "
                "and across types the guest's firmware decides how the "
                "controllers enumerate. "
                f"Determined letters: {known}. Unplaceable drives: "
                f"{', '.join(undetermined)} — address one of the "
                "determined letters, or give the exchange drive a "
                "floppy slot, whose letter no disk can shift",
                rule_id="drive.letter-undetermined")
        raise PreflightError(
            f"{address}: the machine declares no drive at {letter}:; "
            f"declared letters: {known}", rule_id="drive.letter-not-declared")
    key, volume_index = placed
    root = drives[key].get("path")
    if root is None and drives[key].get("media") is None:
        raise PreflightError(
            f"{address}: drive {key} ({letter}:) is an empty removable "
            "slot — insert a medium before exchanging files through it",
            rule_id="drive.slot-empty")
    if not root:
        raise PreflightError(
            f"{address}: drive {key} ({letter}:) has no realized medium "
            "to exchange files through", rule_id="drive.slot-empty")
    if os.path.isdir(root):
        source = _HostDirectory(os.path.abspath(root))
        resolved = source.path(segments)
        if os.path.commonpath([source.root, resolved]) != source.root:
            raise PreflightError(
                f"{address} escapes drive {key}; a guest address stays "
                "inside its own drive", rule_id="drive.address-escapes")
    else:
        source = _at_rest_volume(state, root, key, letter, address,
                                 volume_index)
    return source, letter, segments, platform


def _disk_volumes(machine_id, state, drives, context):
    """How many volumes each hard disk holds, read on the host.

    **The answer the letter map needs**, and the reason it no longer
    assumes (D71). A directory-source disk is one volume by
    construction — reliquary built it, and the backend presents it as
    one FAT volume — so only an image is opened, and only for its
    partition table.

    The count is cached in the machine's own state and **cleared at
    every start**, the same discipline a machine variable follows: a
    guest can repartition its disk, and it can only do so while it is
    running, so a count taken before a boot says nothing about the
    one after it. A disk this cannot read is left out of the map
    rather than guessed at.

    Only reachable for a stopped machine, which is what makes it
    affordable to be right: the caller is already past the
    ``machine.must-be-stopped`` gate, so every disk is a file the host
    may open.

    Returns ``(counts, reasons)``. A disk missing from ``counts`` is
    one whose volumes could not be read, and ``reasons`` says why in
    the caller's own vocabulary — **the specific refusal has to
    survive this**, because "reliquary cannot determine which drive
    is C:" is a worse answer than "this backend cannot read a drive
    image at rest" whenever the second is the truth (P11).

    Reading a disk stores its full geometry record beside the count
    (D83), so the record and the letters derived from it refresh
    together and cannot drift.
    """
    found = {}
    reasons = {}
    unrecorded = False
    for key, drive in drives.items():
        if drive.get("medium") != "hdd":
            continue
        recorded = drive.get("volumes")
        if isinstance(recorded, int) and recorded >= 0 \
                and isinstance(drive.get("geometry"), dict):
            found[key] = recorded
            continue
        record, count = read_drive_record(
            state.get("backend") or "qemu", drive, key)
        drive["geometry"] = record
        unrecorded = True
        if count is None:
            reasons[key] = (record["unread"]["id"],
                            record["unread"]["reason"])
            continue
        found[key] = count
        drive["volumes"] = count
    if unrecorded:
        # Written back so the next verb in a batch does not reopen
        # every disk. Losing this costs a reread and never an answer.
        state["drives"] = drives
        write_state(machine_id, state, context)
    return found, reasons


def read_drive_record(backend, drive, key):
    """One hard disk's geometry record, plus its volume count.

    ``(record, count)`` — the record is what machine state stores and
    :func:`describe_drives` reports (D83): read at every start (the
    first step, before the backend is engaged), by the file verbs'
    stopped re-reads, by an explicit :func:`refresh_drives`, and
    once for a disk never yet recorded on a down machine. An
    unreadable disk records the refusal itself — id and reason, the
    same words the file verbs use, because **the specific refusal
    has to survive** (P11) — and counts ``None``, so the letter map
    leaves it and every drive behind it unplaced rather than
    guessed at.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    root = drive.get("path")
    if not root:
        return _unread_record(stamp, "drive.slot-empty",
                              f"drive {key} has no realized medium")
    if os.path.isdir(root):
        # A directory-source disk is one volume by construction: the
        # backend presents the host directory as one FAT volume, and
        # reliquary built it. Its facts are the backend's to compose
        # at attach, so they are unanswered rather than guessed.
        return {
            "read-at": stamp,
            "backing": "directory",
            "partitioned": False,
            "partitions": [],
            "cylinders": None,
            "volumes": [_unanswered_volume(0)],
        }, 1
    try:
        adapter = backends.adapter(backend)
        report = adapter.capabilities()
    except ReliquaryError as error:
        return _unread_record(stamp, "machine.backend-unavailable",
                              str(error))
    if not report.at_rest:
        return _unread_record(
            stamp, "drive.no-at-rest-access",
            f"drive {key} is a drive image, and the {backend} adapter "
            "cannot read one at rest — give the machine a "
            "directory-source drive for exchange, and have the guest "
            "copy to it")
    image = None
    try:
        image = at_rest.Image(root)
        geometry = image.geometry()
        volumes = [_volume_facts(index, volume)
                   for index, volume in enumerate(image.volumes)]
        return {
            "read-at": stamp,
            "backing": image.format,
            "partitioned": geometry.partitioned,
            "partitions": [
                {"number": entry.number,
                 "type": entry.kind,
                 "declares": entry.description,
                 "size": entry.length,
                 "logical": entry.logical}
                for entry in geometry.partitions],
            "cylinders": geometry.cylinders,
            "volumes": volumes,
        }, len(volumes)
    except (at_rest.UnreadableImage, OSError, ReliquaryError) as error:
        return _unread_record(
            stamp, "drive.image-unreadable",
            f"drive {key} cannot be read at rest — {error}")
    finally:
        if image is not None:
            image.close()


def _volume_facts(index, volume):
    """One volume's read facts, as the drive record stores them.

    The filesystem is what the volume declares itself to be — the
    cluster count decides the width, and the claim stops at FAT16
    (D83). Geometry words are the BPB's own, ``None`` where it
    states none: unanswered rather than guessed (P10).
    """
    return {
        "index": index,
        "filesystem": volume.filesystem,
        "label": volume.volume_label(),
        "size": volume.length,
        "heads": volume.heads,
        "sectors-per-track": volume.sectors_per_track,
    }


def _unanswered_volume(index):
    return {"index": index, "filesystem": None, "label": None,
            "size": None, "heads": None, "sectors-per-track": None}


def _unread_record(stamp, rule, reason):
    return {"read-at": stamp,
            "unread": {"id": rule, "reason": reason}}, None


class _HostDirectory:
    """A directory-source (vvfat) drive: the host directory *is* it.

    Readable and writable, because the backend snapshots the
    directory at attach and flushes the guest's writes back to it —
    which is why every in-band verb is stopped-only.
    """

    writable = True

    def __init__(self, root):
        self.root = root

    def path(self, segments):
        return os.path.abspath(os.path.join(self.root, *segments))

    def kind(self, segments):
        here = self.path(segments)
        if os.path.isdir(here):
            return "directory"
        return "file" if os.path.isfile(here) else None

    def entries(self, segments):
        base = self.path(segments)
        found = []
        for name in sorted(os.listdir(base)):
            here = os.path.join(base, name)
            is_directory = os.path.isdir(here)
            found.append((name, is_directory,
                          None if is_directory else os.path.getsize(here)))
        return found

    def copy_out(self, segments, destination):
        shutil.copyfile(self.path(segments), destination)

    def write_file(self, segments, source):
        target = self.path(segments)
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
        shutil.copyfile(source, target)

    def make_directory(self, segments):
        os.makedirs(self.path(segments), exist_ok=True)

    def commit(self):
        """Nothing to do: the backend flushes this drive at attach."""

    def close(self):
        pass


class _ImageVolume:
    """A drive image, read where it lies: the FAT volume inside it.

    **Opened lazily**, because opening a disk is not free: a verb that
    turns out to be a write it cannot do, or an address that turns out
    to be malformed, should cost nothing. The capability is still
    settled eagerly -- that refusal is the one a caller most needs
    early.

    **The image is never copied to be read.** Remanence opens it
    where it lies -- raw or qcow2 decided by the bytes (P27) -- so
    the cost of a listing is the sectors the listing touches. The
    image is claimed for the length of the access, and an uncommitted
    write is undone when it closes.
    """

    def __init__(self, image_path, key, letter, address,
                 writable, volume_index=0):
        self.image_path = image_path
        self.key = key
        self.letter = letter
        self.address = address
        self.writable = writable
        #: Which volume on this disk the addressed letter is. The
        #: letter map counted the volumes to place the letter, so this
        #: is that count's other half rather than a second guess.
        self.volume_index = volume_index
        self._image = None
        self._volume = None
        self._written = False

    def _opened(self):
        if self._volume is not None:
            return self._volume
        try:
            self._image = at_rest.Image(self.image_path,
                                        writable=self.writable)
        except at_rest.ImageLocked as error:
            self.close()
            raise PreflightError(
                f"{self.address}: drive {self.key} ({self.letter}:) is "
                f"in use — {error}", rule_id="image.locked") from error
        except (at_rest.UnreadableImage, OSError) as error:
            self.close()
            raise PreflightError(
                f"{self.address}: drive {self.key} ({self.letter}:) cannot "
                f"be read at rest — {error}",
                rule_id="drive.image-unreadable") from error
        except Exception:
            self.close()
            raise
        count = len(self._image.volumes)
        if self.volume_index >= count:
            # The disk changed under the count the letter map was
            # built from. Nothing should be able to do that between
            # the two reads — a stopped machine's disk is not moving —
            # so this is a disagreement to report, never one to read
            # past into whichever volume happens to be there.
            self.close()
            raise PreflightError(
                f"{self.address}: drive {self.key} ({self.letter}:) was "
                f"placed as volume {self.volume_index + 1} of this disk "
                f"and the disk holds {count}; the layout changed while "
                "reliquary was reading it", rule_id="drive.volume-vanished")
        self._volume = self._image.volumes[self.volume_index]
        return self._volume

    def path(self, segments):
        del segments
        raise InternalError(
            "a drive image has no host path to hand out; the write "
            "refusal is meant to have fired before this")

    def kind(self, segments):
        return self._opened().kind(segments)

    def entries(self, segments):
        return self._guarded(self._opened().entries, segments)

    def copy_out(self, segments, destination):
        self._guarded(self._opened().copy_to, segments, destination)

    def write_file(self, segments, source):
        parent = list(segments[:-1])
        if parent:
            self._guarded(self._opened().make_directory, parent)
        self._guarded(self._opened().write_file, segments, source)
        self._written = True

    def make_directory(self, segments):
        if segments:
            self._guarded(self._opened().make_directory, list(segments))
            self._written = True

    def commit(self):
        """Keep the writes: the last step, and the only one that is
        not undoable.

        Everything before it stands on Remanence's own commit point —
        a durable undo journal beneath the write-through (D77) — so a
        refusal or a crash between the first write and this leaves
        the disk exactly as it was, and a crash *during* the commit
        is reconciled at the image's next open.
        """
        if not self._written:
            return
        self._guarded(self._image.commit)
        self._written = False

    def _guarded(self, call, *arguments):
        """Restate a reader complaint as the refusal a caller sees."""
        try:
            return call(*arguments)
        except at_rest.UnreadableImage as error:
            raise PreflightError(
                f"{self.address}: {error}",
                rule_id="drive.image-unreadable") from error

    def close(self):
        """Release the image, undoing a write that never committed."""
        self._volume = None
        if self._image is not None:
            self._image.close()
            self._image = None


def _at_rest_volume(state, image_path, key, letter, address,
                    volume_index=0):
    """The FAT volume inside a stopped machine's drive image.

    The capability is settled here and the image is opened later: an
    adapter whose image format is outside the at-rest claim says so
    before anything is opened, which is the refusal a caller acts on
    (P11).
    """
    backend = state.get("backend") or "qemu"
    adapter = backends.adapter(backend)
    report = adapter.capabilities()
    if not report.at_rest:
        raise PreflightError(
            f"{address}: drive {key} ({letter}:) is a drive image, and "
            f"the {backend} adapter cannot read one at rest — give the "
            "machine a directory-source drive for exchange, and have "
            "the guest copy to it",
            rule_id="drive.no-at-rest-access")
    return _ImageVolume(image_path, key, letter, address,
                        report.at_rest_write, volume_index)


def _writable(source, address, verb):
    """Refuse a write against a drive reliquary can only read."""
    if source.writable:
        return source
    source.close()
    raise PreflightError(
        f"{address}: {verb} needs a drive this backend can write — it "
        "reads a drive image at rest and cannot rebuild one, so write "
        "to a directory-source (vvfat) drive instead",
        rule_id="drive.no-at-rest-write")


def _guest_directory(machine_id, address, context, *, must_exist=True):
    """The host directory behind a guest directory address.

    Reading, absence is its own failure and never a listing of
    nothing: a caller that misspelled ``A:\\OUT`` is told the guest
    has no such directory rather than handed an empty tree. Writing,
    it is created — ``put_file`` already makes the directories its
    address names, and the plural verb would be arbitrary for
    refusing to.
    """
    source, letter, segments, platform = _resolve_address(
        machine_id, address, context, directory=True)
    found = source.kind(segments)
    if found == "file":
        source.close()
        raise PreflightError(
            f"{address} is a file, not a directory; address its "
            "directory, or use get-file for the file itself",
            rule_id="drive.address-not-a-directory")
    if found is None:
        if must_exist:
            source.close()
            raise PreflightError(
                f"the guest has no directory at {address}",
                rule_id="drive.guest-directory-missing")
        _writable(source, address, "creating a guest directory")
        source.make_directory(segments)
    return source, letter, segments, platform


def put_file(source, destination, *, machine=None, blueprint=None,
             context=None):
    """Copy a host file into the guest, addressed in the guest's terms.

    ``destination`` is what the guest's own user would write —
    ``A:\\RESULTS\\RUN.TXT`` on DOS — never a host path, an image, or
    a staging directory (P17). Stopped-only. Returns the guest address
    written, which is the address the guest will read it at.
    """
    machine_id = resolve_machine(
        machine=machine, blueprint=blueprint, context=context)
    origin = os.path.abspath(os.fspath(source))
    if not os.path.isfile(origin):
        raise PreflightError(f"no such file: {origin}",
            rule_id="media.file-missing")
    with machine_lock(machine_id, context):
        drive, _letter, segments, _platform = _resolve_address(
            machine_id, destination, context)
        _writable(drive, destination, "put-file")
        try:
            drive.write_file(segments, origin)
            drive.commit()
        finally:
            drive.close()
    return destination


def get_file(source, destination, *, machine=None, blueprint=None,
             context=None):
    """Retrieve a guest file to the host, addressed in the guest's terms.

    ``source`` is the guest address; ``destination`` a host path. The
    counterpart of :func:`put_file`, and the U14 half that makes the
    retrieved file the caller's product. Stopped-only, so the guest's
    writes have been flushed. Returns the host path written.
    """
    machine_id = resolve_machine(
        machine=machine, blueprint=blueprint, context=context)
    target = os.path.abspath(os.fspath(destination))
    with machine_lock(machine_id, context):
        drive, _letter, segments, _platform = _resolve_address(
            machine_id, source, context)
        try:
            if drive.kind(segments) != "file":
                raise PreflightError(
                    f"the guest has no file at {source}",
                    rule_id="drive.guest-file-missing")
            os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
            drive.copy_out(segments, target)
        finally:
            drive.close()
    return target


def _entries(drive, letter, segments, platform, recursive):
    """The listing under one guest directory, sorted by address."""
    found = []
    pending = [list(segments)]
    while pending:
        prefix = pending.pop()
        for name, is_directory, size in drive.entries(prefix):
            here = prefix + [name]
            found.append({
                "address": platform.join_address(letter, here),
                "name": name,
                "kind": "directory" if is_directory else "file",
                # A directory's size is nothing the guest would
                # report, so it is null rather than a host number
                # dressed as a guest fact. Every entry keeps the same
                # four fields either way (P7).
                "size": None if is_directory else size,
            })
            if is_directory and recursive:
                pending.append(here)
    return sorted(found, key=lambda entry: entry["address"])


def list_files(address, *, recursive=False, machine=None, blueprint=None,
               context=None):
    """List what a stopped machine's drive holds, in the guest's terms.

    ``address`` is a guest directory — ``A:\\`` for the drive itself,
    ``A:\\OUT`` for a tree inside it. Returns a flat array of entries
    sorted by address, each ``{"address", "name", "kind", "size"}``:
    ``kind`` is ``"file"`` or ``"directory"``, ``size`` the file's
    bytes and ``None`` for a directory, and ``address`` the full guest
    address — which is what a caller hands straight back to
    :func:`get_file` without composing a path of its own (P17).

    One directory level by default; ``recursive=True`` walks the tree.
    Stopped-only, and the drive must be a directory-source drive, on
    the same terms as :func:`get_file`.
    """
    machine_id = resolve_machine(
        machine=machine, blueprint=blueprint, context=context)
    with machine_lock(machine_id, context):
        drive, letter, segments, platform = _guest_directory(
            machine_id, address, context)
        try:
            return _entries(drive, letter, segments, platform, recursive)
        finally:
            drive.close()


def put_files(source, destination, *, machine=None, blueprint=None,
              context=None):
    """Copy a host directory tree into the guest, addressed in its terms.

    The **contents** of host directory ``source`` land in guest
    directory ``destination`` — ``A:\\`` puts them at the drive root —
    which is the only shape a root can take, having no name of its own
    to nest under. Directories are created as needed, the destination
    itself included — :func:`put_file` already makes the ones its
    address names — existing files are overwritten, and nothing at
    the destination is removed first: this is a copy, never a mirror.
    Stopped-only. Returns the guest addresses written, sorted.
    """
    machine_id = resolve_machine(
        machine=machine, blueprint=blueprint, context=context)
    origin = os.path.abspath(os.fspath(source))
    if not os.path.isdir(origin):
        raise PreflightError(
            f"no such directory: {origin}",
            rule_id="drive.host-directory-missing")
    written = []
    with machine_lock(machine_id, context):
        drive, letter, segments, platform = _guest_directory(
            machine_id, destination, context, must_exist=False)
        _writable(drive, destination, "put-files")
        try:
            for directory, _subdirectories, files in os.walk(origin):
                relative = os.path.relpath(directory, origin)
                parts = ([] if relative == os.curdir
                         else relative.split(os.sep))
                drive.make_directory(segments + parts)
                for name in sorted(files):
                    drive.write_file(segments + parts + [name],
                                     os.path.join(directory, name))
                    written.append(platform.join_address(
                        letter, segments + parts + [name]))
            drive.commit()
        finally:
            drive.close()
    return sorted(written)


def get_files(source, destination, *, machine=None, blueprint=None,
              context=None):
    """Retrieve a guest directory tree to the host, whole.

    The mirror image of :func:`put_files`: the **contents** of guest
    directory ``source`` land in host directory ``destination``, which
    is created if it does not exist. ``destination`` is required —
    Reliquary never invents a location to write to (P12), and a tree
    is the caller's product to place (U14). Stopped-only, so the
    guest's writes have been flushed. Returns the host paths written,
    sorted.
    """
    machine_id = resolve_machine(
        machine=machine, blueprint=blueprint, context=context)
    target = os.path.abspath(os.fspath(destination))
    if os.path.exists(target) and not os.path.isdir(target):
        raise PreflightError(
            f"{target} is a file; get-files writes a directory tree",
            rule_id="drive.host-destination-not-a-directory")
    written = []
    with machine_lock(machine_id, context):
        drive, _letter, segments, _platform = _guest_directory(
            machine_id, source, context)
        try:
            pending = [(list(segments), target)]
            while pending:
                here, destination_here = pending.pop()
                os.makedirs(destination_here, exist_ok=True)
                for name, is_directory, _size in drive.entries(here):
                    path = os.path.join(destination_here, name)
                    if is_directory:
                        pending.append((here + [name], path))
                        continue
                    drive.copy_out(here + [name], path)
                    written.append(path)
        finally:
            drive.close()
    return sorted(written)
