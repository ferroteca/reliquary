# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Unit-test guards against live external effects."""

import subprocess
import unittest
import urllib.request


class ExternalEffectGuardTests(unittest.TestCase):
    def test_network_downloads_must_be_mocked(self):
        with self.assertRaisesRegex(AssertionError, "network downloads"):
            urllib.request.urlopen("https://example.invalid")

    def test_backend_process_execution_must_be_mocked(self):
        with self.assertRaisesRegex(AssertionError, "backend"):
            subprocess.Popen(["qemu-system-i386"])

        with self.assertRaisesRegex(AssertionError, "backend"):
            subprocess.run(["qemu-img", "info", "disk.img"])


if __name__ == "__main__":
    unittest.main()
