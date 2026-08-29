<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Authored-asset resolution and the working directories

> **Status:** normative. This is implemented and matches the code:
> the six placeable directories, the non-placeable `fonts` and
> `landmarks` directories (F61, F65), the rule that the codex
> library is never an implicit source of files, the rule for how an
> asset's identity is determined from its extension and name, the
> blueprint source recorded on a machine, and the default directory
> layout. The layout is a contract other projects build on
> ([SURFACES.md](../../planning/SURFACES.md)), so changing it
> follows the surface-change rule there. One thing below is
> **reserved** — named here only so it isn't mistaken for something
> that already works: the `ObjectSource` fileless third source.
> Details of it may still change before the first release.
>
> This status banner was missing until 2026-07-27, and by then the
> document had drifted out of sync with the code in six places.
> [README.md](README.md) explains why a banner like this one is
> required on every spec page: it is the only thing that tells a
> reader whether a page is current, and moving a page into a
> different directory does not by itself make that true.

This document says where Reliquary looks for the files a user
writes, and where it keeps its own files. It explains the
mechanism behind the split described in
[ARCHITECTURE.md](../../ARCHITECTURE.md) (P4): a user's own assets
live separately from Reliquary's generated files. The format of
each individual asset type is specified in
[blueprint-model.md](blueprint-model.md),
[media-spec.md](media-spec.md), [script-spec.md](script-spec.md),
and [landmarks.md](landmarks.md).

## Assets are identified by extension

Reliquary tells asset types apart by their file **extension**, not
by which directory they're in:

- `.rlqb` is a machine blueprint (`.json` is still accepted, as its
  older spelling).
- `.rlqs` is a script.
- `.rlqf` is an authored glyph font (F61). Its 4096-byte data file,
  `<name>.bin`, is found next to it by matching filename stem — not
  by searching the directory for it.
- `.rlql` is a landmark declaration (F65). Its `<name>.<n>.png`
  variant image files are found the same way, by matching stem and
  number ([landmarks.md](landmarks.md)).

There is **no separate file extension for media**: `.rlqm` was
removed when media definitions moved inside blueprints. A media is
now a section inside a `.rlqb` file (D30), and it is looked up by
name within that blueprint, not by this extension rule.

An asset's **identity** — the name Reliquary refers to it by — is
its declared `name` field if it has one, or its filename stem if it
doesn't. Two files of the same kind that resolve to the same
effective name within one source directory is an error. Scripts,
fonts, and landmarks have no `name` field, so all three are always
identified by filename stem. For fonts and landmarks that isn't
just a convention — the matching data file is found by that same
stem, so if a `name` field ever disagreed with the stem, it would
break that matching.

