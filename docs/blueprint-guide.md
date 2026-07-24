<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Blueprint guide

A **blueprint** is a reusable JSON design for a machine: an array of
**specs** of two types — a `machine` plus the `media` it draws on —
all in one `.rlqb` file. One blueprint can create many machines.

## Blueprint vs machine

- **Blueprint**: The portable `.rlqb` document you author — an
  array of specs, or a lone spec object as sugar for the array of
  one.
- **Machine**: A disposable realization built from a blueprint,
  identified as `<name>-<n>`.

Editing a blueprint never changes an existing machine. To adopt blueprint edits, destroy the machine and create it again.

## Specs

A `.rlqb` root is an array of specs. Each declares its `type`, which
defaults to `media` — so a machine must say `"type": "machine"`, and
an untyped object is a media.

- **machine** - topology only: no content lives here.
- **media** - what a machine's drives name. A media owns
  `materialize` (`new` / `difference` / `copy` / `use`), `size`,
  one `location`, `sha256`, `read-only`, and `children`.

There is no separate source or archive type. A source is a media's
`location`; an archive is just a media that other media name as their
**parent**, either from the child side or through the parent's
`children` list. The distinction was never a property of the
artifact, only of the use — the same ISO can be mounted at a drive
and read as a container.

See [the media spec](../planning/design/media-spec.md) for media in
full.

### Machine fields

- `name` - The machine's identity (the selection key), and
  required: the `.rlqb` file's own stem is never an identity.
  Id-safe (letters, digits, `.`, `_`, `-`; not all digits). A
  machine's id is `<name>-<n>`.
- `description` - Human-readable description
- `platform` - Platform (default: `dos`)
- `memory` - Memory size (e.g., `"32M"`) or positive integer MiB
- `drives` - Drive declarations: each slot names a **media** by
  name, or `null` (empty removable slot), or an object with
  `media` / `controller` / `enabled`, or a media written in place.
  A drive says nothing about content — the media owns it. The
  content-free blank `{"size": "20M"}` written at a drive needs no
  name at all: nothing else refers to it, and it is materialized
  fresh into every machine.
- `boot` - Boot order (array of drive keys)
- `scripts` - Named scripts on the blueprint (values are script stems without `.rlqs`)

## Example blueprint

A machine with a blank hard disk written in place and an empty CD
slot the install script fills — one self-contained file:

```json
[
  {
    "type": "machine",
    "name": "freedos",
    "description": "FreeDOS 1.4 plain installation",
    "platform": "dos",
    "memory": "32M",
    "drives": {
      "hdd0": {"type": "media", "size": "20M"},
      "cdrom0": null
    },
    "boot": ["hdd0", "cdrom0"],
    "scripts": {
      "install": "freedos-install",
      "verify": "freedos-verify"
    }
  }
]
```

## Using blueprints

```powershell
# Create a machine from a blueprint
rlq create-machine --blueprint freedos

# Start it
rlq start-machine --blueprint freedos

# Run a script
rlq run-script install --blueprint freedos

# Stop it
rlq stop-machine --blueprint freedos

# Destroy it
rlq destroy-machine --machine freedos-1
```

## Machine lifecycle

Machines live under `cache/machines/<name>-<n>/`. Each machine has:
- `machine.json` - The resolved state document; while running, it
  also carries the live VM identity and port as a `vm` section, plus
  any machine variables a script set (cleared at each start)
- `media/` - The machine's per-machine materialized images, named
  by media (`<media-name>.qcow2`)
- `screenshots/` - Screenshots a script asked for, and the automatic
  capture a failure report references
- `<backend>/` - The backend's own files (e.g. `qemu/qemu-stderr.log`)

A run writes nothing here: it returns its output to whoever started
it, and keeping that output is the caller's choice.

For the complete blueprint specification, see
[the composed blueprint model](../planning/design/blueprint-model.md);
both spec types validate against the published
[blueprint-schema-v1.json](../reliquary/schemas/blueprint-schema-v1.json).
