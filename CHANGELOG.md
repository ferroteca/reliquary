<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Changelog

All notable changes to Reliquary are documented here. The format is based
on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 0.1.0.dev2 (unreleased)

### Added

- Published the machine-state JSON Schema
  (`planning/design/machine-state.schema.json`) for
  `reliquary-machine.json`, alongside the blueprint and
  media-definition schemas. A shared valid/invalid conformance corpus
  (`reliquary_tests/fixtures/conformance/`) now runs every fixture
  against both the parser and the schema so the two cannot drift
  (schema checks use `jsonschema`, a dev dependency, and skip when it
  or the repo schemas are absent).
- Authored-asset residency: a single global `--assets <dir>` flag
  (API `assets=`) selects where blueprints, media definitions, and
  scripts resolve from. Without it, **home mode** resolves from the
  home's canonical `blueprints/` / `media/` / `scripts/` folders and
  seeds missing names from the codex (the human-CLI convenience).
  With `--assets <dir>`, **dir mode** walks that project root
  recursively by extension as the **sole**, hermetic source — no
  home, no codex, no seeding — for reproducible automation. The
  embedding API has no default source and fails closed until one is
  named, so automation never silently picks up home assets or the
  current directory. `list-blueprints` / `list-scripts` gained API
  twins (`list_blueprints` / `list_scripts`).
- `--blueprint <name>` selection is scoped to the invocation's asset
  resolution: it matches only machines whose recorded
  `blueprint-source` equals the blueprint this invocation resolves,
  so same-named blueprints in different projects never select — and
  `apply` never adopts — each other's machines.
- The cache root (`cache/downloads/`, `cache/media/`,
  `cache/machines/`) resolves independently of the Reliquary home:
  `RELIQUARY_CACHE_DIR`, `--cache`, and `set_cache()` mirror
  `RELIQUARY_HOME` / `--home` / `set_home()`, defaulting to
  `<home>/cache`. Seeding (`seed-blueprint` / `seed-media` /
  `seed-script`) is unaffected — it always targets
  `<home>/blueprints` / `<home>/media` / `<home>/scripts`.
- `Context(home=None, cache=None)`, exported from the package
  root: every function that resolves a path under the home or
  cache now accepts a `context=` parameter (replacing the former
  `home=`). Omitting it uses the process-global default, same as
  before; a bare string is sugar for `Context(home=that_string)`;
  a `Context` instance pins home and cache explicitly, safe to
  vary per call within one embedding process. The CLI only ever
  drives the process-global default via `--home`/`--cache` — scoped
  contexts are an embedding-API-only capability.
- Packaging metadata now declares the project homepage
  (`https://github.com/ferroteca/reliquary`) so PyPI can link to
  the repository.
- ROADMAP milestone 5 is complete: `.rlqs` scripts can declare a
  run-scoped HTTP server for installer answer files, serve named
  inline or script-relative `from=` content, start selected or
  redefined content at `http start`, use the reserved
  `rlq.http.ip` / `rlq.http.port` / `rlq.http.url` bindings, and
  rely on explicit or implied `http stop` teardown.
- Built-in OpenBSD 7.9 amd64 codex assets: an
  `openbsd-7.9-amd64` blueprint, install ISO media definition, and
  install script using OpenBSD autoinstall over the run-scoped HTTP
  server.
- Machine blueprints are now validated against the full field
  reference: `backend`, `cpus`, per-drive `controller`, `base`
  (with `difference`/`duplicate`), `hostdir`, `enabled`,
  `control-planes`, `backend-settings`, and `parameters` join the
  parser, each failing closed and naming the problem. A `cdrom`
  drive accepts only a `media` reference or an empty slot (`size`,
  `base`, and `hostdir` are rejected on optical media); state-only
  fields (`blueprint-digest`, `blueprint-source`, `backend-id`,
  `id`) are rejected in a blueprint by name. Materialization of
  `base`/`hostdir` drives and backend capability checks ride later
  milestone-6 work.
- Media definitions accept the definition-level annotation fields
  `description`, `notes`, and `redistributable-under` (both the
  item and archive forms).
- `create-machine` materializes `base` drives (a differencing qcow2
  backed by the base image, or a full `duplicate` copy) and
  `hostdir` drives (a resolved host directory served over vvfat),
  resolves platform defaults (`memory`, `cpus`, `control-planes`)
  into the machine state, and records the machine's provenance —
  `blueprint-source` (the resolved blueprint path), `blueprint-digest`
  (the resolved-snapshot baseline), and `backend-id`. Non-`ide`
  controllers fail closed pending the adapter seam.
- `insert-media` / `eject-media` now work on a **running** machine,
  not just a stopped one: the medium change is applied live over the
  machine's identity-verified QMP session (each removable drive is
  launched with a stable QMP id) and persisted to the machine state,
  so the change the guest sees and the recorded state stay one
  operation. On a stopped machine they remain a pure state edit
  present at the next `start`. `set-boot-order` stays stopped-only.
- The global `--json` flag prints a command's result as one JSON
  document on stdout — exactly what its API twin returns, with a void
  twin printing `{}` — while diagnostics stay on stderr and exit codes
  are unchanged. The stream-bearing `run-script` and `fetch-media`
  reject `--json`, naming `--progress jsonl` as their machine-readable
  form.
- `search-blueprints` / `search_blueprints()` searches codex and home
  blueprints, matching a term against name, description, and platform
  and reporting provenance (`yes` built-in, `seeded`, or `user`). The
  `seed-blueprint` / `seed-media` / `seed-script` commands gain
  `--only` (API `only=`) to copy just the named file without its
  closure.
- `recreate-machine` / `recreate_machine()` destroys a machine and
  recreates it under the same id (re-resolving the current
  blueprint), and `get-machine-dir` / `get_machine_dir()` prints a
  machine's cache directory as an absolute path — the out-of-band
  file-exchange door, valid in any phase.
