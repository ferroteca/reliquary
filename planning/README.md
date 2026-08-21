<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# planning

Maintainer-facing planning. The directories are the classification;
file names carry no suffix, and a document's location tells you its
standing without reading a word of it.

## The one vocabulary

**A use case, a principle and a task carry the same lifecycle**
(owner, 2026-07-24): each is *proposed*, *pledged*, *completed*, or
*rejected*. One vocabulary runs through the whole planning
machinery — the same four words classify demand, rules and work
alike — and the directories below are that vocabulary made
physical.

- `proposed/` — argued but not pledged. **Nothing is worked from
  here.**
- `pledged/` — owed by the project, and not yet delivered.

**Neither shelf is named after an act** (D44, owner, 2026-07-27),
and the second one used to be: it was `accepted/` until the
approval words gave out. Both gates need one — admitting a document
to `proposed/` is an approval too, and "agreed", "approved" and
"accepted" are what come to mind at either — so a shelf named for
an act claims words the other gate still has to borrow. Both names
now state what the item *is*: **proposed**, argued and binding
nothing; **pledged**, owed by the project with no date attached.
Approval words belong to the gates, and either gate may use any of
them.

**The two directories hold the same three filenames** —
`USE-CASES.md`, `ARCHITECTURE.md`, `FEATURES.md` — because they hold
the same three artifacts in two different states. That is the whole
of what the directories mean: a thing in `proposed/` moves to
`pledged/`, and the commit that moves it is the record.

**The planning root holds what does not move.** The map, the rule,
the record, the queue, and the ledger are machinery rather than
proposals, and none of them has a lifecycle state to be in:

- [README.md](README.md) — this map.
- [SURFACES.md](SURFACES.md) — the vetting rule. It governs
  `proposed/` at least as much as `pledged/`; it is the test a
  proposal is judged by, not a thing that was proposed.
