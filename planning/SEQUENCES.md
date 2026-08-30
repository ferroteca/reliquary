<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# The sequence ledger

This file is one of the files in `planning/` that never moves (see
[README.md](README.md)). It tracks the next number to issue for
every numbered ID the project uses. When you take a number from
here, update the mark in the same commit, on the `main` branch.

**These lines are not a status log** (D42): each one just records
how many numbers a sequence has used so far. It doesn't say what
was done, who did it, or when. Once a number is issued, it's never
issued again — when a task is struck or a feature is delivered, its
number goes with it, and a gap in the numbering is just history,
not something still pending.

Why keep a ledger instead of just counting existing entries?
Because a search only sees the branch you're currently on. A struck
task's only remaining record is its commit (D52); a retired feature
only gets named in [DECISIONS.md](DECISIONS.md) once that round of
work is merged; and a number issued on a feature branch that hasn't
been merged yet is invisible everywhere else. So counting entries
would break as soon as feature branches are involved (owner,
2026-07-31). This also applies to the sequences that never lose
entries (owner, same day) — files that keep every entry forever,
and lists whose numbers never retire. Even for those, counting
entries only counts what's visible on the branch you're searching:
a decision or a use case drafted on an unmerged branch would mint a
number nothing on `main` can see. Using one ledger for every ID
type means you never have to work out case-by-case whether a given
type is safe to count instead.

If the mark here and the actual number of entries in a file
disagree, it means someone issued a number without updating this
ledger. In that case, move the mark up to match. The higher number
always wins, and no number is ever reissued.

## The marks

- **The next D-number to issue is D124** — used for decisions,
  recorded in [DECISIONS.md](DECISIONS.md).
- **The next F-number to issue is F73** — used for features,
  drafted in [proposed/FEATURES.md](proposed/FEATURES.md), or,
  when pledged straight away, entered directly into
  [pledged/FEATURES.md](pledged/FEATURES.md).
- **The next G-number to issue is G8** — used for the scripting
  language's design goals, listed in
  [docs/spec/script-spec.md](../docs/spec/script-spec.md).
- **The next P-number to issue is P28** — used for architectural
  principles. One shared numbering sequence covers proposed,
  pledged, and the root list.
- **The next R-number to issue is R13** — used for recurring
  obligations, listed in [RECURRING.md](RECURRING.md). An R-number
  retires when its obligation is retired.
- **The next S-number to issue is S9** — used for application
  surfaces, listed in root [ARCHITECTURE.md](../ARCHITECTURE.md)
  under "The application surfaces."
- **The next T-number to issue is T35** — used for tasks, entered
  into [TASKS.md](TASKS.md); entering a task is the same act as
  pledging it (D43). This sequence started counting from T8, not
  T0, because T0 through T7 were already used by an earlier
  numbering scheme that numbered three separate lists
  independently; those old numbers survive in
  [DECISIONS.md](DECISIONS.md), in the entries that adopted them.
  Starting the new sequence at T8 avoids any T-number meaning two
  different things.
- **The next U-number to issue is U29** — used for use cases. One
  shared numbering sequence covers proposed, pledged, and the root
  list.
- **The next V-number to issue is V18** — used for the scripting
  language's static validation rules, listed in
  [docs/spec/script-spec.md](../docs/spec/script-spec.md). This
  sequence used the letter S for numbers 1 through 15 before
  decision D84 renamed the letter to V (only the letter changed,
  not the numbers). An ID that was already retired before the
  rename stays retired under its new V-numbered name.
