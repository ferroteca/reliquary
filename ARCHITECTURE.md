<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Architecture

> **Status:** the architecture in force — the whole-system view,
> and the itemized architectural principles, P-numbered so use
> cases, decisions, designs, and commits can cite them. This
> document is a claim: everything here is real — the model is the
> shipped system's and every principle is honored as the code
> stands today (it lives at the root for that reason), with the
> few forward-looking edges named and pointed at `planning/`.
> Proposed architecture lives in
> [planning/proposed/ARCHITECTURE.md](planning/proposed/ARCHITECTURE.md)
> and accepted-but-undelivered architecture in
> [planning/accepted/ARCHITECTURE.md](planning/accepted/ARCHITECTURE.md),
> under the same global P-numbering, with no placeholder here;
> amendments are argued like interface changes and recorded in
> [planning/DECISIONS.md](planning/DECISIONS.md).
> Principles feed into the use cases
> ([USE-CASES.md](USE-CASES.md)) and the decisions; use cases and
> decisions name the principles they serve — and principles drive
> work directly: a feature or task may be demanded by a principle
> just as by a use case, citing its P-number. Each entry indexes
> the principle at its normative home — the pointer is where the
> full prose lives. Most entries shape the system directly; a few
> are the process posture that keeps the architecture governable
> (P8 the vetting rule, P9 the compatibility posture, P22 the
> no-CI rule, P23 the norm gate) and live here because one list
> with one lifecycle beats a second list for four entries.

## What Reliquary is

Reliquary automates guest operating systems — installing them from
vendor media, booting them, and scripting them — across multiple
virtualization backends, driven by named machine blueprints and a
Reliquary scripting language.

Reliquary manages **ephemeral machines**. A Reliquary machine is a
disposable rig: created to run a scripted install or an automated
task, then recreated or deleted. The machine itself is never the
product. Often there is no durable artifact at all — the whole
point was to run some tests and observe the results. When there
is interest in something more durable, it is **exported** —
either a media image (a disk image taken out of the machine) or
an entire machine (handed to a hypervisor built for long-lived
machines). Reliquary is not a VM manager for machines you keep;
every design choice may assume machines are cheap to destroy and
rebuild.

## The seams

The unit of design is the **operation** performed against a
machine: start it, stop it, insert media, send input, run a guest
command, read the screen, transfer a file, take a screenshot. Two
seams stack beneath the operations, and a third concept scopes OS
meaning:

1. **Virtualization backend** — abstracts *across hypervisors*:
   QEMU, VirtualBox, VMware Workstation, or Hyper-V. Each is
   wrapped by a backend adapter; all adapters share the same API,
   and every backend has some way to perform each operation or
   honestly reports that it cannot.
2. **Control plane** — abstracts *within one backend*: when a
   single backend offers several ways to perform the same operation
   (run a command by agentless typing, over a serial console, or
   through a guest agent), each way is a control plane, and
   choosing among them is explicit policy. Lifecycle operations
   (create, start, stop, destroy) always have exactly one way per
   backend — the hypervisor's **management interface** (QMP,
   `VBoxManage`, `vmrun`, WMI), a private tool of the adapter — so
   no control-plane choice applies to them. Control planes exist
   only where choice exists: the guest-facing operations. Selection
   is per capability, not per machine — screenshots may come from
   the management interface while execution goes through a guest
   agent.
3. **Guest platform** — the operating system family inside the
   machine: dos, openbsd, win9x, winnt, and later others. Platform
   workflows own OS meaning: provisioning, readiness, command
   syntax, completion, and result collection.

A machine blueprint names its guest platform and (optionally) its
backend; neither is ever inferred from an image or a running guest.

QEMU is the delivered backend. The adapter seam that generalizes
the model is designed
([planning/proposed/design/backend-adapter.md](planning/proposed/design/backend-adapter.md))
and unbuilt — extraction from the working QEMU implementation
waits on demand in
[planning/proposed/FEATURES.md](planning/proposed/FEATURES.md).

## The interfaces

The seams are the inside; this is the outside boundary — the
surfaces through which the world drives Reliquary. **This
enumeration is normative**: housekeeping's first test and the
interface-change rule
([planning/INTERFACES.md](planning/INTERFACES.md)) both answer
"does it change an interface?" by lookup against this list, and
changing any surface named here follows that rule.

Reliquary meets the world through its primary interfaces:

