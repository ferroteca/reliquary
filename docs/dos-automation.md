<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# DOS automation

Reliquary automates DOS guests through QEMU without needing anything
installed inside the guest — no guest agent, no network driver, no
serial driver.

## How it works

- **Input** is sent as keyboard events through QEMU's control protocol
- **Output** is read directly from VGA text memory, without OCR
- **Files** are yours to move yourself. Reliquary just supplies the
  drive — a directory-source media serves a host directory to the
  guest as a virtual FAT drive, and `insert-media --file` swaps a
  whole image live — but it never reaches inside a volume itself
- **Command completion** is detected by watching for the DOS prompt
  to come back — either the standard `X:\path>` shape, or exactly
  the prompt the guest was already showing, so a customized prompt
  doesn't need to be declared anywhere. It's only confirmed once the
  screen underneath the prompt has stopped changing, because a
  prompt can appear mid-scroll — reading one that's still being
  drawn would cut the output off at a boundary that was never really
  there
- **Screenshots** are captured through QEMU

## Declaring the machine

A machine's platform, memory, boot order, and drives are all
declared in its blueprint (`<name>.rlqb`) — see the
[blueprint guide](blueprint-guide.md), the
[field reference](blueprint-reference.md), and the
[media spec](../docs/spec/media-spec.md). A drive names a **media**
by name, and the media controls its actual content —
`materialize: new` for a blank disk of a given `size`, `difference`
or `copy` for a disk built on top of a payload, or `use` to attach a
payload as-is (an ISO, or a host directory served as a virtual FAT
drive). `platform` has to be `dos`; memory defaults to 16 MB; the
boot order defaults to the slot-0 floppy, or failing that the
slot-0 hard disk, or failing that the first CD-ROM.

To hand the guest its own programs, declare a media whose `source`
is a host directory, with `materialize: use`, and name it from a
drive — that host directory *is* the drive, readable and writable
while the machine is stopped.

## Reading the guest's own font

The screen is normally read using the fonts the *host's* hypervisor
installs by default. If a guest loads its own font — a prepared
codepage, a localized shell — reading its screen with the host's
default fonts won't recognize the characters it's actually using.
The guest is the only party that knows what it loaded, and on DOS,
you can ask it: `rlq seed-script freedos-dump-font` (U11) brings in
a codex script that boots to a prompt, reads the live VGA character
table, and writes it out as 4096 raw bytes.

Those bytes cross over on a drive you supply yourself — the codex
blueprint doesn't declare one, because a host directory needs your
own path (see above). Add a `floppy0` drive whose media is a host
directory before running the script:

```json
"devices": {
  "floppy0": {
    "type": "media",
    "location": "./font-exchange",
    "materialize": "use"
  }
}
```

Run `rlq apply-blueprint --blueprint <name>` to give an existing,
stopped machine the new drive its blueprint just gained, then run
`rlq run-script freedos-dump-font --blueprint <name>`, which boots
the guest, writes `FONT.BIN` into that directory, and powers the
machine off. DOS assigns floppy letters independently of whatever
else is attached, so a lone `floppy0` is always `A:`, no matter how
many hard disks or CD-ROMs the machine also has. If a blueprint
never actually gained the slot, the run fails the same way it would
against a real, empty floppy drive — there's no cheaper check
available than the guest's own answer, since a directory-source
drive has no image file for a live insert or eject to check against
ahead of time.

The dumped bytes are just the raw cell bitmaps — declaring what
they actually *mean* (the cell geometry, and the codepage the
indices decode through) is a separate `<name>.rlqf` authored font
file ([asset resolution](spec/asset-resolution.md)), which a script
reads through its `font @name` statement.

## Example workflow

```powershell
# Create a machine from a blueprint (seed or author one first).
rlq create-machine --blueprint my-dos

# Start it (add --display for a visible QEMU window).
rlq start-machine --blueprint my-dos

# Wait for the DOS prompt, run a program, then stop.
rlq wait-ready --blueprint my-dos
rlq exec "myprog.exe > result.log" --blueprint my-dos
rlq stop-machine --blueprint my-dos
```

If `my-dos` names a directory-source media on one of its drives,
`result.log` ends up in that host directory once the machine stops
(`rlq get-machine-dir` prints the machine's directory).

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

For a guest whose `AUTOEXEC.BAT` customizes the prompt, you say so
directly in the call — `guest.wait_ready(prompt="[C:\\]>")`, the
exact text the guest actually draws — because there's no earlier
screen for readiness to read a customized prompt off of. `execute`
doesn't need this declared, since it reads the prompt straight off
the screen it just typed a command into. For any other boot-time
signal, `machine.wait_text(pattern)` is the general-purpose wait
over the whole screen.

To run a whole `.rlqs` script instead of driving the guest step by step,
use `run_script` (see the [API reference](api-reference.md)). For
complete usage, see [README.md](../README.md).
