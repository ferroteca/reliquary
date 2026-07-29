<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Authored-asset resolution and the working directories

> **Status:** normative. The six placeable directories, the autoseed
> axis, the extension-and-name identity rule, the recorded blueprint
> source, and the default layout are implemented and are what the
> code answers to; the layout is a world-facing contract, so changes
> to it follow the interface-change rule
> ([INTERFACES.md](../../planning/INTERFACES.md)). Two things
> below are **reserved**, named so they are not mistaken for
> today's behaviour: the `ObjectSource` fileless third source, and
> landmark declarations (`.rlql`, the home `landmarks/` folder) —
> settled design in
> [landmarks.md](../../planning/proposed/design/landmarks.md) and
> entirely unbuilt, so no asset kind is declared for them. Details
> may change before first release.
>
> This banner was absent until 2026-07-27, and the document had
> drifted in six places behind it — the directory's own rule is
> that the banner is the marker and shelving proves nothing
> ([README.md](README.md)).

Where Reliquary looks for the files a user authors, and where
Reliquary keeps its own. This is the mechanism behind the
artifact-residency split ([ARCHITECTURE.md](../../ARCHITECTURE.md) P4);
the individual asset formats are specified in
[blueprint-model.md](blueprint-model.md),
[media-spec.md](media-spec.md), [script-spec.md](script-spec.md),
and [landmarks.md](../../planning/proposed/design/landmarks.md).

## Assets are identified by extension

Assets are identified by **extension**, not location: `.rlqb` a
machine blueprint (`.json` is accepted as its legacy spelling),
`.rlqs` a script. There is **no media file kind** — `.rlqm`
retired with the composed model, and a media is a spec inside a
`.rlqb` (D30), resolved through the component namespace rather
than by this rule. Reserved: `.rlql` a landmark declaration (its
`<name>.<n>.png` variant renderings attaching by stem adjacency,
not discovery —
[landmarks.md](../../planning/proposed/design/landmarks.md)),
which no source resolves today.

An asset's **identity** is its
declared `name` when it carries one, else its filename stem; two
files of one kind resolving to the same effective name within a
source are an error. A script carries no `name` field, so it is
always stem-identified.

## Two axes: where a kind lives, and whether the codex backs it

Assets resolve from a **directory per kind** — blueprints from the
`blueprints` directory, scripts from the `scripts` one. Both are
placeable, on the same six-slot model as every other working
directory ([the working directories](#the-working-directories)
below), so "where do my assets live" is not a question with its own
knob. Each directory is walked **recursively** by extension — a
project lays its files out however it likes, and dot-directories
like `.git`/`.venv` are pruned — and it is the **sole** file source
for its kind. There is no shadow and no fallback between
directories.

Whether a miss may fall back to the shipped codex is the separate
**autoseed** axis: `--autoseed` / `--no-autoseed`, API `autoseed=`.

- **On** — the CLI default. A name the directory does not hold is
  read from, or copied out of, the built-in codex, so a person
  meeting Reliquary for the first time finds `freedos` already
  there (U1, U5). Copy-out never overwrites.
- **Off** — the embedding API default. The directories are the sole
  sources and a missing name fails closed, so nothing outside
  source control reaches the run (U14, U4).

Neither axis implies the other. A project tree may keep the codex
behind it and a home may refuse it. The single asset-root knob that
once answered both questions at once — naming a project root *and*
declaring hermeticity by the same word — is retired: placement is
what the directory flags say, and hermeticity is what autoseed says.

The **embedding API assigns nothing**: a bare call that resolves a
name with no directory assigned fails closed, naming the directory
it wanted, so automation never silently picks up user (home) assets
— or a stray current directory, which is arbitrary for a
programmatic caller and is not an asset default anywhere. The API
source is polymorphic: a directory, or a set of JSON-imported
objects supplied in memory with no files at all (self-identifying by
`name` — the fileless third source, landing just after the file
modes).

**Seeding on request is not what autoseed governs.** `seed-blueprint`
and `seed-script` write into the assigned `blueprints` / `scripts`
directory wherever it is, project tree or home alike, whatever
autoseed says: a caller asking for a first draft has named the codex
as its source, which is the use the codex is for — copy it, then
commit the copy.

## Two completing rules

**Machines record their blueprint's source**: the state carries the
resolved blueprint file's absolute path, and `--blueprint <name>`
selection matches only machines whose recorded source equals the
invocation's own resolution of that name, so same-named blueprints
in different projects never select — and `apply` never adopts —
each other's machines (a machine with no recorded source matches by
name alone).

