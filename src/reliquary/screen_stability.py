# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Has the guest stopped drawing?

A script condition can be true on a screen that is still being drawn,
and that is exactly the screen a `wait` must not act on. This module
answers a separate, narrower question: has the captured frame itself
settled enough to be trusted for comparison? It works over the
standard text-screen format every backend must produce: rows of
characters, plus one opaque, comparable attribute token per cell.
Both the character and the attribute matter together, not just the
character: a cursor menu can move its selection using color alone, so
comparing only the text would score those frames as perfectly stable
even while the highlight was still moving.

This same check generalizes from character cells to pixels (F65).
Matching a landmark compares against a captured framebuffer image,
where there are no character cells to compare — so `observe` also
accepts a Pillow image directly, and instead measures the fraction of
*pixels* that stayed unchanged, using the same time window, the same
default threshold, and the same self-animating-region mask. A
`Reading` records which unit it measured, so a diagnostic message can
say which too. The default threshold does not need a separate value
at the pixel level: a landmark match already requires every pixel in
its residual area to match exactly, so a screen that is still
half-painted simply fails the match on its own — what this settling
check adds there is an honest "nearest miss" report, rather than one
measured mid-repaint.

Stability is measured over a fixed window of wall-clock time, never
just by comparing two consecutive samples. Comparing only consecutive
samples would make the answer depend on how fast the caller happens
to poll, not on what the guest is actually doing: the same screen
would read as stable when polled quickly (most back-to-back reads
agree) and unstable when polled slowly (consecutive reads are far
enough apart to differ almost every time). This limitation is stated
explicitly rather than hidden: a caller polling slower than the
stability window simply cannot observe stability at all, and is told
that directly instead of being handed a verdict that's really just an
artifact of its own poll rate.

