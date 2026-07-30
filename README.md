# Reliquary

[![License](https://img.shields.io/badge/license-GPL--3.0--only-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-%3E%3D3.12-blue.svg)](https://www.python.org/downloads/)

Reliquary helps to automate guest VMs, it can script OS installations from standard vendor installation media and
produce bootable disk images without manual interaction. It can help execute one-off commands and capture the results.
It is built on its own agentless QEMU guest automation layer, which owns QEMU lifecycle, media, QMP identity checks,
keyboard input, screen access, screenshots, and per-run state.

Reliquary machines are ephemeral: disposable rigs for scripted installs and automated guest tasks, cheap to destroy and
recreate. The machine is never the product — often nothing durable comes out at all (the point was to run some tests).
Reliquary is not a VM manager for machines you keep.

## When to use Packer, Vagrant, os-autoinst, or Reliquary

For modern, standard operating-system testing in VMs, start with
Packer and Vagrant. Packer is the established tool for defining
source-controlled image builds from install media, provisioners, and
checksummed inputs, then producing reusable VM or cloud artifacts.
Vagrant is the established tool for source-controlled development and
test environments: bring a VM up from a box, sync project files, run
provisioners, execute guest commands over SSH or WinRM, collect normal
test output, and destroy or recreate the environment when needed.

Reliquary is for the cases where that cooperative guest channel is not
available, not trustworthy, or is itself the thing being created or
tested. It drives a guest through the VM's observable console: keyboard
events in, screen text and screenshots out, with media changes and run
records captured by the host. That makes it useful for text-mode
installers, legacy systems such as DOS, broken or partially configured
guests, boot menus, setup flows before SSH/WinRM/guest tools exist, and
tests where the screen or installer behavior is the assertion surface.

If your guest can already accept SSH, WinRM, cloud-init, a guest agent,
or a normal configuration-management/provisioning path, Packer and
Vagrant are usually the better default. Use Reliquary when the important
part of the workflow lives before that point, below it, or outside it.

os-autoinst, the engine under openQA, covers much of that
console-driven ground at production scale: booting systems under test,
driving installers and applications, matching screens with needles,
checking serial and screen output, and recording job artifacts. If you
need openQA's scheduler, worker farm, web UI, asset management, and job
history around that engine, use openQA. Reliquary's overlap is with
os-autoinst itself, not with openQA as a service.

Reliquary lives in the smaller local-tool and embedding-library space.
It is meant to be run directly from a source tree or a user's machine,
as a QEMU automation harness a script, test runner, CI job, or coding
agent can call without adopting a scheduler, worker farm, web service,
or image-needle workflow. Its current strongest case
is agentless text-mode automation — especially DOS and other guests
where VGA text, keyboard input, virtual FAT media, and compact run
records are enough and a larger OS-testing service would be more
machinery than the job needs. Its planned authoring niche is local
demonstration-driven drafting: do the task once, then turn the observed
keystrokes, media changes, and screen states into ordinary script and
asset files that can be reviewed and edited.

## Blueprints and machines

The first thing to learn is Reliquary's central model. A **blueprint** is a reusable JSON design you author and keep —
a `<name>.rlqb` file, conventionally under `<reliquary_home>/blueprints/`. A **machine** is a disposable realization Reliquary builds from it,
identified by a generated id — one blueprint, many machines. The blueprint is one file holding named components — a
`machine` plus the `media`, `source`, and `archive` components it draws on. Machines are created, run, destroyed, and
recreated freely: the blueprint (media components and all) and its scripts are always enough to rebuild one, so nothing
Reliquary materializes is ever precious. Editing a blueprint never changes an existing machine by itself; a machine
keeps the snapshot it was created from. To adopt blueprint edits, destroy the machine and create it again.

### A blueprint, and the machines it makes

Here is a whole blueprint — an MS-DOS-era box with 1 MB of memory
and one floppy drive, saved as `blueprints/msdos.rlqb`:

```jsonc
[
  {
    "type": "machine",
    "name": "msdos",
    "platform": "dos",
    "memory": "1M",
    "description": "A 1 MB MS-DOS box with one floppy drive",
    "drives": {
      // Declared but empty: what goes in is a per-machine choice.
      "floppy0": null
    },
    "boot": ["floppy0"]
  }
]
```

Create two machines from it and they are identical, differing only
in id — numbered from zero, lowest free number first:

```powershell
rlq create-machine --blueprint msdos   # prints msdos-0
rlq create-machine --blueprint msdos   # prints msdos-1
```

Now put a disk in one of them. `insert-media` changes that machine
and nothing else — it survives stop and start, and `msdos-0` never
hears about it:

```powershell
rlq insert-media --machine msdos-1 floppy0 dos-622-disk1
```

That is the split worth remembering: **the blueprint is the design,
and a machine's own state is what has happened to it since.** Memory,
drive slots and boot order come from the blueprint, so changing them
means editing the file. What is *in* a drive is the machine's.

A different design is a different blueprint. This one has sixteen
times the memory and a CD-ROM, so it is `blueprints/dos-cd.rlqb`
rather than a variant of the first:

```jsonc
[
  {
    "type": "machine",
    "name": "dos-cd",
    "platform": "dos",
    "memory": "16M",
    "description": "A 16 MB DOS box that boots from CD",
    "drives": {
      "hdd0": { "type": "media", "size": "20M" },
      "cdrom0": null
    },
    "boot": ["cdrom0", "hdd0"]
  }
]
```

Its machines are `dos-cd-0`, `dos-cd-1`, and so on — the id always
names the blueprint it came from.

Editing a blueprint does not reach back into machines already built
from it; each keeps the snapshot it was created from. `rlq
apply-blueprint --machine msdos-0` adopts the edits into a stopped
machine, absorbing what it can — memory, boot order, CPU count — and
failing closed where it cannot, such as a changed size on an image
that has already been materialized. `rlq recreate-machine` is the
answer when it refuses: destroy and rebuild under the same id.

Read the [Blueprint guide](docs/blueprint-guide.md) for the format,
the [CLI reference](docs/cli-reference.md) for commands, and the
[API reference](docs/api-reference.md) for the Python surface. The
normative definitions are
[the composed blueprint model](docs/spec/blueprint-model.md) and
[Machine blueprints and machines](docs/spec/instance-model.md).

## Installation

**Windows is the supported host.** It is the platform Reliquary is
developed and tested on. The host code is written portably and the
paths for macOS and Linux hosts are there, but they are not
exercised yet — so they are not claimed. (The *guest* side is a
separate question: what a machine runs inside is up to its
blueprint.)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

On an untested host (macOS or Linux), activate the environment
with:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

## Scripting OS installations

Installing registers two equivalent commands: `rlq` (the short form used throughout the docs) and `reliquary`.

```powershell
rlq --help
rlq list-codex
rlq seed-blueprint freedos
rlq run-script install --blueprint freedos
```

From a clean home that is **two commands** to a usable machine, and the first one is the point: `seed-blueprint`
copies the codex's `freedos` blueprint — its LiveCD media rides inside it — and the scripts it names into your own
directories, as ordinary files you own and can read before you run them. Nothing arrives from the built-in library
unasked, so what the second command runs is a recipe you chose.

That second command materializes a machine from your copy, inserts the
fetched, hash-verified LiveCD to the blueprint's empty CD drive, boots it, and drives the FreeDOS installer end to end —
language, partitioning, the reboot, the "Plain DOS system" package set — until the guest powers itself off and the
script ejects the CD. The machine is left with FreeDOS installed on its hard disk; confirm it boots, then start and stop
it freely:

```powershell
rlq run-script verify --blueprint freedos
rlq start-machine --blueprint freedos
rlq stop-machine --blueprint freedos
```

The blueprint's third script is the one a program wants: `ready` boots the installed disk, waits for a DOS prompt, and
**leaves the machine running** with a machine variable set, which is the handoff to whatever drives it next.
`--expect` contracts the run on that variable, so one command either hands you a live guest or fails saying why:

```powershell
rlq run-script ready --blueprint freedos --expect ready=yes
rlq exec "ver" --blueprint freedos
```

To inspect a script without running it, `--dry-run` prints the
resolved timing plan — each observation's timeout, each guest
input's pacing, and where each came from — along with each declared
property's source and how much of the script no static pass can
promise will run, a statement inside a handler being the guest's
decision rather than the plan's. It starts no machine and sends no
keystroke. The selector is optional here and nowhere else, because
its presence is what asks for the machine checks as well:

```powershell
rlq run-script freedos-install --dry-run
rlq run-script install --blueprint freedos --dry-run
```

The same question about a machine — is this blueprint sound, and
what would it build? — is `rlq create-machine --dry-run`, which
reports the machine
id it would allocate, the backend it would land on, every drive's
resolved plan, and where each media would come from, while building
none of it. Nothing is seeded, fetched or written, and nothing is
asked for; a media that is not cached yet is simply reported as one
that would be downloaded. `--backend` turns it into a question about
somewhere else: whether the blueprint would work on VirtualBox or
Hyper-V, answered from what that backend can do, with nothing
installed and nothing booted.

```powershell
rlq create-machine --blueprint freedos --dry-run
rlq create-machine --blueprint freedos --dry-run --backend hyperv
```

Vendor media is cached and verified against pinned SHA-256 hashes on every use, under `cache/media/`
(`Documents\reliquary` by default; override the payload cache with `--media-dir`, or move everything
at once with `--home-dir` or the `RELIQUARY_HOME_DIR` environment variable).

A run **returns its output** and stores nothing: it streams its progress live — `--progress pretty` for a person,
`--progress jsonl` for a program — and the stream is gone when the run ends. Redirect it if you want to keep it. When a
run fails, the report names what it was waiting for, which clock expired, the route it took, the screen row that came
nearest, a screenshot, and the command to try next. Pass `--display` to show the QEMU window instead of running
headless — helpful when debugging a script.

## The machine layer

Beneath the scripts, Reliquary is a general automation harness for running remote tasks in QEMU guests, usable on its
own through the CLI and Python interfaces documented below.

DOS is the default and currently the only complete platform workflow. It boots a DOS guest, types at its keyboard, reads
its VGA text screen, runs commands, takes screenshots, and retrieves files written by the guest. Other platform names
reserve the generic QEMU lifecycle but their provisioning and guest-task semantics currently raise
`NotImplementedError` until an adapter is implemented.

## The platform model

A blueprint names its guest platform in the required `platform` field;
`new-blueprint` scaffolds `dos` by default. DOS is the only complete
workflow today — other platform names reserve the generic QEMU
lifecycle but raise `NotImplementedError` for provisioning and
guest-task semantics until an adapter is implemented. Platform-specific
behavior is never inferred from an image. Future adapters can define how
a guest is provisioned, how a remote task is launched, and how its
result is collected while reusing the same ownership-verified QEMU
machine layer.

## Why the DOS adapter exists

Automating a modern virtual machine usually means installing a guest agent, opening a network connection, or reading a
serial console. Those options are often unavailable in DOS, and they are especially unsuitable when the software under
test is the driver that would provide that communication.

Reliquary therefore works **agentlessly**:

- Input is sent as keyboard events through QEMU's control protocol.
- Text is read directly from VGA text memory, without OCR.
- Files are exchanged through a QEMU virtual FAT drive.
- Command completion is detected by watching for the DOS prompt.
- Screenshots are captured through QEMU.

The guest needs no Reliquary software, network driver, serial driver, or background service. This makes the harness
useful even while the guest is partially configured or broken.

Any DOS with a bootable image works. A machine's drives each name a
**media** component, and the media owns its content — a blank
`materialize: new` disk of `size`, a `difference`/`copy` over a
payload, or a `use` attach (an ISO, or a host directory served as a
virtual FAT drive) — and Reliquary materializes any per-machine image
under `cache/machines/<id>/media/`. Any QEMU-supported image format
works; `*.img` and `*.iso` are taken as raw. Reliquary hands back a
guest program's raw output, and interpreting it is left to the caller.

## The workflow

1. **Describe the machine.** Author a `<name>.rlqb` blueprint (by hand,
   with `rlq new-blueprint`, or by seeding one from the codex) declaring
   the platform, memory, and drives; each drive names a **media**
   component, and the media owns how it materializes — a blank `new`
   disk, a `difference`/`copy` over a payload, or a `use` attach. To
   hand the guest its own files, a media whose `source` is a host
   directory (`materialize: use`) is the natural surface: that directory
   *is* the drive.
2. **Create a machine.** `rlq create-machine --blueprint <name>`
   materializes one under a generated id (or `run-script` creates one on
   demand). The blueprint (media components and all) and its scripts are
   always enough to rebuild it, so a machine is never precious.
3. **Drive it.** Run an attached `.rlqs` script with
   `rlq run-script <label> --blueprint <name>`, or operate the machine
   interactively — `rlq start-machine`, then `exec` / `wait` / `screen` /
   `press` / `select` against it, then `rlq stop-machine`.
4. **Take the results.** A run returns its output to you and keeps
   nothing of its own. A small value comes back through a machine
   variable (`rlq get-machine-var`); a file comes back by its guest
   address (`rlq get-file "A:\RESULT.TXT" .
esult.txt`); a whole
   image comes back by swapping it out. Out of band, `rlq
   get-machine-dir` prints the machine directory: while the machine is
   stopped, its directory-source and image drives are ordinary host
   state to read or prepare.
5. **Recreate freely.** `destroy-machine` deletes a machine entirely and
   `recreate-machine` rebuilds it under the same id; `apply-blueprint`
   adopts blueprint edits into a stopped machine.

## Requirements

Reliquary requires:

- Python 3.12 or newer
- QEMU with `qemu-system-i386` (and `qemu-img` to create hard-disk images)

The Python package installs QEMU's official `qemu.qmp` library. QEMU itself is a separate application and must be
installed on the host.

Reliquary searches for QEMU in this order:

1. `RELIQUARY_QEMU_HOME` environment variable
2. `QEMU_HOME` environment variable
3. The system `PATH`
4. Common installation directories on Windows, macOS, and Linux

`RELIQUARY_QEMU_HOME` is how a specific installation is chosen; the
QEMU adapter probes the rest in the order above.

## Where Reliquary keeps things

Reliquary has **six working directories**, and you can put each one wherever you like — machines on a fast disk, media on
a big one, blueprints in your project's repository. Name any of them and the rest follow:

| Directory | Flag | Environment | Where it lands if you say nothing |
|---|---|---|---|
| home | `--home-dir` | `RELIQUARY_HOME_DIR` | `Documents/reliquary` |
| blueprints | `--blueprints-dir` | `RELIQUARY_BLUEPRINTS_DIR` | `<home>/blueprints` |
| scripts | `--scripts-dir` | `RELIQUARY_SCRIPTS_DIR` | `<home>/scripts` |
| cache | `--cache-dir` | `RELIQUARY_CACHE_DIR` | `<home>/cache` |
| media | `--media-dir` | `RELIQUARY_MEDIA_DIR` | `<cache>/media` |
| machines | `--machines-dir` | `RELIQUARY_MACHINES_DIR` | `<cache>/machines` |

The home's own default is `reliquary/` under your Documents folder (the Windows known Documents folder — including when
redirected, e.g. into OneDrive — `~/Documents` on macOS, and `xdg-user-dir DOCUMENTS` on Linux/BSD). When no Documents
folder can be determined, it falls back to `~/reliquary`.

A flag beats the environment, and both beat the default. Assigning the cache moves media and machines with it unless you
have placed those too, so `--cache-dir D:\reliquary-cache` is enough to keep the bulk off a synced Documents folder. From
Python the twins are `reliquary.set_home_dir()`, `set_cache_dir()`, `set_blueprints_dir()`, and so on — or a
`reliquary.Context(...)` to scope a single call.

The platform Documents lookup itself is available as
`reliquary.documents_dir()`, returning the folder path or `None` when it cannot be determined, for callers that want to
anchor their own directories the same way.

The layout is:

```text
Documents/reliquary/
├── blueprints/           composed blueprints you author (<name>.rlqb) —
│                         a machine plus its media/source/archive components
├── scripts/              automation scripts (<name>.rlqs)
└── cache/                regenerable; resolves independently
    │                     (--cache-dir) and can live elsewhere
    ├── media/            cached, hash-verified media payloads
    └── machines/<id>/    each materialized machine — its own directory
                          with machine.json (the state; while running its
                          `vm` section holds the live VM identity, and
                          any machine variables a script set), media/
                          (per-machine images), screenshots/, and a
                          <backend>/ subdir (e.g. qemu/qemu-stderr.log).
                          A run stores nothing here — it returns its
                          output to whoever started it
```

A machine is wholly its machines-directory entry — there is no
root-home machine model. Everything under the cache is regenerable. When
you have not named a home, the one Reliquary picked is printed to
standard error.

Blueprints (with their media/source/archive components) and scripts are
read from the `blueprints` and `scripts` directories above, each walked
recursively by file extension. A name those directories do not hold is
**not** taken from anywhere else — the built-in codex is not a
fallback tier, so a name they do not hold is refused rather than
supplied (the refusal names `rlq seed-blueprint <name>` when the
library has it). For a project, point the directories at your tree:

```powershell
rlq --blueprints-dir .\vm --scripts-dir .\vm run-script install --blueprint freedos
```

Your source-controlled files are the only source, so a run is
reproducible and never picks up whatever happens to be in your home.
Seeding works wherever you point it —
`rlq --blueprints-dir .\vm seed-blueprint freedos` copies a first draft
into your project, and you commit it. The embedding API is stricter
still: it assigns no directory at all, so a library call fails closed
rather than reading a developer's home — and it cannot reach the
library either, the codex verbs being CLI-only.
A machine records which blueprint file it was built from, so a
`--blueprint <name>` selection only ever picks a machine built from the
blueprint the current invocation resolves — two projects that share a
blueprint name never disturb each other's machines.

## First session

Beyond running a whole script, you can drive a machine interactively —
useful for exploring a guest or debugging a workflow step by step. This
session starts a machine, reaches the DOS prompt, runs a few commands,
and stops it. Every guest-console command selects its machine with
`--blueprint <name>` (or `--machine <id>`).

### 1. Get a machine

Seed a codex blueprint (or scaffold your own with
`rlq new-blueprint <name>`), then create a machine from it:

```powershell
rlq seed-blueprint freedos
rlq create-machine --blueprint freedos
```

`create-machine` materializes the machine's per-machine images under
`cache/machines/<id>/media/` and prints the generated id. (If a
machine of this blueprint already exists — e.g. one installed by
`run-script install` — you can start it directly.)

### 2. Start it

```powershell
rlq start-machine --blueprint freedos
```

Reliquary picks the backend, starts it headless, assigns the VM a
unique identity, and records it in the machine's `machine.json` (as a
`vm` section, written while running). Later commands find the running
VM through the machine selector, so nothing about the connection is
ever copied by hand — how the backend is reached is its adapter's
business. The machine stays running until you stop it. Add
`--display` for a visible, manually interactive window.