1. **The CLI** — the `rlq` / `reliquary` command.
2. **The embedding API** — native language bindings (Python is
   the first).
3. **The scripting language** — `.rlqs` scripts.
4. **The machine blueprint** — the authored `.rlqb` document: an
   array of specs of two types, the machine and the `media` it draws
   on.

They are deliberately not independent designs. The CLI and
the API are two presentations of one semantic surface: every
command maps one-to-one onto a public API call with the same
semantics, and nothing is CLI-only
([docs/spec/cli.md](docs/spec/cli.md)).
Keeping the two in sync is extraordinarily important — a change
to the surface lands on both in the same change, never deferred —
and this parity is a required invariant (AGENTS.md; P6). The
scripting language sits above both — invoked through either — and
is deliberately non-computational, so that anything computational
belongs to the API (language goal G2). The authored blueprint
format is written directly in an editor and consumed through every
other surface: the CLI and API resolve and materialize blueprints
(their media specs included), scripts reference media by name, and
landmark declarations are authored files of their own — a script
carries no JSON. A capability that appears
on one surface appears on the others wherever it is meaningful;
where it does not, the omission is a named decision, not drift.

### The CLI

`rlq` (and its alias `reliquary`) is the human operator's surface:
explicit `--blueprint` / `--machine` selection, the two-layer
lifecycle vocabulary, `run-script`, media, and property commands.
It is a thin veneer over the embedding API — it may resolve
selectors and print ids, but it owns no semantics of its own, and
under the twin-name identity rule a command *is* its API twin's
name, dash-separated (the guest-console family instead spells as
the script language's verbs, and the `run` family maps to the run
handle). It is also the
universal automation path: any language that wants Reliquary
automation but has no native API binding automates via the CLI, so
the CLI serves programs as well as people — and, like the API, it
must never make working from a common language difficult: a
program in any language must be able to invoke it, observe it,
and parse what it prints cleanly (P7). Specification:
[docs/spec/cli.md](docs/spec/cli.md).

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
is the wrong shape, whatever its elegance in Python (P7). Reliquary
attaches
no meaning to guest output; interpretation belongs to the caller.
In-repo consumers (the media layer, the script runtime) must drive
the same public interfaces available to external callers.
Specification: [docs/spec/api.md](docs/spec/api.md); the
implemented Python binding is documented in
[docs/api-reference.md](docs/api-reference.md), with its
engineering contract in [AGENTS.md](AGENTS.md) "The runner
surface".

### The scripting language

`.rlqs` scripts are the authored automation surface: declarative
about resources, imperative about guest interaction, statically
inspectable before the machine starts, and governed by numbered
language goals (G1–G7). Source of truth:
[docs/spec/script-spec.md](docs/spec/script-spec.md), with
[planning/design/script-examples/](planning/design/script-examples/)
as reference material.

### The machine blueprint

A blueprint is a reusable, user-owned JSON description of a kind of
machine: an array of specs of two types, `machine` and `media`
(`type` defaulting to media). A source is a media's `location`, and
an archive is a media that other media name as their parent — the
distinction was never a property of the artifact, only of the use.
Authored directly in an editor, seeded out of the codex, or
synthesized from a native VM by `import-vm` —
the durable artifact from which machines are materialized, and
the home of the parameter seams its author designs in for
customization (U5). Its `media` components name installation media
and pin it: where a payload may be acquired, and the hashes that
verify the exact build the scripts target — what lets a repository
refer precisely to media it cannot distribute (U4). The format's
**norm is two artifacts**: the published schema
(`reliquary/schemas/blueprint-schema-v1.json`) for structure, and
[the composed blueprint model](docs/spec/blueprint-model.md) for
the semantics a schema cannot express — identity, the location
grammar, the reference closure; the
[media spec](docs/spec/media-spec.md) covers acquisition,
verification, and the cache. The
[guide](docs/blueprint-guide.md),
[field reference](docs/blueprint-reference.md), and
[cookbook](docs/blueprint-cookbook.md) are descriptive.

### Supporting world-facing contracts

The primary interfaces do not exhaust what the world touches.
These contracts are world-facing too, and the interface-change
rule covers them equally:

- **Script properties** — the mechanism through which scripts
  consume values. Its authored surfaces face the world without
  passing through any primary interface: the user-owned
  `user.properties` file, edited directly in an editor, and the
  `RELIQUARY_PROPERTY_*` environment spelling:
  [docs/spec/script-properties.md](docs/spec/script-properties.md).
