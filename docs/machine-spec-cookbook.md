<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Machine spec — cookbook

> **Status:** this documents the planned machine spec format. The
> machine model is not implemented yet; details may still change
> before first release.

Complete, working declarations for common machine shapes. Each
recipe shows the declaration (what you write) and, where
instructive, the state document reliquary resolves it into.
Concepts — including the declaration/state split — are in
[the guide](machine-spec.md); every rule is in the
[field reference](machine-spec-reference.md).

Throughout, save the declaration as `machines/<name>.json` and
instantiate it:

```powershell
reliquary create <name>
```

---

## 1. The simplest machine: boot a floppy image

A DOS machine that boots a floppy image from the shared media
library. One required field plus one drive:

```json
{
  "platform": "dos",
  "drives": {
    "floppy": {"source": "media:msdos622-boot"}
  }
}
```

Everything else is defaulted: backend (best available), memory
(16 MiB for DOS), 1 CPU, boot from the floppy, agentless-display
control plane.

The state after `create` on a host where QEMU was selected:

```json
{
  "platform": "dos",
  "backend": "qemu",
  "backend-id": "reliquary-msdos-8c41",
  "created": "2026-07-19T18:20:11Z",
  "memory": 16,
  "cpus": 1,
  "drives": {
    "floppy_0": {"source": "media:msdos622-boot"}
  },
  "boot": ["floppy_0"],
  "control-planes": ["agentless-display"]
}
```

Note what resolution did: `floppy` became `floppy_0`, defaults
became explicit values, and the three state-only fields appeared.

---

## 2. An OS installation machine

A machine to install FreeDOS onto: an installer ISO from the media
library, plus a hard disk that doesn't exist yet — reliquary
creates it from `size`. Boot from CD first so the installer runs;
the extra memory avoids the FreeDOS LiveCD's low-RAM warning:

```json
{
  "platform": "dos",
  "memory": 32,
  "drives": {
    "hdd": {"source": "drives/hdd.qcow2", "size": "20M"},
    "cdrom": {"source": "media:freedos-14-livecd"}
  },
  "boot": ["cdrom", "hdd"]
}
```

Because `drives/hdd.qcow2` doesn't exist, reliquary creates a
20 MiB dynamically-allocated image there. After installation
completes (via an install script), the machine's state
additionally carries:

```json
{"installed": true}
```

To boot the installed system rather than the installer afterward,
edit the declaration — disable the CD entry and boot from the hard
disk; the next `start` applies it:

```json
{
  "drives": {
    "cdrom_0": {"source": "media:freedos-14-livecd", "enabled": false}
  },
  "boot": ["hdd_0"]
}
```

*(Fragment shown; the rest of the declaration is unchanged.)*

