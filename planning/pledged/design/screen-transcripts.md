<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Screen transcripts: capture and replay

> **Status:** design for pledged **F42** and **F43**
> ([../FEATURES.md](../FEATURES.md)). Demanded by **P22** — the
> suite is the gate, and the interpretation layer has no honest way
> to be tested without captured input. Shaped by **P11** (a limit
> names itself), **P6** (the CLI and the API land together) and
> **P12** (Reliquary writes only where it was told to). **Nothing
> here is normative**: the transcript format is deliberately not an
> application surface (D98), so it carries no `docs/spec/` entry and
> no stability guarantee.

## Why fabricated screens cannot do this job

The interpretation layer is heuristic over real-world text —
`_PROMPT_RE` deciding what a DOS prompt looks like,
`_command_output()` finding the echo by scanning back for a row
ending with the command and containing `>`, `screen_text()`,
`wait_text`, `cursor_menu_select`, and the clocks in
`script_timing`. That class of logic cannot be credibly unit tested
on fabricated input, because the fabrication encodes the same
assumptions the heuristic does: you write the screen you believe DOS
draws, and the parser passes on your own belief.

Only captured screens carry the weird spacing, the stray CR, the
half-drawn menu, the prompt that arrived mid-scroll.

## The capture sits at the carrier seam

`script_runner._read()` reads through `console.screen_text()` — text
rows only, attributes already discarded — and it never sees the
polls `cursor_menu_select` takes inside its own loop. Capturing
there would record what the layer under test had already decided.

So the recorder wraps the **carrier**: the session contract an
adapter provides — `text_screen()`, `send_keys()`, `screenshot()`,
`change_medium()` — where a frame is still `(rows, attributes)` and
every read any layer above makes passes through.

Two consequences, and both are the point:

- **Replay stands a fake session at that same seam**, and the whole
  interpretation layer — `control_display`, `interaction_agentless`,
  the runner's dispatch — runs unmodified above it. That is what
  makes the fixtures worth having.
- **The recorder is backend-neutral by construction.** It wraps the
  seam, not QEMU, so a capture taken against another adapter replays
  through the same reader.

## The pace, and the single QMP client

QEMU's QMP server admits one client at a time, which is why no
session is ever held while a statement list runs (AGENTS.md, "Script
dispatch"). An independent sampler thread would contend for the only
slot, so the recorder cannot have its own clock in the obvious way.

And the run's own clocks are coarse: `_POLL_INTERVAL` is 2.0s in
dispatch, `_PROMPT_POLL` 2.0s while waiting on a prompt, `_ECHO_POLL`
0.1s just after a command, and the menu machinery settles at
0.1–0.15s. Recording only what the run already reads leaves
two-second holes through most of a boot.

So **the record pace drives the interpretation layer's poll clocks**:
under `--record`, those intervals are floored by the record pace,
every poll is both a functional read and a recorded frame, and one
client is enough.

Three things that obliges:

- **The pace is a target, never a promise.** No sample is taken while
  a statement list executes, and that invariant is load-bearing — a
  screen that appeared and vanished inside a handler never happened,
  and recording must not change that. The gaps are real; the
  timestamps are what make them visible.
- **The observer effect is named.** A recorded run polls harder than
  an unrecorded one. Denser polling is strictly more information,
  never less, but it is a different run — so the transcript header
  states the pace it was taken at, and a fixture is never mistaken
  for production timing.
- **The pace is recorded, not assumed.** A reader gets it from the
  file rather than from a constant that has since moved.

## What a frame is

The seam's own text-screen contract: character rows plus opaque,
equality-comparable per-cell attribute tokens. **Identity is the
whole pair.** A cursor menu moves its selection by attribute alone,
so text-only comparison would collapse exactly the frames the menu
machinery exists to read.

Consecutive identical frames collapse. What survives each entry:

- **Row deltas** — the rows that changed. A DOS screen typically
  changes one or two of twenty-five.
- **A keyframe after every sampling gap.** Where sampling stopped —
  a statement list running, keys going out — continuity is not
  something the transcript can claim anyway, so the next entry is a
  full frame. That boundary is semantic rather than an arbitrary
  every-N rule.
- **A digest of the reconstructed screen**, a few bytes an entry.
  Playback rebuilds and checks it. A reconstruction bug or a
  hand-edited fixture then fails loudly instead of yielding a screen
  that never existed — the fails-loudly rule below, applied to the
  format itself.
- **Both timestamps** — wall time and elapsed, matching `events.py`'s
  envelope. Elapsed is what replay uses; wall time is provenance.
- **The absorbed sample count.** "This screen held two seconds across
  forty samples" and "this screen held two seconds with nobody
  looking" are different facts, and only the first says the guest was
  quiet (P11).

WHY DELTAS, AND NOT FOR SIZE. Gzip beats a hand-rolled encoding on
frames this repetitive, and a ten-minute install is a few hundred
kilobytes either way. **The argument is reviewability.** These files
are committed, read by whoever is debugging prompt detection, and
re-recorded later. A delta transcript narrates — row 12 became
`C:\>` at 4.35s — and a re-recording produces a diff a reviewer can
read; a whole-frame transcript makes every re-record touch every
line. Cell-granular deltas are refused on the other side of the same
argument: the further gain is marginal and the reconstruction becomes
code that itself needs tests, which is a fixture format you have to
debug.

## The transcript records both directions

Screens alone would test the reader and nothing else. The capture
also records the carrier calls the run made — key combinations sent,
screenshots taken, media changed — each timestamped on the same
clock.

That is what makes the file a transcript rather than a screen dump,
and it is what makes the fails-loudly rule checkable: on
replay, **a request the transcript does not cover is an error**
naming what was asked and where. Never an improvised answer, never
an empty one (P11). Improvising is how a caller ends up reporting a
pass against a transcript that never covered the case.

## Secrets stop the recording

A raw screen carries a typed password in plain text, and the event
stream's redaction does not reach it: redaction works over strings
the stream carries, and a frame is a grid.

The rule is the screenshot precedent taken verbatim — **once a bound
secret reaches the guest, recording stops for the rest of the run**,
and the transcript records that it stopped and why. No partial
redaction and no search for the secret on screen: a value echoed into
a field, wrapped across a row, or masked by the guest is not reliably
findable, and a redactor that usually works is worse than one that
refuses. A run that binds a secret yields a short transcript that
says so.

## Where a transcript is written

At the path given and nowhere else. No default location, nothing in
the machine directory, nothing under `cache/`, and no transcript at
all when the flag is absent — which keeps P12 clean and keeps D36's
"a run stores nothing" true of every run except the one a maintainer
deliberately asked to record (D98).

## What the format's standing is

**Not an application surface** (D98): no `docs/spec/` norm, no
stability guarantee, no compatibility obligation, and a change to it
is housekeeping. The extension is `.rlqt`, matching the existing
family (`.rlqb`, `.rlqs`, `.rlql`) — no reservation beyond that. The
one proposal that would have promoted this format to a surface,
F44, was rejected outright (D100), so nothing about this format is
shaped to anticipate a future public one.

What *is* surface is the invocation — `--record <path>` on
`run-script` and `run_script(record=)` on the session, landing
together on S1 and S2 (P6).

## What is deliberately not here

A public backend running whole flows off a transcript was proposed
as **F44** and rejected (D100): the concrete value it offered —
cheap reruns of one unchanging script — is F43's job already, and
the demand it borrowed for anything broader was F12's, which does
not answer to a recording either. This format stays what it always
was: a maintainer's own debugging and corpus tool, never something
a caller drives directly.
