<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Roadmap

## Vision

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

[planning/INTERFACES.md](INTERFACES.md) names the interfaces through which
the world drives Reliquary and the vetting rule every
interface-changing decision must follow; the use cases
they serve live in [USE-CASES.md](../USE-CASES.md). Every
roadmap item cites what demands it — a use case (its U-number,
whether in force there or still proposed in
[planning/USE-CASE-PROPOSALS.md](USE-CASE-PROPOSALS.md)) or a
governing principle
([PRINCIPLES.md](../PRINCIPLES.md), its P-number), which
drives work just as well — so when
a proposal dies, the sweep (the removal rule there) finds every
item that falls out with it. The flow runs one way: the roadmap
flows from the use cases, and the task list
([planning/TASKS.md](TASKS.md)) flows from the roadmap and from
issues — the GitHub tracker, with TASKS.md's backlog the
parking place for non-GitHub issues.

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

A machine blueprint names its guest platform and (optionally) its backend;
neither is ever inferred from an image or a running guest.

## Backend adapters

All virtualization interaction goes through one of four backend
adapters sharing a common API:

- **QEMU** — the existing machine layer, to be reshaped behind the
  adapter API. Control planes: agentless display (QMP `send-key` + VGA
  text memory), serial (chardev), guest agent (QGA over
  virtio-serial or UART), VNC.
- **VirtualBox** — driven through `VBoxManage`. Control planes: agentless
  display (`controlvm keyboardputscancode` + `controlvm screenshotpng`),
  serial (host pipe/file), guest agent (Guest Additions guest
  control), VNC where the extension pack provides it.
- **VMware Workstation** — driven through `vmrun`/`vmcli` and the
  `.vmx` file. Control planes: agentless display (limited; screenshot via
  `vmrun captureScreen`), serial (named pipe/file), guest agent
  (VMware Tools guest operations), VNC (`RemoteDisplay.vnc.enabled`).
- **Hyper-V** — driven through the PowerShell `Hyper-V` module / WMI
  (`Msvm_*` classes). Control planes: agentless display (WMI keyboard
  injection + thumbnail/screen capture), serial (named pipe), guest
  agent (PowerShell Direct / integration services). No VNC.

Design rules:

- **One API, four adapters.** The adapter API covers machine
  lifecycle (create, start, stop, destroy), media attachment, input,
  screen access, and control plane endpoints. Capabilities differ per
  backend; the API reports capabilities honestly rather than
  emulating missing ones.
- **Autodiscovery.** Available backends are discovered by probing
  the host (binaries on PATH and in conventional install locations,
  the Hyper-V service/module). Discovery only establishes
  availability; it never changes a machine's recorded backend.
- **Default backend assignment.** When a machine blueprint does not name
  a backend, assignment happens at materialization (`create` /
  `recreate`): Reliquary walks its internal backend priority list
  one by one, probing each for availability, and picks the first
  available (and capable) backend. Capability is judged against
  the whole blueprint: referenced media and image types the
  backend must be able to attach, required control planes, and
  the settings that apply to that candidate backend. Backend-specific
  settings are conditional, not a backend selector: a blueprint may
  say "if this materializes on VirtualBox, disable I/O APIC" without
  requiring VirtualBox. Candidates without applicable settings simply
  ignore that backend's settings block. Only an explicit `backend`
  field pins the choice and skips the walk — that backend is probed
  alone and `create` fails closed if it is unavailable or incapable.
  The assignment is recorded in the machine state so the machine
  stays on that backend thereafter.
- **Backend state stays in the cached materialization.** Each
  backend is instructed to keep its machine files (disk images,
  `.vbox`, `.vmx`, Hyper-V VM/VHD paths) inside
  `cache/machines/<id>/`, so a machine's cache directory is the
  whole materialization.
- **Guest agents are consumed, never built.** Reliquary consumes
  native guest agents — QGA, Guest Additions, VMware Tools,
  Hyper-V integration services — through their backend adapters
  and never builds or ships a guest-side agent of its own
  (PRINCIPLES.md P3, the control-plane arc). A guest without
  a native agent stays agentless permanently.

The adapter seam's design doctrine is consolidated in
[planning/design/backend-adapter.md](design/backend-adapter.md)
(owner, 2026-07-21): an internal engineering contract, deliberately
not a world-facing interface (the third-party-adapter watch is in
planning/TASKS.md); adapters own drive-image materialization in
their native formats; adapters provide carriers and control planes
compose them (one shared fixed-font recognizer serves text
readback where no native text carrier exists). The doctrine is
settled ahead; signatures land with the seam extraction —
backlog work since 2026-07-23 ("The backend adapter seam"
below) — defined by the working code.

## The machine model

A **blueprint** is a reusable, user-owned JSON description of a kind
of machine. A **machine** is one realization of that blueprint: its
state, writable disks, backend object, and run history. One
blueprint may have zero, one, or many machines. Nothing about a
machine is durable: a machine **is** its cache directory (see
[planning/design/instance-model.md](design/instance-model.md)):

```text
<reliquary_home>/blueprints/
└── <name>.rlqb              the blueprint (user-owned)
<reliquary_home>/cache/machines/<id>/
├── machine.json             the machine's state (reliquary-owned:
│                            id, blueprint reference, phase,
│                            resolved configuration — and, while
│                            running, the live VM identity as a
│                            `vm` section)
├── media/                   per-machine materialized images, by
│                            media name
├── runs/                    append-only run records (transcripts,
│                            screenshots, outputs)
└── <backend>/               the backend's own files (e.g. qemu/)
```

Everything under `cache/machines/<id>/` is Reliquary's and
disposable: drives and backend files regenerate from the blueprint
(plus media definitions and scripts); run records are evidence —
retained for the machine's life, never regenerable, copied out to
survive it.
Nothing is ever hand-placed there. Pre-existing content enters a
machine through the blueprint: `media` references, and starting-point
images (`base`) that machine drives are differenced from, or
copies of.

### Blueprint and state

User documentation (the milestone-1 core is implemented; the
remaining format is written ahead of implementation):
[planning/design/machine-blueprint.md](design/machine-blueprint.md) with
its [field reference](design/machine-blueprint-reference.md) and
[cookbook](design/machine-blueprint-cookbook.md), and the ownership,
locking, and recovery model in
[planning/design/instance-model.md](design/instance-model.md).

The blueprint is Reliquary's own backend-agnostic format — never a thin
veneer over one backend's configuration. Two documents, one owner
each: the **blueprint** (`<name>.rlqb`) is the machine
shape as the user defined it — authored by hand, by `init`, or by
`import`; Reliquary reads it and — once authored — never writes
it. The **state**
(`cache/machines/<id>/machine.json`) is the machine as
it actually is — fully resolved (aliases canonicalized, defaults
materialized, the resolved blueprint digest, the blueprint's
source path, and backend identity
recorded) plus the machine's own bookkeeping (its id, repeated
inside the file as a safety check against a misplaced directory;
its blueprint's name; creation time; lifecycle phase) — rewritten
atomically in the same operation as every machine change.
Machines have no separate human name — the id
`<blueprint>-<n>` naming the machine's directory is its identity
(lowest free number at create; reused after destroy), and
commands accept the full id exactly, or `--blueprint` selection
of a sole machine. Every mutating operation
takes an exclusive per-machine lock; an interrupted operation is
detected by phase and generation and either rolled back safely or
failed with explicit recovery instructions. The resolved snapshot
recorded at `create` is the machine's **baseline**, but between
`apply`s the machine's own state is authoritative: every `start`
reconciles state and backend — the backend regenerated to match
the state, contradictions failing closed naming both sides — and
never re-reads the blueprint file. Editing a blueprint affects future
`create` operations only; adopting blueprint edits into an existing
stopped machine is the explicit `apply`, which re-resolves the
blueprint, applies what the machine can absorb without regenerating
drives, and records the new baseline digest (drive-regenerating
changes fail closed, pointing at `recreate`). Reconfiguration
(script `insert`/`eject`, CLI) updates the state only, and
persists there — a machine legitimately diverges from its
blueprint, as an install script does while its installer CD is
attached, until the script restores it or `apply` reconciles the
machine back to the blueprint. Script
outcomes live in the append-only run records under the machine's
cache; there is no `installed` flag.

Core fields: `platform` (required, never inferred), `backend`
(assigned from the availability-filtered priority list when not
declared; permanent once assigned), `memory`, `cpus`, `drives`
(the declared-media slot convention, per-drive `controller`
types, `media` references into the shared library, `size`-based
image creation, and `base` starting-point images — the backing
of a differencing disk by default, or copied), `boot`, `control-planes` (the ordered waterfall
policy), and `backend-settings` (the scoped non-portable escape
hatch applied only when its named backend is selected; it never
selects that backend by itself).
Discovery and scripting fields: an optional `description`
(indexed by `search`; the file stem is the blueprint's one name —
a display-name field was weighed and dropped, owner 2026-07-21), the `scripts` map — short labels naming
`.rlqs` files, the verbs used with `run-script`
(`rlq run-script install --blueprint freedos`) — and the
`parameters` map: blueprint-supplied script-input bindings, each
a direct value or a `{"property": ...}` reference, the blueprint
half of U5's customization seams. Like the `scripts` map it is
read at script invocation and configures script binding, not
machine shape — no state, `apply`, or baseline-digest
involvement (see planning/design/machine-blueprint-reference.md).
Validation and capability mismatches fail closed, naming the
backend and missing capability.

The blueprint and media-definition formats have authored JSON
Schema companions beside their specs
(planning/design/machine-blueprint.schema.json,
planning/design/media-definition.schema.json; decided owner,
2026-07-21): the prose specs stay normative and schema validity
never implies document validity — the schemas capture the
per-document structural subset of the format checks, for editor
completion and validation while authoring (U4, U5). The parser
remains Reliquary's own validator (fail-closed, name-the-problem
diagnostics); a shared valid/invalid fixture corpus, run against
both parser and schema at realignment, keeps the two aligned.
Documents carry no `$schema` field pre-1.0 — editors bind the
schemas by file association — with `$schema` as the leading
candidate spelling of the version field at 1.0 ("Decisions
still needed"). The machine-state schema lands at milestone 6,
once the state format settles.

### Home layout

```text
<reliquary_home>/
├── blueprints/          machine blueprints, <name>.rlqb (above)
├── scripts/             reliquary automation scripts
├── landmarks/           landmark declarations and their variant
│                        renderings, <name>.rlql + <name>.<n>.png
│                        (see planning/design/landmarks.md)
├── user.properties      personal user properties (line-based
│                        key = value; ordinary values and @secret
│                        markers for host-stored secrets)
└── cache/               reliquary's regenerable files
    ├── media/           every cached payload, keyed by the name of the
    │                    media it is (a container is a media too),
    │                    fetched/extracted/verified on demand, with
    │                    .ledger.json recording what each file is
    └── machines/<id>/   cached materializations (above —
                         disposable: drives regenerate from
                         blueprint and media; run records are
                         evidence, copied out to outlive the
                         machine)
```

The current `install-media/` cache folds into `cache/`. The
current root-level `drives/`, `machine.json`, and `vm.json`
layout is superseded by the blueprint/cache split; the project
is pre-release, so this is a replacement, not a migration.

### The codex

Reliquary ships the codex — built-in blueprints, media
definitions, and scripts for popular open source operating
systems: see
[planning/design/codex.md](design/codex.md). The codex is
a **seed, not a resolution tier**: referencing a codex artifact
that doesn't yet exist in the home copies it out as an ordinary
user-owned file; a file already present in the home is never
overwritten, and deleting a copy is how it is refreshed. An index
maps every codex artifact to its description and
relationships; `search` queries the index and user files together,
and listings report provenance (`yes` / `seeded` / user-authored).
The `seed-` family is the explicit extraction command; implicit extraction on
first reference makes the common case one command from a clean
home. A top-priority licensing rule
governs its media
definitions: a codex definition may carry a `url` only when that
download is legally redistributable — a maintainer discipline
enforced at review, not a per-definition field. The codex deliberately covers non-redistributable
operating systems too: those blueprints ship media definitions
with hashes but no URLs, and materialization fast-fails naming
the missing media until the user supplies it by adding their own
`url` or `local-path` (the cache is never hand-fed), with the
hash verifying it is the exact build the scripts target. For
open source systems the lazy path is:

```powershell
rlq run-script install --blueprint freedos
```

## Authored-asset resolution

Where Reliquary looks for authored assets — blueprints, media
definitions, scripts, and landmark declarations — is an
invocation-level setting: the mechanism behind the
artifact-residency split (PRINCIPLES.md P4). Assets are
identified by **extension**, not location: `.rlqb` a machine
blueprint, `.rlqm` a media definition, `.rlqs` a script, `.rlql`
a landmark declaration (its `<name>.<n>.png` variant renderings
attach by stem adjacency, not discovery —
[planning/design/landmarks.md](design/landmarks.md)). An asset's
**identity** is its declared `name` when it carries one, else its
filename stem; two files of one kind resolving to the same
effective name within a source are an error.

Resolution has two modes, selected per invocation by one knob —
`--assets` (API `assets=`). There is no shadow and no fallback:
the selected source is the sole source.

- **Home mode** — the CLI default, when `--assets` is absent.
  Resolves from the home's canonical `blueprints/` / `media/` /
  `scripts/` folders and seeds a missing name from the built-in
  codex on first reference. Home assets are a convenience for
  human CLI interaction — one shared place a person reuses across
  scenarios (U1, U5).
- **Dir mode** — `--assets <dir>`, and *every* embedding-API
  call. The directory is walked recursively by extension (a
  project lays its files out however it likes; dot-directories
  like `.git`/`.venv` are pruned) and is the **sole** source: no
  home, no codex, no seeding. Strictly project-scoped resolution,
  so nothing outside source control can reach an automated run
  (U3, U4). The codex is never a resolution tier for automation —
  at most a place to copy a first draft from, the copy committed.

The **embedding API has no default source**: a bare call that
resolves a name with nothing configured fails closed, so
automation never silently picks up user (home) assets — or a
stray current directory, which is arbitrary for a programmatic
caller and is not an asset default anywhere. Home mode is
reachable only through the explicit home marker the CLI sets by
default; it is never the API's default. The API source is
polymorphic: a directory, or a set of JSON-imported objects
supplied in memory with no files at all (self-identifying by
`name` — the fileless third source, landing just after the file
modes).

The home remains Reliquary's own ground regardless of mode:
machines materialize into the home cache, downloads and payloads
use the home caches, and the personal user-properties file stays
home-side (a license key never enters the repo — U5).

Two rules complete the model. **Machines record their blueprint's
source**: the state carries the resolved blueprint file's
absolute path, and `--blueprint <name>` selection matches only
machines whose recorded source equals the invocation's own
resolution of that name, so same-named blueprints in different
projects never select — and `apply` never adopts — each other's
machines (a machine with no recorded source matches by name
alone). **Reliquary reads by extension and writes by
convention**: U6's recorder emits its drafts — the script, its
landmark declarations, and their variant renderings — into the
asset root the session ran with, as new source files their author
commits. Nothing else writes an authored asset: a script carries
no definitions to install, so an ordinary run leaves the asset
root untouched and a CI tree clean.

## The CLI

The command-line structure is being worked out in
[planning/design/cli.md](design/cli.md) (a working document; this section
carries the settled decisions and outlives it).

The command is installed under two names: `rlq`, the short form
used in documentation and examples, and `reliquary`, an alias
matching the project name. They are the same entry point.

The CLI is a thin veneer over the embedding API, which remains a
first-class surface: every command maps one-to-one onto a public
Python call with the same semantics — blueprint resolution, machine
creation and selection, lifecycle, `apply`, scripting, media,
properties — and nothing is CLI-only. Where the CLI resolves a
selector, the API takes the same identifiers (a blueprint name, a
machine id); where the CLI prints an id, the API returns it.
Keeping the two in sync is extraordinarily important: a change to
the shared surface lands on both presentations in the same
change, never deferred (a required invariant — AGENTS.md).

The API expects native bindings in multiple languages; Python is
the first. Any other language that wants Reliquary automation but
has no native binding automates via the CLI. The CLI therefore
serves programs as well as people, and the one-to-one mapping is
what keeps that fallback complete: a capability missing from the
CLI would be unreachable from every language without a binding.
The binding expectation constrains API design: the API must never
make working in a common binding language (C, Java) difficult —
a shape that is elegant in Python but awkward to bind is the
wrong shape. The same constraint binds the CLI: as the fallback
for every unbound language, it must never make driving it from a
common language difficult — clean to invoke, observe, and parse
from a program, never interactive-only.

Blueprints and machines are selected by explicit flags, never by
position: `--blueprint <name>` (short `-b`) names a blueprint,
`--machine <id>` (short `-m`) a machine. A machine's identity is
`<blueprint>-<n>`; `--machine` takes the full id, exactly (owner,
2026-07-21): prefix matching and the bare-number pair form are
deleted — the id *is* the (blueprint, number) pair composed, so
each selector carries one honest type, mirroring
`resolve_machine(machine=, blueprint=)` (an implementation seam
both presentations route through, not a public twin — owner,
2026-07-21), and nothing is left to
disambiguate. As the common convenience, `--blueprint` also selects a
*machine* on machine-level verbs: when exactly one machine of that
blueprint exists — the normal one-machine-per-blueprint case — the
blueprint name is enough; with several machines the command fails
and lists their ids, and with none it fails and suggests
`create-machine` (`run-script` instead creates one).
Nothing is ever selected positionally or by guessing.

Command names follow the **twin-name identity rule** (owner,
2026-07-21): a CLI command *is* its API twin's name,
dash-separated where the twin has underscores, and its flags
mirror the twin's parameters (`--hdd-images` ↔ `hdd_images=`).
Naming the twin names the command, so the two presentations
cannot drift and the parity invariant is self-enforcing. Two
named exceptions, each an identity with a different home surface:
the guest-console family spells as the script language's verbs
(below), and the `run` family maps to the API run handle's
methods. The identity paid four characters on the north-star
command (`rlq run-script install --blueprint freedos`)
— a knowing trade of succinctness for cohesion.

The lifecycle vocabulary is two-layered. Blueprints are plain files
under `blueprints/`: authored, renamed, and removed directly in an
editor, with `new-blueprint` and `import-vm` as authoring
conveniences, the `seed-` family as extraction from the codex, and
`delete-blueprint` as the managed removal. Machine-level verbs act
on machines: `create-machine` materializes a blueprint as a new
machine under a new id, `start-machine`/`stop-machine` run it,
`destroy-machine` deletes it entirely (a machine is nothing but
its cache directory), and `recreate-machine` is destroy + create
as one command under the same id. `import-vm` synthesizes a
blueprint from a native VM — blueprint authoring only; realizing
it afterward is an ordinary `create-machine`; `--name` names the
blueprint to write, so `--blueprint` is selector-only everywhere.
Each verb's embedding-API twin is settled (owner, 2026-07-21):
flat verb-noun functions completing the `fetch_media` /
`run_script` family — `create_machine`, `start_machine`,
`stop_machine`, `apply_blueprint`, `destroy_machine`,
`recreate_machine`, `clone_machine`, `delete_blueprint`,
`import_vm`, `seed_blueprint` / `seed_script`,
`new_blueprint`, and the property family `get_property` /
`set_property` / `unset_property` / `list_properties` — taking
the CLI's selectors (`resolve_machine()` the shared seam) and the
mirrored globals (`home=` / `assets=`),
returning what the CLI prints (`create_machine` and
`clone_machine` return the new id), raising by class where the
CLI exits by code (the classes are named —
planning/design/api.md); export's twins are settled (owner,
2026-07-22): `export-drive` ↔ `export_drive` and
`export-machine` ↔ `export_machine`. Implementation realigns
the current names (`create_from_blueprint`, `machines.start` /
`stop` / `destroy`) to these.

