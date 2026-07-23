<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Blueprint guide

A **blueprint** is a reusable JSON design for a machine, composed of
named **components**: a `machine` plus the `media`, `source`, and
`archive` components it draws on, all in one `.rlqb` file. One
blueprint can create many machines.

## Blueprint vs machine

- **Blueprint**: The portable `.rlqb` document you author — a lone
  machine as a "bare root" (its fields at top level), or the
  sectioned form (`machines` / `media` / `sources` / `archives`).
- **Machine**: A disposable realization built from a blueprint,
  identified as `<name>-<n>`.

Editing a blueprint never changes an existing machine. To adopt blueprint edits, destroy the machine and create it again.

## Component sections

A `.rlqb` root is either a bare machine (its fields at top level) or
these optional sections, each a list:

- `machines` - one or more machine components (topology only)
- `media` - the media a machine's drives name; a media owns
  `materialize` (`new` / `difference` / `copy` / `use`), `size`,
  `source`, `sha256`, `read-only`
- `sources` - named locators (a `url`+mirrors, a `local` path)
- `archives` - recursive archive trees a media is extracted from

See [the media spec](../planning/design/media-spec.md) for the
media/source/archive components.

### Machine fields

- `name` - The machine's identity (the selection key). A lone
  bare-root machine may omit it (it defaults to the filename stem);
  a machine in a `machines` section must name itself. Id-safe
  (letters, digits, `.`, `_`, `-`; not all digits). A machine's id
  is `<name>-<n>`.
- `description` - Human-readable description
- `platform` - Platform (default: `dos`)
- `memory` - Memory size (e.g., `"32M"`) or positive integer MiB
- `drives` - Drive declarations: each slot names a **media** by
  name, or `null` (empty removable slot), or an object with
  `media` / `controller` / `enabled`. A drive says nothing about
  content — the named media owns it.
- `boot` - Boot order (array of drive keys)
- `scripts` - Named scripts on the blueprint (values are script stems without `.rlqs`)

## Example blueprint

A machine with a blank hard disk and an empty CD slot, plus the
`blank-20m` media it names — one self-contained composed file:

```json
{
  "machines": [
    {
      "name": "freedos-1.4-plain",
      "description": "FreeDOS 1.4 plain installation",
      "platform": "dos",
      "memory": "32M",
      "drives": {
        "hdd0": "blank-20m",
        "cdrom0": null
      },
      "boot": ["hdd0", "cdrom0"],
      "scripts": {
        "install": "freedos-1.4-plain-install",
        "verify": "freedos-1.4-verify"
      }
    }
  ],
  "media": [
    {"name": "blank-20m", "materialize": "new", "size": "20M"}
  ]
}
```

## Using blueprints

```powershell
# Create a machine from a blueprint
rlq create-machine --blueprint freedos-1.4-plain

# Start it
rlq start-machine --blueprint freedos-1.4-plain

# Run a script
rlq run-script install --blueprint freedos-1.4-plain

# Stop it
rlq stop-machine --blueprint freedos-1.4-plain

# Destroy it
rlq destroy-machine --machine freedos-1.4-plain-1
```

## Machine lifecycle

Machines live under `cache/machines/<name>-<n>/`. Each machine has:
- `machine.json` - The resolved state document; while running, it
  also carries the live VM identity and port as a `vm` section
- `media/` - The machine's per-machine materialized images, named
  by media (`<media-name>.qcow2`)
- `runs/` - Run records (transcripts, screenshots, outputs)
- `<backend>/` - The backend's own files (e.g. `qemu/qemu-stderr.log`)

For the complete blueprint specification, see [planning/design/machine-blueprint.md](../planning/design/machine-blueprint.md); the machine, media, source, and archive components validate against the published [blueprint-schema-v1.json](../Reliquary/schemas/blueprint-schema-v1.json).