**Reliquary reads by extension and writes by convention**: U6's
recorder ([recorder.md](../../planning/proposed/design/recorder.md)) emits its drafts — the
script, its landmark declarations, and their variant renderings —
into the directories the session ran with, as new source files their
author commits. Nothing else writes an authored asset unasked: a
script carries no definitions to install, so an ordinary run with
autoseeding off leaves those directories untouched and a CI tree
clean.

## The working directories

Reliquary has **six**, and every one of them is placeable — through
the CLI and the embedding API alike. Each starts unassigned; values
arrive by assignment, and the defaults below are *derived* rather
than pre-set.

| Directory | Flag | Environment | Derives as |
|---|---|---|---|
| home | `--home-dir` | `RELIQUARY_HOME_DIR` | — |
| blueprints | `--blueprints-dir` | `RELIQUARY_BLUEPRINTS_DIR` | `<home>/blueprints` |
| scripts | `--scripts-dir` | `RELIQUARY_SCRIPTS_DIR` | `<home>/scripts` |
| cache | `--cache-dir` | `RELIQUARY_CACHE_DIR` | `<home>/cache` |
| media | `--media-dir` | `RELIQUARY_MEDIA_DIR` | `<cache>/media` |
| machines | `--machines-dir` | `RELIQUARY_MACHINES_DIR` | `<cache>/machines` |

Derivation reaches only what is still unassigned, so assigning
`cache` alone conjures no home and assigning `machines` alone leaves
`media` where the rest of the resolution puts it. A directory with
no value when resolution needs it is a **fail-closed error naming
that directory**, raised at first use rather than at `Context`
construction.

The surfaces differ only in whether an assignment is made for the
caller. The **CLI** assigns `home` its default —
`Documents/reliquary`, falling back to `~/reliquary` — whenever
neither a flag nor the environment named one, so one assignment
reaches all six and the error is unreachable at the keyboard. That
is a property of the default, not an exemption from the rule. The
**embedding API** assigns nothing, and there the error is reachable;
that is the safety of the design. Honouring the environment is
likewise the CLI's behaviour and never the library's.

The home is one of the six, no longer a container for the rest
([ARCHITECTURE.md](../../ARCHITECTURE.md) P12). It remains
Reliquary's own ground for what has nowhere else to go: the personal
user-properties file stays home-side, so a license key never enters
the repo (U5).

### The default layout

With only the home assigned, the six land like this:

```text
<reliquary_home>/
├── blueprints/          machine blueprints, <name>.rlqb — media
│                        ride inside them, so there is no media/
├── scripts/             reliquary automation scripts
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

Each of those five paths is only where the directory *derives* to;
any of them may be assigned elsewhere, and `media`/`machines` follow
an assigned `cache` rather than the home. A `landmarks/` folder
joins this layout with landmark support and is reserved until then
(see the banner); the recorder's drafts above land in the
`blueprints` / `scripts` directories the session ran with, which for
a project is its own tree rather than the home.

Everything under the cache is Reliquary's and disposable. Nothing is
ever hand-placed there; pre-existing content enters a machine
through the blueprint — `media` references, and starting-point
images (`base`) that machine drives are differenced from, or copies
of. The machine directory's own structure and ownership model are
in [instance-model.md](instance-model.md).

The working-directory layout is a world-facing contract
([INTERFACES.md](../../planning/INTERFACES.md)): changes to it follow
the interface-change rule.
