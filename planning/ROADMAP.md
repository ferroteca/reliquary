<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Roadmap

## Vision

reliquary automates guest operating systems — installing them from
vendor media, booting them, and scripting them — across multiple
virtualization backends, driven by named machine blueprints and a
reliquary scripting language.

reliquary manages **ephemeral machines**. A reliquary machine is a
disposable rig: created to run a scripted install or an automated
task, then recreated or deleted. The machine itself is never the
product. Often there is no durable artifact at all — the whole
point was to run some tests and observe the results. When there
is interest in something more durable, it is **exported** —
either a media image (a disk image taken out of the machine) or
an entire machine (handed to a hypervisor built for long-lived
machines). reliquary is not a VM manager for machines you keep;
every design choice may assume machines are cheap to destroy and
rebuild.

[planning/INTERFACES.md](INTERFACES.md) names the interfaces through which
the world drives reliquary and the vetting rule every
interface-changing decision must follow; the primary use cases
they serve live in [planning/USE-CASES.md](USE-CASES.md).

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
   machine: dos, win9x, winnt, and later others. Platform workflows
   own OS meaning: provisioning, readiness, command syntax,
   completion, and result collection.

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
  control, or reliquary's own agent over serial), VNC where the
  extension pack provides it.
- **VMware Workstation** — driven through `vmrun`/`vmcli` and the
  `.vmx` file. Control planes: agentless display (limited; screenshot via
  `vmrun captureScreen`), serial (named pipe/file), guest agent
  (VMware Tools guest operations, or reliquary's own agent over
  serial), VNC (`RemoteDisplay.vnc.enabled`).
- **Hyper-V** — driven through the PowerShell `Hyper-V` module / WMI
  (`Msvm_*` classes). Control planes: agentless display (WMI keyboard
  injection + thumbnail/screen capture), serial (named pipe), guest
  agent (PowerShell Direct / integration services, or reliquary's
  own agent over serial). No VNC.

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
  `recreate`): reliquary walks its internal backend priority list
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
- **The serial-carried reliquary guest agent is backend-portable.**
  Every backend can expose an emulated UART, so the QGA-profile
  agent described below is the one guest-side investment that pays
  off on all four backends.

The adapter seam's design doctrine is consolidated in
[planning/design/backend-adapter.md](design/backend-adapter.md)
(owner, 2026-07-21): an internal engineering contract, deliberately
not a world-facing interface (the third-party-adapter watch is in
planning/TASKS.md); adapters own drive-image materialization in
their native formats; adapters provide carriers and control planes
compose them (one shared fixed-font recognizer serves text
readback where no native text carrier exists). The doctrine is
settled ahead; signatures land with the milestone-6 extraction,
defined by the working code.

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
├── reliquary-machine.json   the machine's state (reliquary-owned:
│                            id, blueprint reference, phase,
│                            resolved configuration)
├── drives/                  the machine's disk/floppy images
├── runs/                    append-only run records (transcripts,
│                            screenshots, outputs)
└── ...                      backend files and logs
```

Everything under `cache/machines/<id>/` is reliquary's and
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

The blueprint is reliquary's own backend-agnostic format — never a thin
veneer over one backend's configuration. Two documents, one owner
each: the **blueprint** (`<name>.rlqb`) is the machine
shape as the user defined it — authored by hand, by `init`, or by
`import`; reliquary reads it and — once authored — never writes
it. The **state**
(`cache/machines/<id>/reliquary-machine.json`) is the machine as
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
(`rlq run-script install --blueprint freedos-1.4-plain`) — and the
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
remains reliquary's own validator (fail-closed, name-the-problem
diagnostics); a shared valid/invalid fixture corpus, run against
both parser and schema at realignment, keeps the two aligned.
Documents carry no `$schema` field pre-beta — editors bind the
schemas by file association — with `$schema` as the leading
candidate spelling of the version field at beta ("Decisions
still needed"). The machine-state schema lands at milestone 3,
once the state format settles.

### Home layout

```text
<reliquary_home>/
├── blueprints/          machine blueprints, <name>.rlqb (above)
├── scripts/             reliquary automation scripts
├── landmarks/           landmark declarations and their variant
│                        renderings, <name>.rlql + <name>.<n>.png
│                        (see "Landmarks")
├── user.properties      personal user properties (line-based
│                        key = value; ordinary values and @secret
│                        markers for host-stored secrets)
├── media/               shared media definitions (mirror URLs, archive
│                        and payload SHA-256; one definition per
│                        source archive can itemize several named
│                        files) — see planning/design/media-spec.md
└── cache/               reliquary's regenerable files
    ├── downloads/       cached source archives (redownloadable;
    │                    reclaimed by `clean downloads`)
    ├── media/           the named payload files machines mount,
    │                    fetched/extracted/verified on demand
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

reliquary ships the codex — built-in blueprints, media
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
definitions: a codex definition may carry a `url` only
alongside an explicit assertion that the media's licensing
permits redistribution, and no change adding a URL is accepted
without it. The codex deliberately covers non-redistributable
operating systems too: those blueprints ship media definitions
with hashes but no URLs, and materialization fast-fails naming
the missing media until the user supplies it by adding their own
`url` or `local-path` (the cache is never hand-fed), with the
hash verifying it is the exact build the scripts target. For
open source systems the lazy path is:

```powershell
rlq run-script install --blueprint freedos-1.4-plain
```

## Authored-asset resolution

Where reliquary looks for authored assets — blueprints, media
definitions, and scripts — is an invocation-level setting: the
mechanism behind the artifact-residency split (planning/USE-CASES.md).

- Every invocation names its **asset root**; unspecified, it
  defaults to the **current directory**. Assets are identified by
  extension, not location: `.rlqb` is a machine blueprint,
  `.rlqm` a media definition, `.rlqs` a script, `.rlql` a
  landmark declaration (its `<name>.<n>.png` variant renderings
  attach by stem adjacency, not discovery — see "Landmarks").
  Discovery walks the root for the four extensions, so a project
  lays out its files however it likes — `blueprints/`, `media/`,
  `scripts/`, and `landmarks/` subdirectories are optional
  organizational dressing, the home's own convention included
  (U3, U4). Within one root, two files of one kind with the same
  stem are an error; the home's `cache/` is never scanned.
- Resolution falls back to the reliquary home for assets the root
  does not provide. Home assets are a convenience for human CLI
  interaction — one shared place for the blueprints, media
  definitions, and scripts a person reuses across
  human-interaction scenarios (U1, U5). An explicit option
  disables the fallback entirely, and automation runs with it
  off: resolution is then strictly
  project-scoped, and nothing outside source control — neither
  home assets nor the codex seeded behind them — can
  reach the run.
- The home remains reliquary's own ground regardless of asset
  root: machines materialize into the home cache, downloads and
  payloads use the home caches, and the personal
  user-properties file stays home-side (a license key never
  enters the repo —
  U5).
- `--assets <dir>` names the root and `--assets-only` disables
  the home fallback — global flags, mirrored by the API
  parameters `assets=` / `assets_only=` under parity.

