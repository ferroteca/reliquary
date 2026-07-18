# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Declared QEMU media parsing and argument construction."""

import os
import re


_MEDIA_STEM_RE = re.compile(r"(floppy|hdd|cdrom)(?:_(\d+))?")
_FLOPPY_SLOTS = 2
_IDE_SLOTS = 4


def check_staged_drive(letter):
    """Validate and normalize a staged DOS drive letter."""
    normalized = str(letter).upper()
    if len(normalized) != 1 or not "C" <= normalized <= "Z":
        raise ValueError(
            f"staged_drive={letter!r}: the staged guest drive needs "
            "a single drive letter from C to Z (A: and B: are the "
            "floppies)")
    return normalized


def staged_hdd_plan(media, drives):
    """Return the staging directory and its default guest letter."""
    staged = [slot for slot, (_, is_dir) in media["hdd"].items()
              if is_dir]
    if staged:
        slot = max(staged)
        path = media["hdd"][slot][0]
    else:
        slot = 0
        while slot in media["hdd"]:
            slot += 1
        if slot >= _IDE_SLOTS:
            raise RuntimeError(
                "no free hard-disk slot to stage on: all "
                f"{_IDE_SLOTS} IDE slots are declared under {drives}")
        path = os.path.join(drives,
                            "hdd" if slot == 0 else f"hdd_{slot}")
    lower = sum(1 for candidate in media["hdd"] if candidate < slot)
    return path, chr(ord("C") + lower)


def scan_drives(drives):
    """Read declared media names without interrogating image contents."""
    media = {"floppy": {}, "hdd": {}, "cdrom": {}}
    try:
        entries = sorted(os.listdir(drives))
    except FileNotFoundError:
        return media
    for name in entries:
        path = os.path.join(drives, name)
        is_dir = os.path.isdir(path)
        stem = name if is_dir else os.path.splitext(name)[0]
        match = _MEDIA_STEM_RE.fullmatch(stem)
        if not match:
            continue
        kind = match.group(1)
        slot = int(match.group(2) or 0)
        if is_dir and kind == "cdrom":
            raise RuntimeError(
                f"cannot mount {path}: a staged directory cannot "
                "be a cdrom (virtual FAT emulates no ISO9660); "
                "provide a cdrom image instead")
        limit = _FLOPPY_SLOTS if kind == "floppy" else _IDE_SLOTS
        if kind != "cdrom" and slot >= limit:
            raise RuntimeError(
                f"cannot mount {path}: {kind} slots run from "
                f"0 to {limit - 1}")
        if slot in media[kind]:
            other = os.path.basename(media[kind][slot][0])
            raise RuntimeError(
                f"drive slot clash under {drives}: {other} and "
                f"{name} both claim {kind} slot {slot} (an "
                "unindexed name means slot 0)")
        media[kind][slot] = (path, is_dir)
    return media


def format_options(image):
    extension = os.path.splitext(image)[1].lower()
    return "format=raw," if extension in (".img", ".iso") else ""


def drive_args(media):
    args = []
    for slot, (path, is_dir) in sorted(media["floppy"].items()):
        source = (f"fat:floppy:rw:{path},format=raw," if is_dir
                  else f"{path},{format_options(path)}")
        args += ["-drive", f"file={source}if=floppy,index={slot}"]
    for slot, (path, is_dir) in sorted(media["hdd"].items()):
        source = (f"fat:rw:{path},format=raw," if is_dir
                  else f"{path},{format_options(path)}")
        args += ["-drive", f"file={source}if=ide,index={slot}"]
    next_ide = max(media["hdd"], default=-1) + 1
    for ordinal, slot in enumerate(sorted(media["cdrom"])):
        path, _ = media["cdrom"][slot]
        index = next_ide + ordinal
        if index >= _IDE_SLOTS:
            raise RuntimeError(
                f"cannot mount {path}: the IDE bus is full "
                f"({_IDE_SLOTS} slots, shared by hard disks and "
                "cdroms)")
        args += ["-drive", f"file={path},{format_options(path)}"
                           f"media=cdrom,if=ide,index={index}"]
    return args


def boot_guess(media):
    if 0 in media["floppy"] and not media["floppy"][0][1]:
        return "a"
    if 0 in media["hdd"] and not media["hdd"][0][1]:
        return "c"
    if media["cdrom"]:
        return "d"
    return None
