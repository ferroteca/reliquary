# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
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
    """Root of every deliberate reliquary error."""


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
