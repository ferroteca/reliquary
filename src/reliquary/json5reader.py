# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""JSON5 document reader.

Parses the published JSON5 grammar (https://spec.json5.org) so an
authored blueprint has one external contract rather than a
project-defined dialect (D102). Comments are blanked to spaces of
the same length before the parse and the position scan, which keeps
line and column numbers exact.

**Non-finite numbers are refused.** JSON5 admits ``NaN``,
``Infinity`` and ``-Infinity``; Reliquary does not — blueprint
values remain ordinary JSON data after parsing.

**Positions are recorded on request** (``positions=True``), which is
what lets a blueprint diagnostic cite a line and column rather than a
field breadcrumb alone. They are off by default: a caller that only
wants values pays nothing, and the containers it gets back are the
plain ones.

The recording is a *second pass* over the same blanked text rather
than a replacement parser. ``json5.loads`` stays the one authority
on what a document means, and the scan below reads only the
structure, which is all a position needs. Where the two disagree
about shape the positions are dropped for that subtree rather than
guessed at: an unlocated diagnostic is what this module produced
before, and a *misplaced* caret is worse than none.
"""

import math
import re

import json5

from .errors import StaticError

# Structural characters and the value starts the scanner has to tell
# apart. Numbers and the three literals are skipped as opaque runs: the
# scan never interprets a scalar, so anything that is not a container,
# a string or a delimiter is one token to step over.
_SCALAR_END = set(",]} \t\r\n")

# json5's ValueError message carries line and column in prose rather
# than as attributes: "<string>:12 Unexpected ... at column 34".
_ERROR_AT = re.compile(
    r":(\d+)\s+(.*?)\s+at column\s+(\d+)\s*$")

# ECMAScript IdentifierName, approximated for the position scan: a
# start character, then continue characters. The scan never decides
# meaning — json5.loads already did — so an exotic Unicode key that
# this misses costs positions on that subtree, never a wrong value.
_IDENT_START = re.compile(r"[$_A-Za-z]")
_IDENT_CONTINUE = re.compile(r"[$_A-Za-z0-9]")

# One rule id for every refusal this module raises: the document is
# not legal JSON5 under Reliquary's value-model constraint (D102).
_RULE = "blueprint.json5"


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
    """Load a JSON5 string.

    A document that does not parse is a STATIC ERROR: the text alone
    settles it, and the caller wrote the text. ``ValueError`` from
    the JSON5 reader would otherwise escape as a bare exception and
    report as reliquary's own fault (exit 1) rather than the author's
    mistake. Its message carries the line and column, so it is kept
    verbatim when present.

    With ``positions``, objects and arrays come back as
    :class:`PositionedDict` and :class:`PositionedList`, each carrying
    the source position of its members.
    """
    # Replace comments with spaces of the same length so line/column
    # numbers stay exact for both the JSON5 parse and the position
    # scan. Strings — double- and single-quoted — are left alone so a
    # "//" inside one is not mistaken for a comment.
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
    # Both passes ran over the same blanked text, so the scan's offsets
    # are the original file's: that is what comment blanking bought.
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
    """Refuse any non-finite float that reached the value tree.

    ``parse_constant`` catches the JSON5 spellings; this walk is the
    belt for anything that arrived some other way (a custom hook, a
    future library change) so the invariant stays fail-closed.
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
    structure, unquoted keys are read as identifier runs, and every
    other scalar is skipped as an opaque run up to the next delimiter.
    Malformed text is not this pass's business -- ``json5.loads`` has
    already accepted the document by the time it runs -- so it stops
    at the first thing it cannot read and reports the positions it did
    find.
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
            if self._peek() == "}":        # a trailing comma, blanked
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
            if self._peek() == "]":        # a trailing comma, blanked
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
                # JSON5 allows a line continuation: backslash + newline
                # is one escape, so step both. Any other escape is two
                # characters the same way.
                self._step(2)
                continue
            self._step()
            if char == quote:
                break
        # json5 decodes the escapes, so a key with one still matches
        # the key json5.loads produced. Use it on the slice alone.
        return json5.loads(self.text[start:self.index])

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
