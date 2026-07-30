# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""A backend adapter double, and the seam that installs it.

Cross-cutting on purpose (the neutral home the tdd rules allow): the
machine model, the CLI and the script runtime all need a machine that
starts and a session that answers, and none of them should need a
hypervisor to be tested. What each of them asserts stays in its own
test module; QEMU's own adapter is exercised in
``test_backend_qemu.py`` against the real rendering and launch code.
"""

import contextlib
import os
import shutil
import tempfile

from reliquary import at_rest, backends
from reliquary.backends import Availability, BackendAdapter, Capabilities


class FakeSession:
    """A session whose carriers record what they were asked for."""

    def __init__(self, adapter, vm, rows=None, attributes=None):
        self.adapter = adapter
        self.vm = vm
        self.backend = adapter.name
        self.rows = rows if rows is not None else [""] * 25
        self.attributes = (attributes if attributes is not None
                           else [[0x07] * 80 for _ in range(25)])
        self.keys = []
        self.screenshots = []
        self.media_changes = []

    def native(self):
        return self.adapter.native

    def send_keys(self, combos, delay=0.06):
        self.keys.extend(list(combo) for combo in combos)

    def text_screen(self):
        return list(self.rows), [list(row) for row in self.attributes]

    def screenshot(self, path):
        self.screenshots.append(path)
        with open(path, "wb") as handle:
            handle.write(b"\x89PNG")
        return path

    def change_medium(self, drive_key, path=None):
        self.media_changes.append((drive_key, path))


class FakeAdapter(BackendAdapter):
    """An adapter that materializes nothing and launches nothing."""

    def __init__(self, name="qemu", *, available=True,
                 capabilities=None, extension=".qcow2",
                 image_payload=None):
        self.name = name
        self.available = available
        self.extension = extension
        #: Bytes to lay down when a per-machine image is created, so a
        #: test can give a machine a disk that really holds a
        #: filesystem. ``None`` keeps the old behaviour: the image is
        #: recorded and no file appears.
        self.image_payload = image_payload
        self.report = capabilities or Capabilities(
            backend=name,
            control_planes=("agentless-display",),
            media=("floppy", "hdd", "cdrom"),
            controllers=("ide",),
            materialize=("new", "difference", "copy", "use"),
            devices=("virtio-rng",),
            vvfat=True,
            at_rest=True,
            at_rest_write=True,
        )
        self.images = []
        self.imported = []
        self.starts = []
        self.stops = []
        self.disposed = []
        self.sessions = []
        self.session_rows = None
        self.native = object()
        self.start_error = None
        self.stop_error = None
        self.session_error = None

    # -- discovery and capability ---------------------------------

    def discover(self):
        if not self.available:
            return Availability(self.name, False,
                                detail=f"no {self.name} on this host")
        return Availability(self.name, True, version="fake 1.0",
                            executable=f"fake-{self.name}",
                            detail=f"found at fake-{self.name}")

    def capabilities(self):
        return self.report

    # -- materialize ----------------------------------------------

    def image_path(self, root, stem):
        return os.path.join(root, f"{stem}{self.extension}")

    def create_image(self, path, *, mode, size=None, base=None):
        self.images.append((path, mode, size, base))
        if self.image_payload is not None:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "wb") as handle:
                handle.write(self.image_payload)
        return path

    def open_drive(self, path, *, writable=False):
        """The fake's images are already raw, so the access is the
        staged one QEMU uses for a raw image -- the same commit point
        and the same undo, without a server in the way."""
        path = os.path.abspath(os.fspath(path))
        return _FakeAccess(self, path, writable=writable)

    def dispose(self, machine_dir):
        self.disposed.append(machine_dir)

    # -- start, stop, session -------------------------------------

    def start(self, state, *, machine_dir, backend_dir, display=False,
              current=None):
        if self.start_error is not None:
            raise self.start_error
        self.starts.append({
            "state": state, "machine_dir": machine_dir,
            "backend_dir": backend_dir, "display": display,
            "current": current,
        })
        return backends.identity(
            self.name, state.get("backend-id") or state["id"],
            "0" * 32, {"handle": len(self.starts)}, pid=1234)

    def stop(self, vm):
        if self.stop_error is not None:
            raise self.stop_error
        self.stops.append(vm)

    @contextlib.contextmanager
    def session(self, vm):
        if self.session_error is not None:
            raise self.session_error
        open_session = FakeSession(self, vm, rows=self.session_rows)
        self.sessions.append(open_session)
        yield open_session


class _FakeAccess:
    """A staged at-rest access over a plain file.

    Written from the seam's contract rather than from QEMU's
    implementation of it, so a machine-model test that only passes
    against QEMU's particular staging is caught here.
    """

    #: The seam's ``backing`` fact: the fake's images are raw files.
    format = "raw"

    def __init__(self, adapter, path, *, writable=False):
        self.adapter = adapter
        self.path = path
        self.writable = writable
        self.device = None
        self._workspace = None
        self._scratch = None
        if not writable:
            self.device = at_rest.LocalDevice(path)
            return
        self._workspace = tempfile.mkdtemp(prefix="fake-at-rest-")
        self._scratch = os.path.join(self._workspace, "raw.img")
        shutil.copyfile(path, self._scratch)
        self.device = at_rest.LocalDevice(self._scratch, writable=True)

    def commit(self):
        if self._scratch is None:
            return
        self.device.flush()
        self.device.close()
        self.device = None
        os.replace(self._scratch, self.path)
        self._scratch = None
        self.adapter.imported.append(self.path)
        self._clean()

    def close(self):
        if self.device is not None:
            self.device.close()
            self.device = None
        self._scratch = None
        self._clean()

    def _clean(self):
        if self._workspace:
            shutil.rmtree(self._workspace, ignore_errors=True)
            self._workspace = None


@contextlib.contextmanager
def installed(adapter=None, name="qemu", **kwargs):
    """Install a fake adapter for the duration of a test."""
    adapter = adapter or FakeAdapter(name, **kwargs)
    previous = backends._set_adapter(name, adapter)
    try:
        yield adapter
    finally:
        backends._set_adapter(name, previous)
