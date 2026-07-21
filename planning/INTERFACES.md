<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Interfaces to the world

> **Status:** reliquary's guiding principles, and the governing
> document. It names the world-facing interfaces, the primary use
> cases they serve — the numbered list itself lives in
> [planning/USE-CASES.md](USE-CASES.md) — and the rule every
> interface-changing decision must follow. Settled design decisions
> live in [planning/ROADMAP.md](ROADMAP.md) and the user-facing contracts in
> `planning/`; this document says where every other interface decision
> must be weighed. When these documents and planning/ROADMAP.md disagree,
> the guiding principles and use cases govern: the roadmap is
> realigned to them, never the other way around.

reliquary meets the world through its primary interfaces:

1. **The CLI** — the `rlq` / `reliquary` command.
2. **The embedding API** — native language bindings (Python is
   the first).
3. **The scripting language** — `.rlqs` scripts.
4. **The machine blueprint** — the authored machine-definition
   document.
5. **The media definition** — the authored media-acquisition
   document.

They are deliberately not independent designs. The CLI and
the API are two presentations of one semantic surface: every
command maps one-to-one onto a public API call with the same
semantics, and nothing is CLI-only (planning/ROADMAP.md, "The CLI").
Keeping the two in sync is extraordinarily important — a change
to the surface lands on both in the same change, never deferred —
and this parity is a required invariant (AGENTS.md). The
scripting language sits above both — invoked through either — and
is deliberately non-computational, so that anything computational
belongs to the API (language goal G2). The two document formats
are authored directly in an editor and consumed through every
other surface: the CLI and API resolve and materialize
blueprints, and scripts reference — and may embed — media
definitions. A capability that appears
on one surface appears on the others wherever it is meaningful;
where it does not, the omission is a named decision, not drift.

## The primary interfaces

### The CLI

`rlq` (and its alias `reliquary`) is the human operator's surface:
explicit `--blueprint` / `--machine` selection, the two-layer
lifecycle vocabulary, `script`, media, and property commands. It is
a thin veneer over the embedding API — it may resolve selectors and
print ids, but it owns no semantics of its own. It is also the
universal automation path: any language that wants reliquary
automation but has no native API binding automates via the CLI, so
the CLI serves programs as well as people — and, like the API, it
must never make working from a common language difficult: a
program in any language must be able to invoke it, observe it,
and parse what it prints cleanly. Settled decisions:
planning/ROADMAP.md "The CLI"; working notes: [planning/design/cli-design.md](design/cli-design.md).

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
is the wrong shape, whatever its elegance in Python. reliquary attaches
no meaning to guest output; interpretation belongs to the caller.
In-repo consumers (the media layer, the script runtime) must drive
the same public interfaces available to external callers. Contract
for the Python binding: [AGENTS.md](../AGENTS.md) "The runner
surface".

### The scripting language

`.rlqs` scripts are the authored automation surface: declarative
about resources, imperative about guest interaction, statically
inspectable before the machine starts, and governed by numbered
language goals (G1–G7; planning/ROADMAP.md, "Primary language goals").
Source of truth:
[planning/design/script-spec-design.md](design/script-spec-design.md), with
[script-examples/](../script-examples/) as reference material.

### The machine blueprint

A blueprint is a reusable, user-owned JSON description of a kind
of machine: authored directly in an editor, seeded out of the
codex, or synthesized from a native VM by `import` —
the durable artifact from which machines are materialized, and
the home of the parameter seams its author designs in for
customization (U5). Specification:
[planning/design/machine-blueprint-design.md](design/machine-blueprint-design.md) with its
[reference](design/machine-blueprint-reference-design.md) and
[cookbook](design/machine-blueprint-cookbook-design.md).

### The media definition

A media definition names installation media and pins it: where a
payload may be acquired, and the hashes that verify the exact
build the scripts target. Hash-pinned definitions are what let a
repository refer precisely to media it cannot distribute (U4).
Specification: [planning/design/media-spec-design.md](design/media-spec-design.md).

