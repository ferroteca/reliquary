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
complete it. **No feature has any today**, the shelf being empty
again: both halves of `--dry-run` delivered on the day they were
pledged (D79–D81), and a delivered feature's work items leave with
its number. A task here that merely *relates* to a feature is still
free to be picked whenever.

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

**The next number to issue is T11.** Tasks are the one handle class
whose whole population can vanish: the queue empties, and a struck
task's only record is its commit, so nothing else here would say
what the highest number ever issued was. An F-number is covered
incidentally — every retirement is named in a
[DECISIONS.md](DECISIONS.md) entry — and D52 denies a task that
same cover on purpose, which is why this sequence has to state its
own high-water mark. **This line is not a status column** (D42): it
records what the sequence has spent, and says nothing about what
was done, by whom, or when.

It started at **T8** rather than T1 because T0–T7 were issued
already, by an earlier per-list numbering that ran three separate
times, and those mentions survive in
[DECISIONS.md](DECISIONS.md) under the entries that landed them.
Beginning above them is what keeps every T-number in the record
resolving to exactly one thing — the property the never-reissue
rule exists to buy, which starting at T1 would have spent on the
first entry.

## Pledged

Grouped by kind, because the actor and the gate differ: an audit
is mechanical, a defect needs no pledge because the norm it
violates already is one. A group with nothing in it is not listed:
an empty heading is a record of retired work, which this file does
not keep.

### Mechanical

- **T10 — Move to the src layout, and rename the suite to `tests`.**
  `reliquary/` becomes `src/reliquary/` and `reliquary_tests/`
  becomes `tests/`, which is the layout a Python developer expects
  and neither of which the project can adopt for free until now.

  **D96 is what unblocks the rename.** `reliquary_tests` was named
  that for collision safety: it shipped in the sdist as an
  importable top-level package, and a package called `tests` in
  `site-packages` collides with every other project that did the
  same. Now that released artifacts carry no suite it is installed
  nowhere and cannot collide, so the prefix guards nothing.

  **The src layout buys something structural, not cosmetic.** Flat,
  a suite run from the repository root imports the local
  `reliquary/` directory — grammar and schemas sitting right
  beside it — so a missing `[tool.setuptools.package-data]` entry
  is invisible to every test. Under `src/` that import cannot
  happen: the package must be installed to be imported, and a
  package-data omission fails immediately. That is the exact
  failure class `tools/check_dist.py` was written to catch, so
  this replaces a bespoke guard with a structural one rather than
  duplicating it. Keep `check_dist.py`: it also asserts what the
  artifacts must *not* carry, which no layout enforces.

  Mechanical, and measured: 40 test modules under 458 files, and
  `reliquary_tests` appears 56 times across 29 files. `git mv`,
  rewrite `reliquary_tests.*` imports to `tests.*`, then:

  - `[tool.setuptools.packages.find]` gains `where = ["src"]`, and
    its `exclude = ["reliquary_tests*"]` **becomes dead and should
    go** — with only `src/` scanned a top-level `tests/` cannot be
    found at all. That exclude is commented in place as "required,
    not decorative"; the layout is what makes it genuinely
    unnecessary, which is the change proving itself.
  - `MANIFEST.in` include paths gain the `src/` prefix.
  - `tools/check_dist.py`: `SDIST_FORBIDDEN_TREES` renames
    `reliquary_tests/` to `tests/`. Wheel paths are unaffected —
    they are package-relative and the package name does not change.
  - AGENTS.md, CONTRIBUTING.md and the required-checks commands,
    where `-m unittest reliquary_tests` becomes `-m unittest tests`.

  **One thing to verify rather than assume**: at least one test
  walks up from its own `__file__` to read `docs/spec/` (the
  device/materialize spec-table inventories). `reliquary_tests/` and
  `tests/` sit at the same depth so it should survive untouched,
  but a layout change that silently repoints a spec reader is
  exactly the kind of thing that passes locally and rots.

### Surface decisions

- **T8 — Resolve description visibility in the list family.** The
  `list-*` verbs print no `description` for any item, while
  `--json` carries it in full, so a person cannot read what a
  blueprint, script or media *is* from the CLI at all while the
  data sits one flag away. The omission was deliberate (D88):
  descriptions are unbounded free text and a column of them
  dominates a fixed-width table. The deferral ends in one of two
  places rather than standing indefinitely.

  - **Support it in the CLI**, which means specifying the human
    display rather than adding a column and hoping: truncation
    width, wrapping, or a per-item detail view
    (`show-blueprint <name>`-shaped) instead of a column at all —
    and whether the answer is uniform across the family or per
    noun.
  - **Drop it entirely**, `--json` included, so no surface carries
    a field none of them shows.

  Context: `search-blueprints` was the only human-visible
  description surface and went with the search family (D88), and
  U11's "read a description" is met only through `--json` until
  this settles — the thin fulfilment that prompted the entry.