The interaction vocabulary is the script language's own (owner,
2026-07-21): `type` (raw text, no implicit ending), `enter`
(type + press enter), `press` (the language's closed portable
key vocabulary, `+` chords), `select` (cursor-menu selection by
normalized visible label), `wait` (the language's condition
spellings — `"..."` a normalized literal, `/.../` a regex,
`machine=stopped` the machine channel), and `screenshot` spell
on the CLI exactly as in a script, each defined once in
planning/design/script-spec.md and referenced, never redefined,
by the CLI. The state operations spell as their twins —
`insert-media <slot> <media>`, `eject-media <slot>`,
`set-boot-order <key>...` — because they mutate durable machine
state, not the live console; the script verbs `insert` / `eject` /
`set-boot` are the in-script spellings of the same operations,
whose rules apply by reference (state-not-blueprint persistence;
the CLI's media argument is a bare name — `@` marks references
only inside script text). File exchange is out-of-band (owner,
2026-07-22 — the run-collection model was dropped):
`get-machine-dir` (twin `get_machine_dir`, returning the
machine's cache directory as an absolute path; a query, any
machine phase) is the door, and while a machine is stopped on
every control plane its drives are plain host state — a
`hostdir` drive *is* its directory, and image drives are the
user's own tools' business; Reliquary neither mediates nor
records out-of-band access (contract:
planning/design/instance-model.md). In-band file operations are
deferred to a late milestone ("Horizon" below), and the script
language has no file verbs — a named omission
(planning/design/script-spec.md). The CLI adds exactly two commands the language
deliberately lacks: `screen` prints the current text screen
(scripts observe; humans and programs read), and `exec <command>`
is the composite convenience — `enter` plus the platform
workflow's completion detection — that scripts spell as explicit
observation. `run` therefore names run records exclusively.
`hmp` remains the QEMU-only escape hatch until the control-plane
design homes it; the interaction family's API twins land with
that same design as a named omission (planning/design/api.md),
the capability meanwhile reachable through today's `Machine`
functions. By default these commands leave no record; with an
interaction run open (`begin-run` / `end-run` — "Asynchronous
runs" below) every machine-targeting command appends to its
record.

Flags are the command's parameters and **position carries no
meaning** (owner, 2026-07-21): a flag may appear before or after
the command word — the north star's two spellings are identical —
with synopses canonically showing flags after the command.
`--home`, `--assets <dir>` (the single asset knob — its absence is
home mode, "Authored-asset resolution" above), and `--json`
(below) are accepted by every command, mirroring the API's shared
keywords. There is no
bare-script shorthand — an unrecognized command word is an error,
never a script lookup (`run-script <label>` is the tightest
form).

Machine-readable query output is `--json`, a global flag (owner,
2026-07-21) — the query half of the feedback split, defined by
parity rather than enumeration: under `--json` a command prints
exactly what its API twin returns, serialized as one JSON
document (object, array, or scalar) on stdout — nothing else on
stdout, diagnostics on stderr, exit codes unchanged — so the
twin's return contract is the command's `--json` contract and
the two presentations cannot drift. A twin that returns nothing
prints `{}` on success, letting a program pass `--json`
unconditionally; stream-bearing commands (`run-script`,
`run tail`, `fetch-media`) reject `--json` naming
`--progress jsonl` — a run is
an event stream, not a document; one flag, one meaning each.
Secret property values serialize as their marker, never their
value, and `--verbose` remains pretty-rendering only. Field
names land with each twin's return contract
(planning/design/api.md).

Output discipline (owner, 2026-07-22): **the result is stdout;
everything else is stderr**. A result-bearing command's pretty
stdout is exactly the human rendering of what its twin returns —
the same value `--json` serializes, on the same stream — so the
two presentations are two renderings of one value and the parity
rule extends to channel placement. Progress, narration,
warnings, prompt text, and error reports live on stderr: tables,
screen text, and printed ids pipe clean with no flags, and
announcement lines (a resolved directory header, narration)
never pollute a pipe. Stream-bearing commands' human modes
render everything — live progress, the outcome, the failure
report — to stderr and leave stdout empty: the machine paths are
`--progress jsonl` (whose stdout events are the result — the
settled exception) and the run record, and the outcome is the
exit code; `--detach`'s printed run id remains a result.
`--progress auto` resolves by whether *stderr* is a tty — the
stream progress renders on — so piping stdout never degrades the
live display and redirecting stderr to a log gets `plain`
automatically. Prompting requires stdin and stderr to both be
ttys: prompt text writes to stderr, the answer reads from stdin
(direct console-device access was declined — a platform seam,
and unsuppressable by redirection). Diagnostics are
`rlq: <message>` with detail lines indented beneath, warnings
`rlq: warning: <message>`, and errors name the next command
where one exists. ANSI and color are emitted per stream, only
when that stream is a tty; `NO_COLOR` is honored; there is no
`--color` flag (`--progress pretty` remains the way to force
live rendering at a non-tty).

The stability contract (owner, 2026-07-22): the machine
surfaces are exactly four — exit codes (the error classes),
`--json` documents, the `jsonl` event stream, and run-record
files. Pretty and plain output are explicitly uncontracted —
free to change any release: machine consumers get machine
surfaces, and nobody freezes the human rendering by depending
on it. From 1.0 the machine surfaces grow additively only (the
horizon moved from beta with D25) — new event kinds and new
fields may appear in any release, an existing field never
changes type or meaning, and a removal or rename is a breaking
change — and consumers must ignore unknown event kinds and
unknown fields. Pre-1.0 there is no stability promise; shapes
track the specs and the CHANGELOG records changes. The
version-field spelling stays with the 1.0 format-versioning
decision ("Decisions still needed").

```text
rlq list-blueprints
rlq list-machines [--blueprint <name>]
rlq list-scripts
rlq list-media
rlq list-runs [--blueprint <name> | --machine <id>]
rlq (search-blueprints | search-scripts | search-media) <term>...
    [--verbose]
rlq new-blueprint <name> [flags]
rlq (seed-blueprint | seed-script) <name> [--only]
rlq create-machine --blueprint <name>
rlq start-machine (--blueprint <name> | --machine <id>) [--display]
rlq stop-machine (--blueprint <name> | --machine <id>)
rlq apply-blueprint (--blueprint <name> | --machine <id>)
rlq destroy-machine (--blueprint <name> | --machine <id>)
rlq recreate-machine (--blueprint <name> | --machine <id>)
rlq delete-blueprint <name>
rlq clone-machine (--blueprint <name> | --machine <id>)
rlq export-drive <key> <destination>
    (--blueprint <name> | --machine <id>)
rlq export-machine --to <exporter> [<destination>]
    (--blueprint <name> | --machine <id>)
rlq import-vm <source> --name <name> --platform <platform>
    [--hdd-images (duplicate | difference)] [--snapshot | --no-snapshot]
rlq run-script <label> (--blueprint <name> | --machine <id>)
    [--property <key>=<value>]... [--properties <path>]
    [--display] [--detach] [--progress <mode>]
rlq run status [<n>] (--blueprint <name> | --machine <id>)
rlq run tail [<n>] (--blueprint <name> | --machine <id>)
    [--progress <mode>]
rlq run wait [<n>] (--blueprint <name> | --machine <id>)
rlq run cancel [<n>] [--stop-machine] (--blueprint <name> | --machine <id>)
rlq run delete <n> [<n> ...] (--blueprint <name> | --machine <id>)
rlq begin-run (--blueprint <name> | --machine <id>)
rlq end-run (--blueprint <name> | --machine <id>)
rlq type <text> (--blueprint <name> | --machine <id>)
rlq enter <line> (--blueprint <name> | --machine <id>)
rlq press <key>... (--blueprint <name> | --machine <id>)
rlq exec <command> (--blueprint <name> | --machine <id>)
    [--timeout <duration>]
rlq select <item> (--blueprint <name> | --machine <id>)
    [--exclude <text>]... [--timeout <duration>]
rlq wait <condition> (--blueprint <name> | --machine <id>)
    [--timeout <duration>]
rlq screen (--blueprint <name> | --machine <id>)
rlq screenshot [<name>] (--blueprint <name> | --machine <id>)
rlq insert-media <slot> <media> (--blueprint <name> | --machine <id>)
rlq eject-media <slot> (--blueprint <name> | --machine <id>)
rlq set-boot-order <key>... (--blueprint <name> | --machine <id>)
rlq get-machine-dir (--blueprint <name> | --machine <id>)
rlq hmp <line> (--blueprint <name> | --machine <id>)
rlq check-script <label-or-name> [--blueprint <name> | --machine <id>]
    [--property <key>=<value>]... [--properties <path>]
rlq fetch-media <media_name>
rlq list-properties [<prefix>]
rlq get-property <key>
rlq set-property <key> <value>
rlq set-property <key> --secret
rlq unset-property <key>
rlq clean-media [<name>]
rlq prune-media [--dry-run]
rlq add-media <name> <file>
rlq clean-media
```

Lifecycle semantics:

- `list-blueprints` shows each blueprint with its machine count;
  `list-machines` shows each machine's id, blueprint, phase, and
  backend (`--blueprint` filters to one blueprint's machines).
- `create-machine` validates and resolves the named blueprint
  (a `.rlqb` file — written by hand, by `new-blueprint`, or by
  `import-vm`), materializes a new machine under a new id — state,
  drives, backend object — and prints that id.
  Blueprints are authored documents, and media definitions are
  likewise user-owned files a script references but never carries.
- `apply-blueprint` adopts the current blueprint into a stopped
  machine: it
  re-resolves the blueprint, reconciles the machine to the new
  resolution (memory, boot order, drives enabled/disabled, media
  changes), and records the new baseline digest. Changes the
  machine cannot absorb without regenerating drives (`size` or
  `base` changes on materialized images) fail closed naming both
  sides; `recreate-machine` is the honest alternative.
- `destroy-machine` deletes the machine entirely — its directory
  (state,
  drive images, run records) and the backend's machine. The
  blueprint is never touched; `create-machine` makes a fresh
  machine whenever one is wanted again.
- `delete-blueprint <name>` removes the blueprint file itself and
  fails closed while any machine of it exists, naming the machine
  ids — destroy them first. (Removing a machine is
  `destroy-machine`'s job.)
- runs are machine-scoped — monotonic numbers, never reused; the
  `run` operations take the number positionally and default to
  the machine's latest run. A foreground `run-script` is
  start-plus-attach; `--detach` returns the run id after
  foreground preflight ("Asynchronous runs" below).

- `run-script` completes preflight, resolves its machine (creating
  one when `--blueprint` names a blueprint with no machine yet), and
  starts it if it is not already running before executing guest
  steps.
- `fetch-media` downloads, extracts, and hash-verifies a defined
  media
  item (see planning/design/media-spec.md). It is a convenience: machine
  operations resolving a `media` reference to a fetchable
  media fetch implicitly. Everything caches in the one
  `cache/media/`, keyed by media name — a container is a media like
  any other.
- the property family (`get-property`, `set-property`,
  `unset-property`, `list-properties`) maintains the home-wide
  user properties file described in
  planning/design/script-properties.md. Ordinary strings live in
  `user.properties`; secret values live only in a protected host
  credential store, with a marker in the file. Listing and getting
  secrets never reveal them, and secret setting takes no value
  argument (process listings and shell history are not credential
  stores): on a tty it prompts with no echo; otherwise it reads
  the value from stdin (to EOF, one trailing newline stripped,
  empty is an error — owner, 2026-07-21), keeping the CLI a
  complete binding for programs. Every property command accepts
  `--properties <path>`, maintaining a selected file in place of
  the home's `user.properties`.
- `clean-media` reclaims payloads Reliquary can fetch or derive
  again, sparing what a person supplied and what a running machine
  holds; naming one evicts it deliberately. `prune-media` keeps the
  attachment closure and drops what only existed to produce it.
  `add-media` supplies a payload nothing can locate.
- `recreate-machine` is exactly destroy + create under the same
  machine id: drives regenerate as declared (`size`
  blank, `base` differenced or copied afresh). Since resolution
  and backend assignment re-run, a recreated machine may land on
  a different backend — `recreate-machine` is the sanctioned way
  to move
  a machine between backends, and regenerated drives arrive in
  the new backend's formats.
- `clone-machine` duplicates a stopped machine as a new machine
  under a
  new id (printed like `create-machine`'s): it retains the
  source's resolved blueprint snapshot and copies the source's
  writable drive images — a snapshot of a machine, not another
  blueprint. The clone gets its own backend object and `backend-id`;
  state and backend registration are never copied.

- Export is two commands (owner, 2026-07-22), stopped-only and
  stream-bearing, the artifact independent and permanently
  outside Reliquary's purview.
  `export-drive <key> <destination>` takes one drive out as a
  standalone image — the drive's native format, or raw by
  destination extension (the adapters' raw interchange; other
  conversions declined as growth). `export-machine --to
  <exporter>` creates and registers a native VM with a
  management platform built for keeping machines: `--to` names
  an **exporter** — virtualbox, vmware, hyperv, libvirt, vagrant,
  ... — a
  vocabulary of its own, probed on the host and deliberately
  decoupled from the backend list (libvirt is the QEMU
  ecosystem's answer; the Reliquary-invented
  bare-image-plus-launch-config artifact is dead). The target is
  presented, never defaulted: a tty prompts listing the
  exporters available on this host, noninteractively it is an
  error, `to=` required under parity. The exporter builds the
  native VM from the machine's resolved blueprint shape
  (capability-checked like `create-machine`) with drive content
  through the adapters' raw interchange, and media payloads
  materialize as copies so the export stands alone. Ownership
  verification guarantees Reliquary can never touch the exported
  VM afterward. Import mirrors the decoupling in vocabulary:
  `import-vm` reads a native VM source through an **importer**,
  no same-named backend required. Vagrant belongs here as a
  handoff vocabulary entry — `export-machine --to vagrant`
  generating the Vagrantfile / box-side artifact, and a matching
  importer reading Vagrant metadata where it can — not as a
  backend, because the actual machine capabilities belong to the
  selected provider underneath.
- `import-vm` synthesizes a blueprint from a native VM source's
  configuration (memory, drives, controllers — translation of
  native config read by an importer, not guest inference),
  capturing the VM's disks
  as media items in place (owner, 2026-07-21): each disk gets a
  generated definition — an absolute `local-path` at the file
  where the native hypervisor keeps it, a computed hash, no URL —
  and the blueprint's drives take the items as `base`. Import
  reads only a source at rest (owner, 2026-07-21): a running or
  suspended source VM fails closed naming the VM and its state —
  powered off only, because a saved VM's disks are stable but
  mid-flight guest state, and importing them would bake a
  yanked-power filesystem into every materialization; state per
  the backend's own reporting, with image-lock detection the
  fallback for bare-image sources. Import
  never copies, moves, or modifies the captured images;
  relocating an
  image to more durable ground is the user's own copy/move plus
  a `local-path` edit in the definition, which is theirs. The
  source VM itself is modified only with consent (owner,
  2026-07-21): `--snapshot` has the native hypervisor snapshot
  the disks first — the definitions pin the frozen extent, the
  source VM stays free to keep running natively, the snapshot is
  Reliquary-named with provenance recorded in the generated
  definitions' `notes`, and its later fate in native tooling is
  the user's (verification reports a lost extent);
  `--no-snapshot` touches nothing, and running the source again
  breaks verification until re-import. Absent on a tty, the flag
  prompts with that tradeoff; noninteractively absent is an
  error; `import_vm`'s `snapshot=` parameter is required, under
  parity. The
  materialization choice is presented the same way, never
  defaulted (U2):
  `--hdd-images (duplicate | difference)` selects the generated
  drives' `base.type`, spelled explicitly in the blueprint — on
  a tty an absent flag prompts with the tradeoff (duplicate:
  each create pays a full copy, the machine's drive stands alone
  afterward; difference: cheapest create, the source must stay
  byte-identical — per-start media verification refuses a
  rewritten source), noninteractively an absent flag is an
  error; `import_vm`'s `hdd_images=` parameter is required, under
  parity. A machine created
  from an imported blueprint recreates like any other: from its
  bases. `platform` is not
  knowable from any backend configuration, so `import-vm` requires
  `--platform` explicitly; the never-infer rule holds (`--name`
  names the blueprint to write). `import-vm`
  stops at the blueprint: it never materializes a machine — running one
  afterward is an ordinary `create-machine`. Drive preservation is
  entirely the blueprint's job, through the drive materialization
  triad: `size` (always a fresh blank disk at `create`), `base`
  with type `difference` (the default — a differencing disk
  backed by the base image), and `base` with type `duplicate`
  (materialized as a full copy).
- Machines **stay running** until explicitly stopped — by a script
  step or by `stop-machine`. No command implicitly tears the
  machine down.
- `--display` shows the backend's console window instead of running
  headless.
- Ownership verification generalizes: no adapter sends a control
  command to a hypervisor object until it has verified that the
  object is the one recorded in the machine's state (the QMP
  identity check is the QEMU instance of this rule).

`new-blueprint <name>` is the blueprint-scaffolding
convenience (supersedes the earlier `init` idea): it writes a
minimal starter blueprint from CLI flags (platform, memory, a
blank hard disk by size, CD/floppy media, boot order), so new
machines don't begin from a blank editor. One-shot,
fire-and-forget scaffolding only — it emits an ordinary blueprint
file the user owns from then on; no template registry, no
regeneration, no linkage back to the scaffolder. Anything the
flags don't cover is edited into the JSON directly, or starts
from a built-in blueprint.

## The scripting language

Reliquary gets its own scripting language for automating guests.
Scripts are stored in `<reliquary_home>/scripts` and invoked as
`rlq run-script <label>` against a machine selected with
`--machine <id>` or `--blueprint <name>`.

**The July 2026 surface redesign is decided and
[planning/design/script-spec.md](design/script-spec.md) is its source of
truth** (including the complete typed EBNF), with
`reliquary/codex/scripts/freedos-install.rlqs` as the
reference script. Realigning the implementation — parser, runtime, shipped
scripts — with it was **milestone 4** (complete);
see the milestones below. Pre-1.0, the superseded surface is
deleted, not bridged.

**Decided shape: a line-oriented, constrained DSL with one
grammatical form.** A script is a UTF-8 text file
(`scripts/<name>.rlqs`) in which every line is a *node*: a name,
positional arguments, `name=value` properties, and optionally a
brace block — with `#` comments and no commas or colons anywhere.
Spelling reveals role: `"..."` is guest-boundary text, `/.../` a
regex, `@name` a library reference, `$key` a property reference,
bare words are keywords and script-internal names. Declarative
nodes (headers, `media`, `property`, `phase`) begin with a noun and
precede imperative verb-first statements. It is a domain-specific
programming language with sequencing, branching, named phases,
and explicit transitions, but no expressions, mutable variables,
functions, arithmetic, or general-purpose loop construct.
Computational orchestration belongs in Python.

A script has one of two non-mixing shapes. A **linear script** is
an ordered top-level sequence. A **phased script** declares an
explicit `entry` phase and named phases; every sequential phase
ends in `goto <phase>` or `finish`, with no textual fallthrough.
A phase is either sequential (ordered statements, including
branching `wait` blocks) or reactive (only `always` handlers, all
active from entry), never the former hybrid of an ordered body
and positionally armed ambient handlers. Reactive dispatch is
single-threaded and run-to-completion. A handler fires once per
matching episode and cannot fire again until its condition has
become unmatched and later matches again, preventing persistent
screens from repeating destructive input on every poll. Smaller
phases, rather than statement position, scope which handlers are
active. There are no anonymous phases or handler-splicing macros.

The guest's screen is the **default observation channel** and is
unprefixed — a bare string or regex condition *is* a screen
observation, and that is its only spelling — while every
non-default channel is named as a prefix: `wait machine=stopped`
(there is no bare `stopped` condition). Growth rule: a new channel
names a new non-default observable (`console=`); a new value
spelling names a new matcher over the screen (a `@landmark`
reference for image matching). Every condition is preflightable
against the machine's control planes. Text watches are
case-sensitive **normalized text matches**: screen rows decode to
Unicode, trim cell padding, and collapse whitespace before
literal substring or opt-in regex matching. `wait` is the one
observation construct, in single-condition and branching forms —
the branching `wait { on ... }` covers small ordered forks (two
handlers minimum), and one handler shape carries two arming
keywords: `on`, a one-shot case inside a branching `wait`, and
`always`, a standing rule in a reactive phase — the lifetime
readable from the first word. `machine=stopped` is the machine no-longer-running
condition; it does not claim that the shutdown was graceful. A
guest reboot has no Reliquary verb or event: the script types the
guest command, makes a menu choice, or sends the appropriate key
sequence, then watches for the screen that follows. There is
likewise no `run` verb: `enter` delivers a console line, and
completion is a separate explicit observation.

Timing separates two scoping families: `timeout` bounds the time
to the next observed event and is a lexically scoped default
(statement over branching wait over phase over header, innermost
wins), while `deadline` is a wall-clock budget dynamically scoped
to one activation of the construct it annotates — fresh per phase
entry, with the header `deadline` backstopping the whole run —
and `stable` requires a condition to remain matched. Illegal
placements are parse errors per the spec's placement matrix.
Polling and input pacing belong to the control plane; the
language has no `delay` or sleep. Duration literals carry units
(`500ms`, `30s`, `20m`).

Immutable `text`, `media`, and `secret` properties externalize
run-specific data without adding decisions or expressions:
`property [type] <key> [prompt="..."]` declares one, its name the
user-property key itself, and `$key` references (`${key}` inside
strings) are bound before
execution. Every source speaks the same keys and answers in one
flattened order: an explicit `--property` value
wins for that invocation, then the machine blueprint's
`parameters` binding (a direct value, or a redirect resolving
another key), then `RELIQUARY_PROPERTY_*` environment
variables, then the selected properties file, then — one ask per
key — interactive prompting. Locale-class customization that would
change watch conditions is never a value binding: it is the
blueprint's composition seam — selecting the media/script pair —
per U5 (planning/design/machine-blueprint.md, "Customization seams"). Missing noninteractive, mistyped, or
unresolved-media values fail before the machine starts, as do
ordinary/secret kind mismatches.

The user properties file (`user.properties`) is a flat, user-owned
file of
dotted `key = value` lines, secrets kept as `@secret` markers, with
comments preserved through property commands. Secret values never
enter that file: they live in the host's protected credential store,
scoped by properties-file path and property name, with no plaintext
fallback.
`secret` properties may expand only in `enter` and `type`. Transcripts
record property keys and supplying sources, never values or expanded
secret-bearing arguments; textual diagnostics redact known secret
values, and automatic failure screenshots are suppressed after secret
entry. This protects Reliquary's records, not guest logs, history, or
an explicitly requested screenshot. The complete planned contract is
in [planning/design/script-properties.md](design/script-properties.md).

A script carries no JSON (owner, 2026-07-22). Media definitions
and landmark declarations are authored files of their own — `.rlqm`
and `.rlql` resolved beside the script under authored-asset
resolution — referenced by `@name` and never embedded. The
`media <label> { ... }` and `landmark <name> { ... }` block forms
are deleted, and with them the install-on-first-run model: a run
writes no authored asset, the node grammar has no JSON island, and
one rule covers all four extensions. The cost is that a workflow
travels as a small set of files rather than one — which is what U4
already describes, a repository carrying blueprints, media
definitions, and scripts side by side.

The language has no file-exchange verbs (owner, 2026-07-22 —
the run-collection model was dropped): files cross the boundary
out-of-band, against a machine stopped on every control plane,
whose drives are then plain host state — a `hostdir` drive is
its directory, and the machine directory is reported by
`get-machine-dir`; in-band file operations are a deferred
CLI/API capability ("Horizon"), and future live transfers get
distinct verbs rather than backend-dependent semantics. `start` reconciles the authored
machine blueprint and `stop` is visibly a host hard power-off.
There is no `restart`: a hard power cycle is the explicit pair,
and a guest reboot remains guest input. Parsing, property binding,
whole-script capability preflight, and static control-flow checks
all finish before the first guest input. User documentation and
source of truth: [planning/design/script-spec.md](design/script-spec.md)
(the July 2026 redesign; the tree speaks this surface as of
milestone 4).

The primitive vocabulary already exists in today's CLI and Python
surface — it is the proven instruction set the language must cover:

- enter/type text and send keys;
- wait for normalized screen text (literal or regex), machine
  state, or a stable observation, with timeout/deadline bounds;
- select an entry in a cursor-key menu by visible feedback;
- take a screenshot;
- insert and eject defined media, and start/stop the machine.

### Primary language goals

Every language decision is judged against these. They are numbered
so later decisions, reviews, and spec sections can cite them, and
so a proposed feature can be rejected by naming the goal it costs.

- **G1 — Agentless at the guest seam.** The guest is a black box
  that cannot be configured, only watched and typed at. No feature
  may depend on guest cooperation. This is a permanent requirement
  (AGENTS.md), not a current limitation.
- **G2 — Non-computational.** No expressions, variables,
  arithmetic, functions, or general-purpose loops. Anything
  computational belongs in Python via the embedding API, which
  remains a first-class surface.
- **G3 — Statically inspectable before the machine starts.**
  Parsing, binding, control-flow analysis, and whole-script
  capability preflight all complete before the first guest input.
  The authored graph is explicit and finite even when a run cycles.
- **G4 — Legible in real time.** A run is usually long, unattended,
  and watched by someone who wants to know where it is. The
  language's own structure — named phases, the pending observation,
  declared budgets — must be sufficient to answer "where am I, what
  is it waiting for, how long has it got" without extra syntax.
- **G5 — Backend- and control-plane-agnostic at the surface.** A
  script says "wait for this text"; the machine's backend and
  selected control plane decide how that is observed. Verbs stay
  intent-level, above portable input events.
- **G6 — Small and unambiguous.** Brevity, succinctness, structure,
  clarity. One concept, one spelling. Surface area is the scarce
  resource; deletion is the preferred remedy.
- **G7 — Grows coherently.** New capabilities extend observation and
  action without adding a second control-flow model or a second
  syntax. Growth stays explicit and preflightable.

### Procedural and declarative

The language is deliberately a hybrid, and the seam between its two
halves is the most load-bearing decision in the design. Naming the
seam early is what keeps later decisions consistent; most of the
language's prohibitions exist to keep it clean.

**The governing rule: the script is declarative about everything
Reliquary owns, and procedural at the seam with the guest.**

Everything knowable before the run starts is declared — the
platform, the machine state the script expects, which phases exist,
their timing budgets, the media it needs, the inputs it binds.
Everything the guest dictates is procedural — which key to send,
what text to wait for, the order its own installer screens arrive
in. The seam falls where our knowledge ends:

| concern | paradigm | why |
|---|---|---|
| machine shape | declarative (the blueprint) | ours, and knowable |
| which phases exist, their budgets | declarative | ours, and knowable |
| media and property references | declarative | ours, and knowable |
| keystrokes and observations within a phase | procedural | the guest's installer dictates the order |
| which route the run takes | procedural choice over a declarative graph | the guest chooses at run time |

**Why not fully declarative.** OS installation has a mature
declarative form — Kickstart, preseed, AutoYaST, Windows
`unattend.xml` — in which the author states what the installed
system should be and the installer does the rest. Where those
exist they are strictly better: Reliquary does not invent a
competing declarative install language. For guests that accept
them, it serves the answer file the way Packer does today — a
local HTTP server the installer fetches from (milestone 5;
[planning/design/http-serve.md](design/http-serve.md)).
Procedural keystroke scripting remains for the guests where
answer files do not exist: DOS, Win9x, and similar. G1's
agentless requirement is about the control plane — no dependence
on a guest agent or other cooperating software for observation
and input — not a ban on an installer's native answer-file
path. Using Kickstart (or its kin) is that path; it is not a
substitute for agentless scripting on guests that lack one.

**Why not fully procedural.** A plain imperative script — the
AutoHotkey or Expect shape — would be shorter to specify and would
need no phase concept at all. It is rejected because it forfeits
G3 and G4 together: a straight-line script with ad-hoc loops has
no statically knowable shape to analyze, and no named units to
report progress against. The declarative half is what makes a run
checkable before it starts and legible while it runs.

**The tensions this creates, which we accept.** These are real and
should not be papered over; several are already catalogued as
residual problems in `planning/design/script-examples/`:

- `phase` is a declarative construct whose body is procedural. The
  hybrid is not hidden; it is the point.
- A sequential phase is procedural, a reactive phase is
  declarative, and both are spelled `phase`. The two are forbidden
  to mix rather than given a combined semantics — a prohibition,
  not a definition.
- The paradigm boundary shows in the handler keywords: `on` is a
  case in a branching `wait`, `always` a standing rule in a
  reactive phase — one shape, two named lifetimes
  (`planning/design/script-examples/04`, resolved by the keyword split).
- Declarative timing scopes annotate procedural statements, so an
  observation's effective bound is not locally readable
  (`planning/design/script-examples/03`).
- Procedural `insert`/`eject`/`set-boot` mutate declarative
  machine state that outlives the run (`planning/design/script-examples/09`),
  deliberately diverging a machine from its blueprint until
  restored.

**The prohibitions that keep the seam clean.** Each exists to stop
the procedural half from eroding the declarative half:

- no author-side conditionals — the only decisions that matter are
  the guest's, expressed as observations of what it actually
  showed, never as the script author's logic (G2);
- inputs supply data and may never select a branch, a phase, or a
  path, so the graph stays static (G3, and the "one script, one
  target" principle below);
- no fallthrough and no anonymous phases, so every route is named
  and searchable (G3, G4);
- no `sleep` or `delay`, so every pause is justified by an
  observation rather than a guess about guest speed (G1, G5);
- no implicit machine teardown, so a failed run leaves state to
  diagnose rather than a tidied crime scene.

OS installation automation is expressed as install and verify scripts
attached to machine blueprints. Media acquisition (download, hash-verify,
cache under `cache/media/`) stays a host-side capability the language can
invoke, with pinned hashes kept in shared definitions or directly inside
the script.

## Landmarks

Landmarks — the image-match assets for GUI guests, the
`@landmark` matcher the growth rule names, and the assets U6's
recorder captures — are designed in
[planning/design/landmarks.md](design/landmarks.md): one
declaration owning geometry, with variant renderings sharing it
by construction; whole-screen exact match with `fuzzy`/`ignore`
modifier regions; the `.rlql` catalog form under authored-asset
resolution — declarations are files, never script content; and the
always-on cursor normalization contract. What remains open is
the GUI-era backlog's "Decide first" round.

## Script authoring by recording

U6's authoring recorder — Reliquary supervises a person doing
the task once in a Reliquary-owned console over the `vnc`
control plane, drafts the script and landmark assets, and on
later sessions anchors new fragments by playback position, never
regenerating or text-merging what the author wrote — is designed
in [planning/design/recorder.md](design/recorder.md). Delivery
sits in "Horizon" below; work items in planning/TASKS.md.

## Asynchronous runs

A script run can be started without blocking and observed while
it goes — the consumer story for the feedback split
(PRINCIPLES.md P5):
a person leaves an hour-long install and checks back (U1), an
automating program follows machine-readable events as they
happen (U3). Settled design (owner, 2026-07-21):

**The stream is written live.** `run-events.jsonl` is appended
event by event, flushed at each event boundary, from the first
preflight event to a terminal event stating the outcome. The
file is the update channel: every async affordance below is a
follower of the stream the run already produces, which keeps the
contract binding-clean (any language that can read lines can
follow a run — the C/Java constraint) and keeps daemons and
services permanently out of the picture. A record whose writer
died without a terminal event is detectably a *crashed* run.

**Sync is async plus attach.** A foreground `run-script` run is
defined as: start the run, immediately attach the live renderer.
One semantic, one code path — and a run started in one terminal
can be observed from another. Ctrl-C on a foreground run cancels
the run; Ctrl-C on a later reattach merely stops tailing.

**Detach hands off at the machine boundary.** `run-script
--detach`
completes parsing, binding, and static and capability preflight
in the foreground (G3 — those failures belong to the invoker's
exit code, never buried in a record), then spawns the runner and
prints the run id. The detached runner is an owned child exactly
as QEMU is: the run record carries writer identity (pid plus
start time), liveness checks verify identity before any command
targets the run, and stale records fail closed — the vm.json
doctrine applied to the runner.

**Cancel ends the run, not the machine.** `run cancel` requests
a stop; the runner ends at the next event boundary (input
deliveries are atomic, host transfers abort — the execution
model's severability), writes a `cancelled` terminal event, and
leaves the machine as-is per the no-implicit-teardown rule;
`--stop-machine` opts into the visible hard power-off
(the flag mirrors `cancel(stop_machine=)` — flags mirror
parameters even in the run family; owner, 2026-07-21). Cancelled
exits
with its own code (`5`): deliberately neither success nor RUN
FAILURE.

**Run identity is machine-scoped.** Runs number monotonically
per machine, never reused; the record lives at
`cache/machines/<machine-id>/runs/<n>/` and `<machine-id>/<n>`
is a run's full identity. The `run` operations take the number
as an ordinary positional argument (the property-family
precedent), defaulting to the machine's latest run, with the
machine chosen by the ordinary `--machine` / `--blueprint`
selectors.

**Retention is machine-bounded and explicit (owner,
2026-07-21).** A run record is append-only, never rewritten, and
never implicitly pruned: the only deleters are machine
`destroy`/`recreate` and the explicit `run delete` — a `run`
family member, never a `clean` one, because `clean`'s own
invariant is that nothing irreplaceable is cleanable, and
records are evidence, not regenerable output. `run delete` alone
never defaults to the latest run (deleting evidence warrants
naming it): numbers are explicit, several may be given, a live
run's record is refused (fail closed, naming the writer), and
deletion frees no number. The record directory is self-contained
and self-identifying (machine id, run number, timestamps, script
digest — distinguishable across `recreate` generations that
reuse a machine id); copying it out with ordinary tools is the
sanctioned way to keep a record beyond its machine, and there is
deliberately no export verb for it — the record is already
host-side plain files at a reported path. Contract home:
script-spec.md "Failure, runs, and transcripts"; custody model
in PRINCIPLES.md (P4, the artifact-residency split) and INTERFACES
(recorded outputs).

**Interaction runs — the opt-in bracket (owner, 2026-07-22).**
A primitive-driven loop earns the same evidence a script gets:
`begin-run` (twin `begin_run`, returning the new run number)
opens an ordinary run record whose driver is the caller; while
it is open, every machine-targeting command on that machine —
the guest-console family, the state operations, lifecycle —
appends the event kinds the execution model defines for the
same actions, and `end-run` closes the record with the neutral
`ended` terminal event (Reliquary attaches no outcome to an
interaction run — G2). With no open run, primitives record
nothing: recording is opt-in, so the automator opts in exactly
when the record is the product (U3) and interactive fiddling
never spams records. One run may be open per machine —
`begin-run` and `run-script` both fail closed naming an open
run (mixed-driver records are U6's recorder machinery, grown
from this shape through the reserved handover kinds). An
interaction run has no resident writer: each command appends
under the machine's exclusive lock, the crashed-run rule stays
script-run-scoped, and openness is visible, never inferred —
`run status` shows the open run and its last-event time,
`run cancel` refuses it naming `end-run`, `run delete` refuses
it while open. Followers are indifferent to the driver:
`run tail`, `attach_run()`, and `list runs` treat interaction
runs as ordinary records that self-identify their driver.
U3's per-test loop rides these mechanics: selection in as
script properties, results out as caller-authored artifacts
the caller reads out-of-band from the stopped machine's drives
at rest, and deliberately no
test-result vocabulary in Reliquary (G2) — one iteration is
one run record. Contract home: script-spec.md "Failure, runs,
and transcripts".

**Two presentations, under parity.** The CLI carries
`run-script --detach`, the `run` noun family — `run status`,
`run tail` (rendering per the decided progress vocabulary:
pretty on a tty, plain and jsonl for programs), `run wait`
(its exit code mirrors the run's outcome, so unbound languages
get results by waiting), `run cancel [--stop-machine]`, and
`run delete <n> [<n> ...]` — and
`list runs`. The embedding API's twins: `run_script()` stays the
blocking form; `start_script()` returns a run handle —
`status()`, `events(follow=)` as a blocking iterator,
`wait(timeout=)`, `cancel(stop_machine=)` — plus `delete_run()`;
`attach_run(machine=, blueprint=, run=None)` reopens a handle
from a fresh process, the run number defaulting to the machine's
latest exactly as the CLI `run` operations do. The handle is
pull-only: no callbacks, nothing a common binding language
cannot express directly. `wait(timeout=)` completes exactly as
the blocking form — same result, same raises — and expiry
raises outside the error taxonomy (Python: the builtin
`TimeoutError`): nothing failed, the handle stays valid, the
call repeats (owner, 2026-07-21). A handle is a follower, never
the owner: dropping one never affects its operation — GC timing
carries no semantics in any binding, and `cancel()` is the only
cancellation. A caller wanting concurrency without
any of this still runs the blocking form on its own thread —
computation stays on the caller's side of the seam.

**Synchronous programmatic runs — the blessed divergence.** The
sync forms are twins in capability but divergent in presentation
— a named decision, not drift: `run_script()` returns a typed
result and raises by error class, while the foreground
`run-script` command speaks the stream and its exit code.
Rendering is
selected explicitly with `--progress (auto | pretty | plain |
jsonl)` (default `auto`, tty detection — the decided BuildKit
vocabulary) on the stream-bearing commands — `run-script`,
`run tail`, and `fetch-media`. Under `jsonl`, stdout carries the event stream as
JSON lines and nothing else, ever — diagnostics go to stderr —
and because the stream ends with the terminal event, the last
line is the machine-readable result: no separate result mode
exists. Prompting is confined to interactive contexts (a tty
under `auto`/`pretty`); `plain`/`jsonl` runs are noninteractive,
so a missing input value is a PREFLIGHT ERROR before the machine
starts and a program can never hang on a hidden prompt. This
settles renderer selection and jsonl stdout purity for the
stream-bearing commands; the general stdout/stderr discipline
and the stability contract across every command are settled in
"The CLI" above (owner, 2026-07-22).

**Fetch progress — the same model (owner, 2026-07-21).** Media
movement emits the same transfer and verification event kinds
wherever it happens; only where they land differs. Inside a
script run they ride the run's stream (the transfer events
above). Standalone `fetch-media` renders them itself under the same
`--progress` vocabulary — jsonl stdout purity and the
no-prompt rule included, so the mismatched-file checkpoint
prompts only under `auto`/`pretty` and fails fast under
`plain`/`jsonl`. The stream is ephemeral: media has no state
document and there is no fetch record — nothing persists,
nothing reattaches; run records remain the only recorded
outputs. Machine operations that fetch implicitly outside a run
(`create-machine` / `start-machine` / `apply-blueprint` /
`recreate-machine` reconciliation) render the
same events under the same defaults, under the output discipline
in "The CLI" above. Honesty
rules carry over: byte totals only where the source names them,
hashing and extraction elapsed-only, each mirror attempt its own
event. On the API, `fetch_media()` stays the blocking form
(typed result, errors by class); `start_fetch()` (same
parameters) returns a pull-only fetch handle — `status()`,
`events(follow=)`, `wait(timeout=)`, `cancel()` (aborts at an
event boundary; the partial download is deleted, no pre-existing
file touched). There is no attach-by-id and no CLI command —
`start_fetch` is the one async starter without one (owner,
2026-07-21): an ephemeral stream is process-local, reattachment
is what run records provide, and a CLI driver backgrounds
`fetch-media` itself, the process being the handle. The
handle form is noninteractive by construction and rejects
`on_mismatch="prompt"` — a background fetch can never hang on a
hidden prompt. Contract home: media-spec "Fetch progress".

## Milestones

Milestones run in order — the numbering is the priority. The
numbered arc runs from text-mode DOS on QEMU through the
complete documented design for that one vertical, and **ends
there: milestone 9 is the last numbered milestone**.
Milestones 1–3 are history: the north-star vertical
slice, the media library, and the scripting language on its
first, now-superseded surface. Milestone 4 is complete: the
tree speaks the July 2026 redesign. Milestone 5 (complete) added
Packer's local HTTP server for installer answer files, and
Milestone 6 (complete) delivered the instance model and machine
blueprints with authored-asset residency. Milestone 7 (complete)
folded the blueprint and media formats into one composable
blueprint (the 2026-07-23 composition round); milestones 8–9
then complete the documented design — the script properties,
and run records with asynchronous runs — still for the DOS
platform on the QEMU backend alone. **Milestone 8 is the
current one.**

Generalizing beyond that vertical is **backlog work, not yet
scheduled** (owner, 2026-07-23, for lack of use-case backing —
planning/DECISIONS.md D33): the adapter seam extracted from
working code, the second backend that proves it, native guest
agents, and the arc's former endpoint — the GUI era: the VNC
control plane, GUI installer scripting, and the last backends,
Hyper-V deliberately last. Each keeps its own section below,
design settled and intact; machine mobility — clone, export,
import — sits in Horizon on the same ground. Scheduling is
acceptance (D23): the citing roadmap item is the acceptance
record, so a backlog section returns to the numbered arc when
the case it serves is accepted.

A milestone that needs decisions opens with them: its "Decide
first" block is the design round to run before its deliverables
start. Each milestone is independently shippable: the tree
builds, the test suite passes, and the FreeDOS install keeps
working end to end on whichever surface that milestone provides.
Within a milestone the listed deliverables are ordered but may
land in separate commits. Horizon holds what the arc
deliberately does not deliver — the U6 authoring recorder above
all — each item earning a numbered milestone when its turn
comes.

### Milestone 1 — The north-star command (complete, on the superseded surface)

```powershell
rlq run-script install --blueprint freedos
```

From a clean home, that one command must end with a fully
installed FreeDOS machine that can then be started and stopped
from the Reliquary command line. Everything in this milestone is
the minimum vertical slice of the documented design needed to get
there — each piece grows to its full spec in later milestones. The
built-in blueprint bundle is the public vertical slice for this
milestone.

Deliverables:

1. **Media library core** (of planning/design/media-spec.md): definitions as
   user-owned documents under `media/`, fetch/extract/SHA-256
   verify on demand, the two-cache split (`cache/downloads/`,
   `cache/media/`) — enough to feed the FreeDOS LiveCD.
2. **Blueprint and machine core** (of planning/design/machine-blueprint.md
   and planning/design/instance-model.md, QEMU-only): parse and validate the
   blueprint shape the codex needs (`platform`,
   `memory`, `drives` with `size` and `media`, `boot`, `name`,
   `description`, `scripts`); machines wholly under
   `cache/machines/<id>/` with `reliquary-machine.json` and
   qcow2 materialization; `create`, `start`, `stop`, `destroy`,
   `list machines`; selection by `--blueprint` (sole machine) and
   `--machine` (git-style prefix).
3. **Scripting core** (of planning/design/script-spec.md): enough of the
   `.rlqs` language to express the FreeDOS install and
   verification — parsing, `wait`/`expect` on normalized screen
   text, `enter`/`type`/`press`, `select`, `screenshot`,
   `start`/`stop` — and `script <label>` resolution through the
   blueprint's `scripts` map, creating a machine when the
   blueprint has none.
4. **The codex** (planning/design/codex.md): the
   `codex/` tree (zip-bundled when packaged), copy-out on
   first reference, the never-overwrite rule, and
   `freedos` — blueprint, media definitions, and
   install/verify scripts — as its first entries.
5. The built-in blueprint flow replaces the old root-home
   `drives/`/`machine.json`/`vm.json` layout (pre-release: no
   migration).

Spikes (ordered; each leaves the tree green and proves one
seam; later spikes consume earlier ones). Suggested parallel
tracks: 1→2→3→4→5→6 alongside 8, then 7→9→10→11→13→12. Spike 7
can start after 4; spike 9 needs 6 and 8; spike 12 consumes 13
(persistent `insert`/`eject` is how verify boots the installed
disk — no thin `apply` needed). Highest risk: 3
(cache/hash rules), 9 (LiveCD menu timing), 13 (persistence
semantics reach into `start` reconciliation).

1. **New home layout (additive; complete)** — path helpers for
   `blueprints/`, `media/`, `scripts/`,
   `cache/{downloads,media,machines}/` alongside the existing
   `drives/` / `machine.json` / `vm.json` model. Exit: unit tests
   assert the helpers (including `home=`) resolve under the
   effective home; callers of the current machine path are
   unchanged. Out: migration; cutting the tree over to the new
   layout (spikes 5–6 and 12).
2. **Media definition (item form only; complete)** — parse/validate one
   FreeDOS-shaped definition; resolve by name from `media/`.
   Exit: load a `freedos-livecd`-like JSON; reject bad
   hashes/fields. Out: archive multi-item, `search`/`list`/
   `clean`, eager whole-library scan extras.
3. **Fetch → two caches (complete)** — download → `cache/downloads/`,
   extract/verify → `cache/media/`. Exit: one LiveCD zip lands
   as a verified `.iso` on demand; never-overwrite payload.
   Out: CLI media verbs, mirror lists beyond what is needed.
4. **Blueprint subset (complete)** — parse/validate `platform`, `memory`,
   `drives` (`size`/`media`), `boot`, `name`, `description`,
   `scripts`. Exit: reject unknown/invalid; resolve media names
   against spike 2. Out: controllers, `base`,
   `backend-settings`, `apply`, full cookbook.
5. **Machine materialize (complete)** — `create` → `cache/machines/<id>/`
   + `reliquary-machine.json` + qcow2 from `size`; insert
   cached media. Exit: `create` then inspect state/drives; QEMU
   can see the ISO. Out: locking/recovery polish, `recreate`,
   clone/export.
6. **Lifecycle CLI (complete)** — `start` / `stop` / `destroy` /
   `list machines`; `--blueprint` (sole machine) /
   `--machine` prefix. Exit: start/stop a created
   FreeDOS-shaped machine from the CLI. Out: `apply`,
   interaction subcommands, multi-backend.
7. **Codex seed (complete)** — `codex/` tree + copy-out on first
   reference + never-overwrite (+ packaging zip path). Exit:
   `--blueprint freedos` seeds home files once;
   second call leaves them alone. Out: `pull`, provenance
   columns, full index/`search`.
8. **`.rlqs` parse (FreeDOS shape; complete)** — header + state-machine +
   the verbs that example uses. Exit: parse the documented
   install script; useful parse errors. Out: linear-only path,
   `on`/reactive, `insert`, inputs/properties.
9. **Script runtime on QEMU/DOS (complete)** — `wait`/`expect` on
   normalized VGA text; `enter`/`type`/`press`/`select`;
   `screenshot`; `start`/`stop`. Exit: drive a tiny hand
   fixture script against a live guest (or the LiveCD menu).
   Out: full waterfall, guest agent, VNC.
10. **`script <label>` wiring (complete)** — resolve via blueprint
    `scripts` map; create machine if none; run record under
    `runs/`. Exit: `rlq --blueprint … script install` invokes
    runtime end to end (may still fail mid-install). Out:
    embedded media blocks, property-bound inputs.
11. **Author `freedos` (complete)** — blueprint + media
    definition (URL + license assertion) + install/verify
    scripts in `codex/`. Exit: artifacts resolve and the
    install script matches the LiveCD flow. Out: other OS
    codex entries.
12. **Verify path (complete)** — `script verify` boots the
    installed HDD through spike 13's model (blueprint boots
    `hdd0` then `cdrom0`; install script's final `eject` leaves
    a plain `start` booting the hard disk). Exit: north-star done
    criteria green. Out: full milestone-6 `apply` semantics.
13. **Media-in-script model (complete)** — the machine-state design for
    install media: blueprints declare empty removable drives
    (`"cdrom0": null`) and no installer media — the blueprint
    alone defines machine topology, so `insert`/`eject` never
    create or remove a drive, and a script naming an undeclared
    slot fails static preflight; scripts `insert`
    a defined media item to a declared slot and `eject` it, persisted in
    `reliquary-machine.json` across stop/start (the machine
    diverges from its blueprint until the script's final
    `eject` restores it); the `machine: running|stopped`
    script header, with `stopped` scripts starting the machine
    explicitly after inserting media, and `script` no longer
    unconditionally auto-starting. Media definitions stay
    separate library documents for builtins (embedded blocks
    remain a later milestone). Exit: the FreeDOS install script
    inserts the LiveCD into an empty blueprint slot, installs,
    ejects, and a subsequent plain `start` boots the hard
    disk. Out: `apply` (recovery for diverged machines is
    milestone 6), embedded media blocks, hot-swap polish beyond
    what the install needs. Runs before spike 12, which
    consumes it.

Done when: `rlq --blueprint freedos script
install` runs unattended from a clean home to an installed
machine; `rlq --blueprint freedos script verify`
confirms the installed disk boots to a DOS prompt; and `start` /
`stop` control the machine from the CLI.

### Milestone 2 — Media library and caches (complete)

The remainder of [planning/design/media-spec.md](design/media-spec.md) beyond
milestone 1's core, plus the media-facing CLI (`list media`,
`search media`, `pull media`, `clean`).

Deliverables:

1. Definitions as user-owned documents under `media/`, both
   forms: item (direct download) and archive (multi-item), with
   derived defaults (`url`/`local-path` → `file` → `name` →
   cached name), mirror URL lists, `local-path`,
   `file-extension`, and the item/archive `sha256` rules.
2. Eager whole-library scanning before any media operation, with
   library-wide duplicate-name detection and the
   normalized-descriptor collision rules (the shared groundwork
   for embedded script blocks in milestone 3).
3. The two-cache split: source archives under `cache/downloads/`,
   payloads under `cache/media/`; fetch/extract/verify on demand,
   cheapest source first (verified payload, then cached archive,
   then mirrors). Verification on every use: a payload that fails
   its hash is refetched when a source exists and the deletion is
   approved — an interactive checkpoint, a fast programmatic
   failure, or pre-approval (`--refetch-mismatched` on the CLI,
   `on_mismatch="refetch"` in the API); a mismatched file with no
   source is always kept and reported (see the media spec's
   mismatched-files rules).
4. `rlq fetch <media_name>` and `Reliquary clean
   downloads` / `clean media` (nothing irreplaceable —
   definitions, `local-path` files, sourceless payloads — is
   cleanable). `fetch --script` follows in milestone 3 with
   script parsing.
5. `list media` and `search media` over the built-in index and
   user definitions, with the `yes`/`seeded` provenance column;
   `pull media <name>`.

Done when: the FreeDOS media flows through a definition end to
end; a deliberately corrupted cached payload heals on next use
once its deletion is approved and is kept intact when it is not;
`clean` reclaims only restorable files; the install script passes
on the completed layer.

### Milestone 3 — The scripting language (complete, on the superseded surface)

The remainder of the script spec beyond milestone 1's core,
completing the then-documented design for DOS on QEMU. The
deliverables below record what was built; the July 2026 spec
redesign supersedes their syntax, and milestone 4 retargets
them. Two exceptions to "what was built", left standing as the
record: the embedded-media parts of deliverables 5 and 7
(installation rules, `fetch --script`) and the Done-when clause
naming embedded media blocks were planned but never implemented —
`media` blocks parsed and nothing consumed them — and the
2026-07-22 no-JSON-in-scripts decision deleted the feature
outright rather than completing it (planning/DECISIONS.md).

Deliverables:

1. Parser and static analysis per the blueprint: headers, linear and
   state-machine shapes, sequential vs. reactive states, string
   escapes and raw strings, duration literals, the portable key
   vocabulary (settling that open decision), and the full
   validation/warning lists — all before any guest input.
2. The execution model: `wait`/`expect` observations (normalized
   text, regex, `stopped`), reactive `on` dispatch with the
   edge/episode arming rule, `timeout`/`deadline`/`stable`
   semantics, explicit `->`/`done` transitions.
3. Action verbs on the machine model: `enter`, `type`, `press`,
   `select` (feedback-driven, never guessing), `screenshot`,
   `insert`/`eject` (persistent state-document changes — never
   the blueprint — surviving stop/start per spike 13's model),
   and `start`/`stop`.
4. Property declarations: `property [type] <key>` with
   `${key}` binding by the flattened source order — explicit
   `--property` value → blueprint parameter (direct or
   redirect) → environment → file → the once-per-key interactive
   ask — kind mismatches and unbound noninteractive keys
   failing before the machine starts, and the secret contract
   (expansion only in `enter`/`type`, transcript omission,
   diagnostic redaction, failure-screenshot suppression).
5. Embedded `media <label> { }` blocks: the transactional,
   non-overwriting installation rules against the library
   groundwork from milestone 2; `fetch --script`.
6. Run records per the blueprint: a per-invocation directory under
   the machine's cache `runs/`, the full transcript contract
   (lines, states, observations, input provenance, installed
   definitions, selected control plane, artifacts), failure
   capture, and no automatic retry.
7. `rlq script <script_name> --machine/--blueprint` (preflight,
   embedded
   media installation, implicit create/start) and
   `rlq check-script` (read-only, with optional machine
   and property binding for capability preflight).
8. `list scripts`, `search scripts` (built-in index plus user
   files, with provenance), and `pull script <name>`.

Done when: the FreeDOS install and verification scripts
exercise the full language (states, properties, embedded media
blocks, run records), and transcripts honor the provenance and
secret-redaction contracts. At this point everything `planning/`
documents is implemented for DOS on QEMU.

### Milestone 4 — Script-surface realignment (complete)

The July 2026 script-language redesign
([planning/design/script-spec.md](design/script-spec.md), with
`reliquary/codex/scripts/freedos-install.rlqs` as the
reference script)
supersedes the surface milestones 1 and 3 implemented.
This milestone gated everything after it: later milestones
start only once the tree speaks the new surface. Pre-1.0, the
old surface is deleted, not bridged.

Decide first: nothing — the gating decisions were settled in
July 2026 and folded into the spec (the adjudication trail is
planning/DECISIONS.md: the milestone-zero round — `<key>`-token
deletion, the `on`/`always` split, the cyclic-deadline rule,
linear endings and the two-handler minimum, `set-boot`, the
validation batch — plus the spec-craft and observation-channel
rounds), and the execution-model-before-runner sequencing rule
is satisfied: the spec's "Execution model" section is written,
so the runner retarget may begin. One confirmation remains
in-milestone: the portable key-name vocabulary for `press` is
published in the spec as a closed set — confirm it against the
converted scripts.

Deliverables:

1. Retarget `script.py` to the node grammar and typed EBNF: the
   three-production skeleton plus per-node signatures; no colons
   or commas, `name=value` properties, `/regex/` literals, `@`
   media references, `$`/`${}` property references, and the
   colon-free noun-first headers with `entry` and the run-level
   `deadline`.
2. The renamed vocabulary: `phase` (was `state`), `goto` (was
   `->`), `finish` (was `done`); `expect` folded into the
   branching `wait { on ... }`; `always` for reactive handlers
   (`on` only in branching waits); `set-boot` (was `boot`); no
   `<key>` tokens (keys only after `press`);
   the `regex` keyword replaced by the regex literal.
3. Observation channels, screen-default form: a bare string or
   regex is the screen observation's only spelling (`screen=`
   does not exist), `machine=stopped` is the only machine-state
   spelling (no bare `stopped`), one condition per observation,
   and unknown or wrong-kind channels as validation errors.
4. The timing model: lexically scoped `timeout`/`stable` defaults
   (innermost wins), per-activation `deadline` budgets (fresh per
   phase entry; the header `deadline` backstops the run), the
   placement matrix enforced as parse errors, and failure
   diagnostics naming the expired clock and its source scope.
5. `script_runner.py` retargeted, and `check-script` grown to
   report the resolved timing plan (each observation's effective
   timeout and source scope).
6. The built-in and example scripts converted, and every document
   that quotes script syntax updated (README, planning/examples/README);
   the reference script now IS the converted builtin
   (`reliquary/codex/scripts/freedos-install.rlqs`).
7. The CLI/API surface renames the July 2026 queues decided
   (planning/DECISIONS.md): the twin-name identity sweep —
   `run-script`, `fetch-media`, the `seed-` family,
   `new-blueprint`, `import-vm --name`, `check-script`, the
   dashed `list-`/`search-` forms, the property family noun-last
   — with `create_machine` / `start_machine` / `stop_machine` /
   `destroy_machine` replacing `create_from_blueprint` and
   `machines.start`/`stop`/`destroy`; id-only `--machine`
   selectors; and uniform flag position (the `cli.py` SUPPRESS
   workaround retires). docs/ and README follow the renames.

Done when: the FreeDOS install and verify scripts run end to end
in the new surface, `check-script` reports the timing plan, and
no old-surface syntax or superseded command spelling survives
anywhere.

### Milestone 5 — Local HTTP server for installer answer files (complete)

Packer's host-side pattern for serving Kickstart, preseed,
AutoYaST, `unattend.xml`, and kin: during a run, Reliquary
starts an ephemeral local HTTP server that exposes authored
answer files to the guest installer over the VM network, then
tears the server down when the run ends. This is how guests
that already have a declarative installer path consume it —
not a competing declarative language, and not a replacement for
agentless keystroke scripting on guests that lack one
("Procedural and declarative" above;
[planning/design/http-serve.md](design/http-serve.md)).

Interface triage (planning/INTERFACES.md): strong alignment with
U1 (unattended install from vendor media) and with U4/U5 where
Windows and Linux answer files are the installer's native path.
Surfaces touched: scripting language (declare what is served;
bind the server's address into typed/entered installer
arguments), CLI/API (server lifetime bound to the run), and
authored-asset layout (where the files live). Distinct from the
deleted property-binding "response file" concept
(planning/DECISIONS.md) — these are installer answer files only.

Settled design:

- Scripts declare the run-scoped server with one declarative
  `http` block, not a blueprint field. Milestone 5 serves named
  generated content entries, each with a guest-visible path; the
  response body may be inline or read from one explicit file.
  Serving sibling directories is a later asset-distribution item.
- The live address binds as reserved run properties:
  `$rlq.http.ip`, `$rlq.http.port`, and `$rlq.http.url`, usable
  only where text property expansion is legal. The whole `rlq.*`
  and `reliquary.*` property namespaces are reserved for
  Reliquary-owned run facts and future system properties.
- QEMU uses user-mode networking as the milestone-5 interim
  reachability path, with `$rlq.http.ip` resolving to the
  guest-visible host gateway `10.0.2.2`; richer portable NIC
  modeling waits for the backend/device milestones.
- Port selection follows Packer's random free port in a configurable
  inclusive min/max range, defaulting to 8000-9000; min=max pins a
  single port.
- Generated content may expand script properties, including
  secrets. Rendered bodies are never recorded, secret-bearing
  responses are redacted in progress/records, diagnostics redact
  exact secret values, and automatic screenshots are suppressed
  after serving a secret-bearing response.

Deliverables:

1. Design recorded in
   [planning/design/http-serve.md](design/http-serve.md): the
   Packer-parity contract, the decided authored shape, address
   binding, lifetime, and network reachability rules.
2. The ephemeral HTTP server: serve a selected in-memory map of
   named content to guest-visible paths; pick a free port in the
   configured range when `http start` executes; stop on `http stop`
   and tear down on every terminal path (success, failure, cancel,
   crash of the run process).
3. Script/CLI/API surface for declaring named served content,
   selecting or redefining content at `http start`, and obtaining
   the live address for `type`/`enter` (and any boot argument path
   the decided binding uses), with CLI–API parity.
4. QEMU guest reachability for the FreeDOS-era networking
   defaults the milestone settles on — enough that a guest
   installer can `GET` an answer file from the host server.
5. A worked example (Kickstart or preseed shape is enough):
   authored answer file, script that points the installer at
   `http://<ip>:<port>/…`, and a Done-when path that proves the
   fetch.

Done when: a scripted install fetches its answer file from
Reliquary's local HTTP server exactly as under Packer — server
up for the run, address available to the script, file served,
server gone afterward — and the FreeDOS keystroke install is
untouched.

Completed 2026-07-22. The `.rlqs` language accepts a declarative
`http` block with named served content, inline triple-quoted bodies
or script-relative `from=` files, selected or redefined by
`http start`. The runtime starts the server at `http start`, binds
`rlq.http.ip` / `rlq.http.port` / `rlq.http.url`, stops explicitly
on `http stop`, and implies teardown on terminal paths. The shipped
OpenBSD 7.9 amd64 install blueprint exercises the response-file
path, while the FreeDOS keystroke install remains unchanged.

### Milestone 6 — The instance model and machine blueprints (complete)

The whole machine model beyond milestone 1's core —
[planning/design/instance-model.md](design/instance-model.md)
plus the [machine blueprint](design/machine-blueprint.md) with its
[field reference](design/machine-blueprint-reference.md) and
[cookbook](design/machine-blueprint-cookbook.md) — still scoped to
one backend. The `backend` field is parsed and validated in full,
but with QEMU the only implementation, assignment is trivial; the
adapter seam that makes it real is backlog work ("The backend
adapter seam" below). Capability checks
are real from the start, derived from what the QEMU
implementation can actually do.

> **Completed on the pre-composition authored formats** (`.rlqb`
> machine blueprint + `.rlqm` media definition, flat `drives/`,
> two schemas). The 2026-07-23 media/composition round folds these
> into one composable `.rlqb` **blueprint** of named components —
> that realignment is **Milestone 7** below
> ([planning/design/blueprint-model.md](design/blueprint-model.md);
> DECISIONS.md).

Decide first:

- Running-machine reconfiguration: how hot media changes vs.
  stopped-only changes (like memory) are surfaced in the CLI
  and script language.
- Concurrent machines: whether any home-wide limit applies to
  machines running at once (the per-machine lock and identity
  model suggests none).
- Whether `size`/`base` are valid on `cdrom` drives — the field
  reference says `size` is "meaningful for hdd and floppy"
  without prohibiting it elsewhere, and the schemas encode only
  the stated rules (the JSON-schema round's open find).

Deliverables:

1. Blueprint validation per the full field reference: `platform`,
   `backend`, `memory`, `cpus`, `drives` (slot convention and
   aliases, per-drive `controller`, `media` references, `size`
   blanks, `base` with `difference`/`duplicate`, `hostdir` host
   directories (served by vvfat on QEMU), `enabled`),
   `boot`, `control-planes`, `backend-settings` — format checks
   and capability checks both failing closed and naming the
   problem.
2. Machines wholly under `cache/machines/<blueprint>-<n>/` — the
   numbered id naming the directory is the machine's identity —
   with `reliquary-machine.json` (id repeated as a safety check,
   blueprint reference and resolved digest, creation time, phase,
   fully resolved configuration), canonical drive-image naming,
   and qcow2 materialization of the `size`/`base` triad. The QEMU
   layer re-anchors on it; `MachineConfig`, root-home
   `machine.json`, and `vm.json` are absorbed and deleted.
3. Lifecycle integrity per the instance model: operation
   generations, exclusive per-machine locks, atomic JSON
   replacement, and startup detection of interrupted phases with
   safe rollback or explicit recovery instructions.
4. The lifecycle CLI completed on top of milestone 1's verbs:
   `start-machine` grown to full reconciliation — baseline,
   state, backend identity, and re-verification of every
   referenced media hash — plus `apply-blueprint` (adopt
   blueprint edits into the baseline; drive-regenerating changes
   fail closed), `recreate-machine` (same id),
   `delete-blueprint` (machineless blueprint files only),
   `list-blueprints`, `search-blueprints` (built-in index
   plus user files, with provenance), `seed-blueprint` (closure
   by default, `--only` for the single file), and the
   `new-blueprint` scaffolder. Runtime changes update the
   state only; machines stay running until explicitly stopped.
   The global `--json` flag lands here, defined by the
   twin's-return rule ("The CLI" above).
5. The guest-console family (`type`, `enter`, `press`, `exec`,
   `select`, `wait`, `screen`, `screenshot`, `hmp`) and the state
   ops (`insert-media`, `eject-media`, `set-boot-order`) take the
   same `--machine`/`--blueprint` selection and resolve ownership
   through the machine state; `get-machine-dir` reports the
   machine directory (the out-of-band door —
   planning/design/instance-model.md).
6. Published JSON Schemas for the document types: publication
   mechanics and the shared valid/invalid fixture corpus (run
   against both parser and schema) for the authored blueprint and
   media-definition schemas
   (`planning/design/*.schema.json` — prose specs normative, the
   parser the validator), plus the machine-state schema, authored
   here once the state format settles.
7. `planning/examples/` updated to the implemented shapes
   (`planning/examples/blueprints/`, an explicit `create-machine
   --blueprint` step in its README) — or the docs corrected where
   implementation proves the planned format wrong.
8. Authored-asset residency ("Authored-asset resolution" above):
   the resolution module (the single `--assets` knob — home mode
   vs a hermetic project dir), the `.rlqb` / `.rlqm` extension
   renames, the `builtins/` → `codex/` package rename and the
   codex index, the blueprint-source state field, and selection
   scoping.
9. The shared JSONC reader for authored documents (RFC 8259 plus
   `//` and `/* */` comments and trailing commas, nothing more;
   string-aware, comments replaced by spaces so error positions
   survive; every machine-written file stays strict JSON), the
   remaining media-definition
   surface (definition-level `description` / `notes`,
   archive-level `local-path`,
   sourceless definitions failing resolution naming the
   definition to edit), API parity for the media commands
   (`fetch_media(script=)`, `clean_archives()`,
   `clean_media()`), and the codex teaching comments at
   blueprint seams.

Done when: the FreeDOS install script runs against a machine
created from the example blueprint in a clean home;
`destroy-machine` + `create-machine` regenerates the
materialization from blueprint and media
alone; a process killed mid-operation is detected and recovered
per the instance model; blueprint edits round-trip through
`apply-blueprint` with drive-regenerating changes failing closed.

### Milestone 7 — The composed blueprint model (complete)

> **Complete** (2026-07-23), landed in six stages: S0 the
> launching-point renames (D21), S1 blueprint-model.md as the
> normative model, S2 the conformance corpus written against it
> before the parser, S3 the format core as one landing —
> `document.py`, `resolve.py`, `acquire.py`, the codex and
> example blueprints, the one schema — S4 the cache rework and
> its media command family (D30), S5 the remaining spec
> realignment by dividing the job. The sprint breakdown was
> pruned from planning/TASKS.md on landing per its own rule;
> git history and D21/D22/D30/D32 carry the detail. D32 came
> out of S2 running against S3 — a corpus and a parser written
> from one spec, differentially testing that spec.
>
> Done-when verified 2026-07-23: the FreeDOS install script ran
> end to end against a machine freshly materialized from a
> composed-format `.rlqb` (inline anonymous blank hdd, empty
> cdrom, the LiveCD through its zip), the verify script booted
> the installed system to `C:\>` and powered it off, and
> `prune-media` afterward left exactly the attachment closure —
> the extracted ISO cached, the zip husk gone.

Realign the authored surface to the composed blueprint model as
revised by the second 2026-07-23 design round (DECISIONS.md, "THE
BLUEPRINT REVISION ROUND" — it supersedes the first round's
four-component shape before any of it was implemented — with
D24, D26 and D27 now folded into
[blueprint-model.md](design/blueprint-model.md), which
deliverable 1 rewrote and which is the normative home for the
model in their place). Milestone 6 completed on the
pre-composition
formats; this milestone folds the machine blueprint and the media
definition into one `.rlqb` format of two spec types — machine
and media — and lands the consequent cache and materialization
reorganizations. Still DOS-on-QEMU only — a format and
materialization reshape; beyond deliverable 4's media command
family, no new capability. No backward compatibility: the
pre-composition formats are replaced, not bridged (P9).

Demanded by **U4** above all — the committed, hash-pinned
definitions a second developer builds from in place, and the
disk they reclaim when the work cycle ends — with **U1** (the
codex-seeded one-command install the format has to keep
serving), **U5** (the author's parameter seams, which the
property-valued location and the inline media are), and **P4**,
**P7**, **P12**. D22's supports line traces each; the
deliverables below name the ones they answer to. That trace
sat only in retired D17 until 2026-07-23 — a milestone this
size standing on an entry that binds nothing is the shape the
demand-citation sweep exists to catch.

Decide first: the media lifecycle commands — DECIDED (D30), the
round TASKS.md had queued and this milestone had overlooked: the
noun in every media verb is the media, never the owning file;
`delete-media` and `seed-media` are deleted rather than kept as
a failing command and a no-op (P9), the first of them having
contradicted its own design doc since the composition round;
and `list-media` keeps its plain name list with provenance
behind `--verbose`. Deliverable 4 extends a family this round
cleaned first.

The other gating item, the `${…}` reference
/ media-locator grammar, went through its
scenario battery and is recorded in DECISIONS.md (D24, the
reference grammar battery): the shape D22 settled holds, with the
escape amended to `\${` and the reach widened to full
interpolation anywhere a string value is accepted, under the rule
that a reference may supply any value that does not participate
in identity or resolution structure — as trimmed by D26 (the
reach trim and the string-grammar closure), which adds one clause
to that rule, no reference may supply a closed-vocabulary value,
and closes the `${…}` body itself: operations closed at its two
productions — the character class `[A-Za-z0-9._:/-]` screening
and the productions deciding, D27 correcting D26's claim that
the class alone was the test — while namespaces (new
qualifiers) stay open. Everything else was already
settled (optional root `type` defaulting to media; the plural
sections retired, a lone spec object kept as sugar for the array
of one; the source type and composition declined).

Deliverables:

1. **blueprint-model.md rewritten as the revised model's worked
   design** — folding D22, D24, D26 and D27 into one normative
   document, replacing the superseded first-round shape its
   banner currently disclaims. This leads the milestone rather
   than trailing it (it was deliverable 6's first half) because
   everything below is built against it, and building against
   four chained decision entries instead is how `document.py`
   came to hold 730 lines of the first-round model that D22
   superseded the same afternoon — a spec is what an
   implementation gets checked against, and the check is not
   available until the spec exists. The rest of the spec
   realignment stays where it was, at deliverable 7: those
   documents legitimately follow the code. Demand: none of its
   own — it serves every demand below and adds none, being the
   gate they are checked against (P8's argue-then-build
   discipline made concrete).
2. The revised `.rlqb` parser/validator: the root an array of
   specs (a lone spec object accepted as sugar for the array of
   one, same rules — an untyped lone object is a media);
   `type` optional defaulting to `media`, a machine
   declaring `"type": "machine"` (the media branch's
   unknown-field error carries a did-you-mean hint when machine
   vocabulary appears), optional checked `type` echoes at nested
   positions; media absorbing archive under parent/children
   containment — any media may declare `children` (batch sugar,
   recursive, path-form entries, a bare string being the path)
   or its `parent` from the child side, every edge resolving to
   child-declares-parent, the mount/container reading decided
   per reference site; bare-string root specs desugaring to
   `{ "location": … }`; inline media at drives (a full spec, or
   the `{ "size": … }` blank, `size` implying `new`);
   name-or-nothing identity (explicit or content-stem names into
   the one catalog; the anonymous blank site-identified,
   slot-named at materialization) under the name rules of D24 —
   the `media-name` production is the charter (the script `name`
   production with a leading digit allowed, split from the
   letter-initial `property-key`), an out-of-charter
   stem is repaired with a warning naming the derived name and
   its source, a stem that cannot be repaired or does not exist
   fails closed demanding an explicit `name`, and names match
   case-sensitively but collide case-insensitively;
   identity-dedup (identical
   same-`(name, type)` specs coexist, differing collide, in-file
   duplicates error); and the location grammar — one `location`
   field: bare-path / `https:`-`http:` /
   `${media:<name>}[/<path>]` / `${<key>}` strings,
   the explicit object forms (`url` / `local` / `parent`+`path`
   incl. an inline parent spec / `property`) as canonical form,
   mirror lists (mixed schemes; singleton is the scalar, empty
   and nested illegal), unrecognized-scheme-shape
   parse errors — all parsed by the one shared media-locator
   component. With them the reference grammar as hardened by D24:
   unqualified `${key}` interpolating anywhere a string value is
   accepted, `\${` the literal escape, resolved text never
   re-scanned, references refused in `name` / `type` / `children`
   paths / object keys and — under D26's trim — in the closed
   vocabularies (`platform`, `backend`, `materialize`,
   `controller`, `control-planes` items), the `${…}` body itself
   closed to its two productions — the character class
   `[A-Za-z0-9._:/-]` screening and the productions deciding
   (D27), so that a body carrying any operator is a parse error
   naming the malformed reference — this is where the spec half of
   P14 (the expressive ceiling) is honored, and this deliverable
   is that principle's acceptance, its script half being honored
   already; qualified `${media:…}` whole-value with
   its optional `/<path>` second component (bare form =
   `{"parent": …}`, no path), unknown and reserved qualifiers
   failing closed, path suffixes normalized against `..` /
   absolute / empty segments, containment cycles named, and
   two-phase validation — shape at parse, value at resolution,
   which is where the `sha256`-required-once-remote check and
   non-string coercion now land; `${key}` binding is deferred to
   milestone 8 (failing closed naming properties until then).
   `.rlqm` retired. All fail-closed, naming the problem. (P14,
   as stated above; U4 and U5 for the closure's local price —
   the checked-in source a schema validates and an editor
   completes.)
3. Media and materialization **re-anchored** on the revised
   model (media.py / machines.py). Most of this deliverable is
   already standing and survives the reshape: the four
   `materialize` modes, conditional `sha256`, the cdrom
   read-only rule, recursive zip extraction, and per-machine
   materializations under `cache/machines/<id>/media/` keyed by
   media name rather than slot — so removable-slot swaps never
   clobber — all landed on the first-round model. What remains
   is what the revised model actually changes: extraction
   re-expressed over parent/children containment rather than
   archive/members, the anonymous blank slot-named at
   materialization (it has no catalog name to be keyed by), and
   the container-format roster stated and enforced — zip only
   this milestone, an unsupported container failing closed and
   naming its format (ISO9660 and its `[BOOT]` virtual paths are
   the recorded follow-on). (U4 — the rig built from committed
   definitions alone; U1 for the seeded install that rides the
   same path.)
4. The cache rework — **delivered**: the single name-keyed
   `cache/media/`
   (`cache/archives/` retired), the identity ledger (recorded
   sha256, derivation keys, provenance
   refetchable/derived/supplied, source lineage), the
   deterministic preflight identity check feeding the
   on-mismatch contract with lineage-informed messages; the
   command family with API twins — `clean-media` (blunt; spares
   `supplied`; skips running-machine attachments), `clean-media
   <name>` (targeted eviction), `prune-media`
   (attachment-closure prune; scope-relative; `--dry-run`), and
   `add-media <name> <file>` (the guarded door — a pinned
   unlocated media resolves by cache hit). U4 writes this
   deliverable twice over — *"the developer disposes of the
   large VM and reclaims the disk space"* is `prune-media` and
   `clean-media`, and *"supplying just the two things the
   repository cannot provide"* is `add-media`, which is why the
   milestone's one piece of new capability needs no new use
   case; P12 for the cache staying under its own root, P6 for
   the twins.
5. The machine directory reorganization — **delivered ahead of
   this milestone**, with milestone 6's absorption of the
   root-home machine model: `drives/` → `media/`
   (`_machine_media_dir`), backend files into a backend-named
   subdir (`_backend_dir`), and `reliquary-machine.json` →
   `machine.json` with `vm.json` folded in as a while-running
   state section written atomically with `phase`. Kept in the
   list as the record of where it belonged; no work remains.
   (P12 — the layout is the home contract; P9 for renaming
   rather than bridging.)
6. One published blueprint JSON Schema — the two-variant root,
   machine requiring its declared `type`, media accepting its
   absence — replacing the two milestone-6 schemas; the
   conformance corpus reworked to the revised format. The closed
   vocabularies stay plain `enum`s, never widened to admit a
   reference pattern — which is what D26's reach trim buys, and
   the completion it protects is the point (U4, U5).
   ORDERING, against the numbering: the corpus half **leads**
   the parser rather than trailing it — authored against
   deliverable 1's rewritten spec so deliverable 2 has an
   executable acceptance test from its first line, staged
   beside the current fixtures and moved into place when the
   parser lands. That is deliverable 1's own argument one level
   down. The schema half, by contrast, cannot lag the parser at
   all: the corpus test runs every fixture against both, so the
   schema lands in deliverable 2's commit.
7. The remaining specs realigned as normative — **delivered**, by
   dividing the job rather than restating one format in four
   documents: blueprint-model.md (deliverable 1) is the model,
   machine-blueprint.md the guide, its reference the per-field
   detail, media-spec.md acquisition and the cache, the cookbook
   recipes. The documents realigned:
   machine-blueprint.md + field reference + cookbook,
   media-spec.md (the location grammar, the readings, and
   parent/children containment replacing the source/archive
   sections),
   instance-model.md, INTERFACES.md (its blueprint entry, its
   supporting-contracts list, and its specification-homes table
   all still name the retired four-component shape), and the
   AGENTS / ROADMAP home-layout descriptions — AGENTS' module
   paragraph too, which documents `document.py`'s
   `machines`/`media`/`sources`/`archives` as current. (P8 and
   P9 — a governing document left describing a retired shape is
   what the next change gets checked against; INTERFACES.md is
   an output here, never the premise D22 was triaged on.)
8. The codex and `planning/examples/` re-authored to the revised
   format — explicit `type` on every spec (the good-code
   doctrine: the format doesn't enforce it, the shipped corpus
   models it). **The rename half is delivered** (D21, the
   launching-point doctrine): the codex entries are now generic
   `freedos` / `openbsd`, their media and scripts follow, and the
   version lives inside each file as the location and hash. Only
   the re-authoring half remains, and it rides the format core;
   the FreeDOS install stays green end to end. (U1 — the codex is
   the one-command install's supply; U5 — the seeded copy is
   where customization starts, so what it models is what users
   start from; D21 for the naming.)

Done when: the FreeDOS install script runs from a clean home
against a machine created from a revised-format `.rlqb` (inline
anonymous blank hdd, empty cdrom, the LiveCD reached through its
zip); `destroy-machine` + `create-machine` regenerates from the
blueprint alone; `prune-media` after the install leaves exactly
the attachment closure (the extracted ISO stays, the zip husk
goes); and the one blueprint schema validates the reworked
conformance corpus.

### Milestone 8 — Script properties

All of [planning/design/script-properties.md](design/script-properties.md)
— the sources script-declared properties bind through. Small and
independently useful.

Demanded by **U5** — customization is what properties are for,
and this milestone is where the author's run-specific data
(owner names, login names, product keys) stops being embedded in
scripts; scheduling here is U5's acceptance, and delivery is
what returns it to the current list. It is likewise **P13**'s
acceptance (property sources — the layered chain, custody and
provenance over a frozen order), P13 joining the standing list
when this lands. Also serving **U4** twice — the
project-committed properties file a `--properties` run reads,
which is "the repository defines everything except what it must
not contain", and the `RELIQUARY_PROPERTY_*` injection path a CI
harness uses without provisioning a home — with **P4** (that
same hermetic file is the artifact-residency split applied to
values), **P6** and **P7** (the twins, and the stdin secret path
that exists precisely so the CLI stays a complete binding), and
**P12** (the file lives in the home; credentials scope by its
absolute path).

Deliverables:

1. `user.properties` as a flat user-owned line-based
   `key = value` file (dotted names; `@secret` markers), with
   name validation, comment-preserving surgical edits, and
   atomic writes.
2. `rlq get-property` / `set-property` / `unset-property` /
   `list-properties`: secret values held
   only in the host's protected credential store (scoped by
   properties-file path
   and property name), set via no-echo prompt on a tty and from
   stdin otherwise, never revealed by
   list/get; kind changes require `unset-property` first.
3. The fail-safe update order (store credential before marker,
   remove marker before credential), with orphaned-credential
   reporting and cleanup guidance — never a plaintext fallback.
4. The layered property sources: repeatable `--property`
   (refusing secret-bound keys), `RELIQUARY_PROPERTY_*` with the
   mangling rule and fail-closed collision preflight,
   `--properties <path>` selecting the maintained/consulted
   file in place of the home's (credentials scoped by file path),
   the blueprint `parameters` source (direct value or redirect,
   read at invocation), and the once-per-key interactive ask —
   the full flattened order: flag > parameter > env > file >
   derivation > ask.
5. The declared derivation rank (DECISIONS.md, 2026-07-23):
   repeatable `default=` candidates in the reference grammar —
   literals, `${key}` cross-references with static cycle
   detection, the `rlq.*` system facts (`rlq.host.username`
   login-normalized, `rlq.host.full-name`, the `rlq.env.<NAME>`
   family) — first-answerable-wins, empty facts unanswerable,
   dead literal candidates and any secret involvement static
   errors, and the supplying candidate named by `check-script`
   and transcripts.
6. `${key}` location references (grammar landed at milestone
   7) binding through the same source order at `create` /
   `apply` — the resolved location recorded in the state, never
   adopted at `start`; a resolved value that is itself a
   reference fails closed (no chaining); noninteractive misses
   fail closed naming the media and the key.

Done when: ordinary and secret properties round-trip through the
CLI with no secret material ever in the file, interrupting an
update cannot produce a plaintext value or a marker whose
credential was reported bound but is absent, a
derivation-backed key binds without an ask, naming its winning
candidate as the supplying source, and a media whose `location`
is a `${key}` reference materializes through the same order
with its resolved location recorded in the state.

### Milestone 9 — Run records and asynchronous runs

The implementation of "Asynchronous runs" above — the run-events
stream and everything that renders it — completing the feedback
split (PRINCIPLES.md P5) for the DOS-on-QEMU vertical.

Deliverables:

1. The normative `run-events.jsonl` stream, written live (append
   and flush per event, first preflight event to terminal event),
   and the `runs/<n>/` record layout with machine-scoped
   monotonic run numbers (the superseded `<timestamp>-<run_id>/`
   layout dies); `transcript.txt` as a pure renderer of the
   stream; the crashed-run rule.
2. The `--progress (auto | pretty | plain | jsonl)` renderers on
   the stream-bearing commands (`run-script`, `run tail`,
   `fetch-media`), the output discipline and stability contract
   ("The CLI" above) implemented across every command, and the
   beautiful, timely, informative human rendering the feedback
   split demands.
3. `run-script --detach` (foreground preflight, owned-child
   runner, writer identity), and the `run` family — `run status`
   / `run tail` / `run wait` / `run cancel [--stop-machine]` /
   `run delete` — with `list-runs`.
4. Interaction runs: `begin-run` / `end-run`, every
   machine-targeting command appending while a run is open, one
   open run per machine.
5. API twins under parity: `start_script()` and the pull-only
   run handle, `attach_run()`, `delete_run()`, `begin_run` /
   `end_run`, `start_fetch()` and the fetch handle; the error
   taxonomy (`ReliquaryError`; `StaticError` 2 / `PreflightError`
   3 / `RunFailure` 4 / `RunCancelled` 5).

Done when: a detached FreeDOS install is followed from a second
terminal in pretty and jsonl renderings of the same stream; a
cancel ends the run at an event boundary and leaves the machine
as-is; an interaction-run bracket records a primitive-driven
session; and a failure report names the route and revisits, the
expired clock and its source scope, the nearest miss, the
screenshot, and the suggested next command.

### The backend adapter seam (backlog)

> **Dropped from the numbered arc to the backlog** (owner,
> 2026-07-23): the former Milestone 10, not yet scheduled — the
> multi-backend pillar has no in-force use case demanding it.
> Its demand is the U7 draft
> ([planning/USE-CASE-PROPOSALS.md](USE-CASE-PROPOSALS.md),
> "materialize on the hypervisor the host provides"); accepting
> U7 is what schedules this work back onto the arc, the citing
> item the record. The design is settled and stands as written.

Extract the adapter API from the now-complete QEMU implementation
— the only adapter with a full control plane set — so the seam is
defined by working code, not speculation. The seam's doctrine is
pre-settled in
[planning/design/backend-adapter.md](design/backend-adapter.md)
(layering, seam inventory, ownership and capability doctrines,
extraction map); this milestone defines the signatures and records
them there.

Decide first:

- The backend priority order for default assignment when a
  blueprint names no backend (proposed: QEMU, VirtualBox, VMware
  Workstation, Hyper-V — best scriptability first).

Deliverables:

1. The adapter API: lifecycle, media attachment, input, screen
   access, and control plane endpoints, with honest per-backend
   capability reporting feeding the existing capability checks.
2. Backend autodiscovery (binaries on PATH and conventional
   locations, the Hyper-V service/module) establishing
   availability only.
3. Real default assignment from the prioritized availability
   list, recorded permanently into machine state; a declared
   `backend` pins the choice and fails closed if unavailable or
   incapable.
4. Stub adapters for VirtualBox, VMware Workstation, and Hyper-V
   raising `NotImplementedError`, mirroring platform handling.
5. Generalized ownership verification: no adapter sends a control
   command to a hypervisor object that doesn't match the
   machine's recorded `backend-id`.

Done when: all QEMU interaction flows through the adapter API and
the FreeDOS install script passes unchanged.

### Second backend: VirtualBox (backlog)

> **Dropped from the numbered arc to the backlog** (owner,
> 2026-07-23): the former Milestone 11, not yet scheduled on the
> same ground as the seam extraction above — U7 is its demand
> too, and it follows that extraction whenever the pair returns.

The first non-QEMU adapter end to end, proving the adapter API
against a genuinely different hypervisor. VirtualBox is the
candidate: `VBoxManage` covers lifecycle, keyboard scancodes,
screenshots, and serial redirection — the closest match to the
control plane set scripts already rely on.

Deliverables:

1. Lifecycle through `VBoxManage`, with machine files kept inside
   `cache/machines/<id>/` and VDI/differencing materialization
   of the drive triad.
2. The agentless display control plane: `controlvm
   keyboardputscancode` input and `screenshotpng` capture, with
   pixel-level text recognition for fixed-font text modes behind
   the same control plane interface.
3. VirtualBox in autodiscovery and the priority list;
   `recreate-machine`
   as the sanctioned backend move, drives regenerating in native
   formats.

Done when: the FreeDOS install script runs unmodified on both
backends from the same blueprint (minus a pinned backend field).

### Guest agent communication (backlog)

> **Dropped from the numbered arc to the backlog** (owner,
> 2026-07-23): the former Milestone 12 — numbered 13 until the
> same-day renumber that followed machine mobility's demotion —
> not yet scheduled. No use case demands it: U3's first-class
> demands (granular results, selective re-run) are met by
> milestones 8–9, and the guest-agent plane is that case's
> stated *preference*, not its requirement — its loop runs
> agentlessly on QEMU/DOS today. P3 governs how a native agent
> is consumed if this lands; it does not demand that it land.

Native guest agents as control planes, per
[planning/design/guest-communication.md](design/guest-communication.md):
Reliquary consumes the agents guests already have
— QGA first — and never builds its own (PRINCIPLES.md
P3, the control-plane arc). This milestone must not weaken the
permanent agentless DOS path; guests without a native agent
(DOS-era systems included) remain agentless, and where a guest
holds both planes the same suites validate agentless and
guest-agent control planes with equivalent results.

Decide first:

- The exact initial `guest-exec` subset, including argument and
  environment support, capture modes, output limits, and
  timeouts.
- Which bounded `guest-file-*` operations follow execution,
  including file consistency and atomic replacement semantics.
- Whether a separate plain serial-console control plane earns
  its keep alongside the native guest agents and the agentless
  planes.

Deliverables:

1. The host QGA client module: framing, `guest-sync-delimited`,
   `guest-ping`/`guest-info`, `guest-exec`/`guest-exec-status` —
   depending on QEMU's published guest-agent protocol, never on
   one particular guest implementation.
2. The extended `GuestExec` interface: request and result types
   covering deadlines, completion, output, and exit status,
   without exposing transport objects.
3. The configured readiness waterfall with conservative fallback:
   selection before first dispatch only, ambiguous failures never
   retried on another control plane.

Done when: a guest command runs through QGA on QEMU with
truthful capability reporting, and the agentless suite still
passes byte-for-byte.

### The GUI era: VNC, GUI scripting, and the last backends (backlog)

> **Dropped from the numbered arc to the backlog** (owner,
> 2026-07-23): the former Milestone 13, not yet scheduled —
> sequenced alongside the Horizon items below when its turn comes.

The arc's endpoint: GUI installer automation, carried by the
VNC/RFB control plane where backends provide it — QEMU natively,
VirtualBox with the extension pack, VMware Workstation — and the
two remaining adapters: VMware Workstation, then Hyper-V,
deliberately last. Hyper-V has no VNC (a capability failure,
never an emulation), so it is the proof that GUI automation
rides capabilities, not one wire.

Decide first:

- The GUI asset spec: the `.rlql` JSON schema, the similarity
  metric, and landmark-block placement within a script (the
  asset shape itself is settled —
  [planning/design/landmarks.md](design/landmarks.md)).
- Pointer input end to end: the machine-blueprint
  pointing-device field, the control-plane input capability, and
  the script verbs — match-and-click with the click point in the
  asset; click owns its search as an observation-bearing action
  and needs its timing-matrix row. The input seam follows the
  two-layer event model: three portable primitives — pointer
  move (x, y), button press/release, key press/release — with
  clicks, drags, chords, and paced typing composed above them,
  and event pacing owned by the control plane. The primitives
  are exactly RFB's PointerEvent/KeyEvent, so the VNC control
  plane implements them with no translation, and
  QMP/VBoxManage/WMI input paths reduce to the same three.
  Synchronization concepts to adopt with them: act-then-confirm
  (an input step optionally asserting the screen changed) and
  screen-stillness waits. Also open: a host-side
  landmark-cropping convenience (a CLI subcommand, never a
  service). Era note: DOS/9x-era setup GUIs are fixed-mode,
  fixed-font, animation-free — asset churn should be far below
  os-autoinst needle churn — and NT-era setup is largely keyboard-drivable, so
  keyboard-first remains the preferred path where it works.
  A future os-autoinst bridge belongs as an external-runner
  adapter or export target — generate an os-autoinst test
  distribution and invoke isotovideo out of process — not as
  Reliquary's native machine engine.
  Throughout, os-autoinst is a **concept reference only** — its
  designs are studied and reimplemented, never its code (see
  AGENTS.md prior art for the licensing boundary).
- Blueprint device growth: firmware/boot semantics (BIOS vs
  UEFI) for post-DOS platforms, and when network, display
  adapter, audio, and USB become first-class blueprint fields
  (each following the drives pattern: agnostic vocabulary,
  capability-checked per backend); per-platform controller
  defaults beyond `ide`; whether slot ranges widen for
  multi-device controllers (additive change); and how Hyper-V
  generations surface (a backend setting vs. inferred from
  declared capabilities).
- The Hyper-V agentless screen strategy: whether WMI
  thumbnail/keyboard automation is good enough for installer
  scripting, or Hyper-V machines require the serial/agent
  control planes from day one.

Deliverables:

1. The VNC control plane: per-backend endpoint configuration
   contributed to launch config, endpoint artifacts under the
   machine cache, a readiness probe, and an RFB client —
   framebuffer capture, key events, pointer events — behind the
   same input and screen capabilities as agentless display,
   reusing the pixel-level text recognition built for the
   VirtualBox display plane ("Second backend: VirtualBox"
   above).
   `control-planes: ["vnc"]` honored end to end, with a
   capability error naming Hyper-V where it cannot exist.
2. The three portable input primitives exposed at the
   control-plane seam, with pacing control-plane-owned.
3. Landmarks implemented per
   [planning/design/landmarks.md](design/landmarks.md): the `.rlql`
   catalog form, `@landmark`
   matching with fuzzy/ignore modifier regions, the cursor
   normalization contract, and the match-and-click verbs
   composed on the primitives.
4. Win9x/WinNT platform workflows: GUI installer scripting for
   the setup GUIs text scraping cannot reach, keyboard-first
   where NT-era setup allows it.
5. The VMware Workstation adapter.
6. The Hyper-V adapter, last, on its decided screen strategy.

Done when: the FreeDOS install script runs unmodified on QEMU
with the VNC control plane selected in place of agentless
display, pixel-recognition text observation matching the
VGA-scraping results on the same screens; and a GUI-era install
script drives a setup end to end through landmarks on QEMU over
VNC and on Hyper-V through its decided screen strategy.

### Horizon (sequenced later, not yet scheduled)

- The U6 authoring recorder
  ([planning/design/recorder.md](design/recorder.md)): the
  Reliquary-owned console viewer, text-mode
  recording, run-to-point / breakpoint / human takeover,
  round-trip fragments, and the `record` command family (work
  items in planning/TASKS.md).
- Machine mobility: clone, export, import — the former
  milestone 12 (the number guest agents inherited in the
  same-day renumber), moved here 2026-07-23 for lack of
  use-case
  backing: clone has no use case at all, export's stands only
  as the U8 draft, and import's U2 loses its scheduled
  delivery with this move. Scheduling it back onto the
  numbered arc is the acceptance of those use cases. The
  designs stay settled ("The CLI" above; owner, 2026-07-22):
  `export-drive` / `export-machine` with the decoupled
  exporter vocabulary, `import-vm` with its consent points,
  `clone-machine` as the machine snapshot; the `import-vm`
  scope round (NIC/device translation, untranslatable config,
  named-snapshot targets) remains its decide-first when it
  returns. The durable-artifact exits become meaningful once
  two backends exist — sequence at or after the second
  backend.
- **Host portability: Linux and macOS** (added 2026-07-23, owner).
  Windows is the delivered host — the only one developed on,
  tested on, and claimed in the packaging classifiers (AGENTS.md
  "Dependencies and style"). Host code is written portably and
  the other paths exist, but unexercised is unclaimed under P11.
  Widening is gated on three jobs, each substantial and none of
  them a by-product of ordinary work:
  1. **Secret storage per host** — the credential-store capability
     against a Secret Service provider on Linux and Keychain on
     macOS. The `keyring` seam
     (planning/design/script-properties.md, "Secret storage") is
     built for exactly this, so the code is likely already right;
     what is missing is *evidence*, and the no-plaintext-fallback
     rule means a wrong guess fails a user's run outright.
  2. **Backend verification per host** — QEMU discovery, process
     ownership, paths, and the agentless display plane proven on
     each host, not assumed from the Windows implementation.
  3. **A place to run them** — CI or real hardware. Every claim
     above rests on a suite actually executing there; U18 (drafted)
     is the case for reaching such a host from this one, which
     would make Reliquary its own answer.
  Demand is uncited today: no use case asks to *run Reliquary on*
  another host — U18 asks to reach another OS as a guest, which is
  a different axis. Sequencing it is the acceptance of whatever
  case does.
- `fork-blueprint` (a fire-and-forget authoring convenience;
  `new-blueprint` scaffolding lands in milestone 6) —
  currently unjustified: no use case demands it, and
  `seed-blueprint` already serves the seed-and-customize seam.
- Bounded `guest-file-*` operations through a native guest
  agent — distinct verbs, never bundled into a console
  abstraction.
- In-band file operations against a stopped machine's drives —
  the deferred half of the dropped run-collection model (owner,
  2026-07-22). Rough shape, its own design round before it
  lands: the CLI/API triple `list-files` / `get-files` /
  `put-files` (twins `list_files` / `get_files` / `put_files`),
  addressing `<drive-key>:<path>`; `size`/`base` images reached
  through the adapter's at-rest filesystem access, `hostdir`
  directories directly; capability-honest per call — a drive
  whose filesystem the adapter cannot read fails by name;
  `media` drives excluded; directories recursive; no record
  custody — files land where the caller says (details such as
  `get-files`' destination default are that round's to settle).
  Value concentrates where out-of-band access thins — non-QEMU
  backends (no `hostdir`) and non-FAT guest filesystems — so
  sequence at or soon after the second backend (backlog).
- Media commands beyond `fetch-media` (verify, remove) —
  currently unjustified: no use case demands them; `verify`
  would stand on the U13 draft if accepted.
- A `pytest-reliquary` plugin (per AGENTS.md prior art) —
  currently unjustified: adjacent to the U14/U15 drafts at
  best, and test-framework semantics belong to consumers (the
  doctrine boundary).

## Design principles

The project-wide governing principles are itemized as
P-numbers in root [PRINCIPLES.md](../PRINCIPLES.md); the
list below carries the roadmap-scoped ones and remains
normative prose for what it states.

- **Machines are ephemeral.** A machine exists to run its scripted
  task; disk images are the durable artifact. Prefer designs that
  make machines cheap to recreate over designs that make them
  precious — no feature should exist solely to nurse a long-lived
  machine.
- **One script, one target.** Each OS version and edition gets one
  install script. Immutable text, media, and secret properties supply
  that target's run-specific data from explicit values, blueprint
  parameters, user properties, or
  prompting; they do not select branches or turn a script into a
  flag-driven mega-script.
- **Installation media is input, disk images are output.** Install
  scripts consume vendor media and produce bootable machines. They
  are not runtime configuration generators.
- **Backends are adapters, never leaky defaults.** No feature may
  work only on one backend without the capability being declared;
  scripts and platform workflows target capabilities, not
  hypervisors.
- **Nothing is inferred from guests.** Platform and backend come
  from the machine blueprint. Probes choose among configured control planes;
  they never guess what OS is inside.
- **Dependencies must pull their weight** (per AGENTS.md).

## Guest communication design

The control-plane design — the carrier / protocol /
guest-integration vocabulary, the control plane families
(agentless display, VNC, serial console, native guest agents),
the consume-native-agents-only doctrine, the `GuestExec`
capability seam, and the readiness-waterfall configuration and
lifecycle rules — is consolidated in
[planning/design/guest-communication.md](design/guest-communication.md).
The `GuestExec` protocol, the isolated agentless adapter, and
its use by the DOS workflow are implemented; the native-agent
control planes and the VNC plane are both backlog work ("Guest
agent communication" and the GUI era above), unscheduled since
2026-07-23. Agentless DOS operation remains the permanent base
no milestone may weaken.

## Roadmap constraints

No backward compatibility before 1.0 (see AGENTS.md): no format
versioning or migration, no API aliasing, no compatibility shims.
Every milestone may reshape interfaces freely and completely until
a GA 1.0 release exists — beta included, where an occasional
cushion may be granted when warranted but none is promised.

Agentless DOS operation on QEMU is the permanent base described in
AGENTS.md; no milestone may weaken it.

The declared-media convention (drives named by medium, slot, and
format) carries over into machine blueprints and cached
materializations. New
media kinds, controllers, and USB devices must extend the same
convention — a new medium name — not appear as opaque raw backend
arguments.

The bootstrap direction is important: agentless operation is how
a machine reaches the point where a guest agent exists inside it
— the OS, and with it the OS's own agent package, is installed
through the agentless workflow (PRINCIPLES.md P3, the
control-plane arc). Where a guest holds both planes, the same
suites should validate agentless and guest-agent control planes
with equivalent results.

## Decisions still needed

Milestone-gating decisions sit at the head of the milestone that
needs them — the "Decide first" blocks above. What remains here
is not gating:

- **Cross-script reuse**: whether repeated behavior eventually
  justifies a constrained include mechanism. There is deliberately
  no handler-splicing macro in the initial language; real scripts
  must establish the need and a design that preserves local control
  flow and transcript provenance. A named user desire is now on
  record (owner, 2026-07-21, the bundling wrinkle): complex
  scripts split into multiple interacting files, like programming
  source files. Asset *factoring* — several scripts, catalog
  landmarks, and media definitions referencing each other through
  one asset root — is already served by authored-asset
  resolution; what stays open is behavior reuse, and any future
  include must preserve the static graph (G3), the
  non-computational surface (G2), and transcript provenance.
- **Blueprint computational constructs**: which bounded
  declarative constructs the blueprint format eventually grows.
  Computational expansion is an anticipated growth area, and its
  governing rule is decided (planning/DECISIONS.md, 2026-07-23):
  a construct that enriches values may land as plain data
  expanded by Reliquary — the parked extraction short-circuit
  and a variant/matrix expansion are the candidates on record —
  while general computation never enters the JSON tree. It would
  arrive only as a layer producing plain blueprints: generation
  above via the embedding API, or a JSON-superset evaluation
  layer (Jsonnet the leading candidate — JSONC is already valid
  Jsonnet). In-tree function objects and string templating are
  permanently rejected. What stays open is only which constructs,
  and when one earns its keep.
- **Per-drive backend settings**: whether they are ever needed
  beyond the top-level `backend-settings` scope.
- **Promoting runtime changes**: whether a convenience command
  copies a state-side runtime change (e.g. attached media) back
  into the blueprint, or users always edit the blueprint by hand.
- **Machine cache cleaning**: whether a `clean machines` command
  reclaims cached materializations of stopped machines wholesale
  (they regenerate like everything else under `cache/`), or
  whether `recreate-machine`/`destroy-machine` per machine is
  enough.
- **Friendly machine aliases**: machine identity is already
  human-readable (`<blueprint>-<n>`); still open is whether
  listings and selectors additionally offer docker-style generated
  word aliases, or whether numbered ids plus blueprint selection
  make them unnecessary.

Deferred to 1.0:

- **Format versioning**: pre-1.0, user documents carry no
  version field and no `$schema` field (settled, owner 2026-07-21;
  the horizon moved from beta to 1.0 with the compatibility rule,
  D25, on the same argument:
  a pinned schema reference is a version field in disguise, and a
  pre-1.0 document has no format vintage — the only schema that
  matters is the installed Reliquary's, which editors bind by file
  association; an embedded pin would go stale in seeded files
  under never-overwrite and let the editor pass what Reliquary
  rejects). When compatibility guarantees arrive — no earlier than
  1.0 — the leading candidate spelling for the version field is
  `$schema` as a versioned URL: one field declaring the document's
  format version and binding editors to the matching published
  schema.
