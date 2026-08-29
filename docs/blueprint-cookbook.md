<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Blueprint — cookbook

> **Descriptive.** These are recipes, not rules — the authoritative
> definition of the format is the published schema plus
> [the composed blueprint model](spec/blueprint-model.md).

> **Status:** examples using the implemented subset (`platform`,
> `memory`, `devices` naming media and NICs, `boot`, `description`, `scripts`,
> and the `media` components they name) are parsed, validated,
> resolved, and materialized. The remaining fields may still change
> before first release.

Complete, working blueprints for common machine shapes. Each entry
shows the blueprint (what you write) and, where it helps, the state
document Reliquary resolves it into. A drive names a **media**
component, and the media is what owns the actual content (see the
[media spec](spec/media-spec.md)). For the concepts behind all this —
including the difference between a blueprint and a state document —
see [the guide](blueprint-guide.md); for every field's exact rules,
see the [field reference](blueprint-reference.md).

In each example below, save the blueprint as `<name>.rlqb` under your
asset root and create a machine from it:

```powershell
rlq create-machine --blueprint <name>
```

---

## 1. The simplest machine: boot a floppy image

A DOS machine that boots a floppy image. The `floppy` drive names a
media component, `msdos622-boot`, which gets resolved from the
namespace (either a sibling `.rlqb` file, or a built-in media from
the codex). This blueprint needs only one required field plus one
drive:

```json
{
  "type": "machine",
  "name": "msdos622",
  "platform": "dos",
  "devices": {
    "floppy": "msdos622-boot"
  }
}
```

