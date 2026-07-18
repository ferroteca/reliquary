# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Ownership-safe QEMU process and QMP lifecycle."""

import asyncio
import collections.abc
import contextlib
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import types
import uuid

from qemu.qmp import ConnectError, QMPClient

from .home import drives_dir, effective_home
from .media import boot_guess, drive_args, resolve_media


_QEMU_BIN = "qemu-system-i386.exe" if os.name == "nt" else "qemu-system-i386"
_VM_STATE_FILE = "vm.json"


def normalize_machine(value):
    """Normalize one QEMU ``-machine`` specification."""
    if value is None:
        return None
    if isinstance(value, str):
        value = {"type": value}
    if not isinstance(value, collections.abc.Mapping):
        raise TypeError("machine must be a string or mapping")
    machine_type = value.get("type")
    if not isinstance(machine_type, str) or not machine_type.strip():
        raise ValueError("machine.type must be a non-empty string")
    normalized = {"type": machine_type}
    for name, option in value.items():
        if name == "type":
            continue
        if not isinstance(name, str) or not name:
            raise ValueError(
                "machine option names must be non-empty strings")
        if not isinstance(option, (str, int, float, bool)):
            raise TypeError(
                f"machine.{name} must be a scalar value")
        normalized[name] = option
    return types.MappingProxyType(normalized)


def machine_argument(value):
    """Render a normalized machine specification for QEMU."""
    machine = normalize_machine(value)
    if machine is None:
        return None
    parts = [machine["type"]]
    for name in sorted(name for name in machine if name != "type"):
        option = machine[name]
        if isinstance(option, bool):
            option = "on" if option else "off"
        parts.append(f"{name}={option}")
    return ",".join(parts)


def _qemu_fallback_dirs():
    if os.name == "nt":
        pf = os.environ.get("ProgramFiles", r"C:\Program Files")
        pf86 = os.environ.get("ProgramFiles(x86)",
                              r"C:\Program Files (x86)")
        scoop = os.environ.get("SCOOP", os.path.expanduser(r"~\scoop"))
        choco = os.environ.get("ChocolateyInstall",
                               r"C:\ProgramData\chocolatey")
        return [
            os.path.join(pf, "qemu"),
            os.path.join(pf86, "qemu"),
            os.path.join(scoop, "apps", "qemu", "current"),
            os.path.join(choco, "bin"),
            r"C:\msys64\ucrt64\bin",
            r"C:\msys64\mingw64\bin",
        ]
    dirs = ["/usr/bin", "/usr/local/bin", "/opt/qemu/bin"]
    if sys.platform == "darwin":
        dirs += ["/opt/homebrew/bin", "/opt/local/bin"]
    return dirs


def find_qemu():
    """Locate the QEMU binary from configuration and common paths."""
    for variable in ("RELICT_QEMU_HOME", "QEMU_HOME"):
        qemu_home = os.environ.get(variable)
        if not qemu_home:
            continue
        for directory in (qemu_home, os.path.join(qemu_home, "bin")):
            candidate = os.path.join(directory, _QEMU_BIN)
            if os.path.isfile(candidate):
                return candidate
        raise FileNotFoundError(
            f"{_QEMU_BIN} not found under {variable}={qemu_home}")
    found = shutil.which(_QEMU_BIN)
    if found:
        return found
    for directory in _qemu_fallback_dirs():
        candidate = os.path.join(directory, _QEMU_BIN)
        if os.path.isfile(candidate):
            return candidate
    raise FileNotFoundError(
        f"{_QEMU_BIN} not found: install QEMU, add it to PATH, or set "
        "RELICT_QEMU_HOME to its install directory")


class Qmp:
    """Synchronous facade over the official asyncio qemu.qmp library."""

    def __init__(self, port):
        self._loop = asyncio.new_event_loop()
        self._client = QMPClient("relict")
        self._loop.run_until_complete(
            self._client.connect(("127.0.0.1", port)))

    def cmd(self, name, **arguments):
        return self._loop.run_until_complete(
            self._client.execute(name, arguments or None))

    def hmp(self, command_line):
        return self.cmd("human-monitor-command",
                        **{"command-line": command_line})

    def close(self):
        try:
            self._loop.run_until_complete(self._client.disconnect())
        except Exception:
            pass
        self._loop.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def state_path(home=None):
    return os.path.join(effective_home(home), _VM_STATE_FILE)


