# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The screen-stability primitive: has the guest stopped drawing?"""

import unittest

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


class ScreenStabilityTests(unittest.TestCase):
    def test_an_unchanging_screen_is_stable(self):
        screen = _Screen().write(0, 0, "C:\\>")
        monitor = screen_stability.ScreenStability()

        reading = _observe(monitor, [screen.frame()] * 5)

        self.assertTrue(reading.stable)
        self.assertEqual(reading.stability, 1.0)

    def test_a_line_of_text_arriving_is_not_a_stable_screen(self):
        # 80 cells of 2000 is 4% of the screen, so any threshold
        # looser than 0.96 would call this settled — it is the event
        # the default exists to refuse
        screen = _Screen()
        frames = [screen.frame()] * 4
        screen.write(12, 0,
                     "Copying FreeDOS system files to C:" + "." * 40)

        reading = _observe(screen_stability.ScreenStability(),
                           frames + [screen.frame()])

        self.assertFalse(reading.stable)
        self.assertLess(reading.stability, 0.97)

    def test_screen_furniture_stays_below_the_threshold(self):
        # the default's job is to sit in the gap between furniture and
        # content, so each item costs an order of magnitude less than
        # the row of text above. One change each, so this is the
        # threshold answering and never the animation mask.
        furniture = {
            "blinking cursor": (24, 0, "_"),
            "percentage counter": (12, 40, "100%"),
            "clock": (24, 70, "12:04:31"),
        }
        for name, (row, column, text) in furniture.items():
            with self.subTest(furniture=name):
                screen = _Screen()
                frames = [screen.frame()] * 4
                screen.write(row, column, text)

                reading = _observe(screen_stability.ScreenStability(),
                                   frames + [screen.frame()])

                self.assertTrue(reading.stable)

    def test_the_threshold_falls_on_a_quarter_of_a_row(self):
        # 0.99 of 2000 cells is 20 — a quarter row, above every
        # furniture case and below a line of content
        for changed, expected in ((20, True), (21, False)):
            with self.subTest(changed=changed):
                screen = _Screen()
                frames = [screen.frame()] * 4
                screen.write(5, 0, "x" * changed)

                reading = _observe(screen_stability.ScreenStability(),
                                   frames + [screen.frame()])

                self.assertIs(reading.stable, expected)

    def test_a_highlight_moving_by_attribute_alone_is_a_change(self):
        # a cursor menu moves its selection by attribute alone, so a
        # text-only comparison would score exactly these frames as
        # perfectly stable
        screen = _Screen().write(2, 0, "First item").write(
            3, 0, "Second item").highlight(2)
        frames = [screen.frame()] * 4
        screen.highlight(2, _NORMAL).highlight(3)

        reading = _observe(screen_stability.ScreenStability(),
                           frames + [screen.frame()])

        self.assertFalse(reading.stable)

    def test_a_marching_border_is_decoration_not_movement(self):
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

        self.assertTrue(reading.stable)
        self.assertEqual(len(reading.animated), 76)

    def _border_at(self, screen, moment):
        """A 76-cell border marching on the wall clock, not the sample.

        Advancing on wall time is what makes this a test of the
        measure rather than of the harness: a denser poll sees the
        same animation, only sampled more often.
        """
        step = int(moment / 0.1)
        pattern = "".join("-" if (column + step) % 2 else "="
                          for column in range(76))
        return screen.write(0, 2, pattern).frame()

    def test_the_verdict_does_not_depend_on_the_poll_rate(self):
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
                reading = monitor.observe(
                    self._border_at(screen, moment), now=moment)
            verdicts[cadence] = reading.stable

        self.assertEqual(verdicts, {0.1: True, 0.05: True, 0.025: True})

    def test_a_wholly_churning_screen_is_compared_unmasked(self):
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

        self.assertFalse(reading.stable)
        self.assertEqual(reading.animated, frozenset())

    def test_a_redraw_below_the_recurrence_bar_stays_content(self):
        # a cell that changes once is content wherever it sits, and
        # twice is still not decoration: only recurrence earns the mask
        screen = _Screen()
        frames = [screen.frame()] * 3
        for step in range(2):
            frames.append(
                screen.write(12, 0, "Copying file %d" % step
                             + "." * 60).frame())

        reading = _observe(screen_stability.ScreenStability(), frames)

        self.assertFalse(reading.stable)
        self.assertEqual(reading.animated, frozenset())

    def test_an_animation_starting_mid_wait_is_absorbed(self):
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
                self._border_at(screen, moment)
            verdicts.append(monitor.observe(screen.frame(), now=moment))

        self.assertTrue(verdicts[4].stable)
        self.assertFalse(verdicts[5].stable)
        self.assertTrue(verdicts[8].stable)
        self.assertEqual(len(verdicts[8].animated), 76)

    def test_a_change_exactly_one_window_old_is_outside_it(self):
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
            reading = monitor.observe(screen.frame(),
                                      now=0.1 * step)

        self.assertTrue(reading.stable)

    def test_a_window_never_observed_cannot_be_judged(self):
        # quiescence over a span nobody watched is not an answer the
        # measure has: every guarded observation pays one window
        # before its condition is first evaluated
        screen = _Screen().write(0, 0, "C:\\>")
        monitor = screen_stability.ScreenStability()

        reading = _observe(monitor, [screen.frame()] * 2)

        self.assertFalse(reading.stable)
        self.assertIsNone(reading.stability)


if __name__ == "__main__":
    unittest.main()
