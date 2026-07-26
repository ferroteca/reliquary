# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Blueprint file-authoring conveniences.

Parsing and validating a composed ``.rlqb`` blueprint lives in
``document.py``; this module is the thin file-authoring surface the CLI
drives — scaffolding a new blueprint, writing a media spec for a file
already on disk, and removing a machineless blueprint.
"""

import json
import os


def new_blueprint(name, *, platform="dos", context=None):
    """Scaffold a minimal composed ``blueprints/<name>.rlqb``.

    Writes a one-machine composed blueprint with a blank hard disk, so
    new machines don't begin from a blank editor. Returns the path;
    raises ``FileExistsError`` if the blueprint already exists.
    """
    from .home import blueprints_dir
    path = os.path.join(blueprints_dir(context), f"{name}.rlqb")
    if os.path.exists(path):
        raise FileExistsError(f"blueprint already exists: {path}")

    data = [
        {
            "type": "machine",
            "name": name,
            "platform": platform,
            "memory": 16 if platform == "dos" else 64,
            "drives": {"hdd0": "blank-256m"},
        },
        {
            "type": "media",
            "name": "blank-256m",
            "materialize": "new",
            "size": "256M",
        },
    ]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("// Machine blueprint for " + name + "\n")
        json.dump(data, handle, indent=2)
        handle.write("\n")
    return path


def add_media(name, path, *, context=None):
    """Write a media spec for a file already on disk. Returns the path.

    The file stays where it is: what this authors is the *declaration*
    a blueprint was missing, with the one field a person should never
    have to produce by hand — the ``sha256`` — computed from the file.
    The result is an ordinary ``blueprints/<name>.rlqb`` the user owns
    and can edit, not a cache entry (D41).

    Raises ``FileNotFoundError`` if the file is not there, and
    ``FileExistsError`` if the blueprint already exists — an existing
    declaration is edited, never silently rewritten.
    """
    from . import document
    from .acquire import _sha256
    from .home import blueprints_dir

    source = os.path.abspath(os.fspath(path))
    if not os.path.isfile(source):
        raise FileNotFoundError(f"no such file: {source}")

    destination = os.path.join(blueprints_dir(context), f"{name}.rlqb")
    if os.path.exists(destination):
        raise FileExistsError(
            f"blueprint already exists: {destination}\n"
            f"edit it to declare {name!r}, or choose another name")

    # Forward slashes read the same on every host and need no JSON
    # escaping; the locator's drive-letter exemption accepts 'D:/…'.
    spec = {
        "type": "media",
        "name": name,
        "location": source.replace("\\", "/"),
        "sha256": _sha256(source),
    }
    # Parse before writing, so a name the charter refuses fails here
    # rather than leaving an unloadable file behind.
    document.parse_document([spec])

    os.makedirs(os.path.dirname(destination), exist_ok=True)
    with open(destination, "w", encoding="utf-8") as handle:
        handle.write(f"// Media {name} — supplied locally\n")
        json.dump([spec], handle, indent=2)
        handle.write("\n")
    return destination


def delete_blueprint(name, *, context=None):
    """Remove the home blueprint file for ``name``.

    Fails closed while any machine of the blueprint exists, naming their
    ids. Never deletes package codex files — only a file under
    ``blueprints/``. Returns the removed path.
    """
    from .home import blueprints_dir
    from .machines import list_machines

    machines = list_machines(context, blueprint=name)
    if machines:
        ids = ", ".join(machine["id"] for machine in machines)
        raise RuntimeError(
            f"blueprint {name!r} still has "
            f"{len(machines)} machine(s):\n"
            f"  {ids}\n"
            "destroy them first, then delete the blueprint")

    path = None
    for extension in (".rlqb", ".json"):
        candidate = os.path.join(
            blueprints_dir(context), f"{name}{extension}")
        if os.path.isfile(candidate):
            path = candidate
            break
    if path is None:
        raise FileNotFoundError(
            f"blueprint not found: {name}.rlqb\n"
            f"expected under {blueprints_dir(context)}")
    os.remove(path)
    return path
