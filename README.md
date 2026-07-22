# reliquary

reliquary helps to automate guest VMs, it can script OS installations from standard vendor installation media and
produce bootable disk images without manual interaction. It can help execute one-off comamnds and capture the restuls.
It is built on its own agentless QEMU guest automation layer, which owns QEMU lifecycle, media, QMP identity checks,
keyboard input, screen access, screenshots, and per-run state.

reliquary machines are ephemeral: disposable rigs for scripted installs and automated guest tasks, cheap to destroy and
recreate. The machine is never the product — often nothing durable comes out at all (the point was to run some tests).
reliquary is not a VM manager for machines you keep.

## Blueprints and machines

The first thing to learn is reliquary's central model. A **blueprint** is a reusable JSON design you author and keep —
a `<name>.rlqb` file, conventionally under `<reliquary_home>/blueprints/`. A **machine** is a disposable realization reliquary builds from it,
identified by a generated id — one blueprint, many machines. Machines are created, run, destroyed, and recreated freely:
the blueprint (with media definitions and scripts) is always enough to rebuild one, so nothing reliquary materializes is
ever precious. Editing a blueprint never changes an existing machine by itself; a machine keeps the snapshot it was
created from. To adopt blueprint edits, destroy the machine and create it again.

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
blueprint, its scripts, and the LiveCD media definition into your home as ordinary user-owned files), inserts the
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

Vendor media is cached and verified against pinned SHA-256 hashes on every use: source archives under`cache/downloads/`,
extracted payloads under `cache/media/` (`Documents\reliquary` by default; override with `--home` or the
`RELIQUARY_HOME` environment variable). Each script run writes a transcript and screenshots under the machine's
`cache/machines/<id>/runs/` directory. Pass `--display` to show the QEMU window instead of running headless — helpful
when debugging a script.

## The machine layer

Beneath the scripts, reliquary is a general automation harness for running remote tasks in QEMU guests, usable on its
own through the CLI and Python interfaces documented below.

DOS is the default and currently the only complete platform workflow. It boots a DOS guest, types at its keyboard, reads
its VGA text screen, runs commands, takes screenshots, and retrieves files written by the guest. Other platform names
reserve the generic QEMU lifecycle but their provisioning and guest-task semantics currently raise
`NotImplementedError` until an adapter is implemented.

## The platform model

Omitting the platform selects DOS. This preserves a complete, immediately useful default:

```python
machine = reliquary.Runner()  # uses the established default home
```

The CLI likewise defaults to `--platform dos`. Platform-specific behavior is never inferred from an image. Future
adapters can define how a guest is provisioned, how a remote task is launched, and how its result is collected while
reusing the same ownership-verified QEMU machine layer.

## Why the DOS adapter exists

Automating a modern virtual machine usually means installing a guest agent, opening a network connection, or reading a
serial console. Those options are often unavailable in DOS, and they are especially unsuitable when the software under
test is the driver that would provide that communication.

reliquary therefore works **agentlessly**:

- Input is sent as keyboard events through QEMU's control protocol.
- Text is read directly from VGA text memory, without OCR.
- Files are exchanged through a QEMU virtual FAT drive.
- Command completion is detected by watching for the DOS prompt.
- Screenshots are captured through QEMU.

The guest needs no reliquary software, network driver, serial driver, or background service. This makes the harness
useful even while the guest is partially configured or broken.

Any DOS with a bootable image works. The `<reliquary_home>/drives` directory declares the whole machine: image files
named `floppy[_<n>].<ext>`, `hdd[_<n>].<ext>`, and `cdrom[_<n>].<ext>` mount as that medium and slot, and bare
directories named `floppy[_<n>]` and `hdd[_<n>]` mount as virtual FAT drives. Any QEMU-supported image format works —
the extension declares the format, with `*.img` and `*.iso` taken as raw. reliquary hands back a guest program's raw
output, and interpreting it is left to the caller.

## The workflow