Three rules complete the model. **The root shadows the home**:
when both define a name, the asset root wins — identical media
descriptors coalesce, duplicates within one root remain errors,
and run records name which root supplied each asset. **Machines
record their blueprint's source**: the state carries the resolved
blueprint file's absolute path, and `--blueprint <name>`
selection matches only machines whose recorded source equals the
invocation's own resolution of that name, so same-named
blueprints in different projects never select — and `apply` never
adopts — each other's machines. **reliquary reads by
extension and writes by convention**: embedded media blocks
install as `<label>.rlqm` — into the home's `media/` for a
home-resolved script, beside the script file itself for a
source-resident one — a new source file its author commits;
installation is idempotent by identity, so a committed definition
means no further writes and a clean CI tree. U6's recorder
likewise emits its drafts into the asset root the session ran
with.

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
the first. Any other language that wants reliquary automation but
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
command (`rlq run-script install --blueprint freedos-1.4-plain`)
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
`import_vm`, `seed_blueprint` / `seed_media` / `seed_script`,
`new_blueprint`, and the property family `get_property` /
`set_property` / `unset_property` / `list_properties` — taking
the CLI's selectors (`resolve_machine()` the shared seam) and the
mirrored globals (`home=` / `assets=` / `assets_only=`),
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
only inside script text). The file-exchange pair joins them on
the durable-state side (owner, 2026-07-22):
`stage-files <path>... --to <drive:path>` and
`collect-files <drive:path>... [--to <dir>]` (twins
`stage_files` / `collect_files`) are the in-band copies into and
out of a stopped machine's drives at rest —
`size`/`base`/`hostdir` content only, paths contained within the
named point, directories recursive; `collect-files --to`
defaults to the open interaction run's `output/` and is required
with none open. In a script the same capability is the
`results` header with `stage`/`collect`
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
`--home`, `--assets <dir>` / `--assets-only` ("Authored-asset
resolution" above), and `--json` (below) are accepted by every
command, mirroring the API's shared keywords. There is no
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
on it. From beta the machine surfaces grow additively only —
new event kinds and new fields may appear in any release, an
existing field never changes type or meaning, and a removal or
rename is a breaking change — and consumers must ignore unknown
event kinds and unknown fields. Pre-beta there is no stability
promise; shapes track the specs and the CHANGELOG records
changes. The version-field spelling stays with the beta
format-versioning decision ("Decisions still needed").

```text
rlq list-blueprints
rlq list-machines [--blueprint <name>]
rlq list-scripts
rlq list-media
rlq list-runs [--blueprint <name> | --machine <id>]
rlq (search-blueprints | search-scripts | search-media) <term>...
    [--verbose]
rlq new-blueprint <name> [flags]
rlq (seed-blueprint | seed-media | seed-script) <name> [--only]
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
rlq stage-files <path>... --to <drive:path>
    (--blueprint <name> | --machine <id>)
rlq collect-files <drive:path>... [--to <dir>]
    (--blueprint <name> | --machine <id>)
rlq hmp <line> (--blueprint <name> | --machine <id>)
rlq check-script <label-or-name> [--blueprint <name> | --machine <id>]
    [--property <key>=<value>]... [--properties <path>]
rlq fetch-media <media_name> [--script <script_name>]
rlq list-properties [<prefix>]
rlq get-property <key>
rlq set-property <key> <value>
rlq set-property <key> --secret
rlq unset-property <key>
rlq clean-downloads
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
  Blueprints are authored documents. Media definitions are likewise
  user-owned, though a script can seed missing library
  definitions from its embedded blocks before its first run.
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

- `run-script` completes preflight, installs missing embedded media
  definitions, resolves its machine (creating one when `--blueprint`
  names a blueprint with no machine yet), and starts it if it is not
  already running before executing guest steps.
- `fetch-media` downloads, extracts, and hash-verifies a defined
  media
  item (see planning/design/media-spec.md). It is a convenience: machine
  operations resolving a `media` reference to a fetchable
  definition fetch implicitly. Source archives are cached under
  `cache/downloads/`, separate from the payloads in
  `cache/media/`. `--script` installs that script's embedded
  definitions before fetching, without executing guest steps.
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
- `clean-downloads` / `clean-media` reclaim the two caches:
  cached source archives, and payload files reliquary can fetch
  again. Nothing irreplaceable (definitions, `local-path` files,
  payloads without a download source) is cleanable.
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
  outside reliquary's purview.
  `export-drive <key> <destination>` takes one drive out as a
  standalone image — the drive's native format, or raw by
  destination extension (the adapters' raw interchange; other
  conversions declined as growth). `export-machine --to
  <exporter>` creates and registers a native VM with a
  management platform built for keeping machines: `--to` names
  an **exporter** — virtualbox, vmware, hyperv, libvirt, ... — a
  vocabulary of its own, probed on the host and deliberately
  decoupled from the backend list (libvirt is the QEMU
  ecosystem's answer; the reliquary-invented
  bare-image-plus-launch-config artifact is dead). The target is
  presented, never defaulted: a tty prompts listing the
  exporters available on this host, noninteractively it is an
  error, `to=` required under parity. The exporter builds the
  native VM from the machine's resolved blueprint shape
  (capability-checked like `create-machine`) with drive content
  through the adapters' raw interchange, and media payloads
  materialize as copies so the export stands alone. Ownership
  verification guarantees reliquary can never touch the exported
  VM afterward. Import mirrors the decoupling in vocabulary:
  `import-vm` reads a native VM source through an **importer**,
  no same-named backend required.
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
  reliquary-named with provenance recorded in the generated
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

reliquary gets its own scripting language for automating guests.
Scripts are stored in `<reliquary_home>/scripts` and invoked as
`rlq run-script <label>` against a machine selected with
`--machine <id>` or `--blueprint <name>`.

**The July 2026 surface redesign is decided and
[planning/design/script-spec.md](design/script-spec.md) is its source of
truth** (including the complete typed EBNF), with
`script-examples/design-install.rlqs` as the reference
script. Realigning the implementation — parser, runtime, shipped
scripts — with it is **absolute priority #1**; see the
realignment milestone below. Pre-beta, the superseded surface is
deleted, not bridged.

**Decided shape: a line-oriented, constrained DSL with one
grammatical form.** A script is a UTF-8 text file
(`scripts/<name>.rlqs`) in which every line is a *node*: a name,
positional arguments, `name=value` properties, and optionally a
brace block — with `#` comments and no commas or colons anywhere.
Spelling reveals role: `"..."` is guest-boundary text, `/.../` a
regex, `@name` a library reference, `$name` a run-supplied input,
bare words are keywords and script-internal names. Declarative
nodes (headers, `media`, `input`, `phase`) begin with a noun and
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
guest reboot has no reliquary verb or event: the script types the
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
entry. This protects reliquary's records, not guest logs, history, or
an explicitly requested screenshot. The complete planned contract is
in [planning/design/script-properties.md](design/script-properties.md).

Scripts may also embed ordinary media-definition JSON objects in
top-level, labeled `media <label> { ... }` blocks. After full
preflight but before machine resolution, running the script installs
each missing definition as `<label>.rlqm`; `fetch --script`
does the same without executing guest steps. Existing definitions are
never overwritten: wholly identical blocks are already installed,
while differing targets, item collisions, and partially overlapping
blocks fail with both locations named. New files use canonical JSON
and become ordinary user-owned library documents. Fetched and
extracted artifacts use the common caches.

Offline `stage`/`collect` require a stopped machine on every
control plane, reaching the script-declared results directory — a
drive key plus path (`results hdd0 "/results"`), the bounded
host reach into the guest's disks — through the adapter's
at-rest filesystem access, with collected files landing in the
run record's `output/` (owner, 2026-07-22); future live
transfers get distinct verbs rather
than backend-dependent semantics. `start` reconciles the authored
machine blueprint and `stop` is visibly a host hard power-off.
There is no `restart`: a hard power cycle is the explicit pair,
and a guest reboot remains guest input. Parsing, property binding,
whole-script capability preflight, and static control-flow checks
all finish before the first guest input. User documentation and
source of truth: [planning/design/script-spec.md](design/script-spec.md)
(the July 2026 redesign; the implementation still speaks the
superseded surface until the realignment milestone lands).

The primitive vocabulary already exists in today's CLI and Python
surface — it is the proven instruction set the language must cover:

- enter/type text and send keys;
- wait for normalized screen text (literal or regex), machine
  state, or a stable observation, with timeout/deadline bounds;
- select an entry in a cursor-key menu by visible feedback;
- take a screenshot;
- define embedded media, insert/eject it, and start/stop the
  machine;
- stage files to and collect files from the guest.

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
reliquary owns, and procedural at the seam with the guest.**

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
| media, inputs, embedded definitions | declarative | ours, and knowable |
| keystrokes and observations within a phase | procedural | the guest's installer dictates the order |
| which route the run takes | procedural choice over a declarative graph | the guest chooses at run time |

**Why not fully declarative.** OS installation has a mature
declarative form — Kickstart, preseed, AutoYaST, Windows
`unattend.xml` — in which the author states what the installed
system should be and the installer does the rest. Where those
exist they are strictly better, and reliquary should not compete
with them. It deliberately targets the guests where they do not
exist: DOS, Win9x, and other systems whose installers accept only
keystrokes. An answer file is also a form of guest cooperation,
which G1 forbids depending on. Procedural interaction at the guest
seam is therefore not a stylistic preference; it is the only thing
available.

**Why not fully procedural.** A plain imperative script — the
AutoHotkey or Expect shape — would be shorter to specify and would
need no phase concept at all. It is rejected because it forfeits
G3 and G4 together: a straight-line script with ad-hoc loops has
no statically knowable shape to analyze, and no named units to
report progress against. The declarative half is what makes a run
checkable before it starts and legible while it runs.

**The tensions this creates, which we accept.** These are real and
should not be papered over; several are already catalogued as
residual problems in `script-examples/`:

- `phase` is a declarative construct whose body is procedural. The
  hybrid is not hidden; it is the point.
- A sequential phase is procedural, a reactive phase is
  declarative, and both are spelled `phase`. The two are forbidden
  to mix rather than given a combined semantics — a prohibition,
  not a definition.
- The paradigm boundary shows in the handler keywords: `on` is a
  case in a branching `wait`, `always` a standing rule in a
  reactive phase — one shape, two named lifetimes
  (`script-examples/04`, resolved by the keyword split).
- Declarative timing scopes annotate procedural statements, so an
  observation's effective bound is not locally readable
  (`script-examples/03`).
- Procedural `insert`/`eject`/`set-boot` mutate declarative
  machine state that outlives the run (`script-examples/09`),
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

Landmarks are the image-match assets for GUI guests — the
`@landmark` matcher the growth rule already names, and the assets
U6's recorder captures. The 2026-07-21 owner round settled their
shape; the full asset spec (JSON schema, similarity metric) is
queued work, and "Decisions still needed" below carries what
remains open.

**One declaration, N renderings.** A landmark is a single
declaration owning its geometry — the region list and the named
spot set (click points), with pinned screen dimensions and mode —
plus one or more *variants*: alternative renderings of the same
screen (palette, font, or shading differences). Variants share
the declaration's dimensions, mode, regions, and spots by
construction, which makes the decided variant invariants
(identical spot sets, declared order) structural rather than
checked. A screen whose *layout* changed is a different landmark,
not a variant — keeping variants aligned with U6's "changed
screen for an unchanged step".

**Whole-screen match; regions are modifiers.** A bare landmark
matches the entire screen exactly (pixel-equal after decode
normalization). Declared regions soften or void areas: a `fuzzy`
region carries an explicit `similarity` percent literal (its unit
spelled, as durations spell theirs; no implicit default — G6),
and an `ignore` region is excluded outright. This chooses the
safe failure asymmetry: over-matching misses and times out
visibly (G4), where under-matching would fire on the wrong
screen. os-autoinst-style *selecting* regions that confine
matching to declared rectangles are deferred as additive growth
(G7). Failure reporting stays per-variant: the nearest miss names
the closest variant.

**Catalog form.** The declaration is `<name>.rlql`, a JSONC
authored document — the fourth authored extension beside
`.rlqb` / `.rlqm` / `.rlqs`, resolved under exactly the same
rules ("Authored-asset resolution" above: root discovery by
extension, root shadows home, `--assets-only`; a `landmarks/`
subdirectory is optional dressing). Variant renderings are plain
PNGs attached by stem-and-number adjacency — `<name>.<n>.png`
beside the declaration, ordered numerically — so a U6 asset
refresh is strictly file-creation, never file-rewrite, and
capture provenance lives in PNG text chunks, not sidecar files.
Landmark names share the collision-checked `@` pool with media
names.

**Embedded form — resolve in place.** A script may carry its
landmarks as `landmark <name> { ... }` blocks: the same JSON
schema as `.rlql` (no second schema, as with embedded media) plus
inline base64 variant data, so a workflow travels as one
self-contained source file (U1, U4). Embedded landmarks resolve
in place: nothing installs and no files sprout. Embedded *media*
installs so later machine and media commands can use the
definitions without the script in scope; a landmark has no
consumer outside its script, so the install step would only
defeat the single-file shape. Embedded landmarks are
script-scoped — sharing between scripts uses the catalog form —
and asset refresh writes `<name>.<n>.png` beside the script, file
variants ordering after embedded ones, so reliquary never
rewrites a script. Any duplicate landmark name visible to one
script — embedded against `.rlql`, or against a media name — is
an error naming both locations; landmarks never coalesce because
they never install. Where the blocks sit in a script (the
declarative header zone, or a trailing assets zone that keeps
bulk payloads out of the procedure's way — G4) is left to the
asset spec work.

**Cursor normalization.** Captures and matching always strip the
mouse cursor — a normalization, never an option:

- Every pointer verb ends by parking the cursor at a fixed
  per-platform park position; parking is never script surface.
  For guests that composite the cursor into the framebuffer
  (software cursors — nothing host-side can erase what the guest
  drew), parking *is* the stripping mechanism: the guest
  repaints, and every later capture is clean by construction.
- The park zone is permanently masked from matching — a built-in
  ignore region; a declared region overlapping it draws a
  preflight warning.
- Where the control plane can capture a cursor-free framebuffer
  (RFB cursor pseudo-encodings), that is used automatically.
- While recording, the human drives and cannot be parked — but
  reliquary is the console, so the cursor position at capture
  time is always known; proposed assets mask that neighborhood,
  flagged as a generated comment (U6).
- Diagnostics capture reality: explicit `screenshot` and failure
  screenshots never inject a park move — it could dismiss the
  hover state or menu that explains a failure. In script runs
  they are cursor-clean anyway, because every pointer action
  already ended parked.

## Script authoring by recording

The authoring recorder serves U6: a person performs the task once
in a console session reliquary supervises, and reliquary drafts
the script and captures the landmark assets that reproduce it.
Settled design:

**Recording requires reliquary to be the console.** Input typed
into a backend's own display window never passes through
reliquary and cannot be followed; recording happens in a
reliquary-owned viewer over the `vnc` control plane, where every
keystroke, click, and media swap is observable. The viewer is a
real component, and the recording prerequisite on every backend —
QEMU included.

**First capture drafts, the author tailors.** Input events
segment the session's timeline; the stable screen before each
input proposes the wait condition (a VGA text match in text mode,
a landmark in GUI mode), the input proposes the action, and
observed timing proposes generous timeouts. What the recorder
cannot know — which screen features are load-bearing, how long a
step may honestly take — it flags as generated comments in the
draft. Text-mode capture comes first and needs no new language
surface; GUI capture rides the landmark/click work, and a click's
position seeds its landmark's spot. The draft is ordinary script
text, self-contained by default — landmarks travel as embedded
resolve-in-place blocks ("Landmarks" above) — with factored
catalog files on request; written once and user-owned from then
on, like `import-vm` output.

**Round-trip composes with tailoring — playback is the
positioning mechanism.** Authored customization must survive
re-capture, so later sessions never regenerate or text-merge the
script. Instead, playback of the user's tailored script carries
the machine to the point of change — a breakpoint, or the exact
statement where the script fails against a changed guest — and
the person takes over the console, demonstrates, and hands back.
The recorder emits a *fragment* — new waits, actions, and assets
— anchored at the phase and statement of the user's own script.
Because the anchor comes from executing that script, not from
diffing it against a stored base, round-trip is robust to
arbitrary tailoring: no pristine draft is retained, no merge
happens. (openQA's interactive mode is the concept precedent —
concepts only, per AGENTS.md.)

**Two tracks, two write boundaries.** A changed screen for an
unchanged step is an *asset refresh*: a new landmark variant,
never touching the script — the numbered-adjacency variant shape
(`<name>.<n>.png` beside the declaration, or beside the script
for an embedded landmark; "Landmarks" above) makes refresh
file-creation, never file-rewrite. New or changed steps
are *step capture*: the fragment is emitted beside the script for
the author to splice in their editor; an explicit opt-in apply
may perform the surgical insertion at the anchor, touching no
other byte — a named exception in the family of installing an
embedded definition. Round-trip is append-shaped everywhere;
nothing reliquary wrote once is rewritten.

**Shared machinery.** Run-to-point, breakpoints, and human
takeover are runner features that also serve ordinary debugging —
"take over from here" is a natural suggested next command in a
failure report. Handover events (control passing between script
and human) join the run-events stream as event kinds, so a
capture session is one run record with mixed drivers. The
`record` command family lands on the CLI and the embedding API
together, under parity. Blueprints and media definitions are
untouched: a session runs on an ordinary machine, and media swaps
are already `insert`/`eject`.

## Asynchronous runs

A script run can be started without blocking and observed while
it goes — the consumer story for the feedback split (USE-CASES):
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
in USE-CASES (the artifact-residency split) and INTERFACES
(recorded outputs).

**Interaction runs — the opt-in bracket (owner, 2026-07-22).**
A primitive-driven loop earns the same evidence a script gets:
`begin-run` (twin `begin_run`, returning the new run number)
opens an ordinary run record whose driver is the caller; while
it is open, every machine-targeting command on that machine —
the guest-console family, the state operations, lifecycle —
appends the event kinds the execution model defines for the
same actions, and `end-run` closes the record with the neutral
`ended` terminal event (reliquary attaches no outcome to an
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
collected into the record's `output/`, and deliberately no
test-result vocabulary in reliquary (G2) — one iteration is
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
stream-bearing commands now; the general stdout/stderr
discipline and output-stability contract across every command
remains queued (TASKS).

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
same events under the same defaults, their full output contract
remaining with the general CLI discipline (TASKS). Honesty
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

**Absolute priority #1 is the script-surface realignment** (its
own milestone below): retargeting the implementation to the
redesigned script spec before any other milestone work proceeds.
**Within the larger arc, DOS under QEMU is the top priority, and
blueprints are the extremely high priority within it.**
Milestone 1 is a vertical slice: the north-star command working
end to end from a clean home. Milestones 2–5 then complete the
documented design — the media library, the instance model and
machine blueprint, the script properties, and the scripting
language, i.e. everything in `planning/` — for the DOS platform on
the QEMU backend alone. The script-surface realignment then
retargets the language implementation to the July 2026 redesign.
Only then does the design generalize: the adapter seam is
extracted from working code (6), proven by a second backend (7),
and extended with machine mobility (8), guest agents (9), and the
VNC control plane (10).

Each milestone is independently shippable: the tree builds, the
test suite passes, and the FreeDOS install keeps working end to
end on whichever surface that milestone provides. Within 2–5 the
order is dependency-driven — the media library before blueprints
fully exploit it, the machine model before scripts fully drive
it, the property sources before script declarations bind through
them.
Within a milestone the listed deliverables are ordered but may
land in separate commits.

### Milestone 1 — The north-star command

```powershell
rlq run-script install --blueprint freedos-1.4-plain
```

From a clean home, that one command must end with a fully
installed FreeDOS machine that can then be started and stopped
from the reliquary command line. Everything in this milestone is
the minimum vertical slice of the documented design needed to get
there — each piece grows to its full spec in milestones 2–5. The
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
   `builtins/` tree (zip-bundled when packaged), copy-out on
   first reference, the never-overwrite rule, and
   `freedos-1.4-plain` — blueprint, media definitions, and
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
   Exit: load a `freedos-1.4-livecd`-like JSON; reject bad
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
7. **Builtins seed (complete)** — `builtins/` tree + copy-out on first
   reference + never-overwrite (+ packaging zip path). Exit:
   `--blueprint freedos-1.4-plain` seeds home files once;
   second call leaves them alone. Out: `pull`, provenance
   columns, full index/`search`.
8. **`.rlqs` parse (FreeDOS shape; complete)** — header + state-machine +
   the verbs that example uses. Exit: parse the documented
   install script; useful parse errors. Out: linear-only path,
   `on`/reactive, `insert`/`stage`/`collect`, inputs/properties.
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
11. **Author `freedos-1.4-plain` (complete)** — blueprint + media
    definition (URL + license assertion) + install/verify
    scripts in `builtins/`. Exit: artifacts resolve and the
    install script matches the LiveCD flow. Out: other OS
    builtins.
12. **Verify path (complete)** — `script verify` boots the
    installed HDD through spike 13's model (blueprint boots
    `hdd0` then `cdrom0`; install script's final `eject` leaves
    a plain `start` booting the hard disk). Exit: north-star done
    criteria green. Out: full milestone-3 `apply` semantics.
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
    milestone 3), embedded media blocks, hot-swap polish beyond
    what the install needs. Runs before spike 12, which
    consumes it.

