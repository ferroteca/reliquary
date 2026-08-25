# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for landmarks: the .rlql declaration and the matcher (F65)."""

import json
import os
from importlib import resources

import jsonschema
import pytest
from PIL import Image

from reliquary import Context
from reliquary.errors import InternalError, PreflightError
from reliquary.landmarks import (LandmarkError, load_landmark_declaration,
                                 load_landmark_namespace, match,
                                 resolve_landmark)

_SIZE = (64, 32)


def _write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(obj, handle)


def _plain(size=_SIZE, colour=(10, 20, 30)):
    return Image.new("RGB", size, colour)


def _write_png(path, image):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    image.save(path)


def _paint(image, box, colour):
    """Return a copy of ``image`` with ``box`` filled."""
    copy = image.copy()
    copy.paste(Image.new("RGB", (box[2] - box[0], box[3] - box[1]), colour),
               box[:2])
    return copy


def _write_landmark(home, name, *, screen=None, regions=None, spots=None,
                    variants=(1,), variant_image=None, subdir=""):
    root = os.path.join(home, "landmarks", subdir)
    document = {"screen": screen or {"width": _SIZE[0],
                                     "height": _SIZE[1]}}
    if regions is not None:
        document["regions"] = regions
    if spots is not None:
        document["spots"] = spots
    declaration = os.path.join(root, f"{name}.rlql")
    _write_json(declaration, document)
    for number in variants:
        _write_png(os.path.join(root, f"{name}.{number}.png"),
                   variant_image if variant_image is not None else _plain())
    return declaration


@pytest.fixture
def home(tmp_path):
    return str(tmp_path / "home")


# -- the declaration ---------------------------------------------


def test_a_landmark_resolves_by_stem_with_its_variants(home):
    _write_landmark(home, "welcome", variants=(1, 3),
                    regions=[{"kind": "fuzzy", "x": 4, "y": 4,
                              "width": 8, "height": 8,
                              "similarity": "97%"},
                             {"kind": "ignore", "x": 0, "y": 24,
                              "width": 64, "height": 8}],
                    spots={"next": {"x": 50, "y": 28}})
    namespace = load_landmark_namespace(Context(home_dir=home))
    assert set(namespace) == {"welcome"}
    declaration = namespace["welcome"]
    assert declaration.size == _SIZE
    assert [region.kind for region in declaration.regions] == ["fuzzy",
                                                               "ignore"]
    assert declaration.regions[0].similarity == pytest.approx(0.97)
    assert declaration.spots["next"].x == 50
    # Numbered from 1 and ordered numerically, with no contiguity
    # demanded: deleting a stale rendering stays a file deletion.
    assert [os.path.basename(one) for one in declaration.variants] == [
        "welcome.1.png", "welcome.3.png"]


def test_a_bare_landmark_needs_no_regions_or_spots(home):
    _write_landmark(home, "plain")
    declaration = load_landmark_namespace(Context(home_dir=home))["plain"]
    assert declaration.regions == ()
    assert dict(declaration.spots) == {}


def test_a_landmark_with_no_variant_fails_closed(home):
    path = _write_landmark(home, "welcome", variants=())
    with pytest.raises(LandmarkError) as caught:
        load_landmark_declaration(path)
    assert caught.value.rule_id == "landmark.no-variant"
    assert "welcome.1.png" in str(caught.value)


def test_a_variant_off_the_pinned_dimensions_fails_closed(home):
    path = _write_landmark(home, "welcome",
                           variant_image=_plain(size=(64, 33)))
    with pytest.raises(LandmarkError) as caught:
        load_landmark_declaration(path)
    assert caught.value.rule_id == "landmark.variant-dimensions"
    assert "64x33" in str(caught.value)


def test_a_variant_numbered_zero_fails_closed(home):
    path = _write_landmark(home, "welcome", variants=(0, 1))
    with pytest.raises(LandmarkError) as caught:
        load_landmark_declaration(path)
    assert caught.value.rule_id == "landmark.bad-variant-number"


