# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The static-validation layer of the reliquary script language.

This module checks the V-numbered legality rules that the grammar
deliberately doesn't enforce itself (docs/spec/script-spec.md,
"Syntactic restrictions"). It checks them over the typed tree, so
each diagnostic can name the exact construct that violated the rule
and cite the rule's id:

- **V3** -- ``entry`` appears exactly in phased scripts;
- **V5** -- phase names are unique and durations are positive;
- **V7** -- an observation carries exactly one condition, on a
  known channel, of the right kind;
- **V8** -- a branching ``wait`` carries no condition of its own,
  has at least two handlers, and never appears inside a handler
  body;
- **V9** -- ``on`` only inside a branching ``wait``, ``always``
  only directly inside a reactive phase, no hybrid phase, and no
  ``with`` scope inside another on the same target;
- **V10** -- the two script shapes never mix, and every phase name
  a script transfers to is declared;
- **V11** -- nothing follows a terminating statement, and a
  sequential phase's statement list terminates;
- **V12** -- a phased script whose transition graph can cycle
  declares a header ``deadline``, the backstop that bounds the
  run.
- **V13** -- a watch pattern is non-empty, and a regex compiles;
- **V14** -- every ``press`` key belongs to the language's closed
  portable vocabulary;
- **V17** -- a stopped-only verb is never reached with the machine
  running, wherever a static pass can promise it runs at all.

