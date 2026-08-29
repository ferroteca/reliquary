<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# DOSBox-X as a backend

> **Status:** investigated 2026-08-22 against **DOSBox-X 2026.08.02**
> (the install at `C:\DOSBox-X`). The result: DOSBox-X is **not a
> goal as a backend, for that build**. That ruling is recorded as
> the non-goal bullet in [backend-adapter.md](backend-adapter.md);
> this document is the evidence behind it. **R12's reopen condition
> has since been met** — confirmed independently on 2026-08-24,
> against a control channel added in a personal fork (details
> below). That is a separate fact from the ruling itself changing:
> the missing control interface the non-goal describes now exists,
> but only in that fork, which Reliquary does not depend on today.
> This document lives in `design/` because it does not serve any
> single feature ([README.md](../README.md)). **R12**
> ([RECURRING.md](../RECURRING.md)) is the standing watch on this
> question, now pointed at the adoption question the fork raises
> instead of the original technical question. Three project rules
> shape this document: **P11** (report capabilities honestly, never
> fake one), **P2** (Reliquary must keep working without an agent
> installed in the guest), and **P21** (a dependency has to earn its
> keep). The reason to want a fifth backend at all is **U12**
> (unattended installs) and **U1** (a single command) — both of
> which the DOS workflow already delivers today on QEMU. **This
> document does not authorize building anything.** If DOSBox-X ever
> becomes a backend, on any binary, that needs its own proposal
> under the surface-change rule ([SURFACES.md](../SURFACES.md)), and
> that proposal would take a place in **D66**'s priority order.
> Whether to adopt a personal fork as a build dependency is a
> separate, earlier question that this document does not answer.

## Why the question is worth asking

DOSBox-X is the most complete DOS-era emulator available. It covers
the hardware Reliquary's finished DOS platform workflow cares about
(machine types, the sound and video generations, PC-98) more
faithfully than a general-purpose hypervisor does, and it is the
tool most DOS-era users already have installed. Reliquary's one
finished platform workflow is DOS, so pairing the two looks like an
obvious idea. This document writes down, once, why it does not
work, so the question does not need investigating again later.

The answer splits into two parts. **The machine half of DOSBox-X
fits well. The control half does not exist.**

## The machine half fits

Everything the backend adapter seam requires before a guest is
actually running has a real answer in DOSBox-X, and some of the
answers are better than expected:

- **Boot and media.** `IMGMOUNT` and `BOOT` mount and boot raw
  floppy, hard-disk and ISO images, with IDE emulation on by
  default (`[ide, primary]`, `enable = true`) and support for
  El Torito bootable CDs. DOSBox-X could claim support for
  `floppy`, `hdd`, `cdrom`, and the `ide` controller.
- **Image formats, including a native differencing image.**
  DOSBox-X reads raw `.img`, **VHD**, and **qcow2** files, and its
  `VHDMAKE` tool creates dynamic VHDs, links a **differencing**
  VHD to a parent, and merges one back into its parent. So all
  four materialize modes Reliquary uses — `new`, `copy`,
  `difference`, `use` — have a native way to work in DOSBox-X,
  which is more than the VirtualBox adapter had available. (Because
  DOSBox-X reads qcow2, images the QEMU adapter already builds are
  mountable in DOSBox-X as-is.)
- **Launch configuration.** The whole machine is configured from
  the host at launch: `-conf` names a per-machine config file,
  `-set <section property=value>` overrides any single option,
  `-c` runs commands in the built-in shell, and `-defaultdir` and
  `-savedir` set where its working state is stored. That is enough
  to keep every backend file inside `cache/machines/<id>/`, as
  **P12** and the seam both require, and enough for a `start`
  operation to turn a machine's resolved state into an actual
  launch command — the same job `backend_qemu.settings_args`
  already does for QEMU.
- **Memory.** The `memsize` option is set in megabytes, so
  DOSBox-X can express the DOS platform's minimum memory
  requirement.

There are two real gaps here, exactly the kind a capability report
exists to state honestly: DOSBox-X has **no SMP** (it fakes the
local APIC rather than emulating it), so a `cpus` setting above one
would have to be refused by name. And it has no equivalent to
`vvfat` for a directory-source drive: DOSBox-X's `MOUNT` command
exposes a host directory only inside its own built-in DOS shell,
and that access does not survive `BOOT`. That same fact — that a
tool only works before `BOOT` hands control to a real guest — is
the reason for everything in the next section.

## The control half does not exist