@pytest.mark.parametrize("region,rule", [
    ({"kind": "fuzzy", "x": 60, "y": 0, "width": 8, "height": 8,
      "similarity": "97%"}, "landmark.out-of-bounds"),
    ({"kind": "fuzzy", "x": 0, "y": 0, "width": 8, "height": 8},
     "landmark.similarity-required"),
    ({"kind": "ignore", "x": 0, "y": 0, "width": 8, "height": 8,
      "similarity": "97%"}, "landmark.similarity-on-ignore"),
    ({"kind": "fuzzy", "x": 0, "y": 0, "width": 8, "height": 8,
      "similarity": "0%"}, "landmark.bad-similarity"),
    ({"kind": "fuzzy", "x": 0, "y": 0, "width": 8, "height": 8,
      "similarity": "100%"}, "landmark.bad-similarity"),
    ({"kind": "fuzzy", "x": 0, "y": 0, "width": 8, "height": 8,
      "similarity": "97"}, "landmark.bad-similarity"),
    ({"kind": "fuzzy", "x": 0, "y": 0, "width": 8, "height": 8,
      "similarity": 97}, "landmark.bad-similarity"),
    ({"kind": "select", "x": 0, "y": 0, "width": 8, "height": 8},
     "landmark.bad-region-kind"),
    ({"kind": "ignore", "x": -1, "y": 0, "width": 8, "height": 8},
     "landmark.bad-region"),
    ({"kind": "ignore", "x": 0, "y": 0, "width": 0, "height": 8},
     "landmark.bad-region"),
    ({"kind": "ignore", "x": 0, "y": 0, "width": 8, "height": 8,
      "fuzz": 2}, "landmark.unknown-field"),
])
def test_a_bad_region_fails_closed_by_name(home, region, rule):
    path = _write_landmark(home, "welcome", regions=[region])
    with pytest.raises(LandmarkError) as caught:
        load_landmark_declaration(path)
    assert caught.value.rule_id == rule


@pytest.mark.parametrize("document,rule", [
    ({"screen": {"width": 64}}, "landmark.bad-screen"),
    ({"screen": {"width": 64, "height": 0}}, "landmark.bad-screen"),
    ({"screen": 64}, "landmark.bad-screen"),
    ({"screen": {"width": 64, "height": 32}, "regions": {}},
     "landmark.bad-region"),
    ({"screen": {"width": 64, "height": 32}, "spots": {"go": {"x": 4}}},
     "landmark.bad-spot"),
    ({"screen": {"width": 64, "height": 32},
      "spots": {"go": {"x": 64, "y": 4}}}, "landmark.out-of-bounds"),
    ({"screen": {"width": 64, "height": 32}, "clicks": {}},
     "landmark.unknown-field"),
])
def test_a_bad_declaration_fails_closed_by_name(home, document, rule):
    path = os.path.join(home, "landmarks", "welcome.rlql")
    _write_json(path, document)
    _write_png(os.path.join(home, "landmarks", "welcome.1.png"), _plain())
    with pytest.raises(LandmarkError) as caught:
        load_landmark_declaration(path)
    assert caught.value.rule_id == rule


def test_a_declaration_that_is_not_an_object_fails_closed(home):
    path = os.path.join(home, "landmarks", "welcome.rlql")
    _write_json(path, [1, 2])
    with pytest.raises(LandmarkError) as caught:
        load_landmark_declaration(path)
    assert caught.value.rule_id == "landmark.not-an-object"


def test_a_diagnostic_cites_the_line_it_came_from(home):
    path = os.path.join(home, "landmarks", "welcome.rlql")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write('{\n  "screen": { "width": 64, "height": 32 },\n'
                     '  "regions": [\n'
                     '    { "kind": "wobbly", "x": 0, "y": 0,\n'
                     '      "width": 8, "height": 8 },\n'
                     '  ],\n}\n')
    _write_png(os.path.join(home, "landmarks", "welcome.1.png"), _plain())
    with pytest.raises(LandmarkError) as caught:
        load_landmark_declaration(path)
    assert caught.value.line == 4
    assert "landmark.bad-region-kind" in str(caught.value)


# -- the one @ pool ----------------------------------------------


def test_a_landmark_colliding_with_a_media_names_both(home):
    _write_landmark(home, "boot")
    _write_json(os.path.join(home, "blueprints", "boot.rlqb"),
                [{"type": "media", "name": "boot",
                  "location": {"local": "/boot.img"}}])
    with pytest.raises(PreflightError) as caught:
        load_landmark_namespace(Context(home_dir=home))
    assert caught.value.rule_id == "name.pool-collision"
    assert "boot.rlql" in str(caught.value)
    assert "a media spec named 'boot'" in str(caught.value)


