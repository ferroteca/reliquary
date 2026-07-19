<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# The machine spec

> **Status:** this documents the planned machine spec format. The
> machine model is not implemented yet; details may still change
> before first release.

Every reliquary machine is described by two documents in the
**same format** serving different purposes — a declaration you
write, and a state document reliquary derives from it:

```text
<reliquary_home>/machines/
└── msdos.json               the declaration — yours
<reliquary_home>/cache/machines/msdos/
├── reliquary.json           the state — reliquary's
├── drives/                  the machine's disk and floppy images
├── screenshots/             captured screens (transient)
└── ...                      backend files and logs
```

- The **declaration** (`machines/<name>.json`) is the machine as
  you defined it. You own it: reliquary reads it and never writes
  it.
- The **state** (`cache/machines/<name>/reliquary.json`) is the
  machine as it actually is right now, at the root of the
  machine's **cached instantiation** — the directory holding
  everything reliquary materialized for the machine: state, disk
  images, screenshots, backend files. reliquary owns all of it;
  you never need to touch it. Screenshots in particular are
  transient diagnostics with no retention promise — copy out any
  capture you want to keep, promptly.

The split reflects what reliquary machines are for: **ephemeral
work**. A reliquary machine is a disposable rig — created to run a
scripted OS install or an automated task, recreated freely, and
deleted when done. The declaration makes rebuilding cheap; the
entire cached instantiation is safe to throw away, because
everything in it regenerates from declarations, media definitions,
and scripts. The machine is never the product — often nothing
durable comes out at all (the point was to run some tests); when
there is interest in something more durable, `export` it — either
a media image (a disk image taken out of the machine) or the
entire machine, handed to a hypervisor built for long-lived
machines. reliquary is not the place to keep a machine you care
about.

