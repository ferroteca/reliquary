# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Declared QEMU media parsing and argument construction."""

import collections.abc
import dataclasses
import os
import re
import types


_MEDIA_STEM_RE = re.compile(r"(floppy|hdd|cdrom)(?:_(\d+))?")
_FLOPPY_SLOTS = 2
_IDE_SLOTS = 4
_DRIVE_KEY_RE = re.compile(r"(floppy|hdd|cdrom)(?:_(\d+))?")
_RESERVED_OPTIONS = {"file", "if", "index", "media"}


@dataclasses.dataclass(frozen=True)
class Drive:
    path: str
    is_dir: bool
    options: tuple = ()


def drive_key(name):
    """Return ``(kind, slot, canonical_key)`` for a drive name."""
    match = _DRIVE_KEY_RE.fullmatch(str(name))
    if not match:
        raise ValueError(
            f"invalid drive key {name!r}: expected floppy[_0..1], "
            "hdd[_0..3], or cdrom[_0..3]")
    kind = match.group(1)
    if kind == "cdrom" and match.group(2) is None:
        raise ValueError(
            "invalid drive key 'cdrom': use the ordered slot name "
            "cdrom_0")
    slot = int(match.group(2) or 0)
    limit = _FLOPPY_SLOTS if kind == "floppy" else _IDE_SLOTS
    if slot >= limit:
        raise ValueError(
            f"invalid drive key {name!r}: {kind} slots run from "
            f"0 to {limit - 1}")
    return kind, slot, f"{kind}_{slot}"


def _options(value, key):
    if value is None:
        return ()
    if not isinstance(value, collections.abc.Mapping):
        raise TypeError(f"drives.{key}.options must be a mapping")
    normalized = []
    for name, option in value.items():
        if not isinstance(name, str) or not name:
            raise ValueError(
                f"drives.{key}.options keys must be non-empty strings")
        if name in _RESERVED_OPTIONS:
            raise ValueError(
                f"drives.{key}.options.{name} is owned by reliquary")
        if not isinstance(option, (str, int, float, bool)):
            raise TypeError(
                f"drives.{key}.options.{name} must be a scalar value")
        normalized.append((name, option))
    return tuple(sorted(normalized))


def _validate_directory_options(options, key):
    values = dict(options)
    if "format" in values:
        raise ValueError(
            f"drives.{key}.options.format cannot override "
            "vvfat format=raw")
    if values.get("readonly") in (True, "on"):
        raise ValueError(
            f"drives.{key} is a staged directory and cannot "
            "be read-only")


def normalize_drive_specs(value):
    """Validate and deeply freeze configured drive declarations."""
    if value is None:
        value = {}
    if not isinstance(value, collections.abc.Mapping):
        raise TypeError("drives must be a mapping")
    normalized = {}
    claimed = {}
    for name, declaration in value.items():
        kind, slot, key = drive_key(name)
        if key in claimed:
            raise ValueError(
                f"drive key clash: {claimed[key]!r} and {name!r} "
                f"both mean {key}")
        claimed[key] = name
        if isinstance(declaration, (str, os.PathLike)):
            source = declaration
            options = ()
            enabled = None
        elif isinstance(declaration, collections.abc.Mapping):
            unknown = set(declaration) - {"source", "options", "enabled"}
            if unknown:
                field = sorted(unknown)[0]
                raise ValueError(f"unknown drive field: drives.{key}.{field}")
            source = declaration.get("source")
            options = _options(declaration.get("options"), key)
            enabled = declaration.get("enabled")
            if enabled is not None and not isinstance(enabled, bool):
                raise TypeError(f"drives.{key}.enabled must be a boolean")
        else:
            raise TypeError(
                f"drives.{key} must be a path or drive mapping")
        if source is not None:
            source = os.path.abspath(os.fspath(source))
            if not os.path.exists(source):
                raise FileNotFoundError(
                    f"drive source does not exist: drives.{key}.source="
                    f"{source}")
            is_dir = os.path.isdir(source)
            if kind == "cdrom" and is_dir:
                raise ValueError(
                    f"drives.{key}.source cannot be a directory: "
                    "vvfat emulates no ISO9660 CD-ROM")
            if is_dir:
                _validate_directory_options(options, key)
        normalized[key] = types.MappingProxyType({
            "source": source,
            "options": types.MappingProxyType(dict(options)),
            "enabled": enabled,
        })
    return types.MappingProxyType(normalized)


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
    staged = [slot for slot, drive in media["hdd"].items()
              if drive.is_dir]
    if staged:
        slot = max(staged)
        path = media["hdd"][slot].path
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
            other = os.path.basename(media[kind][slot].path)
            raise RuntimeError(
                f"drive slot clash under {drives}: {other} and "
                f"{name} both claim {kind} slot {slot} (an "
                "unindexed name means slot 0)")
        media[kind][slot] = Drive(path, is_dir)
    return media


