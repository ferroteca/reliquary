<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Pledged features

Large capability that is **pledged but not yet built**, each
carrying the work breakdown that delivers it. A feature arrives here
by being moved out of
[proposed/FEATURES.md](../proposed/FEATURES.md) — the move is the
pledge and the commit is its record ([README.md](../README.md))
— and leaves by being delivered, or by being **withdrawn** back to
that file when the pledge turns out to be one nobody meant (D44;
first used by D61).

Pledged is not scheduled: the numbered milestone arc ended with
milestone 9, so nothing below is queued or dated. The work items are
tasks like any other and answer to the same rules as
[TASKS.md](../TASKS.md); they sit with their feature rather than in
that queue because they are meaningless apart from it.

Each feature carries an **F-number** and must fit in **one sprint**
(D42; the rules are in [README.md](../README.md)). A feature too
large is cut on pledge, the split retiring the parent's number
for a fresh one per piece.

**F-numbers are issued against the sequence ledger**
([SEQUENCES.md](../SEQUENCES.md); owner, 2026-07-31): take the
next mark there and advance it in the same edit, by whichever
door the entry arrives — drafted in
[proposed/FEATURES.md](../proposed/FEATURES.md), or cut straight
to this file on pledge.

## F37 — The prose-parser migration

> Delivers the remaining half of the **P24 amendment**
> ([ARCHITECTURE.md](ARCHITECTURE.md), beside this file): the
> bright line — no test parses the structure of a normative
> prose document. The audit obligations that inherit the deleted
> checks stand in [RECURRING.md](../RECURRING.md). Cut from F35
> at pledge, the split retiring F35's number (D42).

Each check migrates under the amendment's no-second-registers
rule — the corpus or a shipped schema where the machine artifact
is or becomes the norm for what it captures, deletion with the
norm's audit obligation inheriting the check otherwise.

Work items:

1. `test_script_spec_conformance.py` — whole module;
   script-spec.md's V-rules already carry per-rule corpus
   fixtures, the natural machine home for rule coverage.
2. `test_api_spec_conformance.py` — the api.md table-row reads,
   superseded by [F38](#f38--the-command-manifest)'s conformance
   test (`tests/test_command_manifest.py`, landed); the
   twin-parity half (`cli._COMMANDS` against `__all__`) goes
   with them, the manifest asserting
   both directions of P6 where it asserted one.
3. `test_cli.py` `ClaimedCommandTests` — the docs/spec command
   sweep, superseded by [F38](#f38--the-command-manifest)'s
   conformance test (`tests/test_command_manifest.py`,
   landed); the rest of the module stays.
4. `test_script_corpus.py` — the script-spec.md prefix-list
   read.
5. `test_conformance_corpus.py` — the instance-model.md
   phase-sentence read; the phase enum's machine home is
   `machine-state.schema.json` already.
6. `test_facts.py` — the script-properties.md catalog read.
7. `test_assets.py` — the asset-resolution.md extension-registry
   read.
8. `test_document.py` — the media-spec.md materialize-table
   read.
9. `test_library.py` — the codex.md inventory read.

Landing the last item, the register standing, is delivering the
amendment: that change amends root P24's text and deletes the
pledged entry with it — D34's automatic move, named here so the
piece that lands last knows it closes the arc.

## F38 — The command manifest

> Demanded by **P6** (one semantic surface — every command its
> API twin, nothing CLI-only, no capability unreachable from the
> CLI) and by the **P24 amendment**'s migration rule
> ([ARCHITECTURE.md](ARCHITECTURE.md), beside this file): the
> inventory's normative home moves into a machine artifact only
> where that artifact *is* the norm for what it captures. Two of
> [F37](#f37--the-prose-parser-migration)'s dispositions point
> here. No use case asks for it.

**One authored file is the normative inventory of the command
surfaces.** Each capability is declared exactly once, and both
faces — the dash-separated CLI word, the underscored twin —
derive from the one name, so a twin mismatch is not a violation
to catch but a state the artifact cannot express. The suite
consumes it every commit; the prose specs stop enumerating and
defer to it for *what exists*, keeping what prose is for — the
behavior, the semantics, the rules.

**Readability is a requirement, not a preference** (owner,
2026-08-01). This file is what a reviewer actually reads when a
surface change is proposed: the diff of the manifest *is* the
inventory change, argued line by line. The requirement binds the
authoring — comments carrying the grouping and the reasons where
a reviewer meets them, entries grouped by class, one line per
capability so one new capability is one new line in a diff — and
it is the criterion that settled the format (owner, 2026-08-01):
**TOML**. The flattest rendering of exactly this shape, comments
native, and stdlib `tomllib` reads it — so P21 never engages,
and a stdlib that can only *read* it is the right affordance for
a norm nothing should machine-write. JSONC — one authored syntax
across the project — was the close second; a bespoke line format
was refused under P21, a parser nobody else maintains with no
editor support.

The artifact is authored and shipped —
`src/reliquary/schemas/command-manifest.toml` — and is its own
best example: grouped by class, commented where the reviewer
reads, one line per capability. The conformance test holding
the code to it is `tests/test_command_manifest.py`.

**What the suite asserts**, all of it machine against machine:
every declared capability ships both faces; every registered
command is declared; every public name is declared or
classified; nothing declared is absent. Both directions of P6
become enforced for the first time — the reverse direction is
the gap in-force P24 has carried by name since D49, because
"no capability unreachable from the CLI" was a judgment per
name with no roster to check against. This file is that
roster: the judgment still happens once, in a governed edit,
and the artifact records the verdict where a test can hold it.

**Two ceilings, stated here so they bind the work.** Depth:
names only — no flag or parameter encoding; each layer below
names must arrive with a bug it would have caught. Breadth: the
command surfaces only — the blueprint has its schema, the
script language its corpus, and each surface gets the machine
artifact that fits its shape, never one format stretched over
all of them.

Work items:

1. **The prose deferral** — cli.md and api.md stop enumerating
   the inventory and cite the manifest; a norm edit, landing
   under the surface-change rule with this feature.
2. **The audits narrowed** — R1 and R2
   ([RECURRING.md](../RECURRING.md)) shed their inventory half;
   their Check lines are edited to the judgment half in the
   same change.
