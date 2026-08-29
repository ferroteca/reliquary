# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The timing model for the reliquary script language.

There are three kinds of timing settings, and each is scoped
differently (see docs/spec/script-spec.md, "Timing"):

- ``timeout`` and ``stable`` are per-observation settings, and they
  are **lexically scoped**: a container's ``timeout`` becomes the
  default for every observation lexically inside it. The innermost
  setting wins -- statement, then branching ``wait``, then phase,
  then header, then the built-in 60s default. This is entirely
  decided at parse time.
- ``deadline`` is a **budget**, dynamically scoped to one
  activation. It is never inherited, so there is no resolution to
  do: a phase's budget is whatever is written on that phase, and
  the header's deadline bounds the whole run.
- ``pacing`` is a per-guest-input setting, lexically scoped the
  same way as ``timeout``/``stable`` -- statement, phase, header,
  then the built-in 0.1s default. It has no branching-``wait``
  level, because an observation container can't carry pacing:
  pacing paces the actor sending input, and a ``wait`` doesn't send
  input.

Because of this, :func:`resolve` computes the whole timing plan up
front: every observation's effective timeout and which scope
supplied it, every guest-input verb's effective pacing and its
scope, each phase's budget, and the run's deadline. ``run-script
--dry-run`` prints this plan, a timing failure names the clock that
expired and where it came from, and the runner never has to
re-derive a bound -- it is always handed one that was already
resolved.