def read_vm_state(home=None):
    path = state_path(home)
    try:
        with open(path, encoding="utf-8") as state_file:
            state = json.load(state_file)
        port = state["port"]
        name = state["name"]
        if (not isinstance(port, int) or isinstance(port, bool)
                or not 1 <= port <= 65535
                or not isinstance(name, str) or not name):
            raise ValueError("invalid port or name")
        return state
    except FileNotFoundError:
        return None
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise RuntimeError(
            f"invalid relict VM state file: {path}: {error}") from error


def write_vm_state(port, name, pid, home=None):
    os.makedirs(effective_home(home), exist_ok=True)
    path = state_path(home)
    part = path + ".part"
    with open(part, "w", encoding="utf-8", newline="\n") as state_file:
        json.dump({"port": port, "name": name, "pid": pid},
                  state_file, indent=2)
        state_file.write("\n")
    os.replace(part, path)


def remove_vm_state(port=None, name=None, home=None):
    state = read_vm_state(home)
    if not state:
        return
    if port is not None and state["port"] != port:
        return
    if name is not None and state["name"] != name:
        return
    try:
        os.remove(state_path(home))
    except FileNotFoundError:
        pass


def resolve_vm(port=None, home=None):
    state = read_vm_state(home)
    if port is None:
        if not state:
            raise RuntimeError(
                "no active relict VM is recorded; run: relict start")
        return state["port"], state["name"]
    if not 1 <= port <= 65535:
        raise ValueError(f"QMP port must be between 1 and 65535: {port}")
    if not state or state["port"] != port:
        raise RuntimeError(
            f"QMP port {port} is not the recorded relict VM; "
            "start it with relict or omit --port to use the active VM")
    return port, state["name"]


def verify_vm(qmp, port, expected_name):
    reply = qmp.cmd("query-name")
    actual_name = reply.get("name") if isinstance(reply, dict) else None
    if actual_name != expected_name:
        raise RuntimeError(
            "QMP identity mismatch; the unrelated VM was not modified\n"
            f"  expected: {expected_name} on 127.0.0.1:{port}\n"
            f"  found:    {actual_name or '<unnamed QMP server>'}")


@contextlib.contextmanager
def qmp_session(port=None, home=None):
    """Yield an identity-verified QMP session."""
    if isinstance(port, Qmp):
        yield port
    else:
        actual_port, expected_name = resolve_vm(port, home)
        try:
            with Qmp(actual_port) as qmp:
                verify_vm(qmp, actual_port, expected_name)
                yield qmp
        except (OSError, ConnectError) as error:
            remove_vm_state(actual_port, expected_name, home)
            raise RuntimeError(
                "the recorded relict VM is no longer reachable\n"
                f"  expected: {expected_name} on "
                f"127.0.0.1:{actual_port}\n"
                "  stale VM state was removed") from error


