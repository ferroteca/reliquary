# AGENTS.md — repository guidance

This is the canonical, agent-agnostic guidance for working on Reliquary. Human usage documentation belongs
in [README.md](README.md); keep this file focused on repository structure, engineering constraints, verification, and
maintenance context.

## Project state and layout

Reliquary is an OS installation scripter built on its own generic QEMU
runner, with DOS as the default and currently only complete platform
workflow:

- `reliquary/` contains the library and CLI. `__init__.py` preserves the root import surface; `errors.py` owns the
  error taxonomy — `ReliquaryError` the root every deliberate error subclasses, with the run surface's
  `StaticError` (exit 2) / `PreflightError` (3) / `RunFailure` (4) / `RunCancelled` (5, a sibling of `RunFailure`,
  never a subclass) and the `exit_code` / `outcome` mapping both the CLI and the terminal event read; exit `1` is
  precisely a fault outside the taxonomy, `events.py` owns the run event stream — the `Event` envelope
  (`seq` / `time` / `elapsed` / `kind` plus the kind's own fields, flattened at serialization), the `EventStream`
  that records and renders as it goes (redacting every string through the run's secret set, ticking a live display
  without recording the tick), and `note()`, the emit-or-say-it-on-stderr helper media movement uses so a fetch
  outside a run is still honest; `progress.py` owns the renderings — `resolve_mode` (`auto` by stderr tty),
  `describe` (the one human line per event both human modes share), and the `pretty` / `plain` / `jsonl` renderers,
  with the output discipline enforced there: human modes render everything to stderr and leave stdout empty, `jsonl`
  owns stdout alone; `home.py` owns home and
  cache resolution, layout, and containment, plus the `Context` type every path-resolving function accepts (now also
  carrying the authored-asset selection — `HOME_ASSETS`/`set_assets`), `assets.py` owns authored-asset residency: the
  resolution source seam (`HomeSource` = the home's canonical folders + codex seeding, the CLI default; `DirSource` =
  a `--assets <dir>` project root walked recursively by extension as the sole hermetic source), `source_for`, and the
  name-field-else-stem identity with its within-source conflict guard (`index_by_name`); the embedding API names its
  source or fails closed (no home/CWD default), and an `ObjectSource` of JSON-imported objects is the planned third
  source, `document.py` is the `.rlqb` parser (normative spec: `docs/spec/blueprint-model.md`) —
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
  `blueprint.py` is authoring-only — scaffolds (`new_blueprint`), writes a media declaration for a file already
  on disk (`add_media(name, file)`: computes the sha256, writes `blueprints/<name>.rlqb` locating the media at
  that path, copies nothing, refuses to overwrite — the supply seam for pinned-but-unlocated codex media, D41),
  and removes home blueprint files (`delete_blueprint` —
  fails closed while any machine of that blueprint exists), `resolve.py` builds the merged `(name, type)` resolution
  namespace from every `.rlqb` in the active source (`load_namespace` / `build_namespace`, cross-file collision
  detection), resolves a media by name (`resolve_media`), and lowers it to a nested fetch plan
  (`Download` / `LocalFile` / `Extract`), `acquire.py` executes that plan — `fetch_media(media, namespace, context,
  on_mismatch)` downloads (mirrors), extracts recursively, and sha-verifies into the one `cache/media/`
  cache, keyed by the name of the media each file is, and attaches a `local` payload in place. The cache is
  wholly regenerable — every payload arrived by download or extraction, so no verb asks where a file came from
  before reclaiming it and nothing records provenance (D41 deleted the identity ledger),
  `media.py` is acquisition-only — `fetch_media(name,
  context, on_mismatch)` and `list_media` over the namespace, plus the cache family — `clean_media(name=None)`
  (blunt, skipping running attachments; targeted when named) and `prune_media(dry_run=)` (the
  attachment closure: a container goes once its children are cached) — with no `delete_media`: removing a media
  is editing the `.rlqb` that declares it (D30), and no `add_media`: supplying a file is authoring a
  declaration, which is `blueprint.py`'s (D41),
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
  `cache/machines/<blueprint>-<n>/` — where the declared capabilities are checked against the built ones
  before any image work, so a blueprint naming an unwired drive `controller` or an unbuilt
  `control-planes` entry (only `agentless-display` exists) raises `NotImplementedError` naming the gap
  rather than recording a policy nothing can honor (P11) — plus lifecycle (`create` / `start` / `stop` / `destroy` /
  `recreate_machine` (destroy+create under the same id) / `apply_blueprint` (adopt blueprint edits into a
  stopped machine, reconciling absorbable diffs and failing closed on a changed size/materialize of an
  already-materialized media image) / `get_machine_dir` (the out-of-band door) /
  `list_machines` /
  `resolve_machine` / the exec-run family — `set_machine_var` /
  `get_machine_var` (the script→host scalar channel: a `machine.json`
  `variables` map under the op lock, cleared at `start` so a variable
  always reports the current boot, the `rlq`/`reliquary` key
  namespaces reserved; the setter's world-facing spelling is the
  script `set` verb, which is how the capability reaches the CLI
  without a command of its own) and `put_file` / `get_file` (in-band
  file exchange addressed in guest terms — P17 — over a
  directory-source drive, stopped-only, with a non-vvfat target and
  an unmapped letter failing closed naming the gap, P11; the letter
  map itself is `platform_dos.drive_letters`, built from declared
  facts alone — P10);
  ids are `<blueprint_name>-<machine_number>` with
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
  identity-verified QMP session by drive id, then persisted to state;
  `insert_media(slot, media=None, file=None)` takes exactly one of a
  declared media — fetched and verified — or `file=`, an anonymous
  `local`+`use` image mounted in place, mutable, unverified, never
  copied: U20's live-iteration transport)
  or stopped (persisted for the next start); `set_boot_order` is
  stopped-only (a launch-time firmware order); boot-order keys may name
  any declared drive; all three persist and survive stop/start),
  `lifecycle.py` owns QMP,
  QEMU processes, and host-side `qemu-img` helpers,
  `interaction.py` defines capability protocols, `interaction_agentless.py` contains the concrete agentless DOS
  adapter (prompt-based readiness and command completion), `machine.py` provides platform-neutral QMP interaction
  and diagnostics — keyboard input, VGA text/attribute scraping, cursor-menu selection, and screenshots,
  `platform_dos.py` owns DOS provisioning and facades plus the guest-address mapping (`drive_letters` —
  floppies to A:/B: by slot, hard disks C: onward, CD-ROMs after them, from Reliquary's own drive assignment
  and never from a guest; `split_address`). The
  `.rlqs` language is four layers: `script_nodes.py` (the lexer and its diagnostics),
  `script_parser.py` with `script_grammar.lark` (the typed tree, node signatures, `parse_script` /
  `load_script`), `script_validation.py` (the S-numbered static rules, each diagnostic citing its id),
  and `script_timing.py` (durations, and the timing plan resolved at parse time: every observation's
  effective timeout and the scope that supplied it; `format_plan` /
  `check_script` / `rlq check-script` report it without running).
  `binding.py` resolves declared script properties before a run —
  the flattened source order (explicit `--property`, blueprint
  parameter with its `{"property": ...}` redirect, `RELIQUARY_PROPERTY_*`
  environment with collision preflight, the properties file, the
  declared `default=` derivation, then an
  interactive ask), the text/media/secret kind rules, secret values
  pulled from the credential store, and `describe_sources` the dry
  twin that names each key's source for `check-script` without
  binding or prompting; declarations bind in topological order so a
  derivation's referents resolve first. `facts.py` owns the `rlq.*`
  run facts a derivation may reference (`rlq.host.username`
  login-normalized, `rlq.host.full-name`, `rlq.env.<NAME>` verbatim),
  each an unanswerable-when-empty host value. `bind_keys` binds the
  bare keys a media `location`/`sha256` references (no `property`
  node behind them) through the same order minus the derivation;
  `resolve.py` substitutes them (`location_property_keys` collects
  the closure, `resolve_media_plan(..., properties)` binds them),
  and `machines.create` / `apply_blueprint` bind at materialization
  so the state records the resolved location, never a `${key}` — a
  bound value that is itself a reference is refused (no chaining).
  `script_runner.py` executes that tree against
  cached machines — the phase graph, branching-wait and reactive dispatch over samples and episodes,
  the clocks the plan resolved — and wires `run-script <label>` (resolve via blueprint map,
  create-if-none, the machine-state header, static preflight of insert/eject/set-boot drive keys
  (a `ScriptPreflightError`, exit 3 — it is caught before the first guest input),
  property binding before the machine starts, secret redaction, and
  the run **returning its output** to the caller — no run-record
  persistence, milestone 9's return model; the `runs/` archive is
  async-backlog work, D36). Everything it reports goes through the
  one event stream, so no surface can report what the stream does not
  carry; it keeps the failure report's raw material as it goes (the
  pending condition or action, the route with its per-phase revisit
  counts, the last sample) and emits `failure` before the terminal
  event, naming the expired clock and its scope, the nearest miss on
  the last screen read, an automatic screenshot (suppressed for the
  rest of a run once a secret reaches the guest), and the next
  command to try. Ctrl-C installs a handler that sets a cancel flag
  the boundary checks read (`_check_clocks`, at statement starts and
  dispatch samples), so a cancellation ends the run at a boundary
  with an input delivery already in flight completed — never
  wherever the interrupt happened to land. `cli.py` owns command
  parsing, exit codes (`errors.exit_code` over one `ReliquaryError`
  arm), and the output discipline, and
  `__main__.py` preserves `python -m reliquary` execution.