Done when: `rlq --blueprint freedos-1.4-plain script
install` runs unattended from a clean home to an installed
machine; `rlq --blueprint freedos-1.4-plain script verify`
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
   for embedded script blocks in milestone 5).
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
4. `rlq fetch <media_name>` and `reliquary clean
   downloads` / `clean media` (nothing irreplaceable —
   definitions, `local-path` files, sourceless payloads — is
   cleanable). `fetch --script` follows in milestone 5 with
   script parsing.
5. `list media` and `search media` over the built-in index and
   user definitions, with the `yes`/`seeded` provenance column;
   `pull media <name>`.

Done when: the FreeDOS media flows through a definition end to
end; a deliberately corrupted cached payload heals on next use
once its deletion is approved and is kept intact when it is not;
`clean` reclaims only restorable files; the install script passes
on the completed layer.

### Milestone 3 — The instance model and machine blueprints

The whole machine model beyond milestone 1's core —
[planning/design/instance-model.md](design/instance-model.md)
plus the [machine blueprint](design/machine-blueprint.md) with its
[field reference](design/machine-blueprint-reference.md) and
[cookbook](design/machine-blueprint-cookbook.md) — still scoped to
one backend. The `backend` field is parsed and validated in full,
but with QEMU the only implementation, assignment is trivial; the
adapter seam that makes it real is milestone 6. Capability checks
are real from the start, derived from what the QEMU
implementation can actually do.

