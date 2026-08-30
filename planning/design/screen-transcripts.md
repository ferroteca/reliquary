<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Screen transcripts: capture and reconstruction

> **Status:** this is delivered design doctrine — F42 built the
> capture and F43 built the fixture corpus on top of it, and once a
> feature is delivered there's no more "pledged" feature for its
> design document to sit next to ([README.md](../README.md)). It stays
> under `planning/` instead of moving to `docs/spec/` because the
> transcript format is internal by decision (**D98**), the same route
> `backend-adapter.md` took. It exists because of **P22**: the test
> suite is the gate a change has to pass, and the interpretation layer
> has no honest way to be tested without real captured input. It's
> shaped by **P11** (state a limitation plainly rather than hiding
> it), **P6** (the CLI and the API gain a feature together), and
> **P12** (Reliquary only writes files where it was explicitly told
> to). **Nothing in this document is a normative rule for outside
> callers**: the transcript format is deliberately not an application
> surface (D98), so it has no `docs/spec/` entry and no stability
> guarantee — it can change any time this document's author wants.

## Why fabricated test screens don't work

The interpretation layer that reads a guest's screen is heuristic,
built to work on real-world text: `_PROMPT_RE` decides what a DOS
prompt looks like, `_command_output()` finds the command's echo by
scanning backward for a row that ends with the command and contains
`>`, and there's `screen_text()`, `wait_text`, `cursor_menu_select`,
and the timers in `script_timing`. Code like this can't be honestly
unit-tested against screens someone made up by hand, because a
hand-written test screen encodes the same assumptions the heuristic
does — you write the screen you *believe* DOS draws, and then the
parser passes because it agrees with your own belief, not because it
actually handles what DOS really draws.

Only a screen captured from a real DOS run carries the things a
person wouldn't think to write: the odd spacing, a stray carriage
return, a half-drawn menu, a prompt that arrives in the middle of a
scroll.

## Where the recorder attaches: the carrier, not the reader

`script_runner._read()` reads through `console.screen_text()`, which
gives back text rows only — the per-cell attributes are already
thrown away by that point — and it never sees the individual polls
`cursor_menu_select` makes inside its own loop. Recording at that
point would only capture what the layer under test had *already*
decided the screen said, not the raw material it decided from.

So the recorder instead wraps the **carrier** — the session interface
an adapter provides: `text_screen()`, `send_keys()`, `screenshot()`,
`change_medium()`. This is the same carrier concept described in
[backend-adapter.md](backend-adapter.md): here, a frame is still the
raw `(rows, attributes)` pair, and every read any layer above makes
has to pass through it.

That placement has two consequences, and both are the reason it's
placed there:

- **Reconstruction can stand in a fake session at that exact point**,
  and the entire interpretation layer above it —
  `control_display`, `interaction_agentless`, the runner's dispatch
  logic — runs completely unmodified on top of the fake. That's what
  makes the resulting test fixtures worth having: they exercise real
  code, not a simulation of it.
- **Both ways of driving a machine go through this same point.** A
  script run drives the phase graph, the menus, and the stability
  gates. `exec` drives prompt detection and command-echo scanning,
  which no script run ever touches. Both paths sit above this same
  carrier, so a capture of either kind of run produces the same kind
  of file. And because the `exec` adapter takes the machine handle it
  reads through as an argument, capturing an `exec` run needs no flag
  on the `exec` surface itself — just a handle that already has the
  recorder wired into it.
- **The recorder works the same regardless of backend.** It wraps the
  carrier interface, not QEMU specifically, so a capture taken against
  a different backend adapter reconstructs through the exact same
  reader code.

There's also one rule the very first capture run found the hard way:
**every caller has to go through the one wrapped handle.** If
anything in the run builds a second handle, calls made through that
second handle never reach the transcript, and the transcript's own
"never improvise an answer" rule (below) then fires against the
*reader* during reconstruction — it hits a call the file has no
record of. So a run builds exactly one machine handle and reaches the
carrier only through it: the console object is used for every read
and every input verb, and that same handle is reused for the
`screenshot` verb and for automatic failure capture, both of which
used to build their own separate handle.

## Why recording changes the run's own poll rate

QEMU's QMP server only allows one client connected at a time, which
is why Reliquary never holds a session open while a statement list is
running (AGENTS.md, "Script dispatch"). That rules out the obvious
approach of an independent sampler thread polling on its own clock —
it would be competing with the run itself for the one available
connection.

