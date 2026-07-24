<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Python API reference

This is the reference for Reliquary's implemented Python surface —
the first binding of the embedding API. Everything below is
importable from the `reliquary` package and mirrors the CLI: the
two are one semantic surface. The end-goal API design, including
the surface still ahead of implementation and the settled naming
it realigns to, is in
[planning/design/api.md](../planning/design/api.md).

Reliquary attaches no meaning to guest output; interpreting
results belongs to the caller.

## Home, cache, and Context

- `set_home(path)` - Set the process-global Reliquary home
  (overrides `RELIQUARY_HOME`).
- `set_cache(path)` - Set the process-global cache root (overrides
  `RELIQUARY_CACHE_DIR`); defaults to `<home>/cache`.
- `home()` - Return the effective home (`RELIQUARY_HOME`,
  `set_home()`, or the platform default under Documents).
- `documents_dir()` - Resolve the user's platform Documents
  folder, or `None` when it cannot be determined.
- `Context(home=None, cache=None, assets=None)` - An explicit
  (home, cache, asset-source) triple scoping one call or a group of
  calls, independent of the process-global default. Every function
  below that resolves a path under the home accepts a `context=`
  parameter: omit it (the common case) to use the process-global
  default; pass a bare string as shorthand for
  `Context(home=that_string)` (cache still follows the global
  default, and it selects home mode); pass a `Context` instance to
  pin home, cache, and asset source explicitly, safe to vary per
  call within one process. The CLI only ever drives the
  process-global default via `--home`/`--cache`/`--assets` — scoped
  `Context` objects are an embedding-API-only capability.
