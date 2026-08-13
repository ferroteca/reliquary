# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Working-directory resolution, layout, and containment.

Reliquary has six working directories and every one of them is
placeable: ``home``, ``blueprints``, ``scripts``, ``cache``, ``media``
and ``machines``. Each starts **unassigned**. A value arrives in the
``Context`` record a session is opened on — the CLI builds one per
invocation from its ``--*-dir`` flags, the ``RELIQUARY_*_DIR``
environment variables (except ``RELIQUARY_HOME`` for the home), and
the default home — and every default is
*derived* rather than pre-set:

- assigning ``home`` gives default locations under it to
  ``blueprints``, ``scripts`` and ``cache``;
- assigning ``cache`` — explicitly, *or* by the derivation above —
  gives default locations under it to ``media`` and ``machines``.

Derivation reaches only what is still unassigned, so assigning
``cache`` alone conjures no home, and assigning ``machines`` alone
leaves ``media`` wherever the rest of the resolution puts it. There
is no process-global assignment: the record carries everything, so
two sessions in one process are unremarkable (P26).

**A record with no home is a fail-closed error at the session's
door**: construction refuses (``dir.unassigned``), naming the home,
before any call could find a directory unassigned — an assigned
home reaching all six by derivation. The same refusal survives at
first use inside the engine, for a resolution reached with a bare
record; one rule, one id, wherever it is noticed.

The two surfaces differ only in whether an assignment is made on the
caller's behalf. The **CLI** gives ``home`` its default whenever
neither a flag nor the environment named one, so one assignment
reaches all six and the refusal is unreachable at the keyboard: a
property of that default rather than an exemption from the rule,
which matters because a property survives the default changing and
an exemption would have to be re-argued. The **embedding API**
assigns nothing — a session demands its home at the door — so a
library call never silently picks up the developer's home. Honouring
the environment is likewise the CLI's private construction step and
never the library's: nothing here reads the environment.
"""

import os
import subprocess
import sys

from .errors import StaticError


#: The six placeable working directories.
DIRECTORIES = ("home", "blueprints", "scripts", "cache", "media",
               "machines")

#: What each derived directory hangs off, and the leaf it takes
#: there. ``home`` is absent because nothing derives it: it is the
#: one directory that must be assigned or done without.
_DERIVED_FROM = {
    "blueprints": ("home", "blueprints"),
    "scripts": ("home", "scripts"),
    "cache": ("home", "cache"),
    "media": ("cache", "media"),
    "machines": ("cache", "machines"),
}

def environment_variable(name):
    """The environment variable that assigns directory ``name``.

    One mechanical rule — ``RELIQUARY_`` plus the flag's own name —
    so ``--blueprints-dir`` is ``RELIQUARY_BLUEPRINTS_DIR`` and there
    is nothing per-directory to remember. ``home`` is the one
    user-facing exception: its established spelling is
    ``RELIQUARY_HOME``. Honoured by the CLI's construction step alone;
    this module never reads it.
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
    """The home the CLI assigns when the caller named none.

    ``Documents/reliquary``, falling back to ``~/reliquary`` where no
    Documents folder can be determined. Computed, never assigned here:
    assigning is the CLI's act, and this is only the value it uses.
    """
    return os.path.join(documents_dir() or os.path.expanduser("~"),
                        "reliquary")


class Context:
    """A per-call assignment of the six working directories.

    A plain record: each slot holds an absolute path or ``None`` for
    unassigned, and all resolution lives in this module's functions.
    That keeps it a handful of nullable strings, which binds cleanly
    from C or Java where keyword arguments would not (P7) — and it
    leaves ``cache_dir`` free to be the resolver it reads as.

    Every engine function that resolves a working directory takes a
    ``context=``: a plain string is sugar for ``Context(home_dir=...)``,
    and a ``Context`` pins whatever slots it fills, the rest deriving.
    The session pins the whole record once at construction and hands
    it to every call (P26); the CLI builds exactly one per
    invocation — from its flags, the environment, and the default
    home — and opens its session on it.

    ``properties_file`` rides beside the six (P26): the selected
    properties file is ambient state exactly as the directories are,
    so the one record carries it too. ``None`` selects nothing, and
    the selection in ``properties.py`` then falls through exactly as
    if no record carried one.
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
    """Coerce ``None`` / a bare home string / a ``Context`` into one.

    A bare string assigns the home and nothing else, so the other
    five derive from it.
    """
    if context is None:
        return _EMPTY
    if isinstance(context, Context):
        return context
    return Context(home_dir=context)


def _unassigned(name):
    """The fail-closed diagnostic for a directory nobody assigned."""
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
    """Resolve one directory: the record's slot, then derivation."""
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
        # The caller asked for `name`; naming its unassigned ancestor
        # would answer a question nobody put. The routes to fix it
        # include that ancestor, so nothing is lost by restating.
        raise _unassigned(name) from None


def _derive_from(name, context):
    """Resolve one directory from ``context`` alone, or ``None``."""
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
    """Return ``context`` with every derivable slot filled, from it
    alone.

    The resolution a caller would get who pinned every slot:
    per-call assignment then derivation, from the record alone.
    This is the session's construction step (P26 — the session
    carries the six directories, once). A slot the record cannot
    derive — anything, when it holds no home — stays ``None`` rather
    than raising, because whether an unfilled slot is an error is the
    caller's rule, not this record's.
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


def effective_home(explicit):
    """Return the explicit operation home, or the resolved home.

    For the small set of modules (``machine.py``, the backend
    adapters) that take an already-resolved plain directory rather
    than a ``Context`` — sometimes a real reliquary home, sometimes a
    machine's own materialization directory standing in for one.
    """
    return os.path.abspath(explicit) if explicit else home_dir()