- [DECISIONS.md](DECISIONS.md) — the adjudication record, which cuts
  across every state by design: open questions not yet adjudicated,
  decisions that pledged something, decisions that **refused** it
  (this file is the whole record of a refusal — D52 deleted
  TASKS.md's Rejected section, a queue holding only what waits), and
  a retired list binding nothing at all.
- [TASKS.md](TASKS.md) — the queue, and **everything in it is
  already pledged**, so there is nothing to promote and no order to
  work it in. Its entries are itemized, T-numbered like every other
  item here (D86). Its state is the one `pledged/` names; the directory
  is not its home because `proposed/` and `pledged/` hold *demand
  and capability* — use cases, principles, and the features that
  deliver them — and a task is none of those. That kind distinction
  is the distinguisher, not size alone.
- [RECURRING.md](RECURRING.md) — the recurring register: standing
  obligations the every-commit suite cannot discharge — prose-norm
  audits, dependency freshness — each R-numbered, carrying its own
  staleness bound and the mark of its last run. An obligation is
  never done, only current or overdue, which is why it lives here
  rather than in the queue.
- [SEQUENCES.md](SEQUENCES.md) — the sequence ledger: the next
  number to issue for **every** handle class (D, F, G, P, R, S, T,
  U, V), stated in one file on `main` because a search sees only
  the branch it stands on and a number issued on an unmerged branch
  is visible from nowhere else (owner, 2026-07-31). Issue from it
  and advance the mark in the same edit.

One exception cuts the other way: work that only makes sense as part
of one pledged feature lives **with that feature**, under
`pledged/FEATURES.md`, because it is meaningless apart from it.
Only free-standing work goes in the queue.

**There is no roadmap, deliberately** (D42). A roadmap classifies by
*when* where everything here classifies by *state*, and promises an
order nothing commits to. `pledged/` says the project will do it and
says nothing whatever about when — a commitment without a date,
which is why it coexists with keeping no roadmap; the absence of
order in [TASKS.md](TASKS.md) holds equally for pledged features,
the only binding order running inside a feature. The commitment is
what lets the shelf be **wrong**: an item nobody intends to deliver
is withdrawn to `proposed/` or rejected outright, never left sitting
as a pledge nobody means.

**These documents keep no diary either.** The move is the act and
the commit is its record, so a standing document never narrates
its own history: no chronicle of shelf fills and empties; no
"empty today" notes — emptiness is self-evident, and git history
records when; no death records behind retired numbers (no stub,
D23 — the gap in a sequence is the history); and no entry kept
after being applied or struck — done work leaves by deletion. A
live entry's own provenance and argument are not diary; they are
the argument. **[DECISIONS.md](DECISIONS.md) is no exception**: it
is a working file rather than an archive, so an entry is rewritten
in current spellings against the current surface as readily as it
is added, and one that no longer carries value today is struck. Git
history holds what each said when it was written — a record too
large to search stops being a guard against anything. What an entry
keeps is the part with no normative home: a contested call, its
rejected alternative, and the condition that would reopen it.

**Features carry F-numbers and a size bound** (D42). The number is a
handle for what depends on a feature, running in one sequence across
both directories, recording order of issue and never priority; it
**evaporates on delivery** and is never reused, so gaps are history
rather than a promise. **Tasks carry T-numbers on the same terms**
(D86) — issued at entry, since a task has no proposed state here,
and evaporating when the task is struck; every handle sequence
issues against the ledger ([SEQUENCES.md](SEQUENCES.md)), which
states the high-water marks. Designs take no number — a design
serves one feature and is identified by its path. A feature must fit in one
sprint, which here runs in minutes to hours; the bound bites at
the pledge, so entries in `proposed/FEATURES.md` are each many
sprints and cutting one up is part of pledging it.

References between items are written in the dependent item and point
at the prerequisite's handle. They are **not a delivery order**, and
they run down the lifecycle or sideways, never up: a pledged item
that cannot be completed without something still only proposed is a
flaw to fix rather than a reference to record.

The in-force artifacts live at the **repository root**, not here,
because they are claims about the code as it exists today:
[USE-CASES.md](../USE-CASES.md) (every entry met by the code) and
[ARCHITECTURE.md](../ARCHITECTURE.md) — the whole-system view plus
the P-numbered architectural principles, every principle honored
by the code. Together with the specifications
([docs/spec/](../docs/spec/)) they are the project's **vision**:
the standing statement of what Reliquary is and is for. What sits
under `proposed/` and `pledged/` here is vision that has not
arrived yet.

Each is mirrored by name in **both** directories, because use cases
and principles have **three** states, not two: drafted → pledged →
in force. Pledging and delivery are different events, and the gap
between them is real — the root lists are implementation claims, so
pledging a use case can never put it there. Three locations, three
states, and the file an entry sits in says which it is. This is also
what arms a principle: below the root list it is pledged vision and
a shortfall is unbuilt work; at the root list the project asserts
the code honors it, and a divergence becomes a bug — the
gap-is-a-bug rule, whose home is that document's own banner (D48).
Promotion runs on **two bars**, not one: a use case moves on *full*
delivery, a principle on being *honored as a rule* with every known
residue filed as a defect in the same change.

**Design sits with what it serves.** A design for one feature lives
beside that feature — `proposed/design/` or `pledged/design/` — so
the design and the demand it answers move together, and a design for
a proposal that dies is swept with it. `design/` at this level holds
only open design problems belonging to no single feature; the
whole-system view itself is root
[ARCHITECTURE.md](../ARCHITECTURE.md).

**Nothing under `planning/` describes a delivered surface.** Once
an application surface ships, its normative spec is current truth and lives in
[`docs/spec/`](../docs/spec/), which is where the world looks for
what Reliquary *is*. That is a one-way move: a spec never comes
back here. Machine-readable schemas go further still — they ship
inside the package at `src/reliquary/schemas/`, because code consumes
them, and `docs/spec/` refers to them.

## The map

| Location | Holds |
|---|---|
| [`proposed/USE-CASES.md`](proposed/USE-CASES.md) | Drafted use cases, numbering from the same global U-sequence as the root list |
| [`proposed/ARCHITECTURE.md`](proposed/ARCHITECTURE.md) | Proposed architecture: drafted principles under the global P-numbering, and model changes argued before pledging |
| [`proposed/FEATURES.md`](proposed/FEATURES.md) | Large unbuilt capabilities (F-numbered) — each many sprints of work, design settled and intact, awaiting the use case that schedules it; cut to sprint size only on pledging |
| [`pledged/USE-CASES.md`](pledged/USE-CASES.md) | Pledged use cases the code does not yet meet |
| [`pledged/ARCHITECTURE.md`](pledged/ARCHITECTURE.md) | Pledged architecture the code does not yet honor — pledged vision, not yet armed |
| [`pledged/FEATURES.md`](pledged/FEATURES.md) | Pledged-but-unbuilt capability (F-numbered), each within one sprint and carrying the work items that deliver it |
| [`SURFACES.md`](SURFACES.md) | *(root)* The surface-change rule every surface-changing decision follows; the inventory it scopes over is root ARCHITECTURE.md "The application surfaces" (S1–S8) |
| [`DECISIONS.md`](DECISIONS.md) | *(root)* Open questions, the adjudicated decision record (D-numbers), and the retired list — every state, by design |
| [`TASKS.md`](TASKS.md) | *(root)* The third input queue: small work, already pledged, T-numbered, in no particular order |
| [`RECURRING.md`](RECURRING.md) | *(root)* The recurring register: R-numbered standing obligations — prose-norm audits, dependency freshness — each with its own staleness bound and last-performed mark |
| [`SEQUENCES.md`](SEQUENCES.md) | *(root)* The sequence ledger: the high-water marks every handle sequence (D, F, G, P, R, S, T, U, V) issues against — one counter per class, advanced in the issuing entry's own edit |
| [`proposed/design/`](proposed/design/) | Design for proposed features — `landmarks.md` (F5), `recorder.md` (F1, U6) |
| [`pledged/design/`](pledged/design/) | Design for pledged features; a delivered feature leaves no feature for its design to sit with, so its design travels out with the delivery |
| [`design/`](design/) | *(root)* Open design problems and internal doctrine belonging to no single feature — `backend-adapter.md` (the adapter seam's doctrine, delivered as F2 and internal by decision, so it does not move to `docs/spec/`), `screen-transcripts.md` (the capture format and its reconstruction, delivered as F42 and F43 and internal by D98, arriving here by exactly that route), `guest-communication.md` (the control-plane doctrine; the seam is internal, not world-facing), `authored-binary-assets.md` (where binary data an author supplies to a script lives — landmarks' settled shape, stated once because U25's fonts are its second instance), `audits.md` (suggestions for checking the project's own claims — ideas only, nothing enforced), and the script-language residual problems in `script-examples/` |

Not here, deliberately: the normative specs of shipped surfaces
([`docs/spec/`](../docs/spec/)) and the machine-readable schemas
(`src/reliquary/schemas/`).

The worked FreeDOS example is not here: it is the shipped codex
(`src/reliquary/codex/`), which is the live, tested copy and needs no
second one.

## How an idea enters

**An idea enters this project through three work queues** (D43,
widening D39's two):

1. **GitHub issues** — the raw, unfiltered intake, often from
   outside: a bug hit, a question asked, a wish stated.
2. **The `proposed/` directory** — the same idea argued in the
   project's own vocabulary, as a drafted use case, principle or
   feature. Nothing is worked from here until it is pledged.
3. **[TASKS.md](TASKS.md)** — small, **pre-approved** work. Entering
   it is approving it, so it needs no citation and no decision, and
   there is no order to work it in.

**Writing into `planning/` is a governed act** (owner, 2026-07-26).
The issue tracker is the one open door: anyone may file there, and
entry grants nothing. Everything in this directory is the project
speaking in its own voice, so the **same gate governs all three
acts** — entering a document in `proposed/`, promoting it to
`pledged/`, and entering work in [TASKS.md](TASKS.md). Only what
each act grants differs: a live argument, a pledge, an
approval. Authority is a role rather than a person; today it is the
owner alone, and the group may be widened whenever he chooses.

The gate weighs most on the third act: a `proposed/` entry admits an
argument and commits nothing, and a promotion is that argument's
conclusion with its reasoning recorded, but a task entry *is* the
whole vetting with nothing behind it. There, authority is all that
stands between pre-approval and self-approval. The gate sits at
entry only; anyone may pick up what is already there.

**A task has no proposed state under `planning/`.** Both lanes run
the same lifecycle, housed differently: demand and capability are
proposed in `proposed/` and pledged in `pledged/`, while a task is
proposed in the **issue tracker** and pledged in
[TASKS.md](TASKS.md) — there being no argued middle stage for work
too small to need the argument. So the tracker is the only queue a
proposed task has, and an outside contributor needs no write access
here to propose: they argue in the open, and transcription into
`proposed/` is the governed act. The tracker takes everything, and
an issue leaves by whichever exit fits — drafted as a proposal,
entered as a task, fixed as a PR outright where it is a clear bug or
housekeeping, or rejected with its reason recorded here.

Nothing flows without starting in one of them, and the only
exception is a small raw commit approved under housekeeping.

The queues are not peers; issues are upstream of both others. Raw
intake is triaged into a drafted proposal, entered as a task, fixed
directly as housekeeping, or rejected with its reason recorded in
[DECISIONS.md](DECISIONS.md). What keeps the third queue from being
a hole in the vetting is **the gate at its door**: only authority
writes to it, and entering an item *is* approving it (D43). It is
**not** housekeeping's surface test — that boundary is
housekeeping's alone (D45), compensating for a class nobody with
authority ever reviews, and a queue only the owner can write to
needs no such compensation. So **a small surface change may be a
task**, admitted on size and kind and never refused for the surface
it touches; what it may not do is skip the landing rules, which
bind it exactly as they bind a feature. Composed that way the
guarantee still holds — **no surface change without having passed
through a queue** — because passing through this one means an
approval was given, not that the subject was safe.

**Housekeeping** (D38) is the same instinct one size below the third
queue: small cleanups and small reported defects — tiny in scope
*and* crystal clear they are a problem — are approved as a class, in
advance, and are too small to be worth writing down at all. A
qualifying item is approved on sight and needs no entry anywhere;
whoever lands the work invokes the bucket by naming it in the
commit, and the commit is the record.

Refusing is half of both rules. Housekeeping's surface test is
its first gate and it is a lookup, not a judgement — root
ARCHITECTURE.md "The application surfaces" enumerates them as
S1–S8, and the rule that
weighs a hit is [SURFACES.md](SURFACES.md). It governs that
bucket only; the third queue's gate is authority at entry (above).
A use-case or principle amendment and a design
decision are never admissible to either bucket. Past that,
doubt escalates: if it has to be argued in, it does not belong in.
(A defect against a *standing* principle is neither — the principle
is already its own demand, so it needs no approval, only fixing.)

## How an idea is pledged

**The move is the act.** Promoting a document — or an entry within
one — from `proposed/` to `pledged/`, or from `proposed/` to the
root standing list, *is* the pledge, and the commit that does it
is the record. There is no separate register to keep in step, and
nothing is pledged by being cited somewhere.

Every pledged item cites what demands it: a use case (its U-number,
in force at the root or still drafted under `proposed/`) or a
architectural principle (its P-number), which drives work just as well.
When a proposal dies, the sweep — the removal rule in
[SURFACES.md](SURFACES.md) — finds every item that
falls out with it.
