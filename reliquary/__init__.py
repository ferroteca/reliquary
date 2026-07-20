# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""OS installation scripting over agentless QEMU guest automation."""

from .cli import main
from .home import (blueprints_dir, cache_dir, documents_dir,
                   downloads_cache_dir, drives_dir, home, machines_cache_dir,
                   media_cache_dir, media_dir, scripts_dir, set_home)
from .interaction import GuestExec
from .interaction_agentless import AgentlessGuestExec
from .lifecycle import (Qmp, create_hdd_image, find_qemu, find_qemu_img,
                        stop)
from .machine import (Machine, cursor_menu_select, screen_text,
                      screenshot, send_keys, send_text, wait_text)
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
    "cursor_menu_select",
    "blueprints_dir",
    "cache_dir",
    "documents_dir",
    "downloads_cache_dir",
    "drives_dir",
    "find_qemu",
    "find_qemu_img",
    "home",
    "machines_cache_dir",
    "main",
    "media_cache_dir",
    "media_dir",
    "run_guest_program",
    "run_task",
    "screen_text",
    "screenshot",
    "scripts_dir",
    "send_keys",
    "send_text",
    "set_home",
    "start",
    "stop",
    "wait_text",
]
