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
**F51** / **F52** (D42), F3 retiring with the split; **F50 is
delivered** (VirtualBox lifecycle and VDI). U7's pledge was
necessary for both and sufficient for neither. **U7 stays here**:
the seam it demanded exists, but the case is met when a machine
materializes on the hypervisor a host actually provides, and two
of the four adapters are still stubs that claim no capability
(VirtualBox's display plane is F51–F52). What F2 delivered is what
U7 required, not what U7 asks for. The backend-adapter design (now
`design/backend-adapter.md`, its feature delivered) and F51–F52
cite U7 from here. **A second delivery answered part of it and moved it
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