def resolve_media(drives, specs=None):
    """Compose filesystem media and normalized configured drive specs."""
    media = scan_drives(drives)
    specs = normalize_drive_specs(specs)
    for key, declaration in specs.items():
        enabled = declaration.get("enabled")
        if enabled is False:
            kind, slot, _ = drive_key(key)
            if slot in media.get(kind, {}):
                del media[kind][slot]
            continue
        kind, slot, _ = drive_key(key)
        source = declaration["source"]
        options = tuple(declaration["options"].items())
        existing = media[kind].get(slot)
        if source is None:
            if existing is None:
                raise ValueError(
                    f"drives.{key}.options has no drive source")
            if existing.is_dir:
                _validate_directory_options(options, key)
            media[kind][slot] = Drive(
                existing.path, existing.is_dir, options)
        else:
            # An explicit ``enabled: True`` deliberately replaces the
            # filesystem-declared drive; a bare source fails closed.
            if existing is not None and enabled is not True:
                raise RuntimeError(
                    f"drive slot clash: {existing.path} under {drives} "
                    f"and drives.{key}.source={source} both claim "
                    f"{kind} slot {slot}")
            media[kind][slot] = Drive(
                source, os.path.isdir(source), options)
    return media


def format_options(image):
    extension = os.path.splitext(image)[1].lower()
    return "format=raw," if extension in (".img", ".iso") else ""


def drive_args(media):
    args = []
    for slot, drive in sorted(media["floppy"].items()):
        source = (f"fat:floppy:rw:{drive.path},format=raw,"
                  if drive.is_dir else drive.path + ",")
        options = _qemu_options(drive)
        args += ["-drive", f"file={source}{options}"
                           f"if=floppy,index={slot}"]
    for slot, drive in sorted(media["hdd"].items()):
        source = (f"fat:rw:{drive.path},format=raw,"
                  if drive.is_dir else drive.path + ",")
        options = _qemu_options(drive)
        args += ["-drive", f"file={source}{options}if=ide,index={slot}"]
    next_ide = max(media["hdd"], default=-1) + 1
    for ordinal, slot in enumerate(sorted(media["cdrom"])):
        drive = media["cdrom"][slot]
        index = next_ide + ordinal
        if index >= _IDE_SLOTS:
            raise RuntimeError(
                f"cannot mount {drive.path}: the IDE bus is full "
                f"({_IDE_SLOTS} slots, shared by hard disks and "
                "cdroms)")
        args += ["-drive", f"file={drive.path},{_qemu_options(drive)}"
                           f"media=cdrom,if=ide,index={index}"]
    return args


def _qemu_options(drive):
    options = dict(drive.options)
    if not drive.is_dir and "format" not in options:
        inferred = format_options(drive.path)
    else:
        inferred = ""
    rendered = []
    for name, value in drive.options:
        if isinstance(value, bool):
            value = "on" if value else "off"
        rendered.append(f"{name}={value},")
    return inferred + "".join(rendered)


def boot_guess(media):
    if 0 in media["floppy"] and not media["floppy"][0].is_dir:
        return "a"
    if 0 in media["hdd"] and not media["hdd"][0].is_dir:
        return "c"
    if media["cdrom"]:
        return "d"
    return None
