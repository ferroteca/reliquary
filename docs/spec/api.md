<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# The embedding API

> **Status:** the end-goal design for Reliquary's embedding API —
> the second primary interface (planning/INTERFACES.md). The
> implemented Python binding is documented in
> [docs/api-reference.md](../../docs/api-reference.md); this page
> consolidates the settled API design and conventions and is the
> index into each family's normative contract. Engineering
> invariants for the current binding remain in AGENTS.md "The
> runner surface".

## Principles

- **One semantic surface with the CLI.** Every command maps
  one-to-one onto a public API call with the same semantics;
  nothing is CLI-only, and no public capability is unreachable
  from the CLI. A change lands on both presentations in the same
  change, never deferred (planning/INTERFACES.md; AGENTS.md
  "CLI–API parity").
- **Python is the first binding, not the definition.** The API
  expects native bindings in multiple languages, and no shape may
  be adopted that a common binding language (C, Java) cannot
  express cleanly: flat functions, plain values, pull-only
  handles, no callbacks.
- **Computation belongs to the caller** (language goal G2).
  Reliquary attaches no meaning to guest output; result
  interpretation and test-framework semantics live in consuming
  projects. In-repo consumers (the media layer, the script
  runtime) drive the same public surface available to external
  callers.
- **The blessed sync divergence.** Blocking API forms return
  typed results and raise by error class; the CLI speaks streams,
  documents (`--json`), and exit codes. Twins in capability,
  divergent in presentation — a named decision, not drift
  (planning/proposed/FEATURES.md "Asynchronous runs").
- **No backward compatibility before 1.0.** The implemented
  binding realigns to the settled names below when the
  realignment lands; there are no aliases or shims.

## Conventions

- **Naming — the twin-name identity rule** (owner, 2026-07-21):
  flat verb-noun functions — `create_machine`, `fetch_media`,
  `run_script` — and the CLI command *is* the twin's name,
  dash-separated (`create-machine` ↔ `create_machine`), its
  flags mirroring the function's parameters. Naming a twin names
  its command; drift is impossible by construction. Two named
  exceptions, each an identity with a different home surface:
  the guest-console family spells as the script language's verbs
  (its twins deferred to the control-plane design), and the
  `run` family maps to the run handle's methods. The exceptions
  cover command names only — flags mirror their function's or
  method's parameters everywhere, exception families included
  (`run cancel --stop-machine` ↔ `cancel(stop_machine=)`).
- **Selectors** (owner, 2026-07-21): machine-scoped functions
  take `machine=` — the full machine id (`"<blueprint>-<n>"`),
  exactly — or `blueprint=` — a blueprint name, selecting its
  sole machine; `resolve_machine()` is the shared resolution
  seam — an implementation seam both presentations route
  through, not a public twin (owner, 2026-07-21): it gets no
  command, selection is a property of every machine-scoped call,
  and the query form is `list_machines(blueprint=)`. Each
  parameter carries one honest type: there is no
  prefix matching and no bare-number form (the id *is* the
  (blueprint, number) pair composed), so the selectors bind
  cleanly in any language.
