# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Installs ReactOS for real and clicks through its setup wizard, to
prove `click` works against an actual graphical (GUI) installer
(F66).

Like `test_freedos_vnc_integration.py`, this only runs when you pass
`pytest --integration` (see `tests/conftest.py`) — it launches a real
QEMU VM and downloads a real ISO, so it's opt-in, not part of the
normal test run.

Why this matters: ReactOS's second-stage setup is a real Windows GUI
app with Next/Back buttons at fixed positions, not a text menu.
FreeDOS's installer never leaves text mode, so it can never test
`click` at all. This test is the first one that actually does.

Why the first half of this test drives the keyboard itself, instead
of using a `.rlqs` script with `wait` statements: reliquary reads
on-screen text by matching each character's shape against a library
of known fonts. ReactOS's text-mode setup draws a custom font that
isn't in that library, so reliquary reads garbage there — the actual
pixels are fine, reliquary just can't turn them into text. So this
test presses Enter based on the raw screen image settling down
(`screen_stability.observe`, the same stability check the scripting
language itself uses — see F65), not on recognized text. This
matters in practice: naive "did the picture change at all" checks
never work here, because one screen has a blinking cursor that never
looks the same twice, so a naive check would wait forever (this
actually happened during testing: 38 minutes, no progress). The
codex's own `reactos-install` script is deliberately thin for the
same reason — see its header comment.

Once the graphical wizard actually appears, this switches to the
real thing: an actual `.rlqs` script with `wait @landmark` and
`click @landmark spot="..."`, with the landmark images captured live
from the running screen — the same approach
`test_freedos_vnc_integration.py` uses for its own `dos-prompt`
landmark. Nothing here is a checked-in image file.
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

#: Pixel coordinates of the Next and Back buttons on ReactOS 0.4.15's
#: Setup Wizard, at its fixed 800x600 resolution. Measured once from
#: a real screenshot; the same coordinates work on every wizard page
#: because they all share the same button layout.
_NEXT_SPOT = {"x": 498, "y": 470}
_BACK_SPOT = {"x": 403, "y": 470}

#: How many times this test will retry a failed install before
#: giving up. There are two different ways an install can fail, and
#: this retry only helps with one of them (both discovered
#: 2026-08-26 while writing this test).
#:
#: The first way — a bug in this test's own driving code — used to
#: fail every single attempt the same way, so retrying didn't help
#: at all; that bug is fixed now (see `_drive_text_mode_setup`).
#:
#: The second way is real and still happens: ReactOS 0.4.15 calls
#: itself "Alpha stage... not feature-complete" on its own setup
#: screen, and sometimes it crashes its own VM partway through
#: installing, at no predictable point (seen at 5 minutes in one run
#: and 14 minutes in another). When that happens, QEMU just exits
#: with no error message, and the next thing we try to do reports
#: "machine.vm-unreachable". That's the actual failure this retry
#: count is for, which is why the retry logic below only retries on
#: that specific error.
_INSTALL_ATTEMPTS = 3

#: How many pure white pixels a screen needs to count as "the Setup
#: Wizard is showing", rather than just the empty desktop behind it.
#: The wizard's white dialog box covers about 500x390 pixels
#: (~150,000 pixels); the bare desktop only has a few thousand white
#: pixels in its version-number text. This distinction matters
#: because the desktop appears and holds still for a few seconds
#: *before* the wizard window pops up on top of it — if we captured
#: a landmark from the bare desktop, every later click would aim at
#: empty wallpaper instead of a button.
_WIZARD_WHITE_PIXELS = 50_000


