# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Agentless DOS guest adapter: prompt-based readiness and commands."""

import re
import sys
import time

from . import screen_stability
from .errors import RunFailure
from .machine_handle import Machine


_PROMPT_RE = re.compile(r"^[A-Z]:(\\[^>]*)?>$")

#: How often the screen is read while waiting for a command to finish.
#: The first seconds are polled hard and the rest slowly, because the
#: two waits want opposite things: the echo has to be *caught* before
#: the command's own output can scroll it away, and after that there
#: is nothing to catch, only a prompt to wait out.
_ECHO_POLL = 0.1
_ECHO_WINDOW = 3.0
_PROMPT_POLL = 2.0

#: And how often once a prompt *has* been seen, until the screen under
#: it settles. The slow interval waits a prompt out cheaply, but it
#: cannot confirm one: a quiescence window is only observable by
#: sampling inside it, and two reads two seconds apart say nothing
#: about the last 200ms. So the ramp gains a third rung rather than
#: losing its second — dense reads are spent only where the question
#: has become "is this screen finished?", and never for the whole of a
#: long command.
_SETTLE_POLL = 0.1

#: The outcome probe, and the word it looks for. `IF ERRORLEVEL n` is
#: true for *n or greater* and is portable across DOS shells in a way
#: `%ERRORLEVEL%` expansion is not, so a failing command prints the
#: sentinel and a succeeding one prints nothing at all. Both answers
#: are text reliquary composed and reads back, which is why this
#: attaches no meaning to the guest's own output (G2, P18): the
#: sentinel is not a word the command said, it is a word we did.
_PROBE_SENTINEL = "RLQ-EXEC-FAILED"
_PROBE_COMMAND = f"IF ERRORLEVEL 1 ECHO {_PROBE_SENTINEL}"


