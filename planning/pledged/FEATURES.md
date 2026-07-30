<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
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

**It refilled again on 2026-07-29** (owner; D79) with **F24** and
**F25**, the two halves of `--dry-run` — and by the exit no feature
had used before. F11 was **cut on pledge**: too large for D42's
one-sprint bound, so its number retires unreused and a fresh one
comes to each piece, which is the rule this file's own preamble
states and the first occasion to apply it. D65 is the near miss —
F2 was weighed for the same cut a day earlier and pledged whole,
its pieces not being independently useful. These two are: each
lands coherently on its own, and neither waits on the other.

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

*(F24 — `create-machine --dry-run` — delivered 2026-07-29, the day
it was pledged, so its number retires unreused and the work items
go with it. A create's whole evaluation now runs with nothing
committed: the machine id it would allocate, the backend it would
land on, every drive's resolved plan, and each media reported
`cached` / `would-download` / `would-extract` / `local-present` /
`unbound` without a fetch and without a hash. `--backend` asks the
U7 question about a host one is not standing on, capability alone
deciding. The rulings the build produced — what a dry run refuses
and what it merely reports, why nothing is hashed, and the shape of
the `DryRun` F25 inherits — are [D80](../DECISIONS.md); the surface
is normative in [cli.md](../../docs/spec/cli.md)'s "The dry run".

**U7 stays pledged**, and this is the same distinction F2's
delivery drew: a static answer about a backend is not a machine
materialized on one. What F24 delivers is the question, not the
capability.)*

*(F25 — `run-script --dry-run`, and the end of the check family —
delivered 2026-07-29, the day it was pledged, so its number retires
unreused and the work items go with it. `check-script`, its twin and
its result type are **deleted, not aliased** (P9), and
`test_old_surface_purge.py` keeps them retired; `check_key` went
private with them, closing the P6 residue D79 found. The three
surface collisions landed as the entry read them: the selector is
optional under `--dry-run` alone and its presence chooses the tier,
`--json` becomes legal there while `--progress` and `--display` are
refused, and the positional keeps `run-script`'s own name. The
report now says how much of a script no static pass can promise
will run. The rulings the build produced are
[D81](../DECISIONS.md); the surface is normative in
[cli.md](../../docs/spec/cli.md)'s "The dry run" and
[script-spec.md](../../docs/spec/script-spec.md)'s two checkable
tiers.)*

**This shelf stands empty again**, the day it refilled — both
halves of the cut delivered on the day they were pledged, which is
what a sprint-sized pledge is supposed to look like. The project
owes no unbuilt feature; [USE-CASES.md](USE-CASES.md) still owes
**U7**, which neither half met and neither claimed to. What fills
this file next arrives the way F24 and F25 did: by someone deciding
to build something argued in [proposed/](../proposed/).

**It refilled on 2026-07-29** (owner) with **F26–F28**, exactly
that way — the first fill whose features arrived from outside, a
consuming project's proposal admitted the same day. Each was
tested against D42's bound and pledged whole. The pledge round
did what the entries' own admissions required: **U22** was drafted
([proposed/USE-CASES.md](../proposed/USE-CASES.md)) as the case
F27's entry said must exist first, and **F14 was weighed beside
F26** as that entry directs and stays proposed — the surfaces are
separable (an opt-in outcome channel does not reshape the row
return), and F14's own decide-first, whether full capture is
Reliquary's at all, is unsettled, which is exactly the
pledging-outruns-the-design flaw the reference rule names. F28
cites U22 through F27's hatch clause, F27 being pledged in the
same act, so the reference runs sideways.

**F30 passed straight through on 2026-07-30** (owner) — pledged out
of [proposed/](../proposed/FEATURES.md) and delivered in the same
act, so this shelf never held it and its number retires unreused
(D90). Its three decide-firsts were settled as recommended first:
both halves rather than either alone, `expect=` for the parameter,
and an optional `value=` whose absence means presence. What it
delivered: `run_script(expect=)` / `--expect key=value`, contracting
a run on the machine variables it leaves, and `wait_machine_var` /
`wait-machine-var`, the poll for a variable another actor sets. The
build's own finding is the interesting part and is in D90 — the
async design's builtin-`TimeoutError` rule collided with the armed
invariant that no deliberate raise is a bare builtin, and
`WaitExpired` is what honoring both looks like.

