# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The error taxonomy: one root, four classes, one internal fault.

Every deliberate reliquary error subclasses :class:`ReliquaryError`,
so ``except ReliquaryError`` is always the catch-all. The four classes
are the CLI's exit codes and the API's exceptions under one mapping
(docs/spec/script-spec.md, "Error classes and exit codes"):

===================  =====  ==========================================
class                exit   what it says
===================  =====  ==========================================
``StaticError``      2      the authored input is illegal on its face
``PreflightError``   3      the input is legal; the world does not
                            satisfy it
``RunFailure``       4      the operation started and failed
``RunCancelled``     5      a deliberate stop at an event boundary
===================  =====  ==========================================

**The classes describe every surface, not only a script run** (D58).
They were named for a run's enforcement tiers and generalize
unchanged: a malformed blueprint is illegal from its text alone
exactly as a malformed script is, and naming a machine that does not
exist is a world condition exactly as an unbootable drive is. The
deciding questions are the same three in the same order — is it
decidable from the authored input alone, does the world satisfy the
input, did the work itself fail — and the surface the caller happened
to use is not among them. A capability reliquary declares but has not
wired is a ``PreflightError``: the request is legal and the world,
which includes what this build implements, does not satisfy it.

``0`` is success. ``1`` is a **fault** — never a user's mistake. It
has two populations and both are reliquary's own: an
:class:`InternalError`, an invariant reliquary detected in its own
state, and a genuine accident that never was a ``ReliquaryError`` at
all. A deliberate raise always lands in this hierarchy; a bare
builtin is reserved for the invariants python itself enforces.
"""


class ReliquaryError(Exception):
    """Root of every deliberate reliquary error.

    ``rule_id`` is the stable dotted identifier naming the rule this
    diagnostic enforces — ``obs.two-channels`` and its siblings. It
    lives here rather than on the classes below because the spec puts
    every id in **one namespace shared across the classes**
    (docs/spec/script-spec.md, "Error classes and exit codes"), and
    the field at the root is the code saying the same thing: a
    diagnostic's identity is independent of which tier raised it.

    An id is a **contract** — it is what a consumer switches on, so
    it is stable where the message text is not — and a *field* rather
    than text baked into a message, so switching needs no prose
    parsing and the beta id index can be generated.

    Identity is not location. Where a diagnostic can also say *where*
    it happened, that comes from the class: ``ScriptParseError`` and
    ``BlueprintError`` carry line and column, and the script runner's
    ``_Located`` cites the statement. Preflight diagnostics about the
    media namespace have no script line to cite and carry an id alone.

    ``None`` means no id is assigned yet, which is a measured gap
    rather than an estimate: the script conformance corpus asserts
    each fixture's id in both directions, so a marker recording a
    gap cannot outlive it.
    """

    #: Default for every subclass that does not set one.
    rule_id = None

    def __init__(self, *args, rule_id=None):
        super().__init__(*args)
        if rule_id is not None:
            self.rule_id = rule_id


class StaticError(ReliquaryError):
    """The authored input is illegal on its face."""


class PreflightError(ReliquaryError):
    """The input is legal and the world does not satisfy it."""


class RunFailure(ReliquaryError):
    """The operation started and failed."""


class RunCancelled(ReliquaryError):
    """A run deliberately stopped at an event boundary.

    Neither success nor failure, which is why it subclasses the root
    directly and never :class:`RunFailure`.
    """


class WaitExpired(RunFailure, TimeoutError):
    """A wait for something another actor would do ran out of time.

    **Two base classes, deliberately, because two true things are
    being said at once** (D90). A wait that expired is the work not
    happening, so it *is* a :class:`RunFailure` and exits ``4`` — and
    ``except ReliquaryError`` stays the catch-all it is contracted to
    be, which a bare builtin would have broken. But nothing about the
    machine went wrong and the thing waited for may still arrive, so a
    Python caller holding the loop wants the ordinary
    ``except TimeoutError`` and gets it.

    That reconciles two positions the record held separately: the
    async design's "expiry raises outside the taxonomy, the call
    repeats" (api.md, the run handle) and the standing invariant that
    no deliberate raise is a bare builtin — `TimeoutError` being named
    in the forbidden set by name. The first was written when nothing
    raised it yet; this is what honoring both looks like.
    """


class InternalError(ReliquaryError):
    """An invariant reliquary detected in its own state.

    Exit ``1``: no user input reaches this, so there is nothing for a
    caller to correct. It subclasses the root directly rather than
    joining the four, and it is deliberate rather than accidental —
    which is the whole reason it is a class instead of a bare
    ``RuntimeError``, since ``except ReliquaryError`` has to catch it.
    """


#: Success, and the code reserved for reliquary's own faults.
OK = 0
UNEXPECTED = 1

# Each of the four with its exit code and the name the terminal event
# states. Ordered most specific first so a future subclass never
# resolves to a broader ancestor's code. InternalError is absent on
# purpose: it falls through to UNEXPECTED, which is its code.
_TAXONOMY = (
    (RunCancelled, 5, "cancelled"),
    (StaticError, 2, "static-error"),
    (PreflightError, 3, "preflight-error"),
    (RunFailure, 4, "run-failure"),
)


def exit_code(error):
    """The exit code for ``error`` — ``1`` outside the four classes."""
    for class_, code, _name in _TAXONOMY:
        if isinstance(error, class_):
            return code
    return UNEXPECTED


def outcome(error):
    """The terminal event's outcome name for ``error`` (``None``: ok)."""
    if error is None:
        return "ok"
    for class_, _code, name in _TAXONOMY:
        if isinstance(error, class_):
            return name
    return "error"
