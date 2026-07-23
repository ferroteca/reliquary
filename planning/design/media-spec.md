<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# The media spec

> **Status:** the media, source, and archive components are
> implemented: the four `materialize` modes, `size`, locators
> (`url`+mirrors / `local` / from-archive / by-name), conditional
> `sha256` (required on `url`), `read-only`, `extension`, recursive
> archive trees, unknown-key rejection, namespace resolution with
> collision detection, hash-verified fetch and extraction with the
> mismatched-file contract, JSONC acceptance, and the `fetch-media`
> and `clean-` commands. Details may still change before first
> release; the component model is worked out in
> [the composed blueprint model](blueprint-model.md).

Media are the machine-independent payloads a machine mounts:
installer ISOs, boot floppies, driver disks. In the composed
blueprint model they are **components inside the one authored
`.rlqb`** — `media`, and the `source` and `archive` components that
locate and extract them — not a file kind of their own (`.rlqm`
retires). A machine's drive names a `media` by name (the
[`media` drive field](machine-blueprint-reference.md#media--optional--string));
the media owns everything about the payload: where it comes from,
how it is verified, and how it materializes.

Resolution reads the whole source: every `.rlqb` in the active
source is parsed into one `(name, type)` namespace, and references
bind by name. In home mode (the CLI default) that is the whole home,
seeding from the codex on a miss; under `--assets <dir>` it is the
whole project root — the sole hermetic source, where neither home
components nor the codex behind them reach an automated run (the
artifact-residency split, planning/USE-CASES.md). Two media of one
name within a source are a collision error naming both.

```text
<asset root>/…/freedos.rlqb        machine + media + archive components
<reliquary_home>/cache/
├── archives/
│   └── FD14-LiveCD.zip            a cached source archive
└── media/
    └── freedos-1.4-livecd.iso     a cached payload file
```

The cache holds two collision-free, name-keyed namespaces:
`cache/media/` the payload files machines mount, `cache/archives/`
the source archives they were extracted from. Both are entirely
reconstructible — nothing there is authored or hand-fed; a bare file
dropped into either does nothing, because the caches are reliquary's,
not an interface.

## The media component

A `media` component owns all content and materialization.

### `name`

The string machine drives and script `insert`s reference. Explicit,
or defaulted from the `source` filename or archive-member path stem
(`144m/FDBOOT.img` → `FDBOOT`). A media with no filename-bearing
source — a `new` blank — **must** name itself; there is nothing to
derive from. Media names must be unique within a resolution source.

### `materialize`

How the drive is realized from the payload; default `use`:

| value | meaning | needs |
|---|---|---|
| `new` | a fresh blank image of `size` | `size`; **no** `source` |
| `difference` | a writable overlay over the payload (payload untouched) | `source` |
| `copy` | the payload duplicated into a standalone image | `source` |
| `use` | attach the payload itself (mutable unless `read-only`) | `source` |

`use` / `difference` / `copy` require a `source`; a `use` with no
source is a validation error. `new` takes `size` and forbids
`source`. `new` / `difference` / `copy` materialize a per-machine
image under `cache/machines/<id>/media/<name>.<ext>` (named for the
media, not the slot); `use` attaches the shared payload — the
`cache/media/` file, the `local` file, or the `hostdir` directory —
**directly**, with no per-machine copy. This is what a machine
drive's declaration reaches: **to change how a drive materializes,
change (or point at a different) media.**

### `size`

`new` only. A positive integer with a binary unit suffix
(`K` / `M` / `G` / `T`, powers of 1024): `"20M"`, `"1440K"`.

### `source`

Where the payload comes from — a **locator**
([below](#sources-and-locators)). Absent only for a `new` media.

### `sha256`

The payload's hash, verified on every use. **Required when the
source is a `url`** (remote, untrusted); optional for `local` and
from-archive sources. Optional is a feature: a `local` media may
omit it to attach a drive image you are still *evolving* (a pin
would fail on every edit); hermetic workflows add the hash when they
want the pin. The hash is the build pin *independent of the source
kind* — a trusted `local` source can still verify the media is the
exact build the scripts target. Hex, accepted in either case;
reliquary's canonical writes are lowercase.

### `read-only`

Present the drive read-only so a floppy or hard disk is not
corrupted; orthogonal to `materialize`. **Defaults true on a
cdrom** (no backend meaningfully writes a virtual ISO, so a writable
cdrom is rejected), opt-in elsewhere; for a directory source it
protects the host directory.

### `extension`

Override the type-declaring extension of the cached payload when the
source filename misnames it (or omits it) — the extension is what
declares the image format to machine drives. Otherwise derived from
the source filename or archive-member `path`.

**hostdir is a payload shape, not a mode:** a media whose `source`
is a host *directory* with `materialize: use` is the live vvfat
attach — the guest reads and writes it like a disk, the directory
reflecting its writes by machine stop (live on QEMU's vvfat). While
the machine is stopped the directory *is* the drive's content, an
ordinary host directory to prepare or harvest with any tool
(out-of-band exchange, [instance model](instance-model.md)). Nothing
is hash-checked — the directory trades verification for liveness,
where a pinned payload is the reproducible path — and one directory
should not be shared by concurrently running machines. A relative
directory resolves against the invocation's asset root, so a
checked-in blueprint stays portable; a directory that does not exist
fails closed naming the path.

## Sources and locators

A media's `source`, and a standalone `source` component, is a
**locator**.

### Locators

A locator says where bytes come from. It is one of:

- a **string** naming a `source` (or `archive`) component;
- an inline **`{ "url": … }`** — a single URL, or a list of URLs
  that are alternates (mirrors) for the identical artifact; the
  (required) `sha256` is the arbiter, not the URL;
- an inline **`{ "local": … }`** — a path on disk (relative paths
  resolve from the referencing file's directory); the user's own
  file, outside the cache;
- an inline **from-archive** `{ "archive": "<name>", "path":
  "<member>" }` — extract a member from a named `archive`.

A `url` locator's mirrors are tried in order; the first download
that passes hash verification wins, a failing mirror is simply the
cue to try the next. Every mirror must serve the identical artifact.

### The `source` component

A **`source` component** (the `sources` section) is a named,
standalone locator — the same locator schema hoisted so it can be
supplied or replaced independently of the media that pins the
payload's hash. Its name defaults to the URL / local filename stem.
Mirror lists live here naturally:

```json
{ "sources": [
    { "url": ["https://paul.com/PaulsFreedos.zip",
              "https://mirror.example/PaulsFreedos.zip"],
      "sha256": "9f4c…" } ] }
```

## Archives — the recursive tree

An **archive** is a container: a `source` (where the archive bytes
are) plus recursive **`members`**. The tree mirrors the physical
nesting, and its shape *is* the extraction:

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
          ] } ] } ] }
