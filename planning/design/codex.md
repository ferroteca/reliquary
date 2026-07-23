<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# The codex

> **Status:** the seeding core — the packaged tree, copy-out on
> first reference, and the never-overwrite rule — is implemented.
> The index, provenance columns, `search-`, and `seed-` are still
> planned; details may change before first release.

The codex is reliquary's built-in seed content: a shipped
collection of blueprints (their media, source, and archive
components included) and scripts for
popular open source operating systems, so the common case is one
command from a clean home:

```powershell
rlq run-script install --blueprint freedos-1.4-plain
```

That single command extracts the blueprint (its media ride inside
it) and its scripts from the codex, creates a machine, fetches and
verifies the installation media, and runs the scripted install.

## A seed, not a resolution tier

The codex ships inside the reliquary package as ordinary files
under `reliquary/codex/` (`blueprints/`, `scripts/`),
so it travels with every distribution form, including zip-bundled
installs. Wherever it lives, the codex is
never consulted at run time as a fallback layer. Instead, when you
reference a codex artifact that does not yet exist in your home,
reliquary **copies it out**. From that point on it is an ordinary
user-owned file — edit it, delete it, version it. (The codex
serves the home's human-interaction side only: it is never used
for machine automation — a project commits its own copies. See
[planning/USE-CASES.md](../USE-CASES.md), the artifact-residency split.)

Two rules carry the model:

- **A file already present in your home is never overwritten.**
  There is no shadowing, no precedence order, and no "codex
  update changed my machine" surprise: what your home contains is
  what runs, always.
- **Deleting your copy is how you refresh it.** Once you delete a
  file yourself, the next reference (or an explicit `seed-`)
  extracts the current codex copy again. An orphaned reference — a
  blueprint naming a script you removed — re-seeds the same way.

## The index and provenance

The codex carries an index mapping every codex artifact to
its `description` and relationships (which scripts a blueprint
references; its media travel inside it). User-owned files
are indexed by reading the same optional fields from the file.
`search` queries both.

Listings report provenance by name:

| CODEX | meaning |
|---|---|
| `yes` | a codex entry not yet extracted into your home |
| `seeded` | a user file whose name also exists in the codex |
| (blank) | a purely user-authored file |

## Extraction

Extraction happens two ways:

- **Implicitly, on first reference.** Any operation that resolves
  a blueprint or script name checks the home
  first, then the codex; a codex hit is copied out (a
  blueprint brings its referenced scripts with it, and its media
  ride inside it) and resolution proceeds against the new user file.
- **Explicitly, with the `seed-` family.** `seed-blueprint
  <name>` extracts
  the blueprint and everything it references — the one-stop bridge
  from "just use the codex's" to "I want to tweak it"
  (`--only` restricts it to the blueprint file itself);
  `seed-script <name>` extracts a single script (API twins
  `seed_blueprint(name, only=)` / `seed_script`; `seed_media` is a
  deprecated no-op — media are components inside a `.rlqb` now).

Both paths obey the never-overwrite rule.

Codex blueprints are JSONC
documents (see
[format stability](machine-blueprint.md#format-stability-none-yet))
and use comments deliberately: a codex blueprint annotates its
[customization seams](machine-blueprint.md#customization-seams) —
`// this parameter is your registered owner name` — so the
seeded copy teaches at exactly the point of edit (U5). Extraction
copies files verbatim, comments included.

## Non-redistributable media

**Top-priority rule: a codex media (or its `source`) may carry a
`url` only when that download is legally redistributable — media
whose own licensing permits reliquary to point at and fetch it**
(e.g. the FreeDOS LiveCD under the GNU GPL, or the official OpenBSD
install media). This is a maintainer discipline enforced at review,
not a per-component field: reliquary attaches no licensing
metadata to a media and cannot verify a license. The rule is
what keeps the codex shippable — reliquary never points at, or
induces the download of, media it has no right to distribute.

The codex deliberately includes blueprints for operating systems
whose installation media cannot be distributed — Windows and other
commercial systems. Their codex media ship **with hashes but
without URLs** — pinned but *unlocated*, naming a `source`
component nothing supplies yet: the media pins exactly which build
and edition the blueprint's scripts were written against, and the
user supplies the media themselves.

Materializing such a machine before the media is supplied **fast
fails by design**: resolution finds a media with a pinned hash and
a missing source, and stops before anything is created, naming the
missing media and source. That failure is the prompt — the user
drops a matching `source` component beside the seeded blueprint (a
`local` path, or a `url`), **without editing the seeded media** —
the cache is never hand-fed; components are the interface. The
SHA-256 hash then verifies that what they supplied is the exact
media the scripts were built for (see
[media-spec.md](media-spec.md#unlocated-media-non-redistributable)).

## Naming conventions

Codex artifacts follow a convention that ties them together by
blueprint and script:

| artifact | pattern | example |
|---|---|---|
| blueprint | `<name>.rlqb` | `freedos-1.4-plain.rlqb` |
| script | `<blueprint>-<script-id>.rlqs` | `freedos-1.4-plain-install.rlqs` |

Media are components inside the blueprint, not files of their own,
so they carry component *names* rather than filenames: conventionally
`<blueprint>-<script-id>-<drive>` for a media specific to one
script's step (the installer CD it inserts, a driver disk it swaps
in), or a standalone `<name>` for one shared across scripts or
blueprints. Both resolve through the same namespace; the naming
convention identifies ownership, not a namespace.

## Named scripts on blueprints

A blueprint may declare a `scripts` map — short labels naming
`.rlqs` script files — plus an optional `description`
fields for discovery (see the
[field reference](machine-blueprint-reference.md)). The labels are
the verbs you use with `run-script`:
`rlq run-script install --blueprint freedos-1.4-plain` looks up
`scripts.install` and runs the script it names, creating a machine
first when the blueprint has none.
