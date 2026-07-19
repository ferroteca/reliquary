# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Hash-verified acquisition of OS installation media."""

import hashlib
import os
import sys
from urllib.request import urlopen

_CHUNK = 1024 * 1024


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_media(url, sha256, destination):
    """Return verified install media at destination, downloading if needed.

    A cached file that matches the expected SHA-256 is reused. A cached
    file that fails verification is deleted and downloaded again. A
    download that fails verification is deleted and reported.
    """
    if os.path.exists(destination):
        if _sha256(destination) == sha256:
            return destination
        print(f"cached media failed verification, discarding: "
              f"{destination}", file=sys.stderr)
        os.remove(destination)
    _download(url, destination)
    actual = _sha256(destination)
    if actual != sha256:
        os.remove(destination)
        raise RuntimeError(
            f"downloaded media failed verification: {url} has "
            f"SHA-256 {actual}, expected {sha256}")
    return destination


def _download(url, destination):
    """Stream url into destination, replacing it atomically."""
    os.makedirs(os.path.dirname(destination) or ".", exist_ok=True)
    partial = destination + ".part"
    print(f"downloading {url}", file=sys.stderr)
    with urlopen(url) as response:
        total = getattr(response, "length", None)
        received = 0
        milestone = 0
        with open(partial, "wb") as handle:
            for chunk in iter(lambda: response.read(_CHUNK), b""):
                handle.write(chunk)
                received += len(chunk)
                if total and received * 10 // total > milestone:
                    milestone = received * 10 // total
                    print(f"  {received // (1 << 20)} MiB "
                          f"({milestone * 10}%)", file=sys.stderr)
    os.replace(partial, destination)