```

- The root `source` names a `sources` component (or is an inline
  locator). Each internal node becomes an **archive** cached under
  `cache/archives/`; each leaf becomes a **media** cached under
  `cache/media/`.
- **Names default to stems** at every level (`PaulsFreedos`,
  `FD14-FloppyEdition`, `FDBOOT`, `FDSTD01`, …); any node or leaf
  takes an explicit `name`, and a leaf may set `materialize` /
  `read-only` / `sha256` / `extension` like any media (default
  `use`).
- **Members are itemized explicitly** — every payload its own line —
  but the archive chain is declared once. Nesting is unbounded and
  needs no special chaining syntax: one `url` high in the tree
  downloads once, and every descendant extracts from the cached
  parent.

A single payload is just a one-leaf tree, or a media whose `source`
is a from-archive locator naming an existing `archive`.

The single-archive FreeDOS media, written as a tree:

```json
{
  "archives": [
    {
      "name": "FD14-LiveCD",
      "source": {
        "url": "https://download.freedos.org/1.4/FD14-LiveCD.zip",
        "sha256": "cf3f…"
      },
      "members": [
        {
          "path": "FD14LIVE.iso",
          "name": "freedos-1.4-livecd",
          "read-only": true,
          "sha256": "6d3b…"
        }
      ]
    }
  ]
}
```

The leaf becomes the media `freedos-1.4-livecd`, extracted from
`FD14LIVE.iso` inside the cached `FD14-LiveCD` archive and cached as
`cache/media/freedos-1.4-livecd.iso`. *(Hashes truncated for
readability.)*

## Unlocated media (non-redistributable)

A media may pin its `sha256` and name a `source` that nothing
supplies yet — the licensed / non-redistributable case (built-in
codex media ship this way, [the codex's licensing
rule](codex.md#non-redistributable-media)). Resolution **fails
closed** naming the media and the missing source until the user
provides it, **without editing the seeded media**: the media
references its source by name, and the user drops a matching
`source` component beside it.

```jsonc
// shipped (codex / shared): pinned, unlocated
{ "media": [
    { "name": "windows-install-cd", "read-only": true,
      "sha256": "exact-build-hash…", "source": "windows-cd-location" } ] }

