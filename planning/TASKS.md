<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# TASKS

The pledged work backlog. A **proposed** task lives in the issue
tracker — <https://github.com/ferroteca/reliquary/issues> — which is
the only queue a proposed task has (D43): the tracker is a task's
proposed state and this file is its pledged one. So nothing parks
here awaiting a verdict; arriving *is* the verdict.

**Everything in this file is pledged** — the one vocabulary
([README.md](README.md)) applying here exactly as in the
directories. An entry is in the *pledged* state, so entering it is
approving it: nothing waits on a verdict, nothing needs a citation
or a decision of its own, and there is nothing to promote. The
directory is not its home because `proposed/` and `pledged/` hold
*demand and capability*, argued at length, and a task is none of
those — free-standing work too small to be a feature and too small
to need the argument. That kind distinction is the distinguisher,
not size.

**This file is the third work input queue** (D43, widening D39's
two), and adding to it is governed by the gate covering all writing
under `planning/` — weighing most here, this being the one governed
act that grants approval with no argument behind it.

**A queue holds what waits.** Work that arrives already done never
appears here: there is nothing to schedule, only a decision to make,
and an entry filed and closed in one act is ceremony.

**Anything is struck when it is done** (D45, generalized by D52) —
tasks, audits, restructures and rounds alike. Its record is its
commit, its CHANGELOG line, and the D-numbers it produced, so it
leaves this file by deletion and nothing is parked. **Not a
retrospective either**: a note explaining what an emptied group
used to hold is the same parking one paragraph further on, and it
has to be edited every time the work it accounts for moves. The
same holds for the **work-item breakdowns inside a pledged
feature**: when the feature delivers, its list is deleted with its
F-number rather than archived. A record whose reasoning outlives
the work is a decision, and decisions live in
[DECISIONS.md](DECISIONS.md) — kept beside
the work instead, a summary drifts from what it summarizes and a
reader has no way to tell.

**There is no order here.** Nothing in this file is scheduled, and
nothing claims priority over anything else; whoever picks work up
picks whatever they like. The one ordering that does bind is a
feature's: **work that only makes sense as part of one pledged
feature lives with that feature**, in
[pledged/FEATURES.md](pledged/FEATURES.md), and has to be done to
complete it. A task here that merely *relates* to a feature is
still free to be picked whenever.

Housekeeping (D38) is the same instinct one size smaller: work tiny
enough and obvious enough that it needs no entry here **at all**,
approved as a class in advance, with the commit as its record. This
file is where the pre-approved work that is still worth writing
down goes. The full intake machinery — the raw queues, the
housekeeping test, and how pledge is recorded — is in
[README.md](README.md).

**Refused work is not recorded here** (D52). Entry to this file
*is* approval (D43), so a rejected task is one that never
entered — refusal happens at the door, and its record is the issue
that was closed or the [DECISIONS.md](DECISIONS.md) entry that
argued it, that file already being the guard against
re-litigating.

