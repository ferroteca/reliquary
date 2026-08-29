<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# The surface-change rule

> **Status:** This is the rule that governs changes to Reliquary's
> **application surfaces** — the boundaries through which the
> outside world controls it. The surfaces themselves are listed,
> with S-numbers, in root [ARCHITECTURE.md](../ARCHITECTURE.md)
> under "The application surfaces" — checking whether something is
> a surface is just a matter of looking it up in that list. Each
> surface's official specification lives in
> [docs/spec/](../docs/spec/). This document explains how a
> decision to change a surface gets weighed against the use cases
> ([USE-CASES.md](../USE-CASES.md)) and the architectural
> principles ([ARCHITECTURE.md](../ARCHITECTURE.md)) — both carry
> equal weight. If a design document ever disagrees with the use
> cases or principles, the use cases and principles win: the design
> gets changed to match them, never the other way around.

## The decision surface

The numbered use cases that every surface decision gets weighed
against live in [USE-CASES.md](../USE-CASES.md). The principles
that cut across all of them — the ephemeral-machine principle, the
control-plane arc, the artifact-residency split, the feedback
split — are listed with their full wording in root
[ARCHITECTURE.md](../ARCHITECTURE.md). Both lists are numbered so
that a decision, a review, or a section of a spec can cite the use
case it's serving — and so a proposed change can be turned down by
naming the use case it would harm. These two lists hold only what's
currently in force; proposed changes are tracked separately in
[proposed/USE-CASES.md](proposed/USE-CASES.md) and
[proposed/ARCHITECTURE.md](proposed/ARCHITECTURE.md), drawing from
the same overall numbering sequences and moving into the main lists
once adopted.

## The housekeeping boundary

One category of work is exempt from all this, and its limits are
defined here because this is where someone might otherwise try to
sneak around them. **Housekeeping** (decision D38 in
[DECISIONS.md](DECISIONS.md)) pre-approves small cleanups and small,
obviously real bugs as a standing category — tiny in scope *and*
clearly a problem — so they don't need a citation or a formal
decision.

There's one absolute limit: **any change that touches an application
surface is automatically not housekeeping**, no matter how small the
diff looks — it has to follow the rule below instead. This check
comes first, and it's a lookup, not a judgment call: root
[ARCHITECTURE.md](../ARCHITECTURE.md), "The application surfaces,"
lists them as S1 through S8, so you just check the list and cite the
number if there's a match. **The spec itself counts as part of the
surface** (P23): editing a normative document — a spec in
`docs/spec/`, a published schema, or the surface list itself — in a
way that changes what it requires *is* a surface change, and has to
be proposed and approved through this rule before it lands. If such
a change shows up already made, it gets rejected and P23 is cited,
no matter how good the change is — unless it comes from someone with
the authority to approve changes themselves, who can land the whole
thing in one step (see below). The only edits to these documents
that count as plain documentation work are ones that don't change
any rule — just clarify existing wording. This distinction matters
because housekeeping's other two conditions — "tiny" and "clearly a
problem" — are judged by whoever wants to do the work, and the
smallest-looking change is exactly the kind most likely to secretly
be a change to the contract.

This surface-touching exclusion **applies only to housekeeping**
(decision D45 in [DECISIONS.md](DECISIONS.md)) — stating that
plainly is the missing piece this section needed. The exclusion
exists specifically because housekeeping has no other review: it's
pre-approved as a whole category, and its other two conditions are
judged by whoever wants to do the work. So keeping surface changes
out of housekeeping is the only thing standing between that category
and an unreviewed change to the contract. This exclusion does
**not** apply to the task queue ([TASKS.md](TASKS.md)), where every
entry already requires someone with authority to add it (D43): a
small change to a surface *can* be entered as a task — it's judged
on its size and kind, never turned away just because it touches a
surface. Applying the surface exclusion to tasks too would just
double up a protection that's already there and would turn away work
that authority already approved. What this rule actually controls
is how an approved change gets carried out — the three steps below —
not which queue it came through.

## The rule

Requests get sorted by whether they affect the use cases or
principles. A change to an application surface counts as
significant exactly when approving it would require changing a use
case or a principle. A significant change isn't argued for on its
own merits as a feature — instead, the argument is about changing
the use case or principle, and the surface change follows from
that. If a significant proposal can't be phrased as "the use cases
should say ..." or "the principles should say ...", it isn't ready
for a decision. Use cases and principles carry equal weight: an
argument to amend a principle gets argued just as thoroughly as one
to amend a use case, and neither one gets bent to fit a feature
someone has already decided to build.

- **No effect on the use cases or principles, or it clearly matches
  what they already say.** The change either leaves both lists
  untouched — nothing any use case demands or any principle
  requires actually changes — or it directly serves what's already
  written: a better way of doing something Reliquary already does,
  or filling a gap where one surface lags behind the others. This
  is easy to approve — just cite the use cases and principles it
  serves, or state that neither list is affected.
- **Adds a new use case or a new principle.** The change serves a
  purpose Reliquary doesn't currently name, or is required by a
  rule the project already follows but has never written down.
  This takes more work: the new use case or principle has to be
  drafted and numbered in
  [proposed/USE-CASES.md](proposed/USE-CASES.md) or
  [proposed/ARCHITECTURE.md](proposed/ARCHITECTURE.md), and checked
  for consistency with the existing lists and with the
  ephemeral-machine principle. But since it's purely additive, it's
  still an easy call.
