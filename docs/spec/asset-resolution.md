<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Authored-asset resolution and the home

Where Reliquary looks for the files a user authors, and where
Reliquary keeps its own. This is the mechanism behind the
artifact-residency split ([ARCHITECTURE.md](../../ARCHITECTURE.md) P4);
the individual asset formats are specified in
[blueprint-model.md](blueprint-model.md),
[media-spec.md](media-spec.md), [script-spec.md](script-spec.md),
and [landmarks.md](../../planning/proposed/design/landmarks.md).

## Assets are identified by extension

Assets are identified by **extension**, not location: `.rlqb` a
machine blueprint, `.rlqm` a media definition, `.rlqs` a script,
`.rlql` a landmark declaration (its `<name>.<n>.png` variant
renderings attach by stem adjacency, not discovery —
[landmarks.md](../../planning/proposed/design/landmarks.md)). An asset's **identity** is its
declared `name` when it carries one, else its filename stem; two
files of one kind resolving to the same effective name within a
source are an error.

## Two modes, one knob

Resolution has two modes, selected per invocation by one knob —
`--assets` (API `assets=`). There is no shadow and no fallback:
the selected source is the sole source.

- **Home mode** — the CLI default, when `--assets` is absent.
  Resolves from the home's canonical `blueprints/` / `media/` /
  `scripts/` folders and seeds a missing name from the built-in
  codex on first reference. Home assets are a convenience for
  human CLI interaction — one shared place a person reuses across
  scenarios (U1, U5).
- **Dir mode** — `--assets <dir>`, and *every* embedding-API
  call. The directory is walked recursively by extension (a
  project lays its files out however it likes; dot-directories
  like `.git`/`.venv` are pruned) and is the **sole** source: no
  home, no codex, no seeding. Strictly project-scoped resolution,
  so nothing outside source control can reach an automated run
  (U3, U4). The codex is never a resolution tier for automation —
  at most a place to copy a first draft from, the copy committed.

The **embedding API has no default source**: a bare call that
resolves a name with nothing configured fails closed, so
automation never silently picks up user (home) assets — or a
stray current directory, which is arbitrary for a programmatic
caller and is not an asset default anywhere. Home mode is
reachable only through the explicit home marker the CLI sets by
default; it is never the API's default. The API source is
polymorphic: a directory, or a set of JSON-imported objects
supplied in memory with no files at all (self-identifying by
`name` — the fileless third source, landing just after the file
modes).

The home remains Reliquary's own ground regardless of mode:
machines materialize into the home cache, downloads and payloads
use the home caches, and the personal user-properties file stays
home-side (a license key never enters the repo — U5).

## Two completing rules

**Machines record their blueprint's source**: the state carries the
resolved blueprint file's absolute path, and `--blueprint <name>`
selection matches only machines whose recorded source equals the
invocation's own resolution of that name, so same-named blueprints
in different projects never select — and `apply` never adopts —
each other's machines (a machine with no recorded source matches by
name alone).

**Reliquary reads by extension and writes by convention**: U6's
recorder ([recorder.md](../../planning/accepted/design/recorder.md)) emits its drafts — the
script, its landmark declarations, and their variant renderings —
into the asset root the session ran with, as new source files their
author commits. Nothing else writes an authored asset: a script
carries no definitions to install, so an ordinary run leaves the
asset root untouched and a CI tree clean.

## The home layout

```text
<reliquary_home>/
├── blueprints/          machine blueprints, <name>.rlqb
├── scripts/             reliquary automation scripts
├── landmarks/           landmark declarations and their variant
│                        renderings, <name>.rlql + <name>.<n>.png
│                        (see landmarks.md)
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

Everything under `cache/` is Reliquary's and disposable. Nothing is
ever hand-placed there; pre-existing content enters a machine
through the blueprint — `media` references, and starting-point
images (`base`) that machine drives are differenced from, or copies
of. The machine directory's own structure and ownership model are
in [instance-model.md](instance-model.md).

The home layout is a world-facing contract
([INTERFACES.md](../../planning/INTERFACES.md)): changes to it follow
the interface-change rule.
