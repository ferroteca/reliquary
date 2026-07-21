<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Interfaces to the world

> **Status:** reliquary's guiding principles, and the governing
> document. It names the world-facing interfaces, the primary use
> cases they serve, and the rule every interface-changing decision
> must follow. Settled design decisions
> live in [ROADMAP.md](ROADMAP.md) and the user-facing contracts in
> `docs/`; this document records the primary use-case list itself
> and says where every other interface decision must be weighed.
> When this document and ROADMAP.md disagree, this document
> governs: the roadmap is realigned to the guiding principles and
> use cases here, never the other way around.

reliquary meets the world through its primary interfaces:

1. **The CLI** — the `rlq` / `reliquary` command.
2. **The embedding API** — native language bindings (Python is
   the first).
3. **The scripting language** — `.rlqs` scripts.
4. **The machine blueprint** — the authored machine-definition
   document.
5. **The media definition** — the authored media-acquisition
   document.

They are deliberately not independent designs. The CLI and
the API are two presentations of one semantic surface: every
command maps one-to-one onto a public API call with the same
semantics, and nothing is CLI-only (ROADMAP.md, "The CLI").
Keeping the two in sync is extraordinarily important — a change
to the surface lands on both in the same change, never deferred —
and this parity is a required invariant (AGENTS.md). The
scripting language sits above both — invoked through either — and
is deliberately non-computational, so that anything computational
belongs to the API (language goal G2). The two document formats
are authored directly in an editor and consumed through every
other surface: the CLI and API resolve and materialize
blueprints, and scripts reference — and may embed — media
definitions. A capability that appears
on one surface appears on the others wherever it is meaningful;
where it does not, the omission is a named decision, not drift.

## The primary interfaces

### The CLI

`rlq` (and its alias `reliquary`) is the human operator's surface:
explicit `--blueprint` / `--machine` selection, the two-layer
lifecycle vocabulary, `script`, media, and property commands. It is
a thin veneer over the embedding API — it may resolve selectors and
print ids, but it owns no semantics of its own. It is also the
universal automation path: any language that wants reliquary
automation but has no native API binding automates via the CLI, so
the CLI serves programs as well as people — and, like the API, it
must never make working from a common language difficult: a
program in any language must be able to invoke it, observe it,
and parse what it prints cleanly. Settled decisions:
ROADMAP.md "The CLI"; working notes: [docs/cli.md](docs/cli.md).

### The embedding API

The embedding API is the first-class surface for consuming
projects: test harnesses, CI drivers, and any orchestration that
needs decisions, expressions, or loops. It expects native bindings
in multiple languages: the public Python surface — `Runner` /
`MachineConfig` and the module-level functions — is the first
binding, not the definition of the surface. A language without a
native binding automates via the CLI instead. The API must never
make working in a common binding language (C, Java) difficult: a
semantic shape that cannot be expressed cleanly across bindings
is the wrong shape, whatever its elegance in Python. reliquary attaches
no meaning to guest output; interpretation belongs to the caller.
In-repo consumers (the media layer, the script runtime) must drive
the same public interfaces available to external callers. Contract
for the Python binding: [AGENTS.md](AGENTS.md) "The runner
surface".

### The scripting language

`.rlqs` scripts are the authored automation surface: declarative
about resources, imperative about guest interaction, statically
inspectable before the machine starts, and governed by numbered
language goals (G1–G7; ROADMAP.md, "Primary language goals").
Source of truth:
[docs/script-spec.md](docs/script-spec.md), with
[script-examples/](script-examples/) as reference material.

### The machine blueprint

A blueprint is a reusable, user-owned JSON description of a kind
of machine: authored directly in an editor, seeded out of the
built-in library, or synthesized from a native VM by `import` —
the durable artifact from which machines are materialized, and
the home of the parameter seams its author designs in for
customization (U5). Specification:
[docs/machine-blueprint.md](docs/machine-blueprint.md) with its
[reference](docs/machine-blueprint-reference.md) and
[cookbook](docs/machine-blueprint-cookbook.md).

### The media definition

A media definition names installation media and pins it: where a
payload may be acquired, and the hashes that verify the exact
build the scripts target. Hash-pinned definitions are what let a
repository refer precisely to media it cannot distribute (U4).
Specification: [docs/media-spec.md](docs/media-spec.md).

## Supporting world-facing contracts

The primary interfaces do not exhaust what the world touches.
These contracts are world-facing too, and the vetting rule below
covers them equally:

- **The property registry** — a user-owned file authored directly
  in an editor, without passing through any primary interface:
  [docs/property-registry.md](docs/property-registry.md).
- **The built-in library** — the seeded starting content and its
  index: seed-not-a-resolution-tier semantics, never-overwrite,
  delete-to-refresh, provenance, and the licensing rule for
  built-in media URLs:
  [docs/builtin-library.md](docs/builtin-library.md).
- **Recorded outputs** — run records under a machine's `runs/`
  directory: transcripts (with the secret-redaction contract),
  screenshots, and collected outputs. The world reads these;
  their shape is a contract.
- **The home layout** — where users place payload files, find
  caches, and locate everything above:
  [docs/instance-model.md](docs/instance-model.md).

