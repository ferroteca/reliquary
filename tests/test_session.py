# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""The Session object: ambient state carried once (P26).

``Session`` is deliberately unexported while the module-level
surface stands, so these tests import ``reliquary.session``
directly. The veneer carries no logic — each family's behavior is
its own module's suite — so what is asserted here is the door: the
construction refusal, the record pinned at construction from the
record alone, the properties-file cargo, thin forwarding through a
representative verb per family, the mechanical thinness of every
veneer, and the two-sessions-two-homes case the process globals
could never state.
"""

import inspect
import json
import os
import tempfile
import unittest

from reliquary import (authoring, binding, credentials, library,
                       machines, media, properties, resolve,
                       script_runner)
from reliquary.errors import StaticError
from reliquary.home import Context
from reliquary.script_parser import parse_script
from reliquary.session import Session
from tests import fake_backend
from tests.test_credentials import FakeStore

_provider = None


def setUpModule():
    """Never let the unit suite reach the host's real credential store."""
    global _provider
    _provider = credentials._set_provider(FakeStore())


def tearDownModule():
    credentials._set_provider(_provider)


def _write_blueprint(home_dir, name):
    """A composed one-machine blueprint with a blank disk."""
    specs = [
        {"type": "machine", "name": name, "platform": "dos",
         "drives": {"hdd0": "blank"}},
        {"type": "media", "name": "blank", "materialize": "new",
         "size": "20M"},
    ]
    bpdir = os.path.join(home_dir, "blueprints")
    os.makedirs(bpdir, exist_ok=True)
    with open(os.path.join(bpdir, f"{name}.rlqb"), "w",
              encoding="utf-8") as handle:
        json.dump(specs, handle)


class _SessionCase(unittest.TestCase):
    """A temp home for every test."""

    def setUp(self):
        self.workdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.workdir.cleanup)
        self.home = self.workdir.name

    def _pin_env(self, variable, value):
        saved = os.environ.get(variable)

        def restore():
            if saved is None:
                os.environ.pop(variable, None)
            else:
                os.environ[variable] = saved

        self.addCleanup(restore)
        os.environ[variable] = value


class ConstructionTests(_SessionCase):
    """The door: a home opens it, and nothing else does."""

    def test_a_bare_home_string_opens_a_session(self):
        session = Session(self.home)
        self.assertIsNone(session.get_property("unset.key"))

    def test_a_context_opens_a_session(self):
        session = Session(Context(home_dir=self.home))
        self.assertEqual(session.list_machines(), [])

    def test_no_home_refuses_naming_it(self):
        # The same condition first-use ``dir.unassigned`` names,
        # noticed at the door: one rule, one id.
        for context in (None, "", Context(),
                        Context(cache_dir=self.home)):
            with self.subTest(context=context):
                with self.assertRaises(StaticError) as caught:
                    Session(context)
                self.assertIn("home", str(caught.exception))
                self.assertEqual(caught.exception.rule_id,
                                 "dir.unassigned")

    def test_an_explicit_slot_pins_and_the_rest_derive(self):
        fast = os.path.join(self.home, "fast")
        session = Session(Context(home_dir=self.home, cache_dir=fast))
        self.assertEqual(
            session.machine_dir_path("bp-1"),
            os.path.join(fast, "machines", "bp-1"))

    def test_the_record_is_copied_at_the_door(self):
        record = Context(home_dir=self.home)
        session = Session(record)
        record.home_dir = os.path.join(self.home, "moved")
        session.set_property("session.test.where", "original")
        self.assertTrue(os.path.isfile(
            os.path.join(self.home, "user.properties")))


