# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: BSD-3-Clause
"""Media definitions and hash-verified acquisition of OS media."""

import hashlib
import os
import re
import shutil
import sys
import zipfile
from dataclasses import dataclass
from typing import Optional, Tuple
from urllib.request import urlopen
from urllib.parse import urlparse

from . import jsonc
from .home import downloads_cache_dir, media_cache_dir, media_dir

_CHUNK = 1024 * 1024
_SHA256_PATTERN = re.compile(r'^[0-9a-f]{64}$')


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
class MediaItem:
    """One named, hash-verified payload file machines can mount."""
    name: str
    file: str
    sha256: str
    path: Optional[str] = None
    file_extension: Optional[str] = None
    local_path: Optional[str] = None


@dataclass(frozen=True)
class MediaDefinition:
    """A parsed and validated media definition (planning/design/media-spec.md).

    The item form downloads its single payload directly and carries
    no archive fields; the archive form names a source archive whose
    entries its items are extracted from. Mirror URL lists and
    several definitions sharing one archive are milestone 2.

    ``description``, ``notes``, and ``redistributable_under`` are the
    optional definition-level annotations (valid in either form):
    a one-line description read into listings and ``search``,
    free-form provenance/licensing prose reliquary never interprets,
    and the explicit redistribution-licensing assertion naming the
    license (the codex's URL licensing rule — media-spec.md).
    """
    items: Tuple[MediaItem, ...]
    url: Optional[str] = None
    archive: Optional[str] = None
    archive_sha256: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    redistributable_under: Optional[str] = None


@dataclass(frozen=True)
class ResolvedMedia:
    """A media item resolved by name, with its owning definition."""
    definition: MediaDefinition
    item: MediaItem


def _validate_sha256(value):
    """Raise ValueError unless value is a hex SHA-256 string."""
    if not isinstance(value, str):
        raise ValueError(
            f"sha256 must be a string, got {type(value).__name__}")
    if not _SHA256_PATTERN.match(value):
        raise ValueError(
            f"sha256 must be a 64-character hex string, got: {value}")


def _optional_string(data, key):
    """Return data[key] as a non-empty string, or None when absent."""
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError(
            f"{key} must be a non-empty string, got: {value!r}")
    return value


def _parse_url(data):
    """Return the definition's single url, or None when absent."""
    value = data.get("url")
    if isinstance(value, list):
        raise ValueError("mirror url lists are not yet implemented")
    return _optional_string(data, "url")


def _derive_file_from_url(url):
    """Extract the file-name component from a URL."""
    filename = os.path.basename(urlparse(url).path)
    if not filename:
        raise ValueError(f"URL has no filename component: {url}")
    return filename


def _derive_name_from_file(file):
    """Default an item name: its file name with the extension dropped."""
    name, _ = os.path.splitext(file)
    return name if name else file


def _parse_item(data, url=None, archived=False):
    """Parse one item — a whole item form, or one `items` entry."""
    if not isinstance(data, dict):
        raise ValueError(
            f"items entries must be objects, got {type(data).__name__}")
    if "sha256" not in data:
        raise KeyError("sha256 is required")
    _validate_sha256(data["sha256"])
    local_path = _optional_string(data, "local-path")
    file = _optional_string(data, "file")
    if file is None:
        if local_path is not None:
            file = os.path.basename(local_path)
        elif url is not None:
            file = _derive_file_from_url(url)
        elif archived:
            raise ValueError("file is required in items entries")
        else:
            raise ValueError("One of file, local-path, or url is required")
    name = _optional_string(data, "name")
    if name is None:
        name = _derive_name_from_file(file)
    path = _optional_string(data, "path")
    if path is not None and not archived:
        raise ValueError("path is only valid inside archive items")
    if archived and path is None:
        path = file
    return MediaItem(
        name=name,
        file=file,
        sha256=data["sha256"],
        path=path,
        file_extension=_optional_string(data, "file-extension"),
        local_path=local_path,
    )


def _definition_annotations(data):
    """Return the optional definition-level annotation fields.

    ``description`` / ``notes`` / ``redistributable-under`` are valid
    at the top level of either definition form (media-spec.md).
    """
    return {
        "description": _optional_string(data, "description"),
        "notes": _optional_string(data, "notes"),
        "redistributable_under": _optional_string(
            data, "redistributable-under"),
    }