- **The codex** — Reliquary's built-in seed content and its
  index: seed-not-a-resolution-tier semantics, never-overwrite,
  delete-to-refresh, provenance, and the licensing rule
  for shipped media URLs:
  [docs/spec/codex.md](docs/spec/codex.md).
- **The run's returned output** — a run drives the machine and
  returns its output to whoever started it, storing nothing (D36):
  the live event stream (rendered pretty or as `jsonl`, with the
  secret-redaction contract), `--json` documents, and exit codes
  are the world-facing machine surfaces. Their shape is a
  contract; the run stores no record — persisting a run so another
  process can follow it is unbuilt, and the whole record model
  lives with it
  ([planning/proposed/FEATURES.md](planning/proposed/FEATURES.md)
  "Asynchronous runs"). A run's product is the consumer's, kept on
  its own side of the seam
  ([docs/spec/script-spec.md](docs/spec/script-spec.md)).
- **The home layout** — where users place payload files, find
  caches, and locate everything above:
  [docs/spec/instance-model.md](docs/spec/instance-model.md).

### The norms are part of the architecture

Each surface above names the artifact that norms it — a
[docs/spec/](docs/spec/) specification, the published schema for
the blueprint's structure, and this enumeration itself. Those
normative artifacts are not documentation *about* the
architecture; they are architecture: each one is the exact
statement of what an interface is, and the implementation answers
to it. It follows that **changing what a norm requires is
changing the interface** — proposed and gated first under the
interface-change rule
([planning/INTERFACES.md](planning/INTERFACES.md)) like any other
interface change (**P23**), and never admissible as housekeeping
however small the diff. Only an edit that changes no rule — the
clarify test: no past decision citing the norm would have come out
differently under the new wording — is mere documentation work.

- **P1 — Machines are ephemeral.** A machine exists to run its
  task and is cheap to destroy and rebuild; the machine is
  never the product. ("What Reliquary is" above; prose below.)
- **P2 — Agentless operation is permanent.** No feature may
  depend on guest cooperation; agentless is the default and
  the fallback, forever. (AGENTS.md "Agentless operation".)
- **P3 — The control-plane arc.** Agentless operation prepares
  a guest; once a native agent exists inside it, that agent is
  the better work plane. Reliquary consumes native guest
  agents and never builds its own. (Prose below.)
- **P4 — The artifact-residency split.** The home serves human
  CLI convenience; automation artifacts are source code in the
  consuming project's tree and never live in the home; the
  codex never feeds automation. (Prose below.)
- **P6 — One semantic surface.** The CLI and the embedding API
  are twin presentations of one surface: every command is its
  API twin, nothing is CLI-only, and no capability is
  unreachable from the CLI. (AGENTS.md "CLI–API parity";
  INTERFACES.)
- **P7 — The binding constraint.** Nothing may be hard to
  express in a common binding language (C, Java), and the
  CLI — the fallback binding for every unbound language — must
  never be hard to drive from a program. (INTERFACES.)
- **P8 — Interface and principle changes are vetted.** Every
  interface-changing decision triages by its impact on the use
  cases *and the architectural principles*, under the
  interface-change rule; a change misaligned with either is
  argued as the amendment it requires — a principle amendment
  as vigorously as a use-case one — never as a feature on its
  own merits. (INTERFACES.)
- **P9 — No backward compatibility before 1.0.** Changes land
  coherently and completely; the old shape is deleted, never
  bridged. Through beta and the rest of pre-1.0 a cushion may be
  granted when warranted and cheap — never promised, never
  accumulated. (AGENTS.md.)
- **P10 — Nothing is inferred from guests.** Platform and
  backend come from the blueprint; probes select among
  configured control planes, never guess what is inside.
  (AGENTS.md "Platform selection"; "The seams" above.)
- **P11 — Capability honesty.** Backends and control planes
  report what they can do; nothing is emulated, and a
  capability gap fails closed naming itself. ("The seams"
  above.)
- **P12 — Home containment.** All persistent state lives under
  the Reliquary home (the cache separable); Reliquary never
  writes beside the module or into a source repository in
  normal use. (AGENTS.md "Home-directory containment".)
- **P13 — Property sources.** Values reach a run through one
  layered chain: every source speaks the same declared keys,
  the flattened precedence is semantics — never per-user
  configuration — and growth happens only at the named seams
  (a new tier by design decision, provider plurality behind
  a capability contract, programmatic injection with custody
  in code), with every resolution recording its supplying
  source. Custody and introspection, not a frozen order, are
  what make layering safe. (Normative:
  docs/spec/script-properties.md; D19, D20.)
