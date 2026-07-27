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

*(It was empty from D47 until P16 arrived. P5 and P14 were the
previous entries and both promoted: each had stated its own
delivery condition — P5 when milestone 9 landed, P14 when
milestone 7's parser refused an operator-bearing reference — and
both conditions were met without anyone making the move D34 says
rides the work. An empty shelf is the healthy state rather than a
gap to fill: a principle sits here only in the window between the
project owing it and the code honoring it, and that window is
meant to be short. A long occupancy is the thing to be
uncomfortable about.)*

**P16 — Reliquary is the only interface to a machine** — pledged
2026-07-27 (D57, which adjudicated the four questions the draft
left open; drafted 2026-07-23). Owner's proposal, verbatim: *"All
foreseeable interaction with a VM should be through Reliquary. A
known use case which expects out-of-band access to fulfil the
user's goal, would violate this principle."* Rests on **U14** —
the inject-execute-observe loop, in force since U3 retired into it
(D51) — and **U20**.

**THE TEST, WHICH IS THE WHOLE PRINCIPLE:**

> Can every supported use case be completed without the consumer
> reaching around Reliquary?

**The obligation binds Reliquary, not the user** (owner, D57).
Consumers can always reach around — a stopped machine's drives are
plain host state and always will be — and nobody should be
surprised when they do. What P16 forbids is *requiring* it: a
supported use case whose completion needs the consumer to fetch
for themselves is the violation, and reaching around is then a
capability gap wearing a workflow's clothes.

**THE MECHANISM IS INVISIBLE TO THE TEST** (owner, D57, dissolving
the draft's third question). That Reliquary serves `get-file` out
of a vvfat host directory is an implementation detail and no
concern of this principle. The question is never what Reliquary
uses; it is whether a Reliquary verb answers the need.

WHAT IT DOES NOT ASSERT, or it will over-read on first citation:

- **Export is a handoff, not a breach.** `export-machine` ends
  with Reliquary letting go on purpose (P1); the artifact leaves
  its purview by design. P16 governs machines Reliquary still owns.
- **The guest's own world is untouched.** Guest logs, guest
  history, and what a person does at a console are the guest's, as
  the transcript-redaction contract already says.
- **It is not the closed input model.** P15 closes how *authored
  input* reaches Reliquary; P16 closes how *interaction with a
  running or stopped machine* does.
- **It is not a rule about escape hatches.** `--display` and `hmp`
  are extras rather than routes: no use case requires either, so
  neither is in violation. The consumer-obligation test settles
  this without a scope list, which is why the draft's reach
  question needed no separate answer.

**WHAT IT COSTS, ALREADY PRICED** (D57). Under the test, QEMU/DOS
complies for everything a verb serves — single-file exchange
since `put-file` / `get-file` landed at milestone 9 — and violates
it in exactly two places: **listing and whole-tree transfer**,
where a consumer needing either must read the drive directory
themselves. Those become owed work rather than deferred
convenience, pledged as [F23](../pledged/FEATURES.md) and
decoupled from the second backend they had been sequenced against.

**WHAT WOULD ARM IT.** Promotion to the root list when those two
needs are served by Reliquary verbs, with every remaining residue
filed as a defect in the same change (D48's bar: *honored as a
rule*, not exhaustively proven). The known residue to expect is
backends with no vvfat equivalent, where the out-of-band route is
the only one that exists — capability honesty (P11) names such a
gap rather than hiding it, and a named gap is not a silent
violation.
