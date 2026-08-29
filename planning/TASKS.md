<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# TASKS

This is the backlog of pledged work. A task that's still just
proposed lives in the issue tracker —
<https://github.com/ferroteca/reliquary/issues> — which is the only
place a proposed task exists (D43): the issue tracker is a task's
"proposed" stage, and this file is its "pledged" stage. So nothing
here is waiting for a decision — showing up in this file *is* the
decision.

**Everything listed here is pledged** — the same four-word
vocabulary used in [README.md](README.md) (proposed, pledged,
completed, rejected) applies here too. Because an entry here is
already in the pledged state, adding it to this file *is* approving
it: nothing waits for a decision, nothing needs its own citation,
and there's nothing left to promote. This file doesn't live inside
the `pledged/` directory, because `proposed/` and `pledged/` hold
demand and capability — things argued for at length — and a task
isn't either of those. It's free-standing work that's too small to
count as a feature, and too small to need a formal argument. That's
a difference in kind, not just in size.

This file is the third of the project's three work-intake queues
(D43, which expanded D39's original two). Adding something here is
controlled by the same approval gate that covers all writing under
`planning/` — and that gate matters most here, because this is the
one action where approval is granted with no argument behind it at
all.

**A queue is for work that's waiting to be done.** Work that's
already finished never gets added here — there's nothing left to
schedule, only a decision, and filing an entry just to close it in
the same act would be pointless.

**Anything gets deleted from this file once it's done** (D45,
extended by D52) — tasks, audits, restructures, and multi-step
rounds of work all follow this rule. The record of what happened is
its commit, its CHANGELOG entry, and any D-numbers it produced — so
it leaves this file by being deleted, nothing sits around
afterward. This file also isn't a place for retrospectives: a note
explaining what a now-empty section used to contain is really the
same problem, just one paragraph later, and it would have to be
updated every time the underlying work moves. The same applies to
the **lists of work items inside a pledged feature**: once the
feature is delivered, its whole list is deleted along with its
F-number rather than archived. Anything whose reasoning needs to
outlive the work itself is a decision, and decisions belong in
[DECISIONS.md](DECISIONS.md) — if that kind of record were kept
next to the work instead, a summary would drift out of sync with
what it's summarizing, and a reader would have no way to tell.

**Nothing here is in any particular order.** No entry is scheduled,
and none takes priority over another — whoever wants to do the work
picks whatever they like. The one place order does matter is inside
a feature: work that only makes sense as part of one pledged
feature is listed with that feature, in
[pledged/FEATURES.md](pledged/FEATURES.md), and has to happen in
order to complete it. But a task in this file that's merely
*related* to a feature — not required by it — can still be picked
up whenever.

Housekeeping (D38) is one size smaller still: work that's tiny and
obviously worth doing doesn't need an entry here **at all** — it's
pre-approved as a category, and the commit is its only record. This
file is for pre-approved work that's still worth writing down;
housekeeping is for pre-approved work that isn't. The full picture
of how work enters the project — the intake queues, the
housekeeping test, and how pledging gets recorded — is in
[README.md](README.md).

**Rejected work doesn't get recorded here** (D52). Since adding
something to this file is itself the approval (D43), a rejected
task is simply one that was never added — the rejection happens at
the door. The record of that rejection is the closed GitHub issue,
or the entry in [DECISIONS.md](DECISIONS.md) that argued against
it; DECISIONS.md already serves as the guard against re-arguing the
same rejected idea.

The actual queue is the [Pledged](#pledged) section below. It's
grouped by kind of work, because different kinds are done by
different people and approved by different checks — but the
grouping isn't an order to work through.

Open questions to revisit later as the design becomes more settled
aren't tasks — those live in [DECISIONS.md](DECISIONS.md), under its
open questions section.

## Every task is itemized

**Every task has a T-number** (D86), written like this:
`T8 — Widen the drive report` — the number and the name together,
the same way an F-number is written, no matter what heading level
the task sits at. A task is an item like any other item in this
system, and D42's numbering rule applies to it for the same reason
it applies elsewhere: anything other work might depend on needs a
stable handle, because a heading's wording can be edited later and
isn't something safe to point at. The number is what a commit
cites, what another task can point to, and what survives even if
this file gets reorganized — the groupings below are by kind of
work, not by order, so an entry can move between groups. Without a
number, a task would be identified only by its heading text, which
isn't stable enough.

**A task's number is issued the moment it's added to this file**,
which for a task is the same moment as being pledged: a task never
has a "proposed" stage inside `planning/` (D43), so there's no
earlier point at which a number could be issued. Before that, the
idea is only identified by its GitHub issue number. This is the one
way tasks differ from features: an F-number is issued when the
feature is first proposed, and it carries that same number all the
way into `pledged/`.

**A task's number retires when the task is delivered** — it doesn't
outlive the work. This is the second of the two kinds of handle D42
defines: a use case, a principle, and a decision are permanent
records, so their numbers stay forever, while a feature's number
just names work that hasn't happened yet, and goes away once that
work lands. A task is work too, so when a task is struck off the
list, its number is retired along with it (D52). A retired number
is never reused — so a T-number that survives in an old commit
message will always point to the same thing, and a gap in the
numbering just means something was finished, not something still
pending.

**T-numbers now come from the shared sequence ledger**
([SEQUENCES.md](SEQUENCES.md); owner, 2026-07-31), which now holds
the highest-issued number that used to be tracked in this file.
Take the next number from there, and update it in the same edit.
The reasons a running mark needs to be tracked at all — this queue
empties out over time, a struck task's only remaining record is its
commit (D52), and a search only sees the branch you're on — are
explained alongside the ledger, along with why the T-sequence
starts at T8.

## Pledged

Grouped by kind of work, because who does it and how it's approved
differ: an audit is mechanical, and a bug fix needs no separate
pledge because the rule it's violating is already a commitment on
its own. A group with nothing in it isn't shown at all — an empty
heading would just be a record of finished work, and this file
doesn't keep those.

### Backends

- **T32 — Detect a usable bridge interface for QEMU's `bridged`
  network attachment.** `network`'s `bridged` attachment (D120) works
  today by naming an `interface` explicitly, or by falling back to
  QEMU's own default (the conventional bridge name `br0`), which
  fails closed if the host hasn't set one up. This task adds
  detection: read the host's default-route interface and use it only
  if it's already a member of a bridge, failing closed by name
  (naming the interface and telling the user what to bridge) when
  it isn't. No automatic bridge creation — that mutates host network
  configuration and stays out of scope entirely (D120). VirtualBox
  and VMware aren't affected: both already pick a sensible default
  bridge target on their own when `interface` is omitted.

