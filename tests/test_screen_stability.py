# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The screen-stability primitive: has the guest stopped drawing?"""

import pytest

from reliquary import screen_stability


_ROWS = 25
_COLUMNS = 80
_NORMAL = 0x07
_HIGHLIGHT = 0x1B


class _Screen:
    """A mutable text screen that renders the seam's frame pair.

    Sample sequences are built by writing into one of these and
    taking a `frame()` after each edit, so a test reads as the
    guest's own drawing rather than as two literal grids.
    """

    def __init__(self, rows=_ROWS, columns=_COLUMNS):
        self.columns = columns
        self.text = [[" "] * columns for _ in range(rows)]
        self.attributes = [[_NORMAL] * columns for _ in range(rows)]

    def write(self, row, column, text, attribute=None):
        for offset, character in enumerate(text):
            self.text[row][column + offset] = character
            if attribute is not None:
                self.attributes[row][column + offset] = attribute
        return self

    def highlight(self, row, attribute=_HIGHLIGHT):
        self.attributes[row] = [attribute] * self.columns
        return self

    def frame(self):
        return (["".join(row) for row in self.text],
                [list(row) for row in self.attributes])


def _observe(monitor, frames, start=0.0, cadence=0.1):
    """Feed frames at a fixed cadence; return the last reading."""
    reading = None
    for step, frame in enumerate(frames):
        reading = monitor.observe(frame, now=start + step * cadence)
    return reading


def _border_at(screen, moment):
    """A 76-cell border marching on the wall clock, not the sample.

    Advancing on wall time is what makes this a test of the
    measure rather than of the harness: a denser poll sees the
    same animation, only sampled more often.
    """
    step = int(moment / 0.1)
    pattern = "".join("-" if (column + step) % 2 else "="
                      for column in range(76))
    return screen.write(0, 2, pattern).frame()


# What the measure calls settled.

def test_an_unchanging_screen_is_stable():
    screen = _Screen().write(0, 0, "C:\\>")
    monitor = screen_stability.ScreenStability()

    reading = _observe(monitor, [screen.frame()] * 5)

    assert reading.stable
    assert reading.stability == 1.0


def test_a_line_of_text_arriving_is_not_a_stable_screen():
    # 80 cells of 2000 is 4% of the screen, so any threshold
    # looser than 0.96 would call this settled — it is the event
    # the default exists to refuse
    screen = _Screen()
    frames = [screen.frame()] * 4
    screen.write(12, 0, "Copying FreeDOS system files to C:" + "." * 40)

    reading = _observe(screen_stability.ScreenStability(),
                       frames + [screen.frame()])

    assert not reading.stable
    assert reading.stability < 0.97


@pytest.mark.parametrize("row,column,text", [
    (24, 0, "_"),
    (12, 40, "100%"),
    (24, 70, "12:04:31"),
], ids=["blinking cursor", "percentage counter", "clock"])
def test_screen_furniture_stays_below_the_threshold(row, column, text):
    # the default's job is to sit in the gap between furniture and
    # content, so each item costs an order of magnitude less than
    # the row of text above. One change each, so this is the
    # threshold answering and never the animation mask.
    screen = _Screen()
    frames = [screen.frame()] * 4
    screen.write(row, column, text)

    reading = _observe(screen_stability.ScreenStability(),
                       frames + [screen.frame()])

    assert reading.stable


@pytest.mark.parametrize("changed,expected", [(20, True), (21, False)])
def test_the_threshold_falls_on_a_quarter_of_a_row(changed, expected):
    # 0.99 of 2000 cells is 20 — a quarter row, above every
    # furniture case and below a line of content
    screen = _Screen()
    frames = [screen.frame()] * 4
    screen.write(5, 0, "x" * changed)

    reading = _observe(screen_stability.ScreenStability(),
                       frames + [screen.frame()])

    assert reading.stable is expected


def test_a_highlight_moving_by_attribute_alone_is_a_change():
    # a cursor menu moves its selection by attribute alone, so a
    # text-only comparison would score exactly these frames as
    # perfectly stable
    screen = _Screen().write(2, 0, "First item").write(
        3, 0, "Second item").highlight(2)
    frames = [screen.frame()] * 4
    screen.highlight(2, _NORMAL).highlight(3)

    reading = _observe(screen_stability.ScreenStability(),
                       frames + [screen.frame()])

    assert not reading.stable


