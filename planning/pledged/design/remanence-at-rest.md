<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# The at-rest handover (F40)

> **Status:** design for pledged **F40**
> ([../FEATURES.md](../FEATURES.md)), which arms **P27**
> ([../ARCHITECTURE.md](../ARCHITECTURE.md)) on delivery. A design
> carries no number of its own and travels with its feature.

Remanence (`remanence==0.0.1a2`, pinned exact) becomes the one deep
module for at-rest disk access: opening raw and qcow2 images where
they lie, claiming the image and any backing chain, discovering
geometry, reading and writing FAT volumes, and committing or
rolling back. Reliquary keeps the policy Remanence cannot own — the
DOS-only recognition claim, guest-address mapping, rule ids, and
the recorded drive report's shape.

## The seam: opening leaves the adapter

`open_drive` leaves the adapter protocol. The machine model opens a
disk through `at_rest`, which calls
`remanence.Disk(path, writable=...)` — the image opened where it
lies (D77), the claim taken at open under Remanence's own ladder.
The adapter's remaining contribution is `capabilities().at_rest`:
the declaration that its chosen image format is within the claim.

Rejected: keeping `open_drive` per-adapter with a Remanence-backed
implementation. The adapter no longer contributes anything to the
call — raw and qcow2 are both the dependency's claim — and a
per-adapter seam is the door a second implementation would arrive
through, which is the hybrid P27 refuses. A future backend whose
format lies beyond Remanence's claim declares `at_rest` false, and
widening the claim is Remanence work, not adapter work.

## The translation

`at_rest.py` keeps its name and its consumers; its contents change
owner. What it retains is translation, not reading:

| Today | Through Remanence |
|---|---|
| `adapter.open_drive(path, writable=)` → access with `.device` | `remanence.Disk(path, writable=)` |
| `Image(device).geometry()` | `disk.geometry()` |
| `image.volumes[index]` verbs | disk verbs keyed by volume id; the letter map's index resolves to `geometry().volumes[index].id` at open |
| `image.flush()`; `access.commit()` | `disk.commit()` |
| close without commit undoes | `disk.rollback()` / `close()` |
| `ImageLock` claim | the claim `Disk` takes at open; refusal by name |
| `UnreadableImage` | `RemanenceError`, categories mapped to rule ids |

The report's recorded shape is unchanged — the switch touches no
application surface:

- **Blank is an answer on both sides.** Today's reader returns zero
  volumes for an all-zero disk; Remanence answers `blank=True`; the
  record reads the same.
- **Partition rows map field for field**: the number, the type byte
  verbatim, the declared reading, the length, primary or logical.
- **Disk-level `cylinders` stays derived the same way**: the first
  volume's BPB `heads` × `sectors_per_track` against the disk size,
  `None` where no volume states them — unanswered rather than
  guessed (P10).
- **The whole-disk refusal stands.** Remanence reports a partition
  it cannot read as a row carrying its issue and reads the rest;
  the translation keeps today's policy and refuses the disk when
  any row carries one — a disk Reliquary cannot account for is a
  disk whose volume ordering it cannot vouch for. Adopting partial
  reporting is a report-semantics change: its own proposal if
  wanted, never a rider on the arming.
- **The letter map stays index-based.** Remanence's stable volume
  ids are resolved at open and strengthen the volume-vanished
  guard — an id mismatch is caught, not only a count change —
  and nothing recorded changes shape.

Error mapping: Remanence's stable categories land on the standing
rule ids — the contention refusal on `image.locked`, everything
unreadable on `drive.image-unreadable`, the layout disagreement on
`drive.volume-vanished`. The rule ids are Reliquary's (P27); the
categories are the dependency's evidence.

## The commit point moves into the dependency

The at-rest snapshot (`qemu-img snapshot`) and the staged raw copy
(D74) both existed to give a write something to stand on. Remanence
carries that inside: writes buffer until `commit()`, a durable undo
journal stands beneath the commit, and an interrupted commit is
reconciled at the next open — wholly the old image or wholly the
new one — which is D77's crash-recovery guarantee, delivered
upstream and verified below.

## What leaves, what stays

Leaves: `at_rest.py`'s reader internals (the MBR walker, the FAT
reader/writer, `LocalDevice`, `ImageLock`); `nbd.py` whole;
`backend_qemu.py`'s served access (the `qemu-nbd` lifecycle and the
at-rest snapshot commit point), staged raw access, and `qemu-nbd`
discovery; `open_drive` from the adapter protocol; the unit tests
of all of the above, whose subjects Remanence now owns.

Stays: the recognition claim (DOS-only FAT12/FAT16/FAT16B, D83) as
policy; the drive-report translation; the letter map (D78) and the
volume-vanished guard; the rule ids; the consumer-journey tests,
which must pass unchanged on the new path.

## The acceptance record

The pledge's gate was verified against the published wheel
(`remanence-0.0.1a2-cp310-abi3-win_amd64`, remanence-lib tag
`v0.0.1-alpha.2`) on the delivered Windows host (P11): backing
chains read and write with the base immutable, blank answers blank,
an unreadable partition carries its issue, one volume id is shared
by geometry and every file verb, and a torn recovery journal
reconciles at open with the image untouched.
