<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Pledged architecture — awaiting delivery

> **Status:** principles the project has **pledged** but does not
> yet honor. Nothing here is in force: a principle only binds once
> it reaches the standing list in root ARCHITECTURE.md, and if the
> code falls short of an entry below, that's just work not done
> yet — not a bug.
>
> That's the whole reason this file exists separately from the root
> one. Moving a principle to the root list is what makes it binding:
> before that move, an entry here is just a pledge; after it, root
> [ARCHITECTURE.md](../../ARCHITECTURE.md) is claiming the thing is
> actually true of the code, so from that point on, any gap between
> the code and the entry is a bug — that's the gap-is-a-bug rule
> stated in the root document's own status note (D48).
>
> A principle moves through three files as it matures. It starts out
> drafted in [proposed/ARCHITECTURE.md](../proposed/ARCHITECTURE.md),
> moves here once it's pledged, and moves to the root list once the
> code actually honors it. All three files share one P-number
> namespace: numbers are permanent, never reused, and no move —
> either one — leaves a placeholder behind.
>
> The move to the root list happens **automatically once the code
> honors the principle** (D34): whoever lands the work that gets the
> code there moves the principle in the same change — adds it to the
> root list, removes it from here — rather than waiting for separate
> sign-off. The commit that moves it is the whole record; there's no
> separate [DECISIONS.md](../DECISIONS.md) entry for a promotion
> (D63). The bar for moving a principle is lower than the bar for
> moving a use case: a principle only has to be **honored as a
> rule** (D48) — there's no way to prove a rule is followed
> everywhere, and refusing to promote it until that's proven would
> just hide every real shortfall instead of tracking it. So the
> condition for promotion is that every known shortfall gets filed
> as its own defect in the same change that promotes the principle —
> filing those defects is what makes the promotion honest. A use
> case is different: it's a specific journey you can test start to
> finish, so it waits for full delivery before it moves.
>
> A principle already in force can only be clarified, retired, or
> superseded — never have its actual meaning changed. One that's
> only pledged here can still be reworked freely, keeping its
> number; any work already scheduled against it gets rechecked as
> part of that same edit. If a proposal dies at any point, it's
> recorded in [DECISIONS.md](../DECISIONS.md) and removed, which
> triggers the planning-doc sweep; its P-number is what you search
> for to find everything that cited it.
