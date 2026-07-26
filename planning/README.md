<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# planning

Maintainer-facing planning. The directories are the classification;
file names carry no suffix, and a document's location tells you its
standing without reading a word of it.

## The one vocabulary

**A use case, a principle and a task carry the same lifecycle**
(owner, 2026-07-24): each is *proposed*, *accepted*, *completed*, or
*rejected*. One vocabulary runs through the whole planning
machinery — the same four words classify demand, rules and work
alike — and the directories below are that vocabulary made
physical.

- `proposed/` — argued but not accepted. **Nothing is worked from
  here.**
- `accepted/` — approved, and not yet delivered.

**The two directories hold the same three filenames** —
`USE-CASES.md`, `ARCHITECTURE.md`, `FEATURES.md` — because they hold
the same three artifacts in two different states. That is the whole
of what the directories mean: a thing in `proposed/` moves to
`accepted/`, and the commit that moves it is the record.

**The planning root holds what does not move.** The map, the rule,
the record, and the queue are machinery rather than proposals, and
none of them has a lifecycle state to be in:

- [README.md](README.md) — this map.
- [INTERFACES.md](INTERFACES.md) — the vetting rule. It governs
  `proposed/` at least as much as `accepted/`; it is the test a
  proposal is judged by, not a thing that was proposed.
