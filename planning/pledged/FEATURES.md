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

**This shelf emptied three times on 2026-07-27, by the two exits
it has.** F17 and F23 left by **delivery**, the ordinary one, and
their numbers retire with them (below). **F1 left by withdrawal**
(owner; D61) —
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

**It refilled on 2026-07-28** (owner), with **F2**, the backend
adapter seam — **the first feature to arrive here and stay**. F17
and F23 both arrived by an ordinary decision to build them and
both left by delivery within a day of it, and F1 was never pledged
by anyone's decision at all; F2 is the first entry this file has
held with its delivery still ahead of it. Its demand, **U7**, was
pledged in the same act ([USE-CASES.md](USE-CASES.md)) and had to
be: F2 waited five days for it, off the arc since 2026-07-23, and
pledging a feature ahead of the demand that justifies it is the
error D61 undid. Tested against
the size bound and pledged **whole**, so it keeps its number
(D65) — the extraction is bounded by working code and by a
regression oracle, not by judgment about how much is enough.

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

*(F23 — in-band listing and whole-tree file transfer — delivered
2026-07-27, the same day it was pledged, so its number retires
unreused. `list-files` / `get-files` / `put-files` and their
twins ship with one guest-terms address vocabulary shared with
`put-file` / `get-file`, a drive root sayable as `A:\`, a flat
listing document whose addresses feed straight back to the file
verbs, and a required `get-files` destination; the round is
[D62](../DECISIONS.md) and the surface is normative in
[cli.md](../../docs/spec/cli.md)'s in-band section.*

***P16 was armed by the same change***, which is the whole point
of the feature: it moved to the standing list with its residue —
an image drive has no in-band route — filed as a defect under
[TASKS.md](../TASKS.md), per D34 and D48.)*

## F2 — The backend adapter seam

> **Pledged 2026-07-28** (owner), with its demand **U7**
> ([USE-CASES.md](USE-CASES.md)) in the same act. Formerly
> milestone 10, dropped to the backlog 2026-07-23 (D33) because the
> multi-backend pillar had no use case demanding it; U7 is what
> closed that gap. Pledged whole — no cut, F2 keeps its number
> (D65). The seam's doctrine is settled and unchanged by any of
> this.

Extract the adapter API from the now-complete QEMU implementation
— the only adapter with a full control plane set — so the seam is
defined by working code, not speculation. The seam's doctrine is
pre-settled in
[design/backend-adapter.md](design/backend-adapter.md)
(layering, seam inventory, ownership and capability doctrines,
extraction map); this feature defines the signatures and records
them there.

**Settled 2026-07-28** (owner; D66), so this feature carries no
decide-first. The backend priority order for default assignment,
when a blueprint names no backend, is **QEMU, VirtualBox, VMware
Workstation, Hyper-V** — ordered by *agentless* scriptability.
That is the criterion because of when assignment happens:
materialization, before any guest exists, and the install that
follows is agentless by definition under P3's arc. A backend's
agent story is worth nothing at the moment the choice is made.
The order breaks ties among backends already available *and*
capable, so it never overrides a capability check (P11).

Work items:

1. The adapter API: lifecycle, media attachment, input, screen
   access, and control plane endpoints, with honest per-backend
   capability reporting feeding the existing capability checks
   (P11).
2. Backend autodiscovery (binaries on PATH and conventional
   locations, the Hyper-V service/module) establishing
   availability only.
3. Real default assignment from the prioritized availability
   list, recorded permanently into machine state; a declared
   `backend` pins the choice and fails closed if unavailable or
   incapable.
4. Stub adapters for VirtualBox, VMware Workstation, and Hyper-V
   raising `NotImplementedError`, mirroring platform handling.
5. Generalized ownership verification: no adapter sends a control
   command to a hypervisor object that doesn't match the
   machine's recorded `backend-id`.

Done when: all QEMU interaction flows through the adapter API and
the FreeDOS install script passes unchanged.