### 3. Reach the DOS prompt

`start-machine` returns when QEMU is ready, not when DOS is. Wait for a
prompt before running commands:

```powershell
rlq wait "C:\\\\>" --blueprint freedos
```

### 4. Run DOS commands

```powershell
rlq exec "dir" --blueprint freedos
rlq exec "myprog.exe > result.log" --blueprint freedos
```

`exec` types the command and waits for the DOS prompt to return. To
retrieve detailed output, name a directory-source media (`source` a
host directory, `materialize: use`) on a machine drive and have the
program write to it; while the machine is stopped, that directory is
ordinary host state (`rlq get-machine-dir` prints the path).

### 5. Inspect the guest

```powershell
rlq screen --blueprint freedos
rlq screenshot after-test --blueprint freedos
```

`screen` prints the current 80-by-25 text screen; `screenshot` saves a
PNG under the machine's own `screenshots/` directory. Screenshot names
are filename stems, not paths.

### 6. Stop it

```powershell
rlq stop-machine --blueprint freedos
```

Stopping verifies the VM's recorded identity before closing it and
flushes guest writes to any virtual FAT drive. QEMU snapshots a
directory-source media's directory when the drive is attached, so after
changing its host files, stop and restart the machine before using them
in the guest.

## Command guide

### Managing machines (blueprint lifecycle)

