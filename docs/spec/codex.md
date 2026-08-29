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

The first command copies the blueprint — its media definitions
travel inside it — and the scripts it names into your own
directories, where they become ordinary files you own. The second
command creates a machine from your copy, fetches and verifies the
installation media, and runs the scripted install. **Using two
commands instead of one is deliberate** (U1): what runs is a file
you asked for by name and can read before you run it, and nothing
arrives from the library unasked.

## A library of examples

The codex is a **library of examples**. Both words matter. It is a
library: a curated collection, shipped with Reliquary, that you
list and seed from. It is not a library you build on: its entries
are reference material, meant as a starting point to copy rather
than as content your project depends on in place. They are meant
to work — a codex blueprint or script that does not work is a
defect, and the two commands above are the claim that it does —
but nothing about the codex is stable. The library changes with
every point release: `freedos-install` may be rewritten between one
release and the next, the `freedos` blueprint's disk may change
size, a media pin may move to a newer build, and an entry may be
renamed or dropped. Both an entry's name and what it holds can
change, and neither change waits for a version bump to announce it.
That is the whole meaning of "not stable" here: the codex you seed
from tomorrow is not promised to match the one you seeded from
today.

Do not read this as a restatement of the pre-1.0 compatibility
policy. Reliquary makes no backward-compatibility promise at all
before 1.0 ([ARCHITECTURE.md](../../ARCHITECTURE.md) P9), but that
policy is temporary and is expected to end once the project
matures. This rule is different: whatever promise the project
later makes about its application surfaces, codex content stays
outside it, because codex content is content, not a surface.

What this page specifies — the seeding rules, the never-overwrite
rule, the listing behavior, the media licensing rule — is the
surface, and that surface is stable in the normal way. The content
the codex carries is not (root
[ARCHITECTURE.md](../../ARCHITECTURE.md) P18).

None of this leaves you without stable assets; it just means you
get them a different way. The never-overwrite rule below is what
makes this safe, not just honest: once you seed a copy, it is an
ordinary file you own, and no later codex change ever touches it.
So the answer to "how do I depend on a codex script?" is: seed it,
then commit it. From that point the asset belongs to your project,
its stability is your project's responsibility, and the codex has
done its job — it gave you the starting point you built from. This
is the same answer P4 gives to automation in general, reached here
from the codex's side of it.

## A seed, not a resolution tier

The codex ships inside the Reliquary package as ordinary files
under `src/reliquary/codex/` (`blueprints/`, `scripts/`), so it
travels with every distribution form, including zip-bundled
installs. Wherever it lives, Reliquary never reads from the codex
at run time as a fallback source. Instead, when you reference a
codex artifact that does not yet exist in your home, Reliquary
**copies it out**. From that point on it is an ordinary,
user-owned file: edit it, delete it, put it under version control.
(The codex exists for interactive use only. It is never read by
automated runs — a project commits its own copies instead. See
[ARCHITECTURE.md](../../ARCHITECTURE.md) P4, the artifact-residency split.)

Two rules define this model:

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

**`list-codex` is the one command that reads the library**, and it
reads nothing else: it lists what the codex holds, never what your
own directories hold. `list-blueprints` is its counterpart, listing
your own directories and never the codex. So **the command you ran
tells you where a listed entry came from** — there is no column,
value, or field that reports it, because no listing ever mixes the
two sets (D88). `list-codex` prints names only; each entry's
`description` appears in the `--json` output instead, because that
text has no fixed length and does not fit a table column.

Neither command supports searching, of the codex or of your own
assets. Filtering a listing is something you do yourself — with a
shell pipe at the terminal, or a loop or comprehension in a
program — so no `search-` command exists for any of these nouns.

## Extraction

Extraction happens **only one way: on request.**

`seed-blueprint <name>` extracts the blueprint and everything it
references. It is the single command that takes you from "just use
the codex's version" to "I want to tweak it" — pass `--only` to
extract just the blueprint file itself. `seed-script <name>`
extracts a single script. There is no `seed-media`: media are
components inside a `.rlqb` file, and they are seeded along with
it (D30). All of these commands are CLI-only; none has an API twin
(D87).

**Nothing is extracted implicitly.** When Reliquary resolves a
name, it looks only in your own directories: a name they do not
hold is reported as not found, and the error message names the
`seed-` command to run for that name in the library. A codex
artifact only reaches your directories because someone asked for it
by name. That is what lets you see exactly where the copy came
from, and it is what keeps automated runs from depending on content
that can change in a point release (P4, P18).

