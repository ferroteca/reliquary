# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Reliquary home resolution, layout, and containment."""

import os
import subprocess
import sys


_home = os.environ.get("RELIQUARY_HOME")
_home_announced = False
_cache = os.environ.get("RELIQUARY_CACHE_DIR")


class _HomeAssets:
    """The marker selecting home-mode authored-asset resolution.

    Home mode resolves blueprints, media, and scripts from the home's
    canonical ``blueprints/`` / ``media/`` / ``scripts/`` folders and
    seeds missing names from the built-in codex. It is the CLI default
    (no ``--assets``); the embedding API never selects it by default —
    an API caller names a directory (or, later, supplies objects).
    """

    __slots__ = ()

    def __repr__(self):
        return "HOME_ASSETS"


HOME_ASSETS = _HomeAssets()

# Sentinel distinguishing "no asset source ever configured" from an
# explicit home/dir selection. The process-global asset mode starts
# unset: the CLI sets it in ``main()`` (home mode, or a directory);
# an embedding API call must name a source per resolution or fail.
_UNSET = object()
_assets = _UNSET


def set_home(path):
    """Configure the reliquary work directory (overrides RELIQUARY_HOME)."""
    global _home
    _home = os.path.abspath(path)


def set_cache(path):
    """Configure the cache root (overrides RELIQUARY_CACHE_DIR)."""
    global _cache
    _cache = os.path.abspath(path)


def set_assets(value):
    """Configure the process-global authored-asset source.

    ``HOME_ASSETS`` selects home mode; a directory path selects that
    directory as the sole (hermetic) asset root. The CLI drives this
    from ``--assets`` (home mode when the flag is absent). Scoped
    per-call selection is an embedding-API capability via
    ``Context(assets=...)``.
    """
    global _assets
    if value is HOME_ASSETS:
        _assets = value
    else:
        _assets = os.path.abspath(value)


def assets_mode(context=None):
    """Resolve the effective authored-asset mode for ``context``.

    Returns ``HOME_ASSETS`` (home mode) or an absolute directory path
    (dir mode). Per-call ``Context(assets=...)`` wins; otherwise the
    process-global set by ``set_assets`` applies; with neither
    configured — the bare embedding-API case — resolution fails,
    since automation must name where its assets live rather than
    silently fall back to the home or the current directory.
    """
    mode = _ctx(context).assets
    if mode is None:
        mode = _assets
    if mode is None or mode is _UNSET:
        raise RuntimeError(
            "no asset source configured: pass assets=<dir> to name "
            "the project's asset root (the CLI defaults to the home)")
    return mode


def documents_dir():
    """The user's Documents folder, or None if it cannot be determined."""
    if sys.platform == "win32":
        import ctypes

        class GUID(ctypes.Structure):
            _fields_ = [("Data1", ctypes.c_ulong),
                        ("Data2", ctypes.c_ushort),
                        ("Data3", ctypes.c_ushort),
                        ("Data4", ctypes.c_ubyte * 8)]

        folderid_documents = GUID(
            0xFDD39AD0, 0x238F, 0x46AF,
            (ctypes.c_ubyte * 8)(0xAD, 0xB4, 0x6C, 0x85,
                                 0x48, 0x03, 0x69, 0xC7))
        path = ctypes.c_wchar_p()
        if ctypes.windll.shell32.SHGetKnownFolderPath(
                ctypes.byref(folderid_documents), 0, None,
                ctypes.byref(path)):
            return None
        try:
            return path.value
        finally:
            ctypes.windll.ole32.CoTaskMemFree(path)
    if sys.platform == "darwin":
        return os.path.expanduser(os.path.join("~", "Documents"))
    try:
        documents = subprocess.run(
            ["xdg-user-dir", "DOCUMENTS"], capture_output=True, text=True,
        ).stdout.strip()
        if os.path.isabs(documents):
            return documents
    except OSError:
        pass
    return None


