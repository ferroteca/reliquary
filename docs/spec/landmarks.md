<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Landmarks: the `.rlql` file format and image matching

> **Status:** normative for the shipped feature — the `.rlql`
> declaration format, the pixel-equal matcher, the `@name` screen
> condition (F65), and the `click` verb with its spot lookup and
> cursor-parking rules (F66). This document moved here from
> `planning/pledged/design/` when the feature shipped. Every shipped
> feature's spec moves the same way, and that move only happens once
> ([planning/README.md](../../planning/README.md)).
>
> Two documents together define what an `.rlql` file must contain,
> the same split used for blueprints: the published schema
> (`src/reliquary/schemas/landmark-schema-v1.json`) defines the
> structure, and this document covers everything the schema cannot
> express. Changes to either follow the surface-change rule
> ([SURFACES.md](../../planning/SURFACES.md)).

A **landmark** is an image to match against the screen, for screens
that have no text to read — a GUI installer's pages, a graphical boot
menu, a splash screen that a text recognizer would only see as noise.
A script watches for a landmark by name, the same way it watches for
a string:

```rlqs
wait @setup-page timeout=2m
```

## One declaration, many renderings

One declaration holds the fixed facts about a screen — its **screen
dimensions**, its **region list**, and its named **spot set** — plus
one or more **variants**: different renderings of the same screen
(palette, font, or shading differences). Every variant shares the
declaration's dimensions, regions, and spots automatically, because
they all come from the one declaration; there is nothing to check,
because there is nothing that could disagree.

**A screen whose layout changed is a different landmark, not a
variant.** Variants are for the same screen painted differently. If
a button moves, that's a new landmark.

## Catalog form

A landmark is written as `<name>.rlql`, a JSON5 file — the third
authored file extension alongside `.rlqb` and `.rlqs` — resolved
under the same rules as any other asset
([asset-resolution.md](asset-resolution.md)). Landmark files live in
the `landmarks` directory: a fixed location under the home
(`<home>/landmarks`), not one of the six directories a user can
place elsewhere, on the same footing as `fonts`.

Variant renderings are **plain PNG files, matched to their
declaration by filename** — `<name>.<n>.png` sits beside
`<name>.rlql`. Adding a new variant is always creating a new file,
never rewriting an existing one, and the PNG's own text chunks (not
a separate sidecar file) record how it was captured.

**Landmark names, media names, and font names share one namespace,
and Reliquary checks it for collisions**
([authored-binary-assets.md](../../planning/design/authored-binary-assets.md)).
If a script can see two names that collide — an `.rlql` against
another `.rlql`, or against a media or font name — that is an error,
and the error names both files.

**A landmark is always a separate file; a script never contains
one.** A script references a landmark by name and never embeds it —
there is no way to write a landmark inline in a script, the same as
there is no way to embed a media file inline. A script is UTF-8
text, so an embedded image would have to be written as base64:
thousands of lines of encoded data around a hundred lines of actual
script, and once that were allowed, the image format could never
change to something non-text-based.

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

A landmark is **identified by its filename**, like a script or a
font: the declaration has no `name` field. Variant PNGs are matched
to their declaration by filename, so if the declaration's name could
differ from its filename, that matching would break. Keys are
kebab-case. The document is read with the same JSON5 reader used
elsewhere, and any error reports a path, line, column, and rule id.

`regions` and `spots` are both optional. A landmark with no regions
must match the whole screen exactly. A landmark with no spots can be
watched for, but nothing on it can be clicked.

**The schema only records screen dimensions; it deliberately has no
`mode` field.** RFB (the remote framebuffer protocol) reports
dimensions, but no control plane can report the guest's video mode —
its bit depth or mode number — because the framebuffer always
arrives already converted to 32 bits per pixel. Reliquary won't
record a field it has no way to verify; the rendering itself,
captured in the PNG, is the only source of truth for what the screen
looks like.

### The static refusals

Reliquary can check every one of these rules just by reading the
declaration and the files next to it, so all of them are caught
**before a machine starts**:

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