- `pyproject.toml` packages `reliquary` as the `reliquary` command and includes the installable `reliquary_tests` test
  package.
- `reliquary_tests/` contains stdlib `unittest` coverage for core helpers, guest program runs, lifecycle ownership,
  media acquisition, blueprints, machines, and scripts.
- `README.md` is the human guide.
- `CHANGELOG.md` records release-facing changes.
- `planning/README.md` is the map of the maintainer-facing planning machinery, and the place to start. The
  directories are the classification, and they hold the **same three filenames** — `USE-CASES.md`,
  `ARCHITECTURE.md`, `FEATURES.md` — because they hold the same three artifacts in two states:
  `planning/proposed/` is argued but not pledged, and nothing is worked from there; `planning/pledged/` is
  approved but not yet delivered. Promotion is by *moving* a document or an entry, and the commit is the
  pledge record. The **planning root** holds what never moves and so has no state — the map, the vetting
  rule (`INTERFACES.md`), the adjudication record (`DECISIONS.md`, which spans open, pledged, refused and
  retired alike), and the task queue. Design sits with what it serves: `planning/proposed/design/` and
  `planning/pledged/design/` for a feature's own design, `planning/design/` for open design problems serving
  no single feature — the whole-system view itself (the seams model and the P-numbered principles) is root
  `ARCHITECTURE.md`. Once an interface ships, its normative spec moves to `docs/spec/` — current truth does not
  live under `planning/`.