class AgentlessGuestExec:
    """Concrete GuestExec adapter for an agentless DOS guest."""

    def __init__(self, machine: Machine):
        self._machine = machine

    def wait_ready(self, timeout: float = 90) -> None:
        """Wait for a DOS prompt."""
        print("rlq: waiting for a DOS prompt...", file=sys.stderr)
        with self._machine.console() as console:
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                rows = [row for row in console.screen_text() if row]
                if rows and _PROMPT_RE.match(rows[-1]):
                    print(f"rlq: at DOS prompt: {rows[-1]}",
                          file=sys.stderr)
                    return
                time.sleep(2)
        raise RunFailure(
            f"timed out after {timeout}s waiting for a DOS prompt",
            rule_id="screen.no-match")

    def execute(self, command: str, timeout: float = 120, *,
                check: bool = False):
        """Type a DOS command, wait for the prompt, and return its output.

        The output is what the command left on the visible screen —
        the rows between its echo and the prompt that came back.
        Agentless capture has one honest limit: a command that
        scrolls more than a screenful leaves only its tail there.
        Reliquary attaches no meaning to any of it (G2); the text is
        the caller's to read.

        ``check`` asks the one question the rows cannot answer: **did
        it work?** A setup command's output is nothing and its success
        is everything, so success and failure otherwise come back
        looking identical. With ``check`` a command that signalled
        failure raises :class:`RunFailure` naming it, and the row
        return is unchanged either way — this adds a channel rather
        than reinterpreting the existing one.

        **A prompt alone does not mean this command finished.**
        :meth:`wait_ready` returns *because* a prompt is on screen, so
        a completion test that only asks for one is satisfied by the
        prompt already sitting there — and returns whatever was above
        it, which is the boot's output rather than the command's. The
        wait therefore needs evidence that *this* command landed: its
        echo, or failing that a screen that has changed since it was
        sent.
        """
        rows = self._run(command, timeout)
        if check:
            self._refuse_if_failed(command, timeout)
        return rows

    def _refuse_if_failed(self, command, timeout):
        """Ask the guest whether ``command`` signalled failure.

        Opt-in, and asked *after* the command has finished, so the
        ordinary path pays nothing. The probe is one more command at
        the prompt, read back through the same echo discipline as any
        other: its output is the sentinel or it is empty.

        **Its honest scope is commands that ran and signalled
        failure.** `COMMAND.COM` leaves ERRORLEVEL untouched when it
        cannot find a program at all, so a mistyped command escapes
        the probe and reads as success — recognizing the shell's own
        "Bad command or file name" would mean curating guest output
        spellings, which a localized DOS makes unbounded and which is
        the guessing P10 refuses. That limit is stated rather than
        papered over (P11), and a mistyped command is an authoring
        error caught in authoring.
        """
        try:
            output = self._run(_PROBE_COMMAND, timeout)
        except RunFailure as unreadable:
            raise RunFailure(
                f"could not read the outcome of {command!r}: the "
                f"ERRORLEVEL probe did not complete ({unreadable})",
                rule_id="command.outcome-unreadable") from unreadable
        if any(_PROBE_SENTINEL in row for row in output):
            raise RunFailure(
                f"command signalled failure: {command}",
                rule_id="command.signalled-failure")

    def _run(self, command, timeout):
        """Type one command, wait for the prompt, return its rows.

        **A prompt is not read the moment it appears.** It can arrive
        mid-scroll, or the bottom row can transiently resemble one
        while output is still drawing, and acting on either slices the
        output at a boundary that never existed — a short, plausible,
        wrong answer, which is the shape P11 forbids. So a completion
        is a candidate until the screen under it has settled
        (:mod:`screen_stability`), and the menu machinery's rule —
        look twice before believing a screen — finally reaches the
        command path, ten feet from where it was already in force.
        """
        with self._machine.console() as console:
            before = [row for row in console.screen_text() if row]
            console.send_text(command)
            sent = time.monotonic()
            deadline = sent + timeout
            echoed = False
            settling = screen_stability.ScreenStability()
            unsettled = None
            while time.monotonic() < deadline:
                now = time.monotonic()
                frame = console.screen()
                reading = settling.observe(frame, now=now)
                rows = [row for row in frame[0] if row]
                width = _screen_width(frame)
                # Sticky: once the echo has been seen, a later screen
                # without it is a scrolled one, not a command that
                # never ran. Nothing else can tell those apart.
                echoed = (echoed
                          or _echo_at(rows, command, width) is not None)
                landed = echoed or rows != before
                complete = bool(landed and rows
                                and _PROMPT_RE.match(rows[-1]))
                if complete and reading.stable:
                    return _command_output(rows, command, width,
                                           echoed=echoed)
                if complete:
                    unsettled = reading
                time.sleep(_poll_interval(complete, now - sent))
        raise RunFailure(
            f"timed out after {timeout}s waiting for command to finish: "
            f"{command}{_settling_note(unsettled)}",
            rule_id="screen.no-match")


def _poll_interval(confirming, elapsed):
    """How long to wait before the next read.

    Confirming outranks the ramp: once a prompt is on screen the
    question has changed from "has it finished?" to "is this screen
    finished?", and only the second needs dense reads.
    """
    if confirming:
        return _SETTLE_POLL
    return _ECHO_POLL if elapsed < _ECHO_WINDOW else _PROMPT_POLL


def _settling_note(reading):
    """Why a completion that *was* seen never ended the wait.

    A wait now expires two ways that look identical from outside: the
    prompt never came, or it came only on screens still being drawn.
    The second is baffling without help — a screenshot taken at the
    time shows the prompt plainly — so the failure says which, and
    names the region it set aside as decoration, that being what makes
    the message locate the problem rather than restate the expiry.
    """
    if reading is None:
        return ""
    note = ("; a prompt was on screen but what sits under it never "
            "settled")
    if reading.stability is None:
        return f"{note} (never read often enough to tell)"
    note += f" (stability {reading.stability:.3f}"
    if reading.animated:
        note += (f", outside a {len(reading.animated)}-cell animated "
                 "region")
    return f"{note})"


