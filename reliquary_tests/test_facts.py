# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""The rlq.* run facts (milestone 8, T4)."""

import os
import re
import unittest
from unittest import mock
from reliquary import facts
from reliquary.errors import InternalError

_SPEC = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "docs", "spec", "script-properties.md")
#: A catalog entry is a top-level bullet opening with the fact's key.
#: Anchoring on the bullet is what keeps the prose out — the parked
#: candidates (`rlq.host.hostname`, a raw username) are named in a
#: parenthetical, and reading them as catalog would invert the test.
_CATALOG_BULLET = re.compile(r"^- `(rlq\.[^`]+)`", re.M)


@unittest.skipUnless(os.path.isfile(_SPEC),
                     "the properties spec is source-tree only")
class SpecifiedCatalogTests(unittest.TestCase):
    """The catalog the spec lists is the catalog `is_fact` admits.

    P24's inventory pass over the property facts. The hazard is
    specific and one-directional: `is_fact` is what S6 consults, so
    a fact the spec documents and the catalog lacks makes a
    documented derivation fail static validation with a diagnostic
    saying the key is "neither a declared property nor an rlq.*
    fact" — which is exactly what it is. The reverse, a fact
    shipped and undocumented, is an undiscoverable feature.

    The tests below this one assert the same membership by hand and
    would pass whatever the spec said; this one is the half that
    reads it.
    """

    @staticmethod
    def _specified():
        with open(_SPEC, encoding="utf-8") as handle:
            return set(_CATALOG_BULLET.findall(handle.read()))

    def test_every_specified_fact_resolves(self):
        # `rlq.env.<NAME>` is a family, not a key; any member stands
        # for it, and `is_fact` is prefix-based for exactly that.
        unknown = sorted(
            key for key in self._specified()
            if not facts.is_fact(key.replace("<NAME>", "PATH")))
        self.assertEqual(
            unknown, [],
            f"{unknown} are documented facts that is_fact rejects. S6 "
            "consults it, so a script deriving from one would be "
            "refused for referencing a fact the spec told its author "
            "to use.")

    def test_every_curated_fact_is_specified(self):
        undocumented = sorted(set(facts._CATALOG) - self._specified())
        self.assertEqual(
            undocumented, [],
            f"{undocumented} ship in the fact catalog and appear in no "
            "spec bullet. The catalog is deliberately small and each "
            "fact's derivation is part of its contract, so an "
            "unlisted one is a contract nobody can read.")

    def test_the_env_family_is_specified_as_a_family(self):
        family = [key for key in self._specified()
                  if key.startswith(facts._ENV_PREFIX)]
        self.assertEqual(
            len(family), 1,
            "the env escape hatch is one spec bullet naming a family; "
            f"found {family}.")
        self.assertNotIn(
            family[0], facts._CATALOG,
            "the env family is resolved by prefix, not enumerated in "
            "the catalog; a literal entry would shadow the family.")


class FactCatalogTests(unittest.TestCase):
    def test_is_fact_recognizes_the_namespace(self):
        self.assertTrue(facts.is_fact("rlq.host.username"))
        self.assertTrue(facts.is_fact("rlq.host.full-name"))
        self.assertTrue(facts.is_fact("rlq.env.ANYTHING"))
        self.assertFalse(facts.is_fact("owner"))
        self.assertFalse(facts.is_fact("rlqhost"))

    def test_an_unknown_rlq_key_raises(self):
        with self.assertRaises(InternalError):
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