- `apply-blueprint` / `apply_blueprint()` adopts the current
  blueprint into a stopped machine (and returns a script-diverged
  machine to its blueprint shape): memory, cpus, boot order, control
  planes, metadata, and added/removed/`media`/`hostdir`/empty drive
  changes are applied and the baseline digest re-recorded, while a
  changed `size` or `base` on an already-materialized image fails
  closed, naming `recreate-machine`.
- Machine lifecycle is crash-safe: every mutating operation takes an
  exclusive per-machine lock and carries an operation generation, and
  the transitional phases `creating` / `stopping` / `destroying` are
  reconciled at the next operation — an interrupted stop completes, an
  interrupted create or destroy rolls forward to removal, and a create
  that fails mid-materialization leaves nothing behind.

### Changed

- **One media cache, with an identity ledger.** Every cached payload
  now lives in `cache/media/`, keyed by the name of the media it is —
  a container is a media like any other, so `cache/archives/` retires
  along with `clean-archives` / `clean_archives()` and
  `archives_cache_dir()`. Beside the payloads, a ledger records what
  each cached file actually is: the sha256 observed when it was
  written, its provenance (`refetchable`, `derived`, `supplied`), the
  source it came from, and for a derived payload the
  `(parent-sha, path)` that produced it. That turns the pre-fetch
  identity check from a bare hash comparison into a diagnosis: a
  version bump and two projects sharing one media name now read
  differently, and a `supplied` payload is never deleted on a policy,
  because nothing could put it back.
- **The media cache commands.** `clean-media` reclaims what can be
  fetched or derived again, sparing `supplied` payloads and anything
  a running machine holds open; `clean-media <name>` evicts one
  deliberately. `prune-media [--dry-run]` keeps the **attachment
  closure** — what the active scope can still attach — and drops what
  only existed to produce it, so after an install the extracted ISO
  stays and the zip husk goes. `add-media <name> <file>` supplies a
  payload nothing can locate, verified against the blueprint's pin
  and recorded `supplied`. API twins throughout:
  `clean_media(name=None)`, `prune_media(dry_run=)`,
  `add_media(name, path)`.
- **Codex names are generic, never version-bound.** The codex is a
  launching point for real blueprints, so its entries are named for
  the system and the version lives inside the file as the source
  URL and hash: `freedos-1.4-plain` → `freedos`,
  `openbsd-7.9-amd64` → `openbsd`, with the media following
  (`freedos-1.4-livecd` → `freedos-livecd`,
  `openbsd-7.9-amd64-install` → `openbsd-installer`). Scripts are
  named for the flow they drive, never a release:
  `freedos-1.4-plain-install` → `freedos-install`,
  `freedos-1.4-verify` → `freedos-verify`,
  `openbsd-7.9-install` → `openbsd-install`. The `-plain` variant
  marker goes with them — the launching point *is* the plain
  install, and variants are the user's. A codex version bump is now
  a content update under an unchanged name, and machine ids shorten
  with their blueprints (`freedos-0`). Descriptions still name the
  release each entry is tested against.
- **Composed blueprint model.** Reliquary's two authored JSON formats
  fold into one blueprint `.rlqb`, whose root is an **array of specs**
  of two types — `machine` and `media` — with a lone spec object
  accepted as sugar for the array of one and a bare string as a media
  located by it. `type` defaults to `media`, so an untyped lone object
  is a media and the bare-root-machine reading is gone; a machine that
  forgets `"type": "machine"` gets a did-you-mean naming the machine
  vocabulary it used. There is no `source` or `archive` type: a source
  is a media's `location`, and an archive is just a media that other
  media name as their **parent** — the distinction was never a
  property of the artifact, only of the use.
  A machine's drive names a media, is `null` for a declared-but-empty
  removable slot, carries `{media, controller, enabled}`, or holds a
  media **written in place** — including the content-free blank
  `{"size": "20M"}`, the format's one anonymous citizen, which belongs
  to no namespace and is named for its slot when materialized. The old
  four-way drive content selector (`size` / `base` / `media` /
  `hostdir`) is gone.
  The media owns materialization: `materialize` ∈ `new` /
  `difference` / `copy` / `use` (default `use`), with `size`, one
  `location` field, conditional `sha256`, `read-only`, `extension`,
  and `children`. **Containment is parent/children**: any media may
  declare `children` (recursive batch sugar, a bare string being the
  path) or its `parent` from the child side, and every edge resolves
  to child-declares-parent.
  **Locations follow one law — strings are interpreted, objects are
  explicit**: every accepted string has exactly one object desugaring,
  which is the canonical form. Strings dispatch by scheme (a bare
  path, an http(s) URL, `${media:<name>/<path>}`, `${<key>}`), objects
  are `url` / `local` / `parent`+`path` / `property`, and a list of
  them is a mirror list tried in order. A scheme-shaped string that is
  not recognized is a parse error rather than a silently relative
  path, with a drive-letter exemption for `C:/...`.
  **`${...}` is the one reference syntax.** An unqualified reference
  interpolates anywhere a string is accepted (`\${` is the literal
  escape); a qualified `${media:...}` is whole-value. References are
  refused in identity and graph positions (`name`, `type`, `children`
  paths, drive keys) and in the closed vocabularies (`platform`,
  `backend`, `materialize`, `controller`, `control-planes`), whose
  published-schema enums stay plain so editors can complete them. The
  reference body is closed at two productions and carries no
  operators. Property binding itself arrives with script properties;
  until then a `${key}` parses and then fails closed naming
  properties.
  Validation is **two-phase**: shape at parse, value at resolution —
  which is where the `sha256`-required-once-remote rule now lands,
  since a referenced rung may resolve to a URL.
  Identity is `(name, type)` in one catalog. A name is explicit or
  derived from content (never from the slot or the `.rlqb` filename),
  repaired to the name charter with a warning that names both the
  derived name and its source, and failing closed when it cannot be.
  Names match case-sensitively and collide case-insensitively.
  Canonically identical specs of one identity coexist across files;
  differing ones collide naming both.
