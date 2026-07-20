<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Machine blueprints and machines

> **Status:** milestone 1 spikes 5–6 implement materialization and the
> lifecycle CLI (`create` / `start` / `stop` / `destroy` /
> `list machines`, `--blueprint` / `--machine` selection) for the
> QEMU-only subset. Spike 10 adds append-only run directories under
> `cache/machines/<id>/runs/` for `script <label>`. Locking, recovery,
> `apply`, `recreate`, clone / export, and absorbing the legacy
> root-home model remain later milestones.

A **blueprint** is a reusable, user-owned JSON description of a kind of
machine. A **machine** is one realization of that blueprint: its
writable disks, backend object, run history, and lifecycle. One blueprint
may have zero, one, or many machines. Blueprints have names; machines
have ids.

```text
<reliquary_home>/
├── blueprints/
│   └── freedos.json          user-owned reusable blueprint
└── cache/machines/
    └── freedos-0/            the machine — disposable
        ├── reliquary-machine.json
        ├── drives/
        ├── runs/
        └── backend files and logs
```

The file name of `blueprints/<name>.json` is the blueprint name. A machine's
identity is `<blueprint>-<n>`, where `<n>` is the lowest free
non-negative integer for that blueprint at `create` time (destroy
frees the number for reuse). Allocation is serialized with a
per-blueprint lock under `cache/machines/.locks/`. The cache
directory, run directories, and backend identity all use the
machine id, and there is no separate machine name. A machine
**is** its cache directory — nothing about a machine lives
outside `cache/`, because nothing about a machine is durable.
Deleting the cache deletes the machines, by design.

Commands select their targets with explicit flags, never
positionally:

- `--blueprint <name>` — that blueprint's machine when exactly one
  exists
- `--machine <blueprint>-<n>` — the full machine id (or any
  unambiguous prefix)
- `--blueprint <name> --machine <n>` — machine number `<n>` of that
  blueprint

On machine-level verbs, `--blueprint <name>` alone fails when
several machines exist (listing the candidate ids) or when none
exist (suggesting `create`; `script` creates one instead).

## Lifecycle

A machine rests in one of two phases — `ready` or `running` — and
passes through transitional phases (`creating`, `stopping`,
`destroying`) that exist so an interrupted operation is
detectable and recoverable:

```mermaid
stateDiagram-v2
    [*] --> creating: create
    creating --> ready
    ready --> running: start
    running --> stopping: stop
    stopping --> ready
    ready --> ready: apply
    ready --> destroying: destroy
    destroying --> [*]
```

`destroy` removes the machine entirely — there is no
half-destroyed resting phase, because a machine is nothing but
its cache directory. `recreate` is `destroy` + `create` as one
command, reusing the same id; `clone` and `export` require
`ready`. On startup reliquary detects a machine stranded in a
transitional phase and completes a safe rollback or fails with
recovery instructions (see below).

```text
rlq list blueprints
rlq list machines [--blueprint <name>]
rlq create --blueprint <name>
rlq start (--machine <id> | --blueprint <name>) [--display]
rlq stop (--machine <id> | --blueprint <name>)
rlq apply (--machine <id> | --blueprint <name>)
rlq destroy (--machine <id> | --blueprint <name>)
rlq recreate (--machine <id> | --blueprint <name>)
rlq delete --blueprint <name>
rlq clone (--machine <id> | --blueprint <name>)
rlq export (--machine <id> | --blueprint <name>) [<destination>]
```

`list blueprints` shows each blueprint and its machine count; `list machines`
shows each machine's id, blueprint, phase, and backend —
both enumerated by scanning `cache/machines/`. `create`
validates and resolves the current blueprint, materializes a new
machine under the next free `<blueprint>-<n>` id — state, writable
drives, backend object — and prints the id. `destroy` deletes the
machine entirely: the whole cache directory and the backend machine.
`recreate` is `destroy` followed by `create` as one command,
reusing the same id. `delete` takes only `--blueprint`: it
removes the blueprint file itself and fails closed while any
machine of it exists, naming the machine ids — destroy them
first.

Editing a blueprint affects future `create` operations, not existing
machines. Each machine records the source blueprint and resolved digest at
creation; that resolved snapshot is the machine's baseline. Between
`apply`s the machine's own state is authoritative — script
`insert`/`eject` persists there, so a machine may legitimately
diverge from its baseline — and `start` runs the machine as its
state describes, never re-reading the current
blueprint file. Adopting blueprint edits — and returning a
diverged machine to its blueprint shape — is the explicit `apply`: with the
machine stopped, it re-resolves the current blueprint and reconciles the
machine to it — applicable differences (memory, boot order, drives
enabled or disabled, media changes) are applied and the recorded
digest updated; contradictions the machine cannot absorb without
regenerating (such as a changed `size` on an existing image) fail
closed naming both sides, leaving `recreate` as the honest
alternative. Applying a newer blueprint never happens implicitly at
`start`.

`clone` creates a new machine under the next free
`<blueprint>-<n>` id. It retains the same
resolved blueprint snapshot but copies the source machine's writable drives
when they exist; it is therefore a snapshot of a machine, not another
name for a blueprint. A future `fork-blueprint` command may create a new editable blueprint; it
is intentionally not implicit in clone.

## The machine state

The blueprint remains the plain machine JSON object described by the
[machine blueprint](machine-blueprint.md). The machine's one document is
`cache/machines/<id>/reliquary-machine.json` — the resolved
blueprint fields plus the machine's own bookkeeping, not a second
spelling of the blueprint schema:

```json
{
  "id": "5fd11917-147a-4b6b-b7f6-9f4b6d7d1ab2",
  "blueprint": "freedos",
  "created": "2026-07-19T18:20:11Z",
  "phase": "ready",
  "...": "resolved blueprint fields, backend-id, blueprint-digest"
}
```

It contains the machine's own id (repeated inside the file as a
safety check — it must match the directory it sits in, so a
hand-copied or misplaced machine directory fails closed), the
source blueprint name, creation time, lifecycle phase, operation
generation, the resolved blueprint digest, backend ID, realized
drive/controller addresses, and transient runtime attachments. It
must never be edited by hand.

The phase is one of `creating`, `ready`, `running`, `stopping`,
or `destroying`. Every mutating operation takes an exclusive
per-machine lock before inspecting backend state. On startup
reliquary detects an interrupted phase, verifies backend
identity, and either completes a safe rollback or fails with
explicit recovery instructions. Atomic file replacement protects
JSON writes; it does not pretend a host file write and a
hypervisor operation are one transaction.

There is no `installed` boolean. Script outcomes belong to the
append-only run records under the instance cache, where they can name
the script, its source digest, result, transcript, and produced
artifacts without making a vague claim about the guest's contents.

## Naming and identity

Users author and rename blueprints by changing files in `blueprints/`.
Machines are never renamed because the id is the whole identity:
`<blueprint>-<n>`, assigned at `create` (lowest free number) and
reused after `destroy`. Manual renames of machine directories under
`cache/machines/` are unsupported.

## JSON remains the format

Blueprints, machine state, and media definitions remain
JSON. They are declarative documents with strict schemas and benefit
from editor completion, stable formatting, and precise diagnostics.
The script language remains the separate line-oriented behavioral
format. Reliquary publishes a JSON Schema for each JSON document type;
the schema version tracks the reliquary release, not a version field in
user documents before beta.
