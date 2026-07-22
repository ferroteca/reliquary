<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Landmarks

> **Status:** the settled design for landmarks, the image-match
> assets for GUI guests (owner rounds, 2026-07-21; the
> adjudication trail is in planning/DECISIONS.md). The full asset
> spec — the `.rlql` JSON schema, the similarity metric, and
> landmark-block placement within a script — is settled at
> planning/ROADMAP.md milestone 12's "Decide first" round, where
> implementation lands; pointer input and the match-and-click
> verbs land with it.

Landmarks are the image-match assets for GUI guests — the
`@landmark` matcher the script language's growth rule already
names, and the assets U6's recorder captures.

**One declaration, N renderings.** A landmark is a single
declaration owning its geometry — the region list and the named
spot set (click points), with pinned screen dimensions and mode —
plus one or more *variants*: alternative renderings of the same
screen (palette, font, or shading differences). Variants share
the declaration's dimensions, mode, regions, and spots by
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

**Catalog form.** The declaration is `<name>.rlql`, a JSONC
authored document — the fourth authored extension beside
`.rlqb` / `.rlqm` / `.rlqs`, resolved under exactly the same
rules (planning/ROADMAP.md "Authored-asset resolution": root discovery by
extension, root shadows home, `--assets-only`; a `landmarks/`
subdirectory is optional dressing). Variant renderings are plain
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
one rule serve all four authored extensions.

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
  reliquary is the console, so the cursor position at capture
  time is always known; proposed assets mask that neighborhood,
  flagged as a generated comment (U6).
- Diagnostics capture reality: explicit `screenshot` and failure
  screenshots never inject a park move — it could dismiss the
  hover state or menu that explains a failure. In script runs
  they are cursor-clean anyway, because every pointer action
  already ended parked.

