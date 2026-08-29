# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for the Session object: ambient state resolved once and reused by every call (P26).

``Session`` is deliberately unexported while the module-level
surface stands, so these tests import ``reliquary.session``
directly. Each Session method is a thin wrapper with no logic of
its own — the real behavior for each family of calls is tested in
its own module's suite — so what these tests check is the
constructor: the refusal to construct without a home directory, the
Context record being pinned (copied) at construction so a later
change to the original does not reach the session, the selected
properties file being carried on that record, thin forwarding
through one representative verb per family, that every wrapper
method really is that thin, and the two-sessions-two-homes case that
module-level globals could never support.
"""

import inspect
import json
import os

import pytest

from reliquary import (authoring, binding, credentials, library,
                       machines, media, properties, resolve,
                       script_runner)
from reliquary.errors import StaticError
from reliquary.home import Context
from reliquary.script_parser import parse_script
from reliquary.session import Session
from tests import fake_backend
from tests.test_credentials import FakeStore


@pytest.fixture(scope="module", autouse=True)
def fake_credential_store():
    """Never let the unit suite reach the host's real credential store."""
    previous = credentials._set_provider(FakeStore())
    yield
    credentials._set_provider(previous)


@pytest.fixture
def home(tmp_path):
    """A temp home for every test."""
    return str(tmp_path)


@pytest.fixture
def other(tmp_path):
    """A second home, for the two-sessions case."""
    second = tmp_path / "other"
    second.mkdir()
    return str(second)


def _write_blueprint(home_dir, name):
    """A composed one-machine blueprint with a blank disk."""
    specs = [
        {"type": "machine", "name": name, "platform": "dos",
         "devices": {"hdd0": "blank"}},
        {"type": "media", "name": "blank", "materialize": "new",
         "size": "20M"},
    ]
    bpdir = os.path.join(home_dir, "blueprints")
    os.makedirs(bpdir, exist_ok=True)
    with open(os.path.join(bpdir, f"{name}.rlqb"), "w",
              encoding="utf-8") as handle:
        json.dump(specs, handle)


# The constructor: a home directory opens a session, and nothing
# else does.

def test_a_bare_home_string_opens_a_session(home):
    session = Session(home)
    assert session.get_property("unset.key") is None


def test_a_context_opens_a_session(home):
    session = Session(Context(home_dir=home))
    assert session.list_machines() == []


@pytest.mark.parametrize("homeless", [None, "", "empty", "cache-only"])
def test_no_home_refuses_naming_it(home, homeless):
    # The same condition first-use ``dir.unassigned`` names,
    # caught here at construction instead: one rule, one id.
    context = {"empty": Context(),
               "cache-only": Context(cache_dir=home)}.get(homeless, homeless)
    with pytest.raises(StaticError) as caught:
        Session(context)
    assert "home" in str(caught.value)
    assert caught.value.rule_id == "dir.unassigned"


def test_an_explicit_slot_pins_and_the_rest_derive(home):
    fast = os.path.join(home, "fast")
    session = Session(Context(home_dir=home, cache_dir=fast))
    assert session.machine_dir_path("bp-1") == os.path.join(
        fast, "machines", "bp-1")


def test_the_record_is_copied_at_the_door(home):
    record = Context(home_dir=home)
    session = Session(record)
    record.home_dir = os.path.join(home, "moved")
    session.set_property("session.test.where", "original")
    assert os.path.isfile(os.path.join(home, "user.properties"))


# Two sessions in one process are unremarkable.

def test_two_homes_interleave_without_interference(home, other):
    # The case the process globals could never state.
    first = Session(home)
    second = Session(other)
    first.set_property("session.test.name", "first")
    second.set_property("session.test.name", "second")
    first.new_blueprint("alpha")
    second.new_blueprint("beta")
    assert first.get_property("session.test.name") == "first"
    assert second.get_property("session.test.name") == "second"
    assert [entry["name"] for entry in first.list_blueprints()] == ["alpha"]
    assert [entry["name"] for entry in second.list_blueprints()] == ["beta"]


def test_machines_materialize_under_their_own_session(home, other):
    with fake_backend.installed():
        first = Session(home)
        second = Session(other)
        _write_blueprint(home, "freedos")
        machine_id = first.create_machine("freedos")
        assert [state["id"] for state in first.list_machines()] == [
            machine_id]
        assert second.list_machines() == []
        assert first.get_machine_dir(machine=machine_id).startswith(
            os.path.join(home, "cache"))
        first.destroy_machine(machine_id)
        assert first.list_machines() == []


# The selected properties file rides in the record (P26).

def _selected(home):
    return os.path.join(home, "project.properties")


def test_the_record_carries_the_selected_file(home):
    session = Session(Context(home_dir=home,
                              properties_file=_selected(home)))
    session.set_property("cargo.key", "value")
    assert os.path.isfile(_selected(home))
    assert not os.path.isfile(os.path.join(home, "user.properties"))
    assert session.get_property("cargo.key") == "value"


def test_the_selection_replaces_rather_than_layers(home):
    properties.set_property("only.home", "home value", context=home)
    session = Session(Context(home_dir=home,
                              properties_file=_selected(home)))
    assert session.get_property("only.home") is None


def test_the_environment_is_never_read(home, monkeypatch):
    # RELIQUARY_PROPERTIES is the CLI's construction step; a
    # session with no selection uses the home's file, whatever
    # the shell exports.
    env_file = os.path.join(home, "env.properties")
    monkeypatch.setenv("RELIQUARY_PROPERTIES", env_file)
    session = Session(home)
    session.set_property("which.file", "the home's own")
    assert os.path.isfile(os.path.join(home, "user.properties"))
    assert not os.path.exists(env_file)


