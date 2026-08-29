# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Resolving, laying out, and deriving reliquary's working directories.

Reliquary has six working directories, and every one of them can be
placed independently: ``home``, ``blueprints``, ``scripts``,
``cache``, ``media``, and ``machines``. Each one starts out
unassigned. A directory gets a value through the ``Context`` record a
``Session`` is opened on. The CLI builds one ``Context`` per
invocation, from its ``--*-dir`` flags, then the ``RELIQUARY_*_DIR``
environment variables (``RELIQUARY_HOME`` for the home directory
specifically), then the default home directory. Any directory that's
still unassigned after that gets its default location computed, not
hardcoded:

- assigning ``home`` gives ``blueprints``, ``scripts``, and ``cache``
  their default locations, as subdirectories of it;
- assigning ``cache`` — whether directly, or because it was itself
  derived from ``home`` above — gives ``media`` and ``machines``
  their default locations, as subdirectories of it.

This derivation only fills in directories that are still unassigned.
So assigning ``cache`` alone does not invent a ``home`` — there isn't
one — and assigning ``machines`` alone leaves ``media`` to be resolved
however the rest of this process resolves it. None of this state is
global to the process — the ``Context`` record carries everything —
so having two ``Session`` objects at once in one program causes no
conflict (P26).

**A ``Context`` with no home directory assigned is an error, and
``Session`` construction catches it immediately**: construction
raises ``StaticError`` with ``rule_id="dir.unassigned"``, naming the
missing home directory, before any later call could hit an
unassigned directory — since an assigned home makes all six
directories resolvable through derivation. The same check exists
again, deeper in the engine, for the case where some code resolves a
directory directly from a bare ``Context`` rather than going through
``Session``. It's the same rule and the same rule_id in both places.

