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

#: How often the screen is read while waiting for a command to
#: finish. The first few seconds are polled fast, the rest slowly,
#: because the two phases of the wait want different things: the
#: command's echo has to be caught before the command's own output
#: scrolls it off the top of the screen, and after that there is
#: nothing left to catch — just a prompt to wait for.
_ECHO_POLL = 0.1
_ECHO_WINDOW = 3.0
_PROMPT_POLL = 2.0

#: How often the screen is read once a prompt has been seen, while
#: waiting for the screen under it to stop changing. The slow poll
#: interval above is cheap for waiting a prompt out, but it can't
#: confirm the screen has actually settled: whether the screen is
#: still changing can only be told by reading during the window in
#: question, and two reads two seconds apart say nothing about the
#: 200ms right before the second one. So there are three poll rates
#: in total, not two: fast reads are only spent once the question has
#: become "has this screen actually stopped changing?", not for the
#: whole length of a long-running command.
_SETTLE_POLL = 0.1

#: How often the screen is read while a boot is still in progress. A
#: boot can take anywhere from seconds to minutes with nothing that
#: needs to be caught along the way, so it is waited out at the slow
#: rate; fast reads only start once a prompt shows up on screen and
#: the question becomes whether it has settled.
_READY_POLL = 2.0

#: The command that probes whether the last command failed, and the
#: word it prints when it did. `IF ERRORLEVEL n` is true for n *or
#: greater*, and works across DOS shells in a way `%ERRORLEVEL%`
#: expansion does not, so a failing command prints the sentinel word
#: and a succeeding one prints nothing. Both outcomes are text
#: Reliquary itself wrote and then reads back — this deliberately
#: attaches no meaning to anything the guest itself printed (G2,
#: P18): the sentinel is a word Reliquary said, not a word the
#: command said.
_PROBE_SENTINEL = "RLQ-EXEC-FAILED"
_PROBE_COMMAND = f"IF ERRORLEVEL 1 ECHO {_PROBE_SENTINEL}"


