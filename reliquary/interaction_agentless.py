# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Agentless DOS guest adapter: prompt-based readiness and commands."""

import re
import sys
import time

from .errors import RunFailure
from .machine import Machine


_PROMPT_RE = re.compile(r"^[A-Z]:(\\[^>]*)?>$")


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

    def execute(self, command: str, timeout: float = 120):
        """Type a DOS command, wait for the prompt, and return its output.

        The output is what the command left on the visible screen —
        the rows between its echo and the prompt that came back.
        Agentless capture has one honest limit: a command that
        scrolls more than a screenful leaves only its tail there.
        Reliquary attaches no meaning to any of it (G2); the text is
        the caller's to read.
        """
        with self._machine.console() as console:
            console.send_text(command)
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                rows = [row for row in console.screen_text() if row]
                if rows and _PROMPT_RE.match(rows[-1]):
                    return _command_output(rows, command)
                time.sleep(2)
        raise RunFailure(
            f"timed out after {timeout}s waiting for command to finish: "
            f"{command}", rule_id="screen.no-match")


def _command_output(rows, command):
    """The rows a command produced, between its echo and the prompt.

    ``rows`` are the non-blank screen rows, the last being the prompt
    that came back. The echo is the nearest earlier row that both
    ends with the command and carries a prompt before it.
    """
    end = len(rows) - 1
    needle = command.strip()
    for index in range(end - 1, -1, -1):
        text = rows[index].rstrip()
        if needle and text.endswith(needle) and ">" in text:
            return tuple(rows[index + 1:end])
    return tuple(rows[:end])
