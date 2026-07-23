# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Reliquary home resolution, layout, and containment."""

import os
import subprocess
import sys


_home = os.environ.get("RELIQUARY_HOME")
_home_announced = False
_cache = os.environ.get("RELIQUARY_CACHE_DIR")


def set_home(path):
    """Configure the reliquary work directory (overrides RELIQUARY_HOME)."""
    global _home
    _home = os.path.abspath(path)


def set_cache(path):
    """Configure the cache root (overrides RELIQUARY_CACHE_DIR)."""
    global _cache
    _cache = os.path.abspath(path)


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
    """

    __slots__ = ("home", "cache")

    def __init__(self, home=None, cache=None):
        self.home = os.path.abspath(home) if home else None
        self.cache = os.path.abspath(cache) if cache else None

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

    def media_dir(self):
        return os.path.join(self.home_dir(), "media")

    def scripts_dir(self):
        return os.path.join(self.home_dir(), "scripts")

    def downloads_cache_dir(self):
        return os.path.join(self.cache_dir(), "downloads")

    def media_cache_dir(self):
        return os.path.join(self.cache_dir(), "media")

    def machines_cache_dir(self):
        return os.path.join(self.cache_dir(), "machines")


def _ctx(context):
    """Coerce ``None``/a bare home string/a ``Context`` into a ``Context``."""
    if context is None:
        return Context()
    if isinstance(context, Context):
        return context
    return Context(home=context)


def blueprints_dir(context=None):
    """Return the machine-blueprint directory under the effective home."""
    return _ctx(context).blueprints_dir()


def media_dir(context=None):
    """Return the shared media-definition directory under the home."""
    return _ctx(context).media_dir()


def scripts_dir(context=None):
    """Return the automation-script directory under the effective home."""
    return _ctx(context).scripts_dir()


def cache_dir(context=None):
    """Return the regenerable-cache root under the effective context."""
    return _ctx(context).cache_dir()


def downloads_cache_dir(context=None):
    """Return the cached source-archive directory under the context."""
    return _ctx(context).downloads_cache_dir()


def media_cache_dir(context=None):
    """Return the cached media-payload directory under the context."""
    return _ctx(context).media_cache_dir()


def machines_cache_dir(context=None):
    """Return the cached machine-materialization directory."""
    return _ctx(context).machines_cache_dir()
