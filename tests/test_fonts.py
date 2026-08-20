# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for authored glyph fonts: the declaration and the @ pool (F61)."""

import json
import os

import pytest

from reliquary import Context
from reliquary.errors import PreflightError, StaticError
from reliquary.fonts import (FontError, load_font_bank,
                             load_font_declaration, load_font_namespace,
                             resolve_font)

_BANK = bytes(range(256)) * 16  # 4096 bytes, no particular shape


def _write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(obj, handle)


def _write_bytes(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(data)


@pytest.fixture
def home(tmp_path):
    return str(tmp_path / "home")


def _write_font(home, name, *, cell_rows=16, codepage="cp437",
                bank=_BANK, subdir=""):
    declaration = os.path.join(home, "fonts", subdir, f"{name}.rlqf")
    _write_json(declaration, {"cell-rows": cell_rows, "codepage": codepage})
    if bank is not None:
        _write_bytes(os.path.join(home, "fonts", subdir, f"{name}.bin"),
                     bank)
    return declaration


def test_a_font_resolves_by_stem_and_loads_its_bank(home):
    _write_font(home, "guest", cell_rows=8, codepage="cp850")
    context = Context(home_dir=home)
    namespace = load_font_namespace(context)
    assert set(namespace) == {"guest"}
    declaration = namespace["guest"]
    assert declaration.cell_rows == 8
    assert declaration.codepage == "cp850"

    bank = load_font_bank("guest", context)
    assert bank == _BANK
    assert bank.cell_rows == 8
    assert bank.codepage == "cp850"
    assert bank.source == "@guest"


def test_a_missing_bank_fails_closed(home):
    _write_font(home, "guest", bank=None)
    with pytest.raises(FontError) as caught:
        load_font_namespace(Context(home_dir=home))
    assert caught.value.rule_id == "font.no-bank"
    assert "guest.bin" in str(caught.value)


def test_a_bad_cell_rows_fails_closed(home):
    _write_font(home, "guest", cell_rows=12)
    with pytest.raises(FontError) as caught:
        load_font_namespace(Context(home_dir=home))
    assert caught.value.rule_id == "font.bad-cell-rows"


def test_an_unknown_codepage_fails_closed(home):
    _write_font(home, "guest", codepage="not-a-real-codec")
    with pytest.raises(FontError) as caught:
        load_font_namespace(Context(home_dir=home))
    assert caught.value.rule_id == "font.unknown-codepage"


def test_a_wrong_length_bank_fails_closed(home):
    _write_font(home, "guest", bank=b"\x00" * 100)
    context = Context(home_dir=home)
    load_font_namespace(context)  # the declaration alone is still valid
    with pytest.raises(StaticError) as caught:
        load_font_bank("guest", context)
    assert caught.value.rule_id == "recognize.font-corrupt"


def test_two_files_resolving_to_one_stem_collide(home):
    _write_font(home, "guest", subdir="a")
    _write_font(home, "guest", subdir="b")
    with pytest.raises(PreflightError) as caught:
        load_font_namespace(Context(home_dir=home))
    assert caught.value.rule_id == "name.asset-collision"


def test_an_unknown_font_name_fails_closed(home):
    namespace = load_font_namespace(Context(home_dir=home))
    with pytest.raises(PreflightError) as caught:
        resolve_font("nope", namespace)
    assert caught.value.rule_id == "font.unknown"


def test_a_font_sharing_a_medias_name_collides(home):
    _write_font(home, "guest")
    blueprints = os.path.join(home, "blueprints")
    _write_json(os.path.join(blueprints, "lib.rlqb"),
               [{"type": "media", "name": "guest",
                 "location": {"local": "/X.iso"}}])
    with pytest.raises(PreflightError) as caught:
        load_font_namespace(Context(home_dir=home))
    assert caught.value.rule_id == "name.pool-collision"


def test_the_pool_collision_is_case_insensitive(home):
    _write_font(home, "guest")
    blueprints = os.path.join(home, "blueprints")
    _write_json(os.path.join(blueprints, "lib.rlqb"),
               [{"type": "media", "name": "Guest",
                 "location": {"local": "/X.iso"}}])
    with pytest.raises(PreflightError) as caught:
        load_font_namespace(Context(home_dir=home))
    assert caught.value.rule_id == "name.pool-collision"
