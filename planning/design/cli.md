<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# CLI

> **Status:** working document for brainstorming the command-line
> structure; expected to be short-lived. Settled decisions live in
> [ROADMAP.md](../ROADMAP.md) ("The CLI" and the milestones);
> concepts introduced here are documented durably in
> [codex.md](codex.md) (the codex,
> `seed`, naming conventions, provenance) and the
> [blueprint field reference](machine-blueprint-reference.md)
> (`description`, `scripts`).

Every command maps one-to-one onto a public API call — and is
**named by it**: a command is its twin's name, dash-separated
(`create-machine` ↔ `create_machine`), and its flags mirror the
twin's parameters (`--hdd-images` ↔ `hdd_images=`). Naming the
twin names the command; the presentations cannot drift. Two named
exceptions, each an identity with a different home surface: the
guest-console family spells as the script language's verbs
(`type`, `enter`, `press`, `select`, `wait`, `screen`,
`screenshot`, `exec`, `hmp`), and the `run` family maps to the
API's run-handle methods. The CLI resolves `--blueprint` and
`--machine` selectors; the API takes the same identifiers.
Nothing is CLI-only.

**Selection.** Machine-level verbs take a target selector:

- `--blueprint <name>` — selects that blueprint's machine when
  exactly one exists; fails listing candidate ids when several
  exist; fails suggesting `create-machine` when none exist
  (except `run-script`, which creates one).
- `--machine <id>` — the full machine id, exactly. There is no
  prefix matching and no bare-number form: the id *is* the
  (blueprint, number) pair composed, so each selector carries one
  honest type — `resolve_machine(machine=, blueprint=)` under the
  mirror.

Blueprints are selected by name alone (`--blueprint <name>`, the
stem of the `<name>.rlqb` file the asset root supplies). Machine
ids are
`<blueprint>-<n>` (lowest free number, reused after destroy).

---

## Blueprints

Blueprint files describe a kind of machine. They live under
`blueprints/` alongside companion media definitions (`media/`) and
scripts (`scripts/`). Author them by hand, scaffold them with
`new-blueprint`, or let reliquary extract them from its codex.

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
reference (or an explicit `seed-`) extracts the current codex
copy again. Orphaned
references — a blueprint naming a media definition or script you
removed — re-seed the same way.

This means the lazy path is often one command with zero files in
your home beforehand: `rlq run-script install --blueprint
freedos-1.4` extracts the blueprint, its media, and its scripts,
creates a machine, and runs the install — everything materialized on
first use.

### Named scripts

