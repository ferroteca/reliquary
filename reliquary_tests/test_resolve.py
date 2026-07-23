# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Tests for whole-source namespace + fetch-plan resolution."""

import os
import tempfile
import unittest

from reliquary import resolve
from reliquary.document import parse_document
from reliquary.resolve import Download, Extract, LocalFile


class BuildNamespaceTests(unittest.TestCase):
    def _write(self, root, name, text):
        path = os.path.join(root, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def test_merges_components_across_files(self):
        with tempfile.TemporaryDirectory() as root:
            self._write(root, "machine.rlqb",
                        '{"name": "m", "platform": "dos"}')
            self._write(root, "media.rlqb",
                        '{"media": [{"name": "blank", "materialize": "new",'
                        ' "size": "1M"}]}')
            ns = resolve.build_namespace([
                os.path.join(root, "machine.rlqb"),
                os.path.join(root, "media.rlqb")])
            self.assertEqual(set(ns.machines), {"m"})
            self.assertEqual(set(ns.media), {"blank"})

    def test_cross_file_same_name_and_kind_collides(self):
        with tempfile.TemporaryDirectory() as root:
            a = self._write(root, "a.rlqb",
                            '{"media": [{"name": "x", "materialize": "new",'
                            ' "size": "1M"}]}')
            b = self._write(root, "b.rlqb",
                            '{"media": [{"name": "x", "materialize": "new",'
                            ' "size": "2M"}]}')
            with self.assertRaises(ValueError) as caught:
                resolve.build_namespace([a, b])
            self.assertIn("x", str(caught.exception))

    def test_bare_root_machine_named_by_file_stem(self):
        with tempfile.TemporaryDirectory() as root:
            self._write(root, "freedos-1.4.rlqb", '{"platform": "dos"}')
            ns = resolve.build_namespace(
                [os.path.join(root, "freedos-1.4.rlqb")])
            self.assertEqual(set(ns.machines), {"freedos-1.4"})


class FetchPlanTests(unittest.TestCase):
    def _ns(self, doc_value):
        return resolve.namespace_of(parse_document(doc_value))

    def test_nested_archive_plan(self):
        ns = self._ns({
            "sources": [{"url": ["https://paul.com/PaulsFreedos.zip"],
                         "sha256": "a" * 64}],
            "archives": [{"source": "PaulsFreedos", "members": [
                {"path": "FD14-FloppyEdition.zip", "members": [
                    {"path": "144m/FDBOOT.img"}]}]}]})
        plan = resolve.resolve_media_plan(ns.media["FDBOOT"], ns)
        # outermost extract: FDBOOT.img out of FD14-FloppyEdition
        self.assertIsInstance(plan, Extract)
        self.assertEqual(plan.archive, "FD14-FloppyEdition")
        self.assertEqual(plan.member, "144m/FDBOOT.img")
        # next: FD14-FloppyEdition.zip out of PaulsFreedos
        self.assertIsInstance(plan.inner, Extract)
        self.assertEqual(plan.inner.archive, "PaulsFreedos")
        self.assertEqual(plan.inner.member, "FD14-FloppyEdition.zip")
        # root: the mirror download
        self.assertIsInstance(plan.inner.inner, Download)
        self.assertEqual(plan.inner.inner.urls,
                         ("https://paul.com/PaulsFreedos.zip",))
        self.assertEqual(plan.inner.inner.sha256, "a" * 64)

    def test_ref_resolves_through_named_source(self):
        ns = self._ns({
            "media": [{"name": "win", "sha256": "c" * 64,
                       "source": "win-loc"}],
            "sources": [{"name": "win-loc", "local": "D:/isos/win.iso"}]})
        plan = resolve.resolve_media_plan(ns.media["win"], ns)
        self.assertIsInstance(plan, LocalFile)
        self.assertEqual(plan.path, "D:/isos/win.iso")

    def test_new_media_has_no_plan(self):
        ns = self._ns({"media": [
            {"name": "blank", "materialize": "new", "size": "1M"}]})
        self.assertIsNone(
            resolve.resolve_media_plan(ns.media["blank"], ns))

    def test_missing_archive_raises(self):
        ns = self._ns({"media": [
            {"name": "x", "source": {"archive": "gone", "path": "a.img"}}]})
        with self.assertRaises(KeyError):
            resolve.resolve_media_plan(ns.media["x"], ns)


if __name__ == "__main__":
    unittest.main()