The self-animating-cell detection ("recurrence") carried this same
poll-rate dependency for longer than the plain stability threshold
did, before it was fixed too. Decoration is defined as
`animation_repeats` changes within `animation_window` — which is
really a sample count wearing a time duration's clothes: a caller
reading once every 0.83 seconds only fits two samples into a
one-second window and can never reach three changes, so its
self-animating mask stays permanently empty, a blinking cursor gets
counted as real content forever, and the screen never reads as
settled no matter how long anyone waits. That is the exact same
poll-rate-dependency bug the window-based definition above was meant
to prevent, and it is fixed the same way: `Reading.blind` reports
directly that this poll rate is too slow to ever detect decoration,
instead of returning whatever number a falsely empty mask produced.
"""

import dataclasses
import math
import time

from PIL import ImageChops

from .errors import InternalError


#: 0.99 leaves 1% of the screen free to differ and still count as
#: stable — a quarter of an 80-column row, or 20 cells out of the
#: 2000 in a full 80x25 text screen. A looser threshold than 0.96 (4%
#: free, a full row) would call a screen stable while an entire line
#: is still being drawn into it — exactly the false positive this
#: measure exists to prevent. Small self-animating screen details
#: cost far fewer cells than that: a blinking cursor is 1 cell
#: (0.05%), a clock 8 cells (0.4%), a percentage counter 4 cells
#: (0.2%). The whole job of this default is to sit in the gap between
#: those — above what decoration changes, below what real content
#: changes.
DEFAULT_THRESHOLD = 0.99

#: How far back a stability verdict looks, in seconds. A screen can't
#: be said to have held still over a span that was never actually
#: observed, so a monitor younger than this window reports that it
#: cannot measure yet, rather than guessing.
DEFAULT_WINDOW = 0.2

#: Decoration is recognized by how often a cell changes
#: (`DEFAULT_ANIMATION_REPEATS`), measured over wall-clock time
#: (`DEFAULT_ANIMATION_WINDOW`) rather than over a fixed number of
#: samples: a faster poll rate collects more samples in the same real
#: time and would hit any given sample count sooner, which is exactly
#: the poll-rate dependency the time-window approach above is meant
#: to avoid. A cell that changes this many times within this span is
#: repainting on its own — an advancing cursor, a marching border, a
#: spinner — while a cell that changes only once counts as real
#: content, wherever it is on screen.
DEFAULT_ANIMATION_WINDOW = 1.0
DEFAULT_ANIMATION_REPEATS = 3

#: How much extra room a widened animation window gets, beyond the
#: bare minimum needed. Exactly `repeats` samples is what *just*
#: fits, and a window sized to just barely fit flips its verdict
#: every time a single read happens to run long — which on a
#: screenshot backend happens on essentially every garbage collection
#: pause. Doubling the minimum only costs a slower decoration
#: verdict, and in exchange keeps working even when the poll rate
#: wobbles, so decoration is measured over a span the caller can
#: reliably sustain, not just one it can hit on a lucky run.
DEFAULT_CADENCE_MARGIN = 2.0

#: The step size the measured poll rate is rounded *up* to before it
#: is used to size a window. It differs by how the screen is read,
#: because the two reading paths have different amounts of timing
#: noise. A text scrape is a plain memory read, with jitter of only a
#: few milliseconds, so a 0.1s step is finer than the noise it's
#: rounding away. Recognizing a framebuffer, by contrast, costs the
#: better part of a second and varies by hundreds of milliseconds —
#: image decoding, glyph matching, a busy host — so anything finer
#: than a full second would make the window resize constantly just
#: from that noise. Rounding up rather than to the nearest step keeps
#: every adjustment generous, the same instinct behind
#: `DEFAULT_CADENCE_MARGIN`.
GUI_CADENCE_STEP = 1.0
TEXT_CADENCE_STEP = 0.1

#: The widest the animation window is ever allowed to grow, no matter
#: how slow the caller's poll rate is. Past a few seconds, "changed
#: three times recently" stops meaning decoration and starts meaning
#: a screen that is being painted in stages, so a poll rate too slow
#: to fit inside this cap gets reported as `Reading.blind` instead of
#: having the window widened until it masks everything.
MAX_ANIMATION_WINDOW = 5.0

#: A tiny amount of slack at the window's edge, so a change exactly
#: one window old reliably falls *outside* it. Without this, the
#: boundary would be decided by floating-point rounding noise, and
#: that's not a rare edge case: polling every 0.1s against a 0.2s
#: window puts a change exactly two samples back right on the
#: boundary every single time, so the same settled screen could read
#: as stable or unstable depending on accumulated rounding error.
#: This is far below any real sampling interval, so it can never
#: absorb a change that actually mattered.
_EDGE = 1e-9


def unsettled_note(reading):
    """Explain why a condition that was seen on screen never ended a
    wait.

    A wait can time out for two reasons that look identical from the
    outside: either the thing being waited for never appeared, or it
    only ever appeared on screens that were still being drawn. The
    second case is baffling without an explanation — a screenshot
    taken at the time would show it plainly — so a timeout message
    says which case it was, and names the region that was set aside
    as decoration, which is what lets the message point at the actual
    problem instead of just repeating that a timeout happened. Every
    wait that uses this settling check appends this note to its
    timeout message (`execute`, `wait_ready`, `wait_text`); passing
    ``None`` (nothing was ever seen) adds nothing.
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
    """Return the slowest poll rate that can still recognize
    decoration.

    Recognizing decoration needs ``repeats`` changes inside
    ``window``, and a change is only ever recorded when a sample is
    taken, so a caller has to fit at least that many samples into
    that span. With the default 1-second window and 3 repeats, a
    poll slower than one read every ~0.17 seconds can't see
    decoration at all — which is most of a second faster than a
    screenshot backend actually costs per read, and is exactly why
    this had to be measured rather than assumed to be fine.
    """
    return window / (repeats * margin)