def _settled_capture(machine, size=None, timeout=300, poll=0.25,
                     hold=4.0):
    """Take screenshots until the picture stops changing, then return
    the last one.

    This uses plain Python polling, not a `.rlqs` script `wait`,
    because reliquary can't read text off this screen (see the
    module docstring) and once the video mode switches to a real
    graphical framebuffer, there's no text to read at all anyway.

    "Stopped changing" is judged by `screen_stability.observe` —
    the same check reliquary's scripting language uses internally —
    rather than by simple "are these two screenshots identical?"
    equality. That matters because some of these screens have a
    blinking cursor: two screenshots of a truly unchanged screen can
    still differ because the cursor happened to blink between them,
    and a plain equality check would wait forever. `screen_stability`
    knows to ignore that kind of small repeating change.

    Once the screen reads as stable, we keep checking for `hold`
    more seconds before trusting it — otherwise a screen that's
    mid-transition and happens to pause for a moment could be
    mistaken for a finished one. If `size` is given, a screenshot at
    the wrong resolution never counts as stable, since the wrong
    resolution means we're mid-transition. We check often (every
    `poll` seconds) on purpose: this stability check works by
    noticing which pixels repeat, so if we check too rarely, it
    can't tell a blinking cursor from real motion (see
    `Reading.blind`).
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
    """Press Enter on every text-mode setup screen, in order, until
    the graphical Setup Wizard appears. Return the wizard's screenshot.

    ReactOS's text-mode screens always have the right answer already
    highlighted, so all we ever need to do is: wait for the screen
    to stop changing, then press Enter, then repeat.

    We deliberately do NOT count how many screens there are and
    press Enter that many times. An earlier version of this function
    did that — it counted 8 screens by hand and pressed Enter 8
    times — and it was wrong: the real install has more screens than
    that (some bootloader-related screens only show up after the
    file copy finishes), and the exact number varies between runs.
    Counting wrong meant every single install attempt timed out
    waiting for a wizard that this function had already stopped
    trying to reach (found 2026-08-26). Pressing Enter on whatever
    screen is actually showing, instead of counting, fixes that.

    This is safe because the file-copy screen and the reboot screens
    never sit still long enough to count as "stopped changing" while
    they're actually working, so we never press Enter on them by
    mistake. And even if we did press Enter on a screen that
    happened to pause briefly, nothing here is destructive — every
    one of these screens is a "press Enter to continue" prompt.

    We check specifically for the wizard's white dialog box
    (`_WIZARD_WHITE_PIXELS`), not just any 800x600 screen, because
    the empty desktop appears — and sits still — for a few seconds
    *before* the wizard window pops up on top of it. If we grabbed a
    screenshot of the bare desktop instead of waiting for the
    wizard, every click later in the test would aim at empty
    wallpaper instead of a button.
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
                    # This is the bare desktop, not the wizard yet.
                    # Keep watching; don't press anything.
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
    """Try installing ReactOS, up to `_INSTALL_ATTEMPTS` times, until
    it reaches the Setup Wizard. Returns the run, the machine, and
    the wizard's screenshot.

    Each retry starts from a brand-new machine rather than reusing
    the failed one. If we reused it, a disk that already has a
    partition on it (left over from the failed attempt) would make
    each retry start from different disk state than the last one —
    so a fresh machine keeps every attempt comparable.
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
            # If the guest crashes its own VM mid-install (this
            # really happens — see _INSTALL_ATTEMPTS above), QEMU
            # exits, and the next thing we try to do fails with
            # "machine.vm-unreachable". That's the one failure this
            # retry loop exists to handle, so we only retry on it.
            # Any other error is a real bug and should stop the test.
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
    """Save a screenshot as a landmark file reliquary can match
    against later — this is what a human recording a landmark by
    hand would produce.

    We use a "close enough" (fuzzy) match over the whole screen,
    not an exact pixel match, for the same reason
    `test_freedos_vnc_integration.py`'s own `_write_landmark` does:
    the mouse cursor shows up in the screenshot, and it's the only
    thing that moves on an otherwise identical screen. 99% similarity
    is loose enough to ignore one cursor-sized blob of different
    pixels out of the whole 800x600 image.
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
    """Which landmark did the run's last successful match report?"""
    matches = [event for event in run.events
              if event["kind"] == _events.OBSERVATION_MATCH]
    assert matches, "no landmark match event in the run's stream"
    return matches[-1]["description"]


def test_click_advances_and_returns_through_reactos_setup(integration_home):
    """The main proof this test exists for: click one button to move
    forward through a real GUI installer, click another to go back,
    and confirm both clicks actually worked.

    We test both buttons on a single landmark: click "next" (moves
    from the welcome page to the next page — check the screen really
    changed) and click "back" (returns to the welcome page). The
    second check is the important one: we re-match the *original*
    welcome-page landmark, captured before either click ever
    happened, against the screen we're back on now. If that still
    matches, it proves the mouse cursor being visible on screen
    doesn't throw off the match — the landmark system already
    accounts for it.
    """
    # This test needs a real QEMU install on the host. If QEMU isn't
    # found, fail with a clear error rather than silently skipping —
    # someone explicitly asked to run this test tier.
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

        # This is the actual proof of the round trip: the original
        # welcome-page landmark, saved before either click ran,
        # still matches now that we've clicked back to that page.
        _write_script(
            home, "confirm-welcome",
            "platform winnt\nwait @reactos-welcome timeout=15s\n")
        confirmed = run_script("confirm-welcome",
                               machine=installed.machine_id, context=home)
        assert _matched_landmark(confirmed) == "@reactos-welcome"

        stop_machine(installed.machine_id, context=home)
