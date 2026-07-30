<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Python API reference

This is the **descriptive** reference for Reliquary's implemented
Python surface — the first binding of the embedding API. Everything
below is importable from the `reliquary` package and mirrors the
CLI: the two are one semantic surface. The API's norm is
[docs/spec/api.md](spec/api.md) — the binding realizes the surface,
never defines it — and where this reference disagrees with the
spec, this reference has the bug.

Reliquary attaches no meaning to guest output; interpreting
results belongs to the caller.

## The working directories and Context

Reliquary has six working directories — `home`, `blueprints`,
`scripts`, `cache`, `media`, `machines` — and every one is
placeable. Each starts **unassigned**; the rest derive from what is
assigned, and a directory with no value when resolution needs it
raises `StaticError` naming it.

- `set_home_dir(path)` - Assign the home; `blueprints`, `scripts`
  and `cache` derive under it.
- `set_cache_dir(path)` - Assign the cache root, explicitly or over
  the derived one; `media` and `machines` derive under it.
- `set_blueprints_dir(path)` / `set_scripts_dir(path)` /
  `set_media_dir(path)` / `set_machines_dir(path)` - Assign a leaf
  directly. Assigning one leaves its siblings where the rest of the
  resolution puts them.
- `default_home_dir()` - The value the CLI assigns when nothing
  named a home: `Documents/reliquary`, falling back to
  `~/reliquary`. Computed, never assigned by the library.
- `documents_dir()` - Resolve the user's platform Documents
  folder, or `None` when it cannot be determined.
- `Context(home_dir=None, blueprints_dir=None, scripts_dir=None,
  cache_dir=None, media_dir=None, machines_dir=None)` - A plain
  record of six directories and nothing else — there is no axis
  deciding where a name may come from, the directories being the
  sole sources — scoping one call or a group of
  calls, independent of the process-global assignments. Every
  function below that resolves a working directory accepts a
  `context=`: omit it (the common case) to use the globals; pass a
  bare string as shorthand for `Context(home_dir=that_string)`;
  pass a `Context` to pin whatever slots it fills, per call, safe to
  vary within one process. Unfilled slots fall through to the
  globals and then to derivation. The CLI only ever drives the
  globals from its flags — scoped `Context` objects are an
  embedding-API-only capability.
- Resolvers, each accepting `context=None`: `home_dir`,
  `blueprints_dir`, `scripts_dir`, `cache_dir`, `media_dir`, and
  `machines_dir`.

**The embedding API assigns nothing.** A call that resolves a name
with no directory assigned raises rather than reading the
developer's home or a stray current directory, and nothing resolves
out of the built-in codex on any surface, so it never feeds an
automated run at all. The
environment (`RELIQUARY_HOME_DIR` and its five siblings) is honoured
by the CLI and never by the library, for the same reason.

## Cached machines (the blueprint lifecycle)

- `create_machine(name, *, context=None, properties=None,
  properties_file=None, dry_run=False, backend=None)` - Materialize
  a new machine from a blueprint name; returns the machine id
  (`<blueprint>-<n>`, lowest free number). The blueprints directory
  is the sole source: nothing is seeded, and a name only the built-in
  library holds is refused with the seed command named.
  `properties` / `properties_file` bind any
  `${key}` a media location references. CLI twin: `create-machine`.