```text
rlq create-machine --blueprint NAME
rlq start-machine (--blueprint NAME | --machine ID) [--display]
rlq stop-machine (--blueprint NAME | --machine ID)
rlq destroy-machine (--blueprint NAME | --machine ID)
rlq list-machines [--blueprint NAME]
rlq delete-blueprint NAME
```

`--blueprint` selects that blueprint's sole machine (or names the blueprint for `create-machine`).
`--machine` takes the full id (`<blueprint>-<n>`) exactly — no prefix matching and no bare-number form.
The two selectors are mutually exclusive. Machines live under
`cache/machines/<name>-<n>/`.
`delete-blueprint` removes the home blueprint file and refuses while
any machine of it still exists.

```powershell
rlq create-machine --home-dir $scratch --blueprint plain
rlq start-machine --home-dir $scratch --blueprint plain --display
rlq stop-machine --home-dir $scratch --blueprint plain
rlq list-machines --home-dir $scratch
```

### Media catalog

```text
rlq list-media
rlq fetch-media NAME
rlq clean-media [NAME]
rlq prune-media [--dry-run]
rlq add-media NAME FILE
```

`list-media` names the media resolvable from the active source —
yours, and only yours. `fetch-media` resolves one by name and warms
its cached payload.

Everything cached lives in one place, `cache/media/`, keyed by the name
of the media it is — a container is a media like any other, so there is
no separate archive cache. `clean-media` reclaims what can be fetched
or derived again; `prune-media` is the informed version, keeping what
the scope can still attach and dropping what only existed to produce
it, so after an install the extracted ISO stays and the zip husk goes.
`add-media` is the door for payloads nothing can locate — a licensed
ISO you cannot redistribute — verified against the blueprint's pin and
then never reclaimed behind your back.

