<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Blueprint — field reference

> **Descriptive.** The format's norm is the published schema
> (`reliquary/schemas/blueprint-schema-v1.json`, structure) plus
> [the composed blueprint model](spec/blueprint-model.md)
> (semantics); where this reference disagrees with either, this
> reference has the bug.
>
> Every per-field rule here is stated by one of those two. That
> was **not** true until 2026-07-27, when an audit found eight
> fields whose contracts lived only here — where, being
> descriptive, they bound nothing and the code was free to drift
> from them. They now sit in the model, and what follows explains
> and exemplifies them rather than defining them.

> **Status:** the full field reference is validated at parse time —
> `platform`, `backend`, `memory`, `cpus`, `drives` (a media name,
> `null`, or an object with `controller`/`enabled`/`media`), `boot`,
> `name`, `description`, `scripts`, `control-planes`,
> `backend-settings`, and `parameters` — with JSONC acceptance and
> media-name resolution. Machine materialization realizes each drive's
> media per its `materialize` mode (`new`/`difference`/`copy`/`use`),
> resolves defaults into the state, and records the provenance fields
> (`blueprint-digest`, `blueprint-source`, `backend-id`). Non-`ide`
> controllers and backend capability checks ride the adapter seam.
> Details may still change before first release.

Exhaustive reference for every field in the machine blueprint format —
shared by the **blueprint** (`<name>.rlqb`, yours) and each
machine's **state** (`cache/machines/<id>/machine.json`,
Reliquary's). A drive names a **media** component; the media's own
fields (`materialize`, `size`, `location`, `read-only`, …) live in
[the media spec](spec/media-spec.md). For the blueprint/state model, read
[the guide](blueprint-guide.md) first; for complete examples, see
the [cookbook](blueprint-cookbook.md).

Each field is marked with where it may appear:

- **blueprint** — valid in a blueprint (the `.rlqb` document you
  author and realize as a machine with
  `rlq create-machine --blueprint <name>`). Every blueprint field is also
  valid in the state, where it always appears fully resolved.
- **state-only** — written by Reliquary into the state; rejected
  in a blueprint.

All fields are present in the state unless noted otherwise.

