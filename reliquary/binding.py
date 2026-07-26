# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Binding declared script properties before a run.

A script declares each property it consumes; before the machine
starts, every declaration is bound from the first source that
answers. The flattened order is normative in
docs/spec/script-spec.md, "The property sources":

    1. an explicit --property value      (the caller's answer)
    2. a blueprint parameter             (the design's answer)
    3. RELIQUARY_PROPERTY_* environment  (the session's answer)
    4. the user properties file          (the person's answer)
    5. the declared derivation           (the script's answer)  [T4]
    6. the interactive ask               (a person, once per key)

This module owns steps 1-4 and 6; the declared derivation (5) lands
with T4 and slots in between the file and the ask without disturbing
the ranks around it — the model's own claim that a new tier is a
one-line insertion (D19).

Binding finishes before any media is materialized or any machine is
created or started (G3), so a missing value fails a run early rather
than after a long machine start, and a program never hangs on a
hidden prompt.
"""

import collections
import getpass
import os
import sys

from . import credentials, facts, properties
from .errors import PreflightError

class PropertyBindingError(PreflightError):
    """A declared property could not be bound before the run.

    Binding is preflight — it finishes before any media materializes
    or any machine starts — so this is a PREFLIGHT ERROR, exit ``3``.
    """

# The sources named in provenance, for check-script and the run's
# event stream.
FLAG = "--property"
PARAMETER = "blueprint parameter"
ENVIRONMENT = "environment"
FILE = "properties file"
DERIVATION = "declared derivation"
ASK = "interactive ask"

def _env_name(key):
    """The RELIQUARY_PROPERTY_* variable a key mangles to.

    Uppercased, with '.', '-' and '_' all mapped to '_'. The mapping
    can collide (`a.b` and `a-b` land together); a run consulting two
    keys that collide fails, naming both.
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
        """Bind one declared property, top source down.

        The parameter tier is special: a *direct* value answers, and
        a *redirect* substitutes another key into the env/file lookup
        and preempts the declared key's own env/file entry (a redirect
        "replaces resolution of the declared key entirely"). Either
        way, an unanswered key still reaches the ask, under its own
        declaration and prompt.
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
                # check-script names what *would* answer; with no
                # concrete source, an interactive run would ask.
                self._sources[key] = ASK
                return
            raise PropertyBindingError(
                f"the property {key!r} has no value from any source and "
                "there is no interactive terminal to ask; supply it with "
                f"--property, a blueprint parameter, {_env_name(key)}, "
                "or the properties file")
        value, source = answer
        self._sources[key] = source
        if value is not None:
            self._values[key] = value
        if kind == "secret":
            self._secret_keys.add(key)

    def _parameter_answer(self, key, kind):
        """The parameter tier, and the env/file it governs the key for.

        With no parameter, the env/file lookup is on the declared key
        itself. A direct parameter answers outright. A redirect moves
        the lookup to its target key and labels the provenance, but
        does not itself reach the ask.
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
        """Environment then properties file, for one lookup key."""
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
                    "declaration")
            if self._dry_run:
                # A dry pass names the source without reading the value.
                return (None, FILE)
            value = properties.get_secret(
                key, context=self._context,
                properties_file=self._properties_file)
            if value is None:
                raise PropertyBindingError(
                    f"the secret {key!r} is marked in the properties file "
                    "but its credential is missing on this host; set it "
                    f"with 'rlq set-property {key} --secret'")
            return (value, FILE)
        if kind == "secret":
            raise PropertyBindingError(
                f"{key!r} is declared secret but the properties file holds "
                "an ordinary value under that key; store it as a secret")
        return (stored, FILE)

    def _derivation_answer(self, declaration):
        """The script's own answer: the first candidate that resolves.

        Candidates are tried in declaration order; the first whose
        references all resolve to non-empty values answers. A literal
        candidate (no references) always answers, so it stops
        resolution here. A candidate touching an empty or unavailable
        fact — or a declared key that itself did not bind — does not
        answer, and resolution falls through to the ask.
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
        """A derivation reference: a bound declared key, or an rlq fact.

        Static validation (S6) guaranteed the key is one or the other,
        so a fact lookup here never raises. A declared key not yet in
        the bound set resolves to None — it did not answer — which the
        dependency ordering makes deterministic.
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
                f"{key} --secret' or inject it through {_env_name(key)}")
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
        """The bound secret values, for the runtime's redaction."""
        return {self.values[key] for key in self.secret_keys
                if self.values.get(key)}

    def __bool__(self):
        return bool(self.values)

def _preflight_environment(declarations):
    """Fail closed when two consulted keys mangle to one variable."""
    seen = {}
    for declaration in declarations:
        name = _env_name(declaration.key)
        if name in seen and seen[name] != declaration.key:
            raise PropertyBindingError(
                f"the properties {seen[name]!r} and {declaration.key!r} "
                f"both map to {name}; rename one so the environment can "
                "tell them apart")
        seen[name] = declaration.key

def _validate_explicit(declarations, explicit):
    """Every --property key must be declared by the running script."""
    if not explicit:
        return
    declared = {declaration.key for declaration in declarations}
    for key in explicit:
        if key not in declared:
            raise PropertyBindingError(
                f"--property {key}=... is not declared by this script")

def _binding_order(declarations):
    """Order declarations so a derivation's referents bind first.

    A `default=` may reference another declared key's bound value, so
    that key must resolve first. The order is a stable topological
    sort over those edges — declaration order otherwise — and the
    static acyclic guarantee (S6) means it always exists.
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
    """Bind every declared property, or fail closed naming the key.

    ``asker`` is called ``asker(key, prompt, secret) -> value`` for a
    key no earlier source answered; pass ``None`` for a
    noninteractive run, where an unanswered key is an error. Returns
    :class:`BoundProperties`.
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
    """An interactive asker, or None when there is no terminal.

    Asking requires both stdin and stderr to be ttys: the prompt
    writes to stderr and the answer reads from stdin (the CLI output
    discipline). Without a terminal the binder gets no asker and an
    unresolved property fails before the machine starts, so a program
    never hangs on a hidden prompt.
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

# A bare key referenced by a media location has no `property` node to
# declare it — the reference site is the declaration. It binds as
# ordinary text through the same order minus the derivation (which
# needs a `default=` a location cannot carry).
_LocationKey = collections.namedtuple(
    "_LocationKey", ("key", "kind", "prompt", "defaults"))

def bind_keys(keys, *, parameters=None, explicit=None, properties_file=None,
              context=None, asker=None):
    """Bind a set of bare keys through the source order, as text.

    The location-reference counterpart of :func:`bind_properties`:
    keys named by a media `location` (or `sha256`) with no `property`
    declaration behind them. Returns ``{key: value}``; an unbound key
    raises :class:`PropertyBindingError`.
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

def describe_sources(script, *, parameters=None, explicit=None,
                     properties_file=None, context=None):
    """Name each declared property's supplying source, without a run.

    The dry counterpart of :func:`bind_properties` for check-script:
    it consults the same sources in order, never prompts, never reads
    a secret's value, and never fails on an unanswered key — an
    interactive run would ask, so its source is reported as the ask.
    Returns ``{key: source}``.
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
