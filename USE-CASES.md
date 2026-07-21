<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Primary use cases

> **Status:** the primary use-case list — the decision surface of
> reliquary's guiding principles,
> [INTERFACES.md](INTERFACES.md). Interface decisions are weighed
> against this list under the interface-change rule there;
> amendments are argued through that rule and land here. When
> this list and ROADMAP.md disagree, the guiding principles and
> this list govern.

Interface decisions are weighed against these. They are numbered
so a decision, review, or spec section can cite the use case it
serves — and so a proposed change can be rejected by naming the
use case it costs. This list is the decision surface: significant
interface changes arrive as proposed amendments to it (see the
[interface-change rule](INTERFACES.md#the-interface-change-rule)),
and amendments are made deliberately and recorded here.

- **U1 — Install a sandbox VM from the CLI, easily.** A user
  says, in effect, "I'd like to install FreeBSD" — and ends with
  a usable sandbox machine, installed unattended from standard
  vendor media, exportable to a hypervisor built for keeping
  machines (e.g. VirtualBox) to take away and use. Easy is the
  requirement: the command-line syntax stays terse and succinct,
  and the blueprint and install recipe are easy to find, point
  to, and use. From a clean home this is one short command
  (`rlq --blueprint freedos-1.4-plain script install`): the
  codex seeds the blueprint, media definition, and
  scripts; media is fetched and hash-verified; the script drives
  the installer end to end — menus, partitioning, reboots, media
  swaps — until the guest is installed.
- **U2 — Import an existing VM as a blueprint.** A user has
  created a VM natively — in VMware, say — and wants to capture
  it as a reliquary blueprint (`import` synthesizes the
  blueprint; realizing it afterward is an ordinary `create`).
  Import reads only a source at rest — a running or suspended
  source VM fails closed naming its state — and the captured
  disk image stays where the native hypervisor keeps it: import
  points a generated media definition at it and never copies,
  moves, or modifies it; a user who wants the image somewhere
  more durable moves it and repoints the definition, which is
  theirs. Two decision points are presented, never defaulted.
  First, whether to take a native snapshot — the one thing
  import may do to the source VM, and only with this consent:
  snapshotted, the blueprint pins the frozen extent and the
  source VM stays free to keep running natively; declined,
  nothing touches the source, but running it again breaks
  verification until re-import. Second, how machines materialize
  from the captured disk: each created machine a full copy of it
  (`duplicate` — the machine's drive stands alone afterward) or
  a differencing disk backed by it (`difference` — the cheapest
  create, but the source must stay byte-identical, and
  verification refuses a machine whose source has since been
  rewritten). The import flow's job is to present these choices,
  not bury them.
- **U3 — Automated testing of something in a VM.** An agent — a
  test harness, a CI driver, an AI coding agent — starts a
  machine, injects a program, executes it, and observes the
  result; possibly iterates (adjust, re-inject, observe again);
  finally closes the VM. The loop is driven programmatically,
  through a native binding or the CLI; computation and result
  interpretation stay on the agent's side of the seam, and
  reliquary stays ignorant of who builds on it. The canonical
  journey uses reliquary twice: first to define and build the
  test VM (U4), then again to automate the testing inside it.
  Concretely: a unit-test suite runs in the guest while the
  host-side automator captures detailed per-test results,
  possibly updates a test object, and re-runs a specific test or
  the entire suite — a tight edit-and-rerun loop, so granular
  results and selective re-run are first-class demands, not
  conveniences. This case is
  probably best served by a native guest-side agent (QGA, VMware
  Tools, Guest Additions, Hyper-V's integration services) — fast
  injection, execution, and observation as a structured control
  plane — while agentless operation remains the permanent
  fallback for
  guests that cannot cooperate, because the thing under test may
  be the very driver that would provide that communication.
  Often nothing durable remains: the run record is the product.
  This use case is dense and will likely be broken out into
  finer use cases as it settles.
- **U4 — A precisely defined test VM, shared through version
  control.** A developer is writing a program that cannot be
  tested in the work environment — it needs a VM, perhaps running
  a proprietary OS like Windows. The test machine must be
  precisely defined, yet nothing proprietary can be distributed:
  the repository carries only blueprints, media definitions, and
  reliquary scripts. Another developer picks up the work
  supplying just the two things the repository cannot provide —
  the Windows install ISO and its license — and the checked-in
  definitions provide everything else needed to build the test
  VM, the media hashes verifying theirs is the exact build the
  scripts target. The checked-in artifacts are source: reliquary
  uses them from the repository in place — nothing is copied into
  a reliquary home to make them run. The machine is somewhat expensive to build, so
  the developer keeps it for the duration of the work cycle
  rather than tossing it eagerly; day to day, the tests run
  inside it through U3's loop — the same tool that built the rig
  automates the testing in it. When truly finished, the developer
  disposes of the large VM and reclaims the disk space.
- **U5 — Custom installation.** A user wants the German version
  of Windows. The codex will not carry such flavors —
  there are too many variants — so it defines one standard
  Windows install. From the CLI the user easily finds that
  standard blueprint, seeds a local blueprint from it, and
  customizes it. The blueprint's author has foreseen this need
  and wrote it with an obvious locale seam; the user changes the
  language to German — preferably in the blueprint, outside the
  script, so the script can stand alone — and proceeds. A user
  name and a license key are equally obvious examples of
  blueprint parameterization — and they show its two bindings:
  some parameters are specified directly in the blueprint, while
  others are only *referred to* there and must be defined
  externally. A license key is never checked into source
  control, so reliquary must provide a mechanism to store it
  locally and retrieve it at use. The same parameter can go
  either way: an automated-testing blueprint may fix its user
  name as "testuser", while "paul" is a value its owner would
  never check in.
- **U6 — Author a script by doing the task once.** A user
  performs the task by hand — going through a Windows install,
  say — in a console session reliquary supervises, and ends with
  a draft script and the image assets (landmarks) to reproduce
  it. reliquary follows the session — every keystroke, click,
  and media swap, and the screen states between them — and
  drafts the wait conditions and actions, capturing the source
  screenshots landmarks crop from. The output is a *draft*:
  ordinary script text (self-contained with its landmarks
  embedded by default, or with factored catalog assets), owned
  and edited like anything hand-written — recording cannot know
  which screen features are load-bearing or how long a step may
  honestly take, so the person tailors what reliquary proposes.
  Tailoring is not a one-way exit: authoring round-trips. When
  the task changes or coverage grows, a later session captures
  the new screens and steps *against the tailored script* —
  playback carries the machine to the point of change, the
  person takes over and demonstrates, and reliquary proposes
  the new fragment and assets without disturbing what the
  author wrote. A changed screen for an unchanged step is an
  asset refresh — a new landmark variant in the catalog — and
  touches the script not at all. The session machine is as
  disposable as any other; the script and assets are the
  product. (The authoring parallel to U2: import captures a
  machine built by hand; recording captures a procedure
  performed by hand.) This use case is dense and will likely be
  broken out into finer use cases as it settles.

Beneath them all sits the ephemeral-machine principle: machines
are cheap to destroy and rebuild, and the machine is never the
product (ROADMAP.md, "Vision"). Across them runs a control-plane
arc: agentless operation is at its most useful preparing a
machine — installing the OS (U1) and bringing the guest to the
point where an agent exists inside it — and for testing
installations themselves, openQA-style, where the install is the
thing under test and the screen is the assertion surface. Once a
guest holds an agent, that agent is the better work plane (U3);
agentless remains the permanent fallback for guests that can
never cooperate. reliquary consumes native guest agents and
never builds its own: agents may not exist for some operating
systems, but writing one would be a whole project unto itself,
outside reliquary's scope.

Alongside it runs an artifact-residency split. Assets in the
reliquary home are a convenience for human CLI interaction: users
get a convenient home for shared assets — blueprints, media
definitions, and scripts reused across human-interaction
scenarios — seeded by the codex (U1, U5). The other side of the
coin: for automation, media definitions, scripts, blueprints,
and landmark assets are source code artifacts — they belong to
the consuming project, live in its source control, and never
live in reliquary's home (U3, U4). The codex is *never* used for machine
automation — that would be a trap: a blueprint changing outside
the project's source control breaks the project. For automation
the library is at most a place to copy a first draft from; the
copy is committed into the project and evolves there. The first
drafts are likely generated by a person
hand-driving reliquary (U6), but the output goes into source
control and evolves there. Either way the home remains
reliquary's own ground — caches, machines, the personal property
registry — so a project's artifacts must work in place: runnable
from the source tree, with nothing copied into a home to make
them usable. One cache artifact is disposable without being
reconstructible: run records are evidence, not regenerable
output. Their contents are delivered live to whoever drives the
run (the feedback split below), and the record is retained for
its machine's life; durability beyond the machine is the
consumer's claim — copy the record out while the machine exists
(U3, U4).

Alongside these runs a feedback split. reliquary's runs are
long, and whoever drives one gets timely progress — presented
for the driver. A person at the CLI (U1, U5) gets pretty,
legible, real-time progress; an automating program (U3, U4) gets
machine-readable output that is just as timely. The two are
renderings of the same run, and neither is derived by scraping
the other: the pretty rendering is never what a program parses,
and the machine rendering is never what a person is left to
read.
