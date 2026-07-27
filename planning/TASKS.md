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

  **The CLI half is done (2026-07-27), and it paid immediately.**
  `ClaimedCommandTests` compares the command words
  `docs/spec/cli.md` writes after `rlq` against `cli._COMMANDS`,
  both directions. Writing it found the spec specifying **five
  commands that did not exist** — `clone-machine`,
  `export-machine`, `export-drive`, `search-media`,
  `search-scripts`, in present tense with worked example
  output — and **five that shipped undocumented**, one of which
  (`get-machine-var`) a careful hand sweep the same day had
  missed. The root cause was one line: cli.md's banner still
  called it *"a working document for brainstorming"*, so by the
  banner-is-the-marker rule it had never claimed to be true.
  **What that suggests for the remaining interfaces**: look for
  the cheap inventory comparison first — the thing where a spec
  enumerates and the code enumerates, and a set difference is the
  whole test. It is not the deep conformance the blueprint corpus
  achieves, but it caught six divergences in one sitting and it
  generalizes without a design round. Candidates: the S-id list
  against the diagnostics that cite them; the error classes and
  exit codes against `errors.exit_code`; the script language's
  verb table against the grammar's node names.
  **Check the banner first, wherever this goes next.** cli.md
  could not be made true while it disclaimed being a spec, and
  the sweep found one more marker wrong in the same way:
  `asset-resolution.md` **has no status banner at all**, so its
  standing is undeclared — the same rule broken a different way,
  and unfixed.

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

### Small items

Small, obvious, just haven't met the bar for scheduling (the
section formerly named Wishlist, then Backlog). Parked non-GitHub
issues land here. Most would qualify as housekeeping (D38) and
need no entry at all once someone picks them up.

- **Two blueprint rules that need arguing, not relocating** (left
  behind 2026-07-27 when the other orphaned norms were promoted).
  Both live only in the descriptive field reference, and both read
  as **commitments** rather than restatements — which is the line
  the audit warned about: relocating a rule unchanged passes P23's
  clarify test, and asserting a new one does not.
  - **`controller`'s ordering caveat**: *"slot order is
    authoritative only within a controller type; across mixed
    types the guest's firmware decides and Reliquary cannot
    promise a global disk order."* That constrains what Reliquary
    may promise about guest disk order, which is a claim, not a
    restatement — and it is a **second source of the drive-letter
    ambiguity** filed against P17 above, which names only the
    multi-volume case. Whoever takes either should read both.
  - **The backend→format table** (qcow2 / VDI / VMDK / VHDX)
    behind "format-portable by construction". Binding four
    backends to four formats is a commitment about three backends
    that do not exist yet.
  Neither is urgent: they are stated in a descriptive document
  today and would be stated in a normative one after, so nothing
  is unspecified in the meantime — what changes is whether the
  code is free to diverge from them.

- CLI help: run-script's text says little more than "runs a
  script on a machine". Not an interface change — it changes no
  rule, and pretty output is uncontracted — so it is housekeeping
  the moment someone picks it up; it keeps its line only because
  writing the replacement is authoring rather than a one-word fix.

- README, blueprints and machines: give several clear examples
  to illustrate the concepts — e.g. a 1 MB MS-DOS blueprint;
  QEMU machine #0; QEMU machine #1; QEMU machine #3 with a
  specific floppy image mounted; QEMU machine #4 with 16 MB of