- [DECISIONS.md](DECISIONS.md) — the adjudication record, which cuts
  across every state by design: open questions not yet adjudicated,
  decisions that accepted something, decisions that **refused** it
  (TASKS.md's Rejected section is a thin index into this file), and
  a retired list binding nothing at all.
- [TASKS.md](TASKS.md) — the queue. Work entered there is small and
  **pre-approved**, so there is nothing to promote and no order to
  work it in.

One exception cuts the other way: work that only makes sense as part
of one accepted feature lives **with that feature**, under
`accepted/FEATURES.md`, because it is meaningless apart from it.
Only free-standing work goes in the queue.

The in-force artifacts live at the **repository root**, not here,
because they are claims about the code as it exists today:
[USE-CASES.md](../USE-CASES.md) (every entry met by the code) and
[ARCHITECTURE.md](../ARCHITECTURE.md) — the whole-system view plus
the P-numbered architectural principles, every principle honored
by the code. Together with the specifications
([docs/spec/](../docs/spec/)) they are the project's **vision**:
the standing statement of what Reliquary is and is for. What sits
under `proposed/` and `accepted/` here is vision that has not
arrived yet.

Each is mirrored by name in **both** directories, because use cases
and principles have **three** states, not two: drafted → accepted →
in force. Acceptance and delivery are different events, and the gap
between them is real — the root lists are implementation claims, so
accepting a use case can never put it there. Three locations, three
states, and the file an entry sits in says which it is. This is also
what arms a principle: below the root list it is accepted vision and
a shortfall is unbuilt work; at the root list the project asserts
the code honors it, and a divergence becomes a bug.

**Design sits with what it serves.** A design for one feature lives
beside that feature — `proposed/design/` or `accepted/design/` — so
the design and the demand it answers move together, and a design for
a proposal that dies is swept with it. `design/` at this level holds
only open design problems belonging to no single feature; the
whole-system view itself is root
[ARCHITECTURE.md](../ARCHITECTURE.md).

**Nothing under `planning/` describes a delivered interface.** Once
an interface ships, its normative spec is current truth and lives in
[`docs/spec/`](../docs/spec/), which is where the world looks for
what Reliquary *is*. That is a one-way move: a spec never comes
back here. Machine-readable schemas go further still — they ship
inside the package at `reliquary/schemas/`, because code consumes
them, and `docs/spec/` refers to them.

## The map

| Location | Holds |
|---|---|
| [`proposed/USE-CASES.md`](proposed/USE-CASES.md) | Drafted use cases, numbering from the same global U-sequence as the root list |
| [`proposed/ARCHITECTURE.md`](proposed/ARCHITECTURE.md) | Proposed architecture: drafted principles under the global P-numbering, and model changes argued before acceptance |
| [`proposed/FEATURES.md`](proposed/FEATURES.md) | Large unbuilt capabilities — each a milestone's worth of work, design settled and intact, awaiting the use case that schedules it |
| [`accepted/USE-CASES.md`](accepted/USE-CASES.md) | Accepted use cases the code does not yet meet |
| [`accepted/ARCHITECTURE.md`](accepted/ARCHITECTURE.md) | Accepted architecture the code does not yet honor — accepted vision, not yet armed |
| [`accepted/FEATURES.md`](accepted/FEATURES.md) | Accepted-but-unbuilt capability, each carrying the work items that deliver it |
| [`INTERFACES.md`](INTERFACES.md) | *(root)* The interface-change rule every interface-changing decision follows; the inventory it scopes over is root ARCHITECTURE.md "The interfaces" |
| [`DECISIONS.md`](DECISIONS.md) | *(root)* Open questions, the adjudicated decision record (D-numbers), and the retired list — every state, by design |
| [`TASKS.md`](TASKS.md) | *(root)* The third input queue: small, pre-approved work, in no particular order |
| [`proposed/design/`](proposed/design/) | Design for proposed features — `backend-adapter.md`, `landmarks.md` |
| [`accepted/design/`](accepted/design/) | Design for accepted features — `recorder.md` (U6) |
| [`design/`](design/) | *(root)* Open design problems and internal doctrine belonging to no single feature — `guest-communication.md` (the control-plane doctrine; the seam is internal, not world-facing) and the script-language residual problems in `script-examples/` |

Not here, deliberately: the normative specs of shipped interfaces
([`docs/spec/`](../docs/spec/)) and the machine-readable schemas
(`reliquary/schemas/`).

The worked FreeDOS example is not here: it is the shipped codex
(`reliquary/codex/`), which is the live, tested copy and needs no
second one.

## How an idea enters

**An idea enters this project through three work queues** (owner,
2026-07-26, widening D39's two — the widening wants a D-number of
its own):

1. **GitHub issues** — the raw, unfiltered intake, often from
   outside: a bug hit, a question asked, a wish stated.
2. **The `proposed/` directory** — the same idea argued in the
   project's own vocabulary, as a drafted use case, principle or
   feature. Nothing is worked from here until it is accepted.
3. **[TASKS.md](TASKS.md)** — small, **pre-approved** work. Entering
   it is approving it, so it needs no citation and no decision, and
   there is no order to work it in.

Nothing flows without starting in one of them, and the only
exception is a small raw commit approved under housekeeping.

The queues are not peers; issues are upstream of both others. Raw
intake is triaged into a drafted proposal, entered as a task, fixed
directly as housekeeping, or rejected with its reason recorded in
[DECISIONS.md](DECISIONS.md). What keeps the third queue
from being a hole in the vetting is the same test housekeeping
uses: **does it change an interface?** A yes is never small work,
however small the diff, and takes the argued route. Composed that
way, the guarantee still holds — **no interface changes without
having passed through a queue.**

**Housekeeping** (D38) is the same instinct one size below the third
queue: small cleanups and small reported defects — tiny in scope
*and* crystal clear they are a problem — are approved as a class, in
advance, and are too small to be worth writing down at all. A
qualifying item is accepted on sight and needs no entry anywhere;
whoever lands the work invokes the bucket by naming it in the
commit, and the commit is the record.

Refusing is half of both rules. The interface test above is the
first gate and it is a lookup, not a judgement — root
ARCHITECTURE.md "The interfaces" enumerates them, and the rule that
weighs a hit is [INTERFACES.md](INTERFACES.md). A use-case or principle amendment and a design
decision are likewise never admissible to either bucket. Past that,
doubt escalates: if it has to be argued in, it does not belong in.
(A defect against a *standing* principle is neither — the principle
is already its own demand, so it needs no approval, only fixing.)

## How an idea is accepted

**The move is the act.** Promoting a document — or an entry within
one — from `proposed/` to `accepted/`, or from `proposed/` to the
root standing list, *is* the acceptance, and the commit that does it
is the record. There is no separate register to keep in step, and
nothing is accepted by being cited somewhere.

Every accepted item cites what demands it: a use case (its U-number,
in force at the root or still drafted under `proposed/`) or a
architectural principle (its P-number), which drives work just as well.
When a proposal dies, the sweep — the removal rule in
[INTERFACES.md](INTERFACES.md) — finds every item that
falls out with it.
