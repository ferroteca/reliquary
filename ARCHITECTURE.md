<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Architecture

> **Status:** this document describes the architecture as it
> actually is today — the whole-system view, plus the numbered
> architectural principles (P1, P2, and so on) that use cases,
> decisions, designs, and commits can cite by number. Everything
> in this document is true of the shipped system right now: every
> principle listed here is one the code actually follows (that is
> why this file lives at the repository root), and the few places
> where the code is still catching up to a stated goal are called
> out and pointed at `planning/`.
> **If the code diverges from anything stated here, that is a bug**
> (D48) — not a debatable design choice, not unfinished work, and
> not a reason to water down what this document says. That is the
> whole point of putting a principle in this document: it lets a
> principle demand work be done even when no specific use case has
> asked for it — a gap between the code and this document is
> itself sufficient reason to fix the code, no separate approval
> needed. (Contrast the documents below this one: there, an entry
> describes a goal not yet reached, and a shortfall is just work
> not yet done. Here, an entry is a factual claim, and a claim can
> be false.) When the code and this document disagree, **this
> document is what's correct** — the code is wrong — unless this
> document is changed first, following the surface-change rule
> (P23).
> Proposed changes to the architecture live in
> [planning/proposed/ARCHITECTURE.md](planning/proposed/ARCHITECTURE.md),
> and changes that have been approved but not yet built live in
> [planning/pledged/ARCHITECTURE.md](planning/pledged/ARCHITECTURE.md).
> Both use the same global P-numbering as this document, and no
> number here is reserved as a placeholder for them. Changes to
> this document are argued the same way as any other surface
> change and recorded in
> [planning/DECISIONS.md](planning/DECISIONS.md).
> Principles inform the use cases
> ([USE-CASES.md](USE-CASES.md)) and the decisions; use cases and
> decisions state which principles they serve. Principles can also
> drive work directly — a feature or task can be required by a
> principle alone, with no use case behind it, just by citing its
> P-number. Each entry below points to where its full explanation
> lives, rather than repeating it. Most entries describe the
> system itself; a few describe the process that keeps this
> document trustworthy (P8, the review rule; P9, the
> backward-compatibility policy; P22, the no-CI rule; P23, the
> rule for changing this document) — those four live in this same
> list, and in this same numbering, rather than in a separate list,
> because one list with one set of rules is simpler than keeping
> two.

## What Reliquary is

Reliquary automates guest operating systems — installing them from
vendor media, booting them, and scripting them — across multiple
virtualization backends, driven by named machine blueprints and a
Reliquary scripting language.

Reliquary manages **ephemeral machines**. A Reliquary machine is
disposable: it's created to run a scripted install or an automated
task, then torn down and recreated as needed. The machine itself
is never the product. Often there's no lasting output at all — the
point was just to run some tests and see the results. When
something more durable is needed, it is **exported** — either as a
disk image taken out of the machine, or as a whole machine handed
off to a hypervisor meant for long-lived machines. Reliquary is
not a VM manager for machines you keep around; every design choice
in it can assume machines are cheap to destroy and rebuild.

## The seams

The basic unit of design is the **operation** performed against a
machine: start it, stop it, insert media, send input, run a guest
command, read the screen, transfer a file, take a screenshot.
Operations are handled by two layers stacked on top of each other,
plus a third concept that defines what the guest OS means:

1. **Virtualization backend** — handles the differences *between
   hypervisors*: QEMU, VirtualBox, VMware Workstation, or Hyper-V.
   Each one is wrapped by a backend adapter, and all adapters share
   the same API. Every backend either has some way to perform a
   given operation, or honestly reports that it can't.
2. **Control plane** — handles the differences *within one
   backend*, when that backend offers more than one way to perform
   the same operation: for example, running a command by typing
   into the guest with no agent installed, over a serial console,
   or through a guest agent. Each of those ways is a control plane,
   and picking one is an explicit policy decision. Lifecycle
   operations — create, start, stop, destroy — always have exactly
   one way to do them per backend: the hypervisor's own
   **management interface** (QMP, `VBoxManage`, `vmrun`, or WMI),
   used privately by the adapter. So there's no control-plane
   choice to make for those. Control planes only exist where there
   actually is a choice: the operations that talk to the guest.
   The choice is made per capability, not per machine — for
   example, screenshots might come from the management interface
   while running commands goes through a guest agent, on the same
   machine.
3. **Guest platform** — the operating system family running inside
   the machine: dos, openbsd, win9x, winnt, and others to come.
   Platform-specific workflows own everything about what the OS
   means: how to provision it, how to tell it's ready, its command
   syntax, how to tell a command finished, and how to collect its
   result.

A machine blueprint states its guest platform, and optionally its
backend. Reliquary never guesses either one from a disk image or a
running guest.

QEMU is the only backend actually delivered so far, but **the
adapter layer itself is fully built**: every backend operation goes
through one adapter API
(`src/reliquary/backends.py`; design:
[planning/design/backend-adapter.md](planning/design/backend-adapter.md)).
That API was extracted from the working QEMU implementation, not
designed up front before QEMU existed. The backend is chosen when a
machine is materialized: if the blueprint names a `backend`, that
choice is fixed; otherwise Reliquary tries backends in priority
order (QEMU, then VirtualBox, then VMware Workstation, then
Hyper-V; DECISIONS.md D66) and uses the first one that is both
installed and able to handle everything the blueprint needs. The
other three adapters are currently **stubs that report they can do
nothing**, so the search skips over them even if that backend is
actually installed on the machine. Their place in the priority
order records where they're meant to slot in once built — it isn't
live behavior yet. Building one of them out means changing what it
reports it can do.

## The application surfaces

