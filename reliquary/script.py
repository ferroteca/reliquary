# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Parser for the milestone-one subset of reliquary scripts."""

import json
import os
import re
import types
from dataclasses import dataclass, field
from typing import Mapping, Optional, Tuple

from .media import MediaDefinition, parse_definition


_IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9_.-]*$")
_DURATION = re.compile(r"(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)(?:ms|s|m|h)$")
_STRING = re.compile(r'(?:r)?"(?:\\.|[^"\\])*"$')
_KEY = re.compile(r"[a-z]+(?:\+[a-z]+)*$")
_RESERVED = {"description", "platform", "initial", "machine", "timeout",
             "media", "state", "wait", "expect", "enter", "type", "press",
             "select", "screenshot", "insert", "eject", "boot", "start",
             "stop", "done"}
_REMOVABLE_SLOT = re.compile(r"(floppy|cdrom)([0-9]+)?$")
_REMOVABLE_LIMITS = {"floppy": 2, "cdrom": 4}
_DRIVE_SLOT = re.compile(r"(floppy|hdd|cdrom)([0-9]+)?$")
_DRIVE_LIMITS = {"floppy": 2, "hdd": 4, "cdrom": 4}


class ScriptParseError(ValueError):
    """A script syntax or static-validation error with a source line."""

    def __init__(self, line, message, column=1):
        super().__init__(message)
        self.line = line
        self.column = column
        self.message = message
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
        result = f"{location}: error: {self.message}"
        if self.source_line is not None:
            gutter = f"{self.line} | "
            caret = " " * (len(gutter) + self.column - 1) + "^"
            result = f"{result}\n{gutter}{self.source_line}\n{caret}"
        return result


@dataclass(frozen=True)
class Condition:
    kind: str
    value: Optional[str] = None


@dataclass(frozen=True)
class Statement:
    verb: str
    argument: Optional[object] = None
    modifiers: Mapping[str, object] = field(default_factory=dict)
    line: int = 0


@dataclass(frozen=True)
class ExpectBranch:
    condition: Condition
    statements: Tuple[Statement, ...]
    line: int = 0


@dataclass(frozen=True)
class State:
    name: str
    statements: Tuple[Statement, ...]
    modifiers: Mapping[str, object] = field(default_factory=dict)
    line: int = 0


@dataclass(frozen=True)
class EmbeddedMedia:
    label: str
    definition: MediaDefinition
    line: int = 0


@dataclass(frozen=True)
class Script:
    """An immutable parsed linear or state-machine ``.rqs`` document."""

    platform: str
    description: Optional[str] = None
    timeout: Optional[str] = None
    initial: Optional[str] = None
    machine: str = "running"
    media: Tuple[EmbeddedMedia, ...] = ()
    statements: Tuple[Statement, ...] = ()
    states: Mapping[str, State] = field(default_factory=dict)


def _freeze(mapping):
    return types.MappingProxyType(dict(mapping))


def _uncomment(line):
    quoted = False
    escaped = False
    for index, char in enumerate(line):
        if quoted and escaped:
            escaped = False
        elif quoted and char == "\\":
            escaped = True
        elif char == '"':
            quoted = not quoted
        elif char == "#" and not quoted:
            return line[:index]
    return line


def _string(text, line):
    if not _STRING.fullmatch(text):
        raise ScriptParseError(line, "expected a double-quoted string")
    raw = text.startswith('r"')
    body = text[2 if raw else 1:-1]
    if raw:
        return body
    result = []
    index = 0
    while index < len(body):
        if body[index] != "\\" or index + 1 == len(body):
            result.append(body[index])
        else:
            following = body[index + 1]
            if following in ('"', "\\", "<"):
                result.append(following)
            elif following == "$" and body[index + 2:index + 3] == "{":
                result.append("${")
                index += 1
            else:
                result.extend(("\\", following))
            index += 1
        index += 1
    return "".join(result)


def _identifier(value, line, what="identifier"):
    if not _IDENTIFIER.fullmatch(value) or value in _RESERVED:
        raise ScriptParseError(line, f"invalid {what}: {value!r}")
    return value


