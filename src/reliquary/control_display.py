# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The agentless display console: the first real control plane.

A control plane composes an adapter's carriers and presents
capabilities to a platform workflow
(planning/design/guest-communication.md). This one composes key
injection and text readback: it has no guest prerequisite, and it is
the DOS default and permanent fallback.

**Nothing here is QEMU.** The console reads the seam's text-screen
contract — character rows plus opaque, equality-comparable per-cell
attribute tokens — so the menu machinery below never interprets an
attribute value, only compares tokens for equality and frequency to
find and follow the selection highlight. VGA attribute bytes satisfy
that contract today; a fixed-font recognizer hashing each cell's
foreground/background pair into a token satisfies it identically, and
this algorithm carries over unchanged. Where a backend has no native
text carrier, that one shared recognizer lives in
:mod:`reliquary.text_recognize` — composed here, never once per
adapter.

**Whether a screen has stopped changing is not decided here.** That
measure is :mod:`screen_stability`'s, and this module is one of its
callers rather than the owner of a copy: the menu machinery met the
half-drawn-screen hazard first and grew its own hold-for-two-reads
and its own learned animation mask, both of which turned out to be
special cases of the general measure. What stays here is what was
never about settling — whether a keypress changed anything at all,
and which row the highlight moved to. Those are classification.
"""

import difflib
import time

from . import screen_stability
from .errors import RunFailure, StaticError

#: How often the screen is read while waiting for it to settle.
#: A quiescence window is only observable by sampling inside it, so
#: this is the menu machinery's own poll rather than a tuned constant:
#: what counts as settled is :mod:`screen_stability`'s to say.
_SETTLE_POLL = 0.1

#: How many reads a baseline takes before trusting its mask, and the
#: number is forced rather than chosen. **Settling and recognizing
#: decoration want different amounts of looking**: a clock ticking in
#: a corner moves two cells, which is settled on sight, yet nothing
#: can know it is a clock until it has ticked repeatedly. Stopping at
#: the first settled frame would hand back an empty mask and leave the
#: menu treating its own furniture as the effect of a keypress. A cell
#: must change `repeats` times to qualify as decoration, which cannot
#: be observed in fewer than that many reads plus the one they are
#: measured against.
_BASELINE_READS = screen_stability.DEFAULT_ANIMATION_REPEATS + 1

#: Which way each cursor key moves a selection bar. Used only to break
#: a tie between equally good candidate moves, never to require one.
_DIRECTIONS = {"down": 1, "up": -1}


_SHIFTED = {
    ":": "semicolon", "_": "minus", "?": "slash", '"': "apostrophe",
    "!": "1", "@": "2", "#": "3", "$": "4", "%": "5", "^": "6",
    "&": "7", "*": "8", "(": "9", ")": "0", "+": "equal",
    "<": "comma", ">": "dot", "{": "bracket_left", "}": "bracket_right",
    "|": "backslash", "~": "grave_accent",
}
_PLAIN = {
    " ": "spc", ".": "dot", "-": "minus", "=": "equal",
    "\\": "backslash", "/": "slash", ";": "semicolon", ",": "comma",
    "'": "apostrophe", "[": "bracket_left", "]": "bracket_right",
    "`": "grave_accent", "\n": "ret",
}


def char_keys(character):
    """Map one character to a simultaneous key-name combination.

    The names are **the seam's key vocabulary, which is QEMU's qcode
    set** (D103) — which is why the tables above spell `spc` and
    `ret` rather than `space` and `enter`. The adapter translates
    them into its backend's own input events; on QEMU that is the
    identity, and on VirtualBox a scancode lookup.

    This is the character half of key mapping. The *language's*
    `press` names are a separate, genuinely portable vocabulary
    (`script_validation.PORTABLE_KEY_NAMES`), resolved onto this set
    by `script_runner.resolve_key` before anything reaches the seam.
    """
    if character in _PLAIN:
        return [_PLAIN[character]]
    if character in _SHIFTED:
        return ["shift", _SHIFTED[character]]
    if character.islower() or character.isdigit():
        return [character]
    if character.isupper():
        return ["shift", character.lower()]
    raise StaticError(f"no key mapping for {character!r}",
        rule_id="key.no-mapping")


def _normalize(text):
    """Fold case and whitespace for tolerant menu-text comparison."""
    return " ".join(text.split()).casefold()


def _match_menu_row(rows, item, exclude=()):
    """Return the single screen row showing the item.

    A row equal to the item (case- and whitespace-folded) wins over
    rows merely containing it, so an item that is a prefix of a longer
    sibling ("Plain DOS system" beside "Plain DOS system, with
    sources") stays selectable. Otherwise the item must be contained
    in exactly one row. Rows containing any of the exclude texts are
    never selected.
    """
    target = _normalize(item)
    if isinstance(exclude, str):
        exclude = (exclude,)
    banned = [text for text in map(_normalize, exclude) if text]
    folded_rows = [_normalize(text) for text in rows]

    def allowed(folded):
        return not any(marker in folded for marker in banned)

    matches = [row for row, folded in enumerate(folded_rows)
               if folded == target and allowed(folded)]
    if not matches:
        matches = [row for row, folded in enumerate(folded_rows)
                   if target in folded and allowed(folded)]
    if len(matches) == 1:
        return matches[0]
    if matches:
        listed = ", ".join(repr(rows[row].strip()) for row in matches)
        raise RunFailure(
            f"menu item {item!r} matches multiple rows: {listed}",
            rule_id="screen.menu-ambiguous")
    excluded = [row for row, folded in enumerate(folded_rows)
                if target in folded and not allowed(folded)]
    if excluded:
        listed = ", ".join(repr(rows[row].strip()) for row in excluded)
        raise RunFailure(
            f"menu item {item!r} only matches excluded rows: {listed}",
            rule_id="screen.menu-excluded")
    candidates = {folded: text.strip()
                  for folded, text in zip(folded_rows, rows)
                  if text.strip() and allowed(folded)}
    close = difflib.get_close_matches(target, candidates, n=3,
                                      cutoff=0.5)
    hint = ("; closest rows: "
            + ", ".join(repr(candidates[text]) for text in close)
            if close else "")
    raise RunFailure(f"menu item {item!r} is not on screen{hint}",
        rule_id="screen.menu-absent")


def _masked_attributes(attributes, mask):
    """Attribute rows with self-animating cells nulled for comparison."""
    view = [list(row) for row in attributes]
    for row, column in mask:
        view[row][column] = None
    return view


def _changed_attribute(before, attributes, row):
    """Dominant attribute among the row's cells that just changed."""
    counts = {}
    for old, new in zip(before[row], attributes[row]):
        if old != new:
            counts[new] = counts.get(new, 0) + 1
    return max(counts, key=counts.get) if counts else None


def _rows_by_attribute(frame):
    """Which rows each attribute token appears on."""
    index = {}
    for number, row in enumerate(frame):
        for attribute in set(row):
            if attribute is not None:
                index.setdefault(attribute, set()).add(number)
    return index


def _relocated_bar(before, attributes, direction=None):
    """The bar found as the row-unique attribute that changed rows.

    **This is what a selection bar *is*** — an attribute confined to
    one row that moves to another — and saying it that way rather
    than as "the rarest attribute on screen" is what makes tracking
    survive a real framebuffer. Counting cells assumes a row wears one
    attribute, which holds for VGA bytes scraped out of text memory
    and fails for tokens recovered from pixels: a blank cell shows
    only one colour, so nothing can tell its foreground from its
    background, and it can never carry the same token as a lettered
    cell beside it. A bar therefore reads as *two* tokens, and the
    blank one is the backdrop's — the most common token on screen,
    which is the opposite of what rarity looks for.

    Confinement is immune to all of that. It also survives the menu
    that rewrites every row per keypress, because retranslating text
    changes which cells carry a token, never the fact that the bar's
    lettered cells are the only ones wearing theirs.

    Confinement alone is decisive only above two items. With exactly
    one unhighlighted row that row's token is confined too, so two
    attributes make an equally good move — in *opposite directions*,
    which is what ``direction`` then settles: a selection bar travels
    the way the cursor key points. It is a tie-break rather than a
    filter, so a menu that wraps its bar from bottom to top is left
    to the reading below instead of being classified wrongly.

    Returns (row, that row's bar attribute), or (None, None) when no
    single attribute made an unambiguous move.
    """
    was = _rows_by_attribute(before)
    now = _rows_by_attribute(attributes)
    moved = []
    for attribute, rows in now.items():
        if len(rows) != 1:
            continue
        previously = was.get(attribute)
        if previously is None or len(previously) != 1:
            continue
        if previously != rows:
            moved.append(
                (next(iter(previously)), next(iter(rows)), attribute))
    if len(moved) != 1 and direction:
        moved = [entry for entry in moved
                 if (entry[1] - entry[0] > 0) == (direction > 0)]
    if len(moved) == 1:
        _from, row, attribute = moved[0]
        return row, attribute
    return None, None


def _bar_move(before, attributes, direction=None):
    """Locate the menu highlight from an observed attribute change.

    Prefers :func:`_relocated_bar`. Where no attribute made an
    unambiguous move — the bar was erased rather than moved, or the
    screen repainted too broadly to tell — it falls back to the
    frequency reading below, which is what tracked the bar before and
    still answers the uniform-attribute screens a text-memory scrape
    produces.

    The fallback: the rows whose attributes changed after a cursor
    keypress are the old and new cursor positions, and of those the
    newly highlighted row is the one whose changed cells now carry
    the rarest attribute on screen — the normal menu color covers
    many rows, the selection bar exactly one. It answers None when
    nothing changed, or when no changed row gained a bar-like
    attribute, a row whose changed cells took on a widespread
    attribute being a bar erased or a partial repaint.
    """
    row, attribute = _relocated_bar(before, attributes, direction)
    if row is not None:
        return row, attribute
    changed = [row for row in range(len(attributes))
               if attributes[row] != before[row]]
    if not changed:
        return None, None
    frequency = {}
    for row_attributes in attributes:
        for attribute in row_attributes:
            if attribute is not None:
                frequency[attribute] = frequency.get(attribute, 0) + 1

    def rarity(row):
        return frequency[_changed_attribute(before, attributes, row)]

    best = min(changed, key=rarity)
    if rarity(best) > 160:
        return None, None
    return best, _changed_attribute(before, attributes, best)


class DisplayConsole:
    """Keyboard input and text-screen composition over one session.

    Shared by `Machine` methods and interaction adapters that hold a
    session across several exchanges. The session is an adapter's, and
    the console reaches the backend through its carriers alone.
    """

    def __init__(self, session):
        self._session = session
        #: Whether this console's screens are interpreted from pixels
        #: rather than read as resolved characters. Carried through
        #: from the adapter's session because it decides how coarsely
        #: a quiescence caller may quantize its cadence, and a
        #: transcript wrapper must not lose it.
        self.recognizes_text = getattr(
            session, "recognizes_text", False)

    def send_keys(self, combos, delay=0.06):
        """Send a list of key-name combinations to the guest."""
        self._session.send_keys(combos, delay)

    def send_text(self, text, enter=True):
        combos = [char_keys(character) for character in text]
        if enter:
            combos.append(["ret"])
        self.send_keys(combos)

    def screen_text(self):
        """Return the guest's text screen as character rows."""
        return self._session.text_screen()[0]

    def screen(self):
        """Return the screen as (character rows, attribute rows)."""
        return self._session.text_screen()

    def cursor_menu_select(self, item, timeout=30, exclude=()):
        """Steer a cursor-key menu onto a matching item and press ENTER.

        Presses up/down and observes the per-cell attribute tokens to
        follow the selection highlight, so the choice is confirmed by
        what the guest displays rather than by counting keystrokes. The
        screen is sampled before the first keypress so self-animating
        cells (clocks, countdowns, blinking indicators) are ignored, and
        each keypress waits for the redraw it causes to finish — slow
        menus repaint over several reads. Rows containing any of the
        exclude texts are never selected. The item must match when
        navigation starts; if a redraw later rewrites the rows (a
        language chooser translating itself as the highlight moves),
        the target keeps its last matched row. ENTER is only sent
        once a fresh read shows the highlight on the target row.
        Returns the selected row's text as displayed at selection.
        """
        if not _normalize(item):
            raise StaticError("menu item text must be non-empty",
                rule_id="value.not-a-string")
        deadline = time.monotonic() + timeout
        mask, rows, attributes = self._menu_baseline(deadline)
        target_row = _match_menu_row(rows, item, exclude)
        current = None
        highlight = None
        for key in ("down", "up"):
            self.send_keys([[key]])
            responded, moved_rows, attributes, current, attribute = (
                self._follow_keypress(attributes, deadline, mask, key))
            if moved_rows is not None:
                rows = moved_rows
            if current is not None:
                highlight = attribute
                break
        if current is None:
            raise RunFailure(
                "no menu highlight responded to cursor keys; cannot "
                f"select {item!r}", rule_id="screen.menu-no-highlight")
        stalled = 0
        while True:
            while current != target_row:
                if time.monotonic() >= deadline:
                    raise RunFailure(
                        f"menu highlight never reached {item!r} within "
                        f"{timeout}s; is it a selectable menu item?",
                        rule_id="screen.menu-unreachable")
                key = "down" if current < target_row else "up"
                self.send_keys([[key]])
                responded, moved_rows, attributes, moved, attribute = (
                    self._follow_keypress(attributes, deadline, mask, key))
                if moved is not None:
                    stalled = 0
                    current = moved
                    highlight = attribute
                    rows = moved_rows
                else:
                    # No classifiable movement. A stale mask can hide
                    # the bar's cells, and a keypress at the menu's
                    # edge legitimately changes nothing — re-learn the
                    # animation cells on the now-quiet screen and look
                    # for the bar directly before giving up.
                    mask, rows, attributes = (
                        self._menu_baseline(deadline))
                    candidates = [row for row in range(len(attributes))
                                  if highlight in attributes[row]]
                    relocated = (candidates[0]
                                 if len(candidates) == 1 else None)
                    if relocated is not None and relocated != current:
                        stalled = 0
                        current = relocated
                    elif responded:
                        stalled = 0
                    else:
                        stalled += 1
                        if stalled >= 2:
                            raise RunFailure(
                                "menu highlight stopped responding "
                                f"before reaching {item!r}",
                                rule_id="screen.menu-stalled")
                try:
                    target_row = _match_menu_row(rows, item, exclude)
                except RunFailure:
                    # Menus like the FreeDOS language chooser rewrite
                    # every row as the highlight moves; the target
                    # keeps its row from the screen where it was last
                    # matched.
                    pass
            fresh_rows, fresh_raw = self.screen()
            fresh = _masked_attributes(fresh_raw, mask)
            if highlight in fresh[target_row]:
                rows = fresh_rows
                break
            if time.monotonic() >= deadline:
                raise RunFailure(
                    f"menu highlight never reached {item!r} within "
                    f"{timeout}s; is it a selectable menu item?",
                    rule_id="screen.menu-unreachable")
            # The highlight is not on the target after all — a redraw
            # was still in flight, or the menu moved its own cursor.
            # Relocate the bar and steer again.
            candidates = [row for row in range(len(fresh))
                          if highlight in fresh[row]]
            attributes = fresh
            try:
                target_row = _match_menu_row(fresh_rows, item, exclude)
            except RunFailure:
                pass
            if len(candidates) == 1:
                current = candidates[0]
            time.sleep(0.1)
        selected = rows[target_row].strip()
        self.send_keys([["ret"]])
        return selected

    def _menu_baseline(self, deadline, quiet=5.0):
        """Wait for the menu to finish painting, then learn its noise.

        Returns (animation mask, text rows, masked attribute rows).
        Both halves are :mod:`screen_stability`'s: it says when the
        paint has finished, and the region it set aside as decoration
        *is* the mask — a clock, a countdown, a blinking indicator,
        which must be ignored when watching for the effect of a
        keypress or the screen would never settle.

        **The measure is continuous where the learned mask was a
        snapshot**, and that closes a gap rather than reproducing
        one: there is no learning phase to get wrong, decoration that
        begins mid-menu is absorbed within a few samples instead of
        never entering the mask at all, and a cell that changes *once*
        stays content — so a menu's own initial paint can no longer be
        mistaken for animation and blind the tracking to the very
        cells it must watch. A screen that never holds still is
        answered after the cap regardless, the mask having absorbed
        the churn; where nearly everything repaints the mask empties
        itself, which is the same bail-out this code made by hand.
        """
        end = min(deadline, time.monotonic() + quiet)
        monitor = screen_stability.ScreenStability()
        screen = self.screen()
        reading = monitor.observe(screen, now=time.monotonic())
        reads = 1
        while ((not reading.stable or reads < _BASELINE_READS)
               and time.monotonic() < end):
            time.sleep(_SETTLE_POLL)
            screen = self.screen()
            reading = monitor.observe(screen, now=time.monotonic())
            reads += 1
        mask = set(reading.animated)
        rows, raw = screen
        return mask, rows, _masked_attributes(raw, mask)

    def _follow_keypress(self, attributes, deadline, mask, key=None):
        """Track where a keypress moved the menu highlight.

        ``key`` is the cursor key just sent, which settles the
        two-item menus where confinement alone cannot tell the bar
        from the row it left (:func:`_relocated_bar`).

        Waits out the repaint the keypress caused and classifies the
        change. An unclassifiable difference (a half-drawn screen —
        the repaint paused mid-way, say to load translations from
        media) is never acted on: the screen is re-observed until the
        finished repaint shows where the bar landed, or nothing more
        changes. Sending more keys at a menu that is still repainting
        loses them to its type-ahead flush. Returns (responded, rows,
        attributes, moved row or None, that row's bar attribute).
        """
        observed = self._settled_screen(attributes, deadline, mask)
        if observed is None:
            return False, None, attributes, None, None
        while True:
            rows, changed = observed
            moved, attribute = _bar_move(
                attributes, changed, _DIRECTIONS.get(key))
            if moved is not None:
                # The bar's own token, not the dominant one among the
                # row's changed cells: on a recognized framebuffer the
                # latter is the bar's *blank* cells, whose token is the
                # backdrop's, and every later relocation by `highlight`
                # would match every row on screen.
                return True, rows, changed, moved, attribute
            attributes = changed
            observed = self._settled_screen(attributes, deadline, mask)
            if observed is None:
                return True, rows, attributes, None, None

    def _settled_screen(self, before, deadline, mask, wait=2.5):
        """Wait out the repaint following a keypress; None if none came.

        Two questions, and only the second is this module's. **Did
        anything change at all** is the menu's own — a keypress at the
        edge of a menu legitimately changes nothing, and the caller
        reads ``None`` as a dead key — so it stays here, asked against
        the mask. **Has the screen finished changing** is
        :mod:`screen_stability`'s, because returning at the first
        difference would hand back a half-drawn screen and slow menus
        repaint over many reads.

        The cap bounds only the wait for the first change; a screen
        that has started changing is followed until it settles or the
        deadline expires, when the last read wins.
        """
        first = min(deadline, time.monotonic() + wait)
        monitor = screen_stability.ScreenStability()
        seen = None
        while True:
            screen = self.screen()
            now = time.monotonic()
            reading = monitor.observe(screen, now=now)
            rows, raw = screen
            attributes = _masked_attributes(raw, mask)
            if attributes != before:
                seen = (rows, attributes)
                if reading.stable:
                    return seen
            if now >= (deadline if seen is not None else first):
                return seen
            time.sleep(_SETTLE_POLL)