(Media are specs inside a `.rlqb` now, so there is no `delete-media`
command — removing one means editing the blueprint that declares it.)

### Driving a machine from a program

```text
rlq run-script LABEL (--blueprint NAME | --machine ID) [--progress MODE]
rlq get-machine-var KEY (--blueprint NAME | --machine ID)
rlq describe-drives (--blueprint NAME | --machine ID)
rlq refresh-drives (--blueprint NAME | --machine ID)
rlq put-file HOST-PATH GUEST-ADDRESS (--blueprint NAME | --machine ID)
rlq get-file GUEST-ADDRESS HOST-PATH (--blueprint NAME | --machine ID)
rlq put-files HOST-DIR GUEST-DIR (--blueprint NAME | --machine ID)
rlq get-files GUEST-DIR HOST-DIR (--blueprint NAME | --machine ID)
rlq list-files GUEST-DIR [--recursive] (--blueprint NAME | --machine ID)
rlq insert-media SLOT --file PATH (--blueprint NAME | --machine ID)
```

This is the loop an automating program runs: put work into the guest,
run it, read the result back, iterate. Reliquary supplies the
transports and attaches no meaning to what travels through them —
there is no pass/fail vocabulary and no result parsing, because those
belong to whatever you are building.

Values come back as **machine variables**: a script's `set result
"PASS"` writes one, and `get-machine-var result` reads it from any
process. They are cleared at each start, so one always reports what the
current boot produced. Readiness rides the same channel — your own
ready script sets a variable and you poll for it; Reliquary ships no
readiness script of its own.

Files come back **by their guest address** — `A:\RESULT.TXT`, the way
the guest names it, never a host image path. One file moves with
`put-file` / `get-file` and a whole tree with `put-files` /
`get-files`, whose addresses name a directory the same way (`A:\` is
the drive itself); `list-files` says what is over there, printing
addresses the other four accept. All of them work while the machine is
stopped, at whatever letter the drive lands on — including behind an
installed `C:`. Over a directory-source drive the backend snapshots
that directory at attach, so a stopped machine is what makes a put
visible and a guest write flushed; over a **drive image** Reliquary
mounts the disk on the host and works the filesystem inside it, so
files move into and out of an installed `C:` with no guest running.
A write is staged and swapped in at the end, so an interrupted one
leaves the disk as it was.

The letters themselves are learnable, not guessed at:
`describe-drives` reports what the machine's drives are and what
they actually hold — per disk the partitions and volumes as read
from the image (filesystem, label, geometry), and the resulting
letter map, letter to drive and volume. Every start reads the
disks as its first step, so a running machine's report describes
what this boot started from — and says so, with each disk stamped
by when it was read. Changed a disk while the machine was down?
`refresh-drives` re-reads and reports in one step. A disk
Reliquary cannot read is named as undetermined with the reason,
never mapped by guesswork.

When a reboot per round costs too much, swap the medium instead:
`insert-media --file` mounts an image you built, live, and ejecting
flushes the guest's writes back to that same file.

```powershell
rlq put-files .\suite "A:\" --machine rig-0
rlq run-script test --machine rig-0 --progress jsonl > run.jsonl
rlq get-machine-var result --machine rig-0
rlq stop-machine --machine rig-0
rlq list-files "A:\OUT" --recursive --machine rig-0
rlq get-files "A:\OUT" .\out --machine rig-0
```

`--progress` selects the live rendering: `pretty` for a person,
`plain` for a log, `jsonl` for a program (stdout carries the event
stream and nothing else, the last line being the outcome). Exit codes
carry the outcome too, and they are the same on every command rather
than a script run's alone — `2` your input is illegal on its face,
`3` it is legal and the world does not satisfy it, `4` the operation
started and failed, `5` cancelled, `1` a fault of Reliquary's own and
never a mistake of yours.

### Keyboard and command input

```text
rlq type TEXT
rlq enter LINE
rlq press KEY [KEY ...]
rlq exec COMMAND
rlq select ITEM [--exclude TEXT]
```

Every guest-console command targets a running machine — select it with
`--blueprint <name>` / `--machine <id>`, as in the [First
session](#first-session). The examples below omit the selector for
brevity.

`type` sends raw text with no trailing Enter; `enter` types a line and presses Enter. `exec` additionally waits for the
prompt to return. `press` accepts the script language's portable key names (and `+` chords), such as:

```powershell
rlq press down enter
```

`select` selects an entry in a cursor-key driven text menu, such as a boot menu. It presses the up/down cursor keys and
follows the selection highlight through the VGA attribute bytes, so the entry is confirmed by what the guest actually
displays before Enter is pressed:

```powershell
rlq select "Use FreeDOS 1.4 in Live Environment mode"
```

The item text is matched case-insensitively against the visible screen rows. A row exactly equal to the item wins over
rows merely containing it (so `"Plain DOS system"` is selectable beside
`"Plain DOS system, with sources"`); otherwise the item must be contained in exactly one row. `--exclude TEXT` (
repeatable) rules rows out instead: rows containing an excluded text are never selected, which is another way to
disambiguate:

```powershell
rlq select "Full installation" --exclude "with sources"
```

Use the global `--timeout SECONDS` option to change the 30-second navigation timeout.

### Reading the guest

```text
rlq screen
rlq wait REGEX
rlq screenshot [NAME]
```

Use the global `--timeout SECONDS` option to change the timeout for
`exec` or `wait`.

### QEMU monitor access

```powershell
rlq hmp "info block"
```

`hmp` sends a raw QEMU human-monitor command. It is intended for QEMU operations that do not yet have a dedicated
Reliquary command.

Run `reliquary --help` or `reliquary COMMAND --help` for the complete current syntax.

## Python usage

The CLI is a thin veneer over the embedding API: every command maps
one-to-one onto a Python call with the same semantics. To run a whole
script, `reliquary.run_script("install", blueprint="freedos")`
is the one call. To drive a machine directly, create and start it, then
attach the interaction adapter to the machine's own directory — that is
where its recorded identity lives, so ownership is verified against it:

```python
import reliquary