def viable_window(interval, repeats=DEFAULT_ANIMATION_REPEATS,
                  margin=DEFAULT_CADENCE_MARGIN):
    """Return the animation window a caller reading every ``interval``
    seconds needs.

    This is the inverse of :func:`viable_cadence`, and it's what lets
    a slow caller keep this protection instead of losing it: a
    backend that costs 0.83 seconds per read needs roughly a
    5-second window to recognize decoration, and within that wider
    window it recognizes exactly the same decoration a fast caller
    would.
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
    """Return the comparable form of one reading, along with the unit
    it is measured in ("pixel" for a framebuffer, "cell" for a text
    screen)."""
    if _is_image(frame):
        return frame.convert("RGB"), "pixel"
    return _grid(frame), "cell"


def _extent(snapshot, unit):
    """Return how many units (cells or pixels) this reading holds."""
    if unit == "pixel":
        return snapshot.size[0] * snapshot.size[1]
    return sum(len(row) for row in snapshot)


def _changed(before, after, unit):
    """Return the units (cells or pixels) whose identity differs
    between two readings."""
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
    """Return the flat indices of pixels that differ between two
    captures.

    Differenced band by band using Pillow, rather than pixel by pixel
    in Python: a 640x480 screen has 307,200 pixels versus a text
    screen's 2,000 cells, and the mask this feeds into is rebuilt on
    every sample, so the difference has to be fast. A difference in
    *any* color channel counts as the pixel having changed, which is
    the same all-parts-matter rule the cell path applies to the
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
    the window, or ``None`` when the window could not be observed at
    all — which is a different situation from "the screen is moving",
    and a caller's diagnostic is expected to say which one it got.
    ``animated`` is the region excluded as decoration, which is what
    lets a timeout message say "stable outside a 76-cell animated
    region" instead of just restating a ratio.

    ``blind`` means the poll rate is too slow for this measure to
    ever recognize decoration at all, and it's the one answer that no
    amount of further sampling can fix: recognizing decoration needs
    `animation_repeats` changes inside `animation_window`, a change
    can only be recorded at a sample, so a caller reading slower than
    that can never accumulate enough of them. Telling this apart from
    a monitor that is simply still young is the whole point of this
    flag — both situations have too little evidence yet, but one will
    resolve itself with more waiting and the other is a permanent
    limit of the caller's own poll rate. A caller that can't tell the
    two apart either blocks forever, or pays for a wider window it
    didn't actually need.

    A blind reading carries ``stability=None`` because the number the
    mask would otherwise have produced is exactly the
    poll-rate-dependent verdict this module exists to avoid: with no
    decoration recognized, a blinking cursor counts as real content
    and the screen never reads as settled.

    ``__repr__`` is written by hand rather than generated
    automatically, because the animated region can run to thousands
    of cells on a constantly-changing screen, and a diagnostic that
    dumps them all would bury the actual answer in noise.
    """

    stable: bool
    stability: float | None
    animated: frozenset = frozenset()
    blind: bool = False
    #: What this verdict counted in — ``"cell"`` on a text screen,
    #: ``"pixel"`` on a captured framebuffer (F65). A diagnostic that
    #: names a region uses this to say which unit it means, rather
    #: than mislabeling pixels as cells.
    unit: str = "cell"

    def __repr__(self):
        return (f"Reading(stable={self.stable!r}, "
                f"stability={self.stability!r}, "
                f"animated={len(self.animated)} {self.unit}s"
                + (", blind" if self.blind else "") + ")")


class ScreenStability:
    """Judges whether the guest has stopped drawing.

    Samples are handed to it as they are read — this monitor never
    reads the screen itself, so it holds no session and keeps no
    clock of its own beyond a default value for `now`. Each call to
    `observe` returns the verdict as of that one sample.
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
        #: Public and mutable, because a caller only learns which
        #: reading path it is on (text or pixel) once it opens its
        #: session, which happens after this monitor is already
        #: built. Defaults to the finer step, so a caller that never
        #: sets this stays quantized as close as possible to its
        #: actual measured poll rate.
        self.cadence_step = cadence_step
        self._previous = None
        self._first = None
        self._changes = []
        self._samples = []
        self._size = 0
        self._unit = "cell"

    def observe(self, frame, now=None):
        """Record one sample and return the `Reading` it produces.

        ``frame`` is either the standard text screen format every
        backend must produce — ``(rows, attributes)`` — or a Pillow
        image, when the plane captures pixels instead (F65). A
        monitor sticks with whichever kind it was first handed:
        mixing the two would compare a screen against something of an
        entirely different kind, and every sample would read as a
        total repaint.
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
        """Return the fastest gap between samples, or None before at
        least two samples exist.

        This returns the *floor* (the fastest gap seen), not the
        average, because what needs to size the window is how fast
        this caller *can* read, not how fast it happened to read on
        average. A caller that ramps its poll rate up and down —
        reading fast while the screen is moving, and backing off
        while it's idle, which is exactly what the script runtime
        does between its settle poll and its backoff — would
        otherwise have its idle stretches widen the window and mask
        the very redraw its next fast pass exists to catch.

        Erring toward too fast an estimate is the safe direction: an
        estimate that's faster than reality asks for a narrower
        window than needed, which just falls back to the default and
        judges the way it always did. An estimate that's too slow is
        what causes decoration to get over-masked.
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
        """Return the window decoration is actually measured over.

        This window is only ever widened to fit what this caller can
        actually observe, never narrowed: a poll rate fast enough for
        the default window keeps the default, and a poll rate too
        slow gets widened to the span its own poll rate needs (see
        :func:`viable_window`), up to `max_animation_window`. Past
        that cap, widening the window further would start masking a
        screen that is genuinely being painted in stages, so this
        stops widening and reports itself as blind instead.

        This is what lets this protection keep working on a
        screenshot backend instead of just giving up there: inside
        the widened window, a slow caller recognizes exactly the same
        decoration a fast caller would.
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
        # Samples are kept longer than changes: the poll-rate estimate
        # (`cadence`) is what determines the window size, so the
        # samples feeding that estimate must not themselves be pruned
        # by the window they help size.
        sample_horizon = now - max(self._window,
                                   self._max_animation_window)
        self._samples = [when for when in self._samples
                         if when > sample_horizon]

    def _animated(self, now):
        """Return the cells repainting on their own, or none when most
        of the screen qualifies.

        When most of the screen would count as decoration, masking it
        all out would leave almost nothing left to judge, and every
        frame would read as settled regardless of what's actually
        happening — so in that case the mask is dropped entirely and
        the comparison runs on the raw screen instead. This is the
        same fallback the menu-tracking code's own learned mask
        already uses.
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
        """Return whether this caller could recognize decoration at
        all, at its current poll rate.

        Recognizing decoration needs `animation_repeats` changes
        inside the window, and a change is only ever recorded at a
        sample — so a caller whose reads cost more than about a third
        of the window can never accumulate enough of them: the mask
        stays permanently empty, a blinking cursor gets counted as
        real content, and every frame reads as unsettled forever.

        This asks about the caller's *capability*, not about how many
        samples happened to land in the recent window. Counting
        recent samples would get the wrong answer for any caller that
        ramps its poll rate: the script runtime backs off to a
        2-second idle poll once a screen looks settled, and counting
        samples would then mistake that backoff for blindness, and
        stand this protection down at exactly the moment the next
        redraw arrives. What actually decides is the fastest poll
        rate this caller has shown it can sustain, checked against
        the window that poll rate earns.

        This is only checked after the window has already been
        widened as far as it can go, so it reports a poll rate that
        genuinely can't be accommodated, not merely a slow one that
        widening could still fix. It is never reported before a poll
        rate is even known yet, since one sample alone just means a
        young monitor, not a slow caller.
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
        # Only question a verdict that a missing mask could actually
        # have changed. A screen that already reads as settled without
        # any masking is settled no matter what the poll rate was, and
        # saying otherwise would stand this protection down on quiet
        # screens that cost nothing to judge correctly.
        if self._blind():
            return Reading(False, None, animated, blind=True,
                           unit=self._unit)
        return Reading(False, stability, animated,
                       unit=self._unit)
