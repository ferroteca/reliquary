# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Tests for media definitions and hash-verified media acquisition."""

import hashlib
import io
import json
import os
import tempfile
import unittest
import zipfile
from unittest import mock

from reliquary import media
from reliquary.media import (fetch_media, load_definition,
                             parse_definition, resolve_media)

PAYLOAD = b"freedos installer bytes"
PAYLOAD_SHA256 = hashlib.sha256(PAYLOAD).hexdigest()
URL = "https://example.invalid/FD14-LiveCD.zip"

ISO_BYTES = b"iso bytes"
ISO_SHA256 = hashlib.sha256(ISO_BYTES).hexdigest()
BOOT_BYTES = b"boot image bytes"
BOOT_SHA256 = hashlib.sha256(BOOT_BYTES).hexdigest()


def _zip_bytes(members):
    """Build an in-memory zip archive from a name -> bytes mapping."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as bundle:
        for name, payload in members.items():
            bundle.writestr(name, payload)
    return buffer.getvalue()


class EnsureMediaTests(unittest.TestCase):
    """Behavior of media.ensure_media()."""

    def setUp(self):
        self.workdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.workdir.cleanup)
        self.destination = os.path.join(
            self.workdir.name, "FD14-LiveCD.zip")

    def test_missing_media_is_downloaded_and_verified(self):
        """Absent media is downloaded, written, and returned."""
        with mock.patch("reliquary.media.urlopen",
                        return_value=io.BytesIO(PAYLOAD)) as urlopen:
            result = media.ensure_media(
                URL, PAYLOAD_SHA256, self.destination)
        urlopen.assert_called_once_with(URL)
        self.assertEqual(result, self.destination)
        with open(self.destination, "rb") as handle:
            self.assertEqual(handle.read(), PAYLOAD)

    def test_cached_media_with_matching_hash_is_reused(self):
        """A cached file that verifies is returned without download."""
        with open(self.destination, "wb") as handle:
            handle.write(PAYLOAD)
        with mock.patch("reliquary.media.urlopen") as urlopen:
            result = media.ensure_media(
                URL, PAYLOAD_SHA256, self.destination)
        urlopen.assert_not_called()
        self.assertEqual(result, self.destination)


    def test_corrupt_cache_is_erased_before_download(self):
        """A cached file that fails verification is deleted even when
        the replacement download does not complete."""
        with open(self.destination, "wb") as handle:
            handle.write(b"corrupted")
        with mock.patch("reliquary.media.urlopen",
                        side_effect=OSError("network down")):
            with self.assertRaises(OSError):
                media.ensure_media(
                    URL, PAYLOAD_SHA256, self.destination)
        self.assertFalse(os.path.exists(self.destination))

    def test_corrupt_cache_is_replaced_by_fresh_download(self):
        """A cached file that fails verification is downloaded again."""
        with open(self.destination, "wb") as handle:
            handle.write(b"corrupted")
        with mock.patch("reliquary.media.urlopen",
                        return_value=io.BytesIO(PAYLOAD)):
            result = media.ensure_media(
                URL, PAYLOAD_SHA256, self.destination)
        self.assertEqual(result, self.destination)
        with open(self.destination, "rb") as handle:
            self.assertEqual(handle.read(), PAYLOAD)

    def test_unverifiable_download_is_erased_and_reported(self):
        """A download that fails verification is deleted and raises."""
        with mock.patch("reliquary.media.urlopen",
                        return_value=io.BytesIO(b"tampered")):
            with self.assertRaises(RuntimeError) as caught:
                media.ensure_media(
                    URL, PAYLOAD_SHA256, self.destination)
        self.assertIn(PAYLOAD_SHA256, str(caught.exception))
        self.assertFalse(os.path.exists(self.destination))


class EnsureMediaFromArchiveTests(unittest.TestCase):
    """ensure_media() with archive_member: zips are transient."""

    def setUp(self):
        self.workdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.workdir.cleanup)
        self.destination = os.path.join(
            self.workdir.name, "FD14LIVE.iso")
        self.archive = os.path.join(
            self.workdir.name, "FD14-LiveCD.zip")
        self.zip_payload = _zip_bytes({"FD14LIVE.iso": ISO_BYTES})
        self.iso_sha256 = ISO_SHA256

    def _ensure(self, urlopen):
        with mock.patch("reliquary.media.urlopen", urlopen):
            return media.ensure_media(
                "https://example.invalid/FD14-LiveCD.zip",
                self.iso_sha256, self.destination,
                archive_member="FD14LIVE.iso")

    def test_member_is_downloaded_extracted_and_zip_discarded(self):
        """The zip is downloaded, the member kept, the zip deleted."""
        urlopen = mock.Mock(return_value=io.BytesIO(self.zip_payload))
        result = self._ensure(urlopen)
        self.assertEqual(result, self.destination)
        with open(self.destination, "rb") as handle:
            self.assertEqual(handle.read(), ISO_BYTES)
        self.assertFalse(os.path.exists(self.archive))

    def test_verified_media_skips_download(self):
        """A destination whose hash matches is reused, no download."""
        with open(self.destination, "wb") as handle:
            handle.write(ISO_BYTES)
        urlopen = mock.Mock()
        self._ensure(urlopen)
        urlopen.assert_not_called()

    def test_corrupt_media_is_replaced(self):
        """A destination failing verification is downloaded again."""
        with open(self.destination, "wb") as handle:
            handle.write(b"corrupted")
        urlopen = mock.Mock(return_value=io.BytesIO(self.zip_payload))
        self._ensure(urlopen)
        with open(self.destination, "rb") as handle:
            self.assertEqual(handle.read(), ISO_BYTES)

    def test_unverifiable_member_is_erased_and_reported(self):
        """An extracted member failing verification raises cleanly."""
        tampered = _zip_bytes({"FD14LIVE.iso": b"tampered"})
        urlopen = mock.Mock(return_value=io.BytesIO(tampered))
        with self.assertRaises(RuntimeError):
            self._ensure(urlopen)
        self.assertFalse(os.path.exists(self.destination))
        self.assertFalse(os.path.exists(self.archive))


class EnsureExtractedTests(unittest.TestCase):
    """Behavior of media.ensure_extracted()."""

    def setUp(self):
        self.workdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.workdir.cleanup)
        self.archive = os.path.join(self.workdir.name, "bundle.zip")
        with zipfile.ZipFile(self.archive, "w") as bundle:
            bundle.writestr("FD14LIVE.iso", ISO_BYTES)
        self.destination = os.path.join(
            self.workdir.name, "FD14LIVE.iso")

    def test_missing_member_is_extracted(self):
        """The archive member is written to the destination."""
        result = media.ensure_extracted(
            self.archive, "FD14LIVE.iso", self.destination)
        self.assertEqual(result, self.destination)
        with open(self.destination, "rb") as handle:
            self.assertEqual(handle.read(), ISO_BYTES)

    def test_existing_destination_is_reused(self):
        """An already-extracted file is left untouched."""
        with open(self.destination, "wb") as handle:
            handle.write(b"already here")
        result = media.ensure_extracted(
            self.archive, "FD14LIVE.iso", self.destination)
        self.assertEqual(result, self.destination)
        with open(self.destination, "rb") as handle:
            self.assertEqual(handle.read(), b"already here")


class ParseItemDefinitionTests(unittest.TestCase):
    """parse_definition() on the item (direct-download) form."""

    def test_full_item_form(self):
        """A complete item-form definition parses correctly."""
        data = {
            "name": "msdos622-boot",
            "file": "msdos622-boot.img",
            "sha256": PAYLOAD_SHA256,
            "url": "https://mirror.example/msdos/msdos622-boot.img"
        }
        result = parse_definition(data)
        self.assertIsNone(result.archive)
        self.assertEqual(
            result.url, "https://mirror.example/msdos/msdos622-boot.img")
        self.assertEqual(len(result.items), 1)
        item = result.items[0]
        self.assertEqual(item.name, "msdos622-boot")
        self.assertEqual(item.file, "msdos622-boot.img")
        self.assertEqual(item.sha256, PAYLOAD_SHA256)
        self.assertIsNone(item.local_path)
        self.assertIsNone(item.file_extension)
        self.assertIsNone(item.path)

    def test_minimal_url_form(self):
        """A definition with only sha256 and url derives name and file."""
        data = {
            "sha256": PAYLOAD_SHA256,
            "url": "https://mirror.example/msdos/msdos622-boot.img"
        }
        item = parse_definition(data).items[0]
        self.assertEqual(item.name, "msdos622-boot")
        self.assertEqual(item.file, "msdos622-boot.img")

    def test_minimal_local_path_form(self):
        """A definition with sha256 and local-path derives name and
        file from the path's file-name component."""
        data = {
            "sha256": PAYLOAD_SHA256,
            "local-path": "D:/isos/win98se.iso"
        }
        item = parse_definition(data).items[0]
        self.assertEqual(item.name, "win98se")
        self.assertEqual(item.file, "win98se.iso")
        self.assertEqual(item.local_path, "D:/isos/win98se.iso")

    def test_name_derived_from_file(self):
        """When name is omitted, it's the file without its extension."""
        data = {"file": "FD14LIVE.iso", "sha256": ISO_SHA256}
        item = parse_definition(data).items[0]
        self.assertEqual(item.name, "FD14LIVE")
        self.assertEqual(item.file, "FD14LIVE.iso")

    def test_explicit_file_extension(self):
        """file-extension overrides the extension taken from file."""
        data = {
            "file": "FD14LIVE.iso",
            "file-extension": "img",
            "sha256": ISO_SHA256
        }
        item = parse_definition(data).items[0]
        self.assertEqual(item.file_extension, "img")

    def test_missing_sha256_raises_keyerror(self):
        """A definition without sha256 raises KeyError."""
        with self.assertRaises(KeyError) as caught:
            parse_definition({"url": "https://example.com/file.img"})
        self.assertIn("sha256", str(caught.exception))

    def test_invalid_sha256_format_raises_valueerror(self):
        """An invalid sha256 format raises ValueError."""
        data = {"sha256": "not-a-hash",
                "url": "https://example.com/file.img"}
        with self.assertRaises(ValueError) as caught:
            parse_definition(data)
        self.assertIn("sha256", str(caught.exception))

    def test_sha256_wrong_length_raises_valueerror(self):
        """A sha256 with the wrong length raises ValueError."""
        data = {"sha256": "abc123",
                "url": "https://example.com/file.img"}
        with self.assertRaises(ValueError) as caught:
            parse_definition(data)
        self.assertIn("sha256", str(caught.exception))

    def test_no_source_raises_valueerror(self):
        """A definition without file, local-path, or url raises."""
        with self.assertRaises(ValueError) as caught:
            parse_definition({"sha256": PAYLOAD_SHA256})
        self.assertIn("file", str(caught.exception).lower())

    def test_empty_string_field_raises_valueerror(self):
        """Empty string values for fields raise ValueError."""
        data = {"file": "", "sha256": PAYLOAD_SHA256}
        with self.assertRaises(ValueError) as caught:
            parse_definition(data)
        self.assertIn("file", str(caught.exception))

    def test_mirror_url_list_rejected(self):
        """Mirror URL lists are rejected until milestone 2."""
        data = {
            "sha256": PAYLOAD_SHA256,
            "url": ["https://a.example/x.img", "https://b.example/x.img"]
        }
        with self.assertRaises(ValueError) as caught:
            parse_definition(data)
        self.assertIn("mirror", str(caught.exception))

    def test_archive_key_without_items_rejected(self):
        """archive is only meaningful in the archive form."""
        data = {
            "sha256": PAYLOAD_SHA256,
            "archive": "FD14-LiveCD.zip",
            "url": "https://download.freedos.org/1.4/FD14-LiveCD.zip"
        }
        with self.assertRaises(ValueError) as caught:
            parse_definition(data)
        self.assertIn("archive", str(caught.exception))

    def test_path_key_rejected_in_item_form(self):
        """path belongs to archive items, not the item form."""
        data = {
            "sha256": PAYLOAD_SHA256,
            "file": "boot.img",
            "path": "boot/boot.img"
        }
        with self.assertRaises(ValueError) as caught:
            parse_definition(data)
        self.assertIn("path", str(caught.exception))

    def test_url_without_filename_raises_valueerror(self):
        """A URL without a file-name component raises ValueError."""
        data = {"sha256": PAYLOAD_SHA256, "url": "https://example.com/"}
        with self.assertRaises(ValueError) as caught:
            parse_definition(data)
        self.assertIn("filename", str(caught.exception).lower())


