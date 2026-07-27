<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Use-case proposals

> **Status:** the staging ground for changes to the
> use-case list. **Nothing here is pledged, and nothing is worked
> from here.** A proposal is argued under the
> [interface-change rule](../INTERFACES.md#the-rule),
> and **the move is the pledge**: it goes to
> [pledged/USE-CASES.md](../pledged/USE-CASES.md), and the commit
> that moves it is the record. It reaches the current list —
> [USE-CASES.md](../../USE-CASES.md), which holds only the use cases
> the code meets today — when its delivery lands, a second move
> (D34, automatic on full delivery).

This document tracks proposed amendments to the
use-case list: new use cases being drafted, and proposed
retirements or supersessions of use cases in force. It exists
so the current list stays a stable statement of what is in
force while proposals churn here.

## The use-case lifecycle

A use case in force is never changed in nature. A *proposed*
one is different: until it enters force it may be reshaped
freely here — its number stays, and work already scheduled
against it (a pledged proposal) is re-checked in the same
edit. For the standing list, three moves exist, and they are
the only three:

- **Clarify.** An in-place wording edit that sharpens what the
  use case already meant — clarify, never change. The test: no
  past decision citing the use case would have come out
  differently under the new wording. A clarification needs no
  argument: it may land directly in root USE-CASES.md, or —
  undelivered — park here as an entry against its use case's
  number until it is applied. When it is arguable whether an
  edit is a clarification, it is not one — it is a supersession
  and is argued like any other proposal.
- **Add.** A new use case, drafted here, argued under the
  interface-change rule, pledged, and moved to
  root USE-CASES.md when its delivery lands.
- **Retire.** A use case leaves force: **retired** without
  replacement, or **superseded** by one or more successors that
  carry the need forward in a changed shape. A use case whose
  nature must change is superseded by new use cases, never
  edited.

## Numbering

Proposed and in-force use cases share one global namespace: a
proposal drafted here takes the next free U-number, keeps it
for life, and moves to root USE-CASES.md under that number
when its delivery lands. The move to
pledged/USE-CASES.md is the pledge — the argument wins, the
commit that moves it is the record, and the pledged proposal is
citable from there; delivery is what makes it current. The
door swings both ways: a settled use case whose delivery
becomes unscheduled moves back to pledged/USE-CASES.md and lives
only there until delivered. Numbers are never reused: a declined
proposal's number is retired with it (the decline recorded in
[DECISIONS.md](../DECISIONS.md), the guard against re-litigating),
and a superseded use case leaves the current list stubless —
DECISIONS.md records the retirement, and its successors name
the number they supersede — so every citation of it stays
resolvable.

## Removal and the planning sweep

A proposal that dies — declined in argument, or withdrawn or
lapsed without ever being implemented — is removed from this
document, and its removal triggers a sweep of the planning
docs: any downstream material predicated on it (a
planning/design/ document, a planning section,
TASKS entries) is removed or realigned in the same pass, per
the land-coherently rule (INTERFACES.md). The death is
recorded in DECISIONS.md with its reason, so it is not
re-proposed blindly. Nothing downstream may keep citing a
use case that never entered force. The sweep is findable by
construction: every pledged item cites the use case or
principle that demands it (the traceability rule in the planning docs'
preamble), so the dead proposal's U-number is the search key.

## Open proposals

Each proposal records what it proposes (add / retire /
supersede / clarify), the use cases it touches, and its state:
**tracked** (a change expected but not yet drafted — no number
claimed) and **drafted** (full use-case text, number claimed).
Those are the two states this file holds. Beyond them a use case
is **pledged** — moved to
[pledged/USE-CASES.md](../pledged/USE-CASES.md), the move itself
the record — and then **delivered**, moved again to the current
list; a chunk whose demanded work has already landed is pledged
and delivered in one act. A proposal may die at any point before
delivery (recorded in DECISIONS.md and removed, triggering the
sweep above).

Delivery moves it **automatically** (D34): whoever lands the work
that fully meets a use case promotes it in the same change — into
the current list, out of the pledged file, recorded in
DECISIONS.md — not on a separate sign-off. Full delivery is the
trigger: a use case whose work has partly landed stays pledged
rather than current (milestone 8 pledged U5, but its canonical
scenario waits on the GUI era, F5). A clarification claims no number of
its own — it attaches to the use case it sharpens — and skips the
argument entirely: it is simply delivered, applied in place to the
current list and removed here.

### Drafted

Two 2026-07-23 sweeps. The mapping sweep (U7–U10) closes
named coverage gaps — roadmap work standing on demand no use
case writes down. The decomposition sweep (U11–U17) executes
the owner's directive: break the dense cases into much
smaller chunks where possible. **U9 and the U11–U13 chunk trio
left in force** (D46, 2026-07-27): all four were delivered
already, so the pledge and the promotion ran as one act and no
stub stays behind — which is why both sweep ranges now read
with holes in them. The calibrating example
(owner): "a user at the keyboard should be able to easily
find a codex blueprint, for example for freedos or openbsd,
with minimal effort, and seed it into their library." People
read these, so each must be succinct, digestible, and
justified. Draft text is in the current list's exact bullet
form, ready to move verbatim on delivery.