def test_a_marching_border_is_decoration_not_movement():
    # "little ants" round a menu churn every border cell at every
    # sample, so raw magnitude never approaches the threshold —
    # yet nothing of consequence is happening, and the region the
    # change occupies is itself perfectly steady
    screen = _Screen().write(10, 20, "Install to harddisk")
    frames = []
    for step in range(12):
        pattern = "".join("-" if (column + step) % 2 else "="
                          for column in range(76))
        frames.append(screen.write(0, 2, pattern).frame())

    reading = _observe(screen_stability.ScreenStability(), frames)

    assert reading.stable
    assert len(reading.animated) == 76


def test_the_verdict_does_not_depend_on_the_poll_rate():
    # stability counted between *consecutive samples* — or
    # decoration counted over the last N samples — is a property
    # of guest x poll rate, not of the guest: a recorded run polls
    # denser than a production one, and the two must not take
    # different paths through the same script
    verdicts = {}
    for cadence in (0.1, 0.05, 0.025):
        screen = _Screen().write(10, 20, "Install to harddisk")
        monitor = screen_stability.ScreenStability()
        reading = None
        for step in range(int(1.6 / cadence)):
            moment = step * cadence
            reading = monitor.observe(_border_at(screen, moment),
                                      now=moment)
        verdicts[cadence] = reading.stable

    assert verdicts == {0.1: True, 0.05: True, 0.025: True}


def test_a_wholly_churning_screen_is_compared_unmasked():
    # masking a screen that is animated nearly everywhere would
    # leave almost nothing to judge and call every frame settled,
    # so the mask is dropped rather than trusted
    frames = []
    for step in range(12):
        screen = _Screen()
        for row in range(_ROWS):
            screen.write(row, 0, chr(65 + (row + step) % 26) * 80)
        frames.append(screen.frame())

    reading = _observe(screen_stability.ScreenStability(), frames)

    assert not reading.stable
    assert reading.animated == frozenset()


def test_a_redraw_below_the_recurrence_bar_stays_content():
    # a cell that changes once is content wherever it sits, and
    # twice is still not decoration: only recurrence earns the mask
    screen = _Screen()
    frames = [screen.frame()] * 3
    for step in range(2):
        frames.append(
            screen.write(12, 0, "Copying file %d" % step + "." * 60).frame())

    reading = _observe(screen_stability.ScreenStability(), frames)

    assert not reading.stable
    assert reading.animated == frozenset()


def test_an_animation_starting_mid_wait_is_absorbed():
    # the menu machinery's learned mask is sampled once, on a
    # screen that had to be quiet first, so decoration that begins
    # later never enters it at all; recurrence needs no learning
    # phase and no quiet moment
    screen = _Screen().write(10, 20, "Install to harddisk")
    monitor = screen_stability.ScreenStability()
    verdicts = []
    for step in range(16):
        moment = step * 0.1
        if step >= 5:
            _border_at(screen, moment)
        verdicts.append(monitor.observe(screen.frame(), now=moment))

    assert verdicts[4].stable
    assert not verdicts[5].stable
    assert verdicts[8].stable
    assert len(verdicts[8].animated) == 76


def test_a_change_exactly_one_window_old_is_outside_it():
    # polling at 0.1s against a 0.2s window puts a change exactly
    # two samples back on the edge every time, so a boundary
    # decided by float noise is not a rare case but the common
    # one: the same settled screen would read either way
    screen = _Screen().write(0, 0, "C:\\>")
    monitor = screen_stability.ScreenStability()
    monitor.observe(screen.frame(), now=0.0)
    screen.write(5, 0, "Loading FreeDOS" + "." * 60)
    reading = None
    for step in range(1, 4):
        reading = monitor.observe(screen.frame(), now=0.1 * step)

    assert reading.stable


def test_a_window_never_observed_cannot_be_judged():
    # quiescence over a span nobody watched is not an answer the
    # measure has: every guarded observation pays one window
    # before its condition is first evaluated
    screen = _Screen().write(0, 0, "C:\\>")
    monitor = screen_stability.ScreenStability()

    reading = _observe(monitor, [screen.frame()] * 2)

    assert not reading.stable
    assert reading.stability is None
    # Young, not blind: two more samples fix this one.
    assert not reading.blind


