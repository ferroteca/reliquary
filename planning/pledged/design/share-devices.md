<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# `share` devices: a host directory shared into the guest

> **Status:** design from two owner rounds, 2026-08-29 — the second
> folded the existing vvfat directory-drive into this same device
> kind — **pledged the same day as F68–F71**
> ([../FEATURES.md](../FEATURES.md), which carries the work lists;
> the split follows the sprint-size rule). This document adds no
> blueprint vocabulary by itself: the vocabulary lands as those
> features are delivered, under the surface-change rule
> ([../../SURFACES.md](../../SURFACES.md)). It follows the same
> two-question method as
> [device-growth.md](../../proposed/design/device-growth.md): is
> there actual demand, and does the capability work across more than
> one backend (P25)? This candidate passes both, which is why this
> document designs a field instead of declining one.

## The need

Files have to cross the guest/host boundary — that is the purpose,
and it is the salient identity here (owner, this round): however
the mechanism manifests, what the author is declaring is *these
files are visible on both sides*. Reliquary serves that purpose two
ways today, each with a hard limit:

- **A directory-source drive** (a media whose `location` is a host
  directory, rendered as vvfat on QEMU —
  [media-spec.md](../../../docs/spec/media-spec.md)) needs no guest
  driver at all, but the guest's view of it is assembled when the
  machine starts: host-side edits made while the machine runs are
  invisible to the guest, and guest writes only surface on the host
  once the machine stops.
- **A live media swap** (`insert-media`, U20) is genuinely live, but
  moves a whole image at a time, bounded by the medium's size, with
  the caller rebuilding the image between rounds.