Deliverables:

1. Blueprint validation per the full field reference: `platform`,
   `backend`, `memory`, `cpus`, `drives` (slot convention and
   aliases, per-drive `controller`, `media` references, `size`
   blanks, `base` with `difference`/`duplicate`, `enabled`),
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
5. The guest-console family (`type`, `enter`, `press`, `exec`,
   `select`, `wait`, `screen`, `screenshot`, `hmp`) and the state
   ops (`insert-media`, `eject-media`, `set-boot-order`) take the
   same `--machine`/`--blueprint` selection and resolve ownership
   through the machine state.
6. Published JSON Schemas for the document types: publication
   mechanics and the shared valid/invalid fixture corpus (run
   against both parser and schema) for the authored blueprint and
   media-definition schemas
   (`planning/design/*.schema.json` — prose specs normative, the
   parser the validator), plus the machine-state schema, authored
   here once the state format settles.
7. `planning/examples/` updated to the implemented shapes
   (`planning/examples/blueprints/`, an explicit `create --blueprint` step in its
   README) — or the docs corrected where implementation proves
   the planned format wrong.

Done when: the FreeDOS install script runs against a machine
created from the example blueprint in a clean home;
`destroy-machine` + `create-machine` regenerates the
materialization from blueprint and media
alone; a process killed mid-operation is detected and recovered
per the instance model; blueprint edits round-trip through
`apply-blueprint` with drive-regenerating changes failing closed.