Everything else takes a default: the best available backend, 16 MiB
of memory (the DOS default), 1 CPU, boot from the floppy, and the
agentless-display control plane.

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
  "devices": {
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

Notice what resolving the blueprint did: `floppy` became `floppy0`;
the bare media name turned into a full drive entry with `medium`,
`slot`, the resolved `media` name, its `materialize` mode, and the
actual cache `path`; the defaults were filled in as explicit values;
and fields that only exist in machine state (not in blueprints)
appeared.

---

## 2. An OS installation machine

A machine to install FreeDOS onto: a blank hard disk, an empty CD
slot that the install script will fill, and a boot order of CD then
hard disk. **The installer medium has to boot first**, and the
install script ejects it once the hard disk is bootable. That's
because firmware reliably skips over an *empty* drive to get to the
next one in the boot order, but nothing more than that — writing a
boot order that expects firmware to skip a drive with something
bootable on it is a bet on that particular firmware's behavior
([see the measured table](blueprint-reference.md#boot)). The extra
memory avoids the FreeDOS LiveCD's low-RAM warning:

```json
[
  {
    "type": "machine",
    "name": "freedos-install",
    "platform": "dos",
    "memory": "32M",
    "devices": {
      "hdd": "blank-20m",
      "cdrom": null
    },
    "boot": [
      "cdrom",
      "hdd"
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

The `hdd` drive names the `blank-20m` media, which has
`materialize: new`, so `rlq` creates a 20 MiB dynamically-allocated
image at a path keyed by the media's name (`disks/blank-20m.qcow2`
on QEMU — the
[naming and file format](blueprint-reference.md#image-naming-and-formats)
are Reliquary's own choice, not something you configure). Actually
installing the OS is the install script's job: it inserts the
LiveCD, drives the installer, and ejects the CD when done. What the
install does lands in the machine's run records — the blueprint and
the machine's state make no claim about what's actually on the
guest's disk. Once the script has ejected the CD, the same boot
order now boots the hard disk, since the optical drive is empty. A
script that needs a different boot order can use the
[`set-boot`](spec/script-spec.md#set-boot) statement while the
machine is stopped.

> **Media note:** the installer medium never appears on a drive in
> this blueprint — leaving the `cdrom` slot empty is the convention.
> The install script inserts it (`insert cdrom0 @freedos-livecd`)
> and ejects it as its last step. `freedos-livecd` names a
> [media component](spec/media-spec.md): a `read-only` `use` media,
> extracted from an `archive` (the LiveCD's download URL and
> hashes), which can live inside this same `.rlqb` file or a sibling
> file in the same source. Every media reference — whether from a
> blueprint or a script — is resolved against the namespace, and
> fetched and verified only when it's actually needed.

---

## 3. A machine from a starting-point image

To start a machine from existing content, declare a
**`difference` media** — a fixed payload that the drive's own image
is built on top of. Here's a test rig that boots a writable copy of
an already-installed DOS image:

```json
[
  {
    "type": "machine",
    "name": "dos-rig",
    "platform": "dos",
    "devices": {
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

When the machine is created (or first started), the
`dos622-installed` media is materialized as a **differencing disk**
on top of its source payload — writes land in the differencing disk,
and the original payload file is never touched. `recreate-machine`
throws the differencing disk away and creates a fresh one, which is
as cheap as disk creation gets: every run of the rig starts from
exactly the same known content. There's no way to just drop pre-made
files into a machine's cache directory directly — a media entry is
what declares where content comes from.

Because each machine's differencing disk is private to it, many
machines can share one large installed payload, each one only using
disk space for its own writes. This is exactly the fan-out pattern
differencing disks are for.

---

## 4. Copying a payload instead

Differencing depends on what the backend and image format support
(qcow2 backing files, VHDX differencing disks, VMDK linked clones,
VDI differencing) — a backend that can't difference against a given
payload fails its capability check rather than silently falling
back to a copy. Setting a media's `materialize` to `copy` instead
makes a full, independent duplicate. This works on every backend,
converting to the backend's preferred format if it needs to:

```json
[
  {
    "type": "machine",
    "name": "nt4-rig",
    "platform": "winnt",
    "devices": {
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

A copied drive has no runtime dependency on its source payload at
all — worth the extra disk space when the machine's image needs to
stand entirely on its own, for example before running
`export-drive`.

---

## 5. Pinning the backend and using the escape hatch

A machine locked to QEMU, emulating a 486 CPU with an explicit
machine type. These are settings no other backend understands, so
they live under `backend-settings.qemu`:

```json
[
  {
    "type": "machine",
    "name": "dos-486",
    "platform": "dos",
    "backend": "qemu",
    "devices": {
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

With `backend` set explicitly, `create-machine` fails if QEMU isn't
available, rather than falling back to another backend — which
couldn't honor these QEMU-specific settings anyway. `backend-settings`
isn't allowed to restate anything a regular field already controls —
putting `-m 32` in `args` is rejected; write `"memory": "32M"`
instead. The only keys allowed here are QEMU's own (`machine` and
`args` — nothing else); the values inside them are yours to choose,
and it's QEMU itself that will refuse a machine type it doesn't
recognize.

**The `backend` line above is optional here.** Since
`backend-settings` only has a `qemu` section, that alone is enough
to narrow the machine to QEMU — so dropping `"backend": "qemu"` from
this recipe wouldn't change where the machine actually runs, only
whether the blueprint says so explicitly. Keep the `backend` line
when pinning the backend is the point you want to make; drop it when
the `backend-settings` section already makes that obvious.

---

## 6. A Windows 98 machine

A win9x machine with an installer CD and a larger disk. The
platform's defaults already do the right thing here (64 MiB of
memory); the explicit `memory` value below shows how to override a
default:

```json
[
  {
    "type": "machine",
    "name": "win98",
    "platform": "win9x",
    "memory": "128M",
    "devices": {
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

`win98se` names a `use` media the machine keeps as-is (a
non-redistributable ISO — a media component with a pinned hash,
whose `location` you have to supply yourself).

> The win9x platform workflow isn't implemented yet. The machine can
> still be created and operated at the machine level, but
> platform-specific workflows (readiness checks, scripted execution)
> raise `NotImplementedError` until that workflow is added.

---

## 7. Multiple CD-ROMs and a second floppy

Slots after the first are just indexed keys, `floppy1`, `cdrom1`,
and so on. Here's a machine with a boot floppy, a driver floppy, and
two mounted ISOs:

```json
{
  "type": "machine",
  "name": "many-slots",
  "platform": "dos",
  "devices": {
    "floppy0": "boot-floppy",
    "floppy1": "driver-floppy",
    "cdrom0": "apps-cd",
    "cdrom1": "games-cd"
  }
}
```

DOS sees the two floppies as `A:` and `B:`; which letters the
CD-ROMs get depends on how the guest's CD driver is configured. Keep
the slot limits in mind: two floppies, four hard disks, four
CD-ROMs — and a given backend might support fewer than that. If it
does, you get a capability error, not drives silently dropped.

---

## 8. Choosing a storage controller

The storage controller type is hardware the guest can see, and the
guest needs a matching driver for it — so it's declared per drive.
Here's a Windows NT machine with its system disk on SCSI and the
installer CD on IDE:

```json
[
  {
    "type": "machine",
    "name": "nt4",
    "platform": "winnt",
    "devices": {
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

Writing a drive as an object instead of a bare string lets you set
both the media name and the `controller`. The CD-ROM here uses the
platform default (`ide`). If you omit `controller` everywhere, as
every earlier example in this cookbook does, every drive gets
`ide`, which is what DOS-era guests expect.

Vendor variants of a controller (BusLogic vs. LsiLogic, for example)
are backend-specific, so they go in `backend-settings` when they
matter. Also note the ordering caveat from the
[reference](blueprint-reference.md#controller--optional--string):
slot order only determines drive order within a single controller
type, so use one controller type per machine when the guest's drive
lettering matters to you.

---

## 9. A parameterized install

A blueprint written to be seeded and customized — see
[customization seams](blueprint-guide.md#customization-seams) in the
guide. The install script declares the `identity.full-name` and
`os.install-key` properties, and the blueprint supplies values for
them.

```json
[
  {
    "type": "machine",
    "name": "win98",
    "platform": "win9x",
    "devices": {
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

`identity.full-name` is given directly in the blueprint — every
machine installs as `testuser` until you edit that value.
`os.install-key` instead points at a property: each user stores
their own key once, with
`rlq set-property products.windows-98.install-key --secret`, and the
script reads it when it runs. The key itself never enters the
blueprint or version control. You can still override either one for
a single run with an explicit value on the command line, e.g.
`rlq run-script install --blueprint win98 --property identity.full-name="Paul Galbraith"`.

Both of these are value seams — you're only changing a value the
blueprint already exposes. Installing the *German* edition instead
would be a
[composition seam](blueprint-guide.md#customization-seams): you'd
point the seeded blueprint's `devices` media reference and `scripts`
map at a different, localized media/script pair, since each install
script only works against the specific installer it was written for.