This module works structurally over the typed tree and does not
import any node type.
"""

from dataclasses import dataclass, field
from typing import Mapping, Optional, Tuple

from .errors import StaticError

# The built-in timeout for an observation, used when nothing else sets one.
DEFAULT_TIMEOUT = "60s"

# The built-in gap before the first key event of a guest-input verb.
# This is deliberately small, and it's a floor, not an estimate
# (D69): what makes a guest ready to *read* input differs from
# screen to screen -- an installer arming its keyboard handler vs. a
# shell entering its read loop -- so no single number is right for
# every case, which is why the per-phase and per-statement overrides
# matter. The value is nonzero because that readiness can't be
# observed directly (G1).
DEFAULT_PACING = "0.1s"

# The built-in stability threshold: the proportion of the screen that
# must stay unchanged before a sample counts as stable enough to
# evaluate a condition against. This number comes from the screen's
# geometry, not a guess. A text screen is 80 x 25 = 2000 cells, so
# one row of text is 80 of them -- 4% -- and any threshold looser
# than 0.96 would call a screen stable while a line is still being
# drawn into it. Screen furniture (a cursor, a clock) changes far
# fewer cells than that -- a cursor is 1 cell, a clock is 8 -- so
# 0.99 sits between the two: above what furniture changes, below what
# content changes. It's not written anywhere by default on purpose --
# forcing every script author to spell this value out themselves was
# exactly the extra work the pacing design round pushed back against.
DEFAULT_STABILITY = "0.99"

_UNITS = {"ms": 0.001, "s": 1.0, "m": 60.0, "h": 3600.0}

#: The verbs that send keystrokes to the guest, and so wait out the
#: pacing gap before their first key event. Host-side verbs
#: (``insert``, ``eject``, ``set-boot``, ``screenshot``, ``start``,
#: ``stop``, ``set``, ``http``) don't send guest input, so they
#: don't pay this gap.
INPUT_VERBS = frozenset({"enter", "type", "press", "select", "click"})


def parse_duration(spelling):
    """Convert a duration spelling (such as "5s") into seconds.

    The lexer has already checked that `spelling` is a valid
    duration, so this only raises for a value that didn't come
    from a parsed script.
    """
    unit = "ms" if spelling.endswith("ms") else spelling[-1:]
    try:
        return float(spelling[:-len(unit)]) * _UNITS[unit]
    except (KeyError, ValueError):
        raise StaticError(f"not a duration: {spelling!r}",
                          rule_id="time.not-a-duration") from None


class _Sourced:
    """Mixin shared by resolved settings, for naming the scope they came from.

    Both a failure message and a dry-run plan report need to say
    *where* a setting's value came from, and that sentence is
    written the same way whether the setting is a duration or a
    proportion.
    """

    @property
    def source(self):
        """Where this value came from, worded the way a failure or plan report states it."""
        where = self.scope
        if self.scope_name is not None:
            where = f"{where} {self.scope_name}"
        if self.line:
            where = f"{where} (line {self.line})"
        return where

    def __str__(self):
        return f"{self.spelling} from the {self.source}"


@dataclass(frozen=True)
class Bound(_Sourced):
    """One resolved clock: its duration and where it came from."""

    spelling: str
    seconds: float
    scope: str                    # "statement", "phase", "header", ...
    scope_name: Optional[str] = None
    line: int = 0


@dataclass(frozen=True)
class Level(_Sourced):
    """One resolved proportion setting: its value and where it came from.

    This is Bound's counterpart for a setting that isn't a duration.
    Stability is a fraction of the screen, not a span of time, so it
    gets its own record instead of reusing a field named ``seconds``
    -- the same reason the language calls this setting `stability`,
    not `stable`.
    """

    spelling: str
    value: float
    scope: str
    scope_name: Optional[str] = None
    line: int = 0


@dataclass(frozen=True)
class Observation:
    """One observation in the plan, with the clocks that bound it."""

    kind: str                     # "wait", "branching wait", "on", ...
    line: int
    column: int
    phase: Optional[str]
    timeout: Bound
    stable: Optional[Bound] = None
    stability: Optional[Level] = None
    #: The landmark this observation watches for, if it watches one
    #: (F65). A dry run prints it: a landmark wait costs the same
    #: clock as any other wait, but it also needs something extra --
    #: an asset on disk and a plane that can capture pixels -- and
    #: that's exactly what a reader checking the plan wants to see.
    landmark: Optional[str] = None


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
    default_stability: Optional[Level] = None

    def at(self, node):
        """Return the observation plan entry for a parsed node, matched by its line/column."""
        for observation in self.observations:
            if (observation.line, observation.column) == (node.line,
                                                          node.column):
                return observation
        return None

    def pacing_at(self, node):
        """The resolved pacing for a guest-input node, or ``None``.

        The runner looks this up instead of recomputing it: which
        scope supplied the gap is decided at parse time, and a
        failure message can only name that scope if it was computed
        once and reused.
        """
        for entry in self.inputs:
            if (entry.line, entry.column) == (node.line, node.column):
                return entry.pacing
        return None


def resolve(script):
    """Resolve a parsed script's whole timing plan."""
    default = _header_default(script)
    pacing = _header_pacing(script)
    stability = _header_stability(script)
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
            inner_stability = _level(phase.stability, "phase", phase.name,
                                     phase.line) or stability
            if phase.handlers:
                # A reactive phase's timeout is itself a clock: it's
                # the interval the phase allows to pass with no
                # handler firing.
                observations.append(Observation(
                    "reactive interval", phase.line, phase.column,
                    phase.name, inner, None, inner_stability))
                for handler in phase.handlers:
                    _handler(handler, inner, inner_pacing, inner_stability,
                             phase.name, observations, inputs)
            else:
                _statements(phase.statements, inner, inner_pacing,
                            inner_stability, phase.name, observations,
                            inputs)
    else:
        _statements(script.statements, default, pacing, stability, None,
                    observations, inputs)
    return TimingPlan(default, run, dict(deadlines), tuple(observations),
                      pacing, tuple(inputs), stability)


def format_plan(plan, name=None):
    """Render a timing plan the way a dry run prints it."""
    lines = []
    if name:
        lines.append(f"timing plan for {name}")
        lines.append("")
    lines.append(f"default timeout: {plan.default}")
    if plan.default_pacing is not None:
        lines.append(f"default pacing: {plan.default_pacing}")
    if plan.default_stability is not None:
        lines.append(f"default stability: {plan.default_stability}")
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
            # Only shown when it differs from the default: the
            # default stability is already printed once above, and
            # repeating it on every line would bury the observations
            # that actually override it.
            if (observation.stability is not None
                    and observation.stability is not
                    plan.default_stability):
                entry += f"; stability {observation.stability}"
            if observation.landmark is not None:
                entry += f"; landmark @{observation.landmark}"
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


def _header_stability(script):
    """The script-wide quiescence gate, or the built-in one."""
    return _level(script.stability, "header", None,
                  script.headers.get("stability", 0)) or Level(
        DEFAULT_STABILITY, float(DEFAULT_STABILITY), "built-in")


