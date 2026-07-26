<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Script authoring by recording

> **Status:** the settled design for U6's authoring recorder
> (USE-CASES.md U6; owner rounds, 2026-07-21 — the
> adjudication trail is in planning/DECISIONS.md). Delivery is
> deliberately unscheduled: the recorder sits in
> planning/proposed/FEATURES.md "Horizon", earning a numbered milestone
> when its turn comes; work items are listed in
> planning/TASKS.md.

The authoring recorder serves U6: a person performs the task once
in a console session Reliquary supervises, and Reliquary drafts
the script and captures the landmark assets that reproduce it.
Settled design:

**Recording requires Reliquary to be the console.** Input typed
into a backend's own display window never passes through
Reliquary and cannot be followed; recording happens in a
Reliquary-owned viewer over the `vnc` control plane, where every
keystroke, click, and media swap is observable. The viewer is a
real component, and the recording prerequisite on every backend —
QEMU included.

**First capture drafts, the author tailors.** Input events
segment the session's timeline; the stable screen before each
input proposes the wait condition (a VGA text match in text mode,
a landmark in GUI mode), the input proposes the action, and
observed timing proposes generous timeouts. What the recorder
cannot know — which screen features are load-bearing, how long a
step may honestly take — it flags as generated comments in the
draft. Text-mode capture comes first and needs no new language
surface; GUI capture rides the landmark/click work, and a click's
position seeds its landmark's spot. The draft is ordinary script
text, self-contained by default — landmarks travel as embedded
resolve-in-place blocks (planning/proposed/design/landmarks.md) — with
factored
catalog files on request; written once and user-owned from then
on, like `import-vm` output.

**Round-trip composes with tailoring — playback is the
positioning mechanism.** Authored customization must survive
re-capture, so later sessions never regenerate or text-merge the
script. Instead, playback of the user's tailored script carries
the machine to the point of change — a breakpoint, or the exact
statement where the script fails against a changed guest — and
the person takes over the console, demonstrates, and hands back.
The recorder emits a *fragment* — new waits, actions, and assets
— anchored at the phase and statement of the user's own script.
Because the anchor comes from executing that script, not from
diffing it against a stored base, round-trip is robust to
arbitrary tailoring: no pristine draft is retained, no merge
happens. (os-autoinst's interactive mode is the concept precedent —
concepts only, per AGENTS.md.)

**Two tracks, two write boundaries.** A changed screen for an
unchanged step is an *asset refresh*: a new landmark variant,
never touching the script — the numbered-adjacency variant shape
(`<name>.<n>.png` beside the declaration, or beside the script
for an embedded landmark; planning/proposed/design/landmarks.md) makes
refresh
file-creation, never file-rewrite. New or changed steps
are *step capture*: the fragment is emitted beside the script for
the author to splice in their editor; an explicit opt-in apply
may perform the surgical insertion at the anchor, touching no
other byte — a named exception in the family of installing an
embedded definition. Round-trip is append-shaped everywhere;
nothing Reliquary wrote once is rewritten.

**Shared machinery.** Run-to-point, breakpoints, and human
takeover are runner features that also serve ordinary debugging —
"take over from here" is a natural suggested next command in a
failure report. Handover events (control passing between script
and human) join the run-events stream as event kinds, so a
capture session is one run record with mixed drivers. The
`record` command family lands on the CLI and the embedding API
together, under parity. Blueprints are untouched: a session runs
on an ordinary machine, and media swaps are already
`insert`/`eject`.

