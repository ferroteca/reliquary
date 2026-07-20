# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Tests for hash-verified install media acquisition."""

import hashlib
import io
import json
import os
import tempfile
import unittest
import zipfile
from unittest import mock

from reliquary import media
from reliquary.media import MediaDefinition, parse_definition, load_definition, resolve_media

PAYLOAD = b"freedos installer bytes"
PAYLOAD_SHA256 = hashlib.sha256(PAYLOAD).hexdigest()
URL = "https://example.invalid/FD14-LiveCD.zip"


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
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as bundle:
            bundle.writestr("FD14LIVE.iso", b"iso bytes")
        self.zip_payload = buffer.getvalue()
        self.iso_sha256 = hashlib.sha256(b"iso bytes").hexdigest()

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
            self.assertEqual(handle.read(), b"iso bytes")
        self.assertFalse(os.path.exists(self.archive))

    def test_verified_media_skips_download(self):
        """A destination whose hash matches is reused, no download."""
        with open(self.destination, "wb") as handle:
            handle.write(b"iso bytes")
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
            self.assertEqual(handle.read(), b"iso bytes")

    def test_unverifiable_member_is_erased_and_reported(self):
        """An extracted member failing verification raises cleanly."""
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as bundle:
            bundle.writestr("FD14LIVE.iso", b"tampered")
        urlopen = mock.Mock(return_value=io.BytesIO(buffer.getvalue()))
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
            bundle.writestr("FD14LIVE.iso", b"iso bytes")
        self.destination = os.path.join(
            self.workdir.name, "FD14LIVE.iso")

    def test_missing_member_is_extracted(self):
        """The archive member is written to the destination."""
        result = media.ensure_extracted(
            self.archive, "FD14LIVE.iso", self.destination)
        self.assertEqual(result, self.destination)
        with open(self.destination, "rb") as handle:
            self.assertEqual(handle.read(), b"iso bytes")

    def test_existing_destination_is_reused(self):
        """An already-extracted file is left untouched."""
        with open(self.destination, "wb") as handle:
            handle.write(b"already here")
        result = media.ensure_extracted(
            self.archive, "FD14LIVE.iso", self.destination)
        self.assertEqual(result, self.destination)
        with open(self.destination, "rb") as handle:
            self.assertEqual(handle.read(), b"already here")


