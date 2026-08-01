<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Proposed architecture

> **Status:** the staging ground for changes to the architecture —
> new principles, model changes, retirements — argued here before
> anything is pledged. **Nothing here is pledged, and nothing is worked
> from here.** The lifecycle mirrors the use-case one
> ([proposed/USE-CASES.md](USE-CASES.md)) and runs across three
> locations: drafted here, then **pledged** — moved to
> [pledged/ARCHITECTURE.md](../pledged/ARCHITECTURE.md), the move
> itself the record — then in force, moved again into root
> [ARCHITECTURE.md](../../ARCHITECTURE.md), which sits at the
> repository root because it describes current reality: the shipped
> system's model, and only the principles the project honors
> today.
>
> All three share one global P-namespace; numbers are permanent
> and never reused, and no placeholder is left behind by either
> move. A principle in force is clarified, retired, or superseded —
> never changed in nature — while a proposed one may still be
> reshaped freely here (its number stays; work already scheduled
> against it is re-checked in the same edit). The second move is
> **automatic** (D34), and its trigger is delivery rather than
> pledge — for a principle, *honored as a rule* with every known
> residue filed as a defect in the same change (D48), never the
> full-delivery bar a use case answers to. A dead proposal is recorded in
> [DECISIONS.md](../DECISIONS.md) and triggers the same
> planning-doc sweep, its P-number the search key.

## P24 — Every application surface is tested against its specification (amendment)

> **Amends in-force P24**
> ([ARCHITECTURE.md](../../ARCHITECTURE.md)), which binds
> unchanged until this is pledged and delivered. The claim is
> untouched — every surface tested against the norm that defines
> it, the suite green on every commit to `main`, an untestable
> surface naming its gap — and so is D49's arming. What changes
> is the second clause's *instrument*: which checks may live in
> the every-commit suite, and where enforcement of the rest
> moves. Demanded by P24's own collision with the norms it
> enforces; no use case asks for it.
> [F35](FEATURES.md#f35--the-recurring-register-and-the-prose-parser-migration)
> carries the work.

**The enforcement instrument follows the artifact kind.** A norm
is enforced by the every-commit suite where it is
machine-readable — a shipped schema, the conformance corpus, the
code's own enumerations, a fenced example block — and by a
standing obligation in the recurring register
(`planning/RECURRING.md`, below) where it is prose. The prose
norm loses nothing: it is still the authority the implementation
answers to, a divergence is still a bug
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

**The register**, described here so the delivering feature
builds what was argued. One planning-root machinery file,
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
