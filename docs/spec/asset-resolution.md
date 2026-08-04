<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Authored-asset resolution and the working directories

> **Status:** normative. The six placeable directories, the
> codex-is-not-a-tier rule, the extension-and-name identity rule,
> the recorded blueprint
> source, and the default layout are implemented and are what the
> code answers to; the layout is a world-facing contract, so changes
> to it follow the surface-change rule
> ([SURFACES.md](../../planning/SURFACES.md)). Two things
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

**A miss never falls back to the shipped codex**, on either surface
and under no flag (D88). The directories are the sole sources, a
missing name fails closed, and nothing outside your own tree reaches
a run (U14, U4, P4).

Where the library holds that name, the refusal names the command
that fixes it — `rlq seed-blueprint <name>` — so the codex reaches a
tree because someone asked, and the asking is legible in the shell
history rather than implied by a default. An axis for this existed
once, and turning it on meant an operation could quietly resolve
content the next point release may change; it is deleted rather than
defaulted.

Neither axis implies the other. A project tree may keep the codex
behind it and a home may refuse it. The single asset-root knob that
once answered both questions at once — naming a project root *and*
declaring hermeticity by the same word — is retired: placement is
what the directory flags say, and hermeticity is unconditional.

The **embedding API assigns nothing**: a session refuses
construction without a home, naming it, so automation never
silently picks up user (home) assets — or a stray current
directory, which is arbitrary for a programmatic caller and is not
an asset default anywhere. The API source is polymorphic: a
directory, or a set of JSON-imported objects supplied in memory
with no files at all (self-identifying by `name` — the fileless
third source, landing just after the file modes).

**Seeding on request is the only way the codex reaches a tree.**
`seed-blueprint`
and `seed-script` write into the assigned `blueprints` / `scripts`
directory wherever it is, project tree or home alike: a caller
asking for a first draft has named the codex
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
script carries no definitions to install, so an ordinary run leaves
those directories untouched and a CI tree clean.

## The working directories

Reliquary has **six**, and every one of them is placeable — through
the CLI and the embedding API alike. Each starts unassigned; values
arrive in the `Context` record a session is opened on (P26 — the
record also carries the selected properties file), and the defaults
below are *derived* rather than pre-set.

| Directory | Flag | Environment | Derives as |
|---|---|---|---|
| home | `--home-dir` | `RELIQUARY_HOME` | — |
| blueprints | `--blueprints-dir` | `RELIQUARY_BLUEPRINTS_DIR` | `<home>/blueprints` |
| scripts | `--scripts-dir` | `RELIQUARY_SCRIPTS_DIR` | `<home>/scripts` |
| cache | `--cache-dir` | `RELIQUARY_CACHE_DIR` | `<home>/cache` |
| media | `--media-dir` | `RELIQUARY_MEDIA_DIR` | `<cache>/media` |
| machines | `--machines-dir` | `RELIQUARY_MACHINES_DIR` | `<cache>/machines` |

Derivation reaches only what is still unassigned, so assigning
`cache` alone conjures no home and assigning `machines` alone leaves
`media` where the rest of the resolution puts it. A record with no
home is a **fail-closed refusal at the session's door**
(`dir.unassigned`), naming the home — an assigned home reaches all
six by derivation, so nothing a session does can find a directory
unassigned. A bare `Context` may still be built and filled before a
session is opened on it; the refusal is construction's, not the
record's.

The surfaces differ only in whether an assignment is made for the
caller. The **CLI** gives `home` its default —
`Documents/reliquary`, falling back to `~/reliquary` — whenever
neither a flag nor the environment named one, so one assignment
reaches all six and the refusal is unreachable at the keyboard.
That is a property of the default, not an exemption from the rule.
The **embedding API** assigns nothing — the session demands its
home at the door; that is the safety of the design. Honouring the
environment is likewise the CLI's behaviour and never the
library's: the flags and variables above arrive through the CLI's
own construction of the record, and the library reads no
environment.

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
([SURFACES.md](../../planning/SURFACES.md)): changes to it follow
the surface-change rule.
