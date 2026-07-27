<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Pledged architecture — awaiting delivery

> **Status:** principles the project has **pledged** but does not
> yet honor. Nothing here is in force: a principle only binds once
> it reaches the standing list, and a shortfall against an entry
> below is unbuilt work rather than a bug.
>
> That distinction is the point of this file. **Promotion is what
> arms a principle**: before it, an entry is pledged vision; after
> it, root [ARCHITECTURE.md](../../ARCHITECTURE.md) asserts the thing is
> true of the code, so a divergence becomes a *defect* the
> gap-is-a-bug rule can act on.
>
> Three locations hold three states. A principle is drafted in
> [proposed/ARCHITECTURE.md](../proposed/ARCHITECTURE.md), moves here
> when it is pledged, and moves to the root list when the code
> actually honors it. All three share one global P-namespace;
> numbers are permanent, never reused, and no placeholder is left
> behind by either move.
>
> The second move is **automatic on full delivery** (D34): whoever
> lands the work that makes the code honor a principle promotes it
> in the same change — adds it to the standing list, deletes it
> here, records the move in [DECISIONS.md](../DECISIONS.md) — rather
> than holding it for a separate sign-off. Full delivery, not
> pledge, is the trigger: a partly-honored principle stays here,
> since the standing list is an implementation claim.
>
> A principle in force is clarified, retired, or superseded — never
> changed in nature. One pledged here may still be reshaped, its
> number intact, with work already scheduled against it re-checked
> in the same edit. A dead proposal is recorded in
> [DECISIONS.md](../DECISIONS.md) and triggers the planning-doc sweep,
> its P-number the search key.

**Empty today** (D47, 2026-07-27). P5 and P14 were the last two
entries and both promoted: each had stated its own delivery
condition — P5 when milestone 9 landed, P14 when milestone 7's
parser refused an operator-bearing reference — and both conditions
were met without anyone making the move D34 says rides the work.

An empty shelf is the healthy state rather than a gap to fill: a
principle sits here only in the window between the project owing it
and the code honoring it, and that window is meant to be short. A
long occupancy is the thing to be uncomfortable about.
