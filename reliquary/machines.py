# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Machine materialization and cached-state management."""

import json
import os
import uuid
from datetime import datetime, timezone

from .drives import format_options
from .home import machines_cache_dir
from .lifecycle import create_hdd_image
from .media import fetch_media


def machine_dir_path(machine_id, home=None):
    """Return the machine's cache directory path."""
    return os.path.join(machines_cache_dir(home), machine_id)


def _machine_drives_dir(machine_id, home=None):
    return os.path.join(machine_dir_path(machine_id, home), "drives")


def _state_path(machine_id, home=None):
    return os.path.join(machine_dir_path(machine_id, home),
                        "reliquary-machine.json")


def create(blueprint, *, home=None, blueprint_name=""):
    """Materialize one machine from a parsed Blueprint.

    Creates the machine cache directory under ``cache/machines/<id>/``,
    writes ``reliquary-machine.json``, creates qcow2 images for
    every drive declared with ``size``, and fetches every media
    item to the shared cache (the machine's drives record the
    payload path).  Returns the generated machine id.
    """
    machine_id = uuid.uuid4().hex
    drives_root = _machine_drives_dir(machine_id, home)
    os.makedirs(drives_root)

    resolved_drives = {}
    for key, drive in sorted(blueprint.drives.items()):
        if drive.size is not None:
            filename = f"{key}.qcow2"
            path = os.path.join(drives_root, filename)
            create_hdd_image(path, drive.size)
            resolved_drives[key] = {
                "medium": drive.medium,
                "slot": drive.slot,
                "size": drive.size,
                "path": path,
            }
        elif drive.media is not None:
            payload = fetch_media(drive.media.item.name, home=home)
            resolved_drives[key] = {
                "medium": drive.medium,
                "slot": drive.slot,
                "media": drive.media.item.name,
                "path": payload,
            }

    state = {
        "id": machine_id,
        "blueprint": blueprint_name,
        "created": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "phase": "ready",
        "platform": blueprint.platform,
        "memory": blueprint.memory,
        "drives": resolved_drives,
        "boot": list(blueprint.boot),
        "name": blueprint.name,
        "description": blueprint.description,
        "scripts": dict(blueprint.scripts),
    }

    _write_state(machine_id, state, home)
    return machine_id


def _write_state(machine_id, state, home=None):
    path = _state_path(machine_id, home)
    part = path + ".part"
    with open(part, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(state, handle, indent=2)
        handle.write("\n")
    os.replace(part, path)


def load_machine_state(machine_id, home=None):
    """Read and return the machine's ``reliquary-machine.json``."""
    path = _state_path(machine_id, home)
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"machine state not found: {path}")
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def machine_drive_args(machine_id, home=None):
    """Build QEMU ``-drive`` arguments from a machine's state.

    Returns a list of tokens suitable for a QEMU command line
    (``-drive`` alternating with its value), with floppies first,
    hard disks next, and cdroms placed on the IDE bus after the
    last hard disk.
    """
    state = load_machine_state(machine_id, home)
    drives = state.get("drives", {})
    args = []

    floppies = [(k, v) for k, v in drives.items()
                 if v["medium"] == "floppy"]
    for _key, drive in sorted(floppies, key=lambda kv: kv[1]["slot"]):
        path = drive["path"]
        is_dir = os.path.isdir(path)
        source = (f"fat:floppy:rw:{path},format=raw,"
                  if is_dir else path + ",")
        args += ["-drive",
                 f"file={source}if=floppy,index={drive['slot']}"]

    hdds = [(k, v) for k, v in drives.items()
            if v["medium"] == "hdd"]
    for _key, drive in sorted(hdds, key=lambda kv: kv[1]["slot"]):
        path = drive["path"]
        is_dir = os.path.isdir(path)
        source = (f"fat:rw:{path},format=raw,"
                  if is_dir else path + ",")
        inferred = "" if is_dir else format_options(path)
        args += ["-drive",
                 f"file={source}{inferred}if=ide,index={drive['slot']}"]

    cdroms = [(k, v) for k, v in drives.items()
              if v["medium"] == "cdrom"]
    if cdroms:
        next_ide = max(
            (d["slot"] for k, d in drives.items() if d["medium"] == "hdd"),
            default=-1,
        ) + 1
        for ordinal, (_key, drive) in enumerate(
                sorted(cdroms, key=lambda kv: kv[1]["slot"])):
            path = drive["path"]
            index = next_ide + ordinal
            inferred = format_options(path)
            args += ["-drive",
                     f"file={path},{inferred}media=cdrom,if=ide,index={index}"]

    return args
