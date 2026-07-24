<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# The media spec

> **Status:** implemented. Media are specs inside a `.rlqb`: the
> four `materialize` modes, `size`, the one `location` field and its
> grammar, conditional `sha256`, `read-only`, `extension`,
> parent/children containment, unknown-key rejection, catalog
> resolution with identity dedup and collision detection,
> hash-verified fetch and extraction with the mismatched-file
> contract, the identity ledger, JSONC acceptance, and the media
> command family.
>
> **This document covers acquisition** — where a payload comes from
> in practice, how it is verified, and how the cache behaves. The
> format's normative model — the root shape, spec identity, the
> location grammar, containment, and the reference closure — is
> [the composed blueprint model](blueprint-model.md), and is not
> restated here. One model in two documents is how a spec comes to
> contradict itself (D32).

Media are the machine-independent payloads a machine mounts:
installer ISOs, boot floppies, driver disks. They are **specs inside
the one authored `.rlqb`**, not a file kind of their own (`.rlqm`
retires). A machine's drive names a media by name — or carries one
written in place — and the media owns everything about the payload:
where it comes from, how it is verified, and how it materializes.

Resolution reads the whole source: every `.rlqb` in the active
source is parsed into one `(name, type)` catalog, and references
bind by name. In home mode (the CLI default) that is the whole home,
seeding from the codex on a miss; under `--assets <dir>` it is the
whole project root — the sole hermetic source, where neither home
specs nor the codex behind them reach an automated run (the
artifact-residency split, PRINCIPLES.md P4).

```text
<asset root>/…/freedos.rlqb        the machine and the media it draws on
<reliquary_home>/cache/media/
├── .ledger.json                   what each cached file is
├── freedos-livecd-zip.zip         the container, cached by its name
└── freedos-livecd.iso             the payload read out of it
```

One name-keyed cache holds every payload, keyed by the name of the
media it *is* — a container is a media like any other, so there is
no second directory for containers. It is entirely reconstructible
except where a person supplied a payload nothing can re-fetch
(`add-media`), which the ledger records so reclamation can tell the
difference. A bare file dropped into the directory does nothing:
the cache is Reliquary's, not an interface.

## The media component

A `media` component owns all content and materialization.

### `name`

The string machine drives and script `insert`s reference. Explicit,
or derived from content — a location's filename or containment path
stem, repaired to the name charter with a warning when it must be
(`144m/FDBOOT.img` → `FDBOOT`). A media with no filename-bearing
content — a blank — **must** name itself, except the one anonymous
citizen: a content-free blank written in place at a drive, which
belongs to no namespace and takes its slot's name when materialized.
Identity is `(name, type)` in one catalog; identical specs coexist
across files, differing ones collide, and names collide
case-insensitively.

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
image under `cache/machines/<id>/media/<name>.<ext>` (named for the
media, not the slot); `use` attaches the shared payload — the
`cache/media/` file, the `local` file, or the `hostdir` directory —
**directly**, with no per-machine copy. This is what a machine
drive's declaration reaches: **to change how a drive materializes,
change (or point at a different) media.**

### `size`

`new` only. A positive integer with a binary unit suffix
(`K` / `M` / `G` / `T`, powers of 1024): `"20M"`, `"1440K"`.

### `location`