machine_id = reliquary.create_machine("freedos")
reliquary.start_machine(machine_id)
home = reliquary.machine_dir_path(machine_id)
machine = reliquary.Machine(home)
guest = reliquary.AgentlessGuestExec(machine)

try:
    guest.wait_ready()
    guest.execute("dir", timeout=15)
    print("\n".join(machine.screen_text()))
    machine.screenshot("after-test")
finally:
    reliquary.stop_machine(machine_id)
```

`Machine` also exposes the VGA text screen directly: `machine.screen_text()`
returns the 80x25 rows, and `machine.wait_text(pattern, timeout=60)` polls until the screen matches a regular
expression (returning the matching screen)
or raises `TimeoutError`. This is how to block on specific output, such as a boot menu:

```python
machine.wait_text(r"Welcome to FreeDOS")
```

Once a cursor-key menu is displayed, `machine.cursor_menu_select()`
navigates it by feedback: it presses up/down, follows the selection highlight through the VGA attribute bytes, and
presses Enter only after the highlight sits on the row matching the given text (case-insensitive; an exact row match
wins over rows merely containing the item, which otherwise must be unique). `exclude=` takes text snippets whose rows
are never selected, as another way to disambiguate. The item must match when navigation starts; a menu that rewrites its
rows as the highlight moves (the FreeDOS installer's language chooser translates every entry into the newly highlighted
language) is then navigated by row, and the returned text is what the selected row displayed when Enter was pressed:

```python
machine.wait_text(r"Welcome to FreeDOS")
machine.cursor_menu_select("Use FreeDOS 1.4 in Live Environment mode")
```

These screen and keyboard operations live on the platform-neutral
`Machine`, so they work on any guest displaying through VGA text mode — boot menus and loaders included, before any
operating system is up. Module-level conveniences (`reliquary.cursor_menu_select(item, port=port)`,
`reliquary.screen_text(port=port)`, ...) wrap the same methods.

`Machine.qmp()` exposes the identity-verified QMP session when a caller needs raw monitor access. The yielded QEMU
session provides both `cmd()` for QMP and
`hmp()` for human-monitor commands:

```python
with machine.qmp() as qmp:
    status = qmp.cmd("query-status")
    blocks = qmp.hmp("info block")