- `create_machine(name, dry_run=True)` returns a `DryRun` instead —
  never a machine id, so misuse is a `TypeError` at the call site
  rather than a confusing failure three layers down. It materializes
  nothing, seeds nothing, fetches nothing, locks nothing and never
  prompts, and it reports the machine id it would allocate, the
  backend it would land on, each drive's resolved plan and where
  every media would come from. It raises what a create would raise,
  where a create would raise it. `backend=` asks whether the
  blueprint would work on a *named* backend — capability decides and
  it need not be installed here — and is legal only with
  `dry_run=True`. Normative:
  [cli.md](spec/cli.md#the-dry-run).
- `DryRun` - `operation` (the verb described), `report` (the
  printable rendering) and `plan` (the operation's own document,
  which is what `--json` serializes).
- `create(machine, namespace, *, context=None, blueprint_name="")` -
  The same, from an already-parsed machine component and the
  resolution namespace (`load_namespace`).
- `list_machines(context=None, blueprint=None)` - List machines.
  CLI twin: `list-machines`.
- `resolve_machine(*, machine=None, blueprint=None, context=None)` -
  Resolve CLI-style selectors to exactly one machine id. The
  selectors are mutually exclusive: `machine=` is the full id
  (`<blueprint>-<n>`) exactly, or `blueprint=` selects that
  blueprint's sole machine. No prefix matching and no
  bare-number form.
- `start_machine(machine_id, *, display=False, context=None)` -
  Start a machine through its assigned backend's adapter and return
  its id; the verified VM identity is recorded in the machine's
  `machine.json` as a `vm` section, written atomically with `phase`.
  CLI twin: `start-machine`.
- `stop_machine(machine_id, context=None)` - Stop a running machine;
  identity mismatches fail closed. CLI twin: `stop-machine`.
- `destroy_machine(machine_id, context=None)` - Delete the machine
  entirely; frees its number for reuse. CLI twin:
  `destroy-machine`.
- `recreate_machine(*, machine=None, blueprint=None, context=None,
  properties=None, properties_file=None)` -
  Destroy the selected machine and recreate it under the same id,
  re-resolving the current blueprint. Returns the reused id. CLI
  twin: `recreate-machine`.
- `apply_blueprint(*, machine=None, blueprint=None, context=None,
  properties=None, properties_file=None)` -
  Adopt the current blueprint into a stopped machine: absorbable
  changes are applied and the baseline digest re-recorded; a changed
  `size` or `materialize` on an already-materialized media image
  fails closed. Returns the id. CLI twin: `apply-blueprint`.
- `get_machine_dir(*, machine=None, blueprint=None, context=None)` -
  The selected machine's cache directory as an absolute path (any
  phase). CLI twin: `get-machine-dir`.
- `mark_stopped(machine_id, context=None)` - Reconcile the phase of
  a machine whose QEMU process has gone.
- `load_machine_state(machine_id, context=None)` - Read the
  machine's `machine.json`.
- `machine_dir_path(machine_id, context=None)` - The machine's cache
  directory.
- `read_vm_state(machine_dir)` - The machine's recorded live-VM
  identity (`backend`, `backend-id`, `token`, `endpoint`), or `None`
  when it is not running.

Persistent machine-state changes — insert/eject are floppy and cdrom
slots and work running-or-stopped (a running change is applied live
over QMP); `set_boot_order` is stopped-only; all three persist and
survive stop/start:

- `insert_media(machine_id, slot, media=None, *, file=None,
  context=None)` (`insert-media`) - Exactly one of `media` (a
  declared media, fetched and hash-verified) or `file` (your own
  image, mounted in place: anonymous, mutable, unverified, never
  copied — the live-iteration transport).
- `eject_media(machine_id, slot, *, context=None)` (`eject-media`)
- `set_boot_order(machine_id, boot_keys, *, context=None)`
  (`set-boot-order`)

## Driving a machine from a program

The mechanics of the automating loop: put work in, run it, read the
result out, iterate. Reliquary supplies the transports and attaches
no meaning to what travels through them.

- `wait_machine_var(key, value=None, *, machine=None, blueprint=None,
  timeout=120, interval=1, context=None)` - Read a machine variable
  on a loop until it arrives, and return it. For the case a plain
  read cannot serve: **another actor sets it** — a run on another
  thread, or one being followed rather than driven. A blocking
  `run_script` leaves its variables final by the time it returns, so
  contract those with `expect=` instead of waiting on them. `value`
  omitted waits for any value, which is what the readiness idiom
  wants. Expiry raises `WaitExpired`, deliberately both a
  `RunFailure` (exit `4` at the CLI — the work did not happen) and a
  Python `TimeoutError` (nothing broke, ask again). CLI twin:
  `wait-machine-var`.
