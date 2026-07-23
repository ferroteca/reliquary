# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""The built-in library: copy-out seeding of shipped artifacts.

The library is a seed, not a resolution tier (planning/design/codex.md).
Blueprints, media definitions, and scripts ship inside the package
under ``reliquary/codex/``; referencing one that does not yet
exist in the home copies it out as an ordinary user-owned file. A
file already present in the home is never overwritten — deleting a
copy is how it is refreshed.
"""

import collections.abc
import os
import re
from importlib import resources

from . import jsonc
from .home import blueprints_dir, media_dir, scripts_dir
from .media import parse_definition, scan_media_definitions


def _builtins_root():
    """Return the packaged built-in library tree (a Traversable)."""
    return resources.files(__package__) / "codex"


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
    try:
        data = jsonc.loads((_builtins_root() / "codex.json").read_text(encoding="utf-8"))
        blueprints = data.get("blueprints", {})
        for name in sorted(blueprints.keys()):
            yield name
        return
    except (FileNotFoundError, ValueError):
        pass

    # Fallback to directory scan
    root = _builtins_root() / "blueprints"
    if not root.is_dir():
        return
    for entry in sorted(root.iterdir(), key=lambda item: item.name):
        if entry.name.endswith(".rlqb"):
            yield entry.name[:-5]
        elif entry.name.endswith(".json"):
            yield entry.name[:-5]


def list_builtin_media():
    """Yield item names defined by the built-in media library."""
    root = _builtins_root() / "media"
    if not root.is_dir():
        return
    names = set()
    for entry in sorted(root.iterdir(), key=lambda item: item.name):
        if not (entry.name.endswith(".rlqm")
                or entry.name.endswith(".json")):
            continue
        try:
            definition = parse_definition(
                jsonc.loads(entry.read_text(encoding="utf-8")))
        except (ValueError, UnicodeDecodeError, KeyError):
            continue
        for item in definition.items:
            names.add(item.name)
    for name in sorted(names):
        yield name


def _blueprint_fields_from_text(text):
    """Extract (display_name, description, platform), or None."""
    try:
        raw = jsonc.loads(text)
    except ValueError:
        return None
    if (not isinstance(raw, collections.abc.Mapping)
            or "platform" not in raw):
        return None
    return {
        "display_name": raw.get("name"),
        "description": raw.get("description"),
        "platform": raw.get("platform"),
    }


def _home_blueprint_index(context=None):
    """Map stem -> (path, fields) for blueprint files under blueprints/."""
    root = blueprints_dir(context)
    found = {}
    if not os.path.isdir(root):
        return found
    for dirpath, _dirs, files in os.walk(root):
        for entry in sorted(files):
            if entry.endswith(".rlqb") or entry.endswith(".json"):
                stem = entry.rsplit(".", 1)[0]
            else:
                continue
            path = os.path.join(dirpath, entry)
            try:
                with open(path, encoding="utf-8") as handle:
                    fields = _blueprint_fields_from_text(handle.read())
            except OSError:
                continue
            if fields is not None:
                found.setdefault(stem, (path, fields))
    return found


def _codex_blueprint_index():
    """Map stem -> discovery fields for codex blueprints."""
    result = {}
    for name in list_builtin_blueprints():
        source = _builtins_root() / "blueprints" / f"{name}.rlqb"
        if not source.is_file():
            source = _builtins_root() / "blueprints" / f"{name}.json"
        fields = None
        if source.is_file():
            try:
                fields = _blueprint_fields_from_text(
                    source.read_text(encoding="utf-8"))
            except (UnicodeDecodeError, ValueError):
                fields = None
        result[name] = fields or {
            "display_name": None, "description": None, "platform": None}
    return result


def search_blueprints(term, context=None):
    """Search codex and home blueprints, returning matches with provenance.

    Each match is a dict: ``name`` (the stem — the selection key),
    ``display_name`` (the blueprint's ``name`` field), ``description``,
    ``platform``, ``provenance`` (``yes`` = built-in and not seeded,
    ``seeded`` = built-in copied into the home, ``user`` = home-authored
    with no built-in), and ``path`` (the home file, or ``None`` for an
    unseeded built-in). The term matches case-insensitively against the
    stem, display name, description, and platform; an empty term matches
    everything. Results are ordered by stem.
    """
    term_l = (term or "").lower()
    home = _home_blueprint_index(context)
    codex = _codex_blueprint_index()
    results = []
    for stem in sorted(set(home) | set(codex)):
        if stem in codex and stem in home:
            provenance, (path, fields) = "seeded", home[stem]
        elif stem in codex:
            provenance, path, fields = "yes", None, codex[stem]
        else:
            provenance, (path, fields) = "user", home[stem]
        results.append({
            "name": stem,
            "display_name": fields.get("display_name"),
            "description": fields.get("description"),
            "platform": fields.get("platform"),
            "provenance": provenance,
            "path": path,
        })
    if not term_l:
        return results

    def matches(row):
        hay = " ".join(
            str(value) for value in (
                row["name"], row["display_name"],
                row["description"], row["platform"]) if value).lower()
        return term_l in hay

    return [row for row in results if matches(row)]


def seed_blueprint(name, context=None, *, only=False):
    """Seed ``blueprints/<name>.rlqb`` from the built-in library.

    A home blueprint of that name already exists, or no builtin
    does: nothing happens. Otherwise the blueprint is copied out
    along with the media definitions and scripts it references
    (each obeying the never-overwrite rule), and True is returned.
    ``only=True`` copies just the single blueprint file, not its
    closure.
    """
    source = _builtins_root() / "blueprints" / f"{name}.rlqb"
    if not source.is_file():
        source = _builtins_root() / "blueprints" / f"{name}.json"
        if not source.is_file():
            return False

    # Check for existing destination before creating directory
    destination = os.path.join(blueprints_dir(context), source.name)
    if os.path.exists(destination):
        return False

    # Check for legacy home .json IF seeding a .rlqb
    if source.name.endswith(".rlqb"):
        if os.path.exists(
                os.path.join(blueprints_dir(context), f"{name}.json")):
            return False

    # Pre-read to catch referenced media/scripts
    try:
        text = source.read_text(encoding="utf-8")
        data = jsonc.loads(text)
    except (ValueError, UnicodeDecodeError):
        # A malformed builtin still copies out; loading it reports
        # the real parse error against the user's file.
        data = {}

    os.makedirs(blueprints_dir(context), exist_ok=True)
    if not _copy_out(source, destination):
        return False

    if not only and isinstance(data, collections.abc.Mapping):
        # Resolve everything relative to the home this seed is into
        for media_name in _referenced_media(data):
            seed_media(media_name, context=context)
        for stem in _referenced_scripts(data):
            seed_script(stem, context=context)
    return True


def seed_media(name, context=None, *, only=False):
    """Seed the built-in media definition defining item ``name``.

    Returns whether a definition file was copied out. A home
    definition already supplying the name, a home file already
    occupying the builtin's filename, or no builtin defining the
    name: nothing happens. ``only`` is accepted for a uniform seed
    surface but inert — a media definition has no closure.
    """
    if scan_media_definitions(media_dir(context), name):
        return False
    root = _builtins_root() / "media"
    if not root.is_dir():
        return False
    for entry in sorted(root.iterdir(), key=lambda item: item.name):
        if not (entry.name.endswith(".rlqm") or entry.name.endswith(".json")):
            continue
        try:
            definition = parse_definition(
                jsonc.loads(entry.read_text(encoding="utf-8")))
        except (ValueError, UnicodeDecodeError, KeyError):
            continue
        if any(item.name == name for item in definition.items):
            stem = entry.name.rsplit(".", 1)[0]
            os.makedirs(media_dir(context), exist_ok=True)
            destination = os.path.join(media_dir(context), f"{stem}.rlqm")
            return _copy_out(entry, destination)
    return False


# A deliberate text scan, not a parse: seeding must work on a file
# the parser may reject. Only the `@name` form names an item a
# definition can be seeded for -- `$key` is a property reference,
# resolved per run once binding exists.
_INSERT_MEDIA = re.compile(r"^\s*insert\s+\S+\s+@(\S+)", re.MULTILINE)


def _referenced_insert_media(script_text):
    """Yield the media names a script's ``insert`` statements use."""
    yield from _INSERT_MEDIA.findall(script_text)


def seed_script(stem, context=None, *, only=False):
    """Seed ``scripts/<stem>.rlqs`` from the built-in library.

    Returns whether the script file was copied out. The media
    definitions the script's ``insert`` statements reference come
    along (each obeying the never-overwrite rule), so a seeded
    script resolves its media without a live fetch first.
    ``only=True`` copies just the script file, not its media.
    """
    source = _builtins_root() / "scripts" / f"{stem}.rlqs"
    if not source.is_file():
        return False
    os.makedirs(scripts_dir(context), exist_ok=True)
    destination = os.path.join(scripts_dir(context), f"{stem}.rlqs")
    if not _copy_out(source, destination):
        return False
    if only:
        return True
    try:
        text = source.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return True
    for media_name in _referenced_insert_media(text):
        seed_media(media_name, context=context)
    return True


def locate_script(stem, context=None):
    """Return an existing ``.rlqs`` path without seeding.

    Prefers ``scripts/<stem>.rlqs`` under the home; otherwise the
    matching builtin. Raises ``FileNotFoundError`` when neither
    exists — ``check-script`` uses this so a check never writes.
    """
    destination = os.path.join(scripts_dir(context), f"{stem}.rlqs")
    if os.path.isfile(destination):
        return destination
    source = _builtins_root() / "scripts" / f"{stem}.rlqs"
    if source.is_file():
        return os.fspath(source)
    raise FileNotFoundError(
        f"script not found: {stem}.rlqs\n"
        f"expected under {scripts_dir(context)}")


def locate_blueprint(name, context=None):
    """Return an existing blueprint path without seeding."""
    for ext in [".rlqb", ".json"]:
        path = os.path.join(blueprints_dir(context), f"{name}{ext}")
        if os.path.isfile(path):
            return path

    source = _builtins_root() / "blueprints" / f"{name}.rlqb"
    if source.is_file():
        return os.fspath(source)
    source = _builtins_root() / "blueprints" / f"{name}.json"
    if source.is_file():
        return os.fspath(source)

    raise FileNotFoundError(
        f"blueprint not found: {name}.rlqb\n"
        f"expected under {blueprints_dir(context)}")
