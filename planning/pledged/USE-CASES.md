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

**U5 — Custom installation** — pledged 2026-08-21 (owner), the
demand adjudication F5's banner left open, recorded slim as D110.
Re-pledged rather than first pledged: withdrawn 2026-07-28 as the
residue of the split that promoted **U21** (D64) — the delivered
substance, milestone 8's parameterization machinery, went current
under that number, and what remains is the journey none of which is
built: the localized-installer seam is compositional, the half no
value can reach. Its carrier divides now as the demand does: the
first cut — the VNC control plane on QEMU, screen and keyboard —
was pledged in the same act as F63 and is **delivered**; the
second — watch-only landmarks — was pledged as **F65** (owner,
2026-08-24) and is **delivered**, its number retired and its
surface normative at
[docs/spec/landmarks.md](../../docs/spec/landmarks.md); and the rest of the GUI
era — pointer input and `click`, the platform workflows — stands
in [proposed/FEATURES.md](../proposed/FEATURES.md) (F5) on this
pledge, each piece still moving by its own decision (D65). Text
verbatim as reshaped by D64:

> - **U5 — Custom installation.** A user wants the German
>   version of Windows. The codex will not carry such flavors —
>   there are too many variants — so it defines one standard
>   Windows install. The user finds that blueprint easily (U11),
>   seeds a local copy, and customizes it. The author has
>   foreseen the need, and the seam this one takes is
>   compositional rather than a value: a localized edition is a
>   different installer showing different text, which no
>   parameter can reach. The blueprint already names both
>   halves — the media it installs from and the scripts that
>   drive it — so the customized copy points both at the
>   localized pair, each script standing alone against the media
>   it was written for. The user changes what the blueprint
>   names, outside the script, and proceeds. The values an author
>   *can* parameterize are U21's; this is the case values cannot
>   reach.

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

**U10 — The install is the thing under test** — pledged 2026-08-19
(owner). Drafted 2026-07-23: the control-plane arc's prose already
named install-testing ("os-autoinst-style, where the install is the
thing under test") but no numbered case owned it, and it is the use
that makes agentless operation permanently essential rather than a
bootstrap convenience. The pledge carries the citation it promised:
the arc's prose (ARCHITECTURE.md) and the two agentless-permanence
statements that derive from it — P2 (ARCHITECTURE.md) and G1
(docs/spec/script-spec.md) — now name U10. Nothing is built yet; the
case is met when a script can drive and observe an install run to a
pass/fail verdict with the machine discarded, purely agentlessly.
Text verbatim as drafted:

> - **U10 — The install is the thing under test.** An installer
>   or media maintainer runs an install to prove the install:
>   the screen is the assertion surface, the run record is the
>   verdict, and the machine is discarded. Agentless operation
>   is essential here, not a fallback — until the install
>   succeeds there is nothing in the guest to cooperate, and
>   the moments before an agent could exist are exactly the
>   ones under test. The same script observes a changed
>   installer honestly, failing with the screen it actually
>   saw.
