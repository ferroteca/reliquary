# AGENTS.md — repository guidance

This is the canonical, agent-agnostic guidance for working on Reliquary. Human usage documentation belongs
in [README.md](README.md); keep this file focused on repository structure, engineering constraints, verification, and
maintenance context.

## Write plain English

Write every document, comment, and commit message in plain English: short sentences, concrete nouns, say
what actually happens. Do not write dense, metaphorical prose — invented images like "a door that trusts a
recorded phase," or unexplained jargon like "the seam," "fails closed naming itself," "the number retired."
If a sentence needs decoding before it says anything, rewrite it.

**Much of this repository's own existing prose (this file included) is written in exactly that dense
style, built up by agents each imitating the last. That existing text is not a model to follow — it is
the problem.** Do not treat "match the surrounding style" as a reason to write more of it, here or
anywhere else in the project. When you touch a section written that way, rewrite it in plain English
rather than extending its voice.

## Project state and layout

Reliquary is an OS installation scripter built on its own generic QEMU
runner, with DOS as the default and currently only complete platform
workflow:

- `src/reliquary/` contains the library and CLI.
  - `__init__.py` re-exports the package's public names.
  - `errors.py` defines the error classes. `ReliquaryError` is the base class every deliberate error subclasses.
    Four subclasses map to exit codes: `StaticError` (2), `PreflightError` (3), `RunFailure` (4), and
    `RunCancelled` (5 — a sibling of `RunFailure`, not a subclass of it). `errors.py` also defines the
    `exit_code` / `outcome` mapping that the CLI and the terminal event both read.
    These four exit codes describe every surface, not just a script run (D58): which one applies depends only on
    whether the authored input was malformed, the world didn't satisfy that input, or the work itself failed —
    never on whether a script was involved. So a malformed blueprint is a `StaticError`, and a machine that
    doesn't exist is a `PreflightError`.
    Exit code `1` always means a bug in Reliquary, never a mistake by the caller. There are two ways to get it: a
    deliberate `InternalError` (an invariant Reliquary caught itself violating) or an accident — an exception
    that was never wrapped as a `ReliquaryError`. Every deliberate `raise` in the package must raise a
    `ReliquaryError` subclass, never a bare builtin exception: `test_errors.py` checks every `raise` in the
    package for this, since callers are expected to catch everything with `except ReliquaryError`.
  - `events.py` owns the run event stream: the `Event` envelope (`seq` / `time` / `elapsed` / `kind`, plus fields
    specific to that kind, flattened when serialized), the `EventStream` that records and renders events as they
    happen (redacting every string through the run's set of secrets, and updating a live display without
    recording each tick), and `note()` — a helper that emits an event if a run is in progress or prints to
    stderr otherwise, so a media fetch outside a run still reports honestly.
  - `progress.py` owns how events are rendered: `resolve_mode` (defaults to `auto`, which checks whether stderr
    is a tty), `describe` (produces the one human-readable line per event that both human-facing modes share),
    and the `pretty` / `plain` / `jsonl` renderers. The output rule is enforced here: the human modes (`pretty`,
    `plain`) render everything to stderr and leave stdout empty; `jsonl` is the only mode that writes to stdout.
  - `home.py` owns the six working directories that can each be placed independently — the cascade that derives
    unset ones from the ones that are set, the error raised when a directory is still unassigned (fails closed),
    and the `Context` record that every path-resolving engine function accepts. `Context` also carries the
    selected properties file, which is part of what P26 requires a `Context` to carry.
  - `session.py` exports `Session`, the single entry point P26 requires. It's opened on either a plain home
    directory string or a `Context`, and refuses to be constructed without a home (raising `dir.unassigned` —
    the "resolve the home on first use" rule now lives here, at construction). Once constructed, `Session` pins
    its `Context` for good — there's no global state, so nothing stops two `Session`s existing in one process —
    and it forwards one thin wrapper method per stateful operation to the underlying engine modules. The codex
    verbs (CLI-only, see D87) and the pure parsers bypass this wrapper. The CLI is `Session`'s first user.
  - `assets.py` owns finding assets a user has authored. Right now there is one source, `DirectorySource`, which
    reads each asset kind's own placeable directory, walking it recursively by file extension — there's no
    "seed on read" behavior behind it. It also provides `source_for` and the identity rule for these assets: the
    declared `name` field if present, else the filename stem, with collisions within a source caught by
    `index_by_name`. The embedding API is never given a directory to fall back on, so a caller who doesn't
    supply one gets a fail-closed error rather than Reliquary quietly reading the home directory or the current
    working directory. A planned third source, `ObjectSource`, will hold assets imported directly as JSON
    objects.
  - `json5reader.py` reads JSON5 documents (see D102 for the published grammar). It rejects `NaN` and infinities
    so values stay ordinary JSON, and can report source positions on request.
  - `document.py` is the `.rlqb` blueprint parser (normative spec: `docs/spec/blueprint-model.md`).
    `parse_document` / `load_document` build a `Document` holding `machines` and `media` from a root array of
    specs — a single spec object is shorthand for an array of one, and `type` defaults to `media`, so an object
    with no `type` is treated as media (and the media branch's "unknown field" error suggests a fix when it sees
    machine-only field names). The dataclasses are `Machine`, `Media`, `MachineDrive`, `Location`, `Reference`,
    and `Deferred` (a value that still contains unresolved `${…}` references, resolved later) — validation
    happens in two phases: shape is checked here, values are checked at resolution. `children` is sugar for a
    child declaring its own parent. Names are either given explicitly or derived from content, following the
    media-naming rules (an invalid derived name is repaired, with a `BlueprintWarning`, or fails closed if it
    can't be repaired). Identity is the pair `(name, type)`, compared case-insensitively. The reference grammar
    (`${…}`) is restricted to exactly two forms — a character class does a first screen, then the two
    productions decide — and references are refused in identity positions, in the dependency graph, and in
    fields with a closed set of allowed values. `document.py` validates the full set of machine fields:
    `platform`, `backend`, `memory`, `cpus`, `devices` (drives, NICs, and shares sharing one slot-keyed map, D121: a
    drive value is a media name, `null`, `{media, controller, enabled}`, or an inline media definition, including an
    anonymous blank one; a NIC value is an attachment name — `nat` or `bridged` — or `{attachment, interface,
    model}`, D120/D122 — `model` overrides the platform-resolved chipset; a share value is a media name,
    `{media, model, enabled}`, or an inline media definition carrying its own `model`/`enabled` too (F72) — no
    `null`, and no anonymous blank, inline included — where `model` is `vvfat`/`9pfs`/`virtio-fs`, F68),
    `boot`, `name` (the id-safe identity, not a display label), `description`, `scripts`, `control-planes`,
    `backend-settings`, and `parameters`. The pointer device (`tablet`/`mouse`/`virtio-mouse`, F66, `virtio-mouse`
    added by T34) and the RNG (`virtio-rng` only, D125) each live in `devices` too, at the fixed keys `pointer0`
    and `rng0` (D124, D125) — a machine has at most one of each, so neither key takes a second slot.
  - `authoring.py` is the counterpart of `assets.py`: `assets` resolves and reads what a user already owns,
    `authoring` writes and removes it. It's authoring-only: it scaffolds a new blueprint (`new_blueprint`), and
    writes a media declaration for a file already on disk (`add_media(name, file)` — computes the sha256, writes
    `blueprints/<name>.rlqb` pointing the media at that path, copies nothing, and refuses to overwrite; this is
    how a codex media entry that's pinned but not yet located on disk gets supplied, D41). It also removes both
    authored kinds: `delete_blueprint` fails closed if any machine of that blueprint still exists, and
    `delete_script` fails closed if any blueprint in the source still references the script. Both removals follow
    the same three-step order — check who refers to this, check the file exists, remove it — even though the
    answer to "who refers to this" comes from different places for each (the machine list for a blueprint; every
    blueprint's parsed `scripts` map for a script). That's why the two live in the same module, side by side,
    rather than sharing a helper function.
  - `resolve.py` builds the merged `(name, type)` resolution namespace from every `.rlqb` file in the active
    source (`load_namespace` / `build_namespace`, which detects collisions across files), resolves a media by
    name (`resolve_media`), and turns it into a nested fetch plan (`Download` / `LocalFile` / `Extract`).
  - `acquire.py` executes that fetch plan. `fetch_media(media, namespace, context, on_mismatch)` downloads (with
    mirror support), extracts archives recursively, verifies each file's sha256, and stores results in the one
    `cache/media/` cache, keyed by the media's name — then attaches a `local` payload pointing at the cached
    file. The cache is entirely regenerable: every file in it arrived by download or extraction, so nothing
    checks where a file came from before deleting it, and nothing records where it came from either (D41 removed
    the ledger that used to track that).
  - `media.py` only handles acquisition: `fetch_media(name, context, on_mismatch)` and `list_media` work over the
    namespace, plus the cache-cleanup functions `clean_media(name=None)` (a blunt clear-everything, skipping
    anything currently attached to a running machine, unless a specific name narrows it) and
    `prune_media(dry_run=)` (removes a container once all its children are cached). There is no `delete_media`
    function — removing a media means editing the `.rlqb` file that declares it (D30) — and no `add_media`
    function either — supplying a file is `authoring.py`'s job (D41).
  - `properties.py` owns the user properties file, `<home>/user.properties`. It's a line-based format: `key =
    value` lines, `#` comments, dotted keys that start with a letter (with the `rlq`/`reliquary` namespaces
    reserved), values taken verbatim to the end of the line, and a leading `@` marking a value's kind (`@secret`
    marks a secret, `@@` escapes a literal `@`). The whole file is parsed before any edit, so a malformed file is
    never partially rewritten (`PropertiesError` names the path and line). Edits are surgical, line by line,
    preserving comments, blank lines, and ordering, and are written atomically. The functions are `get_property`
    / `set_property` / `unset_property` / `list_properties(prefix)`; reading a secret returns the marker
    `{"secret": True}`, never the actual value. Every one of these functions takes `properties_file=` (set via
    the CLI's `--properties` flag or the `RELIQUARY_PROPERTIES` environment variable), which *replaces* the
    home's properties file rather than adding to it.
  - `credentials.py` owns the host credential store. It has a three-method provider interface shaped like the
    `keyring` package's own interface, so the default provider is `keyring` and a test double just needs to
    implement those same three methods; `_set_provider` installs one, which is how the test suite avoids
    touching the real credential store. Secrets are scoped by the absolute path of the selected properties file.
    There is no plaintext fallback: if the credential store is missing or unusable, `CredentialError` is raised.
    Updates happen in a fail-safe order — the credential is written before its marker property, and the marker
    is removed before the credential — so the only state an interrupted update can leave behind is an orphaned
    credential with no marker; an ordinary `set` refuses to overwrite that, and `unset_property` clears it.
    Binding a property into a run — layering the sources, deriving values, applying the runtime secret rules —
    is separate work, the rest of milestone 8.
  - `library.py` owns the codex, Reliquary's built-in seed library (the package data under
    `src/reliquary/codex/`). Copying out of it only happens on request, and it never overwrites files already in
    the user's home. `seed_blueprint` / `seed_script` copy either the full closure of files by default or a
    single file when `only=` is given. `list_codex` lists what the library holds — nothing about what the user
    already has — and `codex_blueprint_available` is the check a refusal makes so it can name the right seed
    command in its error message.
  - `machines.py` owns machine materialization, under
  `cache/machines/<blueprint>-<n>/`.

    Backend assignment happens here, before any image work. The blueprint's full set of requirements — control
    planes, media kinds, controllers, materialization modes, the pointer device (F66, resolved by
    `_pointer_value`, which defaults to `mouse`), and any RNG models declared (D125) — becomes a
    `backends.Requirements` object. A
    declared `backend` field pins the choice. So does a `backend-settings` section for exactly one backend: its
    presence alone narrows the search to that backend, regardless of what settings it contains
    (`_backend_choice`: use the declared backend if there is one, else the one backend with a settings section if
    there's exactly one, else search). With no `backend` and no single `backend-settings` section, Reliquary
    walks the priority order (`backends.PRIORITY`, D66) and picks the first backend that's both available and
    capable of meeting the requirements. If no candidate can meet a requirement, machine creation fails closed,
    naming both the backend and the unmet requirement — Reliquary never records a machine it knows can't work
    (P11).

    A dry run does the same evaluation but commits nothing. `create_machine(dry_run=True)` returns a `DryRun`
    (with `operation` / `report` / `plan` fields — the same type the script-side dry run in F25 uses) and writes
    nothing at all: no machine directory, no `machine.json`, no image, no fetched payload, no lock file, and no
    seeded blueprint (a codex-only blueprint is read in place, the same way any read-only check reads it). It
    resolves media without fetching them — `acquire.residency` reports `cached` / `would-download` /
    `would-extract` / `local-present` / `local-missing` without hashing anything, so `cached` here means "the
    file is present," not "the file was verified." It describes which location properties would be needed
    without binding them (`binding.describe_keys`), because a dry run must never prompt. It refuses everything an
    actual create would refuse, at the same point a create would refuse it — with two deliberate exceptions,
    each a case where a dry run genuinely *can't* answer rather than a judgment call: an unbound location is
    reported as unevaluated rather than resolved, and, when `backend=` is given explicitly, a backend that isn't
    available is reported rather than raised as an error — because that flag is asking "would this blueprint
    work on that specific backend," so only its capabilities matter (`backends.evaluate`), and this leniency is
    legal only in a dry run because P10 gives the blueprint authority over what a machine is. Missing local
    payloads are collected and reported together as one list, so a single validation pass names all of them at
    once, not just the first one found.

    The lifecycle functions are `create`, `start`, `stop`, `destroy`, `recreate_machine` (destroy followed by
    create, reusing the same id), `apply_blueprint` (applies blueprint edits to a stopped machine — it can
    absorb some kinds of change, but fails closed if a media image that's already been materialized would need
    to change size or materialization mode), `get_machine_dir` (a direct path to the machine's directory, outside
    the normal API), `list_machines`, `resolve_machine`, and the exec-run family:

    - `wait_ready` is `exec`'s precondition, factored out as its own function (D114). It runs the shared
      `_running_guest` preflight check (selector resolves, platform is DOS, machine is running, VM identity
      matches the record) and then the adapter's own readiness wait: a prompt is only accepted as a candidate
      once `screen_stability` confirms the screen underneath it has stopped changing — the same rule `execute`
      uses to decide a command has finished (D115) — and a wait that never gets there raises `WaitExpired`.
    - `exec` runs a command.
    - `get_machine_var` is the one channel a script can use to send a value back to the host: it reads a
      `variables` map inside `machine.json`, guarded by the same lock as other operations, cleared every time the
      machine starts (so a variable always reflects the current boot). The `rlq`/`reliquary` key namespaces are
      reserved. The script's `set` verb is the only thing that writes to this map — per the CLI spec, the host
      side only ever reads it.

    Where a machine lives, how its state is serialized, and how it's named are handled by `machine_state.py`
    (described below). Every mutating operation carries an operation generation number and writes one of the
    transitional phases `creating` / `stopping` / `destroying`, so an operation interrupted partway is reconciled
    the next time something touches that machine: an interrupted `stopping` is completed, and an interrupted
    `creating` or `destroying` is rolled forward to removal.

    `machines.py` also owns the persistent machine-state mutations: `insert_media`, `eject_media`,
    `set_boot_order`, and `mark_stopped`. `insert_media` and `eject_media` only apply to floppy and cdrom drives,
    and work whether the machine is running or stopped — on a running machine the change is applied live, over
    an identity-verified QMP session, addressed by drive id, and then persisted to state; on a stopped machine
    it's just persisted, for the next start. `insert_media(slot, media=None, file=None)` takes exactly one of a
    declared media (which gets fetched and verified) or `file=` — an anonymous image, mounted in place, that's
    mutable, unverified, and never copied (this is U20's transport for iterating on a disk live). `set_boot_order`
    only works on a stopped machine, since it sets the firmware's launch-time boot order; its keys can name any
    declared drive. All three persist their change and it survives a stop/start cycle. A script's `with` scope
    (see below) is a second caller of these same three functions: it captures the current value before making its
    change, then calls the same function again on exit to restore it, under the same rules as any other call — so
    restoring a boot order on a running machine is refused just like setting one is, and if the restore can't be
    done the run fails, naming what it couldn't undo, rather than letting the state file gain a second way to be
    written (D104).

    There is no drive layer and no file-access family in Reliquary (D108). Reliquary declares a machine's drives,
    materializes them, and moves their media — but it never reaches inside a volume: there's no
    `describe_drives`, no `put_file`/`get_file` pair, no drive-letter mapping, no access to a disk at rest, and no
    dependency on `remanence`. Whatever is inside a volume is the caller's business, reached with the caller's
    own tools against the directory `get_machine_dir` returns — which is what makes P16's carve-out for file
    content a real boundary rather than a gap. Two routes Reliquary does supply stay in-band and neither one
    opens a filesystem: a share device that presents a host directory to the guest (F68), and
    `insert_media(file=)`, which swaps a whole image live. `test_old_surface_purge.py` checks that the seven old
    command words for file access stay gone, and `test_command_manifest.py` catches one coming back disguised as
    an unclassified session method.
  - `machine_state.py` is the foundation the machine layer is built on. It knows where a machine lives
    (`machine_dir_path`, `machine_disks_dir`, `backend_dir`), how a machine is named (`machine_id_for` /
    `split_machine_id` — ids look like `<blueprint_name>-<machine_number>`, reusing the lowest free number,
    via `allocate_machine_id`), what serializes concurrent work against it (`blueprint_alloc_lock` for
    numbering, and the exclusive per-machine operation lock `machine_lock`, backed by
    `.locks/<id>.op.lock`, which every mutating operation takes), how `machine.json` is read and written
    (`write_state` / `load_machine_state` / `read_vm_state`), and how a `--blueprint` / `--machine` selector on
    the CLI resolves to a machine (`resolve_machine` / `list_machines` / `machines_for_blueprint`). It knows
    nothing about what a machine actually *is* — no backend, no adapter, no drive, no media. It stayed a
    separate module even after its sibling module, `drives.py`, was deleted by D108, because `machine_handle.py`
    needs `read_vm_state` and would otherwise end up in an import cycle with the lifecycle code. Phase
    transitions have only one consumer, so they stayed with the lifecycle code in `machines.py`, which remains
    the front door for this layer — it re-exports these names so anything above it reaches them all in one
    place.
  - `backends.py` defines the backend adapter interface — the contract each backend provider (QEMU, VirtualBox,
    ...) must implement underneath Reliquary's semantic surface (design doc: `planning/design/backend-adapter.md`).
    This interface is deliberately not itself one of Reliquary's application surfaces. It includes: the
    `BackendAdapter` contract (discovery, a capability report, image materialization, start/stop, and the
    carrier session); the `Availability` / `Capabilities` / `Requirements` types shared between what a backend
    reports and what a blueprint demands (`pointing_devices` / `pointing_device`, F66; `network_models` /
    `network_attachments`, D120; `share_models` / `share_default` and `share_models` / `share_unstated`, F68;
    `rng_models`, D125 — all checked in `unmet()` the same way `drives` is checked); `Requirements.platform`, which is not checked
    against anything but is passed to `capabilities(platform)` so a backend whose host tooling differs by guest
    architecture reports on the tool that guest will actually use (F69 — QEMU's live share transports are build
    options, so the answer differs between two binaries of one install);
    `capture_format(plane)` and its sibling
    `pointer_capable(plane)`, two separate per-plane capabilities (F66 — a display plane can capture a
    framebuffer without being able to deliver a pointer event to it, which is true of VirtualBox today), each
    defaulting honestly to "nothing" (`None` / `False`) when unknown; the `backend-settings` contract
    (`settings_keys`, which lists the keys an adapter's settings section may contain, empty by default, and
    `validate_settings`, the shared rule that refuses unknown keys, which an argv-style adapter extends with its
    own overlap check — only the assigned backend's settings section is ever checked, since no adapter can speak
    for another's vocabulary); `identity()`, the record every adapter writes down once a VM exists (backend
    name, that backend's own `backend-id`, a per-start `token`, and an adapter-specific `endpoint`); the adapter
    registry (`adapter(name)`, `discover()`); and `assign()`, built on `evaluate(name, requirements)`, which
    reports two separate answers rather than one verdict — whether the backend is available on this host, and
    separately, which requirements it can't meet — because those are two different questions, and a dry run
    only needs the second one. `_set_adapter` is the test hook that lets tests substitute a fake adapter, the
    same way `credentials._set_provider` substitutes a fake keyring.
  - `backend_qemu.py` contains everything that's specific to QEMU: finding the QEMU binary, running `qemu-img`
    for image work, rendering a machine's drives, NICs, and boot order into QEMU arguments (`devices.pointer0:
    tablet` renders as `-usb -device usb-tablet,id=pointer0`, F66; `pointer0: virtio-mouse` renders as
    `-device virtio-mouse-pci,id=pointer0`, T34, the same relative device family as the implicit default, just
    explicit and paravirtualized; `devices.rng0: virtio-rng` renders as `-device virtio-rng-pci,id=rng0`, D125;
    `network_args` renders each `devices`
    NIC entry into a `-netdev`/`-device` pair, D120/D121), the `backend-settings.qemu` escape
    hatch (`SETTINGS_KEYS` = `machine` / `args`; `RESERVED_ARGUMENTS` lists what a blueprint field or the VM
    identity already owns, checked case-sensitively — `-m` is memory and `-M` is the machine type, but
    deliberately not `-device` or `-cpu`; `RESERVED_DRIVE_PROPERTIES` similarly reserves the `-drive` properties
    that `devices` already renders, and so also refuses them via `-set drive.<slot>.<property>` — QEMU addresses
    each drive's own options through `id=<slot>`, which is why there's no separate drive-scoped settings section,
    D118; `settings_args` both validates and renders the settings, which is what makes a settings section that a
    `create` accepts the same one a `start` applies, and it renders last so a caller's own arguments appear at
    the end of the logged command line), the actual launch with its identity verification, `Qmp`, the carrier
    methods (`send_keys`, `text_screen`, `screenshot`, `change_medium`, and `pointer_event` — F66, which is
    refused on the base session because it has no coordinate space to aim a pointer into, but works on the VNC
    session via RFB's own `PointerEvent`, unscaled), and the named native escape hatch `QemuSession.native()`.

    `backend_qemu.py` serves two display planes over the same carrier interface (F63): the agentless default,
    which scrapes VGA text memory over QMP, and the VNC plane (turned on with `control-planes: ["vnc"]`, the
    first plane declared drives the session), which launches QEMU with `-vnc 127.0.0.1:<display>` — loopback
    only, no VNC authentication, with the port and the active plane recorded in the identity's endpoint
    alongside the QMP port — and reads the framebuffer over RFB through the same recognizer used elsewhere,
    via `guest_glyph_banks`, sending keys through a qcode-to-X11-keysym table (`keysym_for`, the adapter-side
    layer from D103; VirtualBox has its own equivalent, `scancodes_for`). Identity checking is still QMP's job
    even on the VNC plane: `query-vnc` cross-checks the recorded endpoint after the normal verification, both at
    launch and again right before a session opens the RFB socket, and `change_medium` always goes over QMP
    regardless of which plane is driving the screen.

    `rfb.py` is the wire protocol: an in-tree, minimal RFB 3.8 client (no security, forced 32-bit true colour,
    only full and incremental Raw updates, `KeyEvent` and `PointerEvent` — this is D110's "no new dependency"
    decision). It knows nothing about machines and verifies no identity, which is why it's a separate module
    sitting below the adapter.

    No adapter, for any backend, ever opens a disk's contents: an adapter creates the images a machine runs on
    and exposes nothing that reads inside one (D108).
  - `backend_virtualbox.py` is the VirtualBox adapter (lifecycle and VDI images from F50; agentless-display
    carriers and FreeDOS parity from F52).
  - `backend_stubs.py` holds the two adapters that aren't built yet: VMware Workstation and Hyper-V. Their host
    probes are real — they genuinely check whether the backend is installed — but they claim no capabilities at
    all, so backend assignment always skips them, even on a host where the backend is installed, and pinning one
    explicitly fails preflight, naming what's missing.
  - `control_display.py` is the control plane for agentless-display backends: character-to-key mapping
    (`char_keys`), building up text screens, and the cursor-menu machinery. It's written once, against the
    shared text-screen contract (character rows plus per-cell attribute tokens that can be compared for
    equality but not otherwise inspected), rather than once per adapter.

    Key mapping happens in three layers, and this module is only the middle one (D103). The scripting language's
    portable key names (like `spc`, `ret`) are listed in `script_validation.PORTABLE_KEY_NAMES`.
    `script_runner.resolve_key` maps those onto the shared key vocabulary, which is QEMU's own qcode set. Each
    adapter then translates a qcode into its own input events — QEMU uses qcodes directly, VirtualBox translates
    them via `scancodes_for`. That's why `char_keys` spells things `spc` and `ret` rather than `space` and
    `enter`: the shared vocabulary is named after the reference backend (QEMU) rather than inventing a third
    vocabulary that no backend actually speaks.
  - `text_recognize.py` is the shared fixed-font character recognizer (F51), used by backends that don't offer
    VGA text memory and so have to work from a screenshot instead. It's one contract and one algorithm, shared
    across backends.

    The font bank it matches against belongs to the guest, not to Reliquary — an adapter reading a live screen
    passes its own host's font as `bank=`. What actually determines the font is whether the BIOS or the guest
    painted the screen (T20), not which emulator is in use. Both QEMU and VirtualBox install the *same* font
    when a text mode is set: QEMU's vgabios merges a 19-glyph replacement set (`vgafont16alt`) into the font it
    ships, and VirtualBox ships the unmerged font but applies the same 19-glyph patch at runtime, in
    `vgabios.c`'s `load_text_patch` — so a merged VirtualBox font is byte-for-byte identical to QEMU's font.
    What differs is who paints the screen: the BIOS always uses the merged font, but a DOS guest that loads its
    own CP437 font — FreeDOS does — paints the *unpatched* glyphs instead, and `W`, `m`, and `T` are among the 19
    that differ, which is enough to make a wait miss on any word containing one of them.

    So no single font bank can read an entire run, and nothing in a captured framebuffer says which font painted
    it. That's why the recognizer takes every font the host offers and matches each screen cell against all of
    them, rather than picking one up front. `bank=` accepts either one bank or several (`as_banks`);
    `_all_glyph_bits` unions the bit patterns per character code, so a shape every font agrees on is only scored
    once, and the extra cost is proportional to how much the fonts actually differ — about 5% more work on a
    read, for a stock VirtualBox's 275 entries versus 256. Ties are broken by preferring the first bank, so two
    runs on the same host agree with each other.

    QEMU's VNC plane (F63) recognizes QEMU's own framebuffers even though QEMU only ever offers the merged font,
    because the 19 patched glyphs are visually close to the classic designs they replaced. Measured directly (by
    diffing the merged and unpatched fonts a stock VirtualBox installation provides), every ASCII character pair
    falls within the recognizer's 24-bit match threshold — `W` is the worst case at 22 — except for `₧` (code
    0x9E), which measures 39 and falls outside it. So a guest-drawn screen on QEMU still reads correctly through
    the one font QEMU offers, just with a smaller margin — not because a second font bank is available. If a
    future QEMU build changes its fonts, this margin should be re-measured rather than assumed.

    Each backend answers "what font does this host have" the same way, through `guest_glyph_banks(cache)`,
    implemented identically in `backend_virtualbox` and `backend_qemu`. `banks_from_files` /
    `banks_from_binary` collect every font bank in the backend's installed binaries, plus every variant that an
    override table would install on top of one, anchored on the classic `A` glyph that every CP437 font shares,
    and failing closed (naming the problem) if the installation has none. This extraction works structurally
    rather than off a table Reliquary hand-maintains: it looks for runs of `(code, rows...)` entries with
    ascending codes, terminated by a zero code byte, skipping over runs for other glyph heights — so an
    installation with a different font set is still read correctly. QEMU's own agentless plane never needs any
    of this, since it scrapes text memory where the guest has already resolved its characters into text; this
    machinery exists so the font question is answered the same way for every backend, not just where it caused a
    bug — and a stock QEMU installation ends up yielding a single font bank anyway, since its font ships already
    merged.

    Fonts are extracted on demand and cached — never vendored into the repository — at
    `cache/support/<backend>/cp437-8x16-banks.bin`, via `text_recognize.cached_banks`; every bank found is
    concatenated into that one file, so how many there are is the backend's own business. Like everything else
    under the cache root, this file is fully regenerable, so a truncated cache file is just re-extracted rather
    than raising an error. The cache root reaches the adapter through `Machine(cache=)`, which is passed to
    `adapter.session(vm, cache=)` — a plain resolved directory, not derived from the machine directory (since
    `machines` can be placed independently); passing `None` just means it will always re-extract, which only
    costs time, never correctness. Not vendoring these fonts is both a licensing decision (see
    CONTRIBUTING.md) and an engineering one: the glyphs belong to whichever emulator the host has installed, not
    to Reliquary.

    The `fonts/cp437_8x16.bin` file that ships with Reliquary itself is only used as `recognize`'s default and to
    render test fixtures with — this is what lets the test suite run without a hypervisor. It's drawn by a script
    (`tools/gen_cp437_font.py`) rather than copied from anywhere (D82 — the test for anything included this way
    is "could this ship inside a proprietary product?"). Its ASCII and box-drawing shapes are hand-authored;
    every character code nobody drew gets a computed Reed–Muller codeword instead — a pattern that differs from
    any other glyph in at least 64 of its 128 pixels — because the one requirement for this font is that all 256
    codes must be visually distinct. An undrawn code that came out blank would collide with the space character
    and could never be recognized. This font doesn't need to look like real VGA text, and deliberately isn't
    built to: `CLASSIC_A`, the reference glyph that `bank_from_binary` uses to locate a genuine font in a binary,
    is deliberately absent from it. A test that needs a font the recognizer can actually locate uses
    `tests/vga_bank.py` instead.
  - Whether a screen has stopped changing is *not* decided in `control_display.py` (F49): `_settled_screen` and
    `_menu_baseline` call `screen_stability` for that rather than implementing their own copy of the logic. What
    stays here is classification that was never about settling in the first place — whether a keypress changed
    anything at all (`None` means a dead key) and which row a highlight moved to.
  - `screen_stability.py` answers a question `stable=` can't: has the guest stopped drawing at all, as opposed
    to whether a specific condition currently holds — a condition can hold perfectly true on a screen that's
    still actively painting. It compares individual cells rather than whole rows, because row-level comparison
    can't tell a blinking cursor apart from an arriving line of text, and it treats a cell's text-plus-attribute
    pair as its identity, since a cursor menu moves its highlight purely by changing attributes. Both
    comparisons are measured over wall-clock time windows rather than a fixed number of samples — using sample
    counts instead would mean a denser poll reaches a different verdict on the same guest, so a recorded run and
    a live run could take different paths through the same script.

    Stability is the fraction of (unmasked) cells that held still over the last 200ms, checked against a
    threshold of 0.99 — that's 20 cells out of 2000, about a quarter of a row, which sits between the size of
    small moving furniture (a blinking cursor is 1 cell, a clock is about 8) and actual content (a row of text is
    80 cells). A cell that changes 3 or more times within one second counts as decoration and is excluded from
    that fraction — this carries over `_menu_baseline`'s old majority-churn bail-out logic (mask nothing, compare
    the raw cells). A time window with no samples in it reports `stability=None` rather than inventing a verdict
    the actual sampling never produced (P11).

    This was delivered as F47, and it's the only implementation of this measurement anywhere in the codebase
    (F49): its three users are `exec`'s completion check (F45, described below), the scripting language's
    `stability=` (F48, described below), and the cursor-menu machinery — whose own older "wait for two
    consecutive stable reads" logic and learned animation mask were special cases of the same idea, and were
    deleted rather than kept as a separate implementation. Doing that surfaced one real tension, now recorded in
    `control_display._BASELINE_READS`: recognizing that a screen has *settled* and recognizing that a cell is
    *decoration* need different amounts of observation — a clock only moves two cells, so it looks settled after
    one glance, but nothing can tell it's a clock until it's been watched tick more than once, so a baseline that
    stops looking as soon as the screen looks settled ends up with an empty decoration mask.

    The same contract generalizes from character cells to pixels (F65): `observe` also accepts a Pillow image,
    for landmark matching where there are no character cells to compare, and measures the same fraction over the
    same time window with the same default threshold. A `Reading` records which unit it counted, so a diagnostic
    message correctly says "pixel" when it counted pixels. A single monitor instance sticks to whichever kind it
    was first given — mixing cells and pixels in the same monitor would make every sample look like a total
    repaint.
  - `landmarks.py` is the image-matching asset kind and its matcher (F65; normative spec:
    `docs/spec/landmarks.md`). A `.rlql` file is an authored asset kind alongside `.rlqb` / `.rlqs` / `.rlqf`,
    identified by its filename stem the same way a script or a font is. Its variant images are attached as plain
    `<name>.<n>.png` files, matched to it by stem and number, so refreshing the images just means creating new
    files — never rewriting an existing one. It resolves out of `home.landmarks_dir` (`<home>/landmarks`), a
    fixed subdirectory like `fonts` rather than a seventh independently-placeable root. Its name is checked for
    collisions against the same shared `@`-prefixed name pool that media and fonts already use, now served for
    all three by `assets.guard_pool`.

    The match metric is the fraction of pixels that match exactly, computed separately per region — never one
    combined score across the whole image, which would let a small failing region get lost in a large mostly-
    matching screen's average. An `ignore` region excludes its own pixels from matching entirely and takes
    priority where regions overlap; a `fuzzy` region checks its remaining pixels against its own declared match
    percentage; everything left over (the "residual") must match 100%. A variant matches when its residual is
    clean and every one of its fuzzy regions clears its bar; the landmark as a whole matches if any of its
    variants does. A miss reports the *closest* variant, along with which regions failed and what percentage
    they actually achieved. Before comparing, the captured screen is normalized through whatever pixel format the
    capturing plane reports — a detail settled in `hyperv-screen.md` — which today is the same for every plane
    that's actually built, so it costs nothing until some plane starts reporting a different format.

    `spots` are read by the `click` script verb (F66): a click lands on a named point, or on the single spot a
    landmark declares if it has exactly one (no ambiguity to resolve). `park_position(width, height)` computes
    where the pointer parks after every pointer-verb delivery, relative to the specific landmark matched — the
    bottom-right corner scaled to that landmark's own pinned size, rather than an arbitrary fixed pixel position,
    since real content tends to be anchored at the top-left. `_park_region` always folds in the matching landmark's
    built-in `ignore` region as well, clamped to at most a quarter of the landmark's pinned size, so that a small
    landmark's non-ignored area is never entirely swallowed by the park zone. This is masking done on the host
    side, after capture — it is not a way to keep the cursor out of the framebuffer in the first place; nothing
    here negotiates the RFB option that would exclude the cursor at the source.

    What decides whether a machine can watch for a landmark at all is the display plane's screen carrier, not the
    backend in general: `BackendAdapter.capture_format(plane)` reports the pixel format a given plane captures
    in, or `None` if it doesn't capture a framebuffer at all (the honest default, matching how `settings_keys` is
    empty by default). A session whose plane reports a format offers a `framebuffer()` carrier in addition to
    `text_screen()`. QEMU's agentless-display plane, which just scrapes characters the guest has already
    resolved, reports no format at all, so a landmark condition against it is refused up front with a named
    preflight error (`machine.plane-no-framebuffer`); QEMU's VNC plane and VirtualBox's display plane both
    interpret a captured framebuffer and report `rgb`. `screendump` / `screenshotpng` remain diagnostic-only
    carriers on every plane — they are not screens a landmark is ever matched against.
  - `interaction.py` defines the capability protocols (interfaces).
  - `interaction_agentless.py` contains the concrete agentless DOS adapter: prompt-based readiness and command
    completion. The echoed command and the returned prompt are identified by where they came from, never by
    their shape alone — the echo is the row the command was typed on, with the rows that were above the prompt
    still above it, and the prompt is recognized as having returned when it's either the standard shape or
    exactly the one the guest was showing before (D111 and D112). A detected prompt is treated as a candidate,
    not a final answer, until `screen_stability` confirms the screen underneath it has actually settled —
    otherwise a prompt that appears mid-scroll would cut the command's output off at a point that was never a
    real boundary (F45). To support this, the polling schedule has three stages rather than two:
    `_ECHO_POLL` catches the echo, `_PROMPT_POLL` cheaply waits for a prompt to appear, and `_SETTLE_POLL`
    confirms it's stable — so the more expensive, denser reads only happen once the question has narrowed down
    to "is this screen actually finished?"
  - `machine_handle.py` defines `Machine`, the backend-neutral machine handle. It's named in the singular
    (unlike the plural-named engine modules — `media.py`, `properties.py`, `backends.py`, `machines.py`)
    because it's a handle type, not a family of functions: a machine is addressed by its materialization
    directory, the adapter named in its recorded identity supplies the session (`Machine.session()` /
    `console()`), and `Machine.qmp()` is a QEMU-only escape hatch that refuses to work for any other backend.
  - `platform_dos.py` owns DOS provisioning and facades, and today it's down to just `program_name` — the
    drive-letter mapping and the guest-path grammar it used to hold were removed along with volume mapping
    (D108), so nothing in this module translates a host path into a DOS drive letter any more.
  - The `.rlqs` scripting language is implemented in four layers:
    - `script_nodes.py` — the lexer and its diagnostics.
    - `script_parser.py`, with the grammar file `script_grammar.lark` — builds the typed parse tree, defines
      node signatures, and exposes `parse_script` / `load_script`.
    - `script_validation.py` — the static validation rules, each numbered with a V-id that its diagnostic cites.
    - `script_timing.py` — resolves durations and builds the timing plan at parse time: every observation's
      effective timeout and quiescence gate, and every guest-input verb's effective `pacing` (the settling gap
      before its first key event, D60), each recorded together with the scope it came from. `INPUT_VERBS` gained
      `click` in F66; `click` and `select` are the only two verbs that appear twice in the resolved plan — once
      as an `Observation` for the search (carrying the landmark name), and once as an `Input` for the delivery.
  - `stability=` is the counterpart to `pacing`, but for observations instead of input verbs (F48). Where
    `pacing` is a duration attached to each of the five input verbs, `stability=` is a proportion (a threshold,
    not a time) attached to observations, and is resolved by checking, in order, the statement itself, then a
    branching `wait`, then the phase, then the header, and finally falling back to the built-in default of 0.99.
    Each of `pacing` and `stability=` only guards the one statement kind whose risk it addresses, so neither one
    needs to know where in the script it's being used.

    `stability=` exists because `stable` can't do this job: `stable` qualifies a match, so a match has to exist
    first, whereas `stability` qualifies the screen frame a comparison runs against, and a frame exists at every
    single sample — which is also what makes a default value possible at all. A sample that doesn't clear the
    stability threshold isn't used to judge any condition; in a branching `wait`, an unsettled frame causes none
    of the handlers to be evaluated on that sample. The stability gate never causes a failure by itself: if it
    never got the chance to measure the condition, the timeout is judged only on the samples that did happen,
    preserving the rule that a timeout always means samples were taken (never that no one looked); if it did
    measure the condition and the screen kept moving, the timeout error says so. Setting `stability=0` turns the
    gate off entirely, at no cost — this is the escape hatch for a screen the default threshold would otherwise
    refuse to read. `format_plan` and `run_script(dry_run=True)` (i.e. `rlq run-script --dry-run`) report the
    resolved timing plan without actually running it; `script_validation.reach` counts the statements no static
    pass can promise will run, since whether a given handler body runs is the guest's decision, not something the
    plan can predict.
  - The script dry run returns the same `DryRun` type the machine-create dry run returns, and follows the same
    rule: read-only throughout, seeding nothing, never prompting, and stopping before the machine starts or any
    statement reaches the guest. Two things are unique to the script dry run. First, the machine selector is
    optional only here — whether it's given picks which of the two checkable tiers described in script-spec.md
    applies, which is what keeps the selector-less mode from being silently lost when this feature was reworked.
    Second, `--dry-run` turns the command from something that streams events into something that returns one
    document: `--json` becomes legal (and prints exactly what the equivalent API call returns), while
    `--progress` and `--display` are refused, since a plan has no event stream to render and no window to show.
    The entire older "check" command family was deleted outright rather than kept as an alias (P9) — its
    command, its API twin, its result type, and the property-key predicate function that went private along with
    them (a public predicate over a bare string, with no CLI equivalent, was a leftover violating P6).
    `test_old_surface_purge.py` records the old command spellings and checks they stay gone, which is why they
    aren't written out here.
  - `binding.py` resolves a script's declared properties before a run starts. Values are looked up in this
    order: an explicit `--property` flag, a blueprint parameter (redirected via its `{"property": ...}` field),
    the `RELIQUARY_PROPERTY_*` environment variables (checked up front for collisions), the properties file, the
    property's own declared `default=` expression, and finally an interactive prompt. It applies the rules for
    each property kind (text, media, secret), pulls secret values from the credential store, and provides
    `describe_sources`, the read-only counterpart that reports which source would supply each key, for a dry run
    that must neither bind values nor prompt. Declarations are bound in topological order, so that whatever a
    `default=` derivation refers to is resolved first.
  - `facts.py` owns the built-in `rlq.*` values a `default=` derivation can reference: `rlq.host.username`
    (normalized the way a login name is), `rlq.host.full-name`, and `rlq.env.<NAME>` (taken verbatim from the
    environment) — each one simply has no answer if the underlying host value is empty.
  - `bind_keys` binds the bare keys referenced by a media's `location` or `sha256` fields (the ones with no
    `property` declaration behind them), using the same source order as above minus the `default=` step.
    `resolve.py` substitutes the bound values in (`location_property_keys` collects every key referenced this
    way, and `resolve_media_plan(..., properties)` binds them), and `machines.create` / `apply_blueprint` bind
    them at materialization time, so the machine's recorded state stores the actual resolved location, never an
    unresolved `${key}` placeholder. A bound value that is itself a reference is refused — references can't
    chain.
  - The one language construct added since the rest of the vocabulary was settled is `with` (F54, D104): a
    scoped machine-state change. Its block starts with `boot`, `insert`, or `eject`, and whatever it changed is
    put back to its original value when the block exits, on every possible outcome the script runner reaches.
    Three details about it matter across every layer that touches it:
    - `boot` inside a `with` block states only a *prefix* of the boot order, and is deliberately spelled
      differently from `set-boot` — the drives it names come first, and the machine's existing order follows
      after them, so a stage can say what it boots without having to restate an order it isn't changing. The two
      different spellings mark two different meanings.
    - The scope is dynamic: it's in effect only while control is actually inside the block. So the parser
      flattens phases out normally (`Script.phases` stays one flat namespace that `goto` and phase entry points
      address directly) and separately records `phase_scopes`, the chain of enclosing `with` blocks around each
      phase — which is all a phase transition needs to know, and is why no layer above the parser had to change
      to support this construct.
    - The grammar can no longer tell the two shapes of script apart just from a `with` head, since a `with` head
      doesn't say which shape follows it. So the body of a `with` block is parsed as one permissive list of
      units, and validation rules V10 and V2 are the ones that decide which shape it actually is, at the point
      where a diagnostic can name the shape involved.

    V17 is the one static validation rule that's a flow analysis rather than a local check (T27): it tracks
    whether the machine is running — starting from the `machine` header, then `start`, `stop`, and a completed
    `wait machine=stopped` — forward to a fixed point over the whole transition graph. That lets it refuse, at
    parse time, a `set-boot` or a boot-scope edge that the plan implies would be reached while the machine is
    already running, instead of only discovering that five minutes into an install. It's bounded exactly the way
    `reach` (mentioned above) is bounded: a handler body is walked only for its effect, never judged as
    definitely running or not, and if two paths through the script disagree, V17 refuses nothing — a false
    refusal would be far worse than the later runtime failure it would be trying to prevent, which is why the
    runtime check stays in place regardless.
  - `script_runner.py` executes the parsed script tree against already-materialized machines: the phase graph,
    branching-wait and reactive dispatch over samples and episodes, and the clocks the timing plan resolved. It
    wires up the `run-script <label>` command — resolving the machine via the blueprint map, creating one if
    none exists, writing the machine-state header, and running a static preflight check of the drive keys used
    by `insert`/`eject`/`set-boot` (raised as `ScriptPreflightError`, exit 3, caught before the first guest
    input). `click`'s own three preflight checks join that same error class —
    `machine.pointing-device-not-tablet`, `machine.plane-no-pointer-input`, and
    `landmark.spot-required`/`landmark.spot-unknown` (F66) — checked inside the existing `_preflight_landmarks`
    walk, since `click` carries a `conditions` tuple the same way `wait` does, so no second walk is needed for
    the three landmark-related refusals the two share.

    `_click` reuses `wait`'s own search machinery directly — `_observation`/`_arm`/`_observe` — rather than
    `select`'s opaque `cursor_menu_select` function, because a `click`'s target is matched against a real
    landmark image, not scanned as text. Only once that search finds a match does delivery pay the `pacing`
    delay and perform the click through `DisplayConsole.click`, which parks the cursor as the last step.

    `script_runner.py` also handles property binding before the machine starts, secret redaction, and returning
    the run's output directly to the caller rather than persisting a run record (this is milestone 9's return
    model — the `runs/` archive is separate, not-yet-built work, D36). Everything it reports goes through the
    one event stream, so nothing can report information the stream itself doesn't carry. As it runs, it keeps
    the raw material a failure report would need — the condition or action currently pending, the route taken so
    far with per-phase revisit counts, and the last sample read — and it emits a `failure` event just before the
    terminal event, naming the clock that expired and its scope, the nearest miss found on the last screen read,
    an automatic screenshot (suppressed for the rest of the run once a secret has reached the guest), and the
    next command to try. Ctrl-C installs a handler that just sets a cancel flag, which is checked only at
    boundaries (`_check_clocks`, checked at the start of each statement and at each dispatch sample) — so a
    cancellation always ends the run at a clean boundary, with any input delivery already in flight allowed to
    finish, rather than wherever the interrupt happened to land.
  - `transcript.py` handles screen-transcript capture and reconstruction. This module is not itself an
    application surface (D98): the `.rlqt` file format carries no stability guarantee and has no `docs/spec/`
    entry, so changing the format is ordinary housekeeping — but the *option to record a transcript* is a
    surface change and belongs to S1/S2, since it's exposed as `--record <path>` on `run-script` and
    `run_script(record=)` on the session, and must be changed on both together.

    Capture wraps the carrier interface — the adapter session's `text_screen` / `send_keys` / `screenshot` /
    `change_medium` / `pointer_event` methods (`pointer_event` is F66; it's passed through when recording and
    refused during replay, for the same reason `framebuffer` already is: a transcript holds no pixel data, so a
    `click`'s search step is already impossible to replay before its delivery step would even be reached). This
    makes the module backend-neutral by construction: `RecordingSession` is the wrapper that captures at this
    interface, and `ReplaySession` is a fake session standing in at the same interface, which is what lets the
    entire interpretation layer above run unmodified over a recorded transcript.

    Every captured frame carries a sha256 hash of its canonical `(rows, attributes)` form, checked during
    reconstruction, so a bug or a hand-edited fixture fails loudly instead of quietly reconstructing a screen
    that never existed — the hash covers the screen in its expanded form, even though the file itself stores each
    attribute row compactly, as runs (`pack_attributes`), so how the file happens to encode a screen is never
    what a fixture actually checks. The header records the capture's pace and what script it's a capture of — the
    script's filename stem and a sha256 of its text — because replaying a transcript re-loads that same script,
    and if the script has since been edited, that's reported as staleness rather than as a mysterious divergence
    partway through the replay.

    A frame records the actual moments its underlying reads happened at, not just how many reads there were:
    reconstruction runs on the capture's own recorded timeline, since every stability/quiescence measurement
    above this layer is a window over wall-clock time — spreading a frame's reads out evenly (the obvious
    simplification) was tried and it shifted the menu machinery by one read, which changed which key it pressed.
    For the same reason, a read that arrives where the next entry in the capture is actually a *call* is an error
    (`transcript.read-before-call`) rather than something silently skipped over — a swallowed keypress would
    otherwise surface as a mismatch much later, against a screen that neither the original run nor the replay was
    ever looking at.

    The file ends with what the run concluded: `write_outcome` records the rows a command returned, or the phase
    a script finished in, or the error either one failed with. This is necessary because two runs that make
    identical carrier calls over identical screens don't automatically agree on what counts as "the output" —
    that's decided above the carrier interface — so this is what a reconstruction is checked against, and it's
    what makes a capture of a *failing* run something a test can actually assert on.

    The capture's recorded pace is a ceiling on the poll interval, never a floor: there's no way to sample
    independently of the run itself (QEMU only allows one QMP client at a time), so the run's own polls *are* the
    capture. An earlier version took the larger of the pace and the poll interval, which left a two-second idle
    gap that this mechanism exists specifically to close. This isn't free — a single QEMU sample is a 4000-byte
    HMP dump — and a recorded install run takes two to three times as long as an unrecorded one.

    Two kinds of entries reach the transcript from above the carrier interface, because the interface itself has
    no way to represent them. Every carrier call has to go through the engine's single `_machine()` handle — a
    caller that builds its own machine handle makes a call the transcript never sees, which is exactly the bug
    the `screenshot` verb used to have. And a `vm-gone` entry records the machine disappearing: since identity is
    verified while a session is being opened, a guest that has powered itself off refuses the session before the
    session wrapper even exists, so reconstruction raises the adapter's own `machine.vm-unreachable` error for
    it — which is what answers the `wait machine=stopped` statement both codex scripts end on. A bound secret
    reaching the guest stops the recording for the rest of the run, the same rule that suppresses the automatic
    failure screenshot, applied to this other artifact a run can leave behind.
  - `cli.py` owns command-line parsing, exit codes (`errors.exit_code`, over the one `ReliquaryError` hierarchy),
    and the output discipline described elsewhere in this file. `_build_parser()` registers all 42 commands
    through nine family-specific builder functions and returns `(parser, commands)`; `_COMMANDS` is derived from
    that return value rather than declared separately — it used to be a hand-maintained `frozenset`, which was
    just one more list of the same command names to keep in sync, so don't bring that back. The builders are
    called in the same order they appear in `--help` output, which follows this module's traditional grouping
    rather than a cleaner reorganization: for example, `fetch-media` sits alone between the script family and the
    authoring family, and `add-media` sits with cache-reclamation commands. `_dispatch` routes on the literal
    command word and is the one part of this still kept by hand; `test_cli.py` walks its source and checks it
    against the registered command set in both directions, and a command that isn't routed anywhere but reaches
    the fallback case is treated as an `InternalError` (exit 1) rather than the silent success (exit `0`) it used
    to return.

    `cli.py` is the session layer's first user: it builds one `Context` per invocation (from flags, then
    environment variables, then the default home), opens one `Session` on it, and drives every command through
    `Session` methods — except the codex family and the "locate" command, which take the `Context` record
    directly (D87). `__main__.py` is what makes `python -m reliquary` work.
- `pyproject.toml` packages `reliquary` as the `reliquary` command. The wheel and the sdist carry different
  things: the wheel is the runtime alone, and the sdist is the runtime plus what verifies it (the test suite).
  Setuptools' src-only package search keeps the repository-root test suite out of the wheel automatically;
  `MANIFEST.in` explicitly adds `tests` into the sdist (D105) and explicitly excludes `planning`, `docs`, and
  `tests/source_tree`. The suite is grafted into the sdist as a whole, rather than relying on setuptools'
  default rules, which would only grab top-level `tests/*.py` files and skip the fixture directories underneath
  them — that's why `tools/check_dist.py` names each of those fixture trees individually as required, and names
  the three excluded trees as forbidden.
- `tests/` is the test suite. Pytest is the test runner (D106), and the suite is pytest-native throughout, now
  that the conversion sweeps described below (F56–F60) are finished. It covers core helpers, guest program runs,
  lifecycle ownership, media acquisition, blueprints, machines, and scripts. Shared test machinery lives where
  it's used: the two conformance corpora and the recognizer's reference PNGs are read through `tests/corpus.py`;
  the scripting language's static validation rules are driven from one parametrized table of cases; the two
  backend adapters are checked against one shared parametrized contract; and the command manifest, the session
  wrapper methods, and the documented examples each report one test node per item they cover.

  `tests/conftest.py` holds the suite-wide configuration: the `--integration` option that turns on the
  `integration` marker, the rule that deselects that tier by default, and the home directory those integration
  runs use.

  `tests/source_tree/` is the one exception that ships nowhere: it holds tests that check the *repository*
  itself rather than the installed package — prose documents, maintainer records, the catalogue of open
  problems. If it shipped, a check that scans `docs/` or `AGENTS.md` would find neither directory in an
  installed package and report success without actually checking anything — so instead, these tests live
  somewhere that never runs from an installed package at all. None of these tests need a `skipUnless` guard,
  and a new test belongs in this directory exactly when it reads something a released package doesn't include.
- `README.md` is the human guide.
- `CHANGELOG.md` records release-facing changes.
- `planning/README.md` maps out the maintainer-facing planning machinery, and is the place to start. The
  directories are what classifies a document, and `planning/proposed/` and `planning/pledged/` each hold the
  same three filenames — `USE-CASES.md`, `ARCHITECTURE.md`, `FEATURES.md` — because they hold the same three
  kinds of document at two different stages: `planning/proposed/` holds something argued for but not yet
  approved, and nothing is actively worked on from there; `planning/pledged/` holds something approved but not
  yet delivered. Moving on to the next stage means *moving* the document (or an entry within it), and the commit
  that does the move is the record of that approval.

  The planning root itself holds things that never move and so have no "stage": the map (this README), the
  surface-change rule (`SURFACES.md`), the record of every past decision (`DECISIONS.md`, covering open,
  pledged, refused, and retired decisions alike), the task queue, and the sequence ledger (`SEQUENCES.md` — the
  highest number issued so far for each kind of numbered handle; it's a single file kept on `main` because a
  search only ever sees the branch it's run on).

  Design documents live alongside whatever they serve: a feature's own design lives in
  `planning/proposed/design/` or `planning/pledged/design/`, and a design problem that doesn't belong to any
  single feature lives in `planning/design/`. The one exception is the system-wide architectural view itself
  (the module/seam model and the numbered principles), which is the root `ARCHITECTURE.md`. Once a surface
  actually ships, its normative spec moves to `docs/spec/` — `planning/` never holds the current, authoritative
  description of something already built.
- There is no project roadmap (D42): being in `pledged/` means the project will do the work, but says nothing
  about when. `TASKS.md` has no ordering for the same reason — pledged features have no ordering either, and the
  only ordering that's binding is the ordering of steps *inside* one feature. Features are numbered with
  F-numbers and tasks with T-numbers — these are handles other things (a dependency, a commit, a decision) can
  point at — but unlike U-, P-, S-, and D-numbers, F- and T-numbers are retired once the feature or task is
  delivered and never reused; a gap in the numbering is just history, not a sign of something still pending. A
  T-number is issued the moment a task is added to `TASKS.md` (there's no "proposed" stage for a task), and every
  numbered handle is issued against the high-water marks recorded in `planning/SEQUENCES.md` — a task that gets
  struck, or a branch that never gets merged, is why the searchable record can have gaps. Design documents don't
  get a number at all. A feature has to be small enough to fit in one sprint — here, that means minutes to hours
  of work, so a "pledged feature" is much smaller than the word "milestone" usually implies; that size limit is
  enforced at the point something is pledged. References between planning items only ever point down the
  lifecycle (from a task to the feature it's part of) or sideways, never back up. The full rules are in
  `planning/README.md`.
- Before doing anything that requires approval — drafting a proposal, pledging one, or changing a project norm —
  search `planning/DECISIONS.md` for anything relevant first, and report what you found, even if you found
  nothing. Anything already recorded as killed, declined, or superseded shouldn't be revisited without new
  evidence — re-raising it without realizing it was already settled just wastes everyone's time re-arguing it —
  and an entry that supports the change you're proposing is also worth citing. Do this search whenever you're
  about to take one of these actions, not just when you happen to feel uncertain: most entries in that file
  record something that was declined, and that's the only place that decision is written down.
- `planning/TASKS.md` is the third source of work, alongside GitHub issues and `planning/proposed/`. It holds
  small work that's already pre-approved simply by being entered there, with no particular order, so anyone can
  pick up anything in it. Work that only makes sense as part of one specific pledged feature belongs with that
  feature, in `planning/pledged/FEATURES.md`, instead of here. Truly small one-off work is really just a GitHub
  issue, and sufficiently small, obvious work (housekeeping) needs no entry anywhere at all (D38). In principle
  every issue should point to a use case or a principle it serves; small items may be treated as self-evidently
  fine. Writing anything under `planning/` at all requires approval (D43) — one gate covers adding a document to
  `proposed/`, promoting one to `pledged/`, and adding an entry to `TASKS.md`, with the GitHub issue tracker
  being the only place that doesn't require this approval. Right now, the owner (Paul) is the only one with this
  authority. Agents must not add tasks to `TASKS.md` on their own initiative, and must ask before editing that
  file at all — the approval gate only applies to adding new entries, so anyone is free to pick up work that's
  already there.
- `planning/SURFACES.md` is the rule for how any surface-changing decision gets weighed. The application
  surfaces it applies to — the CLI, the embedding API, the scripting language, and machine blueprints (media,
  source, and archive are components inside a blueprint, not surfaces of their own), plus script properties,
  recorded run output, and the working-directory layout — are listed and numbered S1–S8 in root
  `ARCHITECTURE.md`, under "The application surfaces", where routine housekeeping decisions can be checked
  against a checklist. Together, the use cases, the architectural principles, and the specs make up the
  project's vision: the standing statement of what Reliquary is and is for.

  The numbered use cases — what `SURFACES.md`'s rule actually weighs a proposed change against — live in root
  `USE-CASES.md`. That list only ever contains use cases the code already fully implements today; there are no
  placeholders in it. A use case passes through three locations over its life, because being pledged and being
  delivered are two different events: it's drafted in `planning/proposed/USE-CASES.md`, pledged by being moved
  to `planning/pledged/USE-CASES.md`, and finally moved to the root once it's fully delivered — one single
  U-number sequence runs across all three locations, and neither move leaves a placeholder behind. Every pledged
  item must cite either the use case that justifies it (whether that use case is already in force, pledged, or
  still only proposed) or the architectural principle that demands it — principles justify work exactly the way
  use cases do.

  The architectural principles are the P-numbered entries in root `ARCHITECTURE.md`. Like the use cases, this
  list only contains principles the code already honors today; `planning/proposed/ARCHITECTURE.md` and
  `planning/pledged/ARCHITECTURE.md` follow the same three-stage promotion as use cases do, and promoting a
  principle to the root list is what makes it binding — only once it's there does a divergence from it count as
  a bug. Decisions recorded in `planning/DECISIONS.md` carry permanent D-numbers; they generally exist to
  support a use case or a principle, and are the reference other design choices and code commits cite. A
  decision that's later overruled stays in that file, moved to its Retired list.
- The worked FreeDOS example is the codex Reliquary actually ships (`src/reliquary/codex/`): the `freedos.rlqb`
  blueprint, its media and archive components, and the install and verify scripts. This is the live, tested
  copy — it gets copied into a user's home directory the first time it's referenced — so there's no separate
  second copy that has to be kept in sync with it.
- `docs/` describes how Reliquary currently works. `docs/spec/` holds the normative specification for every
  application surface — the CLI, the embedding API, the scripting language, the blueprint model, media,
  properties, asset resolution, the instance model, the codex, and the answer-file server. A spec is the
  authority the implementation has to match, not a description written after the fact: if a spec and the code
  disagree, that means the code has a bug, unless the spec itself is changed first, through the surface-change
  rule. The rest of `docs/` is descriptive: user-facing references and guides. If one of those contradicts a
  spec, that's a bug in the reference document, not in the spec.

  Which document is normative is marked in that document's own banner, and every descriptive document names the
  norm it defers to — the directory something lives in is just filing, not the marker of its status. One case
  splits across document kinds: a blueprint's structure is normed by the published JSON schema, while its
  semantics are normed by `docs/spec/blueprint-model.md` — so the separate blueprint guide, field reference, and
  cookbook documents are all descriptive `docs/` content, not normative specs. Design documents live under
  `planning/` instead, as described above: with their feature in `planning/proposed/design/` or
  `planning/pledged/design/`, or in `planning/design/` if they don't serve one single feature.
- The machine-readable schemas ship inside the installed package, at `src/reliquary/schemas/`, because code
  actually reads them: `blueprint-schema-v1.json` (versioned as v1 so editors can already bind to it) and
  `machine-state.schema.json`. `docs/spec/` links to these schemas rather than duplicating them. Both schemas
  have to stay in sync with the prose specs, which remain the actual authority — a JSON Schema can only capture
  the structural subset of what a spec says, so a document being valid against the schema doesn't mean it's a
  valid document overall. The shared corpus of valid and invalid example documents
  (`tests/fixtures/conformance/blueprint/`, checked by `test_conformance_corpus.py`) runs every example against
  both the parser and the schema, so the two can't silently drift apart. Where a document like this belongs is
  decided by what governs it: `planning/README.md` covers the planning machinery, `docs/spec/README.md` covers
  specs, references, and guides.
- There are three conformance corpora (collections of example fixture files used as tests), and each one checks
  something the previous ones can't. `fixtures/conformance/script/` (checked by `test_script_corpus.py`) does
  for `.rlqs` scripts what the blueprint corpus does for `.rlqb` blueprints, and adds a check the blueprint
  corpus can't make: an invalid fixture states which validation rule (V-id) must reject it, and the test harness
  checks that the actual error message cites that same id — so a fixture that fails for the *wrong* reason gets
  caught by the suite instead of only by a human reviewer. Where a rule doesn't exist yet, its fixture is marked
  `# cites: no`, and that's checked in both directions too, so the marker automatically stops being needed once
  the rule actually lands; the count of such markers is the live measurement behind decision D55.

  The third corpus is captured rather than hand-written (F43): `fixtures/conformance/transcript/` (checked by
  `test_transcript_corpus.py`, using `tests/replay.py`) holds `.rlqt` recordings of real FreeDOS installs,
  captured by the opt-in integration test tier against real QEMU and then promoted into the suite by hand. A
  fixture here proves itself by being replayable: the normal interpretation layer runs against a `ReplaySession`
  standing in at the carrier interface, and any carrier call the capture didn't originally record is reported as
  a named error. Beyond just replaying, three more things are checked, because a run that ended early would
  otherwise replay without complaint: every carrier call recorded in the capture must actually be made
  (`remaining_calls()`), the script digest stored in the header must still match the script currently in the
  tree (so an edited script is reported as a stale fixture, not a mysterious divergence), and the replay has to
  reach the same conclusion the capture recorded — the rows a command returned, the phase a script finished in,
  or the error it failed with — none of which the carrier interface itself can express.

  Fixtures come in two kinds because there are two ways into this layer: a `script` capture drives the phase
  graph, the cursor menus, and the stability gates, while a `command` capture drives the `exec` adapter's prompt
  detection and echo scanning specifically, which no script run ever touches. A capture of a run that *failed*
  is a perfectly normal fixture like any other — three of the four fixtures capturing a pathological case
  currently pin down a wrong answer that `exec` gives on an ordinary screen, so fixing one of those bugs will
  retire its fixture loudly (the fixture will start failing, on purpose). Each corpus has its own README file,
  where its findings are written up — the transcript corpus's README records six defects the very first real
  captures uncovered, every one of them a bug in the recorder itself rather than in the code under test.
- A corpus of fixtures is only as trustworthy as what its test harness can actually prove ran, which is why both
  the script and blueprint corpora are read through one shared helper, `tests/corpus.py` (F56). Every fixture
  becomes its own collected test node, named after its file, in every check that judges it, and the expected
  count of fixtures in each bucket is pinned at the point the fixtures are collected — so if a bucket somehow
  stops loading its fixtures, that shows up as a collection error, not as a suite that reports green while
  silently checking nothing. This is exactly the defect that led to decision D106: the blueprint corpus was
  running its fixtures against the parser but not against the schema, despite claiming the two couldn't drift
  apart, because looping over fixtures inside one `subTest` reports a single pass regardless of whether it
  actually checked all of them or only half. A check that splits a bucket by some marker has the same failure
  in miniature, so both `// warns:` and `// schema: rejects` markers are checked, in both directions, by one
  single check over the whole bucket, rather than by two separate checks each covering half of it. The
  transcript corpus inherited all of this for free, just by calling the same two functions — which is exactly
  what this shared helper was written to make possible.

Keep these modules deep: add behavior to the module that owns its invariant, and introduce another module only when a
real interface boundary or maintenance need justifies it. The package root exposes the intended embedding surface but
owns no implementation.

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

The CLI, the embedding API, the scripting language, and the machine blueprint (including its media, source, and
archive components) are Reliquary's primary application surfaces, numbered S1–S4. The script properties, the run's
returned output (the live event stream, `--json` documents, exit codes — persistence itself was dropped with D36),
and the working-directory layout are the supporting surfaces, numbered S5–S8, and are covered by the same rule.

Any decision that changes one of these surfaces follows the rule in [planning/SURFACES.md](planning/SURFACES.md):
first, the request is triaged by its impact on the numbered use cases ([USE-CASES.md](USE-CASES.md)) — a request
with no impact, or one that clearly aligns with the use cases, gets easy approval; adding a new use case is more
work, but still easy; a change that doesn't align with the existing use cases has to win the argument for amending
the use-case list itself first, and only starts once that amendment lands. Once approved, the change is identified
across every surface it touches, and landed on all of them together, coherently. Where a `docs/spec/` specification
disagrees with `planning/SURFACES.md` or `USE-CASES.md`, the principles and use cases win, and the design is
brought in line with them.

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

A blueprint may instead drive the same machine over the VNC plane
(`control-planes: ["vnc"]`, QEMU only today): RFB key events for
input, the framebuffer read through the shared fixed-font
recognizer for output. It is equally agentless — nothing changes
in the guest — and everything above the carrier interface runs
unmodified over either plane.

Never make a feature depend on guest cooperation. A future guest-agent transport may be optional, but agentless behavior
must remain the default and fallback.

### Placeable working directories, and what containment now means

There are six working directories, and each one can be placed independently (`home.py`; normative:
docs/spec/asset-resolution.md "The working directories"): `home`, `blueprints`, `scripts`, `cache`, `media`,
`machines`. Each one starts out unassigned. A value reaches one of them through the `Context` record a `Session` is
opened on — set via the CLI's `--<name>-dir` flags and `RELIQUARY_<NAME>_DIR` environment variables when `Context`
is constructed — and the rest are then derived: `home` supplies default locations for `blueprints`, `scripts`, and
`cache`, and `cache` (whether assigned directly or derived from `home`) supplies default locations for `media` and
`machines`. Derivation only ever fills in a directory that's still unassigned, so assigning `cache` alone doesn't
invent a `home`, and assigning `machines` alone leaves `media` to be resolved by the normal rules. A `Context` with
no home at all makes `Session` raise a fail-closed `StaticError` (`dir.unassigned`) naming `home`, right when the
session is opened — once a home is assigned, all six directories are reachable through derivation, so nothing a
session does afterward can ever find a directory still unassigned. (A bare `Context` can still be built and filled
in before a `Session` is opened on it.)

The CLI and the embedding API differ only in whether they make an assignment on the caller's behalf. The CLI gives
`home` a default (`Documents/reliquary`, falling back to `~/reliquary`) whenever neither a flag nor an environment
variable named one — so at the command line, that one default reaches all six directories by derivation, and the
"no home" error can never actually happen. That's a property of the default, not an exception carved out of the
rule — which is exactly what keeps the rule true even if the default location ever changes. The embedding API makes
no such assignment: a `Session` demands its home directory up front, and that's the entire safety mechanism behind
this design. Reading environment variables is likewise something only the CLI does, as part of its own private
setup — the underlying engine itself never reads the environment at all.

`Context` is a plain record: the six optional directory paths, plus the selected properties file (which P26
specifies it should carry), and nothing else — no methods, with all the actual resolution logic living in
`home.py`'s functions. It's kept this plain because a handful of nullable strings binds cleanly to languages like C
or Java, where Python's keyword arguments have no equivalent (P7). There's no global state involved: a `Session`
pins its whole `Context` once, at construction, from that record alone, so nothing prevents two separate `Session`s
existing in the same process. The engine functions underneath take this record as a `context=` argument (a bare
string is shorthand for `Context(home_dir=...)`), and that's the interface `Session`'s wrapper methods forward to.
The CLI builds one `Context` per invocation — from flags, then environment variables, then the default home — and
opens one `Session` on it, driving everything through `Session` methods (except the codex family and the "locate"
command, which bypass the wrapper by D87 and take the `Context` record directly). `machine_handle.py`'s and the
backend adapters' own `home=` parameters are a different, narrower thing — an already-resolved plain directory path
(sometimes a specific machine's own materialization directory standing in for one), not a `Context` — and were
deliberately left as they are.

Containment is no longer a matter of file-tree position. With six independent roots, Reliquary can no longer claim
that everything lives "under the home directory" — what P12 actually requires now is that Reliquary only ever
writes to a location it was explicitly told to use: never next to its own installed module, and never into a
source-code repository during normal use.

Nothing is ever resolved out of the built-in codex library directly (D88), on either the CLI or the API, and there's
no flag to change that: the placeable directories are the only sources Reliquary reads from, a miss fails closed,
and the resulting error names the exact command to fix it, `rlq seed-blueprint <name>`, using whatever name the
library holds. The setting that used to control this — "autoseeding," the surviving half of an older, since-removed
option — was deleted outright rather than just changed to a safer default, because a setting that *can* be turned
on is a setting CI will eventually turn on, and a blueprint that gets silently supplied this way is a bug that only
shows up later, on someone else's machine. Removing it makes P4 an absolute rule again, overriding the earlier
decision (D59) that had softened it. Correspondingly, `assets.py` has exactly one source, `DirectorySource`, which
reads each asset kind's own directory, walking it recursively by file extension, with no seeding behavior of any
kind. An asset's identity is its declared `name` field (which must be id-safe) or, failing that, its filename
stem; a collision between two assets that resolve to the same effective name within one source is an error.
Machine selection is scoped the same way: `--blueprint <name>` only matches machines whose recorded
`blueprint-source` equals what this invocation resolves to (a machine recorded with no source at all matches by
name alone).

Seeding is the one way the codex library's contents reach an actual working tree: `seed-blueprint` and
`seed-script` (there is no `seed-media`) copy files into whichever directory is currently assigned as `blueprints`
or `scripts`, whether that's inside a project's own tree or inside the home directory — the idea being to copy a
first draft and then commit that copy. All three codex verbs — those two plus `list-codex` — are CLI-only, under
P6's one named exception (D87): a library whose contents can change in a point release isn't something a program
should bind against directly, so `src/reliquary/__init__.py` doesn't export any of them, and the CLI/API parity
test reads this specific exception from the codex-family row in `docs/spec/api.md`.

Here's the default layout, assuming only `home` was assigned. A machine is entirely defined by its materialization
directory — there's no separate "root-home machine" model any more. (The old root-home machine layout — a
root-level `drives/`, a root-level `machine.json`, a root-level `vm.json` — was absorbed into the per-machine model
below and deleted. The per-machine `machine.json` described below is a new, unrelated cache state file, not a
successor to that old root-level one.)

- `blueprints/` — composed blueprints, including their media components (`blueprints_dir`)
- `scripts/` — automation scripts (`scripts_dir`)
- `cache/media/` — every cached payload (`media_dir`), under the cache root, keyed by media name; each file is
  named `<media-name>.<ext>`, and that filename is its entire identity — there's no separate sidecar record
  (D41)
- `cache/machines/<name>-<n>/` — machine materializations (`machines_dir`, whose parent is `cache_dir`), under
  the cache root. Each one has:
  - `machine.json` — the machine's resolved state. While the machine is running, this includes a `vm` section
    holding the live VM's identity, port, and PID, and a `variables` map holding the variables a script has
    `set` (cleared every time the machine starts, D36). This recorded snapshot only covers the machine's
    *shape* — its `parameters` and `scripts` fields are deliberately excluded from it, and are instead read
    fresh from the blueprint file on every invocation. They're excluded from the state digest and need no
    `apply` step to take effect, because they describe what to *run* against a machine and what to *bind* into
    it — never what the machine *is* (D101).
  - `media/` — the machine's own per-machine images and vvfat directories, named by media.
  - `screenshots/` — where a script's `screenshot` verb and an automatic failure-capture screenshot are saved,
    now that there's no separate run directory.
  - a `<backend>/` subdirectory (for example, `qemu/qemu-stderr.log`).

  A run doesn't store anything else here — it returns its output directly to the caller (D36); a `runs/`
  archive directory is planned but not yet built.

### VM ownership

Never send a control command to a backend object until its identity is verified. No code outside an adapter opens a
connection to a backend, and every adapter operation verifies the connection's identity before sending it a
command.

The identity record has the same shape for every backend (`backends.identity()`): the backend name, that backend's
own machine identifier (`backend-id` — QEMU's readable `-name` today; eventually a VirtualBox machine UUID, a
`.vmx` path, or a Hyper-V VM Id), a `token` generated fresh each time the machine starts, and an adapter-specific
`endpoint`. The token isn't decoration: an addressable endpoint can outlive the thing that created it — a QMP port
can get reused by an unrelated process, and two machines from the same blueprint with the same number, in
different homes, would share the same readable name — so the name by itself must never be enough to authorize a
command. `machines.py` persists the identity record an adapter returns into the `vm` section of `machine.json`,
atomically together with `phase`; adapters themselves don't own any state file. An identity mismatch always fails
closed; in particular, an adapter's `stop()` must never reach the point of actually telling its backend to quit
without first verifying the identity of the object it's talking to.

On QEMU, this is `launch_owned_qemu()`: it assigns the readable `-name` plus a fresh `-uuid` on every start, and
every later session checks both `query-name` and `query-uuid` against the recorded identity. When no port is given,
it picks an available local port; an explicitly requested port must be free. Both the startup-failure path and the
timeout path must terminate the child process, so a failed or timed-out launch never leaves an untracked QEMU
process running.

`Machine.session()` is the one interface every control plane uses to talk to a backend, and `Machine.qmp()` is a
named escape hatch for talking to QEMU directly — it's explicitly scoped to QEMU and refuses to work on a machine
that isn't QEMU's, rather than trying to approximate a QMP monitor for a backend that doesn't have one. Interaction
adapters are handed a `Machine` and are expected to use these two methods rather than opening their own
connections.

`machines.read_vm_state(machine_dir)` reads the recorded identity and validates the parts of it that are the same
for every backend; what the `endpoint` field actually means is up to the adapter, which validates it itself when it
opens a session. Nothing above this layer ever reads a port directly — `start_machine()` just returns the machine's
id, and the CLI selects a machine using `--blueprint` / `--machine`.

### DOS boot and scripting

A machine's drives are declared in its blueprint (see the field reference, `docs/blueprint-reference.md`), each one
naming a media component. Per-machine images are materialized into `cache/machines/<id>/media/`, named for the
media they hold. `backend_qemu.drive_args()` renders these into QEMU arguments from the machine's state: floppies
first (slots 0–1, drives A: and B:), then hard disks (slots 0–3, on the IDE bus), then cdroms, placed on the IDE
bus after the hard disks. Each removable drive gets a stable QMP `id=<key>`, so a running `insert`/`eject` can
target it later. An image's file extension decides its format (`format_options()`): `*.img` and `*.iso` are pinned
to `format=raw` (this avoids a format-probing warning QEMU would otherwise print), and any other extension is left
for QEMU to identify itself. A drive's resolved payload is never a host directory (F68): that payload shape is
legal only on a `share` device now, rendered separately by `share_args()` (see "Share devices", below) — a drive
whose media resolves to a directory fails closed in `machines._materialize_drive`, before rendering ever sees it.
Memory size and boot order are resolved into the machine's state at `create` time (the best-guess boot order is:
the floppy in slot 0, else the hard disk in slot 0, else the first cdrom).

`AgentlessGuestExec.wait_ready()` only waits for the boot process to reach a native DOS prompt, detected generically
as a bare prompt on the bottom-most non-blank row of the screen. Don't add special boot parameters for ordinary DOS
commands — drive changes, directory changes, environment variables, and program invocations all belong in
`AgentlessGuestExec.execute()` scripting instead.

### Share devices

A `share<n>` slot presents a host directory to the guest (F68; design: `planning/pledged/design/share-devices.md`),
sharing the `devices` keyspace with drives and NICs the same way NICs already do (D121) — `document.py`'s
`MachineShare` / `_share_device` mirror `MachineNetwork` / `_network_device`. A share's media must resolve to a
directory and materialize `use`; `machines._materialize_share` fails closed otherwise (`share.directory-required`,
`share.materialize-not-use`). `model` (`vvfat`/`9pfs`/`virtio-fs`) is capability-checked at assignment the same way a
NIC's `model` is (D122): `backends.Capabilities`/`Requirements` carry `share_models` (what a backend can render by
name) and `share_default`/`share_unstated` (what an *unstated* model resolves to on that backend — never silently
`vvfat`, which only ever arrives by name). QEMU renders `vvfat` and `9pfs` (F69); VirtualBox renders neither until
F71. The media's `read-only` is copied onto the share's state entry at materialization, because a backend renders
from that entry and never sees the media.

**QEMU's share capability is probed, not claimed** (F69). `9pfs` needs a QEMU built with fsdev support, which the
official Windows binaries are not, so `QemuAdapter.capabilities(platform)` runs `probe_share_models(platform)` —
one `-device help` against the binary that platform actually launches, looking for `virtio-9p-pci` — and reports
what it found (P11). `vvfat` is added to that unconditionally, since it is in every build. `share_default` is `9pfs`
where the probe found it and `None` otherwise, so an unstated-model share works on an fsdev-capable QEMU and is
refused by name on a stock one. The probe is cached per process per platform. This is why `capabilities()` takes a
`platform` at all, and why `backends.Requirements` carries one: QEMU installs a separate system binary per guest
architecture, so the report has to be about the binary the machine will actually launch, the same reason
`discover()` already takes a platform. On a Windows host, an fsdev-capable QEMU means the maintainer's
`windows-fs-raw` tree pointed at by `RELIQUARY_QEMU_HOME` (build recipe in virtio-dos's `docs/TESTING.md`).

`backend_qemu.share_args()` dispatches on the model. A `vvfat` share renders as a synthesized FAT hard disk on the
IDE bus, continuing the index sequence `drive_args()` leaves off after the last hdd and cdrom — shares are
disk-shaped only; the old floppy-shaped vvfat rendering is retired. A `9pfs` share renders as `-fsdev local` plus a
`virtio-9p-pci` device, both addressed by the slot key, with `mount_tag` = the slot key as well; it is not a disk
and takes no place on the IDE bus, so mixing the two models never shifts a guest's drive letters.
`security_model=none` is deliberate: these guests have no user ids to map, and the alternative that does map them
(`mapped-file`) would plant a `.virtfs_metadata` directory inside the shared directory. `read-only` maps onto each
mechanism's own option — `fat:` without `rw:` for vvfat, `readonly=on` for the fsdev. `RESERVED_ARGUMENTS` refuses
`-fsdev` and `-virtfs` through the settings hatch, the latter because it is QEMU's shorthand for writing both
arguments at once.

QEMU takes a snapshot of a `vvfat` share's directory the moment the machine starts. Any change made on the host
side after that requires a stop/start cycle to be picked up. Guest writes should only be read back after QEMU
stops, since that's when the write-back to the host directory actually completes. A `9pfs` share has none of that:
it is live in both directions while the machine runs. What it needs instead is a guest driver — `VIO9P` from
virtio-dos for DOS — which is the user's job to load, under U28's packet-driver precedent.

### Script dispatch

The `.rlqs` runtime's semantics are defined in terms of **samples** (discrete readings of the machine) and
**episodes** (the run of consecutive samples where a condition holds) — see docs/spec/script-spec.md, "Execution
model". Preserve these rules when touching `script_runner.py`:

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

`Session` is the only entry point into Reliquary's engine (P26): it's the exported class, opened on a home (either a
bare path or a `Context`), and it carries one thin wrapper method per stateful operation — the machine lifecycle
with its exec, file, and variable families; the media family; blueprint authoring; asset resolution;
properties/credentials/binding; and `run_script` (whose `dry_run=` argument returns a `DryRun` rather than a
`ScriptRun`) — all wrapping engine modules that are otherwise internal. Alongside `Session`, the package root also
exports supporting vocabulary: the types, the errors, `Context`, `default_home_dir()`, the free-standing parsers,
the guest-console family at the carrier layer, and the backend interface's read-only vocabulary.

An older, milestone-1 runner surface built around a single root-level home — `workflows.py`'s `Runner` /
`MachineConfig` / `run_guest_program` / `run_task` / `start`, the old root-level state files (`machine.json`,
`drives/`, `vm.json` — distinct from the per-machine `machine.json` this current model writes), and the old
`drives.py` auto-discovery logic — was absorbed into the current model and deleted, the same way later module-level
verb exports were deleted once `Session` became the one entry point (there's no backward compatibility before
1.0). The user-facing reference for the API is `docs/api-reference.md`; the target API design — settled naming
pairs, conventions, handle types — is `docs/spec/api.md`.

Rules to preserve:

- Reliquary attaches no meaning to a guest program's output — test-framework semantics (command-line flags,
  parsing results) belong to whatever project is consuming Reliquary. A CppUTest adapter used to live here and
  was removed to enforce this boundary; don't reintroduce framework-specific code.
- Refer to consumers only in a general, instructional way ("the caller", "consuming projects", generic usage
  examples) — never name a specific downstream project. The machine layer stays ignorant of who's building on
  top of it.
- The media layer (`media.py`, `library.py`) and the script runtime (`script_runner.py`) are themselves
  in-tree consumers of this surface. They drive the same flat engine functions, with the same `context=`
  argument, that `Session`'s wrapper methods forward to — nothing deeper, and no private helper underneath
  them.
- The project is pre-release; prefer a coherent interface over adding compatibility shims when its architecture
  changes. The embedding API is expected to eventually get native bindings in languages other than Python
  (planning/SURFACES.md; docs/spec/cli.md), so never adopt a design that would be hard to express in a common
  binding language like C or Java — and hold the CLI to that same constraint, since it's the fallback binding
  for any language without a native one: never make it hard to drive the CLI from a program.

## Dependencies and style

- Runtime dependencies are welcome when they earn their keep; declare them under `[project].dependencies` in
  `pyproject.toml`. Prefer the standard library only when it serves the need equally well.
- A test-only dependency is a hard requirement of the test suite. It goes in `[dependency-groups].dev` and is
  imported at the top of a module like any other import — never behind a `try`/`except ImportError` that feeds a
  `skipUnless`. That pattern turns an incomplete dev environment into a quiet skip, which is exactly how the
  blueprint conformance corpus ended up running only against the parser and not against the schema, while still
  claiming the two couldn't drift apart. A missing dev dependency should stop the suite outright and say what's
  missing. `skipUnless` is reserved for a resource that could genuinely be absent even in a fully supported
  setup, and the bar for using it is high. The suite is run from two places — the repository itself, and an
  unpacked sdist (D105) — and a missing *document* isn't one of the legitimate reasons to skip: a test that
  reads something a released package doesn't include belongs in `tests/source_tree/`, which ships nowhere, rather
  than being guarded by a check that quietly turns "can't do its job here" into a pass.

  The default test run skips nothing, in either of those two places, and that's an assertion the suite makes
  directly rather than something inferred from a test count (F57). The two opt-in FreeDOS integration test
  runs — one for QEMU, one for VirtualBox — are marked `@pytest.mark.integration` and are deselected (excluded
  from the run entirely) unless `pytest --integration` explicitly asks for that tier. A deselected test and a
  skipped test aren't the same thing: a marker records that the tier was deliberately not chosen, where a plain
  skip can't tell you whether it was chosen and failed or just never ran. So any actual skip in the suite is
  treated as a bug to fix, never as something to tolerate. The repository's run collects 2,293 tests and an
  unpacked sdist's run collects 2,236, four deselected in each case — that difference is `tests/source_tree/`
  correctly not being present in the sdist, and neither run has any skips. Explicitly selecting the integration
  tier on a host that doesn't have the backend installed is a failure that names the missing capability (P11), not
  a skip either — the tier was asked for, so it has to actually run or fail.
- Pillow is the project's image library: it's used for screenshot conversion, for the landmark assets' image
  decoding and pixel comparison (`landmarks.py`, F65), and for the pixel half of the quiescence measurement,
  which diffs frames using `ImageChops` rather than comparing pixels one at a time in Python. Nothing in this
  codebase hand-writes an image encoder.
- Support Python 3.12 and newer, and actually verify it — the floor-version test run described under "Required
  checks" is what makes that a tested claim rather than just a hope. The stated floor used to be `>=3.9`, until
  that check was first run and 3.9, 3.10, and 3.11 all turned out to fail (D95).
- Windows is the only host platform Reliquary is actually delivered on — the only one it's developed on, tested
  on, and claims support for in its packaging classifiers. Host-specific code should still be written portably —
  the code paths for other hosts exist and should stay correct (the Documents-folder lookup, the
  credential-store backends) — but they are never actually exercised, so never state or imply support the
  project hasn't actually tested. Under P11, an untested platform is a capability Reliquary simply doesn't
  claim, not a quiet promise it's making anyway. Claiming support for another host means running the test suite
  there, either in CI or on real hardware — the three gating jobs this would require are listed in
  `proposed/FEATURES.md`, under "Horizon" / host portability (U18 is the drafted use case for getting there from
  here).
- Keep lines near 79 columns and match the existing formatting style.
- Prefer small public interfaces, with lifecycle complexity kept behind them rather than exposed.
- Preserve useful exception context and write actionable diagnostic messages.

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

Paul holds copyright in the whole work, and reserves the right to relicense the project on any terms he chooses.
Nothing is currently planned — the reservation exists purely so that option isn't lost by default. Two things follow
from this, and neither is negotiable for an individual change:

- The project must own every line it ships. Only a party that holds rights to the whole work can relicense it, and
  enforcing copyleft against a violator also requires that kind of standing. A single file the project can't
  account for the rights to would permanently and silently rule out both.
- For incoming code, the test is whether the project can acquire ownership of it, not whether its license is
  GPL-compatible. Being GPL-compatible isn't good enough on its own — code the project can't acquire title to
  can't come in, no matter what license it carries.

Vetting a dependency and describing the project's policy in public documents are two different jobs, and they use
two different standards on purpose. What the project *states* — in README.md, CONTRIBUTING.md, and CLA.md — is
simply that relicensing is reserved and nothing is currently planned. That's true, and it's all the disclosure the
reservation requires. What the project *vets against* when considering a dependency, however, is the strictest
realistic outcome: a future commercial dual license. Vetting against a weaker standard would quietly give up the
reserved option without anyone noticing.

So the question to ask about any external source is "could this ship inside a proprietary product?" — never "is
this GPL-compatible?" The second question is much easier to answer yes to, which is exactly why it's the wrong one
to ask: Reliquary's GPL side could absorb a lot of code that a future commercial side never could, and the gap
between those two sets is exactly what the reservation is meant to protect.

This asymmetry is why the discipline matters: judging a dependency correctly costs nothing at the moment it's first
considered, but can't be revisited later at any price. By the time it would matter, the code is already
load-bearing, and whoever wrote it is under no obligation to negotiate.

Because of this, contributions are only accepted under the copyright assignment in `CLA.md`, with an automatic
fallback to an exclusive, sublicensable license in any jurisdiction where assignment itself isn't legally possible.
Once a contribution is assigned, the contributor's files carry Paul's copyright notice, since he then genuinely
owns them — the REUSE metadata records ownership, not authorship; authorship credit lives in the git history
instead. Keep the contributor-facing terms in `CONTRIBUTING.md` in sync with this policy.

Never merge third-party source code into the project — not permissively licensed source, not snippets that look
public-domain, not vendored files. A contributor can't assign rights they don't own, and neither can the project.
Third-party code can only enter as a declared dependency, never any other way.

### Dependency licence tiers

Every runtime dependency sorts into exactly one of three tiers below, judged against the commercial-dual-license
standard described above, not against plain GPL compatibility. Placing a dependency in a lower tier than it
actually belongs in is the single change most likely to cost the project something it can never get back.

| Tier | What qualifies | Standing |
|---|---|---|
| **1 — Sublicensable** | MIT, BSD-2/3-Clause, Apache-2.0, ISC, PSF, MIT-CMU/HPND, Zlib | Freely dependable on. Attribution obligations carry into any redistribution. |
| **2 — Arm's length only** | LGPL as an unmodified, separately installed dependency; GPL invoked as a **separate process** | Permitted, but never combined into the project. Vendoring it, forking it, patching it, or bundling it into a frozen executable demotes it to tier 3. |
| **3 — Refused** | Any GPL/AGPL code that would be linked, imported, or copied into the project | Never accepted. It's compatible with Reliquary's own GPL license, but it would be fatal to the relicensing reservation — which is the entire reason this tier exists. |

Build-time and development dependencies are entirely out of scope for these tiers — they're never distributed, so
their licenses don't impose anything on Reliquary. The tiers only govern what `pip install reliquary` actually
pulls in.

There's one case that sits outside these tiers entirely: a dependency that is itself first-party. This rule is
written down because the project has relied on it before and will again. The table above refuses a GPL-3.0-only
package the project imports — but the reason the tiers exist at all is to protect the relicensing reservation from
code the project can't acquire title to, and the owner's own separate work doesn't have that problem: its copyright
is held entirely by Paul Galbraith, and its own contributions are assigned under that other project's own CLA.
Exercising the relicensing reservation would relicense both works together, so nothing is given up by depending on
it. The test for this exception is ownership, not license, and it's conditional: a dependency only keeps
first-party standing for as long as its copyright stays wholly in the same hands. One that stops qualifying falls
back to the ordinary table, where an imported GPL package is tier 3. `remanence` used to qualify for this exception,
until D108 removed the at-rest disk access it supported and the layer that wrapped it; if some future consumer
needs that capability again, it would depend on `remanence` directly, which has nothing to do with these tiers.

Right now, every runtime dependency in the project's dependency tree is tier 1, except `qemu.qmp`, which is tier 2
and discussed under "Architecture and prior art" below. When adding a new dependency, check its *entire* transitive
dependency tree, not just the package you're naming directly — a tier-1 package that pulls in a tier-3 package is
still a tier-3 problem.

Two of tier 2's conditions exist purely because of the commercial-license standard above, and both are easy to
violate by accident:

- A frozen single-file executable does not count as "arm's length." Shipping Reliquary via PyInstaller, Nuitka, or
  py2exe would bundle `qemu.qmp` in a form the end user can't replace — which is exactly what LGPL's "relinking"
  requirement forbids. Decide how to satisfy LGPL before building an executable like that, not after.
- LGPL requires that users be permitted to reverse-engineer the library for the purpose of debugging modifications
  to it. A typical commercial EULA's blanket anti-reverse-engineering clause would violate this. If a commercial
  license is ever drafted, this needs an explicit carve-out — it's easy to miss until someone reads both documents
  side by side, and by then it's already a violation.

## Development environment

uv provisions and owns the development environment (D94). One command creates `.venv`, installs the project in
editable mode, and installs the `dev` dependency group:

```powershell
uv sync
```

`uv.lock` is committed to the repository, and it's what makes "the environment the test suite passed in"
reproducible — that matters here because, under P22, the test suite is what actually gates a change from landing.
`uv sync` reproduces the locked environment exactly; `uv lock` is the command that deliberately updates it. Don't
install development tools globally, and don't manage `.venv` by hand — it belongs to uv.

Runtime dependencies stay listed under `[project].dependencies`. The `dev` group currently contains `jsonschema`
and `pytest`: the build frontend and the upload tool that used to be here both dropped out once uv took over their
jobs, and pytest was added once it became the test runner (D106). Both are hard requirements of the suite, in the
sense described above — imported and invoked directly, never behind a guard. Pytest's floor version, `>=8.4`, is
the release that added `--disable-plugin-autoload` as a command-line option, which is what lets the project's own
configuration turn plugin autoloading off, instead of leaving that decision up to whoever happens to run the
suite.

## Required checks

Run checks through uv, which uses the locked environment.

```powershell
$pythonFiles = (Get-ChildItem src/reliquary,tests -Filter *.py).FullName
uv run python -m py_compile $pythonFiles
uv run pytest
uv run --python 3.12 pytest
uv build
```

The third line above is the floor-version check, and it's not optional. The minimum supported Python version is a
published claim (`requires-python` in `pyproject.toml`), so it needs to actually be tested, the same way this file
already treats host platforms elsewhere: an untested platform, or an untested Python version, is a capability the
project doesn't get to claim — not a quiet promise it's making anyway (P11). uv installs the interpreter itself, so
running this check costs nothing more than one extra command. It was added after the claimed floor turned out to be
wrong: the project used to claim `>=3.9` without ever testing it, and once this check was added, 3.9, 3.10, and
3.11 all turned out to fail (D95).

The suite's own configuration, in `[tool.pytest.ini_options]`, is written for a stranger's environment, not just
this one (D106). Since the suite ships inside the sdist (D105): `--disable-plugin-autoload` means no plugin the
project didn't explicitly ask for can change what a test run collects; `--strict-config` and `--strict-markers`
turn an unreadable option or an undeclared marker into an error instead of a silent no-op; `testpaths` lets a bare
`pytest` command find the suite on its own; and `minversion` refuses to run under a pytest too old to honor the
first of those settings. None of these are just preferences — each one exists so that a run somewhere else collects
exactly what a run here collects. The one marker this configuration declares is `integration`, for the opt-in
tier; `tests/conftest.py` owns the `--integration` option that turns it on, the rule that deselects it by default,
and the `integration_home` fixture those tests use.

`uv build` builds an sdist and then builds a wheel from that sdist, which checks that the source archive is
complete. After any packaging-metadata change, check `PKG-INFO` in both built artifacts for at least the name,
version, Python requirement, and runtime dependencies, then run `uv run python tools/check_dist.py`, which checks
what each artifact is required to contain: the grammar file, the schemas, and the codex in the wheel; the test
suite and each of its fixture directories in the sdist; that the wheel contains no tests at all; and that the sdist
contains none of `planning/`, `docs/`, or `tests/source_tree/`. This check exists because nothing inside a released
package inspects itself: package data is exactly the kind of thing that can silently go missing, and a missing
`.lark` grammar file would break an installed copy of Reliquary while every test that only reads the source tree
would still pass.

For any release-facing packaging change, run two separate checks, because they answer two different questions.
Whether the source archive is *complete* is proved by the build itself: `uv build` builds the wheel *from* the
sdist, so a source archive that's missing something the build needs fails right there, instead of silently —
and that's true whether or not the test suite is included in the archive. What actually including the test suite
buys you is a different question, one only a stranger can really ask: does it work when unpacked somewhere else
entirely and run from there? That's what a downstream packager actually does, at package-build time, on a platform
this project has never tested on:

```powershell
tar -xzf dist/reliquary-<version>.tar.gz -C <scratch>
cd <scratch>/reliquary-<version>
$env:PYTHONPATH = "src"; pytest
```

That interpreter needs the `dev` dependency group — `pytest` and `jsonschema` — which is a cost D106 accepted
deliberately: `python -m unittest tests` is no longer how the suite is run, and now that the conversion to pytest
is finished (F60), it wouldn't collect anything at all — the hook that used to make it work is gone. Pytest was
chosen because it's packaged and available wherever a downstream packager works. Expect 2,236 tests, four
deselected, and none skipped — compare that to the repository's own 2,293 (see "Test expectations" below): the
difference is exactly `tests/source_tree/`, which never ships, and a *skipped* test in this run is just as much a
defect as it would be in the repository's own run. `tests/conftest.py` ships as part of the suite, so the
integration tier is deselected by default here too, the same as in the repository. Check the installed wheel
itself by actually using it — run `rlq --version` and try importing it — since the wheel carries no test suite of
its own to run.

Publishing is done with `uv publish` (D94), which uploads everything in `dist/*` to PyPI. Since there's no CI
(P22), there's no trusted-publishing setup either, so publishing needs an explicit token
(`UV_PUBLISH_TOKEN` or `--token`), and `uv publish --dry-run` walks through the whole process without actually
uploading anything. `twine check` was deliberately removed from this process: its job was checking that
reStructuredText renders correctly, but this project's readme is Markdown; the package index already validates and
rejects bad metadata on its own; a rejected upload doesn't consume a version number; and `tools/check_dist.py` is
this project's real check on what gets published. If the readme ever stops being Markdown, reconsider bringing
`twine check` back.

Run `git diff --check` before handing work back.

Hands-on tests require QEMU. Use `--home-dir` pointed at a scratch directory or a deliberately reused test home,
rather than writing into the default per-user home.

The FreeDOS install-and-verify integration tests are opt-in — they're deselected in the default suite, and need
network access to fetch the LiveCD on a fresh home directory. `--integration` is what selects this tier, and it's
the only thing that does — naming the specific test module on the command line without also passing
`--integration` still deselects it. QEMU is the default backend for these tests. The VirtualBox variant (F52) pins
`backend: virtualbox` on its seeded blueprint and needs `VBoxManage` on `PATH`. The VNC variant (F63) pins
`control-planes: ["vnc"]` on its blueprint and runs on QEMU. Use a separate reuse-home for each of the three runs:
the same machine id can't span two different backends, and the VNC run's seeded blueprint and materialized machine
carry different settings than the plain QEMU run's does:

```powershell
# optional: reuse a home so cache/media survives reruns
# $env:RELIQUARY_INTEGRATION_HOME = "C:\Temp\reliquary-integration"
uv run pytest --integration tests/test_freedos_install_integration.py
uv run pytest --integration tests/test_freedos_virtualbox_integration.py
uv run pytest --integration tests/test_freedos_vnc_integration.py
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

Guarantees about the backend adapter interface, which the suite tests against a fake adapter rather than a real
hypervisor (`tests/fake_backend.py`, installed with `backends._set_adapter`) — no unit test may probe or launch a
real backend:

- a requirement no candidate backend can honor fails closed, naming both the backend and the requirement, before
  any image work happens
- the priority walk picks the first backend that's both available and capable, so being merely available never
  wins on its own, and the priority order never substitutes for an actual capability check
- a `backend-settings` key the assigned adapter doesn't define is refused at materialization; an argument that
  restates a first-class field or the VM identity is refused, naming which field or identity piece owns it; and
  a settings section belonging to a different, inactive backend is kept as-is without being checked
- a declared `backend` field skips the priority walk entirely, and an unavailable or incapable declared backend
  still fails closed
- a stub adapter claims no capability at all, even on a host where its backend is actually installed
- the machine model hands the adapter a resolved state and gets an identity record back — no backend argument is
  ever built above this interface, and no port number is ever read there either

Every backend adapter that's actually built is required to satisfy one shared, parametrized contract
(`tests/test_backend_contract.py`, F59), rather than each backend's module having its own near-duplicate test:
the name it answers to everywhere, its capability report, its image file extension, whether discovery correctly
finds it and correctly reports it absent, the host font it reads and caches, and its refusal to command a VM whose
recorded identity doesn't match. Each of these checks becomes a separate test node per backend, so a requirement
can't be satisfied by QEMU's tests while quietly missing from VirtualBox's (P25). All a backend actually
contributes on top of this shared contract is a "driver" — where its executable is found, where its font lives,
how it aims a stop command at a mismatched identity — so a third adapter inherits the whole contract just by
adding its own driver, rather than by copying a test file. What stays in `test_backend_qemu` /
`test_backend_virtualbox` individually is only what's genuinely specific to that one backend: qcow2 images versus
VDI images, building an argv list versus calling `VBoxManage` verbs, QMP versus scancodes.

Milestone-9 guarantees needing the same care:

- every deliberate error subclasses `ReliquaryError`, and the four run-surface classes exit 2/3/4/5
- a run creates no `runs/` directory and writes nothing to the machine directory
- `--progress jsonl` puts the event stream on stdout and nothing else, terminal event last
- a human `--progress` mode leaves stdout empty
- a bound secret never reaches the event stream, and it suppresses automatic screenshots afterwards
- a cancellation ends at a boundary with an in-flight input delivered whole
- a machine variable is cleared by `start`

### The test idiom

Every test is written in pytest-native style (D106), and this policy now has no exceptions: a bare `assert`
statement, a fixture where `setUp` would previously have been used, and `parametrize` where a loop or a `subTest`
would previously have been used. That last one matters for a real reason, not just style: a parametrized test case
becomes its own collected test node, so its count is itself something the suite checks — a `subTest` doesn't give
you that. That gap is exactly how the blueprint conformance corpus ended up running only against the parser and
not the schema, while still claiming the two couldn't drift apart. No `unittest.TestCase` and no `subTest` should
survive anywhere in the suite; either one showing up in a new test is a regression, not a style choice someone made.

`unittest.mock` stays — this conversion didn't touch it. It's the mocking library, not the test runner; pytest
replaced the runner (`unittest`'s own test-running machinery), and nothing has replaced `unittest.mock`. The
general preference for the standard library over third-party dependencies still holds everywhere else — pytest is
one dependency the project judged worth adding, not a sign that the bar for adding dependencies has been lowered.

The conversion to pytest happened in five separate sweeps. F56 covered the two conformance corpora, which is where
the shared parametrization helper `tests/corpus.py` was introduced. F57 covered the two integration test runs,
which needed a fixture that the older `unittest`-based style couldn't provide. F58 covered the seven
script-language test modules. F59 covered the ten machine- and backend-related modules. F60 covered the remaining
twenty. `python -m unittest tests` stopped working as an entry point once the last sweep landed: with nothing left
for it to collect, it would have reported success over a completely empty run, so `tests/__init__.py` no longer
has the `load_tests` hook that used to make it work.

Each sweep kept the same test count, except where it deliberately increased it — and those increases are exactly
why the conversion was worth doing: a `subTest` loop becomes one node per case, and a table of cases becomes one
node per row. F58 is a good worked example: the script-language test modules' 350 tests became 426, and every one
of those 76 new tests came from either the V-rule case table or a `subTest` loop that stopped hiding its individual
cases — no assertion was added or removed. F59's 460 became 575 the same way, with the wrapper-method roster and
the fixture directory among the tables that stopped reporting a single pass for every row they covered. F60's 470
became 594, mostly from the command manifest, whose thirty-seven declared capabilities now each report their own
result. A test count that changed for any *other* reason means a test was lost somewhere.

A flattened test module is at risk of function-name collisions. Two separate `TestCase` classes could each safely
contain a method named `test_a_running_machine_is_refused`, but once flattened to module level, the second
definition silently replaces the first, and the test count quietly drops by one. Each sweep checked the test count
per module specifically to catch this; where two tests genuinely needed the same name, the fix was to give one a
name that actually describes what it's testing, not just to tack a numeric suffix onto it.

A static validation rule is tested from a table of cases, not one test method per rule (`test_script_validation.py`):
each case in the table names which rule it exercises and becomes its own collected test node, named accordingly.
One parametrized check walks the full range of `script_nodes.RULE_OF` and fails, naming the specific missing rule,
if the language ever gains a new rule with no case covering it. The table also includes cases for the layers below
validation — the lexer's own rules, the placement matrix — so this check needs no separate list of exemptions,
which would just be one more list to keep in sync by hand.

A corpus of fixture files is read through the shared `tests/corpus.py` helper, rather than each test module
growing its own file-globbing logic: `fixtures` pins down the expected count for a bucket of fixtures at the point
they're collected, and `parametrize` names each resulting test node after its file. A check over a fixed
vocabulary the package itself declares — for example, a schema's enum of phase names — isn't a corpus of files and
is parametrized directly instead.

## Documentation maintenance

README.md is a human-facing guide to what Reliquary does, why it exists, and how to use it. Keep it explanatory and
task-oriented. Do not move agent instructions, implementation constraints, roadmap discussion, or maintenance notes into
it.
When Packer and Vagrant are mentioned together in prose, name Packer first and Vagrant second.

After changing commands, flags, paths, behavior, or Python interfaces, update README.md, CHANGELOG.md, and this
file wherever they're affected. The CHANGELOG is a historical record, not documentation of the current state:
everything written under a released version's header records what was true at release time, and stays exactly as
released, byte for byte — including stale paths, broken links, renamed concepts, and wording later superseded
elsewhere. That's the historical record, and "fixing" it after the fact would falsify it. Corrections and
follow-ups get new entries under the unreleased section instead — never edits to already-released text. The one
exception is removing content that's private or legally problematic: redact as little as possible (replace or
drop only the problematic text, never reword or modernize anything around it), and record that redaction as its
own entry under the current release. The unreleased section, by contrast, can be freely edited until it actually
ships. Validate any documented CLI syntax against `reliquary --help` and the relevant subcommand's `--help`.

## Architecture and prior art

Every project named in this section is a reference for its concepts and designs only — none of them is a source
Reliquary implements from. This has been the rule since before the license change: study a design and reimplement
it independently; never read another project's code with the intent of reimplementing, porting, or translating it.
The move to GPL-3.0-only and the relicensing reservation add a second, independent reason this can never change:
the project can't acquire ownership of someone else's code, so adopting it would give up the reservation
permanently. If these two reasons ever seem to disagree, the "study and reimplement" rule wins — a close
translation of someone else's code is still a port, no matter what any license would technically permit.

Every project named below should be vetted the way a dependency is vetted: against the commercial-dual-license
standard, not against plain GPL compatibility. For each project named below, the "study and reimplement" rule
already settles the question on its own, so the license analysis is never actually what's doing the work — but
it's recorded anyway, because a license argument and the "study and reimplement" rule can fail independently of
each other. This section has already seen that happen once: the reasoning below about os-autoinst was true while
Reliquary was BSD-licensed, and became false the day Reliquary switched to copyleft — while the "study and
reimplement" rule sitting right next to it didn't move at all. A boundary that rests on a license argument alone
is one license change away from having no boundary at all.

Reliquary uses QEMU's published `qemu.qmp` library for protocol handling, and implements the machine-lifecycle
logic itself.

`qemu.qmp` is tier 2, and it stays there by being left alone: it's an unmodified, separately installed dependency,
imported but never vendored, forked, patched, or frozen into a bundled executable. Most of it is licensed
LGPL-2.0-or-later, which tier 2 permits. One file inside it, `qemu/qmp/legacy.py` (`QEMUMonitorProtocol`), is
GPL-2.0-only and must never be imported — it sits inside a package the project already depends on, so nothing
except this explicit rule stops it from being imported by accident, since it would look like an ordinary import.

QEMU itself is tier 2 because Reliquary keeps it at arm's length: Reliquary invokes `qemu` as a separate program,
communicating over the documented QMP protocol, rather than combining it into Reliquary itself — that separation
is what qualifies it for tier 2 at all, not an incidental detail. Never link against QEMU, never vendor it, and
never ship a patched build of it.

QEMU's in-tree `QEMUMachine` helper is not published as an independent, separately installable package. Even if
that changes, the answer is still no unless it's published under a permissive or LGPL license: as it exists today,
that in-tree code is GPL-2.0-only, the project can't acquire ownership of it, and adopting it would give up the
relicensing reservation. This replaces an earlier note in this file that left the door open to reconsider based on
maintenance concerns — maintenance is no longer the question here.

QEMU's own functional tests validate the general model of scripting a guest over QMP and checking observable
state. Reliquary adds the DOS-specific layer on top: keyboard conventions, VGA text-memory scraping, prompt
detection, and vvfat staging.

SUSE's os-autoinst (the engine behind openQA) is the closest prior art to Reliquary as a whole. It drives OS
installers using screen matching and key injection over QMP/VNC, with per-operation "consoles" (VNC, serial,
virtio-terminal, ssh) that resemble Reliquary's control planes, multiple backends (qemu, svirt, bare metal) that
resemble Reliquary's backend adapter interface, command completion over a serial connection using echoed marker
strings, per-step screenshot records, and snapshot "milestones" for resuming long installs partway through. Treat
it strictly as a reference for its concepts in control-plane and backend design — Reliquary learns from its
designs (the input event model, its "needle" area types, its console abstractions), never from its actual code:
study its documentation and its ideas, and reimplement from scratch. The bar here is the "study and reimplement"
rule, and licensing has no bearing on where that bar sits — this project has now learned that the hard way, since
its own license changed and the rule did not move with it.

It's worth keeping this record straight, since the project's own earlier reasoning about this is still findable
and is now wrong. While Reliquary was licensed BSD-3-Clause, os-autoinst's GPL-2.0-or-later license by itself was
enough to bar porting its code, its "needles," or its test modules. Under Reliquary's current GPL-3.0-only license,
that particular argument no longer holds: code under GPL-2.0-**or-later** can be brought under GPLv3, so license
compatibility stopped being the obstacle the moment Reliquary itself became copyleft. But nothing about the actual
boundary changed — what enforces it now is firmer than what enforced it before:

- The "study and reimplement" rule applies first, regardless of licensing. A close translation of someone else's
  code is a port no matter what any license permits — that was always the real rule.
- Ownership matters permanently. The project can't acquire ownership of SUSE's code. Merging it in would give up
  the relicensing reservation for good — a one-way decision that would happen silently if it weren't watched for.

The same correction applies to `consoles/VNC.pm`, os-autoinst's RFB client — precisely the file a VNC control plane
implementation would be tempted to reach for. It's dual-licensed `Artistic-1.0 OR GPL-1.0-or-later`. An earlier note
in this file arguing that "copyleft doesn't reach it" was never actually the reason it's off-limits, and in any
case both of its license options are things a GPLv3 project can take code under. Artistic-1.0 is also too vague a
license to build anything on top of, in line with the FSF's long-standing objection to it. This file is off-limits
for the same reasons as the rest of the os-autoinst codebase, which apply to it exactly as they apply everywhere
else in that project. Deliberate differences from os-autoinst that Reliquary should keep: VGA text-memory scraping
instead of image-based "needles" for text-mode guests, authored step documents instead of Perl test modules, and a
local, ephemeral-machine tool instead of a hosted testing service (a scheduler, worker pool, and web UI are
permanently out of scope for Reliquary).

Keysight's eggPlant Functional is the closer analogue specifically for the display control-plane design: a
commercial GUI testing tool that drives its target system over either VNC or RDP, matches screens by image, and
carries a click point embedded inside the matched image. Its vocabulary lines up almost one-to-one with
Reliquary's own settled landmark design (`docs/spec/landmarks.md`) — its "hot spot" corresponds to Reliquary's
"spot," its "image collection" to Reliquary's "variant," its "search rectangle" to Reliquary's still-deferred
"selecting region," and its "tolerance" to Reliquary's "similarity percent." That convergence is the useful part
of this comparison: it shows this general approach to image-based asset matching is well-established, not
something Reliquary invented from nothing. eggPlant is proprietary, so the general concept-reference rule applies
here by default: its public documentation is the entirety of what's available to read, and it's also the *only*
thing that should be read — never decompile a trial binary, never read EULA-gated material, and never read
support-portal content.

eggPlant is the one reference in this section where the relicensing reservation *raises* the stakes rather than
lowering them. A GPL hobby project's design happening to converge with a commercial tool's vocabulary would
normally be unremarkable — but a project that has publicly reserved the right to relicense is a more attractive
target for a patent holder working in the same space, and the convergence documented right here against
`docs/spec/landmarks.md` is a discoverable record of that. The convergence is genuine and was arrived at
independently, which is exactly why it should stay documented as such — it's evidence of parallel design, not of
borrowing. If the relicensing reservation is ever actually exercised, this is the reference to review first, with
legal advice.

Espressif's `pytest-embedded-qemu` is useful prior art for a possible future `pytest-reliquary` plugin: it shows
how to orchestrate pytest on the host around a native test framework running on the guest. It's not directly
reusable, since it assumes Espressif's own hardware targets, serial output, and the Unity test-result format. It's
MIT-licensed, so it's tier 1 — the only reference in this section that could, in principle, actually be depended
on (as a declared dependency, never as copied source), and its designs are governed by the same "study and
reimplement" rule as everything else here.

FreeRDP is the realistic choice to vendor if an RDP display carrier is ever built (see
`planning/proposed/FEATURES.md`). It's Apache-2.0 licensed, so it's tier 1, with two conditions attached: its
NOTICE-file obligations carry into every redistribution of Reliquary, and since it was historically relicensed
*from* GPL, each component's actual licensing needs to be verified at the individual file level before anything
is vendored — a single project-level license statement isn't sufficient evidence for a codebase with that kind of
relicensing history.
