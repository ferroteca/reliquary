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
   superseded by the manifest conformance test
   (`tests/test_command_manifest.py`; F38, delivered); the
   twin-parity half (`cli._COMMANDS` against `__all__`) goes
   with them, the manifest asserting
   both directions of P6 where it asserted one.
3. `test_cli.py` `ClaimedCommandTests` — the docs/spec command
   sweep, superseded by the manifest conformance test
   (`tests/test_command_manifest.py`; F38, delivered); the
   rest of the module stays.
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