- **There is no roadmap** (D42): `pledged/` says the project will do it and nothing about when, so the absence
  of order in `TASKS.md` holds equally for pledged features, the only binding order running inside a feature.
  **Features carry F-numbers** — the handle a dependency, commit or decision points at — which unlike U-, P- and
  D-numbers **evaporate on delivery**, retiring unreused, gaps being history rather than a promise. Designs take
  no number. **A feature must fit in one sprint**, here minutes to hours, so a pledged feature is far smaller
  than "milestone" suggests; the bound bites at the pledge. References between items run **down the lifecycle or
  sideways, never up**. Full rules: `planning/README.md`.
- **Search the record before a governed act.** Before drafting a proposal, pledging one, or changing a norm,
  search `planning/DECISIONS.md` for what bears on it and report what you found — including finding nothing.
  Anything recorded as killed, declined, or superseded is not revisited without new evidence, so re-raising one
  unknowingly wastes the argument; an entry that *supports* the change is worth citing. The trigger is the act,
  not a feeling of uncertainty — most entries carry a refusal, and what was declined is recorded nowhere else.
- `planning/TASKS.md` is the third work input queue, beside GitHub issues and `planning/proposed/`: small,
  **pre-approved** work — entering it is approving it — with no scheduled order, so anyone may pick up
  anything. Work that only makes sense as part of one pledged feature lives with that feature in
  `planning/pledged/FEATURES.md` instead. Small one-offs are really just issues, and work small and obvious
  enough needs no entry at all (housekeeping, D38). In theory every issue points to a use case or principle;
  small ones may be deemed obvious. **Writing anywhere under `planning/` is a governed act** (D43): one gate
  covers entering a document in `proposed/`, promoting one to `pledged/`, and entering work in `TASKS.md`,
  with the issue tracker the one open door. Authority is the owner alone today. **Agents do not add tasks on
  their own initiative and ask before editing that file at all**; the gate is at entry only, so anyone may pick
  up what is already there.