- **Machine directory reorganized.** `cache/machines/<id>/` now holds
  `machine.json` (was `reliquary-machine.json`) with the live-VM
  identity folded in as a `vm` section written atomically with
  `phase`; per-machine images move to `media/<media-name>.<ext>` (was
  `drives/<key>.<ext>`, now keyed by media so removable-slot swaps
  never clobber); and backend artifacts (QEMU's captured stderr) move
  into a `<backend>/` subdir. `lifecycle.py` no longer owns a state
  file — `launch_owned_qemu` returns the identity and `machines.py`
  persists it. Every cached payload now lives in the one
  `cache/media/`, keyed by the name of the media it is: a container is
  a media like any other, so there is no separate archive cache.
- The cache-reclaim command `clean-downloads` and its API twin
  `clean_downloads()` are renamed `clean-archives` / `clean_archives`,
  matching the `cache/archives/` cache they reclaim and the composed
  model's `archive` components. No backward-compatible alias (pre-beta).
- **One published schema.** The blueprint and media-definition JSON
  Schemas collapse into a single `reliquary/schemas/blueprint-schema-v1.json`
  (packaged, versioned v1 so editors can bind it), with a two-variant
  root — a machine requiring its declared `type`, a media accepting its
  absence. `.rlqm` retires, and with it the `media` asset kind and the
  `<home>/media` folder; media are specs inside a blueprint.
- `list-blueprints` (local listing) resolves through the active
  asset source: home mode lists the home's canonical `blueprints/`
  folder (recursively within it), and `--assets <dir>` lists the
  project root. It reports each blueprint's identity name alongside
  its full path.
- The blueprint `name` field is the id-safe **identity** (selection
  key, machine-id segment), overriding the filename stem when
  declared — not a display label; human prose belongs in
  `description`. `new-blueprint` no longer writes a `version`
  field — blueprints carry no version pre-beta.
- Media definitions now reject unknown keys (matching the schema's
  `additionalProperties: false` and the blueprint parser), so a
  mis-spelled field is a loud error instead of a silently ignored
  no-op.

### Fixed

- Usage/help text now names whichever entry point was actually
  invoked (`reliquary -h` says `usage: reliquary ...`, `rlq -h`
  says `usage: rlq ...`) instead of always hardcoding `rlq`.

### Removed

- The milestone-1 root-home machine model is gone, absorbed into the
  cached-machine model: `reliquary.Runner`, `MachineConfig`,
  `run_guest_program()`, `run_task()`, and the module-level `start()`
  (all of `workflows.py`), the root-home `machine.json` / `drives/` /
  `vm.json` layout and the `drives_dir()` path helper, the legacy
  filesystem drive auto-discovery (`drives.py`), and bare
  `rlq start-machine` / `rlq stop-machine` without a selector. Machines
  are created and driven through `create-machine` / `start-machine`
  (selector required) and `run-script`. No backward compatibility is
  kept before beta.
- The media-definition `redistributable-under` field is removed as
  overkill: Reliquary attaches no licensing metadata to a definition.
  Whether a codex definition may carry a `url` is now a maintainer
  discipline (the codex may only link to legally redistributable
  downloads), not a per-definition field.
- The dead `downloads_cache_dir` path helper (`Context` method and
  module twin) — a leftover pointer at the retired `cache/downloads/`.
  Its live counterpart `archives_cache_dir` (`cache/archives/`) is now
  exported from the package root in its place.
- `delete-media` / `delete_media()` and `seed-media` / `seed_media()`
  are removed outright. Media are components inside a `.rlqb`, so the
  first could only ever fail and the second could only ever do
  nothing; neither is kept as a shim. Removing a media means editing
  the blueprint that declares it, and seeding a blueprint brings its
  media along inside the same file. The noun in every media command
  is the media itself, never its owning file.

## 0.1.0.dev1 - 2026-07-22

### Added

- [TRADEMARKS.md](TRADEMARKS.md): the name **Reliquary** is owned by
  Paul Galbraith and is not licensed for forks or redistributions;
  the BSD-3-Clause grant covers the software only. Linked from
  README and CONTRIBUTING.
- `list-media` / `list_media()` lists media item names from the
  home library (or `--builtin` / `builtin=True` for the codex).
- `delete-media` / `delete_media(name)` removes a home media
  definition and refuses while any machine drive still references
  an item from that definition.
- `delete-blueprint` / `delete_blueprint(name)` removes a home
  blueprint file and refuses while any machine of it exists,
  naming the machine ids.
- Opt-in FreeDOS install+verify QEMU integration test
  (`reliquary_tests.test_freedos_install_integration`): set
  `RELIQUARY_INTEGRATION=1` (optional
  `RELIQUARY_INTEGRATION_HOME` to keep the media cache). Skipped
  under the default guarded unit suite.

### Fixed

- Script samples treat a guest power-off as `machine=stopped`
  when `lifecycle.qmp_session` raises its "no longer reachable"
  `RuntimeError` after clearing stale `vm.json`. Identity
  mismatches still fail closed. Unblocks FreeDOS install/verify
  shutdown after `fdapm poweroff`.

### Changed

- Milestone 4 (script-surface realignment) is complete: FreeDOS
  `run-script install` / `run-script verify` on
  `--blueprint freedos-1.4-plain` finish end to end, and
  `check-script` reports the timing plan.
- Documentation follows the redesigned script surface and the
  twin-name CLI: `planning/examples/README`, the script-spec and
  related design pages, and `docs/` quote `run-script`, the
  colon-free `machine` header, and `insert`/`eject`/`set-boot`
  rather than the superseded spellings.
- The old script surface and superseded CLI/API names are gone
  from the live tree. `reliquary_tests.test_old_surface_purge`
  fails the suite if they reappear in the package, tests, docs,
  README, AGENTS, examples, or shipped codex scripts.

- CLI/API twin-name identity (ROADMAP milestone 4, task 9): every
  command is its API twin's name, dash-separated. Lifecycle verbs are
  `create-machine` / `start-machine` / `stop-machine` /
  `destroy-machine`; listings are `list-machines` /
  `list-blueprints` / `list-scripts` (the nested `list …` form and
  its singular aliases are gone); media/cache commands include
  `fetch-media`, `clean-downloads`, `clean-media`, `insert-media`,
  `eject-media`, and `set-boot-order`; the guest-console family
  matches the script language (`type` raw / `enter` / `press` /
  `exec` / `select` / `screen`). Flags may appear before or after
  the command word without a parent-parser SUPPRESS twin.
  `--machine` takes the full `<blueprint>-<n>` id exactly — no
  prefix matching and no `--blueprint` + bare-number pair — and is
  mutually exclusive with `--blueprint`. The embedding API names
  match (`create_machine`, `start_machine`, `stop_machine`,
  `destroy_machine`).

### Added

- The redesigned script surface now has a typed parser:
  `reliquary/script_grammar.lark` mirrors the normative EBNF in
  `planning/design/script-spec.md`, and `reliquary.script_parser`
  builds the typed tree from it. Reliquary's own lexer feeds lark's
  LALR(1) parser through a custom lexer, so lexical diagnostics keep
  their authored wording — `lark` joins the runtime dependencies.
  The runtime still consumes the superseded surface; wiring it over
  is ROADMAP milestone 4's runner retarget.
- Static validation of the redesigned surface:
  `reliquary.script_validation` checks the legality rules the
  grammar deliberately does not carry, and each diagnostic names the
  construct and cites its rule id — the two script shapes and what
  belongs to each (S3, S10), unique phase names (S5), one condition
  per observation on a known channel of the right kind (S7), the
  branching `wait`'s shape and depth limit (S8), sequential-or-
  reactive phases (S9), and the terminating-statement rules (S11).
  Parsing a document now applies them.
- The script timing model: `reliquary.script_timing` resolves a
  script's whole timing plan at parse time — every observation's
  effective timeout and the scope that supplied it (innermost-wins
  over statement, branching `wait`, phase, header, and the built-in
  60s), each phase's per-activation budget, and the run's. A
  timing failure can therefore name the clock that expired and
  where it came from, and `check-script` can report the plan
  without running anything. Alongside it, the placement matrix's
  rejections now give their reason and cite S2 — `deadline` on a
  single observation would be a synonym for `timeout`, `timeout`
  on a handler belongs on its container, `stable` needs a match to
  hold — durations must be positive (S5), and a phased script
  whose reachable phase graph can cycle must declare a header
  `deadline` (S12), the diagnostic naming the route that closes
  the cycle.

- The script runtime executes the redesigned surface. `.rlqs` runs now
  walk the phase graph from `entry` to `finish`, dispatch branching
  `wait` blocks by declaration order, and run reactive phases' standing
  `always` handlers to completion — a fired handler consumed for its
  episode, re-arming only after a sample at which its condition no
  longer holds, so a persistent confirmation screen produces input once
  per appearance rather than on every sample. Every clock comes from the
  parse-time timing plan, so a timing failure names the clock that
  expired and the scope that supplied it, and observation timeouts,
  reactive intervals, per-activation phase budgets, and the run deadline
  are all enforced at sample and statement boundaries.
- The shipped scripts speak the redesigned surface: the built-in
  `freedos-1.4-plain-install` and `freedos-1.4-verify`, and the
  `planning/examples/` pair. The install script is the language's
  reference script. Seeding a script still brings the media
  definitions its `insert` statements name — the scan follows the
  `@name` spelling now, and a `$key` property reference names no
  static item to seed.
- Script sessions are identity-verified. Every sample and input verb
  opens its own QMP session through `Machine.qmp()`, so the runtime can
  no longer drive a VM it has not confirmed is the one this home
  started, and no session is held while a handler body runs.
- `check_script()` / `rlq check-script` report a script's resolved
  timing plan without running it: each observation's effective
  timeout and source scope, phase budgets, and the run deadline.
  The check is read-only (no seeding, no machine create). With a
  machine selector it also preflights media slots. Static errors
  exit 2.
- `press` key names are statically checked against the script
  language's closed portable vocabulary (S14). Unknown names, bare
  printable characters, and malformed chords now fail before a
  machine starts; chords such as `ctrl+c` remain valid.

### Removed

- The milestone-one script parser (`reliquary.script`) is gone, with the
  surface it parsed: `state`/`->`/`done`/`expect`, colon headers, comma
  modifiers, the `regex` keyword, bare `stopped`, `<key>` tokens inside
  `type`, and the `boot` verb (now `set-boot`). `parse_script` and
  `load_script` live in `reliquary.script_parser` and speak the new
  surface; the `State` and `ExpectBranch` exports are replaced by
  `Phase`, `Handler`, and `Property`. Scripts written for the old
  surface do not parse — rewrite them; there is no bridge.
- `ScriptRun.final_state` is `ScriptRun.final_phase`, and
  `rlq run-script` prints `final script phase:`.
- Scripts no longer carry embedded JSON. The `media <label> { ... }`
  block is deleted from the language, along with the planned
  `landmark <name> { ... }` block, the install-on-first-run model
  they implied, and `fetch-media --script`. Media definitions
  (`.rlqm`) and landmark declarations (`.rlql`) are authored files
  of their own, resolved beside the script and referenced by
  `@name`. A script that contains a `media` block no longer parses;
  move the definition into its own file beside the script. The
  parser's `EmbeddedMedia` model and the `reliquary.EmbeddedMedia`
  export are gone. Rationale and what was weighed:
  `planning/DECISIONS.md`.

### Changed

- Screenshot conversion uses Pillow in place of a hand-written PNG
  encoder and PPM header parser, so `pillow` joins the runtime
  dependencies. It also underpins the planned landmark image assets:
  decode normalization, pixel comparison, and PNG text chunks for
  capture provenance.
- `rlq list-machines` and `rlq list-blueprints` report an explicit
  `(no ...)` message on an empty result instead of a column header
  over zero rows, matching `list-scripts`, which already did.
  (`#5`)
- `rlq list-scripts --blueprint <name>` heads its first column
  `LABEL`, naming what it lists: the blueprint scripts-map labels used
  as `run-script` verbs. The bare `rlq list-scripts` listing keeps
  `NAME`, which is what it lists: script file stems.
- Scrubbed private project-history references from release-facing
  documentation and package metadata.
- Removed obsolete references to a superseded installation abstraction;
  built-in blueprints, media definitions, and scripts are the documented
  sharing model.
- Reinstated the released 0.1.0.dev0 section of this changelog to its
  exact release-time text — prior-project history included; it is
  real history. Released changelog history is append-only from here
  on: it is never retroactively edited, with minimal privacy/legal
  redaction the sole exception (the rule lives in
  `.agents/skills/documentation-rules.md`).

## 0.1.0.dev0 - 2026-07-20

The relict project — the agentless QEMU guest automation harness Reliquary
was built on — has been folded into Reliquary. Its modules now live in the
`reliquary` package (its drive-inventory module renamed to `drives.py`), its
CLI commands are `reliquary` subcommands alongside `install`, and its home,
`RELICT_HOME`/`RELICT_QEMU_HOME` environment variables, and default
`Documents/relict` directory are replaced by the Reliquary equivalents
(`RELIQUARY_HOME`, `RELIQUARY_QEMU_HOME`, `Documents/reliquary`). The notes
below merge both projects' unreleased histories with the relict entries
renamed accordingly.

### Recipe layer

Initial scaffold: package structure, CLI stub, and recipe module convention.

The planned `.rlqs` scripting language now separates linear scripts
from explicit state machines, uses run-to-completion reactive states,
and adds immutable text, media, and secret inputs bound from JSON
responses, a home-wide user property registry, or interactive prompts.
Ordinary reusable values live in `properties.json`; passwords and
product keys can use secret markers backed by the host credential
store, and script declarations bind them with `property:`. Scripts may
also embed the same JSON media-definition objects used by the shared
library; after preflight, running a script installs missing definitions
into `media/` without overwriting or updating existing files, while
verified artifacts continue to use shared caches. Console input is
expressed with `enter` rather than a separate `run` verb; guest reboot
remains console or menu input, while host power cycling is the explicit
`stop`/`start` pair. Timing, matching, preflight, transcript, and
offline file-exchange semantics are specified consistently ahead of
implementation.

Added the `freedos-plain` recipe's preparation steps: the FreeDOS 1.4
LiveCD ISO is downloaded into the Reliquary home (the distribution
zip is deleted after extraction) and SHA-256 verified on every run,
and
a 20 MiB dynamically allocated qcow2 (v3) target disk is created. The
`reliquary install <recipe>` CLI command runs a recipe by name, and
`--display` (the `display` recipe parameter) requests a visible QEMU
window for a recipe's guest steps.

The recipe now extracts the LiveCD ISO and boots the installation
machine with the ISO and target disk mounted, booting
from the CD. After start it waits for the LiveCD's first install menu
(`Welcome to FreeDOS 1.4 (LiveCD)`), selects "Install to harddisk",
accepts the defaults for preferred language and the installer welcome
screen with Enter, confirms partitioning drive C: and the required
reboot with Yes, accepts the default keyboard layout with Enter,
chooses the "Plain DOS system" package set (excluding the "with
sources" sibling), and confirms with Yes on the ready-to-install
prompt. `install` then blocks while the machine runs and always shuts
it down when it ends — including on Ctrl-C, which the CLI reports as
an interruption instead of a traceback.

The recipe layer has since been retired in favor of the `.rlqs`
install/verify scripts on the blueprint machine model (see the
machine-layer notes below); `rlq install` no longer exists.

### Machine layer (formerly relict)

### Changed

- Machine ids are `<blueprint>-<n>` instead of random UUID hex.
  `create` allocates the lowest free number for the blueprint
  (reused after `destroy`), serialized by a per-blueprint lock.
  Select with `--machine NAME-N`, `--blueprint NAME --machine N`,
  or `--blueprint NAME` when that blueprint has exactly one machine.
  `short_id()` is removed; the id is already the display form.

### Fixed

- An interrupted machine deletion, such as a transient Windows file lock,
  no longer leaves the machine permanently in the `destroying` phase;
  rerunning `rlq destroy` now retries it safely.

- A configured drive source for a slot already declared by a filesystem
  drive now fails closed with a slot-clash error instead of silently
  replacing it. An explicit `enabled: true` on the configured entry
  remains the deliberate way to override the filesystem drive, and
  `enabled: false` still unmounts it.

### Removed

- The recipe layer is retired (milestone-1 Spike 12): the `recipes/`
  package, the `rlq install <recipe>` command, and the recipe-era
  helpers (`ensure_media`, `install-media/` and `machines/<recipe>/`
  home paths) are deleted. The `.rlqs` install/verify scripts on the
  blueprint machine model replace them; there is no migration
  (pre-release).

### Added

- Milestone-1 Spike 13 lands the media-in-script machine model:
  blueprints declare empty removable drives (`"cdrom0": null`) — the
  blueprint alone defines machine topology — and scripts `insert` a
  defined media item to a declared slot and `eject` it, persisted in
  `reliquary-machine.json` across stop/start (`insert_media` /
  `eject_media` on the Python surface; stopped machines only for
  now). The new `machine: running | stopped` script header declares
  the state a script expects: `stopped` scripts start the machine
  themselves after inserting media, and `script` no longer
  unconditionally auto-starts. Insert/eject slots are statically
  preflighted against the machine before any guest input, and a
  guest-initiated power-off observed by `wait stopped` reconciles the
  machine back to phase `ready`. The built-in `freedos-1.4-plain`
  blueprint boots `["hdd0", "cdrom0"]`: a blank hard disk falls
  through to an attached LiveCD for install, then boots the
  installed disk afterward with no boot-order change. Scripts may
  still reorder boot devices with the `boot` verb / `set_boot_order`
  while the machine is stopped.

- Milestone-1 Spike 10 wires `rlq --blueprint|--machine script <label>`:
  resolve the label through the blueprint `scripts` map (bare stem when
  absent), seed a missing script from the built-in library, create a
  machine when `--blueprint` names one with none yet, and execute under
  an append-only run directory
  `cache/machines/<id>/runs/<timestamp>-<run_id>/` with `transcript.txt`,
  `screenshots/`, and `output/`. `run_script()` is the Python surface;
  `--display` forwards to the runtime. A `screenshot` inside a run
  verifies the QMP session against the machine's own `vm.json` while
  writing the image into the run record (`machine.screenshot()` gained
  a `directory` override to separate the destination from the
  identity home). Embedded media blocks,
  `--responses`, and `check-script` remain later spikes.

- Milestone-1 Spike 9 executes FreeDOS-shaped `.rlqs` scripts against a
  cached QEMU/DOS machine: normalized VGA `wait`/`expect`,
  `enter`/`type`/`press`/`select`, `screenshot`, host `start`/`stop`,
  and (with Spike 13) stopped-machine `insert`/`eject`/`boot`,
  starting a ready machine when needed and leaving it running unless the
  script stopped it. `expect` closes its polling QMP session before
  running the matched branch: QEMU's QMP server admits one client at
  a time, so a branch statement opening its own session while the
  polling session was still held would block forever.

- The global `--home` now reaches the `start`/`stop`/`destroy`
  subcommands: their own `--home` options no longer clobber an
  already-parsed global value with their default, which silently
  targeted machines in the default home.

- VM identity is per QEMU instance, not per name: every start passes
  a fresh `-uuid`, records it in `vm.json` beside the name, and every
  session verifies `query-uuid` as well as `query-name`. Same-numbered
  machines of one blueprint in different homes share their readable
  name, so a name match alone can no longer authorize a command
  against the wrong home's VM. The legacy root-home start path now
  uses the readable name `reliquary-machine` instead of a random hex
  suffix, since uniqueness comes from the uuid. A machine stop that
  fails closed on an identity mismatch no longer resets the phase to
  `ready`: the machine's own QEMU may still be running, so the phase
  only reconciles when the recorded VM is actually gone.

- Milestone-1 Spike 8 parses the FreeDOS-shaped `.rlqs` language into an
  immutable script model: headers, embedded media definitions, linear and
  state-machine bodies, `wait`, `expect`, `enter`, `type`, `press`,
  `select`, `screenshot`, `insert`, `eject`, `boot`, `start`, `stop`,
  and explicit transitions report source-located, compiler-style
  syntax and static-validation errors.

- The built-in library seed: blueprints, media definitions, and
  scripts ship inside the package under `reliquary/codex/`
  (included in wheels and sdists, readable from zip-bundled
  installs) and are copied out into the home on first reference —
  resolving an unknown blueprint via `create` seeds
  `blueprints/<name>.json` plus the media definitions and scripts
  it references, and resolving an unknown media name seeds its
  definition. A file already present in the home is never
  overwritten; deleting a copy is how it is refreshed. First
  entries: the `freedos-1.4-plain` blueprint, the
  `freedos-1.4-livecd` media definition (URL carried with an
  explicit redistribution assertion — FreeDOS is GPL free
  software), and the install/verify scripts.
- Machine lifecycle CLI and API for cached machines: `create`
  / `start` / `stop` / `destroy` / `list machines`, with
  `--blueprint` (sole machine of that blueprint),
  `--machine <blueprint>-<n>` (full id or unambiguous prefix), or
  `--blueprint NAME --machine N` (machine number). Machine ids are
  `<blueprint>-<n>` with the lowest free number reused after
  destroy; allocation is serialized per blueprint. `create_from_blueprint()`,
  `list_machines()`, `resolve_machine()`, and `machines.start` /
  `machines.stop` / `destroy` operate on `cache/machines/<id>/`;
  QEMU ownership (`vm.json`) lives under the machine directory.
  Bare `rlq start` / `rlq stop` without a selector still use the
  transitional root-home `MachineConfig` path. `apply`,
  interaction-via-selector, and multi-backend remain later spikes.
- Immutable machine-blueprint parsing for the milestone 1 subset:
  `parse_blueprint()` / `load_blueprint()` accept `platform`, `memory`,
  `drives` (`size` or `media`), `boot`, `name`, `description`, and
  `scripts`; canonicalize drive aliases, sizes, memory, and boot keys;
  resolve media names through the shared media library; and reject
  unknown fields, slot clashes, invalid sources, and undeclared boot
  targets.
- Machine materialization: `create(blueprint)` writes
  `cache/machines/<blueprint>-<n>/reliquary-machine.json`, qcow2
  images for `size` drives, and media payload paths for `media`
  drives; `machine_drive_args()` renders QEMU `-drive` tokens from
  that state.
- Media definitions per docs/media-spec.md: `parse_definition` /
  `load_definition` validate both the item (direct-download) form and
  the archive form (one source archive itemizing payloads, single
  URL), and `resolve_media(name, home=None)` resolves an item by name
  across the `media/` library, failing on duplicates. Mirror URL
  lists and several definitions sharing one archive remain
  unimplemented (milestone 2).
- `fetch_media(name, home=None, on_mismatch="fail")` returns a
  defined item's verified payload on demand, trying the cheapest
  source first: an existing payload that verifies is returned
  untouched, a cached source archive that verifies is re-extracted,
  and only then is the definition's URL downloaded. Source archives
  are cached under `cache/downloads/` and payloads under
  `cache/media/`; every file is SHA-256-verified before use, and a
  missing source is an error naming the item, file, and hashes.
  An existing payload or archive that fails its hash is never
  silently discarded: `on_mismatch` picks between failing fast with
  both hashes (`"fail"`, the default), an interactive
  delete-and-refetch checkpoint (`"prompt"`), and pre-approved
  deletion (`"refetch"`, which the planned `--refetch-mismatched`
  CLI flag will map to). A mismatched file whose definition names no
  source is always kept and reported.
- Path helpers for the planned blueprint home layout:
  `blueprints_dir`, `media_dir`, `scripts_dir`, `cache_dir`,
  `downloads_cache_dir`, `media_cache_dir`, and `machines_cache_dir`
  (each accepts optional `home=`). The existing `drives/` /
  `machine.json` / `vm.json` machine model is unchanged.
- `cursor_menu_select(item, timeout=30, exclude=(), port=None,
  home=None)` and the `Reliquary menu ITEM [--exclude TEXT]` CLI command
  select an entry in a cursor-key driven text menu (for example a boot
  menu). Rows containing an `exclude` text are never selected. Menus
  that rewrite their rows as the highlight moves (the FreeDOS
  installer's language chooser) are navigated by the row where the
  item last matched. Navigation is feedback-driven:
  Reliquary presses the up/down cursor keys, follows the selection
  highlight through the VGA attribute bytes, and presses Enter only
  once the highlight sits on the single screen row matching the given
  text (case-insensitively; an exact row match wins over rows merely
  containing the item, which otherwise must be unique). Each keypress
  waits for the repaint it causes to finish and hold steady rather
  than acting on the first changed read, so slowly repainting menus —
  the FreeDOS language chooser retranslating itself, with mid-repaint
  pauses while translations load — are never acted on half-drawn: a
  difference that shows no row gaining a bar-like (rare) attribute is
  re-observed instead of steered on, since keys sent to a menu that
  is still repainting are lost to its type-ahead flush. Before the
  first keypress the screen must hold still and is then sampled so
  self-repainting cells (clocks, countdowns, blinking indicators) are
  ignored throughout — without the quiet wait, a menu's own initial
  paint would be mistaken for animation and hide the very cells the
  tracking watches. When a keypress produces no classifiable movement
  the animation cells are re-learned and the bar is located directly
  by its attribute, so a keypress at the menu's edge or a briefly
  blinded diff recovers instead of failing. Enter
  is only sent after a fresh read confirms the highlight on the
  target row. Also available
  as
  `Machine.cursor_menu_select()`; `machine.vga_screen(qmp)` newly
  exposes the attribute bytes alongside the text rows.
- `create_hdd_image(filename, capacity)` creates a sparse qcow2 v3
  (`compat=1.1`, no preallocation) hard-disk image at the given path.
  Capacity accepts a qemu-img size string (`"2G"`, `"512M"`) or a
  positive integer MiB value. `find_qemu_img()` resolves `qemu-img`
  with the same search order as `find_qemu()`.
- `Machine.screen_text()` and `Machine.wait_text(pattern, timeout=60)`
  read and wait on the guest's VGA text screen directly from a `Machine`,
  so tasks and adapters can block until specific output (for example a
  boot menu) is displayed. The module-level `screen_text()` and
  `wait_text()` now delegate to these methods.
- `documents_dir()` publicly resolves the user's platform Documents
  folder (or `None` when it cannot be determined), so embedding
  projects can anchor their own state directories the same way Reliquary
  anchors its home.

### Removed

- The `boot-to-dos` CLI command. Wait for a prompt with `reliquary wait`.
  Programmatic boot readiness remains `AgentlessGuestExec.wait_ready()`.

### Changed

- Keyboard input and screen interaction moved to the platform-neutral
  machine layer, since they need only QMP and VGA text mode, not DOS:
  `char_keys()`, `send_keys()`, `send_text()`, `cursor_menu_select()`,
  `screen_text()`, and `wait_text()` now live in `reliquary.machine`, and
  `Machine` gains `send_keys()`, `send_text()`, and
  `cursor_menu_select()` methods. `interaction_agentless` retains only
  the DOS prompt-driven `AgentlessGuestExec` adapter. Package-level
  imports (`reliquary.send_text`, ...) are unchanged.
- Added an internal, runtime-checkable `GuestExec` protocol and isolated the
  QMP keyboard/VGA implementation as `AgentlessGuestExec`, with the DOS
  workflow and CLI consuming that adapter directly. The former
  `boot_to_dos()` and `run_command()` Python facades were removed; use
  `AgentlessGuestExec.wait_ready()` and `.execute()`.
- Exposed the identity-verified QMP session through `Machine.qmp()` for raw
  `cmd()` and `hmp()` access; interaction adapters now depend on `Machine`
  instead of opening QMP connections themselves.
- One validated `MachineConfig` now threads through the workflow and
  lifecycle layers. `start()`, `run_task()`, and `run_guest_program()` take a
  `MachineConfig`, versioned mapping, or JSON path as their sole machine
  settings input; `Runner.run()` passes its configuration through unchanged,
  and the QEMU launcher consumes that configuration instead of loose hardware
  arguments. The default QEMU argument vector is unchanged.
- The Python API now automatically discovers and loads `<home>/machine.json`
  when no explicit configuration is provided, matching CLI behavior. Explicit
  API values (passed as `MachineConfig`, mapping, or path) override the file
  values; `Runner` likewise loads the file when `config=None`.

### Added

- `--machine PATH` CLI argument for explicit machine configuration file selection; when omitted, the CLI automatically
  loads `<effective-home>/machine.json` if present, otherwise uses the default `MachineConfig()`. Explicit CLI
  overrides (`--platform`, `--qemu`, and raw QEMU arguments) apply on top of the loaded configuration; an omitted
  `--platform` leaves the file's platform unchanged, while `--platform dos` still overrides a non-DOS file value.
- `MachineConfig.from_file()` and `MachineConfig.from_mapping()` load a versioned JSON/mapping machine document
  (`version` must be `1`), normalize it immutably, resolve relative drive sources from the file directory or an
  explicit `base_dir`, and apply field overrides with deterministic merge rules for drives and options.
- Package-based `reliquary/` source layout split into home containment, declared media, ownership-safe lifecycle, generic
  machine interaction, DOS platform behavior, workflow orchestration, and CLI modules while preserving the existing
  root import and command-line interfaces.
- The complete DOS runner from the original implementation: DOS remains the default platform, while
  `MachineConfig(platform=...)` and `--platform` make the platform choice explicit. The reusable QEMU machine layer is
  shared; unimplemented non-DOS platform workflows fail explicitly instead of borrowing DOS assumptions.
- DOS 8.3 executable-name validation now belongs to the DOS platform module rather than generic workflow
  orchestration, so future guest-program workflows are not constrained by DOS naming rules.
- `Runner`/`MachineConfig`: the generic embedding surface for callers driving Reliquary as a runner.
  `Runner(home=None, config=None)` is a configured DOS test machine bound to one absolute home (the established
  process default when omitted), and
  `run(exe_path, args)` automatically ensures bootable media before performing the full `run_guest_program()`
  lifecycle. Provisioning is private; callers create distinct runners with distinct homes for concurrent runs, and
  per-home `vm.json` keeps VM ownership sound.
- Removed the `boot_floppy_image` and `boot_hdd_image` configuration shortcuts. Custom boot media uses the ordinary
  declared-drive inventory.
- `MachineConfig.drives` adds immutable configured drive specs using canonical logical slots plus `floppy`/`hdd`
  slot-zero aliases. A spec accepts a source path or `{source, options}` mapping; files mount as images, floppy and
  hard-disk directories mount as vvfat, and CD-ROM directories fail validation. Configured and home-directory media
  resolve into one inventory with slot conflicts rejected before launch.
- `MachineConfig.machine` maps directly to one QEMU `-machine` argument. A string selects the machine type; a mapping
  combines required `type` with immutable scalar properties and renders Boolean values as `on`/`off`. A raw
  `-machine` or `-M` in `qemu_args` conflicts with the structured field.
- `MachineConfig.memory` configures guest memory as a positive integer number of MiB, defaulting to 16 for DOS, 64
  for Win9x, and 256 for WinNT. It maps to one QEMU `-m` argument; an explicit value conflicts with raw `-m` in
  `qemu_args`, while a raw `-m` alone suppresses the platform default.
- The `drives/` directory under the home declares the whole machine by filename, with image content never
  interrogated. Image files `floppy[_<n>].<ext>` (slots 0–1, A: and B:), `hdd[_<n>].<ext>` (slots 0–3, the IDE bus),
  and `cdrom[_<n>].<ext>` (the IDE slots after the hard disks) mount as that medium; bare directories `floppy[_<n>]`
  and `hdd[_<n>]` mount as virtual FAT drives. An unindexed name means slot 0 (so `hdd.img` and `hdd_0.img` clash,
  as do all duplicate slots — fail closed). The idiomatic extension declares the image format: `*.img` and `*.iso`
  are taken as raw and pinned (avoiding QEMU's format-probing warning); any other extension (`hdd.qcow2`,
  `hdd.vmdk`, ...) is handed to QEMU to identify. Memory defaults to 16 MB and the boot order to a best guess from
  the declared media (slot-0 floppy image, else slot-0 hard-disk image, else cdrom); `-m` or `-boot` in the extra
  QEMU arguments overrides the corresponding default.
- The staged guest hard drive's letter is explicit configuration: `staged_drive` on `MachineConfig` and
  `run_guest_program()` (valid C–Z, normalized uppercase; default: match the declared machine, one letter per
  hard-disk slot before the staged drive, so C: on a floppy-boot machine and D: behind a slot-0 hard-disk image;
  letters below the default are rejected) declares where the staged vvfat hard disk appears in the guest — the drive
  Reliquary switches to for guest program runs. Staging targets the highest staged directory declared among the
  hard-disk slots, or `drives/hdd` created on demand.
- Explicit `home=` keyword on `download()`, `start()`, `stop()`, `run_guest_program()`, and the `drives_dir` path
  helper, overriding the process-global home per call. The
  existing `set_home()`/`--home` surface is unchanged.
- Installable `reliquary_tests` unit-test package, runnable with
  `python -m unittest -v reliquary_tests` so users and downstream packagers can verify an unpacked source distribution or
  installed wheel.
- Contributor guidelines covering development, verification, pull requests, and BSD-3-Clause contribution licensing.
- agentless DOS-under-QEMU automation harness — boot DOS headless, send keystrokes over QMP, scrape the 80x25 text
  screen from VGA memory, run commands with prompt-based completion detection, take screenshots, stage guest media
  via vvfat, and run guest programs end to end
  (`run_guest_program`, returning the program's redirected output).
- Visible manual VM sessions with `reliquary start --display`: the command returns once QEMU is ready, leaves the DOS VM
  running for direct interaction, and `reliquary stop` closes it through the same ownership-verified lifecycle.
- Bring-your-own boot image: Reliquary boots whatever the user declares under `drives/`.
- Test-framework result parsing is out of scope: Reliquary hands back raw guest output, and interpreting it belongs to
  the caller.
- QEMU binary discovery: `RELIQUARY_QEMU_HOME` / `QEMU_HOME`, then PATH, then well-known install locations; `--qemu`
  overrides.
- Home directory (boot images, staged guest drives, screenshots) defaulting to `reliquary/` under the user's Documents
  folder (the Windows known Documents folder, `~/Documents` on macOS, `xdg-user-dir DOCUMENTS` on Linux/BSD), falling
  back to `~/reliquary` when no Documents folder can be determined; override with `RELIQUARY_HOME`, `--home`, or
  `set_home()`.
- Native PNG screendump on QEMU >= 7.1 with a zero-dependency PPM-to-PNG fallback for older QEMU.
- Automatic QMP port selection with the selected port returned by
  `start()`, active-VM metadata under the Reliquary home for separate CLI invocations, and unique-name verification
  before any VM is controlled.
- DOS startup commands such as switching to C: use the ordinary
  `AgentlessGuestExec.execute()` interface rather than special boot options.
- Screenshot names are constrained to filenames so captured images cannot be written outside the Reliquary home.
- The installable test suite uses Python 3.9-compatible syntax, matching the package's declared minimum version.
