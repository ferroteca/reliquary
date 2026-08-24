<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Blueprint device growth: five items under one gate

> **Status:** the design for **F5**'s blueprint-device-growth
> piece (planning/proposed/FEATURES.md, the GUI era's "Decide
> first" bullet) — owner round, 2026-08-24. **Nothing here is
> pledged**, and this document **admits no vocabulary**: every
> disposition below either defers admission or refuses it, and a
> field arriving later still takes the surface-change rule
> ([../SURFACES.md](../SURFACES.md)) at its own admission. The
> adjudicated calls and their rejected alternatives are recorded
> in place, the way the other F5 designs record theirs.

## The gate, applied twice per item

**P25**: a name enters the portable spec when more than one
backend can honor it, and **demand is necessary and never
sufficient**. So every candidate here answers two questions —
does any demand name it, and does it apply across backends — and
the dispositions below differ because they fail *different*
gates. That difference is the finding: "not admitted" is four
distinct arguments, not one.

## Network: live demand, and it is not blueprint-shaped

The one item with delivered demand. The script `http` block
(docs/spec/http-serve.md) declares that the guest must reach the
host, QEMU satisfies it with user-mode NAT as **an interim
backend default the norm itself defers** — "not a first-class
blueprint NIC model; a later milestone that grows backend
adapters and richer device modeling owns portable network
devices" — and that later milestone's round is this one. The norm
also already states where the need lives: "serving answer files
is a run behavior, not machine shape."

The disposition keeps that shape and generalizes it:

- **Host-reachability is a capability derived from the script's
  declared need.** A run whose script declares `http` requires a
  guest-to-host path; each adapter satisfies it with its own NAT
  device — QEMU user-mode, VirtualBox NAT, VMware NAT, Hyper-V's
  default switch — and an adapter that cannot is a named
  capability failure before the run (P11), which is what the
  interim's "if a platform has no supported network path yet, the
  capability check fails" clause already promises.
- **The NIC model joins the per-platform defaults table.** The
  norm asks for "an emulated NIC appropriate for the platform";
  that is a platform fact (what the era's guests hold drivers
  for), owned where memory defaults live and translated per
  backend like every capability. It is never blueprint
  vocabulary.
- **A first-class `network` field waits for machine-shaped
  demand** — a guest-reachable service, guest internet access;
  nothing names either today. When it arrives, its agnostic
  vocabulary is *attachment* (`none` / `nat`), never card names:
  cards are what the platform table and the backends own.

- **WEIGHED AND DECLINED — admitting `network: none|nat` now**:
  clears P25's applicability half, but the delivered http path
  works without it and demand is necessary.
- **WEIGHED AND DECLINED — leaving the QEMU interim as is**:
  cheapest, but it leaves the norm's own deferral unanswered by
  the round it pointed at.

## Firmware: applicability clears, demand is absent

All four backends do UEFI (OVMF, VirtualBox EFI, VMware
`firmware=efi`, Hyper-V Gen2). Every platform in the model —
dos, win9x, winnt, openbsd — boots BIOS, and F5's own platforms
are BIOS-era. So the field is **designed here and not
admitted**: it arrives with the first platform that needs
`uefi`, and a field nothing can meaningfully write until then is
surface pretending to exist.

The settled shape, so that arrival is mechanical:

- **`firmware: "bios" | "uefi"`**, omitted resolving to the
  platform's default — `bios` for every platform today, defaults
  that differ arriving with the platforms that justify them (the
  arrival rule `control-planes` and `pointing-device` already
  use). Capability-checked per backend: `firmware` joins
  `backends.Requirements` at admission.
- **UEFI implies a per-machine NVRAM varstore**: created at
  materialization from the backend's template, living under the
  machine's backend dir, persisting across stop/start — boot
  entries are machine state — and destroyed with the machine.
  Never under `cache/media`: it is machine identity, not
  regenerable payload.
- **Boot-order semantics unchanged**: the order is stated to the
  firmware, the exception that already works; a backend that
  cannot state UEFI boot order is a named capability failure,
  never a silent reordering.

- **WEIGHED AND DECLINED — admitting the field now, default
  `bios`**: saves a later act, but admits vocabulary whose only
  non-default value is refused or untested on every current
  platform.

## Display adapter: fails the applicability gate

Each backend ships its own emulated card — QEMU `std`/`cirrus`,
VirtualBox its SVGA, VMware its own, Hyper-V its own — so there
is no portable vocabulary to admit, whatever the demand. What
the GUI era actually needs — a mode the recognizer reads — is a
capability question, not a device name. Disposition: per-backend
behind `backend-settings`, permanently, citing P25. This is the
refusal P25 was written for, and it needs no re-examination
clause: a portable card vocabulary would require the backends to
converge on emulating the same hardware, which is not a thing
this project waits on.

## Audio: fails the demand gate

No installer needs sound; nothing names it. `backend-settings`,
until demand exists *and* a portable vocabulary does. Unlike the
display adapter, the applicability half is open (SB16-era
emulation is common across backends), so audio's refusal is
demand-shaped and would re-open on a use case — but no watch is
kept: the use case arriving is the watch.

## USB: implied by the device that needs it, never a field

`pointing-device: tablet`
([pointer-input.md](pointer-input.md)) is the demand, and an
adapter that renders the tablet renders its USB controller
unasked. A bare `usb: true` would declare a controller with
nothing on it — machine shape with no consumer. **The rule,
stated once because it recurs**: a USB *device* arrives under
the model's own growth rule (ARCHITECTURE.md, standing
constraints — "new media kinds, controllers, and USB devices
must extend the same convention, a new medium name"), and the
controller is always implied by its devices.

## Controller defaults and slot ranges: rules, not changes

The parser's controller vocabulary is already the model's whole
set (`ide`, `sata`, `scsi`, `nvme`, `virtio`) with backends
reporting what they honor — the `control-planes` pattern, in
force today. What this round adds is the two growth rules:

- **The controller default becomes per-(platform, medium) in the
  platform table** — `ide` for every current platform, so
  nothing changes today; a non-`ide` default arrives with the
  platform that justifies it, by the arrival rule.
- **Slot ranges widen per controller type at that type's
  admission**, additive as F5's entry already holds; uniqueness
  stays by slot, and the admitting round owns the arithmetic of
  the type it admits.
- **The recorded constraint stands untouched**: which disk a
  guest sees first is a fact no declaration supplies (P10), and
  boot order remains the stated exception — declared to the
  firmware, never read back from it.

## Hyper-V generation: derived, never a knob

Generation is a function of declared capability: `bios` → Gen1,
`uefi` → Gen2 — which today, with every platform BIOS, means
**always Gen1**. Gen2's constraints (no floppy, no IDE) are
ordinary `unmet()` arithmetic when the time comes: `uefi` plus a
floppy on Hyper-V is a named refusal, never a silent adjustment.

- **WEIGHED AND DECLINED — a `backend-settings.hyperv.generation`
  pin**: two sources for one fact once `firmware` exists —
  exactly the overlap the `backend-settings` rules forbid ("a
  section may not touch what Reliquary owns") — and until then a
  knob choosing between states only one of which works.

## What this design delivers

Nothing, deliberately: the round's product is the dispositions
and the shapes, so that each later admission is a small act
citing this document rather than a fresh argument. The one
delivered-surface consequence — generalizing http
host-reachability beyond QEMU — lands with the backends that
gain http support, under the capability seam this document
confirms, and amends docs/spec/http-serve.md's interim clause in
the same act.
