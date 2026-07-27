# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Ownership-safe QEMU process and QMP lifecycle."""

import asyncio
import contextlib
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import uuid

from qemu.qmp import ConnectError, QMPClient

from .errors import (InternalError, PreflightError, ReliquaryError,
                     RunFailure, StaticError)
from .home import effective_home


_QEMU_BIN = "qemu-system-i386.exe" if os.name == "nt" else "qemu-system-i386"
_QEMU_IMG_BIN = "qemu-img.exe" if os.name == "nt" else "qemu-img"
_MACHINE_STATE_FILE = "machine.json"


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


def _find_qemu_tool(binary):
    """Locate a QEMU tool from configuration and common paths."""
    for variable in ("RELIQUARY_QEMU_HOME", "QEMU_HOME"):
        qemu_home = os.environ.get(variable)
        if not qemu_home:
            continue
        for directory in (qemu_home, os.path.join(qemu_home, "bin")):
            candidate = os.path.join(directory, binary)
            if os.path.isfile(candidate):
                return candidate
        raise PreflightError(
            f"{binary} not found under {variable}={qemu_home}")
    found = shutil.which(binary)
    if found:
        return found
    for directory in _qemu_fallback_dirs():
        candidate = os.path.join(directory, binary)
        if os.path.isfile(candidate):
            return candidate
    raise PreflightError(
        f"{binary} not found: install QEMU, add it to PATH, or set "
        "RELIQUARY_QEMU_HOME to its install directory")


def find_qemu():
    """Locate the QEMU system binary from configuration and common paths."""
    return _find_qemu_tool(_QEMU_BIN)


def find_qemu_img():
    """Locate ``qemu-img`` from configuration and common paths."""
    return _find_qemu_tool(_QEMU_IMG_BIN)


