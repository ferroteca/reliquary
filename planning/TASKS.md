<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# TASKS

The work backlog — and the parking place for non-GitHub issues
(the tracker:
<https://github.com/ferroteca/reliquary/issues>).

**This file is the third work input queue** (owner, 2026-07-26,
amending D39's two), and it works differently from the other two.
Work entered here is **small and pre-approved**: entering it is
approving it, so nothing waits on a verdict, and nothing here needs
a citation, a use case, or a decision of its own. It sits at the
planning root rather than under `proposed/` or `accepted/` for
exactly that reason — the lifecycle directories classify *demand
and capability*, which is argued before it is accepted, and this
queue is the work that skips the argument because it is too small
to need one.

**There is no order here.** Nothing in this file is scheduled, and
nothing claims priority over anything else; whoever picks work up
picks whatever they like. The one ordering that does bind is a
feature's: **work that only makes sense as part of one accepted
feature lives with that feature**, in
[accepted/FEATURES.md](accepted/FEATURES.md), and has to be done to
complete it — the U6 recorder's items are the standing example. A
task here that merely *relates* to a feature is still free to be
picked whenever.

Housekeeping (D38) is the same instinct one size smaller: work tiny
enough and obvious enough that it needs no entry here **at all**,
approved as a class in advance, with the commit as its record. This
file is where the pre-approved work that is still worth writing
down goes. The full intake machinery — the raw queues, the
housekeeping test, and how acceptance is recorded — is in
[README.md](README.md).

The sections below:

- **[Proposed](#proposed)** — the exception to everything above:
  work that was *argued rather than requested*, and is waiting on a
  verdict. Nothing may be worked from here. An entry earns its
  place by being too big or too contestable to pre-approve.
- **[Accepted](#accepted)** — the queue proper. Grouped by kind,
  because the actor and the gate differ, but the grouping is not a
  running order.
- **[Completed](#completed)** — done. Kept until its record is
  folded where it belongs and pruned.
- **[Rejected](#rejected)** — refused, with the reason recorded in
  [DECISIONS.md](DECISIONS.md), which is already the guard
  against re-litigating. The section here is a thin index pointing
  at those entries, never a second record of the argument.

Standing questions to re-ask as the design hardens are not tasks
and live with the decision record, under
[DECISIONS.md](DECISIONS.md)'s open questions.

## Proposed

Argued but not approved. Nothing is worked from here until it moves
to [Accepted](#accepted).

- **Audit design documents against accepted demand.** Raised
  unprompted during the 2026-07-24 traceability audit rather than
  requested, so it waits here. Findings that motivate it are
  recorded with the audit tasks under Governance in
  [Accepted](#accepted).

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
  * every planning section cites a U/P/G demand — *12 of 34 sections
    in the then-current roadmap cited none*;
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

- **The vision-utility audit — the reverse-citation check.**
  The traceability linter above verifies every *cited*
  identifier resolves; this is its mirror — every *defined*
  vision statement (a use case, principle, or interface) is
  cited or codified *somewhere*, or is surfaced as suspect. A
  statement nothing leans on is suspect of no utility:
  legislated but never used.
  DISCIPLINE — a look-list, not a kill-list. Finding the orphans
  is mechanical (a grep over the numbered handles); the verdict
  is a judgment the audit must not pre-empt. Each orphan earns
  one question — *guardrail or ballast?* — since a ceiling or
  closure cited only when pressure arrives is working, not idle.
  Principles get more rope than use cases: some cannot be
  codified and are legitimately hard to cite.
  DELIVERY — greppable by hand today; a monthly CI run is the
  richer eventual form. Per P22 (no CI, at this time),
  scheduling that run is itself the argued case for turning CI on
  when its day comes, not a breach of it.
  Proposed rather than accepted: raised 2026-07-25, a
  suggestion, not a request.

- **Generate the API reference from docstrings** (raised
  2026-07-26, the spec/descriptive round; owner asked for it to
  be filed with its argument). Adopt a documentation generator
  (pdoc / mkdocstrings / Sphinx autodoc) to produce
  docs/api-reference.md from the binding's docstrings.
  SCOPE, and it is the whole point: **plumbing for the
  descriptive layer, never a transfer of authority.** A generated
  reference is *mechanically* faithful to the binding — the tool
  reads the signatures, so reference-disagrees-with-code becomes
  impossible by construction, which automates the apology the
  reference's banner already makes. The norm of the surface stays
  [docs/spec/api.md](../docs/spec/api.md): code-as-norm would
  invert P8 — an unargued code change would *redefine* the
  interface rather than violate it — and the project has already
  lived the counterexample: the twin-name realignment settled
  names in the spec while the code still said
  `create_from_blueprint`, and the code was realigned to the doc.
  Parity alone cannot replace that direction: it binds shape, not
  semantics, and under twin-name identity the CLI's spellings
  derive from the API's names, so code-as-norm would put the
  guard downstream of the thing guarded. The multi-binding future
  sharpens it — two bindings mean two codes, and "the code is the
  norm" stops being well-formed; generation then rightly yields
  one descriptive reference *per binding*, all answering to the
  one spec.
  THE BAR TO CLEAR, before adopting even the plumbing: P21 binds
  infrastructure — the surface today is small enough that the
  hand-written reference is not obviously losing; without CI
  (P22) a generated document needs a local required check to
  regenerate, or it goes stale in a new way; and
  `test_documented_examples.py` executes fenced examples from the
  docs, so generated output must preserve that property or exit
  that test deliberately.
  Proposed rather than accepted: the owner agreed it needs to win
  this argument, not that it has.

## Accepted

Grouped by kind, because the actor and the gate differ: an
adjudication is the owner's alone, an audit is mechanical, a
restructure is citation-heavy and must run in order.

### Governance — adjudications

Owner-only: each settles a question the record is waiting on.
None depends on the others.

- **Accept and promote U9 and U12 — delivered work is standing on
  unaccepted demand.** Milestone 9's own text cites "live feedback
  for a watched install (U12, P5)", and the roadmap's "The run and its
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
  throughout DECISIONS.md and AGENTS.md, and P17/P18
  are drafted with milestone 9's code as evidence for both.
  WHY IT MATTERS, and it is not bookkeeping: **promotion is what
  arms a principle** (owner, 2026-07-24). Before it, an entry is
  accepted vision and a shortfall is unbuilt work; after it,
  ARCHITECTURE.md asserts the thing is true of the code, so a
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
  ARCHITECTURE.md's preamble says the list is standing-only and
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


- **Sweep planning items for demand citations** (owner,
  2026-07-23; audited 2026-07-24). Every item names the U- or
  P-number that demands it. Audit result: **12 of 34 sections cite
  no U/P/G at all.** Two are upstream of demand and need none
  ("Vision", "Design principles" — the latter being the source of
  P-numbers, and already tracked for itemizing into
  ARCHITECTURE.md). The rest divide: five completed milestones (1,
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
  and `blueprint-cookbook.md` (440 lines, examples —
  arguably exempt). Beyond citation, three designs exist for
  pillars whose demand was never accepted — `backend-adapter.md`,
  `guest-communication.md`, `landmarks.md`, all demoted by D33
  *for lack of use-case backing* after their designs were written.
  The restructure item below encodes the preventive rule (nothing
  gets a design doc until its demand is accepted); this is the
  retrospective pass over what predates it.

### Governance — restructures

**Executed 2026-07-26** (owner, interactively). The
four-step plan below ran as one pass, and the roadmap is gone. What
landed, and where it diverged from what step 2 decided:

1. ~~Split the unscheduled work into `planning/BACKLOG.md`~~ —
   **done**, as `planning/proposed/FEATURES.md` rather than
   BACKLOG.md: the lifecycle word beat the scheduling word, and the
   file sits in the folder that already means "not accepted".
2. ~~Restructure `planning/` around the lifecycle~~ — **done** as
   `proposed/` + `accepted/` + `design/`, landing as decided: the
   proposals files split across the two folders, and the governing
   files (`INTERFACES.md`, `DECISIONS.md`, `TASKS.md`) stayed at the
   planning root. Both took a wrong turn first and were corrected in
   the same pass, each correction found by the owner asking the
   right question. Filing the proposals whole under `proposed/` made
   "nothing is worked from proposed/" false, since P5, P14 and U1–U6
   are accepted; filing `DECISIONS.md` under `accepted/` put the
   *refusal* record — and the open questions — in a folder claiming
   the opposite. **The rule the second one yielded is worth keeping:
   the lifecycle folders are for artifacts that *move between them*.
   Machinery that never moves belongs at the root.**
   One thing is new rather than decided: `TASKS.md` is reframed as
   the third input queue (small, pre-approved, unordered), which
   widens D39's two and wants a D-number.
3. ~~Migrate delivered design out of ROADMAP~~ — **done**, first
   into `planning/design/` and then out again (step 5).
4. ~~Condense the completed milestone sections to notes~~ —
   **done**, and harder than the ~180 lines planned: milestones 1–9
   are one paragraph in [Completed](#completed). The
   demand-citation audit above had not run first, so what demanded
   milestones 1, 2, 3, 4 and 6 was **not** captured before the
   deliverable lists went. It survives in git history
   (`git show 50b67b2:planning/ROADMAP.md`) and must be recovered from
   there if that audit still wants it.
5. ~~Split the delivered specs out of `planning/`~~ — **done**, and
   this was the plan's sharpest finding: `planning/design/` was
   doing four jobs, and the largest was ~12 normative specs of
   *delivered* interfaces, which is current truth and does not
   belong under `planning/`. The decided remedy was a top-level
   `spec/`; **what landed is `docs/spec/`** (owner, 2026-07-26),
   because `docs/` already means the live situation, so the spec
   sits beside the reference that derives from it rather than in a
   third tree of its own. `docs/spec/README.md` states the
   normative direction: the spec binds the implementation, and a
   disagreement is the code's bug.
   Design was resolved along the same axis rather than being left
   as a residue: feature design moved beside its feature
   (`proposed/design/`, `accepted/design/`), and only design
   serving no single feature stayed in `planning/design/`.
   Machine-readable schemas moved into the package,
   `reliquary/schemas/`, since code consumes them — which also
   deleted two dead ones (`machine-blueprint.schema.json`,
   `media-definition.schema.json`): zero references anywhere, and
   both described the pre-composition format milestone 7 replaced,
   so they contradicted the shipped schema rather than duplicating
   it.
6. **PRINCIPLES.md became ARCHITECTURE.md** (owner, 2026-07-26):
   the root document is the architecture in force — the
   whole-system view (absorbed from the former
   `planning/design/architecture.md`) plus the P-numbered
   principles, matching the ARCHITECTURE.md convention readers
   expect at a repo root. The mirrors renamed with it
   (`proposed/ARCHITECTURE.md`, `accepted/ARCHITECTURE.md`),
   restoring mirror-by-name across all three ladders. The same
   pass itemized the model doc's unnumbered principles as
   P19–P21, and stated P22 (no CI, at this time) — a rule
   previously cited in this file but written down nowhere.
   The P-additions and the rename want D-numbers, with
   acceptance-is-the-move (amends D23) and the third queue
   (widens D39).

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
  design/script-examples/*.rlqs (see its README) —
  best-guess priority, fix-cost order, NOT validated against
  real authoring pain; reorder freely once we've actually
  written/debugged scripts under this surface:
  1. [08] reserve the small closed vocabularies (key names,
     drive slots) globally so they can't shadow phase/artifact
     names — mechanical, no spec redesign, also closes most of
     the asymmetry the deleted [01] showed
  2. [06]'s remaining half: warn when an `@`-reference matches no
     known item (the label/item split itself is gone with the
     media block — DECISIONS.md, no JSON in scripts)
  - [03], [07] — provisionally leave as documented
    tradeoffs, not bugs: boundary tax (guest-text escaping) or
    placement-equals-scope consequences, where a "fix" mostly
    just relocates the mush rather than removing it
  - [01], [02], [04], [05], [09] were resolved, and their files
    were **deleted 2026-07-26**: they claimed to be regression
    notes, but nothing in the tree executed them and [04] had
    silently drifted into invalid syntax. The resolutions are in
    DECISIONS.md, which is where they belong. ([05] sat in the
    tradeoff group above until this pass — the README had it
    resolved by D5 dropping the file-exchange verbs, and the
    README was right.)
  - [03] does not currently parse either: its `on` handler bodies
    end without a terminal. Fix it with whatever touches [03]
    next — it is a live example, so it should be valid where it
    is not deliberately illegal
  - note: several of these are the procedural/declarative seam
    showing through the syntax — see "Primary language goals"
    (G1–G7) and "The procedural–declarative seam" in design/script-spec.md
    before proposing fixes, and judge any fix against the goals
    it costs rather than in isolation
- the full Reason-blockquote editorial sweep of script-spec.md
  remains deliberately open (may trail realignment); the
  error-id INDEX is deferred to beta
- resume the spec-audit workflow (wf_1a266a6b-ff8): the
  AHK/Python failure-catalog studies are complete — imports
  recorded in DECISIONS.md — but their spec audits hit the
  session limit

### Small items

Small, obvious, just haven't met the bar for scheduling (the
section formerly named Wishlist, then Backlog). Parked non-GitHub
issues land here. Most would qualify as housekeeping (D38) and
need no entry at all once someone picks them up.

- **Audit the blueprint field reference for orphaned norms**
  (2026-07-26, from the spec/descriptive split). The blueprint's
  norm is now the published schema (structure) plus
  docs/spec/blueprint-model.md (semantics), and
  docs/blueprint-reference.md was demoted to descriptive.
  Walk its per-field contracts (units, controller vocabulary,
  boot semantics, materialize modes): anything load-bearing that
  neither the schema nor the model states gets promoted into one
  of them, so no rule is left normless.

- `download-media` command (owner request, 2026-07-22; shape to
  re-derive under the revised model. D41 settled the overlap
  below: `add-media` is the `--local` half already, so what is
  left here is the *download* half — fetch, hash, scaffold):
  `rlq download-media
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
  the URL filename; no `--local <file>` variant is needed —
  that is `add-media`, which D41 settled as exactly this
  command's local half (compute the hash, scaffold the spec,
  copy nothing), so the two should end up siblings sharing one
  scaffolder; CLI+API parity (a twin returning the written
  blueprint path, as `add_media` already does).
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

### The numbered arc — milestones 1–9 (complete)

**The numbered arc ran 1 through 9 and ended there**, carrying
text-mode DOS on QEMU from the north-star command to the
programmatic testing loop: the vertical slice and the built-in
blueprint bundle (1), the media library and caches (2), the
scripting language on its first, now-superseded surface (3), the
script-surface realignment to the July 2026 redesign (4), the local
HTTP server for installer answer files (5), the instance model and
machine blueprints with authored-asset residency (6), the composed
blueprint model folding the blueprint and media formats into one
(7), the script properties — user properties file, secret storage,
binding pipeline, declared derivation, `${key}` references (8), and
the programmatic testing loop — the run returning its output, live
feedback, the error taxonomy, and the exec-run mechanics (9).
Asynchronous runs left the arc for lack of a use case (D35/D36).

The per-milestone deliverable and stage breakdowns are **pruned**:
the record survives in git history, the CHANGELOG, and the D-numbers
each round produced, which is the standing rule for completed
breakdowns. Generalizing beyond that one vertical is unbuilt and
unscheduled (D33) — it lives in
[proposed/FEATURES.md](proposed/FEATURES.md), design settled and
intact, and returns to a numbered arc when the case it serves is
accepted.

### Design rounds resolved

- Media residency vs the download cache AND composable authored
  specs — RESOLVED together (owner, 2026-07-23, the media/composition
  design round), then REVISED same day by the blueprint revision
  round (both in DECISIONS.md; milestone 7 is the
  retargeted implementation): two spec types (machine / media —
  archive absorbed as the container reading), a flat typed root
  array, one schemed `location` field, no source component, no
  composition (identity-dedup instead), and the single name-keyed
  `cache/media/` (content addressing declined in both rounds; the
  identity ledger that round added was deleted by D41, which left
  the decline's ground unchanged). blueprint-model.md is now the
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
  remains the open decision in DECISIONS.md "Open questions" (was "Decisions still
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