class AgentlessGuestExec:
    """Concrete GuestExec adapter for an agentless DOS guest."""

    def __init__(self, machine: Machine):
        self._machine = machine

    def wait_ready(self, timeout: float = 90, *,
                   prompt: str | None = None) -> None:
        """Wait for a DOS prompt.

        Recognizes either the standard DOS prompt shape, or exactly
        the text in ``prompt`` if the caller supplied one (D113).
        There is no earlier screen here to read a customized prompt's
        text off of, the way :meth:`execute` can (D112), so if the
        guest boots to a customized prompt, this can only recognize
        it when the caller states its exact text — the same thing the
        script language's own ``wait "C:\\>"`` statement does at the
        script level. The match is against the bottom row exactly as
        the guest draws it; a looser pattern match was rejected
        (D112).

        A prompt is not treated as ready the instant it appears
        (D115). The boot screen is the one most likely to still be
        changing — an ``AUTOEXEC.BAT`` with ``ECHO ON`` prints the
        prompt and then the next command on the same row, and
        partway through, that row can briefly look exactly like the
        plain prompt shape. So a prompt sighting is only a candidate
        until the screen under it has stopped changing (see
        :mod:`screen_stability`), the same rule :meth:`execute` uses
        to decide a command is complete. The risk here is smaller —
        nothing gets cut off, a caller just proceeds a little early
        and its first command then reads a screen that is still
        being drawn — but the rule is the same either way, because
        what the caller does next doesn't change whether the screen
        had actually finished.

        Timing out raises :class:`~reliquary.errors.WaitExpired`,
        which is both a ``RunFailure`` and a ``TimeoutError`` (D90,
        D114): the prompt not showing up means the expected thing
        hasn't happened yet, but nothing about the machine is
        necessarily broken, and the boot may still finish — so a
        caller retrying in a loop can just ask again. A prompt that
        was seen but never settled is reported as such, the same way
        :meth:`execute` reports it.
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

        The returned output is whatever the command left on the
        visible screen — the rows between its echo and the prompt
        that came back afterward. Agentless capture has one honest
        limit: a command whose output scrolls past more than one
        screenful only leaves its last screenful behind. Reliquary
        attaches no meaning to any of this text (G2); reading it is
        the caller's job.

        ``check`` answers the one question the returned rows cannot:
        did the command actually work? A setup command's output is
        often nothing at all, and its success is everything, so a
        success and a failure would otherwise look identical. With
        ``check=True``, a command that signalled failure raises
        :class:`RunFailure` naming it; the returned rows are the same
        either way — this adds a separate way to ask about failure,
        it doesn't change what the rows mean.

        A prompt on screen by itself does not mean this particular
        command finished. :meth:`wait_ready` returns as soon as a
        prompt is on screen, so a completion check that only looked
        for a prompt would be satisfied by a prompt that was already
        there before this command ran — and would return whatever was
        above it, which is leftover boot output, not this command's
        output. So this method also needs evidence that this specific
        command actually ran: either its echo on screen, or failing
        that, a screen that has changed since the command was sent.
        """
        rows = self._run(command, timeout)
        if check:
            self._refuse_if_failed(command, timeout)
        return rows

    def _refuse_if_failed(self, command, timeout):
        """Ask the guest whether ``command`` signalled failure.

        This only runs when the caller opts in with ``check=True``,
        and only after the command has already finished, so the
        ordinary path pays nothing for it. The probe itself is just
        one more command typed at the prompt, read back through the
        same echo-matching logic as any other command: its output is
        either the sentinel word, or nothing.

        This check's honest limit is that it only catches commands
        that ran and then signalled failure. `COMMAND.COM` leaves
        ERRORLEVEL untouched when it can't find the program at all,
        so a mistyped command escapes this probe entirely and reads
        as success. Recognizing DOS's own "Bad command or file name"
        message instead would mean hard-coding every wording that
        message can take, which a localized DOS makes an unbounded
        list — exactly the kind of guessing P10 refuses to do. That
        limit is stated here rather than hidden (P11); a mistyped
        command counts as an authoring mistake, caught while
        authoring, not something this check is meant to catch.
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
        """Type one command, wait for the prompt, and return its rows.

        A prompt is never trusted the instant it appears. It can show
        up mid-scroll, or the bottom row can briefly look like a
        prompt while the screen is still being drawn, and acting on
        either would cut the output off at a boundary that was never
        really there — a short, believable, but wrong answer, exactly
        the kind of mistake P11 forbids. So a prompt sighting is only
        a candidate until the screen under it has stopped changing
        (see :mod:`screen_stability`) — the same "read the screen
        twice before trusting it" rule the menu code uses, applied
        here to commands too.
        """
        with self._machine.console() as console:
            before = [row for row in console.screen_text() if row]
            # The prompt the command is typed at. The command's echo
            # appears where this prompt was (D111), and this same
            # prompt coming back is what counts as completion (D112).
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
                # Once the echo has been seen once, it stays counted
                # as seen: a later screen where it's no longer visible
                # just means output has scrolled it off, not that the
                # command never ran. There's no other way to tell
                # those two cases apart.
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
    """Return how long to wait before reading the screen again.

    Once a prompt is on screen (``confirming``), that overrides the
    normal fast-then-slow schedule: the question has changed from
    "has the command finished?" to "has this screen stopped
    changing?", and only that second question needs fast reads.
    """
    if confirming:
        return _SETTLE_POLL
    return _ECHO_POLL if elapsed < _ECHO_WINDOW else _PROMPT_POLL


def _settling_note(reading):
    """Explain why a prompt that was seen never ended the wait.

    Reuses :func:`screen_stability.unsettled_note`'s message, but
    says "prompt" instead of "match", since that's what was actually
    on screen here.
    """
    return screen_stability.unsettled_note(reading).replace(
        "a match was on screen", "a prompt was on screen", 1)


def _screen_width(frame):
    """Return how many cells wide the screen is, read off the
    attribute rows.

    The text rows can't say: they come back right-stripped, so a full
    row and a short row look the same. The attribute rows can tell
    them apart instead, since every backend must return one attribute
    token per cell regardless of row length. A frame with no
    attribute rows has no width to report, and ``0`` says so — with
    no known width, line wrapping can't be detected, and only an echo
    that fits on one row can be found.
    """
    return max((len(row) for row in frame[1]), default=0)


def _is_prompt(row, prompt):
    """Return whether ``row`` is a prompt the wait may treat as
    complete (D112).

    Only two shapes count, nothing wider. The standard DOS prompt
    shape, ``X:\\path>``, is what every unconfigured DOS draws, and
    matching it is what lets a command that changes the prompt's own
    text (like ``CD``) still be recognized as complete. The other
    shape is exactly the prompt the guest was sitting at when the
    command was sent, whatever it looks like — the guest's own screen
    already states what its prompt looks like (D72), so no pattern is
    needed, and this is what makes a guest with a customized prompt
    usable from its very first command. Matching anything wider is
    the false positive P11 refuses to risk — any row merely ending in
    ``>`` would otherwise count as completion.
    """
    return bool(_PROMPT_RE.match(row) or (prompt and row == prompt))


def _prompt_note(prompt):
    """Describe what the expired wait was actually waiting for.

    A command that changes a customized prompt — ``PROMPT`` itself,
    or ``CD`` while a customized prompt is set — returns to a prompt
    text this wait has no record of, so the timeout message needs to
    say so explicitly. Without this note, "the guest never returned
    to the prompt" would send the reader to debug the guest, when the
    command actually ran fine.
    """
    if not prompt:
        return ""
    return (f"; waited for a standard DOS prompt or for {prompt!r}, which "
            "the guest was at — a command that changes the prompt to "
            "another shape returns to text exec has no evidence for")


def _echo_rows(prompt, command, width):
    """Return the rows the guest would draw when ``command`` is typed
    at ``prompt``.

    This is one logical line, ``prompt + command``, broken into rows
    every ``width`` cells and right-stripped row by row, matching how
    the real screen reads back. A row that strips down to nothing is
    dropped, matching how the blank-row filter drops it from the real
    screen. ``width`` of ``0`` means the width is unknown, in which
    case the whole line is treated as a single row.
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
    """Find where the command's echo ends in ``rows``, or return
    ``None`` (D111).

    The echo isn't found by pattern-matching its appearance — it's
    found by where it must be. The command was typed at the prompt
    that ``before`` ends with, so the echo is that same prompt row
    with the command text appended (wrapped across more than one row
    if it's longer than the screen is wide), and it sits exactly
    where the prompt was: the rows above it are the same rows that
    were above the prompt before, minus however many scrolled off the
    top since. Everything the command actually prints appears below
    the echo, so a row that merely happens to contain the same text —
    for example, a file being typed out whose last line matches the
    command that typed it — is never mistaken for the echo, because
    what sits above a genuine echo is the old screen content, not the
    command's own output.

    The search starts at the position where the prompt used to be and
    moves upward, since scrolling is the only thing that can move the
    echo, and it prefers the candidate that needs to explain the
    least scrolling — matching the position closest to where the
    prompt actually was, before trying positions further up. That
    means if the same command text appears on screen more than once
    (running the same command twice, say), this finds the most recent
    echo, not an earlier lookalike. The one case this can't tell
    apart from a real echo is output longer than a full screen, whose
    very first visible row happens to look just like the echo:
    there's nothing left above it on screen to disprove it.

    The row index returned is the echo's *last* row, since the
    command's own output starts on the row right after it. ``width``
    is the screen's cell width; ``0`` means it's unknown, in which
    case only an unwrapped (single-row) echo can be found.
    """
    prompt = before[-1] if before else ""
    echo = _echo_rows(prompt, command, width)
    if not echo:
        return None
    above = before[:-1]
    # Search starts from where the prompt was and moves upward: the
    # echo can only have moved up the screen, through scrolling, and
    # the candidate that requires the least scrolling to explain is
    # the one where every row above it is accounted for.
    for start in range(min(len(above), len(rows) - len(echo)), -1, -1):
        if rows[start:start + len(echo)] != echo:
            continue
        if rows[:start] != above[len(above) - start:]:
            continue
        return start + len(echo) - 1
    return None


def _command_output(rows, before, command, width=0, *, echoed):
    """Return the rows a command produced, between its echo and the
    prompt that came back.

    ``rows`` are the screen's non-blank rows, with the last one being
    the prompt that came back; ``before`` are the non-blank rows of
    the screen the command was typed into, used to locate the echo;
    ``width`` is the screen's cell width, needed to find an echo that
    wrapped across more than one row.

    ``echoed`` records whether the echo was seen at any point during
    the wait, and it's what tells apart the two different reasons the
    echo might be missing from the final screen. If the command
    produced more than a screenful of output — agentless capture's
    documented limit — the echo has simply scrolled off the top, and
    returning the visible tail is the honest answer. If the echo was
    never seen at all, the command's output could not be located, and
    returning the rows above the prompt would hand back someone
    else's text as if it were this command's answer. That case is
    reported as a failure, not returned as a value (P11).
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
