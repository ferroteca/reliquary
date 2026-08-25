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

from reliquary import backends
from reliquary.backends import Availability, BackendAdapter, Capabilities


class FakeSession:
    """A session whose carriers record what they were asked for."""

    def __init__(self, adapter, vm, rows=None, attributes=None,
                 image=None):
        self.adapter = adapter
        self.vm = vm
        self.backend = adapter.name
        self.rows = rows if rows is not None else [""] * 25
        self.attributes = (attributes if attributes is not None
                           else [[0x07] * 80 for _ in range(25)])
        self.keys = []
        self.pointer_events = []
        self.screenshots = []
        self.media_changes = []
        #: What this session's framebuffer carrier hands back, where
        #: its plane states a capture format at all (F65).
        self.image = image
        self.grabs = 0

    def native(self):
        return self.adapter.native

    def send_keys(self, combos, delay=0.06):
        self.keys.extend(list(combo) for combo in combos)

    def pointer_event(self, x, y, buttons):
        self.pointer_events.append((x, y, buttons))

    def text_screen(self, font_banks=()):
        return list(self.rows), [list(row) for row in self.attributes]

    def framebuffer(self):
        self.grabs += 1
        if self.image is None:
            raise AssertionError(
                "this double's plane captures no framebuffer")
        return self.image

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
                 image_payload=None, settings_keys=(),
                 capture_planes=None, pointer_planes=None):
        self.name = name
        self.available = available
        self.extension = extension
        #: The ``backend-settings`` vocabulary this double defines. The
        #: seam's own unknown-key refusal is inherited rather than
        #: reimplemented, and no QEMU key is assumed: a test that wants
        #: a section accepted says which keys exist, so what is
        #: asserted here is the machine model calling the seam and not
        #: QEMU's answer.
        self.settings_keys = tuple(settings_keys)
        #: Every section this double was asked to validate, in order.
        self.validated = []
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
            vvfat=True,
            pointing_devices=("tablet", "mouse"),
        )
        self.images = []
        self.starts = []
        self.stops = []
        self.disposed = []
        self.sessions = []
        #: The cache root each session was opened with, so a test can
        #: assert an adapter is told where to keep host-extracted
        #: support files.
        self.session_caches = []
        self.session_rows = None
        #: ``{plane: pixel format}`` for the planes this double
        #: captures a framebuffer on (F65). Empty by default, which
        #: is the seam's own honest default: a plane that states no
        #: format is one a landmark condition is refused on.
        self.capture_planes = dict(capture_planes or {})
        #: ``{plane: bool}`` for the planes this double can deliver a
        #: pointer event on (F66). Empty by default, the seam's own
        #: honest default (`backends.BackendAdapter.pointer_capable`).
        self.pointer_planes = dict(pointer_planes or {})
        #: What a session's framebuffer carrier answers with.
        self.session_image = None
        self.native = object()
        self.start_error = None
        self.stop_error = None
        self.session_error = None
        self.discovered_for = None

    # -- discovery and capability ---------------------------------

    def discover(self, platform=None):
        # The seam offers the machine's platform for a backend whose
        # host tooling differs by guest architecture; this one has a
        # single fake tool and records what it was asked for.
        self.discovered_for = platform
        if not self.available:
            return Availability(self.name, False,
                                detail=f"no {self.name} on this host")
        return Availability(self.name, True, version="fake 1.0",
                            executable=f"/fake/{self.name}/bin",
                            home=f"/fake/{self.name}",
                            detail=f"found at fake-{self.name}")

    def capabilities(self):
        return self.report

    def capture_format(self, plane):
        return self.capture_planes.get(plane)

    def pointer_capable(self, plane):
        return self.pointer_planes.get(plane, False)

    def validate_settings(self, settings):
        self.validated.append(settings)
        return super().validate_settings(settings)

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
    def session(self, vm, cache=None):
        if self.session_error is not None:
            raise self.session_error
        self.session_caches.append(cache)
        open_session = FakeSession(self, vm, rows=self.session_rows,
                                   image=self.session_image)
        self.sessions.append(open_session)
        yield open_session


@contextlib.contextmanager
def installed(adapter=None, name="qemu", **kwargs):
    """Install a fake adapter for the duration of a test."""
    adapter = adapter or FakeAdapter(name, **kwargs)
    previous = backends._set_adapter(name, adapter)
    try:
        yield adapter
    finally:
        backends._set_adapter(name, previous)
