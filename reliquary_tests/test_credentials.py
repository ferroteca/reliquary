# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Secret properties: the credential store and the fail-safe order.

Spec: docs/spec/script-properties.md, "Secret storage".

Every test here runs against an in-memory provider, so the rules are
verified on any host. Only the thin keyring adapter is platform-bound,
and Windows is the delivered host (AGENTS.md).
"""

import os
import shutil
import tempfile
import unittest
from reliquary import credentials, properties
from reliquary.credentials import CredentialError
from reliquary.properties import PropertiesError


class FakeStore:
    """An in-memory stand-in for the host credential service."""

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


class SecretPropertyTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.store = FakeStore()
        self.previous = credentials._set_provider(self.store)

    def tearDown(self):
        credentials._set_provider(self.previous)
        shutil.rmtree(self.home)

    def path(self):
        return properties._properties_path(context=self.home)

    def read(self):
        with open(self.path(), "r", encoding="utf-8") as handle:
            return handle.read()

    def stored(self, key, path=None):
        scope = credentials.scope_for(path or self.path())
        return self.store.entries.get((scope, key))

    def test_the_value_goes_to_the_store_and_the_marker_to_the_file(self):
        properties.set_property(
            "accounts.default-password", "hunter2", secret=True,
            context=self.home)
        self.assertEqual(
            self.read(), "accounts.default-password = @secret\n")
        self.assertNotIn("hunter2", self.read())
        self.assertEqual(self.stored("accounts.default-password"), "hunter2")

    def test_reading_a_secret_never_returns_its_value(self):
        properties.set_property(
            "pw", "hunter2", secret=True, context=self.home)
        value = properties.get_property("pw", context=self.home)
        self.assertEqual(value, {"secret": True})
        self.assertTrue(
            properties.has_credential("pw", context=self.home))

    def test_listing_shows_markers_not_values(self):
        properties.set_property("plain", "visible", context=self.home)
        properties.set_property(
            "pw", "hunter2", secret=True, context=self.home)
        self.assertEqual(
            properties.list_properties(context=self.home),
            {"plain": "visible", "pw": {"secret": True}})

    def test_a_secret_may_be_replaced_by_another_secret(self):
        properties.set_property(
            "pw", "first", secret=True, context=self.home)
        properties.set_property(
            "pw", "second", secret=True, context=self.home)
        self.assertEqual(self.stored("pw"), "second")
        self.assertEqual(self.read(), "pw = @secret\n")

    def test_kind_changes_need_an_unset_first(self):
        properties.set_property("pw", "hunter2", secret=True,
                                context=self.home)
        with self.assertRaises(PropertiesError):
            properties.set_property("pw", "plain", context=self.home)
        properties.set_property("plain", "value", context=self.home)
        with self.assertRaises(PropertiesError):
            properties.set_property(
                "plain", "secret-value", secret=True, context=self.home)

    def test_unset_removes_marker_and_credential(self):
        properties.set_property(
            "pw", "hunter2", secret=True, context=self.home)
        properties.unset_property("pw", context=self.home)
        self.assertEqual(self.read(), "")
        self.assertIsNone(self.stored("pw"))

    def test_an_empty_secret_is_refused(self):
        with self.assertRaises(PropertiesError):
            properties.set_property("pw", "", secret=True, context=self.home)
        self.assertEqual(self.store.entries, {})


class FailSafeOrderTests(unittest.TestCase):
    """The two interruption points, and what each may leave behind."""

    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.store = FakeStore()
        self.previous = credentials._set_provider(self.store)

    def tearDown(self):
        credentials._set_provider(self.previous)
        shutil.rmtree(self.home)

    def path(self):
        return properties._properties_path(context=self.home)

    def scope(self):
        return credentials.scope_for(self.path())

    def test_a_set_interrupted_after_the_credential_leaves_no_marker(self):
        # The credential is stored first, so the only reachable
        # failure state is an orphan -- never a marker whose
        # credential was reported bound and is absent.
        original = properties._File.save

        def explode(self):
            raise OSError("interrupted before the marker landed")

        properties._File.save = explode
        try:
            with self.assertRaises(OSError):
                properties.set_property(
                    "pw", "hunter2", secret=True, context=self.home)
        finally:
            properties._File.save = original
        self.assertFalse(os.path.exists(self.path()))
        self.assertEqual(
            self.store.entries.get((self.scope(), "pw")), "hunter2")

    def test_an_orphaned_credential_blocks_an_ordinary_set(self):
        self.store.entries[(self.scope(), "pw")] = "hunter2"
        with self.assertRaises(PropertiesError) as caught:
            properties.set_property("pw", "plain", context=self.home)
        message = str(caught.exception)
        self.assertIn("orphaned credential", message)
        self.assertIn("unset-property pw", message)
        # The secret the user believes is stored is still there.
        self.assertEqual(
            self.store.entries.get((self.scope(), "pw")), "hunter2")

    def test_unset_is_the_cleanup_door_for_an_orphan(self):
        self.store.entries[(self.scope(), "pw")] = "hunter2"
        properties.unset_property("pw", context=self.home)
        self.assertEqual(self.store.entries, {})
        properties.set_property("pw", "plain", context=self.home)
        self.assertEqual(
            properties.get_property("pw", context=self.home), "plain")

    def test_a_marker_without_a_credential_reads_as_missing(self):
        with open(self.path(), "w", encoding="utf-8", newline="\n") as handle:
            handle.write("pw = @secret\n")
        self.assertEqual(
            properties.get_property("pw", context=self.home),
            {"secret": True})
        self.assertFalse(
            properties.has_credential("pw", context=self.home))


class NoStoreTests(unittest.TestCase):
    """A host with no usable store fails closed, never falls back."""

    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.previous = credentials._set_provider(FakeStore(broken=True))

    def tearDown(self):
        credentials._set_provider(self.previous)
        shutil.rmtree(self.home)

    def test_storing_a_secret_fails_closed(self):
        with self.assertRaises(CredentialError):
            properties.set_property(
                "pw", "hunter2", secret=True, context=self.home)
        path = properties._properties_path(context=self.home)
        self.assertFalse(os.path.exists(path))

    def test_ordinary_properties_still_work(self):
        properties.set_property("plain", "value", context=self.home)
        self.assertEqual(
            properties.get_property("plain", context=self.home), "value")
        properties.unset_property("plain", context=self.home)
        self.assertEqual(properties.list_properties(context=self.home), {})


class PropertiesFileSelectionTests(unittest.TestCase):
    """`--properties` replaces the home file, and scopes its secrets."""

    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.project = tempfile.mkdtemp()
        self.selected = os.path.join(self.project, "project.properties")
        self.store = FakeStore()
        self.previous = credentials._set_provider(self.store)

    def tearDown(self):
        credentials._set_provider(self.previous)
        shutil.rmtree(self.home)
        shutil.rmtree(self.project)

    def test_the_selected_file_replaces_the_home_file(self):
        properties.set_property("home-key", "home", context=self.home)
        properties.set_property(
            "project-key", "project", properties_file=self.selected)
        self.assertEqual(
            properties.list_properties(properties_file=self.selected),
            {"project-key": "project"})
        self.assertEqual(
            properties.list_properties(context=self.home),
            {"home-key": "home"})

    def test_secrets_scope_to_the_file_holding_the_marker(self):
        properties.set_property(
            "pw", "home-secret", secret=True, context=self.home)
        properties.set_property(
            "pw", "project-secret", secret=True,
            properties_file=self.selected)
        home_scope = credentials.scope_for(
            properties._properties_path(context=self.home))
        project_scope = credentials.scope_for(self.selected)
        self.assertNotEqual(home_scope, project_scope)
        self.assertEqual(
            self.store.entries[(home_scope, "pw")], "home-secret")
        self.assertEqual(
            self.store.entries[(project_scope, "pw")], "project-secret")

    def test_a_relative_selection_scopes_by_absolute_path(self):
        scope = credentials.scope_for("project.properties")
        self.assertIn(os.path.abspath("project.properties"), scope)

    def test_the_environment_selects_the_same_way(self):
        previous = os.environ.get("RELIQUARY_PROPERTIES")
        os.environ["RELIQUARY_PROPERTIES"] = self.selected
        try:
            properties.set_property("env-key", "value", context=self.home)
            self.assertTrue(os.path.exists(self.selected))
            self.assertEqual(
                properties.list_properties(context=self.home),
                {"env-key": "value"})
        finally:
            if previous is None:
                del os.environ["RELIQUARY_PROPERTIES"]
            else:
                os.environ["RELIQUARY_PROPERTIES"] = previous


if __name__ == "__main__":
    unittest.main()
