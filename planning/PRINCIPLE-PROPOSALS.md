<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Principle proposals

> **Status:** the staging ground for changes to the governing
> principles. Nothing here is in force: the standing list —
> [PRINCIPLES.md](../PRINCIPLES.md), at the repository root
> because it describes current reality — holds only the
> principles the project honors today. The lifecycle mirrors
> the use-case one
> ([planning/USE-CASE-PROPOSALS.md](USE-CASE-PROPOSALS.md)):
> proposed and in-force principles share one global
> P-namespace, numbers are permanent and never reused, a
> principle in force is clarified, retired, or superseded —
> never changed in nature — while a proposed one may still be
> reshaped freely here (its number stays; work already
> scheduled against it is re-checked in the same edit), and a
> proposal moves over when the project actually honors it,
> with no placeholder left behind. A dead proposal is recorded in
> [DECISIONS.md](DECISIONS.md) and triggers the same
> planning-doc sweep, its P-number the search key.

## Open proposals

### Accepted — awaiting delivery

**P5 — The feedback split** — accepted; moved from the
standing list 2026-07-23 by the delivery pass: the principle
is run-scoped, and the machine-readable run rendering does not
exist yet — no run-events stream, no `--progress` renderers
(the flag appears only in an error message today). The query
half (`--json`) is real, but the run half is milestone 9's
work, whose scheduling — it cites the split — is this
proposal's acceptance. P5 returns to the standing list when
milestone 9 lands. Statement and prose verbatim:

> - **P5 — The feedback split.** One run, two renderings: pretty
>   and legible for a person, machine-readable and just as
>   timely for a program — neither scraped from the other.

> Alongside these runs a feedback split (P5). Reliquary's runs
> are long, and whoever drives one gets timely progress —
> presented for the driver. A person at the CLI (U1, U5) gets
> pretty, legible, real-time progress; an automating program
> (U3, U4) gets machine-readable output that is just as timely.
> The two are renderings of the same run, and neither is
> derived by scraping the other: the pretty rendering is never
> what a program parses, and the machine rendering is never
> what a person is left to read.

### Drafted

**P13 — Property sources** — drafted (add, 2026-07-23; the
owner's name for it — the house noun: script-properties.md's
own section, D19's title). The principle-sized kernel of the
property source model, distinct from the tier list, which
stays design (normative in
[planning/design/script-properties.md](design/script-properties.md)).
Delivery is milestone 8; citing P13 there is its acceptance.
The secret-custody contract (credential store, redaction)
stays with the spec; whether it earns its own principle is
open. Statement:

> - **P13 — Property sources.** Values reach a run through one
>   layered chain: every source speaks the same declared keys,
>   the flattened precedence is semantics — never per-user
>   configuration — and growth happens only at the named seams
>   (a new tier by design decision, provider plurality behind
>   a capability contract, programmatic injection with custody
>   in code), with every resolution recording its supplying
>   source. Custody and introspection, not a frozen order, are
>   what make layering safe. (Normative:
>   planning/design/script-properties.md; D19, D20.)

**P14 — The expressive ceiling** — drafted (add, 2026-07-23;
the format re-examination round, D26). The principle-sized
kernel of a rule the project has been applying surface by
surface without ever stating it as one: scripts got a
purpose-built constrained language rather than a general one
(D12, G7), blueprints stay logic-free in the tree (D18) and
now in the strings (D26), and computation's designated home is
the layer above (G2). Delivery is milestone 7, where the
blueprint half becomes a parser that refuses an
operator-bearing reference; citing P14 there is its
acceptance. What is deliberately NOT in it: how far a
reference may *reach*, which is a different axis with the
opposite economics (widening is cheap, narrowing is not) and
stays a design call. Statement:

> - **P14 — The expressive ceiling.** Every authored surface is
>   given an expressive ceiling and holds it: a logic-bearing
>   surface gets a purpose-built, deliberately constrained
>   language, and a declarative surface stays logic-free —
>   closed in the tree and closed in the strings alike. When
>   the ceiling binds, the answer is another layer —
>   generation above, or an evaluation step producing the plain
>   format — arriving as its own kind, never as a wider dialect
>   of the surface it feeds. The ceiling is stated as a closed
>   grammar ahead of
>   the pressure, because each request to raise it arrives
>   individually well justified, and a format that grants them
>   one at a time cannot take them back. (Normative:
>   planning/design/machine-blueprint.md "Format stability",
>   planning/design/script-spec.md "How the vocabulary grows";
>   D12, D18, D26.)

### Tracked

- **Itemize ROADMAP's remaining design principles** — tracked
  (recorded 2026-07-23; previously a candidates note inside
  PRINCIPLES.md). One script, one target; installation media
  is input, disk images are output; dependencies pull their
  weight — each already normative in ROADMAP "Design
  principles", absorbed here under a P-number as it proves
  cross-cutting.
