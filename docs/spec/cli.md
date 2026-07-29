<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# CLI

> **Status:** normative. This is the specification of the CLI —
> one of the four primary interfaces (root ARCHITECTURE.md, "The
> interfaces") — and the implementation answers to it: where this
> document and the code disagree, the code has the bug unless the
> document is changed first through the interface-change rule
> ([planning/INTERFACES.md](../../planning/INTERFACES.md)).
>
> **Every command here exists.** Commands that do not are not
> documented here at all, however settled their design: unbuilt
> capability lives in
> [planning/proposed/FEATURES.md](../../planning/proposed/FEATURES.md).
> A test enforces both directions (`ClaimedCommandTests`), because
> until 2026-07-27 this document specified five commands the CLI
> did not have and omitted five it did.
>
> Concepts introduced here are documented durably in
> [codex.md](codex.md) (the codex,
> `seed`, naming conventions, provenance) and the
> [blueprint field reference](../blueprint-reference.md)
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
  mirror (the shared implementation seam, not a public twin: no
  command; the query form is `list-machines --blueprint`).

Blueprints are selected by name alone (`--blueprint <name>`, the
stem of the `<name>.rlqb` file the asset root supplies). Machine
ids are
`<blueprint>-<n>` (lowest free number, reused after destroy).

---

## Blueprints

Blueprint files describe a kind of machine, composed of named
`machine` / `media` / `source` / `archive` components. They live
under `blueprints/` alongside scripts (`scripts/`); a blueprint
carries its media, source, and archive components inside itself.
Author them by hand, scaffold them with `new-blueprint`, or let
Reliquary extract them from its codex.

**The codex.** Reliquary ships a set of blueprints (media
components included) and scripts for popular open source operating
systems. In a source checkout these live as ordinary files under
`codex/blueprints/` and `codex/scripts/`; when packaged for
distribution they are bundled
in a zip archive within the Reliquary package. Either way, when you
reference a codex artifact that doesn't yet exist in your home,
Reliquary copies it out. From that point on it is an ordinary
user-owned file — edit it, delete it, version it. A file already
present in your home is never overwritten; the codex is a seed,
not a live resolution tier.

Deleting your copy is also how you refresh it: a file in your home
is never touched, but once you delete it yourself, the next
reference (or an explicit `seed-`) extracts the current codex
copy again. An orphaned
reference — a blueprint naming a script you removed — re-seeds the
same way.

This means the lazy path is often one command with zero files in
your home beforehand: `rlq run-script install --blueprint
freedos` extracts the blueprint (its media inside it) and its
scripts, creates a machine, and runs the install — everything
materialized on first use.

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
    "install": "freedos-install",
    "verify": "freedos-verify"
  },
  "drives": {
    "hdd": "blank-20m",
    "cdrom": null
  },
  "boot": ["hdd", "cdrom"]
}
```

(`blank-20m` names a `media` component — `materialize: new`,
`size: "20M"` — carried in a `media` section of the same `.rlqb`.)

The labels are the verbs you use with `run-script`:
`rlq run-script install --blueprint freedos` looks up
`scripts.install`, finds `freedos-install`, and runs
`scripts/freedos-install.rlqs`.

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
  "machines": [
    {"name": "test-rig", "platform": "dos", "drives": {"hdd": "blank-20m"}}
  ],
  "media": [
    {"name": "blank-20m", "materialize": "new", "size": "20M"}
  ]
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
  "machines": [
    {
      "name": "freedos",
      "platform": "dos",
      "memory": "32M",
      "drives": {"hdd": "blank-20m", "cdrom": null},
      "boot": ["hdd", "cdrom"]
    }
  ],
  "media": [
    {"name": "blank-20m", "materialize": "new", "size": "20M"}
  ]
}
```

(A blank hard disk falls through to an attached LiveCD; no
boot-order change is needed after install.)

**Pin to a backend, with a specific machine type:**

```powershell
rlq new-blueprint retro-pc --platform dos --backend qemu `
    --hdd 100M --memory 16M
