# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for the media acquisition convenience surface (media.py).

Parsing, resolution, and fetch-plan execution are covered by
test_document.py / test_resolve.py / test_acquire.py; this module
covers the name-level module surface (fetch/list/clean/delete).
"""

import hashlib
import json
import os

import pytest

from reliquary import authoring, media
from reliquary.document import load_document
from reliquary.errors import PreflightError
from reliquary.home import Context, blueprints_dir, media_dir


@pytest.fixture
def context(tmp_path):
    """A home with its own cache root."""
    home = str(tmp_path)
    return Context(home_dir=home, cache_dir=os.path.join(home, "cache"))


def _declare(context, media_entries):
    bpdir = os.path.join(context.home_dir, "blueprints")
    os.makedirs(bpdir, exist_ok=True)
    with open(os.path.join(bpdir, "lib.rlqb"), "w", encoding="utf-8") as h:
        json.dump(list(media_entries), h)
    return context


def _cache(context, filenames):
    cache = media_dir(context)
    os.makedirs(cache, exist_ok=True)
    for filename in filenames:
        with open(os.path.join(cache, filename), "wb") as handle:
            handle.write(b"x")
    return cache


# The name-level verbs.

def test_fetch_local_use_media_attaches_in_place(context):
    iso = os.path.join(context.home_dir, "win.iso")
    with open(iso, "wb") as handle:
        handle.write(b"ISO")
    _declare(context, [{"name": "win", "location": {"local": iso}}])
    assert media.fetch_media("win", context=context) == iso


def test_new_media_fetch_returns_none(context):
    _declare(context, [{"name": "blank", "materialize": "new",
                        "size": "1M"}])
    assert media.fetch_media("blank", context=context) is None


def test_list_media_names_the_catalog(context):
    _declare(context, [
        {"name": "blank", "materialize": "new", "size": "1M"},
        {"name": "win", "location": {"local": "/x.iso"}}])
    assert media.list_media(context=context) == ["blank", "win"]


def test_clean_media_reclaims_the_one_cache(context):
    cache = _cache(context, ("junk.iso", "husk.zip"))
    assert media.clean_media(context=context) == ["husk", "junk"]
    assert os.listdir(cache) == []


def test_clean_media_targets_just_the_named_payload(context):
    """Naming one leaves the rest of the cache alone."""
    cache = _cache(context, ("win.iso", "husk.zip"))
    assert media.clean_media("win", context=context) == ["win"]
    assert not os.path.exists(os.path.join(cache, "win.iso"))
    assert os.path.exists(os.path.join(cache, "husk.zip"))


# The attachment closure: what a scope still needs cached.

_CONTAINER_AND_CHILD = [
    {"type": "media", "name": "husk",
     "location": "https://x.test/husk.zip", "sha256": "a" * 64,
     "children": [{"path": "payload.iso", "name": "payload"}]},
]


def test_a_container_goes_once_its_child_is_cached(context):
    """The extracted payload stays; the husk it came out of goes."""
    _declare(context, _CONTAINER_AND_CHILD)
    cache = _cache(context, ("husk.zip", "payload.iso"))
    assert media.prune_media(context=context) == ["husk"]
    assert not os.path.exists(os.path.join(cache, "husk.zip"))
    assert os.path.exists(os.path.join(cache, "payload.iso"))


def test_a_container_stays_while_its_child_is_not_cached(context):
    """It is still the only way to produce the child."""
    _declare(context, _CONTAINER_AND_CHILD)
    cache = _cache(context, ("husk.zip",))
    assert media.prune_media(context=context) == []
    assert os.path.exists(os.path.join(cache, "husk.zip"))


def test_dry_run_reports_without_removing(context):
    _declare(context, _CONTAINER_AND_CHILD)
    cache = _cache(context, ("husk.zip", "payload.iso"))
    assert media.prune_media(context=context, dry_run=True) == ["husk"]
    assert os.path.exists(os.path.join(cache, "husk.zip"))


def test_prune_keeps_a_cached_media_the_catalog_declares(context):
    """Nothing derives from it, so it stays in the closure."""
    _declare(context, [{"type": "media", "name": "payload",
                        "location": "p.iso"}])
    cache = _cache(context, ("payload.iso",))
    assert media.prune_media(context=context) == []
    assert os.path.exists(os.path.join(cache, "payload.iso"))


# `add-media` authors a declaration; it never touches the cache.

def _payload(context, body=b"ISO"):
    path = os.path.join(context.home_dir, "win98.iso")
    with open(path, "wb") as handle:
        handle.write(body)
    return path


def test_it_writes_a_media_spec_pinning_the_computed_hash(context):
    payload = _payload(context)
    expected = hashlib.sha256(b"ISO").hexdigest()

    written = authoring.add_media("win98-cd", payload, context=context)

    assert written.endswith("win98-cd.rlqb")
    declared = load_document(written).media["win98-cd"]
    assert declared.sha256 == expected
    assert len(declared.location) == 1
    assert declared.location[0].kind == "local"


def test_the_file_stays_put_and_the_cache_is_untouched(context):
    payload = _payload(context)

    authoring.add_media("win98-cd", payload, context=context)

    assert os.path.exists(payload)
    assert not os.path.isdir(media_dir(context))


def test_the_declaration_resolves_and_fetches_in_place(context):
    """The whole point: the media now works, unpinned from a cache."""
    payload = _payload(context)
    authoring.add_media("win98-cd", payload, context=context)

    fetched = media.fetch_media("win98-cd", context=context)
    # Forward slashes in the spec, so compare identity, not spelling.
    assert os.path.samefile(fetched, payload)


def test_an_existing_blueprint_is_never_rewritten(context):
    payload = _payload(context)
    authoring.add_media("win98-cd", payload, context=context)
    with pytest.raises(PreflightError):
        authoring.add_media("win98-cd", payload, context=context)


def test_a_missing_file_fails_before_writing_anything(context):
    with pytest.raises(PreflightError):
        authoring.add_media("win98-cd",
                            os.path.join(context.home_dir, "nope"),
                            context=context)
    assert not os.path.exists(
        os.path.join(blueprints_dir(context), "win98-cd.rlqb"))
