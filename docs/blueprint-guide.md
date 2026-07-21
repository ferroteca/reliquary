<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Blueprint guide

A **blueprint** is a reusable JSON design for a machine. One blueprint can create many machines.

## Blueprint vs machine

- **Blueprint**: The portable JSON document you author (`<name>.rlqb`)
- **Machine**: A disposable realization built from a blueprint, identified as `<blueprint>-<n>`

Editing a blueprint never changes an existing machine. To adopt blueprint edits, destroy the machine and create it again.

## Milestone-1 implementation

The current implementation (milestone-1) supports a subset of the blueprint format:

### Implemented fields

- `name` - Blueprint name
- `description` - Human-readable description
- `platform` - Platform (default: `dos`)
- `memory` - Memory size (e.g., `"32M"`) or positive integer MiB
- `drives` - Drive declarations
  - `size` - Drive size (e.g., `"20M"`, `"2G"`)
  - `media` - Media item reference
  - JSON `null` - Empty removable slot
- `boot` - Boot order (array of drive keys)
- `scripts` - Named scripts on the blueprint (values are script stems without `.rlqs`)

### Not yet implemented

- JSONC acceptance (comments, trailing commas)
- `backend` / `backend-settings`
- `control-planes`
- Drive `base` (starting-point image)
- Blueprint `parameters`
- Additional platform workflows beyond DOS

## Example blueprint

```json
{
  "name": "freedos-1.4-plain",
  "description": "FreeDOS 1.4 plain installation",
  "platform": "dos",
  "memory": "32M",
  "drives": {
    "hdd0": {"size": "20M"},
    "cdrom0": null
  },
  "boot": ["hdd0", "cdrom0"],
  "scripts": {
    "install": "freedos-1.4-plain-install",
    "verify": "freedos-1.4-verify"
  }
}
```

## Using blueprints

```powershell
# Create a machine from a blueprint
rlq --blueprint freedos-1.4-plain create

# Start it
rlq --blueprint freedos-1.4-plain start

# Run a script
rlq --blueprint freedos-1.4-plain script install

# Stop it
rlq --blueprint freedos-1.4-plain stop

# Destroy it
rlq --blueprint freedos-1.4-plain --machine 1 destroy
```

## Machine lifecycle

Machines live under `cache/machines/<blueprint>-<n>/`. Each machine has:
- `reliquary-machine.json` - The resolved state document
- `drives/` - The machine's drive images
- `runs/` - Run records (transcripts, screenshots, outputs)
- `vm.json` - Active VM identity and port (when running)
- `qemu-stderr.log` - QEMU diagnostics

For the complete blueprint specification (including unimplemented fields), see [planning/design/machine-blueprint.md](../planning/design/machine-blueprint.md).
