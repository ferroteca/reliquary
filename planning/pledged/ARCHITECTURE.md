<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Pledged architecture — awaiting delivery

> **Status:** principles the project has **pledged** but does not
> yet honor. Nothing here is in force: a principle only binds once
> it reaches the standing list, and a shortfall against an entry
> below is unbuilt work rather than a bug.
>
> That distinction is the point of this file. **Promotion is what
> arms a principle**: before it, an entry is pledged vision; after
> it, root [ARCHITECTURE.md](../../ARCHITECTURE.md) asserts the thing is
> true of the code, so a divergence becomes a *defect* the
> gap-is-a-bug rule can act on — that rule being stated in the
> root document's own banner (D48).
>
> Three locations hold three states. A principle is drafted in
> [proposed/ARCHITECTURE.md](../proposed/ARCHITECTURE.md), moves here
> when it is pledged, and moves to the root list when the code
> actually honors it. All three share one global P-namespace;
> numbers are permanent, never reused, and no placeholder is left
> behind by either move.
>
> The second move is **automatic on full delivery** (D34): whoever
> lands the work that makes the code honor a principle promotes it
> in the same change — adds it to the standing list, deletes it
> here — rather than holding it for a separate sign-off; the moving
> commit is the record, and no [DECISIONS.md](../DECISIONS.md) entry
> marks a promotion (D63). **A principle's bar is
> *honored as a rule*, not full delivery** (D48): it cannot be
> exhaustively proven, and holding it here until it is perfect
> keeps every shortfall invisible, which is the worse outcome.
> The condition is that every known residue is filed as a defect
> in the same change — that conversion being the whole point of
> arming it. (Full delivery remains the bar for a *use case*,
> which is a discrete journey and can be tested end to end.)
>
> A principle in force is clarified, retired, or superseded — never
> changed in nature. One pledged here may still be reshaped, its
> number intact, with work already scheduled against it re-checked
> in the same edit. A dead proposal is recorded in
> [DECISIONS.md](../DECISIONS.md) and triggers the planning-doc sweep,
> its P-number the search key.

## P24 — Every application surface is tested against its specification (amendment)

