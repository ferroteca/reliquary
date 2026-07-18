# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Generic QEMU guest automation with an agentless DOS workflow.

The package root preserves relict's original import surface. Implementation
is organized by responsibility in the sibling modules.
"""

from .cli import main
from .home import drives_dir, home, set_home
from .lifecycle import Qmp, find_qemu, stop
from .machine import (Machine, screenshot, screen_text, send_keys, send_text,
                      wait_screen)
from .platform_dos import boot_to_dos, download, run_command
from .workflows import (MachineConfig, Runner, run_guest_program, run_task,
                        start)

# Private compatibility names retained for existing diagnostics and tests.
from .home import effective_home as _effective_home
from .lifecycle import (available_port as _available_port,
                        qmp_session as _qmp,
                        read_vm_state as _read_vm_state,
                        remove_vm_state as _remove_vm_state,
                        resolve_vm as _resolve_vm,
                        state_path as _state_path,
                        verify_vm as _verify_vm,
                        write_vm_state as _write_vm_state)
from .machine import char_keys as _char_keys
from .media import (boot_guess as _boot_guess,
                    check_staged_drive as _check_staged_drive,
                    drive_args as _drive_args,
                    format_options as _format_options,
                    scan_drives as _scan_drives,
                    staged_hdd_plan as _staged_hdd_plan)
from .platform_dos import download_boot_image as _download_boot_image


__all__ = [
    "Machine",
    "Qmp",
    "Runner",
    "MachineConfig",
    "boot_to_dos",
    "download",
    "drives_dir",
    "find_qemu",
    "home",
    "main",
    "run_command",
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
