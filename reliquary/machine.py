# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Generic interaction with and diagnostics for a running QEMU machine."""

import contextlib
import dataclasses
import difflib
import os
import re
import sys
import time

from PIL import Image
from qemu.qmp import ExecuteError

from .errors import RunFailure, StaticError
from .home import effective_home
from .lifecycle import qmp_session


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


def screenshot(name="screen", port=None, home=None, directory=None):
    """Save the guest display; `directory` overrides the destination.

    The QMP session identity always resolves through `home` — a
    caller collecting images somewhere else (a script run record)
    still verifies the machine it talks to.
    """
    name = validate_screenshot_name(name)
    screenshots = directory or os.path.join(
        effective_home(home), "screenshots")
    os.makedirs(screenshots, exist_ok=True)
    ppm = os.path.join(screenshots, f"{name}.ppm")
    with qmp_session(port, home) as qmp:
        try:
            png = os.path.join(screenshots, f"{name}.png")
            qmp.cmd("screendump", filename=png.replace("\\", "/"),
                    format="png")
            print(f"rlq: saved {png}", file=sys.stderr)
            return
        except ExecuteError:
            pass
        qmp.cmd("screendump", filename=ppm.replace("\\", "/"))
    time.sleep(0.3)
    png = os.path.join(screenshots, f"{name}.png")
    try:
        with Image.open(ppm) as image:
            image.save(png)
    except OSError as error:
        raise RunFailure(
            f"unexpected screendump format in {ppm}: {error}",
            rule_id="screen.screendump-unreadable") from error
    os.remove(ppm)
    print(f"rlq: saved {png}", file=sys.stderr)


def vga_screen(qmp):
    """Return the 80x25 VGA text screen as (text rows, attribute rows).

    Text rows are right-stripped strings; attribute rows keep the raw
    VGA attribute byte of all 80 cells, so callers can observe color
    effects such as a menu selection highlight.
    """
    raw = qmp.hmp("xp /4000bx 0xb8000")
    data = []
    for line in raw.splitlines():
        if not re.match(r"^[0-9a-f]+:", line):
            continue
        data.extend(int(token, 16) for token in line.split()[1:])
    rows = []
    attributes = []
    for row in range(25):
        cells = data[row * 160:(row + 1) * 160]
        rows.append("".join(
            chr(byte) if 32 <= byte < 127 else " "
            for byte in cells[0::2]).rstrip())
        attributes.append(cells[1::2])
    return rows, attributes


def vga_text(qmp):
    """Return the guest's 80x25 VGA text screen over an open session."""
    return vga_screen(qmp)[0]


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
    """Map one character to a simultaneous QEMU qcode combination."""
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


def _animation_cells(samples):
    """Return the (row, column) cells that changed with no keypress.

    Samples are (text rows, attribute rows) screens read back to
    back. Any cell whose character or attribute differs between
    reads is repainting on its own — a clock, a countdown, a
    blinking indicator — and must be ignored when watching for the
    effect of a keypress, or the screen would never settle.
    """
    mask = set()
    base_rows, base_attributes = samples[0]
    base_text = [row.ljust(80) for row in base_rows]
    for rows, attributes in samples[1:]:
        text = [row.ljust(80) for row in rows]
        for row in range(len(attributes)):
            if (text[row] == base_text[row]
                    and attributes[row] == base_attributes[row]):
                continue
            for column in range(80):
                if (text[row][column] != base_text[row][column]
                        or attributes[row][column]
                        != base_attributes[row][column]):
                    mask.add((row, column))
    return mask


def _masked_attributes(attributes, mask):
    """Attribute rows with self-animating cells nulled for comparison."""
    view = [list(row) for row in attributes]
    for row, column in mask:
        view[row][column] = None
    return view


def _masked_text(rows, mask):
    """Text rows with self-animating cells blanked for comparison."""
    padded = [row.ljust(80) for row in rows]
    if not mask:
        return padded
    view = [list(row) for row in padded]
    for row, column in mask:
        view[row][column] = " "
    return ["".join(characters) for characters in view]


