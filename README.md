# Reliquary

[![License](https://img.shields.io/badge/license-GPL--3.0--only-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-%3E%3D3.12-blue.svg)](https://www.python.org/downloads/)

Reliquary automates guest virtual machines. It can script an OS installation from the vendor's own install media and
produce a bootable disk image with no manual steps. It can also run one-off commands inside a guest and capture the
results. Reliquary is built on its own agentless QEMU automation layer, which handles the QEMU process itself, media,
QMP identity checks, keyboard input, reading the screen, screenshots, and the state Reliquary keeps between runs.

Reliquary machines are meant to be thrown away. They are cheap to destroy and recreate, built for scripted installs
and automated guest tasks. The machine itself usually is not what you keep — often nothing durable comes out of a run
at all, because the point was just to run some tests. Reliquary is not a VM manager for machines you want to keep
around long-term.

## When to use Packer, Vagrant, os-autoinst, or Reliquary

For modern, standard operating-system testing in VMs, start with
Packer and Vagrant. Packer is the established tool for defining
source-controlled image builds from install media, provisioners, and
checksummed inputs, then producing reusable VM or cloud artifacts.
Vagrant is the established tool for source-controlled development and
test environments: bring a VM up from a box, sync project files, run
provisioners, execute guest commands over SSH or WinRM, collect normal
test output, and destroy or recreate the environment when needed.

Reliquary is for cases where a channel like SSH, WinRM, or a guest agent is
not available, not trustworthy, or is itself the thing being built or
tested. It drives a guest through the VM's console the way a person at the
keyboard would: it sends keyboard events in, and reads back screen text and
screenshots, while the host records media changes and run history. That
makes it useful for text-mode installers, legacy systems such as DOS,
broken or partially configured guests, boot menus, setup flows that run
before SSH/WinRM/guest tools exist, and tests where what matters is what
actually shows up on the screen or how the installer behaves.

If your guest can already accept SSH, WinRM, cloud-init, a guest agent,
or a normal configuration-management/provisioning path, Packer and
Vagrant are usually the better default. Use Reliquary when the important
part of the workflow lives before that point, below it, or outside it.

os-autoinst, the engine under openQA, does this same kind of console-driven
automation, but at production scale: it boots systems under test, drives
installers and applications, matches screens against reference images
called needles, checks serial and screen output, and records job
artifacts. If you need openQA's scheduler, worker farm, web UI, asset
management, and job history around that engine, use openQA. Reliquary
overlaps with os-autoinst itself, not with openQA as a hosted service.

Reliquary fits a smaller niche: it is a local tool and embedding library,
meant to be run directly from a source tree or a user's own machine. It is
a QEMU automation harness that a script, test runner, CI job, or coding
agent can call without adopting a scheduler, worker farm, web service, or
image-matching workflow. Its strongest case today is agentless text-mode
automation — especially DOS and other guests where VGA text, keyboard
input, virtual FAT media, and compact run records are enough, and a
larger OS-testing service would be more machinery than the job needs. Its
planned approach to writing new scripts is demonstration-driven: you do
the task once by hand, and Reliquary turns the keystrokes, media changes,
and screen states it observed into ordinary script and asset files that
you can review and edit.

## Blueprints and machines

The first thing to learn is Reliquary's core model: blueprints and machines. A **blueprint** is a reusable JSON design
you write and keep — a `<name>.rlqb` file, normally under `<reliquary_home>/blueprints/`. A **machine** is a
disposable copy that Reliquary builds (materializes) from that blueprint, identified by a generated id — one
blueprint can produce many machines. The blueprint is a single file holding named components: a `machine` plus the
`media`, `source`, and `archive` components it uses. You can create, run, destroy, and recreate machines freely: the
blueprint (including its media components) and its scripts are always enough to rebuild one, so nothing Reliquary
builds needs to be protected from deletion. Editing a blueprint never changes a machine that already exists on its
own — a machine keeps the snapshot it was created from. To pick up blueprint edits, destroy the machine and create it
again.

### A blueprint, and the machines it makes

Here is a whole blueprint — an MS-DOS-era box with 1 MB of memory
and one floppy drive, saved as `blueprints/msdos.rlqb`:

```json5
[
  {
    "type": "machine",
    "name": "msdos",
    "platform": "dos",
    "memory": "1M",
    "description": "A 1 MB MS-DOS box with one floppy drive",
    "devices": {
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
and nothing else — it survives stop and start, and `msdos-0` is
unaffected:

```powershell
rlq insert-media --machine msdos-1 floppy0 dos-622-disk1
```

That is the split worth remembering: **the blueprint is the design, and a
machine's own state is whatever has happened to it since it was
created.** Memory, drive slots and boot order come from the blueprint, so
changing them means editing the file. What is *in* a drive belongs to the
machine.

A different design is a different blueprint. This one has sixteen
times the memory and a CD-ROM, so it is `blueprints/dos-cd.rlqb`
rather than a variant of the first:

```json5
[
  {
    "type": "machine",
    "name": "dos-cd",
    "platform": "dos",
    "memory": "16M",
    "description": "A 16 MB DOS box that boots from CD",
    "devices": {
      "hdd0": { "type": "media", "size": "20M" },
      "cdrom0": null
    },
    "boot": ["cdrom0", "hdd0"]
  }
]
```

Its machines are `dos-cd-0`, `dos-cd-1`, and so on — the id always
names the blueprint it came from.

Editing a blueprint does not change machines already built from it; each
one keeps the snapshot it was created from. `rlq apply-blueprint
--machine msdos-0` applies the edits to a stopped machine — it picks up
what it safely can, such as memory, boot order, and CPU count, and
refuses (fails closed) where it cannot, such as a changed size on an
image that has already been built. When it refuses, `rlq
recreate-machine` is the answer: it destroys and rebuilds the machine
under the same id.

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

Installing the package registers two equivalent commands: `rlq` (the short form used throughout the docs) and
`reliquary`.

```powershell
rlq --help
rlq list-codex
rlq seed-blueprint freedos
rlq run-script install --blueprint freedos
```

From a clean home, that is **two commands** to a usable machine, and the first one is the important part:
`seed-blueprint` copies the codex's `freedos` blueprint — its LiveCD media travels inside it — along with the scripts
it names, into your own directories, as ordinary files you own and can read before you run them. Nothing runs from
the built-in library without you asking for it, so what the second command runs is a recipe you chose.

That second command builds (materializes) a machine from your copy, inserts the fetched, hash-verified LiveCD into
the blueprint's empty CD drive, boots the machine, and runs the FreeDOS installer end to end — language,
partitioning, the reboot, and the "Plain DOS system" package set — until the guest powers itself off and the script
ejects the CD. The machine is left with FreeDOS installed on its hard disk. Confirm it boots, then start and stop it
freely:

```powershell
rlq run-script verify --blueprint freedos
rlq start-machine --blueprint freedos
rlq stop-machine --blueprint freedos
```

The blueprint's third script is the one a program wants: `ready` boots the installed disk, waits for a DOS prompt,
and **leaves the machine running** with a machine variable set — that variable is the signal to whatever drives the
machine next. `--expect` checks the run against that variable, so one command either hands you a live guest or fails
and says why:

```powershell
rlq run-script ready --blueprint freedos --expect ready=yes
rlq exec "ver" --blueprint freedos
```

To check a script without running it, `--dry-run` prints the resolved timing plan: the timeout for each thing the
script waits on, the pacing for each keystroke or input it sends, and where each of those values came from. It also
shows where each declared property's value came from, and how much of the script cannot be guaranteed to run just by
reading it — what happens inside a handler is the guest's decision, not something the plan can promise. `--dry-run`
starts no machine and sends no keystroke. Normally the `--blueprint` / `--machine` selector is required; with
`--dry-run` it is optional, and giving it anyway is what makes `--dry-run` also run the machine-specific checks:

```powershell
rlq run-script freedos-install --dry-run
rlq run-script install --blueprint freedos --dry-run
```

Asking the same question about a machine instead of a script — is this blueprint sound, and what would it build? —
is `rlq create-machine --dry-run`. It reports the machine id it would allocate, the backend it would run on, the
resolved plan for every drive, and where each media would come from, without actually building any of it. Nothing is
seeded, fetched, or written — a media that is not cached yet is just reported as one that would be downloaded.
`--backend` turns this into a question about a different backend: whether the blueprint would work on VirtualBox or
Hyper-V, answered from what that backend can do, with nothing installed and nothing booted.

```powershell
rlq create-machine --blueprint freedos --dry-run
rlq create-machine --blueprint freedos --dry-run --backend hyperv
```

Vendor media is cached and verified against pinned SHA-256 hashes on every use, under `cache/media/`
(`Documents\reliquary` by default; override the payload cache with `--media-dir`, or move everything
at once with `--home-dir` or the `RELIQUARY_HOME` environment variable).

A run **returns its output** and stores nothing: it streams its progress live — `--progress pretty` for a person,
`--progress jsonl` for a program — and the stream is gone once the run ends. Redirect it if you want to keep it. When
a run fails, the report names what it was waiting for, which timeout expired, which branch of the script it took,
the screen row that came closest to matching, a screenshot, and the command to try next. Pass `--display` to show
the QEMU window instead of running headless — helpful when debugging a script.

**Screens that text cannot describe are watched as images.** A
*landmark* is a `<name>.rlql` declaration in your `landmarks/`
directory with one or more PNG renderings beside it
(`<name>.1.png`, `<name>.2.png` — alternative screenshots of the same
screen), and a script watches one exactly where it would watch for a
string:

```rlqs
wait @setup-page timeout=2m
```

The whole screen has to match pixel for pixel by default, which is the safe choice: a screen that has drifted times
out visibly instead of sending input to the wrong page. Rectangles in the declaration relax that rule where a screen
has changing decoration on it, such as a clock or a cursor — an `ignore` region is excluded from the match entirely,
and a `fuzzy` region is matched with its own tolerance (`"similarity": "97%"`). When nothing matches, the failure
report names the closest rendering, the regions it failed on, and the percentage each one reached. Watching a
landmark needs a control plane that can capture a framebuffer — `control-planes: ["vnc"]` on QEMU — and if the
machine's control plane cannot do that, Reliquary says so before the run touches the guest. The format is specified
in [docs/spec/landmarks.md](docs/spec/landmarks.md).

**GUI screens are clicked, not guessed at.** A landmark's `spots`
name points on it a script can click:

```rlqs
click @setup-page spot="next"
```

`click` finds the landmark the same way `wait` does: it waits for a matching, settled frame, and times out visibly
if the landmark never appears. It then sends a left click at the named spot (or the only spot, if the landmark
declares exactly one), and moves the cursor out of frame afterward. It needs an absolute pointing device — declare
`"devices": {"pointer0": "virtual-tablet"}` on the machine, because a relative mouse cannot be aimed without
guessing (a PS/2 mouse's guest driver applies acceleration the host cannot observe) — and a machine declaring
`emulated-mouse` is refused by name before the run starts.

## The machine layer

Beneath the scripts, Reliquary is a general automation harness for running remote tasks in QEMU guests, usable on its
own through the CLI and Python interfaces documented below.

DOS is the default and currently the only complete platform workflow. It boots a DOS guest, types at its keyboard,
reads its VGA text screen, runs commands, takes screenshots, and retrieves files written by the guest. Other
platform names reserve the same general QEMU lifecycle, but calling a provisioning or guest-task operation on them
currently raises `NotImplementedError`, until an adapter for that platform is implemented.

## The platform model

A blueprint names its guest platform in the required `platform` field;
`new-blueprint` scaffolds `dos` by default. DOS is the only complete
workflow today — other platform names reserve the same general QEMU
lifecycle, but raise `NotImplementedError` for provisioning and
guest-task operations until an adapter is implemented. Reliquary never
guesses the platform from an image. Future adapters can define how a
guest is provisioned, how a remote task is launched, and how its result
is collected, while reusing the same QEMU machine layer and its identity
checks.

## Why the DOS adapter exists

Automating a modern virtual machine usually means installing a guest agent, opening a network connection, or reading a
serial console. Those options are often unavailable in DOS, and they are especially unsuitable when the software under
test is the driver that would provide that communication.

Reliquary therefore works **agentlessly**:

- Input is sent as keyboard events through QEMU's control protocol.
- Text is read directly from VGA text memory, without OCR.
- Files are exchanged through a share — a host directory presented to
  the guest, either as a QEMU virtual FAT drive (`model: vvfat`,
  which needs nothing in the guest) or live over virtio-9p.
- Command completion is detected by watching for the DOS prompt.
- Screenshots are captured through QEMU.

The guest needs no Reliquary software, network driver, serial driver, or background service. This makes the harness
useful even while the guest is partially configured or broken.

A blueprint may also select the `vnc` control plane (QEMU only for
now): the machine starts with a loopback VNC server, keys arrive as
VNC key events, and the screen is read off the framebuffer by
Reliquary's fixed-font recognizer. Nothing changes in the guest, so
it is equally agentless — see `control-planes` in the
[blueprint field reference](docs/blueprint-reference.md).

Any DOS with a bootable image works. A machine's drive slots each name a
**media** component, and that media component determines its own
content — a blank `materialize: new` disk of a given `size`, a
`difference`/`copy` over a payload, or a `use` attach (an image or an
ISO). A **share** slot works the same way but always `use`s its
media, and that media is always a host directory: the guest sees it
live, for as long as the machine runs. Reliquary builds (materializes)
any per-machine image under `cache/machines/<id>/disks/`. Any
QEMU-supported image format works; `*.img` and `*.iso` are treated as
raw. Reliquary hands back a guest program's raw output as-is;
interpreting it is left to the caller.

## The workflow

1. **Describe the machine.** Write a `<name>.rlqb` blueprint (by hand,
   with `rlq new-blueprint`, or by seeding one from the codex) declaring
   the platform, memory, and devices. Each drive names a **media**
   component, and that media component decides how it is built
   (materialized) — a blank `new` disk, a `difference`/`copy` over a
   payload, or a `use` attach. To hand the guest its own files, add a
   **share** instead: a device whose media is a host directory
   (`materialize: use`) — that directory *is* the share, visible to
   the guest for as long as the machine runs.
2. **Create a machine.** `rlq create-machine --blueprint <name>` builds
   one under a generated id (or `run-script` creates one on demand). The
   blueprint (including its media components) and its scripts are
   always enough to rebuild it, so a machine is never something you
   need to protect from deletion.
3. **Drive it.** Run an attached `.rlqs` script with
   `rlq run-script <label> --blueprint <name>`, or operate the machine
   interactively — `rlq start-machine`, then `exec` / `wait` / `screen` /
   `press` / `select` against it, then `rlq stop-machine`.
4. **Take the results.** A run returns its output to you and keeps
   nothing of its own. A small value comes back through a machine
   variable (`rlq get-machine-var`); a whole image comes back by
   swapping it out. Moving files is your job: `rlq get-machine-dir`
   prints the machine directory, and its shares and image drives are
   ordinary host files you can read or prepare with your own tools —
   a share's directory even while the machine is running.
5. **Recreate freely.** `destroy-machine` deletes a machine entirely and
   `recreate-machine` rebuilds it under the same id; `apply-blueprint`
   applies blueprint edits to a stopped machine.

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
| home | `--home-dir` | `RELIQUARY_HOME` | `Documents/reliquary` |
| blueprints | `--blueprints-dir` | `RELIQUARY_BLUEPRINTS_DIR` | `<home>/blueprints` |
| scripts | `--scripts-dir` | `RELIQUARY_SCRIPTS_DIR` | `<home>/scripts` |
| cache | `--cache-dir` | `RELIQUARY_CACHE_DIR` | `<home>/cache` |
| media | `--media-dir` | `RELIQUARY_MEDIA_DIR` | `<cache>/media` |
| machines | `--machines-dir` | `RELIQUARY_MACHINES_DIR` | `<cache>/machines` |

The home's own default is `reliquary/` under your Documents folder (the Windows known Documents folder — including when
redirected, e.g. into OneDrive — `~/Documents` on macOS, and `xdg-user-dir DOCUMENTS` on Linux/BSD). When no Documents
folder can be determined, it falls back to `~/reliquary`.

A flag overrides the environment variable, and both override the default. Setting the cache directory moves media
and machines with it, unless you have set those directories separately too — so `--cache-dir D:\reliquary-cache` is
enough on its own to keep the bulk of the data off a synced Documents folder. From Python, the same choice is
explicit: open your session on a `reliquary.Context(...)` filling in any of the directory arguments — or on a bare
home path — and the rest are derived the same way. The library reads no environment variables and picks no default:
you must give the session a home directory when you create it.

The layout is:

```text
Documents/reliquary/
├── blueprints/           composed blueprints you author (<name>.rlqb) —
│                         a machine plus its media/source/archive components
├── scripts/              automation scripts (<name>.rlqs)
├── fonts/                authored glyph fonts (<name>.rlqf beside its
│                         <name>.bin bank) — read from the home only
├── landmarks/            authored landmarks (<name>.rlql beside its
│                         <name>.1.png, <name>.2.png renderings) —
│                         read from the home only
└── cache/                regenerable; resolves independently
    │                     (--cache-dir) and can live elsewhere
    ├── media/            cached, hash-verified media payloads
    └── machines/<id>/    each materialized machine — its own directory
                          with machine.json (the state; while running its
                          `vm` section holds the live VM identity, and
                          any machine variables a script set), disks/
                          (per-machine images), screenshots/, and a
                          <backend>/ subdir (e.g. qemu/qemu-stderr.log).
                          A run stores nothing here — it returns its
                          output to whoever started it
```

A machine exists entirely as its entry under the machines directory — there is no separate record of it at the
home's root. Everything under the cache can be regenerated. When you have not named a home directory, the one
Reliquary picked is printed to standard error.

Blueprints (with their media/source/archive components) and scripts are read from the `blueprints` and `scripts`
directories above, each searched recursively by file extension. Fonts and landmarks are read the same way, from
`fonts` and `landmarks` — but those two directories are always under the home and cannot be relocated separately, so
a project tree holding its own blueprints and scripts still finds fonts and landmarks under the home. If a name is
not found in these directories, Reliquary does **not** look anywhere else for it — the built-in codex is not a
fallback, so a name it does not hold is refused rather than silently supplied (the refusal names `rlq seed-blueprint
<name>` when the codex library does have that name). For a project, point the directories at your own tree:

```powershell
rlq --blueprints-dir .\vm --scripts-dir .\vm run-script install --blueprint freedos
```

Your source-controlled files are the only source, so a run is reproducible and never picks up whatever happens to be
sitting in your home directory. Seeding works wherever you point it — `rlq --blueprints-dir .\vm seed-blueprint
freedos` copies a first draft into your project, for you to commit. The embedding (Python) API is stricter still: it
assigns no directory at all, so a library call refuses (fails closed) rather than reading a developer's home
directory — and it cannot reach the codex library either, since the codex commands are CLI-only. A machine records
which blueprint file it was built from, so a `--blueprint <name>` selection only ever picks a machine built from the
blueprint that the current command resolves to — two projects that happen to share a blueprint name never disturb
each other's machines.

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

`create-machine` builds the machine's per-machine images under
`cache/machines/<id>/disks/` and prints the generated id. (If a
machine from this blueprint already exists — for example, one installed
by `run-script install` — you can start it directly.)

### 2. Start it

```powershell
rlq start-machine --blueprint freedos
```

Reliquary picks the backend, starts it headless, assigns the VM a
unique identity, and records that identity in the machine's
`machine.json` (in a `vm` section, written while the machine is
running). Later commands find the running VM through the machine
selector, so you never have to copy any connection details by hand —
how the backend is reached is handled internally by its adapter. The
machine stays running until you stop it. Add `--display` for a visible
window you can interact with manually.

### 3. Reach the DOS prompt

`start-machine` returns when QEMU is ready, not when DOS is. Wait for a
prompt before running commands:

```powershell
rlq wait-ready --blueprint freedos
```

If a guest's `AUTOEXEC.BAT` customizes the prompt, tell Reliquary what it
looks like — `rlq wait-ready --prompt "[C:\]>" --blueprint freedos`;
the standard prompt is always recognized without asking. For any other
boot-time signal, `rlq wait <pattern>` is the general-purpose wait over
the whole screen.

### 4. Run DOS commands

```powershell
rlq exec "dir" --blueprint freedos
rlq exec "myprog.exe > result.log" --blueprint freedos
```

`exec` types the command and waits for the DOS prompt to come back. To
capture detailed output, add a **share** to the machine — a device
whose media is a host directory (`materialize: use`) — and have the
program write to it. While the machine is stopped, that directory is
just an ordinary folder on the host (`rlq get-machine-dir` prints its
path).

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

Stopping checks the VM's recorded identity before shutting it down, and
flushes any guest writes to a `vvfat`-model share back to disk. QEMU
takes a snapshot of a `vvfat` share's directory when the machine
starts, so after changing its files on the host, stop and restart the
machine before the guest will see the changes — that is `vvfat`'s
trade-off for needing no guest driver at all. A `9pfs` share has no such
step: it is live in both directions while the machine runs.

## Command guide

### Installed backends

```text
rlq list-backends
```

`list-backends` shows the backends Reliquary discovers on this host and each
installation's home directory. Add `--json` for an array of `{backend, home}`
records.

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

`list-media` lists the media names that resolve from your own active
blueprints and scripts directories — never from the built-in codex.
`fetch-media` resolves one by name and downloads it into the cache.

Everything cached lives in one place, `cache/media/`, keyed by the
media's own name — an archive (a container such as a zip or tar file)
is a media like any other, so there is no separate archive cache.
`clean-media` deletes anything that can simply be re-fetched or
rebuilt. `prune-media` is smarter about it: it keeps whatever the
current blueprints can still use and deletes anything that existed
only to produce something else, so after an install the extracted ISO
stays and the zip it was extracted from is deleted. `add-media` is how
you add a payload Reliquary cannot fetch on its own — a licensed ISO
you are not allowed to redistribute, for example — checked against the
blueprint's pinned hash and never deleted automatically afterward.

(Media are specs inside a `.rlqb` now, so there is no `delete-media`
command — removing one means editing the blueprint that declares it.)

### Driving a machine from a program

```text
rlq run-script LABEL (--blueprint NAME | --machine ID) [--progress MODE]
rlq get-machine-var KEY (--blueprint NAME | --machine ID)
rlq get-machine-dir (--blueprint NAME | --machine ID)
rlq insert-media SLOT --file PATH (--blueprint NAME | --machine ID)
```

This is the loop a program driving Reliquary runs: put work into the
guest, run it, read the result back, repeat. Reliquary only supplies
the channels the data travels over — it does not interpret what
travels through them. There is no built-in pass/fail vocabulary and no
result parsing, because that is up to whatever you are building.

Values come back as **machine variables**: a script's `set result
"PASS"` writes one, and `get-machine-var result` reads it back from any
process. They are cleared each time the machine starts, so a variable
always reports what the current boot produced. Readiness works the
same way — your own ready script sets a variable and you poll for it;
Reliquary does not ship a readiness script of its own.

**Moving files is your job; Reliquary just supplies the drives and
shares they cross on.** It does not put files onto a machine's drives
or shares, does not read any back, and never tells you which drive
letter the guest gave a volume — what is inside one is yours to reach
with your own tools. There are three ways to get files across, and
none of them requires Reliquary to look inside a filesystem:

- **A share.** Add a `share` device whose media is a host directory,
  and the guest sees it as a volume for as long as the machine runs.
  QEMU serves it two ways. `model: vvfat` is QEMU's own synthesized
  FAT volume and needs nothing loaded in the guest, but it is a
  snapshot: you write into the host directory and the guest reads it,
  the guest writes and you read it back on the host, and both
  directions only take effect across a stop/start, because QEMU takes
  a snapshot of the directory when the machine starts. Leaving `model`
  out gets you virtio-9p instead, which is live in both directions
  while the machine runs — at the cost of a QEMU built with fsdev
  support and a 9P driver loaded in the guest.
- **A whole image, swapped live.** `insert-media --file` mounts an
  image you built, without a reboot, and ejecting flushes the guest's
  writes back to that same file. Build and read it with whatever
  image library you like — [remanence][remanence] opens raw and qcow2
  disks in place and reads and writes the FAT volumes inside them.
- **The machine directory.** `get-machine-dir` prints it. While the
  machine is stopped its drives and shares are plain files: a share
  *is* its directory, and an image drive is a raw or qcow2 file.

[remanence]: https://pypi.org/project/remanence/

```powershell
rlq insert-media floppy0 --file .\round-7.img --machine rig-0
rlq run-script test --machine rig-0 --progress jsonl > run.jsonl
rlq get-machine-var result --machine rig-0
rlq stop-machine --machine rig-0
rlq get-machine-dir --machine rig-0
```

`--progress` selects how progress is shown while it runs: `pretty` for
a person, `plain` for a log, `jsonl` for a program (stdout carries only
the event stream, with the last line being the outcome). Exit codes
report the outcome too, and they mean the same thing on every command,
not just a script run — `2` means your input was invalid on its face,
`3` means it was valid but the actual situation did not satisfy it,
`4` means the operation started and then failed, `5` means it was
cancelled, and `1` means a fault in Reliquary itself, never a mistake
on your part.

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
rlq wait CONDITION
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

The CLI is a thin layer over the embedding (Python) API: every command
maps one-to-one onto a session method with the same behavior. The
session is the only entry point, and the library assigns no default
home directory, so you open one on your own path. To run a whole
script, `session.run_script("install", blueprint="freedos")` is the
one call you need. To drive a machine directly, create and start it,
then attach the interaction adapter to the machine's own directory —
that is where its recorded identity lives, so ownership is verified
against it:

```python
import reliquary

session = reliquary.Session(r"C:\path\to\your\reliquary-home")
machine_id = session.create_machine("freedos")
session.start_machine(machine_id)
home = session.machine_dir_path(machine_id)
machine = reliquary.Machine(home)
guest = reliquary.AgentlessGuestExec(machine)

try:
    guest.wait_ready()
    guest.execute("dir", timeout=15)
    print("\n".join(machine.screen_text()))
    machine.screenshot("after-test")
finally:
    session.stop_machine(machine_id)
```

If a guest's `AUTOEXEC.BAT` customizes the prompt, say so at the call —
`guest.wait_ready(prompt="[C:\\]>")`, the exact text the guest
displays — because at that point there is no earlier screen
`wait_ready` could read the prompt from. `execute` needs no such
argument, since it reads the prompt directly off the screen it is
typing into.

`Machine` also exposes the VGA text screen directly: `machine.screen_text()`
returns the 80x25 rows, and `machine.wait_text(pattern, timeout=60)` polls until one row of the screen matches a
regular expression (whitespace-collapsed, never matched across rows) and the screen underneath it has stopped
changing. It returns the matching screen, or raises `WaitExpired`, which is both a `RunFailure` and a `TimeoutError`.
This is the script language's `wait` verb, available at the API level, the same way `rlq wait` exposes it on the
CLI. This is how to wait for specific output, such as a boot menu:

```python
machine.wait_text(r"Welcome to FreeDOS")
```

Once a cursor-key menu is displayed, `machine.cursor_menu_select()`
navigates it by watching what actually happens on screen: it presses
up/down, follows the selection highlight through the VGA attribute
bytes, and presses Enter only once the highlight sits on the row
matching the given text (case-insensitive; an exact row match wins over
rows that merely contain the item, which otherwise must be unique).
`exclude=` takes text snippets whose rows are never selected, as
another way to disambiguate. The item must match when navigation
starts. If a menu rewrites its own rows as the highlight moves — the
FreeDOS installer's language chooser translates every entry into the
newly highlighted language — navigation then follows the row position
instead, and the returned text is whatever the selected row displayed
at the moment Enter was pressed:

```python
machine.wait_text(r"Welcome to FreeDOS")
machine.cursor_menu_select("Use FreeDOS 1.4 in Live Environment mode")
```

These screen and keyboard operations live on the platform-neutral
`Machine` class, so they work on any guest displaying through VGA text mode — boot menus and loaders included, even
before any operating system is up. Module-level convenience functions (`reliquary.cursor_menu_select(item,
home=machine_dir)`, `reliquary.screen_text(home=machine_dir)`, and so on) just wrap the same methods.

`Machine.qmp()` exposes the identity-verified QMP session when a caller needs raw monitor access. The yielded QEMU
session provides both `cmd()` for QMP and
`hmp()` for human-monitor commands:

```python
with machine.qmp() as qmp:
    status = qmp.cmd("query-status")
    blocks = qmp.hmp("info block")
```

### Running scripts and managing machines

The lifecycle and scripting commands are all available as Python calls
with the same names as their CLI counterparts: `create_machine` /
`start_machine` / `stop_machine` / `destroy_machine` /
`recreate_machine` / `apply_blueprint`, and `run_script` for running a
`.rlqs` script. `run_script` **returns the run's output** — the whole
event stream, plus the final script phase and the machine's phase —
and writes nothing to disk; on failure it raises an exception of the
matching error class. See the [API reference](docs/api-reference.md)
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
uses the same `--home-dir` / `RELIQUARY_HOME` and the same machine
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

Stop the machine before reading files the guest wrote to a `vvfat`-model share. Writes are flushed back to the host during shutdown.

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