The run's own polling is already coarse: `_POLL_INTERVAL` is 2.0
seconds during dispatch, `_PROMPT_POLL` is 2.0 seconds while waiting
on a prompt, `_ECHO_POLL` is 0.1 seconds right after a command runs,
and the menu-following code settles at 0.1–0.15 seconds. If the
recorder only captured what the run already happened to read, most of
a boot sequence would have two-second gaps in it.

So instead, **recording speeds up the interpretation layer's own poll
clocks**: under `--record`, no poll interval is allowed to be slower
than the recording pace, every poll doubles as both a normal
functional read and a recorded frame, and one QMP client connection
is all that's needed either way.

**The pace only ever makes polling faster — it never makes it
slower** — and that one-directional rule is the whole point of the
mechanism, not an incidental detail. The first implementation instead
took whichever was *larger*, the pace or the normal production
interval, which meant every interval stayed exactly as slow as it was
before: the `--record` flag existed, the transcript header stated a
pace, but the capture still had the same two-second gaps this
mechanism exists to close. A capture of a five-and-a-half-minute
install held 536 screens under that first version; the same run now
yields 2,673.

That one-directional rule requires three things in turn:

- **The pace is a target, not a promise.** No sample is ever taken
  while a statement list is actively executing, and that rule matters
  — a screen that appeared and then vanished again inside a single
  handler simply never happened as far as the recording is concerned,
  and recording must not change that. The resulting gaps in the
  transcript are real gaps; the timestamps are what make them visible
  rather than hidden.
- **Recording changes the run being recorded, and that effect isn't
  small.** A recorded run polls harder than an unrecorded one would.
  Denser polling only ever adds information, it never removes any —
  but it's still a measurably different run. So the transcript header
  states the pace the capture was taken at, so nobody mistakes a
  fixture's timing for production timing. Measured on QEMU, where
  each sample is a 4,000-byte memory dump and the guest is briefly
  stopped for each one: a recorded FreeDOS install takes **two to
  three times longer** than the same install unrecorded. That's a
  deliberate trade — a slower pace costs less time but loses fidelity,
  a faster pace costs more time but keeps more detail, and choosing
  the pace is choosing that trade-off.
- **The pace is recorded in the file, not assumed by the reader.** A
  reader gets the pace from the transcript's own header, not from a
  source-code constant that might have since changed.

## What a frame is

A frame follows the same text-screen format the carrier itself uses
(see [backend-adapter.md](backend-adapter.md)): character rows, plus
per-cell attribute tokens that are opaque but can be compared for
equality. **A frame's identity is the whole pair, rows and
attributes together, not the rows alone.** A cursor menu moves its
highlighted selection by attribute alone, with the text underneath
unchanged, so comparing text only would treat two frames as identical
right when the menu machinery most needs to tell them apart.

Two frames in a row that are identical collapse into one entry. What
each surviving entry actually stores:

- **Row deltas** — only the rows that changed. A DOS screen typically
  changes one or two rows out of twenty-five.
- **A full keyframe right after every gap in sampling.** Whenever
  sampling stopped — a statement list running, keys going out — the
  transcript has no honest claim about continuity across that gap
  anyway, so the next entry recorded is a complete frame rather than
  a delta. That's a rule based on what the transcript can actually
  claim, not an arbitrary "every N frames" rule.
- **A digest of the reconstructed screen**, a few bytes per entry.
  Reconstruction rebuilds the screen and checks it against this
  digest. That way, a bug in reconstruction or a hand-edited fixture
  fails loudly instead of silently producing a screen that never
  actually happened — the same "never improvise an answer" rule
  described below, applied to the file format itself. The digest
  covers the screen **after it's been expanded back out**, so exactly
  how the file spells a delta is never something a fixture's
  assertions depend on.
- **Attributes stored as runs**, `[[count, token], …]` per row, rather
  than one token per cell. Per-cell arrays made up seventy percent of
  the first real capture's size — eighty tokens per row, twenty-five
  rows per keyframe — where a real DOS row is actually only one to
  four runs of a repeated attribute. The same reasoning behind row
  deltas applies here too: a reviewer reads "normal text, then a
  highlight starting at column ten for fifteen cells" far more easily
  than eighty repeated copies of the same number.
