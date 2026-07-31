# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The typed layer of the reliquary script language.

reliquary's own lexer (:mod:`reliquary.script_nodes`) feeds lark's
LALR(1) parser over ``script_grammar.lark``, which mirrors the
normative EBNF in docs/spec/script-spec.md. The lexer keeps
the lexical diagnostics; the grammar fixes node names and
positional argument types; this module's transformer checks each
node's modifiers against its signature and builds the typed tree.

The V-numbered static rules live above this layer.
"""

import os
import re
import textwrap
from dataclasses import dataclass, field
from typing import Mapping, Optional, Tuple

from lark import Lark, Token as LarkToken, Transformer
from lark.exceptions import UnexpectedInput, VisitError
from lark.lexer import Lexer

from .errors import PreflightError, StaticError
from .script_nodes import (
    KEYWORDS, Interpolation, ScriptParseError, StringLiteral, tokenize)
from .script_validation import validate

# Each node's allowed modifiers. The transformer reports anything
# else naming the node and what it accepts. Observation nodes list
# their timing modifiers only: every other modifier on an
# observation names a channel (script-spec.md, "Channels"), which
# V7 checks in the validation layer.
_SIGNATURES = {
    "wait_one": ("timeout", "stable"),
    "wait_branching": ("timeout",),
    "on_handler": ("stable",),
    "always_handler": ("stable",),
    "phase": ("timeout", "deadline", "pacing"),
    "property_def": ("prompt",),
    "http_def": ("port-min", "port-max"),
    "content_def": ("indent", "from"),
    "http_control": (),
    # The guest-input verbs, and only they, accept `pacing`: it is
    # the gap before the first key event, so a verb that delivers no
    # keys has nothing to pace.
    "select": ("exclude", "pacing"),
    "enter": ("pacing",), "type_text": ("pacing",),
    "press": ("pacing",), "screenshot": (),
    "insert": (), "eject": (), "set_boot": (), "set_var": (),
    "start": (), "stop": (),
    "goto": (), "finish": (),
}

# Grammar rule names back to the spelling an author wrote, so a
# signature diagnostic names the node as it appears in the script.
_DISPLAY = {
    "wait_one": "wait", "wait_branching": "wait", "on_handler": "on",
    "always_handler": "always", "type_text": "type",
    "set_boot": "set-boot", "set_var": "set", "property_def": "property",
    "http_def": "http", "content_def": "content",
    "http_control": "http",
}

# Modifiers whose value must be a duration. They are also the
# closed timing set that separates an observation's own modifiers
# from the channels it observes.
_DURATION_MODIFIERS = frozenset({"timeout", "deadline", "stable",
                                 "pacing"})

# The placement matrix (script-spec.md, "Timing"): every timing
# word the signatures above reject is rejected for a reason, and
# V2 diagnostics give it rather than listing what fits instead.
_PLACEMENT = {
    ("wait_one", "deadline"):
        "a budget bounds the wall clock of the construct it annotates, "
        "which on a single observation is exactly what timeout bounds",
    ("wait_branching", "deadline"):
        "a budget belongs to a phase or the run; a wait is bounded by "
        "timeout",
    ("wait_branching", "stable"):
        "only a match can be required to hold: write stable on the on "
        "handler whose condition must hold",
    ("on_handler", "timeout"):
        "the container owns the waiting: write timeout on the wait",
    ("always_handler", "timeout"):
        "the container owns the waiting: write timeout on the phase, "
        "where it bounds each interval with no handler firing",
    ("on_handler", "deadline"):
        "a budget belongs to a phase or the run",
    ("always_handler", "deadline"):
        "a budget belongs to a phase or the run",
    ("phase", "stable"):
        "only a match can be required to hold, and a phase has no "
        "condition of its own",
    ("wait_one", "pacing"):
        "pacing paces the actor, not the observation: write it on the "
        "input verb that follows, or on the phase",
    ("wait_branching", "pacing"):
        "pacing paces the actor, not the observation: write it on the "
        "input verb that follows, or on the phase",
    ("on_handler", "pacing"):
        "pacing belongs to a guest-input verb or the scope containing "
        "one: write it on the input verb in this handler, or on the "
        "phase",
    ("always_handler", "pacing"):
        "pacing belongs to a guest-input verb or the scope containing "
        "one: write it on the input verb in this handler, or on the "
        "phase",
    ("screenshot", "pacing"):
        "pacing is the gap before delivering guest input, and this "
        "verb delivers none",
    ("insert", "pacing"):
        "pacing is the gap before delivering guest input, and this "
        "verb delivers none",
    ("eject", "pacing"):
        "pacing is the gap before delivering guest input, and this "
        "verb delivers none",
    ("set_boot", "pacing"):
        "pacing is the gap before delivering guest input, and this "
        "verb delivers none",
    ("set_var", "pacing"):
        "pacing is the gap before delivering guest input, and this "
        "verb delivers none",
    ("start", "pacing"):
        "pacing is the gap before delivering guest input, and this "
        "verb delivers none",
    ("stop", "pacing"):
        "pacing is the gap before delivering guest input, and this "
        "verb delivers none",
    ("http_control", "pacing"):
        "pacing is the gap before delivering guest input, and this "
        "verb delivers none",
}
# A modifier value's terminal, as the condition kind it spells.
_CONDITION_KINDS = {
    "STRING": "text", "REGEX": "regex", "NAME": "state",
    "DURATION": "duration", "MEDIA_REF": "media", "PROP_REF": "property",
}
_PROPERTY_KINDS = ("text", "media", "secret")
_GRAMMAR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "script_grammar.lark")
_PROPERTY_REF = re.compile(r"[A-Za-z][A-Za-z0-9._-]*$")


@dataclass(frozen=True)
class Condition:
    """One observation condition on one channel.

    ``channel`` is ``None`` for a bare word, which spells no
    condition at all; the parser types it anyway so V7 can name
    what the author wrote. ``named`` distinguishes a channel the
    author named with a modifier from the unprefixed screen
    default, which V7 also checks.
    """

    channel: Optional[str]        # "screen", "machine", or None
    kind: str                     # "text", "regex", "state", ...
    value: object                 # StringLiteral, pattern text, or word
    line: int = 0
    column: int = 1
    named: bool = False


class _Observed:
    """The one-condition view V7 guarantees over the authored ones."""

    @property
    def condition(self):
        """The single condition, or ``None`` when none was written."""
        return self.conditions[0] if self.conditions else None


@dataclass(frozen=True)
class Handler(_Observed):
    """An ``on`` case or an ``always`` standing rule."""

    keyword: str                  # "on" or "always"
    conditions: Tuple[Condition, ...]
    statements: Tuple["Statement", ...]
    stable: Optional[str] = None
    line: int = 0
    column: int = 1


@dataclass(frozen=True)
class Statement(_Observed):
    """One executable node of the authored surface."""

    verb: str
    arguments: Tuple[object, ...] = ()
    conditions: Tuple[Condition, ...] = ()
    handlers: Tuple[Handler, ...] = ()
    timeout: Optional[str] = None
    stable: Optional[str] = None
    pacing: Optional[str] = None
    exclude: Optional[StringLiteral] = None
    contents: Tuple["HttpContent", ...] = ()
    line: int = 0
    column: int = 1


@dataclass(frozen=True)
class Property:
    """A declared script property."""

    key: str
    kind: str = "text"
    prompt: Optional[StringLiteral] = None
    defaults: Tuple[StringLiteral, ...] = ()
    line: int = 0
    column: int = 1


@dataclass(frozen=True)
class Phase:
    """A named phase: sequential statements or reactive handlers."""

    name: str
    statements: Tuple[Statement, ...] = ()
    handlers: Tuple[Handler, ...] = ()
    timeout: Optional[str] = None
    deadline: Optional[str] = None
    pacing: Optional[str] = None
    line: int = 0
    column: int = 1


@dataclass(frozen=True)
class HttpContent:
    """One run-served HTTP response body declared by a script."""

    name: str
    path: StringLiteral
    body: StringLiteral
    indent: str = "dedent"
    source_path: Optional[str] = None
    line: int = 0
    column: int = 1


@dataclass(frozen=True)
class Http:
    """The script's run-scoped HTTP answer-file server plan."""

    contents: Tuple[HttpContent, ...]
    port_min: Optional[str] = None
    port_max: Optional[str] = None
    line: int = 0
    column: int = 1


