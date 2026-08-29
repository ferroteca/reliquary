# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Reliquary's own run facts -- the `rlq.*` namespace.

Facts are values Reliquary computes from the host machine. A
property's `default=` derivation can reference them, but no user
source can set them. Each fact's derivation is documented here, next
to its own definition, and that documentation is part of the fact's
contract. When a fact is empty or can't be determined, that counts as
unanswerable on purpose: a derivation that reads it simply gets no
answer, and property resolution falls through to the next candidate
or to asking the user.

The catalog is kept small on purpose. Adding a new fact is a real
design decision, the same as adding any other source tier (see
docs/spec/script-properties.md). Derivation syntax will never grow
transforms -- normalization belongs here, in a fact's own definition;
any other computation belongs in the embedding API.

Spec: docs/spec/script-properties.md, "The property sources".
"""

import getpass
import os
import re

from .errors import InternalError

_ENV_PREFIX = "rlq.env."

def _host_username():
    """The host's login name, normalized into a login-safe form.

    Lowercases the name, collapses any run of characters outside
    `[a-z0-9._-]` into a single `-`, and trims leading/trailing `-`
    or `.`. This conservative shape is accepted by most guest login
    systems. If the login name can't be read, the fact is
    unanswerable.
    """
    try:
        raw = getpass.getuser()
    except Exception:
        return None
    normalized = re.sub(r"[^a-z0-9._-]+", "-", raw.strip().lower())
    normalized = normalized.strip("-.")
    return normalized or None

def _host_full_name():
    """The host account's descriptive (display) name, or None.

    On Windows this reads the account's display name; on POSIX it
    reads the first comma-separated part of the GECOS field. This is
    often empty, and an empty value counts as an unanswerable fact
    on purpose.
    """
    if os.name == "nt":
        return _windows_full_name()
    return _posix_full_name()

def _windows_full_name():
    try:
        import ctypes
        NameDisplay = 3
        size = ctypes.c_ulong(0)
        ctypes.windll.secur32.GetUserNameExW(NameDisplay, None, ctypes.byref(size))
        if not size.value:
            return None
        buffer = ctypes.create_unicode_buffer(size.value)
        if ctypes.windll.secur32.GetUserNameExW(
                NameDisplay, buffer, ctypes.byref(size)):
            return buffer.value or None
    except Exception:
        return None
    return None

def _posix_full_name():
    try:
        import pwd
        gecos = pwd.getpwuid(os.getuid()).pw_gecos
    except Exception:
        return None
    name = (gecos or "").split(",", 1)[0].strip()
    return name or None

def _host_env(name):
    """The value of one host environment variable, unchanged, or None.

    This is the raw escape hatch alongside the curated facts above: a
    derivation that reads `rlq.env.<NAME>` is inherently
    host-specific. The variable name lookup follows whatever case
    rules the platform uses. An unset or empty variable is
    unanswerable.
    """
    if not name:
        return None
    value = os.environ.get(name)
    return value or None

# The curated facts. Each one is a zero-argument function that
# computes its value. `rlq.env.<NAME>` isn't listed here because the
# part after `rlq.env.` is a parameter, so it's handled separately
# in _host_env.
_CATALOG = {
    "rlq.host.username": _host_username,
    "rlq.host.full-name": _host_full_name,
}

def is_fact(key):
    """Whether `key` names a Reliquary run fact (something in the `rlq.*` namespace)."""
    return key in _CATALOG or key.startswith(_ENV_PREFIX)

def resolve(key):
    """Return the value of the fact named by `key`, or None if it is unavailable or empty.

    Raises KeyError if `key` is outside the known `rlq.*` catalog.
    In practice this shouldn't happen at run time, because the
    static reference check (V6) has already ruled out unknown keys
    before a run starts.
    """
    if key in _CATALOG:
        return _CATALOG[key]()
    if key.startswith(_ENV_PREFIX):
        return _host_env(key[len(_ENV_PREFIX):])
    raise InternalError(key)
