# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Tests for hash-verified install media acquisition."""

import hashlib
import io
import os
import tempfile
import unittest
import zipfile
from unittest import mock

from reliquary import media

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


if __name__ == "__main__":
    unittest.main()
