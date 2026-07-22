# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""The typed layer of the reliquary script language.

reliquary's own lexer (:mod:`reliquary.script_nodes`) feeds lark's
LALR(1) parser over ``script_grammar.lark``, which mirrors the
normative EBNF in planning/design/script-spec.md. The lexer keeps
the lexical diagnostics; the grammar fixes node names and
positional argument types; this module's transformer checks each
node's modifiers against its signature and builds the typed tree.

The S-numbered static rules live above this layer.
"""

import os
from dataclasses import dataclass, field
from typing import Mapping, Optional, Tuple

from lark import Lark, Token as LarkToken, Transformer
from lark.exceptions import UnexpectedInput, VisitError
from lark.lexer import Lexer

from .script_nodes import ScriptParseError, StringLiteral, tokenize
from .script_validation import validate

# Node names, reserved everywhere a script-internal name may appear
# (S5). Recognized as keywords only in node-name position: `enter`
# is a verb at the start of a line and a key name after `press`
# (script-spec.md, "Grammar" -- closed vocabularies are checked by
# validation, not the grammar).
KEYWORDS = (
    "description", "platform", "machine", "entry", "timeout", "deadline",
    "property", "phase", "wait", "on", "always", "goto", "finish",
    "enter", "type", "press", "select", "screenshot", "insert", "eject",
    "set-boot", "start", "stop",
)

# Each node's allowed modifiers. The transformer reports anything
# else naming the node and what it accepts. Observation nodes list
# their timing modifiers only: every other modifier on an
# observation names a channel (script-spec.md, "Channels"), which
# S7 checks in the validation layer.
_SIGNATURES = {
    "wait_one": ("timeout", "stable"),
    "wait_branching": ("timeout",),
    "on_handler": ("stable",),
    "always_handler": ("stable",),
    "phase": ("timeout", "deadline"),
    "property_def": ("prompt",),
    "select": ("exclude",),
    "enter": (), "type_text": (), "press": (), "screenshot": (),
    "insert": (), "eject": (), "set_boot": (), "start": (), "stop": (),
    "goto": (), "finish": (),
}

# Grammar rule names back to the spelling an author wrote, so a
# signature diagnostic names the node as it appears in the script.
_DISPLAY = {
    "wait_one": "wait", "wait_branching": "wait", "on_handler": "on",
    "always_handler": "always", "type_text": "type",
    "set_boot": "set-boot", "property_def": "property",
}

# Modifiers whose value must be a duration. They are also the
# closed timing set that separates an observation's own modifiers
# from the channels it observes.
_DURATION_MODIFIERS = frozenset({"timeout", "deadline", "stable"})
# A modifier value's terminal, as the condition kind it spells.
_CONDITION_KINDS = {
    "STRING": "text", "REGEX": "regex", "NAME": "state",
    "DURATION": "duration", "MEDIA_REF": "media", "PROP_REF": "property",
}
_PROPERTY_KINDS = ("text", "media", "secret")
_GRAMMAR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "script_grammar.lark")


@dataclass(frozen=True)
class Condition:
    """One observation condition on one channel.

    ``channel`` is ``None`` for a bare word, which spells no
    condition at all; the parser types it anyway so S7 can name
    what the author wrote. ``named`` distinguishes a channel the
    author named with a modifier from the unprefixed screen
    default, which S7 also checks.
    """

    channel: Optional[str]        # "screen", "machine", or None
    kind: str                     # "text", "regex", "state", ...
    value: object                 # StringLiteral, pattern text, or word
    line: int = 0
    column: int = 1
    named: bool = False


class _Observed:
    """The one-condition view S7 guarantees over the authored ones."""

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
    exclude: Optional[StringLiteral] = None
    line: int = 0
    column: int = 1


@dataclass(frozen=True)
class Property:
    """A declared script property."""

    key: str
    kind: str = "text"
    prompt: Optional[StringLiteral] = None
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
    line: int = 0
    column: int = 1


@dataclass(frozen=True)
class Script:
    """A parsed ``.rlqs`` document, before the S-rule checks."""

    platform: Optional[str] = None
    description: Optional[StringLiteral] = None
    machine: Optional[str] = None
    entry: Optional[str] = None
    timeout: Optional[str] = None
    deadline: Optional[str] = None
    properties: Tuple[Property, ...] = ()
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
        for number, text in enumerate(data.splitlines(), 1):
            tokens = tokenize(text, number)
            if not tokens:
                continue
            for index, token in enumerate(tokens):
                yield from self._convert(token, number, index == 0)
            yield LarkToken("_NL", "\n", line=number, column=1)

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
                line, f"duplicate modifier: {name}", column)
        if name not in allowed:
            listing = ", ".join(allowed) if allowed else "none"
            raise ScriptParseError(
                line, f"{_DISPLAY.get(node, node)} does not accept the "
                f"modifier {name!r} (accepts: {listing})", column)
        if name in _DURATION_MODIFIERS and value.type != "DURATION":
            raise ScriptParseError(
                line, f"{name} must be a duration", column)
        found[name] = value
    return found


def _observation(node, items):
    """Split an observation's modifiers from the channels it names.

    The timing set is closed, so every other modifier on an
    observation names a channel. Whether that channel exists and
    carries a value of the right kind is S7's, in the validation
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


