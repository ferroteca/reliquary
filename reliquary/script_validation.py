# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""The static-validation layer of the reliquary script language.

The S-numbered legality rules that the grammar deliberately does
not carry (planning/design/script-spec.md, "Syntactic
restrictions"), checked over the typed tree so each diagnostic can
name the offending construct and cite its rule:

- **S3** — ``entry`` appears exactly in phased scripts;
- **S5** — phase names are unique and durations are positive;
- **S7** — an observation carries exactly one condition, on a
  known channel, of the right kind;
- **S8** — a branching ``wait`` carries no condition of its own,
  has at least two handlers, and never appears inside a handler
  body;
- **S9** — ``on`` only inside a branching ``wait``, ``always``
  only directly inside a reactive phase, and no hybrid phase;
- **S10** — the two script shapes never mix, and every phase name
  a script transfers to is declared;
- **S11** — nothing follows a terminating statement, and a
  sequential phase's statement list terminates;
- **S12** — a phased script whose transition graph can cycle
  declares a header ``deadline``, the backstop that bounds the
  run.
- **S14** — every ``press`` key belongs to the language's closed
  portable vocabulary.

The remaining rules belong to the layers around this one: S1, S2,
and S4 are the lexer's and the parser's — the timing placement
matrix is a node signature — and S6, S13, and the remaining S14
vocabularies arrive with their owning features. The timing *model*
itself, which resolves the durations this module checks, is
:mod:`reliquary.script_timing`.

This module works structurally over the tree, so it imports no
node type; that keeps the parser free to import it.
"""

from .script_nodes import ScriptParseError
from .script_timing import parse_duration

# The observable channels, each with the condition kind it takes
# and its closed value set. The screen is the default channel and
# is deliberately absent: it has no named spelling.
_CHANNELS = {"machine": ("state", ("stopped",))}
_TRANSFERS = ("goto", "finish")
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
    if script.phases:
        _phased(script)
    else:
        _linear(script)


# -- durations (S5) ----------------------------------------------

def _properties(script):
    """Property names are unique and outside reserved namespaces."""
    seen = {}
    for prop in script.properties:
        _property_key(prop.key, prop.line, prop.column)
        if prop.key in seen:
            raise ScriptParseError(
                prop.line, f"duplicate property: {prop.key} (S5)",
                prop.column)
        seen[prop.key] = prop


def _derivations(script):
    """The `default=` derivation rules (S5, S6).

    Static because a derivation is not an expression: its answer is
    knowable — or knowably unanswerable — before the run, so every
    error it can carry is caught here rather than at binding time.
    """
    from . import facts
    declared = {prop.key: prop for prop in script.properties}
    for prop in script.properties:
        if not prop.defaults:
            continue
        if prop.kind == "secret":
            raise ScriptParseError(
                prop.line,
                f"a secret property may not carry default=: {prop.key} "
                "(S5)", prop.column)
        # A literal candidate (no references) always answers, so any
        # candidate after it is dead code.
        for candidate in prop.defaults[:-1]:
            if not candidate.interpolated:
                raise ScriptParseError(
                    prop.line,
                    f"a literal default= must be the last candidate; "
                    f"those after it are dead: {prop.key} (S5)",
                    prop.column)
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
            "neither a declared property nor an rlq.* fact (S6)",
            prop.column)
    if target.kind == "secret":
        raise ScriptParseError(
            prop.line,
            f"default= for {prop.key} references the secret {key!r}; "
            "no derivation may reference a secret (S6)", prop.column)


def _forbid_derivation_cycles(script, declared):
    """A `${key}` chain among derivations must be acyclic (S6)."""
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
                f"default= derivations form a cycle: {cycle} (S6)",
                prop.column)
        state[key] = "open"
        for target in edges.get(key, ()):
            visit(target, trail + [key])
        state[key] = "closed"

    for key in edges:
        visit(key, [])


def _property_key(key, line, column):
    if key in ("text", "media", "secret"):
        raise ScriptParseError(
            line, f"{key!r} is reserved in property declarations (S5)",
            column)
    if key == "rlq" or key.startswith("rlq."):
        raise ScriptParseError(
            line,
            "property keys in the rlq namespace are reserved for "
            "reliquary-owned run facts (S5)", column)
    if key == "reliquary" or key.startswith("reliquary."):
        raise ScriptParseError(
            line,
            "property keys in the reliquary namespace are reserved (S5)",
            column)


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
            script.http.column)
    _ports(script.http)
    _content_set(script.http.contents)


def _content_set(contents):
    names = {}
    paths = {}
    for content in contents:
        if content.name in names:
            raise ScriptParseError(
                content.line, f"duplicate content name: {content.name}",
                content.column)
        names[content.name] = content
        path = _plain(content.path, "content path", content.line,
                      content.column)
        if not path.startswith("/"):
            raise ScriptParseError(
                content.line,
                f"content path must begin with '/': {path!r}",
                content.column)
        segments = path.split("/")
        if any(segment in (".", "..") for segment in segments):
            raise ScriptParseError(
                content.line,
                f"content path may not contain . or ..: {path!r}",
                content.column)
        if path in paths:
            raise ScriptParseError(
                content.line, f"duplicate content path: {path}",
                content.column)
        paths[path] = content
        if content.body.spelling == "":
            raise ScriptParseError(
                content.line, f"content path {path!r} has an empty body",
                content.column)


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
                statement.column)
        if command == "start" and script.http is None \
                and not statement.contents:
            raise ScriptParseError(
                statement.line,
                "http start requires declared or inline content",
                statement.column)
        if command == "start":
            _content_set(statement.contents)
            for name in statement.arguments[1:]:
                if name not in declared:
                    raise ScriptParseError(
                        statement.line,
                        f"http start names undeclared content: {name}",
                        statement.column)
        elif len(statement.arguments) > 1 or statement.contents:
            raise ScriptParseError(
                statement.line, "http stop takes no content names or block",
                statement.column)


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
                f"{port}", http.column)
    if http.port_min is not None and http.port_max is not None:
        if int(http.port_min) > int(http.port_max):
            raise ScriptParseError(
                http.line, "port-min must be less than or equal to port-max",
                http.column)


def _plain(literal, what, line, column):
    try:
        return literal.text
    except ValueError:
        raise ScriptParseError(
            line, f"{what} may not contain property references", column)


def _forbid_http_refs(script):
    for literal, line, column in _text_literals(script):
        for key in literal.keys:
            if key.startswith("rlq.http."):
                raise ScriptParseError(
                    line,
                    "rlq.http.* properties require an http block (S6)",
                    column)


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


def _all_statements(script):
    yield from _walk(script.statements)
    for phase in script.phases:
        yield from _walk(phase.statements, phase.handlers)


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
    """Every written duration is positive.

    Where each may be written is the placement matrix, which the
    node signatures enforce (S2); this is the value rule.
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
            line, f"{name} must be a positive duration: {spelling} (S5)",
            column)


