# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""The timing model of the reliquary script language.

Two families scope differently
(docs/spec/script-spec.md, "Timing"):

- ``timeout`` and ``stable`` are per-observation settings and
  **lexically scoped**, so a container's ``timeout`` is the
  default for every observation it lexically contains. Resolution
  is innermost-wins — statement, branching ``wait``, phase,
  header, the built-in 60s — and entirely a parse-time question;
- ``deadline`` is a **budget**, dynamically scoped to one
  activation. It is never inherited, so resolution has nothing to
  decide: a phase's budget is the one written on it, and the
  header's bounds the run.

:func:`resolve` therefore computes the whole plan up front: every
observation's effective timeout and the scope that supplied it,
each phase's budget, and the run's. ``check-script`` reports the
plan, a timing failure names the clock that expired and its
source scope, and the runner never re-derives a bound it could
have been handed.

This module works structurally over the typed tree, so it imports
no node type.
"""

from dataclasses import dataclass, field
from typing import Mapping, Optional, Tuple

# The built-in observation bound, when nothing else supplies one.
DEFAULT_TIMEOUT = "60s"
_UNITS = {"ms": 0.001, "s": 1.0, "m": 60.0, "h": 3600.0}


def parse_duration(spelling):
    """Return a duration spelling in seconds.

    The lexer has already typed the spelling, so this raises only
    on a value that never came from a script.
    """
    unit = "ms" if spelling.endswith("ms") else spelling[-1:]
    try:
        return float(spelling[:-len(unit)]) * _UNITS[unit]
    except (KeyError, ValueError):
        raise ValueError(f"not a duration: {spelling!r}") from None


@dataclass(frozen=True)
class Bound:
    """One resolved clock: its duration and where it came from."""

    spelling: str
    seconds: float
    scope: str                    # "statement", "phase", "header", ...
    scope_name: Optional[str] = None
    line: int = 0

    @property
    def source(self):
        """The source scope, as a failure or a plan report says it."""
        where = self.scope
        if self.scope_name is not None:
            where = f"{where} {self.scope_name}"
        if self.line:
            where = f"{where} (line {self.line})"
        return where

    def __str__(self):
        return f"{self.spelling} from the {self.source}"


@dataclass(frozen=True)
class Observation:
    """One observation in the plan, with the clocks that bound it."""

    kind: str                     # "wait", "branching wait", "on", ...
    line: int
    column: int
    phase: Optional[str]
    timeout: Bound
    stable: Optional[Bound] = None


@dataclass(frozen=True)
class TimingPlan:
    """Every clock a script resolves at parse time."""

    default: Bound
    run_deadline: Optional[Bound] = None
    phase_deadlines: Mapping[str, Bound] = field(default_factory=dict)
    observations: Tuple[Observation, ...] = ()

    def at(self, node):
        """The plan entry for a parsed node, by its source position."""
        for observation in self.observations:
            if (observation.line, observation.column) == (node.line,
                                                          node.column):
                return observation
        return None


def resolve(script):
    """Resolve a parsed script's whole timing plan."""
    default = _header_default(script)
    run = _bound(script.deadline, "header", None,
                 script.headers.get("deadline", 0))
    deadlines = {}
    observations = []
    if script.phases:
        for phase in script.phases:
            budget = _bound(phase.deadline, "phase", phase.name, phase.line)
            if budget is not None:
                deadlines[phase.name] = budget
            inner = _bound(phase.timeout, "phase", phase.name,
                           phase.line) or default
            if phase.handlers:
                # A reactive phase's timeout is itself a clock: the
                # interval it allows with no handler firing.
                observations.append(Observation(
                    "reactive interval", phase.line, phase.column,
                    phase.name, inner))
                for handler in phase.handlers:
                    _handler(handler, inner, phase.name, observations)
            else:
                _statements(phase.statements, inner, phase.name,
                            observations)
    else:
        _statements(script.statements, default, None, observations)
    return TimingPlan(default, run, dict(deadlines), tuple(observations))


def format_plan(plan, name=None):
    """Render a timing plan the way ``check-script`` prints it."""
    lines = []
    if name:
        lines.append(f"timing plan for {name}")
        lines.append("")
    lines.append(f"default timeout: {plan.default}")
    if plan.run_deadline is not None:
        lines.append(f"run deadline: {plan.run_deadline}")
    if plan.phase_deadlines:
        lines.append("phase deadlines:")
        for phase_name, budget in plan.phase_deadlines.items():
            lines.append(f"  phase {phase_name}: {budget}")
    if plan.observations:
        lines.append("observations:")
        for observation in plan.observations:
            where = f"line {observation.line}"
            if observation.phase is not None:
                where = f"{where} phase {observation.phase}"
            entry = (f"  {where} {observation.kind}: "
                     f"{observation.timeout}")
            if observation.stable is not None:
                entry += f"; stable {observation.stable}"
            lines.append(entry)
    return "\n".join(lines) + "\n"


def _header_default(script):
    """The script-wide observation default, or the built-in one."""
    return _bound(script.timeout, "header", None,
                  script.headers.get("timeout", 0)) or Bound(
        DEFAULT_TIMEOUT, parse_duration(DEFAULT_TIMEOUT), "built-in")


def _bound(spelling, scope, scope_name, line):
    """A bound for a written duration, or ``None`` if none was."""
    if spelling is None:
        return None
    return Bound(spelling, parse_duration(spelling), scope, scope_name, line)


def _statements(statements, default, phase, observations):
    """Resolve a statement list under its innermost default."""
    for statement in statements:
        if statement.verb == "select":
            # An observation-bearing action: its feedback watches
            # run within the statement's effective timeout.
            observations.append(Observation(
                "select", statement.line, statement.column, phase, default))
            continue
        if statement.verb != "wait":
            continue
        if not statement.handlers:
            inner = _bound(statement.timeout, "statement", None,
                           statement.line) or default
            observations.append(Observation(
                "wait", statement.line, statement.column, phase, inner,
                _bound(statement.stable, "statement", None, statement.line)))
            continue
        # A branching wait bounds reaching the first match, and is
        # the innermost scope for the observations its handlers
        # lexically contain.
        branching = _bound(statement.timeout, "branching wait", None,
                           statement.line) or default
        observations.append(Observation(
            "branching wait", statement.line, statement.column, phase,
            branching))
        for handler in statement.handlers:
            _handler(handler, branching, phase, observations)


def _handler(handler, default, phase, observations):
    """Resolve one handler: its own hold, then its body."""
    observations.append(Observation(
        handler.keyword, handler.line, handler.column, phase, default,
        _bound(handler.stable, "statement", None, handler.line)))
    _statements(handler.statements, default, phase, observations)