def test_a_landmark_colliding_with_a_font_names_both(home):
    _write_landmark(home, "guest")
    _write_json(os.path.join(home, "fonts", "guest.rlqf"),
                {"cell-rows": 16, "codepage": "cp437"})
    with open(os.path.join(home, "fonts", "guest.bin"), "wb") as handle:
        handle.write(bytes(4096))
    with pytest.raises(PreflightError) as caught:
        load_landmark_namespace(Context(home_dir=home))
    assert caught.value.rule_id == "name.pool-collision"
    assert "guest.rlql" in str(caught.value)
    assert "guest.rlqf" in str(caught.value)


def test_an_unknown_landmark_fails_closed(home):
    namespace = load_landmark_namespace(Context(home_dir=home))
    with pytest.raises(PreflightError) as caught:
        resolve_landmark("welcome", namespace)
    assert caught.value.rule_id == "landmark.unknown"


# -- the matcher -------------------------------------------------


def _declaration(home, **kwargs):
    path = _write_landmark(home, "welcome", **kwargs)
    return load_landmark_declaration(path)


def test_a_bare_landmark_is_a_whole_screen_exact_match(home):
    declaration = _declaration(home)
    assert match(declaration, _plain()).matched
    result = match(declaration, _paint(_plain(), (0, 0, 1, 1), (9, 9, 9)))
    assert not result.matched
    assert [miss.region for miss in result.nearest.failing] == [None]
    assert result.nearest.changed == 1


def test_the_built_in_park_zone_is_excluded_from_every_match(home):
    # F66: unconditional and unauthored -- a captured cursor sitting in
    # the bottom-right corner (the park position for this landmark's
    # own 64x32 pinned size) never breaks an otherwise-clean match.
    declaration = _declaration(home)
    parked = _paint(_plain(), (48, 24, 64, 32), (255, 255, 255))
    assert match(declaration, parked).matched


def test_a_pixel_just_outside_the_park_zone_still_fails_a_match(home):
    # The boundary is precise: one pixel to the left of the built-in
    # region is ordinary screen content and is judged like any other.
    declaration = _declaration(home)
    almost_parked = _paint(_plain(), (47, 24, 48, 32), (255, 255, 255))
    assert not match(declaration, almost_parked).matched


def test_an_ignore_region_excludes_its_pixels_outright(home):
    declaration = _declaration(
        home, regions=[{"kind": "ignore", "x": 0, "y": 24,
                        "width": 64, "height": 8}])
    changed = _paint(_plain(), (0, 24, 64, 32), (200, 0, 0))
    assert match(declaration, changed).matched


def test_a_fuzzy_region_judges_its_own_pixels_against_its_own_bar(home):
    # 16x16 = 256 pixels; 8 changed is 96.875%, under a 97% bar and
    # over a 90% one.
    regions = [{"kind": "fuzzy", "x": 0, "y": 0, "width": 16,
                "height": 16, "similarity": "97%"}]
    declaration = _declaration(home, regions=regions)
    capture = _paint(_plain(), (0, 0, 8, 1), (200, 0, 0))
    result = match(declaration, capture)
    assert not result.matched
    miss = result.nearest.failing[0]
    assert miss.region is declaration.regions[0]
    assert miss.achieved == pytest.approx(248 / 256)
    assert miss.required == pytest.approx(0.97)

    regions[0]["similarity"] = "90%"
    assert match(_declaration(home, regions=regions), capture).matched


def test_ignore_wins_where_regions_overlap(home):
    declaration = _declaration(
        home, regions=[{"kind": "fuzzy", "x": 0, "y": 0, "width": 16,
                        "height": 16, "similarity": "99%"},
                       {"kind": "ignore", "x": 0, "y": 0, "width": 16,
                        "height": 8}])
    # Every changed pixel sits in the overlap, so the fuzzy region has
    # nothing left to fail on.
    assert match(declaration,
                 _paint(_plain(), (0, 0, 16, 8), (200, 0, 0))).matched


def test_the_residual_requires_every_pixel(home):
    declaration = _declaration(
        home, regions=[{"kind": "fuzzy", "x": 0, "y": 0, "width": 16,
                        "height": 16, "similarity": "50%"}])
    result = match(declaration, _paint(_plain(), (32, 0, 33, 1), (1, 2, 3)))
    assert not result.matched
    assert result.nearest.failing[0].region is None
    assert result.nearest.failing[0].required == 1.0


