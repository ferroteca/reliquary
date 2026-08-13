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

## F60 — The remaining suites are pytest-native

> **Pledged 2026-08-13** (owner), cut straight to this file by
> **D106**. Demanded by **P11** on D106's reading. Needs **F55**
> delivered first; no order binds it against F56–F59. Assumes
> **D105**'s catalogue move has landed, since two of these modules
> read it.

The tail: twenty small modules and roughly 470 tests — the CLI and
document surface, the core helpers, the home and asset machinery,
the media path, and the guards. Nothing here is architecturally
interesting, and that is the point: it is what stands between a
mostly-converted suite and an idiom policy with no exceptions.

Work items:

1. Convert the surface modules — `test_cli`, `test_document`,
   `test_documented_examples`, `test_command_manifest`,
   `test_old_surface_purge`, `test_errors`.
2. Convert the core and resource modules — `test_core`,
   `test_binding`, `test_home`, `test_assets`, `test_resolve`,
   `test_library`, `test_media`, `test_acquire`,
   `test_credentials`, `test_json5reader`, `test_transcript`,
   `test_authoring`, `test_facts`,
   `test_external_effect_guards`.
3. The document-globbing tests read the script-example catalogue at
   its `docs/` home, which is where D105 put it.
4. Same assertions and the same collected count as the run before
   the conversion. The suite is pytest-native throughout, and the
   idiom policy F55 wrote has nothing left to exempt.

## F59 — The machine and backend suites are pytest-native

> **Pledged 2026-08-13** (owner), cut straight to this file by
> **D106**. Demanded by **P11** on D106's reading. Needs **F55**
> delivered first; no order binds it against the other sweeps.

Ten modules and roughly 460 tests, `test_machines` alone carrying
182 of them. This is the cluster that builds things — temp homes,
stub backends, machine state — so it is where fixtures earn their
keep rather than merely replacing `setUp`.

Work items:

1. The shared construction becomes fixtures: the temp home, the
   stub backend, the machine under test — each scoped so an
   expensive one is built once rather than per method.
2. Convert `test_machines`, `test_session`, `test_events`,
   `test_properties`.
3. Convert `test_backend_qemu`, `test_backend_virtualbox`,
   `test_backends`, `test_at_rest`, `test_screen_stability`,
   `test_text_recognize`.
4. The two backends' shared expectations become **one parametrised
   contract over the adapter seam** instead of paired near-identical
   methods, so a seam requirement cannot be honored by one backend's
   test and quietly missing from the other's (**P25**).
5. Same assertions and the same collected count as the run before
   the conversion.

## F58 — The script-language suite is pytest-native

> **Pledged 2026-08-13** (owner), cut straight to this file by
> **D106**. Demanded by **P11** on D106's reading. Needs **F55**
> delivered first; no order binds it against the other sweeps.

Eight modules and roughly 360 tests — the largest single cluster,
and the one where parametrisation pays past the conversion itself.
The static validation rules are a table pretending to be a method
list, and the script corpus is a directory pretending to be one.

Work items:

1. Convert `test_script_runner`, `test_script_validation`,
   `test_script_parser`, `test_script_nodes`, `test_script_timing`,
   `test_run_script`, `test_dry_run`.
2. **The V-rules become parametrised over the rule table** rather
   than a method per rule, so a rule added to the language without a
   test is visible as a missing case instead of an absence nobody
   counts.
3. `test_script_corpus` reads through the parametrisation helper
   F56 builds, rather than growing a second one.
4. Same assertions and the same collected count as the run before
   the conversion.

## F57 — The integration tier is a marker, not a skip

> **Pledged 2026-08-13** (owner), cut straight to this file by
> **D106**, whose argument about skips this is. Demanded by
> **P11**. Needs **F55** delivered first.

Two FreeDOS runs are gated by `RELIQUARY_INTEGRATION` and a
`skipUnless`, and AGENTS.md asserts the suite skips **exactly two**
tests — a count that exists precisely because a skip cannot say
whether it was chosen or suffered. A marker says which, and the
count stops standing in for it.

Work items:

