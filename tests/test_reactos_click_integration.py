# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Opt-in `click` proof against ReactOS's real GUI setup wizard (F66).

The `integration` marker is what makes this opt-in: the tier is
deselected unless `pytest --integration` asks for it, and it is never
skipped (`tests/conftest.py`), the same discipline
`test_freedos_vnc_integration.py` runs under.

ReactOS's second-stage Setup Wizard is a genuine Win32 GUI application
— fixed-position Next/Back buttons, not a text-mode menu — which is
exactly the case the whole pointer-input piece exists to reach (U5,
the GUI era). FreeDOS's own install never leaves text mode, so it
cannot exercise `click` at all; this is the real end of that gap.

**Why this test drives its own keyboard, rather than a `.rlqs`
install script driving all of it**: ReactOS's text-mode setup paints
its own font, which the shared recognizer's font-bank library does
not cover the way it covers FreeDOS's (`text_screen()` reads back
noise on this guest, confirmed against a live capture — the raw
pixels are perfect, only the *recognized* text is not). A `wait
"..."` condition there would be a text condition over a screen the
recognizer genuinely cannot read, not a script bug, so the
keyboard-only phase is driven directly over the same raw-pixel
carrier `click`'s own search already reads
(`session.framebuffer()`), with stability judged by
`screen_stability.observe` on those frames — the same measure the
script language's own quiescence gate uses (F65 generalized it to
pixels), and not naive frame equality, **which a blinking text
cursor defeats**: the install-directory screen holds a cursor that
never yields two identical frames, and an equality-based settle
stares at it forever (measured 2026-08-26, 38 minutes without a
press). The codex's own `reactos-install` script stays honestly
thin for the same reason (see its own header comment).