> **Amends in-force P24**
> ([ARCHITECTURE.md](../../ARCHITECTURE.md)), which binds
> unchanged until this delivers. The claim is untouched — every
> surface tested against the norm that defines it, the suite
> green on every commit to `main`, an untestable surface naming
> its gap — and so is D49's arming. What changes is the second
> clause's *instrument*: which checks may live in the
> every-commit suite, and where enforcement of the rest moves.
> Demanded by P24's own collision with the norms it enforces; no
> use case asks for it. The register stands
> ([RECURRING.md](../RECURRING.md));
> [F37](FEATURES.md#f37--the-prose-parser-migration) carries the
> migration.

**The enforcement instrument follows the artifact kind.** A norm
is enforced by the every-commit suite where it is
machine-readable — a shipped schema, the conformance corpus, the
code's own enumerations, a fenced example block — and by a
standing obligation in the recurring register
(`planning/RECURRING.md`, described below) where it is prose.
The prose norm loses nothing: it is still the authority the
implementation answers to, a divergence is still a bug
([docs/spec/README.md](../../docs/spec/README.md)'s banner is
untouched), and the register entry is what exercises that claim
on a stated rhythm. The bright line for the suite: **no test
parses the structure of a normative prose document** — no regex
over its headings, bullets, tables, or backticked terms.

**What this repairs.** Nine modules today read the prose norms
structurally: `test_script_spec_conformance` (script-spec.md's
keyword, rule, signature and error inventories, anchored to
exact heading text), `test_api_spec_conformance` (api.md's
family table rows), `test_cli`'s ClaimedCommandTests (every
`rlq` word written in docs/spec), `test_script_corpus`
(script-spec.md's prefix list), `test_conformance_corpus` (the
phase-enumeration sentence in instance-model.md), `test_facts`
(script-properties.md's catalog bullets), `test_assets`
(asset-resolution.md's extension registry), `test_document`
(media-spec.md's materialize table), `test_library` (codex.md's
inventory). Each welds the prose's *form* to the suite: a
heading rename, a reshaped table, a section rewritten for its
reader breaks tests, so the documents whose entire job is to be
read by people are the ones that cannot be freely rewritten. P23
already gates a norm's *content* — every rule change is proposed
and vetted — and the regexes gate its *form*, which nothing
demands.

**What is not demoted** (owner, 2026-07-31). The doc-example
runner (`test_documented_examples`) stays every-commit: a fenced
code block is a machine-readable island inside a prose document,
the test consumes only the islands, and a rotting example is the
one drift class the project has been burned by twice — the prose
around the fences stays entirely free. The old-surface purge
sweep (`test_old_surface_purge`, with the retired-vocabulary
grep beside the example runner) stays for now: a vocabulary
denylist constrains no structure, and its value is highest while
the retirement rounds are recent; its demotion triggers are
named — allowlist growth, a false positive, or the retirements
ending. And the code-vs-code checks those modules also carry
(twin-name parity, exports absent, commands absent, fixture
parsing) were never in scope: they read no prose.

**The register**, described here so the delivering features
build what was argued. One planning-root machinery file,
`planning/RECURRING.md`, holding the standing obligations the
suite cannot: per-norm spec audits, dependency freshness, and
whatever else recurs. Each entry carries an **R-number** issued
against [SEQUENCES.md](../SEQUENCES.md) — the R-mark enters the
ledger when the register does — evaporating when the obligation
is retired; **what to check**; a **staleness bound**, time-based
or event-based, each entry's own (owner, 2026-07-31 — a uniform
cadence was declined: obligations decay at different rates, and
a bound is a ceiling rather than an appointment, so nothing
stops running everything due in one batch); and a
**last-performed mark** — date and performing commit,
overwritten in place. The mark is SEQUENCES.md's kind of line,
not a diary: one line of state the file exists to hold, past
runs living in git history. The preamble states the semantics:
overdue is a visible fact and a signal to run, never a defect;
a bound promises no delivery and schedules nothing — it states
when the last run's evidence expires. Findings from a run are
filed where findings go — the tracker, TASKS.md, a defect —
under [design/audits.md](../design/audits.md)'s caution that a
finding is not a fact until re-tested; the run's own record is
the commit that advances the mark. Entering an obligation is a
governed act like all writing under `planning/`; performing one
needs no further approval, the entry being the standing one.
`design/audits.md` stays the un-committed idea pen, and an idea
graduates by being entered.

**No second registers.** Each parsing check migrates one of two
ways: the inventory's *normative home* moves into a machine
artifact the suite consumes — only where that artifact is or
becomes the norm for what it captures, the blueprint schema's
pattern — or the check is deleted and the norm's audit
obligation inherits it. Never a machine inventory whose only
consumer is a test while the prose remains the normative
statement of the same list: that is two copies that drift,
which this machinery refuses everywhere else.

**What the audits inherit**, said honestly. The parsers caught
real divergences no behavior test could: V13 specified and
enforced nowhere, `import-vm` shipped as a registered
`NotImplementedError`, `fetch_media` missing from `__all__`
while its command shipped. That class of catch becomes the
register's job, and the obligation entries should say so.

**P22 is untouched.** The register is discipline made visible —
the posture P22 states, written from the other side — and
automating its staleness check is a knock on the door P22
already expects.

- **P27 — Remanence owns at-rest disk access.** Direct disk-image
  access belongs to Remanence, not to Reliquary. Reliquary consumes
  Remanence as the one deep module for opening raw and qcow2 drive
  images at rest, claiming the image and any backing chain,
  discovering complete partition and volume geometry, reading and
  changing files in FAT volumes, and committing or rolling back
  mutations. Reliquary keeps the policy Remanence cannot own: the
  DOS-only FAT12/FAT16/FAT16B recognition claim, guest-address
  mapping, rule ids, and translation into the recorded drive report.
  The dependency earns the whole layer or none of it: a hybrid that
  keeps Reliquary's NBD client, `qemu-nbd` lifecycle, qcow2 snapshot
  orchestration, staged raw access, MBR reader, or FAT reader/writer
  as a fallback is refused, because it leaves two authorities for
  the same disk facts (P21; D83). D73's refusal to write and
  maintain a qcow2 reader inside Reliquary is honored by making the
  format implementation a declared dependency (D82), and D77's
  guarantees remain binding: an image is opened where it lies, a
  backing relationship survives a write, work is proportional to
  touched data, contention fails by name, and an interrupted write
  is reconciled on the next access. This principle is pledged, not
  armed: the current `remanence==0.0.1a1` release is evidence for
  the direction but not a candidate, because it refuses qcow2
  backing files, treats a blank newly materialized disk as an
  unreadable filesystem, silently omits unreadable partitions from
  `geometry()`, lacks a stable volume identity shared by geometry
  and file operations, and does not yet establish D77's
  crash-recovery guarantee. Implementation waits for a later
  Remanence release that satisfies those acceptance conditions on
  the delivered Windows host (P11), and that exact release is
  pinned.
