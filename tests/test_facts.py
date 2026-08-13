# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The rlq.* run facts (milestone 8, T4)."""

import os
from unittest import mock

import pytest

from reliquary import facts
from reliquary.errors import InternalError


def test_is_fact_recognizes_the_namespace():
    assert facts.is_fact("rlq.host.username")
    assert facts.is_fact("rlq.host.full-name")
    assert facts.is_fact("rlq.env.ANYTHING")
    assert not facts.is_fact("owner")
    assert not facts.is_fact("rlqhost")


def test_an_unknown_rlq_key_raises():
    with pytest.raises(InternalError):
        facts.resolve("rlq.host.nonesuch")


def test_username_is_login_normalized():
    with mock.patch("reliquary.facts.getpass.getuser",
                    return_value="Ada Lovelace!"):
        assert facts.resolve("rlq.host.username") == "ada-lovelace"


def test_username_that_normalizes_to_nothing_is_unanswerable():
    with mock.patch("reliquary.facts.getpass.getuser", return_value="!!!"):
        assert facts.resolve("rlq.host.username") is None


def test_an_unresolvable_login_is_unanswerable():
    with mock.patch("reliquary.facts.getpass.getuser", side_effect=OSError):
        assert facts.resolve("rlq.host.username") is None


def test_env_fact_reads_verbatim():
    with mock.patch.dict(os.environ, {"MY_FACT": "  spaced value  "}):
        assert facts.resolve("rlq.env.MY_FACT") == "  spaced value  "


def test_an_unset_or_empty_env_fact_is_unanswerable(monkeypatch):
    monkeypatch.setenv("EMPTY_FACT", "")
    assert facts.resolve("rlq.env.EMPTY_FACT") is None
    monkeypatch.delenv("MISSING_FACT", raising=False)
    assert facts.resolve("rlq.env.MISSING_FACT") is None


def test_an_empty_env_name_is_unanswerable():
    assert facts.resolve("rlq.env.") is None
