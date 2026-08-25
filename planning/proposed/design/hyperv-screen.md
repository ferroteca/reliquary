<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# The Hyper-V screen strategy: the half prior art avoids

> **Status:** the design for **F5**'s Hyper-V screen strategy
> (planning/proposed/FEATURES.md, the GUI era's last "Decide
> first" bullet) — owner round, 2026-08-24. **Nothing here is
> pledged.** The design is a **bet with its refutation stated**,
> the [platform-dialect.md](platform-dialect.md) discipline: what
> decides it is the spike below, which precedes any pledge of F5's
> Hyper-V deliverable exactly as spike 0 preceded F64's. The
> adjudicated calls and their rejected alternatives are recorded
> in place.

## The question, sharpened

F5's bullet asks whether WMI thumbnail/keyboard automation is
good enough for installer scripting, or whether Hyper-V needs the
serial/agent planes from day one. The halves are not equally
open:

- **Input is proven prior art.** Packer's hyperv builder drives
  `Msvm_Keyboard.TypeScancodes` host-side, agentlessly, in
  production. The adapter translates the qcode seam onto its own
  scancode vocabulary, which is D103's rule doing what it was
  written for. `Msvm_SyntheticMouse` answers absolutely, which is
  also what keeps
  [blueprint-model.md](../../../docs/spec/blueprint-model.md)'s
  (F66, delivered) P25 claim true on this backend.
- **The screen is the half prior art avoids.** Packer types
  **blind**, on timing alone — and blind typing is the guess P10
  forbids and the language cannot express: every pause must be
  justified by an observation. So the strategy question is solely
  about the screen carrier, and "input works" is no evidence for
  it.

## The carrier, and the bet

`Msvm_VirtualSystemManagementService.GetVirtualSystemThumbnailImage`
returns the console framebuffer as RGB565 at a requested size.
Two facts decide everything, and only one is known:

- **RGB565 quantization is survivable — measured against our own
  code, not assumed.** Text recognition binarizes each cell into
  a foreground/background pair before the Hamming comparison
  (`text_recognize.py`), so 16-bit color cannot smear a glyph.
  Landmarks' pixel-equal metric *is* affected, and the answer is
  the normalization below, not a refusal.
- **Scaling is the unknown that decides the strategy.** At the
  framebuffer's native resolution, 1:1, the agentless-display
  plane composes on Hyper-V exactly as it composed on VirtualBox
  (F51/F52): the shared recognizer over the captured frame,
  `Msvm_Keyboard` for keys, `Msvm_SyntheticMouse` for the
  pointer. Scaled-only, resampled 8×16 glyphs smear past the
  Hamming threshold and the carrier does not exist — a screen
  captured at the wrong geometry is the same class of blindness
  spike 0 measured at `0xb8000`: a reading that looks live and is
  not.

## The decision table, stated before measurement

| the spike finds | the strategy is |
|---|---|
| native-res, unscaled | the agentless-display composition delivers; F5's Hyper-V deliverable proceeds on it |
| scaled-only | the screen carrier is a **reported capability absence** (P11) — Hyper-V machines refuse screen-watching scripts by name; the RDP console carrier (the F5 banner's MS-RDPEPS finding: host-side, port 2179, the console before any OS exists — but a vendored native FreeRDP stack, P21's heaviest ask) is weighed **then**, as its own proposal, never pre-committed here |

- **WEIGHED AND DECLINED — committing to the RDP carrier now**:
  it vendors the project's heaviest dependency before the cheaper
  carrier has even been measured.
- **WEIGHED AND DECLINED — serial/agent planes from day one**
  (the bullet's stated alternative): an installer cannot be
  driven over a serial console the guest has not configured, and
  the agent arrives only after the install it would have driven
  (P3's arc). Those planes serve Hyper-V machines on their own
  arcs whatever the spike finds — the alternative is really the
  scaled-only row wearing a different name, and it concedes
  installer scripting before measuring the carrier that might
  serve it.

Either way the ownership doctrine holds unchanged: the VM's GUID
is the identity the adapter verifies over WMI before any carrier
is used, the vm.json rule applied to a new management interface.

## The normalization: one rule for every plane

**The plane states its capture pixel format as a capability, and
the landmark matcher normalizes the reference side through it**
before the pixel-equal comparison — an RGB565 round-trip is
deterministic, so "97 of every 100 pixels identical" keeps its
meaning and an asset captured on QEMU still matches on Hyper-V.
On the VNC plane the stated format is the forced 32bpp, so the
normalization is the identity and nothing delivered moves. This
is the cursor-cell precedent
([platform-dialect.md](platform-dialect.md)): a plane difference
settled once at the seam, not per platform — and not per asset.

- **WEIGHED AND DECLINED — requiring lossless capture for
  landmark conditions**: honest, and capability-at-condition-
  granularity could express it, but it guts F5's own goal on this
  backend — GUI installers are exactly the landmark case.
- **WEIGHED AND DECLINED — absorbing the quantization in fuzzy
  regions**: it moves a plane's known, deterministic artifact
  into every asset's thresholds, which is the author paying for
  what the seam knows.

## The spike

Host-side only, nothing in-guest, no platform workflow needed —
a Gen1 guest booting anything that paints:

1. request the thumbnail at the console's native resolution and
   test 1:1 against known glyph geometry — a VGA text screen's
   8×16 cells either land on cell boundaries or the carrier
   scaled;
2. measure call latency against the stability gate's minimum
   viable cadence (~0.17s per read) — a carrier too slow to
   establish quiescence is a second way to fail, stated rather
   than discovered late;
3. drive `Msvm_Keyboard` and read the effect back through the
   same carrier — the loop closed once, which is what "good
   enough for installer scripting" actually means;
4. confirm `Msvm_SyntheticMouse` accepts absolute positioning on
   a machine with no guest cooperation.

What the spike returns is folded into this document the way spike
0 was folded into platform-dialect.md — the refuted half kept,
saying what it used to claim.

## Out of scope

The RDP carrier's design (weighed only at the scaled-only
outcome, as its own proposal); the serial and agent control
planes (their own arcs — F4 and the guest-communication
doctrine); the VMware adapter (F5's own sequencing keeps Hyper-V
last); and everything the other three F5 designs already own.