**Fonts, landmarks, and media share one name pool.** A font's name
and a landmark's name are checked against the same pool of `@`
names that a media's name already occupies
(`planning/design/authored-binary-assets.md`, "one reference
pool"). If two files end up with the same name, and a script can
see both, that's an error naming both files — checked at the point
a script actually looks one of them up (`fonts.py`,
`landmarks.py`), the same on-demand check the media name pool
already uses. Which kind of asset a `@name` reference must resolve
to depends on **where it's used**: an `insert` statement expects
`@name` to be a media, and a condition expects `@name` to be a
landmark. Using a landmark's name where `insert` expects a media,
or a media's name where a condition expects a landmark, is refused
— the error names both where it was used and what kind was
expected.

## Where each asset kind lives, and whether the codex library backs it up

Each asset kind resolves from **one directory**: blueprints come
from the `blueprints` directory, scripts from `scripts`, fonts from
`fonts` (below). Blueprints and scripts are placeable — you can
point them anywhere, using the same six-slot model as every other
working directory ([the working directories](#the-working-directories)
below) — so there's no separate setting for "where do my assets
live." **Fonts are the one exception**: `fonts` is always a fixed
subdirectory of `home` and can never be assigned separately, because
adding a placement setting for every binary asset kind was rejected
(`planning/design/authored-binary-assets.md`, "P12"). So a project
whose `blueprints`/`scripts` live outside `home` still finds its
fonts under `home`. Each kind's directory is searched
**recursively** by extension — you can lay your files out inside it
however you like, and directories like `.git`/`.venv` are skipped —
and that directory is the **only** source for that kind. There is no
second directory checked as a fallback.

**A name that isn't found never falls back to the shipped codex
library**, on the CLI or in the API, and there is no flag to turn
that fallback on (D88). Each directory is the only source for its
kind; if a name isn't in your directory, the lookup fails, and
nothing from outside your own project tree can reach a run (U14,
U4, P4).

When the library does hold that name, the error message names the
command that fixes it: `rlq seed-blueprint <name>`. That way, using
something from the codex library always happens because someone
asked for it, and that request shows up in shell history instead of
happening silently. There used to be a setting that turned automatic
fallback to the codex on; it's been removed rather than just turned
off by default, because turning it on let an operation silently pull
in library content that the next point release might change.

These two questions — where an asset kind's directory is, and
whether the codex library is a fallback for it — are independent.
A project's own directory can still be seeded from the codex, and a
`home` directory can still refuse to fall back to it. There used to
be a single setting that answered both questions at once — naming a
project's root directory and, by the same setting, turning fallback
off — that setting has been removed: where files live is only ever
what the directory flags say, and the codex is never a fallback,
unconditionally.

**The embedding API sets none of these locations itself**: a
session refuses to construct without an explicit home, so calling
the API never silently picks up assets from the user's own `home`
directory, or from whatever directory the process happens to be
running in — a directory that would be arbitrary for a program to
guess, and is never used as a default for assets anywhere. The API
can take its assets from more than one kind of source: a directory
on disk, or a set of JSON objects supplied directly in memory with
no files at all — each self-identified by its `name` field. That
in-memory form is the fileless third source, covered just after the
file-based ones below.

**The only way the codex library's content reaches your own
directory is by asking for it.** `seed-blueprint` and `seed-script`
copy files into whichever `blueprints` / `scripts` directory is
currently assigned, whether that's a project directory or `home`.
Asking for a first draft this way means the caller has explicitly
chosen the codex library as the source — which is what the library
is for: copy from it, then commit the copy into your own project.

## Two related rules

**A machine records which blueprint file it came from.** Its saved
state carries the resolved blueprint file's absolute path.
`--blueprint <name>` selection only matches a machine whose recorded
source path equals what resolving `<name>` produces for the current
invocation. That means two different projects can each have a
blueprint with the same name, and their machines will never be
confused with each other, and `apply` will never apply one
project's blueprint to another project's machine. (A machine with no
recorded source at all still matches by name alone.)

**Reliquary reads assets by extension, but only writes them in one
specific case.** U6's recorder
([recorder.md](../../planning/proposed/design/recorder.md)) writes
its drafts — a script, its landmark declarations, and their variant
image renderings — into whatever directories the session was using,
as new source files for the author to commit. Nothing else ever
writes an authored asset without being asked to: a script has no
mechanism to install definitions on its own, so running a script
normally leaves those directories untouched, and a CI checkout stays
clean.

## The working directories

Reliquary has **six** working directories, and every one of them
can be placed anywhere — through the CLI and the embedding API
alike. Each one starts unassigned. Values are set on the `Context`
record that a session is opened on (P26 — the same record also
carries the selected properties file), and the defaults shown below
are *derived* from what you do assign, not preset ahead of time.

| Directory | Flag | Environment | Derives as |
|---|---|---|---|
| home | `--home-dir` | `RELIQUARY_HOME` | — |
| blueprints | `--blueprints-dir` | `RELIQUARY_BLUEPRINTS_DIR` | `<home>/blueprints` |
| scripts | `--scripts-dir` | `RELIQUARY_SCRIPTS_DIR` | `<home>/scripts` |
| cache | `--cache-dir` | `RELIQUARY_CACHE_DIR` | `<home>/cache` |
| media | `--media-dir` | `RELIQUARY_MEDIA_DIR` | `<cache>/media` |
| machines | `--machines-dir` | `RELIQUARY_MACHINES_DIR` | `<cache>/machines` |

Derivation only fills in what's still unassigned: assigning `cache`
alone does not invent a `home`, and assigning `machines` alone
leaves `media` to derive normally from the rest. A `Context` with no
`home` assigned causes a **construction-time refusal**
(`dir.unassigned`), which names `home` as the missing piece. Once
`home` is assigned, all six directories can be derived from it, so
nothing a session does can ever encounter an unassigned directory.
A bare `Context` object can still be built and its fields filled in
before a session is opened on it — the refusal happens when a
session is constructed, not when the `Context` itself is built.

The CLI and the embedding API differ only in whether something
assigns `home` for you. The **CLI** gives `home` a default —
`Documents/reliquary`, or `~/reliquary` if that doesn't exist —
whenever neither a flag nor an environment variable set one. That
one default reaches all six directories through derivation, so at
the command line you'll never actually see the refusal — but that's
because of the default, not because the rule doesn't apply to the
CLI. The **embedding API** assigns nothing on its own: a session
demands an explicit home, by design, as its main safety guarantee.
Reading environment variables is likewise something only the CLI
does, never the library: the flags and variables in the table above
are read while the CLI builds its own `Context`, and the library
itself never reads environment variables.

`home` is just one of the six directories now, not a folder that
contains the other five ([ARCHITECTURE.md](../../ARCHITECTURE.md)
P12). It's still where Reliquary keeps things that have nowhere
else to go: the personal user-properties file stays under `home`,
so that a license key never ends up committed into a project's
repository (U5).

### The default layout

With only the home assigned, the six land like this:

```text
<reliquary_home>/
├── blueprints/          machine blueprints, <name>.rlqb — media
│                        ride inside them, so there is no media/
├── scripts/             reliquary automation scripts
├── fonts/               authored glyph fonts, <name>.rlqf beside
│                        <name>.bin — not independently placeable
│                        (F61)
├── landmarks/           authored landmarks, <name>.rlql beside its
│                        <name>.<n>.png renderings — not
│                        independently placeable (F65)
├── user.properties      personal user properties (line-based
│                        key = value; ordinary values and @secret
│                        markers for host-stored secrets)
└── cache/               reliquary's regenerable files
    ├── media/           every cached payload, keyed by the name of the
    │                    media it is (a container is a media too),
    │                    fetched/extracted/verified on demand; the
    │                    filename is the whole of a file's identity
    └── machines/<id>/   cached materializations — disposable:
                         drives regenerate from blueprint and media;
                         a run stores nothing, returning its output
                         to the caller (D36)
```

The layout above is only where `blueprints`, `scripts`, and `cache`
*derive* to by default; any of the three can be assigned somewhere
else, and if `cache` is reassigned, `media` and `machines` follow
`cache` rather than `home`. `fonts` and `landmarks` always derive
from `home` and can never be assigned separately (as explained
above): the cost of not giving every read-only binary asset kind
its own placement setting is accepted so the six-slot model doesn't
have to grow for each new one. So a project whose `scripts` and
`blueprints` live outside `home` still finds its fonts and
landmarks under `home`. The recorder's drafts are written into
whichever `blueprints` / `scripts` directories the session was
using — for a project, that's the project's own tree, not `home`.

Everything under `cache` belongs to Reliquary and can be deleted at
any time. Nothing is ever placed there by hand; anything that
should end up on a machine gets there through the blueprint —
either a `media` reference, or a starting-point image (`base`) that
a machine's drives are either differenced from or copied from. The
machine directory's own structure and what owns it are described in
[instance-model.md](instance-model.md).

The working-directory layout is a contract other projects build on
([SURFACES.md](../../planning/SURFACES.md)): changing it follows
the surface-change rule described there.