### Milestone 4 — Script properties

All of [planning/design/script-properties.md](design/script-properties.md),
landed ahead of the scripting language because script-declared
properties bind
through its sources. Small and independently useful.

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
   and `--properties <path>` selecting the maintained/consulted
   file in place of the home's (credentials scoped by file path).

Done when: ordinary and secret properties round-trip through the
CLI with no secret material ever in the file, and interrupting an
update cannot produce a plaintext value or a marker whose
credential was reported bound but is absent.

### Milestone 5 — The scripting language (complete, on the superseded surface)

The remainder of the script spec beyond milestone 1's core,
completing the then-documented design for DOS on QEMU. The
deliverables below record what was built; the July 2026 spec
redesign supersedes their syntax, and the realignment milestone
that follows retargets them.

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
   stopped-only `stage`/`collect` with contained paths, and
   `start`/`stop`.
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

### Milestone zero — settle the surface (decided July 2026)

The adjudicated language decisions recorded in ./TASKS.md are
resolved and folded into the spec: `<key>` tokens deleted (keys
live only after `press`; `enter` kept as a derived form —
`type` + `press enter`); the reactive-handler keyword split
(`always` in reactive phases, `on` only in branching waits, a
container mismatch a validation error); a mandatory header
`deadline` for cyclic phase graphs; `finish` banned from linear
scripts (end of file is the one ending) and two handlers minimum
per branching `wait`; the pre-approved validation batch applied;
`boot` renamed `set-boot`; `machine=running` and an undiverged
header option deferred with reasons recorded in the spec;
response files accepted JSONC (the response concept later
dissolved into property values — the property rounds). The
execution-model-before-runner
sequencing rule is satisfied: the spec's execution model (sample /
episode / clock table), with the minimum run-events vocabulary,
is written — its "Execution model" section — and the runner
retarget may begin. The reference
script is valid under the answers.

### Script-surface realignment — absolute priority #1

The July 2026 script-language redesign
([planning/design/script-spec.md](design/script-spec.md), with
`script-examples/design-install.rlqs` as the reference script)
supersedes the surface milestones 1 and 5 implemented.
This milestone gates everything after it: no later milestone
starts before the tree speaks the new surface. Pre-beta, the old
surface is deleted, not bridged.

Deliverables:

1. Retarget `script.py` to the node grammar and typed EBNF: the
   three-production skeleton plus per-node signatures; no colons
   or commas, `name=value` properties, `/regex/` literals, `@`
   media references, `$`/`${}` input references, and the
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
   `script-examples/design-install.rlqs` retires into the
   converted builtins.

Done when: the FreeDOS install and verify scripts run end to end
in the new surface, `check-script` reports the timing plan, and
no old-surface syntax parses anywhere.

### Milestone 6 — The backend adapter seam

Extract the adapter API from the now-complete QEMU implementation
— the only adapter with a full control plane set — so the seam is
defined by working code, not speculation. The seam's doctrine is
pre-settled in
[planning/design/backend-adapter.md](design/backend-adapter.md)
(layering, seam inventory, ownership and capability doctrines,
extraction map); this milestone defines the signatures and records
them there.

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

### Milestone 7 — Second backend: VirtualBox

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

### Milestone 8 — Machine mobility: clone, export, import

The durable-artifact exits, once two backends make them
meaningful. The open question under "Decisions still needed"
(`import-vm` scope) must be settled at the start of this
milestone; export's design is settled (owner, 2026-07-22).

Deliverables:

1. `clone-machine`: a new machine under a new UUID retaining the
   source's
   resolved blueprint snapshot, with the source's writable drive
   images copied — a snapshot of a machine, never a shared
   state or backend registration.
2. `export-drive` and `export-machine` per the settled design
   (owner, 2026-07-22): native-or-raw drive images;
   exporter-registered native VMs — `--to` presented, never
   defaulted, the exporter vocabulary decoupled from backends;
   the initial exporter set is scoped at this milestone
   (virtualbox first; libvirt the recorded QEMU-ecosystem
   answer); media payloads materialized in; both commands
   stream-bearing.
3. `import-vm`: synthesize a blueprint from a native VM's
   configuration,
   disks preserved as generated media definitions taken as
   `base`; `--platform` required; never materializes a machine.

Done when: an exported FreeDOS machine boots under the backend's
own tooling, and a machine created from an imported blueprint
recreates from its bases like any authored machine.

### Milestone 9 — Guest agent communication

The QGA-profile client and guest agents per the design below —
backend-portable over serial. This milestone must not weaken the
permanent agentless DOS path; the same suites validate agentless
and guest-agent control planes with equivalent results.

Deliverables:

1. The host QGA client module: framing, `guest-sync-delimited`,
   `guest-ping`/`guest-info`, `guest-exec`/`guest-exec-status`,
   shared across carriers.
2. The extended `GuestExec` interface: request and result types
   covering deadlines, completion, output, and exit status,
   without exposing transport objects.
3. The DOS guest agent speaking the QGA execution profile over an
   emulated UART, provisioned through the agentless workflow (the
   serial-to-virtio bootstrap, steps 1–2).
4. The configured readiness waterfall with conservative fallback:
   selection before first dispatch only, ambiguous failures never
   retried on another control plane.

Done when: a guest command runs through the serial-carried agent
on QEMU with truthful capability reporting, and the agentless
suite still passes byte-for-byte.

### Milestone 10 — VNC control plane

The second agentless control plane, per "Control plane families"
below: framebuffer output plus keyboard and pointer input over
the RFB protocol, where backends provide it — QEMU natively,
VirtualBox with the extension pack, VMware Workstation; never
Hyper-V (a capability failure, not an emulation). Beyond a
backend-independent wire for display automation, this is the
groundwork for GUI installer scripting: RFB's
PointerEvent/KeyEvent are exactly the three portable input
primitives the GUI plan adopts (see "Decisions still needed").

Deliverables:

1. Per-backend VNC endpoint configuration contributed to launch
   config, endpoint artifacts under the machine cache, and a
   readiness probe.
2. An RFB client — framebuffer capture, key events, pointer
   events — as a control plane behind the same input and screen
   capabilities as agentless display, reusing the pixel-level
   text recognition built for the VirtualBox display plane in
   milestone 7.
3. `control-planes: ["vnc"]` policy honored end to end, with a
   capability error naming Hyper-V where it cannot exist.
4. The three portable input primitives (pointer move, button
   press/release, key press/release) exposed at the control-plane
   seam, with pacing control-plane-owned. Script-level pointer
   verbs and image matching remain horizon work.

Done when: the FreeDOS install script runs unmodified on QEMU
with the VNC control plane selected in place of agentless
display, and text observation through pixel recognition matches
the VGA-scraping results on the same screens.

### Horizon (sequenced later, not yet scheduled)

- `fork-blueprint` (a fire-and-forget authoring convenience;
  `new-blueprint` scaffolding lands in milestone 3).
- The virtio-serial carrier for the DOS agent and bounded
  `guest-file-*` operations (serial-to-virtio bootstrap,
  steps 3–5).
- Win9x/WinNT platform workflows, and with them GUI installer
  scripting: needle-like assets, script-level pointer verbs (on
  the milestone-10 input primitives), and image-match `wait`
  (see "Decisions still needed").
- VMware Workstation and Hyper-V adapters.
- Media commands beyond `fetch-media` (verify, remove).
- A `pytest-reliquary` plugin (per AGENTS.md prior art).

## Design principles

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

Status: bootstrap direction established on QEMU. The `GuestExec`
protocol, isolated agentless adapter, and its use by the DOS
workflow are implemented; later adapters and their implementation
details remain open. This section is QEMU-first but its seams are
backend-neutral: `GuestExec` and the control plane vocabulary apply to
every backend adapter, and the serial-carried QGA-profile agent is
the portable piece. This document does not by itself authorize
further implementation.

