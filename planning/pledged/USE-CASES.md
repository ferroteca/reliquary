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
> change — adds it to the root list, deletes it here, records the
> move in [DECISIONS.md](../DECISIONS.md) — rather than holding it for
> a separate sign-off. *Full* delivery is the trigger: a use case
> whose work has partly landed stays here, since the root list is an
> implementation claim (milestone 8 pledged U5, but its canonical
> scenario waits on the GUI era, F5).
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

**U5 — Custom installation** — pledged; moved back from the
current list 2026-07-23 (owner: an in-force use case whose
delivery is unscheduled is a real problem — proposed is the
honest state). Its canonical scenario — a customized Windows
install — waits on the unscheduled GUI era (F5); the
parameterization machinery lands at milestone 8 — the
scheduled, U5-citing work that constitutes its pledge,
while the unscheduled scenario is why it is not current. U5
lives only
here while undelivered — the shared U-namespace keeps every
existing citation valid — and returns to the current list when
the delivery is real. Text verbatim as adopted:

> - **U5 — Custom installation.** A user wants the German version
>   of Windows. The codex will not carry such flavors —
>   there are too many variants — so it defines one standard
>   Windows install. From the CLI the user easily finds that
>   standard blueprint, seeds a local blueprint from it, and
>   customizes it. The blueprint's author has foreseen this need
>   and wrote it with an obvious locale seam; the user changes the
>   language to German — preferably in the blueprint, outside the
>   script, so the script can stand alone — and proceeds. A user
>   name and a license key are equally obvious examples of
>   blueprint parameterization — and they show its two bindings:
>   some parameters are specified directly in the blueprint, while
>   others are only *referred to* there and must be defined
>   externally. A license key is never checked into source
>   control, so Reliquary must provide a mechanism to store it
>   locally and retrieve it at use. The same parameter can go
>   either way: an automated-testing blueprint may fix its user
>   name as "testuser", while "paul" is a value its owner would
>   never check in.
