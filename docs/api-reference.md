<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Python API reference

This is the reference for reliquary's implemented Python surface —
the first binding of the embedding API. Everything below is
importable from the `reliquary` package and mirrors the CLI: the
two are one semantic surface. The end-goal API design, including
the surface still ahead of implementation and the settled naming
it realigns to, is in
[planning/design/api.md](../planning/design/api.md).

reliquary attaches no meaning to guest output; interpreting
results belongs to the caller.

## Home, cache, and Context

- `set_home(path)` - Set the process-global reliquary home
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
- `assets=` selects where authored assets (blueprints and their
  media/source/archive components, plus scripts) resolve from: a
  directory path is a
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
  `media_dir`, `scripts_dir`, `cache_dir`, `archives_cache_dir`,
  `media_cache_dir`, and `machines_cache_dir`.

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

- `parse_document(value, *, stem=None)` /
  `load_document(path)` - Parse and validate a composed `.rlqb`
  document (a bare-root machine, or the `machines` / `media` /
  `sources` / `archives` sections); return `Document`, whose
  `machines` / `media` / `sources` / `archives` are dicts by name.
- `load_namespace(context=None)` - Build the merged `(name, type)`
  resolution namespace from every `.rlqb` in the active source;
  `resolve_machine`/`create` and media resolution read it. (The
  namespace-level `resolve_media(name, namespace)` lives in
  `reliquary.resolve`.)
- `new_blueprint(name, *, platform="dos", context=None)` - Scaffold a
  home ``blueprints/<name>.rlqb`` (a bare-root machine). CLI twin:
  `new-blueprint`.
- `delete_blueprint(name, *, context=None)` - Remove the home blueprint
  file; fails closed while any machine of it exists. Never touches
  package builtins. CLI twin: `delete-blueprint`.
- Component types live in `reliquary.document`: `Media`, `Source`,
  `Archive`, `Locator`, `Machine`.

## Media

- `fetch_media(name, context=None, on_mismatch="fail")` - Resolve a
  media by name against the namespace and return its verified
  payload path, fetching on demand — cheapest source first: a
  verifying payload as-is, a verifying cached archive re-extracted,
  then the mirror URLs. Every file is SHA-256-verified before use.
  `on_mismatch` is `"fail"` (default), `"prompt"` (interactive
  delete-and-refetch checkpoint), or `"refetch"` (pre-approved
  deletion); a mismatched file whose media names no source is
  always kept. CLI twin: `fetch-media`.
- `list_media(context=None, *, builtin=False)` - Sorted media names
  from the namespace, or the package codex when ``builtin=True``.
  CLI twin: `list-media`.
- `delete_media(name, *, context=None)` - Media now lives inside a
  `.rlqb`; deleting a shared component is not a file operation, so
  this raises `NotImplementedError` pointing at editing the
  blueprint. CLI twin: `delete-media`.
- `clean_archives(context=None)` / `clean_media(context=None)` -
  Reclaim the cached source archives (`cache/archives/`) and cached
  payloads (`cache/media/`). CLI twins: `clean-archives`,
  `clean-media`.

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
reliquary-owned VM. Every operation verifies VM identity before
sending anything. `Machine.home` is a plain already-resolved
directory, not a `Context` — typically a specific machine's own
cache subdirectory, not the reliquary home itself.

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
