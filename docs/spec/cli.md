<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# CLI

> **Status:** normative. This document specifies the CLI — one of
> the four primary application surfaces, S1 (root ARCHITECTURE.md,
> "The application surfaces"). The implementation must match it:
> where this document and the code disagree, the code has the bug,
> unless the document is changed first through the surface-change
> rule ([planning/SURFACES.md](../../planning/SURFACES.md)).
>
> **Every command described here exists.** A command that doesn't
> exist yet is not documented here, no matter how settled its
> design is — unbuilt capability lives in
> [planning/proposed/FEATURES.md](../../planning/proposed/FEATURES.md).
> **The list of what exists is defined elsewhere**: the command
> manifest (`src/reliquary/schemas/command-manifest.toml`) declares
> every command, its API twin, its family mapping, and any
> exception, and a test (`tests/test_command_manifest.py`) checks
> both this document and the code against it on every commit. This
> document specifies behavior: what each command does, its flags,
> its output, and its exit codes — **and nothing more than that**
> (D119). A twin's return contract — which is also the command's
> `--json` contract — belongs to [api.md](api.md); a family's other
> rules (the script spec, the media spec, the blueprint and
> instance models, and so on) live wherever api.md's index points
> for that family. This document cites those other documents rather
> than repeating their rules, and if a passage here disagrees with
> the document it cites, that other document is correct and this
> passage is the bug.
>
> Some concepts introduced here are documented in full elsewhere:
> the codex, `seed`, naming conventions, and provenance in
> [codex.md](codex.md); the `description` and `scripts` blueprint
> fields in the
> [blueprint field reference](../blueprint-reference.md).

Every command corresponds to exactly one public API call, and is
**named after it**: a command's name is its API twin's name with
dashes instead of underscores (`create-machine` is `create_machine`),
and its flags mirror the twin's parameters (`--hdd-images` is
`hdd_images=`). Because the command is named directly from the
twin, the two can never drift apart. There are two declared
exceptions to this naming rule, and each is recorded in the command
manifest along with its reason: the guest-console family, which
uses the script language's own verb names instead, and the codex
family, which is CLI-only by decision (D87). The CLI resolves
`--blueprint` and `--machine` selectors into a machine; the API
takes the same identifiers directly. Any place where the CLI offers
something the API doesn't must be declared in the manifest — an
undeclared difference between the two is a bug.

**Selection.** Commands that act on a machine take a target
selector:

- `--blueprint <name>` — selects that blueprint's machine, but only
  when exactly one exists. If several exist, the command fails and
  lists the candidate ids. If none exist, the command fails and
  suggests `create-machine` (except `run-script`, which creates one
  itself instead of failing).
- `--machine <id>` — the full machine id, given exactly. There is
  no prefix matching and no bare-number shorthand: the id is the
  (blueprint, number) pair written out, so each selector has one
  clear meaning. Both selectors are resolved by one shared internal
  function, `resolve_machine(machine=, blueprint=)` — it isn't part
  of the public API and has no command of its own; the closest
  thing to a command form of it is `list-machines --blueprint`, which
  queries rather than selects.

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

**The codex.** Reliquary ships a set of blueprints (with their
media components) and scripts for popular open source operating
systems. In a source checkout these live as ordinary files under
`codex/blueprints/` and `codex/scripts/`; in a packaged distribution
they are bundled into a zip archive inside the Reliquary package.
Either way, the first time you reference a codex artifact that
doesn't yet exist in your home directory, Reliquary copies it out
for you. From then on it's an ordinary file you own — edit it,
delete it, put it under version control. If a file already exists
in your home, Reliquary never overwrites it: the codex only ever
supplies a starting copy, it isn't a place Reliquary keeps
re-reading from.

Deleting your copy is also how you get a fresh one: Reliquary never
touches a file already in your home, but once you delete it
yourself, the next reference to it (or running `seed-blueprint` /
`seed-script` explicitly) copies the current codex version out
again. The same thing happens if a blueprint refers to a script you
removed — that reference re-triggers the copy too.

So the fastest path to a working install is often one command, run
with nothing in your home directory yet: `rlq run-script install
--blueprint freedos` copies the blueprint (with its media inside
it) and its scripts out of the codex, creates a machine, and runs
the install — everything is created the first time it's needed.

### Named scripts

A blueprint may declare a `scripts` map — short labels that name
`.rlqs` script files. It may also carry an optional `description`
field so it can be found by browsing (the file's name without the
extension is the blueprint's one and only name):

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

Those labels are the words you pass to `run-script`:
`rlq run-script install --blueprint freedos` looks up
`scripts.install`, finds `freedos-install`, and runs
`scripts/freedos-install.rlqs`.

`description` is optional in both user blueprints and codex
blueprints. For the codex, Reliquary keeps an index mapping every
codex artifact to its description and its relationships to other
artifacts. For your own blueprints, Reliquary builds that index by
reading the `description` field straight out of each file.

### Scaffolding a blueprint

```
rlq new-blueprint <name> [flags]
```

Builds `blueprints/<name>.rlqb` from the flags you pass. Refuses to
run if the file already exists. `--platform` is required; every
other flag is optional. A field you don't pass a flag for is left
out of the file entirely, rather than written in with a default
value — that way the blueprint still tracks whatever the default
changes to later, instead of locking in today's default.

The result is an ordinary blueprint file that you own from that
point on.

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
    --hdd 20M --boot cdrom,hdd
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
      "boot": ["cdrom", "hdd"]
    }
  ],
  "media": [
    {"name": "blank-20m", "materialize": "new", "size": "20M"}
  ]
}
```

(The installer disc boots first, and the install script ejects it
once the hard disk is bootable. Firmware always skips an empty
optical drive, so you don't need to change the boot order after
install.)

**Pin to a backend, with a specific machine type:**

```powershell
rlq new-blueprint retro-pc --platform dos --backend qemu `
    --hdd 100M --memory 16M
```

`--hdd <size>` creates a `new` media of that size and a drive that
names it. For a hard disk using `difference` or `copy` (overlaying
or copying an existing payload), or one that attaches existing
media, edit the JSON file directly — or start from a codex
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
--control-planes <list>           comma-separated, e.g. vnc,agentless-display
```

For drives beyond the first slot, controller types, or anything
else the scaffolder doesn't cover, edit the JSON file directly.

### Seeding from the codex

```
rlq (seed-blueprint | seed-script) <name> [--only]
```

Copies artifacts from the codex into your home directory — API
twins `seed_blueprint(name, only=)`, `seed_script`. Existing files
are never overwritten. There is no `seed-media` command: media are
components inside a `.rlqb` file, so they get copied along with the
blueprint that declares them. (D30 removed the `seed-media` verb
entirely, rather than leaving it around as a command that does
nothing.)

- `rlq seed-blueprint <name>` — copies a blueprint (its media,
  source, and archive components come along inside it, since they're
  part of the same file) and every script named in its `scripts`
  map. This is the one command that pulls a whole codex artifact
  into your home in one go. `--only` limits it to just the blueprint
  file itself.
- `rlq seed-script <name>` — copies a single script.

```powershell
# Seed everything for a codex blueprint
rlq seed-blueprint freedos