1. **Provide the guest.** Place the bootable DOS image of your choice under `<reliquary_home>/drives` — a floppy image
   as `floppy.<ext>` (typically `floppy.img`), or a hard-disk image as `hdd.<ext>` (e.g. `hdd.qcow2`). To create an
   empty sparse qcow2 v3 hard disk for later partitioning or imaging:

   ```python
   reliquary.create_hdd_image(
       os.path.join(reliquary.drives_dir(), "hdd.qcow2"),
       "2G",
   )
   ```

2. **Stage the files.** Collect everything the guest should work with — your programs, test executables, data files, and
   any DOS utilities they depend on — place them in a `<reliquary_home>/drives/hdd` folder (or `hdd_1` behind a
   hard-disk boot image, which claims slot 0). reliquary attaches the folder as a virtual FAT hard disk — `C:` when it
   is the first hard disk, one letter later per disk before it. A `floppy`/`floppy_<n>` folder is likewise attached as a
   virtual FAT 1.44 MB floppy.
3. **Let reliquary operate the machine.** Boot to the DOS prompt, then use reliquary as your agent at the keyboard: run
   commands, send keystrokes, wait for text to appear, read the screen, take screenshots.
4. **Collect the results.** Have programs write their output to files on drive C:. After the VM stops, those files are
   left in the staging directory on the host and the caller can interrogate them to interpret the results.

## Requirements

reliquary requires:

- Python 3.9 or newer
- QEMU with `qemu-system-i386` (and `qemu-img` to create hard-disk images)

The Python package installs QEMU's official `qemu.qmp` library. QEMU itself is a separate application and must be
installed on the host.

reliquary searches for QEMU in this order:

1. `RELIQUARY_QEMU_HOME` environment variable
2. `QEMU_HOME` environment variable
3. The system `PATH`
4. Common installation directories on Windows, macOS, and Linux

`--qemu PATH` and the Python `qemu=` argument can select a specific binary.

## The reliquary home directory

reliquary keeps its persistent state in one visible home directory. The default is `reliquary/` under your Documents
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
├── blueprints/           machine blueprints you author
├── media/                shared media definitions
├── scripts/              automation scripts (.rlqs)
├── drives/               the machine's declared drives
│   ├── floppy.img        a boot floppy image (slot 0 = A:)
│   ├── hdd/              a folder exposed as a virtual FAT hard disk
│   └── ...               hdd_1.qcow2, cdrom.iso, floppy_1/, ...
├── machine.json          optional legacy CLI config for bare `rlq start-machine`
├── screenshots/          captured PNG files
├── qemu-stderr.log       diagnostics from the last QEMU start
├── vm.json               identity and port of the active VM
└── cache/
    ├── downloads/        cached source archives (redownloadable)
    ├── media/            cached media payloads
    └── machines/         materialized machine directories
