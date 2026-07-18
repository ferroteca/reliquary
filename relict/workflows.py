# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Configured and one-shot QEMU workflow orchestration."""

import collections.abc
import dataclasses
import json
import os
import shutil
import time

from .home import drives_dir, effective_home
from .interaction_agentless import AgentlessGuestExec
from .lifecycle import (normalize_machine, normalize_memory, start_machine,
                        stop)
from .machine import Machine
from .media import (boot_guess, check_staged_drive, drive_key,
                    normalize_drive_specs, resolve_media, staged_hdd_plan)
from .platform_dos import prepare_drives, program_name


_PLATFORM_MEMORY = {
    "dos": 16,
    "win9x": 64,
    "winnt": 256,
}
_CONFIG_FIELDS = frozenset({
    "platform", "staged_drive", "timeout", "memory", "qemu",
    "qemu_args", "drives", "machine",
})


def start(display=False, qemu=None, port=None, qemu_args=(), home=None,
          platform="dos", drives=None, machine=None, memory=None):
    """Start a relict-owned QEMU process and return its QMP port."""
    memory = normalize_memory(memory)
    if memory is not None and any(
            argument == "-m" or str(argument).startswith("-m=")
            for argument in qemu_args):
        raise ValueError(
            "memory configuration conflicts with -m in qemu_args")
    provision = prepare_drives if platform == "dos" else None
    default_memory = _PLATFORM_MEMORY.get(platform.lower())
    return start_machine(
        display, qemu, port, qemu_args, home, provision, default_memory,
        drives, machine, memory)


def run_task(task, timeout=None, display=False, qemu=None, port=None,
             qemu_args=(), home=None, platform="dos", drives=None,
             machine=None, memory=None):
    """Boot one VM, invoke ``task(machine)``, then stop the VM."""
    if not callable(task):
        raise TypeError("task must be callable as task(machine)")
    base = effective_home(home)
    actual_port = start(display, qemu, port, qemu_args, base, platform,
                        drives, machine, memory)
    deadline = (None if timeout is None
                else time.monotonic() + timeout)
    machine = Machine(actual_port, base, deadline)
    try:
        return task(machine)
    finally:
        stop(actual_port, base)


def run_guest_program(exe_path, args="", timeout=180, staged_drive=None,
                      qemu_args=(), qemu=None, port=None, home=None,
                      platform="dos", drives=None, machine=None,
                      memory=None):
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
                 drives=drives, machine=machine, memory=memory)
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


def _resolve_path(path, base_dir):
    path = os.fspath(path)
    if not os.path.isabs(path) and base_dir is not None:
        path = os.path.join(base_dir, path)
    return os.path.abspath(path)


def _drive_parts(declaration, base_dir, key):
    if isinstance(declaration, (str, os.PathLike)):
        return _resolve_path(declaration, base_dir), {}
    if not isinstance(declaration, collections.abc.Mapping):
        raise TypeError(f"drives.{key} must be a path or drive mapping")
    unknown = set(declaration) - {"source", "options"}
    if unknown:
        field = sorted(unknown)[0]
        raise ValueError(f"unknown drive field: drives.{key}.{field}")
    source = declaration.get("source")
    if source is not None:
        if not isinstance(source, (str, os.PathLike)):
            raise TypeError(f"drives.{key}.source must be a path")
        source = _resolve_path(source, base_dir)
    options = declaration.get("options")
    if options is None:
        options = {}
    elif not isinstance(options, collections.abc.Mapping):
        raise TypeError(f"drives.{key}.options must be a mapping")
    else:
        options = dict(options)
    return source, options


def _drive_entries(drives, base_dir):
    if drives is None:
        return {}
    if not isinstance(drives, collections.abc.Mapping):
        raise TypeError("drives must be a mapping")
    entries = {}
    claimed = {}
    for name, declaration in drives.items():
        _, _, key = drive_key(name)
        if key in claimed:
            raise ValueError(
                f"drive key clash: {claimed[key]!r} and {name!r} "
                f"both mean {key}")
        claimed[key] = name
        source, options = _drive_parts(declaration, base_dir, key)
        entries[key] = {"source": source, "options": options}
    return entries