- **Both kinds of timestamp** — wall-clock time and elapsed time,
  matching the envelope `events.py` already uses. Reconstruction uses
  the elapsed time; the wall-clock time is there just to record when
  the capture was taken.
- **Every read that was absorbed into this frame, and exactly when
  each one happened.** The first design only stored a count of how
  many reads a frame absorbed, and that turned out not to be enough.
  "This screen was on-screen for two seconds across forty separate
  reads" and "this screen was on-screen for two seconds with nobody
  reading it" are different facts, and only the first one actually
  tells you the guest was sitting quietly (P11). Reconstruction has to
  answer each of those forty reads *at the specific moment each one
  was originally taken*, and a bare count leaves it guessing at those
  moments. Spreading the reads out evenly across the gap is the
  obvious guess to make — and on a real capture, that guess shifted
  the cursor-menu code by exactly one read, which changed which key it
  ended up pressing. The reconstruction section below covers this same
  fact from the reader's side.

**Why deltas, when it isn't about file size.** Gzip already beats any
hand-rolled encoding on frames this repetitive, and a ten-minute
install comes out to a few hundred kilobytes either way, delta-encoded
or not. **The actual reason is reviewability.** These transcript files
get committed to the repository, read by whoever is debugging prompt
detection, and re-recorded later as the code changes. A delta
transcript reads like a narration — row 12 became `C:\>` at 4.35
seconds — so re-recording produces a diff a person can actually read.
A whole-frame transcript would make every single re-recording touch
every line of the file. Going one step further, to cell-granular
deltas instead of row-granular ones, was rejected for the same
reason working the other way: the extra size savings would be
marginal, and the reconstruction code needed to rebuild cell-level
deltas would itself become code that needs its own tests — a fixture
format that you'd then have to debug in turn.

## The transcript records both what was read and what was sent

Recording screens alone would only test the reader half of the code.
The capture also records the carrier calls the run itself made — key
combinations sent, screenshots taken, media swapped — each timestamped
on the same clock as the screens.

That's what makes this a transcript, not just a screen dump, and it's
what makes the "never improvise" rule checkable: when reconstructing,
**any request the transcript doesn't have a matching entry for is an
error**, naming exactly what was asked for and where in the run. It's
never answered with an improvised guess, and never with an empty
response (P11). Improvising is exactly how a broken reader could end
up reporting a passing test against a transcript that never actually
covered the situation it was being tested on.

**A read that arrives at a point where the capture's next entry is
actually a carrier call is exactly this kind of unanswerable
request**, and silently stepping past it was a real bug in the first
version. A run that read the screen one extra time compared to what
was recorded ended up swallowing the keypress the capture had
recorded at that point, treated the *following* recorded call as its
answer instead, and from then on compared every subsequent keystroke
against the wrong recorded one. The resulting mismatch only surfaced
eighteen seconds later, against a screen that had nothing to do with
where the actual bug was. Where a mismatch shows up and where its
cause actually is can be two completely different places in the file.

**One kind of entry doesn't come from the carrier at all, because the
carrier has no way to represent it.** A guest that powers itself off
isn't a carrier call that returns some particular value — it's a
session that refuses to even open, since a session's identity gets
verified while it's opening, and the recording wrapper doesn't exist
until that verification succeeds. So the run instead records a
**`vm-gone`** entry whenever its console can't be opened, and
reconstruction raises the adapter's own "can't reach this VM" error
in its place. This is what makes a `wait machine=stopped` work during
reconstruction — and every DOS install script ends with exactly that
wait. Without a `vm-gone` entry, a capture would only replay up to the
shutdown and stop there.

## What a capture says about itself

The transcript's header records the pace it was captured at (above),
whether the recording stopped early because a secret reached the
guest, and **what the capture is actually a recording of** — either a
script, identified by name plus the sha256 hash of its text, or a
command, identified by its text plus the timeout it was given (which
is the entire input to an `exec` run).

**And the file ends with what the run actually concluded.** The
carrier itself can't show this: two different runs looking at the
same screens — one that correctly extracted the right output rows,
one that grabbed somebody else's rows by mistake, one that finished
normally, one that timed out — all make the exact same carrier calls,
because deciding which rows count as "the output" happens above the
carrier, not at it. So the driver writes its conclusion as a trailer
at the end of the file, and reconstruction is checked against that
trailer. That's what lets a capture of a run that **failed** work as
a test fixture just like any other — and the deliberately pathological
captures are exactly that: they pin down what the interpretation
layer does when it reads a screen wrongly, so that once the
underlying bug is actually fixed, the fixture fails loudly and gets
retired, instead of quietly passing over behavior nobody believes in
anymore.