```

All files created by reliquary stay under this home. The selected home is printed to standard error the first time it is
used.

## First session

### 1. Declare the machine's drives (optional)

Everything under `<home>/drives` whose name states a medium is mounted; reliquary never inspects the content — the name
is the declaration. Image files mount as their medium and slot: `floppy[_<n>].<ext>` (slots 0–1, drives `A:` and
`B:`), `hdd[_<n>].<ext>` (slots 0–3, the IDE bus), and `cdrom[_<n>].<ext>` (placed on the IDE slots after the hard
disks; their `<n>` only orders them). An unindexed name means slot 0, so `hdd.img` and `hdd_0.img` clash. Any
QEMU-supported image format works: the idiomatic extension declares the format — `*.img` and `*.iso` are taken as raw
(so `floppy.img` and `cdrom.iso` mount without QEMU's format-probing warning), and any other extension (`hdd.qcow2`,
`hdd.vmdk`, ...) is handed to QEMU to identify.

To use a particular DOS — MS-DOS, DR-DOS, or another distribution — copy its bootable image in as, say,
`drives/floppy.img` or `drives/hdd.qcow2`.

The boot order defaults to a best guess — the slot-0 floppy image, else the slot-0 hard-disk image, else the cdrom — and
memory defaults to 16 MB; pass `-boot` or `-m` after `--` on `rlq start-machine` to override either.

Guest drive letters follow disk order, so a hard-disk boot image at slot 0 claims `C:` and pushes a staged virtual FAT
drive to `D:`; reliquary defaults the staged drive letter accordingly, and `staged_drive` overrides it (for example when
a multi-partition hard-disk image pushes the drive further down the alphabet).

### 2. Prepare the staged drive

Create a `drives/hdd` directory containing the DOS programs and files you want the guest to see — including any DOS
utilities your workflow needs that the boot image does not provide. It mounts as a writable virtual FAT hard disk. For
example:

```powershell
New-Item -ItemType Directory "$HOME\Documents\reliquary\drives\hdd"
Copy-Item .\MYPROG.EXE "$HOME\Documents\reliquary\drives\hdd\"
```

A directory can also be staged as a virtual 1.44 MB floppy (`drives/floppy`, or `drives/floppy_1` when a floppy image
already claims slot 0 / drive `A:`).

### 3. Start QEMU

```powershell
rlq start-machine
```

Everything declared under `drives/` is mounted. reliquary chooses an available local QMP port, starts QEMU, assigns the
VM a unique identity, and records it in `<home>/vm.json`. Later CLI commands find the active VM from that file, so the
port normally does not need to be copied manually.

For a visible, manually interactive DOS session, start QEMU with its display enabled:

```powershell
rlq start-machine --display
```

The command returns once QEMU is ready, while the VM and its display remain open. Give the QEMU window focus and use it
like a DOS computer for as long as needed. When the manual session is finished, close the VM safely from the same
terminal (or another terminal using the same reliquary home):

```powershell
rlq stop-machine
```

This shutdown verifies the VM's recorded identity before closing it and flushes guest writes to the virtual FAT drive.

Use `--port PORT` to request a particular QMP port. reliquary refuses to use an occupied port or control a VM whose
identity does not match its state file.

### 4. Reach the DOS prompt

`start-machine` returns when QEMU is ready, not when DOS is. Wait for a prompt before running commands:

```powershell
rlq wait "A:\\\\>"
```

A user-provided boot image must reach its prompt on its own, without interactive menus. Switch to the staged drive using
an ordinary DOS command:

```powershell
rlq exec "c:"
```

Programmatic workflows use `AgentlessGuestExec.wait_ready()`, which waits for a prompt.

### 5. Run DOS commands

```powershell
rlq exec "dir"
rlq exec "myprog.exe"
rlq exec "myprog.exe > result.log"
```

`exec` types the command and waits for a DOS prompt to return. Redirecting output to drive C: is the most reliable way to
retrieve detailed output. Guest writes become visible in the host staging directory after QEMU stops.

### 6. Inspect the guest

Print the current 80-by-25 text screen:

```powershell
rlq screen
```

Wait until the screen contains a regular expression:

```powershell
rlq wait "C:\\\\>"
```

Take a screenshot:

```powershell
rlq screenshot after-test
```

The image is saved as `<home>/screenshots/after-test.png`. Screenshot names are filename stems, not paths; directory
separators are rejected so captures remain under the reliquary home.

### 7. Stop QEMU

```powershell
rlq stop-machine
```

Stopping QEMU flushes writes from the virtual FAT drive and removes the active `vm.json` record.

QEMU snapshots the host directory when the virtual FAT drive is attached. After changing staged files on the host, stop
and restart QEMU before using them in the guest.

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
`cache/machines/<blueprint>-<n>/`.
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
rlq delete-media NAME
rlq fetch-media NAME
rlq clean-downloads
rlq clean-media
```

`list-media` names items in home ``media/`` (or the package codex with
`--builtin`). `delete-media` removes the home definition for an item
and refuses while a machine drive still holds it.

### Managing the VM (legacy root-home path)

```text
rlq start-machine [--display] [-- QEMU_ARGS...]
rlq stop-machine
```