The seams described above are internal. The **application
surfaces** are the outside boundary — the places where the outside
world actually drives Reliquary. **This list is the authoritative
one**: both housekeeping's first check and the surface-change rule
([planning/SURFACES.md](planning/SURFACES.md)) answer the question
"does this change an application surface?" by looking it up against
this list. Changing any surface named here means following that
rule.

**Each surface has an S-number**, so a decision, a review, a commit,
or a spec section can just name the number instead of describing
the surface in prose — and so the surface-change rule's first step
("name every surface it touches") can point at a number instead of
writing a paragraph. The numbers form one running sequence and are
**permanent**: a surface's number is never reused, even if the
surface itself is later retired, because the number identifies a
piece of the project's vision, not a specific unit of work
([planning/DECISIONS.md](planning/DECISIONS.md) D42 explains the
different classes of number). A surface still being drafted gets a
number from this same sequence in
[planning/proposed/ARCHITECTURE.md](planning/proposed/ARCHITECTURE.md),
and one that's approved but not yet built gets one in
[planning/pledged/ARCHITECTURE.md](planning/pledged/ARCHITECTURE.md).
No number is set aside here as a placeholder for those.

The first four are the **primary** surfaces — the ones a user
drives directly:

1. **S1 — The CLI** — the `rlq` / `reliquary` command.
2. **S2 — The embedding API** — native language bindings (Python
   is the first).
3. **S3 — The scripting language** — `.rlqs` scripts.
4. **S4 — The machine blueprint** — the authored `.rlqb` document:
   an array of specs of two types, the machine and the `media` it
   draws on.

The remaining four are **supporting** world-facing contracts. The
surface-change rule covers them exactly as it covers the first
four — grouping them as "supporting" only describes how a user
runs into them, not that they matter less:

5. **S5 — The script properties** — the mechanism through which
   scripts consume values.
6. **S6 — The codex** — Reliquary's built-in seed content and its
   index.
7. **S7 — The run's returned output** — the event stream, the
   `--json` documents, and the exit codes.
8. **S8 — The working-directory layout** — the six placeable
   directories.

These eight surfaces are deliberately not designed independently
of each other. The CLI and the API present the same underlying
semantics: every CLI command maps one-to-one onto a public API call
that means the same thing, unless the command manifest gives a
specific, reasoned exception for a CLI-only command
([docs/spec/cli.md](docs/spec/cli.md)). Keeping the two in sync
matters enormously — a change to one lands on both in the same
change, never done for one and left for later on the other — and
this parity is a required rule (AGENTS.md; P6). The scripting
language sits above both — you invoke it through either the CLI or
the API — and is deliberately not a general-purpose programming
language: anything that requires actual computation belongs in the
API instead (language goal G2). The blueprint format is written by
hand in a text editor and is consumed by every other surface: the
CLI and the API resolve and materialize blueprints, including their
media specs; scripts refer to media by name; and landmark
declarations are their own separate authored files — a script never
contains embedded JSON. If a capability exists on one surface, it
exists on the others too wherever it makes sense there; if it's
missing from one, that's a deliberate, named decision, not an
oversight.

### S1 — The CLI

`rlq` (and its alias `reliquary`) is the surface for a human
operator: explicit `--blueprint` / `--machine` selection, the
two-layer lifecycle commands, `run-script`, and the media and
property commands. It is a thin layer over the embedding API — it
may resolve selectors and print ids, but it has no logic of its
own. Under the naming rule, a CLI command's name *is* its matching
API function's name, with underscores turned into dashes (the
guest-console commands instead use the same words as the scripting
language's verbs, and the `run` family of commands maps onto the
run object). The CLI is also the universal automation path: any
language that wants to automate Reliquary but has no native API
binding does it through the CLI, so the CLI serves programs as
well as people. Like the API, it must never be hard to work with
from a common language: a program written in any language must be
able to invoke it, watch it run, and cleanly parse what it prints
(P7). Specification: [docs/spec/cli.md](docs/spec/cli.md).

### S2 — The embedding API

The embedding API is the main surface for consuming projects: test
harnesses, CI drivers, and any orchestration code that needs to
make decisions, evaluate expressions, or run loops. It's meant to
have native bindings in multiple languages: the public Python
surface — the one exported `Session` class (P26), the vocabulary
around it, and the guest-console functions that work directly on a
machine — is the first binding, not the only definition of what the
API is. A language with no native binding automates through the
CLI instead. The API must never be hard to work with from a common
binding language such as C or Java: if a piece of the API's shape
can't be expressed cleanly in those languages, that shape is wrong,
no matter how elegant it looks in Python (P7). Reliquary attaches no
meaning to guest output; interpreting it is the caller's job.
Consumers inside the repository itself (the media layer, the script
runtime) must use the same public interfaces that external callers
use — no private shortcuts. Specification:
[docs/spec/api.md](docs/spec/api.md); the implemented Python
binding is documented in
[docs/api-reference.md](docs/api-reference.md), with its
engineering contract in [AGENTS.md](AGENTS.md) "The runner
surface".

### S3 — The scripting language

`.rlqs` scripts are the surface for authoring automation: they
declare resources declaratively, but describe guest interaction as
a sequence of steps, and can be checked for errors before the
machine even starts. Their design is governed by numbered language
goals (G1–G7). Source of truth:
[docs/spec/script-spec.md](docs/spec/script-spec.md), with
[planning/design/script-examples/](planning/design/script-examples/)
as reference material.

### S4 — The machine blueprint