- `exec(command, *, machine=None, blueprint=None, timeout=120,
  check=False, context=None)` - Run one command in a running guest
  and return the
  text it produced, as a tuple of screen rows. The run family's
  one-shot member: it drives the machine and returns its output,
  storing nothing. Agentless capture, so the output is the visible
  screen — a command that scrolls further leaves only its tail;
  retrieve a file or read a machine variable when you need more.
  Completion means *this* command finished rather than that a prompt
  is visible, so output that cannot be tied to the command raises
  `RunFailure` (`screen.no-echo`) instead of returning rows that
  belong to something else. `check=True` opts into the outcome: a
  command that signalled failure raises `RunFailure`
  (`command.signalled-failure`) naming it, with the row return
  unchanged — the channel a setup command needs, whose output is
  nothing and whose success is everything. On DOS the verdict comes
  from an `IF ERRORLEVEL 1` probe Reliquary composes and reads back,
  so it costs one extra command at the prompt and sees only commands
  that *ran* and signalled failure; a mistyped one escapes it. CLI
  twin: `exec --check`.
  Non-DOS platforms raise `NotImplementedError`. CLI twin: `exec`.
  (The name shadows the Python builtin where it is imported by name,
  which is the price of the twin-name identity rule; `builtins.exec`
  remains reachable.)
- `get_machine_var(key, *, machine=None, blueprint=None,
  context=None)` - Read one machine variable, or `None` when it is
  not set. A query, valid in any phase. CLI twin: `get-machine-var`.
- `describe_drives(*, machine=None, blueprint=None, context=None)` -
  One report of the machine's drives and what they actually hold:
  per drive the declared and chosen facts; per hard disk the at-rest
  read (backing, the partition table as it declares itself, and per
  volume the filesystem, label and BPB geometry — `None` where
  unstated); and the platform's letter map over those facts, letter
  to `(drive key, volume index)`, with unplaced drives named as
  undetermined carrying the blocking disk's own reason. Never
  phase-refused, and it answers **from the record** in
  `machine.json`: every `start` reads the disks as its first step,
  so a running machine's answer is this boot's starting state
  (`"recorded": true`, each disk stamped `read-at`); the call
  itself reads a disk only when the machine is down and the disk
  has no record yet — the window between create and first start.
  Recognized: DOS platforms, FAT12/FAT16/FAT16B, and standard MBR
  primary/extended partitioning — everything else reports as a
  named `unread` refusal. CLI twin: `describe-drives`.
- `refresh_drives(*, machine=None, blueprint=None, context=None)` -
  Re-read a stopped machine's disks into the record and return the
  same report, fresh. The explicit way to pick up a layout changed
  behind the record — a guest session's repartitioning, an
  out-of-band edit — without waiting for the next start.
  Stopped-only: a running guest owns its disks. CLI twin:
  `refresh-drives`.
- `set_machine_var(machine_id, key, value, *, context=None)` - Record
  one. Its world-facing spelling is the script `set` verb, so the
  capability reaches the CLI through the scripting language rather
  than a command of its own. Variables are cleared at each `start`,
  so one always reports what the current boot produced; the `rlq` and
  `reliquary` key namespaces are reserved.
- `put_file(source, destination, *, machine=None, blueprint=None,
  context=None)` - Copy a host file into the guest, `destination`
  addressed **as the guest names it** (`"A:\TEST.EXE"`). Returns
  that address. CLI twin: `put-file`.
- `get_file(source, destination, *, machine=None, blueprint=None,
  context=None)` - The reverse: `source` is the guest address,
  `destination` a host path, and the host path is returned. CLI twin:
  `get-file`.
- `put_files(source, destination, *, machine=None, blueprint=None,
  context=None)` - Copy a host directory's **contents** into guest
  directory `destination` (`"A:\\"` is the drive root), recursively.
  Returns the guest addresses written, sorted. CLI twin: `put-files`.
- `get_files(source, destination, *, machine=None, blueprint=None,
  context=None)` - The reverse: the contents of guest directory
  `source` land in host directory `destination`, which is created if
  absent and is required — Reliquary invents no location to write to.
  Returns the host paths written, sorted. CLI twin: `get-files`.
- `list_files(address, *, recursive=False, machine=None,
  blueprint=None, context=None)` - What a guest directory holds: a
  flat list sorted by address, each entry
  `{"address", "name", "kind", "size"}` — `kind` is `"file"` or
  `"directory"`, `size` is `None` for a directory, and `address` is
  the full guest address, ready to hand back to `get_file`. One
  directory level unless `recursive=True`. CLI twin: `list-files`.