The same line runs through the whole reliquary home: everything
outside `cache/` is a document you authored — machine
declarations, media definitions, scripts — small, shareable, and
worth versioning; everything under `cache/` is reliquary's and
reconstructible. There is no dropping of pre-created files into
cache directories; inputs enter machines through the declaration —
`media:` references and [starting-point
images](machine-spec-reference.md#base--optional--string) that are
copied or used as bases of differencing disks.

This page explains the format and how the two documents behave
through a machine's life. Companion pages:

- **[Field reference](machine-spec-reference.md)** — every field,
  every rule.
- **[Cookbook](machine-spec-cookbook.md)** — complete worked
  examples.
- **[The media spec](media-spec.md)** — the shared media library
  that `media:` drive sources reference.

## What the spec format is

**It is backend-agnostic.** The same declaration can describe a
machine on any supported virtualization backend — QEMU,
VirtualBox, VMware Workstation, or Hyper-V. Nothing in the core
format is a QEMU option or a VirtualBox setting in disguise. The
one deliberate exception is the
[`backend-settings`](machine-spec-reference.md#backend-settings)
field, an explicitly scoped escape hatch; a declaration that
doesn't use it is portable by construction.

**Declaration and state are the same format.** Every field valid
in a declaration is valid in the state document, with the same
meaning. The state is simply a fully resolved instance — plus a
few [state-only fields](machine-spec-reference.md#state-only-fields)
(the assigned backend identity, timestamps) that never appear in a
declaration.

**The machine's name is its declaration's file name** (without
`.json`). Neither document contains a name field. Renaming a
machine is renaming the declaration file — and, to keep the
instantiation, its `cache/machines/<name>` directory — while the
machine is stopped.

## A first example

A minimal declaration that boots a DOS floppy image:

```json
{
  "platform": "dos",
  "drives": {
    "floppy": {"source": "media:msdos622-boot"}
  }
}
```

Save it as `machines/msdos.json` — declarations are authored
directly into `machines/`, by hand, by the (future) `init`
scaffolding command, or by `import` — then instantiate and run
it:

```powershell
reliquary create msdos
reliquary start msdos --display
reliquary stop msdos
```

`create` resolves the declaration against an assigned backend and
materializes the cached instantiation under
`cache/machines/msdos/`; `start` and `stop` operate the machine by
name.

## Declaration and state

### The declaration — yours

`machines/<name>.json` holds the machine as you defined it — the
file you authored, and whatever you edit it to later. Write as
little as possible and let resolution fill in the rest:

- Omit `backend` and reliquary picks the best available one.
- Omit `memory`, `cpus`, or `control-planes` and the platform's
  defaults apply.
- Use shorthand: `"hdd"` instead of `"hdd_0"`, a bare source
  string instead of an object.

Omissions are preserved, not baked in: a declaration that omits
`memory` keeps tracking the platform default, even if that default
changes in a later reliquary.

A declaration may not contain
[state-only fields](machine-spec-reference.md#state-only-fields);
`create` rejects a document carrying them.

**Editing the declaration is the supported way to reconfigure a
machine.** Edit it while the machine is stopped; the next `start`
applies your changes (see [reconciliation](#reconciliation-at-start)
below). Editing while the machine runs doesn't take effect until
the next start.

### The state — reliquary's

`cache/machines/<name>/reliquary.json` describes the machine as
it actually is, and reliquary maintains it: whenever reliquary
changes the machine — attaches media, changes memory, reorders
boot devices — it updates the state in the same operation. A
state document that disagrees with the hypervisor's actual
configuration is a bug in reliquary, not an ambiguity you have to
resolve.

The state is fully resolved:

- shorthand keys are canonicalized (`"hdd"` → `"hdd_0"`);
- platform defaults are materialized into explicit values;
- the assigned `backend` is recorded, along with the state-only
  fields: `backend-id`, `created`, `installed`.

The declaration from the [first example](#a-first-example)
produces, on a host where QEMU was selected:

```json
{
  "platform": "dos",
  "backend": "qemu",
  "backend-id": "reliquary-msdos-8c41",
  "created": "2026-07-19T18:20:11Z",
  "memory": 16,
  "cpus": 1,
  "drives": {
    "floppy_0": {"source": "media:msdos622-boot"}
  },
  "boot": ["floppy_0"],
  "control-planes": ["agentless-display"]
}
```

Don't edit the state — or anything else under
`cache/machines/<name>/`. reliquary rewrites the state as it
operates the machine, and reconciliation regenerates its
configuration from the declaration; hand edits are overwritten
without notice. There is never a reason to: the declaration is
your interface.

reliquary rewrites the state carefully: in the same operation as
the machine change it records, atomically
(write-temp-and-replace), and in canonical formatting — stable key
order, two-space indent, UTF-8, trailing newline.

### Reconciliation at `start`

Every `start` brings the three parties — declaration, state,
backend — back into line:

1. The declaration is validated and resolved.
2. Every `media:` item the machine references is hash-verified
   (and fetched if missing or stale — see
   [the media spec](media-spec.md)); the machine never boots
   against silently changed media.
3. The resolved configuration is compared with the state and the
   actual backend machine (verified by identity — see
   [backend assignment](#backend-assignment)).
4. Differences reliquary can apply to the backend — a memory
   change, a drive added, disabled, or detached — are applied and
   recorded in the state.
5. Contradictions reliquary cannot reconcile — an unknown
   `backend-id`, a missing image file, a capability the backend
   lacks — stop the start with an error naming both sides. Nothing
   is silently adopted from either side.

### Runtime changes live in the state

Script steps and CLI commands that reconfigure a running machine —
attaching installer media, ejecting a CD — update the state (and
the machine), never the declaration. The declaration stays what
you meant the machine to be; the state absorbs what operation has
done to it. On the next `start`, reconciliation returns the
machine to its declared configuration.

To make a runtime change permanent, make it in the declaration.

### Destroying and recreating a machine

Because the declaration lives outside the cache, an instantiation
is always disposable:

```powershell
reliquary destroy msdos
reliquary recreate msdos
```

`destroy` discards the machine's entire cached instantiation —
the state, the backend's machine, and the drive images — and
never touches the declaration; an uninstantiated declaration is
just a file, ready for a later `create`. `recreate` is exactly
`destroy` + `create`. Drives
regenerate the way they were declared: `size` drives come back
blank, [`base` drives](machine-spec-reference.md#base--optional--string)
come back as fresh copies (or fresh differencing disks) of their
starting-point images. An installed system that only lives in the
cached drive image is gone after `recreate` — which is the point;
if it should survive, `export` it first or produce it with an
install script that can simply run again.

Because resolution re-runs from scratch, backend assignment
re-runs too: a declaration that doesn't pin `backend` may come
back on a different backend than before — this is the supported
way to move a machine between backends, and since the drive
images regenerate as well, they arrive in the new backend's
native formats.

### Cloning, exporting, importing

Three more lifecycle commands follow from the same model
(machine stopped, in every case):

**`clone <new_name>`** duplicates a machine: the declaration is
copied to `machines/<new_name>.json`, the source's cached drive
images (if it is instantiated) are copied into the clone's cached
instantiation, and `create` resolution runs fresh — the clone
gets its own backend assignment and `backend-id`. State and
backend registration are never copied; a clone shares ancestry,
nothing else.

**`export`** takes something durable out of an ephemeral machine.
It has two targets: a **media image** — a single drive taken out
of the machine as a standalone image file — or the **entire
machine**, copied to its backend's native management, registered
where that backend normally keeps VMs with disks in its native
format. This is the first-class form of the intended endgame:
reliquary machines are ephemeral, and when something should live
on, you export it. An exported machine is independent and
permanently outside reliquary's purview — reliquary will never
touch it again.

**`import <source> --platform <platform>`** goes the other way:
it produces a *spec* from a native backend VM — a declaration
synthesized from the backend's machine configuration, with the
VM's disks preserved as media items (copied, never moving or
modifying the source; each gets a generated definition with a
computed hash) that the declaration's drives `base` on. Import stops
at the spec — it never instantiates; run `create` when you want
the machine materialized. An imported machine recreates like any
other: from its bases. Translating backend config — memory, drives, controllers —
is fine; guessing what OS is inside is not, and no backend
records it, so `--platform` is required. Use import to run
scripted, disposable experiments against a copy of a real machine
without risking the original.

`delete` removes the declaration, destroying the instantiation
first if one exists — the machine is gone entirely. To discard
only the instantiation, use `destroy`.

## Backend assignment

`backend` is optional in a declaration. When omitted, `create`
walks reliquary's internal backend priority order and assigns the
first backend that is:

1. **available** — actually installed and working on this host
   (backends are autodiscovered), and
2. **capable** — able to provide everything the declaration asks
   for (its media, controllers, image formats, control planes).

The assignment is recorded in the state — the declaration stays
portable — and holds for the machine's life: backend disk formats,
identifiers, and VM registration are not portable between
hypervisors, so the assignment never changes underneath a machine.
Moving to another backend is done by
[recreating the machine](#recreating-a-machine).

Declaring `backend` explicitly pins the choice, and fails at
`create` if that backend is unavailable or incapable, rather than
falling back to another.

Alongside the assignment, the state records `backend-id` — the
backend's own identifier for the machine. reliquary never sends a
control command to a hypervisor object until its identity matches
`backend-id`, so a stale or foreign machine is detected and
refused rather than manipulated.

## Validation: fail closed, name the problem

reliquary never guesses what a declaration means and never
silently degrades it. Two kinds of checks apply:

**Format checks** reject malformed documents outright: unknown
fields, bad values, clashing drive slots, state-only fields in a
declaration. See the [field reference](machine-spec-reference.md)
for each field's rules.

**Capability checks** compare the declaration against what the
machine's backend can actually do. A declaration can be perfectly
well-formed and still ask for something a backend cannot provide —
a differencing disk in a format without differencing support, a
SCSI controller on a backend generation without one, VNC on
Hyper-V. These fail with a *capability error* that names the
backend and the missing capability, at `create` or `start` — never
by silently dropping or emulating the feature.

## Platform defaults

Omitted declaration fields resolve from the guest platform, and
the resolved values appear in the state:

| platform | memory (MiB) | cpus | control-planes            |
|----------|--------------|------|---------------------------|
| `dos`    | 16           | 1    | `["agentless-display"]`   |
| `win9x`  | 64           | 1    | `["agentless-display"]`   |
| `winnt`  | 256          | 1    | `["agentless-display"]`   |

## Format stability: none, yet

reliquary is evolving rapidly and **maintains no backward
compatibility before at least a beta-quality release**. That
applies to the spec format in full:

- The format may change shape at any time, without migration
  support.
- There is no in-place upgrading of old documents, no
  compatibility parsing, no deprecated-field aliasing.
- A declaration written for an older reliquary may simply fail
  validation after an update. The remedy is to recreate the
  machine (or update the declaration by hand to the current format
  as documented here).

There is deliberately no version field. Versioning is
compatibility machinery, and the spec carries none until a real
second format version exists — no earlier than beta.

The spec is JSON only. YAML may be supported later; if it is, it
will normalize through exactly the same model with no YAML-only
features.

## Where to next

- [Field reference](machine-spec-reference.md) — `platform`,
  `backend`, `drives` (including starting-point `base` images),
  `boot`, `control-planes`, `backend-settings`, and the
  state-only fields, with every rule and per-field examples.
- [Cookbook](machine-spec-cookbook.md) — complete declarations for
  common machine shapes, with the state documents they resolve
  into.
