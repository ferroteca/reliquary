# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Authoring the files a user owns: writing them, and removing them.

The counterpart of `assets.py`, which resolves and reads what this
writes. Four verbs over the two authored kinds — scaffold a
blueprint, declare a media for a file already on disk, and remove a
blueprint or a script.

**Both removals refuse while something still refers to the file**,
and that shared discipline is why the two kinds sit together rather
than a shared helper: a blueprint is refused while machines of it
exist, a script while blueprints reference it, and the two answer
from entirely different places — the machine list, and every
blueprint in the source parsed for its `scripts` map. What they have
in common is the order of the questions (who refers to this, does
the file exist, remove it), which is a shape to keep aligned by
sitting side by side, not code to factor.

Parsing and validating a composed `.rlqb` is `document.py`'s;
nothing here interprets what it writes beyond the one parse that
keeps `add_media` from leaving an unloadable file behind.
"""

import json
import os

from .acquire import sha256
from .assets import source_for, stem
from .document import parse_document
from .errors import PreflightError, ReliquaryError
from .home import blueprints_dir, scripts_dir
from .json5reader import loads
from .library import referenced_scripts
from .machine_state import list_machines


def new_blueprint(name, *, platform="dos", context=None):
    """Scaffold a minimal composed ``blueprints/<name>.rlqb``.

    Writes a one-machine composed blueprint with a blank hard disk, so
    new machines don't begin from a blank editor. Returns the path;
    raises :class:`PreflightError` if the blueprint already exists.
    """
    path = os.path.join(blueprints_dir(context), f"{name}.rlqb")
    if os.path.exists(path):
        raise PreflightError(f"blueprint already exists: {path}",
            rule_id="blueprint.already-exists")

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

    Raises :class:`PreflightError` if the file is not there, and again
    if the blueprint already exists — an existing declaration is
    edited, never silently rewritten.
    """

    source = os.path.abspath(os.fspath(path))
    if not os.path.isfile(source):
        raise PreflightError(f"no such file: {source}",
            rule_id="media.file-missing")

    destination = os.path.join(blueprints_dir(context), f"{name}.rlqb")
    if os.path.exists(destination):
        raise PreflightError(
            f"blueprint already exists: {destination}\n"
            f"edit it to declare {name!r}, or choose another name",
            rule_id="blueprint.already-exists")

    # Forward slashes read the same on every host and need no JSON
    # escaping; the locator's drive-letter exemption accepts 'D:/…'.
    spec = {
        "type": "media",
        "name": name,
        "location": source.replace("\\", "/"),
        "sha256": sha256(source),
    }
    # Parse before writing, so a name the charter refuses fails here
    # rather than leaving an unloadable file behind.
    parse_document([spec])

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

    machines = list_machines(context, blueprint=name)
    if machines:
        ids = ", ".join(machine["id"] for machine in machines)
        raise PreflightError(
            f"blueprint {name!r} still has "
            f"{len(machines)} machine(s):\n"
            f"  {ids}\n"
            "destroy them first, then delete the blueprint",
            rule_id="blueprint.has-machines")

    path = None
    for extension in (".rlqb", ".json"):
        candidate = os.path.join(
            blueprints_dir(context), f"{name}{extension}")
        if os.path.isfile(candidate):
            path = candidate
            break
    if path is None:
        raise PreflightError(
            f"blueprint not found: {name}.rlqb\n"
            f"expected under {blueprints_dir(context)}",
            rule_id="blueprint.unknown")
    os.remove(path)
    return path


def delete_script(name, *, context=None):
    """Remove the home script file for ``name``.

    Fails closed while any blueprint refers to the script.
    Never deletes package codex files — only a file under
    ``scripts/``. Returns the removed path.
    """

    # Check for blueprint references first.
    source = source_for(context)
    blueprints = []
    for path in source.candidate_files("blueprint"):
        try:
            with open(path, encoding="utf-8") as handle:
                data = loads(handle.read())
        except (OSError, ReliquaryError):
            continue

        if name in referenced_scripts(data):
            blueprints.append(stem(path))

    if blueprints:
        ids = ", ".join(sorted(blueprints))
        raise PreflightError(
            f"script {name!r} still has "
            f"{len(blueprints)} blueprint(s):\n"
            f"  {ids}\n"
            "edit them to remove the reference first, then delete the script",
            rule_id="script.has-blueprints")

    path = os.path.join(scripts_dir(context), f"{name}.rlqs")
    if not os.path.isfile(path):
        raise PreflightError(
            f"script not found: {name}.rlqs\n"
            f"expected under {scripts_dir(context)}",
            rule_id="script.unknown")

    os.remove(path)
    return path
