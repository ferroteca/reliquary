# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Generic QEMU guest automation with an agentless DOS workflow."""

from .cli import main
from .home import drives_dir, home, set_home
from .interaction import GuestExec
from .interaction_agentless import (AgentlessGuestExec, screen_text,
                                    send_keys, send_text, wait_screen)
from .lifecycle import (Qmp, create_hdd_image, find_qemu, find_qemu_img,
                        stop)
from .machine import Machine, screenshot
from .workflows import (MachineConfig, Runner, run_guest_program, run_task,
                        start)

__all__ = [
    "Machine",
    "Qmp",
    "Runner",
    "MachineConfig",
    "AgentlessGuestExec",
    "GuestExec",
    "create_hdd_image",
    "drives_dir",
    "find_qemu",
    "find_qemu_img",
    "home",
    "main",
    "run_guest_program",
    "run_task",
    "screen_text",
    "screenshot",
    "send_keys",
    "send_text",
    "set_home",
    "start",
    "stop",
    "wait_screen",
]
