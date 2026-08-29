<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Recurring obligations

This is the list of recurring obligations: checks the project owes
on a repeating schedule instead of just once, each one recording
when it was last checked. This isn't a queue — an obligation is
never marked done, crossed off, or promoted to something else. It
stays on this list until it's retired by deleting its entry, and
the commit that deletes it is the record ([README.md](README.md)).

**Why this list exists**: the test suite that runs on every commit
can only enforce things that are machine-readable — a shipped
schema, a conformance corpus, the command manifest, an enumeration
in the code, a fenced example block (**P24**, root
[ARCHITECTURE.md](../ARCHITECTURE.md)). The rules written in prose
bind just as strongly, but the suite can't check them
automatically. This list is how they get checked instead: on a
stated schedule rather than on every commit.

**How this list works**, stated once here so no entry below has to
repeat it:

- **"Stale after" is a deadline, not a scheduled appointment.** It
  says when the evidence from the last check expires. Nothing here
  is actually scheduled and nothing is promised in advance; running
  a check early is always fine, and so is running every overdue
  check in one batch.
- **Being overdue is just a signal, not a defect by itself.** An
  entry past its deadline is a visible fact that a check is due;
  nothing escalates automatically, and being late doesn't file a
  bug on its own.
- **"Last performed" is current state, not a log.** It's one line,
  overwritten in place each time the check runs; earlier runs are
  still visible in git history, and no entry writes out its own
  history or keeps any date beyond that one line.
- **Whatever a check finds gets filed where findings belong** — the
  issue tracker, [TASKS.md](TASKS.md), or a defect against the norm
  it checked — following [design/audits.md](design/audits.md)'s
  caution that a finding isn't established fact until it's
  re-tested. This list holds only the obligations, never the
  results of running them.
- **The commit is what records a check having run.** Running a
  check only changes its "last performed" line here — nothing
  else — and the commit that updates that line is where the record
  of what the run found belongs.

**How entries are numbered and approved.** Each entry gets an
**R-number**, issued from [SEQUENCES.md](SEQUENCES.md); like a
task's number, an R-number is retired for good once the entry is
removed, never reused (D42's classification: an obligation is
standing work, not a vision statement). Adding an obligation here
is a governed change like any other writing under `planning/`, but
once it's added, the entry itself is the standing approval —
actually running the check needs no further sign-off.
[design/audits.md](design/audits.md) is where an idea for a check
waits until it's accepted; it becomes a real obligation by being
added here.

**What a spec audit actually checks.** A spec is the authority, so
if the code and the spec disagree, that's a bug in the code, not
the spec ([docs/spec/README.md](../docs/spec/README.md)). Running
an audit means reading the spec's prose against what actually
ships, and checking both directions: does the code do everything
the spec says it should (the V13 class of gap — specified, but not
enforced anywhere), and does the spec mention everything the code
actually does (the `fetch_media` class of gap — shipped, but not
documented anywhere)? Comparing the two inventories is the easy
half, and it's already handled by the test suite's own prose
parsers. Judging whether each individual rule actually holds is the
half no automated inventory can reach — which is why running one of
these audits takes a person's judgment, not just a script's
verdict.

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
  actual declared surface. The spec itself says it describes the
  end-goal design, not just what's built today. Two parts of it are
  already checked every commit by the command manifest — which API
  calls exist, and that each one has its matching CLI twin — so
  this audit covers what's left: statements written as present-tense
  behavior, and any of the design's claims about what's true right
  now.
- **Stale after**: one month.
- **Last performed**: never.

### R3 — Audit docs/spec/script-spec.md

- **Check**: [script-spec.md](../docs/spec/script-spec.md)
  against the parser, validators and runner — keywords,
  signatures, error classes, and the content of every V-rule:
  that each is enforced, and enforced as stated.
- **Stale after**: one month.
- **Last performed**: 2026-08-01.

### R4 — Audit docs/spec/blueprint-model.md

- **Check**: [blueprint-model.md](../docs/spec/blueprint-model.md)
  against the parser, for the meaning that goes beyond the schema's
  structure — the schema itself is checked every commit, through
  the conformance corpus.
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
  against how machine state is actually handled, for the meaning
  that goes beyond `machine-state.schema.json` — ownership,
  locking, recovery. The phase vocabulary's structure is already
  covered by the schema.
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
- **Last performed**: 2026-08-01.

### R12 — Watch DOSBox-X's control channel for a path to adoption

- **Check**: originally, whether DOSBox-X had grown a host-side
  control channel meeting the four capabilities in
  [design/dosbox-x.md](design/dosbox-x.md) — met 2026-08-24,
  independently verified against `pgalbraith/dosbox-x`'s
  `control-channel` branch ("The bar was met, on a personal fork").
  **Retargeted to what that resolved into**: whether the channel (or
  an equivalent) has reached somewhere Reliquary could depend on
  without maintaining a fork itself — merged upstream, or released
  in an official build. A fork staying a fork, however capable,
  doesn't satisfy this check.
- **Stale after**: six months — an upstream merge is an
  infrequent event, not a point release.
- **Last performed**: 2026-08-24.