def test_a_secret_scopes_to_the_selected_file(home):
    session = Session(Context(home_dir=home,
                              properties_file=_selected(home)))
    session.set_property("service.token", "hunter2", secret=True)
    assert session.has_credential("service.token")
    assert properties.is_secret(session.get_property("service.token"))
    # Scoped by the selected file's absolute path, not the home's.
    assert not properties.has_credential("service.token", context=home)


def test_binding_answers_from_the_carried_selection(home):
    session = Session(Context(home_dir=home,
                              properties_file=_selected(home)))
    session.set_property("answered", "from the selected file")
    script = parse_script("property answered\n")
    assert session.describe_sources(script) == {"answered": binding.FILE}


# One representative verb per family, called on a constructed Session.

def test_blueprint_authoring_and_resolution(home):
    session = Session(home)
    path = session.new_blueprint("freedos")
    assert os.path.dirname(path) == os.path.join(home, "blueprints")
    namespace = session.load_namespace()
    assert "blank-256m" in namespace.media
    assert session.list_media() == ["blank-256m"]
    payload = os.path.join(home, "payload.img")
    with open(payload, "wb") as handle:
        handle.write(b"PAYLOAD")
    session.add_media("payload", payload)
    assert session.list_media() == ["blank-256m", "payload"]
    session.delete_blueprint("payload")
    assert session.list_media() == ["blank-256m"]


def test_machine_lifecycle_state_and_variables(home):
    with fake_backend.installed():
        session = Session(home)
        _write_blueprint(home, "freedos")
        machine_id = session.create_machine("freedos")
        assert session.resolve_machine(blueprint="freedos") == machine_id
        assert session.load_machine_state(machine_id)["id"] == machine_id
        # The channel's only writer is the script `set` verb;
        # simulate its write through the engine.
        machines.set_machine_var(machine_id, "step", "created",
                                 context=home)
        assert session.get_machine_var("step", machine=machine_id) == (
            "created")
        session.destroy_machine(machine_id)


def test_a_dry_script_run_through_the_session(home):
    session = Session(home)
    scripts = os.path.join(home, "scripts")
    os.makedirs(scripts)
    with open(os.path.join(scripts, "hello.rlqs"), "w",
              encoding="utf-8", newline="\n") as handle:
        handle.write('platform dos\nwait "C:\\>"\n')
    run = session.run_script("hello", dry_run=True)
    assert run.operation == "run-script"
    assert run.plan["tier"] == "static"


#: Every wrapper method, named against the engine function it forwards to.
#: The dict is the roster: a method the session lacks, or one it
#: grew that no engine verb backs, fails the completeness check.
_AMBIENT = frozenset({"context", "properties_file"})
_VENEERS = {
    "create_machine": machines.create_machine,
    "recreate_machine": machines.recreate_machine,
    "start_machine": machines.start_machine,
    "stop_machine": machines.stop_machine,
    "restart_machine": machines.restart_machine,
    "destroy_machine": machines.destroy_machine,
    "apply_blueprint": machines.apply_blueprint,
    "get_machine_dir": machines.get_machine_dir,
    "list_machines": machines.list_machines,
    "resolve_machine": machines.resolve_machine,
    "load_machine_state": machines.load_machine_state,
    "machine_dir_path": machines.machine_dir_path,
    "mark_stopped": machines.mark_stopped,
    "insert_media": machines.insert_media,
    "eject_media": machines.eject_media,
    "set_boot_order": machines.set_boot_order,
    "exec": machines.exec,
    "wait_ready": machines.wait_ready,
    "get_machine_var": machines.get_machine_var,
    "wait_machine_var": machines.wait_machine_var,
    "fetch_media": media.fetch_media,
    "list_media": media.list_media,
    "clean_media": media.clean_media,
    "prune_media": media.prune_media,
    "new_blueprint": authoring.new_blueprint,
    "add_media": authoring.add_media,
    "delete_blueprint": authoring.delete_blueprint,
    "delete_script": authoring.delete_script,
    "load_namespace": resolve.load_namespace,
    "list_blueprints": library.list_blueprints,
    "list_scripts": library.list_scripts,
    "get_property": properties.get_property,
    "has_credential": properties.has_credential,
    "set_property": properties.set_property,
    "unset_property": properties.unset_property,
    "list_properties": properties.list_properties,
    "bind_properties": binding.bind_properties,
    "describe_sources": binding.describe_sources,
    "run_script": script_runner.run_script,
}


# Each wrapper method is thin and complete, checked mechanically.
# One method per ambient-state verb, its signature the engine verb's
# minus the ambient parameters the session carries — so an engine
# verb growing a parameter fails here rather than drifting apart
# from its wrapper, and it fails as the *named* verb rather than as
# one method reporting for all forty-four.

@pytest.mark.parametrize("name", sorted(_VENEERS))
def test_every_veneer_mirrors_its_engine_verb(name):
    veneer = list(inspect.signature(
        getattr(Session, name)).parameters.values())
    assert veneer[0].name == "self"
    mirrored = [(p.name, p.kind, p.default) for p in veneer[1:]]
    engine_shape = [
        (p.name, p.kind, p.default)
        for p in inspect.signature(_VENEERS[name]).parameters.values()
        if p.name not in _AMBIENT]
    assert mirrored == engine_shape


def test_the_session_carries_exactly_the_veneers():
    public = {name for name in dir(Session)
              if not name.startswith("_")
              and callable(getattr(Session, name))}
    assert public == set(_VENEERS)