The drive-letter mapping is built from the machine's declared
platform and Reliquary's own drive assignment — never from
inspecting a guest — and places every drive: floppies at `A:`/`B:`
by slot, hard disks from `C:` in slot order, CD-ROMs after them.
Disk letters follow the volumes each disk **actually holds**, read
off the image on the host and re-read after every boot; a disk
holding none takes no letter, as on DOS itself.
All five are **stopped-only**: the backend snapshots a
directory-source drive at attach, so a put made while the machine
runs would be invisible and a guest write is not flushed until it
stops — and a drive image is only safe to work once nothing holds
it open. All five reach either kind of drive, mounting the image
and working its FAT volume where there is no host directory. The
image is opened where it lies rather than copied, locked for the
length of the access, and every write stands on a commit point the
backend holds until the last write returns — so a refusal partway
through leaves the image untouched. Anything the reader or the
backend cannot answer raises `PreflightError` naming it — a name
that is not 8.3, a partition type this build does not read, an
image another caller holds, a disk holding more than one volume.

The plural verbs move a tree's contents rather than nesting the
source inside the destination, which is the only shape a drive root
can take; they recurse, overwrite what is in the way, and delete
nothing.

## Blueprints (composed documents)

- `parse_document(value)` / `load_document(path)` - Parse and
  validate a `.rlqb` document: an array of specs, or a lone spec
  object as sugar for the array of one. Returns `Document`, whose
  `machines` and `media` are dicts by name. `type` defaults to
  `media`, so a machine declares `"type": "machine"`. Errors raise
  `BlueprintError` (a `StaticError`, so exit `2` and
  `except StaticError` are unchanged). `load_document` has a file to
  point into and gives each one a `line` and `column`, rendered with
  the source line and a caret; `parse_document` is handed a value
  that never had a position, so those are `None` and the diagnostic
  is its field breadcrumb alone.
- `load_namespace(context=None)` - Build the merged `(name, type)`
  catalog from every `.rlqb` in the active source;
  `resolve_machine`/`create` and media resolution read it.
  Canonically identical specs of one identity coexist across files;
  differing ones collide. (The catalog-level
  `resolve_media(name, namespace)` lives in `reliquary.resolve`.)
- `new_blueprint(name, *, platform="dos", context=None)` - Scaffold a
  home ``blueprints/<name>.rlqb``. CLI twin: `new-blueprint`.
- `add_media(name, path, *, context=None)` - Write a home
  ``blueprints\<name>.rlqb`` declaring a media located at `path` and
  pinned to its computed SHA-256. The file stays where it is; nothing
  is cached. Returns the blueprint path, and raises `FileExistsError`
  rather than overwriting one. CLI twin: `add-media`.
- `delete_blueprint(name, *, context=None)` - Remove the home blueprint
  file; fails closed while any machine of it exists. Never touches
  package builtins. CLI twin: `delete-blueprint`.
- Spec types live in `reliquary.document`: `Machine`, `Media`,
  `MachineDrive`, `Location`, `Reference`, and `Deferred` — the last
  carrying a value that still holds `${...}` references, finished at
  resolution rather than at parse.

## Media

- `fetch_media(name, context=None, on_mismatch="fail")` - Resolve a
  media by name against the catalog and return its verified payload
  path, fetching on demand — a verifying cached payload as-is, a
  verifying cached container re-extracted, then the mirror rungs in
  order. Every file is SHA-256-verified before use.
  `on_mismatch` is `"fail"` (default), `"prompt"` (interactive
  delete-and-refetch checkpoint), or `"refetch"` (pre-approved
  deletion); a mismatched file whose media names no source is
  always kept. CLI twin: `fetch-media`.
- `list_media(context=None)` - Sorted media names from the
  namespace — yours alone. CLI twin: `list-media`.
- `clean_media(name=None, *, context=None)` - Reclaim cached
  payloads, returning the names reclaimed. Blunt with no name,
  skipping anything a running machine holds; targeted with one. The
  cache holds only what can be fetched or derived again, so nothing
  is spared on provenance. CLI twin: `clean-media`.
- `prune_media(*, context=None, dry_run=False)` - Drop cached
  payloads outside the attachment closure, returning the names
  pruned (or, under `dry_run`, the names that would be). CLI twin:
  `prune-media`.

`add_media` is an authoring call and lives with the blueprint verbs
below, not here — it writes a declaration and never touches the cache.

## User properties

