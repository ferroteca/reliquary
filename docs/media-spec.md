<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# The media spec

> **Status:** this documents the planned media definition format.
> The media library is not implemented yet; details may still
> change before first release.

The media library, `<reliquary_home>/media`, holds
machine-independent media: installer ISOs, boot floppies, driver
disks. Machines reference media by name (the
[`media:` source form](machine-spec-reference.md#source--required--string)),
and every media item is described by a **definition** stating
where its file comes from and how it is verified.

```text
<reliquary_home>/media/
└── freedos-14-livecd.json       a media definition
<reliquary_home>/cache/
├── downloads/
│   └── FD14-LiveCD.zip          a cached source archive
└── media/
    └── freedos-14-livecd.iso    a cached payload file
```

The layout separates what is worth keeping from what is
reconstructible: `media/` holds the definitions — the part worth
sharing and versioning — while its sibling `cache/` holds the
files: `cache/media/` the media files machines actually mount,
and `cache/downloads/` the source archives, cached separately from
the media items themselves.

## Media items

**Every media item has a definition** — a file in `media/`
declaring the item's payload file name, where to download it
from, how to extract it if it arrives inside an archive, and the
hashes that verify it. reliquary can fetch, extract, and verify
defined media on demand, and one definition can itemize several
media files from one source archive.

There is no way to use a media file without a definition:
dropping a bare file into `cache/media/` does nothing — the
cache directories are reliquary's, not an interface. Media that
cannot be downloaded still gets a definition (with no `url`, or
with a [`local-path`](#item-fields) pointing at the file where it
lives); the definition is what names and verifies it.

A `media:<name>` reference in a machine declaration resolves to
the defined item of that name. A name no definition provides is
an error, and a resolved item whose payload is missing or fails
verification is fetched when its definition allows, and is
otherwise an error.

Names are checked eagerly: any command that touches media begins
by scanning every definition in `media/` and **fails fast on a
duplicate item name** — before resolving references, fetching, or
starting a machine. The error names the two definition files and
the colliding name (explicit `name` or defaulted file name), so a
bad library is caught whole rather than whenever the second name
happens to be used.

## The definition format

A definition comes in two forms. There is no version field in
either
([no backward compatibility before beta](machine-spec.md#format-stability-none-yet)).

### Item form — one definition, one item

`media/msdos622-boot.json`:

```json
{
  "name": "msdos622-boot",
  "file": "msdos622-boot.img",
  "sha256": "9f4c2c1e5a7b8d3f2e1a0b9c8d7e6f5a4b3c2d1e0f9a8b7c6d5e4f3a2b1c0d9e",
  "url": "https://mirror.example/msdos/msdos622-boot.img"
}
```

Every item has a `name` — the string `media:` references use.
When `name` is not given explicitly, it is the item's file name
without its extension (`media:msdos622-boot` above, even had
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
`media/freedos-14-livecd.json`:

```json
{
  "archive": "FD14-LiveCD.zip",
  "sha256": "cf3f4c9f2f4d9e70a3a08a52f1c67c0ff01b18cf07a4c0f1a3f5b7e6d1a2b3c4",
  "url": "https://download.freedos.org/1.4/FD14-LiveCD.zip",
  "items": [
    {
      "name": "freedos-14-livecd",
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

The first item is referenced as `media:freedos-14-livecd`; the
second declares no `name`, so its name is its file name without
the extension — `media:FD14BOOT`.

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
  `url`, the payload (or archive) must be placed on disk by hand;
  the definition still names and verifies it — useful for media
  that cannot be downloaded, like your own licensed installer
  ISOs.

### Item fields

Valid per item — at the top level of the item form, or inside
each `items` entry of the archive form:

- **`name`** — optional. The item's name, the string `media:`
  references use. Defaults to the item's file name with its
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
  type-identifying extension: the `freedos-14-livecd` item with
  `"file": "FD14LIVE.iso"` is cached as
  `cache/media/freedos-14-livecd.iso`. (With a defaulted name the
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
  verification is treated as absent (and refetched when a source
  is available — a corrupted cache heals itself).
- **`local-path`** — optional. A custom local path for the payload
  file, in place of the default `cache/media/<file>`. Use it when
  a media item should live (or already lives) somewhere else —
  an ISO collection on another drive, licensed media kept in a
  managed folder:

  ```json
  {"file": "win98se.iso", "local-path": "D:/isos/win98se.iso"}
  ```

  Fetching, extraction, and `sha256` verification behave exactly
  as they would in the cache, just at this path. `file` defaults
  to the location's file-name component, so it can usually be
  omitted alongside `local-path`. A custom local path is outside
  `cache/`, so `clean media` never touches it — the file is the
  user's, wherever it is.
- **`path`** — optional in `items` entries, defaulting to `file`
  (the common case: the archive entry already has the name you
  want to keep). Not valid in the item form, which downloads
  directly. The path of the payload inside the archive.
  Extraction takes exactly this entry as `file` and keeps the
  archive in the downloads cache, where it can be re-extracted
  later without downloading again.

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
`media:msdos622-boot` — identical to the fully spelled-out item
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

Definitions are user-authored; reliquary reads them and never
writes them. There is no state document for media — the payload
file either exists and verifies, or it doesn't.

## Fetching

```text
reliquary fetch <media_name>
```

fetches a defined item explicitly: downloads (if missing or failing
verification), extracts, verifies, reports. Machine operations that
resolve a `media:` reference to a fetchable definition do the same
implicitly, so `fetch` is a convenience for warming the library —
an install script's media is fetched before the machine boots
either way.

Fetch prefers the caches, cheapest source first: a payload that
verifies is used as-is; otherwise a cached archive that verifies
is re-extracted; only then are the mirror URLs tried.

Verification is not optional: an item is never used without its
`sha256` matching, and a failed download or hash mismatch is a
plain error naming the item, the file, and both hashes. In
particular, **every machine `start` re-verifies the hash of every
media item the machine references** before the machine boots — a
payload that no longer verifies is refetched when its definition
allows, and is otherwise an error; a machine never boots against
silently changed media.

## Cleaning

Both payloads and archives are caches — anything with a
definition can be rebuilt from its mirrors — and each has its own
clean command:

```text
reliquary clean downloads
reliquary clean media
```

- `clean downloads` deletes cached source archives. Always safe:
  archives exist only to spare a re-download.
- `clean media` deletes payload files that reliquary can fetch
  again — items whose definition has a `url` (or a cached,
  verifying archive). It never touches definitions, `local-path`
  files, or payloads without a download source: nothing
  irreplaceable is cleanable.

To reclaim everything for an item reliquary can restore, run both;
the next reference to the item fetches it fresh.

## Sharing

Media definitions travel well: a definition file is small,
hash-pinned, and machine-independent, so checking a set of
definitions into version control (or shipping them beside install
scripts) gives everyone the same verified inputs without shipping
the payloads themselves.