There is no version field — see
[Format stability](blueprint-guide.md#format-stability-none-yet).
Blueprints accept comments and trailing commas — the JSONC
dialect — per the same section; the state is strict canonical
JSON, always.

The machine-checkable companion is the one published
[blueprint-schema-v1.json](../reliquary/schemas/blueprint-schema-v1.json)
(machine, media, source, and archive components in one schema) —
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
[platform defaults](blueprint-guide.md#platform-defaults) for omitted
fields. The list is extended deliberately, one platform workflow at
a time.

The platform is **never inferred**. Reliquary does not inspect disk
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
machine is materialized (`create` or `recreate`): Reliquary walks
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
[the guide](blueprint-guide.md#destroying-and-recreating-a-machine)).

```json
{"backend": "virtualbox"}
```

---

## `name`

**blueprint (optional) · string · present in the state**

The machine component's **identity** — its selection key. Declared,
it overrides the filename stem: `--blueprint <name>` selects it and a
machine's identity is `<name>-<n>`. A machine spec may not omit
it — identity falls back to the file stem (the common case, a
`freedos.rlqb` needs no `name`); a machine written inside a
`machines` section must name itself, since a section can hold several
and the file stem cannot pick one. Because it becomes a machine-id
segment and a
cache directory name it must be **id-safe**: a leading
alphanumeric then alphanumerics, `.`, `_`, or `-`, and never all
digits. Two blueprints resolving to one effective name within a
source are an error. `name` gives fileless object-provided
blueprints (which have no stem) a stable identity; human prose
belongs in [`description`](#description).

```json
{"name": "freedos"}
```

---

## `description`

**blueprint (optional) · string**

Human-readable discovery prose — the blueprint's one free-text
label, now that [`name`](#name) is an id-safe identity rather than
a display string. It does not affect machine behavior; it feeds
`search`, which matches terms against the identity name,
`description`, and platform (U5). Codex blueprints carry the description
through the codex's index; user blueprints are indexed by reading
the field from the file (see [the codex](spec/codex.md)).

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
`rlq run-script install --blueprint freedos`
looks up `scripts.install` and runs the script it names. Labels
take priority over bare script filenames.

```json
{
  "scripts": {
    "install": "freedos-install",
    "verify": "freedos-verify"
  }
}
```

Labels are conventionally short verbs — `install`, `verify`,
`test`, `configure`.

---

## `parameters`

**blueprint (optional) · object · not carried in the state**

Values the blueprint supplies to [script-declared
properties](spec/script-spec.md#properties) — the
blueprint's half of the customization seams its author designs in
(U5; see [the guide](blueprint-guide.md#customization-seams)).
Keys are property keys its scripts declare. Each value is one of
the two bindings the
use case names:

- a **direct value** — a JSON string: the parameter is specified
  in the blueprint itself. An automated-testing blueprint fixes
  its user name as `"testuser"`; a seeded copy is customized by
  editing the value.
- a **redirect** — `{"property": "<key>"}`: the declared key is
  answered by resolving *another* key through the remaining
  [property sources](spec/script-spec.md#the-property-sources) — so a
  generic script's key can be wired to a specific personal one,
  and automation can satisfy it from the environment. This is the
  form for values that must never enter the blueprint — a license
  key is the canonical example.

```json
{
  "parameters": {
    "identity.full-name": "testuser",
    "os.install-key": {"property": "products.windows-98.install-key"},
    "supplemental-disk": "freedos-bonus"
  }
}
```

When a script runs against a machine of this blueprint (or
creates one), each declared property binds from the first source
that answers: an explicit `--property` value, then the
blueprint parameter, then the environment, the properties file,
and — interactively — the ask (normative in the [script
spec](spec/script-spec.md#the-property-sources)). The
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
[`apply`](blueprint-guide.md#applying-blueprint-edits) or the
baseline digest, and an edit is live on the next script run — the
U5 loop is edit the blueprint, run the script.

---

## State-only fields

Four fields exist only in the state; a blueprint containing any of
them is rejected. (The state document also carries the machine's
bookkeeping — its blueprint's name, creation time, and lifecycle
phase — which is outside the blueprint field set entirely. A
script's outcome is not there at all: a run returns it to whoever
drove the run and stores nothing. See
[the instance model](spec/instance-model.md).)

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

This is the anchor for **ownership verification**: Reliquary never
sends a control command to a hypervisor object until the object's
identity matches `backend-id`. A stale or foreign machine is
detected and refused rather than manipulated.

### `blueprint-source`

**state-only · string**

The absolute path of the blueprint file this machine resolved
from at `create` (re-recorded by `apply`). Selection by
`--blueprint <name>` matches only machines whose recorded source
equals the invocation's own resolution of that name — through its
asset root (docs/spec/asset-resolution.md) — so
same-named blueprints in different projects never select each
other's machines, and `apply` can never adopt another project's
blueprint: a selection or reconciliation whose resolution
disagrees with the recorded source fails closed naming both
paths.

### `blueprint-digest`

**state-only · string**

The digest of the resolved blueprint snapshot this machine was created
from (or last [`apply`](blueprint-guide.md#applying-blueprint-edits)-d
to). This is the machine's baseline. Operation may diverge the
state from it — script `insert`/`eject` persists in the state —
and `apply` is what reconciles the machine back to (or forward to
an edited) blueprint; editing the blueprint file changes nothing
until `apply` records a new digest.

---

## `memory`

**blueprint (optional) · positive integer or size string**

Guest memory. A size string uses the same grammar as a media
[`size`](spec/media-spec.md#size) — a positive integer with a
binary unit suffix (`K`/`M`/`G`/`T`, powers of 1024) — and a bare
integer means MiB, so
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

The machine's drive inventory — topology only. Keys declare a medium
and slot; each value names the **media** the slot carries (or leaves
it empty), plus optional hardware attributes. What the content *is*
and how it materializes belongs to the named
[media component](spec/media-spec.md), never to the drive.

### Keys: medium and slot

| medium   | slots         | keys                      |
|----------|---------------|---------------------------|
| `floppy` | 0–1           | `floppy0`, `floppy1`      |
| `hdd`    | 0–3           | `hdd0` ... `hdd3`         |
| `cdrom`  | 0–3           | `cdrom0` ... `cdrom3`     |

In a blueprint, the bare medium name is accepted as an alias for
slot 0 (`"hdd"` ≡ `"hdd0"`); the state always uses the canonical
indexed form. A per-machine image, when a drive's media materializes
one, is named for the **media**, not the slot (see
[image naming](#image-naming-and-formats) below). Declaring both an
alias and its indexed form in one document is a slot clash and fails
validation, as do slots outside the table's ranges.

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

A value is a **media-name string** (shorthand):

```json
{"drives": {"cdrom": "freedos-livecd"}}
```

or an **object** carrying the media name plus hardware attributes:

```json
{"drives": {"hdd0": {"media": "dos622-installed", "controller": "scsi"}}}
```

The drive names one [`media`](#media--optional--string) component and
says nothing else about content: the media owns
[materialization](spec/media-spec.md#materialize) — a fresh blank, a
writable overlay over a payload, a copy of one, or an attached
payload (a file, or a host directory served as a virtual FAT drive).
**The old four-way drive content selector (`size` / `base` / `media`
/ `hostdir`) is gone**; a blank disk is a media with
`materialize: new`, a differencing drive is a media with
`materialize: difference`, a `hostdir` drive is a media whose
`location` is a directory with `materialize: use`. To change how a
drive materializes, change (or point at a different) media.

A removable drive (`cdrom`, `floppy`) may instead be declared
**empty** with the value `null`:

```json
{"drives": {"cdrom0": null}}
```

The slot exists as guest-visible hardware with no medium inserted.
This is the normal shape for a drive that scripts occupy
temporarily — an install script inserts the installer medium into
the empty slot and ejects it as its final step (U1; see
[the script spec](spec/script-spec.md#insert-and-eject)). Declaring
the slot is required: `insert` only places media into hardware
the blueprint declares, and never creates the drive itself — the
blueprint alone determines machine topology, so capability
preflight (and a script's `insert` targets) can be checked before
anything runs. Fixed drives
(`hdd`) cannot be empty.

There are no paths to Reliquary-managed images anywhere in the
blueprint. A drive whose media materializes a per-machine image
(`new` / `difference` / `copy`) gets it created by Reliquary inside
the cached materialization, named for the **media** —
`cache/machines/<id>/media/blank-20m.qcow2` for a media `blank-20m`
on QEMU — with the extension of the format Reliquary chose (see
[image naming](#image-naming-and-formats)). You never name, place,
or reference these files; the media name is the handle.

#### `media` — optional · string

The name of a [media component](spec/media-spec.md):

```json
{"media": "freedos-livecd"}
```

The name resolves against the blueprint namespace — the `media`
components across every `.rlqb` in the active source — and its
payload is fetched and hash-verified on demand. A name no component
provides is an error (resolution fails closed naming the media). The
media owns [materialization](spec/media-spec.md#materialize): a `use`
media attaches the payload itself (use it for machine-independent
media the machine carries *at rest* — a driver disk, a reference
CD), while `new`/`difference`/`copy` materialize a per-machine image.
Media a workflow needs only temporarily — above all installer ISOs —
conventionally stay off the machine's drives: declare the slot empty
and let the install script insert and eject the medium, so the
machine's default shape is the installed system, not the installer.
A media name is the *only* cross-boundary reference the machine
shape may make: the drive inventory reaches the media components and
nothing else (U4). (The [`scripts`](#scripts) map and
[`parameters`](#parameters) property references are invocation
wiring — they configure script binding, never machine shape.)

A `cdrom` drive's media must be read-only (`materialize: use`): the
optical medium has nothing to size, difference, or synthesize, so a
`new`/`difference`/`copy` media on a `cdrom` fails validation naming
the drive.

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
{"drives": {"hdd0": {"media": "system-disk", "controller": "scsi"}}}
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
offers them and a guest with the driver — Reliquary checks the
backend half and leaves the driver half to you. A declared
controller the machine's backend cannot provide is a capability
error naming both.

One ordering caveat, for when a second controller type is wired:
slot order is authoritative *within* a type, and across types the
guest's firmware decides how the controllers themselves enumerate.
On such a machine no disk letter is a declared fact, so the
in-band file verbs refuse every disk address rather than guess one
(floppies keep `A:` and `B:`, which nothing can shift). Prefer one
controller type per machine when drive lettering matters, as it
does under DOS. The constraint is recorded with the work that
would make it reachable — F2's device growth in
[planning/proposed/FEATURES.md](../planning/proposed/FEATURES.md) —
rather than stated here as a rule, because today it describes a
machine that cannot be built.

#### `enabled` — optional · boolean · default `true`

`false` keeps the entry in the document but removes the drive
from the machine entirely — no slot, no hardware — useful for
switching between configurations without deleting entries:

```json
{"drives": {"hdd1": {"media": "scratch-100m", "enabled": false}}}
```

This differs from an empty removable drive (`null`): an empty
drive is present hardware awaiting a medium; a disabled drive does
not exist on the machine. (Temporarily mounted installer media
need neither — see the [`media`](#media--optional--string)
convention above.)

### Image naming and formats

A drive's per-machine image (a media that `materialize`s
`new` / `difference` / `copy`) lives at the canonical path
`cache/machines/<id>/media/<media-name>.<ext>` — named for the
media, not the slot, so a media moving through one removable slot
keeps its own image and a re-insert reuses it. There are no other
image names, ever: the blueprint has no image-path field, and
nothing is hand-placed in the cache.

The format is Reliquary's choice, made per backend. A `new` blank,
or a `copy` of a payload (converting when needed), uses the
backend's preferred dynamically-allocated format; a `difference`
media uses the backend-native differencing format:

| backend | image format | |
|--------------|--------------|---|
| `qemu`       | qcow2 (v3)   | built |
| `virtualbox` | VDI          | not wired — F3 |
| `vmware`     | VMDK         | not wired — F2 |
| `hyperv`     | VHDX         | not wired — F2 |

**Only `qemu` is built.** The other three rows are the intended
mapping, recorded with the work that would deliver it
([planning/proposed/FEATURES.md](../planning/proposed/FEATURES.md)),
not a promise this version keeps: a blueprint naming an unwired
backend is refused at `create-machine` naming the gap, rather than
quietly getting QEMU's format and QEMU's lifecycle.

Because Reliquary owns image creation and naming, a blueprint is
format-portable *by construction* rather than by luck — the format
is never written down anywhere for a backend change to contradict,
and `recreate` onto a different backend regenerates the images in
the new backend's format. What that buys is available the day a
second backend is; the construction is what makes it cheap then,
and it is worth stating now for the same reason the table is.

A `use` media attaches the payload file itself — or its `location`
directory, served as vvfat — with no per-machine image. Its format
is declared by its
[cached file name's extension](spec/media-spec.md). A media payload in a
format the machine's backend cannot attach is a capability error
naming both.

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
[`boot`](spec/script-spec.md#boot) verb while the machine is stopped.
When omitted, the default order is: the slot-0 floppy image if
declared, else the slot-0 hard disk, else the first CD-ROM; the
resolved order appears in the state.

Backends differ in how faithfully they honor multi-entry boot
orders; a backend that cannot honor the declared order reports a
capability error rather than silently booting from something else.

---

## `control-planes`

**blueprint (optional) · array of strings**

The ordered control-plane policy: which control planes Reliquary
may use for guest-facing operations on this machine, in preference
order. Reliquary probes readiness in this order and never uses a
control plane the policy doesn't list. Entries are unique — a
control plane listed twice fails validation.

Working name set:

| name                | mechanism                                  | built |
|---------------------|--------------------------------------------|-------|
| `agentless-display` | keyboard injection + screen readback; no guest cooperation needed | yes |
| `vnc`               | framebuffer and input over VNC             | no    |
| `serial-console`    | text console on an emulated serial port    | no    |
| `guest-agent`       | structured agent protocol (QGA profile)    | no    |

The names are the model's whole vocabulary and the parser accepts
them all; only `agentless-display` exists today, so a blueprint
listing any of the others is refused at materialization —
`create-machine` and `apply-blueprint` fail closed naming the plane
rather than recording a policy Reliquary cannot honor. A plane that
is built is one Reliquary can probe, so the refusal is what keeps
the state's list truthful. Listing a working plane alongside an
unbuilt one does not excuse it: the policy is every plane Reliquary
may use.

Defaults by platform (DOS: `["agentless-display"]`); the resolved
default appears in the state. Backends that cannot provide a
listed control plane fail capability checking (e.g. `vnc` on
Hyper-V).

```json
{"control-planes": ["agentless-display"]}
```

Today that is the only list a machine can be built from. The
preference order the field exists for — `["guest-agent",
"agentless-display"]`, meaning *try the agent, fall back to the
display* — is the shape it takes once a second plane is built.

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
- Settings may not touch what Reliquary owns through first-class
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
- a drive object missing `media`, or carrying keys other than
  `media` / `controller` / `enabled`;
- `null` (empty) values on non-removable (`hdd`) drives;
- a `media` name no media component provides (plus every media /
  source / archive rule in [the media spec](spec/media-spec.md));
- a `cdrom` drive naming a media that is not read-only `use`;
- `backend-settings` sections overlapping Reliquary-owned fields;
- `parameters` values that are neither a string nor a
  `{"property": "<key>"}` object, or with invalid input or
  property names.

Capability checks (reject the blueprint for *this* backend,
naming backend and capability):

- media the backend cannot provide (unsupported medium, too many
  slots);
- controller types the backend cannot provide (e.g. anything but
  `scsi` on Hyper-V Generation 2);
- `difference` media the backend/format pair cannot express;
- directory-source media the backend cannot serve;
- image formats the backend cannot attach;
- control planes the backend cannot offer;
- boot orders the backend cannot honor.
