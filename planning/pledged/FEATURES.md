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

## F42 — The screen transcript: capture and replay

> **Pledged 2026-08-01** (owner), cut from F13 with F43 and
> proposed F44, that number retiring with the split (D42). Demanded
> by **P22** — the suite is the gate, and this is what would make
> that gate real for the interpretation layer, which today has no
> honest way to be tested at all. Shaped by **P11**, **P6** and
> **P12**. Design:
> [design/screen-transcripts.md](design/screen-transcripts.md);
> the D36 squaring and the format's standing are **D98**.

**Capture and replay land together**, because a transcript format
with no reader is an unverified format: nothing would prove a
capture is replayable, and the format would be wrong in ways only
F43's fixtures would eventually discover.

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
6. The replay session at the same seam: reconstruct, verify every
   digest, and fail loudly naming what was asked where the
   transcript does not cover a request.
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
5. The suite discipline: fixtures replay with no QEMU present, so
   they run in the **default** suite, and a failing capture is a
   defect to fix rather than a skip to tolerate.

## F44 — The `replay` backend

> **Pledged 2026-08-02** (owner), the deferred half of F13 as
> entered 2026-08-01 (that number retired when the rest pledged as
> **F42** and **F43**, D42). It sat proposed on its own citing no
> demand — sharing **F12**'s gap, the nearest case being about
> driving a *real* machine — so this pledge drafts **U23** in
> [proposed/USE-CASES.md](../proposed/USE-CASES.md), "test my own
> Reliquary integration with no hypervisor present," which also
> closes F12's identical gap without pledging F12 itself.
> Shaped by **P11** and **P6**, and by **D98**, which named this
> feature outright as the trigger that promotes the `.rlqt`
> transcript from housekeeping to application surface — the
> vetting rule and a `docs/spec/` norm arrive with it, never after.
> Needs **F42** delivered first.

**The pairing is the whole of it**: `--record` teaches the format,
`--backend replay` spends it —

    rlq run-script install --record install.rlqt   # once, real QEMU
    rlq run-script install --backend replay         # thereafter, free

— and what this feature adds beyond F42's own replay session is
full lifecycle fidelity over a format callers can depend on, which
is exactly the thing D98 refused to call a surface until a caller
actually did.

Work items:

1. The `replay` backend value in the existing `backend` enum and
   adapter registry — new values in existing plumbing, per F12's
   pattern — answering the whole machine lifecycle (create, start,
   exec, stop, destroy) from a loaded `.rlqt` transcript rather
   than a real backend session.
2. The `docs/spec/` norm the format gains on promotion (D98): what
   `.rlqt` guarantees, what changing it costs, and the vetting rule
   applied to it from here on — nothing renamed, the extension
   stays what F42 claimed.
3. The unmatched-request rule generalized beyond F42's own replay
   session to every caller of this backend: no recorded response
   for a command is a loud failure naming the command and the gap,
   never an improvised or empty answer (P11).
4. `--backend replay` and its API twin landing together with the
   command manifest (P6).
5. Full-lifecycle fidelity tests beyond F43's scripted-corpus
   scope: a transcript recorded once drives create/start/exec/stop
   through the replay backend with results indistinguishable from
   the real run that produced it.

## F45 — The command wait settles before it reads

> **Pledged 2026-08-02** (owner). Serves **U9**, **U12** and
> **U14**; demanded by **P11** — a prompt matched on a half-drawn
> screen yields confident wrong data. **Needs F47** (the stability
> primitive, cut from proposed F46 in the same pledge round)
> delivered first: rather than build its own hold-for-two-reads
> mechanism, this feature adopts F47's primitive directly, which is
> the order F45 and F46 each argued for themselves — taking F46's
> half first buys no throwaway implementation for this one to
> retire later.

`control_display._settled_screen()` already waits for a menu screen
to change and then holds for two further reads before acting, on
the stated ground that returning at the first difference hands
back a half-drawn screen. `interaction_agentless._run()` never got
the rule: first frame whose bottom row matches the prompt wins,
with no second look. One project, one guest, one hazard, two
answers — this closes the gap on the command path once F47 gives
it a shared primitive to close it with.

**Scope is bounded deliberately**: this reaches the *unauthored*
command-completion test inside `exec` alone. `wait_text`'s authored
path is **F48**'s (the `stability=` language surface), not this
one's — an author who wants the guard on their own `wait` already
has the tool once F48 lands; this feature is what closes the gap
nobody authored.

Work items:

1. Wire `interaction_agentless._run()`'s command-completion test
   through F47's primitive: a candidate prompt match is accepted
   only once the sampled frame clears the primitive's default
   threshold, never on the first frame that merely looks right.
2. No new script vocabulary and no header changes — internal only,
   which is what keeps this separable from F48.
