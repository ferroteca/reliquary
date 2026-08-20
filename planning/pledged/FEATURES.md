<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Pledged features

Large capability that is **pledged but not yet built**, each
carrying the work breakdown that delivers it. A feature arrives here
by being moved out of
[proposed/FEATURES.md](../proposed/FEATURES.md) — the move is the
pledge and the commit is its record ([README.md](../README.md))
— and leaves by being delivered, or by being **withdrawn** back to
that file when the pledge turns out to be one nobody meant (D44;
first used by D61).

Pledged is not scheduled: the numbered milestone arc ended with
milestone 9, so nothing below is queued or dated. The work items are
tasks like any other and answer to the same rules as
[TASKS.md](../TASKS.md); they sit with their feature rather than in
that queue because they are meaningless apart from it.

Each feature carries an **F-number** and must fit in **one sprint**
(D42; the rules are in [README.md](../README.md)). A feature too
large is cut on pledge, the split retiring the parent's number
for a fresh one per piece.

**F-numbers are issued against the sequence ledger**
([SEQUENCES.md](../SEQUENCES.md); owner, 2026-07-31): take the
next mark there and advance it in the same edit, by whichever
door the entry arrives — drafted in
[proposed/FEATURES.md](../proposed/FEATURES.md), or cut straight
to this file on pledge.

## F61 — The authored glyph font, and the statement that names it

> **Pledged 2026-08-19** (owner), cut straight to this file in the
> act that pledged **U25** and **U27**. It is **U27's whole
> delivery**, so that promotion to root
> [USE-CASES.md](../../USE-CASES.md) rides with it (D34); U25 needs
> **F62** as well and stays pledged until it lands. Serves **U25**,
> **U27**. Weighed against **P14**, which is what makes a new
> statement expensive; **P10**, which is why the declaration declares
> what the bytes cannot say rather than inferring it; and **P12**,
> which the fonts directory answers to. It is the second instance of
> [design/authored-binary-assets.md](../design/authored-binary-assets.md)
> and the proposal that document said each adopting kind still owes.
> The contested calls — the spelling, the declaration's content, and
> the match order — are **D109**.

The agentless display plane reads a screen through every font the
*host's* hypervisor binaries carry, and through nothing else
(`text_recognize.banks_from_binary`). A guest that loads a face of
its own is read through fonts that do not include it, and the run
ends at a timeout counting cells it could not read. This is the
asset that face becomes, and the word a script uses to put it in
front of the host's.

**The asset.** `<name>.rlqf`, a JSON5 authored document — the fourth
authored extension beside `.rlqb` / `.rlqs` and the reserved
`.rlql` — with the bank itself a plain file attached by stem
adjacency, `<name>.bin`. Discovery is by the declaration's
extension under the ordinary resolution rules
([docs/spec/asset-resolution.md](../../docs/spec/asset-resolution.md)),
out of a `fonts/` directory joining the layout exactly as
`landmarks/` is reserved to; a subdirectory grouping the pair is
optional dressing and never part of the identity. The name comes out
of the collision-checked `@` pool that media and landmark names
already share, so a duplicate visible to one script is an error
naming both locations. **P12 is not in the way**: it governs where
Reliquary *writes*, and nothing writes a font — this adds a read
directory for an authored kind, which is what the `landmarks/`
reservation already is.

**What the declaration states** is exactly what the bytes cannot
say:

- **the cell size.** 256 glyphs of 16 rows and 512 of 8 are the same
  4096 bytes, so the geometry is declared and never inferred — the
  seam P10 exists to keep declared.
- **the codepage its indices mean.** A bank is shapes; what a
  matched index *is* comes from the codepage the guest loaded, and a
  localized installer is the case's own example. A cell matched in
  an authored bank decodes through that bank's codepage. **The
  host's own banks keep today's mapping** (printable ASCII, else the
  code point), so no recorded transcript, fixture, or corpus entry
  moves on this delivery.

**The statement.** `font @guest` states a **prefix**, from that point
in the run forward: the fonts it names are tried first and the
host's follow, and a second `font` replaces the prefix rather than
appending to it. It is a new action kind in the node shape the
language already has (G7) — not a new construct, and deliberately
not a `with` head: the head vocabulary there is closed at three
names, all of them durable machine changes the scope exists to undo,
and a font changes nothing on the machine and has nothing to put
back. It is equally not a header declaration, which cannot express
the thing the case is about — the painting authority changes
mid-boot, and only the script knows when (D109).

