<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# CLI reference

> **Descriptive.** The CLI's norm is
> [docs/spec/cli.md](spec/cli.md); where this reference disagrees
> with it, this reference has the bug.

This is the complete reference for the `rlq` command-line interface
(alias: `reliquary`). Every command is its API twin's name,
dash-separated (`create-machine` ↔ `create_machine`); flags may
appear before or after the command word.

## Global options

Six flags place Reliquary's working directories. Each is also
settable as `RELIQUARY_<NAME>_DIR` in the environment, an explicit
flag winning; what none of them names derives from what does.

- `--home-dir <path>` - The Reliquary home (default:
  `Documents/reliquary`, falling back to `~/reliquary`)
- `--blueprints-dir <path>` - Where blueprints (media included)
  resolve from and seed to, walked recursively by extension
  (default: `<home>/blueprints`)
- `--scripts-dir <path>` - Where scripts resolve from and seed to,
  walked recursively (default: `<home>/scripts`)
- `--cache-dir <path>` - The regenerable cache root (default:
  `<home>/cache`)
- `--media-dir <path>` - Cached media payloads (default:
  `<cache>/media`)
- `--machines-dir <path>` - Machine materializations (default:
  `<cache>/machines`)
- `--no-autoseed` - Never fall back to the built-in codex; the
  directories above are the sole sources. Use it with
  `--blueprints-dir` / `--scripts-dir` for reproducible,
  project-scoped automation. `--autoseed` states the CLI default
  out loud
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
- `--progress (auto | pretty | plain | jsonl)` - Live rendering, on
  the stream-bearing commands (`run-script`, `fetch-media`) only.
  See [Live progress](#live-progress) below.
- `--version` - Show version and exit

`--display` is accepted on `start-machine` and `run-script`.
Flags may appear before or after the command word.

`--blueprint` and `--machine` are mutually exclusive.

## Output, exit codes, and live progress

**The result is stdout; everything else is stderr.** A command that
returns a value prints exactly that value's plain rendering on stdout
— the same thing `--json` serializes — so ids, paths, and tables pipe
clean with no flags. Narration, warnings, prompts, progress, and error
reports go to stderr. Colour is emitted only to a terminal and never
under `NO_COLOR`.

### Exit codes

| code | meaning |
|---|---|
| `0` | success |
| `1` | a fault — Reliquary's own, never a mistake of yours |
| `2` | STATIC ERROR — your input is illegal on its face |
| `3` | PREFLIGHT ERROR — your input is legal; the world does not satisfy it |
| `4` | RUN FAILURE — the operation started and failed |
| `5` | cancelled — Ctrl-C ended the run at an event boundary |

**These are not the script surface's codes alone.** `2`, `3` and `4`
were named for a script run's tiers and mean the same on every
command: a malformed blueprint is `2`, naming a machine that does not
exist is `3`, a media fetch that fails halfway is `4`. A capability
this build has not implemented is `3` — the request is legal and the
world, which includes what this build implements, does not satisfy
it.

`1` never means you got something wrong. It is Reliquary detecting a
broken invariant of its own, or an outright bug, and a bug prints a
traceback with it.

Cancelled is deliberately neither success nor failure. Ctrl-C on a
foreground run requests a stop; the run ends at the next event
boundary (an input already in flight completes), reports a
`cancelled` terminal event, and leaves the machine exactly as it
stands — nothing is torn down.

### Live progress

`--progress` selects how a run or a fetch reports itself while it
happens. Nothing is written to disk: the stream is live output, and
the run returns it to whoever started it.

- `auto` (default) — `pretty` when stderr is a terminal, else `plain`.
- `pretty` — an in-place live line with elapsed time against its
  limit. Forces the terminal rendering where `auto` would not (a CI
  log that renders ANSI, a pager).
- `plain` — one line per event plus a periodic heartbeat, for a
  redirected log.
- `jsonl` — **stdout carries the run's event stream as JSON Lines and
  nothing else.** Each line has `seq`, `time`, `elapsed`, `kind`, and
  the kind's own fields; the last line is the terminal event, which is
  the machine-readable result. Diagnostics stay on stderr.

`plain` and `jsonl` never prompt: a property no source answers is a
PREFLIGHT ERROR before the machine starts, so a program can never
hang on a question it cannot see.

Consumers of the `jsonl` stream should ignore event kinds and fields
they do not recognize — the stream grows additively.

## Machine lifecycle commands

### `rlq create-machine --blueprint NAME`

Create a new machine from a blueprint. If any media the machine
attaches is located by a `${key}` property reference, that key is
bound before materialization — from `--property KEY=VALUE`, a
blueprint parameter, `RELIQUARY_PROPERTY_<KEY>`, the properties file
(`--properties PATH`), or an interactive ask — so a blueprint can
name a non-redistributable ISO by `${windows.iso}` and each host
supplies its own path or URL. The **resolved** location is recorded
in the machine state; `start` never re-resolves it. A key that no
source answers fails the create before any drive is materialized. A
bound value that is itself a reference is refused — a location binds
once, it does not chain. `recreate-machine` and `apply-blueprint`
take the same `--property` / `--properties`.

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

### `rlq run-script <label> (--blueprint NAME | --machine ID) [--display] [--progress MODE]`

Run a script against a blueprint's machine. Resolves the blueprint,
creates a machine if none exists, and runs the script, streaming its
progress live.

**The run returns its output and stores nothing.** There is no run
directory, no saved transcript, and no run-management commands: the
event stream is rendered as `--progress` asks and is gone when the run
ends. Keep it by redirecting `--progress jsonl`, or take the returned
stream from the `run_script()` twin. The run's *product* is yours —
the file you pull back with `get-file`, the value you read with
`get-machine-var`, the image you swapped out — and Reliquary attaches
no meaning to any of it.

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
kept out of the event stream and diagnostics (shown as `«secret»`),
and once one reaches the guest, automatic failure screenshots are
suppressed for the rest of the run. `--properties PATH` selects the
file for binding, exactly as for the property commands above.

When a run fails, the report names what was pending, which clock
expired and the scope that supplied it, the route through the phase
graph with its revisit counts, the screen row that came nearest to
matching, an automatic screenshot, and the command to try next.

### `rlq check-script <name> [--blueprint NAME | --machine ID]`

Parse and statically check a script; print its resolved timing plan
(each observation's effective timeout, each guest-input verb's
effective pacing, and the scope that supplied each) and, for each
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

### `rlq fetch-media <name> [--progress MODE]`

Resolve a media by name and fetch and verify its payload into the
cache. Stream-bearing: transfer and verification report live under the
same `--progress` vocabulary a run uses, with byte totals only where
the source names one — hashing and extraction report elapsed time
alone, and each mirror attempt is its own event.

### `rlq clean-media [<name>]`

Reclaim cached payloads from `cache/media/`. With no argument it is
blunt: everything goes. The cache holds only what Reliquary can fetch
or derive again, so nothing there is irreplaceable — a file you
supplied yourself stays wherever you keep it and is never copied in.
Anything a running machine is holding open is skipped. Naming a media
evicts just that one.

### `rlq prune-media [--dry-run]`

Drop cached payloads outside the **attachment closure**: what the
active scope can still attach stays, and what only existed to produce
it goes. After an install, that means the extracted ISO stays and the
zip it came out of does not — re-deriving the husk is one download
away, and it is usually the larger file. `--dry-run` reports what
would go without touching anything.

### `rlq add-media <name> <file>`

Declare a media for a file you already have. Codex blueprints for
commercial systems ship pinned but without a URL — Reliquary has no
right to distribute a Windows ISO — so they name the build their
scripts target and leave you to supply it.

This writes `blueprints/<name>.rlqb` declaring that media, located at
your file and pinned to its SHA-256, which it computes for you. The
file is not copied or moved: the blueprint points at it where it sits.
Prints the blueprint path.

The result is an ordinary blueprint you own — edit it freely, and if
the pin needs to differ from the codex's (a different edition, your
own rip), that is your copy's business. `add-media` refuses to
overwrite an existing blueprint of that name.