```

`--hdd <size>` produces a `new` media of that size plus a drive
naming it. For a hard disk that differences or copies a payload, or
attaches an existing media, edit the JSON — or start from a codex
blueprint that already has the shape you want.

`--cdrom <media>` and `--floppy <media>` name an existing media on
the slot.

`--boot <order>` takes a comma-separated list of drive keys in alias
form (`cdrom,hdd`, `floppy,hdd`).

```
--platform <dos|win9x|winnt>     required
--memory <size>                   e.g. 32M, 128M, 2G
--cpus <n>                        default 1
--backend <qemu|virtualbox|vmware|hyperv>
--hdd <size>                      blank hard disk (a new media), e.g. 20M, 500M
--cdrom <media>                   CD-ROM naming an existing media
--floppy <media>                  floppy naming an existing media
--boot <order>                    comma-separated drive keys, e.g. cdrom,hdd
--control-planes <list>           comma-separated, e.g. guest-agent,agentless-display
```

For drives beyond the first slot, controller types, or anything
else the scaffolder doesn't cover, edit the JSON file directly.

### Seeding from the codex

```
rlq (seed-blueprint | seed-script) <name> [--only]
```

Extracts artifacts from the codex into your home — API twins
`seed_blueprint(name, only=)`, `seed_script`. Existing files are
never overwritten. There is no `seed-media`: media are components
inside a `.rlqb` and are seeded with the blueprint that declares
them (D30 deleted the verb rather than keep it as a no-op).

- `rlq seed-blueprint <name>` — seeds a blueprint (its media, source,
  and archive components ride inside it) and all scripts named in its
  `scripts` map. This is the one-stop command to materialize a codex
  artifact into your home. `--only` restricts it to the blueprint
  file itself.
- `rlq seed-script <name>` — seeds a single script.

```powershell
# Seed everything for a codex blueprint
rlq seed-blueprint freedos

# Seed individual artifacts
rlq seed-blueprint freedos --only
rlq seed-script freedos-install
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
| blueprint | `<name>.rlqb` | `freedos.rlqb` |
| script | `<blueprint>-<script-id>.rlqs` | `freedos-install.rlqs` |

Media are components inside the blueprint, not files of their own, so
they carry component *names* rather than filenames: conventionally
`<blueprint>-<script-id>-<drive>` for a media specific to one script's
step (the installer CD it inserts, a driver disk it swaps in), or a
standalone `<name>` for one shared across scripts or blueprints. Both
resolve through the same namespace; the naming convention identifies
ownership, not a namespace.

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
freedos      Installs FreeDOS 1.4 onto a blank ha...  2         seeded
test-rig                                                        0
msdos-622              Installs MS-DOS 6.22 from three flop...  —         yes

$ rlq search-blueprints freedos install
BLUEPRINT              DESCRIPTION                              MACHINES  CODEX
freedos      Installs FreeDOS 1.4 onto a blank ha...  2         seeded
```

The CODEX column tracks provenance by name: `yes` marks a
library entry not yet in your home; `seeded` marks a user file
whose name also exists in the library (it was extracted, or shares
the name); blank marks a purely user-authored file.

`--verbose` shows the full record:

```powershell
$ rlq search-blueprints freedos --verbose
BLUEPRINT              freedos
DESCRIPTION            Installs FreeDOS 1.4 onto a blank hard disk. Selects the Plain DOS system package set.
PLATFORM               dos
SCRIPTS                install → freedos-install
                       verify → freedos-verify
MACHINES               2
```

### Deleting a blueprint

```
rlq delete-blueprint <name>
```

Removes the blueprint's `.rlqb` file. Refuses while any machine of it
exists, listing their ids:

```
$ rlq delete-blueprint freedos
rlq: blueprint 'freedos' still has 2 machine(s):
  freedos-0, freedos-1
destroy them first, then delete the blueprint
```

---

## Machines

Machines are disposable realizations of a blueprint, each identified
by `<blueprint>-<n>` and stored entirely under
`cache/machines/<blueprint>-<n>/`. Everything under `cache/` is
Reliquary's and disposable, regenerating from blueprints (media
components and all) and scripts. A run stores nothing here — it
returns its output to the caller (D36).

Every machine verb *is* its embedding-API twin's name under the
identity rule: `create-machine` ↔ `create_machine`,
`start-machine`, `stop-machine`, `apply-blueprint`,
`destroy-machine`, `recreate-machine`, and `delete-blueprint`.
The mobility verbs — `clone-machine`, `export-drive`,
`export-machine`, `import-vm` — are unbuilt: their names are
settled and their design stands in [api.md](api.md), which is the
end-goal design rather than a claim about today, and in
planning/proposed/FEATURES.md "Machine mobility".

### Creating a machine

```
rlq create-machine --blueprint <name>
```

Resolves `<name>` to a blueprint in `blueprints/`. If the file
doesn't exist but is available in the codex, it is
extracted — along with any referenced scripts not already present
(its media ride inside it). Existing files are never overwritten.

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
rlq start-machine --blueprint freedos
rlq stop-machine --blueprint freedos
```

