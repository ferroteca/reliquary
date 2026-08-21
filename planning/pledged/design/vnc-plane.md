<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# The VNC control plane

> **Status:** design for **F63** ([../FEATURES.md](../FEATURES.md))
> — the VNC control plane on QEMU, screen and keyboard. Serves
> **U5** ([../USE-CASES.md](../USE-CASES.md)). The demand
> adjudication and the cut that produced F63 are **D110**; the GUI
> era's remaining design — pointer input, landmarks, the other
> backends' endpoints — stays with F5 in
> [../../proposed/FEATURES.md](../../proposed/FEATURES.md). The
> control-plane doctrine this composes under is
> [../../design/guest-communication.md](../../design/guest-communication.md);
> the carrier seam and the snapshot contract are
> [../../design/backend-adapter.md](../../design/backend-adapter.md).

## What the plane is

A second agentless display plane: framebuffer output and key input
over the RFB protocol, against the VNC server the backend itself
serves. Nothing exists in the guest for it (P2) and nothing is
inferred from one (P10) — the guest paints, the server hands the
client the pixels, and what a screen *says* is read by the shared
fixed-font recognizer exactly as the VirtualBox display plane reads
a screenshot. The plane is backend-neutral by design — VirtualBox
(extension pack) and VMware Workstation serve the same wire — and
F63 wires it on QEMU alone, where `-vnc` is native and the
integration oracle (the FreeDOS install, and the VGA scrape to
compare against) already runs.

## The wire (adjudicated 2026-08-21)

**An in-tree minimal RFB client, no new dependency.** Weighed and
declined: `vncdotool` (drags in Twisted for a protocol subset we
control both ends of) and `asyncvnc` (an asyncio surface and a thin
ecosystem for the same subset). The subset is pinned *because*
Reliquary launches the server it connects to:

- the RFB 3.8 version handshake;
- security type 1 (None) — the endpoint ruling below;
- `SetPixelFormat` forcing 32bpp true-colour, so the framebuffer
  has exactly one in-memory shape;
- `FramebufferUpdateRequest`, full and incremental, with **Raw
  encoding only** — the client advertises nothing else, and Raw is
  the encoding every server must be able to fall back to;
- `KeyEvent`. `PointerEvent` is deliberately absent: it arrives
  with the pointer-input feature still in F5, and a message nothing
  sends is surface pretending to exist.

Throughout, os-autoinst remains a concept reference only — designs
studied, code never read (AGENTS.md prior art).

## The endpoint (adjudicated 2026-08-21)

**Loopback, no VNC auth.** The adapter launches
`-vnc 127.0.0.1:<display>` with a display number allocated the way
the QMP port is, and records the endpoint in the identity's
adapter-shaped `endpoint` beside it, atomically with `phase` as
ever. Weighed and declined: a per-start password via
`set_password` — VNC auth is single-DES, security theater on
loopback, and the threat it would answer (another local process
racing the port) is what the identity verification below detects;
the password would be one more secret with custody rules for no
gain.

**Identity is QMP's job and stays there.** RFB carries no machine
identity, so the VM-ownership rule is satisfied the way it always
is — `query-name` and `query-uuid` over the identity-verified QMP
session — before the RFB connection is used, with `query-vnc`
cross-checking that the recorded endpoint is the one this QEMU
serves. A VNC connection never authorizes a command; it is a
carrier reached only after the machine behind it is verified.

## Selection (adjudicated 2026-08-21)

**The declared `control-planes` list is an ordered preference.**
The requirement semantics are unchanged: every declared plane must
appear in the assigned backend's capability report, failing closed
naming the plane and the backend (P11). What is new is that the
**first** entry drives the run — the session's carriers are the
first declared plane's — so `["vnc"]` selects VNC and the default
policy stays `["agentless-display"]`, nothing moving for existing
blueprints. This is the ordered-policy intent
guest-communication.md already states, made real at the size F63
needs. Order becoming meaningful is a blueprint-surface change
(S4) and lands in `docs/spec/blueprint-model.md` with the
delivery. Weighed and declined: refusing more than one declared
plane until a readiness waterfall exists — a vocabulary
restriction that would take a second surface change to lift, for
no protection the capability check does not already give.

## The carriers

Behind the same carrier seam the agentless plane serves, so
everything above it — `control_display`, `screen_stability`, the
runner, the transcript wrapper — is untouched by construction:

- **`text_screen`** — the shared recognizer over the framebuffer:
  `text_recognize.recognize` with `guest_glyph_banks(cache)`,
  returning the `(text_rows, attribute_rows)` contract whole,
  `attribute_token` tokens included. This is the composition F51 /
  F52 built for the VirtualBox display plane, running over an RFB
  framebuffer instead of a VBoxManage screenshot — one algorithm,
  never a per-plane reimplementation.
- **`screenshot`** — the framebuffer rendered out through pillow.
- **`send_keys`** — the seam speaks QEMU qcodes (D103's middle
  layer); the plane owns the third layer, a qcode → X11 keysym
  table, exactly as VirtualBox owns `scancodes_for`.
- **`change_medium` stays on QMP.** Media movement is a machine
  operation, not a display one; it rides the management interface
  whatever plane drives the screen, and the recording wrapper
  keeps watching the one call it always watched.

## Readiness

The two lifecycle phases guest-communication.md gives every plane:
the adapter contributes the validated `-vnc` argument before the
machine starts, and the session connects and completes the
handshake after it. The probe — TCP connect plus the version and
security handshake — is bounded by the startup deadline like every
other probe, and a failure names the endpoint it could not reach
(P11).

## Testing

- **Unit tier, no hypervisor:** a fake RFB server at the socket
  seam exercises the client (handshake, pixel-format force, Raw
  updates, key events); golden framebuffers through the shipped
  fallback font exercise the recognition composition; the adapters'
  parametrised seam contract gains the plane's carriers.
- **Integration tier — the done-when:** the FreeDOS install script
  runs unmodified on QEMU with `control-planes: ["vnc"]`, and the
  recognizer's reading matches the VGA scrape on the same screens.
