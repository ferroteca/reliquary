<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# DOSBox-X as a backend

> **Status:** investigated 2026-08-22 against **DOSBox-X 2026.08.02**
> (the install at `C:\DOSBox-X`), ruled **not a goal against that
> build** — the ruling is the non-goal bullet in
> [backend-adapter.md](backend-adapter.md), and this document is the
> evidence behind it. **R12's reopen condition has since been met**,
> independently verified 2026-08-24 against a control channel added
> on a personal fork (below), which is a different fact from the
> ruling changing: the control half the non-goal names is no longer
> missing, but it exists nowhere Reliquary could depend on today
> without adopting that fork. It sits in `design/` because it serves
> no single feature ([README.md](../README.md)); **R12**
> ([RECURRING.md](../RECURRING.md)) is the standing watch, now
> retargeted to the adoption question the technical one resolved
> into. Shaped by **P11** (capability honesty — reported, never
> emulated), **P2** (agentless operation is permanent) and **P21** (a
> dependency must pull its weight); the demand a fifth backend would
> serve is **U12**'s unattended install and **U1**'s single command,
> which the DOS workflow already reaches on QEMU today. **It
> authorizes no implementation.** DOSBox-X arriving as a backend, on
> whatever binary, would be its own proposal under the surface-change
> rule ([SURFACES.md](../SURFACES.md)), taking a place in **D66**'s
> priority order as part of that act — and adopting a personal fork
> as a build dependency is a separate, prior question this document
> does not answer.

## Why the question is worth asking

DOSBox-X is the most complete DOS-era emulator in circulation — it
covers hardware Reliquary's delivered platform workflow cares about
(machine types, the sound and video generations, PC-98) more
faithfully than a general-purpose hypervisor does, and it is the
tool a DOS-era user is likely to already have. Reliquary's one
complete platform workflow is DOS. So the pairing suggests itself,
and the reason it does not work is worth writing down once rather
than rediscovering.

The answer splits cleanly in two, and the split is the finding:
**the machine half fits well, and the control half does not exist.**

## The machine half fits

Everything the seam asks of a backend *before* a guest is running
has an honest answer, and several are better than expected:

- **Boot and media.** `IMGMOUNT` and `BOOT` mount and boot raw
  floppy, hard-disk and ISO images, with IDE emulation on by
  default (`[ide, primary]`, `enable = true`) and El Torito
  handling for bootable CDs. `floppy`, `hdd`, `cdrom` and
  controller `ide` could all be claimed.
- **Image formats, including a native differencing image.**
  DOSBox-X reads raw `.img`, **VHD** and **qcow2**, and its
  `VHDMAKE` tool creates dynamic VHDs, links a **differencing**
  VHD to a parent, and merges one back. So all four materialize
  modes — `new`, `copy`, `difference`, `use` — have a native
  route, which is more than the VirtualBox adapter had available.
  (Reading qcow2 also means images the QEMU adapter already builds
  are mountable as they stand.)
- **Launch configuration.** The whole machine is configured from
  the host at launch: `-conf` for a per-machine config file,
  `-set <section property=value>` to override any single option,
  `-c` to run commands in the built-in shell, `-defaultdir` and
  `-savedir` to place its working state. That is enough to keep
  every backend file inside `cache/machines/<id>/` as **P12** and
  the seam both require, and enough for `start` to lower a
  machine's resolved state into a launch — the same shape
  `backend_qemu.settings_args` renders.
- **Memory.** `memsize` in megabytes, so the DOS platform's memory
  floor is expressible.

Two honest gaps on this side, both the kind a capability report
exists to state: there is **no SMP** (the local APIC is faked, not
emulated), so a `cpus` above one would be refused by name; and
there is no `vvfat` equivalent for a directory-source drive —
DOSBox-X's `MOUNT` of a host directory is a *built-in-DOS* feature
that does not survive `BOOT`, which is the same distinction that
governs everything below.

## The control half does not exist

Every carrier the seam requires — `send_keys`, `text_screen`,
`screenshot`, `change_medium`, and an identity-verified `stop`
([backends.py](../../src/reliquary/backends.py)) — is a **host-side
command issued against a machine that is already running**. That is
the shape of QMP on QEMU and `VBoxManage controlvm` on VirtualBox,
and DOSBox-X has no equivalent of any kind.

Its entire external surface is the command line at launch and the
SDL window afterwards. Searched for the alternative and not found:
no monitor, no control socket, no named pipe, no stdio protocol.
The only listeners it has (`serial1=nullmodem` with its `server` /
`port` / `inhsocket` parameters, and `modem listenport`) face the
**guest's** COM port, and `-socket` is only the socket number for
that same null-modem emulation — a serial line into the guest is
the serial-console plane, and a booted DOS has no console on it.

Carrier by carrier:

| Seam carrier | What DOSBox-X offers | Why it does not answer |
|---|---|---|
| `send_keys` | The window, the mapper, or `AUTOTYPE` | `AUTOTYPE` is a fixed sequence — `-w` at most 30s before it starts, `-p` at most 10s between keys — with no readback of any kind, and it is a **built-in-shell program on `Z:`**, so it can only be issued before `BOOT` hands the machine to a real DOS. Whether a queued sequence keeps firing into the booted guest does not matter: it is blind either way, and Reliquary's loop is type–wait–read. |
| `text_screen` | Nothing | No text-memory readback is exposed to the host at all. |
| `screenshot` | A mapper hotkey, or `DX-CAPTURE` | The hotkey needs a host key event; `DX-CAPTURE` is another `Z:` program, gone after `BOOT`. Captures land in the `captures` directory on the emulator's own terms, not on a caller's request. |
| `change_medium` | A menu item, or `IMGSWAP` | Both are inside the running emulator — the menu needs a mouse, `IMGSWAP` needs the built-in shell. |
| `stop`, identity-verified | `-time-limit <n>`, or killing the process | A launch-time timer is not a command, and neither names the instance. |

The through-line is one fact: **the tools that could drive a
machine all live inside the DOS that DOSBox-X itself provides, and
Reliquary's product is a real guest OS installed onto a disk image,
which replaces exactly that DOS.** `IMGMOUNT`, `AUTOTYPE`,
`DX-CAPTURE`, `IMGSWAP` and `VHDMAKE` are `Z:` drive programs;
`BOOT` is the moment they stop existing. An emulator whose
automation surface is its own DOS cannot automate someone else's.

And with no addressable instance there is no **identity** to record
or verify, so the ownership doctrine — the `backend-id`, the
per-start `token`, verify-before-command, fail-closed stop — has
nothing to attach to. That is not a missing convenience; it is the
rule every adapter operation is built on.

## The near miss, named because it is the seed

The one thing in DOSBox-X shaped like a channel is the
**integration device** (`integration device`, `[cpu]`): an emulated
ISA I/O device, still marked experimental, through which
"additional software can talk to DOSBox-X" — reporting emulator
status, matching the mouse pointer. It is the closest thing to a
control channel in the codebase, and it faces the **wrong way**:
the software that talks through it runs *inside the guest*, which
means guest cooperation (**P2**) and a driver in a guest Reliquary
has not installed yet. It answers nothing the seam asks. It is
recorded here because if a host-side channel is ever built, this is
the plausible thing it gets built on.

## Why not a stub adapter

`backend_stubs.py` holds VMware and Hyper-V, and DOSBox-X does not
belong beside them. Those two are real hypervisors with real
control surfaces (`vmrun`, the Hyper-V PowerShell module) that
nobody has written the adapter against yet — a stub there is
*unbuilt work*, and its empty capability report is a placeholder
that will one day be filled. Here there is nothing to build
against: a DOSBox-X stub would be a permanent entry whose
capability report could never grow, advertising a backend the
project has decided against. The honest record of a decision is
this document, not an adapter that returns nothing.

## Why not host GUI automation

The path that would work is synthesizing input into the SDL window
(`SendInput` and its non-Windows equivalents) and grabbing that
window's pixels. It is refused on four independent grounds, any one
of which would be enough:

- **It is the brittle plane the doctrine already rejects.**
  [guest-communication.md](guest-communication.md) refuses
  screenshot-driven UI automation as a substitute for a
  communication protocol; driving the *host's* window is that,
  one layer further out.
- **It emulates a capability rather than reporting one** (**P11**).
  An `agentless-display` claim would mean something categorically
  less reliable than the same claim on QEMU or VirtualBox, which
  is precisely what capability honesty forbids.
- **It is a new host-only dependency** for a subset of one
  backend's needs — the weighing **P21** governs and **D110**
  already ran once, when an in-tree RFB client won over pulling in
  a VNC library.
- **It cannot run unattended.** The window must be visible and
  focused to receive synthesized input, so a run would seize the
  host's desktop. Configuring `videodriver = dummy` for headless
  operation removes the window — and with it the only readback
  there was.

## What would reopen this

The bar, as originally set: DOSBox-X would need a **host-side
control channel** — a socket, named pipe, or stdio protocol — that
against an **already-booted** guest can inject key events, read the
screen, change a removable medium, and name/verify the running
instance so a stop can be fail-closed. More mapper hotkeys, more
`Z:` programs, or a richer guest-facing integration device would
**not** have reopened it.

## The bar was met, on a personal fork (2026-08-24)

`pgalbraith/dosbox-x`, branch `control-channel` (built from DOSBox-X
2026.08.02 plus four commits, `a108b48c` → `7879a182` → `1d6406c1` →
`d21d1581`), adds `src/hardware/hostcontrol.cpp`: a loopback TCP
listener (`[control]` section, off by default) speaking a
line-oriented protocol — `PING`/`VERSION`/`IDENTIFY`, `AUTH <token>`,
`KEY`/`KEYDOWN`/`KEYUP`, `SCREEN`, `SCREENSHOT`, `MOUNT`/`SWAP`,
`EJECT`, `STOP`. Every guest-touching command refuses until `AUTH`
succeeds against a launcher-minted token (`-set control.token=...`),
a wrong guess drops the connection rather than allowing retries, and
`IDENTIFY` reports a free-form `backend-id` — the ownership
doctrine's shape, not just its name.

