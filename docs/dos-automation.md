<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# DOS automation

Reliquary provides agentless automation for DOS guests through QEMU. No guest agent, network driver, or serial driver is required.

## How it works

- **Input** is sent as keyboard events through QEMU's control protocol
- **Output** is read directly from VGA text memory, without OCR
- **Files** are yours to move. Reliquary supplies the drive — a
  directory-source media serves a host directory to the guest as a
  virtual FAT drive, and `insert-media --file` swaps a whole image
  live — and never reaches inside a volume itself
- **Command completion** is detected by watching for the DOS prompt
  to come back — the standard `X:\path>` shape, or exactly the
  prompt the guest was at, so a customized prompt needs nothing
  declared — and confirmed only once the screen under it has stopped
  changing —
  a prompt can arrive mid-scroll, and reading one that is still being
  drawn returns output cut at a boundary that never existed
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

## Reading the guest's own font

A screen is read through the fonts the *host's* hypervisor installs by
default, and a guest that loads a face of its own — a prepared
codepage, a localized shell — is read through fonts that do not
include it. The guest is the only party that knows what it loaded, and
on DOS it can be asked: `rlq seed-script freedos-dump-font` (U11)
brings in a codex script that boots to a prompt, reads the live VGA
character table, and writes it out as 4096 raw bytes.

The bytes cross on a drive you supply — the codex blueprint declares
none, because a host directory is your own path (see above). Add a
`floppy0` drive whose media is a host directory before running the
script:

```json
"drives": {
  "floppy0": {
    "type": "media",
    "location": "./font-exchange",
    "materialize": "use"
  }
}
```

`rlq apply-blueprint --blueprint <name>` hands a stopped machine a
drive its blueprint gained, then `rlq run-script freedos-dump-font
--blueprint <name>` boots the guest, writes `FONT.BIN` into that
directory, and powers the machine off. Floppy lettering is fixed by
DOS independently of whatever else the machine has attached, so a
lone `floppy0` is always `A:` regardless of how many hard disks or
CD-ROMs are also declared. A blueprint that never gained the slot
fails the run the same way a real, empty floppy drive would — there
is no cheaper check than the guest's own answer, since a
directory-source drive carries no image for a live insert or eject
to preflight against.

The dumped bytes are the cell bitmaps alone; declaring what they
*mean* — the cell geometry and the codepage the indices decode
through — is a `<name>.rlqf` authored font
([asset resolution](spec/asset-resolution.md)), read through with a
script's `font @name` statement.

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

A guest whose `AUTOEXEC.BAT` customizes the prompt says so at the
call — `guest.wait_ready(prompt="[C:\\]>")`, the exact text the guest
draws — because readiness has no earlier screen to read it off;
`execute` needs nothing, reading the prompt off the screen it types
into. For any other boot-time evidence, `machine.wait_text(pattern)`
is the general authored wait over the whole screen.

To run a whole `.rlqs` script instead of driving the guest step by step,
use `run_script` (see the [API reference](api-reference.md)). For
complete usage, see [README.md](../README.md).