def _modifiers(text, line, allowed):
    if not text:
        return _freeze({})
    result = {}
    for part in text.split(","):
        key, separator, value = part.strip().partition(":")
        if not separator or not value.strip():
            raise ScriptParseError(line, "modifiers must use name: value")
        if key not in allowed:
            raise ScriptParseError(line, f"unknown modifier: {key}")
        if key in result:
            raise ScriptParseError(line, f"duplicate modifier: {key}")
        value = value.strip()
        if key in {"timeout", "deadline", "stable"}:
            if not _DURATION.fullmatch(value):
                raise ScriptParseError(
                    line, f"{key} must be a positive duration")
        elif key == "exclude":
            value = _string(value, line)
        result[key] = value
    return _freeze(result)


def _condition(text, line):
    text = text.strip()
    if text == "stopped":
        return Condition("stopped")
    if text.startswith("regex "):
        return Condition("regex", _string(text[6:].strip(), line))
    return Condition("text", _string(text, line))


def _removable_slot(value, line):
    """Normalize a removable drive slot name (``cdrom0``, ``floppy``)."""
    match = _REMOVABLE_SLOT.fullmatch(value)
    if not match:
        raise ScriptParseError(
            line, f"not a removable drive slot: {value!r} (expected "
            "floppy[0..1] or cdrom[0..3])")
    medium = match.group(1)
    slot = int(match.group(2) or 0)
    limit = _REMOVABLE_LIMITS[medium]
    if slot >= limit:
        raise ScriptParseError(
            line, f"invalid drive slot {value!r}: {medium} slots run "
            f"from 0 to {limit - 1}")
    return f"{medium}{slot}"


def _drive_slot(value, line):
    """Normalize any drive slot name (``hdd0``, ``cdrom``, ...)."""
    match = _DRIVE_SLOT.fullmatch(value)
    if not match:
        raise ScriptParseError(
            line, f"not a drive slot: {value!r} (expected "
            "floppy[0..1], hdd[0..3], or cdrom[0..3])")
    medium = match.group(1)
    slot = int(match.group(2) or 0)
    limit = _DRIVE_LIMITS[medium]
    if slot >= limit:
        raise ScriptParseError(
            line, f"invalid drive slot {value!r}: {medium} slots run "
            f"from 0 to {limit - 1}")
    return f"{medium}{slot}"


def _terminal(text, line):
    if text == "done":
        return Statement("done", line=line)
    if text.startswith("-> "):
        return Statement("transition", _identifier(text[3:].strip(), line,
                                                    "state name"), line=line)
    return None


def _statement(text, line):
    terminal = _terminal(text, line)
    if terminal is not None:
        return terminal
    verb, _, remainder = text.partition(" ")
    remainder = remainder.strip()
    argument, comma, modifiers = remainder.partition(",")
    if verb in {"wait", "enter", "type", "select"}:
        if not argument:
            raise ScriptParseError(line, f"{verb} requires an argument")
        allowed = {"timeout", "stable"} if verb == "wait" else set()
        if verb == "select":
            allowed = {"exclude"}
        return Statement(
            verb,
            (_condition(argument, line)
             if verb == "wait" else _string(argument, line)),
            _modifiers(modifiers if comma else "", line, allowed), line)
    if verb == "press":
        if comma or not remainder:
            raise ScriptParseError(line, "press requires only key names")
        keys = tuple(remainder.split())
        if not all(_KEY.fullmatch(key) for key in keys):
            raise ScriptParseError(line, "press contains an invalid key")
        return Statement("press", keys, line=line)
    if verb == "screenshot":
        if comma or (remainder and not _IDENTIFIER.fullmatch(remainder)):
            raise ScriptParseError(
                line, "screenshot accepts one optional name")
        return Statement("screenshot", remainder or None, line=line)
    if verb in {"insert", "eject"}:
        if comma:
            raise ScriptParseError(line, f"{verb} takes no modifiers")
        parts = remainder.split()
        if verb == "insert":
            if len(parts) != 2:
                raise ScriptParseError(
                    line, "insert requires a drive slot and a media name")
            slot = _removable_slot(parts[0], line)
            media_name = _identifier(parts[1], line, "media name")
            return Statement("insert", (slot, media_name), line=line)
        if len(parts) != 1:
            raise ScriptParseError(
                line, "eject requires exactly a drive slot")
        return Statement(
            "eject", _removable_slot(parts[0], line), line=line)
    if verb == "boot":
        if comma:
            raise ScriptParseError(line, "boot takes no modifiers")
        parts = remainder.split()
        if not parts:
            raise ScriptParseError(
                line, "boot requires at least one drive key")
        keys = []
        seen = set()
        for part in parts:
            key = _drive_slot(part, line)
            if key in seen:
                raise ScriptParseError(
                    line, f"boot contains duplicate drive {key}")
            seen.add(key)
            keys.append(key)
        return Statement("boot", tuple(keys), line=line)
    if verb in {"start", "stop"}:
        if remainder:
            raise ScriptParseError(line, f"{verb} takes no arguments")
        return Statement(verb, line=line)
    raise ScriptParseError(line, f"unknown statement: {verb}")


