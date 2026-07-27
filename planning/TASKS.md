<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# TASKS

The pledged work backlog. A **proposed** task lives in the issue
tracker — <https://github.com/ferroteca/reliquary/issues> — which is
the only queue a proposed task has (D43): the tracker is a task's
proposed state and this file is its pledged one. So nothing parks
here awaiting a verdict; arriving *is* the verdict.

**Everything in this file is pledged** — the one vocabulary
([README.md](README.md)) applying here exactly as in the
directories. An entry is in the *pledged* state, so entering it is
approving it: nothing waits on a verdict, nothing needs a citation
or a decision of its own, and there is nothing to promote. The
directory is not its home because `proposed/` and `pledged/` hold
*demand and capability*, argued at length, and a task is none of
those — free-standing work too small to be a feature and too small
to need the argument. That kind distinction is the distinguisher,
not size.

**This file is the third work input queue** (D43, widening D39's
two), and adding to it is governed by the gate covering all writing
under `planning/` — weighing most here, this being the one governed
act that grants approval with no argument behind it.

**A queue holds what waits.** Work that arrives already done never
appears here: there is nothing to schedule, only a decision to make,
and an entry filed and closed in one act is ceremony.

**There is no order here.** Nothing in this file is scheduled, and
nothing claims priority over anything else; whoever picks work up
picks whatever they like. The one ordering that does bind is a
feature's: **work that only makes sense as part of one pledged
feature lives with that feature**, in
[pledged/FEATURES.md](pledged/FEATURES.md), and has to be done to
complete it — F1's items are the standing example. A
task here that merely *relates* to a feature is still free to be
picked whenever.

Housekeeping (D38) is the same instinct one size smaller: work tiny
enough and obvious enough that it needs no entry here **at all**,
approved as a class in advance, with the commit as its record. This
file is where the pre-approved work that is still worth writing
down goes. The full intake machinery — the raw queues, the
housekeeping test, and how pledge is recorded — is in
[README.md](README.md).

The sections below:

