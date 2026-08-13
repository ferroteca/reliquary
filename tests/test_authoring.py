# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for authoring the files a user owns.

Composed-blueprint parsing is covered by test_document.py; this
module covers the ``new_blueprint`` / ``add_media`` /
``delete_blueprint`` / ``delete_script`` file surface — and in
particular the refusal both removals share, each answering from its
own place: a blueprint while machines of it exist, a script while
blueprints reference it.
"""

import json
import os

import pytest

from reliquary.authoring import (delete_blueprint, delete_script,
                                 new_blueprint)
from reliquary.document import parse_document
from reliquary.errors import PreflightError
from reliquary.home import blueprints_dir


@pytest.fixture
def home(tmp_path):
    return str(tmp_path)


# Scaffolding a blueprint.

def test_scaffolds_a_composed_blueprint(home):
    path = new_blueprint("test-bp", context=home)
    assert os.path.exists(path)
    assert path.endswith(".rlqb")
    with open(path, encoding="utf-8") as handle:
        content = handle.read()
    assert "// Machine blueprint for test-bp" in content
    data = json.loads("\n".join(line for line in content.splitlines()
                                if not line.strip().startswith("//")))
    assert "version" not in data
    # The scaffold parses under the composed model with the given name.
    doc = parse_document(data, stem="test-bp")
    assert "test-bp" in doc.machines
    assert doc.machines["test-bp"].platform == "dos"


def test_already_exists_raises(home):
    new_blueprint("test-bp", context=home)
    with pytest.raises(PreflightError):
        new_blueprint("test-bp", context=home)


# Removing one, and what refuses.

def test_deletes_rlqb(home):
    path = new_blueprint("test-bp", context=home)
    removed = delete_blueprint("test-bp", context=home)
    assert removed == path
    assert not os.path.exists(path)


def test_deletes_legacy_json(home):
    path = os.path.join(home, "blueprints", "legacy.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("{}\n")
    removed = delete_blueprint("legacy", context=home)
    assert removed == path
    assert not os.path.exists(path)


def test_missing_blueprint_raises(home):
    with pytest.raises(PreflightError) as caught:
        delete_blueprint("missing", context=home)
    assert "blueprint not found" in str(caught.value)


def test_refuses_while_machines_exist(home):
    new_blueprint("plain", context=home)
    machine_dir = os.path.join(home, "cache", "machines", "plain-0")
    os.makedirs(machine_dir)
    with open(os.path.join(machine_dir, "machine.json"), "w",
              encoding="utf-8") as handle:
        json.dump({"id": "plain-0", "blueprint": "plain",
                   "phase": "ready"}, handle)
    with pytest.raises(PreflightError) as caught:
        delete_blueprint("plain", context=home)
    message = str(caught.value)
    assert "still has 1 machine(s)" in message
    assert "plain-0" in message
    assert os.path.exists(os.path.join(home, "blueprints", "plain.rlqb"))


def test_a_codex_blueprint_is_not_deleted(home):
    with pytest.raises(PreflightError):
        delete_blueprint("freedos", context=home)


# The script half of the same shape.

def _write_script(home, name,
                  content="description \"test\"\nplatform dos\n"):
    path = os.path.join(home, "scripts", f"{name}.rlqs")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    return path


def _write_blueprint(home, name, scripts=None):
    path = os.path.join(blueprints_dir(home), f"{name}.rlqb")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = [{"type": "machine", "name": name, "platform": "dos",
             "scripts": scripts or {}}]
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle)
    return path


def test_deletes_rlqs(home):
    path = _write_script(home, "test-script")
    removed = delete_script("test-script", context=home)
    assert removed == path
    assert not os.path.exists(path)


def test_missing_script_raises(home):
    with pytest.raises(PreflightError) as caught:
        delete_script("missing", context=home)
    assert "script not found" in str(caught.value).lower()
    assert caught.value.rule_id == "script.unknown"


def test_refuses_while_blueprints_refer_to_it(home):
    _write_script(home, "useful")
    _write_blueprint(home, "my-machine", scripts={"run": "useful"})

    with pytest.raises(PreflightError) as caught:
        delete_script("useful", context=home)

    message = str(caught.value)
    assert "still has 1 blueprint(s)" in message
    assert "my-machine" in message
    assert caught.value.rule_id == "script.has-blueprints"
    assert os.path.exists(os.path.join(home, "scripts", "useful.rlqs"))


def test_a_codex_script_is_not_deleted(home):
    # freedos-install is in the codex
    with pytest.raises(PreflightError):
        delete_script("freedos-install", context=home)
