<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Accepted features

Large capability that is **accepted but not yet built**, each
carrying the work breakdown that delivers it. A feature arrives here
by being moved out of
[proposed/FEATURES.md](../proposed/FEATURES.md) — the move is the
acceptance and the commit is its record ([README.md](../README.md))
— and leaves by being delivered.

Accepted is not scheduled: the numbered milestone arc ended with
milestone 9, so nothing below is on a sprint. The work items are
tasks like any other and answer to the same rules as
[TASKS.md](../TASKS.md); they sit with their feature rather than in
that queue because they are meaningless apart from it.

## The U6 authoring recorder

Use case **U6 — accepted, awaiting delivery** (moved 2026-07-23);
design in [design/recorder.md](design/recorder.md). The one
capability the numbered arc deliberately did not deliver while its
demand was already accepted: the arc ended at milestone 9 with the
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
plane, which is itself unbuilt — it arrives with the GUI era in
[proposed/FEATURES.md](../proposed/FEATURES.md). The text-mode
recorder is what can proceed without it.
