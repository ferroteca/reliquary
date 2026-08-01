<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# The recurring register

The standing obligations: checks the project owes on a rhythm
rather than once, each carrying the mark of its last discharge.
Nothing here is a queue — an obligation is never done, struck or
promoted; it stands until it is retired by deletion, and the
commit is the record ([README.md](README.md)).

**Why**: the every-commit suite enforces only what is
machine-readable — a shipped schema, the conformance corpus, the
code's own enumerations, a fenced example block (**P24** as
amended; [pledged/ARCHITECTURE.md](pledged/ARCHITECTURE.md)
until the migration delivers). The prose norms bind just as
hard, and this register is their enforcement instrument: what
the suite cannot check on every commit is checked here on a
stated rhythm instead.

**The semantics**, stated once so no entry restates them:

- **A staleness bound is a ceiling, never an appointment.** It
  states when the last run's evidence expires. Nothing is
  scheduled and nothing is promised; running early is always
  allowed, and so is running everything due in one batch.
- **Overdue is a signal, never a defect.** An entry past its
  bound is a visible fact asking to be discharged; nothing
  escalates on its own, and lateness files nothing.
- **The mark is state, never diary.** One line, overwritten in
  place by each discharge; past runs live in git history, and no
  entry narrates its history or keeps dates beyond the mark.
- **Findings are filed where findings go** — the issue tracker,
  [TASKS.md](TASKS.md), or a defect against the norm — under
  [design/audits.md](design/audits.md)'s caution that a finding
  is not a fact until re-tested. The register holds obligations,
  never results.
- **The discharge is recorded by its commit.** A run edits the
  mark and nothing else here, and the commit that advances it is
  where the run's account belongs.

**The mechanics.** Entries carry **R-numbers** issued against
[SEQUENCES.md](SEQUENCES.md), evaporating on retirement the way
a task's number does (D42's work class — an obligation is
standing work, not vision). Entering an obligation is a governed
act like all writing under `planning/`, and the entry is the
standing approval: performing a run needs no further permission.
[design/audits.md](design/audits.md) stays the un-committed idea
pen; an idea graduates by being entered here.

**What a spec audit is.** The norm is the authority and a
divergence is a bug in the code
([docs/spec/README.md](../docs/spec/README.md)), so the audit
reads the prose against what ships and asks both directions:
does the code do everything the norm states (the V13 class —
specified, enforced nowhere), and does the norm state everything
the code does (the `fetch_media` class — shipped, declared
nowhere)? The inventory comparison is the cheap half, inherited
from the suite's prose parsers; judging the *content* of each
rule is the half no inventory could reach, and it is why a
discharge is judgment work, never a script's verdict alone.

## The obligations

### R1 — Audit docs/spec/cli.md

- **Check**: [cli.md](../docs/spec/cli.md) against the `rlq`
  command the package ships — behavior only: flag semantics,
  output and exit-code claims, per-command rules. The command
  inventory is the manifest's, checked every commit
  (`tests/test_command_manifest.py`).
- **Stale after**: one month.
- **Last performed**: never.

### R2 — Audit docs/spec/api.md

- **Check**: [api.md](../docs/spec/api.md) against the package's
  declared surface. The spec declares itself end-goal design, and
  the inventory and twin-identity halves are the manifest's,
  checked every commit — the audit reads what remains: behavior
  asserted in present tense, and the design's claims about
  today.
- **Stale after**: one month.
- **Last performed**: never.

### R3 — Audit docs/spec/script-spec.md

- **Check**: [script-spec.md](../docs/spec/script-spec.md)
  against the parser, validators and runner — keywords,
  signatures, error classes, and the content of every V-rule:
  that each is enforced, and enforced as stated.
- **Stale after**: one month.
- **Last performed**: never.

### R4 — Audit docs/spec/blueprint-model.md

- **Check**: [blueprint-model.md](../docs/spec/blueprint-model.md)
  against the parser, for the semantics beyond the schema —
  structure is the shipped schema's half of the norm, checked
  every commit through the corpus.
- **Stale after**: one month.
- **Last performed**: never.

### R5 — Audit docs/spec/media-spec.md

- **Check**: [media-spec.md](../docs/spec/media-spec.md) against
  acquisition, verification and the cache — the materialize
  modes included.
- **Stale after**: one month.
- **Last performed**: never.

### R6 — Audit docs/spec/script-properties.md

- **Check**:
  [script-properties.md](../docs/spec/script-properties.md)
  against the binding pipeline, the fact catalog, and secret
  storage.
- **Stale after**: one month.
- **Last performed**: never.

### R7 — Audit docs/spec/asset-resolution.md

- **Check**:
  [asset-resolution.md](../docs/spec/asset-resolution.md)
  against resolution behavior — the six placeable directories,
  the resolution order, the extension registry.
- **Stale after**: one month.
- **Last performed**: never.

### R8 — Audit docs/spec/instance-model.md

- **Check**: [instance-model.md](../docs/spec/instance-model.md)
  against machine state handling, for the semantics beyond
  `machine-state.schema.json` — ownership, locking, recovery;
  the phase vocabulary's structural half is the schema's.
- **Stale after**: one month.
- **Last performed**: never.

### R9 — Audit docs/spec/codex.md

- **Check**: [codex.md](../docs/spec/codex.md) against the
  shipped seed content and its index.
- **Stale after**: three months — seed content moves slowly.
- **Last performed**: never.

### R10 — Audit docs/spec/http-serve.md

- **Check**: [http-serve.md](../docs/spec/http-serve.md) against
  the local answer-file server.
- **Stale after**: three months — a small, stable surface.
- **Last performed**: never.

### R11 — Dependency freshness

- **Check**: the pins in `pyproject.toml` and `uv.lock` against
  upstream — stale versions, yanked releases, advisories — and
  **P21**'s standing question: does each dependency still pull
  its weight better than the stdlib?
- **Stale after**: one month.
- **Last performed**: never.
