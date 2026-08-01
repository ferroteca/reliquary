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
