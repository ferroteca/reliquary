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

The remaining rules belong to the layers around this one: S1, S2,
and S4 are the lexer's and the parser's — the timing placement
matrix is a node signature — and S6, S13, and S14 arrive with the
closed vocabularies. The timing *model* itself, which resolves
the durations this module checks, is
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


def validate(script):
    """Check the static rules over a parsed script.

    Raises :class:`~reliquary.script_nodes.ScriptParseError` on the
    first violation. Source context is attached by the caller that
    knows the document's path.
    """
    _durations(script)
    if script.phases:
        _phased(script)
    else:
        _linear(script)


# -- durations (S5) ----------------------------------------------

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