def _timed(statements, handlers=()):
    """Yield every node that may carry a timing modifier."""
    for handler in handlers:
        yield handler
        yield from _timed(handler.statements)
    for statement in statements:
        yield statement
        yield from _timed((), statement.handlers)


# -- portable keys (S14) -----------------------------------------

def _keys(script):
    """Every ``press`` argument belongs to the portable key set.

    A chord may also contain one-character printable members, as
    in ``ctrl+c``. A bare character remains text and must be sent
    with ``type`` or ``enter``.
    """
    statements = list(_walk(script.statements))
    for phase in script.phases:
        statements.extend(_walk(phase.statements, phase.handlers))
    for statement in statements:
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
                    f"{unknown!r} is not a portable key name (S14)",
                    statement.column)


# -- the two shapes (S3, S10) ------------------------------------

def _linear(script):
    """Validate a linear script: no phase machinery reaches it."""
    if script.entry is not None:
        raise ScriptParseError(
            script.headers.get("entry", 1),
            "entry is invalid in a linear script: it names the phase a "
            "phased script begins in (S3)")
    for statement in _walk(script.statements):
        if statement.verb in _TRANSFERS:
            raise ScriptParseError(
                statement.line,
                f"{statement.verb} is invalid in a linear script: reaching "
                "end of file completes the run (S10)", statement.column)
    _body(script.statements)


def _phased(script):
    """Validate a phased script and every phase in it."""
    phases = {}
    for phase in script.phases:
        if phase.name in phases:
            raise ScriptParseError(
                phase.line, f"duplicate phase: {phase.name} (S5)",
                phase.column)
        phases[phase.name] = phase
    if script.entry is None:
        raise ScriptParseError(
            script.phases[0].line,
            "a phased script declares the entry phase it begins in (S3)",
            script.phases[0].column)
    if script.entry not in phases:
        raise ScriptParseError(
            script.headers.get("entry", script.phases[0].line),
            f"entry names an undeclared phase: {script.entry} (S10)")
    for phase in script.phases:
        _phase(phase)
        for statement in _walk(phase.statements, phase.handlers):
            if statement.verb == "goto" and statement.arguments[0] not in \
                    phases:
                raise ScriptParseError(
                    statement.line,
                    "goto names an undeclared phase: "
                    f"{statement.arguments[0]} (S10)", statement.column)
    _cycles(script)