A blueprint may declare a `scripts` map — short labels that name
`.rlqs` script files. It may also carry an optional
`description` field for discovery (the file stem is the
blueprint's one name):

```json
{
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

The labels are the verbs you use with `run-script`:
`rlq run-script install --blueprint freedos-1.4-plain` looks up
`scripts.install`, finds `freedos-1.4-plain-install`, and runs
`scripts/freedos-1.4-plain-install.rlqs`.

`description` is optional in both user and codex
blueprints. The codex carries an index mapping every
codex artifact to its description and relationships;
user blueprints are indexed by reading the field from the file.

### Scaffolding a blueprint

```
rlq new-blueprint <name> [flags]
```

Scaffolds `blueprints/<name>.rlqb` from CLI flags. Refuses if the
file already exists. `--platform` is required; everything else is
optional. Omitted fields stay omitted (the blueprint tracks
defaults, it doesn't bake them in).

The result is an ordinary user-owned blueprint file — you own it from
then on.

**A blank hard disk:**

```powershell
rlq new-blueprint test-rig --platform dos --hdd 20M
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
rlq new-blueprint freedos --platform dos --memory 32M `
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
rlq new-blueprint retro-pc --platform dos --backend qemu `
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

### Seeding from the codex

```
rlq (seed-blueprint | seed-media | seed-script) <name> [--only]
```

Extracts artifacts from the codex into your home — API twins
`seed_blueprint(name, only=)`, `seed_media`, `seed_script`.
Existing files are never overwritten.

- `rlq seed-blueprint <name>` — seeds a blueprint and
  everything it references: its media definitions and all scripts
  named in its `scripts` map. This is the one-stop command to
  materialize a codex artifact into your home. `--only` restricts it to
  the blueprint file itself.
- `rlq seed-media <name>` — seeds a single media definition.
- `rlq seed-script <name>` — seeds a single script.

```powershell
# Seed everything for a codex blueprint
rlq seed-blueprint freedos-1.4

# Seed individual artifacts
rlq seed-blueprint freedos-1.4-plain --only
rlq seed-media freedos-1.4-livecd
rlq seed-script freedos-1.4-plain-install
```

After seeding, the files are ordinary user-owned documents — edit
them, version them, delete them. This is the bridge from "just use
the codex's" to "I want to tweak it." To reset a copy to the
current codex copy, delete your file and seed again.

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
blueprints (or used independently by `create-machine`) uses a
standalone name. Both resolve through the same media library;
the naming convention identifies ownership, not a namespace.

### Listing and searching blueprints

```
rlq list-blueprints
rlq search-blueprints <term>...
```

`list-blueprints` shows everything in `blueprints/`.
`search-blueprints` queries the codex index and user blueprint files,
matching terms against filename, `description`, and
platform (the file stem is the blueprint's one name — there is no
display-name field). Multiple terms are ANDed:

```powershell
$ rlq search-blueprints dos
BLUEPRINT              DESCRIPTION                              MACHINES  CODEX
freedos-1.4-plain      Installs FreeDOS 1.4 onto a blank ha...  2         seeded
test-rig                                                        0
msdos-622              Installs MS-DOS 6.22 from three flop...  —         yes

$ rlq search-blueprints freedos install
BLUEPRINT              DESCRIPTION                              MACHINES  CODEX
freedos-1.4-plain      Installs FreeDOS 1.4 onto a blank ha...  2         seeded
```

The CODEX column tracks provenance by name: `yes` marks a
library entry not yet in your home; `seeded` marks a user file
whose name also exists in the library (it was extracted, or shares
the name); blank marks a purely user-authored file.

`--verbose` shows the full record:

```powershell
$ rlq search-blueprints freedos --verbose
BLUEPRINT              freedos-1.4-plain
DESCRIPTION            Installs FreeDOS 1.4 onto a blank hard disk. Selects the Plain DOS system package set.
PLATFORM               dos
SCRIPTS                install → freedos-1.4-plain-install
                       verify → freedos-1.4-plain-verify
MACHINES               2
```

### Deleting a blueprint

```
rlq delete-blueprint <name>
```

Removes the blueprint's `.rlqb` file. Refuses while any machine of it
exists, listing their ids:

```
$ rlq delete-blueprint freedos-1.4
rlq: blueprint 'freedos-1.4-plain' still has 2 machine(s):
  freedos-1.4-plain-0, freedos-1.4-plain-1
destroy them first, then delete the blueprint
```

### Importing a blueprint from a native VM

```
rlq import-vm <source> --name <name> --platform <platform>
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

`--name` names the blueprint to write (`--blueprint` always
selects an existing one) and `--platform` is required
(no backend records the guest OS). Stops at the blueprint; run
`create-machine` when you want a machine.

```powershell
rlq import-vm "C:\VMs\my-dos-box" --name my-dos-box `
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

Every machine verb *is* its embedding-API twin's name under the
identity rule: `create-machine` ↔ `create_machine`,
`start-machine`, `stop-machine`, `apply-blueprint`,
`destroy-machine`, `recreate-machine`, `clone-machine`,
`delete-blueprint`, and `import-vm` ↔ `import_vm`; `export`'s
name and twin land together with export's still-open shape.

### Creating a machine

```
rlq create-machine --blueprint <name>
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
$ rlq create-machine --blueprint freedos
created machine freedos-0
```

The printed id is the machine's identity — use it with
`--machine`, or select by `--blueprint` when it is the sole
machine:

```powershell
rlq start-machine --machine freedos-0
rlq start-machine --blueprint freedos
```

`create-machine` resolves the blueprint once and records the
resolved snapshot as the machine's *baseline*. Thereafter the
machine's own state is authoritative — script `insert`/`eject`
persists in it — and `start-machine` never re-reads the current
blueprint file. Editing the blueprint affects future
`create-machine` operations only; adopt edits into an existing
machine (or return a diverged machine to its blueprint shape)
with [`apply-blueprint`](#applying-blueprint-edits).

### Starting and stopping

```
rlq start-machine (--blueprint <name> | --machine <id>) [--display]
rlq stop-machine (--blueprint <name> | --machine <id>)
```

```powershell
rlq start-machine --blueprint freedos-1.4-plain
rlq stop-machine --blueprint freedos-1.4-plain
```

```powershell
rlq start-machine --blueprint freedos-1.4-plain --display
# QEMU window opens — interact manually
rlq stop-machine --blueprint freedos-1.4-plain
```

```powershell
rlq start-machine --machine freedos-0
rlq stop-machine --machine freedos-0
```

Every start reconciles the backend to the machine's state —
verifying backend identity and re-verifying every media hash,
including media a script attached. Machines stay running until
explicitly stopped — by `stop-machine`, by a script step, or by
guest shutdown.

### Applying blueprint edits

```
rlq apply-blueprint (--blueprint <name> | --machine <id>)
```

Adopts the current blueprint into a stopped machine. Differences the
machine can absorb without regenerating drives — memory, boot order,
drives enabled or disabled, changed `media` references, added drives
— are applied and the baseline digest updated:

```powershell
# Edit freedos.rlqb: disable the CD, boot from hard disk
rlq stop-machine --blueprint freedos
rlq apply-blueprint --blueprint freedos
rlq start-machine --blueprint freedos
```

Changes the machine cannot absorb — a different `size` on an
existing image, a `base` change on a materialized drive — fail
closed:

```
$ rlq apply-blueprint --blueprint freedos
rlq: cannot apply: hdd0 size changed from "20M" to "40M"
drive-regenerating changes require 'recreate-machine' (machine freedos-0)
```

### Destroying and recreating

```
rlq destroy-machine (--blueprint <name> | --machine <id>)
rlq recreate-machine (--blueprint <name> | --machine <id>)
```

`destroy-machine` deletes the machine entirely — its cache
directory and the backend's machine. The blueprint is never
touched.

`recreate-machine` is destroy + create as one command under the
same id.
Drives regenerate fresh: `size` drives come back blank, `base`
drives come back as fresh differencing disks (or copies). A
blueprint without a pinned `backend` may land on a different
backend — this is the supported way to move a machine between
backends.

```powershell
rlq destroy-machine --blueprint freedos
rlq recreate-machine --blueprint freedos
# same id, fresh materialization
```

```powershell
rlq recreate-machine --machine freedos-0
# destroys freedos-0, creates new freedos-0 from its blueprint
```

### Cloning

```
rlq clone-machine (--blueprint <name> | --machine <id>)
```

Duplicates a stopped machine under the next free
`<blueprint>-<n>` id. The clone retains the
source's resolved blueprint snapshot and copies the source's
writable drive images:

```powershell
rlq stop-machine --blueprint freedos
rlq clone-machine --blueprint freedos
# → cloned machine freedos-1
```

### Exporting

```
rlq export (--blueprint <name> | --machine <id>)
    [--drive <key>] [<destination>]
```

Takes a durable artifact out of an ephemeral machine. (Export's
shape is still open; under the identity rule its final command
name and API twin land together when it settles.) Two targets:

- **A media image** — a single drive taken out as a standalone image:
  `rlq export --drive hdd0 D:\exports\dos-disk.qcow2 --blueprint freedos`
- **The entire machine** — copied to its backend's native management,
  registered where that backend normally keeps VMs, with disks in
  its native format:
  `rlq export --blueprint freedos`

The exported artifact is independent and permanently outside
reliquary's purview.

### Listing machines

```
rlq list-machines [--blueprint <name>]
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
rlq start-machine --blueprint freedos
```

With several machines, the command fails and lists candidate ids:

```
$ rlq start-machine --blueprint freedos
rlq: blueprint 'freedos' has 2 machines; pick one with --machine <id>:
  freedos-0  (ready)
  freedos-1  (running)
```

With none, the command fails suggesting `create-machine`:

```
$ rlq start-machine --blueprint freedos
rlq: no machine exists for blueprint 'freedos'
create one: rlq create-machine --blueprint freedos
```

`--machine <id>` always works, and takes the full id exactly —
no prefixes, no bare numbers, nothing to disambiguate:

```powershell
rlq start-machine --machine freedos-0
```

---

## Interaction

Commands for sending input, executing guest commands, and
inspecting the guest. This is the identity rule's guest-console
exception: the vocabulary is the script language's own
([script-spec.md](script-spec.md), "Input verbs") — a capability
spells the same on both surfaces, each verb defined once, in the
spec, and referenced, never redefined, by the CLI. The CLI adds
exactly two commands scripts deliberately lack: `screen` (scripts
observe; humans and programs read) and `exec` (a composite
convenience; in a script, completion is an explicit observation).
Every interaction command requires `--blueprint <name>` or
`--machine <id>` to identify the machine. There is no "active
machine" shortcut. The family's API twins land with the
control-plane design — a named omission ([api.md](api.md)); the
capability is meanwhile reachable through today's `Machine`
functions.

### Typing and pressing keys

```
rlq type <text> (--blueprint <name> | --machine <id>)
rlq enter <line> (--blueprint <name> | --machine <id>)
rlq press <key>... (--blueprint <name> | --machine <id>)
```

`type` sends raw text with no implicit ending; `enter` types the
line and presses Enter (the language's derived form); `press`
sends keys from the language's closed portable key vocabulary,
with `+` forming chords. Key names and delivery semantics are the
script spec's — the CLI adds no keys and no per-platform variants.

```powershell
rlq type "A:" -b freedos
rlq press enter -b freedos
rlq enter "dir C:\" -b freedos
rlq press ctrl+alt+delete -m freedos-0
```

### Executing guest commands

```
rlq exec <command> (--blueprint <name> | --machine <id>) [--timeout <seconds>]
```

`exec` is the composite convenience: `enter` plus the platform
workflow's completion detection (prompt-based on DOS). The script
language deliberately has no such verb — in a script, completion
is an explicit observation — but interactively one command is
worth the composite, and the platform owns the completion
knowledge the caller would otherwise re-spell. A CLI/API
capability above the language, not a language concept.

```powershell
rlq exec "ver" -b freedos
# → FreeDOS kernel 2043 (Build 2043) [compiled Feb 26 2021]
rlq exec "dir C:\*.exe" -b freedos --timeout 120
```

### Observing the screen

```
rlq screen (--blueprint <name> | --machine <id>)
rlq wait <condition> (--blueprint <name> | --machine <id>) [--timeout <seconds>]
rlq screenshot [<name>] (--blueprint <name> | --machine <id>)
```

`screen` prints the current text screen (80x25 rows on VGA
guests) — the read twin of the language's default observation
channel. `wait` blocks until a condition matches, in the
language's condition spellings: `"..."` is a normalized literal
match (decoded, trimmed, whitespace-collapsed — no regex
escaping), `/.../` an opt-in regex, and `machine=stopped` the
machine channel — how a shell waits out a guest-initiated
power-off. `screenshot` captures the framebuffer.

```powershell
rlq screen -b freedos
# 25 lines of screen content printed to stdout

rlq wait "C:\>" -b freedos --timeout 30
# blocks until the DOS prompt appears

rlq wait machine=stopped -b freedos
# returns when the guest powers itself off

rlq screenshot boot-menu -b freedos
# writes screenshots/boot-menu.png under the machine's cache
```

### Menu selection

```
rlq select <item> (--blueprint <name> | --machine <id>)
    [--exclude <text>]... [--timeout <seconds>]
```

`select` picks an entry in a cursor-key menu by its normalized
visible label, exactly as the language's `select`: candidate rows
matching `<item>` are found, rows containing any `--exclude` text
are rejected, the highlight moves by observable feedback, and
Enter is pressed. Zero candidates, several remaining candidates,
an undetectable highlight, or traversal without progress are named
failures — it never guesses.

```powershell
rlq select "Install to harddisk" -b freedos
rlq select "Plain DOS system" --exclude "with sources" -b freedos
```

### Removable media and boot order

```
rlq insert-media <slot> <media> (--blueprint <name> | --machine <id>)
rlq eject-media <slot> (--blueprint <name> | --machine <id>)
rlq set-boot-order <key>... (--blueprint <name> | --machine <id>)
```

The state operations spell as their twins — `insert_media`,
`eject_media`, `set_boot_order` — because they mutate durable
machine state, not the live console (the script verbs `insert` /
`eject` / `set-boot` are the in-script spellings of the same
operations, whose rules apply by reference): `insert-media` and
`eject-media` address declared removable slots only (floppy and
CD-ROM; slot names per the blueprint reference) and work on a
running or stopped machine; inserting into an occupied slot or
ejecting an empty one fails; a missing or non-removable slot
fails before anything is touched. `set-boot-order` replaces the
boot order with the listed drive keys (canonical or alias form,
duplicates rejected, every key a declared drive) and requires a
stopped machine. The CLI's `<media>` argument is a bare media
name — `@` marks references only inside script text. Each change
lands in the machine's state document, not its blueprint, and
persists across stop/start: the machine legitimately diverges
until a later change restores it or `apply-blueprint` reconciles
it to its blueprint.

```powershell
rlq insert-media cdrom0 freedos-1.4-livecd -b freedos
rlq stop-machine -b freedos
rlq set-boot-order cdrom0 hdd0 -b freedos
rlq start-machine -b freedos
```

### Raw HMP

```
rlq hmp <line> (--blueprint <name> | --machine <id>)
```

Sends a raw QEMU human monitor protocol (HMP) command — the
QEMU-only escape hatch. It has no meaning on other backends and
will be homed as an explicitly backend-scoped command when the
control-plane design settles.

```powershell
rlq hmp "info status" -b freedos
rlq hmp "info block" -m freedos-0
```

---

## Scripts

### Listing and searching scripts

```
rlq list-scripts
rlq search-scripts <term>...
```

`list-scripts` shows everything in `scripts/`. `search-scripts`
queries the codex index and user scripts, matching terms against
filename and the script's `description` header (scripts have no
name field; the filename is the name):

```powershell
$ rlq search-scripts freedos
SCRIPT                        DESCRIPTION                              CODEX
freedos-1.4-plain-install     Unattended FreeDOS 1.4 plain install     seeded
freedos-1.4-plain-verify      Boot the installed disk and verify       yes
```

### Running scripts

```
rlq run-script <label> (--blueprint <name> | --machine <id>)
    [--responses <path>] [--display] [--detach] [--progress <mode>]
rlq check-script <label-or-name>
    [--blueprint <name> | --machine <id>] [--responses <path>]
```

A script is a `.rlqs` file under `scripts/`. `run-script <label>`
first looks up `<label>` in the blueprint's `scripts` map (labels
are short verbs — `install`, `verify`, `test`, `configure`); when
there is no matching label, `<label>` is taken as a bare script
filename and `scripts/<label>.rlqs` is run. Label takes priority
over bare filename.

If a referenced script doesn't exist in `scripts/` but is available
in the codex, it is extracted alongside any missing media
definitions before execution. Existing files are never overwritten.

**One-shot install — the common case:**

```powershell
rlq run-script install --blueprint freedos-1.4-plain
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
rlq run-script verify --blueprint freedos-1.4-plain
rlq stop-machine --blueprint freedos-1.4-plain
```

`run-script` resolves the machine (creating one when `--blueprint`
names a blueprint with no machine yet), brings it to the state the
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
checks, capability preflight. With a machine selector, its
argument resolves exactly as `run-script`'s — label first, then
bare script name — and it also binds responses and checks media
resolution; without a selector there is no `scripts` map to
consult, so the argument is a bare script name. Read-only, no
guest steps.

```powershell
rlq run-script install --blueprint freedos-1.4-plain --display
rlq run-script install --blueprint freedos-1.4-plain --responses answers.json
rlq run-script install --blueprint freedos-1.4-plain --progress rawjson

rlq check-script freedos-1.4-plain-install
rlq check-script install --blueprint freedos-1.4-plain
```

### Detached runs

```
rlq run-script <label> --detach (--blueprint <name> | --machine <id>)
rlq run status [<n>] (--blueprint <name> | --machine <id>)
rlq run tail [<n>] (--blueprint <name> | --machine <id>)
rlq run wait [<n>] (--blueprint <name> | --machine <id>)
rlq run cancel [<n>] [--stop] (--blueprint <name> | --machine <id>)
rlq run delete <n> [<n> ...] (--blueprint <name> | --machine <id>)
rlq list-runs [--blueprint <name> | --machine <id>]
```

The `run` family is the identity rule's second named exception:
its operations map to the API run handle's methods (`status()`,
`events()`, `wait()`, `cancel()`, plus `delete_run`), not to flat
functions. A foreground `run-script` run is start-plus-attach: it
streams its own progress until the run ends, and Ctrl-C cancels
the run.
`--detach` completes parsing, binding, and preflight in the
foreground — those failures land on the invoking command's exit
code — then hands off at the machine boundary and prints the
run id.

Runs number monotonically per machine (`<machine-id>/<n>`); the
`run` operations take the number positionally and default to the
machine's latest run. `run tail` renders live progress
(`--progress` as on `run-script`: pretty on a tty, `plain` or
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
rlq run-script install --blueprint freedos-1.4-plain --detach
# → freedos-1.4-plain-1/4
rlq run tail --blueprint freedos-1.4-plain
rlq run wait --blueprint freedos-1.4-plain; echo $LASTEXITCODE
rlq run cancel 4 --stop --machine freedos-1.4-plain-1
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
rlq list-media
rlq search-media <term>...
```

`list-media` shows everything in `media/`. `search-media` queries
the codex index and user media definitions, matching terms
against filename, item `name`s (the identifiers machine drives
reference — semantic, not display metadata), and `description`.
Multiple terms are ANDed:

```powershell
$ rlq search-media freedos
MEDIA                   DESCRIPTION                              CODEX
freedos-1.4-livecd      The FreeDOS 1.4 LiveCD installer ISO     seeded
freedos-1.4-bonus       The FreeDOS 1.4 BonusCD package ISO      yes

$ rlq search-media win98
MEDIA                   DESCRIPTION                              CODEX
win98se                 Windows 98 SE OEM installation ISO       yes
```

`--verbose` adds the description and source URL.

### Fetching and cleaning

```
rlq fetch-media <media_name> [--script <script_name>] [--progress <mode>]
rlq clean-downloads
rlq clean-media
```

`fetch-media` downloads, extracts, and hash-verifies a defined
media item. Machine operations resolving a `media` reference to a
fetchable definition fetch implicitly; `fetch-media` is the
standalone convenience.
`--script` installs that script's embedded definitions before
fetching, without executing guest steps. `--progress` selects
rendering as on `run-script` — pretty live progress on a tty under
`auto`; `rawjson` emits pure event JSON on stdout, the last line
the terminal event stating the outcome. `plain` and `rawjson`
never prompt: a hash mismatch without `--refetch-mismatched`
fails fast.

```powershell
rlq fetch-media freedos-1.4-livecd
rlq fetch-media --script freedos-plain-install
```

`clean-downloads` reclaims cached source archives under
`cache/downloads/`. `clean-media` reclaims fetched payload files
under `cache/media/` that reliquary can re-fetch. Nothing
irreplaceable — definitions, `local-path` files, sourceless
payloads — is cleanable.

```powershell
rlq clean-downloads
rlq clean-media
```

---

## Properties

```
rlq list-properties [<prefix>]
rlq get-property <key>
rlq set-property <key> <value>
rlq set-property <key> --secret
rlq unset-property <key>
```

Maintains the home-wide personal registry in `properties.json` —
API twins `get_property`, `set_property`, `unset_property`,
`list_properties` under the identity rule.
Ordinary values are strings; secret values live only in the host's
protected credential store, with a marker in the file.

```powershell
rlq set-property username "paul"
rlq set-property product-key --secret
# prompts for the value with no echo
rlq get-property username
# → paul
rlq get-property product-key
# → (secret) — stored in credential store, cannot display
rlq list-properties
# username
# product-key (secret)
rlq unset-property username
```

Keys are dotted names (`timezone`, `keys.product`, `network.host`).
Listing and getting secrets never reveals them; `set-property
--secret` uses a no-echo prompt. Kind changes — making a secret
ordinary or vice versa — require `unset-property` first.

---

## Flags and options

```
rlq <command> [args...] [--home <path>] [--blueprint <name>]
    [--machine <id>] [--timeout <seconds>] [--json]
```

Flags are the command's parameters, mirroring its API twin's
under the identity rule, and **position carries no meaning**: a
flag may appear before or after the command word —
`rlq run-script install --blueprint freedos-1.4-plain` and
`rlq --blueprint freedos-1.4-plain run-script install` are
identical. Synopses canonically show flags after the command.

Four flags are accepted by every command, mirroring the API's
shared keywords: `--home` (overrides the reliquary home; default
`Documents/reliquary`), `--assets` / `--assets-only` (the asset
root), and `--json` (below).

`--blueprint <name>` and `--machine <id>` are the machine
selectors, mutually exclusive. On machine-scoped commands
(`create-machine`, `start-machine`, `stop-machine`,
`apply-blueprint`, `destroy-machine`, `recreate-machine`,
`clone-machine`, `export`, `run-script`, the `run` operations,
`insert-media`, `eject-media`, `set-boot-order`, and the
guest-console family `type`, `enter`, `press`, `exec`, `select`,
`screen`, `wait`, `screenshot`, `hmp`) at least one is required;
`run-script` auto-creates a machine when `--blueprint` names a
blueprint with none yet. `check-script` uses a selector for label
resolution and response binding when one is given. Commands that
don't operate on a machine (`list-*`, `search-*`, `fetch-media`,
the property family, `clean-*`, `new-blueprint`,
`delete-blueprint`, `seed-*`, `import-vm`) ignore them.

