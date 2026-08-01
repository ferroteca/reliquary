<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Proposed architecture

> **Status:** the staging ground for changes to the architecture —
> new principles, model changes, retirements — argued here before
> anything is pledged. **Nothing here is pledged, and nothing is worked
> from here.** The lifecycle mirrors the use-case one
> ([proposed/USE-CASES.md](USE-CASES.md)) and runs across three
> locations: drafted here, then **pledged** — moved to
> [pledged/ARCHITECTURE.md](../pledged/ARCHITECTURE.md), the move
> itself the record — then in force, moved again into root
> [ARCHITECTURE.md](../../ARCHITECTURE.md), which sits at the
> repository root because it describes current reality: the shipped
> system's model, and only the principles the project honors
> today.
>
> All three share one global P-namespace; numbers are permanent
> and never reused, and no placeholder is left behind by either
> move. A principle in force is clarified, retired, or superseded —
> never changed in nature — while a proposed one may still be
> reshaped freely here (its number stays; work already scheduled
> against it is re-checked in the same edit). The second move is
> **automatic** (D34), and its trigger is delivery rather than
> pledge — for a principle, *honored as a rule* with every known
> residue filed as a defect in the same change (D48), never the
> full-delivery bar a use case answers to. A dead proposal is recorded in
> [DECISIONS.md](../DECISIONS.md) and triggers the same
> planning-doc sweep, its P-number the search key.

- **P27 — Remanence owns at-rest disk access (amendment: the
  keeps clause shrinks).** Argued with **F41**
  ([FEATURES.md](FEATURES.md)), whose delivery would land it. The
  in-force entry reads "Reliquary keeps the policy Remanence
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
  principle is a P23 act — this entry is the argument staged for
  it, and it is pledged only together with F41, because a keeps
  clause shrunk before the dependency answers would leave the
  code honoring neither reading.
