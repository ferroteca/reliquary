<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Pointer input: one wire shape, composition above it

> **Status:** the design for **F5**'s pointer-input piece
> (planning/proposed/FEATURES.md, the GUI era's "Decide first"
> bullet) — owner round, 2026-08-24. The demand is **U5** (pledged;
> D110 adjudicated it as the GUI half's), and it references the
> delivered VNC plane (F63) and **the watch-only landmarks piece**
> ([docs/spec/landmarks.md](../../../docs/spec/landmarks.md)), which is
> **delivered** — so this piece's references point downward at
> shipped surface rather than at a pledge. The four calls
> below were adjudicated in the round that produced this
> document; their rejected alternatives are recorded here, the way
> [platform-dialect.md](../../proposed/design/platform-dialect.md)
> records its own.
>
> **This piece is pledged as F66** (owner, 2026-08-25;
> [../FEATURES.md](../FEATURES.md)), which is why this document
> sits in `pledged/design/` — "Out of scope" below is that piece's
> boundary, and the host-side landmark-cropping convenience it
> names stays open in F5's own entry.

## The claim

F5's two-layer event model holds, and it collapses further than
the entry's text says. The entry names three portable primitives —
pointer move, button press/release, key press/release — but RFB's
`PointerEvent` already carries every pointer facet in **one
message**: `(x, y, button-mask)`, where a move is a mask-unchanged
event and a press or release is a mask-bit transition at a
position. Key press/release is `KeyEvent` and is delivered
(`rfb.py`, F63). So the carrier seam gains exactly one method:

```text
session.pointer_event(x, y, buttons)
```

This is **D103**'s reasoning applied to the pointer: the key
vocabulary crossing the seam is QEMU's qcode set because the
reference backend's own names are the identity, and here the
reference wire's own event shape is the identity. The VNC carrier
implements it with no translation — the `PointerEvent` the in-tree
client deliberately omitted, its docstring reserving exactly this
arrival ("a message nothing sends is surface pretending to
exist"). The QMP carrier decomposes it into `input-send-event`
`abs`/`btn` sequences — the reduction F5's entry predicted for the
management-interface paths. Clicks, drags, chords, and pacing are
composed **above** this seam by the control plane, never inside an
adapter: the seam stays one method however the surface grows.

## Coordinates are framebuffer pixels

RFB speaks framebuffer coordinates natively; QMP's `abs` axes run
0–32767 and the adapter scales. Click points come from a
landmark's named spot set, whose declaration pins screen
dimensions ([landmarks.md](../../../docs/spec/landmarks.md)) — and since a landmark
match is whole-screen, a dimension mismatch is already a non-match
by construction. No scaling, no second coordinate space, and
nothing for a verb to check that matching has not already checked.

## The device: absolute pointing, declared in the blueprint

The honest fact under all of this: an absolute event needs an
absolute device. A PS/2 mouse is relative, and the guest's own
driver applies acceleration the host cannot observe, so "move to
(x, y)" against one is a guess — **P10** forbids exactly that.

**`pointing-device` is a first-class machine field**, vocabulary
`tablet` / `mouse`, capability-checked per backend the way
`drives` is, resolved into the machine state at creation. **P25**'s
multi-backend gate is cleared on paper: every backend in the
priority order has an absolute device (QEMU `usb-tablet`,
VirtualBox `usbtablet`, VMware's tablet, Hyper-V's synthetic
mouse). `pointing-device` joins `backends.Requirements`, so a
declared `tablet` a backend cannot supply fails assignment closed,
naming both — the drives pattern, nothing new. Today's platforms
default to `mouse` — the stock relative device that is present
anyway, so the default records reality — and GUI-era defaults
arrive with the platform workflows that justify them, the same
arrival rule `control-planes` already states for its own defaults.

- **WEIGHED AND DECLINED — a `backend-settings` pin until a
  second backend delivers pointer input.** A stricter P25 reading
  (capability proven, not cataloged), but it promotes a portable
  need into a backend pin, which `backend-settings` exists to
  avoid; the capability is native vocabulary on all four backends,
  which is what the gate actually asks.

**Pointer verbs preflight-require `tablet`.** A relative-only
machine is a named capability failure before the first input
(P11, G3), never a calibration attempt.

- **WEIGHED AND DECLINED — corner-slam calibration for relative
  mice** (os-autoinst's route: drive the pointer past a corner to
  a known origin, then count relative steps). It works on many
  guests and fails silently on the rest — the miss clicks the
  wrong control, and what it bets on (the guest's acceleration
  settings) is state the host cannot observe. P10 and P11 both
  refuse it: delivery would be a guess wearing a verb.

## Parking rides the same primitive

[landmarks.md](../../../docs/spec/landmarks.md) states the cursor interim and
what replaces it: every
pointer verb ends by parking the cursor at the fixed per-platform
park position, and the park zone is permanently masked from
matching. The park move is simply the last `pointer_event` of the
composed delivery — no new mechanism, and no script surface.

## The verb: `click`, the fifth guest-input verb

The growth rule already promises the shape: "new action kinds use
explicit sibling forms following the same node shape, as future
pointer verbs will" (docs/spec/script-spec.md, "How the vocabulary
grows"). So:

```rlqs
click @welcome-screen
click @component-list spot="continue"
```

`select` is the exact precedent: an **observation-bearing
action**. Its *search* — match the landmark on stability-gated
frames, locate the spot — runs under the statement's effective
`timeout`, resolved by the same lexical rules as any observation;
its *delivery* — the pointer events, then the park move — pays
`pacing` and follows the shared input contract: the verb completes
when the control plane has delivered, claiming nothing about
consumption. Like `select`, it appears twice in the resolved
timing plan and takes its row in the placement matrix. A search
that matches nothing times out visibly — the safe failure
asymmetry landmarks chose (G4): over-matching misses, it never
fires on the wrong screen.

**No `expect=` modifier.** Completion claims belong to the
observation that follows, exactly as `enter`'s do — F5's
act-then-confirm concept is `click` followed by `wait
@next-screen`, which the language already spells; a modifier would
be a second spelling of a `wait` (G6). Screen-stillness is already
the `stability` gate, which the search's frames pass through
without a word written.

**Spot naming: `spot=` modifier, lone-spot default.** A landmark
declaring exactly one spot needs no modifier; more than one makes
`spot=` required, and a `spot=` naming nothing in the declaration
is a static error — the `.rlql` is loaded at preflight, before the
machine starts (G3).

- **WEIGHED AND DECLINED — a dotted reference (`@name.spot`)**:
  compact, but it widens the `@` production of the closed
  reference grammar where a modifier says the same thing with
  grammar the language already has.
- **WEIGHED AND DECLINED — `spot=` always required**: maximally
  explicit, but the common one-button screen would pay a modifier
  that adds no information, and the lone-spot case is decidable
  statically either way.

**First cut: left-single-click only.** `button=`, `count=`, and a
drag verb are additive sibling growth (G7) with no named demand —
F5's own era note has DOS/9x setup keyboard-first where possible
and NT-era setup largely keyboard-drivable, and G6 prefers
deletion. The *seam* already carries them: any mask, any sequence,
so growth never touches an adapter.

- **WEIGHED AND DECLINED — `button=`/`count=` now**: covers more
  installers immediately, but nothing named needs either yet.
- **WEIGHED AND DECLINED — drag in the first cut**: the largest
  surface on the weakest demand, and a drag needs its own
  feedback design (what observation confirms one) before it is a
  verb at all.

## Capability preflight, at the condition's granularity

The growth rule's own words: capability requirements are explicit
and preflightable at the granularity of the condition. A landmark
reference requires framebuffer capture; a `click` additionally
requires pointer input on the selected control plane and
`pointing-device: tablet` on the machine. Each refusal names what
refused it (P11), and all of it is judged before the first guest
input (G3). The seam is plane-neutral — both QEMU planes can
carry `pointer_event` — and which planes advertise the capability
is each plane's own report, never an assumption.

## Proof

Integration, asked for by name as the DOS boots are:

1. a machine with `pointing-device: tablet`, a landmark with two
   named spots, and a script that `click`s each — the guest
   observably acting on both (a menu opening, a button
   depressing), the cursor parked after each, and a capture after
   the park showing no cursor in the match region;
2. `click` on a landmark that never appears — the timeout expiry
   naming the statement's clock and scope, no pointer event
   delivered;
3. preflight refusals by name: a `click` in a script bound to a
   `mouse` machine, a `click` under a control plane without
   pointer input, and a `spot=` naming nothing in the
   declaration — each before the machine starts;
4. the DOS agentless suite untouched — the seam method is new
   surface, and nothing existing moves.

## Out of scope

The recorder (F1, U6); the other backends' VNC endpoints (F5
deliverable 1); Hyper-V's screen strategy; drags, chords,
`button=`/`count=`, and any paced-pointer surface (additive
growth, above); any relative-mouse delivery (declined, above); and
the host-side landmark-cropping convenience, which stays open in
F5's entry where it was raised.
