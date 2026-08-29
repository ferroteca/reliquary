# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The host credential store.

A secret property's value never enters `user.properties`: the file
holds an `@secret` marker, and the actual value lives in the host's
protected credential service, keyed by the absolute path of the
properties file holding that marker plus the property name
(docs/spec/script-properties.md, "Secret storage").

Other code should depend on what this module can do, not on how it
does it. Every operation here goes through one provider object with
three methods (get/set/delete password) — the same shape the
`keyring` library already has, so the real default provider is
`keyring` itself, and a test double is just three plain functions
matching that shape. That is the extension point where support for
another backend, such as a corporate secrets service, would be
added later if needed, and it is what lets the rules below be
tested without a real credential store on the test machine.

Windows is the delivered host (AGENTS.md), so Credential Manager is
the only backend actually exercised; `keyring` reaching Keychain or
a Secret Service provider follows from the same code path but is
untested.

There is no plaintext fallback anywhere. A host with no usable
store fails with an error naming what it could not reach.
"""

import os

from .errors import PreflightError

_SERVICE_PREFIX = "reliquary"

_provider = None

class CredentialError(PreflightError):
    """The credential store could not be reached or used.

    A PREFLIGHT ERROR (exit code 3): the request itself is valid, but
    something about the world — here, the host's credential store —
    can't satisfy it. It subclasses the root error class directly,
    the way it did back when the four error classes lined up with
    stages of a script run (D58 made those four classes apply
    everywhere, not just to scripts).
    """

def scope_for(path):
    """Return the store scope for a properties file path.

    The scope is the file's absolute path, so a `--properties` file
    and the home's own file never share a secret, and copying a
    properties file elsewhere copies names but not credentials.
    """
    return f"{_SERVICE_PREFIX}:{os.path.abspath(path)}"

class _Keyring:
    """The default provider: the host's own credential service."""

    def __init__(self, keyring):
        self._keyring = keyring

    def _guarded(self, action, call):
        from keyring.errors import KeyringError
        try:
            return call()
        except KeyringError as error:
            raise CredentialError(
                f"the host credential store could not {action}: "
                f"{error}", rule_id="store.unusable") from error

    def get_password(self, service, name):
        return self._guarded(
            "be read", lambda: self._keyring.get_password(service, name))

    def set_password(self, service, name, value):
        return self._guarded(
            "be written",
            lambda: self._keyring.set_password(service, name, value))

    def delete_password(self, service, name):
        return self._guarded(
            "be updated",
            lambda: self._keyring.delete_password(service, name))

def _default_provider():
    """Return the keyring-backed provider, or raise an error rather
    than fall back to something insecure."""
    try:
        import keyring
    except ImportError as error:  # pragma: no cover - install-shaped
        raise CredentialError(
            "secret properties need the 'keyring' package for the "
            "host credential store; there is no plaintext "
            "fallback", rule_id="store.missing-dependency") from error
    from keyring.backends.fail import Keyring as FailKeyring
    if isinstance(keyring.get_keyring(), FailKeyring):
        raise CredentialError(
            "this host has no usable credential store, so secret "
            "properties cannot be stored or read; there is no "
            "plaintext fallback", rule_id="store.unavailable")
    return _Keyring(keyring)

def _current_provider():
    global _provider
    if _provider is None:
        _provider = _default_provider()
    return _provider

def _set_provider(provider):
    """Install a provider (tests), returning the previous one."""
    global _provider
    previous = _provider
    _provider = provider
    return previous

def read_secret(scope, name):
    """Return the stored secret, or None when there is none."""
    return _current_provider().get_password(scope, name)

def has_secret(scope, name):
    """Return True when a credential exists for this scope and name."""
    return read_secret(scope, name) is not None

def store_secret(scope, name, value):
    """Store a secret, replacing any value already there."""
    _current_provider().set_password(scope, name, value)

def delete_secret(scope, name):
    """Delete a secret, reporting whether one was there.

    Deleting a credential that isn't there is not an error: since
    `unset_property` removes the marker line before it removes the
    credential, a cleanup pass calling this can legitimately find
    nothing left to remove.
    """
    provider = _current_provider()
    try:
        from keyring.errors import PasswordDeleteError
    except ImportError:  # pragma: no cover - install-shaped
        PasswordDeleteError = ()
    try:
        provider.delete_password(scope, name)
    except CredentialError:
        if provider.get_password(scope, name) is None:
            return False
        raise
    except PasswordDeleteError:
        return False
    return True
