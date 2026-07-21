<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# CLI

> **Status:** working document for brainstorming the command-line
> structure; expected to be short-lived. Settled decisions live in
> [ROADMAP.md](../ROADMAP.md) ("The CLI" and the milestones);
> concepts introduced here are documented durably in
> [codex.md](codex-design.md) (the codex,
> `pull`, naming conventions, provenance) and the
> [blueprint field reference](machine-blueprint-reference-design.md)
> (`name`, `description`, `scripts`).

Every command maps one-to-one onto a public Python call. The CLI
resolves `--blueprint` and `--machine` selectors; the API takes the
same identifiers. Nothing is CLI-only.

**Selection.** Machine-level verbs take a target selector:

- `--blueprint <name>` — selects that blueprint's machine when
  exactly one exists; fails listing candidate ids when several
  exist; fails suggesting `create` when none exist (except
  `script`, which creates one).
- `--machine <blueprint>-<n>` — the full machine id or any
  unambiguous prefix.
- `--blueprint <name> --machine <n>` — machine number `<n>` of that
  blueprint.

Blueprints are selected by name alone (`--blueprint <name>`, the
stem of the `<name>.rlqb` file the asset root supplies). Machine
ids are
`<blueprint>-<n>` (lowest free number, reused after destroy).

---

## Blueprints

Blueprint files describe a kind of machine. They live under
`blueprints/` alongside companion media definitions (`media/`) and
scripts (`scripts/`). Author them by hand, scaffold them with
`create blueprint`, or let reliquary extract them from its codex.

**The codex.** reliquary ships a set of blueprints, media
definitions, and scripts for popular open source operating systems.
In a source checkout these live as ordinary files under
`builtins/blueprints/`, `builtins/media/`, and
`builtins/scripts/`; when packaged for distribution they are bundled
in a zip archive within the reliquary package. Either way, when you
reference a codex artifact that doesn't yet exist in your home,
reliquary copies it out. From that point on it is an ordinary
user-owned file — edit it, delete it, version it. A file already
present in your home is never overwritten; the codex is a seed,
not a live resolution tier.

Deleting your copy is also how you refresh it: a file in your home
is never touched, but once you delete it yourself, the next
reference (or `pull`) extracts the current codex copy again. Orphaned
references — a blueprint naming a media definition or script you
removed — re-seed the same way.

This means the lazy path is often one command with zero files in
your home beforehand: `rlq --blueprint freedos-1.4
script install` extracts the blueprint, its media, and its scripts,
creates a machine, and runs the install — everything materialized on
first use.

### Named scripts

A blueprint may declare a `scripts` map — short labels that name
`.rlqs` script files. It may also carry optional `name` and
`description` fields for discovery:

```json
{
  "name": "FreeDOS 1.4 — Plain DOS system",
  "description": "Installs FreeDOS 1.4 onto a blank hard disk. Selects the Plain DOS system package set.",
  "platform": "dos",
  "scripts": {
    "install": "freedos-1.4-plain-install",
    "verify": "freedos-1.4-plain-verify"
  },
  "drives": {
    "hdd": {"size": "20M"},
    "cdrom": null
  },
  "boot": ["hdd", "cdrom"]
}
```

The labels are the verbs you use with `script`:
`rlq --blueprint freedos-1.4-plain script install` looks up
`scripts.install`, finds `freedos-1.4-plain-install`, and runs
`scripts/freedos-1.4-plain-install.rlqs`.

`name` and `description` are optional in both user and codex
blueprints. The codex carries an index mapping every
codex artifact to its name, description, and relationships;
user blueprints are indexed by reading these fields from the file.

### Creating a blueprint

```
rlq create blueprint <name> [flags]
```

