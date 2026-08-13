<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
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
leaves this file by deletion and nothing is parked. **Not a
retrospective either**: a note explaining what an emptied group
used to hold is the same parking one paragraph further on, and it
has to be edited every time the work it accounts for moves. The
same holds for the **work-item breakdowns inside a pledged
feature**: when the feature delivers, its list is deleted with its
F-number rather than archived. A record whose reasoning outlives
the work is a decision, and decisions live in
[DECISIONS.md](DECISIONS.md) — kept beside
the work instead, a summary drifts from what it summarizes and a
reader has no way to tell.

**There is no order here.** Nothing in this file is scheduled, and
nothing claims priority over anything else; whoever picks work up
picks whatever they like. The one ordering that does bind is a
feature's: **work that only makes sense as part of one pledged
feature lives with that feature**, in
[pledged/FEATURES.md](pledged/FEATURES.md), and has to be done to
complete it. A task here that merely *relates* to a feature is
still free to be picked whenever.

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

The queue proper is [Pledged](#pledged) below — grouped by kind
because the actor and the gate differ, though the grouping is not
a running order.

Standing questions to re-ask as the design hardens are not tasks
and live with the decision record, under
[DECISIONS.md](DECISIONS.md)'s open questions.

## Every task is itemized

**A task carries a T-number** (D86) — `T8 — Widen the drive report`,
number and name together, the way an F-number reads, at whatever
heading depth its group sits at. A
task is an item like any other, and D42's rule reaches it for
D42's reason: every item that can be depended on needs a handle,
because a heading someone may reword is not something to point
at. The number is what a commit cites, what another task points
at, and what survives this file's own regrouping — the groups
below are kinds rather than a running order, so an entry may move
between them, and without a number its heading text is the whole
of its identity.

**The number is issued at entry**, which for a task is the pledge
itself: a task has no proposed state under `planning/` (D43), so
there is no earlier moment to issue one at, and the idea that
preceded it carries the tracker's own issue number instead. That
is the one asymmetry with an F-number, which is issued at
proposal and travels into `pledged/` unchanged.

**And it evaporates on delivery**, with the work rather than
outliving it. That is D42's second handle class: a use case, a
principle and a decision persist, so their numbers are permanent,
while a feature names work not yet done and its handle goes when
the work lands. A task is work, so a struck task takes its number
with it (D52). **Evaporating is not reusable** — the number
retires and is never issued again, so a T-number surviving in a
commit message can never resolve to something else later, and
gaps in the sequence are history rather than a promise.

**T-numbers are issued against the sequence ledger**
([SEQUENCES.md](SEQUENCES.md); owner, 2026-07-31), which holds the
high-water mark this file used to state — take the next number
there and advance it in the same edit. The reasons the mark must
be stated at all — the queue empties, a struck task's only record
is its commit (D52), and a search sees only the branch it stands
on — live with the ledger, along with the sequence's T8 start.

## Pledged

Grouped by kind, because the actor and the gate differ: an audit
is mechanical, a defect needs no pledge because the norm it
violates already is one. A group with nothing in it is not listed:
an empty heading is a record of retired work, which this file does
not keep.

### Defects

#### T27 — A stopped-only verb reached with the machine running is refused five minutes late

`set-boot` against a running machine fails closed and by name —
`machine.must-be-stopped`, a `PreflightError` at exit `3`, so
nothing is silently ignored. But it fails at **run** time, and for
the shape that provokes it — flip the boot device, start, install,
stop, flip back — run time means after five minutes of installing.

**The script text already decides it.** The header declares the
starting state (`machine stopped`, or the default `running`), and
the language knows exactly which verbs start and stop the machine.
A statement provably reached with the machine running is therefore
decidable before anything reaches a guest, which is what the
V-numbered rules do with every other authoring mistake of this
kind.

Bounded by the reachability limit the rest of the static pass
already accepts — a handler body is the guest's decision, not the
plan's, and `script_validation.reach` is where that boundary is
already drawn. So this is a rule about the statements a static pass
can **promise** will run, and silence everywhere else: a false
refusal would be far worse than the late failure it replaces.

The rule takes a V-number issued against
[SEQUENCES.md](SEQUENCES.md), and its fixtures go in the script
corpus declaring that id, as that corpus requires.

Recorded 2026-08-13, from the same live FreeDOS install that drafted
U24; it was deliberately left out of that use case, because
`set-boot` does not go away if U24 is delivered. **F54** reuses this
analysis for its own exit check.
