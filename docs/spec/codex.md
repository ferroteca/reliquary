<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# The codex

> **Status:** the seeding core — the packaged tree, seeding on
> request, and the never-overwrite rule — is implemented, and so
> are `seed-blueprint` / `seed-script` and `list-codex`, all three
> CLI-only (D87). The index ships
> for **blueprint names and descriptions only**: script and media
> entries and the relationship data described below are still
> planned, and nothing reads them, so the codex derives media from
> the blueprints that declare them. Details may change before
> first release.

The codex is Reliquary's built-in seed content: a shipped
collection of blueprints (their media, source, and archive
components included) and scripts for
popular open source operating systems, so the common case is two
commands from a clean home:

```powershell
rlq seed-blueprint freedos
rlq run-script install --blueprint freedos
```

The first copies the blueprint (its media ride inside it) and the
scripts it names into your own directories, where they are ordinary
files you own. The second creates a machine from your copy, fetches
and verifies the installation media, and runs the scripted install.
**Two commands rather than one is the point** (U1): what runs is a
file you asked for by name and can read before you run it, and
nothing arrives from the library unasked.

## A library of examples

The codex is a **library of examples**, and both words carry
weight. It is a library: a curated collection, shipped with
Reliquary, that you list and seed from. What it is not
is a library you build on — its entries are reference material, a
starting point to copy rather than content to depend on in place.
They are meant to work — a codex blueprint or script that does
not is a defect, and the commands above are the claim — but nothing
about it is stable. The library evolves, and evolves in a
**point release**: `freedos-install` may be rewritten between one
and the next, the `freedos` blueprint's disk may change size, a
media pin may move to a newer build, an entry may be renamed or
dropped altogether. Neither a name nor what it holds is fixed —
both axes move — and none of it waits for a version bump that
would announce it. That is the whole of what "not stable" means
here: the codex you seed from tomorrow is not promised to be the
one you seeded from today.

Do not read this as the pre-1.0 licence restated. Reliquary
makes no backward-compatibility promise before 1.0 at all
([ARCHITECTURE.md](../../ARCHITECTURE.md) P9), but that licence
is scaffolding and is expected to come down as the project
matures. This rule is not: whatever promise the project comes to
make about its application surfaces, codex content stays outside
it, because it is content rather than surface.

What is specified is on this page — the seeding semantics, the
never-overwrite rule, the listing, the media licensing rule — and
*that* is the surface; the content it carries is not (root
[ARCHITECTURE.md](../../ARCHITECTURE.md) P18).

None of which leaves you without stable assets — it locates them
somewhere else. The never-overwrite rule below is what makes this
safe rather than merely honest: once you seed a copy it is an
ordinary file you own, and no codex change ever reaches it. So
the answer to "how do I depend on a codex script?" is to seed it
and commit it. From that point the asset is your project's, its
stability is your project's to hold, and the codex was what it is
for — the starting point you built it from. This is the same
answer P4 gives automation, arrived at from the other side.

## A seed, not a resolution tier

The codex ships inside the Reliquary package as ordinary files
under `src/reliquary/codex/` (`blueprints/`, `scripts/`),
so it travels with every distribution form, including zip-bundled
installs. Wherever it lives, the codex is
never consulted at run time as a fallback layer. Instead, when you
reference a codex artifact that does not yet exist in your home,
Reliquary **copies it out**. From that point on it is an ordinary
user-owned file — edit it, delete it, version it. (The codex
serves the home's human-interaction side only: it is never used
for machine automation — a project commits its own copies. See
[ARCHITECTURE.md](../../ARCHITECTURE.md) P4, the artifact-residency split.)

Two rules carry the model:

- **A file already present in your home is never overwritten.**
  There is no shadowing, no precedence order, and no "codex
  update changed my machine" surprise: what your home contains is
  what runs, always.
- **Deleting your copy is how you refresh it.** Once you delete a
  file yourself, the next reference (or an explicit `seed-`)
  extracts the current codex copy again. An orphaned reference — a
  blueprint naming a script you removed — re-seeds the same way.

## The index, and listing what the library holds

The codex carries an index mapping every codex artifact to
its `description` and relationships (which scripts a blueprint
references; its media travel inside it). Today the index carries
blueprint names and descriptions and nothing else (see the banner);
a media name is read from the blueprint that declares it, which is
where media live (D30).

**`list-codex` is the one verb that reads the library**, and it
reads nothing else: it names what the codex holds, never what your
directories hold, and `list-blueprints` is its mirror image. So
**which command you ran is the provenance** — there is no column,
value or field reporting where a row came from, because no listing
mixes the two sets (D88). It prints names alone; each entry's
`description` rides the `--json` record, unbounded free text being
a column a fixed-width table cannot hold.

