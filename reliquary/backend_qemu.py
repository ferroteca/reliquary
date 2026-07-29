# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The QEMU backend adapter: everything that knows QEMU.

The seam was read off this implementation rather than designed ahead
of one (F2): binary discovery, image creation, configuration
rendering, owned process launch, monitor sessions, identity
verification, input injection, screen capture and readback all live
here, and nothing above the seam names QEMU, qcow2, QMP or a port.

The management interface is QMP — a private tool of this adapter, and
never a control plane (planning/design/guest-communication.md). It
reaches the world only through the named native escape hatch,
``QemuSession.native()``, which is explicitly backend-scoped.
"""

import asyncio
import contextlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import uuid

from PIL import Image
from qemu.qmp import ConnectError, ExecuteError, QMPClient

from . import at_rest, backends, nbd
from .backends import Availability, BackendAdapter, Capabilities
from .errors import (PreflightError, ReliquaryError, RunFailure,
                     StaticError)
from .home import effective_home


_QEMU_BIN = "qemu-system-i386.exe" if os.name == "nt" else "qemu-system-i386"
_QEMU_IMG_BIN = "qemu-img.exe" if os.name == "nt" else "qemu-img"
_QEMU_NBD_BIN = "qemu-nbd.exe" if os.name == "nt" else "qemu-nbd"

_BOOT_LETTER = {"floppy": "a", "hdd": "c", "cdrom": "d"}


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
            f"{binary} not found under {variable}={qemu_home}",
            rule_id="machine.backend-not-found")
    found = shutil.which(binary)
    if found:
        return found
    for directory in _qemu_fallback_dirs():
        candidate = os.path.join(directory, binary)
        if os.path.isfile(candidate):
            return candidate
    raise PreflightError(
        f"{binary} not found: install QEMU, add it to PATH, or set "
        "RELIQUARY_QEMU_HOME to its install directory",
        rule_id="machine.backend-not-found")


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
        raise StaticError("filename must be a non-empty path",
            rule_id="value.not-a-string")
    path = os.path.abspath(filename)
    if not path.lower().endswith(".qcow2"):
        raise StaticError(
            f"hdd image filename must end with .qcow2: {filename}",
            rule_id="image.wrong-extension")
    if isinstance(capacity, bool) or not isinstance(capacity, (int, str)):
        raise StaticError(
            "capacity must be a qemu-img size string or positive "
            "integer MiB value", rule_id="value.not-a-size")
    if isinstance(capacity, int):
        if capacity <= 0:
            raise StaticError(
                "capacity must be a positive integer MiB value",
                rule_id="value.not-a-size")
        size = f"{capacity}M"
    else:
        size = capacity.strip()
        if not size:
            raise StaticError("capacity must be a non-empty size",
                rule_id="value.not-a-size")
    if os.path.exists(path):
        raise PreflightError(f"image already exists: {path}",
            rule_id="image.already-exists")
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
            + (f": {detail}" if detail else ""),
            rule_id="image.creation-failed")
    return path


def _run_qemu_img(args, action, target):
    completed = subprocess.run(
        [find_qemu_img(), *args], capture_output=True, text=True,
        check=False)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RunFailure(
            f"qemu-img failed {action} {target}"
            + (f": {detail}" if detail else ""),
            rule_id="image.operation-failed")
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
            f"difference image filename must end with .qcow2: {filename}",
            rule_id="image.wrong-extension")
    if os.path.exists(path):
        raise PreflightError(f"image already exists: {path}",
            rule_id="image.already-exists")
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
            f"duplicate image filename must end with .qcow2: {filename}",
            rule_id="image.wrong-extension")
    if os.path.exists(path):
        raise PreflightError(f"image already exists: {path}",
            rule_id="image.already-exists")
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


# -- at-rest access -----------------------------------------------
#
# The two shapes a stopped machine's disk is opened in, both
# answering the seam's `open_drive` contract: a device, a commit
# point, and a close that undoes an uncommitted write.

#: The internal snapshot that *is* the commit point for a served
#: image. One fixed name, because a leftover means exactly one thing
#: -- a write that never finished -- and the next access reconciles
#: it the way an interrupted machine operation is reconciled.
_AT_REST_SNAPSHOT = "rlq-at-rest"

#: How long to wait for the server to start listening. Generous
#: because it is a process launch, and bounded because a wait with no
#: end is a hang the user cannot diagnose.
_SERVE_TIMEOUT = 20.0


def find_qemu_nbd():
    """Locate ``qemu-nbd`` from configuration and common paths."""
    return _find_qemu_tool(_QEMU_NBD_BIN)


def _claim(path, *, exclusive):
    """Take the at-rest claim on an image, or refuse by name.

    One place, so the refusal does not depend on which format the
    image turned out to be: a caller meeting a busy disk gets the
    same answer whether it is served or opened directly.
    """
    try:
        return at_rest.ImageLock(path, exclusive=exclusive)
    except at_rest.UnreadableImage as error:
        raise PreflightError(
            f"{path} is in use by another reliquary process — a drive "
            "image is read at rest by one caller at a time",
            rule_id="image.locked") from error


def _reads_as_a_lock(detail):
    """Whether the server's complaint is contention over the image.

    Matched on QEMU's own wording rather than an exit code, which it
    does not distinguish: the lock failure and every other startup
    failure leave the same status behind.
    """
    lowered = detail.lower()
    return "lock" in lowered or "another process" in lowered


def _snapshot_names(path):
    """Every internal snapshot the image carries, by name."""
    completed = _run_qemu_img(
        ["info", "--output=json", path], "probing", path)
    report = json.loads(completed.stdout)
    return {entry.get("name") for entry in report.get("snapshots") or []}


class _ServedAccess:
    """A qcow2 served over NBD and written where it lies.

    The snapshot is the whole of the undo: taken before the first
    byte moves, discarded when the caller commits, and applied when
    it does not. It costs the clusters a write touches rather than
    the size of the disk, which is what makes writing in place
    affordable enough to do at all.
    """

    def __init__(self, path, *, writable=False):
        self.path = path
        self.writable = writable
        self.device = None
        self._server = None
        self._staged = False
        self._lock = None
        try:
            # Taken before the snapshot, and before the server: every
            # step after this assumes nothing else is moving the
            # image, so the claim has to precede the first of them.
            self._lock = _claim(path, exclusive=writable)
            if writable:
                self._reconcile()
                _run_qemu_img(
                    ["snapshot", "-c", _AT_REST_SNAPSHOT, self.path],
                    "snapshotting", self.path)
                self._staged = True
            port = available_port()
            self._server = self._serve(port)
            self.device = self._connect(port)
        except Exception:
            self.close()
            raise

    def _reconcile(self):
        """Undo a write an earlier run never finished.

        The same discipline the machine model uses for an interrupted
        operation: the next one reconciles it rather than refusing
        forever or stepping over it.
        """
        if _AT_REST_SNAPSHOT not in _snapshot_names(self.path):
            return
        _run_qemu_img(["snapshot", "-a", _AT_REST_SNAPSHOT, self.path],
                      "rolling back", self.path)
        _run_qemu_img(["snapshot", "-d", _AT_REST_SNAPSHOT, self.path],
                      "clearing the rollback point of", self.path)

    def _serve(self, port):
        """Start ``qemu-nbd`` on the loopback interface, or say why not.

        ``-t`` keeps it up across connections so a retry does not end
        it; this owns the process and stops it in :meth:`close`. No
        ``--force-share``: QEMU's own image lock is what keeps a
        running machine's disk out of reach, and defeating it is the
        one thing that would make this dangerous.
        """
        command = [find_qemu_nbd(), "-t", "-b", "127.0.0.1",
                   "-p", str(port), "-f", "qcow2"]
        if not self.writable:
            command.append("-r")
        command.append(self.path)
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True)
        deadline = time.monotonic() + _SERVE_TIMEOUT
        while time.monotonic() < deadline:
            if process.poll() is not None:
                detail = self._complaint(process)
                if _reads_as_a_lock(detail):
                    # QEMU's own image lock, which is the thing keeping
                    # a running machine's disk out of reach. Naming it
                    # as contention beats naming it as a server that
                    # would not start.
                    raise PreflightError(
                        f"{self.path} is held by another process — a "
                        "machine using this disk is still running, and "
                        "reliquary reads a drive at rest only when it "
                        "is stopped", rule_id="image.locked")
                raise RunFailure(
                    f"qemu-nbd failed serving {self.path}"
                    + (f": {detail}" if detail else ""),
                    rule_id="image.serve-failed")
            if port_in_use(port):
                return process
            time.sleep(0.02)
        _stop_process(process)
        raise RunFailure(
            f"the image server for {self.path} did not start listening "
            f"within {_SERVE_TIMEOUT:.0f}s", rule_id="image.serve-timeout")

    @staticmethod
    def _complaint(process):
        """Whatever the server said before it gave up."""
        return ((process.stderr.read() if process.stderr else "")
                or "").strip()

    def _connect(self, port):
        """Attach to the export, retrying while the server settles."""
        deadline = time.monotonic() + _SERVE_TIMEOUT
        while True:
            try:
                return nbd.NbdDevice(port=port)
            except ReliquaryError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.05)

    def commit(self):
        """Keep the writes: drop the point they would have been undone
        from."""
        if not self._staged:
            return
        if self.device is not None:
            self.device.flush()
        self._release()
        _run_qemu_img(["snapshot", "-d", _AT_REST_SNAPSHOT, self.path],
                      "committing", self.path)
        self._staged = False

    def close(self):
        """Release everything, undoing a write that never committed."""
        self._release()
        if self._staged:
            self._reconcile()
            self._staged = False
        if self._lock is not None:
            # Last: the rollback above is part of what the lock is
            # held for.
            self._lock.close()
            self._lock = None

    def _release(self):
        """Drop the connection and the server, in that order."""
        if self.device is not None:
            self.device.close()
            self.device = None
        if self._server is not None:
            _stop_process(self._server)
            self._server = None


class _StagedRawAccess:
    """An image already raw: read in place, written through a copy.

    A raw file has nowhere to stand an undo, so the staging D74 built
    is kept for it exactly as it was. Reading still costs nothing —
    the bytes are already what the reader wants, and only a write
    pays for the copy.
    """

    def __init__(self, path, *, writable=False):
        self.path = path
        self.writable = writable
        self.device = None
        self._lock = None
        self._origin = None
        self._workspace = None
        self._scratch = None
        try:
            # The claim comes first here too, and by the same route,
            # so a busy image answers the same whatever its format.
            self._lock = _claim(path, exclusive=writable)
            if not writable:
                self.device = at_rest.LocalDevice(path, lock=False)
                return
            # Copied *under the claim*, so the bytes staged are the
            # bytes nothing else was free to change.
            self._origin = at_rest.LocalDevice(path, writable=True,
                                               lock=False)
            self._workspace = tempfile.mkdtemp(prefix="rlq-at-rest-")
            self._scratch = os.path.join(self._workspace, "raw.img")
            _copy_device(self._origin, self._scratch)
            self.device = at_rest.LocalDevice(self._scratch, writable=True,
                                              lock=False)
        except Exception:
            self.close()
            raise

    def commit(self):
        """Move the staged copy over the image, in one step."""
        if self._scratch is None:
            return
        self.device.flush()
        self.device.close()
        self.device = None
        # Every handle on the image has to go before the move: a held
        # one is a sharing violation on the delivered host, not a
        # safeguard. The claim goes last, so nothing else can take the
        # image between the release and the replace.
        self._origin.close()
        self._origin = None
        self._lock.close()
        self._lock = None
        os.replace(self._scratch, self.path)
        self._scratch = None
        self._cleanup()

    def close(self):
        for held in (self.device, self._origin, self._lock):
            if held is not None:
                held.close()
        self.device = None
        self._origin = None
        self._lock = None
        self._scratch = None
        self._cleanup()

    def _cleanup(self):
        if self._workspace:
            shutil.rmtree(self._workspace, ignore_errors=True)
            self._workspace = None


def _copy_device(device, destination):
    """Lay a device's bytes down as a file, a chunk at a time."""
    chunk = 1 << 20
    with open(destination, "wb") as handle:
        offset = 0
        while offset < device.size:
            block = device.read_at(offset, min(chunk, device.size - offset))
            handle.write(block)
            offset += len(block)