Without `--blueprint` / `--machine`, bare `rlq start-machine` still loads an optional versioned JSON machine document from
`<home>/machine.json`. A missing home file means the ordinary defaults.

`version` is required and must be `1`. The document uses the same field names as `MachineConfig`: `platform`, `timeout`,
`staged_drive`,
`memory`, `qemu`, `machine`, `qemu_args`, and `drives`. Relative drive sources resolve from the file's directory. For
example:

```json
{
  "version": 1,
  "memory": 32,
  "machine": {
    "type": "pc",
    "accel": "tcg"
  },
  "drives": {
    "hdd_0": {
      "source": "../images/dos.qcow2",
      "options": {
        "snapshot": true
      }
    }
  }
}
```

Explicit CLI controls override the loaded file for that invocation:
`--platform`, `--qemu`, and raw QEMU arguments after `--`. Omitting
`--platform` leaves the file's platform (or the DOS default) unchanged; passing `--platform dos` overrides a non-DOS
file value.

Additional QEMU arguments can follow `--`:

```powershell
rlq start-machine -- -cpu 486 -device virtio-rng-pci
```

### Keyboard and command input

```text
rlq type TEXT
rlq enter LINE
rlq press KEY [KEY ...]
rlq exec COMMAND
rlq select ITEM [--exclude TEXT]
```

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
reliquary command.

Run `reliquary --help` or `reliquary COMMAND --help` for the complete current syntax.

## Python usage

The Python interface exposes the selected interaction adapter directly.
`start()` always returns the selected QMP port; construct the adapter with it so ownership is explicit in programmatic
workflows:

```python
import os
import shutil

import reliquary

stage = os.path.join(reliquary.drives_dir(), "hdd")
os.makedirs(stage, exist_ok=True)
shutil.copy("MYPROG.EXE", stage)
port = reliquary.start()
machine = reliquary.Machine(port)
guest = reliquary.AgentlessGuestExec(machine)

try:
    guest.wait_ready()
    guest.execute("c:", timeout=15)
    guest.execute("myprog.exe > result.log")
    print("\n".join(reliquary.screen_text(port=port)))
    reliquary.screenshot("after-test", port=port)
finally:
    reliquary.stop(port=port)
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

### Running a guest program end to end

`run_guest_program()` performs the complete agentless lifecycle for one DOS executable: stage it, boot DOS, switch to
C:, run it with its output redirected to a log file, stop QEMU, and return the log text.

```python
log = reliquary.run_guest_program("TESTS.EXE", args="-v")

print(log)
```

For the DOS platform, the executable must have an 8.3 `.EXE` filename. This is a DOS workflow policy, not a restriction
on guest-program workflows for other platforms. reliquary attaches no meaning to the output — interpreting it (for
example, parsing test-framework results) is the caller's job.

### Embedding reliquary as a runner

Callers that manage isolated runs (test harnesses, CI drivers) can use the `Runner` surface instead of the module-level
functions. A `Runner` is a configured DOS *test machine* bound to one home directory, which contains its drives,
staging, diagnostics, and VM identity:

```python
machine = reliquary.Runner(
    "run-42",
    reliquary.MachineConfig(
        platform="dos",
        timeout=120,
        memory=32,
        machine={"type": "pc", "accel": "tcg"},
        drives={"floppy": "images/msdos-boot.img"},
    ),
)

