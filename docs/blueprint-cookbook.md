<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Blueprint — cookbook

> **Descriptive.** Recipes, not rules — the format's norm is the
> published schema plus
> [the composed blueprint model](spec/blueprint-model.md).

> **Status:** examples using the implemented subset (`platform`,
> `memory`, `drives` naming media, `boot`, `description`, `scripts`,
> and the `media` components they name) are parsed, validated,
> resolved, and materialized. The remaining fields may still change
> before first release.

Complete, working blueprints for common machine shapes. Each
entry shows the blueprint (what you write) and, where instructive,
the state document Reliquary resolves it into. A drive names a
**media** component; the media owns its content (see the
[media spec](spec/media-spec.md)). Concepts — including the blueprint/state
split — are in [the guide](blueprint-guide.md); every rule is in the
[field reference](blueprint-reference.md).

Throughout, save the blueprint as `<name>.rlqb` under your asset
root and create a
machine from it:

```powershell
rlq create-machine --blueprint <name>
```

---

## 1. The simplest machine: boot a floppy image

A DOS machine that boots a floppy image. The `floppy` drive names a
media component, `msdos622-boot`, resolved from the namespace (a
sibling `.rlqb`, or a codex media). One required field plus one
drive:

```json
{
  "type": "machine",
  "name": "msdos622",
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
  "id": "msdos-0",
  "blueprint": "msdos",
  "created": "2026-07-19T18:20:11Z",
  "phase": "ready",
  "platform": "dos",
  "backend": "qemu",
  "backend-id": "reliquary-msdos-0",
  "memory": 16,
  "cpus": 1,
  "drives": {
    "floppy0": {
      "medium": "floppy",
      "slot": 0,
      "media": "msdos622-boot",
      "materialize": "use",
      "path": "<cache>/media/msdos622-boot.img"
    }
  },
  "boot": ["floppy0"],
  "control-planes": ["agentless-display"]
}
```

Note what resolution did: `floppy` became `floppy0`, the bare
media name became a full drive entry (medium, slot, the resolved
`media` and its `materialize` mode, and the realized cache `path`),
defaults became explicit values, and the state-only fields appeared.

---

## 2. An OS installation machine

A machine to install FreeDOS onto: a blank hard disk, an empty CD
slot the install script will fill, and boot order hard-disk then
CD. A blank disk fails to boot, so firmware falls through to the
attached installer — no boot-order change is needed before or after
install. The extra memory avoids the FreeDOS LiveCD's low-RAM
warning:

```json
[
  {
    "type": "machine",
    "name": "freedos-install",
    "platform": "dos",
    "memory": "32M",
    "drives": {
      "hdd": "blank-20m",
      "cdrom": null
    },
    "boot": [
      "hdd",
      "cdrom"
    ]
  },
  {
    "type": "media",
    "name": "blank-20m",
    "materialize": "new",
    "size": "20M"
  }
]
```

