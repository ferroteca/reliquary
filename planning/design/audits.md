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

- **Mechanical** — a script can decide it. Cheap to run, safe to
  automate, and the results are facts.
- **Judgment** — it takes a person reading and thinking. A script
  can only go as far as *surfacing candidates* for a person to
  look at; it can never deliver the verdict itself. A tool that
  claims to deliver the verdict just invites people to tick a box
  without actually thinking it through.

## The caution, learned the hard way

**Check a finding again before you write it down.** The 2026-07-24
hand audit reported "U15 is cited 6 times and defined nowhere." When
it was checked again on 2026-07-26, the truth turned out to be
different: U15 had been deliberately **closed** (D36, "its demands
are U14's own"), and D23's no-stub rule says a retired number should
correctly leave no definition behind. The original finding was
false — and it had already been written into a proposal as one of
six violations used to justify building the linter.

Two lessons follow from this. First, a checker built to scan these
documents will produce false positives easily, because entries are
written in several different forms, and a retired entry is *meant*
to disappear without a trace — there's nothing left to distinguish
"retired" from "never written." Second, **a finding is not a fact
until it has been checked again** — writing an unverified finding
into the record is worse than not auditing at all, because people
trust what's in the record.

## Mechanical

- **Check that every cited identifier actually points to something.**
  Collect every `U`/`P`/`D`/`F`/`G` citation across all the markdown
  files and check each one against its definition. *Run 2026-07-26:
  clean, except for U15, which is a legitimate reference to a closed
  use case.* This check only works if there is a register listing
  retired identifiers — and right now D23's no-stub rule forbids
  keeping one anywhere obvious. That has to be reconciled before this
  can be automated, or every retired identifier will look like a
  dangling citation.
- **Check the format each entry is defined in.** Use cases are
  currently defined in at least five different forms across the
  three use-case files (bulleted, unbulleted, nested inside a
  blockquote, and combined headers such as `U16 + U17`). In
  `proposed/` that looseness is fine — a sketch is not a permanent
  record — so this check should only apply to the **in-force lists**,
  where precision matters.
- **Check that every entry in DECISIONS.md carries a `Supports`
  line.** *Measured 2026-07-26: 18 of 41 entries carry it, 23 do
  not.* Until every entry has one, answering "what has been decided
  that bears on P8?" means guessing at keywords instead of just
  looking it up. This is already a task; this is the reason for it.
- **Check that every amendment claim has a matching back-pointer.**
  When an entry says it *amends*, *widens*, *completes*, or
  *retires* another entry, the target entry must carry the
  bracketed one-line pointer that the record's own rule requires.
  Without it, anyone who finds the superseded entry by search will
  read it as still current — which is exactly the situation this
  rule exists to prevent. *Run 2026-07-26: three such claims found,
  two had a correct pointer (D43→D39, after it was fixed, and
  D41→D22), and one was missing (**D36 amends D35**, but D35 does
  not say so).* This is cheap and decidable: pull out the claims,
  then check that each target entry mentions the number that amends
  it.
- **Check that no entry appears in both a standing list and its
  proposals document** (this is D23's no-stub rule).
- **Check that every design document's subject has a pledged use
  case behind it.** The 2026-07-24 audit found three design
  documents whose subject matter D33 had demoted specifically for
  lacking that pledged demand. (F7 is this check as a feature.)

## Judgment

- **Are the in-force use cases actually met by the code?** The root
  list claims they are, and nothing has ever checked that this is
  true. This is the claim that the entire process of putting a use
  case into force depends on.
- **Are the in-force principles actually honored?** Same question,
  and harder to answer: some principles can't be checked by rule at
  all.
- **Is P24 true clause by clause?** *This question was superseded
  on 2026-07-27 by D49: it is now a filed defect rather than a
  proposed audit item, because the paragraph it replaces was wrong
  about its own premise.* As of 2026-07-26, P24 had **not** actually
  been put into force — it had only been decided in a commit
  message, it never reached any document, its D-number was reused
  that same day for something else, and this entry in audits.md was
  the only place in the whole repository that referred to it at all.
  D49 restates P24 and puts it into force (768 tests were passing at
  the time it was adjudicated). D49 also files the gap this question
  was pointing at — that most modules test behavior instead of
  deriving their test cases from the stated principle — as a defect
  under TASKS.md's Defects, because once a principle is in force, a
  known gap against it is a bug, not an item for this audit list.
  **The lesson here applies to this file too**: a finding is not a
  fact until it has been checked again, and that cuts both ways — an
  entry here that claims something *is* true needs the same
  re-check as one that claims something is broken.
- **Is every defined vision statement cited or acted on somewhere?**
  If nothing in the project relies on a vision statement, that's a
  sign it may serve no purpose. This should produce a list to look
  at, never a list of automatic removals — each statement nobody
  relies on earns one question: *is it still guarding against
  something, or is it just dead weight?* (F9 is this check as a
  feature.)
- **Does any decision recorded here contradict another?** Nothing
  currently checks that the 43 entries in DECISIONS.md are
  consistent with each other. Under the annotate-never-rewrite rule,
  an entry that has been partly overruled by a later decision stays
  in the document exactly as written, with only a pointer added to
  the entry that overrules it.
