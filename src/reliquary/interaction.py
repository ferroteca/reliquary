# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Capability interfaces implemented by guest interaction adapters."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class GuestExec(Protocol):
    """Readiness and command-completion capability for a running guest."""

    def wait_ready(self, timeout: float = 90, *,
                   prompt: str | None = None) -> None:
        """Wait until the adapter can execute guest commands.

        ``prompt`` is what ready looks like when the platform's
        default evidence cannot say — on agentless DOS, the exact
        text of a customized prompt (D113). An adapter whose
        readiness is reported rather than observed may ignore it.
        """
        ...

    def execute(self, command: str, timeout: float = 120, *,
                check: bool = False) -> None:
        """Execute one guest command and wait for completion.

        ``check`` opts into reporting whether the command signalled
        failure, raising rather than returning the verdict — how a
        platform asks is its own business (DOS probes ERRORLEVEL; an
        agent would read an exit status), and what every adapter owes
        is the same answer.
        """
        ...
