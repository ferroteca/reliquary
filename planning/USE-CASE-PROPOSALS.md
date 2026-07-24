<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Use-case proposals

> **Status:** the staging ground for changes to the
> use-case list. Nothing here is delivered: the current list —
> [USE-CASES.md](../USE-CASES.md) — holds only the use
> cases the code meets today. A proposal is argued
> under the
> [interface-change rule](INTERFACES.md#the-interface-change-rule);
> scheduling in the roadmap **is** acceptance — a proposal is
> accepted when the roadmap schedules the work its use case
> demands, the citing roadmap item the acceptance record — and
> it moves to the current list when its delivery lands.

This document tracks proposed amendments to the
use-case list: new use cases being drafted, and proposed
retirements or supersessions of use cases in force. It exists
so the current list stays a stable statement of what is in
force while proposals churn here.

## The use-case lifecycle

A use case in force is never changed in nature. A *proposed*
one is different: until it enters force it may be reshaped
freely here — its number stays, and work already scheduled
against it (an accepted proposal) is re-checked in the same
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
  interface-change rule, accepted, and moved to
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
when its delivery lands. Scheduling in the roadmap is
acceptance: the argument wins by the roadmap taking the work,
the citing item the record, and the accepted proposal is
citable from there; delivery is what makes it current. The
door swings both ways: a settled use case whose delivery
becomes unscheduled moves back here as accepted and lives only
here until delivered. Numbers are never reused: a declined
proposal's number is retired with it (the decline recorded in
[DECISIONS.md](DECISIONS.md), the guard against re-litigating),
and a superseded use case leaves the current list stubless —
DECISIONS.md records the retirement, and its successors name
the number they supersede — so every citation of it stays
resolvable.

## Removal and the planning sweep

A proposal that dies — declined in argument, or withdrawn or
lapsed without ever being implemented — is removed from this
document, and its removal triggers a sweep of the planning
docs: any downstream material predicated on it (a
planning/design/ document, ROADMAP sections or milestones,
TASKS entries) is removed or realigned in the same pass, per
the land-coherently rule (INTERFACES.md). The death is
recorded in DECISIONS.md with its reason, so it is not
re-proposed blindly. Nothing downstream may keep citing a
use case that never entered force. The sweep is findable by
construction: every roadmap item cites the use case or
principle that demands it (the traceability rule in ROADMAP's
preamble), so the dead proposal's U-number is the search key.

## Open proposals

Each proposal records what it proposes (add / retire /
supersede / clarify), the use cases it touches, and its state:
**tracked** (a change expected but not yet drafted — no number
claimed), **drafted** (full use-case text, number claimed),
then **accepted** (its work scheduled in the roadmap, the
citing item the record; a chunk whose demanded work has
already landed is accepted and delivered in one act), then
**delivered** (moved to
the current list) — or dead at any point before delivery
(recorded in DECISIONS.md and removed here, triggering the
sweep above). A
clarification claims no number of its own — it attaches to the
use case it sharpens — and skips the argument: it is simply
delivered, applied in place to the current list and removed
here.

### Accepted — awaiting delivery

**U1 — Install a sandbox VM from the CLI, easily** — accepted;
moved from the current list 2026-07-23 (owner: the current
list is implemented-only). The install journey is delivered
end to end — the north-star command works from a clean home —
but the export clause is unimplemented Horizon work (machine
mobility), so U1 as written is not met. The delivered
substance is separately drafted as chunks U11–U13: accepting
those already-delivered chunks seats it in the current list at
once, and the pending U1 condensation completes the story when
export schedules. Text verbatim as adopted:

> - **U1 — Install a sandbox VM from the CLI, easily.** A user
>   says, in effect, "I'd like to install FreeBSD" — and ends with
>   a usable sandbox machine, installed unattended from standard
>   vendor media, exportable to a hypervisor built for keeping
>   machines (e.g. VirtualBox) to take away and use. Easy is the
>   requirement: the command-line syntax stays terse and succinct,
>   and the blueprint and install recipe are easy to find, point
>   to, and use. From a clean home this is one short command
>   (`rlq run-script install --blueprint freedos`): the
>   codex seeds the blueprint (its media included) and scripts;
>   media is fetched and hash-verified; the script drives
>   the installer end to end — menus, partitioning, reboots, media
>   swaps — until the guest is installed.

**U2 — Import an existing VM as a blueprint** — settled as
adopted; unscheduled since machine mobility's demotion to
Horizon (2026-07-23) took `import-vm` off the numbered arc,
and nothing of it is implemented. Rescheduling import-bearing
work is its re-acceptance. Text verbatim as adopted:

> - **U2 — Import an existing VM as a blueprint.** A user has
>   created a VM natively — in VMware, say — and wants to capture
>   it as a Reliquary blueprint (`import` synthesizes the
>   blueprint; realizing it afterward is an ordinary `create`).
>   Import reads only a source at rest — a running or suspended
>   source VM fails closed naming its state — and the captured
>   disk image stays where the native hypervisor keeps it: import
>   points a generated `media` component — a `local` source
>   inside the blueprint — at it and never copies, moves, or
>   modifies it; a user who wants the image somewhere more durable
>   moves it and repoints that media, which is theirs. Two decision points are presented, never defaulted.
>   First, whether to take a native snapshot — the one thing
>   import may do to the source VM, and only with this consent:
>   snapshotted, the blueprint pins the frozen extent and the
>   source VM stays free to keep running natively; declined,
>   nothing touches the source, but running it again breaks
>   verification until re-import. Second, how machines materialize
>   from the captured disk: each created machine a full copy of it
>   (`duplicate` — the machine's drive stands alone afterward) or
>   a differencing disk backed by it (`difference` — the cheapest
>   create, but the source must stay byte-identical, and
>   verification refuses a machine whose source has since been
>   rewritten). The import flow's job is to present these choices,
>   not bury them.

**U3 — Automated testing of something in a VM** — accepted;
moved from the current list 2026-07-23 (owner:
implemented-only). The programmatic loop itself runs
agentlessly on QEMU/DOS today, but the first-class demands —
granular results, selective re-run — ride milestone 8's
properties and milestone 9's run records and interaction runs.
The preferred guest-agent plane left the numbered arc for the
backlog 2026-07-23 (D33) — a preference this case states, not
a demand it makes: the loop runs agentlessly today, and the
demands that gate delivery are 8's and 9's. The split
superseding it (U14 + U15) is drafted below. Text verbatim as
adopted:

> - **U3 — Automated testing of something in a VM.** An agent — a
>   test harness, a CI driver, an AI coding agent — starts a
>   machine, injects a program, executes it, and observes the
>   result; possibly iterates (adjust, re-inject, observe again);
>   finally closes the VM. The loop is driven programmatically,
>   through a native binding or the CLI; computation and result
>   interpretation stay on the agent's side of the seam, and
>   Reliquary stays ignorant of who builds on it. The canonical
>   journey uses Reliquary twice: first to define and build the
>   test VM (U4), then again to automate the testing inside it.
>   Concretely: a unit-test suite runs in the guest while the
>   host-side automator captures detailed per-test results,
>   possibly updates a test object, and re-runs a specific test or
>   the entire suite — a tight edit-and-rerun loop, so granular
>   results and selective re-run are first-class demands, not
>   conveniences. This case is
>   probably best served by a native guest-side agent (QGA, VMware
>   Tools, Guest Additions, Hyper-V's integration services) — fast
>   injection, execution, and observation as a structured control
>   plane — while agentless operation remains the permanent
>   fallback for
>   guests that cannot cooperate, because the thing under test may
>   be the very driver that would provide that communication.
>   Often nothing durable remains: the run record is the product.

**U5 — Custom installation** — accepted; moved back from the
current list 2026-07-23 (owner: an in-force use case whose
delivery is unscheduled is a real problem — proposed is the
honest state). Its canonical scenario — a customized Windows
install — waits on the unscheduled GUI era; the
parameterization machinery lands at milestone 8 — the
scheduled, U5-citing work that constitutes its acceptance,
while the unscheduled scenario is why it is not current. U5
lives only
here while undelivered — the shared U-namespace keeps every
existing citation valid — and returns to the current list when
the delivery is real. Text verbatim as adopted:

> - **U5 — Custom installation.** A user wants the German version
>   of Windows. The codex will not carry such flavors —
>   there are too many variants — so it defines one standard
>   Windows install. From the CLI the user easily finds that
>   standard blueprint, seeds a local blueprint from it, and
>   customizes it. The blueprint's author has foreseen this need
>   and wrote it with an obvious locale seam; the user changes the
>   language to German — preferably in the blueprint, outside the
>   script, so the script can stand alone — and proceeds. A user
>   name and a license key are equally obvious examples of
>   blueprint parameterization — and they show its two bindings:
>   some parameters are specified directly in the blueprint, while
>   others are only *referred to* there and must be defined
>   externally. A license key is never checked into source
>   control, so Reliquary must provide a mechanism to store it
>   locally and retrieve it at use. The same parameter can go
>   either way: an automated-testing blueprint may fix its user
>   name as "testuser", while "paul" is a value its owner would
>   never check in.

**U6 — Author a script by doing the task once** — accepted in
residue only; moved back from the current list 2026-07-23
(owner, confirming the delivery-gate flag): the recorder —
U6's whole delivery — sits unscheduled in ROADMAP's Horizon,
so U6 is not current. Its one scheduled thread is milestone
9's reserved run-event handover kinds, which keep the
recorder's shape growable from the interaction-run bracket.
U6 lives only here while undelivered — the shared U-namespace
keeps every existing citation valid — and returns to the
current list when recorder delivery is scheduled and lands.
Text verbatim as adopted:

> - **U6 — Author a script by doing the task once.** A user
>   performs the task by hand — going through a Windows install,
>   say — in a console session Reliquary supervises, and ends with
>   a draft script and the image assets (landmarks) to reproduce
>   it. Reliquary follows the session — every keystroke, click,
>   and media swap, and the screen states between them — and
>   drafts the wait conditions and actions, capturing the source
>   screenshots landmarks crop from. The output is a *draft*:
>   ordinary script text beside the landmark declarations and
>   renderings it references — separate authored files, since a
>   script carries no embedded assets (amended 2026-07-22; see
>   planning/DECISIONS.md) — owned
>   and edited like anything hand-written — recording cannot know
>   which screen features are load-bearing or how long a step may
>   honestly take, so the person tailors what Reliquary proposes.
>   Tailoring is not a one-way exit: authoring round-trips. When
>   the task changes or coverage grows, a later session captures
>   the new screens and steps *against the tailored script* —
>   playback carries the machine to the point of change, the
>   person takes over and demonstrates, and Reliquary proposes
>   the new fragment and assets without disturbing what the
>   author wrote. A changed screen for an unchanged step is an
>   asset refresh — a new landmark variant in the catalog — and
>   touches the script not at all. The session machine is as
>   disposable as any other; the script and assets are the
>   product. (The authoring parallel to U2: import captures a
>   machine built by hand; recording captures a procedure
>   performed by hand.)

### Drafted

Two 2026-07-23 sweeps. The mapping sweep (U7–U10) closes
named coverage gaps — roadmap work standing on demand no use
case writes down. The decomposition sweep (U11–U17) executes
the owner's directive: break the dense cases into much
smaller chunks where possible — the calibrating example
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
D33). Accepting U7 is scheduling that pair back onto the arc,
the citing item the acceptance record; on acceptance the
ROADMAP backend-adapter section and both returning milestones
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
import journey, U8 the export journey). On acceptance, U1
gains a cross-reference clarification pointing at U8 (its
nature — ending in a usable, exportable machine — is
untouched); accepting U8 is scheduling the mobility work's
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

