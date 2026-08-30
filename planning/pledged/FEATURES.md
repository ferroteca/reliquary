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


