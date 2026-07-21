# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""The built-in library: copy-out seeding of shipped artifacts.

The library is a seed, not a resolution tier (planning/design/codex.md).
Blueprints, media definitions, and scripts ship inside the package
under ``reliquary/builtins/``; referencing one that does not yet
exist in the home copies it out as an ordinary user-owned file. A
file already present in the home is never overwritten — deleting a
copy is how it is refreshed.
"""

import collections.abc
import json
import os
import re
from importlib import resources

from .home import blueprints_dir, media_dir, scripts_dir
from .media import parse_definition, scan_media_definitions


def _builtins_root():
    """Return the packaged built-in library tree (a Traversable)."""
    return resources.files(__package__) / "builtins"


def _copy_out(source, destination):
    """Extract one builtin file, unless the destination exists.

    Returns whether the file was written. Uses exclusive creation
    so an existing user file is never overwritten, whatever it
    contains.
    """
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    try:
        with open(destination, "xb") as handle:
            handle.write(source.read_bytes())
    except FileExistsError:
        return False
    return True


def _referenced_media(blueprint_data):
    """Yield the media names a raw blueprint object references."""
    drives = blueprint_data.get("drives")
    if not isinstance(drives, collections.abc.Mapping):
        return
    for declaration in drives.values():
        if isinstance(declaration, str):
            yield declaration
        elif (isinstance(declaration, collections.abc.Mapping)
                and isinstance(declaration.get("media"), str)):
            yield declaration["media"]


def _referenced_scripts(blueprint_data):
    """Yield the script stems a raw blueprint object references."""
    scripts = blueprint_data.get("scripts")
    if not isinstance(scripts, collections.abc.Mapping):
        return
    for stem in scripts.values():
        if isinstance(stem, str):
            yield stem


def list_builtin_blueprints():
    """Yield the stem names of blueprints shipped in the built-in library."""
    root = _builtins_root() / "blueprints"
    if not root.is_dir():
        return
    for entry in sorted(root.iterdir(), key=lambda item: item.name):
        if entry.name.endswith(".json"):
            yield entry.name[:-5]


def seed_blueprint(name, home=None):
    """Seed ``blueprints/<name>.json`` from the built-in library.

    A home blueprint of that name already exists, or no builtin
    does: nothing happens. Otherwise the blueprint is copied out
    along with the media definitions and scripts it references
    (each obeying the never-overwrite rule), and True is returned.
    """
    destination = os.path.join(blueprints_dir(home), f"{name}.json")
    if os.path.exists(destination):
        return False
    source = _builtins_root() / "blueprints" / f"{name}.json"
    if not source.is_file():
        return False
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        # A malformed builtin still copies out; loading it reports
        # the real parse error against the user's file.
        data = {}
    if not _copy_out(source, destination):
        return False
    if isinstance(data, collections.abc.Mapping):
        for media_name in _referenced_media(data):
            seed_media(media_name, home=home)
        for stem in _referenced_scripts(data):
            seed_script(stem, home=home)
    return True


def seed_media(name, home=None):
    """Seed the built-in media definition defining item ``name``.

    Returns whether a definition file was copied out. A home
    definition already supplying the name, a home file already
    occupying the builtin's filename, or no builtin defining the
    name: nothing happens.
    """
    if scan_media_definitions(media_dir(home), name):
        return False
    root = _builtins_root() / "media"
    if not root.is_dir():
        return False
    for entry in sorted(root.iterdir(), key=lambda item: item.name):
        if not entry.name.endswith(".json"):
            continue
        try:
            definition = parse_definition(
                json.loads(entry.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, UnicodeDecodeError,
                ValueError, KeyError):
            continue
        if any(item.name == name for item in definition.items):
            destination = os.path.join(media_dir(home), entry.name)
            return _copy_out(entry, destination)
    return False


_INSERT_MEDIA = re.compile(r"^\s*insert\s+\S+\s+(\S+)\s*$", re.MULTILINE)


def _referenced_insert_media(script_text):
    """Yield the media names a script's ``insert`` statements use."""
    yield from _INSERT_MEDIA.findall(script_text)


def seed_script(stem, home=None):
    """Seed ``scripts/<stem>.rlqs`` from the built-in library.

    Returns whether the script file was copied out. The media
    definitions the script's ``insert`` statements reference come
    along (each obeying the never-overwrite rule), so a seeded
    script resolves its media without a live fetch first.
    """
    source = _builtins_root() / "scripts" / f"{stem}.rlqs"
    if not source.is_file():
        return False
    destination = os.path.join(scripts_dir(home), f"{stem}.rlqs")
    if not _copy_out(source, destination):
        return False
    try:
        text = source.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return True
    for media_name in _referenced_insert_media(text):
        seed_media(media_name, home=home)
    return True
