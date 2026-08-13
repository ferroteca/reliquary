# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The built-in library: copy-out seeding of shipped artifacts.

The library is a seed, not a resolution tier (docs/spec/codex.md).
Blueprints and scripts ship inside the package under
``reliquary/codex/``; referencing one that does not yet exist copies
it out into the ``blueprints`` / ``scripts`` directory as an
ordinary user-owned file. A file already present there is never
overwritten — deleting a copy is how it is refreshed.

Copy-out happens **on request only** — ``seed_blueprint`` /
``seed_script``, reached from the CLI alone (D87) — and writes to the
assigned directory wherever it is, so seeding a first draft straight
into a project tree is the ordinary way to do it. Nothing is ever
seeded by a resolution miss: a miss is a miss, and the codex reaches
a tree because someone asked for it by name (P4, D88).
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

    Raw because this runs before parsing — search and seeding read
    files that may not be valid. The root is an array of specs, or a
    lone spec object as sugar for the array of one; a machine is the
    spec that declares ``"type": "machine"``.
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

    A ``.rlqb`` is a blueprint by extension — an unparseable one still
    counts, identified by its stem. A legacy ``.json`` counts only when
    its top level declares ``platform``, so a same-extension media
    definition or notes file is not mistaken for one. ``name`` is the
    declared identity or ``None`` (identity then falls to the stem).
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
            raise StaticError(
                f"two blueprint assets both resolve to the name "
                f"{name!r}:\n  {entries[name][0]}\n  {path}",
                rule_id="name.asset-collision")
        entries[name] = (path, meta)
    return entries


def _blueprint_index(source):
    """Map identity name -> path for a source's blueprints (guarded)."""
    return {name: path
            for name, (path, _meta) in _blueprint_entries(source).items()}


def list_blueprints(context=None):
    """Return sorted ``[{name, path, description, platform}]`` for
    the blueprints directory.

    Yours alone: the codex is a separate set with its own verb
    (``list_codex``), and no listing spans the two (D88).
    ``description`` and ``platform`` are the blueprint's own declared
    words, ``None`` where it declares none — in the record so
    ``--json`` carries what the human listing shows (D97; P6).
    """
    source = assets.source_for(context)
    return [{"name": name, "path": path,
             "description": meta.get("description"),
             "platform": meta.get("platform")}
            for name, (path, meta) in sorted(
                _blueprint_entries(source).items())]


def codex_blueprint_available(name):
    """Whether the shipped library holds a blueprint of this name.

    A question, not a resolution: nothing is read, copied or resolved.
    It exists so a refusal can name the fix — the codex has this one,
    seed it — without the resolver gaining a fallback (D88, P11).
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

    Identity is the file's ``name`` field when declared, else its
    stem. The directory is the sole source: nothing falls back to the
    codex, which reaches a tree only when ``seed_blueprint`` is asked
    to put it there (D88). Raises :class:`PreflightError` when nothing
    resolves — naming the fix where the codex has that name, since a
    deleted fallback should leave an instruction rather than a silence
    (P11).
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

    The codex's own verb, and the only one that reads it: no listing
    of yours reports a codex entry and this reports nothing of yours,
    so **which command you ran is the provenance** (D88). It takes no
    context, the library being the same wherever your directories
    point, and no term — filtering is the shell's job or the
    caller's.

    ``description`` rides the record for ``--json``; the CLI prints
    it beneath its name, indented and wrapped (D97) — the column
    D88 refused stays refused.
    """
    return [{"name": name, "description": meta.get("description")}
            for name, (_path, meta) in sorted(
                _codex_blueprint_rows().items())]


def seed_blueprint(name, context=None, *, only=False):
    """Seed ``<blueprints>/<name>.rlqb`` from the built-in library.

    A blueprint of that name already exists there, or no builtin
    does: nothing happens. Otherwise the blueprint is copied out
    along with the scripts it references (each obeying the
    never-overwrite rule), and True is returned. ``only=True`` copies
    just the single blueprint file, not its closure.

    The target is the assigned ``blueprints`` directory, project tree
    or home alike. Seeding is the only way the codex reaches a tree
    (D88): a caller that asked for a first draft has named the codex
    as its source, which is exactly the use the codex is for — copy
    it, then commit the copy.
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
        # Media travel inside the composed blueprint; only the scripts
        # its machines reference are separate files to seed.
        for stem in referenced_scripts(data):
            seed_script(stem, context=context)
    return True


def seed_script(stem, context=None, *, only=False):
    """Seed ``<scripts>/<stem>.rlqs`` from the built-in library.

    Returns whether the script file was copied out. Scripts have no
    seed closure of their own now — the media a script's ``insert``
    statements reference live inside the composed blueprint that named
    the script. ``only`` is accepted for a uniform seed surface.
    """
    source = _builtins_root() / "scripts" / f"{stem}.rlqs"
    if not source.is_file():
        return False
    os.makedirs(scripts_dir(context), exist_ok=True)
    destination = os.path.join(scripts_dir(context), f"{stem}.rlqs")
    return _copy_out(source, destination)


def _script_index(source):
    """Map stem -> path for a source's scripts (guarded).

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

    Resolves from the scripts directory, which is the sole source:
    nothing falls back to the codex (D88). Raises
    :class:`PreflightError` when nothing resolves, naming the fix
    where the codex ships that script — a blueprint's own
    ``seed-blueprint`` brings its scripts too, so the usual answer is
    to seed the blueprint that names it.
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