# Decoration needs samples the caller may not be able to take.
#
# Recurrence is `animation_repeats` changes inside
# `animation_window`, and a change is only recorded at a sample — so
# a caller polling more slowly than that can never accumulate them. A
# screenshot backend costs ~0.83s a read, which is the cadence these
# use.

def _blinking():
    """Frames of a screen whose only motion is a blinking bar."""
    frames = []
    for step in range(10):
        screen = _Screen().write(0, 0, "Do you want to proceed?")
        screen.write(10, 0, "Yes - Continue with the installation")
        if step % 2:
            screen.highlight(10)
        frames.append(screen.frame())
    return frames


def test_the_minimum_viable_cadence_is_stated_not_assumed():
    # repeats samples must fit the window, with the margin's room
    # to spare, so the defaults demand a read every ~0.17s.
    assert screen_stability.viable_cadence() == pytest.approx(1.0 / 6)
    # And the inverse: what a 0.83s reader needs to keep the guard.
    assert screen_stability.viable_window(0.83) == pytest.approx(4.98)


def test_a_dense_poll_keeps_the_default_window():
    monitor = screen_stability.ScreenStability()

    reading = _observe(monitor, _blinking(), cadence=0.1)

    assert monitor.animation_window() == (
        screen_stability.DEFAULT_ANIMATION_WINDOW)
    assert reading.stable
    assert not reading.blind
    assert reading.animated


def test_a_sparse_poll_widens_the_window_and_keeps_the_guard():
    # The same screen at a screenshot backend's cost. Recurrence
    # is measured over the span this caller can observe, so the
    # blink is still recognized as decoration rather than scored
    # as content forever.
    monitor = screen_stability.ScreenStability()

    reading = _observe(monitor, _blinking(), cadence=0.83)

    assert monitor.animation_window() > 4.0
    assert reading.stable
    assert not reading.blind
    assert reading.animated


def test_the_window_never_grows_past_its_cap():
    monitor = screen_stability.ScreenStability()

    _observe(monitor, _blinking(), cadence=3.0)

    assert monitor.animation_window() == (
        screen_stability.MAX_ANIMATION_WINDOW)


def test_a_cadence_past_the_cap_is_answered_as_blind():
    # Widening is tried first; blindness is what is left when even
    # the capped window cannot hold `repeats` samples.
    reading = _observe(screen_stability.ScreenStability(),
                       _blinking(), cadence=3.0)

    assert reading.blind
    assert reading.stability is None


def test_blindness_is_never_claimed_before_a_cadence_is_known():
    # One sample is a young monitor, not a slow caller, and
    # calling it blind would stand the guard down on every run's
    # opening read. Two samples is the whole evidence needed:
    # nothing later can make a hopeless cadence workable.
    monitor = screen_stability.ScreenStability()
    frames = _blinking()

    first = monitor.observe(frames[0], now=0.0)
    assert monitor.cadence() is None
    assert not first.blind

    second = monitor.observe(frames[1], now=3.0)
    assert monitor.cadence() == 3.0
    assert second.blind


def test_an_idle_backoff_is_not_mistaken_for_a_slow_caller():
    """The regression the capability rule exists to prevent.

    The script runtime polls densely while a screen moves and
    backs off to 2s once it settles. Counting samples in the last
    window would read that backoff as blindness and stand the
    guard down exactly when the next redraw arrives.
    """
    screen = _Screen().write(0, 0, "C:\\>")
    monitor = screen_stability.ScreenStability()
    for step in range(5):
        monitor.observe(screen.frame(), now=0.1 * step)

    backed_off = monitor.observe(screen.frame(), now=2.4)

    assert not backed_off.blind
    assert monitor.cadence() == 0.1


def test_a_static_screen_still_settles_at_a_sparse_poll():
    # Blindness is about decoration alone: with nothing moving
    # there is nothing to mask, and the verdict stands.
    screen = _Screen().write(0, 0, "C:\\>")

    reading = _observe(screen_stability.ScreenStability(),
                       [screen.frame()] * 6, cadence=0.83)

    assert reading.stable
    assert reading.stability == 1.0
    assert not reading.blind