The `hdd` drive names the `blank-20m` media — `materialize: new`,
so rlq creates a 20 MiB dynamically-allocated image at the
media-keyed path (`media/blank-20m.qcow2` on QEMU — the
[naming and format](blueprint-reference.md#image-naming-and-formats)
are Reliquary's choice, not yours). Installation itself is an
install script's job (`insert` the LiveCD, drive the installer,
`eject`); its outcome lands in the machine's run records — the
blueprint and state make no claim about the guest's contents. After
install, the same boot order boots the hard disk. Scripts that need
a different order can use the
[`set-boot`](spec/script-spec.md#set-boot) verb while the machine is
stopped.

> **Media note:** the installer medium never appears on a drive
> here — the empty `cdrom` slot is the convention. The install
> script inserts it (`insert cdrom0 @freedos-livecd`) and
> ejects it as its last act. `freedos-livecd` names a
> [media component](spec/media-spec.md) — a `read-only` `use` media,
> extracted from an `archive` (the LiveCD's download URL and
> hashes), carried inside this same `.rlqb` or a sibling in the
> source. Every media reference — a blueprint's or a script's —
> resolves against the namespace, fetched and verified on demand.

---

## 3. A machine from a starting-point image

Pre-existing content enters a machine as a **`difference` media** —
a fixed payload the drive's own image is materialized over. A test
rig booting a writable instance of an installed DOS image:

```json
[
  {
    "type": "machine",
    "name": "dos-rig",
    "platform": "dos",
    "drives": {
      "hdd": "dos622-installed"
    }
  },
  {
    "type": "media",
    "name": "dos622-installed",
    "materialize": "difference",
    "location": {
      "local": "D:/images/dos622.qcow2"
    }
  }
]
```

At `create` (or first `start`), the `dos622-installed` media
materializes as a **differencing disk** over its source payload —
so writes land in the difference and the payload is never written
to. `recreate` throws the difference away and starts a fresh one,
which is as cheap as disk creation gets: every run of the rig
starts from the same known content. There is no way to drop
pre-created files into a machine's cache directory; a media
declares where its content comes from.

Because every machine's difference is private, many machines can
share one large installed payload, each paying only for its own
writes — the fan-out pattern differencing exists for.

---

## 4. Copying a payload instead

Differencing is a backend/format capability (qcow2 backing files,
VHDX differencing disks, VMDK linked clones, VDI differencing); a
backend that cannot difference against the payload fails the
capability check rather than silently copying. A media's
`materialize: copy` selects a full independent duplicate instead
— it works everywhere, converting to the backend's preferred
format when needed:

```json
[
  {
    "type": "machine",
    "name": "nt4-rig",
    "platform": "winnt",
    "drives": {
      "hdd": "nt4-installed"
    }
  },
  {
    "type": "media",
    "name": "nt4-installed",
    "materialize": "copy",
    "location": {
      "local": "D:/images/nt4.vhdx"
    }
  }
]
```

A copied drive has no runtime dependency on its source payload —
worth the disk space when the machine's image should stand alone
(say, ahead of an `export-drive`).

---

## 5. Pinning the backend and using the escape hatch

A machine locked to QEMU, emulating a 486 with an explicit machine
type — settings no other backend understands, so they live under
`backend-settings.qemu`:

```json
[
  {
    "type": "machine",
    "name": "dos-486",
    "platform": "dos",
    "backend": "qemu",
    "drives": {
      "hdd": "blank-100m"
    },
    "backend-settings": {
      "qemu": {
        "machine": "pc",
        "args": [
          "-cpu",
          "486"
        ]
      }
    }
  },
  {
    "type": "media",
    "name": "blank-100m",
    "materialize": "new",
    "size": "100M"
  }
]
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
[
  {
    "type": "machine",
    "name": "win98",
    "platform": "win9x",
    "memory": "128M",
    "drives": {
      "hdd": "blank-2g",
      "cdrom": "win98se"
    },
    "boot": [
      "cdrom",
      "hdd"
    ]
  },
  {
    "type": "media",
    "name": "blank-2g",
    "materialize": "new",
    "size": "2G"
  }
]
```

`win98se` names a `use` media the machine carries at rest (a
non-redistributable ISO — a component with a pinned hash and a
`location` the user supplies).

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
  "type": "machine",
  "name": "many-slots",
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
[
  {
    "type": "machine",
    "name": "nt4",
    "platform": "winnt",
    "drives": {
      "hdd": {
        "media": "nt4-blank-4g",
        "controller": "scsi"
      },
      "cdrom": "nt4-install"
    },
    "boot": [
      "cdrom",
      "hdd"
    ]
  },
  {
    "type": "media",
    "name": "nt4-blank-4g",
    "materialize": "new",
    "size": "4G"
  }
]
```

The object drive form carries the media name plus the
`controller`. The CD-ROM takes the platform default (`ide`). Omit
`controller`
everywhere — as every earlier example does — and you get `ide`
across the board, which is what DOS-era guests want.

Vendor variants (BusLogic vs. LsiLogic, etc.) are backend-specific
and go in `backend-settings` when they matter. And note the
ordering caveat from the
[reference](blueprint-reference.md#controller--optional--string):
slot order is authoritative within one controller type, so prefer a
single type per machine when drive lettering matters.

---

## 9. A parameterized install

A blueprint written to be seeded and customized (its
[customization seams](blueprint-guide.md#customization-seams)):
the install script declares the `identity.full-name` and
`os.install-key` properties, and the blueprint binds them.

```json
[
  {
    "type": "machine",
    "name": "win98",
    "platform": "win9x",
    "drives": {
      "hdd": "blank-2g",
      "cdrom": null
    },
    "boot": [
      "hdd",
      "cdrom"
    ],
    "scripts": {
      "install": "win98-install",
      "verify": "win98-verify"
    },
    "parameters": {
      "identity.full-name": "testuser",
      "os.install-key": {
        "property": "products.windows-98.install-key"
      }
    }
  },
  {
    "type": "media",
    "name": "blank-2g",
    "materialize": "new",
    "size": "2G"
  }
]
```

`identity.full-name` is specified directly — every machine installs
as
`testuser` until you edit the value. `os.install-key` is
redirected: each user stores their own key once
(`rlq set-property products.windows-98.install-key --secret`) and
the script retrieves it at use; the key never enters the
blueprint or version control. An explicit value still overrides
either binding for one invocation
(`rlq run-script install --blueprint win98 --property identity.full-name="Paul Galbraith"`).

Both are value seams. Installing the *German* edition instead is
a [composition seam](blueprint-guide.md#customization-seams):
the seeded blueprint's `drives` media reference and `scripts` map
are pointed at a localized media/script pair, and each script
stands alone against the installer it was written for.
