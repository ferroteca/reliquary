<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Authored binary assets

> **Status:** the storage shape for binary data an author supplies
> to a script, stated once because it now has more than one
> instance. It was settled for landmark renderings in the 2026-07-21
> owner rounds ([pledged/design/landmarks.md](../pledged/design/landmarks.md);
> the adjudication trail is in [DECISIONS.md](../DECISIONS.md)) and
> this document generalizes that settlement rather than deciding
> anything new. It sits in `design/` because it serves no single
> feature: landmarks are one instance, the fonts **U25** needs are
> a second, and **U6**'s recorder captures a third. **It authorizes
> no implementation.** A kind adopting the shape still arrives as
> its own proposal and takes the surface-change rule
> ([SURFACES.md](../SURFACES.md)) for the vocabulary it adds. **The
> font kind has now done exactly that** (2026-08-19): U25 and U27
> are pledged, and **F61**
> ([pledged/FEATURES.md](../pledged/FEATURES.md)) is the entry that
> adopts this shape — `.rlqf` beside its bank, one `@` pool, the
> declaration owning the cell size and the codepage the bytes cannot
> state (D109).

## The question

A script is UTF-8 text ([P14](../../ARCHITECTURE.md), the
expressive ceiling: a script never nests a second format). Some of
what a script needs is not text — a screen rendering to match
against, a glyph bank to read a screen through. Where does it live,
and how does the script name it?

The answer is the same every time, and writing it once is what
stops the third instance from inventing a fourth spelling.

## The shape

**A declaration file, resolved like every other authored asset.**
The declaration is an authored JSON5 document with its own
extension beside `.rlqb` / `.rlqs` / `.rlql`, discovered by
extension under the ordinary resolution rules
([docs/spec/asset-resolution.md](../../docs/spec/asset-resolution.md)).
A subdirectory grouping the files is optional dressing and never
part of the identity.

**The binaries sit beside it, attached by adjacency.** They are
plain files in their own ordinary formats — a PNG is a PNG —
named by stem from the declaration and ordered where order
matters (landmarks: `<name>.<n>.png`). Adjacency rather than a
path list inside the declaration is what makes adding one a
**file creation** rather than a file rewrite, which is what a
capture tool needs in order to add to an author's asset without
touching what the author wrote (U6).

**One reference pool.** An asset is named `@name`, out of the same
collision-checked pool media and landmark names already share; a
duplicate visible to one script is an error naming both locations.
One pool is what lets a reader resolve any `@name` without knowing
its kind first, and it is why a new kind costs a collision rule
rather than a namespace.

**Never embedded in a script.** There is no inline block for a
binary asset, as there is none for a media (owner, 2026-07-22, the
no-JSON-in-scripts round). Embedding forces base64 — thousands of
lines of payload around a hundred lines of procedure — and freezes
the asset format as text forever, since what a text script carries
can never become non-text. Keeping the declaration in its own file
leaves each format free to grow, keeps scripts legible (G4), and
lets one resolution rule serve every authored extension.

**The declaration owns what the bytes cannot say.** A binary is
only its own content; what a consumer needs beyond that goes in
the declaration — a landmark's geometry, regions and spots; a
font's cell dimensions, which a 4096-byte file cannot distinguish
(256 glyphs of 16 rows and 512 of 8 are the same length). Deriving
that by inspection is guessing, and this is the seam that keeps it
declared instead ([P10](../../ARCHITECTURE.md)).

## What this is not

**Not media.** Media are guest-facing payloads: fetched, hash-pinned,
cached, and attached to a drive
([docs/spec/media-spec.md](../../docs/spec/media-spec.md)). A binary
asset here is host-side interpretation data — what Reliquary reads a
screen *through*, not what the guest boots. The two are separate
kinds even where a file could technically travel either way, and the
test is which side of the seam consumes it.

**Not a working directory of its own.** Assets resolve out of the
directories that already exist for the kind that declares them; this
shape adds no seventh placeable root
([P12](../../ARCHITECTURE.md)).

**Not a capture mechanism.** How an asset comes to exist — a
recorder, a guest dump, a maintainer's own file — is each kind's own
question and is argued with that kind. This document says only where
the result lives once it exists.