1. `@pytest.mark.integration` on the QEMU and VirtualBox runs,
   deselected by default and selected by an explicit option.
2. `RELIQUARY_INTEGRATION` retires as the gate.
   `RELIQUARY_INTEGRATION_HOME` stays and becomes a fixture input
   rather than an environment read at module scope.
3. The AGENTS.md skip rule rewrites against what the marker makes
   true: **zero** skips in the default run, the tier deselected
   rather than skipped, and any surviving skip a defect as before.
4. The integration command blocks in AGENTS.md fold to the marker
   selection.

## F56 — The conformance corpus is parametrised

> **Pledged 2026-08-13** (owner), cut straight to this file by
> **D106**, whose whole argument this is. Demanded by **P11**. Needs
> **F55** delivered first.

The corpus claims the parser and the schema cannot drift. It once
ran against the parser and **not** the schema and nothing said so,
because 135 fixtures across two checks inside `subTest` is a run
whose halved form looks exactly like its whole one. Parametrised,
the fixtures are collected nodes and the count is the assertion.

Work items:

1. Every fixture becomes a collected node named for its file,
   across both the parser check and the schema check.
2. **The collected count is asserted**, so a corpus that stops
   loading fails rather than passing quietly.
3. The blueprint, machine-state and script corpora read through
   **one** parametrisation helper, not three — the helper F58's
   corpus item also uses.
4. The corpus READMEs say what a fixture's node is called, since
   selecting one by name is now how a failing fixture is debugged.

## F54 — The scoped machine-state change

> **Pledged 2026-08-13** (owner), cut straight to this file in the
> act that pledged **U24** and **U26**, whose whole delivery it is —
> the promotion of both to root [USE-CASES.md](../../USE-CASES.md)
> rides with it (D34), neither being met until it lands. U24 asks
> that a stage state what it boots; U26 asks that what a run
> arranged come off when the run ends, which is the same mechanism
> seen from the retry. Weighed against **P14**, which is what
> makes a new construct expensive, and **P25**, which both backends
> already satisfy since the vocabulary is Reliquary's own state and
> not a backend's. The spelling and the restore rule, with the
> alternatives they beat: **D104**. Reads better after **T27**,
> whose reachability analysis the exit check below reuses.

A script's `insert`, `eject` and `set-boot` change the machine
durably and leave it changed; the author writes the undo by hand, in
a place no failure path reaches. This gives the change a scope, and
the scope undoes it.

**The construct.** A `with` block whose head names the change:

```rlqs
with boot cdrom0 {
    phase startup { ... }
    phase cd-boot { ... }
}
```

- **The head vocabulary is `boot`, `insert` and `eject`.** The last
  two are the existing verbs written exactly as they are written
  today. The first is **not** `set-boot`, and the difference is the
  point: `set-boot` *replaces* the order, while what a stage wants
  to say is "boot the CD first" — the real shape of the demand, and
  the author should not have to restate an order they are not
  changing. **`boot` states a prefix**: the drives named come first
  in the order given, and the machine's own order follows for
  everything else, so `with boot cdrom0` over a machine ordered
  `["hdd0", "cdrom0"]` boots `["cdrom0", "hdd0"]`. Naming more than
  one pins a longer prefix, for the author who wants it. Every key
  must name a declared drive, as `set-boot`'s do, and `set-boot`
  itself is untouched — replacement is still what that verb means,
  and giving one spelling two meanings was the alternative (D104).
- **It wraps the enclosing shape's own units** — phases in a phased
  script, statements in a linear one. That is what gives the
  language a word for a *stage*: a group of phases. It is also the
  only form in which an install is expressible, since its stage
  spans phases and every phase body ends in a transition.
- **The scope is where control is, not where the text is.** It holds
  while control is inside the group, is entered by reaching any
  phase in it — including by `goto` from outside — and is left by
  reaching a phase outside it or by the run ending. Re-entry
  re-applies. A purely lexical reading was declined (D104): every
  phase body ends in `goto`, so it would revert at the first
  transition and express nothing.
