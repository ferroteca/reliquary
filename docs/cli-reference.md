<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# CLI reference

This is the complete reference for the `rlq` command-line interface
(alias: `reliquary`). Every command is its API twin's name,
dash-separated (`create-machine` ↔ `create_machine`); flags may
appear before or after the command word.

## Global options

- `--home <path>` - Override the reliquary home directory
- `--cache <path>` - Override the cache directory (default:
  `<home>/cache`)
- `--blueprint <name>` - Select a blueprint's sole machine, or
  name the blueprint for `create-machine` / `list-*`
- `--machine <id>` - Select a machine by full id
  (`<blueprint>-<n>`), exactly — no prefix matching and no
  bare-number form
- `--port <n>` - QMP port (legacy root-home interaction and
  bare `start-machine` / `stop-machine`)
- `--platform <name>` - Guest platform adapter (default: `dos`)
- `--qemu <path>` - Path to the QEMU binary
- `--timeout <seconds>` - Default timeout for commands
- `--version` - Show version and exit

`--display` is accepted on `start-machine` and `run-script`.

`--blueprint` and `--machine` are mutually exclusive.

## Machine lifecycle commands

### `rlq create-machine --blueprint NAME`

Create a new machine from a blueprint.

### `rlq start-machine (--blueprint NAME | --machine ID) [--display]`

Start a machine. Returns when QEMU is ready. Without a selector,
loads the legacy root-home `machine.json` path.

### `rlq stop-machine (--blueprint NAME | --machine ID)`

Stop a running machine. Without a selector, stops the legacy
root-home VM.

### `rlq destroy-machine (--blueprint NAME | --machine ID)`

Destroy a machine. Frees the machine number for reuse.

### `rlq recreate-machine (--blueprint NAME | --machine ID)`

Destroy a machine and recreate it under the same id — exactly
`destroy-machine` + `create-machine`. The current blueprint is
re-resolved, so drives regenerate as declared.

### `rlq get-machine-dir (--blueprint NAME | --machine ID)`

Print the machine's cache directory as an absolute path — the door
to out-of-band file exchange (valid in any phase, touching
nothing).

### `rlq list-machines [--blueprint NAME]`

List all machines, optionally filtered by blueprint.

### `rlq list-blueprints [--builtin]`

List blueprints. With `--builtin`, list only built-in blueprints.

### `rlq delete-blueprint <name>`

Remove the home blueprint file (``.rlqb`` or legacy ``.json``).
Refuses while any machine of that blueprint exists, naming their
ids — destroy them first. Never deletes package builtins.

### `rlq list-scripts [--blueprint NAME]`

List scripts, optionally filtered by blueprint.

## Script commands

### `rlq run-script <label> (--blueprint NAME | --machine ID) [--display]`

Run a script against a blueprint's machine. Resolves the blueprint,
creates a machine if none exists, runs the script, and records the run.

### `rlq check-script <name> [--blueprint NAME | --machine ID]`

Parse and statically check a script; print its resolved timing plan
(each observation's effective timeout and source scope). Read-only:
does not seed the home, create a machine, or run guest steps. Without
a selector, `<name>` is a bare script stem (home `scripts/` or a
builtin). With `--blueprint` or `--machine`, `<name>` may be a
blueprint scripts-map label. With a machine, media-slot preflight
runs as well. Static errors exit 2.

## Media and cache

### `rlq list-media [--builtin]`

List media item names from the home ``media/`` library. With
``--builtin``, list package codex items instead.

### `rlq delete-media <name>`

Remove the home definition file that defines media item ``name``.
Refuses while any machine drive still references an item from that
definition. Never deletes package builtins. Does not reclaim
``cache/media/`` payloads — use ``clean-media`` for that.

### `rlq fetch-media <name>`

Fetch and verify a named media item into the cache.

### `rlq clean-downloads` / `rlq clean-media`

Reclaim files under `cache/downloads/` or `cache/media/`.

### `rlq insert-media <slot> <media> (--blueprint NAME | --machine ID)`

### `rlq eject-media <slot> (--blueprint NAME | --machine ID)`

### `rlq set-boot-order <key>... (--blueprint NAME | --machine ID)`

Persistent media and boot-order changes on a stopped machine.

## Keyboard and command input

Guest-console verbs match the script language. Select a machine with
`--blueprint` / `--machine`, or pass legacy `--port`.

### `rlq type TEXT`

Type text with no trailing Enter.

### `rlq enter LINE`

Type a line and press Enter.

### `rlq press KEY [KEY ...]`

Send portable key names (and `+` chords) from the script vocabulary.

### `rlq exec COMMAND [--timeout SECONDS]`

Enter a command and wait for the DOS prompt to return.

### `rlq select ITEM [--exclude TEXT]`

Select an entry in a cursor-key driven text menu.

## Reading the guest

### `rlq screen`

Print the current 80-by-25 text screen.

### `rlq wait REGEX`

Wait until the screen contains a regular expression.

### `rlq screenshot [NAME]`

Take a screenshot saved as `<home>/screenshots/<name>.png`.

## QEMU monitor access

### `rlq hmp "COMMAND"`

Send a raw QEMU human-monitor command.

For more examples and usage patterns, see [README.md](../README.md).
Agentless DOS automation is covered in
[DOS automation](dos-automation.md).
