<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Blueprint — field reference

> **Descriptive.** The authoritative definition of the format is the
> published schema (`src/reliquary/schemas/blueprint-schema-v1.json`,
> for structure) plus
> [the composed blueprint model](spec/blueprint-model.md) (for
> semantics). Where this reference disagrees with either one, this
> reference is wrong.
>
> Every per-field rule here is also stated by one of those two
> documents. That wasn't true until 2026-07-27, when an audit found
> eight fields whose rules only existed here — and because this
> document is descriptive rather than authoritative, those rules
> didn't actually bind anything, so the code was free to drift away
> from them. Those rules now live in the model instead, and what
> follows explains and gives examples of them rather than being the
> place that defines them.

> **Status:** every field in this reference is validated at parse
> time — `platform`, `backend`, `memory`, `cpus`, `drives` (a media
> name, `null`, or an object with `controller`/`enabled`/`media`),
> `boot`, `name`, `description`, `scripts`, `control-planes`,
> `backend-settings`, and `parameters` — along with accepting JSON5
> syntax and resolving media names. When a machine is materialized,
> each drive's media is realized per its `materialize` mode
> (`new`/`difference`/`copy`/`use`), defaults are resolved into the
> state, and the provenance fields (`blueprint-digest`,
> `blueprint-source`, `backend-id`) are recorded. Backend capability
> checks run at materialization time, against a report from the
> assigned backend itself; controllers other than `ide` are waiting
> on a backend that offers them. Details may still change before the
> first release.

A complete reference for every field in the machine blueprint
format — shared by the **blueprint** (`<name>.rlqb`, which belongs
to you) and each machine's **state**
(`cache/machines/<id>/machine.json`, which belongs to Reliquary). A
drive names a **media** component; the media's own fields
(`materialize`, `size`, `location`, `read-only`, and so on) are
documented in [the media spec](spec/media-spec.md). For the concepts
behind the blueprint/state split, read [the guide](blueprint-guide.md)
first; for complete worked examples, see the
[cookbook](blueprint-cookbook.md).

Each field below is marked with where it's allowed to appear:

- **blueprint** — valid in a blueprint (the `.rlqb` document you
  write, which becomes a machine when you run
  `rlq create-machine --blueprint <name>`). Every blueprint field is
  also valid in a machine's state, where it always shows up fully
  resolved.
- **state-only** — written by Reliquary into the state; not allowed
  in a blueprint.

All fields show up in the state unless it says otherwise.