```powershell
rlq start-machine --blueprint freedos --display
# QEMU window opens — interact manually
rlq stop-machine --blueprint freedos
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
drives enabled or disabled, re-pointed media names, re-fetched `use`
media, added drives — are applied and the baseline digest updated:

```powershell
# Edit freedos.rlqb: disable the CD, boot from hard disk
rlq stop-machine --blueprint freedos
rlq apply-blueprint --blueprint freedos
rlq start-machine --blueprint freedos
```

Changes the machine cannot absorb — a changed `size` or
`materialize` on an already-materialized media image — fail closed:

```
$ rlq apply-blueprint --blueprint freedos
rlq: cannot apply: media blank-20m size changed from "20M" to "40M"
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
Drives regenerate fresh the way their media declare: a `new` media
comes back blank, a `difference`/`copy` media comes back as a fresh
overlay on (or copy of) its payload. A
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
functions. Each command returns its output; recording a loop of
them into one persisted record (`begin-run` / `end-run`) is
async-backlog work (D36; "Recorded interaction runs — backlog"
below).

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
rlq exec <command> (--blueprint <name> | --machine <id>) [--timeout <duration>]
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
rlq wait <condition> (--blueprint <name> | --machine <id>) [--timeout <duration>]
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
    [--exclude <text>]... [--timeout <duration>]
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
rlq insert-media cdrom0 freedos-livecd -b freedos
rlq stop-machine -b freedos
rlq set-boot-order cdrom0 hdd0 -b freedos
rlq start-machine -b freedos
```

### In-band file exchange

```
rlq put-file <source> <destination> (--blueprint <name> | --machine <id>)
rlq get-file <source> <destination> (--blueprint <name> | --machine <id>)
rlq put-files <source> <destination> (--blueprint <name> | --machine <id>)
rlq get-files <source> <destination> (--blueprint <name> | --machine <id>)
rlq list-files <address> [--recursive] (--blueprint <name> | --machine <id>)
```

Twins `put_file` / `get_file` / `put_files` / `get_files` /
`list_files`. The guest-side path is written **the way the guest
names it** — `A:\TEST.EXE` on DOS, that system's separators and
roots, never an image file or a staging directory (**P17**). The
drive letter resolves from the machine's declared platform and
Reliquary's own drive assignment, never by inspecting a guest
(**P10**).

**One address vocabulary across all five**, not two spellings of
it. A directory is addressed exactly as a file is, and only the
drive itself is newly sayable: `A:\` (or the bare `A:`) is the
drive root, a trailing separator is optional everywhere else, and
`.` / `..` segments are refused. A file address needs a file — a
plain `A:\` to `get-file` is an error, because a drive is not a
file.

All five are **stopped-only**, and the addressed drive must be a
directory-source drive: the backend snapshots that directory when
it attaches, so a change made while the machine runs would be
invisible to the guest and a guest write is not flushed until it
stops. A **drive image is read and written at rest**: with the
machine stopped its disk is a file the host owns, so all five
verbs reach an installed `C:` by mounting the image and working
the FAT volume in it — no guest, no boot, and no reaching around
Reliquary. A write lands in a scratch copy and replaces the disk
in one step at the end, so an interrupted or refused write leaves
the image exactly as it was; a differencing image stays one, over
the same base.

A guest-side name must be one the guest could type: **8.3, or a
refusal** (`drive.image-unreadable`), never a silent truncation
that would land the file where the caller cannot find it.
Three more refusals name themselves, each raised before anything
is transferred (**P11**): `drive.no-at-rest-access` when the
backend cannot flatten its own image format,
`drive.no-at-rest-write` when it can read one and not rebuild it,
and `drive.volume-count-unsupported` when a disk holds more than
one volume — the letter map assumes one per disk, so answering
for either would answer for a drive the caller did not
address.

**The letter map places every drive**, so a directory-source drive
is addressable wherever it sits — including behind an installed
`C:`, which is the ordinary shape and used to be unreachable
entirely. Floppies take `A:` and `B:` by slot; hard disks follow
from `C:` in slot order; CD-ROMs follow the last disk. Disk
letters rest on **one stated assumption — one volume per hard
disk** — which is true of every disk Reliquary materializes and
which a guest that repartitions can silently contradict; reading
the real volume layout off the image is unbuilt. The one thing
that still unfixes a letter is a machine mixing controller types,
where slot order is authoritative only within a type.

The plural verbs move a tree's **contents**: `put-files` places
what is inside the host directory into the guest directory, and
`get-files` the reverse — the only shape a drive root can take,
having no name of its own to nest under. Both recurse, create
directories as needed — the destination included, as `put-file`
already creates the ones its address names — overwrite a file
already there, and remove
nothing: a copy, never a mirror. `get-files`' destination is
**required** — Reliquary invents no location to write to (**P12**)
— and is created if absent. `put-files` returns the guest
addresses written and `get-files` the host paths, each sorted.

`list-files` reports one directory level, or the whole tree under
`--recursive`. Its return is a flat array sorted by address, one
object per entry:

```json
[
  {"address": "A:\\JOB.BAT", "name": "JOB.BAT", "kind": "file", "size": 42},
  {"address": "A:\\OUT", "name": "OUT", "kind": "directory", "size": null}
]
```

`kind` is `file` or `directory`; `size` is the file's bytes and
`null` for a directory, which is not a size the guest would
report. `address` is the full guest address, so a caller feeds a
listing straight back to `get-file` without composing a path of
its own — the same vocabulary out as in (**P17**). The array is
flat rather than nested because a tree costs every binding a
walker and buys nothing a full address does not already carry
(**P7**).

```powershell
rlq put-file .\JOB.BAT "A:\JOB.BAT" --machine freedos-0
rlq get-file "A:\RESULT.TXT" .\result.txt --machine freedos-0
rlq put-files .\suite "A:\" --machine freedos-0
rlq list-files "A:\" --recursive --machine freedos-0
rlq get-files "A:\OUT" .\results --machine freedos-0
```

### Reading a machine variable

```
rlq get-machine-var <key> (--blueprint <name> | --machine <id>)
```

Twin `get_machine_var`. Reads one machine variable — the script
`set` verb's channel back to the host — from the machine's state.
It works while the run is still going or long after it ends, and
from any process, which is what makes it a readiness poll: a
consumer's own ready script `set`s a variable as its last step
and the driving program polls for it. Variables are cleared at
each `start`, so a value always reports the current boot. There
is no `set-machine-var` command: writing is the script verb's,
and the host side only reads.

### The machine directory

```
rlq get-machine-dir (--blueprint <name> | --machine <id>)
```

Prints the machine's cache directory —
`cache/machines/<id>/` as an absolute path — twin
`get_machine_dir()`, whose return is the path string (`--json`
serializes it like any other return). A query: it works in any
machine phase and touches nothing.

The path is the door to out-of-band file exchange, and it is no
longer a door anything needs: the in-band family covers single
files (`put-file` / `get-file`) and whole trees and listings
(`put-files` / `get-files` / `list-files`), so reaching in is a
convenience rather than a route (**P16**). While the machine is
stopped on every control
plane, its drives are plain host state — a drive whose media is a
directory *is* that directory, and image drives are readable and
writable with the user's own tools. Reliquary neither mediates nor records
out-of-band access. The contract, including what stays
untouchable (`cache/media/` payloads), lives
in the [instance model](instance-model.md).

```powershell
rlq get-machine-dir -b freedos
# → D:\OneDrive\Documents\reliquary\cache\machines\freedos-0
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