- **P15 — The closed input model.** Everything reaches
  Reliquary through four channels: three authored — **specs**
  carry the data, **scripts** the logic, **properties** the
  values — and one invocation, the **CLI/API** twins, carrying
  the command. The set is closed against *accretion*, not
  against decision: a new input is assigned to an existing
  channel, and a new channel is argued and recorded before it
  exists, never arrived at by naively implementing a small
  request across a stated boundary. (P6 and P7 govern the
  invocation channel; the authored three carry expressive
  ceilings. Prose below; D27.)
- **P19 — One script, one target.** Each OS version and edition
  gets one install script. Properties and blueprint parameters
  supply that target's run-specific data; they never select a
  branch, a phase, or a path, so no script becomes a
  flag-driven mega-script. (docs/spec/script-spec.md "The
  procedural–declarative seam"; G3.)
- **P20 — Installation media is input, disk images are
  output.** Install scripts consume vendor media and produce
  bootable machines; they are not runtime configuration
  generators. (Acquisition: docs/spec/media-spec.md; the
  prose here is normative.)
- **P21 — Dependencies must pull their weight.** A dependency
  earns its place by serving the need better than the stdlib;
  the rule binds infrastructure as well as packages.
  (AGENTS.md "Dependencies and style".)
- **P22 — No CI, at this time.** Verification is local: the
  suite is the gate, and it runs where development happens; the
  project maintains no CI pipeline. Both halves are load-bearing.
  *No CI* means a pipeline may never arrive by convenience — a
  workflow file is an amendment of this principle, argued under
  P8 and won **before** it lands, never after. *At this time*
  means the door is real: the cases expected to knock are named
  (the vision-utility audit's monthly run; host portability's
  suite-must-run-there job), and when one wins the argument this
  entry is retired with the decision that retires it. (Stated
  here; this is the rule's normative home.)
- **P23 — Norms change by proposal, never by arrival.** The
  normative artifacts — the specs, the published schemas, the
  interface enumeration, and the standing lists themselves —
  change only through a proposal that wins its gate first: the
  interface-change rule, entered through the queues (D39). A
  change that arrives already made — a PR editing what a norm
  requires with no accepted proposal behind it — is rejected by
  citing this principle, whatever its technical merit; the
  missing argument is the whole reason, and the rejection needs
  no other. The one exception is the clarify test: an edit no
  past decision would read differently under is documentation
  work, not a norm change. (Prose: "The norms are part of the
  architecture" above; the enforcement point is
  planning/INTERFACES.md's housekeeping boundary. P8 says how
  the argument is weighed; this says it must happen first.)

## The cross-cutting prose

Moved from the use-case list (2026-07-23; talk of seams, axes,
models, and concepts is principle material, not a use case) —
normative here. "Them" below is the use cases; the U-numbers
cited live in USE-CASES.md and USE-CASE-PROPOSALS.md under the
shared namespace.

Beneath them all sits the ephemeral-machine principle (P1):
machines
are cheap to destroy and rebuild, and the machine is never the
product ("What Reliquary is" above). Across them runs a control-plane
arc (P3): agentless operation is at its most useful preparing a
machine — installing the OS (U1) and bringing the guest to the
point where an agent exists inside it — and for testing
installations themselves, os-autoinst-style, where the install is the
thing under test and the screen is the assertion surface. Once a
guest holds an agent, that agent is the better work plane (U3);
agentless remains the permanent fallback for guests that can
never cooperate. Reliquary consumes native guest agents and
never builds its own: agents may not exist for some operating
systems, but writing one would be a whole project unto itself,
outside Reliquary's scope.

Alongside it runs an artifact-residency split (P4). Assets in
the
Reliquary home are a convenience for human CLI interaction: users
get a convenient home for shared assets — blueprints, media
definitions, and scripts reused across human-interaction
scenarios — seeded by the codex (U1, U5). The other side of the
coin: for automation, scripts, blueprints, and landmark assets
are source code artifacts — they belong to the consuming
project, live in its source control, and never
live in Reliquary's home (U3, U4). The codex is *never* used for machine
automation — that would be a trap: a blueprint changing outside
the project's source control breaks the project. For automation
the library is at most a place to copy a first draft from; the
copy is committed into the project and evolves there. The first
drafts are likely generated by a person
hand-driving Reliquary (U6), but the output goes into source
control and evolves there. Either way the home remains
Reliquary's own ground — caches, machines, the personal
user-properties file — so a project's artifacts must work in
place: runnable
from the source tree, with nothing copied into a home to make
them usable. One cache artifact is disposable without being
reconstructible: run records are evidence, not regenerable
output. Their contents are delivered live to whoever drives the
run (the feedback split, P5), and the record is retained for
its machine's life; durability beyond the machine is the
consumer's claim — copy the record out while the machine exists
(U3, U4).

## The four channels (P15)

Everything reaches Reliquary through four channels and no
others — three authored, one invocation:

| Channel | Carries | Ceiling — what it may say | Closed against |
|---|---|---|---|
| **Specs** `.rlqb` `.rlql` | Topology and content: machines, media, containment, landmarks | Logic-free declarative data; bounded constructs that *enrich values* may be added, expanded by Reliquary | In-tree function objects, string templating, any operator inside `${…}` |
| **Scripts** `.rlqs` | Sequencing, waits, input, branching | A purpose-built line-oriented DSL, growing only under G7 | A second format nested inside it — no JSON islands |
| **Properties** the chain | Values: per-user, per-project, per-run | Declared keys, layered precedence as semantics, repeatable `default=` candidates | Transforms in derivation syntax — permanently out |
| **CLI / API** twins | The command | *Inverted:* every capability reachable, as plain commands and arguments | Not narrowness but cleverness — no capability may need a language to reach it |

The three authored channels are **capped** — each says *no more
than this*, and its failure mode is a language accreting one
justified feature at a time. The invocation channel is
**floored**: P6 requires completeness (no capability
unreachable from the CLI) and P7 requires plainness (never hard
to drive from C, Java, or a shell), so its failure mode is the
opposite — capability that exists but cannot be reached, or
reached only through something too clever to drive from a
program. One principle could not say both, which is why the
authored ceilings and the invocation floor are governed
separately.

All three authored ceilings send computation to the same place,
and that identity is the evidence they are one rule:
**computation lives outside Reliquary, in the caller's own
language.** It is not a Reliquary capability — the embedding
API and the CLI are two doors to it, and the CLI user's host
language is the shell, which P7 already requires be easy to
drive Reliquary from.

The closure is against accretion, not decision. A new input is
assigned to a channel; a new channel is argued and recorded
first. What it guards against is narrow and checkable: **a
small request, implemented naively across a stated boundary,
with the crossing never noticed.** The implementation is not
unskilled — it is *locally correct*, which is exactly why
nothing stops it — but it is naive about the line it crosses.
This is why the lines are written down at all: a boundary
nobody stated cannot be checked against. The precedents all
failed here rather than by decision — nobody set out to build a
template engine — so the principle's work is to manufacture the
moment where the large change is visibly being made, because
that moment does not arrive on its own.

## Guest communication

The control-plane design — the carrier / protocol /
guest-integration vocabulary, the control plane families
(agentless display, VNC, serial console, native guest agents),
the consume-native-agents-only doctrine, the `GuestExec`
capability seam, and the readiness-waterfall configuration and
lifecycle rules — is consolidated in
[planning/design/guest-communication.md](planning/design/guest-communication.md).
The `GuestExec` protocol, the isolated agentless adapter, and
its use by the DOS workflow are implemented; the native-agent
control planes and the VNC plane are both unbuilt
([planning/proposed/FEATURES.md](planning/proposed/FEATURES.md)),
unscheduled since 2026-07-23. Agentless DOS operation remains
the permanent base no work may weaken.

## Standing constraints

Two are principles, cited rather than restated: no backward
compatibility before 1.0 (P9), and agentless DOS operation on
QEMU as the permanent base nothing may weaken (P2; its bootstrap
direction — agentless operation is how a machine reaches the
point where a guest agent exists inside it — is P3's arc).

One is the model's own growth rule. The declared-media convention
(drives named by medium, slot, and format) carries over into
machine blueprints and cached materializations. New media kinds,
controllers, and USB devices must extend the same convention — a
new medium name — not appear as opaque raw backend arguments.

Where a guest holds both control planes, the same suites should
validate agentless and guest-agent operation with equivalent
results.

Proposed changes to any of this — new principles, model changes,
absorptions, retirements — are tracked in
[planning/proposed/ARCHITECTURE.md](planning/proposed/ARCHITECTURE.md).
