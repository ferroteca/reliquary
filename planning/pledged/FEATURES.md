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

## F40 — The at-rest handover

> Delivers **P27** ([ARCHITECTURE.md](ARCHITECTURE.md), beside
> this file): Remanence owns at-rest disk access, pinned at
> `remanence==0.0.1a2`. Landing the last item arms the principle —
> D34's automatic move, named here so the piece that lands last
> knows it closes the arc.

The switch is atomic by principle: P27's whole-layer-or-none
clause refuses any landed state holding two authorities for the
same disk facts, so the items below order one delivery rather than
staging several. The seam decision and the translation table are
in [design/remanence-at-rest.md](design/remanence-at-rest.md).

Work items:

1. Pin `remanence==0.0.1a2` — exact and unconditional — in
   `pyproject.toml` and the lock. No platform marker: the wheel is
   Windows-only and so is the delivered host (P11); a non-Windows
   resolve fails loudly rather than leaving the capability quietly
   absent.
2. Rebuild `at_rest.py` as the translation module: a disk opens
   where it lies through `remanence.Disk`; geometry translates to
   the recorded report shape unchanged, the whole-disk refusal
   preserved when any partition row carries an issue; the letter
   map's volume index resolves to Remanence's stable volume id at
   open; the exchange verbs, commit and rollback ride the same
   handle; Remanence's error categories map onto the standing
   rule ids.
3. Retire the transport and the seam: `nbd.py` goes whole;
   `backend_qemu.py` loses the served access (the `qemu-nbd`
   lifecycle and the at-rest snapshot commit point), the staged
   raw access, and the `qemu-nbd` tool discovery; `open_drive`
   leaves the adapter protocol, `capabilities().at_rest` staying
   as the adapter's declaration; `machines.py` consumes the
   translation module directly.
4. Re-point the suite: the reader and transport unit tests
   (`test_at_rest.py` internals, `test_nbd.py`) leave with their
   subjects, whose coverage Remanence owns; the consumer
   journeys — report shape, exchange, the locking refusal, the
   volume-vanished guard — pass unchanged on the new path.
5. Sweep the prose: AGENTS.md's module map and the CHANGELOG.
6. Promote P27: enter it in root ARCHITECTURE.md, delete it
   beside this file, and file every known residue as a defect in
   the same change (D34; D48).
