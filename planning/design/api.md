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
  typed results and raise by error class; the CLI speaks streams
  and exit codes. Twins in capability, divergent in presentation
  — a named decision, not drift (planning/ROADMAP.md
  "Asynchronous runs").
- **No backward compatibility before beta.** The implemented
  binding realigns to the settled names below when the
  realignment lands; there are no aliases or shims.

## Conventions

- **Naming**: flat verb-noun functions — `create_machine`,
  `fetch_media`, `run_script`.
- **Selectors**: machine-scoped functions take a machine id
  (`"<blueprint>-<n>"`) or the CLI's `blueprint=` / `machine=`
  selector pair; `resolve_machine()` is the shared resolution
  seam.
- **Mirrored globals**: `home=`, `assets=`, and `assets_only=`
  keywords mirror `--home`, `--assets`, and `--assets-only`.
- **Returns mirror what the CLI prints**: `create_machine` and
  `clone_machine` return the new machine id; `import_vm` returns
  the blueprint it wrote.
- **Handles are pull-only**: `status()`, `events(follow=)` as a
  blocking iterator, `wait(timeout=)`, `cancel()` — never
  callbacks.

## The surface

Each family's normative contract lives with its interface spec;
this table is the index.

| CLI | API twin | contract home |
|---|---|---|
| `create` | `create_machine` | [blueprint guide](machine-blueprint.md) |
| `start` | `start_machine` | blueprint guide |
| `stop` | `stop_machine` | blueprint guide |
| `apply` | `apply_blueprint` | blueprint guide |
| `destroy` | `destroy_machine` | blueprint guide |
| `recreate` | `recreate_machine` | blueprint guide |
| `clone` | `clone_machine` | blueprint guide |
| `delete` | `delete_blueprint` | blueprint guide |
| `export` | *open — lands with export's shape* | blueprint guide |
| `import` | `import_vm(source, blueprint, platform, hdd_images, snapshot)` | blueprint guide |
| `script <label>` | `run_script()` blocking; `start_script()` → run handle | [script spec](script-spec.md) |
| `check-script` | `check_script()` | script spec |
| `run status` / `tail` / `wait` / `cancel` | run-handle `status()` / `events()` / `wait()` / `cancel()`, plus attach-by-id | script spec |
| `run delete` | `delete_run()` | script spec |
| `fetch` | `fetch_media()` blocking; `start_fetch()` → fetch handle | [media spec](media-spec.md#fetch-progress) |
| `clean downloads` / `clean media` | `clean_downloads()` / `clean_media()` | media spec |
| `insert` / `eject` / `set-boot` (state ops) | `insert_media()` / `eject_media()` / `set_boot_order()` | blueprint guide, script spec |
| `list` / `search` families | `list_<noun>` (`list_machines` today; the rest follow the pattern as they land) | [cli design](cli.md) |
| `property` family | pending naming, with the property-registry design | [property registry](property-registry.md) |
| interaction family (`type` / `keys` / `wait` / `screenshot` / `menu` / `hmp`) | today's `Machine` and module functions; the settled family lands with the control-plane design | cli design (open) |

`import`'s twin is `import_vm` because a bare `import` is a
Python keyword in the first binding. `export`'s twin is
deliberately unnamed until export's own CLI shape settles — a
named omission, not drift.

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
