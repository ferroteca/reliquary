<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Use-case proposals

> **Status:** the staging ground for changes to the
> use-case list. **Nothing here is pledged, and nothing is worked
> from here.** A proposal is argued under the
> [surface-change rule](../SURFACES.md#the-rule),
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
  surface-change rule, pledged, and moved to
  root USE-CASES.md when its delivery lands.
- **Retire.** A use case leaves force: **retired** without
  replacement, or **superseded** by one or more successors that
  carry the need forward in a changed shape. A use case whose
  nature must change is superseded by new use cases, never
  edited.

## The bar, by stage

A use case is written toward one destination shape: the summary
of why it exists and what it achieves for the user, and — for a
worked journey — the step-by-step a user follows over Reliquary's
application surfaces, spelled exactly. **Proposed and pledged cases
are not held to that bar; getting them there is the job** (owner,
2026-07-29). At these stages a step may lean on an undelivered
piece so long as it is clearly flagged — *requires F-number*, the
pledged feature that delivers it — spelled in the form that
feature is committed to deliver where that form is settled, and
flagged open where it is not. The flags are the case's own
delivery checklist: its distance from force is its outstanding
marks, and none can survive the move, because an F-handle
evaporates on delivery — replacing each flag with the delivered
spelling is part of landing the work. The landing bar itself is
stated where it bites, in the current list's preamble.

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
only there until delivered. **It swings at the second gate too**
(D61, 2026-07-27): a pledge the project does not mean is withdrawn
to this file or rejected outright, never left sitting as a promise
nobody made. Withdrawal costs the commitment and nothing else — the
number, the text, and every citation of it stand, since the
U-namespace is shared across all three locations. Numbers are never
reused: a declined
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
the land-coherently rule (SURFACES.md). The death is
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
claimed), **drafted** (full use-case text, number claimed), and
**withdrawn** (pledged once and no longer — the argument still
stands, the commitment does not; D61, 2026-07-27). Those are the
three states this file holds. Beyond them a use case
is **pledged** — moved to
[pledged/USE-CASES.md](../pledged/USE-CASES.md), the move itself
the record — and then **delivered**, moved again to the current
list; a chunk whose demanded work has already landed is pledged
and delivered in one act. A proposal may die at any point before
delivery (recorded in DECISIONS.md and removed, triggering the
sweep above).

Delivery moves it **automatically** (D34): whoever lands the work
that fully meets a use case promotes it in the same change — into
the current list, out of the pledged file — not on a separate
sign-off, and not recorded in DECISIONS.md, since the moving commit
is the record and carries the delivery evidence (D63). Full
delivery is the
trigger: a use case whose work has partly landed stays pledged
rather than current — unless the delivered part is a use case in
its own right, in which case it is cut out under its own number
and goes current, the remainder staying here. U5 did both in turn:
milestone 8's parameterization machinery met part of it while its
canonical scenario waited on the GUI era (F5), and on 2026-07-28
that part was cut out as U21 (D64). The cut must stand alone; a
rind of a use case is not one. A clarification claims no number of
its own — it attaches to the use case it sharpens — and skips the
argument entirely: it is simply delivered, applied in place to the
current list and removed here.

### Withdrawn from pledged

**Withdrawal costs the commitment and nothing else.** An entry here
left [pledged/USE-CASES.md](../pledged/USE-CASES.md) without being
rejected: its argument still stands, and its number and every
citation of it stay resolvable, since the U-namespace is shared
across all three locations. Its text stands as it stood — verbatim
as adopted, or reshaped where the withdrawal was itself a reshape,
which this file permits freely. Pledging one again is the ordinary
move to `pledged/`, and what earns it is work actually scheduled
against it.

**The grounds differ, and each entry carries its own.** What this
section must never do is assert one ground for all of them: that is
how the shelf went wrong in the first place — a category claim
extended to its members without re-testing each, D61's own closing
lesson — and the two grounds so far are opposites. **U2 and U6**
arrived together on 2026-07-27 (owner; D61) because their pledges
were never made: the 2026-07-26 restructure filed them by the status
word each carried, when *accepted* still meant only that the
argument had won, and D44's rename the next day converted the
shelf's claim to **a commitment to deliver** while clearing its
occupants in a sentence rather than re-testing them. Re-tested,
neither had any delivery behind it. **U5** arrived on 2026-07-28
(owner; D64) because its pledge was real and was paid.

