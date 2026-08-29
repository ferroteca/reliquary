<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Pledged use cases — awaiting delivery

> **Status:** these are use cases the project has **committed to**
> but hasn't built yet. Work can be done from this list; nothing
> here is a claim about what the code currently does.
>
> A use case moves through three files as it matures. It starts out
> drafted in [proposed/USE-CASES.md](../proposed/USE-CASES.md), moves
> here once we commit to it, and moves to the root
> [USE-CASES.md](../../USE-CASES.md) once the code actually delivers
> it. The root list only holds things that are already built — every
> entry there is true today, which is why it lives at the repository
> root — so committing to a use case is never, by itself, enough to
> put it on that list. All three files share one set of U-numbers:
> numbers are permanent, never reused, and no move — including one
> that goes backward — leaves a placeholder behind. **If the project
> stops meaning a commitment, it withdraws it** back to `proposed/`,
> or rejects it outright — it's never just left sitting here (D44;
> first used by D61). Withdrawing only costs the commitment: the
> number, the text, and every citation of it stay put.
>
> The move onto the root list happens **automatically once delivery
> is complete** (D34): whoever finishes the work that fully meets a
> use case moves it in the same change — adds it to the root list,
> removes it from here — rather than waiting for a separate sign-off.
> The commit that moves it is the whole record, and it should say
> what was delivered; there's no separate
> [DECISIONS.md](../DECISIONS.md) entry for a promotion (D63). It
> takes *full* delivery to trigger the move: a use case that's only
> partly built stays here, because the root list only holds things
> that are fully true — unless the part that's done is really a use
> case of its own, in which case it moves under its own number and
> the rest stays behind in `proposed/`. U5 went through both of
> these in turn (D64).
>
> A use case that's already in force can only be clarified, retired,
> or superseded — never have its actual meaning changed. One that's
> only pledged here can still be reworked freely, keeping its number,
> and any work already scheduled against it gets rechecked as part of
> that same edit. If a proposal dies at any point, it's recorded in
> [DECISIONS.md](../DECISIONS.md) and removed, which triggers the
> planning sweep described in
> [proposed/USE-CASES.md](../proposed/USE-CASES.md); its U-number is
> what you search for to find everything that depended on it.

