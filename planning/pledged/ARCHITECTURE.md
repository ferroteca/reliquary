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
> gap-is-a-bug rule can act on — that rule being stated in the
> root document's own banner (D48).
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
> than holding it for a separate sign-off. **A principle's bar is
> *honored as a rule*, not full delivery** (D48): it cannot be
> exhaustively proven, and holding it here until it is perfect
> keeps every shortfall invisible, which is the worse outcome.
> The condition is that every known residue is filed as a defect
> in the same change — that conversion being the whole point of
> arming it. (Full delivery remains the bar for a *use case*,
> which is a discrete journey and can be tested end to end.)
>
> A principle in force is clarified, retired, or superseded — never
> changed in nature. One pledged here may still be reshaped, its
> number intact, with work already scheduled against it re-checked
> in the same edit. A dead proposal is recorded in
> [DECISIONS.md](../DECISIONS.md) and triggers the planning-doc sweep,
> its P-number the search key.

*(Empty again since 2026-07-27, and empty is the healthy state: a
principle sits here only in the window between the project owing
it and the code honoring it, and that window is meant to be
short. A long occupancy is the thing to be uncomfortable about.*

*P16 — Reliquary is the only interface to a machine — was the last
occupant and held the shelf for a single day: pledged by D57 in
the morning and armed by D62 the same day, when F23 delivered the
two operations that were in violation. It is the shelf working as
designed, and the only entry so far to have been promoted by the
work D34 says rides it rather than by someone noticing later. P5
and P14 were the previous entries and both promoted that other
way: each had stated its own delivery condition — P5 when
milestone 9 landed, P14 when milestone 7's parser refused an
operator-bearing reference — and both conditions were met without
anyone making the move.)*
