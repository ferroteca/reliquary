<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Use cases

> **Status:** the use-case list, in force. Together with the
> architectural principles ([ARCHITECTURE.md](ARCHITECTURE.md))
> and the specifications ([docs/spec/](docs/spec/)) it forms the
> project's **vision** — the standing statement of what Reliquary
> is and is for. Interface decisions are weighed against this list
> and the pledged proposals under the surface-change rule
> ([planning/SURFACES.md](planning/SURFACES.md)); proposed
> changes are tracked in
> [planning/proposed/USE-CASES.md](planning/proposed/USE-CASES.md) and
> land here only when delivered — every use case here is met
> by the code today, and a settled use case with unimplemented
> demands lives there instead, with no placeholder here (the
> shared U-namespace keeps its citations valid). When this
> list and a planning document disagree, the architectural
> principles and this list govern.

Interface decisions are weighed against these. They are numbered
so a decision, review, or spec section can cite the use case it
serves — and so a proposed change can be rejected by naming the
use case it costs. This list is the decision surface: significant
surface changes arrive as proposed amendments to it (see the
[surface-change rule](planning/SURFACES.md#the-rule)),
drafted and tracked in
[planning/proposed/USE-CASES.md](planning/proposed/USE-CASES.md), and
moved here when delivered — the move to
[planning/pledged/USE-CASES.md](planning/pledged/USE-CASES.md) is
the pledge; delivery makes it current.

This list is an implementation claim: every use case here is
met by the code as it stands today, in full. A use case with
any unimplemented demand — however settled — lives in the
proposals doc instead, and moves here only when its delivery
lands. That claim is why this file sits at the repository root
beside [ARCHITECTURE.md](ARCHITECTURE.md) rather than under
`planning/`: both describe current reality, and neither is a
plan.

**The landing bar** (owner, 2026-07-29): a use case lands here
fully flushed. Every surface it names is delivered exactly as
written, and a case authored as a worked journey — a summary of
what it achieves plus the numbered steps that achieve it — reads
as a precise recipe: a user follows it as written, over public
surfaces, to accomplish the goal. Nothing here may lean on an
undelivered piece — a proposed or pledged case flags such steps
by the pledged feature they require, and no flag can survive to
this list, because the feature's handle evaporates on the very
delivery that makes the case current. The implementation claim
above is therefore step-checkable for a journey case: every
call, field, and refusal it names exists as written.

**The steps are the minimum, not the menu**: a journey lists the
fewest steps that reach the goal, and a step that can be removed
with the goal still met belongs in a guide instead. Options,
alternatives, and the reasons behind each choice are a cookbook's
job; the case states the claim and the shortest true path to it.
A case never states its own success signal either — completing
the path *is* success.

**A use case is the happy path.** It describes the simple path a
user follows to reach the goal, and nothing else: no branches, no
failure handling, no recovery. A use case is not code, and the
paths it omits are not paths the application may neglect — what a
surface does when the happy path does not hold is specified
elsewhere, and specified normatively. A deviation worth stating
at this level has two homes. Where it is *itself a goal someone
pursues*, it becomes **its own use case** — U1's "keeping the
machine afterward" is U8. Where it is *a rule every surface
obeys*, it becomes an **architectural principle** — P11, a gap
names itself; P10, nothing about a guest is guessed — which is
the usual home but not a required one: the four error classes are
a normative spec (D58) rather than a P-number. What a deviation
never becomes is a clause inside a use case.

**Cases compose, through named preconditions.** A journey may
start where another ends: it names the case that gets the user
there — "Precondition: a seeded blueprint (U11)" — rather than
repeating its steps, and the minimum test applies to what is
left. A precondition is always a case in force, never a paragraph
of narrative, and it may name the one command that satisfies it;
if satisfying it takes more than one, that is a chain of cases
rather than a precondition. Where the composite claims something
no single case does — that the whole chain is short, say — the
composing case's summary states it, because a claim no case's
text carries is a claim the list does not make.

A use case in force is never changed in nature (a proposed
one may still be reshaped freely in the proposals doc). It
may be
**clarified** — an in-place wording edit no past citation would
read differently under; clarify, never change, and an
undelivered clarification may park in the proposals doc — or
**retired**: dropped without
replacement, or **superseded** by one or more new use cases that
carry the need forward in a changed shape. Numbers are permanent
and never reused; proposals share this global namespace and keep
their numbers when they move here. A retired use case leaves
this list entirely — no stub, the same as an undelivered one:
its retirement is recorded in [planning/DECISIONS.md](planning/DECISIONS.md), its
full text survives in git history, and successors name the
number they superseded.

- **U1 — Install a sandbox VM from the CLI, easily.** A user
  decides, in effect, "I'd like to install FreeDOS" — and ends with
  a usable sandbox machine. Easy is the requirement: the
  command-line syntax stays terse, and the blueprint and install
  recipe are easy to find, point to, and use. From a clean home
  the whole journey is **two commands** — copy the blueprint out
  (U11), then run its install script — and the install itself is
  keystroke-free, composing the media acquisition (U13) and the
  unattended install (U12) that the copied recipe describes.
  **Nothing arrives from the built-in library without being asked
  for by name** (P4, P18), so what runs is a file they chose and
  own. Keeping the machine afterward is a separate journey and a
  separate demand (U8).

  Precondition: the blueprint copied out of the library —
  `rlq seed-blueprint freedos` (U11).

  1. **Install.** `rlq run-script install --blueprint freedos` —
     creates the machine, fetches and hash-verifies the LiveCD,
     drives the installer to completion, and powers the guest off.
     No keystroke at any point.
  2. **Use it.** `rlq start-machine --blueprint freedos --display`
     — the sandbox on screen, FreeDOS installed and ready to go.

- **U4 — A precisely defined test VM, shared through version
  control.** A developer is writing a program that cannot be
  tested in the work environment — it needs a VM, perhaps running
  a proprietary OS like Windows. The test machine must be
  precisely defined, yet nothing proprietary can be distributed:
  the repository carries only blueprints (media included) and
  Reliquary scripts. Another developer picks up the work
  supplying just the two things the repository cannot provide —
  the Windows install ISO and its license — and the checked-in
  definitions provide everything else needed to build the test
  VM, the media hashes verifying theirs is the exact build the
  scripts target. The checked-in artifacts are source: Reliquary
  uses them from the repository in place — nothing is copied into
  a Reliquary home to make them run. The machine is somewhat expensive to build, so
  the developer keeps it for the duration of the work cycle
  rather than tossing it eagerly; day to day, the tests run
  inside it through U14's loop — the same tool that built the rig
  automates the testing in it. When truly finished, the developer
  disposes of the large VM and reclaims the disk space.

- **U9 — Automate from a language without a binding.** A
  consuming project's harness is Java, C#, Go, or shell — no
  Python, no native Reliquary binding. It still gets
  everything through the CLI: every capability invocable,
  observable, and parseable from a program — results on
  stdout, diagnostics on stderr, exit codes by class,
  machine-readable output as timely as the pretty rendering,
  and no hidden prompt ever hanging a pipeline. A native
  binding, where one exists for the language, is the same
  surface with types; nothing is CLI-only or binding-only.

- **U11 — Find and seed a codex blueprint, easily.** A user
  at the keyboard wants a starting point — freedos,
  openbsd — and finds it with minimal effort: list the codex,
  read a description, seed the blueprint (its media and
  scripts included) into their own library as ordinary files
  they own from then on.

- **U12 — An unattended install, end to end.** From standard
  vendor media, a script drives the installer the whole way —
  menus, partitioning, reboots, media swaps — with no hand on
  the keyboard, ending in a usable machine. A run this long
  shows where it is and what it is waiting for while it goes.

- **U13 — Media fetches and verifies itself.** A blueprint
  names its media and pins it by hash; Reliquary acquires
  it — download, extract, cache — and verifies it is exactly
  the build the scripts target. The user never hand-places a
  file in Reliquary's caches, and a wrong or changed payload
  fails closed by name.

- **U14 — Drive a machine from a program.** An agent — a test
  harness, a CI driver, an AI coding agent — drives a machine
  from its own code, through a native binding or the CLI: it
  places input into the guest, runs work, reads results back,
  iterates, and closes the machine down. The **result is the
  product** — a value the run produced — delivered across the
  seam to the caller; Reliquary's own run output is *evidence*,
  never the product. **A file is the caller's own to move.**
  Reliquary carries values across the seam and supplies the
  drives a file crosses on — a host directory declared as a
  drive, a medium swapped live (U20), the machine directory
  handed back — but it does not reach into a drive to read or
  write one, and it maps no volume to a guest letter; a caller
  wanting a file out opens the drive itself, with its own tools.
  The loop is tight: per-run selection goes
  in as properties, granular results come out as values and as
  the caller's own media, and re-running one step or the whole
  task is first-class. Reliquary supplies the mechanics and
  attaches no meaning to any of it — the computation, the result
  parsing, and any reusable scripting are the caller's or
  another project's, never Reliquary's. The canonical journey
  uses Reliquary twice: build the rig (U16), then automate the
  work inside it; often nothing durable remains but the
  retrieved result.

- **U20 — Iterate against a live machine by swapping media.**
  The programmatic drive of U14, but the machine stays *up*
  across rounds: an agent mounts a disk image it built — a test
  binary on a floppy — runs it, reads the results, unmounts,
  rebuilds the image with the next binary, and mounts again, all
  live, no reboot between rounds. Reliquary supplies the live
  media swap (`insert-media`/`eject-media` over the running
  machine) and attaches no meaning; the consumer owns the images
  and the host-side tooling that builds and reads them. This is
  the fast *agentless* loop — no guest agent, no stop/start per
  round — and its price is the consumer's: whole-image
  granularity and the medium's size. The retrieved result is the
  product, exactly as U14; only the transport differs, chosen
  when reboot-per-round is the bottleneck.

- **U21 — Parameterize a blueprint, and keep the secret out of
  it.** A blueprint's author foresees what its users will
  change — a login name, a product key, which supplemental
  disk — and designs the seam in: the blueprint answers the
  properties its scripts declare, either by fixing a value
  directly, so every machine built from it gets that value, or by
  naming a property each user defines locally, so the blueprint
  carries the key and never the value. That second binding is what
  a license key needs. It is never checked into source control, so
  Reliquary holds it on the host and retrieves it at use — a
  secret's value never enters the properties file either, which
  leaves the blueprint and that file both shareable and
  versionable. This is U4's model applied to values: the artifact
  defines everything except what it must not contain. The design
  beats a user's standing defaults; an explicit per-run value
  beats the design; and nothing reaches a script that did not
  declare the key.

- **U24 — Install from a medium, and keep a blueprint that
  describes the machine.** An install takes two boots — the
  medium first, the disk once it is bootable — and the author
  automating it has to say which is which. Written into the
  blueprint, that arrangement outlives the install it was for: the
  definition says the machine boots its CD-ROM first, forever, and
  says it to everyone the definition is shared with (U4). Written
  into the script instead, the blueprint goes on stating what the
  machine *is* while the install states what the install *does*,
  and the machine that comes out boots its disk under the
  blueprint's own order — on whatever backend the host provides
  (U7), without the author knowing which firmware will skip a
  device it cannot boot.

  Precondition: the blueprint copied out of the library —
  `rlq seed-blueprint <name>` (U11).

  1. **Declare the machine.** In the blueprint, the drives it has
     and the order it boots in ordinary use — the disk ahead of an
     empty optical slot: `"boot": ["hdd0", "cdrom0"]` with
     `"cdrom0": null`.
  2. **Put the install's boot arrangement in the install.** In the
     script, enclose the phases that drive the installer and name
     what they boot — `with boot cdrom0 { … }` — inserting the
     medium as those phases begin.
  3. **Run it.** `rlq run-script install --blueprint <name>`.

- **U25 — Automate a guest that paints in its own font.** A script
  waits for text the author can plainly see on the screen, and the
  wait never matches. The guest has loaded a face of its own — a
  prepared codepage, a localized shell — and the screen is being
  read against the fonts the *host's* hypervisor installed, which
  do not include it; the run ends at a timeout saying how much of
  the screen could not be read. The guest is the only party that
  knows what it loaded, and wherever a script can reach a prompt it
  can be asked: the face comes out of the running guest, is kept as
  an asset of its own, and is named from the point in the run where
  the guest takes the screen over — the firmware painted the
  earlier screens, and painted them in a different face. From there
  the wait matches the text that was on the screen all along, and
  the guest automates on any host that will run it (U7).

  Precondition: an installed machine (U12), and the dumper copied
  out of the library — `rlq seed-script freedos-dump-font` (U11).

  1. **Give the machine somewhere to put the dump.** In the
     blueprint, a drive whose media is a host directory — the drive
     the file crosses on, with nothing of Reliquary's inside it
     (U14) — and `rlq apply-blueprint --blueprint <name>`, which is
     what hands the stopped machine a drive its blueprint gained.
  2. **Ask the guest for the font it loaded.** `rlq run-script
     freedos-dump-font --blueprint <name>`: it boots to a prompt,
     reads the live glyph table, writes it to that drive as
     `FONT.BIN`, and powers the machine off. The 4096 bytes are in
     the author's own directory when the run returns.
  3. **Declare what the bytes cannot say.** `guest.rlqf` in the
     fonts directory — the cell size, and the codepage the bank's
     indices mean — with the dumped file beside it as `guest.bin`.
  4. **Name it where the guest takes the screen over.** In the
     script, `font @guest` at the phase that follows the guest's
     own font load: the font named is tried first and the host's
     follow.
  5. **Run the script.** `rlq run-script <script> --blueprint
     <name>`.

- **U26 — Iterate on an install script without repairing the
  machine between attempts.** Writing an install script is a loop
  of failed runs: a wait whose screen never arrives, a menu that
  moved, a timeout a slower host blows through. Each failure
  leaves the machine part-installed, which is what the author
  wants to look at — but if it also leaves behind the arrangements
  the *script* made to get there, the medium it inserted and the
  device it told the machine to boot, then the next attempt starts
  from a machine that is no longer the one the blueprint
  describes, and every retry is preceded by a repair. This case
  makes the retry the next thing the author does: what the script
  arranged is put back when its run ends, whether it ended by
  finishing or by failing, so a change to the script is the only
  thing that differs between two attempts. What the *guest* did is
  not an arrangement and stays — the installer's writes to the
  disk are the run's own product, and how far it got is the
  evidence.

  Precondition: the blueprint copied out of the library —
  `rlq seed-blueprint <name>` (U11).

  1. **Run the script.** `rlq run-script install --blueprint
     <name>`. It fails partway, returning the failure report and
     screenshot that say what it was waiting for.
  2. **Power the machine off.** `rlq stop-machine --blueprint
     <name>` — the script declares `machine stopped`, and a guest
     left mid-install is still running.
  3. **Change the script and run it again.** The same
     `rlq run-script` command: the medium the failed attempt
     inserted is out of the drive, and the boot arrangement it made
     is off the machine.

- **U27 — Automate an installer that paints in its own font.** An
  installer paints its first screen in a face of its own and never
  offers a prompt to ask about it: there is no moment in that boot
  when the guest could be asked what it loaded, and the run ends at
  a timeout saying how much of the screen could not be read. The
  author holds the face — it came off the installer's own media, or
  off a guest of the same build — and states it as the font the
  screen is read through from the point the installer takes the
  screen over, the firmware having painted what came before in a
  different one. From there the wait matches the text that was on
  the screen all along.

  Precondition: the blueprint copied out of the library —
  `rlq seed-blueprint <name>` (U11).

  1. **Declare the face, and what its bytes cannot say.**
     `installer.rlqf` in the fonts directory — the cell size, and
     the codepage its indices mean — with the font file beside it
     as `installer.bin`.
  2. **Name it where the installer takes the screen over.** In the
     script, `font @installer` at the phase where the installer's
     own screens begin: the font named is tried first and the
     host's follow.
  3. **Run the install.** `rlq run-script install --blueprint
     <name>`.