def _cycles(script):
    """A phase graph that can cycle declares a run deadline (S12).

    Only phases reachable from ``entry`` are walked: a cycle among
    phases the run can never enter is unreachable code, which
    static analysis warns about rather than budgets.
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
                    "backstop that bounds the run (S12)", statement.column)
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
            "handlers: a phase is sequential or reactive, never both (S9)",
            second.column)
    if phase.handlers:
        for handler in phase.handlers:
            if handler.keyword != "always":
                raise ScriptParseError(
                    handler.line,
                    "on is legal only inside a branching wait: a standing "
                    "rule in a reactive phase is written always (S9)",
                    handler.column)
            _handler(handler)
        return
    _body(phase.statements)
    if not _terminates(phase.statements):
        last = phase.statements[-1] if phase.statements else phase
        raise ScriptParseError(
            last.line,
            f"phase {phase.name} does not end in goto or finish: a "
            "sequential phase's statement list terminates (S11)",
            last.column)


# -- statement lists (S7, S8, S9, S11) ---------------------------

def _body(statements, in_handler=False):
    """Validate one statement list and everything nested in it."""
    for index, statement in enumerate(statements):
        _statement(statement, in_handler)
        if _terminating(statement) and index + 1 < len(statements):
            following = statements[index + 1]
            raise ScriptParseError(
                following.line,
                f"unreachable statement: {statement.verb} ends its "
                "statement list (S11)", following.column)


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
            "further branching belongs in the phase graph (S8)",
            statement.column)
    if statement.conditions:
        condition = statement.conditions[0]
        raise ScriptParseError(
            condition.line,
            "a branching wait carries no condition of its own: each "
            "handler carries its own (S8)", condition.column)
    if len(statement.handlers) < 2:
        raise ScriptParseError(
            statement.line,
            "a branching wait requires at least two handlers: one "
            "condition is a plain wait (S8)", statement.column)
    for handler in statement.handlers:
        if handler.keyword != "on":
            raise ScriptParseError(
                handler.line,
                "always is legal only directly inside a reactive phase: a "
                "branching wait's cases are written on (S9)", handler.column)
        _handler(handler)


def _handler(handler):
    """Validate one handler's condition and its body."""
    _condition(handler, handler.keyword)
    _body(handler.statements, in_handler=True)


# -- observation conditions (S7) ---------------------------------

def _condition(node, what):
    """Check that an observation carries exactly one good condition."""
    if not node.conditions:
        raise ScriptParseError(
            node.line, f"{what} requires a condition (S7)", node.column)
    # Each condition is checked before the count, so a misspelled
    # channel is named as one rather than reported as a second
    # condition beside the string it was written next to.
    for condition in node.conditions:
        _channel(condition)
    if len(node.conditions) > 1:
        extra = node.conditions[1]
        raise ScriptParseError(
            extra.line,
            f"{what} carries more than one condition: an observation "
            "carries exactly one (S7)", extra.column)


def _channel(condition):
    """Check one condition's channel, and its value against it."""
    if condition.channel is None:
        hint = (", and machine state is spelled machine=stopped"
                if condition.value == "stopped" else "")
        raise ScriptParseError(
            condition.line,
            f"{condition.value!r} is not a condition: the screen is "
            f"observed by a bare string or regex{hint} (S7)",
            condition.column)
    if not condition.named:
        return                          # the screen, the one spelling
    if condition.channel == "screen":
        raise ScriptParseError(
            condition.line,
            "the screen channel has no named spelling: write the string "
            "or regex alone (S7)", condition.column)
    channel = _CHANNELS.get(condition.channel)
    if channel is None:
        raise ScriptParseError(
            condition.line,
            f"unknown observation channel: {condition.channel} (known: "
            f"{', '.join(sorted(_CHANNELS))}) (S7)", condition.column)
    kind, values = channel
    if condition.kind != kind or condition.value not in values:
        raise ScriptParseError(
            condition.line,
            f"{condition.channel} observes the state "
            f"{' or '.join(values)} (S7)", condition.column)


# -- terminating statements (S11) --------------------------------

def _terminating(statement):
    """Whether a statement ends the flow through its list."""
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
    """Yield every statement in a body, handler bodies included."""
    for handler in handlers:
        yield from _walk(handler.statements)
    for statement in statements:
        yield statement
        yield from _walk((), statement.handlers)