Where the payload comes from. One field, one grammar — specified in
[the composed blueprint model](blueprint-model.md#the-location-grammar);
[below](#where-a-payload-comes-from) is what each shape costs at
fetch time. Absent only for a blank.

### `sha256`

The payload's hash, verified on every use. **Required when the
rung is remote** (untrusted); optional for local and derived
payloads. The check happens at resolution rather than parse, since a
referenced rung may resolve to a URL. Optional is a feature: a local
media may
omit it to attach a drive image you are still *evolving* (a pin
would fail on every edit); hermetic workflows add the hash when they
want the pin. The hash is the build pin *independent of the location
kind* — a trusted local payload can still verify the media is the
exact build the scripts target. Hex, accepted in either case;
Reliquary's canonical writes are lowercase.

### `read-only`

Present the drive read-only so a floppy or hard disk is not
corrupted; orthogonal to `materialize`. **Defaults true on a
cdrom** (no backend meaningfully writes a virtual ISO, so a writable
cdrom is rejected), opt-in elsewhere; for a directory source it
protects the host directory.

### `extension`

Override the type-declaring extension of the cached payload when the
location's filename misnames it (or omits it) — the extension is
what declares the image format to machine drives. Otherwise derived
from the location's filename or its containment path.

**A host directory is a payload shape, not a mode:** a media whose
`location` is a host *directory* with `materialize: use` is the live vvfat
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
  hash, not the URL, is the arbiter, so a failing mirror is simply
  the cue to try the next.
- A **local** payload is used **in place** and never copied into the
  cache. Its hash is optional, which is the point: a drive image you
  are still evolving would fail a pin on every edit.
- A **contained** payload is extracted from its parent, which is
  fetched first by the same rules — so one remote rung high in a
  tree downloads once and every descendant derives from the cached
  parent. Container reading is roster-gated by format: zip today, an
  unsupported container failing closed and naming its format.
- A **property-supplied** location resolves through the property
  chain at `create` / `apply`, never at `start`.

### Supplying what nothing can locate

A media may pin its `sha256` and name a location nothing supplies —
the licensed, non-redistributable case, which is how codex media
ship ([the codex's licensing rule](codex.md#non-redistributable-media)).
Resolution **fails closed** naming the media until someone provides
the payload, and there are two ways to do that without editing the
shipped spec's identity:

- **`add-media <name> <file>`** — the guarded door. The file is
  verified against the pin and copied into the cache under the
  media's own name, recorded `supplied`. This is the home-CLI path,
  and the one case where a payload legitimately enters the cache
  from outside.
- **A property-valued location** — the project and CI path, and the
  hermetic one: the committed hash still determines the input, and
  the path that supplies it is per-run.

Editing your own seeded copy is always the third option; that is
what seeding is for.

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
container that verifies is re-extracted; only then are the mirror rungs
tried.

The embedding API counterpart is
`fetch_media(name, context=None, on_mismatch="fail")` — the CLI and
the API move together (planning/INTERFACES.md). `fetch_media` is the
blocking form: a typed result, errors raised by class. Its
asynchronous twin `start_fetch(...)` is **backlog work** (D35 —
the async pillar left the numbered arc for lack of a use case,
drafted as U19; ROADMAP "Asynchronous runs (backlog)"); the
blocking `fetch_media` and its foreground `--progress` rendering
stay in milestone 9. Design as settled, for when it returns:
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

Fetching is Reliquary's longest operation outside a run, and it
reports progress under the same feedback model as script runs
(the feedback split, PRINCIPLES.md P5): one event
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

## Reclaiming the cache

Everything cached can be fetched or derived again, except a payload
a person supplied — so reclamation distinguishes the two rather than
asking the user to.

```text
rlq clean-media [<name>]
rlq prune-media [--dry-run]
```

- **`clean-media`** is blunt: it takes back everything the project
  can get again. A `supplied` payload is spared, because nothing
  could put it back, and so is anything a running machine is holding
  open. Naming a media evicts that one deliberately, whatever its
  provenance.
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

### The identity ledger

Beside the payloads, `cache/media/.ledger.json` records what each
cached file actually is: the sha256 observed when it was written,
its provenance (`refetchable`, `derived`, `supplied`), the source it
came from, and for a derived payload the `(parent-sha, path)` that
produced it.

That is what makes the preflight identity check a diagnosis rather
than a comparison. A bare hash mismatch cannot tell a **version
bump** — same location, changed bytes — from a **cross-project name
collision** — two different media sharing one name — and those want
opposite fixes. The ledger names which one you have.

## Sharing

Media travel inside the blueprint: a `.rlqb` carries its media specs
alongside the machine that uses them, so sharing the blueprint shares
the verified inputs — small, hash-pinned, and machine-independent —
without shipping the payloads themselves (U4). A media reused across
several blueprints is written once and referenced by name, or
declared identically in each and deduplicated by identity; the
residency split decides which source supplies it. What crosses the wire is the pinned
identity, never the licensed bytes.
