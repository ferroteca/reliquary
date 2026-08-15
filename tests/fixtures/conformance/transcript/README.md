<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# The transcript conformance corpus

The corpus for the **interpretation layer** — `control_display`,
`interaction_agentless`, and the runner's dispatch and clocks. Design:
[planning/design/screen-transcripts.md](../../../../planning/design/screen-transcripts.md).
Harness: [test_transcript_corpus.py](../../../test_transcript_corpus.py),
over [tests/replay.py](../../../replay.py).

**The third corpus, and the one whose fixtures nobody can author.**
The blueprint and script corpora are written: a fixture states a
document and what must happen to it. This layer is heuristic over
real-world text — what a DOS prompt looks like, where a command's echo
ends, whether a screen has stopped moving — and a fabricated screen
encodes the same belief the heuristic does, so the parser passes on
your own assumption. Only a captured screen carries the weird spacing,
the stray CR, the half-drawn menu, the prompt that arrived mid-scroll.

## The fixtures

**Two kinds, because the layer has two front doors.** A `.rlqs` run
drives the phase graph, the cursor menus and the stability gates; a
`exec` command drives prompt detection and command-echo scanning,
which a script run never touches. A fixture declares which it is by
carrying a `script` or a `command` in its header.

### The working paths

| fixture | what it is a capture of |
|---|---|
| `freedos-install.rlqt` | the codex `freedos-install.rlqs` — LiveCD boot, partitioning, format, package selection, reboot, shutdown, and every cursor menu the install has |
| `freedos-verify.rlqt` | the codex `freedos-verify.rlqs` — boot the installed disk, read a prompt, power off |
| `freedos-ready.rlqt` | the codex `freedos-ready.rlqs` — the handoff, and the one capture that ends with the machine still **running**: no `vm-gone`, and a `set` reaching the host |

### The pathological screens

Each is a screen a real FreeDOS draws for an ordinary command —
nothing here is malformed or staged. What the layer *makes* of each
is what the fixture pins, and three of the four are wrong today.

| fixture | the screen | what the layer does |
|---|---|---|
| `freedos-exec-wrapped-echo.rlqt` | an 85-column command, whose echo wraps across two rows | **refuses** it — `screen.no-echo` on a command that ran fine |
| `freedos-exec-echo-lookalike.rlqt` | a file whose last line reads `C:\>TYPE C:\ECHOLIKE.TXT`, printed by that very command | **returns nothing** — no error, three lines on screen, an empty result |
| `freedos-exec-scrolling-output.rlqt` | `DIR /S` over a thousand files: pages of scroll, then a prompt | correct — the visible tail, which is the documented limit |
| `freedos-exec-custom-prompt.rlqt` | a guest whose prompt is `[C:\]>` after `PROMPT [$P]$G` | **never completes** — `screen.no-match` at the timeout |

All seven are taken against real QEMU on the opt-in integration tier and
**reconstruct with no hypervisor present**, so they run in the default
suite, in about a second between them: the layer's waiting is real
time and a replay has none of it. A failing capture is a defect to
fix, not a skip to tolerate.

## What a fixture asserts

**That it is replayable.** `ReplaySession` stands at the carrier seam
the capture was taken at, so the shipped interpretation layer runs
unmodified above it, and a call the transcript does not cover is an
error naming what was asked (P11). A regression in prompt detection or
echo scanning changes what the layer asks the carrier for, and the
transcript is the record of what it asked last time. Nothing is
restated in a sidecar that could drift from the capture.

Two claims sit beside that, because "the replay finished" is weaker
than it looks:

- **Every recorded call was made.** A run that ends early replays
  without error — it simply stops asking, and an unread transcript is
  silent. `remaining_calls()` is the difference, and the harness
  asserts it is zero.
- **The script has not moved since.** The header carries the script's
  name and the sha256 of its text; a capture taken against an edited
  script is named as stale rather than reported as a divergence
  eleven minutes into a replay.
- **The run reached the conclusion it reached.** Two runs over the
  same screens — one returning the right rows, one returning somebody
  else's — make the same carrier calls, so the file is the same file.
  The capture states its conclusion as a trailer, and the replay is
  held to it: the rows a command returned, the phase a script
  finished in, or the rule id either refused with.

**Which is what lets a capture of a failing run be a fixture.** Three
of the four pathological captures record a refusal or a wrong answer,
and they assert it — so the day one of those gaps closes, its fixture
fails saying so and asks to be re-recorded. A green test over
behaviour nobody believes in is the thing this avoids.

A codex label resolves to the shipped script rather than to a copy —
the codex is the live, tested one — and any other name resolves to a
`.rlqs` beside the fixture, which is how a script written to provoke
one misbehaviour would carry its own.

## Re-recording

Captures are taken by the integration tier and promoted by hand. No
test writes into this directory: the run records into the integration
home, and a maintainer looks at what came out before it becomes an
assertion.

```powershell
$env:RELIQUARY_INTEGRATION_HOME = "C:\Temp\reliquary-integration"
uv run pytest tests/test_freedos_install_integration.py --integration
copy C:\Temp\reliquary-integration\captures\*.rlqt tests\fixtures\conformance\transcript\
```

The tier leaves a machine behind on success, and a `freedos-0` holding
FreeDOS already boots its disk rather than the LiveCD — so
`destroy-machine --machine freedos-0` first, or the install run waits
out its deadline on a welcome screen that never comes.

## One fixture, one node

Every fixture is a collected pytest node named for its file, in each
check that judges it, and the bucket count is pinned in the harness
(`tests/corpus.py`) so a corpus that stops loading is a collection
error rather than a green run over nothing — the D106 defect, which is
the reason all three corpora read through one helper. Adding or
retiring a fixture updates the pin and the table above together.

