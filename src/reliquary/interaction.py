# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Capability interfaces implemented by guest interaction adapters."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class GuestExec(Protocol):
    """Readiness and command-completion capability for a running guest."""

    def wait_ready(self, timeout: float = 90, *,
                   prompt: str | None = None) -> None:
        """Wait until the adapter is ready to execute guest commands.

        ``prompt`` tells the adapter what "ready" looks like, for
        cases where the platform's own default check for readiness
        cannot tell — on agentless DOS, this is the exact text of a
        customized command prompt (D113). An adapter that is told
        readiness directly, rather than having to observe it, may
        ignore this argument.
        """
        ...

    def execute(self, command: str, timeout: float = 120, *,
                check: bool = False) -> None:
        """Execute one guest command and wait for it to finish.

        ``check=True`` makes this raise an error if the command
        failed, instead of just returning without saying. How a
        platform actually detects failure is up to it (DOS checks
        ERRORLEVEL, an agent would read an exit status), but every
        adapter must answer this same question the same way.
        """
        ...