- `planning/INTERFACES.md` is the interface-change rule: how every interface-changing decision is weighed. The
  interface inventory it scopes over (CLI, embedding API, scripting language, and machine blueprints — media,
  source, and archive are components inside the blueprint — plus the script properties, recorded outputs, and
  the home layout) lives in root `ARCHITECTURE.md` "The interfaces", where the housekeeping lookup answers by
  checklist. The use cases, the architectural principles, and the specs are together the project's **vision** —
  the standing statement of what Reliquary is and is for. The numbered use cases — the decision
  surface that rule weighs against — live in root `USE-CASES.md` (implemented-only: every use case there is
  met by the code today, no placeholders). Use cases run through **three** locations, because pledging and
  delivery are different events: drafted in `planning/proposed/USE-CASES.md`, pledged in
  `planning/pledged/USE-CASES.md` (the move is the pledge), and current at the root on full delivery — one
  global U-sequence throughout, no placeholder left by either move. Every pledged item cites the use case — in
  force, pledged, or proposed — or the architectural principle that demands it: principles drive tasks and features
  just as use cases do. The architectural
  principles are itemized as P-numbers in root `ARCHITECTURE.md` — standing-only, every entry honored by the code
  today, with `planning/proposed/ARCHITECTURE.md` and `planning/pledged/ARCHITECTURE.md` the same three-state
  ladder; promotion to the root list is what *arms* a principle, since only there does a divergence become a
  bug. Decisions in `planning/DECISIONS.md` carry
  permanent D-numbers, generally support use cases or principles, and are the citation handle for design choices
  and code commits — overruled decisions sit in that file's Retired list.
- The worked FreeDOS example is the shipped codex itself (`reliquary/codex/`): the `freedos.rlqb` blueprint with
  its media and archive components, and the install and verify scripts. It is the live, tested copy — seeded into
  a user's home on first reference — so there is no second copy to keep synchronized.
