<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
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
> here — rather than holding it for a separate sign-off; the moving
> commit is the record, and no [DECISIONS.md](../DECISIONS.md) entry
> marks a promotion (D63). **A principle's bar is
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

- **P27 — Remanence owns at-rest disk access (amendment: the
  keeps clause shrinks).** **Pledged 2026-08-03** (owner), with
  **F41** ([FEATURES.md](FEATURES.md)), whose delivery lands it.
  The in-force entry reads "Reliquary keeps the policy Remanence
  cannot own: the DOS-only FAT12/FAT16/FAT16B recognition claim
  and its refusal vocabulary, the whole-disk-or-none rule,
  guest-address mapping, rule ids, and translation into the
  recorded drive report" — and F41's inventory shows most of that
  clause is not policy Remanence *cannot* own but policy it does
  not yet offer to. Under the amendment the clause reads:
  Reliquary keeps **guest-address parsing, the rule ids, and the
  recorded drive report** — the recognition claim surviving as
  which report outcomes Reliquary accepts, never as re-derived
  facts; the refusal vocabulary, the whole-disk rule, label and
  name semantics, and the letter algorithm all crossing to the
  dependency with F41's asks. The clause that does not move: the
  dependency still earns the whole layer or none of it, the
  hybrid refusal standing exactly as armed. Amending an in-force
  principle is a P23 act — this entry is the argument pledged for
  it, and it was pledged only together with F41, because a keeps
  clause shrunk before the dependency answers would leave the
  code honoring neither reading.
