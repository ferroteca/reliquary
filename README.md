# Reliquary

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

Read the [Blueprint guide](docs/blueprint-guide.md) for the implemented
milestone-1 surface, the [CLI reference](docs/cli-reference.md) for
commands, and the [API reference](docs/api-reference.md) for the
Python surface. The full design (including fields not yet implemented) is in
[The machine blueprint](planning/design/machine-blueprint.md) —
starting with "The model at a glance" and its diagrams — and
[Machine blueprints and machines](planning/design/instance-model.md).

> **Status:** milestone-1 blueprint materialization, lifecycle CLI
> (`create-machine` / `start-machine` / `stop-machine` /
> `destroy-machine` / `list-machines`), and
> `rlq run-script <label> --blueprint NAME` (resolve, create-if-none, run
> records, persistent `insert`/`eject`) are implemented for the
> QEMU/DOS subset.

## Installation

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

On macOS or Linux, activate the environment with:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

## Scripting OS installations

Installing registers two equivalent commands: `rlq` (the short form used throughout the docs) and `reliquary`.

```powershell
rlq --help
rlq run-script install --blueprint freedos-1.4-plain
```

From a clean home, that one command materializes a machine from the codex's `freedos-1.4-plain` blueprint (seeding the
blueprint — its LiveCD media rides inside it — and its scripts into your home as ordinary user-owned files), inserts the
fetched, hash-verified LiveCD to the blueprint's empty CD drive, boots it, and drives the FreeDOS installer end to end —
language, partitioning, the reboot, the "Plain DOS system" package set — until the guest powers itself off and the
script ejects the CD. The machine is left with FreeDOS installed on its hard disk; confirm it boots, then start and stop
it freely:

```powershell
rlq run-script verify --blueprint freedos-1.4-plain
rlq start-machine --blueprint freedos-1.4-plain
rlq stop-machine --blueprint freedos-1.4-plain
```

To inspect a script without running it, `rlq check-script` prints
the resolved timing plan (each observation's timeout and where it
came from):

```powershell
rlq check-script freedos-1.4-plain-install
rlq check-script install --blueprint freedos-1.4-plain
```

Vendor media is cached and verified against pinned SHA-256 hashes on every use: source archives under `cache/archives/`,
extracted payloads under `cache/media/` (`Documents\reliquary` by default; override with `--home` or the
`RELIQUARY_HOME` environment variable). Each script run writes a transcript and screenshots under the machine's
`cache/machines/<id>/runs/` directory. Pass `--display` to show the QEMU window instead of running headless — helpful
when debugging a script.

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
4. **Collect the results.** Script runs leave a transcript, screenshots,
   and outputs under the machine's `cache/machines/<id>/runs/` records.
   For files, `rlq get-machine-dir` prints the machine directory: while
   the machine is stopped, its directory-source and image drives are
   ordinary host state to read or prepare.
5. **Recreate freely.** `destroy-machine` deletes a machine entirely and
   `recreate-machine` rebuilds it under the same id; `apply-blueprint`
   adopts blueprint edits into a stopped machine.

## Requirements

Reliquary requires:

- Python 3.9 or newer
- QEMU with `qemu-system-i386` (and `qemu-img` to create hard-disk images)

The Python package installs QEMU's official `qemu.qmp` library. QEMU itself is a separate application and must be
installed on the host.

Reliquary searches for QEMU in this order:

1. `RELIQUARY_QEMU_HOME` environment variable
2. `QEMU_HOME` environment variable
3. The system `PATH`
4. Common installation directories on Windows, macOS, and Linux

`--qemu PATH` and the Python `qemu=` argument can select a specific binary.

## The Reliquary home directory

Reliquary keeps its persistent state in one visible home directory. The default is `reliquary/` under your Documents
folder (the Windows known Documents folder — including when redirected, e.g. into OneDrive — `~/Documents` on macOS, and
`xdg-user-dir DOCUMENTS` on Linux/BSD). When no Documents folder can be determined, it falls back to `~/reliquary`.

Choose a different home with any of these methods:

1. The `--home <reliquary_home>` command-line option
2. The `RELIQUARY_HOME` environment variable
3. The Python `reliquary.set_home()` function

The platform Documents lookup itself is available as
`reliquary.documents_dir()`, returning the folder path or `None` when it cannot be determined, for callers that want to
anchor their own directories the same way.

The layout is:

```text
Documents/reliquary/
├── blueprints/           composed blueprints you author (<name>.rlqb) —
│                         a machine plus its media/source/archive components
├── scripts/              automation scripts (<name>.rlqs)
└── cache/                regenerable; resolves independently (--cache /
    │                     RELIQUARY_CACHE_DIR) and can live elsewhere
    ├── archives/         cached source archives (redownloadable)
    ├── media/            cached, hash-verified media payloads
    └── machines/<id>/    each materialized machine — its own directory
                          with machine.json (the state; while running its
                          `vm` section holds the live VM identity), media/
                          (per-machine images), runs/ (transcripts +
                          screenshots), and a <backend>/ subdir (e.g.
                          qemu/qemu-stderr.log)
```

A machine is wholly its `cache/machines/<id>/` directory — there is no
root-home machine model. Everything under `cache/` is regenerable. The
selected home is printed to standard error the first time it is used.

