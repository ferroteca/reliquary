# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Reliquary-owned run facts — the `rlq.*` namespace.

Facts are values Reliquary computes from the host, referenceable in a
property's `default=` derivation and unwritable by any user source.
Each fact's derivation is part of its contract (each is documented
with its definition here); an empty or unavailable fact is
*unanswerable* by design, so a derivation that reaches for one simply
does not answer and resolution falls through to the next candidate or
the ask.

The catalog is deliberately small. Growth is a design decision like
any new source tier (docs/spec/script-properties.md); transforms
in derivation syntax are permanently out — normalization lives here,
in a fact's definition, arbitrary computation in the embedding API.

Spec: docs/spec/script-properties.md, "The property sources".
"""

import getpass
import os
import re

from .errors import InternalError

_ENV_PREFIX = "rlq.env."

def _host_username():
    """The host login name, normalized to a login-safe form.

    Lowercased, non-`[a-z0-9._-]` runs collapsed to a single `-`, and
    surrounding `-`/`.` trimmed — a conservative shape most guest
    logins accept. An unresolvable login is unanswerable.
    """
    try:
        raw = getpass.getuser()
    except Exception:
        return None
    normalized = re.sub(r"[^a-z0-9._-]+", "-", raw.strip().lower())
    normalized = normalized.strip("-.")
    return normalized or None

def _host_full_name():
    """The host account's descriptive name, or None.

    Windows reads the account display name; POSIX reads the GECOS
    field's first comma-part. Frequently empty, and an empty value is
    an unanswerable fact by design.
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
    """A named host environment variable, verbatim, or None.

    The raw escape hatch beside the curated facts: a derivation that
    reads `rlq.env.<NAME>` is host-specific by construction. Lookup
    follows the platform's own case rules; an unset or empty variable
    is unanswerable.
    """
    if not name:
        return None
    value = os.environ.get(name)
    return value or None

# The curated facts, each a zero-argument derivation. `rlq.env.<NAME>`
# is handled separately because its tail is a parameter.
_CATALOG = {
    "rlq.host.username": _host_username,
    "rlq.host.full-name": _host_full_name,
}

def is_fact(key):
    """Whether a key names a Reliquary run fact (the `rlq.*` namespace)."""
    return key in _CATALOG or key.startswith(_ENV_PREFIX)

def resolve(key):
    """Return a fact's value, or None when it is unavailable/empty.

    Raises KeyError for a key outside the known `rlq.*` catalog, which
    the static reference check (S6) has already ruled out before a run.
    """
    if key in _CATALOG:
        return _CATALOG[key]()
    if key.startswith(_ENV_PREFIX):
        return _host_env(key[len(_ENV_PREFIX):])
    raise InternalError(key)
