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

**F-numbers are issued against the sequence ledger**
([SEQUENCES.md](../SEQUENCES.md); owner, 2026-07-31): take the
next mark there and advance it in the same edit, by whichever
door the entry arrives — drafted in
[proposed/FEATURES.md](../proposed/FEATURES.md), or cut straight
to this file on pledge.

## F41 — The drive-determination handover

> **Pledged 2026-08-03** (owner), with the **P27** keeps-clause
> amendment ([ARCHITECTURE.md](ARCHITECTURE.md)). Entered
> 2026-08-01 from the owner's direction after F40 landed: an
> inventory of what the at-rest translation still holds that
> Remanence could own, written whole so the upstream ask and the
> downstream consequences are argued from one document. Serves
> **U14** and **U20** through **P10**, **P11**, **P16** and
> **P17**; extends in-force **P27**'s one-deep-module logic the
> rest of the way down. Its delivery lands the **P27 amendment**
> and reopens **D83**'s report semantics under the surface rule.
> The gate mirrors the one P27's own pledge carried: a Remanence
> release satisfying the acceptance conditions below on the
> delivered Windows host, pinned exact — a different release is a
> fresh verification, never a substitution.

**What Reliquary still holds today**, each with its current home —
the complete inventory this feature would retire, two of them
struck already where the `0.0.1a3` pin retired them on its own:

1. **The recognition claim's enforcement.** `at_rest.py` pins the
   partition-type vocabulary value by value — `_FAT_TYPES`,
   `_EXTENDED`, `_KNOWN_FOREIGN` — and `_describe` composes the
   refusals ("partition 2 holds NTFS or exFAT, and reliquary's DOS
   workflow reads FAT12 and FAT16 partitions and DOS extended
   containers only").
2. **The whole-disk-or-none rule.** A partition row Remanence
   reports with an issue refuses the entire disk, on the ordering
   argument in-force P27 records — an argument Remanence's
   pledged **F38** dissolves outright ("an unreadable region retains
   its identity and position, so a failure cannot renumber objects
   which follow it").
3. ~~**Sector-0 classification.**~~ Retired at the `0.0.1a3` pin:
   the `partitioned` flag was derived locally — `bool(partitions)
   or (not blank and not volumes)` — and is now the scheme the
   dependency classified, read rather than reconstructed. Which
   outcomes reliquary accepts stays here, as "what stays
   regardless" below has it.
4. **Disk-level `cylinders` selection.** The record's value is the
   first volume's BPB answer, chosen by reliquary rather than
   stated by the report.
5. **Positional volume identity.** The letter map and drive record
   store volume *indexes*; the index is resolved to Remanence's id
   at open, and the volume-vanished guard compares counts rather
   than identities.
6. ~~**Label policy.**~~ Retired at the `0.0.1a3` pin: the "NO
   NAME"-reads-as-unlabeled rule was applied here and the
   BPB-label fallback was root P27's residue. The dependency reads
   both now, and `volume_label()` passes its answer on.
7. **Guest-name policy.** `_validated_short_name` and `_ILLEGAL`
   enforce 8.3 validity with named reasons, and segments are
   uppercased here because Remanence's matching is exact.
8. **The letter algorithm.** `platform_dos.drive_letters` assigns
   A:/B: by floppy slot and C: onward one letter per volume across
   disks — DOS's own assignment, reimplemented host-side.

**The upstream contract, and where the pin leaves it.** The
inventory below was written against the pinned Remanence
`0.0.1a2`, from which none of the eight capabilities was
available; five were named by Remanence's pledged **F38** / **F39**
(cut from proposed F20 on pledge) and three were only proposed
(**F24**, **F25**, **F26**). **All eight are blocking**, and P27's
no-hybrid rule permits no local fallback for a capability a partial
upstream delivery omits.

The pin moved to **`0.0.1a3`** on 2026-08-12, and each of the eight
was exercised against that release on the delivered Windows host
while the at-rest layer was rewritten onto it. Seven answer — the
notes under each say what was observed; ask 8's answer did not
survive review, and the note under it records the restatement of
2026-08-13. **That is an API
observation and not this feature's gate**: the gate asks for a
release verified against P27's guarantees, and delivery is a
surface change (S1, S7 — the drive record and the letter map) that
triages under the surface rule before any of the inventory above
leaves. Both remain the owner's, and the eight stand as written
until they land.

Named by Remanence's pledged F38 / F39:

1. **Stable region and volume identities, end to end.** Every
   discovered region and readable volume carries an identity which
   the geometry report and file-access calls share. An unreadable
   region retains its identity and position, so it cannot renumber
   anything after it. A later access names the volume by that
   identity; disappearance is an identity miss, not a changed-count
   inference. This retires positional volume identity and supplies
   the premise on which partial reads are safe. (F38 issues the
   identities; F39 makes the file verbs select by them and retires
   `DiskGeometry` / `geometry()`.)

   *Observed in `0.0.1a3`:* regions, volumes and filesystems each
   carry an id, the inspection report is keyed by them, and content
   is reached through the partition holding the identity rather than
   by position. `DiskGeometry` / `geometry()` are gone.
2. **Sector 0 classified by the disk seam.** The report distinguishes
   four outcomes directly: blank; a partition schema containing no
   volumes; a direct, unpartitioned volume; and unknown nonblank
   content. Reliquary must not reconstruct those states from
   `partitions`, `blank`, and `volumes` combinations. (F38.)

   *Observed in `0.0.1a3`:* `DiskReport.content` answers exactly
   those four — `"blank"`, `"schema"`, `"direct-volume"`,
   `"unknown-nonblank"` — with `content_evidence` on the last.
   `at_rest.py` reads it directly and derives nothing.
3. **Filesystem-declared geometry kept at the filesystem seam.** A
   volume reports the geometry its filesystem declares, unanswered
   where it declares none. The disk report must leave Reliquary no
   reason to select the first volume's BPB answer as a synthesized
   disk-level `cylinders` value. (F38.)

   *Observed in `0.0.1a3`:* the BPB's words are the filesystem's
   (`FilesystemInfo.cylinders` / `.heads` / `.sectors_per_track`),
   and the medium answers its own discovered `Geometry` with the
   readings behind it. The disk-level selection is still made here,
   which is this feature's work rather than a gap upstream.
4. **A partial-read report.** Failure to interpret one region is an
   issue on that region, not failure of the disk report. Regions and
   volumes which can be read remain present with their stable
   identities, including those after the issue, so the consumer can
   place and use everything whose identity and position are known.
   (F38.)

   *Observed in `0.0.1a3`:* a disk whose first row is `0x83` reports
   that row with its issue and its category, and row 2 keeps its
   ordinal, its identity and its readable content.
5. **Declared-type readings fit for a user-facing refusal.** Every
   partition or region reports both its raw declaration and a
   description Reliquary can quote without maintaining its own type
   table. A kind tag alone is insufficient: type byte `0x07` must
   yield "NTFS or exFAT", and `0xEE` must yield "a GPT protective
   partition — this disk is GPT, not MBR". (F38 commits to readings
   fit to quote in a user-facing refusal.)

   *Observed in `0.0.1a3`:* `Partition.type_byte` beside
   `type_reading`, which answers "NTFS or exFAT" for `0x07` and
   "that the whole disk is GPT rather than MBR, this entry being the
   protective placeholder GPT writes" for `0xEE` — the sense asked
   for, in the dependency's own wording, and `0x3C` reads as "no
   type this release has a reading for" rather than as nothing.

Proposed upstream when this was written (F24 / F25 / F26):

6. **FAT label semantics owned at the filesystem seam.** The FAT
   answer treats `NO NAME` as the format's spelling of unlabeled and
   therefore absent. It carries the boot-record label as evidence
   beside the root-directory label, so Reliquary neither reads a
   sector nor recreates the fallback policy.

   *Observed in `0.0.1a3`:* `VolumeLabel` answers the name whole
   with both readings — root-directory entry and boot-record field —
   and `answered_by` naming which one spoke; `NO NAME` is stored
   evidence and an absent name. Taken as the answer here already:
   the local rule is gone.
7. **DOS short-name semantics owned at the file-access seam.** Reads
   match case-insensitively and return the stored short name; writes
   validate and normalize at that same seam. A name outside DOS 8.3
   is refused with the particular rule it broke, never generically
   rejected, silently truncated, or repaired by caller-side
   uppercasing. Reliquary keeps only guest-address parsing
   (`A:\OUT\X.TXT` into a letter and segments) and rule-id
   restatement.

   *Observed in `0.0.1a3`:* a write names the rule it broke —
   separators, base length, extension length, excluded character —
   and `lower.txt` lands as `LOWER.TXT`; reads match case
   insensitively and answer with the stored short name.
8. **A DOS namespace composer which produces the mapping.** Given
   the machine facts Reliquary owns — medium, slot, and authoritative
   attachment order — plus the composed volumes and their stable
   identities, Remanence returns the DOS namespace: `A:`/`B:` for
   floppy slots, hard-disk volumes from `C:` onward, then CD-ROMs.
   It returns only mappings it can establish and identifies what
   remains undetermined when ordering or a disk outcome is
   insufficient. Its answers name stable volume identities, not
   positional indexes. This goes beyond Remanence P19's current
   wording, which consumes an explicit drive mapping rather than
   producing one; which image occupies each slot remains the
   machine model's fact. (Needs Remanence F38 delivered.)

   *Observed in `0.0.1a3`:* `Machine.compose_dos_letters()` returns
   a `DriveMap` over the machine's own device set — mappings naming
   volume identities, an `undetermined` outcome carrying the reason,
   and provenance stating the rules applied. It goes further than
   the ask: the assignment rules are per DOS variant (`ms-dos-4`,
   `ms-dos-5`), and where an unstated variant leaves them
   disagreeing the letter is undetermined rather than chosen.

   *Restated 2026-08-13, and not available.* The per-variant rules
   are this capability's defect rather than its surplus. The
   composer takes the DOS variant and every resident condition
   (`LASTDRIVE`, `SUBST`, `JOIN`, `ASSIGN`, a block-device driver, a
   network redirector) as caller assertions, though each is evidence
   on a volume it already reads — the boot volume's kernel and
   `COMMAND.COM` for the version, `CONFIG.SYS` and `AUTOEXEC.BAT`
   for the conditions — and it derives no boot device at all. So the
   ask is restated: reliquary states the machine it already holds —
   devices, their slots and attachment order, and the media in them
   — and the composer derives which device boots, the DOS booting
   from it, the conditions that DOS declared, and the letters. It
   takes a boot-order override only because an emulated machine's
   order is its host's (`boot`, `set-boot-order`), and that belongs
   on the machine model rather than on this call. Note also that no
   claimed rule names FreeDOS, which is the DOS the shipped codex
   runs. Raised upstream as remanence **T7**: until it lands this
   capability is unavailable and ask 8 is unmet, so the eight stand
   blocking exactly as written.

The upstream API's spelling is Remanence's design choice. The gate
is observable: a released API must make each answer above available
without Reliquary reading disk structures, reproducing filesystem
or DOS policy, or translating through a second local model.

**What leaves on delivery**: the type tables and `_describe`; the
whole-disk refusal loop; the `cylinders` derivation;
`_validated_short_name`, `_ILLEGAL`, and the
uppercasing; the letter algorithm; positional
identity everywhere — the letter map and drive record store
Remanence's identities, and the volume-vanished guard becomes an
identity miss answered by name.

**What stays regardless**: the rule ids and the error-category
mapping (`UnreadableImage` / `ImageLocked` onto
`drive.image-unreadable` / `image.locked`); the recorded report's
serialization and its read-at lifecycle (D83); the machine model's
own facts — slots, stopped-only access, operation locks; and the
decision to run under the DOS claim at all, expressed as which
report outcomes reliquary accepts rather than as re-derived facts.

**The two amendments this pledge weighs**:
in-force **P27's "Reliquary keeps" clause shrinks** to
guest-address parsing, rule ids, and the recorded report — the
amendment beside this file; and **D83's report gains partial
reads** — a disk with an unreadable partition records the readable
volumes beside the issue-carrying row instead of one unread
refusal, and the letter map places what is placeable — a surface
change for the vetting rule, weighed at this pledge rather than
discovered at delivery.