def _changed_attribute(before, attributes, row):
    """Dominant attribute among the row's cells that just changed."""
    counts = {}
    for old, new in zip(before[row], attributes[row]):
        if old != new:
            counts[new] = counts.get(new, 0) + 1
    return max(counts, key=counts.get) if counts else None


def _cursor_row(before, attributes):
    """Locate the menu highlight from an observed attribute change.

    The rows whose attributes changed after a cursor keypress are the
    old and new cursor positions. Of those, the newly highlighted row
    is the one whose changed cells now carry the rarest attribute on
    screen: the normal menu color covers many rows, the selection bar
    exactly one. Returns None when nothing changed, or when no
    changed row gained a bar-like attribute — the bar covers at most
    a couple of rows' worth of cells, so a row whose changed cells
    took on a widespread attribute is a bar being erased or a
    partial repaint, not the new position.
    """
    changed = [row for row in range(len(attributes))
               if attributes[row] != before[row]]
    if not changed:
        return None
    frequency = {}
    for row_attributes in attributes:
        for attribute in row_attributes:
            if attribute is not None:
                frequency[attribute] = frequency.get(attribute, 0) + 1

    def rarity(row):
        return frequency[_changed_attribute(before, attributes, row)]

    best = min(changed, key=rarity)
    if rarity(best) > 160:
        return None
    return best


