# AGENTS.md — repository guidance

This is the canonical, agent-agnostic guidance for working on Reliquary. Human usage documentation belongs
in [README.md](README.md); keep this file focused on repository structure, engineering constraints, verification, and
maintenance context.

## Project state and layout

Reliquary is an OS installation scripter built on its own generic QEMU
runner, with DOS as the default and currently only complete platform
workflow:

- `src/reliquary/` contains the library and CLI. `__init__.py` preserves the root import surface; `errors.py` owns the
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
  directories — the derivation cascade, the fail-closed unassigned error, and the
  `Context` record every path-resolving engine function accepts, which also carries the selected
  properties file (P26's cargo); `session.py` is the exported **`Session`**, P26's one door —
  opened on a bare home string or a `Context`, refusing construction
  without a home (`dir.unassigned`, the first-use rule moved to the door), pinning the record
  once at construction from that record alone (no module-global state exists, so two
  sessions in one process are unremarkable), and forwarding one thin veneer method per
  ambient-state verb to the engine modules; the codex verbs (CLI-only, D87) and the pure
  parsers take no veneer, and
  the CLI is its first consumer; `assets.py` owns authored-asset residency: one resolution
  source (`DirectorySource`, reading each kind's own placeable directory walked recursively by extension, and no
  seeding axis behind it), `source_for`, and the
  name-field-else-stem identity with its within-source conflict guard (`index_by_name`); the embedding API assigns no
  directory, so it fails closed rather than reading a home or CWD, and an `ObjectSource` of
  JSON-imported objects is the planned third
  source, `json5reader.py` is the JSON5 document reader (D102 — the published
  grammar, `NaN`/infinities refused so values stay ordinary JSON, source
  positions on request), `document.py` is the `.rlqb` parser (normative spec: `docs/spec/blueprint-model.md`) —
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
  `authoring.py` is **the counterpart of `assets.py`** — `assets` resolves and reads what a user owns, `authoring`
  writes and removes it — and is authoring-only: it scaffolds (`new_blueprint`), writes a media declaration for a
  file already
  on disk (`add_media(name, file)`: computes the sha256, writes `blueprints/<name>.rlqb` locating the media at
  that path, copies nothing, refuses to overwrite — the supply seam for pinned-but-unlocated codex media, D41),
  and removes both authored kinds — `delete_blueprint`, which fails closed while any machine of that blueprint
  exists, and `delete_script`, which fails closed while any blueprint in the source references the script.
  **Both removals refuse while something still refers to the file, and that shared order is why the two kinds sit
  together** — who refers to this, does the file exist, remove it — while the answers come from entirely different
  places (the machine list; every blueprint parsed for its `scripts` map), which is why it is a shape kept aligned
  by adjacency and not a helper. `resolve.py` builds the merged `(name, type)` resolution
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
  (`src/reliquary/codex/` package data: copy-out **on request only**, never overwriting home files;
  `seed_blueprint`/`seed_script` copy a closure by default or the single file with `only=`; `list_codex`
  names what the library holds and reports nothing of yours, `codex_blueprint_available` is the question a
  refusal asks so it can name the seed command), `machines.py` owns machine materialization under
  `cache/machines/<blueprint>-<n>/` — where **backend assignment** happens, before any image work: the
  blueprint's whole demand (control planes, media kinds, controllers, materialization modes) becomes a
  `backends.Requirements`, and a declared `backend` pins the choice — as does `backend-settings` for exactly
  one backend, which **narrows** the walk to it (`_backend_choice`: declared, else a lone section, else the
  walk; presence narrows, not content) — while an absent one walks the priority
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
  `resolve_machine` / the exec-run family — `get_machine_var`
  (the script→host scalar channel: a `machine.json` `variables`
  map under the op lock, cleared at `start` so a variable always
  reports the current boot, the `rlq`/`reliquary` key namespaces
  reserved; the script `set` verb is the channel's only writer —
  the host side only reads, per the CLI spec); the drive layer —
  the report and the in-band file family alike — is `drives.py`'s
  (below);
  where a machine lives, what serializes it and how one is named is
  `machine_state.py`'s (below); each mutating op carries an
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
  any declared drive; all three persist and survive stop/start — and **a
  script's `with` scope is a second caller of exactly these three**,
  capturing before it changes and calling them again to put the value
  back, under the same rules: a boot restore is refused on a running
  machine like any other write of that order, and the run fails naming
  what it could not undo rather than the state document gaining a
  writer under a different rule, D104),
  `drives.py` is **what a stopped machine's disks hold, and how the
  guest names them** — one module for one question asked two ways.
  `describe_drives` is the window onto all of it (D83): one
  machine-level report — declared and chosen facts per drive, the
  at-rest read per disk (backing, partitions, per-volume
  filesystem/label/BPB geometry), and the letter map with its
  undetermined drives — never phase-refused, because it answers from
  the record in `machine.json`: **read at every start's first step**
  (`read_drive_record`, the one edge `machines.py` has into this
  module), before the backend is engaged, so a running machine
  answers with this boot's starting state (`recorded: true`); the
  call reads a disk only when the machine is down and no record
  exists yet, and `refresh_drives` is the explicit stopped-only
  re-read for a layout changed behind the record. The in-band file
  family is the other half — `put_file` / `get_file`,
  `put_files` / `get_files` (a tree's contents, recursive, a copy and
  never a mirror) and `list_files` (one level or `recursive=`,
  returning a flat array of `{address, name, kind, size}` sorted by
  address, whose addresses the other four accept). All five address
  in guest terms — P17 — over a directory-source drive, stopped-only,
  with a non-vvfat target and an unmapped letter failing closed
  naming the gap (P11); one address form serves all of them, a
  directory spelled as a file is and the drive root sayable as `A:\`
  (`platform_dos.split_address` / `split_directory_address` /
  `join_address`), and the letter map itself is
  `platform_dos.drive_letters`, built from declared facts *and the
  volumes each disk actually holds* — read on the host, one letter
  per volume, a disk holding none taking none, cached per-drive in
  `machine.json` and cleared at every start (a guest repartitions
  only while running). A disk whose volumes cannot be read leaves
  every letter behind it unplaced and answers with the reason it
  could not be read, never the symptom — P10, D71 closed. **The two
  halves are one module because they answer from the same three
  facts**, and `_blocking_disk` is where that shows: which unread
  disk accounts for the unplaceable letters is chosen once, and only
  the wording — a list of unplaced drives, or one refused address —
  belongs to each caller. The drive seam is `_HostDirectory` and
  `_ImageVolume`, two adapters behind one interface (`writable`,
  `path`, `kind`, `entries`, `copy_out`, `write_file`,
  `make_directory`, `commit`, `close`) that `_resolve_address`
  chooses between; a directory-source drive *is* its host directory,
  and an image is opened where it lies through `at_rest` (P27) and
  never copied to be read. It stands on `machine_state` alone, never
  on the lifecycle, and `machines.py` re-exports its verbs as the
  layer's front door,
  `machine_state.py` is **the substrate the machine layer stands on** —
  where a machine lives (`machine_dir_path`, `machine_disks_dir`,
  `backend_dir`), how one is named (`machine_id_for` /
  `split_machine_id`, ids `<blueprint_name>-<machine_number>` with
  lowest-free reuse, `allocate_machine_id`), what serializes work
  against it (`blueprint_alloc_lock` for numbering, and the exclusive
  per-machine operation lock `machine_lock`, `.locks/<id>.op.lock`,
  taken by every mutating op), its `machine.json`
  (`write_state` / `load_machine_state` / `read_vm_state`), and the
  selector resolution `--blueprint` / `--machine` reach it by
  (`resolve_machine` / `list_machines` / `machines_for_blueprint`).
  It knows nothing of what a machine *is*: no backend, no adapter, no
  drive, no media. **Only what both halves need lives there** — phase
  transitions have one consumer and stay with the lifecycle above —
  and `machines.py` remains the layer's **front door**, re-exporting
  these names so a consumer above it reaches them in one place. The
  one module taking them from the substrate directly is `machine_handle.py`,
  which needs `read_vm_state` alone and would otherwise be back in a
  cycle with the lifecycle,
  `backends.py` is **the backend adapter seam** — the provider contract behind the semantic surface
  (design: `planning/design/backend-adapter.md`), deliberately *not* one of the application surfaces:
  the `BackendAdapter` contract (discovery, capability report, image materialization, start/stop, and the
  carrier session), the `Availability` / `Capabilities` / `Requirements` vocabulary the report and the demand
  share, the `backend-settings` contract (`settings_keys` — the keys an adapter's section may carry, empty
  being the honest default — and `validate_settings`, the shared unknown-key refusal an argv-shaped adapter
  extends with its own overlap rule; only the *assigned* backend's section is ever judged, no adapter being
  able to speak for another's vocabulary), `identity()` (the recorded-VM-identity record every adapter writes: backend, `backend-id`,
  per-start `token`, and an adapter-shaped `endpoint`), the registry (`adapter(name)`, `discover()`), and
  `assign()` — built over `evaluate(name, requirements)`, which reports availability and unmet
  requirements as **two answers rather than one verdict**, because whether this host has a backend and
  whether that backend could build this machine are two questions and a dry run asks only the second.
  `_set_adapter` is the test seam, as `credentials._set_provider` is for the keyring.
  `backend_qemu.py` is **everything that knows QEMU** — binary discovery, `qemu-img` image work, the drive
  and boot rendering a machine's state lowers into, the `backend-settings.qemu` hatch (`SETTINGS_KEYS` = `machine` /
  `args`, `RESERVED_ARGUMENTS` = what a blueprint field or the VM identity owns — case-sensitively, `-m`
  being memory and `-M` the machine type, and deliberately *not* `-device` or `-cpu`; `settings_args` both
  validates and renders, which is what makes a section a create accepted one a start applies, and it renders
  last so a caller's own arguments are the tail of the logged command line), the owned launch with its identity verification, `Qmp`,
  the carriers (`send_keys`, `text_screen`, `screenshot`, `change_medium`) plus the named native escape
  hatch `QemuSession.native()`. At-rest access is **not** this adapter's: opening a stopped machine's disk
  belongs to `at_rest.py`, and the adapter contributes only its `capabilities().at_rest` declaration.
  `at_rest.py` is **the at-rest translation layer** over the `remanence` dependency (P27), which is the one
  deep module for direct disk access: Remanence opens a raw or qcow2 image where it lies (the format decided
  by the bytes), claims it for the length of the access under its declared intent, composes and claims a
  backing chain immutable, discovers geometry, reads and writes FAT volumes reached through the partitions
  the loaded medium bears — each carrying the stable volume id its inspection report issued — and stands a
  durable undo journal beneath `commit()` so an interrupted commit is
  reconciled at the image's next open (D77). The image is loaded into a session as one medium under a
  declared device type (`mbr-sector-hd`: reliquary's drives are DOS's, MBR-partitioned and CHS-addressed),
  because a raw or qcow2 image says nothing about the drive that recorded it; releasing the medium ends the
  claim. What `at_rest.py` keeps is reliquary's policy: **the
  recognition claim** (D83) — FAT12, FAT16 and FAT16B over standard MBR primary/extended partitioning,
  everything else, FAT32 included, a named refusal in reliquary's own vocabulary, **partition types pinned
  value by value**; **the whole-disk rule** — a partition Remanence reports as unreadable refuses the disk,
  because a disk with a partition reliquary cannot account for is one whose volume ordering it cannot vouch
  for; **guest-address validation** — a name a DOS guest could not type is refused, never mangled; and the
  error vocabulary — Remanence's stable categories restated as `UnreadableImage` / `ImageLocked`, which the
  drive seam maps onto the standing rule ids. `geometry()` reports the drive's shape (partitions with their
  declared types, volume count, and the BPB's own CHS where it states one) as P10's *read on the host*
  source, blank-as-an-answer included.
  `backend_virtualbox.py` is the VirtualBox adapter (F50 lifecycle
  and VDI; F52 agentless-display carriers and FreeDOS parity).
  `backend_stubs.py` holds the two unbuilt adapters (VMware
  Workstation, Hyper-V): their host probe is real, they claim **no
  capability**, so assignment passes over them even where the
  backend is installed, and a pinned one fails preflight naming the
  gap.
  `control_display.py` is the **agentless-display control plane** — character-to-key mapping (`char_keys`),
  text-screen composition and
  the cursor-menu machinery, written once over the seam's text-screen contract (character rows plus opaque,
  equality-comparable per-cell attribute tokens) and never per adapter. **Key mapping is three layers, not
  one, and only the middle one is here** (D103): the language's portable `press` names are
  `script_validation.PORTABLE_KEY_NAMES`, `script_runner.resolve_key` maps those onto **the seam's key
  vocabulary — which is QEMU's qcode set**, and each adapter translates that into its own input events
  (identity on QEMU, `scancodes_for` on VirtualBox). So `char_keys` spells `spc` and `ret`, and VirtualBox's
  table has no entry for `space` or `enter`; the seam is named for the reference backend rather than carrying
  a third vocabulary no backend speaks.
  `text_recognize.py` is the **shared fixed-font recognizer** (F51) backends without VGA text memory
  use over a screenshot — same contract, one algorithm. **The glyph bank is the guest's, not
  Reliquary's**, and an adapter reading a live screen passes `bank=` its own host's font.
  **The axis is BIOS-drawn versus guest-drawn, and not which emulator** (T20). Both emulators
  install the *same* font on a text mode set — QEMU's vgabios merges its 19-glyph
  `vgafont16alt` into the bank it ships, VirtualBox ships the raw bank and applies the same 19
  at runtime from `vgabios.c`'s `load_text_patch`, and merged-VirtualBox equals QEMU's bank byte
  for byte. What differs is *who painted the screen*: the BIOS uses that merged set, while a DOS
  guest that loads its own CP437 font (FreeDOS does) paints the **unpatched** design, `W`, `m`
  and `T` among the 19 — enough to miss a wait on any word carrying one. So **no single bank
  reads a whole run, and nothing in a framebuffer says which font painted it** — which is why
  the recognizer takes *every* font a host offers and matches each cell against all of them,
  rather than choosing. `bank=` accepts one bank or many (`as_banks`); `_all_glyph_bits` unions
  them per code, so shapes the fonts agree on are scored once and the cost is proportional to
  how much they actually differ — 275 entries against 256 for a stock VirtualBox, about 5% on a
  read. Ties go to the first bank, which keeps two runs on one host agreeing. This would bite
  QEMU identically if anything ever recognized a QEMU screenshot rather than scraping its text
  memory. Each backend answers the font question the same way — `guest_glyph_banks(cache)` on
  `backend_virtualbox` and `backend_qemu` alike — with `banks_from_files` / `banks_from_binary`
  collecting every bank in the installation's binaries **plus every variant an override table
  behind one would install**, anchored on the classic `A` every CP437 bank shares and failing
  closed by name where the install holds none. That extraction is structural, not a table
  Reliquary knows by name: a run of `(code, rows...)` entries whose codes ascend, closed by a
  zero code byte, with runs for other glyph heights stepped over — so a build carrying a
  different set is read on its own terms. QEMU's own plane never needs any of this (it scrapes
  text memory, where the guest already resolved its characters); it exists so the question is
  answered identically for both rather than only where it bit, and a stock QEMU yields one font
  because its bank ships already merged. **The fonts are extracted on demand and cached, never
  vendored** — `cache/support/<backend>/cp437-8x16-banks.bin` via `text_recognize.cached_banks`,
  every bank concatenated so the count stays the backend's business, wholly regenerable
  like everything under that root, so a truncated cache file is re-extracted rather than raised
  on. The cache root reaches the adapter as `Machine(cache=)` → `adapter.session(vm, cache=)`, a
  plain resolved directory and **not derivable from the machine directory** (`machines` is
  independently placeable); `None` simply re-extracts, since this is a speed concern and never a
  correctness one. Not vendoring is the licensing policy (CONTRIBUTING.md) as much as the
  engineering: the glyphs belong to whatever emulator the host installed. The shipped
  `fonts/cp437_8x16.bin` remains **only** as `recognize`'s default and what `render` draws
  fixtures with, so the suite needs no hypervisor — and it is **drawn rather than dumped**
  (`tools/gen_cp437_font.py`, D82: the incoming test is *could this ship inside a proprietary
  product?*). Its ASCII and box-drawing shapes are authored; every code nobody drew gets a
  computed Reed–Muller codeword, 64 of 128 pixels from any other, because the one thing the bank
  must be is **all 256 codes distinct** — an undrawn code came out blank, collided with the
  space, and could never be recognized. It is not a VGA face and does not have to be, which is
  why `CLASSIC_A` — the anchor `bank_from_binary` locates a *real* bank by — is deliberately
  **not** in it; a test wanting a findable bank says so via `tests/vga_bank.py`.
  **Whether a screen has stopped changing
  is not decided here** (F49): `_settled_screen` and `_menu_baseline` are callers of `screen_stability` rather
  than owners of a copy. What stays is what was never about settling — whether a keypress changed anything at
  all (`None` reads as a dead key) and which row the highlight moved to, both classification.
  `screen_stability.py` answers whether the guest has **stopped drawing** — the frame-level question
  `stable=` cannot ask, a condition being able to hold perfectly on a screen that is still painting. It
  compares **cells, not rows** (row granularity cannot separate a blinking cursor from an arriving line of
  text) with the **text+attribute pair as identity** (a cursor menu moves its selection by attribute alone),
  and measures both halves over **wall-clock windows rather than sample counts** — otherwise a denser poll
  reaches a different verdict on the same guest, and a recorded run and a production run could take different
  paths through one script. Stability is the unmasked fraction that held still over the last 200ms, judged
  against 0.99: 20 cells of 2000, a quarter row, which is the gap between furniture (a cursor 1 cell, a clock
  8) and content (a row of text, 80). Decoration is **recurrence** — a cell changing 3+ times within 1s —
  excluded from that fraction, with `_menu_baseline`'s majority-churn bail-out carried over (mask nothing,
  compare raw). A window never observed answers `stability=None` rather than a verdict the cadence produced
  (P11). Delivered as F47, and **the only implementation of the measure in the tree** (F49): its three consumers
  are `exec`'s completion test (F45, below), the script language's `stability=` (F48, below), and the menu
  machinery, whose own hold-for-two-reads and learned animation mask were special cases of it and were deleted
  rather than kept beside it. One interaction the cut exposed and `control_display._BASELINE_READS` now records:
  **settling and recognizing decoration want different amounts of looking** — a clock moves two cells and is
  settled on sight, but nothing can know it is a clock until it has ticked repeatedly, so a baseline that stops
  at the first settled frame hands back an empty mask.
  `interaction.py` defines capability protocols, `interaction_agentless.py` contains the concrete agentless DOS
  adapter (prompt-based readiness and command completion — **a prompt is a candidate, not an answer**, held
  until `screen_stability` says the screen under it settled, because one arriving mid-scroll would otherwise
  slice the output at a boundary that never existed, F45; the poll ramp gains a third rung for that rather
  than losing its second — `_ECHO_POLL` catches the echo, `_PROMPT_POLL` waits a prompt out cheaply, and
  `_SETTLE_POLL` confirms one, dense reads being spent only where the question has become "is this screen
  finished?"), `machine_handle.py` is the backend-neutral machine handle — **singular, and named for what it
  holds**: the package spells its collective engine modules in the plural (`media.py`, `properties.py`,
  `backends.py`, `machines.py`), and this one is a handle type rather than a family engine:
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
  effective timeout and quiescence gate, and every guest-input verb's effective `pacing` — the settling gap
  before its first
  key event, D60 — each with the scope that supplied it. **`stability=` is `pacing`'s opposite number** (F48):
  a proportion rather than a duration, resolved over the ladder statement > branching wait > phase > header >
  built-in 0.99, sitting on observations where pacing sits on the four input verbs — each guard on exactly the
  statement kind whose hazard it addresses, so neither needs position-sensitive semantics. It sits where
  `stable` cannot, and the divergence is principled: `stable` qualifies a match, so one must exist, while
  `stability` qualifies the frame a compare runs on, and a frame exists at every sample — which is also what
  makes a default possible at all. A sample below the gate is not one any condition is judged on, and in a
  branching `wait` an unsettled frame evaluates **none** of the handlers. **The gate never causes a failure on
  its own**: where it never got to measure the condition is judged on what is there, so the "a timeout means
  samples were taken, never that nobody looked" invariant survives; where it measured and the screen was
  moving, the expiry names it. `stability=0` turns it off and costs nothing — the escape for a screen the
  default refuses; `format_plan` and
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
  **The one construct added since the vocabulary was set is `with`** (F54, D104), the scoped
  machine-state change: a block whose head is `boot`, `insert` or `eject` and whose exit puts
  the target back to what it held on entry, on every outcome the runner reaches. Three things
  about it are load-bearing across the layers. **`boot` states a prefix and is deliberately not
  `set-boot`** — the drives named come first and the machine's own order follows, so a stage says
  what it boots without restating an order it is not changing, and the two spellings keep two
  meanings. **The scope is dynamic**: it holds while control is *inside* the group, so the
  parser flattens the phases out (`Script.phases` stays the one flat namespace `goto` and `entry`
  address) and records only `phase_scopes`, the chain around each phase — which is the whole of
  what a transition needs, and is why every layer above the parser is unchanged by the construct.
  **The grammar can no longer split the two script shapes**, a `with` head saying nothing about
  which shape follows it, so the body is one permissive unit list and V10 and V2 decide it where a
  diagnostic can name the shape. `script_runner.py` executes that tree against
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
  wherever the interrupt happened to land.
  `transcript.py` is screen-transcript capture and reconstruction,
  and **the module is not an application surface** (D98): the
  `.rlqt` format carries no stability guarantee and no `docs/spec/`
  entry, so changing it is housekeeping — while the *invocation* is
  surface and lands on S1/S2 in the same change (`--record <path>`
  on `run-script`, `run_script(record=)` on the session). The
  capture wraps the **carrier seam** — the adapter session's
  `text_screen` / `send_keys` / `screenshot` / `change_medium` —
  so it is backend-neutral by construction: `RecordingSession` is
  that wrapper, and `ReplaySession` stands a fake session at the
  same seam, which is what lets the whole interpretation layer
  above run unmodified over a recording. Every frame carries a
  sha256 of its canonical `(rows, attributes)` pair, checked at
  reconstruction, so a bug or a hand-edited fixture fails loudly
  rather than yielding a screen that never existed. **A bound
  secret reaching the guest stops the recording** for the rest of
  the run — the same rule that suppresses the automatic failure
  screenshot above, applied to the other artifact a run can leave
  behind. `cli.py` owns command parsing, exit codes
  (`errors.exit_code` over one `ReliquaryError` arm), and the
  output discipline. `_build_parser()` registers the 48 commands
  through ten family builders and returns `(parser, commands)`, and
  **`_COMMANDS` is derived from that rather than declared** — it was
  a hand-kept frozenset, which is one more list of the same words to
  keep in step; do not restore it. **Builder call order is `--help`
  order**, so the groups follow the blocks this module has always
  carried rather than a tidier taxonomy: `fetch-media` sits alone
  between the script and authoring families, and `add-media` sits
  with cache reclamation. `_dispatch` routes on literal command
  words and is the one list still kept by hand; `test_cli.py` walks
  its source and pins it to the registered set in both directions,
  and an unrouted command reaching the fall-through is an
  `InternalError` (exit 1) rather than the silent `0` it once
  returned. It is the session layer's first
  consumer — one `Context` built per invocation (flags, then
  environment, then the default home), one `Session` opened on it,
  every command driven through session methods, the codex and
  locate seam taking the record directly (D87) — and
  `__main__.py` preserves `python -m reliquary` execution.
- `pyproject.toml` packages `reliquary` as the `reliquary` command. **The two artifacts carry different things**: the
  wheel is the runtime alone, the sdist is the runtime plus what verifies it. The src-only package search keeps the
  repository-root suite out of the wheel; `MANIFEST.in` grafts `tests` into the sdist (D105) and prunes `planning`,
  `docs` and `tests/source_tree`. The suite is grafted whole rather than left to setuptools' default rules, which take
  top-level `tests/*.py` and none of the fixture trees beneath it — `tools/check_dist.py` names those trees one by one
  for that reason, and names the three pruned trees as forbidden.
- `tests/` is the suite, and **pytest is the runner** (D106) — **pytest-native throughout** now that the sweeps have
  finished (F56–F60), covering core helpers, guest program runs, lifecycle ownership,
  media acquisition, blueprints, machines, and scripts. Its shared machinery is named where it is used: the two
  conformance corpora and the recognizer's golden PNGs read through `tests/corpus.py`; the script language's static
  rules are one parametrised case table; the two backend adapters answer one parametrised seam contract; and the
  command manifest, the session veneer and the documented examples each report a node per declared item.
  `tests/conftest.py` is the suite-wide configuration: the
  `integration` marker's `--integration` option, the deselection that keeps the tier out of a default run, and the
  home those runs work in. **`tests/source_tree/` is the exception that ships nowhere**:
  the tests that read the *repository* rather than the package — prose documents, the maintainer records, the
  open-problem catalogue. Shipped, a sweep over `docs/` and `AGENTS.md` would find neither and report success on a
  fraction of its job, so it is kept where it cannot run at all instead. Nothing there needs a `skipUnless`, and a new
  test belongs there exactly when it reads something a released artifact does not carry.
- `README.md` is the human guide.
- `CHANGELOG.md` records release-facing changes.
- `planning/README.md` is the map of the maintainer-facing planning machinery, and the place to start. The
  directories are the classification, and they hold the **same three filenames** — `USE-CASES.md`,
  `ARCHITECTURE.md`, `FEATURES.md` — because they hold the same three artifacts in two states:
  `planning/proposed/` is argued but not pledged, and nothing is worked from there; `planning/pledged/` is
  approved but not yet delivered. Promotion is by *moving* a document or an entry, and the commit is the
  pledge record. The **planning root** holds what never moves and so has no state — the map, the vetting
  rule (`SURFACES.md`), the adjudication record (`DECISIONS.md`, which spans open, pledged, refused and
  retired alike), the task queue, and the sequence ledger (`SEQUENCES.md` — the high-water marks every
  handle sequence issues against, one file on `main` because a search sees only the branch it
  stands on). Design sits with what it serves: `planning/proposed/design/` and
  `planning/pledged/design/` for a feature's own design, `planning/design/` for open design problems serving
  no single feature — the whole-system view itself (the seams model and the P-numbered principles) is root
  `ARCHITECTURE.md`. Once a surface ships, its normative spec moves to `docs/spec/` — current truth does not
  live under `planning/`.
- **There is no roadmap** (D42): `pledged/` says the project will do it and nothing about when, so the absence
  of order in `TASKS.md` holds equally for pledged features, the only binding order running inside a feature.
  **Features carry F-numbers and tasks carry T-numbers** — the handle a dependency, commit or decision points
  at — which unlike U-, P-, S- and D-numbers **evaporate on delivery**, retiring unreused, gaps being history
  rather than a promise. A T-number is issued at entry to `TASKS.md` (a task has no proposed state), and every
  handle sequence issues against `planning/SEQUENCES.md`'s high-water marks, a struck task or an unmerged
  branch leaving the searchable record incomplete. Designs take
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
- The worked FreeDOS example is the shipped codex itself (`src/reliquary/codex/`): the `freedos.rlqb` blueprint with
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
  `src/reliquary/schemas/`, because code consumes them:
  `blueprint-schema-v1.json` (versioned v1 so editors can bind it
  today) and `machine-state.schema.json`. `docs/spec/` refers to
  them rather than holding them. Both must stay synchronized with the
  prose specs, **which are normative** — a schema captures only the
  structural subset JSON Schema can express, and schema validity
  never implies document validity. The shared valid/invalid
  conformance corpus (`tests/fixtures/conformance/blueprint/`,
  `test_conformance_corpus.py`) runs every fixture against both the
  parser and the schema so the two cannot drift. Placement rules
  live with the documents they govern: `planning/README.md` for the
  planning machinery, `docs/spec/README.md` for spec, reference,
  and guide.
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
- **A corpus is worth what its harness can prove ran**, which is why
  both read through one helper — `tests/corpus.py` (F56). Every
  fixture is a **collected node named for its file**, in every check
  that judges it, and each bucket's count is **pinned where the
  fixtures are gathered**, so a bucket that stops loading is a
  collection error rather than a green run over nothing. That is the
  defect D106 was decided on: the blueprint corpus ran against the
  parser and *not* the schema while claiming the two cannot drift,
  because a loop of fixtures inside one `subTest` test reports the
  same single pass whether it checked all of them or half. A check
  that partitions a bucket by a marker is the same failure in
  miniature, so `// warns:` and `// schema: rejects` are each asserted
  in both directions by **one** check over the whole bucket rather
  than by two over its halves. A third corpus inherits all of it by
  calling the same two functions.

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
extraordinarily important. Every command maps one-to-one onto a `Session` method with the same semantics
(P26); nothing is CLI-only outside the codex family's named exception, and no public capability may be
unreachable from the CLI — it is the fallback binding for every language without a native one. A change to
this surface lands on both presentations in the same change, never deferred to a later pass.

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
`machines`. Each starts **unassigned**; a value arrives in the `Context` record a session is opened on — the CLI's
`--<name>-dir` flags and `RELIQUARY_<NAME>_DIR` variables land there through its construction step — and the rest
**derive** — `home` gives default locations to `blueprints`/`scripts`/`cache`,
and `cache` (assigned or derived) gives them to `media`/`machines`. Derivation reaches only what is still unassigned,
so `cache` alone conjures no home and `machines` alone leaves `media` where the rest of the resolution puts it.
**A record with no home is a fail-closed `StaticError` (`dir.unassigned`) at the session's door**, naming the home —
an assigned home reaches all six by derivation, so nothing a session does can find a directory unassigned; a bare
`Context` may still be built and filled before a session is opened on it.

The surfaces differ only in whether an assignment is made for the caller. **The CLI** gives `home` its default
(`Documents/reliquary`, falling back to `~/reliquary`) whenever neither a flag nor the environment named one, so one
assignment reaches all six and the refusal is unreachable at the keyboard — **a property of that default, not an
exemption from the rule**, which is what keeps it true if the default ever changes. **The embedding API** assigns
nothing — the session demands its home at the door; that is the whole safety of the design. Honouring the environment
is likewise the CLI's private construction step and never the library's: the engine reads no environment at all.

`Context` is a **plain record** of the six optional directory paths plus the selected properties file (P26's cargo
ruling) and nothing else — no methods, all resolution in `home.py`'s module functions — because a handful of nullable
strings binds cleanly from C or Java where keyword arguments would not
(P7). There is no process-global assignment: the session pins the whole record once at construction, from that record
alone, so two sessions in one process are unremarkable; the engine functions underneath take the record as their
`context=` (a bare string is shorthand for `Context(home_dir=...)`), which is the seam the veneer forwards over. The
CLI builds **one `Context` per invocation** — flags, then the environment, then the default home — and opens one
`Session` on it, driving only session methods (the codex family and the locate seam, veneerless by D87, take the same
record directly). `machine_handle.py`'s and the adapters' own `home=` parameters are a different,
narrower concept — an already-resolved plain directory (sometimes a machine's own materialization directory standing
in for one), not a `Context`; they were deliberately left alone.

**Containment is no longer topology.** With six independent roots, "under the home" is not a claim Reliquary can make;
what P12 now requires is that Reliquary **writes only where it was told to** — never beside the module and never into
a source repository during normal use.

**Nothing resolves out of the codex** (D88), on either surface and under no flag: the directories are the sole
sources, a miss fails closed, and the refusal names `rlq seed-blueprint <name>` where the library holds that name.
The seeding axis that once decided this — autoseeding, the surviving half of the retired asset-root knob — was
deleted rather than defaulted, because a knob that can be turned on is one CI will turn on and a silently supplied
blueprint is a bug that surfaces on someone else's machine. That restores **P4 to an absolute** and retires D59's
amendment of it. `assets.py` is correspondingly one source
(`DirectorySource`) reading each kind's own directory, walked recursively by extension, and carrying no seeding
property at all. An asset's identity is its declared `name` (id-safe) else its filename stem;
within-source effective-name collisions are errors. Selection scoping: `--blueprint <name>` matches only machines
whose recorded `blueprint-source` equals this invocation's resolution (a sourceless machine matches by name alone).
**Seeding is the one way the library reaches a tree**: `seed-blueprint` / `seed-script` (there is no `seed-media`) write
into the assigned `blueprints` / `scripts` directory wherever it is, project tree or home alike — copy a first draft,
commit the copy. All three codex verbs — those two plus `list-codex` — are **CLI-only under P6's named exception**
(D87): a library that changes in a point release is not something a program may bind against, so `src/reliquary/__init__.py`
exports none of them and the parity test reads the exception from `docs/spec/api.md`'s codex-family row.

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
  script `set`s, cleared on start — D36. **The recorded snapshot is the
  machine's *shape* and only that**: `parameters` and `scripts` are blueprint
  fields deliberately outside it, read from the blueprint file at each
  invocation, absent from the digest, and needing no `apply` to take effect —
  they name what to run against a machine and what to bind into it, never what
  it is, D101),
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

**The session is the only door** (P26): the exported `Session`,
opened on a home (a bare path or a `Context`), carries one thin
veneer method per ambient-state verb — the machines lifecycle with
its exec, file and variable families, the media family, blueprint
authoring, asset resolution, properties/credentials/binding, and
`run_script` (whose `dry_run=` returns a `DryRun` rather than a
`ScriptRun`) — over the engine modules, which are internal. Beside
it the root exports the vocabulary: the types, the errors,
`Context`, `default_home_dir()`, the free parsers, the
guest-console family at the carrier stratum, and the backend seam's
read-only vocabulary. The
milestone-1 root-home runner surface — `workflows.py`'s
`Runner` / `MachineConfig` / `run_guest_program` / `run_task` / `start`,
the old root-home state files (a root `machine.json`, `drives/`,
`vm.json` — distinct from the per-machine cache `machine.json` this
model writes), and the legacy `drives.py` auto-discovery — was absorbed
into this model and deleted, as the module-level verb exports later
were when the door closed (no backward compatibility before 1.0). The user-facing reference is
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
  (`script_runner.py`) are in-repo consumers of this surface and
  drive the same engine seam the session's veneer drives, nothing
  deeper — the flat engine functions with their `context=`, exactly
  what a session method forwards to, never a private helper below
  them.
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
  supported configuration, and **the bar is high**. The suite runs
  from two places — the repository, and an unpacked sdist (D105) —
  and **a missing document is not one of the cases**: a test that
  reads what a released artifact does not carry goes in
  `tests/source_tree/` and ships nowhere, rather than carrying a
  guard that turns "cannot do its job here" into a quiet pass.

  **The default run skips nothing, in both places**, and that is the
  assertion — no count stands in for it any more (F57). The opt-in
  FreeDOS integration runs, one per backend (QEMU and VirtualBox),
  carry `@pytest.mark.integration` and are **deselected** unless
  `pytest --integration` asks for the tier: a marker says the tier
  was chosen, where a skip could not say whether it was chosen or
  suffered. So **any** skip is a defect to fix, not a configuration
  to tolerate. That the two runs differ — 2,140 tests from the
  repository, 2,086 from an sdist, two deselected in each — is the
  isolation working; neither skips. Selecting the tier on a host
  without the backend is a **failure naming the gap** (P11) and not a
  skip either: the run was asked for.
- Pillow is the image library: screenshot conversion uses it, and the
  planned landmark assets (decode normalization, pixel comparison, PNG
  text chunks) build on it rather than on hand-written encoders.
- Support Python 3.12 and newer, and **check it** — the floor run in
  "Required checks" is what makes that a claim rather than a hope. It was
  `>=3.9` until the check was first run and 3.9, 3.10 and 3.11 all failed
  (D95).
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

**A first-party dependency sits outside the tiers.** `remanence` is GPL-3.0-only and imported, which the table would
refuse — but the tiers exist to protect the relicensing reservation from code the project cannot acquire title to,
and remanence is the owner's own work: copyright held whole by Paul Galbraith, contributions assigned under that
project's own CLA, published from `ferroteca/remanence-lib`. Exercising the reservation relicenses both works
together, so nothing is forfeited. The qualifying test is **ownership, not licence**, and it is conditional:
first-party standing holds only while the dependency's copyright stays whole in the same hands, and one that stops
qualifying reverts to the table — where GPL-imported is tier 3.

The current runtime closure is tier 1 throughout except `remanence` (first-party, above) and `qemu.qmp`, which is
tier 2 and discussed under prior art
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

**uv provisions and owns the environment** (D94). One command creates
`.venv`, installs the project editable, and installs the `dev` dependency
group:

```powershell
uv sync
```

`uv.lock` is committed, and it is what makes "the environment the suite
passed in" reproducible — which matters here because under P22 the suite
*is* the gate. `uv sync` reproduces the lock exactly; `uv lock` is what
deliberately moves it. Do not install development tools globally, and do
not hand-manage `.venv` — it is uv's.

Runtime dependencies stay under `[project].dependencies`. The `dev` group
is `jsonschema` and `pytest`: the build frontend and the upload tool both
left it when uv absorbed their jobs, and pytest arrived as the runner
(D106). Both are hard requirements of the suite in the sense above —
imported and invoked, never guarded. The `>=8.4` floor on pytest is the
release that made `--disable-plugin-autoload` a command-line option, which
is what lets the project's own configuration turn autoload off rather than
leaving it to whoever runs the suite.

## Required checks

Run checks through uv, which uses the locked environment.

```powershell
$pythonFiles = (Get-ChildItem src/reliquary,tests -Filter *.py).FullName
uv run python -m py_compile $pythonFiles
uv run pytest
uv run --python 3.12 pytest
uv build
```

**The third line is the floor check, and it is not optional.** The
supported floor is a published claim (`requires-python`), so it is tested
like any other — the same reading AGENTS.md already applies to host
platforms, where an untested platform is an unclaimed capability rather
than a quiet promise (P11). uv installs the interpreter itself, so the
check costs one line. It was added when the floor turned out to be wrong:
`>=3.9` was claimed and unexercised, and 3.9, 3.10 and 3.11 all failed
(D95).

**The suite's own configuration is `[tool.pytest.ini_options]`, and it is
written for a stranger's environment rather than this one** (D106): the
suite ships in the sdist (D105), so `--disable-plugin-autoload` means no
plugin the project did not ask for can change what a run collects,
`--strict-config` and `--strict-markers` make an unreadable option or an
undeclared marker an error instead of a silent no-op, `testpaths` lets a
bare `pytest` find the suite, and `minversion` refuses a pytest too old to
honour the first of those. Nothing there is a preference — each line is
there so that a run somewhere else collects what a run here collects. The
one declared marker is `integration`, the opt-in tier; `tests/conftest.py`
owns the `--integration` option that selects it, the deselection that is
its default, and the `integration_home` fixture the runs work in.

`uv build` builds an sdist and then a wheel from that sdist, which checks that the source archive is complete.
After packaging metadata changes, inspect `PKG-INFO` for at least the name, version, Python requirement, and runtime
dependencies in both built artifacts, then run `uv run python tools/check_dist.py`, which asserts what each artifact must
carry — the grammar, the schemas and the codex in the wheel; the suite and each of its fixture trees in the sdist —
that the wheel carries no tests, and that the sdist carries none of `planning/`, `docs/` or `tests/source_tree/`. It
exists because nothing inside a released artifact inspects the artifact: package data is what disappears silently, and a
missing `.lark` grammar breaks an installed Reliquary while every source-tree test still passes.

For release-facing packaging changes, **two checks, and they answer different questions.** The archive's *completeness*
is proved by the build itself: `uv build` builds the wheel *from* the sdist, so a source archive missing anything the
build needs fails there rather than silently — and that holds whether or not the suite ships. What the shipped suite
buys is the other question, the one only a stranger can ask: **unpack the sdist outside the tree and run it there**,
which is what a downstream packager does at package-build time on a platform this project never tests.

```powershell
tar -xzf dist/reliquary-<version>.tar.gz -C <scratch>
cd <scratch>/reliquary-<version>
$env:PYTHONPATH = "src"; pytest
```

That interpreter needs the dev group — `pytest` and `jsonschema` — which is the cost D106 took deliberately: `python -m
unittest tests` is no longer the entry point, and with the conversion finished (F60) it collects nothing at all —
the hook that made it work is gone. It was taken because pytest is packaged everywhere a packager works. Expect
**2,086 tests, two deselected and none
skipped**, against the repository's 2,140 ("Test expectations", above): the difference is `tests/source_tree/`, which
ships nowhere, and a *skip* there is a defect exactly as it is here. `tests/conftest.py` ships with the suite, so the
integration tier is deselected in a stranger's run exactly as it is here. Install the wheel into a clean environment and check it by using it —
`rlq --version` and an import — since it carries no suite to run.

**Publishing is `uv publish`** (D94), which uploads `dist/*` to PyPI; with
no CI (P22) there is no trusted-publishing path, so it takes a token
(`UV_PUBLISH_TOKEN` or `--token`), and `uv publish --dry-run` walks the
whole path without uploading. `twine check` is deliberately gone: its
rendering job is an RST problem and the readme is markdown, the index
validates and rejects bad metadata itself, a rejected upload does not
consume the version, and `tools/check_dist.py` is this project's real
artifact gate. Reopen that if the readme ever stops being markdown.

Run `git diff --check` before handing work back.

Hands-on tests require QEMU. Use `--home-dir` with a scratch or deliberately reused test home rather than polluting the
default per-user home.

The FreeDOS install+verify integration tests are opt-in (deselected in
the default suite; need network for the LiveCD on a cold home). `--integration`
selects the tier, and it is the whole gate — naming the module without it
deselects it just the same. QEMU is the default backend; VirtualBox (F52) pins
``backend: virtualbox`` on the seeded blueprint and needs ``VBoxManage`` on
``PATH``. Give the two runs *separate* reuse homes — the same machine id cannot
span backends:

```powershell
# optional: reuse a home so cache/media survives reruns
# $env:RELIQUARY_INTEGRATION_HOME = "C:\Temp\reliquary-integration"
uv run pytest --integration tests/test_freedos_install_integration.py
uv run pytest --integration tests/test_freedos_virtualbox_integration.py
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
hypervisor (`tests/fake_backend.py`, installed with `backends._set_adapter`) —
no unit test may probe or launch a real backend:

- a requirement no candidate can honor fails closed naming the backend *and* the
  requirement, before any image work
- the priority walk takes the first backend both available and capable, so availability
  alone never wins and the order never stands in for a capability check
- a `backend-settings` key the assigned adapter does not define is refused at
  materialization, an argument restating a first-class field or the VM identity is
  refused naming its owner, and an inert section (another backend's) is preserved
  without being judged
- a declared `backend` skips the walk, and an unavailable or incapable one fails closed
- a stub adapter claims no capability even where its backend is installed
- the machine model hands the adapter a resolved state and gets an identity back: no
  backend argument is composed above the seam, and no port is read there

**What every *built* adapter owes the seam is one parametrised contract**
(`tests/test_backend_contract.py`, F59) rather than a near-identical method in each
backend's own module: the name it answers to everywhere, the capability report, its
image extension, discovery found and absent, the host font it reads and caches, and the
refusal to command a VM whose recorded identity does not match. Each check is a node per
backend, so a requirement cannot be honored by QEMU's tests and quietly missing from
VirtualBox's (**P25**). A **driver** is all a backend contributes — where its executable
is found, where its font lives, how a mismatched stop is aimed — so a third adapter
inherits the contract by adding one rather than by copying a file. What stays in
`test_backend_qemu` / `test_backend_virtualbox` is what only that backend knows: qcow2
against VDI, argv against `VBoxManage` verbs, QMP against scancodes.

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

### The test idiom

**Every test is pytest-native** (D106), and the policy now has nothing
to exempt: a bare `assert`, a fixture where `setUp` would have been, and
`parametrize` where a loop or a `subTest` would have been. The last is
the point rather than a style note — a parametrised case is a collected
node whose count is an assertion, and a `subTest` is not, which is how
the conformance corpus came to run against the parser and not the schema
while claiming the two cannot drift. **No `unittest.TestCase` and no
`subTest` survives anywhere in the suite**; either arriving in a new test
is a regression, not a style preference.

`unittest.mock` **stays**, and is not what changed: it is the mocking
library, the runner is what pytest replaced, and nothing supersedes it.
The stdlib preference stands everywhere else — pytest is one dependency
judged compelling, not the bar lowered.

The conversion ran as five sweeps — F56 took the two conformance
corpora, which is where the shared parametrisation helper
(`tests/corpus.py`) lives; F57 the two integration runs, which needed a
fixture the older idiom cannot be given; F58 the seven script-language
modules; F59 the ten machine and backend ones; F60 the remaining twenty.
`python -m unittest tests` went with the last of them: with nothing left
for it to collect it would report success over an empty run, so
`tests/__init__.py` no longer carries the `load_tests` hook that made it
work.

**A sweep keeps the count except where it deliberately raises it**, and
the exceptions are the reason for converting: a `subTest` loop becomes
one node per case, and a table becomes one node per row. F58 is the
worked example — the script-language cluster's 350 tests became 426,
every one of the 76 either the V-rule table or a `subTest` loop that
stopped hiding its cases, with no assertion added or dropped; F59's
460 became 575 the same way, the veneer roster and the fixture
directory among the tables that stopped reporting one pass for all
their rows; F60's 470 became 594, mostly the command manifest, whose
thirty-seven declared capabilities each report for themselves now. A
count that moved for any *other* reason is a lost test.

**A flattened module's function names are its collision surface.** Two
`TestCase` classes may each hold a `test_a_running_machine_is_refused`;
at module level the second silently replaces the first and the count
drops by one. A sweep checks the count per module for exactly this,
and a name that has to differ says what it is about rather than
gaining a suffix.

**A static rule is exercised from a case table, not a method per rule**
(`test_script_validation.py`): each case names the rule it drives and is
a collected node named for it, and one parametrised check walks
`script_nodes.RULE_OF`'s range so a rule the language gains with no case
fails as a named missing rule. The table carries a case for the tiers
below it — the lexer's, the placement matrix's — so that check needs no
list of exemptions, which would be one more list to keep in step.

**A corpus of fixture files reads through `tests/corpus.py`** rather
than growing its own glob: `fixtures` pins the bucket's count at
collection and `parametrize` names each node for its file. A check over
a vocabulary the *package* declares — a schema's phase enum — is not a
corpus and parametrises directly.

## Documentation maintenance

README.md is a human-facing guide to what Reliquary does, why it exists, and how to use it. Keep it explanatory and
task-oriented. Do not move agent instructions, implementation constraints, roadmap discussion, or maintenance notes into
it.
When Packer and Vagrant are mentioned together in prose, name Packer first and Vagrant second.

After changing commands, flags, paths, behavior, or Python interfaces, update README.md, CHANGELOG.md, and this file
wherever affected. The CHANGELOG is history, not documentation: everything under a released version header records
what was true at release time and stays byte-for-byte as released — stale paths, broken links, renamed concepts, and
superseded wording included; they are the historical record, and "fixing" them falsifies it. Corrections and
follow-ups get new entries under the unreleased section, never edits to released text. The one exception is removing
private or legally problematic content: redact minimally — replace or drop the problematic text, never reword or
modernize around it — and record the redaction as an entry of its own release. The unreleased section is freely
editable until it ships. Validate documented CLI syntax with `reliquary --help` and subcommand help.

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