@dataclass(frozen=True)
class Script:
    """A parsed ``.rlqs`` document, before the V-rule checks."""

    platform: Optional[str] = None
    description: Optional[StringLiteral] = None
    machine: Optional[str] = None
    entry: Optional[str] = None
    timeout: Optional[str] = None
    deadline: Optional[str] = None
    pacing: Optional[str] = None
    properties: Tuple[Property, ...] = ()
    http: Optional[Http] = None
    statements: Tuple[Statement, ...] = ()
    phases: Tuple[Phase, ...] = ()
    headers: Mapping[str, int] = field(default_factory=dict)


class _Token(LarkToken):
    """A lark token carrying its reliquary token's decoded value.

    lark's own ``Token`` is slotted, so the decoded payload — a
    :class:`StringLiteral` with its interpolation parts, a regex
    pattern — rides in a slot of its own rather than an attribute.
    """

    __slots__ = ("reliquary",)


def _terminal(word):
    return "KW_" + word.upper().replace("-", "_")


_KEYWORD_TERMINALS = {word: _terminal(word) for word in KEYWORDS}


class ReliquaryLexer(Lexer):
    """Adapt reliquary's tokenizer to lark's token stream."""

    def __init__(self, lexer_conf=None):
        pass

    def lex(self, data):
        lines = data.splitlines()
        index = 0
        while index < len(lines):
            number = index + 1
            text = lines[index]
            tokens = tokenize(text, number)
            index += 1
            if not tokens:
                continue
            for position, token in enumerate(tokens):
                yield from self._convert(token, number, position == 0)
            yield LarkToken("_NL", "\n", line=number, column=1)
            if _opens_content_body(tokens):
                body, closing = _collect_content_body(lines, index, number)
                body_token = _Token("CONTENT_TEXT", body, line=number + 1,
                                    column=1)
                body_token.reliquary = body
                yield body_token
                yield LarkToken("_NL", "\n", line=closing, column=1)
                index = closing

    def _convert(self, token, number, leading):
        if token.kind == "modifier":
            modifier = token.value
            yield LarkToken("MOD_NAME", modifier.name, line=number,
                            column=modifier.column)
            yield from self._convert(modifier.value, number, False)
            return
        kind = {
            "open": "_BLOCK_OPEN", "close": "_BLOCK_CLOSE",
            "string": "STRING", "regex": "REGEX", "duration": "DURATION",
            "media": "MEDIA_REF", "property": "PROP_REF",
            "triple": "TRIPLE",
        }.get(token.kind)
        if kind is None:
            kind = (_KEYWORD_TERMINALS.get(token.value, "NAME")
                    if leading else "NAME")
        lark_token = _Token(kind, token.value, line=number,
                            column=token.column)
        lark_token.reliquary = token
        yield lark_token