There is no searching, of the codex or of your own assets.
Filtering a listing is a pipe on a terminal and a comprehension in
a program, so no `search-` verb exists for any noun.

## Extraction

Extraction happens **one way: on request.**

`seed-blueprint <name>` extracts the blueprint and everything it
references — the one-stop bridge from "just use the codex's" to "I
want to tweak it" (`--only` restricts it to the blueprint file
itself); `seed-script <name>` extracts a single script. There is no
`seed-media`: media are components inside a `.rlqb` and are seeded
with it (D30). All of it is CLI-only, with no API twins (D87).

**Nothing is extracted implicitly.** Resolution reads your
directories and stops there: a name they do not hold is not found,
and the refusal names the seed command where the library has that
name. A codex artifact reaches a tree because someone asked for it
by name — which is what makes the copy legible, and what keeps
automation from depending on content that moves in a point release
(P4, P18).

Seeding obeys the never-overwrite rule.

Codex blueprints are JSON5
documents (see
[format stability](../blueprint-guide.md#format-stability-none-yet))
and use comments deliberately: a codex blueprint annotates its
[customization seams](../blueprint-guide.md#customization-seams) —
`// this parameter is your registered owner name` — so the
seeded copy teaches at exactly the point of edit (U5). Extraction
copies files verbatim, comments included.

## Non-redistributable media

**Top-priority rule: a codex media (or its `source`) may carry a
`url` only when that download is legally redistributable — media
whose own licensing permits Reliquary to point at and fetch it**
(e.g. the FreeDOS LiveCD under the GNU GPL, or the official OpenBSD
install media). This is a maintainer discipline enforced at review,
not a per-component field: Reliquary attaches no licensing
metadata to a media and cannot verify a license. The rule is
what keeps the codex shippable — Reliquary never points at, or
induces the download of, media it has no right to distribute.

The codex deliberately includes blueprints for operating systems
whose installation media cannot be distributed — Windows and other
commercial systems. Their codex media ship **with hashes but
without URLs**: the media pins exactly which build and edition the
blueprint's scripts were written against, and the user supplies the
media themselves.

The supply seam is **`rlq add-media <name> <file>`**: it computes
the file's SHA-256 and writes a blueprint declaring that media,
located at the file where it already sits (D41). Nothing is copied,
and nothing is hand-fed into the cache — what the user gains is a
declaration they own.

That declaration is theirs to edit, and the codex's pin is a
statement of *what the scripts were tested against*, not a gate the
user must satisfy. A retail disc, an OEM variant, or a differently
made rip will not match the codex hash, and the user is free to
keep their own — the never-overwrite seeding rule above is what
makes an edited copy safe. See
[media-spec.md](media-spec.md#supplying-what-the-project-cannot-distribute).

## Naming conventions

**The codex is a launching point, never a version library.**
Entries are named for the system, not the release — `openbsd`,
`freedos` — and no codex name ever carries a version. Each entry
tracks one current release *inside* the file (the source
component's URL and hash); a codex version bump is a content
update under an unchanged name, reaching new seeds only — the
never-overwrite rule keeps every existing copy yours. Pinned
vintages, concurrent versions, and variants are user and
project territory: seed the generic entry, rename your copy,
make it real. Scripts are named for the flow they drive, not a
release — a well-authored install script spans versions by
watching stable prompts and branching on observed divergence
(script-spec), and its supported span is legible in its own
handlers.

The contract stops there, deliberately. Each entry keeps its
version *control points* nominal and legible where that is
easy — the source component's URL and hash sit adjacent, one
component, and a codex blueprint's seam comments point at them —
because version churn is a fact and turning those two knobs is
the supported move. But the codex never promises a
comprehensive, guaranteed-working matrix of systems and
versions — that set is unboundable. An entry is tested as
shipped, against the one release it tracks; a bumped copy is
the user's experiment, aided by everything that fails closed —
hash verification, script waits timing out at the exact
divergence point — and warranted by nothing.

Codex artifacts follow a convention that ties them together by
blueprint and script:

| artifact | pattern | example |
|---|---|---|
| blueprint | `<name>.rlqb` | `freedos.rlqb` |
| script | `<blueprint>-<script-id>.rlqs` | `freedos-install.rlqs` |

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
[field reference](../blueprint-reference.md)). The labels are
the verbs you use with `run-script`:
`rlq run-script install --blueprint freedos` looks up
`scripts.install` and runs the script it names, creating a machine
first when the blueprint has none.
