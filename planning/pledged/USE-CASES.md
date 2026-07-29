<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
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

**Three entries left this shelf on 2026-07-27** (owner; D61) — the
first use of the withdrawal remedy D44 wrote. **U1** condensed to
the journey it uniquely owns and went **up**, to the current list:
its export clause is now U8's, and with that clause gone every
remaining word of it is delivered. **U2** and **U6** went **back**,
to [proposed/USE-CASES.md](../proposed/USE-CASES.md); neither had
any delivery behind it, and both reached this shelf by D44's rename
rather than by a decision to build them. U5 is what survived that
re-test, and it survived on substance — milestone 8's
parameterization machinery is real, shipped, U5-citing work.

**U5 left the next day, and this shelf is now empty** (owner; D64,
2026-07-28). It left by the substance that had saved it: that
machinery was cut out as **U21** and promoted to the current list,
which is what the pledge had bought, and the residue — the
seed-and-customize journey, whose seam is compositional and whose
only carrier is the unpledged GUI era (F5) — went back to
[proposed/USE-CASES.md](../proposed/USE-CASES.md). Not a pledge
broken but a pledge paid, with the unpaid remainder returned to
where unpledged demand lives.

**Both pledged shelves stood empty for the rest of that day** —
this one and [pledged/FEATURES.md](FEATURES.md). The project owed
no undelivered use case and no unbuilt feature, which was a state
rather than a defect: `proposed/` held the argued demand, and what
this file held next would arrive by someone deciding to build it.

**U7 is that arrival** (owner, 2026-07-28), pledged in the same act
as the feature that delivers its first half — the backend adapter
seam, **F2** ([FEATURES.md](FEATURES.md)). The pairing is not a
convenience: a feature may not be pledged ahead of the demand that
justifies it, and this pillar is where that rule was learned. F2
sat in `proposed/` for five days on exactly this lack.

**U7 — Materialize on the hypervisor the host provides** — pledged
2026-07-28 (owner). Drafted 2026-07-23 by the mapping sweep, which
found the multi-backend pillar demand-free: no use case in force
named a hypervisor in any role, and the three non-substrate roles
that once did — export target (U1), import source (U2), guest-agent
vendor (U3) — have all since gone, widening the gap rather than
closing it. The pledge schedules the pair that left the numbered
arc on that lack: **F2**, the adapter seam, pledged in the same
act — and **delivered the same day**, so its number is retired and
the seam is built — and **F3**, the second backend, which follows
whenever it is pledged on its own move; U7's pledge was necessary
for both and sufficient for neither. **U7 stays here**: the seam it
demanded exists, but the case is met when a machine materializes on
the hypervisor a host actually provides, and three of the four
adapters are stubs that claim no capability. What F2 delivered is
what U7 required, not what U7 asks for. The backend-adapter design
(now `design/backend-adapter.md`, its feature delivered), F3, and
**F24** — pledged 2026-07-29, whose `--backend` under `--dry-run`
answers U7's question about a host before there is a host to ask it
on (D79) — cite U7 from here. Text verbatim as drafted:

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