def _line(token):
    return getattr(token, "line", 0) or 0


def _column(token):
    return getattr(token, "column", 1) or 1


def _modifiers(node, items):
    """Split a node's trailing modifiers, checking its signature."""
    allowed = _SIGNATURES[node]
    found = {}
    for name, value, line, column in items:
        if name in found:
            raise ScriptParseError(
                line, f"duplicate modifier: {name}", column,
                rule_id="node.duplicate-modifier")
        if name not in allowed:
            display = _DISPLAY.get(node, node)
            reason = _PLACEMENT.get((node, name))
            if reason is not None:
                raise ScriptParseError(
                    line, f"{display} does not accept {name}=: {reason}",
                    column, rule_id="node.timing-placement")
            listing = ", ".join(allowed) if allowed else "none"
            raise ScriptParseError(
                line, f"{display} does not accept the "
                f"modifier {name!r} (accepts: {listing})", column,
                rule_id="node.modifier-not-allowed")
        if name in _DURATION_MODIFIERS and value.type != "DURATION":
            raise ScriptParseError(
                line, f"{name} must be a duration", column,
                rule_id="node.modifier-not-a-duration")
        found[name] = value
    return found


def _observation(node, items):
    """Split an observation's modifiers from the channels it names.

    The timing set is closed, so every other modifier on an
    observation names a channel. Whether that channel exists and
    carries a value of the right kind is V7's, in the validation
    layer, where the diagnostic can say so.
    """
    timing = [item for item in items if item[0] in _DURATION_MODIFIERS]
    channels = tuple(_channel(item) for item in items
                     if item[0] not in _DURATION_MODIFIERS)
    return _modifiers(node, timing), channels


