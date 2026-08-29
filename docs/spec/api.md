<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# The embedding API

> **Status:** this document describes the end-goal design for
> Reliquary's embedding API — the second primary application
> surface, S2 (planning/SURFACES.md). The implemented Python
> binding is documented in
> [docs/api-reference.md](../../docs/api-reference.md); this page
> lays out the settled API design and conventions, and points to
> each family's normative contract. Engineering invariants for the
> current binding are in AGENTS.md, "The runner surface".
>
> **What this document specifies, and what it only points to**
> (D119). Under P6's rule that the CLI and the API are one
> semantic surface, three documents share the normative claims:
> the command manifest lists the **inventory** (what commands
> exist), [cli.md](cli.md) specifies **command behaviour** (flags,
> output, exit codes), and this document specifies the
> **conventions** below — the identity rule, selectors, returns,
> error classes — plus each twin's **return contract**. A family's
> *semantics* live wherever its row below names as the contract
> home, and the row only points there. If a row's description here
> ever disagrees with that document, the contract home is correct
> and the row here is the bug.

## Principles

- **One semantic surface with the CLI.** Every command maps
  one-to-one onto a public API call with the same behaviour;
  nothing is CLI-only unless this spec says so, and every public
  capability is also reachable from the CLI. A change to one
  lands on both in the same change, never deferred
  (planning/SURFACES.md; AGENTS.md "CLI–API parity").
- **Python is the first binding, not the only one.** The API is
  meant to gain native bindings in other languages too, so it
  avoids any shape a common binding language (C, Java) cannot
  express cleanly: flat functions, plain values, pull-only
  handles, no callbacks.
- **Computation belongs to the caller** (language goal G2).
  Reliquary attaches no meaning to guest output; interpreting
  results and any test-framework semantics are the consuming
  project's job, not Reliquary's. Consumers inside this repo (the
  media layer, the script runtime) call the same internal engine
  functions the session's methods call — nothing lower-level than
  that is exposed.
- **A deliberate split between the two presentations.** The
  blocking API calls return typed results and raise by error
  class; the CLI writes streams, `--json` documents, and exit
  codes. Both do the same work; only how they present it differs,
  and that difference is a decision, not something that crept in
  (planning/proposed/FEATURES.md "Asynchronous runs").
- **No backward compatibility before 1.0.** When the implemented
  binding is realigned to the settled names below, there will be
  no aliases or compatibility shims for the old names.

## Conventions

- **`Session` is the only entry point for ambient state** (P26):
  every method that touches the working directories, machine
  state, or media state is a method of the one exported `Session`
  class, which must be opened on at least a home directory.
  `Session(context)` accepts either a bare home-directory string
  or a `Context` object, and refuses to construct without a home
  — this is the `dir.unassigned` error, raised here instead of on
  first use, and it is safe to raise it this early because once a
  home is assigned, all six working directories can be derived
  from it. Each `Session` pins its own `Context` at construction
  and reads only that record, so having two `Session` objects
  alive in one process is unremarkable. A few things stay
  importable independently of `Session`: the type definitions,
  the error classes, `Context`, `default_home_dir()`, and the
  standalone parsing functions — these stay free functions rather
  than session methods because parsing and validating a document
  you were handed does not need a working directory, and tooling
  should never have to invent a home just to parse a string. The
  guest-console family stays at module level rather than becoming
  `Session` methods (see its row below); `Machine.session()` — a
  live connection to a running machine — is a different thing
  entirely and keeps its own name.
- **Naming: the CLI command name is the API method name** (owner,
  2026-07-21): a `Session` method is named as a verb-noun pair —
  `create_machine`, `fetch_media`, `run_script` — and its matching
  CLI command is the same name with dashes instead of underscores
  (`create-machine` ↔ `create_machine`), with the command's flags
  mirroring the method's parameters. Because the command name is
  mechanically derived from the method name, the two can never
  drift apart. There are three named exceptions, each for its own
  reason: the guest-console family is named after the script
  language's own verbs instead (its API methods are deferred to
  the control-plane design); the `run` family is named after the
  run handle's methods instead; and the **codex family has no API
  method at all** — `seed-blueprint`, `seed-script`, and
  `list-codex` are CLI-only, under P6's named exception, because a
  library whose contents can change in any point release is not
  something a program should be able to call directly (D87).
  These three exceptions apply only to command *names* — flags
  still mirror the underlying function's or method's parameters in
  every case, exceptions included (`run cancel --stop-machine`
  maps to `cancel(stop_machine=)`).