Authored assets (blueprints — with their media/source/archive
components — and scripts) resolve in one of two modes. By default —
**home mode** — Reliquary reads the home's `blueprints/` / `scripts/`
folders and seeds any name it does not find from the built-in codex;
this is the convenient path for interactive use. Point `--assets <dir>`
at a project directory instead
and Reliquary resolves **solely** from that tree (walked recursively by
file extension): no home, no codex, no seeding. That is the mode for
automation — assets are your project's source-controlled files, so a run
is reproducible and never picks up whatever happens to be in your home.
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
rlq seed-blueprint freedos-1.4-plain
rlq create-machine --blueprint freedos-1.4-plain
```

`create-machine` materializes the machine's per-machine images under
`cache/machines/<id>/media/` and prints the generated id. (If a
machine of this blueprint already exists — e.g. one installed by
`run-script install` — you can start it directly.)

### 2. Start it

```powershell
rlq start-machine --blueprint freedos-1.4-plain
```

Reliquary chooses an available local QMP port, starts QEMU headless,
assigns the VM a unique identity, and records it in the machine's
`machine.json` (as a `vm` section, written while running). Later
commands find the running VM through the machine selector, so the port
never needs to be copied by hand. The machine
stays running until you stop it. Add `--display` for a visible,
manually interactive QEMU window; `--port PORT` requests a particular
QMP port (an occupied port is refused).

### 3. Reach the DOS prompt

`start-machine` returns when QEMU is ready, not when DOS is. Wait for a
prompt before running commands:

```powershell
rlq wait "C:\\\\>" --blueprint freedos-1.4-plain
```

### 4. Run DOS commands

```powershell
rlq exec "dir" --blueprint freedos-1.4-plain
rlq exec "myprog.exe > result.log" --blueprint freedos-1.4-plain
```

`exec` types the command and waits for the DOS prompt to return. To
retrieve detailed output, name a directory-source media (`source` a
host directory, `materialize: use`) on a machine drive and have the
program write to it; while the machine is stopped, that directory is
ordinary host state (`rlq get-machine-dir` prints the path).

### 5. Inspect the guest

```powershell
rlq screen --blueprint freedos-1.4-plain
rlq screenshot after-test --blueprint freedos-1.4-plain
```

`screen` prints the current 80-by-25 text screen; `screenshot` saves a
PNG under the machine's run directory. Screenshot names are filename
stems, not paths.

### 6. Stop it

```powershell
rlq stop-machine --blueprint freedos-1.4-plain
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
rlq create-machine --home $scratch --blueprint plain
rlq start-machine --home $scratch --blueprint plain --display
rlq stop-machine --home $scratch --blueprint plain
rlq list-machines --home $scratch
```

### Media catalog

```text
rlq list-media [--builtin]
rlq fetch-media NAME
rlq clean-archives
rlq clean-media
```

`list-media` names the `media` components resolvable from the active
source (or the package codex with `--builtin`). `fetch-media` resolves
a media by name and warms its cached payload. `clean-archives` and
`clean-media` reclaim the cached source archives (`cache/archives/`)
and payloads (`cache/media/`); both are safe — anything with a source
refetches. (Media are components inside a `.rlqb` now, so there is no
`delete-media` command — removing one means editing the blueprint that
declares it.)

### Keyboard and command input

```text
rlq type TEXT
rlq enter LINE
rlq press KEY [KEY ...]
rlq exec COMMAND
rlq select ITEM [--exclude TEXT]
```

Every guest-console command targets a running machine — select it with
`--blueprint <name>` / `--machine <id>` (as in the [First
session](#first-session)) or address a QMP port directly with
`--port <n>`. The examples below omit the selector for brevity.

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
script, `reliquary.run_script("install", blueprint="freedos-1.4-plain")`
is the one call. To drive a machine directly, create and start it, then
attach the interaction adapter to the returned port and the machine's
directory (so ownership is verified against its recorded identity):

```python
import reliquary

machine_id = reliquary.create_machine("freedos-1.4-plain")
port = reliquary.start_machine(machine_id)
home = reliquary.machine_dir_path(machine_id)
machine = reliquary.Machine(port, home=home)
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
`recreate_machine` / `apply_blueprint`, and `run_script` /
`check_script` for the `.rlqs` language. `run_script` returns a result
describing the run (its record directory, final script phase, and the
machine's phase) and writes a transcript and screenshots under the
machine's `runs/` directory. See the [API reference](docs/api-reference.md)
for the full surface and [`planning/design/api.md`](planning/design/api.md)
for the end-goal design.

## Troubleshooting

### QEMU cannot be found

Install QEMU and put `qemu-system-i386` on `PATH`, set
`RELIQUARY_QEMU_HOME` to the QEMU installation directory, or pass
`--qemu PATH`.

### A command cannot find an active VM

Guest-console commands find the running VM through the `vm` section of
the machine's `cache/machines/<id>/machine.json`. Ensure every command
uses the same `--home` / `RELIQUARY_HOME` and the same machine
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

BSD-3-Clause. See [LICENSE](LICENSE).

The name **Reliquary** is owned by Paul Galbraith and is not licensed
for use by forks or redistributions. See [TRADEMARKS.md](TRADEMARKS.md).