class ParseDefinitionTests(unittest.TestCase):
    """Behavior of parse_definition()."""

    def test_full_item_form(self):
        """A complete item-form definition parses correctly."""
        data = {
            "name": "msdos622-boot",
            "file": "msdos622-boot.img",
            "sha256": "9f4c2c1e5a7b8d3f2e1a0b9c8d7e6f5a4b3c2d1e0f9a8b7c6d5e4f3a2b1c0d9e",
            "url": "https://mirror.example/msdos/msdos622-boot.img"
        }
        result = parse_definition(data)
        self.assertEqual(result.name, "msdos622-boot")
        self.assertEqual(result.file, "msdos622-boot.img")
        self.assertEqual(result.sha256, "9f4c2c1e5a7b8d3f2e1a0b9c8d7e6f5a4b3c2d1e0f9a8b7c6d5e4f3a2b1c0d9e")
        self.assertEqual(result.url, "https://mirror.example/msdos/msdos622-boot.img")
        self.assertIsNone(result.local_path)
        self.assertIsNone(result.file_extension)

    def test_minimal_url_form(self):
        """A minimal definition with only sha256 and url derives name and file."""
        data = {
            "sha256": "9f4c2c1e5a7b8d3f2e1a0b9c8d7e6f5a4b3c2d1e0f9a8b7c6d5e4f3a2b1c0d9e",
            "url": "https://mirror.example/msdos/msdos622-boot.img"
        }
        result = parse_definition(data)
        self.assertEqual(result.name, "msdos622-boot")
        self.assertEqual(result.file, "msdos622-boot.img")
        self.assertEqual(result.url, "https://mirror.example/msdos/msdos622-boot.img")

    def test_minimal_local_path_form(self):
        """A minimal definition with only sha256 and local-path derives name and file."""
        data = {
            "sha256": "b1946ac92492d2347c6235b4d2611184a1e5d2c383a3a0522f9d21ac96f78c40",
            "local-path": "D:/isos/win98se.iso"
        }
        result = parse_definition(data)
        self.assertEqual(result.name, "win98se")
        self.assertEqual(result.file, "win98se.iso")
        self.assertEqual(result.local_path, "D:/isos/win98se.iso")

    def test_name_derived_from_file(self):
        """When name is omitted, it's derived from file without extension."""
        data = {
            "file": "FD14LIVE.iso",
            "sha256": "6d3b1b4b6b9c4dbd1bcd8e0d640d29aa22a5a04f2a4b0a6a49b1e0f56a5b1c9e"
        }
        result = parse_definition(data)
        self.assertEqual(result.name, "FD14LIVE")
        self.assertEqual(result.file, "FD14LIVE.iso")

    def test_file_derived_from_local_path(self):
        """When file is omitted but local-path is present, file is derived."""
        data = {
            "local-path": "/path/to/boot.img",
            "sha256": "1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b"
        }
        result = parse_definition(data)
        self.assertEqual(result.file, "boot.img")
        self.assertEqual(result.name, "boot")

    def test_explicit_file_extension(self):
        """file-extension overrides the extension from file."""
        data = {
            "file": "FD14LIVE.iso",
            "file-extension": "img",
            "sha256": "6d3b1b4b6b9c4dbd1bcd8e0d640d29aa22a5a04f2a4b0a6a49b1e0f56a5b1c9e"
        }
        result = parse_definition(data)
        self.assertEqual(result.file_extension, "img")

    def test_missing_sha256_raises_keyerror(self):
        """A definition without sha256 raises KeyError."""
        data = {
            "url": "https://example.com/file.img"
        }
        with self.assertRaises(KeyError) as caught:
            parse_definition(data)
        self.assertIn("sha256", str(caught.exception))

    def test_invalid_sha256_format_raises_valueerror(self):
        """An invalid sha256 format raises ValueError."""
        data = {
            "sha256": "not-a-hash",
            "url": "https://example.com/file.img"
        }
        with self.assertRaises(ValueError) as caught:
            parse_definition(data)
        self.assertIn("sha256", str(caught.exception))

    def test_sha256_wrong_length_raises_valueerror(self):
        """A sha256 with wrong length raises ValueError."""
        data = {
            "sha256": "abc123",
            "url": "https://example.com/file.img"
        }
        with self.assertRaises(ValueError) as caught:
            parse_definition(data)
        self.assertIn("sha256", str(caught.exception))

    def test_no_source_raises_valueerror(self):
        """A definition without file, local-path, or url raises ValueError."""
        data = {
            "sha256": "9f4c2c1e5a7b8d3f2e1a0b9c8d7e6f5a4b3c2d1e0f9a8b7c6d5e4f3a2b1c0d9e"
        }
        with self.assertRaises(ValueError) as caught:
            parse_definition(data)
        self.assertIn("file", str(caught.exception).lower())

    def test_empty_string_field_raises_valueerror(self):
        """Empty string values for required fields raise ValueError."""
        data = {
            "file": "",
            "sha256": "9f4c2c1e5a7b8d3f2e1a0b9c8d7e6f5a4b3c2d1e0f9a8b7c6d5e4f3a2b1c0d9e"
        }
        with self.assertRaises(ValueError) as caught:
            parse_definition(data)
        self.assertIn("file", str(caught.exception))

    def test_archive_form_rejected(self):
        """Archive form (items key) is rejected with clear error."""
        data = {
            "sha256": "cf3f4c9f2f4d9e70a3a08a52f1c67c0ff01b18cf07a4c0f1a3f5b7e6d1a2b3c4",
            "archive": "FD14-LiveCD.zip",
            "url": "https://download.freedos.org/1.4/FD14-LiveCD.zip",
            "items": []
        }
        with self.assertRaises(ValueError) as caught:
            parse_definition(data)
        self.assertIn("not yet implemented", str(caught.exception))

    def test_archive_key_rejected(self):
        """Archive key alone is rejected with clear error."""
        data = {
            "sha256": "cf3f4c9f2f4d9e70a3a08a52f1c67c0ff01b18cf07a4c0f1a3f5b7e6d1a2b3c4",
            "archive": "FD14-LiveCD.zip",
            "url": "https://download.freedos.org/1.4/FD14-LiveCD.zip"
        }
        with self.assertRaises(ValueError) as caught:
            parse_definition(data)
        self.assertIn("not yet implemented", str(caught.exception))

    def test_url_without_filename_raises_valueerror(self):
        """A URL without a filename component raises ValueError."""
        data = {
            "sha256": "9f4c2c1e5a7b8d3f2e1a0b9c8d7e6f5a4b3c2d1e0f9a8b7c6d5e4f3a2b1c0d9e",
            "url": "https://example.com/"
        }
        with self.assertRaises(ValueError) as caught:
            parse_definition(data)
        self.assertIn("filename", str(caught.exception).lower())


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
            "sha256": "9f4c2c1e5a7b8d3f2e1a0b9c8d7e6f5a4b3c2d1e0f9a8b7c6d5e4f3a2b1c0d9e"
        }
        with open(filepath, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
        
        result = load_definition(filepath)
        self.assertEqual(result.name, "test-media")
        self.assertEqual(result.file, "test.img")

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


class ResolveMediaTests(unittest.TestCase):
    """Behavior of resolve_media()."""

    def setUp(self):
        self.workdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.workdir.cleanup)
        self.media_dir = os.path.join(self.workdir.name, "media")
        os.makedirs(self.media_dir)

    def _write_definition(self, filename, data):
        """Helper to write a definition file."""
        filepath = os.path.join(self.media_dir, filename)
        with open(filepath, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
        return filepath

    def test_resolves_by_name(self):
        """A media definition is found by its parsed name."""
        data = {
            "name": "freedos-1.4-livecd",
            "file": "FD14LIVE.iso",
            "sha256": "6d3b1b4b6b9c4dbd1bcd8e0d640d29aa22a5a04f2a4b0a6a49b1e0f56a5b1c9e"
        }
        self._write_definition("freedos.json", data)
        
        from reliquary.home import set_home
        set_home(self.workdir.name)
        
        result = resolve_media("freedos-1.4-livecd")
        self.assertEqual(result.name, "freedos-1.4-livecd")
        self.assertEqual(result.file, "FD14LIVE.iso")

    def test_derived_name_resolution(self):
        """A definition without explicit name resolves by derived name."""
        data = {
            "file": "FD14LIVE.iso",
            "sha256": "6d3b1b4b6b9c4dbd1bcd8e0d640d29aa22a5a04f2a4b0a6a49b1e0f56a5b1c9e"
        }
        self._write_definition("freedos.json", data)
        
        from reliquary.home import set_home
        set_home(self.workdir.name)
        
        result = resolve_media("FD14LIVE")
        self.assertEqual(result.name, "FD14LIVE")

    def test_missing_name_raises_filenotfound(self):
        """Requesting a non-existent name raises FileNotFoundError."""
        from reliquary.home import set_home
        set_home(self.workdir.name)
        
        with self.assertRaises(FileNotFoundError) as caught:
            resolve_media("nonexistent")
        self.assertIn("nonexistent", str(caught.exception))

    def test_duplicate_names_raise_valueerror(self):
        """Multiple definitions with the same name raise ValueError."""
        data1 = {
            "name": "duplicate",
            "file": "file1.img",
            "sha256": "9f4c2c1e5a7b8d3f2e1a0b9c8d7e6f5a4b3c2d1e0f9a8b7c6d5e4f3a2b1c0d9e"
        }
        data2 = {
            "name": "duplicate",
            "file": "file2.img",
            "sha256": "1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b"
        }
        self._write_definition("first.json", data1)
        self._write_definition("second.json", data2)
        
        from reliquary.home import set_home
        set_home(self.workdir.name)
        
        with self.assertRaises(ValueError) as caught:
            resolve_media("duplicate")
        self.assertIn("duplicate", str(caught.exception))
        self.assertIn("multiple", str(caught.exception).lower())

    def test_nonexistent_media_dir_raises_filenotfound(self):
        """A missing media directory raises FileNotFoundError."""
        from reliquary.home import set_home
        set_home(self.workdir.name)  # media/ doesn't exist here
        
        with self.assertRaises(FileNotFoundError) as caught:
            resolve_media("any-name")
        self.assertIn("media", str(caught.exception).lower())

    def test_skips_non_json_files(self):
        """Non-JSON files in the media directory are ignored."""
        self._write_definition("readme.txt", {"not": "json"})
        
        data = {
            "name": "test",
            "file": "test.img",
            "sha256": "9f4c2c1e5a7b8d3f2e1a0b9c8d7e6f5a4b3c2d1e0f9a8b7c6d5e4f3a2b1c0d9e"
        }
        self._write_definition("test.json", data)
        
        from reliquary.home import set_home
        set_home(self.workdir.name)
        
        result = resolve_media("test")
        self.assertEqual(result.name, "test")

    def test_skips_invalid_files(self):
        """Invalid JSON files are skipped without error."""
        # Write an invalid JSON file
        invalid_path = os.path.join(self.media_dir, "invalid.json")
        with open(invalid_path, "w", encoding="utf-8") as handle:
            handle.write("not valid json")
        
        data = {
            "name": "test",
            "file": "test.img",
            "sha256": "9f4c2c1e5a7b8d3f2e1a0b9c8d7e6f5a4b3c2d1e0f9a8b7c6d5e4f3a2b1c0d9e"
        }
        self._write_definition("test.json", data)
        
        from reliquary.home import set_home
        set_home(self.workdir.name)
        
        result = resolve_media("test")
        self.assertEqual(result.name, "test")


if __name__ == "__main__":
    unittest.main()