A blueprint is a reusable JSON document, owned by the user, that
describes a kind of machine: an array of specs of two types,
`machine` and `media` (`type` defaults to `media` when omitted). A
"source" is just a media entry's `location`, and an "archive" is a
media entry that other media entries name as their parent — that
distinction was never a property of the file itself, only of how a
given entry is used. A blueprint can be written by hand in an
editor, or seeded from the codex (a third route — building one from
a native VM — is not built yet: Machine mobility,
planning/proposed/FEATURES.md). It's the durable file that
machines get built from, and it's where its author designs the
parameters that let it be customized (U5). Its `media` entries name
the installation media it needs and pin down exactly which build:
where the payload can be fetched from, and the hashes that verify
it's the exact build the scripts were written against — this is
what lets a project refer precisely to media it isn't allowed to
distribute itself (U4). The format's authority rests on **two
documents**: the published schema
(`src/reliquary/schemas/blueprint-schema-v1.json`) defines its
structure, and [the composed blueprint model](docs/spec/blueprint-model.md)
defines the meaning a schema can't express — identity, the location
syntax, how references resolve. The
[media spec](docs/spec/media-spec.md) covers acquiring media,
verifying it, and the cache. The
[guide](docs/blueprint-guide.md),
[field reference](docs/blueprint-reference.md), and
[cookbook](docs/blueprint-cookbook.md) describe the format but
aren't its authority.

### S5–S8 — The supporting contracts

The four primary surfaces don't cover everything the world touches.
These four contracts face the world too, and the surface-change
rule covers them just the same:

- **S5 — Script properties** — the mechanism scripts use to consume
  values. Its authored parts reach the world directly, without
  going through any primary surface: the user-owned
  `user.properties` file, edited by hand in a text editor, and the
  `RELIQUARY_PROPERTY_*` environment-variable naming convention:
  [docs/spec/script-properties.md](docs/spec/script-properties.md).
- **S6 — The codex** — Reliquary's built-in library of seed content
  and its index. This covers: that it is content to seed from, not
  a tier Reliquary resolves against automatically; that seeding
  never overwrites an existing copy; that deleting a copy and
  reseeding is how you refresh it; how it tracks where content came
  from; and the licensing rule for the media URLs it ships:
  [docs/spec/codex.md](docs/spec/codex.md).
- **S7 — The run's returned output** — a run drives the machine and
  returns its output to whoever started it, and stores nothing
  itself (D36). The world-facing parts are: the live event stream
  (rendered either as pretty text or as `jsonl`, following the
  secret-redaction rules), the `--json` documents, and the exit
  codes. Their shape is a contract Reliquary keeps. The run keeps no
  record of itself — letting another process follow a run after the
  fact is not built ("Asynchronous runs" in
  [planning/proposed/FEATURES.md](planning/proposed/FEATURES.md)
  covers that whole idea). What a run produces belongs to whoever
  consumed it, kept on their side, not Reliquary's
  ([docs/spec/script-spec.md](docs/spec/script-spec.md)).
- **S8 — The working-directory layout** — the six directories a
  user can place, where users put payload files, where caches live,
  and where everything above can be found:
  [docs/spec/asset-resolution.md](docs/spec/asset-resolution.md)
  "The working directories" and
  [docs/spec/instance-model.md](docs/spec/instance-model.md).

### The norms are part of the architecture

Each surface above points to the document that governs it — a
[docs/spec/](docs/spec/) specification, the published schema for
the blueprint's structure, or this list itself. Those documents
aren't commentary *about* the architecture; they *are* the
architecture: each one is the exact statement of what an
application surface is, and the code has to match it. It follows
that **changing what one of these documents requires is changing
the surface** — it has to be proposed and approved first, under
the surface-change rule
([planning/SURFACES.md](planning/SURFACES.md)), exactly like any
other surface change (**P23**), never treated as routine
housekeeping no matter how small the diff looks. The only edit that
counts as mere documentation work is one that changes no rule at
all — the test is: would any past decision that cited this document
have come out differently if it had been worded this new way? If
no, it's just wording.

- **P1 — Machines are ephemeral.** A machine exists to run its
  task and is cheap to destroy and rebuild; the machine is
  never the product. ("What Reliquary is" above; prose below.)
- **P2 — Agentless operation is permanent.** No feature may
  depend on the guest cooperating with it; operating without a
  guest agent is the default, and it stays available as a
  fallback forever. (AGENTS.md "Agentless operation"; U10.)
- **P3 — Agentless first, then hand off to an agent.** Operating
  without a guest agent is how Reliquary gets a guest ready in the
  first place; once a native agent exists inside the guest, that
  agent is the better way to keep working with it. Reliquary only
  ever uses agents that already exist — it builds none of its own,
  neither inside the guest nor on the host. What it does build is
  the client code that talks to an existing agent, and the logic
  that picks which control plane to use — never a new transport of
  its own. (Prose below; D36, D68.)
- **P4 — Where artifacts live.** The Reliquary home directory
  exists for the convenience of a human using the CLI. Artifacts
  used for automation — blueprints, scripts — are source code that
  lives in the consuming project's own tree, never in the home
  directory. **The codex never feeds automation, period** —
  nothing is ever pulled from the codex automatically, on either
  the CLI or the API, and content only reaches a project's tree
  when someone explicitly asks to copy it by name. (D59 briefly
  replaced that absolute rule with a default, when "autoseeding"
  became a switchable option; D88 deleted that option and restored
  the absolute rule — no default, no switch. Prose below.)
- **P5 — Two renderings of one run.** A single run produces two
  renderings of its progress: one pretty and readable for a person,
  one machine-readable and just as prompt for a program to consume.
  Neither is derived by scraping the other. (Prose below;
  docs/spec/script-spec.md "The run event stream"; D35, D36.)