def _terminal_block(statements):
    """Whether a sequential block concludes on every final path."""
    if not statements:
        return False
    final = statements[-1]
    if final.verb in {"done", "transition"}:
        return True
    if final.verb == "expect":
        return all(_terminal_block(branch.statements)
                   for branch in final.argument)
    return False


def _transitions(statement):
    """Yield every transition named by a statement and its branches."""
    if statement.verb == "transition":
        yield statement
    elif statement.verb == "expect":
        for branch in statement.argument:
            for nested in branch.statements:
                yield from _transitions(nested)


class _Parser:
    def __init__(self, source):
        self.lines = [(number, _uncomment(line).strip())
                      for number, line in enumerate(source.splitlines(), 1)]
        self.index = 0

    def _next(self):
        while self.index < len(self.lines):
            item = self.lines[self.index]
            self.index += 1
            if item[1]:
                return item
        return None

    def _body(self, end_line, branches=False):
        statements = []
        while True:
            item = self._next()
            if item is None:
                raise ScriptParseError(end_line, "unclosed block")
            line, text = item
            if text == "}":
                return tuple(statements)
            if text.startswith("expect"):
                if branches:
                    raise ScriptParseError(line, "expect cannot be nested")
                statements.append(self._expect(text, line))
            else:
                statement = _statement(text, line)
                statements.append(statement)
                if statement.verb in {"done", "transition"}:
                    next_item = self._next()
                    if next_item is None or next_item[1] != "}":
                        raise ScriptParseError(
                            line, "a transition or done must end its block")
                    return tuple(statements)

    def _expect(self, text, line):
        head = text[6:].strip()
        if not head.endswith("{"):
            raise ScriptParseError(line, "expect must open a block")
        modifiers = _modifiers(head[:-1].strip(), line, {"timeout", "stable"})
        branches = []
        while True:
            item = self._next()
            if item is None:
                raise ScriptParseError(line, "unclosed expect block")
            branch_line, branch = item
            if branch == "}":
                if not branches:
                    raise ScriptParseError(line, "expect requires a branch")
                return Statement("expect", tuple(branches), modifiers, line)
            match = re.fullmatch(r"(.*):\s*\{", branch)
            if not match:
                raise ScriptParseError(branch_line, "expected condition: {")
            branches.append(ExpectBranch(
                _condition(match.group(1), branch_line),
                self._body(branch_line, branches=True), branch_line))

    def parse(self):
        headers = {}
        header_lines = {}
        media = []
        states = {}
        linear = []
        while (item := self._next()) is not None:
            line, text = item
            if text.startswith("media "):
                if states or linear:
                    raise ScriptParseError(
                        line,
                        "media definitions must precede executable content")
                label, separator, payload = text[6:].strip().partition(" ")
                _identifier(label, line, "media label")
                if not separator or not payload.startswith("{"):
                    raise ScriptParseError(
                        line, "media requires a JSON object")
                chunks = [payload]
                depth = payload.count("{") - payload.count("}")
                while depth > 0:
                    next_item = self._next()
                    if next_item is None:
                        raise ScriptParseError(
                            line, "unclosed media JSON object")
                    chunks.append(next_item[1])
                    depth += next_item[1].count("{") - next_item[1].count("}")
                try:
                    definition = parse_definition(
                        json.loads("\n".join(chunks)))
                except (json.JSONDecodeError, KeyError, ValueError) as error:
                    raise ScriptParseError(
                        line, f"invalid media definition: {error}") from error
                if any(entry.label == label for entry in media):
                    raise ScriptParseError(
                        line, f"duplicate media label: {label}")
                media.append(EmbeddedMedia(label, definition, line))
                continue
            if text.startswith("state "):
                if linear:
                    raise ScriptParseError(
                        line,
                        "state declarations cannot follow linear statements")
                match = re.fullmatch(r"state\s+([^,\s]+)(?:,(.*))?\s+\{", text)
                if not match:
                    raise ScriptParseError(line, "invalid state declaration")
                name = _identifier(match.group(1), line, "state name")
                if name in states:
                    raise ScriptParseError(line, f"duplicate state: {name}")
                statements = self._body(line)
                if not _terminal_block(statements):
                    raise ScriptParseError(
                        line,
                        "a sequential state must end in a transition or done")
                states[name] = State(
                    name, statements,
                    _modifiers(match.group(2) or "", line,
                               {"timeout", "deadline"}), line)
                continue
            match = re.fullmatch(
                r"(description|platform|initial|machine|timeout):\s*(.*)",
                text)
            if match:
                key, value = match.groups()
                if states or linear or media or key in headers:
                    raise ScriptParseError(
                        line, f"{key} must appear once in the header")
                if key in {"description"}:
                    value = _string(value, line)
                elif key == "timeout":
                    if not _DURATION.fullmatch(value):
                        raise ScriptParseError(
                            line, "timeout must be a positive duration")
                elif key == "machine":
                    if value not in ("running", "stopped"):
                        raise ScriptParseError(
                            line, "machine must be running or stopped")
                else:
                    value = _identifier(value, line, key)
                headers[key] = value
                header_lines[key] = line
                continue
            if states:
                raise ScriptParseError(
                    line, "only state declarations may follow a state")
            linear.append(_statement(text, line))
        if "platform" not in headers:
            raise ScriptParseError(1, "platform is required")
        if states and "initial" not in headers:
            raise ScriptParseError(
                next(iter(states.values())).line,
                "state-machine scripts require initial")
        if not states and "initial" in headers:
            raise ScriptParseError(
                header_lines["initial"],
                "linear scripts cannot declare initial")
        if states:
            if headers["initial"] not in states:
                raise ScriptParseError(
                    header_lines["initial"],
                    "initial names an undeclared state")
            for state in states.values():
                for statement in state.statements:
                    for transition in _transitions(statement):
                        if transition.argument not in states:
                            raise ScriptParseError(
                                transition.line,
                                "transition names undeclared state: "
                                f"{transition.argument}")
        return Script(headers["platform"], headers.get("description"),
                      headers.get("timeout"), headers.get("initial"),
                      headers.get("machine", "running"),
                      tuple(media), tuple(linear), _freeze(states))


def parse_script(source, path="<script>"):
    """Parse and statically validate a milestone-one ``.rqs`` document."""
    if not isinstance(source, str):
        raise TypeError("script source must be text")
    source = source.lstrip("\ufeff")
    try:
        return _Parser(source).parse()
    except ScriptParseError as error:
        error._set_context(path, source.splitlines())
        raise


def load_script(path):
    """Load and parse a UTF-8 ``.rqs`` file with path-aware diagnostics."""
    path = os.path.abspath(os.fspath(path))
    try:
        with open(path, encoding="utf-8") as handle:
            return parse_script(handle.read(), path=path)
    except FileNotFoundError:
        raise FileNotFoundError(f"Script not found: {path}") from None
