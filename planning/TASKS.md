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
complete it. **No feature has any today**, the shelf being empty:
F1's items left with it when it was withdrawn to `proposed/`
(D61), and F17's and F23's retired with their deliveries (D60,
D62). A task here that merely *relates* to a feature is still free
to be picked whenever.

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

*(Emptied and struck on 2026-07-27, as the restructures and the
adjudications were before it. The supports retrofit was the last
one standing and it is done: every live entry in
[DECISIONS.md](DECISIONS.md) now names the use cases, principles
or goals it supports — 54 of 56, the two exceptions being the
retired D2 and D17, which bind nothing and which the file's own
practice already exempted. The third audit had left on the same
day into [F7](proposed/FEATURES.md).*

*The class it audited for is not struck with it — the
traceability rule stands, and new entries carry supports from the
start. What retires is the standing backlog of entries written
before the rule existed.*

*Two entries the tally passed on the letter of the clause were
closed 2026-07-28: **D1** said "Supports (none)" and **D40**
named a spec promise rather than a numbered one, so both carried
a supports clause citing no vision. D1 now cites P18 — clarified
the same day to state what the codex is and is not — and D40
cites U12, U13 and P5. The audit's own claim is therefore true
now in a way it was not when written: every live entry names
numbered vision, the two exceptions still being retired D2 and
D17.)*

### Defects

A gap against a *standing* principle is a bug: the principle is
already its demand, so these need no pledge, only fixing. A gap
against a **shipped spec** is the same class and sits here too —
where `docs/spec/` and the code disagree the spec is right and the
code has the bug, so the norm is already the demand.

- **An image drive has no in-band route** (P16's residue, filed
  with its arming — D62, 2026-07-27, per D48's bar). All five
  in-band file verbs — `put-file` / `get-file` / `put-files` /
  `get-files` / `list-files` — need a directory-source drive, and
  refuse an image drive by name (`drive.not-a-host-directory`,
  which is P11 doing its job). So a consumer whose results are on
  an installed `C:` still has to reach around Reliquary with its
  own image tooling, which is exactly what P16 now forbids
  Reliquary to require. The fix is at-rest filesystem access
  behind the adapter seam — read and write a FAT volume in a drive
  image on the host, which is no more guest inspection than
  reading an image's format is (P10 untouched, and the same
  capability D56 named as the way to grow the letter map). It
  stays capability-honest per call: a filesystem the adapter
  cannot read fails **by name**, never by guess. Related but not
  this: the *letter* map's own gap (D56) is refusal for a
  different reason, and a backend with no vvfat equivalent is F2/F3's.

*(The rest of this group was emptied and struck on 2026-07-27,
the last of the five groups. The
standing identifier defect was the final entry: `script-spec.md`
requires an id of every diagnostic, and every diagnostic has one —
284 ids across 26 subjects, all 26 listed in the spec's prefix list
and held there by test.

It closed in four passes, each measuring the next: the script surface
(82 static, then 43 preflight and runtime), the properties file and
CLI (40, where the reuse rule first paid off), the blueprint document
(97, its subjects argued rather than guessed), and the rest (108,
subjects all reused). The population went from 30 to 288 in between,
because D58 generalized the error classes and the id requirement
travelled with them — one ratification turning a script-surface job
into a whole-system one.

Three guards keep it closed rather than a measurement having to be
repeated: every deliberate raise carries an id, every id's subject is
one the spec lists, and both corpora assert that the declared id is
the one that fires. What is *not* closed is a **located** blueprint
diagnostic — `document.py` walks a parsed object with a `where`
breadcrumb and no line, so position has to be threaded through the
parse. That is its own work, untouched by the ids, and wants its own
entry when someone picks it up.)*

### Small items

*(Emptied and struck on 2026-07-27, as the audits, the restructures
and the adjudications were before it. The two orphaned blueprint
rules were the last entry standing, and taking them found the reason
they resisted promotion: both described capability that does not
exist. The `controller` caveat was correctly gated — no machine can
mix controller types — and its constraint now sits with F2's device
growth, plus a guard in `platform_dos.drive_letters` asserted by
test so the invariant is local rather than borrowed from a gate three
modules away. The backend/format table was **not** gated: a blueprint
naming `virtualbox` was accepted and materialized qcow2, which made
the document right and the code wrong, so an unwired backend is now
refused like an unwired controller (P11) and the table's three
unbuilt rows are intent recorded against F2 and F3.*

*Neither was promoted, which was the entry's own question: a rule
about unbuilt capability belongs with the work that would build it,
not in a spec that states what exists.)*