**U2 — Import an existing VM as a blueprint** — withdrawn
(2026-07-27; pledged 2026-07-26 by the restructure, settled as
adopted 2026-07-22). **Nothing of it is implemented.** `import-vm`
left the numbered arc on 2026-07-23 when machine mobility was
demoted to Horizon, and there is a circularity in that record worth
naming: mobility was demoted partly because "import's U2 loses its
scheduled delivery with this move", so U2 was the backing for the
work and demoting the work is what left U2 unscheduled. Each waited
on the other. Its own entry already conceded the position —
"rescheduling import-bearing work is its re-pledging" — and a
re-pledge is only needed by something not currently pledged. The
parked condensation below still applies. Text verbatim as adopted:

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

**U5 — Custom installation** — withdrawn (2026-07-28; pledged
2026-07-26 by the restructure, moved off the current list
2026-07-23, and re-tested onto the shelf 2026-07-27 by D61),
reshaped to the residue of the split that promoted **U21**. Its
delivered substance was the value seam and the secret custody
behind it — milestone 8's parameterization machinery, real and
shipped, which is what carried it past D61's re-test the previous
day. That substance now stands as U21, in force under its own
number, so the pledge it justified is discharged rather than
abandoned. **What remains is the journey, and none of it is
built.** The codex carries two blueprints, freedos and openbsd;
there is no standard Windows install to seed from, no shipped
blueprint declares a seam at all, and the localized-installer seam
is compositional — the half no value can reach, which is why the
machinery landing did not deliver it. Its only carrier is the GUI
era (**F5**), itself proposed and under an open demand
adjudication that names this use case as one of its two threads.
Reshaped text:

> - **U5 — Custom installation.** A user wants the German
>   version of Windows. The codex will not carry such flavors —
>   there are too many variants — so it defines one standard
>   Windows install. The user finds that blueprint easily (U11),
>   seeds a local copy, and customizes it. The author has
>   foreseen the need, and the seam this one takes is
>   compositional rather than a value: a localized edition is a
>   different installer showing different text, which no
>   parameter can reach. The blueprint already names both
>   halves — the media it installs from and the scripts that
>   drive it — so the customized copy points both at the
>   localized pair, each script standing alone against the media
>   it was written for. The user changes what the blueprint
>   names, outside the script, and proceeds. The values an author
>   *can* parameterize are U21's; this is the case values cannot
>   reach.

**U6 — Author a script by doing the task once** — withdrawn
(2026-07-27; pledged 2026-07-26 by the restructure, moved off the
current list 2026-07-23). Its whole delivery is the authoring
recorder, **F1** ([FEATURES.md](FEATURES.md)), withdrawn in the
same round; the design is settled and stands at
[design/recorder.md](design/recorder.md). **The residue it was
pledged on is empty.** That residue is milestone 9's reserved
run-event handover kinds, and
[script-spec.md](../../docs/spec/script-spec.md) says of reserved
kinds that one "has no constant in the implementation: the
vocabulary the code declares is the vocabulary it emits" — a
documented reservation keeping the recorder's shape growable, not
delivery. The blocking dependency is total rather than partial:
recording requires Reliquary to *be* the console, so the whole of
F1 waits on the VNC plane that arrives with the GUI era (F5), text
mode included. Text verbatim as adopted:

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
smaller chunks where possible. **U9 and the U11–U13 chunk trio
left in force** (D46, 2026-07-27): all four were delivered
already, so the pledge and the promotion ran as one act and no
stub stays behind — which is why both sweep ranges now read
with holes in them. **U7 left for
[pledged/USE-CASES.md](../pledged/USE-CASES.md)** on 2026-07-28,
the ordinary move, alongside the adapter seam it schedules; the
mapping sweep's first gap is closed. The calibrating example
(owner): "a user at the keyboard should be able to easily
find a codex blueprint, for example for freedos or openbsd,
with minimal effort, and seed it into their library." People
read these, so each must be succinct, digestible, and
justified. Draft text is in the current list's exact bullet
form, ready to move verbatim on delivery.

