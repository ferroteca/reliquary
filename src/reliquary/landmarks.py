# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Landmarks: the ``.rlql`` authored kind and the pixel-equal matcher.

A landmark is **one declaration and N renderings** (F65; the settled
design is docs/spec/landmarks.md). The declaration owns the geometry
-- pinned screen dimensions, a region list, a named spot set -- and
the renderings are plain PNGs beside it, attached by stem-and-number
adjacency (``<name>.1.png``, ``<name>.2.png``), so refreshing an
asset is file *creation* and never file rewriting. A screen whose
layout changed is a different landmark; a variant is the same screen
painted differently.

Matching is **whole-screen exact, with regions as modifiers**. Every
pixel of a capture is in exactly one regime: an ``ignore`` region
excludes it -- ignore wins where regions overlap -- a ``fuzzy``
region judges its own pixels against its own declared percentage, and
the residual screen requires 100%. A variant matches when its
residual is clean and every fuzzy region clears its own bar; the
landmark matches when any variant does. That is the safe failure
asymmetry (G4): anti-aliasing and palette drift fail toward a visible
timeout, never toward the wrong screen.

**Watch-only** (F65). ``spots`` are parsed and validated because they
are part of the settled schema and a recorder writes them, but
nothing here reads one: the pointer verbs that would, and the
cursor-parking contract that makes a capture reproducible under them,
arrive with the pointer piece (planning/proposed/design/pointer-input.md).
Before any pointer verb exists nothing moves the guest's cursor, so a
capture and a keyboard-only run agree by construction.
"""

import functools
import os
import re
import types
from dataclasses import dataclass
from typing import Optional, Tuple

from PIL import Image, ImageChops, ImageDraw

from . import assets, fonts, json5reader, resolve
from .errors import InternalError, PreflightError, StaticError

#: The region kinds, and what each does to the pixels under it.
REGION_KINDS = ("fuzzy", "ignore")

#: The fields a declaration may carry. Unknown keys are refused, as
#: they are in a blueprint: a mistyped ``similarty`` that softened
#: nothing would be a landmark that silently demands more than its
#: author asked for.
_FIELDS = ("screen", "regions", "spots")
_REGION_FIELDS = ("kind", "x", "y", "width", "height", "similarity")
_SCREEN_FIELDS = ("width", "height")
_SPOT_FIELDS = ("x", "y")

#: A percent literal with its unit spelled, as durations spell theirs
#: (G6). The range it is then held to is the **exclusive** (0%, 100%):
#: ``0%`` is ``ignore`` in a second spelling and ``100%`` is the
#: region's absence, and the language refuses a second way to say
#: either.
_PERCENT = re.compile(r"(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)%$")

#: The capture pixel formats a plane may state, and what normalizing a
#: reference rendering through one costs. The **hook** is the point,
#: not today's table: a plane states its capture format as a
#: capability and the reference side is normalized through it before
#: the comparison, so an asset captured on one plane still matches on
#: another (docs/spec/landmarks.md, "The capture format"). On the VNC
#: plane the stated format is the forced 32bpp true colour, so the
#: normalization is the identity and nothing delivered moves.
_NORMALIZERS = {
    "rgb": lambda image: image,
}


class LandmarkError(StaticError):
    """A landmark declaration diagnostic that can say *where*.

    The legality tier, like every other authored-document diagnostic:
    decided from the declaration's own text, so it is a STATIC ERROR
    and exits ``2``, rendered by the same skeleton
    :class:`document.BlueprintError`, :class:`fonts.FontError` and
    :class:`script_nodes.ScriptParseError` already use (D70).
    """

    def __init__(self, message, *, rule_id=None, path=None, position=None):
        super().__init__(message, rule_id=rule_id)
        self.message = message
        self.path = path
        self.line, self.column = position if position else (None, None)

    def __str__(self):
        cited = f" ({self.rule_id})" if self.rule_id else ""
        if self.line is None:
            return f"{self.path or '<landmark>'}: error: {self.message}"\
                   f"{cited}"
        return (f"{self.path}:{self.line}:{self.column}: "
                f"error: {self.message}{cited}")


@dataclass(frozen=True)
class Region:
    """One declared rectangle, and what it does to its own pixels."""

    kind: str                     # "fuzzy" or "ignore"
    x: int
    y: int
    width: int
    height: int
    #: The declared percentage as a fraction, ``None`` on ``ignore``.
    similarity: Optional[float] = None
    #: The percentage as authored, for a diagnostic that quotes it.
    spelling: Optional[str] = None

    @property
    def box(self):
        """The Pillow box of this rectangle."""
        return (self.x, self.y, self.x + self.width, self.y + self.height)

    def describe(self):
        """Name this region the way a failure report names it."""
        where = f"{self.width}x{self.height}+{self.x}+{self.y}"
        if self.kind == "fuzzy":
            return f"fuzzy {where} at {self.spelling}"
        return f"ignore {where}"


@dataclass(frozen=True)
class Spot:
    """One named point on the landmark, in screen coordinates.

    Declared, validated and carried; **unread until pointer verbs
    exist** (F65's cut). A landmark with no spots is watchable and not
    clickable, which is the static refusal the pointer piece owes.
    """

    x: int
    y: int


@dataclass(frozen=True)
class LandmarkDeclaration:
    """One parsed ``.rlql`` document and the renderings beside it."""

    name: str
    width: int
    height: int
    regions: Tuple[Region, ...]
    spots: types.MappingProxyType
    path: str
    #: Variant renderings, ordered numerically by their stem number.
    variants: Tuple[str, ...]

    @property
    def size(self):
        return (self.width, self.height)


# -- the declaration ---------------------------------------------


def _error(doc, path, key, message, rule_id):
    position = json5reader.position_of(doc, key) or json5reader.position(doc)
    return LandmarkError(message, rule_id=rule_id, path=path,
                         position=position)


def _object(value, doc, path, key, what, rule_id):
    if not isinstance(value, dict):
        raise _error(doc, path, key,
                     f"{what} must be a JSON5 object, got {value!r}",
                     rule_id)
    return value


def _fields(value, allowed, doc, path, what):
    for key in value:
        if key not in allowed:
            raise _error(
                value, path, key,
                f"unknown {what} field {key!r} (known: "
                f"{', '.join(allowed)})", "landmark.unknown-field")


def _dimension(value, doc, path, key, what, rule_id):
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise _error(doc, path, key,
                     f"{what} must be a positive whole number, "
                     f"got {value!r}", rule_id)
    return value


def _coordinate(value, doc, path, key, what, rule_id):
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise _error(doc, path, key,
                     f"{what} must be a whole number of pixels from the "
                     f"screen's top-left, got {value!r}", rule_id)
    return value


def _percent(value, doc, path, key, rule_id):
    """A percent literal with its unit spelled, inside (0%, 100%)."""
    if not isinstance(value, str) or not _PERCENT.fullmatch(value):
        raise _error(
            doc, path, key,
            f"similarity is a percent literal with its unit spelled, "
            f"such as \"97%\"; got {value!r}", rule_id)
    fraction = float(value[:-1]) / 100.0
    if not 0.0 < fraction < 1.0:
        raise _error(
            doc, path, key,
            f"similarity {value} is outside the exclusive range "
            "(0%, 100%): 0% is an ignore region in a second spelling "
            "and 100% is the region's absence", rule_id)
    return fraction


def _region(entry, index, regions, path, width, height):
    _object(entry, regions, path, index, "a region", "landmark.bad-region")
    _fields(entry, _REGION_FIELDS, regions, path, "region")
    kind = entry.get("kind")
    if kind not in REGION_KINDS:
        raise _error(entry, path, "kind",
                     f"a region's kind is {' or '.join(REGION_KINDS)}, "
                     f"got {kind!r}", "landmark.bad-region-kind")
    x = _coordinate(entry.get("x"), entry, path, "x", "a region's x",
                    "landmark.bad-region")
    y = _coordinate(entry.get("y"), entry, path, "y", "a region's y",
                    "landmark.bad-region")
    region_width = _dimension(entry.get("width"), entry, path, "width",
                              "a region's width", "landmark.bad-region")
    region_height = _dimension(entry.get("height"), entry, path, "height",
                               "a region's height", "landmark.bad-region")
    if x + region_width > width or y + region_height > height:
        raise _error(
            entry, path, "x",
            f"the region {region_width}x{region_height}+{x}+{y} falls "
            f"outside the pinned {width}x{height} screen",
            "landmark.out-of-bounds")
    spelling = entry.get("similarity")
    if kind == "ignore":
        if spelling is not None:
            raise _error(
                entry, path, "similarity",
                "similarity belongs to a fuzzy region: an ignore region "
                "excludes its pixels outright and judges none of them",
                "landmark.similarity-on-ignore")
        similarity = None
    else:
        if spelling is None:
            raise _error(
                entry, path, "kind",
                "a fuzzy region states its own similarity, spelled as a "
                "percent literal such as \"97%\"; there is no default",
                "landmark.similarity-required")
        similarity = _percent(spelling, entry, path, "similarity",
                              "landmark.bad-similarity")
    return Region(kind, x, y, region_width, region_height, similarity,
                  spelling)


def _spots(value, doc, path, width, height):
    spots = {}
    if value is None:
        return types.MappingProxyType(spots)
    _object(value, doc, path, "spots", "spots", "landmark.bad-spot")
    for name, entry in value.items():
        _object(entry, value, path, name, f"the spot {name!r}",
                "landmark.bad-spot")
        _fields(entry, _SPOT_FIELDS, value, path, "spot")
        x = _coordinate(entry.get("x"), entry, path, "x",
                        f"the spot {name!r}'s x", "landmark.bad-spot")
        y = _coordinate(entry.get("y"), entry, path, "y",
                        f"the spot {name!r}'s y", "landmark.bad-spot")
        if x >= width or y >= height:
            raise _error(
                entry, path, "x",
                f"the spot {name!r} at ({x}, {y}) falls outside the "
                f"pinned {width}x{height} screen",
                "landmark.out-of-bounds")
        spots[name] = Spot(x, y)
    return types.MappingProxyType(spots)


_VARIANT = re.compile(r"(.+)\.([0-9]+)\.png$", re.IGNORECASE)


def _variants(path, name, width, height):
    """The renderings beside a declaration, ordered numerically.

    **Numbered from 1, with no contiguity demanded** — deleting a
    stale rendering stays a file deletion, which is the recorder's
    file-creation property read in the other direction. Each is
    checked against the pinned dimensions here, before a machine
    starts (G3): a rendering off the declared geometry can never
    match, and saying so at the declaration is the difference
    between a named refusal and a silent timeout.
    """
    directory = os.path.dirname(path) or "."
    found = []
    try:
        entries = sorted(os.listdir(directory))
    except OSError:
        entries = []
    for filename in entries:
        matched = _VARIANT.fullmatch(filename)
        if matched is None or matched.group(1) != name:
            continue
        number = int(matched.group(2))
        if number < 1:
            raise LandmarkError(
                f"variant renderings are numbered from 1: {filename!r}",
                rule_id="landmark.bad-variant-number", path=path)
        found.append((number, os.path.join(directory, filename)))
    if not found:
        raise LandmarkError(
            f"no variant rendering {name}.1.png beside declaration "
            f"{os.path.basename(path)!r}",
            rule_id="landmark.no-variant", path=path)
    found.sort()
    for _number, variant in found:
        try:
            with Image.open(variant) as image:
                size = image.size
        except OSError as error:
            raise LandmarkError(
                f"variant {os.path.basename(variant)!r} cannot be read "
                f"as an image: {error}",
                rule_id="landmark.unreadable-variant", path=path) from error
        if size != (width, height):
            raise LandmarkError(
                f"variant {os.path.basename(variant)!r} is "
                f"{size[0]}x{size[1]}, off the pinned {width}x{height} "
                "screen the declaration shares with every variant",
                rule_id="landmark.variant-dimensions", path=path)
    return tuple(variant for _number, variant in found)


def load_landmark_declaration(path):
    """Parse and validate one ``.rlql`` file, failing closed by name.

    Every refusal here is decided from the declaration and the files
    beside it, so all of them land before a machine starts (G3).
    """
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    try:
        doc = json5reader.loads(text, positions=True)
    except StaticError as error:
        raise LandmarkError(str(error),
                            rule_id=getattr(error, "rule_id", None),
                            path=path) from error
    if not isinstance(doc, dict):
        raise LandmarkError("a landmark declaration must be a JSON5 object",
                            rule_id="landmark.not-an-object", path=path)
    _fields(doc, _FIELDS, doc, path, "declaration")

    screen = doc.get("screen")
    _object(screen, doc, path, "screen", "screen", "landmark.bad-screen")
    _fields(screen, _SCREEN_FIELDS, doc, path, "screen")
    width = _dimension(screen.get("width"), screen, path, "width",
                       "the screen width", "landmark.bad-screen")
    height = _dimension(screen.get("height"), screen, path, "height",
                        "the screen height", "landmark.bad-screen")

    regions = doc.get("regions")
    if regions is None:
        regions = []
    if not isinstance(regions, list):
        raise _error(doc, path, "regions",
                     f"regions is a list of rectangles, got {regions!r}",
                     "landmark.bad-region")
    parsed = tuple(_region(entry, index, regions, path, width, height)
                   for index, entry in enumerate(regions))

    name = assets.stem(path)
    return LandmarkDeclaration(
        name=name, width=width, height=height, regions=parsed,
        spots=_spots(doc.get("spots"), doc, path, width, height),
        path=path, variants=_variants(path, name, width, height))


def load_landmark_namespace(context=None):
    """``{name: LandmarkDeclaration}`` for every ``.rlql`` in the source.

    Collision-checked against the one ``@`` pool media and font names
    already occupy — the pool gaining its third kind (F65) — so a
    duplicate visible to one script is an error naming both files.
    """
    source = assets.source_for(context)
    index = assets.index_by_name(
        source.candidate_files("landmark"), lambda _path: None,
        kind="landmark")
    declarations = {name: load_landmark_declaration(path)
                    for name, path in index.items()}
    claims = {name: declaration.path
              for name, declaration in declarations.items()}
    media = resolve.load_namespace(context).media
    assets.guard_pool(
        "landmark", claims, "media",
        {name: f"a media spec named {name!r}" for name in media})
    assets.guard_pool(
        "landmark", claims, "font",
        {name: declaration.path for name, declaration
         in fonts.load_font_namespace(context).items()})
    return types.MappingProxyType(declarations)


def resolve_landmark(name, namespace):
    """Return the declaration named ``name``, or fail closed."""
    try:
        return namespace[name]
    except KeyError:
        raise PreflightError(f"no landmark named {name!r}",
                             rule_id="landmark.unknown") from None


# -- the matcher -------------------------------------------------


@dataclass(frozen=True)
class RegionMiss:
    """One judged area a variant failed on, and by how much.

    ``region`` is ``None`` for the residual screen — everything no
    declared region covers, which requires 100% — so a report names
    the geography of a miss rather than restating that one happened.
    """

    region: Optional[Region]
    achieved: float
    required: float

    def describe(self):
        where = ("the rest of the screen" if self.region is None
                 else self.region.describe())
        return (f"{where}: {self.achieved * 100:.2f}% of "
                f"{self.required * 100:g}% required")


@dataclass(frozen=True)
class VariantMatch:
    """How one rendering scored against one capture."""

    path: str
    matched: bool
    failing: Tuple[RegionMiss, ...] = ()
    #: Judged pixels that differed, over every regime — what ranks
    #: the nearest miss.
    changed: int = 0

    @property
    def filename(self):
        return os.path.basename(self.path)


@dataclass(frozen=True)
class LandmarkMatch:
    """The landmark's verdict, and the evidence a failure quotes."""

    name: str
    matched: bool
    #: The variant that matched, or the nearest miss when none did.
    nearest: Optional[VariantMatch] = None
    #: Set when the capture is not the pinned size, in which case no
    #: variant was compared at all.
    size_mismatch: Optional[Tuple[int, int]] = None

    def describe(self):
        """The nearest-miss report, naming variant and geography."""
        if self.matched:
            return (f"@{self.name} matched "
                    f"{self.nearest.filename if self.nearest else '?'}")
        if self.size_mismatch is not None:
            return (f"@{self.name} pins a "
                    f"{self.size_mismatch[0]}x{self.size_mismatch[1]} "
                    "screen and the capture is a different size")
        if self.nearest is None:
            return f"@{self.name} matched no variant"
        misses = "; ".join(miss.describe() for miss in self.nearest.failing)
        return (f"@{self.name} came closest on {self.nearest.filename} "
                f"({misses})")


def normalize(image, capture_format):
    """Put a reference rendering through a plane's capture format.

    The seam point ``hyperv-screen.md`` settled and this piece lands
    at zero cost: a plane states the pixel format its capture arrives
    in, and the *reference* side is normalized through it before the
    pixel-equal comparison, so a deterministic round trip keeps "97
    of every 100 pixels identical" meaning the same thing on every
    plane. ``None`` and the VNC plane's ``rgb`` are both the
    identity.
    """
    if capture_format is None:
        return image
    try:
        return _NORMALIZERS[capture_format](image)
    except KeyError:
        raise InternalError(
            f"no landmark normalization for capture format "
            f"{capture_format!r}") from None


def _masks(declaration):
    """The three regimes as Pillow masks over one screen.

    ``ignore`` wins where regions overlap, so it is drawn first and
    subtracted from everything else; each fuzzy region judges only
    its own surviving pixels; the residual is what no region claims.

    **Built once per geometry, not once per sample.** A wait reads
    every ~0.2s and the regimes depend on the declaration alone, so
    rebuilding a screenful of masks each time would be the dominant
    cost of watching a landmark. Keyed by what actually decides them
    — the file, its pinned size, and its regions — so two
    declarations never share a cache entry and an edited one gets
    fresh masks on its next parse.
    """
    return _regime_masks(declaration.path, declaration.size,
                         declaration.regions)


@functools.lru_cache(maxsize=16)
def _regime_masks(path, size, regions):
    """:func:`_masks`, memoized on what actually decides the answer."""
    del path                          # a cache key, not an argument
    ignored = Image.new("L", size, 0)
    drawn = ImageDraw.Draw(ignored)
    for region in regions:
        if region.kind == "ignore":
            drawn.rectangle(_inclusive(region.box), fill=255)
    keep = ImageChops.invert(ignored)
    fuzzy = []
    claimed = Image.new("L", size, 0)
    drawn = ImageDraw.Draw(claimed)
    for region in regions:
        if region.kind != "fuzzy":
            continue
        own = Image.new("L", size, 0)
        ImageDraw.Draw(own).rectangle(_inclusive(region.box), fill=255)
        drawn.rectangle(_inclusive(region.box), fill=255)
        fuzzy.append((region, ImageChops.multiply(own, keep)))
    residual = ImageChops.multiply(ImageChops.invert(claimed), keep)
    return tuple(fuzzy), residual


def _inclusive(box):
    """Pillow's ``rectangle`` draws its bottom-right corner too."""
    left, top, right, bottom = box
    return (left, top, right - 1, bottom - 1)


def _count(mask):
    return mask.histogram()[255]


def _changed_mask(reference, capture):
    """255 wherever the two images differ in any channel."""
    difference = ImageChops.difference(reference, capture)
    bands = difference.split()
    combined = bands[0]
    for band in bands[1:]:
        combined = ImageChops.lighter(combined, band)
    return combined.point(lambda value: 255 if value else 0)


@functools.lru_cache(maxsize=32)
def _decoded(path, stamp, capture_format):
    """One rendering, decoded and normalized, kept across samples.

    A wait decodes every variant at every sample without this, which
    on a 640x480 PNG is most of what watching a landmark costs.
    ``stamp`` is the file's modification time and size and is never
    read here — it is *part of the key*, so an author who re-exports
    a rendering is never matched against the pixels it used to have.
    """
    del stamp                         # a cache key, not an argument
    with Image.open(path) as opened:
        return normalize(opened.convert("RGB"), capture_format)


def _file_stamp(path):
    """What makes a decoded rendering stale: when it changed, and size."""
    try:
        stat = os.stat(path)
    except OSError:
        return None
    return (stat.st_mtime_ns, stat.st_size)


def _judge(capture, variant, fuzzy, residual, capture_format):
    """Score one rendering against one capture, per region."""
    reference = _decoded(variant, _file_stamp(variant), capture_format)
    changed = _changed_mask(reference, capture)
    failing = []
    total_changed = 0
    missed = _count(ImageChops.multiply(changed, residual))
    judged = _count(residual)
    total_changed += missed
    if missed:
        achieved = (judged - missed) / judged if judged else 0.0
        failing.append(RegionMiss(None, achieved, 1.0))
    for region, mask in fuzzy:
        judged = _count(mask)
        if not judged:
            continue                  # wholly covered by an ignore
        missed = _count(ImageChops.multiply(changed, mask))
        total_changed += missed
        achieved = (judged - missed) / judged
        if achieved < region.similarity:
            failing.append(RegionMiss(region, achieved, region.similarity))
    return VariantMatch(variant, not failing, tuple(failing),
                        total_changed)


def match(declaration, capture, capture_format=None):
    """Judge one capture against a landmark, variant by variant.

    Returns a :class:`LandmarkMatch`: matched as soon as any variant
    is clean, and otherwise carrying the **nearest miss** — the
    variant with the fewest failing pixels, with its failing regions
    and the percentage each achieved. Per-region and independently,
    never one pooled score: a small failing region drowns in a large
    matching screen's average, and the report loses its geography.
    """
    capture = capture.convert("RGB")
    if capture.size != declaration.size:
        return LandmarkMatch(declaration.name, False,
                             size_mismatch=declaration.size)
    fuzzy, residual = _masks(declaration)
    nearest = None
    for variant in declaration.variants:
        scored = _judge(capture, variant, fuzzy, residual,
                        capture_format)
        if scored.matched:
            return LandmarkMatch(declaration.name, True, scored)
        if nearest is None or scored.changed < nearest.changed:
            nearest = scored
    return LandmarkMatch(declaration.name, False, nearest)
