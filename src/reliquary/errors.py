# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The error classes reliquary raises, and the exit code each maps to.

Every error reliquary raises on purpose is a subclass of
:class:`ReliquaryError`, so ``except ReliquaryError`` always catches
all of them. There are four classes, and they are both the CLI's exit
codes and the API's exception hierarchy, from one table
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

**These four classes apply everywhere in reliquary, not only to a
script run** (D58). They were first defined for what a script run
checks at each stage, but the same three questions decide any error,
on any surface: can you tell it's wrong just by reading the input,
does the world satisfy the input, did the operation itself fail? A
malformed blueprint is a ``StaticError`` for the same reason a
malformed script is: you can tell from its text alone. Naming a
machine that does not exist is a ``PreflightError`` for the same
reason an unbootable drive is: it's a fact about the world, not about
the input's text. It does not matter which surface (CLI command, API
call, etc.) raised the error. A capability reliquary has declared but
not actually wired up is also a ``PreflightError``: the request is
legal, but this build does not (yet) satisfy it.

Exit code ``0`` is success. Exit code ``1`` means reliquary itself is
at fault — it is never the user's mistake. That happens in two ways:
either an :class:`InternalError` was raised because reliquary caught
itself in a broken state, or some other, unplanned-for Python
exception occurred that was never one of reliquary's own error
classes. Every error reliquary raises on purpose belongs to this
hierarchy; a plain built-in exception (like a bare ``ValueError``) is
reserved for the errors Python itself raises, not for reliquary's.
"""


class ReliquaryError(Exception):
    """Base class every error reliquary raises on purpose inherits from.

    ``rule_id`` is a stable dotted name identifying which rule the
    error is enforcing, such as ``obs.two-channels``. It lives on this
    base class, not on the subclasses below, because the spec keeps
    every rule id in one shared namespace across all four error
    classes (docs/spec/script-spec.md, "Error classes and exit
    codes") — putting the field here says the same thing in code: an
    error's identity does not depend on which of the four classes
    raised it.

    ``rule_id`` is a stable field a caller can switch on, unlike the
    human-readable message text, which can change. Keeping it as a
    separate field (rather than embedding it in the message) means no
    one has to parse the message to find it, and it lets the docs
    generate an index of every rule id automatically.

    ``rule_id`` says *what* rule fired, not *where*. Where an error
    happened comes from the specific subclass instead:
    ``ScriptParseError`` and ``BlueprintError`` carry a line and
    column, and the script runner's ``_Located`` names the statement.
    A preflight error about the media catalog has no script line to
    point to, so it carries only a rule id.

    ``rule_id`` is ``None`` when no id has been assigned to that error
    yet. That is a known, tracked gap, not a guess: the script
    conformance test suite checks every fixture's id in both
    directions, so a ``None`` here cannot silently linger once that
    gap is filled.
    """

    #: The default when a subclass does not set its own rule_id.
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
    """Raised when a wait for something another actor would do times out.

    This class inherits from both ``RunFailure`` and ``TimeoutError``
    on purpose, because both are true at once (D90). The wait expiring
    means the expected work never happened, so it counts as a
    :class:`RunFailure` and exits with code ``4`` — and
    ``except ReliquaryError`` still catches it, the way it's supposed
    to catch every deliberate error. But nothing about the machine
    actually broke, and the thing being waited for might still show up
    later, so Python code that's polling in a loop can catch it with
    the ordinary ``except TimeoutError`` too.

    Inheriting from both classes reconciles two things that were
    written separately and would otherwise conflict: the async design
    said an expired wait should raise a plain ``TimeoutError`` outside
    reliquary's error hierarchy so the caller can just retry the call
    (api.md, the run handle), while the project's standing rule is
    that reliquary never raises a bare built-in exception on purpose —
    ``TimeoutError`` was even named explicitly as one of the forbidden
    ones. The async design was written before anything actually raised
    a wait-expiry error; this class is what satisfying both rules
    looks like once something does.
    """


class UnreadableScreen(RunFailure):
    """Raised when a captured screen isn't text this build can read.

    Raised by the fixed-font recognizer when the backend has no native
    way to read VGA text and the guest is showing something the
    80x25 text-mode contract can't describe — for example a BIOS
    splash screen in a graphics mode, or a resolution whose cells the
    glyph bank doesn't have matching glyphs for.

    It's a :class:`RunFailure`, not one of the other three classes,
    because none of them fit: nothing about the authored blueprint or
    script is illegal, so exit code ``2`` would blame the wrong thing;
    nothing about the host fails to satisfy the input either, so it's
    not a preflight problem. What actually happened is that reliquary
    tried to read the screen and failed, which is the operation
    itself failing.

    A script run never lets this exception escape: `script_runner`
    catches it and records the sample as unreadable, so a wait just
    keeps polling until the guest reaches a text mode, and only times
    out on its own clock if it never does. This exception escapes
    uncaught only for callers that ask for a single screen and have no
    clock of their own to fall back on — `rlq screen` and the other
    console commands — where exiting with code ``4`` and this error
    message is the right answer.
    """


class InternalError(ReliquaryError):
    """Raised when reliquary catches its own state violating an invariant.

    Exits with code ``1``. No user input caused this, so there's
    nothing for the caller to fix. It inherits directly from
    ``ReliquaryError`` rather than from any of the four main classes,
    because it isn't a case of bad input, a preflight problem, or a
    failed operation — it's reliquary catching a bug in itself. It's
    raised on purpose, as its own class, rather than as a bare
    ``RuntimeError``, specifically so that ``except ReliquaryError``
    still catches it.
    """


#: Success, and the exit code reserved for reliquary's own faults.
OK = 0
UNEXPECTED = 1

# Each of the four error classes with its exit code and the name used
# in the terminal event. Listed most-specific-first, so a future
# subclass of one of these is never mistakenly matched against a
# broader ancestor's code first. InternalError isn't listed here on
# purpose: it isn't matched below, so it falls through to
# UNEXPECTED (1), which is the exit code it should have anyway.
_TAXONOMY = (
    (RunCancelled, 5, "cancelled"),
    (StaticError, 2, "static-error"),
    (PreflightError, 3, "preflight-error"),
    (RunFailure, 4, "run-failure"),
)


def exit_code(error):
    """Return the exit code for ``error``; 1 if it's none of the four."""
    for class_, code, _name in _TAXONOMY:
        if isinstance(error, class_):
            return code
    return UNEXPECTED


def outcome(error):
    """Return the terminal event's outcome name for ``error``.

    Returns ``"ok"`` when ``error`` is ``None``.
    """
    if error is None:
        return "ok"
    for class_, _code, name in _TAXONOMY:
        if isinstance(error, class_):
            return name
    return "error"
