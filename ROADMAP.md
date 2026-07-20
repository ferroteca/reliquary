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

The unit of design is the **operation** performed against a
machine: start it, stop it, attach media, send input, run a guest
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
  a backend, reliquary assigns one from an internal prioritized list
  of the backends actually available, and records the assignment in
  the machine state so the machine stays on that backend
  thereafter.
- **Backend state stays in the cached materialization.** Each
  backend is instructed to keep its machine files (disk images,
  `.vbox`, `.vmx`, Hyper-V VM/VHD paths) inside
  `cache/machines/<id>/`, so a machine's cache directory is the
  whole materialization.
- **The serial-carried reliquary guest agent is backend-portable.**
  Every backend can expose an emulated UART, so the QGA-profile
  agent described below is the one guest-side investment that pays
  off on all four backends.

## The machine model

A **blueprint** is a reusable, user-owned JSON description of a kind
of machine. A **machine** is one realization of that blueprint: its
durable record, writable disks, backend object, and run history.
One blueprint may have zero, one, or many machines (see
[docs/instance-model.md](docs/instance-model.md)):

```text
<reliquary_home>/blueprints/
└── <name>.json              the blueprint (user-owned)
<reliquary_home>/machines/
└── <id>.json                the machine record (reliquary-owned:
                             blueprint reference, phase)
<reliquary_home>/cache/machines/<id>/
├── state.json               the resolved state (reliquary-owned)
├── drives/                  the machine's disk/floppy images
├── runs/                    append-only run records (transcripts,
│                            screenshots, outputs)
└── ...                      backend files and logs
```

Everything under `cache/machines/<id>/` is reliquary's and
regenerates from the blueprint (plus media definitions and scripts);
nothing is ever hand-placed there. Pre-existing content enters a
machine through the blueprint: `media` references, and starting-point
images (`base`) that machine drives are differenced from, or
copies of.

### Blueprint, record, and state

User documentation (planned format, written ahead of
implementation): [docs/machine-blueprint.md](docs/machine-blueprint.md) with
its [field reference](docs/machine-blueprint-reference.md) and
[cookbook](docs/machine-blueprint-cookbook.md), and the ownership,
locking, and recovery model in
[docs/instance-model.md](docs/instance-model.md).

The blueprint is reliquary's own backend-agnostic format — never a thin
veneer over one backend's configuration. Three documents, one
owner each: the **blueprint** (`blueprints/<name>.json`) is the machine
shape as the user defined it — authored by hand, by `init`, or by
`import`; reliquary reads it and never writes it. The **machine
record** (`machines/<id>.json`) is reliquary-owned: the machine's
blueprint reference, creation time, and lifecycle phase. Machines have
no separate human name — the generated UUID in the record's file
name is the machine's identity, and commands accept any
unambiguous prefix of it, git-style. The **state** (`cache/machines/<id>/state.json`) is the
machine as it actually is — fully resolved (aliases
canonicalized, defaults materialized, the resolved blueprint digest
and backend identity recorded) and rewritten atomically in the
same operation as every machine change. Every mutating operation
takes an exclusive per-machine lock; an interrupted operation is
detected by phase and generation and either rolled back safely or
failed with explicit recovery instructions. The resolved snapshot
recorded at `create` is the machine's **baseline**: every `start`
reconciles baseline, state, and backend — applicable differences
are applied, contradictions fail closed naming both sides — and
never re-reads the blueprint file. Editing a blueprint affects future
`create` operations only; adopting blueprint edits into an existing
stopped machine is the explicit `apply`, which re-resolves the
blueprint, applies what the machine can absorb without regenerating
drives, and records the new baseline digest (drive-regenerating
changes fail closed, pointing at `recreate`). Runtime
reconfiguration (script steps, CLI) updates the state only;
permanence belongs in the blueprint, adopted by `apply`. Script
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
hatch — a blueprint without it is portable by construction).
Validation and capability mismatches fail closed, naming the
backend and missing capability.

### Home layout

