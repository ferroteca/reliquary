<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# TASKS

The pledged work backlog. A **proposed** task lives in the issue
tracker — <https://github.com/ferroteca/reliquary/issues> — which is
the only queue a proposed task has (D43): the tracker is a task's
proposed state and this file is its pledged one. So nothing parks
here awaiting a verdict; arriving *is* the verdict.

**Everything in this file is pledged** — the one vocabulary
([README.md](README.md)) applying here exactly as in the
directories. An entry is in the *pledged* state, so entering it is
approving it: nothing waits on a verdict, nothing needs a citation
or a decision of its own, and there is nothing to promote. The
directory is not its home because `proposed/` and `pledged/` hold
*demand and capability*, argued at length, and a task is none of
those — free-standing work too small to be a feature and too small
to need the argument. That kind distinction is the distinguisher,
not size.

**This file is the third work input queue** (D43, widening D39's
two), and adding to it is governed by the gate covering all writing
under `planning/` — weighing most here, this being the one governed
act that grants approval with no argument behind it.

**A queue holds what waits.** Work that arrives already done never
appears here: there is nothing to schedule, only a decision to make,
and an entry filed and closed in one act is ceremony.

**Anything is struck when it is done** (D45, generalized by D52) —
tasks, audits, restructures and rounds alike. Its record is its
commit, its CHANGELOG line, and the D-numbers it produced, so it
leaves this file by deletion and nothing is parked. **Not a
retrospective either**: a note explaining what an emptied group
used to hold is the same parking one paragraph further on, and it
has to be edited every time the work it accounts for moves. The
same holds for the **work-item breakdowns inside a pledged
feature**: when the feature delivers, its list is deleted with its
F-number rather than archived. A record whose reasoning outlives
the work is a decision, and decisions live in
[DECISIONS.md](DECISIONS.md) — kept beside
the work instead, a summary drifts from what it summarizes and a
reader has no way to tell.

**There is no order here.** Nothing in this file is scheduled, and
nothing claims priority over anything else; whoever picks work up
picks whatever they like. The one ordering that does bind is a
feature's: **work that only makes sense as part of one pledged
feature lives with that feature**, in
[pledged/FEATURES.md](pledged/FEATURES.md), and has to be done to
complete it. **No feature has any today**, the shelf being empty. A
task here that merely *relates* to a feature is still free to be
picked whenever.

Housekeeping (D38) is the same instinct one size smaller: work tiny
enough and obvious enough that it needs no entry here **at all**,
approved as a class in advance, with the commit as its record. This
file is where the pre-approved work that is still worth writing
down goes. The full intake machinery — the raw queues, the
housekeeping test, and how pledge is recorded — is in
[README.md](README.md).

**Refused work is not recorded here** (D52). Entry to this file
*is* approval (D43), so a rejected task is one that never
entered — refusal happens at the door, and its record is the issue
that was closed or the [DECISIONS.md](DECISIONS.md) entry that
argued it, that file already being the guard against
re-litigating.

The file is one section, [Pledged](#pledged) — the queue proper,
grouped by kind because the actor and the gate differ, though the
grouping is not a running order.

Standing questions to re-ask as the design hardens are not tasks
and live with the decision record, under
[DECISIONS.md](DECISIONS.md)'s open questions.

## Pledged

Grouped by kind, because the actor and the gate differ: an audit
is mechanical, a defect needs no pledge because the norm it
violates already is one. A group with nothing in it is not listed:
an empty heading is a record of retired work, which this file does
not keep.

### Defects

A gap against a *standing* principle is a bug: the principle is
already its demand, so these need no pledge, only fixing. A gap
against a **shipped spec** is the same class and sits here too —
where `docs/spec/` and the code disagree the spec is right and the
code has the bug, so the norm is already the demand.

- **A drive image has no in-band route** (P16's residue, narrowed
  by D71 to the capability it actually needs). All five in-band
  file verbs — `put-file` / `get-file` / `put-files` /
  `get-files` / `list-files` — reach a directory-source (vvfat)
  drive only, and answer `drive.no-at-rest-access` for a drive
  image, which is P11 doing its job. D71 made the *letter*
  reachable, so the exchange-drive route works; what stays shut is
  the disk itself, and a consumer whose results are on an
  installed `C:` still needs the guest to copy them across.
  **Every hard-disk image should be readable and writable while
  the machine is offline** — which is when it is safe, the backend
  holding no lock and the guest not running. The fix is at-rest
  filesystem access behind the adapter seam: read and write a FAT
  volume in a drive image on the host, which is no more guest
  inspection than reading an image's format is (P10 untouched). It
  stays capability-honest per call: a filesystem the adapter
  cannot read fails **by name**, never by guess. DOS/FAT is the
  delivered case to close; a backend with no vvfat equivalent is
  the second backend's problem, not this one's.

- **A hard disk is assumed to hold one volume** (D71's residue,
  filed with the assumption per D48's bar). `platform_dos.drive_letters`
  places disks from `C:` in slot order and CD-ROMs after them, on
  the assumption that each disk carries exactly one volume. It is
  true of every disk Reliquary materializes and it is not a fact:
  a guest that repartitions `hdd0` into two volumes shifts every
  letter after it, and the map then names **the wrong drive
  silently** — it does not fail, which is what makes this a defect
  rather than a stated limit. Reliquary needs a mechanism to
  determine what volumes a hard-disk image really contains: the
  partition table, and past it whatever volume manager the guest
  layered on. That is host-side image reading and no more guest
  inspection than probing an image's format is (P10 untouched),
  and it shares its reader with the defect above. What stays
  refused permanently is a *declared* volume count in the
  blueprint (D56): the guest is the source of truth for its own
  volumes, and a declaration would carry a spec's authority over
  an assertion the guest can silently contradict.
