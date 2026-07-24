# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""The line-based user properties file.

Spec: planning/design/script-properties.md.
"""

import os
import shutil
import tempfile
import unittest
from reliquary import credentials, properties
from reliquary.properties import PropertiesError
from reliquary_tests.test_credentials import FakeStore

_provider = None


def setUpModule():
    """Never let the unit suite reach the host's real credential store."""
    global _provider
    _provider = credentials._set_provider(FakeStore())


def tearDownModule():
    credentials._set_provider(_provider)


class PropertiesFileTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.home)

    def path(self):
        return properties._properties_path(context=self.home)

    def write(self, text):
        path = self.path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        return path

    def read(self):
        with open(self.path(), "r", encoding="utf-8") as handle:
            return handle.read()

    def test_absent_file_has_no_properties(self):
        self.assertIsNone(
            properties.get_property("identity.full-name", context=self.home))
        self.assertEqual(properties.list_properties(context=self.home), {})

    def test_set_creates_the_file_and_get_reads_it(self):
        properties.set_property(
            "identity.full-name", "Paul Galbraith", context=self.home)
        self.assertEqual(
            properties.get_property("identity.full-name", context=self.home),
            "Paul Galbraith")
        self.assertEqual(self.read(), "identity.full-name = Paul Galbraith\n")

    def test_values_are_verbatim_to_end_of_line(self):
        # No quoting, no escapes, no comment stripping mid-line.
        self.write("greeting = hello = world # not a comment\n")
        self.assertEqual(
            properties.get_property("greeting", context=self.home),
            "hello = world # not a comment")

    def test_comments_blanks_and_order_survive_a_set(self):
        self.write(
            "# reliquary user properties\n"
            "identity.full-name = Paul Galbraith\n"
            "\n"
            "# the zeta key sorts first on purpose\n"
            "zeta = last\n"
            "alpha = first\n")
        properties.set_property("zeta", "changed", context=self.home)
        self.assertEqual(
            self.read(),
            "# reliquary user properties\n"
            "identity.full-name = Paul Galbraith\n"
            "\n"
            "# the zeta key sorts first on purpose\n"
            "zeta = changed\n"
            "alpha = first\n")

    def test_unset_removes_only_its_own_line(self):
        self.write(
            "# keep me\n"
            "alpha = one\n"
            "beta = two\n"
            "\n"
            "gamma = three\n")
        properties.unset_property("beta", context=self.home)
        self.assertEqual(
            self.read(),
            "# keep me\n"
            "alpha = one\n"
            "\n"
            "gamma = three\n")

    def test_unset_then_set_still_edits_the_right_lines(self):
        # The index bookkeeping after a deletion is easy to get wrong.
        self.write("alpha = one\nbeta = two\ngamma = three\n")
        properties.unset_property("alpha", context=self.home)
        properties.set_property("gamma", "changed", context=self.home)
        self.assertEqual(self.read(), "beta = two\ngamma = changed\n")

    def test_set_appends_a_new_key(self):
        self.write("# header\nalpha = one\n")
        properties.set_property("beta", "two", context=self.home)
        self.assertEqual(self.read(), "# header\nalpha = one\nbeta = two\n")

    def test_unset_missing_key_is_quiet(self):
        self.write("alpha = one\n")
        properties.unset_property("beta", context=self.home)
        self.assertEqual(self.read(), "alpha = one\n")

    def test_a_crlf_file_keeps_its_line_endings(self):
        # A file hand-edited in a Windows editor must not come back
        # rewritten end to end just because one line changed.
        self.write("# header\r\nalpha = one\r\nbeta = two\r\n")
        properties.set_property("alpha", "changed", context=self.home)
        with open(self.path(), "r", encoding="utf-8", newline="") as handle:
            self.assertEqual(
                handle.read(),
                "# header\r\nalpha = changed\r\nbeta = two\r\n")

    def test_an_lf_file_keeps_its_line_endings(self):
        self.write("alpha = one\nbeta = two\n")
        properties.set_property("gamma", "three", context=self.home)
        with open(self.path(), "r", encoding="utf-8", newline="") as handle:
            self.assertEqual(
                handle.read(), "alpha = one\nbeta = two\ngamma = three\n")

    def test_a_file_without_a_final_newline_gains_one(self):
        self.write("alpha = one")
        properties.set_property("beta", "two", context=self.home)
        self.assertEqual(self.read(), "alpha = one\nbeta = two\n")

    def test_whitespace_around_the_separator_is_trimmed(self):
        self.write("alpha=one\n  beta   =   two  \n")
        self.assertEqual(
            properties.list_properties(context=self.home),
            {"alpha": "one", "beta": "two"})

    def test_listing_sorts_and_prefix_selects_a_namespace(self):
        self.write(
            "products.windows-98.install-key = k\n"
            "identity.full-name = Paul\n"
            "products.windows-98 = ninety-eight\n"
            "products.windows-98-extra = not-a-descendant\n")
        self.assertEqual(
            list(properties.list_properties(context=self.home)),
            ["identity.full-name", "products.windows-98",
             "products.windows-98-extra", "products.windows-98.install-key"])
        self.assertEqual(
            properties.list_properties(
                "products.windows-98", context=self.home),
            {"products.windows-98": "ninety-eight",
             "products.windows-98.install-key": "k"})


class ValueKindTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.home)

    def write(self, text):
        path = properties._properties_path(context=self.home)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)

    def test_secret_marker_reads_as_the_marker_never_a_value(self):
        self.write("accounts.default-password = @secret\n")
        value = properties.get_property(
            "accounts.default-password", context=self.home)
        self.assertTrue(properties.is_secret(value))
        self.assertEqual(value, {"secret": True})

    def test_literal_at_sign_is_doubled(self):
        self.write("handle = @@paul\n")
        self.assertEqual(
            properties.get_property("handle", context=self.home), "@paul")

    def test_unknown_value_kind_fails_closed(self):
        self.write("handle = @nonesuch\n")
        with self.assertRaises(PropertiesError) as caught:
            properties.get_property("handle", context=self.home)
        self.assertIn("reserved", str(caught.exception))
        self.assertIn(":1:", str(caught.exception))

    def test_setting_a_value_with_a_leading_at_escapes_it(self):
        properties.set_property("handle", "@paul", context=self.home)
        self.assertEqual(
            properties.get_property("handle", context=self.home), "@paul")

    def test_an_ordinary_value_may_read_back_as_secret_text(self):
        properties.set_property("decoy", "@secret", context=self.home)
        self.assertEqual(
            properties.get_property("decoy", context=self.home), "@secret")
        self.assertFalse(
            properties.is_secret(
                properties.get_property("decoy", context=self.home)))

    def test_ordinary_over_a_secret_needs_an_unset_first(self):
        self.write("accounts.default-password = @secret\n")
        with self.assertRaises(PropertiesError) as caught:
            properties.set_property(
                "accounts.default-password", "plain", context=self.home)
        self.assertIn("unset", str(caught.exception))

    def test_values_that_would_not_round_trip_are_refused(self):
        for value in (" padded", "padded ", "two\nlines"):
            with self.assertRaises(PropertiesError):
                properties.set_property("alpha", value, context=self.home)

    def test_a_non_string_value_is_refused(self):
        with self.assertRaises(PropertiesError):
            properties.set_property("alpha", 42, context=self.home)


class KeyRulesTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.home)

    def test_valid_keys(self):
        for key in ("alpha", "identity.full-name", "a.b.c",
                    "products.windows-98.install-key", "x_y"):
            self.assertEqual(properties.check_key(key), key)

    def test_invalid_keys(self):
        for key in ("", "9lives", ".leading", "trailing.",
                    "two..dots", "has space", "-dash", "_under",
                    "seg.9nine"):
            with self.assertRaises(PropertiesError, msg=key):
                properties.check_key(key)

    def test_reserved_namespaces(self):
        for key in ("rlq", "rlq.host.username", "reliquary",
                    "reliquary.anything"):
            with self.assertRaises(PropertiesError, msg=key) as caught:
                properties.check_key(key)
            self.assertIn("reserved", str(caught.exception))

    def test_keys_are_case_sensitive(self):
        properties.set_property("alpha", "lower", context=self.home)
        properties.set_property("Alpha", "upper", context=self.home)
        self.assertEqual(
            properties.list_properties(context=self.home),
            {"Alpha": "upper", "alpha": "lower"})


class MalformedFileTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.home)

    def write(self, text):
        path = properties._properties_path(context=self.home)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        return path

    def test_a_line_without_a_separator_names_its_line(self):
        path = self.write("alpha = one\nnonsense\n")
        with self.assertRaises(PropertiesError) as caught:
            properties.list_properties(context=self.home)
        message = str(caught.exception)
        self.assertIn(path, message)
        self.assertIn(":2:", message)

    def test_an_invalid_key_names_its_line(self):
        self.write("alpha = one\n9lives = two\n")
        with self.assertRaises(PropertiesError) as caught:
            properties.list_properties(context=self.home)
        self.assertIn(":2:", str(caught.exception))

    def test_a_duplicate_key_names_both_lines(self):
        self.write("alpha = one\n# comment\nalpha = two\n")
        with self.assertRaises(PropertiesError) as caught:
            properties.list_properties(context=self.home)
        message = str(caught.exception)
        self.assertIn(":3:", message)
        self.assertIn("line 1", message)

    def test_an_invalid_file_is_never_partly_rewritten(self):
        original = "alpha = one\nnonsense\n"
        self.write(original)
        with self.assertRaises(PropertiesError):
            properties.set_property("beta", "two", context=self.home)
        path = properties._properties_path(context=self.home)
        with open(path, "r", encoding="utf-8") as handle:
            self.assertEqual(handle.read(), original)

    def test_a_failed_write_leaves_no_temporary_file(self):
        properties.set_property("alpha", "one", context=self.home)
        directory = os.path.dirname(properties._properties_path(
            context=self.home))
        self.assertEqual(
            [name for name in os.listdir(directory)
             if name.startswith(".user.properties.")],
            [])


if __name__ == "__main__":
    unittest.main()