class _DisplayConsole:
    """Keyboard input and VGA-text composition over an open session.

    Shared by `Machine` methods and interaction adapters that hold a
    session across several exchanges.
    """

    def __init__(self, qmp):
        self._qmp = qmp

    def send_keys(self, combos, delay=0.06):
        """Send a list of qcode combinations to the guest."""
        for combo in combos:
            self._qmp.cmd(
                "send-key",
                keys=[{"type": "qcode", "data": key}
                      for key in combo])
            time.sleep(delay)

    def send_text(self, text, enter=True):
        combos = [char_keys(character) for character in text]
        if enter:
            combos.append(["ret"])
        self.send_keys(combos)

    def screen_text(self):
        """Return the guest's 80x25 VGA text screen."""
        return vga_text(self._qmp)

    def screen(self):
        """Return the VGA screen as (text rows, attribute rows)."""
        return vga_screen(self._qmp)

    def cursor_menu_select(self, item, timeout=30, exclude=()):
        """Steer a cursor-key menu onto a matching item and press ENTER.

        Presses up/down and observes the VGA attribute bytes to follow
        the selection highlight, so the choice is confirmed by what the
        guest displays rather than by counting keystrokes. The screen
        is sampled before the first keypress so self-animating cells
        (clocks, countdowns, blinking indicators) are ignored, and
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
                self._follow_keypress(attributes, deadline, mask))
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
                    self._follow_keypress(attributes, deadline, mask))
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
        The screen must hold still for two consecutive reads before
        the animation cells are sampled: sampling straight away would
        mistake a menu's own initial paint for animation and blind
        the highlight tracking to the very cells it must watch. A
        screen that never holds still (real animation) is sampled
        after the cap regardless — the mask absorbs those cells.
        """
        end = min(deadline, time.monotonic() + quiet)
        previous = None
        while time.monotonic() < end:
            screen = self.screen()
            if previous is not None and screen == previous:
                break
            previous = screen
            time.sleep(0.1)
        samples = [self.screen() if previous is None else previous]
        for _ in range(2):
            time.sleep(0.15)
            samples.append(self.screen())
        mask = _animation_cells(samples)
        if len(mask) * 2 > 25 * 80:
            # Nearly everything repaints; masking it all would blind
            # highlight tracking entirely, so track unmasked instead.
            mask = set()
        rows, raw = samples[-1]
        return mask, rows, _masked_attributes(raw, mask)

    def _follow_keypress(self, attributes, deadline, mask):
        """Track where a keypress moved the menu highlight.

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
            moved = _cursor_row(attributes, changed)
            if moved is not None:
                attribute = _changed_attribute(
                    attributes, changed, moved)
                return True, rows, changed, moved, attribute
            attributes = changed
            observed = self._settled_screen(attributes, deadline, mask)
            if observed is None:
                return True, rows, attributes, None, None

    def _settled_screen(self, before, deadline, mask,
                        wait=2.5, hold=2):
        """Wait out the repaint following a keypress; None if none came.

        Polls until the non-masked attributes change from `before`
        and the screen then holds steady for `hold` further reads.
        Slow menus repaint over many reads; returning at the first
        difference would hand back a half-drawn screen. The cap only
        bounds the wait for the first change; a screen that has
        started changing is followed until it settles or the deadline
        expires (when the last read wins). With no change at all,
        returns None.
        """
        first = min(deadline, time.monotonic() + wait)
        previous = None
        steady = 0
        while True:
            rows, raw = self.screen()
            attributes = _masked_attributes(raw, mask)
            view = (_masked_text(rows, mask), attributes)
            if attributes != before:
                if previous is not None and view == previous[0]:
                    steady += 1
                    if steady >= hold:
                        return previous[1], previous[2]
                else:
                    previous = (view, rows, attributes)
                    steady = 0
            if time.monotonic() >= (deadline if previous is not None
                                    else first):
                if previous is not None:
                    return previous[1], previous[2]
                return None
            time.sleep(0.1)


@dataclasses.dataclass(frozen=True)
class Machine:
    """A running, reliquary-owned VM passed to generic remote tasks."""

    port: "int | None" = None
    home: "str | None" = None
    deadline: "float | None" = None

    @contextlib.contextmanager
    def qmp(self):
        """Yield an identity-verified QMP session for this machine."""
        with qmp_session(self.port, self.home) as qmp:
            yield qmp

    def screenshot(self, name="screen"):
        return screenshot(name, self.port, self.home)

    def send_keys(self, combos, delay=0.06):
        """Send a list of qcode combinations to the guest."""
        with self.qmp() as qmp:
            return _DisplayConsole(qmp).send_keys(combos, delay)

    def send_text(self, text, enter=True):
        """Type text on the guest keyboard, with Enter by default."""
        with self.qmp() as qmp:
            return _DisplayConsole(qmp).send_text(text, enter)

    def cursor_menu_select(self, item, timeout=30, exclude=()):
        """Select a matching item in a cursor-key menu and press ENTER."""
        with self.qmp() as qmp:
            return _DisplayConsole(qmp).cursor_menu_select(
                item, timeout, exclude)

    def screen_text(self):
        """Return the guest's 80x25 VGA text screen."""
        with self.qmp() as qmp:
            return vga_text(qmp)

    def wait_text(self, pattern, timeout=60):
        """Wait until the VGA text screen matches a regular expression.

        Returns the matching screen as one newline-joined string.
        """
        with self.qmp() as qmp:
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                screen = "\n".join(vga_text(qmp))
                if re.search(pattern, screen):
                    return screen
                time.sleep(2)
        raise RunFailure(
            f"timed out after {timeout}s waiting for screen to match: "
            f"{pattern}", rule_id="screen.no-match")


def send_keys(combos, port=None, delay=0.06, home=None):
    """Send a list of qcode combinations to the guest."""
    return Machine(port, home).send_keys(combos, delay)


def send_text(text, port=None, enter=True, home=None):
    """Type text on the guest keyboard, with Enter by default."""
    return Machine(port, home).send_text(text, enter)


def cursor_menu_select(item, timeout=30, exclude=(), port=None,
                       home=None):
    """Select a matching item in a cursor-key menu and press ENTER."""
    return Machine(port, home).cursor_menu_select(item, timeout, exclude)


def screen_text(port=None, home=None):
    """Return the guest's 80x25 VGA text screen."""
    return Machine(port, home).screen_text()


def wait_text(pattern, timeout=60, port=None, home=None):
    """Wait until the VGA text screen matches a regular expression."""
    return Machine(port, home).wait_text(pattern, timeout)