### `rlq insert-media <slot> (<media> | --file PATH) (--blueprint NAME | --machine ID)`

### `rlq eject-media <slot> (--blueprint NAME | --machine ID)`

Insert or eject removable media (floppy/cdrom slots). Works
running or stopped: on a running machine the change is applied live
over QMP (a change the guest observes); on a stopped machine it is
present at the next `start`. Either way it persists in the machine
state until a later `insert`/`eject` or `apply-blueprint`.

`<media>` names a declared media, fetched and hash-verified like any
other. `--file PATH` mounts **your own image** instead: an anonymous
medium, attached in place, mutable and unverified. Nothing is copied
and no hash is pinned, so you can rebuild the image between rounds
and mount it again — the fast agentless loop, with no reboot and no
guest agent (see [Iterating live](#iterating-against-a-live-machine)).

### `rlq set-boot-order <key>... (--blueprint NAME | --machine ID)`

Set the boot order on a **stopped** machine (a launch-time firmware
order). Persists in the machine state until the next `set-boot-order`
or `apply-blueprint`.

## Driving a machine from a program

These are the mechanics for the loop an automating program runs:
put work in, run it, read the result out, iterate. Reliquary supplies
the transports and attaches no meaning to what travels through them.

### `rlq get-machine-var <key> (--blueprint NAME | --machine ID)`

Read a machine variable a script set with the `set` verb — the
script-to-host channel for a small value. Prints the value, or
nothing at all when it is unset (`null` under `--json`); either way
the command succeeds, which is what makes polling a plain loop.

Variables are cleared at each `start`, so one always reports what the
*current* boot produced. Keys are yours, except the reserved `rlq` and
`reliquary` namespaces.

**Readiness rides this.** Reliquary ships no readiness script: your
own ready script sets a variable as its last step, and you poll
`get-machine-var` until it appears. What "ready" means belongs to
whatever you are building, not to Reliquary.

```powershell
# in your script:  set ready "yes"
rlq get-machine-var ready --machine rig-0
```

### `rlq put-file <host-path> <guest-address> (--blueprint NAME | --machine ID)`

### `rlq get-file <guest-address> <host-path> (--blueprint NAME | --machine ID)`

Move one file across the guest boundary, addressed **the way the
guest names it** — `A:\TEST.EXE`, not an image file or a staging
directory. The drive-letter mapping comes from the machine's declared
platform and Reliquary's own drive assignment; nothing is inferred by
inspecting the guest.

Both are **stopped-only**, and the addressed drive must be a
directory-source drive: the backend snapshots that
directory when the drive is attached, so a change made while the
machine runs would be invisible to the guest, and a guest write is
not flushed until it stops. An image drive has no in-band route and
says so rather than pretending.

`put-file` prints the guest address it wrote; `get-file` prints the
host path.

```powershell
rlq stop-machine --machine rig-0
rlq put-file .\build\TEST.EXE "A:\TEST.EXE" --machine rig-0
rlq run-script test --machine rig-0
rlq stop-machine --machine rig-0
rlq get-file "A:\RESULT.TXT" .\out\result.txt --machine rig-0
```

### Iterating against a live machine

When a reboot per round is the bottleneck, swap the medium instead.
`insert-media --file` mounts an image you built; the guest sees the
media change live, and ejecting flushes its writes back to that same
file. Whole images rather than single files, and the images are
yours to build and read with your own tools.

```powershell
# build round-1.img yourself, then:
rlq stop-machine --machine rig-0
rlq insert-media floppy0 --file .\round-1.img --machine rig-0
rlq start-machine --machine rig-0
# from here every round is live:
rlq exec "A:\TEST.EXE" --machine rig-0
rlq eject-media floppy0 --machine rig-0
# read round-1.img host-side, rebuild it, and mount the next one
rlq insert-media floppy0 --file .\round-2.img --machine rig-0
```

**Mount the first image before starting, and keep every round the
same size.** A floppy drive's geometry is fixed when the backend
attaches its medium at launch, and a live change does not revise it:
a slot that was empty at start takes the backend's own default, and
a differently sized image would reach the guest as read and write
errors rather than as a new disk. Reliquary records the launched
size and refuses a mismatch rather than hand you a broken drive.

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
> (`docs/spec/script-properties.md`).

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

Enter a command in a running guest, wait for the DOS prompt to
return, and **print the text the command produced** — the run
family's one-shot member, returning its output exactly as
`run-script` does and storing nothing. Twin: `exec(command, *,
machine=, blueprint=, timeout=120)`, which returns those rows.

The capture is agentless, so the output is what the command left on
the visible 80x25 screen: a command that scrolls more than a
screenful leaves only its tail. When you need more than that, have
the guest write a file and take it with `get-file`, or set a machine
variable. Reliquary reads no meaning into any of it.

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