The CLI and the embedding API differ only in whether they assign a
default home on the caller's behalf. The **CLI** fills in the default
home directory whenever neither a flag nor an environment variable
named one, so from that one assignment all six directories become
resolvable, and a user running the CLI can never actually trigger the
"no home assigned" error — that's a result of the default being
applied, not a special case carved out of the rule. That distinction
matters because it means the guarantee still holds even if the
default value itself changes later. The **embedding API** assigns no
default at all — a ``Session`` requires its home directory to be
given explicitly — so a library call never silently reuses whatever
home directory happens to belong to the developer running it.
Likewise, only the CLI reads environment variables during its own
construction step; nothing in this module reads them.
"""

import os
import subprocess
import sys

from .errors import StaticError


#: The six placeable working directories.
DIRECTORIES = ("home", "blueprints", "scripts", "cache", "media",
               "machines")

#: For each directory that can be derived, which directory it's
#: derived from and the subdirectory name it takes there. ``home`` has
#: no entry, because nothing derives it — it's the one directory that
#: must either be assigned directly or left unassigned.
_DERIVED_FROM = {
    "blueprints": ("home", "blueprints"),
    "scripts": ("home", "scripts"),
    "cache": ("home", "cache"),
    "media": ("cache", "media"),
    "machines": ("cache", "machines"),
}

def environment_variable(name):
    """Return the environment variable name that assigns directory ``name``.

    Follows one mechanical rule: ``RELIQUARY_`` plus the flag's own
    name, uppercased — so ``--blueprints-dir`` maps to
    ``RELIQUARY_BLUEPRINTS_DIR``, with nothing to memorize per
    directory. ``home`` is the one exception users actually see: its
    variable is ``RELIQUARY_HOME``, not ``RELIQUARY_HOME_DIR``. Only
    the CLI's construction step actually reads these variables; this
    module never does.
    """
    if name == "home":
        return "RELIQUARY_HOME"
    return "RELIQUARY_%s_DIR" % name.upper()


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


def default_home_dir():
    """Return the home directory the CLI uses when the caller named none.

    Returns ``Documents/reliquary``, or ``~/reliquary`` if no Documents
    folder can be found. This function only computes that path; it's
    the CLI's job to actually assign it.
    """
    return os.path.join(documents_dir() or os.path.expanduser("~"),
                        "reliquary")


class Context:
    """Holds the six working-directory assignments for one call or session.

    A plain data record: each field holds an absolute path, or
    ``None`` if unassigned, and all the logic for resolving those
    paths lives in this module's functions instead of on the class.
    Keeping it this simple — a handful of strings that can be
    ``None`` — means it can be constructed cleanly from C or Java too,
    where Python-style keyword arguments aren't available (P7), and it
    leaves the name ``cache_dir`` free to also be read as "the thing
    that resolves the cache directory."

    Every engine function that resolves a working directory accepts a
    ``context=`` argument: passing a plain string is shorthand for
    ``Context(home_dir=<that string>)``, and passing a ``Context``
    pins whatever fields it has set, letting the rest be derived. A
    ``Session`` resolves the whole record once, at construction, and
    passes it to every call it makes (P26). The CLI builds exactly
    one ``Context`` per invocation — from its flags, the environment,
    and the default home directory — and opens its ``Session`` on
    that.

    ``properties_file`` is carried alongside the six directories
    (P26): which properties file is selected is state that travels
    with a call the same way the directories do, so it lives in this
    same record. ``None`` means no file was explicitly selected, and
    ``properties.py`` then falls back to its own default exactly as
    if this record had never carried a value at all.
    """

    __slots__ = ("home_dir", "blueprints_dir", "scripts_dir",
                 "cache_dir", "media_dir", "machines_dir",
                 "properties_file")

    def __init__(self, home_dir=None, blueprints_dir=None,
                 scripts_dir=None, cache_dir=None, media_dir=None,
                 machines_dir=None, properties_file=None):
        self.home_dir = os.path.abspath(home_dir) if home_dir else None
        self.blueprints_dir = (os.path.abspath(blueprints_dir)
                               if blueprints_dir else None)
        self.scripts_dir = (os.path.abspath(scripts_dir)
                            if scripts_dir else None)
        self.cache_dir = os.path.abspath(cache_dir) if cache_dir else None
        self.media_dir = os.path.abspath(media_dir) if media_dir else None
        self.machines_dir = (os.path.abspath(machines_dir)
                             if machines_dir else None)
        self.properties_file = (os.path.abspath(properties_file)
                                if properties_file else None)

    def __repr__(self):
        filled = ", ".join(
            "%s=%r" % (slot, getattr(self, slot))
            for slot in self.__slots__ if getattr(self, slot) is not None)
        return "Context(%s)" % filled


_EMPTY = Context()


def as_context(context):
    """Coerce ``None``, a bare home-directory string, or a ``Context`` into a ``Context``.

    A bare string assigns only the home directory; the other five
    directories are then derived from it.
    """
    if context is None:
        return _EMPTY
    if isinstance(context, Context):
        return context
    return Context(home_dir=context)


def _unassigned(name):
    """Build the StaticError raised when directory ``name`` was never assigned."""
    routes = [name]
    parent = _DERIVED_FROM.get(name)
    while parent is not None:
        routes.append(parent[0])
        parent = _DERIVED_FROM.get(parent[0])
    derive = " or ".join("'%s'" % route for route in routes[1:])
    message = (
        "no directory assigned for '%s'\n"
        "  assign it with %s_dir=<path> (CLI --%s-dir, environment "
        "%s)" % (name, name, name, environment_variable(name)))
    if derive:
        message += "\n  or assign %s and let it derive" % derive
    return StaticError(message, rule_id="dir.unassigned")


def _resolve(name, context):
    """Resolve directory ``name``: use the record's own value if set, else derive it."""
    context = as_context(context)
    assigned = getattr(context, "%s_dir" % name)
    if assigned:
        return assigned
    derivation = _DERIVED_FROM.get(name)
    if derivation is None:
        raise _unassigned(name)
    parent, leaf = derivation
    try:
        return os.path.join(_resolve(parent, context), leaf)
    except StaticError as error:
        if getattr(error, "rule_id", None) != "dir.unassigned":
            raise
        # The caller asked to resolve `name`, so the error should
        # name `name`, not the unassigned ancestor directory that
        # `name` derives from — that would answer a question nobody
        # asked. The error message for `name` already lists that
        # ancestor as one of the ways to fix it, so nothing is lost by
        # raising this instead of letting the ancestor's own error
        # propagate.
        raise _unassigned(name) from None


