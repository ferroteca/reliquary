<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Specifications

**These documents are normative.** They define Reliquary's
application surfaces, and the implementation must match them —
they are not a description of the implementation. Where a spec and
the code disagree, **the spec is right and the code has a bug**,
unless the spec itself is changed first through the surface-change
rule ([planning/SURFACES.md](../../planning/SURFACES.md)).

These specs are one of three documents that together state what
Reliquary is and is for: the use cases
([USE-CASES.md](../../USE-CASES.md)), the architectural principles
([ARCHITECTURE.md](../../ARCHITECTURE.md)), and these specs.
ARCHITECTURE.md, in its section "The application surfaces", names
these specs as the rules the application surfaces must follow — so
they count as part of the architecture, not as documentation
written about it. Because of that status, any edit that changes
what a spec requires is a surface change: it must be proposed and
approved before it lands (**P23**), it is never treated as routine
maintenance, and a change that arrives already made is rejected by
pointing to that rule. Only an edit that leaves every rule unchanged
counts as ordinary documentation work.

That is why these files live here and not under `planning/`.
Everything under `docs/` describes how Reliquary works right now. A
spec states that exactly: what a surface *is*, in force today, a
fact you can cite in a bug report and one the next change must
respect. Work on what a surface might become someday does not
belong here — it is proposed in
[planning/proposed/](../../planning/proposed/), and once approved
but not yet built, it moves to
[planning/pledged/](../../planning/pledged/).

## Spec, reference, guide

Three kinds of document describe the same surfaces, and they are
not interchangeable:

- **Specs** (this directory) — normative, written for maintainers,
  and complete. They state every rule, including ones no user
  needs to read, and they are what the parser, the validators, and
  the test suite are checked against.
- **References** (`docs/*-reference.md`) — descriptive and written
  for users. They document the implemented surface the way a
  person encounters it. If a reference disagrees with a spec, the
  reference is wrong.
- **Guides** (`docs/`) — organized around one task at a time. Each
  teaches one job start to finish and does not try to cover
  everything.

**What marks a document's status is its banner, not which folder
it sits in.** Every spec states its normative standing in its own
status banner, and every descriptive document names the spec it
defers to. That way, a document still says what it is even if it
gets copied, excerpted, or moved elsewhere. To change what kind of
document something is, edit that banner statement first; moving
the file afterward is just tidying up — the move itself changes
nothing.

**A spec is written as a rule, not as a report on current
behavior.** It binds the implementation, so it states what must
hold — "a missing slot fails before anything is touched," never
"Reliquary currently fails when the slot is missing." If the code
does not yet obey a clause, file that as a bug. Do not soften the
spec's wording to match the code instead.

## The application surfaces

| Spec | Interface |
|---|---|
| [cli.md](cli.md) | The `rlq` / `reliquary` command |
| [api.md](api.md) | The embedding API — the semantic twin of the CLI |
| [script-spec.md](script-spec.md) | The `.rlqs` scripting language, and the G1–G7 language goals |
| [blueprint-model.md](blueprint-model.md) | The composed blueprint model — structure, identity, the location grammar, the reference closure |
| [media-spec.md](media-spec.md) | Media: acquisition, verification, and the cache |
| [landmarks.md](landmarks.md) | Landmarks: the `.rlql` image-match asset, the `@name` screen condition, and the cursor-parking contract `click` mechanizes |
| [script-properties.md](script-properties.md) | Properties, secret storage, and the binding pipeline |
| [asset-resolution.md](asset-resolution.md) | Where authored assets resolve from, and the six placeable working directories |
| [instance-model.md](instance-model.md) | Machines: the state document, ownership, locking, recovery |
| [codex.md](codex.md) | The shipped seed content and its index |
| [http-serve.md](http-serve.md) | The local answer-file server |

Two different documents are normative for the authored `.rlqb`
file, each for a different part of it: the published schema
(`src/reliquary/schemas/blueprint-schema-v1.json`) is normative for
its structure, and [blueprint-model.md](blueprint-model.md) is
normative for the meaning a schema cannot express. The
[guide](../blueprint-guide.md),
[field reference](../blueprint-reference.md), and
[cookbook](../blueprint-cookbook.md) are **descriptive** — if one
of them disagrees with the schema or the model, the guide,
reference, or cookbook is wrong. The control-plane doctrine
([guest-communication.md](../../planning/design/guest-communication.md))
is internal engineering design, not part of the application-surface
contract, and it lives under `planning/`.

## Machine-readable schemas

The schemas are **not** in this directory. They ship inside the
package, at `src/reliquary/schemas/`, because code consumes them
directly: the test suite validates documents against them, and
editors pick them up by file association:

- `src/reliquary/schemas/blueprint-schema-v1.json` — the composed
  blueprint, versioned so editors can bind it today.
- `src/reliquary/schemas/landmark-schema-v1.json` — the `.rlql`
  landmark declaration, on the same terms.
- `src/reliquary/schemas/machine-state.schema.json` — the machine state
  document.

**For both the blueprint and the landmark, the schema is normative
only for structure.** A JSON Schema can only express structural
rules, so a document that validates against the schema is not
necessarily a valid document — [blueprint-model.md](blueprint-model.md)
and [landmarks.md](landmarks.md) are normative for the rules a
schema cannot express. Reliquary's own parser checks both halves.
The shared conformance corpus (`tests/fixtures/conformance/`) runs
every fixture against both the prose rules and the schema, so if
one drifts from the other, a fixture catches it.

Documents carry no `$schema` field before 1.0; see the open
questions in
[planning/DECISIONS.md](../../planning/DECISIONS.md).
