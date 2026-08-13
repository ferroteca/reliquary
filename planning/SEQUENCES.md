<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# The sequence ledger

The planning root holds what never moves ([README.md](README.md)),
and this file is the handle ledger: **the next number to issue for
every handle sequence the project carries**. Issue from here and
advance the mark in the same edit, on `main`.

**These lines are not status columns** (D42): each records what
its sequence has spent, and says nothing about what was done, by
whom, or when. A number, once issued, is never reissued — a struck
task or a delivered feature takes its number with it, and gaps in
a sequence are history rather than a promise.

Why a ledger, when the record could be searched: a search sees
only the branch it stands on. A struck task's only record is its
commit (D52), a feature's retirement is named in
[DECISIONS.md](DECISIONS.md) only once its round lands, and a
number issued on an unmerged feature branch is visible from
nowhere else — so the incidental cover fails exactly when feature
branches arrive (owner, 2026-07-31). **The permanent classes count
here too** (owner, same day): a file that keeps every entry it has
ever held, and vision lists whose handles never evaporate, still
count their populations only on the branch being searched — a
decision recorded or a use case drafted on an unmerged branch
mints a number invisible from `main` — and one rule for every
class spares each issuance the which-kind-is-this reasoning.

Where a mark and a file's own population disagree, someone issued
past the ledger: advance the mark. The higher number governs, and
nothing is ever reissued.

## The marks

- **The next D-number to issue is D103** — decisions, recorded in
  [DECISIONS.md](DECISIONS.md).
- **The next F-number to issue is F54** — features, drafted in
  [proposed/FEATURES.md](proposed/FEATURES.md) or cut straight to
  [pledged/FEATURES.md](pledged/FEATURES.md) on pledge.
- **The next G-number to issue is G8** — the authored language's
  goals ([docs/spec/script-spec.md](../docs/spec/script-spec.md)).
- **The next P-number to issue is P28** — architectural
  principles, one namespace across proposed, pledged, and the root
  list.
- **The next R-number to issue is R12** — recurring obligations,
  standing in [RECURRING.md](RECURRING.md), the number
  evaporating when an obligation is retired.
- **The next S-number to issue is S9** — application surfaces
  (root [ARCHITECTURE.md](../ARCHITECTURE.md), "The application
  surfaces").
- **The next T-number to issue is T18** — tasks, entering
  [TASKS.md](TASKS.md), entry being the pledge (D43). The sequence
  started at **T8** because T0–T7 were spent by an earlier
  per-list numbering that ran three separate times, surviving in
  [DECISIONS.md](DECISIONS.md) under the entries that landed them;
  beginning above them is what keeps every T-number in the record
  resolving to exactly one thing.
- **The next U-number to issue is U24** — use cases, one namespace
  across proposed, pledged, and the root list.
- **The next V-number to issue is V17** — the script language's
  static validation rules
  ([docs/spec/script-spec.md](../docs/spec/script-spec.md)). The
  sequence spent 1–15 under its old S-spelling before D84 renamed
  the letter — the number never changes — and the id retired
  before the rename stays retired under the new letter.
