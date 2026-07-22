<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Machine blueprint — field reference

> **Status:** the milestone-1 subset (`platform`, `memory`, `drives` with
> `size`/`media` and empty removable slots (`null`), `boot`,
> `description`, and `scripts`) is implemented: parsing, validation,
> media-name resolution, machine materialization, and persistent
> script-driven `insert`/`eject`. The remaining fields, and JSONC
> acceptance, are not implemented yet; details may still change
> before first release.

Exhaustive reference for every field in the machine blueprint format —
shared by the **blueprint** (`<name>.rlqb`, yours) and each
machine's **state** (`cache/machines/<id>/reliquary-machine.json`,
reliquary's). For the blueprint/state model, read
[the guide](machine-blueprint.md) first; for complete examples, see
the [cookbook](machine-blueprint-cookbook.md).

Each field is marked with where it may appear:

- **blueprint** — valid in a blueprint (the `.rlqb` document you
  author and realize as a machine with
  `rlq create-machine --blueprint <name>`). Every blueprint field is also
  valid in the state, where it always appears fully resolved.
- **state-only** — written by reliquary into the state; rejected
  in a blueprint.

All fields are present in the state unless noted otherwise.

There is no version field — see
[Format stability](machine-blueprint.md#format-stability-none-yet).
Blueprints accept comments and trailing commas — the JSONC
dialect — per the same section; the state is strict canonical
JSON, always.

The machine-checkable companion is
[machine-blueprint.schema.json](machine-blueprint.schema.json) —
the structural subset of the format checks only; this reference
is normative.

---

## `platform`

**blueprint · required · string**

The guest platform — the operating system family the machine is
for:

| value   | meaning                    |
|---------|----------------------------|
| `dos`   | DOS (FreeDOS, MS-DOS, ...) |
| `openbsd` | OpenBSD                  |
| `win9x` | Windows 95/98/Me           |
| `winnt` | Windows NT family          |

The platform selects workflow behavior (boot readiness detection,
command syntax, prompt handling) and the
[platform defaults](machine-blueprint.md#platform-defaults) for omitted
fields. The list is extended deliberately, one platform workflow at
a time.

The platform is **never inferred**. reliquary does not inspect disk
images, watch the guest screen, or probe devices to decide what OS
a machine runs; the blueprint says so, or nothing does.

---

## `backend`

**blueprint (optional) · string · always present in the state**

The virtualization backend hosting the machine:

| value        | backend            |
|--------------|--------------------|
| `qemu`       | QEMU               |
| `virtualbox` | VirtualBox         |
| `vmware`     | VMware Workstation |
| `hyperv`     | Hyper-V            |

Omitted from the blueprint, the backend is assigned when the
machine is materialized (`create` or `recreate`): reliquary walks
its backend priority order one by one, probing each for
availability on the host, and assigns the first entry that is
available and capable of everything the blueprint asks for.
Capability is judged against the whole blueprint — referenced
media and image types the backend must be able to attach,
required [`control-planes`](#control-planes), and
[`backend-settings`](#backend-settings) — so a blueprint can
dictate its backend without declaring one: a `backend-settings`
section for exactly one backend, or a media type only one backend
can consume, narrows the walk to that backend. Declared
explicitly, `backend` pins the choice — only that backend is
probed, and `create` fails if it is unavailable or incapable,
rather than falling back.

Either way the resolved value is recorded in the state (an omitted
blueprint stays portable), and the assignment holds for the
machine's life. Backend state — identifiers, disk image formats,
VM registration — is not portable between hypervisors, so the
assignment never changes underneath a machine; moving to another
backend is done with `recreate`, which discards the state and
backend machine and resolves the blueprint afresh (see
[the guide](machine-blueprint.md#destroying-and-recreating-a-machine)).

```json
{"backend": "virtualbox"}
```

---

## `description`

**blueprint (optional) · string**

Human-readable discovery prose. It does not affect machine
behavior; it feeds `search`, which matches terms against
filename, `description`, and platform (U5). The blueprint's one
name is its file stem — there is no display-name field (a
`name` field was weighed and dropped, owner 2026-07-21: a second
name drifts from the stem and adds nothing over the
description). Codex blueprints carry the description through the
codex's index; user blueprints are indexed by reading the field
from the file (see [the codex](codex.md)).

```json
{
  "description": "Installs FreeDOS 1.4 onto a blank hard disk. Selects the Plain DOS system package set."
}
```

---

## `scripts`

**blueprint (optional) · object**

A map of short labels to script file names (the stem of
`scripts/<name>.rlqs`). Labels are the verbs used with the
`run-script` command:
`rlq run-script install --blueprint freedos-1.4-plain`
looks up `scripts.install` and runs the script it names. Labels
take priority over bare script filenames.

```json
{
  "scripts": {
    "install": "freedos-1.4-plain-install",
    "verify": "freedos-1.4-plain-verify"
  }
}
```

Labels are conventionally short verbs — `install`, `verify`,
`test`, `configure`.

---

## `parameters`

**blueprint (optional) · object · not carried in the state**

Values the blueprint supplies to [script-declared
properties](script-spec.md#properties) — the
blueprint's half of the customization seams its author designs in
(U5; see [the guide](machine-blueprint.md#customization-seams)).
Keys are property keys its scripts declare. Each value is one of
the two bindings the
use case names:

- a **direct value** — a JSON string: the parameter is specified
  in the blueprint itself. An automated-testing blueprint fixes
  its user name as `"testuser"`; a seeded copy is customized by
  editing the value.
- a **redirect** — `{"property": "<key>"}`: the declared key is
  answered by resolving *another* key through the remaining
  [property sources](script-spec.md#the-property-sources) — so a
  generic script's key can be wired to a specific personal one,
  and automation can satisfy it from the environment. This is the
  form for values that must never enter the blueprint — a license
  key is the canonical example.

```json
{
  "parameters": {
    "identity.full-name": "testuser",
    "os.install-key": {"property": "products.windows-98.install-key"},
    "supplemental-disk": "freedos-1.4-bonus"
  }
}
```

When a script runs against a machine of this blueprint (or
creates one), each declared property binds from the first source
that answers: an explicit `--property` value, then the
blueprint parameter, then the environment, the properties file,
and — interactively — the ask (normative in the [script
spec](script-spec.md#the-property-sources)). The
blueprint therefore
overrides the person's standing values — a value the blueprint
fixes
stays fixed for every machine of it — while an explicit CLI value
overrides even the blueprint for one invocation. A redirect
*replaces* resolution of the declared key entirely: the target
key resolves through the
non-blueprint sources — the interactive ask last — or fails
noninteractively; parameters never chain through other
parameters, and resolution never falls back to the key the
author redirected away from.

Rules, checked at blueprint validation and script preflight:

- A value is a string or a `{"property": "<key>"}` object —
  nothing else. Keys and redirect targets must be valid property
  names.
- A `secret`-typed property never takes a direct value:
  blueprints are
  written to be shared and versioned (U4), and a secret in one is
  plaintext in source control. A secret parameter uses the
  redirect form, its target obeys the secret rules of whichever
  source answers it (a secret property at the file, the warned
  plaintext class in the environment, never argv), and ordinary
  (`text`, `media`) declarations require
  ordinary values — kind mismatches fail rather than
  downgrading protected data.
- A parameter naming no property of the *running* script is
  unused
  for that run: one blueprint's parameters serve every script in
  its [`scripts`](#scripts) map, and each script binds only the
  properties it declares. A parameter matching no declared
  property of *any*
  script in the map draws a validation warning — it is probably a
  typo.

Like the `scripts` map, `parameters` is read from the blueprint
at script invocation: it configures script binding, not machine
shape. It never appears in the machine's state, takes no part in
[`apply`](machine-blueprint.md#applying-blueprint-edits) or the
baseline digest, and an edit is live on the next script run — the
U5 loop is edit the blueprint, run the script.

---

## State-only fields

Four fields exist only in the state; a blueprint containing any of
them is rejected. (The state document also carries the machine's
bookkeeping — its blueprint's name, creation time, and lifecycle
phase — which is outside the blueprint field set entirely; script
outcomes live in run records. See
[the instance model](instance-model.md).)

### `id`

**state-only · string**

The machine's own id (`<blueprint>-<n>`), repeated inside the state
as a safety check: it must match the machine directory the state
sits in. A mismatch — a hand-copied or misplaced machine directory —
fails closed before any operation touches the backend.

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

### `blueprint-source`

**state-only · string**

The absolute path of the blueprint file this machine resolved
from at `create` (re-recorded by `apply`). Selection by
`--blueprint <name>` matches only machines whose recorded source
equals the invocation's own resolution of that name — through its
asset root (planning/ROADMAP.md, "Authored-asset resolution") — so
same-named blueprints in different projects never select each
other's machines, and `apply` can never adopt another project's
blueprint: a selection or reconciliation whose resolution
disagrees with the recorded source fails closed naming both
paths.

### `blueprint-digest`

**state-only · string**

The digest of the resolved blueprint snapshot this machine was created
from (or last [`apply`](machine-blueprint.md#applying-blueprint-edits)-d
to). This is the machine's baseline. Operation may diverge the
state from it — script `insert`/`eject` persists in the state —
and `apply` is what reconciles the machine back to (or forward to
an edited) blueprint; editing the blueprint file changes nothing
until `apply` records a new digest.

---

## `memory`

**blueprint (optional) · positive integer or size string**

Guest memory. A size string uses the same grammar as drive
[`size`](#size--optional--string) — a positive integer with a
binary unit suffix — and a bare integer means MiB, so
`"memory": "32M"` and `"memory": 32` are the same declaration.
The size must resolve to a whole number of MiB because the state
always carries the canonical integer-MiB form. Defaults by platform
(dos 16 MiB, openbsd 512 MiB, win9x 64 MiB, winnt 256 MiB).

```json
{"memory": "32M"}
```

---

## `cpus`

**blueprint (optional) · positive integer**

Virtual CPU count. Default `1`.

---

## `drives`

**blueprint (optional) · object**

The machine's drive inventory. Keys declare a medium and slot; each
value declares where the drive's content comes from, and options.

### Keys: medium and slot

| medium   | slots         | keys                      |
|----------|---------------|---------------------------|
| `floppy` | 0–1           | `floppy0`, `floppy1`      |
| `hdd`    | 0–3           | `hdd0` ... `hdd3`         |
| `cdrom`  | 0–3           | `cdrom0` ... `cdrom3`     |

In a blueprint, the bare medium name is accepted as an alias for
slot 0 (`"hdd"` ≡ `"hdd0"`); the state always uses the canonical
indexed form. The canonical key is also the name of the drive's
image file in the cached materialization, when it has one (see
[image naming](#image-naming-and-formats) below). Declaring both an alias and its indexed form in one
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

A value is either a media-name string (shorthand):

```json
{"drives": {"cdrom": "freedos-1.4-livecd"}}
```

or an object. **Exactly one** of four fields — `media`, `size`,
`base`, or `hostdir` — declares where the drive's content comes
from; a
drive object with none of them, or more than one, fails
validation.

A removable drive (`cdrom`, `floppy`) may instead be declared
**empty** with the value `null`:

```json
{"drives": {"cdrom0": null}}
```

The slot exists as guest-visible hardware with no medium inserted.
This is the normal shape for a drive that scripts occupy
temporarily — an install script inserts the installer medium into
the empty slot and ejects it as its final step (U1; see
[the script spec](script-spec.md#insert-and-eject)). Declaring
the slot is required: `insert` only places media into hardware
the blueprint declares, and never creates the drive itself — the
blueprint alone determines machine topology, so capability
preflight (and a script's `insert` targets) can be checked before
anything runs. Fixed drives
(`hdd`) cannot be empty.

There are no paths to reliquary-managed images anywhere in the
blueprint ([`hostdir`](#hostdir--optional--string) deliberately
names user-owned content — the media `local-path` class). A
drive that has
its own image file (declared with `size` or `base`) gets it
materialized by reliquary inside the cached materialization, named
canonically after the drive key —
`cache/machines/<id>/drives/hdd0.qcow2` for `hdd0` on QEMU —
with the extension of the format reliquary chose (see
[image naming](#image-naming-and-formats)). You never name,
place, or reference these files; the drive key is the only handle.

#### `media` — optional · string

The name of a defined media item:

```json
{"media": "freedos-1.4-livecd"}
```

The name resolves to a [defined media item](media-spec.md), fetched
and hash-verified on demand. Definitions live in the shared
`<reliquary_home>/media` library; scripts may install embedded
definitions there before resolving their target machine. A name no
definition provides is an error. The drive attaches the media payload
itself — use this for
machine-independent, read-only-use media the machine should carry
*at rest*: a driver disk, a reference CD. Media a workflow needs
only temporarily — above all installer ISOs — conventionally stay
out of the blueprint: declare the slot empty and let the install
script insert and eject the medium, so the machine's default
shape is the installed system, not the installer. (To boot or
modify a copy of a media image,
make it a drive [`base`](#base--optional--string-or-object) instead.)
A media name is the *only* cross-boundary reference the machine
shape may make: the drive inventory reaches the media catalog and
nothing else (U4). (The [`scripts`](#scripts) map and
[`parameters`](#parameters) property references are invocation
wiring — they configure script binding, never machine shape.)

#### `size` — optional · string

Start the drive as a blank image of this size — meaningful for
`hdd` and `floppy` drives:

```json
{"size": "20M"}
```

rlq creates the image — at `create`, or at the first
`start` — dynamically allocated, in the backend's preferred
format, at the drive's canonical path. Once the image exists,
`size` is validated against it and a mismatch is an error;
`size` never resizes or overwrites an existing image
(`recreate` is how a drive starts over).

Grammar: a positive integer immediately followed by a binary unit
suffix — `K`, `M`, `G`, or `T` (powers of 1024) — case-insensitive.
`"20M"`, `"2G"`, `"720k"`.

#### `base` — optional · string or object

A **starting-point image** for the drive: a media item the
drive's own image is materialized from — at `create`, or at the
first `start`. As an object it has two fields — `media` (required)
and `type` (how to materialize, optional). `base.media` names an
defined item in the media catalog, exactly like the
[`media` field](#media--optional--string): the name must resolve to a
[media definition](media-spec.md) in the library, possibly installed
from the current script before machine resolution, and the item is
fetched and hash-verified on demand. The difference is what happens
next —
`media` attaches the payload itself, `base` materializes the
drive's own image from it:

```json
{"drives": {"hdd0": {"base": {"media": "dos622-installed", "type": "duplicate"}}}}
```

A bare string is shorthand for the object with only `media` set:

```json
{"drives": {"hdd0": {"base": "dos622-installed"}}}
```

The state always carries the resolved object form, `type`
explicit.

The base itself is never written to; it is the fixed external
image the drive starts from. This is how pre-existing content
enters a machine: there is no dropping of files into the cache —
a drive that should start with content declares where that
content comes from, and `recreate` can regenerate it at any time.

`type` selects one of two materializations, defaulting to
`difference`:

| type         | meaning                                         |
|--------------|-------------------------------------------------|
| `difference` | the drive is a differencing disk backed by the base; writes land in the difference, the base stays pristine (default) |
| `duplicate`  | the base image is copied in full                |

`difference` maps to the backend's native mechanism — qcow2
backing files, VHDX differencing disks, VMDK linked clones, VDI
differencing — and is a backend/format capability: a backend that
cannot difference against the base fails the capability check
rather than silently copying (declare `"type": "duplicate"` to
copy instead). It is the default because it matches what based drives
are for: differencing keeps large bases cheap to fan out — many
machines can difference against one installed base image, each
paying only for its own writes — and a fresh difference is the
cheapest possible `recreate`.

`duplicate` works everywhere (converted to the backend's
preferred format when needed) and makes the drive fully
independent of backing-file support.

#### `hostdir` — optional · string

A host directory presented to the guest as a FAT drive —
readable and writable:

```json
{"drives": {"hdd1": {"hostdir": "work/"}}}
```

The guest reads and writes the drive like any disk; the
directory reflects the guest's writes at the latest by machine
stop — on QEMU (vvfat) they may appear live. While the machine
is stopped, the directory is the drive's content and is an
ordinary host directory: prepare or harvest it with any tool —
out-of-band exchange is the sanctioned file path
([instance model](instance-model.md)); host-side edits while the machine
runs are outside the contract. The directory always shows the
drive's *latest* state, never history — history is what run
records are for — and one directory should not
be shared by concurrently running machines.

Valid on `hdd` and `floppy` drives, never `cdrom` (no ISO9660
synthesis). A relative path resolves against the invocation's
asset root, so a checked-in blueprint can present the project's
own tree and stay portable (U4); an absolute path is allowed —
the content is the user's own, exactly the media `local-path`
class — with the caveat that it is machine-specific and belongs
in personal, not shared, blueprints. A missing directory fails
closed naming the path; contents exceeding the medium's capacity
(a floppy's fixed size, the platform-default hard-disk capacity)
fail at `start` naming the files that do not fit.

`hostdir` deliberately trades verification for liveness: the
directory is user-owned and mutable between runs, and nothing is
hash-checked — `media` remains the pinned, reproducible path for
content a workflow must trust (U4). The mechanism is the
adapter's under capability honesty: QEMU serves `hostdir` with
vvfat (proven in exactly this domain — simple FAT, DOS-era write
patterns); a backend without an equivalent serves the same
contract its own way (a FAT image materialized from the
directory and reconciled at rest) or reports the capability
unsupported, naming itself. `apply` absorbs `hostdir` changes
(content re-presents at the next start; nothing regenerates).

Division of labor: `hostdir` is the standing working surface
declared by the design; per-run injection and harvest are
out-of-band host work against the stopped machine
([instance model](instance-model.md)), for which a `hostdir`
drive is the natural surface.

#### `controller` — optional · string

The kind of storage controller the drive attaches to. This is
guest-visible hardware — the guest needs a driver for the
controller type — so it is blueprint vocabulary, not a backend detail:

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
{"drives": {"hdd0": {"size": "4G", "controller": "scsi"}}}
```

What the blueprint deliberately does **not** say:

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

`false` keeps the entry in the document but removes the drive
from the machine entirely — no slot, no hardware — useful for
switching between configurations without deleting entries:

```json
{"drives": {"hdd1": {"size": "100M", "enabled": false}}}
```

This differs from an empty removable drive (`null`): an empty
drive is present hardware awaiting a medium; a disabled drive does
not exist on the machine. (Temporarily mounted installer media
need neither — see the [`media`](#media--optional--string)
convention above.)

### Image naming and formats

A drive's own image file (from `size` or `base`) lives at the
canonical path `cache/machines/<id>/drives/<key>.<ext>` — the
drive key names the file, and the extension follows the image
format. There are no other image names, ever: the blueprint has no
image-path field, and nothing is hand-placed in the cache.

The format is reliquary's choice, made per backend. An image
created blank from `size`, or duplicated from a `base`
(`"type": "duplicate"`, converting when needed), uses the
backend's preferred dynamically-allocated format; a `difference`
drive uses the backend-native differencing format:

| backend      | image format |
|--------------|--------------|
| `qemu`       | qcow2 (v3)   |
| `virtualbox` | VDI          |
| `vmware`     | VMDK         |
| `hyperv`     | VHDX         |

Because reliquary owns image creation and naming, every
blueprint is format-portable by construction: the right format
arrives on whatever backend is assigned, and `recreate` onto a
different backend regenerates the images in the new backend's
format.

`media` drives attach the media payload file itself, whose format
is declared by its
[cached file name's extension](media-spec.md) in the media
library. A media payload in a format the machine's backend cannot
attach is a capability error naming both.

---

## `boot`

**blueprint (optional) · array of drive keys**

The boot order: drive keys (canonical or alias form) tried in
order.

```json
{"boot": ["hdd0", "cdrom0"]}
```

Every entry must reference a declared, enabled drive, and entries
are unique by slot: naming the same slot twice — in either
spelling — fails validation. An empty
or non-bootable drive is a valid entry: firmware falls through it
to the next entry. This is the standard install pattern —
`["hdd0", "cdrom0"]` with a blank `hdd0` and an empty `cdrom0`
falls through to the installer CD while a script has one attached,
and boots the installed hard disk afterward, with no boot-order
change needed. Scripts may still reorder boot devices with the
[`boot`](script-spec.md#boot) verb while the machine is stopped.
When omitted, the default order is: the slot-0 floppy image if
declared, else the slot-0 hard disk, else the first CD-ROM; the
resolved order appears in the state.

Backends differ in how faithfully they honor multi-entry boot
orders; a backend that cannot honor the declared order reports a
capability error rather than silently booting from something else.

---

## `control-planes`

**blueprint (optional) · array of strings**

The ordered control-plane policy: which control planes reliquary
may use for guest-facing operations on this machine, in preference
order. reliquary probes readiness in this order and never uses a
control plane the policy doesn't list. Entries are unique — a
control plane listed twice fails validation.

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

**blueprint (optional) · object**

The escape hatch for backend-specific configuration — explicitly
scoped and explicitly non-portable. One object per backend name;
only the section matching the machine's `backend` applies, other
sections are inert but preserved. When the blueprint does not
declare [`backend`](#backend), the sections present also steer
default assignment: settings for exactly one backend narrow the
assignment walk to that backend. For example:

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
  appear. A blueprint with no `backend-settings` is portable by
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
- state-only fields (`backend-id`, `blueprint-digest`,
  `blueprint-source`) in a blueprint;
- `boot` entries naming undeclared or disabled drives, or naming
  one slot twice (in either spelling), and duplicate
  `control-planes` entries;
- drive objects declaring none, or more than one, of `media`,
  `size`, `base`, and `hostdir`;
- `hostdir` on `cdrom` drives, or a `hostdir` directory that
  does not exist;
- `null` (empty) values on non-removable (`hdd`) drives;
- `media` or `base.media` names no media definition provides;
- `backend-settings` sections overlapping reliquary-owned fields;
- `parameters` values that are neither a string nor a
  `{"property": "<key>"}` object, or with invalid input or
  property names.

Capability checks (reject the blueprint for *this* backend,
naming backend and capability):

- media the backend cannot provide (unsupported medium, too many
  slots);
- controller types the backend cannot provide (e.g. anything but
  `scsi` on Hyper-V Generation 2);
- `difference` bases the backend/format pair cannot express;
- `hostdir` drives the backend cannot serve;
- image formats the backend cannot attach;
- control planes the backend cannot offer;
- boot orders the backend cannot honor.
