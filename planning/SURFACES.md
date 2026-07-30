<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# The surface-change rule

> **Status:** the governing rule for changes to Reliquary's
> **application surfaces** — the critical boundaries through which
> the world drives it. The surfaces themselves are enumerated,
> S-numbered, in root [ARCHITECTURE.md](../ARCHITECTURE.md) "The
> application surfaces" — that enumeration is this rule's scope,
> answered by lookup — and each surface's normative specification
> lives in [docs/spec/](../docs/spec/). This document says how a
> surface-changing decision is weighed: against the use cases
> ([USE-CASES.md](../USE-CASES.md)) and the architectural
> principles ([ARCHITECTURE.md](../ARCHITECTURE.md)), which carry
> equal weight. When a design document and these lists disagree,
> the principles and use cases govern: the design is realigned to
> them, never the other way around.

## The decision surface

The numbered use cases — the decision surface every
surface decision is weighed against — live in
[USE-CASES.md](../USE-CASES.md); the cross-cutting
principles that run through them — the ephemeral-machine
principle, the control-plane arc, the artifact-residency
split, the feedback split — are itemized with their normative
prose in root [ARCHITECTURE.md](../ARCHITECTURE.md). They are
numbered so a decision, review, or spec section
can cite the use case it serves — and so a proposed change can
be rejected by naming the use case it costs. Those lists hold
only what is in force; proposed changes are tracked in
[proposed/USE-CASES.md](proposed/USE-CASES.md) and
[proposed/ARCHITECTURE.md](proposed/ARCHITECTURE.md),
numbering from the same global sequences and moving over when
adopted.

## The housekeeping boundary

One class of work is exempt, and its boundary is drawn here
because here is where it would be walked around. **Housekeeping**
([DECISIONS.md](DECISIONS.md) D38) approves small cleanups and
small reported defects as a standing class — tiny in scope *and*
clearly a problem — so they need no citation and no adjudication.

**It stops at the application surfaces, absolutely: a change that
touches any surface the enumeration names is automatically not
housekeeping**, whatever its diff looks like, and takes the rule
below instead. That test is asked first and answered by lookup —
root [ARCHITECTURE.md](../ARCHITECTURE.md) "The application
surfaces" enumerates them as S1–S8, so it is a checklist, not a
judgement, and a hit is cited by number. **The norm is part of the
surface** (P23): an edit to a normative artifact — a `docs/spec/`
specification, the published schema, the enumeration itself — that
changes what the norm requires *is* a surface change and takes this
rule,
proposed and gated before it lands; work that arrives already
made is rejected citing P23, whatever its merit — unless it comes
from someone holding the authority to approve it, who may land the
whole change at once (below). Only an edit
that changes no rule (the clarify test) is documentation work. This matters because housekeeping's other two tests
("tiny", "clearly a problem") are judged by whoever wants to do
the work, and the smallest-looking change is the one most likely
to be a contract change wearing a small diff.

**The boundary is housekeeping's alone** ([DECISIONS.md](DECISIONS.md)
D45), and saying so is the negative half this section was
missing.
It exists *because* housekeeping is ungoverned — approved as a
class in advance, its remaining two tests judged by whoever wants
the work — so the surface exclusion is the whole of what stands
between that class and an unreviewed contract change. It does
**not** reach the pledged task queue ([TASKS.md](TASKS.md)), where
the gate sits at entry and only authority may enter anything
(D43): **a small surface change may be a task**, admitted on size
and kind and never refused for the surface it touches. Read across,
the boundary counts the same protection twice and turns away work
authority has already approved. What this rule governs is how a
change *lands* — the three steps below — not which queue it waited
in.

## The rule

Requests triage by their use-case and principle impact. A change
to an application surface is significant precisely
when approving it requires a use case or a principle to be
adjusted; a significant change is not argued as a feature on its
own merits — the amendment is the argument, and the surface
change follows from the amended list. A significant proposal that
cannot be phrased as "the use cases should say ..." or "the
principles should say ..." is not ready to decide. The two carry
equal weight: a principle amendment is argued exactly as
vigorously as a use-case one, and neither is edited to fit a
feature someone has already decided to build.

- **No use-case or principle impact, or strong alignment with
  the existing lists.** The change leaves both untouched —
  nothing any use case demands and nothing any principle
  requires is altered — or serves them as written: a
  better spelling for an existing capability, a gap filled where
  one surface lags the others. An easy decision to approve; cite
  the use cases and principles served, or state that none are
  disturbed.
