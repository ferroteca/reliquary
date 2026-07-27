<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Pledged features

Large capability that is **pledged but not yet built**, each
carrying the work breakdown that delivers it. A feature arrives here
by being moved out of
[proposed/FEATURES.md](../proposed/FEATURES.md) — the move is the
pledge and the commit is its record ([README.md](../README.md))
— and leaves by being delivered.

Pledged is not scheduled: the numbered milestone arc ended with
milestone 9, so nothing below is queued or dated. The work items are
tasks like any other and answer to the same rules as
[TASKS.md](../TASKS.md); they sit with their feature rather than in
that queue because they are meaningless apart from it.

Each feature carries an **F-number** and must fit in **one sprint**
(D42; the rules are in [README.md](../README.md)). A feature too
large is cut on pledge, the split retiring the parent's number
for a fresh one per piece.

## F1 — The U6 authoring recorder

> **Unusually large — flagged, not cut** (owner, 2026-07-26). On the
> sprint this project runs, its seven work items are not one feature
> but at least seven. It stands as written by decision, and the flag
> is the whole of the treatment; the sequencing note below marks
> where a cut would fall if one is ever wanted.

Use case **U6 — pledged, awaiting delivery** (moved 2026-07-23);
design in [design/recorder.md](design/recorder.md). The one
capability the numbered arc deliberately did not deliver while its
demand was already pledged: the arc ended at milestone 9 with the
recorder unbuilt.

Work items, in rough dependency order:

- Reliquary-owned console viewer over the vnc control plane
  (recording prerequisite: backend display-window input is
  invisible to Reliquary)
- text-mode recorder first (no new language surface: waits from
  VGA scrapes, type/press actions, generated-comment
  uncertainty flags)
- runner run-to-point / breakpoint / human-takeover machinery
  (also the failure report's "take over from here" suggested
  next command)
- round-trip: fragment emission anchored by playback position;
  opt-in surgical apply at the anchor (never regenerate, never
  text-merge)
- landmark catalog shape: decided (DECISIONS.md, the wrinkle
  round; [design/landmarks.md](../proposed/design/landmarks.md)) —
  implementation rides the asset spec work
- run-events: handover event kinds (script/human control
  passing); a capture session is one run record with mixed
  drivers
- CLI record command family + API twins land together (parity)

**Sequencing note.** The console viewer rides the VNC control
plane, which is itself unbuilt — it arrives with the GUI era (F5,
[proposed/FEATURES.md](../proposed/FEATURES.md)). The text-mode
recorder is what can proceed without it. That reference runs *up*
the lifecycle, which D42 treats as a flaw rather than a dependency —
tolerated here alongside the size, and noted so it is not mistaken
for the normal shape. The text-mode half is the part that depends on
nothing unpledged.