def available_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def port_in_use(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def _startup_error(proc, stderr_log, port, automatic, detail, args):
    try:
        with open(stderr_log, errors="replace") as stderr_file:
            stderr = stderr_file.read().strip()
    except OSError:
        stderr = ""
    selection = "automatic" if automatic else "explicit"
    message = (f"{detail}\n"
               f"  QMP port: 127.0.0.1:{port} ({selection})\n"
               f"  stderr log: {stderr_log}")
    if proc.returncode is not None:
        message += f"\n  QEMU exit status: {proc.returncode}"
    if stderr:
        message += f"\n  QEMU error: {stderr}"
    message += f"\n  command line: {subprocess.list2cmdline(args)}"
    return RuntimeError(message)


def _terminate_started_process(proc):
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def start_machine(display=False, qemu=None, port=None, qemu_args=(),
                  home=None, prepare_drives=None, default_memory=None,
                  drive_specs=None, machine=None):
    """Start an owned QEMU process after optional drive preparation."""
    automatic_port = port is None
    port = available_port() if automatic_port else port
    if not 1 <= port <= 65535:
        raise ValueError(f"QMP port must be between 1 and 65535: {port}")
    if port_in_use(port):
        selection = "automatically selected" if automatic_port else "explicit"
        raise RuntimeError(
            f"QMP port 127.0.0.1:{port} is already in use "
            f"({selection}); choose another --port or stop its owner")
    old_state = read_vm_state(home)
    if old_state:
        try:
            with Qmp(old_state["port"]) as old_qmp:
                verify_vm(old_qmp, old_state["port"], old_state["name"])
        except (OSError, ConnectError):
            remove_vm_state(old_state["port"], old_state["name"], home)
        else:
            raise RuntimeError(
                "a relict VM is already active\n"
                f"  name: {old_state['name']}\n"
                f"  QMP port: 127.0.0.1:{old_state['port']}\n"
                "stop it before starting another VM in this home")
    qemu = qemu or find_qemu()
    print(f"using QEMU: {qemu}")
    drives = drives_dir(home)
    media = resolve_media(drives, drive_specs)
    if boot_guess(media) is None and prepare_drives is not None:
        prepare_drives(drives, media)
        media = resolve_media(drives, drive_specs)
    vm_name = f"relict-{uuid.uuid4().hex[:12]}"
    qemu_args = list(qemu_args)
    machine_value = machine_argument(machine)
    if machine_value is not None and any(
            argument in ("-machine", "-M") or
            argument.startswith(("-machine=", "-M="))
            for argument in qemu_args):
        raise ValueError(
            "machine configuration conflicts with -machine in qemu_args")
    args = [qemu, "-name", vm_name]
    if machine_value is not None:
        args += ["-machine", machine_value]
    if default_memory is not None and "-m" not in qemu_args:
        args += ["-m", str(default_memory)]
    args += drive_args(media)
    boot = boot_guess(media)
    if boot is not None and "-boot" not in qemu_args:
        args += ["-boot", boot]
    args += ["-qmp", f"tcp:127.0.0.1:{port},server,nowait"]
    if not display:
        args += ["-display", "none"]
    args += qemu_args
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = (subprocess.DETACHED_PROCESS
                                   | subprocess.CREATE_NEW_PROCESS_GROUP)
    base = effective_home(home)
    os.makedirs(base, exist_ok=True)
    stderr_log = os.path.join(base, "qemu-stderr.log")
    with open(stderr_log, "wb") as error_file:
        proc = subprocess.Popen(args, stderr=error_file, **kwargs)
    deadline = time.monotonic() + 15
    while True:
        if proc.poll() is not None:
            raise _startup_error(
                proc, stderr_log, port, automatic_port,
                "QEMU exited during startup", args)
        try:
            with Qmp(port) as qmp:
                verify_vm(qmp, port, vm_name)
            if proc.poll() is not None:
                raise _startup_error(
                    proc, stderr_log, port, automatic_port,
                    "QEMU exited while establishing its QMP connection",
                    args)
            break
        except (OSError, ConnectError):
            if time.monotonic() > deadline:
                _terminate_started_process(proc)
                raise _startup_error(
                    proc, stderr_log, port, automatic_port,
                    "QEMU did not come up; QMP was unreachable after 15s",
                    args)
            time.sleep(0.5)
        except RuntimeError:
            _terminate_started_process(proc)
            raise
    try:
        write_vm_state(port, vm_name, proc.pid, home)
    except OSError as error:
        _terminate_started_process(proc)
        raise RuntimeError(
            "QEMU started but its identity could not be recorded; "
            "the new QEMU process was terminated\n"
            f"  state file: {state_path(home)}\n"
            f"  error: {error}") from error
    print(f"QEMU started: {vm_name} (QMP on 127.0.0.1:{port})")
    return port


def stop(port=None, home=None):
    port, expected_name = resolve_vm(port, home)
    try:
        with Qmp(port) as qmp:
            verify_vm(qmp, port, expected_name)
            try:
                qmp.cmd("quit")
            except Exception:
                pass
    except (OSError, ConnectError):
        remove_vm_state(port, expected_name, home)
        raise RuntimeError(
            "the recorded relict VM is no longer reachable\n"
            f"  expected: {expected_name} on 127.0.0.1:{port}\n"
            "  stale VM state was removed")
    deadline = time.monotonic() + 15
    while True:
        try:
            Qmp(port).close()
        except (OSError, ConnectError):
            break
        if time.monotonic() > deadline:
            raise RuntimeError(
                "QEMU is still holding the QMP port 15s after quit; "
                "a following start() on the same port would collide")
        time.sleep(0.5)
    print("VM stopped.")
    remove_vm_state(port, expected_name, home)
