<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# The media spec

> **Status:** the definition core is implemented: both forms with
> their derived defaults, `file-extension`, `local-path`, library
> scanning with duplicate detection, and hash-verified fetching
> and extraction with the mismatched-file contract. Embedded
> `media` blocks parse in scripts; their installation into the
> library, mirror URL lists, the `fetch` and `clean` commands,
> JSONC acceptance, and the definition-level annotation fields
> are not implemented yet; details may still change before first
> release.

The media catalog holds machine-independent media: installer ISOs,
boot floppies, and driver disks. Definitions are authored assets —
`.rlqm` files, identified by extension and discovered anywhere
under the invocation's asset root (the current directory by
default), falling back to the reliquary home unless
`--assets-only` disables the fallback (planning/ROADMAP.md,
"Authored-asset resolution"); a `media/` subdirectory is optional
organizational dressing, the home's own convention included. The
home library is the human
convenience: one shared place for definitions reused across
interactive scenarios. Automation disables the fallback
(`--assets-only`) and resolves strictly project-scoped: neither
home definitions nor the codex behind them can reach an automated
run — a project commits its own copies (the artifact-residency
split, planning/USE-CASES.md). A rlq script may also
embed definitions, installed on first run as `<label>.rlqm`
beside the script — or into the home's `media/` when the script
resolved from the home. Machines reference media by name (the
[`media` drive field](machine-blueprint-reference.md#media--optional--string)),
and every media item is described by a **definition** stating
where its file comes from and how it is verified.

```text
<reliquary_home>/media/
└── freedos-1.4-livecd.rlqm       a media definition
<reliquary_home>/cache/
├── downloads/
│   └── FD14-LiveCD.zip          a cached source archive
└── media/
    └── freedos-1.4-livecd.iso    a cached payload file
```

The layout separates what is worth keeping from what is
reconstructible: `media/` holds shared definitions — the part worth
sharing and versioning — while its sibling `cache/` holds the files:
`cache/media/` the media files machines actually mount, and
`cache/downloads/` the source archives, cached separately from the
media items themselves. A project asset root organizes its
`.rlqm` files however it likes; the caches stay under the home
either way. A definition embedded in a script remains in
that authored script and is also copied into the library on first
run; its downloaded artifacts use the same shared caches.

## Media items

**Every media item has a definition** — a `.rlqm` file, possibly
installed from a labeled `media <label> { ... }` block in a script.
During read-only script checking, embedded blocks are treated as
prospective library additions. A definition declares the item's
payload file name, where to download it from, how to extract it if it
arrives inside an archive, and the hashes that verify it. reliquary
can fetch, extract, and verify defined media on demand, and one
definition can itemize several media files from one source archive.

There is no way to use a media file without a definition:
dropping a bare file into `cache/media/` does nothing — the
cache directories are reliquary's, not an interface, and are
never hand-fed; everything under `cache/` stays reconstructible.
Media that cannot be downloaded still gets a definition, with a
[`local-path`](#item-fields) — item-level, or
[archive-level](#archive-fields) — pointing at the file where
the user keeps it; the definition is what names and verifies it
(U4). A definition may also name no source at all: it then pins
the item's identity and hashes — the form built-in definitions
for non-redistributable media ship in — but cannot resolve.
Resolution fails naming the missing media and the definition to
edit; supplying the payload means adding a `url` or `local-path`
to the definition, never placing files in the cache.

A media name referenced from a machine blueprint resolves to the
defined item of that name. A script run validates and installs all
its embedded definitions before its machine is created or started,
then uses the ordinary shared catalog. A name no definition provides
is an error, and a resolved item whose payload is missing or fails
verification is fetched when its definition allows, and is otherwise
an error.

Names are checked eagerly: any command that touches media begins by
scanning every `.rlqm` under the asset root — and, unless
the fallback is disabled, the home — before resolving
references, fetching, or
starting a machine. Two files in one root with the same item name
are an error; across roots the asset root shadows the home
(identical descriptors coalesce, and run records name which root
supplied each item). Before installing embedded definitions, reliquary compares
their prospective items with the library and one another. An item may
coincide only when its normalized descriptor is identical. The
descriptor includes the payload identity and its direct-source or
archive-source context; unrelated sibling items in an archive
definition do not participate. Any difference is a collision error
naming both locations and the item. Embedded definitions never
override library files. The complete installation rules, including
mixed partially redundant blocks, are in the
[script spec](script-spec.md#installation-into-the-media-library).

## The definition format

A definition comes in two forms. There is no version field in
either
([no backward compatibility before beta](machine-blueprint.md#format-stability-none-yet)).
Both library JSON files and embedded `media` blocks use these exact
forms. In a script, `media <label> {` replaces the JSON object's
outer opening brace; the block body otherwise follows JSON syntax and
closes with the object's `}`. The label determines the installed
file name, `<label>.rlqm`, and carries no item meaning. See
[the script spec](script-spec.md#embedded-media-definitions) for
scope and resolution rules.

Library definition files are authored documents and accept the
JSONC dialect: JSON (RFC 8259) plus `//` and `/* */` comments
and trailing commas in arrays and objects — the dialect editors
already apply to files like `tsconfig.json`, and nothing more
(no unquoted keys, no single-quoted strings, no other JSON5
extensions). Comments are the author's margin notes —
provenance, review context, where a hash came from (U4) — and
carry no meaning: reliquary never reads them, and nothing
normative may live in one; anything the contract needs is a
field. A definition without comments remains valid strict JSON;
one with them is not parseable by strict JSON tooling — a
deliberate trade.

Embedded `media` blocks are strict JSON: no comments, no
trailing commas. The divergence from library files is a named
decision with two reasons — the script grammar closes the JSON
island by tracking its braces, which a comment containing a
brace would break, and installation writes the library copy in
canonical strict JSON, so block comments would silently vanish
from the installed file.

`sha256` values, at every level, are hexadecimal and accepted in
either case; reliquary's canonical writes use lowercase.

The format has a machine-checkable companion: the published JSON
Schema
([media-definition.schema.json](media-definition.schema.json),
beside this spec) captures the per-document structural subset of
the format's rules, for editor completion and validation while
authoring (U4). This prose remains normative, and schema validity
never implies definition validity: library-wide name uniqueness,
cross-definition archive agreement, defaults derived from URL
file names, and every resolution rule live beyond the schema. One
schema covers both homes of a definition — the library file and
the embedded block use the same forms, and the schema validates
the parsed document, so the JSONC dialect is invisible to it.
Editors bind it to `.rlqm` by file association; a definition
carries no `$schema` field pre-beta
([format stability](machine-blueprint.md#format-stability-none-yet)).

### Item form — one definition, one item

`msdos622-boot.rlqm`:

```json
{
  "name": "msdos622-boot",
  "file": "msdos622-boot.img",
  "sha256": "9f4c2c1e5a7b8d3f2e1a0b9c8d7e6f5a4b3c2d1e0f9a8b7c6d5e4f3a2b1c0d9e",
  "url": "https://mirror.example/msdos/msdos622-boot.img"
}
```

Every item has a `name` — the string machine drives reference.
When `name` is not given explicitly, it is the item's file name
without its extension (`msdos622-boot` above, even had
`name` been omitted). The definition's own file name is only a
label for organizing `media/`; it carries no meaning.

The item form is the direct-download form: the URL points at the
media image itself, the download lands directly in `cache/media/`
(as `msdos622-boot.img` here — see the cache-naming rule under
[`file`](#item-fields)), `sha256` verifies it, and the downloads
cache is never involved. A payload that arrives inside an archive always uses
the archive form below — with a single entry in `items` when the
archive contributes only one item.

### Archive form — one definition per source archive

When a source archive contains several files worth naming, one
definition describes the archive once and itemizes them.
`freedos-1.4-livecd.rlqm`:

```json
{
  "archive": "FD14-LiveCD.zip",
  "sha256": "cf3f4c9f2f4d9e70a3a08a52f1c67c0ff01b18cf07a4c0f1a3f5b7e6d1a2b3c4",
  "url": "https://download.freedos.org/1.4/FD14-LiveCD.zip",
  "items": [
    {
      "name": "freedos-1.4-livecd",
      "file": "FD14LIVE.iso",
      "sha256": "6d3b1b4b6b9c4dbd1bcd8e0d640d29aa22a5a04f2a4b0a6a49b1e0f56a5b1c9e"
    },
    {
      "file": "FD14BOOT.img",
      "path": "boot/FD14BOOT.img",
      "sha256": "1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b"
    }
  ]
}
```

The first item is referenced as `freedos-1.4-livecd`; the
second declares no `name`, so its name is its file name without
the extension — `FD14BOOT`.

`sha256` appears at two levels with sibling-scoped meaning: next
to `archive` it verifies the archive; inside an item it verifies
that item's payload file. Likewise `path` is always a location
inside the archive. Item names must be unique across the whole
library, wherever they come from (explicit `name` or defaulted
file name).

*(Hashes above are illustrative, not real pins.)*

One definition per source archive is the natural shape, but not a
rule: several definitions may reference the same `archive` — say,
to keep unrelated item groups in separate files. They must then
agree on the archive's `sha256` and `url`; a disagreement about
the same archive name is an error.

### Archive fields

The top level of the archive form:

- **`archive`** — optional. The archive's file name in the
  downloads cache (`<reliquary_home>/cache/downloads/`), and the
  shared key when several definitions reference one archive. When
  omitted it defaults to the file-name component of the `url` —
  but if the mirror URLs end in different file names, there is no
  single default and the definition must say `archive`
  explicitly; omitting it is then an error. (The `items` key is
  what selects the archive form.)
- **`sha256`** — required. Hex SHA-256 of the archive, verified
  before any extraction.
- **`url`** — optional. Where to download from: a single URL, or
  a list of URLs that are alternates (mirrors) for the same
  artifact:

  ```json
  {"url": ["https://mirror-a.example/FD14-LiveCD.zip",
           "https://mirror-b.example/FD14-LiveCD.zip"]}
  ```

  Mirrors are tried in order; the first successful download that
  passes hash verification wins, and a mirror whose download
  fails or fails verification is simply the cue to try the next.
  Every mirror must serve the identical artifact — the hashes are
  the arbiter, not the URL. In the item form, the URL yields the
  payload itself; in the archive form, the archive. Without a
  `url`, the payload (or archive) must be supplied locally
  through `local-path`; the definition still names and verifies
  it — useful for media that cannot be downloaded, like your own
  licensed installer ISOs (U4).

- **`local-path`** — optional. A local path to the archive file,
  in place of the downloads cache: for archives that cannot be
  downloaded — obtained behind a login, say — or that already
  live in a managed folder. Download (when a `url` is present),
  extraction, and `sha256` verification behave exactly as they
  would in the cache, just at this path. When present, `archive`
  defaults to its file-name component. Relative paths resolve
  exactly like the [item field](#item-fields) of the same name.
  A local archive is outside `cache/`, so `clean downloads`
  never touches it — the file is the user's, wherever it is.

### Item fields

Valid per item — at the top level of the item form, or inside
each `items` entry of the archive form:

- **`name`** — optional. The item's name, the string machine
  drives reference. Defaults to the item's file name with its
  extension dropped (`FD14BOOT.img` → `FD14BOOT`). Must be
  unique across all definitions.
- **`file`** — the payload's original file name — what the
  source calls it. A bare name, no directories. Optional when a
  default exists: from `local-path`'s file-name component, or (in
  the item form) from the `url`'s file-name component — with the
  same mirror caveat as `archive`: mirrors ending in different
  file names have no single default, so `file` must then be
  explicit. Required otherwise (always, in `items` entries
  without `local-path`). In the cache the payload is saved
  as **`<name>` plus `file`'s extension**, preserving the
  type-identifying extension: the `freedos-1.4-livecd` item with
  `"file": "FD14LIVE.iso"` is cached as
  `cache/media/freedos-1.4-livecd.iso`. (With a defaulted name the
  two coincide: `FD14BOOT.img` caches as `FD14BOOT.img`.) Because
  item names are library-unique, naming cache files by item makes
  a filename clash in `cache/media/` impossible — two items may
  freely share the same original `file` name (every vendor ships
  a `boot.img`).
- **`file-extension`** — optional. Overrides the extension
  taken from `file` for the cached payload name: with
  `"file-extension": "img"`, the item caches as `<name>.img`
  regardless of what `file` ends in. For
  sources whose original name misidentifies (or omits) the type —
  the extension is what declares the image format to machine
  drives, so it is worth correcting here.
- **`sha256`** — required. Hex SHA-256 of the payload file. The
  payload is verified against it on every use; a file that fails
  verification is refetched when a source is available and the
  deletion is approved (see
  [mismatched files](#mismatched-files)).
- **`local-path`** — optional. A custom local path for the payload
  file, in place of the default `cache/media/<file>`. Use it when
  a media item should live (or already lives) somewhere else —
  an ISO collection on another drive, licensed media kept in a
  managed folder, a native VM's disk captured in place by
  `import` (whose generated definitions use exactly this form):

  ```json
  {"file": "win98se.iso", "local-path": "D:/isos/win98se.iso"}
  ```

  Fetching, extraction, and `sha256` verification behave exactly
  as they would in the cache, just at this path. `file` defaults
  to the location's file-name component, so it can usually be
  omitted alongside `local-path`. A custom local path is outside
  `cache/`, so `clean media` never touches it — the file is the
  user's, wherever it is.
  A relative path in a library definition resolves from that
  definition file's directory. An embedded definition resolves it
  from the containing script's directory and installs the resulting
  absolute path, preserving its meaning after the copy.
- **`path`** — optional in `items` entries, defaulting to `file`
  (the common case: the archive entry already has the name you
  want to keep). Not valid in the item form, which downloads
  directly. The path of the payload inside the archive.
  Extraction takes exactly this entry as `file` and keeps the
  archive in the downloads cache, where it can be re-extracted
  later without downloading again.

### Definition-level fields

Valid at the top level of either form, alongside the fields
above:

- **`description`** — optional. A one-line human description of
  the definition, read into listings and `search` exactly like a
  blueprint's `description` (see
  [the codex](codex.md)).
- **`notes`** — optional. Free-form prose for anything longer:
  provenance, licensing context, why a particular mirror.
  reliquary never interprets it.
- **`redistributable-under`** — optional. The explicit assertion
  that the payload's own licensing permits redistribution,
  naming the license (`"GPL-2.0-or-later"`, say). Its presence
  is the assertion; reliquary records and displays it but cannot
  verify a license. A built-in definition may carry a `url` only
  when it also carries this field — the
  [codex's licensing rule](codex.md#non-redistributable-media).

### Derived defaults, worked through

`name`, `file`, and `archive` are all derivable, and the chains
compose. Derivation order: `url` (or `local-path`) → `file` →
`name` → cached file name.

A minimal item form — only a hash and a URL:

```json
{
  "sha256": "9f4c2c1e5a7b8d3f2e1a0b9c8d7e6f5a4b3c2d1e0f9a8b7c6d5e4f3a2b1c0d9e",
  "url": "https://mirror.example/msdos/msdos622-boot.img"
}
```

- `file` ← the URL's file-name component: `msdos622-boot.img`
- `name` ← `file` minus its extension: `msdos622-boot`
- cached as ← `<name>` + `file`'s extension:
  `cache/media/msdos622-boot.img`

So this two-field definition is referenced as
`msdos622-boot` — identical to the fully spelled-out item
form example above.

A minimal local item — a hash and a local path:

```json
{
  "sha256": "b1946ac92492d2347c6235b4d2611184a1e5d2c383a3a0522f9d21ac96f78c40",
  "local-path": "D:/isos/win98se.iso"
}
```

- `file` ← `local-path`'s file-name component: `win98se.iso`
- `name` ← `win98se`
- no cache entry — the payload stays at `D:/isos/win98se.iso`

A minimal archive form — archive and item names all derived:

```json
{
  "sha256": "cf3f4c9f2f4d9e70a3a08a52f1c67c0ff01b18cf07a4c0f1a3f5b7e6d1a2b3c4",
  "url": "https://download.freedos.org/1.4/FD14-LiveCD.zip",
  "items": [
    {"file": "FD14LIVE.iso",
     "sha256": "6d3b1b4b6b9c4dbd1bcd8e0d640d29aa22a5a04f2a4b0a6a49b1e0f56a5b1c9e"},
    {"file": "FD14BOOT.img",
     "sha256": "1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b"}
  ]
}
```

- `archive` ← the URL's file-name component: `FD14-LiveCD.zip`,
  cached as `cache/downloads/FD14-LiveCD.zip`
- each item's `path` ← its `file` (the archive entries sit at the
  root under their own names)
- names ← `FD14LIVE` and `FD14BOOT`; cached as
  `cache/media/FD14LIVE.iso` and `cache/media/FD14BOOT.img`

Inside `items`, `file` cannot be derived — nothing else names the
archive entry — so it is the one field (besides `sha256`) an
archive item always states.

When a derivation has no single answer, the field must be
explicit: mirror URLs ending in different file names break the
`url` → `archive` and `url` → `file` defaults, and a defaulted
`name` that collides with another item's is caught by the
duplicate scan — give one of them a `name`.

Definitions are authored documents. Reliquary normally reads but
never writes them; the one deliberate exception is installing a
missing definition from a script before its first run. The new file
uses canonical JSON formatting and immediately becomes an ordinary
user-owned library document: reliquary never updates or deletes it
implicitly. There is no state document for media — the payload file
either exists and verifies, or it doesn't.

## Fetching

```text
rlq fetch <media_name> [--script <script_name>]
```

fetches a defined item explicitly: downloads (if missing or failing
verification), extracts, verifies, reports. Machine operations that
resolve a media reference to a fetchable definition do the same
implicitly, so `fetch` is a convenience for warming the library —
an install script's media is fetched before the machine boots
either way. Without `--script`, `fetch` sees the shared library.
With it, fetch validates and installs that script's embedded
definitions using the same rules as script execution, then fetches
the named item; it does not execute guest steps or start a machine.

Fetch prefers what is already on disk, cheapest source first: a
payload that verifies is used as-is; otherwise a cached (or
`local-path`) archive that verifies is re-extracted; only then
are the mirror URLs tried.

The embedding API counterpart is
`fetch_media(name, home=None, script=None, on_mismatch="fail")`,
with `script` mirroring `--script` — the CLI and the API move
together (planning/INTERFACES.md). `fetch_media` is the blocking
form: a typed result, errors raised by class. Its asynchronous
twin `start_fetch(...)` (same parameters) returns a pull-only
fetch handle — `status()`, `events(follow=)` as a blocking
iterator over the same event kinds
([fetch progress](#fetch-progress)), `wait(timeout=)` returning
the blocking form's result, and `cancel()`, which aborts at the
next event boundary and deletes the partial download (no
pre-existing file is touched) — no callbacks, nothing a common
binding language cannot express. A fetch stream is ephemeral, so
a handle lives only in the process that started it — there is no
attach-by-id; reattachment is what run records exist to provide.
The handle form is noninteractive by construction:
`on_mismatch="prompt"` is rejected, so a background fetch can
never hang on a hidden prompt.

Verification is not optional: an item is never used without its
`sha256` matching, and a failed download or hash mismatch is a
plain error naming the item, the file, and both hashes. In
particular, **every machine `start` re-verifies the hash of every
media item the machine references** before the machine boots — a
payload that no longer verifies is refetched when its definition
allows and the deletion is approved (below), and is otherwise an
error; a machine never boots against silently changed media
(U1, U4).

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
- **Standalone `fetch`** renders them itself. `--progress
  (auto | tty | plain | rawjson)` selects the rendering exactly
  as on `script`: pretty, live progress on a tty under `auto`;
  under `rawjson`, stdout carries the event stream as JSON lines
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
are noninteractive exactly as on `script`: under `plain` and
`rawjson` the [mismatched-file checkpoint](#mismatched-files)
below never prompts — an unapproved mismatch fails fast, the
documented programmatic behavior — while `auto`/`tty` map it to
the interactive checkpoint.

### Mismatched files

An existing payload or cached archive that fails its hash is
never silently discarded — the file may be evidence, or the
definition may simply be wrong. What happens instead depends on
how reliquary is running:

- **Interactively**, the mismatch is a checkpoint: reliquary asks
  (`Existing file <path> does not match its defined hash … Delete
  it and fetch again? [y/N]`) and only deletes and refetches on a
  yes. Declining keeps the file and fails the operation.
- **Programmatically** (and whenever input is not a terminal),
  the mismatch fails fast with an error naming the file and both
  hashes.
- The deletion can be **pre-approved**: the CLI flag
  `--refetch-mismatched` on commands that fetch media, or the
  embedding API's `on_mismatch="refetch"` option
  (`fetch_media(name, home=None, script=None,
  on_mismatch="fail")`; the CLI maps interactive runs to
  `"prompt"`).

A mismatched file whose definition names no source is always kept
and reported — with nothing to refetch from, deleting it could
destroy the only copy.

A *freshly downloaded or extracted* file that fails verification
is not a checkpoint: the partial result is deleted and the
failure reported; no pre-existing file is touched.

## Cleaning

Both payloads and archives are caches — anything with a
definition can be rebuilt from its mirrors — and each has its own
clean command:

```text
rlq clean downloads
rlq clean media
```

- `clean downloads` deletes cached source archives. Always safe:
  archives exist only to spare a re-download.
- `clean media` deletes payload files that reliquary can fetch
  again — items whose definition has a `url` (or a cached — or
  local — verifying archive). It never touches definitions,
  `local-path` files, or payloads without a download source:
  nothing irreplaceable is cleanable. (A hand-supplied payload
  is always a `local-path` file, outside the cache's reach.)

To reclaim everything for an item reliquary can restore, run both;
the next reference to the item fetches it fresh. The API
counterparts are `clean_downloads(home=None)` and
`clean_media(home=None)`.

## Sharing

Media definitions travel well: they are small, hash-pinned, and
machine-independent. A definition may be distributed directly under
`media/` or embedded in a script and installed into the recipient's
library on first run. The latter produces a more self-contained
script bundle without changing the persistent catalog, cache, or
verification model. Either form gives everyone the same verified
inputs without shipping the payloads themselves (U4).
