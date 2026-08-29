<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# planning

Planning documents for maintainers. Where a file sits tells you its
status — proposed or pledged — without needing to read it. File
names don't carry a status suffix; the directory does that job.

## The one vocabulary

A use case, a principle, and a task all move through the same four
stages (set by the owner on 2026-07-24): *proposed*, *pledged*,
*completed*, or *rejected*. The same four words are used for all
three kinds of item — demand (use cases), rules (principles), and
work (tasks) — and the directories below exist because of this
shared vocabulary.

- `proposed/` holds items that have been argued for but not
  committed to. **Nobody works on anything here.**
- `pledged/` holds items the project has committed to deliver, but
  hasn't yet.

Neither directory is named after the act of approving something
(D44, decided by the owner on 2026-07-27). `pledged/` used to be
called `accepted/`, but that name was dropped: moving something into
either directory is an approval, so a name like "accepted" for one
directory would take a word the other directory needs too. Both
directory names now describe what the item *is*, not the act that
put it there: **proposed** means argued for but not binding;
**pledged** means the project owes it, with no delivery date
attached. Words like "approved" or "accepted" can be used to
describe either step — they just aren't used as directory names.

Both `proposed/` and `pledged/` contain files with the same three
names — `USE-CASES.md`, `ARCHITECTURE.md`, and `FEATURES.md` —
because each directory holds the same three kinds of content, just
at a different stage. That's the entire meaning of the two
directories: an item moves from the `proposed/` copy of a file to
the `pledged/` copy, and the git commit that makes that move is the
record that it happened.

Files directly in `planning/` (not inside `proposed/` or
`pledged/`) are the ones that never move. They aren't proposals
working through a lifecycle — they're the fixed machinery that runs
the process itself: a map, a rule, a record, a queue, and a ledger.

- [README.md](README.md) — this map.
- [SURFACES.md](SURFACES.md) — the rule for deciding whether a
  change to Reliquary's surfaces is acceptable. It applies just as
  much to `proposed/` as to `pledged/` — it's the test used to judge
  a proposal, not something that itself goes through the proposal
  process.
- [DECISIONS.md](DECISIONS.md) — the record of decisions. By design
  it covers every stage at once: open questions still being decided,
  decisions that committed the project to something, decisions that
  turned something down (this file is where a refusal is recorded —
  decision D52 removed the "Rejected" section from TASKS.md, since a
  queue should only hold work that's waiting, not work that was
  refused), and a list of retired items that don't bind the project
  to anything.
- [TASKS.md](TASKS.md) — the queue of pending work. Everything
  listed in it is already pledged — there's nothing left to promote,
  and no required order to do the work in. Each entry has a
  T-number, the same way every other item in this system gets a
  number (D86). Even though its entries are in the pledged state,
  TASKS.md doesn't live in the `pledged/` directory: that directory
  is for demand and capability — use cases, principles, and the
  features that satisfy them — and a task isn't any of those. It's a
  different kind of thing, not just a smaller one.
- [RECURRING.md](RECURRING.md) — the list of recurring obligations —
  things that have to be checked periodically because the automated
  test suite can't check them on every commit, like auditing the
  writing style or checking whether dependencies are out of date.
  Each one has an R-number, a limit on how long it can go unchecked,
  and a record of when it was last checked. An obligation like this
  is never "done" — it's either current or overdue — which is why it
  lives here instead of in the task queue.
- [SEQUENCES.md](SEQUENCES.md) — the ledger that tracks the next
  number to hand out for every ID type used in this system (D, F, G,
  P, R, S, T, U, V). It's kept in one file on the `main` branch
  because a search only sees the branch you're on — a number given
  out on a branch that hasn't been merged yet wouldn't show up
  anywhere else (owner, 2026-07-31). When you take the next number,
  update the ledger in the same commit.

There's one exception to the "queue holds all tasks" rule: work that
only makes sense as part of a single pledged feature is listed with
that feature, inside `pledged/FEATURES.md`, instead of in the task
queue — because it has no meaning on its own. Only work that stands
on its own goes in the queue.

This project deliberately has no roadmap (D42). A roadmap organizes
work by *when* it will happen; everything here is organized by
*state* instead, and a roadmap would promise an order that nothing
here actually commits to. `pledged/` means the project will do the
work — it says nothing about when. That's why it's fine to have no
roadmap: pledging is a commitment without a date. The lack of
ordering in [TASKS.md](TASKS.md) applies to pledged features too —
the only ordering that's binding is the order of steps inside a
single feature. Because pledging is a real commitment, a pledge can
also be wrong: if the project no longer intends to deliver
something, it gets moved back to `proposed/` or rejected outright,
rather than left sitting in `pledged/` as a promise nobody means to
keep.