A transcript gets replayed by standing the same script back up and
running it against the recorded data, and the transcript file itself
is the only thing that records which script that was — nothing else
in a fixture directory says so on its own. The digest is the other
half of that: if a script gets edited after its capture was taken, the
recording diverges from the new script partway through, and "this was
captured against a different, older `freedos-install.rlqs`" is a far
more useful error than a keystroke mismatch eleven minutes into
reconstruction. This digest field is left out entirely when there's no
readable script behind the run — because a header field that's
sometimes just a guess is worse than one that's sometimes simply
absent (P11).

## Reconstruction runs on the capture's own recorded clock, not real time

The interpretation layer is timed all the way through — poll ramps,
the settling gap, the stability window, the menu machinery's baseline
— and `screen_stability` measures over **wall-clock windows**
specifically so that polling faster or slower never changes the
verdict it reaches. If a reconstruction reader instead ticked forward
using its own `sleep()` calls, it would end up placing frames 100
milliseconds apart that the guest had actually drawn a third of a
second apart — and it would reach different verdicts than the
original recorded run reached.

So during reconstruction, **time is exactly what the transcript file
says it is**: a sleep the interpretation layer asks for is honored as
asked, and the read that follows it is handed back at the exact
moment that read was originally taken. Both of those pieces are
needed, and they aren't interchangeable — the interpretation layer
samples the clock *before* it reads the screen, so a reader that only
gets the read timing right (and fakes the sleep) hands back a moment
that's one read stale; a reader that only gets the sleep timing right
(and fakes the read) drifts away from what the guest actually did.
This has two consequences, and the second is exactly why each frame
stores every moment it absorbed:

- A five-minute capture replays in about one second, which is what
  lets these fixtures live in the default test suite instead of some
  opt-in slow tier.
- Every moment has to come from the recording, never be estimated.
  The interpretation layer is sensitive down to the granularity of a
  single read, so any reconstructed timing — however reasonable it
  looks — produces a different run than the one that was recorded.

## A typed secret stops the recording

A raw captured screen can carry a typed password in plain text, and
the event stream's redaction logic can't reach it there — redaction
works on strings the event stream carries, and a frame is a grid of
cells, not a string.

The rule here is taken verbatim from the same rule screenshots
already follow — **once a bound secret has reached the guest,
recording stops for the rest of that run**, and the transcript records
that it stopped, and why. There's no partial redaction and no
scanning the screen to find and mask the secret: a value that's been
echoed into a form field, wrapped across a row boundary, or already
masked by the guest itself isn't something you can reliably find on
screen, and a redactor that usually catches it is more dangerous than
one that refuses to try at all. A run that binds a secret ends up with
a short transcript that plainly says why it's short.

## Where a transcript is written

Only at the path the caller gave — and nowhere else. There's no
default location, nothing gets written into the machine directory,
nothing under `cache/`, and no transcript at all when the `--record`
flag isn't given. That keeps P12 intact, and keeps D36's rule — "a run
stores nothing" — true of every run except the one a maintainer
deliberately asked to record (D98).

## This format is not an application surface

It has **no standing as an application surface** (D98): no entry in
`docs/spec/`, no stability guarantee, no compatibility obligation, and
a change to the format itself just counts as ordinary housekeeping.
Its file extension is `.rlqt`, matching the existing family
(`.rlqb`, `.rlqs`, `.rlql`) — that naming match is the only thing
reserved about it. The one proposal that would have promoted this
format into a real application surface, F44, was rejected outright
(D100), so nothing about the format's design anticipates a future
public version of it.

What *is* an application surface is the `--record <path>` flag on
`run-script`, and `run_script(record=)` on the embedding session —
those two landed together as S1 and S2, following P6.

## What was deliberately left out

A public backend that ran entire flows straight off a transcript was
proposed as **F44**, and rejected (D100): the concrete benefit it
offered — cheap, repeatable reruns of one unchanging script — is
already F43's job. The broader demand it was trying to borrow was
actually F12's, and a recording doesn't answer to that demand either.
So this format stays exactly what it has always been: a maintainer's
own tool for debugging and building the fixture corpus, never
something an outside caller drives directly.
