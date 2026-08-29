# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Binds a script's declared properties to values before a run starts.

A script declares each property it uses. Before the machine starts,
each declaration is bound to a value from the first source, in this
order, that has an answer for it. This order is fixed by
docs/spec/script-spec.md, "The property sources":

    1. an explicit --property value      (the caller's answer)
    2. a blueprint parameter             (the design's answer)
    3. RELIQUARY_PROPERTY_* environment  (the session's answer)
    4. the user properties file          (the person's answer)
    5. the declared derivation           (the script's answer)
    6. the interactive ask               (a person, once per key)

This module implements all six sources. The declared derivation
(source 5) was added later (milestone 8, T4) and was inserted
between the file and the ask without disturbing the order of the
others -- a one-line insertion, exactly as the source-tier model
claims a new tier should be (D19), which this confirms.

Binding always finishes before any media file is created and before
any machine is created or started (G3). That way a missing value
fails the run early, instead of after a long machine startup, and
the program never hangs waiting on a prompt the caller doesn't
expect.
"""

import collections
import getpass
import os
import sys

from . import credentials, facts, properties
from .errors import PreflightError

class PropertyBindingError(PreflightError):
    """Raised when a declared property can't be bound before the run starts.

    Binding happens during preflight -- before any media file is
    created and before any machine starts -- so this is a preflight
    error, and it exits with code ``3``.
    """

# Names for each source, used when reporting where a value came
# from -- in a dry run and in the run's event stream.
FLAG = "--property"
PARAMETER = "blueprint parameter"
ENVIRONMENT = "environment"
FILE = "properties file"
DERIVATION = "declared derivation"
ASK = "interactive ask"

def _env_name(key):
    """The RELIQUARY_PROPERTY_* environment variable name a key maps to.

    Uppercases the key and maps '.', '-', and '_' all to '_'. This
    mapping can collide -- `a.b` and `a-b` both map to the same
    variable name -- and a run that consults two keys which collide
    fails, naming both.
    """
    mangled = key.upper()
    for character in ".-":
        mangled = mangled.replace(character, "_")
    return "RELIQUARY_PROPERTY_" + mangled

class _Binder:
    """One binding pass over one script's declarations."""

    def __init__(self, *, parameters, explicit, properties_file, context,
                 asker, dry_run=False):
        self._parameters = parameters or {}
        self._explicit = explicit or {}
        self._properties_file = properties_file
        self._context = context
        self._asker = asker
        self._dry_run = dry_run
        self._values = {}
        self._sources = {}
        self._secret_keys = set()

    # -- the cascade ---------------------------------------------

    def bind(self, declaration):
        """Bind one declared property, trying each source from the top down.

        The parameter tier is special: a *direct* parameter value
        answers immediately. A *redirect* parameter instead
        substitutes a different key into the environment/file
        lookup, replacing the declared key's own environment/file
        lookup entirely. Either way, if nothing answers, the key
        still reaches the ask, using its own declaration and prompt.
        """
        key = declaration.key
        kind = declaration.kind

        answer = self._explicit_answer(key, kind)
        if answer is None:
            answer = self._parameter_answer(key, kind)
        if answer is None:
            answer = self._derivation_answer(declaration)
        if answer is None:
            answer = self._ask(declaration)
        if answer is None:
            if self._dry_run:
                # A dry run reports what *would* answer: since no
                # source has a concrete value, an interactive run
                # would fall through to asking.
                self._sources[key] = ASK
                return
            raise PropertyBindingError(
                f"the property {key!r} has no value from any source and "
                "there is no interactive terminal to ask; supply it with "
                f"--property, a blueprint parameter, {_env_name(key)}, "
                "or the properties file",
                rule_id="prop.unbound")
        value, source = answer
        self._sources[key] = source
        if value is not None:
            self._values[key] = value
        if kind == "secret":
            self._secret_keys.add(key)

    def _parameter_answer(self, key, kind):
        """Try the parameter tier, then the environment/file lookup it points to.

        If there is no parameter for this key, the environment/file
        lookup uses the declared key itself. A direct parameter
        answers right away. A redirect parameter moves the
        environment/file lookup to a different target key and labels
        the source accordingly, but if that lookup finds nothing,
        this returns None -- it does not itself fall through to the
        ask; the caller does that.
        """
        binding = self._parameters.get(key)
        if binding is None:
            return self._env_then_file(key, kind)
        if isinstance(binding, str):
            return (binding, PARAMETER)
        target = binding["property"]
        answer = self._env_then_file(target, kind)
        if answer is None:
            return None
        value, source = answer
        return (value, f"{PARAMETER} -> {source}")

    def _env_then_file(self, key, kind):
        """Look up one key: the environment variable first, then the properties file."""
        name = _env_name(key)
        value = os.environ.get(name)
        if value is not None:
            return (value, ENVIRONMENT)
        return self._from_file(key, kind)

    def _from_file(self, key, kind):
        stored = properties.get_property(
            key, context=self._context,
            properties_file=self._properties_file)
        if stored is None:
            return None
        if properties.is_secret(stored):
            if kind != "secret":
                raise PropertyBindingError(
                    f"{key!r} is declared {kind} but the properties file "
                    "holds a secret under that key; unset it or fix the "
                    "declaration",
                    rule_id="prop.secret-under-plain-key")
            if self._dry_run:
                # A dry run reports the source without reading the
                # actual secret value.
                return (None, FILE)
            value = properties.get_secret(
                key, context=self._context,
                properties_file=self._properties_file)
            if value is None:
                raise PropertyBindingError(
                    f"the secret {key!r} is marked in the properties file "
                    "but its credential is missing on this host; set it "
                    f"with 'rlq set-property {key} --secret'",
                    rule_id="prop.credential-missing")
            return (value, FILE)
        if kind == "secret":
            raise PropertyBindingError(
                f"{key!r} is declared secret but the properties file holds "
                "an ordinary value under that key; store it as a "
                "secret", rule_id="prop.plain-under-secret-key")
        return (stored, FILE)

    def _derivation_answer(self, declaration):
        """Try the script's own derivation: the first candidate that resolves.

        Candidates are tried in the order they are declared. The
        first one whose references all resolve to non-empty values
        is the answer. A literal candidate (one with no references)
        always resolves, so it always answers here. A candidate that
        touches an empty or unavailable fact -- or a declared key
        that itself did not bind -- does not answer, and resolution
        moves on, eventually falling through to the ask.
        """
        for candidate in declaration.defaults:
            resolved = self._resolve_candidate(candidate)
            if resolved is not None:
                return (resolved, DERIVATION)
        return None

    def _resolve_candidate(self, candidate):
        rendered = []
        for part in candidate.parts:
            if isinstance(part, str):
                rendered.append(part)
                continue
            value = self._reference_value(part.key)
            if not value:
                return None
            rendered.append(value)
        return "".join(rendered)

    def _reference_value(self, key):
        """Resolve one reference inside a derivation: a bound declared key, or an rlq fact.

        Static validation (V6) already guaranteed the key is one or
        the other, so looking it up as a fact here never raises. If
        the key is a declared key that has not bound yet, this
        returns None -- meaning it did not answer -- and the
        dependency ordering from _binding_order guarantees a
        referenced key is always bound before the keys that
        reference it, which keeps this deterministic.
        """
        if facts.is_fact(key):
            return facts.resolve(key)
        return self._values.get(key)

    def _explicit_answer(self, key, kind):
        if key not in self._explicit:
            return None
        if kind == "secret":
            raise PropertyBindingError(
                f"{key!r} is a secret and cannot be supplied with "
                "--property: process listings and shell history are not "
                "credential stores; store it with 'rlq set-property "
                f"{key} --secret' or inject it through "
                f"{_env_name(key)}", rule_id="prop.secret-on-flag")
        return (self._explicit[key], FLAG)

    def _ask(self, declaration):
        if self._asker is None:
            return None
        prompt = (declaration.prompt.text if declaration.prompt is not None
                  else declaration.key)
        value = self._asker(
            declaration.key, prompt, declaration.kind == "secret")
        if value is None:
            return None
        return (value, ASK)

    def result(self):
        return BoundProperties(
            dict(self._values), dict(self._sources),
            frozenset(self._secret_keys))

class BoundProperties:
    """The resolved bindings, each key's source, and which are secret."""

    def __init__(self, values, sources, secret_keys=frozenset()):
        self.values = values
        self.sources = sources
        self.secret_keys = secret_keys

    def secret_values(self):
        """The bound values that are secrets, so the runtime can redact them."""
        return {self.values[key] for key in self.secret_keys
                if self.values.get(key)}

    def __bool__(self):
        return bool(self.values)

def _preflight_environment(declarations):
    """Raise an error up front if two declared keys map to the same environment variable."""
    seen = {}
    for declaration in declarations:
        name = _env_name(declaration.key)
        if name in seen and seen[name] != declaration.key:
            raise PropertyBindingError(
                f"the properties {seen[name]!r} and {declaration.key!r} "
                f"both map to {name}; rename one so the environment can "
                "tell them apart",
                rule_id="prop.environment-collision")
        seen[name] = declaration.key

def _validate_explicit(declarations, explicit):
    """Every --property key must be declared by the running script."""
    if not explicit:
        return
    declared = {declaration.key for declaration in declarations}
    for key in explicit:
        if key not in declared:
            raise PropertyBindingError(
                f"--property {key}=... is not declared by this "
                "script", rule_id="prop.undeclared-flag")

def _binding_order(declarations):
    """Order declarations so any key a derivation references binds before it does.

    A `default=` derivation can reference another declared key's
    bound value, so that other key has to resolve first. This does a
    stable topological sort over those reference edges, keeping
    declaration order wherever two keys have no dependency between
    them. Static validation (V6) already guarantees there are no
    reference cycles, so this ordering always exists.
    """
    by_key = {d.key: d for d in declarations}
    ordered = []
    placed = set()

    def place(declaration):
        if declaration.key in placed:
            return
        placed.add(declaration.key)
        for candidate in declaration.defaults:
            for key in candidate.keys:
                referent = by_key.get(key)
                if referent is not None:
                    place(referent)
        ordered.append(declaration)

    for declaration in declarations:
        place(declaration)
    return ordered

def bind_properties(script, *, parameters=None, explicit=None,
                    properties_file=None, context=None, asker=None):
    """Bind every property a script declares, or raise an error naming the key that failed.

    ``asker`` is called as ``asker(key, prompt, secret) -> value``
    for any key that no earlier source answered. Pass ``None`` for a
    noninteractive run, where an unanswered key is an error. Returns
    a :class:`BoundProperties`.
    """
    declarations = list(script.properties)
    _validate_explicit(declarations, explicit)
    _preflight_environment(declarations)
    binder = _Binder(
        parameters=parameters, explicit=explicit,
        properties_file=properties_file, context=context, asker=asker)
    for declaration in _binding_order(declarations):
        binder.bind(declaration)
    return binder.result()

def console_asker():
    """Build an interactive asker function, or return None if there is no terminal to ask on.

    Asking requires both stdin and stderr to be ttys: the prompt is
    written to stderr and the answer is read from stdin, following
    the CLI's usual output rules. Without a terminal, the binder gets
    no asker at all, so an unresolved property fails before the
    machine starts instead of the program hanging on a prompt nobody
    can see.
    """
    if not (sys.stdin.isatty() and sys.stderr.isatty()):
        return None

    def ask(key, prompt, secret):
        text = prompt or key
        if secret:
            return getpass.getpass(f"{text}: ", stream=sys.stderr) or None
        print(f"{text}: ", end="", file=sys.stderr, flush=True)
        line = sys.stdin.readline()
        if not line:
            return None
        return line.rstrip("\n").rstrip("\r") or None

    return ask

# A bare key referenced by a media `location` has no `property` node
# declaring it -- the reference itself is the only declaration it
# gets. It binds as plain text, through the same source order but
# skipping the derivation source (that needs a `default=`, which a
# location cannot carry).
_LocationKey = collections.namedtuple(
    "_LocationKey", ("key", "kind", "prompt", "defaults"))

def bind_keys(keys, *, parameters=None, explicit=None, properties_file=None,
              context=None, asker=None):
    """Bind a set of bare keys through the usual source order, as plain text.

    This is the counterpart to :func:`bind_properties` for keys
    named by a media `location` (or `sha256`) that have no
    `property` declaration behind them. Returns ``{key: value}``. An
    unbound key raises :class:`PropertyBindingError`.
    """
    declarations = [
        _LocationKey(key=key, kind="text", prompt=None, defaults=())
        for key in sorted(keys)]
    _preflight_environment(declarations)
    binder = _Binder(
        parameters=parameters, explicit=explicit,
        properties_file=properties_file, context=context, asker=asker)
    for declaration in declarations:
        binder.bind(declaration)
    return binder.result().values

def describe_keys(keys, *, parameters=None, explicit=None,
                  properties_file=None, context=None):
    """Bind whatever a location's bare keys can bind without asking anyone.

    This is the dry-run counterpart of :func:`bind_keys`, the same
    way :func:`describe_sources` is the dry-run counterpart of
    :func:`bind_properties`: it checks the same sources in the same
    order, but never prompts, never reads a secret's actual value,
    and never fails on a key nothing answered. For a key that an
    interactive run would have to ask about, this reports the ask as
    its source and leaves it with no value.

    Returns a :class:`BoundProperties`: ``values`` holds whatever
    concretely bound (what a location can actually be rendered
    from), and ``sources`` names every key, including the ones that
    did not bind.
    """
    declarations = [
        _LocationKey(key=key, kind="text", prompt=None, defaults=())
        for key in sorted(keys)]
    _preflight_environment(declarations)
    binder = _Binder(
        parameters=parameters, explicit=explicit,
        properties_file=properties_file, context=context, asker=None,
        dry_run=True)
    for declaration in declarations:
        binder.bind(declaration)
    return binder.result()

def describe_sources(script, *, parameters=None, explicit=None,
                     properties_file=None, context=None):
    """Name the source that would supply each declared property, without running anything.

    This is the dry-run counterpart of :func:`bind_properties`: it
    checks the same sources in the same order, never prompts, never
    reads a secret's actual value, and never fails on a key nothing
    answered. For a key that an interactive run would have to ask
    about, this reports the ask as its source. Returns ``{key:
    source}``.
    """
    declarations = list(script.properties)
    _validate_explicit(declarations, explicit)
    _preflight_environment(declarations)
    binder = _Binder(
        parameters=parameters, explicit=explicit,
        properties_file=properties_file, context=context, asker=None,
        dry_run=True)
    for declaration in _binding_order(declarations):
        binder.bind(declaration)
    return binder.result().sources
