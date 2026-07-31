<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Remanence as the at-rest disk module

> **Status:** proposed design for
> [F31](../FEATURES.md#f31--remanence-owns-at-rest-disk-access).
> It binds no work until the feature is pledged. Supports **U14**,
> **U20**; **P10**, **P11**, **P12**, **P16**, **P17**, **P21**.

## The proposal

Reliquary replaces its at-rest disk implementation with an exact
pin of the PyPI package `remanence`. Remanence becomes the deep
module behind one internal seam: it opens a raw or qcow2 image,
owns the image and backing-chain claims, reports complete disk
geometry, addresses the volumes it reported, reads or changes
files, and owns commit or rollback. Reliquary translates that
answer into its existing machine model and keeps every
world-facing policy.

The replacement is all-or-nothing. It deletes:

- the Reliquary NBD client and its wire-protocol tests;
- `qemu-nbd` discovery, process ownership, connection retries, and
  server diagnostics;
- the qcow2 internal-snapshot transaction;
- the staged-copy transaction for raw images;
- the local byte device and advisory image lock;
- the MBR/EBR and FAT12/FAT16 reader and writer.

What remains in Reliquary is policy and composition:

- the backend adapter opens the dependency and maps its errors;
- the machine layer enforces Reliquary's recognized DOS disk
  subset and renders the recorded drive report;
- `platform_dos` maps the reported volumes to guest letters;
- the file verbs translate guest addresses to a selected volume
  and translate their results back to the existing surface.

No Remanence type crosses S1 or S2. The dependency is an
implementation detail, not a second embedding surface.

## Why the seam moves upward

The current backend seam presents native images as byte-addressable
devices, and `at_rest.py` turns those bytes into partitions,
volumes, and files. That was the right seam while QEMU itself was
the format implementation: `qemu-nbd` supplied bytes and kept
qcow2 knowledge below the adapter.

Remanence already composes both halves. Stopping at its byte access
would leave two implementations of partition and FAT semantics and
make the new dependency carry less than the code it adds. The
deletion test decides the seam: if Remanence owns the high-level
disk interface, the MBR, FAT, allocation, transaction, and locking
complexity vanishes from Reliquary; if it owns only reads and
writes by offset, most of that complexity remains. P21 favors the
first.

The backend adapter remains a real seam because native image
formats vary by backend. Its at-rest member changes internally
from “present this image as bytes” to “open this image as a disk.”
The QEMU adapter answers with Remanence. A future adapter may answer
with Remanence once that package supports its native format, or
with another adapter to the same semantic interface. The machine
layer learns neither qcow2 nor a Remanence-specific format rule.

## The required Remanence interface

The exact Python spelling belongs to Remanence, but the release
Reliquary consumes must provide this semantic shape:

```python
with remanence.Disk(path, writable=False) as disk:
    geometry = disk.geometry()
    entry = disk.stat(volume_id, path)
    entries = disk.entries(volume_id, path)
    contents = disk.read_file(volume_id, path)

with remanence.Disk(path, writable=True) as disk:
    disk.make_directory(volume_id, path)
    disk.write_file(volume_id, path, contents)
    disk.commit()
```

Opening intent is explicit. A writable request never falls back to
read-only and fails before the first mutation when the write claim
cannot be obtained. A read request does not obtain stronger access
than it needs. Closing without `commit()` discards every mutation.

`stat()` returns a file or directory entry, or `None` when the path
does not exist. `entries()` lists one directory. `read_file()` and
`write_file()` address one file. `make_directory()` is recursive
and idempotent. Paths accept `/` or `\`, resolve DOS names
case-insensitively, ignore `.` components, and refuse `..`.

The binding may initially move file contents as `bytes`; that is
acceptable for the delivered DOS workflow. A streaming extension
is not part of F31 and must not be invented in Reliquary ahead of
demand.

## Geometry is complete, not permissive

`geometry()` returns the complete observation, including facts
Reliquary currently records:

- whether the disk is blank and whether it is partitioned;
- every primary, extended, and logical MBR entry;
- partition number, primary/logical kind, type byte and declared
  type, byte offset, and byte length;
- every recognized volume's stable id, filesystem kind, label,
  byte offset and length, cluster facts, heads, and
  sectors-per-track;
- cylinders where the disk states them or the format supports an
  exact derivation;
- a structured issue on any declared region Remanence cannot read.

An unsupported or unreadable partition is never silently omitted.
It remains in `partitions` with no volume and with an issue that
states why. This lets a general disk-analysis library report the
whole disk while Reliquary preserves its stricter policy: any
partition outside standard MBR primary/extended partitioning and
FAT12/FAT16/FAT16B makes at-rest access unavailable by name.
Remanence may support more filesystems for other consumers;
Reliquary does not broaden its claim by depending on them.

### Blank is an answer

When no partition table is present:

- an all-zero boot sector is a blank disk with zero volumes;
- a valid unpartitioned filesystem is one volume;
- non-zero data that is neither a supported filesystem nor a
  partition table is an unreadable image.

The first case is not an error. Reliquary creates blank disks and
DOS assigns them no letter until they hold a volume. The third case
stays distinct so corruption or a foreign format never becomes an
empty answer.

### One identity from geometry through file access

Every reported volume carries a stable identifier, and every
volume operation accepts that identifier. The invariant is:

> For one disk layout, a `VolumeInfo.id` names exactly the same
> region in `stat`, `entries`, `read_file`, `write_file`, and
> `make_directory` that it named in `geometry`.

The id may be a package-defined string such as `superfloppy:0`,
`partition:1`, or `logical:5`; callers treat it as opaque.
Filtering unreadable partitions must never renumber a later
volume. Reliquary records the id with the volume observation and
uses it when reopening the addressed drive. A missing id reports
`drive.volume-vanished` even when the new layout happens to contain
the same number of volumes.

## Image-format obligations

The consumed Remanence release must support the exact QEMU image
population Reliquary creates:

- raw images;
- qcow2 versions 2 and 3 as exercised by the delivered QEMU;
- standalone qcow2 images;
- qcow2 images backed by raw or qcow2 files;
- relative backing paths resolved from the containing image;
- multi-level backing chains with cycle detection and a bounded
  maximum depth;
- unallocated and zero clusters reading through to the backing
  image where the format requires it;
- compressed clusters on the read path where QEMU can produce
  them;
- copy-on-write allocation into the top image only.

A write never changes a backing file and never flattens the chain.
After commit, QEMU must still report the same backing relationship
and must read the changed guest bytes. Missing backing files,
cycles, unsupported feature bits, encryption, external data files,
and any untested format feature fail with structured errors rather
than partial interpretation.

Claims cover only cases tested against QEMU-authored fixtures on
the delivered Windows host. Remanence may support a wider qcow2
population, but Reliquary claims no wider population merely by
installing a newer library.

## Commit and recovery

D77's guarantee moves into Remanence without weakening:

- mutations are invisible to the image before `commit()`;
- closing or rolling back before commit leaves the image unchanged;
- commit preserves a qcow2 backing relationship;
- interruption during commit leaves recoverable state;
- the next open reconciles an interrupted commit before exposing
  the disk;
- after reconciliation the disk is wholly the old state or wholly
  the committed new state, never a partial third state.

The mechanism is Remanence's choice. A durable undo journal,
format-native transaction, or another tested implementation can
satisfy it. Reliquary does not prescribe an internal qcow2 snapshot
and does not recreate recovery above the dependency. Any recovery
artifact is private transient state: it introduces no stable S8
path, user-owned file, cleanup verb, or provenance contract.

Fault-injection tests terminate a separate process after each
durability boundary in commit and prove the next open reconciles
correctly. An in-process rollback test is not evidence for the
crash case.

## Claims and errors

The open disk holds its claims until close. Read claims coexist
where safe; a write claim excludes every read or write that could
observe a partial mutation. Every file in a backing chain is
claimed consistently, with the top image writable and backing
images immutable through this access. Contention is immediate,
never a hidden wait.

`RemanenceError` carries a stable machine-readable category in
addition to human text. The minimum categories are:

- `locked`;
- `invalid-image`;
- `unsupported`;
- `read-only`;
- `not-found`;
- `not-directory`;
- `is-directory`;
- `no-space`;
- `io`.

Reliquary maps categories to its existing `ReliquaryError`
taxonomy and rule ids. It never parses dependency message text,
never exposes a dependency exception, and never adopts a
dependency category as a new S7 identifier by accident.

## Reliquary integration

The delivery change:

1. Pins one exact Remanence release in `pyproject.toml` and the
   lock file. A range is not accepted while the dependency is
   prerelease and its disk interface is moving.
2. Changes the internal backend `open_drive` contract to return a
   semantic disk access rather than a byte device. The fake backend
   supplies the same interface without importing Remanence.
3. Makes the QEMU adapter construct the pinned `remanence.Disk` and
   translate open/claim errors.
4. Makes the machine layer translate complete geometry into the
   existing recorded drive report, enforce the DOS recognition
   subset, and use stable volume ids for file operations.
5. Deletes `at_rest.py`, `nbd.py`, both old access implementations
   in `backend_qemu.py`, and their implementation-specific tests.
6. Updates the internal backend design, AGENTS.md module map,
   descriptive documentation, and CHANGELOG. Normative
   specifications change only if review finds that they currently
   prescribe an implementation rather than the behavior retained
   here; a behavioral change returns through the surface rule.

There is no compatibility fallback. If Remanence refuses an image
inside Reliquary's current claim, the integration is incomplete;
it does not silently route that image through the retired NBD
implementation.

## Verification gates

Remanence must prove, through its public Python interface:

- blank raw and blank qcow2 disks report zero volumes;
- unpartitioned FAT12/FAT16 and partitioned FAT12/FAT16/FAT16B
  geometry;
- primary and logical partitions, including a later readable
  volume after an unreadable partition without identity drift;
- directory stat/list, nested reads, overwrite shorter and longer,
  recursive directory creation, free-space refusal, and both FAT
  copies kept consistent;
- raw and qcow2 rollback, commit, reopen, and lock contention;
- raw-backed, qcow2-backed, and multi-level qcow2 chains;
- backing-chain preservation after a write;
- crash recovery at every commit durability boundary;
- structured error categories for every refusal Reliquary maps.

Reliquary then runs:

- the existing at-rest geometry and FAT behavior suite through the
  backend seam, rewritten as contract tests rather than copied
  implementation tests;
- the drive-letter, recorded-geometry, refresh, and start-boundary
  tests;
- all five file verbs against raw, standalone qcow2, and
  differencing qcow2 images;
- real `qemu-img` fixtures for the format claims;
- the full local test suite and artifact build.

The release is not accepted merely because Remanence's own suite
passes. Reliquary's regression oracle proves that moving ownership
changed the implementation and not the application.

## Rejected cuts

**Remanence for qcow2, Reliquary for raw.** Rejected because
locking, transaction, and filesystem behavior would still vary by
format above the format seam.

**Remanence as a byte device, keeping `at_rest.py`.** Viable but
too shallow: it removes NBD and retains a second MBR/FAT
implementation beside the dependency's existing one. Reopen only
if Remanence declines to make geometry complete or volume identity
authoritative.

**A fallback to NBD for backing chains or unsupported qcow2
features.** Rejected because it preserves two authorities and lets
the dependency claim more integration than it earned. Missing
capability blocks the pin.

**String-matching dependency errors.** Rejected because wording is
not an interface and would make diagnostic correctness depend on a
message no Reliquary release controls.

**Pinning `0.0.1a1` now.** Rejected because it fails backing,
blank-disk, complete-geometry, stable-volume, and crash-recovery
gates that Reliquary already meets.
