<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# CLI reference

> **Descriptive.** The authoritative definition of the CLI is
> [docs/spec/cli.md](spec/cli.md). Where this reference disagrees
> with it, this reference is wrong.

This is the complete reference for the `rlq` command-line interface
(also available as `reliquary`). Every command name matches its
Python API function name, dash-separated instead of underscored
(`create-machine` corresponds to `create_machine`). Flags may appear
before or after the command word.

## Global options

Six flags set Reliquary's working directories. Each one can also be
set with an environment variable, and an explicit flag always wins
over that; any directory that isn't set by either one gets derived
from the others that are. The home directory's variable is
`RELIQUARY_HOME`; the other five follow the pattern
`RELIQUARY_<NAME>_DIR`.

- `--home-dir <path>` - The Reliquary home (default:
  `Documents/reliquary`, falling back to `~/reliquary`)
- `--blueprints-dir <path>` - Where blueprints (media included) are
  resolved from and seeded to; searched recursively by file
  extension (default: `<home>/blueprints`)
- `--scripts-dir <path>` - Where scripts are resolved from and
  seeded to; searched recursively (default: `<home>/scripts`)
- `--cache-dir <path>` - The cache directory root, which can always
  be regenerated (default: `<home>/cache`)
- `--media-dir <path>` - Cached media payloads (default:
  `<cache>/media`)
- `--machines-dir <path>` - Where machines are materialized
  (default: `<cache>/machines`)
- `--blueprint <name>` - Select a blueprint's sole machine, or
  name the blueprint for `create-machine` / `list-*`
- `--machine <id>` - Select a machine by its full id
  (`<blueprint>-<n>`), written out exactly — no prefix matching, and
  you can't pass just the number
- `--platform <name>` - Guest platform adapter (default: `dos`)
- `--timeout <seconds>` - Default timeout for commands
- `--json` - Print the command's result as a single JSON document on
  stdout: exactly what the corresponding Python API function
  returns (a function with no return value prints `{}`). Diagnostics
  still go to stderr, and exit codes don't change. Commands that
  stream progress (`run-script`, `fetch-media`) reject `--json` —
  their machine-readable form is `--progress jsonl` instead.
  `run-script --dry-run` doesn't stream, though: a dry-run plan is
  just a document, so it takes `--json` like any other result.
- `--progress (auto | pretty | plain | jsonl)` - Controls the live
  progress display, only on commands that stream progress
  (`run-script`, `fetch-media`). Refused under `run-script
  --dry-run`, since a dry run has no stream to render. See
  [Live progress](#live-progress) below.
- `--version` - Show version and exit

`--display` is accepted by both `start-machine` and `run-script`. As
noted above, flags may appear before or after the command word.

`--blueprint` and `--machine` are mutually exclusive.

## Output, exit codes, and live progress

**The result goes to stdout; everything else goes to stderr.** A
command that returns a value prints exactly that value's plain-text
rendering to stdout — the same value `--json` would serialize — so
ids, paths, and tables all pipe cleanly with no extra flags needed.
Narration, warnings, prompts, progress, and error reports all go to
stderr instead. Color is only ever printed to an actual terminal,
and never when `NO_COLOR` is set.

### Exit codes

| code | meaning |
|---|---|
| `0` | success |
| `1` | a fault — Reliquary's own, never a mistake of yours |
| `2` | STATIC ERROR — your input is illegal on its face |
| `3` | PREFLIGHT ERROR — your input is legal; the world does not satisfy it |
| `4` | RUN FAILURE — the operation started and failed |
| `5` | cancelled — Ctrl-C ended the run at an event boundary |

**These exit codes aren't only used for script runs.** `2`, `3`, and
`4` were originally named for the tiers of a script run, but they
mean the same thing on every command: a malformed blueprint exits
`2`, naming a machine that doesn't exist exits `3`, and a media
fetch that fails partway through exits `4`. Asking for a capability
this build hasn't implemented yet also exits `3` — the request
itself is legal, and "the world" that doesn't satisfy it includes
what this particular build happens to implement.

Exit code `1` never means you did something wrong. It means
Reliquary detected something broken in its own internal
assumptions, or hit an outright bug — and when it's a bug, it
prints a traceback along with the exit code.

Cancelled (exit code `5`) is deliberately neither a success nor a
failure. Pressing Ctrl-C on a foreground run just requests a stop:
the run finishes whatever it's currently doing (an input already in
flight completes), reports a `cancelled` terminal event, and leaves
the machine exactly as it was — nothing gets torn down.

