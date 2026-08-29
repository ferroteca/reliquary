<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Authored binary assets

> **Status:** This document describes how Reliquary stores binary
> data that an author supplies to a script. It is written down once
> because more than one kind of binary asset now needs this shape.
> It was first settled for landmark renderings during the 2026-07-21
> owner rounds
> ([docs/spec/landmarks.md](../../docs/spec/landmarks.md), where the
> finished spec now lives; the decision trail is in
> [DECISIONS.md](../DECISIONS.md)), and this document generalizes
> that settlement rather than deciding anything new. It lives in
> `design/` rather than inside one feature file because no single
> feature owns it: landmarks are one case, the fonts that **U25**
> needs are a second, and the recorder in **U6** is a third. **This
> document does not authorize building anything.** A kind that
> adopts this shape still has to go through its own proposal, and
> still needs the surface-change rule ([SURFACES.md](../SURFACES.md))
> to cover any new vocabulary it adds. **The font kind has now done
> exactly that** (2026-08-19): U25 and U27 are pledged, and **F61**
> ([pledged/FEATURES.md](../pledged/FEATURES.md)) is the feature
> that adopts this shape — a `.rlqf` file sits beside its glyph
> bank, both draw from the one shared `@` pool, and the declaration
> records the cell size and the codepage, since the raw bytes can't
> state either (D109). **The landmark kind has since shipped too**
> (F65, 2026-08-24): a `.rlql` file sits beside its numbered PNG
> renderings, using the same one `@` pool and the same kind of fixed
> location under the Reliquary home directory.

## The question

A Reliquary script is a plain UTF-8 text file — that is the limit
P14 sets: a script never has a second file format embedded inside
it ([P14](../../ARCHITECTURE.md)). But some of what a script needs
is not text — a screen rendering to compare against, or a glyph
bank to read a screen through. Where does that non-text data live,
and how does the script refer to it?

The answer should be the same every time. Writing it down once here
is what stops a third case from inventing a fourth way to do it.

## The shape

**A declaration file, found the same way as every other authored
asset.** The declaration is a JSON5 document written by hand, with
its own file extension alongside `.rlqb` / `.rlqs` / `.rlql`.
Reliquary finds it by that extension, under the same resolution
rules as everything else
([docs/spec/asset-resolution.md](../../docs/spec/asset-resolution.md)).
Grouping the files together in a subdirectory is optional and purely
cosmetic — it is never part of how the asset is identified.

**The binary files sit next to the declaration; the declaration
never lists them by path.** Each binary is an ordinary file in its
own normal format — a PNG is just a PNG. Its filename is built from
the declaration's stem, with a number added where order matters
(landmarks: `<name>.<n>.png`). Because the declaration does not
contain a path list, adding a new binary means **creating a new
file** rather than rewriting the declaration. That matters because
a capture tool (U6) needs to add to an author's asset without
touching anything the author wrote.

**One shared pool of names.** Every asset is referred to as
`@name`, drawn from the same pool of names that media files and
landmarks already share, and that pool is checked for collisions.
If a script can see two assets with the same name, that is an
error, and the error message names both locations. Sharing one pool
is what lets code resolve any `@name` without knowing what kind of
asset it is first — and it is why adding a new kind of asset only
costs a collision rule, not a whole new namespace.

**Never written inline inside a script.** There is no inline block
for a binary asset, just as there is none for a media file (decided
by the owner on 2026-07-22, the round that removed JSON from
scripts). Writing one inline would force it to be base64-encoded —
thousands of lines of encoded data wrapped around a hundred lines of
actual script logic — and would lock the asset format as text
forever, since what a text script carries can never become
non-text. Keeping the declaration in its own file lets each binary
format change independently, keeps scripts easy to read (G4), and
lets one resolution rule handle every authored file extension.

**The declaration states what the raw bytes cannot say.** A binary
file only contains its own content. Whatever a consumer needs beyond
that content goes in the declaration instead — a landmark's
geometry, regions, and spots; or a font's cell dimensions, which a
4096-byte file cannot tell you on its own (256 glyphs of 16 rows and
512 glyphs of 8 rows are the same file length — there is no way to
tell them apart just by looking at the bytes). Trying to work that
out by inspecting the file would mean guessing, so the interface
between Reliquary and the file requires it to be declared instead
([P10](../../ARCHITECTURE.md)).

## What this is not

**This is not media.** Media files are what the guest sees: they
are fetched, pinned to a checksum, cached, and attached to a virtual
drive ([docs/spec/media-spec.md](../../docs/spec/media-spec.md)). A
binary asset described in this document is different: it is data
Reliquary itself uses to interpret what is on the guest's screen,
not something the guest boots or reads. The two stay separate kinds
even in a case where the same file could technically be used either
way — what decides which kind it is is whether the host side or the
guest side consumes it.

**This is not a working directory of its own.** Assets are found in
the directories that already exist for the kind that declares them.
This shape does not add a seventh directory that a project could
place independently ([P12](../../ARCHITECTURE.md)).

**This is not a capture mechanism.** How an asset comes to exist in
the first place — through a recorder, a dump taken from the guest,
or a maintainer writing it by hand — is a question for each specific
kind of asset to answer on its own. This document says only where
the finished asset lives once it exists.
