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
> and the pledged proposals under the interface-change rule
> ([planning/INTERFACES.md](planning/INTERFACES.md)); proposed
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
interface changes arrive as proposed amendments to it (see the
[interface-change rule](planning/INTERFACES.md#the-rule)),
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
  says, in effect, "I'd like to install FreeBSD" — and ends with
  a usable sandbox machine. Easy is the requirement: the
  command-line syntax stays terse and succinct, and the blueprint
  and install recipe are easy to find, point to, and use. From a
  clean home this is one short command
  (`rlq run-script install --blueprint freedos`), and that one
  command is the whole of the claim — it composes finding and
  seeding the blueprint (U11), acquiring and verifying its media
  (U13), and driving the installer end to end (U12) into a single
  keystroke-free journey. Keeping the machine afterward is a
  separate journey and a separate demand (U8).

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
  openbsd — and finds it with minimal effort: search or list
  the codex, read a description, seed the blueprint (its
  media and scripts included) into their own library as
  ordinary files they own from then on.

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
  product** — a value the run produced, and the specific file
  the caller asked Reliquary to hand back — delivered across the
  seam to the caller; Reliquary's own run output is *evidence*,
  never the product. The loop is tight: per-run selection goes
  in as properties, granular results come out as the caller's
  own files and values, and re-running one step or the whole
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