def _channel(item):
    """Type one ``channel=value`` modifier as a condition."""
    name, value, line, column = item
    kind = _CONDITION_KINDS.get(value.type, "word")
    decoded = getattr(value, "reliquary", None)
    return Condition(name, kind,
                     decoded.value if decoded is not None else str(value),
                     line, column, named=True)


def _opens_content_body(tokens):
    """Whether a tokenized line begins a raw ``content`` body."""
    return (tokens and tokens[0].kind == "word"
            and tokens[0].value == "content"
            and tokens[-1].kind == "triple")


def _collect_content_body(lines, start, opener_line):
    """Collect raw body lines through the next trimmed ``\"\"\"``."""
    body = []
    for index in range(start, len(lines)):
        if lines[index].strip() == '"""':
            return "\n".join(body), index + 1
        body.append(lines[index])
    raise ScriptParseError(opener_line, "unterminated content body",
    rule_id="lex.unterminated-content")


def _content_literal(text, indent, line, column):
    """Build a content body literal after applying indentation policy."""
    if indent == "dedent":
        text = textwrap.dedent(text)
    if text == "":
        return StringLiteral(())
    return _content_template(text.rstrip("\r\n") + "\n", line, column)


def _content_template(text, line, column):
    """Parse ``${key}`` references inside a content body."""
    parts = []
    chunk = []
    index = 0
    while index < len(text):
        char = text[index]
        if char == "\\" and text[index + 1:index + 3] == "${":
            chunk.append("${")
            index += 3
            continue
        if char == "$" and text[index + 1:index + 2] == "{":
            closing = text.find("}", index + 2)
            if closing < 0:
                raise ScriptParseError(
                    line, "unclosed property reference in content body",
                    column,
                    rule_id="lex.unclosed-reference")
            key = text[index + 2:closing]
            if not _PROPERTY_REF.fullmatch(key):
                raise ScriptParseError(
                    line,
                    f"invalid property reference in content body: {key!r}",
                    column,
                    rule_id="lex.invalid-reference")
            if chunk:
                parts.append("".join(chunk))
                chunk = []
            parts.append(Interpolation(key))
            index = closing + 1
            continue
        chunk.append(char)
        index += 1
    if chunk:
        parts.append("".join(chunk))
    return StringLiteral(tuple(parts))


