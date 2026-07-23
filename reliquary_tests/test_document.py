# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Tests for the composed blueprint document parser (document.py)."""

import unittest

from reliquary import document
from reliquary.document import parse_document


class BareMachineTests(unittest.TestCase):
    def test_bare_root_machine_takes_stem_name(self):
        doc = parse_document(
            {"platform": "dos", "memory": "16M",
             "drives": {"hdd0": "blank-20m", "cdrom0": None}},
            stem="freedos-1.4")
        self.assertEqual(set(doc.machines), {"freedos-1.4"})
        machine = doc.machines["freedos-1.4"]
        self.assertEqual(machine.platform, "dos")
        self.assertEqual(machine.memory, 16)
        self.assertEqual(machine.drives["hdd0"].media, "blank-20m")
        self.assertIsNone(machine.drives["cdrom0"].media)
        self.assertEqual(machine.boot, ("hdd0",))  # default best-guess: slot-0 hdd

    def test_bare_machine_without_stem_or_name_fails(self):
        with self.assertRaises(ValueError):
            parse_document({"platform": "dos"})

    def test_explicit_name_overrides_stem(self):
        doc = parse_document({"name": "custom", "platform": "dos"},
                             stem="from-file")
        self.assertEqual(set(doc.machines), {"custom"})

    def test_drive_with_old_size_source_rejected(self):
        with self.assertRaises(ValueError):
            parse_document({"platform": "dos", "drives": {"hdd0": {"size": "20M"}}})

    def test_hdd_null_rejected(self):
        with self.assertRaises(ValueError):
            parse_document({"platform": "dos", "drives": {"hdd0": None}})

    def test_state_only_field_rejected(self):
        with self.assertRaises(ValueError):
            parse_document({"platform": "dos", "id": "x"})


class MediaTests(unittest.TestCase):
    def test_new_media_needs_size_no_source(self):
        doc = parse_document({"media": [
            {"name": "blank-20m", "materialize": "new", "size": "20M"}]})
        media = doc.media["blank-20m"]
        self.assertEqual(media.materialize, "new")
        self.assertEqual(media.size, "20M")
        self.assertIsNone(media.source)

    def test_new_media_with_source_rejected(self):
        with self.assertRaises(ValueError):
            parse_document({"media": [
                {"name": "x", "materialize": "new", "size": "20M",
                 "source": {"local": "d:/x.img"}}]})

    def test_use_media_needs_source(self):
        with self.assertRaises(ValueError):
            parse_document({"media": [{"name": "x", "materialize": "use"}]})

    def test_media_default_materialize_is_use(self):
        doc = parse_document({"media": [
            {"name": "iso", "source": {"url": "https://x/a.iso",
                                       "sha256": "a" * 64}}]})
        self.assertEqual(doc.media["iso"].materialize, "use")

    def test_media_name_defaults_from_local_source_stem(self):
        doc = parse_document({"media": [
            {"source": {"local": "D:/isos/win98se.iso"}}]})
        self.assertEqual(set(doc.media), {"win98se"})

    def test_unlocated_media_references_source_by_name(self):
        doc = parse_document({
            "media": [{"name": "windows-install-cd", "read-only": True,
                       "sha256": "c" * 64, "source": "windows-cd-location"}],
            "sources": [{"name": "windows-cd-location",
                         "local": "D:/isos/win.iso"}]})
        media = doc.media["windows-install-cd"]
        self.assertEqual(media.source.kind, "ref")
        self.assertEqual(media.source.ref, "windows-cd-location")
        self.assertTrue(media.read_only)
        self.assertEqual(doc.sources["windows-cd-location"].locator.kind, "local")

    def test_bad_sha256_rejected(self):
        with self.assertRaises(ValueError):
            parse_document({"media": [
                {"name": "x", "source": {"url": "u", "sha256": "zz"}}]})

    def test_duplicate_media_name_rejected(self):
        with self.assertRaises(ValueError):
            parse_document({"media": [
                {"name": "x", "materialize": "new", "size": "1M"},
                {"name": "x", "materialize": "new", "size": "2M"}]})


class ArchiveTreeTests(unittest.TestCase):
    def _freedos_tree(self):
        return parse_document({
            "sources": [{"url": ["https://paul.com/PaulsFreedos.zip",
                                 "https://m/PaulsFreedos.zip"],
                         "sha256": "a" * 64}],
            "archives": [{"source": "PaulsFreedos", "members": [
                {"path": "FD14-FloppyEdition.zip", "members": [
                    {"path": "144m/FDBOOT.img"},
                    {"path": "144m/FDSTD01.img"}]}]}]})

    def test_source_name_from_url_filename_stem(self):
        doc = self._freedos_tree()
        self.assertEqual(set(doc.sources), {"PaulsFreedos"})
        self.assertEqual(doc.sources["PaulsFreedos"].locator.urls,
                         ("https://paul.com/PaulsFreedos.zip",
                          "https://m/PaulsFreedos.zip"))

    def test_tree_expands_to_archives_and_leaf_media(self):
        doc = self._freedos_tree()
        self.assertEqual(set(doc.archives),
                         {"PaulsFreedos", "FD14-FloppyEdition"})
        self.assertEqual(set(doc.media), {"FDBOOT", "FDSTD01"})
        # top archive sources from the named download
        self.assertEqual(doc.archives["PaulsFreedos"].source.kind, "ref")
        self.assertEqual(doc.archives["PaulsFreedos"].source.ref, "PaulsFreedos")
        # nested archive extracts from its parent
        inner = doc.archives["FD14-FloppyEdition"].source
        self.assertEqual(inner.kind, "archive")
        self.assertEqual(inner.archive, "PaulsFreedos")
        self.assertEqual(inner.path, "FD14-FloppyEdition.zip")
        # leaf media extract from the inner archive, default use
        fdboot = doc.media["FDBOOT"]
        self.assertEqual(fdboot.materialize, "use")
        self.assertEqual(fdboot.source.kind, "archive")
        self.assertEqual(fdboot.source.archive, "FD14-FloppyEdition")
        self.assertEqual(fdboot.source.path, "144m/FDBOOT.img")

    def test_member_with_members_rejects_leaf_fields(self):
        with self.assertRaises(ValueError):
            parse_document({"archives": [
                {"name": "a", "source": {"url": "u", "sha256": "a" * 64},
                 "members": [{"path": "inner.zip", "materialize": "use",
                              "members": [{"path": "x.img"}]}]}]})

    def test_archive_requires_source(self):
        with self.assertRaises(ValueError):
            parse_document({"archives": [{"name": "a"}]})


class DocumentShapeTests(unittest.TestCase):
    def test_unknown_section_rejected(self):
        with self.assertRaises(ValueError):
            parse_document({"widgets": []})

    def test_empty_object_is_a_nameless_machine_and_fails(self):
        with self.assertRaises((ValueError, KeyError)):
            parse_document({})

    def test_machine_and_media_share_a_name_across_types(self):
        doc = parse_document({
            "machines": [{"name": "dos622", "platform": "dos"}],
            "media": [{"name": "dos622", "materialize": "new", "size": "1M"}]})
        self.assertIn("dos622", doc.machines)
        self.assertIn("dos622", doc.media)


if __name__ == "__main__":
    unittest.main()