**U8 — Keep what was built** — drafted (add, 2026-07-23; **the
separation is complete since D61**, 2026-07-27). The gap: the
export family — machine mobility, demoted from milestone 12 to
Horizon for this very lack — hung from half a sentence inside U1,
and the durable-exit concern deserved its own case (separation: U1
the easy-install journey, U2 the import journey, U8 the export
journey). **That half-sentence is now gone.** U1 condensed to its
journey and promoted to the current list, citing U8 for the export
exit rather than stating it, so the export demand rests here alone
and nothing in force claims the capability. Pledging U8 is
scheduling the mobility work's export half back onto the arc, the
citing item the record — and it is now the *only* thing that
would.

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
work. It is distinct from U14 (something is tested *in* a VM,
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
work (D33 demoted it for lack of exactly this) — and behind
**P16** and **P17**, both in force since D62 and D47
respectively. The in-band file operations it would have needed
scheduled are already delivered (D62), so what is left to demand
is the guest-agent half: a developer driving a Linux guest from
Windows cannot
reach around Reliquary into the guest's own filesystem, and
would name that guest's files in the guest's own terms. Reliquary self-hosting
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

**U22 — The device is the machine's whole point** — drafted (add,
2026-07-29; the case F27's admission said must be drafted before
that feature could be pledged, drafted in the round that pledged
it, and reworked the same day into the shape below — owner: **the
use case is the journey itself**, the summary and the numbered
steps together the adopted text, moving together on delivery).
The gap: no case names the guest's *hardware* as the subject.
U14's consumers are exactly who this serves, and U4/U16 reach a
precisely-defined machine, but none reaches a machine whose
*device model* is the point — a driver under test binds one
particular device, and its developer needs that device's presence
to be a declarable, portable fact that assignment can honor and
preflight can refuse by name. The journey is written from the
real workflow of the consumer class that raised it — a guest-side
driver project and the test harness that drives it — generalized
per the doctrine that consumers are never named. The hatch
sentence is F28's demand citation, and the driver-half sentence
states the split F27's decide-first asks to have stated.

> - **U22 — The device is the machine's whole point.** A
>   developer writing a guest-side driver for a paravirtual
>   device tests it from their own harness, in a machine that
>   exists so that one particular device is present for the
>   driver to bind — without it nothing under test runs: not a
>   weaker test but a different one. Today that need can only be
>   spelled as an engine — a backend pin plus raw device
>   arguments — which records the wrong fact, forecloses every
>   other backend that genuinely provides the device, and fails
>   late or not at all. Declaring the device in the blueprint as
>   a portable fact is what the case buys the user: assignment
>   finds any backend that provides it, a host where none can
>   refuses up front naming the device — the need, not a
>   symptom — the blueprint stays shareable and checked in
>   (U4/U17), and the whole loop — stage, load, exercise, read
>   back, dispose — runs from the caller's own code through one
>   tool, with no raw engine flags and no second harness. A
>   device the vocabulary does not yet name is reachable through
>   the backend's own settings section, at the price of
>   portability — the pressure that grows the vocabulary one name
>   at a time. Whether the *guest* has a driver for the device
>   stays the caller's business: the machine provides the
>   hardware; supplying the driver is the point of the exercise.

**The use case, step by step** — a precise recipe over
Reliquary's application surfaces: a user should be able to follow it
as written to accomplish the goal. Every spelling is the surface
as it stands today. **No step carries a mark any more.** At the
proposed stage a gap was fine as long as it was flagged (owner,
2026-07-29): three steps carried **requires F26/F27/F28** marks —
a pledged, undelivered piece, spelled in the form its feature was
committed to deliver — and the case was to read complete only when
nothing marked remained open. **All three cleared on 2026-07-30**:
F26 (D89) freed step 8, F27 (D91) the `devices` declaration in
step 3 and the assignment axis in step 5, and F28 (D92) the escape
hatch in step 3. Every spelling below is now the surface as it
stands, and the journey has been walked end to end in code rather
than only argued. API spellings shown;
every step has its CLI twin (U9).

