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

## F66 — Pointer input: `pointer_event`, the tablet device, and `click`

> **Pledged 2026-08-25** (owner), cut out of **F5** — which keeps
> its number and the remainder, D110's shape — as the GUI era's
> third piece; the cut's adjudication and its declined
> alternatives are recorded in the design itself
> ([design/pointer-input.md](design/pointer-input.md), "Out of
> scope"). Serves **U5**. References **F63** (delivered): the VNC
> plane's `KeyEvent` carrier is what `pointer_event` joins.
> References **F65** (delivered): a `click` search matches a
> landmark and its target is one of that landmark's named spots.
> Runs under **G3** (every refusal before a machine starts),
> **P10** (an absolute delivery needs an absolute device — never a
> calibration guess against a relative one), **P11** (a
> relative-only machine is a named capability failure, not an
> approximation), and **P25** (the multi-backend gate, cleared on
> paper: every backend in the priority order has an absolute
> pointing device).

One wire shape, composition above it: the seam gains exactly one
carrier method, `pointer_event(x, y, buttons)` — RFB's own
`PointerEvent` shape, which the entry's three portable primitives
(move, press, release) collapse into. `click` and cursor parking
compose above it; no adapter grows a second method as the surface
grows.

Work items:

1. The carrier: `pointer_event` at the control-plane seam; the
   VNC plane speaks it with no translation (the `PointerEvent`
   the in-tree RFB client deliberately reserved); the QMP plane
   decomposes it into `input-send-event` `abs`/`btn` sequences.
   Coordinates are framebuffer pixels throughout — a landmark's
   own coordinate space, so a click point needs no second scale
   and no verb re-checks what matching already checked.
2. The device: `pointing-device` (`tablet` / `mouse`) as a
   first-class machine field, joining `backends.Requirements` and
   capability-checked per backend exactly as `drives` is; a
   declared `tablet` a backend cannot supply fails assignment
   closed, naming both. Pointer verbs preflight-refuse a
   relative-only machine by name — never a corner-slam
   calibration attempt.
3. The verb: `click @landmark` / `click @landmark spot="name"` —
   an observation-bearing action like `select`: its search runs
   under the statement's effective `timeout` and the stability
   gate, its delivery pays `pacing`. The lone-spot default; a
   `spot=` naming nothing in the declaration is a static error,
   the `.rlql` being loaded at preflight. Left-single-click is the
   whole first cut — `button=`, `count=`, and a drag verb are
   additive sibling growth on a seam that already carries them,
   with no named demand yet.
4. Parking: every pointer verb's delivery ends with a park-position
   `pointer_event` — the last event of the composed delivery, no
   new mechanism and no script surface. This is what
   `docs/spec/landmarks.md`'s stated cursor interim names as
   arriving with this piece; the park zone becomes a built-in
   ignore region.
5. Capability preflight at the condition's granularity: a `click`
   requires pointer input on the selected control plane and
   `pointing-device: tablet` on the machine, each refusal naming
   itself before the first guest input.
6. Norms and schema: script-spec's `click` verb and its row in the
   placement matrix and the resolved timing plan; blueprint-model's
   `pointing-device` field and its capability vocabulary; the
   cursor-parking contract stated in docs/spec/landmarks.md
   mechanized; the CHANGELOG.
7. Tests: the parser corpus for the static refusals (an unmatched
   `spot=`); the preflight refusals (a `mouse` machine, a plane
   without pointer input); golden delivery cases through the fake
   backend seam; integration per the done-when.

Done when: integration, asked for by name, drives a machine with
`pointing-device: tablet` and a two-spot landmark, `click`ing each
spot to an observable guest effect with the cursor parked and out
of the match region after each; a `click` on a landmark that never
appears times out naming the statement's clock and scope with no
pointer event delivered; the three preflight refusals — a `mouse`
machine, a plane without pointer input, an unmatched `spot=` —
land by name before a machine starts; and the agentless DOS suite
passes byte for byte untouched.
