# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for whole-source catalog + fetch-plan resolution.

This is where the second phase of validation lives, so it is where the
rules a single document cannot express are tested: identity across
files, containment through the catalog, and the value checks that need
a resolved reference.
"""

import os
import tempfile
import unittest

from reliquary import resolve
from reliquary.errors import PreflightError
from reliquary.document import parse_document
from reliquary.resolve import Alternatives, Download, Extract, LocalFile

SHA = "a" * 64
SHB = "b" * 64


class BuildNamespaceTests(unittest.TestCase):
    def _write(self, root, name, text):
        path = os.path.join(root, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def test_merges_specs_across_files(self):
        with tempfile.TemporaryDirectory() as root:
            a = self._write(
                root, "machine.rlqb",
                '[{"type": "machine", "name": "m", "platform": "dos"}]')
            b = self._write(
                root, "media.rlqb",
                '[{"name": "blank", "materialize": "new", "size": "1M"}]')
            ns = resolve.build_namespace([a, b])
            self.assertEqual(set(ns.machines), {"m"})
            self.assertEqual(set(ns.media), {"blank"})

    def test_identical_specs_across_files_dedup(self):
        """What lets a self-contained blueprint be pasted around."""
        spec = ('[{"name": "iso", "location": "https://x.test/p.iso",'
                ' "sha256": "%s"}]' % SHA)
        with tempfile.TemporaryDirectory() as root:
            a = self._write(root, "a.rlqb", spec)
            b = self._write(root, "b.rlqb", spec)
            ns = resolve.build_namespace([a, b])
            self.assertEqual(set(ns.media), {"iso"})

    def test_differing_specs_of_one_name_collide_naming_both_files(self):
        with tempfile.TemporaryDirectory() as root:
            a = self._write(
                root, "a.rlqb",
                '[{"name": "x", "materialize": "new", "size": "1M"}]')
            b = self._write(
                root, "b.rlqb",
                '[{"name": "x", "materialize": "new", "size": "2M"}]')
            with self.assertRaises(PreflightError) as caught:
                resolve.build_namespace([a, b])
            message = str(caught.exception)
            self.assertIn("x", message)
            self.assertIn("a.rlqb", message)
            self.assertIn("b.rlqb", message)

    def test_names_collide_case_insensitively_across_files(self):
        with tempfile.TemporaryDirectory() as root:
            a = self._write(root, "a.rlqb", '[{"name": "FDBOOT",'
                                            ' "location": "a.img"}]')
            b = self._write(root, "b.rlqb", '[{"name": "fdboot",'
                                            ' "location": "b.img"}]')
            with self.assertRaises(PreflightError) as caught:
                resolve.build_namespace([a, b])
            self.assertIn("case", str(caught.exception))


class LocalAnchorResolutionTests(unittest.TestCase):
    """Local media resolve against the referencing file, never the CWD."""

    def _write(self, root, name, text):
        path = os.path.join(root, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def test_the_plan_is_cwd_independent(self):
        with tempfile.TemporaryDirectory() as root, \
                tempfile.TemporaryDirectory() as elsewhere:
            blueprint = self._write(
                root, "b.rlqb", '[{"name": "iso", "location": "x.iso"}]')
            saved = os.getcwd()
            os.chdir(elsewhere)
            try:
                ns = resolve.build_namespace([blueprint])
                plan = resolve.resolve_media_plan(
                    resolve.resolve_media("iso", ns), ns)
            finally:
                os.chdir(saved)
            self.assertIsInstance(plan, LocalFile)
            self.assertEqual(plan.path, os.path.join(root, "x.iso"))

    def test_one_relative_spelling_in_two_directories_collides(self):
        """Anchored, the two specs name different bytes: different
        media, so they collide rather than silently resolving through
        whichever file was read first."""
        spec = '[{"name": "iso", "location": "x.iso"}]'
        with tempfile.TemporaryDirectory() as root:
            os.mkdir(os.path.join(root, "a"))
            os.mkdir(os.path.join(root, "b"))
            a = self._write(os.path.join(root, "a"), "a.rlqb", spec)
            b = self._write(os.path.join(root, "b"), "b.rlqb", spec)
            with self.assertRaises(PreflightError) as caught:
                resolve.build_namespace([a, b])
            message = str(caught.exception)
            self.assertIn("a.rlqb", message)
            self.assertIn("b.rlqb", message)

    def test_one_relative_spelling_in_one_directory_still_dedups(self):
        spec = '[{"name": "iso", "location": "x.iso"}]'
        with tempfile.TemporaryDirectory() as root:
            a = self._write(root, "a.rlqb", spec)
            b = self._write(root, "b.rlqb", spec)
            ns = resolve.build_namespace([a, b])
            self.assertEqual(set(ns.media), {"iso"})
            rung = ns.media["iso"].location[0]
            self.assertEqual(rung.local, os.path.join(root, "x.iso"))


class FetchPlanTests(unittest.TestCase):
    def _ns(self, value):
        return resolve.namespace_of(parse_document(value))

    def test_nested_containment_plan(self):
        ns = self._ns([{
            "name": "PaulsFreedos",
            "location": "https://paul.com/PaulsFreedos.zip", "sha256": SHA,
            "children": [{"path": "FD14-FloppyEdition.zip",
                          "children": ["144m/FDBOOT.img"]}]}])
        plan = resolve.resolve_media_plan(ns.media["FDBOOT"], ns)
        # outermost extract: FDBOOT.img out of the floppy edition
        self.assertIsInstance(plan, Extract)
        self.assertEqual(plan.parent, "FD14-FloppyEdition")
        self.assertEqual(plan.member, "144m/FDBOOT.img")
        # next: the floppy edition out of the outer download
        self.assertIsInstance(plan.inner, Extract)
        self.assertEqual(plan.inner.parent, "PaulsFreedos")
        self.assertEqual(plan.inner.member, "FD14-FloppyEdition.zip")
        # root: the download itself
        self.assertIsInstance(plan.inner.inner, Download)
        self.assertEqual(plan.inner.inner.url,
                         "https://paul.com/PaulsFreedos.zip")
        self.assertEqual(plan.inner.inner.sha256, SHA)

    def test_bare_parent_reference_is_the_parents_own_bytes(self):
        """How a difference overlay names what it sits on."""
        ns = self._ns([
            {"name": "golden", "location": "golden.qcow2"},
            {"name": "scratch", "materialize": "difference",
             "location": "${media:golden}"}])
        plan = resolve.resolve_media_plan(ns.media["scratch"], ns)
        self.assertIsInstance(plan, LocalFile)
        self.assertEqual(plan.path, "golden.qcow2")

    def test_mirror_list_becomes_alternatives(self):
        ns = self._ns([{"name": "iso", "sha256": SHA,
                        "location": ["https://a.test/p.iso",
                                     "vendor/p.iso"]}])
        plan = resolve.resolve_media_plan(ns.media["iso"], ns)
        self.assertIsInstance(plan, Alternatives)
        self.assertIsInstance(plan.options[0], Download)
        self.assertIsInstance(plan.options[1], LocalFile)

    def test_blank_has_no_plan(self):
        ns = self._ns([{"name": "blank", "materialize": "new", "size": "1M"}])
        self.assertIsNone(resolve.resolve_media_plan(ns.media["blank"], ns))

    def test_missing_parent_names_both_media(self):
        ns = self._ns([{"name": "x", "location": "${media:gone/a.img}"}])
        with self.assertRaises(PreflightError) as caught:
            resolve.resolve_media_plan(ns.media["x"], ns)
        self.assertIn("gone", str(caught.exception))

    def test_containment_cycle_is_named(self):
        ns = self._ns([{"name": "loop", "location": "${media:loop/p.img}"}])
        with self.assertRaises(PreflightError) as caught:
            resolve.resolve_media_plan(ns.media["loop"], ns)
        self.assertIn("cycle", str(caught.exception))

    def test_remote_without_a_hash_fails_at_resolution(self):
        """Parse cannot know: a referenced rung may resolve to a URL."""
        ns = self._ns([{"name": "iso", "location": "https://x.test/p.iso"}])
        with self.assertRaises(PreflightError) as caught:
            resolve.resolve_media_plan(ns.media["iso"], ns)
        self.assertIn("sha256", str(caught.exception))

    def test_unsupported_container_names_its_format(self):
        ns = self._ns([
            {"name": "disk", "location": "disk.img"},
            {"name": "inside", "location": "${media:disk/p.txt}"}])
        with self.assertRaises(PreflightError) as caught:
            resolve.resolve_media_plan(ns.media["inside"], ns)
        message = str(caught.exception)
        self.assertIn("img", message)
        self.assertIn("zip", message)

    def test_property_location_fails_closed_naming_properties(self):
        """Never a milestone number: name the channel it waits on."""
        ns = self._ns([{"name": "win", "location": "${windows.iso}"}])
        with self.assertRaises(PreflightError) as caught:
            resolve.resolve_media_plan(ns.media["win"], ns)
        message = str(caught.exception)
        self.assertIn("propert", message)
        self.assertNotIn("milestone", message)


class LocationBindingTests(unittest.TestCase):
    """`${key}` in a location binds through a supplied properties map (T5)."""

    def _ns(self, value):
        return resolve.namespace_of(parse_document(value))

    def test_a_property_location_binds_to_a_url(self):
        ns = self._ns([{"name": "win", "location": "${windows.iso}",
                        "sha256": SHA}])
        plan = resolve.resolve_media_plan(
            ns.media["win"], ns,
            {"windows.iso": "https://vendor.test/win.iso"})
        self.assertIsInstance(plan, Download)
        self.assertEqual(plan.url, "https://vendor.test/win.iso")
        self.assertEqual(plan.sha256, SHA)

    def test_a_property_location_binds_to_a_local_path(self):
        ns = self._ns([{"name": "win", "location": "${windows.iso}"}])
        plan = resolve.resolve_media_plan(
            ns.media["win"], ns, {"windows.iso": "C:/isos/win.iso"})
        self.assertIsInstance(plan, LocalFile)
        self.assertEqual(plan.path, "C:/isos/win.iso")

    def test_a_deferred_string_interpolates_bound_values(self):
        ns = self._ns([{
            "name": "win",
            "location": "https://vendor.test/${edition}/win.iso",
            "sha256": SHA}])
        plan = resolve.resolve_media_plan(
            ns.media["win"], ns, {"edition": "pro"})
        self.assertIsInstance(plan, Download)
        self.assertEqual(plan.url, "https://vendor.test/pro/win.iso")

    def test_an_unbound_key_names_the_media_and_the_key(self):
        ns = self._ns([{"name": "win", "location": "${windows.iso}"}])
        with self.assertRaises(PreflightError) as caught:
            resolve.resolve_media_plan(ns.media["win"], ns, {})
        message = str(caught.exception)
        self.assertIn("win", message)
        self.assertIn("windows.iso", message)

    def test_a_value_that_is_itself_a_reference_fails_closed(self):
        ns = self._ns([{"name": "win", "location": "${windows.iso}"}])
        with self.assertRaises(PreflightError) as caught:
            resolve.resolve_media_plan(
                ns.media["win"], ns, {"windows.iso": "${other}"})
        self.assertIn("chain", str(caught.exception))

    def test_a_value_naming_another_media_is_refused(self):
        ns = self._ns([{"name": "win", "location": "${windows.iso}"}])
        with self.assertRaises(PreflightError) as caught:
            resolve.resolve_media_plan(
                ns.media["win"], ns, {"windows.iso": "${media:other}"})
        self.assertIn("chain", str(caught.exception))

    def test_a_deferred_sha256_binds(self):
        ns = self._ns([{"name": "win",
                        "location": "https://vendor.test/win.iso",
                        "sha256": "${win.hash}"}])
        plan = resolve.resolve_media_plan(
            ns.media["win"], ns, {"win.hash": SHA})
        self.assertEqual(plan.sha256, SHA)

    def test_location_property_keys_walks_the_closure(self):
        # A child inherits its parent's location keys: to extract inner,
        # the outer download's ${outer.zip} must bind first.
        ns = self._ns([{
            "name": "outer", "location": "${outer.zip}", "sha256": SHA,
            "children": ["inner.img"]}])
        inner = next(m for name, m in ns.media.items() if name != "outer")
        keys = resolve.location_property_keys(inner, ns)
        self.assertEqual(keys, {"outer.zip"})


if __name__ == "__main__":
    unittest.main()
