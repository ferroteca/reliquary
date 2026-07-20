<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Machine specs and machines

> **Status:** this documents the planned machine model. It replaces
> the earlier one-declaration/one-machine model and is not implemented
> yet.

A **spec** is a reusable, user-owned JSON description of a kind of
machine. A **machine** is one named realization of that spec: its
writable disks, backend object, run history, and lifecycle. One spec
may have zero, one, or many machines. A spec name is never a machine
name.

```text
<reliquary_home>/
├── specs/
│   └── freedos-plain.json          user-owned reusable spec
├── machines/
│   └── lab-a.json                  reliquary-owned machine record
└── cache/machines/
    └── 5fd1…/                      replaceable machine cache
        ├── state.json
        ├── drives/
        ├── runs/
        └── backend files and logs
```

The file name of `specs/<name>.json` is the spec name. The file name
of `machines/<name>.json` is the machine name. Machine names are
unique within a home; a generated UUID in each record is the stable
machine ID. Backend identity, cache paths, locks, and run directories
use that UUID rather than either human name.

## Lifecycle

```text
reliquary create <machine_name> --spec <spec_name>
reliquary start <machine_name> [--display]
reliquary stop <machine_name>
reliquary destroy <machine_name>
reliquary recreate <machine_name>
reliquary delete <machine_name>
reliquary clone <machine_name> <new_machine_name>
reliquary export <machine_name> [<destination>]
```

`create` validates and resolves the current spec, creates a machine
record with a new UUID, and materializes its writable drives and
backend object. `destroy` removes only the materialization and marks
the machine uninstantiated; its name, UUID, and spec reference remain.
`recreate` is `destroy` followed by `create` using the same machine
name and UUID. `delete` removes the durable record after
destroying the materialization.

Editing a spec affects future `create` operations, not existing
machines. Each machine records the source spec and resolved digest at
creation. Applying a newer spec to a stopped machine is an explicit
operation and never happens implicitly at `start`.

`clone` creates a new UUID and machine record. It retains the same
resolved spec snapshot but copies the source machine's writable drives
when they exist; it is therefore a snapshot of a machine, not another
name for a spec. A future `fork-spec` command may create a new editable spec; it
is intentionally not implicit in clone.

## Instance record and cache state

The spec remains the plain machine JSON object described by the
[machine spec](machine-spec.md). A machine record is a separate
reliquary-owned JSON document, not a second spelling of that schema:

```json
{
  "id": "5fd11917-147a-4b6b-b7f6-9f4b6d7d1ab2",
  "spec": "freedos-plain",
  "created": "2026-07-19T18:20:11Z",
  "phase": "ready"
}
```

`cache/machines/<id>/state.json` contains the resolved spec digest,
backend ID, realized drive/controller addresses, and transient runtime
attachments. It is fully regenerated from the spec and instance record
when safe. It must never be edited by hand.

The record and cache state carry an operation generation and one of
`uninstantiated`, `creating`, `ready`, `running`, `stopping`, or
`destroying`. Every mutating operation takes an exclusive per-machine
lock before inspecting backend state. On startup reliquary detects an
interrupted phase, verifies backend identity, and either completes a
safe rollback or fails with explicit recovery instructions. Atomic
file replacement protects JSON writes; it does not pretend a host file
write and a hypervisor operation are one transaction.

There is no `installed` boolean. Script outcomes belong to the
append-only run records under the instance cache, where they can name
the script, its source digest, result, transcript, and produced
artifacts without making a vague claim about the guest's contents.

## Naming and renaming

Users author and rename specs by changing files in `specs/`. Machine
renaming is a lifecycle operation:

```text
reliquary rename <machine_name> <new_machine_name>
```

It updates the durable machine record atomically while retaining its
UUID, cache directory, and backend identity. Manual directory renames
are unsupported.

## JSON remains the format

Specs, instance records, cache state, and media definitions remain
JSON. They are declarative documents with strict schemas and benefit
from editor completion, stable formatting, and precise diagnostics.
The script language remains the separate line-oriented behavioral
format. Reliquary publishes a JSON Schema for each JSON document type;
the schema version tracks the reliquary release, not a version field in
user documents before beta.
