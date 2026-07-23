<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Interfaces to the world

> **Status:** Reliquary's guiding principles, and the governing
> document. The itemized principles themselves are P-numbered
> in root [PRINCIPLES.md](../PRINCIPLES.md). It names the
> world-facing interfaces, the use cases
> they serve — the numbered list itself lives in
> [planning/USE-CASES.md](USE-CASES.md) — and the rule every
> interface-changing decision must follow. Settled design decisions
> live in [planning/ROADMAP.md](ROADMAP.md) and the user-facing contracts in
> `planning/`; this document says where every other interface decision
> must be weighed. When these documents and planning/ROADMAP.md disagree,
> the guiding principles and use cases govern: the roadmap is
> realigned to them, never the other way around.

Reliquary meets the world through its primary interfaces:

1. **The CLI** — the `rlq` / `reliquary` command.
2. **The embedding API** — native language bindings (Python is
   the first).
3. **The scripting language** — `.rlqs` scripts.
4. **The machine blueprint** — the authored `.rlqb` document: the
   machine and the `media`, `source`, and `archive` components it
   draws on.

They are deliberately not independent designs. The CLI and
the API are two presentations of one semantic surface: every
command maps one-to-one onto a public API call with the same
semantics, and nothing is CLI-only (planning/ROADMAP.md, "The CLI").
Keeping the two in sync is extraordinarily important — a change
to the surface lands on both in the same change, never deferred —
and this parity is a required invariant (AGENTS.md). The
scripting language sits above both — invoked through either — and
is deliberately non-computational, so that anything computational
belongs to the API (language goal G2). The authored blueprint
format is written directly in an editor and consumed through every
other surface: the CLI and API resolve and materialize blueprints
(their media, source, and archive components included), scripts
reference media by name, and landmark declarations are authored
files of their own — a script carries no JSON. A capability that
appears
on one surface appears on the others wherever it is meaningful;
where it does not, the omission is a named decision, not drift.

## The primary interfaces

### The CLI

`rlq` (and its alias `reliquary`) is the human operator's surface:
explicit `--blueprint` / `--machine` selection, the two-layer
lifecycle vocabulary, `run-script`, media, and property commands.
It is a thin veneer over the embedding API — it may resolve
selectors and print ids, but it owns no semantics of its own, and
under the twin-name identity rule a command *is* its API twin's
name, dash-separated (the guest-console family instead spells as
the script language's verbs, and the `run` family maps to the run
handle — planning/ROADMAP.md "The CLI"). It is also the
universal automation path: any language that wants Reliquary
automation but has no native API binding automates via the CLI, so
the CLI serves programs as well as people — and, like the API, it
must never make working from a common language difficult: a
program in any language must be able to invoke it, observe it,
and parse what it prints cleanly. Settled decisions:
planning/ROADMAP.md "The CLI"; working notes: [planning/design/cli.md](design/cli.md).

### The embedding API

The embedding API is the first-class surface for consuming
projects: test harnesses, CI drivers, and any orchestration that
needs decisions, expressions, or loops. It expects native bindings
in multiple languages: the public Python surface — `Runner` /
`MachineConfig` and the module-level functions — is the first
binding, not the definition of the surface. A language without a
native binding automates via the CLI instead. The API must never
make working in a common binding language (C, Java) difficult: a
semantic shape that cannot be expressed cleanly across bindings
is the wrong shape, whatever its elegance in Python. Reliquary attaches
no meaning to guest output; interpretation belongs to the caller.
In-repo consumers (the media layer, the script runtime) must drive
the same public interfaces available to external callers. Design:
[planning/design/api.md](design/api.md); the implemented Python
binding is documented in
[docs/api-reference.md](../docs/api-reference.md), with its
engineering contract in [AGENTS.md](../AGENTS.md) "The runner
surface".

### The scripting language

`.rlqs` scripts are the authored automation surface: declarative
about resources, imperative about guest interaction, statically
inspectable before the machine starts, and governed by numbered
language goals (G1–G7; planning/ROADMAP.md, "Primary language goals").
Source of truth:
[planning/design/script-spec.md](design/script-spec.md), with
[planning/design/script-examples/](design/script-examples/) as
reference material.

### The machine blueprint

A blueprint is a reusable, user-owned JSON description of a kind
of machine, composed of named `machine`, `media`, `source`, and
`archive` components: authored directly in an editor, seeded out of
the codex, or synthesized from a native VM by `import-vm` —
the durable artifact from which machines are materialized, and
the home of the parameter seams its author designs in for
customization (U5). Its `media` components name installation media
and pin it: where a payload may be acquired, and the hashes that
verify the exact build the scripts target — what lets a repository
refer precisely to media it cannot distribute (U4). Specification:
[planning/design/machine-blueprint.md](design/machine-blueprint.md) with its
[reference](design/machine-blueprint-reference.md),
[cookbook](design/machine-blueprint-cookbook.md), and the
[media spec](design/media-spec.md) for the media, source, and
archive components.

## Supporting world-facing contracts

The primary interfaces do not exhaust what the world touches.
These contracts are world-facing too, and the vetting rule below
covers them equally:

- **Script properties** — the mechanism through which scripts
  consume values. Its authored surfaces face the world without
  passing through any primary interface: the user-owned
  `user.properties` file, edited directly in an editor, and the
  `RELIQUARY_PROPERTY_*` environment spelling:
  [planning/design/script-properties.md](design/script-properties.md).