def _landmark(node):
    """The landmark an observation watches for, or ``None``.

    This reads the landmark straight off the node's own conditions
    instead of having it passed down: a branching wait itself
    carries no landmark, but each of its handlers carries its own,
    and that's exactly what the plan needs to show.
    """
    for condition in getattr(node, "conditions", ()):
        if condition.kind == "landmark":
            return condition.value
    return None


def _level(spelling, scope, scope_name, line):
    """A Level for a written proportion, or ``None`` if none was written."""
    if spelling is None:
        return None
    return Level(spelling, float(spelling), scope, scope_name, line)


def _bound(spelling, scope, scope_name, line):
    """A Bound for a written duration, or ``None`` if none was written."""
    if spelling is None:
        return None
    return Bound(spelling, parse_duration(spelling), scope, scope_name, line)


def _statements(statements, default, pacing, stability, phase,
                observations, inputs):
    """Resolve a list of statements using the innermost defaults passed in.

    A ``with`` block is invisible to the timing model: it can't
    carry a timing modifier of its own, so it doesn't introduce a
    new scope. Statements inside a ``with`` block resolve against
    exactly the same defaults they would have outside it -- nothing
    here treats a ``with`` block specially.
    """
    for statement in statements:
        units = getattr(statement, "units", None)
        if units is not None:
            _statements(units, default, pacing, stability, phase,
                        observations, inputs)
            continue
        if not hasattr(statement, "verb"):
            continue                  # a phase -- resolve() already handles those
        if statement.verb in INPUT_VERBS:
            inputs.append(Input(
                statement.verb, statement.line, statement.column, phase,
                _bound(statement.pacing, "statement", None,
                       statement.line) or pacing))
        if statement.verb == "select":
            # `select` both watches and sends input, so it's added
            # to both lists here: its feedback checks run within the
            # statement's effective timeout, and it also delivers
            # keystrokes.
            observations.append(Observation(
                "select", statement.line, statement.column, phase, default,
                None, stability))
            continue
        if statement.verb == "click":
            # Like `select`, `click` is added to the plan twice: its
            # search is a real landmark match (using F65's own
            # machinery), not select's text scan, so it also carries
            # a landmark, the way a `wait` does.
            observations.append(Observation(
                "click", statement.line, statement.column, phase, default,
                None, stability, statement.arguments[0]))
            continue
        if statement.verb != "wait":
            continue
        own = _level(statement.stability, "statement", None,
                     statement.line) or stability
        if not statement.handlers:
            inner = _bound(statement.timeout, "statement", None,
                           statement.line) or default
            observations.append(Observation(
                "wait", statement.line, statement.column, phase, inner,
                _bound(statement.stable, "statement", None, statement.line),
                own, _landmark(statement)))
            continue
        # A branching wait's timeout bounds how long it can take to
        # reach the first matching handler, and it's the innermost
        # scope for the observations its handlers lexically contain.
        # Unlike `stable`, `stability` can be written here: an
        # unstable frame skips evaluating all of the handlers, so
        # the stability gate belongs to the sample as a whole, which
        # means it belongs to the container.
        branching = _bound(statement.timeout, "branching wait", None,
                           statement.line) or default
        inherited = _level(statement.stability, "branching wait", None,
                           statement.line) or stability
        observations.append(Observation(
            "branching wait", statement.line, statement.column, phase,
            branching, None, inherited))
        for handler in statement.handlers:
            _handler(handler, branching, pacing, inherited, phase,
                     observations, inputs)


def _handler(handler, default, pacing, stability, phase, observations,
             inputs):
    """Resolve one handler: its own wait, then the statements in its body.

    The branching ``wait`` containing this handler is the innermost
    *timeout* scope for the handler's body, but it isn't a pacing
    scope at all -- a branching wait can't carry a pacing setting --
    so the pacing default passes straight through from the phase
    unchanged. It *is* a stability scope, though, which is where the
    timeout and pacing scoping rules diverge.
    """
    own = _level(handler.stability, "statement", None,
                 handler.line) or stability
    observations.append(Observation(
        handler.keyword, handler.line, handler.column, phase, default,
        _bound(handler.stable, "statement", None, handler.line), own,
        _landmark(handler)))
    _statements(handler.statements, default, pacing, own, phase,
                observations, inputs)