- **[Pledged](#pledged)** — the queue proper. Grouped by kind,
  because the actor and the gate differ, but the grouping is not a
  running order.
- **[Completed](#completed)** — done. Kept until its record is
  folded where it belongs and pruned.
- **[Rejected](#rejected)** — refused, with the reason recorded in
  [DECISIONS.md](DECISIONS.md), which is already the guard
  against re-litigating. The section here is a thin index pointing
  at those entries, never a second record of the argument.

Standing questions to re-ask as the design hardens are not tasks
and live with the decision record, under
[DECISIONS.md](DECISIONS.md)'s open questions.

## Pledged

Grouped by kind, because the actor and the gate differ: an
adjudication is the owner's alone, an audit is mechanical, a defect
needs no pledge because the norm it violates already is one.
(A fourth group, the restructures, left for
[Completed](#completed) on 2026-07-27 — it had finished.)

### Governance — adjudications

Owner-only: each settles a question the record is waiting on.
None depends on the others.

- **Take or refuse U3's supersession.** D36 settled that U14
  supersedes U3 alone; U14 is now delivered and promoted (D37).
  Retiring U3 is the lifecycle's Retire clause — an owner
  adjudication, not a step of that delivery — so it waits, with a
  note saying so, in
  [pledged/USE-CASES.md](pledged/USE-CASES.md) (**pointer
  corrected 2026-07-27**: the entry said USE-CASE-PROPOSALS.md,
  which no longer exists). The move sharpened the question rather
  than settling it — U3 is *pledged*, so what waits is a use case
  the project still owes being superseded by one it has already
  delivered.

### Governance — audits

Unscheduled. Problems in the planning machinery
itself, found while landing milestone 9 and while asking where the
roadmap's bulk belongs (2026-07-24). (They once said they would
move to planning/BACKLOG.md "when that split lands"; it landed as
[proposed/FEATURES.md](proposed/FEATURES.md) instead, and these
stay here — they are work, not capability.)
The former "Planning docs" section is folded in here: its two
sweeps are the same class as everything else below (owner,
2026-07-24 — *something exists in the planning machinery without
the demand that justifies it*), and splitting the class across two
sections was itself part of the problem.

**The class, stated once.** The traceability rule says every
roadmap item, design document, and decision names the U-number (in
force or proposed) or P-number that demands it. A violation takes
one of three shapes, and each has its own remedy: work that cites
*no* demand (find it or delete the work); work that cites
*unpledged* demand as though it were pledged (pledge it, or
mark the citation conditional); and a design written for demand
that was never pledged at all (the D33 pattern — the design
outran its justification). The audits below are the standing way
to find them, not a one-off.


- **Sweep planning items for demand citations** (owner,
  2026-07-23; audited 2026-07-24; **rescoped 2026-07-27**). Every
  item names the U- or P-number that demands it.
  The 2026-07-24 audit result — **12 of 34 sections cite no U/P/G
  at all** — was measured against ROADMAP.md, which the
  restructure has since deleted, so the count no longer indexes
  anything readable. Re-run it over what replaced that file:
  `proposed/`, `pledged/`, and `design/`. The one finding that
  survived the move intact is the pillar it named — **"The GUI
  era", now [F5](proposed/FEATURES.md), still citing no demand
  whatsoever**, which is the D33 pattern in its purest form.
  What was lost with ROADMAP.md, and is the reason to run this
  before anything else prunes further: five completed milestones
  (1, 2, 3, 4, 6) went with their deliverable lists, so **what
  demanded them was never recorded**. It survives only in
  `git show 50b67b2:planning/ROADMAP.md`.

- **Retrofit supports onto DECISIONS.md entries** (owner,
  2026-07-23; audited 2026-07-24). Each names the use cases (U),
  principles (P), or goals (G) it supports; new entries carry
  supports from the start. Audit result: **22 entries lack one** —
  D1–D21 as the original task said, minus D22 (done, pulled
  forward by the milestone-7 governing-input audit), **plus D29**,
  which the original range missed. Correct the scope when picking
  it up.

*(The third audit — "Audit design documents against pledged
demand" — left here on 2026-07-27. It was in two lifecycle states
at once: pledged by sitting in this file, and proposed as
[F7](proposed/FEATURES.md), which D43 created from this file's
legacy Proposed section without removing the twin. The proposal
was kept and its findings folded into F7.)*

### Defects

A gap against a *standing* principle is a bug: the principle is
already its demand, so these need no pledge, only fixing. A gap
against a **shipped spec** is the same class and sits here too —
where `docs/spec/` and the code disagree the spec is right and the
code has the bug, so the norm is already the demand.

- **P24's tests check behavior, not specifications** (filed
  2026-07-27 by D49, the same hour P24 armed — D48's second bar).
  P24 claims every enumerated interface carries automated tests
  checking it **against its specification**. Every interface does
  carry test modules and the suite is green, which is why the
  principle is armed rather than pledged; what is uneven is the
  second half. Only the blueprint has a true conformance
  artifact — `test_conformance_corpus.py`, one fixture corpus run
  against both the parser and the published schema so the two
  cannot drift. Everywhere else the tests assert behavior the
  author knew about, which catches regressions but cannot catch
  **a requirement the spec states and the code never
  implemented** — the failure mode P24 exists for.
  The work is not "write more tests": it is deciding, per
  interface, what a spec-derived case set looks like and whether
  the conformance-corpus pattern generalizes past a document
  format. Where a surface genuinely cannot be tested that way,
  P24's own clause applies — **name the gap**, do not exempt it
  quietly.
  Was [design/audits.md](design/audits.md)'s third audit question;
  under D48 a named gap against an armed principle is a defect,
  not a proposal.

- **The DOS drive-letter map assumes one volume per hard disk
  and does not say so** (filed 2026-07-27 by D47, the hour P17
  armed). P17 requires that where the declared facts leave an
  address ambiguous the call fails closed naming the ambiguity
  (P11). `platform_dos.drive_letters` instead assumes one volume
  per hard disk — its own docstring says so, and offers the
  caller a workaround: address a floppy, or declare fewer disks.
  A guest that partitioned a disk shifts every letter after it,
  and `put-file "D:\X"` then writes confidently to the wrong
  drive with nothing reported.
  **Reliquary is right not to look** — asking the guest is
  exactly what P10 forbids, so the fix is not detection. It is
  honesty about the assumption: report it where the machine
  declares more than one hard disk and a letter at or past the
  second one is addressed, or narrow what the mapping claims.
  Which of those is the design question this carries.
  **[F16](proposed/FEATURES.md) already names the same hazard
  from the other side** — a caller who copies the letter rule
  "cannot know" when a disk carries several volumes — which is
  worth knowing before designing a fix: whatever this reports,
  the public query F16 proposes has to report too.
  Filed as a defect and not a feature because the norm it
  violates is already standing — that is the whole mechanism
  P5/P14/P17/P18's promotion turned on.

- `--qemu` is removed by the spec and still declared in the code
  (found 2026-07-27 by the gate audit, checking a task that
  proposed renaming it). [docs/spec/cli.md](../docs/spec/cli.md)
  says the old global `--qemu`, `--platform` and `--port` "are
  removed", yet `_FLAG_ARITY` in `reliquary/cli.py` still lists
  `--qemu`, which no subparser defines. Delete the entry.
  `--platform` and `--port` stay: they are live per-command
  options, and their place in that table is the documented
  position-carries-no-meaning rewrite, not the removed globals.
  **The consequence is small and worth stating so it is not
  oversold** (measured, not reasoned): `rlq --qemu foo
  list-machines` today fails with "unrecognized arguments: --qemu
  foo", which is a perfectly clear message — the arity entry is
  what makes it clear, by letting the reorder carry the pair past
  the command word. Deleting it drops `--qemu` into the
  unknown-leading-token path, where the message is *worse*
  ("invalid choice: 'foo'"), so the honest fix is the deletion
  plus whatever keeps a removed option from degrading into that
  path — which is a question about the reorder, not about
  `--qemu`. What makes this a defect either way is the
  divergence: the code names an option the spec says is gone.
  (This also retires the "`--qemu` → `--qemu-home`" task that had
  sat under Small items since before the option was specified
  away — renaming it would reinstate it.)

### Language

The **script-language residuals** stay here rather than becoming a
feature (D45): they change the scripting language, which is no bar
to being a task, and on size they are two items and a ride-along.
**No use case asks for them**, said plainly rather than papered
over — they serve language goal **G6**, one small vocabulary and
one spelling — and the catalogue behind them is
[design/script-examples/](design/script-examples/), whose README
carries the numbering and the deletion rule. The order below is a
guess at fix cost, never validated against real authoring pain;
reorder freely once scripts have been written and debugged under
this surface.

- **[08] reserve the small closed vocabularies globally** — key
  names and drive slots, so they cannot be shadowed by phase or
  artifact names. Mechanical, no spec redesign, and it closes most
  of the asymmetry the deleted [01] showed
- **[06]'s remaining half** — warn when an `@`-reference matches
  no known item. The label/item split itself is gone with the
  media block (DECISIONS.md, no JSON in scripts)
- riding along with whatever touches it next: **[03] does not
  currently parse** — its `on` handler bodies end without a
  terminal. It is a live example, so it should be valid where it is
  not deliberately illegal

  *Deliberately not tasks.* [03] and [07] stay documented
  tradeoffs rather than bugs — boundary tax (guest-text escaping)
  or placement-equals-scope consequences, where a "fix" mostly
  relocates the mush rather than removing it. Several are the
  procedural/declarative seam showing through the syntax: read
  "Primary language goals" (G1–G7) and "The procedural–declarative
  seam" in [script-spec.md](../docs/spec/script-spec.md) before
  proposing fixes, and judge any fix against the goals it costs
  rather than in isolation.

- the full Reason-blockquote editorial sweep of script-spec.md
  remains deliberately open (may trail realignment); the
  error-id INDEX is deferred to beta
- resume the spec-audit work the AHK/Python failure-catalog
  studies were feeding: the studies themselves are complete and
  their imports are recorded in DECISIONS.md, but the spec audits
  hit the session limit. (The workflow handle the entry carried,
  `wf_1a266a6b-ff8`, is dead — a run id resumes only within its
  own session — so this restarts rather than resumes.)

### Small items

Small, obvious, just haven't met the bar for scheduling (the
section formerly named Wishlist, then Backlog). Parked non-GitHub
issues land here. Most would qualify as housekeeping (D38) and
need no entry at all once someone picks them up.

- **Audit the blueprint field reference for orphaned norms**
  (2026-07-26, from the spec/descriptive split). The blueprint's
  norm is now the published schema (structure) plus
  docs/spec/blueprint-model.md (semantics), and
  docs/blueprint-reference.md was demoted to descriptive.
  Walk its per-field contracts (units, controller vocabulary,
  boot semantics, materialize modes): anything load-bearing that
  neither the schema nor the model states gets promoted into one
  of them, so no rule is left normless.
  The audit is a task, but **its findings may not be** (noted
  2026-07-27): relocating a rule unchanged passes P23's clarify
  test, while anything that reads as a *new* requirement on the
  blueprint is an interface change and takes the argued route.

- CLI help: run-script's text says little more than "runs a
  script on a machine". Not an interface change — it changes no
  rule, and pretty output is uncontracted — so it is housekeeping
  the moment someone picks it up; it keeps its line only because
  writing the replacement is authoring rather than a one-word fix.

- README, blueprints and machines: give several clear examples
  to illustrate the concepts — e.g. a 1 MB MS-DOS blueprint;
  QEMU machine #0; QEMU machine #1; QEMU machine #3 with a
  specific floppy image mounted; QEMU machine #4 with 16 MB of
  memory and a specific cdrom mounted


## Completed

Records whose reasoning outlives the work — audits, restructures,
resolved rounds — kept until each is folded where it belongs and
pruned, which is itself a pledged task above.

**An ordinary task is struck, not moved here** (D45): its record is
its commit and its CHANGELOG line, so it leaves this file by
deletion the moment it is done. Parking one here is the ceremony
this file already refuses for work that arrives done.

### The gate audit — 2026-07-27

Every entry in [Pledged](#pledged) walked against this file's own
gate: *is this free-standing work small enough to be a task?*
**Size and kind, never subject matter.** Touching an interface is
no bar (D45) — entry here is approval, so the gate that matters
already sat at the door. The walk's first pass asked the wrong
question, borrowing the **housekeeping** boundary that excludes
interface changes absolutely; that boundary compensates for
housekeeping being ungoverned and does not reach a queue only the
owner can write to. [F16](proposed/FEATURES.md) is where the
borrowed reading started and is corrected in its own text.

**Six entries left**, none of them rejected: they were pledged
already, and the audit changed where they are housed, not what
they are.

- To [pledged/FEATURES.md](pledged/FEATURES.md), on its **size**:
  **F17** (input pacing, from Design) — seven work items with a
  bisection rig among them, which no queue of small work can hold.
  The script-language residuals travelled with it on the first
  reading and stayed here instead, being two items and mechanical.
- To [proposed/FEATURES.md](proposed/FEATURES.md), each carrying an
  open shape question — the argument, not the surface, being what
  keeps them out of a queue of pre-approved work: **F18**
  (`download-media` + `extract-media`, one feature because they
  share a scaffolder), **F19** (the home inventory report), **F20**
  (`version` and `help` as commands, which is a P6 question about
  the API twin rather than a rename).
- To that file's **Horizon** list: `diff-blueprint`, one line of
  intent and no design.
- Folded into **F7**: the design-document audit, which was pledged
  here and proposed there at once.

**Two defects came out of the walk**, entered above: `--qemu`
survives in the code after the spec removed it, and DECISIONS.md
still names ARCHITECTURE.md by its old title. **One entry closed**
as satisfied ("Define horizon, or drop it" — see below), **two were
rescoped** against a tree that had moved under them (the principles
promotion, the demand-citation sweep), and **one pointer was
corrected** (U3's, which named a file that no longer exists).

What stays is what the gate admits: adjudications, audits of the
machinery, defects, documentation work, and the script-language
residuals. Some of those touch an interface, which is exactly the
point — the file admits work by its size and its kind, and asks
nothing about which surface it lands on.

### "Define horizon, or drop it" — satisfied 2026-07-26

Closed by the restructure rather than by being worked. The word now
carries a definition at first use —
[proposed/FEATURES.md](proposed/FEATURES.md)'s Horizon section
opens "Not a feature, and so unnumbered. This is a holding list of
items too small or too unformed to be one" — with an exit rule
saying how an item leaves. That answers the entry's first branch
("define it at first use"), and the complaint behind it is gone
with the roadmap: the collapse it objected to was *horizon* drifting
into a synonym for backlog, and the lifecycle folders now carry
that distinction structurally. The four documents that use the word
(AGENTS.md, `cli.md`, `instance-model.md`, `api.md`) all point at
that section, so the definition is reachable from every use.

### The numbered arc — milestones 1–9 (complete)

**The numbered arc ran 1 through 9 and ended there**, carrying
text-mode DOS on QEMU from the north-star command to the
programmatic testing loop: the vertical slice and the built-in
blueprint bundle (1), the media library and caches (2), the
scripting language on its first, now-superseded surface (3), the
script-surface realignment to the July 2026 redesign (4), the local
HTTP server for installer answer files (5), the instance model and
machine blueprints with authored-asset residency (6), the composed
blueprint model folding the blueprint and media formats into one
(7), the script properties — user properties file, secret storage,
binding pipeline, declared derivation, `${key}` references (8), and
the programmatic testing loop — the run returning its output, live
feedback, the error taxonomy, and the exec-run mechanics (9).
Asynchronous runs left the arc for lack of a use case (D35/D36).

The per-milestone deliverable and stage breakdowns are **pruned**:
the record survives in git history, the CHANGELOG, and the D-numbers
each round produced, which is the standing rule for completed
breakdowns. Generalizing beyond that one vertical is unbuilt and
unscheduled (D33) — it lives in
[proposed/FEATURES.md](proposed/FEATURES.md), design settled and
intact, and returns to a numbered arc when the case it serves is
pledged.

### The planning restructure — executed 2026-07-26

*Moved out of [Pledged](#pledged) on 2026-07-27: it was a
finished record sitting in a queue, and a queue holds what
waits. The one obligation it still carries — the D-numbers step
6 says are owed — is entered as an adjudication above.*

**Executed 2026-07-26** (owner, interactively). The
four-step plan below ran as one pass, and the roadmap is gone. What
landed, and where it diverged from what step 2 decided:

1. ~~Split the unscheduled work into `planning/BACKLOG.md`~~ —
   **done**, as `planning/proposed/FEATURES.md` rather than
   BACKLOG.md: the lifecycle word beat the scheduling word, and the
   file sits in the folder that already means "not pledged".
2. ~~Restructure `planning/` around the lifecycle~~ — **done** as
   `proposed/` + `pledged/` + `design/`, landing as decided: the
   proposals files split across the two folders, and the governing
   files (`INTERFACES.md`, `DECISIONS.md`, `TASKS.md`) stayed at the
   planning root. Both took a wrong turn first and were corrected in
   the same pass, each correction found by the owner asking the
   right question. Filing the proposals whole under `proposed/` made
   "nothing is worked from proposed/" false, since P5, P14 and U1–U6
   are pledged; filing `DECISIONS.md` under `pledged/` put the
   *refusal* record — and the open questions — in a folder claiming
   the opposite. **The rule the second one yielded is worth keeping:
   the lifecycle folders are for artifacts that *move between them*.
   Machinery that never moves belongs at the root.**
   One thing is new rather than decided: `TASKS.md` is reframed as
   the third input queue (small, pre-approved, unordered), which
   widens D39's two and wants a D-number. [D43 gives it one.]
3. ~~Migrate delivered design out of ROADMAP~~ — **done**, first
   into `planning/design/` and then out again (step 5).
4. ~~Condense the completed milestone sections to notes~~ —
   **done**, and harder than the ~180 lines planned: milestones 1–9
   are one paragraph in [Completed](#completed). The
   demand-citation audit above had not run first, so what demanded
   milestones 1, 2, 3, 4 and 6 was **not** captured before the
   deliverable lists went. It survives in git history
   (`git show 50b67b2:planning/ROADMAP.md`) and must be recovered from
   there if that audit still wants it.
5. ~~Split the delivered specs out of `planning/`~~ — **done**, and
   this was the plan's sharpest finding: `planning/design/` was
   doing four jobs, and the largest was ~12 normative specs of
   *delivered* interfaces, which is current truth and does not
   belong under `planning/`. The decided remedy was a top-level
   `spec/`; **what landed is `docs/spec/`** (owner, 2026-07-26),
   because `docs/` already means the live situation, so the spec
   sits beside the reference that derives from it rather than in a
   third tree of its own. `docs/spec/README.md` states the
   normative direction: the spec binds the implementation, and a
   disagreement is the code's bug.
   Design was resolved along the same axis rather than being left
   as a residue: feature design moved beside its feature
   (`proposed/design/`, `pledged/design/`), and only design
   serving no single feature stayed in `planning/design/`.
   Machine-readable schemas moved into the package,
   `reliquary/schemas/`, since code consumes them — which also
   deleted two dead ones (`machine-blueprint.schema.json`,
   `media-definition.schema.json`): zero references anywhere, and
   both described the pre-composition format milestone 7 replaced,
   so they contradicted the shipped schema rather than duplicating
   it.
6. **PRINCIPLES.md became ARCHITECTURE.md** (owner, 2026-07-26):
   the root document is the architecture in force — the
   whole-system view (absorbed from the former
   `planning/design/architecture.md`) plus the P-numbered
   principles, matching the ARCHITECTURE.md convention readers
   expect at a repo root. The mirrors renamed with it
   (`proposed/ARCHITECTURE.md`, `pledged/ARCHITECTURE.md`),
   restoring mirror-by-name across all three ladders. The same
   pass itemized the model doc's unnumbered principles as
   P19–P21, and stated P22 (no CI, at this time) — a rule
   previously cited in this file but written down nowhere.
   ~~The P-additions and the rename want D-numbers, with
   pledge-is-the-move (amends D23) and the third queue
   (widens D39).~~ — **paid 2026-07-27**: the third queue by
   D43, everything else by **D50**, which found the debt was
   twice what this summary records. The commit's own closing
   paragraph flagged seven items, not four; this step listed the
   ones it could see from inside the restructure record, and
   P23, the INTERFACES split, the norm-is-interface clause and
   the format-stability promotion were owed too.

### Design rounds resolved

- Media residency vs the download cache AND composable authored
  specs — RESOLVED together (owner, 2026-07-23, the media/composition
  design round), then REVISED same day by the blueprint revision
  round (both in DECISIONS.md; milestone 7 is the
  retargeted implementation): two spec types (machine / media —
  archive absorbed as the container reading), a flat typed root
  array, one schemed `location` field, no source component, no
  composition (identity-dedup instead), and the single name-keyed
  `cache/media/` (content addressing declined in both rounds; the
  identity ledger that round added was deleted by D41, which left
  the decline's ground unchanged). blueprint-model.md is now the
  worked design of the revised model, rewritten at milestone 7's
  S1 and normative in the decision entries' place.
- Media lifecycle commands — RESOLVED (owner, 2026-07-23,
  DECISIONS.md D30, run as milestone 7's decide-first round):
  the noun in every media verb is the media, never the owning
  file; `delete-media` and `seed-media` are deleted outright
  (P9 — a command that can only fail and a no-op that "still
  resolves" are the shim the rule names); `list-media` keeps
  its plain name list with owning file, containment parent and
  cache state behind `--verbose`, a dedup'd media showing every
  declaring file on its one row, anonymous inline blanks never
  listed. Component-removal tooling is parked, arriving as its
  own named thing under the interface-change rule if a real
  case appears.

- CLI clean — RESOLVED by the blueprint revision round
  (DECISIONS.md, 2026-07-23): `clean-media` (blunt + targeted
  eviction) and `prune-media` (attachment-closure prune of
  unneeded entries) land at milestone 7; `clean-archives`
  retires with the single cache dir. Machine-cache cleaning
  remains the open decision in DECISIONS.md "Open questions" (was "Decisions still
  needed".

## Rejected

Refused work, indexed here and argued in
[DECISIONS.md](DECISIONS.md) — that file is already the guard
against re-litigating, so this section stays a pointer and never
restates the argument. Empty today: historic refusals
(`delete-media` and `seed-media` under D30, `clean-archives` with
the single cache dir) were recorded straight to DECISIONS.md
before this section existed, and are indexed with the design round
that made them.

