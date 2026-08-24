<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Landmarks

> **Status:** the settled design for landmarks, the image-match
> assets for GUI guests (owner rounds, 2026-07-21; the
> adjudication trail is in planning/DECISIONS.md). **The
> remainder that round deferred is settled below** (owner round,
> 2026-08-24): the `.rlql` schema, the similarity metric, and
> reference placement — the F5 "Decide first" bullet used to call
> the third item "landmark-block placement within a script", a
> phrase surviving from before D12 deleted the embedded block;
> what it names is where `@name` may stand.
>
> **The watch-only piece is pledged as F65** (owner, 2026-08-24;
> [../FEATURES.md](../FEATURES.md)), which is why this document
> sits in `pledged/design/` — "The cut" below is that piece's
> boundary. The pointer half — `click`, parking, the park-zone
> mask — remains proposed with **F5**, designed at
> [pointer-input.md](../../proposed/design/pointer-input.md).

Landmarks are the image-match assets for GUI guests — the
`@landmark` matcher the script language's growth rule already
names, and the assets U6's recorder captures.

**One declaration, N renderings.** A landmark is a single
declaration owning its geometry — the region list and the named
spot set (click points), with pinned screen dimensions (this
used to say "and mode"; dropped 2026-08-24, in the schema
section below) —
plus one or more *variants*: alternative renderings of the same
screen (palette, font, or shading differences). Variants share
the declaration's dimensions, regions, and spots by
construction, which makes the decided variant invariants
(identical spot sets, declared order) structural rather than
checked. A screen whose *layout* changed is a different landmark,
not a variant — keeping variants aligned with U6's "changed
screen for an unchanged step".

**Whole-screen match; regions are modifiers.** A bare landmark
matches the entire screen exactly (pixel-equal after decode
normalization). Declared regions soften or void areas: a `fuzzy`
region carries an explicit `similarity` percent literal (its unit
spelled, as durations spell theirs; no implicit default — G6),
and an `ignore` region is excluded outright. This chooses the
safe failure asymmetry: over-matching misses and times out
visibly (G4), where under-matching would fire on the wrong
screen. os-autoinst-style *selecting* regions that confine
matching to declared rectangles are deferred as additive growth
(G7). Failure reporting stays per-variant: the nearest miss names
the closest variant.

**Catalog form**, and the shape below is no longer landmarks' alone:
it is the project's rule for authored binary assets generally
([design/authored-binary-assets.md](../../design/authored-binary-assets.md)),
stated once when U25's fonts became its second instance. What
follows is where it was settled. The declaration is `<name>.rlql`, a JSON5
authored document — the third authored extension beside
`.rlqb` / `.rlqs`, resolved under exactly the same
rules (docs/spec/asset-resolution.md: home mode
vs a hermetic `--assets` project root, discovery by extension;
a `landmarks/` subdirectory is optional dressing). Variant renderings are plain
PNGs attached by stem-and-number adjacency — `<name>.<n>.png`
beside the declaration, ordered numerically — so a U6 asset
refresh is strictly file-creation, never file-rewrite, and
capture provenance lives in PNG text chunks, not sidecar files.
Landmark names share the collision-checked `@` pool with media
names; any duplicate visible to one script — `.rlql` against
`.rlql`, or against a media name — is an error naming both
locations.

**Declarations are files, never script content.** A script
references landmarks and never carries them: there is no
embedded `landmark` block, as there is no embedded `media`
block (owner, 2026-07-22 — planning/DECISIONS.md, the
no-JSON-in-scripts round). A script is UTF-8 text, so an
embedded rendering would have to be base64 — thousands of
lines of payload around a hundred lines of procedure, and a
permanent freeze on the asset format, since anything embedded
in a text script can never become non-text. Keeping the
declaration in its own file leaves `.rlql` free to grow a
non-text form later, keeps scripts legible (G4), and makes
one rule serve all three authored extensions.

**Cursor normalization.** Captures and matching always strip the
mouse cursor — a normalization, never an option:

- Every pointer verb ends by parking the cursor at a fixed
  per-platform park position; parking is never script surface.
  For guests that composite the cursor into the framebuffer
  (software cursors — nothing host-side can erase what the guest
  drew), parking *is* the stripping mechanism: the guest
  repaints, and every later capture is clean by construction.
- The park zone is permanently masked from matching — a built-in
  ignore region; a declared region overlapping it draws a
  preflight warning.
- Where the control plane can capture a cursor-free framebuffer
  (RFB cursor pseudo-encodings), that is used automatically.
