# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Agentless DOS provisioning and guest interaction."""

import hashlib
import os
import re
import time
import urllib.request
import zipfile

from .home import drives_dir
from .lifecycle import qmp_session
from .machine import screen_text, send_text
from .media import boot_guess, scan_drives


_PROMPT_RE = re.compile(r"^[A-Z]:(\\[^>]*)?>$")
_FREEDOS_ZIP_URL = (
    "https://download.freedos.org/1.4/FD14-FloppyEdition.zip")
_FREEDOS_ZIP_SHA256 = (
    "45b1fa7c52dd996c3bfa5e352ffcd410781b952a6ad629f15a4"
    "c9ec4bbaefc5a")
_FREEDOS_BOOT_IMG = "144m/x86BOOT.img"


def run_command(command, timeout=120, port=None, home=None):
    """Type a DOS command and wait for the prompt to return."""
    with qmp_session(port, home) as qmp:
        send_text(command, qmp)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            rows = [row for row in screen_text(qmp) if row]
            if rows and _PROMPT_RE.match(rows[-1]):
                return
            time.sleep(2)
    raise TimeoutError(
        f"timed out after {timeout}s waiting for command to finish: "
        f"{command}")


def boot_to_dos(timeout=90, port=None, home=None):
    """Wait for a DOS prompt, declining the FreeDOS installer."""
    print("waiting for a DOS prompt...")
    installer_seen = False
    with qmp_session(port, home) as qmp:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            rows = [row for row in screen_text(qmp) if row]
            if rows and _PROMPT_RE.match(rows[-1]):
                print(f"at DOS prompt: {rows[-1]}")
                return
            if (not installer_seen
                    and any("Do you want to proceed" in row
                            for row in rows)):
                installer_seen = True
                print("FreeDOS installer detected; declining the install...")
                send_text("n", qmp)
            time.sleep(2)
    raise TimeoutError(
        f"timed out after {timeout}s waiting for a DOS prompt")


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as archive:
        for block in iter(lambda: archive.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def download(home=None):
    """Ensure that the declared machine has a bootable DOS image."""
    drives = drives_dir(home)
    media = scan_drives(drives)
    if boot_guess(media) is not None:
        print(f"already bootable: {drives}")
        return
    if 0 in media["floppy"]:
        raise RuntimeError(
            f"nothing bootable is declared under {drives}, and the "
            "FreeDOS boot floppy cannot be installed: floppy slot 0 "
            f"is taken by the staged directory "
            f"{media['floppy'][0][0]}")
    download_boot_image(drives)


def prepare_drives(drives):
    """Install the DOS fallback when a start has no bootable media."""
    print(f"nothing bootable under {drives}; fetching FreeDOS")
    media = scan_drives(drives)
    if 0 in media["floppy"]:
        raise RuntimeError(
            f"nothing bootable is declared under {drives}, and the "
            "FreeDOS boot floppy cannot be installed: floppy slot 0 "
            f"is taken by the staged directory "
            f"{media['floppy'][0][0]}")
    download_boot_image(drives)


def download_boot_image(drives):
    """Fetch, verify, and install the FreeDOS 1.4 boot floppy."""
    os.makedirs(drives, exist_ok=True)
    image = os.path.join(drives, "floppy.img")
    zip_path = os.path.join(drives, "FD14-FloppyEdition.zip")
    if not os.path.exists(zip_path):
        print("downloading FreeDOS 1.4 FloppyEdition (~23 MB) "
              "from download.freedos.org...")
        part = zip_path + ".part"
        urllib.request.urlretrieve(_FREEDOS_ZIP_URL, part)
        os.replace(part, zip_path)
    digest = _sha256(zip_path)
    if digest != _FREEDOS_ZIP_SHA256:
        os.remove(zip_path)
        raise ValueError(
            f"checksum mismatch for {zip_path}:\n"
            f"  expected {_FREEDOS_ZIP_SHA256}\n"
            f"  got      {digest}\n"
            "the corrupt download was removed; retry")
    print(f"extracting {_FREEDOS_BOOT_IMG}...")
    with zipfile.ZipFile(zip_path) as archive:
        try:
            with archive.open(_FREEDOS_BOOT_IMG) as source, \
                    open(image + ".part", "wb") as destination:
                destination.write(source.read())
        except KeyError:
            raise FileNotFoundError(
                f"{_FREEDOS_BOOT_IMG} not found in the archive")
        os.replace(image + ".part", image)
    os.remove(zip_path)
    print(f"ready: {image}")
