<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Pledged use cases — awaiting delivery

> **Status:** use cases the project has **pledged** but does not
> yet meet. Work may be done from here; nothing here is a claim
> about the code.
>
> Three locations hold three states. A use case is drafted in
> [proposed/USE-CASES.md](../proposed/USE-CASES.md), moves here when
> it is pledged, and moves to root
> [USE-CASES.md](../../USE-CASES.md) when the code actually meets
> it. The root list is implemented-only — every entry there is met
> today, which is why it lives at the repository root — so
> pledge alone can never put an entry in it. All three share
> one global U-namespace; numbers are permanent, never reused, and
> no placeholder is left behind by any move — including the one
> that runs backwards. **A pledge the project does not mean is
> withdrawn** to `proposed/` or rejected outright, never left
> sitting (D44; first used by D61). Withdrawal costs the
> commitment and nothing else: the number, the text and every
> citation stand.
>
> The second move is **automatic on full delivery** (D34): whoever
> lands the work that fully meets a use case promotes it in the same
> change — adds it to the root list, deletes it here — rather than
> holding it for a separate sign-off. The moving commit is the whole
> record, and the delivery evidence belongs in its message; no
> [DECISIONS.md](../DECISIONS.md) entry marks a promotion (D63). *Full* delivery is the trigger: a use case
> whose work has partly landed stays here, since the root list is an
> implementation claim — unless the delivered part is a use case in
> its own right, in which case it is promoted under its own number
> and the remainder returns to `proposed/`. U5 did both in turn
> (D64).
>
> A use case in force is clarified, retired, or superseded — never
> changed in nature. One pledged here may still be reshaped, its
> number intact, with work already scheduled against it re-checked
> in the same edit. A proposal that dies at any point is recorded in
> [DECISIONS.md](../DECISIONS.md) and removed, triggering the planning
> sweep described in
> [proposed/USE-CASES.md](../proposed/USE-CASES.md); its U-number is
> the search key.

**U24 — A script says what a stage boots, and hands the machine back
as it found it** — pledged 2026-08-13 (owner), drafted the same day
from a live FreeDOS install on VirtualBox. The pledge cuts **F54**
straight to [pledged/FEATURES.md](FEATURES.md) in the same act; F54
is this use case's whole delivery, so the promotion to root
[USE-CASES.md](../../USE-CASES.md) rides with it (D34) rather than
waiting on a second judgement. The settlements the round made — the
construct's shape, and the rule its restore obeys — are **D104**.

**Two findings made it a demand rather than a preference.** *Firmware
fallthrough is not portable*: both backends skip an empty optical
drive, but only SeaBIOS moves past a disk partitioned without an
active partition — VirtualBox stops there, which is precisely the
state every installer leaves behind before its reboot. And *a script
cannot restore what it changes*: `set-boot` is stopped-only (D15's
Q1, a launch-time firmware order with no live effect — cited, not
reopened), so the flip precedes `start` and the restore follows the
machine stopping, with no `finally` in the language to hold the two
together. Any failure in between — most runs, while a script is being
written — leaves the boot order silently disagreeing with the
blueprint until someone runs `apply-blueprint`.

**A third finding is deliberately not part of this use case.** The
run-time refusal of a `set-boot` against a running machine arrives
after five minutes of installing, where the declared `machine
stopped` header and the start/stop verbs make it decidable at parse
time. That stands whether or not U24 is ever built — `set-boot` does
not go away — so it is queued on its own as **T27** rather than
folded in here, and F54's exit check reuses its analysis.

**What the pledge does not claim, found while working F54.** A
guest-driven reboot is not Reliquary's `stop`/`start`: the VM never
stops, the firmware simply runs again under the order it was launched
with, and nothing Reliquary offers can reach in between. So the
device cannot change *within* one boot, and the codex install
script's mid-install `eject` — how the disk is reached across the
installer's own reboot — stays exactly where it is. What U24 buys is
the other half: the machine returns to its declared shape, so the
blueprint stops permanently expressing a condition that is true only
while one install runs. The workaround shipped in `df37b0a` — a
CD-first blueprint — is what that describes, and it is a workaround
for exactly that reason, one that does not generalize to a guest
needing a third order later. Text as pledged:

> - **U24 — A script says what a stage boots, and hands the machine
>   back as it found it.** An install is not one boot: the installer
>   medium boots first, the disk boots once it is bootable, and which
>   of them the firmware chooses is not the same question on two
>   backends — both skip an empty optical drive, only one moves past
>   a disk partitioned without an active partition, and that is
>   exactly the state an installer leaves behind before its own
>   reboot. So a script states the boot device for a stage of its run
>   rather than arranging for the firmware to fall past the wrong
>   one, and states it once: what a stage changes about the
>   machine — which device it boots first, the medium in a
>   removable slot — is
>   undone when the stage ends, whether it ended by finishing, by
>   failing, or by being cancelled. The machine handed back is the
>   machine that was picked up, so a blueprint never has to
>   permanently express a condition that holds only while one install
>   runs. What the author did not scope still stands: an installer's
>   writes to a disk are the machine's own history and no script
>   undoes them, and `apply` remains the recovery for a machine that
>   diverged some other way.

**U7 — Materialize on the hypervisor the host provides** — pledged
2026-07-28 (owner). Drafted 2026-07-23 by the mapping sweep, which
found the multi-backend pillar demand-free: no use case in force
named a hypervisor in any role, and the three non-substrate roles
that once did — export target (U1), import source (U2), guest-agent
vendor (U3) — have all since gone, widening the gap rather than
closing it. The pledge schedules the pair that left the numbered
arc on that lack: **F2**, the adapter seam, pledged in the same
act — and **delivered the same day**, so its number is retired and
the seam is built — and **F3**, the second backend, which followed
on its own move (2026-08-03) and was cut at pledge into **F50** /
**F51** / **F52** (D42), F3 retiring with the split; **F50**,
**F51**, and **F52** are delivered (VirtualBox lifecycle/VDI, the
shared fixed-font recognizer, and VirtualBox agentless display with
FreeDOS parity). U7's pledge was
necessary for both and sufficient for neither. **U7 stays here**:
the seam it demanded exists, but the case is met when a machine
materializes on the hypervisor a host actually provides, and two
of the four adapters are still stubs that claim no capability
(VMware and Hyper-V). What F2 delivered is what
U7 required, not what U7 asks for. The backend-adapter design (now
`design/backend-adapter.md`, its feature delivered) cites U7 from
here; F52 closed the VirtualBox half of the demand. **A second
delivery answered part of it and moved it
no closer** (2026-07-29; D80): `create-machine --dry-run --backend`
asks whether a blueprint would work on a named backend, capability
alone deciding, with nothing installed and nothing booted — U7's own
contract, checked statically. A static answer about a backend is not
a machine materialized on one, so the pledge stands exactly where it
did. Text verbatim as drafted:

> - **U7 — Materialize on the hypervisor the host provides.** A
>   blueprint and its scripts are written once; the hosts that
>   run them differ — a Windows laptop with Hyper-V already
>   enabled, a CI runner with only QEMU, a workstation with
>   VirtualBox. The machine materializes on whatever capable
>   backend the host offers, and the same blueprint and scripts
>   drive it there unchanged. Capability, not identity, is the
>   contract: a blueprint needing what a backend cannot give
>   fails closed naming the gap, never silently degrading;
>   declaring a `backend` explicitly is the exception, for when
>   the choice is the point. Without this, U4's journey breaks
>   at the second developer's host: a precisely shared
>   definition only helps if the machine can be built where
>   that developer is.