- While recording, the human drives and cannot be parked — but
  Reliquary is the console, so the cursor position at capture
  time is always known; proposed assets mask that neighborhood,
  flagged as a generated comment (U6).
- Diagnostics capture reality: explicit `screenshot` and failure
  screenshots never inject a park move — it could dismiss the
  hover state or menu that explains a failure. In script runs
  they are cursor-clean anyway, because every pointer action
  already ended parked.

## The `.rlql` schema

Settled in the 2026-08-24 owner round, with the metric and the
placement below. **Stem-identified**, like a script and a font —
asset-resolution.md's reserved text already attaches the variant
renderings by *stem* adjacency, and a `name` field diverging from
the stem would break the adjacency that attaches them. A JSON5
document through the shared reader (D102), kebab-case keys, the
`FontError` diagnostic skeleton — path, line, column, rule id:

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

`regions` and `spots` are optional: a bare landmark is the
whole-screen exact match, and a spotless one is watchable but not
clickable — a `click` against it is the static error
[pointer-input.md](../../proposed/design/pointer-input.md) names. The static refusals,
all before a machine starts (G3): a region or spot outside the
pinned dimensions; `similarity` on an `ignore` region or missing
from a `fuzzy` one; a percent outside the **exclusive** (0%,
100%) range — `0%` is `ignore` in a second spelling and `100%` is
the region's absence, and G6 refuses both; no variant PNG at all
(the `font.no-bank` shape); a variant whose decoded dimensions
differ from the pinned ones. `similarity` is a percent literal
with its unit spelled, as the shape section above already
settled.

**Variants are numbered from 1 and ordered numerically, with no
contiguity demanded** — deleting a stale rendering stays a file
deletion, which is U6's file-creation property read in both
directions; diagnostics name a variant by its filename. **Decode
normalization is conversion to RGB**, so a tool exporting opaque
RGBA does not fail its author.

**The schema pins dimensions only — mode is dropped.** The
declaration used to pin "dimensions and mode"; nothing can check
the second half. RFB reports dimensions, and the guest's video
mode — bit depth, mode number — is observable over no plane: the
framebuffer arrives forced-32bpp. A field nothing can verify is a
declaration P10 refuses to act on and P11 refuses to pretend
about, and the PNG itself carries the rendering.

- **WEIGHED AND DECLINED — `mode` kept as unvalidated
  provenance**: costs nothing at match time, but it is schema
  surface that guarantees nothing, and a reader will assume it is
  checked. Capture provenance already has a home in the PNG text
  chunks.

## The similarity metric: pixel-equal fraction

