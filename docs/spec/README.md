<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Specifications

**These documents are normative.** They define Reliquary's
interfaces, and they are the authority the implementation answers
to — not a description of it. Where a spec and the code disagree,
**the spec is right and the code has a bug**, unless the spec
itself is changed first through the interface-change rule
([planning/INTERFACES.md](../../planning/INTERFACES.md)).

These specs are one leg of the project's **vision** — with the use
cases ([USE-CASES.md](../../USE-CASES.md)) and the architectural
principles ([ARCHITECTURE.md](../../ARCHITECTURE.md)), the standing
statement of what Reliquary is and is for. They are also **part of
the architecture**, not documentation about it
(ARCHITECTURE.md "The interfaces" names them as the norms): an
edit that changes what a spec requires is an interface change,
proposed and gated before it lands (**P23**) — never
housekeeping, and a change arriving already made is rejected by
citing that principle. Only an edit that changes no rule is
documentation work.

That direction matters, and it is the reason these live here rather
than under `planning/`. Everything in `docs/` describes the live
situation. A spec is the exact statement of that situation: what an
interface *is*, in force today, citable in a bug report and binding
on the next change. Speculative work — what an interface might
become — is not here; it is argued in
[planning/proposed/](../../planning/proposed/) and, once accepted
but not yet built, in
[planning/accepted/](../../planning/accepted/).

## Spec, reference, guide

Three kinds of document describe the same interfaces, and they are
not interchangeable:

- **Specs** (this directory) — normative, maintainer-facing, and
  complete. They state every rule, including the ones no user needs
  to read, and they are what the parser, the validators and the
  test suite are checked against.
- **References** (`docs/*-reference.md`) — descriptive and
  user-facing. They document the implemented surface as a person
  consumes it. A reference that disagrees with a spec is the
  reference's bug.
- **Guides** (`docs/`) — task-shaped. They teach one job end to
  end and make no completeness claim at all.

**The banner is the marker; this directory is only shelving.**
Every specification declares its normative standing in its own
status banner, and every descriptive document names the norm it
defers to — so a document copied, excerpted, or moved still says
what it is. Reclassifying a document is an edit to that statement
first; relocating the file is tidiness, not the act.

## The interfaces

| Spec | Interface |
|---|---|
| [cli.md](cli.md) | The `rlq` / `reliquary` command |
| [api.md](api.md) | The embedding API — the semantic twin of the CLI |
| [script-spec.md](script-spec.md) | The `.rlqs` scripting language, and the G1–G7 language goals |
| [blueprint-model.md](blueprint-model.md) | The composed blueprint model — structure, identity, the location grammar, the reference closure |
| [media-spec.md](media-spec.md) | Media: acquisition, verification, and the cache |
| [script-properties.md](script-properties.md) | Properties, secret storage, and the binding pipeline |
| [asset-resolution.md](asset-resolution.md) | Where authored assets resolve from, and the home layout |
| [instance-model.md](instance-model.md) | Machines: the state document, ownership, locking, recovery |
| [codex.md](codex.md) | The shipped seed content and its index |
| [http-serve.md](http-serve.md) | The local answer-file server |

The authored `.rlqb` document's **norm is split**: the published
schema (`reliquary/schemas/blueprint-schema-v1.json`) is normative
for structure, and [blueprint-model.md](blueprint-model.md) for the
semantics a schema cannot express. The
[guide](../blueprint-guide.md),
[field reference](../blueprint-reference.md), and
[cookbook](../blueprint-cookbook.md) are **descriptive** —
a disagreement with the schema or the model is their bug. The
control-plane doctrine
([guest-communication.md](../../planning/design/guest-communication.md))
is internal engineering design, not a world-facing interface
contract, and lives under `planning/`.

## Machine-readable schemas

The schemas are **not** here. They ship inside the package, at
`reliquary/schemas/`, because they are consumed by code — the test
suite validates against them, and editors bind them by file
association:

- `reliquary/schemas/blueprint-schema-v1.json` — the composed
  blueprint, versioned so editors can bind it today.
- `reliquary/schemas/machine-state.schema.json` — the machine state
  document.

**For the blueprint, the schema is the structural norm** — and only
the structural one: a schema captures the part JSON Schema can
express, so schema validity never implies document validity, and
[blueprint-model.md](blueprint-model.md) is normative for the
semantics beyond it. Reliquary's own parser is the validator of
both halves. Prose and schema are kept honest by the shared
conformance corpus (`reliquary_tests/fixtures/conformance/`), which
runs every fixture against both, so neither can drift from the
other unnoticed.

Documents carry no `$schema` field before 1.0; see the open
questions in
[planning/DECISIONS.md](../../planning/DECISIONS.md).