`--timeout` sets a per-command timeout in seconds where applicable
(runtime defaults vary by command).

### Machine-readable output

`--json` is the global machine-readable switch for result-bearing
commands — the query half of the feedback split, and the parity
rule made visible: under `--json` a command prints **exactly what
its API twin returns**, serialized as one JSON document (object,
array, or scalar) on stdout — nothing else on stdout, diagnostics
on stderr, the exit code unchanged. The two presentations cannot
drift: a twin's return contract *is* the command's `--json`
contract, defined once where the twin is specified
([api.md](api.md)).

```powershell
$ rlq list-machines --json
[{"id": "freedos-0", "blueprint": "freedos", "phase": "ready", "backend": "qemu"}]

$ rlq create-machine --blueprint freedos --json
"freedos-1"
```

Rules:

- A command whose twin returns nothing prints `{}` on success, so
  a program may pass `--json` unconditionally on any
  result-bearing command.
- Stream-bearing commands (`run-script`, `run tail`,
  `fetch-media`) reject `--json`, naming `--progress rawjson`: a
  live run is an event stream, not a document — one flag, one
  meaning each.
- Secret property values never serialize; the marker
  (`{"secret": true}`) stands in, exactly as in `properties.json`.
- `--verbose` is a pretty-rendering concern: `--json` always
  carries the full record and never combines with it.

Field names are part of the CLI contract and land with each
twin's return contract; pre-beta the shapes are closed, and the
output-stability promise arrives with the general
programmatic-contract work.

There is no bare-script shorthand: an unrecognized command word is
an error, never a script lookup. `run-script <label>` is the
tightest form — it keeps script names from colliding with present
or future subcommands.

The old `--qemu`, `--platform`, and `--port` global options belong to
the pre-blueprint single-machine model and are removed —
`--platform` is a blueprint field, `--qemu` is resolved by backend
assignment, and `--port` is a state detail.
