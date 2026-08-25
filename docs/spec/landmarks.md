<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Landmarks: the `.rlql` authored kind and the image match

> **Status:** normative for the delivered surface — the `.rlql`
> declaration, the pixel-equal matcher, and the `@name` screen
> condition (F65). It arrived here from
> `planning/pledged/design/` on delivery, which is the one-way move
> every shipped surface makes ([planning/README.md](../../planning/README.md)).
>
> **One thing below is stated and not built**: the cursor-parking
> contract, which arrives with the pointer verbs and is designed at
> [pointer-input.md](../../planning/pledged/design/pointer-input.md).
> It is named here because a landmark author needs to know why
> today's rule is enough and what will change — see
> [the cursor](#the-cursor) — and it binds nothing until that piece
> is pledged. Everything else on this page is in force.
>
> The authored `.rlql` document's norm is **split**, like the
> blueprint's: the published schema
> (`src/reliquary/schemas/landmark-schema-v1.json`) is normative for
> structure, and this document for everything a schema cannot
> express. Changes follow the surface-change rule
> ([SURFACES.md](../../planning/SURFACES.md)).

A **landmark** is the image-match asset for screens that text cannot
describe — a GUI installer's pages, a graphical boot menu, a splash a
recognizer reads as noise. A script watches one by name, exactly
where it would watch for a string:

```rlqs
wait @setup-page timeout=2m
```

## One declaration, N renderings

A landmark is a single declaration owning its **geometry** — the
pinned screen dimensions, the region list and the named spot set —
plus one or more **variants**: alternative renderings of the same
screen (palette, font or shading differences). Variants share the
declaration's dimensions, regions and spots by construction, which
makes those invariants structural rather than checked.

**A screen whose layout changed is a different landmark, not a
variant.** Variants exist for the same screen painted differently;
a moved button is a new landmark.

## Catalog form

The declaration is `<name>.rlql`, a JSON5 authored document — the
third authored extension beside `.rlqb` and `.rlqs`, resolved under
exactly the rules in [asset-resolution.md](asset-resolution.md).
Landmarks read from the `landmarks` directory, a fixed leaf under the
home (`<home>/landmarks`) and not one of the six placeable working
directories, on the same terms as `fonts`.

Variant renderings are **plain PNGs attached by stem-and-number
adjacency** — `<name>.<n>.png` beside the declaration — so refreshing
an asset is strictly file *creation*, never file rewriting, and
capture provenance lives in PNG text chunks rather than in a sidecar
file.

**Landmark names share the one collision-checked `@` pool** with
media and font names
([authored-binary-assets.md](../../planning/design/authored-binary-assets.md)).
Any duplicate visible to one script — `.rlql` against `.rlql`, or
against a media or a font — is an error naming both locations.

**Declarations are files, never script content.** A script
references landmarks and never carries them: there is no embedded
`landmark` block, as there is no embedded `media` block. A script is
UTF-8 text, so an embedded rendering would have to be base64 —
thousands of lines of payload around a hundred lines of procedure,
and a permanent freeze on the asset format, since anything embedded
in a text script can never become non-text.

## The declaration

```json5
// welcome-screen.rlql — welcome-screen.1.png,
// welcome-screen.2.png beside it
{
  "screen": { "width": 640, "height": 480 },
  "regions": [
    { "kind": "fuzzy", "x": 200, "y": 120,
      "width": 240, "height": 32, "similarity": "97%" },
    { "kind": "ignore", "x": 0, "y": 456,
      "width": 640, "height": 24 },
  ],
  "spots": {
    "next":   { "x": 520, "y": 440 },
    "cancel": { "x": 420, "y": 440 },
  },
}
```

A landmark is **stem-identified**, like a script and a font: it
carries no `name` field, because the variant renderings attach by
stem adjacency and a name diverging from the stem would break the
adjacency that attaches them. Keys are kebab-case, the document is
read through the shared JSON5 reader, and a diagnostic carries path,
line, column and rule id.

`regions` and `spots` are both optional: a bare landmark is the
whole-screen exact match, and a spotless one is watchable but not
clickable.

**The schema pins dimensions only; there is deliberately no `mode`
field.** RFB reports dimensions, and the guest's video mode — bit
depth, mode number — is observable over no control plane: the
framebuffer arrives forced to 32bpp. A field nothing can verify is a
declaration Reliquary would have to take on faith, and the PNG itself
carries the rendering.

### The static refusals

Every one of these is decided from the declaration and the files
beside it, so all of them land **before a machine starts**:

| rule id | what it refuses |
|---|---|
| `landmark.not-an-object` | a document that is not a JSON5 object |
| `landmark.unknown-field` | a key the declaration, a region or a spot does not define |
| `landmark.bad-screen` | a missing or non-positive `screen` dimension |
| `landmark.bad-region` | a region that is not an object, or whose coordinates are not whole non-negative pixels with a positive extent |
| `landmark.bad-region-kind` | a `kind` other than `fuzzy` or `ignore` |
| `landmark.bad-spot` | a spot that is not an object with whole non-negative `x` and `y` |
| `landmark.out-of-bounds` | a region or spot falling outside the pinned dimensions |
| `landmark.similarity-on-ignore` | `similarity` on an `ignore` region, which judges none of its pixels |
| `landmark.similarity-required` | a `fuzzy` region with no `similarity`; there is no default |
| `landmark.bad-similarity` | a percent that is not a literal with its unit spelled, or falls outside the **exclusive** (0%, 100%) range |
| `landmark.no-variant` | a declaration with no variant PNG beside it |
| `landmark.bad-variant-number` | a variant numbered below 1 |
| `landmark.unreadable-variant` | a variant that cannot be decoded as an image |
| `landmark.variant-dimensions` | a variant whose decoded dimensions differ from the pinned ones |

`similarity` is a percent literal with its unit spelled, as durations
spell theirs; there is no implicit default. The range is exclusive
because `0%` is an `ignore` region in a second spelling and `100%` is
the region's absence, and the language admits no second way to say
either.

**Variants are numbered from 1 and ordered numerically, with no
contiguity demanded** — deleting a stale rendering stays a file
deletion. Diagnostics name a variant by its filename. **Decode
normalization is conversion to RGB**, so a tool exporting opaque RGBA
does not fail its author.

## The match

**A bare landmark matches the entire screen exactly** — every pixel
equal after decode normalization. Declared regions soften or void
areas, and every pixel of a capture is in exactly one regime:

- an **`ignore`** region excludes its pixels outright, and **ignore
  wins where regions overlap**;
- a **`fuzzy`** region judges its own surviving pixels against its
  own declared percentage — matched fraction ≥ the literal;
- the **residual** — everything no region covers — requires 100%,
  which is the bare landmark's rule applied uniformly.

A **variant** matches when its residual is clean and every fuzzy
region clears its own bar. The **landmark** matches when any variant
does.

The metric is **pixel-equal fraction**, and it is judged
**per region, independently**. A single pooled screen score would let
a small failing region drown in a large matching screen's average —
the unsafe direction — and would lose the geography a failure report
needs. The asymmetry is deliberate: anti-aliasing and palette drift
fail toward a visible timeout, never toward the wrong screen, and
palette drift is what variants are for.

A capture whose size is not the pinned size matches nothing, and the
report says so rather than reporting a miss on every pixel.

### The nearest miss

When no variant matches, the failure report names the **closest
variant** — the one with the fewest failing pixels — with its failing
regions and the percentage each achieved:

```text
  landmark miss: @setup-page came closest on setup-page.2.png
    (fuzzy 240x32+200+120 at 97%: 91.40% of 97% required)
```

### The capture format

A control plane **states the pixel format its screen carrier captures
in**, and the *reference* rendering is normalized through that format
before the comparison. A deterministic round trip therefore keeps "97
of every 100 pixels identical" meaning the same thing on every plane,
so an asset captured on one plane still matches on another whose
capture quantizes. Every plane that captures a framebuffer today
states `rgb`, so the normalization is the identity.

A plane that states **no** format captures no framebuffer, and a
landmark condition against a machine driving it is refused by name —
see [capability](#capability) below.

## The `@name` screen condition

**`@name` stands wherever a screen condition stands**: a single-form
`wait`, an `on` arm of a branching wait, and an `always` handler of a
reactive phase. It carries `stable=` and `timeout` like any screen
condition, and one condition per observation, unchanged:

```rlqs
wait @setup-page stable=500ms timeout=2m

wait {
    on @finished-page  { goto done }
    on "Setup failed"  { finish }
}

phase installing {
    always @error-dialog { press esc }
    always @summary-page { finish }
}
```

A GUI installer's error dialogs are exactly the `always` case, which
is why handlers are in from the first cut rather than carved out of
it.

This is the growth rule doing what it was written for
([script-spec.md](script-spec.md), "How the vocabulary grows"): a new
matcher over an existing channel arrives as a **new value spelling**,
not new syntax. The screen stays the unprefixed default channel, and
there is no negation form — the language has none, and none arrives
here.

### Kind, checked at binding

The `@` pool is one namespace across media, fonts and landmarks, so
**the use decides which kind is meant** and the reference is checked
against it when the pool is read:

- a `@name` in condition position naming no landmark is
  `landmark.unknown`, with a did-you-mean over the landmark names the
  source holds;
- a `@name` in condition position that resolves to a **media or a
  font** is `landmark.wrong-kind`, naming the use and the kind it
  actually hit — exactly as a landmark name in `insert` position is
  refused in the other direction.

Both are PREFLIGHT ERRORS: they are settled by the world the authored
script is run against — which assets the source holds — rather than
by the script text alone.

### Capability

A landmark condition requires **framebuffer capture**, and the
capability is preflighted at the **condition's granularity** rather
than the script's: a script that watches no landmark asks the plane
for nothing and runs on a plane that captures nothing, exactly as it
always did.

The machine's first declared control plane drives its session, and
that is the plane asked. If it states no capture format, the run is
refused before any guest input, naming the plane and the condition
(`machine.plane-no-framebuffer`).

What decides is what a plane's **screen carrier** is, not which
hypervisor is behind it:

| plane | screen carrier | landmarks |
|---|---|---|
| QEMU, `agentless-display` | VGA text memory over QMP — characters the guest already resolved | refused by name |
| QEMU, `vnc` | the RFB framebuffer | `rgb` |
| VirtualBox, `agentless-display` | a guest-display screenshot | `rgb` |

The diagnostic `screenshot` verb and the automatic failure capture
are a different carrier on a different clock, and they keep working
on every plane; a plane that captures a diagnostic image does not
thereby offer a screen a landmark can be matched against.

### The settled-frame rule

A landmark, like text, is only ever judged on a frame the guest has
stopped drawing. The quiescence gate's contract generalizes from
cells to pixels for a landmark compare — the proportion of *pixels*
that held still over the same window, at the same default. This is
host-side behaviour rather than script surface: `stability=` is
written and read exactly as it is for a text condition.

## The cursor

Captures and matching are cursor-free by construction today, and the
mechanism that will keep them so is **not yet built**.

**Today**: nothing moves the guest's cursor. There are no pointer
verbs, so a keyboard-only run leaves the cursor where the guest drew
it — which is where the author's capture shows it — and capture and
run agree without any mechanism at all. An author who wants a screen
whose cursor may sit anywhere declares an `ignore` region, like any
other furniture.

**With the pointer verbs**
([pointer-input.md](../../planning/pledged/design/pointer-input.md)):
every pointer verb will end by parking the cursor at a fixed
per-platform park position — never script surface — the park zone
becomes a built-in ignore region, and a cursor-free capture is used
automatically where the control plane can provide one (RFB cursor
pseudo-encodings). None of that lands until that piece is pledged,
and this document is where it will be stated when it does.

Diagnostics capture reality either way: an explicit `screenshot` and
an automatic failure capture never inject a park move, because it
could dismiss the hover state or menu that explains a failure.

## What a landmark is not

- **There is no selecting region.** os-autoinst-style regions that
  confine matching to declared rectangles are deferred as additive
  growth; today a region softens or voids, and the rest of the screen
  is always judged.
- **There is no `click`, and no spot is read.** `spots` are declared
  and validated because a recorder writes them and the schema is
  settled, but the verbs that consume them arrive with the pointer
  piece.
- **A landmark is not recordable.** A screen transcript holds
  character rows and attribute tokens, so a run watching a landmark
  can be recorded but its landmark waits cannot be replayed: the
  replay says so by name rather than improvising a screen.
