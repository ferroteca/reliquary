# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""The host credential store.

A secret property's value never enters `user.properties`: the file
holds an `@secret` marker and the value lives in the host's
protected credential service, scoped by the absolute path of the
properties file holding that marker and by the property name
(docs/spec/script-properties.md, "Secret storage").

The public contract is the *capability*, not the library. Everything
here goes through one three-method provider — the shape `keyring`
already has, so the default provider is `keyring` itself and a test
double is three functions. That seam is where provider plurality
lands when a corporate secrets service earns its keep, and it is
what lets the rules below be tested on any host.

Windows is the delivered host (AGENTS.md), so Credential Manager is
the only backend actually exercised; `keyring` reaching Keychain or
a Secret Service provider is correct-by-construction and untested.

There is no plaintext fallback anywhere. A host with no usable
store fails closed naming what it could not reach.
"""

import os

from .errors import PreflightError

_SERVICE_PREFIX = "reliquary"

_provider = None

class CredentialError(PreflightError):
    """The credential store could not be reached or used.

    A PREFLIGHT ERROR (exit 3): the request is legal and the world —
    here the host's credential store — does not satisfy it. It
    subclassed the root directly while the four classes were read as
    tiers of a script run (D58 generalized them).
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
                f"{error}") from error

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
    """Return the keyring-backed provider, or fail closed."""
    try:
        import keyring
    except ImportError as error:  # pragma: no cover - install-shaped
        raise CredentialError(
            "secret properties need the 'keyring' package for the "
            "host credential store; there is no plaintext "
            "fallback") from error
    from keyring.backends.fail import Keyring as FailKeyring
    if isinstance(keyring.get_keyring(), FailKeyring):
        raise CredentialError(
            "this host has no usable credential store, so secret "
            "properties cannot be stored or read; there is no "
            "plaintext fallback")
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

    Deleting an absent credential is not an error: the fail-safe
    update order removes a marker before its credential, so a
    cleanup pass legitimately finds nothing left to remove.
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
