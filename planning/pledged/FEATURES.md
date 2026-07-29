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

**It refilled and emptied again on 2026-07-28** (owner), with
**F2**, the backend adapter seam — pledged in the morning and
delivered the same day, so it joins F17 and F23 in leaving by the
ordinary exit rather than becoming the first entry to sit here.
Its demand, **U7**, was pledged in the same act
([USE-CASES.md](USE-CASES.md)) and had to be: F2 waited five days
for it, off the arc since 2026-07-23, and pledging a feature ahead
of the demand that justifies it is the error D61 undid. **U7 does
not travel with it**: the seam is what U7 needed built, and the
case itself is met only when a second adapter can materialize a
machine on the hypervisor a host actually provides. F2 was tested
against the size bound and pledged **whole**, so its number
retires unreused (D65) — the extraction was bounded by working
code and by a regression oracle, not by judgment about how much is
enough.

*(F17 — input pacing before guest input — delivered 2026-07-27,
so its number retires unreused. The `pacing` keyword, the
`statement > phase > header > built-in 0.1s` ladder, the
parse-time plan `check-script` reports, and the runtime pause are
recorded in [D60](../DECISIONS.md); the model is normative in
[script-spec.md](../../docs/spec/script-spec.md)'s Timing
section.)*

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

*(F2 — the backend adapter seam — delivered 2026-07-28, the day it
was pledged, so its number retires unreused. One adapter API now
carries every backend operation
([design/backend-adapter.md](../design/backend-adapter.md), which
travelled out of `pledged/design/` with the delivery and records
the signatures it said it would): QEMU's half is
`reliquary/backend_qemu.py` and nothing above the seam names QEMU,
qcow2, QMP or a port; the agentless display console is
`reliquary/control_display.py`, reading the portable text-screen
contract rather than VGA bytes; assignment walks the D66 priority
order at materialization and takes the first backend both
available and capable, naming the backend and the requirement when
none is; VirtualBox, VMware Workstation and Hyper-V ship as stubs
that probe honestly and claim nothing; and the recorded VM
identity generalized to `{backend, backend-id, token, endpoint}`.
The oracle it was pledged against — the FreeDOS install script
passing unchanged — is the opt-in integration test, which is
unchanged by the extraction. The round is
[D67](../DECISIONS.md).*

***The three stubs are not a second backend.*** U7 stays pledged
and F3 stays proposed: what is delivered is the seam U7 demanded,
not the capability, and the order's tail remains intent recorded
(D66).)*