Every pixel after decode normalization is judged by **exact
equality** — with the reference side first normalized through the
capture plane's stated pixel format, a seam rule settled at
[hyperv-screen.md](../../proposed/design/hyperv-screen.md) ("one rule for every
plane"; on VNC's forced 32bpp it is the identity) — and every
pixel is in exactly one regime: an `ignore`
region excludes it — ignore wins where regions overlap — a
`fuzzy` region judges its own pixels against its own threshold
(matched fraction ≥ the declared literal), and the residual
screen requires 100%, which is the bare landmark's rule applied
uniformly. A variant matches when its residual is clean and every
fuzzy region clears its own bar; the landmark matches when any
variant does.

The metric is legible — "97 of every 100 pixels identical" is a
sentence an author can act on — it needs nothing beyond Pillow
(P21), and it fails in the safe direction the shape section
chose: anti-aliasing and palette drift fail toward a visible
timeout, never toward the wrong screen, and palette drift is what
*variants* are for.

- **WEIGHED AND DECLINED — per-channel tolerance**: absorbs
  dithering without a variant, but adds a second knob the author
  must understand, and softens toward wrong-match — the unsafe
  direction.
- **WEIGHED AND DECLINED — correlation (NCC/SSIM,
  os-autoinst's family)**: robust to global brightness shifts,
  but drags in numpy/OpenCV for the one consumer (P21), and the
  score is unexplainable on a failure report.
- **WEIGHED AND DECLINED — one pooled screen score**: a single
  similarity with regions as weights reads simple, but a small
  failing region drowns in a large matching screen's average —
  the unsafe direction again — and the failure report loses its
  geography. **Per-region, independently** is the rule: a
  failure names the region and its achieved percent.

Fuzzy-over-fuzzy overlap draws a preflight warning (the
park-zone precedent above) and each region is judged on its own
pixels. The nearest-miss report stays per-variant as settled:
the closest variant is the one with the fewest failing pixels,
reported with its failing regions and their achieved
percentages.

## Reference placement

The growth rule already wrote the answer's form: `wait
@setup-page` is "a new value spelling … a different matcher over
the same screen". So **`@name` stands wherever a screen condition
stands** — single-form `wait`, an `on` arm, an `always` handler —
carrying `stable=` and `timeout` like any screen condition, one
condition per observation unchanged. A GUI installer's error
dialogs are exactly the `always` case, so carving handlers out of
the first cut would cut against the feature's own use; the
narrower cut was weighed and declined for that reason.

The `@` pool is one namespace, so **kind is checked at binding**:
`@name` resolving to a media (or a font) in condition position is
a static error naming the use and the kind, exactly as a landmark
name in `insert` position would be. Capability stays at the
condition's granularity: a landmark condition requires
framebuffer capture, preflight-checked per condition (G3). There
is no negation form — the language has none, and none arrives
here.

One host-side note, not script surface: the stability gate's
contract generalizes from cells to pixels for landmark compares —
the proportion of pixels changed over the same window, the same
default — so a landmark, like text, is only ever judged on a
settled frame.

## The cut: F5's first piece is watch-only landmarks

Prepared in the 2026-08-24 owner round so the pledge is
mechanical; the piece takes the ledger's next F-number **in the
pledge commit, not here**, citing U5 and referencing F63, and F5
keeps its number and the remainder — D110's own shape.

**The order is forced, not chosen.** A pledged item may not
depend on a proposal, and `click` composes on landmarks — its
search matches one, its target is a landmark's spot — so the
pointer piece cannot pledge first. The pointer carrier alone,
with no verb to send through it, is the surface `rfb.py`'s own
doctrine refuses. Watch-only landmarks are the one piece whose
references all point at delivered work — F63's framebuffer
capture, the JSON5 reader (D102), asset resolution, the
stability gate, the condition seam — and the piece carries
standalone value: NT-era setup is largely keyboard-drivable
(F5's era note), so `wait @name` plus the delivered keyboard
verbs is the whole loop for keyboard-first GUI flows the moment
a platform workflow arrives.

- **WEIGHED AND DECLINED — landmarks and pointer as one
  piece**: two designs' worth of surface in one pledge, the
  seven-work-items shape the sprint bound exists to refuse.
- **WEIGHED AND DECLINED — the pointer seam first**: `click`
  cannot come with it (an upward reference), and a carrier
  without a sender is refused above.

**In the piece:** `.rlql` parsing and validation per the schema
above — stem identity, the static refusals, variants by
adjacency; the `landmarks` fixed leaf and `@` pool integration,
asset-resolution.md un-reserving `.rlql` in the same act; the
pixel-equal matcher — three regimes, per-region judgment,
nearest-miss reporting, and the plane-stated-format
normalization hook ([hyperv-screen.md](../../proposed/design/hyperv-screen.md)), the
identity on VNC so it lands as one seam point costing nothing
today; `@name` as a screen condition in `wait` / `on` /
`always`, kind-checked at binding, capability preflight at the
condition's granularity, the dry-run timing plan naming it; the
norms amended (script-spec's value spelling, asset-resolution)
and a packaged `.rlql` schema beside the blueprint's.

**Out, staying where it stands:** `click` and every pointer
surface ([pointer-input.md](../../proposed/design/pointer-input.md) whole — the
natural second piece, its references then pointing at this one,
downward); the cursor-parking contract and the park-zone
built-in mask; the recorder (F1); other backends' endpoints,
platform workflows, and the cropping convenience.

**The cursor interim, stated rather than mechanized.** Parking
exists because pointer verbs move the cursor unpredictably.
Before any pointer verb exists nothing moves the guest's
cursor — a keyboard-only run leaves it where the guest drew it,
which is where the author's capture shows it, so capture and run
agree by construction. The norm states that the parking contract
arrives with the pointer piece (P11), and no mechanism lands
now.

- **WEIGHED AND DECLINED — minimal internal parking in this
  piece**: it drags the `pointing-device` field and the carrier
  in — half the pointer design — past the sprint bound, for a
  hazard keyboard-only runs cannot produce.

**Proof, on delivered machinery only:** integration asked for by
name — a real `.rlql` landmark of a FreeDOS screen matched over
the VNC plane on QEMU; a variant miss reported with its
nearest-miss geography; the capability refusal on a plane
without framebuffer capture; and the agentless DOS suite byte
for byte untouched. Proving against a real GUI guest would
couple the piece to unpledged platform workflows — the flaw the
reference rule names — so that proof belongs to the workflow
piece that boots one.