# Seed individual artifacts
rlq seed-blueprint freedos --only
rlq seed-script freedos-install
```

After seeding, the files are ordinary documents you own — edit
them, put them under version control, delete them. This is how you
go from "just use the codex's version" to "I want to change it
myself." To get back to the current codex version, delete your file
and seed it again.

### Naming conventions

Codex artifacts follow a convention that ties them together by
blueprint and script:

| artifact | pattern | example |
|---|---|---|
| blueprint | `<name>.rlqb` | `freedos.rlqb` |
| script | `<blueprint>-<script-id>.rlqs` | `freedos-install.rlqs` |

Media are components inside the blueprint, not files of their own, so
they have component *names* rather than filenames. The convention is
`<blueprint>-<script-id>-<drive>` for a media that belongs to one
script's step (the installer CD it inserts, a driver disk it swaps
in), or a standalone `<name>` for a media shared across scripts or
blueprints. Both kinds resolve through the same namespace — the
naming convention just signals who owns a media, it doesn't put it
in a separate namespace.

### Listing blueprints, and listing the library

```
rlq list-blueprints
rlq list-codex
```

**Each command lists one set, and no command mixes the two.**
`list-blueprints` shows everything in `blueprints/` — your files,
and only your files. `list-codex` shows what the shipped codex
holds, and nothing of yours. So which command you ran tells you
where a row came from — there's no column reporting that, because
no single listing ever mixes the two sets.

```powershell
$ rlq list-blueprints
NAME     PATH                                             DESCRIPTION
freedos  C:\Users\you\Documents\reliquary\blueprints\freedos.rlqb  Plain FreeDOS 1.4 system installed from the LiveCD
test-rig C:\Users\you\Documents\reliquary\blueprints\test-rig.rlqb

$ rlq list-codex
NAME     DESCRIPTION
freedos  Plain FreeDOS 1.4 system installed from the LiveCD
openbsd  OpenBSD 7.9 amd64 installed from install79.iso using autoinstall over
         reliquary's run-scoped HTTP server
```

When a listing includes descriptions — `list-codex`, `list-scripts`,
`list-blueprints` — the human-readable table adds a `DESCRIPTION`
column next to each item's row. The table library (Rich) wraps that
cell to the terminal width instead of truncating the text; entries
with no description just leave the column out. The `--json` output
carries the same field — `list-blueprints` rows carry `description`
and `platform` alongside `name` and `path` — so both presentations
show the same data. A terminal that supports UTF-8 gets rounded
table borders; any other terminal encoding gets a plain ASCII grid.

Neither command filters its results, and **no listing command has a
search flag or a search term** of its own: filtering by a search
term is what a shell's own tools do, and `--json` makes that easy in
any programming language, so adding a separate search flag to each
listing command would just duplicate that without adding anything.

Nothing resolves outside your own directories plus the library. If a
name isn't in your directories, it isn't found — and the error
message names the fix, when the library happens to have that name:

```
$ rlq run-script install --blueprint freedos
rlq: blueprint not found: freedos
expected under C:\Users\you\Documents\reliquary\blueprints
the codex has one: rlq seed-blueprint freedos
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

A machine is a disposable, running (or stopped) copy of a blueprint,
identified by `<blueprint>-<n>` and stored entirely under
`cache/machines/<blueprint>-<n>/`. Everything under `cache/` belongs
to Reliquary and can be thrown away — it's regenerated from
blueprints (media components included) and scripts. A run doesn't
store anything here; it returns its output directly to the caller
(D36).