def test_any_variant_decides_the_landmark(home):
    second = _paint(_plain(), (0, 0, 64, 32), (99, 99, 99))
    path = _write_landmark(home, "welcome", variants=(1,))
    _write_png(os.path.join(home, "landmarks", "welcome.2.png"), second)
    declaration = load_landmark_declaration(path)
    assert match(declaration, second).matched
    assert os.path.basename(match(declaration, second).nearest.path) == \
        "welcome.2.png"


def test_the_nearest_miss_names_the_closest_variant_and_its_geography(home):
    path = _write_landmark(home, "welcome", variants=(1,),
                           regions=[{"kind": "fuzzy", "x": 0, "y": 0,
                                     "width": 16, "height": 16,
                                     "similarity": "99%"}])
    _write_png(os.path.join(home, "landmarks", "welcome.2.png"),
               _plain(colour=(80, 80, 80)))
    declaration = load_landmark_declaration(path)
    # Close to variant 1 (four pixels out), miles from variant 2.
    capture = _paint(_plain(), (0, 0, 4, 1), (200, 0, 0))
    result = match(declaration, capture)
    assert not result.matched
    assert result.nearest.filename == "welcome.1.png"
    report = result.describe()
    assert "welcome.1.png" in report
    assert "fuzzy 16x16+0+0 at 99%" in report
    assert "98.44% of 99% required" in report


def test_a_capture_off_the_pinned_size_matches_nothing_and_says_so(home):
    declaration = _declaration(home)
    result = match(declaration, _plain(size=(80, 40)))
    assert not result.matched
    assert result.size_mismatch == _SIZE
    assert "64x32" in result.describe()


def test_the_reference_side_is_normalized_through_the_capture_format(home):
    declaration = _declaration(home)
    # The one format a plane states today is the identity, which is
    # what makes the hook cost nothing on the VNC plane.
    assert match(declaration, _plain(), capture_format="rgb").matched
    with pytest.raises(InternalError):
        match(declaration, _plain(), capture_format="rgb565")


# -- the packaged schema -----------------------------------------


def _schema():
    text = (resources.files("reliquary") / "schemas"
            / "landmark-schema-v1.json").read_text(encoding="utf-8")
    return json.loads(text)


_SCHEMA = _schema()


@pytest.mark.parametrize("document", [
    {"screen": {"width": 640, "height": 480}},
    {"screen": {"width": 640, "height": 480},
     "regions": [{"kind": "fuzzy", "x": 200, "y": 120, "width": 240,
                  "height": 32, "similarity": "97%"},
                 {"kind": "ignore", "x": 0, "y": 456, "width": 640,
                  "height": 24}],
     "spots": {"next": {"x": 520, "y": 440},
               "cancel": {"x": 420, "y": 440}}},
])
def test_the_packaged_schema_accepts_what_the_parser_accepts(document):
    jsonschema.validate(document, _SCHEMA)


@pytest.mark.parametrize("document", [
    {},
    {"screen": {"width": 640}},
    {"screen": {"width": 640, "height": 480}, "clicks": {}},
    {"screen": {"width": 640, "height": 480},
     "regions": [{"kind": "select", "x": 0, "y": 0, "width": 8,
                  "height": 8}]},
    {"screen": {"width": 640, "height": 480},
     "regions": [{"kind": "fuzzy", "x": 0, "y": 0, "width": 8,
                  "height": 8}]},
    {"screen": {"width": 640, "height": 480},
     "regions": [{"kind": "ignore", "x": 0, "y": 0, "width": 8,
                  "height": 8, "similarity": "97%"}]},
    {"screen": {"width": 640, "height": 480},
     "regions": [{"kind": "fuzzy", "x": 0, "y": 0, "width": 8,
                  "height": 8, "similarity": 97}]},
    {"screen": {"width": 640, "height": 480},
     "spots": {"next": {"x": 1}}},
])
def test_the_packaged_schema_refuses_what_the_parser_refuses(document,
                                                             home):
    """The two are kept honest against each other on shape.

    Not on everything: the schema's own description says which
    refusals it cannot make — the bounds checks, the variant
    renderings, and the exclusive similarity range all need either a
    numeric comparison or the files beside the declaration. What both
    layers *can* decide, both decide the same way, and this is that
    overlap rather than a claim of equivalence.
    """
    assert not jsonschema.Draft202012Validator(_SCHEMA).is_valid(document)
    path = os.path.join(home, "landmarks", "welcome.rlql")
    _write_json(path, document)
    _write_png(os.path.join(home, "landmarks", "welcome.1.png"),
               _plain(size=(640, 480)))
    with pytest.raises(LandmarkError):
        load_landmark_declaration(path)