**Independently verified against a built binary**, not taken on the
branch's own word: the CI artifact for `d21d1581` (`64-bit Visual
Studio builds` → `dosbox-x-vs2026build-*`) was downloaded and run
standalone, driven over the socket by a throwaway Python client,
against the FreeDOS LiveCD ISO already cached at
`cache/media/freedos-livecd.iso` and a hand-assembled minimal
bootable floppy (a boot sector that prints a marker and halts, built
to force a real BIOS→guest handoff without depending on any DOS
distribution). Confirmed directly:

- **`PING`/`VERSION`/`IDENTIFY`** answer before auth; every
  guest-touching command refuses with `ERR not authenticated` before
  it; `AUTH` with the wrong token gets `ERR auth failed` and the
  connection closes (no retry); the right token authenticates and
  `IDENTIFY` then reports `authenticated=yes`.
- **`KEY`** injection works pre-boot: a multi-character DOS command
  string, sent one `KEY` per character, landed correctly on
  DOSBox-X's own `Z:\>` prompt.
- **`SCREEN`** readback is exact: it echoed the typed command and
  DOSBox-X's own response verbatim, then — after `BOOT`ing the
  hand-built floppy — showed the guest's own `GUEST-BOOTED-OK`
  banner, confirming the readback survives the boot handoff rather
  than freezing on DOSBox-X's own last-drawn screen (the failure
  mode F64 hit on OpenBSD's `wscons`,
  [FEATURES.md:922](../proposed/FEATURES.md)).
- **`MOUNT` + `SWAP`** (floppy): appending a second, never-mounted
  image to the booted floppy drive and switching to it both
  returned `OK`, matching the "append then select" contract.
- **`EJECT`** (the gap this document originally flagged, closed in
  `1d6406c1`/`d21d1581`): called against the CD-ROM mounted *before*
  `BOOT`, once the guest was live (confirmed via the log line
  `Alright: DOS kernel shutdown, booting a guest OS`) — returned
  `OK`, and independently confirmed in the log by
  `IDE ATAPI acknowledge media change for drive D`, not just the
  socket's own say-so. A second `EJECT` on the same drive was
  idempotent (`OK`); `EJECT` against an unmounted/invalid drive was
  correctly refused (`ERR drive not a mounted CD-ROM`); the
  connection stayed healthy immediately after (`PING` still
  answered).

Not personally re-verified: `SCREENSHOT` (graphics-mode framebuffer
capture) rests on the branch author's own testing, not mine — lower
risk, since it reads the same persistent buffer `SCREEN`'s sibling
capture feature already reads, and the mechanism class (`KEY`,
`SCREEN`) it shares was independently confirmed.

**A separate, unrelated limitation surfaced along the way**: this
build's `IMGMOUNT -bootcd` cannot boot the actual FreeDOS LiveCD ISO
— `El Torito boot entry: media types other than floppy emulation not
supported yet`. The LiveCD uses a no-emulation El Torito boot
record; DOSBox-X's El Torito handling only supports floppy
emulation. This is core boot-handling, not `hostcontrol.cpp`, so it
predates and is unrelated to the control channel — but it means the
control channel alone would not carry Reliquary's exact
`freedos-install` recipe (which boots that ISO directly) without a
second fix or a different installer-delivery shape (a hard-disk
image instead of a CD, for instance). Named here rather than
silently worked around, per **P11**.

**What the branch still doesn't close.** No floppy/hdd eject-to-empty,
no attaching an unseen image to a drive that started empty (`MOUNT`
still requires an already-mounted `fatDrive`), no SMP, no `vvfat`.
None of Reliquary's codex recipes currently need the first two; the
last two were already named as honest gaps in "The machine half
fits" above and are unaffected by this branch.

**What no amount of testing changes.** The channel lives on an
**unmerged personal fork**, not upstream DOSBox-X and not the stock
`C:\DOSBox-X` install this document was first written against. An
adapter built against it would depend on that fork specifically —
maintain it, upstream it, or track someone else's release of it —
which is a commitment distinct from "the capability now exists
somewhere," and not one this document decides.

## Where DOSBox-X does have a place

Not as a backend, but at the image boundary. It reads raw, VHD and
qcow2 — including the qcow2 the QEMU adapter already produces — so
a disk image Reliquary builds is a disk image DOSBox-X can boot,
with no adapter in between. Under **P20** installation media is
input and disk images are output, and handing that output to a tool
the user drives themselves is the **exporter** family's territory,
not a backend's. That is the same disposition
[backend-adapter.md](backend-adapter.md) already records for
orchestrators and external harnesses: a handoff target is not a
provider.
