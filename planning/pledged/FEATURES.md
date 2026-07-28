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

**This shelf emptied twice on 2026-07-27, by the two exits it
has.** F17 left by **delivery**, the ordinary one, and its number
retires with it (below). **F1 left by withdrawal** (owner; D61) —
the first use of that exit, and the reverse of the move that is
supposed to fill this file. Nothing was rejected: the recorder's
design stands and its demand is live. What was wrong was the
pledge, which nobody ever made — the 2026-07-26 restructure housed
the feature here because its work items had nowhere else to live,
and D44's rename then converted what this shelf *claims*, from
agreement into a commitment to deliver, without re-testing its
occupants. **U6**, the use case F1 delivers, and **U2** left for
[proposed/USE-CASES.md](../proposed/USE-CASES.md) in the same
round; **U1** left upward, condensed and promoted to the current
list. D44 wrote the remedy — a pledge nobody means is withdrawn or
rejected, never left sitting — and this is its first use.

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