def _stop_process(process):
    """End a child and wait for it, so nothing is left untracked."""
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
    for stream in (process.stdout, process.stderr):
        if stream is not None:
            stream.close()


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


def verify_vm(qmp, port, expected_name, expected_token):
    """Fail closed unless the server is the exact VM instance recorded.

    The name alone cannot identify a VM: same-numbered machines of
    two homes share their readable name, so the per-start token (the
    QEMU ``-uuid``) must match as well before any command may target
    the server.
    """
    reply = qmp.cmd("query-name")
    actual_name = reply.get("name") if isinstance(reply, dict) else None
    if actual_name != expected_name:
        raise PreflightError(
            "QMP identity mismatch; the unrelated VM was not modified\n"
            f"  expected: {expected_name} on 127.0.0.1:{port}\n"
            f"  found:    {actual_name or '<unnamed QMP server>'}",
            rule_id="machine.identity-mismatch")
    reply = qmp.cmd("query-uuid")
    actual_uuid = reply.get("UUID") if isinstance(reply, dict) else None
    if (not isinstance(actual_uuid, str)
            or actual_uuid.casefold() != expected_token.casefold()):
        raise PreflightError(
            "QMP identity mismatch; the unrelated VM was not modified\n"
            f"  expected: {expected_name} ({expected_token}) "
            f"on 127.0.0.1:{port}\n"
            f"  found:    {actual_name} "
            f"({actual_uuid or '<no uuid>'})",
            rule_id="machine.identity-mismatch")


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
    return RunFailure(message, rule_id="machine.backend-failed-to-start")


