# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Secret properties: the credential store and the fail-safe order.

Spec: docs/spec/script-properties.md, "Secret storage".

Every test here runs against an in-memory provider, so the rules are
verified on any host. Only the thin keyring adapter is platform-bound,
and Windows is the delivered host (AGENTS.md).
"""

import os

import pytest

from reliquary import credentials, properties
from reliquary.credentials import CredentialError
from reliquary.home import Context
from reliquary.properties import PropertiesError


class FakeStore:
    """An in-memory stand-in for the host credential service.

    Imported by every module that must not reach the real store
    (`test_properties`, `test_session`), which is why it lives here
    rather than in a fixture.
    """

    def __init__(self, broken=False):
        self.entries = {}
        self.broken = broken

    def _check(self):
        if self.broken:
            raise CredentialError("this host has no usable credential store")

    def get_password(self, service, name):
        self._check()
        return self.entries.get((service, name))

    def set_password(self, service, name, value):
        self._check()
        self.entries[(service, name)] = value

    def delete_password(self, service, name):
        self._check()
        self.entries.pop((service, name), None)


@pytest.fixture
def home(tmp_path):
    return str(tmp_path / "home")


@pytest.fixture
def store():
    """An in-memory credential provider, uninstalled with the test."""
    fake = FakeStore()
    previous = credentials._set_provider(fake)
    yield fake
    credentials._set_provider(previous)


@pytest.fixture
def broken_store():
    """A host whose credential service cannot be used at all."""
    previous = credentials._set_provider(FakeStore(broken=True))
    yield
    credentials._set_provider(previous)


def _path(home):
    return properties._properties_path(context=home)


def _read(home):
    with open(_path(home), "r", encoding="utf-8") as handle:
        return handle.read()


def _stored(store, home, key):
    return store.entries.get((credentials.scope_for(_path(home)), key))


# The marker in the file, the value in the store.

def test_the_value_goes_to_the_store_and_the_marker_to_the_file(store, home):
    properties.set_property("accounts.default-password", "hunter2",
                            secret=True, context=home)
    assert _read(home) == "accounts.default-password = @secret\n"
    assert "hunter2" not in _read(home)
    assert _stored(store, home, "accounts.default-password") == "hunter2"


def test_reading_a_secret_never_returns_its_value(store, home):
    properties.set_property("pw", "hunter2", secret=True, context=home)
    assert properties.get_property("pw", context=home) == {"secret": True}
    assert properties.has_credential("pw", context=home)


def test_listing_shows_markers_not_values(store, home):
    properties.set_property("plain", "visible", context=home)
    properties.set_property("pw", "hunter2", secret=True, context=home)
    assert properties.list_properties(context=home) == {
        "plain": "visible", "pw": {"secret": True}}


def test_a_secret_may_be_replaced_by_another_secret(store, home):
    properties.set_property("pw", "first", secret=True, context=home)
    properties.set_property("pw", "second", secret=True, context=home)
    assert _stored(store, home, "pw") == "second"
    assert _read(home) == "pw = @secret\n"


def test_kind_changes_need_an_unset_first(store, home):
    properties.set_property("pw", "hunter2", secret=True, context=home)
    with pytest.raises(PropertiesError):
        properties.set_property("pw", "plain", context=home)
    properties.set_property("plain", "value", context=home)
    with pytest.raises(PropertiesError):
        properties.set_property("plain", "secret-value", secret=True,
                                context=home)


def test_unset_removes_marker_and_credential(store, home):
    properties.set_property("pw", "hunter2", secret=True, context=home)
    properties.unset_property("pw", context=home)
    assert _read(home) == ""
    assert _stored(store, home, "pw") is None


def test_an_empty_secret_is_refused(store, home):
    with pytest.raises(PropertiesError):
        properties.set_property("pw", "", secret=True, context=home)
    assert store.entries == {}


# The two interruption points, and what each may leave behind.

def test_a_set_interrupted_after_the_credential_leaves_no_marker(
        store, home, monkeypatch):
    # The credential is stored first, so the only reachable
    # failure state is an orphan -- never a marker whose
    # credential was reported bound and is absent.
    def explode(self):
        raise OSError("interrupted before the marker landed")

    monkeypatch.setattr(properties._File, "save", explode)
    with pytest.raises(OSError):
        properties.set_property("pw", "hunter2", secret=True, context=home)
    monkeypatch.undo()
    assert not os.path.exists(_path(home))
    assert _stored(store, home, "pw") == "hunter2"


def test_an_orphaned_credential_blocks_an_ordinary_set(store, home):
    store.entries[(credentials.scope_for(_path(home)), "pw")] = "hunter2"
    with pytest.raises(PropertiesError) as caught:
        properties.set_property("pw", "plain", context=home)
    message = str(caught.value)
    assert "orphaned credential" in message
    assert "unset-property pw" in message
    # The secret the user believes is stored is still there.
    assert _stored(store, home, "pw") == "hunter2"


def test_unset_is_the_cleanup_door_for_an_orphan(store, home):
    store.entries[(credentials.scope_for(_path(home)), "pw")] = "hunter2"
    properties.unset_property("pw", context=home)
    assert store.entries == {}
    properties.set_property("pw", "plain", context=home)
    assert properties.get_property("pw", context=home) == "plain"


def test_a_marker_without_a_credential_reads_as_missing(store, home):
    os.makedirs(os.path.dirname(_path(home)), exist_ok=True)
    with open(_path(home), "w", encoding="utf-8", newline="\n") as handle:
        handle.write("pw = @secret\n")
    assert properties.get_property("pw", context=home) == {"secret": True}
    assert not properties.has_credential("pw", context=home)


# A host with no usable store fails closed, never falls back.

def test_storing_a_secret_fails_closed(broken_store, home):
    with pytest.raises(CredentialError):
        properties.set_property("pw", "hunter2", secret=True, context=home)
    assert not os.path.exists(_path(home))


def test_ordinary_properties_still_work(broken_store, home):
    properties.set_property("plain", "value", context=home)
    assert properties.get_property("plain", context=home) == "value"
    properties.unset_property("plain", context=home)
    assert properties.list_properties(context=home) == {}


# `--properties` replaces the home file, and scopes its secrets.

@pytest.fixture
def selected(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    return str(project / "project.properties")


def test_the_selected_file_replaces_the_home_file(store, home, selected):
    properties.set_property("home-key", "home", context=home)
    properties.set_property("project-key", "project",
                            properties_file=selected)
    assert properties.list_properties(properties_file=selected) == {
        "project-key": "project"}
    assert properties.list_properties(context=home) == {"home-key": "home"}


def test_secrets_scope_to_the_file_holding_the_marker(store, home,
                                                      selected):
    properties.set_property("pw", "home-secret", secret=True, context=home)
    properties.set_property("pw", "project-secret", secret=True,
                            properties_file=selected)
    home_scope = credentials.scope_for(_path(home))
    project_scope = credentials.scope_for(selected)
    assert home_scope != project_scope
    assert store.entries[(home_scope, "pw")] == "home-secret"
    assert store.entries[(project_scope, "pw")] == "project-secret"


def test_a_relative_selection_scopes_by_absolute_path():
    scope = credentials.scope_for("project.properties")
    assert os.path.abspath("project.properties") in scope


def test_the_record_slot_selects_the_same_way(store, home, selected):
    # The selection rides in the record (P26's cargo). The
    # environment spelling is the CLI's construction step: the
    # engine reads no environment, so the slot is the one
    # programmatic channel.
    context = Context(home_dir=home, properties_file=selected)
    properties.set_property("env-key", "value", context=context)
    assert os.path.exists(selected)
    assert properties.list_properties(context=context) == {
        "env-key": "value"}
