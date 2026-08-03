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

## F42 — The screen transcript: capture and reconstruction

> **Pledged 2026-08-01** (owner), cut from F13 with F43 and
> proposed F44, that number retiring with the split (D42). Demanded
> by **P22** — the suite is the gate, and this is what would make
> that gate real for the interpretation layer, which today has no
> honest way to be tested at all. Shaped by **P11**, **P6** and
> **P12**. Design:
> [design/screen-transcripts.md](design/screen-transcripts.md);
> the D36 squaring and the format's standing are **D98**.

**Capture and reconstruction land together**, because a transcript
format with no reader is an unverified format: nothing would prove a
capture is reconstructible, and the format would be wrong in ways
only F43's fixtures would eventually discover.

**Recording is a debugging tool, not a reward for success.** It is
worth having *before* the heuristics are reliable, not after —
capture the boots where prompt detection fails, and each capture
becomes a regression fixture. The pathological captures are the
valuable ones, and they are most abundant now. It also makes
inspectable what is currently only reasoned about, the honest limit
that a command scrolling more than a screenful leaves only its tail.

Work items:

1. The recording session wrapper at the carrier seam —
   `text_screen` / `send_keys` / `screenshot` / `change_medium` —
   backend-neutral by construction, so it wraps the seam and never
   QEMU.
2. The record pace flooring the interpretation layer's poll clocks
   (`_POLL_INTERVAL`, `_PROMPT_POLL`, `_ECHO_POLL`, the menu
   settling waits), the pace written into the transcript header
   because a recorded run polls harder than an unrecorded one.
3. The writer: row deltas, a keyframe after every sampling gap, a
   per-entry digest of the reconstructed screen, wall and elapsed
   timestamps, absorbed sample counts, and the carrier calls the run
   made.
4. The secret rule — recording stops for the rest of the run once a
   bound secret reaches the guest, and the transcript says so.
5. `--record <path>` and `run_script(record=)`, landing on S1 and S2
   in the same change with `docs/spec/cli.md`, `docs/spec/api.md`
   and the command manifest.
6. The reconstruction session at the same seam: rebuild frames from
   the transcript, verify every digest, and fail loudly naming what
   was asked where the transcript does not cover a request.
7. The round-trip test, against `tests/fake_backend.py` — no unit
   test launches a real backend, so capturing real guests is F43's
   under the opt-in integration run.

## F43 — The interpretation-layer corpus

> **Pledged 2026-08-01** (owner), cut from F13 with F42, that
> number retiring with the split (D42). Demanded by **P22** and
> **P24** — a surface that genuinely cannot be tested names the gap
> rather than being quietly exempted, and this closes the largest
> one. Needs **F42** delivered first. Design:
> [design/screen-transcripts.md](design/screen-transcripts.md).

The third conformance corpus, and the one whose fixtures nobody can
author: the blueprint and script corpora are written, and this one
is only ever captured.

Work items:

1. The harness: run the interpretation layer against a `.rlqt`
   fixture — the fixture directory, the loader, and the assertion
   vocabulary.
2. The first captures, taken under the opt-in integration run
   against real QEMU: the FreeDOS install path and the verify
   script.
3. The pathological captures — the boots where prompt detection or
   command-echo scanning misbehaves, each becoming a regression
   fixture.
4. The corpus README, as the blueprint and script corpora each
   carry: where its findings live.
5. The suite discipline: fixtures reconstruct with no QEMU present,
   so they run in the **default** suite, and a failing capture is a
   defect to fix rather than a skip to tolerate.