**U7 — Materialize on the hypervisor the host provides** —
drafted (add, 2026-07-23). The gap: the backend-adapter
pillar — the adapter seam, the second backend, and the GUI
era's remaining backends — has no use-case demand; VirtualBox,
VMware, and Hyper-V appear in the current list only as export
targets (U1), import sources (U2), and guest-agent vendors
(U3), never as run substrates. The seam and the second backend
left the numbered arc for the backlog on this very lack, the
same day this draft was written (formerly milestones 10–11;
D33). Pledging U7 is scheduling that pair back onto the arc,
the citing item the pledge record; on pledging the
the backend-adapter design and both returning features
cite U7.

> - **U7 — Materialize on the hypervisor the host provides.** A
>   blueprint and its scripts are written once; the hosts that
>   run them differ — a Windows laptop with Hyper-V already
>   enabled, a CI runner with only QEMU, a workstation with
>   VirtualBox. The machine materializes on whatever capable
>   backend the host offers, and the same blueprint and scripts
>   drive it there unchanged. Capability, not identity, is the
>   contract: a blueprint needing what a backend cannot give
>   fails closed naming the gap, never silently degrading;
>   declaring a `backend` explicitly is the exception, for when
>   the choice is the point. Without this, U4's journey breaks
>   at the second developer's host: a precisely shared
>   definition only helps if the machine can be built where
>   that developer is.

**U8 — Keep what was built** — drafted (add, 2026-07-23). The
gap: the export family — machine mobility, demoted from
milestone 12 to Horizon for this very lack — hangs from half a
sentence inside U1; the durable-exit concern deserves its own
case (separation: U1 stays the easy-install journey, U2 the
import journey, U8 the export journey). On pledge, U1
gains a cross-reference clarification pointing at U8 (its
nature — ending in a usable, exportable machine — is
untouched); pledging U8 is scheduling the mobility work's
export half back onto the arc, the citing item the record.

> - **U8 — Keep what was built.** Sometimes the product is the
>   machine after all: the sandbox worth keeping (U1), the
>   built rig worth handing on. The user exports it and
>   Reliquary lets go — a whole machine registered with a
>   hypervisor built for keeping machines, bootable under that
>   platform's own tooling, or a single disk image taken out as
>   a standalone file. The export stands alone — media copied
>   in, nothing referencing Reliquary's home or caches — and
>   Reliquary never touches it again. This preserves the
>   ephemeral-machine principle rather than bending it: the
>   Reliquary machine stays disposable precisely because the
>   durable exit exists.

**U10 — The install is the thing under test** — drafted (add,
2026-07-23). The gap: the control-plane arc's prose already
names install-testing ("os-autoinst-style, where the install
is the thing under test") but no numbered case owns it — and
it is the use that makes agentless operation permanently
essential rather than a bootstrap convenience. On pledge,
the arc's prose cites U10, as do the agentless-permanence
statements.

> - **U10 — The install is the thing under test.** An installer
>   or media maintainer runs an install to prove the install:
>   the screen is the assertion surface, the run record is the
>   verdict, and the machine is discarded. Agentless operation
>   is essential here, not a fallback — until the install
>   succeeds there is nothing in the guest to cooperate, and
>   the moments before an agent could exist are exactly the
>   ones under test. The same script observes a changed
>   installer honestly, failing with the screen it actually
>   saw.

**U16 + U17 — split U4** — drafted (supersede U4, 2026-07-23,
the decomposition sweep). U4 bundled the sharing journey with
the residency rule; the residency rule is already the
artifact-residency split's automation half — U17 numbers it so
decisions can cite it directly, and the split's prose
condenses to cite U16/U17 on pledge. When both are
delivered, U4 retires to a stub naming them.

> - **U16 — Share a precise test VM through version control.**
>   A program must be tested in a VM — perhaps a proprietary
>   OS — and the repository can carry only definitions:
>   blueprints and scripts, their hashes pinning the exact
>   media they target. Another developer supplies the two
>   things the repo cannot — the install media and its
>   license — and builds the same rig, verified. The rig is
>   somewhat expensive, so it is kept for the work cycle and
>   disposed when the work ends.

> - **U17 — Project artifacts work in place.** For automation,
>   blueprints, scripts, and their assets are source code: they
>   live in the consuming project's tree, under its source
>   control, and run from there — nothing is copied into a
>   Reliquary home to make them usable, and nothing outside the
>   project's tree reaches an automated run. The home stays
>   Reliquary's own ground: caches, machines, the personal
>   properties file.

**U18 — Test on the platform the host isn't** — drafted (add,
2026-07-23; owner's, from the observation that Reliquary's own
credential-store code has a Linux path its Windows developer
cannot execute). The gap: every case in the list treats the
guest as the subject or the product; none treats it as **the
missing platform** a developer needs in order to test their own
work. It is distinct from U3 (something is tested *in* a VM,
platform incidental) and from U16 (a rig shared between
developers): here the guest's *identity as a different OS* is
the entire point, and the "somebody else's machine" it replaces
is a CI matrix nobody has locally.