## Supporting world-facing contracts

The primary interfaces do not exhaust what the world touches.
These contracts are world-facing too, and the vetting rule below
covers them equally:

- **The property registry** — a user-owned file authored directly
  in an editor, without passing through any primary interface:
  [planning/design/property-registry-design.md](design/property-registry-design.md).
- **The codex** — reliquary's built-in seed content and its
  index: seed-not-a-resolution-tier semantics, never-overwrite,
  delete-to-refresh, provenance, and the licensing rule
  for shipped media URLs:
  [planning/design/codex-design.md](design/codex-design.md).
- **Recorded outputs** — run records under a machine's `runs/`
  directory: transcripts (with the secret-redaction contract),
  screenshots, and collected outputs. The world reads these;
  their shape and retention are a contract: append-only, never
  rewritten, never implicitly pruned — a record lives until its
  machine is destroyed or the user explicitly deletes it. A
  record is evidence, not reconstructible; durability beyond the
  machine is the consumer's claim — the record directory is
  self-contained, and copying it out is the sanctioned way to
  keep one ([planning/design/script-spec-design.md](design/script-spec-design.md)).
- **The home layout** — where users place payload files, find
  caches, and locate everything above:
  [planning/design/instance-model-design.md](design/instance-model-design.md).

## Primary use cases

The numbered primary use cases — the decision surface every
interface decision is weighed against — live in
[planning/USE-CASES.md](USE-CASES.md), together with the cross-cutting
principles that run through them: the ephemeral-machine
principle, the control-plane arc, and the artifact-residency
split. They are numbered so a decision, review, or spec section
can cite the use case it serves — and so a proposed change can
be rejected by naming the use case it costs.

## The interface-change rule

The use-case list ([planning/USE-CASES.md](USE-CASES.md)) is where
interface changes are argued. A change
to an interfacing aspect of reliquary is significant precisely
when approving it requires the primary use cases to be adjusted;
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
- **Adds a new use.** The change serves a use reliquary does not
  yet name. More work — the new use case must be drafted,
  numbered, and weighed for coherence with the existing list and
  the ephemeral-machine principle — but, being additive, still an
  easy decision.
- **Misaligned with the primary use cases.** The hard case, and
  the one that must be argued very vigorously: approving such a
  change in good faith would require reliquary's primary use
  cases to change, so the use-case amendment — not the feature —
  is what gets argued. The workflow is strict: make the argument;
  if the argument wins, amend the use cases in planning/USE-CASES.md; only
  then does work start. A misaligned change that can propose no amendment
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
3. **Record it.** Use-case amendments land in
   [planning/USE-CASES.md](USE-CASES.md); settled decisions go to their
   planning/ROADMAP.md sections; user-facing contracts to their `planning/`
   design specs; examples stay synchronized.

## Specification homes

| Interface | Specification |
|---|---|
| CLI | planning/ROADMAP.md "The CLI"; working notes in [planning/design/cli-design.md](design/cli-design.md) |
| Embedding API | [AGENTS.md](../AGENTS.md) "The runner surface" (the Python binding's contract) |
| Scripting language | [planning/design/script-spec-design.md](design/script-spec-design.md) |
| Blueprints | [planning/design/machine-blueprint-design.md](design/machine-blueprint-design.md) with its [reference](design/machine-blueprint-reference-design.md) and [cookbook](design/machine-blueprint-cookbook-design.md) |
| Media definitions | [planning/design/media-spec-design.md](design/media-spec-design.md) |
| Property registry | [planning/design/property-registry-design.md](design/property-registry-design.md) |
| The codex | [planning/design/codex-design.md](design/codex-design.md) |
| Home / machines | [planning/design/instance-model-design.md](design/instance-model-design.md) |
| Run records | transcript contract in [planning/design/script-spec-design.md](design/script-spec-design.md) |
