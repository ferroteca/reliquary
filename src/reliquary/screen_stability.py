# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Has the guest stopped drawing?

A condition can hold perfectly on a screen that is still painting,
and that is exactly the screen a wait must not act on. This module
answers the other question — whether the frame itself is settled
enough to compare against — over the seam's text-screen contract:
character rows plus opaque, equality-comparable per-cell attribute
tokens. **Identity is the whole pair**, because a cursor menu moves
its selection by attribute alone, and a text-only comparison would
score exactly those frames as perfectly stable.

Stability is measured over a **window of wall-clock time**, never
between consecutive samples. Sample adjacency would make the answer a
property of the poll rate rather than of the guest: the same screen
reads stable at a dense cadence, where most adjacent pairs agree, and
unstable at a sparse one, where consecutive samples are far enough
apart to differ almost always. The consequence is stated rather than
hidden — a caller sampling sparser than the window cannot observe it,
and is told so instead of being given a verdict the cadence produced.
"""

import dataclasses
import time


#: A quarter of an 80-column row. A text screen is 80 x 25 = 2000
#: cells, so a single row of text is 80 of them — 4% of the screen.
#: Any threshold looser than 0.96 therefore calls a screen stable
#: while a line is being drawn into it, which is precisely the event
#: this measure exists to refuse. Screen furniture costs an order of
#: magnitude less: a blinking cursor is 1 cell (0.05%), a clock 8
#: (0.4%), a percentage counter 4 (0.2%). The default's whole job is
#: to sit in that gap — above furniture, below content.
DEFAULT_THRESHOLD = 0.99

#: How far back a verdict looks. Quiescence cannot be claimed over a
#: span that was never observed, so a monitor younger than this
#: reports that it cannot measure rather than guessing.
DEFAULT_WINDOW = 0.2

#: Decoration is recognized by **recurrence**, and over the clock
#: rather than over samples: a denser run collects more samples in the
#: same wall time and would reach any sample count sooner, which is
#: the cadence dependence the window definition exists to refuse.
#: A cell changing this often within this span is repainting on its
#: own — an advancing cursor, a marching border, a spinner — and a
#: cell that changes once is content, wherever it sits.
DEFAULT_ANIMATION_WINDOW = 1.0
DEFAULT_ANIMATION_REPEATS = 3

#: Slack on the window edge, so a change exactly one window old falls
#: *outside* it deterministically. Without this the boundary is
#: decided by float noise, and it is not a rare case: polling at 0.1s
#: against a 0.2s window puts a change exactly two samples back on the
#: edge every time, so the same settled screen would read stable or
#: unstable depending on accumulated rounding. Far below any real
#: sampling interval, so it can never absorb a change that mattered.
_EDGE = 1e-9


def _grid(frame):
    """Flatten a frame into rows of (character, attribute) pairs."""
    rows, attributes = frame
    grid = []
    for index, attribute_row in enumerate(attributes):
        text = rows[index] if index < len(rows) else ""
        grid.append(list(zip(text.ljust(len(attribute_row)),
                             attribute_row)))
    return grid


def _changed_cells(before, after):
    """The (row, column) cells whose identity pair differs."""
    changed = set()
    for row, (old, new) in enumerate(zip(before, after)):
        for column, (was, is_now) in enumerate(zip(old, new)):
            if was != is_now:
                changed.add((row, column))
    return changed


@dataclasses.dataclass(frozen=True, repr=False)
class Reading:
    """One verdict on the screen, and the evidence behind it.

    ``stability`` is the fraction of the screen that held still over
    the window, or ``None`` where the window could not be observed at
    all — which is a different answer from "moving", and a caller's
    diagnostic is expected to say which. ``animated`` is the region
    excluded as decoration, which is what lets a timeout say "stable
    outside a 76-cell animated region" rather than restating a ratio.

    The repr is written rather than generated because the animated
    region runs to thousands of cells on a churning screen, and a
    diagnostic that dumps them all buries the answer it carries.
    """

    stable: bool
    stability: float | None
    animated: frozenset = frozenset()

    def __repr__(self):
        return (f"Reading(stable={self.stable!r}, "
                f"stability={self.stability!r}, "
                f"animated={len(self.animated)} cells)")


class ScreenStability:
    """Judges whether the guest has stopped drawing.

    Samples are handed in as they are read — the monitor never reads
    for itself, so it carries no session and no clock of its own
    beyond a default `now`. Each `observe` returns the verdict as of
    that sample.
    """

    def __init__(self, threshold=DEFAULT_THRESHOLD,
                 window=DEFAULT_WINDOW,
                 animation_window=DEFAULT_ANIMATION_WINDOW,
                 animation_repeats=DEFAULT_ANIMATION_REPEATS):
        self._threshold = threshold
        self._window = window
        self._animation_window = animation_window
        self._animation_repeats = animation_repeats
        self._previous = None
        self._first = None
        self._changes = []
        self._size = 0

    def observe(self, frame, now=None):
        """Record one sample and return the `Reading` it produces."""
        if now is None:
            now = time.monotonic()
        grid = _grid(frame)
        self._size = sum(len(row) for row in grid)
        if self._first is None:
            self._first = now
        if self._previous is not None:
            self._changes.append(
                (now, _changed_cells(self._previous, grid)))
        self._previous = grid
        self._prune(now)
        return self._read(now)

    def _prune(self, now):
        horizon = now - max(self._window, self._animation_window)
        self._changes = [(when, cells) for when, cells in self._changes
                         if when > horizon]

    def _animated(self, now):
        """The cells repainting on their own, or none where most are.

        When most of the screen qualifies, masking it would leave
        almost nothing to judge and every frame would read settled —
        so the mask is dropped and the comparison runs raw, the same
        bail-out the menu machinery's learned mask already makes.
        """
        horizon = now - self._animation_window + _EDGE
        counts = {}
        for when, cells in self._changes:
            if when <= horizon:
                continue
            for cell in cells:
                counts[cell] = counts.get(cell, 0) + 1
        animated = {cell for cell, count in counts.items()
                    if count >= self._animation_repeats}
        if len(animated) * 2 > self._size:
            return frozenset()
        return frozenset(animated)

    def _read(self, now):
        animated = self._animated(now)
        if now - self._first < self._window:
            return Reading(False, None, animated)
        horizon = now - self._window + _EDGE
        changed = set()
        for when, cells in self._changes:
            if when > horizon:
                changed |= cells
        changed -= animated
        stability = 1.0 - len(changed) / self._size
        return Reading(stability >= self._threshold, stability,
                       animated)
