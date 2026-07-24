<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# TASKS

The work queue — and the parking place for non-GitHub issues
(the tracker:
<https://github.com/ferroteca/reliquary/issues>).

**An idea enters this project through exactly two raw queues**
(D39): GitHub issues — the unfiltered intake, often from outside —
and the `proposed/` directory, where the same idea is argued in
the project's own vocabulary as a drafted use case, principle or
task. Nothing flows without starting in one of them, and the only
exception is a small raw commit approved under housekeeping
(below). Issues are upstream of proposals, not their peer: raw
intake is triaged into a drafted proposal, fixed directly as
housekeeping, or rejected with its reason recorded in
[DECISIONS.md](DECISIONS.md). Composed with housekeeping's refusal
of anything touching an interface, this is what guarantees that
**no interface changes without having passed through a queue**.

Tasks flow from the roadmap and from issues; small one-offs really
just are issues, and a small, obvious, needed fix goes directly to
tasks. **A task carries the same lifecycle as a use case or a
principle** (owner, 2026-07-24): it is *proposed*, *accepted*,
*completed*, or *rejected*, and this file is grouped by that
state. One vocabulary now runs through the whole planning
machinery — the same four words classify demand, rules and work
alike. In theory
every issue points to the use case or principle it serves;
principles ([PRINCIPLES.md](../PRINCIPLES.md)) drive tasks just as
use cases do. The exception is a standing one:
**housekeeping** (D38) approves small cleanups and small reported
defects as a class, in advance — tiny in scope *and* crystal clear
they are a problem — so they need no citation, no issue and no
decision of their own. Whoever lands the work invokes it by naming
it in the commit, and the commit is the record. Refusing is half
the rule: anything failing that test is **rejected** under
housekeeping and takes the rigorous route instead. The first
question is mechanical and absolute — **does it change an
interface?** INTERFACES.md enumerates them, so this is a lookup
rather than a judgement, and a yes is automatically not
housekeeping however small the diff. A use-case or principle
amendment and a design decision are likewise never admissible.
Past that, doubt escalates — if it has to be argued into the
bucket, it does not belong in it. (A defect against a *standing* principle is not
housekeeping either: the principle is already its demand, so it
needs no approval, only fixing.) An issue can
easily trigger a use-case or principle change, drafted as a
proposal in [USE-CASE-PROPOSALS.md](USE-CASE-PROPOSALS.md) or
[PRINCIPLE-PROPOSALS.md](PRINCIPLE-PROPOSALS.md) through the
interface-change rule (INTERFACES.md), which weighs the two
alike. Large work belongs in
the roadmap; a milestone item is picked up by translating it
into a sprint tasklist here. The adjudicated design-decision
records live in
[DECISIONS.md](DECISIONS.md). Completed milestone
task-breakdowns are pruned once the milestone lands — the
record survives in git history, DECISIONS.md, and the ROADMAP
milestone notes (the milestone-4, -6, and -7 breakdowns were
pruned 2026-07-23).

The lifecycle in this file:

- **[Proposed](#proposed)** — argued but not approved. Nothing may
  be worked from here.
- **[Accepted](#accepted)** — approved to do, and grouped by kind
  below because the actor and the gate differ. Accepted is not
  scheduled: the numbered arc ended with milestone 9, so nothing
  here is currently on a sprint.
- **[Completed](#completed)** — done. Kept until its record is
  folded where it belongs and pruned, per the rule above.
- **[Rejected](#rejected)** — refused, with the reason recorded in
  [DECISIONS.md](DECISIONS.md), which is already the guard against
  re-litigating. The section here is a thin index pointing at
  those entries, never a second record of the argument.

Two things below are deliberately *not* tasks and sit outside the
lifecycle: [Watches](#watches) are standing questions to re-ask as
the design hardens, and the completed milestone breakdowns are
landing records awaiting their prune.

Housekeeping (D38) is best read in this vocabulary: it is a
**standing acceptance**. A qualifying item is accepted on sight
and needs no entry here at all; everything else is accepted
explicitly, or rejected.

## Proposed

Argued but not approved. Nothing is worked from here until it
moves to Accepted.

- **Audit design documents against accepted demand.** Raised
  unprompted during the 2026-07-24 traceability audit rather than
  requested, so it waits here. Findings that motivate it are
  recorded with the audit tasks under Governance.

- **A traceability linter over the planning documents.** Check the
  invariants the governance rules already assert, in the required
  checks, so they are enforced rather than remembered.
  THE ARGUMENT: the artifacts are versioned files by necessity —
  the standing lists claim every entry is true of the code *at
  this commit*, which only something travelling in the commit can
  assert, and only a diff can review (this is why architecture
  decision records converged on markdown-in-repo, and why their
  tooling is indexers over files rather than trackers). What files
  do not give is **type and query**: nothing enforces that a
  decision carries supports or that delivered work cites accepted
  demand. Today those are checked by whoever happens to grep,
  which is exactly how U9 and U12 went unnoticed through the
  milestone that delivered them.
  EACH CHECK EARNED ITS PLACE — the 2026-07-24 hand audit found a
  real violation of every one:
  * every ROADMAP section cites a U/P/G demand — *12 of 34 cite
    none*;
  * every DECISIONS entry carries supports — *22 lack them, and
    D29 sat outside the range the existing task assumed*;
  * no *delivered* work cites *unaccepted* demand — *U9 and U12*,
    the sharpest defect of the set, and the one a linter would
    have caught the day milestone 9 landed;
  * every design document's subject has accepted demand — *three
    designs exist for pillars D33 demoted for lack of it*;
  * every cited identifier resolves — *U15 is cited 6 times and
    defined nowhere*;
  * no entry appears in both a standing list and its proposals doc
    (D23's no-stub rule).
  ONE DESIGN POINT IT RAISES. The U15 result is not simply a bug
  to fix: most of those citations are legitimate death-record
  references, and the lifecycle deliberately leaves **no stub**
  behind a retired number (D23). So a checker cannot distinguish a
  proper historical citation from a stale one without a
  machine-readable register of retired identifiers — which the
  no-stub rule currently forbids anywhere obvious. Reconcile the
  two before building: either the register lives in DECISIONS.md's
  Retired list in a parseable form, or retirement earns the one
  stub the rule otherwise refuses.
  SCOPE, deliberately narrow: mechanical invariants only. Whether
  a use case is *well argued*, whether a principle is *honored by
  the code*, whether a design is *good* — none of that is
  checkable, and a linter that pretended otherwise would licence
  exactly the box-ticking the governance rules exist to prevent.
  Proposed rather than accepted: my suggestion, not a request.

## Accepted

Approved to do, not scheduled — the numbered arc ended with
milestone 9, so nothing below is on a sprint. Grouped by kind,
because the actor and the gate differ: an adjudication is the
owner's alone, an audit is mechanical, a restructure is
citation-heavy and must run in order.

### Governance — adjudications

Owner-only: each settles a question the record is waiting on.
None depends on the others.

- **Accept and promote U9 and U12 — delivered work is standing on
  unaccepted demand.** Milestone 9's own text cites "live feedback
  for a watched install (U12, P5)", and ROADMAP's "The run and its
  output" cites "an automating program reads machine-readable
  events as they happen and takes the result (U9, U14)" — both
  flatly, not conditionally. Both use cases are **drafted, never
  accepted**, and both describe behavior that now ships
  (`--progress` and the jsonl event stream). Under D23 scheduling
  milestone 9 accepted them and the record never moved; under D34
  their delivery should then have promoted them to USE-CASES.md
  beside U14 and U20. Missed by D37's promotion pass, which
  checked only the two use cases the milestone named as its own.
  This is the sharpest instance of the class: the standing list is
  an implementation claim, so it is currently *incomplete* rather
  than merely untidy.
  Distinguish from the legitimate citations the same audit found —
  U7, U8, U13, U18 and U19 are all named conditionally by backlog
  work ("would stand on the U13 draft if accepted", "U7 is what
  schedules this work back onto the arc"), which is the rule
  working, not failing.

- **Promote the principles reality has already caught up with.**
  The standing list is P1, P2, P3, P4, P6, P7, P8, P10, P11, P12,
  P13, P15 — P5, P9 and P14 are missing from it while being cited
  throughout DECISIONS.md, AGENTS.md and ROADMAP.md, and P17/P18
  are drafted with milestone 9's code as evidence for both.
  WHY IT MATTERS, and it is not bookkeeping: **promotion is what
  arms a principle** (owner, 2026-07-24). Before it, an entry is
  accepted vision and a shortfall is unbuilt work; after it,
  PRINCIPLES.md asserts the thing is true of the code, so a
  divergence is a *bug*. P9 is the sharpest case — AGENTS.md
  enforces "no backward compatibility before 1.0" as a required
  invariant and milestone 9 obeyed it deliberately when it deleted
  the run-record model rather than shimming it, yet because P9 is
  not standing, a shim that crept in tomorrow would be a debatable
  design choice rather than a defect. The delay is costing
  enforcement.
  P16 and P17 carry open adjudication questions (P17 four of
  them); P17's first — where the drive-letter mapping comes from —
  now has a worked implementation to argue against rather than a
  hypothetical (D37).

- **Record the gap-is-a-bug rule, and the two promotion bars.**
  PRINCIPLES.md's preamble says the list is standing-only and
  every entry honored by the code today — true, but passive: it
  never says what a divergence *is*. It is a bug, and that is the
  mechanism by which principles drive work with no use case asking
  (the control-planes item under [Defects](#defects) is one such
  bug, filed against P11 by the P1–P12 delivery pass; milestone
  9's floppy-geometry guard is another).
  This also sharpens D34, which sets **one** promotion test for
  use cases and principles alike and refuses a partly-delivered
  entry as "a false one". That flattens a real difference: a use
  case is a discrete journey, so *full* delivery is the honest and
  testable bar (U14's loop either runs end to end or does not); a
  principle is a standing property of the whole codebase that
  cannot be exhaustively proven, so its bar is "honored as a
  rule", and promoting at *largely there* is exactly what converts
  the residue from invisible shortfall into filed bugs. Wants a
  D-number so the divergence from D34 is deliberate rather than a
  contradiction someone trips over.

- **Take or refuse U3's supersession.** D36 settled that U14
  supersedes U3 alone; U14 is now delivered and promoted (D37).
  Retiring U3 is the lifecycle's Retire clause — an owner
  adjudication, not a step of that delivery — so it waits in
  USE-CASE-PROPOSALS.md with a note saying so.

- **Define "horizon", or drop it.** The word is never defined
  anywhere in the repo; it entered through a documentation
  restructure and its only gloss is its own heading, "(sequenced
  later, not yet scheduled)". It has since collapsed into a
  synonym for *backlog*: machine mobility sits under Horizon "for
  lack of use-case backing", which is verbatim D33's reason for
  sending the pillars to the backlog. Unlike backlog — a defined
  Scrum artifact every reader arrives knowing — horizon has no
  established meaning as a planning container ("planning horizon"
  is a *time span*; McKinsey's Three Horizons is a portfolio
  model whose horizons are all active). Either define it at first
  use or drop it and name the sections after what actually
  distinguishes them: demand accepted and awaiting scheduling (U6's
  recorder) versus design settled with demand not accepted (the
  pillars, async, machine mobility).

### Governance — audits

Backlogged (unscheduled). Problems in the planning machinery
itself, found while landing milestone 9 and while asking where the
roadmap's bulk belongs (2026-07-24). They move to
planning/BACKLOG.md when that split lands — which is one of them.
The former "Planning docs" section is folded in here: its two
sweeps are the same class as everything else below (owner,
2026-07-24 — *something exists in the planning machinery without
the demand that justifies it*), and splitting the class across two
sections was itself part of the problem.

**The class, stated once.** The traceability rule says every
roadmap item, design document, and decision names the U-number (in
force or proposed) or P-number that demands it. A violation takes
one of three shapes, and each has its own remedy: work that cites
*no* demand (find it or delete the work); work that cites
*unaccepted* demand as though it were accepted (accept it, or
mark the citation conditional); and a design written for demand
that was never accepted at all (the D33 pattern — the design
outran its justification). The audits below are the standing way
to find them, not a one-off.


- **Sweep ROADMAP items for demand citations** (owner,
  2026-07-23; audited 2026-07-24). Every item names the U- or
  P-number that demands it. Audit result: **12 of 34 sections cite
  no U/P/G at all.** Two are upstream of demand and need none
  ("Vision", "Design principles" — the latter being the source of
  P-numbers, and already tracked for itemizing into
  PRINCIPLES.md). The rest divide: five completed milestones (1,
  2, 3, 4, 6 — milestone 6 the largest at 116 lines), which the
  condensation item below should not erase without first
  recording what demanded them; four delivered design sections
  ("The machine model", "The codex", "Home layout", "Guest
  communication design"), which migrate to `spec/` and should
  carry a citation when they do; and **"The GUI era" (94 lines) —
  a whole backlog pillar citing no demand whatsoever**, which is
  the D33 pattern in its purest form.

- **Retrofit supports onto DECISIONS.md entries** (owner,
  2026-07-23; audited 2026-07-24). Each names the use cases (U),
  principles (P), or goals (G) it supports; new entries carry
  supports from the start. Audit result: **22 entries lack one** —
  D1–D21 as the original task said, minus D22 (done, pulled
  forward by the milestone-7 governing-input audit), **plus D29**,
  which the original range missed. Correct the scope when picking
  it up.

- **Audit design documents against accepted demand.** Two
  documents cite no U/P/G at all: `backend-adapter.md` (230 lines)
  and `machine-blueprint-cookbook.md` (440 lines, examples —
  arguably exempt). Beyond citation, three designs exist for
  pillars whose demand was never accepted — `backend-adapter.md`,
  `guest-communication.md`, `landmarks.md`, all demoted by D33
  *for lack of use-case backing* after their designs were written.
  The restructure item below encodes the preventive rule (nothing
  gets a design doc until its demand is accepted); this is the
  retrospective pass over what predates it.

### Governance — restructures

Mechanical, citation-heavy, and **sequenced** — each depends on
the one before it. Run them in this order or the later ones move
content twice.

1. Split the unscheduled work into `planning/BACKLOG.md`
2. Restructure `planning/` around the lifecycle (and create
   `spec/`) — takes the backlog pillar designs with step 1
3. Migrate delivered design out of ROADMAP into `spec/` — its
   destination is decided by step 2
4. Condense the completed milestone sections to notes — must not
   run before the ROADMAP demand-citation audit above, which would
   otherwise lose what demanded milestones 1, 2, 3, 4 and 6

- **Split the unscheduled work into planning/BACKLOG.md**
  (decided, owner, 2026-07-24). Everything unscheduled goes:
  ROADMAP's four backlog pillars, "Asynchronous runs (backlog)"
  and Horizon (~400 lines), plus this file's Backlog, Language,
  U6 authoring recorder and Watches sections. TASKS.md is then
  purely the scheduled list — currently empty, which honestly
  reflects the numbered arc having ended. Sections inside keep the
  gates visible, because they differ: a pillar returns by
  *accepting a use case* (D23), a small item when someone has an
  hour. Cost: roughly twenty inbound citations to rewrite.

- **Restructure planning/ around the lifecycle** (decided, owner,
  2026-07-24). Three primary subfolders, one pipeline rather than
  two axes: **proposed/** (argued, not accepted) → **accepted/**
  (accepted, not delivered) → **design/**, which is *implementation
  planning of accepted items*. The governing files —
  INTERFACES.md, DECISIONS.md, ROADMAP.md, TASKS.md, BACKLOG.md —
  stay at planning/ root; docs/ stays user-facing and unchanged.
  THE RULE HAS TEETH: **nothing gets a design doc until its demand
  is accepted.** Applied to what exists, that is not a formality —
  the project wrote `backend-adapter.md`, `guest-communication.md`
  and `landmarks.md`, and D33 then demoted all three pillars *for
  lack of use-case backing*. The folder would have made that
  visible while the designs were being written rather than after.
  A trial sort found design/ doing four jobs, only one of which is
  the stated meaning:
  * ~10 normative specs of **delivered** interfaces (`media-spec`,
    `script-properties`, `http-serve`, `machine-blueprint`,
    `codex`, `instance-model`, …) — these describe what exists, so
    planning/ is the wrong parent. **Decided: a top-level `spec/`**,
    with a doc moving `planning/design/` → `spec/` as its milestone
    lands, which puts the lifecycle in the path end to end. This
    also settles the destination for the ROADMAP migration item
    below, so that one should not start first.
  * 2 that fit the stated meaning — `recorder.md` (U6, accepted)
    and `api.md` (the end-goal embedding API).
  * 3 designs for backlog pillars whose demand was never accepted.
    **Decided: they move with the backlog they serve**, beside
    BACKLOG.md — D33 kept each "settled and intact" precisely so it
    survives the demotion, and this keeps design/ meaning what it
    says.
  * 1 outright misfiled: `cli.md` self-describes as a "working
    document for brainstorming the command-line" — a proposal
    sitting in the design folder.
  CORROBORATION: `.agents/skills/documentation-rules.md` already
  defines `planning/design/` as "end-goal designs, **not current
  truth**", while ~10 of its documents say "implemented" or
  "normative and implemented" in their own status banners. The
  folder drifted from its own written rule; this restructure is
  what brings the two back together.
  ALSO DECIDED: USE-CASE-PROPOSALS.md and PRINCIPLE-PROPOSALS.md
  each split across the two folders (proposed/ and accepted/
  halves), so promotion becomes moving an entry between two files
  in two folders — D34's "add there, delete here, no stub" made
  mechanical and visible in the diff instead of a discipline
  someone has to remember.
  Cost: ~30 file moves, their inbound citations, and rewrites of
  AGENTS.md's layout section and documentation-rules.md's
  placement rules — both of which currently teach the old shape.

- **Migrate delivered design out of ROADMAP into its specs.**
  ~1,100 lines describe interfaces that now have normative homes:
  "The CLI" (476 lines), "The machine model" (184),
  "Authored-asset resolution" (66), "The scripting language"
  (283), "The run and its output" (88). The governing rule to
  adopt: **the roadmap holds what is planned, the spec holds what
  is decided, and the milestone note records that it landed** —
  AGENTS.md already scopes ROADMAP to "planned interfaces and
  architecture".
  MEASURED BEFORE PROPOSING, because it changes the job: this is
  **not** de-duplication. Only 2 of 120 sentences in ROADMAP's CLI
  section appear anywhere in design/cli.md, and none in
  docs/cli-reference.md — the command synopsis overlaps (41 of 53
  commands) but the lifecycle semantics, the stability contract
  and the output discipline exist *only* in the roadmap, which is
  why 24 citations point at it. So the content must move and carry
  its citations, never be deleted: ~40 inbound references across
  the set (24 "The CLI", 12 async, 8 authored-asset, 5 Horizon).
  Deliberately its own pass — the citation rewrites must be exact
  or the traceability rule breaks.
- **Condense the completed milestone sections to notes**
  (decided, owner, 2026-07-24). Milestones 1–9 occupy ~940 of
  ROADMAP's ~2,800 lines in deliverable lists and Done-when
  clauses that are now all satisfied; git and DECISIONS.md hold
  the record. Keep title, what it delivered, and the decisions it
  cites — roughly 180 lines. This is the rule this file already
  applies one level down when it prunes completed breakdowns
  "into the ROADMAP milestone notes", turned on the notes
  themselves. Takes the milestone-8 and milestone-9 breakdowns
  above with it: both say they are kept only until this happens.

### Defects

A gap against a *standing* principle is a bug: the principle is
already its demand, so these need no acceptance, only fixing.

- validate declared control-planes at materialization: the
  parser accepts `vnc` / `serial-console` / `guest-agent` as
  `control-planes` values, but nothing refuses them at create
  or start — a blueprint declaring an unimplemented plane is
  accepted silently, against P11 (capability gaps fail closed
  naming themselves). Refuse anything but `agentless-display`
  until the plane exists (found by the P1–P12 delivery pass,
  2026-07-23).

### Design

- Built-in input pacing before guest input — OPEN (owner,
  2026-07-24, raised by milestone 9's FreeDOS install failure).
  Shape settled in that day's question round; unscheduled.
  Demand: G1, G5; serves U12, U14, U20 — a script that cannot
  reliably land a keystroke serves none of them.
  THE PROBLEM, with evidence: `freedos-install.rlqs` waited for
  the installer's welcome screen and then `press enter`, and the
  keystroke was swallowed — the installer paints the screen
  *before* it starts reading the keyboard. The wait timed out 30s
  later at the next step. Pressing Enter by hand, seconds after,
  advanced it immediately. Reproduced on the pre-milestone tree,
  so this is structural, not a regression. It was worked around by
  switching that one line to `select "Yes"`, which is
  feedback-driven and re-reads the screen between keys — which is
  also *why* every other confirmation in that script already
  worked.
  THE OWNER'S POSITION: this will be very common — "wait for
  <this>, then do <that>" needs a gap between the two — and
  authors should not have to code that gap every time. A standard
  delay belongs in the system; only *changing* it should require
  writing anything.
  THE FRAMING THAT MAKES IT LEGAL: this is **not** a `delay` verb,
  and the language's prohibition on one stands. script-spec.md's
  Timing section already ends "Screen polling and input-event
  pacing remain control-plane-owned; the script does not tune
  them" — a gap between observing a screen and delivering the next
  input *is* input-event pacing. G1 supplies the argument:
  agentlessly, the guest's *input* readiness is unobservable (only
  its output is), so a control plane that types the instant a
  screen paints asserts something it cannot know. The mechanism is
  half-present already — `send_keys` paces at 0.06s *between* key
  events; what is missing is the pause before the *first* one.
  `stable=` is the wrong tool: it strengthens the observation
  (does the condition keep holding?) where the need is to pace the
  actor, it costs a poll interval plus its duration, it changes
  what the author is asserting, and it must be written on every
  wait — the burden being objected to.
  SETTLED IN THE 2026-07-24 QUESTION ROUND (owner):
  * **Scope: header > phase > statement**, the same lexical ladder
    `timeout` uses — innermost-wins, resolved at parse time,
    reported by `check-script`. A column in the placement matrix,
    not a second model.
  * **Applies to every guest-input verb** — `enter`, `type`,
    `press`, `select`. One invariant needing no context: before
    typing at an agentless guest, let it settle. Host-side verbs
    (`insert`, `eject`, `set-boot`, `screenshot`, `start`, `stop`,
    `set`, `http`) are not guest input and do not pay it.
  * **Default 0.1s for now, expected to be revisited.** The owner's
    note is the important part: this number will swing wildly — a
    plain text screen renders quickly, while the colourful
    exploding TUI menus render very slowly. So the default cannot
    serve every screen by construction, which is itself the
    argument for the per-phase and per-statement override carrying
    real weight rather than being speculative generality.
  * **The term is *pacing*** (owner, 2026-07-24, settling the one
    question the round left open). It is the spec's own word for
    this — Timing already says "input-event pacing remain[s]
    control-plane-owned" — so the language adopts a term the design
    already used rather than coining one, and the name says plainly
    which half of the model it belongs to: it paces the actor, it
    does not strengthen an observation. It collides with nothing.
    The rejected candidates are worth keeping: `settle` read best
    on meaning but sat a near-homophone away from `stable` in one
    small vocabulary, on the opposite half of the model — a real G6
    cost; `ready` reads naturally but collides with the resting
    machine phase.
    Residual nit for the implementing round, not a reopening:
    whether the token spells `pacing` or `pace` in both positions
    (`pacing 300ms` in a header, `press enter pacing=300ms` on a
    statement). Lean `pacing` for both — one spelling everywhere
    (G6), and a *pace* is naturally a rate while what is being set
    is an interval.
  ALSO UNMEASURED: no evidence yet fixes the number against the
  case that motivated it. What is known is that "immediately" is
  too little and "several seconds later" is enough; the interval
  that reliably lands a keystroke on that installer screen was
  never bisected. Worth doing when this is picked up — the rig is
  cheap to stand up now.
  When it lands: script-spec.md's Timing section is the normative
  home (the placement matrix, and the "there is no `delay`"
  paragraph amended to distinguish the absent *verb* from
  control-plane pacing), plus a D-number recording the
  interface-change triage. Triage as it stands: no use case is
  cost, several are served — an easy approval under the
  interface-change rule.

### Language

- residual language problems catalogued in
  planning/design/script-examples/*.rlqs (see its README) —
  best-guess priority, fix-cost order, NOT validated against
  real authoring pain; reorder freely once we've actually
  written/debugged scripts under this surface:
  1. [08] reserve the small closed vocabularies (key names,
     drive slots) globally so they can't shadow phase/artifact
     names — mechanical, no spec redesign, also closes most of
     [01]'s asymmetry
  2. [06]'s remaining half: warn when an `@`-reference matches no
     known item (the label/item split itself is gone with the
     media block — DECISIONS.md, no JSON in scripts)
  - [03], [05], [07] — provisionally leave as documented
    tradeoffs, not bugs: boundary tax (guest-text escaping) or
    placement-equals-scope consequences, where a "fix" mostly
    just relocates the mush rather than removing it
  - [01], [02], [04], [09] are resolved (DECISIONS.md: milestone
    zero and the observation-channel decisions); their files are
    regression notes
  - note: several of these are the procedural/declarative seam
    showing through the syntax — see "Primary language goals"
    (G1–G7) and "Procedural and declarative" in ./ROADMAP.md
    before proposing fixes, and judge any fix against the goals
    it costs rather than in isolation
- the full Reason-blockquote editorial sweep of script-spec.md
  remains deliberately open (may trail realignment); the
  error-id INDEX is deferred to beta
- resume the spec-audit workflow (wf_1a266a6b-ff8): the
  AHK/Python failure-catalog studies are complete — imports
  recorded in DECISIONS.md — but their spec audits hit the
  session limit

### U6 authoring recorder

Use case U6 in planning/USE-CASE-PROPOSALS.md (accepted,
awaiting delivery — moved 2026-07-23); design in
planning/design/recorder.md. Work items, in rough
dependency order:

- Reliquary-owned console viewer over the vnc control plane
  (recording prerequisite: backend display-window input is
  invisible to Reliquary)
- text-mode recorder first (no new language surface: waits from
  VGA scrapes, type/press actions, generated-comment
  uncertainty flags)
- runner run-to-point / breakpoint / human-takeover machinery
  (also the failure report's "take over from here" suggested
  next command)
- round-trip: fragment emission anchored by playback position;
  opt-in surgical apply at the anchor (never regenerate, never
  text-merge)
- landmark catalog shape: decided (DECISIONS.md, the wrinkle
  round; planning/design/landmarks.md) — implementation rides
  the asset spec work
- run-events: handover event kinds (script/human control
  passing); a capture session is one run record with mixed
  drivers
- CLI record command family + API twins land together (parity)

### Small items

Small, obvious, just haven't met the bar for scheduling (the
section formerly named Wishlist, then Backlog). Parked non-GitHub
issues land here. Most would qualify as housekeeping (D38) and
need no entry at all once someone picks them up.

- `download-media` command (owner request, 2026-07-22; shape to
  re-derive under the revised model — milestone 7's `add-media`
  covers its cache-warming half): `rlq download-media
  https://freedos.org/downloads/FreeDOS14.zip` downloads the file
  into `cache/media/`,
  computes its sha256, and scaffolds a standalone `.rlqb` into
  the home library carrying the url + sha256 — a media spec,
  with `children` left for the user to add when the payload is a
  container. A home-mode
  convenience: it warms the cache and writes the committed-source
  stub so the user need not hand-author it and then `fetch`. Open
  shape: members can't be
  inferred, so the stub stops at the container and the user adds
  the extraction tree (with `extract-media`); stem-default naming
  from
  the URL filename; a `--local <file>` variant for
  non-downloadable
  payloads (overlaps `add-media` — reconcile when picked up);
  CLI+API parity (a twin returning the written blueprint
  path).
- `extract-media` command (owner request, 2026-07-23; re-derive
  under the revised model) — the
  incremental companion to `download-media`: `rlq extract-media
  --parent FreeDOS14 FreeDOS14-LiveCD.zip` extracts the child
  from
  the named media,
  computes its sha256, and records it by
  **appending a child** (path + sha256) to the
  existing media spec's `children` (the leaning option)
  rather than writing a separate file — or as a flat
  `${media:…}`-located spec; reconcile when picked up. A child
  that is itself a
  container becomes another node to drill into (`extract` it
  again); a
  payload child is extracted to `cache/media/`. So
  a nested source is hand-authored by walking down it one
  `extract-media` at a time, the `children` tree growing
  in place. Open: new-file vs append-to-existing (lean append);
  node shape (child is itself a container → node with its own
  `children`, else leaf).
- new command diff-blueprint <name>: diff the user blueprint
  against the codex blueprint of the same name
- CLI, from cli help: --version should be `version` with an
  undocumented --version/-v alias; -h should be `help` with
  undocumented -h/--help aliases
- --qemu → --qemu-home
- CLI help: run-script's text says little more than "runs a
  script on a machine"
- an 'inventory' report: every item in the home and cache dirs
  itemized in one way or another (backend implementation files
  ignored — just the presence of a machine is noticed):
  - orphaned listed first (because either you *really* want to
    keep it, or you really *should* delete it): media
    (definitions, not cached payloads), scripts
  - blueprints: materialized (online machines, offline
    machines), unmaterialized
  - media: referenced
  - scripts: orphaned (listed first??), referenced
- README, blueprints and machines: give several clear examples
  to illustrate the concepts — e.g. a 1 MB MS-DOS blueprint;
  QEMU machine #0; QEMU machine #1; QEMU machine #3 with a
  specific floppy image mounted; QEMU machine #4 with 16 MB of
  memory and a specific cdrom mounted

## Completed

Done. Kept until each record is folded where it belongs and
pruned — which is itself an accepted task above.

### Milestone 8 — script properties (complete)

All five stages landed (T1–T5). This breakdown is kept until the
milestone-8 record is folded into the ROADMAP note and pruned like
milestones 4/6/7; the stage markers below are the landing record.

The sprint tasklist, translated from ROADMAP milestone 8. The
roadmap holds the *what* and
[script-properties.md](design/script-properties.md) the
normative detail; this holds the **landing order**, which is not
the deliverable numbering. Only the sequencing argument lives
here.

**What shapes this one:** nothing must land as one piece — the
milestone is new capability over a stub (`properties.py` today
is a JSON file with a `set_property(secret=)` parameter that
does nothing with it), so each stage is independently green.
What does bind the order is that two decisions are expensive to
retrofit: the **credential scope key** (the properties file's
absolute path) and the **rank of a source**. Both are cheap to
get right the first time and silently corrupting to change
later — an orphaned credential nobody can name, or a bundle that
resolves differently than it did last release.

- **T1 — the properties file — DONE.** Deliverable 1. Replace the JSON
  stub with the line-based format: `key = value`, `#` full-line
  comments, blank lines, the `@secret` marker and `@@` literal
  escape, dot-separated letter-initial segments with the `rlq` /
  `reliquary` namespaces refused, comment- and order-preserving
  surgical edits, atomic writes. Invalid files report path and
  line and are never partly rewritten. Pure host-side and fully
  unit-testable — no credential store, no binding. **Gate:** a
  file with comments, blank lines, and a deliberate ordering
  survives a set and an unset with everything but the named line
  untouched.
- **T2 — the credential store and the command family — DONE.**
  Deliverables 2 and 3, **plus `--properties <path>` pulled
  forward from deliverable 4**. Use the `keyring` package rather
  than hand-rolling Credential Manager / Keychain / Secret
  Service; its `(service, username)` model takes the spec's
  scoping directly — properties-file path as service, property
  name as username — behind a thin Reliquary-owned seam, so an
  absent or unusable store fails closed and there is never a
  plaintext fallback. The four commands with their secret rules
  (no-echo prompt on a tty, stdin to EOF otherwise, empty
  rejected; get and list never revealing; prefix filtering by
  dotted descendants, not string prefix; a kind change requiring
  `unset-property` first), the fail-safe update order
  (credential before marker, marker before credential) and
  orphan reporting. API twins in the same commit (P6), including
  the named divergence — `set_property` takes a secret's value
  in-process, because argv is what the CLI's entry channels
  exist to avoid. **Why `--properties` lands here and not in
  T4:** credentials scope by the selected file's absolute path,
  so the scoping rule is untestable without it, and changing a
  scope key after credentials exist orphans every one of them.
  **Gate:** the milestone's own — secrets round-trip with no
  secret material in the file, and an interrupted update can
  leave neither a plaintext value nor a marker whose credential
  was reported bound but is absent.
- **T3 — the binding pipeline — DONE.** Deliverable 4: the flattened
  order minus derivation — flag > parameter > env > file > ask.
  It lands where `script_runner.py` today raises "property
  binding arrives with the property family", and reaches
  preflight (every failure before a media materializes or a
  machine starts), `check-script` (each key's supplying source
  named, never its value), and the runtime secret rules
  (transcripts record key and source only; diagnostics redact;
  failure screenshots suppressed for the rest of a run after
  secret entry). Env mangling with the fail-closed collision
  preflight over the keys a run actually consults; blueprint
  `parameters` direct and redirect (`document.py` already parses
  both). **Gate:** one script bound from each tier in turn, each
  naming its source, and a noninteractive miss failing in
  preflight before the machine is created.
- **T4 — the declared derivation rank — DONE.** Deliverable 5 (D20).
  `default=` candidates in declaration order, first-answerable
  wins, with static cycle detection, dead literal candidates and
  any secret involvement as static errors, and the `rlq.*` facts
  (`host.username` login-normalized, `host.full-name`,
  `rlq.env.<NAME>`; an empty fact is unanswerable by design).
  The grammar already parses the modifier — this is semantics.
  Deliberately after T3: it is a one-rank insertion between file
  and ask, which is the model's own claim (D19 — new tiers land
  at fixed ranks) getting its first real test. **Gate:** a
  derivation-backed key binds with no ask, naming its winning
  candidate as the supplying source.
- **T5 — `${key}` location references — DONE.** Deliverable 6. The
  grammar landed at milestone 7 parsing-only, failing closed
  naming properties; now it binds through T3's order at `create`
  / `apply`, with the resolved location recorded in the state
  and never re-adopted at `start`, no chaining (a resolved value
  that is itself a reference fails closed), and noninteractive
  misses naming both the media and the key. Last because it is
  the only consumer outside scripts and wants the order settled
  under it. **Gate:** a media whose `location` is `${key}`
  materializes, with the resolved location in the machine state.

Cross-cutting, every stage: docs and CHANGELOG land with the
code (AGENTS "Documentation maintenance"), and
script-properties.md's status banner — *"None of it is
implemented yet"* — comes off as its sections land. A banner
that outlives the code it disclaims is the wrong-instruction
failure DECISIONS.md's preamble names.

### Milestone 9 — the programmatic testing loop (complete)

All seven stages landed (T1–T7). This breakdown is kept until the
milestone-9 record is folded into the ROADMAP note and pruned like
milestones 4/6/7; the stage markers below are the landing record.

The sprint tasklist, translated from ROADMAP milestone 9 as
reframed by D36 — the vertical's culmination: the programmatic
drive loop (U14/U20) plus live feedback for a watched install
(U12). Normative detail lives in script-spec.md and the U14/U20
entries (USE-CASE-PROPOSALS.md); this holds the **landing order**.

**What shapes this one:** the run model flips, and two behaviors
are unproven. The model flips from "rlq retains a record archive"
to "**rlq runs and returns output**" (D36) — the `runs/<n>/`
persistence, retention, and record verbs are deleted first, a
clean break (P9), so nothing is built against a model that is
leaving. And U20 rests on two unproven QEMU/DOS behaviors (live
floppy media-change, eject-flush); prove them before design rests
on them. The error taxonomy also folds milestone 8's debt — five
orphan classes (`PropertiesError`, `PropertyBindingError`,
`CredentialError`, `ScriptParseError`, `ScriptRuntimeError`) with
no common root and a CLI that collapses everything but a parse
error to exit 1.

- **T1 — Spike: prove the transports — DONE.** Before any code rests on
  them, confirm on QEMU/DOS: a live `insert-media`/`eject-media`
  floppy swap is *seen* by DOS (media-change detection), `eject`
  flushes guest writes to the local `.img`, and vvfat's
  stop/start flush holds (U14). **Gate:** a swap-run-swap cycle
  where DOS reads the new floppy's contents, and a guest-written
  file reads back host-side after eject. If either fails, U20 is
  reshaped here, not later.

  **Result: both hold, with one condition.** Run against an
  installed FreeDOS 1.4 on QEMU: a live `insert-media --file` swap
  is seen by DOS (a `DIR A:` after the swap lists the *new* image's
  files, never the previous disk's), and a guest write reaches the
  host `.img` — verified byte-wise after `eject-media`, and again
  after swapping back, each image carrying only its own rounds.
  U20 needs no reshaping. THE CONDITION: **a floppy drive's
  geometry is fixed when the backend attaches it at launch, and a
  live change does not revise it.** A slot launched empty gets
  QEMU's own default (2.88M), so inserting a 1.44M image into it
  live reaches the guest as "general failure" on every read and
  write. Reliquary did not choose that geometry, so it now records
  the launched medium's size and refuses a mismatched live insert
  naming both sizes and the fix (P11) — the spike's finding turned
  into a guard rather than a footnote.
- **T2 — The run model: return, don't store — DONE.** Delete `runs/<n>/`
  persistence (the `<timestamp>-<id>/` layout and the `output/`
  subdir die), stored `run-events.jsonl`/`transcript.txt`,
  retention, `list-runs`/`run status`/`run delete`, and
  interaction runs (`begin-run`/`end-run`). `run_script`/`exec`
  **return** their output directly; the `exec` API twin lands
  here (parity). **Gate:** a run returns its output with no
  `runs/` dir created; two concurrent runs return independently,
  no shared store.
- **T3 — Error taxonomy and exit codes — DONE.** `ReliquaryError` the
  root every deliberate error subclasses, `StaticError` (2) /
  `PreflightError` (3) / `RunFailure` (4) / `RunCancelled` (5)
  and their exit-code mapping, the milestone-8 classes folded
  under the root, the CLI's except-arms remapped from the
  everything-is-1 collapse, and the `--json` document contract.
  Ctrl-C on a foreground run emits `cancelled`, exit 5.
  **Gate:** the four classes exit 2/3/4/5, and
  `except ReliquaryError` catches all four.
- **T4 — Live feedback (P5) — DONE.** `--progress (auto | pretty |
  plain | jsonl)` rendered live during a run and **never
  stored**, jsonl stdout purity (terminal event last,
  diagnostics to stderr), the stdout/stderr discipline, and the
  noninteractive no-prompt rule (a missing input under
  `plain`/`jsonl` is a PREFLIGHT ERROR before the machine
  starts). Serves U12 (watch an install) and U9 (timely machine
  output). **Gate:** an install renders live in pretty; rerun
  under jsonl it emits the event stream to stdout, terminal event
  last, with zero bytes written to disk.
- **T5 — Machine variables and readiness — DONE.** A `set` script verb
  + `get-machine-var` query (a `machine.json` field, cleared on
  `start`, under the op lock) — the script→host scalar/signal
  channel. Readiness rides it: the consumer's ready script `set`s
  a var, `get-machine-var` polls; no Reliquary-provided default
  script (P18). **Gate:** a `set` var is readable by any process,
  cleared on start; a consumer ready script drives boot-to-ready
  with no Reliquary-side prompt knowledge.
- **T6 — In-band file put/get over vvfat (U14) — DONE.** Guest-terms
  addressing (P17) → vvfat hostdir mapping (P10-safe from the
  declared drive assignment), stopped-only, non-vvfat fails
  closed (P11). Put before start, get after stop. **Gate:**
  put/get a guest-addressed file to/from a vvfat drive; a
  non-vvfat target fails closed naming the gap.
- **T7 — `insert-media --file` (U20) — DONE.** `insert-media <slot>
  --file <path>` (twin `insert_media(slot, file=)`) mounting an
  anonymous `local`+`use` media (mutable, unverified, in place),
  live; the declared-media form stays. **Gate:** a freshly-built
  floppy `.img` mounts live by path, runs, ejects, and remounts
  with new content picked up.

Cross-cutting, every stage: CLI–API parity lands in the same
change (P6), and docs (README, `docs/api-reference.md`,
`docs/cli-reference.md`) and CHANGELOG land with the code
(AGENTS "Documentation maintenance").

Found while landing it, and fixed in passing:

- the codex `freedos-install.rlqs` pressed `enter` on the
  installer's first Yes/No menu, which the installer draws before it
  reads the keyboard — the keystroke was swallowed and the install
  timed out at the next wait. Reproduced on the pre-milestone tree,
  so it was not a milestone-9 regression. Now `select "Yes"`, as
  every other confirmation in that script already was: `select` is
  feedback-driven and verifies the highlight moved.
- the guest-console commands (`screen`, `type`, `enter`, `press`,
  `exec`, `select`, `wait`, `screenshot`, `hmp`) resolved a selected
  machine's QMP port but not its directory, so the identity check
  looked for the recorded VM under the home, found none, and refused
  every one of them as a mismatch. Found by the failure report's own
  suggested next command (`rlq screen --machine …`) not working.

### Design rounds resolved

- Media residency vs the download cache AND composable authored
  specs — RESOLVED together (owner, 2026-07-23, the media/composition
  design round), then REVISED same day by the blueprint revision
  round (both in DECISIONS.md; ROADMAP milestone 7 is the
  retargeted implementation): two spec types (machine / media —
  archive absorbed as the container reading), a flat typed root
  array, one schemed `location` field, no source component, no
  composition (identity-dedup instead), and the single name-keyed
  `cache/media/` with the identity ledger (content addressing
  declined in both rounds). blueprint-model.md is now the
  worked design of the revised model, rewritten at milestone 7's
  S1 and normative in the decision entries' place.
- Media lifecycle commands — RESOLVED (owner, 2026-07-23,
  DECISIONS.md D30, run as milestone 7's decide-first round):
  the noun in every media verb is the media, never the owning
  file; `delete-media` and `seed-media` are deleted outright
  (P9 — a command that can only fail and a no-op that "still
  resolves" are the shim the rule names); `list-media` keeps
  its plain name list with owning file, containment parent and
  cache state behind `--verbose`, a dedup'd media showing every
  declaring file on its one row, anonymous inline blanks never
  listed. Component-removal tooling is parked, arriving as its
  own named thing under the interface-change rule if a real
  case appears.

- CLI clean — RESOLVED by the blueprint revision round
  (DECISIONS.md, 2026-07-23): `clean-media` (blunt + targeted
  eviction) and `prune-media` (attachment-closure prune of
  unneeded entries) land at milestone 7; `clean-archives`
  retires with the single cache dir. Machine-cache cleaning
  remains the open decision in ROADMAP "Decisions still
  needed".

## Rejected

Refused work, indexed here and argued in
[DECISIONS.md](DECISIONS.md) — that file is already the guard
against re-litigating, so this section stays a pointer and never
restates the argument. Empty today: historic refusals
(`delete-media` and `seed-media` under D30, `clean-archives` with
the single cache dir) were recorded straight to DECISIONS.md
before this section existed, and are indexed with the design round
that made them.

## Watches (re-ask as these harden)

- live-run progress surface (G4 during the run — ties to
  run-events; the feedback split, PRINCIPLES.md P5, names
  the demand)
- GUI/landmark assets forming a new authored artifact class
  (hardened 2026-07-21: .rlql is the fourth authored extension —
  the INTERFACES listing is due at the asset-spec/realignment
  pass)
- published JSON Schemas elevating `reliquary-machine.json` into a
  public contract (the blueprint and media-definition schemas
  are authored — DECISIONS.md; the state schema and its
  public-contract elevation stay with milestone 6)
- the adapter API becoming world-facing
  (planning/design/backend-adapter.md is INTERNAL by decision,
  owner 2026-07-21 — a real third-party adapter story elevates
  it into the INTERFACES inventory through the interface-change
  rule, never by drift)
