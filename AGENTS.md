# AGENTS.md — repository guidance

This is the canonical, agent-agnostic guidance for working on Reliquary. Human usage documentation belongs
in [README.md](README.md); keep this file focused on repository structure, engineering constraints, verification, and
maintenance context.

## Project state and layout

Reliquary is an OS installation scripter built on its own generic QEMU
runner, with DOS as the default and currently only complete platform
workflow:

- `reliquary/` contains the library and CLI. `__init__.py` preserves the root import surface; `home.py` owns home and
  cache resolution, layout, and containment, plus the `Context` type every path-resolving function accepts (now also
  carrying the authored-asset selection — `HOME_ASSETS`/`set_assets`), `assets.py` owns authored-asset residency: the
  resolution source seam (`HomeSource` = the home's canonical folders + codex seeding, the CLI default; `DirSource` =
  a `--assets <dir>` project root walked recursively by extension as the sole hermetic source), `source_for`, and the
  name-field-else-stem identity with its within-source conflict guard (`index_by_name`); the embedding API names its
  source or fails closed (no home/CWD default), and an `ObjectSource` of JSON-imported objects is the planned third
  source, `document.py` is the `.rlqb` parser (normative spec: `planning/design/blueprint-model.md`) —
  `parse_document` / `load_document` build a `Document` of `machines` / `media` from a root array of specs (a lone
  spec object is sugar for the array of one; `type` defaults to `media`, so an untyped object is a media and the
  media branch's unknown-field error carries a did-you-mean when machine vocabulary appears), dataclasses `Machine`,
  `Media`, `MachineDrive`, `Location`, `Reference`, `Deferred` (a value still carrying `${…}` references, finished at
  resolution — validation is two-phase, shape here and value at resolve); `children` desugars to
  child-declares-parent containment, names are explicit or content-derived under the media-name charter (repaired
  with a `BlueprintWarning`, failing closed when it cannot be), identity is `(name, type)` colliding
  case-insensitively, and the reference grammar is closed at two productions — the character class screens, the
  productions decide — refusing references in identity/graph positions and the closed vocabularies; it validates the
  full field reference (`platform`, `backend`, `memory`, `cpus`,
  `drives` — a media name, `null`, `{media, controller, enabled}`, or an inline media (the anonymous blank included) —
  `boot`, `name` (the id-safe identity, not a
  display label), `description`, `scripts`, `control-planes`, `backend-settings`, `parameters`),
  `blueprint.py` is authoring-only — scaffolds (`new_blueprint`) and removes home blueprint files (`delete_blueprint` —
  fails closed while any machine of that blueprint exists), `resolve.py` builds the merged `(name, type)` resolution
  namespace from every `.rlqb` in the active source (`load_namespace` / `build_namespace`, cross-file collision
  detection), resolves a media by name (`resolve_media`), and lowers it to a nested fetch plan
  (`Download` / `LocalFile` / `Extract`), `acquire.py` executes that plan — `fetch_media(media, namespace, context,
  on_mismatch)` downloads (mirrors), extracts recursively, and sha-verifies into the one `cache/media/`
  cache, keyed by the name of the media each file is, recording provenance in `ledger.py`'s identity ledger
  (`refetchable` / `derived` / `supplied`, with a derived payload's `(parent-sha, path)` derivation key) and
  attaching a `local` payload in place, `media.py` is acquisition-only — `fetch_media(name,
  context, on_mismatch)` and `list_media` over the namespace, plus the cache family — `clean_media(name=None)`
  (blunt, sparing `supplied` and running attachments; targeted when named), `prune_media(dry_run=)` (the
  attachment closure: a container goes once its children are cached), and `add_media(name, file)` (the guarded
  door for payloads nothing can locate) — with no `delete_media`: removing a media is editing the `.rlqb` that
  declares it (D30),
  `properties.py` owns the user properties file — the line-based
  `<home>/user.properties` (`key = value`, `#` comments, dotted
  letter-initial keys with the `rlq`/`reliquary` namespaces reserved,
  values verbatim to end of line, a leading `@` naming a value kind:
  `@secret` the marker, `@@` a literal `@`), parsed whole before any
  edit so a malformed file is never partly rewritten (`PropertiesError`
  naming path and line), edited surgically line by line — comments,
  blanks, and ordering preserved — and written atomically;
  `get_property` / `set_property` / `unset_property` /
  `list_properties(prefix)` are the verbs, a secret reading as the
  marker `{"secret": True}` and never a value; every verb takes
  `properties_file=` (CLI `--properties`, env `RELIQUARY_PROPERTIES`),
  which *replaces* the home's file rather than layering over it.
  `credentials.py` owns the host credential store — a three-method
  provider seam (`keyring`'s own shape, so the default provider is
  `keyring` and a test double is three functions; `_set_provider`
  installs one, which is how the suite never touches the real store),
  secrets scoped by the selected properties file's absolute path, and
  no plaintext fallback anywhere: an absent or unusable store raises
  `CredentialError`. Updates are fail-safe ordered — credential before
  marker, marker before credential — so the only recoverable leftover
  is an orphaned credential, which an ordinary set refuses to
  overwrite and `unset_property` clears. Property *binding* into a run
  (the layered sources, the derivation, the runtime secret rules) is
  the rest of milestone 8,
  `library.py` owns the codex — the built-in seed library
  (`reliquary/codex/` package data: seed-on-first-reference copy-out, never overwriting home files;
  `seed_blueprint`/`seed_script` copy a closure by default or the single file with `only=`; `search_blueprints`
  matches codex + home blueprints and reports provenance `yes`/`seeded`/`user`), `machines.py` owns machine materialization under
  `cache/machines/<blueprint>-<n>/` plus lifecycle (`create` / `start` / `stop` / `destroy` /
  `recreate_machine` (destroy+create under the same id) / `apply_blueprint` (adopt blueprint edits into a
  stopped machine, reconciling absorbable diffs and failing closed on a changed size/materialize of an
  already-materialized media image) / `get_machine_dir` (the out-of-band door) /
  `list_machines` /
  `resolve_machine`; ids are `<blueprint_name>-<machine_number>` with
  lowest-free reuse; a per-blueprint allocation lock serializes
  numbering and an exclusive per-machine operation lock
  (`.locks/<id>.op.lock`) serializes every mutating op; each carries an
  operation generation and writes the transitional phases
  `creating` / `stopping` / `destroying`, so an interrupted operation is
  reconciled at the next op — `stopping` completes, `creating` /
  `destroying` roll forward to removal) and persistent machine-state mutations
  (`insert_media` / `eject_media` / `set_boot_order` /
  `mark_stopped` — insert/eject are floppy and cdrom only and work
  running-or-stopped (a running change is applied live over the
  identity-verified QMP session by drive id, then persisted to state)
  or stopped (persisted for the next start); `set_boot_order` is
  stopped-only (a launch-time firmware order); boot-order keys may name
  any declared drive; all three persist and survive stop/start),
  `lifecycle.py` owns QMP,
  QEMU processes, and host-side `qemu-img` helpers,
  `interaction.py` defines capability protocols, `interaction_agentless.py` contains the concrete agentless DOS
  adapter (prompt-based readiness and command completion), `machine.py` provides platform-neutral QMP interaction
  and diagnostics — keyboard input, VGA text/attribute scraping, cursor-menu selection, and screenshots,
  `platform_dos.py` owns DOS provisioning and facades. The
  `.rlqs` language is four layers: `script_nodes.py` (the lexer and its diagnostics),
  `script_parser.py` with `script_grammar.lark` (the typed tree, node signatures, `parse_script` /
  `load_script`), `script_validation.py` (the S-numbered static rules, each diagnostic citing its id),
  and `script_timing.py` (durations, and the timing plan resolved at parse time: every observation's
  effective timeout and the scope that supplied it; `format_plan` /
  `check_script` / `rlq check-script` report it without running).
  `script_runner.py` executes that tree against
  cached machines — the phase graph, branching-wait and reactive dispatch over samples and episodes,
  the clocks the plan resolved — and wires `run-script <label>` (resolve via blueprint map,
  create-if-none, the machine-state header, static preflight of insert/eject/set-boot drive keys, run
  records under `cache/machines/<blueprint>-<n>/runs/`), `cli.py` owns command parsing, and
  `__main__.py` preserves `python -m reliquary` execution.
- `pyproject.toml` packages `reliquary` as the `reliquary` command and includes the installable `reliquary_tests` test
  package.
- `reliquary_tests/` contains stdlib `unittest` coverage for core helpers, guest program runs, lifecycle ownership,
  media acquisition, blueprints, machines, and scripts.
- `README.md` is the human guide.
- `CHANGELOG.md` records release-facing changes.
- `planning/ROADMAP.md` contains maintainer-facing design and roadmap for planned interfaces and architecture. The
  flow runs one way: the roadmap flows from the use cases, and `planning/TASKS.md` flows from the roadmap and from
  issues — the GitHub tracker, with the TASKS.md backlog the parking place for non-GitHub issues. A task is either
  scheduled for the sprint or backlogged, and a milestone item is picked up by translating it into a sprint
  tasklist; small one-offs are issues, and a small obvious needed fix goes directly to tasks. In theory every
  issue points to a use case or principle; small ones may be deemed obvious.
- `planning/INTERFACES.md` is the governing document for Reliquary's world-facing interfaces: it names the interface
  inventory (CLI, embedding API, scripting language, and machine blueprints — media, source, and archive are
  components inside the blueprint — plus the
  script properties, recorded outputs, and the home layout) and the
  vetting rule every interface-changing decision must follow. The numbered use cases — the decision
  surface that rule weighs against — live in root `USE-CASES.md` (implemented-only: every use case there is
  met by the code today, no placeholders); everything else is tracked in `planning/USE-CASE-PROPOSALS.md`, numbering from the
  same global U-sequence and moving over when delivered (scheduling in the roadmap is acceptance; delivery
  makes it current). Every roadmap item cites the use case — in force or proposed — or the governing principle
  that demands it: principles drive tasks and roadmap items just as use cases do. The governing
  principles are itemized as P-numbers in root `PRINCIPLES.md` — standing-only, every entry honored by the code
  today (proposed changes in
  `planning/PRINCIPLE-PROPOSALS.md`, same lifecycle); decisions in `planning/DECISIONS.md` carry
  permanent D-numbers, generally support use cases or principles, and are the citation handle for design choices
  and code commits — overruled decisions sit in that file's Retired list.
- `planning/examples/` contains a complete FreeDOS example: a composed `.rlqb` blueprint (the machine plus its media and
  archive components) and scripts, the install script inserting the LiveCD media the blueprint carries. Its README
  carries the status note. Keep the examples synchronized with `planning/design/` when the formats change.
- `docs/` holds user-facing documentation for implemented features
  (CLI reference, Python API reference, blueprint guide, DOS
  automation). Design documents
  and planned interfaces live in `planning/design/` — the directory
  is the classification; file names carry no suffix. The one composed
  blueprint JSON Schema is published and packaged at
  `reliquary/schemas/blueprint-schema-v1.json` (versioned v1 so
  editors can bind it today); the machine-state schema
  (`machine-state.schema.json`) sits beside its spec in
  `planning/design/`. Both must stay synchronized with the prose specs
  (which are normative); the shared valid/invalid conformance corpus
  (`reliquary_tests/fixtures/conformance/`,
  `test_conformance_corpus.py`) runs every fixture against both the
  parser and the schema so the two cannot drift. Placement rules
  are in `.agents/skills/documentation-rules.md`.

Keep these modules deep: add behavior to the module that owns its invariant, and introduce another module only when a
real interface or maintenance seam justifies it. The package root exposes the intended embedding surface but owns no
implementation.

## Required invariants

### No backward compatibility before 1.0

Reliquary is evolving rapidly and deliberately maintains **no backward compatibility of any kind** until a
GA 1.0 release: no spec/config format versioning or migration, no API aliasing, no
deprecated-name shims, no compatibility parsing. When an interface changes, change it coherently and
completely — update every caller, document, and test to the new shape and delete the old one. Do not add
transition affordances "to be safe"; stale artifacts (old machine blueprints, homes, embeddings) may simply fail
and users recreate them.

Through beta and the rest of pre-1.0 this softens in degree only: **some** effort not to break users may be
granted where it is warranted and cheap, but nothing is promised, an effort granted once creates no
expectation of the next, and a clean break remains the default. Any cushion is a deliberate exception —
the owner's call, recorded in the CHANGELOG — never a shim left to accumulate. Compatibility guarantees
proper are defined no earlier than 1.0.

### Interface changes are vetted

The CLI, the embedding API, the scripting language, and the machine blueprint (media, source, and archive
components included) are
Reliquary's primary interfaces to the world; the script properties, recorded outputs (run records,
transcripts), and the home layout are world-facing contracts alongside them. Any decision that
changes one follows the rule in [planning/INTERFACES.md](planning/INTERFACES.md): requests triage by their impact on the
numbered use cases ([USE-CASES.md](USE-CASES.md)) — no impact or strong alignment is an easy approval, adding a new use case is more work but still
easy, and a change misaligned with the use cases must win the argument for amending the list itself, with
work starting only after the amendment lands — then the change is named across every surface it touches
and landed coherently on all of them. Where planning/ROADMAP.md and planning/INTERFACES.md or USE-CASES.md disagree, the
principles and use cases govern; the roadmap is realigned to them.

### CLI–API parity

The CLI and the embedding API are two presentations of one semantic surface, and keeping them in sync is
extraordinarily important. Every command maps one-to-one onto a public API call with the same semantics;
nothing is CLI-only, and no public capability may be unreachable from the CLI — it is the fallback binding
for every language without a native one. A change to this surface lands on both presentations in the same
change, never deferred to a later pass.

### Platform selection

DOS is the compatibility default when no platform is specified. Platform-specific behavior must be selected through
the blueprint's `platform` field (or `--platform` where a command takes one), never inferred by inspecting an image or guest screen. The reusable machine
layer may remain platform-neutral, but provisioning, readiness, remote-task execution, and result collection belong to
platform workflows. Until a non-DOS workflow is complete and tested, it must raise `NotImplementedError` rather than
using DOS assumptions.

### Agentless operation

Agentless DOS operation is a permanent requirement. The DOS workflow must continue to work against a guest with no guest agent,
network driver, serial driver, or other cooperating software.

The current transport is:

- QMP `send-key` for input
- VGA text-memory scraping for output
- QEMU vvfat for bidirectional files
- prompt detection for command completion
- QMP `screendump` for screenshots

Never make a feature depend on guest cooperation. A future guest-agent transport may be optional, but agentless behavior
must remain the default and fallback.

### Home-directory containment

All persistent state belongs under the Reliquary home (`Documents/reliquary` by default, falling back to `~/reliquary`
when no Documents folder can be determined; overridden by `RELIQUARY_HOME`, `--home`, or `set_home()`). The
regenerable cache root defaults to `<home>/cache` but resolves independently — overridden by `RELIQUARY_CACHE_DIR`,
`--cache`, or `set_cache()` — so it can live outside the home entirely (e.g. off OneDrive-synced storage). Seeding
(`seed-blueprint` / `seed-script`; there is no `seed-media`) always targets `<home>/blueprints` /
`<home>/scripts`, never the cache root. Every function that resolves a path under the home or cache accepts a
`context=` parameter (`home.py`'s `Context`, exported from the package root): omit it (the common case) to use the
process-global default; pass a bare string as shorthand for `Context(home=that_string)`; pass a `Context(home=...,
cache=...)` instance to pin both independently and safely per call within one process. The CLI only ever drives the
process-global default via `--home`/`--cache` — scoped `Context` objects are an embedding-API-only capability.
`lifecycle.py`'s and `machine.py`'s own `home=` parameters are a different, narrower concept — an already-resolved
plain directory (sometimes a machine's own cache subdirectory standing in for one), not a `Context`; they were
deliberately left alone. Never write beside the module or into the source repository during normal use.

Authored-asset residency is a separate axis from the home (ROADMAP "Authored-asset resolution"; `assets.py`). Blueprints
(their media, source, and archive components included) and scripts resolve in one of two modes, carried on
`Context.assets` / the `set_assets` global:
**home mode** (`HOME_ASSETS` — the CLI default when `--assets` is absent) reads the home's canonical `blueprints/` /
`scripts/` folders and seeds from the codex on a miss; **dir mode** (`--assets <dir>`, API `assets=<dir>`)
walks that project root recursively by extension as the sole hermetic source — no home, no codex, no seeding. The
root **replaces** the home (there is no shadow and no fallback; `--assets-only` never existed here). The embedding API
has **no default source**: a bare `Context`/`None` that resolves a name with nothing configured fails closed, so
automation never picks up home assets or a stray CWD (CWD is not an asset default). A bare-string `context=` is the
home-mode shorthand. An asset's identity is its declared `name` (id-safe) else its filename stem; within-source
effective-name collisions are errors. Selection scoping: `--blueprint <name>` matches only machines whose recorded
`blueprint-source` equals this invocation's resolution (a sourceless machine matches by name alone). Seeding
(`seed-blueprint` / `seed-script`) is a home operation and still targets `<home>/blueprints` etc.,
never a project root or the cache.

Home layout. A machine is wholly its cache materialization — there is
no root-home machine model (the legacy root-home machine surface — a
root-level `drives/`, a root `machine.json`, a root `vm.json` — was
absorbed and deleted; the per-machine `machine.json` below is the new,
unrelated cache state file):

- `blueprints/` — composed blueprints, media components included (`blueprints_dir`)
- `scripts/` — automation scripts (`scripts_dir`)
- `cache/media/` — every cached payload (`media_cache_dir`), keyed by media name, under the cache root, with
  the identity ledger (`.ledger.json`) recording what each file is
- `cache/machines/<name>-<n>/` — machine materializations (`machines_cache_dir`;
  parent via `cache_dir`), under the cache root, each with `machine.json` (the
  resolved state; while running its `vm` section carries the live VM identity,
  port, PID), `media/` (the machine's per-machine images and vvfat directories,
  named by media), `runs/` (run records), and a `<backend>/` subdir
  (e.g. `qemu/qemu-stderr.log`)

### VM ownership

Never send a control command to a QMP server until its identity is verified.

`launch_owned_qemu()` assigns a readable QEMU name plus a fresh per-start `-uuid`,
and returns the verified identity `{port, name, uuid, pid}`; `machines.py`
persists it into the `vm` section of `machine.json`, atomically with `phase`
(lifecycle no longer owns a state file). Every later connection checks
`query-name` **and** `query-uuid` against
that record. The name alone must never authorize a command: same-numbered
machines of one blueprint in different homes share their readable name, so
only the uuid identifies the exact QEMU instance this home started.
Identity mismatches fail closed; in particular, `stop()` must never send
`quit` to an unrelated VM.

`Machine.qmp()` is the public raw-monitor seam. It yields the
identity-verified QMP session, whose `cmd()` and `hmp()` methods remain
available to callers. Interaction adapters receive a `Machine` and must use
this seam rather than opening QMP connections directly.

When `port=None`, `launch_owned_qemu()` selects an available local port. An explicit port must be free. Startup failure and timeout
paths must terminate the child so they cannot leave an untracked QEMU process.

The CLI resolves the active port from the `vm` section of the machine's `machine.json` (via `read_vm_state`, which
reads that section); `start_machine()` returns the port for callers to propagate explicitly.

### DOS boot and scripting

A machine's drives are declared in its blueprint (the field reference,
`planning/design/machine-blueprint-reference.md`), each naming a media
component; per-machine images are materialized into
`cache/machines/<id>/media/`, named for the media.
`machine_drive_args()` (`machines.py`) renders them from the machine
state: floppies first (slots 0–1, A: and B:), hard disks next (slots
0–3, the IDE bus), then cdroms placed on the IDE slots after the hard
disks; each removable drive carries a stable QMP `id=<key>` so a running
`insert`/`eject` can target it. An image path's extension declares the
format (`format_options()`): `*.img` / `*.iso` are pinned to
`format=raw` (avoiding QEMU's format-probing warning), any other
extension is handed to QEMU to identify; a directory-source media (its
`source` a directory, `materialize: use`) renders as a vvfat drive
(vvfat emulates no ISO9660, so a directory source on a cdrom is rejected
at resolution). Memory and boot order
resolve into the state at `create` (boot best-guess: the slot-0 floppy,
else the slot-0 hard disk, else the first cdrom).

`AgentlessGuestExec.wait_ready()` only waits out the boot process to a native DOS prompt, detected generically as a
bare prompt on the bottom-most non-blank screen row. Do not add special boot parameters for ordinary DOS commands. Drive changes, directory changes,
environment variables, and program invocations belong in `AgentlessGuestExec.execute()` scripting.

### Virtual FAT behavior

QEMU snapshots a vvfat staging directory when the drive is attached. Host changes require a stop/start cycle. Guest
writes should be read after QEMU stops so write-back has completed. A
directory-source media attaches its directory as vvfat (`hdd` as a vvfat
hard disk, `floppy` as a vvfat 1.44M FAT12 floppy).

### Script dispatch

The `.rlqs` runtime's semantics are defined over **samples** (discrete readings of the machine) and the
**episodes** a condition's consecutive holding samples form — planning/design/script-spec.md, "Execution
model". Preserve these when touching `script_runner.py`:

- Dispatch is single-threaded and run to completion: no sample is taken while a statement list executes, so
  a screen that appeared and vanished inside a handler action never happened.
- A fired handler is consumed for its episode and re-arms only after a sample at which its condition does
  not hold. This is what makes a persistent confirmation screen fire input exactly once per appearance.
- An observation's timeout can never expire before at least one sample has been taken for it: a timeout
  always means samples were taken and none satisfied the condition.
- Clocks are checked only at boundaries — statement starts and dispatch samples — and every bound comes
  from the parse-time plan, never re-derived here, so a failure can name the scope that supplied it.
- No QMP session is ever held while a statement list runs: QEMU's QMP server admits one client at a time,
  so every sample and every input verb opens its own identity-verified session.
- A sample whose QMP session is gone is the stopped observation: `_read` treats connect failures and
  lifecycle's wrapped "no longer reachable" `RuntimeError` as `machine=stopped` and calls `mark_stopped`
  (which clears the `vm` section and returns the machine to `ready`). Identity-mismatch `RuntimeError`s still
  fail closed.

## The embedding surface

The cached-machine model is the sole embedding surface: `machines.py`'s
flat verb-noun functions (`create_machine` / `start_machine` /
`stop_machine` / `destroy_machine` / `recreate_machine` /
`apply_blueprint` / `get_machine_dir` / `resolve_machine` / …) and the
script runtime (`script_runner.py`'s `run_script` / `check_script`). The
milestone-1 root-home runner surface — `workflows.py`'s
`Runner` / `MachineConfig` / `run_guest_program` / `run_task` / `start`,
the old root-home state files (a root `machine.json`, `drives/`,
`vm.json` — distinct from the per-machine cache `machine.json` this
model writes), and the legacy `drives.py` auto-discovery — was absorbed
into this model and deleted (no backward compatibility before 1.0). The user-facing reference is
`docs/api-reference.md`; the end-goal API design (settled twin names,
conventions, handles) is `planning/design/api.md`.

Doctrine to preserve:

- Reliquary attaches no meaning to guest program output —
  test-framework semantics (command-line flags, result parsing) belong
  to consuming projects. A CppUTest adapter that once lived here was
  removed to enforce that boundary; do not reintroduce
  framework-specific code.
- Refer to consumers only in the general instructional sense ("the
  caller", "consuming projects", generic usage examples) — never name
  specific downstream projects; the machine layer stays ignorant of who
  builds on it.
- The media layer (`media.py`, `library.py`) and the script runtime
  (`script_runner.py`) are in-repo consumers of this surface and must
  drive it only through the same public interfaces available to
  external callers.
- The project is pre-release; prefer a coherent interface over
  compatibility shims when its architecture changes. The embedding API
  expects native bindings beyond Python (planning/INTERFACES.md;
  planning/ROADMAP.md "The CLI"): never adopt a design that would be
  difficult to express in a common binding language such as C or Java,
  and hold the CLI to the same constraint as the fallback binding for
  unbound languages — never make it difficult to drive from a program.

## Dependencies and style

- Runtime dependencies are welcome when they pull their weight; declare
  them under `[project].dependencies` in `pyproject.toml`. Prefer the
  stdlib only when it serves the need equally well.
- Pillow is the image library: screenshot conversion uses it, and the
  planned landmark assets (decode normalization, pixel comparison, PNG
  text chunks) build on it rather than on hand-written encoders.
- Support Python 3.9 and newer.
- **Windows is the delivered host platform.** It is the only one
  developed on, tested on, and claimed in the packaging classifiers.
  Write host code portably — the paths for other hosts exist and
  should stay correct (the Documents lookup, the credential-store
  backends) — but they are *unexercised*, so never state or imply
  support the project has not tested. Under P11 an untested platform
  is an unclaimed capability, not a quiet promise. Claiming another
  host means running the suite there, in CI or on real hardware —
  the three gating jobs are itemized in ROADMAP "Horizon" under
  host portability (U18 is the drafted case for reaching one from
  here).
- Keep lines near 79 columns and match existing formatting.
- Prefer small public interfaces with lifecycle complexity kept behind them.
- Preserve useful exception context and actionable diagnostics.

## Licensing

The project is BSD-3-Clause and follows REUSE conventions. The name
**Reliquary** is reserved to Paul Galbraith under [TRADEMARKS.md](TRADEMARKS.md);
do not weaken or contradict that policy in docs or packaging metadata.

Every new file authored for the project by Paul needs:

```text
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
```

Use the appropriate comment syntax for the file type. Files that cannot or should not carry headers must be covered by
`REUSE.toml`.

External contributors retain copyright in accepted contributions and license them under BSD-3-Clause. Their new files
must use accurate contributor copyright notices rather than attributing their work to Paul. Keep the human submission
terms in `CONTRIBUTING.md` synchronized with this policy.

## Development environment

Use the project-local `.venv`; do not install development tools globally.

On Windows:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --group dev
python -m pip install -e .
```

The `dev` dependency group contains repository tooling such as the `build`
frontend. Runtime dependencies remain under `[project].dependencies`.

## Required checks

Run checks with the project virtual environment.

```powershell
$pythonFiles = (Get-ChildItem reliquary,reliquary_tests -Filter *.py).FullName
.venv\Scripts\python.exe -m py_compile $pythonFiles
.venv\Scripts\python.exe -m unittest -v reliquary_tests
.venv\Scripts\python.exe -m build
```

`python -m build` builds an sdist and then a wheel from that sdist, which checks that the source archive is complete.
After packaging metadata changes, inspect `PKG-INFO` for at least the name, version, Python requirement, runtime
dependencies, and the presence of the `reliquary_tests` package in both built artifacts. For release-facing packaging
changes, install the wheel into a clean environment, change to a directory outside the source tree, and run
`python -m unittest -v reliquary_tests`. Downstream packagers should be able to run the same command against both their
unpacked source package and installed artifact.

Run `git diff --check` before handing work back.

Hands-on tests require QEMU. Use `--home` with a scratch or deliberately reused test home rather than polluting the
default per-user home.

The FreeDOS install+verify QEMU integration test is opt-in (skipped in the
default suite; needs network for the LiveCD on a cold home):

```powershell
$env:RELIQUARY_INTEGRATION = "1"
# optional: reuse a home so cache/media survives reruns
# $env:RELIQUARY_INTEGRATION_HOME = "C:\Temp\reliquary-integration"
.venv\Scripts\python.exe -m unittest -v reliquary_tests.test_freedos_install_integration
```

## Test expectations

Lifecycle changes need focused tests, especially for failure paths. Preserve coverage for these guarantees:

- automatic ports are returned and recorded
- occupied explicit ports fail before launch
- identity mismatch terminates a just-started child
- identity mismatch never reaches `quit`
- a name match with a uuid mismatch is an identity mismatch
- a stop refused on identity mismatch leaves the machine phase `running`
- stale state produces clear diagnostics and cannot target another VM

Use stdlib `unittest` and `unittest.mock` unless a compelling reason justifies another dependency.

## Documentation maintenance

README.md is a human-facing guide to what Reliquary does, why it exists, and how to use it. Keep it explanatory and
task-oriented. Do not move agent instructions, implementation constraints, roadmap discussion, or maintenance notes into
it.
When Packer and Vagrant are mentioned together in prose, name Packer first and Vagrant second.

After changing commands, flags, paths, behavior, or Python interfaces, update README.md, CHANGELOG.md, and this file
wherever affected. CHANGELOG updates land under the unreleased section only: released history is never retroactively
edited — not even for stale paths or renamed concepts (the sole exception, minimal privacy/legal redaction, and the
full rule live in `.agents/skills/documentation-rules.md`). Validate documented CLI syntax with `reliquary --help` and
subcommand help.

## Architecture and prior art

Reliquary uses QEMU's published `qemu.qmp` library for protocol handling and implements the machine-lifecycle role
locally. QEMU's in-tree `QEMUMachine`
is not published independently; if that changes, reassess whether replacing local lifecycle code would reduce
maintenance without weakening ownership checks or the public interface.

QEMU's own functional tests validate the broad model of scripting a guest over QMP and asserting on observable state.
Reliquary adds the DOS-specific layer: keyboard conventions, VGA text scraping, prompt
completion, and vvfat staging.

SUSE's os-autoinst (the engine under openQA) is the closest prior art to Reliquary as a whole: it drives OS
installers by screen matching and key injection over QMP/VNC, with per-operation "consoles" (VNC, serial,
virtio-terminal, ssh) mirroring Reliquary's control planes, multiple backends (qemu, svirt, bare metal) mirroring the
adapter seam, command completion over serial via echoed marker strings, per-step screenshot records, and snapshot
"milestones" for resuming long installs. Use it as a **concept reference only** for control-plane and backend implementations — Reliquary learns from its
designs (the input event model, needle area types, console seams), never from its code: it is GPL-2.0-or-later, so no
code, needles, or test modules may ever be ported or closely translated into this BSD-3-Clause project. Study the
documentation and the ideas; reimplement from scratch. Deliberate divergences to preserve: VGA text scraping instead of image needles for
text-mode guests, authored step documents instead of Perl test modules, and a local ephemeral-machine tool instead of
a testing service (scheduler, workers, and web UI are permanently out of scope).

Espressif's `pytest-embedded-qemu` is useful prior art for a future
`pytest-reliquary` plugin: host pytest orchestration around a native guest test framework. It is not directly reusable
because it assumes Espressif targets, serial output, and Unity result grammar.
