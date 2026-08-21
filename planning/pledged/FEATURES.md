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

## F63 — The VNC control plane on QEMU: screen and keyboard

> **Pledged 2026-08-21** (owner), cut out of **F5** — which keeps
> its number and the remainder — in the act that pledged **U5**,
> closing the demand adjudication F5's banner left open; the
> adjudication and the cut ruling are **D110**. Serves **U5**.
> **U6**'s recorder (F1) names this plane as its prerequisite
> without being demand for it (D61). Design:
> [design/vnc-plane.md](design/vnc-plane.md), which carries the
> three adjudicated calls — the in-tree RFB client, the
> loopback-no-auth endpoint with QMP-verified identity, and the
> declared plane list as an ordered preference. Runs under **P2**
> — the plane needs nothing in the guest — with the VM-ownership
> rule binding it like every carrier, and **P11** naming what a
> backend cannot honor.

A second agentless display plane: framebuffer output and key input
over RFB, against the VNC server the backend itself serves —
`control-planes: ["vnc"]` honored end to end on QEMU, where today
it correctly fails assignment closed because no adapter claims it.
Text observation is the shared fixed-font recognizer over the
framebuffer, the composition F51 / F52 built, so everything above
the carrier seam is untouched by construction.

Work items:

1. The RFB client module, in-tree and minimal: the 3.8 handshake,
   security None, `SetPixelFormat` forcing 32bpp, Raw-only
   framebuffer updates (full and incremental), `KeyEvent` — no
   `PointerEvent` until the pointer feature pledges.
2. The QEMU launch contribution: `-vnc 127.0.0.1:<display>` with an
   allocated display when the resolved policy names the plane, the
   endpoint recorded in the identity beside the QMP port, and the
   bounded readiness probe; `query-vnc` cross-checks the endpoint
   after the ordinary QMP identity verification.
3. Capability and selection: the QEMU report claims `vnc`, and the
   declared `control-planes` list becomes an ordered preference —
   every entry must be capable (unchanged), the first drives the
   session's carriers; the default stays `["agentless-display"]`.
4. The carriers behind the existing seam: `text_screen` via
   `text_recognize.recognize` with `guest_glyph_banks`,
   `screenshot` from the framebuffer, `send_keys` through a qcode →
   X11 keysym table (D103's adapter-side layer); `change_medium`
   stays on QMP.
5. Tests: a fake RFB server at the socket seam and golden-frame
   recognition in the unit tier; the adapters' seam contract gains
   the plane; the integration tier runs the done-when.
6. Documentation: the ordered-preference semantics in
   `docs/spec/blueprint-model.md` (S4 lands coherently), the plane
   in the blueprint reference and guide, and the CHANGELOG.

Done when: the FreeDOS install script runs unmodified on QEMU with
`control-planes: ["vnc"]`, the recognizer's reading matching the
VGA scrape on the same screens.