- **Selectors** (owner, 2026-07-21): a function that acts on one
  machine takes either `machine=` (the machine's full id, exactly,
  e.g. `"<blueprint>-<n>"`) or `blueprint=` (a blueprint name,
  which selects that blueprint's one machine). `resolve_machine()`
  is the shared function both the CLI and the API route through to
  turn either selector into a machine id; it is not part of the
  naming pairing above (owner, 2026-07-21) — it has no matching
  CLI command, because selecting a machine is something every
  machine-scoped call does, not a separate operation, and the way
  to list what a selector would match is `list_machines(blueprint=)`.
  Each parameter accepts exactly one kind of value: there is no
  partial-id matching and no bare number by itself (the id already
  combines the blueprint name and the number), so the selectors
  work the same way in any binding language.
- **The `Context` record is what a session is opened on**: a
  `Context` has six directory slots — `home_dir=`,
  `blueprints_dir=`, `scripts_dir=`, `cache_dir=`, `media_dir=`,
  `machines_dir=` — one for each of the six `--*-dir` CLI flags —
  plus the selected properties file (`properties_file=`, matching
  the CLI's `--properties`). That is all of the ambient state, and
  nothing else. A `Context` is a plain record of paths that may be
  unset, not a configured object, so it can be represented as
  plain strings when called from C or Java. The embedding API
  **sets none of these fields itself**: a session refuses to
  construct without an explicit home, and nothing on either
  surface is ever silently resolved from the shipped codex library
  — so calling the API never picks up the developer's own home
  directory, the current working directory, or content from the
  library by accident. The CLI's defaults belong to the CLI, not
  the library: for each invocation the CLI builds one `Context`
  from its flags, then the environment variables (a step private
  to the CLI's own construction of the record — the library itself
  never reads environment variables), then the default home
  directory
  ([asset-resolution.md](asset-resolution.md#the-working-directories)).
- **A method's return value is what the matching CLI command
  prints**: `create_machine` and `clone_machine` return the new
  machine's id; `import_vm` returns the blueprint it wrote. Under
  the CLI's global `--json` flag this match is exact (settled
  2026-07-21): the command prints the method's return value
  serialized as one JSON document, so each method's return
  contract is also that command's `--json` output contract
  (docs/spec/cli.md). A return value is always a plain JSON-shaped
  value (owner, 2026-07-21): where a return can take more than one
  shape, each shape is still ordinary JSON — for example
  `get_property` returns a plain string for an ordinary value, or
  a marker value for a secret, exactly as `--json` would serialize
  it — but a return is never sometimes a plain value and sometimes
  a handle object; a handle is not a value, which is why the
  blocking methods were not given a `detach=` flag that could
  return either kind. From 1.0, return shapes may only grow
  (owner, 2026-07-22; this guarantee starts at 1.0 rather than at
  beta, per D25): new fields may be added, an existing field never
  changes type or meaning, and removing or renaming a field is a
  breaking change — callers should tolerate fields they don't
  recognize. Before 1.0, return shapes may still change along with
  the rest of the specs (the CLI stability contract,
  docs/spec/cli.md).
- **Errors: one named class hierarchy** (owner, 2026-07-21): the
  blocking methods raise by error class, and every class shares
  one root. In Python the root is `ReliquaryError` — every
  deliberate Reliquary error subclasses it, on every surface, so
  `except ReliquaryError` always catches them all. The run
  surface's four classes are `StaticError` (exit code 2),
  `PreflightError` (exit code 3), `RunFailure` (exit code 4), and
  `RunCancelled` (exit code 5; this subclasses the root directly,
  never `RunFailure` — a cancellation is neither a success nor a
  failure, it's its own outcome): these four exit codes and
  exception classes are one and the same mapping, on every surface
  (script spec, "Error classes and exit codes"). **These four
  classes are not specific to running scripts** (D58, 2026-07-27):
  they apply unchanged everywhere, because what decides which one
  applies — whether the authored input itself is malformed,
  whether the world doesn't satisfy that input, or whether the
  work itself fails while running — has nothing to do with
  scripts specifically. A malformed blueprint raises
  `StaticError`; naming a machine that doesn't exist raises
  `PreflightError`; so does asking for a capability this build
  declares but hasn't implemented. New error subclasses may be
  added later, but never as a breaking change.
  Exit code `1` means the fault is Reliquary's own, never the
  caller's — it covers exactly the errors outside those four, and
  it has two sources: a deliberate `InternalError`, raised when
  Reliquary detects a broken invariant in its own state, and a
  genuine bug that was never wrapped as a `ReliquaryError` at all.
  Every deliberate error Reliquary raises lands in the
  `ReliquaryError` hierarchy, which is what keeps
  `except ReliquaryError` a true catch-all as promised above.
  Other language bindings spell out the same classes natively.

  **A wait that times out is the one class with two parent
  classes** (D90): `WaitExpired` subclasses both `RunFailure` and
  the host language's own timeout type — in Python, `TimeoutError`
  — because two things are true about it at once. The work that
  was asked for did not happen, so its exit code is `4`; but
  nothing about the machine went wrong, and the thing being waited
  for may still arrive later, so a caller that's holding a retry
  loop can catch it with its ordinary timeout handler and simply
  ask again. This is how the rule "waiting that times out is not a
  failure — retry it" (from the async design) is honored without
  using a bare built-in exception that would fall outside the
  `ReliquaryError` hierarchy, which the rule above forbids. A
  binding without multiple inheritance for exceptions spells this
  out instead as its own timeout error type that carries exit code
  `4`.
- **Async starters: a blocking call is "start" plus "attach"
  combined** (owner, 2026-07-21; backlogged 2026-07-24, D35/D36 —
  there is no use case for it yet, drafted as U19; milestone 9
  ships only the blocking methods, which *return* their output and
  store nothing — D36 — so the record-management commands are
  backlogged too): a long-running operation is modeled as one
  start-plus-attach pair, presented two ways
  (planning/proposed/FEATURES.md "Asynchronous runs"). The CLI
  combines them: every foreground command starts the operation and
  then attaches to watch it, and `--detach` starts it without
  attaching. The API keeps them separate: the blocking method
  (`run_script()`, `fetch_media()`) is the combined form, and the
  starter method (`start_script()`, `start_fetch()`) returns a
  handle that a separate attach call can then follow. A starter
  method therefore has no CLI command of its own — it *is* what
  `--detach` does on the combined command
  (`run-script --detach` ↔ `start_script()`), and the naming rule
  above binds the pair of capabilities together, not each function
  on its own. `start_fetch` has no CLI form at all: a fetch handle
  only exists inside the process that created it, so for the CLI,
  the running `fetch-media` process itself acts as the handle —
  put it in the background and read `--progress jsonl` to watch
  it; reconnecting to it later is what run records are for.
- **Handles only support pulling status, never callbacks**:
  `status()`, `events(follow=)` as a blocking iterator,
  `wait(timeout=)`, and `cancel()`. `wait()` finishes exactly like
  the blocking method it corresponds to — same result, same
  exceptions — except that a timeout raises outside the
  `ReliquaryError` hierarchy (in Python, the built-in
  `TimeoutError`), because nothing failed: the operation is still
  running, the handle is still valid, and the caller can simply
  call `wait()` again (owner, 2026-07-21). This is deliberately
  outside what `except ReliquaryError` catches, because a timeout
  here is not a Reliquary error. A handle only watches an
  operation, it never owns it: dropping a handle never affects the
  operation it was watching — `cancel()` is the only way to cancel
  it.

## The surface

Each family's normative contract lives in its own spec document;
this table just indexes them. **This table does not tell you
what ships today**: the command manifest
(`src/reliquary/schemas/command-manifest.toml`) is the normative
list of what's actually shipped, and a test enforces that on
every commit (`tests/test_command_manifest.py`). That separation
is what lets this table describe the end-goal design freely —
where it names a capability that doesn't exist yet, the manifest
is what tells you so.

Under the naming rule above, the CLI column is just the API
column with dashes instead of underscores; the table below calls
out the exceptions and each family's contract home. Every method
listed below is a method of the one `Session` class (P26) — the
`context=` / `properties_file=` parameters that older signatures
threaded through every call are now carried once, in the record
the session was opened on, so they don't appear in any signature
below.

| CLI | API method | contract home |
|---|---|---|
| `create-machine` / `start-machine` / `stop-machine` / `apply-blueprint` / `destroy-machine` / `recreate-machine` / `clone-machine` / `delete-blueprint` | the same names with underscores; `create_machine(name, *, dry_run=False, backend=None)` returns `str \| DryRun` — this is a distinct type so a dry-run result can never be mistaken for a real one — and `backend=` (only legal when `dry_run` is set) asks what a *named* backend would do | [instance model](instance-model.md), [cli.md](cli.md#the-dry-run) |
| `export-drive` / `export-machine` | `export_drive(key, destination)` / `export_machine(to=, destination=None)` — both return a stream; `to=` names an exporter (this is its own vocabulary, separate from the backend list) and is required | [instance model](instance-model.md) (design: proposed/FEATURES.md "Machine mobility") |
| `import-vm` | `import_vm(source, name, platform, hdd_images, snapshot)` | [instance model](instance-model.md) (design: proposed/FEATURES.md "Machine mobility") |
| `new-blueprint` | `new_blueprint()` | [blueprint model](blueprint-model.md), [cli.md](cli.md#scaffolding-a-blueprint) |
| codex family (`seed-blueprint`, `seed-script`, `list-codex`) | **no API method — CLI-only** (D87). `seed-blueprint <name> [--only]` copies a library blueprint, and the scripts it names, into your `blueprints`/`scripts` directories; `seed-script <stem> [--only]` copies one script; `list-codex` lists what the library holds (`--json` adds each entry's description). Reaching the shipped library is something only a person does at the command line: no program may depend on a name the library could rename or drop in the next point release (P18) | [codex](codex.md) |
| `list-backends` | **no API method — CLI-only.** It reports the backends discovered on this host and where each is installed; the adapters themselves stay an internal implementation detail. `--json` gives non-Python callers the same report without exposing that internal layer as a public API | [cli.md](cli.md#discovering-backends) |
| `run-script <label>` | `run_script()` returns the run's output and raises by error class (D36 — nothing is stored; the `exec` method lands alongside it); `run_script(label, *, dry_run=False)` returns `ScriptRun \| DryRun`, and under `dry_run` the label is optional, because whether you pass one decides which level of checking runs. `expect={key: value}` (`--expect key=value`, repeatable) checks the run's final machine variables against the values you name — this is a check made after the run, not something waited for, because a blocking run's variables are already final by the time it returns — and is refused under `dry_run`, since a dry run does not actually run anything. `record=<path>` (`--record <path>`) writes a screen transcript for debugging and for building a corpus; recording stops for the rest of the run as soon as a bound secret reaches the guest, and this flag too is refused under `dry_run`, since a dry run never reads the screen. The `.rlqt` transcript file format itself is deliberately not a stable contract; only the command-line flag that produces it is (D98) | [script spec](script-spec.md), [cli.md](cli.md#the-dry-run), [cli.md](cli.md#recording-a-screen-transcript) |
| the `run` family; `begin-run` / `end-run`; `list-runs` — all backlogged (D35/D36) | persisted run records, `run status` / `run delete`, the async followers `run tail` / `run wait` / `run cancel`, the run handle (`start_script()` / `attach_run()` / `delete_run()`), and interaction runs (`begin_run` / `end_run`) are all backlogged async-run work; milestone 9 stores nothing | script spec |
| `fetch-media` | `fetch_media()` blocking; `start_fetch()` → fetch handle (backlogged — D35) | [media spec](media-spec.md#fetch-progress) |
| `clean-media` / `prune-media` / `add-media` | `clean_media(name=None)` / `prune_media(dry_run=)` / `add_media(name, path)` | media spec |
| `insert-media` / `eject-media` / `set-boot-order` | `insert_media(slot, media=None, file=None)` (`--file` mounts an anonymous `local`+`use` image, U20) / `eject_media()` / `set_boot_order()` | [blueprint model](blueprint-model.md), [media spec](media-spec.md), [script spec](script-spec.md) |
| `get-machine-dir` | `get_machine_dir()` — returns the machine's cache directory as an absolute path; this is the entry point for out-of-band file access | [instance model](instance-model.md) |
| `get-machine-var` | `get_machine_var(key)` — reads a machine variable that a script set (a `machine.json` field that is cleared when the machine starts; the channel a script uses to hand a value back to the host, U14/U20) | script spec |
| `wait-machine-var` | `wait_machine_var(key, value=None, *, timeout=120, interval=1)` — polls the same value in a loop, for a variable **something else** sets (a run on another thread, or a run you're following): a blocking `run_script` call's variables are already final when it returns, so check those with its `expect=` parameter instead. `value=None` waits for the variable to have any value at all. Timing out raises `WaitExpired`, which is both a `RunFailure` (exit code `4`) and a Python `TimeoutError`, so a caller in a retry loop can just call it again | [cli.md](cli.md) |
| `wait-ready` | `wait_ready(*, timeout=90, prompt=None)` — waits for the boot to reach the platform's own evidence of readiness (on DOS, a prompt on the bottom row: either the standard prompt shape, or exactly the text named by `prompt` for a customized guest, D113); this is `exec`'s precondition, exposed as a method in its own right (D114). Returns nothing; a timeout raises `WaitExpired`, exactly like `wait_machine_var` does. `AgentlessGuestExec.wait_ready`, at the handle layer, is the same capability reached without going through a session | [cli.md](cli.md#reaching-the-prompt) |
| `list-machines` / `list-blueprints` / `list-scripts` / `list-media` | `list_<noun>` — **one function per kind of thing, named after what it lists**: each lists only your own, never a codex library entry (`list-codex`, above, is the library's own listing). There is no separate `search-<noun>` function: filtering a list by a search term is something the shell already does, and `--json` makes it just as easy to do from any language (D88) | shared behaviour: [cli.md](cli.md); each kind's return value: that kind's own spec, as they are written |
| `get-property` / `set-property` / `unset-property` / `list-properties` | `get_property()` / `set_property()` / `unset_property()` / `list_properties()` | [script properties](script-properties.md) |
| guest-console family (`type` / `enter` / `press` / `select` / `wait` / `screen` / `screenshot` / `hmp`) | today's `Machine` class and its module-level functions; API methods land with the control-plane design — this is the script-language-naming exception (CLI spellings settled 2026-07-21). `exec` is no longer deferred: its `Session` method shipped alongside the exec-run work (D36), so it now follows the naming rule like any other method | [script spec](script-spec.md) (verbs); the control-plane design (methods) |

`import-vm`'s API method is `import_vm`, not `import` — a bare
`import` is a reserved word in Python — and under the naming rule
the CLI simply reuses that same name, giving `import-vm`. Export
used to have no method name decided for it; that gap is now
closed (owner, 2026-07-22):
`export_drive` / `export_machine`, above, with `--to` naming an
exporter from its own vocabulary, deliberately kept separate from
the backend list.

## Handles

> Both handles below are **backlogged work** (D35): the
> asynchronous-run feature area was dropped from the numbered
> plan for lack of a use case (drafted as U19). Milestone 9
> delivers only the blocking methods (`run_script()`,
> `fetch_media()`) and the record-management commands; the
> pull-only handles and `attach_run()` will return once U19 is
> scheduled. The design below is still the plan.

**The run handle** (returned by `start_script()`; reopened later
by `attach_run()`): watches a run's live `run-events.jsonl` file
by pulling status, never by callback. Because a run record is
saved to disk, a handle can be reopened from a fresh process:
`attach_run(machine=, blueprint=, run=None)` takes the ordinary
selectors plus the machine-scoped run number, defaulting to the
machine's latest run exactly like the CLI's `run` commands do. A
handle doesn't care what kind of run started it: `attach_run`
follows an interaction run (`begin_run` / `end_run`) exactly the
same way it follows a script run.
Contract:
[script spec](script-spec.md) "Failure, runs, and transcripts"
and planning/proposed/FEATURES.md "Asynchronous runs".

**The fetch handle** (returned by `start_fetch()`): the same
pull-based interface, but over a stream that exists only for as
long as the process runs — there is no attaching to it by id from
another process (reconnecting later is what run records are for),
and no CLI command exists for it (see the async-starter rule
above). It also rejects `on_mismatch="prompt"`: a fetch running in
the background can never stop and wait on a hidden prompt.
Contract: [media spec](media-spec.md#fetch-progress).

## Realignment of the implemented binding

**The session realignment (P26, 2026-07-31)** did the whole
change in one landing: the methods described above moved onto
the exported `Session` class, the old module-level functions
became internal, the directory global variables — along with
their `set_*_dir()` setter functions and `adopt_environment()` —
were deleted, and the `context=` / `properties_file=` parameters
that every public function used to take were removed, since they
are now carried once in the record the session is opened on. The
old first-use `dir.unassigned` check was replaced by the
construction-time refusal described above; the error id itself
did not change.

The implemented binding now uses the settled names:
`create_machine`, `start_machine`, `stop_machine`, and
`destroy_machine` (replacing the earlier names
`create_from_blueprint` / `start_cached_machine` /
`stop_cached_machine` / `machines.start`).
`lifecycle.py`'s old `start_machine(config)` function, which used
to collide with this name, is gone along with the root-home model
it belonged to — its `Runner` / `MachineConfig` interface has been
replaced by the blueprint machine model.

**There is no file-transfer API, and no drive-contents report**
(D108). The binding never writes a file onto a machine's drives,
never reads one back, never lists what's on a drive, and never
maps a volume to a guest drive letter: what's inside a volume is
the caller's own business, reached with the caller's own tools
against the machine directory that `get_machine_dir` returns —
this is the sanctioned way to reach it, not a fallback for a
missing feature (P16's file-content carve-out). What the binding
does provide is the drives themselves: a directory-source media
attaches a host directory to the guest through vvfat, and
`insert_media(file=)` mounts an image the caller already built
(U20). `describe_drives` / `refresh_drives` / `put_file` /
`get_file` / `put_files` / `get_files` / `list_files` have been
deleted outright, not merely marked deprecated, and
`list_machines` now includes the declared drive facts for anyone
who used to read that from the deleted report.
