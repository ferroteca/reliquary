# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Authored-asset residency: the resolution source seam.

Authored assets — machine blueprints (``.rlqb``, which includes
media) and scripts (``.rlqs``) — are found by looking in one
directory per kind: blueprints in the ``blueprints`` directory,
scripts in the ``scripts`` directory. Both directories can be
relocated (see ``home.py``), using the same six-slot placement model
that decides where everything else Reliquary reads and writes lives
— there's no separate setting just for asset location. That's what
made the old asset-root setting unnecessary: it used to exist only
because there was no way to name the ``blueprints``/``scripts``
directories directly, and now there is.

The old "hermetic vs. convenient" mode split is gone, not replaced
by something else: a directory either has the file or it doesn't,
and nothing falls back to the built-in codex content. The only way
codex content reaches a project directory is the explicit
``seed-blueprint`` command copying it there (P4).

An asset's identity is the ``name`` field declared inside the file,
if it has one, otherwise the filename without its extension. Two
files of the same kind that resolve to the same effective name
within one source is an error. Media aren't a file kind at all —
they're specs written inside a blueprint file, identified by their
own name field — so they're looked up through the catalog instead of
by this file-naming rule. Scripts never have a ``name`` field, so
they're always identified by their filename.

A planned third source, ``ObjectSource`` (for objects an embedding
program supplies directly as JSON, with no files involved), will fit
into this same interface.
"""

import os

from .errors import PreflightError
from .home import (blueprints_dir, fonts_dir, landmarks_dir,
                   scripts_dir)


# File extensions recognized for each authored-asset kind. ``.json``
# is still accepted as an older spelling for blueprints; scripts have
# no older form to accept.
#
# One kind is deliberately missing from this table, and is instead
# just documented in docs/spec/asset-resolution.md: ``.rlqm`` was
# retired when the composed blueprint model was introduced, since a
# media is now just a spec written inside a ``.rlqb`` file (D30). The
# two binary-asset kinds are both implemented now: ``.rlqf`` fonts
# (F61) and ``.rlql`` landmarks (F65). Each reads from its own fixed
# directory under the home (`fonts_dir`, `landmarks_dir`), and each
# finds its binary data by looking for a file with a matching stem.
KIND_EXTENSIONS = {
    "blueprint": (".rlqb", ".json"),
    "script": (".rlqs",),
    "font": (".rlqf",),
    "landmark": (".rlql",),
}


def stem(path):
    """Return a file's stem (basename without its final extension)."""
    return os.path.splitext(os.path.basename(path))[0]


def _walk_files(root, extensions):
    """Yield files of the given extensions under ``root``, recursively.

    Dot-directories (``.git``, ``.venv`` and friends) are pruned, so a
    project root can be walked without descending into version-control
    or virtual-environment trees. Results are ordered for stable
    diagnostics.
    """
    if not root or not os.path.isdir(root):
        return []
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            name for name in dirnames if not name.startswith("."))
        for filename in sorted(filenames):
            if filename.endswith(extensions):
                found.append(os.path.join(dirpath, filename))
    return found


class AssetSource:
    """Where a resolution looks for authored asset files."""

    def candidate_files(self, kind):
        """Return candidate file paths of ``kind`` in this source."""
        raise NotImplementedError

    def document_files(self):
        """Return every composed ``.rlqb`` document in this source.

        All ``.rlqb`` files are read into one shared namespace of
        specs identified by ``(name, type)`` (docs/spec/blueprint-model.md),
        rather than being indexed separately by file extension the
        way other asset kinds are.
        """
        raise NotImplementedError

    def describe(self, kind):
        """Return a human location for ``kind`` for error messages."""
        raise NotImplementedError


class DirectorySource(AssetSource):
    """Resolve each asset kind from its own relocatable directory.

    There's only one kind of source, because there's really only one
    question to answer: which directory holds files of this kind.
    Whether that directory was set explicitly (``--blueprints-dir``)
    or derived from the home location makes no difference to how it's
    read — either way, it's walked recursively for matching file
    extensions, using the same helper.
    """

    _DIRS = {
        "blueprint": blueprints_dir,
        "script": scripts_dir,
        "font": fonts_dir,
        "landmark": landmarks_dir,
    }

    def __init__(self, context=None):
        self._context = context
        self._cache = {}

    def _dir(self, kind):
        resolver = self._DIRS.get(kind)
        return resolver(self._context) if resolver is not None else None

    def candidate_files(self, kind):
        if kind not in self._cache:
            self._cache[kind] = _walk_files(
                self._dir(kind), KIND_EXTENSIONS[kind])
        return self._cache[kind]

    def document_files(self):
        return _walk_files(self._dir("blueprint"), (".rlqb",))

    def describe(self, kind):
        return self._dir(kind)


def source_for(context=None):
    """Build the :class:`AssetSource` for ``context``.

    The directories aren't looked up until they're actually needed,
    so building a source here never fails on its own. If
    ``blueprints`` (for example) isn't configured, that only raises
    an error once something actually tries to resolve from it, naming
    the missing directory (``home.py``).
    """
    return DirectorySource(context)


def index_by_name(files, name_of, kind):
    """Map effective name -> path for ``files``, guarding conflicts.

    ``name_of(path)`` returns the asset's declared ``name`` field, or
    ``None`` if it doesn't have one, in which case the filename stem
    is used instead. If two files of the same kind end up with the
    same effective name, this raises an error naming both files.
    """
    index = {}
    for path in files:
        effective = name_of(path) or stem(path)
        existing = index.get(effective)
        if existing is not None:
            raise PreflightError(
                f"two {kind} assets both resolve to the name "
                f"{effective!r}:\n  {existing}\n  {path}",
                rule_id="name.asset-collision")
        index[effective] = path
    return index


def guard_pool(kind, claims, other_kind, others):
    """Raise an error if a name is claimed by two different kinds sharing one ``@`` pool.

    Media, fonts (F61), and landmarks (F65) are all looked up through
    one shared ``@`` reference pool (planning/design/authored-binary-assets.md),
    so when a script reads ``@welcome``, exactly one thing has to
    match that name. Both ``claims`` and ``others`` map an effective
    name to a human-readable file location; the error names both
    files, since fixing the conflict means renaming one of them, and
    a message that doesn't name both files gives the author nothing
    to act on.

    Names are compared case-insensitively, the same rule
    ``resolve.build_namespace`` uses for its own namespace, and the
    error says whether it found an exact duplicate name or names that
    only differ by case — those look very different to someone
    reading the error.
    """
    folded = {name.lower(): name for name in others}
    for name, where in claims.items():
        other = folded.get(name.lower())
        if other is None:
            continue
        how = ("the same name" if other == name
               else "names that differ only by case")
        raise PreflightError(
            f"{kind} {name!r} and {other_kind} {other!r} share the @ "
            f"pool ({how}):\n  {where}\n  {others[other]}",
            rule_id="name.pool-collision")
