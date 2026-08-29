# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The line-based user properties file.

Spec: docs/spec/script-properties.md.
"""

import os

import pytest

from reliquary import credentials, home, properties
from reliquary.properties import PropertiesError
from tests.test_credentials import FakeStore


@pytest.fixture(scope="module", autouse=True)
def fake_credential_store():
    """Never let the unit suite reach the host's real credential store."""
    previous = credentials._set_provider(FakeStore())
    yield
    credentials._set_provider(previous)


@pytest.fixture
def home_dir(tmp_path):
    return str(tmp_path)


def _path(home_dir):
    return properties._properties_path(context=home_dir)


def _write(home_dir, text):
    path = _path(home_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return path


def _read(home_dir):
    with open(_path(home_dir), "r", encoding="utf-8") as handle:
        return handle.read()


# The file itself: what a read sees and what an edit leaves behind.

def test_absent_file_has_no_properties(home_dir):
    assert properties.get_property(
        "identity.full-name", context=home_dir) is None
    assert properties.list_properties(context=home_dir) == {}


def test_set_creates_the_file_and_get_reads_it(home_dir):
    properties.set_property(
        "identity.full-name", "Paul Galbraith", context=home_dir)
    assert properties.get_property(
        "identity.full-name", context=home_dir) == "Paul Galbraith"
    assert _read(home_dir) == "identity.full-name = Paul Galbraith\n"


def test_values_are_verbatim_to_end_of_line(home_dir):
    # No quoting, no escapes, no comment stripping mid-line.
    _write(home_dir, "greeting = hello = world # not a comment\n")
    assert properties.get_property("greeting", context=home_dir) == (
        "hello = world # not a comment")


def test_comments_blanks_and_order_survive_a_set(home_dir):
    _write(home_dir,
           "# reliquary user properties\n"
           "identity.full-name = Paul Galbraith\n"
           "\n"
           "# the zeta key sorts first on purpose\n"
           "zeta = last\n"
           "alpha = first\n")
    properties.set_property("zeta", "changed", context=home_dir)
    assert _read(home_dir) == (
        "# reliquary user properties\n"
        "identity.full-name = Paul Galbraith\n"
        "\n"
        "# the zeta key sorts first on purpose\n"
        "zeta = changed\n"
        "alpha = first\n")


def test_unset_removes_only_its_own_line(home_dir):
    _write(home_dir,
           "# keep me\n"
           "alpha = one\n"
           "beta = two\n"
           "\n"
           "gamma = three\n")
    properties.unset_property("beta", context=home_dir)
    assert _read(home_dir) == (
        "# keep me\n"
        "alpha = one\n"
        "\n"
        "gamma = three\n")


def test_unset_then_set_still_edits_the_right_lines(home_dir):
    # The index bookkeeping after a deletion is easy to get wrong.
    _write(home_dir, "alpha = one\nbeta = two\ngamma = three\n")
    properties.unset_property("alpha", context=home_dir)
    properties.set_property("gamma", "changed", context=home_dir)
    assert _read(home_dir) == "beta = two\ngamma = changed\n"


def test_set_appends_a_new_key(home_dir):
    _write(home_dir, "# header\nalpha = one\n")
    properties.set_property("beta", "two", context=home_dir)
    assert _read(home_dir) == "# header\nalpha = one\nbeta = two\n"


def test_unset_missing_key_is_quiet(home_dir):
    _write(home_dir, "alpha = one\n")
    properties.unset_property("beta", context=home_dir)
    assert _read(home_dir) == "alpha = one\n"


def test_a_crlf_file_keeps_its_line_endings(home_dir):
    # A file hand-edited in a Windows editor must not come back
    # rewritten end to end just because one line changed.
    _write(home_dir, "# header\r\nalpha = one\r\nbeta = two\r\n")
    properties.set_property("alpha", "changed", context=home_dir)
    with open(_path(home_dir), "r", encoding="utf-8",
              newline="") as handle:
        assert handle.read() == (
            "# header\r\nalpha = changed\r\nbeta = two\r\n")


def test_an_lf_file_keeps_its_line_endings(home_dir):
    _write(home_dir, "alpha = one\nbeta = two\n")
    properties.set_property("gamma", "three", context=home_dir)
    with open(_path(home_dir), "r", encoding="utf-8",
              newline="") as handle:
        assert handle.read() == "alpha = one\nbeta = two\ngamma = three\n"


def test_a_file_without_a_final_newline_gains_one(home_dir):
    _write(home_dir, "alpha = one")
    properties.set_property("beta", "two", context=home_dir)
    assert _read(home_dir) == "alpha = one\nbeta = two\n"


def test_whitespace_around_the_separator_is_trimmed(home_dir):
    _write(home_dir, "alpha=one\n  beta   =   two  \n")
    assert properties.list_properties(context=home_dir) == {
        "alpha": "one", "beta": "two"}


def test_listing_sorts_and_prefix_selects_a_namespace(home_dir):
    _write(home_dir,
           "products.windows-98.install-key = k\n"
           "identity.full-name = Paul\n"
           "products.windows-98 = ninety-eight\n"
           "products.windows-98-extra = not-a-descendant\n")
    assert list(properties.list_properties(context=home_dir)) == [
        "identity.full-name", "products.windows-98",
        "products.windows-98-extra", "products.windows-98.install-key"]
    assert properties.list_properties(
        "products.windows-98", context=home_dir) == {
        "products.windows-98": "ninety-eight",
        "products.windows-98.install-key": "k"}


# Value kinds: the leading `@` and what it reserves.

def test_secret_marker_reads_as_the_marker_never_a_value(home_dir):
    _write(home_dir, "accounts.default-password = @secret\n")
    value = properties.get_property(
        "accounts.default-password", context=home_dir)
    assert properties.is_secret(value)
    assert value == {"secret": True}


def test_literal_at_sign_is_doubled(home_dir):
    _write(home_dir, "handle = @@paul\n")
    assert properties.get_property("handle", context=home_dir) == "@paul"


def test_unknown_value_kind_fails_closed(home_dir):
    _write(home_dir, "handle = @nonesuch\n")
    with pytest.raises(PropertiesError) as caught:
        properties.get_property("handle", context=home_dir)
    assert "reserved" in str(caught.value)
    assert ":1:" in str(caught.value)


def test_setting_a_value_with_a_leading_at_escapes_it(home_dir):
    properties.set_property("handle", "@paul", context=home_dir)
    assert properties.get_property("handle", context=home_dir) == "@paul"


def test_an_ordinary_value_may_read_back_as_secret_text(home_dir):
    properties.set_property("decoy", "@secret", context=home_dir)
    assert properties.get_property("decoy", context=home_dir) == "@secret"
    assert not properties.is_secret(
        properties.get_property("decoy", context=home_dir))


def test_ordinary_over_a_secret_needs_an_unset_first(home_dir):
    _write(home_dir, "accounts.default-password = @secret\n")
    with pytest.raises(PropertiesError) as caught:
        properties.set_property(
            "accounts.default-password", "plain", context=home_dir)
    assert "unset" in str(caught.value)


def test_values_that_would_not_round_trip_are_refused(home_dir):
    for value in (" padded", "padded ", "two\nlines"):
        with pytest.raises(PropertiesError):
            properties.set_property("alpha", value, context=home_dir)


def test_a_non_string_value_is_refused(home_dir):
    with pytest.raises(PropertiesError):
        properties.set_property("alpha", 42, context=home_dir)


# Key rules.

def test_valid_keys():
    for key in ("alpha", "identity.full-name", "a.b.c",
                "products.windows-98.install-key", "x_y"):
        assert properties._check_key(key) == key


def test_invalid_keys():
    for key in ("", "9lives", ".leading", "trailing.",
                "two..dots", "has space", "-dash", "_under",
                "seg.9nine"):
        try:
            properties._check_key(key)
        except PropertiesError:
            continue
        raise AssertionError(f"{key!r} was accepted as a key")


def test_reserved_namespaces():
    for key in ("rlq", "rlq.host.username", "reliquary",
                "reliquary.anything"):
        with pytest.raises(PropertiesError) as caught:
            properties._check_key(key)
        assert "reserved" in str(caught.value), key


def test_keys_are_case_sensitive(home_dir):
    properties.set_property("alpha", "lower", context=home_dir)
    properties.set_property("Alpha", "upper", context=home_dir)
    assert properties.list_properties(context=home_dir) == {
        "Alpha": "upper", "alpha": "lower"}


# A malformed file is named, and never partly rewritten.

def test_a_line_without_a_separator_names_its_line(home_dir):
    path = _write(home_dir, "alpha = one\nnonsense\n")
    with pytest.raises(PropertiesError) as caught:
        properties.list_properties(context=home_dir)
    message = str(caught.value)
    assert path in message
    assert ":2:" in message


def test_an_invalid_key_names_its_line(home_dir):
    _write(home_dir, "alpha = one\n9lives = two\n")
    with pytest.raises(PropertiesError) as caught:
        properties.list_properties(context=home_dir)
    assert ":2:" in str(caught.value)


def test_a_duplicate_key_names_both_lines(home_dir):
    _write(home_dir, "alpha = one\n# comment\nalpha = two\n")
    with pytest.raises(PropertiesError) as caught:
        properties.list_properties(context=home_dir)
    message = str(caught.value)
    assert ":3:" in message
    assert "line 1" in message


def test_an_invalid_file_is_never_partly_rewritten(home_dir):
    original = "alpha = one\nnonsense\n"
    _write(home_dir, original)
    with pytest.raises(PropertiesError):
        properties.set_property("beta", "two", context=home_dir)
    with open(_path(home_dir), "r", encoding="utf-8") as handle:
        assert handle.read() == original


def test_a_failed_write_leaves_no_temporary_file(home_dir):
    properties.set_property("alpha", "one", context=home_dir)
    directory = os.path.dirname(_path(home_dir))
    assert [name for name in os.listdir(directory)
            if name.startswith(".user.properties.")] == []


# A ``Context`` carries the selected properties file, which is part
# of what P26 requires it to carry.

def test_a_context_slot_selects_the_file(home_dir):
    selected = os.path.join(home_dir, "project.properties")
    context = home.Context(home_dir=home_dir, properties_file=selected)
    properties.set_property("key", "value", context=context)
    assert os.path.isfile(selected)
    assert properties.get_property("key", context=context) == "value"
    # It replaces the home's file rather than layering over it.
    assert properties.get_property("key", context=home_dir) is None


def test_an_explicit_argument_beats_the_context_slot(home_dir):
    argument = os.path.join(home_dir, "argument.properties")
    context = home.Context(
        home_dir=home_dir,
        properties_file=os.path.join(home_dir, "slot.properties"))
    properties.set_property("key", "value", context=context,
                            properties_file=argument)
    assert os.path.isfile(argument)
    assert not os.path.exists(os.path.join(home_dir, "slot.properties"))


def test_the_environment_is_never_read(home_dir, monkeypatch):
    # RELIQUARY_PROPERTIES only reaches the properties_file slot on
    # the Context, and only the CLI's construction step reads that
    # env var -- the engine itself never does. With no slot set, the
    # home directory's own file is used.
    monkeypatch.setenv("RELIQUARY_PROPERTIES",
                       os.path.join(home_dir, "env.properties"))
    context = home.Context(home_dir=home_dir)
    properties.set_property("key", "value", context=context)
    assert os.path.isfile(_path(home_dir))
    assert not os.path.exists(os.path.join(home_dir, "env.properties"))