These files also don't keep a history log. Moving an item is the
action, and the git commit that does the move is the record of it —
so none of these standing files narrates its own past. There are no
notes about a section being emptied or filled; if a section is
empty, that's obvious just by looking, and git history already shows
when it became empty. Retired numbers get no explanation written
next to them (D23) — the gap in the numbering sequence is itself the
historical record. And entries aren't kept around after the work is
done or the item is struck — completed work is deleted, not
archived. When an entry explains its own background and reasoning,
that's not a history log, it's the actual argument for the item.
**[DECISIONS.md](DECISIONS.md) follows the same rule**: it's a working document, not
an archive, so an entry can be reworded to match current terminology
and current facts just as easily as a new entry is added, and an
entry that's no longer useful gets deleted. Git history already
preserves what each entry said at the time it was written — keeping
that in the file too would make the file too large to search, at
which point it stops being useful as a guard against re-arguing
settled questions. What an entry does keep is anything with no other
home: a call that was contested, the alternative that was rejected,
and the condition under which the decision could be reopened.

Features get F-numbers, and each feature has to be small enough to
fit in one sprint (D42). The number is a handle other things can
reference when they depend on this feature; it's issued from one
sequence shared by both `proposed/` and `pledged/`, and it only
records the order numbers were issued in, never priority. Once a
feature is delivered, its number is retired for good and never
reused, so a gap in the numbering is just history, not a sign that
something's still coming. Tasks get T-numbers on the same terms
(D86): a task's number is issued the moment it's entered (since a
task has no proposed stage in `planning/`), and the number retires
when the task is struck off the list. Every one of these numbering
sequences pulls its next number from the ledger in
[SEQUENCES.md](SEQUENCES.md), which records the highest number
issued so far. Designs don't get a
number at all — a design belongs to one feature and is identified by
its file path instead. A sprint here means minutes to hours, not
days or weeks. The size limit applies at the point a feature is
pledged: an entry in `proposed/FEATURES.md` can be much bigger than
one sprint, and cutting it down to sprint-sized pieces is part of
the work of pledging it.

When one item depends on another, the dependent item names the
other item's number — the reference is written on the item that
needs something, pointing at the thing it needs. This isn't a
schedule for what gets built first. A reference should only point to
something at the same stage or an earlier one, never a later one: if
a pledged item can't be finished without something that's still only
proposed, that's a problem to fix, not something to just note as a
dependency.

The files that describe what's actually true right now live at the
repository root, not under `planning/`, because they're claims about
the code as it exists today: [USE-CASES.md](../USE-CASES.md) lists
use cases the code actually satisfies, and
[ARCHITECTURE.md](../ARCHITECTURE.md) gives the whole-system view
plus the P-numbered architectural principles the code actually
honors. Together with the specs in [docs/spec/](../docs/spec/),
these describe what Reliquary is and what it's for right now.
Anything under `planning/proposed/` or `planning/pledged/` describes
a future the project hasn't reached yet.

USE-CASES.md and ARCHITECTURE.md exist under both `proposed/` and
`pledged/`, because a use case or a principle actually passes
through three states, not two: drafted, then pledged, then in force.
Pledging something and actually delivering it are two separate
events, and the gap between them matters — the root-level files are
claims about what's actually built, so pledging a use case doesn't
put it there; only delivering it does. Three locations map to the
three states, and which file an entry sits in tells you which state
it's in. This is also what makes a principle binding: while it sits
below the root list, it's pledged but not yet real, and any gap is
just unfinished work. Once it's in the root list, the project is
claiming the code actually follows it, and any gap becomes a bug
instead — that's the "gap is a bug" rule, stated in that document's
own banner (D48). Promotion works differently for the two kinds of
item: a use case is promoted once it's *fully* delivered; a
principle is promoted once the code actually follows it as a rule,
with every known exception filed as a bug in the same change that
promotes it.

A design document for a feature lives next to that feature, in
`proposed/design/` or `pledged/design/`, so the design moves along
with the feature it's designing. If the feature it belongs to is
dropped, its design gets deleted along with it. The
`planning/design/` directory (not inside `proposed/` or `pledged/`)
holds only design problems that don't belong to any single feature.
The whole-system architecture view itself lives in root
[ARCHITECTURE.md](../ARCHITECTURE.md).

Nothing under `planning/` describes a surface that has already
shipped. Once an application surface is released, its official spec
lives in [`docs/spec/`](../docs/spec/) — that's where anyone looking
for what Reliquary actually does should look. That move only happens
in one direction: a spec never moves back into `planning/`.
Machine-readable schemas go even further — they ship as part of the
package itself, at `src/reliquary/schemas/`, because code reads them
directly, and `docs/spec/` just points to them.

