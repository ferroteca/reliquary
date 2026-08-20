# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Authored glyph fonts: the declaration, and the shared ``@`` pool (F61).

A font is one authored asset per file, stem-identified like a script
(``assets.py``) rather than name-fielded like a blueprint or media --
``<name>.rlqf``, a JSON5 declaration, with ``<name>.bin`` beside it by
stem adjacency: the raw 4096-byte bank
(``planning/design/authored-binary-assets.md``, "the binaries sit
beside it, attached by adjacency"). What the declaration states is
exactly what the bytes cannot say (D109): the cell geometry -- 256
glyphs of 16 rows and 512 of 8 are the same 4096 bytes, so it is
declared rather than inferred (P10) -- and the codepage its indices
mean, decoded through Python's own codec registry rather than a
bespoke table this module would otherwise have to carry.

Resolution is the ordinary one: ``.rlqf`` files walk out of
``home.fonts_dir`` (``assets.py``), indexed by filename stem, and a
name is checked against the one ``@`` pool media (and, once built,
landmark) names already share -- a font claiming a name a media
already holds is an error naming both files.
"""

import codecs
import os
import types
from dataclasses import dataclass

from . import assets, json5reader, resolve
from .errors import PreflightError, StaticError
from .text_recognize import Bank, check_bank

#: The two geometries a 4096-byte bank can declare (D109): 256 glyphs
#: of 16 rows, or 512 of 8 -- Reliquary only ever addresses the first
#: 256 either way, its codes being the ordinary 8-bit CP437 range.
_CELL_ROWS = (8, 16)


class FontError(StaticError):
    """A font declaration diagnostic that can say *where* it happened.

    The legality tier, like every other authored-document diagnostic:
    decided from the declaration's own text, so it is a STATIC ERROR
    and exits ``2``, rendered by the same skeleton
    :class:`document.BlueprintError` and
    :class:`script_nodes.ScriptParseError` already use (D70).
    """

    def __init__(self, message, *, rule_id=None, path=None, position=None):
        super().__init__(message, rule_id=rule_id)
        self.message = message
        self.path = path
        self.line, self.column = position if position else (None, None)

    def __str__(self):
        cited = f" ({self.rule_id})" if self.rule_id else ""
        if self.line is None:
            return f"{self.path or '<font>'}: error: {self.message}{cited}"
        return (f"{self.path}:{self.line}:{self.column}: "
                f"error: {self.message}{cited}")


@dataclass(frozen=True)
class FontDeclaration:
    """One parsed ``.rlqf`` document: its geometry, codepage, and bank."""

    name: str
    cell_rows: int
    codepage: str
    path: str
    bin_path: str


def _field_error(doc, path, key, message, rule_id):
    position = json5reader.position_of(doc, key) or json5reader.position(doc)
    return FontError(message, rule_id=rule_id, path=path, position=position)


def load_font_declaration(path):
    """Parse and validate one ``.rlqf`` file, failing closed by name.

    The three refusals work item 1 owes: ``cell-rows`` outside
    ``{8, 16}``, a ``codepage`` no codec registry entry answers to
    (:func:`codecs.lookup`, so this module carries no codepage table
    of its own), and a declaration with no adjacent bank file. A
    bank whose *length* disagrees with its declared geometry is
    caught later, when the bank is actually read
    (:func:`load_font_bank`) -- every valid ``cell-rows`` implies the
    same 4096-byte total, so the check is the ordinary
    :func:`text_recognize.check_bank` one.
    """
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    try:
        doc = json5reader.loads(text, positions=True)
    except StaticError as error:
        raise FontError(str(error), rule_id=getattr(error, "rule_id", None),
                        path=path) from error
    if not isinstance(doc, dict):
        raise FontError("a font declaration must be a JSON5 object",
                        rule_id="font.not-an-object", path=path)

    cell_rows = doc.get("cell-rows")
    if cell_rows not in _CELL_ROWS:
        raise _field_error(
            doc, path, "cell-rows",
            f"cell-rows must be 8 or 16 (256 or 512 glyphs), "
            f"got {cell_rows!r}", "font.bad-cell-rows")
    codepage = doc.get("codepage")
    if not isinstance(codepage, str):
        raise _field_error(
            doc, path, "codepage",
            f"codepage must be a string naming a codec, got {codepage!r}",
            "font.bad-codepage")
    try:
        codecs.lookup(codepage)
    except LookupError:
        raise _field_error(
            doc, path, "codepage", f"unknown codepage {codepage!r}",
            "font.unknown-codepage") from None

    name = assets.stem(path)
    bin_path = os.path.join(os.path.dirname(path), f"{name}.bin")
    if not os.path.isfile(bin_path):
        raise FontError(
            f"no bank file {os.path.basename(bin_path)!r} beside "
            f"declaration {os.path.basename(path)!r}",
            rule_id="font.no-bank", path=path)

    return FontDeclaration(name=name, cell_rows=cell_rows, codepage=codepage,
                           path=path, bin_path=bin_path)


def load_font_namespace(context=None):
    """``{name: FontDeclaration}`` for every ``.rlqf`` the source holds.

    Collision-checked against the shared ``@`` pool media names
    already occupy (``authored-binary-assets.md``, "one reference
    pool") -- a font and a media claiming the same name is an error
    naming both files, folded case-insensitively like every other
    name in this pool (:func:`resolve.build_namespace`'s own rule).
    """
    source = assets.source_for(context)
    index = assets.index_by_name(
        source.candidate_files("font"), lambda _path: None, kind="font")
    declarations = {name: load_font_declaration(path)
                    for name, path in index.items()}
    media = resolve.load_namespace(context).media
    folded_media = {existing.lower(): existing for existing in media}
    for name, declaration in declarations.items():
        other = folded_media.get(name.lower())
        if other is not None:
            raise PreflightError(
                f"font {name!r} and media {other!r} share the @ pool "
                f"({'the same name' if other == name else 'names that '
                    'differ only by case'}):\n"
                f"  {declaration.path}\n"
                f"  a media spec named {other!r}",
                rule_id="name.pool-collision")
    return types.MappingProxyType(declarations)


def resolve_font(name, namespace):
    """Return the :class:`FontDeclaration` named ``name``, or fail closed."""
    try:
        return namespace[name]
    except KeyError:
        raise PreflightError(f"no font named {name!r}",
                             rule_id="font.unknown") from None


def load_font_bank(name, context=None):
    """Resolve ``@name`` through the font source and return its ``Bank``.

    The bank a script's ``font`` statement actually reads through:
    the declaration's geometry and codepage, folded onto the raw
    bytes (:func:`text_recognize.Bank`), labelled ``@name`` for the
    failure report's "fonts tried".
    """
    declaration = resolve_font(name, load_font_namespace(context))
    with open(declaration.bin_path, "rb") as handle:
        data = handle.read()
    data = check_bank(data, declaration.bin_path)
    return Bank(data, cell_rows=declaration.cell_rows,
               codepage=declaration.codepage, source=f"@{declaration.name}")
