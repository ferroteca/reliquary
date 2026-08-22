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
from . import screen_stability
from . import text_recognize
# Only the recorded VM identity is wanted here, and it lives in the
# substrate — so this module no longer imports the lifecycle, and the
# two stop importing each other.
from .machine_state import read_vm_state
from .control_display import DisplayConsole, normalize_row
from .errors import PreflightError, StaticError, WaitExpired
from .home import effective_home

#: How often the screen is read while nothing matches, and once a
#: match is on screen and the question is whether it settled — the
#: same two rates the readiness wait uses, for the same reason: a
#: wait is seconds to minutes with nothing to catch along the way,
#: and dense reads are spent only where the verdict needs them.
_MATCH_POLL = 2.0
_SETTLE_POLL = 0.1


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
    ``cache`` is the resolved cache root, on the same terms, and it is
    **not derivable from** ``home``: `machines` is independently
    placeable, so a machine directory says nothing about where the
    cache root sits. A caller that has it passes it; one that does not
    leaves an adapter re-extracting its host support files each time
    rather than keeping them.
    """

    home: "str | None" = None
    deadline: "float | None" = None
    cache: "str | None" = None
    _session_wrapper: "object" = None

    def _identity(self):
        """The recorded VM identity and the adapter that owns it."""
        vm = read_vm_state(self.home)
        if vm is None:
            raise PreflightError(
                "no active reliquary VM is recorded for this machine; "
                "start it first", rule_id="machine.no-active-vm")
        return backends.adapter(vm["backend"]), vm

    @contextlib.contextmanager
    def session(self):
        """Yield an identity-verified backend session for this machine."""
        adapter, vm = self._identity()
        with adapter.session(vm, cache=self.cache) as open_session:
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
        """Return the guest's text screen as character rows.

        Narrates on stderr when part of the screen could not be read.
        A recognized screen is a *measurement*, and one that reports
        no confidence cannot be told from a good one: cells matching
        no known glyph come back as spaces, so a screen drawn in a
        font this host does not have looks merely sparse. The rows
        returned are unchanged — this says how much to trust them.
        """
        with self.console() as console:
            screen = console.screen()
            _narrate_unreadable(screen)
            return screen[0]

    def wait_text(self, pattern, timeout=60):
        """Wait until a row of the guest text screen matches ``pattern``.

        **The screen channel of the script language's `wait` verb, at
        the handle stratum** (D116) — the face `rlq wait` drives, so
        the semantics are the verb's and not a second definition:
        ``pattern`` is a regular expression searched in each visible
        row after normalization (trailing padding trimmed, whitespace
        runs collapsed — script-spec "Normalized text matching"), and
        never across rows; a literal spelling lowers to its escaped,
        normalized text before it reaches here. A match is a candidate
        until the screen under it has settled (D115), as every other
        wait in the system holds its evidence. Returns the matching
        screen as one newline-joined string, as the guest drew it.

        Expiry raises :class:`~reliquary.errors.WaitExpired` — a
        ``RunFailure`` and a ``TimeoutError`` (D90) — saying when a
        match was seen but never settled.
        """
        with self.console() as console:
            deadline = time.monotonic() + timeout
            settling = screen_stability.ScreenStability()
            unsettled = None
            while time.monotonic() < deadline:
                now = time.monotonic()
                frame = console.screen()
                reading = settling.observe(frame, now=now)
                candidate = any(re.search(pattern, normalize_row(row))
                                for row in frame[0])
                if candidate and reading.stable:
                    return "\n".join(frame[0])
                if candidate:
                    unsettled = reading
                time.sleep(_SETTLE_POLL if candidate else _MATCH_POLL)
        raise WaitExpired(
            f"timed out after {timeout}s waiting for screen to match: "
            f"{pattern}{screen_stability.unsettled_note(unsettled)}",
            rule_id="screen.no-match")

    def wait_stopped(self, timeout=60):
        """Wait until this machine's VM is gone.

        **The machine channel of the `wait` verb** — ``machine=stopped``
        — at the handle stratum (D116): how a caller waits out a
        guest-initiated power-off. It *observes* only, exactly as the
        script runtime's sample does: the backend's session refusing
        the recorded identity, or the connection failing, is the
        machine down. Reconciling the machine's phase is the
        lifecycle's act (``Session.mark_stopped``), which the CLI
        performs after this returns, as the runtime does after the
        same observation; this handle knows no lifecycle.

        Expiry raises :class:`~reliquary.errors.WaitExpired` (D90).
        """
        deadline = time.monotonic() + timeout
        while True:
            try:
                with self.console() as console:
                    console.screen()
            except (OSError, ConnectionError):
                return
            except PreflightError as refused:
                if refused.rule_id in ("machine.vm-unreachable",
                                       "machine.no-active-vm"):
                    return
                raise
            now = time.monotonic()
            if now >= deadline:
                raise WaitExpired(
                    f"timed out after {timeout}s waiting for the machine "
                    "to stop: its VM is still answering",
                    rule_id="machine.still-running")
            time.sleep(min(_MATCH_POLL, max(0.0, deadline - now)))


def _narrate_unreadable(screen):
    """Say how much of a screen matched no glyph, when any did not.

    Silent on a clean read, and silent for a backend that scrapes
    resolved characters — it recognizes nothing, so it can
    misrecognize nothing either.
    """
    cells = text_recognize.unreadable_cells(screen)
    if not cells:
        return
    lines = sorted({row for row, _col in cells})
    where = ", ".join(str(line) for line in lines[:6])
    if len(lines) > 6:
        where += ", ..."
    print(f"rlq: {len(cells)} cells on this screen matched no glyph in "
          f"any known font (rows {where}); it may be drawn in a font "
          "this host does not have", file=sys.stderr)


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