def _screen_width(frame):
    """How many cells wide the screen is, read off the attribute rows.

    The text rows cannot say: they come back right-stripped, so a
    full row and a short one are told apart only by the attribute
    half of the seam's contract, which carries one token per cell
    whatever the backend. A frame with no attribute rows has no
    width to offer, and ``0`` says so — wrapping is then undetectable
    and only a one-row echo can be found.
    """
    return max((len(row) for row in frame[1]), default=0)


def _echo_at(rows, command, width=0):
    """Where the command's echo ends in ``rows``, or ``None``.

    The echo is the guest repeating back what was typed at it: the
    prompt and the command on one line. **A line longer than the
    screen is wide wraps**, and the guest wraps it by the cell — a
    full row, then the rest — so an 85-column command leaves no row
    that ends with it, and the echo is the *last* of the rows it
    spans. The scan walks upward from each candidate row, matching
    the command's tail on that row and then exactly the ``width``
    characters the guest would have drawn on each row above, so a
    row that merely happens to be full is never mistaken for a
    continuation: what sits on it has to be the command's own text.
    ``width`` is the screen's cell width; ``0`` means it is unknown,
    and only an unwrapped echo can then be found.

    The last row of the echo is the index returned, since the
    command's output starts on the row after it.
    """
    needle = command.strip()
    if not needle:
        return None
    for index in range(len(rows) - 1, -1, -1):
        if _echo_ends_at(rows, index, needle, width):
            return index
    return None


def _echo_ends_at(rows, index, needle, width):
    """Whether ``needle``'s echo ends on ``rows[index]``, wrapped or not.

    Rows arrive right-stripped, so the chunk of the line a row held
    is compared stripped as well — a wrap falling on a space inside
    the command leaves a row shorter than the screen, and the match
    restores that space from the command rather than asking the row
    for what the stripping took.
    """
    text = rows[index].rstrip()
    if text.endswith(needle):
        return ">" in text
    if not width or not text or not needle.endswith(text):
        return False
    remaining = needle[:-len(text)]
    for row in range(index - 1, -1, -1):
        text = rows[row].rstrip()
        if len(remaining) >= width:
            if text != remaining[-width:].rstrip():
                return False
            remaining = remaining[:-width]
            if not remaining:
                # The command began at column zero: the prompt filled
                # the row above by itself.
                return row > 0 and ">" in rows[row - 1]
            continue
        # The first row: the prompt, then the head of the command,
        # filling the row exactly — that is what made it wrap.
        head = remaining.rstrip()
        stripped_away = len(remaining) - len(head)
        return (text.endswith(head)
                and len(text) + stripped_away == width
                and ">" in text[:len(text) - len(head)])
    return False


def _command_output(rows, command, width=0, *, echoed):
    """The rows a command produced, between its echo and the prompt.

    ``rows`` are the non-blank screen rows, the last being the prompt
    that came back, and ``width`` the screen's cell width, which is
    what lets an echo that wrapped be found at all.

    ``echoed`` says whether the echo was seen at any point during the
    wait, and it is what separates the two ways the echo can be
    missing from the final screen. **Scrolled off** — the command
    produced more than a screenful, which is agentless capture's
    documented limit — leaves the visible tail, which is the honest
    answer. **Never there at all** means the command's output could
    not be located, and returning the rows above the prompt would
    hand back somebody else's text as though it were the answer. That
    is a failure to report, not a value to return (P11).
    """
    end = len(rows) - 1
    index = _echo_at(rows[:end], command, width)
    if index is not None:
        return tuple(rows[index + 1:end])
    if echoed:
        return tuple(rows[:end])
    raise RunFailure(
        f"the guest never echoed {command!r}, so what is on screen "
        "cannot be attributed to it — reliquary will not return text "
        "it cannot place", rule_id="screen.no-echo")