Once the GUI wizard appears, this switches to the real thing: an
actual `.rlqs` script executing `wait @landmark` / `click @landmark
spot="..."`, with both landmarks authored live from the plane's own
captures — exactly as `test_freedos_vnc_integration.py` authors
`dos-prompt` for F65's own proof. Nothing here is a committed binary
fixture.
"""

import json
import os
import time

import pytest

from reliquary import events as _events
from reliquary import screen_stability
from reliquary.errors import PreflightError
from reliquary.backend_qemu import find_qemu, find_qemu_img
from reliquary.home import cache_dir
from reliquary.library import seed_blueprint
from reliquary.machine_handle import Machine
from reliquary.machines import destroy_machine, machine_dir_path, stop_machine
from reliquary.script_runner import run_script
from tests import live_external_effects


pytestmark = pytest.mark.integration

#: The Next/Back button centers on ReactOS 0.4.15's Setup Wizard, at
#: its fixed 800x600 GUI-mode resolution — measured once against a
#: real capture and stable across wizard pages, since every page
#: shares the same dialog chrome.
_NEXT_SPOT = {"x": 498, "y": 470}
_BACK_SPOT = {"x": 403, "y": 470}

#: How many clean-slate install attempts this test budgets before
#: giving up naming the exhausted count. The historical failures
#: divide into two populations, and only one of them is what this
#: budget buys (both measured 2026-08-26). **Systematic**: a fixed
#: press count plus equality-based settling timed out every attempt
#: identically (30 straight, accelerated and not) — that was the
#: driver's own defect, fixed below, and no retry count survives a
#: systematic failure. **Transient**: ReactOS 0.4.15 — "Alpha
#: stage... not feature-complete", per its own setup screen —
#: sometimes takes its VM down outright mid-install, at unpredictable
#: points (observed at 5 and 14 minutes in consecutive cold runs):
#: QEMU exits silently, its stderr empty, and the next session open
#: refuses with `machine.vm-unreachable`. That death is what the
#: retry spends its budget on, which is why the retry loop catches
#: that refusal specifically and not refusals in general.
_INSTALL_ATTEMPTS = 3

#: A frame with at least this many pure-white pixels is the Setup
#: Wizard, not the bare second-stage desktop: the wizard's dialog
#: body is a ~500x390 white sheet (~150k pixels), while the desktop
#: is its wallpaper plus a few thousand white pixels of version
#: text. The distinction matters because the desktop paints first,
#: sits **stable** for the seconds the wizard takes to appear, and a
#: landmark authored from that stable-but-empty frame would aim
#: `click` at wallpaper.
_WIZARD_WHITE_PIXELS = 50_000


def _settled_capture(machine, size=None, timeout=300, poll=0.25,
                     hold=4.0):
    """Poll the live framebuffer until it reads stable.

    Ordinary Python polling over the carrier, not a `.rlqs` wait:
    nothing text-readable survives this guest's own font (see the
    module docstring), and nothing text-readable exists at all once
    the video mode changes to a real GUI framebuffer. Stability is
    `screen_stability.observe` over the pixel frames — the engine's
    own measure, which excludes recurring decoration — because the
    text-mode setup's input screens carry a blinking cursor that
    naive frame equality reads as perpetual motion. The reading must
    hold for ``hold`` seconds before the frame is returned, so a
    freeze mid-transition does not read as a settled screen.
    ``size``, when given, is also a gate — the wrong resolution is a
    screen mid-transition, never a settled one, so stability at the
    wrong size never counts. The poll is deliberately dense: the
    measure recognizes decoration by recurrence, and a sparse poll
    is blind to it (`Reading.blind`).
    """
    deadline = time.monotonic() + timeout
    monitor = screen_stability.ScreenStability()
    last_size = None
    stable_since = None
    while time.monotonic() < deadline:
        with machine.session() as session:
            capture = session.framebuffer()
        if capture.size != last_size:
            monitor = screen_stability.ScreenStability()
            last_size = capture.size
            stable_since = None
        reading = monitor.observe(capture)
        at_size = size is None or capture.size == size
        if at_size and reading.stable:
            if stable_since is None:
                stable_since = time.monotonic()
            if time.monotonic() - stable_since >= hold:
                return capture
        else:
            stable_since = None
        time.sleep(poll)
    raise AssertionError(
        "the screen never settled"
        + (f" at {size}" if size else "") + f" within {timeout}s")


def _press_enter(machine):
    with machine.console() as console:
        console.send_keys([["ret"]])


def _white_pixels(capture):
    return sum(1 for px in capture.convert("RGB").getdata()
               if px == (255, 255, 255))


def _drive_text_mode_setup(machine, timeout=1500):
    """Confirm every settled pre-GUI screen until the wizard appears.

    Every one of ReactOS's text-mode screens already has the wanted
    option highlighted, so the whole phase is press-Enter-on-stable;
    no traversal is needed. **The screen count is deliberately not
    modeled**: the live sequence runs longer than the eight screens
    an earlier version of this function counted (the bootloader
    screens land after the file copy, and the reboot path adds
    more), and the exact order was observed to differ between runs —
    a fixed count is a fencepost that times out every install, which
    is precisely how this function failed before it was measured
    (2026-08-26). The file-copy and reboot screens never read stable
    while they are actually working, so they draw no keypress, and a
    stray Enter on a transiently stable frame is harmless — no
    pre-GUI screen destroys anything on Enter that the flow was not
    already about to do.

    Returns the first frame that is both stable at 800x600 and
    actually shows the wizard (`_WIZARD_WHITE_PIXELS`): the
    second-stage desktop paints first and sits stable while the
    wizard loads, and a landmark authored from the bare desktop
    would aim every later click at wallpaper.
    """
    deadline = time.monotonic() + timeout
    monitor = screen_stability.ScreenStability()
    last_size = None
    stable_since = None
    presses = 0
    while time.monotonic() < deadline:
        with machine.session() as session:
            capture = session.framebuffer()
        if capture.size != last_size:
            monitor = screen_stability.ScreenStability()
            last_size = capture.size
            stable_since = None
        reading = monitor.observe(capture)
        if reading.stable:
            if stable_since is None:
                stable_since = time.monotonic()
            if time.monotonic() - stable_since >= 4.0:
                if capture.size == (800, 600):
                    if _white_pixels(capture) >= _WIZARD_WHITE_PIXELS:
                        return capture
                    # the bare desktop: the wizard is still loading,
                    # so keep watching without pressing anything
                else:
                    _press_enter(machine)
                    presses += 1
                    monitor = screen_stability.ScreenStability()
                stable_since = None
        else:
            stable_since = None
        time.sleep(0.25)
    raise AssertionError(
        f"the Setup Wizard never appeared within {timeout}s "
        f"({presses} screens confirmed)")


def _install_and_reach_wizard(home):
    """Drive one full install attempt per try, retrying from a clean
    machine on a guest-side reset (see `_INSTALL_ATTEMPTS`).

    A fresh machine each attempt rather than nursing the failed one
    along: a reset mid-copy leaves a disk that already has *a*
    partition on it, so resuming in place would silently change what
    each attempt actually exercises from one try to the next.
    """
    last_error = None
    for attempt in range(1, _INSTALL_ATTEMPTS + 1):
        installed = run_script("install", blueprint="reactos", context=home)
        assert installed.machine_phase == "running"
        machine = Machine(machine_dir_path(installed.machine_id, home),
                          cache=cache_dir(home))
        try:
            welcome = _drive_text_mode_setup(machine)
            return installed, machine, welcome
        except (AssertionError, PreflightError) as error:
            # A guest that powers itself off mid-install kills QEMU,
            # and the next session open then refuses with the
            # adapter's `machine.vm-unreachable` — which is the very
            # guest-side death this retry budget exists for, so it
            # retries exactly like a wizard that never appeared. Any
            # other refusal is a real defect and propagates.
            if isinstance(error, PreflightError) \
                    and error.rule_id != "machine.vm-unreachable":
                raise
            last_error = error
            print(f"install attempt {attempt}/{_INSTALL_ATTEMPTS} did not "
                 f"reach the wizard ({error}); resetting to a clean "
                 "machine and retrying")
            stop_machine(installed.machine_id, context=home)
            destroy_machine(installed.machine_id, context=home)
    raise AssertionError(
        "ReactOS never reached the Setup Wizard in "
        f"{_INSTALL_ATTEMPTS} attempts; last failure: {last_error}")


def _write_landmark(home, name, capture, spots, similarity="99%"):
    """Author one landmark from a live screen, as a recorder would.

    A full-screen fuzzy region rather than a bare exact match, for
    the same reason `test_freedos_vnc_integration.py`'s own
    `_write_landmark` uses one: a captured cursor is furniture on a
    screen otherwise painted identically every time, and 99%
    comfortably absorbs one cursor sprite's worth of pixels out of a
    whole 800x600 frame.
    """
    root = os.path.join(home, "landmarks")
    os.makedirs(root, exist_ok=True)
    width, height = capture.size
    document = {
        "screen": {"width": width, "height": height},
        "regions": [{"kind": "fuzzy", "x": 0, "y": 0, "width": width,
                     "height": height, "similarity": similarity}],
        "spots": spots,
    }
    with open(os.path.join(root, f"{name}.rlql"), "w",
              encoding="utf-8") as handle:
        json.dump(document, handle)
    capture.save(os.path.join(root, f"{name}.1.png"))


def _write_script(home, name, source):
    path = os.path.join(home, "scripts", f"{name}.rlqs")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(source)
    return path


def _matched_landmark(run):
    """The last landmark description this run's event stream matched."""
    matches = [event for event in run.events
              if event["kind"] == _events.OBSERVATION_MATCH]
    assert matches, "no landmark match event in the run's stream"
    return matches[-1]["description"]