def parse_definition(data):
    """Parse and validate one media definition object.

    The `items` key selects the archive form; anything else is the
    item form. Raises KeyError for missing required fields and
    ValueError for invalid ones, naming the field.
    """
    if not isinstance(data, dict):
        raise ValueError(
            f"Media definition must be a JSON object, "
            f"got {type(data).__name__}")
    if "items" in data:
        return _parse_archive_definition(data)
    if "archive" in data:
        raise ValueError(
            "archive is only valid in the archive form (with items)")
    url = _parse_url(data)
    return MediaDefinition(items=(_parse_item(data, url=url),), url=url,
                           **_definition_annotations(data))


def _parse_archive_definition(data):
    """Parse the archive form: one source archive, itemized payloads."""
    if "sha256" not in data:
        raise KeyError("sha256 is required")
    _validate_sha256(data["sha256"])
    url = _parse_url(data)
    archive = _optional_string(data, "archive")
    if archive is None:
        if url is None:
            raise ValueError(
                "archive is required when the definition has no url")
        archive = _derive_file_from_url(url)
    entries = data["items"]
    if not isinstance(entries, list) or not entries:
        raise ValueError("items must be a non-empty list")
    items = tuple(_parse_item(entry, archived=True) for entry in entries)
    seen = set()
    for item in items:
        if item.name in seen:
            raise ValueError(
                f"duplicate item name in definition: {item.name}")
        seen.add(item.name)
    return MediaDefinition(items=items, url=url, archive=archive,
                           archive_sha256=data["sha256"],
                           **_definition_annotations(data))


