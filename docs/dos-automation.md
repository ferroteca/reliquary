<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# DOS automation

reliquary provides agentless automation for DOS guests through QEMU. No guest agent, network driver, or serial driver is required.

## How it works

- **Input** is sent as keyboard events through QEMU's control protocol
- **Output** is read directly from VGA text memory, without OCR
- **Files** are exchanged through a QEMU virtual FAT drive
- **Command completion** is detected by watching for the DOS prompt
- **Screenshots** are captured through QEMU

## Declaring drives

Place files under `<reliquary_home>/drives/`:

- Image files named `floppy[_<n>].<ext>` mount as floppy drives (A:, B:)
- Image files named `hdd[_<n>].<ext>` mount as hard disks
- Image files named `cdrom[_<n>].<ext>` mount as CD-ROM drives
- Directories named `floppy[_<n>]` or `hdd[_<n>]` mount as virtual FAT drives
  (cdrom directories are rejected — vvfat emulates no ISO9660)

Any QEMU-supported image format works. The extension declares the format:
- `*.img` and `*.iso` are treated as raw
- Other extensions (`.qcow2`, `.vmdk`) are handed to QEMU to identify

## Boot order

The default boot order is:
1. Slot-0 floppy image (if declared)
2. Slot-0 hard disk image (if declared)
3. First CD-ROM

Override with `-boot` after the known options on `rlq start`.

## Memory

Defaults to 16 MB for DOS. Override with `-m` after the known options
on `rlq start`.

## Example workflow

```powershell
# 1. Create a virtual FAT drive with your programs
New-Item -ItemType Directory "$HOME\Documents\reliquary\drives\hdd"
Copy-Item .\MYPROG.EXE "$HOME\Documents\reliquary\drives\hdd\"

# 2. Start QEMU with your DOS boot image
rlq start-machine --display

# 3. Wait for the DOS prompt
rlq wait "A:\\\\>"

# 4. Switch to the staged drive
rlq exec "c:"

# 5. Run your program
rlq exec "myprog.exe > result.log"

# 6. Stop QEMU
rlq stop-machine
```

After stopping, the `result.log` file is available in the `drives/hdd` directory.

## Python API

```python
import reliquary

port = reliquary.start()
machine = reliquary.Machine(port)
guest = reliquary.AgentlessGuestExec(machine)

try:
    guest.wait_ready()
    guest.execute("c:", timeout=15)
    guest.execute("myprog.exe > result.log")
    print("\n".join(reliquary.screen_text(port=port)))
finally:
    reliquary.stop(port=port)
```

## Running a guest program end-to-end

```python
log = reliquary.run_guest_program("TESTS.EXE", args="-v")
print(log)
```

This stages the program, boots DOS, runs it with output redirected to a log file, stops QEMU, and returns the log text.

For complete API details, see [README.md](../README.md).
