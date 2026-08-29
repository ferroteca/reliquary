# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The structural node layer of the reliquary script language.

Every line of a script is one node::

    node = name , { argument } , { modifier } , [ block ]

This module handles the lexical rules and that shape only -- what a
line *looks like*. What node names exist, and what arguments and
modifiers each one accepts, plus the V-numbered static rules, are
handled by the layer above, in :mod:`reliquary.script`. The
milestone-5 ``content`` declaration has one structural extension: a
trailing ``\"\"\"`` opens a raw body that is skipped over until its
closing ``\"\"\"`` line.

Source of truth: docs/spec/script-spec.md, "Lexical rules" and "Core
grammar".
"""

import re
import types
from dataclasses import dataclass, field
from typing import Mapping, Optional, Tuple

from .errors import InternalError, StaticError

_DURATION = re.compile(r"(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)(?:ms|s|m|h)$")
# A bare number with no unit -- that's what a proportion looks like.
# It's allowed only after a name that takes a proportion, so
# "durations carry a unit" stays true everywhere else a duration was
# expected.
_FRACTION = re.compile(r"(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)$")
#: The names whose value is a proportion rather than a duration.
FRACTION_VALUED = frozenset({"stability"})
_NAME = re.compile(r"[A-Za-z][A-Za-z0-9._-]*$")
# A media name is allowed to start with a digit; a property key is
# not. The `@` sigil already marks a media reference as a media
# name, but a property key also appears bare, with no sigil, at its
# `property` declaration, where a leading digit would instead lex as
# a duration (D24).
_MEDIA_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*$")
# A token ends at whitespace, a brace, a comment, or the line
# terminator; strings and regexes end at their closing delimiter.
_DELIMITERS = " \t{}#"

# Every node name: each header, declaration, and verb. This list
# lives here instead of in the parser because two layers both need
# it and neither can import the other: the lexer treats these words
# as keywords when they appear in node-name position, and validation
# separately rejects them as identifiers everywhere else (V5).
#
# The two jobs are kept separate on purpose. A word counts as a
# keyword only where a node name is allowed to start, so `enter` is
# a verb at the start of a line but an ordinary key name after
# `press`. Which specific node names and key names are valid is
# validation's job, not the grammar's (script-spec.md, "Grammar").
# What the grammar by itself can't express is the *reservation* --
# that `phase enter` can't be used to name a phase called "enter" --
# because if the grammar rejected that identifier itself, it would
# show up as a generic "unexpected token" error instead of a named
# rule.
KEYWORDS = (
    "description", "platform", "machine", "entry", "timeout", "deadline",
    "pacing", "stability",
    "property", "http", "content", "phase", "with", "wait", "on", "always",
    "goto", "finish", "enter", "type", "press", "select", "click",
    "screenshot", "insert", "eject", "set-boot", "set", "start", "stop",
    "font",
)


#: Maps every error id the script parser stack can raise to the
#: V-numbered rule it enforces.
#:
#: Several ids can map to the same V-number. For example, V7 is one
#: rule, and ``obs.two-channels`` is just one of six different ids
#: raised for violations of it.
#:
#: This map only covers ids raised by this module, the grammar
#: transformer, and validation. An id raised elsewhere -- such as
#: ``media.unknown`` from resolution or ``machine.slot-not-declared``
#: from preflight -- has no V-number and isn't listed here. An id in
#: this module's scope that isn't tied to any V-number still gets an
#: entry, mapped to ``None``, so every id you look up here gets an
#: answer.
#:
#: This mapping is kept here, not just in docs/spec/script-spec.md,
#: so code that needs to look up the rule for an id doesn't have to
#: parse the spec's prose. A test checks that this map and the
#: spec's rule list agree.
RULE_OF = {
    "node.duplicate-modifier": "V4",
    "node.modifier-not-allowed": "V2",
    "node.timing-placement": "V2",
    "scope.head-arguments": "V2",
    "scope.wraps-the-wrong-unit": "V2",
    "scope.unknown-head": "V14",
    "scope.doubled-target": "V9",
    "flow.mixed-shapes": "V10",
    "drive.boot-duplicate": "V5",
    "name.reserved-node": "V5",
    "name.duplicate-phase": "V5",
    "name.duplicate-property": "V5",
    "name.property-is-a-kind": "V5",
    "name.property-reserved-namespace": "V5",
    "name.variable-reserved-namespace": "V5",
    "time.non-positive": "V5",
    "prop.secret-default": "V5",
    "prop.dead-default": "V5",
    "prop.undefined-reference": "V6",
    "prop.secret-reference": "V6",
    "prop.derivation-cycle": "V6",
    "prop.http-without-block": "V6",
    "obs.missing-condition": "V7",
    "obs.two-channels": "V7",
    "obs.not-a-condition": "V7",
    "obs.unknown-channel": "V7",
    "obs.screen-named": "V7",
    "obs.wrong-kind": "V7",
    "wait.branching-condition": "V8",
    "wait.branching-in-handler": "V8",
    "wait.too-few-handlers": "V8",
    "handler.mixed-phase": "V9",
    "handler.on-outside-branching-wait": "V9",
    "handler.always-outside-reactive-phase": "V9",
    "flow.entry-in-linear": "V3",
    "flow.entry-missing": "V3",
    "flow.entry-undeclared": "V10",
    "flow.transfer-in-linear": "V10",
    "flow.goto-undeclared": "V10",
    "flow.unreachable-statement": "V11",
    "flow.phase-falls-through": "V11",
    "flow.cycle-without-deadline": "V12",
    "obs.empty-pattern": "V13",
    "obs.uncompilable-regex": "V13",
    "key.not-portable": "V14",
    # This is deliberately the *runtime* id, left unchanged here: the
    # static pass and the machine layer both enforce the same rule,
    # so code that switches on this id never needs to know which
    # layer caught the violation. V17 only changes when the
    # violation is caught, not what it means.
    "machine.must-be-stopped": "V17",
}

#: The lexical and structural rule ids. V1 means "syntax is well
#: formed: no unknown node names, no unbalanced blocks," and the
#: lexer and the grammar enforce it between them, so these are the
#: diagnostics for V1. A ``lex.`` id is something the tokenizer
#: rejects while reading characters; a ``syn.`` id is about line,
#: block, and document shape.
RULE_OF.update({
    "lex.unclosed-reference": "V1",
    "lex.invalid-reference": "V1",
    "lex.unterminated-string": "V1",
    "lex.unterminated-regex": "V1",
    "lex.unterminated-content": "V1",
    "lex.invalid-token": "V1",
    "lex.invalid-duration": "V1",
    "lex.spaced-modifier": "V1",
    "lex.modifier-missing-value": "V1",
    "syn.brace-not-alone": "V1",
    "syn.unmatched-close": "V1",
    "syn.unclosed-block": "V1",
    "syn.open-brace-position": "V1",
    "syn.expected-node-name": "V1",
    "syn.argument-after-modifier": "V1",
    "syn.unexpected-token": "V1",
    "syn.unexpected-end": "V1",
    "syn.duplicate-header": "V3",
    "node.modifier-not-a-duration": "V2",
    "node.modifier-not-a-fraction": "V2",
    "node.modifier-not-a-string": "V2",
    "prop.unknown-kind": "V5",
})

#: Ids this stack raises that no V-number covers. Mapped to None.
#:
#: An id lands here for one of two reasons. The `http` declaration's
#: rules are static, legality-tier rules just like the others, but
#: they simply predate the V-numbering scheme. The last two ids
#: aren't legality rules at all -- they cover a script source that
#: isn't text, and a script file that doesn't exist -- and the
#: parser reports them because it's the layer that checked. Either
#: way, code that asks what rule an id enforces gets an honest None
#: back, instead of a V-number invented just to fill in the map.
RULE_OF.update({
    "http.port-not-a-number": "V16",
    "http.indent-not-a-mode": "V16",
    "http.content-two-bodies": "V16",
    "http.content-no-body": "V16",
    "http.indent-on-file-body": "V16",
    "http.from-reference": "V16",
    "http.from-not-relative": "V16",
    "http.from-traversal": "V16",
    "http.from-missing": "V16",
    "http.from-unreadable": "V16",
    "http.duplicate-declaration": "V16",
    "http.no-content": "V16",
    "http.duplicate-content-name": "V16",
    "http.duplicate-content-path": "V16",
    "http.path-not-absolute": "V16",
    "http.path-traversal": "V16",
    "http.empty-body": "V16",
    "http.unknown-action": "V16",
    "http.start-without-content": "V16",
    "http.undeclared-content": "V16",
    "http.stop-takes-nothing": "V16",
    "http.port-out-of-range": "V16",
    "http.port-range-inverted": "V16",
    "http.reference-in-path": "V16",
    "value.not-a-string": None,
    "script.unknown": None,
})


class ScriptParseError(StaticError):
    """A script syntax or static-validation error, with the source line it happened on.

    This is the legality tier of the error taxonomy: it is decided
    from the script text alone, so it is a STATIC ERROR and exits
    with code ``2``.

    ``rule_id`` is the stable dotted identifier naming the rule that
    diagnostic enforces (docs/spec/script-spec.md, "Error classes
    and exit codes") -- things like ``obs.two-channels`` and its
    siblings, all sharing one namespace across every error class.
    It is a *field* on the error, not text baked into the message,
    so code can switch on it without parsing the message text, and
    the id index in the beta docs can be generated instead of kept
    up to date by hand. When the error is rendered, the id is
    appended in parentheses, which is where V-numbers used to be
    shown.

    These ids are more specific than the V-numbered rules they
    enforce: V7 is one rule, and ``obs.two-channels`` is one of
    several different diagnostics raised for violations of it. The
    spec's rule list is what defines that mapping, and a test checks
    that the two stay in sync.

    ``rule_id`` is inherited from :class:`~reliquary.errors.ReliquaryError`,
    where it lives because the spec keeps every id in one namespace
    across all the error classes. Every tier of this error surface
    carries a rule_id now, including preflight and runtime errors;
    other error surfaces in the codebase do not yet, and the
    conformance test corpora measure how much of that work remains,
    rather than that being estimated by hand.
    """

    def __init__(self, line, message, column=1, rule_id=None):
        super().__init__(message)
        self.line = line
        self.column = column
        self.message = message
        self.rule_id = rule_id
        self.path = None
        self.source_line = None

    def _set_context(self, path, source_lines):
        """Attach source context once the top-level parser knows it."""
        self.path = path
        if 1 <= self.line <= len(source_lines):
            self.source_line = source_lines[self.line - 1]

    def __str__(self):
        """Render this error as a compiler-style diagnostic: location, message, and a caret."""
        location = f"{self.path or '<script>'}:{self.line}:{self.column}"
        cited = f" ({self.rule_id})" if self.rule_id else ""
        result = f"{location}: error: {self.message}{cited}"
        if self.source_line is not None:
            gutter = f"{self.line} | "
            caret = " " * (len(gutter) + self.column - 1) + "^"
            result = f"{result}\n{gutter}{self.source_line}\n{caret}"
        return result


@dataclass(frozen=True)
class Interpolation:
    """A ``${key}`` property reference inside a string literal."""

    key: str


@dataclass(frozen=True)
class StringLiteral:
    """A double-quoted string, broken into literal text chunks and interpolations.

    Escape sequences are already decoded by this point. ``\\${``
    produces a literal ``${`` text chunk instead of an
    :class:`Interpolation`, so the layer above can tell a real
    ``${key}`` reference apart from an escaped, literal ``${``.
    """

    parts: Tuple[object, ...]

    @property
    def interpolated(self):
        """Whether the literal carries any ``${key}`` reference."""
        return any(isinstance(part, Interpolation) for part in self.parts)

    @property
    def keys(self):
        """The property keys this literal references, in order."""
        return tuple(part.key for part in self.parts
                     if isinstance(part, Interpolation))

    @property
    def text(self):
        """The plain text of an uninterpolated literal."""
        if self.interpolated:
            # This is a safety check, not a real branch: callers are
            # expected to check `interpolated` first, so getting
            # here at all means there's a bug somewhere.
            raise InternalError("string carries a property reference")
        return "".join(self.parts)

    @property
    def spelling(self):
        """The literal exactly as written, with any ``${key}`` references left unresolved.

        Use this to display a string when no run has bound property
        values for it yet -- for example in a listing or a
        diagnostic message -- where :attr:`text` would raise
        instead.
        """
        return "".join(
            part if isinstance(part, str) else "${" + part.key + "}"
            for part in self.parts)


@dataclass(frozen=True)
class Token:
    """One lexed token: its class, source spelling, and position.

    ``kind`` is one of ``word``, ``duration``, ``string``,
    ``regex``, ``media``, ``property``, ``modifier``, ``open``,
    ``close``, or ``triple``. ``value`` is the decoded payload -- a
    :class:`StringLiteral` for ``string``, the pattern text for
    ``regex``, the referenced name for ``media`` and ``property``,
    a :class:`Modifier` for ``modifier``, and the spelling itself
    otherwise.
    """

    kind: str
    text: str
    value: object
    line: int
    column: int


@dataclass(frozen=True)
class Modifier:
    """A ``name=value`` modifier of the node it follows."""

    name: str
    value: Token
    line: int
    column: int


@dataclass(frozen=True)
class Node:
    """One structural node: a name, its arguments, its modifiers, and an optional block.

    ``block`` is ``None`` when the node did not open a block. Every
    block holds only other nodes -- a script never embeds JSON or
    any other foreign syntax inside it, so tokenization never has to
    pause partway through a line to hand off to a different parser.
    """

    name: str
    arguments: Tuple[Token, ...] = ()
    modifiers: Mapping[str, Modifier] = field(default_factory=dict)
    block: Optional[Tuple["Node", ...]] = None
    line: int = 0
    column: int = 1


def _freeze(mapping):
    return types.MappingProxyType(dict(mapping))


def _scan_string(text, start, number):
    """Scan a double-quoted string, returning its literal and end."""
    parts = []
    chunk = []
    index = start + 1
    while index < len(text):
        char = text[index]
        if char == '"':
            if chunk:
                parts.append("".join(chunk))
            return StringLiteral(tuple(parts)), index + 1
        if char == "\\":
            following = text[index + 1:index + 2]
            if following == "$" and text[index + 2:index + 3] == "{":
                chunk.append("${")
                index += 3
                continue
            if following in ('"', "\\"):
                chunk.append(following)
                index += 2
                continue
            if not following:
                break
            # Any other backslash is literal, both characters kept.
            chunk.append(char)
            chunk.append(following)
            index += 2
            continue
        if char == "$" and text[index + 1:index + 2] == "{":
            closing = text.find("}", index + 2)
            if closing < 0:
                raise ScriptParseError(
                    number, "unclosed property reference: expected '}'",
                    index + 1,
                    rule_id="lex.unclosed-reference")
            key = text[index + 2:closing]
            if not _NAME.fullmatch(key):
                raise ScriptParseError(
                    number, f"invalid property reference: {key!r}", index + 1,
                    rule_id="lex.invalid-reference")
            if chunk:
                parts.append("".join(chunk))
                chunk = []
            parts.append(Interpolation(key))
            index = closing + 1
            continue
        chunk.append(char)
        index += 1
    raise ScriptParseError(number, "unterminated string", start + 1,
    rule_id="lex.unterminated-string")


def _scan_regex(text, start, number):
    """Scan a ``/.../`` regex, returning its pattern and end."""
    pattern = []
    index = start + 1
    while index < len(text):
        char = text[index]
        if char == "/":
            return "".join(pattern), index + 1
        if char == "\\":
            following = text[index + 1:index + 2]
            if not following:
                break
            if following == "/":
                pattern.append("/")
            else:
                # Every other escape passes through to the engine.
                pattern.append(char)
                pattern.append(following)
            index += 2
            continue
        pattern.append(char)
        index += 1
    raise ScriptParseError(number, "unterminated regex", start + 1,
    rule_id="lex.unterminated-regex")


def _scan_word(text, start, stop_at_equals):
    """Scan a bare run of token characters, returning it and its end."""
    index = start
    while index < len(text):
        char = text[index]
        if char in _DELIMITERS:
            break
        if char == "=" and stop_at_equals:
            break
        index += 1
    return text[start:index], index


def _scan_value(text, start, number, bare_number=False,
                bare_fraction=False):
    """Scan one non-modifier token beginning at ``start``."""
    char = text[start]
    if text[start:start + 3] == '"""':
        return Token("triple", '"""', '"""', number, start + 1), start + 3
    if char == '"':
        literal, end = _scan_string(text, start, number)
        return Token("string", text[start:end], literal, number,
                     start + 1), end
    if char == "/":
        pattern, end = _scan_regex(text, start, number)
        return Token("regex", text[start:end], pattern, number,
                     start + 1), end
    if char in "@$":
        name, end = _scan_word(text, start + 1, False)
        kind = "media" if char == "@" else "property"
        if not (_MEDIA_NAME if char == "@" else _NAME).fullmatch(name):
            what = "media reference" if char == "@" else "property reference"
            raise ScriptParseError(
                number, f"invalid {what}: {text[start:end]!r}", start + 1,
                rule_id="lex.invalid-token")
        return Token(kind, text[start:end], name, number, start + 1), end
    word, end = _scan_word(text, start, False)
    if char.isdigit() or char == ".":
        if not _DURATION.fullmatch(word):
            if bare_number and word.isdigit():
                return Token("word", word, word, number, start + 1), end
            if bare_fraction and _FRACTION.fullmatch(word):
                return Token("word", word, word, number, start + 1), end
            raise ScriptParseError(
                number,
                f"invalid duration: {word!r} (durations carry a unit: "
                "ms, s, m, or h)", start + 1,
                rule_id="lex.invalid-duration")
        return Token("duration", word, word, number, start + 1), end
    return Token("word", word, word, number, start + 1), end


def tokenize(text, number):
    """Lex one source line into tokens, dropping any comment.

    Returns an empty tuple for a line holding only whitespace
    and/or a comment -- such a line is invisible to the grammar.
    """
    tokens = []
    index = 0
    while index < len(text):
        char = text[index]
        if char in " \t":
            index += 1
            continue
        if char == "#":
            break
        if char in "{}":
            kind = "open" if char == "{" else "close"
            tokens.append(Token(kind, char, char, number, index + 1))
            index += 1
            continue
        if char == "=":
            raise ScriptParseError(
                number, "modifiers are written name=value with no spaces "
                "around '='", index + 1,
                rule_id="lex.spaced-modifier")
        if char.isalpha():
            name, end = _scan_word(text, index, True)
            if text[end:end + 1] == "=":
                if end + 1 >= len(text) or text[end + 1] in _DELIMITERS:
                    raise ScriptParseError(
                        number, f"modifier {name!r} requires a value with no "
                        "spaces around '='", index + 1,
                        rule_id="lex.modifier-missing-value")
                value, end = _scan_value(
                    text, end + 1, number,
                    bare_number=name in ("port-min", "port-max"),
                    bare_fraction=name in FRACTION_VALUED)
                tokens.append(Token("modifier", text[index:end],
                                    Modifier(name, value, number, index + 1),
                                    number, index + 1))
                index = end
                continue
        # A header's value follows its keyword directly, with no `=`,
        # so it's the leading word that decides whether a bare
        # number is allowed here -- the same kind of contextual check
        # the modifier-scanning path above makes.
        token, index = _scan_value(
            text, index, number,
            bare_fraction=bool(tokens)
            and tokens[0].value in FRACTION_VALUED)
        tokens.append(token)
    return tuple(tokens)


def parse_nodes(source, path="<script>"):
    """Parse a script into its structural node tree.

    Enforces only the lexical rules and node shape: blocks must be
    balanced (V1), arguments must come before modifiers, and no
    modifier can be named twice on one node (V4). Node names
    themselves are not interpreted here.
    """
    if not isinstance(source, str):
        raise StaticError("script source must be text",
            rule_id="value.not-a-string")
    source = source.lstrip(chr(0xFEFF))
    lines = source.splitlines()
    try:
        return _parse(lines)
    except ScriptParseError as error:
        error._set_context(path, lines)
        raise


def _parse(lines):
    roots = []
    # Each open block contributes (node, children, opening line).
    stack = []
    index = 0
    while index < len(lines):
        number = index + 1
        tokens = tokenize(lines[index], number)
        index += 1
        if not tokens:
            continue
        first = tokens[0]
        if first.kind == "close":
            if len(tokens) > 1:
                raise ScriptParseError(
                    number, "a closing brace stands alone on its line",
                    tokens[1].column,
                    rule_id="syn.brace-not-alone")
            if not stack:
                raise ScriptParseError(number, "unmatched '}'", first.column,
    rule_id="syn.unmatched-close")
            node, children, _ = stack.pop()
            finished = Node(node.name, node.arguments, node.modifiers,
                            tuple(children), node.line, node.column)
            (stack[-1][1] if stack else roots).append(finished)
            continue
        if first.kind != "word":
            raise ScriptParseError(
                number, f"expected a node name, found {first.text!r}",
                first.column,
                rule_id="syn.expected-node-name")
        node, opens = _node(tokens, number)
        if not opens:
            (stack[-1][1] if stack else roots).append(node)
            if _opens_content_body(node):
                index = _skip_content_body(lines, index, number)
            continue
        stack.append((node, [], number))
    if stack:
        node = stack[-1][0]
        raise ScriptParseError(
            stack[-1][2], f"unclosed block opened by {node.name!r}",
            node.column,
            rule_id="syn.unclosed-block")
    return tuple(roots)


def _opens_content_body(node):
    return (node.name == "content" and node.arguments
            and node.arguments[-1].kind == "triple")


def _skip_content_body(lines, start, opener_line):
    for index in range(start, len(lines)):
        if lines[index].strip() == '"""':
            return index + 1
    raise ScriptParseError(opener_line, "unterminated content body",
    rule_id="lex.unterminated-content")


def _node(tokens, number):
    """Build one node from a line's tokens; report whether it opens."""
    name = tokens[0].value
    arguments = []
    modifiers = {}
    opens = False
    for position, token in enumerate(tokens[1:], 1):
        if token.kind == "open":
            if position != len(tokens) - 1:
                raise ScriptParseError(
                    number, "a block opens at the end of its line",
                    token.column,
                    rule_id="syn.open-brace-position")
            opens = True
            continue
        if token.kind == "close":
            raise ScriptParseError(
                number, "a closing brace stands alone on its line",
                token.column,
                rule_id="syn.brace-not-alone")
        if token.kind == "modifier":
            modifier = token.value
            if modifier.name in modifiers:
                raise ScriptParseError(
                    number, f"duplicate modifier: {modifier.name}",
                    token.column,
                    rule_id="node.duplicate-modifier")
            modifiers[modifier.name] = modifier
            continue
        if modifiers:
            raise ScriptParseError(
                number, "arguments precede modifiers", token.column,
                rule_id="syn.argument-after-modifier")
        arguments.append(token)
    return Node(name, tuple(arguments), _freeze(modifiers), None, number,
                tokens[0].column), opens
