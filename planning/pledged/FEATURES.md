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
