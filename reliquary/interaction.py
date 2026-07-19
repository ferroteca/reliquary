# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Capability interfaces implemented by guest interaction adapters."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class GuestExec(Protocol):
    """Readiness and command-completion capability for a running guest."""

    def wait_ready(self, timeout: float = 90) -> None:
        """Wait until the adapter can execute guest commands."""
        ...

    def execute(self, command: str, timeout: float = 120) -> None:
        """Execute one guest command and wait for completion."""
        ...