There's no `version` field — see
[Format stability](blueprint-guide.md#format-stability). Blueprints
accept the published JSON5 grammar — comments, trailing commas,
unquoted keys, and so on — as described in that same section; the
state is always strict, canonical JSON.

There's also a machine-readable companion to this reference: the
published
[blueprint-schema-v1.json](../src/reliquary/schemas/blueprint-schema-v1.json),
one schema covering the machine, media, source, and archive
components together. It only captures the structural subset of the
format checks below — this written reference is the authoritative
one.

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

The platform selects the workflow behavior used for the machine —
how boot readiness is detected, command syntax, prompt handling —
and the [platform defaults](blueprint-guide.md#platform-defaults)
for any field you omit. This list only grows deliberately, one
platform workflow at a time.

The platform is **never guessed**. Reliquary doesn't inspect disk
images, watch the guest screen, or probe devices to figure out what
OS a machine runs — the blueprint has to say so explicitly, or
nothing does.

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

When `backend` is left out of the blueprint, it's assigned when the
machine is materialized (at `create` or `recreate`): Reliquary walks
through its backend priority order one by one, probing each for
availability on the host, and assigns the first one that's available
and capable of everything the blueprint asks for. Capability is
judged against the whole blueprint — the media and image types the
backend has to be able to attach, any required
[`control-planes`](#control-planes), and
[`backend-settings`](#backend-settings) — so a blueprint can
effectively dictate its backend without declaring one explicitly: a
`backend-settings` section for exactly one backend, or a media type
only one backend can handle, narrows the walk down to that backend
on its own. Declaring `backend` explicitly pins the choice instead —
only that one backend is probed, and `create` fails if it's
unavailable or incapable, rather than falling back to another one.

Either way, the resolved value is recorded in the state (so a
blueprint that omits it stays portable), and the assignment holds
for the machine's entire life. Backend-specific state —
identifiers, disk image formats, VM registration — doesn't carry
over between hypervisors, so the assignment never changes underneath
a running machine. To move a machine to another backend, use
`recreate`, which discards the state and the backend machine and
resolves the blueprint fresh (see
[the guide](blueprint-guide.md#destroying-and-recreating-a-machine)).

```json
{"backend": "virtualbox"}
```

---

## `name`

**blueprint (optional) · string · present in the state**

The machine component's **identity** — its selection key. Declared,
it overrides the filename stem: `--blueprint <name>` selects it and
a machine's identity is `<name>-<n>`. A single machine spec doesn't
have to declare it — its identity then falls back to the file's
stem (the common case: `freedos.rlqb` needs no `name` field). But a
machine written inside a `machines` section must name itself, since
a section can hold several specs and the file's stem can't pick
between them. Because the name becomes part of a machine's id and
part of a cache directory name, it has to be **id-safe**: it must
start with a letter or digit, followed by letters, digits, `.`,
`_`, or `-`, and it can never be all digits. If two blueprints in
the same source resolve to the same effective name, that's an
error. `name` is also what gives a stable identity to blueprints
that don't come from a file at all (object-provided blueprints with
no filename to fall back on); free-form human-readable text belongs
in [`description`](#description), not here.

```json
{"name": "freedos"}
```

---

## `description`

**blueprint (optional) · string**

Human-readable text for discovery — the blueprint's one free-text
field, now that [`name`](#name) is an id-safe identity rather than
something meant for display. It doesn't affect machine behavior at
all; it's what `search` matches against, along with the identity
name and platform (U5). For codex blueprints, the description comes
through the codex's own index; for user blueprints, it's read
straight from the file (see [the codex](spec/codex.md)).

```json
{
  "description": "Installs FreeDOS 1.4 onto a blank hard disk. Selects the Plain DOS system package set."
}
```

---

## `scripts`

**blueprint (optional) · object**

A map from short labels to script file names (the filename stem of
`scripts/<name>.rlqs`). Labels are the verbs you use with the
`run-script` command: `rlq run-script install --blueprint freedos`
looks up `scripts.install` and runs the script it names. A label
takes priority over a bare script filename with the same text.

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

Values the blueprint supplies to
[properties a script declares](spec/script-spec.md#properties) —
this is the blueprint's half of the customization seams its author
builds in (U5; see
[the guide](blueprint-guide.md#customization-seams)). Keys are
property keys declared by the blueprint's scripts. Each value is one
of two kinds:

- a **direct value** — a plain JSON string: the value is written
  straight into the blueprint. An automated-testing blueprint might
  fix its user name as `"testuser"`; a copy seeded from it is then
  customized by editing that value.
- a **redirect** — `{"property": "<key>"}`: the declared key gets
  its value by resolving a *different* key, through whichever of
  the remaining [property sources](spec/script-spec.md#the-property-sources)
  answers it. This lets a generic script's key point at a specific
  personal one, or let automation supply it from the environment.
  Use this form for anything that must never enter the blueprint
  itself — a license key is the classic example.

```json
{
  "parameters": {
    "identity.full-name": "testuser",
    "os.install-key": {"property": "products.windows-98.install-key"},
    "supplemental-disk": "freedos-bonus"
  }
}
```

When a script runs against a machine of this blueprint (or creates
one), each declared property gets its value from the first source
that answers it, checked in this order: an explicit `--property`
value, then the blueprint's parameter, then the environment, then
the properties file, and finally — if running interactively — a
prompt (this order is authoritative in the
[script spec](spec/script-spec.md#the-property-sources)). So a
blueprint's own values override a person's standing values — a
value the blueprint fixes stays fixed for every machine created
from it — while an explicit value on the command line overrides
even the blueprint, for that one invocation. A redirect *replaces*
resolution of the declared key entirely: the target key it points at
is resolved through the remaining, non-blueprint sources (ending
with an interactive prompt), or fails if running non-interactively.
Parameters never chain through other parameters, and resolution
never falls back to the key the author redirected away from.

These rules are checked at blueprint validation and at script
preflight:

- A value has to be a string or a `{"property": "<key>"}` object —
  nothing else is allowed. Keys and redirect targets have to be
  valid property names.
- A `secret`-typed property can never take a direct value:
  blueprints are meant to be shared and put in version control
  (U4), and a secret written directly into one would be plaintext
  in source control. A secret parameter has to use the redirect
  form, and its target then follows the secret rules of whatever
  source ends up answering it (a secret property in the file, the
  warned-about plaintext class in the environment, but never a
  command-line argument). Ordinary (`text`, `media`) properties
  require ordinary values in return — a mismatch between the two
  fails outright, rather than quietly downgrading protected data.
- A parameter that names a property the *currently running* script
  doesn't declare is simply unused for that run: one blueprint's
  parameters serve every script in its [`scripts`](#scripts) map,
  and each script only binds the properties it declares itself. A
  parameter that doesn't match any declared property in *any*
  script in the map gets flagged as a validation warning — it's
  probably a typo.

Like the `scripts` map, `parameters` is read straight from the
blueprint file each time a script runs — it configures how the
script binds its values, not the machine's shape. It never appears
in the machine's state, plays no part in
[`apply`](blueprint-guide.md#applying-blueprint-edits) or the
baseline digest, and an edit to it takes effect the very next time a
script runs — the whole U5 workflow is: edit the blueprint, run the
script.

---

## State-only fields

Four fields exist only in the state; a blueprint that contains any
of them gets rejected. (The state document also carries the
machine's own bookkeeping — its blueprint's name, creation time, and
lifecycle phase — which isn't part of the blueprint field set at
all. A script's outcome isn't stored here either: a run returns it
directly to whoever ran it and stores nothing. See
[the instance model](spec/instance-model.md).)

### `id`

**state-only · string**

The machine's own id (`<blueprint>-<n>`), repeated inside the state
file itself as a safety check — it has to match the name of the
machine directory the state file sits in. A mismatch (for example,
from a hand-copied or misplaced machine directory) is caught and
refused before any operation touches the backend.

### `backend-id`

**state-only · string**

The backend's own identifier for this machine:

| backend      | identifier                  |
|--------------|-----------------------------|
| `qemu`       | QEMU instance name          |
| `virtualbox` | VM UUID                     |
| `vmware`     | path to the `.vmx` file     |
| `hyperv`     | Hyper-V VM id               |

This is what makes **ownership verification** possible: Reliquary
never sends a control command to a hypervisor object until that
object's identity matches the recorded `backend-id`. A stale or
unrelated machine object gets detected and refused, rather than
accidentally controlled.

### `blueprint-source`

**state-only · string**

The absolute path of the blueprint file this machine was resolved
from at `create` (updated again by `apply`). Selecting with
`--blueprint <name>` only matches machines whose recorded source
matches the path that name resolves to in this invocation — through
its own asset root (docs/spec/asset-resolution.md). That's why
same-named blueprints in different projects never select each
other's machines, and why `apply` can never accidentally adopt
another project's blueprint: if a selection or reconciliation's
resolved path disagrees with the recorded source, it fails, naming
both paths.

### `blueprint-digest`

**state-only · string**

The digest of the resolved blueprint snapshot this machine was
created from (or last had
[`apply`](blueprint-guide.md#applying-blueprint-edits)-ed against
it). This is the machine's baseline. Normal operation can make the
state diverge from it — a script's `insert`/`eject` persists in the
state — and `apply` is what reconciles the machine back to that
baseline, or forward to an edited one. Editing the blueprint file
changes nothing about an existing machine until `apply` records a
new digest for it.

---

## `memory`

**blueprint (optional) · positive integer or size string**

How much memory the guest gets. A size string uses the same grammar
as a media's [`size`](spec/media-spec.md#size) field — a positive
integer with a binary unit suffix (`K`/`M`/`G`/`T`, powers of
1024) — and a bare integer means MiB, so `"memory": "32M"` and
`"memory": 32` mean exactly the same thing. The value has to
resolve to a whole number of MiB, because the state always stores
it as a plain MiB integer. Defaults by platform: DOS 16 MiB,
OpenBSD 512 MiB, win9x 64 MiB, winnt 256 MiB.

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

The machine's drive inventory — this only describes the topology,
not the content. Each key declares a medium and a slot; each value
names the **media** that slot carries (or leaves it empty), plus
optional hardware attributes. What the content actually *is*, and
how it gets materialized, is entirely up to the named
[media component](spec/media-spec.md) — never up to the drive
itself.

### Keys: medium and slot

| medium   | slots         | keys                      |
|----------|---------------|---------------------------|
| `floppy` | 0–1           | `floppy0`, `floppy1`      |
| `hdd`    | 0–3           | `hdd0` ... `hdd3`         |
| `cdrom`  | 0–3           | `cdrom0` ... `cdrom3`     |

In a blueprint, the bare medium name is accepted as shorthand for
slot 0 (`"hdd"` means the same thing as `"hdd0"`); the state always
spells it out in the full indexed form. If a drive's media
materializes a per-machine image, that image is named after the
**media**, not the slot (see
[image naming](#image-naming-and-formats) below). Declaring both the
shorthand and its indexed form for the same slot in one document is
a clash and fails validation, as does a slot number outside the
ranges in the table above.

**Slots are logical positions, not controller addresses.** Slot
numbers determine guest drive ordering — DOS assigns `C:`, `D:`,
and so on by disk order — and each backend maps those slots onto
controller ports in its own documented, predictable order. Which
port or channel a disk actually sits on is the backend's concern;
which *kind* of controller it's attached to is what you declare per
drive with [`controller`](#controller--optional--string), because
the guest needs a matching driver for it.

If a backend can't provide a declared drive — no floppy support, or
fewer slots of a given medium than were declared — it fails with a
capability error naming the backend and the drive. Drives are never
silently dropped.

### Values

A value is a **media-name string** (shorthand):

```json
{"drives": {"cdrom": "freedos-livecd"}}
```

or an **object** carrying the media name plus hardware attributes:

```json
{"drives": {"hdd0": {"media": "dos622-installed", "controller": "scsi"}}}
```

The drive names one [`media`](#media--optional--string) component
and says nothing else about its content — the media is what
controls [materialization](spec/media-spec.md#materialize): a fresh
blank disk, a writable overlay on top of a payload, a copy of one,
or an attached payload as-is (a file, or a host directory served as
a virtual FAT drive). **The old four-way drive-content selector
(`size` / `base` / `media` / `hostdir`) is gone.** A blank disk is
now a media with `materialize: new`; a differencing drive is a
media with `materialize: difference`; a `hostdir` drive is a media
whose `location` is a directory, with `materialize: use`. To change
how a drive materializes, change the media it names — or point it
at a different media.

A removable drive (`cdrom`, `floppy`) may instead be declared
**empty** with the value `null`:

```json
{"drives": {"cdrom0": null}}
```

The slot exists as guest-visible hardware, just with no medium
inserted. This is the normal shape for a drive that a script fills
in temporarily — an install script inserts the installer medium
into the empty slot and ejects it as its very last step (U1; see
[the script spec](spec/script-spec.md#insert-and-eject)). Declaring
the empty slot ahead of time is required: `insert` only places
media into hardware the blueprint already declares, and never
creates the drive itself. The blueprint alone determines a
machine's topology, which is what lets capability preflight (and a
script's `insert` targets) get checked before anything actually
runs. Fixed drives (`hdd`) can't be empty.

There are no file paths to Reliquary-managed images anywhere in the
blueprint. If a drive's media materializes a per-machine image
(`new` / `difference` / `copy`), Reliquary creates it inside the
cache, named for the **media** — for example,
`cache/machines/<id>/disks/blank-20m.qcow2` for a media named
`blank-20m` on QEMU — with the file extension of whatever format
Reliquary chose (see [image naming](#image-naming-and-formats)). You
never name, place, or reference these files yourself; the media's
name is the only handle you need.

#### `media` — optional · string

The name of a [media component](spec/media-spec.md):

```json
{"media": "freedos-livecd"}
```

The name resolves against the blueprint namespace — the `media`
components across every `.rlqb` file in the active source — and its
payload is fetched and hash-verified on demand. A name that no
component provides is an error (resolution fails, naming the
missing media). The media component controls
[materialization](spec/media-spec.md#materialize): a `use` media
attaches the payload as-is (use this for media the machine just
carries *at rest*, unchanged — a driver disk, a reference CD),
while `new`/`difference`/`copy` materialize a per-machine image
instead. Media a workflow only needs temporarily — installer ISOs
above all — conventionally stay off the machine's drives entirely:
declare the slot empty, and let the install script insert and eject
the medium itself, so the machine's default shape is the installed
system, not the installer. A media name is the *only* reference the
machine shape is allowed to make outside itself — the drive
inventory can reach media components and nothing else (U4). (The
[`scripts`](#scripts) map and the property references inside
[`parameters`](#parameters) are invocation wiring, not machine
shape — they configure how a script binds, never what the machine
looks like.)

A `cdrom` drive's media has to be read-only (`materialize: use`) —
an optical medium has nothing to size, difference, or synthesize,
so a `new`/`difference`/`copy` media on a `cdrom` fails validation,
naming the drive.

#### `controller` — optional · string

The kind of storage controller the drive attaches to. This is
hardware the guest can see, and the guest needs a driver for that
particular controller type — so it's part of the blueprint's
vocabulary, not just a backend detail:

| value    | controller                  |
|----------|-----------------------------|
| `ide`    | IDE / parallel ATA          |
| `sata`   | SATA (AHCI)                 |
| `scsi`   | SCSI                        |
| `nvme`   | NVMe                        |
| `virtio` | virtio block (paravirtual)  |

Valid on `hdd` and `cdrom` drives; floppies attach to the floppy
controller automatically and reject a `controller` key entirely.
The default for every current platform is `ide`, resolved into the
state when the machine is created.

```json
{"drives": {"hdd0": {"media": "system-disk", "controller": "scsi"}}}
```

What the blueprint deliberately leaves unsaid:

- **Which exact port or channel.** Drives sharing a controller type
  attach in slot order; the precise port layout is the backend
  adapter's own documented, predictable mapping.
- **Vendor variants.** BusLogic vs. LsiLogic SCSI, a specific AHCI
  implementation — these select a particular guest driver within a
  family and are backend-specific. When they matter, they belong in
  [`backend-settings`](#backend-settings).

Controller support is a backend capability, checked the same way
any other one is. Every backend supports `ide` except Hyper-V
Generation 2 machines, which only support SCSI. Paravirtual
controller types need both a backend that offers them and a guest
with the matching driver installed — Reliquary checks the backend
half of that, and leaves the driver half up to you. A declared
controller the machine's backend can't provide is a capability
error, naming both.

One caveat about ordering, for a machine wired with more than one
controller type: slot order only determines drive order *within* a
single controller type — across types, it's the guest's own
firmware that decides how the controllers enumerate. On a machine
like that, no disk letter is a fact you can read off the
blueprint — you can't work out from the blueprint alone which disk
the guest will call `C:`, and Reliquary can't tell you either,
since it never maps a volume to a letter itself. Use one controller
type per machine when drive lettering matters to you, as it does
under DOS. This caveat is recorded alongside the work that would
actually make it relevant — richer device topology, tracked in
[planning/proposed/FEATURES.md](../planning/proposed/FEATURES.md) —
rather than being stated here as a hard rule, because today it
describes a machine that can't actually be built yet: the one
adapter that exists only wires up `ide`, and says so by name if a
blueprint asks for more than that.

#### `enabled` — optional · boolean · default `true`

Setting this to `false` keeps the entry in the document but removes
the drive from the machine entirely — no slot, no hardware at all.
This is useful for switching between configurations without
deleting entries outright:

```json
{"drives": {"hdd1": {"media": "scratch-100m", "enabled": false}}}
```

This is different from an empty removable drive (`null`): an empty
drive is hardware that exists and is waiting for a medium, while a
disabled drive doesn't exist on the machine at all. (Temporarily
mounted installer media need neither of these — see the
[`media`](#media--optional--string) convention above.)

### Image naming and formats

A drive's per-machine image (from a media whose `materialize` is
`new`, `difference`, or `copy`) always lives at
`cache/machines/<id>/disks/<media-name>.<ext>` — named for the
media, not the slot, so a media that moves through one removable
slot keeps its own image, and reinserting it reuses that same
image. There's never any other image name: the blueprint has no
field for an image path, and nothing gets hand-placed into the
cache.

The image format is Reliquary's own choice, made per backend. A
`new` blank disk, or a `copy` of a payload (converting the format
if needed), uses the backend's preferred dynamically-allocated
format; a `difference` media uses that backend's own native
differencing format:

| backend | image format | |
|--------------|--------------|---|
| `qemu`       | qcow2 (v3)   | built |
| `virtualbox` | VDI          | lifecycle + agentless display (F50/F52) |
| `vmware`     | VMDK         | adapter unbuilt |
| `hyperv`     | VHDX         | adapter unbuilt |

**Only the QEMU adapter is actually built.** Each backend's adapter
is responsible for the image formats it materializes, so the other
three rows in the table above describe the intended mapping —
tracked alongside the work that would build it
([planning/proposed/FEATURES.md](../planning/proposed/FEATURES.md)) —
not something this version of Reliquary actually delivers. Those
three adapters honestly report that they can't do it, claiming no
capability at all, so backend assignment skips over them even when
the backend software itself is installed on the host. A blueprint
that names one of those backends is refused at `create-machine`,
naming the backend and what it's missing — rather than quietly
getting QEMU's format and lifecycle substituted in instead.

Because Reliquary is what owns image creation and naming, a
blueprint is portable between image formats *by design* rather than
by luck — the format is never written down anywhere for a backend
change to contradict, and `recreate`-ing onto a different backend
regenerates the images in that backend's own format. This benefit
becomes available the day a second backend adapter actually exists;
it's the design choice that makes it cheap once that happens, and
it's worth stating now for the same reason the table above is.

A `use` media attaches the payload file itself — or, for a
`location` that's a directory, serves it as a virtual FAT drive —
with no per-machine image involved at all. Its format is determined
by the extension of its
[cached file name](spec/media-spec.md). If a media payload is in a
format the machine's backend can't attach, that's a capability
error naming both.

---

## `boot`

**blueprint (optional) · array of drive keys**

The boot order: drive keys (canonical or alias form) tried in
order.

```json
{"boot": ["hdd0", "cdrom0"]}
```

Every entry has to reference a declared, enabled drive, and entries
have to be unique by slot: naming the same slot twice, even with
different spellings, fails validation. An empty or non-bootable
drive is a valid entry to list — though whether firmware actually
moves past it to the next entry is up to the firmware itself, see
below. A script can still reorder boot devices while the machine is
stopped: the [`set-boot`](spec/script-spec.md#set-boot) statement
*replaces* the boot order and leaves it replaced, while
[`with boot`](spec/script-spec.md#scoped-machine-state-changes)
puts named drives ahead of it just for one stage, restoring the
original order once that stage ends. When `boot` is omitted, the
default order is: the slot-0 floppy image if one's declared,
otherwise the slot-0 hard disk, otherwise the first CD-ROM; the
resolved order shows up in the state.

### Fallthrough is the firmware's, and it is not uniform

**Don't rely on a hard disk falling through to the next boot
entry.** Whether firmware moves on from an unbootable device is
entirely up to the firmware itself — it's not something Reliquary
implements or can control — and the backends tested so far don't
even agree with each other about it:

| the entry tried | QEMU (SeaBIOS) | VirtualBox |
|---|---|---|
| blank hard disk, no partition table | falls through | falls through |
| partitioned disk with no *active* partition | falls through | **stops** |
| empty optical drive | falls through | falls through |

VirtualBox prints `No active partition. Trying next boot
device...` and then just stops there — so a machine can end up in
that state once an installer has partitioned the disk but hasn't
made it bootable yet.

**So an install that reboots partway through can't depend on
falling past its own disk.** Ordering `["hdd0", "cdrom0"]` and
trusting the blank disk to fall through *looks* like it works at
first — the installer CD boots fine — and then it fails on the
reboot that happens *after* partitioning, but only on some
backends. The CD genuinely has to be first for the entire install,
and the script ejects it once the disk is ready: every boot then
takes the CD as long as one's attached, and once the slot is empty,
the installed disk boots — neither step ever depends on firmware
falling past a disk.

**Where that boot order gets declared is exactly what this field
decides.** Booting from the installer is true of an *install*, not
of the machine in general, so it belongs in the install script, not
here:

```rlqs
with boot cdrom0 {
    phase startup { … }
}
```

`with boot` states a prefix — the named drive goes first, and this
field's own order follows after it — so the blueprint declares what
the machine fundamentally is (`["hdd0", "cdrom0"]`, a system that
boots its own disk past an empty optical drive), while the script's
stage declares what it needs to boot for that one step. The scoped
change is undone once the stage ends, on every outcome including a
failure — which is exactly what keeps a half-finished install from
leaving behind a machine that boots its installer forever. The
shipped `freedos` blueprint and its install script are a working
example of this pairing. Declaring `["cdrom0", "hdd0"]` directly in
the blueprint is still the right call for a machine whose actual
*job* is to boot an optical drive first.

Backends also differ more generally in how faithfully they honor a
multi-entry boot order; a backend that can't honor the declared
order reports a capability error, rather than silently booting from
something else instead. That check only covers what a backend can
*express* as a boot order, not what its firmware actually does when
a device turns out not to be bootable — which is why the table
above is a caution, not something Reliquary refuses to let you do.

---

## `control-planes`

**blueprint (optional) · array of strings**

An ordered list of which control planes Reliquary is allowed to use
for guest-facing operations on this machine, in order of
preference. **The first entry is what actually drives the run** —
the session's screen and keyboard both come from whichever plane is
listed first — and Reliquary never uses a control plane that isn't
in this list at all. Entries have to be unique — listing the same
control plane twice fails validation.

Working name set:

| name                | mechanism                                  | built |
|---------------------|--------------------------------------------|-------|
| `agentless-display` | keyboard injection + screen readback; no guest cooperation needed | yes |
| `vnc`               | framebuffer and input over VNC             | on QEMU |
| `serial-console`    | text console on an emulated serial port    | no    |
| `guest-agent`       | structured agent protocol (QGA profile)    | no    |

These names are the model's entire vocabulary, and the parser
accepts all of them — but whether a given plane can actually be
honored depends on the assigned backend. So `create-machine` and
`apply-blueprint` refuse a policy naming a plane the backend can't
provide, rather than record a policy nothing can actually honor.
`vnc` is served by QEMU: the machine starts with a loopback VNC
server that QEMU itself provides, the screen is read off the
framebuffer through the same fixed-font recognizer used elsewhere,
and keys arrive as VNC key events — nothing changes inside the
guest, so this plane is just as agentless as the default one. A
plane no backend has built yet (`serial-console`, `guest-agent`) is
refused everywhere, on every backend. Listing a plane that works
alongside one that can't be honored doesn't excuse the one that
can't — the policy has to be entirely made up of planes Reliquary
is actually able to use.

Defaults by platform (DOS: `["agentless-display"]`); the resolved
default shows up in the state. A backend that can't provide a
listed control plane fails its capability check (for example, `vnc`
on VirtualBox today).

```json
{"control-planes": ["vnc"]}
```

This selects the VNC plane end-to-end on QEMU: the same script now
drives the machine over the framebuffer instead of scraping the VGA
text screen. This ordering also anticipates a fallback shape —
`["guest-agent", "agentless-display"]`, meaning *try the agent, and
fall back to the display* — which will work once a plane that can
actually be "not ready yet" is built, along with the readiness
check to fall back from it. For now, the first entry in the list is
the only one that matters.

---

## `backend-settings`

**blueprint (optional) · object**

This is the escape hatch for backend-specific configuration —
explicitly scoped, and explicitly not portable. It's one object per
backend name; only the section matching the machine's actual
`backend` applies, and the other sections just sit there unused but
preserved. When the blueprint doesn't declare
[`backend`](#backend) explicitly, the sections present also steer
the default assignment: settings for exactly one backend narrow the
assignment walk down to that backend automatically. For example:

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

- This is the **only** place backend-specific configuration is
  allowed to appear. A blueprint with no `backend-settings` section
  is portable automatically.
- Settings can't touch anything Reliquary already owns through its
  regular fields — memory, drives, boot order, CPU count, machine
  identity. Each backend adapter validates its own section and
  rejects any overlap with those.
- The keys allowed in each backend's section are defined and
  documented by that backend's own adapter. A key the adapter
  doesn't recognize is refused when the machine is materialized,
  and the error names the keys that backend actually does define —
  settings are never silently carried into the state and then just
  ignored.
- Only the section for the **assigned** backend is validated. Every
  other backend's section is kept exactly as written and never
  examined — no adapter can speak for another adapter's vocabulary.
- A section that passes validation is a section that gets applied.
  Whatever `create-machine` accepts is exactly what every
  `start-machine` afterward applies.

### `qemu`

The one built adapter's vocabulary:

| key | value | becomes |
|---|---|---|
| `machine` | a QEMU machine type | `-machine <value>` |
| `args` | array of arguments | appended verbatim |

The values are entirely yours to choose: Reliquary doesn't check
whether QEMU actually has the machine type you named, or
understands the arguments you gave it — QEMU itself refuses
whatever it doesn't recognize, and that refusal is yours to read
and act on. What Reliquary *does* check is which keys are allowed,
each key's shape, and whether anything overlaps with a field
Reliquary already owns. These arguments are refused outright, each
one naming the field that already owns it:

| refused | owned by |
|---|---|
| `-m` | [`memory`](#memory) |
| `-smp` | [`cpus`](#cpus) |
| `-boot` | [`boot`](#boot) |
| `-drive`, `-hda`…`-hdd`, `-fda`, `-fdb`, `-cdrom` | [`drives`](#drives) |
| `-set drive.<slot>.<property>` for a property `drives` renders (`file`, `if`, `index`, `media`, `id`, `format`, `bus`, `unit`) | [`drives`](#drives) |
| `-machine`, `-M` | this section's own `machine` key |
| `-name`, `-uuid`, `-qmp` | the recorded VM identity |
| `-display`, `-nographic` | the display choice a start is given |

An option written with its value packed into one array element
(`"-m 64"`) is caught the same way as if it were split apart. Two
arguments people often expect to be refused are **not**: `-device`
is the documented way to ask for a QEMU device — backend-specific
hardware has no dedicated field of its own (P25), so this escape
hatch is exactly where you ask for one — and `-cpu` selects a CPU
*model*, where the `cpus` field only owns the count.

One of those field owners doesn't actually deliver on what it owns
yet: the QEMU adapter renders **no** `-smp` at all, so a
[`cpus`](#cpus) value above 1 is resolved into the state but not
actually applied when the machine launches. `-smp` is still refused
in `backend-settings` regardless — the CPU count belongs to the
first-class field, wherever it ends up being honored, and having a
second way to set it through the escape hatch would just have to be
undone the day the adapter starts rendering it properly. Closing
that gap is the adapter's job, not something to work around through
`backend-settings`.

**Settings for one specific drive** are reached through QEMU's own
per-drive addressing rather than a dedicated drive-scoped section
(D118): every drive Reliquary renders carries `id=<slot>` —
`hdd0`, `cdrom0`, `floppy0` — so `-set drive.<slot>.<option>=<value>`
sets an option on exactly that one drive, after the `-drive`
argument that originally defined it. The properties that `drives`
itself already renders are refused through `-set` the same way
`-drive` itself is refused (see the table above); everything else —
`cache`, `aio`, `discard`, `serial`, and so on — is yours to set,
and QEMU refuses an option it doesn't recognize by name, or a value
this host can't honor (`cache=none` asks for unbuffered I/O that a
qcow2 file on Windows can't provide, and QEMU reports that against
the drive):

```json
{
  "backend-settings": {
    "qemu": { "args": ["-set", "drive.hdd0.cache=writethrough"] }
  }
}
```

This section renders **last**, after everything Reliquary itself
owns — so in the launch command line Reliquary logs, your own
arguments are always at the tail end. That ordering is also what
lets `-set` find the drive it's targeting.

---

## Validation summary

Format checks reject the document outright when they find:

- an unknown top-level key, an unknown drive key, or a malformed
  value;
- a slot clash (the shorthand and indexed form of the same slot
  both declared) or a slot number out of range;
- a state-only field (`backend-id`, `blueprint-digest`,
  `blueprint-source`) showing up in a blueprint;
- a `boot` entry naming an undeclared or disabled drive, the same
  slot named twice (in either spelling), or a duplicate
  `control-planes` entry;
- a drive object missing `media`, or carrying keys other than
  `media` / `controller` / `enabled`;
- a `null` (empty) value on a non-removable (`hdd`) drive;
- a `media` name that no media component provides (plus every
  media / source / archive rule in
  [the media spec](spec/media-spec.md));
- a `cdrom` drive naming a media that isn't read-only `use`;
- a `parameters` value that's neither a string nor a
  `{"property": "<key>"}` object, or one with an invalid key or
  property name.

Capability checks reject the blueprint for *this particular
backend*, naming both the backend and the capability it's missing,
when it asks for:

- media the backend can't provide (an unsupported medium, or too
  many slots of one);
- a controller type the backend can't provide (for example,
  anything but `scsi` on a Hyper-V Generation 2 machine);
- a `difference` media the backend/format combination can't
  express;
- a directory-source media the backend can't serve;
- an image format the backend can't attach;
- a control plane the backend can't offer;
- a boot order the backend can't honor;
- a `backend-settings` key the assigned backend doesn't define, or
  one of its arguments that restates a field Reliquary already
  owns.
