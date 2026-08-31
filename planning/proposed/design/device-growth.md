<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Blueprint device growth: five items checked against one rule

> **Status:** this is the design for the blueprint-device-growth
> piece of **F5** (planning/proposed/FEATURES.md, the GUI era's
> "Decide first" bullet) — owner round, 2026-08-24. **Nothing here
> is pledged, and this document adds no new blueprint vocabulary**:
> every item below either puts off adding a field or refuses to add
> one at all. If a field does get added later, it still has to go
> through the surface-change rule ([../../SURFACES.md](../../SURFACES.md))
> at that later point. The decisions made here, and the alternatives
> rejected along the way, are written down in place — the same way
> the other F5 design documents record theirs.

## The same rule, checked twice for each item

**P25** says: a name only enters the portable blueprint spec once
more than one backend can actually honor it, and **there being
demand for it is necessary but never sufficient on its own**. So
every candidate device or field in this document gets checked
against two separate questions: does anything actually demand it,
and does it work the same way across backends? The dispositions
below differ from each other because different candidates fail
*different* one of those two checks. That's the actual finding here
— "not added yet" isn't one argument repeated five times, it's four
different arguments.

## Network: real demand exists, but it isn't a machine-shape question

> **Superseded (D120/D121/D122, 2026-08-29).** Real demand for a
> first-class network field showed up (owner, U28) — for choosing
> whether a NIC is host-only or reaches the wider network. `net`
> slots (`net0`, `net1`, …) are now first-class vocabulary, closed to
> the attachment `nat`/`bridged`, exactly the shape this section
> originally called for ("its cross-backend vocabulary should
> describe *attachment* ... never specific card names") — landed
> first as its own `network` field (D120), then folded into the same
> `devices` map drives already live in, hours later (D121). This
> section's flat claim that the chipset should *never* be named did
> not hold, though: DOS-era networking software is often written
> against one specific chipset, and the platform default isn't always
> it, so `model` became an optional override the same day (D122),
> checked per backend the same way `controller`'s `nvme`/`virtio`
> already are. The chipset still defaults per platform when
> unstated — this section's reasoning about the *default* was right,
> its reasoning about there being no *override* wasn't.

This is the one item here with demand that's already been delivered.
The script's `http` block (docs/spec/http-serve.md) declares that the
guest needs to reach the host, and today QEMU satisfies that with
user-mode NAT as **a temporary default that the spec itself says will
be replaced**: docs/spec/http-serve.md already states this is a
temporary default for the QEMU backend, not a network device model
defined on the blueprint, and that a later milestone — one that adds
more backend adapters and richer device modeling — will own portable
network devices. This document is that later milestone. The spec also
already says where the need actually lives: serving answer files is a
run behavior, not machine shape.

This design keeps that same shape and extends it to every backend:

- **Host-reachability becomes a capability derived from what the
  script declares it needs**, not a blueprint field. A run whose
  script declares `http` needs a guest-to-host path. Each backend
  adapter satisfies that with its own NAT device — QEMU's user-mode
  networking, VirtualBox NAT, VMware NAT, Hyper-V's default switch —
  and a backend that can't provide one fails as a named capability
  failure before the run even starts (P11). That's exactly what the
  spec's existing promise — that the capability check fails when a
  platform has no supported network path yet — already commits to.
- **The specific network card model joins the per-platform defaults
  table**, the same table platform memory defaults already live in.
  The spec calls for an emulated network card appropriate to the
  platform — which card is appropriate is a fact about the platform
  (which drivers that era of guest actually has), translated per
  backend the same way every other capability is. It never becomes
  something a blueprint names directly.
- **A first-class `network` field in the blueprint waits until there's
  demand that's actually about machine shape** — something like a
  guest-reachable service, or guest internet access. Nothing names
  either of those today. If that field does eventually get added, its
  cross-backend vocabulary should describe *attachment* (`none` /
  `nat`), never specific card names — which card is used stays owned
  by the platform table and the backends, not the blueprint.

- **Weighed and declined — adding `network: none|nat` right now**:
  this would satisfy the "works the same across backends" half of
  P25's rule, but the existing http path already works without it,
  and P25 requires actual demand too, which doesn't exist yet.
- **Weighed and declined — leaving the QEMU-only default as it is**:
  the cheapest option, but it would leave the spec's own promise —
  that this gets addressed by a later milestone — unanswered by the
  very milestone it pointed to.

## Firmware: works the same across backends, but nothing needs it yet

All four backends can do UEFI: QEMU with OVMF, VirtualBox with its
EFI firmware, VMware with `firmware=efi`, Hyper-V with Generation 2.
But every platform Reliquary's model currently has — dos, win9x,
winnt, openbsd — boots BIOS, and F5's own platforms are all BIOS-era.
So this field is **designed here, but not actually added yet**: it
gets added once the first platform that needs `uefi` shows up. A
field nothing can meaningfully set yet would just be surface area
that exists for no reason.

Here's the shape it's designed to take, so adding it later is a
purely mechanical step:

- **`firmware: "bios" | "uefi"`**, defaulting to whatever the
  platform's own default is when left unset — `bios` for every
  platform today. A platform with a different default arrives only
  once a platform that actually justifies it exists — the same rule
  `control-planes` and `pointing-device` already follow when they
  grow new values. Each backend checks this field the normal way:
  `firmware` joins `backends.Requirements` once this is actually
  added.
- **UEFI implies a per-machine NVRAM variable store.** It gets
  created at materialization time from the backend's own template,
  lives inside the machine's backend directory, and persists across
  stop/start — because UEFI boot entries are part of the machine's
  state, not something regenerated fresh each time. It's destroyed
  along with the machine, and it never lives under `cache/media`,
  because it's machine identity, not a regenerable payload.
- **Boot-order behavior doesn't change.** The boot order is stated to
  the firmware, the same exception that already works today. A
  backend that can't state a UEFI boot order fails as a named
  capability failure — it never silently reorders things instead.

- **Weighed and declined — adding the field now, defaulting to
  `bios`**: this would save a small amount of work later, but it
  would add blueprint vocabulary whose only non-default value is
  currently refused or untested on every platform that exists.

## Display adapter: backends don't agree on this, so it stays per-backend

Every backend ships its own emulated graphics card — QEMU's `std` or
`cirrus`, VirtualBox's own SVGA card, VMware's own, Hyper-V's own —
so there's no vocabulary here that could work the same way across
backends, no matter how much demand exists for it. What the GUI era
actually needs — a display mode the screen recognizer can read — is
a question about capability, not about which specific device is
attached. Disposition: this stays per-backend, configured through
`backend-settings`, permanently, per P25. This is exactly the kind of
case P25 exists to refuse, and it doesn't need a clause saying when
to revisit it: a shared vocabulary here would require every backend
to converge on emulating identical hardware, and that's not something
this project is waiting around for.

## Audio: nothing needs it, so it stays out

No installer needs sound, and nothing names a need for it. It stays
configured through `backend-settings` until both demand exists *and*
a vocabulary exists that works the same way across backends. Unlike
the display adapter above, the cross-backend half of this is actually
fine — SB16-era sound emulation is common across backends — so audio
is only being refused because of missing demand, and a real use case
showing up would reopen the question. No one is watching for that to
happen, though: the use case arriving *is* what would prompt someone
to notice.

## USB: comes from whatever device needs it, never its own field

`devices.pointer0: emulated-tablet`
([blueprint-model.md](../../../docs/spec/blueprint-model.md), F66,
already delivered, moved into `devices` by D124, renamed by D126,
split from `virtual-tablet` by D127) is the actual demand here, and a
backend adapter
that renders the tablet renders its USB controller automatically,
without being asked separately. A bare `usb: true` field would just
declare a controller with nothing plugged into it — machine shape
with nothing that actually uses it. **The rule here, stated once
because it'll come up again**: a USB *device* gets added following
the model's own existing growth rule (ARCHITECTURE.md, standing
constraints — new kinds of media, controllers, and USB devices must
all extend the same medium-naming convention, rather than showing up
as opaque raw arguments passed straight to a backend), and the
controller itself is always just implied by whatever devices need
it.

