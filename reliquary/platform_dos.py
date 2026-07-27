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
        raise StaticError(f"guest executable needs a DOS 8.3 name: {name}")
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
    """Map DOS drive letters to drive keys, from declared facts alone.

    Built from reliquary's own drive assignment — each drive's medium
    and slot, which reliquary chose — and never from inspecting a
    guest (P10). **It maps only the letters the declared facts
    determine**, which is fewer than the drives a machine has:

    - floppies take ``A:`` and ``B:`` by slot, always: DOS gives the
      floppy drives those letters whatever the disks carry;
    - with **no hard disk** declared, CD-ROMs follow from ``C:`` in
      slot order — nothing can shift them;
    - with a hard disk declared, the first one is ``C:``.

    Nothing beyond that is mapped, and the omission is deliberate.
    Every later letter depends on how many **volumes** the disks
    before it carry: a disk the guest partitioned in two shifts every
    letter after it. A blueprint declares drives, not what was made
    of them, so reliquary has no fact to reason from and refuses
    rather than guessing (P11, P17). The caller's fix today is to
    address a determined drive — for in-band exchange, a floppy or
    the first hard disk.

    **Volume count is one of two things that unfix a letter; the
    other is mixed controller types.** Slot order is authoritative
    only within a type, and across types the guest's firmware decides
    how the controllers themselves enumerate — so on such a machine
    even the *first* disk is not a declared fact, and no disk letter
    is returned. The floppies still are: DOS gives them ``A:`` and
    ``B:`` whatever the disks do.

    **This is unimplemented, not impossible.** Volume layout can be
    read from the drive image on the host — the partition table, and
    past it whatever volume manager a guest layered on — which is no
    more guest inspection than
    :func:`lifecycle.probe_image_format` is. Growing the mapping that
    way is open; what stops it is that every layout is its own
    reader, not a rule. The refusal here keeps the gap honest in the
    meantime.

    What is refused permanently is a *declared* volume count in the
    blueprint (owner, 2026-07-27, D56): the guest is the source of
    truth for its own volumes, and a declaration would carry a spec's
    authority over an assertion the guest can silently contradict —
    worse than the assumption it replaced.
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
    hdds = sorted((drive.get("slot", 0), key)
                  for key, drive in drives.items()
                  if drive.get("medium") == "hdd")
    if hdds:
        letters["C"] = hdds[0][1]
        return letters
    for ordinal, (_slot, key) in enumerate(
            sorted((drive.get("slot", 0), key)
                   for key, drive in drives.items()
                   if drive.get("medium") == "cdrom")):
        letters[chr(ord("C") + ordinal)] = key
    return letters


def undetermined_letters(drives):
    """The drive keys whose letter the declared facts do not fix.

    Every drive a machine declares that :func:`drive_letters` cannot
    place. Callers use it to say *why* a letter is unavailable — the
    machine has drives beyond the determined ones, and which letter
    each landed on is the guest's answer, not reliquary's.
    """
    placed = set(drive_letters(drives).values())
    return [key for key in sorted(drives) if key not in placed]


def split_address(address):
    """Split a DOS guest address into ``(letter, path segments)``.

    The address is what the guest's own user would write —
    ``C:\\DOS\\FOO.TXT`` — with DOS separators and roots. Case is not
    significant on DOS, so the letter is normalized; the path
    segments are passed through as written (the host filesystem
    matches them, and the vvfat staging directory is where they land).
    """
    if not isinstance(address, str) or not address.strip():
        raise StaticError("a guest file address is required")
    match = _ADDRESS.match(address.strip())
    if match is None:
        raise StaticError(
            f"{address!r} is not a DOS path: write it as the guest "
            r"does, drive-letter first (C:\DOS\FOO.TXT)")
    letter, remainder = match.group(1).upper(), match.group(2)
    segments = [part for part in re.split(r"[\\/]+", remainder) if part]
    if not segments:
        raise StaticError(
            f"{address!r} names a drive but no file")
    if any(part in (".", "..") for part in segments):
        raise StaticError(
            f"{address!r} may not contain . or .. segments")
    return letter, segments
