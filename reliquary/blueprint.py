# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Blueprint file-authoring conveniences.

Parsing and validating a composed ``.rlqb`` blueprint lives in
``document.py``; this module is the thin file-authoring surface the CLI
drives — scaffolding a new blueprint and removing a machineless one.
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

    data = {
        "machines": [
            {
                "name": name,
                "platform": platform,
                "memory": 16 if platform == "dos" else 64,
                "drives": {"hdd0": "blank-256m"},
            }
        ],
        "media": [
            {"name": "blank-256m", "materialize": "new", "size": "256M"}
        ],
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("// Machine blueprint for " + name + "\n")
        json.dump(data, handle, indent=2)
        handle.write("\n")
    return path


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
