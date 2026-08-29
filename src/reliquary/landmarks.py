# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Landmarks: the ``.rlql`` authored file format, and the pixel-equal
matcher.

A landmark is one declaration plus N renderings (F65; the settled
design is in docs/spec/landmarks.md). The declaration owns the
geometry — pinned screen dimensions, a list of regions, a set of
named spots — and the renderings are plain PNG files next to it,
matched by name and number (``<name>.1.png``, ``<name>.2.png``), so
adding a new rendering is always creating a new file, never rewriting
an existing one. A screen whose layout has changed is a different
landmark; a variant is the same screen painted differently (a
different color scheme, a different loaded translation, and so on).

Matching compares the whole screen exactly, with regions acting as
modifiers. Every pixel of a capture falls into exactly one of three
categories: an ``ignore`` region excludes it entirely (and wins
wherever regions overlap), a ``fuzzy`` region judges its own pixels
against its own declared percentage, and everything left over — the
residual screen — requires a 100% pixel match. A variant matches when
its residual is clean and every fuzzy region clears its own
percentage bar; the landmark as a whole matches when any one of its
variants does. This is a deliberately asymmetric failure mode (G4):
anti-aliasing noise or palette drift causes a visible timeout, never
a false match against the wrong screen.

``spots`` are read by the `click` verb (F66), which looks one up by
name and sends a pointer event there. Every pointer verb ends by
parking the cursor at :func:`park_position`, and this module excludes
that parked-cursor area from every match unconditionally (see
:func:`_park_region`), so a capture is always free of the cursor,
just as it was before pointer verbs existed.
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

#: The size of the built-in park-zone ignore region (F66): big enough
#: to hold a rendered cursor glyph on any screen a landmark pins.
_PARK_SIZE = 16


def park_position(width, height):
    """Return the cursor's park position after a pointer verb, for a
    screen of this size.

    This is the bottom-right corner, scaled to the screen's own
    pinned dimensions rather than a fixed pixel constant. There is
    only one rule today because DOS is the only shipped platform
    (docs/spec/landmarks.md, "The cursor"), but it is resolved
    separately for each landmark since different landmarks pin
    different screen sizes. Authored content usually anchors things
    to the top-left (a title, a menu bar), so the opposite corner is
    the one least likely to overlap it.
    """
    return (max(0, width - 1), max(0, height - 1))

#: The fields a declaration may carry. Unknown keys are refused, the
#: same as in a blueprint: a typo like ``similarty`` that silently
#: does nothing would leave a landmark demanding more of a match than
#: its author actually asked for.
_FIELDS = ("screen", "regions", "spots")
_REGION_FIELDS = ("kind", "x", "y", "width", "height", "similarity")
_SCREEN_FIELDS = ("width", "height")
_SPOT_FIELDS = ("x", "y")

#: Matches a percent literal that spells out its % unit, the same way
#: durations spell out their unit (G6). The value is then required to
#: fall strictly between 0% and 100%: 0% would just be another way to
#: write an ``ignore`` region, and 100% would just mean the region
#: isn't there at all, so the language refuses to let either be
#: written as a similarity percentage.
_PERCENT = re.compile(r"(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)%$")

#: Maps each capture pixel format a plane may declare to the function
#: that normalizes a reference rendering into that format. The point
#: is having this hook at all, not what's in today's table: a plane
#: declares its capture format as a capability, and the reference
#: image is normalized through the matching function before
#: comparison, so a landmark asset captured on one plane still
#: matches correctly on another (docs/spec/landmarks.md, "The capture
#: format"). The VNC plane always forces 32bpp true color, so its
#: normalization is a no-op.
_NORMALIZERS = {
    "rgb": lambda image: image,
}