- **P6 — CLI and API mean the same thing; this is the base rule.**
  The CLI and the embedding API present the same underlying
  surface: every CLI command has a matching API call, nothing is
  CLI-only, and no capability is reachable only through the API and
  not the CLI. **Different defaults don't break this rule** — the
  CLI assigns a home directory and picks up settings from the
  environment automatically, where the API requires you to set
  those explicitly; the actual capability behind each is present on
  both surfaces either way (D59). What *does* break this rule is a
  capability that exists on only one surface, full stop — that is
  refused **unless some other principle currently in force actually
  forbids it from crossing over** — argued explicitly as the
  exception it is, and the list of exceptions is closed rather than
  something new exceptions can be added to casually. **There is
  exactly one standing exception: the codex commands are CLI-only,
  under P18** — a library of examples that can change in any point
  release isn't something a program should be able to bind against,
  so reaching it is deliberately kept as a human action. When this
  rule and another principle truly conflict, the asymmetry between
  the two directions settles it (D24): adding a matching command
  later costs nothing, but removing one after programs have started
  calling it can't be undone — so the burden of proof falls on
  whichever side wants to break the parity. (AGENTS.md "CLI–API
  parity"; SURFACES; D24, D59, D87.)
- **P7 — Easy to call from any language.** Nothing in the API may
  be hard to express in a common language used for bindings, such
  as C or Java. And the CLI — which is the fallback way to
  automate Reliquary from any language with no native binding —
  must never be hard to drive from a program either. (SURFACES.)
- **P8 — Surface and principle changes get reviewed.** Every
  decision that changes a surface is checked against both its
  effect on the use cases *and* its effect on the architectural
  principles, following the surface-change rule. A change that
  doesn't fit one of the two is argued as the amendment it actually
  requires — amending a principle is argued just as seriously as
  amending a use case — never smuggled in as "just a feature" on
  its own merits. (SURFACES.)
- **P9 — No backward compatibility before 1.0.** Changes land
  fully and all at once; the old shape is deleted outright, never
  kept around as a bridge. During beta and the rest of the
  pre-1.0 period, a temporary cushion may be granted when it's
  clearly worth it and cheap to provide — but it is never promised
  in advance, and cushions never pile up. (AGENTS.md.)
- **P10 — Reliquary never infers its configuration from a guest,
  and never guesses anything about one.** What a machine *is* —
  its platform, backend, and control plane — comes from the
  blueprint. When Reliquary probes something, it's choosing among
  options that were already configured, never guessing what's
  actually inside the guest. **Guessing is the violation, and
  assuming counts as guessing.** Three sources are allowed to
  answer instead, and a fact from any of them counts as known
  rather than guessed: what the blueprint **declares**, what
  Reliquary can **read** directly on the host (an image's file
  format, a partition table on a drive it owns), and what the guest
  **reports about itself** when asked — recorded exactly as given,
  and valid only for the boot it was captured during. That last
  source is the guest treated as a black box that Reliquary watches
  and types commands at (G1); it is never configuration, and it
  exists as a remedy for not being able to guess, not as an
  exception to this rule. What a blueprint field may never do is
  assert what the guest's own internal arrangement is (D56).
  (AGENTS.md "Platform selection"; "The seams" above.)
- **P11 — Honesty about capability.** Backends and control planes
  report exactly what they can do. Nothing is faked or emulated,
  and if a capability is missing, that failure is reported by name
  rather than papered over. ("The seams" above.)
- **P12 — Reliquary only writes where it was told to.** Every
  file Reliquary creates that needs to persist lands in one of the
  six working directories. Each of those six can be placed by the
  user, and each is either explicitly assigned or derived from one
  that was. In normal use, Reliquary never writes a file next to
  its own code and never writes into a source repository, and it
  never invents a location on its own. (Amended by D59, which made
  all six directories individually placeable by the user and so
  retired the older claim that everything lived "under the home
  directory" — the safety guarantee that claim existed to protect
  is what's stated here now. AGENTS.md "Placeable working
  directories"; normative: docs/spec/asset-resolution.md.)
- **P13 — Where property values come from.** Values reach a run
  through one layered chain of sources. Every source uses the same
  declared key names; the order in which sources override each
  other is itself part of the language's meaning, never something a
  user configures per-project; and the chain only grows at specific,
  named points — adding a new tier is a design decision, adding a
  new provider happens behind a capability contract, and injecting
  values programmatically is owned in code. Every value that gets
  resolved records which source supplied it. What keeps layering
  values safe isn't a frozen, unchangeable order — it's knowing who
  owns each layer and being able to inspect where a value came from.
  (Normative: docs/spec/script-properties.md; D19, D20.)
- **P14 — Each authored channel has a ceiling on what it can
  express, and none may do another's job.** The three authored
  channels named in P15 each have an expressive ceiling: a spec
  never grows the ability to contain expressions — this is true
  both of its tree structure and of its strings; a script never
  nests a second file format inside it; a property never gains the
  ability to run a transform. These ceilings are written down as
  closed grammars ahead of time, precisely because every individual
  request to raise one arrives well justified on its own, and a
  channel that grants such requests one at a time can never take
  the capability back afterward. When a ceiling is actually blocking
  something, the answer is to add a new layer that arrives as its
  own distinct kind of channel — never to just widen the dialect of
  the channel already in place — and that new layer is argued for
  under the surface-change rule and decided then, not assumed in
  advance. Actual computation lives outside all three channels
  entirely, in the caller's own programming language. A ceiling
  limits what a channel may *express*, never how much an
  already-allowed construct may be *used*. This principle is what
  P4, P6, and P7 require of the three authored input channels,
  stated here as one standing rule. (Normative:
  docs/spec/blueprint-model.md "Format stability",
  docs/spec/script-spec.md "How the vocabulary grows";
  D12, D18, D26.)
- **P15 — Reliquary has exactly four input channels, and no
  others.** Everything reaches Reliquary through these: three
  authored channels — **specs** carry data, **scripts** carry
  logic, **properties** carry values — and one invocation channel,
  the **CLI and API**, which carry the command itself. This set is
  closed against channels quietly multiplying, not against adding
  one deliberately: a new kind of input gets assigned to one of the
  existing channels, and a genuinely new channel has to be argued
  for and recorded before it's built — never arrived at by simply
  implementing a small request in a way that happens to cross this
  boundary without anyone noticing. (P6 and P7 govern the invocation
  channel; the three authored channels each carry the expressive
  ceiling described in P14. Prose below; D27.)
- **P16 — Reliquary is the only interface to a machine.** Every
  supported use case can be completed without the consumer having
  to go around Reliquary to do it. This obligation binds Reliquary
  itself, not the user: going around it stays possible in
  principle — the drives of a stopped machine are just files sitting
  on the host, and that will always be true — but Reliquary must
  never *require* that anyone do so; a violation of this principle
  is a missing command, not something a user did wrong. How a
  command is implemented internally doesn't matter for this test —
  that a live media swap happens to be a QEMU monitor command under
  the hood is just plumbing — the only question is whether some
  Reliquary command answers the need. "Foreseeable" here means a use
  case that is **already in force, or already pledged** — so a
  citation for this principle has to point at a specific U-number,
  not just a hunch about what someone might want. This principle
  does not govern things that are deliberately outside Reliquary's
  scope: what happens after `export-machine` hands a machine off
  (P1); **the content of a machine's files**, covered below; the
  guest's own internal world; how authored input reaches Reliquary
  in the first place (that's P15's job); or escape hatches that no
  use case actually requires, like `--display` or `hmp`.
  **A machine's file content is deliberately out of scope, and
  that's a real boundary, not a gap that needs filling** (D108).
  Reliquary declares a machine's drives, builds them, swaps their
  media while the machine runs, and hands back the directory they
  live in (`get-machine-dir`, D5). What's *inside* a drive, though,
  belongs to the caller, reached with the caller's own tools. So a
  missing command for reading or writing files inside a drive is not
  a defect in this principle, and no use case asks for one — that
  is the entire point of this carve-out, because without stating it
  explicitly, the next person to read this would file exactly that
  as a bug. What this principle still does govern is everything a
  machine actually *is*: its lifecycle, its drives and the media in
  them, its screen, the input sent to it, and the values it hands
  back. (Pledged by D57. Rests on U14 and U20. No open gap is left
  unaddressed here: a backend that can't do something says so by
  name rather than hiding it (P11).)
- **P18 — Reliquary provides mechanism, not content.** Reliquary
  provides the mechanism — machines, the drives they carry, the
  value channels moving data in and out — and **it relies on no
  content of its own to actually function**. Nothing Reliquary
  ships is required for it to work: every command behaves exactly
  the same in a home directory that holds not a single codex file,
  and no code path in the engine reads a codex script to do its
  job. What Reliquary ships alongside the mechanism, reachable from
  the app itself, is **a library of examples** — the codex.
  Blueprint and script examples in it can be searched and copied out
  through ordinary commands (U11); they are meant to be read and
  copied from, not built on top of, and once copied, that copy is
  yours to keep (P4). **Every example is meant to work**, and one
  that doesn't is a bug. What no example is, though, is **frozen**:
  the library keeps improving over time — a script gets rewritten, a
  blueprint's disk gets resized, a pinned version moves, an entry
  gets renamed or dropped — and improvements ship in an ordinary
  *point release*. So neither an entry's name nor its content is
  fixed, and no release promises otherwise. That's a statement about
  how the library evolves, not about the quality of any one example:
  a codex script is as good as the project can make it, and the copy
  you took stops changing the moment you made it. This holds
  permanently, on its own terms: the codex is content, not a
  surface, so it stays outside whatever compatibility promise the
  project ever makes. Nothing programmatic is meant to depend on the
  codex in place. The codex is meant as the starting point for a
  consuming project's own assets — copy it, use it, change it
  however you like, commit the copy, and from then on the stability
  of that copy is the consuming project's responsibility to hold,
  not Reliquary's to promise (P4). **And it isn't something to bind
  a program against.** A program that imported a codex entry by name
  would be holding onto a name whose meaning the next point release
  could move — which is why the codex's own commands, for listing
  and seeding from it, are CLI-only (P6's one named exception,
  D87). A person copies an example and commits it; a program can
  bind to that committed copy, because the copy belongs to the
  consuming project, not to this one, and this project can't move
  it out from under them. The codex's *behavior* — how seeding and
  listing work — is an application surface, and is specified. Its
  *content* is not a surface at all: building a reusable library of
  authored content is work for the consuming project, or some other
  project, to do. Reliquary attaches no meaning to whatever runs
  through its mechanisms; interpreting and computing on that data
  is entirely the caller's job (G2).
  (docs/spec/codex.md, docs/spec/cli.md,
  docs/spec/script-spec.md; AGENTS.md
  "The embedding surface"; D1, D36.)
- **P19 — One script per target.** Each OS version and edition
  gets its own single install script. Properties and blueprint
  parameters only supply that target's run-specific data — they
  never choose which branch of logic, phase, or code path the
  script takes. So no script turns into one giant script controlled
  by flags. (docs/spec/script-spec.md "The
  procedural–declarative seam"; G3.)
- **P20 — Installation media goes in, disk images come out.**
  Install scripts consume vendor media and produce bootable
  machines; they are not tools for generating runtime
  configuration. (Acquisition: docs/spec/media-spec.md; the
  prose here is normative.)
- **P21 — A dependency has to earn its place.** Reliquary only
  takes on a dependency when it serves the need better than the
  Python standard library would. This rule applies to
  infrastructure choices, not just packages.
  (AGENTS.md "Dependencies and style".)
- **P22 — No CI, for now.** Verification happens locally: the test
  suite is the gate, it runs wherever development happens, and the
  project runs no continuous-integration pipeline. Both halves of
  that sentence matter. *No CI* means a pipeline may never show up
  just because it would be convenient — adding a CI workflow file
  would be an amendment to this principle, and has to be argued for
  and won under P8 **before** it lands, not after. *For now* means
  the door really is open: the specific situations that would
  justify CI are named in advance (the vision-utility audit's
  monthly run; host portability's requirement that the suite run on
  every supported host; automating **P24**'s every-commit gate), and
  when one of those arguments actually wins, this principle is
  retired by the decision that retires it. (Stated here; this is
  where this rule officially lives.)

- **P23 — The project's self-description changes only by proposal,
  never by just arriving.** What the project says it is and is
  for — the standing lists (this document and USE-CASES.md), the
  authoritative documents (the specs, the published schemas, the
  surface list), and everything under `planning/` — changes only
  through a proposal that wins approval first, submitted through
  the proposal queues (D39). These are grouped as one category
  because they're the documents that **bind everyone else's work**.
  The door is open: anyone can argue for any change, and the
  argument is welcome. What's refused is a change *just showing up*
  — a change that lands with no approved proposal behind it gets
  rejected by citing this principle, whatever its technical merit.
  The missing argument is the entire reason for the rejection, no
  other reason is needed, and it is a rejection **for not having
  made the case first** — never a judgment on the work's quality,
  and never on who submitted it. Citing this principle also names
  exactly what's missing, which is also the way back in: make the
  case.
  Anyone can propose a change; **only the project's designated
  authority can accept one** (D43). There are two exceptions. First,
  the clarify test: an edit that no past decision would have read
  differently under is documentation work, not a change to what's
  required — and this exception is narrow, since a requirement that
  was already *implied* is not the same as a requirement left
  unchanged. Second, **governance authority can compress the
  steps** (D43): whoever is entitled to approve a change can
  propose, accept, and land it in one pull request — the change and
  its record land together. That compresses the timeline, never the
  content that has to be recorded.

  Approval is sometimes granted **in advance**, resting on trust in
  a specific claim: that the work implements an already-pledged
  decision, or that it's mere housekeeping (D38). That's still real,
  standing approval, not an absence of governance — if the claim
  turns out to be false, an unapproved change landed. (Prose: "The
  norms are part of the architecture" above; the enforcement point
  is planning/SURFACES.md's housekeeping boundary. P8 covers how the
  argument gets weighed; this principle says the argument has to
  happen first.)

- **P24 — Every application surface is tested against its
  specification.** Each surface listed in "The application
  surfaces" above is held to the document that defines it, and the
  full test suite has to pass on every commit to `main`. **Which
  tool enforces this depends on what kind of document defines the
  surface**: where the definition is machine-readable — a shipped
  schema, a conformance corpus, the command manifest, an enumeration
  in the code itself, a fenced example block — the every-commit test
  suite runs against it directly. **No test parses the structure of
  a prose specification**: a regex keyed to specific headings and
  tables would freeze the prose's exact wording and layout in place,
  and that form belongs to whoever is reading it, not to a test.
  Prose-defined rules are still fully binding — a divergence from
  them is still a bug — and they're checked instead by the standing
  audit tasks in planning/RECURRING.md, each with its own deadline
  for how stale it's allowed to get and a note of when it was last
  done. There's no "to whatever extent possible" escape clause here:
  this principle is stated precisely so that it *can* be violated,
  and a surface that genuinely can't be tested has to say so by
  name rather than being quietly let off the hook. What actually
  enforces the every-commit half of this rule is discipline, not
  tooling — the project runs no CI (**P22**), so the test suite is a
  gate that whoever lands a change has to walk through by hand.
  (AGENTS.md "Required checks" and "Test expectations"; the
  conformance corpora and `src/reliquary/schemas/`; D49.)

- **P25 — Only cross-backend capability becomes portable
  vocabulary.** A first-class field in the machine blueprint may
  only carry a capability that applies generally, across more than
  one backend. Something only one backend can provide reaches a
  machine through that backend's own pin and its `backend-settings`
  section instead — it never becomes part of the portable
  vocabulary. Wanting a capability is necessary but never enough on
  its own: a name only enters the portable spec once more than one
  backend can actually support it, and a proposal that can't meet
  that bar is refused by citing this principle's number. (D93
  removed the single-backend `devices` field that D91 had allowed
  in; the working rule, as it reaches authors, is documented in
  [docs/blueprint-reference.md](docs/blueprint-reference.md)
  under `backend-settings`.)
- **P26 — Every API call goes through a `Session`.** Every consumer
  interaction with the API passes through a **`Session`** object,
  which is opened on at least a home directory; the consumer talks
  to the session, never directly to the code underneath it. The CLI
  is the session layer's first user: every CLI invocation opens its
  own session, and assigns the default home directory
  (`Documents/reliquary`, falling back to `~/reliquary`) whenever
  neither a flag nor an environment variable named one — exactly
  the same default-directory behavior the CLI always had (D59's
  defaulting rule, just relocated). The session carries, in one
  place, the ambient state that used to be passed into every call
  separately — the six placeable directories, and which properties
  file is selected. Because of that, the old way of threading
  `context=` and `properties_file=` arguments into every call, and
  the old module-level directory globals, are both replaced; having
  two sessions open at once in the same process is now completely
  unremarkable, which was never true when that ambient state lived
  in module-level globals. The dividing line is ambient state, and
  it's a precise one: anything that resolves a directory, touches
  machine or media state, or reads ambient configuration is only
  reachable through a session. Pure data-in/data-out work — parsing
  or validating a document or script that's handed to it — stays a
  plain function with no session involved, so tooling is never
  forced to invent a home directory just to parse a string. Some
  vocabulary stays importable directly, without a session: the
  types, the errors, the `Context` record (now used as the value you
  construct a session with), and `default_home_dir()` — which is
  what keeps the CLI's defaulting behavior available on both the CLI
  and the API surfaces (P6, D87), even after the setter functions
  for individual directories and the automatic environment-variable
  reading were removed from the public API; reading the environment
  automatically is now a private step of the CLI's own session
  construction. Everything else about D59 still holds: all six
  directories can still be individually placed when opening a
  session, a directory only gets derived from another if it wasn't
  explicitly assigned, and the API itself assigns no default home —
  it requires one to be given up front. Requiring the home directory
  at construction time is the same fail-closed safety guarantee as
  before, just moved earlier and to a single door, and it refuses
  clearly rather than failing later with a vague error; it also
  outright retired first-use `dir.unassigned` — the old behavior
  where an unassigned directory would only be caught the first time
  it was used — since now an assigned home lets all six directories
  be derived from it up front. (P6's rule that CLI and API can have different defaults
  still holds — the CLI assigns a default, the API demands one
  explicitly. P7 shapes what the `Session` object actually is:
  built from the plain `Context` record D59 already settled on, and
  from then on treated as an opaque handle that every API call hangs
  off of — a shape that can be bound from C, where passing
  per-call keyword arguments the way Python does is not an option.
  The *other* kind of session — `Machine.session()`, a live
  connection to a specific running machine — is a different concept
  entirely and keeps its own name. This principle replaces D59's
  older mechanism for carrying that ambient state — the per-call
  `context=` argument, the directory globals, and first-use
  `dir.unassigned` — but none of D59's decisions about where directories are placed, how
  they're derived, or how defaulting works. Pledged 2026-07-31 and
  delivered the same day in three parts — the session itself built,
  the CLI switched onto it, and the old door closed — which is what
  put this principle into force (D34). **One known loose end,
  called out rather than hidden (D48):** the guest-console
  functions — `Machine` and its module-level functions — still work
  the older way, keyed to a specific machine's own directory rather
  than going through a session. Moving them onto the session model
  is deferred until the control-plane design is done, and
  [docs/spec/api.md](docs/spec/api.md)'s guest-console row records
  that deferral.)


## The cross-cutting prose

This section was moved out of the use-case list on 2026-07-23,
because talk of seams, axes, models, and concepts is architecture
material, not a use case — it is normative here instead. "Them"
below refers to the use cases; the U-numbers cited live in
USE-CASES.md and USE-CASE-PROPOSALS.md, sharing one numbering
scheme.

Underneath all of the use cases sits the ephemeral-machine
principle (P1): machines are cheap to destroy and rebuild, and the
machine itself is never the product ("What Reliquary is" above).
Running through them is the agentless-then-agent progression (P3):
operating without a guest agent is most useful for getting a
machine ready in the first place — installing the OS (U1) and
bringing the guest to the point where an agent exists inside it —
and for testing installations themselves, in the style of
os-autoinst, where the install itself is the thing under test and
the screen is what gets checked (U10). Once a guest actually has an
agent, that agent is the better way to work with it; going
agentless remains the permanent fallback for guests that can never
cooperate. Reliquary only ever uses native guest agents that already
exist, and never builds its own: some operating systems have no
agent available, but writing one would be a whole separate project,
outside what Reliquary is trying to do. The same logic applies on
the host side (D36, D68): a transport faster than the agentless one
needs both ends to cooperate, and Reliquary provides neither end —
just the drives a file crosses on, with nothing about what's inside
them (P16's carve-out for file content) — while the transport
itself is expected to come from an existing external tool rather
than a project Reliquary builds. The dividing line is whether it's
an agent, not which side it runs on: a client module inside
Reliquary that speaks a protocol the guest already runs counts as
Reliquary's own code, while a second long-running process is
exactly the kind of thing Reliquary will not build.

Alongside that runs the rule for where artifacts live (P4). The
Reliquary home directory exists purely for the convenience of a
human using the CLI: users get a convenient shared place for
blueprints, media definitions, and scripts they reuse across
different interactive sessions, seeded from the codex (U1, U5). The
other side of that rule: for automation, scripts, blueprints, and
landmark files are source code — they belong to the consuming
project, live in its own source control, and never live in
Reliquary's home directory (U14, U4). The codex never feeds machine
automation, because that would be a trap: a blueprint that can
change out from under a project, outside that project's own source
control, breaks the project. So **nothing is ever automatically
pulled from the codex**, on either the CLI or the API, under any
flag: a name your own directories don't hold simply isn't found,
and the resulting error names the seed command that would fetch
something with that name from the library. There used to be a
switch for this — "autoseeding," on by default at the CLI and off
in the API — and D88 deleted it outright rather than picking a
default, because a library silently supplying a blueprint behind
the scenes is a bug that only shows up on someone else's machine,
and any knob that can be turned on is a knob CI will eventually turn
on. For automation, the codex library is at most a place to copy a
first draft from; the copy then gets committed into the project and
evolves there — `seed-blueprint` writes into whichever blueprints
directory the invocation named, including a directory inside a
project's own tree. The first drafts are likely written by a person
driving Reliquary by hand (U6), but the resulting file goes into
source control and evolves there from then on. Either way, the home
directory stays Reliquary's own territory — caches, machines, the
personal user-properties file — so a project's own artifacts have to
work in place: runnable straight from the project's source tree,
with nothing needing to be copied into a home directory to make them
usable. Nothing a run produces counts as a cache artifact at all:
the run returns its output to whoever started it and stores nothing
itself (D36), so there's no record left behind to retain, reclaim,
or copy out later — whatever a run produces belongs to the caller,
carried across to their side and kept there.

Alongside these runs the two-renderings rule (P5). Reliquary's runs
take a while, and whoever is driving one gets progress in real
time, presented in the form that suits them. A person at the CLI
(U1, U5, U12) gets pretty, readable, real-time progress; a program
automating Reliquary (U9, U14) gets machine-readable output that is
just as prompt. The two are both renderings of the same underlying
run, and neither is produced by scraping the other: the pretty
rendering is never what a program has to parse, and the
machine-readable rendering is never what a person is left reading.

## The four channels (P15)

Everything reaches Reliquary through four channels, and no
others — three for authoring, one for invocation:

| Channel | Carries | Ceiling — what it may express | Never allowed |
|---|---|---|---|
| **Specs** `.rlqb` `.rlql` | Structure and content: machines, media, containment, landmarks | Declarative data with no logic; Reliquary may add bounded constructs that *enrich a value*, but only Reliquary expands them | Function objects embedded in the tree, string templating, any operator inside `${…}` |
| **Scripts** `.rlqs` | Sequencing, waits, input, branching | A purpose-built, line-oriented scripting language, which only grows under G7 | A second file format nested inside it — no embedded JSON |
| **Properties** the property chain | Values: per-user, per-project, per-run | Declared key names, a layered override order that is itself part of the language's meaning, repeatable `default=` candidates | Transforms written in the syntax that derives one property from another — permanently disallowed |
| **CLI / API** the matching pair | The command itself | *The opposite of the other three:* every capability must be reachable, as plain commands and arguments | Not narrowness but cleverness — no capability may require a special trick or language to reach it |

The three authoring channels are **capped** — each one states
*no more than this*, and the failure this guards against is a
language slowly accreting one individually-justified feature at a
time until it's a whole programming language. The invocation
channel works the opposite way — it has a **floor, not a
ceiling**: P6 requires that everything be reachable (no capability
unreachable from the CLI), and P7 requires that reaching it stays
plain (never hard to drive from C, Java, or a shell). So its
failure mode is the reverse of the others: a capability that
technically exists but can't actually be reached, or can only be
reached through something too clever to drive from an ordinary
program. No single principle could state both a ceiling and a
floor at once, which is why the authoring ceilings and the
invocation floor are stated as separate rules.

All three authoring-channel ceilings point computation to the same
place, and that shared destination is the evidence that they're
really one rule: **actual computation happens outside Reliquary
entirely, in the caller's own programming language.** Reliquary
itself doesn't offer computation as a capability — the embedding
API and the CLI are just two doors into the caller's own language
(for a CLI user, that language is the shell, which P7 already
requires stays easy to drive Reliquary from).

This is a closure against channels quietly multiplying, not against
adding one on purpose. A new kind of input gets assigned to an
existing channel; a genuinely new channel gets argued for and
recorded before it exists. What this guards against is narrow and
checkable: **a small request, implemented in a way that's locally
reasonable but that quietly crosses one of these stated boundaries,
with nobody noticing the crossing.** The implementation in these
cases isn't unskilled — it's *locally correct*, which is exactly
why nothing stops it on its own — it's just naive about the larger
boundary it happens to cross. That's why these lines are written
down explicitly at all: a boundary nobody wrote down can't be
checked against. The past examples that went wrong all failed this
way, by accretion rather than by a deliberate decision — nobody
set out to build a template engine, it just happened one small
change at a time — so this principle's real job is to force the
moment where a change of that size becomes visible as it's being
made, since that moment doesn't happen on its own.

## Guest communication

The design for the control plane — its vocabulary of carrier,
protocol, and guest-integration; the control-plane families
(agentless display, VNC, serial console, native guest agents); the
rule that Reliquary only ever uses existing native agents; the
`GuestExec` capability layer; and the readiness-waterfall
configuration and lifecycle rules — is all written up in
[planning/design/guest-communication.md](planning/design/guest-communication.md).
The `GuestExec` protocol, the isolated agentless adapter, and its
use by the DOS workflow are implemented. The native-agent control
planes and the VNC plane are both not yet built
([planning/proposed/FEATURES.md](planning/proposed/FEATURES.md)),
and neither has been scheduled since 2026-07-23. Agentless DOS
operation remains the permanent baseline that no future work may
weaken.

## Standing constraints

Three of these are principles already stated above, so they're
just cited here rather than repeated: no backward compatibility
before 1.0 (P9); agentless DOS operation on QEMU as the permanent
baseline nothing may weaken (P2 — its role in getting a machine to
the point where a guest agent exists inside it is covered by P3);
and the requirement that only cross-backend capability becomes
first-class blueprint vocabulary (P25).

One more is a rule about how the model itself is allowed to grow.
The convention of naming drives by medium, slot, and format carries
over into machine blueprints and cached materializations. New kinds
of media, controllers, and USB devices must extend that same naming
convention with a new medium name — they may not appear as opaque
raw arguments passed straight to a backend. Admitting a new one
follows P25's bar: a `backend-settings` key that shows up
repeatedly across blueprints is evidence that demand exists for a
first-class name, but demand by itself is never enough to admit
one.

Where a guest supports both control planes, the same test suites
should validate agentless and guest-agent operation and expect
equivalent results from both.

Proposed changes to anything in this document — new principles,
changes to the model, absorbing one principle into another,
retiring one — are tracked in
[planning/proposed/ARCHITECTURE.md](planning/proposed/ARCHITECTURE.md).
