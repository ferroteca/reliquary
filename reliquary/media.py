# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Hash-verified acquisition of OS installation media."""

import hashlib
import json
import os
import re
import shutil
import sys
import zipfile
from dataclasses import dataclass, field
from typing import Optional
from urllib.request import urlopen
from urllib.parse import urlparse

_CHUNK = 1024 * 1024
_SHA256_PATTERN = re.compile(r'^[0-9a-f]{64}$')


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


@dataclass(frozen=True)
class MediaDefinition:
    """A parsed and validated media definition (item form only).
    
    This represents the item form from docs/media-spec.md: a single
    media item with optional url, name, file, and required sha256.
    Archive form is not yet implemented (milestone 2).
    """
    name: str
    file: str
    sha256: str
    url: Optional[str] = None
    local_path: Optional[str] = None
    file_extension: Optional[str] = None


def _validate_sha256(hash_value: str) -> None:
    """Raise ValueError if hash_value is not a valid hex SHA-256."""
    if not isinstance(hash_value, str):
        raise ValueError(f"sha256 must be a string, got {type(hash_value).__name__}")
    if not _SHA256_PATTERN.match(hash_value):
        raise ValueError(f"sha256 must be a 64-character hex string, got: {hash_value}")


def _derive_file_from_url(url: str) -> str:
    """Extract the filename component from a URL."""
    parsed = urlparse(url)
    path = parsed.path
    filename = os.path.basename(path)
    if not filename:
        raise ValueError(f"URL has no filename component: {url}")
    return filename


def _derive_name_from_file(file: str) -> str:
    """Extract the name from a file by removing its extension."""
    # Split on the last dot; if no dot, the whole thing is the name
    name, ext = os.path.splitext(file)
    return name if name else file


def parse_definition(data: dict) -> MediaDefinition:
    """Parse and validate a media definition dictionary (item form).
    
    Args:
        data: A dictionary containing the media definition fields.
        
    Returns:
        A MediaDefinition with all fields resolved.
        
    Raises:
        ValueError: If required fields are missing or invalid.
        KeyError: If required fields are missing.
    """
    # Validate required sha256
    if "sha256" not in data:
        raise KeyError("sha256 is required")
    sha256 = data["sha256"]
    _validate_sha256(sha256)
    
    # Determine file: explicit, from local-path, or from url
    file = None
    if "file" in data:
        file = data["file"]
        if not isinstance(file, str) or not file:
            raise ValueError(f"file must be a non-empty string, got: {file}")
    elif "local-path" in data:
        local_path = data["local-path"]
        if not isinstance(local_path, str) or not local_path:
            raise ValueError(f"local-path must be a non-empty string, got: {local_path}")
        file = os.path.basename(local_path)
    elif "url" in data:
        url = data["url"]
        if not isinstance(url, str) or not url:
            raise ValueError(f"url must be a non-empty string, got: {url}")
        file = _derive_file_from_url(url)
    else:
        raise ValueError("One of file, local-path, or url is required")
    
    # Determine name: explicit or derived from file
    name = None
    if "name" in data:
        name = data["name"]
        if not isinstance(name, str) or not name:
            raise ValueError(f"name must be a non-empty string, got: {name}")
    else:
        name = _derive_name_from_file(file)
    
    # Validate optional fields
    url = data.get("url")
    if url is not None and (not isinstance(url, str) or not url):
        raise ValueError(f"url must be a non-empty string or null, got: {url}")
    
    local_path = data.get("local-path")
    if local_path is not None and (not isinstance(local_path, str) or not local_path):
        raise ValueError(f"local-path must be a non-empty string or null, got: {local_path}")
    
    file_extension = data.get("file-extension")
    if file_extension is not None and (not isinstance(file_extension, str) or not file_extension):
        raise ValueError(f"file-extension must be a non-empty string or null, got: {file_extension}")
    
    # Reject archive form (items key) - not implemented in spike #2
    if "items" in data:
        raise ValueError("Archive form (items key) is not yet implemented")
    if "archive" in data:
        raise ValueError("Archive form (archive key) is not yet implemented")
    
    return MediaDefinition(
        name=name,
        file=file,
        sha256=sha256,
        url=url,
        local_path=local_path,
        file_extension=file_extension,
    )


def load_definition(path: str) -> MediaDefinition:
    """Load and parse a media definition from a JSON file.
    
    Args:
        path: Path to the JSON file containing the media definition.
        
    Returns:
        A MediaDefinition parsed from the file.
        
    Raises:
        FileNotFoundError: If the file does not exist.
        json.JSONDecodeError: If the file is not valid JSON.
        ValueError: If the definition is invalid.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Media definition not found: {path}")
    
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    
    if not isinstance(data, dict):
        raise ValueError(f"Media definition must be a JSON object, got {type(data).__name__}")
    
    return parse_definition(data)


def resolve_media(name: str, home=None) -> MediaDefinition:
    """Resolve a media definition by name from the media/ directory.
    
    Scans all JSON files in the media directory and returns the definition
    whose parsed name matches the requested name.
    
    Args:
        name: The media item name to resolve.
        home: Optional explicit home path; uses process-global home if None.
        
    Returns:
        A MediaDefinition with the matching name.
        
    Raises:
        FileNotFoundError: If the media directory does not exist or contains
            no definition with the given name.
        ValueError: If multiple definitions have the same name (duplicate error).
    """
    from reliquary.home import media_dir
    
    media_path = media_dir(home)
    
    if not os.path.exists(media_path):
        raise FileNotFoundError(f"Media directory does not exist: {media_path}")
    
    if not os.path.isdir(media_path):
        raise ValueError(f"Media path is not a directory: {media_path}")
    
    matches = []
    
    for filename in os.listdir(media_path):
        if not filename.endswith(".json"):
            continue
        
        filepath = os.path.join(media_path, filename)
        try:
            definition = load_definition(filepath)
            if definition.name == name:
                matches.append((filepath, definition))
        except (json.JSONDecodeError, ValueError, KeyError):
            # Skip invalid files; they'll be caught by explicit operations
            continue
    
    if not matches:
        raise FileNotFoundError(f"No media definition found with name: {name}")
    
    if len(matches) > 1:
        paths = ", ".join(m[0] for m in matches)
        raise ValueError(f"Multiple media definitions have the same name '{name}': {paths}")
    
    return matches[0][1]