class _Builder(Transformer):
    """Build the typed tree from lark's parse tree."""

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

    # -- declarations --------------------------------------------
    def property_def(self, children):
        words = [child for child in children
                 if isinstance(child, LarkToken) and child.type == "NAME"]
        modifiers = _modifiers(
            "property_def", [c for c in children if isinstance(c, tuple)])
        line = _line(words[0])
        if len(words) == 2:
            kind, key = str(words[0]), str(words[1])
            if kind not in _PROPERTY_KINDS:
                raise ScriptParseError(
                    line, f"unknown property kind: {kind!r} (expected "
                    f"{', '.join(_PROPERTY_KINDS)})", words[0].column)
        else:
            kind, key = "text", str(words[0])
        prompt = modifiers.get("prompt")
        if prompt is not None and prompt.type != "STRING":
            raise ScriptParseError(line, "prompt must be a string",
                                   words[0].column)
        return Property(key, kind,
                        prompt.reliquary.value if prompt else None, line,
                        words[0].column)

    # -- conditions ----------------------------------------------
    def screen_text(self, children):
        return self._screen("text", children[0])

    def screen_regex(self, children):
        return self._screen("regex", children[0])

    def _screen(self, kind, token):
        return Condition("screen", kind, token.reliquary.value,
                         _line(token), _column(token))

    def bare_condition(self, children):
        # No channel: a bare word spells no condition at all. S7
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

    def enter(self, children):
        return self._simple("enter", "enter", children,
                            (children[1].reliquary.value,))

    def type_text(self, children):
        return self._simple("type", "type_text", children,
                            (children[1].reliquary.value,))

    def press(self, children):
        keys = tuple(str(c) for c in children[1:]
                     if isinstance(c, LarkToken) and c.type == "NAME")
        return self._simple("press", "press", children, keys)

    def select(self, children):
        modifiers = _modifiers(
            "select", [c for c in children if isinstance(c, tuple)])
        exclude = modifiers.get("exclude")
        line = _line(children[0])
        if exclude is not None and exclude.type != "STRING":
            raise ScriptParseError(line, "exclude must be a string",
                                   children[0].column)
        return Statement(
            "select", (children[1].reliquary.value,),
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
            _duration(modifiers.get("deadline")), _line(children[0]),
            _column(children[0]))

    def phased_body(self, children):
        return ("phased", tuple(children))

    def linear_body(self, children):
        return ("linear", tuple(children))

    def script(self, children):
        headers, lines = {}, {}
        properties, statements, phases = [], [], []
        for child in children:
            if isinstance(child, Property):
                properties.append(child)
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
                        line, f"{name} may appear only once in the header")
                headers[name] = value
                lines[name] = line
        return Script(
            headers.get("platform"), headers.get("description"),
            headers.get("machine"), headers.get("entry"),
            headers.get("timeout"), headers.get("deadline"),
            tuple(properties), tuple(statements), tuple(phases), lines)


def _duration(token):
    return str(token) if token is not None else None


_PARSER = Lark.open(_GRAMMAR, parser="lalr", lexer=ReliquaryLexer,
                    start="script", propagate_positions=True)


def parse_document(source, path="<script>"):
    """Parse and statically validate a ``.rlqs`` document.

    Applies the lexical rules, the node signatures, and header
    uniqueness here, then the S-numbered rules over the typed tree
    in :mod:`reliquary.script_validation` — script shape,
    observation channels, control flow.
    """
    if not isinstance(source, str):
        raise TypeError("script source must be text")
    source = source.lstrip(chr(0xFEFF))
    try:
        script = _Builder().transform(_PARSER.parse(source))
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


def _diagnose(error, source, path):
    """Turn a lark parse error into a reliquary diagnostic."""
    token = getattr(error, "token", None)
    line = getattr(error, "line", 0) or 0
    column = getattr(error, "column", 1) or 1
    if token is not None and token.type == "$END":
        message = "unexpected end of script"
    elif token is not None:
        spelling = str(token)
        message = f"{spelling!r} is not valid here"
    else:
        message = "unexpected input"
    failure = ScriptParseError(line, message, column)
    failure._set_context(path, source.splitlines())
    return failure