class ParseArchiveDefinitionTests(unittest.TestCase):
    """parse_definition() on the archive form."""

    ARCHIVE_SHA256 = hashlib.sha256(b"zip bytes").hexdigest()

    def test_full_archive_form(self):
        """The documented FreeDOS-shaped definition parses fully."""
        data = {
            "archive": "FD14-LiveCD.zip",
            "sha256": self.ARCHIVE_SHA256,
            "url": "https://download.freedos.org/1.4/FD14-LiveCD.zip",
            "items": [
                {"name": "freedos-1.4-livecd",
                 "file": "FD14LIVE.iso",
                 "sha256": ISO_SHA256},
                {"file": "FD14BOOT.img",
                 "path": "boot/FD14BOOT.img",
                 "sha256": BOOT_SHA256}
            ]
        }
        result = parse_definition(data)
        self.assertEqual(result.archive, "FD14-LiveCD.zip")
        self.assertEqual(result.archive_sha256, self.ARCHIVE_SHA256)
        self.assertEqual(
            result.url,
            "https://download.freedos.org/1.4/FD14-LiveCD.zip")
        self.assertEqual(len(result.items), 2)
        livecd, boot = result.items
        self.assertEqual(livecd.name, "freedos-1.4-livecd")
        self.assertEqual(livecd.file, "FD14LIVE.iso")
        self.assertEqual(livecd.path, "FD14LIVE.iso")
        self.assertEqual(livecd.sha256, ISO_SHA256)
        self.assertEqual(boot.name, "FD14BOOT")
        self.assertEqual(boot.path, "boot/FD14BOOT.img")

    def test_archive_derived_from_url(self):
        """An omitted archive defaults to the url's file name."""
        data = {
            "sha256": self.ARCHIVE_SHA256,
            "url": "https://download.freedos.org/1.4/FD14-LiveCD.zip",
            "items": [{"file": "FD14LIVE.iso", "sha256": ISO_SHA256}]
        }
        result = parse_definition(data)
        self.assertEqual(result.archive, "FD14-LiveCD.zip")

    def test_archive_without_url_or_name_rejected(self):
        """No archive name and no url to derive it from is an error."""
        data = {
            "sha256": self.ARCHIVE_SHA256,
            "items": [{"file": "FD14LIVE.iso", "sha256": ISO_SHA256}]
        }
        with self.assertRaises(ValueError) as caught:
            parse_definition(data)
        self.assertIn("archive", str(caught.exception))

    def test_missing_archive_sha256_raises_keyerror(self):
        """The archive form requires the top-level archive hash."""
        data = {
            "archive": "FD14-LiveCD.zip",
            "items": [{"file": "FD14LIVE.iso", "sha256": ISO_SHA256}]
        }
        with self.assertRaises(KeyError) as caught:
            parse_definition(data)
        self.assertIn("sha256", str(caught.exception))

    def test_empty_items_rejected(self):
        """An empty items list is an error."""
        data = {
            "archive": "FD14-LiveCD.zip",
            "sha256": self.ARCHIVE_SHA256,
            "items": []
        }
        with self.assertRaises(ValueError) as caught:
            parse_definition(data)
        self.assertIn("items", str(caught.exception))

    def test_item_without_file_rejected(self):
        """items entries must state their file."""
        data = {
            "archive": "FD14-LiveCD.zip",
            "sha256": self.ARCHIVE_SHA256,
            "items": [{"sha256": ISO_SHA256}]
        }
        with self.assertRaises(ValueError) as caught:
            parse_definition(data)
        self.assertIn("file", str(caught.exception))

    def test_item_without_sha256_rejected(self):
        """items entries must carry their payload hash."""
        data = {
            "archive": "FD14-LiveCD.zip",
            "sha256": self.ARCHIVE_SHA256,
            "items": [{"file": "FD14LIVE.iso"}]
        }
        with self.assertRaises(KeyError) as caught:
            parse_definition(data)
        self.assertIn("sha256", str(caught.exception))

    def test_duplicate_item_names_rejected(self):
        """Two items resolving to one name is an error."""
        data = {
            "archive": "bundle.zip",
            "sha256": self.ARCHIVE_SHA256,
            "items": [
                {"file": "boot.img", "sha256": ISO_SHA256},
                {"name": "boot", "file": "other.img",
                 "sha256": BOOT_SHA256}
            ]
        }
        with self.assertRaises(ValueError) as caught:
            parse_definition(data)
        self.assertIn("boot", str(caught.exception))