3. The poll ramp is untouched: the fast 0.1s echo-catching phase
   and its reasoning stand exactly as they are; only the slow
   phase's completion test gains the guard.
4. The failure diagnostic distinguishes "never matched" from
   "matched only on frames the guard skipped," reusing F47's
   animated-region naming so a baffling expiry names its own cause.
5. The **P8** / [SURFACES.md](../SURFACES.md) argument, made
   explicit rather than assumed: `docs/spec/cli.md`'s "completion
   means this command finished, not that a prompt is visible" is
   strengthened by this change, not amended, but the timing it
   moves is observable, so the triage runs properly.

## F47 — The screen-stability primitive

> **Pledged 2026-08-02** (owner), cut from proposed **F46** in this
> round (D42) — F46's own account of itself was many sprints of
> work under one number: a comparison primitive, an authored
> language surface, and a retirement of the menu machinery's own
> copies, each a feature's worth on its own. This piece is the
> foundation the other two need before either can be built, so it
> is cut first and takes the ledger's next mark; **F48** (the
> `stability=` language surface) and **F49** (the menu-machinery
> retirement) are its siblings, cut in the same edit. Serves **U9**,
> **U12** and **U14** through **P11**, the same demand F46 carried.

**The measure, not yet a word anywhere.** A screen is stable when
its content has stopped changing — but magnitude alone cannot tell
a spinner that repaints forever from a line of content arriving
once, and sample-adjacency alone makes stability a property of the
poll rate rather than of the guest: the same screen reads stable at
a dense cadence and unstable at a sparse one. Two corrections, both
load-bearing:

1. **Cadence-independence.** Stability is defined over a *window of
   wall-clock time* (no more than 1% of cells changed in the last
   200ms), never over consecutive samples — otherwise a denser
   poller (F42's own recording pace, notably) reaches a different
   verdict than a sparser one on the identical guest, which would
   let a recorded run and a production run take different paths
   through the same script.
2. **Animation is recurrence, not magnitude.** A cell is animated if
   it changed in at least M of the last T milliseconds — cadence-
   independent for the same reason — and stability is computed over
   the non-animated cells only. A single advancing cursor or a
   marching border then reads as "100% stable outside its own
   animated region," where raw magnitude would never settle; a cell
   that changes once, wherever it sits, is content and is never
   masked.

**Cells, not rows** — row granularity cannot separate a blinking
cursor from an arriving line of text, both being "one row changed."
**Identity is the pair** (text and attribute together), because a
cursor-menu selection moves by attribute alone and a text-only
comparison would score that as perfectly stable.

**The default falls out of the geometry.** A text screen is
80 × 25 = 2000 cells; one row is 80 of them, 4% of the screen. Any
threshold looser than 0.96 therefore calls a screen stable while a
line is still being drawn into it — precisely the event the primitive
exists to catch. Furniture costs an order of magnitude less (a
cursor 0.05%, a clock 0.4%, a counter 0.2%), so the default sits in
the gap above furniture and below content: **0.99**, recommended and
adopted here — 0.98 is the defensible fallback if a real capture
later shows heavier furniture; 0.95 is refused outright on the
arithmetic, admitting a full line of text and more.

**The bail-out carries over from `_menu_baseline`**: when most of the
screen qualifies as animated, mask nothing and compare raw, exactly
as the code this primitive will let F49 retire already does.

Work items:

1. The frame-comparison core: cell-level, identity-paired
   (text+attribute), window-based over wall-clock time, with the
   0.99 default and its geometry rationale.
2. The animation/recurrence mask: a cell qualifies as animated by
   recurrence within a wall-clock window, never by sample count;
   stability is computed over the unmasked remainder; majority-churn
   bails out to a raw, unmasked comparison.
3. A query surface returning enough to build a diagnostic from it: a
   pass/fail against a given threshold, and — on failure — the
   animated region, so a caller (F45, F48, F49) can name what it
   skipped rather than merely report a number.
4. Tests against captured real-guest frames: the furniture cases
   named above (cursor, clock, counter, marching border) read
   stable; a line of text arriving reads unstable; a cursor-menu
   selection move reads unstable by attribute alone.
5. No consumer wiring here — F45, F48 and F49 each adopt this
   primitive in their own work, which is what keeps this piece to
   one sprint.

## F48 — `stability=`, the compare guard

> **Pledged 2026-08-02** (owner), cut from proposed **F46** with
> **F47** and **F49** (D42). Serves **U9**, **U12** and **U14**
> through **P11**. Needs **F47** delivered first — this feature is
> the authored language surface over that primitive, nothing more.
> Sits opposite `pacing` in the language: `pacing` guards the actor
> and lives on the four input verbs, `stability` guards the compare
> and lives on observations — the mirror the language had half-built
> already.

**The spelling is `stability=`**, not a second sense of `stable=`.
`stable=2s` is in-force language guarding whether a *matched
condition* is durable across an episode; `stability` guards whether
the *frame itself* is trustworthy to compare against at all — a
condition can hold perfectly on a screen that is still painting
around it, which is exactly the case `stable=` cannot catch and this
does. Neither retires the other: `stability` absorbs most real uses
of `stable=2s` in practice, but the two answer different questions
and G6's adjacency risk is the reason to keep them apart rather than
collapse them.

**Placement mirrors `pacing`'s, on the opposite statement kind**:
`stability` sits only on observations — a branching `wait` may carry
it directly (where `stable` is refused, "put it on the `on`," an
unstable frame evaluating none of the handlers), and the container
ladder runs statement > branching wait > phase > header > built-in
**0.99** — F47's default, written nowhere unless an author overrides
it, exactly as `timeout` (60s) and `pacing` (0.1s) already work.

**The price is bounded and stated**: establishing quiescence costs at
least one poll interval before a guarded observation's condition is
first evaluated at all — cheap in the common case (an idle prompt
agrees on the second sample) and charged per observation, never per
statement. Migration is one-directional: a script that raised
`pacing` to cover paint keeps working, slower and still correct.

**The timeout diagnostic must say which clock lost.** A wait can now
expire two ways that look identical from outside — the condition
never matched, or it matched only on frames the guard skipped — and
F47's animated-region report is what makes the second sayable:
*"stable outside a 76-cell animated region; condition never matched
there"* rather than a bare, unhelpful ratio.

Work items:

1. Grammar: `stability` fits the `watch-mod` shape, a distinct unit
   from `stable`'s duration.
2. Placement law: observations only; container rungs statement,
   branching wait, phase, header; the built-in **0.99** default at
   the foot of the ladder, written nowhere by default.
3. The clock table gains its sixth entry (`docs/spec/script-spec.md`
   scoping and clock tables), naming quiescence beside timeout,
   pacing, stable, and the reactive interval.
4. The timeout/failure diagnostic, built on F47's animated-region
   report, naming which clock expired.
5. **P6** parity: script grammar, CLI, API and the command manifest
   land together; **P8**/[SURFACES.md](../SURFACES.md) argument
   made explicit for the default changing when existing waits fire,
   since a silent behavior change to shipped scripts is exactly what
   the vetting rule exists to weigh.
6. Docs: `script-spec.md`'s worked example
   (`wait "Formatting" stable=2s`) updated to show `stability`'s
   relationship to it, and the G6 adjacency risk recorded as
   considered and accepted.

## F49 — Retire the menu machinery's bespoke copies

> **Pledged 2026-08-02** (owner), cut from proposed **F46** with
> **F47** and **F48** (D42). Serves the same demand as its siblings
> through **P11**, applied here as a correctness argument for the
> menu machinery specifically: `_settled_screen`'s hold-for-two-reads
> and `_menu_baseline`'s learned animation mask are both special
> cases of F47's general measure, tuned by hand against real guests
> rather than derived. Needs **F47** delivered first.

**A trade, not an addition.** `_menu_baseline` needs a learning phase
and a quiet moment before it works at all; an animation that begins
mid-wait is never absorbed into a mask that already closed. F47's
recurrence-over-a-window measure has neither limitation — it accepts
new animation within a few samples wherever it starts. Once F47
exists, keeping the bespoke copies is unearned duplication rather
than a safer bet.

**What survives untouched**: the menu machinery's own questions,
which were never about settling — whether a keypress changed
anything at all (`_settled_screen` returning `None` reads as a dead
key) and which row the highlight moved to. Those are classification,
not stability, and stay exactly where they are.

**The risk is named rather than waved through**: this is
behavior-preserving surgery on the most delicate interpretation code
in the project, tuned against real guests over `wait=2.5` and
`hold=2` constants that F47's threshold does not obviously reproduce
by construction. Menu regression is the acceptance criterion for the
cut, not a side check performed after it lands.

Work items:

1. `_settled_screen` becomes a caller of F47's primitive in place of
   its own hold-for-two-reads loop, preserving its `None`-on-no-change
   contract.
2. `_menu_baseline` becomes a caller of F47's primitive in place of
   its own learned mask and majority-churn bail-out, preserving its
   bail-out behavior exactly.
3. Regression run against real guests on the existing menu suite and
   scripts, with any divergence from today's `wait=2.5`/`hold=2`
   tuned behavior treated as a defect in the cut, not a tuning
   invitation.
4. The bespoke constants and learning-phase code deleted once the
   primitive-backed replacement passes regression — no dual
   implementation kept "to be safe" (no backward compatibility
   before 1.0).
