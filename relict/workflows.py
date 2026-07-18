# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Configured and one-shot QEMU workflow orchestration."""

import dataclasses
import os
import shutil
import time

from .home import drives_dir, effective_home
from .interaction_agentless import AgentlessGuestExec
from .lifecycle import normalize_machine, start_machine, stop
from .machine import Machine
from .media import (boot_guess, check_staged_drive, normalize_drive_specs,
                    resolve_media, staged_hdd_plan)
from .platform_dos import prepare_drives, program_name


def start(display=False, qemu=None, port=None, qemu_args=(), home=None,
          platform="dos", drives=None, machine=None):
    """Start a relict-owned QEMU process and return its QMP port."""
    provision = prepare_drives if platform == "dos" else None
    memory = 16 if platform == "dos" else None
    return start_machine(display, qemu, port, qemu_args, home,
                         provision, memory, drives, machine)


def run_task(task, timeout=None, display=False, qemu=None, port=None,
             qemu_args=(), home=None, platform="dos", drives=None,
             machine=None):
    """Boot one VM, invoke ``task(machine)``, then stop the VM."""
    if not callable(task):
        raise TypeError("task must be callable as task(machine)")
    base = effective_home(home)
    actual_port = start(display, qemu, port, qemu_args, base, platform,
                        drives, machine)
    deadline = (None if timeout is None
                else time.monotonic() + timeout)
    machine = Machine(actual_port, base, deadline)
    try:
        return task(machine)
    finally:
        stop(actual_port, base)


def run_guest_program(exe_path, args="", timeout=180, staged_drive=None,
                      qemu_args=(), qemu=None, port=None, home=None,
                      platform="dos", drives=None, machine=None):
    """Stage, execute, and collect one agentless DOS program run."""
    if platform != "dos":
        raise NotImplementedError(
            f"platform {platform!r} guest-program workflow is not "
            "implemented")
    declared_drives = drives_dir(home)
    media = resolve_media(declared_drives, drives)
    stage, default_letter = staged_hdd_plan(media, declared_drives)
    if staged_drive is None:
        staged_drive = default_letter
    else:
        staged_drive = check_staged_drive(staged_drive)
        if staged_drive < default_letter:
            claimed = ("C:" if default_letter == "D" else
                       f"C: to {chr(ord(default_letter) - 1)}:")
            raise ValueError(
                f"staged_drive={staged_drive!r}: the hard disks "
                f"before the staged drive already claim {claimed}; "
                f"it appears at {default_letter}: or later")
    exe_name = program_name(exe_path)
    base = os.path.splitext(exe_name)[0]
    log_name = base + ".log"
    command = f"{base} {args}".strip() + f" > {log_name}"

    os.makedirs(stage, exist_ok=True)
    shutil.copy(exe_path, stage)
    log_path = os.path.join(stage, log_name)
    if os.path.exists(log_path):
        os.remove(log_path)

    port = start(qemu=qemu, port=port, qemu_args=qemu_args, home=home,
                 drives=drives, machine=machine)
    try:
        guest = AgentlessGuestExec(Machine(port, home))
        guest.wait_ready()
        guest.execute(f"{staged_drive.lower()}:", 15)
        guest.execute(command, timeout)
    finally:
        stop(port, home)
    time.sleep(2)

    if not os.path.exists(log_path):
        raise FileNotFoundError(
            f"guest did not write {log_name} (vvfat write-back failed?)")
    with open(log_path, errors="replace") as log_file:
        return log_file.read()


@dataclasses.dataclass(frozen=True)
class MachineConfig:
    """Immutable configuration for a :class:`Runner`."""

    platform: "str" = "dos"
    staged_drive: "str | None" = None
    timeout: "float | None" = None
    qemu: "str | None" = None
    qemu_args: "tuple" = ()
    drives: "object" = dataclasses.field(default_factory=dict)
    machine: "object" = None

    def __post_init__(self):
        if not isinstance(self.platform, str) or not self.platform.strip():
            raise ValueError("platform must be a non-empty string")
        object.__setattr__(self, "platform", self.platform.lower())
        if self.platform != "dos" and self.staged_drive is not None:
            raise ValueError(
                "staged_drive is DOS-specific; use platform='dos'")
        if self.staged_drive is not None:
            object.__setattr__(self, "staged_drive",
                               check_staged_drive(self.staged_drive))
        object.__setattr__(self, "drives",
                           normalize_drive_specs(self.drives))
        object.__setattr__(self, "machine",
                           normalize_machine(self.machine))
        if self.machine is not None and any(
                argument in ("-machine", "-M") or
                str(argument).startswith(("-machine=", "-M="))
                for argument in self.qemu_args):
            raise ValueError(
                "machine configuration conflicts with -machine "
                "in qemu_args")


class Runner:
    """A configured QEMU runner whose state lives under one home."""

    def __init__(self, home=None, config=None):
        self.home = os.path.abspath(effective_home(home))
        self.config = MachineConfig() if config is None else config

    @property
    def platform(self):
        return self.config.platform

    def _provision(self):
        """Ensure the declared machine has something bootable."""
        drives = os.path.join(self.home, "drives")
        media = resolve_media(drives, self.config.drives)
        if boot_guess(media) is not None:
            return
        if self.platform == "dos":
            prepare_drives(drives, media)
            return
        raise ValueError(
            f"no bootable drive is declared under {drives}")

    def run(self, task, args=""):
        """Run a DOS executable using this runner's configuration."""
        if self.platform != "dos":
            raise NotImplementedError(
                f"platform {self.platform!r} task workflow is not "
                "implemented; use run_task() with an explicit callable")
        self._provision()
        timeout = (180 if self.config.timeout is None
                   else self.config.timeout)
        return run_guest_program(
            task, args, timeout=timeout,
            staged_drive=self.config.staged_drive,
            qemu_args=self.config.qemu_args, qemu=self.config.qemu,
            home=self.home, drives=self.config.drives,
            machine=self.config.machine)
