# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Agentless DOS guest adapter: prompt-based readiness and commands."""

import re
import sys
import time

from . import screen_stability
from .errors import RunFailure, WaitExpired
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

#: How often the screen is read while a boot is still under way. A
#: boot is seconds to minutes with nothing to catch along the way, so
#: it is waited out at the slow rate and the dense one is spent only
#: once a prompt is on screen and the question is whether it settled.
_READY_POLL = 2.0

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

    def wait_ready(self, timeout: float = 90, *,
                   prompt: str | None = None) -> None:
        """Wait for a DOS prompt.

        The standard shape, or exactly ``prompt`` when the caller
        declares one (D113): there is no earlier screen here to read
        a customized prompt off, the way :meth:`execute` does (D112),
        so a guest that boots to one is recognized only when the
        caller says what it draws — the script language's own
        ``wait "C:\\>"`` stance, at the API. The text is the bottom
        row as the guest draws it, compared exactly; a pattern is
        the wider door D112 refused.

        **A prompt is not ready the moment it appears** (D115). The boot
        is the screen likeliest to still be moving — an
        ``AUTOEXEC.BAT`` with ``ECHO ON`` paints the prompt and then
        the command on the same row, and the standard shape matches
        the row in between — so a prompt is a candidate until the
        screen under it has settled (:mod:`screen_stability`), the
        same rule :meth:`execute` holds its completion to. The
        hazard is weaker here (nothing is sliced, a caller merely
        proceeds early and its first command reads a screen still
        painting), and the rule is the same because what the actor
        does next does not change whether the screen was finished.

        Expiry raises :class:`~reliquary.errors.WaitExpired` — a
        ``RunFailure`` *and* a ``TimeoutError`` (D90, D114): the
        prompt not arriving is the work not happening, while nothing
        about the machine went wrong and the boot may still finish,
        so a caller holding the loop asks again. A prompt that was
        seen but never settled is said to be, as :meth:`execute`
        says it.
        """
        print("rlq: waiting for a DOS prompt...", file=sys.stderr)
        with self._machine.console() as console:
            deadline = time.monotonic() + timeout
            settling = screen_stability.ScreenStability()
            unsettled = None
            while time.monotonic() < deadline:
                now = time.monotonic()
                frame = console.screen()
                reading = settling.observe(frame, now=now)
                rows = [row for row in frame[0] if row]
                candidate = bool(rows and _is_prompt(rows[-1], prompt))
                if candidate and reading.stable:
                    print(f"rlq: at DOS prompt: {rows[-1]}",
                          file=sys.stderr)
                    return
                if candidate:
                    unsettled = reading
                time.sleep(_SETTLE_POLL if candidate else _READY_POLL)
        declared = f" or for {prompt!r}" if prompt else ""
        raise WaitExpired(
            f"timed out after {timeout}s waiting for a DOS prompt"
            f"{declared}{_settling_note(unsettled)}",
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
            # The prompt the command is typed at: the echo sits where
            # it was (D111), and its coming back is completion (D112).
            prompt = before[-1] if before else ""
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
                echoed = (echoed or
                          _echo_at(rows, before, command, width) is not None)
                landed = echoed or rows != before
                complete = bool(landed and rows
                                and _is_prompt(rows[-1], prompt))
                if complete and reading.stable:
                    return _command_output(rows, before, command, width,
                                           echoed=echoed)
                if complete:
                    unsettled = reading
                time.sleep(_poll_interval(complete, now - sent))
        raise RunFailure(
            f"timed out after {timeout}s waiting for command to finish: "
            f"{command}{_settling_note(unsettled)}{_prompt_note(prompt)}",
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
    """Why a prompt that *was* seen never ended the wait.

    The shared note (:func:`screen_stability.unsettled_note`) in
    this adapter's words: what was on screen here is a prompt.
    """
    return screen_stability.unsettled_note(reading).replace(
        "a match was on screen", "a prompt was on screen", 1)


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


def _is_prompt(row, prompt):
    """Whether ``row`` is a prompt the wait may complete on (D112).

    Two shapes, and no third. The standard DOS prompt, ``X:\\path>``,
    is what every unconfigured DOS draws, and it is what lets a
    command that changes the prompt's *text* — ``CD`` — complete. And
    exactly the prompt the guest was sitting at when the command was
    sent, whatever its shape: the guest's own statement of what its
    prompt looks like (D72), which needs no pattern and is what makes
    a customized guest usable from its first command. A wider pattern
    is the false positive P11 refuses — any row ending in ``>`` would
    become a completion signal.
    """
    return bool(_PROMPT_RE.match(row) or (prompt and row == prompt))


def _prompt_note(prompt):
    """What the expired wait was waiting for, so the reader looks here.

    A command that changes a customized prompt — ``PROMPT`` itself,
    or ``CD`` under one — returns to text the wait has no evidence
    for, and the expiry has to say so: "the guest never returned to
    the prompt" sends the reader to the guest, which ran the command
    perfectly well.
    """
    if not prompt:
        return ""
    return (f"; waited for a standard DOS prompt or for {prompt!r}, which "
            "the guest was at — a command that changes the prompt to "
            "another shape returns to text exec has no evidence for")


def _echo_rows(prompt, command, width):
    """The rows the guest draws when ``command`` is typed at ``prompt``.

    One line, ``prompt + command``, broken by the cell at ``width``
    and right-stripped row by row, as the screen reads back; a chunk
    that strips to nothing is dropped, as the blank-row filter drops
    it from the screen. ``width`` ``0`` means unknown, and the line
    then stands as one row.
    """
    line = (prompt + command).rstrip()
    if not line:
        return []
    if not width:
        return [line]
    chunks = [line[start:start + width].rstrip()
              for start in range(0, len(line), width)]
    return [chunk for chunk in chunks if chunk]


def _echo_at(rows, before, command, width=0):
    """Where the command's echo ends in ``rows``, or ``None`` (D111).

    The echo is not found by its looks. The command was typed at the
    prompt ``before`` ends with, so the echo is that row with the
    command appended — wrapped by the cell when longer than the
    screen is wide — and it sits *where the prompt was*: the rows
    above it are the rows that were above the prompt, less whatever
    scrolled off the top. Everything the command prints lands below
    it, so a row that merely spells the same text (a file whose last
    line is the echo of the command that types it) is never taken
    for the echo — what sits above it is the command's own output
    rather than the screen the command was typed into. The scan
    starts where the prompt was and moves up, since scrolling is the
    only way the echo moves, and the candidate needing the least of
    it wins — the same command run twice finds the second echo, not
    the first. The one screen this cannot tell apart is output
    longer than a screenful whose first visible row is such a
    lookalike: nothing is left above it to contradict it.

    The last row of the echo is the index returned, since the
    command's output starts on the row after it. ``width`` is the
    screen's cell width; ``0`` means it is unknown, and only an
    unwrapped echo can then be found.
    """
    prompt = before[-1] if before else ""
    echo = _echo_rows(prompt, command, width)
    if not echo:
        return None
    above = before[:-1]
    # From where the prompt was, upward: the echo can only have moved
    # up, by scrolling, and the candidate that needs the least of it
    # is the one every row above is accounted for.
    for start in range(min(len(above), len(rows) - len(echo)), -1, -1):
        if rows[start:start + len(echo)] != echo:
            continue
        if rows[:start] != above[len(above) - start:]:
            continue
        return start + len(echo) - 1
    return None


def _command_output(rows, before, command, width=0, *, echoed):
    """The rows a command produced, between its echo and the prompt.

    ``rows`` are the non-blank screen rows, the last being the prompt
    that came back; ``before`` the non-blank rows of the screen the
    command was typed into, which is what places the echo; and
    ``width`` the screen's cell width, which is what lets an echo
    that wrapped be found at all.

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
    index = _echo_at(rows[:end], before, command, width)
    if index is not None:
        return tuple(rows[index + 1:end])
    if echoed:
        return tuple(rows[:end])
    raise RunFailure(
        f"the guest never echoed {command!r}, so what is on screen "
        "cannot be attributed to it — reliquary will not return text "
        "it cannot place", rule_id="screen.no-echo")
