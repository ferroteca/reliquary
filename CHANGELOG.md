<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Changelog

All notable changes to reliquary are documented here. The format is based
on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 0.1.0.dev1 (unreleased)

### Added

- Accept `rlq list machine` and `rlq list blueprint` as singular
  aliases for `rlq list machines` and `rlq list blueprints`. (`#3`)

### Added

- The redesigned script surface now has a typed parser:
  `reliquary/script_grammar.lark` mirrors the normative EBNF in
  `planning/design/script-spec.md`, and `reliquary.script_parser`
  builds the typed tree from it. reliquary's own lexer feeds lark's
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
- `ScriptRun.final_state` is `ScriptRun.final_phase`, and `rlq script`
  prints `final script phase:`.
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
- `rlq list machines` and `rlq list blueprints` report an explicit
  `(no ...)` message on an empty result instead of a column header
  over zero rows, matching `list scripts`, which already did.
  (`#5`)
- `rlq list scripts --blueprint <name>` heads its first column
  `LABEL`, naming what it lists: the blueprint scripts-map labels used
  as `run-script` verbs. The bare `rlq list scripts` listing keeps
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

The relict project — the agentless QEMU guest automation harness reliquary
was built on — has been folded into reliquary. Its modules now live in the
`reliquary` package (its drive-inventory module renamed to `drives.py`), its
CLI commands are `reliquary` subcommands alongside `install`, and its home,
`RELICT_HOME`/`RELICT_QEMU_HOME` environment variables, and default
`Documents/relict` directory are replaced by the reliquary equivalents
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
LiveCD ISO is downloaded into the reliquary home (the distribution
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
  scripts ship inside the package under `reliquary/builtins/`
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
  home=None)` and the `reliquary menu ITEM [--exclude TEXT]` CLI command
  select an entry in a cursor-key driven text menu (for example a boot
  menu). Rows containing an `exclude` text are never selected. Menus
  that rewrite their rows as the highlight moves (the FreeDOS
  installer's language chooser) are navigated by the row where the
  item last matched. Navigation is feedback-driven:
  reliquary presses the up/down cursor keys, follows the selection
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
  projects can anchor their own state directories the same way reliquary
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
- `Runner`/`MachineConfig`: the generic embedding surface for callers driving reliquary as a runner.
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
  reliquary switches to for guest program runs. Staging targets the highest staged directory declared among the
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
- Bring-your-own boot image: reliquary boots whatever the user declares under `drives/`.
- Test-framework result parsing is out of scope: reliquary hands back raw guest output, and interpreting it belongs to
  the caller.
- QEMU binary discovery: `RELIQUARY_QEMU_HOME` / `QEMU_HOME`, then PATH, then well-known install locations; `--qemu`
  overrides.
- Home directory (boot images, staged guest drives, screenshots) defaulting to `reliquary/` under the user's Documents
  folder (the Windows known Documents folder, `~/Documents` on macOS, `xdg-user-dir DOCUMENTS` on Linux/BSD), falling
  back to `~/reliquary` when no Documents folder can be determined; override with `RELIQUARY_HOME`, `--home`, or
  `set_home()`.
- Native PNG screendump on QEMU >= 7.1 with a zero-dependency PPM-to-PNG fallback for older QEMU.
- Automatic QMP port selection with the selected port returned by
  `start()`, active-VM metadata under the reliquary home for separate CLI invocations, and unique-name verification
  before any VM is controlled.
- DOS startup commands such as switching to C: use the ordinary
  `AgentlessGuestExec.execute()` interface rather than special boot options.
- Screenshot names are constrained to filenames so captured images cannot be written outside the reliquary home.
- The installable test suite uses Python 3.9-compatible syntax, matching the package's declared minimum version.