class TwoSessionsTests(_SessionCase):
    """Two sessions in one process are unremarkable."""

    def setUp(self):
        super().setUp()
        self.second = tempfile.TemporaryDirectory()
        self.addCleanup(self.second.cleanup)
        self.other = self.second.name

    def test_two_homes_interleave_without_interference(self):
        # The case the process globals could never state.
        first = Session(self.home)
        second = Session(self.other)
        first.set_property("session.test.name", "first")
        second.set_property("session.test.name", "second")
        first.new_blueprint("alpha")
        second.new_blueprint("beta")
        self.assertEqual(first.get_property("session.test.name"),
                         "first")
        self.assertEqual(second.get_property("session.test.name"),
                         "second")
        self.assertEqual(
            [entry["name"] for entry in first.list_blueprints()],
            ["alpha"])
        self.assertEqual(
            [entry["name"] for entry in second.list_blueprints()],
            ["beta"])

    def test_machines_materialize_under_their_own_session(self):
        with fake_backend.installed():
            first = Session(self.home)
            second = Session(self.other)
            _write_blueprint(self.home, "freedos")
            machine_id = first.create_machine("freedos")
            self.assertEqual(
                [state["id"] for state in first.list_machines()],
                [machine_id])
            self.assertEqual(second.list_machines(), [])
            self.assertTrue(
                first.get_machine_dir(machine=machine_id)
                .startswith(os.path.join(self.home, "cache")))
            first.destroy_machine(machine_id)
            self.assertEqual(first.list_machines(), [])


class CargoTests(_SessionCase):
    """The selected properties file rides in the record (P26)."""

    def _selected(self):
        return os.path.join(self.home, "project.properties")

    def test_the_record_carries_the_selected_file(self):
        session = Session(Context(home_dir=self.home,
                                  properties_file=self._selected()))
        session.set_property("cargo.key", "value")
        self.assertTrue(os.path.isfile(self._selected()))
        self.assertFalse(os.path.isfile(
            os.path.join(self.home, "user.properties")))
        self.assertEqual(session.get_property("cargo.key"), "value")

    def test_the_selection_replaces_rather_than_layers(self):
        properties.set_property("only.home", "home value",
                                context=self.home)
        session = Session(Context(home_dir=self.home,
                                  properties_file=self._selected()))
        self.assertIsNone(session.get_property("only.home"))

    def test_the_environment_is_never_read(self):
        # RELIQUARY_PROPERTIES is the CLI's construction step; a
        # session with no selection uses the home's file, whatever
        # the shell exports.
        env_file = os.path.join(self.home, "env.properties")
        self._pin_env("RELIQUARY_PROPERTIES", env_file)
        session = Session(self.home)
        session.set_property("which.file", "the home's own")
        self.assertTrue(os.path.isfile(
            os.path.join(self.home, "user.properties")))
        self.assertFalse(os.path.exists(env_file))

    def test_a_secret_scopes_to_the_selected_file(self):
        session = Session(Context(home_dir=self.home,
                                  properties_file=self._selected()))
        session.set_property("service.token", "hunter2", secret=True)
        self.assertTrue(session.has_credential("service.token"))
        self.assertTrue(properties.is_secret(
            session.get_property("service.token")))
        # Scoped by the selected file's absolute path, not the home's.
        self.assertFalse(properties.has_credential(
            "service.token", context=self.home))

    def test_binding_answers_from_the_carried_selection(self):
        session = Session(Context(home_dir=self.home,
                                  properties_file=self._selected()))
        session.set_property("answered", "from the selected file")
        script = parse_script("property answered\n")
        self.assertEqual(session.describe_sources(script),
                         {"answered": binding.FILE})


