<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
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
> [machine-blueprint.md](machine-blueprint.md), its
> [field reference](machine-blueprint-reference.md), and
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

The format is deliberately **logic-free** and stays that way:
what it may say is capped by P14, and the ceiling is stated here
as a closed grammar rather than left to judgment. See
[Format stability](machine-blueprint.md#format-stability-none-yet)
for the growth rule; this document states the grammar it closes.

## The file

A `.rlqb` root is an **array of specs**:

```jsonc
[
  { "type": "machine", "name": "freedos", "platform": "dos", … },
  { "type": "media", "name": "freedos-livecd", … }
]
```

A **lone spec object** is accepted as pure sugar for the array
of one, under exactly the same rules:

```jsonc
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
`drives`, `boot`, `scripts`, …) appears, so the diagnosis is one
line rather than a puzzle.

A root array element that is a **bare string** is a media
desugaring to `{ "location": <string> }` — see
[the string-position table](#strings-are-interpreted-objects-are-explicit).
It is invalid where the location kind demands a pin: a bare URL
string fails closed naming the object form, since a remote
payload needs a `sha256` it has nowhere to put.

JSONC is accepted: RFC 8259 plus `//`, `/* */`, and trailing
commas — nothing more. Every machine-written file stays strict
JSON. There is no `$schema` or version field pre-1.0.

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
`control-planes`, `backend-settings`, `description`, `scripts`,
`parameters`, and `name`.

`drives` maps a slot key (`hdd0`, `cdrom0`, `floppy0`, …) to one
of:

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
change the media, or point the drive at a different one.**

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
  **Required once any remote rung is present** (checked at
  resolution, not parse — see
  [Two-phase validation](#two-phase-validation)), optional for
  local and derived payloads. Optional is a feature: a local
  media may omit it to attach a drive image still being
  *evolved*, where a pin would fail on every edit; hermetic
  workflows add the hash when they want the pin. The hash is the
  build pin *independent of the location kind* — a trusted local
  payload can still verify it is the exact build the scripts
  target (U4).
- **`read-only`** — present the drive read-only. Orthogonal to
  `materialize`. **Defaults true on a cdrom** (no backend
  meaningfully emulates writing a virtual ISO; a writable cdrom
  is rejected); opt-in elsewhere. On a directory payload it
  protects the host directory.
- **`extension`** — override the type-declaring extension of the
  cached payload when the source filename misnames or omits it.
  Otherwise derived from the location's filename or path.
- **`children`** — containment sugar; see
  [Containment](#containment-parent-and-children).
- **`description`**, **`notes`** — prose.

**A host directory is a payload shape, not a mode:** a media
whose location is a directory, with `materialize: use`, is the
live vvfat attach. `use` covers "attach this file" and "attach
this directory" alike. vvfat emulates no ISO9660, so a directory
on a cdrom is rejected at resolution.

## Identity and the catalog

Every named spec lands in **one global catalog**, and identity
is the pair **`(name, type)`** — a media named `dos622` and a
machine named `dos622` coexist, because every reference is
type-directed.

**The name is the membership bit.** A spec is either named —
explicitly, or derived from content-intrinsic material — and in
the catalog, or it is the one anonymous citizen and in no
namespace at all.

### The name charter

A name is checked against one production:

```ebnf
media-name = ( letter | digit ) , { letter | digit | "." | "_" | "-" } ;
```

This is the script language's `name` production with a leading
digit allowed, split from the letter-initial `property-key`. The
split is one clause and it is load-bearing in only one
direction: a media name has no bare site in any surface (`@name`
in scripts, a JSON string in blueprints), while a property key
appears bare at a declaration, where a leading digit would lex
as a duration. So `86Box` is a perfectly good media name.

What is mechanically forced out regardless: whitespace, `{`,
`}`, `#`, `/` (the containment separator — `${media:C:/x}` is
otherwise ambiguous), and control characters. Parentheses and
brackets are excluded by **argv, not grammar**: every media name
is a command-line argument at `fetch-media` / `add-media` /
`clean-media`, and `rlq fetch-media FD(1)` is a shell syntax
error exactly as `FD[1]` is — a name needing per-shell quoting
is a permanent papercut against P7, and brackets add a glob
hazard over `cache/media/` on top.

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
first rung is a reference), it **fails closed demanding an
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

Composition — merging fragments of one spec across files — was
worked through and **declined**: it was a second personal-values
mechanism in disguise. The supply seam is
**edit-your-seeded-copy** (home) or a **property-valued
location** (project, CI).

### The anonymous blank

The content-free blank — a drive-inline `{ "size": "20M" }` — is
the **sole anonymous citizen**: it belongs to no namespace, is
identified only by its site, is named for its **slot** at
materialization, and cannot be referenced from a script. It has
no content to derive a name from and no reason to be shared;
anything else must be named. Document-scoped anonymous names
were declined — anonymous means *absent*, not *private*.

## Resolution

Resolution reads **every `.rlqb` in the active source** — the
whole home in home mode, the whole project root under
`--assets` — into one catalog, then binds every reference by
name. The residency split is unchanged: home mode seeds from the
codex on a miss, `--assets` is the sole hermetic source (P4).

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

```jsonc
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

```jsonc
[
  { "type": "media", "name": "freedos-livecd-zip",
    "location": "https://download.freedos.org/1.4/FD14-LiveCD.zip",
    "sha256": "2020ff…" },
  { "type": "media", "name": "freedos-livecd", "read-only": true,
    "location": "${media:freedos-livecd-zip}/FD14LIVE.iso",
    "sha256": "c48a9d…" }
]
```

Nesting is unbounded and needs no chaining syntax: a child that
is itself a container simply has `children` of its own. One
remote rung high in the tree downloads once; every descendant
derives from the cached parent.

**The reading is decided at the reference site, not in the
spec.** A drive or a script `insert` **mounts** a media; a
parent location or a `children` walk **extracts** from it. Dual
roles are legal and unremarkable — one ISO mounted at `cdrom0`
and container-read for its boot floppy is the same media used
two ways. This is why the archive type could be absorbed: it
described a use, not an artifact.

**Container reading is roster-gated by format.** Milestone 7
supports **zip** only; an unsupported container fails closed
naming its format. ISO9660, including its `[BOOT]` El Torito
virtual paths, is the recorded follow-on; reading filesystem
images is out pre-beta.

A **path glob** in `children` was declined: names must be
static, because the catalog can never depend on a download (G3).

## The location grammar

One field, `location`, under one format-wide law:

### Strings are interpreted, objects are explicit

**Every interpreted string has exactly one object desugaring**,
and that object is the canonical form — what the machine state
records, what the embedding API emits, and the escape hatch
whenever a string would be ambiguous. The object is also the
option point: attributes that have no string spelling live
there.

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
| `${media:<name>}/<path>` | a member of the parent | `{ "parent": "<name>", "path": "<path>" }` |
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

A location may be a **list** of locations, tried in order, with
mixed schemes allowed — the hash, not the URL, is the arbiter. A
**one-element list is simply the scalar** (no special case), an
**empty list is an error**, and **nested lists are illegal**.
`sha256` is required once any rung is remote.

## The universal reference

`${…}` is the one reference syntax, everywhere.

- **Unqualified** `${a.b.c}` ≡ `{ "property": "a.b.c" }` — one
  spelling shared with the script language and with milestone
  8's derivation grammar.
- **Qualified** `${media:<name>}` reads the catalog. A **bare**
  `${media:X}` is a legal whole location meaning the parent's
  own bytes — which is how `materialize: difference` puts an
  overlay over another media. With a suffix,
  `${media:<name>}/<path>` is the containment location; the path
  is the **second component of one location**, never string
  interpolation.

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
   `materialize`, `controller`, and `control-planes` items never
   take a reference. These are where a published schema's
   completion is most valuable and where a reference destroys
   it (U4, U5), and they have no named case asking for one.
   `platform` is the sharpest instance: P10 has it never
   inferred and always from the blueprint, and a `${…}` platform
   is a runtime-decided platform in all but name.

Everything else a scalar position accepts may be referenced:
`location`, `parameters` values, `description`, and the open
numerics `memory`, `cpus`, `size`. **`sha256` stays
interpolable** — a hash is not a closed vocabulary, and
excluding it would buy nothing, since what forces the
required-once-remote check to resolution time is a *referenced
location rung*, not the hash field.

Reach is **asymmetric**: widening it later is compatible,
narrowing it is not. That is why these exclusions are stated
before the parser exists, and why reach is a design call that
may be revisited on a named case — unlike the grammar below.

### Resolution order

**Interpolate, then scheme-dispatch the result. Resolved text is
never re-scanned.** A property whose value happens to read
`${media:X}/p` stays literal text and fails the scheme check —
this is the no-chaining rule made precise.

### The path suffix

Exactly **one `/`** separates reference from path. Member paths
are `/`-separated always, following the container formats' own
convention. The path normalizes, and `..`, absolute paths, and
empty segments are **refused as containment escapes**. A
backslash after `}` is an error naming the `/` rule — the
Windows author's first guess — and trailing or doubled slashes
are errors.

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

The second half is not decoration. `${mem:-512M}` — the likeliest
request of all — is built **entirely from legal characters** and
passes the class; it is refused because the text before the
first colon is the qualifier and `mem` is not one. A closure
whose stated test is wrong invites exactly the feature it exists
to refuse.

**Closed permanently:** every operator — defaults (`${key:-x}`),
pipes and filters, calls, indexing, arithmetic, comparison,
ternaries, nesting (`${${a}}`), and any second escape. A
proposal that does not fit is a **layer-switch signal, never a
grammar extension**. Each such feature will arrive with a real
user and a good case, and unanimous individual justification is
precisely how the Helm shape is reached (P14).

**Open:** new **qualifiers**. A qualifier names a *namespace to
look in*, never an *operation to perform*, and adding one costs
no new character. `env:`, `file:`, `machine:`, `script:`,
`landmark:`, and `secret:` are reserved.

### Dispatch and degenerates

The qualifier is the text before the **first** colon, so a
property key never contains one (the charter agrees).
Qualifiers are lowercase-only. Unqualified `${media}` is
rejected with a did-you-mean rather than read as a property of
that name. Unknown qualifiers fail closed naming themselves
(P11); `property:` is reserved-and-rejected under a nudge to
drop the qualifier. `${}`, `${media:}`, `${:x}`, an unterminated
`${`, and whitespace inside the braces are all parse errors
naming the malformed reference.

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
- At **resolution**: the
  **`sha256`-required-once-remote** check — a `${key}` rung may
  resolve to a URL, so parse time cannot know — and **coercion**
  at non-string positions, which is the field's own parser run
  over the resolved string, failing closed naming field, value,
  and source.

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

Beside it sits an **identity ledger** recording, per entry:

- the **sha256** actually observed,
- the **derivation key** — `(parent-sha, path)` — for a derived
  payload,
- **provenance**: `refetchable` · `derived` · `supplied`,
- **source lineage**.

The ledger buys a **deterministic preflight identity check
before any fetch**, which feeds the standing on-mismatch
contract with **lineage-informed messages** — a version bump and
a cross-project name collision are distinguishable at a glance,
which is exactly what name-keying could not do on its own.

**Content addressing was weighed and declined twice.** An opaque
hash-named cache cuts against "the cache is not an interface",
and the ledger closes the detection gap that was content
addressing's real argument. It stays the recorded escalation if
collision friction ever proves real.

### The command family

Each has an API twin (P6):

- **`clean-media`** — blunt reclamation; **spares `supplied`**
  entries (nothing irreplaceable is ever deleted) and skips
  payloads attached to a running machine.
- **`clean-media <name>`** — targeted eviction.
- **`prune-media`** — attachment-closure prune: keep what the
  scope's machines and blueprints actually need, drop the rest.
  Scope-relative, with `--dry-run`.
- **`add-media <name> <file>`** — the guarded door. A pinned but
  unlocated media resolves by **cache hit**: the user supplies
  the file once, it is verified against the pin, and the
  blueprint never has to be edited.

## Machine directory layout

```text
cache/machines/<id>/
├── machine.json    the machine's state: id, blueprint ref, phase,
│                   resolved config — and, while running, the live
│                   VM identity (name, uuid, port, pid), written
│                   atomically with phase so the two cannot disagree
├── media/          per-machine materialized images, <media-name>.<ext>
├── <backend>/      the backend's own artifacts (qemu/ virtualbox/ …)
└── runs/           append-only run records
```

This layout is **already delivered** — it landed with milestone
6's absorption of the root-home machine model — and is recorded
here because the model depends on it.

## Materialization

- **Materialized images are named for the media, not the slot**,
  under `cache/machines/<id>/media/<media-name>.<ext>`. Media
  moving through a shared removable slot each keep their own
  materialization and never clobber one another, and a re-insert
  reuses the existing image. The **anonymous blank**, having no
  catalog name, is named for its **slot** — the one place the
  slot names anything.
- Only `new` / `copy` / `difference` write a per-machine image. A
  read-only `use` attaches the shared `cache/media/<name>`
  payload, the local file, or the directory **directly**, with no
  per-machine copy.
- **`new` is ephemeral.** A blank lives only in the disposable
  machine; destroying it loses the image unless
  `export-drive <key> <destination>` took it out first — durable
  artifacts leave through the export door (P1). The build-and-keep
  loop for a bootable floppy needs no new concept: `new` blank →
  a run makes it bootable → export → reference the exported
  `.img` as a local media (`use` + `read-only`, or
  `difference`).
- **Medium compatibility** is checked at resolution and fails
  closed naming media and slot: a directory on a cdrom, a `new`
  size onto a cdrom, an ISO into an `hdd` slot.
- **Cross-format differencing** is allowed (a qcow2 overlay over
  a `.vdi`); the backing format is detected from the extension.
  Caveat: a local backing must be a usable standalone image — a
  mid-chain VirtualBox snapshot `.vdi` is only a delta, and
  making it complete is the user's responsibility.

## Worked examples

### 1 — a nested container, children itemized

```jsonc
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
    "drives": { "hdd0": "blank-20m", "cdrom0": null, "floppy0": null },
    "boot": ["cdrom0", "hdd0"] }
]
```

Every child is a media. Names derive from stems —
`FD14-LiveCD`, `FD14LIVE`, `FDBOOT`, `FDSTD01`… — and the bare
strings under the floppy edition are paths. Only the one remote
rung carries a `sha256`. The machine here is a *user's* pinned
vintage, which is exactly where version-bound names belong; the
codex's own entries are generic (D21).

### 2 — an overlay over another media

```jsonc
[
  { "type": "media", "name": "golden", "location": "C:/images/golden.qcow2" },
  { "type": "media", "name": "scratch", "materialize": "difference",
    "location": "${media:golden}" },

  { "type": "machine", "name": "rig", "platform": "dos", "memory": "64M",
    "drives": { "hdd0": "scratch" }, "boot": ["hdd0"] }
]
```

The bare `${media:golden}` — no path — is the parent's own
bytes. A local location leaves the hash optional, so `golden`
may keep evolving.

### 3 — pinned but unlocated, and the two supply seams

A media may pin a `sha256` with a location nothing supplies yet:
the licensed, non-redistributable case (U4). Resolution fails
closed naming the media, and there are two ways to supply it —
neither of which edits the shipped spec's identity.

```jsonc
// shipped: pinned, located by property
[
  { "type": "media", "name": "windows-install-cd", "read-only": true,
    "sha256": "exact-build-hash…",
    "location": "${windows.iso}" }
]
```

In a **project or CI**, the property supplies the path — the
hermetic seam, since the committed hash still determines the
input. At the **home CLI**, `add-media windows-install-cd
D:/isos/en_windows.iso` resolves it by cache hit against the
pin. Editing your seeded copy is always the third option, and
that is the point of seeding.

## What this supersedes

- The first-round four-component model — `source` and `archive`
  as types, the plural root sections, the bare-root machine, the
  `members` tree, and the two-directory cache — is superseded
  entirely by this document.
- `.rlqm` retires.
- machine-blueprint.md, its field reference and cookbook, and
  media-spec.md realign to this model (milestone 7, deliverable
  7); until then they describe the implemented pre-composition
  surface.
- The two published JSON Schemas collapse into **one** blueprint
  schema with a two-variant root — machine requiring its declared
  `type`, media accepting its absence. Its closed vocabularies
  stay plain `enum`s and are **never widened to admit a reference
  pattern**: that is what the reach trim buys, and the editor
  completion it protects is the point.
- **Parked:** a succinct extraction short-circuit for long
  itemized child lists — wanted, not now, and never at the cost
  of static names.
