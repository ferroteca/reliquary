<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Accepted architecture — awaiting delivery

> **Status:** principles the project has **accepted** but does not
> yet honor. Nothing here is in force: a principle only binds once
> it reaches the standing list, and a shortfall against an entry
> below is unbuilt work rather than a bug.
>
> That distinction is the point of this file. **Promotion is what
> arms a principle**: before it, an entry is accepted vision; after
> it, root [ARCHITECTURE.md](../../ARCHITECTURE.md) asserts the thing is
> true of the code, so a divergence becomes a *defect* the
> gap-is-a-bug rule can act on.
>
> Three locations hold three states. A principle is drafted in
> [proposed/ARCHITECTURE.md](../proposed/ARCHITECTURE.md), moves here
> when it is accepted, and moves to the root list when the code
> actually honors it. All three share one global P-namespace;
> numbers are permanent, never reused, and no placeholder is left
> behind by either move.
>
> The second move is **automatic on full delivery** (D34): whoever
> lands the work that makes the code honor a principle promotes it
> in the same change — adds it to the standing list, deletes it
> here, records the move in [DECISIONS.md](../DECISIONS.md) — rather
> than holding it for a separate sign-off. Full delivery, not
> acceptance, is the trigger: a partly-honored principle stays here,
> since the standing list is an implementation claim.
>
> A principle in force is clarified, retired, or superseded — never
> changed in nature. One accepted here may still be reshaped, its
> number intact, with work already scheduled against it re-checked
> in the same edit. A dead proposal is recorded in
> [DECISIONS.md](../DECISIONS.md) and triggers the planning-doc sweep,
> its P-number the search key.

**P5 — The feedback split** — accepted; moved from the
standing list 2026-07-23 by the delivery pass: the principle
is run-scoped, and the machine-readable run rendering does not
exist yet — no run-events stream, no `--progress` renderers
(the flag appears only in an error message today). The query
half (`--json`) is real, but the run half is milestone 9's
work, whose scheduling — it cites the split — is this
proposal's acceptance. The 2026-07-24 async deferral (D35)
and the return-not-store revision (D36) leave P5 whole within
milestone 9: its two-rendering demand is on the run's *own
driver* — pretty and machine-readable, both live — which the
`--progress` renderers deliver as **live output**, never a
stored file (persistence was async's substrate and went with it,
D36). Detach and cross-process following (backlogged) are not
P5's concern. P5 returns to the standing list when milestone 9
lands. Statement and prose verbatim:

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

**P14 — The expressive ceiling** — accepted (add, 2026-07-23;
the format re-examination round, D26). The principle-sized
kernel of a rule the project has been applying channel by
channel without ever stating it as one. THE ARCHITECTURE IS
P15'S — three authored channels and one invocation channel —
and P14 governs THE AUTHORED THREE ONLY, the invocation channel
being floored rather than capped and staying with P6/P7. What
P14 adds is that each authored channel holds a CEILING, and
that the refusals are symmetric: a spec never grows
expressions, a script never nests a second format, a property
never gains a transform.

WHERE IT ANCHORS — P14 asserts nothing new. It is what three
principles ALREADY IN FORCE require of the authored inputs,
gathered into one standing rule so they survive pressure that
arrives one convenient feature at a time:

- **P7, the binding constraint.** A pillar that grows a
  language becomes hard to EMIT from C or Java — reading it
  needs a parser, writing it needs the language. That is
  precisely why D26 declined HCL2, whose writer exists only in
  Go.
- **P6, one semantic surface.** Specs are documents the
  embedding API writes as well as reads. A spec that must be
  evaluated before it means anything can be read but not
  emitted, and the CLI/API twinning breaks on the half that
  cannot be written.
- **P4, the artifact-residency split.** Automation artifacts
  are source in the consuming project's tree — and source is
  what a schema checks and an editor completes. A spec needing
  evaluation before it can be checked stops behaving like the
  checked-in source P4 requires.

Two more govern how it operates rather than why it exists:
pressure against a ceiling routes to a decision under the
interface-change rule (**P8**), and the window in which a
breach is still recoverable closes at 1.0 (**P9**).

The instances, each argued alone at the time and none of them
citing the others:

- **The script channel** got a purpose-built, line-oriented DSL
  rather than an embedded general language, and D12 then
  refused JSON islands inside it — a data format nested in the
  logic channel is the same breach seen from the other side.
- **The spec tree** stays logic-free (D18), with in-tree
  function objects (the CloudFormation `Fn::` shape) and
  string templating (the Helm shape) permanently rejected.
- **The spec strings** close at two fixed productions (D26 as
  corrected by D27), so an operator-bearing reference is a
  parse error and not a judgment call.