### Live progress

`--progress` controls how a run or a fetch reports itself while
it's happening. Nothing gets written to disk — this is a live
output stream, returned directly to whoever started the run.

- `auto` (the default) — `pretty` when stderr is an actual
  terminal, otherwise `plain`.
- `pretty` — a single line that updates in place, showing elapsed
  time against its limit. Forces terminal-style rendering even
  where `auto` wouldn't (for example, a CI log that renders ANSI,
  or a pager).
- `plain` — one line per event, plus a periodic heartbeat — meant
  for a redirected log file.
- `jsonl` — **stdout carries the run's event stream as JSON Lines,
  and nothing else.** Each line has `seq`, `time`, `elapsed`,
  `kind`, and fields specific to that kind of event; the last line
  is the terminal event, which is the machine-readable result.
  Diagnostics still go to stderr.

`plain` and `jsonl` never prompt interactively: a property that no
source can answer is a PREFLIGHT ERROR raised before the machine
even starts, so an automated program can never hang waiting on a
question it has no way to see.

Anything reading the `jsonl` stream should ignore event kinds and
fields it doesn't recognize — new ones get added to the stream over
time, but existing ones never change meaning.

## Machine lifecycle commands

### `rlq create-machine --blueprint NAME`

Create a new machine from a blueprint. If any media the machine
attaches has its location given as a `${key}` property reference,
that key gets resolved before the machine is materialized — checked
in order from `--property KEY=VALUE`, a blueprint parameter,
`RELIQUARY_PROPERTY_<KEY>`, the properties file
(`--properties PATH`), or an interactive prompt. This lets a
blueprint name a non-redistributable ISO as `${windows.iso}`, with
each host supplying its own path or URL. The **resolved** location
gets recorded in the machine's state; `start` never resolves it
again later. If no source can answer a key, the create fails before
any drive gets materialized. A resolved value that turns out to
itself be a reference is rejected — a location only resolves once,
it doesn't chain through multiple references. `recreate-machine`
and `apply-blueprint` accept the same `--property` / `--properties`
flags.

`--dry-run` reports what a `create-machine` would do without
actually doing any of it: nothing gets seeded, fetched, locked, or
written, and it never prompts for anything. It prints the machine
id it would allocate, the backend it would run on, each drive's
resolved plan, and each media's status as `cached`,
`would-download`, `would-extract`, `local-present`, or `unbound` —
media get resolved, but never actually fetched or hashed. It fails
wherever a real create would fail, so a nonzero exit code is the
verdict on whether the create would have worked.

`--backend NAME` overrides the blueprint's `backend` field, pinning
the assignment at materialization time — the named backend has to
be both available and capable on this host, and the command fails
if it's either. With `--dry-run`, the question changes to whether
the blueprint *would* work on that backend, so only its capability
matters and it doesn't need to actually be installed on this host —
if it's not installed, that's reported, not treated as a failure.

### `rlq start-machine (--blueprint NAME | --machine ID) [--display]`

Start a machine. You have to give a selector (`--blueprint` or
`--machine`). Returns as soon as QEMU is up and running.

### `rlq stop-machine [ID] (--blueprint NAME | --machine ID)`

Stop a running machine. You can give the machine id as a plain
positional argument instead — `rlq stop-machine freedos-0` is
shorthand for `rlq stop-machine --machine freedos-0`.

### `rlq restart-machine [ID] (--blueprint NAME | --machine ID) [--display]`