**U5 — Custom installation** — pledged 2026-08-21 (owner). This
closed the gap that feature adjudication F5 had flagged and left
open, recorded briefly as D110. It's a re-pledge, not a first
pledge: U5 was withdrawn on 2026-07-28 once the split that promoted
**U21** left it behind (D64) — the part that was actually delivered,
milestone 8's parameterization machinery, went onto the current list
under U21's number, and what's left here is the part that isn't
built at all: swapping in a localized installer is a matter of
combining different scripts and media, not a value any parameter can
set. What's left is now being delivered in pieces, matching how the
demand itself splits up. The first piece — the VNC control plane on
QEMU, covering screen and keyboard — was pledged alongside F63 and is
**delivered**. The second — watch-only landmarks — was pledged as
**F65** (owner, 2026-08-24) and is **delivered**; its number is
retired, and it's now specified at
[docs/spec/landmarks.md](../../docs/spec/landmarks.md). The third —
pointer input, `pointing-device`, and `click` — was pledged as
**F66** (owner, 2026-08-25) and is **delivered**; its number is
retired, and it's now specified at
[../../docs/spec/script-spec.md](../../docs/spec/script-spec.md#click).
The fourth — the WinNT platform workflow, the ReactOS codex recipe
that drives a real Win32 setup GUI through those landmarks and that
pointer — was pledged as **F67** (owner, 2026-08-26) and is
**delivered**; its number is retired, and its record is at
[proposed/design/winnt-platform.md](../proposed/design/winnt-platform.md).
The remaining piece, for Win9x, is still pledged here and stands in
[proposed/FEATURES.md](../proposed/FEATURES.md) (F5), moving under
its own decision (D65). Here is U5's current text, as reshaped by
D64:

> - **U5 — Custom installation.** A user wants the German version
>   of Windows. The codex won't carry every language variant —
>   there are too many — so it defines just one standard Windows
>   install. The user finds that blueprint easily (U11), makes a
>   local copy, and customizes it. The blueprint's author saw this
>   need coming, but it isn't something a simple value can fix: a
>   localized edition is a different installer showing different
>   text, and no parameter reaches that. What a parameter *can*
>   reach is covered by U21 instead — this use case is for the
>   need that a parameter can't reach. The blueprint already names
>   both parts it needs — the media it installs from, and the
>   scripts that drive that install — so the user's customized
>   copy points both of them at the localized versions, and each
>   script matches the media it was written for. The user changes
>   what the blueprint points to, outside the script itself, and
>   goes ahead with the install.

**U7 — Materialize on the hypervisor the host provides** — pledged
2026-07-28 (owner). It was drafted on 2026-07-23 by a review that
went looking for the multi-backend work's justification, and found
none: no use case in force named a hypervisor in any role, and the
three roles that once did — export target (U1), import source (U2),
guest-agent vendor (U3) — had all been dropped since, so the gap was
widening rather than closing. Pledging U7 gave two pieces of stalled
work a use case again: **F2**, the adapter layer, was pledged at the
same time and **delivered the same day**, so its number is retired
and the layer is built; **F3**, the second backend, followed on its
own later (2026-08-03) and was split at pledge time into **F50**,
**F51**, and **F52** (D42), with F3's number retiring as part of the
split. F50, F51, and F52 are all delivered now (VirtualBox's
lifecycle and VDI handling, a font recognizer shared across
backends, and VirtualBox's agentless display matching FreeDOS's).
Pledging U7 was necessary for both F2 and F3's descendants, but
wasn't enough on its own for either. **U7 itself stays pledged**:
the adapter layer it called for now exists, but the use case itself
is only met once a machine actually materializes on whatever
hypervisor the host provides, and two of the four adapters (VMware
and Hyper-V) are still stubs that don't claim to support anything.
What F2 delivered is what U7 needed in order to be buildable, not
what U7 itself asks for. The backend-adapter design (now
`design/backend-adapter.md`, its feature delivered) cites U7 as its
reason for existing; F52 closed out the VirtualBox part of the
demand. **A later delivery answered part of the need but didn't
close it** (2026-07-29; D80): `create-machine --dry-run --backend`
lets you ask whether a blueprint would work on a named backend,
based on capability alone, without installing or booting
anything — which checks U7's own contract, but only on paper. A
static answer about whether a backend *would* work isn't the same
as a machine actually materializing on one, so the pledge stands
exactly where it did before. Here is U7's text, as drafted:

> - **U7 — Materialize on the hypervisor the host provides.** A
>   blueprint and its scripts are written once, but the hosts that
>   run them differ — a Windows laptop with Hyper-V already turned
>   on, a CI runner with only QEMU, a workstation with VirtualBox.
>   The machine should materialize on whichever backend the host
>   actually offers that can support it, and the same blueprint
>   and scripts should drive it there unchanged. What matters is
>   whether the backend can do the job, not which backend it is: a
>   blueprint that needs something a backend can't give should
>   fail up front, naming the gap, rather than quietly working
>   worse. Naming a `backend` explicitly is only for when the
>   choice itself matters. Without this, U4's journey breaks down
>   at the second developer's machine — a precisely shared
>   definition only helps if the machine can actually be built on
>   whatever host that developer has.

**U10 — The install is the thing under test** — pledged 2026-08-19
(owner). It was drafted on 2026-07-23: the description of the
control-plane work already talked about testing installs
("os-autoinst-style, where the install is the thing under test"),
but no numbered use case actually owned that idea, even though it's
the reason agentless operation has to stay permanently essential
rather than just being a convenience during bootstrap. Pledging U10
delivers on that missing citation — the control-plane description
(ARCHITECTURE.md) and the two statements that explain why agentless
operation is permanent, P2 (ARCHITECTURE.md) and G1
(docs/spec/script-spec.md), now point to U10. Nothing is built yet;
this use case will be met once a script can drive and watch an
install run through to a pass/fail verdict, with the machine
discarded afterward, entirely without a guest agent. Here is U10's
text, as drafted:

> - **U10 — The install is the thing under test.** An installer or
>   media maintainer runs an install in order to check that the
>   install itself works: what's on screen is what gets checked,
>   the run's record is the verdict, and the machine is thrown away
>   afterward. Agentless operation isn't a fallback here — it's
>   essential, because until the install succeeds there's nothing
>   in the guest that could cooperate with an agent, and the moments
>   before an agent could even exist are exactly the moments under
>   test. Run the same script against a changed installer, and it
>   reports honestly on what actually happened, failing with
>   whatever it actually saw on screen.
