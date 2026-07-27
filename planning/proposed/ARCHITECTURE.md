<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Proposed architecture

> **Status:** the staging ground for changes to the architecture —
> new principles, model changes, retirements — argued here before
> anything is pledged. **Nothing here is pledged, and nothing is worked
> from here.** The lifecycle mirrors the use-case one
> ([proposed/USE-CASES.md](USE-CASES.md)) and runs across three
> locations: drafted here, then **pledged** — moved to
> [pledged/ARCHITECTURE.md](../pledged/ARCHITECTURE.md), the move
> itself the record — then in force, moved again into root
> [ARCHITECTURE.md](../../ARCHITECTURE.md), which sits at the
> repository root because it describes current reality: the shipped
> system's model, and only the principles the project honors
> today.
>
> All three share one global P-namespace; numbers are permanent
> and never reused, and no placeholder is left behind by either
> move. A principle in force is clarified, retired, or superseded —
> never changed in nature — while a proposed one may still be
> reshaped freely here (its number stays; work already scheduled
> against it is re-checked in the same edit). The second move is
> **automatic** (D34), and its trigger is delivery rather than
> pledge — for a principle, *honored as a rule* with every known
> residue filed as a defect in the same change (D48), never the
> full-delivery bar a use case answers to. A dead proposal is recorded in
> [DECISIONS.md](../DECISIONS.md) and triggers the same
> planning-doc sweep, its P-number the search key.

## Open proposals

### Drafted

**P16 — Reliquary is the only interface to a machine** —
drafted (add, 2026-07-23; the owner's proposal, verbatim: *"All
foreseeable interaction with a VM should be through Reliquary.
A known use case which expects out-of-band access to fulfil the
user's goal, would violate this principle."* — "VM" reads as
the house noun **machine**). Adjudication pending; nothing is
folded downstream, and the collision below is the reason to
adjudicate rather than absorb.

WHAT IT ASSERTS is a test on use cases, not on users. Out-of-band
access stays physically possible — a stopped machine's drives
are plain host state and always will be — and a user who wants
to poke at them is not the target. The violation is narrower and
sharper: a KNOWN GOAL THAT CANNOT BE REACHED without leaving
Reliquary. Reaching around the tool is then not a workflow, it
is a capability gap wearing one.

WHAT IT DOES NOT ASSERT, or it will over-read on first citation:
- **Export is a handoff, not a breach.** `export-machine` ends
  with Reliquary letting go on purpose (P1, the U8 draft); the
  artifact leaves its purview by design. P16 governs machines
  Reliquary still owns.
- **The guest's own world is untouched.** Guest logs, guest
  history, and what a person does at a console are the guest's,
  as the transcript-redaction contract already says.
- **It is not the closed input model.** P15 closes how
  *authored input* reaches Reliquary; P16 would close how
  *interaction with a running or stopped machine* does.

ALREADY HONORED IN ONE PLACE, WHICH IS THE ARGUMENT FOR IT: the
U6 recorder's first work item exists for exactly this reason —
"backend display-window input is invisible to Reliquary"
(TASKS.md; planning/pledged/design/recorder.md), so the recorder gets a
Reliquary-owned console viewer rather than recording a person
typing into QEMU's own window. That is P16 reasoning, applied
before P16 was stated, and it is what a real principle looks
like on the way in.

WHERE IT COLLIDES — D5, HEAD-ON, and this is the whole
adjudication. D5 (the out-of-band round, owner 2026-07-22)
dropped run collection and made **file exchange out-of-band by
design**: while a machine is stopped its drives are plain host
state, `get-machine-dir` is the door, "Reliquary neither
mediates nor records it", and in-band `list-files` /
`get-files` / `put-files` were deferred to Horizon. D5 reached
that by asking *"what use case cannot be met without it?"* and
answering *"none"*. P16 CHANGES THE QUESTION — from whether the
goal is reachable to whether it is reachable THROUGH RELIQUARY —
and on the new question D5's own answer inverts: U14's
inject-execute-observe loop is a known use case whose file half
was, when this was written, served only out of band. Under P16
that was a violation on its face.

**MILESTONE 9 MOVED THIS GROUND, and the correction is recorded
rather than absorbed** (2026-07-27, the `hostdir` sweep) because
it weakens P16's own strongest example. Single-file in-band
exchange **now ships**: `put-file` / `get-file`, addressed in
guest terms, over a directory-source drive. So U14's file half
is no longer out-of-band-only, and the violation P16 named has
narrowed to what is still deferred — **listing and whole-tree
transfer**, plus every backend with no vvfat equivalent, where
the out-of-band route remains the only one. Whether a narrower
violation still carries P16 is exactly what its adjudication has
to weigh, and it should weigh the current fact rather than the
one that was true in July. **The citation strengthened in the
other direction when U3 retired** (D51): the loop it names is
now a use case *in force*, not a pledged one.

WHAT PLEDGING WOULD COST, stated plainly so it is priced
before it is granted: the Horizon in-band file operations stop
being unjustified deferral and become demanded work — a roadmap
item citing P16, which under D23 is this proposal's pledge.
They are currently sequenced against the second backend, which
left the numbered arc the same day (D33), so pledge would
also be the argument for scheduling them independently of it.
D5 is not retired by this: its drops (the `results` header,
`stage`/`collect`, record custody) stand on their own reasoning,
and only its out-of-band clause is in question.

OPEN FOR ADJUDICATION:
1. **Reach.** Does "foreseeable interaction" mean file exchange
   specifically, or every touch — a person typing into the
   backend's console window under `--display`, `hmp`, a user's
   own tools on a stopped drive image?
2. **Does the out-of-band route survive?** Permitted convenience
   alongside an in-band route, or retracted as the sanctioned
   answer? (The edges D5 contracted — running drives
   untouchable, media cache read-only, `runs/` append-only —
   are worth keeping either way.)
3. **`hostdir`.** A `hostdir` drive *is* a declared host
   directory: in-band by declaration, or the canonical instance
   of the violation? The answer decides whether QEMU/DOS is
   already compliant or is the first thing to fix.
4. **"Foreseeable."** A principle that binds on foresight needs
   its own test, or it becomes unfalsifiable — probably "a use
   case in force or pledged", which keeps it inside the
   existing lifecycle.

Statement (candidate; the reach question above may narrow it):

> - **P16 — Reliquary is the only interface to a machine.**
>   Every interaction a use case depends on goes through
>   Reliquary — its CLI, its API, its scripts. Out-of-band
>   access to a machine's host state stays possible and stays
>   unmediated, but no goal the project has pledged may
>   *require* it: a use case that must reach around Reliquary
>   to be met names a capability gap, and the gap is what gets
>   fixed. Handing a machine off is not a breach — export ends
>   Reliquary's ownership on purpose. (Normative home: TBD on
>   pledge.)

### Tracked

- **Sharpen P3 from "guest agents" to "transport agents"** —
  tracked (recorded 2026-07-24, the exec-run round; D36). P3
  today says Reliquary consumes native guest agents and never
  builds its own; the fast file-transport thread found the same
  logic binds the *host* side of a transport agent — Reliquary
  builds neither side, sourcing the transport externally (an
  existing tool, then a dedicated project) and providing only the
  control-plane seam. Fold into P3's wording if the fast-transport
  work schedules.