class _Builder(Transformer):
    """Build the typed tree from lark's parse tree."""

    def __init__(self, base_dir=None):
        super().__init__()
        self.base_dir = base_dir

    def modifier(self, children):
        name, value = children
        return (str(name), value, _line(name), name.column)

    # -- headers -------------------------------------------------
    def h_description(self, children):
        return ("description", children[1].reliquary.value,
                _line(children[0]))

    def h_platform(self, children):
        return ("platform", str(children[1]), _line(children[0]))

    def h_machine(self, children):
        return ("machine", str(children[1]), _line(children[0]))

    def h_entry(self, children):
        return ("entry", str(children[1]), _line(children[0]))

    def h_timeout(self, children):
        return ("timeout", str(children[1]), _line(children[0]))

    def h_deadline(self, children):
        return ("deadline", str(children[1]), _line(children[0]))

    def h_pacing(self, children):
        return ("pacing", str(children[1]), _line(children[0]))

    # -- declarations --------------------------------------------
    def property_def(self, children):
        words = [child for child in children
                 if isinstance(child, LarkToken) and child.type == "NAME"]
        items = [c for c in children if isinstance(c, tuple)]
        # `default=` is the one repeatable modifier -- an ordered list of
        # derivation candidates -- so it is split out before the generic
        # single-value modifier check.
        defaults = []
        for name, value, line, column in items:
            if name != "default":
                continue
            if value.type != "STRING":
                raise ScriptParseError(
                    line, "default must be a string", column,
                    rule_id="node.modifier-not-a-string")
            defaults.append(value.reliquary.value)
        modifiers = _modifiers(
            "property_def", [item for item in items if item[0] != "default"])
        line = _line(words[0])
        if len(words) == 2:
            kind, key = str(words[0]), str(words[1])
            if kind not in _PROPERTY_KINDS:
                raise ScriptParseError(
                    line, f"unknown property kind: {kind!r} (expected "
                    f"{', '.join(_PROPERTY_KINDS)})", words[0].column,
                    rule_id="prop.unknown-kind")
        else:
            kind, key = "text", str(words[0])
        prompt = modifiers.get("prompt")
        if prompt is not None and prompt.type != "STRING":
            raise ScriptParseError(line, "prompt must be a string",
                                   words[0].column,
                                   rule_id="node.modifier-not-a-string")
        return Property(key, kind,
                        prompt.reliquary.value if prompt else None,
                        tuple(defaults), line, words[0].column)

    def http_def(self, children):
        modifiers = _modifiers(
            "http_def", [c for c in children if isinstance(c, tuple)])
        for name, token in modifiers.items():
            if token.type != "NAME" or not str(token).isdigit():
                raise ScriptParseError(
                    token.line, f"{name} must be a decimal TCP port",
                    token.column,
                    rule_id="http.port-not-a-number")
        return Http(
            tuple(c for c in children if isinstance(c, HttpContent)),
            str(modifiers["port-min"]) if "port-min" in modifiers else None,
            str(modifiers["port-max"]) if "port-max" in modifiers else None,
            _line(children[0]), _column(children[0]))

    def content_def(self, children):
        modifiers = _modifiers(
            "content_def", [c for c in children if isinstance(c, tuple)])
        name = str(children[1])
        path = children[2]
        indent = "dedent"
        if "indent" in modifiers:
            value = modifiers["indent"]
            if value.type != "NAME" or str(value) not in ("dedent",
                                                          "literal"):
                raise ScriptParseError(
                    value.line,
                    "indent must be dedent or literal", value.column,
                    rule_id="http.indent-not-a-mode")
            indent = str(value)
        text = next((c for c in children if isinstance(c, LarkToken)
                     and c.type == "CONTENT_TEXT"), None)
        source = modifiers.get("from")
        if source is not None and source.type != "STRING":
            raise ScriptParseError(
                source.line, "from must be a string", source.column,
                rule_id="node.modifier-not-a-string")
        if source is not None and text is not None:
            raise ScriptParseError(
                source.line,
                "content may not combine from= with a triple-quoted body",
                source.column,
                rule_id="http.content-two-bodies")
        if source is None and text is None:
            raise ScriptParseError(
                _line(children[0]),
                "content requires a triple-quoted body or from=",
                _column(children[0]),
                rule_id="http.content-no-body")
        if source is not None and "indent" in modifiers:
            raise ScriptParseError(
                modifiers["indent"].line,
                "indent applies only to triple-quoted content bodies",
                modifiers["indent"].column,
                rule_id="http.indent-on-file-body")
        if source is not None:
            source_path, body = self._content_file(
                source.reliquary.value, _line(children[0]),
                _column(children[0]))
        else:
            source_path = None
            body = _content_literal(str(text), indent,
                                    _line(children[0]),
                                    _column(children[0]))
        return HttpContent(name, path.reliquary.value, body, indent,
                           source_path, _line(children[0]),
                           _column(children[0]))

    def _content_file(self, literal, line, column):
        if literal.interpolated:
            raise ScriptParseError(
                line, "from path may not contain property references",
                column,
                rule_id="http.from-reference")
        spelling = literal.text
        if spelling == "" or os.path.isabs(spelling) \
                or spelling.startswith(("/", "\\")):
            raise ScriptParseError(
                line, "from path must be relative to the script file",
                column,
                rule_id="http.from-not-relative")
        segments = re.split(r"[\\/]+", spelling)
        if any(segment in (".", "..") for segment in segments):
            raise ScriptParseError(
                line, "from path may not contain . or .. segments",
                column,
                rule_id="http.from-traversal")
        base_dir = self.base_dir or os.getcwd()
        source_path = os.path.abspath(os.path.join(base_dir, spelling))
        try:
            with open(source_path, encoding="utf-8") as handle:
                text = handle.read()
        except FileNotFoundError:
            raise ScriptParseError(
                line, f"content source file not found: {source_path}",
                column,
                rule_id="http.from-missing") from None
        except OSError as error:
            raise ScriptParseError(
                line,
                f"content source file cannot be read: {source_path}: "
                f"{error}", column,
                rule_id="http.from-unreadable") from None
        return source_path, _content_template(
            text.rstrip("\r\n") + "\n" if text else "", line, column)

    # -- conditions ----------------------------------------------
    def screen_text(self, children):
        return self._screen("text", children[0])

    def screen_regex(self, children):
        return self._screen("regex", children[0])

    def _screen(self, kind, token):
        return Condition("screen", kind, token.reliquary.value,
                         _line(token), _column(token))

    def bare_condition(self, children):
        # No channel: a bare word spells no condition at all. V7
        # names it, so the grammar admits it rather than failing
        # here with an unexpected-token diagnostic.
        token = children[0]
        return Condition(None, "word", str(token), _line(token),
                         _column(token))

    # -- observations --------------------------------------------
    def wait_one(self, children):
        conditions = [c for c in children if isinstance(c, Condition)]
        modifiers, channels = _observation(
            "wait_one", [c for c in children if isinstance(c, tuple)])
        return Statement(
            "wait", conditions=tuple(conditions) + channels,
            timeout=_duration(modifiers.get("timeout")),
            stable=_duration(modifiers.get("stable")),
            line=_line(children[0]), column=_column(children[0]))

    def wait_branching(self, children):
        handlers = tuple(c for c in children if isinstance(c, Handler))
        modifiers, channels = _observation(
            "wait_branching", [c for c in children if isinstance(c, tuple)])
        return Statement("wait", conditions=channels, handlers=handlers,
                         timeout=_duration(modifiers.get("timeout")),
                         line=_line(children[0]),
                         column=_column(children[0]))

    def on_handler(self, children):
        return self._handler("on", "on_handler", children)

    def always_handler(self, children):
        return self._handler("always", "always_handler", children)

    def _handler(self, keyword, node, children):
        conditions = tuple(c for c in children if isinstance(c, Condition))
        modifiers, channels = _observation(
            node, [c for c in children if isinstance(c, tuple)])
        return Handler(
            keyword, conditions + channels,
            tuple(c for c in children if isinstance(c, Statement)),
            _duration(modifiers.get("stable")), _line(children[0]),
            _column(children[0]))

    # -- transfers and actions -----------------------------------
    def goto(self, children):
        return Statement("goto", (str(children[1]),),
                         line=_line(children[0]),
                         column=_column(children[0]))

    def finish(self, children):
        return Statement("finish", line=_line(children[0]),
                         column=_column(children[0]))

    def _simple(self, verb, node, children, arguments):
        _modifiers(node, [c for c in children if isinstance(c, tuple)])
        return Statement(verb, arguments, line=_line(children[0]),
                         column=_column(children[0]))

    def _paced(self, verb, node, children, arguments):
        """A guest-input verb: like ``_simple``, keeping ``pacing``."""
        modifiers = _modifiers(
            node, [c for c in children if isinstance(c, tuple)])
        return Statement(verb, arguments,
                         pacing=_duration(modifiers.get("pacing")),
                         line=_line(children[0]),
                         column=_column(children[0]))

    def enter(self, children):
        return self._paced("enter", "enter", children,
                           (children[1].reliquary.value,))

    def type_text(self, children):
        return self._paced("type", "type_text", children,
                           (children[1].reliquary.value,))

    def press(self, children):
        keys = tuple(str(c) for c in children[1:]
                     if isinstance(c, LarkToken) and c.type == "NAME")
        return self._paced("press", "press", children, keys)

    def http_control(self, children):
        _modifiers("http_control",
                   [c for c in children if isinstance(c, tuple)])
        names = tuple(str(c) for c in children[2:]
                      if isinstance(c, LarkToken) and c.type == "NAME")
        contents = tuple(c for c in children if isinstance(c, HttpContent))
        return Statement("http", (str(children[1]),) + names,
                         contents=contents, line=_line(children[0]),
                         column=_column(children[0]))

    def select(self, children):
        modifiers = _modifiers(
            "select", [c for c in children if isinstance(c, tuple)])
        exclude = modifiers.get("exclude")
        line = _line(children[0])
        if exclude is not None and exclude.type != "STRING":
            raise ScriptParseError(line, "exclude must be a string",
                                   children[0].column,
                                   rule_id="node.modifier-not-a-string")
        return Statement(
            "select", (children[1].reliquary.value,),
            pacing=_duration(modifiers.get("pacing")),
            exclude=exclude.reliquary.value if exclude else None, line=line,
            column=_column(children[0]))

    def screenshot(self, children):
        names = tuple(str(c) for c in children[1:]
                      if isinstance(c, LarkToken) and c.type == "NAME")
        return self._simple("screenshot", "screenshot", children, names)

    def insert(self, children):
        reference = children[2]
        return self._simple(
            "insert", "insert", children,
            (str(children[1]),
             (reference.type == "MEDIA_REF" and "media" or "property",
              str(reference))))

    def eject(self, children):
        return self._simple("eject", "eject", children,
                            (str(children[1]),))

    def set_boot(self, children):
        keys = tuple(str(c) for c in children[1:]
                     if isinstance(c, LarkToken) and c.type == "NAME")
        return self._simple("set-boot", "set_boot", children, keys)

    def set_var(self, children):
        # The script -> host scalar channel: `set <key> "<value>"`
        # records a machine variable any process can read back with
        # `get-machine-var`.
        return self._simple(
            "set", "set_var", children,
            (str(children[1]), children[2].reliquary.value))

    def start(self, children):
        return self._simple("start", "start", children, ())

    def stop(self, children):
        return self._simple("stop", "stop", children, ())

    # -- phases and the document ---------------------------------
    def phase(self, children):
        modifiers = _modifiers(
            "phase", [c for c in children if isinstance(c, tuple)])
        return Phase(
            str(children[1]),
            tuple(c for c in children if isinstance(c, Statement)),
            tuple(c for c in children if isinstance(c, Handler)),
            _duration(modifiers.get("timeout")),
            _duration(modifiers.get("deadline")),
            _duration(modifiers.get("pacing")), _line(children[0]),
            _column(children[0]))

    def phased_body(self, children):
        return ("phased", tuple(children))

    def linear_body(self, children):
        return ("linear", tuple(children))

    def script(self, children):
        headers, lines = {}, {}
        properties, statements, phases, http = [], [], [], None
        for child in children:
            if isinstance(child, Property):
                properties.append(child)
            elif isinstance(child, Http):
                if http is not None:
                    raise ScriptParseError(
                        child.line, "http may appear only once",
                        rule_id="http.duplicate-declaration")
                http = child
            elif isinstance(child, tuple) and child[0] in ("linear",
                                                           "phased"):
                if child[0] == "linear":
                    statements.extend(child[1])
                else:
                    phases.extend(child[1])
            elif isinstance(child, tuple):
                name, value, line = child
                if name in headers:
                    raise ScriptParseError(
                        line, f"{name} may appear only once in the header",
                        rule_id="syn.duplicate-header")
                headers[name] = value
                lines[name] = line
        return Script(
            headers.get("platform"), headers.get("description"),
            headers.get("machine"), headers.get("entry"),
            headers.get("timeout"), headers.get("deadline"),
            headers.get("pacing"),
            tuple(properties), http, tuple(statements), tuple(phases), lines)


