<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# The embedding API

> **Status:** the end-goal design for reliquary's embedding API —
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
  reliquary attaches no meaning to guest output; result
  interpretation and test-framework semantics live in consuming
  projects. In-repo consumers (the media layer, the script
  runtime) drive the same public surface available to external
  callers.
- **The blessed sync divergence.** Blocking API forms return
  typed results and raise by error class; the CLI speaks streams,
  documents (`--json`), and exit codes. Twins in capability,
  divergent in presentation — a named decision, not drift
  (planning/ROADMAP.md "Asynchronous runs").
- **No backward compatibility before beta.** The implemented
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
  `run` family maps to the run handle's methods.
- **Selectors** (owner, 2026-07-21): machine-scoped functions
  take `machine=` — the full machine id (`"<blueprint>-<n>"`),
  exactly — or `blueprint=` — a blueprint name, selecting its
  sole machine; `resolve_machine()` is the shared resolution
  seam. Each parameter carries one honest type: there is no
  prefix matching and no bare-number form (the id *is* the
  (blueprint, number) pair composed), so the selectors bind
  cleanly in any language.
- **Mirrored globals**: `home=`, `assets=`, and `assets_only=`
  keywords mirror `--home`, `--assets`, and `--assets-only`.
- **Returns mirror what the CLI prints**: `create_machine` and
  `clone_machine` return the new machine id; `import_vm` returns
  the blueprint it wrote. Under the CLI's global `--json` the
  mirror is exact (settled 2026-07-21): the command prints the
  twin's return serialized as one JSON document, so a return
  contract is also the command's machine-readable output
  contract (planning/ROADMAP.md "The CLI").
- **Handles are pull-only**: `status()`, `events(follow=)` as a
  blocking iterator, `wait(timeout=)`, `cancel()` — never
  callbacks.

## The surface

Each family's normative contract lives with its interface spec;
this table is the index.

Under the identity rule the CLI column is the mechanical
transform of the twin column (dash ↔ underscore); the table
carries the exceptions and each family's contract home.

| CLI | API twin | contract home |
|---|---|---|
| `create-machine` / `start-machine` / `stop-machine` / `apply-blueprint` / `destroy-machine` / `recreate-machine` / `clone-machine` / `delete-blueprint` | the same names with underscores | [blueprint guide](machine-blueprint.md) |
| `export` | *open — name and twin land together with export's shape* | blueprint guide |
| `import-vm` | `import_vm(source, name, platform, hdd_images, snapshot)` | blueprint guide |
| `new-blueprint` | `new_blueprint()` | blueprint guide |
| `seed-blueprint` / `seed-media` / `seed-script` | `seed_blueprint(name, only=)` / `seed_media()` / `seed_script()` | [codex](codex.md) |
| `run-script <label>` | `run_script()` blocking; `start_script()` → run handle (`--detach`) | [script spec](script-spec.md) |
| `check-script` | `check_script()` | script spec |
| `run status` / `tail` / `wait` / `cancel` | run-handle `status()` / `events()` / `wait()` / `cancel()`, plus attach-by-id — the handle-method exception | script spec |
| `run delete` | `delete_run()` | script spec |
| `fetch-media` | `fetch_media()` blocking; `start_fetch()` → fetch handle | [media spec](media-spec.md#fetch-progress) |
| `clean-downloads` / `clean-media` | `clean_downloads()` / `clean_media()` | media spec |
| `insert-media` / `eject-media` / `set-boot-order` | `insert_media()` / `eject_media()` / `set_boot_order()` | blueprint guide, script spec |
| `list-machines` / `list-blueprints` / `list-scripts` / `list-media` / `list-runs`; `search-blueprints` / `search-scripts` / `search-media` | `list_<noun>` / `search_<noun>` (`list_machines` today; the rest follow the pattern as they land) | [cli design](cli.md) |
| `get-property` / `set-property` / `unset-property` / `list-properties` | `get_property()` / `set_property()` / `unset_property()` / `list_properties()` | [property registry](property-registry.md) |
| guest-console family (`type` / `enter` / `press` / `exec` / `select` / `wait` / `screen` / `screenshot` / `hmp`) | today's `Machine` and module functions; twins land with the control-plane design — the script-language-identity exception (CLI spellings settled 2026-07-21) | cli design |

`import-vm`'s twin is `import_vm` — a bare `import` is a Python
keyword, and under the identity rule the CLI simply adopts the
twin's name. `export`'s name and twin are deliberately unsettled
until export's own shape lands — a named omission, not drift.

## Handles

**The run handle** (`start_script()`, reopenable by id): a
pull-only follower of the run's live `run-events.jsonl`. Because
a run record persists, a handle can be reopened from a fresh
process (attach-by-id). Contract:
[script spec](script-spec.md) "Failure, runs, and transcripts"
and planning/ROADMAP.md "Asynchronous runs".

**The fetch handle** (`start_fetch()`): the same pull vocabulary
over an ephemeral stream — process-local, no attach-by-id
(reattachment is what run records provide), and it rejects
`on_mismatch="prompt"`: a background fetch can never hang on a
hidden prompt. Contract: [media spec](media-spec.md#fetch-progress).

## Realignment of the implemented binding

At the implementation realignment the current binding renames to
the settled family: `create_from_blueprint` → `create_machine`;
the package's `start_cached_machine` / `stop_cached_machine`
(module `machines.start` / `stop` / `destroy`) →
`start_machine` / `stop_machine` / `destroy_machine`.
`lifecycle.py`'s legacy `start_machine(config)` name collision
dies with the root-home model, whose `Runner` / `MachineConfig`
surface is superseded by the blueprint machine model
(file exchange for U3's stage/collect loop remains an open
design — planning/TASKS.md).
