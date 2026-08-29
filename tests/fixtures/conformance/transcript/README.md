<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# The transcript conformance corpus

The corpus for the **interpretation layer** — `control_display`,
`interaction_agentless`, and the runner's dispatch and clocks. Design:
[planning/design/screen-transcripts.md](../../../../planning/design/screen-transcripts.md).
Harness: [test_transcript_corpus.py](../../../test_transcript_corpus.py),
built on [tests/replay.py](../../../replay.py).

**This is the third corpus, and the one whose fixtures nobody can just
write by hand.** The blueprint and script corpora are authored: a
fixture states a document, and what should happen when it's processed.
This layer is different — it's heuristics applied to real-world text:
what a DOS prompt looks like, where a command's echo ends, whether a
screen has stopped changing. A hand-written fake screen would just
encode the same assumptions the heuristic makes, so a fixture built
that way would only ever confirm the code agrees with itself. Only a
screen actually captured from a real machine carries the odd spacing,
the stray carriage return, the half-drawn menu, the prompt that arrived
mid-scroll — the things a fixture needs to actually test the heuristic
against.

## The fixtures

**There are two kinds of fixture, because the layer has two entry
points.** A `.rlqs` run drives the phase graph, the cursor menus, and
the stability gates. An `exec` command drives prompt detection and
command-echo scanning, which a script run never touches. A fixture
declares which kind it is by carrying a `script` or a `command` field
in its header.

### The working paths

| fixture | what it is a capture of |
|---|---|
| `freedos-install.rlqt` | the codex `freedos-install.rlqs` — LiveCD boot, partitioning, format, package selection, reboot, shutdown, and every cursor menu the install has |
| `freedos-verify.rlqt` | the codex `freedos-verify.rlqs` — boot the installed disk, read a prompt, power off |
| `freedos-ready.rlqt` | the codex `freedos-ready.rlqs` — the handoff, and the one capture that ends with the machine still **running**: no `vm-gone`, and a `set` reaching the host |

### The pathological screens

