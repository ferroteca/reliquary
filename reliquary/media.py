# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Hash-verified acquisition of OS installation media."""

import hashlib
import os
import shutil
import sys
import zipfile
from urllib.request import urlopen

_CHUNK = 1024 * 1024


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_media(url, sha256, destination, archive_member=None):
    """Return verified install media at destination, fetching if needed.

    The destination's SHA-256 is checked on every call: a cached file
    that verifies is reused, one that fails verification is deleted
    and fetched again, and a fetch that fails verification is deleted
    and reported. Without ``archive_member``, the url is downloaded
    directly to destination. With ``archive_member``, the url is a zip
    archive: the member is extracted to destination and the archive is
    deleted — only the extracted, verified file is kept.
    """
    if os.path.exists(destination):
        if _sha256(destination) == sha256:
            return destination
        print(f"cached media failed verification, discarding: "
              f"{destination}", file=sys.stderr)
        os.remove(destination)
    if archive_member is None:
        _download(url, destination)
    else:
        archive = os.path.join(os.path.dirname(destination) or ".",
                               os.path.basename(url))
        try:
            _download(url, archive)
            ensure_extracted(archive, archive_member, destination)
        finally:
            if os.path.exists(archive):
                os.remove(archive)
    actual = _sha256(destination)
    if actual != sha256:
        os.remove(destination)
        raise RuntimeError(
            f"downloaded media failed verification: {url} has "
            f"SHA-256 {actual}, expected {sha256}")
    return destination


def ensure_extracted(archive, member, destination):
    """Return the archive member extracted at destination.

    An already-extracted destination is reused untouched; otherwise the
    member is streamed out of the zip archive atomically.
    """
    if os.path.exists(destination):
        return destination
    print(f"extracting {member} from {os.path.basename(archive)}",
          file=sys.stderr)
    os.makedirs(os.path.dirname(destination) or ".", exist_ok=True)
    partial = destination + ".part"
    with zipfile.ZipFile(archive) as bundle:
        with bundle.open(member) as source, \
                open(partial, "wb") as handle:
            shutil.copyfileobj(source, handle, _CHUNK)
    os.replace(partial, destination)
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