- `assets=` selects where authored assets (blueprints, media
  included, plus scripts) resolve from: a directory path is a
  hermetic project root walked recursively by extension (the sole
  source — no home, no codex, no seeding), and `HOME_ASSETS` is
  home mode (the home's canonical folders plus codex seeding). The
  embedding API has **no default source**: a call that resolves an
  asset by name with none configured (no `assets=` and no
  `set_assets`) raises, so automation never silently reads home
  assets or the current directory. `set_assets(HOME_ASSETS)` /
  `set_assets(dir)` set the process-global; the CLI sets it from
  `--assets` (home mode when absent).
- Path helpers, each accepting `context=None`: `blueprints_dir`,
  `scripts_dir`, `cache_dir`, `media_cache_dir`, and
  `machines_cache_dir`.

All state lives under the home, except the regenerable cache,
which lives under the (independently resolvable) cache root.

## Cached machines (the blueprint lifecycle)

- `create_machine(name, *, context=None)` - Materialize a new machine
  from a blueprint name; returns the machine id
  (`<blueprint>-<n>`, lowest free number). Seeds codex content on
  first reference. CLI twin: `create-machine`.
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
  Start a machine; the QMP port and VM identity are recorded in
  the machine's `machine.json` as a `vm` section, written
  atomically with `phase`. CLI twin: `start-machine`.
- `stop_machine(machine_id, context=None)` - Stop a running machine;
  identity mismatches fail closed. CLI twin: `stop-machine`.
- `destroy_machine(machine_id, context=None)` - Delete the machine
  entirely; frees its number for reuse. CLI twin:
  `destroy-machine`.
- `recreate_machine(*, machine=None, blueprint=None, context=None)` -
  Destroy the selected machine and recreate it under the same id,
  re-resolving the current blueprint. Returns the reused id. CLI
  twin: `recreate-machine`.
- `apply_blueprint(*, machine=None, blueprint=None, context=None)` -
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
- `machine_drive_args(machine_id, context=None)` - Render QEMU
  `-drive` arguments from the machine's state.

Persistent machine-state changes — insert/eject are floppy and cdrom
slots and work running-or-stopped (a running change is applied live
over QMP); `set_boot_order` is stopped-only; all three persist and
survive stop/start:

- `insert_media(machine_id, slot, media_name, *, context=None)`
  (`insert-media`)
- `eject_media(machine_id, slot, *, context=None)` (`eject-media`)
- `set_boot_order(machine_id, boot_keys, *, context=None)`
  (`set-boot-order`)

## Blueprints (composed documents)

- `parse_document(value)` / `load_document(path)` - Parse and
  validate a `.rlqb` document: an array of specs, or a lone spec
  object as sugar for the array of one. Returns `Document`, whose
  `machines` and `media` are dicts by name. `type` defaults to
  `media`, so a machine declares `"type": "machine"`.
- `load_namespace(context=None)` - Build the merged `(name, type)`
  catalog from every `.rlqb` in the active source;
  `resolve_machine`/`create` and media resolution read it.
  Canonically identical specs of one identity coexist across files;
  differing ones collide. (The catalog-level
  `resolve_media(name, namespace)` lives in `reliquary.resolve`.)
- `new_blueprint(name, *, platform="dos", context=None)` - Scaffold a
  home ``blueprints/<name>.rlqb``. CLI twin: `new-blueprint`.
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
- `list_media(context=None, *, builtin=False)` - Sorted media names
  from the namespace, or the package codex when ``builtin=True``.
  CLI twin: `list-media`.
- `clean_media(name=None, *, context=None)` - Reclaim cached
  payloads, returning the names reclaimed. Blunt with no name,
  sparing `supplied` payloads and anything a running machine holds;
  targeted with one. CLI twin: `clean-media`.
- `prune_media(*, context=None, dry_run=False)` - Drop cached
  payloads outside the attachment closure, returning the names
  pruned (or, under `dry_run`, the names that would be). CLI twin:
  `prune-media`.
- `add_media(name, path, *, context=None)` - Supply a payload nothing
  can locate, verified against the media's pin and recorded as
  `supplied`. Returns the cached path. CLI twin: `add-media`.

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
  secret marker. `check_key(key)` validates a property key.

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
  display=False)` - Resolve the label through the blueprint's
  `scripts` map, create a machine when the blueprint has none,
  honor the script's `machine` header, statically preflight
  insert/eject/set-boot targets, and execute with a run record under
  the machine's `runs/` directory. Returns `ScriptRun`; failures
  raise `ScriptRuntimeError`. CLI twin: `run-script`.
- `check_script(name, *, blueprint=None, machine=None, context=None)` -
  Parse and statically check a script; return a printable timing
  plan without running it. CLI twin: `check-script`.
- `execute_script(script, *, machine_id, context=None,
  display=False, run_dir=None, script_path=None)` - Execute an
  already-parsed script against a specific machine.

## Guest interaction

`Machine(port=None, home=None, deadline=None)` is the
platform-neutral interaction handle for a running,
Reliquary-owned VM. Every operation verifies VM identity before
sending anything. `Machine.home` is a plain already-resolved
directory, not a `Context` — typically a specific machine's own
cache subdirectory, not the Reliquary home itself.

- `Machine.qmp()` - Context manager yielding the
  identity-verified QMP session (its `cmd()` and `hmp()` remain
  available).
- `Machine.screen_text()` /
  `Machine.wait_text(pattern, timeout=60)` - Read or wait on the
  80x25 VGA text screen.
- `Machine.send_keys(combos, delay=0.06)` /
  `Machine.send_text(text, enter=True)` - Keyboard input.
- `Machine.cursor_menu_select(item, timeout=30, exclude=())` -
  Feedback-driven cursor-menu selection.
- `Machine.screenshot(name="screen")` - PNG screendump.

Module-level equivalents take `port=` / `home=` directly:
`send_keys`, `send_text`, `screen_text`, `wait_text`,
`cursor_menu_select`, and `screenshot(name="screen", port=None,
home=None, directory=None)`.

`GuestExec` is the capability protocol —
`wait_ready(timeout=90)`, `execute(command, timeout=120)` — and
`AgentlessGuestExec` is the concrete agentless DOS adapter over a
`Machine`.

## QEMU helpers

- `find_qemu()` / `find_qemu_img()` - Locate the binaries
  (`RELIQUARY_QEMU_HOME` / `QEMU_HOME`, then PATH, then
  well-known install locations).
- `create_hdd_image(filename, capacity)` - Create a sparse qcow2
  v3 image; capacity is a qemu-img size string (`"2G"`) or a
  positive integer MiB value.
- `Qmp(port)` - Synchronous facade over the official `qemu.qmp`
  client.

`main(argv=None)` is the CLI entry point.

For the command-line equivalents of everything above, see the
[CLI reference](cli-reference.md).
