<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Pledged use cases — awaiting delivery

> **Status:** use cases the project has **pledged** but does not
> yet meet. Work may be done from here; nothing here is a claim
> about the code.
>
> Three locations hold three states. A use case is drafted in
> [proposed/USE-CASES.md](../proposed/USE-CASES.md), moves here when
> it is pledged, and moves to root
> [USE-CASES.md](../../USE-CASES.md) when the code actually meets
> it. The root list is implemented-only — every entry there is met
> today, which is why it lives at the repository root — so
> pledge alone can never put an entry in it. All three share
> one global U-namespace; numbers are permanent, never reused, and
> no placeholder is left behind by either move.
>
> The second move is **automatic on full delivery** (D34): whoever
> lands the work that fully meets a use case promotes it in the same
> change — adds it to the root list, deletes it here, records the
> move in [DECISIONS.md](../DECISIONS.md) — rather than holding it for
> a separate sign-off. *Full* delivery is the trigger: a use case
> whose work has partly landed stays here, since the root list is an
> implementation claim (milestone 8 pledged U5, but its canonical
> scenario waits on the GUI era, F5).
>
> A use case in force is clarified, retired, or superseded — never
> changed in nature. One pledged here may still be reshaped, its
> number intact, with work already scheduled against it re-checked
> in the same edit. A proposal that dies at any point is recorded in
> [DECISIONS.md](../DECISIONS.md) and removed, triggering the planning
> sweep described in
> [proposed/USE-CASES.md](../proposed/USE-CASES.md); its U-number is
> the search key.

**U1 — Install a sandbox VM from the CLI, easily** — pledged;
moved from the current list 2026-07-23 (owner: the current
list is implemented-only). The install journey is delivered
end to end — the north-star command works from a clean home —
but the export clause is unimplemented Horizon work (machine
mobility), so U1 as written is not met. **The delivered
substance is now seated in the current list** as U11, U12 and
U13 (D46, 2026-07-27), which is what that split was for; U1
stays here for its export clause alone, and the pending
condensation — contingent on U8, the last of the four it would
cite — completes the story when export schedules. Text
verbatim as adopted:

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
work is its re-pledging. Text verbatim as adopted:

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

**U3 — Automated testing of something in a VM** — pledged;
moved from the current list 2026-07-23 (owner:
implemented-only). The programmatic loop itself runs
agentlessly on QEMU/DOS today, but the first-class demands —
granular results, selective re-run — ride milestone 8's
properties and milestone 9's exec-run mechanics (in-band file
retrieval, machine variables, the return-not-store run model —
D36).
The preferred guest-agent plane left the numbered arc for the
backlog 2026-07-23 (D33) — a preference this case states, not
a demand it makes: the loop runs agentlessly today, and the
demands that gate delivery are 8's and 9's. U14 supersedes it
**alone** (U15 closed 2026-07-24, D36 — its demands are U14's own
loop). **Both gating milestones have now landed** (milestone 9,
2026-07-24) and U14 moved to the current list with them (D37), so
U3's supersession is due: retiring it is an owner adjudication
under the lifecycle's Retire clause, not a step of that delivery,
and it waits here until made. Text verbatim as adopted:

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

**U5 — Custom installation** — pledged; moved back from the
current list 2026-07-23 (owner: an in-force use case whose
delivery is unscheduled is a real problem — proposed is the
honest state). Its canonical scenario — a customized Windows
install — waits on the unscheduled GUI era (F5); the
parameterization machinery lands at milestone 8 — the
scheduled, U5-citing work that constitutes its pledge,
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

**U6 — Author a script by doing the task once** — pledged in
residue only; moved back from the current list 2026-07-23
(owner, confirming the delivery-gate flag): the recorder —
U6's whole delivery — sits unscheduled in proposed/FEATURES.md's Horizon,
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