Every carrier the seam requires — `send_keys`, `text_screen`,
`screenshot`, `change_medium`, and a `stop` that checks the
machine's identity first
([backends.py](../../src/reliquary/backends.py)) — works by
sending a command **from the host to a machine that is already
running**. That is what QMP does for QEMU and what
`VBoxManage controlvm` does for VirtualBox. DOSBox-X has nothing
like it.

DOSBox-X's entire interface to the outside world is the command
line used to launch it and the SDL window it opens afterward. We
looked for anything else and found nothing: no monitor, no control
socket, no named pipe, no stdio protocol. The only network-facing
settings it has (`serial1=nullmodem` with its `server` / `port` /
`inhsocket` parameters, and `modem listenport`) connect to the
**guest's** own COM port, not to DOSBox-X itself, and `-socket`
just sets the port number for that same null-modem emulation. A
serial line into the guest is the serial-console plane, and a
booted DOS guest has no console listening on it.

Carrier by carrier:

| Seam carrier | What DOSBox-X offers | Why it does not answer |
|---|---|---|
| `send_keys` | The window, the mapper, or `AUTOTYPE` | `AUTOTYPE` only runs a fixed sequence of keystrokes: `-w` sets a wait of up to 30 seconds before it starts, `-p` sets a delay of up to 10 seconds between keys. It has no way to read anything back, and it is a **built-in-shell program on `Z:`**, so it can only run before `BOOT` replaces DOSBox-X's own DOS with a real one. It does not matter whether a queued `AUTOTYPE` sequence keeps sending keys after `BOOT` — either way there is no way to see what happened, and Reliquary's automation loop needs to type, wait, and then read the result. |
| `text_screen` | Nothing | DOSBox-X exposes no way to read text-mode screen memory from the host at all. |
| `screenshot` | A mapper hotkey, or `DX-CAPTURE` | The hotkey needs an actual keypress on the host; `DX-CAPTURE` is another `Z:` drive program that stops working after `BOOT`. Either way the captured image is written to the `captures` directory whenever DOSBox-X decides to write it, not on request from a calling program. |
| `change_medium` | A menu item, or `IMGSWAP` | Both only work from inside the running emulator: the menu needs a mouse click, and `IMGSWAP` needs the built-in shell. |
| `stop`, identity-verified | `-time-limit <n>`, or killing the process | A launch-time timer is not a command you can send while it is running, and neither option identifies which running instance it is acting on. |

The underlying reason is one fact: **every tool that could drive a
machine lives inside the DOS that DOSBox-X itself provides.
Reliquary's whole purpose is installing a real guest OS onto a disk
image, and that installed OS replaces exactly that built-in DOS.**
`IMGMOUNT`, `AUTOTYPE`, `DX-CAPTURE`, `IMGSWAP` and `VHDMAKE` are
all `Z:` drive programs, and `BOOT` is the moment they stop being
available. An emulator whose automation tools live inside its own
DOS cannot use them to automate a different, installed OS.

And because there is no running instance you can address from
outside, there is no **identity** to record or check. So the
ownership doctrine — the `backend-id`, the per-start `token`,
checking identity before sending a command, and stopping only when
that check passes — has nothing to attach to in DOSBox-X. This is
not a missing convenience: checking identity first is the rule
every adapter operation in Reliquary is built on.

## A near miss, worth naming for later

The one thing in DOSBox-X that resembles a control channel is the
**integration device** (the `integration device` setting in the
`[cpu]` section): an emulated ISA I/O device, still marked
experimental, that lets "additional software talk to DOSBox-X" —
for example reporting emulator status or matching the mouse pointer
position. It is the closest thing to a control channel that exists
in the DOSBox-X source, but it works in the **wrong direction**:
the software that talks through it runs *inside the guest*. That
needs guest cooperation, which **P2** rules out, and it needs a
driver installed in a guest that Reliquary has not installed
anything into yet. It does not provide anything the seam needs. It
is recorded here because if a host-side channel is ever built for
DOSBox-X, this device is the most likely thing it would be built
on.

## Why not a stub adapter

`backend_stubs.py` holds VMware and Hyper-V, and DOSBox-X should not
be added alongside them. Those two are real hypervisors with real
control surfaces (`vmrun` for VMware, the Hyper-V PowerShell module
for Hyper-V) that nobody has written the adapter code for yet. A
stub for either one represents work not yet done, and its empty
capability report is a placeholder waiting to be filled in later.
DOSBox-X has nothing to build against: a DOSBox-X stub would be a
permanent entry whose capability report could never grow, since it
would be advertising a backend the project has already decided
against. This document is the honest record of that decision — not
an adapter that returns nothing.