### Recorded interaction runs — backlog (D36)

The `begin-run` / `end-run` bracket that records a primitive-driven
loop into one persisted run record is part of the record model,
which moved to the asynchronous-runs backlog with the rest of
persistence (D36; proposed/FEATURES.md "Asynchronous runs").
Milestone 9 stores nothing: the interaction commands each *return*
their output, and a caller wanting a record collects those returned
outputs in its own code (the driving program is the record). The
bracket returns if the async work schedules.

---

## Scripts

### Listing scripts

```
rlq list-scripts
```

`list-scripts` shows everything in `scripts/`. Searching scripts
is unbuilt — the codex index it would query is itself planned
([codex.md](codex.md)).

### Running scripts

```
rlq run-script <label> (--blueprint <name> | --machine <id>)
    [--property <key>=<value>]... [--properties <path>]
    [--display] [--detach] [--progress <mode>]
rlq check-script <label-or-name>
    [--blueprint <name> | --machine <id>]
    [--property <key>=<value>]... [--properties <path>]
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
rlq run-script install --blueprint freedos
```

Behind the scenes this:
1. Extracts `blueprints/freedos.rlqb`, its companion media
   definitions, and its scripts from the codex (skipping
   any that already exist).
2. Creates a machine from the blueprint.
3. Runs `scripts/freedos-install.rlqs`, which inserts
   the LiveCD, starts the machine, drives the install, and
   ejects the CD again as its final step.

