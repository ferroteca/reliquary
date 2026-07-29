# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Agentless DOS provisioning and guest interaction."""

import os
import re

from .errors import StaticError

_ADDRESS = re.compile(r"([A-Za-z]):[\\/]?(.*)\Z", re.DOTALL)


def program_name(path):
    """Return the DOS command name for a supported executable path."""
    name = os.path.basename(path)
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,8}\.[Ee][Xx][Ee]", name):
        raise StaticError(f"guest executable needs a DOS 8.3 name: {name}",
            rule_id="name.not-dos-8-3")
    return name


def _mixes_controller_types(drives):
    """Whether the machine's disks span more than one controller type.

    Only the disks are asked. A floppy sits on the floppy controller
    by construction and carries no `controller` field, so it is
    neither a type in this count nor affected by the answer.
    """
    types = {drive.get("controller", "ide")
             for drive in drives.values()
             if drive.get("medium") != "floppy"}
    return len(types) > 1


def drive_letters(drives):
    """Map DOS drive letters to drive keys, from declared facts and
    **one stated assumption**.

    Built from reliquary's own drive assignment — each drive's medium
    and slot, which reliquary chose — and never from inspecting a
    guest (P10):

    - floppies take ``A:`` and ``B:`` by slot, always: DOS gives the
      floppy drives those letters whatever the disks carry;
    - hard disks follow from ``C:`` in slot order;
    - CD-ROMs follow the last disk, in slot order — ``C:`` when there
      is no disk at all.

    **The assumption is one volume per hard disk** (owner,
    2026-07-28, D71), and it is what places every letter after the
    first disk. It is not a fact: a disk the guest partitioned in two
    shifts every letter after it, and a blueprint declares drives
    rather than what was made of them. It is true of every disk
    reliquary itself materializes — a blank is one volume, and a
    payload image is what its author built — and the price of
    refusing it was that a machine with any hard disk could not
    address its own exchange drive at all, which is what P16 forbids
    (D62's residue).

    **A guest that repartitions makes this silently wrong**, and that
    is filed as a defect rather than hidden: the mapping would name
    the wrong drive, not fail. Closing it means reading volume layout
    off the image on the host — the partition table, and past it
    whatever volume manager a guest layered on — which is no more
    guest inspection than :func:`backend_qemu.probe_image_format` is.
    What stops it today is that every layout is its own reader rather
    than a rule.

    **Mixed controller types still unfix every disk letter**, and no
    assumption rescues them. Slot order is authoritative only within
    a type; across types the guest's firmware decides how the
    controllers themselves enumerate, so even the *first* disk is not
    placeable. The floppies still are: DOS gives them ``A:`` and
    ``B:`` whatever the disks do.

    What is refused permanently is a *declared* volume count in the
    blueprint (owner, 2026-07-27, D56): the guest is the source of
    truth for its own volumes, and a declaration would carry a spec's
    authority over an assertion the guest can silently contradict.
    D71 does not reopen that — an assumption reliquary makes in its
    own code, stated here and filed as a defect, is not a field an
    author can assert into a document.
    """
    letters = {}
    for slot, key in sorted((drive.get("slot", 0), key)
                            for key, drive in drives.items()
                            if drive.get("medium") == "floppy"):
        if slot in (0, 1):
            letters[chr(ord("A") + slot)] = key
    if _mixes_controller_types(drives):
        # Slot order is authoritative only *within* a controller type.
        # Across types the guest's firmware decides how the controllers
        # themselves enumerate, so which disk is C: is not a declared
        # fact and no disk letter is returned rather than guessing one
        # (P17). The floppies above survive: DOS gives them A: and B:
        # whatever the disks do, so their letters are never in doubt.
        #
        # Unreachable today — `machines._drive_common` refuses any
        # controller but `ide`, so every machine that exists is
        # single-type. The guard is here anyway because the invariant
        # is this function's own: depending on a gate three modules
        # away means the day a second type is wired, this mapping
        # quietly starts answering a question it has no fact for.
        return letters
    ordinal = 0
    for medium in ("hdd", "cdrom"):
        # Disks first and then CD-ROMs, which is the order DOS itself
        # assigns in: the disk volumes take their letters at boot and
        # MSCDEX takes the next one after them.
        for _slot, key in sorted((drive.get("slot", 0), key)
                                 for key, drive in drives.items()
                                 if drive.get("medium") == medium):
            letters[chr(ord("C") + ordinal)] = key
            ordinal += 1
    return letters


def undetermined_letters(drives):
    """The drive keys whose letter the declared facts do not fix.

    Every drive a machine declares that :func:`drive_letters` cannot
    place. Since D71 places every disk and CD-ROM on the one-volume-per
    -disk assumption, this is empty for every machine that exists —
    only a machine mixing controller types has drives it cannot place,
    and no controller but ``ide`` is wired. Callers use it to say
    *why* a letter is unavailable, and it stays because the day a
    second controller type lands is the day it fills again.
    """
    placed = set(drive_letters(drives).values())
    return [key for key in sorted(drives) if key not in placed]


def _split(address, *, what):
    """Split a DOS guest address into ``(letter, path segments)``.

    The one address form, shared by every file verb: what the guest's
    own user would write — ``C:\\DOS\\FOO.TXT`` — with DOS separators
    and roots. Case is not significant on DOS, so the letter is
    normalized; the path segments are passed through as written (the
    host filesystem matches them, and the vvfat staging directory is
    where they land). The segment list may be empty here — whether
    that is an address at all is the caller's question, since a drive
    root is a directory and never a file.
    """
    if not isinstance(address, str) or not address.strip():
        raise StaticError(f"a guest {what} address is required",
            rule_id="drive.address-empty")
    match = _ADDRESS.match(address.strip())
    if match is None:
        raise StaticError(
            f"{address!r} is not a DOS path: write it as the guest "
            r"does, drive-letter first (C:\DOS\FOO.TXT)",
            rule_id="drive.address-malformed")
    letter, remainder = match.group(1).upper(), match.group(2)
    segments = [part for part in re.split(r"[\\/]+", remainder) if part]
    if any(part in (".", "..") for part in segments):
        raise StaticError(
            f"{address!r} may not contain . or .. segments",
            rule_id="drive.address-has-dot-segments")
    return letter, segments


def split_address(address):
    """Split a guest **file** address into ``(letter, segments)``.

    A file needs a name, so ``A:\\`` is refused here: it addresses the
    drive itself, which is where :func:`split_directory_address`
    starts.
    """
    letter, segments = _split(address, what="file")
    if not segments:
        raise StaticError(
            f"{address!r} names a drive but no file",
            rule_id="drive.address-has-no-file")
    return letter, segments


def split_directory_address(address):
    """Split a guest **directory** address into ``(letter, segments)``.

    The same form as a file's and never a second spelling of it
    (P17): only the drive root is newly sayable, as ``A:\\`` or the
    bare ``A:``, and a trailing separator is optional everywhere else
    — ``A:\\OUT`` and ``A:\\OUT\\`` are one address. An empty segment
    list *is* the answer for a root, not a missing one.
    """
    return _split(address, what="directory")


def join_address(letter, segments):
    """Render ``(letter, segments)`` back as the guest would write it.

    The inverse of :func:`_split`, and the reason a listing can hand
    back addresses a caller feeds straight to ``get-file``: what
    Reliquary reports is the same vocabulary it accepts (P17).
    """
    return f"{letter}:\\" + "\\".join(segments)
