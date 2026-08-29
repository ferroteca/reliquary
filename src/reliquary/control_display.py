# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The agentless display console: the first real control plane.

A control plane combines an adapter's low-level carrier methods and
offers them to a platform workflow (see
planning/design/guest-communication.md). This one combines key
injection and reading text off the screen. It needs no cooperation
from inside the guest, and it is the default fallback for DOS.

**This module does not depend on QEMU.** It only relies on the
text-screen contract every backend adapter must satisfy: rows of
characters, plus one opaque attribute token per cell that can be
compared for equality but never interpreted. The menu-tracking code below only ever compares these
tokens to each other and counts how often they appear — it never
looks at what a token actually means — so it works whether the
tokens are VGA attribute bytes (true today) or, on a backend with no
native text screen, a hash of each cell's foreground/background
color pair. The same tracking code runs unchanged either way. Where
a backend cannot read text natively, the one shared recognizer that
produces those hashed tokens lives in :mod:`reliquary.text_recognize`
and is called from here — not duplicated in each adapter.

**This module does not decide whether a screen has stopped
changing.** That is :mod:`screen_stability`'s job, and this module is
just one of its callers, not a second copy of it. The menu-tracking
code here used to have its own version of that check — it hit the
problem of half-drawn screens first, and grew its own "wait for two
matching reads" logic and its own learned mask of self-animating
cells — before both were generalized into the shared
screen_stability check. What is still handled here is what
screen_stability does not cover: whether a keypress changed anything
at all, and which row the highlight moved to. That is classification,
not settling.
"""

import difflib
import time

from . import screen_stability
from .errors import RunFailure, StaticError

#: How often (in seconds) this module re-reads the screen while
#: waiting for it to settle. This is only a poll interval — whether
#: the screen actually counts as settled is decided by
#: :mod:`screen_stability`, not by this constant.
_SETTLE_POLL = 0.1

#: How many reads the baseline needs before its animation mask can be
#: trusted. This value is forced by the math below, not picked freely.
#: Telling that the screen has stopped changing takes only a couple of
#: reads, but telling that a *cell* changes on its own (a clock
#: ticking in a corner, say) takes more: after one change, there is no
#: way to tell a clock's tick apart from the effect of a keypress. If
#: the baseline stopped at the first settled frame, its mask would
#: come back empty, and the menu code would then mistake the clock's
#: own tick for something a keypress did. A cell only counts as
#: self-animating once it has changed `repeats` times, and seeing
#: `repeats` changes needs `repeats` reads plus the one read they are
#: each compared against — hence the `+ 1`.
_BASELINE_READS = screen_stability.DEFAULT_ANIMATION_REPEATS + 1

#: Which way each cursor key moves the selection bar (down = +1,
#: up = -1). Used only to break a tie between two equally good
#: candidate moves — a move is never required to match this.
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


def normalize_row(text):
    """Normalize one screen row the way text matching does (see
    script-spec, "Normalized text matching"): trim trailing padding
    and collapse every run of whitespace to a single space. The
    script runtime and the handle layer's ``wait_text`` both match
    text through this same function, which is what keeps ``rlq
    wait`` and a script's ``wait`` behaving identically (D116).
    """
    return " ".join(text.split())


def char_keys(character):
    """Map one character to the key names that must be pressed together
    to type it.

    These names are the key vocabulary every adapter must accept,
    which is QEMU's qcode set (D103) — that is why the tables above
    spell `spc` and `ret` rather than `space` and `enter`. Each
    adapter translates these names into its own backend's input
    events: on QEMU that is a direct pass-through, on VirtualBox a
    scancode lookup.

    This handles only characters. The language's `press` names are a
    separate, genuinely portable vocabulary
    (`script_validation.PORTABLE_KEY_NAMES`); `script_runner.resolve_key`
    converts those into this module's names before anything reaches
    the adapter.
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
    """Fold case and collapse whitespace, so menu-text comparison
    ignores both."""
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
    """Return `attributes` with each cell listed in `mask` replaced by
    None, so self-animating cells are ignored when comparing frames."""
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
    """Find the bar as the attribute token confined to one row that
    moved to a different row.

    A selection bar is an attribute token that appears on exactly one
    row, and that row changes when a cursor key is pressed. Looking
    for that — rather than for "the rarest attribute token on
    screen" — is what lets this keep working on a real framebuffer.

    Counting cells per row (the fallback approach in `_bar_move`
    below) assumes every cell in a row carries the same attribute.
    That is true for VGA bytes read straight out of text memory, but
    false for tokens recovered from pixels: a blank cell shows only a
    background color, so there is no way to tell its foreground from
    its background, and it ends up with a different token than a
    lettered cell right next to it. A highlighted row can then show
    *two* different tokens — the lettered cells carry the bar's own
    distinctive token, while the blank cells carry the same token as
    the ordinary background, which is the most common token on
    screen, the opposite of what a rarity check is looking for.

    Checking confinement to one row sidesteps that problem, because it
    only asks whether the token appears on any other row, not how many
    cells in the row carry it. It also survives a menu that rewrites
    every row on each keypress (a language chooser retranslating
    itself as the highlight moves): retranslating text changes which
    cells carry a token, but not the fact that the bar's lettered
    cells are still the only ones carrying theirs.

    Confinement alone can only settle the question above two menu
    items. With exactly one unhighlighted row, that row's own
    attribute is confined to one row too, so two attributes both look
    like equally good moves — in *opposite* directions. That is what
    `direction` then resolves: a selection bar moves the way the
    cursor key points. `direction` only breaks a tie between two
    candidates; it never rules a candidate out by itself, so a menu
    whose bar wraps from the bottom row to the top is left for
    `_bar_move`'s fallback reading rather than being classified
    wrongly here.

    Returns (row, that row's bar attribute), or (None, None) if no
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
    """Find the row the menu highlight moved to, comparing attributes
    before and after a keypress.

    Tries `_relocated_bar` first. If no attribute made an unambiguous
    move — the bar was erased rather than moved, or the screen
    repainted too broadly to tell — falls back to the frequency check
    below, which is how this module tracked the bar before
    `_relocated_bar` existed, and which still works on the
    uniform-attribute screens a text-memory scrape produces.

    The fallback: the rows whose attributes changed after a cursor
    keypress are the old and new highlighted rows, and of those, the
    new one is whichever changed row's cells now carry the rarest
    attribute on screen — the normal menu color covers many rows, the
    selection bar covers exactly one. Returns None when nothing
    changed, or when no changed row picked up a bar-like attribute (a
    row whose changed cells took on a widespread attribute is read as
    the bar having been erased, or as a partial repaint, not as a
    move).
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
    """Keyboard input and text-screen reading, built on one session.

    Shared by `Machine` methods and by interaction adapters that hold
    a session open across several exchanges. The session belongs to an
    adapter; this console only ever reaches the backend through the
    session's carrier methods.
    """

    def __init__(self, session):
        self._session = session
        #: Whether this console reads screen text by recognizing
        #: pixels (True) or reads it directly as already-resolved
        #: characters (False). Carried through from the adapter's
        #: session because callers waiting for the screen to settle
        #: use it to decide how often they can afford to re-read the
        #: screen, and a transcript wrapper around a session must pass
        #: this value through unchanged.
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

    def screen(self, font_banks=()):
        """Return the screen as (character rows, attribute rows).

        ``font_banks`` (F61) are fonts named by a script's `font`
        statement. They are tried before whatever fonts the session
        itself reads through. A session that reads text directly
        (QEMU's native text-memory read) never looks at pixels, so it
        simply ignores this argument.
        """
        return self._session.text_screen(font_banks)

    def framebuffer(self):
        """Return the plane's captured framebuffer as a Pillow image.

        This is the read path the landmark matcher uses (F65) —
        separate from the text-reading methods above, and never
        routed through them, because a landmark comparison works
        directly on pixels, so recognizing glyphs first would be
        wasted work. A plane whose screen carrier resolves characters
        rather than capturing pixels refuses this call by name;
        preflight has already rejected that machine's landmark
        conditions (`backends.BackendAdapter.capture_format`).
        """
        return self._session.framebuffer()

    def click(self, x, y, park, buttons=1):
        """Click at one framebuffer pixel, then park the cursor (F66).

        Composed here, never inside an adapter, for the same reason
        D103 gives for other input: a click is a move-and-press, a
        release at the same point, and a park move to ``park`` — three
        ``pointer_event`` calls over the one carrier method, so future
        growth (a drag, a multi-button chord) stays composition in
        this shared code instead of becoming adapter code. Resolving
        the park position is the caller's job
        (``landmarks.park_position``), since it depends on the screen
        a landmark pinned, not on anything this console knows.
        """
        self._session.pointer_event(x, y, buttons)
        self._session.pointer_event(x, y, 0)
        park_x, park_y = park
        self._session.pointer_event(park_x, park_y, 0)

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
        mask, rows, attributes = self._first_look(deadline, item, exclude)
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

    def _first_look(self, deadline, item, exclude):
        """Take one read before any settling, so a running countdown
        is not lost.

        A menu with a running countdown cannot safely be studied
        before acting on it. `_menu_baseline` below spends
        `_BASELINE_READS` reads learning which cells repaint on their
        own, and on a screenshot-based backend, where each read can
        take seconds, that is longer than a typical boot menu's
        countdown — this code would time out the very menu it is
        trying to steer. It is not just a matter of being slow: a
        countdown itself counts as self-animating, so those baseline
        reads would be spent learning the shape of the very timer
        that is about to run out.

        If the item is already on screen — which is normally true,
        since a script's `select` is usually reached right after a
        `wait` matched that same text — one read is enough to find it
        and press a key. Every boot menu tested so far cancels its
        countdown on any keypress, so this first, exploratory
        keypress buys back the time the baseline would have spent,
        and `_menu_baseline` learns the animation mask afterward, once
        the countdown has already stopped.

        Falls back to the full baseline when the item is not on
        screen yet. That is the case where settling is unavoidable
        anyway: the screen is still being drawn, and there is no
        countdown left to race.
        """
        rows, raw = self.screen()
        try:
            _match_menu_row(rows, item, exclude)
        except RunFailure:
            return self._menu_baseline(deadline)
        empty = frozenset()
        return empty, rows, _masked_attributes(raw, empty)

    def _menu_baseline(self, deadline, quiet=5.0):
        """Wait for the menu to finish painting, then read back which
        cells are animating on their own.

        Returns (animation mask, text rows, masked attribute rows).
        `screen_stability` is responsible for both halves: it decides
        when the screen has stopped changing, and the cells it set
        aside as decoration along the way become the mask — a clock,
        a countdown, a blinking indicator, anything that must be
        ignored when watching for the effect of a keypress, or the
        screen would never register as settled.

        `screen_stability` learns which cells are decoration
        continuously, as it reads, rather than in one separate
        learning phase the way this module used to. That closes a gap
        rather than just moving it: there is no separate learning
        phase to get wrong, decoration that only starts partway
        through the menu's lifetime is absorbed into the mask within a
        few more reads instead of never being recognized, and a cell
        that changes only once is not treated as decoration — so a
        menu's own initial paint can no longer be mistaken for
        animation and blind the tracking to cells it actually needs to
        watch. A screen that never holds fully still is still answered
        once the time cap is hit, using whatever mask has been learned
        by then; on a screen where nearly everything keeps repainting,
        the mask ends up empty, which is the same fallback this code
        used to apply by hand.
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

        ``key`` is the cursor key just sent. It resolves the two-item
        menu case where confinement alone can't tell the bar's new
        row apart from the row it left (see :func:`_relocated_bar`).

        Waits out the repaint the keypress caused, then classifies the
        change. A difference that can't yet be classified — a
        half-drawn screen, say because the repaint paused partway
        through to load translated text from disk — is never acted
        on: the screen is read again until either a finished repaint
        shows where the bar landed, or nothing more changes. Sending
        more keys while a menu is still repainting would just lose
        them when its type-ahead buffer gets flushed. Returns
        (responded, rows, attributes, moved row or None, that row's
        bar attribute).
        """
        observed = self._settled_screen(attributes, deadline, mask)
        if observed is None:
            return False, None, attributes, None, None
        while True:
            rows, changed = observed
            moved, attribute = _bar_move(
                attributes, changed, _DIRECTIONS.get(key))
            if moved is not None:
                # Use the bar's own token from `_bar_move`, not the
                # dominant token among the row's changed cells. On a
                # framebuffer read through pixel recognition, most of
                # a row's cells are blank, and a blank cell's token is
                # the same as the ordinary background's. If
                # `highlight` were set to that dominant token instead,
                # every later attempt to relocate the bar by searching
                # for `highlight` would match every row on screen.
                return True, rows, changed, moved, attribute
            attributes = changed
            observed = self._settled_screen(attributes, deadline, mask)
            if observed is None:
                return True, rows, attributes, None, None

    def _settled_screen(self, before, deadline, mask, wait=2.5):
        """Wait out the repaint following a keypress; return None if
        no repaint happened.

        This answers two separate questions, and only the second one
        belongs to :mod:`screen_stability`. Did anything change at
        all? That is this module's own question — a keypress at the
        edge of a menu can legitimately change nothing, and the
        caller reads a ``None`` result as a dead key — so it is
        checked here, against the mask. Has the screen finished
        changing? That is :mod:`screen_stability`'s question, because
        returning as soon as the first difference appears would hand
        back a half-drawn screen; slow menus can take several reads to
        finish repainting.

        The time cap only bounds the wait for the *first* change. Once
        the screen has started changing, it is followed until it
        settles or the deadline runs out, in which case the last read
        is used.
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