def _duration(token):
    return str(token) if token is not None else None


_PARSER = Lark.open(_GRAMMAR, parser="lalr", lexer=ReliquaryLexer,
                    start="script", propagate_positions=True)


def parse_script(source, path="<script>"):
    """Parse and statically validate a ``.rlqs`` document.

    Applies the lexical rules, the node signatures, and header
    uniqueness here, then the V-numbered rules over the typed tree
    in :mod:`reliquary.script_validation` — script shape,
    observation channels, control flow.
    """
    if not isinstance(source, str):
        raise StaticError("script source must be text",
            rule_id="value.not-a-string")
    source = source.lstrip(chr(0xFEFF))
    base_dir = None
    if path != "<script>":
        base_dir = os.path.dirname(os.path.abspath(os.fspath(path)))
    try:
        script = _Builder(base_dir).transform(_PARSER.parse(source))
        validate(script)
        return script
    except VisitError as error:
        # The transformer's own diagnostics arrive wrapped.
        if isinstance(error.orig_exc, ScriptParseError):
            error.orig_exc._set_context(path, source.splitlines())
            raise error.orig_exc from None
        raise
    except ScriptParseError as error:
        error._set_context(path, source.splitlines())
        raise
    except UnexpectedInput as error:
        raise _diagnose(error, source, path) from None