## Primary use cases

Interface decisions are weighed against these. They are numbered
so a decision, review, or spec section can cite the use case it
serves — and so a proposed change can be rejected by naming the
use case it costs. This list is the decision surface: significant
interface changes arrive as proposed amendments to it (see the
interface-change rule below), and amendments are made
deliberately and recorded here.

- **U1 — Install a sandbox VM from the CLI, easily.** A user
  says, in effect, "I'd like to install FreeBSD" — and ends with
  a usable sandbox machine, installed unattended from standard
  vendor media, exportable to a hypervisor built for keeping
  machines (e.g. VirtualBox) to take away and use. Easy is the
  requirement: the command-line syntax stays terse and succinct,
  and the blueprint and install recipe are easy to find, point
  to, and use. From a clean home this is one short command
  (`rlq --blueprint freedos-1.4-plain script install`): the
  built-in library seeds the blueprint, media definition, and
  scripts; media is fetched and hash-verified; the script drives
  the installer end to end — menus, partitioning, reboots, media
  swaps — until the guest is installed.
- **U2 — Import an existing VM as a blueprint.** A user has
  created a VM natively — in VMware, say — and wants to capture
  it as a reliquary blueprint (`import` synthesizes the
  blueprint; realizing it afterward is an ordinary `create`).
  The key decision point is where the hard-disk image will live:
  it can simply remain where VMware keeps it — the *simplest*
  choice — but that is not very durable; the fuller import
  copies the image to a more durable location as a `base` image
  for differencing. The import flow's job is to present that
  choice, not bury it.
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
  scripts target. The machine is somewhat expensive to build, so
  the developer keeps it for the duration of the work cycle
  rather than tossing it eagerly; day to day, the tests run
  inside it through U3's loop — the same tool that built the rig
  automates the testing in it. When truly finished, the developer
  disposes of the large VM and reclaims the disk space.
- **U5 — Custom installation.** A user wants the German version
  of Windows. The built-in library will not carry such flavors —
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
  ordinary script text plus catalog assets, owned and edited
  like anything hand-written — recording cannot know which
  screen features are load-bearing or how long a step may
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

## The interface-change rule

The use-case list is where interface changes are argued. A change
to an interfacing aspect of reliquary is significant precisely
when approving it requires the primary use cases to be adjusted;
a significant change is not argued as a feature on its own merits
— the use-case amendment is the argument, and the interface
change follows from the amended list. A significant proposal that
cannot be phrased as "the use cases should say ..." is not ready
to decide.

Requests triage by their use-case impact:

- **No use-case impact, or strong alignment with the existing
  list.** The change leaves the use cases untouched — nothing
  any use case demands is altered — or serves them as written: a
  better spelling for an existing capability, a gap filled where
  one surface lags the others. An easy decision to approve; cite
  the use cases served, or state that none are disturbed.
- **Adds a new use.** The change serves a use reliquary does not
  yet name. More work — the new use case must be drafted,
  numbered, and weighed for coherence with the existing list and
  the ephemeral-machine principle — but, being additive, still an
  easy decision.
- **Misaligned with the primary use cases.** The hard case, and
  the one that must be argued very vigorously: approving such a
  change in good faith would require reliquary's primary use
  cases to change, so the use-case amendment — not the feature —
  is what gets argued. The workflow is strict: make the argument;
  if the argument wins, amend the use cases here; only then does
  work start. A misaligned change that can propose no amendment
  has nothing to argue and is rejected, regardless of its
  elegance.

Every approved change then lands the same way:

1. **Name every surface it touches.** A change rarely touches one:
   the CLI and API move together under the one-to-one rule, the
   language grows only through its growth goals (G6, G7), and a
   document format changes with its spec. An intentionally
   single-surface change states why the others are unaffected.
2. **Land it coherently and completely.** Pre-beta there is no
   backward compatibility (AGENTS.md): the change updates every
   affected surface, document, example, and test to the new shape
   and deletes the old one. That freedom makes execution cheap; it
   does not make the decision cheap — nothing downstream cushions
   a wrong one.
3. **Record it.** Use-case amendments land in this document;
   settled decisions go to their ROADMAP.md sections; user-facing
   contracts to their `docs/` specs; examples stay synchronized.

## Specification homes

| Interface | Specification |
|---|---|
| CLI | ROADMAP.md "The CLI"; working notes in [docs/cli.md](docs/cli.md) |
| Embedding API | [AGENTS.md](AGENTS.md) "The runner surface" (the Python binding's contract) |
| Scripting language | [docs/script-spec.md](docs/script-spec.md) |
| Blueprints | [docs/machine-blueprint.md](docs/machine-blueprint.md) with its [reference](docs/machine-blueprint-reference.md) and [cookbook](docs/machine-blueprint-cookbook.md) |
| Media definitions | [docs/media-spec.md](docs/media-spec.md) |
| Property registry | [docs/property-registry.md](docs/property-registry.md) |
| Built-in library | [docs/builtin-library.md](docs/builtin-library.md) |
| Home / machines | [docs/instance-model.md](docs/instance-model.md) |
| Run records | transcript contract in [docs/script-spec.md](docs/script-spec.md) |
