# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for working-directory resolution: the six placeable dirs.

There is no process-global assignment any more (P26): the ``Context``
record a session is opened on carries everything, so what is asserted
here is the record's own resolution — slots, derivation, the
fail-closed refusal — and that nothing ambient stands behind it.
"""

import os

import pytest

from reliquary import home
from reliquary.errors import StaticError

#: The six placeable directories and the function that answers for
#: each — one node per directory, so a resolver that stops failing
#: closed is named.
RESOLVERS = {
    "home": home.home_dir,
    "blueprints": home.blueprints_dir,
    "scripts": home.scripts_dir,
    "cache": home.cache_dir,
    "media": home.media_dir,
    "machines": home.machines_dir,
}


# An empty record holds nothing, and asking is an error.

@pytest.mark.parametrize("name", sorted(RESOLVERS))
def test_each_directory_fails_closed_naming_itself(name):
    with pytest.raises(StaticError) as caught:
        RESOLVERS[name]()
    assert "'%s'" % name in str(caught.value)
    assert caught.value.rule_id == "dir.unassigned"


def test_the_error_names_the_directory_asked_for():
    """Not the unassigned ancestor, which nobody asked about."""
    with pytest.raises(StaticError) as caught:
        home.media_dir()
    message = str(caught.value)
    assert "no directory assigned for 'media'" in message
    assert "--media-dir" in message
    assert "RELIQUARY_MEDIA_DIR" in message
    # The ancestors appear as the other way to supply it.
    assert "'cache' or 'home'" in message


# The variables name themselves; the library reads none of them.

def test_the_variable_name_follows_the_flag():
    assert home.environment_variable("home") == "RELIQUARY_HOME"
    assert home.environment_variable("blueprints") == (
        "RELIQUARY_BLUEPRINTS_DIR")


def test_the_environment_is_never_read(monkeypatch):
    """A library must not acquire a directory from the shell.

    The environment is honoured by the CLI's own construction
    step and nowhere else, so an exported variable changes
    nothing about an engine call's resolution.
    """
    monkeypatch.setenv(home.environment_variable("home"),
                       os.path.join("env", "home"))
    with pytest.raises(StaticError):
        home.home_dir()


# A record's slots cascade, and only into what is unassigned.

def test_a_home_reaches_all_six():
    context = home.Context(home_dir=os.path.join("some", "home"))
    root = os.path.abspath(os.path.join("some", "home"))
    assert home.home_dir(context) == root
    assert home.blueprints_dir(context) == os.path.join(root, "blueprints")
    assert home.scripts_dir(context) == os.path.join(root, "scripts")
    assert home.cache_dir(context) == os.path.join(root, "cache")
    assert home.media_dir(context) == os.path.join(root, "cache", "media")
    assert home.machines_dir(context) == os.path.join(
        root, "cache", "machines")


def test_an_explicit_cache_wins_over_the_derived_one():
    context = home.Context(home_dir=os.path.join("some", "home"),
                           cache_dir=os.path.join("fast", "disk"))
    fast = os.path.abspath(os.path.join("fast", "disk"))
    assert home.cache_dir(context) == fast
    assert home.media_dir(context) == os.path.join(fast, "media")
    assert home.blueprints_dir(context) == os.path.join(
        os.path.abspath(os.path.join("some", "home")), "blueprints")


def test_cache_alone_conjures_no_home():
    context = home.Context(cache_dir=os.path.join("only", "cache"))
    assert home.media_dir(context) == os.path.join(
        os.path.abspath(os.path.join("only", "cache")), "media")
    with pytest.raises(StaticError):
        home.home_dir(context)
    with pytest.raises(StaticError):
        home.blueprints_dir(context)


def test_machines_alone_leaves_media_where_the_rest_puts_it():
    context = home.Context(home_dir=os.path.join("some", "home"),
                           machines_dir=os.path.join("big", "disk"))
    assert home.machines_dir(context) == os.path.abspath(
        os.path.join("big", "disk"))
    assert home.media_dir(context) == os.path.join(
        os.path.abspath(os.path.join("some", "home")), "cache", "media")


def test_bare_string_is_sugar_for_the_home():
    assert home.blueprints_dir(os.path.join("scoped", "home")) == (
        os.path.join(os.path.abspath(os.path.join("scoped", "home")),
                     "blueprints"))


def test_a_context_may_be_built_before_it_is_usable():
    """The refusal fires at use, not at record construction."""
    assert home.Context().media_dir is None


# The record-only resolution the session pins at its door.

def test_a_home_alone_fills_all_six():
    pinned = home.pinned(os.path.join("some", "home"))
    root = os.path.abspath(os.path.join("some", "home"))
    assert pinned.home_dir == root
    assert pinned.blueprints_dir == os.path.join(root, "blueprints")
    assert pinned.scripts_dir == os.path.join(root, "scripts")
    assert pinned.cache_dir == os.path.join(root, "cache")
    assert pinned.media_dir == os.path.join(root, "cache", "media")
    assert pinned.machines_dir == os.path.join(root, "cache", "machines")


def test_an_explicit_slot_wins_over_derivation():
    pinned = home.pinned(home.Context(
        home_dir=os.path.join("some", "home"),
        cache_dir=os.path.join("fast", "disk")))
    fast = os.path.abspath(os.path.join("fast", "disk"))
    assert pinned.cache_dir == fast
    assert pinned.media_dir == os.path.join(fast, "media")


def test_what_the_record_cannot_derive_stays_none():
    pinned = home.pinned(home.Context(
        cache_dir=os.path.join("only", "cache")))
    assert pinned.home_dir is None
    assert pinned.blueprints_dir is None
    assert pinned.media_dir == os.path.join(
        os.path.abspath(os.path.join("only", "cache")), "media")


def test_the_properties_file_rides_along():
    pinned = home.pinned(home.Context(
        home_dir=os.path.join("some", "home"),
        properties_file=os.path.join("some", "project.properties")))
    assert pinned.properties_file == os.path.abspath(
        os.path.join("some", "project.properties"))


# There is no seeding axis at all: a miss is a miss (D88).
#
# The knob these tests used to exercise is deleted rather than
# defaulted, so what is left to assert is its absence — a context
# carries the working directories and the selected properties file
# (P26's cargo) and nothing that decides where a name may come from.

def test_the_record_carries_no_seeding_slot():
    assert home.Context.__slots__ == (
        "home_dir", "blueprints_dir", "scripts_dir", "cache_dir",
        "media_dir", "machines_dir", "properties_file")


def test_no_seeding_switch_survives():
    for gone in ("autoseed", "set_autoseed", "_autoseed"):
        assert not hasattr(home, gone), gone


def test_the_global_machinery_is_deleted():
    """The carrier mechanism P26 retired is gone, not dormant.

    The directory globals, their setters, the environment adoption
    and the assignment probe were deleted with the surface move; a
    survivor here would be a second carrier waiting to disagree with
    the record.
    """
    for gone in ("_globals", "_assign", "set_home_dir",
                 "set_blueprints_dir", "set_scripts_dir",
                 "set_cache_dir", "set_media_dir",
                 "set_machines_dir", "is_assigned",
                 "adopt_environment"):
        assert not hasattr(home, gone), gone


# The value the CLI assigns when the caller named no home.

def test_default_home_is_named_reliquary():
    assert os.path.basename(home.default_home_dir()) == "reliquary"


def test_default_home_is_absolute():
    assert os.path.isabs(home.default_home_dir())