class LandmarkError(StaticError):
    """A landmark declaration error that can point at a specific
    location.

    This is a legality-tier error, like every other authored-document
    diagnostic: it is decided purely from the declaration's own text,
    so it counts as a STATIC ERROR and exits with code ``2``. It is
    rendered with the same format that :class:`document.BlueprintError`,
    :class:`fonts.FontError`, and :class:`script_nodes.ScriptParseError`
    already use (D70).
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

    Declared, validated, and stored, but not read anywhere until
    pointer verbs exist (this was cut from the original F65 scope). A
    landmark with no spots can be watched for but not clicked on, and
    that refusal is checked statically, before a script runs.
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
    """Find the renderings next to a declaration, ordered numerically.

    Numbers start at 1, and there is no requirement that they be
    contiguous — deleting a stale rendering is just deleting a file,
    which is the flip side of adding a rendering also being just
    adding a file. Each rendering's size is checked against the
    declaration's pinned dimensions here, before a machine even
    starts (G3): a rendering with the wrong size could never match
    anyway, and catching that at declaration load time turns it into
    a named error instead of a silent timeout later.
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
    """Parse and validate one ``.rlql`` file, raising a named error on
    any problem.

    Every check here is decided just from the declaration and the
    files next to it, so every one of these errors is caught before a
    machine even starts (G3).
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
    """Return ``{name: LandmarkDeclaration}`` for every ``.rlql`` file
    in the source.

    Names are checked against the same shared ``@`` namespace that
    media and font names already share — landmarks are the third kind
    of thing in that namespace (F65) — so a name reused across two
    files is an error that names both files.
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
    """One area a variant failed on, and by how much.

    ``region`` is ``None`` for the residual screen — everything not
    covered by a declared region, which requires a 100% match — so a
    failure report can name exactly where the mismatch was, rather
    than just saying that one happened.
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
    #: Total pixels that differed, across every region and the
    #: residual — used to rank which variant came closest to
    #: matching.
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
    """Put a reference rendering through a plane's declared capture
    format.

    This is the cross-adapter design settled in ``hyperv-screen.md``,
    implemented here at no extra cost: a plane declares the pixel
    format its captures arrive in, and the reference rendering is
    normalized through that same format before the pixel-equal
    comparison. That keeps "97 of every 100 pixels identical" meaning
    the same thing on every plane, as long as the normalization is a
    deterministic round trip. Both ``None`` and the VNC plane's
    ``rgb`` are no-ops.
    """
    if capture_format is None:
        return image
    try:
        return _NORMALIZERS[capture_format](image)
    except KeyError:
        raise InternalError(
            f"no landmark normalization for capture format "
            f"{capture_format!r}") from None


def _park_region(width, height):
    """Return the built-in ignore region around :func:`park_position`.

    This region is never authored and never appears in a ``.rlql``
    file — every match excludes it automatically, exactly as a
    declared ``ignore`` region would, because the parked cursor is
    something no landmark author asked to describe (F66). Its size is
    clamped to at most a quarter of the declaration's pinned screen
    size, not just capped at a fixed pixel size: on a screen small
    enough that the plain pixel cap would still cover the whole
    thing, the entire residual would be excluded, and a "match" that
    compares nothing isn't really a match.
    """
    size_x = min(_PARK_SIZE, max(1, width // 4))
    size_y = min(_PARK_SIZE, max(1, height // 4))
    return Region("ignore", width - size_x, height - size_y, size_x, size_y)


def _masks(declaration):
    """Build the three region categories as Pillow masks over one
    screen.

    ``ignore`` wins wherever regions overlap, so it is drawn first
    and subtracted from everything else; each fuzzy region then
    judges only its own remaining pixels; the residual is whatever no
    region claims at all. The built-in park-zone region (see
    :func:`_park_region`) is added to the declared ones on every
    landmark unconditionally, whether or not a script in this run
    ever clicks anything.

    These masks are built once per screen geometry, not once per
    sample. A `wait` re-reads the screen roughly every 0.2 seconds,
    and the masks only depend on the declaration, so rebuilding a
    full screen's worth of masks on every read would be the dominant
    cost of watching a landmark. The cache key is exactly what
    decides the masks — the file, its pinned size, and its regions —
    so two different declarations never share a cache entry, and an
    edited declaration gets fresh masks the next time it is parsed.
    """
    return _regime_masks(
        declaration.path, declaration.size,
        declaration.regions + (_park_region(declaration.width,
                                            declaration.height),))


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
    """Return one rendering, decoded and normalized, cached across
    samples.

    Without this cache, a `wait` would decode every variant on every
    sample, which for a 640x480 PNG is most of what watching a
    landmark costs. ``stamp`` (the file's modification time and size)
    is never read inside this function — its only job is being part
    of the cache key, so that when an author re-exports a rendering,
    the cache is never matched against pixels the file used to have.
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
    """Judge one capture against a landmark, trying each variant in
    turn.

    Returns a :class:`LandmarkMatch`: matched as soon as any variant
    comes back clean, and otherwise carrying the nearest miss —
    whichever variant had the fewest failing pixels, along with its
    failing regions and the percentage each one achieved. Each region
    is scored independently rather than pooled into one overall
    score: a small failing region would otherwise get averaged away
    by a large matching screen, and the report would lose the
    information about exactly where it failed.
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
