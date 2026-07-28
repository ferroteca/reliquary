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

*(F17 — input pacing before guest input — delivered 2026-07-27,
so its number retires unreused. The `pacing` keyword, the
`statement > phase > header > built-in 0.1s` ladder, the
parse-time plan `check-script` reports, and the runtime pause are
recorded in [D60](../DECISIONS.md); the model is normative in
[script-spec.md](../../docs/spec/script-spec.md)'s Timing section.

**One item did not travel with it, and is not closed.** The
bisection that would fix the default — the interval that reliably
lands a keystroke on the installer screen that motivated this —
needs a FreeDOS install rig, and no evidence yet fixes the number:
what is known is that "immediately" is too little and "several
seconds later" is enough. The shipped 0.1s is provisional by
design, so this revises a default rather than completing a
feature, which is why it did not hold the rest back. It wants its
own entry when someone stands the rig up.)*

## F23 — In-band listing and whole-tree file transfer

> **Pledged 2026-07-27 by D57**, which pledged **P16** and priced
> it: these two operations are the only places the shipped
> QEMU/DOS workflow fails P16's test, so they stop being deferred
> convenience and become owed work. Promoted out of
> [proposed/FEATURES.md](../proposed/FEATURES.md)'s Horizon, where
> they had been sequenced against the second backend; **that
> coupling is cut** — the second backend left the numbered arc
> with D33, and P16 does not wait on it. Serves **U14** and
> **U20**, demanded by **P16**.

THE GAP, IN P16'S TERMS. A consumer that needs to know what files
a stopped machine's drive holds, or to move a whole tree in or
out, has no verb to ask. It must open the drive directory itself —
which is exactly what P16 forbids Reliquary to require. Single-file
exchange is already served (`put-file` / `get-file`, milestone 9),
so the gap is precisely listing and bulk.

THE VERBS: `list-files` / `get-files` / `put-files` (twins
`list_files` / `get_files` / `put_files`), stopped-machine
operations under CLI–API parity.

**THE ADDRESSING MUST BE REDESIGNED, NOT RESUMED.** D5's rough
`<drive-key>:<path>` shape is illegal: **P17 refuses it**, armed
D47, because `hdd0:` is a blueprint key no guest ever says. The
shipped verbs address in guest terms (`A:\JOB.BAT`) and these must
match — one address vocabulary, not two spellings of it. F15 is
the neighbour that settles the same question from the other side.

The rest of D5's shape stands: images reached through the
adapter's at-rest filesystem access, directory-source media
directly; capability-honest per call, so a drive whose filesystem
the adapter cannot read fails **by name** (P11); `media` drives
excluded; directories recursive; no record custody — files land
where the caller says.

Work items:

- the guest-terms address form these share with `put-file` /
  `get-file`, settled once for all five verbs
- `list-files`, and what it returns: the shape is a contracted
  `--json` document under P7, so it is designed before it is built
- `get-files` / `put-files` over a directory-source drive, the
  path the shipped single-file verbs already take
- the same over an image through the adapter's at-rest access,
  where the filesystem may be unreadable and must fail by name
- `get-files`' destination default, which D5 left to this round
- CLI and API twins land together (parity)
- P16's promotion rides this work (D34): when these land, P16
  moves to the root list with its residue — backends with no
  vvfat equivalent — filed as a defect in the same change
