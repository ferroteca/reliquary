<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Use-case proposals

> **Status:** this is where changes to the use-case list are drafted.
> **Nothing here is pledged, and no work is done from this list.** A
> proposal has to be argued for under the
> [surface-change rule](../SURFACES.md#the-rule), and **moving it is
> what pledging it means**: it goes to
> [pledged/USE-CASES.md](../pledged/USE-CASES.md), and the commit
> that moves it is the record of the decision. It only reaches the
> current list — [USE-CASES.md](../../USE-CASES.md), which holds only
> the use cases the code already meets — once it's actually
> delivered, in a second move that happens automatically once
> delivery is complete (D34).

This document tracks proposed changes to the use-case list: new use
cases being drafted, and proposed retirements or replacements of use
cases already in force. It exists so the current list can stay a
stable, settled statement of what's true while proposals are still
being worked out here.

## The use-case lifecycle

Once a use case is in force, its actual meaning never changes. A
*proposed* one is different: until it's in force, it can be
reworked freely here — it keeps its number, and any work already
scheduled against it (if it's a pledged proposal) gets rechecked as
part of the same edit. There are exactly three things that can
happen to an entry on the standing list:

- **Clarify it.** Edit the wording in place to sharpen what the use
  case already meant — this changes the words, never the meaning.
  The test: no past decision that cited the use case would have come
  out differently under the new wording. A clarification doesn't
  need an argument — it can land directly in the root USE-CASES.md,
  or, if it's not ready yet, sit here as an entry against its use
  case's number until it's applied. If it's debatable whether an
  edit counts as a clarification, then it isn't one — it's a
  replacement, and has to be argued for like any other proposal.
- **Add one.** A new use case gets drafted here, argued for under
  the surface-change rule, pledged, and moved to the root
  USE-CASES.md once it's delivered.
- **Retire it.** A use case leaves the current list either
  **retired**, with nothing replacing it, or **superseded** by one
  or more new use cases that carry the same need forward in a
  changed shape. If a use case's actual meaning has to change, it
  gets superseded by a new one — it's never just edited in place.

## The bar, by stage

Every use case is written toward the same eventual shape: a summary
of why it exists and what it gets the user, and — for a worked
journey — the exact steps a user follows over Reliquary's real
interfaces. **Proposed and pledged use cases don't have to meet that
bar yet; getting them there is the whole job of doing the work**
(owner, 2026-07-29). At these earlier stages, a step is allowed to
lean on something not yet built, as long as it's clearly flagged —
*requires F-number*, naming the pledged feature that will deliver
it — spelled out in the form that feature has committed to deliver,
if that's already settled, or left flagged open if it isn't. These
flags work as the use case's own checklist: however many of them
remain is how far it still has to go before it's in force, and none
of them can survive the move onto the current list, because once
the feature ships, the F-number they point to no longer means
anything — replacing each flag with what actually got delivered is
part of finishing the work. The bar itself for landing on the
current list is stated where it actually applies, in that list's
own preamble.

## Numbering

Proposed and in-force use cases all share one set of numbers: a
proposal drafted here takes the next free U-number, keeps that
number for good, and moves to the root USE-CASES.md under that same
number once it's delivered. Moving it to pledged/USE-CASES.md is
what pledging means — the argument for it won, the commit that
moves it is the record, and from there the pledged proposal can be
cited; delivery is what finally makes it current. This can also run
in reverse: a use case that was pledged but loses its schedule moves
back to pledged/USE-CASES.md and stays there until it's delivered.
**And it can run in reverse a step further too** (D61, 2026-07-27):
if the project stops meaning a pledge, that pledge is withdrawn back
to this file, or rejected outright — never just left sitting as a
promise nobody actually intends to keep. Withdrawing only costs the
commitment: the number, the text, and every citation of it stay
exactly as they were, because all three files share the same
U-numbers. Numbers are never reused: when a proposal is declined,
its number is retired along with it (the decision is recorded in
[DECISIONS.md](../DECISIONS.md), so it doesn't get re-argued later),
and when a use case is superseded, it leaves the current list with
no stub behind — DECISIONS.md records the retirement, and whatever
replaces it names the number it's replacing — so any old citation to
it still resolves.

## Removal and the planning sweep

When a proposal dies — declined after argument, withdrawn, or just
lapsed without ever being built — it's removed from this document,
and that removal triggers a sweep of the other planning docs: any
downstream material that depended on it (a planning/design/
document, a planning section, TASKS entries) gets removed or
rewritten in the same pass, following the land-coherently rule
(SURFACES.md). The death is recorded in DECISIONS.md along with its
reason, so it doesn't get proposed again blindly, and nothing
downstream is left citing a use case that never actually made it
into force. The sweep is easy to do thoroughly because everything is
traceable: every pledged item cites the use case or principle that
justifies it (the traceability rule in the planning docs' preamble),
so the dead proposal's U-number is what you search for to find
everything that depended on it.

## Open proposals

Each proposal records what it's proposing (add / retire / supersede
/ clarify), which use cases it touches, and its state: **tracked**
(a change we expect to make but haven't drafted yet — no number
claimed), **drafted** (full use-case text written, number claimed),
or **withdrawn** (pledged once, not anymore — the argument for it
still stands, but the commitment doesn't; D61, 2026-07-27). Those
are the three states this file itself holds. Beyond that, a use
case can be **pledged** — moved to
[pledged/USE-CASES.md](../pledged/USE-CASES.md), where the move
itself is the record — and then **delivered**, moved again onto the
current list. A piece of work that's already landed by the time it's
proposed can be pledged and delivered in one single act. A proposal
can die at any point before delivery, in which case it's recorded in
DECISIONS.md and removed, triggering the sweep described above.

Delivery moves a use case **automatically** (D34): whoever finishes
the work that fully meets it moves it in the same change — onto the
current list, out of the pledged file — rather than waiting for a
separate sign-off, and it isn't recorded in DECISIONS.md, because the
commit that moves it is already the record, carrying the delivery
evidence itself (D63). It takes full delivery to trigger the move: a
use case that's only partly built stays pledged rather than moving
to the current list — unless the part that's done is really a use
case in its own right, in which case that part is carved out under
its own number and moves to the current list, while the rest stays
here. U5 went through both of these: milestone 8's parameterization
machinery met part of it, while its main scenario was still waiting
on the GUI era (F5), so on 2026-07-28 that finished part was carved
out as U21 (D64). A carved-out piece has to be a complete use case on
its own — a leftover fragment doesn't count as one. A clarification
doesn't claim a number of its own — it attaches to the use case it's
sharpening — and skips the argument step entirely: it's simply
applied in place on the current list and removed from here.

### Withdrawn from pledged

**Withdrawing only costs the commitment, nothing else.** Every entry
in this section left [pledged/USE-CASES.md](../pledged/USE-CASES.md)
without being rejected: the argument for it still stands, and its
number and every citation of it still resolve, since all three files
share the same U-numbers. Its text stands as it was — either exactly
as it was adopted, or reworded, if the withdrawal itself came with a
rewording, which this file allows freely. Pledging it again is just
the ordinary move to `pledged/`, earned by work actually being
scheduled against it.

**The reasons differ for each one, so each entry states its own.**
This section must never claim one blanket reason for all of them —
that's exactly how a whole batch of use cases went wrong before:
a claim made about the group as a whole, applied to its members
without checking each one. That's the closing lesson of D61.

**U2 — Import an existing VM as a blueprint** — withdrawn
(2026-07-27; pledged 2026-07-26 during a restructure, originally
adopted 2026-07-22). **None of it is built.** `import-vm` fell off
the schedule on 2026-07-23 when machine-mobility work was pushed out
to the backlog, and there's a circular piece of history worth
pointing out: mobility was pushed out partly because "import's U2
loses its scheduled delivery with this move" — meaning U2 was the
justification for that work, and pushing the work out is exactly
what left U2 without a schedule. Each one was waiting on the other.
The entry itself already admitted as much — "rescheduling
import-bearing work is its re-pledging" — and a re-pledge is only
needed for something that isn't currently pledged. The condensed
version below, parked here, still applies. Here is U2's text, as
adopted:

> - **U2 — Import an existing VM as a blueprint.** A user has
>   already created a VM natively — in VMware, say — and wants to
>   capture it as a Reliquary blueprint (`import` builds the
>   blueprint; actually creating a machine from it afterward is an
>   ordinary `create`). Import only reads a source VM that's
>   stopped — a source VM that's running or suspended makes it fail
>   right away, naming the problem — and the captured disk image
>   stays exactly where the native hypervisor keeps it: import
>   points a generated `media` entry — a `local` source inside the
>   blueprint — at that image, and never copies, moves, or changes
>   it. A user who wants the image somewhere more permanent can
>   move it themselves and repoint that entry, since it's theirs to
>   manage. Two choices are always presented to the user, never
>   picked automatically. First, whether to take a native
>   snapshot — the only thing import is allowed to do to the
>   source VM, and only with this consent: if the user says yes,
>   the blueprint locks onto that frozen state and the source VM is
>   free to keep running normally; if the user says no, nothing
>   touches the source VM, but running it again afterward will
>   break verification until it's re-imported. Second, how new
>   machines are built from the captured disk: each one can be a
>   full copy of it (`duplicate` — the new machine's drive is
>   independent afterward) or a differencing disk layered on top of
>   it (`difference` — the cheapest to create, but the source has
>   to stay byte-for-byte unchanged, and verification refuses to
>   build a machine if the source has since been altered). The
>   import flow's job is to put these choices in front of the user,
>   not hide them.

**U6 — Author a script by doing the task once** — withdrawn
(2026-07-27; pledged 2026-07-26 during a restructure, moved off the
current list 2026-07-23). The whole of what would deliver it is the
authoring recorder, **F1** ([FEATURES.md](FEATURES.md)), which was
withdrawn in the same round; its design is settled and stands at
[design/recorder.md](design/recorder.md). **What it was pledged on
turned out to be empty.** That was milestone 9's reserved run-event
handover kinds, and [script-spec.md](../../docs/spec/script-spec.md)
says of reserved kinds that one "has no constant in the
implementation: the vocabulary the code declares is the vocabulary
it emits" — meaning it's a documented placeholder that keeps the
recorder's shape flexible for later, not something already
delivered. The thing actually blocking this is total, not partial:
recording requires Reliquary itself to be the console, so all of F1
is waiting on the VNC control plane. Its screen-and-keyboard half is
delivered on QEMU (F63); the recorder's viewer also needs pointer
input, pledged as **F66**; and interactive display — including text
mode — is still waiting on F5. Here is U6's text, as adopted:

> - **U6 — Author a script by doing the task once.** A user performs
>   a task by hand — going through a Windows install, say — in a
>   console session that Reliquary is watching, and ends up with a
>   draft script plus the image assets (landmarks) needed to
>   reproduce it. Reliquary follows the whole session — every
>   keystroke, click, and media swap, and the screen states in
>   between — and drafts the wait conditions and actions, capturing
>   the screenshots that the landmarks are cropped from. The result
>   is a *draft*: ordinary script text, alongside the landmark
>   declarations and images it references as separate authored
>   files, since a script never embeds its assets directly (amended
>   2026-07-22; see planning/DECISIONS.md). It's owned and edited
>   like anything hand-written, because recording can't know which
>   screen features actually matter or how long a step can honestly
>   be allowed to take — so the person tailors what Reliquary
>   proposed. Tailoring isn't a one-way trip: authoring can go back
>   and forth. When the task changes, or more coverage is needed, a
>   later session captures the new screens and steps *against the
>   already-tailored script* — playback carries the machine up to
>   the point of the change, the person takes over and demonstrates
>   the rest, and Reliquary proposes the new fragment and its
>   assets without touching what the author already wrote. If a
>   screen changes but the step itself hasn't, that's just an asset
>   refresh — a new landmark variant added to the catalog — and it
>   doesn't touch the script at all. The machine used for the
>   session is just as disposable as any other; the script and its
>   assets are the actual product. (This is the authoring
>   counterpart to U2: import captures a machine that was built by
>   hand, and recording captures a procedure that was performed by
>   hand.)

### Drafted

The use cases below came out of two reviews, both on 2026-07-23.
The first review (U7–U10) closed named gaps in coverage — roadmap
work that had no use case actually justifying it. The second review
(U11–U17) followed the owner's direction to break the dense, bundled
use cases into much smaller pieces where possible. The example the
owner gave to calibrate by: "a user at the keyboard should be able
to easily find a codex blueprint, for example for freedos or
openbsd, with minimal effort, and seed it into their library."
People actually read these, so each one has to be short, easy to
follow, and clearly justified. The draft text below is written in
the same bullet form the current list uses, ready to move over
unchanged once it's delivered.

**U8 — Keep what was built** — drafted (add, 2026-07-23; **the split
has been complete since D61**, 2026-07-27). The gap this fills: the
export side of machine mobility — pushed out of milestone 12 to the
backlog for exactly this reason — used to hang off half a sentence
inside U1, when the need to keep a built machine deserved a use case
of its own (so the work split three ways: U1 for the easy-install
journey, U2 for the import journey, U8 for the export journey).
**That half-sentence is gone now.** U1 was trimmed down to its own
journey and promoted to the current list, and it now just cites U8
for the export step instead of describing it — so the export need
now rests on U8 alone, and nothing currently in force actually
claims this capability. Pledging U8 is what would put the export
half of the mobility work back on the schedule, with this entry as
the record of why — and right now, it's the *only* thing that
would.

> - **U8 — Keep what was built.** Sometimes the machine itself is
>   the product after all — the sandbox that's worth keeping (U1),
>   the built rig worth handing on to someone else. The user exports
>   it, and Reliquary lets go of it completely: either as a whole
>   machine registered with a hypervisor meant for keeping machines
>   long-term, bootable with that platform's own tools, or as a
>   single disk image taken out as a standalone file. The exported
>   copy stands entirely on its own — its media is copied in, and
>   nothing about it points back to Reliquary's home directory or
>   caches — and Reliquary never touches it again afterward. This
>   doesn't bend the rule that Reliquary machines are disposable —
>   it's exactly what makes that rule work: a Reliquary machine can
>   stay disposable precisely because there's always a durable way
>   to keep what came out of it.

**U16 + U17 — split U4** — drafted (supersede U4, 2026-07-23, the
decomposition review). U4 bundled the sharing journey together with
the rule about where artifacts live; that residency rule already
matches the automation half of the artifact-residency split, so U17
gives it a number decisions can cite directly, and the split's
writeup can now just cite U16/U17 once they're pledged. Once both
are delivered, U4 retires down to a stub that names them.

> - **U16 — Share a precise test VM through version control.** A
>   program has to be tested in a VM — maybe running a proprietary
>   OS — and the repository can only carry definitions: blueprints
>   and scripts, with their hashes pinning down the exact media
>   they target. A second developer supplies the two things the
>   repo can't — the install media and its license — and builds the
>   same rig, verified to match. The rig is somewhat expensive to
>   build, so it's kept around for the work cycle and thrown away
>   once the work is done.

> - **U17 — Project artifacts work in place.** For automation,
>   blueprints, scripts, and their assets count as source code: they
>   live in the consuming project's own directory tree, under that
>   project's source control, and run straight from there — nothing
>   gets copied into a Reliquary home directory to make them usable,
>   and an automated run never reaches outside the project's tree.
>   The Reliquary home directory stays reserved for Reliquary's own
>   things: caches, machines, and the user's personal properties
>   file.

**U18 — Test on the platform the host isn't** — drafted (add,
2026-07-23; the owner's, prompted by noticing that Reliquary's own
credential-store code has a Linux code path that its Windows
developer can't run). The gap this fills: every use case on the
list treats the guest as either the subject being tested or the
product being built; none of them treat it as **the missing
platform** a developer needs in order to test their own work. That's
different from U14 (something is tested *inside* a VM, but which
platform is incidental) and from U16 (a rig shared between
developers): here, the point is specifically that the guest *is* a
different operating system, standing in for "somebody else's
machine" — the kind of thing normally covered by a CI matrix, but
available locally instead.

A caveat, from the owner: this needs more maturity than the project
currently has — a modern-guest platform workflow for Linux, a way
to get code in and results out, and realistically a native guest
agent to keep the loop tight. So this isn't a near-term request to
schedule. What makes it worth numbering now is what it would demand
once pledged: it would be the first use case in force to put real
weight behind the guest-agent work that's currently in the
backlog — work that was pushed there specifically for lack of a
case like this (D33) — and behind **P16**. **D108 sharpened exactly
what it demands**, because the approach it would have relied on is
gone: Reliquary doesn't place any file on a machine's drives, so a
loop that gets code in and results out of a Linux guest has to be
either the guest-agent's job, or the caller's own tooling working
against a drive Reliquary provided. Pledging this use case is really
an argument about which of those it should be, and any demand for
built-in file access has to be argued as an amendment to P16's
carve-out, not assumed as already covered by it. The case that
motivated this is Reliquary testing its own code across platforms,
but the use case itself applies generally.

> - **U18 — Test on the platform the host isn't.** A developer's
>   code has paths that only run on an operating system they aren't
>   actually sitting in front of. They describe that system as a
>   blueprint, put their code and its test runner inside it, run it,
>   and read the results back — on their own machine, with no round
>   trip through CI and no second computer needed. The guest here is
>   neither the product nor the thing being tested: it's the
>   platform the work needs, which the host itself can't provide.
>   What makes it useful is that it's the real thing — an actual OS,
>   not an emulated API surface — and that the loop is fast enough
>   to actually use while working.

**U19 — Start a long run and follow it from elsewhere** — drafted
(add, 2026-07-24; from the round that deferred async work, D35). The
gap this fills: the asynchronous-run work — `run-script --detach`,
the cross-process followers (`run tail` / `run wait` / `run cancel`),
and the API's async handles (`start_script` / `attach_run` /
`start_fetch`) — is real, designed work, but it was only justified by
a loose reading of U1 ("leaves an hour-long install and checks back")
that U1's actual text never says, and by U14's "observes results,"
which a synchronous jsonl stream already satisfies on its own.
Milestone 9's records core already delivers the live stream and its
renderings to whatever process started the run (P5); what U19 names
is the separate capability of following a run from a process that
did *not* start it. This work was moved off the schedule to the
backlog the same day this was drafted (D35), for the same reason
D33 gave for the backend work: it was a settled design with no use
case, in force or pledged, actually backing it. Pledging U19 would
put the async work back on the schedule, with this entry as the
record; once pledged, the planning doc's "Asynchronous runs
(backlog)" section and the milestone that picks the work back up
both cite U19.

> - **U19 — Start a long run and follow it from elsewhere.** A run
>   takes an hour, and the person or program that started it doesn't
>   sit and wait at the terminal that launched it: they detach from
>   it, or start it in one place and follow it from another — a
>   second terminal, a later session, a different process — watching
>   the same live stream and seeing the same outcome the original
>   driver would have seen. The run doesn't belong to its terminal:
>   the machine owns it, not the process that invoked it, so a
>   follower can attach to its record while it's running and detach
>   again without disturbing it.

**U22 — The device is the machine's whole point** — drafted (add,
2026-07-29; feature F27 admitted this use case had to be drafted
before it could be pledged, so it was drafted in the same round that
pledged F27, and reworked the same day into the shape below — the
owner's call: **the use case is the whole journey** — the summary
and the numbered steps count as one adopted text, and they move
together when this is delivered). The gap this fills: no use case
names the guest's *hardware* as the actual subject. U14's users are
exactly the ones this serves, and U4/U16 reach a precisely defined
machine, but none of them reach a machine whose whole point is its
*device model* — a driver under test binds to one particular device,
and its developer needs that device's presence to be something they
can declare as a portable fact, something assignment can honor and
preflight can refuse by name if it's missing. This journey is
written from the real workflow of the group that raised the need —
a guest-side driver project and the test harness that drives it —
but generalized, since specific consumers are never named directly.
The sentence about the settings hatch cites F28's need for it, and
the sentence about the driver states the split that F27's
decide-first approach asked to have written down.

> - **U22 — The device is the machine's whole point.** A developer
>   writing a guest-side driver for a paravirtual device tests it
>   from their own harness, in a machine that exists for one
>   reason: to have that one particular device present for the
>   driver to bind to. Without it, nothing under test even runs —
>   not a weaker test, a completely different one. Today, the only
>   way to ask for that is by pinning a specific backend engine and
>   passing it raw device arguments, which records the wrong thing,
>   rules out every other backend that could genuinely provide the
>   device, and fails either too late or not at all. What this use
>   case buys the user is being able to declare the device in the
>   blueprint as a portable fact instead: assignment finds any
>   backend that provides it, a host where none can refuses up
>   front and names the missing device — the actual need, not just
>   a symptom of it — the blueprint stays shareable and checkable
>   into source control (U4/U17), and the whole loop — stage, load,
>   exercise, read results back, dispose — runs from the caller's
>   own code through one tool, with no raw engine flags and no
>   second test harness. A device the vocabulary doesn't name yet
>   can still be reached through the backend's own settings
>   section, at the cost of portability — and that cost is exactly
>   the pressure that grows the vocabulary, one device name at a
>   time. Whether the *guest* even has a driver for the device is
>   still the caller's own business: the machine just provides the
>   hardware, and supplying the driver is the whole point of the
>   exercise.

**The use case, step by step** — a precise recipe over Reliquary's
real interfaces: a user should be able to follow it exactly as
written and reach the goal. Every command shown here is the
interface as it actually stands today — no step is a placeholder,
and this journey has actually been run end to end in code, not just
argued for on paper. The steps below show the API; every one also
has an equivalent CLI command (U9).

1. **The intent.** "I built `DRIVER.EXE` — a DOS driver for a
   paravirtual device — with my host toolchain, and I want to test
   it against the real device model, from my own test harness." The
   build lands in `build\out\`, alongside its load-time transport
   tool (`TRANSPRT.EXE`) and its exerciser (`DRVTEST.EXE`), which
   exits `0` on success and `1` on any failure.

2. **Pin everything to the project's own directory tree** (U17).
   The harness builds one context object and passes it everywhere;
   nothing resolves from the user's home directory, and nothing
   resolves out of the codex on any interface, so the checked-in
   files are the only source Reliquary can pull from (D88 — there's
   no setting to turn this off):

   ```python
   ctx = reliquary.Context(
       home_dir=".rig",              # caches and machines land here
       blueprints_dir="blueprints",  # checked in, used in place
       scripts_dir="scripts")
   ```

3. **Write `blueprints\driver-rig.rlqb`**, checked into the repo —
   pinning the backend and asking for the device in that backend's
   own settings section, with the work drive pointing straight at
   the build output. Relative paths resolve against the project's
   own directories, so the file stays portable across checkouts:

   ```json
   [
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

   `hdd0` materializes as a differencing image on top of the
   checked-in installed base, so every machine boots the exact same
   bytes and the base image is never written to; `hdd1` *is* the
   build directory, served to the guest as one FAT volume. Between
   the backend pin and the settings section, that's the whole
   spelling of the device (D92): a driver under test binds to one
   particular device on one particular backend, and P25 (D93) keeps
   backend-specific hardware out of the portable vocabulary, so the
   machine just says `qemu` and asks QEMU for the device in QEMU's
   own terms.

   **Being an ordinary machine field isn't the same as being
   portable, and it's easy to mix the two up.** Both fields here are
   ordinary machine fields — parsed, validated, checked against the
   schema, and recorded in the machine's state like any other field
   — while `backend-settings` is the one place backend-specific
   configuration is allowed to appear at all, which is exactly what
   makes a blueprint *without* it portable by design. So using this
   settings hatch only costs you portability, nothing else: the same
   machine, tied to one engine, described in that engine's own
   vocabulary — and the keys inside it belong to that adapter alone,
   so a key `qemu` doesn't recognize is rejected rather than silently
   ignored, and trying to restate `memory`, `drives`, `boot`, or the
   machine's recorded identity through it is rejected too, naming
   which field already owns that (D92). If the same settings key
   keeps showing up across different blueprints, that's a sign it
   deserves to become a proper first-class field — which happens
   under P25's bar, once more than one backend can support it, and
   never just because it's been requested (D93).

4. **Write `scripts\driver-ready.rlqs`** — the caller's own
   readiness check, since Reliquary doesn't ship a built-in
   readiness policy (this is U14's usual pattern: the guest says
   it's ready, and the host reads that back):

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
   `reliquary.create_machine("driver-rig", context=ctx)` — with the
   CLI equivalent `rlq create-machine --blueprint driver-rig` —
   returns `"driver-rig-0"`. Because the backend is pinned, only
   `qemu` gets probed, and a host without QEMU refuses **right
   here**, at preflight, naming the backend — a `PreflightError`,
   exit code `3` on the CLI — instead of failing later, mid-boot,
   as a driver that mysteriously won't load. The settings section's
   arguments are already validated at create time (D92: the same
   code that renders them is what validates them), so any machine
   that actually gets created is one whose device argument is
   guaranteed to render at every start.

6. **Boot, and let the guest say it's ready.**
   `reliquary.run_script("ready", machine="driver-rig-0",
   context=ctx)` looks up the blueprint's `scripts` map, starts the
   stopped machine the way the script's own `start` step directs,
   waits for the boot to reach a prompt, and sets the variable;
   `reliquary.get_machine_var("ready", machine="driver-rig-0",
   context=ctx)` reads back `"yes"`.

7. **Load the driver — a setup step whose output is nothing and
   whose success is everything.** Run these in order, once per
   session, each one checked for success (D89):

   ```python
   reliquary.exec(r"D:\TRANSPRT.EXE", check=True,
                  machine="driver-rig-0", context=ctx)
   reliquary.exec(r"D:\DRIVER.EXE", check=True,
                  machine="driver-rig-0", context=ctx)
   ```

   After each command, Reliquary's interaction layer checks the
   guest with `IF ERRORLEVEL 1` and a sentinel it composes itself.
   If a command signals failure — "no device present," already
   loaded, wrong load order — Reliquary raises `RunFailure`, naming
   the command that failed (exit code `4` on the CLI), so a rejected
   loader ends the session right there with one clear failure,
   instead of every later test failing in confusing ways. What each
   command returns is unchanged otherwise. A command that never ran
   at all — say, a typo — doesn't get caught by this check: it's
   only designed to catch commands that ran and then signaled
   failure.

8. **Exercise the driver, and read the results back.**
   `rows = reliquary.exec(r"D:\DRVTEST.EXE 48",
   machine="driver-rig-0", timeout=30, context=ctx)` returns the
   screen's rows, and parsing them is entirely the caller's own
   business (P18) — Reliquary doesn't interpret them at all. For
   bulkier results, redirect them in the guest to the work drive
   instead (`DRVTEST -v > D:\RUN.LOG`), and the caller reads them
   **straight off its own host directory** once the machine stops:
   the work drive *is* that directory, so nothing needs to be
   fetched back separately (D108). The guest drive letter `D:` is
   the author's own choice — it appears in the guest commands above
   because the author built the machine that way, not because
   Reliquary reported it.

9. **Iterate, then dispose of the machine.** Rebuild the driver;
   because the work drive reads straight from its source directory,
   it picks up the new build automatically at the next start. So one
   round looks like `stop_machine` → `run_script("ready")` → load →
   exercise — or, when rebooting each round becomes the bottleneck,
   U20's live `insert-media --file` swap instead. When the work is
   done, `reliquary.destroy_machine("driver-rig-0", ctx)` cleans up:
   nothing is left behind except the results the caller chose to
   keep (U14).

### Pending clarifications

These are wording edits parked here, ready to apply in place —
no argument needed, and each one has to pass the clarification
test: no past citation would read any differently under the new
wording.

- **U2 — condense** (recorded 2026-07-23; U2 has been withdrawn as
  of D61, which doesn't affect this — a proposed use case can still
  be reworked freely, and this edit was always just a trim, not a
  change of meaning). Trim out the import details — never copying
  the source, snapshot consent, and the duplicate/difference
  choice, which are already settled in the retired roadmap's import
  design and in DECISIONS.md — down to the core demand: capture a
  native VM as a blueprint, reading the source as-is without
  touching it, with both decision points always presented to the
  user rather than picked automatically.

### Tracked

- **Break U6 into finer use cases** — tracked (recorded 2026-07-23;
  this was previously just a note inside U6 itself). Candidate ways
  to split it, per the recorder design
  ([design/recorder.md](design/recorder.md)): recording a task once
  into a draft script; extending an already-tailored script by
  recording again to add to it; and refreshing assets for a screen
  that changed. Left undrafted by the decomposition review, because
  the recorder itself isn't pledged yet (F1), and splitting this up
  too early risks getting the split wrong.
