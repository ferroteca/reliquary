# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""The timing model of the reliquary script language.

Three families scope differently
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
- ``pacing`` is a per-guest-input setting and lexically scoped
  like the first family — statement, phase, header, the built-in
  0.1s. It has no branching-``wait`` rung because an observation
  container cannot carry it: pacing paces the actor, and a
  ``wait`` acts on nothing.

:func:`resolve` therefore computes the whole plan up front: every
observation's effective timeout and the scope that supplied it,
every guest-input verb's effective pacing and its scope, each
phase's budget, and the run's. ``check-script`` reports the
plan, a timing failure names the clock that expired and its
source scope, and the runner never re-derives a bound it could
have been handed.

This module works structurally over the typed tree, so it imports
no node type.
"""

from dataclasses import dataclass, field
from typing import Mapping, Optional, Tuple

from .errors import StaticError

# The built-in observation bound, when nothing else supplies one.
DEFAULT_TIMEOUT = "60s"

# The built-in gap before the first key event of a guest-input verb.
# Deliberately small and deliberately provisional: a plain text
# screen paints quickly and an animated TUI menu very slowly, so no
# single number serves every screen — which is the argument for the
# per-phase and per-statement override carrying real weight.
DEFAULT_PACING = "0.1s"

_UNITS = {"ms": 0.001, "s": 1.0, "m": 60.0, "h": 3600.0}

#: The verbs that deliver keystrokes, and so pay the pacing gap.
#: Host-side verbs (``insert``, ``eject``, ``set-boot``,
#: ``screenshot``, ``start``, ``stop``, ``set``, ``http``) are not
#: guest input and do not.
INPUT_VERBS = frozenset({"enter", "type", "press", "select"})


def parse_duration(spelling):
    """Return a duration spelling in seconds.

    The lexer has already typed the spelling, so this raises only
    on a value that never came from a script.
    """
    unit = "ms" if spelling.endswith("ms") else spelling[-1:]
    try:
        return float(spelling[:-len(unit)]) * _UNITS[unit]
    except (KeyError, ValueError):
        raise StaticError(f"not a duration: {spelling!r}",
                          rule_id="time.not-a-duration") from None


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
class Input:
    """One guest-input verb in the plan, with the gap before it."""

    verb: str                     # "enter", "type", "press", "select"
    line: int
    column: int
    phase: Optional[str]
    pacing: Bound


@dataclass(frozen=True)
class TimingPlan:
    """Every clock a script resolves at parse time."""

    default: Bound
    run_deadline: Optional[Bound] = None
    phase_deadlines: Mapping[str, Bound] = field(default_factory=dict)
    observations: Tuple[Observation, ...] = ()
    default_pacing: Optional[Bound] = None
    inputs: Tuple[Input, ...] = ()

    def at(self, node):
        """The plan entry for a parsed node, by its source position."""
        for observation in self.observations:
            if (observation.line, observation.column) == (node.line,
                                                          node.column):
                return observation
        return None

    def pacing_at(self, node):
        """The resolved pacing for a guest-input node, or ``None``.

        The runner asks rather than re-deriving: the scope that
        supplied a gap is a parse-time fact, and a failure report
        that names it can only do so if one answer was computed once.
        """
        for entry in self.inputs:
            if (entry.line, entry.column) == (node.line, node.column):
                return entry.pacing
        return None


def resolve(script):
    """Resolve a parsed script's whole timing plan."""
    default = _header_default(script)
    pacing = _header_pacing(script)
    run = _bound(script.deadline, "header", None,
                 script.headers.get("deadline", 0))
    deadlines = {}
    observations = []
    inputs = []
    if script.phases:
        for phase in script.phases:
            budget = _bound(phase.deadline, "phase", phase.name, phase.line)
            if budget is not None:
                deadlines[phase.name] = budget
            inner = _bound(phase.timeout, "phase", phase.name,
                           phase.line) or default
            inner_pacing = _bound(phase.pacing, "phase", phase.name,
                                  phase.line) or pacing
            if phase.handlers:
                # A reactive phase's timeout is itself a clock: the
                # interval it allows with no handler firing.
                observations.append(Observation(
                    "reactive interval", phase.line, phase.column,
                    phase.name, inner))
                for handler in phase.handlers:
                    _handler(handler, inner, inner_pacing, phase.name,
                             observations, inputs)
            else:
                _statements(phase.statements, inner, inner_pacing,
                            phase.name, observations, inputs)
    else:
        _statements(script.statements, default, pacing, None,
                    observations, inputs)
    return TimingPlan(default, run, dict(deadlines), tuple(observations),
                      pacing, tuple(inputs))


def format_plan(plan, name=None):
    """Render a timing plan the way ``check-script`` prints it."""
    lines = []
    if name:
        lines.append(f"timing plan for {name}")
        lines.append("")
    lines.append(f"default timeout: {plan.default}")
    if plan.default_pacing is not None:
        lines.append(f"default pacing: {plan.default_pacing}")
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
    if plan.inputs:
        lines.append("guest input:")
        for delivery in plan.inputs:
            where = f"line {delivery.line}"
            if delivery.phase is not None:
                where = f"{where} phase {delivery.phase}"
            lines.append(f"  {where} {delivery.verb}: "
                         f"pacing {delivery.pacing}")
    return "\n".join(lines) + "\n"


def _header_default(script):
    """The script-wide observation default, or the built-in one."""
    return _bound(script.timeout, "header", None,
                  script.headers.get("timeout", 0)) or Bound(
        DEFAULT_TIMEOUT, parse_duration(DEFAULT_TIMEOUT), "built-in")


def _header_pacing(script):
    """The script-wide input pacing, or the built-in one."""
    return _bound(script.pacing, "header", None,
                  script.headers.get("pacing", 0)) or Bound(
        DEFAULT_PACING, parse_duration(DEFAULT_PACING), "built-in")


def _bound(spelling, scope, scope_name, line):
    """A bound for a written duration, or ``None`` if none was."""
    if spelling is None:
        return None
    return Bound(spelling, parse_duration(spelling), scope, scope_name, line)


def _statements(statements, default, pacing, phase, observations, inputs):
    """Resolve a statement list under its innermost defaults."""
    for statement in statements:
        if statement.verb in INPUT_VERBS:
            inputs.append(Input(
                statement.verb, statement.line, statement.column, phase,
                _bound(statement.pacing, "statement", None,
                       statement.line) or pacing))
        if statement.verb == "select":
            # An observation-bearing action, so it lands in both
            # lists: its feedback watches run within the statement's
            # effective timeout, and it still delivers keys.
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
            _handler(handler, branching, pacing, phase, observations, inputs)


def _handler(handler, default, pacing, phase, observations, inputs):
    """Resolve one handler: its own hold, then its body.

    The branching ``wait`` above is the innermost *timeout* scope for
    this body and no scope at all for pacing — it cannot carry one —
    so the pacing default passes straight through from the phase.
    """
    observations.append(Observation(
        handler.keyword, handler.line, handler.column, phase, default,
        _bound(handler.stable, "statement", None, handler.line)))
    _statements(handler.statements, default, pacing, phase, observations,
                inputs)