```text
<reliquary_home>/
├── blueprints/               machine blueprints, <name>.json (above)
├── machines/            machine records, <name>.json (above)
├── scripts/             reliquary automation scripts
├── properties.json      personal property registry (ordinary values
│                        and markers for host-stored secrets)
├── media/               shared media definitions (mirror URLs, archive
│                        and payload SHA-256; one definition per
│                        source archive can itemize several named
│                        files) — see docs/media-spec.md
└── cache/               fetched/cached files (clean commands
                         only ever delete what reliquary can
                         restore)
    ├── downloads/        cached source archives (redownloadable;
    │                    reclaimed by `clean downloads`)
    └── media/           the named payload files machines mount,
                         fetched/extracted/verified on demand
```

The current `install-media/` cache folds into `cache/`. The
current root-level `drives/`, `machine.json`, and `vm.json`
layout is superseded by the blueprint/record/cache split; the project
is pre-release, so this is a replacement, not a migration.

Cached materializations live under `cache/machines/<id>/` (see
"The machine model" above).

## The CLI

The CLI is a thin veneer over the embedding API, which remains a
first-class surface: every command maps one-to-one onto a public
Python call with the same semantics — blueprint resolution, machine
creation and selection, lifecycle, `apply`, scripting, media,
properties — and nothing is CLI-only. Where the CLI resolves a
selector, the API takes the same identifiers (a blueprint name, a
machine id); where the CLI prints an id, the API returns it.

Blueprints and machines are selected by explicit flags, never by
position: `--blueprint <name>` (short `-b`) names a blueprint,
`--machine <id>` (short `-m`) a machine. A machine's identity is its generated UUID; `--machine`
accepts the full id or any unambiguous prefix, git-style, and
listings print a short prefix for exactly this use. As the common
convenience, `--blueprint` also selects a *machine* on machine-level
verbs: when exactly one machine of that blueprint exists — the normal
one-machine-per-blueprint case — the blueprint name is enough; with several
machines the command fails and lists their ids, and with none it
fails and suggests `create` (`script` instead creates one).
Nothing is ever selected positionally or by guessing.
Property-registry commands put an operation (`list`, `get`,
`set`, or `unset`) after `property`.

The lifecycle vocabulary is two-layered. Blueprints are plain files
under `blueprints/`: authored, renamed, and removed directly in an
editor, with `init` and `import` as authoring conveniences and
`delete --blueprint` as the managed removal. Machine-level verbs act
on machines: `create` realizes a blueprint as a new machine (record,
new id, cached materialization), `start`/`stop` run it, `destroy`
discards only the materialization (record, id, and blueprint reference
remain), `recreate` is `destroy` + `create` under the same id,
and `delete --machine` removes the machine entirely. `import`
synthesizes a blueprint from a native VM — blueprint authoring only;
realizing it afterward is an ordinary `create`.

```text
reliquary list blueprints
reliquary list machines [--blueprint <name>]
reliquary create --blueprint <name>
reliquary start (--machine <id> | --blueprint <name>) [--display]
reliquary stop (--machine <id> | --blueprint <name>)
reliquary apply (--machine <id> | --blueprint <name>)
reliquary destroy (--machine <id> | --blueprint <name>)
reliquary recreate (--machine <id> | --blueprint <name>)
reliquary delete (--machine <id> | --blueprint <name>)
reliquary clone (--machine <id> | --blueprint <name>)
reliquary export (--machine <id> | --blueprint <name>) [<destination>]
reliquary import <source> --blueprint <name> --platform <platform>
reliquary script <script_name> (--machine <id> | --blueprint <name>)
    [--responses <path>] [--display]
reliquary check-script <script_name> [--machine <id> | --blueprint <name>]
    [--responses <path>]
reliquary fetch <media_name> [--script <script_name>]
reliquary property list [<prefix>]
reliquary property get <key>
reliquary property set <key> <value>
reliquary property set <key> --secret
reliquary property unset <key>
reliquary clean downloads
reliquary clean media
```

Lifecycle semantics:

- `list blueprints` shows each blueprint with its machine count; `list
  machines` shows each machine's short id, blueprint, phase, and
  backend (`--blueprint` filters to one blueprint's machines).
- `create` validates and resolves the named blueprint
  (`blueprints/<name>.json` — written by hand, by `init`, or by
  `import`), creates a machine record with a new id, prints that
  id, and materializes the machine's drives and backend object.
  Blueprints are authored documents. Media definitions are likewise
  user-owned, though a script can seed missing library
  definitions from its embedded blocks before its first run.
- `apply` adopts the current blueprint into a stopped machine: it
  re-resolves the blueprint, reconciles the machine to the new
  resolution (memory, boot order, drives enabled/disabled, media
  changes), and records the new baseline digest. Changes the
  machine cannot absorb without regenerating drives (`size` or
  `base` changes on materialized images) fail closed naming both
  sides; `recreate` is the honest alternative.
- `destroy` discards the machine's cached materialization —
  state, backend machine, drive images — and marks the machine
  unmaterialized; its record, id, and blueprint reference remain. The
  blueprint is never touched.
- `delete --machine` removes the machine record, destroying the
  materialization first if one exists; the blueprint remains a plain
  file. `delete --blueprint` removes the blueprint file itself and fails
  closed while any machine of it exists, naming the machine ids —
  delete the machines first (on this verb only, `--blueprint` is the
  blueprint itself, never a machine selector).

- `script` completes preflight, installs missing embedded media
  definitions, resolves its machine (creating one when `--blueprint`
  names a blueprint with no machine yet), and starts it if it is not
  already running before executing guest steps.
- `fetch` downloads, extracts, and hash-verifies a defined media
  item (see docs/media-spec.md). It is a convenience: machine
  operations resolving a `media` reference to a fetchable
  definition fetch implicitly. Source archives are cached under
  `cache/downloads/`, separate from the payloads in
  `cache/media/`. `--script` installs that script's embedded
  definitions before fetching, without executing guest steps.
- `property` maintains the home-wide personal registry described in
  docs/property-registry.md. Ordinary strings live in
  `properties.json`; secret values live only in a protected host
  credential store, with a marker in the file. Listing and getting
  secrets never reveal them, and secret setting uses a no-echo prompt
  rather than an argument that would enter process listings or shell
  history.
- `clean downloads` / `clean media` reclaim the two caches:
  cached source archives, and payload files reliquary can fetch
  again. Nothing irreplaceable (definitions, `local-path` files,
  payloads without a download source) is cleanable.
- `recreate` is exactly `destroy` + `create` under the same
  machine id: drives regenerate as declared (`size`
  blank, `base` differenced or copied afresh). Since resolution
  and backend assignment re-run, a recreated machine may land on
  a different backend — `recreate` is the sanctioned way to move
  a machine between backends, and regenerated drives arrive in
  the new backend's formats.
- `clone` duplicates a stopped machine as a new machine record
  under a new id (printed like `create`'s): it retains the
  source's resolved blueprint snapshot and copies the source's
  writable drive images — a snapshot of a machine, not another
  blueprint. The clone gets its own backend object and `backend-id`;
  state and backend registration are never copied.

- `export` copies a stopped machine out to the backend's native
  management — registered in the backend's own machine location
  (or an explicit destination) with disks in its native format.
  The exported VM is independent and permanently outside
  reliquary's purview: this is the first-class form of "copy the
  result to a platform built for long-lived machines," and
  ownership verification guarantees reliquary can never touch it
  afterward.
- `import` synthesizes a blueprint from a native backend VM's
  configuration (memory, drives, controllers — translation of
  backend config, not guest inference), preserving the VM's
  disks as media items — copied (never moved; the source is not
  touched) with generated definitions (computed hashes, no URL),
  the blueprint's drives taking them as `base`. A machine created
  from an imported blueprint recreates like any other: from its
  bases. `platform` is not
  knowable from any backend configuration, so `import` requires
  `--platform` explicitly; the never-infer rule holds. `import`
  stops at the blueprint: it never materializes a machine — running one
  afterward is an ordinary `create`. Drive preservation is
  entirely the blueprint's job, through the drive materialization
  triad: `size` (always a fresh blank disk at `create`), `base`
  with type `difference` (the default — a differencing disk
  backed by the base image), and `base` with type `duplicate`
  (materialized as a full copy).
- Machines **stay running** until explicitly stopped — by a script
  step or by `stop`. No command implicitly tears the machine down.
- `--display` shows the backend's console window instead of running
  headless.
- Ownership verification generalizes: no adapter sends a control
  command to a hypervisor object until it has verified that the
  object is the one recorded in the machine's state (the QMP
  identity check is the QEMU instance of this rule).

A future milestone adds `init`, the blueprint-scaffolding
convenience: a simple CLI command that writes a minimal starter
blueprint from a few answers or flags (platform, disk size,
installer media), so new machines don't begin from a blank
editor. One-shot, fire-and-forget scaffolding only — it emits an
ordinary blueprint file the user owns from then on; no template
registry, no regeneration, no linkage back to the scaffolder.

## The scripting language

reliquary gets its own scripting language for automating guests.
Scripts are stored in `<reliquary_home>/scripts` and invoked as
`reliquary script <script_name>` against a machine selected with
`--machine <id>` or `--blueprint <name>`.

**Decided shape: a line-oriented, constrained DSL.** A script is
a UTF-8 text file (`scripts/<name>.rqs`): header directives, then
one statement per line — a verb, arguments, and comma-separated
`key: value` modifiers — with `#` comments and brace blocks. It
is a domain-specific programming language with sequencing,
branching, named states, and explicit transitions, but no
expressions, mutable variables, functions, arithmetic, or
general-purpose loop construct. Computational orchestration
belongs in Python.

A script has one of two non-mixing shapes. A **linear script** is
an ordered top-level sequence. A **state-machine script** declares
an explicit `initial` state and named states; every sequential
state ends in a standalone `-> <state>` or `done`, with no
textual fallthrough. A state is either sequential (ordered
statements and `expect`) or reactive (only `on` handlers, all
active from entry), never the former hybrid of an ordered body
and positionally armed ambient handlers. Reactive dispatch is
single-threaded and run-to-completion. A handler fires once per
matching episode and cannot fire again until its condition has
become unmatched and later matches again, preventing persistent
screens from repeating destructive input on every poll. Smaller
states, rather than statement position, scope which handlers are
active. There are no anonymous states or handler-splicing macros.

Text watches are case-sensitive **normalized text matches**:
screen rows decode to Unicode, trim cell padding, and collapse
whitespace before literal substring or opt-in Python-regex
matching. `expect` covers small ordered forks. `stopped` is the
machine no-longer-running condition; it does not claim that the
shutdown was graceful. A guest reboot has no reliquary verb or
event: the script types the guest command, makes a menu choice, or
sends the appropriate key sequence, then watches for the screen
that follows. There is likewise no `run` verb: `enter` delivers a
console line, and completion is a separate explicit observation.

Timing separates three meanings: `timeout` bounds one
observation (or a reactive state's inactivity), `deadline` bounds
total state/block time without resetting, and `stable` requires a
condition to remain matched. Polling and input pacing belong to
the control plane; the language has no `delay` or sleep. Duration
literals carry units (`500ms`, `30s`, `20m`). Block modifiers are
written on the opening line.

Immutable `text`, `media`, and `secret` inputs externalize
run-specific data without adding decisions or expressions. `${name}`
references are bound before execution. Each input may name a
home-wide user property with `property: "<key>"`; an explicit JSON
response wins for that invocation, then the property registry, then
interactive prompting. Missing noninteractive, mistyped, or
unresolved-media values fail before the machine starts, as do
ordinary/secret kind mismatches.

The registry is a flat, user-owned `properties.json` map of dotted
names to strings or `{"secret": true}` markers. Secret values never
enter that file: they live in the host's protected credential store,
scoped by reliquary home and property name, with no plaintext fallback.
`secret` inputs may expand only in `enter` and `type`. Transcripts
record input references and source kinds, never values or expanded
secret-bearing arguments; textual diagnostics redact known secret
values, and automatic failure screenshots are suppressed after secret
input. This protects reliquary's records, not guest logs, history, or
an explicitly requested screenshot. The complete planned contract is
in [docs/property-registry.md](docs/property-registry.md).

Scripts may also embed ordinary media-definition JSON objects in
top-level, labeled `media <label> { ... }` blocks. After full
preflight but before machine resolution, running the script installs
each missing definition as `media/<label>.json`; `fetch --script`
does the same without executing guest steps. Existing definitions are
never overwritten: wholly identical blocks are already installed,
while differing targets, item collisions, and partially overlapping
blocks fail with both locations named. New files use canonical JSON
and become ordinary user-owned library documents. Fetched and
extracted artifacts use the common caches.

Offline `stage`/`collect` require a stopped machine on every
control plane; future live transfers get distinct verbs rather
than backend-dependent semantics. `start` reconciles the authored
machine blueprint and `stop` is visibly a host hard power-off.
There is no `restart`: a hard power cycle is the explicit pair,
and a guest reboot remains guest input. Parsing, response binding,
whole-script capability preflight, and static control-flow checks
all finish before the first guest input. User documentation
(planned format, written ahead of implementation):
[docs/script-spec.md](docs/script-spec.md).

The primitive vocabulary already exists in today's CLI and Python
surface — it is the proven instruction set the language must cover:

- enter/type text and send keys;
- wait for normalized screen text (literal or regex), machine
  state, or a stable observation, with timeout/deadline bounds;
- select an entry in a cursor-key menu by visible feedback;
- take a screenshot;
- define embedded media, attach/detach it, and start/stop the
  machine;
- stage files to and collect files from the guest.

Language design goals:

- **Backend- and control plane-agnostic at the surface.** A script says
  "wait for this text"; the machine's backend and selected control plane
  decide how that is observed.
- **Inspectable and replay-oriented.** The graph is explicit and
  finite, while guest-selected routes and cycles remain honest.
  Failures report the step, route, observed state, and screenshot.
- **Small.** The language exists to sequence guest automation, not
  to be a general-purpose programming language. Anything
  computational belongs in Python via the embedding API, which
  remains a first-class surface.
- **Grows coherently.** Image matching and pointer input extend
  observation and action without adding a second control-flow
  model. Before beta, empirical use may still reshape the syntax;
  after the language is proven, existing forms retain their
  meanings and new capabilities stay explicit and preflightable.

OS installation recipes become install scripts: the current
`recipes/` Python package retires once the language can express the
FreeDOS plain install end to end. Media acquisition (download,
hash-verify, cache under `cache/media/`) stays a host-side capability
the language can invoke, with pinned hashes kept in shared
definitions or directly inside the script.

## Milestones

**DOS under QEMU is the top priority.** Milestones 1–5 deliver
the complete documented design — the media library, the instance
model and machine blueprint, the property registry, and the scripting
language, i.e. everything in `docs/` — for the DOS platform on
the QEMU backend alone. Only then does the design generalize:
the adapter seam is extracted from working code (6), proven by a
second backend (7), and extended with machine mobility (8), guest
agents (9), and the VNC control plane (10).

Each milestone is independently shippable: the tree builds, the
test suite passes, and the FreeDOS install keeps working end to
end on whichever surface that milestone provides. Within 1–5 the
order is dependency-driven — the media library before blueprints can
reference it, the machine model before scripts can drive it, the
property registry before script inputs can bind to it. Within a
milestone the listed deliverables are ordered but may land in
separate commits.

### Milestone 1 — FreeDOS plain install to hard disk (finish as-is)

The proving ground for scripted installation, nearly done on the
current stack. The recipe's shape (Python module under `recipes/`,
`reliquary install freedos-plain`) is acknowledged as transitional
and retires in milestone 5.

Deliverables:

1. Script the installer's "Plain DOS system" path onto the target
   disk (the LiveCD boots to a live `D:\>` prompt; `SETUP.BAT`
   starts the installer). Watch guest memory: the LiveCD warns
   about limited RAM at the 16 MiB DOS default.
2. A verification pass that boots the installed disk and confirms
   a DOS prompt.

Done when: `reliquary install freedos-plain` runs unattended from
a clean home to a bootable hard-disk image, and the verification
pass confirms the installed disk boots to a prompt.

### Milestone 2 — Media library and caches

All of [docs/media-spec.md](docs/media-spec.md), implemented
before the machine model so blueprints can reference media by name.
`media.py`'s recipe-scoped acquisition is reshaped into the
library; the `install-media/` cache folds into `cache/`.

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
   its hash is treated as absent and refetched when a source
   exists — the cache heals itself.
4. `reliquary fetch <media_name>` and `reliquary clean
   downloads` / `clean media` (nothing irreplaceable —
   definitions, `local-path` files, sourceless payloads — is
   cleanable). `fetch --script` follows in milestone 5 with
   script parsing.
5. The FreeDOS recipe consumes its media through the library
   instead of its private `install-media/` path.

Done when: the FreeDOS media flows through a definition end to
end; a deliberately corrupted cached payload heals on next use;
`clean` reclaims only restorable files; the recipe passes on the
new layer.

### Milestone 3 — The instance model and machine blueprints (QEMU-only)

The whole machine model — [docs/instance-model.md](docs/instance-model.md)
plus the [machine blueprint](docs/machine-blueprint.md) with its
[field reference](docs/machine-blueprint-reference.md) and
[cookbook](docs/machine-blueprint-cookbook.md) — scoped to one
backend. The `backend` field is parsed and validated in full, but
with QEMU the only implementation, assignment is trivial; the
adapter seam that makes it real is milestone 6. Capability checks
are real from the start, derived from what the QEMU
implementation can actually do. This replaces the root-home
`drives/`, `machine.json`, and `vm.json` layout wholesale —
pre-release, so no migration.

Deliverables:

1. Blueprint validation per the full field reference: `platform`,
   `backend`, `memory`, `cpus`, `drives` (slot convention and
   aliases, per-drive `controller`, `media` references, `size`
   blanks, `base` with `difference`/`duplicate`, `enabled`),
   `boot`, `control-planes`, `backend-settings` — format checks
   and capability checks both failing closed and naming the
   problem.
2. Machine records under `machines/<id>.json` (blueprint reference
   and resolved digest, creation time, phase; the generated UUID
   in the file name is the machine's identity) and the
   cached materialization under `cache/machines/<id>/`
   (`state.json` fully resolved, canonical drive-image naming,
   qcow2 materialization of the `size`/`base` triad). The QEMU
   layer re-anchors on it; `MachineConfig`, root-home
   `machine.json`, and `vm.json` are absorbed and deleted.
3. Lifecycle integrity per the instance model: operation
   generations, exclusive per-machine locks, atomic JSON
   replacement, and startup detection of interrupted phases with
   safe rollback or explicit recovery instructions.
4. The lifecycle CLI with explicit flag-based selection —
   `--machine <id>` (full id or unambiguous git-style prefix)
   and `--blueprint <name>` (the blueprint's sole machine, failing with
   candidate ids when several exist): `list blueprints`,
   `list machines`, `create --blueprint`, `start` (full
   reconciliation — baseline, state, backend identity, and
   re-verification of every referenced media hash), `stop`,
   `apply` (adopt blueprint edits into the baseline; drive-regenerating
   changes fail closed), `destroy`, `recreate` (same id), and
   `delete` (`--machine` for a machine, `--blueprint` for a
   machineless blueprint file).
   Runtime changes update the state only; machines stay running
   until explicitly stopped.
5. Existing single-machine commands (`type`, `run`, `keys`,
   `menu`, `wait`, `text`, `screenshot`, `hmp`) take the same
   `--machine`/`--blueprint` selection and resolve ownership through
   the record and state.
6. Published JSON Schemas for the blueprint, machine record, state,
   and media definition document types.
7. `examples/` updated to the implemented shapes
   (`examples/blueprints/`, an explicit `create --blueprint` step in its
   README) — or the docs corrected where implementation proves
   the planned format wrong.

Done when: the FreeDOS install (still recipe-driven) runs against
a machine created from the example blueprint in a clean home;
`destroy` + `create` regenerates the materialization from blueprint
and media alone; a process killed mid-operation is detected and
recovered per the instance model; the old layout is gone from
code, tests, and docs.

### Milestone 4 — The property registry

All of [docs/property-registry.md](docs/property-registry.md),
landed ahead of the scripting language because script inputs bind
to it. Small and independently useful.

Deliverables:

1. `properties.json` as a flat user-owned map of dotted names to
   strings or `{"secret": true}` markers, with name validation
   and canonical atomic writes.
2. `reliquary property list/get/set/unset`: secret values held
   only in the host's protected credential store (scoped by home
   and property name), set via no-echo prompt, never revealed by
   `list`/`get`; kind changes require `unset` first.
3. The fail-safe update order (store credential before marker,
   remove marker before credential), with orphaned-credential
   reporting and cleanup guidance — never a plaintext fallback.

Done when: ordinary and secret properties round-trip through the
CLI with no secret material ever in the file, and interrupting an
update cannot produce a plaintext value or a marker whose
credential was reported bound but is absent.

### Milestone 5 — The scripting language

All of [docs/script-spec.md](docs/script-spec.md), completing the
documented design for DOS on QEMU: the FreeDOS install and
verification as `.rqs` scripts, and the retirement of `recipes/`
and the `install` command.

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
   `attach`/`detach` (updating the state, not the blueprint),
   stopped-only `stage`/`collect` with contained paths, and
   `start`/`stop`.
4. Inputs and response files: `text`/`media`/`secret` with
   `${name}` binding by the response → property → prompt
   precedence, kind mismatches and missing noninteractive values
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
7. `reliquary script <script_name> --machine/--blueprint` (preflight,
   embedded
   media installation, implicit create/start) and
   `reliquary check-script` (read-only, with optional machine
   and response binding for capability preflight).
8. `examples/scripts/freedos-plain-install.rqs` and `-verify.rqs`
   run end to end; `recipes/` and `install` are deleted.

Done when: the FreeDOS plain install and verification pass as
`.rqs` scripts from a clean home with no Python recipe left in
the tree, and transcripts honor the provenance and
secret-redaction contracts. At this point everything `docs/`
documents is implemented for DOS on QEMU.

### Milestone 6 — The backend adapter seam

Extract the adapter API from the now-complete QEMU implementation
— the only adapter with a full control plane set — so the seam is
defined by working code, not speculation.

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
3. VirtualBox in autodiscovery and the priority list; `recreate`
   as the sanctioned backend move, drives regenerating in native
   formats.

Done when: the FreeDOS install script runs unmodified on both
backends from the same blueprint (minus a pinned backend field).

### Milestone 8 — Machine mobility: clone, export, import

The durable-artifact exits, once two backends make them
meaningful. The open questions under "Decisions still needed"
(`export` mechanics, `import` scope) must be settled at the start
of this milestone.

Deliverables:

1. `clone`: a new machine record and UUID retaining the source's
   resolved blueprint snapshot, with the source's writable drive
   images copied — a snapshot of a machine, never a shared
   state or backend registration.
2. `export`: a stopped machine out to the backend's native
   management (or a media image out of one drive), independent
   and permanently outside reliquary's purview.
3. `import`: synthesize a blueprint from a native VM's configuration,
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

- `init` blueprint scaffolding and `fork-blueprint` (both fire-and-forget
  authoring conveniences).
- The virtio-serial carrier for the DOS agent and bounded
  `guest-file-*` operations (serial-to-virtio bootstrap,
  steps 3–5).
- Win9x/WinNT platform workflows, and with them GUI installer
  scripting: needle-like assets, script-level pointer verbs (on
  the milestone-10 input primitives), and image-match `wait`
  (see "Decisions still needed").
- VMware Workstation and Hyper-V adapters.
- Media commands beyond `fetch` (list, verify, remove).
- A `pytest-reliquary` plugin (per AGENTS.md prior art).

## Design principles

- **Machines are ephemeral.** A machine exists to run its scripted
  task; disk images are the durable artifact. Prefer designs that
  make machines cheap to recreate over designs that make them
  precious — no feature should exist solely to nurse a long-lived
  machine.
- **One script, one target.** Each OS version and edition gets one
  install script. Immutable text, media, and secret inputs supply
  that target's run-specific data from responses, user properties, or
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
- vvfat staging and write-back as an independent file-exchange
  mechanism.

It has no guest prerequisite and remains the DOS default and
fallback. It is not accurately modeled as a stream: output is a
sequence of screen snapshots, and keyboard input is independent of
that output. VGA text-memory inspection is QEMU-specific; other
backends implement the agentless display control plane with their native
input injection and screenshot capture, which for text readback
means pixel-level recognition — acceptable for fixed-font text
modes, and a per-backend implementation detail behind the same
control plane.

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
- **Script spec details** (the control-flow and response-file shape
  are decided — see "The scripting language" and
  docs/script-spec.md): the portable key-name vocabulary for
  `press`/`<key>` tokens, and whether literal input defaults are
  useful in addition to user-property bindings.
- **Cross-script reuse**: whether repeated behavior eventually
  justifies a constrained include mechanism. There is deliberately
  no handler-splicing macro in the initial language; real scripts
  must establish the need and a design that preserves local control
  flow and transcript provenance.
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
  whether `recreate`/`delete` per machine is enough.
- **`export` mechanics**: export has two targets — a media image
  (a single drive taken out of the machine as a standalone image
  file) and an entire machine (registered with the backend's
  native management: VirtualBox machine folder + registration,
  Hyper-V import/export format, `.vmx` directory for VMware,
  bare image + launch config for QEMU). Open: the exact CLI
  shape for the two, whether export offers format conversion,
  and whether a `media`-referenced drive blocks whole-machine
  export or is materialized into it.
- **`import` scope**: which backend config translates into the
  synthesized blueprint (memory, drives, controllers are clear;
  what of NICs and other devices the blueprint doesn't model yet), and
  whether untranslatable configuration fails the import or lands
  in `backend-settings`.
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
  need screenshot-based matching, for which os-autoinst's needle
  design is the reference (see AGENTS.md prior art): a reference
  image plus a JSON sidecar of areas — fuzzy `match` with a
  similarity threshold, `ocr` for text regions, `exclude` masks
  for dynamic content — selected by tag, optionally carrying a
  click point. Open: the needle-like asset format and where the
  assets live (beside scripts, shared like media definitions?);
  pointer input, which reliquary currently lacks end to end
  (machine blueprint pointing-device field, a control-plane input
  capability, and script verbs — match-and-click with the click
  point in the asset, following os-autoinst). The input seam
  should follow os-autoinst's two-layer event model: three
  portable primitives — pointer move (x, y), button press/release,
  key press/release — with clicks, drags, chords, and paced typing
  composed above them, and event pacing owned by the control
  plane. The primitives are exactly VNC's RFB input vocabulary
  (PointerEvent, KeyEvent), so a VNC control plane implements them
  with no translation, and QMP/VBoxManage/WMI input paths reduce
  to the same three. Synchronization concepts to adopt with them:
  act-then-confirm (an input step optionally asserting the screen
  changed), screen-stillness waits, and pointer hygiene (parking
  or restoring the cursor after clicks so it never perturbs
  matching). Also open: how `wait` grows an
  image-match form without weakening the text-first DOS path, and
  a host-side needle-cropping convenience (a CLI subcommand, never
  a service). Era note: DOS/9x-era setup GUIs are fixed-mode,
  fixed-font, animation-free — needle churn should be far below
  openQA's — and NT-era setup is largely keyboard-drivable, so
  keyboard-first remains the preferred path where it works.
  Throughout, os-autoinst is a **concept reference only** — its
  designs are studied and reimplemented, never its code (see
  AGENTS.md prior art for the licensing boundary).
- **Media commands beyond `fetch`**: whether the CLI grows verbs
  such as list, verify, and remove, and whether each can select
  embedded definitions through `--script` when needed.
- **Hyper-V agentless screen strategy**: whether WMI thumbnail/
  keyboard automation is good enough for installer scripting or
  Hyper-V machines require the serial/agent control planes from day one.
- **Concurrent machines**: per-machine exclusive locking is
  decided (docs/instance-model.md); still open is whether any
  home-wide limit applies to machines running at once (the
  per-machine lock and identity model suggests none).
- **Friendly machine aliases**: machine identity is the UUID
  addressed by unambiguous prefix (decided, git-style); still
  open is whether listings and selectors additionally offer
  docker-style generated word aliases for memorability, or
  whether blueprint-based selection makes them unnecessary.
- The exact initial `guest-exec` subset, including argument and
  environment support, capture modes, output limits, timeouts, and
  legacy-OS deviations.
- Which bounded `guest-file-*` operations follow execution,
  including file consistency and atomic replacement semantics.
- Whether a separate plain serial-console control plane remains useful
  once the QGA-compatible serial listener exists.