- **On exit the target returns to the value it held on entry**, on
  every outcome the runner reaches: `finish`, a failure, and a
  cancellation at a boundary. A host crash restores nothing and
  `apply` remains its recovery, exactly as today.
- **A boot restore requires a stopped machine** (D104). An exit
  reached with the machine running fails the run, naming the change
  it could not undo; where a static pass can promise that exit is
  reached running, it is an authoring refusal instead (T27). Media
  restores carry no such rule — `insert`/`eject` are
  running-or-stopped, so the restore is live where the machine is up.
- **One scope per target.** Two scopes on the same target, nested or
  overlapping, are refused; scopes on different targets nest freely.

Work items:

1. The grammar and the typed tree: the `with` block in
   `script_grammar.lark` and `script_parser.py`, both shapes, the
   `insert` / `eject` heads reusing those actions' signatures rather
   than restating them, and `boot` as a head-only node taking one
   slot key or more.
2. Validation and preflight: the head vocabulary (closed at three
   names, V14's kind), which units a block may wrap in each shape
   (V2's kind), the doubled-scope refusal, and `boot` keys — unique
   by slot, canonical or alias — checked against the machine's
   declared drives where `set-boot`'s already are. New ids where the existing rules do not stretch; no new
   V-number is expected, and one is issued against
   [SEQUENCES.md](../SEQUENCES.md) if that turns out wrong.
3. The runtime: scope entry and exit in `script_runner.py`'s
   dispatch — capture on entry, restore on every exit and every
   terminal outcome, with the stopped-machine rule on boot restores
   and its run failure.
4. The run's output: entry and restore are reported on the event
   stream (P5), and the failure report names a restore it performed.
   What the author gave up by scoping is the state a diagnostician
   would have found, so the run has to say what it took back.
5. The spec: `docs/spec/script-spec.md` — the grammar, a section
   beside `insert`/`eject`/`set-boot`, the "persists for diagnosis"
   paragraph amended to say what a scope changes, and a line in "How
   the vocabulary grows" recording that this is a construct and was
   argued as one.
6. The corpus: valid fixtures for each verb under both shapes;
   invalid fixtures for a foreign head, a doubled scope, and a boot
   restore provably reached running — each declaring the id that
   must reject it.
7. The codex and the example: `freedos.rlqb` returns to
   `["hdd0", "cdrom0"]`, `freedos-install.rlqs` wraps its phases in
   `with boot cdrom0` and keeps its mid-install `eject`,
   and the spec's FreeDOS example follows the codex as it must.
8. The references: `docs/cli-reference.md` is untouched — a scope is
   syntax and not a capability, so P6 parity has nothing to add —
   and the script guide and reference gain the construct.

**The sprint bound** (D42) is tight here and was weighed at the
pledge rather than discovered. If it breaks, the cut is the linear
form: no shipped script needs a statement-level scope, and U24 names
no script shape, so the phased form alone still delivers it.

## F43 — The interpretation-layer corpus

> **Pledged 2026-08-01** (owner), cut from F13 with F42, that
> number retiring with the split (D42). Demanded by **P22** and
> **P24** — a surface that genuinely cannot be tested names the gap
> rather than being quietly exempted, and this closes the largest
> one. Needs **F42** delivered first. Design:
> [design/screen-transcripts.md](design/screen-transcripts.md).

The third conformance corpus, and the one whose fixtures nobody can
author: the blueprint and script corpora are written, and this one
is only ever captured.

Work items:

1. The harness: run the interpretation layer against a `.rlqt`
   fixture — the fixture directory, the loader, and the assertion
   vocabulary.
2. The first captures, taken under the opt-in integration run
   against real QEMU: the FreeDOS install path and the verify
   script.
3. The pathological captures — the boots where prompt detection or
   command-echo scanning misbehaves, each becoming a regression
   fixture.
4. The corpus README, as the blueprint and script corpora each
   carry: where its findings live.
5. The suite discipline: fixtures reconstruct with no QEMU present,
   so they run in the **default** suite, and a failing capture is a
   defect to fix rather than a skip to tolerate.

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
while the at-rest layer was rewritten onto it. Every one answers —
the notes under each say what was observed. **That is an API
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
