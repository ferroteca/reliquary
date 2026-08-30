<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Pledged features

This file lists large capabilities that are **pledged but not yet
built**. Each entry carries the list of work that delivers it. A
feature gets added here by being moved out of
[proposed/FEATURES.md](../proposed/FEATURES.md). That move is what
makes it a pledge, and the git commit that makes the move is the
record of the pledge ([README.md](../README.md)). A feature leaves
this file either by being delivered, or by being **withdrawn** back
to that file, if it turns out nobody actually meant to commit to it
(D44; first used by D61).

This file is not a schedule. Numbered milestones stopped after
milestone 9, so nothing below has a queue position or a date. The
work items under each feature follow the same rules as
[TASKS.md](../TASKS.md) — they're just tasks. They're listed under
their feature instead of in that task queue because they don't make
sense on their own, apart from the feature.

Each feature carries an **F-number** and must fit in **one sprint**
(D42; the rules are in [README.md](../README.md)). If a feature is
too large, it gets split up when it's pledged: the original
F-number is retired, and each resulting piece gets its own new
F-number.

**F-numbers come from the sequence ledger**
([SEQUENCES.md](../SEQUENCES.md); owner, 2026-07-31). When a feature
is added — whether it's first drafted in
[proposed/FEATURES.md](../proposed/FEATURES.md) or added straight to
this file as a pledge — take the next number from that ledger and
update the ledger in the same edit.

## F68 — The `share` device kind, and the vvfat fold

The blueprint gains `share<n>` slots in `devices`: a host directory
presented to the guest for file exchange. The existing vvfat
directory-drive folds in as this device kind's one snapshot model,
and directory payloads stop being legal on drive slots. Design,
argument, and every rejected alternative:
[design/share-devices.md](design/share-devices.md) (owner rounds,
2026-08-29). Demand rests on in-force U14/U20 (D65); pledged
straight to this file (owner, 2026-08-29).

After this feature alone, `vvfat` is the only model any backend
serves — an unstated-model share is refused by name everywhere
until F69/F71 land. That interim state is honest (P11) and named
here so nobody reads it as a bug.

Work:

- `document.py`: `share` joins the devices-key grammar (D121's
  clash check covers it by construction); value forms (media name,
  inline media, `{media, model, enabled}` — no `null`); `model`
  vocabulary `vvfat`/`9p`/`virtio-fs`; share keys refused in
  `boot`; directory payloads legal only on share slots — a drive
  slot whose media resolves to a directory fails closed, and the
  old cdrom carve-out dissolves into that rule.
- `backends.py`: share capability and requirement fields with the
  usual `unmet()` math; `Capabilities.vvfat` retires into them.
- `backend_qemu.py`: the vvfat rendering moves out of `drive_args`
  into the share renderer, disk-shaped only.
- `machines.py` / state: share entries in the merged `devices` map,
  discriminated by shape; `apply_blueprint` absorbs share changes
  on a stopped machine; inserting a directory media becomes a named
  refusal.
- Specs and content: blueprint-model.md and the JSON schema;
  media-spec.md's directory-payload section re-homes onto shares;
  USE-CASES.md's U25 journey respells its drive step as a share;
  the freedos-dump-font codex script's vvfat comment; AGENTS.md's
  D108 "two routes" sentence rewords its first route.
- Tests: `fake_backend.py`'s capability claim and
  `test_backend_qemu.py`'s vvfat render coverage move with the
  mechanism.

## F69 — QEMU virtio-9p shares

QEMU serves a share over virtio-9p, and becomes able to honor an
unstated `model` (its default live mechanism is 9p — never vvfat,
per the design doc's declined list). Needs F68 delivered first.
Design: [design/share-devices.md](design/share-devices.md).

Work:

- A per-installation probe of the selected QEMU binary — fsdev/9p
  is a build option the official Windows binaries lack, so the
  capability report says what the probe found, never what the
  adapter's code implements (P11). On a Windows host this needs the
  maintainer's `windows-fs-raw` QEMU tree via `RELIQUARY_QEMU_HOME`
  (build recipe in virtio-dos's `docs/TESTING.md`).
- Rendering: `-fsdev local` plus `virtio-9p-pci`, `mount_tag` =
  slot key, the media's `read-only` mapped to the fsdev option.
- `RESERVED_ARGUMENTS` grows the fsdev family.

## F70 — QEMU virtio-fs shares

QEMU serves a share over virtio-fs, chosen by `model: virtio-fs`.
Needs F68 delivered first. Design:
[design/share-devices.md](design/share-devices.md).

Work:

- The probe: `vhost-user-fs-pci` in the selected binary (its own
  build option) plus a `virtiofsd` binary — upstream ships one for
  Linux only; on Windows the maintainer's prototype
  (`D:\Projects\virtiofsd`, branch `windows-raw`) is what exists.
- One `virtiofsd` per share: started before the machine, supervised
  while it runs, stopped after; its death mid-run is a named
  failure.
- The vhost-user socket (a named-object transport on Windows, per
  the prototype) and the shared-memory backend, which must agree
  with the blueprint's own `memory` — the coupling that puts this
  work in the adapter rather than the `backend-settings` escape
  hatch.

## F71 — VirtualBox shared folders

VirtualBox serves a share over its own shared-folder protocol.
Needs F68 delivered first. Design:
[design/share-devices.md](design/share-devices.md).

Work:

- `VBoxManage sharedfolder add` at materialization and `remove` at
  disposal; share name = slot key; the media's `read-only` mapped
  to `--readonly`.
- Capability: serves an unstated-model share (its only mechanism);
  every authored model is refused by name, the same way `ne2k`
  already is on this backend.

