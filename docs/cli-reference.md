<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# CLI reference

This is the complete reference for the `rlq` command-line interface
(alias: `reliquary`).

## Global options

- `--home <path>` - Override the reliquary home directory
- `--blueprint <name>` - Select a blueprint's sole machine, or combine
  with `--machine <n>`; names the blueprint for `create` / `list`
- `--machine <id|n>` - Select a machine by id (`<blueprint>-<n>`),
  unambiguous id prefix, or number with `--blueprint`
- `--port <n>` - QMP port (legacy interaction commands; lifecycle
  stores port per machine)
- `--platform <name>` - Guest platform adapter (default: `dos`)
- `--qemu <path>` - Path to the QEMU binary
- `--timeout <seconds>` - Default timeout for commands
- `--version` - Show version and exit

`--display` is not global: it is accepted on `start` and `script`.

## Machine lifecycle commands

### `rlq --blueprint NAME create`

Create a new machine from a blueprint.

### `rlq --blueprint NAME start [--display]`

Start a machine. Returns when QEMU is ready.

### `rlq --blueprint NAME stop`

Stop a running machine.

### `rlq --blueprint NAME --machine N destroy`

Destroy a machine. Frees the machine number for reuse.

### `rlq list machines [--blueprint NAME]`

List all machines, optionally filtered by blueprint.

### `rlq list blueprints [--builtin]`

List blueprints. With `--builtin`, list only built-in blueprints.

### `rlq list scripts [--blueprint NAME]`

List scripts, optionally filtered by blueprint.

## Script commands

### `rlq --blueprint NAME script <label> [--display]`

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

## Legacy root-home commands

### `rlq start [--display] [QEMU_ARGS...]`

Start QEMU using the legacy root-home path. Loads configuration from
`<home>/machine.json` if present. Extra arguments after the known
options are passed to QEMU.

### `rlq stop`

Stop the active VM.

## Keyboard and command input

### `rlq type TEXT`

Type text followed by Enter.

### `rlq run COMMAND`

Type a command and wait for the prompt to return.

### `rlq keys KEY [KEY ...]`

Send raw QEMU key names (e.g., `down ret`).

### `rlq menu ITEM [--exclude TEXT]`

Select an entry in a cursor-key driven text menu.

## Reading the guest

### `rlq text`

Print the current 80-by-25 text screen.

### `rlq wait REGEX`

Wait until the screen contains a regular expression.

### `rlq screenshot [NAME]`

Take a screenshot saved as `<home>/screenshots/<name>.png`.

## QEMU monitor access

### `rlq hmp "COMMAND"`

Send a raw QEMU human-monitor command.

## Machine selection

- `--blueprint NAME` - Select a blueprint's sole machine
- `--machine NAME-N` - Select a specific machine by full id
- Combine `--blueprint NAME --machine N` for explicit selection

For more examples and usage patterns, see [README.md](../README.md).
Agentless DOS automation is covered in
[DOS automation](dos-automation.md).
