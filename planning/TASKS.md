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

**Anything is struck when it is done** (D45, generalized by D52) —
tasks, audits, restructures and rounds alike. Its record is its
commit, its CHANGELOG line, and the D-numbers it produced, so it
leaves this file by deletion and nothing is parked. The same holds
for the **work-item breakdowns inside a pledged feature**: when the
feature delivers, its list is deleted with its F-number rather than
archived. A record whose reasoning outlives the work is a decision,
and decisions live in [DECISIONS.md](DECISIONS.md) — kept beside
the work instead, a summary drifts from what it summarizes and a
reader has no way to tell.

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

**Refused work is not recorded here** (D52). Entry to this file
*is* approval (D43), so a rejected task is one that never
entered — refusal happens at the door, and its record is the issue
that was closed or the [DECISIONS.md](DECISIONS.md) entry that
argued it, that file already being the guard against
re-litigating.

The file is one section, [Pledged](#pledged) — the queue proper,
grouped by kind because the actor and the gate differ, though the
grouping is not a running order.

Standing questions to re-ask as the design hardens are not tasks
and live with the decision record, under
[DECISIONS.md](DECISIONS.md)'s open questions.

## Pledged

Grouped by kind, because the actor and the gate differ: an audit
is mechanical, a defect needs no pledge because the norm it
violates already is one. (Two further groups — the restructures,
then the adjudications — were struck on 2026-07-27 as each
finished: D46–D51 are the adjudications' record, and D50 the
restructures'.)

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

- **`hostdir` survives a drive type that retired** (found
  2026-07-27 by the blueprint-field audit; the `runs/` half of
  this entry was fixed the same day). Milestone 7 replaced the
  `hostdir` drive with directory-source media — a media whose
  `location` is a directory, with `materialize: use` — and the
  word still appears in five live documents: `api.md` (twice),
  `cli.md`, `instance-model.md`, `media-spec.md`, and
  `blueprint-model.md`.
  **The work is sorting which are which**, and they are not all
  the same: `blueprint-model.md`'s is a *death record* ("the first
  round's four-way content selector … is gone"), which is correct
  and stays; the others read as live instruction naming a
  construct an author cannot write. The QEMU adapter also still
  uses "hostdir" internally for vvfat, so some mentions may be
  describing the adapter rather than the authored surface — worth
  keeping if so, and worth saying which is meant.

- **Diagnostics carry no stable identifier** (found 2026-07-27 by
  D55, checking what the error-id bullet was actually deferring).
  [script-spec.md](../docs/spec/script-spec.md) requires it of
  *every* diagnostic: "**every diagnostic carries a stable dotted
  identifier naming its rule** (`obs.two-channels` style);
  identifiers share one namespace across the classes, and the full
  id index is deferred to beta."
  The scheme does not exist. `obs.two-channels` appears nowhere
  outside that sentence. What ships instead:
  - **static rules** carry `(S5)`-style ids — 44 of them — which
    are neither dotted nor namespaced, and cover only the
    S-numbered restrictions;
  - **parse errors** (43 raise sites across `script_nodes.py` and
    `script_parser.py`) carry no id;
  - **preflight and runtime errors** carry none either — including
    the media-reference rejection added the same day.
  So one class has a *different* scheme and the rest have none,
  where the spec asks for one namespace across all of them.
  **The index is not the gap.** Deferring the id *index* to beta
  is fine and stays where the spec says it; what is unmet is the
  requirement that the identifiers exist at all, which is a
  today-rule and not a beta one. Sequencing follows from that: ids
  first, index at beta over whatever they turned out to be.
  Worth settling on the way in: whether `S5` becomes a dotted id
  under the one namespace, or stays and the dotted scheme covers
  only what has no id today. The spec says one namespace, which
  points at the first.

- **Reserved node names are not reserved** (found 2026-07-27 by
  D53, walking task [08]).
  [script-spec.md](../docs/spec/script-spec.md) requires it twice —
  the Grammar section's *"reserved node names (headers,
  declarations, and verbs) cannot name phases or property keys"*,
  and **S5**'s *"reserved node names are not identifiers"*. The
  code enforces neither. Verified by parsing:

  ```
  phase enter { ... }      parses
  phase cdrom0 { ... }     parses
  ```

  The cause is in the lexer: a word becomes a keyword token only
  when it **leads a line** (`script_parser.py`, `_convert` —
  `_KEYWORD_TERMINALS.get(...) if leading else "NAME"`), and no
  validation rule reserves anything afterwards. So the
  implementation is pure contextual keywording where the spec asks
  for the mixed line — syntax words reserved, domain vocabularies
  contextual.
  **The spec is right and the code has the bug** (D53 refused the
  opposite change, so the spec stands as written). The fix belongs
  in validation rather than the grammar, which is where the spec
  says closed vocabularies are checked.
  Ride-along, and probably why nobody noticed: the comment above
  `KEYWORDS` in `script_parser.py` states the reservation as
  though it were enforced — *"reserved everywhere a
  script-internal name may appear (S5)"*. It describes the intent
  correctly and the behaviour not at all.

- **The CLI spec and the CLI have drifted apart in both
  directions** (found 2026-07-27, checking one stale command
  reference and sweeping the rest). Five divergences, same class
  as `--qemu` above and larger.
  **Specified but gone**: `clean-archives`, in
  [docs/spec/cli.md](../docs/spec/cli.md) three times — the
  synopsis, the prose, and a worked example — reclaiming
  `cache/archives/`, which retired with it when the single media
  cache landed (CHANGELOG, "One media cache, wholly
  regenerable"). Neither the command nor the directory exists.
  **Present but unspecified**: `prune-media`, `add-media`,
  `put-file`, `get-file` — all four declared in `cli.py` and
  absent from the spec entirely.
  **The last two are the sharpest.** They are milestone 9's
  in-band file exchange, the capability **P17** was armed over
  (D47) — so the CLI spec does not declare the commands whose
  addressing an armed principle governs. It also explains why
  D47 gave P17 its normative home in `script-spec.md` and
  `api.md` rather than here.
  **This is evidence for the P24 defect above**, not a separate
  worry: four commands with no specification are four commands no
  conformance test could check even if one existed.
  Direction matters for the fix. The `clean-archives` half is a
  stale spec describing a deliberate removal, so the spec is
  simply wrong and is corrected. The four missing commands are
  live world-facing surface with no norm — writing that norm is
  authoring, and whatever it states about `put-file`/`get-file`
  must match what P17 already binds.

### Small items

Small, obvious, just haven't met the bar for scheduling (the
section formerly named Wishlist, then Backlog). Parked non-GitHub
issues land here. Most would qualify as housekeeping (D38) and
need no entry at all once someone picks them up.

- **Promote the blueprint reference's orphaned norms** (the audit
  ran 2026-07-27; this is its findings, not a second audit — all
  18 sections walked, each rule checked against the published
  schema and blueprint-model.md, and every orphan below verified
  implemented in the code). A rule stated only in
  [blueprint-reference.md](../docs/blueprint-reference.md) is
  normless: that document was demoted to descriptive, so it binds
  nothing and the code is free to drift from it.
  **The orphans, by field:**
  - **`memory`** — a bare integer means MiB (the size grammar the
    reference defers to *requires* a suffix, so this case is
    covered nowhere); the value must resolve to a whole MiB;
    per-platform defaults, dos 16 / openbsd 512 / win9x 64 /
    winnt 256, which live only in `machines._PLATFORM_MEMORY`;
  - **`boot`** — entries must name declared *and enabled* drives;
    entries are unique by slot in either spelling; an empty or
    non-bootable entry is valid and falls through (the documented
    install pattern depends on it); the default order when
    omitted — slot-0 floppy, else slot-0 hdd, else first cdrom;
  - **`controller`** — floppies reject the key; the default is
    `ide`; **slot order is authoritative only within one
    controller type**;
  - **drive keys** — the bare-medium alias means slot 0, and
    declaring alias plus indexed form is a slot clash;
  - **`name`** — "never all digits". The schema's pattern admits
    `123`; `document.py` rejects it;
  - **`control-planes`** — entries unique; an unbuilt plane is
    refused at materialization; the per-platform default;
  - **`backend-settings`** — the only place backend config may
    appear; it may not touch Reliquary-owned fields; its sections
    steer default backend assignment;
  - **image formats** — the backend→format table (qcow2 / VDI /
    VMDK / VHDX) that the "format-portable by construction" claim
    rests on.

  Clean, deferring correctly, and needing nothing: `materialize`,
  image *naming*, `platform`, `scripts` label priority,
  `parameters`, `description`, the state-only fields.
  **THE SPLIT THE ORIGINAL ENTRY WARNED ABOUT IS REAL, and two
  items fall the wrong side of it.** Relocating a rule unchanged
  passes P23's clarify test and is ordinary work. But
  `controller`'s within-one-type ordering caveat and the
  image-format table both read as *commitments* rather than
  restatements — the first constrains what Reliquary may promise
  about guest disk order, the second binds four backends to four
  formats. Promoting those is an interface change and takes the
  argued route; do not sweep them in with the rest.
  **One finding reaches outside this task.** `controller`'s
  ordering caveat is a *second* source of the drive-letter
  ambiguity already filed against P17 above — that defect names
  only the multi-volume case, and mixed controller types are an
  independent way the guest's lettering diverges from Reliquary's
  assignment. Whoever fixes either should read both.

- CLI help: run-script's text says little more than "runs a
  script on a machine". Not an interface change — it changes no
  rule, and pretty output is uncontracted — so it is housekeeping
  the moment someone picks it up; it keeps its line only because
  writing the replacement is authoring rather than a one-word fix.

- README, blueprints and machines: give several clear examples
  to illustrate the concepts — e.g. a 1 MB MS-DOS blueprint;
  QEMU machine #0; QEMU machine #1; QEMU machine #3 with a
  specific floppy image mounted; QEMU machine #4 with 16 MB of