def home():
    global _home, _home_announced
    if not _home:
        base = documents_dir() or os.path.expanduser("~")
        _home = os.path.join(base, "reliquary")
    if not _home_announced:
        _home_announced = True
        print(f"using reliquary home: {_home}", file=sys.stderr)
    return _home


def effective_home(explicit):
    """Return the explicit operation home or the process-global home.

    For the small set of modules (``lifecycle.py``, ``machine.py``)
    that take an already-resolved plain directory rather than a
    ``Context`` — sometimes a real reliquary home, sometimes a
    machine's own cache subdirectory standing in for one.
    """
    return os.path.abspath(explicit) if explicit else home()


class Context:
    """An explicit (home, cache) pair scoping one call or a group of calls.

    Every reliquary function that resolves a path under the home
    accepts a ``context=`` parameter. Omitting it (the common case)
    uses the process-global default — whatever ``set_home()`` /
    ``set_cache()`` / ``RELIQUARY_HOME`` / ``RELIQUARY_CACHE_DIR``
    currently resolve to, exactly as a bare ``home=None`` did
    before. Passing a plain string is sugar for ``Context(home=...)``
    (cache still follows the global default). Passing a ``Context``
    instance pins both home and cache explicitly, independent of the
    global default and safe to vary per call within one process —
    the CLI never does this itself (it only ever drives the global
    default via ``--home``/``--cache``); scoped contexts are an
    embedding-API-only capability.

    ``assets`` selects where authored assets (blueprints, media
    definitions, scripts) resolve from: ``HOME_ASSETS`` for home mode
    (the home's canonical folders plus codex seeding) or a directory
    path for that hermetic root. ``None`` inherits the process-global
    ``set_assets`` selection; when neither is set, resolution fails —
    an embedding call must name its source rather than default to the
    home or the current directory.
    """

    __slots__ = ("home", "cache", "assets")

    def __init__(self, home=None, cache=None, assets=None):
        self.home = os.path.abspath(home) if home else None
        self.cache = os.path.abspath(cache) if cache else None
        if assets is None or assets is HOME_ASSETS:
            self.assets = assets
        else:
            self.assets = os.path.abspath(assets)

    def home_dir(self):
        """The effective home for this context."""
        return self.home if self.home else home()

    def cache_dir(self):
        """The effective cache root for this context."""
        if self.cache:
            return self.cache
        if _cache:
            return os.path.abspath(_cache)
        return os.path.join(self.home_dir(), "cache")

    def blueprints_dir(self):
        return os.path.join(self.home_dir(), "blueprints")

    def scripts_dir(self):
        return os.path.join(self.home_dir(), "scripts")

    def media_cache_dir(self):
        return os.path.join(self.cache_dir(), "media")

    def machines_cache_dir(self):
        return os.path.join(self.cache_dir(), "machines")


def _ctx(context):
    """Coerce ``None``/a bare home string/a ``Context`` into a ``Context``.

    A bare home string is the human/home shorthand, so it selects home
    mode (``assets=HOME_ASSETS``); a fully explicit ``Context`` names
    its own asset source (or inherits the process-global).
    """
    if context is None:
        return Context()
    if isinstance(context, Context):
        return context
    return Context(home=context, assets=HOME_ASSETS)


def blueprints_dir(context=None):
    """Return the machine-blueprint directory under the effective home."""
    return _ctx(context).blueprints_dir()


def scripts_dir(context=None):
    """Return the automation-script directory under the effective home."""
    return _ctx(context).scripts_dir()


def cache_dir(context=None):
    """Return the regenerable-cache root under the effective context."""
    return _ctx(context).cache_dir()


def media_cache_dir(context=None):
    """Return the cached media-payload directory under the context."""
    return _ctx(context).media_cache_dir()


def machines_cache_dir(context=None):
    """Return the cached machine-materialization directory."""
    return _ctx(context).machines_cache_dir()
