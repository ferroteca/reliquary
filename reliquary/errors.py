# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""The error taxonomy: one root, four run-surface classes.

Every deliberate reliquary error subclasses :class:`ReliquaryError`,
so ``except ReliquaryError`` is always the catch-all. The run
surface's four classes are the CLI's exit codes and the API's
exceptions under one mapping (planning/design/script-spec.md,
"Error classes and exit codes"):

===================  =====  ==========================================
class                exit   tier
===================  =====  ==========================================
``StaticError``      2      legality rules, from the script text alone
``PreflightError``   3      machine rules, before the first input
``RunFailure``       4      the dynamic semantics, during the run
``RunCancelled``     5      a deliberate stop at an event boundary
===================  =====  ==========================================

``0`` is success and ``1`` is precisely an error *outside* the
taxonomy — reliquary's own unexpected fault. A deliberate error with
no run-surface class subclasses the root directly and exits ``1``
until the general programmatic-contract work names finer classes;
growth there is additive, never a break (planning/design/api.md).
"""


class ReliquaryError(Exception):
    """Root of every deliberate reliquary error."""


class StaticError(ReliquaryError):
    """A legality rule the script text alone violates."""


class PreflightError(ReliquaryError):
    """A machine rule broken before the first guest input."""


class RunFailure(ReliquaryError):
    """The run's dynamic semantics failed."""


class RunCancelled(ReliquaryError):
    """A run deliberately stopped at an event boundary.

    Neither success nor failure, which is why it subclasses the root
    directly and never :class:`RunFailure`.
    """


#: Success, and the code reserved for faults outside the taxonomy.
OK = 0
UNEXPECTED = 1

# Each run-surface class with its exit code and the name the
# terminal event states. Ordered most specific first so a future
# subclass never resolves to a broader ancestor's code.
_TAXONOMY = (
    (RunCancelled, 5, "cancelled"),
    (StaticError, 2, "static-error"),
    (PreflightError, 3, "preflight-error"),
    (RunFailure, 4, "run-failure"),
)


def exit_code(error):
    """The exit code for ``error`` — ``1`` outside the taxonomy."""
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
