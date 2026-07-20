<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Machine blueprint — cookbook

> **Status:** this documents the planned machine blueprint format. The
> machine model is not implemented yet; details may still change
> before first release.

Complete, working blueprints for common machine shapes. Each
recipe shows the blueprint (what you write) and, where
instructive, the state document reliquary resolves it into.
Concepts — including the blueprint/state split — are in
[the guide](machine-blueprint.md); every rule is in the
[field reference](machine-blueprint-reference.md).

Throughout, save the blueprint as `blueprints/<name>.json` and create a
machine from it:

```powershell
rlq create --blueprint <name>
```

---

## 1. The simplest machine: boot a floppy image

A DOS machine that boots a floppy image from the shared media
library. One required field plus one drive:

```json
{
  "platform": "dos",
  "drives": {
    "floppy": "msdos622-boot"
  }
}
```

Everything else is defaulted: backend (best available), memory
(16 MiB for DOS), 1 CPU, boot from the floppy, agentless-display
control plane.

The state after `create` on a host where QEMU was selected:

```json
{
  "id": "5fd11917-147a-4b6b-b7f6-9f4b6d7d1ab2",
  "blueprint": "msdos",
  "created": "2026-07-19T18:20:11Z",
  "phase": "ready",
  "platform": "dos",
  "backend": "qemu",
  "backend-id": "reliquary-msdos-8c41",
  "memory": 16,
  "cpus": 1,
  "drives": {
    "floppy0": {"media": "msdos622-boot"}
  },
  "boot": ["floppy0"],
  "control-planes": ["agentless-display"]
}
```

Note what resolution did: `floppy` became `floppy0`, the bare
media name became a `media` object, defaults became explicit
values, and the state-only fields appeared.

---

## 2. An OS installation machine

A machine to install FreeDOS onto: an installer ISO from the media
library, plus a hard disk that doesn't exist yet — reliquary
creates it from `size`. Boot from CD first so the installer runs;
the extra memory avoids the FreeDOS LiveCD's low-RAM warning:

```json
{
  "platform": "dos",
  "memory": "32M",
  "drives": {
    "hdd": {"size": "20M"},
    "cdrom": "freedos-1.4-livecd"
  },
  "boot": ["cdrom", "hdd"]
}
```

rlq creates the hard disk as a 20 MiB dynamically-allocated
image at the drive's canonical path (`drives/hdd0.qcow2` on QEMU —
the [naming and format](machine-blueprint-reference.md#image-naming-and-formats)
are reliquary's choice, not yours). Installation itself is an
install script's job, and its outcome lands in the machine's run
records — the blueprint and state make no claim about the guest's
contents.

To boot the installed system rather than the installer afterward,
edit the blueprint — disable the CD entry and boot from the hard
disk — and adopt the edit with the explicit
[`apply`](machine-blueprint.md#applying-blueprint-edits) (a change the
machine absorbs without touching its drives):

```json
{
  "drives": {
    "cdrom0": {"media": "freedos-1.4-livecd", "enabled": false}
  },
  "boot": ["hdd0"]
}
```

*(Fragment shown; the rest of the blueprint is unchanged.)*

> **Media note:** `freedos-1.4-livecd` names a
> [media definition](media-spec.md)
> (`media/freedos-1.4-livecd.json` with the LiveCD's download
> URL, archive details, and hashes) — every media reference
> resolves through a definition, fetched and verified on demand.
> This shared definition lets the machine be operated independently;
> a script may instead carry it in a labeled `media` block, which
> installs the definition into the library before resolving the
> machine and leaves it available to later independent operations.

---

## 3. A machine from a starting-point image

Pre-existing content enters a machine as a drive `base` — a
fixed starting-point image the drive's own image is materialized
from. A test rig booting a writable instance of an installed DOS
image:

```json
{
  "platform": "dos",
  "drives": {
    "hdd": {"base": "dos622-installed"}
  }
}
```

At `create` (or first `start`), the drive is materialized as a
**differencing disk** backed by the `dos622-installed` media item
— the default base `type` — so writes land in the difference
and the base is never written to. `recreate` throws the
difference away and starts a fresh one, which is as cheap as disk
creation gets: every run of the rig starts from the same known
content. There is no way to drop pre-created files into a
machine's cache directory; a drive that should start with content
declares where the content comes from.

Because every machine's difference is private, many machines can
share one large installed base, each paying only for its own
writes — the fan-out pattern differencing exists for.

---

## 4. Duplicating a base instead

Differencing is a backend/format capability (qcow2 backing files,
VHDX differencing disks, VMDK linked clones, VDI differencing); a
backend that cannot difference against the base fails the
capability check rather than silently copying. The `base` object
form's `type` field selects a full independent duplicate instead
— it works everywhere, converting to the backend's preferred
format when needed:

```json
{
  "platform": "winnt",
  "drives": {
    "hdd": {
      "base": {"media": "nt4-installed", "type": "duplicate"}
    }
  }
}
```

A duplicated drive has no runtime dependency on its base image —
worth the disk space when the machine's image should stand alone
(say, ahead of an `export`).

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
    "hdd": {"size": "100M"}
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
say `"memory": "32M"` instead.

---

## 6. A Windows 98 machine

A win9x machine with an installer CD and a larger disk. Platform
defaults do the right thing (64 MiB memory), and the explicit
`memory` bump shows overriding one:

```json
{
  "platform": "win9x",
  "memory": "128M",
  "drives": {
    "hdd": {"size": "2G"},
    "cdrom": "win98se"
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
    "floppy0": "boot-floppy",
    "floppy1": "driver-floppy",
    "cdrom0": "apps-cd",
    "cdrom1": "games-cd"
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
    "hdd": {"size": "4G", "controller": "scsi"},
    "cdrom": "nt4-install"
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
[reference](machine-blueprint-reference.md#controller--optional--string):
slot order is authoritative within one controller type, so prefer a
single type per machine when drive lettering matters.
