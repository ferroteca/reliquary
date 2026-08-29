# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The built-in library: copies shipped files out on request.

The built-in library (the codex) is a seed you copy files from, not
one of the places a blueprint or script lookup searches
(docs/spec/codex.md). Blueprints and scripts ship inside the package
under ``reliquary/codex/``; seeding one that isn't already present
copies it into the ``blueprints`` / ``scripts`` directory as an
ordinary, user-owned file. A file already present there is never
overwritten — to refresh it from the shipped version, delete the
copy and seed it again.

Copying out only happens when it is explicitly requested — through
``seed_blueprint`` / ``seed_script``, which only the CLI calls (D87)
— and it writes into whichever directory is currently assigned, so
seeding a first draft straight into a project's own tree is the
normal way to do it. A failed lookup never triggers a copy on its
own: a lookup that finds nothing just reports that, and the codex
only reaches a project's tree because someone asked for a blueprint
or script by name (P4, D88).
"""

import collections.abc
import os
import re
from importlib import resources

from . import assets, document, json5reader
from .errors import PreflightError, StaticError
from .home import blueprints_dir, scripts_dir


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


def _machine_objects(blueprint_data):
    """Yield the machine specs in a raw composed document.

    Called "raw" because this runs before real parsing — search and
    seeding both read files that might not even be valid. The
    document's root is either an array of specs, or, as a shorthand
    for an array of one, a single spec object by itself. A machine is
    any spec whose ``"type"`` field is ``"machine"``.
    """
    if isinstance(blueprint_data, collections.abc.Mapping):
        entries = [blueprint_data]
    elif isinstance(blueprint_data, list):
        entries = blueprint_data
    else:
        return
    for spec in entries:
        if (isinstance(spec, collections.abc.Mapping)
                and spec.get("type") == "machine"):
            yield spec


def referenced_scripts(blueprint_data):
    """Yield the script stems a composed blueprint's machines reference."""
    for machine in _machine_objects(blueprint_data):
        scripts = machine.get("scripts")
        if isinstance(scripts, collections.abc.Mapping):
            for stem in scripts.values():
                if isinstance(stem, str):
                    yield stem


def list_builtin_blueprints():
    """Yield the stem names of blueprints shipped in the built-in library."""
    try:
        data = json5reader.loads((_builtins_root() / "codex.json").read_text(encoding="utf-8"))
        blueprints = data.get("blueprints", {})
        for name in sorted(blueprints.keys()):
            yield name
        return
    except (FileNotFoundError, StaticError):
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


def _blueprint_meta(path):
    """Return ``{name, description, platform}`` for a blueprint, or None.

    Any file with a ``.rlqb`` extension counts as a blueprint — even
    one that fails to parse still counts, identified by its filename
    stem. A legacy ``.json`` file counts only when its top level
    declares a ``platform`` field, so a same-extension media
    definition or notes file next to it isn't mistaken for a
    blueprint. ``name`` is the blueprint's own declared name, or
    ``None`` if it declares none (its stem is used as the name
    instead).
    """
    try:
        with open(path, encoding="utf-8") as handle:
            raw = json5reader.loads(handle.read())
    except (OSError, StaticError, UnicodeDecodeError):
        raw = None
    machine = next(_machine_objects(raw), None)
    if not path.endswith(".rlqb") and machine is None:
        return None
    name = machine.get("name") if machine else None
    if not (isinstance(name, str) and name.strip()):
        name = None
    return {
        "name": name,
        "description": machine.get("description") if machine else None,
        "platform": machine.get("platform") if machine else None,
    }


def _blueprint_entries(source):
    """Map each blueprint's name to its (path, meta) for one source.

    Checks for name collisions: if two different blueprint files
    resolve to the same effective name, this raises an error naming
    both paths.
    """
    entries = {}
    for path in source.candidate_files("blueprint"):
        meta = _blueprint_meta(path)
        if meta is None:
            continue
        name = meta["name"] or assets.stem(path)
        if name in entries:
            raise StaticError(
                f"two blueprint assets both resolve to the name "
                f"{name!r}:\n  {entries[name][0]}\n  {path}",
                rule_id="name.asset-collision")
        entries[name] = (path, meta)
    return entries


def _blueprint_index(source):
    """Map each blueprint's name to its path for one source, using the
    same name-collision check as `_blueprint_entries`."""
    return {name: path
            for name, (path, _meta) in _blueprint_entries(source).items()}


def list_blueprints(context=None):
    """Return sorted ``[{name, path, description, platform}]`` for
    the blueprints directory.

    Lists only the user's own blueprints directory: the shipped codex
    library has its own separate listing function, ``list_codex``,
    and no single listing shows both together (D88). ``description``
    and ``platform`` come straight from what the blueprint file
    itself declares, and are ``None`` when it declares neither —
    they're included here so the ``--json`` output carries the same
    information the human-readable listing shows (D97; P6).
    """
    source = assets.source_for(context)
    return [{"name": name, "path": path,
             "description": meta.get("description"),
             "platform": meta.get("platform")}
            for name, (path, meta) in sorted(
                _blueprint_entries(source).items())]


def codex_blueprint_available(name):
    """Whether the shipped library holds a blueprint of this name.

    Just answers yes or no — nothing is read, copied, or resolved. It
    exists so that when a lookup fails, the error message can tell
    the user to seed this blueprint from the codex, without the
    lookup itself falling back to the codex (D88, P11).
    """
    return _codex_blueprint_path(name) is not None