def load_script(path):
    """Load and parse a UTF-8 ``.rlqs`` file with path-aware
    diagnostics."""
    path = os.path.abspath(os.fspath(path))
    try:
        with open(path, encoding="utf-8") as handle:
            return parse_script(handle.read(), path=path)
    except FileNotFoundError:
        raise PreflightError(f"Script not found: {path}",
            rule_id="script.unknown") from None


def _diagnose(error, source, path):
    """Turn a lark parse error into a reliquary diagnostic.

    These are the grammar's own rejections, so they carry the
    coarsest ids in the scheme: the grammar knows a token is
    unexpected, never which rule the author was reaching for. That
    is the trade script-spec.md makes deliberately by keeping the
    V-rules above the CFG — a named rule where validation can
    reach, an unexpected token where only the parser can.
    """
    token = getattr(error, "token", None)
    line = getattr(error, "line", 0) or 0
    column = getattr(error, "column", 1) or 1
    if token is not None and token.type == "$END":
        message = "unexpected end of script"
        rule_id = "syn.unexpected-end"
    elif token is not None:
        spelling = str(token)
        message = f"{spelling!r} is not valid here"
        rule_id = "syn.unexpected-token"
    else:
        message = "unexpected input"
        rule_id = "syn.unexpected-token"
    failure = ScriptParseError(line, message, column, rule_id=rule_id)
    failure._set_context(path, source.splitlines())
    return failure