- **The property channel** put it most bluntly of the three,
  and had done so before this round noticed:
  script-properties.md already reads *transforms in derivation
  syntax are permanently out — normalization lives in a fact's
  definition, arbitrary computation in the embedding API's
  provider seam*. The same rule and the same escape, written
  for values. Its authored source sits lower still —
  machine-rewritten `key=value`, which left JSON behind because
  a file a program rewrites needs less, not more (D18).

What the ceiling does NOT forbid matters as much, or it will
be misread as hostility to every convenience: a bounded
declarative construct that ENRICHES VALUES may land as data
and be expanded by Reliquary — a variant matrix on the
GitHub-Actions shape, say — argued on its own when it earns
its keep (D18). What the ceiling refuses is computation that
DECIDES STRUCTURE. And a construct can still die for reasons
the ceiling knows nothing about: the `children` glob D18
floated was killed by D22 on the static-catalog rule — a name
may never depend on a download — which is not P14's doing and
must not be recorded as such. Computation itself lives OUTSIDE
all three channels — in the caller's own language, reached
through either door (G2). It is not a Reliquary capability, so
it is not an API-only one either, and the CLI user's host
language is the shell, which P7 already requires be easy to
drive Reliquary from.

THE DANGERS ARE OBSERVED, NOT HYPOTHETICAL, and naming them is
the point — a ceiling nobody can price is a ceiling that gets
traded away. Helm charts are Go templates rendered to text
before anything parses them as YAML: Kubernetes publishes an
excellent schema and a chart cannot use it, indentation becomes
the template engine's problem rather than the format's, and
errors report against rendered text the author never wrote.
CloudFormation carries `Fn::` objects and `!Sub` shorthand as
two spellings of one thing, forever, because removing either
would break stacks in the field. HCL2's expression language is
fluent to author and effectively unemittable outside Go, which
is the P7 failure D26 declined it on. EVERY ONE OF THESE
ARRIVED ONE WELL-JUSTIFIED FEATURE AT A TIME — no maintainer
approved a template engine; each approved a default, then a
conditional, then a filter. That ratchet is what the closure
exists to stop, and it is why the moment to refuse is before
the first request rather than during it, when the request will
have a real user and a good case behind it.
Locally the bill would fall on U4 and U5 (the published
schema's validation and completion, which is what the plain
format was chosen to buy), on P6 (an embedding API that can
read blueprints but no longer emit them), and on P7. And it is
PRICED BY THE CALENDAR: pre-1.0 a breach is still recoverable
under D25, and at 1.0 it stops being — so the window in which
this principle is cheap to hold is the window the project is
in right now.

TWO OF THE THREE ARE ALREADY HONORED: the script channel in
landed code — the language is the constrained one it was
designed to be, growing under G7 — and the property channel in
normative design, its refusal written before this round found
it. ONLY THE SPEC CHANNEL WAITS, and on one deliverable:
milestone 7's parser, honored when it refuses an
operator-bearing reference. The milestone's citation of P14 is
this acceptance, and P14 joins the standing list when the
milestone lands. What is deliberately NOT in it: how far a
reference may *reach*, which is a different axis with the
opposite economics (widening is cheap, narrowing is not) and
stays a design call. THE GUARD AGAINST CONFUSING THE TWO is one
question — does the change alter what may appear BETWEEN the
braces, or only WHERE the braces may appear? Take one field,
`controller`, and two requests against it. Admitting `${key}`
there, which D26's trim currently refuses, is POSITION: it is
granted or refused on whether a named case has finally appeared,
and P14 must never be cited against it, because P14 does not
govern reach at all — nor does it license narrowing reach, on
which it is equally silent. Admitting `${key:-ide}` there is
BODY: refused by P14 outright whatever the demand, and it
routes to a layer decision instead. Note it PASSES the
character class — `:` and `-` are both legal — and is refused
by the production, the text before the first colon being the
qualifier and `key` not being one. The class screens; the
productions decide (D27). The first is a design call that can be taken back; the
second cannot, which is the whole reason they are governed
differently. Statement:

> - **P14 — The expressive ceiling.** Each of P15's three
>   authored channels holds an expressive ceiling, and none
>   takes on another's job: a spec never grows expressions,
>   closed in its tree and its strings alike; a script never
>   nests a second format; a property never gains a transform.
>   Ceilings are stated as closed grammars ahead of the
>   pressure, because every request to raise one arrives
>   individually well justified and a channel that grants them
>   one at a time cannot take them back. When a ceiling binds
>   the answer is a layer — arriving as its own kind, never as
>   a wider dialect of the channel it feeds — argued under the
>   interface-change rule and chosen then, never pre-committed.
>   Computation lives outside all three, in the caller's own
>   language. A ceiling governs what a channel may *say*, never
>   how widely an already-permitted form may be *used*. This is
>   what P4, P6, and P7 require of the authored inputs, held as
>   one standing rule. (Normative:
>   docs/spec/blueprint-model.md "Format stability",
>   docs/spec/script-spec.md "How the vocabulary grows";
>   D12, D18, D26.)