Seeding obeys the never-overwrite rule.

Codex blueprints are JSON5 documents (see
[format stability](../blueprint-guide.md#format-stability-none-yet))
and use comments on purpose: a codex blueprint marks its
[customization seams](../blueprint-guide.md#customization-seams) —
the fields you are expected to change — with comments like
`// this parameter is your registered owner name`, right next to
the field itself, so the seeded copy explains what to edit at the
exact place you'd edit it (U5). Extraction copies files verbatim,
comments included.

## Non-redistributable media

**Top-priority rule: a codex media entry (or its `source`) may
carry a `url` only when that download is legally redistributable —
media whose own license permits Reliquary to point at it and fetch
it** (for example, the FreeDOS LiveCD, licensed under the GNU GPL,
or the official OpenBSD install media). This rule is enforced by
maintainers reviewing each addition, not by a field on the
component: Reliquary attaches no licensing metadata to a media
entry and cannot verify a license itself. The rule exists to keep
the codex shippable: Reliquary never points at, or triggers the
download of, media it has no right to distribute.

The codex deliberately includes blueprints for operating systems
whose installation media cannot be distributed — Windows and other
commercial systems. Their codex media ship **with hashes but
without URLs**: the hash pins exactly which build and edition the
blueprint's scripts were written against, and the user has to
supply the media file themselves.

The command for supplying it is **`rlq add-media <name> <file>`**:
it computes the file's SHA-256 hash and writes a blueprint entry
declaring that media, pointing at the file where it already sits
(D41). Nothing is copied, and nothing is added to the cache
automatically — what the user gets is a declaration they own and
can edit.

The user is free to edit that declaration, because the codex's
pinned hash states what the scripts were tested against, not a
requirement the user's file must meet. A retail disc, an OEM
variant, or a differently made rip will not match the codex hash,
and the user can keep their own copy anyway — the never-overwrite
seeding rule above is what makes an edited copy safe to keep. See
[media-spec.md](media-spec.md#supplying-what-the-project-cannot-distribute).

## Naming conventions

**The codex is a starting point, never a versioned library.**
Entries are named for the system, not the release — `openbsd`,
`freedos` — and no codex name ever carries a version number. Each
entry tracks one current release inside the file itself (in the
source component's URL and hash); a codex version bump is a
content update under the same, unchanged name, and it only reaches
new copies you seed after the bump — the never-overwrite rule keeps
every copy you already have exactly as it was. If you need a pinned
older version, a version running alongside others, or a variant,
that is your project's territory to handle: seed the generic entry,
rename your copy, and make the changes you need. Scripts are named
for the install flow they drive, not for a release — a
well-authored install script works across versions by watching for
stable prompts and branching when it observes a difference
(script-spec), and you can see which versions it supports by
reading its own handlers.

The contract stops there, on purpose. Each entry keeps its two
version-pin points easy to find and change, where that is easy: the
source component's URL and its hash sit next to each other in one
component, and a codex blueprint's customization-seam comments
point at them, because new versions come out regularly and updating
those two values is the supported way to track one. But the codex
never promises a complete, guaranteed-working matrix of every
system and every version — that set has no boundary. An entry is
tested as
shipped, against the one release it tracks. If you bump a copy to
a newer release, that is your own experiment — everything that
fails safely still protects you, such as hash verification and
script waits that time out exactly at the point where the new
release diverges — but nothing guarantees the result will work.

Codex artifacts follow a naming convention that ties a blueprint to
its scripts:

| artifact | pattern | example |
|---|---|---|
| blueprint | `<name>.rlqb` | `freedos.rlqb` |
| script | `<blueprint>-<script-id>.rlqs` | `freedos-install.rlqs` |

Media are components inside the blueprint, not files of their own,
so they are identified by a component *name* rather than a
filename: conventionally `<blueprint>-<script-id>-<drive>` for
media specific to one step of one script (the installer CD it
inserts, a driver disk it swaps in), or a standalone `<name>` for
media shared across scripts or blueprints. Both forms resolve
through the same namespace — the naming convention just signals
who owns the entry, it does not create a separate namespace.

## Named scripts on blueprints

A blueprint may declare a `scripts` map — short labels naming
`.rlqs` script files — plus an optional `description` field for
discovery (see the [field reference](../blueprint-reference.md)).
The labels are the command names you use with `run-script`:
`rlq run-script install --blueprint freedos` looks up
`scripts.install` and runs the script it names, creating a machine
first if the blueprint doesn't already have one.
