# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Agentless DOS guest adapter: prompt-based readiness and commands."""

import re
import sys
import time

from .errors import RunFailure
from .machine import Machine


_PROMPT_RE = re.compile(r"^[A-Z]:(\\[^>]*)?>$")

#: How often the screen is read while waiting for a command to finish.
#: The first seconds are polled hard and the rest slowly, because the
#: two waits want opposite things: the echo has to be *caught* before
#: the command's own output can scroll it away, and after that there
#: is nothing to catch, only a prompt to wait out.
_ECHO_POLL = 0.1
_ECHO_WINDOW = 3.0
_PROMPT_POLL = 2.0

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
        """Type one command, wait for the prompt, return its rows."""
        with self._machine.console() as console:
            before = [row for row in console.screen_text() if row]
            console.send_text(command)
            sent = time.monotonic()
            deadline = sent + timeout
            echoed = False
            while time.monotonic() < deadline:
                rows = [row for row in console.screen_text() if row]
                # Sticky: once the echo has been seen, a later screen
                # without it is a scrolled one, not a command that
                # never ran. Nothing else can tell those apart.
                echoed = echoed or _echo_at(rows, command) is not None
                landed = echoed or rows != before
                if landed and rows and _PROMPT_RE.match(rows[-1]):
                    return _command_output(rows, command, echoed=echoed)
                time.sleep(_ECHO_POLL if time.monotonic() - sent < _ECHO_WINDOW
                           else _PROMPT_POLL)
        raise RunFailure(
            f"timed out after {timeout}s waiting for command to finish: "
            f"{command}", rule_id="screen.no-match")


def _echo_at(rows, command):
    """Where the command's echo sits in ``rows``, or ``None``.

    The echo is the last row that both ends with the command and
    carries a prompt before it — the guest repeating back what was
    typed at it.
    """
    needle = command.strip()
    if not needle:
        return None
    for index in range(len(rows) - 1, -1, -1):
        text = rows[index].rstrip()
        if text.endswith(needle) and ">" in text:
            return index
    return None


def _command_output(rows, command, *, echoed):
    """The rows a command produced, between its echo and the prompt.

    ``rows`` are the non-blank screen rows, the last being the prompt
    that came back.

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
    index = _echo_at(rows[:end], command)
    if index is not None:
        return tuple(rows[index + 1:end])
    if echoed:
        return tuple(rows[:end])
    raise RunFailure(
        f"the guest never echoed {command!r}, so what is on screen "
        "cannot be attributed to it — reliquary will not return text "
        "it cannot place", rule_id="screen.no-echo")