Scaffolds `blueprints/<name>.rlqb` from CLI flags. Refuses if the
file already exists. `--platform` is required; everything else is
optional. Omitted fields stay omitted (the blueprint tracks
defaults, it doesn't bake them in).

The result is an ordinary user-owned blueprint file — you own it from
then on.

**A blank hard disk:**

```powershell
rlq create blueprint test-rig --platform dos --hdd 20M
```

Writes `blueprints/test-rig.rlqb`:

```json
{
  "platform": "dos",
  "drives": {
    "hdd": {"size": "20M"}
  }
}
```

**An installation machine — blank hard disk plus empty CD slot:**

```powershell
rlq create blueprint freedos --platform dos --memory 32M `
    --hdd 20M --boot hdd,cdrom
```

Then edit the blueprint to declare the empty CD slot the install
script will fill (`"cdrom": null`). Resulting shape:

```json
{
  "platform": "dos",
  "memory": "32M",
  "drives": {
    "hdd": {"size": "20M"},
    "cdrom": null
  },
  "boot": ["hdd", "cdrom"]
}
```

(A blank hard disk falls through to an attached LiveCD; no
boot-order change is needed after install.)

**Pin to a backend, with a specific machine type:**

```powershell
rlq create blueprint retro-pc --platform dos --backend qemu `
    --hdd 100M --memory 16M
```

`--hdd <size>` produces a blank disk (`{"size": "20M"}`). For a
hard disk built on a base image or backed by a media item, edit the
JSON — or start from a codex blueprint that already has the
shape you want.

`--cdrom <media>` and `--floppy <media>` produce `media`
references.

`--boot <order>` takes a comma-separated list of drive keys in alias
form (`cdrom,hdd`, `floppy,hdd`).

```
--platform <dos|win9x|winnt>     required
--memory <size>                   e.g. 32M, 128M, 2G
--cpus <n>                        default 1
--backend <qemu|virtualbox|vmware|hyperv>
--hdd <size>                      blank hard disk, e.g. 20M, 500M
--cdrom <media>                   CD-ROM from the media library
--floppy <media>                  floppy from the media library
--boot <order>                    comma-separated drive keys, e.g. cdrom,hdd
--control-planes <list>           comma-separated, e.g. guest-agent,agentless-display
```

For drives beyond the first slot, controller types, or anything
else the scaffolder doesn't cover, edit the JSON file directly.

### Pulling from the codex

```
rlq pull (blueprint | media | script) <name> [--only]
```

Extracts artifacts from the codex into your home.
Existing files are never overwritten.

- `rlq pull blueprint <name>` — pulls a blueprint and
  everything it references: its media definitions and all scripts
  named in its `scripts` map. This is the one-stop command to
  materialize a codex artifact into your home. `--only` restricts it to
  the blueprint file itself.
- `rlq pull media <name>` — pulls a single media definition.
- `rlq pull script <name>` — pulls a single script.

```powershell
# Pull everything for a codex blueprint
rlq pull blueprint freedos-1.4

# Pull individual artifacts
rlq pull blueprint freedos-1.4-plain --only
rlq pull media freedos-1.4-livecd
rlq pull script freedos-1.4-plain-install
```

After pulling, the files are ordinary user-owned documents — edit
them, version them, delete them. This is the bridge from "just use
the codex's" to "I want to tweak it." To reset a copy to the
current codex copy, delete your file and pull again.

### Naming conventions

Codex artifacts follow a convention that ties them together by
blueprint and script:

| artifact | pattern | example |
|---|---|---|
| blueprint | `<name>.json` | `freedos-1.4-plain.json` |
| script | `<blueprint>-<script-id>.rlqs` | `freedos-1.4-plain-install.rlqs` |
| script-aligned media | `<blueprint>-<script-id>-<drive>.json` | `freedos-1.4-plain-install-cdrom.json` |
| shared media | `<name>.json` | `freedos-1.4-livecd.json` |

A media definition that is specific to one script's step — the
installer CD that script inserts, a driver disk it stages — uses the
script-aligned pattern. A media definition shared across scripts or
blueprints (or used independently by `create --blueprint`) uses a
standalone name. Both resolve through the same media library;
the naming convention identifies ownership, not a namespace.

### Listing and searching blueprints

```
rlq list blueprints
rlq search blueprints <term>...
```

`list blueprints` shows everything in `blueprints/`. `search
blueprints` queries the codex index and user blueprint files,
matching terms against filename, `name`, `description`, and
platform. Multiple terms are ANDed:

```powershell
$ rlq search blueprints dos
BLUEPRINT              NAME                                MACHINES  CODEX
freedos-1.4-plain      FreeDOS 1.4                         2         seeded
test-rig               (untitled)                          0
msdos-622              MS-DOS 6.22 — base install          —         yes

$ rlq search blueprints freedos install
BLUEPRINT              NAME                                MACHINES  CODEX
freedos-1.4-plain      FreeDOS 1.4                         2         seeded
```

The CODEX column tracks provenance by name: `yes` marks a
library entry not yet in your home; `seeded` marks a user file
whose name also exists in the library (it was extracted, or shares
the name); blank marks a purely user-authored file.

`--verbose` adds the description line:

```powershell
$ rlq search blueprints freedos --verbose
BLUEPRINT              freedos-1.4-plain
NAME                   FreeDOS 1.4 — Plain DOS system
DESCRIPTION            Installs FreeDOS 1.4 onto a blank hard disk. Selects the Plain DOS system package set.
PLATFORM               dos
SCRIPTS                install → freedos-1.4-plain-install
                       verify → freedos-1.4-plain-verify
MACHINES               2
```

### Deleting a blueprint

```
rlq delete blueprint <name>
```

Removes the blueprint's `.rlqb` file. Refuses while any machine of it
exists, listing their ids:

```
$ rlq delete blueprint freedos-1.4
rlq: blueprint 'freedos-1.4-plain' still has 2 machine(s): a1b2c3d4, e5f6a7b8
destroy them first, then delete the blueprint
```

### Importing a blueprint from a native VM

```
rlq import <source> --blueprint <name> --platform <platform>
    [--hdd-images (duplicate | difference)] [--snapshot | --no-snapshot]
```

Synthesizes a blueprint from a native backend VM's configuration —
memory, drives, controllers — capturing the VM's disks as media
items in place: each gets a generated definition whose
`local-path` points at the disk where the native hypervisor
keeps it (computed hash, no URL); nothing is copied or moved.
The source must be at rest: a running or suspended VM fails
closed naming its state — power it off first.

Two choices are presented, never defaulted (U2) — on a terminal
an absent flag prompts with its tradeoff; noninteractively it is
an error:

- `--snapshot` has the native hypervisor snapshot the disks
  first — the one thing import may do to the source VM, and only
  with this consent: the definitions pin the frozen extent and
  the source VM stays free to keep running natively. The
  snapshot is reliquary-named and noted in the generated
  definitions; its later fate in native tooling is yours
  (verification reports a lost extent). `--no-snapshot` touches
  nothing — but running the source VM again breaks verification
  until re-import.
- `--hdd-images` sets how machines materialize from the captured
  disks: `duplicate` copies the image into each created machine,
  whose drive stands alone afterward; `difference` differences
  against it (cheapest create, but per-start verification
  refuses a source rewritten since).

`--platform` is required
(no backend records the guest OS). Stops at the blueprint; run
`create` when you want a machine.

```powershell
rlq import "C:\VMs\my-dos-box" --blueprint my-dos-box `
    --platform dos --hdd-images difference --snapshot
```

Machines created from an imported blueprint recreate from their
bases like any other. To move a captured image to more durable
ground, move the file and repoint the definition's `local-path` —
the definition is yours.

---

## Machines

Machines are disposable realizations of a blueprint, each identified
by `<blueprint>-<n>` and stored entirely under
`cache/machines/<blueprint>-<n>/`. Everything under `cache/` is
reliquary's and disposable — and, run records excepted, regenerates
from blueprints, media definitions, and scripts (records are
evidence: copy out any worth keeping).

Every machine verb has an embedding-API twin under parity, flat
verb-noun functions: `create_machine`, `start_machine`,
`stop_machine`, `apply_blueprint`, `destroy_machine`,
`recreate_machine`, `clone_machine`, `delete_blueprint`, and
`import_vm` (a bare `import` is a Python keyword); `export`'s
twin lands with export's still-open shape.

### Creating a machine

```
rlq --blueprint <name> create
```

Resolves `<name>` to a blueprint in `blueprints/`. If the file
doesn't exist but is available in the codex, it is
extracted — along with any referenced media definitions and scripts
not already present. Existing files are never overwritten.

Validates the blueprint, assigns a backend (if not declared),
allocates the lowest free machine number for that blueprint,
materializes the machine under `cache/machines/<blueprint>-<n>/`,
and prints the new id:

```powershell
$ rlq --blueprint freedos create
created machine freedos-0
```

The printed id is the machine's identity — use it with
`--machine`, or select by `--blueprint` when it is the sole
machine, or by `--blueprint NAME --machine N`:

```powershell
rlq --machine freedos-0 start
rlq --blueprint freedos --machine 0 start
```

`create` resolves the blueprint once and records the resolved
snapshot as the machine's *baseline*. Thereafter the machine's own
state is authoritative — script `insert`/`eject` persists in it —
and `start` never re-reads the current blueprint file. Editing the
blueprint affects future `create` operations only; adopt edits into
an existing machine (or return a diverged machine to its blueprint
shape) with [`apply`](#applying-blueprint-edits).

### Starting and stopping

```
reliquary (--blueprint <name> | --machine <id>) start [--display]
reliquary (--blueprint <name> | --machine <id>) stop
```

```powershell
rlq --blueprint freedos-1.4-plain start
rlq --blueprint freedos-1.4-plain stop
```

```powershell
rlq --blueprint freedos-1.4-plain start --display
# QEMU window opens — interact manually
rlq --blueprint freedos-1.4-plain stop
```

```powershell
rlq --machine a1b2 start
rlq --machine a1b2 stop
```

Every `start` reconciles the backend to the machine's state —
verifying backend identity and re-verifying every media hash,
including media a script attached. Machines stay running until
explicitly stopped — by `stop`, by a script step, or by guest
shutdown.

### Applying blueprint edits

```
reliquary (--blueprint <name> | --machine <id>) apply
```

Adopts the current blueprint into a stopped machine. Differences the
machine can absorb without regenerating drives — memory, boot order,
drives enabled or disabled, changed `media` references, added drives
— are applied and the baseline digest updated:

```powershell
# Edit freedos.rlqb: disable the CD, boot from hard disk
rlq --blueprint freedos stop
rlq --blueprint freedos apply
rlq --blueprint freedos start
```

Changes the machine cannot absorb — a different `size` on an
existing image, a `base` change on a materialized drive — fail
closed:

```
$ rlq --blueprint freedos apply
rlq: cannot apply: hdd0 size changed from "20M" to "40M"
drive-regenerating changes require 'recreate' (machine a1b2)
```

### Destroying and recreating

```
reliquary (--blueprint <name> | --machine <id>) destroy
reliquary (--blueprint <name> | --machine <id>) recreate
```

`destroy` deletes the machine entirely — its cache directory and
the backend's machine. The blueprint is never touched.

`recreate` is `destroy` + `create` as one command under the same id.
Drives regenerate fresh: `size` drives come back blank, `base`
drives come back as fresh differencing disks (or copies). A
blueprint without a pinned `backend` may land on a different
backend — this is the supported way to move a machine between
backends.

```powershell
rlq --blueprint freedos destroy
rlq --blueprint freedos recreate
# same id, fresh materialization
```

```powershell
rlq --machine a1b2 recreate
# destroys a1b2, creates new a1b2 from its blueprint
```

### Cloning

```
reliquary (--blueprint <name> | --machine <id>) clone
```

Duplicates a stopped machine under the next free
`<blueprint>-<n>` id. The clone retains the
source's resolved blueprint snapshot and copies the source's
writable drive images:

```powershell
rlq --blueprint freedos stop
rlq --blueprint freedos clone
# → cloned machine f3e4d5c6
```

### Exporting

```
reliquary (--blueprint <name> | --machine <id>) export
    [--drive <key>] [<destination>]
```

Takes a durable artifact out of an ephemeral machine. Two targets:

- **A media image** — a single drive taken out as a standalone image:
  `rlq --blueprint freedos export --drive hdd0 D:\exports\dos-disk.qcow2`
- **The entire machine** — copied to its backend's native management,
  registered where that backend normally keeps VMs, with disks in
  its native format:
  `rlq --blueprint freedos export`

The exported artifact is independent and permanently outside
reliquary's purview.

### Listing machines

```
rlq list machines [--blueprint <name>]
```

```
ID              BLUEPRINT          PHASE    BACKEND
freedos-0       freedos            ready    qemu
freedos-1       freedos            running  qemu
msdos-0         msdos              ready    qemu
```

`--blueprint` filters to one blueprint's machines.

### Selection rules

On every machine-level verb, `--blueprint <name>` selects that
blueprint's machine when exactly one exists — the common
one-machine-per-blueprint case:

```powershell
# freedos has exactly one machine: works
rlq --blueprint freedos start
```

With several machines, the command fails and lists candidate ids:

```
$ rlq --blueprint freedos start
rlq: blueprint 'freedos' has 2 machines; pick one with --machine <n> or --machine <blueprint>-<n>:
  freedos-0  (ready)
  freedos-1  (running)
```

With none, the command fails suggesting `create`:

```
$ rlq --blueprint freedos start
rlq: no machine exists for blueprint 'freedos'
create one: rlq --blueprint freedos create
```

`--machine <blueprint>-<n>` always works; so does
`--blueprint <name> --machine <n>`:

```powershell
rlq --machine freedos-0 start
rlq --blueprint freedos --machine 0 start
```

Ambiguous prefixes list candidates:

```
$ rlq --machine a1b start
rlq: 'a1b' matches 2 machines:
  a1b2c3d4  freedos (ready)
  a1b3e5f7  msdos (ready)
```

---

## Interaction

Commands for typing, running commands, and inspecting the guest.
Every interaction command requires `--blueprint <name>` or
`--machine <id>` to identify the running machine. There is no
"active machine" shortcut.

### Typing and sending keys

```
reliquary (--blueprint <name> | --machine <id>) type <text>
reliquary (--blueprint <name> | --machine <id>) keys <key>...
```

```powershell
rlq --blueprint freedos type "dir C:\"
rlq --blueprint freedos keys enter
rlq --machine a1b2 keys ctrl-alt-del
```

Available key names include `enter`, `esc`, `tab`, `backspace`,
`f1`–`f12`, `up`, `down`, `left`, `right`, `ctrl-alt-del`, and
single characters.

### Running DOS commands

```
reliquary (--blueprint <name> | --machine <id>) run <command> [--timeout <seconds>]
```

Executes a DOS command with prompt-based completion detection.
Requires the DOS platform:

```powershell
rlq --blueprint freedos run "ver"
# → FreeDOS kernel 2043 (Build 2043) [compiled Feb 26 2021]
rlq --blueprint freedos run --timeout 120 "dir C:\*.exe"
```

### Inspecting the screen

```
reliquary (--blueprint <name> | --machine <id>) text
reliquary (--blueprint <name> | --machine <id>) wait <pattern> [--timeout <seconds>]
reliquary (--blueprint <name> | --machine <id>) screenshot [<name>]
```

`text` prints the current VGA text screen (80x25 rows). `wait`
blocks until the screen matches a regex — literal text or a Python
regular expression. `screenshot` captures the framebuffer.

```powershell
rlq --blueprint freedos text
# 25 lines of screen content printed to stdout

rlq --blueprint freedos wait "C:\\\\>" --timeout 30
# blocks until the DOS prompt appears
# → matched.

rlq --blueprint freedos screenshot boot-menu
# writes screenshots/boot-menu.png under the machine's cache
```

### Menu navigation

```
reliquary (--blueprint <name> | --machine <id>) menu <item>
    [--exclude <text>]... [--timeout <seconds>]
```

Navigates a cursor-key text menu by visible text. Presses up/down
keys following the selection highlight until the highlight sits on
the matching row, then presses Enter. Rows containing any
`--exclude` text are skipped.

```powershell
rlq --blueprint freedos menu "Install to harddisk"
rlq --blueprint freedos menu --exclude "with sources" "Plain DOS system"
```

### Raw HMP

```
reliquary (--blueprint <name> | --machine <id>) hmp <line>
```

Sends a raw QEMU human monitor protocol (HMP) command:

```powershell
rlq --blueprint freedos hmp "info status"
rlq --machine a1b2 hmp "info block"
```

---

## Scripts

### Listing and searching scripts

```
rlq list scripts
rlq search scripts <term>...
```

`list scripts` shows everything in `scripts/`. `search scripts`
queries the codex index and user scripts, matching terms against
filename, `name`, and `description`:

```powershell
$ rlq search scripts freedos
SCRIPT                        NAME                          CODEX
freedos-1.4-plain-install     FreeDOS 1.4 — plain install         seeded
freedos-1.4-plain-verify      FreeDOS 1.4 — verify boot     yes
```

### Running scripts

```
reliquary (--blueprint <name> | --machine <id>) script <label>
    [--responses <path>] [--display] [--detach] [--progress <mode>]
rlq check-script <script_name>
    [--blueprint <name> | --machine <id>] [--responses <path>]
```

A script is a `.rlqs` file under `scripts/`. `script <label>` first
looks up `<label>` in the blueprint's `scripts` map (labels are
short verbs — `install`, `verify`, `test`, `configure`); when there
is no matching label, `<label>` is taken as a bare script filename
and `scripts/<label>.rlqs` is run. Label takes priority over bare
filename.

If a referenced script doesn't exist in `scripts/` but is available
in the codex, it is extracted alongside any missing media
definitions before execution. Existing files are never overwritten.

**One-shot install — the common case:**

```powershell
rlq --blueprint freedos-1.4-plain script install
```

Behind the scenes this:
1. Extracts `blueprints/freedos-1.4-plain.rlqb`, its companion media
   definitions, and its scripts from the codex (skipping
   any that already exist).
2. Creates a machine from the blueprint.
3. Runs `scripts/freedos-1.4-plain-install.rlqs`, which inserts
   the LiveCD, starts the machine, drives the install, and
   ejects the CD again as its final step.

When a script ends the machine stays in whatever state its last
step left it (the FreeDOS install script powers it off); run
another script against it or control it directly:

```powershell
rlq --blueprint freedos-1.4-plain script verify
rlq --blueprint freedos-1.4-plain stop
```

`script` resolves the machine (creating one when `--blueprint` names
a blueprint with no machine yet), brings it to the state the
script's `machine:` header expects — starting a stopped machine
when the script expects `running` (the default), failing when a
`machine: stopped` script finds it running — then executes guest
steps. `--display` shows the backend's console
window; `--responses` binds a JSON file of input values.

`--progress (auto | tty | plain | rawjson)` selects the rendering
(default `auto`: tty detection). `rawjson` is the programmatic
synchronous form: stdout carries the run's event stream as JSON
lines and nothing else — the last line is the terminal event, the
machine-readable result — diagnostics go to stderr, and the exit
code carries the outcome. `plain` and `rawjson` never prompt: a
missing input value fails preflight instead of hanging a program.

`check-script` runs preflight only: parsing, static control-flow
checks, capability preflight. With a machine selector, also binds
responses and checks media resolution — read-only, no guest steps.

```powershell
rlq --blueprint freedos-1.4-plain script install --display
rlq --blueprint freedos-1.4-plain script install --responses answers.json
rlq --blueprint freedos-1.4-plain script install --progress rawjson

rlq check-script freedos-1.4-plain-install
rlq check-script freedos-1.4-plain-install --blueprint freedos-1.4
```

### Detached runs

```
reliquary (--blueprint <name> | --machine <id>) script <label> --detach
reliquary (--blueprint <name> | --machine <id>) run status [<n>]
reliquary (--blueprint <name> | --machine <id>) run tail [<n>]
reliquary (--blueprint <name> | --machine <id>) run wait [<n>]
reliquary (--blueprint <name> | --machine <id>) run cancel [<n>] [--stop]
reliquary (--blueprint <name> | --machine <id>) run delete <n> [<n> ...]
rlq list runs [--blueprint <name> | --machine <id>]
```

A foreground `script` run is start-plus-attach: it streams its
own progress until the run ends, and Ctrl-C cancels the run.
`--detach` completes parsing, binding, and preflight in the
foreground — those failures land on the invoking command's exit
code — then hands off at the machine boundary and prints the
run id.

Runs number monotonically per machine (`<machine-id>/<n>`); the
`run` operations take the number positionally and default to the
machine's latest run. `run tail` renders live progress
(`--progress` as on `script`: pretty on a tty, `plain` or
`rawjson` for programs) and Ctrl-C stops
tailing without touching the run; `run wait` blocks until the
terminal event and exits with the run's own outcome code, so a
shell script or unbound language gets the result by waiting;
`run cancel` ends the run at the next event boundary and leaves
the machine as-is — `--stop` also hard powers it off.
`run delete` removes a run's record — the one `run` operation
that never defaults to the latest run, because deleting evidence
warrants naming it: the numbers are explicit, several may be
given, a live run's record is refused (`run cancel` first), and
deletion frees no number. Records are otherwise kept for the
machine's life; copy a record's directory out to keep it beyond
`destroy` (the record contract is in the script spec).

```powershell
rlq --blueprint freedos-1.4-plain script install --detach
# → freedos-1.4-plain-1/4
rlq --blueprint freedos-1.4-plain run tail
rlq --blueprint freedos-1.4-plain run wait; echo $LASTEXITCODE
rlq --machine freedos-1.4-plain-1 run cancel 4 --stop
```

---

## Media

Media definitions describe installation media — download URLs,
archive structure, and SHA-256 hashes. Definitions live under
`media/` and are ordinary user-owned JSON files (the codex
library provides seeds that are extracted on first reference;
existing files are never overwritten).

### Listing and searching media

```
rlq list media
rlq search media <term>...
```

`list media` shows everything in `media/`. `search media` queries
the codex index and user media definitions, matching terms
against filename, `name`, and `description`. Multiple terms are
ANDed:

```powershell
$ rlq search media freedos
MEDIA                   NAME                    CODEX
freedos-1.4-livecd      FreeDOS 1.4 LiveCD ISO  seeded
freedos-1.4-bonus       FreeDOS 1.4 Bonus CD    yes

$ rlq search media win98
MEDIA                   NAME                    CODEX
win98se                 Windows 98 SE OEM ISO   yes
```

`--verbose` adds the description and source URL.

### Fetching and cleaning

```
rlq fetch <media_name> [--script <script_name>] [--progress <mode>]
rlq clean downloads
rlq clean media
```

`fetch` downloads, extracts, and hash-verifies a defined media item.
Machine operations resolving a `media` reference to a fetchable
definition fetch implicitly; `fetch` is the standalone convenience.
`--script` installs that script's embedded definitions before
fetching, without executing guest steps. `--progress` selects
rendering as on `script` — pretty live progress on a tty under
`auto`; `rawjson` emits pure event JSON on stdout, the last line
the terminal event stating the outcome. `plain` and `rawjson`
never prompt: a hash mismatch without `--refetch-mismatched`
fails fast.

```powershell
rlq fetch freedos-1.4-livecd
rlq fetch --script freedos-plain-install
```

`clean downloads` reclaims cached source archives under
`cache/downloads/`. `clean media` reclaims fetched payload files
under `cache/media/` that reliquary can re-fetch. Nothing
irreplaceable — definitions, `local-path` files, sourceless
payloads — is cleanable.

```powershell
rlq clean downloads
rlq clean media
```

---

## Properties

```
rlq property list [<prefix>]
rlq property get <key>
rlq property set <key> <value>
rlq property set <key> --secret
rlq property unset <key>
```

Maintains the home-wide personal registry in `properties.json`.
Ordinary values are strings; secret values live only in the host's
protected credential store, with a marker in the file.

```powershell
rlq property set username "paul"
rlq property set product-key --secret
# prompts for the value with no echo
rlq property get username
# → paul
rlq property get product-key
# → (secret) — stored in credential store, cannot display
rlq property list
# username
# product-key (secret)
rlq property unset username
```

Keys are dotted names (`timezone`, `keys.product`, `network.host`).
Listing and getting secrets never reveals them; `set --secret` uses
a no-echo prompt. Kind changes — making a secret ordinary or vice
versa — require `unset` first.

---

## Global options

```
rlq [--home <path>] [--blueprint <name>] [--machine <id>]
          [--timeout <seconds>] <command> [args...]
```

`--home` overrides the reliquary home directory (default:
`Documents/reliquary`).

`--blueprint <name>` and `--machine <id>` are global selectors
available before any subcommand. They are mutually exclusive. On
machine-level verbs (`start`, `stop`, `apply`, `destroy`,
`recreate`, `clone`, `export`, `type`, `run`, `keys`, `menu`,
`text`, `wait`, `screenshot`, `hmp`, `script`) at least one is
required; `script` auto-creates a machine when `--blueprint` names a
blueprint with none yet. Commands that don't operate on a machine
(`list`, `fetch`, `property`, `clean`, `create blueprint`, `delete
blueprint`, `import`, `check-script`) ignore them.

`--timeout` sets a per-command timeout in seconds where applicable
(runtime defaults vary by command).

There is no bare-script shorthand: an unrecognized command word is
an error, never a script lookup. `script <label>` is the tightest
form — it keeps script names from colliding with present or future
subcommands.

The old `--qemu`, `--platform`, and `--port` global options belong to
the pre-blueprint single-machine model and are removed —
`--platform` is a blueprint field, `--qemu` is resolved by backend
assignment, and `--port` is a state detail.
