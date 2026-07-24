# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Agentless DOS provisioning and guest interaction."""

import os
import re

_ADDRESS = re.compile(r"([A-Za-z]):[\\/]?(.*)\Z", re.DOTALL)


def program_name(path):
    """Return the DOS command name for a supported executable path."""
    name = os.path.basename(path)
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,8}\.[Ee][Xx][Ee]", name):
        raise ValueError(f"guest executable needs a DOS 8.3 name: {name}")
    return name


def drive_letters(drives):
    """Map DOS drive letters to drive keys, from declared facts alone.

    The mapping is built from reliquary's own drive assignment — each
    drive's medium and slot, which reliquary chose — and never from
    inspecting a guest (P10):

    - floppies take ``A:`` and ``B:`` by slot;
    - hard disks take ``C:`` onward, in slot order;
    - CD-ROMs take the letters after the last hard disk, in slot order.

    That last rule assumes one volume per hard disk, which is what
    reliquary's own materialization produces. A guest that partitions
    a disk into several volumes shifts every later letter — the
    ambiguity P17 names — and the caller resolves it by addressing a
    drive reliquary assigned unambiguously (a floppy) or by declaring
    fewer disks.
    """
    letters = {}
    floppies = sorted((drive.get("slot", 0), key)
                      for key, drive in drives.items()
                      if drive.get("medium") == "floppy")
    for slot, key in floppies:
        if slot in (0, 1):
            letters[chr(ord("A") + slot)] = key
    ordinal = 0
    hdds = sorted((drive.get("slot", 0), key)
                  for key, drive in drives.items()
                  if drive.get("medium") == "hdd")
    cdroms = sorted((drive.get("slot", 0), key)
                    for key, drive in drives.items()
                    if drive.get("medium") == "cdrom")
    for _slot, key in hdds + cdroms:
        letters[chr(ord("C") + ordinal)] = key
        ordinal += 1
    return letters


def split_address(address):
    """Split a DOS guest address into ``(letter, path segments)``.

    The address is what the guest's own user would write —
    ``C:\\DOS\\FOO.TXT`` — with DOS separators and roots. Case is not
    significant on DOS, so the letter is normalized; the path
    segments are passed through as written (the host filesystem
    matches them, and the vvfat staging directory is where they land).
    """
    if not isinstance(address, str) or not address.strip():
        raise ValueError("a guest file address is required")
    match = _ADDRESS.match(address.strip())
    if match is None:
        raise ValueError(
            f"{address!r} is not a DOS path: write it as the guest "
            r"does, drive-letter first (C:\DOS\FOO.TXT)")
    letter, remainder = match.group(1).upper(), match.group(2)
    segments = [part for part in re.split(r"[\\/]+", remainder) if part]
    if not segments:
        raise ValueError(
            f"{address!r} names a drive but no file")
    if any(part in (".", "..") for part in segments):
        raise ValueError(
            f"{address!r} may not contain . or .. segments")
    return letter, segments