- **Mirrored globals**: a `Context` of six directory slots —
  `home_dir=`, `blueprints_dir=`, `scripts_dir=`, `cache_dir=`,
  `media_dir=`, `machines_dir=` — mirrors the six `--*-dir` flags
  one for one, and `autoseed=` mirrors `--autoseed`/`--no-autoseed`.
  A `Context` is a plain record of nullable paths rather than a
  configured object, so it binds as six strings from C or Java. The
  embedding API **assigns nothing**: a bare call that resolves a
  name with no directory assigned fails closed naming that
  directory, and autoseeding is off, so automation never picks up
  the developer's home, a stray CWD, or the codex. The CLI's
  defaults are the CLI's, not the library's
  ([asset-resolution.md](asset-resolution.md#the-working-directories)).
- **Returns mirror what the CLI prints**: `create_machine` and
  `clone_machine` return the new machine id; `import_vm` returns
  the blueprint it wrote. Under the CLI's global `--json` the
  mirror is exact (settled 2026-07-21): the command prints the
  twin's return serialized as one JSON document, so a return
  contract is also the command's machine-readable output
  contract (docs/spec/cli.md). Returns are plain
  JSON-shaped values (owner, 2026-07-21): a union of document
  shapes is ordinary JSON — `get_property` returns an ordinary
  value's string but a secret's marker, exactly as `--json`
  serializes — while a value-or-handle union is never allowed: a
  handle is not a value, which is why a `detach=` mode flag on
  the blocking twins was declined. Return shapes are contracted
  additively from 1.0 (owner, 2026-07-22; the horizon moved from
  beta with D25): new fields may
  appear, an existing field never changes type or meaning, and a
  removal or rename is a breaking change — consumers tolerate
  unknown fields; pre-1.0 the shapes may change with the specs
  (the CLI stability contract, docs/spec/cli.md).
- **Errors — the taxonomy is named** (owner, 2026-07-21):
  blocking forms raise by error class under one root. Python
  spells the root `ReliquaryError` — every deliberate Reliquary
  error subclasses it, on every surface, so
  `except ReliquaryError` is always the catch-all — and the run
  surface's classes `StaticError` (exit 2), `PreflightError`
  (exit 3), `RunFailure` (exit 4), and `RunCancelled` (exit 5;
  it subclasses the root, never `RunFailure` — cancellation is
  an outcome, neither success nor failure): the run surface's
  exit codes and exceptions are one mapping under parity (script
  spec "Error classes and exit codes"). **The four are not the
  run surface's alone** (D58, 2026-07-27): they generalize
  unchanged to every interface, because what decides them —
  settled by the authored input alone, the world not satisfying
  that input, the work itself failing — never mentions a script.
  A malformed blueprint raises `StaticError`; naming a machine
  that does not exist raises `PreflightError`; so does a
  capability this build declares but has not implemented. Growth
  is still additive, never a break.
  Exit `1` — Reliquary's own fault, never a caller's
  mistake — is precisely an error outside those four, and has two
  populations: a deliberate `InternalError`, an invariant
  Reliquary detected in its own state, and a genuine accident
  that never was a `ReliquaryError`. A deliberate raise always
  lands in the hierarchy, which is what keeps
  `except ReliquaryError` the catch-all promised above.
  Other bindings spell the same classes natively.
- **Async starters — sync is async plus attach** (owner,
  2026-07-21; backlogged 2026-07-24, D35/D36 — no use case,
  drafted as U19; milestone 9 keeps only the blocking twins,
  which *return* their output and store nothing — D36, so the
  record-management verbs go to the backlog too): a long
  operation is one start+attach model with
  two projections (planning/proposed/FEATURES.md "Asynchronous runs"). The
  CLI composes them: every foreground command is
  start-plus-attach, and `--detach` is start without attach. The
  API separates them: the blocking twin (`run_script()`,
  `fetch_media()`) is the composition, and the starter
  (`start_script()`, `start_fetch()`) returns the handle that
  attach follows. A starter therefore never has its own command —
  it *is* the composed command's `--detach` mode
  (`run-script --detach` ↔ `start_script()`), and the identity
  rule binds the capability pair, not each function alone.
  `start_fetch` has no CLI form at all — a fetch handle is
  process-local, so for a CLI driver the `fetch-media` process
  itself is the handle: background it and read
  `--progress jsonl`; reattachment is what run records provide.
- **Handles are pull-only**: `status()`, `events(follow=)` as a
  blocking iterator, `wait(timeout=)`, `cancel()` — never
  callbacks. `wait()` completes exactly as the blocking twin —
  same result, same raises — and expiry raises outside the
  taxonomy (Python: the builtin `TimeoutError`), because nothing
  failed: the operation is still live, the handle stays valid,
  and the call may be repeated (owner, 2026-07-21) —
  deliberately outside `except ReliquaryError`'s reach, because
  an expiry is not a Reliquary error. A handle is
  a follower, never the owner: dropping one never affects its
  operation — `cancel()` is the only cancellation.

## The surface

Each family's normative contract lives with its interface spec;
this table is the index.

Under the identity rule the CLI column is the mechanical
transform of the twin column (dash ↔ underscore); the table
carries the exceptions and each family's contract home.

| CLI | API twin | contract home |
|---|---|---|
| `create-machine` / `start-machine` / `stop-machine` / `apply-blueprint` / `destroy-machine` / `recreate-machine` / `clone-machine` / `delete-blueprint` | the same names with underscores; `create_machine(name, *, dry_run=False, backend=None)` returns `str \| DryRun` — a distinct type so a dry return can never pass for the real one, and `backend=` (legal only under `dry_run`) asks what a *named* backend would do | [blueprint guide](../blueprint-guide.md), [cli.md](cli.md#the-dry-run) |
| `export-drive` / `export-machine` | `export_drive(key, destination)` / `export_machine(to=, destination=None)` — stream-bearing; `to=` names an exporter (a vocabulary decoupled from backends) and is required | blueprint guide |
| `import-vm` | `import_vm(source, name, platform, hdd_images, snapshot)` | blueprint guide |
| `new-blueprint` | `new_blueprint()` | blueprint guide |
| `seed-blueprint` / `seed-script` | `seed_blueprint(name, only=)` / `seed_script()` | [codex](codex.md) |
| `run-script <label>` | `run_script()` returns the run's output, raises by error class (D36 — no stored record; the `exec` twin lands with it) | [script spec](script-spec.md) |
| `check-script` | `check_script()` | script spec |
| the `run` family; `begin-run` / `end-run`; `list-runs` — all backlog (D35/D36) | the record model — persisted runs, `run status` / `run delete`, the async followers `run tail` / `run wait` / `run cancel` with the run handle (`start_script()` / `attach_run()` / `delete_run()`), and interaction runs (`begin_run` / `end_run`) — is async-backlog work; milestone 9 stores nothing | script spec |
| `fetch-media` | `fetch_media()` blocking; `start_fetch()` → fetch handle (backlog — D35) | [media spec](media-spec.md#fetch-progress) |
| `clean-media` / `prune-media` / `add-media` | `clean_media(name=None)` / `prune_media(dry_run=)` / `add_media(name, path)` | media spec |
| `insert-media` / `eject-media` / `set-boot-order` | `insert_media(slot, media=None, file=None)` (`--file` mounts an anonymous `local`+`use` image, U20) / `eject_media()` / `set_boot_order()` | blueprint guide, script spec |
| `get-machine-dir` | `get_machine_dir()` — the machine's cache directory as an absolute path; the out-of-band door | [instance model](instance-model.md) |
| `get-machine-var` | `get_machine_var(key)` — reads a machine variable a script `set` (a `machine.json` field cleared on start; the script→host scalar channel, U14/U20) | script spec |
| `put-file` / `get-file` / `put-files` / `get-files` / `list-files` | the same names with underscores; `list_files(address, recursive=False)` returns the flat entry array — guest-terms addressed (P17) in one vocabulary across all five, over a vvfat drive, stopped-only, non-vvfat fails closed by name (P11). Single files landed at milestone 9, the trees and the listing with D62 (U14, U20; P16) | [cli.md](cli.md) |
| `list-machines` / `list-blueprints` / `list-scripts` / `list-media`; `search-blueprints` / `search-scripts` / `search-media` | `list_<noun>` / `search_<noun>` (`list_machines` today; the rest follow the pattern as they land) | family semantics: [cli.md](cli.md); each noun's returns: that noun's spec, as they land |
| `get-property` / `set-property` / `unset-property` / `list-properties` | `get_property()` / `set_property()` / `unset_property()` / `list_properties()` | [script properties](script-properties.md) |
| guest-console family (`type` / `enter` / `press` / `exec` / `select` / `wait` / `screen` / `screenshot` / `hmp`) | today's `Machine` and module functions; twins land with the control-plane design — the script-language-identity exception (CLI spellings settled 2026-07-21) | [script spec](script-spec.md) (verbs); the control-plane design (twins) |

`import-vm`'s twin is `import_vm` — a bare `import` is a Python
keyword, and under the identity rule the CLI simply adopts the
twin's name. Export's former named omission is closed (owner,
2026-07-22): `export_drive` / `export_machine` above, the `--to`
exporter vocabulary deliberately decoupled from the backend
list.

## Handles

> Both handles below are **backlog work** (D35): the
> asynchronous-run pillar left the numbered arc for lack of a use
> case (drafted as U19). Milestone 9 delivers the blocking twins
> (`run_script()`, `fetch_media()`) and the record-management
> verbs; the pull-only handles and `attach_run()` return when U19
> is pledged. The design stands as written.

**The run handle** (`start_script()`; reopened by
`attach_run()`): a pull-only follower of the run's live
`run-events.jsonl`. Because a run record persists, a handle can
be reopened from a fresh process:
`attach_run(machine=, blueprint=, run=None)` takes the ordinary
selectors plus the machine-scoped run number, defaulting to the
machine's latest run exactly as the CLI `run` operations do.
Followers are indifferent to the driver: `attach_run` follows an
interaction run (`begin_run` / `end_run`) exactly as a script
run.
Contract:
[script spec](script-spec.md) "Failure, runs, and transcripts"
and planning/proposed/FEATURES.md "Asynchronous runs".

**The fetch handle** (`start_fetch()`): the same pull vocabulary
over an ephemeral stream — process-local, no attach-by-id
(reattachment is what run records provide), no CLI command (the
async-starter convention above), and it rejects
`on_mismatch="prompt"`: a background fetch can never hang on a
hidden prompt. Contract: [media spec](media-spec.md#fetch-progress).

## Realignment of the implemented binding

The implemented binding uses the settled family:
`create_machine`, `start_machine`, `stop_machine`, and
`destroy_machine` (replacing the earlier
`create_from_blueprint` / `start_cached_machine` /
`stop_cached_machine` / `machines.start` spellings).
`lifecycle.py`'s legacy `start_machine(config)` name collision
dies with the root-home model, whose `Runner` / `MachineConfig`
surface is superseded by the blueprint machine model
(file exchange is settled 2026-07-22 and completed by D62:
in-band verbs cover single files, whole trees and listings —
`put_file` / `get_file` / `put_files` / `get_files` /
`list_files`, all guest-terms addressed and stopped-only, and
none of them a script verb. Out-of-band host access to a stopped
machine's drives remains possible and is now convenience alone
(P16): the machine directory reported by `get_machine_dir`, the
user's own image tooling. vvfat is the mechanism a
directory-source media attaches through, and an image drive has
no in-band route until an adapter grows at-rest filesystem
access — a gap named rather than hidden, P11).