Each of these is a screen a real FreeDOS draws for an ordinary command
— nothing here is malformed or staged. What the layer *makes* of each
screen is what the fixture pins down. None of the five is wrong today:
three of them were wrong when they were first captured, and each one
was closed against its own capture (issues #7, #8, #9; D111, D112).
Two of the five now pin a documented limit rather than a bug.

| fixture | the screen | what the layer does |
|---|---|---|
| `freedos-exec-wrapped-echo.rlqt` | an 85-column command, whose echo wraps across two rows | correct — the echo is found across the rows it spans, and the command's output below it comes back |
| `freedos-exec-echo-lookalike.rlqt` | a file whose last line reads `C:\>TYPE C:\ECHOLIKE.TXT`, printed by that very command | correct — the echo is the row the command was typed at, and the lookalike below it is the file's own last line, returned with the other two |
| `freedos-exec-scrolling-output.rlqt` | `DIR /S` over a thousand files: pages of scroll, then a prompt | correct — the visible tail comes back, which is the documented limit |
| `freedos-exec-custom-prompt.rlqt` | `PROMPT [$P]$G` itself, changing the prompt from `C:\>` to `[C:\]>` | **expires** — `screen.no-match`, the documented limit: neither the standard prompt shape nor the prompt the guest was actually at comes back, and the expiry error says so |
| `freedos-exec-at-custom-prompt.rlqt` | `VER` at that `[C:\]>` prompt | correct — the prompt the guest was already at counts as evidence the command finished |

All eight fixtures are captured against real QEMU on the opt-in
integration tier, but **replay them with no hypervisor present at
all**, so they run in the default suite, taking about a second total:
the layer's waiting is real time in the capture, and replaying it costs
none of that time. A failing capture is a bug to fix, not a flaky test
to tolerate.

## What a fixture asserts

**That it can be replayed.** `ReplaySession` stands in for the real
carrier at the same seam the capture was taken from, so the shipped
interpretation layer runs completely unmodified above it. A call the
transcript doesn't cover comes back as an error naming what was asked
for (P11). A regression in prompt detection or echo scanning changes
what the layer asks the carrier for, and the transcript is a record of
exactly what it asked for last time. Nothing here is duplicated in a
side file that could drift out of sync with the capture.

Two more claims sit alongside "the replay finished," because that
claim alone is weaker than it sounds:

- **Every recorded call actually got made.** A run that ends early
  still replays without raising any error — it just stops asking
  questions, and a transcript that goes unread produces no error
  either. `remaining_calls()` is what catches this: the harness checks
  that it comes back zero.
- **The script hasn't changed since the capture was taken.** The
  transcript header carries the script's name and the sha256 of its
  text, so a capture taken against an older version of a script is
  flagged as stale, rather than reported as some mysterious divergence
  eleven minutes into the replay.
- **The run reached the same conclusion it originally reached.** Two
  runs over the same screens — one returning the right rows, one
  returning the wrong ones — would make identical calls to the carrier,
  so on their own the calls can't tell those two runs apart. The
  capture also records its conclusion, in a trailer: the rows a command
  returned, the phase a script finished in, or the rule id it was
  refused with. The replay is checked against that trailer too.

**That's what makes it possible for the capture of a failing run to be
a fixture at all.** Three of the pathological captures recorded a
refusal or a wrong answer, and asserted it — and each one did its job:
the day the underlying bug was fixed, the fixture failed, said so, and
was re-recorded. The custom-prompt capture still records a refusal —
now a documented limit rather than a bug — and still asserts it. The
whole point is to avoid a green test that no longer reflects real
behavior.

A codex label in a fixture's header resolves to the actual shipped
script, not to a copy of it — the codex script is the live, tested one.
Any other name resolves to a `.rlqs` file kept beside the fixture,
which is how a script written specifically to provoke one kind of
misbehavior gets to carry its own copy.

## Re-recording

Captures are taken by the integration tier and then promoted by hand.
No test writes into this directory automatically: a run records into
the integration home directory, and a maintainer looks over what came
out before it becomes an actual assertion.

```powershell
$env:RELIQUARY_INTEGRATION_HOME = "C:\Temp\reliquary-integration"
uv run pytest tests/test_freedos_install_integration.py --integration
copy C:\Temp\reliquary-integration\captures\*.rlqt tests\fixtures\conformance\transcript\
```

The integration tier leaves a machine running behind after a successful
run, and a `freedos-0` machine that already has FreeDOS installed will
boot straight to its disk rather than the LiveCD — so run
`destroy-machine --machine freedos-0` first, or the install run will
sit waiting out its deadline on a welcome screen that never appears.

**The lookalike fixture is staged by the guest itself**, using `COPY
CON` typed at the prompt. Reliquary never places a file on a machine's
drives on its own (D108), and DOS's own redirection can't produce the
`>` character that fixture's third line needs — no DOS shell has an
escape for it — so the guest has to write that file itself. That's why
the file gets planted after the readiness script hands over a running
machine, rather than while the machine is still powered off.

## One fixture, one node

Every fixture is its own collected pytest node, named after its file,
in every check that runs against it, and the bucket count is pinned in
the harness (`tests/corpus.py`) so a corpus that stops loading fixtures
fails with a collection error instead of quietly passing with nothing
to check — the same D106 issue described above, and the reason all
three corpora share one helper. When you add or retire a fixture,
update both the pin and the table above.

```powershell
uv run pytest tests/test_transcript_corpus.py -k freedos-verify
```

## What the first captures measured

This corpus paid for itself before it had a single fixture in it:
**taking the first real capture turned up six bugs, and every one of
them was in the recorder, not in the layer the corpus was meant to
test.** Three were found on the first attempt, and three more on the
next one.

- **The recorder had never actually been wired in.** `Machine` is a
  frozen dataclass, and the code was assigning the recording wrapper
  *after* construction, so every `--record` run died on its first
  screen read. The `--record` flag had never worked on a real run: F42's
  own tests build the recording session directly, bypassing the path
  that was broken.
- **The delta-encoding test was backwards.** A row that had changed was
  taking the keyframe branch, and deltas only fired for rows that
  hadn't changed — so no transcript ever actually recorded a row
  change, and every re-recording rewrote every single line. That
  defeated the whole reason the format used deltas: to make diffs
  reviewable.
- **A collapsed frame counted as one sample, no matter how long it
  lasted.** Repeated identical reads were being dropped instead of
  merged with a duration, so "this screen held for two seconds across
  forty samples" and "it held for two seconds with only one sample
  taken" produced the exact same recorded entry.
- **The `screenshot` verb skipped the recorder entirely**, building its
  own separate machine handle. Both codex scripts take a screenshot at
  some point, so this affected every single capture — and a replay
  would then hit a call the transcript had no record of.
- **A machine going away wasn't being recorded.** The machine's identity
  is checked while a session is being opened, so a guest that had
  powered itself off would cause the session to refuse *before* the
  recording wrapper even existed — so the wrapper could never record its
  own machine disappearing. Both codex scripts end on
  `wait machine=stopped`, which relies on exactly that refusal to work.
  Captures taken before this was fixed replayed right up to the
  shutdown and then stopped.
- **The recording pace setting did nothing.** The poll-interval code
  was taking the *larger* of the production interval and the recording
  pace, so a recorded run kept its normal two-second idle poll — the
  exact two-second gap through most of the boot that the pace setting
  exists to close. The first install capture, made before this was
  fixed, held 536 samples across five and a half minutes; the current
  fixture holds 2,673.

**A capture is a test of the recorder before it's a fixture of
anything else** — that's the pattern behind all six bugs above. Nothing
above the recording seam could have caught any of them, and no unit
test of the recorder had caught them either.

## And two more the replay found, which are really the same lesson

Neither of these is a recorder bug. Both are about what it actually
takes to put a run back together *exactly* as it happened, which is
what this kind of assertion needs.

- **A read that skipped past a recorded call failed silently.** The
  code reconstructing a run would skip over call entries while looking
  for the next frame, so a run that read the screen one extra time
  compared to the capture would silently consume the keypress the
  capture had recorded there — and every keystroke after that point got
  compared against the wrong recorded value. The mismatch didn't show
  up until eighteen seconds later, against a screen neither run was
  even looking at. This is now an error raised at the point it
  happens (`transcript.read-before-call`), and that's what made the
  next bug (below) findable at all.
- **A frame's sample *count* alone can't reconstruct its timing.** A
  collapsed frame recorded how many reads it had absorbed, and replay
  spread those reads evenly across the time gap as a guess. But even
  spacing is only a guess, and the layer's own timing measurements are
  based on wall-clock windows: in one case, the cursor-menu code read
  the screen one extra time before its first keypress, chose a
  different key than it originally had, and the whole install couldn't
  be replayed at all. The format now records **when** each absorbed
  read actually happened, and once that guess was removed, the entire
  install replays keystroke for keystroke.

The general lesson: **the transcript has to record the moments, not
just the screens.** A guest's screen is only half of what the layer
above it sees; the other half is when someone actually looked at it.

## And three more the pathological captures found in the layer itself

The first five bugs above were about capturing faithfully. These three
are what the faithful captures then revealed, and they are **not**
recorder bugs — they're about what `exec` itself does with three very
ordinary screens.

- **A command longer than 80 columns couldn't be run at all.** Its echo
  wrapped across two rows, so no single row *ended* with the full
  command, and `_echo_at` found nothing. The command ran fine on the
  guest, but `exec` had no way to tell the caller what it had printed
  (`screen.no-echo`). **Closed** (issue #8): the scanner now
  reconstructs the line the way the guest actually wrapped it, working
  from the screen width taken off the attribute rows, and the fixture
  was re-recorded against the fixed layer — the capture of the original
  bug did exactly the job it was kept around for.
- **A line of output that happens to look like the echo could silently
  win.** The scanner searches backward from the bottom of the screen for
  a row that ends with the command and contains a `>`, and a file whose
  last line is `C:\>TYPE C:\ECHOLIKE.TXT` matches that exactly.
  Everything above it — the file's actual content — was being thrown
  away, and `exec` returned an **empty** result with no error at all.
  This one wasn't just an undocumented limit, it was a **violation of
  the spec**: `docs/spec/cli.md` promises "the command's own output or
  a failure — never text it cannot attribute," and an empty result
  attributed to a command that had printed three lines is neither of
  those. **Closed** (issue #7; D111): the echo is now identified by its
  *position* — the row the command was typed at — with everything that
  was above the prompt still kept above it. A row that merely happens
  to spell the same text as the command is treated as the command's
  own output. There's still one screen this rule genuinely can't tell
  apart from the real echo, and that limit is now documented rather
  than hidden: output longer than a full screen, whose *first visible
  row* happens to be a lookalike, with nothing left above it to prove
  otherwise.
- **A customized prompt was never recognized.** `_PROMPT_RE` is
  `^[A-Z]:(\\[^>]*)?>$`, so a guest whose `AUTOEXEC.BAT` sets `PROMPT
  [$P]$G` — or `$T$G`, or anything with a suffix — made every `exec`
  call wait out its full timeout. Nothing in the spec said which
  prompts were even supported. **Closed** (issue #9; D112): the
  prompt the guest is already sitting at now counts as completion
  evidence, alongside the standard prompt shape, so a guest with a
  customized prompt works from its very first command with nothing
  extra needing to be declared. What's left is now stated rather than
  left open: a command that itself changes to a customized prompt
  returns text `exec` has no evidence for; the timeout error now names
  both prompt shapes it was waiting for; and the capture of `PROMPT
  [$P]$G` pins down that remaining limit.

None of these three is still an open gap. The corpus is why they closed
honestly: what counts as a DOS prompt, or as a command's echo, was a
real design question with a decision to make (D111, D112), not
something a test fixture should have been left to quietly settle on
its own. The fixtures pinned down the old, wrong behavior specifically
so that it couldn't be changed silently. Each re-recording is the
record that it wasn't.

## What this corpus deliberately does not cover

- **The machine layer.** A live `insert` or `eject` changes the medium
  through the machine layer's own session, not through the run being
  captured, so it can't show up in a capture at all — the fake
  lifecycle in `tests/replay.py` covers that case instead. What this
  corpus covers is only what the *guest's own screen* drove.
- **Timing as it actually happened in real time.** A replay runs on the
  capture's own recorded timeline, not against a real clock: every
  moment the layer measures against is the one the recording holds, and
  none of the original waiting costs anything to replay. A capture
  takes minutes because a real guest is slow, not because the layer
  itself is slow.
- **`--check`.** The ERRORLEVEL probe is a second command sent to the
  prompt, read back through the same echo logic, so a capture of it
  would only test the probe, not the reading logic. Nothing here
  exercises it.
- **The other backend.** These are all QEMU captures, which read text
  straight out of memory. VirtualBox reaches the same interpretation
  layer through the fixed-font recognizer instead, and a capture taken
  there would exercise that different path. The transcript format
  itself doesn't depend on which backend produced it, but testing the
  VirtualBox path needs an actual VirtualBox run, not a change to this
  corpus.
