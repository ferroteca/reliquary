<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# The media spec

> **Status:** implemented. Media are specs inside a `.rlqb`: the
> four `materialize` modes, `size`, the one `location` field and its
> grammar, conditional `sha256`, `read-only`, `extension`,
> parent/children containment, unknown-key rejection, catalog
> resolution with identity dedup and collision detection,
> hash-verified fetch and extraction with the mismatched-file
> contract, JSON5 acceptance, and the media command family.
>
> **This document covers acquisition** — where a payload comes from
> in practice, how it is verified, and how the cache behaves. The
> format's normative model — the root shape, spec identity, the
> location grammar, containment, and the reference closure — is
> [the composed blueprint model](blueprint-model.md), and is not
> restated here. Stating the same model in two documents is how a
> spec comes to contradict itself (D32).

Media are the machine-independent payloads a machine mounts:
installer ISOs, boot floppies, driver disks. They are **specs inside
the one authored `.rlqb`**, not a file kind of their own (`.rlqm`
retires). A machine's drive names a media by name — or carries one
written in place — and the media owns everything about the payload:
where it comes from, how it is verified, and how it materializes.

Resolution reads the whole source: every `.rlqb` in the blueprints
directory, walked recursively, is parsed into one `(name, type)`
catalog, and references bind by name. That directory is the home's
`blueprints/` folder by default and a project's own tree where
`--blueprints-dir` says so; a miss never falls back to the codex, on
either surface, so nothing outside a project's source control
reaches a run at all (the artifact-residency split,
ARCHITECTURE.md P4).

```text
<asset root>/…/freedos.rlqb        the machine and the media it draws on
<reliquary_home>/cache/media/
├── freedos-livecd-zip.zip         the container, cached by its name
└── freedos-livecd.iso             the payload read out of it
```

One name-keyed cache holds every payload, keyed by the name of the
media it *is* — a container is a media like any other, so there is
no second directory for containers. It is **entirely
reconstructible**, without exception: nothing enters it except by
download or extraction, so no payload there is irreplaceable and
reclamation never has to ask where a file came from (D41). A bare
file dropped into the directory does nothing: the cache is
Reliquary's, not an application surface.

## The media component

A `media` component owns all content and materialization.

### `name`

The string machine drives and script `insert` statements reference
it by. It's given explicitly, or derived from content — from a
location's filename, or from the last segment of a containment
path — repaired to fit the name charter, with a warning, when it has
to be (`144m/FDBOOT.img` becomes `FDBOOT`). A media with no
filename-bearing content — a blank — **must** name itself, with one
exception: a content-free blank written in place at a drive belongs
to no namespace at all, and takes its slot's name when materialized.
Identity is the pair `(name, type)` in one catalog: identical specs
can coexist across files, specs that differ collide, and names
collide case-insensitively.

### `materialize`

How the drive is realized from the payload; default `use`:

| value | meaning | needs |
|---|---|---|
| `new` | a fresh blank image of `size` | `size`; **no** `location` |
| `difference` | a writable overlay over the payload (payload untouched) | `location` |
| `copy` | the payload duplicated into a standalone image | `location` |
| `use` | attach the payload itself (mutable unless `read-only`) | `location` |

`use` / `difference` / `copy` require a `location`; one without is a
validation error. `new` takes `size` and forbids `location` — and a
spec carrying `size` and no `location` *is* `new`, which is what
lets the drive-inline blank be written `{"size": "20M"}`. `new` / `difference` / `copy` materialize a per-machine
image under `cache/machines/<id>/disks/<name>.<ext>` (named for the
media, not the slot); `use` attaches the shared payload — the
`cache/media/` file, the `local` file, or the directory a
location names — **directly**, with no per-machine copy. A
machine's drive declaration only ever points at a media by name —
it has no materialize setting of its own. **So to change how a
drive materializes, you change the media it names, or point the
drive at a different media.**

### `size`

`new` only. A positive integer with a binary unit suffix
(`K` / `M` / `G` / `T`, powers of 1024): `"20M"`, `"1440K"`.

### `location`