```powershell
uv run pytest tests/test_transcript_corpus.py -k freedos-verify
```

## What the first captures measured

The corpus paid for itself before it had a fixture in it: **taking the
first real capture found six defects, and every one of them was in the
recorder rather than in the layer under test.** Three were found by the
first attempt and three by this one.

- **The recorder was never installed.** `Machine` is a frozen
  dataclass and the engine assigned the wrapper after construction, so
  every `--record` run died at its first screen read. The flag had
  never worked on a real run: F42's own tests build the recording
  session directly.
- **The delta test was inverted.** A changed row took the keyframe
  branch and deltas fired only on identical rows, so no transcript
  ever carried a row change and every re-recording rewrote every line
   — the reviewability the format was chosen for.
- **A collapsed frame counted one sample.** Repeat reads were dropped
  rather than absorbed, so "this screen held two seconds across forty
  samples" and "it held two seconds with nobody looking" wrote the
  same entry.
- **The `screenshot` verb bypassed the recorder**, building its own
  machine handle. Both codex scripts take a screenshot, so it was
  every capture — and a replay then meets a call the transcript
  cannot answer.
- **The machine going away was not recorded.** Identity is verified
  while a session is being opened, so a guest that powered itself off
  refuses the session *before* the recording wrapper exists, and the
  seam cannot record its own disappearance. Both codex scripts end on
  `wait machine=stopped`, which is answered by exactly that refusal:
  captures without it replayed up to the shutdown and no further.
- **The record pace did nothing.** The poll intervals took the
  *larger* of the production interval and the pace, so a recorded run
  kept its two-second idle poll — the two-second hole through most of
  a boot that the pace exists to close. The first install capture held
  536 samples across five and a half minutes; the fixture holds 2673.

**A capture is a test of the recorder before it is a fixture**, which
is the general form of all six: nothing above the seam could have
found any of them, and no unit test of the recorder did.

## And two the replay found, which are the same lesson

Neither is a recorder defect. Both are about what it takes to put a
run back *exactly*, which is what an assertion of this kind needs.

- **A read that stepped over a recorded call was silent.** The
  reconstruction skipped call entries while looking for the next
  frame, so a run that read once more than the capture did swallowed
  the keypress the capture had made there — and every keystroke after
  that was compared against the wrong one. The mismatch surfaced
  eighteen seconds later, against a screen neither run was looking at.
  It is now an error where it happens
  (`transcript.read-before-call`), and that is what made the second
  one findable at all.
- **A frame's sample *count* cannot reconstruct its cadence.** A
  collapsed frame recorded how many reads it absorbed, and the replay
  spread them evenly across the gap. Even spacing is a guess, and the
  layer's measures are windows over wall-clock: the menu machinery
  read one extra time before its first keypress, chose a different
  key, and the install could not be replayed at all. The format now
  records **when** each absorbed read happened, and with the guess
  removed the whole install replays keystroke for keystroke.

The general form: **the transcript has to carry the moments, not
just the screens.** A guest's screen is only half of what the layer
above sees; the other half is when somebody looked at it.

## And three the pathological captures found in the layer itself

The first five findings were about capturing faithfully. These are
what the faithful captures then showed, and they are **not** in the
recorder — they are what `exec` does with three ordinary screens.

- **A command over 80 columns cannot be run.** Its echo wraps, no row
  *ends* with the command, and `_echo_at` finds nothing; the command
  runs fine on the guest and `exec` refuses to tell you what it said
  (`screen.no-echo`).
- **A line of output that looks like the echo silently wins.** The
  scan runs backwards from the bottom for a row ending with the
  command and carrying a `>`, and a file whose last line is
  `C:\>TYPE C:\ECHOLIKE.TXT` is exactly that row. Everything above it
  — the file's real content — is discarded and `exec` returns an
  **empty** result with no error. This one is a **spec violation**,
  not an unstated limit: `docs/spec/cli.md` promises "the command's
  own output or a failure — never text it cannot attribute", and an
  empty tuple attributed to a command that printed three lines is
  neither.
- **A customized prompt is never recognized.** `_PROMPT_RE` is
  `^[A-Z]:(\\[^>]*)?>$`, so a guest whose `AUTOEXEC.BAT` sets
  `PROMPT [$P]$G` — or `$T$G`, or anything with a suffix — makes
  every `exec` wait out its full timeout. Nothing in the spec says
  which prompts are supported.

None of the three is fixed here, and that is deliberate: a corpus
records what the layer does, and what counts as a DOS prompt (or as
an echo) is a design question with a decision to make, not a test
fixture's to settle. The fixtures pin today's behaviour so that
whoever settles it cannot do so silently.

## What this corpus deliberately does not cover

- **The machine layer.** A live `insert` or `eject` changes the medium
  over the machine layer's own session, not the run's, so it is
  absent from a capture — the fake lifecycle in `tests/replay.py`
  answers it instead. What the corpus covers is what the *guest
  screen* drove.
- **Timing as it happened.** A replay runs on the capture's own
  timeline rather than a clock of its own: every moment the layer
  measures against is the one the recording holds, and the waiting
  between them costs nothing. A capture is minutes long because a
  guest is slow, not because the layer is.
- **`--check`.** The ERRORLEVEL probe is a second command at the
  prompt, read back through the same echo discipline, so a capture of
  it would pin the probe rather than the reading. Nothing here runs
  one.
- **The other backend.** These are QEMU captures, which scrape text
  memory. VirtualBox reaches the same seam through the fixed-font
  recognizer, and a capture taken there would exercise that path
  instead; the format is backend-neutral by construction, so it needs
  a run rather than a change.
