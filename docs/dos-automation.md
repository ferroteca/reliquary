<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# DOS automation

Reliquary provides agentless automation for DOS guests through QEMU. No guest agent, network driver, or serial driver is required.

## How it works

- **Input** is sent as keyboard events through QEMU's control protocol
- **Output** is read directly from VGA text memory, without OCR
- **Files** are exchanged out-of-band through a directory-source
  media (a host directory served as a virtual FAT drive)
- **Command completion** is detected by watching for the DOS prompt
- **Screenshots** are captured through QEMU

## Declaring the machine

A machine's platform, memory, boot order, and drives are declared in its
blueprint (`<name>.rlqb`) — see the [blueprint guide](blueprint-guide.md),
the [field reference](blueprint-reference.md),
and the [media spec](../docs/spec/media-spec.md). A drive names a
**media** by name; the media owns its content — `materialize: new` for a
blank disk of `size`, `difference`/`copy` over a payload, or `use` to
attach a payload (an ISO, or a host directory served as vvfat).
`platform` must be `dos`; memory defaults to 16 MB; the boot order
defaults to the slot-0 floppy, else the slot-0 hard disk, else the first
cdrom.

To hand the guest its own programs, declare a media whose `source` is a
host directory with `materialize: use`, and name it from a drive: that
directory *is* the drive, readable and writable while the machine is
stopped.

## Example workflow

```powershell
# Create a machine from a blueprint (seed or author one first).
rlq create-machine --blueprint my-dos

# Start it (add --display for a visible QEMU window).
rlq start-machine --blueprint my-dos

# Wait for the DOS prompt, run a program, then stop.
rlq wait "C:\\\\>" --blueprint my-dos
rlq exec "myprog.exe > result.log" --blueprint my-dos
rlq stop-machine --blueprint my-dos
```

If `my-dos` names a directory-source media on a drive, `result.log` is
in that host directory once the machine stops (`rlq get-machine-dir`
prints the machine directory).

## Python API

```python
import reliquary

machine_id = reliquary.create_machine("my-dos")
port = reliquary.start_machine(machine_id)
machine = reliquary.Machine(
    port, home=reliquary.machine_dir_path(machine_id))
guest = reliquary.AgentlessGuestExec(machine)

try:
    guest.wait_ready()
    guest.execute("myprog.exe > result.log", timeout=30)
    print("\n".join(machine.screen_text()))
finally:
    reliquary.stop_machine(machine_id)
```

To run a whole `.rlqs` script instead of driving the guest step by step,
use `run_script` (see the [API reference](api-reference.md)). For
complete usage, see [README.md](../README.md).