def _derive_from(name, context):
    """Resolve directory ``name`` using only ``context``; return None if it can't be resolved."""
    assigned = getattr(context, "%s_dir" % name)
    if assigned:
        return assigned
    derivation = _DERIVED_FROM.get(name)
    if derivation is None:
        return None
    parent, leaf = derivation
    parent_path = _derive_from(parent, context)
    if parent_path is None:
        return None
    return os.path.join(parent_path, leaf)


def pinned(context=None):
    """Return a new ``Context`` with every derivable field filled in.

    Fills in each directory the same way a caller resolving it
    manually would: use what's explicitly assigned, then derive the
    rest, using only what's in ``context`` itself. This is what a
    ``Session`` calls at construction time to resolve its six
    directories once and hold onto that result (P26). A field that
    can't be derived — which happens for every field when there's no
    home directory — is left as ``None`` here rather than raising an
    error, because whether a missing field is actually an error is
    for the caller to decide, not this function.
    """
    context = as_context(context)
    slots = {"%s_dir" % name: _derive_from(name, context)
             for name in DIRECTORIES}
    return Context(properties_file=context.properties_file, **slots)


def home_dir(context=None):
    """Return the Reliquary home."""
    return _resolve("home", context)


def blueprints_dir(context=None):
    """Return the machine-blueprint directory."""
    return _resolve("blueprints", context)


def scripts_dir(context=None):
    """Return the automation-script directory."""
    return _resolve("scripts", context)


def cache_dir(context=None):
    """Return the regenerable-cache root."""
    return _resolve("cache", context)


def media_dir(context=None):
    """Return the cached media-payload directory."""
    return _resolve("media", context)


def machines_dir(context=None):
    """Return the machine-materialization directory."""
    return _resolve("machines", context)


def fonts_dir(context=None):
    """Return the directory where authored fonts live.

    This is not one of the six placeable directories — it's always a
    fixed subdirectory of ``home``, ``<home>/fonts``, and can never be
    assigned independently. `authored-binary-assets.md` states
    explicitly that adding a new binary asset kind (a font, a
    landmark) does not add a seventh placeable directory (P12); each
    one resolves to a subdirectory of a directory that already
    exists, the same way `landmarks_dir` below does. So a project
    whose ``scripts`` or ``blueprints`` live outside the home
    directory still has its fonts under the home directory regardless
    — an accepted tradeoff, rather than widening the six-directory
    model for one more read-only kind of asset.
    """
    return os.path.join(home_dir(context), "fonts")


def landmarks_dir(context=None):
    """Return the directory where authored landmarks live.

    ``<home>/landmarks`` — a fixed subdirectory, the same pattern
    `fonts_dir` above already established (F65). A landmark is the
    second kind of authored binary asset, and follows the same rule
    as a font: it does not add a seventh placeable directory, it is
    read-only, and its different renderings sit next to the
    declaration by filename-stem matching rather than each getting
    their own directory.
    """
    return os.path.join(home_dir(context), "landmarks")


def effective_home(explicit):
    """Return ``explicit`` if given, else the resolved home directory.

    Used by the small set of modules (``machine.py``, the backend
    adapters) that take an already-resolved plain directory path
    instead of a ``Context`` — sometimes that's a real reliquary home
    directory, and sometimes it's a machine's own materialization
    directory being used in its place.
    """
    return os.path.abspath(explicit) if explicit else home_dir()
