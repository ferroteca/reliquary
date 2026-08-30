<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# The composed blueprint model

> **Status:** the worked design of the composed blueprint model,
> **normative** for the format milestone 7 implements. It folds
> four decisions into one document — D22 (the blueprint revision
> round), D24 (the reference grammar battery), D26 (the reach
> trim and the string-grammar closure) and D27 (the corrected
> closure test) — and replaces this file's superseded first-round
> shape entirely. Where it and those entries differ, this
> document governs; where it is silent, they remain the record.
> The **implemented** surface is still described by
> [blueprint-guide.md](../blueprint-guide.md), its
> [field reference](../blueprint-reference.md), and
> [media-spec.md](media-spec.md) — those realign to this model at
> milestone 7's deliverable 7, and until they do they describe
> the pre-composition formats, not this one.

Reliquary has one authored JSON kind: the **blueprint**
(`.rlqb`). It holds **specs** of two types — `machine` and
`media` — and nothing else. `.rlqm` retires; the separate
`source` and `archive` types of the first round are gone, the
first absorbed into a media's `location` and the second into
parent/children containment, because the archive/media
distinction was never a property of the artifact, only of the
use. Scripts (`.rlqs`) and landmark declarations (`.rlql`)
remain their own kinds.

The format is deliberately **logic-free**, and that will not
change: P14 limits what the format may express, and this
document states that limit as a closed grammar instead of
leaving it to judgment. See
[Format stability](#format-stability-none-yet)
for the rule on how the format is allowed to grow; this document
states the grammar that rule closes.

## The file

A `.rlqb` root is an **array of specs**:

```json5
[
  { "type": "machine", "name": "freedos", "platform": "dos", … },
  { "type": "media", "name": "freedos-livecd", … }
]
```

A **lone spec object** is accepted as pure sugar for the array
of one, under exactly the same rules:

```json5
{ "type": "machine", "name": "freedos", "platform": "dos", … }
```

The first round's plural component sections
(`machines`/`media`/`sources`/`archives`) are retired, and with
them the historical **bare-root-machine** reading: a root object
carrying no `type` is a *media*, not a machine, because `type`
defaults to `media` everywhere (below). A blueprint whose lone
machine forgets `"type": "machine"` therefore fails in the media
branch — and that branch's unknown-field error carries a
**did-you-mean** hint when machine vocabulary (`platform`,
`devices`, `boot`, `scripts`, …) appears, so the diagnosis is one
line rather than a puzzle.

A root array element that is a **bare string** is a media
desugaring to `{ "location": <string> }` — see
[the string-position table](#strings-are-interpreted-objects-are-explicit).
It is invalid where the location kind demands a pin: a bare URL
string fails closed naming the object form, since a remote
payload needs a `sha256` it has nowhere to put.

JSON5 is accepted ([spec.json5.org](https://spec.json5.org)):
comments, trailing commas, unquoted keys, single-quoted strings,
hexadecimal and signed numbers, and the rest of that grammar.
`NaN`, `Infinity`, and `-Infinity` are refused — parsed blueprint
values remain ordinary JSON data. Every machine-written file stays
strict JSON. There is no `$schema` or version field pre-1.0.

## Spec types

`type` is **optional and defaults to `media`**. A machine
declares `"type": "machine"`; a media may declare its type or
leave it out. Mandatory-everywhere was argued and declined:
blueprints are small, and loose typing wins on convenience at
this scale. The **codex and the shipped examples always write
`type`** — model good code, do not enforce it.

An optional `type` at a **nested** position (a `children` entry,
an inline media at a drive, an inline parent) is a **checked
echo**: it may be written, and a mismatch with the position's
required type is an error.

### machine

Topology only — no content lives here. `platform` (required,
never inferred — P10), `backend`, `memory`, `cpus`, `boot`,
`control-planes`, `pointing-device`, `devices`, `backend-settings`,
`description`, `scripts`, `parameters`, and `name`.

`devices` maps a slot key (`hdd0`, `cdrom0`, `floppy0`, `net0`,
`share0`, …) to a drive, a NIC, or a share — the three kinds share
one map and one key-clash check, discriminated by the key's own
medium (D121). A drive value is one of:

- a **media name** (string) — the catalog reference;
- **`null`** — a declared but empty removable slot a script
  fills;
- an **object** carrying hardware attributes (`controller`,
  `enabled`) plus `media`;
- an **inline media spec** — a full media written in place, or
  the blank `{ "size": … }` (`size` implies `materialize: new`).

The first round's four-way content selector (`size` / `base` /
`media` / `hostdir`) is gone. A media name is the machine's one
cross-boundary reference: **to change how a drive materializes,
change the media, or point the drive at a different one.** A NIC
value is described below, under `net` keys, and a share value under
`share` keys (F68).

#### What the topology fields mean

The schema fixes each field's shape; these are the rules a schema
cannot carry.

- **`name`** follows the name charter below with one added
  clause: a machine name is **never all digits**, because it
  becomes an id segment in `<name>-<n>` and `42-0` would not read
  as the pair it is. Media names carry no such restriction.
- **`memory`** is a size string or an integer, and **a bare
  integer means MiB** — `32` and `"32M"` are one declaration. A
  size string uses the media `size` grammar (a positive integer
  with a binary `K`/`M`/`G`/`T` suffix), which admits no bare
  form, so this clause is what makes the integer legal. The value
  must resolve to a **whole number of MiB**: the state carries the
  canonical integer form, so `"1500K"` is refused rather than
  rounded. Omitted, it takes the platform's default — dos 16,
  openbsd 512, win9x 64, winnt 256.
- **`cpus`** defaults to 1.
- **device keys** name a medium and a slot (`floppy` 0–1, `hdd`
  0–3, `cdrom` 0–3, `net` 0–3, `share` 0–3), all sharing one
  keyspace and one clash check (D121) — declaring `hdd0` and `net0`
  in the same `devices` map is fine, but naming one slot twice, in
  either spelling, is a **clash** and fails validation, as does a
  slot outside its medium's range. Only drive keys (`floppy`/`hdd`/
  `cdrom`) get the **bare-medium-is-an-alias-for-slot-0** shorthand
  (`hdd` ≡ `hdd0`); a NIC or a share is always named by its full
  slot key. The state always records the indexed form.
- **`controller`** is valid on `hdd` and `cdrom` only — a floppy
  attaches to the floppy controller implicitly and **rejects the
  key**. Omitted, it resolves to `ide`, recorded into the state at
  creation.
- **`net` keys** (D120) name a NIC's **attachment**: either
  an attachment name (string) — `nat` or `bridged` — or an object
  carrying `attachment` plus optional `interface` (`bridged` only)
  and `model`. The choice of `nat` vs. `bridged` is orthogonal to
  platform, so it's always author-stated; which chipset is emulated
  is resolved per platform when `model` is omitted, the same way a
  controller default is — but naming `model` explicitly overrides
  that default (D122), the same test `controller`'s `nvme`/`virtio`
  values already pass (above): a name only needs to be real,
  general hardware, not honored by every backend today. `pcnet`
  (AMD's Am79C970A, "PCnet-II") runs on both QEMU and VirtualBox;
  `ne2k` (Novell/Eagle NE2000) and `virtio` (QEMU's paravirtualized
  NIC, `virtio-net-pci`) only exist on QEMU today, checked and
  refused by name on any other backend at materialization.
  `interface` names the host network interface to bridge onto,
  taking a plain string or a `${key}` reference bound the same way a
  media `location` is — a host interface name is exactly the kind of
  host-specific fact a shared blueprint shouldn't hardcode (U21).
  Omitted, `bridged` uses whatever the backend does with no interface
  named: on VirtualBox this is that adapter's own default; on QEMU,
  which attaches to an existing Linux bridge device rather than a
  physical interface directly, this means the conventional bridge
  name `br0` — Reliquary does not probe the host for one, so a host
  with no `br0` fails at QEMU's own launch, not at a Reliquary
  preflight (T32 tracks adding host detection later). Each attachment
  is still capability-checked against the assigned backend at
  materialization, failing closed and naming both (P11) — what isn't
  checked is whether a *named* interface or the default bridge
  actually exists on this host, which stays the backend's own error
  to raise. No `net` keys in `devices` means the machine has no NIC
  at all.

  Attachment and chipset are two different questions — whether the
  guest can reach anything at all, versus which driver it needs —
  and D120 kept the first one always-authored while D122 made the
  second one authorable only when it actually matters, defaulting
  otherwise.
- **`share` keys** (F68) name a host directory presented to the
  guest for file exchange, for as long as the machine runs: a
  media name (string) — the catalog reference to a directory-payload
  media — an object carrying `media` plus optional `model` and
  `enabled`, or an inline media spec — a full media written in place,
  the same shape a drive accepts, except a share never admits the
  anonymous blank: an inline share medium must still resolve to a
  named, materializable directory. `model` and `enabled` are share
  attributes, pulled off the object before the rest of it is read as
  a media reference or an inline spec, so both compose with either
  form — `{"location": "D:/exchange", "model": "9p"}` names a path
  and a model in the one object (F72). No `null` form either way: an
  empty drive bay is real hardware, but a share with no directory
  means nothing. The referenced media's
  `materialize` must be `use` — a share presents the directory in
  place, never as a per-machine image — and it must resolve to a
  directory: a share whose media resolves to a file fails closed
  naming the path, and, symmetrically, a drive slot whose media
  resolves to a directory now fails closed too (a directory payload
  is legal only on a share). `model` names the live mechanism
  (`vvfat`, `9p`, or `virtio-fs`), capability-checked against the
  assigned backend the same way a NIC's `model` is (D122): honored
  where the backend's capability report claims it, refused by name
  otherwise. Omitted, an unstated `model` means the assigned
  backend's own default live mechanism — **never** silently `vvfat`,
  which only ever arrives by name. Which mechanisms a backend
  actually offers, and what its default is, is a capability fact
  reported at assignment, not fixed here — see
  [share-devices.md](../../planning/pledged/design/share-devices.md)
  for the full argument, the per-backend mechanisms, and the guest
  driver each one needs. A `${key}` location binds the same way a
  drive media's does (U21). `share` keys are refused in `boot`, the
  same way `net` keys are: nothing boots from a shared directory, and
  `insert-media`/`eject-media`/`set-boot-order` and the script's
  `with boot`/`insert`/`eject` don't apply to a share — those stay
  drive-only.
- **`boot`** entries must each name a drive the machine
  **declares and has not disabled**, and are unique by slot: the
  same slot twice, in either spelling, fails validation. An empty
  or non-bootable drive is a **valid** entry: whether firmware
  moves past one depends on the firmware, not on this model, and
  firmware does not behave uniformly — an empty optical drive is
  skipped everywhere, but a disk partitioned without an active
  partition is not. So a blueprint that carries an installer
  states the install medium **first** in `boot`, and its script
  ejects that medium once the disk is ready (the measured table
  of what each firmware does is in the blueprint reference).
  Writing an order that depends on the firmware falling through
  to a later entry means relying on host firmware behavior that
  is not guaranteed. Omitted, the order is the slot-0 floppy,
  else the slot-0 hard disk, else the first cdrom; the resolved
  order is recorded.
- **`control-planes`** is an **ordered preference**. Entries must
  be unique — listing one twice fails validation — and **the
  first entry drives the run**: the session talks to the guest
  using whichever carriers that first listed plane provides.
  Every entry must appear in the assigned backend's capability
  report, or materialization fails closed naming the plane and
  the backend (P11): `control-planes` records every plane
  Reliquary is allowed to use, so recording a plane the backend
  cannot actually check would leave the saved state claiming
  something false. The field accepts the model's whole
  vocabulary of planes — the parser does not reject any of
  them — but whether a given plane actually works depends on the
  backend: `vnc` is served on QEMU and refused on a backend that
  can't provide it, and a plane no backend has built yet is
  refused everywhere. Omitted, it resolves to the platform's
  default, which is `["agentless-display"]` for every platform
  today — the one plane that works everywhere because it needs
  nothing installed or running in the guest. Defaults that differ
  by platform will arrive once a platform has planes that justify
  a different default.
- **`pointing-device`** (F66) is `tablet` or `mouse`, judged the
  same way as `control-planes`: capability-checked against the
  assigned backend at materialization, failing closed naming both
  the backend and the device. An absolute event needs an absolute
  device — a PS/2 mouse is relative and the guest's own driver
  applies acceleration the host cannot observe (P10) — so `click`
  preflight-refuses a `mouse` machine by name rather than
  attempting a calibration guess. Omitted, it resolves to `mouse`
  — the plain relative device every platform's machine has
  anyway, so the default matches what's actually there rather
  than assuming something better. A GUI-era platform will get a
  richer default once it has one to justify it, the same way
  `control-planes` will.
- **`backend-settings`** is the **only** place backend-specific
  configuration may appear, which is what makes a blueprint
  without it portable by construction. One section per backend
  name; only the section matching the machine's backend applies,
  and the others are inert but preserved.

  **The applying section is honored, and three rules bound it.**
  First, **the keys are the adapter's own vocabulary**: each
  backend defines the keys its section may carry and refuses any
  other by name, so a misspelled or invented key fails at
  materialization rather than being carried into the state and
  silently ignored (P11). An adapter that reads no settings
  defines no keys, and therefore refuses every one. Second, **a
  section may not touch what Reliquary already owns** through
  first-class fields (memory, devices, boot order, CPU count) or
  through the recorded VM identity — the adapter refuses that
  overlap in its own configuration language, because
  `backend-settings` exists to carry backend-specific
  configuration, not to give one fact two different places to be
  set. Third, **the section that validates is the section that
  renders**: what `create` accepts is exactly what `start`
  applies.

  Only the assigned backend's section is checked, because no
  adapter can validate another backend's vocabulary — which is
  also why an inert section is kept as-is without being checked.

  **A `backend-settings` section can narrow which backend gets
  picked.** Where a blueprint declares no `backend`, and it
  carries a `backend-settings` section for **exactly one**
  backend, Reliquary picks that backend instead of trying the
  usual priority order (ARCHITECTURE.md, "The seams" —
  installed backends are tried QEMU, then VirtualBox, then VMware
  Workstation, then Hyper-V). That pick then fails closed if the
  named backend is unavailable or can't handle what the machine
  needs, naming the section that forced the pick. A blueprint
  carrying one section has already said which backend it's
  written for, so trying a different backend that could never
  apply those settings would mean ignoring what the blueprint
  said. Two or more sections narrow nothing: each stays inert
  until its own backend wins the ordinary priority-order search.
  **What narrows the pick is the section being present, not what
  it contains** — an empty section names its backend exactly as a
  full one does. A `backend` field written explicitly always
  outranks this narrowing.

### media

A media owns all content and materialization.

- **`name`** — explicit, or derived from content; or absent, for
  the anonymous blank alone. See [Identity](#identity-and-the-catalog).
- **`materialize`** — `new` · `difference` · `copy` · `use`,
  default `use`:

  | value | meaning | needs |
  |---|---|---|
  | `new` | fresh blank image of `size` | `size`; **no** `location` |
  | `difference` | writable overlay over the payload (payload untouched) | `location` |
  | `copy` | payload duplicated into a standalone image | `location` |
  | `use` | attach the payload itself (mutable unless `read-only`) | `location` |

- **`size`** — `new` only (`"20M"`, `"1440K"`). A spec carrying
  `size` and no `location` **is `new`**, whether or not it says
  so: there is nothing else it could be, which is what lets the
  drive-inline blank be written `{ "size": "20M" }`. Writing
  `materialize: new` beside it is legal and checked, and the
  codex and examples write it.
- **`location`** — where the payload comes from. One field, one
  grammar: [The location grammar](#the-location-grammar).
- **`sha256`** — the payload's hash, verified on every use.
  **Required once any of the location's entries is remote**
  (checked at resolution, not parse — see
  [Two-phase validation](#two-phase-validation)), optional for
  local and derived payloads. Being optional here is deliberate: a
  local media may leave `sha256` out so you can attach a drive
  image that is still being actively edited, where a pinned hash
  would fail every time the image changes. A hermetic workflow —
  one that wants a fully reproducible, pinned build — adds the
  hash when it wants that guarantee. The hash pins the build
  regardless of where the payload comes from — even a trusted
  local payload can use it to verify it is the exact build the
  scripts target (U4).
- **`read-only`** — present the drive (or share, F68) read-only.
  Orthogonal to `materialize`. **Defaults true on a cdrom** (no
  backend meaningfully emulates writing a virtual ISO; a writable
  cdrom is rejected); opt-in elsewhere. On a directory payload —
  legal only on a share now — it protects the host directory.
- **`extension`** — override the type-declaring extension of the
  cached payload when the source filename misnames or omits it.
  Otherwise derived from the location's filename or path.
- **`children`** — containment sugar; see
  [Containment](#containment-parent-and-children).
- **`description`**, **`notes`** — prose.

**A host directory is a payload shape, not a mode:** `use` covers
"attach this file" and "attach this directory" alike — the media
model doesn't distinguish them. Which *device* a directory payload
may attach to is a separate rule, and it changed under F68: a
directory is legal only on a `share` slot now, where it becomes a
live shared filesystem; a drive slot (including a cdrom) whose media
resolves to a directory is rejected at resolution. See the `share`
keys bullet above and
[share-devices.md](../../planning/pledged/design/share-devices.md)
for what a share actually does with it.

## Identity and the catalog

Every named spec lands in **one global catalog**, and identity
is the pair **`(name, type)`** — a media named `dos622` and a
machine named `dos622` coexist, because every reference is
type-directed.

**Having a name is what makes a spec a member of the catalog.**
A spec either has a name — given explicitly, or derived from its
own content — and belongs to the catalog, or it is the one kind
of spec allowed to have no name at all (the anonymous blank,
described in [The anonymous blank](#the-anonymous-blank) below),
which belongs to no namespace.

### The name charter

A name is checked against one production:

```ebnf
media-name = ( letter | digit ) , { letter | digit | "." | "_" | "-" } ;
```

This is the script language's `name` production, with one
change: a leading digit is now allowed. The script language
splits `name` from `property-key`, which must start with a
letter, and that split matters here only in one direction. A
media name is never written bare — it always appears inside a
marker: `@name` in scripts, or a plain JSON string in
blueprints — so a leading digit never causes ambiguity for a
media name. A property key, by contrast, is sometimes written
bare at a declaration site, and there a leading digit would be
read by the parser as a duration (like `5m`) instead of a key.
That is why `property-key` must stay letter-initial while
`media-name` does not have to. So `86Box` is a perfectly good
media name.

Some characters are forced out regardless of any of this:
whitespace, `{`, `}`, `#`, and `/` (which is reserved as the
containment separator — `${media:C:/x}` would otherwise be
ambiguous), plus control characters. **A machine name has one
rule more than a media name**: it may never be all digits, since
it becomes the `<name>-<n>` id segment, and `42-0` would not
read as the pair it is. Otherwise the rules are the same for
machine and media names. Parentheses and brackets are excluded
for a different reason — **the command line, not the name
grammar**: every media name is used as a command-line argument
to `fetch-media`, `add-media`, and `clean-media`, and
`rlq fetch-media FD(1)` is a shell syntax error just as
`FD[1]` is. A name that needs shell-specific quoting is a small
but permanent annoyance that P7 rules out, and brackets would
also make a name behave like a glob pattern over
`cache/media/`, on top of that.

### Derivation, repair, and failure

A spec without an explicit `name` derives one from
**content-intrinsic material** — a URL or path stem — never from
the slot it sits in and never from the `.rlqb` file's own stem.

The sanitizer **repairs the character set; it never invents a
name.** A stem outside the charter is repaired and **warned**,
naming both the derived name and the source it came from
(`FD 1.4 (final).zip` → `FD-1.4-final`). Where repair cannot
yield a legal name — the stem is empty, or repairs to nothing —
or where there is **no stem to derive from at all** (a `${…}`
location, a reference-bearing path suffix, a mirror list whose
first entry is a reference), it **fails closed demanding an
explicit `name`**. The derived key must be visible to the author
who will later type `@name`, which is why silent sanitization
was declined.

Two sources sanitizing to one name still meet the duplicate-name
rules below, so a repair can hide nothing.

### Case

Names **match case-sensitively and collide
case-insensitively**. `cache/media/` is name-keyed on
filesystems that are not, so `FDBOOT` and `fdboot` in one source
are a collision error naming both, while references still bind
exactly.

### Duplicates: dedup, collide, or error

- **Identical** specs of the same `(name, type)` — canonically
  equal — **coexist**. This is what lets self-contained
  blueprints be pasted around freely.
- **Differing** specs of the same `(name, type)` **collide**,
  naming both files.
- **In-file duplicates always error**, identical or not.

Composing a spec — merging fragments of it across files — was
considered and **declined**: it would only have been a second
version of the property mechanism that already exists for
supplying personal values and secrets (see
[blueprint-guide.md](../blueprint-guide.md)). Instead, when you
need to supply your own value, you either **edit your own seeded
copy of the blueprint directly** (at home) or **supply the value
through a property** (in a project or in CI).

### The anonymous blank

The content-free blank — a drive-inline `{ "size": "20M" }` — is
the **only spec allowed to have no name**: it belongs to no
namespace, is identified only by where it is written, is named
for its **slot** once materialized, and cannot be referenced
from a script. It has no content to derive a name from and no
reason to be shared; everything else must be named. Giving
anonymous specs a name scoped to just their own document was
considered and declined — anonymous means the spec has *no
name*, not that its name is *private* to that document.

## Resolution

Resolution reads **every `.rlqb` in the blueprints directory**,
walked recursively — the home directory's blueprints folder by
default, or a project's own tree where `--blueprints-dir` points
there instead — into one catalog, then binds every reference by
name. Where blueprints live still works the same way it always
has: the home directory for the CLI's convenience, a project's
own tree for automation (P4). What's new is that this is now
absolute: if a name isn't found, resolution never falls back to
the codex, on either the CLI or the API.

Resolution is **order-independent** and forward references are
legal. Containment cycles and a self-parent fail closed naming
the cycle.

**Selection.** `--blueprint <name>` selects the **machine** of
that name; a machine id is `<name>-<n>`.

## Containment: parent and children

Any media may declare **`children`**, and any media may declare
its **`parent`** from the child side. These are one semantic
with two spellings:

> **Every containment edge resolves to child-declares-parent.**
> `children` is pure sugar.

A `children` entry is a media spec **declared in place**, in
**path form only** — it carries no `location` key, because its
location is its parent plus its path — and a **bare string entry
is the path**. It desugars to a standalone spec with a parent
location. Because the identity rules are position-independent,
a spec written as a child and the same spec written standalone
are the same spec.

```json5
[
  { "type": "media", "name": "freedos-livecd-zip",
    "location": "https://download.freedos.org/1.4/FD14-LiveCD.zip",
    "sha256": "2020ff…",
    "children": [
      { "path": "FD14LIVE.iso", "name": "freedos-livecd",
        "read-only": true, "sha256": "c48a9d…" }
    ] }
]
```

The same graph, written from the child side:

```json5
[
  { "type": "media", "name": "freedos-livecd-zip",
    "location": "https://download.freedos.org/1.4/FD14-LiveCD.zip",
    "sha256": "2020ff…" },
  { "type": "media", "name": "freedos-livecd", "read-only": true,
    "location": "${media:freedos-livecd-zip/FD14LIVE.iso}",
    "sha256": "c48a9d…" }
]
```

Nesting has no depth limit and needs no special chaining syntax:
a child that is itself a container simply has `children` of its
own. If just one ancestor high in the tree is remote, it
downloads once; every descendant below it is then extracted from
that cached copy.

**Whether a media gets mounted or extracted from is decided by
where it's referenced, not by anything in the spec itself.** A
drive, or a script's `insert`, **mounts** a media. A `parent`
location, or walking a `children` list, **extracts** from it.
Both at once are fine and unremarkable — the same ISO can be
mounted at `cdrom0` and also read as a container for its boot
floppy; it's the same media used two different ways. This is why
the old separate archive type could be folded into media: it was
describing a use of a media, not a different kind of artifact.

**Reading into a container only works for formats Reliquary
supports.** Milestone 7 supports **zip** only; trying to read an
unsupported container format fails closed, naming the format it
found. Reading ISO9660, including its `[BOOT]` El Torito virtual
paths, is planned as a follow-on; reading filesystem images at
all is out of scope before beta.

A **path glob** in `children` was declined: names must be
static, because the catalog can never depend on a download (G3).

## The location grammar

One field, `location`, and one rule applies to it everywhere it
appears:

### Strings are interpreted, objects are explicit

**Every string form has exactly one equivalent object form**, and
that object form is the canonical one — it's what the machine
state records, what the embedding API emits, and what you write
instead whenever a string would be ambiguous. The object form is
also where extra options live: any attribute with no string
spelling can only be set there.

Strings are interpreted **by position**:

| position | a string means | desugars to |
|---|---|---|
| at a drive | a media name | `{ "media": … }` |
| at a spec position | a location | `{ "location": … }` |
| in `children` | a path | `{ "path": … }` |

And a location string is interpreted **by scheme**:

| string | meaning | object form |
|---|---|---|
| `FD14LIVE.iso` | path, relative to the referencing file | `{ "local": … }` |
| `https:…` / `http:…` | a download | `{ "url": … }` |
| `${media:<name>}` | the parent's own bytes | `{ "parent": "<name>" }` |
| `${media:<name>/<path>}` | a member of the parent | `{ "parent": "<name>", "path": "<path>" }` |
| `${<key>}` | a property-supplied location | `{ "property": "<key>" }` |

The object forms are `url`, `local`, `parent` + `path`, and
`property`. **`parent` takes a media name or an inline media
spec**, so a container that exists only to be descended into
need not be named separately.

A string that **looks like a scheme but is not recognized** is a
parse error rather than a silently-relative path, with a
single-character **drive-letter exemption** so `C:/isos/x.iso`
reads as a Windows path. `file://` was declined: bare paths
already carry relative resolution, and RFC `file:` is
absolute-only.

### Mirror lists

A location may be a **list** of locations, tried in order, and
the entries can mix schemes freely — what decides whether the
payload is correct is the hash, not which URL supplied it. A
**one-element list is simply the scalar value** (no special
handling needed), an **empty list is an error**, and **nested
lists are illegal**. `sha256` is required once any entry in the
list is remote.

## The universal reference

`${…}` is the one reference syntax, everywhere.

- **Unqualified** `${a.b.c}` ≡ `{ "property": "a.b.c" }` — one
  spelling shared with the script language and with milestone
  8's derivation grammar.
- **Qualified** `${media:<name>}` reads the catalog. A **bare**
  `${media:X}` is a legal whole location meaning the parent's
  own bytes — which is how `materialize: difference` puts an
  overlay over another media. With a suffix,
  `${media:<name>/<path>}` is the containment location; the path
  is the **second component of one reference**, never string
  interpolation — which is why it lives *inside* the braces, where
  the closure can see it (D32).

Property binding itself lands at **milestone 8**. Until then a
`${key}` reference parses and then **fails closed naming
properties** — never naming a milestone number.

### Reach: where a reference may appear

An **unqualified** reference interpolates **anywhere a string
value is accepted**, exactly as the script language already
allows, including inside object field values. The escape is
**`\${`** — identical to the script spelling, written `"\\${"`
in JSON — because prose fields and direct `parameters` values
have no object form, and a parameter carrying a literal
`${HOME}` into a guest config file is an ordinary case.

A **qualified** reference is **whole-value only**: it desugars
to an object, and a media reference embedded in prose is
meaningless.

Two exclusions, and they have different grounds:

1. **Identity and resolution structure.** `name`, `type`,
   `children` paths, and object keys (drive slots) never take a
   reference. The catalog and the authored graph stay static
   (G3) — the same ground that killed the `children` glob.
2. **Closed vocabularies.** `platform`, `backend`,
   `materialize`, `controller`, `control-planes` items, and
   `pointing-device` never take a reference. These are where a
   published schema's
   completion is most valuable and where a reference destroys
   it (U4, U5), and they have no named case asking for one.
   `platform` is the sharpest instance: P10 has it never
   inferred and always from the blueprint, and a `${…}` platform
   is a runtime-decided platform in all but name.

Everything else a scalar position accepts may be referenced:
`location`, `parameters` values, `description`, and the open
numerics `memory`, `cpus`, `size`. **`sha256` stays
interpolable** — a hash is not a closed vocabulary, and
excluding it would buy nothing, since what pushes the
required-once-remote check to resolution time is a *referenced
location entry*, not the hash field.

Reach is **asymmetric**: widening it later is compatible,
narrowing it is not. That is why these exclusions are stated
before the parser exists, and why reach is a design call that
may be revisited on a named case — unlike the grammar below.

### Resolution order

**Interpolate, then scheme-dispatch the result. Resolved text is
never re-scanned.** A property whose value happens to read
`${media:X/p}` stays literal text and fails the scheme check —
this is the no-chaining rule made precise.

### The path suffix

The path lives **inside the braces**, after the media name:
`${media:<name>/<path>}`. Exactly **one `/`** separates name from
path — the first one; every later `/` belongs to the path. Member
paths are `/`-separated always, following the container formats'
own convention. The path normalizes, and `..`, absolute paths,
and empty segments are **refused as containment escapes**. A
backslash anywhere in the body is an error naming the `/` rule —
the mistake a Windows-using author is likely to try first — and
trailing or doubled slashes are also errors.

The path lives inside the braces, not after them, so that **the
closure test can see the whole location** (D32): a qualified
reference is whole-value, and with the path inside, "whole-value"
means the string is *exactly* one reference with no trailing text
left over to disambiguate. This is also the reason the character
class includes `/` at all.

### The closure: operations closed, namespaces open

The `${…}` body is **closed**, permanently, and the test has two
halves. Neither alone is sufficient:

1. **The character class screens.**

   ```
   ^\$\{[A-Za-z0-9._:/-]+\}$
   ```

   Every character in it is load-bearing: `:` separates the
   qualifier, `/` separates the containment path, `.` carries
   the property dot-path and is legal in a media name, `_` and
   `-` are charter characters. The class catches `|`, `(`, `[`,
   `?`, `=`, and whitespace.

2. **The productions decide.** The body must be **one of the two
   productions** — qualified `qualifier:media-name[/path]`, or a
   dotted property key — and *neither has a position an operator
   could occupy*.

The second test is not there just for show. `${mem:-512M}` — the
most likely request anyone will ever make — is built **entirely
from legal characters** and passes the character class; it is
refused because the text before the first colon is read as the
qualifier, and `mem` is not a known qualifier. If the stated test
were wrong in some way that let this pass, it would let in
exactly the feature the closure exists to keep out.

**Closed permanently:** every operator — defaults (`${key:-x}`),
pipes and filters, calls, indexing, arithmetic, comparison,
ternaries, nesting (`${${a}}`), and any second escape character.
A proposal for one of these is a signal that what's wanted is a
whole new authoring layer on top of blueprints, never an
extension to this grammar — see
[When it is time for a layer](#when-it-is-time-for-a-layer)
below. Each such feature would only ever be added once a real
user has a genuinely good case for it — and that is exactly the
trap: justifying each feature individually, one at a time, is the
same process that let Kubernetes's Helm grow from a plain
templating tool into what is effectively a programming language
embedded in YAML. Keeping this grammar closed for good is what
keeps that from happening here (P14).

**Open:** new **qualifiers**. A qualifier names a *namespace to
look in*, never an *operation to perform*, and adding one costs
no new character. `env:`, `file:`, `machine:`, `script:`,
`landmark:`, and `secret:` are reserved.

### Dispatch and edge cases

The qualifier is the text before the **first** colon, so a
property key can never contain a colon (the name charter agrees
with this, since `:` is not a legal character in a name).
Qualifiers must be lowercase. Unqualified `${media}` is rejected
with a did-you-mean hint rather than read as a property literally
named "media". Unknown qualifiers fail closed, naming themselves
in the error (P11). `property:` is reserved but rejected, with an
error suggesting you drop the qualifier — `${key}` unqualified
already means a property lookup. `${}`, `${media:}`, `${:x}`, an
unterminated `${`, and whitespace inside the braces are all parse
errors naming the malformed reference.

**Recorded, not a defect:** scripts reference media as `@name`
and blueprints as `${media:<name>}`. JSON has no token classes,
so a reference must live inside a string; the *property*
spelling is identical across both surfaces, which is what one
reference syntax was buying.

## Two-phase validation

**Shape at parse; value at resolution** (`create` / `apply`).
This is the cost of the interpolation reach, and it is work the
`location` field already demanded.

- At **parse**: structure, vocabulary, the name charter, the
  reference grammar, containment shape, and every rule stated
  above that does not need a resolved value.
- At **resolution**: the **`sha256`-required-once-remote** check
  — a `${key}` entry may resolve to a URL, so parse time cannot
  know that yet — and **coercion** at non-string positions, which
  is the field's own parser run over the resolved string, failing
  closed naming field, value, and source.

A property reference in a location resolves at `create` /
`apply` into the machine state, never at `start`.

## The cache

```text
cache/
└── media/     every payload, by name: <media-name>.<ext>
```

One **name-keyed** directory; `cache/archives/` retires with the
archive type. The cached filename tracks the spec's **name**
(explicit or derived), not the source's basename, so the file is
always `<name>.<ext>` with the extension from the location or
the `extension` override.

Nothing else is recorded about a cached file — the filename is
its whole identity, and there is no separate metadata file next
to it (D41 deleted the ledger that used to track where each file
came from). This is safe because the cache is **entirely
reconstructible**: nothing enters it except by download or
extraction, so no payload in it is irreplaceable — losing it just
means downloading or extracting it again.

The **identity check Reliquary runs before any fetch** is
justified on its own: it hashes the cached file against the
media's pinned hash, which catches both a version bump and a
name collision between two unrelated projects, without needing
to know in advance which of the two it found. The message on a
mismatch names both possible causes and points at `--media-dir`,
the flag that keeps one project's media cache separate from
another's.

**Naming cached files by content hash instead of by media name
was considered and declined, twice.** An opaque hash-named cache
would work against the principle that the cache is internal
implementation detail, not one of Reliquary's public surfaces —
and it wouldn't even buy anything: the pinned hash already makes
a silent collision impossible, so detecting collisions was never
something name-keying lacked. Content addressing stays on record
as the fallback to switch to, if two unrelated media sharing one
name ever turns out to be enough of a real problem in practice to
justify the change.

### The media cache commands

Each of these has a matching API call (P6):

- **`clean-media`** — deletes everything in the cache, since
  anything in it can always be downloaded or extracted again.
  Skips any payload currently attached to a running machine.
- **`clean-media <name>`** — deletes just the one named payload.
- **`prune-media`** — keeps whatever the current scope's machines
  and blueprints actually need — including anything they need
  indirectly, through a containment chain — and deletes the rest.
  Applies to one scope at a time, and supports `--dry-run`.

`add-media <name> <file>` is **not** in this family: it authors
a media declaration for a file already on disk, computing its
sha256, and copies nothing into the cache (D41). It belongs with
the blueprint verbs.

## Machine directory layout

```text
cache/machines/<id>/
├── machine.json    the machine's state: id, blueprint ref, phase,
│                   resolved config — and, while running, the live
│                   VM identity (backend, backend-id, token,
│                   endpoint, pid), written atomically with phase
│                   so the two cannot disagree
├── disks/          per-machine materialized images, <media-name>.<ext>
├── screenshots/    the `screenshot` verb's captures, and a
│                   failure's automatic one
└── <backend>/      the backend's own artifacts (qemu/ virtualbox/ …)
```

A run adds nothing to this tree: it returns its output to whoever
drove it and stores none of it (D36).

This layout is **already delivered** — it landed with milestone
6's absorption of the root-home machine model — and is recorded
here because the model depends on it.

## Materialization

- **Materialized images are named for the media, not the slot**,
  under `cache/machines/<id>/disks/<media-name>.<ext>`. Media
  moving through a shared removable slot each keep their own
  materialization and never clobber one another, and a re-insert
  reuses the existing image. The **anonymous blank**, having no
  catalog name, is named for its **slot** — the one place the
  slot names anything.
- Only `new` / `copy` / `difference` write a per-machine image. A
  read-only `use` attaches the shared `cache/media/<name>`
  payload, the local file, or the directory **directly**, with no
  per-machine copy.
- **`new` is temporary.** A blank image lives only inside the
  disposable machine; destroying the machine loses the image
  unless `export-drive <key> <destination>` already copied it out
  — `export-drive` is the only way a durable artifact leaves a
  machine (P1). The build-and-keep loop for a bootable floppy
  needs no new concept: `new` blank → a run makes it bootable →
  export → reference the exported `.img` as a local media
  (`use` + `read-only`, or `difference`).
- **Medium compatibility** is checked at resolution and fails
  closed naming media and slot: a directory on any drive slot
  (floppy, hdd, or cdrom — legal only on a share now, F68), a `new`
  size onto a cdrom, an ISO into an `hdd` slot.
- **Cross-format differencing** is allowed (a qcow2 overlay over
  a `.vdi`); the backing format is detected from the extension.
  Caveat: a local backing must be a usable standalone image — a
  mid-chain VirtualBox snapshot `.vdi` is only a delta, and
  making it complete is the user's responsibility.

## Worked examples

### 1 — a nested container, children itemized

```json5
[
  { "type": "media", "name": "PaulsFreedos",
    "location": ["https://paul.com/PaulsFreedos.zip",
                 "https://mirror.example/PaulsFreedos.zip"],
    "sha256": "9f4c…",
    "children": [
      { "path": "FD14-LiveCD.zip",
        "children": [ { "path": "FD14LIVE.iso", "read-only": true } ] },
      { "path": "FD14-FloppyEdition.zip",
        "children": [
          "144m/FDBOOT.img",
          "144m/FDSTD01.img",
          "144m/FDSTD02.img"
          // … through FDSTD07
        ] }
    ] },

  { "type": "media", "name": "blank-20m",
    "materialize": "new", "size": "20M" },

  { "type": "machine", "name": "freedos-1.4", "platform": "dos",
    "memory": "16M",
    "devices": { "hdd0": "blank-20m", "cdrom0": null, "floppy0": null },
    "boot": ["cdrom0", "hdd0"] }
]
```

Every child is a media. Their names are derived from filename
stems — `FD14-LiveCD`, `FD14LIVE`, `FDBOOT`, `FDSTD01`… — and the
bare strings under the floppy edition are paths, not names. Only
the one remote location carries a `sha256`. The machine here
belongs to a user's own pinned version of FreeDOS, which is
exactly where a version-specific name like `freedos-1.4` belongs;
the codex's own built-in entries stay generic (D21).

### 2 — an overlay over another media

```json5
[
  { "type": "media", "name": "golden", "location": "C:/images/golden.qcow2" },
  { "type": "media", "name": "scratch", "materialize": "difference",
    "location": "${media:golden}" },

  { "type": "machine", "name": "rig", "platform": "dos", "memory": "64M",
    "devices": { "hdd0": "scratch" }, "boot": ["hdd0"] }
]
```

The bare `${media:golden}` — no path — is the parent's own
bytes. A local location leaves the hash optional, so `golden`
may keep evolving.

### 3 — pinned but unlocated, and the two ways to supply the file

A media may pin a `sha256` while its location has nothing to
supply yet — the case of a licensed, non-redistributable payload
that Reliquary can't fetch on your behalf (U4). Resolution fails
closed, naming the media, and there are two ways to supply the
missing file — neither one changes the identity of the shipped
spec.

```json5
// shipped: pinned, located by property
[
  { "type": "media", "name": "windows-install-cd", "read-only": true,
    "sha256": "exact-build-hash…",
    "location": "${windows.iso}" }
]
```

In a **project or CI**, a property supplies the path. This keeps
the build reproducible: the committed hash still determines
exactly what input gets accepted, no matter what file ends up at
that path. At the **home CLI**, running
`add-media windows-install-cd D:/isos/en_windows.iso` supplies
the file, and Reliquary accepts it once its hash is a match
against the pinned `sha256`. Editing your own seeded copy of the
blueprint directly is always a third option too — and letting you
do exactly that is the whole reason a blueprint is seeded as an
editable copy in the first place.

## Format stability: none, yet

Reliquary is evolving rapidly and **maintains no backward
compatibility until a GA 1.0 release** (see AGENTS.md, the
normative home — beta included, where an occasional cushion may
be granted when warranted but none is promised). That applies to
the blueprint format in full:

- The format may change shape at any time, without migration
  support.
- There is no in-place upgrading of old documents, no
  compatibility parsing, no deprecated-field aliasing.
- A blueprint written for an older Reliquary may simply fail
  validation after an update. The remedy is to recreate the
  machine (or update the blueprint by hand to the current format
  as documented here).

There is deliberately no version field. Versioning is
compatibility machinery, and the blueprint carries none until a real
second format version exists — no earlier than 1.0.

For the same reason, a blueprint carries no `$schema` field
either: a document that pins the schema it was written against is
really just a version field wearing a different name, and before
1.0 a document has no format version to pin in the first place.
The only schema that actually matters is the one belonging to the
Reliquary installation that will read the document, and editors
already bind to that by file association — which tracks the
installed version automatically, where an embedded schema pin
would instead go stale over time and let the editor accept
documents Reliquary itself would reject. When versioning does
arrive, no earlier than 1.0, `$schema` as a versioned URL is the
leading candidate for what the version field will look like
(planning/DECISIONS.md, "Open questions", formerly "Decisions
still needed").

The blueprint's value model is ordinary JSON data — there is no
YAML form, and none is planned. Because a blueprint is a document
you author and Reliquary only ever reads (`import` and `init`
write one once, then never again), the file accepts the published
**JSON5** grammar ([spec.json5.org](https://spec.json5.org); D102):
comments, trailing commas, unquoted keys, single-quoted strings,
hexadecimal and signed numbers, and the other JSON5 productions.
`NaN`, `Infinity`, and `-Infinity` are refused so the parsed
value tree stays ordinary JSON. Comments are the author's margin
notes — a seeded built-in blueprint uses them to mark the places
you're meant to customize it, its
[customization seams](../blueprint-guide.md#customization-seams)
(U5) — and they carry no meaning to Reliquary: it never reads
them, and nothing that affects behavior may live in one; anything
the format actually needs is a field, not a comment. A blueprint
written as strict JSON
remains valid JSON5; one that uses JSON5 syntax is not parseable
by strict JSON tooling — a deliberate trade. Machine-written
documents are different: the state — and every other file
Reliquary writes — is strict canonical JSON, always.

The rule for how the format is allowed to grow was decided
before that growth pressure actually arrives (planning/DECISIONS.md,
2026-07-23). Reliquary expects pressure to add computation to the
format over time — expanding a set of variants, itemizing the
members of something, deriving one value from another — and one
rule governs all of it: **a construct that adds more data for
Reliquary to work with may be added to the format; computation
that decides the shape of the document itself never may.** A
bounded, purpose-built declarative construct — something like a
member glob or a variant matrix — may be added once it has earned
its place, but it is always expanded by Reliquary itself, never
evaluated by something the author wrote. General-purpose
computation — arithmetic, conditionals, string interpolation, or
user-written logic of any kind — cannot be added to the format at
all; wanting it is a signal to move to a separate layer, not to
extend the document tree. That layer would only ever *produce*
plain blueprints as its output — either code written above the
format (the embedding API is where computation belongs, the same
rule the scripting language follows as G2), or a separate
evaluation step that reads some JSON-superset input and writes
out the format documented here, leaving the blueprint's own
parsing, validation, and resolution completely unchanged.
Functions embedded in the document, and string templating, are
permanently ruled out.

The rule above governs the document's tree structure. A twin rule
governs the *strings* inside it, because a format like this can
be undermined just as easily by what's allowed inside one
reference string as by what's allowed in the tree
(planning/DECISIONS.md, D26): **the `${…}` reference body is
closed, permanently — new namespaces may be added to it, but no
new operation ever may.** The body must be one of exactly two
productions — a qualified `qualifier:media-name[/path]`, or a
dotted property key — and neither one has a position an operator
could occupy. No operator ever joins them: no defaults, no
filters or pipes, no calls, no indexing, no arithmetic, no
comparison, no nesting, no second escape character.

Two tests apply, in order, and both are necessary (D27). The
character class `[A-Za-z0-9._:/-]` is the **first screen**: every
character allowed in it is already doing real work (`:` separates
the qualifier, `/` the containment path, `.` the property
dot-path, and `_` and `-` come from the media-name charter), so
anything reaching for `|`, `(`, `[`, `?`, `=`, or whitespace is
rejected immediately. **The two productions decide the rest**,
and this second test matters because an operator can be built
entirely out of legal characters: `${mem:-512M}` passes the
character class and is still refused, because the text before its
first colon is read as the qualifier, and `mem` is not a
recognized one. A proposal for something new that fails either
test is a signal to build a separate layer, not to extend this
grammar.

What can still be added is new *qualifiers* — `env:`, `file:`,
`machine:`, `script:`, `landmark:`, and `secret:` are already
reserved for future use. A qualifier only names a namespace to
look values up in; it never performs an operation, and adding one
never creates a position an operator could occupy.

### When a request arrives

The standing answer to a request like this is not "no." Picture
an author writing: *"CI needs 2G, my laptop needs 512M — let
`memory` take `${mem:-512M}` so it still boots when the property
is unset."* The real answer is **that this already works, just
through a different channel.** Reliquary is not missing a way to
set a default; it already has one, in the property channel, which
exists specifically to handle exactly this situation — the
project's properties file gives CI its 2G, the user's own file
gives their laptop its 512M, and the blueprint itself just says
`${mem}` and needs no fallback written into it at all. Where a
value truly must survive an unset property, that's a question
about which property sources take precedence over which
([script-properties.md](script-properties.md) covers the
repeatable `default=` candidates), and it's answered there, where
defaults already live.

This is the shape of nearly every request like this. The feature
being asked for is not missing from the project — it already
exists, in a different channel, and it only got raised against
the reference grammar because the grammar is the part of the
format the author happened to have open when they hit the need.
The first move is always to find where the feature already lives.

The danger of simply agreeing is not the default itself but what
the default makes sayable next. `${mem:-512M}` requires deciding
what an unset property *is* (absent? empty? null?), which is a
specification. Then comes `${mem:-${fallback}}`, because a
literal default is obviously less useful than a computed one.
Then a conditional, because two defaults need choosing between.
None of those is a stretch; each follows from the one before.
Meanwhile the published schema can no longer say what a valid
`memory` is, and the editor stops completing the field — which
is what the plain format was chosen to buy (U4, U5).

### When it is time for a layer

This isn't a matter of crossing some threshold — it's a
conjunction: all four of the following have to be true at once.
Volume alone is not a signal: a hundred requests for defaults and
conditionals mean the property channel needs better
documentation, not that the format's ceiling is set wrong.

1. **The need is about structure, not about what goes in a
   value.** It asks *how many specs exist*, or *which ones*,
   rather than what value to put in one field. A need shaped
   around a value always has an answer already; a need shaped
   around structure may not. Twelve near-identical blueprints that
   differ only in one localized ISO's URL and hash is a structural
   need.
2. **It comes up again and again, from independent authors.**
   Not just one project's convenience — a shape that two or more
   unrelated people hit on their own, or one the codex itself
   needs.
3. **Solving it with a bounded declarative construct was tried,
   and it failed.** The format's ceiling has its own way to grow:
   a bounded construct that adds more data to work with, expanded
   by Reliquary itself. A variant matrix has to be designed
   against the real case first, and it has to either fail to
   express that case, or turn into a full language once it's
   fully specified. Skipping this step is how a whole new layer
   ends up getting adopted for a problem a twenty-line construct
   would have solved just fine.
4. **Generating blueprints from code fails for the user who has
   no project and no programming language to write that code in.**
   The embedding API can already emit twelve blueprints today, and
   P4 requires the generator and its output to live in the
   consuming project's own tree — so for someone automating a
   project (U4), this condition is rarely met; they already have a
   good option. It's the *home* CLI user (U1, U5) — with no
   repository and nothing beyond the shell to write code in — for
   whom neither route works well. That's exactly the user this
   layer would be built for, and it follows directly from where
   blueprints live: the home directory exists for a person working
   alone at a shell prompt, with neither a project to put a
   generator in nor a language to write one in.

When all four of those hold at once, the answer is an evaluation
step: something like a `freedos.rlqb.jsonnet` file that produces
an ordinary `freedos.rlqb`, as its own separate file kind. That
step gets argued through and recorded under the surface-change
rule when it actually happens — it is not pre-committed to here,
and it would never take the form of a mode flag that makes the
existing parser start evaluating things.

When this new layer does eventually arrive, it will take the form
of a **separate file kind, or an explicit extra step** — never a
widening of what `.rlqb` itself means. A document that has to be
evaluated before it can even be read can't be checked against a
schema or completed by an editor, and that cost would fall on
every blueprint in the format if `.rlqb` grew this capability
itself — including the large majority of blueprints that want no
computation at all. Plain `.rlqb` keeps its schema, its editor
completion, and its strictness, permanently.


## What this supersedes

- The first-round four-component model — `source` and `archive`
  as types, the plural root sections, the bare-root machine, the
  `members` tree, and the two-directory cache — is superseded
  entirely by this document.
- `.rlqm` retires.
- blueprint-guide.md, its field reference and cookbook, and
  media-spec.md realign to this model (milestone 7, deliverable
  7); until then they describe the implemented pre-composition
  surface.
- The two published JSON Schemas collapse into **one** blueprint
  schema with a two-variant root: the machine variant requires its
  declared `type`, and the media variant accepts leaving `type`
  out. Its closed vocabularies stay plain `enum`s and are **never
  widened to accept a `${…}` reference in their place**: that is
  exactly what excluding them from reach (above, "Reach: where a
  reference may appear") is for — protecting the editor completion
  a published schema gives you is the whole point.
- **Parked, with no case yet to justify either one:** the two
  candidate constructs the growth rule allows for (above, "Format
  stability"). One is a compact shorthand for extracting many
  children at once, instead of listing each one out the way the
  worked example above lists `FDSTD01` through `FDSTD07` — wanted,
  but not now, and never at the cost of requiring static, glob-free
  names. The other is a variant matrix for near-identical
  blueprints that differ only in one localized medium's location
  and hash. Each will be designed against a real case once one
  arrives, and argued through under the surface-change rule at
  that point; nothing here commits to either one in advance.
