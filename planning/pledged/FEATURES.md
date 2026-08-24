<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Pledged features

Large capability that is **pledged but not yet built**, each
carrying the work breakdown that delivers it. A feature arrives here
by being moved out of
[proposed/FEATURES.md](../proposed/FEATURES.md) — the move is the
pledge and the commit is its record ([README.md](../README.md))
— and leaves by being delivered, or by being **withdrawn** back to
that file when the pledge turns out to be one nobody meant (D44;
first used by D61).

Pledged is not scheduled: the numbered milestone arc ended with
milestone 9, so nothing below is queued or dated. The work items are
tasks like any other and answer to the same rules as
[TASKS.md](../TASKS.md); they sit with their feature rather than in
that queue because they are meaningless apart from it.

Each feature carries an **F-number** and must fit in **one sprint**
(D42; the rules are in [README.md](../README.md)). A feature too
large is cut on pledge, the split retiring the parent's number
for a fresh one per piece.

**F-numbers are issued against the sequence ledger**
([SEQUENCES.md](../SEQUENCES.md); owner, 2026-07-31): take the
next mark there and advance it in the same edit, by whichever
door the entry arrives — drafted in
[proposed/FEATURES.md](../proposed/FEATURES.md), or cut straight
to this file on pledge.

## F65 — Watch-only landmarks: the `.rlql` kind and the landmark condition

> **Pledged 2026-08-24** (owner), cut out of **F5** — which keeps
> its number and the remainder, D110's shape — as the GUI era's
> second piece; the cut's adjudication and its declined
> alternatives are recorded in the design itself
> ([design/landmarks.md](design/landmarks.md), "The cut").
> Serves **U5**. References **F63** (delivered): the VNC plane's
> framebuffer capture is what the matcher reads. The pointer
> piece ([../proposed/design/pointer-input.md](../proposed/design/pointer-input.md))
> composes on this one and pledges by its own decision. Runs
> under **G3** (every refusal before a machine starts), **P11**
> (the cursor interim stated, not mechanized), and **P21**
> (Pillow only — the metric was chosen partly for it).

Landmarks a script can *watch*: the `.rlql` authored kind and the
`@name` screen condition, with `click` and every pointer surface
deliberately out — before pointer verbs exist nothing moves the
guest's cursor, so capture and run agree by construction, and the
parking contract arrives with the pointer piece.

Work items:

1. The `.rlql` kind: parsing and validation per the settled
   schema — stem identity, the static refusals (bounds,
   `similarity` on the wrong region kind, the exclusive
   (0%, 100%) range, no variant PNG, a variant off the pinned
   dimensions), variants by stem-and-number adjacency with no
   contiguity demanded; the `landmarks` fixed leaf beside
   `fonts`; the one `@` pool gaining the third kind, collisions
   naming both files.
2. The matcher: pixel-equal fraction in three regimes — `ignore`
   excludes and wins overlaps, `fuzzy` judges its own pixels
   against its own literal, the residual requires 100% — judged
   per region, any variant deciding the landmark; nearest-miss
   reporting naming the closest variant, its failing regions and
   their achieved percentages; the plane-stated-format
   normalization hook (the identity on VNC's forced 32bpp); the
   stability gate's contract generalized from cells to pixels.
3. The condition: `@name` wherever a screen condition stands —
   single-form `wait`, `on` arms, `always` handlers — with
   `stable=` and `timeout` as any screen condition; kind checked
   at binding (a media or font in condition position is a static
   error naming use and kind); capability preflight at the
   condition's granularity (framebuffer capture); the dry-run
   timing plan naming landmark waits.
4. Norms and schema: script-spec's landmark value spelling,
   asset-resolution un-reserving `.rlql` and the `landmarks/`
   leaf going live, the cursor interim stated where the condition
   is specified, a packaged `.rlql` JSON schema beside the
   blueprint's, and the CHANGELOG.
5. Tests: the parser corpus for the static refusals; golden-frame
   matcher cases (match, per-region miss, variant fallback,
   nearest-miss report); the condition through the script suites;
   integration per the done-when.

Done when: integration, asked for by name, matches a real `.rlql`
landmark of a FreeDOS screen over the VNC plane on QEMU; a
variant miss reports its nearest-miss geography; a plane without
framebuffer capture refuses the condition by name; and the
agentless DOS suite passes byte for byte untouched.