SEQUENCING, and the owner's own caveat — this needs a maturity
the project does not have: a modern-guest platform workflow
(Linux), a way in for the code and out for the results, and
realistically a native guest agent for a tight loop. So it is
not a near-term schedule request. What makes it worth numbering
now is what it would *demand* if pledged: it is the first case
that would put in-force weight behind the backlogged guest-agent
work (D33 demoted it for lack of exactly this), behind the
deferred in-band file operations, and behind **P16** and
**P17** — a developer driving a Linux guest from Windows cannot
reach around Reliquary to a `hostdir`, and would name that
guest's files in the guest's own terms. Reliquary self-hosting
its own cross-platform tests is the motivating instance; the
case is general.

> - **U18 — Test on the platform the host isn't.** A developer's
>   code has paths that only run on an operating system they are
>   not sitting in front of. They describe that system as a
>   blueprint, put the code and its test runner inside, run it,
>   and read the results back — on their own machine, with no CI
>   round trip and no second computer. The guest is not the
>   product and not the subject: it is the platform the work
>   needs and the host cannot provide. What makes it useful is
>   fidelity — a real OS, not an emulated API surface — and the
>   loop being tight enough to use while actually working.

**U19 — Start a long run and follow it from elsewhere** —
drafted (add, 2026-07-24; the async-deferral round, D35). The
gap: the asynchronous-run pillar — `run-script --detach`, the
cross-process followers (`run tail` / `run wait` / `run cancel`),
and the API async handles (`start_script` / `attach_run` /
`start_fetch`) — shapes real design but hangs from a gloss on U1
("leaves an hour-long install and checks back") that U1's own
text never makes, and from U14's "observes results," which a
synchronous jsonl stream already satisfies. Milestone 9's
records core delivers the live stream and its renderings to the
run's own driver (P5); following a run from a process that did
not start it is the separable capability U19 names. The pillar
left the numbered arc for the backlog the day this was drafted
(D35), on the same ground D33 used for the backend pillars — a
settled design with no in-force or pledged use case. Pledging
U19 is scheduling the async work back onto the arc, the citing
item the pledge record; on pledging the planning
"Asynchronous runs (backlog)" section and the returning
milestone cite U19.

> - **U19 — Start a long run and follow it from elsewhere.** A
>   run takes an hour, and the person or program that started it
>   does not wait at the terminal that launched it: they detach
>   it, or start it in one place and follow it from another — a
>   second terminal, a later session, a different process —
>   watching the same live stream and reading the same outcome
>   the driver would have seen. The run is not its terminal's
>   captive: the machine, not the invoking process, owns it, and
>   a follower attaches to its record while it runs and detaches
>   without disturbing it.

### Pending clarifications

Parked in-place edits — no argument needed, delivered when
applied; each must pass the clarification test (no past
citation reads differently under the new wording).

- **U1 — condense to the journey** (recorded 2026-07-23;
  **contingent on U8 alone** since D46, 2026-07-27). Tighten
  U1 to the composed journey it uniquely owns — one short,
  terse command from a clean home to a usable machine,
  easy-is-the-requirement included — citing U11 (find and
  seed), U13 (media), U12 (the install), and U8 (the export
  exit) for the capabilities it composes. Three of the four
  are now in force; U8 is the last, and until it is pledged
  U1's export clause stays load-bearing text rather than a
  citation.
- **U2 — condense** (recorded 2026-07-23). Trim the import
  doctrine detail — never-copy, snapshot consent, and the
  duplicate/difference choice are settled in the dissolved roadmap's import
  design and DECISIONS.md — down to the demand itself: capture
  a native VM as a blueprint, source at rest and untouched,
  the two decision points presented, never defaulted.

### Tracked

- **Break U5 into finer pieces** — tracked (recorded
  2026-07-23, the decomposition sweep; U5 itself is pledged
  above, awaiting delivery). Candidate cuts: the
  seed-and-customize journey; parameterization's two bindings
  (in-blueprint values vs externally defined); secret custody
  (never in source control). Cut when U5 approaches delivery
  or an argument needs the finer citation.
- **Break U6 into finer use cases** — tracked (recorded
  2026-07-23; previously an expectation noted inside U6
  itself). Candidate cuts per the recorder design
  ([planning/pledged/design/recorder.md](../pledged/design/recorder.md)): record
  a task once into a draft script; extend a tailored script by
  round-trip re-recording; refresh assets for a changed
  screen. Left undrafted by the decomposition sweep: the
  recorder is Horizon work, and premature cuts risk being the
  wrong ones.