```

### Running scripts and managing machines

The lifecycle and scripting verbs are all available as Python calls
with the same names as their CLI twins: `create_machine` /
`start_machine` / `stop_machine` / `destroy_machine` /
`recreate_machine` / `apply_blueprint`, and `run_script` for the
`.rlqs` language. `run_script` **returns the
run's output** — the whole event stream, plus the final script phase
and the machine's phase — and writes nothing to disk; it raises by
error class on failure. See the [API reference](docs/api-reference.md)
for the full surface and [`docs/spec/api.md`](docs/spec/api.md)
for the end-goal design.

## Troubleshooting

### QEMU cannot be found

Install QEMU and put `qemu-system-i386` on `PATH`, or set
`RELIQUARY_QEMU_HOME` to the QEMU installation directory. With no
QEMU available, `create-machine` reports every backend it probed and
why each was passed over.

### A command cannot find an active VM

Guest-console commands find the running VM through the `vm` section of
the machine's `cache/machines/<id>/machine.json`. Ensure every command
uses the same `--home-dir` / `RELIQUARY_HOME_DIR` and the same machine
selector, and that `rlq start-machine` completed successfully.

### The VM identity does not match

Reliquary verifies the unique QEMU name and per-start uuid before
sending any command. An identity error means the recorded port now
belongs to another process or the state file is stale. The unrelated VM
is not modified. Review the machine's `machine.json` (its `vm` section)
and its backend `qemu/qemu-stderr.log` (under `cache/machines/<id>/`;
`rlq get-machine-dir` prints the path), then start the machine again.

### QEMU exits during startup

The error includes the selected port, QEMU exit status, command line,
and path to the machine's `qemu/qemu-stderr.log`. That log normally
contains QEMU's reason, such as an invalid device option or an
unavailable disk image.

### Guest-written files are missing

Stop QEMU before reading files written to the virtual FAT drive. Writes are flushed back to the host during shutdown.

## License

GPL-3.0-only. See [LICENSE](LICENSE).

Reliquary is copyleft. You may run, study, modify, and redistribute it
freely; any work you distribute that incorporates it must also be
GPL-3.0-only. It cannot be taken into a proprietary product.

Paul Galbraith holds copyright in the project and **reserves the right to
relicense it**, on any terms, at any time. No relicensing is planned or
in preparation — the reservation exists so the option is not lost by
default, not because it is about to be used. It takes nothing back from
what has already been released: every version published under the GPL
stays under the GPL, permanently. Contributions are accepted under a
copyright assignment that keeps the reservation intact; see
[CONTRIBUTING.md](CONTRIBUTING.md).

The name **Reliquary** is owned by Paul Galbraith and is not licensed
for use by forks or redistributions. See [TRADEMARKS.md](TRADEMARKS.md).
