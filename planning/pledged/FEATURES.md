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

## F72 — A share's path and its model in one place

> **Entered 2026-08-30** by the owner, from using F69's `9p` model
> the day it landed. Serves **U14** and **U20** through F68's share
> device; the complaint is about that device's authoring surface,
> not about any mechanism underneath it. This proposal assumes an
> inline media stays legal on a share slot — settled by **D123**
> ([DECISIONS.md](../DECISIONS.md)), which struck T33 in favor of
> keeping the form and catching the docs up to it. Related to **F15**,
> which asks for a *command* that attaches a host directory; this asks
> for a shorter way to *write* one in a blueprint. Neither replaces
> the other.
>
> **Pledged 2026-08-30** (owner), the same day it was entered.
> Nothing was left open: the design already settles its own fix
> shape, and the two declined alternatives below are settled
> refusals, not open questions.

**When you declare a share, two facts usually matter — the host
directory, and the model — and today they cannot be written in the
same object.** This is a parse error:

```json
{"devices": {"share0": {"location": "D:/exchange", "model": "9p"}}}
```

```
error: unknown media field: devices.share0.model (field.unknown)
```

The cause is how `document._share_device` decides what kind of
object it is looking at. If the object's keys all fall inside
`{media, model, enabled}` it is a share-attribute object; otherwise
the whole object is re-read as an inline media spec, where `model`
is not a field. So `location` and `model` select different branches,
and adding the second one changes the meaning of the first.
`enabled` has the same problem for the same reason.

The consequence is that the compact form only works for a share
that accepts every default. The moment an author names a model, the
media has to be promoted to its own top-level component and the
device entry rewritten to point at it by name — one fact becomes two
components. That is the wrong direction: naming the model is the
*more* considered choice, and it costs more to write.

The shape of a fix, if this is pledged: **stop deciding the branch
by the whole object's shape.** Take `model` and `enabled` off the
object first, as share attributes that are always share attributes,
and hand every remaining key to the media parser. Then
`{location, model}` works, `{media, model}` keeps working unchanged,
and nothing that parses today changes meaning — a strict widening
rather than a redefinition. Media has no `model` field of its own,
so nothing collides.

DECLINED, and why:

- **A bare host path as the share's value** —
  `{"share0": "D:/exchange"}`. This is what an author reaches for
  first, and it is the shape least likely to work. A bare string in
  `devices` is a media name in every other slot, so this would make
  one string mean two different things depending on which slot it
  sits in, and telling them apart would be a rule about the shape of
  the text — does it contain a separator, is it absolute — rather
  than about anything the author declared. A media named `dist` and
  a directory named `dist` are both ordinary.
- **A `path` key on the share-attribute object** —
  `{"path": …, "model": …}`. This works and reads well. What it
  costs is a second way to say where a payload comes from, sitting
  next to `location`, which is the media model's only spelling for
  that fact today. The same objection killed a second spelling
  inside `backend-settings.qemu` (`backend_qemu.SETTINGS_KEYS`), and
  it would land harder here, because this is the device grammar
  rather than an escape hatch.

Work:

- `document.py`: rework `_share_device`'s dispatch so `model` and
  `enabled` are pulled off the object first, as share attributes
  independent of whatever else the object carries, and every
  remaining key is handed to the same media-parsing path a bare
  `media` reference or an inline spec already goes through — a
  strict widening, so every combination that parses today keeps its
  meaning.
- Tests: `{location, model}`, `{location, model, enabled}`, and the
  existing `{media, model, enabled}` all parse to the expected
  `MachineShare`; the two declined spellings above (a bare host
  path, a `path` key) stay refused.
- Docs: blueprint-model.md, blueprint-reference.md, and AGENTS.md's
  share value-form text — restated by D123 as three forms — notes
  that `model`/`enabled` now compose with the inline form too.

