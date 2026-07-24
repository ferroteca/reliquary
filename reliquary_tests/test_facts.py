# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""The rlq.* run facts (milestone 8, T4)."""

import os
import unittest
from unittest import mock
from reliquary import facts


class FactCatalogTests(unittest.TestCase):
    def test_is_fact_recognizes_the_namespace(self):
        self.assertTrue(facts.is_fact("rlq.host.username"))
        self.assertTrue(facts.is_fact("rlq.host.full-name"))
        self.assertTrue(facts.is_fact("rlq.env.ANYTHING"))
        self.assertFalse(facts.is_fact("owner"))
        self.assertFalse(facts.is_fact("rlqhost"))

    def test_an_unknown_rlq_key_raises(self):
        with self.assertRaises(KeyError):
            facts.resolve("rlq.host.nonesuch")

    def test_username_is_login_normalized(self):
        with mock.patch("reliquary.facts.getpass.getuser",
                        return_value="Ada Lovelace!"):
            self.assertEqual(facts.resolve("rlq.host.username"), "ada-lovelace")

    def test_username_that_normalizes_to_nothing_is_unanswerable(self):
        with mock.patch("reliquary.facts.getpass.getuser",
                        return_value="!!!"):
            self.assertIsNone(facts.resolve("rlq.host.username"))

    def test_an_unresolvable_login_is_unanswerable(self):
        with mock.patch("reliquary.facts.getpass.getuser",
                        side_effect=OSError):
            self.assertIsNone(facts.resolve("rlq.host.username"))

    def test_env_fact_reads_verbatim(self):
        with mock.patch.dict(os.environ, {"MY_FACT": "  spaced value  "}):
            self.assertEqual(
                facts.resolve("rlq.env.MY_FACT"), "  spaced value  ")

    def test_an_unset_or_empty_env_fact_is_unanswerable(self):
        with mock.patch.dict(os.environ, {"EMPTY_FACT": ""}):
            self.assertIsNone(facts.resolve("rlq.env.EMPTY_FACT"))
        os.environ.pop("MISSING_FACT", None)
        self.assertIsNone(facts.resolve("rlq.env.MISSING_FACT"))

    def test_an_empty_env_name_is_unanswerable(self):
        self.assertIsNone(facts.resolve("rlq.env."))


if __name__ == "__main__":
    unittest.main()