**U9 — Automate from a language without a binding** — drafted
(add, 2026-07-23). The gap: the multi-language binding
expectation and the CLI-as-universal-binding role shape real
decisions (pull-only handles, no callbacks, the four machine
surfaces) yet hang from one clause inside U3. Alternative
weighed: leave this as INTERFACES doctrine only — drafted
anyway because the parity invariant deserves demand-side
backing the interface-change rule can weigh against. On
adoption, the CLI programmatic contract and parity items cite
U9. Owner direction (2026-07-23): addressed as a use case
only, NO roadmap item — the CLI fallback carries unbound
languages until a second binding earns scheduling on its own.

> - **U9 — Automate from a language without a binding.** A
>   consuming project's harness is Java, C#, Go, or shell — no
>   Python, no native Reliquary binding. It still gets
>   everything through the CLI: every capability invocable,
>   observable, and parseable from a program — results on
>   stdout, diagnostics on stderr, exit codes by class,
>   machine-readable output as timely as the pretty rendering,
>   and no hidden prompt ever hanging a pipeline. A native
>   binding, where one exists for the language, is the same
>   surface with types; nothing is CLI-only or binding-only.

**U10 — The install is the thing under test** — drafted (add,
2026-07-23). The gap: the control-plane arc's prose already
names install-testing ("os-autoinst-style, where the install
is the thing under test") but no numbered case owns it — and
it is the use that makes agentless operation permanently
essential rather than a bootstrap convenience. On acceptance,
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

**U11 + U12 + U13 — chunk U1** — drafted (add, 2026-07-23,
the decomposition sweep). U1 bundles three separately
demandable capabilities with its journey; the chunks are
additive — U1 itself stays as the composed one-command
journey, condensed by the pending clarification below to cite
them. Each chunk is what a decision would actually cite:
discovery work cites U11, script-runtime work U12,
acquisition work U13.

> - **U11 — Find and seed a codex blueprint, easily.** A user
>   at the keyboard wants a starting point — freedos,
>   openbsd — and finds it with minimal effort: search or list
>   the codex, read a description, seed the blueprint (its
>   media and scripts included) into their own library as
>   ordinary files they own from then on.

> - **U12 — An unattended install, end to end.** From standard
>   vendor media, a script drives the installer the whole way —
>   menus, partitioning, reboots, media swaps — with no hand on
>   the keyboard, ending in a usable machine. A run this long
>   shows where it is and what it is waiting for while it goes.

> - **U13 — Media fetches and verifies itself.** A blueprint
>   names its media and pins it by hash; Reliquary acquires
>   it — download, extract, cache — and verifies it is exactly
>   the build the scripts target. The user never hand-places a
>   file in Reliquary's caches, and a wrong or changed payload
>   fails closed by name.

**U14 + U15 — split U3** — drafted (supersede U3, 2026-07-23,
the decomposition sweep; fulfills the tracked U3 break-out).
U3 bundled two journeys that shape different work: the
programmatic loop (the embedding surface, interaction runs)
and the test-iteration journey (granular results, selective
re-run). The control-plane preference U3 carried — agent when
present, agentless the permanent fallback — is the
cross-cutting arc's prose and stays there, re-cited on
acceptance. When both are delivered, U3 retires to a stub
naming them.

> - **U14 — Drive a machine from a program.** An agent — a test
>   harness, a CI driver, an AI coding agent — creates or
>   starts a machine, injects input, executes work, observes
>   results, iterates, and closes it, through a native binding
>   or the CLI. Reliquary supplies the loop's mechanics and
>   stays ignorant of its meaning: computation and
>   interpretation live on the caller's side of the seam. Often
>   nothing durable remains — the run record is the product.

> - **U15 — Rerun tests in a guest, tightly.** A test suite
>   runs in the guest while the host-side automator captures
>   per-test results, adjusts something, and reruns one test or
>   the whole suite. The loop is tight, so granular results and
>   selective re-run are first-class demands — served through
>   the caller's own artifacts and selection inputs, never a
>   Reliquary test vocabulary. The canonical journey uses
>   Reliquary twice: build the rig (U16), then automate the
>   testing inside it.

**U16 + U17 — split U4** — drafted (supersede U4, 2026-07-23,
the decomposition sweep). U4 bundled the sharing journey with
the residency rule; the residency rule is already the
artifact-residency split's automation half — U17 numbers it so
decisions can cite it directly, and the split's prose
condenses to cite U16/U17 on acceptance. When both are
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
now is what it would *demand* if accepted: it is the first case
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

### Pending clarifications

Parked in-place edits — no argument needed, delivered when
applied; each must pass the clarification test (no past
citation reads differently under the new wording).

- **U1 — condense to the journey** (recorded 2026-07-23;
  contingent on U8 and U11–U13 being accepted). Tighten U1 to
  the composed journey it uniquely owns — one short, terse
  command from a clean home to a usable machine,
  easy-is-the-requirement included — citing U11 (find and
  seed), U13 (media), U12 (the install), and U8 (the export
  exit) for the capabilities it composes. Until those are
  accepted, U1's full text stays: every clause is load-bearing
  demand.
- **U2 — condense** (recorded 2026-07-23). Trim the import
  doctrine detail — never-copy, snapshot consent, and the
  duplicate/difference choice are settled in ROADMAP's import
  design and DECISIONS.md — down to the demand itself: capture
  a native VM as a blueprint, source at rest and untouched,
  the two decision points presented, never defaulted.

### Tracked

- **Break U5 into finer pieces** — tracked (recorded
  2026-07-23, the decomposition sweep; U5 itself is accepted
  above, awaiting delivery). Candidate cuts: the
  seed-and-customize journey; parameterization's two bindings
  (in-blueprint values vs externally defined); secret custody
  (never in source control). Cut when U5 approaches delivery
  or an argument needs the finer citation.
- **Break U6 into finer use cases** — tracked (recorded
  2026-07-23; previously an expectation noted inside U6
  itself). Candidate cuts per the recorder design
  ([planning/design/recorder.md](design/recorder.md)): record
  a task once into a draft script; extend a tailored script by
  round-trip re-recording; refresh assets for a changed
  screen. Left undrafted by the decomposition sweep: the
  recorder is Horizon work, and premature cuts risk being the
  wrong ones.