def _codex_blueprint_path(name):
    """Return the codex blueprint path for ``name`` (by stem), or None."""
    for ext in (".rlqb", ".json"):
        candidate = _builtins_root() / "blueprints" / f"{name}{ext}"
        if candidate.is_file():
            return os.fspath(candidate)
    return None


def locate_blueprint(name, context=None):
    """Resolve a blueprint by identity without seeding.

    A blueprint's identity is its declared ``name`` field, or its
    filename stem when it declares none. The blueprints directory is
    the only place searched — nothing falls back to the codex, which
    only reaches a project's tree when ``seed_blueprint`` is asked to
    copy it there (D88). Raises :class:`PreflightError` when nothing
    matches; if the codex has a blueprint of that name, the error
    says so, because removing the automatic fallback should leave the
    user with instructions, not just silence (P11).
    """
    source = assets.source_for(context)
    path = _blueprint_index(source).get(name)
    if path is None:
        detail = ""
        if _codex_blueprint_path(name) is not None:
            detail = (f"\nthe codex has one: "
                      f"rlq seed-blueprint {name}")
        raise PreflightError(
            f"blueprint not found: {name}\n"
            f"expected under {source.describe('blueprint')}{detail}",
            rule_id="blueprint.unknown")
    return path


def _codex_blueprint_rows():
    """Map codex identity name -> (path, meta) for the codex listing."""
    rows = {}
    for name in list_builtin_blueprints():
        path = _codex_blueprint_path(name)
        meta = _blueprint_meta(path) if path else None
        rows[name] = (path, meta or {
            "name": None, "description": None, "platform": None})
    return rows


def list_codex():
    """Return sorted ``[{name, description}]`` for the shipped library.

    The codex's own listing function, and the only one that reads it:
    ``list_blueprints`` never reports a codex entry and this never
    reports a user blueprint, so which command you ran tells you
    which set you're looking at (D88). It takes no ``context``
    argument, because the shipped library is the same no matter where
    the user's directories point, and no search term — filtering is
    left to the shell or the caller.

    ``description`` is included in the record for the ``--json``
    output; the CLI prints it below the blueprint's name, indented
    and wrapped (D97) — matching D88's decision not to show it as its
    own column.
    """
    return [{"name": name, "description": meta.get("description")}
            for name, (_path, meta) in sorted(
                _codex_blueprint_rows().items())]


def seed_blueprint(name, context=None, *, only=False):
    """Seed ``<blueprints>/<name>.rlqb`` from the built-in library.

    If a blueprint of that name already exists there, or the
    built-in library has none, nothing happens. Otherwise the
    blueprint is copied out along with the scripts it references
    (each following the never-overwrite rule), and True is returned.
    ``only=True`` copies just the one blueprint file, not the scripts
    it references too.

    The target is whichever ``blueprints`` directory is currently
    assigned — a project tree or the home directory alike. Seeding is
    the only way the codex ever reaches a project's tree (D88):
    calling this has already named the codex as the source for a
    first draft, which is exactly what the codex is for — copy it,
    then commit the copy.
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
        data = json5reader.loads(text)
    except (StaticError, UnicodeDecodeError):
        # A malformed builtin still copies out; loading it reports
        # the real parse error against the user's file.
        data = []

    os.makedirs(blueprints_dir(context), exist_ok=True)
    if not _copy_out(source, destination):
        return False

    if not only:
        # Media definitions live inside the composed blueprint file
        # itself; only the scripts its machines reference are
        # separate files that need seeding.
        for stem in referenced_scripts(data):
            seed_script(stem, context=context)
    return True


def seed_script(stem, context=None, *, only=False):
    """Seed ``<scripts>/<stem>.rlqs`` from the built-in library.

    Returns whether the script file was copied out. A script no
    longer has anything else that needs seeding alongside it — the
    media a script's ``insert`` statements reference live inside the
    composed blueprint that named the script, not in separate files.
    ``only`` is accepted (and ignored) just so this function has the
    same shape as ``seed_blueprint``.
    """
    source = _builtins_root() / "scripts" / f"{stem}.rlqs"
    if not source.is_file():
        return False
    os.makedirs(scripts_dir(context), exist_ok=True)
    destination = os.path.join(scripts_dir(context), f"{stem}.rlqs")
    return _copy_out(source, destination)


def _script_index(source):
    """Map each script's filename stem to its path for one source.

    Scripts carry no ``name`` field, so identity is always the stem.
    """
    return assets.index_by_name(
        source.candidate_files("script"), lambda _path: None, "script")


def list_scripts(context=None):
    """Return sorted ``[{name, path}]`` for the scripts directory.

    Unseeded codex scripts are not listed.
    """
    source = assets.source_for(context)
    return [{"name": stem, "path": path}
            for stem, path in sorted(_script_index(source).items())]


def locate_script(stem, context=None):
    """Return an existing ``.rlqs`` path without seeding.

    Resolves only from the scripts directory — nothing falls back to
    the codex (D88). Raises :class:`PreflightError` when nothing
    matches; if the codex ships that script, the error says so.
    Since seeding a blueprint also seeds the scripts it references,
    the usual fix is to seed the blueprint that names this script.
    """
    source = assets.source_for(context)
    path = _script_index(source).get(stem)
    if path is None:
        detail = ""
        if (_builtins_root() / "scripts" / f"{stem}.rlqs").is_file():
            detail = (f"\nthe codex has one: "
                      f"rlq seed-script {stem}")
        raise PreflightError(
            f"script not found: {stem}.rlqs\n"
            f"expected under {source.describe('script')}{detail}",
            rule_id="script.unknown")
    return path