1. **The intent.** "I built `DRIVER.EXE` — a DOS driver for a
   paravirtual device — with my host toolchain, and I want it
   tested against the real device model, from my own harness."
   The build lands in `build\out\` beside its load-time
   transport (`TRANSPRT.EXE`) and its exerciser (`DRVTEST.EXE`),
   which exits `0` on success and `1` on any failure.

2. **Pin the world to the project tree** (U17). The harness
   builds one context and passes it everywhere; nothing resolves
   from the user's home, and nothing resolves out of the codex on
   any surface, so the checked-in files are the only source
   (D88 — there is no axis to switch off):

   ```python
   ctx = reliquary.Context(
       home_dir=".rig",              # caches and machines land here
       blueprints_dir="blueprints",  # checked in, used in place
       scripts_dir="scripts")
   ```

3. **Author `blueprints\driver-rig.rlqb`**, checked in — the
   device declared beside memory and drives, the work
   drive pointing straight at the build output, relative
   locations resolving against the project's own directories so
   the file stays portable:

   ```json
   [
     {
       "type": "machine",
       "name": "driver-rig",
       "platform": "dos",
       "memory": "32M",
       "devices": ["virtio-rng"],
       "boot": ["hdd0"],
       "scripts": {
         "ready": "driver-ready"
       },
       "drives": {
         "hdd0": {
           "type": "media",
           "name": "dos-base",
           "location": {"local": "images/dos-base.img"},
           "materialize": "difference"
         },
         "hdd1": {
           "type": "media",
           "name": "work",
           "location": {"local": "build/out"},
           "materialize": "use"
         }
       }
     }
   ]
   ```

   `hdd0` materializes as a differencing image over the
   checked-in installed base, so every machine boots the same
   bytes and the base is never written; `hdd1` *is* the build
   directory, served to the guest as one FAT volume. The
   `devices` line is the live surface since 2026-07-30 (F27
   delivered, D91): the field, its closed curated vocabulary —
   `virtio-rng` is in it — and the assignment axis step 5
   exercises.

   A device the vocabulary does not yet name takes the escape
   hatch instead — live since 2026-07-30 (F28 delivered, D92) —
   two more fields on
   the same machine, `backend` and `backend-settings` sitting
   beside `memory` and `drives` as first-class members of the
   blueprint rather than a mode the document switches into:

   ```json
   {
     "type": "machine",
     "name": "driver-rig",
     "platform": "dos",
     "memory": "32M",
     "backend": "qemu",
     "backend-settings": {
       "qemu": {
         "args": ["-device", "virtio-rng-pci"]
       }
     },
     "boot": ["hdd0"],
     "scripts": { "ready": "driver-ready" },
     "drives": { "…": "as above" }
   }
   ```

   **First-class is not the same as portable**, and the two are
   easy to conflate. Both fields are ordinary machine fields —
   parsed, validated, schema'd and recorded in the machine's state
   like every other — while `backend-settings` is the one place
   backend-specific configuration may appear, which is exactly
   what makes a blueprint *without* it portable by construction.
   So the hatch costs portability and nothing else: the same
   machine, on one engine, by that engine's own vocabulary — and
   the keys are that adapter's own, so a key `qemu` does not
   define is refused rather than carried and ignored, and an
   argument restating `memory`, `drives`, `boot` or the recorded
   identity is refused naming its owner (D92). That
   is the pressure that grows the curated `devices` names one at a
   time, and a settings key in repeated use across blueprints is
   demand arriving for one.

4. **Author `scripts\driver-ready.rlqs`** — the caller's own
   readiness protocol, because Reliquary ships no readiness
   policy (U14's idiom: the guest says ready, the host reads it
   back):

   ```text
   description "Boot to a DOS prompt and say so"
   platform dos
   machine  stopped
   timeout  2m

   start
   wait /[A-Z]:\\.*>/
   set ready "yes"
   ```

5. **Create the machine.**
   `reliquary.create_machine("driver-rig", context=ctx)` — CLI
   twin `rlq create-machine --blueprint driver-rig` — returns
   `"driver-rig-0"`. Assignment reads the whole demand, `devices`
   included: the priority walk takes the first
   backend both available and capable of `virtio-rng`, and a host
   where none is refuses **now**, at preflight, naming the
   device — a `PreflightError`, exit `3` at the CLI — not
   mid-boot as a driver that mysteriously would not load, and
   never by silently landing on an engine without the device.

6. **Learn the guest's own names.**
   `reliquary.describe_drives(machine="driver-rig-0",
   context=ctx)` — `rlq describe-drives -m driver-rig-0` — and
   the report's mapping says the work drive is one FAT volume at
   `D:` (delivered, D83). That letter is the address every later
   step speaks (P17); nothing is inferred from a boot screen.

7. **Boot, and let the guest say ready.**
   `reliquary.run_script("ready", machine="driver-rig-0",
   context=ctx)` resolves the blueprint's `scripts` map, starts
   the stopped machine as the script's own `start` directs, waits
   out the boot to a prompt, and sets the variable;
   `reliquary.get_machine_var("ready", machine="driver-rig-0",
   context=ctx)` reads back `"yes"`.

8. **Load the driver — setup whose output is nothing and whose
   success is everything.** In order, once per session, each
   checked — **delivered 2026-07-30** (D89), so this step's mark is
   gone and its spelling is the live surface:

   ```python
   reliquary.exec(r"D:\TRANSPRT.EXE", check=True,
                  machine="driver-rig-0", context=ctx)
   reliquary.exec(r"D:\DRIVER.EXE", check=True,
                  machine="driver-rig-0", context=ctx)
   ```

   After each command Reliquary's interaction layer probes the
   guest with `IF ERRORLEVEL 1` and a sentinel of its own
   composing; a command that signalled failure — "no device
   present", already resident, wrong load order — raises
   `RunFailure` naming the command (CLI: exit `4`), so a refused
   loader ends the session here as one legible failure, not later
   as every test failing strangely. The row return is unchanged.
   A command that never ran at all — mistyped — escapes the
   probe: its honest scope is commands that ran and signalled
   failure.

9. **Exercise, and read the results back.**
   `rows = reliquary.exec(r"D:\DRVTEST.EXE 48",
   machine="driver-rig-0", timeout=30, context=ctx)` returns the
   screen rows, and parsing them is the caller's business (P18) —
   Reliquary attaches no meaning. Bulkier results are redirected
   in-guest to the work drive (`DRVTEST -v > D:\RUN.LOG`) and
   retrieved after a stop with
   `reliquary.get_file(r"D:\RUN.LOG", "results/run.log",
   machine="driver-rig-0", context=ctx)` — named in guest terms,
   both directions.

10. **Iterate, then dispose.** Rebuild the driver; the
    directory-source work drive re-reads at the next start, so a
    round is `stop_machine` → `run_script("ready")` → load →
    exercise — or U20's live `insert-media --file` swap when
    reboot-per-round is the bottleneck. When the work ends,
    `reliquary.destroy_machine("driver-rig-0", ctx)`: nothing
    durable remains but the retrieved results (U14).

### Pending clarifications

Parked in-place edits — no argument needed, delivered when
applied; each must pass the clarification test (no past
citation reads differently under the new wording).

- **U1 — the two-command journey** — **applied 2026-07-30** (D88),
  and struck from this list. It went to the root with the delivery
  that made it true, as a supersession rather than a clarification:
  past citations read differently (D61's own description of U1,
  D66's "single command", D12's "one-command path"), and the
  number was reshaped in place exactly as D61's condense was. The
  opening wish also went from FreeBSD to FreeDOS — a system no
  codex blueprint provides, contradicted by the case's own
  command, which the landing bar no longer tolerates now that a
  journey must be followable as written.

- **U1 — condense to the journey** — **applied 2026-07-27** (D61),
  and struck from this list. It ran without waiting on U8: the
  contingency existed to keep the export clause owned by something,
  and withdrawing rather than pledging is the other way to settle
  who owns it. U1 is now the composed journey it uniquely owns —
  one short, terse command from a clean home to a usable machine,
  easy-is-the-requirement included — citing U11 (find and seed),
  U13 (media) and U12 (the install) for what it composes, and U8
  for the export exit it no longer claims. **It went in as a
  supersession, not a clarification**: the clarification test is
  that no past citation reads differently, and one did —
  blueprint-guide's "you export it (U1)" now points at U8. With the
  export clause gone every remaining word was delivered, so D34
  promoted it to the current list in the same act.
- **U2 — condense** (recorded 2026-07-23; U2 is withdrawn as of
  D61, which does not disturb this — a proposed use case may be
  reshaped freely, and this edit was always a trim rather than a
  change of nature). Trim the import
  doctrine detail — never-copy, snapshot consent, and the
  duplicate/difference choice are settled in the dissolved roadmap's import
  design and DECISIONS.md — down to the demand itself: capture
  a native VM as a blueprint, source at rest and untouched,
  the two decision points presented, never defaulted.

### Tracked

- **Break U5 into finer pieces** — **executed 2026-07-28** (D64),
  and closed. Recorded 2026-07-23 by the decomposition sweep with
  three candidate cuts; two of them — parameterization's two
  bindings (in-blueprint values vs externally defined) and secret
  custody (never in source control) — went as one to the current
  list as **U21**, met by milestone 8's machinery, and the third —
  the seed-and-customize journey — is what U5 now is. The trigger
  it named fired on its second clause: an argument needed the
  finer citation.
- **Break U6 into finer use cases** — tracked (recorded
  2026-07-23; previously an expectation noted inside U6
  itself). Candidate cuts per the recorder design
  ([design/recorder.md](design/recorder.md)): record
  a task once into a draft script; extend a tailored script by
  round-trip re-recording; refresh assets for a changed
  screen. Left undrafted by the decomposition sweep: the
  recorder is unpledged (F1), and premature cuts risk being the
  wrong ones.
