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

- `--home <path>` - Override the Reliquary home directory
- `--cache <path>` - Override the cache directory (default:
  `<home>/cache`)
- `--assets <dir>` - Resolve authored assets (blueprints, media
  included, and scripts) solely from
  this project root, walked recursively by extension — no home, no
  codex, no seeding. Its absence is home mode: the home's canonical
  `blueprints/` / `scripts/` folders, seeding missing names from the
  built-in codex. Use `--assets` for reproducible, project-scoped
  automation
- `--blueprint <name>` - Select a blueprint's sole machine, or
  name the blueprint for `create-machine` / `list-*`
- `--machine <id>` - Select a machine by full id
  (`<blueprint>-<n>`), exactly — no prefix matching and no
  bare-number form
- `--port <n>` - QMP port for direct guest-console interaction
  (`type` / `enter` / `press` / …) against a running machine by
  port instead of a selector
- `--platform <name>` - Guest platform adapter (default: `dos`)
- `--qemu <path>` - Path to the QEMU binary
- `--timeout <seconds>` - Default timeout for commands
- `--json` - Print the command's result as one JSON document on
  stdout: exactly what the command's API twin returns (a void twin
  prints `{}`). Diagnostics stay on stderr and exit codes are
  unchanged. Stream-bearing commands (`run-script`, `fetch-media`)
  reject `--json` — their machine-readable form is `--progress jsonl`.
- `--version` - Show version and exit

`--display` is accepted on `start-machine` and `run-script`.
Flags may appear before or after the command word.

`--blueprint` and `--machine` are mutually exclusive.

## Machine lifecycle commands

### `rlq create-machine --blueprint NAME`

Create a new machine from a blueprint.

### `rlq start-machine (--blueprint NAME | --machine ID) [--display]`

Start a machine (a selector is required). Returns when QEMU is
ready.

### `rlq stop-machine (--blueprint NAME | --machine ID)`

Stop a running machine (a selector is required).

### `rlq destroy-machine (--blueprint NAME | --machine ID)`

Destroy a machine. Frees the machine number for reuse.

### `rlq recreate-machine (--blueprint NAME | --machine ID)`

Destroy a machine and recreate it under the same id — exactly
`destroy-machine` + `create-machine`. The current blueprint is
re-resolved, so drives regenerate as declared.

### `rlq apply-blueprint (--blueprint NAME | --machine ID)`

Adopt the current blueprint into a **stopped** machine, and return
a script-diverged machine to its blueprint shape. Absorbable
changes — memory, cpus, boot order, control planes, metadata,
added/removed/re-pointed and empty drives, and re-fetched `use`
media — are applied and the baseline digest re-recorded; a changed
`size` or `materialize` on an already-materialized media image
fails closed (use `recreate-machine`).

### `rlq get-machine-dir (--blueprint NAME | --machine ID)`

Print the machine's cache directory as an absolute path — the door
to out-of-band file exchange (valid in any phase, touching
nothing).

### `rlq list-machines [--blueprint NAME]`

List all machines, optionally filtered by blueprint.

### `rlq list-blueprints [--builtin]`

List blueprints. With `--builtin`, list only built-in blueprints.

### `rlq search-blueprints [TERM]`

Search codex and home blueprints, printing name, provenance
(`yes` = built-in and not seeded, `seeded` = built-in copied into
the home, `user` = home-authored), platform, and description. The
term is matched case-insensitively against name, description, and
platform; omitted, everything is listed.

### `rlq (seed-blueprint | seed-script) <name> [--only]`

Copy a built-in artifact into the home. By default a blueprint or
script also brings its closure (referenced scripts; media travel
inside the blueprint itself); `--only` copies just the named file.
There is no `seed-media`: media are components inside a `.rlqb` and
are seeded with the blueprint that declares them.

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

A script declares the properties it consumes; each is bound before
the machine starts, from the first source that answers:

1. `--property KEY=VALUE` — the caller's answer for this run
   (repeatable; never a secret — argv is not a credential store).
2. a **blueprint parameter** — a value the blueprint fixes for its
   machines, or a `{"property": "<key>"}` redirect to another key.
3. `RELIQUARY_PROPERTY_<KEY>` — an environment value (the CI
   injection path); the key uppercases with `.`, `-`, `_` all
   mapped to `_`.
4. the **properties file** — `user.properties`, or the file named by
   `--properties PATH`; a secret is read from the credential store.
5. an **interactive ask** — only on a terminal, once per unresolved
   key. Without a terminal, an unresolved property fails before the
   machine starts, so a program never hangs on a hidden prompt.

A `secret` property expands only in `enter` and `type`; its value is
kept out of the transcript and diagnostics (shown as `«secret»`).
`--properties PATH` selects the file for binding, exactly as for the
property commands above.

### `rlq check-script <name> [--blueprint NAME | --machine ID]`

