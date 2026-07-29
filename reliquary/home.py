# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Working-directory resolution, layout, and containment.

Reliquary has six working directories and every one of them is
placeable: ``home``, ``blueprints``, ``scripts``, ``cache``, ``media``
and ``machines``. Each starts **unassigned**. A value arrives by
explicit assignment — a ``set_*_dir`` call, the CLI's matching
``--*-dir`` flag, or the matching ``RELIQUARY_*_DIR`` environment
variable — and every default is *derived* rather than pre-set:

- assigning ``home`` gives default locations under it to
  ``blueprints``, ``scripts`` and ``cache``;
- assigning ``cache`` — explicitly, *or* by the derivation above —
  gives default locations under it to ``media`` and ``machines``.

Derivation reaches only what is still unassigned, so assigning
``cache`` alone conjures no home, and assigning ``machines`` alone
leaves ``media`` wherever the rest of the resolution puts it.

**Unassigned is a fail-closed error**, raised at first use — not at
``Context`` construction, so a context may be built now and filled
later, and the diagnostic names the directory actually needed rather
than the root of a cascade nobody asked about.

The two surfaces differ only in whether an assignment is made on the
caller's behalf. The **CLI** assigns ``home`` its default unless
``--home-dir`` was given, so one assignment reaches all six and the
error is unreachable at the keyboard — a property of that default
rather than an exemption from the rule, which matters because a
property survives the default changing and an exemption would have
to be re-argued. The **embedding API** assigns nothing, so a library
call never silently picks up the developer's home; there the error
is reachable, and it is the whole safety of the design.

Two further behaviours follow the same CLI-on/API-off split, for the
same reason: honouring the environment (:func:`adopt_environment`)
and codex autoseeding (:func:`autoseed`).
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

# Process-global assignments, all unassigned at import. Nothing is
# read from the environment here: that is the CLI's step, and doing
# it at import would make an embedding call's resolution depend on
# the developer's shell — exactly what the API rule forbids.
_globals = dict.fromkeys(DIRECTORIES)

# Codex autoseeding, off until something turns it on. The CLI does;
# an embedding caller must ask.
_autoseed = False


def environment_variable(name):
    """The environment variable that assigns directory ``name``.

    One mechanical rule — ``RELIQUARY_`` plus the flag's own name —
    so ``--blueprints-dir`` is ``RELIQUARY_BLUEPRINTS_DIR`` and there
    is nothing per-directory to remember.
    """
    return "RELIQUARY_%s_DIR" % name.upper()


def _assign(name, path):
    _globals[name] = os.path.abspath(path)


def set_home_dir(path):
    """Assign the home; ``blueprints``/``scripts``/``cache`` derive."""
    _assign("home", path)


def set_blueprints_dir(path):
    """Assign where machine blueprints resolve from and seed to."""
    _assign("blueprints", path)


def set_scripts_dir(path):
    """Assign where automation scripts resolve from and seed to."""
    _assign("scripts", path)


def set_cache_dir(path):
    """Assign the regenerable cache root; ``media``/``machines`` derive."""
    _assign("cache", path)


def set_media_dir(path):
    """Assign where fetched media payloads are cached."""
    _assign("media", path)


def set_machines_dir(path):
    """Assign where machines materialize."""
    _assign("machines", path)


def is_assigned(name):
    """Whether directory ``name`` has a process-global assignment.

    Assignment, not resolvability: a derived directory answers False
    here while resolving perfectly well. The CLI asks so it can
    default the home only when neither a flag nor the environment
    named one.
    """
    return _globals[name] is not None


def set_autoseed(enabled):
    """Turn codex autoseeding on or off for this process.

    Autoseeding copies a shipped codex asset out on a resolution miss.
    It is on at the CLI and off in the embedding API: a person meeting
    Reliquary for the first time wants ``freedos`` to exist, and a
    program does not want its blueprint arriving from somewhere its
    source tree does not record. Either surface may say otherwise —
    the CLI with ``--no-autoseed``, a caller with ``autoseed=``.
    """
    global _autoseed
    _autoseed = bool(enabled)


def adopt_environment():
    """Assign whatever the environment names, filling unassigned slots.

    A CLI step, never the API's. Explicit assignment wins: this only
    fills what is still unassigned, and it runs when the CLI
    configures itself rather than at import, so a test that sets a
    variable and then calls in gets the behaviour it wrote.
    """
    for name in DIRECTORIES:
        if _globals[name] is None:
            value = os.environ.get(environment_variable(name))
            if value:
                _assign(name, value)


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
    That keeps it six nullable strings, which binds cleanly from C or
    Java where six keyword arguments would not (P7) — and it leaves
    ``cache_dir`` free to be the resolver it reads as.

    Every reliquary function that resolves a working directory takes a
    ``context=``. Omitting it uses the process-global assignments;
    passing a plain string is sugar for ``Context(home_dir=...)``;
    passing a ``Context`` pins whatever slots it fills, per call and
    independent of the globals, with the rest falling through to them
    and then to derivation. The CLI never builds one — it drives the
    globals from its flags; scoped contexts are an embedding-API
    capability.

    ``autoseed`` is the same tri-state: ``None`` inherits the
    process-global, ``True``/``False`` pin it for this call.
    """

    __slots__ = ("home_dir", "blueprints_dir", "scripts_dir",
                 "cache_dir", "media_dir", "machines_dir", "autoseed")

    def __init__(self, home_dir=None, blueprints_dir=None,
                 scripts_dir=None, cache_dir=None, media_dir=None,
                 machines_dir=None, autoseed=None):
        self.home_dir = os.path.abspath(home_dir) if home_dir else None
        self.blueprints_dir = (os.path.abspath(blueprints_dir)
                               if blueprints_dir else None)
        self.scripts_dir = (os.path.abspath(scripts_dir)
                            if scripts_dir else None)
        self.cache_dir = os.path.abspath(cache_dir) if cache_dir else None
        self.media_dir = os.path.abspath(media_dir) if media_dir else None
        self.machines_dir = (os.path.abspath(machines_dir)
                             if machines_dir else None)
        self.autoseed = autoseed

    def __repr__(self):
        filled = ", ".join(
            "%s=%r" % (slot, getattr(self, slot))
            for slot in self.__slots__ if getattr(self, slot) is not None)
        return "Context(%s)" % filled


_EMPTY = Context()


def _ctx(context):
    """Coerce ``None`` / a bare home string / a ``Context`` into one.

    A bare string assigns the home and nothing else, so the other
    five derive from it. It carries no autoseed choice: seeding is
    its own axis now, and a shorthand for one directory should not
    quietly decide another question.
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
    """Resolve one directory: per-call, then global, then derived."""
    context = _ctx(context)
    assigned = getattr(context, "%s_dir" % name)
    if assigned:
        return assigned
    assigned = _globals[name]
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


def autoseed(context=None):
    """Whether a resolution miss may seed from the built-in codex."""
    choice = _ctx(context).autoseed
    return _autoseed if choice is None else bool(choice)


def effective_home(explicit):
    """Return the explicit operation home, or the resolved home.

    For the small set of modules (``machine.py``, the backend
    adapters) that take an already-resolved plain directory rather
    than a ``Context`` — sometimes a real reliquary home, sometimes a
    machine's own materialization directory standing in for one.
    """
    return os.path.abspath(explicit) if explicit else home_dir()