def create_hdd_image(filename, capacity):
    """Create a sparse qcow2 v3 hard-disk image at ``filename``.

    ``capacity`` is a qemu-img size string such as ``"512M"`` or ``"2G"``,
    or a positive integer MiB value. The image uses ``compat=1.1``
    (qcow2 v3) with no preallocation. Existing files are not overwritten.
    Returns the absolute path of the created image.
    """
    if not isinstance(filename, str) or not filename.strip():
        raise StaticError("filename must be a non-empty path")
    path = os.path.abspath(filename)
    if not path.lower().endswith(".qcow2"):
        raise StaticError(
            f"hdd image filename must end with .qcow2: {filename}")
    if isinstance(capacity, bool) or not isinstance(capacity, (int, str)):
        raise StaticError(
            "capacity must be a qemu-img size string or positive "
            "integer MiB value")
    if isinstance(capacity, int):
        if capacity <= 0:
            raise StaticError(
                "capacity must be a positive integer MiB value")
        size = f"{capacity}M"
    else:
        size = capacity.strip()
        if not size:
            raise StaticError("capacity must be a non-empty size")
    if os.path.exists(path):
        raise PreflightError(f"image already exists: {path}")
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    qemu_img = find_qemu_img()
    command = [
        qemu_img, "create", "-f", "qcow2",
        "-o", "compat=1.1,preallocation=off",
        path, size,
    ]
    print(f"rlq: creating qcow2 image: {path} ({size})", file=sys.stderr)
    completed = subprocess.run(
        command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RunFailure(
            f"qemu-img failed creating {path}"
            + (f": {detail}" if detail else ""))
    return path


def _run_qemu_img(args, action, target):
    completed = subprocess.run(
        [find_qemu_img(), *args], capture_output=True, text=True,
        check=False)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RunFailure(
            f"qemu-img failed {action} {target}"
            + (f": {detail}" if detail else ""))
    return completed


def probe_image_format(path):
    """Return the qemu-detected format string of an existing image."""
    completed = _run_qemu_img(
        ["info", "--output=json", os.fspath(path)], "probing", path)
    return json.loads(completed.stdout)["format"]


def create_difference_image(filename, base):
    """Create a qcow2 differencing image backed by ``base``.

    Writes land in the difference; the base image stays pristine
    (the drive ``base`` triad's default ``difference`` type). The
    base's format is probed so the backing reference is explicit.
    Existing files are not overwritten. Returns the created path.
    """
    path = os.path.abspath(os.fspath(filename))
    if not path.lower().endswith(".qcow2"):
        raise StaticError(
            f"difference image filename must end with .qcow2: {filename}")
    if os.path.exists(path):
        raise PreflightError(f"image already exists: {path}")
    base = os.path.abspath(os.fspath(base))
    base_format = probe_image_format(base)
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    print(f"rlq: creating qcow2 difference: {path} (backing {base})",
          file=sys.stderr)
    _run_qemu_img(
        ["create", "-f", "qcow2", "-o", "compat=1.1",
         "-b", base, "-F", base_format, path],
        "creating difference", path)
    return path


def create_duplicate_image(filename, base):
    """Materialize a standalone qcow2 copy of ``base``.

    The base is converted in full (``duplicate`` base type), leaving
    the drive independent of any backing file. Existing files are not
    overwritten. Returns the created path.
    """
    path = os.path.abspath(os.fspath(filename))
    if not path.lower().endswith(".qcow2"):
        raise StaticError(
            f"duplicate image filename must end with .qcow2: {filename}")
    if os.path.exists(path):
        raise PreflightError(f"image already exists: {path}")
    base = os.path.abspath(os.fspath(base))
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    print(f"rlq: creating qcow2 duplicate: {path} (from {base})",
          file=sys.stderr)
    _run_qemu_img(
        ["convert", "-O", "qcow2", base, path],
        "duplicating", path)
    return path


class Qmp:
    """Synchronous facade over the official asyncio qemu.qmp library."""

    def __init__(self, port):
        self._loop = asyncio.new_event_loop()
        self._client = QMPClient("reliquary")
        try:
            self._loop.run_until_complete(
                self._client.connect(("127.0.0.1", port)))
        except BaseException:
            self._loop.close()
            raise

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
    """Path to the machine-state file that carries the live-VM section."""
    return os.path.join(effective_home(home), _MACHINE_STATE_FILE)


def read_vm_state(home=None):
    """Return the recorded live-VM identity for a machine, or ``None``.

    The identity lives in the ``vm`` section of the machine's
    ``machine.json`` — written by ``machines.py`` atomically with the
    machine ``phase``. Lifecycle reads it only to verify the QMP
    session it is about to talk to. A state file with no ``vm`` section
    (a stopped machine, or a plain reliquary home) reads as ``None``; a
    malformed section fails closed.
    """
    path = state_path(home)
    try:
        with open(path, encoding="utf-8") as state_file:
            document = json.load(state_file)
    except FileNotFoundError:
        return None
    except (ValueError, json.JSONDecodeError) as error:
        raise InternalError(
            f"invalid reliquary machine state file: {path}: {error}"
        ) from error
    vm = document.get("vm") if isinstance(document, dict) else None
    if vm is None:
        return None
    try:
        port = vm["port"]
        name = vm["name"]
        vm_uuid = vm["uuid"]
    except (KeyError, TypeError) as error:
        raise InternalError(
            f"invalid reliquary VM state in {path}: {error}") from error
    # Checked outside the try: a bare `raise ValueError` caught by the
    # clause above read as a signal rather than an error, and the
    # hierarchy has no room for a deliberate raise that is neither.
    if (not isinstance(port, int) or isinstance(port, bool)
            or not 1 <= port <= 65535
            or not isinstance(name, str) or not name
            or not isinstance(vm_uuid, str) or not vm_uuid):
        raise InternalError(
            f"invalid reliquary VM state in {path}: "
            "invalid port, name, or uuid")
    return vm


def resolve_vm(port=None, home=None):
    state = read_vm_state(home)
    if port is None:
        if not state:
            raise PreflightError(
                "no active reliquary VM is recorded; run: reliquary start")
        return state["port"], state["name"], state["uuid"]
    if not 1 <= port <= 65535:
        raise StaticError(f"QMP port must be between 1 and 65535: {port}")
    if not state or state["port"] != port:
        raise PreflightError(
            f"QMP port {port} is not the recorded reliquary VM; "
            "start it with reliquary or omit --port to use the active VM")
    return port, state["name"], state["uuid"]


def verify_vm(qmp, port, expected_name, expected_uuid):
    """Fail closed unless the server is the exact VM instance recorded.

    The name alone cannot identify a VM: same-numbered machines of
    two homes share their readable name, so the per-start uuid must
    match as well before any command may target the server.
    """
    reply = qmp.cmd("query-name")
    actual_name = reply.get("name") if isinstance(reply, dict) else None
    if actual_name != expected_name:
        raise PreflightError(
            "QMP identity mismatch; the unrelated VM was not modified\n"
            f"  expected: {expected_name} on 127.0.0.1:{port}\n"
            f"  found:    {actual_name or '<unnamed QMP server>'}")
    reply = qmp.cmd("query-uuid")
    actual_uuid = reply.get("UUID") if isinstance(reply, dict) else None
    if (not isinstance(actual_uuid, str)
            or actual_uuid.casefold() != expected_uuid.casefold()):
        raise PreflightError(
            "QMP identity mismatch; the unrelated VM was not modified\n"
            f"  expected: {expected_name} ({expected_uuid}) "
            f"on 127.0.0.1:{port}\n"
            f"  found:    {actual_name} "
            f"({actual_uuid or '<no uuid>'})")


@contextlib.contextmanager
def qmp_session(port=None, home=None):
    """Yield an identity-verified QMP session."""
    if isinstance(port, Qmp):
        yield port
    else:
        actual_port, expected_name, expected_uuid = resolve_vm(port, home)
        try:
            with Qmp(actual_port) as qmp:
                verify_vm(qmp, actual_port, expected_name, expected_uuid)
                yield qmp
        except (OSError, ConnectError) as error:
            # The recorded VM is gone. Lifecycle no longer owns the
            # machine state, so it does not clear it here — the caller
            # (a lifecycle operation, or ``mark_stopped``) reconciles
            # the phase and the ``vm`` section on the next operation.
            raise PreflightError(
                "the recorded reliquary VM is no longer reachable\n"
                f"  expected: {expected_name} on "
                f"127.0.0.1:{actual_port}") from error


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
    return RunFailure(message)


def _terminate_started_process(proc):
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def launch_owned_qemu(args, *, vm_name, display=False, port=None,
                      current_vm=None, log_dir=None):
    """Launch an owned QEMU process and return its verified identity.

    ``args`` is the command line including the QEMU binary and
    ``-name``, but excluding ``-qmp`` / ``-display`` / ``-uuid`` (added
    here). ``current_vm`` is the machine's previously recorded VM
    identity (or ``None``): a still-reachable one refuses the launch so
    a live VM is never orphaned; a stale one is ignored (the caller
    overwrites the recorded identity). ``log_dir`` receives
    ``qemu-stderr.log`` — the machine's backend subdirectory. Returns
    the identity dict ``{port, name, uuid, pid}``; the caller persists
    it, atomically with the machine phase. Lifecycle no longer owns any
    state file.
    """
    automatic_port = port is None
    port = available_port() if automatic_port else port
    if not 1 <= port <= 65535:
        raise StaticError(f"QMP port must be between 1 and 65535: {port}")
    if port_in_use(port):
        selection = "automatically selected" if automatic_port else "explicit"
        raise PreflightError(
            f"QMP port 127.0.0.1:{port} is already in use "
            f"({selection}); choose another --port or stop its owner")
    if current_vm:
        try:
            with Qmp(current_vm["port"]) as old_qmp:
                verify_vm(old_qmp, current_vm["port"],
                          current_vm["name"], current_vm["uuid"])
        except (OSError, ConnectError):
            pass  # stale identity; the caller overwrites it
        else:
            raise PreflightError(
                "a reliquary VM is already active\n"
                f"  name: {current_vm['name']}\n"
                f"  QMP port: 127.0.0.1:{current_vm['port']}\n"
                "stop it before starting another VM for this machine")
    # The readable -name repeats across homes (same-numbered machines
    # of one blueprint); the per-start uuid is what makes this exact
    # QEMU instance verifiable.
    vm_uuid = str(uuid.uuid4())
    command = list(args)
    command += ["-uuid", vm_uuid]
    command += ["-qmp", f"tcp:127.0.0.1:{port},server,nowait"]
    if not display:
        command += ["-display", "none"]
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = (subprocess.DETACHED_PROCESS
                                   | subprocess.CREATE_NEW_PROCESS_GROUP)
    base = effective_home(log_dir)
    os.makedirs(base, exist_ok=True)
    stderr_log = os.path.join(base, "qemu-stderr.log")
    with open(stderr_log, "wb") as error_file:
        proc = subprocess.Popen(command, stderr=error_file, **kwargs)
    deadline = time.monotonic() + 15
    while True:
        if proc.poll() is not None:
            raise _startup_error(
                proc, stderr_log, port, automatic_port,
                "QEMU exited during startup", command)
        try:
            with Qmp(port) as qmp:
                verify_vm(qmp, port, vm_name, vm_uuid)
            if proc.poll() is not None:
                raise _startup_error(
                    proc, stderr_log, port, automatic_port,
                    "QEMU exited while establishing its QMP connection",
                    command)
            break
        except (OSError, ConnectError):
            if time.monotonic() > deadline:
                _terminate_started_process(proc)
                raise _startup_error(
                    proc, stderr_log, port, automatic_port,
                    "QEMU did not come up; QMP was unreachable after 15s",
                    command)
            time.sleep(0.5)
        except ReliquaryError:
            _terminate_started_process(proc)
            raise
    print(f"rlq: QEMU started: {vm_name} (QMP on 127.0.0.1:{port})",
          file=sys.stderr)
    print(f"rlq: command line: {subprocess.list2cmdline(command)}",
          file=sys.stderr)
    return {"port": port, "name": vm_name, "uuid": vm_uuid, "pid": proc.pid}


def stop(vm):
    """Power off the identified owned VM (no persistence).

    ``vm`` is the recorded identity dict ``{port, name, uuid, ...}``.
    The QMP session is identity-verified before ``quit``, so an
    unrelated VM on the same port is never touched. Fails closed on an
    identity mismatch or an unreachable VM; the caller reconciles the
    machine ``phase`` and clears the ``vm`` section.
    """
    if not vm:
        # A machine caught with no recorded VM identity — treat as
        # already gone so the caller reconciles it to a resting phase.
        raise PreflightError("no recorded reliquary VM to stop")
    port = vm["port"]
    expected_name = vm["name"]
    expected_uuid = vm["uuid"]
    try:
        with Qmp(port) as qmp:
            verify_vm(qmp, port, expected_name, expected_uuid)
            try:
                qmp.cmd("quit")
            except Exception:
                pass
    except (OSError, ConnectError):
        raise PreflightError(
            "the recorded reliquary VM is no longer reachable\n"
            f"  expected: {expected_name} on 127.0.0.1:{port}")
    deadline = time.monotonic() + 15
    while True:
        try:
            Qmp(port).close()
        except (OSError, ConnectError):
            break
        if time.monotonic() > deadline:
            raise RunFailure(
                "QEMU is still holding the QMP port 15s after quit; "
                "a following start() on the same port would collide")
        time.sleep(0.5)
    print("rlq: VM stopped", file=sys.stderr)