Where the payload comes from. One field, one grammar — specified in
[the composed blueprint model](blueprint-model.md#the-location-grammar);
[below](#where-a-payload-comes-from) is what each shape costs at
fetch time. Absent only for a blank.

### `sha256`

The payload's hash, verified on every use. **Required once the
rung is remote** (an untrusted source); optional for local and
derived payloads. The check happens at resolution rather than parse,
since a referenced rung may resolve to a URL. Being optional is
deliberate: a local media may leave `sha256` out so you can attach a
drive image you're still *evolving* (a pinned hash would fail on
every edit); a hermetic workflow — one that wants a fully
reproducible, pinned build — adds the hash when it wants that
guarantee. The hash pins the build independent of where the payload
comes from: even a trusted local payload can use it to verify the
media is the exact build the scripts target. Hex, accepted either
case; Reliquary's own canonical writes are lowercase.

### `read-only`

Present the drive (or share, F68) read-only so a floppy, hard disk,
or shared directory is not corrupted; orthogonal to `materialize`.
**Defaults true on a cdrom** (no backend meaningfully writes a
virtual ISO, so a writable cdrom is rejected), opt-in elsewhere; for
a directory payload it protects the host directory.

### `extension`

Override the type-declaring extension of the cached payload when the
location's filename misnames it (or omits it) — the extension is
what declares the image format to machine drives. Otherwise derived
from the location's filename or its containment path.

**A host directory is a payload shape, not a separate mode:** a
media's `location` may name a host *directory*, with `materialize:
use` — the payload is the directory itself, the same way it may be a
single file. Which *device* may carry that payload, and what the
guest and host each see of it while the machine runs, is decided at
the device layer, not here: only a `share` slot accepts a directory
payload (F68); a drive slot refuses one at resolution
(docs/spec/blueprint-model.md's `share` keys, and
[share-devices.md](../../planning/pledged/design/share-devices.md)
for the live mechanisms and their contracts). The one thing every
mechanism agrees on: while the machine is stopped, the directory is
just an ordinary host directory — prepare it or read what's in it
with any tool you like (out-of-band exchange, [instance
model](instance-model.md)). Nothing about it is hash-checked — a
directory gives up the guarantee a pinned, hash-verified payload
gives you, in exchange for being writable — and one directory should
never be shared between machines running at the same time. A
relative directory path resolves against the invocation's asset
root, so a checked-in blueprint stays portable; a directory that
doesn't exist fails with an error naming the path.

## Where a payload comes from

The `location` grammar — the interpreted string forms, their object
desugarings, mirror lists, and `${media:…}` containment — is
specified in
[the composed blueprint model](blueprint-model.md#the-location-grammar),
along with [parent/children containment](blueprint-model.md#containment-parent-and-children).
What matters for acquisition is what each shape costs at fetch time:

- A **remote** rung downloads once into `cache/media/<name>.<ext>`
  and is verified against the media's `sha256`, which is required
  once any rung is remote. Mirror rungs are tried in order; the
  hash, not the URL, decides whether a download is correct, so a
  failing mirror is simply the cue to try the next one.
- A **local** payload is used **in place** and never copied into the
  cache. Its hash is optional, which is the point: a drive image you
  are still evolving would fail a pin on every edit.
- A **contained** payload is extracted from its parent, which is
  fetched first, by these same rules — so one remote rung high in a
  tree downloads once, and every descendant derives from that
  cached parent. Only certain container formats can actually be read
  from — zip, today — and an unsupported format fails with an error
  naming the format it found.
- A **property-supplied** location resolves through the property
  chain at `create` / `apply`, never at `start`.

### Supplying what the project cannot distribute

A codex blueprint may name the build its scripts target without
naming anywhere to get it — the licensed, non-redistributable case
([the codex's licensing rule](codex.md#non-redistributable-media)).
The user supplies the payload themselves, in one of two ways:

- **`add-media <name> <file>`** — the CLI command that writes into
  the home directory. It computes the
  file's `sha256` and writes a `blueprints/<name>.rlqb` declaring
  a
  media located at that file. The file is **not copied**: the
  declaration points at it where it sits, and the result is an
  ordinary blueprint the user owns and can edit (D41). **Nothing
  ever enters the cache from outside** — the cache holds only what
  Reliquary can fetch or derive again.
- **A property-valued location** — the project and CI path, and the
  hermetic one: the committed hash still determines the input, and
  the path that supplies it is per-run.

Editing your own seeded copy is always available and is not a last
resort — that is what seeding is for, and never-overwrite seeding is
what makes the copy safe to edit. A pin that does not match the
build you legitimately hold is your copy's to change.

## Fetching

```text
rlq fetch-media <media_name>
```

fetches a media by name: downloads (if missing or failing
verification), extracts down through its containment chain,
verifies, reports.
Machine operations that resolve a media reference do the same
implicitly, so `fetch-media` is a convenience for warming the cache
— an install script's media is fetched before the machine boots
either way. `fetch-media` resolves against the same namespace every
command sees.

Fetch prefers what is already on disk, cheapest source first: a
payload that verifies is used as-is; otherwise a cached (or `local`)
container that verifies is re-extracted; only then are the mirror
rungs tried.

The embedding API counterpart is
`fetch_media(name, context=None, on_mismatch="fail")` — the CLI and
the API move together (planning/SURFACES.md). `fetch_media` is the
blocking form: a typed result, errors raised by class. Its
asynchronous twin `start_fetch(...)` is **not scheduled** (D35 —
asynchronous work was taken off the project's planned schedule for
lack of a use case to justify it; the demand exists only as the
draft use case U19; proposed/FEATURES.md "Asynchronous runs"); the
blocking `fetch_media` and its foreground `--progress` rendering
stay in milestone 9. The design is already settled, for when it
returns:
`start_fetch(...)` (same parameters) returns a
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
`--progress jsonl` (docs/spec/api.md, the async-starter
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

Fetching is Reliquary's longest operation outside a run, and it
reports progress under the same feedback model as script runs
(the feedback split, ARCHITECTURE.md P5): one event
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
  docs/spec/cli.md);
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
its own event, so anyone following along sees each mirror being
tried in turn. The renderer modes
are noninteractive exactly as on `run-script`: under `plain` and
`jsonl` the [mismatched-file checkpoint](#mismatched-files)
below never prompts — an unapproved mismatch fails fast, the
documented programmatic behavior — while `auto`/`pretty` map it to
the interactive checkpoint.

### Mismatched files

An existing cached payload or container that fails its hash is
never silently discarded — the file may be evidence, or the
media may simply pin the wrong hash. What happens instead depends on
how Reliquary is running:

- **Interactively**, the mismatch is a checkpoint: Reliquary asks
  (`Existing file <path> does not match its pinned hash … Delete
  it and fetch again? [y/N]`) and only deletes and refetches on a
  yes. Declining keeps the file and fails the operation.
- **Programmatically** (and whenever input is not a terminal),
  the mismatch fails fast with an error naming the file and both
  hashes.
- The deletion can be **pre-approved**: `--on-mismatch refetch`
  on commands that fetch media — the flag mirrors its API twin's
  parameter, under the naming rule — or the embedding
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

## Reclaiming the cache

Everything cached can be fetched or derived again, except a payload
a person supplied — so reclamation distinguishes the two rather than
asking the user to.

```text
rlq clean-media [<name>]
rlq prune-media [--dry-run]
```

- **`clean-media`** is blunt: it takes back everything, because
  everything there can be got again. Anything a running machine is
  holding open is skipped. Naming a media evicts that one
  deliberately.
- **`prune-media`** is informed: it keeps the **attachment
  closure** — what the active scope can still attach — and drops
  what only existed to produce it. A container goes once its
  children are cached, and stays while they are not, since it is
  then still the only way to produce them. After an install that
  means the extracted ISO stays and the zip husk goes, which is
  usually the larger file. `--dry-run` reports without removing.

Both are scope-relative: the closure is computed against the media
the active source declares and the machines that exist, so pruning
in one project never reasons about another's. The API twins are
`clean_media(name=None)` and `prune_media(dry_run=)`.

### What a cached file is

Its filename. A payload is written as `<media-name>.<ext>` and
nothing else is recorded about it — no sidecar, no provenance (D41).
The cache can afford that because it is entirely reconstructible:
everything in it arrived by download or extraction and can arrive
that way again.

Identity is still checked before every fetch, by hashing the cached
file against the media's pin. That catches a **version bump** — same
location, changed bytes — and a **cross-project name collision** —
two different media sharing one name across a common cache — with
equal reliability; a colliding payload is never silently accepted.
What it cannot do is say which of the two it found, so the mismatch
message names both possibilities and points at `--media-dir`, the
flag that isolates one project's media cache from another's.

## Sharing

Media travel inside the blueprint: a `.rlqb` carries its media specs
alongside the machine that uses them, so sharing the blueprint shares
the verified inputs — small, hash-pinned, and machine-independent —
without shipping the payloads themselves (U4). A media reused across
several blueprints is written once and referenced by name, or
declared identically in each and deduplicated by identity; the
artifact-residency split decides which source supplies it. What
crosses the wire is the pinned identity, never the licensed bytes.