## The map

| Location | Holds |
|---|---|
| [`proposed/USE-CASES.md`](proposed/USE-CASES.md) | Draft use cases, numbered from the same U-sequence used by the root list |
| [`proposed/ARCHITECTURE.md`](proposed/ARCHITECTURE.md) | Proposed architecture: draft principles (numbered from the shared P-sequence) and proposed model changes, argued before they can be pledged |
| [`proposed/FEATURES.md`](proposed/FEATURES.md) | Large capabilities not yet built (F-numbered). Each is many sprints of work with the design already settled, waiting for the use case that schedules it. They only get cut down to sprint-sized pieces when pledged |
| [`pledged/USE-CASES.md`](pledged/USE-CASES.md) | Use cases the project has committed to but the code doesn't satisfy yet |
| [`pledged/ARCHITECTURE.md`](pledged/ARCHITECTURE.md) | Architecture principles the project has committed to but the code doesn't follow yet |
| [`pledged/FEATURES.md`](pledged/FEATURES.md) | Capabilities the project has committed to build (F-numbered), each sized to fit one sprint, listed with the work items needed to deliver them |
| [`SURFACES.md`](SURFACES.md) | *(root)* The rule every surface-changing decision must follow. It covers the surfaces listed in root ARCHITECTURE.md, "The application surfaces" (S1–S8) |
| [`DECISIONS.md`](DECISIONS.md) | *(root)* Open questions, the record of decisions made (D-numbers), and a list of retired items — all stages, on purpose |
| [`TASKS.md`](TASKS.md) | *(root)* The third work queue: small work that's already pledged, T-numbered, with no particular order |
| [`RECURRING.md`](RECURRING.md) | *(root)* The list of recurring obligations (R-numbered) — things like writing-style audits and dependency checks — each with a time limit and a record of when it was last done |
| [`SEQUENCES.md`](SEQUENCES.md) | *(root)* The ledger of the next number to issue for every numbering sequence (D, F, G, P, R, S, T, U, V) — one counter per type, updated in the same edit that uses a number |
| [`proposed/design/`](proposed/design/) | Design documents for proposed features: `device-growth.md` (F5), `hyperv-screen.md` (F5), `recorder.md` (F1, U6), `platform-dialect.md` (F64) |
| [`pledged/design/`](pledged/design/) | Design documents for pledged features — currently empty. When a feature is delivered, there's no feature left for its design to sit with, so the design moves out along with the delivery: to `docs/spec/` if the surface is user-facing (as happened for landmarks and pointer input), or to `design/` if it's internal |
| [`design/`](design/) | *(root)* Open design problems and internal documentation that don't belong to any single feature: `backend-adapter.md` (documents the adapter interface; delivered as F2, and kept internal by decision rather than moved to `docs/spec/`), `screen-transcripts.md` (documents the capture format and how it's reconstructed; delivered as F42 and F43, kept internal by D98), `guest-communication.md` (documents the control-plane design; this interface is internal, not user-facing), `authored-binary-assets.md` (where binary data supplied by a script author lives; this is landmarks' established approach, written down once because U25's fonts are the second use of it), `audits.md` (ideas for checking the project's own claims — suggestions only, nothing enforced), `dosbox-x.md` (explains why DOSBox-X isn't used as a backend, with the evidence and the condition that would reopen the question, which R12 watches for), and the script-language's remaining open problems in `script-examples/` |

Not included here, on purpose: the official specs for surfaces that
have already shipped ([`docs/spec/`](../docs/spec/)), and the
machine-readable schemas (`src/reliquary/schemas/`).

The worked FreeDOS example isn't here either: it's the shipped codex
(`src/reliquary/codex/`), which is the live, tested version, and
there's no need for a second copy.

## How an idea enters