def _terminate_started_process(proc):
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def _endpoint_port(vm):
    """The recorded QMP port of a QEMU VM record, or fail closed."""
    endpoint = (vm or {}).get("endpoint")
    port = endpoint.get("port") if isinstance(endpoint, dict) else None
    if (not isinstance(port, int) or isinstance(port, bool)
            or not 1 <= port <= 65535):
        raise PreflightError(
            f"the recorded QEMU endpoint is not a usable QMP port: "
            f"{endpoint!r}", rule_id="machine.endpoint-invalid")
    return port


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
    the generic identity record (:func:`backends.identity`) whose
    endpoint is this QEMU's QMP port; the caller persists it,
    atomically with the machine phase.
    """
    automatic_port = port is None
    port = available_port() if automatic_port else port
    if not 1 <= port <= 65535:
        raise StaticError(f"QMP port must be between 1 and 65535: {port}",
            rule_id="value.not-a-port")
    if port_in_use(port):
        selection = "automatically selected" if automatic_port else "explicit"
        raise PreflightError(
            f"QMP port 127.0.0.1:{port} is already in use "
            f"({selection}); choose another port or stop its owner",
            rule_id="machine.port-in-use")
    if current_vm:
        current_port = _endpoint_port(current_vm)
        try:
            with Qmp(current_port) as old_qmp:
                verify_vm(old_qmp, current_port,
                          current_vm["backend-id"], current_vm["token"])
        except (OSError, ConnectError):
            pass  # stale identity; the caller overwrites it
        else:
            raise PreflightError(
                "a reliquary VM is already active\n"
                f"  name: {current_vm['backend-id']}\n"
                f"  QMP port: 127.0.0.1:{current_port}\n"
                "stop it before starting another VM for this machine",
                rule_id="machine.vm-already-active")
    # The readable -name repeats across homes (same-numbered machines
    # of one blueprint); the per-start uuid is the token that makes
    # this exact QEMU instance verifiable.
    token = str(uuid.uuid4())
    command = list(args)
    command += ["-uuid", token]
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
                verify_vm(qmp, port, vm_name, token)
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
    return backends.identity(
        "qemu", vm_name, token, {"port": port}, pid=proc.pid)


def stop(vm):
    """Power off the identified owned VM (no persistence).

    ``vm`` is the recorded identity record. The QMP session is
    identity-verified before ``quit``, so an unrelated VM on the same
    port is never touched. Fails closed on an identity mismatch or an
    unreachable VM; the caller reconciles the machine ``phase`` and
    clears the ``vm`` section.
    """
    if not vm:
        # A machine caught with no recorded VM identity — treat as
        # already gone so the caller reconciles it to a resting phase.
        raise PreflightError("no recorded reliquary VM to stop",
            rule_id="machine.no-active-vm")
    port = _endpoint_port(vm)
    expected_name = vm["backend-id"]
    expected_token = vm["token"]
    try:
        with Qmp(port) as qmp:
            verify_vm(qmp, port, expected_name, expected_token)
            try:
                qmp.cmd("quit")
            except Exception:
                pass
    except (OSError, ConnectError):
        raise PreflightError(
            "the recorded reliquary VM is no longer reachable\n"
            f"  expected: {expected_name} on 127.0.0.1:{port}",
            rule_id="machine.vm-unreachable")
    deadline = time.monotonic() + 15
    while True:
        try:
            Qmp(port).close()
        except (OSError, ConnectError):
            break
        if time.monotonic() > deadline:
            raise RunFailure(
                "QEMU is still holding the QMP port 15s after quit; "
                "a following start() on the same port would collide",
                rule_id="machine.port-not-released")
        time.sleep(0.5)
    print("rlq: VM stopped", file=sys.stderr)


# -- carriers -----------------------------------------------------

def format_options(image):
    """The QEMU ``format=`` option for an image, by extension.

    ``.img`` / ``.iso`` are pinned to ``format=raw`` (avoiding QEMU's
    format-probing warning); any other extension is left for QEMU to
    identify.
    """
    extension = os.path.splitext(image)[1].lower()
    return "format=raw," if extension in (".img", ".iso") else ""


def vga_screen(qmp):
    """Return the 80x25 VGA text screen as (text rows, attribute rows).

    Text rows are right-stripped strings; attribute rows keep the raw
    VGA attribute byte of all 80 cells. Those bytes are the adapter's
    contribution to the seam's text-screen contract: opaque,
    equality-comparable per-cell tokens, promising nothing except
    that equal tokens mean identically rendered cells.
    """
    raw = qmp.hmp("xp /4000bx 0xb8000")
    data = []
    for line in raw.splitlines():
        if not re.match(r"^[0-9a-f]+:", line):
            continue
        data.extend(int(token, 16) for token in line.split()[1:])
    rows = []
    attributes = []
    for row in range(25):
        cells = data[row * 160:(row + 1) * 160]
        rows.append("".join(
            chr(byte) if 32 <= byte < 127 else " "
            for byte in cells[0::2]).rstrip())
        attributes.append(cells[1::2])
    return rows, attributes


class QemuSession:
    """The carriers a running QEMU offers, over one verified session.

    A control plane composes these; it never opens a connection of its
    own and never learns the port behind them.
    """

    backend = "qemu"

    def __init__(self, qmp):
        self._qmp = qmp

    def native(self):
        """The named native escape hatch: this QEMU's QMP session.

        Always explicitly backend-scoped, never generalized — a
        caller reaching for it has left the portable surface
        deliberately.
        """
        return self._qmp

    def send_keys(self, combos, delay=0.06):
        """Inject key combinations, each a list of portable key names.

        The seam's key vocabulary is the portable name set the display
        console speaks; QEMU's qcode names are that set today, so the
        mapping here is the identity — a backend whose input API names
        keys differently translates in its own adapter, never in the
        control plane.
        """
        for combo in combos:
            self._qmp.cmd(
                "send-key",
                keys=[{"type": "qcode", "data": key} for key in combo])
            time.sleep(delay)

    def text_screen(self):
        """The native text readback: (character rows, attribute rows)."""
        return vga_screen(self._qmp)

    def screenshot(self, path):
        """Capture the framebuffer to ``path`` as a PNG.

        QEMU writes PNG directly where its build supports it, and PPM
        otherwise — converted here, so the carrier's product is a PNG
        either way.
        """
        png = os.fspath(path)
        try:
            self._qmp.cmd("screendump", filename=png.replace("\\", "/"),
                          format="png")
            return png
        except ExecuteError:
            pass
        ppm = os.path.splitext(png)[0] + ".ppm"
        self._qmp.cmd("screendump", filename=ppm.replace("\\", "/"))
        time.sleep(0.3)
        try:
            with Image.open(ppm) as image:
                image.save(png)
        except OSError as error:
            raise RunFailure(
                f"unexpected screendump format in {ppm}: {error}",
                rule_id="screen.screendump-unreadable") from error
        os.remove(ppm)
        return png

    def change_medium(self, drive_key, path=None):
        """Swap or eject a removable medium on the running machine.

        The drive is addressed by its launch id, which is the state's
        drive key, so the change the guest sees and the change
        persisted to the state stay one operation.
        """
        if path is None:
            self._qmp.hmp(f"eject {drive_key}")
            return
        target = os.fspath(path).replace("\\", "/")
        extension = os.path.splitext(target)[1].lower()
        fmt = " raw" if extension in (".img", ".iso") else ""
        self._qmp.hmp(f"change {drive_key} {target}{fmt}")


class QemuAdapter(BackendAdapter):
    """QEMU: the delivered backend, and the seam's source."""

    name = "qemu"

    # -- discovery and capability ---------------------------------

    def discover(self):
        try:
            executable = find_qemu()
        except PreflightError as missing:
            return Availability("qemu", False, detail=str(missing))
        return Availability("qemu", True, version=_qemu_version(executable),
                            executable=executable,
                            detail=f"found at {executable}")

    def capabilities(self):
        """What QEMU provides today — built, not merely intended.

        Only ``agentless-display`` is listed because only it is built;
        the VNC, serial-console and guest-agent planes are named in the
        blueprint vocabulary and unbuilt, so claiming them here would
        promise what nothing can honor (P11). The same reading governs
        controllers: the drive renderer wires ``ide`` alone.
        """
        return Capabilities(
            backend="qemu",
            control_planes=("agentless-display",),
            media=("floppy", "hdd", "cdrom"),
            controllers=("ide",),
            materialize=("new", "difference", "copy", "use"),
            vvfat=True,
            at_rest=True,
            at_rest_write=True,
        )

    # -- materialize and dispose ----------------------------------

    def image_path(self, root, stem):
        """QEMU's native per-machine image: qcow2, named for its media."""
        return os.path.join(root, f"{stem}.qcow2")

    def open_drive(self, path, *, writable=False):
        """Open a stopped machine's disk where it lies.

        **A qcow2 is served, not copied.** ``qemu-nbd`` exports it on
        the loopback interface and :class:`reliquary.nbd.NbdDevice`
        addresses it, so a read costs nothing proportional to the
        disk and a write lands in the image itself -- clusters
        allocated, refcounts kept and a backing chain copied on write
        by QEMU, which owns the format and is the only thing that
        should. A differencing image is therefore still a difference
        afterwards without anything here arranging it.

        **An image already raw needs no server**, and is opened
        directly. Its write path keeps the staged copy D74 built,
        because a raw file has nowhere to stand an undo: qcow2's own
        snapshot is what replaces staging, and a format without one
        keeps it.

        **Two formats are claimed and the rest are refused by name.**
        qcow2 is what reliquary materializes and raw is what a
        ``materialize: use`` payload usually is; both are tested on
        the delivered host. QEMU reads plenty more, and serving one
        untested would be claiming a capability nobody exercised —
        which P11 makes a refusal rather than a quiet promise.
        """
        path = os.path.abspath(os.fspath(path))
        found = probe_image_format(path)
        if found == "raw":
            return _StagedRawAccess(path, writable=writable)
        if found != "qcow2":
            raise PreflightError(
                f"{path} is a {found} image, and reliquary reads a "
                "drive at rest in qcow2 or raw form only — convert it, "
                "or exchange files through a directory-source drive",
                rule_id="image.format-not-at-rest")
        return _ServedAccess(path, writable=writable)

    def create_image(self, path, *, mode, size=None, base=None):
        if mode == "new":
            return create_hdd_image(path, size)
        if mode == "difference":
            return create_difference_image(path, base)
        if mode == "copy":
            return create_duplicate_image(path, base)
        raise StaticError(
            f"the qemu adapter cannot materialize an image for "
            f"mode {mode!r}", rule_id="image.mode-unsupported")

    # -- start, stop, liveness ------------------------------------

    def start(self, state, *, machine_dir, backend_dir, display=False,
              current=None):
        """Render the machine's state into a QEMU command line and launch.

        Reliquary drive vocabulary in, QEMU configuration out: memory,
        the drive arguments, and the firmware boot order are all
        rendered here, so no caller ever composes a backend argument.
        """
        memory = state.get("memory") or 16
        vm_name = state.get("backend-id") or f"reliquary-{state['id']}"
        args = [find_qemu(), "-name", vm_name, "-m", str(memory)]
        args += drive_args(state.get("drives", {}))
        boot = _boot_order(state.get("boot", []), state.get("drives", {}))
        if boot is not None:
            args += ["-boot", f"order={boot}"]
        return launch_owned_qemu(
            args, vm_name=vm_name, display=display, current_vm=current,
            log_dir=backend_dir)

    def stop(self, vm):
        return stop(vm)

    @contextlib.contextmanager
    def session(self, vm):
        """Yield an identity-verified session over the recorded VM."""
        port = _endpoint_port(vm)
        name = vm["backend-id"]
        token = vm["token"]
        try:
            with Qmp(port) as qmp:
                verify_vm(qmp, port, name, token)
                yield QemuSession(qmp)
        except (OSError, ConnectError) as error:
            # The recorded VM is gone. The adapter owns no state, so
            # it does not clear it here — the caller (a lifecycle
            # operation, or ``mark_stopped``) reconciles the phase and
            # the ``vm`` section on the next operation.
            raise PreflightError(
                "the recorded reliquary VM is no longer reachable\n"
                f"  expected: {name} on 127.0.0.1:{port}",
                rule_id="machine.vm-unreachable") from error