## Why not host GUI automation

One approach that would technically work is sending simulated
keystrokes into DOSBox-X's SDL window (using `SendInput` on
Windows, or the equivalent on other platforms) and capturing that
window's pixels as a screenshot. This document rejects that
approach for four separate reasons, and any one of them would be
enough on its own:

- **It is the same unreliable approach the project already rejects
  elsewhere.** [guest-communication.md](guest-communication.md)
  rules out screenshot-driven UI automation as a stand-in for a
  real communication protocol. Driving the *host's own window* this
  way is the same problem, just one step further removed from the
  guest.
- **It would report a capability DOSBox-X does not really have,
  instead of reporting the truth** (**P11**). Claiming
  `agentless-display` support this way would mean something far
  less reliable than the same claim for QEMU or VirtualBox — exactly
  what the rule against faking capabilities exists to prevent.
- **It would add a new host-only dependency** just to cover part of
  one backend's needs. **P21** already covers this kind of
  tradeoff, and **D110** already worked through it once, when the
  project chose to write its own small VNC client in-tree instead
  of adding a dependency on a VNC library.
- **It cannot run unattended.** The DOSBox-X window has to be
  visible and focused on the host to receive simulated keystrokes,
  so running this way would take over the host's desktop. Setting
  `videodriver = dummy` to run headless removes the window — and
  with it, the only way to read the screen back.

## What would reopen this

The bar, as originally set: DOSBox-X would need a **host-side
control channel** — a socket, named pipe, or stdio protocol — that
works against an **already-booted** guest. It would need to inject
key events, read the screen, change a removable medium, and
identify and verify the running instance, so a stop command can
safely refuse to act on the wrong one. More mapper hotkeys, more
`Z:` drive programs, or a richer guest-facing integration device
would **not** have met this bar.

## The bar was met, on a personal fork (2026-08-24)

`pgalbraith/dosbox-x`, branch `control-channel` (built from DOSBox-X
2026.08.02 plus four commits, `a108b48c` → `7879a182` → `1d6406c1` →
`d21d1581`), adds `src/hardware/hostcontrol.cpp`. This adds a TCP
listener on localhost (the `[control]` section, off by default)
that speaks a line-oriented protocol: `PING`, `VERSION`,
`IDENTIFY`, `AUTH <token>`, `KEY`/`KEYDOWN`/`KEYUP`, `SCREEN`,
`SCREENSHOT`, `MOUNT`/`SWAP`, `EJECT`, and `STOP`. Every command
that touches the guest refuses to run until `AUTH` succeeds against
a token set by whoever launches DOSBox-X (`-set
control.token=...`). A wrong token drops the connection instead of
allowing another try. `IDENTIFY` reports a free-form `backend-id`,
which is the same kind of identifier the ownership doctrine
requires, not just a name that resembles it.

**Independently verified against a built binary**, not taken on the
branch's own word: the CI artifact for `d21d1581` (`64-bit Visual
Studio builds` → `dosbox-x-vs2026build-*`) was downloaded and run
standalone. It was driven over the control socket using a throwaway
Python client, against the FreeDOS LiveCD ISO already cached at
`cache/media/freedos-livecd.iso`, and against a hand-assembled
minimal bootable floppy (a boot sector that just prints a marker
and halts, built so the test forces a real BIOS-to-guest handoff
without depending on any actual DOS distribution). This confirmed
directly:

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

Not personally re-verified: `SCREENSHOT` (capturing the framebuffer
in graphics mode) was only tested by the branch's author, not
independently confirmed here. The risk is lower because it reads
the same persistent buffer that `SCREEN`'s sibling capture feature
already reads, and the same kind of mechanism (`KEY`, `SCREEN`) was
independently confirmed to work.

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

Not as a backend, but as a place to hand off finished disk images.
DOSBox-X reads raw, VHD, and qcow2 images — including the qcow2
files the QEMU adapter already produces — so a disk image
Reliquary builds is a disk image DOSBox-X can boot directly, with
no adapter needed in between. Under **P20**, installation media is
input to Reliquary and disk images are its output. Handing that
output to a tool the user runs themselves belongs to the
**exporter** family, not to a backend. That is the same treatment
[backend-adapter.md](backend-adapter.md) already gives
orchestrators and external harnesses: something a user hands
finished output to is not the same as something that provides a
backend.