def _merge_drives(base, override, base_dir):
    merged = _drive_entries(base, base_dir)
    for key, declaration in _drive_entries(override, None).items():
        if key not in merged:
            merged[key] = declaration
            continue
        current = merged[key]
        if declaration["source"] is not None:
            current["source"] = declaration["source"]
        current["options"] = {
            **current["options"],
            **declaration["options"],
        }
    return merged


def _mapping_timeout(value):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("timeout must be a number")
    return float(value)


def _mapping_qemu_args(value):
    if isinstance(value, (str, bytes)) or not isinstance(
            value, collections.abc.Sequence):
        raise TypeError("qemu_args must be a sequence of tokens")
    args = tuple(value)
    for index, token in enumerate(args):
        if not isinstance(token, str):
            raise TypeError(
                f"qemu_args[{index}] must be a string")
    return args


@dataclasses.dataclass(frozen=True)
class MachineConfig:
    """Immutable configuration for a :class:`Runner`."""

    platform: "str" = "dos"
    staged_drive: "str | None" = None
    timeout: "float | None" = None
    memory: "int | None" = None
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
        memory = normalize_memory(self.memory)
        if memory is None:
            memory = _PLATFORM_MEMORY.get(self.platform)
        object.__setattr__(self, "memory", memory)
        if isinstance(self.qemu_args, (str, bytes)):
            raise TypeError(
                "qemu_args must be a sequence of tokens, not a string")
        object.__setattr__(self, "qemu_args", tuple(self.qemu_args))
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
        if self.memory is not None and any(
                argument == "-m" or str(argument).startswith("-m=")
                for argument in self.qemu_args):
            raise ValueError(
                "memory configuration conflicts with -m in qemu_args")

    @classmethod
    def from_file(cls, path, **overrides):
        """Load a versioned machine document and apply overrides."""
        path = os.path.abspath(os.fspath(path))
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return cls.from_mapping(
            data, base_dir=os.path.dirname(path), **overrides)

    @classmethod
    def from_mapping(cls, value, base_dir=None, **overrides):
        """Normalize a machine mapping and apply overrides."""
        if not isinstance(value, collections.abc.Mapping):
            raise TypeError("machine configuration must be a mapping")
        unknown = set(value) - _CONFIG_FIELDS - {"version"}
        if unknown:
            raise ValueError(
                f"unknown field: {sorted(unknown)[0]}")
        if "version" not in value:
            raise ValueError("version is required")
        if value["version"] != 1:
            raise ValueError("version must be 1")
        unknown_overrides = set(overrides) - _CONFIG_FIELDS
        if unknown_overrides:
            raise ValueError(
                f"unknown field: {sorted(unknown_overrides)[0]}")

        fields = {}
        if "platform" in value:
            platform = value["platform"]
            if not isinstance(platform, str):
                raise TypeError("platform must be a string")
            fields["platform"] = platform
        if "staged_drive" in value:
            staged = value["staged_drive"]
            if staged is not None and not isinstance(staged, str):
                raise TypeError("staged_drive must be a string")
            fields["staged_drive"] = staged
        if "timeout" in value:
            fields["timeout"] = _mapping_timeout(value["timeout"])
        if "memory" in value:
            fields["memory"] = value["memory"]
        if "qemu" in value:
            qemu = value["qemu"]
            if qemu is not None and not isinstance(qemu, str):
                raise TypeError("qemu must be a string")
            fields["qemu"] = qemu
        if "qemu_args" in value:
            fields["qemu_args"] = _mapping_qemu_args(
                value["qemu_args"])
        if "machine" in value:
            fields["machine"] = value["machine"]
        if "drives" in value or "drives" in overrides:
            fields["drives"] = _merge_drives(
                value.get("drives"), overrides.get("drives"),
                base_dir)

        for name, override in overrides.items():
            if name == "drives":
                continue
            if name == "timeout":
                fields[name] = _mapping_timeout(override)
            elif name == "qemu_args":
                fields[name] = _mapping_qemu_args(override)
            else:
                fields[name] = override
        return cls(**fields)


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
            machine=self.config.machine, memory=self.config.memory)
