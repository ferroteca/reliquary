# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Authored-asset residency: the resolution source seam.

Authored assets — machine blueprints (``.rlqb``, media included)
and scripts (``.rlqs``) — resolve through one of two file-backed
sources, selected per invocation (``home.assets_mode``):

- **home mode** (``HomeSource``) — the CLI default. Resolves from the
  home's canonical ``blueprints/`` and ``scripts/`` folders and seeds
  missing names from the built-in codex. A convenience for human CLI
  interaction.
- **dir mode** (``DirSource``) — ``--assets <dir>`` / API ``assets=``.
  A project's own asset root, walked recursively by extension, as the
  **sole** source: no home, no codex. Hermetic, for automation.

An asset's identity is its ``name`` field when the authored file
declares one, else its filename stem; two files of one kind claiming
the same effective name within a source is an error. Media are not a
file kind at all — they are specs inside a blueprint, identified by
their own names — so they resolve through the catalog rather than by
this rule; scripts carry no ``name`` field and stay stem-identified.

An ``ObjectSource`` (JSON-imported objects supplied by an embedding
caller, no files at all) is the planned third source and slots onto
this same seam.
"""

import os

from .home import (HOME_ASSETS, assets_mode, blueprints_dir,
                   scripts_dir)


# Authored-asset file extensions by kind. ``.json`` is the accepted
# legacy spelling for blueprints; scripts have no legacy form.
#
# Two kinds are deliberately absent, both reserved in
# docs/spec/asset-resolution.md rather than declared here. ``.rlqm``
# retired with the composed model — a media is a spec inside a
# ``.rlqb`` (D30). ``.rlql`` landmarks are unbuilt: nothing requests
# the kind, and home mode has no ``landmarks/`` folder to resolve one
# from, so declaring it would only advertise a resolution that
# cannot happen.
KIND_EXTENSIONS = {
    "blueprint": (".rlqb", ".json"),
    "script": (".rlqs",),
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

    seeds = False

    def candidate_files(self, kind):
        """Return candidate file paths of ``kind`` in this source."""
        raise NotImplementedError

    def document_files(self):
        """Return every composed ``.rlqb`` document in this source.

        The composed model reads all ``.rlqb`` into one ``(name, type)``
        component namespace (docs/spec/blueprint-model.md), rather
        than indexing one file kind per extension.
        """
        raise NotImplementedError

    def describe(self, kind):
        """Return a human location for ``kind`` for error messages."""
        raise NotImplementedError


class HomeSource(AssetSource):
    """Resolve from the home's canonical folders; seed from the codex."""

    seeds = True

    _DIRS = {
        "blueprint": blueprints_dir,
        "script": scripts_dir,
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
        return self._dir(kind) or "the home"


class DirSource(AssetSource):
    """Resolve solely from a project asset root, walked by extension."""

    seeds = False

    def __init__(self, root):
        self.root = os.path.abspath(root)
        self._cache = {}

    def candidate_files(self, kind):
        if kind not in self._cache:
            self._cache[kind] = _walk_files(
                self.root, KIND_EXTENSIONS[kind])
        return self._cache[kind]

    def document_files(self):
        return _walk_files(self.root, (".rlqb",))

    def describe(self, kind):
        return self.root


def source_for(context=None):
    """Build the :class:`AssetSource` selected for ``context``.

    Reads :func:`reliquary.home.assets_mode`, so a bare embedding-API
    call with no source configured raises rather than silently
    resolving against the home or the current directory.
    """
    mode = assets_mode(context)
    if mode is HOME_ASSETS:
        return HomeSource(context)
    return DirSource(mode)


def index_by_name(files, name_of, kind):
    """Map effective name -> path for ``files``, guarding conflicts.

    ``name_of(path)`` returns the asset's declared ``name`` or ``None``;
    the effective name falls back to the filename stem. Two files of
    one kind sharing an effective name is an error naming both — the
    residency conflict guard.
    """
    index = {}
    for path in files:
        effective = name_of(path) or stem(path)
        existing = index.get(effective)
        if existing is not None:
            raise ValueError(
                f"two {kind} assets both resolve to the name "
                f"{effective!r}:\n  {existing}\n  {path}")
        index[effective] = path
    return index
