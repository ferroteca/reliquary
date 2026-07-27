# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""The structural node layer of the reliquary script language.

Every line of a script is one node::

    node = name , { argument } , { modifier } , [ block ]

This module implements the lexical rules and that shape only --
what a line *looks like*. Typing (which node names exist, what
arguments and modifiers each admits) and the S-numbered static
rules belong to the layer above, in :mod:`reliquary.script`.
The milestone-5 ``content`` declaration has one structural
extension: a trailing ``\"\"\"`` opens a raw body that is skipped
until its closing ``\"\"\"`` line.

Source of truth: docs/spec/script-spec.md, "Lexical rules"
and "Core grammar".
"""

import re
import types
from dataclasses import dataclass, field
from typing import Mapping, Optional, Tuple

from .errors import InternalError, StaticError

_DURATION = re.compile(r"(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)(?:ms|s|m|h)$")
_NAME = re.compile(r"[A-Za-z][A-Za-z0-9._-]*$")
# A media name may lead with a digit where a property key may not:
# the `@` sigil already classifies the token, while a property key
# also appears bare at its `property` declaration, where a leading
# digit would lex as a duration (D24).
_MEDIA_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*$")
# A token ends at whitespace, a brace, a comment, or the line
# terminator; strings and regexes end at their closing delimiter.
_DELIMITERS = " \t{}#"

# The node names: every header, declaration and verb. They live here
# rather than with the parser because two layers need the same list
# and neither may import the other -- the lexer recognizes them as
# keywords in node-name position, and validation refuses them as
# identifiers everywhere (S5).
#
# The two jobs are separate on purpose. A word is a keyword only
# where a node name may start, so `enter` is a verb at the head of a
# line and an ordinary key name after `press`; the closed
# vocabularies are validation's, not the grammar's (script-spec.md,
# "Grammar"). What the grammar cannot express is the *reservation* --
# that `phase enter` names no phase -- because a rejected identifier
# there would surface as "unexpected token" instead of a named rule.
KEYWORDS = (
    "description", "platform", "machine", "entry", "timeout", "deadline",
    "property", "http", "content", "phase", "wait", "on", "always",
    "goto", "finish", "enter", "type", "press", "select", "screenshot",
    "insert", "eject", "set-boot", "set", "start", "stop",
)


#: Every id the script parser stack raises, and the S-numbered rule
#: it enforces.
#:
#: Ids are finer than the rules — S7 is one restriction and
#: ``obs.two-channels`` is one of six diagnostics under it — so this
#: is many-to-one by design.
#:
#: Its scope is this module, the grammar transformer and validation,
#: and nothing beyond. An S-number names a syntactic restriction, so
#: an id raised elsewhere — ``media.unknown`` from resolution,
#: ``machine.slot-not-declared`` from preflight — has none to map to
#: and no entry here. Within the stack, an id no S-number covers maps
#: to ``None`` rather than being left out, so the map answers for
#: every id it can be asked about.
#:
#: It lives here rather than only in docs/spec/script-spec.md because
#: a consumer switching on an id needs the rule without parsing
#: prose; the spec's rule list carries the same mapping and a test
#: holds the two together.
RULE_OF = {
    "node.duplicate-modifier": "S4",
    "node.modifier-not-allowed": "S2",
    "node.timing-placement": "S2",
    "name.reserved-node": "S5",
    "name.duplicate-phase": "S5",
    "name.duplicate-property": "S5",
    "name.property-is-a-kind": "S5",
    "name.property-reserved-namespace": "S5",
    "name.variable-reserved-namespace": "S5",
    "time.non-positive": "S5",
    "prop.secret-default": "S5",
    "prop.dead-default": "S5",
    "prop.undefined-reference": "S6",
    "prop.secret-reference": "S6",
    "prop.derivation-cycle": "S6",
    "prop.http-without-block": "S6",
    "obs.missing-condition": "S7",
    "obs.two-channels": "S7",
    "obs.not-a-condition": "S7",
    "obs.unknown-channel": "S7",
    "obs.screen-named": "S7",
    "obs.wrong-kind": "S7",
    "wait.branching-condition": "S8",
    "wait.branching-in-handler": "S8",
    "wait.too-few-handlers": "S8",
    "handler.mixed-phase": "S9",
    "handler.on-outside-branching-wait": "S9",
    "handler.always-outside-reactive-phase": "S9",
    "flow.entry-in-linear": "S3",
    "flow.entry-missing": "S3",
    "flow.entry-undeclared": "S10",
    "flow.transfer-in-linear": "S10",
    "flow.goto-undeclared": "S10",
    "flow.unreachable-statement": "S11",
    "flow.phase-falls-through": "S11",
    "flow.cycle-without-deadline": "S12",
    "obs.empty-pattern": "S13",
    "obs.uncompilable-regex": "S13",
    "key.not-portable": "S14",
}

#: The lexical and structural tiers. S1 is "syntax is well formed:
#: no unknown node names, no unbalanced blocks", which the lexer and
#: the grammar enforce between them, so these are its diagnostics.
#: ``lex.`` is what the tokenizer rejects while reading characters;
#: ``syn.`` is line, block and document shape.
RULE_OF.update({
    "lex.unclosed-reference": "S1",
    "lex.invalid-reference": "S1",
    "lex.unterminated-string": "S1",
    "lex.unterminated-regex": "S1",
    "lex.unterminated-content": "S1",
    "lex.invalid-token": "S1",
    "lex.invalid-duration": "S1",
    "lex.spaced-modifier": "S1",
    "lex.modifier-missing-value": "S1",
    "syn.brace-not-alone": "S1",
    "syn.unmatched-close": "S1",
    "syn.unclosed-block": "S1",
    "syn.open-brace-position": "S1",
    "syn.expected-node-name": "S1",
    "syn.argument-after-modifier": "S1",
    "syn.unexpected-token": "S1",
    "syn.unexpected-end": "S1",
    "syn.duplicate-header": "S3",
    "node.modifier-not-a-duration": "S2",
    "node.modifier-not-a-string": "S2",
    "prop.unknown-kind": "S5",
})

#: Ids this stack raises that no S-number covers, mapped to None.
#:
#: Two reasons an id lands here. The http declaration's rules are
#: static and legality-tier like the rest and simply predate the
#: S-numbering. The last two are not legality rules at all: a
#: source that is not text and a script file that is not there,
#: which the parser reports because it is the layer that looked.
#: Either way a consumer asking what rule an id enforces gets a
#: truthful None rather than an S-number invented to fill the map.
RULE_OF.update({
    "http.port-not-a-number": None,
    "http.indent-not-a-mode": None,
    "http.content-two-bodies": None,
    "http.content-no-body": None,
    "http.indent-on-file-body": None,
    "http.from-reference": None,
    "http.from-not-relative": None,
    "http.from-traversal": None,
    "http.from-missing": None,
    "http.from-unreadable": None,
    "http.duplicate-declaration": None,
    "http.no-content": None,
    "http.duplicate-content-name": None,
    "http.duplicate-content-path": None,
    "http.path-not-absolute": None,
    "http.path-traversal": None,
    "http.empty-body": None,
    "http.unknown-action": None,
    "http.start-without-content": None,
    "http.undeclared-content": None,
    "http.stop-takes-nothing": None,
    "http.port-out-of-range": None,
    "http.port-range-inverted": None,
    "http.reference-in-path": None,
    "value.not-a-string": None,
    "script.unknown": None,
})


class ScriptParseError(StaticError):
    """A script syntax or static-validation error with a source line.

    The legality tier of the error taxonomy: it is decided from the
    script text alone, so it is a STATIC ERROR and exits ``2``.

    ``rule_id`` is the stable dotted identifier naming the rule the
    diagnostic enforces (docs/spec/script-spec.md, "Error classes
    and exit codes"): ``obs.two-channels`` and its siblings, one
    namespace across the error classes. It is a *field* rather than
    text baked into the message, so a consumer can switch on it
    without parsing prose and the beta id index can be generated
    rather than hand-kept. The rendering appends it in parentheses,
    which is where the S-numbers used to sit.

    Ids are finer than the S-numbered rules they enforce: S7 is one
    restriction and ``obs.two-channels`` is one of the several
    diagnostics under it. The spec's rule list carries the mapping,
    and a test holds the two together.

    ``rule_id`` is inherited from :class:`~reliquary.errors.ReliquaryError`,
    where it lives because the spec puts every id in one namespace
    across the classes. Every tier of this surface carries one now,
    preflight and runtime included; other surfaces do not yet, and
    the conformance corpora measure what remains rather than
    estimating it.
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
        """Render an actionable compiler-style diagnostic."""
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
    """A double-quoted string as literal chunks and interpolations.

    Escapes are already decoded. ``\\${`` produces a literal
    ``${`` chunk rather than an :class:`Interpolation`, so the
    typed layer can tell an authored reference from escaped text.
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
            # A guard, not a question: `interpolated` is the question,
            # and every caller asks it first. Reaching here is a bug.
            raise InternalError("string carries a property reference")
        return "".join(self.parts)

    @property
    def spelling(self):
        """The literal as authored, references left unresolved.

        For displaying a string no run has bound values for -- a
        listing, a diagnostic -- where :attr:`text` would refuse.
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
    """One structural node: a name, arguments, modifiers, a block.

    ``block`` is ``None`` when the node opened no block. Every
    block holds nodes: a script carries no JSON, so there is no
    island and tokenization never suspends.
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


def _scan_value(text, start, number, bare_number=False):
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
                    bare_number=name in ("port-min", "port-max"))
                tokens.append(Token("modifier", text[index:end],
                                    Modifier(name, value, number, index + 1),
                                    number, index + 1))
                index = end
                continue
        token, index = _scan_value(text, index, number)
        tokens.append(token)
    return tuple(tokens)


def parse_nodes(source, path="<script>"):
    """Parse a script into its structural node tree.

    Enforces the lexical rules and the node shape only: balanced
    blocks (S1), arguments before modifiers, and no modifier named
    twice on one node (S4). Node names are not interpreted here.
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