The remaining rules are checked by the layers around this one: V1,
V2, and V4 belong to the lexer and the parser (the timing placement
matrix is checked as part of a node's signature), and the remaining
V14 vocabularies arrive along with the features that own them. V6 is
split between two places: the ``default=`` derivation half is
checked here, while the ``${key}`` references written inside
statement strings are checked when they are bound, not here. The
timing *model* itself -- which resolves the durations this module
checks -- lives in :mod:`reliquary.script_timing`.

This module works structurally over the tree, so it does not import
any node type; that keeps the parser free to import this module in
turn.
"""

import collections
import re

from . import facts
from .script_nodes import KEYWORDS, ScriptParseError
from .script_timing import parse_duration

_RESERVED = frozenset(KEYWORDS)


def _not_reserved(name, what, line, column):
    """Reject a node name that reuses a reserved keyword as an author-chosen identifier (V5).

    script-spec.md, "Grammar" says reserved node names cannot be
    used to name phases or property keys. The lexer only treats
    these words as keywords where a node name is allowed to start,
    so `phase enter` parses without error -- and without this check,
    it would declare a phase whose name collides with the verb
    `enter`, which neither a person nor `goto` could read
    unambiguously.
    """
    if name in _RESERVED:
        raise ScriptParseError(
            line, f"{what} may not be a reserved node name: {name}",
            column,
            rule_id="name.reserved-node")

# The observable channels, each with the condition kind it takes
# and its fixed set of allowed values. The screen is the default
# channel and is deliberately left out of this map: it has no named
# spelling of its own.
_CHANNELS = {"machine": ("state", ("stopped",))}
_TRANSFERS = ("goto", "finish")
# A drive key, as written in a blueprint field reference: a medium
# name plus an optional slot index, where a bare name means slot 0.
# Only the shape of the key is checked here -- whether a machine
# actually declares that slot is preflight's question, and answering
# it needs an actual machine to check against.
_SLOT_KEY = re.compile(r"([A-Za-z]+)([0-9]*)")
PORTABLE_KEY_NAMES = frozenset({
    "enter", "esc", "tab", "space", "backspace",
    "up", "down", "left", "right",
    "insert", "delete", "home", "end", "pageup", "pagedown",
    "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10",
    "f11", "f12", "ctrl", "alt", "shift",
})


def validate(script):
    """Check the static rules over a parsed script.

    Raises :class:`~reliquary.script_nodes.ScriptParseError` on the
    first violation. Source context is attached by the caller that
    knows the document's path.
    """
    _properties(script)
    _derivations(script)
    _http(script)
    _durations(script)
    _keys(script)
    _variables(script)
    _scoping(script)
    if script.phases:
        _phased(script)
    else:
        _linear(script)
    # This runs last: the flow analysis reads the transition graph,
    # so it can only run once V10 has confirmed every `goto` names a
    # phase that actually exists.
    _machine_flow(script)


# -- durations (V5) ----------------------------------------------

def _properties(script):
    """Property names are unique and outside reserved namespaces."""
    seen = {}
    for prop in script.properties:
        _not_reserved(prop.key, "a property key", prop.line, prop.column)
        _property_key(prop.key, prop.line, prop.column)
        if prop.key in seen:
            raise ScriptParseError(
                prop.line, f"duplicate property: {prop.key}",
                prop.column,
                rule_id="name.duplicate-property")
        seen[prop.key] = prop


def _derivations(script):
    """Check the `default=` derivation rules (V5, V6).

    These are checked statically because a derivation is not a
    runtime expression: whether it can answer -- or whether it is
    knowably unanswerable -- can be determined before the run even
    starts, so every error it could produce is caught here instead
    of later, at binding time.
    """
    declared = {prop.key: prop for prop in script.properties}
    for prop in script.properties:
        if not prop.defaults:
            continue
        if prop.kind == "secret":
            raise ScriptParseError(
                prop.line,
                f"a secret property may not carry default=: {prop.key}",
                prop.column, rule_id="prop.secret-default")
        # A literal candidate (no references) always answers, so any
        # candidate after it is dead code.
        for candidate in prop.defaults[:-1]:
            if not candidate.interpolated:
                raise ScriptParseError(
                    prop.line,
                    f"a literal default= must be the last candidate; "
                    f"those after it are dead: {prop.key}",
                    prop.column,
                    rule_id="prop.dead-default")
        for candidate in prop.defaults:
            for key in candidate.keys:
                _check_reference(prop, key, declared, facts)
    _forbid_derivation_cycles(script, declared)


def _check_reference(prop, key, declared, facts):
    if facts.is_fact(key):
        return
    target = declared.get(key)
    if target is None:
        raise ScriptParseError(
            prop.line,
            f"default= for {prop.key} references {key!r}, which is "
            "neither a declared property nor an rlq.* fact",
            prop.column,
            rule_id="prop.undefined-reference")
    if target.kind == "secret":
        raise ScriptParseError(
            prop.line,
            f"default= for {prop.key} references the secret {key!r}; "
            "no derivation may reference a secret", prop.column,
            rule_id="prop.secret-reference")


def _forbid_derivation_cycles(script, declared):
    """A `${key}` chain among derivations must be acyclic (V6)."""
    edges = {}
    for prop in script.properties:
        targets = set()
        for candidate in prop.defaults:
            targets.update(
                key for key in candidate.keys if key in declared)
        edges[prop.key] = targets
    state = {}  # unvisited / "open" / "closed"

    def visit(key, trail):
        if state.get(key) == "closed":
            return
        if state.get(key) == "open":
            cycle = " -> ".join(trail + [key])
            prop = declared[key]
            raise ScriptParseError(
                prop.line,
                f"default= derivations form a cycle: {cycle}",
                prop.column,
                rule_id="prop.derivation-cycle")
        state[key] = "open"
        for target in edges.get(key, ()):
            visit(target, trail + [key])
        state[key] = "closed"

    for key in edges:
        visit(key, [])


def _property_key(key, line, column):
    if key in ("text", "media", "secret"):
        raise ScriptParseError(
            line, f"{key!r} is reserved in property declarations",
            column,
            rule_id="name.property-is-a-kind")
    if key == "rlq" or key.startswith("rlq."):
        raise ScriptParseError(
            line,
            "property keys in the rlq namespace are reserved for "
            "reliquary-owned run facts", column,
            rule_id="name.property-reserved-namespace")
    if key == "reliquary" or key.startswith("reliquary."):
        raise ScriptParseError(
            line,
            "property keys in the reliquary namespace are reserved",
            column,
            rule_id="name.property-reserved-namespace")


# -- HTTP declarations -------------------------------------------

def _http(script):
    _http_statements(script)
    if script.http is None:
        if not _has_inline_http_start(script):
            _forbid_http_refs(script)
        return
    if not script.http.contents:
        raise ScriptParseError(
            script.http.line, "http requires at least one content entry",
            script.http.column,
            rule_id="http.no-content")
    _ports(script.http)
    _content_set(script.http.contents)


def _content_set(contents):
    names = {}
    paths = {}
    for content in contents:
        if content.name in names:
            raise ScriptParseError(
                content.line, f"duplicate content name: {content.name}",
                content.column,
                rule_id="http.duplicate-content-name")
        names[content.name] = content
        path = _plain(content.path, "content path", content.line,
                      content.column)
        if not path.startswith("/"):
            raise ScriptParseError(
                content.line,
                f"content path must begin with '/': {path!r}",
                content.column,
                rule_id="http.path-not-absolute")
        segments = path.split("/")
        if any(segment in (".", "..") for segment in segments):
            raise ScriptParseError(
                content.line,
                f"content path may not contain . or ..: {path!r}",
                content.column,
                rule_id="http.path-traversal")
        if path in paths:
            raise ScriptParseError(
                content.line, f"duplicate content path: {path}",
                content.column,
                rule_id="http.duplicate-content-path")
        paths[path] = content
        if content.body.spelling == "":
            raise ScriptParseError(
                content.line, f"content path {path!r} has an empty body",
                content.column,
                rule_id="http.empty-body")


def _http_statements(script):
    declared = set()
    if script.http is not None:
        declared = {content.name for content in script.http.contents}
    for statement in _all_statements(script):
        if statement.verb != "http":
            continue
        command = statement.arguments[0]
        if command not in ("start", "stop"):
            raise ScriptParseError(
                statement.line,
                f"http action must be start or stop: {command!r}",
                statement.column,
                rule_id="http.unknown-action")
        if command == "start" and script.http is None \
                and not statement.contents:
            raise ScriptParseError(
                statement.line,
                "http start requires declared or inline content",
                statement.column,
                rule_id="http.start-without-content")
        if command == "start":
            _content_set(statement.contents)
            for name in statement.arguments[1:]:
                if name not in declared:
                    raise ScriptParseError(
                        statement.line,
                        f"http start names undeclared content: {name}",
                        statement.column,
                        rule_id="http.undeclared-content")
        elif len(statement.arguments) > 1 or statement.contents:
            raise ScriptParseError(
                statement.line, "http stop takes no content names or block",
                statement.column,
                rule_id="http.stop-takes-nothing")


def _has_inline_http_start(script):
    return any(statement.verb == "http"
               and statement.arguments[0] == "start"
               and statement.contents
               for statement in _all_statements(script))


def _ports(http):
    for name in ("port_min", "port_max"):
        spelling = getattr(http, name)
        if spelling is None:
            continue
        port = int(spelling)
        if port < 1 or port > 65535:
            raise ScriptParseError(
                http.line, f"{name.replace('_', '-')} is not a TCP port: "
                f"{port}", http.column,
                rule_id="http.port-out-of-range")
    if http.port_min is not None and http.port_max is not None:
        if int(http.port_min) > int(http.port_max):
            raise ScriptParseError(
                http.line, "port-min must be less than or equal to port-max",
                http.column,
                rule_id="http.port-range-inverted")


def _plain(literal, what, line, column):
    if literal.interpolated:
        raise ScriptParseError(
            line, f"{what} may not contain property references", column,
            rule_id="http.reference-in-path")
    return literal.text


def _forbid_http_refs(script):
    for literal, line, column in _text_literals(script):
        for key in literal.keys:
            if key.startswith("rlq.http."):
                raise ScriptParseError(
                    line,
                    "rlq.http.* properties require an http block",
                    column,
                    rule_id="prop.http-without-block")


def _text_literals(script):
    for prop in script.properties:
        if prop.prompt is not None:
            yield prop.prompt, prop.line, prop.column
    for statement in _walk(script.statements):
        yield from _statement_literals(statement)
    for phase in script.phases:
        for statement in _walk(phase.statements, phase.handlers):
            yield from _statement_literals(statement)
    if script.http is not None:
        for content in script.http.contents:
            yield content.body, content.line, content.column
    for statement in _all_statements(script):
        for content in statement.contents:
            yield content.body, content.line, content.column


def _statement_literals(statement):
    for arg in statement.arguments:
        if hasattr(arg, "parts"):
            yield arg, statement.line, statement.column
    if statement.exclude is not None:
        yield statement.exclude, statement.line, statement.column
    for condition in statement.conditions:
        if hasattr(condition.value, "parts"):
            yield condition.value, condition.line, condition.column

def _durations(script):
    """Check that every written duration is positive.

    Where each timing modifier is allowed to be written is checked
    by the placement matrix, enforced through the node signatures
    (V2); this function checks the *value*, not the placement.

    **`pacing` is deliberately not checked here.** A bound of zero
    asks for something that can never happen, which is why
    `timeout`, `deadline`, and `stable` are checked in this
    function; `pacing` is different -- it is an interval, not a
    bound, and `0s` is a perfectly meaningful thing to write: "this
    guest is ready, don't wait." An author is entitled to make that
    claim about a screen they know. Rejecting `pacing=0s` would only
    push authors toward writing `pacing=1ms` instead, which claims
    the same thing less honestly. A negative pacing value needs no
    check either: a duration token can never carry a minus sign, so
    the lexer has already rejected it before this code would ever
    run.
    """
    for name in ("timeout", "deadline"):
        _positive(getattr(script, name), name,
                  script.headers.get(name, 1), 1)
    for phase in script.phases:
        for name in ("timeout", "deadline"):
            _positive(getattr(phase, name), name, phase.line, phase.column)
        _observed(_timed(phase.statements, phase.handlers))
    _observed(_timed(script.statements))


def _observed(nodes):
    for node in nodes:
        for name in ("timeout", "stable"):
            _positive(getattr(node, name, None), name, node.line,
                      node.column)


def _positive(spelling, name, line, column):
    if spelling is not None and parse_duration(spelling) <= 0:
        raise ScriptParseError(
            line, f"{name} must be a positive duration: {spelling}",
            column,
            rule_id="time.non-positive")


def _timed(statements, handlers=()):
    """Yield every node that may carry a timing modifier."""
    for handler in handlers:
        yield handler
        yield from _timed(handler.statements)
    for statement in statements:
        if _scoped(statement) is not None:
            yield from _timed(_scoped(statement))
            continue
        if not _is_statement(statement):
            continue
        yield statement
        yield from _timed((), statement.handlers)


# -- portable keys (V14) -----------------------------------------

def _all_statements(script):
    """Every statement of a script, nested bodies included."""
    statements = list(_walk(script.statements))
    for phase in script.phases:
        statements.extend(_walk(phase.statements, phase.handlers))
    return statements


def reach(script):
    """Return ``(statically reachable, total)`` statement counts.

    **A statement counts as statically reachable when reaching it
    does not depend on anything the guest does.** That is the honest
    limit on what a dry run can report: a plan is only ever a plan,
    and reporting how much of the script it could not account for is
    what keeps the report from claiming a completeness it does not
    have (P11, at the report level).

    A linear script is entirely reachable except for its handler
    bodies. In a phased script, the walk starts at ``entry`` and
    follows only the ``goto``s in a phase's **own** statement list,
    never one inside a handler: a handler only fires when the guest
    does something, so every statement in its body -- and every
    phase only that handler can reach -- depends on the guest. A
    reactive phase is made up of handlers alone, so it contributes
    nothing reachable and transfers nothing that can be determined
    statically.
    """
    total = len(_all_statements(script))
    if not script.phases:
        return len(list(_sequence(script.statements))), total
    reachable = 0
    seen = set()
    pending = [script.entry]
    by_name = {phase.name: phase for phase in script.phases}
    while pending:
        name = pending.pop()
        if name in seen or name not in by_name:
            continue
        seen.add(name)
        phase = by_name[name]
        reachable += len(phase.statements)
        for statement in phase.statements:
            if statement.verb == "goto":
                pending.append(statement.arguments[0])
    return reachable, total


def _variables(script):
    """Check that every ``set`` key is outside reliquary's reserved namespaces.

    A machine variable is a name the script author chose for their
    own value (P18), so the only rule is that it must never collide
    with a name reliquary might introduce later.
    """
    for statement in _all_statements(script):
        if statement.verb != "set":
            continue
        key = statement.arguments[0]
        head = key.split(".", 1)[0]
        if head in ("rlq", "reliquary"):
            raise ScriptParseError(
                statement.line,
                f"machine-variable keys in the {head} namespace are "
                f"reserved: {key}", statement.column,
                rule_id="name.variable-reserved-namespace")


def _keys(script):
    """Check that every ``press`` argument belongs to the portable key set.

    A chord can also include one-character printable keys, as in
    ``ctrl+c``. A bare single character on its own is still just
    text, and must be sent with ``type`` or ``enter`` instead of
    ``press``.
    """
    for statement in _all_statements(script):
        if statement.verb != "press":
            continue
        for spelling in statement.arguments:
            parts = spelling.split("+")
            unknown = next((part for part in parts
                            if part not in PORTABLE_KEY_NAMES
                            and not (len(parts) > 1 and len(part) == 1)),
                           None)
            if unknown is not None:
                raise ScriptParseError(
                    statement.line,
                    f"{unknown!r} is not a portable key name",
                    statement.column,
                    rule_id="key.not-portable")


# -- scoped machine-state changes (V2, V5, V9, V10) --------------

def _scoping(script):
    """Check the rules a ``with`` block has to follow.

    There are four rules here, and each is really an instance of a
    rule kind checked elsewhere too. What a block is allowed to hold
    is a signature rule (V2). That no two scopes can own the same
    target is a placement rule (V9): nested scopes on the same
    target would make what a restore puts back depend on which
    order they unwound in, which a reader should not have to work
    out. That `boot` names each drive only once is a uniqueness rule
    (V5), and it canonicalizes each drive key first, since an alias
    and its indexed form (like `cdrom` and `cdrom0`) are the same
    slot. And that the two script shapes never mix is V10 -- a rule
    the grammar used to be able to decide on its own but no longer
    can, because a `with` head by itself says nothing about which
    shape follows it.
    """
    phased = bool(script.phases)
    _units(script.statements, phased, top=True)
    _targets(script.statements, ())
    for scope in script.scopes:
        if scope.head == "boot":
            _boot_keys(scope)


def _units(units, phased, top):
    """A block wraps the enclosing shape's own units, and only those."""
    for unit in units:
        inner = _scoped(unit)
        if inner is not None:
            _units(inner, phased, top=False)
            continue
        if not (phased and _is_statement(unit)):
            continue
        if top:
            raise ScriptParseError(
                unit.line,
                f"{unit.verb} is outside every phase: a script is phased "
                "or linear, and a phased one holds its statements in "
                "phases", unit.column, rule_id="flow.mixed-shapes")
        raise ScriptParseError(
            unit.line,
            f"a with block in a phased script wraps phases, and this one "
            f"holds the statement {unit.verb}", unit.column,
            rule_id="scope.wraps-the-wrong-unit")


def _targets(units, chain):
    """One scope per target; scopes on different targets nest freely."""
    for unit in units:
        inner = _scoped(unit)
        if inner is None:
            continue
        if unit.target in chain:
            raise ScriptParseError(
                unit.line,
                f"{unit.target} is already scoped by an enclosing with: "
                "one scope per target, so what a restore puts back is "
                "never in question", unit.column,
                rule_id="scope.doubled-target")
        _targets(inner, chain + (unit.target,))


def _boot_keys(scope):
    """Check that a scoped boot prefix names each drive only once (V5).

    This checks by slot, not by spelling: `cdrom` is the blueprint's
    alias for `cdrom0`, so the two names refer to the same drive,
    and a boot prefix cannot put that one drive in two places.
    Whether the drive actually exists is checked separately, in
    preflight, where `set-boot`'s keys are checked against an actual
    machine.
    """
    seen = {}
    for key in scope.action.arguments:
        slot = _canonical_slot(key)
        if slot in seen:
            raise ScriptParseError(
                scope.line,
                f"boot names one drive twice: {seen[slot]} and {key}",
                scope.column, rule_id="drive.boot-duplicate")
        seen[slot] = key


def _canonical_slot(key):
    """A drive key's canonical spelling, or the key where it is not one."""
    match = _SLOT_KEY.fullmatch(key)
    return f"{match.group(1)}{match.group(2) or '0'}" if match else key


# -- where the machine is (V17) ----------------------------------
#
# `set-boot` and a scoped `boot` head both write a launch-time
# firmware boot order, and that write is only valid while the
# machine is stopped -- that is a property of the machine itself
# (D15's Q1). If the script reaches one of these with the machine
# running, it currently fails closed, by name, but only at RUN
# time -- and for the shape of script that triggers this (flip the
# boot device, start, install, stop, flip back), run time can mean
# after five minutes of installing.
#
# **The script text already contains everything needed to decide
# this ahead of time.** The header declares the machine's starting
# state, and the language knows exactly which verbs start and stop
# the machine, so the answer -- is the machine running or stopped at
# this point -- is available before anything ever reaches a guest.
#
# **This rule only checks what the rest of the static pass already
# commits to checking.** A handler body only runs because of a
# guest's action, not because of the plan -- `reach` above already
# draws that same line -- so this rule only speaks about statements
# a static pass can *promise* will run, and stays silent everywhere
# else. A handler body is still walked, to track its *effect* on the
# machine, but it is never judged directly, because whether control
# reaches it is the guest's call, not the script's. And when two
# possible paths through the script disagree about where the machine
# is, the answer becomes "unknown" rather than picking one: a false
# refusal here would be worse than the late runtime failure this
# rule is meant to replace.

_STOPPED, _RUNNING, _UNKNOWN = "stopped", "running", "unknown"

#: One program point: where the machine is, and the phrase a
#: diagnostic uses to explain how it got there. Naming the cause is
#: most of the value here -- "the machine is running here" is just a
#: verdict, but "started at line 7" tells the author what to fix.
_Where = collections.namedtuple("_Where", "state why")


def _machine_flow(script):
    """Refuse a stopped-only verb wherever the plan promises it runs with the machine running."""
    if script.machine == "stopped":
        start = _Where(_STOPPED, "the machine header says stopped")
    else:
        start = _Where(
            _RUNNING,
            "the machine header says running" if script.machine
            else "the machine header defaults to running")
    if script.phases:
        _phased_flow(script, start)
    else:
        _flow(script.statements, start, judge=True)


def _join(here, there):
    """Merge two paths' answers about where the machine is; disagreement produces no answer."""
    if here is None:
        return there
    if here.state != there.state:
        return _Where(_UNKNOWN, None)
    return here if here.why == there.why else _Where(here.state, None)


def _after(statement, where):
    """Where the machine is once this statement has run."""
    verb, line = statement.verb, statement.line
    if verb == "start":
        return _Where(_RUNNING, f"started at line {line}")
    if verb == "stop":
        return _Where(_STOPPED, f"stopped at line {line}")
    if verb != "wait":
        return where
    if not statement.handlers:
        condition = statement.condition
        # A `wait machine=stopped` that completed actually *observed*
        # the machine stopped, so this reflects something the script
        # measured, not an assumption -- and it is how every script
        # that powers a guest off from the inside already ends.
        if condition is not None and condition.channel == "machine" \
                and condition.value == "stopped":
            return _Where(_STOPPED, f"observed stopped at line {line}")
        return where
    # A branching wait continues into whichever handlers do not
    # transfer control away, so what follows sees the combined
    # effect of all of them.
    reached = [_flow(handler.statements, where, judge=False)
               for handler in statement.handlers
               if not _terminates(handler.statements)]
    if not reached:
        return where                    # terminating: nothing follows
    merged = reached[0]
    for other in reached[1:]:
        merged = _join(merged, other)
    return merged


def _flow(units, where, judge):
    """Walk a unit list, and report where the machine is once the walk is done.

    ``judge`` is turned off wherever reaching this code depends on a
    guest decision: the walk still tracks what the statements *do*
    to the machine, but does not reject anything.
    """
    for unit in units:
        inner = _scoped(unit)
        if inner is not None:
            if judge:
                _scope_gate(unit, where, entering=True)
            where = _flow(inner, where, judge)
            if judge:
                _scope_gate(unit, where, entering=False)
            continue
        if not _is_statement(unit):
            continue                    # a phase, walked in its own turn
        if judge:
            _statement_gate(unit, where)
        where = _after(unit, where)
    return where


def _statement_gate(statement, where):
    """Refuse a stopped-only verb wherever the machine cannot be confirmed stopped."""
    if statement.verb != "set-boot" or where.state != _RUNNING:
        return
    raise ScriptParseError(
        statement.line,
        f"set-boot needs a stopped machine, and it is running here "
        f"({where.why}): the order is read at the next start, so it "
        "belongs before one or after a stop",
        statement.column, rule_id="machine.must-be-stopped")


def _scope_gate(scope, where, entering, leaving_at=None):
    """Refuse a boot scope whose entry or exit is crossed with the machine running.

    Both edges of the scope write the boot order -- entering it
    applies the boot prefix, leaving it restores the old order -- so
    both are subject to the same rule that governs `set-boot`
    itself. The exit edge is the one an author is unlikely to
    anticipate: it is reached both by the scope finishing normally
    and by any failure inside it.
    """
    if scope.head != "boot" or where.state != _RUNNING:
        return
    at = f" at line {leaving_at}" if leaving_at else ""
    said = (f"this scope is entered with the machine running "
            f"({where.why})" if entering else
            f"this scope puts the boot order back where it is left{at}, "
            f"and the machine is running there ({where.why})")
    raise ScriptParseError(
        scope.line,
        f"{said}: a boot order is written only on a stopped machine",
        scope.column, rule_id="machine.must-be-stopped")


def _phased_flow(script, start):
    """Work out where the machine is at every phase the plan can reach.

    This makes two passes over the static transition graph. The
    first pass runs the joins repeatedly until the answers stop
    changing, because a phase that can be reached two different
    ways has to be judged on what *both* paths promise. The second
    pass judges each phase against the answer that settled, so
    nothing gets rejected based on a state that a later-discovered
    edge would have widened to `unknown`.
    """
    by_name = {phase.name: phase for phase in script.phases}
    entries = {script.entry: start}
    pending = [script.entry]
    while pending:
        phase = by_name.get(pending.pop())
        if phase is None:
            continue
        end, target = _phase_exit(phase, entries[phase.name])
        if target is None:
            continue
        merged = _join(entries.get(target), end)
        if entries.get(target) != merged:
            entries[target] = merged
            pending.append(target)
    for scope in script.phase_scopes.get(script.entry, ()):
        _scope_gate(scope, start, entering=True)
    # Walked in source order, so a script with two violations
    # reports the first one an author would read, not just the
    # first one the earlier walk happened to settle.
    for phase in script.phases:
        where = entries.get(phase.name)
        if where is None:
            continue                    # not a phase the plan reaches
        _flow(phase.statements, where, judge=True)
        _crossings(script, phase, *_phase_exit(phase, where))


def _phase_exit(phase, where):
    """Where a phase leaves the machine, and which phase it transfers to next.

    This only looks at the phase's **own** statement list: a `goto`
    inside a handler happens because of a guest decision, so the
    phase it names is not one the plan can promise it reaches, and
    neither is anything beyond it.
    """
    end = _flow(phase.statements, where, judge=False)
    last = phase.statements[-1] if phase.statements else None
    if last is not None and last.verb == "goto":
        return end, last.arguments[0]
    return end, None


def _crossings(script, phase, where, target):
    """Judge the scope edges a phase's transfer crosses.

    A scope's effect holds only while control is inside it, so
    leaving one scope and entering another both happen **during the
    transition** between phases -- which is why this check belongs
    to the transition itself, not to either phase alone. A `finish`
    leaves every scope the phase it is in was nested inside.
    """
    chain = script.phase_scopes.get(phase.name, ())
    last = phase.statements[-1] if phase.statements else None
    line = last.line if last is not None else phase.line
    if target is None:
        if last is not None and last.verb == "finish":
            for scope in reversed(chain):
                _scope_gate(scope, where, entering=False, leaving_at=line)
        return
    onward = script.phase_scopes.get(target, ())
    shared = 0
    while (shared < len(chain) and shared < len(onward)
           and chain[shared] is onward[shared]):
        shared += 1
    for scope in reversed(chain[shared:]):
        _scope_gate(scope, where, entering=False, leaving_at=line)
    for scope in onward[shared:]:
        _scope_gate(scope, where, entering=True)


# -- the two shapes (V3, V10) ------------------------------------

def _linear(script):
    """Validate a linear script: no phase machinery reaches it."""
    if script.entry is not None:
        raise ScriptParseError(
            script.headers.get("entry", 1),
            "entry is invalid in a linear script: it names the phase a "
            "phased script begins in",
            rule_id="flow.entry-in-linear")
    for statement in _walk(script.statements):
        if statement.verb in _TRANSFERS:
            raise ScriptParseError(
                statement.line,
                f"{statement.verb} is invalid in a linear script: reaching "
                "end of file completes the run", statement.column,
                rule_id="flow.transfer-in-linear")
    _body(script.statements)


def _phased(script):
    """Validate a phased script and every phase in it."""
    phases = {}
    for phase in script.phases:
        _not_reserved(phase.name, "a phase", phase.line, phase.column)
        if phase.name in phases:
            raise ScriptParseError(
                phase.line, f"duplicate phase: {phase.name}",
                phase.column,
                rule_id="name.duplicate-phase")
        phases[phase.name] = phase
    if script.entry is None:
        raise ScriptParseError(
            script.phases[0].line,
            "a phased script declares the entry phase it begins in",
            script.phases[0].column,
            rule_id="flow.entry-missing")
    if script.entry not in phases:
        raise ScriptParseError(
            script.headers.get("entry", script.phases[0].line),
            f"entry names an undeclared phase: {script.entry}",
            rule_id="flow.entry-undeclared")
    for phase in script.phases:
        _phase(phase)
        for statement in _walk(phase.statements, phase.handlers):
            if statement.verb == "goto" and statement.arguments[0] not in \
                    phases:
                raise ScriptParseError(
                    statement.line,
                    "goto names an undeclared phase: "
                    f"{statement.arguments[0]}", statement.column,
                    rule_id="flow.goto-undeclared")
    _cycles(script)


def _cycles(script):
    """Check that a phase graph which can cycle also declares a run deadline (V12).

    Only phases reachable from ``entry`` are walked: a cycle among
    phases the run could never actually enter is unreachable code,
    which is something static analysis should warn about, not
    something that needs a time budget.
    """
    if script.deadline is not None:
        return
    edges = {phase.name: tuple(
        (statement.arguments[0], statement)
        for statement in _walk(phase.statements, phase.handlers)
        if statement.verb == "goto") for phase in script.phases}
    visiting, done, path = set(), set(), []

    def visit(name):
        visiting.add(name)
        path.append(name)
        for target, statement in edges[name]:
            if target in visiting:
                route = " -> ".join(path[path.index(target):] + [target])
                raise ScriptParseError(
                    statement.line,
                    f"the phase graph can cycle ({route}): a script that "
                    "can revisit a phase declares a header deadline, the "
                    "backstop that bounds the run", statement.column,
                    rule_id="flow.cycle-without-deadline")
            if target not in done:
                visit(target)
        path.pop()
        visiting.discard(name)
        done.add(name)

    visit(script.entry)


def _phase(phase):
    """Validate one phase as sequential or reactive, never both."""
    if phase.statements and phase.handlers:
        first, second = sorted((phase.statements[0], phase.handlers[0]),
                               key=lambda item: item.line)
        raise ScriptParseError(
            second.line,
            f"phase {phase.name} mixes ordered statements with standing "
            "handlers: a phase is sequential or reactive, never both",
            second.column,
            rule_id="handler.mixed-phase")
    if phase.handlers:
        for handler in phase.handlers:
            if handler.keyword != "always":
                raise ScriptParseError(
                    handler.line,
                    "on is legal only inside a branching wait: a standing "
                    "rule in a reactive phase is written always",
                    handler.column,
                    rule_id="handler.on-outside-branching-wait")
            _handler(handler)
        return
    _body(phase.statements)
    if not _terminates(phase.statements):
        last = phase.statements[-1] if phase.statements else phase
        raise ScriptParseError(
            last.line,
            f"phase {phase.name} does not end in goto or finish: a "
            "sequential phase's statement list terminates",
            last.column,
            rule_id="flow.phase-falls-through")


# -- statement lists (V7, V8, V9, V11) ---------------------------

def _body(statements, in_handler=False):
    """Validate one statement list and everything nested in it."""
    for index, statement in enumerate(statements):
        if _scoped(statement) is not None:
            _body(_scoped(statement), in_handler)
        else:
            _statement(statement, in_handler)
        if _terminating(statement) and index + 1 < len(statements):
            following = statements[index + 1]
            raise ScriptParseError(
                following.line,
                f"unreachable statement: {statement.verb} ends its "
                "statement list", following.column,
                rule_id="flow.unreachable-statement")


def _statement(statement, in_handler):
    """Validate one statement; only observations nest anything."""
    if statement.verb != "wait":
        return
    if not statement.handlers:
        _condition(statement, "wait")
        return
    if in_handler:
        raise ScriptParseError(
            statement.line,
            "a branching wait may not appear inside a handler body: "
            "further branching belongs in the phase graph",
            statement.column,
            rule_id="wait.branching-in-handler")
    if statement.conditions:
        condition = statement.conditions[0]
        raise ScriptParseError(
            condition.line,
            "a branching wait carries no condition of its own: each "
            "handler carries its own", condition.column,
            rule_id="wait.branching-condition")
    if len(statement.handlers) < 2:
        raise ScriptParseError(
            statement.line,
            "a branching wait requires at least two handlers: one "
            "condition is a plain wait", statement.column,
            rule_id="wait.too-few-handlers")
    for handler in statement.handlers:
        if handler.keyword != "on":
            raise ScriptParseError(
                handler.line,
                "always is legal only directly inside a reactive phase: a "
                "branching wait's cases are written on", handler.column,
                rule_id="handler.always-outside-reactive-phase")
        _handler(handler)


def _handler(handler):
    """Validate one handler's condition and its body."""
    _condition(handler, handler.keyword)
    _body(handler.statements, in_handler=True)


# -- observation conditions (V7) ---------------------------------

def _condition(node, what):
    """Check that an observation carries exactly one good condition."""
    if not node.conditions:
        raise ScriptParseError(
            node.line, f"{what} requires a condition", node.column,
            rule_id="obs.missing-condition")
    # Each condition is checked individually before checking the
    # count, so a misspelled channel gets named as the actual
    # problem, instead of being reported as an extra condition
    # sitting next to the string it was written beside.
    for condition in node.conditions:
        _channel(condition)
        _pattern(condition)
    if len(node.conditions) > 1:
        extra = node.conditions[1]
        raise ScriptParseError(
            extra.line,
            f"{what} carries more than one condition: an observation "
            "carries exactly one", extra.column,
            rule_id="obs.two-channels")


def _channel(condition):
    """Check one condition's channel, and its value against it."""
    if condition.channel is None:
        hint = (", and machine state is spelled machine=stopped"
                if condition.value == "stopped" else "")
        raise ScriptParseError(
            condition.line,
            f"{condition.value!r} is not a condition: the screen is "
            f"observed by a bare string or regex{hint}",
            condition.column,
            rule_id="obs.not-a-condition")
    if not condition.named:
        return                          # the screen, the one spelling
    if condition.channel == "screen":
        raise ScriptParseError(
            condition.line,
            "the screen channel has no named spelling: write the string "
            "or regex alone", condition.column,
            rule_id="obs.screen-named")
    channel = _CHANNELS.get(condition.channel)
    if channel is None:
        raise ScriptParseError(
            condition.line,
            f"unknown observation channel: {condition.channel} (known: "
            f"{', '.join(sorted(_CHANNELS))})", condition.column,
            rule_id="obs.unknown-channel")
    kind, values = channel
    if condition.kind != kind or condition.value not in values:
        raise ScriptParseError(
            condition.line,
            f"{condition.channel} observes the state "
            f"{' or '.join(values)}", condition.column,
            rule_id="obs.wrong-kind")


# -- watch patterns (V13) ----------------------------------------

def _pattern(condition):
    """Check that a watch pattern is non-empty and, for a regex, that it compiles (V13).

    Both checks catch the same underlying problem in two different
    forms: a pattern that cannot say what it is actually waiting
    for. An empty pattern matches every screen, so the ``wait``
    around it does not really observe anything and passes on the
    very first sample. A malformed regex cannot be matched against
    anything at all, and if this were not caught here, it would show
    up mid-run as a Python ``re.error`` -- a kind of failure outside
    reliquary's normal error classes, caused by a defect that the
    script text alone already reveals.

    The regex dialect is Python's ``re``, which script-spec.md
    commits to as part of the language's contract, not just an
    implementation detail ("Regexes"). So compiling the pattern here
    is checking exactly what the spec requires, not something
    specific to how this implementation happens to work.
    """
    if condition.kind == "text":
        empty = condition.value.spelling == ""
    elif condition.kind == "regex":
        empty = condition.value == ""
    else:
        return                          # a state word, not a pattern
    if empty:
        raise ScriptParseError(
            condition.line,
            "an empty watch pattern matches every screen: write what "
            "the screen shows", condition.column,
            rule_id="obs.empty-pattern")
    if condition.kind == "regex":
        try:
            re.compile(condition.value)
        except re.error as error:
            raise ScriptParseError(
                condition.line,
                f"the regex does not compile: {error}; the dialect is "
                "Python's re syntax", condition.column,
                rule_id="obs.uncompilable-regex") from None


# -- terminating statements (V11) --------------------------------

def _terminating(statement):
    """Whether a statement ends the flow through its list."""
    if _scoped(statement) is not None:
        # A scope ends the flow through its list exactly when
        # whatever it wraps does: control leaves the block through
        # the same kind of transfer it would have left the
        # underlying list through.
        return _terminates(_scoped(statement))
    if statement.verb in _TRANSFERS:
        return True
    if statement.verb == "wait" and statement.handlers:
        return all(_terminates(handler.statements)
                   for handler in statement.handlers)
    return False


def _terminates(statements):
    """Whether a statement list terminates."""
    return bool(statements) and _terminating(statements[-1])


def _walk(statements, handlers=()):
    """Yield every statement in a body, including statements inside handler bodies.

    A ``with`` scope is transparent here: whatever it wraps gets
    walked, but the scope itself is not yielded as a statement.
    Phases inside a scope are skipped rather than walked into,
    because every phase is already reached through the flat
    ``script.phases`` list, and walking it here too would
    double-count every rule that counts statements.
    """
    for handler in handlers:
        yield from _walk(handler.statements)
    for statement in statements:
        if _scoped(statement) is not None:
            yield from _walk(_scoped(statement))
            continue
        if not _is_statement(statement):
            continue
        yield statement
        yield from _walk((), statement.handlers)


def _sequence(statements):
    """Yield a statement list's own statements, with scopes flattened out.

    This is :func:`_walk` without the handler bodies -- it only
    yields statements control reaches by falling straight through
    the list, not statements reached because the guest satisfied
    some condition. That is the exact distinction :func:`reach`
    needs to measure.
    """
    for statement in statements:
        if _scoped(statement) is not None:
            yield from _sequence(_scoped(statement))
        elif _is_statement(statement):
            yield statement


def _scoped(node):
    """The units a ``with`` scope wraps, or ``None`` for anything that is not a scope.

    This is a structural check, like the rest of this module: a
    scope is simply whichever node has a ``units`` attribute.
    """
    return getattr(node, "units", None)


def _is_statement(node):
    """Whether a body item is a statement rather than a phase."""
    return hasattr(node, "verb")
