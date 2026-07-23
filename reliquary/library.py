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

from . import assets, jsonc
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


def _blueprint_meta(path):
    """Return ``{name, description, platform}`` for a blueprint, or None.

    A ``.rlqb`` is a blueprint by extension — an unparseable one still
    counts, identified by its stem. A legacy ``.json`` counts only when
    its top level declares ``platform``, so a same-extension media
    definition or notes file is not mistaken for one. ``name`` is the
    declared identity or ``None`` (identity then falls to the stem).
    """
    try:
        with open(path, encoding="utf-8") as handle:
            raw = jsonc.loads(handle.read())
    except (OSError, ValueError, UnicodeDecodeError):
        raw = None
    mapping = raw if isinstance(raw, collections.abc.Mapping) else None
    if not path.endswith(".rlqb") and (
            mapping is None or "platform" not in mapping):
        return None
    name = mapping.get("name") if mapping else None
    if not (isinstance(name, str) and name.strip()):
        name = None
    return {
        "name": name,
        "description": mapping.get("description") if mapping else None,
        "platform": mapping.get("platform") if mapping else None,
    }


def _blueprint_entries(source):
    """Map identity name -> (path, meta) for a source's blueprints.

    Applies the residency conflict guard: two blueprints resolving to
    one effective name is an error naming both.
    """
    entries = {}
    for path in source.candidate_files("blueprint"):
        meta = _blueprint_meta(path)
        if meta is None:
            continue
        name = meta["name"] or assets.stem(path)
        if name in entries:
            raise ValueError(
                f"two blueprint assets both resolve to the name "
                f"{name!r}:\n  {entries[name][0]}\n  {path}")
        entries[name] = (path, meta)
    return entries


def _blueprint_index(source):
    """Map identity name -> path for a source's blueprints (guarded)."""
    return {name: path
            for name, (path, _meta) in _blueprint_entries(source).items()}


def list_blueprints(context=None):
    """Return sorted ``[{name, path}]`` for the active source.

    Home mode lists the home's canonical ``blueprints/`` folder; dir
    mode (``--assets``) lists the project root. Unseeded codex entries
    are not listed — ``search_blueprints`` surfaces those.
    """
    source = assets.source_for(context)
    return [{"name": name, "path": path}
            for name, path in sorted(_blueprint_index(source).items())]


def _codex_blueprint_path(name):
    """Return the codex blueprint path for ``name`` (by stem), or None."""
    for ext in (".rlqb", ".json"):
        candidate = _builtins_root() / "blueprints" / f"{name}{ext}"
        if candidate.is_file():
            return os.fspath(candidate)
    return None


def locate_blueprint(name, context=None):
    """Resolve a blueprint by identity without seeding.

    Identity is the file's ``name`` field when declared, else its
    stem. Home mode falls back to reading the codex file directly (no
    copy) so a read-only ``check-script`` never writes; dir mode
    (``--assets``) is the sole source. Seeding on first reference is
    ``create_machine``'s job. Raises ``FileNotFoundError`` when nothing
    resolves.
    """
    source = assets.source_for(context)
    path = _blueprint_index(source).get(name)
    if path is None and source.seeds:
        path = _codex_blueprint_path(name)
    if path is None:
        raise FileNotFoundError(
            f"blueprint not found: {name}\n"
            f"expected under {source.describe('blueprint')}")
    return path


def _codex_blueprint_rows():
    """Map codex identity name -> (path, meta) for search."""
    rows = {}
    for name in list_builtin_blueprints():
        path = _codex_blueprint_path(name)
        meta = _blueprint_meta(path) if path else None
        rows[name] = (path, meta or {
            "name": None, "description": None, "platform": None})
    return rows


def search_blueprints(term, context=None):
    """Search the active asset source (and codex) with provenance.

    Each match is a dict: ``name`` (the identity — the selection key),
    ``description``, ``platform``, ``provenance``, and ``path``. In
    home mode provenance is ``yes`` (codex, not seeded), ``seeded``
    (codex copied into the home), or ``user`` (home-authored, no
    codex), and ``path`` is the home file (``None`` for an unseeded
    codex entry). In dir mode the codex is not a tier: every match is
    ``user`` with its project path. The term matches case-insensitively
    against name, description, and platform; empty matches everything.
    Results are ordered by name.
    """
    term_l = (term or "").lower()
    source = assets.source_for(context)
    present = _blueprint_entries(source)
    codex = _codex_blueprint_rows() if source.seeds else {}

    results = []
    for name in sorted(set(present) | set(codex)):
        if name in codex and name in present:
            provenance, (path, meta) = "seeded", present[name]
        elif name in codex:
            provenance, (_codex_path, meta) = "yes", codex[name]
            path = None
        else:
            provenance, (path, meta) = "user", present[name]
        results.append({
            "name": name,
            "description": meta.get("description"),
            "platform": meta.get("platform"),
            "provenance": provenance,
            "path": path,
        })
    if not term_l:
        return results

    def matches(row):
        hay = " ".join(
            str(value) for value in (
                row["name"], row["description"],
                row["platform"]) if value).lower()
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


def _script_index(source):
    """Map stem -> path for a source's scripts (guarded).

    Scripts carry no ``name`` field, so identity is always the stem.
    """
    return assets.index_by_name(
        source.candidate_files("script"), lambda _path: None, "script")


def list_scripts(context=None):
    """Return sorted ``[{name, path}]`` scripts for the active source.

    Home mode lists the home's canonical ``scripts/`` folder; dir mode
    (``--assets``) lists the project root. Unseeded codex scripts are
    not listed.
    """
    source = assets.source_for(context)
    return [{"name": stem, "path": path}
            for stem, path in sorted(_script_index(source).items())]


def locate_script(stem, context=None):
    """Return an existing ``.rlqs`` path without seeding.

    Resolves from the active asset source; home mode falls back to the
    codex file directly (no copy), dir mode is the sole source. Raises
    ``FileNotFoundError`` when nothing resolves — ``check-script`` uses
    this so a check never writes.
    """
    source = assets.source_for(context)
    path = _script_index(source).get(stem)
    if path is None and source.seeds:
        candidate = _builtins_root() / "scripts" / f"{stem}.rlqs"
        if candidate.is_file():
            path = os.fspath(candidate)
    if path is None:
        raise FileNotFoundError(
            f"script not found: {stem}.rlqs\n"
            f"expected under {source.describe('script')}")
    return path