// the user supplies it, without touching the media above:
{ "sources": [
    { "name": "windows-cd-location", "local": "D:/isos/en_windows.iso" } ] }
```

The media's `source` string and the `source` component's `name` must
match; two sources of one name within a source must agree, else it
is a collision error. Supplying the payload always means adding a
`source` (or a `url` / `local` on the media), never placing files in
the cache.

## The format

Authored components accept the JSONC dialect: JSON (RFC 8259) plus
`//` and `/* */` comments and trailing commas — the dialect editors
apply to files like `tsconfig.json`, and nothing more. Comments are
the author's margin notes (provenance, review context, where a hash
came from) and carry no meaning; anything the contract needs is a
field. There is no version field and no `$schema` in a document
([no backward compatibility before beta](machine-blueprint.md#format-stability-none-yet)).

The machine-checkable companion is the one published
[blueprint-schema-v1.json](../../reliquary/schemas/blueprint-schema-v1.json)
— the machine, media, source, and archive components in one schema.
It captures the per-document structural subset of the format's
rules, for editor completion while authoring; this prose stays
normative, and schema validity never implies validity: name
uniqueness, cross-file agreement, stem-derived defaults, the
`sha256`-required-on-`url` rule, medium compatibility, and every
resolution rule live beyond the schema. Editors bind it to `.rlqb`
by file association.

## Fetching

```text
rlq fetch-media <media_name>
```

fetches a media by name: downloads (if missing or failing
verification), extracts through its archive tree, verifies, reports.
Machine operations that resolve a media reference do the same
implicitly, so `fetch-media` is a convenience for warming the cache
— an install script's media is fetched before the machine boots
either way. `fetch-media` resolves against the same namespace every
command sees.

Fetch prefers what is already on disk, cheapest source first: a
payload that verifies is used as-is; otherwise a cached (or `local`)
archive that verifies is re-extracted; only then are the mirror URLs
tried.

The embedding API counterpart is
`fetch_media(name, context=None, on_mismatch="fail")` — the CLI and
the API move together (planning/INTERFACES.md). `fetch_media` is the
blocking form: a typed result, errors raised by class. Its
asynchronous twin `start_fetch(...)` (same parameters) returns a
pull-only fetch handle — `status()`, `events(follow=)` as a blocking
iterator over the same event kinds
([fetch progress](#fetch-progress)), `wait(timeout=)` completing
exactly as the blocking form — same result, same raises, expiry
raising outside the error taxonomy (Python: the builtin
`TimeoutError`) with the fetch still live and the call
repeatable — and `cancel()`, which aborts at the
next event boundary and deletes the partial download (no
pre-existing file is touched) — no callbacks, nothing a common
binding language cannot express. A fetch stream is ephemeral, so
a handle lives only in the process that started it — there is no
attach-by-id; reattachment is what run records exist to provide.
Nor is there a CLI command: `start_fetch` is the one async
starter without one, because for a CLI driver the `fetch-media`
process itself is the handle — background it and read
`--progress jsonl` (planning/design/api.md, the async-starter
convention).
A handle is a follower, never the owner: dropping it never
cancels — the fetch runs to completion unless `cancel()` is
called.
The handle form is noninteractive by construction:
`on_mismatch="prompt"` is rejected, so a background fetch can
never hang on a hidden prompt.

Verification is not optional: a payload is never used without its
`sha256` matching (when one is pinned), and a failed download or
hash mismatch is a plain error naming the media, the file, and both
hashes. In particular, **every machine `start` re-verifies the hash
of every media the machine references** before the machine boots — a
payload that no longer verifies is refetched when its source allows
and the deletion is approved (below), and is otherwise an error; a
machine never boots against silently changed media (U1, U4).

### Fetch progress

Fetching is reliquary's longest operation outside a run, and it
reports progress under the same feedback model as script runs
(the feedback split, planning/USE-CASES.md): one event
vocabulary, every surface a renderer of it. Media movement —
download, extraction, verification — emits the same transfer
and verification event kinds the run-event stream defines
([script spec](script-spec.md)), wherever it happens:

- **Inside a script run**, the events ride the run's own stream;
  followers of the run see the fetch as part of it.
- **Standalone `fetch-media`** renders them itself. `--progress
  (auto | pretty | plain | jsonl)` selects the rendering exactly
  as on `run-script`: pretty, live progress under `auto` when
  stderr is a tty, the human modes drawing entirely on stderr
  with stdout left empty (the CLI output discipline,
  planning/ROADMAP.md "The CLI");
  under `jsonl`, stdout carries the event stream as JSON lines
  and nothing else, the last line the terminal event stating the
  outcome. The stream is ephemeral — media has no state document
  and there is no fetch record: nothing persists, and there is
  nothing to reattach to. Run records remain the only recorded
  outputs.
- **Machine operations that fetch implicitly** outside a run —
  `create`, `start`, `apply`, and `recreate` resolving,
  verifying, and fetching referenced media — render the same
  events in their own output under the same defaults. Their full
  output contract belongs to the general CLI output discipline,
  settled separately.

Progress is honest: a download shows byte totals only when the
source names them, hashing and extraction render as elapsed-only
phases with no invented denominators, and each mirror attempt is
its own event, so a follower sees the walk. The renderer modes
are noninteractive exactly as on `run-script`: under `plain` and
`jsonl` the [mismatched-file checkpoint](#mismatched-files)
below never prompts — an unapproved mismatch fails fast, the
documented programmatic behavior — while `auto`/`pretty` map it to
the interactive checkpoint.

### Mismatched files

An existing payload or cached archive that fails its hash is
never silently discarded — the file may be evidence, or the
media may simply pin the wrong hash. What happens instead depends on
how reliquary is running:

- **Interactively**, the mismatch is a checkpoint: reliquary asks
  (`Existing file <path> does not match its pinned hash … Delete
  it and fetch again? [y/N]`) and only deletes and refetches on a
  yes. Declining keeps the file and fails the operation.
- **Programmatically** (and whenever input is not a terminal),
  the mismatch fails fast with an error naming the file and both
  hashes.
- The deletion can be **pre-approved**: `--on-mismatch refetch`
  on commands that fetch media — the flag mirrors the twin's
  parameter under the twin-name identity rule — or the embedding
  API's `on_mismatch="refetch"` option
  (`fetch_media(name, context=None, on_mismatch="fail")`; the CLI
  accepts `fail | refetch` explicitly and maps interactive runs
  without the flag to `"prompt"`).

The `"prompt"` value is selected, never inferred (owner,
2026-07-21): a library never prompts by default — passing
`on_mismatch="prompt"` is the caller explicitly delegating the
checkpoint to the tty. The blocking form's default stays
`"fail"`, `start_fetch` rejects `"prompt"`, and the `plain` /
`jsonl` renderings never pass it.

A mismatched file whose media names no source is always kept and
reported — with nothing to refetch from, deleting it could destroy
the only copy.

A *freshly downloaded or extracted* file that fails verification
is not a checkpoint: the partial result is deleted and the
failure reported; no pre-existing file is touched.

## Cleaning

Both payloads and archives are caches — anything with a source can
be rebuilt from its mirrors — and each has its own clean command:

```text
rlq clean-downloads
rlq clean-media
```

- `clean-downloads` deletes cached source archives (under
  `cache/archives/`). Always safe: archives exist only to spare a
  re-download.
- `clean-media` deletes payload files reliquary can fetch again —
  media whose source is a `url` (or a cached, or `local`, verifying
  archive). It never touches `local` source files or payloads
  without a download source: nothing irreplaceable is cleanable.

To reclaim everything for a media reliquary can restore, run both;
the next reference fetches it fresh. The API counterparts are
`clean_downloads(context=None)` and `clean_media(context=None)`.

## Sharing

Media travel inside the blueprint: a `.rlqb` carries its `media`,
`source`, and `archive` components alongside the machine that uses
them, so sharing the blueprint shares the verified inputs — small,
hash-pinned, and machine-independent — without shipping the payloads
themselves (U4). A component reused across several blueprints is
written once and referenced by name; the residency split decides
which source supplies it. What crosses the wire is the pinned
identity, never the licensed bytes.
