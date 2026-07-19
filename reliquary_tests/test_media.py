# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Tests for hash-verified install media acquisition."""

import hashlib
import io
import os
import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main()
