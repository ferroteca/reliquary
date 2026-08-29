<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Proposed architecture

> **Status:** this is where changes to the architecture are drafted —
> new principles, changes to the model, retirements — and argued for
> before anything is pledged. **Nothing here is pledged, and no work
> is done from this list.** The lifecycle mirrors the use-case one
> ([proposed/USE-CASES.md](USE-CASES.md)) and runs across three
> files: a principle is drafted here, then **pledged** — moved to
> [pledged/ARCHITECTURE.md](../pledged/ARCHITECTURE.md), the move
> itself the record of the decision — then, once it's in force,
> moved again into root [ARCHITECTURE.md](../../ARCHITECTURE.md).
> The root file sits at the repository root because it describes
> current reality: the shipped system's model, and only the
> principles the project actually honors today.
>
> All three files share one P-number namespace: numbers are
> permanent and never reused, and no move leaves a placeholder
> behind. A principle already in force can only be clarified,
> retired, or superseded — never have its actual meaning changed —
> while a proposed one, still here, can be reshaped freely: it keeps
> its number, and any work already scheduled against it gets
> rechecked as part of the same edit. The second move — into the
> root file — happens **automatically** (D34), and what triggers it
> is delivery, not pledging: for a principle, that means being
> **honored as a rule**, with every known shortfall filed as its own
> defect in the same change (D48). That's a lower bar than the
> full-delivery bar a use case has to meet before it moves. If a
> proposal dies, it's recorded in [DECISIONS.md](../DECISIONS.md)
> and removed, which triggers the same planning-doc sweep; its
> P-number is what you search for to find everything that cited it.