> **Portability note:** this declaration pins the image name
> `hdd.qcow2`, which only QEMU can attach. To keep an input fully
> portable, let the extension follow the backend by omitting it
> from your plans entirely — declare the drive only in a spec you
> create per backend, or accept the pin. Images reliquary creates
> get the backend's preferred format automatically
> ([formats table](machine-spec-reference.md#image-formats)).

> **Media note:** `media:freedos-14-livecd` names a
> [media definition](media-spec.md)
> (`media/freedos-14-livecd.json` with the LiveCD's download
> URL, archive details, and hashes) — every `media:` reference
> resolves through a definition, fetched and verified on demand.

---

## 3. A machine from a starting-point image

Pre-existing content enters a machine as a drive `base` — a
starting-point image the drive is materialized from. A test rig
booting a writable copy of an installed DOS base:

```json
{
  "platform": "dos",
  "drives": {
    "hdd": {"source": "drives/hdd.img", "base": "media:dos622-installed"}
  }
}
```

At `create` (or first `start`), `drives/hdd.img` is created as a
copy of the `dos622-installed` media item; the base itself is
never written to. `recreate` throws the copy away and materializes
a fresh one — every run of the rig starts from the same known
content. There is no way to drop pre-created files into a
machine's cache directory; a drive that should start with content
declares where the content comes from.

---

## 4. Fan-out with differencing disks

When many machines share one large base, `"base-mode":
"differencing"` materializes each drive as a differencing disk
backed by the base — writes land in the difference, the base
stays pristine, and each machine pays only for its own changes:

```json
{
  "platform": "winnt",
  "drives": {
    "hdd": {
      "source": "drives/hdd.vhdx",
      "base": "media:nt4-installed",
      "base-mode": "differencing"
    }
  }
}
```

Differencing is a backend/format capability (qcow2 backing files,
VHDX differencing disks, VMDK linked clones, VDI differencing); a
backend that cannot difference against the base fails the
capability check rather than silently copying. The default
`base-mode` is `copy`, which works everywhere.

---

## 5. Pinning the backend and using the escape hatch

A machine locked to QEMU, emulating a 486 with an explicit machine
type — settings no other backend understands, so they live under
`backend-settings.qemu`:

```json
{
  "platform": "dos",
  "backend": "qemu",
  "drives": {
    "hdd": {"source": "drives/hdd.qcow2", "size": "100M"}
  },
  "backend-settings": {
    "qemu": {
      "machine": "pc",
      "args": ["-cpu", "486"]
    }
  }
}
```

With `backend` declared, `create` fails if QEMU is unavailable
rather than picking another backend (which couldn't honor the
settings anyway). `backend-settings` may not restate what
first-class fields own — putting `-m 32` in `args` is rejected;
say `"memory": 32` instead.

---

## 6. A Windows 98 machine

A win9x machine with an installer CD and a larger disk. Platform
defaults do the right thing (64 MiB memory), and the explicit
`memory` bump shows overriding one:

```json
{
  "platform": "win9x",
  "memory": 128,
  "drives": {
    "hdd": {"source": "drives/hdd.img", "size": "2G"},
    "cdrom": {"source": "media:win98se"}
  },
  "boot": ["cdrom", "hdd"]
}
```

> The win9x platform workflow is not implemented yet; the machine
> can be created and operated at the machine level, but platform
> workflows (readiness, scripted execution) raise
> `NotImplementedError` until the workflow lands.

---

## 7. Multiple CD-ROMs and a second floppy

Slots beyond 0 are plain indexed keys. A machine with a boot
floppy, a driver floppy, and two mounted ISOs:

```json
{
  "platform": "dos",
  "drives": {
    "floppy_0": {"source": "media:boot-floppy"},
    "floppy_1": {"source": "media:driver-floppy"},
    "cdrom_0": {"source": "media:apps-cd"},
    "cdrom_1": {"source": "media:games-cd"}
  }
}
```

DOS sees the floppies as `A:` and `B:`; CD-ROM letters depend on
the guest's CD driver configuration. Remember slot limits: two
floppies, four hard disks, four CD-ROMs — and a given backend may
support fewer (capability error, not a silent drop).

---

## 8. Choosing a storage controller

Controller type is guest-visible hardware — the guest needs the
matching driver — so it's declared per drive. A Windows NT machine
with its system disk on SCSI and the installer CD on IDE:

```json
{
  "platform": "winnt",
  "drives": {
    "hdd": {"source": "drives/nt.img", "size": "4G", "controller": "scsi"},
    "cdrom": {"source": "media:nt4-install"}
  },
  "boot": ["cdrom", "hdd"]
}
```

The CD-ROM takes the platform default (`ide`). Omit `controller`
everywhere — as every earlier recipe does — and you get `ide`
across the board, which is what DOS-era guests want.

Vendor variants (BusLogic vs. LsiLogic, etc.) are backend-specific
and go in `backend-settings` when they matter. And note the
ordering caveat from the
[reference](machine-spec-reference.md#controller--optional--string):
slot order is authoritative within one controller type, so prefer a
single type per machine when drive lettering matters.