Stop the machine if it's running, then start it — this happens as
one operation, not two, holding the per-machine lock the whole time
so nothing else can start it or change its media in between. If the
machine is already stopped, this just starts it. You can give the
machine id as a plain positional argument instead —
`rlq restart-machine freedos-0` is shorthand for
`rlq restart-machine --machine freedos-0`.

### `rlq destroy-machine [ID] (--blueprint NAME | --machine ID)`

Destroy a machine, stopping it first if it's running — the
per-machine lock stays held across both steps, just like
`restart-machine`. You can give the machine id as a plain
positional argument instead — `rlq destroy-machine freedos-0` is
shorthand for `rlq destroy-machine --machine freedos-0`. This frees
the machine number for reuse.

### `rlq recreate-machine (--blueprint NAME | --machine ID)`

Destroy a machine and recreate it under the same id — exactly
`destroy-machine` followed by `create-machine`. The blueprint gets
resolved fresh, so drives regenerate the way they're currently
declared.

### `rlq apply-blueprint (--blueprint NAME | --machine ID)`

Bring the current blueprint into a **stopped** machine, and bring a
machine that's diverged (say, from a script) back to its blueprint
shape. Changes the machine can absorb without rebuilding anything —
memory, CPU count, boot order, control planes, metadata, drives
added, removed, re-pointed, or left empty, and re-fetched `use`
media — get applied, and the baseline digest gets re-recorded. A
changed `size` or `materialize` on a media image that's already
been materialized causes this to refuse (use `recreate-machine`
instead).

### `rlq get-machine-dir (--blueprint NAME | --machine ID)`

Print the machine's cache directory as an absolute path — this is
how you exchange files with a machine outside its normal drives.
Works in any phase, and doesn't touch anything.

### `rlq list-machines [--blueprint NAME]`

List all machines, optionally filtered by blueprint.

### `rlq list-blueprints`

List your own blueprints — the ones in the `blueprints` directory —
with each one's path. This only covers your own: the built-in
library is a separate set with its own command below, and no single
listing covers both.

### `rlq list-codex`

List the built-in library's blueprints by name. None of your own
blueprints show up here — since you ran `list-codex` specifically,
that itself tells you where these came from, so there's no column
saying so. Each entry's description is shown in its table row, and
also included in the `--json` output.

Nothing ever resolves straight out of the library on its own: a
name your own directories don't hold is refused, and that refusal
tells you to run `rlq seed-blueprint <name>` if the library actually
has it.

### `rlq (seed-blueprint | seed-script) <name> [--only]`

Copy a built-in blueprint or script into your home directory. By
default, this also brings along everything it references (a
blueprint's scripts; media travel inside the blueprint file
itself); `--only` copies just the one named file. There's no
`seed-media` command: media are components inside a `.rlqb` file,
and get seeded along with whichever blueprint declares them.

### `rlq delete-blueprint <name>`

Remove a blueprint file (`.rlqb`) from your home directory. Refuses
to run while any machine created from that blueprint still exists,
naming their ids in the error — destroy them first. This never
deletes codex blueprints.

### `rlq delete-script <name>`

Remove a script file (`.rlqs`) from your home directory. Refuses to
run while any blueprint still refers to the script. This never
deletes codex scripts.

### `rlq list-scripts [--blueprint NAME]`

List scripts, optionally filtered by blueprint.

## Script commands

### `rlq run-script <label> (--blueprint NAME | --machine ID) [--display] [--progress MODE]`

Run a script against a blueprint's machine. This resolves the
blueprint, creates a machine if one doesn't already exist, and runs
the script, streaming its progress live as it goes.

**The run returns its output and stores nothing.** There's no run
directory, no saved transcript, and no commands for managing past
runs — the event stream is rendered however `--progress` asks and
is gone as soon as the run ends. Keep a copy by redirecting
`--progress jsonl` to a file, or by reading the stream returned from
the `run_script()` Python function. The run's actual *product* is
yours to keep — the value you read back with `get-machine-var`, the
image you swapped out, the results directory the guest wrote
into — and Reliquary doesn't interpret any of it.

A script declares the properties it needs; each one is resolved
before the machine starts, from the first of these sources that
answers it:

1. `--property KEY=VALUE` — an answer given for this specific run
   (repeatable; never usable for a secret — a command-line argument
   isn't a credential store).
2. a **blueprint parameter** — a value the blueprint fixes for its
   machines, or a `{"property": "<key>"}` redirect pointing at a
   different key.
3. `RELIQUARY_PROPERTY_<KEY>` — a value from an environment variable
   (the way to inject one from CI); the key is uppercased, with
   `.`, `-`, and `_` all mapped to `_`.
4. the **properties file** — `user.properties`, or the file named by
   `--properties PATH`; a secret's value is read from the host's
   credential store.
5. an **interactive prompt** — only when running on a terminal, once
   per key that's still unresolved. Without a terminal, an
   unresolved property fails before the machine even starts, so an
   automated program never hangs waiting on a prompt it can't see.

A `secret` property can only be expanded inside `enter` and `type`
statements; its actual value is kept out of the event stream and
out of diagnostics (shown as `«secret»` instead). Once a secret has
reached the guest, automatic failure screenshots are suppressed for
the rest of that run. `--properties PATH` selects which file to
read properties from, exactly like it does for the property
commands above.

When a run fails, the report names what was still pending, which
timer expired and where it came from, the path taken through the
script's phase graph along with how many times each phase was
revisited, the screen row that came closest to matching, an
automatic screenshot, and a suggested next command to try.

### `rlq run-script <name> --dry-run [--blueprint NAME | --machine ID]`

Parse and statically check a script, then print its resolved timing
plan (each observation's effective timeout, each guest-input
statement's effective pacing, and which scope supplied each one),
the source that would supply each declared property (a flag, a
blueprint parameter, the environment, the properties file, or a
prompt — never the actual value), and how many statements can't be
statically guaranteed to run. This is read-only: it seeds nothing,
creates no machine, runs no guest step, never prompts, and never
reads a secret's actual value.

**This is the one command where the selector is optional**, because
whether you give one decides which level of checking you get.
Without a selector, `<name>` has to be a bare script filename stem,
and every general legality rule applies. With `--blueprint` or
`--machine`, `<name>` can instead be a label from the blueprint's
scripts map, and the machine-specific rules also apply, including
checking media-slot targets ahead of time. Static errors exit with
code 2.

`--dry-run` returns a document instead of a stream, so `--json` can
print it, and `--progress` and `--display` are both refused.

## Media and cache

### `rlq list-media`

List media names that can be resolved from the active source (the
media specs across all its `.rlqb` files) — this only shows your
own. The library's media are components inside blueprints you
haven't seeded yet, and since there's no `seed-media` command,
nothing lists parts that can't be ordered on their own anyway.

### `rlq fetch-media <name> [--progress MODE]`

Resolve a media by name, and fetch and verify its payload into the
cache. This streams progress, using the same `--progress`
vocabulary a script run does: the transfer and verification report
live, with byte totals shown only when the source provides one —
hashing and extraction just report elapsed time, and each mirror
attempt shows up as its own event.

### `rlq clean-media [<name>]`

Delete cached payloads from `cache/media/`. With no argument, this
is blunt: everything in the cache goes. The cache only ever holds
things Reliquary can fetch or derive again, so nothing in it is
irreplaceable — a file you supplied yourself stays wherever you keep
it and is never copied into the cache in the first place. Anything
a running machine currently has open is skipped. Name a specific
media to delete just that one.

### `rlq prune-media [--dry-run]`

Delete cached payloads that nothing in the active scope still
needs: anything your namespace can still attach stays, and anything
that only existed to produce that gets deleted. After an install,
for example, the extracted ISO stays, but the zip file it was
extracted from doesn't — re-deriving that intermediate file is only
one download away, and it's usually the larger of the two files
anyway. `--dry-run` reports what would be deleted, without actually
touching anything.

### `rlq add-media <name> <file>`

Declare a media entry for a file you already have. Codex blueprints
for commercial systems ship with a pinned hash but no URL —
Reliquary has no right to redistribute a Windows ISO — so they just
name the build their scripts are written for, and leave it to you
to supply the actual file.

This writes a `blueprints/<name>.rlqb` file that declares the media,
pointing at your file and pinned to its SHA-256 hash, which it
computes for you. The file itself isn't copied or moved — the
blueprint just points at it wherever it already sits. Prints the
path of the new blueprint file.

What you get is an ordinary blueprint you own outright — edit it
freely, and if its pinned hash needs to differ from the codex's own
(say, a different edition, or your own disc rip), that's entirely
up to your copy. `add-media` refuses to overwrite an existing
blueprint of the same name.

### `rlq insert-media <slot> (<media> | --file PATH) (--blueprint NAME | --machine ID)`

### `rlq eject-media <slot> (--blueprint NAME | --machine ID)`

Insert or eject removable media (floppy/cdrom slots). Works
whether the machine is running or stopped: on a running machine,
the change is applied live over QMP (something the guest will
actually notice); on a stopped machine, it takes effect at the next
`start`. Either way, it persists in the machine's state until a
later `insert`/`eject` or `apply-blueprint`.

`<media>` names a declared media, which gets fetched and
hash-verified like any other. `--file PATH` mounts **your own
image** instead: an unnamed medium, attached in place, mutable and
never hash-verified. Nothing gets copied and no hash gets pinned,
so you can rebuild the image between rounds and mount it again —
this is the fast agentless loop, with no reboot and no guest agent
needed (see [Iterating live](#iterating-against-a-live-machine)).

### `rlq set-boot-order <key>... (--blueprint NAME | --machine ID)`

Set the boot order on a **stopped** machine (this is the firmware's
own boot order, used at launch). It persists in the machine's
state until the next `set-boot-order` or `apply-blueprint`.

## Driving a machine from a program

This section covers the mechanics of an automation loop: send work
in, run it, read the result back out, repeat. Reliquary just moves
the data — it doesn't interpret what it means.

### `rlq wait-machine-var <key> [<value>] (--blueprint NAME | --machine ID)`

Poll for a machine variable until it appears, and print it.
`--timeout SECONDS` (default 120) and `--interval SECONDS` (default
1) bound how long and how often it polls; leave out `<value>` to
wait for the variable to be set to anything at all.

This is for the case a plain read can't handle: **something else is
setting the variable.** A `run-script` run blocks until it
finishes, so its variables are already final by the time it
returns — check those with `rlq run-script … --expect key=value`
instead of waiting for them. A wait is for a variable set by a run
happening on another thread, or one you're watching rather than
driving yourself. An expired wait exits `4`; the Python equivalent
raises `WaitExpired`, which is both a `RunFailure` and a Python
`TimeoutError`, so code holding the polling loop can simply try
again.

### `rlq get-machine-var <key> (--blueprint NAME | --machine ID)`

Read a machine variable that a script set with its `set`
statement — this is the channel a script uses to hand a small value
back to the host. Prints the value, or prints nothing at all if
it's unset (`null` under `--json`); either way the command
succeeds, which is exactly what makes polling in a plain loop work.

Variables get cleared on every `start`, so this always reports what
the *current* boot has produced. The keys are yours to choose,
except for the reserved `rlq` and `reliquary` namespaces.

**This is also how readiness checks work.** Reliquary doesn't ship
a built-in readiness script — you write your own ready script that
sets a variable as its last step, and poll `get-machine-var` until
that variable shows up. What "ready" actually means is up to
whatever you're building, not up to Reliquary.

```powershell
# in your script:  set ready "yes"
rlq get-machine-var ready --machine rig-0
```

### Moving files across the boundary

**Reliquary itself doesn't move files for you.** It doesn't put
files onto a machine's drives or shares, doesn't read any back, and
never tells you which drive letter the guest assigned to a volume —
whatever's inside one is yours to open with your own tools. What
Reliquary supplies is the drives and shares a file can cross on, and
there are three ways to do it:

- **A share.** A `share` device whose media is a host directory
  presents that directory to the guest for as long as the machine
  runs (F68): you write files into it and the guest reads them, or
  the guest writes and you read them back on your side. The only
  model that actually renders today is `vvfat`, and QEMU takes a
  snapshot of the directory when the machine starts, so with it the
  machine has to be stopped for a change to become visible, in either
  direction.
- **A whole image, swapped live** — `insert-media --file`, below.
- **The machine directory itself** — `rlq get-machine-dir`. While
  the machine is stopped, its drives and shares are just plain
  files: a share *is* its host directory, and an image drive is a
  raw or qcow2 file, which any disk-image library can open.

```powershell
# the exchange directory is declared in the blueprint as a share
copy .uild\TEST.EXE .\exchangerlq start-machine --machine rig-0
rlq run-script test --machine rig-0
rlq stop-machine --machine rig-0
type .\exchange\RESULT.TXT
```


### Iterating against a live machine

When rebooting between rounds is the bottleneck, swap the medium
instead. `insert-media --file` mounts an image you built yourself;
the guest sees the media change live, and ejecting it flushes its
writes back to that same file. This works with whole images, not
single files, and building and reading those images is up to your
own tools.

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

**Mount the first image before starting the machine, and keep every
round the exact same size.** A floppy drive's geometry gets fixed
when the backend attaches its medium at launch, and a live media
change doesn't revise that — a slot that started out empty takes
the backend's own default geometry, and an image of a different
size would reach the guest as read and write errors, not as a new,
differently sized disk. Reliquary records the size the drive
launched with, and refuses a mismatched image rather than hand you
a broken drive.

## User properties

Values a script uses without them being written directly into it —
a registered owner's name, a login name, a product key — live in
`<home>/user.properties`, a flat file of `key = value` lines that
belongs to you, not to any machine or script. Reliquary edits this
file *surgically*: your comments, blank lines, and the ordering of
everything else survive every command below untouched.

Keys are dot-separated segments of ASCII letters, digits, `_` and
`-`, and each segment has to start with a letter. The `rlq` and
`reliquary` namespaces are reserved for Reliquary's own facts.
Values are just the trimmed remainder of the line, written
verbatim — no quoting, no escape sequences, no line continuations
(despite the file extension, this isn't the Java properties
format). A value that starts with `@` names a value *kind*:
`@secret` is the marker for a secret, and a literal leading `@`
character is written as `@@`.

```properties
# reliquary user properties
identity.full-name = Paul Galbraith
identity.preferred-username = paul

# the value lives in the host credential store, not here
accounts.default-password = @secret
```

Every command below accepts `--properties PATH`, which **replaces**
your home directory's properties file for that one invocation,
rather than merging with it. Pointing it at a file committed to
your project makes a run self-contained — nothing from your
personal properties file can reach it. The `RELIQUARY_PROPERTIES`
environment variable selects a file the same way.

### `rlq list-properties [PREFIX]`

List keys with their values, sorted. A secret shows up as
`@secret`, never its actual value. `PREFIX` limits the results to
that key and its dotted descendants — this matches a namespace, not
just a raw string prefix, so `products.windows-98` matches
`products.windows-98.install-key` but not `products.windows-98-extra`.
A secret whose credential is missing on this host gets reported as
a warning on stderr, but the listing itself doesn't change because
of it.

### `rlq get-property <key>`

Print one value. A secret prints only its kind.

### `rlq set-property <key> <value>`

Create or replace an ordinary property, rewriting or adding only
that one key's line. Changing a property between ordinary and
secret requires running `unset-property` first — so a single
command can never accidentally downgrade a secret to a plaintext
value.

### `rlq set-property <key> --secret`

Store a secret. The value never appears on the command line
itself — process listings and shell history aren't credential
stores — so there's deliberately no value argument to this command.
On a terminal, you get prompted for it without the input being
echoed back; otherwise, the value is read from stdin until EOF,
with one trailing newline stripped, which keeps the CLI fully
usable from a program:

```powershell
"swordfish" | rlq set-property accounts.default-password --secret
```

The actual value goes into the host's credential store, and only
the `@secret` marker gets written to the properties file. Secrets
are scoped by the absolute path of whichever properties file holds
the marker, so a `--properties` file and your home file never share
a credential — and copying a properties file elsewhere copies the
names and markers, but not the underlying credentials.

### `rlq unset-property <key>`

Remove a property, leaving the rest of the file untouched. For a
secret, this removes both the marker and its stored credential —
and it's also how you clean up an orphaned credential (see below).

A malformed properties file gets reported with its path and line
number, and is never left partly rewritten.

**There's no plaintext fallback.** If this host has no usable
credential store, storing or reading a secret fails outright rather
than falling back to writing it into the file. Updates are ordered
so an interruption can never leave behind a marker whose credential
doesn't actually exist: setting a secret writes the credential
first and the marker second, and removing one deletes the marker
first. The only thing that can be left behind is an *orphaned
credential* — stored, but with no marker pointing at it — which a
later, ordinary `set-property` on that key refuses to write over,
telling you to run `unset-property` to clear it first.

> **Not yet:** actually binding these properties into a script
> run — the layered sources, how they're declared, and the runtime
> rules for secrets — is coming with the rest of milestone 8
> (`docs/spec/script-properties.md`).

## Keyboard and command input

These guest-console commands match the verbs in the script
language. Select a machine with `--blueprint` / `--machine`, like
every other command — the actual connection behind it belongs to
the machine's backend adapter, and is never addressed directly.

### `rlq type TEXT`

Type text with no trailing Enter.

### `rlq enter LINE`

Type a line and press Enter.

### `rlq press KEY [KEY ...]`

Send one or more portable key names (and `+`-joined chords) from the
script language's vocabulary.

### `rlq exec COMMAND [--timeout SECONDS] [--check]`

Type a command into a running guest, wait for the DOS prompt to
come back, and **print the text the command produced.** This is the
one-shot member of the run family — it returns its output exactly
the way `run-script` does, and stores nothing. Python equivalent:
`exec(command, *, machine=, blueprint=, timeout=120, check=False)`,
which returns those same rows.

There's no agent involved, so the output captured is just whatever
the command left on the visible 80x25 screen — a command whose
output scrolls past a full screen leaves only its tail visible.
When you need more than that, have the guest write a file to a
drive you can read from the host, or have it set a machine variable
instead. Reliquary doesn't interpret any of this output.

`--check` answers a question the output alone can't: **did the
command actually work?** For a setup command — loading a driver or
a TSR — there's normally no output at all, and success is
everything, so without `--check` a success and a failure look
identical. With `--check`, a command that signalled failure makes
`exec` exit `4`, naming the command — and the output still gets
printed regardless:

```powershell
rlq exec "D:\DRIVER.EXE" --check --machine driver-rig-0
```

On DOS, this works by running an `IF ERRORLEVEL 1` probe afterward,
with a sentinel value that Reliquary itself composes and reads
back — its own text, not the guest's. That costs one extra command
at the prompt, which is why it's opt-in, and it can only catch
commands that **actually ran** and signalled failure — a mistyped
command leaves ERRORLEVEL untouched and reads as a success. See
[cli.md](spec/cli.md) for the authoritative details.

### `rlq select ITEM [--exclude TEXT]`

Select an entry in a cursor-key driven text menu.

## Reading the guest

### `rlq screen`

Print the current 80-by-25 text screen.

### `rlq wait CONDITION`

Wait for the script language's `wait` condition: plain text is
matched literally (after normalizing) within one screen row,
`/regex/` is a regular expression, and `machine=stopped` waits for
the machine to power off. A match only counts once the screen has
settled and stopped changing. Exits with code `4` if it times out.

### `rlq screenshot [NAME]`

Take a screenshot saved as `<home>/screenshots/<name>.png`.

## QEMU monitor access

### `rlq hmp "COMMAND"`

Send a raw QEMU human-monitor command.

For more examples and usage patterns, see [README.md](../README.md).
Agentless DOS automation is covered in
[DOS automation](dos-automation.md).
