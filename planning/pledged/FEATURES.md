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

**F32–F34 are one cut** from **P26** — the session layer is the
only door ([pledged/ARCHITECTURE.md](ARCHITECTURE.md)) — whose
respell is too large for D42's bound, each piece landing
coherently on its own: the session built (F32), the CLI on it
(F33), the door closed and the principle armed (F34). The cut is
staged so the public surface moves **once**: F32 and F33 are
internal work a consumer never sees, and F34 is the one landing
that changes the surface, which is where P9's
coherent-and-complete rule bites — no interval in which two public
doors stand open.

## F32 — The `Session` object

> Pledged 2026-07-31 (owner), cut from **P26**
> ([pledged/ARCHITECTURE.md](ARCHITECTURE.md)), which demands it.
> First of the three: after it the session exists, is complete,
> and is exercised by the suite — and nothing public has moved.
> `Session` stays **unexported** until F34 closes the door, so
> this feature changes no application surface and touches no
> spec.

1. `session.py`: **`Session`**, opened on what `context=` accepts
   today — a bare home string or a `Context` — and refusing
   construction without a home, fail-closed naming what is
   missing: the construction-time refusal that retires first-use
   `dir.unassigned` when F34 lands. Two sessions in one process
   must be unremarkable — construction reads and writes no
   module-global state.
2. `Context` grows **`properties_file`** (P26's cargo ruling),
   and the session hands it to the properties, credentials, and
   binding veneers the way it hands the directories to
   everything else.
3. **The veneer**: one thin session method per ambient-state
   verb — the machines lifecycle with its exec, file, and
   variable families, the media family, blueprint authoring,
   namespace resolution, properties/credentials/binding, and
   `run_script` — each forwarding to the engine with the stored
   record and carrying no logic of its own. Pure parse/validate
   stays free per P26's named boundary; the codex verbs stay
   CLI-only (P6's named exception, D87) and take no veneer.
4. Suite coverage driving the session directly, including the
   two-sessions-two-homes case the globals could never state.

## F33 — The CLI opens a session

> Pledged 2026-07-31 (owner), cut from **P26**; depends on
> **F32**. The CLI becomes the session layer's first consumer
> with **no observable change**: same flags, same environment
> honoring, same default home, same exit codes — which is what
> makes it its own sprint, verifiable by the existing CLI suite
> alone. No application surface moves and no spec is touched.

1. `cli.py` builds the `Context` from its flags, the environment
   (`adopt_environment` becoming the CLI's private construction
   step), and the default home whenever neither named one —
   D59's defaulting rule relocated intact — then opens **one
   `Session` per invocation** and drives only session methods.
2. The module-level directory globals lose their last in-tree
   driver; they stay present and public until F34 deletes them,
   because deleting them is a surface change and this feature
   makes none.

## F34 — The door closes

> Pledged 2026-07-31 (owner), cut from **P26**; depends on
> **F33**. The one landing that changes what a consumer sees,
> and the whole surface change lands in it coherently and
> completely (P9, P8 triage: S2 respelled, S1 unchanged in
> behavior, both named). **Delivery arms P26** — the same change
> promotes it to root [ARCHITECTURE.md](../../ARCHITECTURE.md)
> (D34), with any known residue filed as a defect in the same
> commit (D48).

1. The public surface narrows to the session and the vocabulary:
   `Session` exported; the module verbs go internal; the
   directory globals, `set_*_dir()`, and `adopt_environment()`
   are deleted from the public surface; per-call `context=` and
   `properties_file=` leave every public signature. The types,
   errors, `Context`, `default_home_dir()`, and the free parsers
   remain importable, per P26's survivor ruling.
2. First-use `dir.unassigned` retires for the construction-time
   refusal; `test_old_surface_purge.py` grows every retired
   spelling, and the parity test respells its mapping — every
   CLI command onto its session-method twin.
3. The norms move with the surface, in the same change:
   [docs/spec/api.md](../../docs/spec/api.md) (the session
   convention and the twin table),
   [docs/spec/asset-resolution.md](../../docs/spec/asset-resolution.md)
   (the working directories and the resolution rule),
   [docs/spec/cli.md](../../docs/spec/cli.md) where it names
   twins, the API reference and README examples, and AGENTS.md —
   including the in-repo-consumer doctrine, restated as driving
   the same engine seam the session's veneer drives, nothing
   deeper.
4. The record's discipline: D59's carrier-mechanism clauses take
   their bracketed annotation naming P26; the CHANGELOG's
   unreleased section carries the break.
