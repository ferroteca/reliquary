# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Configured and one-shot QEMU workflow orchestration."""

import dataclasses
import os
import re
import shutil
import time

from .home import drives_dir, effective_home
from .lifecycle import start_machine, stop
from .machine import Machine
from .media import (boot_guess, check_staged_drive, scan_drives,
                    staged_hdd_plan)
from .platform_dos import (boot_to_dos, download_boot_image,
                           prepare_drives, run_command)
from .lifecycle import qmp_session


def start(display=False, qemu=None, port=None, qemu_args=(), home=None,
          platform="dos"):
    """Start a relict-owned QEMU process and return its QMP port."""
    provision = prepare_drives if platform == "dos" else None
    memory = 16 if platform == "dos" else None
    return start_machine(display, qemu, port, qemu_args, home,
                         provision, memory)


def run_task(task, timeout=None, display=False, qemu=None, port=None,
             qemu_args=(), home=None, platform="dos"):
    """Boot one VM, invoke ``task(machine)``, then stop the VM."""
    if not callable(task):
        raise TypeError("task must be callable as task(machine)")
    base = effective_home(home)
    actual_port = start(display, qemu, port, qemu_args, base, platform)
    deadline = (None if timeout is None
                else time.monotonic() + timeout)
    machine = Machine(actual_port, base, deadline)
    try:
        return task(machine)
    finally:
        stop(actual_port, base)


def run_guest_program(exe_path, args="", timeout=180, staged_drive=None,
                      qemu_args=(), qemu=None, port=None, home=None,
                      platform="dos"):
    """Stage, execute, and collect one agentless DOS program run."""
    if platform != "dos":
        raise ValueError(
            "run_guest_program() is DOS-specific; pass platform='dos'")
    drives = drives_dir(home)
    stage, default_letter = staged_hdd_plan(scan_drives(drives), drives)
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
    exe_name = os.path.basename(exe_path)
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,8}\.[Ee][Xx][Ee]", exe_name):
        raise ValueError(f"guest executable needs a DOS 8.3 name: {exe_name}")
    base = os.path.splitext(exe_name)[0]
    log_name = base + ".log"
    command = f"{base} {args}".strip() + f" > {log_name}"

    os.makedirs(stage, exist_ok=True)
    shutil.copy(exe_path, stage)
    log_path = os.path.join(stage, log_name)
    if os.path.exists(log_path):
        os.remove(log_path)

    port = start(qemu=qemu, port=port, qemu_args=qemu_args, home=home)
    try:
        with qmp_session(port, home) as qmp:
            boot_to_dos(port=qmp)
            run_command(f"{staged_drive.lower()}:", 15, qmp)
            run_command(command, timeout, qmp)
    finally:
        stop(port, home)
    time.sleep(2)

    if not os.path.exists(log_path):
        raise FileNotFoundError(
            f"guest did not write {log_name} (vvfat write-back failed?)")
    with open(log_path, errors="replace") as log_file:
        return log_file.read()


@dataclasses.dataclass(frozen=True)
class RunnerConfig:
    """Immutable configuration for a :class:`Runner`."""

    platform: "str" = "dos"
    boot_floppy_image: "str | None" = None
    boot_hdd_image: "str | None" = None
    staged_drive: "str | None" = None
    timeout: "float | None" = None
    qemu: "str | None" = None
    qemu_args: "tuple" = ()

    def __post_init__(self):
        if not isinstance(self.platform, str) or not self.platform.strip():
            raise ValueError("platform must be a non-empty string")
        object.__setattr__(self, "platform", self.platform.lower())
        if self.platform != "dos" and self.staged_drive is not None:
            raise ValueError(
                "staged_drive is DOS-specific; use platform='dos'")
        if self.boot_floppy_image and self.boot_hdd_image:
            raise ValueError(
                "configure either boot_floppy_image or "
                "boot_hdd_image, not both")
        if self.staged_drive is not None:
            object.__setattr__(self, "staged_drive",
                               check_staged_drive(self.staged_drive))
        if self.boot_hdd_image and self.staged_drive == "C":
            raise ValueError(
                "staged_drive='C': a hard-disk boot image claims C: "
                "as the system drive; the staged vvfat drive "
                "appears at D: or later")


class Runner:
    """A configured QEMU runner with per-run state under an explicit home."""

    def __init__(self, config=None):
        self.config = RunnerConfig() if config is None else config

    @property
    def platform(self):
        return self.config.platform

    def provision(self, drives):
        """Ensure the declared machine has something bootable."""
        if boot_guess(scan_drives(drives)) is not None:
            return
        for image, stem in ((self.config.boot_hdd_image, "hdd"),
                            (self.config.boot_floppy_image, "floppy")):
            if image:
                os.makedirs(drives, exist_ok=True)
                extension = os.path.splitext(image)[1]
                shutil.copy(image, os.path.join(drives, stem + extension))
                return
        if self.platform == "dos":
            download_boot_image(drives)
            return
        raise ValueError(
            "no bootable drive is configured; declare media under "
            f"{drives} or configure a boot image")

    def run(self, task, args="", home=None):
        """Run a DOS executable using this runner's configuration."""
        if home is None:
            raise ValueError("Runner.run() requires an explicit home")
        if self.platform != "dos":
            raise NotImplementedError(
                f"platform {self.platform!r} task workflow is not "
                "implemented; use run_task() with an explicit callable")
        home = os.path.abspath(home)
        drives = os.path.join(home, "drives")
        if boot_guess(scan_drives(drives)) is None:
            self.provision(drives)
        timeout = (180 if self.config.timeout is None
                   else self.config.timeout)
        return run_guest_program(
            task, args, timeout=timeout,
            staged_drive=self.config.staged_drive,
            qemu_args=self.config.qemu_args, qemu=self.config.qemu,
            home=home)