def _qemu_version(executable):
    """The version string QEMU reports, or ``None`` if it will not say.

    Discovery never fails on this: a binary that cannot be run is a
    version Reliquary does not know, not an unavailable backend — the
    launch itself will report what is actually wrong.
    """
    try:
        completed = subprocess.run(
            [executable, "--version"], capture_output=True, text=True,
            check=False, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    line = (completed.stdout or "").strip().splitlines()
    return line[0] if line else None


def _boot_order(boot_keys, drives):
    letters = []
    for key in boot_keys:
        drive = drives.get(key)
        if drive is None:
            continue
        letter = _BOOT_LETTER.get(drive["medium"])
        if letter is not None and letter not in letters:
            letters.append(letter)
    return "".join(letters) or None


def drive_args(drives):
    """Build QEMU ``-drive`` arguments from a machine's resolved drives.

    Returns a list of tokens for a QEMU command line (``-drive``
    alternating with its value), with floppies first, hard disks next,
    and cdroms placed on the IDE bus after the last hard disk. A drive
    whose realized path is a host directory renders as vvfat — the
    one capability only knowable once resolution has run, so it is
    judged here rather than at assignment.
    """
    args = []

    floppies = [(k, v) for k, v in drives.items()
                if v["medium"] == "floppy"]
    for key, drive in sorted(floppies, key=lambda kv: kv[1]["slot"]):
        path = drive["path"]
        # id=<key> names the drive so a running insert/eject can target
        # it over QMP (the slot key is the launch id).
        if path is None:
            args += ["-drive",
                     f"if=floppy,index={drive['slot']},id={key}"]
            continue
        is_dir = os.path.isdir(path)
        source = (f"fat:floppy:rw:{path},format=raw,"
                  if is_dir else path + ",")
        args += ["-drive",
                 f"file={source}if=floppy,index={drive['slot']},id={key}"]

    hdds = [(k, v) for k, v in drives.items()
            if v["medium"] == "hdd"]
    for _key, drive in sorted(hdds, key=lambda kv: kv[1]["slot"]):
        path = drive["path"]
        is_dir = os.path.isdir(path)
        source = (f"fat:rw:{path},format=raw,"
                  if is_dir else path + ",")
        inferred = "" if is_dir else format_options(path)
        args += ["-drive",
                 f"file={source}{inferred}if=ide,index={drive['slot']}"]

    cdroms = [(k, v) for k, v in drives.items()
              if v["medium"] == "cdrom"]
    if cdroms:
        next_ide = max(
            (d["slot"] for k, d in drives.items() if d["medium"] == "hdd"),
            default=-1,
        ) + 1
        for ordinal, (key, drive) in enumerate(
                sorted(cdroms, key=lambda kv: kv[1]["slot"])):
            path = drive["path"]
            index = next_ide + ordinal
            if path is None:
                args += ["-drive",
                         f"media=cdrom,if=ide,index={index},id={key}"]
                continue
            inferred = format_options(path)
            args += ["-drive",
                     f"file={path},{inferred}media=cdrom,if=ide,"
                     f"index={index},id={key}"]

    return args