The `<home>/user.properties` file, edited surgically — comments,
blank lines, and ordering outside the named key are preserved.
Malformed files raise `PropertiesError` (a `ValueError`) naming the
path and line, and are never partly rewritten.

Every function takes `properties_file=` (CLI `--properties`), which
replaces the home's file rather than layering over it;
`RELIQUARY_PROPERTIES` selects the same way.

- `get_property(key, context=None, properties_file=None)` - The
  value, or `None`. A secret returns its marker `{"secret": True}`,
  never its value — exactly what `--json` serializes. CLI twin:
  `get-property`.
- `set_property(key, value, secret=False, context=None,
  properties_file=None)` - Create or replace a property, rewriting
  or appending only that key's line. With `secret=True` the value
  goes to the host credential store and only the marker to the
  file. Changing a property between ordinary and secret raises;
  unset it first. CLI twin: `set-property`.
  **One named divergence from the CLI:** this takes a secret's
  value as its ordinary `value` parameter. The CLI's prompt and
  stdin channels exist because argv reaches process listings and
  shell history, which an in-process value never touches — and a
  library function never prompts.
- `unset_property(key, context=None, properties_file=None)` - Remove
  a property; for a secret, its credential too. Also clears an
  orphaned credential. CLI twin: `unset-property`.
- `list_properties(prefix=None, context=None, properties_file=None)` -
  The properties projection, key to value-or-marker, sorted.
  `prefix` selects that key and its dotted descendants. CLI twin:
  `list-properties`.
- `has_credential(key, context=None, properties_file=None)` - Whether
  a secret's credential is actually present on this host. Kept
  separate from `get_property` so reading a property never depends
  on reaching the store; the CLI renders it as a stderr warning
  rather than folding it into the result.
- `is_secret(value)` / `secret_marker()` - Recognize and build the
  secret marker.

Secrets are stored in the host's credential service, scoped by the
absolute path of the properties file holding the marker and the
property name. There is no plaintext fallback: a host with no
usable store raises `CredentialError`. Updates are ordered
fail-safely (credential before marker, marker before credential),
so the only recoverable leftover is an orphaned credential, which
an ordinary `set_property` on that key refuses to overwrite.

## Scripts and runs

- `parse_script(source, path="<script>")` / `load_script(path)` -
  Parse a redesigned-surface `.rlqs` script into an immutable
  `Script`; errors raise `ScriptParseError` with source locations.