- `docs/` describes the live situation. `docs/spec/` holds the
  **normative specifications** of every interface — the CLI, the
  embedding API, the scripting language, the blueprint model, media,
  properties, asset resolution, the instance model, the codex, and
  the answer-file server. A spec is the authority
  the implementation answers to, not a report on it: where a spec and
  the code disagree, the spec is right and the code has a bug, unless
  the spec is changed first through the interface-change rule. The
  rest of `docs/` is descriptive — user-facing references and guides,
  and a reference that contradicts a spec is the reference's bug.
  **The banner is the marker, the directory is shelving**: every
  spec declares its standing in its own banner, and every
  descriptive document names the norm it defers to. One norm is
  split across artifact kinds: the blueprint's structure is normed
  by the published schema and its semantics by
  `docs/spec/blueprint-model.md`, so the blueprint guide, field
  reference, and cookbook are descriptive `docs/`.
  Design lives under `planning/` instead: with its feature in
  `planning/proposed/design/` or `planning/pledged/design/`, or in
  `planning/design/` when it serves no single feature.
- **Machine-readable schemas ship inside the package**, at
  `reliquary/schemas/`, because code consumes them:
  `blueprint-schema-v1.json` (versioned v1 so editors can bind it
  today) and `machine-state.schema.json`. `docs/spec/` refers to
  them rather than holding them. Both must stay synchronized with the
  prose specs, **which are normative** — a schema captures only the
  structural subset JSON Schema can express, and schema validity
  never implies document validity. The shared valid/invalid
  conformance corpus (`reliquary_tests/fixtures/conformance/`,
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
Reliquary's primary interfaces to the world; the script properties, the run's returned output (the live
event stream, `--json` documents, exit codes — persistence dropped with D36), and the home layout are
world-facing contracts alongside them. Any decision that
changes one follows the rule in [planning/INTERFACES.md](planning/INTERFACES.md): requests triage by their impact on the
numbered use cases ([USE-CASES.md](USE-CASES.md)) — no impact or strong alignment is an easy approval, adding a new use case is more work but still
easy, and a change misaligned with the use cases must win the argument for amending the list itself, with
work starting only after the amendment lands — then the change is named across every surface it touches
and landed coherently on all of them. Where a docs/spec/ specification and planning/INTERFACES.md or
USE-CASES.md disagree, the principles and use cases govern; the design is realigned to them.

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

Authored-asset residency is a separate axis from the home (docs/spec/asset-resolution.md; `assets.py`). Blueprints
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
- `cache/media/` — every cached payload (`media_cache_dir`), keyed by media name, under the cache root; each
  file is named `<media-name>.<ext>`, which is the whole of its identity — no sidecar record (D41)
- `cache/machines/<name>-<n>/` — machine materializations (`machines_cache_dir`;
  parent via `cache_dir`), under the cache root, each with `machine.json` (the
  resolved state; while running its `vm` section carries the live VM identity,
  port, PID; and a `variables` map holding the machine variables a
  script `set`s, cleared on start — D36),
  `media/` (the machine's per-machine images and vvfat directories,
  named by media), `screenshots/` (where a script's `screenshot` verb
  and an automatic failure capture land, now that there is no run
  directory), and a `<backend>/` subdir
  (e.g. `qemu/qemu-stderr.log`). A run stores nothing here — it
  returns its output to the caller (D36); the `runs/` archive is
  async-backlog work.

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
`docs/blueprint-reference.md`), each naming a media
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
**episodes** a condition's consecutive holding samples form — docs/spec/script-spec.md, "Execution
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
conventions, handles) is `docs/spec/api.md`.

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
  docs/spec/cli.md): never adopt a design that would be
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
  the three gating jobs are itemized in proposed/FEATURES.md "Horizon" under
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

Milestone-9 guarantees needing the same care:

- every deliberate error subclasses `ReliquaryError`, and the four run-surface classes exit 2/3/4/5
- a run creates no `runs/` directory and writes nothing to the machine directory
- `--progress jsonl` puts the event stream on stdout and nothing else, terminal event last
- a human `--progress` mode leaves stdout empty
- a bound secret never reaches the event stream, and it suppresses automatic screenshots afterwards
- a cancellation ends at a boundary with an in-flight input delivered whole
- a machine variable is cleared by `start`
- a non-vvfat or unmapped in-band file target fails closed naming the gap

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
