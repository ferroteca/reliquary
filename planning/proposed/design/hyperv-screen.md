<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# The Hyper-V screen strategy: the one thing existing tools skip

> **Status:** this is the design for the Hyper-V screen strategy
> piece of **F5** (planning/proposed/FEATURES.md, the GUI era's last
> "Decide first" bullet) — owner round, 2026-08-24. **Nothing here is
> pledged.** This design is **a bet, with the test that would prove
> it wrong stated up front** — the same discipline
> [platform-dialect.md](platform-dialect.md) follows. What actually
> settles the question is the spike described below, which has to run
> before F5's Hyper-V work can be pledged, exactly the way an earlier
> spike (spike 0) ran before F64 was pledged. The decisions made
> here, and the alternatives rejected along the way, are recorded in
> place.

## The actual question

F5's bullet asks whether WMI's thumbnail-and-keyboard automation is
good enough to drive an installer, or whether Hyper-V needs the
serial-console and guest-agent control planes from day one. These
two halves of the question aren't equally settled:

- **Sending input is already proven, by existing tools.** Packer's
  Hyper-V builder drives `Msvm_Keyboard.TypeScancodes` from the host
  side, with no guest agent, in production use today.
  The Hyper-V adapter would translate QEMU's qcode key names — the
  seam's own key vocabulary — into Hyper-V's own scancode vocabulary,
  exactly the kind of per-backend translation D103's rule was written
  to handle.
  `Msvm_SyntheticMouse` accepts absolute pointer positions directly,
  which is also what keeps true the P25 claim
  [blueprint-model.md](../../../docs/spec/blueprint-model.md) (F66,
  already delivered) makes about this backend.
- **Reading the screen is the part existing tools skip.** Packer
  types **blind**, timing its keystrokes with no idea what's actually
  on screen — and typing blind is exactly the kind of unjustified
  guess P10 forbids, one the scripting language has no way to even
  express: every pause has to be justified by something Reliquary
  actually observed. So the real open question here is entirely about
  reading the screen. The fact that sending input already works is no
  evidence at all about whether reading the screen will.

## What might carry the screen, and the bet being made on it

`Msvm_VirtualSystemManagementService.GetVirtualSystemThumbnailImage`
returns the console framebuffer as RGB565 pixels, at whatever size is
requested. Two facts decide whether this actually works, and only one
of them is known yet:

- **RGB565's lower color precision is survivable — checked against
  our actual code, not just assumed.** Text recognition first turns
  each screen cell into a plain foreground/background pair before
  comparing them (`text_recognize.py`), so RGB565's reduced 16-bit
  color can't smear a character glyph badly enough to break that
  comparison. Landmark image matching's pixel-equal check *is*
  affected by it, though — the fix for that is the normalization
  described below, not giving up on RGB565.
- **Whether Hyper-V returns the thumbnail scaled or at native
  resolution is the unknown that decides everything.** If it comes
  back at the framebuffer's actual native resolution, 1:1, the
  agentless-display plane works on Hyper-V exactly the way it already
  works on VirtualBox (F51/F52): the same shared recognizer runs over
  the captured frame, `Msvm_Keyboard` sends keys, and
  `Msvm_SyntheticMouse` handles the pointer. But if it only ever comes
  back scaled, the resampling smears each 8×16 character glyph badly
  enough to break the comparison threshold, and this carrier simply
  doesn't work — a screen captured at the wrong resolution is the same
  kind of false reading the earlier spike 0 found when it measured
  memory address `0xb8000`: a reading that looks like it's live and
  actually isn't.

## The decision table, written before anything is measured

