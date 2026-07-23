<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# The composed blueprint model

> **Status:** worked design of the 2026-07-23 media/composition
> round. Source of truth for the composed authored model; the
> existing specs ([machine-blueprint.md](machine-blueprint.md),
> its [field reference](machine-blueprint-reference.md),
> [media-spec.md](media-spec.md)) and the published JSON Schemas
> realign to it, and stay normative until they do.

This round folds reliquary's two authored JSON formats — the
machine blueprint (`.rlqb`) and the media definition (`.rlqm`) —
into **one composable format**. There is a single authored JSON
kind, the **blueprint** (`.rlqb`); `.rlqm` retires. A blueprint
file is a bag of independently named **components**, mixed and
matched across files however the author likes. Scripts (`.rlqs`)
and landmark declarations (`.rlql`) remain their own kinds — this
round is the declarative JSON specs only.

## The file

A `.rlqb` root is polymorphic — named component sections, any
combination present, each holding a list:

```jsonc
{
  "machines": [ … ],
  "media":    [ … ],
  "sources":  [ … ],
  "archives": [ … ]
}
```

Section keys are plural (each holds a list; `media` is already
the plural of medium). Every section is optional. The common
case — a lone machine — stays a **bare root** with the machine's
fields at top level (today's blueprint, unchanged): a root with
none of the section keys reads as a single machine. Detection is
unambiguous — no machine field is named `machines` / `media` /
`sources` / `archives`.

JSONC is accepted as before (RFC 8259 plus `//`, `/* */`,
trailing commas; nothing more). No `$schema` / version field
pre-beta.

## Components, identity, resolution

Four component types: **machine**, **media**, **source**,
**archive**. (Archives and their leaf media are usually written
together as a tree — below.)

- **Names default to the source/path stem.** A component may
  carry an explicit `name`; when it does not, its name is the
  **stem of its source filename or archive path** —
  `PaulsFreedos.zip` → `PaulsFreedos`, `144m/FDBOOT.img` →
  `FDBOOT`. A component with no filename-bearing source (a
  `machine`, a `new` blank media) **must** name itself; there is
  nothing to derive from. This refines — does not undo — the
  mandatory-name rule: the default comes from the *payload's*
  filename, which travels with the source, so a fragment resolves
  the same when pasted among siblings. It is only the
  `.rlqb`-*file* stem that is still forbidden as identity.
- **Identity is the pair `(name, type)`.** A `media` named
  `dos622` and a `machine` named `dos622` coexist, because every
  reference is type-directed. Two components of the same type and
  name within one resolution source are a collision error naming
  both.
- **Resolution reads the whole source.** At run time rlq reads
  **every `.rlqb` in the active source** — the whole home in home
  mode, the whole project root under `--assets` — into one
  `(name, type)` namespace, then binds every reference by name.
  This is authored-asset resolution (planning/ROADMAP.md)
  generalized to "all `.rlqb`, components typed and named". The
  residency split is unchanged: home mode seeds from the codex on
  a miss; `--assets` is the sole hermetic source.
- **Selection.** `--blueprint <name>` selects the **machine** of
  that name; a machine id is `<name>-<n>`. (Supersedes the earlier
  "file stem is the selection key" call — with many machines
  possibly in one file, the stem cannot select.)

## machine

Topology only — no content lives here:

- `platform` (required, never inferred), `backend`, `memory`,
  `cpus`, `boot`, `control-planes`, `backend-settings`,
  `description`, `scripts`, `parameters` — as in today's field
  reference.
- `drives` maps a slot key (`hdd0`, `cdrom0`, `floppy0`, …) to a
  **media name** (string), to **`null`** (a declared but empty
  removable slot a script fills), or to an object carrying
  hardware attributes (`controller`, `enabled`) plus `media` (the
  name). The old four-way content selector (`size` / `base` /
  `media` / `hostdir`) is **gone**.

A media name is the machine's one cross-boundary reference. **To
change how a drive materializes, change (or point at a different)
media.**

## media

A media owns all content and materialization:

- **`name`** — explicit, or defaulted from the `source` filename.
- **`materialize`** — `new` · `difference` · `copy` · `use`;
  default **`use`**.

  | value | meaning | needs |
  |---|---|---|
  | `new` | fresh blank image of `size` | `size`; **no** `source` |
  | `difference` | writable overlay over the payload (payload untouched) | `source` |
  | `copy` | payload duplicated into a standalone image | `source` |
  | `use` | attach the payload itself (mutable unless `read-only`) | `source` |

  `use`/`difference`/`copy` require a `source`; a `use` with no
  source is a validation error. `new` takes `size`, forbids
  `source`.
- **`size`** — `new` only (`"20M"`, `"1440K"`).
- **`source`** — where the payload comes from (a locator, below).
- **`sha256`** — the payload's hash, verified on every use.
  **Required when the source is a `url`** (remote, untrusted),
  optional for `local` and from-archive sources. Optional is a
  feature: a `local` media may omit it to attach a drive image
  you are still **evolving** (a pin would fail on every edit) —
  the same liveness logic as `hostdir`; hermetic workflows add
  the hash when they want the pin. `media.sha256` is the build
  pin *independent of the source kind* — a trusted `local` source
  (hash optional at the source) can still verify the media is the
  exact build the scripts target.
- **`read-only`** — present the drive read-only so a floppy/hdd is
  not corrupted. Orthogonal to `materialize`. **Defaults true on a
  cdrom** (no backend meaningfully emulates writing a virtual ISO;
  a writable cdrom is rejected); opt-in elsewhere; for `hostdir`
  it protects the host directory.
- **`extension`** — override the type-declaring extension of the
  cached payload when the source filename misnames (or omits) it.
  Otherwise derived from the source filename / archive member
  `path`.

**hostdir folds in as a payload shape, not a mode:** a media whose
`source` is a host *directory* with `materialize: use` is the live
vvfat attach. `use` covers "attach this file" and "attach this
directory" alike.

## sources and locators

A **locator** says where bytes come from. As a media's `source`
it is one of:

- a **string** naming a `source` (or `archive`) component;
- an inline **`{ "url": … }`** — a single URL or a **mirror list**
  tried in order, the (required) `sha256` the arbiter, not the URL;
- an inline **`{ "local": … }`** — a path on disk (relative paths
  resolve from the referencing file's directory); the user's own
  file, outside the cache;
- an inline **from-archive** `{ "archive": "<name>", "path":
  "<member>" }` — extract a member from a named archive.

A **`source` component** (the `sources` section) is a named,
standalone locator — the same schema hoisted so it can be supplied
or replaced independently of the media that pins the payload's
hash. Mirror lists live here naturally:

```json
{ "sources": [
    { "url": ["https://paul.com/PaulsFreedos.zip",
              "https://mirror.example/PaulsFreedos.zip"],
      "sha256": "9f4c…" } ] }
```

Its name defaults to the URL/local filename stem (`PaulsFreedos`).

## archives — the recursive tree

An **archive** is a container: a `source` (where the archive bytes
are) plus recursive **`members`**. The tree mirrors the physical
nesting, and **its shape *is* the extraction**:

> **A node with `members` is an archive** (descend into it); **a
> leaf — no `members` — is a media** payload.

```json
{ "archives": [
    { "source": "PaulsFreedos",
      "members": [
        { "path": "FD14-FloppyEdition.zip",
          "members": [
            { "path": "144m/FDBOOT.img"  },
            { "path": "144m/FDSTD01.img" }
            // … through FDSTD07
          ] } ] } ] }
```

- The root `source` names a `sources` component (or is an inline
  locator). Each internal node becomes an **archive** cached under
  `archives/`; each leaf becomes a **media** cached under `media/`.
- **Names default to stems** at every level (`PaulsFreedos`,
  `FD14-FloppyEdition`, `FDBOOT`, `FDSTD01`…); any node or leaf
  takes an explicit `name`, and a leaf may set `materialize` /
  `read-only` / `extension` like any media (default `use`).
- **Members are itemized explicitly** — every payload is its own
  line — but the archive chain is declared once. (A globbed
  auto-expander — the earlier "media-set" — was **dropped**; a
  succinct "short-circuit" convenience is parked as a wish.)
- A single payload is just a one-leaf tree, or a media whose
  `source` is a from-archive locator referencing an existing
  archive by name.

Nesting is therefore unbounded and needs no special chaining
syntax — the tree is the chain. One `url` high in it downloads
once; every descendant extracts from the cached parent.

## Unlocated media (non-redistributable)

A media may pin its `sha256` and name a `source` that nothing
supplies yet — the licensed / non-redistributable case. Resolution
**fails closed** naming the media and the missing source until the
user provides it, **without editing the seeded media**: the media
references its source by name, and the user drops a matching
`source` component beside it.

```jsonc
// shipped (codex / shared): pinned, unlocated
{ "media": [
    { "name": "windows-install-cd", "read-only": true,
      "sha256": "exact-build-hash…", "source": "windows-cd-location" } ] }

// user supplies, without touching the media above:
{ "sources": [
    { "name": "windows-cd-location", "local": "D:/isos/en_windows.iso" } ] }
```

The media's `source` string and the `source` component's `name`
must match. Two sources of one name within a resolution source
must agree, else it is a collision error.

## Machine directory layout

```text
cache/machines/<id>/
├── machine.json             the machine's state (reliquary-owned):
│                            id, blueprint ref, phase, resolved
│                            config — and, while running, the live
│                            VM identity (name, uuid, port, pid)
├── media/                   per-machine materialized images,
│                            <media-name>.<ext>
├── <backend>/               the backend's own artifacts, in its
│                            backend-named subdir (qemu/ virtualbox/
│                            vmware/ hyperv/): virtualbox .vbox,
│                            vmware .vmx, hyperv config; qemu keeps
│                            only its captured stderr log here
└── runs/                    append-only run records
```

The state file is renamed `reliquary-machine.json` →
**`machine.json`** (the backend noise is quarantined in the
backend subdir, so the prefix no longer earns its keep), and
**`vm.json` folds into it** as a while-running state section
written atomically with `phase` — so phase and identity can never
disagree. `launch_owned_qemu` still returns the identity and
`machines.py` persists it, keeping `lifecycle.py` decoupled from
the state format; `mark_stopped` clears the running section.

## Materialization lifecycle

- **Materialized media are named for the media, not the slot,**
  and live under `media/`:
  `cache/machines/<id>/media/<media-name>.<ext>`, keyed by the
  media item. So media moving through a shared removable slot
  (floppy/cdrom swaps) each keep their own materialization and
  never clobber one another, and a re-insert reuses the existing
  image. A materialized image is per `(machine, media)`; a
  *writable* materialization occupies at most one slot at a time.
  Only `new` / `copy` / `difference` write a per-machine image
  here — a read-only `use` attaches the shared `cache/media/<name>`
  payload (or the `local` file, or the `hostdir` directory)
  **directly**, no per-machine copy.
- **`new` is ephemeral.** A `new` image lives only in the
  disposable machine. Destroying the machine loses it unless
  `export-drive <key> <destination>` took it out first — durable
  artifacts leave through the export door (planning/ROADMAP.md
  "Vision"). The create → build → store → reuse loop for a
  bootable floppy: `new` blank → a run makes it bootable → export
  it → reference the exported `.img` as a `local` media (`use` +
  `read-only`, or `difference`). "Keep editing the same floppy"
  needs no new concept: `use` + `read-only:false` + `local`
  mutates its source in place; bootstrap the first blank with
  `new` + one export. A create-at-destination shortcut was
  **weighed and declined** (fuses source with destination,
  duplicates export).
- **Medium compatibility** is checked at resolution and fails
  closed naming media and slot (`use`-an-ISO into `hdd`, `new`
  size onto `cdrom`, cdrom `hostdir`, …).
- **Cross-format differencing** is allowed (qcow2 overlay over a
  `.vdi`): `materialize` detects the backing format from the
  source extension. Caveat: a `local` backing must be a usable
  standalone image — a mid-chain VirtualBox snapshot `.vdi` is
  only a delta, the user's responsibility to make complete.

## The cache

```text
cache/
├── archives/   archive components, by name: <archive-name>.<ext>
│               (nested/intermediate archives included)
└── media/      resolved payloads, by name:  <media-name>.<ext>
```

Everything is **name-keyed** (the topic-A decision holds), across
two collision-free namespaces (separate dirs). The cached filename
tracks the component's **`name`** (explicit or stem-derived), not
the source's original basename — an explicit `name: "boot"` on a
payload extracted from `144m/FDBOOT.img` caches as `boot.img` — so
the file is always `<name>.<ext>`, `<ext>` from the source
filename/path or the `extension` override. By source kind: a
`url` media downloads straight into `media/`; a from-archive media
caches the archive under `archives/` and the extracted payload
under `media/`; a `local` media attaches in place (nothing
cached). Content addressing was **weighed and declined** — names
stay the key. Intra-invocation name collisions are caught by the
resolution scan; inter-invocation cache aliasing is guarded by
per-use hash verification and isolated when wanted via the
already-orthogonal `--cache` / `RELIQUARY_CACHE_DIR` knob
(decoupled from `--assets`).

The residual exposure is **accepted**: two same-named components
in different projects can alias one cache slot, but hash
verification catches any actual byte mismatch, and the exposure
stays small by design — a reliquary user targets a handful of
systems, not a vast library, so the odds of a genuine name clash
are low. Content addressing's cost (opaque hash-named cache,
against the "cache is not an interface" grain) is not worth paying
to close a rare, already-guarded case. And a clash that does occur
is never blocking: give one component an explicit `name` (names
are overridable everywhere), or isolate with `--cache` — either
resolves it.

## What this supersedes, and the fold ahead

- `.rlqm` retires; media definitions become `media` / `source` /
  `archive` components in `.rlqb`.
- The machine drive model loses `size` / `base` / `hostdir` (a
  drive names a media); `media` owns materialization.
  machine-blueprint.md, its field reference, and the cookbook
  realign.
- media-spec.md folds into this model (its fetch, mismatch, and
  clean prose carry over; `downloads/` → `archives/`).
- The two published JSON Schemas and the conformance corpus
  collapse into one blueprint schema with per-component variants.
- The machine directory reorganizes: `drives/` → `media/` (images
  by media item), backend files into a backend-named subdir,
  `reliquary-machine.json` → `machine.json` with `vm.json` folded
  in. instance-model.md, the ROADMAP home-layout diagram,
  AGENTS.md, the milestone-6 machine-state schema, and
  machines.py / lifecycle.py realign.
- The codex and `planning/examples/` re-author to the composed
  format.
- **Parked wishes:** a succinct extraction short-circuit /
  member-glob convenience (the dropped media-set's job, wanted but
  not now).

## Worked examples

### 1 — nested zip, floppies itemized under one tree

```json
{
  "sources": [
    { "url": ["https://paul.com/PaulsFreedos.zip",
              "https://mirror.example/PaulsFreedos.zip"],
      "sha256": "9f4c…" }
  ],
  "archives": [
    { "source": "PaulsFreedos",
      "members": [
        { "path": "FD14-LiveCD.zip",
          "members": [ { "path": "FD14LIVE.iso", "read-only": true } ] },
        { "path": "FD14-FloppyEdition.zip",
          "members": [
            { "path": "144m/FDBOOT.img"  },
            { "path": "144m/FDSTD01.img" },
            { "path": "144m/FDSTD02.img" },
            { "path": "144m/FDSTD03.img" },
            { "path": "144m/FDSTD04.img" },
            { "path": "144m/FDSTD05.img" },
            { "path": "144m/FDSTD06.img" },
            { "path": "144m/FDSTD07.img" }
          ] }
      ] }
  ],
  "media": [
    { "name": "blank-20m", "materialize": "new", "size": "20M" }
  ],
  "machines": [
    { "name": "freedos-1.4", "platform": "dos", "memory": "16M",
      "drives": { "hdd0": "blank-20m", "cdrom0": null, "floppy0": null },
      "boot": ["cdrom0", "hdd0"] }
  ]
}
```

Yields media `FD14LIVE`, `FDBOOT`, `FDSTD01…07` (+ the explicit
`blank-20m`) and archives `PaulsFreedos`, `FD14-LiveCD`,
`FD14-FloppyEdition`. Only the one `url` carries a `sha256`.

### 2 — differencing over a local VirtualBox snapshot

```json
{ "media": [
    { "name": "vbox-snap", "materialize": "difference",
      "source": { "local": "C:/…/MyVM/Snapshots/{uuid}.vdi" } } ],
  "machines": [
    { "name": "vbox-derived", "platform": "dos", "memory": "64M",
      "drives": { "hdd0": "vbox-snap" }, "boot": ["hdd0"] } ] }
```

reliquary's overlay protects the `.vdi`; local source ⇒ hash
optional.

### 3 — pinned but unlocated "Windows Install CD"

See [Unlocated media](#unlocated-media-non-redistributable) above.
