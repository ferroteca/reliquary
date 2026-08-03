# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Backend-neutral interaction with and diagnostics for a running machine.

Above the adapter seam: this module names no backend, opens no
connection, and knows no endpoint. A machine is addressed by its
materialization directory, which is where its recorded VM identity
lives; the adapter named in that identity supplies the session, and
the control plane composes the session's carriers.
"""

import contextlib
import dataclasses
import os
import re
import sys
import time

from . import backends
from . import machines as _machines
from .control_display import DisplayConsole
from .errors import PreflightError, RunFailure, StaticError
from .home import effective_home


def validate_screenshot_name(name):
    """Return a filename-only screenshot name that cannot escape home."""
    name = os.fspath(name)
    if (not isinstance(name, str) or not name or name in (".", "..")
            or os.path.basename(name) != name
            or "/" in name or "\\" in name):
        raise StaticError(
            "screenshot name must be a non-empty filename, not a path",
            rule_id="value.not-a-filename")
    return name


def screenshot(name="screen", home=None, directory=None):
    """Save the guest display; `directory` overrides the destination.

    Where the image lands is Reliquary's policy and stays above the
    seam; capturing the framebuffer is the adapter's carrier. The
    session identity always resolves through `home` — a caller
    collecting images somewhere else still verifies the machine it
    talks to.
    """
    return Machine(home).screenshot(name, directory)


@dataclasses.dataclass(frozen=True)
class Machine:
    """A running, reliquary-owned machine passed to generic remote tasks.

    ``home`` is the machine's own materialization directory — an
    already-resolved plain directory, never a :class:`~home.Context`.
    """

    home: "str | None" = None
    deadline: "float | None" = None
    _session_wrapper: "object" = None

    def _identity(self):
        """The recorded VM identity and the adapter that owns it."""
        vm = _machines.read_vm_state(self.home)
        if vm is None:
            raise PreflightError(
                "no active reliquary VM is recorded for this machine; "
                "start it first", rule_id="machine.no-active-vm")
        return backends.adapter(vm["backend"]), vm

    @contextlib.contextmanager
    def session(self):
        """Yield an identity-verified backend session for this machine."""
        adapter, vm = self._identity()
        with adapter.session(vm) as open_session:
            yield open_session

    @contextlib.contextmanager
    def qmp(self):
        """Yield this machine's QMP session — the QEMU escape hatch.

        Explicitly backend-scoped, and never generalized: a machine on
        another backend has no QMP monitor and says so rather than
        offering an approximation of one.
        """
        with self.session() as open_session:
            if open_session.backend != "qemu":
                raise PreflightError(
                    f"this machine runs on {open_session.backend}, which "
                    "has no QMP monitor; the QMP seam is QEMU's alone",
                    rule_id="machine.not-a-qemu-machine")
            yield open_session.native()

    @contextlib.contextmanager
    def console(self):
        """Yield the agentless display console over a fresh session."""
        with self.session() as open_session:
            session = open_session
            if self._session_wrapper is not None:
                session = self._session_wrapper(session)
            yield DisplayConsole(session)

    def screenshot(self, name="screen", directory=None):
        """Capture the guest framebuffer as a PNG, and return its path."""
        name = validate_screenshot_name(name)
        screenshots = directory or os.path.join(
            effective_home(self.home), "screenshots")
        os.makedirs(screenshots, exist_ok=True)
        png = os.path.join(screenshots, f"{name}.png")
        with self.session() as open_session:
            session = open_session
            if self._session_wrapper is not None:
                session = self._session_wrapper(session)
            written = session.screenshot(png)
        print(f"rlq: saved {written}", file=sys.stderr)
        return written

    def send_keys(self, combos, delay=0.06):
        """Send a list of key-name combinations to the guest."""
        with self.console() as console:
            return console.send_keys(combos, delay)

    def send_text(self, text, enter=True):
        """Type text on the guest keyboard, with Enter by default."""
        with self.console() as console:
            return console.send_text(text, enter)

    def cursor_menu_select(self, item, timeout=30, exclude=()):
        """Select a matching item in a cursor-key menu and press ENTER."""
        with self.console() as console:
            return console.cursor_menu_select(item, timeout, exclude)

    def screen_text(self):
        """Return the guest's text screen as character rows."""
        with self.console() as console:
            return console.screen_text()

    def wait_text(self, pattern, timeout=60):
        """Wait until the guest text screen matches a regular expression.

        Returns the matching screen as one newline-joined string.
        """
        with self.console() as console:
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                screen = "\n".join(console.screen_text())
                if re.search(pattern, screen):
                    return screen
                time.sleep(2)
        raise RunFailure(
            f"timed out after {timeout}s waiting for screen to match: "
            f"{pattern}", rule_id="screen.no-match")


def send_keys(combos, delay=0.06, home=None):
    """Send a list of key-name combinations to the guest."""
    return Machine(home).send_keys(combos, delay)


def send_text(text, enter=True, home=None):
    """Type text on the guest keyboard, with Enter by default."""
    return Machine(home).send_text(text, enter)


def cursor_menu_select(item, timeout=30, exclude=(), home=None):
    """Select a matching item in a cursor-key menu and press ENTER."""
    return Machine(home).cursor_menu_select(item, timeout, exclude)


def screen_text(home=None):
    """Return the guest's text screen as character rows."""
    return Machine(home).screen_text()


def wait_text(pattern, timeout=60, home=None):
    """Wait until the guest text screen matches a regular expression."""
    return Machine(home).wait_text(pattern, timeout)
