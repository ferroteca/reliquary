<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Use cases

> **Status:** this is the current list of use cases — things Reliquary
> can already do. Together with the architectural principles
> ([ARCHITECTURE.md](ARCHITECTURE.md)) and the specifications
> ([docs/spec/](docs/spec/)), it lays out what Reliquary is and what
> it's for. When we decide how an interface should work, we check it
> against this list and against the proposals already pledged under
> the surface-change rule ([planning/SURFACES.md](planning/SURFACES.md)).
> Proposed changes are tracked in
> [planning/proposed/USE-CASES.md](planning/proposed/USE-CASES.md) and
> only move here once they're delivered — every use case on this page
> is something the code does today. A use case that's been agreed to
> but isn't fully built yet stays on the proposed list instead; we
> don't leave a placeholder here for it, because U-numbers are shared
> across all three lists, so a citation to it still works. If this
> list and a planning document ever disagree, the architectural
> principles and this list win.

We check interface decisions against these use cases. Each one has a
number, so a decision, a review, or a section of a spec can point to
the use case it serves — and so a proposed change can be turned down
by naming the use case it would break. This list is where those
decisions get made: any significant change to it starts as a proposal
(see the [surface-change rule](planning/SURFACES.md#the-rule)),
drafted and tracked in
[planning/proposed/USE-CASES.md](planning/proposed/USE-CASES.md).
From there it moves to
[planning/pledged/USE-CASES.md](planning/pledged/USE-CASES.md) once
we commit to it, and moves here once it's actually built.

Every use case on this page is a claim: the code meets it today, in
full. A use case with any part still unbuilt — even if we've fully
agreed to it — stays in the proposals doc instead, and only moves
here once that part is delivered. That's also why this file sits at
the repository root next to [ARCHITECTURE.md](ARCHITECTURE.md)
rather than under `planning/`: both describe how things are right
now, not what's planned.

**The bar for landing here** (owner, 2026-07-29): a use case only
lands on this list once it's fully done. Everything it names is
delivered exactly as written. A use case written as a worked
journey — a short summary of what it achieves, plus the numbered
steps to get there — has to work as a precise recipe: a user can
follow it, step by step, over Reliquary's real interfaces, and
reach the goal. None of it can lean on something not yet built —
a proposed or pledged use case can flag a step as depending on a
feature that isn't delivered yet, but that flag has to be gone by
the time the case lands here, because once the feature ships the
flag has nothing left to point at. So for a journey-style case,
the "delivered in full" claim above is literally checkable: every
command, field, and error it names actually exists as written.

**The steps are the minimum, not a menu of options.** A journey
lists the fewest steps needed to reach the goal. If a step can be
dropped and the goal is still reached, it belongs in a guide, not
here. Explaining the alternatives, or why one choice was made over
another, is a cookbook's job — a use case just states the goal and
the shortest real path to it. It also never says how you'd know
you succeeded; reaching the end of the path *is* success.

**A use case only covers the happy path.** It describes the
straightforward way a user reaches the goal — no branches, no
error handling, no recovery. That doesn't mean the application is
free to ignore everything else; it just means those other paths
are specified somewhere else, and specified as firm rules, not
left to guesswork. When something outside the happy path is
important enough to write down at this level, it goes in one of
two places. If it's something a user actually sets out to do, it
becomes **its own use case** — the part of U1 about keeping the
machine afterward became U8. If it's a rule every interface has to
follow, it becomes an **architectural principle** instead — for
example P11 ("a gap names itself") or P10 ("nothing about a guest
is guessed"); that's the usual home, though not the only one — the
four error classes are written up as a normative spec (D58)
rather than as a numbered principle. What it never becomes is an
extra clause bolted onto a use case.

**Use cases can build on each other, through named preconditions.**
One journey can pick up where another leaves off: instead of
repeating the earlier case's steps, it just names it — for example
"Precondition: a seeded blueprint (U11)" — and the minimum-steps
rule applies only to what's left. A precondition always points to
a use case that's actually in force, never to a paragraph of
backstory, and it may name the single command that satisfies it.
If satisfying it actually takes more than one command, that's a
chain of use cases, not a precondition. And if the combined
journey claims something neither case claims on its own — that
the whole chain is short, say — that claim has to be stated
explicitly in the combining case's summary, because a list only
claims what its text actually says.

Once a use case is on this list, what it actually means never
changes (a proposal that hasn't landed yet can still be reworked
freely in the proposals doc). What can happen to a use case here
is one of three things. It can be **clarified** — a wording fix
that no past citation would read any differently under; that's
editing the words, not the meaning, and an unfinished clarification
can sit in the proposals doc until it's ready. It can be
**retired** — dropped with nothing replacing it. Or it can be
**superseded** — replaced by one or more new use cases that carry
the same need forward in a new shape. Numbers are permanent and
never reused: a proposal keeps its number when it moves here,
since all three lists share the same numbering. A retired use
case is removed from this list entirely, with no stub left behind
— the same as a use case that was never delivered. Its retirement
is recorded in [planning/DECISIONS.md](planning/DECISIONS.md), its
full text still lives in git history, and whatever replaces it
names the number it superseded.

- **U1 — Install a sandbox VM from the CLI, easily.** A user
  decides "I'd like to install FreeDOS" — and ends up with a
  working sandbox machine. It has to be easy: short commands, and
  a blueprint and install recipe that are easy to find, point to,
  and use. Starting from a clean home directory, the whole thing
  takes **two commands** — copy the blueprint out (U11), then run
  its install script — and the install itself needs no keystrokes
  from the user. It fetches the media (U13) and runs the
  unattended install (U12) that the copied recipe describes.
  **Nothing from the built-in library runs unless the user asks
  for it by name** (P4, P18), so what runs is a file they chose
  and now own. Keeping the machine afterward is a separate need,
  covered by its own use case (U8).

  Precondition: the blueprint copied out of the library —
  `rlq seed-blueprint freedos` (U11).

  1. **Install.** `rlq run-script install --blueprint freedos` —
     creates the machine, fetches and hash-verifies the LiveCD,
     drives the installer to completion, and powers the guest off.
     No keystroke at any point.
  2. **Use it.** `rlq start-machine --blueprint freedos --display`
     — the sandbox on screen, FreeDOS installed and ready to go.

- **U4 — A precisely defined test VM, shared through version
  control.** A developer is writing a program that can't be tested
  in their normal work environment — it needs a VM, maybe one
  running a proprietary OS like Windows. The test machine has to
  be defined precisely, but nothing proprietary can be checked in:
  the repository only holds blueprints (which describe the media)
  and Reliquary scripts. A second developer can pick up the work
  by supplying just the two things the repository can't provide —
  the Windows install ISO and its license. Everything else needed
  to build the test VM comes from the checked-in files, and the
  media's hashes confirm it's exactly the build the scripts expect.
  The checked-in files are used straight from the repository —
  Reliquary doesn't copy them into its own home directory to run
  them. Building the machine is somewhat expensive, so the developer
  keeps it around for the whole work cycle instead of throwing it
  away right after use; day to day, tests run inside it through
  U14's loop, using the same tool that built the machine to
  automate testing in it. When the work is truly done, the
  developer deletes the large VM and gets the disk space back.

- **U9 — Automate from a language without a binding.** A project's
  test harness is written in Java, C#, Go, or shell — no Python,
  no native Reliquary binding for that language. It can still use
  everything through the CLI: every capability can be called,
  watched, and parsed from a program — results on stdout,
  diagnostics on stderr, exit codes that identify the kind of
  failure, and machine-readable output available just as quickly
  as the human-readable version, with no hidden prompt ever
  hanging a pipeline. Where a native binding exists for a
  language, it offers the same surface with proper types; nothing
  is CLI-only, and nothing is binding-only.

- **U11 — Find and seed a codex blueprint, easily.** A user at the
  keyboard wants a starting point — freedos, openbsd — and can get
  one with almost no effort: list the codex, read a description,
  and seed the blueprint (media and scripts included) into their
  own library, where it's now an ordinary file they own.

- **U12 — An unattended install, end to end.** Starting from
  standard vendor media, a script drives the installer the whole
  way through — menus, partitioning, reboots, swapping media —
  with no hand on the keyboard, and ends with a usable machine.
  Since a run like this takes a while, it shows where it is and
  what it's waiting for as it goes.

- **U13 — Media fetches and verifies itself.** A blueprint names
  its media and pins it to a specific hash. Reliquary fetches
  it — downloads, extracts, and caches it — and checks that it's
  exactly the build the scripts expect. The user never has to
  place a file in Reliquary's caches by hand, and if the file is
  wrong or has changed, the run stops and says which file failed.

- **U14 — Drive a machine from a program.** Some caller — a test
  harness, a CI driver, an AI coding agent — drives a machine from
  its own code, through a native binding or the CLI: it puts input
  into the guest, runs the work, reads the results back, repeats as
  needed, and shuts the machine down. **The result the run
  produces is the product** the caller wants; Reliquary's own run
  output is just evidence of what happened, never the product
  itself. **A file belongs to the caller, and moving it is the
  caller's job.** Reliquary carries values back to the caller and
  provides the drives a file can cross on — a host directory
  declared as a drive, a medium swapped in live (U20), the machine
  directory handed back — but it never reaches into a drive to
  read or write a file itself, and it never maps a drive to a
  guest letter for you. A caller who wants a file out opens the
  drive with their own tools. The loop stays tight: per-run
  settings go in as properties, detailed results come back as
  values and as the caller's own files, and re-running one step —
  or the whole task — is easy to do. Reliquary just supplies the
  mechanics and doesn't interpret any of it: the computation, the
  parsing of results, and any reusable scripting belong to the
  caller or another project, never to Reliquary. The typical
  journey uses Reliquary twice: build the machine (U16), then
  automate the work inside it. Often nothing is left behind
  afterward except the result the caller retrieved.

- **U20 — Iterate against a live machine by swapping media.** This
  is U14's programmatic drive, except the machine stays running
  across rounds: an agent mounts a disk image it built — say a test
  binary on a floppy — runs it, reads the results, unmounts it,
  rebuilds the image with the next binary, and mounts it again, all
  without a reboot in between. Reliquary provides the live media
  swap (`insert-media`/`eject-media` on the running machine) and
  doesn't interpret what's on it; the caller owns the images and
  the host-side tooling that builds and reads them. This is the
  fast, *agentless* loop — no guest agent needed, no stopping and
  starting the machine each round — but it comes at a cost the
  caller pays: you can only swap a whole image at a time, and
  you're limited by the medium's size. The result retrieved is the
  product, just as in U14; only how it gets there differs, and
  it's worth choosing when rebooting each round is what's slowing
  you down.

- **U21 — Parameterize a blueprint, and keep the secret out of
  it.** A blueprint's author knows ahead of time what its users
  will need to change — a login name, a product key, which extra
  disk to use — and builds that flexibility in: the blueprint
  fills in the properties its scripts ask for, either by fixing a
  value directly (so every machine built from it gets that same
  value), or by naming a property that each user sets locally (so
  the blueprint carries the property's name but never its value).
  That second option is what a license key needs. A license key is
  never checked into source control; instead Reliquary keeps it on
  the user's own host and looks it up when needed. The value never
  even enters the properties file, so both the blueprint and that
  file stay safe to share and to check in. This is the same idea
  as U4, applied to values instead of files: the artifact defines
  everything except the one thing it must not contain. If there's
  a value set in the blueprint, it wins over a user's own defaults
  — but a value the user sets explicitly for one run wins over
  that. And a script never sees a value for a key it didn't ask
  for.

- **U24 — Install from a medium, and keep a blueprint that
  describes the machine.** An install boots twice — once from the
  install medium, then from the disk once it's bootable — and
  whoever writes the install script has to say which device boots
  first at each stage. If that boot order is written into the
  blueprint, it outlives the install: the blueprint would go on
  saying the machine boots its CD-ROM first forever, and would say
  that to everyone the blueprint is shared with (U4). Written into
  the script instead, the blueprint keeps describing what the
  machine normally *is*, while the script describes what the
  install *does* — and the finished machine boots from its disk in
  the blueprint's own normal order, on whatever backend the host
  happens to provide (U7), even though the author has no way of
  knowing which firmware will skip a device it can't boot from.

  Precondition: the blueprint copied out of the library —
  `rlq seed-blueprint <name>` (U11).

  1. **Declare the machine.** In the blueprint, list the drives it
     has and the order it boots in normal use — disk first, then
     an empty optical drive: `"boot": ["hdd0", "cdrom0"]` with
     `"cdrom0": null`.
  2. **Put the install's own boot order in the script.** In the
     script, wrap the phases that drive the installer and name
     what they boot from — `with boot cdrom0 { … }` — inserting
     the medium as those phases start.
  3. **Run it.** `rlq run-script install --blueprint <name>`.

- **U25 — Automate a guest that paints in its own font.** A script
  waits for text that the author can plainly see on the screen, but
  the wait never matches. The guest has loaded its own look — a
  different codepage, a localized shell — so the screen is being
  read against the fonts the *host's* hypervisor installed, which
  don't include that one. The run ends in a timeout, reporting how
  much of the screen it couldn't read. Only the guest itself knows
  what font it loaded, but anywhere a script can reach a prompt, it
  can ask: it pulls the font out of the running guest, saves it as
  its own asset, and names the point in the run where the guest
  takes over painting the screen — before that, the firmware
  painted the screen in a different font. From that point on, the
  wait matches the text that was there all along, and it works on
  any host that can run the guest (U7).

  Precondition: an installed machine (U12), and the font-dumping
  script copied out of the library —
  `rlq seed-script freedos-dump-font` (U11).

  1. **Give the machine somewhere to put the dump.** In the
     blueprint, add a share whose media is a host directory — the
     device a file crosses on, with nothing of Reliquary's own
     inside it (U14) — then run `rlq apply-blueprint --blueprint
     <name>`, which gives the stopped machine the share the
     blueprint just gained.
  2. **Ask the guest for the font it loaded.** `rlq run-script
     freedos-dump-font --blueprint <name>` boots to a prompt, reads
     the live glyph table, writes it to that share as `FONT.BIN`,
     and powers the machine off. The 4096 bytes are sitting in the
     author's own directory once the run finishes.
  3. **Write down what the raw bytes don't say.** Create
     `guest.rlqf` in the fonts directory, stating the cell size and
     the codepage the glyph indices mean, with the dumped file
     beside it named `guest.bin`.
  4. **Name it at the point the guest takes over the screen.** In
     the script, add `font @guest` at the phase right after the
     guest loads its own font: that font is tried first, and the
     host's fonts are tried after it.
  5. **Run the script.** `rlq run-script <script> --blueprint
     <name>`.

- **U26 — Iterate on an install script without repairing the
  machine between attempts.** Writing an install script means a
  loop of failed runs: a wait for a screen that never shows up, a
  menu that moved, a timeout a slower host blows through. Each
  failure leaves the machine partly installed, which is exactly
  what the author wants to look at. But if the failure also leaves
  behind what the *script* set up to get there — the medium it
  inserted, the device it told the machine to boot from — then the
  next attempt starts from a machine that no longer matches what
  the blueprint describes, and every retry needs a manual repair
  first. This use case makes the retry the very next thing the
  author does: whatever the script set up is put back the way it
  was when the run ends, whether the run finished or failed, so
  changing the script is the only difference between one attempt
  and the next. What the *guest itself* did during the run isn't
  touched — the installer's writes to disk are the run's actual
  product, and how far it got is the evidence of what worked.

  Precondition: the blueprint copied out of the library —
  `rlq seed-blueprint <name>` (U11).

  1. **Run the script.** `rlq run-script install --blueprint
     <name>`. It fails partway through, returning a failure report
     and a screenshot showing what it was waiting for.
  2. **Power the machine off.** `rlq stop-machine --blueprint
     <name>` — the script declares `machine stopped`, and a guest
     left mid-install is still running.
  3. **Change the script and run it again.** The same
     `rlq run-script` command: the medium the failed attempt
     inserted has been taken back out of the drive, and the boot
     order it set has been removed from the machine.

- **U27 — Automate an installer that paints in its own font.** An
  installer paints its first screen in its own font and never gives
  a prompt where the guest could be asked about it — there's no
  point in that boot to ask what it loaded, so the run just ends in
  a timeout, reporting how much of the screen it couldn't read. The
  author already has the font on hand — pulled from the installer's
  own media, or from a guest built the same way — and declares it
  as the font to read the screen with, starting from the point the
  installer takes over painting the screen; before that point, the
  firmware painted the screen in a different font. From there on,
  the wait matches the text that was on the screen all along.

  Precondition: the blueprint copied out of the library —
  `rlq seed-blueprint <name>` (U11).

  1. **Declare the font, and what its raw bytes don't say.** Create
     `installer.rlqf` in the fonts directory, stating the cell size
     and the codepage its glyph indices mean, with the font file
     beside it named `installer.bin`.
  2. **Name it at the point the installer takes over the screen.**
     In the script, add `font @installer` at the phase where the
     installer's own screens begin: that font is tried first, and
     the host's fonts are tried after it.
  3. **Run the install.** `rlq run-script install --blueprint
     <name>`.

- **U28 — Give a machine a real network path, and say whether it
  faces the host or the LAN.** A machine that needs network access —
  to reach an installer's own file server (docs/spec/http-serve.md),
  to join a game's IPX/TCP session, to be reachable from another
  machine on the LAN — needs a NIC declared, not just implied by
  whatever a backend happens to default to today. Whether that NIC
  should be host-only (`nat`, the same path the install server
  already uses) or visible to the wider network (`bridged`) is a
  fact about what the machine is *for*, so the blueprint states it
  directly. Which chipset actually drives the connection defaults to
  a platform default (`pcnet`), the same way a drive's `controller`
  defaults to `ide` without being named (P10) — but DOS-era
  networking software is often written against one specific chipset,
  not "a network card" in the abstract (packet drivers above all), so
  naming a `model` explicitly is how a blueprint reaches software the
  default chipset's driver can't talk to.

  Precondition: the blueprint copied out of the library —
  `rlq seed-blueprint <name>` (U11).

  1. **Declare the attachment.** In the blueprint's `devices`
     section, name how the NIC reaches the world:
     `"devices": {"net0": "nat"}`, or `{"net0": "bridged"}` to put
     it on the host's own network — naming a specific host interface
     with `{"net0": {"attachment": "bridged", "interface":
     "${host-nic}"}}` when the default isn't the right one.
  2. **Name the chipset, if the driver on hand needs a specific one.**
     `{"net0": {"attachment": "nat", "model": "ne2k"}}` for software
     that only ships an NE2000 packet driver. Leave `model` out and
     the platform default applies.
  3. **Run it.** `rlq create-machine --blueprint <name>` or
     `rlq run-script install --blueprint <name>`. An attachment or a
     model the assigned backend can't provide fails closed at
     materialization, naming both (P11).