### Purpose

reliquary needs to support modern guests without weakening its
permanent agentless DOS path. The current DOS interaction combines
QMP keyboard events with VGA text-memory inspection. Future guests
may instead expose a serial console, a service over virtio-serial,
or QEMU Guest Agent (QGA).

These mechanisms should be isolated, but they should not be forced
behind one false "control plane" interface. They differ in both shape and
capability:

- keyboard input and VGA inspection are independent, host-mediated
  capabilities rather than a duplex byte stream;
- a serial port and a virtio-serial port carry bytes but define no
  command, completion, or file-transfer semantics;
- QGA is a structured request/reply protocol, normally carried over
  a virtio-serial port, with command and file operations defined by
  the guest agent.

QMP remains the QEMU adapter's management interface. Some control
planes use QMP operations, but QMP itself is not a guest
communication strategy. Other backends have their own management
interfaces (`VBoxManage`, `vmrun`, WMI) with the same rule: the
management interface and the control planes are distinct.

#### Limits of management-interface-only automation

Management-interface-only interaction (QMP on QEMU, and its analogues
elsewhere) is not a useful general automation path for Win9x,
Windows NT, Linux, or BSD guests. It can provide lifecycle control,
keyboard and pointing-device input, screenshots, and other
machine-level observations, which can automate bounded firmware,
installer, recovery, or GUI scenarios when reliquary knows the
exact screen sequence.

It does not provide the primitives needed for reliable general
guest automation: a stable textual output stream, command
completion and exit status, structured errors, or live file access.
Modern graphical and framebuffer consoles also cannot be read
through the DOS VGA text-memory technique. Screenshot recognition
or OCR could observe them, but would be a brittle UI-automation
control plane rather than a substitute for an OS communication protocol.

Linux and BSD can be useful through a configured serial console,
and modern guests through a guest agent, but those cease to be
management-interface-only communication. reliquary keeps agentless
interaction for the DOS workflow and bounded machine-level
automation; it is not the general fallback for modern platforms.

### Vocabulary

Keep three layers distinct:

1. **Carrier** — how bytes or device events cross the VM seam: QMP
   keyboard events, VGA memory, a VNC connection, an emulated UART,
   or a virtio-serial port.
2. **Protocol** — the meaning and framing carried over that
   mechanism: an interactive console or QGA JSON messages. A raw
   serial carrier has no protocol by itself.
3. **Guest integration** — what must exist in the guest: nothing
   for the keyboard/VGA/VNC paths, an OS-configured serial console
   or listener for serial, a virtio driver plus a QGA-compatible
   listener, or the upstream QGA implementation where the guest
   supports it.

A **control plane** composes the required carriers and protocol and
presents useful capabilities to a platform workflow. Configuration
selects a control plane, not merely a device type such as
`virtio-serial`.

### Control plane families

#### Agentless display console

The existing DOS path is the first real control plane. On QEMU it
combines:

- QMP `send-key` for input;
- VGA text-memory inspection for textual output and completion
  detection;
- QMP `screendump` as an independent diagnostic capability; and
- vvfat as the QEMU adapter's `hostdir` mechanism — a host
  directory as a writable guest FAT drive, proven for DOS-era
  write patterns (`stage`/`collect` ride at-rest image access
  instead).

It has no guest prerequisite and remains the DOS default and
fallback. It is not accurately modeled as a stream: output is a
sequence of screen snapshots, and keyboard input is independent of
that output. VGA text-memory inspection is QEMU-specific; other
backends supply their native input injection and framebuffer
capture as adapter carriers, and text readback there runs **one
shared fixed-font recognizer** over the captured framebuffer
(owner, 2026-07-21) — a control-plane composition over adapter
carriers, never a per-backend reimplementation. The portable
snapshot contract — character rows plus opaque,
equality-comparable per-cell attribute tokens — is in
[planning/design/backend-adapter.md](design/backend-adapter.md).

#### VNC

A separate agentless control plane: framebuffer output plus keyboard (and
pointer) input over the VNC protocol. QEMU, VirtualBox (extension
pack), and VMware Workstation can expose VNC servers; Hyper-V
cannot. VNC gives a backend-independent wire for display automation
where available, at the cost of pixel-level text recognition. It is
diagnostic and installer-automation machinery, not a general guest
communication path.

#### Serial console

An emulated UART connected to a host endpoint supplies a duplex
byte stream on every backend. Many operating systems already
contain UART drivers, so a custom driver is not inherently
required. The guest must nevertheless attach a console, shell, or
listener to the selected port before reliquary can do useful work.

A serial-console protocol may provide text input, streamed text
output, and prompt-based completion. It does not inherently provide
structured command results or file transfer. A custom listener
could add those operations, but that would be a separate protocol
carried over serial.

#### Guest agents

Structured guest protocols with command execution and file
operations:

- **QGA** on QEMU, usually over a named virtio-serial port. Support
  must depend only on QEMU's published guest-agent protocol, never
  on a particular downstream agent project.
- **Backend-native agents** — VirtualBox Guest Additions guest
  control, VMware Tools guest operations, Hyper-V PowerShell
  Direct / integration services — wrapped by their backend adapter
  where they earn their keep.
- **The reliquary guest agent** — a portable QGA-compatible profile
  (below) carried over serial, and therefore available on all four
  backends and on guests the native agents do not support.

### A portable automation agent

A host controller paired with guest-resident agents provides
substantial automation value, particularly for Win9x, old Windows
NT, DOS, and other systems on which vendor agents are unavailable.
This is a well-established architecture rather than a new category
of system:

- [QGA](https://www.qemu.org/docs/master/interop/qemu-ga-ref.html)
  provides synchronized request/reply messaging, capability
  reporting, command execution, exit status, and file operations;
- [VirtualBox Guest Control](https://docs.oracle.com/en/virtualization/virtualbox/7.0/user/vboxmanage.html)
  uses Guest Additions for host-initiated process and file
  operations;
- [Hyper-V integration services](https://learn.microsoft.com/en-us/windows/win32/hyperv_v2/integration-services-classes)
  expose guest services such as host-to-guest file copying;
- [SPICE vdagent](https://www.spice-space.org/agent-protocol.html)
  defines a framed protocol over a named virtio-serial port; and
- [libguestfs](https://libguestfs.org/guestfsd.8.html) uses RPC
  between a host library and `guestfsd` over virtio-serial.

The host side should normally be a client module inside reliquary,
not another long-running host agent. The backend owns the carrier
endpoint and reliquary owns the VM lifecycle. The guest side is the
resident agent or listener that turns protocol requests into native
OS operations.

#### Chosen target: a QGA-compatible execution profile

The gold-standard execution interface is QGA `guest-exec`. The
first guest implementations should provide a small, portable
profile of the published QGA protocol rather than a
reliquary-specific wire protocol. A guest implementation for an
unsupported OS may implement only the profile while reporting its
actual command set through `guest-info`. reliquary then depends on
the QGA wire contract, not on one particular guest implementation.

The initial profile consists of:

- `guest-sync-delimited` for reconnect and stale-stream recovery;
- `guest-ping` and `guest-info` for readiness and capability
  discovery;
- `guest-exec` and `guest-exec-status` for process completion,
  output, and exit status.

Bounded `guest-file-*` operations are the next capability, not a
prerequisite for proving execution. The existing staged-media path
can bootstrap the guest agent until live file operations exist.

The preferred compatibility level is the actual QGA request and
response shapes over the serial byte stream. A minimal subset is
still QGA-compatible: unsupported commands are omitted or disabled
in `guest-info`. A serial-specific protocol that merely maps to a
similar host result is a last resort, because it would require
another host adapter and would not be a drop-in replacement for
QGA.

The same profile can be carried over an emulated UART on systems
without virtio support and over virtio-serial where it exists. QGA
itself already supports both virtio-serial and ISA serial carriers,
so this does not require transport-specific protocol semantics.
Because every supported backend can expose an emulated UART, the
serial-carried profile is the backend-portable execution path.

#### Serial-to-virtio bootstrap

The development sequence deliberately bootstraps richer guest
integration from the permanent agentless base:

1. The keyboard/VGA and staged-media workflow boots the legacy
   guest, installs the serial listener, and starts it.
2. A minimal guest agent speaks the QGA execution profile over an
   emulated UART. The guest initially needs only its native or
   purpose-built UART support, a QGA message parser, and an OS
   execution adapter.
3. That control plane is used to develop and test the guest's
   virtio-serial driver.
4. The unchanged QGA message and execution layers are moved onto
   the virtio-serial carrier.
5. Additional QGA commands are added by capability, without
   changing the execution interface or carrier seam.

The guest implementation should therefore have three internal
seams:

- a carrier adapter that only reads and writes bytes;
- a QGA profile module that owns framing, synchronization,
  messages, and capability reporting; and
- an OS execution adapter that launches a native command and
  reports its state and result.

The host mirrors this separation: reliquary's QGA client owns
protocol behavior, while backend lifecycle configuration owns the
host endpoint and selected UART or virtio-serial device. Platform
workflows consume execution results and do not need to know which
carrier delivered them.

##### Provider topology

At reliquary's guest-execution seam, the waterfall consists of
control planes satisfying the same `GuestExec` interface; on QEMU:

1. standard QGA guest-exec;
2. the legacy agent over a named virtio-serial port;
3. the legacy agent over an emulated UART; and
4. agentless DOS execution through keyboard input, screen
   observation, and staged media.

The names above identify control plane roles, not committed Python class
or public configuration names. Each control plane owns its provisioning
requirements, readiness probe, endpoint selection, execution
lifecycle, and failure diagnostics. The waterfall selects the first
ready control plane that supplies the capabilities required by the
workflow. Other backends assemble their own waterfalls from the
control planes they support; the serial-carried profile and the agentless
display control plane are the common members.

Multiple control planes do not imply multiple copies of the protocol
implementation. The QGA-speaking control planes share one deep QGA client
module for framing, synchronization, capability discovery,
`guest-exec`, status polling, and result decoding; they configure
different carriers and endpoints around that shared implementation.
The agentless control plane has a genuinely different implementation
behind the same execution interface.

`GuestExec` is currently a runtime-checkable `typing.Protocol` with
`wait_ready(timeout)` and `execute(command, timeout)`. The first
implementation models the readiness and command-completion
semantics already available from the agentless DOS workflow. Before
a QGA control plane is added, extend this narrow interface with
deliberate request and result types covering deadlines, completion,
output, and exit status without exposing QGA transport objects.
Control-plane-specific limitations, such as unavailable exit status or
separate standard-error capture, must be explicit capabilities or
result states rather than invented values.

By default, the DOS agent selects its carrier once at startup. It
first probes for the named virtio-serial port and verifies that the
port can actually be opened and used. If that probe fails, it opens
the configured UART instead. Checking only that a virtio driver is
resident is insufficient because the device or named port may be
absent or unusable.

During the transition, reliquary configures both guest devices and
their host endpoints. The host QGA client probes the corresponding
endpoints in the same order, synchronizes with the one on which the
agent responds, and locks that carrier for the VM's lifetime.
Explicit UART-only and virtio-serial-only modes remain useful for
testing and diagnosis.

Carrier fallback occurs only during startup, before command
dispatch. Neither side switches carriers after a command has begun
or retries that command on the other carrier; doing so would make
execution-at-most-once ambiguous. A VM restart permits a fresh
carrier probe.

The DOS guest still has one QGA profile and execution
implementation. Its UART driver is replaced by a virtio-serial
driver without replacing the agent above it.

A minimal DOS listener that conforms to the QGA wire contract is
already a real, limited QGA-compatible guest agent even when it
runs over UART. The long-term goal is the same DOS agent, with a
progressively broader QGA command set, running over native DOS
virtio-serial support. Virtio is the preferred final carrier, not
what makes the agent QGA-compatible.

If the serial stepping stone cannot speak the QGA profile and
requires a genuinely different wire protocol, only its reliquary
control plane adapter changes; the `GuestExec` interface and waterfall
remain stable. That is the fallback design, not the target.

Legacy execution semantics must be truthful where the OS cannot
implement the full concurrency model. A single-tasking DOS agent
may:

- allow only one command in flight;
- return a synthetic process handle before invoking the child;
- defer status replies while the child owns the machine; and
- capture output through temporary files and return it after
  completion.

Those limitations should be documented and tested as profile
behavior, not hidden behind optimistic capability claims. Win9x,
Windows NT, and multitasking Unix-like guests can implement the
asynchronous process model more closely.

A new protocol becomes justified only if an implementation
experiment proves that QGA semantics cannot meet essential
constraints, such as memory limits on a 16-bit guest, streaming
output, cancellation, or safe recovery after a mid-command
disconnect. In that case, retain the proven elements: framed
requests, correlation identifiers, version and capability
negotiation, bounded payloads, explicit error categories,
duplicate-request handling, and an unambiguous distinction between
transport failure and command completion.

Never retry an execution request automatically unless the protocol
can prove that the guest did not begin it. At-most-once execution
and reconnect behavior are part of the protocol interface, not
incidental host-client details.

### Capability-oriented platform workflows

Platform workflows own OS meaning: provisioning, readiness, command
syntax, completion, and result collection. Control planes own
communication mechanics and protocol details. The seam between them
should be expressed in terms of the smallest capabilities workflows
actually need, not one broad interface every control plane must pretend
to implement.

Candidate capabilities are:

- text or key input;
- screen snapshots;
- a duplex byte stream;
- structured command execution;
- guest file read/write; and
- screenshots for diagnostics.

The list is a design inventory, not a commitment to six public
classes. Add a seam only when two real control planes need to satisfy the
same workflow capability. Until then, keep control plane details private
to their platform workflow.

In particular, screenshots remain a management-interface
diagnostic regardless of the selected control plane. They are
explicitly outside the `GuestExec` protocol: using QGA for
execution does not affect screenshot availability, and a control plane
does not implement or advertise screenshots. Orchestration may
capture them internally when useful, while the existing direct-use
screenshot surface remains independent. File exchange should not be
bundled into a console abstraction: vvfat and QGA file operations
have different lifecycle and consistency rules.

The QEMU `Machine` exposes its identity-verified QMP session
through `Machine.qmp()`. Raw QMP `cmd()` and HMP `hmp()` operations
remain available to embedding callers. Control planes receive a `Machine`
and use this public seam; they do not connect to QMP directly or
duplicate monitor methods on their own interfaces.

### Configuration and lifecycle

Platform selection and the allowed control plane policy must be explicit
through the machine blueprint or per-invocation configuration. reliquary
must never infer the platform from the guest image, screen, or
device behavior; capability probes only choose among control planes
already permitted by that policy. The current DOS default remains
the agentless display-console control plane. Once guest-agent support
exists, the intended DOS automatic policy is an explicitly
configured ordered readiness waterfall:

1. probe the standard QGA endpoint;
2. probe the legacy agent's named virtio-serial endpoint;
3. probe the legacy agent's UART endpoint; and
4. fall back to the agentless keyboard/VGA workflow.

The first three candidates may all use the same host QGA-profile
client. If a QGA-compatible DOS agent uses the standard QGA
endpoint, the first two steps collapse: reliquary neither needs nor
tries to distinguish the upstream QGA binary from another
conforming implementation.

An endpoint is ready only after `guest-sync-delimited` succeeds and
`guest-info` advertises the commands required by the workflow. A
connected host socket, an attached device, or resident guest driver
is not proof that a compatible listener is servicing the endpoint.
Each unsuccessful probe uses a bounded part of the overall startup
deadline.

The selected candidate is reported in diagnostics and remains fixed
after the first command is dispatched. A timeout or transport
failure after dispatch must surface as an ambiguous execution
failure; reliquary must not resend the command through the next
candidate. The agentless final fallback applies only to platform
workflows, currently DOS, that explicitly support keyboard and
screen automation. It is not a general fallback for modern guests.

A control plane may need two lifecycle phases:

1. contribute validated backend launch configuration for its
   carrier and host endpoint before the machine starts; and
2. connect to that endpoint and establish protocol readiness after
   startup.

Endpoint paths and other persistent artifacts must remain under the
machine's cached materialization. Ownership verification remains
mandatory for every
management-interface operation, including operations used by the agentless
control plane.

Automatic fallback must be conservative. It may select another
configured control plane only before a guest command has been dispatched.
Retrying through a fallback after an ambiguous transport failure
could execute a command twice. The selected control plane and fallback
decision should be visible in diagnostics.

## Roadmap constraints

No backward compatibility before beta (see AGENTS.md): no format
versioning or migration, no API aliasing, no compatibility shims.
Every milestone may reshape interfaces freely and completely until
at least a beta-quality release exists.

Agentless DOS operation on QEMU is the permanent base described in
AGENTS.md; no milestone may weaken it.

The declared-media convention (drives named by medium, slot, and
format) carries over into machine blueprints and cached
materializations. New
media kinds, controllers, and USB devices must extend the same
convention — a new medium name — not appear as opaque raw backend
arguments.

The bootstrap direction is important: agentless reliquary is the
rig used to test the DOS drivers and guest agent before those
components exist. Once available, the same suites should validate
agentless and guest-agent control planes with equivalent results.

## Decisions still needed

- **Backend priority order** for default assignment when a blueprint
  names no backend (proposed: QEMU, VirtualBox, VMware Workstation,
  Hyper-V — best scriptability first).
- **Format versioning at beta**: pre-beta, user documents carry no
  version field and no `$schema` field (settled, owner 2026-07-21:
  a pinned schema reference is a version field in disguise, and a
  pre-beta document has no format vintage — the only schema that
  matters is the installed reliquary's, which editors bind by file
  association; an embedded pin would go stale in seeded files
  under never-overwrite and let the editor pass what reliquary
  rejects). When compatibility guarantees arrive — no earlier than
  beta — the leading candidate spelling for the version field is
  `$schema` as a versioned URL: one field declaring the document's
  format version and binding editors to the matching published
  schema.
- **Script spec details** (the control-flow and property-binding
  shape
  are decided — see "The scripting language" and
  planning/design/script-spec.md): the portable key-name vocabulary for
  `press`/`<key>` tokens is published in the spec as a closed set;
  confirm it at realignment. Literal value defaults are resolved:
  they live in the blueprint `parameters` field (U5's
  blueprint-held seam), never in property declarations — a default
  in
  the script would undercut the blueprint as the customization
  surface.
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
- **Blueprint details**: whether per-drive backend settings are ever
  needed beyond the top-level `backend-settings` scope, and how
  running-machine reconfiguration (hot media changes vs.
  stopped-only changes like memory) is surfaced in the CLI and
  script language.
- **Promoting runtime changes**: whether a convenience command
  copies a state-side runtime change (e.g. attached media) back
  into the blueprint, or users always edit the blueprint by hand.
- **Machine cache cleaning**: whether a `clean machines` command
  reclaims cached materializations of stopped machines wholesale
  (they regenerate like everything else under `cache/`), or
  whether `recreate-machine`/`destroy-machine` per machine is
  enough.
- **`import-vm` scope**: which backend config translates into the
  synthesized blueprint (memory, drives, controllers are clear;
  what of NICs and other devices the blueprint doesn't model yet),
  whether untranslatable configuration fails the import or lands
  in `backend-settings`, and whether import can target a named
  native snapshot in a VM's disk chain rather than the current
  head (the generated definition would point at that snapshot's
  file).
- **Blueprint device growth**: firmware/boot semantics (BIOS vs UEFI)
  for post-DOS platforms, and when network, display adapter,
  audio, and USB become first-class blueprint fields (each following
  the drives pattern: agnostic vocabulary, capability-checked per
  backend). Storage controller *types* are already blueprint vocabulary
  (per-drive `controller`); still open are per-platform controller
  defaults beyond `ide`, whether slot ranges widen for
  multi-device controllers (additive change), and how Hyper-V
  generations surface (a backend setting vs. inferred from
  declared capabilities).
- **GUI installer scripting** (an explicit goal: win9x/winnt setup
  GUIs and beyond). Text scraping ends at text mode; GUI guests
  need screenshot-based matching. The asset shape is settled —
  see "Landmarks": one declaration plus variant renderings,
  whole-screen matching with fuzzy/ignore modifier regions,
  catalog and embedded resolve-in-place forms under
  authored-asset resolution, and the always-on cursor
  normalization contract — with os-autoinst's needle design the
  concept reference behind it (AGENTS.md prior art). Still open:
  the full asset spec (the `.rlql` JSON schema, the similarity
  metric, landmark-block placement within a script), and pointer
  input, which reliquary currently lacks end to end (machine
  blueprint pointing-device field, a control-plane input
  capability, and the script verbs — match-and-click with the
  click point in the asset; click owns its search as an
  observation-bearing action and needs its timing-matrix row).
  The input seam should follow os-autoinst's two-layer event
  model: three portable primitives — pointer move (x, y), button
  press/release, key press/release — with clicks, drags, chords,
  and paced typing composed above them, and event pacing owned by
  the control plane. The primitives are exactly VNC's RFB input
  vocabulary (PointerEvent, KeyEvent), so a VNC control plane
  implements them with no translation, and QMP/VBoxManage/WMI
  input paths reduce to the same three. Synchronization concepts
  to adopt with them: act-then-confirm (an input step optionally
  asserting the screen changed) and screen-stillness waits;
  pointer hygiene has hardened into the landmark normalization
  contract (pointer actions always end parked). Also open: a
  host-side landmark-cropping convenience (a CLI subcommand,
  never a service). Era note: DOS/9x-era setup GUIs are
  fixed-mode, fixed-font, animation-free — asset churn should be
  far below openQA's — and NT-era setup is largely
  keyboard-drivable, so keyboard-first remains the preferred path
  where it works. Throughout, os-autoinst is a **concept
  reference only** — its designs are studied and reimplemented,
  never its code (see AGENTS.md prior art for the licensing
  boundary).
- **Distribution-assertion field shape**: the exact field(s) in a
  media definition that assert redistribution licensing for
  built-in URLs (an SPDX identifier? free text naming the
  license? both?), and whether user-owned definitions may carry
  the same field inertly.
- **Media commands beyond `fetch-media`**: whether the CLI grows
  verbs such as verify and remove, and whether each can select
  embedded definitions through `--script` when needed.
- **Hyper-V agentless screen strategy**: whether WMI thumbnail/
  keyboard automation is good enough for installer scripting or
  Hyper-V machines require the serial/agent control planes from day one.
- **Concurrent machines**: per-machine exclusive locking is
  decided (planning/design/instance-model.md); still open is whether any
  home-wide limit applies to machines running at once (the
  per-machine lock and identity model suggests none).
- **Friendly machine aliases**: machine identity is already
  human-readable (`<blueprint>-<n>`); still open is whether
  listings and selectors additionally offer docker-style generated
  word aliases, or whether numbered ids plus blueprint selection
  make them unnecessary.
- The exact initial `guest-exec` subset, including argument and
  environment support, capture modes, output limits, timeouts, and
  legacy-OS deviations.
- Which bounded `guest-file-*` operations follow execution,
  including file consistency and atomic replacement semantics.
- Whether a separate plain serial-console control plane remains useful
  once the QGA-compatible serial listener exists.
