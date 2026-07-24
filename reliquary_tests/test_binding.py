# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""The property binding pipeline (milestone 8, T3).

Order: --property, blueprint parameter, environment, properties file,
interactive ask. The declared derivation (T4) slots between file and
ask later. Spec: planning/design/script-spec.md, "The property
sources".
"""

import os
import shutil
import tempfile
import unittest
from reliquary import binding, credentials, properties
from reliquary.binding import (BoundProperties, PropertyBindingError,
                               bind_properties, describe_sources)
from reliquary.script_parser import parse_script
from reliquary_tests.test_credentials import FakeStore


def script(text):
    return parse_script(text)


class _EnvGuard:
    """Set RELIQUARY_PROPERTY_* variables and restore them after."""

    def __init__(self, **values):
        self.values = values
        self.saved = {}

    def __enter__(self):
        for name, value in self.values.items():
            self.saved[name] = os.environ.get(name)
            os.environ[name] = value
        return self

    def __exit__(self, *exc):
        for name, previous in self.saved.items():
            if previous is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = previous


class SourceOrderTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.store = FakeStore()
        self.previous = credentials._set_provider(self.store)

    def tearDown(self):
        credentials._set_provider(self.previous)
        shutil.rmtree(self.home)

    def bind(self, text, **kwargs):
        kwargs.setdefault("context", self.home)
        return bind_properties(script(text), **kwargs)

    def test_flag_beats_every_other_source(self):
        properties.set_property("owner", "from-file", context=self.home)
        with _EnvGuard(RELIQUARY_PROPERTY_OWNER="from-env"):
            bound = self.bind(
                "property owner\n",
                explicit={"owner": "from-flag"},
                parameters={"owner": "from-parameter"})
        self.assertEqual(bound.values["owner"], "from-flag")
        self.assertEqual(bound.sources["owner"], binding.FLAG)

    def test_parameter_beats_env_and_file(self):
        properties.set_property("owner", "from-file", context=self.home)
        with _EnvGuard(RELIQUARY_PROPERTY_OWNER="from-env"):
            bound = self.bind(
                "property owner\n", parameters={"owner": "from-parameter"})
        self.assertEqual(bound.values["owner"], "from-parameter")
        self.assertEqual(bound.sources["owner"], binding.PARAMETER)

    def test_env_beats_file(self):
        properties.set_property("owner", "from-file", context=self.home)
        with _EnvGuard(RELIQUARY_PROPERTY_OWNER="from-env"):
            bound = self.bind("property owner\n")
        self.assertEqual(bound.values["owner"], "from-env")
        self.assertEqual(bound.sources["owner"], binding.ENVIRONMENT)

    def test_file_answers_when_nothing_above_does(self):
        properties.set_property("owner", "from-file", context=self.home)
        bound = self.bind("property owner\n")
        self.assertEqual(bound.values["owner"], "from-file")
        self.assertEqual(bound.sources["owner"], binding.FILE)

    def test_ask_is_last_and_only_when_offered(self):
        asked = []

        def asker(key, prompt, secret):
            asked.append((key, prompt, secret))
            return "from-ask"

        bound = self.bind(
            'property owner prompt="Owner"\n', asker=asker)
        self.assertEqual(bound.values["owner"], "from-ask")
        self.assertEqual(bound.sources["owner"], binding.ASK)
        self.assertEqual(asked, [("owner", "Owner", False)])

    def test_noninteractive_unbound_fails_closed(self):
        with self.assertRaises(PropertyBindingError) as caught:
            self.bind("property owner\n", asker=None)
        self.assertIn("owner", str(caught.exception))


class RedirectTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.previous = credentials._set_provider(FakeStore())

    def tearDown(self):
        credentials._set_provider(self.previous)
        shutil.rmtree(self.home)

    def test_redirect_resolves_target_through_lower_sources(self):
        properties.set_property(
            "company.key", "resolved", context=self.home)
        bound = bind_properties(
            script("property install-key\n"),
            parameters={"install-key": {"property": "company.key"}},
            context=self.home)
        self.assertEqual(bound.values["install-key"], "resolved")
        self.assertEqual(
            bound.sources["install-key"],
            f"{binding.PARAMETER} -> {binding.FILE}")

    def test_redirect_does_not_fall_back_to_the_declared_key(self):
        # The declared key has a file value, but a redirect replaces
        # its resolution entirely -- the target, unanswered, reaches
        # the ask, not the declared key's own file entry.
        properties.set_property(
            "install-key", "declared-file", context=self.home)
        asked = []

        def asker(key, prompt, secret):
            asked.append(key)
            return "from-ask"

        bound = bind_properties(
            script("property install-key\n"),
            parameters={"install-key": {"property": "missing.key"}},
            context=self.home, asker=asker)
        self.assertEqual(bound.values["install-key"], "from-ask")
        self.assertEqual(asked, ["install-key"])

    def test_redirect_reads_env_of_the_target(self):
        with _EnvGuard(RELIQUARY_PROPERTY_COMPANY_KEY="from-env"):
            bound = bind_properties(
                script("property install-key\n"),
                parameters={"install-key": {"property": "company.key"}},
                context=self.home)
        self.assertEqual(bound.values["install-key"], "from-env")
        self.assertEqual(
            bound.sources["install-key"],
            f"{binding.PARAMETER} -> {binding.ENVIRONMENT}")


class SecretAndKindTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.store = FakeStore()
        self.previous = credentials._set_provider(self.store)

    def tearDown(self):
        credentials._set_provider(self.previous)
        shutil.rmtree(self.home)

    def test_secret_binds_from_the_credential_store(self):
        properties.set_property(
            "pw", "hunter2", secret=True, context=self.home)
        bound = bind_properties(
            script("property secret pw\n"), context=self.home)
        self.assertEqual(bound.values["pw"], "hunter2")
        self.assertEqual(bound.secret_keys, frozenset({"pw"}))
        self.assertEqual(bound.secret_values(), {"hunter2"})

    def test_secret_cannot_come_from_a_flag(self):
        with self.assertRaises(PropertyBindingError) as caught:
            bind_properties(
                script("property secret pw\n"),
                explicit={"pw": "hunter2"}, context=self.home)
        self.assertIn("not", str(caught.exception).lower())

    def test_secret_may_come_from_the_environment(self):
        with _EnvGuard(RELIQUARY_PROPERTY_PW="from-env"):
            bound = bind_properties(
                script("property secret pw\n"), context=self.home)
        self.assertEqual(bound.values["pw"], "from-env")

    def test_text_declaration_finding_a_secret_is_an_error(self):
        properties.set_property(
            "pw", "hunter2", secret=True, context=self.home)
        with self.assertRaises(PropertyBindingError) as caught:
            bind_properties(script("property pw\n"), context=self.home)
        self.assertIn("secret", str(caught.exception))

    def test_secret_declaration_finding_ordinary_is_an_error(self):
        properties.set_property("pw", "plain", context=self.home)
        with self.assertRaises(PropertyBindingError) as caught:
            bind_properties(
                script("property secret pw\n"), context=self.home)
        self.assertIn("ordinary", str(caught.exception))

    def test_secret_marker_without_a_credential_fails_closed(self):
        path = properties._properties_path(context=self.home)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("pw = @secret\n")
        with self.assertRaises(PropertyBindingError) as caught:
            bind_properties(
                script("property secret pw\n"), context=self.home)
        self.assertIn("credential", str(caught.exception))


class EnvironmentMangleTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.previous = credentials._set_provider(FakeStore())

    def tearDown(self):
        credentials._set_provider(self.previous)
        shutil.rmtree(self.home)

    def test_dots_and_dashes_map_to_underscores(self):
        with _EnvGuard(
                RELIQUARY_PROPERTY_PRODUCTS_WINDOWS_98_INSTALL_KEY="k"):
            bound = bind_properties(
                script("property products.windows-98.install-key\n"),
                context=self.home)
        self.assertEqual(
            bound.values["products.windows-98.install-key"], "k")

    def test_colliding_keys_fail_before_the_run(self):
        with self.assertRaises(PropertyBindingError) as caught:
            bind_properties(
                script("property a.b\nproperty a-b\n"), context=self.home)
        message = str(caught.exception)
        self.assertIn("a.b", message)
        self.assertIn("a-b", message)


class ExplicitValidationTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.previous = credentials._set_provider(FakeStore())

    def tearDown(self):
        credentials._set_provider(self.previous)
        shutil.rmtree(self.home)

    def test_undeclared_explicit_key_is_rejected(self):
        with self.assertRaises(PropertyBindingError) as caught:
            bind_properties(
                script("property owner\n"),
                explicit={"stranger": "x"}, context=self.home)
        self.assertIn("stranger", str(caught.exception))


class DescribeSourcesTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.previous = credentials._set_provider(FakeStore())

    def tearDown(self):
        credentials._set_provider(self.previous)
        shutil.rmtree(self.home)

    def test_reports_each_source_without_prompting_or_values(self):
        properties.set_property("from-file", "v", context=self.home)
        with _EnvGuard(RELIQUARY_PROPERTY_FROM_ENV="v"):
            sources = describe_sources(
                script(
                    "property from-flag\n"
                    "property from-param\n"
                    "property from-env\n"
                    "property from-file\n"
                    "property will-ask\n"),
                explicit={"from-flag": "v"},
                parameters={"from-param": "v"},
                context=self.home)
        self.assertEqual(sources, {
            "from-flag": binding.FLAG,
            "from-param": binding.PARAMETER,
            "from-env": binding.ENVIRONMENT,
            "from-file": binding.FILE,
            "will-ask": binding.ASK,
        })

    def test_dry_run_never_reads_a_secret_value(self):
        # A marker present, credential absent: dry mode names the file
        # as the source without fetching (nothing to fetch here).
        path = properties._properties_path(context=self.home)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("pw = @secret\n")
        sources = describe_sources(
            script("property secret pw\n"), context=self.home)
        self.assertEqual(sources, {"pw": binding.FILE})


if __name__ == "__main__":
    unittest.main()