## Controller defaults and slot ranges: writing down rules, not changing anything today

The parser's controller vocabulary is already the model's complete
set (`ide`, `sata`, `scsi`, `nvme`, `virtio`), with each backend
reporting which of them it actually honors — the same pattern
`control-planes` already uses, already in force today. What this
document adds is two rules for how that grows over time:

- **The controller default becomes per-(platform, medium), living in
  the platform table** — `ide` for every current platform, so nothing
  actually changes today. A platform whose default should be
  something other than `ide` gets added only once that platform
  exists to justify it, following the same arrival rule as above.
- **Slot ranges widen per controller type, exactly when that
  controller type gets added** — purely additive, the way F5's own
  entry already describes. Uniqueness is still tracked by slot, and
  whichever round adds a new controller type owns working out that
  type's own slot arithmetic.
- **The existing rule doesn't change**: which disk a guest sees first
  is never something a declaration can state directly (P10), and boot
  order stays the one stated exception — it's declared to the
  firmware, never read back out of it.

## Hyper-V generation: computed, never its own setting

Which Hyper-V generation a machine gets is computed from the
`firmware` field once it exists: `bios` means Generation 1, `uefi`
means Generation 2 — which today, since every platform is still
BIOS-only, means **it's always Generation 1**. Generation 2's
restrictions (no floppy, no IDE) become ordinary capability-check
arithmetic once that time comes: asking for `uefi` plus a floppy
drive on Hyper-V becomes a named refusal, never something Reliquary
silently works around.

- **Weighed and declined — a separate
  `backend-settings.hyperv.generation` setting**: this would create
  two different sources of truth for the same fact once `firmware`
  exists, which is exactly the overlap the `backend-settings` rules
  forbid (a `backend-settings` section may not touch anything
  Reliquary itself already owns). And until `firmware` exists, it
  would just be a knob letting someone pick between two states only
  one of which actually works.

## What this design actually delivers

Deliberately, nothing yet. What this round produces is the set of
decisions and the shapes they'll take, so that adding any one of them
later is a small, mechanical step that cites this document, rather
than requiring a fresh argument each time. The one exception —
something that actually changes shipped behavior — is extending
host-reachability beyond QEMU: that lands as each backend gains `http`
support, using the same capability-check approach this document
confirms, and it amends the temporary QEMU-only clause in
docs/spec/http-serve.md as part of that same change.
