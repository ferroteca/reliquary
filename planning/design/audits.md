<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Audit suggestions

Ideas for what could be checked about this project's own claims.
**Nothing here is policy, enforced, or committed to.** It is a
holding list, so that a check worth running is written down when it
occurs to someone rather than lost.

It sits in `design/` rather than inside a feature because the ideas
outlive any particular one: F8 (the traceability linter) and F9 (the
vision-utility audit) would implement some of these, F7 is one of
them, and if any of those proposals dies the ideas should not die
with it.

Two kinds, and the difference matters:

- **Mechanical** — decidable by a script. Cheap to run, safe to
  automate, and the results are facts.
- **Judgment** — requires reading and thinking. Automatable only as
  far as *surfacing candidates*; the verdict is never the tool's.
  A tool that pretends otherwise licenses box-ticking.

## The caution, learned the hard way

**Verify a finding before recording it.** The 2026-07-24 hand audit
reported "U15 is cited 6 times and defined nowhere". Re-run
2026-07-26: U15 was deliberately **closed** (D36, "its demands are
U14's own"), and under D23's no-stub rule a retired number correctly
leaves no definition behind. The finding was false — and it had
already been written into a proposal as one of six violations
justifying the linter.

Two lessons stand behind it. A checker over these documents produces
false positives easily, because entries appear in several forms and
retirement is invisible by design. And **a finding is not a fact
until it is re-tested** — an unverified finding entering the record
is worse than no audit, because the record is trusted.

## Mechanical

- **Every cited identifier resolves.** Collect `U`/`P`/`D`/`F`/`G`
  citations across all markdown and check each against its
  definitions. *Run 2026-07-26: clean, except U15 which is a
  legitimate death-record reference.* The check is only sound with a
  register of retired identifiers, which D23's no-stub rule
  currently forbids anywhere obvious — reconcile the two before
  automating, or every retirement reads as a dangling citation.
- **Entry-definition formats.** Use cases are defined in at least
  five forms across the three files (bulleted, unbulleted,
  blockquote-nested, and combined headers such as `U16 + U17`).
  For `proposed/` this is appropriate looseness — a sketch is not a
  record — so the check belongs to the **in-force lists only**,
  where precision is the point.
- **Every DECISIONS entry carries `Supports`.** *Measured
  2026-07-26: 18 of 41 carry it, 23 do not.* Until complete,
  "what has been decided that bears on P8?" is keyword-guessing
  rather than lookup. Already a task; this is its justification.
- **Every amendment claim has a back-pointer.** When an entry says
  it *amends*, *widens*, *completes* or *retires* another, the
  target must carry the bracketed one-line pointer the record's own
  rule requires — otherwise the superseded clause reads as current
  to anyone arriving by search, which is the exact case that rule
  exists for. *Run 2026-07-26: three claims, two sound (D43→D39
  after fixing, D41→D22), one missing (**D36 amends D35**, and D35
  does not say so).* Cheap and decidable: extract the claims, check
  each target mentions the amending number.
- **No entry appears in both a standing list and its proposals
  doc** (D23's no-stub rule).
- **Every design document's subject has pledged demand** — the
  2026-07-24 audit found three designs for pillars D33 demoted for
  lack of it. (F7 is this check as a feature.)

## Judgment

- **Are the in-force use cases actually met by the code?** The root
  list asserts they are, and nothing has ever confirmed it. This is
  the claim the whole arming mechanism rests on.
- **Are the in-force principles actually honored?** Same, and
  harder: some principles are not codifiable.
- **Is P24 true clause by clause?** *Superseded 2026-07-27 by
  D49: this question is now a filed defect rather than a proposed
  audit, and the paragraph it replaces was wrong about the
  premise.* P24 was **not** armed on 2026-07-26 — it was decided
  in a commit message and reached no document at all, its
  D-number reused the same day, and this entry was the only place
  in the repository that referred to it. D49 restates and arms
  it (768 passing at adjudication), and files the gap this
  question named — most modules test behavior rather than
  deriving cases from the norm — under TASKS.md's Defects,
  because a named gap against an armed principle is a bug and
  not an audit idea. **The lesson is this file's own**: a
  finding is not a fact until re-tested, and that cuts both
  ways — an entry here asserting something *is* true needs the
  same re-test as one asserting something is broken.
- **Is every defined vision statement cited or codified somewhere?**
  A statement nothing leans on is suspect of no utility. A
  look-list, never a kill-list; each orphan earns one question,
  *guardrail or ballast?* (F9 is this check as a feature.)
- **Does any decision recorded here contradict another?** Nothing
  checks coherence across 43 entries, and the annotate-never-rewrite
  rule means a partly-overruled entry stays in place with a pointer.
