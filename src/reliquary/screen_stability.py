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

**The contract generalizes from cells to pixels** (F65). A landmark
is compared against a captured framebuffer, where there are no cells
to compare, so `observe` also takes a Pillow image and measures the
proportion of *pixels* that held still — the same window, the same
default, the same recurrence mask. A `Reading` says which unit it
counted, so a diagnostic can too. The default needs no restating at
the finer grain: a landmark's residual demands every pixel, so a
half-painted screen fails the match on its own, and what the gate
buys there is an honest nearest-miss report rather than one measured
mid-repaint.

Stability is measured over a **window of wall-clock time**, never
between consecutive samples. Sample adjacency would make the answer a
property of the poll rate rather than of the guest: the same screen
reads stable at a dense cadence, where most adjacent pairs agree, and
unstable at a sparse one, where consecutive samples are far enough
apart to differ almost always. The consequence is stated rather than
hidden — a caller sampling sparser than the window cannot observe it,
and is told so instead of being given a verdict the cadence produced.

**Recurrence carried that dependence longer than the threshold did.**
Decoration is `animation_repeats` changes inside `animation_window`,
which is a sample count wearing a clock's clothes: a caller reading
once per 0.83s fits two samples in a 1s window and can never reach
three, so the mask stays empty, a blinking cursor scores as content,
and the screen never reads settled however long anyone waits. That is
the same artifact the window definition refuses, and it is answered
the same way — `Reading.blind` says the cadence cannot see decoration,
rather than handing back the number an empty mask produced.
"""

import dataclasses
import math
import time

from PIL import ImageChops

from .errors import InternalError


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

#: How much room over the bare minimum a widened window is given.
#: `repeats` samples is what *just* fits, and a window sized to just
#: fit flips its verdict whenever one read runs long — which on a
#: screenshot backend is every garbage collection. Doubling it costs
#: only a slower decoration verdict and buys a window that keeps
#: working when the cadence wobbles, so recurrence is measured over a
#: span the caller can actually sustain rather than one it can hit on
#: a good pass.
DEFAULT_CADENCE_MARGIN = 2.0

#: What the measured cadence is rounded **up** to before it sizes a
#: window, and it differs by how the screen was read because the two
#: paths have different noise. A text scrape is a memory read and its
#: jitter is milliseconds, so a 0.1s grid is finer than the variation
#: it quantizes. Interpreting a framebuffer costs the better part of a
#: second and varies by hundreds of milliseconds — image decode, glyph
#: matching, a host under load — so anything finer than a second would
#: have the window resize continuously on noise. Rounding up rather
#: than to nearest keeps every step in the generous direction, which
#: is the same instinct as the margin.
GUI_CADENCE_STEP = 1.0
TEXT_CADENCE_STEP = 0.1

#: The widest the animation window may grow, however slow the caller.
#: Past a few seconds "changed three times recently" stops describing
#: decoration and starts describing a screen painted in stages, so a
#: cadence that cannot be accommodated inside this is answered as
#: `Reading.blind` instead of by widening until everything is masked.
MAX_ANIMATION_WINDOW = 5.0

#: Slack on the window edge, so a change exactly one window old falls
#: *outside* it deterministically. Without this the boundary is
#: decided by float noise, and it is not a rare case: polling at 0.1s
#: against a 0.2s window puts a change exactly two samples back on the
#: edge every time, so the same settled screen would read stable or
#: unstable depending on accumulated rounding. Far below any real
#: sampling interval, so it can never absorb a change that mattered.
_EDGE = 1e-9


def unsettled_note(reading):
    """Why a condition that *was* seen never ended a wait.

    A wait expires two ways that look identical from outside: the
    thing waited for never came, or it came only on screens still
    being drawn. The second is baffling without help — a screenshot
    taken at the time shows it plainly — so a failure says which, and
    names the region set aside as decoration, that being what makes
    the message locate the problem rather than restate the expiry.
    Every gated wait appends this to its expiry (`execute`,
    `wait_ready`, `wait_text`); ``None`` — nothing was ever seen —
    adds nothing.
    """
    if reading is None:
        return ""
    note = ("; a match was on screen but what sits under it never "
            "settled")
    if reading.stability is None:
        return f"{note} (never read often enough to tell)"
    note += f" (stability {reading.stability:.3f}"
    if reading.animated:
        note += (f", outside a {len(reading.animated)}-"
                 f"{reading.unit} animated region")
    return f"{note})"


def viable_cadence(window=DEFAULT_ANIMATION_WINDOW,
                   repeats=DEFAULT_ANIMATION_REPEATS,
                   margin=DEFAULT_CADENCE_MARGIN):
    """The slowest poll that can still recognize decoration.

    **The minimum viable cadence**: recurrence needs ``repeats``
    changes inside ``window``, a change is only ever recorded at a
    sample, so a caller must fit that many samples in that span. With
    the default 1s window and 3 repeats, a poll slower than one read
    every ~0.17s cannot see decoration at all — which is most of a
    second short of what a screenshot backend costs, and is the whole
    of why this had to be answered rather than assumed.
    """
    return window / (repeats * margin)


def viable_window(interval, repeats=DEFAULT_ANIMATION_REPEATS,
                  margin=DEFAULT_CADENCE_MARGIN):
    """The animation window a caller reading every ``interval`` needs.

    The inverse of :func:`viable_cadence`, and what lets a slow
    caller keep the guard rather than lose it: a backend that costs
    0.83s a read needs a ~5s window to recognize decoration, and
    inside that window it recognizes exactly what a fast caller does.
    """
    return interval * repeats * margin


def _is_image(frame):
    """Whether this reading is a framebuffer rather than a text screen."""
    return hasattr(frame, "mode") and hasattr(frame, "size")


def _grid(frame):
    """Flatten a frame into rows of (character, attribute) pairs."""
    rows, attributes = frame
    grid = []
    for index, attribute_row in enumerate(attributes):
        text = rows[index] if index < len(rows) else ""
        grid.append(list(zip(text.ljust(len(attribute_row)),
                             attribute_row)))
    return grid


def _snapshot(frame):
    """The comparable form of one reading, and what it counts in."""
    if _is_image(frame):
        return frame.convert("RGB"), "pixel"
    return _grid(frame), "cell"


def _extent(snapshot, unit):
    """How many units this reading holds."""
    if unit == "pixel":
        return snapshot.size[0] * snapshot.size[1]
    return sum(len(row) for row in snapshot)


def _changed(before, after, unit):
    """The units whose identity differs between two readings."""
    if unit == "pixel":
        return _changed_pixels(before, after)
    return _changed_cells(before, after)


def _changed_cells(before, after):
    """The (row, column) cells whose identity pair differs."""
    changed = set()
    for row, (old, new) in enumerate(zip(before, after)):
        for column, (was, is_now) in enumerate(zip(old, new)):
            if was != is_now:
                changed.add((row, column))
    return changed


def _changed_pixels(before, after):
    """The flat indices of pixels that differ between two captures.

    Differenced band by band in Pillow rather than pixel by pixel in
    Python: a 640x480 screen is 307,200 units where a text screen is
    2,000, and the mask this feeds is rebuilt at every sample. A
    difference in *any* channel counts, which is the same
    identity-is-the-whole-thing rule the cell path applies to the
    character and attribute pair.
    """
    if before.size != after.size:
        return set(range(after.size[0] * after.size[1]))
    difference = ImageChops.difference(before, after)
    bands = difference.split()
    combined = bands[0]
    for band in bands[1:]:
        combined = ImageChops.lighter(combined, band)
    # ``tobytes`` on an ``L`` image is one byte per pixel with no
    # padding, so the index *is* the pixel — and unlike ``getdata`` it
    # is not on its way out of Pillow.
    return {index for index, value in enumerate(combined.tobytes())
            if value}


@dataclasses.dataclass(frozen=True, repr=False)
class Reading:
    """One verdict on the screen, and the evidence behind it.

    ``stability`` is the fraction of the screen that held still over
    the window, or ``None`` where the window could not be observed at
    all — which is a different answer from "moving", and a caller's
    diagnostic is expected to say which. ``animated`` is the region
    excluded as decoration, which is what lets a timeout say "stable
    outside a 76-cell animated region" rather than restating a ratio.

    ``blind`` says the poll is **too sparse for this measure to see
    decoration at all**, and it is the one answer no further sampling
    will improve: recurrence needs `animation_repeats` changes inside
    `animation_window`, a change can only be recorded at a sample, so
    a caller reading more slowly than that can never accumulate them.
    Distinguishing it from a monitor that is merely young is the
    whole of its purpose — both hold too little evidence, but one is
    a wait and the other is a permanent condition of the caller's
    cadence, and a caller that cannot tell them apart either blocks
    forever or pays a window it did not owe.

    A blind reading carries ``stability=None`` because the number the
    mask would have produced is exactly the verdict-from-cadence this
    module exists to refuse: with no decoration recognized, a blinking
    cursor counts as content and the screen never reads settled.

    The repr is written rather than generated because the animated
    region runs to thousands of cells on a churning screen, and a
    diagnostic that dumps them all buries the answer it carries.
    """

    stable: bool
    stability: float | None
    animated: frozenset = frozenset()
    blind: bool = False
    #: What the verdict counted — ``"cell"`` on a text screen,
    #: ``"pixel"`` on a captured framebuffer (F65). A diagnostic that
    #: names a region says which, rather than calling pixels cells.
    unit: str = "cell"

    def __repr__(self):
        return (f"Reading(stable={self.stable!r}, "
                f"stability={self.stability!r}, "
                f"animated={len(self.animated)} {self.unit}s"
                + (", blind" if self.blind else "") + ")")


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
                 animation_repeats=DEFAULT_ANIMATION_REPEATS,
                 cadence_margin=DEFAULT_CADENCE_MARGIN,
                 max_animation_window=MAX_ANIMATION_WINDOW,
                 cadence_step=TEXT_CADENCE_STEP):
        self._threshold = threshold
        self._window = window
        self._animation_window = animation_window
        self._animation_repeats = animation_repeats
        self._cadence_margin = cadence_margin
        self._max_animation_window = max_animation_window
        #: Public and mutable: the caller learns which reading path it
        #: is on from the session it opens, which is after the monitor
        #: is built. Defaults to the finer grid, so a caller that never
        #: sets it is quantized closest to its measured cadence.
        self.cadence_step = cadence_step
        self._previous = None
        self._first = None
        self._changes = []
        self._samples = []
        self._size = 0
        self._unit = "cell"

    def observe(self, frame, now=None):
        """Record one sample and return the `Reading` it produces.

        ``frame`` is the seam's text screen — ``(rows, attributes)``
        — or a Pillow image where the plane captured pixels (F65). A
        monitor stays on the kind it was first handed: mixing the two
        would compare a screen against a different thing entirely and
        read every sample as a total repaint.
        """
        if now is None:
            now = time.monotonic()
        snapshot, unit = _snapshot(frame)
        if self._previous is not None and unit != self._unit:
            raise InternalError(
                f"a stability monitor reading {self._unit}s was handed "
                f"a {unit} frame")
        self._unit = unit
        self._size = _extent(snapshot, unit)
        if self._first is None:
            self._first = now
        if self._previous is not None:
            self._changes.append(
                (now, _changed(self._previous, snapshot, unit)))
        self._previous = snapshot
        self._samples.append(now)
        self._prune(now)
        return self._read(now)

    def cadence(self):
        """The fastest gap between samples, or None before two.

        **The floor, not the average**, because what sizes the window
        is how fast this caller *can* read and not how fast it chose
        to. A caller that ramps — dense while a screen moves, idle
        while it rests, which is exactly what the script runtime does
        between its settle poll and its backoff — would otherwise
        have its quiet stretches widen the window and mask the very
        redraw the next dense pass exists to catch.

        Erring low is the safe direction: a cadence estimate that is
        too fast asks for a narrower window, which falls back to the
        default and judges as it always did. Too slow is what
        over-masks.
        """
        if len(self._samples) < 2:
            return None
        fastest = min(later - earlier for earlier, later
                      in zip(self._samples, self._samples[1:]))
        step = self.cadence_step
        if not step:
            return fastest
        return math.ceil((fastest - _EDGE) / step) * step

    def animation_window(self):
        """The window recurrence is actually measured over.

        **Widened to what this caller can observe**, never narrowed:
        a poll dense enough for the default keeps the default, and one
        too sparse gets the span its own cadence needs
        (:func:`viable_window`), up to `max_animation_window`. Past
        that the window would mask a screen painted in stages, so the
        measure stops widening and says it is blind instead.

        This is what makes the guard survive a screenshot backend
        rather than switch off there: inside the widened window, a
        slow caller recognizes exactly the decoration a fast one does.
        """
        interval = self.cadence()
        if interval is None:
            return self._animation_window
        return min(self._max_animation_window,
                   max(self._animation_window,
                       viable_window(interval, self._animation_repeats,
                                     self._cadence_margin)))

    def _prune(self, now):
        horizon = now - max(self._window, self.animation_window())
        self._changes = [(when, cells) for when, cells in self._changes
                         if when > horizon]
        # Samples outlive changes: the cadence estimate is what sizes
        # the window, so it must not be pruned by the window it sizes.
        sample_horizon = now - max(self._window,
                                   self._max_animation_window)
        self._samples = [when for when in self._samples
                         if when > sample_horizon]

    def _animated(self, now):
        """The cells repainting on their own, or none where most are.

        When most of the screen qualifies, masking it would leave
        almost nothing to judge and every frame would read settled —
        so the mask is dropped and the comparison runs raw, the same
        bail-out the menu machinery's learned mask already makes.
        """
        horizon = now - self.animation_window() + _EDGE
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

    def _blind(self):
        """Whether this caller *could* recognize decoration at all.

        Recurrence is `animation_repeats` changes inside the window,
        and a change is only ever recorded at a sample — so a caller
        whose reads cost more than a third of the window can never
        accumulate them: the mask stays empty, a blinking cursor
        scores as content, and every frame reads unsettled forever.

        **A question about capability, not about recent density.**
        Asking how many samples happen to fall in the last window
        answers it wrongly for any caller that ramps: the script
        runtime backs off to a 2s idle poll once a screen settles, and
        counting samples would call that backoff blindness and stand
        the guard down exactly when the next redraw arrives. What
        decides is the fastest cadence this caller has shown it can
        sustain, against the window that cadence earns.

        Reached only after widening has been tried and capped, so it
        answers a cadence nothing can accommodate rather than a merely
        slow one. Never claimed before a cadence is known, since one
        sample is a young monitor and not a slow caller.
        """
        interval = self.cadence()
        if interval is None:
            return False
        return interval * self._animation_repeats > self.animation_window()

    def _read(self, now):
        animated = self._animated(now)
        if now - self._first < self._window:
            return Reading(False, None, animated,
                           unit=self._unit)
        horizon = now - self._window + _EDGE
        changed = set()
        for when, cells in self._changes:
            if when > horizon:
                changed |= cells
        changed -= animated
        stability = 1.0 - len(changed) / self._size
        if stability >= self._threshold:
            return Reading(True, stability, animated,
                           unit=self._unit)
        # Only doubt a verdict the missing mask could have changed. A
        # screen that reads settled without one is settled whatever
        # the cadence, and saying otherwise would stand the guard down
        # on the quiet screens it costs nothing to judge.
        if self._blind():
            return Reading(False, None, animated, blind=True,
                           unit=self._unit)
        return Reading(False, stability, animated,
                       unit=self._unit)