- **The codex** — Reliquary's built-in seed content and its
  index: seed-not-a-resolution-tier semantics, never-overwrite,
  delete-to-refresh, provenance, and the licensing rule
  for shipped media URLs:
  [planning/design/codex.md](design/codex.md).
- **Recorded outputs** — run records under a machine's `runs/`
  directory: the event stream, transcripts (with the
  secret-redaction contract), and screenshots. The world reads these;
  their shape and retention are a contract: append-only, never
  rewritten, never implicitly pruned — a record lives until its
  machine is destroyed or the user explicitly deletes it. A
  record is evidence, not reconstructible; durability beyond the
  machine is the consumer's claim — the record directory is
  self-contained, and copying it out is the sanctioned way to
  keep one ([planning/design/script-spec.md](design/script-spec.md)).
- **The home layout** — where users place payload files, find
  caches, and locate everything above:
  [planning/design/instance-model.md](design/instance-model.md).

## Use cases

The numbered use cases — the decision surface every
interface decision is weighed against — live in
[planning/USE-CASES.md](USE-CASES.md); the cross-cutting
principles that run through them — the ephemeral-machine
principle, the control-plane arc, the artifact-residency
split, the feedback split — are itemized with their normative
prose in root [PRINCIPLES.md](../PRINCIPLES.md). They are numbered so a decision, review, or spec section
can cite the use case it serves — and so a proposed change can
be rejected by naming the use case it costs. That list holds
only what is in force; proposed changes to it are tracked in
[planning/USE-CASE-PROPOSALS.md](USE-CASE-PROPOSALS.md),
numbering from the same global U-sequence and moving over when
adopted.

## The interface-change rule

The use-case list ([planning/USE-CASES.md](USE-CASES.md)) is where
interface changes are argued. A change
to an interfacing aspect of Reliquary is significant precisely
when approving it requires the use cases to be adjusted;
a significant change is not argued as a feature on its own merits
— the use-case amendment is the argument, and the interface
change follows from the amended list. A significant proposal that
cannot be phrased as "the use cases should say ..." is not ready
to decide.

Requests triage by their use-case impact:

- **No use-case impact, or strong alignment with the existing
  list.** The change leaves the use cases untouched — nothing
  any use case demands is altered — or serves them as written: a
  better spelling for an existing capability, a gap filled where
  one surface lags the others. An easy decision to approve; cite
  the use cases served, or state that none are disturbed.
- **Adds a new use.** The change serves a use Reliquary does not
  yet name. More work — the new use case must be drafted and
  numbered in
  [planning/USE-CASE-PROPOSALS.md](USE-CASE-PROPOSALS.md) and
  weighed for coherence with the existing list and
  the ephemeral-machine principle — but, being additive, still an
  easy decision.
- **Misaligned with the use cases.** The hard case, and
  the one that must be argued very vigorously: approving such a
  change in good faith would require Reliquary's use cases to
  change, so the use-case amendment — not the feature —
  is what gets argued. The workflow is strict: draft the
  amendment in planning/USE-CASE-PROPOSALS.md and make the
  argument; if the argument wins, the work is scheduled in the
  roadmap — scheduling is acceptance, the citing roadmap item
  its record; only then does work start. Accepted use
  cases move into planning/USE-CASES.md when their delivery
  lands, anything superseded retiring to a stub. A misaligned change that can propose no amendment
  has nothing to argue and is rejected, regardless of its
  elegance.

Every approved change then lands the same way:

1. **Name every surface it touches.** A change rarely touches one:
   the CLI and API move together under the one-to-one rule, the
   language grows only through its growth goals (G6, G7), and a
   document format changes with its spec. An intentionally
   single-surface change states why the others are unaffected.
2. **Land it coherently and completely.** Pre-beta there is no
   backward compatibility (AGENTS.md): the change updates every
   affected surface, document, example, and test to the new shape
   and deletes the old one. That freedom makes execution cheap; it
   does not make the decision cheap — nothing downstream cushions
   a wrong one.
3. **Record it.** Use-case amendments are drafted in
   [planning/USE-CASE-PROPOSALS.md](USE-CASE-PROPOSALS.md),
   accepted by roadmap scheduling, and move into
   [planning/USE-CASES.md](USE-CASES.md) when delivered,
   keeping their numbers; settled decisions go to their
   planning/ROADMAP.md sections; user-facing contracts to their `planning/`
   design specs; examples stay synchronized.

## Specification homes

| Interface | Specification |
|---|---|
| CLI | planning/ROADMAP.md "The CLI"; working notes in [planning/design/cli.md](design/cli.md) |
| Embedding API | [planning/design/api.md](design/api.md); the implemented binding in [docs/api-reference.md](../docs/api-reference.md) |
| Scripting language | [planning/design/script-spec.md](design/script-spec.md) |
| Blueprints | [planning/design/machine-blueprint.md](design/machine-blueprint.md) with its [reference](design/machine-blueprint-reference.md) and [cookbook](design/machine-blueprint-cookbook.md) |
| Media / source / archive components | [planning/design/media-spec.md](design/media-spec.md) |
| Script properties | [planning/design/script-properties.md](design/script-properties.md) |
| The codex | [planning/design/codex.md](design/codex.md) |
| Home / machines | [planning/design/instance-model.md](design/instance-model.md) |
| Run records | transcript contract in [planning/design/script-spec.md](design/script-spec.md) |