The queue proper is [Pledged](#pledged) below — grouped by kind
because the actor and the gate differ, though the grouping is not
a running order.

Standing questions to re-ask as the design hardens are not tasks
and live with the decision record, under
[DECISIONS.md](DECISIONS.md)'s open questions.

## Every task is itemized

**A task carries a T-number** (D86) — `T8 — Widen the drive report`,
number and name together, the way an F-number reads, at whatever
heading depth its group sits at. A
task is an item like any other, and D42's rule reaches it for
D42's reason: every item that can be depended on needs a handle,
because a heading someone may reword is not something to point
at. The number is what a commit cites, what another task points
at, and what survives this file's own regrouping — the groups
below are kinds rather than a running order, so an entry may move
between them, and without a number its heading text is the whole
of its identity.

**The number is issued at entry**, which for a task is the pledge
itself: a task has no proposed state under `planning/` (D43), so
there is no earlier moment to issue one at, and the idea that
preceded it carries the tracker's own issue number instead. That
is the one asymmetry with an F-number, which is issued at
proposal and travels into `pledged/` unchanged.

**And it evaporates on delivery**, with the work rather than
outliving it. That is D42's second handle class: a use case, a
principle and a decision persist, so their numbers are permanent,
while a feature names work not yet done and its handle goes when
the work lands. A task is work, so a struck task takes its number
with it (D52). **Evaporating is not reusable** — the number
retires and is never issued again, so a T-number surviving in a
commit message can never resolve to something else later, and
gaps in the sequence are history rather than a promise.

**T-numbers are issued against the sequence ledger**
([SEQUENCES.md](SEQUENCES.md); owner, 2026-07-31), which holds the
high-water mark this file used to state — take the next number
there and advance it in the same edit. The reasons the mark must
be stated at all — the queue empties, a struck task's only record
is its commit (D52), and a search sees only the branch it stands
on — live with the ledger, along with the sequence's T8 start.

## Pledged

Grouped by kind, because the actor and the gate differ: an audit
is mechanical, a defect needs no pledge because the norm it
violates already is one. A group with nothing in it is not listed:
an empty heading is a record of retired work, which this file does
not keep.

### Defects

Found by running the opt-in FreeDOS VirtualBox integration against
a live hypervisor for the first time (2026-08-13). What was fixed
in that sitting is not here — the unreadable-framebuffer abort, the
menu bar located by rarity, the wrong glyph bank, and the
quiescence guard's cadence dependence — as a queue holds only what
waits.

#### T23 — `select` loses a race with a menu that boots itself

The installed FreeDOS boot menu auto-boots before `select` can
steer it. The run reaches `hd-boot`, `wait "Load FreeDOS"` matches
after 9s on `1 - Load FreeDOS with JEMM386 (no EMS, max RAM free)`,
and the following `select "Load FreeDOS with JEMMEX (more
compatible)"` fails as *not on screen* — because by then the
countdown has expired and the guest has booted option 1. The
failure screenshot shows a fully booted system with `Jemm386 v5.85`
loaded, not a menu.

**Now the live blocker on the FreeDOS VirtualBox integration**,
which otherwise installs to disk and boots it.

Two things it is not, both checked. Not the glyph bank: `JEMM386`
recognized correctly at the wait a moment earlier, so the menu text
was readable. Not the boot order: the disk booted, which is the
whole point of the change that got the run this far.

**It is the cadence problem one layer up** — in the interaction
machinery rather than the quiescence measure that was just fixed.
`cursor_menu_select` spends `_BASELINE_READS` reads learning the
screen before it presses anything, then a read per keypress to
follow the highlight. At ~2s a read on a screenshot backend that is
tens of seconds before the first key is even sent. The LiveCD menu
survives it because its countdown is 13s and generous; the
installed system's is not.

**The sharp edge is that the baseline exists to learn decoration,
and the countdown *is* decoration.** `_BASELINE_READS` is
`DEFAULT_ANIMATION_REPEATS + 1` precisely because a ticking cell
cannot be recognized as furniture in fewer reads — so the machinery
spends its time learning the very timer that is running out. A menu
with a countdown is the case where looking before acting costs the
most and is worth the least.

Directions, none obviously right: press first and classify after,
so the first keypress does not wait on a baseline; take the
baseline from the reads a preceding `wait` already spent rather
than starting fresh; or let a `select` say it is racing a timer and
skip the mask. Note that `screen_stability` now reports the
measured cadence (`guard.cadence`), so the machinery can know it is
on a slow reading path rather than assuming.

#### T22 — A VirtualBox guest never reaches its second boot device

After FreeDOS repartitions and reboots, the guest stops at the
BIOS's `No active partition. Trying next boot device...` and stays
there — confirmed still on that line minutes after the run gave up,
so it is hung rather than slow. The freshly partitioned disk has no
active partition yet, which is expected; what does not happen is
the fallthrough to the CD that the same script gets on QEMU.

**Now the last blocker on the FreeDOS VirtualBox integration**, and
the first one that is not about reading the screen: the run drives
the boot menu, the language chooser, the installer welcome, the
partition prompt, partitioning and the reboot, and dies at the
BIOS.

**Two candidates have been ruled out by reading the live VM.** The
boot order is right — `boot1="disk" boot2="dvd"`, matching the
recorded `['hdd0', 'cdrom0']` — and the CD is still attached and not
ejected after the reboot. A third, the adapter assigning IDE slots
in *alphabetical* key order so `cdrom0` took the primary master and
the boot disk sat on the slave, was real and is fixed; the hang
survived it, with `hdd0.vdi` confirmed on 0-0 and the ISO on 0-1.

**What is left is a BIOS behavioural difference.** The same machine
boots the LiveCD from that slot happily while the disk is *blank*:
the first boot of every run does exactly that. Once FreeDOS writes a
partition table with no active partition, VirtualBox's BIOS prints
`No active partition. Trying next boot device...` and stops there
rather than falling through to the DVD, where QEMU's SeaBIOS
proceeds and the same script passes. So the fallthrough the script
depends on is QEMU's, and it is not portable.

That makes the remaining question a design one rather than a bug
hunt: whether the codex blueprint's boot order should put the cdrom
first, whether the install script should `set-boot` before the
reboot it asks for, or whether a machine should express "boot the
installer medium until the disk is bootable" at all. Whichever it
is, it touches an authored surface and needs the argument, not a
patch.

#### T19 — A machine whose VM died out of band can be neither stopped nor destroyed

`stop-machine` on a machine whose VM is already gone fails, and
`destroy-machine` then refuses because the phase says `running`,
with no `--force` and no other door: the only way out is deleting
the machine directory by hand. Hit while clearing up after a
failed integration run.

Backend-neutral and pre-existing, though the two arrive
differently. On VirtualBox a powered-off VM is still *registered*,
so `showvminfo` answers, `verify_vm` passes, and `controlvm
poweroff` fails as `RunFailure(machine.backend-failed)`. On QEMU
the dead QMP port raises `PreflightError(machine.vm-unreachable)`.
Either way `machines._complete_stop` sees a `vm` section still
recorded, restores `phase: running`, and re-raises.

Only reachable **outside** a run: `script_runner._read` converts
an unreachable VM into the stopped observation and calls
`mark_stopped`, so a run self-heals and only a guest that halts
itself between runs strands the machine. Whether the fix is
`stop-machine` treating an already-dead VM as an accomplished stop
— it is, on any reading of what stop means — or a separate
reconciliation door is the open question.

#### T20 — Two fonts are in play per run, and the choice is not the emulator's

With the host font in use (`guest_glyph_bank`) the FreeDOS
installer recognizes perfectly and the BIOS's own boot message
reads `Trying next boot device` as `Irying`. Before the fix it was
the other way round. **Both readings are correct**, which is the
finding: two different fonts are painted during one run, and no
run-long bank can be right for all of it.

Verified against the shipped binaries *and* the published source,
because the first reading of this — "the emulators draw different
faces" — was wrong and is worth not repeating.

**What the binaries hold.** `VBoxDD2.dll` carries three complete
VGA BIOS images, each with 8x8, 8x14 and 8x16 banks plus a
19-entry `vgafont16alt` override table. The three 8x16 banks are
byte-identical, so the classic-`A` anchor `bank_from_binary` uses
is unambiguous — worth recording, since a second distinct bank
would have made the extraction a coin toss. QEMU's `vgabios-*.bin`
carry **no alt table at all**: their 8x16 bank already has those
19 glyphs merged in.

**What the source says.** VirtualBox's `vgafonts.h` declares
`vgafont16alt[19*17+1]` — 19 entries of a code byte plus 16 rows,
then a terminator — and its codes are exactly the 19 parsed out of
the DLL. `vgabios.c` applies it *automatically on every text mode
set*, not on request:

    biosfn_load_text_user_pat(0, 0xC000, vgafont16, 256, ...);
    load_text_patch(0xC000, vgafont16alt, 0, 16);

So both emulators install **the same** font after a mode set. One
stores it merged, the other patches at runtime; VirtualBox's raw
bank plus its patch equals QEMU's shipped bank byte for byte.
**There is no emulator font difference.**

**The real axis is BIOS-drawn versus guest-drawn.** The merged set
is what the BIOS paints its own messages with. The FreeDOS boot
path leaves a stock CP437 font in the VGA that matches the
*unpatched* design, and that is what the installer draws with —
which is why extracting VirtualBox's raw `vgafont16` fixed the
screens scripts wait on. That axis is emulator-independent: a
FreeDOS guest on QEMU paints the same unmerged glyphs, and QEMU
escapes the bug only because it scrapes text memory instead of
recognizing pixels.

**A latent consequence to fix with this.**
`backend_qemu.guest_glyph_bank` returns QEMU's pre-merged bank —
the BIOS font, and the *wrong* one for guest-drawn screens. It has
no consumer today, so nothing is broken; it would be wrong the
moment anything recognizes a QEMU screenshot, and the symmetry it
was written for is machinery aimed at the wrong target.

**The fix fits the recognizer's existing shape.** `_match_cell`
already scores two polarities and keeps the lower Hamming
distance, so scoring **both** banks per cell and keeping the best
costs one more pass over a 19-glyph ambiguity surface and reads
both screens — no state, no guessing which font is loaded. The
alternative, tracking the guest's font through its mode sets,
needs state no screenshot carries. Only BIOS-drawn screens are
wrong today and no script waits on one, so this is correctness
owed rather than a live blocker; it is queued because a
systematically misread screen is precisely what hid the original
font bug for as long as it did.

#### T21 — The shipped glyph bank is another project's font, recorded as ours

`src/reliquary/fonts/cp437_8x16.bin` is 4096 bytes carved out of
the host's **QEMU** vgabios by `tools/extract_vga_font.py` — the
pre-merged BIOS font, per T20 — and
`REUSE.toml` sweeps `reliquary/fonts/*.bin` into
`SPDX-FileCopyrightText = "2026 Paul Galbraith"`,
`GPL-3.0-only` — a record of ownership over bytes the project did
not author.

D82 is what makes this worth an entry rather than a shrug: the
incoming test is *could this ship inside a proprietary product?*,
never *is this GPL-compatible?*. It also **supports how the live
path was fixed** — each backend's font is now extracted from the
installation on the host and cached under
`cache/support/<backend>/`, so nothing is vendored and the glyphs
belong to whatever emulator the host has.

What remains is this one file, now used *only* as `recognize`'s
default and as the font `text_recognize.render` draws fixtures
with. Deleting it is not free: the suite would need a synthetic
bank to render against, and the three golden PNGs under
`tests/fixtures/text_recognize/` encode real FreeDOS screens whose
value is exactly that they are real. Un-vendor and regenerate, or
keep it and correct the REUSE record to say what it is — the
choice is the owner's, and either closes the entry.