Every machine command has the same name as its API twin, with
dashes for underscores: `create-machine` is `create_machine`, and
the same goes for `start-machine`, `stop-machine`,
`apply-blueprint`, `destroy-machine`, `recreate-machine`, and
`delete-blueprint`. The mobility commands — `clone-machine`,
`export-drive`, `export-machine`, `import-vm` — don't exist yet:
their names are settled, and their design is written up in
[api.md](api.md) (which describes the intended end state, not
today's behavior) and in planning/proposed/FEATURES.md, "Machine
mobility".

### Creating a machine

```
rlq create-machine --blueprint <name> [--dry-run [--backend <name>]]
```

Looks up `<name>` as a blueprint in `blueprints/`. If the file
doesn't exist there but is available in the codex, Reliquary copies
it out — along with any scripts it references that aren't already
present (its media come along inside it, since they're part of the
same file). Existing files are never overwritten.

Reliquary then validates the blueprint, assigns a backend (if the
blueprint doesn't declare one), picks the lowest free machine number
for that blueprint, creates the machine under
`cache/machines/<blueprint>-<n>/`, and prints the new id:

```powershell
$ rlq create-machine --blueprint freedos
created machine freedos-0
```

The printed id identifies the machine — use it with `--machine`, or
select by `--blueprint` when it's the only machine for that
blueprint:

```powershell
rlq start-machine --machine freedos-0
rlq start-machine --blueprint freedos
```

`create-machine` reads the blueprint once, at creation time, and
records that snapshot as the machine's *baseline*. From then on the
machine's own saved state is what's authoritative — a script's
`insert`/`eject` steps are saved into it — and `start-machine` never
re-reads the current blueprint file. Editing the blueprint only
affects machines created after the edit. To bring the edits into an
existing machine (or to reset a machine that has drifted back to
its blueprint's shape), use
[`apply-blueprint`](#applying-blueprint-edits).

#### The dry run

`--dry-run` performs every step that costs nothing and commits
nothing, stops at the first step that would cost something or
commit something, and reports what it would have done. Its API twin
is `create_machine(name, dry_run=True)`, which returns a `DryRun`
object rather than a machine id, so a caller can never mistake a dry
run's result for a real machine.

Two rules define what it does:

- **It leaves no state behind.** No machine directory, no
  `machine.json` file, no disk image, no fetched payload file, no
  lock file — and nothing is seeded from the codex either, which is
  now true of every operation, not just this one (D88). A blueprint
  name that only exists in the codex library, not in your own
  directories, is refused the same way a live run refuses it, naming
  the seed command to fix it, rather than being read out of the
  library.
- **Its return value describes the run; it never pretends to be the
  run's actual output.** What comes back is a plan, a report, and a
  verdict. Fabricating what the guest OS would have output is a
  completely different thing, and is deliberately not something this
  does.

It checks the blueprint parses, resolves the namespace, checks the
reference closure, checks drive and media compatibility, checks
backend capability, checks slot limits, works out the machine id it
would allocate, and works out each drive's plan — for `new`: the
size and image path; for `use`: which payload; for `difference` /
`copy`: which base it would build on. It stops before creating the
machine directory or `machine.json`, before creating any image, and
before fetching anything.

**Media are resolved, but never fetched.** Each one is reported as
`cached`, `would-download`, `would-extract`, `local-present`, or
`unbound`. A container media is listed only when the child media
that comes out of it isn't already cached — the same rule
`prune-media` uses to decide what it can reclaim. Nothing is hashed:
`cached` only means the file is present in the cache, not that it's
the right file. A byte size is shown only when something on this
host already knows it, so a `would-download` entry shows its URL and
its pinned `sha256` hash, but no size.

**A dry run refuses anything a real create would refuse, at the same
point a real create would refuse it** — so if the verdict is "this
would fail," the dry run itself fails, and its error message is the
answer. One kind of problem is collected instead of stopping at the
first instance: every missing *local* payload is named all at once,
because finding all of them is exactly what this pass is good at,
and stopping at the first one would mean a separate fix-and-rerun
cycle for each. There are exactly two things a dry run will not
refuse, and in both cases that's because it genuinely can't check
them — not because they're being treated as unimportant:

- **It never prompts for input.** A media location that no concrete
  source can answer is reported as `unbound`, with the key named,
  and the properties section notes that a real create would have
  prompted here.
- **Under `--backend`, a missing backend is reported, not treated as
  a failure** (explained below).

`--backend <name>` overrides the blueprint's `backend` field, fixing
the backend at machine-creation time: the named backend must be
available and capable on this host, and it fails outright if either
is not true — the same as when the blueprint itself declares a
`backend`. Under `--dry-run` the question being asked is different:
would the blueprint work on that backend, in principle. So **what
decides is the backend's capability, and the backend doesn't need to
be installed on this host at all** — if it isn't, that's reported,
not treated as a failure. This is the U7 contract, checked
statically: what's being checked is capability, not whether the
backend is actually present, and it still fails outright by name if
the backend lacks the needed capability.

```powershell
$ rlq create-machine --blueprint freedos --dry-run
create-machine freedos --dry-run

machine: freedos-0 (lowest free)
directory: ...\cache\machines\freedos-0
backend: qemu (priority walk)
platform: dos
memory: 32
cpus: 1
boot: hdd0, cdrom0
control planes: agentless-display
drives:
  cdrom0 (cdrom slot 0 ide): empty
  hdd0 (hdd slot 0 ide): (inline) new 20M -> ...\disks\hdd0.qcow2

nothing was created.
```

`--json` prints the `DryRun` object itself — `operation`, `report`,
and the `plan` document — following the general rule that a
command's `--json` output is exactly what its API twin returns.

### Starting and stopping

```
rlq start-machine (--blueprint <name> | --machine <id>) [--display]
rlq stop-machine [<id>] (--blueprint <name> | --machine <id>)
rlq restart-machine [<id>] (--blueprint <name> | --machine <id>) [--display]
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

Every `start-machine` reconciles the backend to match the machine's
saved state — checking the backend is really the one recorded, and
re-checking every media file's hash, including media a script
attached. Machines stay running until something explicitly stops
them: `stop-machine`, a script step, or the guest OS shutting itself
down.

`restart-machine` is **a single operation, not two commands run back
to back**: it holds the per-machine operation lock across both the
stop and the start, so nothing else can start the machine, change
its media, or apply a blueprint in between. This isn't a new kind of
guarantee — it's the same lock every state-changing operation
already takes, just not released partway through — and it's what
stops a restart from landing on a machine someone else already
started in the meantime and failing with `machine.already-running`.
If the machine is **already stopped, `restart-machine` just starts
it** rather than refusing — the goal state you asked for is
*running*, so the command doesn't need to know or care what phase
the machine was in before. A machine caught mid-`stopping` is
brought to a clean state first, exactly as `stop-machine` or
`start-machine` alone would do.

### Applying blueprint edits

```
rlq apply-blueprint (--blueprint <name> | --machine <id>)
```

Applies the current blueprint's changes to a stopped machine. Any
change the machine can absorb without regenerating a drive — memory,
boot order, drives enabled or disabled, a media name changed to
point elsewhere, a `use` media re-fetched, drives added — is applied,
and the machine's baseline digest is updated to match:

```powershell
# Edit freedos.rlqb: disable the CD, boot from hard disk
rlq stop-machine --blueprint freedos
rlq apply-blueprint --blueprint freedos
rlq start-machine --blueprint freedos
```

A change the machine can't absorb — a changed `size` or
`materialize` on a media image that already exists — is refused
outright, rather than partly applied:

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

`destroy-machine` deletes the machine entirely: its cache directory
and the machine as the backend knows it. If it's running, it's
stopped first, holding the per-machine lock across both steps, the
same way `restart-machine` does. The blueprint file itself is never
touched.

`recreate-machine` is destroy followed by create, run as one command
under the same id. Each drive is regenerated fresh according to what
its media declares: a `new` media comes back blank, a
`difference`/`copy` media comes back as a fresh overlay on (or copy
of) its payload. If the blueprint doesn't pin a `backend`, the
recreated machine may land on a different backend than before — this
is the supported way to move a machine from one backend to another.

```powershell
rlq destroy-machine --blueprint freedos
rlq recreate-machine --blueprint freedos
# same id, fresh materialization
```

```powershell
rlq recreate-machine --machine freedos-0
# destroys freedos-0, creates new freedos-0 from its blueprint
```

(There is no `clean-machines` command, because the machine family
isn't a cache family in the sense `clean-media` cleans. A media
payload can be reclaimed because it comes back identical — it's
pinned, so re-fetching it gives you the same bytes back — and that's
all `clean-media` promises. A machine directory *is* the machine: its
disks hold whatever an install and every run since has put there,
and recreating it only brings back the blueprint's blank starting
shape, not that history. So reclaiming a machine means destroying
it — a choice P1 allows and leaves to the user, one machine at a
time with `destroy-machine`. To destroy several at once, loop over
`list-machines --json` from the shell — that's the general answer
D88 gives whenever a command needs to act on a set of things. That
machines live under `cache/` by default just says where they live,
not what they are; `--machines-dir` can place them anywhere.)

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

On every command that acts on a machine, `--blueprint <name>`
selects that blueprint's machine when exactly one exists — the
common case of one machine per blueprint:

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

Commands for sending input to the guest, running guest commands, and
inspecting the guest's screen. This is the one place the naming rule
works differently: these commands use the script language's own verb
names instead of an API twin's name
([script-spec.md](script-spec.md), "Input verbs") — the same
capability is spelled the same way on both the script and the CLI,
each verb is defined once, in the script spec, and the CLI just
refers to that definition rather than redefining it. The CLI adds
exactly three commands that scripts deliberately don't have: `screen`
(scripts observe the screen as part of a wait; a human or a program
reads it directly), `wait-ready` (waits for the named evidence that
the platform is ready; inside a script, "ready" is whatever the
script's own wait condition says it is), and `exec` (a convenience
that combines several steps; inside a script, you observe completion
explicitly instead).
Every interaction command requires `--blueprint <name>` or
`--machine <id>` to say which machine it targets. There's no "active
machine" shortcut. These commands don't have API twins yet — that's
part of the not-yet-built control-plane design ([api.md](api.md)) —
but the same capability is available today through the `Machine`
class's own functions. Each command returns its own output.
Recording a sequence of them into one saved record (`begin-run` /
`end-run`) is planned but not yet built (D36; see "Recorded
interaction runs — backlog" below).

### Typing and pressing keys

```
rlq type <text> (--blueprint <name> | --machine <id>)
rlq enter <line> (--blueprint <name> | --machine <id>)
rlq press <key>... (--blueprint <name> | --machine <id>)
```

`type` sends raw text with nothing appended at the end. `enter`
types the line and then presses Enter (it's built from `type` in the
script language). `press` sends key names from the script language's
fixed, portable list of keys, with `+` combining several into a
chord. The key names and how they're delivered are defined in the
script spec — the CLI doesn't add any keys of its own, and there
are no per-platform variants.

```powershell
rlq type "A:" -b freedos
rlq press enter -b freedos
rlq enter "dir C:\" -b freedos
rlq press ctrl+alt+delete -m freedos-0
```

### Reaching the prompt

```
rlq wait-ready (--blueprint <name> | --machine <id>)
    [--timeout <seconds>] [--prompt <text>]
```

API twin: `wait_ready`. `start-machine` returns as soon as the
backend is up, not when the guest OS is ready — the boot process is
what happens in between. `wait-ready` waits out the boot until the
platform workflow's own readiness evidence appears — on DOS, that's
a prompt on the bottom row of the screen. This means a harness only
needs one command between `start-machine` and its first `exec`, and
that command doesn't need to spell out any screen pattern of its own
(D114). `wait-ready` is `exec`'s precondition, as a command you run
without needing a script: for a workflow where "ready" means more
than just a prompt — a driver has to be bound, a TSR has to be
resident — the codex supplies a `ready` script instead, which states
its own readiness condition in script form, waits for it, and sets a
variable the host reads.

**What counts as a prompt here is almost the same as what `exec`
knows, minus one thing.** `exec` recognizes either the standard DOS
prompt or exactly the prompt the guest was already showing when the
command was typed (D112). `wait-ready` has no earlier screen to read
a customized prompt from, so the caller has to declare it (D113):
`--prompt <text>` is the exact text the guest draws on the bottom
row, and the standard prompt shape is still recognized alongside it.
A time-bearing prompt (one using `$T`) can never match declared text,
so `wait-ready` is stated to leave that case unhandled. `wait
"C:\>"` is a different kind of wait — it matches that pattern
anywhere on the screen, and it's the general-purpose wait you'd
author for any other kind of boot-time evidence.

```powershell
rlq start-machine -b freedos
rlq wait-ready -b freedos
rlq exec "ver" -b freedos

rlq wait-ready -b custom-dos --prompt "[C:\]>" --timeout 180
```

**A prompt appearing on screen does not by itself mean the machine
is ready** (D115). The boot sequence is the point where the screen
is most likely to still be changing — for example, an `AUTOEXEC.BAT`
with `ECHO ON` draws the prompt and then the command on the same
row, and the standard prompt shape matches that row while it's still
mid-draw. So a prompt is only a candidate for readiness until the
screen underneath it has stopped changing — the same "wait until
the screen settles" rule that `exec` uses to decide a command has
completed, and that the script language's `wait` applies to every
observation (F45). Whatever the caller does next doesn't change
whether the screen had actually finished changing. There's no
`stable=`/`stability=` flag to tune this on the command, just as
there's none on `exec` — that setting belongs to the script
language, not the CLI.

**A wait that times out exits with code `4`**, the same as
`wait-machine-var`. The API twin raises `WaitExpired`, which is
both a `RunFailure` (the work didn't happen) and Python's own
`TimeoutError` (nothing about the machine is actually wrong, and the
boot might still finish, so a caller running its own retry loop can
catch this and ask again). The error message names what it was
waiting for, including the case where a prompt *was* on screen but
the screen underneath it never settled — a screenshot taken at that
moment shows the prompt plainly, even though the wait still timed
out. A machine that isn't running, or whose platform has no
workflow built yet, is refused before any screen is even read — this
is a preflight check, the same as for `exec`.

### Executing guest commands

```
rlq exec <command> (--blueprint <name> | --machine <id>)
    [--timeout <duration>] [--check]
```

`exec` combines `enter` with the platform workflow's own way of
detecting that a command has finished (on DOS, that's based on the
prompt reappearing). The script language deliberately has no
equivalent verb — inside a script, you observe completion
explicitly instead — but for interactive use, combining the two
steps into one command is worth it, and it lets the platform own the
completion-detection logic instead of making every caller reimplement
it. `exec` is a CLI and API capability built on top of the script
language, not a concept the language itself has.

**"Completed" means this specific command has finished** — it does
not just mean a prompt is visible, because the guest was already
sitting at a prompt before the command was even sent. So detecting
completion needs evidence that this command actually ran, and a
prompt that reappears is only a candidate until the screen underneath
it has settled (F45; D75) — because if `exec` read a prompt that
appeared mid-scroll, it could cut the command's output off at a
point that was never a real boundary. What `exec` returns is either
the command's own output or a failure — never text it can't actually
attribute to that command. A command whose output scrolls past a
full screen leaves only its final visible portion, which is the
documented limit of agentless screen capture, and that's what's
returned. Output that can't be tied to the command at all is
reported as `screen.no-echo`, because guessing at a plausible-looking
set of rows that actually belong to something else would be worse
than just reporting an error (**P11**).

**What counts as an echo, and what counts as a prompt** (D111, D112).
The command is typed at the prompt the guest was already sitting at,
so its echo is that same prompt row with the command text appended
— wrapped to the screen's width if it's longer than one row — and it
sits *exactly where the prompt was*: the rows above it are the rows
that were above the prompt before, minus whatever has scrolled off
since. A row that merely looks like an echo (for example, a file
whose last line happens to read `C:\>TYPE C:\ECHOLIKE.TXT`, printed
by the very command that reads that file) is never mistaken for one,
because what's above it is recognizably the command's own output,
not a prompt. Completion is detected as the prompt coming back, and
only in one of two exact shapes: the **standard DOS prompt**,
`X:\path>` (which is what lets `CD` be detected as complete even
after it changes the prompt's own text), or **exactly the prompt the
guest was already showing** when the command was sent, whatever
shape that prompt has — so a guest whose `AUTOEXEC.BAT` sets `PROMPT
[$P]$G` works from the very first command, with nothing declared up
front. **There is one known limit, and it's stated rather than
hidden**: a command that changes a customized prompt — `PROMPT`
itself, or `CD` while under one — leaves `exec` with no evidence to
match against, since the text it returns to isn't either of the two
recognized shapes, and the wait times out (`screen.no-match`), naming
both shapes it was waiting for. There is no way today to declare a
prompt pattern for this case.

```powershell
rlq exec "ver" -b freedos
# → FreeDOS kernel 2043 (Build 2043) [compiled Feb 26 2021]
rlq exec "dir C:\*.exe" -b freedos --timeout 120
```

**`--check` adds the one thing the screen text alone can't tell
you: whether the command actually succeeded.** A setup command —
loading a driver, installing a TSR — usually produces no output
worth reading, and its success is the entire point of running it. So
without `--check`, success and failure look identical, and a driver
that was refused only shows up later, as every command after it
fails in some unrelated-looking way. With `--check`, a command that
reported failure raises `RunFailure` naming the command (exit code
`4`); the output `exec` returns is the same either way, so `--check`
adds a separate signal rather than changing how the existing output
is read. It's **opt-in** because checking a command's outcome costs
an extra command sent to the prompt.

```powershell
rlq exec "D:\DRIVER.EXE" --check -b driver-rig   # exit 4 if it refused
```

How this check is actually done belongs to the platform workflow. On
DOS it's an `IF ERRORLEVEL 1` probe with a sentinel word Reliquary
composes and reads back — `IF ERRORLEVEL` is used because it's
portable across DOS shells, unlike `%ERRORLEVEL%` expansion, which
isn't. This doesn't read any meaning into the guest's own output
(**G2**, **P18**): the sentinel is a word Reliquary wrote itself,
not something the command produced — exactly like how prompt
detection already reads the screen only for Reliquary's own
protocol, not for guest-authored content.

**`--check` only covers commands that ran and reported failure
through this mechanism**, and that limit is stated plainly rather
than glossed over (**P11**). `COMMAND.COM` leaves ERRORLEVEL
untouched when it can't find a program to run at all, so a mistyped
command slips past the probe and reads as success. Recognizing the
shell's own "Bad command or file name" text instead would mean
Reliquary maintaining a list of exact guest-output messages to
recognize — an open-ended list, since a localized copy of DOS prints
localized messages — which is exactly the kind of guessing **P10**
rules out. A mistyped command is treated as an authoring mistake,
to be caught while authoring the script, not by `--check`. And if
the probe's own answer can't be read at all, that's reported as
`command.outcome-unreadable`, not treated as a pass — an outcome
Reliquary can't determine is never counted as success.

### Observing the screen

```
rlq screen (--blueprint <name> | --machine <id>)
rlq wait <condition> (--blueprint <name> | --machine <id>) [--timeout <duration>]
rlq screenshot [<name>] (--blueprint <name> | --machine <id>)
```

`screen` prints the current text screen (80x25 rows on VGA guests)
— it's the read-only command form of the same observation the
script language does by default. `wait` **is the script language's
`wait` verb**, taking one condition, and its argument is parsed by
the language's own parser (D116) — the CLI has no separate condition
grammar of its own. **The shell strips off the language's outer
quotes**, so what `wait` actually sees is the condition with those
quotes removed: plain text is treated as a normalized literal,
`/.../` as a regex, `machine=stopped` as the machine-state channel,
and text that still carries its own quotes (because you quoted it
that way) is taken exactly as written. A literal condition matches a
normalized substring of one visible row, and a regex is searched
within one normalized row — trailing padding trimmed, runs of
whitespace collapsed to one space, never matching across rows
([script-spec.md](script-spec.md#normalized-text-matching)). A
`${key}` inside the text is the language's property-reference syntax,
and it's refused here, because properties belong to scripts, not to
this CLI command. A match is only a candidate until the screen
underneath it has settled, exactly as in a script (F45; D115).
`machine=stopped` — how you wait out the guest powering itself off
— completes when the backend reports the VM is gone, and the
machine's recorded phase is then reconciled the same way a script's
own observation reconciles it; a machine that's already stopped
satisfies this immediately. `screenshot` captures the framebuffer as
an image.

**A wait that times out exits with code `4`** (`WaitExpired`, both
a `RunFailure` and a `TimeoutError`, D90). The error message says so
if a matching row was on screen but the screen underneath it never
settled.

```powershell
rlq screen -b freedos
# 25 lines of screen content printed to stdout

rlq wait "C:\>" -b freedos --timeout 30
# blocks until a row holds the DOS prompt and the screen settles

rlq wait "/installed [0-9]+ of [0-9]+/" -b freedos
# the regex spelling, quoted for the shell

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
visible label, exactly the way the script language's `select` does:
it finds candidate rows matching `<item>`, rejects any row
containing text passed to `--exclude`, moves the highlight while
watching for observable feedback that it actually moved, and then
presses Enter. It reports a named failure — rather than guessing —
if there are zero matching candidates, several candidates still
remaining, no way to detect the highlight, or if moving the
highlight makes no observable progress.

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

These commands are named after their API twins — `insert_media`,
`eject_media`, `set_boot_order` — rather than after the script
language's verbs, because they change durable machine state, not
just the live console. (The script verbs `insert` / `eject` /
`set-boot` are the in-script spellings of these same operations, and
their rules apply here by reference.) `insert-media` and
`eject-media` only work on the removable slots a blueprint declares
(floppy and CD-ROM; slot names come from the blueprint reference),
and both work whether the machine is running or stopped. Inserting
into a slot that's already occupied fails, and so does ejecting an
empty slot; a slot that doesn't exist, or isn't removable, fails
before anything is touched. `set-boot-order` replaces the whole boot
order with the drive keys you list (either their canonical or alias
form, duplicates rejected, and every key must name a declared drive)
and requires the machine to be stopped. The CLI's `<media>` argument
is a bare media name — the `@` marker for references is only used
inside script text, not on the command line. Every change here is
written into the machine's own state document, not into its
blueprint, and it persists across a stop and start: the machine is
allowed to diverge from its blueprint this way until either a later
change restores it, or `apply-blueprint` reconciles it back to the
blueprint's shape.

```powershell
rlq insert-media cdrom0 freedos-livecd -b freedos
rlq stop-machine -b freedos
rlq set-boot-order cdrom0 hdd0 -b freedos
rlq start-machine -b freedos
```

### Reading and waiting on a machine variable

```
rlq get-machine-var <key> (--blueprint <name> | --machine <id>)
rlq wait-machine-var <key> [<value>] (--blueprint <name> | --machine <id>)
    [--timeout <seconds>] [--interval <seconds>]
```

API twin: `get_machine_var`. Reads one machine variable from the
machine's saved state — this is the channel the script `set` verb
uses to report values back to the host. It works whether the run is
still going or finished long ago, and can be called from any
process. Variables are cleared every time the machine starts, so a
read always reflects the current boot. There is no `set-machine-var`
command: writing a variable is something only a script does, and the
host side only ever reads.

`wait-machine-var` (API twin: `wait_machine_var`) does the same
read, but on a loop, and it exists for the one case a plain read
can't handle: **when something else is setting the variable.** A
`run-script` run doesn't return control to the caller until it's
finished, so by the time it returns, every variable it was ever
going to set has already been set — there's nothing left to wait
for, and you'd use `--expect` there instead. A wait is for a
variable that some other actor sets: a run being driven from another
thread, or a run you're only watching rather than the one driving
it. If you omit `<value>`, the wait is satisfied by any value at
all, which is what you want for a plain readiness check.

**A wait that times out exits with code `4`.** The API twin raises
`WaitExpired`, which is deliberately both a `RunFailure` and
Python's own `TimeoutError`: the wait not finishing counts as the
work not having happened, so it gets the ordinary failure exit code
— but nothing about the machine is actually wrong, and the value
might still show up later, so a caller running its own retry loop
can catch `TimeoutError` and try again. Exit code `1` is reserved
for bugs in Reliquary itself, and a timeout is never one of those.

### The machine directory

```
rlq get-machine-dir (--blueprint <name> | --machine <id>)
```

Prints the machine's cache directory — `cache/machines/<id>/` as an
absolute path. API twin: `get_machine_dir()`, which returns the path
as a string (`--json` serializes it like any other return value).
It's a read-only query: it works in any machine phase and doesn't
change anything.

**This is the only way Reliquary gives you to reach a machine's file
content, and that's deliberate, not a shortcut it happens to offer**
(D108). Reliquary never places a file on a machine's drives, never
reads one back, and never maps a drive to a guest-visible letter of
its own — getting files in or out of a machine is explicitly outside
what Reliquary itself handles (this is carved out by **P16**) — so a
caller that needs to move a file in or out gets the directory from
this command and uses its own tools on it. While the machine is
stopped, regardless of which control plane it uses, its drives are
just ordinary files and directories on the host: a drive whose media
is a directory *is* that directory, and an image drive is a raw or
qcow2 file that any disk-image library can open directly. Reliquary
doesn't mediate this access and doesn't record that it happened. The
full rules — including which files stay off-limits even here
(`cache/media/` payloads) — are in the
[instance model](instance-model.md).

Two other routes Reliquary supplies stay within its own machinery,
and neither one reaches inside a drive's own filesystem: a
**directory-source media** attaches a host directory as a drive
directly, and **`insert-media --file`** mounts an image the caller
built, while the machine is running (U20).

```powershell
rlq get-machine-dir -b freedos
# → D:\OneDrive\Documents\reliquary\cache\machines\freedos-0
```

### Raw HMP

```
rlq hmp <line> (--blueprint <name> | --machine <id>)
```

Sends a raw QEMU human monitor protocol (HMP) command — an escape
hatch that only works with QEMU. It has no meaning on other
backends, and once the control-plane design is settled, it will be
reclassified as a command explicitly scoped to one backend.

```powershell
rlq hmp "info status" -b freedos
rlq hmp "info block" -m freedos-0
```

### Recorded interaction runs — backlog (D36)

The `begin-run` / `end-run` pair, which would record a loop of
interaction commands into one saved run record, is part of the
record model — and that whole model moved to the asynchronous-runs
backlog along with the rest of persistence (D36; see
proposed/FEATURES.md, "Asynchronous runs"). As of Milestone 9,
nothing is stored: each interaction command just *returns* its own
output, and a caller that wants a record has to collect those
returned outputs itself, in its own code — the program driving the
commands is the record, for now. `begin-run` / `end-run` will come
back if and when the asynchronous-runs work gets scheduled.

---

## Scripts

### Listing scripts

```
rlq list-scripts
```

`list-scripts` shows everything in `scripts/`. Its `DESCRIPTION`
column shares the script's row and wraps wide text to the terminal.
Searching scripts is unbuilt — the codex index it would query is itself planned
([codex.md](codex.md)).

### Deleting a script

```
rlq delete-script <name>
```

Removes the script's `.rlqs` file. Refuses while any blueprint
refers to it, listing their names:

```
$ rlq delete-script freedos-install
rlq: script 'freedos-install' still has 1 blueprint(s):
  freedos
edit them to remove the reference first, then delete the script
```

### Running scripts

```
rlq run-script <label> (--blueprint <name> | --machine <id>)
    [--property <key>=<value>]... [--properties <path>]
    [--display] [--progress <mode>]
    [--expect <key>=<value>]... [--record <path>]
rlq run-script <label-or-name> --dry-run
    [--blueprint <name> | --machine <id>]
    [--property <key>=<value>]... [--properties <path>]
```

A script is a `.rlqs` file under `scripts/`. `run-script <label>`
first looks up `<label>` in the blueprint's `scripts` map (labels
are short verbs, like `install`, `verify`, `test`, `configure`).
When there's no matching label, `<label>` is instead taken as a bare
script filename, and `scripts/<label>.rlqs` is run directly. A
matching label always wins over treating the argument as a bare
filename.

If a script that's referenced doesn't exist in `scripts/` but is
available in the codex, Reliquary copies it out, along with any
media definitions it's missing, before running it. Existing files
are never overwritten.

**One-shot install — the common case:**

```powershell
rlq run-script install --blueprint freedos
```

Behind the scenes this:
1. Copies `blueprints/freedos.rlqb`, its media definitions, and its
   scripts out of the codex (skipping anything that already
   exists).
2. Creates a machine from the blueprint.
3. Runs `scripts/freedos-install.rlqs`, which inserts the LiveCD,
   starts the machine, drives the install, and ejects the CD again
   as its final step.

When a script ends the machine stays in whatever state its last
step left it (the FreeDOS install script powers it off); run
another script against it or control it directly:

```powershell
rlq run-script verify --blueprint freedos
rlq stop-machine --blueprint freedos
```

`run-script` resolves the machine (creating one if `--blueprint`
names a blueprint that doesn't have one yet), brings it to the state
the script's `machine:` header expects — starting a stopped machine
if the script expects `running` (the default), or failing if a
`machine: stopped` script finds the machine running — and then runs
the script's guest steps. `--display` shows the backend's console
window. A `--property <key>=<value>` flag, which can be repeated,
supplies an explicit value for a property the script declares — this
is the same thing as the API twin's in-memory `properties=` mapping
— and it sits at the top of the
[property source order](script-spec.md#the-property-sources): it
overrides even a value fixed by the blueprint. Giving the same key
twice is an error, an undeclared key fails preflight, and a
secret-typed key is refused outright — command-line arguments show
up in process listings and shell history, which is exactly the
problem `set-property`'s own rule is there to avoid, so use an
environment variable or the credential store instead.
`RELIQUARY_PROPERTY_*` environment variables supply standing values
that sit below the blueprint in that order, and `--properties <path>`
picks a different properties file to use for this one invocation,
in place of the home directory's `user.properties`
([script properties](script-properties.md#property-sources)).

`--progress (auto | pretty | plain | jsonl)` picks how progress is
rendered. The default, `auto`, decides based on whether stderr is a
tty. `pretty` forces the live tty-style rendering even somewhere
that isn't a real terminal — CI logs that render ANSI codes, or a
pager. Both human-readable modes render everything — live progress,
the outcome, the failure report — to stderr and leave stdout empty:
the outcome is conveyed by the exit code, and, under `jsonl`, also by
the event stream returned on stdout. `jsonl` is the form meant for
programs: stdout carries the run's event stream as JSON lines and
nothing else — the last line is the terminal event, which is the
machine-readable result — diagnostics go to stderr, and the exit
code carries the outcome. Neither `plain` nor `jsonl` ever prompts
for input: an unbound property fails preflight instead of hanging a
program waiting on input it can't get.

`--dry-run` runs preflight checks only: parsing, static
control-flow checks, capability preflight. It starts no machine and
sends no guest input, and like every dry run, it seeds nothing,
writes nothing, and never prompts (see
[the dry run](#the-dry-run) for the rule both operations share).

**The selector (`--blueprint` or `--machine`) is optional here, and
nowhere else, because whether you give one decides which of two
checks you get.** If you give one, the machine is resolved exactly
as it would be for a live `run-script` — and the script argument is
resolved the same way too, checking for a matching label first, then
falling back to a bare script name — and the same machine-level
checks apply: properties are bound, media are resolved, and named
slots are checked. If you don't give one, there's no blueprint
`scripts` map to look the label up in, so the argument is treated as
a bare script name, and every rule that doesn't depend on a specific
machine still applies. These are the two checkable levels
([script spec](script-spec.md#static-and-dynamic-semantics)), and a
dry run is how you ask for either one.

A dry run stops short of **creating** a machine, so `--blueprint`
naming a blueprint with no machine yet has no machine to check the
machine-level rules against. The report states which of the two
levels it actually reached, rather than just the one you asked for.

**A dry run's result is a document, not a stream.** A live run's
output is its event stream, so `run-script` refuses `--json` and
renders through `--progress` instead. `--dry-run` returns a `DryRun`
object instead of a stream, so `--json` is allowed there and prints
exactly that object. `--progress` and `--display` are both refused
together with `--dry-run` — a plan has no stream to render and no
window to show.

The report names the timing plan, which source supplied each
declared property, and **how much of the script it could not check
statically**: a statement inside a handler only runs if the guest
actually triggers it, so the report states how many statements it
can't make any promise about, instead of implying a completeness
check that isn't actually possible.

```powershell
rlq run-script install --blueprint freedos --display
rlq run-script install --blueprint freedos --property identity.full-name="Paul Galbraith"
rlq run-script install --blueprint freedos --progress jsonl

rlq run-script freedos-install --dry-run
rlq run-script install --blueprint freedos --dry-run
```

### The run returns its output

A foreground `run-script` run streams its progress live and
**returns its output** directly to the caller — a value a program
can use, or a rendering a person watches (D36). It stores nothing:
there's no run directory, no persisted record, and no `run`
management family of commands. That whole record model — persisted
runs, `run status` / `run delete` / `list-runs`, the asynchronous
followers and handle, and interaction runs — is planned but not
built (planning/proposed/FEATURES.md, D35/D36). Ctrl-C cancels the
run at the next event boundary (producing a `cancelled` terminal
event, exit code `5`) and leaves the machine as it is, except for
the [scoped changes](script-spec.md#scoped-machine-state-changes)
the run puts back — the cancellation message names those.

What the run produces belongs to the caller: the returned value, a
machine variable read with `get-machine-var`, a disk image swapped
out and opened with the caller's own tools. Reliquary hands it over
and the caller is responsible for keeping and organizing it — that
division of responsibility is the boundary P4 and P18 draw: what
Reliquary owns (running the script, returning its output) stops
there, and what the caller does with the result is entirely up to
them. The whole `run` command family, and the ability to detach from
and reattach to a run, only come back if the asynchronous work gets
scheduled (drafted as U19).

### Recording a screen transcript

```
rlq run-script <label> (--blueprint <name> | --machine <id>)
    --record <path>
```

`--record <path>` writes a screen transcript to `<path>`: every
frame the run reads and every carrier call it makes, useful for
debugging a script or for building up a corpus of examples.
`run_script(record=<path>)` is the API twin.

This is a **tool for Reliquary's own maintainers, and the file it
writes is not something other code should depend on** (D98): the
`.rlqt` format has no specification of its own, no stability
guarantee, and no compatibility obligation, so changing it counts as
routine maintenance work, not a surface change. What *is* a surface
is the ability to invoke it at all — this flag and the `record=`
parameter — and those two are covered together (S1, S2). If you find
`.rlqt` files and go looking for a spec of their format, this is
where you should learn that none exists.

**A recorded run behaves differently from an unrecorded one, and
runs slower.** There's no way to sample the screen independently of
the run itself, because a backend only allows one control session at
a time — so the run's own polls are the capture, and turning on
recording makes those polls happen at the pace the transcript needs
rather than at the cheaper pace used in normal operation. Sampling
more often always captures strictly more information, but it isn't
free: each QEMU sample reads the guest's text memory, and sampling
ten times a second makes a FreeDOS install run two to three times
longer than it takes unrecorded. The transcript file records the
pace it was captured at, so it's never mistaken for how long the run
takes in normal operation.

**A secret's value reaching the guest stops the recording.** The
moment a secret property's value reaches the guest, capture stops
for the rest of the run, and the transcript records why. The frames
already written stay in the file, and nothing captured after that
point is added. This is the same rule that suppresses a failure's
automatic screenshot, applied to the other kind of file a run can
leave behind.

**`--dry-run` refuses `--record`** (exit code `2`,
`progress.record-on-a-dry-run`): a dry run never starts a machine or
reads a screen, so there'd be nothing to write. This is the fourth
flag refused on that same ground, alongside `--display`, `--expect`,
and a non-default `--progress` — a plan has no window to show, no
run outcome to guarantee, no stream to render, and no screens to
capture.

---

## Media

`media` components describe installation media: where a payload is
located (a `url` plus mirrors, a `local` path, or a member of an
`archive`), how it's materialized, and the SHA-256 hashes that
verify it. They're components inside a blueprint's `.rlqb` file, not
files of their own — the codex copies them out as part of the
blueprints that use them.

### Listing media

```
rlq list-media
```

`list-media` shows the media names that can be resolved from the
active source (the `media` components across its `.rlqb` files) — a
plain list of names, because names are what drives and scripts
reference, and what a program would grep for. `--verbose` adds each
media's owning file, its containing parent where it has one, and its
cache state; a media declared identically in several files counts as
one media and gets one row naming all of them (this is showing the
identity rule's deduplication, not contradicting it). The anonymous
inline blank media is never listed: it belongs to no namespace, and
nothing can reference it (D30). `--verbose` also adds the
description and source URL.

**No listing command has a search flag**, and none is planned — this
whole idea was dropped rather than half-built (D88). Filtering a
listing is the shell's job at a terminal, and `--json`'s job inside
a program, so a search flag on each command would just be a second
way of spelling what a pipe already does.

### Fetching and cleaning

```
rlq fetch-media <media_name>
    [--progress <mode>] [--on-mismatch (fail | refetch)]
rlq clean-media
rlq prune-media [--dry-run]
rlq add-media <name> <file>
```

`fetch-media` resolves a media by name and downloads, extracts, and
hash-verifies its payload. Machine operations that resolve a `media`
reference fetch it automatically, as a side effect; `fetch-media` is
the standalone command for doing that on its own. Media are resolved
against the same namespace every command sees, so there's nothing a
script could supply that `fetch-media` doesn't already have access
to. `--progress` selects the rendering the same way it does on
`run-script` — pretty live progress on a tty under `auto`; `jsonl`
emits pure event JSON on stdout, with the last line being the
terminal event that states the outcome. Neither `plain` nor `jsonl`
ever prompts: a hash mismatch without `--on-mismatch refetch` fails
immediately rather than waiting for input. `--on-mismatch` mirrors
the API twin's `on_mismatch=` parameter, following the naming rule
(media spec, "Mismatched files"): `refetch` pre-approves deleting and
re-downloading the file, `fail` forces the non-interactive failure
even when running on a tty, and running interactively without the
flag at all gets you the checkpoint prompt.

The media name is always required — this matches the API twin
`fetch_media(name)` exactly. (A convenience that fetches everything a
script needs in one call would be a separate, deliberately named
addition, if real usage ever demands one.)

```powershell
rlq fetch-media freedos-livecd
```

`clean-media` reclaims cached payload files under `cache/media/`
that Reliquary can re-fetch — with no argument it's a blunt
clear-everything, and with a name it targets just that one media —
skipping any payload a running machine has attached. `prune-media`
is a narrower operation: it only drops payloads outside what's still
needed — a container media is dropped once every payload extracted
from it is already cached on its own — and `--dry-run` reports what
it would reclaim without touching anything. Neither command reclaims
anything irreplaceable — `local` files or payloads with no source to
re-fetch from stay untouched by both.

`add-media <name> <file>` is the other half of authoring, the part
that supplies a file: it computes the file's SHA-256 hash and writes
`blueprints/<name>.rlqb`, declaring a media of that name located at
that path. It **copies nothing**, and it refuses to overwrite an
existing blueprint — the file stays exactly where it already is, and
the new declaration is what pins it in place (D41). This is how a
codex media that's pinned but has no local copy gets a real local
payload, without you having to hand-place anything in the cache
yourself.

(There's no `delete-media` command: media are components inside a
`.rlqb` file, so removing one means editing the blueprint directly.
A `delete-media` command used to exist and always failed, until D30
removed it — every media command's target is the media itself, never
the file it lives in, and managing that file's lifecycle is the
blueprint commands' job.)

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

These commands maintain the home-wide [user properties
file](script-properties.md), `user.properties` — API twins
`get_property`, `set_property`, `unset_property`, `list_properties`,
each named directly after its command. Ordinary values are stored as
strings; secret values live only in the host's protected credential
store, with just a marker left in the file. Every property command
accepts `--properties <path>` (in the API, this is the
`properties_file` field on the record a `Session` is opened with, as
required by P26), which selects a different file to maintain in
place of the home directory's `user.properties` — so a
project-controlled properties file gets its secret markers handled
the same way the home one does.

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
Listing properties or getting one never reveals a secret's actual
value. `set-property --secret` prompts for the value with no echo
when run on a tty, and otherwise reads the value from stdin (reading
to EOF, stripping one trailing newline, and treating an empty value
as an error) — it never takes the value as a command-line argument,
because that would put it in process listings and shell history.
Changing a property's kind — making a secret ordinary, or an
ordinary value secret — requires running `unset-property` on it
first.

---

## Flags and options

```
rlq <command> [args...] [--home-dir <path>] [--blueprint <name>]
    [--machine <id>] [--timeout <duration>] [--json]
```

Flags are a command's parameters, and they mirror its API twin's
parameter names. **Where a flag appears doesn't matter**: a flag can
come before or after the command word — `rlq run-script install
--blueprint freedos` and `rlq --blueprint freedos run-script
install` do the same thing. The examples in this document
conventionally show flags after the command, but that's just a
convention for readability, not a requirement.

Seven flags are accepted by every command, mirroring keywords shared
across the API. Six of them place Reliquary's working directories —
`--home-dir`, `--blueprints-dir`, `--scripts-dir`, `--cache-dir`,
`--media-dir`, `--machines-dir` — and each can also be set with an
environment variable instead: `RELIQUARY_HOME` for the home
directory, and `RELIQUARY_<NAME>_DIR` for each of the others.
Whichever of these six you don't set are derived from the ones you
did, and if you set none of them, all six default to living under
`Documents/reliquary`. There's no flag for whether a name may be
read straight from the built-in library, because none ever may: your
own directories are the only place Reliquary reads from, and the
only way anything reaches your directories from the library is
through `seed-blueprint` or `seed-script` (D88). `--json` is covered
below. The full directory-resolution model is documented in
[asset-resolution.md](asset-resolution.md#the-working-directories).

`--blueprint <name>` and `--machine <id>` are the two ways to select
a machine, and they're mutually exclusive. On any command scoped to
a machine — `create-machine`, `start-machine`, `stop-machine`,
`apply-blueprint`, `destroy-machine`, `recreate-machine`,
`clone-machine`, `export-drive`, `export-machine`, `run-script`, the
`run` operations, `begin-run`, `end-run`, `insert-media`,
`eject-media`, `set-boot-order`, `get-machine-dir`, and the
guest-console family (`type`, `enter`, `press`, `exec`, `select`,
`screen`, `wait`, `screenshot`, `hmp`) — at least one selector is
required. The one exception is `run-script`, which creates a machine
automatically when `--blueprint` names a blueprint that has none
yet. Under `--dry-run`, a selector is optional, and whether you give
one decides which of the two check levels you get: given one, it
resolves the script label and binds properties the same way a live
run would. Commands that don't operate on a machine at all
(`list-*`, `search-*`, `fetch-media`, the property family,
`clean-*`, `new-blueprint`, `delete-blueprint`, `seed-*`) ignore
both selectors.

`--timeout` sets a per-command timeout on the commands where it
applies (the default timeout varies by command). It accepts the
script language's duration literals (`500ms`, `30s`, `20m` — one
duration vocabulary, defined in the script spec); a bare integer
means seconds. The API twins take a plain number of seconds instead
— the duration literal is a CLI-only presentation detail, the same
kind of deliberate difference between the CLI and the API as exit
codes are to raised exceptions.

### Output discipline

The result goes to stdout; everything else goes to stderr (owner,
2026-07-22). For a command that returns a result, its plain
human-readable stdout output is exactly the human-readable rendering
of what its API twin returns — the same value `--json` serializes —
so tables, screen text, and printed ids pipe cleanly with no flags
needed. Progress, narration, warnings, prompt text, and error reports
all go to stderr; for commands whose output is a stream, the
human-readable modes render everything to stderr and leave stdout
empty (`jsonl` is the one exception: its stdout events *are* the
result). Prompting for input requires both stdin and stderr to be
ttys — the prompt text goes to stderr, and the answer is read from
stdin. Diagnostic messages are formatted as `rlq: <message>`, with
detail lines indented underneath; warnings are `rlq: warning:
<message>`; and error messages name the next command to run, when
there is one. ANSI codes and color are emitted per stream, only when
that particular stream is a tty; the `NO_COLOR` environment variable
is honored; there's no `--color` flag — use `--progress pretty` to
force live rendering even when not on a tty.

### Machine-readable output

`--json` is the global machine-readable switch, available on every
command that returns a result. It's the machine-readable half of the
output split, and it makes the naming rule visible directly in the
output: under `--json`, a command prints **exactly its result**,
serialized as one JSON document (an object, array, or scalar) on
stdout — nothing else on stdout, diagnostics still on stderr, and the
exit code unchanged. For a command with an API twin, the twin's
return contract is also the command's `--json` contract — it's
defined once, where the twin itself is specified ([api.md](api.md)).

```powershell
$ rlq list-machines --json
[{"id": "freedos-0", "blueprint": "freedos", "phase": "ready", "backend": "qemu"}]

$ rlq create-machine --blueprint freedos --json
"freedos-1"
```

### Discovering backends

```
rlq list-backends
```

`list-backends` reports only the backends actually discovered on
this host. Each row names the backend and its installation home
directory. It's a host-inspection command rather than an embedding
API twin: discovering adapters is internal to Reliquary, handled by
each backend adapter on its own side, with no public API of its own
exposing that process. `--json` returns the same data as an array of
`{backend, home}` records, for programs that need the report.

Rules:

- A command whose API twin returns nothing prints `{}` on success,
  so a program can pass `--json` unconditionally on any
  result-bearing command, without special-casing the ones with
  nothing to return.
- Commands whose output is a stream (`run-script` and `fetch-media`,
  and the not-yet-built `run tail` alongside them) reject `--json`
  and tell you to use `--progress jsonl` instead: a live run is an
  event stream, not a single document — each flag has exactly one
  meaning.
- Secret property values are never serialized. The JSON marker
  `{"secret": true}` stands in for the value — this is the `--json`
  spelling of the same marker the properties file spells `@secret`.
- `--verbose` only affects the pretty, human-readable rendering:
  `--json` always includes the full record regardless, and the two
  flags are never combined for a different effect.

Field names are part of the CLI's contract, and are defined together
with each API twin's return contract. The stability contract is
settled (owner, 2026-07-22): the machine-readable surfaces — exit
codes, `--json` documents, the `jsonl` event stream, run-record
files — only grow additively from version 1.0 onward (an existing
field never changes type or meaning; consumers should ignore any
kind or field they don't recognize). The pretty and plain output
formats are explicitly not covered by this stability contract, and
before 1.0, nothing at all is promised to stay stable.

There's no shorthand for running a bare script name directly: an
unrecognized command word is always an error, never treated as a
script lookup. `run-script <label>` is the only form — this keeps
script names from ever colliding with a present or future
subcommand name.

The old `--qemu`, `--platform`, and `--port` global options belonged
to the pre-blueprint, single-machine model, and have been removed:
`--platform` is now a blueprint field, `--qemu` is now decided by
backend assignment, and `--port` is now a detail of machine state.