`similarity` is written as a percentage with its `%` sign, the same
way durations spell out their unit, and there is no default value.
The allowed range excludes both endpoints: `0%` would just be
another way of writing an `ignore` region, and `100%` would just be
leaving the region out entirely, and the language does not allow two
ways to say the same thing.

**Variants are numbered starting from 1, in numeric order, and the
numbers don't need to be consecutive.** Deleting an outdated variant
is just deleting its file — nothing else needs renumbering. Error
messages identify a variant by its filename. **When Reliquary
decodes a PNG, it converts it to RGB**, so a tool that exports
opaque RGBA still works.

## The match

**A landmark with no declared regions must match every pixel of the
screen exactly**, after both images are decoded to RGB. Declared
regions relax or exclude parts of the screen from that check. Every
pixel of a captured screen falls into exactly one of these:

- An **`ignore`** region is excluded from matching entirely, and
  where an `ignore` region and a `fuzzy` region overlap, `ignore`
  wins.
- A **`fuzzy`** region is judged against its own declared
  percentage: the fraction of its pixels that match must be at
  least that percentage.
- The **residual** — every pixel not covered by any region — must
  match 100%. That's the same rule a bare landmark applies to the
  whole screen, applied here to whatever regions leave uncovered.

A **variant** matches when its residual matches 100% and every
fuzzy region meets its own percentage. The **landmark** matches when
at least one of its variants matches.

Each region's match is measured on its own, as a fraction of
matching pixels, and never averaged into one screen-wide score.
Averaging would let a small failing region get lost inside a large
screen that otherwise matches — the wrong kind of mistake to allow —
and it would throw away the information a failure report needs about
where the mismatch actually is. This is deliberately asymmetric:
anti-aliasing and palette drift should make a wait fail visibly, as
a timeout, never make it match the wrong screen — and palette drift
is exactly what variants exist to handle.

If a captured screen is not the same size as the landmark's declared
dimensions, nothing can match, and the failure report says exactly
that — it does not report every pixel as a mismatch.

### The nearest miss

When no variant matches, the failure report names the **closest
variant** — the one with the fewest failing pixels — lists which of
its regions failed, and gives the percentage each one achieved:

```text
  landmark miss: @setup-page came closest on setup-page.2.png
    (fuzzy 240x32+200+120 at 97%: 91.40% of 97% required)
```

### The capture format

Each control plane declares the pixel format its screen carrier
captures in, and the landmark's *reference* rendering is converted
to that same format before comparison. That conversion is
deterministic in both directions, so "97 of every 100 pixels match"
means the same thing regardless of which plane captured the
reference image — an asset captured on one plane still matches
correctly on another plane whose captures are quantized differently.
Every plane that captures a framebuffer today declares `rgb`, so
today this conversion is a no-op.