**The match order becomes a real priority.** Today every bank's
shapes are unioned and the globally nearest wins, order breaking
ties alone (`text_recognize._match_glyph_with_distance`) — under
which naming a font could only ever *add* one more chance for a
near-match to beat the true glyph, the opposite of what the case
asks for. The first bank whose best match is inside the threshold
decides. That is what makes the narrowing real, and it is also what
makes the per-bank codepage well defined: without an ordered
decision, "the bank that matched" names nothing.

**A wrong font must say so.** The unread-cell count a failure report
already carries gains the fonts the screen was read through, in the
order they were tried, so an author who named the wrong face is told
what was actually consulted rather than left with a silent timeout
(P11).

Work items:

1. The declaration: schema, reader, and the fail-closed refusals — a
   bank whose length disagrees with the declared cell size, an
   unknown codepage, a declaration with no adjacent bank.
2. Resolution: the extension, the `fonts/` directory landing in
   `asset-resolution.md` beside the `.rlql` reservation, and the `@`
   pool collision check.
3. The statement: grammar, execution, and preflight — an
   unresolvable `@name` fails closed before the machine starts, with
   the static rule taking a V-number issued against
   [SEQUENCES.md](../SEQUENCES.md) when it lands.
4. The recognizer: ordered banks, first-inside-threshold decision,
   per-bank decode, and the authored prefix reaching it from the run.
5. Reporting: the fonts consulted on the failure report and the run
   event stream.
6. Documentation: the asset in `docs/spec/`, the statement in
   `script-spec.md`, and U27's promotion to root
   [USE-CASES.md](../../USE-CASES.md) in the same change (D34).

## F62 — The DOS font dump

> **Pledged 2026-08-19** (owner), cut straight to this file in the
> act that pledged **U25**, whose second half it is: with **F61**
> landed this is what remains before U25's promotion to root
> [USE-CASES.md](../../USE-CASES.md), which rides with it (D34).
> Serves **U25**; nothing in it depends on F61's code, and no use
> case is met until both have landed. **P2** is what it runs under — agentless, at a prompt,
> with no guest prerequisite — **P3** is what it must not become,
> and **P16** with **D108** is why the bytes cross on a drive rather
> than through Reliquary. The transport and its rejected
> alternatives: **D109**.

The guest is the only party that knows which font it loaded, and on
DOS it can be asked. `INT 10h AH=11h AL=30h` with `BH=03h` returns a
pointer to the **live** character table — the one the guest
installed, not the ROM bank — all 256 glyphs, 4096 bytes.

**A codex script, not a program.** `freedos-dump-font.rlqs` ships in
the codex (S6) beside the install / verify / ready trio and is
seeded like them (`rlq seed-script`, U11). It boots the installed
disk, waits for the prompt, types a `DEBUG` stub that makes the call
and writes the table out, and powers the machine off. Nothing
remains in the guest: the stub is typed, runs once, and goes with
the machine — this is not an agent and never becomes one (P3), and
typing a staged file at the prompt is the idiom the install script
already uses.

**The drive is the author's.** The script writes `FONT.BIN` to a
slot the blueprint declares, and the codex blueprint declares none,
because a host directory is the author's own path. Reliquary
supplies the drive the file crosses on and nothing inside it (P16,
D108, U14); the author reads the bytes off their own disk. A run
against a blueprint with no such slot fails closed naming it rather
than dumping into nowhere (P11).

**Two bounds, named rather than discovered later.**
Directory-source drives are QEMU-only
(`backend_virtualbox.py`: `vvfat=False`), so the dump runs on QEMU —
while the asset it produces is portable to every backend, because
the font is the guest's and not the host's. And the file is on the
host directory once the machine stops, which is why the script ends
by powering off rather than handing back a live machine.

Work items:

1. **First, and the feature stands on it**: prove `DEBUG` is present
   in the codex's own FreeDOS 1.4 install. If it is not, the stub is
   staged the way the install script stages files, and that is the
   work instead.
2. The script, its blueprint keying in the codex index, and the
   preflight for the missing drive slot.
3. An integration test against a real guest, in the tier the suite
   already has for them, asserting 4096 bytes on the host directory.
4. `docs/dos-automation.md` gains the dump.
5. U25's promotion to root [USE-CASES.md](../../USE-CASES.md) in the
   change that lands this, F61 having landed (D34).
