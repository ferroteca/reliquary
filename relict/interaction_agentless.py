# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Agentless DOS guest adapter: prompt-based readiness and commands."""

import re
import time

from .machine import Machine, _DisplayConsole


_PROMPT_RE = re.compile(r"^[A-Z]:(\\[^>]*)?>$")


class AgentlessGuestExec:
    """Concrete GuestExec adapter for an agentless DOS guest."""

    def __init__(self, machine: Machine):
        self._machine = machine

    def wait_ready(self, timeout: float = 90) -> None:
        """Wait for a DOS prompt."""
        print("waiting for a DOS prompt...")
        with self._machine.qmp() as qmp:
            console = _DisplayConsole(qmp)
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                rows = [row for row in console.screen_text() if row]
                if rows and _PROMPT_RE.match(rows[-1]):
                    print(f"at DOS prompt: {rows[-1]}")
                    return
                time.sleep(2)
        raise TimeoutError(
            f"timed out after {timeout}s waiting for a DOS prompt")

    def execute(self, command: str, timeout: float = 120) -> None:
        """Type a DOS command and wait for the prompt to return."""
        with self._machine.qmp() as qmp:
            console = _DisplayConsole(qmp)
            console.send_text(command)
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                rows = [row for row in console.screen_text() if row]
                if rows and _PROMPT_RE.match(rows[-1]):
                    return
                time.sleep(2)
        raise TimeoutError(
            f"timed out after {timeout}s waiting for command to finish: "
            f"{command}")