class LoadDefinitionTests(unittest.TestCase):
    """Behavior of load_definition()."""

    def setUp(self):
        self.workdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.workdir.cleanup)

    def test_loads_valid_json_file(self):
        """A valid JSON file is loaded and parsed."""
        filepath = os.path.join(self.workdir.name, "test.json")
        data = {
            "name": "test-media",
            "file": "test.img",
            "sha256": PAYLOAD_SHA256
        }
        with open(filepath, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
        result = load_definition(filepath)
        self.assertEqual(result.items[0].name, "test-media")
        self.assertEqual(result.items[0].file, "test.img")

    def test_nonexistent_file_raises_filenotfound(self):
        """A missing file raises FileNotFoundError."""
        filepath = os.path.join(self.workdir.name, "missing.json")
        with self.assertRaises(FileNotFoundError):
            load_definition(filepath)

    def test_invalid_json_raises_jsondecodeerror(self):
        """Invalid JSON raises json.JSONDecodeError."""
        filepath = os.path.join(self.workdir.name, "invalid.json")
        with open(filepath, "w", encoding="utf-8") as handle:
            handle.write("not valid json")
        with self.assertRaises(json.JSONDecodeError):
            load_definition(filepath)

    def test_non_object_json_raises_valueerror(self):
        """A JSON array instead of object raises ValueError."""
        filepath = os.path.join(self.workdir.name, "array.json")
        with open(filepath, "w", encoding="utf-8") as handle:
            json.dump([1, 2, 3], handle)
        with self.assertRaises(ValueError) as caught:
            load_definition(filepath)
        self.assertIn("object", str(caught.exception))


class MediaHomeTestCase(unittest.TestCase):
    """Shared scaffolding: a temporary home with a media library."""

    def setUp(self):
        self.workdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.workdir.cleanup)
        self.home = self.workdir.name
        self.media_dir = os.path.join(self.home, "media")
        os.makedirs(self.media_dir)

    def write_definition(self, filename, data):
        """Write a definition file into the home's media library."""
        filepath = os.path.join(self.media_dir, filename)
        with open(filepath, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
        return filepath


class ResolveMediaTests(MediaHomeTestCase):
    """Behavior of resolve_media()."""

    def test_resolves_by_name(self):
        """A media item is found by its parsed name."""
        self.write_definition("freedos.json", {
            "name": "freedos-1.4-livecd",
            "file": "FD14LIVE.iso",
            "sha256": ISO_SHA256
        })
        result = resolve_media("freedos-1.4-livecd", home=self.home)
        self.assertEqual(result.item.name, "freedos-1.4-livecd")
        self.assertEqual(result.item.file, "FD14LIVE.iso")
        self.assertIsNone(result.definition.archive)

    def test_derived_name_resolution(self):
        """A definition without explicit name resolves by derived name."""
        self.write_definition("freedos.json", {
            "file": "FD14LIVE.iso",
            "sha256": ISO_SHA256
        })
        result = resolve_media("FD14LIVE", home=self.home)
        self.assertEqual(result.item.name, "FD14LIVE")

    def test_resolves_item_inside_archive_definition(self):
        """Archive-form items resolve with their owning definition."""
        self.write_definition("livecd.json", {
            "archive": "FD14-LiveCD.zip",
            "sha256": hashlib.sha256(b"zip").hexdigest(),
            "url": "https://example.invalid/FD14-LiveCD.zip",
            "items": [
                {"name": "freedos-1.4-livecd", "file": "FD14LIVE.iso",
                 "sha256": ISO_SHA256},
                {"file": "FD14BOOT.img", "sha256": BOOT_SHA256}
            ]
        })
        result = resolve_media("FD14BOOT", home=self.home)
        self.assertEqual(result.item.file, "FD14BOOT.img")
        self.assertEqual(result.definition.archive, "FD14-LiveCD.zip")

    def test_missing_name_raises_filenotfound(self):
        """Requesting a non-existent name raises FileNotFoundError."""
        with self.assertRaises(FileNotFoundError) as caught:
            resolve_media("nonexistent", home=self.home)
        self.assertIn("nonexistent", str(caught.exception))

    def test_duplicate_names_raise_valueerror(self):
        """The same name in two definition files is an error."""
        self.write_definition("first.json", {
            "name": "duplicate", "file": "file1.img",
            "sha256": PAYLOAD_SHA256
        })
        self.write_definition("second.json", {
            "name": "duplicate", "file": "file2.img",
            "sha256": ISO_SHA256
        })
        with self.assertRaises(ValueError) as caught:
            resolve_media("duplicate", home=self.home)
        self.assertIn("duplicate", str(caught.exception))
        self.assertIn("multiple", str(caught.exception).lower())

    def test_nonexistent_media_dir_raises_filenotfound(self):
        """A missing media directory raises FileNotFoundError."""
        missing_home = os.path.join(self.home, "elsewhere")
        with self.assertRaises(FileNotFoundError) as caught:
            resolve_media("any-name", home=missing_home)
        self.assertIn("media", str(caught.exception).lower())

    def test_skips_non_json_files(self):
        """Non-JSON files in the media directory are ignored."""
        self.write_definition("readme.txt", {"not": "json"})
        self.write_definition("test.json", {
            "name": "test", "file": "test.img",
            "sha256": PAYLOAD_SHA256
        })
        result = resolve_media("test", home=self.home)
        self.assertEqual(result.item.name, "test")

    def test_skips_invalid_files(self):
        """Invalid JSON files are skipped without error."""
        invalid_path = os.path.join(self.media_dir, "invalid.json")
        with open(invalid_path, "w", encoding="utf-8") as handle:
            handle.write("not valid json")
        self.write_definition("test.json", {
            "name": "test", "file": "test.img",
            "sha256": PAYLOAD_SHA256
        })
        result = resolve_media("test", home=self.home)
        self.assertEqual(result.item.name, "test")


class FetchMediaItemFormTests(MediaHomeTestCase):
    """fetch_media() on item-form (direct download) definitions."""

    ITEM_URL = "https://example.invalid/msdos/msdos622-boot.img"

    def setUp(self):
        super().setUp()
        self.write_definition("boot.json", {
            "name": "msdos622-boot",
            "file": "msdos622-boot.img",
            "sha256": PAYLOAD_SHA256,
            "url": self.ITEM_URL
        })
        self.payload_path = os.path.join(
            self.home, "cache", "media", "msdos622-boot.img")

    def _fetch(self, urlopen):
        with mock.patch("reliquary.media.urlopen", urlopen):
            return fetch_media("msdos622-boot", home=self.home)

    def test_download_lands_in_media_cache(self):
        """The payload downloads straight into cache/media/ under its
        item name, verified."""
        urlopen = mock.Mock(return_value=io.BytesIO(PAYLOAD))
        result = self._fetch(urlopen)
        urlopen.assert_called_once_with(self.ITEM_URL)
        self.assertEqual(result, self.payload_path)
        with open(result, "rb") as handle:
            self.assertEqual(handle.read(), PAYLOAD)

    def test_verified_payload_is_never_overwritten(self):
        """An existing payload that verifies is returned untouched,
        with no download."""
        os.makedirs(os.path.dirname(self.payload_path))
        with open(self.payload_path, "wb") as handle:
            handle.write(PAYLOAD)
        urlopen = mock.Mock()
        result = self._fetch(urlopen)
        urlopen.assert_not_called()
        self.assertEqual(result, self.payload_path)

    def test_corrupt_payload_is_refetched(self):
        """A payload failing verification is treated as absent and
        downloaded again."""
        os.makedirs(os.path.dirname(self.payload_path))
        with open(self.payload_path, "wb") as handle:
            handle.write(b"corrupted")
        result = self._fetch(mock.Mock(return_value=io.BytesIO(PAYLOAD)))
        with open(result, "rb") as handle:
            self.assertEqual(handle.read(), PAYLOAD)

    def test_unverifiable_download_is_erased_and_reported(self):
        """A download failing verification is deleted and raises with
        both hashes."""
        tampered_sha256 = hashlib.sha256(b"tampered").hexdigest()
        with self.assertRaises(RuntimeError) as caught:
            self._fetch(mock.Mock(return_value=io.BytesIO(b"tampered")))
        self.assertIn(PAYLOAD_SHA256, str(caught.exception))
        self.assertIn(tampered_sha256, str(caught.exception))
        self.assertFalse(os.path.exists(self.payload_path))

    def test_missing_payload_without_source_reports_item(self):
        """No payload and no url is an error naming item and hash."""
        self.write_definition("local.json", {
            "name": "handmade", "file": "handmade.img",
            "sha256": ISO_SHA256
        })
        with self.assertRaises(RuntimeError) as caught:
            fetch_media("handmade", home=self.home)
        message = str(caught.exception)
        self.assertIn("handmade", message)
        self.assertIn(ISO_SHA256, message)

    def test_corrupt_payload_without_source_reports_both_hashes(self):
        """A failing payload with no source names both hashes."""
        self.write_definition("local.json", {
            "name": "handmade", "file": "handmade.img",
            "sha256": ISO_SHA256
        })
        payload = os.path.join(
            self.home, "cache", "media", "handmade.img")
        os.makedirs(os.path.dirname(payload))
        with open(payload, "wb") as handle:
            handle.write(b"corrupted")
        corrupted_sha256 = hashlib.sha256(b"corrupted").hexdigest()
        with self.assertRaises(RuntimeError) as caught:
            fetch_media("handmade", home=self.home)
        message = str(caught.exception)
        self.assertIn("handmade", message)
        self.assertIn(ISO_SHA256, message)
        self.assertIn(corrupted_sha256, message)

    def test_file_extension_override_names_the_cached_payload(self):
        """file-extension renames the cached payload's extension."""
        self.write_definition("renamed.json", {
            "name": "renamed", "file": "payload.bin",
            "file-extension": "img", "sha256": PAYLOAD_SHA256,
            "url": "https://example.invalid/payload.bin"
        })
        urlopen = mock.Mock(return_value=io.BytesIO(PAYLOAD))
        with mock.patch("reliquary.media.urlopen", urlopen):
            result = fetch_media("renamed", home=self.home)
        self.assertEqual(
            result,
            os.path.join(self.home, "cache", "media", "renamed.img"))

    def test_local_path_payload_is_verified_in_place(self):
        """A local-path payload verifies where it lives; no cache."""
        elsewhere = os.path.join(self.home, "isos", "win98se.iso")
        os.makedirs(os.path.dirname(elsewhere))
        with open(elsewhere, "wb") as handle:
            handle.write(PAYLOAD)
        self.write_definition("local.json", {
            "sha256": PAYLOAD_SHA256,
            "local-path": elsewhere.replace(os.sep, "/")
        })
        result = fetch_media("win98se", home=self.home)
        self.assertEqual(
            os.path.normpath(result), os.path.normpath(elsewhere))
        self.assertFalse(os.path.exists(
            os.path.join(self.home, "cache", "media", "win98se.iso")))


class FetchMediaArchiveFormTests(MediaHomeTestCase):
    """fetch_media() on archive-form definitions: the two caches."""

    def setUp(self):
        super().setUp()
        self.zip_payload = _zip_bytes({
            "FD14LIVE.iso": ISO_BYTES,
            "boot/FD14BOOT.img": BOOT_BYTES,
        })
        self.zip_sha256 = hashlib.sha256(self.zip_payload).hexdigest()
        self.write_definition("livecd.json", {
            "archive": "FD14-LiveCD.zip",
            "sha256": self.zip_sha256,
            "url": URL,
            "items": [
                {"name": "freedos-1.4-livecd", "file": "FD14LIVE.iso",
                 "sha256": ISO_SHA256},
                {"file": "FD14BOOT.img", "path": "boot/FD14BOOT.img",
                 "sha256": BOOT_SHA256}
            ]
        })
        self.archive_path = os.path.join(
            self.home, "cache", "downloads", "FD14-LiveCD.zip")
        self.payload_path = os.path.join(
            self.home, "cache", "media", "freedos-1.4-livecd.iso")

    def _fetch(self, urlopen, name="freedos-1.4-livecd"):
        with mock.patch("reliquary.media.urlopen", urlopen):
            return fetch_media(name, home=self.home)

    def test_livecd_zip_lands_as_verified_iso(self):
        """The spike exit criterion: the zip downloads into
        cache/downloads/, the iso extracts into cache/media/, both
        verified, and the archive stays cached."""
        urlopen = mock.Mock(return_value=io.BytesIO(self.zip_payload))
        result = self._fetch(urlopen)
        urlopen.assert_called_once_with(URL)
        self.assertEqual(result, self.payload_path)
        with open(result, "rb") as handle:
            self.assertEqual(handle.read(), ISO_BYTES)
        self.assertTrue(os.path.exists(self.archive_path))
        with open(self.archive_path, "rb") as handle:
            self.assertEqual(handle.read(), self.zip_payload)

    def test_item_path_selects_the_archive_member(self):
        """An item's path picks its member out of a subdirectory, and
        the payload caches under the item's name."""
        urlopen = mock.Mock(return_value=io.BytesIO(self.zip_payload))
        result = self._fetch(urlopen, name="FD14BOOT")
        self.assertEqual(
            result,
            os.path.join(self.home, "cache", "media", "FD14BOOT.img"))
        with open(result, "rb") as handle:
            self.assertEqual(handle.read(), BOOT_BYTES)

    def test_cached_archive_is_reextracted_without_download(self):
        """A verifying archive already in cache/downloads/ serves the
        payload with no download."""
        os.makedirs(os.path.dirname(self.archive_path))
        with open(self.archive_path, "wb") as handle:
            handle.write(self.zip_payload)
        urlopen = mock.Mock()
        result = self._fetch(urlopen)
        urlopen.assert_not_called()
        with open(result, "rb") as handle:
            self.assertEqual(handle.read(), ISO_BYTES)

    def test_verified_payload_skips_archive_and_download(self):
        """An existing verified payload is returned untouched — no
        archive, no download."""
        os.makedirs(os.path.dirname(self.payload_path))
        with open(self.payload_path, "wb") as handle:
            handle.write(ISO_BYTES)
        urlopen = mock.Mock()
        result = self._fetch(urlopen)
        urlopen.assert_not_called()
        self.assertEqual(result, self.payload_path)
        self.assertFalse(os.path.exists(self.archive_path))

    def test_corrupt_cached_archive_is_redownloaded(self):
        """A cached archive failing verification is discarded and
        downloaded again."""
        os.makedirs(os.path.dirname(self.archive_path))
        with open(self.archive_path, "wb") as handle:
            handle.write(b"corrupted")
        urlopen = mock.Mock(return_value=io.BytesIO(self.zip_payload))
        result = self._fetch(urlopen)
        urlopen.assert_called_once_with(URL)
        with open(result, "rb") as handle:
            self.assertEqual(handle.read(), ISO_BYTES)

    def test_missing_archive_without_url_reports_archive(self):
        """No cached archive and no url is an error naming the
        archive."""
        self.write_definition("sourceless.json", {
            "archive": "handmade.zip",
            "sha256": self.zip_sha256,
            "items": [{"name": "handmade-boot", "file": "boot.img",
                       "sha256": BOOT_SHA256}]
        })
        with self.assertRaises(RuntimeError) as caught:
            fetch_media("handmade-boot", home=self.home)
        self.assertIn("handmade.zip", str(caught.exception))

    def test_unverifiable_archive_download_is_erased_and_reported(self):
        """A downloaded archive failing verification is deleted and
        raises with both hashes."""
        tampered = _zip_bytes({"FD14LIVE.iso": ISO_BYTES})
        tampered_sha256 = hashlib.sha256(tampered).hexdigest()
        with self.assertRaises(RuntimeError) as caught:
            self._fetch(mock.Mock(return_value=io.BytesIO(tampered)))
        message = str(caught.exception)
        self.assertIn(self.zip_sha256, message)
        self.assertIn(tampered_sha256, message)
        self.assertFalse(os.path.exists(self.archive_path))

    def test_tampered_member_is_erased_and_reported(self):
        """An extracted payload failing verification leaves no
        payload behind and names both hashes."""
        tampered_zip = _zip_bytes({
            "FD14LIVE.iso": b"tampered",
            "boot/FD14BOOT.img": BOOT_BYTES,
        })
        self.write_definition("livecd.json", {
            "archive": "FD14-LiveCD.zip",
            "sha256": hashlib.sha256(tampered_zip).hexdigest(),
            "url": URL,
            "items": [
                {"name": "freedos-1.4-livecd", "file": "FD14LIVE.iso",
                 "sha256": ISO_SHA256}
            ]
        })
        tampered_sha256 = hashlib.sha256(b"tampered").hexdigest()
        with self.assertRaises(RuntimeError) as caught:
            self._fetch(mock.Mock(return_value=io.BytesIO(tampered_zip)))
        message = str(caught.exception)
        self.assertIn(ISO_SHA256, message)
        self.assertIn(tampered_sha256, message)
        self.assertFalse(os.path.exists(self.payload_path))
        self.assertFalse(os.path.exists(self.payload_path + ".part"))

    def test_corrupt_payload_heals_from_cached_archive(self):
        """A corrupted payload is re-extracted from the cached
        archive — the cache heals itself without a download."""
        os.makedirs(os.path.dirname(self.archive_path))
        with open(self.archive_path, "wb") as handle:
            handle.write(self.zip_payload)
        os.makedirs(os.path.dirname(self.payload_path))
        with open(self.payload_path, "wb") as handle:
            handle.write(b"corrupted")
        urlopen = mock.Mock()
        result = self._fetch(urlopen)
        urlopen.assert_not_called()
        with open(result, "rb") as handle:
            self.assertEqual(handle.read(), ISO_BYTES)


if __name__ == "__main__":
    unittest.main()
