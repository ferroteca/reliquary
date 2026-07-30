# AGENTS.md — repository guidance

This is the canonical, agent-agnostic guidance for working on Reliquary. Human usage documentation belongs
in [README.md](README.md); keep this file focused on repository structure, engineering constraints, verification, and
maintenance context.

## Project state and layout

Reliquary is an OS installation scripter built on its own generic QEMU
runner, with DOS as the default and currently only complete platform
workflow:

- `reliquary/` contains the library and CLI. `__init__.py` preserves the root import surface; `errors.py` owns the
  error taxonomy — `ReliquaryError` the root every deliberate error subclasses, with
  `StaticError` (exit 2) / `PreflightError` (3) / `RunFailure` (4) / `RunCancelled` (5, a sibling of `RunFailure`,
  never a subclass) and the `exit_code` / `outcome` mapping both the CLI and the terminal event read. **Those four
  describe every surface, not a script run** (D58): what decides one never mentions a script — settled by the
  authored input alone, the world not satisfying that input, the work itself failing — so a malformed blueprint is
  a `StaticError` and a machine that does not exist is a `PreflightError`. Exit `1` is a fault and never a caller's
  mistake, with two populations: a deliberate `InternalError` (an invariant reliquary caught in its own state) and
  an accident that never was a `ReliquaryError`. **A deliberate raise is never a bare builtin** — `test_errors.py`
  walks every `raise` in the package and fails on one, because `except ReliquaryError` is contracted as the
  catch-all. `events.py` owns the run event stream — the `Event` envelope
  (`seq` / `time` / `elapsed` / `kind` plus the kind's own fields, flattened at serialization), the `EventStream`
  that records and renders as it goes (redacting every string through the run's secret set, ticking a live display
  without recording the tick), and `note()`, the emit-or-say-it-on-stderr helper media movement uses so a fetch
  outside a run is still honest; `progress.py` owns the renderings — `resolve_mode` (`auto` by stderr tty),
  `describe` (the one human line per event both human modes share), and the `pretty` / `plain` / `jsonl` renderers,
  with the output discipline enforced there: human modes render everything to stderr and leave stdout empty, `jsonl`
  owns stdout alone; `home.py` owns the six placeable working
  directories — assignment, the derivation cascade, the fail-closed unassigned error, the codex-autoseed axis, and the
  `Context` record every path-resolving function accepts; `assets.py` owns authored-asset residency: one resolution
  source (`DirectorySource`, reading each kind's own placeable directory walked recursively by extension, its `seeds`
  following autoseed), `source_for`, and the
  name-field-else-stem identity with its within-source conflict guard (`index_by_name`); the embedding API assigns no
  directory and never autoseeds, so it fails closed rather than reading a home or CWD, and an `ObjectSource` of
  JSON-imported objects is the planned third
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
  `cache/machines/<blueprint>-<n>/` — where **backend assignment** happens, before any image work: the
  blueprint's whole demand (control planes, media kinds, controllers, materialization modes) becomes a
  `backends.Requirements`, and a declared `backend` pins the choice while an absent one walks the priority
  order (`backends.PRIORITY`, D66) and takes the first backend both available and capable. A requirement no
  candidate can honor fails closed naming the backend and the requirement, rather than recording a policy
  nothing can honor (P11). **The dry run is the same evaluation with nothing committed** —
  `create_machine(dry_run=True)` returns a `DryRun` (`operation` / `report` / `plan`, the type F25's script
  variant shares) and writes nothing at all: no machine directory, no `machine.json`, no image, no fetched
  payload, no lock file and no seeded blueprint, a codex-only blueprint being read where it lies as a
  read-only check reads it. It resolves media without fetching them (`acquire.residency` reports
  `cached` / `would-download` / `would-extract` / `local-present` / `local-missing`, hashing nothing —
  `cached` is presence, not verification) and describes location properties without binding them
  (`binding.describe_keys`), because it must never prompt. It refuses what a create would refuse where a
  create would refuse it, with two deliberate exceptions, each a thing it *cannot do* rather than a
  severity judgement: an unbound location is reported unevaluated, and under `backend=` an absent backend
  is reported rather than raised — that flag asks whether the blueprint would work *there*, so capability
  alone decides (`backends.evaluate`), and it is legal only under `dry_run` because P10 gives the blueprint
  authority over what a machine is. Missing local payloads are the one class collected and raised together,
  so a validator pass names them all — plus lifecycle (`create` / `start` / `stop` / `destroy` /
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
  without a command of its own) and the in-band file family —
  `put_file` / `get_file`, `put_files` / `get_files` (a tree's
  contents, recursive, a copy and never a mirror) and `list_files`
  (one level or `recursive=`, returning a flat array of
  `{address, name, kind, size}` sorted by address, whose addresses
  the other four accept). All five address in guest terms — P17 —
  over a directory-source drive, stopped-only, with a non-vvfat
  target and an unmapped letter failing closed naming the gap
  (P11); one address form serves all of them, a directory spelled
  as a file is and the drive root sayable as `A:\`
  (`platform_dos.split_address` / `split_directory_address` /
  `join_address`), and the letter
  map itself is `platform_dos.drive_letters`, built from declared
  facts *and the volumes each disk actually holds* — read on the
  host, one letter per volume, a disk holding none taking none,
  cached per-drive in `machine.json` and cleared at every start
  (a guest repartitions only while running). A disk whose volumes
  cannot be read leaves every letter behind it unplaced and
  answers with the reason it could not be read, never the
  symptom — P10, D71 closed. `describe_drives` is the window onto
  all of it (D83): one machine-level report — declared and chosen
  facts per drive, the at-rest read per disk (backing, partitions,
  per-volume filesystem/label/BPB geometry), and the letter map
  with its undetermined drives — never phase-refused, because it
  answers from the record in `machine.json`: **read at every
  start's first step**, before the backend is engaged, so a running
  machine answers with this boot's starting state
  (`recorded: true`); the call reads a disk only when the machine
  is down and no record exists yet, and `refresh_drives` is the
  explicit stopped-only re-read for a layout changed behind the
  record;
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
  `backends.py` is **the backend adapter seam** — the provider contract behind the semantic surface
  (design: `planning/design/backend-adapter.md`), deliberately *not* one of the application surfaces:
  the `BackendAdapter` contract (discovery, capability report, image materialization, start/stop, and the
  carrier session), the `Availability` / `Capabilities` / `Requirements` vocabulary the report and the demand
  share, `identity()` (the recorded-VM-identity record every adapter writes: backend, `backend-id`,
  per-start `token`, and an adapter-shaped `endpoint`), the registry (`adapter(name)`, `discover()`), and
  `assign()` — built over `evaluate(name, requirements)`, which reports availability and unmet
  requirements as **two answers rather than one verdict**, because whether this host has a backend and
  whether that backend could build this machine are two questions and a dry run asks only the second.
  `_set_adapter` is the test seam, as `credentials._set_provider` is for the keyring.
  `backend_qemu.py` is **everything that knows QEMU** — binary discovery, `qemu-img` image work, the drive
  and boot rendering a machine's state lowers into, the owned launch with its identity verification, `Qmp`,
  the carriers (`send_keys`, `text_screen`, `screenshot`, `change_medium`) plus the named native escape
  hatch `QemuSession.native()`, and **at-rest access** (`open_drive`): a qcow2 is served by `qemu-nbd` on
  the loopback interface and addressed through `nbd.NbdDevice` rather than copied, with a qcow2 internal
  snapshot as the commit point a write is undone from; an image already raw keeps the staged copy, having
  nowhere else to stand an undo. Only qcow2 and raw are claimed — any other format QEMU could read is
  refused (`image.format-not-at-rest`) rather than served untested. `nbd.py` is the **NBD client** — the
  fixed-newstyle handshake and the four commands at-rest access uses, exposing an export as the byte device
  `at_rest` reads through. It knows nothing of qcow2 and nothing of FAT; **the reply handle is checked on
  every command**, because a stream out of step would otherwise hand a caller another request's sector.
  `at_rest.py` is **the portable half of at-rest access** and never learns what qcow2 is: it reads a
  *device* (`size` / `read_at` / `write_at` / `flush` / `close`), finding the partition table if there is
  one and a FAT12 or FAT16 volume past it, with the width decided by cluster count because that is what the
  format says decides it. **The recognition claim stops there** (D83): FAT12, FAT16 and FAT16B over
  standard MBR primary/extended partitioning, and everything else — FAT32 included — is a named refusal. `LocalDevice` is the one device it owns — an image already raw, opened where it
  lies under the advisory host lock. **The lock sits one byte past any image** (`_LOCK_OFFSET`): a lock
  over the image's own content is one the *server* trips on, since QEMU reads the header of a qcow2 it is
  serving, so the claim is placed where nothing reads. QEMU's own image locking is not the mechanism —
  it lives in QEMU's POSIX file driver and the Windows one implements none. **Partition types are pinned
  value by value** and an unreadable one is refused rather than skipped, because skipping renumbers every
  volume after it; `geometry()` reports the drive's shape (partitions with their declared types, volume
  count, and the BPB's own CHS where it states one) as P10's *read on the host* source.
  `backend_stubs.py` holds the three unbuilt adapters (VirtualBox, VMware
  Workstation, Hyper-V): their host probe is real, they claim **no capability**, so assignment passes over
  them even where the backend is installed, and a pinned one fails preflight naming the gap.
  `control_display.py` is the **agentless-display control plane** — key mapping, text-screen composition and
  the cursor-menu machinery, written once over the seam's text-screen contract (character rows plus opaque,
  equality-comparable per-cell attribute tokens) and never per adapter.
  `interaction.py` defines capability protocols, `interaction_agentless.py` contains the concrete agentless DOS
  adapter (prompt-based readiness and command completion), `machine.py` is the backend-neutral machine handle:
  a machine is addressed by its materialization directory, the adapter named in the recorded identity supplies
  the session (`Machine.session()` / `console()`), and `Machine.qmp()` is the QEMU-scoped escape hatch that
  refuses any other backend,
  `platform_dos.py` owns DOS provisioning and facades plus the guest-address mapping (`drive_letters` —
  floppies to A:/B: by slot, hard disks C: onward, CD-ROMs after them, from Reliquary's own drive assignment
  and never from a guest; `split_address`). The
  `.rlqs` language is four layers: `script_nodes.py` (the lexer and its diagnostics),
  `script_parser.py` with `script_grammar.lark` (the typed tree, node signatures, `parse_script` /
  `load_script`), `script_validation.py` (the V-numbered static rules, each diagnostic citing its id),
  and `script_timing.py` (durations, and the timing plan resolved at parse time: every observation's
  effective timeout and every guest-input verb's effective `pacing` — the settling gap before its first
  key event, D60 — each with the scope that supplied it; `format_plan` and
  `run_script(dry_run=True)` / `rlq run-script --dry-run` report it without running,
  with `script_validation.reach` counting the statements no static pass can promise
  will run — a handler body is the guest's decision, not the plan's).
  **The script dry run is the same `DryRun` the create half returns** and the same
  rule: read-only throughout, seeding nothing and never prompting, stopping before
  the machine starts and before any statement reaches a guest. Two things are its
  own. **The selector is optional there alone** — its presence chooses which of
  script-spec.md's two checkable tiers applies, which is what keeps the
  selector-less mode the respelling would otherwise have deleted in silence. And
  `--dry-run` flips the command from a stream to a **document**: `--json` becomes
  legal (it prints exactly what the twin returns) while `--progress` and
  `--display` are refused, a plan having no stream to render and no window to
  show. **The whole check family is deleted rather than aliased** (P9): its
  command, its twin, its result type, and the property-key predicate that went
  private with them — a public predicate on a string with no CLI twin was a
  standing P6 residue. `test_old_surface_purge.py` holds the spellings and keeps
  them retired, which is why they are not written out here.
  `binding.py` resolves declared script properties before a run —
  the flattened source order (explicit `--property`, blueprint
  parameter with its `{"property": ...}` redirect, `RELIQUARY_PROPERTY_*`
  environment with collision preflight, the properties file, the
  declared `default=` derivation, then an
  interactive ask), the text/media/secret kind rules, secret values
  pulled from the credential store, and `describe_sources` the dry
  twin that names each key's source for a dry run without
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
- `pyproject.toml` packages `reliquary` as the `reliquary` command. **The wheel is the runtime alone**: `reliquary_tests`
  is excluded from it (the `reliquary*` glob would otherwise match it, so the exclude is load-bearing) and ships in the
  sdist instead, via `MANIFEST.in`, together with `docs/` and `planning/design/`. A source package must be able to run
  its own suite; an end user has no use for the fixtures.
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
  rule (`SURFACES.md`), the adjudication record (`DECISIONS.md`, which spans open, pledged, refused and
  retired alike), and the task queue. Design sits with what it serves: `planning/proposed/design/` and
  `planning/pledged/design/` for a feature's own design, `planning/design/` for open design problems serving
  no single feature — the whole-system view itself (the seams model and the P-numbered principles) is root
  `ARCHITECTURE.md`. Once a surface ships, its normative spec moves to `docs/spec/` — current truth does not
  live under `planning/`.
- **There is no roadmap** (D42): `pledged/` says the project will do it and nothing about when, so the absence
  of order in `TASKS.md` holds equally for pledged features, the only binding order running inside a feature.
  **Features carry F-numbers and tasks carry T-numbers** — the handle a dependency, commit or decision points
  at — which unlike U-, P-, S- and D-numbers **evaporate on delivery**, retiring unreused, gaps being history
  rather than a promise. A T-number is issued at entry to `TASKS.md` (a task has no proposed state), and that
  file states the sequence's high-water mark because a struck task leaves no other record of it. Designs take
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
- `planning/SURFACES.md` is the surface-change rule: how every surface-changing decision is weighed. The
  **application surface** inventory it scopes over (CLI, embedding API, scripting language, and machine blueprints — media,
  source, and archive are components inside the blueprint — plus the script properties, recorded outputs, and
  the working-directory layout) lives in root `ARCHITECTURE.md` "The application surfaces", S-numbered S1–S8, where the housekeeping lookup answers by
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
  **normative specifications** of every application surface — the CLI, the
  embedding API, the scripting language, the blueprint model, media,
  properties, asset resolution, the instance model, the codex, and
  the answer-file server. A spec is the authority
  the implementation answers to, not a report on it: where a spec and
  the code disagree, the spec is right and the code has a bug, unless
  the spec is changed first through the surface-change rule. The
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
  conformance corpus (`reliquary_tests/fixtures/conformance/blueprint/`,
  `test_conformance_corpus.py`) runs every fixture against both the
  parser and the schema so the two cannot drift. Placement rules
  are in `.agents/skills/documentation-rules.md`.
- **Two conformance corpora, and the second is the stronger
  pattern.** `fixtures/conformance/script/` (`test_script_corpus.py`)
  does for `.rlqs` what the blueprint corpus does for `.rlqb`, and
  adds the assertion the first cannot make: an invalid fixture
  declares the V-id that must reject it, and the harness checks the
  diagnostic cites it — so a fixture failing for the *wrong* reason
  is caught by the suite rather than by a reviewer. Where an id does
  not exist yet the fixture carries `# cites: no`, asserted in both
  directions so it retires itself when the id lands; that count is
  the live measurement behind D55. Each corpus has its own README,
  which is where its findings live.

Keep these modules deep: add behavior to the module that owns its invariant, and introduce another module only when a
real interface or maintenance seam justifies it. The package root exposes the intended embedding surface but owns no
implementation.

## Required invariants

### No backward compatibility before 1.0

Reliquary is evolving rapidly and deliberately maintains **no backward compatibility of any kind** until a
GA 1.0 release: no spec/config format versioning or migration, no API aliasing, no
deprecated-name shims, no compatibility parsing. When a surface changes, change it coherently and
completely — update every caller, document, and test to the new shape and delete the old one. Do not add
transition affordances "to be safe"; stale artifacts (old machine blueprints, homes, embeddings) may simply fail
and users recreate them.

Through beta and the rest of pre-1.0 this softens in degree only: **some** effort not to break users may be
granted where it is warranted and cheap, but nothing is promised, an effort granted once creates no
expectation of the next, and a clean break remains the default. Any cushion is a deliberate exception —
the owner's call, recorded in the CHANGELOG — never a shim left to accumulate. Compatibility guarantees
proper are defined no earlier than 1.0.

### Surface changes are vetted

The CLI, the embedding API, the scripting language, and the machine blueprint (media, source, and archive
components included) are
Reliquary's primary **application surfaces** (S1–S4); the script properties, the run's returned output (the live
event stream, `--json` documents, exit codes — persistence dropped with D36), and the working-directory layout are
the supporting ones (S5–S8), covered equally. Any decision that
changes one follows the rule in [planning/SURFACES.md](planning/SURFACES.md): requests triage by their impact on the
numbered use cases ([USE-CASES.md](USE-CASES.md)) — no impact or strong alignment is an easy approval, adding a new use case is more work but still
easy, and a change misaligned with the use cases must win the argument for amending the list itself, with
work starting only after the amendment lands — then the change is named across every surface it touches
and landed coherently on all of them. Where a docs/spec/ specification and planning/SURFACES.md or
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

### Placeable working directories, and what containment now means

**Six working directories, every one placeable** (`home.py`; normative:
docs/spec/asset-resolution.md "The working directories"): `home`, `blueprints`, `scripts`, `cache`, `media`,
`machines`. Each starts **unassigned**; a value arrives by `set_<name>_dir()`, the CLI's `--<name>-dir` flag, or
`RELIQUARY_<NAME>_DIR`, and the rest **derive** — `home` gives default locations to `blueprints`/`scripts`/`cache`,
and `cache` (assigned or derived) gives them to `media`/`machines`. Derivation reaches only what is still unassigned,
so `cache` alone conjures no home and `machines` alone leaves `media` where the rest of the resolution puts it.
**Unassigned is a fail-closed `StaticError` (`dir.unassigned`) naming the directory**, raised at first use rather than
at `Context` construction, so the diagnostic names what was actually needed and a context may be built before it is
filled.

The surfaces differ only in whether an assignment is made for the caller. **The CLI** assigns `home` its default
(`Documents/reliquary`, falling back to `~/reliquary`) whenever neither a flag nor the environment named one, so one
assignment reaches all six and the error is unreachable at the keyboard — **a property of that default, not an
exemption from the rule**, which is what keeps it true if the default ever changes. **The embedding API** assigns
nothing, and there the error is reachable; that is the whole safety of the design. Honouring the environment
(`adopt_environment()`) is likewise the CLI's step and never the library's.

`Context` is a **plain record** of the six optional paths plus `autoseed` — no methods, all resolution in `home.py`'s
module functions — because six nullable strings bind cleanly from C or Java where six keyword arguments would not
(P7). Every function resolving a working directory accepts `context=`: omit it for the globals, pass a bare string as
shorthand for `Context(home_dir=...)`, or pass a `Context` to pin whatever slots it fills per call, unfilled slots
falling through to the globals and then to derivation. The CLI only ever drives the globals — scoped `Context` objects
are an embedding-API-only capability. `machine.py`'s and the adapters' own `home=` parameters are a different,
narrower concept — an already-resolved plain directory (sometimes a machine's own materialization directory standing
in for one), not a `Context`; they were deliberately left alone.

**Containment is no longer topology.** With six independent roots, "under the home" is not a claim Reliquary can make;
what P12 now requires is that Reliquary **writes only where it was told to** — never beside the module and never into
a source repository during normal use.

**Autoseeding is its own axis** (`home.autoseed` / `Context(autoseed=)`; `--autoseed` / `--no-autoseed`), replacing
the retired asset-root knob that answered placement and hermeticity with one word. On at the CLI, **off in the
embedding API**: a resolution miss falls back to the built-in codex only when something asked for it, so automation
never picks up the codex, a developer's home, or a stray CWD. `assets.py` is correspondingly one source
(`DirectorySource`) reading each kind's own directory, walked recursively by extension, with `seeds` a live property
rather than a per-source constant. An asset's identity is its declared `name` (id-safe) else its filename stem;
within-source effective-name collisions are errors. Selection scoping: `--blueprint <name>` matches only machines
whose recorded `blueprint-source` equals this invocation's resolution (a sourceless machine matches by name alone).
**Seeding on request is not what autoseed governs**: `seed-blueprint` / `seed-script` (there is no `seed-media`) write
into the assigned `blueprints` / `scripts` directory wherever it is, project tree or home alike — copy a first draft,
commit the copy.

Default layout, with only the home assigned. A machine is wholly its materialization directory — there is
no root-home machine model (the legacy root-home machine surface — a
root-level `drives/`, a root `machine.json`, a root `vm.json` — was
absorbed and deleted; the per-machine `machine.json` below is the new,
unrelated cache state file):

- `blueprints/` — composed blueprints, media components included (`blueprints_dir`)
- `scripts/` — automation scripts (`scripts_dir`)
- `cache/media/` — every cached payload (`media_dir`), keyed by media name, under the cache root; each
  file is named `<media-name>.<ext>`, which is the whole of its identity — no sidecar record (D41)
- `cache/machines/<name>-<n>/` — machine materializations (`machines_dir`;
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

Never send a control command to a backend object until its identity is verified.
**No code outside an adapter opens a backend connection**, and every adapter operation
verifies before it commands.

The identity is generic (`backends.identity()`): the **backend**, that backend's own
machine identifier (**`backend-id`** — QEMU's readable `-name`, and later a VirtualBox
machine UUID, a `.vmx` path, a Hyper-V VM Id), a per-start **`token`**, and the
adapter-shaped **`endpoint`**. The token is not decoration: an addressable endpoint
outlives its owner (a QMP port is reusable by strangers, and same-numbered machines of
one blueprint in different homes share their readable name), so the name alone must
never authorize a command. `machines.py` persists the record the adapter returns into
the `vm` section of `machine.json`, atomically with `phase`; adapters own no state file.
Identity mismatches fail closed; in particular, an adapter's `stop()` must never reach
its backend's quit path with an unverified object.

On QEMU that is `launch_owned_qemu()` assigning the readable `-name` plus a fresh
per-start `-uuid`, and every later session checking `query-name` **and** `query-uuid`
against the record. When no port is given it selects an available local one; an explicit
port must be free. Startup failure and timeout paths must terminate the child so they
cannot leave an untracked QEMU process.

`Machine.session()` is the carrier seam every control plane uses, and `Machine.qmp()` is
the **named native escape hatch** — explicitly backend-scoped, refusing a machine that is
not QEMU's rather than approximating a monitor it does not have. Interaction adapters
receive a `Machine` and use these seams rather than opening connections directly.

`machines.read_vm_state(machine_dir)` reads the recorded identity and validates its
generic core; what the endpoint *is* belongs to the adapter, which validates it when it
opens a session. Nothing above the seam reads a port — `start_machine()` returns the
machine id, and the CLI selects a machine by `--blueprint` / `--machine`.

### DOS boot and scripting

A machine's drives are declared in its blueprint (the field reference,
`docs/blueprint-reference.md`), each naming a media
component; per-machine images are materialized into
`cache/machines/<id>/media/`, named for the media.
`backend_qemu.drive_args()` renders them from the machine
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
script runtime (`script_runner.py`'s `run_script`, whose `dry_run=` returns a
`DryRun` rather than a `ScriptRun`). The
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
  expects native bindings beyond Python (planning/SURFACES.md;
  docs/spec/cli.md): never adopt a design that would be
  difficult to express in a common binding language such as C or Java,
  and hold the CLI to the same constraint as the fallback binding for
  unbound languages — never make it difficult to drive from a program.

## Dependencies and style

- Runtime dependencies are welcome when they pull their weight; declare
  them under `[project].dependencies` in `pyproject.toml`. Prefer the
  stdlib only when it serves the need equally well.
- **A test-only dependency is a hard requirement of the suite.** It goes
  in `[dependency-groups].dev` and is imported at module top like any
  other — never behind a `try`/`except ImportError` feeding a
  `skipUnless`. That pattern turns an incomplete dev environment into
  quiet skips, which is how the blueprint corpus came to run against
  the parser and *not* the schema while claiming the two cannot drift.
  A missing dev dependency should stop the suite and name itself.
  `skipUnless` is for a resource that genuinely may be absent in a
  supported configuration. **The bar is high, and it moved**: `docs/`
  and `planning/design/` now ship in the sdist precisely so the
  spec-conformance tests run there, so a guard on them fires nowhere
  the suite is supposed to run. The suite skips exactly **one** test —
  the opt-in FreeDOS integration run — in the source tree and in the
  unpacked sdist alike; any other skip is a defect to fix, not a
  configuration to tolerate. A guard that survives is one whose
  resource is genuinely optional, and it says which.
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

The project is **GPL-3.0-only** and follows REUSE conventions. The name
**Reliquary** is reserved to Paul Galbraith under [TRADEMARKS.md](TRADEMARKS.md) — a reservation GPL section 7(e)
expressly permits; do not weaken or contradict that policy in docs or packaging metadata.

Every new file authored for the project needs:

```text
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
```

Use the appropriate comment syntax for the file type. Files that cannot or should not carry headers must be covered by
`REUSE.toml`.

### The relicensing reservation, and what it constrains

Paul holds copyright in the whole work and **reserves the right to relicense the project on any terms**. Nothing is
planned; the reservation exists so the option is not lost by default. Two consequences bind everything below, and
neither is negotiable at the level of an individual change:

- **The project must own every line it ships.** Relicensing is only available to a party holding rights in the whole
  work, and enforcing copyleft requires standing that only an owner has. One file the project cannot account for
  forecloses both, permanently and silently.
- **Assignability, not licence compatibility, is the test for incoming code.** GPL-compatible is not good enough. Code
  the project cannot acquire *title* to cannot enter, whatever its licence.

**Vet against a commercial dual licence, and say only "relicensing" out loud.** These are two different jobs and the
difference between them is deliberate. What the project *states* — in README.md, CONTRIBUTING.md, and CLA.md — is that
relicensing is reserved and nothing is planned, which is true and is all the disclosure the reservation needs. What the
project *vets against* is the strictest realistic outcome, which is a commercial dual licence, because vetting to a
weaker bar would forfeit the reserved option invisibly.

So the question to ask of any external source is **"could this ship inside a proprietary product?"** — never "is this
GPL-compatible?" The second question has a comfortable answer far more often than the first, which is exactly why it is
the wrong one. Reliquary's own GPL arm could absorb a great deal that a commercial arm never could, and the difference
between those two sets is precisely what the reservation is holding open.

The asymmetry is what makes this worth the discipline: judging correctly costs nothing at the moment a dependency or a
reference is first considered, and cannot be revisited afterwards at any price. By the time it matters the code is
load-bearing, and the upstream author is under no obligation to sell anything.

Contributions are therefore accepted only under the copyright assignment in `CLA.md`, with an automatic fallback to an
exclusive sublicensable licence where a jurisdiction bars assignment. Once assigned, a contributor's files carry Paul's
copyright notice, because he is then the actual owner — the REUSE record states ownership, not authorship, and
authorship credit lives in the git history. Keep the human submission terms in `CONTRIBUTING.md` synchronized with this
policy.

**Never merge third-party source.** Not permissively licensed source, not public-domain-looking snippets, not vendored
files. The contributor cannot assign what they do not own, and neither can the project. Third-party code enters as a
declared dependency or not at all.

### Dependency licence tiers

Every runtime dependency sorts into exactly one tier, and the tiers are drawn against the commercial-dual-licence bar
above rather than against GPL compatibility. Adding a dependency in a lower tier than it belongs is the single change
most likely to cost the project something it cannot get back.

| Tier | What qualifies | Standing |
|---|---|---|
| **1 — Sublicensable** | MIT, BSD-2/3-Clause, Apache-2.0, ISC, PSF, MIT-CMU/HPND, Zlib | Freely dependable. Attribution obligations carry into any redistribution. |
| **2 — Arm's length only** | LGPL as an unmodified, separately installed dependency; GPL invoked as a **separate process** | Permitted, never combined. Vendoring, forking, patching, or bundling it into a frozen executable demotes it to tier 3. |
| **3 — Refused** | Any GPL/AGPL code that would be linked, imported, or copied into the project | Never. Compatible with the GPL arm and fatal to the reservation, which is the whole point of the tier. |

Build-time and development dependencies are **out of scope entirely** — they are not distributed, so their licences
impose nothing. The tiers govern what a `pip install reliquary` pulls in.

The current runtime closure is tier 1 throughout except `qemu.qmp`, which is tier 2 and discussed under prior art
below. Verify a new dependency's whole transitive closure, not just the package named — a tier-1 package that pulls a
tier-3 one is a tier-3 problem.

Two conditions on tier 2 exist only because of the commercial-arm bar, and both are easy to breach by accident:

- **A frozen single-file executable is not arm's length.** Shipping Reliquary via PyInstaller, Nuitka, or py2exe would
  bundle `qemu.qmp` in a form the user cannot replace, which is exactly what LGPL's relinking requirement forbids.
  Decide the LGPL story before building one, not after.
- **LGPL requires permitting reverse engineering for debugging modifications** to the library. A boilerplate
  commercial EULA's blanket anti-reverse-engineering clause would breach it. If a commercial licence is ever drafted,
  carve this out — it is invisible until someone reads both documents together, and by then it is a breach.

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
After packaging metadata changes, inspect `PKG-INFO` for at least the name, version, Python requirement, and runtime
dependencies in both built artifacts, then run `python tools/check_dist.py`, which asserts what each artifact must
carry — the grammar, the schemas and the codex in the wheel; the suite, its fixtures, `docs/spec/` and the
script-example catalogue in the sdist — and that the wheel carries no tests. It exists because the suite no longer
ships in the wheel, so nothing running inside the wheel inspects it: package data is what disappears silently, and a
missing `.lark` grammar breaks an installed Reliquary while every source-tree test still passes.

For release-facing packaging changes, unpack the sdist outside the source tree and run `python -m unittest -v
reliquary_tests` there: it must report one skip, the opt-in integration test. That is the run a downstream packager
makes, and it is the one that proves the source package is complete. Install the wheel into a clean environment too, but
check it by using it — `rlq --version` and an import — since it carries no suite to run.

Run `git diff --check` before handing work back.

Hands-on tests require QEMU. Use `--home-dir` with a scratch or deliberately reused test home rather than polluting the
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
- a `backend-id` match with a token mismatch is an identity mismatch
- a stop refused on identity mismatch leaves the machine phase `running`
- stale state produces clear diagnostics and cannot target another VM

Adapter-seam guarantees, which the suite exercises against a **double** rather than a
hypervisor (`reliquary_tests/fake_backend.py`, installed with `backends._set_adapter`) —
no unit test may probe or launch a real backend:

- a requirement no candidate can honor fails closed naming the backend *and* the
  requirement, before any image work
- the priority walk takes the first backend both available and capable, so availability
  alone never wins and the order never stands in for a capability check
- a declared `backend` skips the walk, and an unavailable or incapable one fails closed
- a stub adapter claims no capability even where its backend is installed
- the machine model hands the adapter a resolved state and gets an identity back: no
  backend argument is composed above the seam, and no port is read there

Milestone-9 guarantees needing the same care:

- every deliberate error subclasses `ReliquaryError`, and the four run-surface classes exit 2/3/4/5
- a run creates no `runs/` directory and writes nothing to the machine directory
- `--progress jsonl` puts the event stream on stdout and nothing else, terminal event last
- a human `--progress` mode leaves stdout empty
- a bound secret never reaches the event stream, and it suppresses automatic screenshots afterwards
- a cancellation ends at a boundary with an in-flight input delivered whole
- a machine variable is cleared by `start`
- a non-vvfat or unmapped in-band file target fails closed naming the gap —
  on every one of the five verbs, an image drive being P16's standing residue
- a listing's addresses are the ones the file verbs accept, and a missing
  guest directory is an error rather than an empty listing

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

**Every project named in this section is a concept reference. None is an implementation source.** The rule is doctrine
and it predates the licence change: designs are studied and reimplemented, code is never read for reimplementation,
ported, or translated. What the GPL-3.0-only move and the relicensing reservation add is a second, independent reason
the answer can never be yes — the project cannot acquire title to another author's code, so adopting it would forfeit
the reservation permanently. **Where the two reasons ever appear to diverge, the doctrine governs.** A close
translation is a port whatever a licence permits.

Vet these the way dependencies are vetted, against the commercial-dual-licence bar rather than GPL compatibility. For
every project named below the doctrine already settles it, so the licence question is never the one doing the work —
but **record both reasons anyway**, because they fail differently. A licence argument can be falsified by a licence
change, and this section has already had that happen once: the os-autoinst reasoning below was true under BSD and
false the day the project became copyleft, while the doctrine it sat beside did not move an inch. A boundary resting
on one reason is one licence change away from having none.

Reliquary uses QEMU's published `qemu.qmp` library for protocol handling and implements the machine-lifecycle role
locally.

`qemu.qmp` is **tier 2**, and stays there by being left alone: an unmodified, separately installed dependency, imported
and never vendored, forked, patched, or frozen into a bundled executable. Most of it is LGPL-2.0-or-later, which the
tier permits. **`qemu/qmp/legacy.py` (`QEMUMonitorProtocol`) is GPL-2.0-only and must never be imported** — it sits in
a package the project already depends on, so nothing but this rule stands between it and an ordinary-looking import.

QEMU itself is **tier 2 by process separation**, and that separation is load-bearing rather than incidental: Reliquary
invokes `qemu` as a separate program over the documented QMP protocol, which is arm's-length use of a GPL work rather
than a combination with it. Never link it, never vendor it, never ship a patched build.

QEMU's in-tree `QEMUMachine` is not published independently. **If that changes, the answer is still no** unless it is
published under a permissive or LGPL licence: the in-tree code is GPL-2.0-only, unassignable, and adopting it would
foreclose the reservation. This supersedes the earlier standing invitation to reassess on maintenance grounds — the
question is no longer about maintenance.

QEMU's own functional tests validate the broad model of scripting a guest over QMP and asserting on observable state.
Reliquary adds the DOS-specific layer: keyboard conventions, VGA text scraping, prompt
completion, and vvfat staging.

SUSE's os-autoinst (the engine under openQA) is the closest prior art to Reliquary as a whole: it drives OS
installers by screen matching and key injection over QMP/VNC, with per-operation "consoles" (VNC, serial,
virtio-terminal, ssh) mirroring Reliquary's control planes, multiple backends (qemu, svirt, bare metal) mirroring the
adapter seam, command completion over serial via echoed marker strings, per-step screenshot records, and snapshot
"milestones" for resuming long installs. Use it as a **concept reference only** for control-plane and backend
implementations — Reliquary learns from its designs (the input event model, needle area types, console seams), never
from its code. Study the documentation and the ideas; reimplement from scratch. **The bar is doctrine, and it does not
move with the license** — which this project has now demonstrated the hard way, because the licence moved and the bar
did not.

The record is worth keeping straight, since the old reasoning is still quotable and is now wrong. While Reliquary was
BSD-3-Clause, os-autoinst's GPL-2.0-or-later licence *by itself* barred porting its code, needles, or test modules.
Under GPL-3.0-only that is no longer true: GPL-2.0-**or-later** may be taken under GPLv3, so licence compatibility
stopped being the obstacle the moment this project became copyleft. **Nothing about the boundary changed.** What holds
it now is firmer than what held it before:

- **Doctrine, first and regardless.** A close translation is a port whatever any licence permits, and that was always
  the actual rule.
- **Assignability, permanently.** The project cannot acquire title to SUSE's code. Merging it would forfeit the
  relicensing reservation for good — a one-way door, and one that closes silently.

The same correction applies to `consoles/VNC.pm`, its RFB client and precisely the file a VNC control plane would reach
for. It is dual-licensed `Artistic-1.0 OR GPL-1.0-or-later`; the earlier note that "copyleft does not reach it" was
never the point, and both arms are in any case reachable from a GPLv3 project. Artistic-1.0 is additionally too vague
to build anything on — the FSF's long-standing objection to it stands. It is off limits for the reasons above, which
apply to it exactly as they apply to the rest of the tree. Deliberate divergences to preserve: VGA text
scraping instead of image needles for text-mode guests, authored step documents instead of Perl test modules, and a
local ephemeral-machine tool instead of a testing service (scheduler, workers, and web UI are permanently out of
scope).

Keysight's eggPlant Functional is the closer analogue for the display seam specifically: a commercial GUI test tool
that drives its system under test over VNC **or** RDP, matches screens by image, and carries the click point inside
the matched image. Its vocabulary lands almost one-to-one on the settled landmark design
(`planning/proposed/design/landmarks.md`) — hot spot to spot, image collection to variant, search rectangle to the
deferred selecting region, tolerance to the similarity percent — and that convergence is the useful part: it says the
asset model is well-trodden rather than novel. Proprietary, so the concept-reference rule applies by default; the
public documentation is the whole of what is readable, and it is the *only* thing to be read — no trial binaries
decompiled, no EULA-gated material, no support-portal content.

eggPlant is the one reference here where the relicensing reservation *raises* rather than lowers the stakes. A GPL
hobby project converging on a commercial tool's vocabulary is unremarkable; a project that has publicly reserved the
right to relicense is a more attractive target for a patent holder in the same space, and the convergence documented
against `planning/proposed/design/landmarks.md` is a discoverable record. The convergence is genuine and independently
arrived at, which is exactly why it should stay documented as such — evidence of parallel design, not of borrowing.
Should the reservation ever be exercised, this is the reference to review first, with advice.

Espressif's `pytest-embedded-qemu` is useful prior art for a future
`pytest-reliquary` plugin: host pytest orchestration around a native guest test framework. It is not directly reusable
because it assumes Espressif targets, serial output, and Unity result grammar. MIT-licensed, so it is **tier 1** and
the only reference here that could in principle be depended on — as a dependency, never as copied source, and the
concept-reference rule governs its designs like any other.

FreeRDP is the realistic vendored stack should an RDP display carrier ever be built (see
`planning/proposed/FEATURES.md`). Apache-2.0, so **tier 1**, with two conditions attached: its NOTICE obligations flow
into every redistribution, and it was relicensed *from* GPL historically, so per-component licensing must be verified
at the file level before anything is vendored. A project-level licence statement is not sufficient evidence for a
relicensed codebase.