- **Conflicts with a use case or a principle.** This is the hard
  case, and it has to be argued very thoroughly: approving a change
  like this, in good faith, would require changing a use case or a
  principle — so the thing actually being argued is the amendment,
  not the feature, and an amendment to a principle gets argued just
  as thoroughly as one to a use case. The process here is strict:
  draft the amendment in `proposed/USE-CASES.md` or
  `proposed/ARCHITECTURE.md` and make the case for it. If the
  argument succeeds, the amendment moves to `pledged/` — that move
  is the pledge, and the commit that makes it is the record
  ([README.md](README.md)) — and only then does the actual work
  begin. A pledged use case moves into root USE-CASES.md once it's
  delivered; a pledged principle moves into ARCHITECTURE.md once
  the project actually follows it. Anything the amendment replaces
  is retired without a stub — its number is never reused, and
  DECISIONS.md is where that's recorded. If a change conflicts with
  the use cases or principles and no amendment can be proposed for
  it, there's nothing left to argue, and it's rejected regardless
  of how good the idea otherwise is.

**Someone with authority can skip the staged steps** (owner,
2026-07-26). The staged process above is for someone who can't
approve their own change. A person who holds governance authority —
the owner, or anyone else the project gives that authority to — can
land a surface or norm change directly, in a single pull request,
doing every required step themselves, and can't be refused on the
grounds described above. This isn't skipping the process — it's
doing every step of it at once. The use-case or principle amendment,
the entry in DECISIONS.md, and the spec update still all have to
exist and land together with the change; only the timing is
compressed, not the content. A change that shows up with none of
those things hasn't been compressed, it's been skipped, and what's
lost is the record of reasoning in [DECISIONS.md](DECISIONS.md),
which is the entire point of this process. Anyone who doesn't hold
that authority has to go through the staged process, and if their
finished work is refused, it's refused for one of two reasons,
**never because of who they are**: either they didn't make the case
for it, or they made the case and didn't win. State refusals that
way, because that phrasing also names the way to come back and try
again. It's worth being honest about a limitation here too: the
same person who wrote this standard is also the one judging changes
against it, so this isn't an impartial process. What it offers
instead is a clearly stated standard to be judged against, and a
written record of the reasoning ([DECISIONS.md](DECISIONS.md)) that
can be argued with later — without any separation of powers, that's
the entire check that exists. A refusal that just cites a principle
and stops there is technically accurate but useless — it reads as
final when it isn't meant to be. Every refusal should state what
would change the outcome: make the case, propose the amendment, or
bring an argument that beats the reasoning already on record.

**Compressing the steps only speeds up the process — it never
changes what's actually true.** A principle normally moves drafted →
pledged → in force, and authority can skip straight through those
stages: if a principle is already true of the code, it can be
written directly into root [ARCHITECTURE.md](../ARCHITECTURE.md) in
one step. What authority can't do is put something false there —
the root lists claim the code complies *today*, so where a
principle gets placed depends on whether it's actually true, not on
who has permission to place it. A principle the code doesn't yet
follow belongs under `pledged/`, no matter how obviously correct it
is, and putting an untrue principle in the root list would make
that list a lie. It's also worth checking the shape of the
principle itself: a principle should be a rule the project holds
itself to, not just a fact about its current state — and the two
can be worded almost identically. For example, "No CI" as a note
that there's simply no pipeline yet would just be a fact about
tooling, and treating that as an armed principle would turn *adding*
CI into a bug. P22 is deliberately worded as the other kind of thing
— a rule about how a pipeline is allowed to be introduced, not a
statement that none exists. Keep the expectation separate from how
it's enforced: automation changes how easily a violation gets
noticed, but never whether something counts as a violation. So where
something belongs is decided by whether it's true, not by who has
permission or what tooling exists.

Once a change is approved, it lands the same way every time:

1. **Name every surface it touches, by number.** A change rarely
   touches just one surface: S1 and S2 always move together under
   the one-to-one rule, the scripting language only grows through
   its stated growth goals (G6, G7), and a document format changes
   together with its spec. If a change genuinely touches only one
   surface, say why the others aren't affected.
2. **Land it as one coherent, complete change.** Before version 1.0
   there's no promise of backward compatibility (P9), so the change
   should update every affected surface, document, example, and
   test to the new shape, and delete the old one, all at once. That
   freedom makes the change itself cheap to carry out — it does not
   make the decision behind it any cheaper, since nothing downstream
   will soften the effect of a wrong decision.
3. **Record it.** Use-case amendments are drafted in
   [proposed/USE-CASES.md](proposed/USE-CASES.md),
   pledged by being moved out of that file, and move into
   [USE-CASES.md](../USE-CASES.md) once delivered, keeping the same
   number throughout. Settled decisions get written into their
   specs in [docs/spec/](../docs/spec/); user-facing contracts get
   written into their `docs/` references; and examples are kept in
   sync.

The spec each surface has to follow is indexed in
[docs/spec/README.md](../docs/spec/README.md).