Parse and statically check a script; print its resolved timing plan
(each observation's effective timeout and source scope) and, for each
declared property, the source that would supply it — flag, blueprint
parameter, environment, properties file, or the ask — never its
value. Accepts the same `--property` and `--properties` as
`run-script`. Read-only: does not seed the home, create a machine,
run guest steps, prompt, or read a secret's value. Without a
selector, `<name>` is a bare script stem (home `scripts/` or a
builtin). With `--blueprint` or `--machine`, `<name>` may be a
blueprint scripts-map label. With a machine, media-slot preflight
runs as well. Static errors exit 2.

## Media and cache

### `rlq list-media [--builtin]`

List media names resolvable from the active source (the media specs
across its `.rlqb` files). With ``--builtin``, list package codex
media instead.

### `rlq fetch-media <name>`

Resolve a media by name and fetch and verify its payload into the
cache.

### `rlq clean-media [<name>]`

Reclaim cached payloads from `cache/media/`. With no argument it is
blunt: everything the project can fetch or derive again goes. A
**supplied** payload — one you put there with `add-media`, which
nothing can reproduce — is spared, and so is anything a running
machine is holding open. Naming a media evicts just that one,
whatever its provenance.

### `rlq prune-media [--dry-run]`

Drop cached payloads outside the **attachment closure**: what the
active scope can still attach stays, and what only existed to produce
it goes. After an install, that means the extracted ISO stays and the
zip it came out of does not — re-deriving the husk is one download
away, and it is usually the larger file. `--dry-run` reports what
would go without touching anything.

### `rlq add-media <name> <file>`

Supply a payload nothing can locate. A blueprint may pin a `sha256`
for media it cannot legally distribute; resolution fails closed until
someone provides the file. This copies it into the cache under the
media's own name, verified against the pin, so the blueprint never has
to be edited. The payload is recorded as **supplied** and is not
reclaimed unless you name it.

### `rlq insert-media <slot> <media> (--blueprint NAME | --machine ID)`

### `rlq eject-media <slot> (--blueprint NAME | --machine ID)`

Insert or eject removable media (floppy/cdrom slots). Works
running or stopped: on a running machine the change is applied live
over QMP (a change the guest observes); on a stopped machine it is
present at the next `start`. Either way it persists in the machine
state until a later `insert`/`eject` or `apply-blueprint`.

### `rlq set-boot-order <key>... (--blueprint NAME | --machine ID)`

Set the boot order on a **stopped** machine (a launch-time firmware
order). Persists in the machine state until the next `set-boot-order`
or `apply-blueprint`.

## User properties

Values scripts consume without embedding them — a registered owner,
a login name, a product key — live in `<home>/user.properties`, a
flat file of `key = value` lines that belongs to you, not to any
machine or script. Reliquary edits it *surgically*: your comments,
blank lines, and ordering survive every command below untouched.

Keys are dot-separated segments of ASCII letters, digits, `_` and
`-`, each starting with a letter. The `rlq` and `reliquary`
namespaces are reserved for Reliquary's own facts. Values are the
trimmed remainder of the line, verbatim — no quoting, no escapes,
no line continuations (despite the extension, this is not the Java
properties format). A value starting with `@` names a value *kind*:
`@secret` is a secret marker, and a literal leading `@` is written
`@@`.

```properties
# reliquary user properties
identity.full-name = Paul Galbraith
identity.preferred-username = paul

# the value lives in the host credential store, not here
accounts.default-password = @secret
```

Every command below accepts `--properties PATH`, which **replaces**
the home's file for that invocation rather than layering over it.
Pointing it at a project-committed file makes a run hermetic —
nothing from your personal file can reach it. The environment
variable `RELIQUARY_PROPERTIES` selects the same way.

### `rlq list-properties [PREFIX]`

List keys with their values, sorted. A secret shows as `@secret`,
never its value. `PREFIX` selects that key and its dotted
descendants — a namespace, not a raw string match, so
`products.windows-98` matches `products.windows-98.install-key`
but not `products.windows-98-extra`. A secret whose credential is
missing on this host is reported as a warning on stderr; the
listing itself is unchanged.

### `rlq get-property <key>`

Print one value. A secret prints only its kind.

### `rlq set-property <key> <value>`

Create or replace an ordinary property, rewriting or appending
only that key's line. Changing a property between ordinary and
secret requires `unset-property` first, so a secret can never be
downgraded to a plaintext value by one command.

### `rlq set-property <key> --secret`

Store a secret. The value never appears on the command line —
process listings and shell history are not credential stores — so
there is deliberately no value argument. On a terminal you are
prompted without echo; otherwise the value is read from stdin to
EOF with one trailing newline stripped, which keeps the CLI a
complete binding for programs:

```powershell
"swordfish" | rlq set-property accounts.default-password --secret
```

The value goes to the host credential store and only the `@secret`
marker is written to the file. Secrets are scoped by the absolute
path of the properties file holding the marker, so a `--properties`
file and your home file never share one, and copying a properties
file elsewhere copies names and markers but not credentials.

### `rlq unset-property <key>`

Remove a property, leaving the rest of the file as it was. For a
secret this removes both the marker and its credential — and it is
also the cleanup door for an orphaned credential (below).

A malformed properties file is reported with its path and line
number and is never partly rewritten.

**No plaintext fallback.** If this host has no usable credential
store, storing or reading a secret fails closed rather than
falling back to the file. Updates are ordered so an interruption
can never strand a marker whose credential Reliquary reported as
stored: the credential is written first and the marker second, and
on removal the marker goes first. The recoverable leftover is an
*orphaned credential* — stored, with no marker — which a later
ordinary `set-property` on that key refuses to write over, naming
`unset-property` as the way to clear it.

> **Not yet:** binding these properties into a script run — the
> layered sources, the declared derivation, and the runtime secret
> rules — arrives with the rest of milestone 8
> (`planning/design/script-properties.md`).

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