def load_definition(path):
    """Load and parse one media definition JSON file."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Media definition not found: {path}")
    with open(path, "r", encoding="utf-8") as handle:
        data = jsonc.load(handle)
    return parse_definition(data)


def _scan_media_files(files, name):
    """Return (path, definition, item) for each file defining ``name``."""
    matches = []
    for filepath in files:
        try:
            definition = load_definition(filepath)
        except (ValueError, KeyError):
            continue
        for item in definition.items:
            if item.name == name:
                matches.append((filepath, definition, item))
    return matches


def scan_media_definitions(library, name):
    """Return (path, definition, item) for every definition of name.

    Scans every definition file directly under the library directory,
    skipping invalid files (they'll be caught by explicit operations
    on them). A missing library directory scans empty. This is the
    home-directory scan that ``seed_media`` / ``delete_media`` use;
    residency-scoped resolution goes through the asset source instead.
    """
    if os.path.exists(library) and not os.path.isdir(library):
        raise ValueError(f"Media path is not a directory: {library}")
    if not os.path.isdir(library):
        return []
    files = [
        os.path.join(library, filename)
        for filename in sorted(os.listdir(library))
        if filename.endswith(".rlqm") or filename.endswith(".json")
    ]
    return _scan_media_files(files, name)


def resolve_media(name, context=None):
    """Resolve a defined media item by name from the media library.

    Scans every definition under `media/` and returns a
    ResolvedMedia for the item whose name matches. A name the home
    does not define is seeded from the built-in library on this
    first reference (never overwriting user files). A name defined
    more than once is an error naming the definition files.
    """
    from .assets import source_for
    source = source_for(context)
    matches = _scan_media_files(source.candidate_files("media"), name)
    if not matches and source.seeds:
        from .library import seed_media
        if seed_media(name, context=context):
            source = source_for(context)
            matches = _scan_media_files(
                source.candidate_files("media"), name)
    if not matches:
        raise FileNotFoundError(
            f"No media definition found with name: {name}")
    if len(matches) > 1:
        paths = ", ".join(match[0] for match in matches)
        raise ValueError(
            f"Multiple media definitions have the same name "
            f"'{name}': {paths}")
    _, definition, item = matches[0]
    return ResolvedMedia(definition=definition, item=item)


def list_media(context=None, *, builtin=False):
    """Return sorted media item names from the catalog.

    Home ``media/`` by default. With ``builtin=True``, the package
    codex instead — never writes or seeds.
    """
    if builtin:
        from .library import list_builtin_media
        return list(list_builtin_media())
    from .assets import source_for
    names = set()
    for filepath in source_for(context).candidate_files("media"):
        try:
            definition = load_definition(filepath)
        except (ValueError, KeyError, FileNotFoundError):
            continue
        for item in definition.items:
            names.add(item.name)
    return sorted(names)


def delete_media(name, *, context=None):
    """Remove the home definition file that defines item ``name``.

    Fails closed while any machine drive references any item in
    that definition, naming the machine ids. Never deletes package
    builtins. Returns the removed path.
    """
    from .machines import list_machines

    library = media_dir(context)
    matches = scan_media_definitions(library, name)
    if not matches:
        raise FileNotFoundError(
            f"No media definition found with name: {name}\n"
            f"expected under {library}")
    if len(matches) > 1:
        paths = ", ".join(match[0] for match in matches)
        raise ValueError(
            f"Multiple media definitions have the same name "
            f"'{name}': {paths}")
    path, definition, _item = matches[0]
    item_names = {item.name for item in definition.items}

    holders = []
    for state in list_machines(context):
        drives = state.get("drives") or {}
        for drive in drives.values():
            media_name = drive.get("media")
            if media_name in item_names:
                holders.append(state["id"])
                break
    if holders:
        ids = ", ".join(holders)
        raise RuntimeError(
            f"media {name!r} is still used by "
            f"{len(holders)} machine(s):\n"
            f"  {ids}\n"
            "eject or destroy them first, then delete the media")

    os.remove(path)
    return path


_MISMATCH_POLICIES = ("fail", "prompt", "refetch")


def _approve_refetch(path, actual, expected, on_mismatch):
    """Gate discarding an existing file that fails verification.

    Returns when the mismatched file may be deleted and fetched
    again; raises RuntimeError when it must be kept — the "fail"
    policy (the programmatic default) and a declined "prompt" both
    keep it. Only called when a source exists to refetch from.
    """
    if on_mismatch == "refetch":
        print(f"existing file {path} does not match its defined "
              f"hash; deleting for refetch", file=sys.stderr)
        return
    if on_mismatch == "prompt":
        try:
            answer = input(
                f"Existing file {path} does not match its defined "
                f"hash (SHA-256 {actual}, expected {expected}). "
                f"Delete it and fetch again? [y/N] ")
        except EOFError:
            answer = ""
        if answer.strip().lower() in ("y", "yes"):
            return
    raise RuntimeError(
        f"existing file {path} has SHA-256 {actual}, expected "
        f"{expected}; delete it, or pre-approve the deletion with "
        f"on_mismatch='refetch' to fetch it again")


def _payload_path(item, context=None):
    """Return where the item's payload file lives (or will land).

    A `local-path` item lives at that path; otherwise the payload is
    cached as `<name>` plus the file's extension (or the
    `file-extension` override) under `cache/media/`.
    """
    if item.local_path:
        return item.local_path
    extension = item.file_extension
    if extension is None:
        extension = os.path.splitext(item.file)[1].lstrip(".")
    cached = item.name + ("." + extension if extension else "")
    return os.path.join(media_cache_dir(context), cached)


def fetch_media(name, context=None, on_mismatch="fail"):
    """Return the named item's verified payload path, fetching it on
    demand.

    Sources are tried cheapest first (planning/design/media-spec.md): an
    existing payload that verifies is returned untouched; otherwise a
    cached source archive that verifies is re-extracted; only then is
    the definition's url downloaded. Archives land in
    `cache/downloads/` and stay there; payloads land in
    `cache/media/`. Every file is SHA-256-verified before use.

    An existing payload or archive that fails verification is never
    silently discarded; `on_mismatch` decides its fate: "fail" (the
    default) raises an error naming the file and both hashes,
    "prompt" asks interactively before deleting and refetching, and
    "refetch" pre-approves the deletion. A mismatched or missing
    file whose definition names no source is always an error.
    """
    if on_mismatch not in _MISMATCH_POLICIES:
        raise ValueError(
            f"on_mismatch must be one of {_MISMATCH_POLICIES}, "
            f"got: {on_mismatch!r}")
    resolved = resolve_media(name, context)
    definition, item = resolved.definition, resolved.item
    destination = _payload_path(item, context)
    actual = _sha256(destination) if os.path.exists(destination) else None
    if actual == item.sha256:
        return destination
    has_source = (definition.archive is not None
                  or definition.url is not None)
    if actual is not None:
        if not has_source:
            raise RuntimeError(
                f"media {item.name} ({item.file}) at {destination} "
                f"has SHA-256 {actual}, expected {item.sha256}, and "
                f"its definition names no source to refetch it from")
        _approve_refetch(destination, actual, item.sha256, on_mismatch)
        os.remove(destination)
    if definition.archive is not None:
        archive = _ensure_archive(definition, context, on_mismatch)
        _extract_item(archive, item, destination)
        return destination
    if definition.url is not None:
        _download(definition.url, destination)
        downloaded = _sha256(destination)
        if downloaded != item.sha256:
            os.remove(destination)
            raise RuntimeError(
                f"downloaded media failed verification: "
                f"{definition.url} has SHA-256 {downloaded}, "
                f"expected {item.sha256}")
        return destination
    raise RuntimeError(
        f"media {item.name} ({item.file}) is missing at "
        f"{destination} (expected SHA-256 {item.sha256}) and its "
        f"definition names no source to fetch it from")


def _ensure_archive(definition, context, on_mismatch):
    """Return the definition's verified source archive in the cache.

    A cached archive that verifies is reused. One that fails
    verification is kept and reported unless `on_mismatch` approves
    deleting it (and a url exists) for a fresh download; a
    mismatched or missing archive without a url is always an error.
    """
    archive = os.path.join(downloads_cache_dir(context), definition.archive)
    if os.path.exists(archive):
        actual = _sha256(archive)
        if actual == definition.archive_sha256:
            return archive
        if definition.url is None:
            raise RuntimeError(
                f"source archive {definition.archive} at {archive} "
                f"has SHA-256 {actual}, expected "
                f"{definition.archive_sha256}, and its definition "
                f"names no url to refetch it from")
        _approve_refetch(archive, actual, definition.archive_sha256,
                         on_mismatch)
        os.remove(archive)
    if definition.url is None:
        raise RuntimeError(
            f"source archive {definition.archive} is missing at "
            f"{archive} (expected SHA-256 "
            f"{definition.archive_sha256}) and its definition names "
            f"no url to fetch it from")
    _download(definition.url, archive)
    actual = _sha256(archive)
    if actual != definition.archive_sha256:
        os.remove(archive)
        raise RuntimeError(
            f"downloaded archive failed verification: "
            f"{definition.url} has SHA-256 {actual}, expected "
            f"{definition.archive_sha256}")
    return archive


def _extract_item(archive, item, destination):
    """Extract and verify one item out of a cached zip archive.

    The member streams to a partial file that replaces the
    destination only after its SHA-256 verifies; the archive stays in
    the downloads cache for later re-extraction.
    """
    print(f"extracting {item.path} from {os.path.basename(archive)}",
          file=sys.stderr)
    os.makedirs(os.path.dirname(destination) or ".", exist_ok=True)
    partial = destination + ".part"
    with zipfile.ZipFile(archive) as bundle:
        with bundle.open(item.path) as source, \
                open(partial, "wb") as handle:
            shutil.copyfileobj(source, handle, _CHUNK)
    actual = _sha256(partial)
    if actual != item.sha256:
        os.remove(partial)
        raise RuntimeError(
            f"extracted media failed verification: {item.name} "
            f"({item.path} in {os.path.basename(archive)}) has "
            f"SHA-256 {actual}, expected {item.sha256}")
    os.replace(partial, destination)
    return destination


def clean_downloads(context=None):
    """Delete all files in the downloads cache."""
    cache = downloads_cache_dir(context)
    if not os.path.isdir(cache):
        return
    for entry in os.scandir(cache):
        if entry.is_file():
            os.remove(entry.path)


def clean_media(context=None):
    """Delete all files in the media cache."""
    cache = media_cache_dir(context)
    if not os.path.isdir(cache):
        return
    for entry in os.scandir(cache):
        if entry.is_file():
            os.remove(entry.path)
