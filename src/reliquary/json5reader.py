# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""JSON5 document reader.

Parses standard JSON5 (https://spec.json5.org), so an authored
blueprint follows one public spec instead of a dialect this project
invented (D102). Before parsing, comments are replaced with spaces
of the same length, so line and column numbers in error messages
still match the original file.

Non-finite numbers are rejected. JSON5 allows ``NaN``, ``Infinity``,
and ``-Infinity``, but Reliquary does not accept them — after
parsing, every blueprint value is ordinary JSON data.

Pass ``positions=True`` to record where each value came from in the
source file, so a blueprint error can point at a line and column
instead of just naming a field. This is off by default: a caller
that only wants the values pays nothing extra, and gets back plain
dicts and lists.

Recording positions is a second pass over the same space-blanked
text, not a second parser. ``json5.loads`` is still the only thing
that decides what the document means; the scan below only reads the
structure, which is all it needs to find positions. If the scan's
idea of the shape ever disagrees with what ``json5.loads`` produced,
positions for that part of the document are dropped rather than
guessed — an error without a location is what this module already
produced before positions existed, and a wrong location would be
worse than none.
"""

import math
import re

import json5

from .errors import StaticError

# Characters that end a scalar (a number or one of the three literals
# true/false/null). The scanner does not parse the scalar's value —
# it just steps over characters until one of these turns up.
_SCALAR_END = set(",]} \t\r\n")

# json5's ValueError message carries the line and column as plain text
# rather than as attributes: "<string>:12 Unexpected ... at column 34".
_ERROR_AT = re.compile(
    r":(\d+)\s+(.*?)\s+at column\s+(\d+)\s*$")

# A rough match for a JSON5 unquoted key (an ECMAScript IdentifierName):
# one start character, then zero or more continue characters. This is
# only used to find positions, not to decide what's valid — json5.loads
# already parsed the key — so an exotic Unicode key this pattern misses
# just means no position is recorded for it; the value is unaffected.
_IDENT_START = re.compile(r"[$_A-Za-z]")
_IDENT_CONTINUE = re.compile(r"[$_A-Za-z0-9]")

# The rule id used for every error this module raises: the document
# either isn't valid JSON5, or it breaks Reliquary's rule against
# non-finite numbers (D102).
_RULE = "blueprint.json5"


class PositionedDict(dict):
    """A JSON object that remembers where each of its members was written.

    ``positions`` maps each member's key to the ``(line, column)`` of
    the key itself, not its value — a blueprint error names a field,
    and pointing at the field's name is what makes the error easy to
    find in the source. ``position`` is the ``(line, column)`` of the
    object's own opening brace.

    Otherwise this behaves exactly like a plain ``dict``, so code that
    doesn't know about positions — the JSON schema validator,
    ``json.dumps``, an equality check — sees no difference.
    """

    __slots__ = ("positions", "position")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.positions = {}
        self.position = None


class PositionedList(list):
    """A JSON array that remembers where each element was written.

    ``positions`` maps each element's index to its ``(line, column)``;
    ``position`` is the ``(line, column)`` of the array's own opening
    bracket.
    """

    __slots__ = ("positions", "position")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.positions = {}
        self.position = None


def position_of(node, key):
    """The ``(line, column)`` of ``key`` within ``node``, or ``None``.

    Deliberately tolerant: a plain ``dict`` or ``list`` has no
    position data at all. That's what any caller who didn't pass
    ``positions=True`` gets back, and it's also what ``parse_document``
    receives when it's given an already-parsed value instead of a file
    path. In both cases this returns ``None`` instead of raising.
    """
    positions = getattr(node, "positions", None)
    if positions is None:
        return None
    return positions.get(key)


def position(node):
    """The ``(line, column)`` of ``node`` itself, or ``None``."""
    return getattr(node, "position", None)


def loads(s, *, positions=False):
    """Load a JSON5 string.

    A document that fails to parse is treated as a STATIC ERROR: it's
    the author's mistake, not Reliquary's, since the text alone
    determines whether it's valid JSON5. Without this, a ``ValueError``
    from the JSON5 library would escape as a bare exception and look
    like a bug in Reliquary itself (exit code 1). The library's error
    message already includes the line and column, so that text is kept
    verbatim when it's present.

    With ``positions=True``, objects and arrays come back as
    :class:`PositionedDict` and :class:`PositionedList` instead of
    plain ``dict``/``list``, each recording where its members were
    written in the source.
    """
    # Replace comments with spaces of the same length, so line and
    # column numbers stay correct for both the JSON5 parse below and
    # the position scan later. Quoted strings (both "..." and '...')
    # are left untouched, so a "//" inside a string isn't mistaken for
    # the start of a comment.
    s = _blank_comments(s)

    try:
        value = json5.loads(s, parse_constant=_refuse_nonfinite)
    except StaticError:
        raise
    except ValueError as error:
        match = _ERROR_AT.search(str(error))
        if match:
            lineno = int(match.group(1))
            colno = int(match.group(3))
            detail = match.group(2)
            failure = StaticError(
                f"line {lineno} column {colno}: {detail}",
                rule_id=_RULE)
            failure.lineno = lineno
            failure.colno = colno
        else:
            failure = StaticError(str(error), rule_id=_RULE)
        raise failure from error
    _reject_nonfinite(value)
    if not positions:
        return value
    # Both the JSON5 parse and this scan ran over the same
    # comment-blanked text, so the scan's line/column numbers match
    # the original file. That's the whole reason comments were
    # blanked instead of removed.
    return _attach(value, _Scanner(s).scan())


def load(fp, *, positions=False):
    """Load JSON5 from a file-like object."""
    return loads(fp.read(), positions=positions)


def _refuse_nonfinite(token):
    """``parse_constant`` hook: JSON5's non-finite tokens are refused."""
    raise StaticError(
        f"non-finite number {token} is not allowed "
        f"(blueprint values must be ordinary JSON data)",
        rule_id=_RULE)


def _reject_nonfinite(value):
    """Raise an error if a non-finite float made it into the value tree.

    ``_refuse_nonfinite`` (the ``parse_constant`` hook) already catches
    the JSON5 spellings like ``NaN``. This walk is a second check, in
    case a non-finite value reaches the tree some other way — a custom
    hook, or a future change to the json5 library — so the "no
    non-finite numbers" rule still holds even then.
    """
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        raise StaticError(
            "non-finite number is not allowed "
            "(blueprint values must be ordinary JSON data)",
            rule_id=_RULE)
    if isinstance(value, dict):
        for member in value.values():
            _reject_nonfinite(member)
    elif isinstance(value, list):
        for member in value:
            _reject_nonfinite(member)


def _blank_comments(text):
    """Replace ``//`` and ``/* */`` comments with same-length spaces."""
    pattern = re.compile(
        r'("(?:[^"\\]|\\.)*")|'      # Group 1: double-quoted strings
        r"('(?:[^'\\]|\\.)*')|"      # Group 2: single-quoted strings
        r'(//[^\n]*)|'               # Group 3: // comments
        r'(/\*.*?\*/)',              # Group 4: /* */ comments
        re.DOTALL
    )

    def replace(match):
        if match.group(1) is not None or match.group(2) is not None:
            return match.group(0)
        return ''.join(
            '\n' if char == '\n' else ' '
            for char in match.group(0))

    return pattern.sub(replace, text)


class _Node:
    """One value's position, plus its members' positions if it has any.

    ``keys`` holds the position of an object member's *key*, kept
    separate from that member's own ``position`` because they answer
    different questions: an error about a field should point at the
    field's name, while an error about the object that field holds
    should point at that object's opening brace.
    """

    __slots__ = ("position", "members", "keys")

    def __init__(self, position):
        self.position = position
        self.members = None
        self.keys = None


class _Scanner:
    """Walks the text once, recording where each value was written.

    It only reads the shape of the document, nothing else: strings are
    skipped in an escape-aware way, so a brace inside a string isn't
    mistaken for structure; unquoted keys are read as identifier runs;
    and every other scalar (numbers, ``true``/``false``/``null``) is
    just skipped up to the next delimiter. This scanner isn't
    responsible for catching malformed text — ``json5.loads`` has
    already accepted the document by the time this runs — so if it
    hits something it can't read, it just stops and returns the
    positions it found up to that point.
    """

    def __init__(self, text):
        self.text = text
        self.index = 0
        self.line = 1
        self.column = 1

    def scan(self):
        """The root value's node, or ``None`` if the text will not read."""
        try:
            self._space()
            return self._value()
        except _Unreadable:
            return None

    # -- position bookkeeping ------------------------------------------

    def _step(self, count=1):
        for _ in range(count):
            if self.index >= len(self.text):
                raise _Unreadable()
            if self.text[self.index] == "\n":
                self.line += 1
                self.column = 1
            else:
                self.column += 1
            self.index += 1

    def _here(self):
        return (self.line, self.column)

    def _peek(self):
        if self.index >= len(self.text):
            raise _Unreadable()
        return self.text[self.index]

    def _space(self):
        while self.index < len(self.text) and self.text[self.index].isspace():
            self._step()

    # -- structure ----------------------------------------------------

    def _value(self):
        char = self._peek()
        if char == "{":
            return self._object()
        if char == "[":
            return self._array()
        node = _Node(self._here())
        if char in "\"'":
            self._string()
        else:
            self._scalar()
        return node

    def _object(self):
        node = _Node(self._here())
        node.members = {}
        node.keys = {}
        self._step()                       # past '{'
        self._space()
        if self._peek() == "}":
            self._step()
            return node
        while True:
            self._space()
            if self._peek() == "}":        # trailing comma: stop, no more members
                break
            key_at = self._here()
            key = self._key()
            self._space()
            if self._peek() != ":":
                raise _Unreadable()
            self._step()
            self._space()
            # Last wins, as json5.loads does with a repeated key.
            node.members[key] = self._value()
            node.keys[key] = key_at
            self._space()
            if self._peek() != ",":
                break
            self._step()
        self._space()
        if self._peek() != "}":
            raise _Unreadable()
        self._step()
        return node

    def _array(self):
        node = _Node(self._here())
        node.members = {}
        self._step()                       # past '['
        self._space()
        if self._peek() == "]":
            self._step()
            return node
        index = 0
        while True:
            self._space()
            if self._peek() == "]":        # trailing comma: stop, no more elements
                break
            node.members[index] = self._value()
            index += 1
            self._space()
            if self._peek() != ",":
                break
            self._step()
        self._space()
        if self._peek() != "]":
            raise _Unreadable()
        self._step()
        return node

    def _key(self):
        """Step over a member key, returning its decoded name."""
        char = self._peek()
        if char in "\"'":
            return self._string()
        return self._identifier()

    def _identifier(self):
        """Step over an unquoted IdentifierName key."""
        start = self.index
        if not _IDENT_START.match(self._peek()):
            raise _Unreadable()
        self._step()
        while (self.index < len(self.text)
               and _IDENT_CONTINUE.match(self.text[self.index])):
            self._step()
        return self.text[start:self.index]

    def _string(self):
        """Step over a string literal, returning its decoded text."""
        quote = self._peek()
        start = self.index
        self._step()                       # past the opening quote
        while True:
            char = self._peek()
            if char == "\\":
                # JSON5 allows a line continuation (backslash followed
                # by a newline), which counts as one escape, so step
                # past both characters. Every other escape is also two
                # characters, so the same step works.
                self._step(2)
                continue
            self._step()
            if char == quote:
                break
        # Reuse json5.loads to decode the escapes in this slice, so a
        # key containing an escape still comes out identical to the
        # key json5.loads produced when it parsed the whole document.
        return json5.loads(self.text[start:self.index])

    def _scalar(self):
        """Step over a number or one of the three literals."""
        while self.index < len(self.text) and self._peek() not in _SCALAR_END:
            self._step()


class _Unreadable(Exception):
    """Raised when the scan hits something it can't read; positions stop there."""


def _attach(value, node):
    """Walk ``value`` and ``node`` together, rebuilding dicts and lists
    as ``PositionedDict``/``PositionedList``.

    If a subtree's shape doesn't match what the scanner found, that
    subtree keeps its plain ``dict``/``list`` instead. So a mismatch
    only means missing positions there — it never changes a value.
    """
    if node is None or node.members is None:
        return value
    if isinstance(value, dict):
        built = PositionedDict()
        built.position = node.position
        keys = node.keys or {}
        for key, member in value.items():
            built[key] = _attach(member, node.members.get(key))
            if key in keys:
                built.positions[key] = keys[key]
        return built
    if isinstance(value, list):
        built = PositionedList()
        built.position = node.position
        for index, member in enumerate(value):
            child = node.members.get(index)
            built.append(_attach(member, child))
            if child is not None:
                built.positions[index] = child.position
        return built
    return value