What neither gives is **per-file, both-directions visibility while
the machine runs** — the host writes a file and the guest sees it
without a restart; the guest writes a file and the host reads it
without a stop. That's what a shared filesystem protocol does, and
it's the exchange shape U14's tight loop ("puts input into the
guest, runs the work, reads the results back, repeats") still has
to approximate today with image swaps or stop/start cycles.

The demand is concrete, not speculative: the owner's own virtio-dos
project ships working DOS guest drivers for exactly this — `VIO9P`
(virtio-9p) and `VIOFS` (virtio-fs/FUSE), both verified against
real devices — and its integration suites already serve host
directories into Reliquary-provisioned FreeDOS guests by
hand-building the QEMU arguments. The guest half exists and is
tested; what's missing is the blueprint being able to declare the
device half.

This design gives the purpose one device kind. The live protocols
are its new capability, and the existing directory-drive folds in
as one of its models rather than surviving as a sibling spelling
(the argument is recorded in its own section below).

## What a share is

A **`share`** is a new device kind in the `devices` map, a sibling
of drives and NICs under D121's one-inventory rule: slot keys
`share0`, `share1`, … following the same `<medium><slot>` grammar
and the same single clash check. Its portable meaning: *this host
directory is presented to the guest for file exchange, for as long
as the machine runs*. When changes become visible on each side is
part of each model's documented contract — the same way
`materialize`'s values already carry different write-back contracts
(`copy` never reaches the source, `use` does) — and every model a
backend defaults to is fully live, in both directions. The one
snapshot-semantics model, `vvfat`, arrives only by name, never as a
default.

The value reuses the directory-source media grammar unchanged — a
share points at a media whose `location` resolves to a host
directory. The media layer keeps carrying the payload ("a host
directory is a payload shape, not a mode", media-spec.md); what
changes is that exactly one device kind now accepts that shape:

- **Value forms**: a media name, an inline media definition, or an
  object naming `media` plus share-specific keys (`model`,
  `enabled`) — the same shapes a drive value takes, minus `null`
  (an empty drive bay is real hardware; a share with no directory
  means nothing).
- **Directory payloads are legal only on share slots.** A drive
  slot whose media resolves to a directory fails closed at
  resolution — today it silently switches the drive into vvfat, a
  render-time `isdir` check — and a share whose media resolves to
  a file fails closed naming the path. The old per-medium
  carve-outs (a directory rejected on a cdrom slot) dissolve into
  this one rule.
- **`materialize` must be `use`.** A share serves the directory in
  place. `read-only` stays a media field, as today, and maps onto
  each mechanism's own read-only option.
- **A `${key}` location works for free** (U21): the directory is a
  media `location`, so it binds through the same property chain a
  media path already does — right for a share, since a host
  directory path is exactly the kind of fact that shouldn't be
  hardcoded into a blueprint meant to be shared (the same argument
  D120 made for `interface`).
- **The slot key names the device on every mechanism**: the 9p
  `mount_tag`, the virtio-fs tag, the VirtualBox share name, and
  the vvfat drive's launch id. One rule, no per-backend naming
  field.
- **Share keys are refused in `boot`**, like `net` keys, and
  `insert-media` / `eject-media` / `set-boot-order` and the
  script's `with boot` / `insert` / `eject` don't apply — those are
  drive-only by shape, exactly as D121 already has each of them
  check. What the fold retires from the old drive spelling is
  covered below.

## The mechanism is the backend's business, with one authored override

Each backend serves a share with its own mechanisms:

- **QEMU** has three. **vvfat** — a FAT volume synthesized over the
  directory in-process, needing no guest driver, no build option,
  and present in every QEMU build. **virtio-9p** (`-fsdev local`
  plus a `virtio-9p-pci` device — in-process, no daemon).
  **virtio-fs** (a `vhost-user-fs-pci` device backed by an external
  `virtiofsd` process per share, over a vhost-user socket, with the
  machine's memory served from a shared memory backend sized
  exactly to the blueprint's `memory`).
- **VirtualBox** has one: its own shared-folder protocol
  (`VBoxManage sharedfolder add` at materialization, removed with
  the machine).
- **VMware** has one (HGFS, via `.vmx` entries) — relevant only
  once that adapter is actually built; the stub claims no
  capabilities, so a blueprint with a share never assigns there
  today. Hyper-V has no mechanism these guests could mount at all,
  and its stub likewise claims nothing.

Because QEMU genuinely has several, a share's object form gains an
optional **`model`** key — values `vvfat`, `9p`, and `virtio-fs` —
under D122's bar: honored where the capability report says so,
refused by name everywhere else, the same way `controller`'s
`nvme`/`virtio` and `net`'s `ne2k` already are. `9p` and
`virtio-fs` are real, general protocols (9P is Plan 9's own, in
Linux, QEMU, and Windows/WSL; virtio-fs is a cross-hypervisor
virtio spec). `vvfat` is admitted with eyes open: the word is
QEMU's own name for its mechanism, kept because it's what every
QEMU document calls it and it's greppable — the contract it names
is stated here, not implied by the word.

**The `vvfat` model's contract**, carried over from the drive it
replaces: the guest's view is assembled when the machine starts;
host edits during the run are invisible; guest writes surface on
the host once the machine stops; the volume is FAT-shaped and
disk-shaped, on whatever controller the adapter renders (not
authored); nothing is hash-checked. What it buys for that: no guest
driver, no QEMU build option, no daemon — the one model that works
on a completely stock installation with a completely stock guest.

**An unstated `model` means the assigned backend's own default
mechanism** — for VirtualBox its only one, for QEMU **`9p`**,
deliberately not vvfat: an author who declares a share and says
nothing must get the field's full live contract, never silently the
snapshot one. 9p over virtio-fs because it is the cheaper live
contract in every direction: served in-process with no daemon to
supervise, no vhost-user socket, and no shared-memory coupling to
the machine's own `memory`. `virtio-fs` is chosen by name when its
throughput and semantics are worth that host-side cost.

One consequence is stated plainly rather than hidden: **which guest
driver a share needs follows the assigned backend and model.** A
9p share needs `VIO9P` loaded in the guest, a virtio-fs share
`VIOFS`, a VirtualBox share a vboxsf redirector — and a vvfat share
nothing at all. There is no cross-backend live-share device the way
`pcnet` is a cross-backend NIC. An author who needs one specific
guest driver (or none) pins `backend` or authors `model`, and
assignment records what was chosen, so a run never depends on
guessing.

## Capability is probed per installation, not assumed

Every capability report so far is a static claim about what the
adapter's own code implements, and that's been honest because a
stock QEMU or VirtualBox honors those claims uniformly. The live
transports break that pattern on the QEMU side: **fsdev/9p is a
QEMU build option, and the official Windows binaries are built
without it** (`-fsdev help` answers "fsdev support is disabled";
`-device help` lists no 9P device). virtio-fs needs
`vhost-user-fs-pci` (its own build option) plus a `virtiofsd`
binary, which upstream ships for Linux only — on a Windows host,
both live transports exist today only through the maintainer's own
working ports (a QEMU tree with fsdev/9p and vhost-user on Windows,
`D:\Projects\qemu` branch `windows-fs-raw`, and a virtiofsd
prototype, `D:\Projects\virtiofsd` branch `windows-raw`;
virtio-dos's `docs/TESTING.md` documents building and running
both), reached the ordinary way via `RELIQUARY_QEMU_HOME`. vvfat,
by contrast, is in every QEMU build and needs no probe.

So the QEMU adapter's share capability is `vvfat` plus whatever a
probe of the selected binary finds, per transport, and the report
says exactly what the probe found (P11). The emergent behavior is
right without special casing: on a Windows host with a stock QEMU,
an authored `model: vvfat` share works as it always has; an
unstated-model share defaults to 9p, is refused by name there, and
assignment falls through to VirtualBox if it's installed — or
machine creation fails closed naming the unmet requirement, like
any other capability.

virtio-fs also carries a real adapter obligation beyond the probe:
Reliquary starts one `virtiofsd` per share before the machine,
supervises it, stops it after, and reports its death mid-run as a
named failure — plus the shared-memory configuration, which must
agree with the blueprint's `memory`. That coupling is also why the
`backend-settings.qemu.args` escape hatch, which genuinely can
carry a 9p share today, structurally can't deliver virtio-fs: the
settings section is forbidden from touching what Reliquary owns,
and the memory backend is exactly that.

## This does not reopen D108

D108's boundary is that Reliquary never reads or writes file
content inside a machine's drives, and a share doesn't: Reliquary
renders arguments and `VBoxManage` calls; the protocol servers are
QEMU's, `virtiofsd`'s, and VirtualBox's; the actual reading and
writing is done by the guest on its side and by the caller's own
tools on the host directory. The in-band routes stay exactly two —
AGENTS.md's D108 summary names "a directory-source media that
attaches a host directory as a vvfat drive, and
`insert_media(file=)`"; the first of those becomes the share
device, and that sentence is reworded when this ships. The
file-access command family stays gone.

## The guest side stays the guest's business

A live share needs a driver loaded in the guest — `VIO9P`/`VIOFS`
from virtio-dos for QEMU, a vboxsf redirector (vbados's `VBSF.EXE`)
for VirtualBox — and supplying it is the user's job, under U28's
packet-driver precedent: Reliquary wires the device; what the guest
runs against it is the guest's own business. (`model: vvfat` is the
deliberate exception — it needs nothing in the guest, which is
exactly why it survives inside this design as a model instead of
being retired.) Reliquary functions with no content of its own
(P18), so nothing is vendored; the author-facing docs point at the
known drivers instead. And per P10, Reliquary never verifies the
guest actually mounted a share — the device being attached is a
host-side fact it knows; the mount is the guest's own act, observed
only the way anything else in a guest is, by watching the screen.

## The directory-source drive folds into this design

Settled in the second owner round: the vvfat directory-drive is
absorbed as this device kind's `vvfat` model, and directory
payloads stop being legal on drive slots. The argument, recorded so
the drive spelling doesn't come back:

**Purpose is the salient identity.** The blueprint's fields name
what the author means, with mechanism resolving underneath —
U28's own adopted language ("a fact about what the machine is
*for*"). "These files are visible on both sides of the guest/host
boundary" is one purpose; that one mechanism delivers it as a
synthesized BIOS-visible block device and another as a filesystem
protocol is exactly the kind of difference the model key exists to
carry (D120/D122).

**The contract objection dissolves against Reliquary's own
precedent.** The strongest case for keeping two device kinds was
that vvfat's snapshot semantics and a live protocol's semantics are
different contracts, and one field shouldn't cover both. But
`materialize` already does precisely this — `copy` and `use` are
different write-back contracts behind one authored field, chosen
per value, documented per value. An authored `model: vvfat` opting
into snapshot semantics is the same shape, and since no backend
defaults to it, nobody gets the weaker contract without writing the
word.

**Directory payloads were already a shadow device kind inside the
drive grammar.** They were rejected on cdrom slots, detected by a
render-time `isdir` check the drive model knew nothing about, never
hash-checked, and gave `read-only` its own special meaning. The
fold names what was already there.

**The fold gains real things.** One authoring axis (a model table
in one doc section, instead of two device kinds needing a permanent
"which do I want" comparison); the `Capabilities.vvfat` boolean — a
QEMU brand name bolted onto the capability report — dissolves into
the ordinary share-model mechanism; and slot intent becomes
fail-closed in both directions, where today the payload silently
switches a drive's semantics at render time.

**Three pieces of drive machinery are knowingly retired for
directory payloads**, each with its reopen condition:

- **The floppy shape.** Today a directory on a floppy slot renders
  as `fat:floppy:`; shares are disk-shaped only. Nothing in the
  codex or virtio-dos declares a directory media at all, let alone
  a floppy-shaped one (checked this round). Reopens if something
  genuinely needs an A:-shaped share — the `vvfat` model would gain
  a shape key then.
- **Boot-order membership.** A directory-drive could be named in
  `boot`; a share can't. Nothing boots from a synthesized FAT
  volume, and no journey ever did.
- **Live insertion.** A directory media on a removable slot was in
  principle insertable; inserting a directory media now fails
  closed naming the rule. It is doubtful QEMU's `change_medium`
  ever accepted a vvfat source over QMP, so this likely retires
  nothing but the appearance of an option.

What would reopen the fold itself: a real use case needing drive
machinery — controller choice, boot membership, insertion — on a
directory payload. None is known, and none is expected.

## Weighed and declined

- **A top-level `shares` field** — D121 settled the container: one
  `devices` inventory, discriminated by the key's medium prefix.
- **Naming the vvfat model by its contract instead of its QEMU
  name** (`fat-snapshot` or similar) — declined: the invented name
  would need a glossary entry to connect it back to what every QEMU
  document and error message calls the mechanism, and the contract
  is documented either way. Reopens if a second backend ever grows
  an equivalent mechanism and the QEMU brand name becomes actively
  wrong.
- **vvfat as QEMU's unstated-model default** — declined even though
  it's the only model needing no guest driver and no build option:
  an unstated share must mean the field's full live contract, never
  silently the snapshot one. The author who wants vvfat's trade
  writes the word.
- **A `vboxsf` or `hgfs` model name** — on a backend with exactly
  one mechanism there is nothing to choose, so a model name there
  would be a backend pin wearing vocabulary's clothes. Reopens if
  some backend ever offers a second mechanism.
- **Resolving an unstated `model` to whichever transport the probed
  QEMU has** — rejected: the guest-visible device (and so the
  driver the guest must have loaded) would then depend on the
  host's QEMU build flags. A QEMU without fsdev refuses an unstated
  share by name rather than silently serving something else.
- **Vendoring the guest drivers, or shipping them in the codex** —
  P18 and the U28 precedent, plus a real sync burden against
  virtio-dos's own releases. A docs pointer costs nothing and goes
  stale gracefully.
- **Live attach/detach of shares** — VirtualBox has transient
  folders and QEMU could hotplug, but no use case asks; shares
  attach at start and detach at stop. U20's live-iteration journey
  is already served by `insert-media`, and a share that exists for
  the whole run serves it better still.
- **A `null` share value** — an empty drive bay is real hardware; a
  share with no directory means nothing.
- **Hash verification of a share's contents** — inherits the
  directory-media trade already recorded in media-spec.md: writable
  means unverifiable, and that's the deal the author chose.
- **One directory shared into several running machines at once** —
  none of the mechanisms coordinates concurrent guests, so the
  existing advisory carries over unchanged: don't.

## What delivering this touches

A sketch, so the feature entry can be sized honestly — this
document delivers none of it:

- `document.py`: `share` joins the devices-key grammar (D121's
  clash check covers it by construction), the value forms, the
  directory/`use` constraints, share keys refused in `boot`; drive
  slots refuse directory payloads at resolution, and the cdrom
  carve-out dissolves into that rule; blueprint-model.md and the
  JSON schema alongside.
- `backends.py`: share capability and requirement fields, with the
  usual `unmet()` math; `Capabilities.vvfat` retires into the share
  models; the QEMU live-transport entries fed by a
  per-installation probe rather than a static claim.
- `backend_qemu.py`: the vvfat rendering moves out of `drive_args`
  into the share renderer; fsdev/9p rendering; the virtio-fs path's
  `virtiofsd` lifecycle, vhost-user socket, and shared-memory
  configuration; the probe; `RESERVED_ARGUMENTS` grows the fsdev
  family.
- `backend_virtualbox.py`: `sharedfolder add`/`remove` at
  materialization and disposal.
- `machines.py` / state: shares in the merged `devices` map (a
  share entry is discriminated by its own shape, like drives and
  NICs); `apply_blueprint` can absorb share changes on a stopped
  machine, since no image is materialized for one; inserting a
  directory media becomes a named refusal.
- Docs and content: media-spec.md's directory-payload section
  re-homes onto shares; USE-CASES.md's U25 journey respells "add a
  drive whose media is a host directory" as adding a share; the
  freedos-dump-font codex script's comment citing the vvfat drive;
  AGENTS.md's D108 "two routes" sentence rewords its first route.
- Tests: `fake_backend.py`'s capability claim and
  `test_backend_qemu.py`'s vvfat render coverage move with the
  mechanism.