An idea can enter this project through three queues (D43, which
expanded on D39's original two):

1. **GitHub issues** — the raw, unfiltered intake, often from people
   outside the project: a bug report, a question, a wish.
2. **The `proposed/` directory** — the same idea, written up in the
   project's own terms, as a draft use case, principle, or feature.
   Nobody works on it until it's pledged.
3. **[TASKS.md](TASKS.md)** — small work that's pre-approved. Putting
   something in this file *is* approving it, so it needs no citation
   and no separate decision, and there's no required order to work
   through it.

Writing into `planning/` requires approval (owner, 2026-07-26). The
issue tracker is the only open door — anyone can file an issue
there, and filing one doesn't grant anything by itself. Everything
else in `planning/` is the project speaking in its own official
voice, so the same approval gate covers all three actions: adding a
document to `proposed/`, promoting it to `pledged/`, and adding work
to [TASKS.md](TASKS.md). What each action grants is different — a
live argument gets started, a pledge gets made, or work gets
approved — but the same gate controls all three. "Authority" here is
a role, not a specific person. Right now the owner is the only one
who holds it, but he can widen that group whenever he wants.

The gate matters most for the third action. Adding something to
`proposed/` just starts an argument and commits to nothing; promoting
it to `pledged/` is the conclusion of that argument, with the
reasoning written down. But adding a task to TASKS.md *is* the
entire review — there's no argument behind it. For a task, having
someone with authority make the call is the only thing separating
"pre-approved" from "anyone approves their own work." The gate only
applies when something is being added — once an item is already in
the queue, anyone can pick it up and work on it.

A task has no "proposed" stage inside `planning/`. Both use
cases/principles and tasks go through the same lifecycle, just in
different places: use cases and principles are proposed in
`proposed/` and pledged in `pledged/`, while a task is proposed in
the issue tracker and pledged directly in [TASKS.md](TASKS.md) —
there's no in-between arguing stage, because a task is too small to
need one. So the issue tracker is the only place a task can be
"proposed," and that means an outside contributor doesn't need write
access to this repository to propose one — they can make their case
in a public issue, and someone with authority copies it into
`proposed/` if it's a use case or principle (that copying is the
governed step). The issue tracker accepts everything, and each issue
eventually exits one of a few ways: written up as a proposal,
entered as a task, fixed directly with a pull request if it's a
clear bug or housekeeping item, or rejected with the reason recorded
here.

Every piece of work has to start in one of these queues — the only
exception is a small, direct commit approved under the housekeeping
rule (below).

The three queues aren't equal alternatives — GitHub issues feed into
the other two. Raw issues get sorted into a draft proposal, a task,
a direct fix under housekeeping, or a rejection recorded in
[DECISIONS.md](DECISIONS.md). What keeps the task queue from being a
way to skip review is the gate at its entry: only someone with
authority can add something to it, and adding it *is* approving it
(D43). This is a different check from housekeeping's surface-change
test (see SURFACES.md) — that test exists specifically for
housekeeping (D45), to make up for the fact that nobody with
authority reviews housekeeping items. A queue that only the owner
can write to doesn't need that same compensating check. So a task
*can* be a small change to an application surface — it's admitted
based on its size and kind, never turned away just because of which
surface it touches. What it can't do is skip the rules for how a
surface change has to land — those rules apply to a task exactly as
they apply to a feature. Put together, the underlying guarantee
still holds: no surface change happens without going through one of
the queues, because going through the task queue means someone with
authority approved it, not that the change is automatically safe.

**Housekeeping** (D38) is one step smaller than the task queue:
small cleanups and small, obviously-real bugs — tiny in scope *and*
clearly a problem — are approved as a category, in advance, and are
too small to be worth writing down anywhere at all. Anything that
qualifies is approved just by looking at it and doesn't need an
entry in any file. Whoever does the work just says "housekeeping" in
the commit message, and that commit is the entire record.

Turning things away is just as much a part of these rules as
accepting them. Housekeeping's first check is whether the change
touches an application surface — that's a simple lookup, not a
judgment call: root ARCHITECTURE.md, "The application surfaces,"
lists them as S1–S8, and [SURFACES.md](SURFACES.md) is the rule that
applies once a change hits one of them. That check applies only to
housekeeping; the task queue's check is simply whether someone with
authority added the item (see above). A use-case amendment, a
principle amendment, or a design decision can never qualify as
housekeeping or as a task. Beyond that, when in doubt, leave it out:
if something needs to be argued for before it can be added, it
doesn't belong in either of these two lighter-weight paths. (A bug
that violates an existing, already-adopted principle is neither a
housekeeping item nor something needing approval — the principle
already demands the fix, so nothing needs approving, just fixing.)

## How an idea is pledged

Moving something *is* the act of pledging it. When a document, or an
entry within one, moves from `proposed/` to `pledged/`, or moves
straight to the root list, that move is the pledge, and the commit
that makes the move is the record of it. There's no separate log to
keep in sync — being cited somewhere else doesn't make something
pledged.

Every pledged item names what makes it necessary: a use case (by its
U-number, whether it's already in force at the root level or still a
draft in `proposed/`) or an architectural principle (by its
P-number) — either one can be the reason work is needed. When a
proposal is dropped, the removal rule in [SURFACES.md](SURFACES.md)
is what finds and removes every item that depended on it.
