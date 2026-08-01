<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Pledged architecture — awaiting delivery

> **Status:** principles the project has **pledged** but does not
> yet honor. Nothing here is in force: a principle only binds once
> it reaches the standing list, and a shortfall against an entry
> below is unbuilt work rather than a bug.
>
> That distinction is the point of this file. **Promotion is what
> arms a principle**: before it, an entry is pledged vision; after
> it, root [ARCHITECTURE.md](../../ARCHITECTURE.md) asserts the thing is
> true of the code, so a divergence becomes a *defect* the
> gap-is-a-bug rule can act on — that rule being stated in the
> root document's own banner (D48).
>
> Three locations hold three states. A principle is drafted in
> [proposed/ARCHITECTURE.md](../proposed/ARCHITECTURE.md), moves here
> when it is pledged, and moves to the root list when the code
> actually honors it. All three share one global P-namespace;
> numbers are permanent, never reused, and no placeholder is left
> behind by either move.
>
> The second move is **automatic on full delivery** (D34): whoever
> lands the work that makes the code honor a principle promotes it
> in the same change — adds it to the standing list, deletes it
> here — rather than holding it for a separate sign-off; the moving
> commit is the record, and no [DECISIONS.md](../DECISIONS.md) entry
> marks a promotion (D63). **A principle's bar is
> *honored as a rule*, not full delivery** (D48): it cannot be
> exhaustively proven, and holding it here until it is perfect
> keeps every shortfall invisible, which is the worse outcome.
> The condition is that every known residue is filed as a defect
> in the same change — that conversion being the whole point of
> arming it. (Full delivery remains the bar for a *use case*,
> which is a discrete journey and can be tested end to end.)
>
> A principle in force is clarified, retired, or superseded — never
> changed in nature. One pledged here may still be reshaped, its
> number intact, with work already scheduled against it re-checked
> in the same edit. A dead proposal is recorded in
> [DECISIONS.md](../DECISIONS.md) and triggers the planning-doc sweep,
> its P-number the search key.

- **P27 — Remanence owns at-rest disk access.** Direct disk-image
  access belongs to Remanence, not to Reliquary. Reliquary consumes
  Remanence as the one deep module for opening raw and qcow2 drive
  images at rest, claiming the image and any backing chain,
  discovering complete partition and volume geometry, reading and
  changing files in FAT volumes, and committing or rolling back
  mutations. Reliquary keeps the policy Remanence cannot own: the
  DOS-only FAT12/FAT16/FAT16B recognition claim, guest-address
  mapping, rule ids, and translation into the recorded drive report.
  The dependency earns the whole layer or none of it: a hybrid that
  keeps Reliquary's NBD client, `qemu-nbd` lifecycle, qcow2 snapshot
  orchestration, staged raw access, MBR reader, or FAT reader/writer
  as a fallback is refused, because it leaves two authorities for
  the same disk facts (P21; D83). D73's refusal to write and
  maintain a qcow2 reader inside Reliquary is honored by making the
  format implementation a declared dependency (D82), and D77's
  guarantees remain binding: an image is opened where it lies, a
  backing relationship survives a write, work is proportional to
  touched data, contention fails by name, and an interrupted write
  is reconciled on the next access. This principle is pledged, not
  armed: the pinned candidate is `remanence==0.0.1a2`, which meets
  the acceptance gate this pledge set — backing chains compose for
  reading and writing with every backing file claimed immutable, a
  blank newly materialized disk is an answer rather than an error,
  a partition that cannot be read stays in `geometry()` carrying
  its issue, one stable volume identity is shared by geometry and
  every file verb, and an interrupted commit is reconciled on the
  next open, which is D77's crash-recovery guarantee — verified
  against the published wheel on the delivered Windows host (P11).
  That exact release is pinned; a different release is a fresh
  verification, never a substitution.