class VeneerTests(_SessionCase):
    """A representative verb per family, driven through the door."""

    def test_blueprint_authoring_and_resolution(self):
        session = Session(self.home)
        path = session.new_blueprint("freedos")
        self.assertEqual(
            os.path.dirname(path),
            os.path.join(self.home, "blueprints"))
        namespace = session.load_namespace()
        self.assertIn("blank-256m", namespace.media)
        self.assertEqual(session.list_media(), ["blank-256m"])
        payload = os.path.join(self.home, "payload.img")
        with open(payload, "wb") as handle:
            handle.write(b"PAYLOAD")
        session.add_media("payload", payload)
        self.assertEqual(session.list_media(),
                         ["blank-256m", "payload"])
        session.delete_blueprint("payload")
        self.assertEqual(session.list_media(), ["blank-256m"])

    def test_machine_lifecycle_state_and_variables(self):
        with fake_backend.installed():
            session = Session(self.home)
            _write_blueprint(self.home, "freedos")
            machine_id = session.create_machine("freedos")
            self.assertEqual(
                session.resolve_machine(blueprint="freedos"),
                machine_id)
            self.assertEqual(
                session.load_machine_state(machine_id)["id"],
                machine_id)
            # The channel's only writer is the script `set` verb;
            # simulate its write through the engine.
            machines.set_machine_var(machine_id, "step", "created",
                                     context=self.home)
            self.assertEqual(
                session.get_machine_var("step", machine=machine_id),
                "created")
            session.destroy_machine(machine_id)

    def test_a_dry_script_run_through_the_session(self):
        session = Session(self.home)
        scripts = os.path.join(self.home, "scripts")
        os.makedirs(scripts)
        with open(os.path.join(scripts, "hello.rlqs"), "w",
                  encoding="utf-8", newline="\n") as handle:
            handle.write('platform dos\nwait "C:\\>"\n')
        run = session.run_script("hello", dry_run=True)
        self.assertEqual(run.operation, "run-script")
        self.assertEqual(run.plan["tier"], "static")


#: Every veneer, named against the engine function it forwards to.
#: The dict is the roster: a method the session lacks, or one it
#: grew that no engine verb backs, fails the completeness check.
_AMBIENT = frozenset({"context", "properties_file"})
_VENEERS = {
    "create_machine": machines.create_machine,
    "recreate_machine": machines.recreate_machine,
    "start_machine": machines.start_machine,
    "stop_machine": machines.stop_machine,
    "destroy_machine": machines.destroy_machine,
    "apply_blueprint": machines.apply_blueprint,
    "get_machine_dir": machines.get_machine_dir,
    "list_machines": machines.list_machines,
    "resolve_machine": machines.resolve_machine,
    "load_machine_state": machines.load_machine_state,
    "machine_dir_path": machines.machine_dir_path,
    "mark_stopped": machines.mark_stopped,
    "describe_drives": machines.describe_drives,
    "refresh_drives": machines.refresh_drives,
    "insert_media": machines.insert_media,
    "eject_media": machines.eject_media,
    "set_boot_order": machines.set_boot_order,
    "exec": machines.exec,
    "put_file": machines.put_file,
    "get_file": machines.get_file,
    "put_files": machines.put_files,
    "get_files": machines.get_files,
    "list_files": machines.list_files,
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


class VeneerShapeTests(unittest.TestCase):
    """The veneer is thin and complete, mechanically.

    One method per ambient-state verb, its signature the engine
    verb's minus the ambient parameters the session carries — so an
    engine verb growing a parameter fails here rather than drifting
    apart from its veneer.
    """

    def test_every_veneer_mirrors_its_engine_verb(self):
        for name, engine in sorted(_VENEERS.items()):
            with self.subTest(name):
                veneer = list(inspect.signature(
                    getattr(Session, name)).parameters.values())
                self.assertEqual(veneer[0].name, "self")
                mirrored = [(p.name, p.kind, p.default)
                            for p in veneer[1:]]
                engine_shape = [
                    (p.name, p.kind, p.default)
                    for p in inspect.signature(
                        engine).parameters.values()
                    if p.name not in _AMBIENT]
                self.assertEqual(mirrored, engine_shape)

    def test_the_session_carries_exactly_the_veneers(self):
        public = {name for name in dir(Session)
                  if not name.startswith("_")
                  and callable(getattr(Session, name))}
        self.assertEqual(public, set(_VENEERS))


if __name__ == "__main__":
    unittest.main()