- `run_script(label, *, blueprint=None, machine=None, context=None,
  display=False, properties=None, properties_file=None,
  progress="auto", expect=None)` - Resolve the
  label through the blueprint's `scripts` map, create a machine when
  the blueprint has none, honor the script's `machine` header,
  statically preflight insert/eject/set-boot targets, bind every
  declared property before the machine starts, and run it.
  `properties` is the
  explicit `{key: value}` mapping (the CLI's repeated `--property`);
  `properties_file` selects the binding file; `progress` selects the
  live rendering (`"auto"` | `"pretty"` | `"plain"` | `"jsonl"`, as
  the CLI's `--progress`), and `"plain"`/`"jsonl"` never prompt.

  **The run returns its output and stores nothing.** The returned
  `ScriptRun` carries `machine_id`, `script_path`, `created_machine`,
  `final_phase`, `machine_phase`, and `events` — the whole event
  stream as plain dicts, in order, the terminal event last. Keep it
  if you want a record; Reliquary keeps none. Failures raise by error
  class (below). CLI twin: `run-script`.

  `expect={"ready": "yes"}` (CLI: repeated `--expect ready=yes`)
  **contracts the run on the machine variables it leaves.** Each key
  is read once the run completes, and one that is unset or holds
  something else raises `RunFailure` naming key, wanted and got —
  which turns a script that never reached its `set` from silence into
  a failure. It is a postcondition and not a wait: this call blocks,
  so the values are final when it returns. When the setter is
  somebody else, that is `wait_machine_var`.
- `run_script(label, dry_run=True, ...)` returns a `DryRun` instead
  of a `ScriptRun`: it parses and statically checks the script and
  reports the timing plan, each declared property's supplying source,
  and how many statements no static pass can promise will run —
  without prompting, starting a machine, running a guest step or
  reading a secret's value. **The selector is optional in this mode
  alone**, its presence choosing which of the two checkable tiers
  applies. `display=`, a non-default `progress=` and `expect=` are
  refused with it — a plan has no window, no stream, and no run whose
  outcome could be contracted. Normative:
  [cli.md](spec/cli.md#the-dry-run).
- `execute_script(script, *, machine_id, context=None,
  display=False, script_path=None, bindings=None, events=None)` -
  Execute an already-parsed script against a specific machine.
  `bindings` is a `BoundProperties` (from `bind_properties`); without
  it, a `${key}` reference fails at runtime. `events` is the
  `EventStream` the run emits into.
- `bind_properties(script, *, parameters=None, explicit=None,
  properties_file=None, context=None, asker=None)` - Resolve every
  declared property through the source order, or raise
  `PropertyBindingError`. `describe_sources(...)` is its dry twin,
  naming each key's source without binding it (what a dry run
  reports).

`create_machine`, `recreate_machine`, and `apply_blueprint` accept
`properties=` and `properties_file=`: any `${key}` a media
`location` (or `sha256`) references binds through the same source
order before materialization, and the resolved location is recorded
in the machine state (`start` never re-resolves it). A bound value
that is itself a reference is refused. See the blueprint guide for
the `location` grammar.

## Guest interaction

`Machine(home=None, deadline=None)` is the backend-neutral
interaction handle for a running, Reliquary-owned machine. `home`
is the machine's own materialization directory — a plain
already-resolved path, not a `Context` — and it is the whole
address: the recorded VM identity lives there, and the adapter it
names supplies the endpoint and verifies it before anything is
sent. There is no port to pass.

- `Machine.session()` - Context manager yielding the
  identity-verified backend session (the adapter's carriers).
- `Machine.console()` - Context manager yielding the agentless
  display console over one such session.
- `Machine.qmp()` - Context manager yielding the identity-verified
  QMP session (its `cmd()` and `hmp()` remain available). The named
  native escape hatch, and QEMU's alone: a machine on another
  backend refuses it rather than approximating a monitor it has not
  got.
- `Machine.screen_text()` /
  `Machine.wait_text(pattern, timeout=60)` - Read or wait on the
  guest text screen.
- `Machine.send_keys(combos, delay=0.06)` /
  `Machine.send_text(text, enter=True)` - Keyboard input.
- `Machine.cursor_menu_select(item, timeout=30, exclude=())` -
  Feedback-driven cursor-menu selection.
- `Machine.screenshot(name="screen", directory=None)` - Capture the
  guest framebuffer as a PNG, and return its path.

Module-level equivalents take `home=` directly: `send_keys`,
`send_text`, `screen_text`, `wait_text`, `cursor_menu_select`, and
`screenshot(name="screen", home=None, directory=None)`.

`GuestExec` is the capability protocol —
`wait_ready(timeout=90)`, `execute(command, timeout=120, *,
check=False)` — and
`AgentlessGuestExec` is the concrete agentless DOS adapter over a
`Machine`. How a platform answers `check` is its own business: DOS
probes ERRORLEVEL, an agent would read an exit status, and what
every adapter owes is the same answer.

## Backends

The adapter API is an **internal engineering contract**, not one of
the application surfaces: no adapter operation is a CLI command
or an API twin, and consumers reach backends through blueprint
vocabulary (`backend`, `backend-settings`, `control-planes`,
`devices`, drives and controllers) and through the capability
failures preflight reports. What the package root exposes is the seam's vocabulary,
for reading rather than driving:

- `adapter(name)` / `discover()` - The adapter for a backend name,
  and an availability probe of every backend in priority order.
  Discovery establishes availability only: it never selects a
  backend and never changes a machine's recorded one.
- `BACKEND_PRIORITY` - The default assignment order (QEMU,
  VirtualBox, VMware Workstation, Hyper-V), which breaks ties among
  backends already available *and* capable.
- `Availability` / `Capabilities` / `BackendAdapter` - The probe
  result, the named-vocabulary capability report, and the contract
  itself.

QEMU's own helpers (`find_qemu`, `create_hdd_image`, `Qmp`, the
drive rendering) are adapter internals in `reliquary.backend_qemu`
and are not part of the embedding surface.

`main(argv=None)` is the CLI entry point.

For the command-line equivalents of everything above, see the
[CLI reference](cli-reference.md).