- **Adds a new use, or a new principle.** The change serves a
  use Reliquary does not yet name, or is demanded by a rule the
  project honors but has never stated. More work — the new use
  case or principle must be drafted and numbered in
  [proposed/USE-CASES.md](proposed/USE-CASES.md) or
  [proposed/ARCHITECTURE.md](proposed/ARCHITECTURE.md) and
  weighed for coherence with the existing lists and
  the ephemeral-machine principle — but, being additive, still an
  easy decision.
- **Misaligned with the use cases or a principle.** The hard
  case, and the one that must be argued very vigorously:
  approving such a change in good faith would require a use case
  or a principle to change, so the amendment — not the feature —
  is what gets argued, and a principle amendment is argued
  exactly as vigorously as a use-case one. The workflow is
  strict: draft the amendment in
  proposed/USE-CASES.md or
  proposed/ARCHITECTURE.md and make the
  argument; if the argument wins, the amendment moves to
  `pledged/` — the move is the pledge and the commit is its
  record ([README.md](README.md)); only then does work start.
  Pledged use cases move into root USE-CASES.md when their
  delivery lands, pledged principles into ARCHITECTURE.md when
  the project honors them, anything superseded retiring
  stubless — its number never reused, DECISIONS.md the record. A
  misaligned change that can propose no amendment
  has nothing to argue and is rejected, regardless of its
  elegance.

**Authority may compress the steps** (owner, 2026-07-26). The
staged workflow above is the route for someone who cannot approve
their own change. A person holding governance authority — the owner,
or whoever else the project entrusts with it — may land a surface
or norm change **outright, in a single PR**, being entitled to
perform every step it needs, and is never refused on the ground
above. That is an *execution* of the governance steps all at once
rather than a bypass of them: compressed in time, not reduced in
content, so the use-case or principle amendment, the D-entry, and
the specification update all still exist and land with it. A change
arriving with none of them has not been compressed but skipped, and
what is lost is the adjudication trail
([DECISIONS.md](DECISIONS.md)) that this whole apparatus exists to
keep. Anyone without that authority takes the staged route, and
finished work from them is refused on one of two grounds, **never
identity**: not having argued the merit, or having argued it and not
won. Word it that way — the ground names the door back in. Note the
limit honestly too: here the author of the standard is also its
arbitrator, so this is not impartial adjudication. What it offers is
a stated standard to be judged against and a recorded reasoning
([DECISIONS.md](DECISIONS.md)) to disagree with later, which absent
any separation of powers is the whole of the check. A refusal that cites a principle and stops
is accurate and useless, reading as final when it means the
opposite; every refusal states what would change the answer — argue
it, argue the amendment, or bring what beats the recorded
reasoning.

**Compression reaches the process, never the claim.** A principle's
route runs drafted → pledged → in force, and authority may collapse
it: a principle *already true of the code* may be written straight
into root [ARCHITECTURE.md](../ARCHITECTURE.md) in one act. What
authority cannot do is place a false claim there — the root lists
assert that the code complies today, so **placement is governed by
truth, not by permission**. An unarmed principle sits under
`pledged/` however unarguable it is, and an untrue one makes the
list lie. Check the shape too: a principle is a rule the project
holds itself to, not a state it merely happens to be in — and both
get phrased the same way. "No CI" as a note that no pipeline exists
would be a fact about tooling, and arming it would make *adopting*
CI a bug; P22 is deliberately the other thing, a rule about how a
pipeline may arrive. **Separate the expectation from its
enforcement**: automation changes the cost of noticing a violation,
never the status of one, so placement is governed by truth — not by
permission, and not by tooling.

Every approved change then lands the same way:

1. **Name every surface it touches, by number.** A change rarely
   touches one:
   S1 and S2 move together under the one-to-one rule, the
   language grows only through its growth goals (G6, G7), and a
   document format changes with its spec. An intentionally
   single-surface change states why the others are unaffected.
2. **Land it coherently and completely.** Pre-1.0 there is no
   backward compatibility guarantee (P9): the change updates every
   affected surface, document, example, and test to the new shape
   and deletes the old one. That freedom makes execution cheap; it
   does not make the decision cheap — nothing downstream cushions
   a wrong one.
3. **Record it.** Use-case amendments are drafted in
   [proposed/USE-CASES.md](proposed/USE-CASES.md),
   pledged by being moved out of that file, and move into
   [USE-CASES.md](../USE-CASES.md) when delivered,
   keeping their numbers; settled decisions go to their
   [docs/spec/](../docs/spec/) specs; user-facing contracts to
   their `docs/` references; examples stay synchronized.

The specification each surface answers to is indexed in
[docs/spec/README.md](../docs/spec/README.md).
