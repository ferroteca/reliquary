<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Machine spec — field reference

> **Status:** this documents the planned machine spec format. The
> machine model is not implemented yet; details may still change
> before first release.

Exhaustive reference for every field in the machine spec format —
shared by the machine's two documents: the **declaration**
(`machines/<name>.json`, yours) and the **state**
(`cache/machines/<name>/reliquary.json`, reliquary's). For the
two-document model, read [the guide](machine-spec.md) first; for
complete examples, see the [cookbook](machine-spec-cookbook.md).

Each field is marked with where it may appear:

- **declaration** — valid in a declaration (the document you
  author at `machines/<name>.json` and instantiate with
  `reliquary create <name>`). Every declaration field is also
  valid in the state, where it always appears fully resolved.
- **state-only** — written by reliquary into the state; rejected
  in a declaration.

All fields are present in the state unless noted otherwise.

There is no version field — see
[Format stability](machine-spec.md#format-stability-none-yet).

---

## `platform`

**declaration · required · string**

The guest platform — the operating system family the machine is
for:

| value   | meaning                    |
|---------|----------------------------|
| `dos`   | DOS (FreeDOS, MS-DOS, ...) |
| `win9x` | Windows 95/98/Me           |
| `winnt` | Windows NT family          |

The platform selects workflow behavior (boot readiness detection,
command syntax, prompt handling) and the
[platform defaults](machine-spec.md#platform-defaults) for omitted
fields. The list is extended deliberately, one platform workflow at
a time.

The platform is **never inferred**. reliquary does not inspect disk
images, watch the guest screen, or probe devices to decide what OS
a machine runs; the declaration says so, or nothing does.

---

## `backend`

**declaration (optional) · string · always present in the state**

The virtualization backend hosting the machine:

| value        | backend            |
|--------------|--------------------|
| `qemu`       | QEMU               |
| `virtualbox` | VirtualBox         |
| `vmware`     | VMware Workstation |
| `hyperv`     | Hyper-V            |

Omitted from the declaration, the backend is assigned
automatically: the first entry in reliquary's backend priority
order that is available on the host and capable of everything the
declaration asks for. Declared explicitly, it pins the choice —
`create` fails if that backend is unavailable or incapable, rather
than falling back.

Either way the resolved value is recorded in the state (an omitted
declaration stays portable), and the assignment holds for the
machine's life. Backend state — identifiers, disk image formats,
VM registration — is not portable between hypervisors, so the
assignment never changes underneath a machine; moving to another
backend is done with `recreate`, which discards the state and
backend machine and resolves the declaration afresh (see
[the guide](machine-spec.md#recreating-a-machine)).

```json
{"backend": "virtualbox"}
```

---

## State-only fields

Three fields exist only in the state; a declaration containing any
of them is rejected.

### `backend-id`

**state-only · string**

The backend's own identifier for this machine:

| backend      | identifier                  |
|--------------|-----------------------------|
| `qemu`       | QEMU instance name          |
| `virtualbox` | VM UUID                     |
| `vmware`     | path to the `.vmx` file     |
| `hyperv`     | Hyper-V VM id               |

This is the anchor for **ownership verification**: reliquary never
sends a control command to a hypervisor object until the object's
identity matches `backend-id`. A stale or foreign machine is
detected and refused rather than manipulated.

### `created`

**state-only · string**

Creation timestamp: UTC, ISO 8601, `Z` suffix.

```json
{"created": "2026-07-19T18:20:11Z"}
```

### `installed`

**state-only · boolean · absent until first set**

Whether an install script has completed against this machine. Set
by reliquary when an installation finishes; absent on a machine
nothing has been installed on.

---

## `memory`

**declaration (optional) · positive integer**

Guest memory in MiB. Defaults by platform (dos 16, win9x 64,
winnt 256); the resolved value appears in the state.

```json
{"memory": 32}
```

---

## `cpus`

**declaration (optional) · positive integer**

Virtual CPU count. Default `1`.

---

## `drives`

**declaration (optional) · object**

The machine's drive inventory. Keys declare a medium and slot; each
value declares the drive's source and options.

### Keys: medium and slot

| medium   | slots         | keys                      |
|----------|---------------|---------------------------|
| `floppy` | 0–1           | `floppy_0`, `floppy_1`    |
| `hdd`    | 0–3           | `hdd_0` ... `hdd_3`       |
| `cdrom`  | 0–3           | `cdrom_0` ... `cdrom_3`   |

In a declaration, the bare medium name is accepted as an alias for
slot 0 (`"hdd"` ≡ `"hdd_0"`); the state always uses the canonical
indexed form. Declaring both an alias and its indexed form in one
document is a slot clash and fails validation, as do slots outside
the table's ranges.

**Slots are logical positions, not controller addresses.** Slot
numbers declare guest drive ordering — DOS assigns `C:`, `D:`, ...
by disk order — and each backend maps slots onto controller ports
in a documented, deterministic order. Which port or channel a disk
sits on is the backend's business; which *kind* of controller it
hangs off is declared per drive with
[`controller`](#controller--optional--string), because guests need
matching drivers.

A backend that cannot provide a declared drive — no floppy support,
fewer slots of a medium than declared — fails with a capability
error naming the backend and the drive. Drives are never silently
dropped.

### Values

A value is either a source string (shorthand):

```json
{"drives": {"cdrom": "media:freedos-14-livecd"}}
```

or an object with these fields:

#### `source` — required · string

One of two forms:

1. **A relative path to the machine's own image file**, inside
   its cached instantiation, conventionally under `drives/`:

   ```json
   {"source": "drives/hdd.qcow2"}
   ```

   Paths resolve from `cache/machines/<name>/` and must stay
   inside it: no absolute paths, no `..` traversal above it.
   These images are materialized by reliquary — created blank
   from [`size`](#size--optional--string) or from a
   [`base`](#base--optional--string) starting-point image; there
   is no dropping of pre-created files into the cache.

2. **A `media:` reference** — `media:<name>` names an item in the
   shared media library `<reliquary_home>/media`:

   ```json
   {"source": "media:freedos-14-livecd"}
   ```

   The name resolves to a [defined media item](media-spec.md),
   fetched and hash-verified on demand; every media item has a
   definition under `media/`, and a name no definition provides
   is an error. Use this for machine-independent, read-only-use
   media: installer ISOs, boot floppies, driver disks. (To boot
   or modify a copy of a media image, make it a drive `base`
   instead.) `media:` is the *only* cross-boundary reference a
   declaration may make.

#### `size` — optional · string

Image-creation size, meaningful only for `hdd` and `floppy` image
sources:

```json
{"source": "drives/hdd.qcow2", "size": "20M"}
```

- If the source file **does not exist**, reliquary creates it at
  this size — at `create`, or at the first `start` — as a
  dynamically-allocated image in the backend's preferred format.
- If the source file **exists**, `size` is validated against it
  and a mismatch is an error. `size` never resizes or overwrites an
  existing image.

Grammar: a positive integer immediately followed by a binary unit
suffix — `K`, `M`, `G`, or `T` (powers of 1024) — case-insensitive.
`"20M"`, `"2G"`, `"720k"`.

`size` and `base` are mutually exclusive: a drive starts blank at
a size, or starts from an image, never both.

#### `base` — optional · string

A **starting-point image** for the drive: a `media:` reference
(the usual case) or a relative path to another image in the
cached instantiation. When the drive's `source` image does not
exist, reliquary materializes it from the base — at `create`, or
at the first `start` — in one of two modes:

```json
{"drives": {"hdd_0": {
  "source": "drives/hdd.qcow2",
  "base": "media:dos622-installed",
  "base-mode": "differencing"
}}}
```

The base itself is never written to. This is how pre-existing
content enters a machine: there is no dropping of files into the
cache — a drive that should start with content declares where
that content comes from, and `recreate` can regenerate it at any
time.

#### `base-mode` — optional · string

How the drive is materialized from `base`:

| mode           | meaning                                       |
|----------------|-----------------------------------------------|
| `copy`         | the base image is copied (default)            |
| `differencing` | the drive is a differencing disk backed by the base; writes land in the difference, the base stays pristine |

`copy` works everywhere (converted to the backend's preferred
format when needed). `differencing` maps to the backend's native
mechanism — qcow2 backing files, VHDX differencing disks, VMDK
linked clones, VDI differencing — and is a backend/format
capability: a backend that cannot difference against the base
fails the capability check rather than silently copying.
Differencing keeps large bases cheap to fan out: many machines
can difference against one installed base image, each paying only
for its own writes.

#### `controller` — optional · string

The kind of storage controller the drive attaches to. This is
guest-visible hardware — the guest needs a driver for the
controller type — so it is spec vocabulary, not a backend detail:

| value    | controller                  |
|----------|-----------------------------|
| `ide`    | IDE / parallel ATA          |
| `sata`   | SATA (AHCI)                 |
| `scsi`   | SCSI                        |
| `nvme`   | NVMe                        |
| `virtio` | virtio block (paravirtual)  |

Valid on `hdd` and `cdrom` drives; floppies attach to the floppy
controller implicitly and reject a `controller` key. The default
for all current platforms is `ide`, resolved into the state at
creation.

```json
{"drives": {"hdd_0": {"source": "drives/nt.vhdx", "controller": "scsi"}}}
```

What the spec deliberately does **not** say:

- **Port/channel placement.** Drives of one controller type attach
  in slot order; the exact port layout is the backend adapter's
  documented, deterministic mapping.
- **Vendor variants.** BusLogic vs. LsiLogic SCSI, a particular
  AHCI implementation — these select guest drivers within a family
  and are backend-specific; when they matter, they belong in
  [`backend-settings`](#backend-settings).

Controller support is a backend capability, checked like any
other. Every backend supports `ide` except Hyper-V Generation 2
machines (SCSI only); paravirtual types need both a backend that
offers them and a guest with the driver — reliquary checks the
backend half and leaves the driver half to you. A declared
controller the machine's backend cannot provide is a capability
error naming both.

One ordering caveat: slot order is authoritative *within* a
controller type. When a machine mixes controller types, the
guest's firmware decides how the controllers themselves enumerate,
and reliquary cannot promise a global disk order across types —
prefer one controller type per machine when drive lettering
matters (as it does under DOS).

#### `enabled` — optional · boolean · default `true`

`false` keeps the entry in the document but detaches the drive
from the machine — useful for installer media you'll re-enable later, or for
switching between configurations without deleting entries:

```json
{"drives": {"cdrom_0": {"source": "media:freedos-14-livecd", "enabled": false}}}
```

### Image formats

The file extension declares the image format; content is never
probed. Keep extensions idiomatic: `.img` and `.iso` are raw,
`.qcow2`, `.vdi`, `.vmdk`, `.vhdx` name their formats.

Each backend attaches its native format set; declaring an image the
machine's backend cannot attach is a capability error. When
reliquary creates an image from `size`, it uses the backend's
preferred dynamically-allocated format and names the file
accordingly:

| backend      | created format |
|--------------|----------------|
| `qemu`       | qcow2 (v3)     |
| `virtualbox` | VDI            |
| `vmware`     | VMDK           |
| `hyperv`     | VHDX           |

Letting reliquary create images (rather than declaring
pre-existing ones) keeps a declaration fully portable: the right
format arrives on whatever backend is assigned.

---

## `boot`

**declaration (optional) · array of drive keys**

The boot order: drive keys (canonical or alias form) tried in
order.

```json
{"boot": ["cdrom_0", "hdd_0"]}
```

Every entry must reference a declared, enabled drive. When omitted,
the default order is: the slot-0 floppy image if declared, else the
slot-0 hard disk, else the first CD-ROM; the resolved order
appears in the state.

Backends differ in how faithfully they honor multi-entry boot
orders; a backend that cannot honor the declared order reports a
capability error rather than silently booting from something else.

---

## `control-planes`

**declaration (optional) · array of strings**

The ordered control-plane policy: which control planes reliquary
may use for guest-facing operations on this machine, in preference
order. reliquary probes readiness in this order and never uses a
control plane the policy doesn't list.

Working name set:

| name                | mechanism                                  |
|---------------------|--------------------------------------------|
| `agentless-display` | keyboard injection + screen readback; no guest cooperation needed |
| `vnc`               | framebuffer and input over VNC             |
| `serial-console`    | text console on an emulated serial port    |
| `guest-agent`       | structured agent protocol (QGA profile)    |

Defaults by platform (DOS: `["agentless-display"]`); the resolved
default appears in the state. Backends that cannot provide a
listed control plane fail capability checking (e.g. `vnc` on
Hyper-V).

```json
{"control-planes": ["guest-agent", "agentless-display"]}
```

---

## `backend-settings`

**declaration (optional) · object**

The escape hatch for backend-specific configuration — explicitly
scoped and explicitly non-portable. One object per backend name;
only the section matching the machine's `backend` applies, other
sections are inert but preserved:

```json
{
  "backend-settings": {
    "qemu": {
      "machine": "pc",
      "args": ["-cpu", "486"]
    }
  }
}
```

Rules:

- This is the **only** place backend-specific configuration may
  appear. A declaration with no `backend-settings` is portable by
  construction.
- Settings may not touch what reliquary owns through first-class
  fields — memory, drives, boot order, CPU count, machine identity.
  Each backend adapter validates its section and rejects overlap.
- The available keys in each backend's section are defined and
  documented by that backend adapter.

---

## Validation summary

Format checks (reject the document):

- unknown top-level keys, unknown drive keys, malformed values;
- slot clashes (alias + indexed form of the same slot) and
  out-of-range slots;
- state-only fields (`backend-id`, `created`, `installed`) in a
  declaration;
- `boot` entries naming undeclared or disabled drives;
- `source` or `base` paths escaping the cached instantiation;
- `size` and `base` on the same drive;
- `backend-settings` sections overlapping reliquary-owned fields.

Capability checks (reject the declaration for *this* backend,
naming backend and capability):

- media the backend cannot provide (unsupported medium, too many
  slots);
- controller types the backend cannot provide (e.g. anything but
  `scsi` on Hyper-V Generation 2);
- `differencing` bases the backend/format pair cannot express;
- image formats the backend cannot attach;
- control planes the backend cannot offer;
- boot orders the backend cannot honor.
