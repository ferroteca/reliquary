# relict

relict is a Python automation harness for running remote tasks in QEMU guests. Its reusable machine layer owns QEMU
lifecycle, media, QMP identity checks, keyboard input, screen access, screenshots, and per-run state.

DOS is the default and currently the only complete platform workflow. It boots a DOS guest, types at its keyboard,
reads its VGA text screen, runs commands, takes screenshots, and retrieves files written by the guest. Other platform
names reserve the generic QEMU lifecycle but their provisioning and guest-task semantics currently raise
`NotImplementedError` until an adapter is implemented.

## The platform model

Omitting the platform selects DOS. This preserves a complete, immediately useful default:

```python
machine = relict.Runner()  # uses the established default home
```

The CLI likewise defaults to `--platform dos`. Platform-specific behavior is never inferred from an image. Future
adapters can define how a guest is provisioned, how a remote task is launched, and how its result is collected while
reusing the same ownership-verified QEMU machine layer.

## Why the DOS adapter exists

Automating a modern virtual machine usually means installing a guest agent, opening a network connection, or reading a
serial console. Those options are often unavailable in DOS, and they are especially unsuitable when the software under
test is the driver that would provide that communication.

relict therefore works **agentlessly**:

- Input is sent as keyboard events through QEMU's control protocol.
- Text is read directly from VGA text memory, without OCR.
- Files are exchanged through a QEMU virtual FAT drive.
- Command completion is detected by watching for the DOS prompt.
- Screenshots are captured through QEMU.

The guest needs no relict software, network driver, serial driver, or background service. This makes the harness
useful even while the guest is partially configured or broken.

Any DOS (e.g. MS-DOS or FreeDOS) with a bootable image works. The `<relict_home>/drives` directory declares the
whole machine: image files named `floppy[_<n>].<ext>`, `hdd[_<n>].<ext>`, and `cdrom[_<n>].<ext>` mount as that
medium and slot, and bare directories named `floppy[_<n>]` and `hdd[_<n>]` mount as virtual FAT drives. Any
QEMU-supported image format works — the extension declares the format, with `*.img` and `*.iso` taken as raw. When
nothing bootable is declared, the freely distributable FreeDOS 1.4 boot floppy is downloaded automatically and used
as the default. relict hands back a guest program's raw output, and interpreting it is left to the caller.

## The workflow

1. **Provide the guest.** Place the bootable DOS image of your choice under `<relict_home>/drives` — a floppy image
   as `floppy.<ext>` (typically `floppy.img`), or a hard-disk image as `hdd.<ext>` (e.g. `hdd.qcow2`) — or skip this
   step and let relict download a minimal FreeDOS system.
2. **Stage the files.** Collect everything the guest should work with — your programs, test executables, data files, and
   any DOS utilities they depend on — place them in a `<relict_home>/drives/hdd` folder (or `hdd_1` behind a
   hard-disk boot image, which claims slot 0). relict attaches the folder as a virtual FAT hard disk — `C:` when it
   is the first hard disk, one letter later per disk before it. A `floppy`/`floppy_<n>` folder is likewise attached
   as a virtual FAT 1.44 MB floppy.
3. **Let relict operate the machine.** Boot to the DOS prompt, then use relict as your agent at the keyboard: run
   commands, send keystrokes, wait for text to appear, read the screen, take screenshots.
4. **Collect the results.** Have programs write their output to files on drive C:. After the VM stops, those files are
   left in the staging directory on the host and the caller can interrogate them to interpret the results.

## Requirements

relict requires:

- Python 3.9 or newer
- QEMU with `qemu-system-i386`

The Python package installs QEMU's official `qemu.qmp` library. QEMU itself is a separate application and must be
installed on the host.

relict searches for QEMU in this order:

1. `RELICT_QEMU_HOME` environment variable
2. `QEMU_HOME` environment variable
3. The system `PATH`
4. Common installation directories on Windows, macOS, and Linux

`--qemu PATH` and the Python `qemu=` argument can select a specific binary.

## Installation

Create and activate a virtual environment, then install the project:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install relict
```

On macOS or Linux, activate the environment with:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install relict
```

## The relict home directory

relict keeps its persistent state in one visible home directory. The default is `relict/` under your Documents
folder (the Windows known Documents folder — including when redirected, e.g. into OneDrive — `~/Documents` on macOS, and
`xdg-user-dir DOCUMENTS` on Linux/BSD). When no Documents folder can be determined, it falls back to `~/relict`.

Choose a different home with any of these methods:

1. The `--home <relict_home>` command-line option
2. The `RELICT_HOME` environment variable
3. The Python `relict.set_home()` function

The layout is:

```text
Documents/relict/
├── drives/               the machine's declared drives
│   ├── floppy.img        a boot floppy image (slot 0 = A:)
│   ├── hdd/              a folder exposed as a virtual FAT hard disk
│   └── ...               hdd_1.qcow2, cdrom.iso, floppy_1/, ...
├── machine.json          optional machine configuration (CLI only)
├── screenshots/          captured PNG files
├── qemu-stderr.log       diagnostics from the last QEMU start
└── vm.json               identity and port of the active VM
```

All files created by relict stay under this home. The selected home is printed to standard error the first time it is
used.

## First session

### 1. Declare the machine's drives (optional)

Everything under `<home>/drives` whose name states a medium is mounted; relict never inspects the content — the
name is the declaration. Image files mount as their medium and slot: `floppy[_<n>].<ext>` (slots 0–1, drives `A:` and
`B:`), `hdd[_<n>].<ext>` (slots 0–3, the IDE bus), and `cdrom[_<n>].<ext>` (placed on the IDE slots after the hard
disks; their `<n>` only orders them). An unindexed name means slot 0, so `hdd.img` and `hdd_0.img` clash. Any
QEMU-supported image format works: the idiomatic extension declares the format — `*.img` and `*.iso` are taken as raw
(so `floppy.img` and `cdrom.iso` mount without QEMU's format-probing warning), and any other extension (`hdd.qcow2`,
`hdd.vmdk`, ...) is handed to QEMU to identify.

To use a particular DOS — MS-DOS, DR-DOS, a customized FreeDOS — copy its bootable image in as, say,
`drives/floppy.img` or `drives/hdd.qcow2`. When nothing bootable is declared, relict downloads the FreeDOS 1.4
FloppyEdition archive (roughly 23 MB), verifies its SHA-256 digest, extracts the 1.44M boot floppy as
`drives/floppy.img`, and discards the archive.

The boot order defaults to a best guess — the slot-0 floppy image, else the slot-0 hard-disk image, else the
cdrom — and memory defaults to 16 MB; pass `-boot` or `-m` after `--` on `relict start` to override either.

Guest drive letters follow disk order, so a hard-disk boot image at slot 0 claims `C:` and pushes a staged virtual
FAT drive to `D:`; relict defaults the staged drive letter accordingly, and `staged_drive` overrides it (for
example when a multi-partition hard-disk image pushes the drive further down the alphabet).

The FreeDOS boot floppy is a minimal system: the kernel, the FreeCOM command shell, and little else. Commands built into
the shell (`dir`, `copy`, `del`, `type`, `set`, ...) work, but external DOS utilities such as `xcopy`, `find`, or
`edit` are not included. If your workflow needs them, stage them on drive C: alongside your own files, or build a
custom boot image.

The download happens automatically on the first `relict start`; to fetch it ahead of time instead, run:

```powershell
relict download
```

### 2. Prepare the staged drive

Create a `drives/hdd` directory containing the DOS programs and files you want the guest to see — including any DOS
utilities your workflow needs that the boot image does not provide. It mounts as a writable virtual FAT hard disk.
For example:

```powershell
New-Item -ItemType Directory "$HOME\Documents\relict\drives\hdd"
Copy-Item .\MYPROG.EXE "$HOME\Documents\relict\drives\hdd\"
```

A directory can also be staged as a virtual 1.44 MB floppy (`drives/floppy`, or `drives/floppy_1` when a floppy image
already claims slot 0 / drive `A:`).

### 3. Start QEMU

```powershell
relict start
```

Everything declared under `drives/` is mounted. relict chooses an available local QMP port, starts QEMU,
assigns the VM a unique identity, and records it in `<home>/vm.json`. Later CLI commands find the active VM from that
file, so the port normally does not need to be copied manually.

For a visible, manually interactive DOS session, start QEMU with its display enabled:

```powershell
relict start --display
```

The command returns once QEMU is ready, while the VM and its display remain open. Give the QEMU window focus and use
it like a DOS computer for as long as needed. When the manual session is finished, close the VM safely from the same
terminal (or another terminal using the same relict home):

```powershell
relict stop
```

This shutdown verifies the VM's recorded identity before closing it and flushes guest writes to the virtual FAT drive.

Use `--port PORT` to request a particular QMP port. relict refuses to use an occupied port or control a VM whose
identity does not match its state file.

### 4. Reach the DOS prompt

```powershell
relict boot-to-dos
```

This waits until the guest shows a DOS prompt. If the FreeDOS installer appears on the way, relict declines the
installation and returns to DOS, stopping at the `A:\>` prompt. A user-provided boot image must reach its prompt on its
own, without interactive menus. Switch to the staged drive using an ordinary DOS command:

```powershell
relict run "c:"
```

### 5. Run DOS commands

```powershell
relict run "dir"
relict run "myprog.exe"
relict run "myprog.exe > result.log"
```

`run` types the command and waits for a DOS prompt to return. Redirecting output to drive C: is the most reliable way to
retrieve detailed output. Guest writes become visible in the host staging directory after QEMU stops.

### 6. Inspect the guest

Print the current 80-by-25 text screen:

```powershell
relict text
```

Wait until the screen contains a regular expression:

```powershell
relict wait "C:\\\\>"
```

Take a screenshot:

```powershell
relict screenshot after-test
```

The image is saved as `<home>/screenshots/after-test.png`.
Screenshot names are filename stems, not paths; directory separators are rejected so captures remain under the
relict home.

### 7. Stop QEMU

```powershell
relict stop
```

Stopping QEMU flushes writes from the virtual FAT drive and removes the active `vm.json` record.

QEMU snapshots the host directory when the virtual FAT drive is attached. After changing staged files on the host, stop
and restart QEMU before using them in the guest.

## Command guide

### Managing the VM

```text
relict download
relict start [--display] [--machine PATH] [-- QEMU_ARGS...]
relict boot-to-dos
relict stop
```

The CLI accepts an optional versioned JSON machine document. Put
`machine.json` under the effective home and `relict start` loads it
automatically; `--machine PATH` selects another file instead (relative
paths resolve from the current directory). A missing explicit file is an
error; a missing home file means the ordinary defaults.

`version` is required and must be `1`. The document uses the same field
names as `MachineConfig`: `platform`, `timeout`, `staged_drive`,
`memory`, `qemu`, `machine`, `qemu_args`, and `drives`. Relative drive
sources resolve from the file's directory. For example:

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
      "options": {"snapshot": true}
    }
  }
}
```

Explicit CLI controls override the loaded file for that invocation:
`--platform`, `--qemu`, and raw QEMU arguments after `--`. Omitting
`--platform` leaves the file's platform (or the DOS default) unchanged;
passing `--platform dos` overrides a non-DOS file value.

Additional QEMU arguments can follow `--`:

```powershell
relict start -- -cpu 486 -device virtio-rng-pci
```

### Keyboard and command input

```text
relict type TEXT
relict run COMMAND
relict keys KEY [KEY ...]
```

`type` types text followed by Enter. `run` additionally waits for the prompt to return. `keys` accepts raw QEMU key
names, such as:

```powershell
relict keys down ret
```

### Reading the guest

```text
relict text
relict wait REGEX
relict screenshot [NAME]
```

Use the global `--timeout SECONDS` option to change the timeout for
`boot-to-dos`, `run`, or `wait`.

### QEMU monitor access

```powershell
relict hmp "info block"
```

`hmp` sends a raw QEMU human-monitor command. It is intended for QEMU operations that do not yet have a dedicated
relict command.

Run `relict --help` or `relict COMMAND --help` for the complete current syntax.

## Python usage

The Python interface exposes the selected interaction adapter directly.
`start()` always returns the selected QMP port; construct the adapter with it
so ownership is explicit in programmatic workflows:

```python
import os
import shutil

import relict

stage = os.path.join(relict.drives_dir(), "hdd")
os.makedirs(stage, exist_ok=True)
shutil.copy("MYPROG.EXE", stage)
port = relict.start()
machine = relict.Machine(port)
guest = relict.AgentlessGuestExec(machine)

try:
    guest.wait_ready()
    guest.execute("c:", timeout=15)
    guest.execute("myprog.exe > result.log")
    print("\n".join(relict.screen_text(port=port)))
    relict.screenshot("after-test", port=port)
finally:
    relict.stop(port=port)
```

`Machine.qmp()` exposes the identity-verified QMP session when a caller needs
raw monitor access. The yielded QEMU session provides both `cmd()` for QMP and
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
log = relict.run_guest_program("TESTS.EXE", args="-v")

print(log)
```

For the DOS platform, the executable must have an 8.3 `.EXE` filename. This is a DOS workflow policy, not a
restriction on guest-program workflows for other platforms. relict attaches no meaning to the output — interpreting it (for
example, parsing test-framework results) is the caller's job.

### Embedding relict as a runner

Callers that manage isolated runs (test harnesses, CI drivers) can use the `Runner` surface instead of the module-level
functions. A `Runner` is a configured DOS *test machine* bound to one home directory, which contains its drives,
staging, diagnostics, and VM identity:

```python
machine = relict.Runner(
    "run-42",
    relict.MachineConfig(
        platform="dos",
        timeout=120,
        memory=32,
        machine={"type": "pc", "accel": "tcg"},
        drives={"floppy": "images/msdos-boot.img"},
    ),
)

log = machine.run("TESTS.EXE", "-v")
```

Media can be declared by name under the runner's `drives/` directory or through `MachineConfig.drives`. Configured
keys are `floppy_0` through `floppy_1`, `hdd_0` through `hdd_3`, and `cdrom_0` through `cdrom_3`; `floppy` and `hdd`
are aliases for slot zero. A path value is shorthand for `{"source": path}`. A file source is mounted as an image,
while a floppy or hard-disk directory is mounted as vvfat; a CD-ROM directory is rejected. The object form also
accepts QEMU drive `options`, except for lifecycle-owned properties such as `file`, `if`, `index`, and `media`:

```python
config = relict.MachineConfig(drives={
    "hdd": {
        "source": "images/dos.qcow2",
        "options": {"snapshot": True},
    },
    "hdd_1": "guest-files",
})
```

The same versioned JSON document can be loaded from Python and overridden
field-by-field. Relative drive sources in the file resolve from the file's
directory; Python overrides still resolve from the current directory:

```python
config = relict.MachineConfig.from_file(
    "machines/dos.json",
    timeout=90,
    qemu_args=("-cpu", "pentium"),
)
```

`MachineConfig.from_mapping(...)` accepts the same document shape in memory.
`version` is required in the document and must be `1`; it is not a constructor
field. Explicit overrides win: scalars replace (including `None`),
`qemu_args` and `machine` replace wholesale, and `drives` merge by logical
slot then by entry field / option name. Programmatic construction and
`Runner` do not load `<home>/machine.json` implicitly — that discovery is
CLI-only.

The module-level `start()`, `run_task()`, and `run_guest_program()` functions
accept a `machine_config` containing a `MachineConfig`, versioned mapping, or
machine-document path. Machine settings such as `qemu`, `timeout`, `memory`,
and `drives` belong in that configuration; the functions expose only separate
operational controls such as `display`, `port`, and `home`.

Configured sources are mounted in place and must already exist. They conflict with a filesystem declaration for the
same logical slot rather than overriding it. `run()` keeps present bootable media and, for an empty DOS home, installs
the downloaded FreeDOS default. It then performs the `run_guest_program()` lifecycle under the runner's home.
`machine` maps directly to QEMU's `-machine`: a string selects only the type, while a mapping requires `type` and may
add scalar machine properties. Booleans render as `on`/`off`; configuring both `machine` and `-machine` in
`qemu_args` is an error.
`memory` is a positive integer number of MiB. It defaults by platform: 16 for
DOS, 64 for Win9x, and 256 for WinNT. Configuring both `memory` and `-m` in
`qemu_args` is an error, while a raw `-m` alone suppresses the platform
default.
`staged_drive` declares the guest drive letter where the staged virtual FAT drive appears — the
drive `run()` switches to and stages under (the highest staged directory declared among the hard-disk slots, or
`drives/hdd` created on demand). Its default matches the declared machine: C: with no hard disk before the staged
drive, one letter later per hard-disk slot before it (lower letters are rejected). Every
`MachineConfig` field has a working default, so `relict.Runner()` is a complete FreeDOS machine using the established
default home. Pass `home=` to select another one, and create separate runners with separate homes for concurrent runs.
The same explicit `home=` keyword is available on the
module-level functions (`download`, `start`, `stop`,
`run_guest_program`, and the path helpers) and overrides the process-global home per call.

## Troubleshooting

### QEMU cannot be found

Install QEMU and put `qemu-system-i386` on `PATH`, set
`RELICT_QEMU_HOME` to the QEMU installation directory, or pass
`--qemu PATH`.

### A command cannot find an active VM

CLI commands use `<home>/vm.json`. Ensure every command uses the same
`--home` or `RELICT_HOME` value and that `relict start` completed successfully.

### The VM identity does not match

relict verifies the unique QEMU name before sending any command. An identity error means the recorded port now belongs
to another process or the state file is stale. The unrelated VM is not modified. Review
`<home>/vm.json` and `<home>/qemu-stderr.log`, then start a new relict VM.

### QEMU exits during startup

The error includes the selected port, QEMU exit status, command line, and path to `<home>/qemu-stderr.log`. That log
normally contains QEMU's reason, such as an invalid device option or an unavailable disk image.

### Guest-written files are missing

Stop QEMU before reading files written to the virtual FAT drive. Writes are flushed back to the host during shutdown.

## License

relict is distributed under the BSD 3-Clause License. See [LICENSE](LICENSE).

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow and contribution
licensing terms.
