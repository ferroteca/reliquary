# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""JSON with Comments (JSONC) reader.

Implements RFC 8259 + // and /* */ comments + trailing commas.
Comments are replaced by spaces to preserve line and column numbers.

**Positions are recorded on request** (``positions=True``), which is
what lets a blueprint diagnostic cite a line and column rather than a
field breadcrumb alone. They are off by default: a caller that only
wants values pays nothing, and the containers it gets back are the
plain ones.

The recording is a *second pass* over the same text rather than a
replacement parser. ``json.loads`` stays the one authority on what a
document means -- numbers, escapes, duplicate keys and the decode
failure's own message and position -- and the scan below reads only
the structure, which is all a position needs. Where the two disagree
about shape the positions are dropped for that subtree rather than
guessed at: an unlocated diagnostic is what this module produced
before, and a *misplaced* caret is worse than none.
"""

import json
import re

from .errors import StaticError

# Structural characters and the value starts the scanner has to tell
# apart. Numbers and the three literals are skipped as opaque runs: the
# scan never interprets a scalar, so anything that is not a container,
# a string or a delimiter is one token to step over.
_SCALAR_END = set(",]} \t\r\n")


class PositionedDict(dict):
    """A JSON object that remembers where each of its members was written.

    ``positions`` maps a member's key to the ``(line, column)`` of that
    key's own token -- the field name, not its value, because a
    blueprint diagnostic names a field and a caret under the name is
    what reads. ``position`` is the object's own opening brace.

    It is a ``dict`` in every other respect, so a consumer that does not
    know about positions -- the JSON schema validator, ``json.dumps``,
    an equality assertion -- sees no difference.
    """

    __slots__ = ("positions", "position")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.positions = {}
        self.position = None


class PositionedList(list):
    """A JSON array that remembers where each element was written.

    ``positions`` maps an element's index to its ``(line, column)``;
    ``position`` is the array's own opening bracket.
    """

    __slots__ = ("positions", "position")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.positions = {}
        self.position = None


def position_of(node, key):
    """The ``(line, column)`` of ``key`` within ``node``, or ``None``.

    Tolerant by design: a plain ``dict`` or ``list`` -- what every
    caller that did not ask for positions holds, and what the public
    ``parse_document`` is handed when someone passes a value rather
    than a path -- has none, and answers ``None`` rather than raising.
    """
    positions = getattr(node, "positions", None)
    if positions is None:
        return None
    return positions.get(key)


def position(node):
    """The ``(line, column)`` of ``node`` itself, or ``None``."""
    return getattr(node, "position", None)


def loads(s, *, positions=False):
    """Load JSONC string.

    A document that does not parse is a STATIC ERROR: the text alone
    settles it, and the caller wrote the text. ``JSONDecodeError``
    would otherwise escape as a bare ``ValueError`` and report as
    reliquary's own fault (exit 1) rather than the author's mistake.
    Its message carries the line and column, so it is kept verbatim.

    With ``positions``, objects and arrays come back as
    :class:`PositionedDict` and :class:`PositionedList`, each carrying
    the source position of its members.
    """
    # 1. Replace comments with spaces of the same length
    # This keeps line/column numbers exact for the JSON parser if it reports them.
    # Note: we must be careful not to replace comments inside strings.

    # Regex for JSON strings, // comments, and /* */ comments
    # Strings: " ( [^"\\] | \\. )* "
    # // comments: // [^\n]*
    # /* */ comments: /\* .*? \*/
    pattern = re.compile(
        r'("(?:[^"\\]|\\.)*")|'      # Group 1: Strings
        r'(//[^\n]*)|'               # Group 2: // comments
        r'(/\*.*?\*/)',              # Group 3: /* */ comments
        re.DOTALL
    )

    def replace(match):
        if match.group(1):
            return match.group(1) # Keep strings as is
        return ''.join(
            '\n' if char == '\n' else ' '
            for char in match.group(0))

    s = pattern.sub(replace, s)

    # 2. Remove trailing commas
    # [1, 2,] -> [1, 2]
    # {"a": 1,} -> {"a": 1}
    # We look for a comma followed by whitespace and then ] or }
    # Again, avoiding commas inside strings.

    # This is a bit trickier with regex alone to be 100% correct regarding strings,
    # but since we already know where the strings are from the previous pass,
    # we can do it safely.

    # Re-using the pattern to find strings and trailing commas
    trailing_comma_pattern = re.compile(
        r'("(?:[^"\\]|\\.)*")|'      # Group 1: Strings
        r'(,\s*([\]\}]))'            # Group 2: Trailing comma, Group 3: closing char
    )

    def replace_comma(match):
        if match.group(1):
            return match.group(1)
        else:
            return ' ' + match.group(3) # Replace comma with space, keep closing char

    s = trailing_comma_pattern.sub(replace_comma, s)

    try:
        value = json.loads(s)
    except json.JSONDecodeError as error:
        failure = StaticError(str(error))
        # Comment stripping preserves line and column on purpose, so
        # the position survives the class change rather than being
        # readable only out of the message. A properly located
        # blueprint diagnostic -- line, column and a rule id, as
        # ScriptParseError already carries -- is document.py's, built
        # on the positions this module records below (D70).
        failure.lineno = error.lineno
        failure.colno = error.colno
        raise failure from error
    if not positions:
        return value
    # Both passes ran over the same blanked text, so the scan's offsets
    # are the original file's: that is what comment blanking bought.
    return _attach(value, _Scanner(s).scan())


def load(fp, *, positions=False):
    """Load JSONC from a file-like object."""
    return loads(fp.read(), positions=positions)


class _Node:
    """One value's position, and its members' if it has any.

    ``keys`` holds an object member's *key* position, kept apart from
    the member's own ``position`` because the two answer different
    questions: a diagnostic about a field wants the name it was written
    under, and one about the object that field holds wants its brace.
    """

    __slots__ = ("position", "members", "keys")

    def __init__(self, position):
        self.position = position
        self.members = None
        self.keys = None


class _Scanner:
    """A structure-only walk recording where each value was written.

    It reads the shape and nothing else: strings are skipped
    escape-aware so a brace inside one cannot be mistaken for
    structure, and every other scalar is skipped as an opaque run up to
    the next delimiter. Malformed text is not this pass's business --
    ``json.loads`` has already accepted the document by the time it
    runs -- so it stops at the first thing it cannot read and reports
    the positions it did find.
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
        if char == '"':
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
            if self._peek() != '"':    # a trailing comma, blanked to space
                break
            key_at = self._here()
            key = self._string()
            self._space()
            if self._peek() != ":":
                raise _Unreadable()
            self._step()
            self._space()
            # Last wins, as json.loads does with a repeated key.
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
            if self._peek() == "]":    # a trailing comma, blanked to space
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

    def _string(self):
        """Step over a string literal, returning its decoded text."""
        start = self.index
        self._step()                       # past the opening quote
        while True:
            char = self._peek()
            if char == "\\":
                self._step(2)
                continue
            self._step()
            if char == '"':
                break
        # json decodes the escapes, so a key with one still matches the
        # key json.loads produced.
        return json.loads(self.text[start:self.index])

    def _scalar(self):
        """Step over a number or one of the three literals."""
        while self.index < len(self.text) and self._peek() not in _SCALAR_END:
            self._step()


class _Unreadable(Exception):
    """The scan met something it could not read; positions stop here."""


def _attach(value, node):
    """Rebuild ``value``'s containers as positioned ones, in lockstep.

    A subtree whose shape does not match the scan keeps its plain
    containers, so a disagreement costs positions and never truth.
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