| what the spike finds | what the strategy becomes |
|---|---|
| native resolution, unscaled | the agentless-display approach works; F5's Hyper-V work proceeds on it |
| only scaled thumbnails available | the screen carrier is reported as a **missing capability** (P11) — Hyper-V machines refuse any script that watches the screen, by name; the RDP console carrier (the F5 planning document's MS-RDPEPS finding: reached host-side over port 2179, available even before any OS is installed — but it would require vendoring a native FreeRDP stack, the heaviest dependency P21 allows for) gets weighed **at that point**, as its own separate proposal — it is not committed to here |

- **Weighed and declined — committing to the RDP carrier right
  now**: this would mean vendoring the project's heaviest dependency
  before the cheaper carrier above has even been measured.
- **Weighed and declined — using the serial-console and guest-agent
  planes from day one** (the alternative F5's own bullet names): an
  installer can't be driven over a serial console the guest hasn't
  been configured to use yet, and a guest agent only becomes available
  after the very install it would have been driving (following P3's
  usual arc). Those planes will serve Hyper-V machines eventually,
  on their own separate timelines, regardless of what this spike
  finds — but adopting them now is really the "only scaled thumbnails
  available" row wearing a different name: it gives up on installer
  scripting before even measuring the carrier that might make it
  possible.

Either way, the ownership rule holds unchanged: the VM's GUID is the
identity the adapter verifies over WMI before any carrier gets
used — the same `vm.json` identity rule, just applied to a new
management interface.

## Normalizing pixel format: one rule that covers every plane

**Each screen-reading plane states its own capture pixel format as a
capability, and the landmark matcher converts the reference image
through that same format** before running its pixel-equal comparison.
An RGB565 round-trip is deterministic, so "97 of every 100 pixels
identical" still means the same thing after the conversion, and an
asset image captured on QEMU still matches when read back on
Hyper-V. On the VNC plane, the stated format is already the forced
32 bits per pixel, so this conversion is a no-op there and nothing
already delivered changes. This follows the same precedent
[platform-dialect.md](platform-dialect.md) sets for cursor cells: a
difference between backends gets settled once, at the seam between
Reliquary and the backend, not repeated per platform — and not
repeated per asset either.

- **Weighed and declined — requiring lossless screen capture for
  landmark conditions**: this would be honest, and the existing
  per-condition capability system could express it. But it would
  break F5's own goal on this backend — GUI installers are exactly
  the case landmark conditions exist for.
- **Weighed and declined — absorbing the color-precision loss into
  each asset's fuzzy-matching thresholds instead**: this would push a
  plane's own known, predictable quirk onto every single asset's
  threshold tuning — making each blueprint author pay, over and over,
  for something the seam already knows about once.

## The spike that will actually answer this

This runs entirely host-side — nothing needs to run inside the guest,
and no platform workflow is needed — against a Generation 1 guest
booting anything that draws to the screen:

1. Request the thumbnail at the console's native resolution, and
   check whether it lands 1:1 against known character-glyph geometry
   — a VGA text screen's 8×16 cells either land cleanly on cell
   boundaries, or the image was scaled.
2. Measure how long each call takes, against the minimum call rate
   the stability-detection logic needs (roughly 0.17 seconds per
   read) — a carrier too slow to let that logic detect a settled
   screen is a second, independent way this could fail, and it's
   worth checking for up front rather than discovering it late.
3. Drive `Msvm_Keyboard` and read the result back through the same
   carrier — closing that loop once is what "good enough for
   installer scripting" actually means in practice.
4. Confirm `Msvm_SyntheticMouse` accepts absolute pointer positions
   on a machine with no cooperation from the guest.

Whatever the spike finds gets folded back into this document, the
same way an earlier spike (spike 0) was folded into
platform-dialect.md: the losing half of the bet stays in the
document, recording what it used to claim.

## What this document doesn't cover

The RDP carrier's actual design — that only gets weighed if the
spike comes back scaled-only, and it would be its own separate
proposal at that point. The serial-console and guest-agent control
planes — those follow their own separate timelines (F4 and the
guest-communication design). The VMware adapter — F5's own ordering
puts Hyper-V last. And everything the other three F5 design documents
already cover on their own.