When a script ends the machine stays in whatever state its last
step left it (the FreeDOS install script powers it off); run
another script against it or control it directly:

```powershell
rlq run-script verify --blueprint freedos
rlq stop-machine --blueprint freedos
```

`run-script` resolves the machine (creating one when `--blueprint`
names a blueprint with no machine yet), brings it to the state the
script's `machine:` header expects — starting a stopped machine
when the script expects `running` (the default), failing when a
`machine: stopped` script finds it running — then executes guest
steps. `--display` shows the backend's console
window. A repeatable `--property <key>=<value>` supplies an
explicit value for a script-declared property — the twins'
in-memory `properties=` mapping under parity — at the top of the
[property source order](script-spec.md#the-property-sources): it
beats even blueprint-fixed parameters, a key given twice is an
error, an undeclared key fails preflight, and a secret-typed key
is refused (argv enters process listings and shell history — the
`set-property` rule; use the environment or the credential
store). `RELIQUARY_PROPERTY_*` environment variables supply
standing values below the blueprint, and `--properties <path>`
selects the properties file, replacing the home's
`user.properties` for the invocation
([script properties](script-properties.md#property-sources)).

`--progress (auto | pretty | plain | jsonl)` selects the rendering
(default `auto`: resolved by whether stderr is a tty; `pretty`
forces the live tty
rendering elsewhere — CI logs that render ANSI, a pager). The
human modes render everything — live progress, the outcome, the
failure report — to stderr and leave stdout empty: the outcome
travels by exit code and, under `jsonl`, the returned event
stream on stdout. `jsonl`
is the programmatic
synchronous form: stdout carries the run's event stream as JSON
lines and nothing else — the last line is the terminal event, the
machine-readable result — diagnostics go to stderr, and the exit
code carries the outcome. `plain` and `jsonl` never prompt: an
unbound property fails preflight instead of hanging a program.

`check-script` runs preflight only: parsing, static control-flow
checks, capability preflight. With a machine selector, its
argument resolves exactly as `run-script`'s — label first, then
bare script name — and it also binds properties and checks media
resolution; without a selector there is no `scripts` map to
consult, so the argument is a bare script name. Read-only, no
guest steps.

```powershell
rlq run-script install --blueprint freedos --display
rlq run-script install --blueprint freedos --property identity.full-name="Paul Galbraith"
rlq run-script install --blueprint freedos --progress jsonl

rlq check-script freedos-install
rlq check-script install --blueprint freedos
```

### The run returns its output

A foreground `run-script` run streams its progress live and
**returns its output** to the caller — a value the program takes,
a rendering a person watches (D36). It stores nothing: there is
no run directory, no persisted record, and no `run` management
family (that whole record model — persisted runs, `run status` /
`run delete` / `list-runs`, the async followers and handle, and
interaction runs — is asynchronous-runs backlog work
(planning/proposed/FEATURES.md, D35/D36). Ctrl-C cancels the run
at the next event boundary (a `cancelled` terminal event, exit
`5`) and leaves the machine as-is.

The run's product is the caller's — the returned value, a file
retrieved in-band, a machine variable read with `get-machine-var`,
a disk image swapped out — kept and organized on the caller's own
side of the seam (P4, P18). The whole `run` family and the
detach/follow surface return only if the async work schedules
(drafted as U19).

---

## Media

`media` components describe installation media — where a payload
is located (a `url`+mirrors, a `local` path, or a member of an
`archive`), how it materializes, and the SHA-256 hashes that verify
it. They are components inside a blueprint `.rlqb`, not files of
their own; the codex seeds them inside the blueprints that use them.

### Listing media

```
rlq list-media
```

`list-media` shows the media names resolvable from the active
source (the `media` components across its `.rlqb` files) — a
plain name list, because the names are what drives and scripts
reference and what a program greps. `--verbose` adds each
media's owning file, its containment parent where it has one,
and its cache state; a media declared identically in several
files is one media and takes one row naming all of them
(identity-dedup shown, not contradicted). The anonymous inline
blank is never listed: it belongs to no namespace and nothing
can reference it (D30). `--verbose` adds the description and
source URL.

Searching media is unbuilt, like searching scripts: it would
query the codex index, which is planned ([codex.md](codex.md)).
`search-blueprints` is the one search that ships.

### Fetching and cleaning

```
rlq fetch-media <media_name>
    [--progress <mode>] [--on-mismatch (fail | refetch)]
rlq clean-media
rlq prune-media [--dry-run]
rlq add-media <name> <file>
```

`fetch-media` resolves a media by name and downloads, extracts,
and hash-verifies its payload. Machine operations resolving a
`media` reference fetch implicitly; `fetch-media` is the
standalone convenience. Media resolve against the same namespace
every command sees, so there is nothing a script would supply that
it does not already have. `--progress` selects
rendering as on `run-script` — pretty live progress on a tty under
`auto`; `jsonl` emits pure event JSON on stdout, the last line
the terminal event stating the outcome. `plain` and `jsonl`
never prompt: a hash mismatch without `--on-mismatch refetch`
fails fast. `--on-mismatch` mirrors the twin's `on_mismatch=`
parameter under the identity rule (media spec, "Mismatched
files"): `refetch` pre-approves delete-and-refetch, `fail`
forces the noninteractive failure even on a tty; an interactive
run without the flag gets the checkpoint prompt.

The media name is always required — exactly the twin
`fetch_media(name)` (a fetch-everything-for-a-script convenience
would be its own named growth if real use demands one).

```powershell
rlq fetch-media freedos-livecd
```

`clean-media` reclaims cached payload files under `cache/media/`
that Reliquary can re-fetch — blunt with no argument, targeted at
one media when named — skipping any payload a running machine has
attached. `prune-media` is the narrower cut: it drops only the
payloads outside the **attachment closure**, a container going
once its children are cached, and `--dry-run` reports what it
would reclaim without touching anything. Nothing irreplaceable —
`local` files, sourceless payloads — is reclaimable by either.

`add-media <name> <file>` is the supply half of authoring: it
computes the file's sha256 and writes `blueprints/<name>.rlqb`
declaring a media of that name located at that path. It **copies
nothing** and refuses to overwrite an existing blueprint — the
file stays where it is, and the declaration is what pins it
(D41). This is how a pinned-but-unlocated codex media gets a
local payload without hand-placing anything in the cache.

(There is no `delete-media`: media are components inside
a `.rlqb`, so removing one means editing the blueprint. The
command existed as a pure failure until D30 deleted it — the
noun in every media verb is the media, never its owning file,
and file lifecycle is the blueprint verbs' job.)

```powershell
rlq clean-media
rlq prune-media --dry-run
rlq add-media win98se D:\images\win98se.iso
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

Maintains the home-wide [user properties
file](script-properties.md),
`user.properties` —
API twins `get_property`, `set_property`, `unset_property`,
`list_properties` under the identity rule.
Ordinary values are strings; secret values live only in the host's
protected credential store, with a marker in the file. Every
property command accepts `--properties <path>` (twin parameter
`properties_file=`), selecting the file it maintains in place of
the home's `user.properties` — so a project-controlled file's
secret markers are provisioned like any other.

```powershell
rlq set-property username "paul"
rlq set-property product-key --secret
# tty: prompts for the value with no echo
# not a tty: reads the value from stdin
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
--secret` uses a no-echo prompt on a tty and otherwise reads the
value from stdin (to EOF, one trailing newline stripped, empty is
an error) — never an argument, which would enter process listings
and shell history. Kind changes — making a secret
ordinary or vice versa — require `unset-property` first.

---

## Flags and options

```
rlq <command> [args...] [--home-dir <path>] [--blueprint <name>]
    [--machine <id>] [--timeout <duration>] [--json]
```

Flags are the command's parameters, mirroring its API twin's
under the identity rule, and **position carries no meaning**: a
flag may appear before or after the command word —
`rlq run-script install --blueprint freedos` and
`rlq --blueprint freedos run-script install` are
identical. Synopses canonically show flags after the command.

Eight flags are accepted by every command, mirroring the API's
shared keywords. Six place Reliquary's working directories —
`--home-dir`, `--blueprints-dir`, `--scripts-dir`, `--cache-dir`,
`--media-dir`, `--machines-dir` — each also settable by
`RELIQUARY_<NAME>_DIR` in the environment; what none of them names
derives, and a bare invocation places all six under the default home
(`Documents/reliquary`). `--no-autoseed` (and its default-stating
twin `--autoseed`) decides whether a name the directories do not
hold may come from the built-in codex. `--json` is below. The full
model is
[asset-resolution.md](asset-resolution.md#the-working-directories).

`--blueprint <name>` and `--machine <id>` are the machine
selectors, mutually exclusive. On machine-scoped commands
(`create-machine`, `start-machine`, `stop-machine`,
`apply-blueprint`, `destroy-machine`, `recreate-machine`,
`clone-machine`, `export-drive`, `export-machine`, `run-script`,
the `run` operations,
`begin-run`, `end-run`,
`insert-media`, `eject-media`, `set-boot-order`,
`get-machine-dir`, and the
guest-console family `type`, `enter`, `press`, `exec`, `select`,
`screen`, `wait`, `screenshot`, `hmp`) at least one is required;
`run-script` auto-creates a machine when `--blueprint` names a
blueprint with none yet. `check-script` uses a selector for label
resolution and property binding when one is given. Commands that
don't operate on a machine (`list-*`, `search-*`, `fetch-media`,
the property family, `clean-*`, `new-blueprint`,
`delete-blueprint`, `seed-*`) ignore them.

`--timeout` sets a per-command timeout where applicable (runtime
defaults vary by command). It accepts the script language's
duration literals (`500ms`, `30s`, `20m` — one duration
vocabulary, defined in the script spec); a bare integer means
seconds. The API twins take numeric seconds natively — the
literal is CLI presentation, a named divergence like exit codes
beside exceptions.

### Output discipline

The result is stdout; everything else is stderr (owner,
2026-07-22). A result-bearing command's pretty stdout is exactly
the human rendering of what its twin returns — the same value
`--json` serializes — so tables, screen text, and printed ids
pipe clean with no flags. Progress, narration, warnings, prompt
text, and error reports live on stderr; stream-bearing commands'
human modes render everything there and leave stdout empty
(`jsonl` is the named exception: its stdout events *are* the
result). Prompting requires stdin and stderr to both be ttys —
prompt text on stderr, the answer from stdin. Diagnostics are
`rlq: <message>` with detail lines indented beneath, warnings
`rlq: warning: <message>`, and errors name the next command
where one exists. ANSI and color are emitted per stream, only
when that stream is a tty; `NO_COLOR` is honored; there is no
`--color` flag — `--progress pretty` forces live rendering at a
non-tty.

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
- Stream-bearing commands (`run-script` and `fetch-media`, the
  backlogged `run tail` with them) reject `--json`, naming
  `--progress jsonl`: a live run is an event stream, not a
  document — one flag, one meaning each.
- Secret property values never serialize; the JSON marker
  (`{"secret": true}`) stands in — the marker's `--json`
  spelling; the properties file spells it `@secret`.
- `--verbose` is a pretty-rendering concern: `--json` always
  carries the full record and never combines with it.

Field names are part of the CLI contract and land with each
twin's return contract. The stability contract is settled
(owner, 2026-07-22): the machine surfaces — exit codes, `--json`
documents, the `jsonl` event stream, run-record files — grow
additively only from 1.0 (an existing field never changes type
or meaning; consumers ignore unknown kinds and fields); pretty
and plain output are explicitly uncontracted, and pre-1.0
nothing is promised.

There is no bare-script shorthand: an unrecognized command word is
an error, never a script lookup. `run-script <label>` is the
tightest form — it keeps script names from colliding with present
or future subcommands.

The old `--qemu`, `--platform`, and `--port` global options belong to
the pre-blueprint single-machine model and are removed —
`--platform` is a blueprint field, `--qemu` is resolved by backend
assignment, and `--port` is a state detail.