log = machine.run("TESTS.EXE", "-v")
```

Media can be declared by name under the runner's `drives/` directory or through `MachineConfig.drives`. Configured keys
are `floppy_0` through `floppy_1`, `hdd_0` through `hdd_3`, and `cdrom_0` through `cdrom_3`; `floppy` and `hdd`
are aliases for slot zero. A path value is shorthand for `{"source": path}`. A file source is mounted as an image, while
a floppy or hard-disk directory is mounted as vvfat; a CD-ROM directory is rejected. The object form also accepts QEMU
drive `options`, except for lifecycle-owned properties such as `file`, `if`, `index`, and `media`:

```python
config = reliquary.MachineConfig(drives={
    "hdd": {
        "source": "images/dos.qcow2",
        "options": {"snapshot": True},
    },
    "hdd_1": "guest-files",
})
```

The same versioned JSON document can be loaded from Python and overridden field-by-field. Relative drive sources in the
file resolve from the file's directory; Python overrides still resolve from the current directory:

```python
config = reliquary.MachineConfig.from_file(
    "machines/dos.json",
    timeout=90,
    qemu_args=("-cpu", "pentium"),
)
```

`MachineConfig.from_mapping(...)` accepts the same document shape in memory.
`version` is required in the document and must be `1`; it is not a constructor field. Explicit overrides win: scalars
replace (including `None`),
`qemu_args` and `machine` replace wholesale, and `drives` merge by logical slot then by entry field / option name. When
no configuration is provided, the API automatically discovers and loads `<home>/machine.json` if present; explicit API
values override the file values.

The module-level `start()`, `run_task()`, and `run_guest_program()` functions accept a `machine_config` containing a
`MachineConfig`, versioned mapping, or machine-document path. Machine settings such as `qemu`, `timeout`, `memory`, and
`drives` belong in that configuration; the functions expose only separate operational controls such as `display`,`port`,
and `home`.

Configured sources are mounted in place and must already exist. They conflict with a filesystem declaration for the same
logical slot rather than overriding it. `run()` keeps present bootable media. It then performs the `run_guest_program()`
lifecycle under the runner's home.
`machine` maps directly to QEMU's `-machine`: a string selects only the type, while a mapping requires `type` and may
add scalar machine properties. Booleans render as `on`/`off`; configuring both `machine` and `-machine` in
`qemu_args` is an error.
`memory` is a positive integer number of MiB. It defaults by platform: 16 for DOS, 64 for Win9x, and 256 for WinNT.
Configuring both `memory` and `-m` in
`qemu_args` is an error, while a raw `-m` alone suppresses the platform default.
`staged_drive` declares the guest drive letter where the staged virtual FAT drive appears — the drive `run()` switches
to and stages under (the highest staged directory declared among the hard-disk slots, or
`drives/hdd` created on demand). Its default matches the declared machine: C: with no hard disk before the staged drive,
one letter later per hard-disk slot before it (lower letters are rejected). Every
`MachineConfig` field has a working default, so `reliquary.Runner()` is a complete DOS machine using the established
default home. Pass `home=` to select another one, and create separate runners with separate homes for concurrent runs.
The same explicit `home=` keyword is available on the module-level functions (`start`, `stop`,
`run_guest_program`, and the path helpers) and overrides the process-global home per call.

## Troubleshooting

### QEMU cannot be found

Install QEMU and put `qemu-system-i386` on `PATH`, set
`RELIQUARY_QEMU_HOME` to the QEMU installation directory, or pass
`--qemu PATH`.

### A command cannot find an active VM

CLI commands use `<home>/vm.json`. Ensure every command uses the same
`--home` or `RELIQUARY_HOME` value and that `rlq start-machine` completed successfully.

### The VM identity does not match

reliquary verifies the unique QEMU name before sending any command. An identity error means the recorded port now
belongs to another process or the state file is stale. The unrelated VM is not modified. Review
`<home>/vm.json` and `<home>/qemu-stderr.log`, then start a new reliquary VM.

### QEMU exits during startup

The error includes the selected port, QEMU exit status, command line, and path to `<home>/qemu-stderr.log`. That log
normally contains QEMU's reason, such as an invalid device option or an unavailable disk image.

### Guest-written files are missing

Stop QEMU before reading files written to the virtual FAT drive. Writes are flushed back to the host during shutdown.

## License

BSD-3-Clause. See [LICENSE](LICENSE).

The name **reliquary** is owned by Paul Galbraith and is not licensed
for use by forks or redistributions. See [TRADEMARKS.md](TRADEMARKS.md).