**F26 left by delivery on 2026-07-30** (owner), the ordinary exit,
and its number retires with it: `exec` grew `check=True` / `--check`
and the ERRORLEVEL probe behind them (D89). Its error-text refusal —
the recommendation its entry said would travel unresolved to
delivery — was adopted as recommended and is now stated in the
normative spec rather than carried as a decide-first. **F14 stays
proposed** and is untouched by this: an opt-in outcome channel does
not reshape the row return, which is what the pledge round already
found when it weighed the two.

*(F27 — a `devices` axis for the machine blueprint — delivered
2026-07-30 (owner), so its number retires unreused and the work
items go with it. A machine now declares the hardware it must
contain beyond its drives (`"devices": ["virtio-rng"]`), the
declaration reaches `assign()` as a `Requirements` axis judged in
`unmet()` like every other, and the adapter that reported the
device renders it (QEMU: `-device virtio-rng-pci`). What that
buys is what the entry argued: a portable need rather than an
engine pin, refused up front naming the device where no available
backend provides it (P11). **Both decide-firsts were settled as
the record already implied** rather than re-argued — the name is
the device *model* spelled by its own cross-hypervisor standard,
which is U22's own spelling, and the guest's driver stays the
caller's business, as the entry recommended and the `controller`
rule already words it. The rulings the build produced — why an
abstract class was declined, why the vocabulary ships with one
name instead of borrowing the `control-planes` accept-then-refuse
pattern, and why a reported device must be a renderable one — are
[D91](../DECISIONS.md); the surface is normative in
[blueprint-model.md](../../docs/spec/blueprint-model.md)'s
`devices` clause.*

***U22's step 3 kept one mark for the rest of that day.*** The
`devices` half was live; the escape-hatch half was **F28**, which
cleared hours later — below.)*

*[D93 overruled this the same day it landed: the axis is removed,
admission to the blueprint's first-class vocabulary is gated by
P25 (root ARCHITECTURE.md), and U22's route is the backend pin
plus F28's hatch. The `devices` clause this note points at is
gone with it.]*

*(F28 — adapters honor `backend-settings` — delivered 2026-07-30
(owner), the same day as F27 and immediately after it, so its
number retires unreused and the work items go with it. The entry's
strong preference is what was done: implement what was designed
rather than re-scope the documents. QEMU's section is honored
(`machine` becomes `-machine`, `args` are appended verbatim, both
rendered last so a caller's own arguments are the tail of the
logged command line), the adapter defines the keys its section may
carry and refuses the rest, an argument restating a first-class
field or the recorded VM identity is refused naming its owner, and
`backend-settings` for exactly one backend narrows assignment to
it where no `backend` is declared. The descriptive reference stops
outrunning its norm in the same change, which was the one bug the
entry said was the reference's whatever else got decided. The
rulings the build produced — the renderer *is* the validator, why
`-device` and `-cpu` stay the caller's while `-smp` is reserved
over a gap the adapter has not closed, and why a narrowed backend
must not be reported as a pinned one — are
[D92](../DECISIONS.md); the surface is normative in
[blueprint-model.md](../../docs/spec/blueprint-model.md)'s
`backend-settings` clause.*

***U22's marks are all clear now***, so the journey reads complete
on the live surface. **Promoting it is a governed act and none of
this delivery's business** (D43): the case sits in
[proposed/USE-CASES.md](../proposed/USE-CASES.md) until the owner
moves it.)*

**This shelf stands empty again** — F26, F27 and F28 all delivered
on 2026-07-30, the three that arrived from outside on 2026-07-29.
The project owes no unbuilt feature; [USE-CASES.md](USE-CASES.md)
still owes **U7**, which none of the three met or claimed to. What
fills this file next arrives the way they did: by someone deciding
to build something argued in [proposed/](../proposed/).