A plane that declares **no** capture format captures no framebuffer
at all. A landmark condition used against a machine running on that
plane is refused, by name — see [capability](#capability) below.

## The `@name` screen condition

**`@name` can appear anywhere a screen condition can appear**: in a
plain `wait`, in an `on` branch of a branching wait, and in an
`always` handler inside a reactive phase. It takes `stable=` and
`timeout` like any other screen condition, and the existing rule of
one condition per observation still applies:

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

A GUI installer's error dialogs are a typical use of the `always`
case. That's why `always` handlers were included from the start,
rather than added later.

This follows the vocabulary-growth rule described in
[script-spec.md](script-spec.md) ("How the vocabulary grows"): a new
way to match the same channel is written as a **new kind of value**,
not as new syntax. The screen stays the default, unprefixed channel.
There is no way to negate a condition — the language has no
negation anywhere, and landmarks don't add one.

### Kind, checked at binding

Media, fonts, and landmarks share one `@name` namespace, so **where
a name is used decides which kind it must be**. That check happens
when the name is looked up:

- A `@name` used as a condition that names no landmark is an error,
  `landmark.unknown`, and the error suggests the closest matching
  landmark name the source actually has.
- A `@name` used as a condition that does resolve, but to a media
  item or a font rather than a landmark, is `landmark.wrong-kind`.
  The error names the use and which kind it actually found — the
  same check applies in reverse: a landmark name used where `insert`
  expects a media or font is refused too.

Both are PREFLIGHT ERRORS: they can only be checked against the
actual assets available when the script runs, not from the script
text alone.

### Capability

A landmark condition requires the control plane to capture the
framebuffer. Reliquary checks this per condition, not once for the
whole script: a script that never watches for a landmark makes no
such demand on the plane, and runs fine on a plane that captures no
framebuffer at all — exactly as it did before landmarks existed.

The machine's session is driven by its first declared control plane,
and that is the plane Reliquary checks. If that plane declares no
capture format, the run is refused before any input reaches the
guest, and the error names both the plane and the condition
(`machine.plane-no-framebuffer`).

What matters is what a plane's **screen carrier** actually is, not
which hypervisor is behind it:

| plane | screen carrier | landmarks |
|---|---|---|
| QEMU, `agentless-display` | VGA text memory over QMP — characters the guest already resolved | refused by name |
| QEMU, `vnc` | the RFB framebuffer | `rgb` |
| VirtualBox, `agentless-display` | a guest-display screenshot | `rgb` |

The diagnostic `screenshot` verb and the automatic failure capture
use a different carrier, on a different schedule, and they keep
working on every plane regardless. A plane that can capture a
diagnostic image does not necessarily offer a screen that a landmark
can be matched against.

### The settled-frame rule

A landmark, like text, is only ever checked against a frame the
guest has stopped drawing. The same stability check used for text
applies here too, measured in pixels instead of character cells: the
proportion of *pixels* that stayed the same over the same time
window, using the same default. This is something Reliquary does
internally, not something the script controls differently:
`stability=` is written and behaves exactly as it does for a text
condition.

## The cursor

Captures and matching never include the cursor, and every pointer
verb keeps it that way (F66).

**Before the first `click`, and for the whole run if the script
never clicks**: nothing moves the guest's cursor. It stays wherever
the guest itself drew it, which is also where it was when the author
captured the landmark — so the capture and the running screen agree
with no extra work needed. If an author wants to allow the cursor to
sit anywhere on a screen, they still declare an `ignore` region for
it, the same as for anything else that might vary.

**Every pointer verb ends by moving the cursor to a fixed parking
position** on the screen it just acted on. That position is scaled
to that landmark's own declared dimensions, not to one fixed pixel
position, because different landmarks declare different screen
sizes. This parking spot is treated as a **built-in `ignore`
region**: Reliquary adds it to a landmark's declared regions at
match time, but it is never written into the `.rlql` file. Reliquary
does this by masking the parking spot on the host side, not by
hiding the cursor from the capture itself — it does not negotiate an
RFB pseudo-encoding to suppress the cursor from the framebuffer. So
an author capturing a screen by hand still sees whatever the guest
actually drew, including a cursor that a previous `click` parked
into the frame.

Diagnostic captures always show reality as it is: an explicit
`screenshot` and an automatic failure capture never trigger a park
move first, because that move could dismiss the hover state or menu
that would have explained the failure.

## What a landmark is not

- **There is no "selecting" region kind.** Some other tools (in the
  os-autoinst style) let a region confine matching to just that
  rectangle and ignore the rest of the screen. Reliquary does not do
  that today — a region can only soften (`fuzzy`) or exclude
  (`ignore`) part of the screen, and everything else is always
  checked. This could be added later.
- **There is no drag, multi-button click, or timed pointer
  sequence.** `click` only does a single left click today (F66).
  Adding `button=` for other mouse buttons, `count=` for
  double-clicks, or a separate drag verb is possible later, but
  nobody has asked for it yet. The underlying `pointer_event` call
  already accepts a button mask and can already be called
  repeatedly in sequence, so adding these to the script language
  would only mean new syntax — it would not require any change to
  the backend code.
- **A landmark cannot be replayed from a recording.** A recorded
  screen transcript stores character rows and their attributes, not
  images. So a run that watches a landmark can still be recorded,
  but replaying that recording cannot re-create the landmark match —
  the replay says so explicitly instead of guessing what the screen
  looked like.