def test_click_advances_and_returns_through_reactos_setup(integration_home):
    """F66's own done-when: a two-spot landmark, clicking each spot to
    an observable guest effect, on a real GUI installer.

    Both spots of one landmark declaration are exercised in a single
    round trip: `next` (welcome -> acknowledgements, a real page
    change) and `back` (acknowledgements -> welcome again), the
    second click's effect confirmed against the very landmark
    authored before any pointer event was ever delivered — proof
    that the built-in park-zone mask and the fuzzy residual tolerance
    are enough to survive a real, uncontrolled cursor.
    """
    # QEMU is what this tier *is*, so a host without it fails naming
    # the gap (P11) rather than skipping: the tier was asked for.
    find_qemu()
    find_qemu_img()
    home = integration_home

    with live_external_effects():
        seed_blueprint("reactos", context=home)
        installed, machine, welcome = _install_and_reach_wizard(home)

        _write_landmark(home, "reactos-welcome", welcome,
                        spots={"next": _NEXT_SPOT, "back": _BACK_SPOT})

        _write_script(
            home, "click-next",
            "platform winnt\n"
            'wait  @reactos-welcome timeout=15s\n'
            'click @reactos-welcome spot="next"\n')
        advanced = run_script("click-next", machine=installed.machine_id,
                              context=home)
        assert _matched_landmark(advanced) == "@reactos-welcome"

        acknowledgements = _settled_capture(machine, size=(800, 600))
        assert acknowledgements.tobytes() != welcome.tobytes(), (
            "the guest screen did not change after clicking next")
        _write_landmark(home, "reactos-acknowledgements", acknowledgements,
                        spots={"next": _NEXT_SPOT, "back": _BACK_SPOT})

        _write_script(
            home, "click-back",
            "platform winnt\n"
            'wait  @reactos-acknowledgements timeout=15s\n'
            'click @reactos-acknowledgements spot="back"\n')
        returned = run_script("click-back", machine=installed.machine_id,
                              context=home)
        assert _matched_landmark(returned) == "@reactos-acknowledgements"

        # The round trip's own proof: the *original* welcome landmark
        # — authored before either click ever ran — still matches.
        _write_script(
            home, "confirm-welcome",
            "platform winnt\nwait @reactos-welcome timeout=15s\n")
        confirmed = run_script("confirm-welcome",
                               machine=installed.machine_id, context=home)
        assert _matched_landmark(confirmed) == "@reactos-welcome"

        stop_machine(installed.machine_id, context=home)
