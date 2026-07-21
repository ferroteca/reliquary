<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# The built-in library

> **Status:** the seeding core — the packaged tree, copy-out on
> first reference, and the never-overwrite rule — is implemented.
> The index, provenance columns, `search`, and `pull` are still
> planned; details may change before first release.

reliquary ships a library of blueprints, media definitions, and
scripts for popular open source operating systems, so the common
case is one command from a clean home:

```powershell
rlq --blueprint freedos-1.4-plain script install
```

That single command extracts the blueprint, its media definitions,
and its scripts from the library, creates a machine, fetches and
verifies the installation media, and runs the scripted install.

## A seed, not a resolution tier

The library ships inside the reliquary package as ordinary files
under `reliquary/builtins/` (`blueprints/`, `media/`, `scripts/`),
so it travels with every distribution form, including zip-bundled
installs. Wherever it lives, the library is
never consulted at run time as a fallback layer. Instead, when you
reference a built-in artifact that does not yet exist in your home,
reliquary **copies it out**. From that point on it is an ordinary
user-owned file — edit it, delete it, version it.

Two rules carry the model:

- **A file already present in your home is never overwritten.**
  There is no shadowing, no precedence order, and no "library
  update changed my machine" surprise: what your home contains is
  what runs, always.
- **Deleting your copy is how you refresh it.** Once you delete a
  file yourself, the next reference (or an explicit `pull`)
  extracts the current built-in again. Orphaned references — a
  blueprint naming a media definition or script you removed —
  re-seed the same way.

## The index and provenance

The library carries an index mapping every built-in artifact to
its `name`, `description`, and relationships (which media
definitions and scripts a blueprint references). User-owned files
are indexed by reading the same optional fields from the file.
`search` queries both.

Listings report provenance by name:

| BUILT-IN | meaning |
|---|---|
| `yes` | a library entry not yet extracted into your home |
| `seeded` | a user file whose name also exists in the library |
| (blank) | a purely user-authored file |

## Extraction

Extraction happens two ways:

- **Implicitly, on first reference.** Any operation that resolves
  a blueprint, media definition, or script name checks the home
  first, then the library; a library hit is copied out (a
  blueprint brings its referenced media definitions and scripts
  with it) and resolution proceeds against the new user file.
- **Explicitly, with `pull`.** `pull blueprint <name>` extracts
  the blueprint and everything it references — the one-stop bridge
  from "just use the built-in" to "I want to tweak it"
  (`--only` restricts it to the blueprint file itself);
  `pull media <name>` and `pull script <name>` extract single
  artifacts.

Both paths obey the never-overwrite rule.

Built-in blueprints and standalone media definitions are JSONC
documents (see
[format stability](machine-blueprint.md#format-stability-none-yet))
and use comments deliberately: a built-in blueprint annotates its
[customization seams](machine-blueprint.md#customization-seams) —
`// this parameter is your registered owner name` — so the
seeded copy teaches at exactly the point of edit (U5). Extraction
copies files verbatim, comments included.

## Non-redistributable media

**Top-priority rule: a built-in media definition may carry a
`url` only when it also carries the
[`redistributable-under` field](media-spec.md#definition-level-fields)
— the explicit assertion that the media's own licensing permits
redistribution, naming the license** (e.g. FreeDOS's
`"GPL-2.0-or-later"`). The assertion lives in the definition
itself, so the claim travels with the URL it justifies. No change adding or altering a URL in a built-in
media definition is accepted without it; absent the assertion, a
built-in definition ships hashes only. This is what keeps the
library shippable: reliquary never points at — or fetches —
media it has no right to distribute or induce the download of.

The library deliberately includes blueprints for operating systems
whose installation media cannot be distributed — Windows and other
commercial systems. Their built-in media definitions ship **with
hashes but without URLs**: the definition pins exactly which build
and edition the blueprint's scripts were written against, and the
user supplies the media themselves.

Materializing such a machine before the media is supplied **fast
fails by design**: resolution finds a definition with no download
source and no payload on disk, and stops before anything is
created, naming the missing media. That failure is the prompt —
the user pulls (or lets reliquary seed) the definition, then
adds their own `url` or `local-path` to it, pointing at the
media wherever they keep it — the cache is never hand-fed;
definitions are the interface, and a payload the user supplies
always enters through `local-path`. The SHA-256 hash then
verifies that what they supplied is the exact media the
scripts were built for (see
[media-spec.md](media-spec.md) for URL-less definitions and
`local-path`).

## Naming conventions

Built-in artifacts follow a convention that ties them together by
blueprint and script:

| artifact | pattern | example |
|---|---|---|
| blueprint | `<name>.json` | `freedos-1.4-plain.json` |
| script | `<blueprint>-<script-id>.rlqs` | `freedos-1.4-plain-install.rlqs` |
| script-aligned media | `<blueprint>-<script-id>-<drive>.json` | `freedos-1.4-plain-install-cdrom.json` |
| shared media | `<name>.json` | `freedos-1.4-livecd.json` |

A media definition specific to one script's step — the installer
CD that script inserts, a driver disk it stages — uses the
script-aligned pattern. A media definition shared across scripts
or blueprints uses a standalone name. Both resolve through the
same media library; the naming convention identifies ownership,
not a namespace.

## Named scripts on blueprints

A blueprint may declare a `scripts` map — short labels naming
`.rlqs` script files — plus optional `name` and `description`
fields for discovery (see the
[field reference](machine-blueprint-reference.md)). The labels are
the verbs you use with `script`:
`rlq --blueprint freedos-1.4-plain script install` looks up
`scripts.install` and runs the script it names, creating a machine
first when the blueprint has none.
