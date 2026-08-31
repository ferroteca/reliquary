<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# DECISIONS

This file is the permanent record of every design decision. Its job
is to stop old arguments from being reopened: once an entry here
says something was killed, declined, or superseded, that stands
unless someone brings new evidence, following the process in
[SURFACES.md](SURFACES.md).

**This is a working file, not an archive.** Every entry has to
still be useful *today*, or it doesn't belong here. We rewrite
entries — updating names and matching the current codebase — just
as often as we add new ones. Git history already keeps the old
wording from when an entry was written, so nothing is lost by
updating the live text. A file too big to search through stops
doing its job.

**Before giving a rule a D-number, ask where it actually belongs.**
If a rule belongs in a principle, a use case, a specification, or
AGENTS.md, write it there — the commit that adds it is the record.
Don't also restate it here; we don't keep the same rule written down
twice. A decision to change the project's direction doesn't get an
entry, and neither does a decision to bring something in line with
that direction. What does get an entry: a **contested call where an
alternative was considered and rejected**, recorded here so it
doesn't get re-argued, plus the condition that would justify
reopening it. Keep each entry to a paragraph, not a page.

A ROUTINE LIFECYCLE STEP ALONE DOES NOT GET AN ENTRY. Proposing,
pledging, promoting, or delivering something isn't a decision on its
own — an item's location already shows its status, and the commit
that moves it is the record, so evidence that something was
delivered belongs in that commit's message, not here. Only an actual
ruling made along the way — resolving a disputed reading, deciding
scope, withdrawing something — gets recorded, and only the ruling
itself, not the process around it.

Decisions are numbered in the order they were first recorded — D1 is
the earliest — and a number is never reused. The list reads
newest-first: the top entry has the highest number, and a new entry
goes at the top with the next free number. The D-number is how a
decision gets cited everywhere else: a decision usually supports use
cases (U-numbers), architectural principles
([ARCHITECTURE.md](../ARCHITECTURE.md), P-numbers), or language
goals (G-numbers), and it names what it supports. It may also cite
application surfaces (S-numbers), features (F-numbers), tasks
(T-numbers), and script-validation rules (V-numbers). Design docs,
specs, and code commits justify their choices by citing D-numbers.

If a later decision only partly overrules an entry, the entry stays
where it is — the later, amending entry governs, and we add a
bracketed note at the affected part pointing to it. If a decision is
fully overruled or no longer relevant, it moves to the Retired
decisions section at the bottom, with a note saying what overruled
it. A retired decision no longer binds anything, but we keep it as
part of the record.

**Old terminology still used in entries we haven't rewritten yet.**
This glossary is temporary scaffolding, not policy — it shrinks as
we rewrite entries, and a rewritten entry doesn't need it at all.
**Interfaces** / `INTERFACES.md` is what D85 renamed "application
surfaces" and `SURFACES.md` to. **PRINCIPLES.md** is the old name
for root `ARCHITECTURE.md` (D50). **ROADMAP** was dissolved into
these directories on 2026-07-26. **accepted** was renamed to
**pledged** (D44). **Milestone N** refers to the numbered plan that
ran from 1 through 9 and no longer schedules anything (D33). One
term is a genuine ambiguity, not just an old name: in an entry we
haven't rewritten yet, `S<n>` might mean a **script-validation
rule** — D84 renumbered those to `V<n>`, one for one — or it might
mean one of today's S1–S8 application surfaces. Until that entry is
rewritten, tell which one it means from the entry's date.

## Open questions

Questions we haven't ruled on yet. They live at the front of this
file rather than in a separate one, because the entry that settles a
question is one of the entries below. Nothing in this section binds
anything — a question leaves this section by becoming a D-number,
and the commit that adds that entry is the record.

A question that blocks one specific, not-yet-built feature does
**not** go here — it goes in that feature's own "Decide first"
block, in [proposed/FEATURES.md](proposed/FEATURES.md) or
[pledged/FEATURES.md](pledged/FEATURES.md), because it's a design
question to settle before that feature's work starts. What's listed
below doesn't block any one feature in particular.

### Deferred to 1.0

- **Format versioning**: before 1.0, user documents carry no version
  field and no `$schema` field (settled, owner 2026-07-21; the
  deadline moved from beta to 1.0 along with the compatibility rule,
  D25, for the same reason: a pinned schema reference is really a
  version field wearing a disguise, and a pre-1.0 document doesn't
  have a format version to record — the only schema that matters is
  whichever one the installed copy of Reliquary uses, and editors
  already pick that up through file association. An embedded pin
  would go stale in seed files, which are never overwritten, and
  could let an editor accept a document that Reliquary itself would
  reject). Once compatibility guarantees exist — no earlier than
  1.0 — the leading candidate for the version field is `$schema` as
  a versioned URL: one field that states the document's format
  version and points editors at the matching published schema.

### Open design pressures — revisit as these develop

These aren't questions waiting on an answer today. Each is a design
pressure worth re-examining once the surrounding area firms up.

- Whether GUI/landmark assets should form a new authored-artifact
  category (as of 2026-07-21: `.rlql` is now the fourth authored
  file extension — we still owe it an entry in the INTERFACES
  listing, to be added during the asset-spec/realignment pass).
- Whether the adapter API should become world-facing, i.e. something
  third parties build against (as of 2026-07-21,
  `design/backend-adapter.md` is marked INTERNAL by decision — if a
  real third-party-adapter use case shows up, move it into the
  INTERFACES inventory deliberately, through the interface-change
  rule, not by letting it happen unnoticed).

## Decided

- D127 — THE POINTER TABLET SPLITS INTO `emulated-tablet` (REAL USB HID)
  AND `virtual-tablet` (PARAVIRTUALIZED) — DECIDED (owner, 2026-08-31)
  and delivered the same day, amending D126's tablet handling and
  correcting `backend_qemu.py`'s rendering. Supports U5; P25.

  D126 named `virtual-tablet` as the one exception to its own rule —
  "an absolute-position input device with no bare-metal equivalent" —
  because it didn't fit either the `emulated-` (mimics real legacy
  hardware) or `virtual-` (paravirtualized, useful only in a VM)
  category cleanly. That exception was unnecessary: the device QEMU
  actually rendered for `virtual-tablet` was `usb-tablet`, a real USB
  HID device — squarely an `emulated-` case, just one D126 hadn't
  reclassified. `virtual-tablet` now renders as QEMU's paravirtualized
  `virtio-tablet-pci`, the same family as `virtual-mouse`
  (`virtio-mouse-pci`); a new `emulated-tablet` name takes over
  `usb-tablet`'s rendering, needing no guest driver beyond USB HID
  support. `click`'s absolute-device refusal
  (`machine.pointing-device-not-tablet`) now accepts either name.

  This matters beyond naming: `virtio-tablet-pci` needs a virtio-input
  guest driver that DOS, ReactOS, and most pre-virtio guests don't
  carry, while `usb-tablet` is plug-and-play. The recovered
  `reactos.rlqb` blueprint (`winnt-platform.md`) demonstrated
  `click`-based GUI installs against `virtual-tablet` before this
  decision — it is updated to `emulated-tablet` alongside this change,
  so the working install path keeps working. None of the renamed
  fields has shipped in a release yet (P9), so, like D124 and D126,
  this lands as a plain rename/split with nothing to migrate.

- D126 — A GENERIC DEVICE NAME IN THE BLUEPRINT VOCABULARY IS PREFIXED
  `emulated-` OR `virtual-`, NEVER BARE — DECIDED (owner, 2026-08-30)
  and delivered the same day, renaming `pointer0`'s
  `tablet`/`mouse`/`virtio-mouse`, `rng0`'s `virtio-rng`, a `net`
  device's `model: virtio-net`, and a `share` device's
  `model: virtio-fs`. Supports P25.

  A device model name in this vocabulary is either a real hardware or
  protocol name (`pcnet`, `ne2k`, `9pfs`, `vvfat`) or a generic
  description of what the device does, with no one specific chipset
  behind it. The generic names had drifted into different spellings
  for the same two ideas — a plain `mouse`, a bare `tablet`, and four
  separate `virtio-*` names — which made `virtio-*` read like a
  chipset family of its own, when it actually just means
  "paravirtualized, not modeling any real card." It also isn't tied
  to QEMU: VirtualBox and other backends can implement the same
  paravirtualized idea their own way, under their own driver stack.

  Every generic name now says which of the two kinds it is:
  `emulated-` for a name that mimics one specific piece of real
  legacy hardware (`emulated-mouse`, the PS/2 mouse every machine
  already has), and `virtual-` for a name that exists only because
  it's useful inside a VM — a paravirtualized device (`virtual-mouse`,
  `virtual-rng`, `virtual-net`) or an absolute-position input device
  with no bare-metal equivalent (`virtual-tablet`) [D127 closed this
  exception: `virtual-tablet` now IS the paravirtualized case, and a
  new `emulated-tablet` name took over the real-hardware rendering
  this paragraph had folded into it]. Real hardware and
  protocol names are unaffected — `pcnet`, `ne2k`, `9pfs`, and `vvfat`
  keep their names. None of the renamed fields has shipped in a
  release yet, so this is a plain rename with nothing to migrate, the
  same reasoning D124 gave for the `pointer0` move.

- D125 — A PORTABLE `rng` DEVICE JOINS `devices` AS AN `rng0` SLOT,
  NARROWING D91 RATHER THAN REVERSING IT — DECIDED (owner,
  2026-08-30) and delivered the same day, promoting U22 to the
  current list. Supports U22; P25.

  D91 was overruled for putting `virtio-rng-pci` into the blueprint's
  vocabulary by name — that name is QEMU's own internal
  bus-addressing spelling, not something portable across backends,
  and D93 shut down building the shared vocabulary out of one
  backend's internal names. That specific objection still holds
  today. What's changed since is D122: it already lets a `net`
  device or a share name real hardware directly through `model` — a
  value checked against whichever backend is actually assigned,
  refused by name on any backend that doesn't have it — as long as
  the name is real, general hardware, not a backend's own internal
  spelling. This decision applies that same rule to a random-number
  generator: `devices` gains an `rng0` slot, whose value is a
  portable name, currently `virtual-rng` only (renamed by D126),
  capability-checked the same way a NIC's or a share's `model` is.
  QEMU renders it as
  `-device virtio-rng-pci,id=rng0`; every other backend refuses it by
  name until one actually builds the capability. Leaving `rng0` out
  means the machine has no RNG device at all, the same way leaving
  out every `net` key means it has no NIC.

  The demand is U22's driver-testing harness (the `driver-rig`
  example in `planning/proposed/USE-CASES.md`), which already worked
  through `backend-settings.qemu.args` but wanted this named as
  portable vocabulary instead of a QEMU-only argument, so the
  declaration stays meaningful if another backend ever grows the same
  capability. That's the first real device U22's growable vocabulary
  actually delivers, so U22 moves to the current list the same way
  U28 did for network devices — future devices join the same way,
  one name at a time, without needing a new use case each time.

- D124 — THE POINTER INPUT DEVICE MOVES FROM ITS OWN `pointing-device`
  FIELD INTO `devices`, AS A `pointer0` SLOT — DECIDED (owner,
  2026-08-30) and delivered the same day, extending D121's device-map
  merge to a fourth device kind. Supports U5; P25.

  Since D121, `devices` already holds drives, NICs, and shares in one
  slot-keyed map, discriminated by the key's own medium. The pointer
  input device was the one piece of machine topology left outside
  that map, in its own top-level `pointing-device` field with no
  slot. This decision moves it in: `pointer0` is the only valid key —
  a machine has at most one active pointing device, so there is no
  `pointer1` — and its value is the same three choices as before:
  `virtual-tablet`, `emulated-mouse`, or `virtual-mouse` (renamed by
  D126) [D127 split `virtual-tablet` into `virtual-tablet` and
  `emulated-tablet`, a fourth choice]. Leaving `pointer0` out still
  means the same default leaving out `pointing-device` used to mean:
  `emulated-mouse`. Every check that used to run against
  `pointing-device` — the capability check against the assigned
  backend, `click`'s refusal of every device but `virtual-tablet`
  [now `emulated-tablet` or `virtual-tablet`, D127] — still runs the
  same way, now reading the value from `devices.pointer0` instead of
  a separate field.

  This is a breaking rename of an already-shipped field (F66, T34).
  Before 1.0 there is no compatibility promise (P9), so it lands as
  one complete change: the old field is gone outright, not
  deprecated, matching how T34 renamed the share and NIC model names
  the same day it added them.

- D123 — A SHARE'S INLINE-MEDIA FORM IS THE INTENDED ONE; THE MODEL AND
  ITS DOCS WERE THE DRIFT — DECIDED (owner, 2026-08-30) and delivered
  the same day, striking T33. Supports U14, U21; extends F72's own
  starting point.

  `document._share_device` already accepted a full media written in
  place on a share slot — deliberately: the branch carries a comment
  saying what it's for, and a share-specific rule (no anonymous blank
  there) that only makes sense if the form is intended, not an
  accident. But blueprint-model.md counted two share value forms
  where a drive gets four, blueprint-reference.md called `media`
  unconditionally required, and AGENTS.md repeated the two-form
  claim — so the shortest share an author could actually write,
  `{"share0": {"location": "D:/exchange"}}`, was undefined against
  the project's own norm.

  **The code stays; the norm and its docs catch up.** A deliberate
  carve-out with an explanatory comment is not what an accidental
  branch looks like, and a share's inline form is exactly the shape a
  drive's already is (U14, U21) — refusing it there would be an
  arbitrary asymmetry, not a considered one. blueprint-model.md,
  blueprint-reference.md, and AGENTS.md now all state three share
  value forms — a media name, `{media, model, enabled}`, or an inline
  media spec — with the inline form still refusing the anonymous
  blank a drive's inline form permits: a share with no directory
  means nothing, named or not.

- D122 — A `net` DEVICE MAY NAME ITS CHIPSET EXPLICITLY (`model`),
  OVERRIDING THE PLATFORM DEFAULT, CHECKED PER BACKEND THE SAME WAY
  `controller`'S `nvme`/`virtio` ALREADY ARE — DECIDED (owner,
  2026-08-29) and delivered the same day, reopening the half of D120
  that refused to let a blueprint name a chipset at all. Supports
  U28; P25.

  THE RULE: D120 concluded the chipset should never be authored,
  full stop — resolved per platform, with no override, because
  "which card is used stays owned by the platform table and the
  backends, not the blueprint." That conclusion turned out to be
  wrong for a case D120 didn't consider: DOS-era networking software
  — packet drivers above all — is often written against one specific
  NIC chipset, not "a network card" in the abstract, and the platform
  default (`pcnet`) is a fine default precisely because it's *not*
  what every packet driver expects. Refusing an override entirely
  would leave no way to reach that software at all.

  So `net0`'s object form gains an optional `model` key, checked the
  same way D121's own decision text already worked out for
  `controller`: P25's bar is whether the chipset is real, general
  hardware, not whether every backend already emulates it. `pcnet`
  (AMD Am79C970A) is real hardware both QEMU and VirtualBox emulate.
  `ne2k` (Novell/Eagle NE2000) is real hardware too, but only QEMU's
  adapter emulates it — admitted anyway, and refused by capability
  check on any other backend, exactly the way `controller`'s
  `nvme`/`virtio` already are. Omitting `model` still resolves to the
  platform default (`_PLATFORM_NIC`); naming it overrides that
  default for that one slot. Attachment (`nat`/`bridged`) and chipset
  stay two separate, independent facts — D120's actual point, that
  reachability and driver compatibility are different questions, is
  unaffected; only "the second question can never be answered by the
  blueprint" turned out to be one step too far.

- D121 — `drives` IS RENAMED `devices`, AND `net` KEYS JOIN IT AS A
  SIBLING MEDIUM SHARING THE SAME SLOT-KEYED MAP AND KEY-CLASH CHECK
  — DECIDED (owner, 2026-08-29) and delivered the same day, extending
  D120 the same day it landed. Supports U28; P25.

  THE RULE: `devices` is the one authored field for everything
  attached to a machine — drives (`floppy`/`hdd`/`cdrom`) and NICs
  (`net`) — discriminated by the key's own medium prefix, never by a
  separate `type` tag. A `hdd0` and a `net0` in the same `devices`
  map are unrelated concepts sharing nothing but the map and the
  slot-key grammar; declaring the same slot twice, in any spelling,
  across either kind, is one clash check, not two.

  This is a naming and shape change, not a new capability: nothing
  about what a drive or a NIC *is* changed, and P25's bar (a portable
  field's vocabulary applies generally, not that every value is
  honored everywhere — see D120) is unaffected either way. What
  changed is that the earlier two-field shape (`drives` and, freshly
  landed the same day, a separate `network` field) never actually
  matched what was being asked for: the owner's model for this was
  always one merged device inventory, the way `docs/spec/
  blueprint-model.md`'s own "topology" framing already implied before
  either field existed. Landing `network` as its own field first,
  then merging it into `devices` hours later, means D120's own text
  should be read as superseded on this one point — its `nat`/`bridged`
  vocabulary and the "no chipset named" rule it argued for are both
  still exactly correct and unchanged; only the container they live
  in changed shape.

  **What stays "drive"-worded on purpose, because the concept
  genuinely doesn't reach a NIC:** the `MachineDrive` dataclass; the
  CLI's `insert-media`/`eject-media`/`set-boot-order` commands and
  the script language's `with boot`/`insert`/`eject` verbs (a NIC
  can't be inserted, ejected, or booted); `RESERVED_DRIVE_PROPERTIES`
  and QEMU's own literal `-drive`/`-set drive.<slot>.<property>`
  syntax (D118); `drive_args()`; boot-order resolution and the
  `controller` field. `Machine.drives` and `Machine.network` stay as
  read-only computed views over `Machine.devices`, filtered by type —
  most of the engine only ever wants one kind or the other
  (materialization only touches drives; a capability check wants
  both, separately), and a view keeps that filter in one place
  instead of an `isinstance` check at every call site. State
  (`machine.json`) merges the same way: `drives`/`network` become one
  `devices` map, so `insert_media`/`eject_media`/`set_boot_order` and
  the script runner's preflight now filter that map by shape (a drive
  entry carries `medium`, a NIC entry carries `attachment`) rather
  than getting storage-only behavior for free from a separate map —
  each of those functions is genuinely drive-only, and now says so by
  checking rather than by construction.

- D120 — `network` NAMES AN ATTACHMENT (`nat`/`bridged`), NEVER A NIC
  MODEL; THE CHIPSET IS RESOLVED PER PLATFORM, ORTHOGONAL TO
  ATTACHMENT — DECIDED (owner, 2026-08-29) and delivered the same
  day, reopening the network item in
  [proposed/design/device-growth.md](proposed/design/device-growth.md)
  now that real demand exists (U28). Supports U28; P10, P11, P25.

  **Superseded in part, hours later, by D121 and D122**: `network`
  as a separate top-level field was folded into `devices` alongside
  `drives` (D121), and "the chipset is never named" was narrowed to
  "never named unless the blueprint author actually needs to" (D122)
  — a `model` key overrides the platform default, checked per backend
  the same way `controller`'s `nvme`/`virtio` are. Everything else
  below — the `nat`/`bridged` vocabulary and QEMU's bridge handling —
  is still exactly correct.

  THE RULE: whether a guest can reach anything at all (`nat` vs.
  `bridged`) and which chipset drives that connection are two
  different questions, and only the first is something a blueprint
  author actually wants to state — the second is exactly the kind of
  fact Reliquary already resolves per platform rather than asking for
  (P10), the same way a drive's `controller` defaults to `ide`
  without being named. `network` is a slot-keyed map (`net0`, `net1`,
  …, following the same `<medium><slot>`-shaped key convention
  `drives` already uses), whose value is either a bare attachment
  name or an object adding `interface` (only meaningful for
  `bridged`, refused on `nat`). The NIC chipset itself never appears
  in the blueprint at all — it's chosen by a per-platform table the
  same shape `_PLATFORM_MEMORY` already is, so this needed no
  argument against P25 in either direction: nothing single-backend is
  ever named in the portable field, because nothing about a specific
  chipset is named there at all.

  An earlier version of this decision considered making the chipset
  itself portable vocabulary (`net0: pcnet`/`ne2k`), reasoning by
  analogy to `controller`'s `nvme`/`virtio` values (portable despite
  being single-backend today, since the concept is general hardware
  even where one adapter's capability report is incomplete). That
  reasoning was sound but the wrong question: the owner's actual
  interest was in choosing `nat` vs. `bridged`, never in choosing a
  chipset by name, so the field was reshaped before anything shipped.
  The `controller`-precedent argument stays on record here because
  it's still correct and may be needed again — a future field that
  does need to name single-backend-only hardware shouldn't have to
  re-derive it.

  `bridged` needs a host network interface to mean anything, and the
  two built backends aren't symmetric about supplying one: VirtualBox
  attaches straight to a physical host NIC and has its own sensible
  default when none is named; QEMU's bridged networking attaches to
  an existing **Linux bridge device**, not a physical interface
  directly, and has no host-discovery mechanism — omitting
  `interface` there falls back to QEMU's own conventional bridge name
  `br0`. Reliquary does not probe the host to find or verify a bridge
  itself (weighed and declined for now: detecting the host's default
  egress interface is easy, but automatically enslaving it into a new
  bridge mutates host network configuration and needs per-OS,
  privileged implementation — out of scope here entirely); a host
  with no `br0` fails at QEMU's own launch, not at a Reliquary
  preflight. Read-only detection — use the egress interface only if
  it's already bridged, refuse by name otherwise — is tracked
  separately as **T32**. `interface` is a plain string or a `${key}`
  property reference, bound the same way a media `location` already
  is (U21) — a host interface name is exactly the kind of fact that
  shouldn't be hardcoded into a blueprint meant to be shared.

  The standing constraints in ARCHITECTURE.md ("new kinds of media,
  controllers, and USB devices must extend that same naming
  convention") now also name network devices, since this is that same
  slot-keyed convention applied to a new device kind, not a new one
  invented.

- D119 — CLI.MD, API.MD, AND THE COMMAND MANIFEST EACH GOVERN A
  DIFFERENT PART, AND WHOEVER DEFINES SOMETHING WINS ON THAT PART —
  DECIDED (owner, 2026-08-22), closing the "two norms for one
  semantic surface" open question. Supports P6, P23. Settles which
  of api.md, cli.md, and the command manifest governs when they
  overlap.

  The question was: when cli.md and api.md disagree, which one
  wins? Both were being treated as authoritative for the one
  command surface P6 covers. By the time we revisited this, the
  work had already split naturally: the manifest is authoritative
  for the **list of commands** (F60), cli.md's status section is
  authoritative for **command behavior** — flags, output, exit
  codes — and api.md's status section is authoritative for
  **conventions and return contracts**, describing itself as an
  index pointing to each command family's real contract-defining
  document. So the answer is the third option the open question had
  listed: each kind of rule lives in exactly one home document.
  We're adding the tie-break the question didn't have before: if a
  passage that cites a rule disagrees with that rule's home
  document, the citing passage is wrong, and the home document
  wins. Both api.md's and cli.md's status sections now say this
  explicitly. We rejected making api.md the single authority for
  everything — the obvious-seeming choice — because api.md
  describes design goals that haven't shipped yet, while cli.md
  documents only what currently exists; picking api.md as the sole
  authority would make unbuilt features the official standard.

  WHERE THIS CAUSED PROBLEMS: four rows in the index pointed to the
  blueprint *guide* document as the contract-defining home, but that
  document's own header says it isn't one ("descriptive … this
  guide has the bug"). Those rows now point to instance-model.md and
  blueprint-model.md instead. REOPENS IF a second binding's reference
  docs and the Python implementation disagree about a return
  contract — that's the one kind of conflict no home document
  currently settles.

- D118 — NO SEPARATE SECTION FOR PER-DRIVE SETTINGS; A DRIVE IS
  CONFIGURED THROUGH THE BACKEND'S EXISTING SETTINGS ESCAPE HATCH —
  DECIDED (owner, 2026-08-22) and delivered the same day, closing
  the "per-drive backend settings" open question. Supports U22;
  P25. Extends D92's overlap rule.

  The question was whether a drive-scoped settings section could do
  something the existing machine-scoped one can't. **It can't.**
  Every per-drive setting is really just one backend's own
  vocabulary — QEMU's `cache=`, `aio=`, `serial=`; VirtualBox's
  `--nonrotational` — so P25 already keeps all of it behind the
  backend-settings escape hatch, and the backend's own addressing
  syntax can reach a specific drive from there. For example, QEMU's
  `-set drive.<slot>.<option>=<value>` — we confirmed on an
  installed QEMU that this targets one named drive and refuses
  unknown options or drive ids on its own. The real obstacle was in
  the adapter: hard disks were rendered without an `id=`, and the
  overlap rule (D92) didn't recognize `-set` as a way of touching a
  drive's settings. Both are now fixed — every drive gets
  `id=<slot>`, and a `-set` that touches a property the blueprint's
  `drives` field already renders is rejected, the same rule already
  applied to `-drive`. No blueprint anywhere actually uses
  `backend-settings` yet, so this was settled on design grounds, not
  because of a real case that needed it.

  CONSIDERED AND REJECTED: **a separate drive-scoped settings
  section** — this would mean the same backend vocabulary living in
  two places, with the overlap rule needing to be restated for each
  one. REOPENS IF a backend turns out to have per-drive settings
  that can't be reached from its machine-level settings hatch;
  VirtualBox's hatch is empty today and will be judged once it has
  one.

- D117 — NO SCRIPT-INCLUDE FEATURE; THE EXISTING SCRIPTS DON'T
  JUSTIFY ONE — DECIDED (owner, 2026-08-22), closing the
  "cross-script reuse" open question. Supports (none) — this is a
  refusal; argued from G2, G3, G6, and D104's rule for justifying
  new language constructs.

  The question was whether scripts repeat enough behavior to
  justify adding a constrained include mechanism, checked against
  real scripts, given a recorded wish (owner, 2026-07-21) for
  complex scripts to split into files that reference each other,
  the way source files do. **Measured against the actual scripts,
  the need isn't there.** Of seven scripts (four shipped with the
  codex, three of the owner's), only two idioms repeat: booting to
  a prompt (`start` / `wait "C:\>"`) and powering off (`enter
  "fdapm poweroff"` / `wait machine=stopped`) — two lines each, at
  three places. The one larger candidate, the owner's install
  script, is actually a *diverged* copy of the codex's own install
  script (a different loader, an `eject` moved) — exactly the
  pattern P18's copy-out mechanism expects. A language construct to
  save two lines fails D104's bar for justifying one, and G6 treats
  added syntax as the scarce resource. What "files that reference
  each other" would give you is already available outside the
  language itself: G2 already handles composition — a harness runs
  a `ready` script, its own steps, then a `verify` script; `machine`
  headers state each script's precondition; and variables and
  properties carry data between them.

  CONSIDERED AND REJECTED — **`run @script`, treating a script as
  one statement**: a verb that would run a *linear* script in
  place, with headers checked statically, no recursion allowed so
  the call graph stays a finite tree (G3), no parameters (G2), and
  every statement still keeping its own file, line, and call site.
  This is the least-bad design, recorded so that if this is
  reopened, it starts from this shape rather than from a macro that
  splices in handlers, or a "phase import" (whose `goto` targets
  would tie it to whatever imports it, and untangling that is a
  much bigger feature on its own). REOPENS IF a script in actual
  use repeats a unit that is **bigger than a two-line idiom,
  identical everywhere it's used rather than a diverged copy, and
  self-contained without depending on surrounding control flow** —
  that needs to be evidence of real repetition, not just a wish for
  the feature.

- D116 — `rlq wait` NOW MATCHES THE SCRIPT LANGUAGE'S `wait` VERB
  EXACTLY — DECIDED (owner, 2026-08-22) and delivered the same day,
  striking T31. Supports U14; P6, P11. Completes, for this one
  verb, the rule that a CLI command must behave identically to its
  script-language verb.

  The command manifest maps the CLI's `wait` subcommand to the
  language's `wait_text` verb, and cli.md promised that a CLI
  command behaves exactly like the verb it maps to. But the shipped
  `rlq wait` command differed from the script verb on four points:
  it always treated its argument as a regex, it searched the whole
  joined screen instead of going through the normal stability
  check, it didn't normalize the text before matching, it answered
  the instant it saw a match instead of waiting for the screen to
  settle, and it had no way to wait on the machine channel — only
  the screen. The reference docs listed the argument type as
  `REGEX`. Task T31 had flagged the gate/expiry gap; this decision
  round found the rest of the mismatches.

  **The whole command is fixed to match the verb exactly**, because
  surface S1 says the CLI must not carry its own semantics, and the
  Interaction spec says every verb is defined once and referenced
  everywhere else — never redefined. The `rlq wait` argument is now
  parsed with the same `parse_script("wait <text>")` call the
  language itself uses, so there is no second, CLI-only parser for
  the wait condition. It is then handled exactly the way the
  language handles it: `wait_text` matches one normalized screen
  row under the same stability gate other waits use, and
  `Machine.wait_stopped` watches for the VM to actually stop for
  the machine-channel case, with the lifecycle machinery marking
  the phase afterward — this split is how the runtime already
  works, not something invented for the CLI.

  ALSO DECIDED AT THE SAME TIME: **the shell strips the language's
  quote characters before `rlq wait` ever sees the text**, so the
  bare text typed on the command line is treated as the literal
  spelling, and it is re-quoted using the language's own escaping
  rules; a `${key}` inside it keeps its script-language meaning,
  except property substitution is refused, since properties belong
  to a script, not a bare CLI invocation. Also: **`wait_stopped`
  stays a method on the `Machine` class, with no separate top-level
  function exported for it**, because the manifest's family table
  has one CLI-facing name per command, and which methods deserve a
  true top-level "twin" function is a question for the control-plane
  design, not this decision — REOPENS there.

  CONSIDERED AND REJECTED: **fixing only the gate/expiry problem
  T31 originally flagged** — this would leave the reference docs
  still claiming the command behaved like the language's verb when
  it didn't. **Fixing only the screen-channel behavior and leaving
  the machine-channel wait unsupported from the CLI** — this would
  leave one spelling of the wait verb usable only from scripts, for
  no reason the spec could actually justify.

- D115 — READINESS WAITS NOW GO THROUGH THE SAME STABILITY CHECK AS
  EVERY OTHER WAIT — DECIDED (owner, 2026-08-22) and delivered the
  same day, striking T30. Supports U14; P11. Extends D75's
  screen-stability rule to the readiness wait.

  `wait_ready` was the one prompt-detecting wait in the system that
  answered as soon as it saw a match, instead of waiting for the
  screen to stop changing. By contrast, `execute` holds off until
  the screen under a prompt settles (F45, D75), the script
  language's `wait` verb applies the stability check to every
  observation by default, and the menu-handling code reads the
  screen twice to be sure. T30 asked whether the stability rule
  should also apply to readiness, since the risk here seemed
  smaller — nothing gets cut off, a caller just proceeds slightly
  early. **The rule does apply**, because it's about whether the
  screen has actually finished drawing, not about what the caller
  does next: what happens afterward doesn't change whether the
  screen was really done. And there's a real case that needs this —
  D113's customized guest, whose `AUTOEXEC.BAT` uses `ECHO ON` and
  draws the prompt and the following command on the same row one
  after another; the stability check is what tells them apart.

  CONSIDERED AND REJECTED: **a lighter rule — hold for one "quiet"
  window instead of the full stability check** — this is already
  the same mechanism, since `ScreenStability`'s default window
  already is that window; there's no separate, lighter check to
  build. **Deciding the boot doesn't need this at all** — stock
  FreeDOS runs with `@ECHO OFF`, so watching it boot by hand looks
  fine either way, which is exactly why that observation isn't good
  evidence either way. **Letting the caller tune the wait, the way
  a couple of related settings do** (`stable=`/`stability=`) —
  `execute` doesn't expose any such settings itself; that's an axis
  that belongs to the language, not to this call.

  NOTICED BUT NOT ACTED ON: `rlq wait` and `Machine.wait_text`
  answer as soon as they see a match, even though the verb they
  represent is supposed to apply the stability gate — filed as
  **T31**, decided by **D116**.

- D114 — READINESS GETS A CLI COMMAND TOO; IT IS NOT A SPECIAL CASE
  THAT ONLY WORKS FROM PYTHON — DECIDED (owner, 2026-08-22) and
  delivered the same day, striking T29. Supports U14; P6. Refines
  D90 at the adapter layer.

  `AgentlessGuestExec.wait_ready` had no CLI command that did the
  same thing, and T29 asked whether it needed one, or whether this
  method could be the kind of exception P6 sometimes tolerates.
  **It needs one.** P6 says a capability missing from one surface
  must get added there "unless another principle in force forbids
  it crossing" — and no principle forbids it here. The one standing
  exception to that rule, the codex verbs, is backed by P18, and
  this had nothing backing it. The closest thing the shell already
  had, `rlq wait "C:\>"`, is a weaker wait — it matches a pattern
  anywhere on screen — not the same thing spelled differently, so
  surface S1's promise of a "universal automation path" genuinely
  had a gap here. `Session.exec` was already a thin CLI-facing
  wrapper around its sibling Python method, so by the same pattern
  the new CLI command is `rlq wait-ready`, wrapping
  `Session.wait_ready`, and it shares `exec`'s preflight checks.

  ALSO DECIDED AT THE SAME TIME: the adapter's timeout error becomes
  `WaitExpired` (D90) instead of a plain `RunFailure`, since this is
  a wait and the boot might still complete later. The new class is a
  subclass of `RunFailure`, so no caller's existing error-handling
  code needs to change.

  CONSIDERED AND REJECTED: **treating the missing CLI command as an
  acceptable special case** — this would add a second named
  exception to P6 with no principle behind it, and would mean adding
  an exception category to the manifest just for a method on this
  one type — a category that doesn't actually exist, because this
  gap only slipped through the test suite due to how
  `AgentlessGuestExec` happened to be classified. REOPENS once an
  agent-backed adapter arrives whose readiness is reported to it
  rather than observed on screen — at that point the `prompt=`
  argument on the new command means nothing on that platform, and
  the flag's contract needs to be restated.

- D113 — `wait_ready` NOW ACCEPTS A CUSTOM PROMPT FROM THE CALLER —
  DECIDED (owner, 2026-08-22) and delivered the same day, striking
  T28. Supports U14; P10, P11. Extends D112 to the public API.

  `execute` already learns a customized prompt by reading it off the
  screen it types into (D112). `wait_ready` has no such screen to
  read from, and it is the readiness pattern the README and
  `docs/dos-automation.md` teach *before* `execute`, so a guest whose
  `AUTOEXEC.BAT` sets `PROMPT [$P]$G` failed at the very first
  documented step (T28). **The fix: the caller now states the
  custom prompt at the call site.** `wait_ready(timeout=90, *,
  prompt=None)` — `prompt` is the exact text of the bottom row the
  guest draws when it's ready, and leaving it as `None` keeps the
  standard behavior. This matches how the script language already
  treats this: the codex's own `ready` script states what "ready"
  means with `wait "C:\>"`, on the principle that what counts as
  ready is the workflow's own business, not Reliquary's — now
  applied to the API too: whoever customized the guest states what
  "ready" looks like, right at the one call that needs to know
  it. This is declared rather than guessed (P10), an exact row of
  text rather than a pattern (matching D112's earlier decision
  against a looser match), a plain string every language binding
  can pass through (api.md's second principle), and it touches only
  surface S2. If the wait times out, the error names what it was
  waiting for.

  REMAINING GAP: a prompt that includes `$T` (time) or `$D` (date)
  changes every second and never equals any fixed piece of text —
  this affects both `wait_ready` and `execute` equally, and this
  decision doesn't fix it.

  NOTICED BUT NOT ACTED ON: `wait_ready` has no matching CLI
  command, even though api.md's first principle says every public
  capability needs one — this gap already existed before this
  decision; `exec`'s CLI command never needed one since its
  precondition is just "the machine is running." Also, `wait_ready`
  doesn't apply the screen-stability check under a custom prompt the
  way `execute` does (F45). Both were filed as separate tasks:
  **T29** (decided by **D114**) and **T30** (decided by **D115**)
  (owner, 2026-08-22).

  CONSIDERED AND REJECTED:

  - **A blueprint field** (`platform-settings.prompt`, surface S4)
    — heavier-weight, and it would have the blueprint describe the
    installed system's runtime configuration rather than describing
    the machine itself; D112's earlier finding that `execute` has
    no demand for this still holds. This is the fallback if a
    second call site ever needs the same kind of declaration.
  - **Treating "ready" as just "the screen has stopped changing"**
    — rejected because a boot menu, a "Press any key to continue"
    prompt, and a stalled driver are all screens that stop changing
    too; this is exactly the false-positive case P11 exists to
    prevent, and it's the likeliest place for one to happen.
  - **Removing `wait_ready` in favor of `machine.wait_text`** —
    rejected: the split between the two is correct as designed. An
    agent-based adapter (not yet built) will report readiness by
    the agent checking in, not by reading the screen, while
    `wait_text` matches text anywhere on screen with no concept of
    a "prompt." `wait_ready` stays the general-purpose, documented
    way to wait for readiness, and the guides now explain the
    difference.
  - **A regex that must match the whole bottom row** — this would
    handle `$T`-style prompts, but at the cost of reopening the
    looser matching D112 already rejected, and would mean passing a
    Python-flavored value through a supposedly plain API; it would
    also depart from `execute`'s existing rule of matching the row
    exactly.

- D112 — `execute` NOW RECOGNIZES TWO PROMPT SHAPES: THE STANDARD
  ONE, AND WHATEVER THE GUEST WAS SHOWING BEFORE THE COMMAND RAN —
  DECIDED (owner, 2026-08-22) and delivered the same day. Supports
  U14; P10, P11. Refines D75, which required evidence that a
  command actually finished before treating "a prompt" as a match,
  but left "a prompt" defined as a single fixed pattern.

  `exec`'s completion check only recognized one prompt shape,
  `X:\path>`. So a guest whose `AUTOEXEC.BAT` customizes the DOS
  prompt would sit out the entire timeout on every single command,
  because its real prompt never matched that pattern (issue #9,
  confirmed by a custom-prompt capture in the transcript corpus).
  **Two sources can now count as "the prompt is back," and no
  others:** the **standard DOS shape** — what any unconfigured copy
  of DOS draws, and what lets a `CD` command, which changes the
  visible prompt text, still be recognized as complete — and
  **exactly the prompt text the guest was already showing** when
  the command was sent, whatever shape that text has. The second
  source is the guest telling us, through its own screen, what its
  prompt looks like — an actual observation, not a guess based on
  appearance (D72) — so it needs no declared pattern, and it's what
  makes a guest with a customized prompt usable from its very first
  command.

  REMAINING GAP (P11): if a command itself changes what a
  customized prompt looks like — running `PROMPT` itself, or
  running `CD` under a prompt format like `[$P]$G` — the guest
  returns to text that neither known source predicted, so the wait
  times out. When it does, the timeout error names both prompt
  shapes it was waiting for, so whoever reads the error isn't left
  confused about a guest that actually ran the command just fine.
  This is confirmed in the transcript corpus: the `PROMPT [$P]$G`
  capture still records that timeout as an accepted limitation,
  while a new capture of running `VER` at the customized prompt
  shows the success case working. `wait_ready` only recognizes the
  standard prompt shape — it has no earlier screen to read a
  customized prompt from. That's a real gap on the **public API
  surface**, not simply a dead method: nothing inside `src/` calls
  `wait_ready` itself, but it's exported from the package root, and
  it's the readiness pattern the README and `docs/dos-automation.md`
  teach *before* `execute` — so a guest that boots to a customized
  prompt fails at the very first documented step. This gap is filed
  as **T28** rather than fixed here (an earlier draft of this note
  called the method "unused," which was true only inside `src/` and
  understated the actual, public-facing problem).

  CONSIDERED AND REJECTED:

  - **A declared prompt pattern in the blueprint** — this would
    close the gap, and matches P10's general preference for
    declared configuration over guessed configuration — rejected
    for now because it would be a change to the blueprint format
    (surface S4) with no real demand behind it: no use case
    currently mentions a customized prompt, and the only evidence
    is this one finding from the transcript corpus. This is the
    right move if a guest ever actually needs it.
  - **A declared pattern only, with every other prompt shape
    refused by name** — the option the original bug report called
    "honest and cheap" — rejected because it would make every
    customized guest unusable unless someone explicitly declares
    its prompt pattern, when the guest's own screen already tells
    us what the prompt looks like.
  - **A looser pattern that matches more prompt shapes** — rejected
    outright: this would turn any row ending in `>` into a signal
    that the command finished, which is exactly the false positive
    P11 exists to prevent.

- D111 — `exec` NOW FINDS A COMMAND'S ECHO BY WHERE THE PROMPT WAS,
  NOT BY WHAT THE ROW LOOKS LIKE — DECIDED (owner, 2026-08-22) and
  delivered the same day. Supports U14; P10 (as sharpened by D72),
  P11 (as applied by D75).

  `exec` used to find a command's echoed line by appearance —
  scanning upward from the bottom of the screen for "a row ending
  in `>` that contains the command text." That scan could be
  fooled: if a file's last line happened to echo back text that
  looked like the command, `exec` would stop there, throw away the
  file's real content, and return an **empty** result with no error
  at all (issue #7; confirmed by an echo-lookalike capture in the
  transcript corpus) — a real violation of what P11 requires. There
  is better evidence available than what a row looks like: a
  command is typed at whatever prompt the screen was already
  showing before it was sent, so the echo is **that same prompt
  row, with the command text appended** (wrapped across more than
  one line if the combined text is longer than the screen is wide —
  issue #8), and it appears **exactly where the prompt used to
  be** — the rows above it are the same rows that were above the
  prompt before, minus anything that has since scrolled off the top
  of the screen. Everything the command actually prints appears
  below its echo, so a row that merely happens to contain the same
  text, but has the command's real output above it, is never
  mistaken for the echo — and running the same command twice, with
  the first echo still visible on screen, correctly finds the
  *second* occurrence for the same reason. The old rule of "a row
  ending in `>`" is no longer needed, because the echo's location is
  now known directly, not inferred from its shape.

  REMAINING GAP: if the output is longer than a full screen, and the
  very first visible row happens to look like an echo, that row is
  still accepted as the echo, because there's nothing left above it
  on screen to prove otherwise. This was also wrong under the old
  rule; it is now documented in the transcript corpus's README
  instead of being silently wrong.

  CONSIDERED AND REJECTED:

  - **Remembering which row the live wait first saw the echo appear
    on** (a fix suggested in issue #7 itself) — rejected because
    this depends on the polling loop catching the echo before
    fast-scrolling output pushes it off screen, whereas reading the
    screen before typing the command always works and places the
    echo precisely.
  - **Scanning downward from the top by appearance instead of
    upward from the bottom** — rejected: this still just finds the
    first row that looks right, so running the same command twice
    would return the *previous* run's output with the new echo
    embedded somewhere inside it. The actual rule is what's above
    the echo, not which direction the scan runs in — the scan
    direction was never the fix.

- D110 — GUI AUTOMATION IS JUSTIFIED BY USE CASE U5; FEATURE F63 IS
  SPLIT OUT ON ITS OWN, AND F5 KEEPS ITS NUMBER FOR WHAT'S LEFT —
  DECIDED (owner, 2026-08-21). Supports U5. Pledging U5 and F63 are
  themselves routine lifecycle steps and don't get their own entries
  (D63) — this entry records the actual rulings made while doing
  that, which is the open question F5's status note had carried
  since the 2026-07-27 cleanup.

  WHY THIS IS NEEDED. The remaining, not-yet-built part of U5
  (customized installation) is what justifies building GUI
  automation: a localized installer is really just a different
  installer that shows different text — and on a graphical
  installer, different pixels — which is exactly what the video
  plane, pointer input, and landmark matching exist to handle.
  CONSIDERED AND REJECTED: reading U10's "the screen is the thing
  we assert against" as already covering graphical installers — U10
  is about agentless install-testing and was pledged after F5's
  open banner note was written, so stretching it to cover this case
  would be exactly the kind of citation-written-to-fit-the-need this
  file warns against; this only gets reopened if a GUI
  install-testing scenario shows up as its own, separate use case.
  ALSO REJECTED: pledging U6 (screen recording) at the same time —
  that would commit the whole recording feature (F1) just to serve
  a video plane that U5 already needs on its own.

  THE SPLIT. Feature F63 (the VNC control plane on QEMU, covering
  screen and keyboard) is split out as its own feature and pledged.
  **F5 keeps its number** and covers whatever's left, following the
  same partial-split pattern already used for U5/U21 (D64), rather
  than fully splitting F5 into every planned piece up front the way
  F3 was split. A full split would spend a fresh feature number on
  every piece, but only one piece is actually being pledged right
  now — spending numbers on pieces that stay merely proposed would
  waste the numbering sequence for nothing. The rest of F5 will
  still get split out piece by piece, at each later pledge, when
  each piece is actually ready.

  DESIGN DECISIONS MADE DURING THE SAME ROUND, kept here along with
  the alternatives we rejected, now that shipping the feature has
  replaced the design document that first described them (the
  authoritative spec is now docs/spec/blueprint-model.md; the code
  is `src/reliquary/rfb.py` and the QEMU adapter):

  - **Write a small RFB (VNC) client in-tree, with no new external
    dependency.** We only need to support a fixed, minimal subset
    of the protocol, because Reliquary itself launches the VNC
    server it connects to: the RFB 3.8 handshake, security type
    "None," a pixel format forced to 32-bit true color, framebuffer
    updates using only the Raw encoding, and the `KeyEvent` message
    — no `PointerEvent` yet, until the pointer-input feature is
    pledged separately. CONSIDERED AND REJECTED: the `vncdotool`
    library (it would pull in the Twisted framework for a protocol
    subset we already fully control on both ends) and the
    `asyncvnc` library (it commits to an asyncio-based API, and its
    ecosystem is thin, for the same limited subset we need).
  - **Connect over loopback only, with no VNC-level authentication**,
    leaving identity verification to QMP, which cross-checks the
    connection against the endpoint QMP itself recorded via
    `query-vnc`. CONSIDERED AND REJECTED: adding a per-session VNC
    password via `set_password` — VNC's built-in password scheme
    uses single-DES, which is security theater over a loopback
    connection, and the one real threat it could stop — another
    local process racing to grab the port first — is already caught
    by the identity check. Adding a password would just be one more
    secret to manage, for no real protection gained.
  - **Treat the blueprint's declared `control-planes` list as an
    ordered list of preferences.** This doesn't change what's
    required — the first entry still determines which carriers the
    session uses, and the default behavior is unchanged.
    CONSIDERED AND REJECTED: refusing to let a blueprint declare
    more than one control plane until a proper fallback/preference
    mechanism exists — that would be an arbitrary restriction on
    what can be written in a blueprint, needing its own separate
    change to lift later, and it wouldn't add any protection beyond
    what the capability check already provides.

- D109 — A GUEST'S OWN FONT CAN BE SAVED AS AN AUTHORED ASSET, AND
  ITS BYTES LEAVE THE GUEST THROUGH A DRIVE — DECIDED (owner,
  2026-08-19, during the U25 pledge round). Supports **U25** and
  **U27**; P10, P12, P14, P16, S3, S8. Applies
  [design/authored-binary-assets.md](design/authored-binary-assets.md)'s
  general shape to fonts, its second kind of asset — this is the
  proposal that document said each new kind of asset still had to
  work out for itself. Builds on **D108**'s rule for how a file's
  content leaves Reliquary, rather than reopening it.

  The design draft left four questions open, and this entry answers
  the last two: what a font's declaration in a blueprint actually
  says, and how the font's raw bytes get out of the guest. Both are
  settled here because they had to be settled before the feature
  could ship, and the recorded use-case journey has to name actual
  commands.

  **This serves two separate use cases, not one use case with two
  branches.** U25, as originally drafted, named two situations: a
  font *captured from the running guest*, and a font *supplied
  directly by the author*. These were kept deliberately separate,
  because they don't share a path — capturing a font needs to
  interactively prompt the user, while an installer often draws its
  first screens before any prompt is even possible. A recorded
  use-case journey is supposed to describe one path — the shortest
  route to the goal, with any real choices left to a separate guide
  — so the second situation became its own use case, **U27**, rather
  than staying as a branch inside U25. Neither situation's actual
  requirements changed. **Feature F61 delivers both of them**; only
  the font-dumping tool (F62) belongs to U25 alone. This mirrors how
  U24 and U26 were split apart earlier, for the same reason.

  **The font's bytes leave the guest through a drive the author
  supplies.** A directory-source drive attaches a host directory to
  the guest; the guest writes a file named `FONT.BIN` into that
  directory, and the author then reads it straight off their own
  disk — this is exactly the mechanism D108 already established for
  getting a file's content out of a guest, so it costs nothing new
  to build. Two trade-offs are accepted here rather than avoided:
  directory-source drives currently only work on QEMU, so the
  dumping tool is tied to QEMU, even though the font asset it
  produces works with every backend once it exists; and the file
  only appears once the machine is stopped, which is fine for
  something an author only needs to do once per guest font.

  CONSIDERED AND REJECTED: **sending the bytes over a serial port to
  a file on the host.** This would actually be the better transport
  on its own merits — it works on both reference backends, moves raw
  bytes, and needs no filesystem tooling — but it's rejected for
  what it would drag in, not for what it does. `serial-console`
  already exists as a name in the control-plane vocabulary
  (`document.py`) but nothing is built behind it; adding a real,
  declared serial device would mean new blueprint surface (S4) plus
  a whole endpoint lifecycle — a feature of its own — and bolting on
  a write-only file sink just for this one use would end up
  deciding the shape of the serial control plane sideways, before
  it's actually been designed. Also rejected: **swapping the disk
  image live and reading it with the author's own tools.** This is
  also portable and needs no new mechanism, but pulling 4096 bytes
  out of a live FAT filesystem image isn't something the use-case
  journey can describe as a single command.

  WHAT WOULD REOPEN THIS: either the serial control plane getting
  properly designed for its own reasons, or directory-source drives
  becoming available on a second backend. Either one would make the
  dumping tool portable — being tied to QEMU is the only cost this
  decision is actually paying.

  **A script names a font to use with `font @name`, a statement that
  sets a font-search prefix.** From that point in the script forward,
  the named fonts are tried first, before falling back to the host's
  built-in fonts; running `font` a second time replaces the prefix
  rather than adding to it. This is a new kind of action added to an
  existing statement shape, which is exactly the kind of small
  addition G7 says should be cheap to add.

  CONSIDERED AND REJECTED: **a scoped block, `with font @name { … }`.**
  This is the obvious-looking alternative, but it doesn't fit how
  scoped blocks work in this language: the set of things a scoped
  block header can declare is fixed at three, and every one of them
  is a lasting change to the machine that the block exists to *undo*
  automatically when it ends (D104). Choosing a font doesn't change
  anything on the machine, so there's nothing for the block to undo,
  and no reason to use one. Also rejected: **a font declaration in
  the script's header, before any statements run.** This is the
  cheapest of the three options, and it's easy to check statically —
  but it can't express the actual situation this feature has to
  handle: which program is responsible for drawing the screen
  changes partway through booting (the firmware draws early screens
  in a different typeface than the OS draws later ones), and only the
  running script knows when that handoff happens.

  **A font's declaration states its codepage, and matching now works
  by priority order.** Beyond just declaring the glyph cell's
  dimensions — 256 glyphs of 16 rows and 512 glyphs of 8 rows both
  add up to the same 4096 bytes, so the geometry has to be declared,
  never guessed (P10) — a font's declaration also states what its
  character codes actually mean. When the text-recognition matcher
  finds a glyph inside a font that was explicitly declared this way,
  it decodes the matched code using that font's stated meaning. The
  host's own built-in fonts keep their existing, current meanings —
  nothing already working changes. These two pieces are really one
  decision: today's matcher pools every font's glyphs together, picks
  whichever is the closest visual match across all of them, and only
  uses declaration order to break exact ties. Under that scheme,
  "which font matched" doesn't actually mean anything reliable, so a
  newly declared font could only ever make things worse — adding one
  more near-match that might beat out the correct glyph. Only by
  checking fonts in priority order, and stopping at the first one
  whose match is close enough, do both the narrower search and the
  codepage-based decoding actually mean something.

  CONSIDERED AND REJECTED: **declaring the cell dimensions only,
  leaving every matched character code with its existing meaning.**
  This is a meaningfully smaller change — nothing in the text
  pipeline, the recorded transcripts, or the test fixtures would need
  to move — but it only covers a guest whose glyph shapes differ
  while its underlying character codes stay the same. The case this
  feature actually has to handle — a specially prepared codepage on a
  localized installer — is exactly the opposite: the glyph shape
  would be found, but the wait for specific text still wouldn't
  match, because the character code meanings wouldn't be tracked.

- D108 — RELIQUARY DOES NOT READ OR WRITE FILE CONTENT INSIDE A
  MACHINE'S DRIVES, AND THE DRIVE-LETTER MAPPING IS REMOVED ALONG
  WITH THAT — DECIDED (owner, 2026-08-16). Supports U14, U20; P16,
  P18. Changes **U14** and **P16**, removes **P17** and **P27**,
  and withdraws feature **F41**.

  Reliquary declares a machine's drives, creates them, and can swap
  their media — but it does not read or write what's actually
  inside a drive, and it does not map any volume to a specific
  guest drive letter. If something outside Reliquary needs to get a
  file across the guest/host boundary, it has to supply the drive
  and move the file itself: by using a directory-source drive that
  attaches a host directory, by swapping a disk image live with
  `insert-media --file`, or by using the machine's own directory,
  which D5 already exposes as a way to reach the files directly with
  outside tools. **The recommended tool for this is named
  explicitly: the third-party `remanence` library**, which opens raw
  and qcow2 disk images directly and reads and writes the FAT
  volumes inside them. This work happens entirely outside
  Reliquary's own runtime — a consumer uses `remanence` (or another
  tool) directly, not through Reliquary.

  CONSIDERED AND REJECTED: **keeping just the directory-source half
  of the removed file-access feature**, since that half needs no
  access to a stopped machine's disk at all. This was rejected
  because it would still require keeping the drive-letter mapping
  alive to address a drive by letter — the very thing this decision
  removes — so keeping half the feature would cost nearly the whole
  mechanism anyway, and the surviving half would only work on QEMU.
  Also rejected: **a narrowed `describe-drives` command** that
  reports only the declared and chosen drive facts. `list-machines
  --json` already reports those facts, and a command shaped only by
  what was just deleted isn't a real, separately justified feature;
  a genuine per-machine inspection command would need to be argued
  for on its own merits, not as a leftover.

  WHAT WOULD REOPEN THIS: a real use case that can't be completed
  using property values, declared drives, and live media swapping.
  **Feature F15 is the place to watch** — it now reports drives by
  their key name rather than by guest drive letter, so any future
  demand to bring back drive letters is really a demand to bring
  back the whole mapping this decision removes.


- D106 — THE TEST SUITE NOW REQUIRES PYTEST, NOT JUST PYTHON'S
  BUILT-IN `unittest` — DECIDED (owner, 2026-08-13). Supports how
  P11 was already read by D95: a check that silently fails to run
  is a capability gap that fails silently, which P11 forbids.
  Changes AGENTS.md's stated preference for the standard library's
  `unittest`; the rule's actual wording is updated as part of this
  migration.

  **The real argument was never about adding a dependency, even
  though that's the argument that kept getting made against it.**
  AGENTS.md already treats a test-only dependency as acceptable when
  the suite genuinely needs it — `jsonschema` is one such dependency
  — so simply counting dependencies doesn't settle anything. What
  settles it is the exact kind of failure the "no check silently
  skips" rule exists to catch: the conformance-corpus tests were
  running against the parser and never against the schema, while
  claiming the two could never drift apart, and 135 test fixtures
  split across two checks, run inside `unittest`'s `subTest`,
  produced a test run that looked identical whether it ran the full
  set or only half of it. With pytest parametrizing each fixture as
  its own separately collected test, the number of tests collected
  becomes part of what's actually being checked. The same problem
  showed up in the opt-in integration test tier: a pytest marker
  states "this tier is being deliberately skipped," where
  `unittest`'s `skipUnless` looks identical whether the skip is
  deliberate or accidental — which is why, under the old setup, that
  tier needed its own separately asserted, exact skip count just to
  catch an accidental skip.

  CONSIDERED AND REJECTED: **using pytest only as the test runner,
  while keeping the existing `TestCase`-based test classes.** This
  costs almost nothing and keeps `python -m unittest tests` working
  for someone who just unpacks the source distribution — but it
  buys none of the benefits above, since the fixtures would stay
  wrapped in `subTest` and the integration tier would stay a plain
  skip, which are exactly the two problems this migration exists to
  fix. CONSIDERED AND REJECTED: **staying entirely on `unittest`** —
  the same downsides, with the dependency avoided.

  Two costs are accepted here, deliberately. First, `python -m
  unittest tests` no longer works, so checking an unpacked source
  distribution now needs the project's development dependency group
  installed — decided in the same round as **D105**, which is what
  put the test suite itself into the source distribution. This cost
  was accepted because pytest is already packaged everywhere a
  package maintainer would be working. Second, **plugin autoloading
  is explicitly turned off in the project's own pytest
  configuration**, rather than left to whatever plugins happen to be
  installed for whoever runs the tests — a test suite shipped to
  other people must not collect a different set of tests in their
  environment than it does in this one.

  Nothing else is reopened by this. The general preference for the
  standard library's `unittest` still stands everywhere else — this
  is one dependency judged worth it for this specific reason, not a
  general lowering of the bar.

- D105 — THE SOURCE DISTRIBUTION (SDIST) NOW SHIPS THE TEST SUITE,
  BUT NOT THE `planning/` GOVERNANCE FILES — DECIDED (owner,
  2026-08-13). Supports how P11 is read: a claim nobody can actually
  check isn't really a claim. Changes **D96** — its ruling about
  `planning/` stands, and its ruling about the wheel package is
  untouched.

  **D96 treated the packaging ecosystem as neutral on whether the
  sdist should include the test suite, but it isn't neutral.** By
  convention, an sdist is the artifact a stranger can both build
  *and verify* from, and downstream packagers routinely run a
  project's own test suite as part of building their package — that
  convention points the opposite way from what D96 decided, and D96
  only weighed the wheel package's already-settled rule and a raw
  file count, without weighing this packaging convention. That file
  count argument was really about `planning/`, not about the test
  suite: 187 of 280 files were governance documents and test
  fixtures counted together as a single number, when it's really
  only the governance documents that have no business in a
  stranger's hands.

  CONSIDERED AND REJECTED: leaving the test suite out and relying on
  `uv build`'s completeness check instead, which is what D96
  originally offered as the benefit of leaving the suite out. That
  completeness check is kept, and it's still how we prove a source
  archive is complete — but it was never actually an argument for
  *withholding* the test suite, only that nothing was technically
  lost from the archive by leaving it out. What actually was lost is
  a downstream packager's ability to run the test suite, on a
  platform this project itself never tests on.

  CONSIDERED AND REJECTED: **moving the catalogue of example scripts
  into `docs/`**, so the tests that check documented examples could
  still read it. This was the initial plan, on the idea that a body
  of examples the code is checked against counts as documentation
  rather than governance — but it was abandoned once we looked at
  what the catalogue actually holds: *unresolved* design problems,
  which get deleted once they're resolved. That's governance, and
  shipping governance to strangers is exactly what the other half of
  this decision refuses. **Instead, the test itself moved**, into
  `tests/source_tree/`, which is never shipped anywhere: a test that
  reads something no shipped artifact carries should simply be
  unable to run outside this repository, rather than wrapped in a
  guard that quietly makes it pass elsewhere. The general rule for
  this kind of test now lives in AGENTS.md, governing every test
  like this, not just this one catalogue.

  REOPENS IF the test suite ever needs something a downstream
  packager can't reasonably provide. **D106**'s requirement of
  pytest does not count as one of those.

- D104 — A TEMPORARY MACHINE-STATE CHANGE IS WRITTEN AS A `with`
  BLOCK, AND UNDOING A BOOT-ORDER CHANGE REQUIRES A STOPPED MACHINE
  — DECIDED (owner, 2026-08-13, during the U24 pledge round).
  Supports **U24** and **U26**; P14, S3. Builds on **D15**'s first
  open question (Q1), without reopening it.

  **This serves two separate use cases, not one use case with a
  failure-handling clause attached.** U24, as originally drafted,
  included the guarantee that a run leaves the machine's state
  exactly as it began, as part of its own path — but the "one use
  case is one simple path" rule doesn't allow a deviation like that
  to live as a clause inside the happy path. This guarantee became a
  **use case in its own right** (U26), rather than a principle,
  which was the other place such a rule could have lived.
  CONSIDERED AND REJECTED: writing it as a principle instead (it
  would have been P28). The rule genuinely does apply to every
  outcome and every surface — reverting state after a run that
  *succeeded* is the same rule quietly doing its job where nobody's
  watching — but the half of it a user actually experiences is a
  goal they pursue, and turning it into a principle would have
  described the mechanism when what was actually missing was
  recognizing the demand for it. Neither half's substance changed,
  and feature F54 delivers both.

  Two close calls were made here, against what was initially
  recommended, and the arguments against them are recorded because
  each one is strong enough that someone might raise it again.

  **The syntax is a `with` block** — wrapping either the phases of a
  phased script or the statements of a linear one — headed by one of
  `insert`, `eject`, or `set-boot`, written exactly as those verbs
  are written today. CONSIDERED AND REJECTED: **a `scope=run`
  modifier** added to those three verbs instead, which would cost
  nothing in new syntax — a `key=value` modifier is already the same
  shape as the existing `exclude=` and `stability=` modifiers, so no
  new language construct is needed, and validation rules V2/V14
  could cover it without a new rule id. This was rejected because a
  modifier like that can only ever scope its effect to the whole
  *run*, while what U24 actually needs is to scope to one *stage*
  within a run — a mechanism that can't express the actual unit the
  need is written in isn't cheap, no matter how little syntax it
  adds. Also rejected: a **header declaration** at the top of the
  script (like `boot cdrom0 hdd0`) — this covers boot order alone,
  leaving media changes — half of what U24 needs — requiring a
  second mechanism, and it would put persistent-state policy in
  exactly the place script-spec.md deliberately keeps that kind of
  policy out of.

  **The boot-order form of the block is headed by `boot`, and it
  states only a prefix** — not `set-boot`, and not a full boot
  order. What a stage of a script actually needs to say is "boot
  from the CD-ROM first," and an author shouldn't have to restate
  the rest of an order they aren't changing (owner, same day). The
  drives named come first, in the order given, and the machine's
  already-configured order follows after them. CONSIDERED AND
  REJECTED: reusing `set-boot` as this block's header too. That verb
  *replaces* the whole boot order, so using the same word for a
  scoped, prefix-only version would give one spelling two different
  meanings — which a closed grammar like this one can't tolerate,
  since a reader would have no way to tell which meaning applies. A
  separate word costs one more entry in a vocabulary that has room
  for it, and leaves `set-boot`'s existing meaning untouched.

  CONSIDERED AND REJECTED — raised and then withdrawn within the
  same decision round: **promoting an entire class of drive at
  once**, so one word could move every CD-ROM drive together.
  Instead, the block's header takes specific drive slot keys, so a
  machine with two optical drives has to name both explicitly. This
  was withdrawn as more capability than the actual need calls for —
  but the naming collision it would have run into is worth
  recording: a bare `cdrom` is already the blueprint's shorthand for
  the drive named `cdrom0`, so a drive-kind keyword couldn't have
  used that obvious spelling, and every other candidate spelling
  would just have been a third way of naming a drive.

  **The block's scope is dynamic, not based on where the text sits.**
  It stays active as long as control is actually inside the block,
  regardless of how control got there. A text-based (lexical) scope
  was rejected for a mechanical reason, not a stylistic one: every
  phase body in this language ends with a jump to another phase, so
  a scope that ended wherever its own text ended would revert its
  changes the instant the first `goto` fired, making it useless for
  anything an installer script actually needs.

  **Undoing a boot-order change requires the machine to be
  stopped.** If control exits the block while the machine is still
  running, the run fails, and the error names exactly what couldn't
  be undone. CONSIDERED AND REJECTED: letting the runtime's own
  restore mechanism write the saved state document even while the
  machine keeps running, on the reasoning that a restore has no live
  effect and only changes what the next boot will read. This was
  rejected because D15's first open question already established
  that changing the boot order requires a stopped machine, as a
  property of the machine itself — not merely as a courtesy to
  whoever's writing the script — and letting a second code path
  write that state under a different rule is exactly the kind of
  exception that erodes a guarantee over time, since the next
  exception would cite this one as precedent. The cost accepted here
  is real, and stated plainly: a run that otherwise succeeded
  completely can still fail at its very last step, and the fix, if
  an author needs to hand back a still-running machine, is for the
  script itself to say so explicitly. **Task T27 removes most of the
  sting** by moving this same check to parse time instead of run
  time, which is why feature F54 depends on that earlier analysis.

  **What would reopen the stopped-only restore rule** is the same
  thing that would reopen D15's first open question: if the boot
  order is ever given a live effect on a running machine, or if the
  stopped-only requirement is revisited for its own separate
  reasons, this rule gets reconsidered together with that change,
  and not before.

- D103 — THE VOCABULARY CROSSING THE ADAPTER BOUNDARY FOR KEY NAMES
  IS QEMU'S OWN QCODE SET, DOCUMENTED AS SUCH — DECIDED (owner,
  2026-08-13). Supports P11. Leaves P25 untouched: that principle
  governs the blueprint's portable vocabulary, and the script
  language's `press` key names stay portable.

  **The internal boundary between the control plane and the
  backends was already using QEMU's own key names, while claiming
  to be backend-neutral.** Three docstrings, plus the boundary's own
  design note, claimed the key names crossing it were a portable set
  that QEMU simply happened to match. That wasn't true:
  `control_display._PLAIN` emits QEMU-specific names like `spc` and
  `ret`, `script_runner.resolve_key` translates the script
  language's own key names into QEMU's names before crossing the
  boundary, and the VirtualBox adapter's own scancode table is keyed
  by `ret`, `spc`, `pgup`, and `pgdn` — not `enter` or `space`.
  **That table is the proof**: the one adapter this supposedly
  neutral contract was written for was actually built to match
  whatever names arrived, rather than to match what was declared, so
  the "portable" claim had already failed the one real test it had.

  CONSIDERED AND REJECTED: making the boundary genuinely
  backend-neutral — renaming the control plane's internal tables,
  moving the QEMU-specific name mapping into the QEMU adapter, and
  rekeying VirtualBox's table to match. This would need a naming
  vocabulary that doesn't exist yet: `PORTABLE_KEY_NAMES` only
  covers 31 named keys, while this boundary also has to carry
  punctuation, letters, and digits — so doing this honestly would
  mean inventing a third naming scheme that neither backend actually
  speaks natively, for no real behavioral benefit on either one. The
  cost accepted instead is just naming the boundary after the
  reference backend (QEMU) it was already built around — a one-time
  cost.

  REOPENS IF a backend shows up whose own input API can't express a
  qcode name, or a second adapter author needs key spellings this set
  doesn't cover — at that point, a real third naming scheme would
  earn its keep, and this decision is the one to overrule.

- D102 — BLUEPRINT FILES ARE WRITTEN IN JSON5, NOT JSONC — DECIDED
  (owner, 2026-08-05). Supports U4, U5; G2. Changes D18's earlier
  choice of input format; D18's rule that a blueprint construct may
  only expand into plain data, never carry general computation,
  still applies unchanged.

  **JSON5 is now the grammar blueprint files are written in.** JSONC
  turned out not to be one settled grammar, but more of a loose
  label used across the ecosystem: even its own draft specification
  makes support for trailing commas optional, which forced
  Reliquary's earlier wording to define its own project-specific
  variant of it. JSON5, by contrast, has one published grammar, so
  authors and any independent tooling they use have one external
  spec to implement against. The parser still rejects `NaN` and both
  positive and negative infinity, so a parsed blueprint's values
  remain ordinary JSON data once loaded.

  CONSIDERED AND REJECTED: keeping the narrower JSONC dialect because
  it's more familiar to editors. That's still a reasonable choice for
  a generic configuration file, but it doesn't outweigh having a
  fully specified grammar for Reliquary's own authored file format.
  REOPENS only if there's evidence that the editor and schema tooling
  this format depends on can't actually support JSON5 without a real
  loss to the authoring experience.

- D101 — THE MAP OF SCRIPT LABELS COMES FROM THE BLUEPRINT, READ
  FRESH EACH TIME A SCRIPT RUNS — DECIDED (owner, 2026-08-02).
  Supports U1, U14; P6, P11.

  A map of labels to scripts describes which instructions to run,
  not what the machine itself is — so it belongs alongside
  `parameters`, outside the set of fields that get frozen into a
  machine's saved state, rather than inside it. It's read straight
  from the blueprint every time a script runs, and it's never stored
  in machine state or included in the state digest. The
  authoritative description of this lives in
  [instance-model.md](../docs/spec/instance-model.md); what's
  recorded here is the actual contested question, because the code
  had drifted toward the opposite behavior, and a reader could
  reasonably have assumed that drift was intentional — cli.md had
  already defined a label as coming from "the blueprint's `scripts`
  map," and the design for U5's parameters was written assuming the
  scripts map was read fresh at each run.

  CONSIDERED AND REJECTED: making `parameters` also read from saved
  machine state instead, to make the two symmetrical. This was
  rejected because it would break the half of the existing behavior
  that was actually correct — editing a parameter would then require
  running `apply` before the next run could see the change. REOPENS
  only if a real case shows a machine needs its script-label map
  locked in place against later blueprint edits — which is exactly
  the kind of argument this decision says doesn't apply to it.

- D100 — FEATURES F12 AND F44 ARE REJECTED OUTRIGHT — DECIDED
  (owner, 2026-08-02). Supports P8. Retires both feature numbers
  (see D23 — no placeholder stub kept for either).

  Neither feature is worth what it would cost to build. **F44**
  (`replay`) would have offered cheap reruns without needing a real
  hypervisor — but that only holds as long as neither the script nor
  the guest's behavior changes. What's left once you account for
  that is catching regressions in Reliquary's own
  screen-interpretation logic against a frozen recording — and F43
  already does that job. **F12** (`simulator`) names one real pain
  point — people writing tests end up monkeypatching
  `start_machine`, `stop_machine`, and `exec` directly — but its own
  "decide first" section left the actual feature undesigned (what
  shape should a fake guest-output responder take, under principles
  P6 and P7?), which is a disproportionate design cost just to make
  life more convenient for people writing tests.

  CONSIDERED AND REJECTED: leaving both parked in `proposed/`
  instead of rejecting them outright. That shelf is for live
  arguments still waiting on real demand, not for settled maybes.
  Either capability can come back, but only by winning its own
  argument again from scratch — not by reviving these entries.

- D99 — A USE CASE INVENTED JUST TO SATISFY THE CITATION REQUIREMENT
  DOES NOT COUNT AS REAL DEMAND — DECIDED (owner, 2026-08-02).
  Supports P8.

  P8 requires that a real need be shown before a feature is built,
  so that features answer actual needs, instead of needs getting
  invented backward to justify a feature someone already wanted to
  build. Writing a use case *specifically in order to* satisfy that
  citation requirement inverts the rule while appearing to follow
  it — the check looks satisfied on paper, while the exact problem
  it exists to prevent still happens, just one step removed. A use
  case only earns its number by describing a need that would exist
  on its own, independent of whatever feature is citing it. This was
  caught when F44's pledge round drafted use case U23 for exactly
  this reason — F44 was withdrawn, U23 was struck, and its number is
  not reused (see D23 — no placeholder kept).

  CONSIDERED AND REJECTED: narrowing U23 down to just the part about
  F12's monkeypatching problem, instead of striking it entirely.
  That specific problem is real, but it belongs to F12 alone, and
  keeping a use case alive just to justify a feature nobody has
  actually argued for repeats the same mistake in smaller print.

- D98 — A DIAGNOSTIC CAPTURE FILE IS NOT THE SAME THING AS A RUN
  RECORD, AND ITS FILE FORMAT IS NOT A DOCUMENTED APPLICATION
  SURFACE — DECIDED (owner, 2026-08-01, during the F13 pledge
  round). Supports P22; **narrows how far D36 reaches**.

  **The real question here is whether D36 already rules this out.**
  D36 deleted persisted run output entirely — the `run-events.jsonl`
  file, the `transcript.txt` file, and the whole `runs/` archive —
  and surface S7 now states the rule as "a run drives the machine
  and returns its output to whoever started it, and stores nothing."
  Feature F42's new `--record <path>` option writes screen captures
  to disk, which looks at first glance like exactly what D36 already
  refused. It isn't: what D36 actually refused was **using
  persistence as the mechanism for asynchronous runs** — a record
  written so a separate process could follow along with a run in
  progress — and it refused that because nobody had shown a need for
  it. A capture file, by contrast, is only ever written when a
  maintainer explicitly names a path for it, nothing reads it at
  runtime, and it answers a real need D36 never actually considered:
  P22 requires a way to test the screen-interpretation logic against
  more than fabricated input, and a capture file is how that testing
  happens. D36 still fully applies to every run that doesn't ask for
  a capture.

  **The capture file's format is deliberately not treated as a
  documented application surface**, and this decision records that
  choice explicitly so it isn't lost: someone who finds `.rlqt`
  files and goes looking for its entry in `docs/spec/` should learn,
  from this entry, that no such spec was ever written on purpose. It
  has no compatibility guarantee and no stability promise — changing
  its format is routine maintenance, not an application-surface
  change requiring the surface-change process. What *is* a
  documented surface is only the `--record` option's existence and
  behavior (surfaces S1 and S2, which are governed together under
  P6). The alternative considered and rejected was a maintainer-only
  `RELIQUARY_RECORD` environment variable instead of the `--record`
  flag — this would have left D36 and S7 technically untouched, but
  only by leaving the whole capability undocumented: an unspecified
  environment variable quietly behaving like a real surface without
  ever being reviewed as one, in a project where every other
  `RELIQUARY_*` environment variable is fully specified.

  **What would reopen this is feature F44 (a hypothetical "replay"
  feature)**: the moment some caller's workflow starts depending on
  a transcript file for something other than diagnostics, the format
  becomes something the outside world relies on, which brings back
  both the surface-change vetting process and the need for a real
  `docs/spec/` entry. That dependency is exactly what F44 would
  introduce, which is why this entry states the format's current,
  undocumented standing now, rather than leaving it to be discovered
  the hard way later.

- D97 — EVERY `list-*` COMMAND SHOWS ITS DESCRIPTIONS; DROPPING THE
  FIELD ENTIRELY WAS REJECTED — DECIDED (owner, 2026-08-01).
  Supports U11; P6, P11. Resolves the open question D88 left as
  task T8.

  T8 offered two ways to resolve this open question: decide how
  descriptions should display to a human reader, or drop the
  `description` field entirely from every listing surface, including
  `--json` output. **Dropping it is rejected, because use case U11
  still stands** — "read a description" is an active requirement of
  that use case, so dropping the field would really be changing the
  list of use cases while disguised as a display cleanup; reopening
  this would first require winning that separate argument. The
  display question is now settled: **an indented, wrapped line of
  description text under each entry, never a fixed-width column** —
  a fixed-width column holding unbounded free text is exactly what
  D88 already rejected, since truncating it would cut off the very
  words someone is trying to read. This applies uniformly everywhere
  a listing shows something with a description: `list-codex`, both
  forms of `list-scripts`, and `list-blueprints`. `list-blueprints`'s
  JSON record also gains `description` and `platform` fields, so
  `--json` output carries the same information the human-readable
  view shows (P6). CONSIDERED AND REJECTED: a separate `describe-*`
  detail command. Reading full text one command per entry is the
  wrong interaction for scanning an entire library at once, and a
  whole new family of commands needs real justification that a
  simple wrapped line of text already satisfies. The authoritative
  wording for this lands in docs/spec/cli.md, delivered together
  with the implementation that resolves T8.

- D96 — RELEASED PACKAGE ARTIFACTS CARRY NO TESTS — DECIDED (owner,
  2026-07-30). [Its ruling about the sdist is later overruled by
  **D105**: the test suite ships in the sdist again — only the
  ruling about the wheel package, and the clauses below about
  `planning/`, still apply.] Supports P21's general instinct,
  applied here to what actually gets shipped rather than what the
  project depends on. The wheel package already excluded the test
  suite; the sdist had the suite deliberately added to it, and
  **that choice was never actually decided by anyone** — it built up
  gradually through `MANIFEST.in`, and AGENTS.md and `check_dist.py`
  then started describing it as settled policy, with `check_dist`
  going as far as to *require* the suite's presence. Two-thirds of
  the source distribution's files were test files: 187 of 280.

  [This paragraph is overruled by D105.] **The real question is what
  replaces the check the sdist's test suite provided.** Shipping the
  suite bought one genuinely useful thing: the ability to unpack the
  sdist outside the repository and run the suite there, as a check
  that the source package was complete. Dropping the suite has to
  account for losing that. The answer is structural rather than a
  direct replacement: `uv build` builds the wheel package *from* the
  sdist, so an archive that's missing anything the build needs will
  simply fail to build. The actual check was never "do the tests
  pass" — it was "is the archive complete" — and the build process
  proves that on its own, without needing to ship 187 test files to
  do it.

  **THE `planning/`/`design/` DIRECTORIES WERE THE GIVEAWAY** (in the
  owner's words: "'planning' docs in published test package is a
  solution to a problem, it's part of a problem"). These were added
  to the sdist so the test suite could read the catalogue of example
  scripts out of an unpacked sdist — meaning internal, maintainer-only
  governance documents were being shipped to a stranger, just to
  support a test run essentially nobody ever actually performs. This
  goes away along with the test suite, and `check_dist` now
  **forbids** both the `planning/` and `design/` trees from appearing
  in either shipped artifact, rather than requiring them in one.
  [D105 later keeps the `planning/` half of this rule and drops the
  other half: the test suite is required in the sdist again, and
  still forbidden in the wheel.] `docs/` still ships: documentation
  inside a source package is a normal convention, and it isn't a
  test.

  This takes effect starting with the next release. **The
  already-published 0.1.0.dev6 sdist on PyPI still carries the
  tests** and can't be changed — once a version is published, it's
  immutable — so this record shouldn't be read as if it applied
  retroactively to that release.

- D95 — THE MINIMUM SUPPORTED PYTHON VERSION IS RAISED TO 3.12, BY
  DROPPING SUPPORT FOR OLDER VERSIONS RATHER THAN FIXING THEM —
  DECIDED (owner, 2026-07-30). Supports how P11 is already read
  elsewhere — AGENTS.md already applies this to host platforms — an
  untested version is a capability nobody has actually verified, not
  a quiet promise that it works. The package had published `>=3.9`
  as its requirement, but that had never actually been tested. The
  first real test run failed on **Python 3.9 and 3.10** (the
  `keyring` dependency reaches `platform.win32_ver()`, which shells
  out to another process on those versions, tripping the test
  suite's own rule against spawning subprocesses) and on **Python
  3.11** (39 errors, caused by a dataclass default value using
  `MappingProxyType`, which 3.11 rejects as unhashable). Python
  3.12, 3.13, and 3.14 all pass. **Fixing these instead of dropping
  support for the older versions was considered and rejected** (in
  the owner's words: "if there is *any* doubt, just drop"): the 3.11
  issue needs a `default_factory`, and the 3.9/3.10 issue needs the
  no-subprocess guard taught about `platform`'s internal behavior —
  both are cheap fixes, but neither is worth making a support claim
  that nobody had actually asked for. This can be reopened by
  actually fixing those two issues and lowering the floor again —
  the test run against the floor version, described in AGENTS.md's
  "Required checks" section, is what would keep that claim honest
  going forward.

- D94 — DROPPING TWINE IS PART OF ADOPTING UV — DECIDED (owner,
  2026-07-30). Supports P21, which applies to development tooling
  just as much as to shipped packages. Adopting uv itself doesn't
  need its own entry: uv owning the Python environment and the
  release process is already stated in AGENTS.md's "Development
  environment" and "Required checks" sections, and the commit that
  made the change is the record of it. **What earns this entry is
  one specific contested call.** Keeping the `twine` tool around just
  for its `twine check` step was considered and rejected: that
  check's job is really about validating RST-formatted long
  descriptions, but this project's `readme` field points at
  `README.md`, and CommonMark markdown essentially has no input that
  fails that kind of validation; also, PyPI's own upload endpoint
  already validates and **rejects** bad package metadata on its own;
  a rejected upload doesn't consume the version number, so the cost
  of only finding out at upload time is just a retry; and
  `tools/check_dist.py` already is the project's real check on
  built artifacts. Running a pre-flight duplicate of a check the
  server already performs, against a file format that essentially
  never fails that check, is exactly the kind of redundant tooling
  P21 rules out. **This can be reopened if the readme ever stops
  being markdown** — switching to an RST-formatted description would
  bring back the original reason for `twine check`. The Poetry, PDM,
  and Hatch tools were also briefly considered and rejected: each of
  them manages a lock file, but none of them provisions the Python
  interpreter itself the way uv does, and Poetry specifically wants
  its own dialect of `pyproject.toml`, where this project already
  writes standard PEP 621 and PEP 735 configuration.

- D93 — A DEVICE OR ADAPTER NAME ONLY BECOMES PART OF THE
  FIRST-CLASS BLUEPRINT VOCABULARY IF IT APPLIES ACROSS MULTIPLE
  BACKENDS — DECIDED (owner, 2026-07-30), overruling **D91** the
  same day it was delivered, and removing D91's device-list field.
  Supports P8; adds a new principle, **P25**.

  THE RULE: a device or adapter name only becomes a proper,
  first-class blueprint field if it applies to more than one
  backend. Anything only one backend provides has to stay behind
  that backend's own settings section, `backend-settings` — still
  reachable, but at the cost of not being portable across backends,
  and that cost is exactly the pressure that should grow the shared
  vocabulary one name at a time, as real cross-backend need appears.
  Adding `virtio-console` and `virtio-net` as seed entries in that
  shared vocabulary was rejected under this same rule: including a
  name in the shared vocabulary just because one backend happens to
  expose it would record something that isn't actually true.

- D92 — THE `backend-settings` ESCAPE HATCH IS SUPPORTED; THE SAME
  CODE THAT RENDERS SETTINGS ALSO VALIDATES THEM; AND DECLARING
  SETTINGS FOR ONE BACKEND NARROWS BACKEND SELECTION TO THAT
  BACKEND — DECIDED (owner, 2026-07-30) and delivered the same day,
  retiring feature F28. Supports U22; P10, P11. `backend-settings`
  is now normative, documented in the blueprint field reference and
  in AGENTS.md.

  Three rulings made here, recorded because they don't fit anywhere
  else:

  - **The code that renders backend settings is also the code that
    validates them.** The `settings_args` function does both jobs —
    that's what guarantees a settings section a `create` command
    accepted is exactly the section a `start` command later applies.
    Two separate code paths for validating and rendering could drift
    apart from each other.
  - **Declaring a settings section for just one backend narrows
    backend selection to that backend, but only because the section
    exists — never because of what's inside it.** Declaring any
    settings at all for one backend pins the machine to that
    backend, without the actual setting values themselves being
    treated as requirements a backend must satisfy.
  - **Only the settings section belonging to whichever backend was
    actually assigned gets checked.** No adapter is allowed to judge
    another backend's settings vocabulary, so an unknown setting key
    is only rejected where an adapter actually owns that settings
    section.

- D90 — A RUN'S "OUTCOME" DESCRIBES ITS END STATE, A "WAIT" IS A
  POLL RATHER THAN A SUBSCRIPTION, AND A TIMED-OUT WAIT IS REPORTED
  AS BOTH A FAILURE AND A TIMEOUT AT ONCE — DECIDED (owner,
  2026-07-30) and delivered the same day, retiring feature F30.
  Supports U14; P11.

  These three rulings are really one decision about **what each of
  these words is allowed to promise**. A run's "outcome" describes
  the state the run ended in, not the path it took to get there. A
  "wait" works by repeatedly checking (polling), never by
  subscribing to be notified — so it can only ever report what it
  actually observed the last time it checked. And when a wait times
  out, it is reported as *both* a failure and a timeout at the same
  time, rather than being forced into one category or the other — a
  system that made a caller pick one classification would lose
  whichever half it didn't pick, which is exactly the kind of silent
  loss of information P11 forbids.

- D89 — THE SUCCESS/FAILURE CHECK USES TEXT RELIQUARY ITSELF WROTE
  AND READS BACK, AND ITS LIMITATION IS DOCUMENTED RATHER THAN
  HIDDEN — DECIDED (owner, 2026-07-30) and delivered the same day,
  retiring feature F26. Supports U14, U22; P6, P10, P11, G2.

  The `--check` flag asks the guest whether the last command
  signaled failure. Both sides of that check use **text Reliquary
  itself wrote into the guest and then reads back** — the marker
  text it looks for is a word Reliquary said, not something the
  command itself printed. That is what keeps this feature within
  the bounds of G2 and P18: Reliquary never tries to interpret
  meaning out of arbitrary guest output.

  **Its limitation is stated explicitly, rather than hidden** (P11):
  if a command is mistyped, DOS leaves the `ERRORLEVEL` variable
  unchanged, so `--check` reads that as success even though nothing
  actually ran. Recognizing DOS's own "Bad command or file name"
  message would mean maintaining a list of every possible spelling
  of that message across every guest — unbounded once localized
  copies of DOS are considered — exactly the kind of guessing P10
  rules out.

- D88 — THE AUTOMATIC-SEEDING FEATURE IS DELETED; U1 BECOMES TWO
  SEPARATE COMMANDS, AND P4 IS ABSOLUTE AGAIN — DECIDED (owner,
  2026-07-30). Supports P4, P18, U11. **Replaces the wording of
  U1** (rewritten in place under the same number, the same way D61
  handled a similar case), **clarifies U11**, and **changes D59** by
  removing its automatic-seeding option.

  Nothing resolves automatically out of the codex library anymore,
  on either the CLI or the API, and no flag brings the old behavior
  back — the blueprint and script directories a user manages are the
  only sources Reliquary looks in, a missing blueprint or script now
  fails outright rather than silently falling back, and the
  resulting error names the exact command to run —
  `rlq seed-blueprint <name>` — when the codex library actually holds
  that name. This rule now lives in **P4** and in AGENTS.md.

  - CONSIDERED AND REJECTED: **an alternative that added no new
    command-line flag**, reproducing both of the old modes of
    behavior while still keeping P4 absolute. Rejected because it
    would make automatic seeding a silent side effect of just
    resolving a name — a setting that can be turned on is a setting
    some CI pipeline eventually turns on, and a blueprint quietly
    supplied from the codex is a bug that only shows up later, on
    somebody else's machine.
  - The related rule, **"a codex blueprint is read directly from
    where it lives, rather than copied out first,"** is retired
    along with this: once there's no automatic fallback to the
    codex, there's nothing left to read that way, and an unseeded
    name is simply refused, not silently resolved through the codex.

- D87 — THE CODEX LIBRARY'S COMMANDS ARE NOT EXPOSED THROUGH THE
  PYTHON API; THIS IS PRINCIPLE P6'S FIRST NAMED EXCEPTION —
  DECIDED (owner, 2026-07-30). Supports P4, P18, U11; **changes
  P6**.

  The codex-related CLI commands — `seed-blueprint`, `seed-script`,
  `list-codex` — are **CLI-only**, and this exception is written
  down explicitly in [api.md](../docs/spec/api.md), rather than left
  as a silent gap a reader might mistake for an oversight. WHY: the
  codex library's contents can change between minor point releases,
  so it isn't something a program should be able to depend on
  programmatically — exposing these commands through the API would
  invite exactly the kind of fragile programmatic dependency the
  codex is designed never to promise. Writing the exception down
  explicitly is what keeps P6 a rule with exactly one documented
  exception, instead of a rule with an undocumented gap.

- D86 — TASKS GET THEIR OWN NUMBERED LIST; A RETIRED T-NUMBER IS
  NEVER REUSED, AND THE SEQUENCE'S STARTING POINT RECORDS ITS OWN
  HISTORY — DECIDED (owner, 2026-07-29). Supports P23. Applies
  D42's general numbering rule to tasks specifically.

  - CONSIDERED AND REJECTED: **reusing the lowest free number**, the
    same way machine ids are allocated. Rejected because an id that
    only ever refers to one thing at a time works fine for a
    machine, but is useless for a citation — if a struck task's
    number gets assigned to a new task later, any past reference to
    that number in this record becomes ambiguous.
  - The task-numbering sequence **starts at T8** because T0 through
    T7 were already used up by an earlier, per-list numbering scheme
    that had been restarted three separate times; starting the new
    sequence above those old numbers guarantees every T-number in
    this record always resolves to exactly one task.

- D85 — THE PROJECT'S USER-FACING BOUNDARIES ARE NOW CALLED
  "APPLICATION SURFACES," NUMBERED S1 THROUGH S8 — DECIDED (owner,
  2026-07-29). Supports P8, P23, P24. Normative wording lives in
  root [ARCHITECTURE.md](../ARCHITECTURE.md).

  Renaming what used to be called "interfaces" to **application
  surfaces**, and giving each one a number from S1 to S8, turns the
  check for "does this change need the surface-change process" from
  a *judgment call* into a **lookup**: a contributor now just checks
  whether their change touches one of the numbered items, instead of
  having to judge whether it "feels" user-facing. A check that
  requires judgment is a check that gets skipped by whoever's in a
  hurry — exactly the group this rule most needs to reach.

- D84 — SCRIPT-VALIDATION RULES ARE RENUMBERED FROM S1–S14 TO
  V1–V14, FREEING UP THE LETTER "S" — DECIDED (owner, 2026-07-29).
  Supports (none) — this is a pure renaming with no use case or
  principle requiring it. Recorded because **D85 needed the letter
  S**, and because these rule ids are visible to users, so this
  change is a breaking change, not just a cleanup.

  WHY THE VALIDATION RULES MOVED, RATHER THAN THE APPLICATION
  SURFACES. D85 assigns the letter **S** to the application
  surfaces, but S was already taken: the script language's static
  validation rules (in `.rlqs` files) had used that letter ever
  since dotted rule ids were introduced (D55). Having two separate,
  live "S-something" numbering systems at once was the one option
  ruled out immediately — `S6` would have simultaneously meant both
  a specific reference-checking validation rule and the application
  surface covering a run's returned output, and this very file cites
  both — exactly the kind of ambiguity the "never reuse a number"
  discipline exists to prevent. Between the two, the validation
  rules were the ones renumbered: application surfaces are the outer
  boundary the whole governance process checks changes against,
  while a validation rule is purely internal to the script language.

  "V" FOR VALIDATION, AND THE ACTUAL NUMBERS STAY THE SAME. V1
  through V14 map one-to-one onto the old S1 through S14 — only the
  letter changes, never the number — so any historical citation can
  be decoded just by substituting the letter (old S6 is now V6),
  with no lookup table needed. The old **S15, which D5 already
  retired** (it was the `results` header, removed along with the
  `stage`/`collect` commands), stays retired, and no V15 is ever
  issued — so a search for either S15 or V15 still points to
  exactly one thing (nothing currently in force).

  WHAT THIS COST TO CHANGE, ITEMIZED. Around 230 live references
  needed updating: the diagnostic-id lookup table in
  `script_nodes.py`; rule citations in `script_validation.py`,
  `script_parser.py`, `binding.py`, and `facts.py`, plus comments in
  the grammar file; the normative rule list in script-spec.md; 41
  conformance test fixtures (both the `# rule:` header inside each
  file and the filename prefix); four regular expressions used by
  the test harness; and both corpus README files. **Because these
  ids are visible outside the codebase** — a diagnostic message
  cites its rule id, and the conformance corpus's own tests assert
  on that id — this was done as a clean, one-time breaking change
  under P9, since the project is still pre-1.0: no alias for the old
  spelling, no period of supporting both spellings — every reference
  was updated in one single change, with the full test suite passing
  afterward (1110 tests, with the one already-accepted skip).

  A THIRD MEANING, FOUND ALONG THE WAY AND HANDLED SEPARATELY. The
  blueprint corpus README used `S2` and `S3` to mean **milestone
  stages** — vocabulary that's been unused since D33 — not rule ids
  at all. These were rewritten as plain words ("the second stage")
  instead of being renumbered, because left as-is, they would have
  looked like references to application surfaces the moment D85 took
  effect. This was caught by reviewing every match of the search
  pattern before actually running the rename — exactly why that kind
  of review is worth doing.

  FILES TOUCHED BY THIS CHANGE: this entry and the glossary at the
  top of this document; the normative
  [script-spec.md](../docs/spec/script-spec.md) (its rule list and
  the section on how rule ids work); `script_nodes.py`,
  `script_validation.py`, `script_parser.py`, `script_grammar.lark`,
  `binding.py`, `facts.py`; the script conformance corpus (41
  fixtures renamed and rewritten, plus its README) and the blueprint
  corpus README; the test files `test_script_corpus.py`,
  `test_script_spec_conformance.py`, `test_script_validation.py`,
  `test_script_timing.py`, `test_script_nodes.py`,
  `test_script_parser.py`, `test_binding.py`, `test_facts.py`,
  `test_dry_run.py`; [AGENTS.md](../AGENTS.md); and the CHANGELOG's
  unreleased section.

- D82 — THE PROJECT IS LICENSED GPL-3.0-ONLY, THE OPTION TO
  RELICENSE COMMERCIALLY LATER IS RESERVED, AND CONTRIBUTORS ASSIGN
  THEIR COPYRIGHT — DECIDED (owner, 2026-07-29). Supports nothing —
  no use case or principle required a specific license; this was the
  owner's own call. The policy is written normatively in AGENTS.md,
  `CONTRIBUTING.md`, and `CLA.md`.

  The rule that governs everything downstream from this: **when
  vetting any external code or dependency, check it against the
  standard of a commercial dual license — but don't publicly say
  more than the word "relicensing."** The question to ask about any
  external source is *could this ever ship inside a proprietary
  product?* — never *is this merely GPL-compatible?*, which has a
  comfortable "yes" far more often, and is therefore the wrong
  question to be asking. Judging this correctly costs nothing at the
  moment a dependency is first considered, and cannot be fixed later
  at any cost once it's already in use.

  - CONSIDERED AND REJECTED: **using AGPL-3.0-only instead of
    GPL-3.0-only.** This would close one narrow loophole (the
    network-use case), but at the cost of discouraging the adoption
    the project needs more.
  - CONSIDERED AND REJECTED: **requiring contributors to assign
    copyright with no fallback option.** Some legal jurisdictions
    don't allow copyright assignment, so the actual rule falls back
    automatically to an exclusive, sublicensable license grant in
    those cases.

- D81 — "STATICALLY REACHABLE" ONLY MEANS THE GUEST HASN'T MADE A
  CHOICE YET; AND REMOVED COMMANDS FROM THE CHECK FAMILY ARE
  ACTIVELY GUARDED AGAINST, NOT JUST DELETED — DECIDED (owner,
  2026-07-29) and delivered the same day. Supports P6, P9, P11.

  Whether a menu handler's body actually runs is a decision the
  **guest** makes at runtime, not something the script's static
  structure decides — so no static analysis pass can ever promise a
  given handler body will run. The dry-run report instead counts
  what it *couldn't* statically reach, rather than implying a
  completeness the analysis can't actually have.

  **Deleted command spellings are actively guarded against, not just
  deleted from the code** — a dedicated test enforces that they stay
  gone. A name that's deleted without a test guarding against its
  return tends to come back anyway, through autocomplete or through
  someone half-remembering the old name — and when it comes back
  that way, it looks like a new feature request instead of a
  regression.

- D80 — A DRY RUN REJECTS EXACTLY WHAT A REAL `create` WOULD
  REJECT, AND IT NEVER COMPUTES A HASH — DECIDED (owner, 2026-07-29)
  and delivered the same day. Supports U7; P7, P10, P11. Normative
  in [cli.md](../docs/spec/cli.md).

  A dry run performs the same evaluation as a real run, just without
  committing anything: it rejects whatever a real `create` would
  reject, at the exact same point a real `create` would reject it —
  with two deliberate exceptions, and each exception exists because
  the dry run genuinely **cannot** do that check, not because of a
  judgment call about how serious the issue is. First, an unbound
  location value is reported as "not evaluated" rather than checked,
  because a dry run must never prompt the user for input. Second,
  when a `backend=` value is given, a backend that isn't installed is
  reported rather than raised as an error, because that flag's whole
  purpose is asking whether the blueprint *would* work on that
  backend, if it were available.

  **A dry run never computes a file hash.** The `cached` field in
  its output only reports whether a file is present, not whether its
  contents have been verified. Actually verifying the hash would
  make what's supposed to be a cheap, read-only check pay a real
  computational cost, and it would report a stronger guarantee than
  what the flag is actually being asked to answer.

- D79 — FEATURE F11 IS SPLIT IN TWO; THE `--dry-run` FLAG PRODUCES A
  DOCUMENT, NOT A LIVE STREAM — DECIDED (owner, 2026-07-29).
  Supports U7; P6, P9, P10, P11. Normative in
  [cli.md](../docs/spec/cli.md).

  Adding `--dry-run` turns a command's output from a live stream
  into a **document**: `--json` output becomes valid for the first
  time, because it now prints exactly what the underlying function
  call returns, while `--progress` and `--display` are refused,
  because a plan being evaluated has no live stream to render and no
  window to show it in.

  - CONSIDERED AND REJECTED: **adding `--dry-run` to just one
    command instead of the whole family.** Rejected because being
    pledged doesn't mean being scheduled for a specific release — the
    flag has to mean the same thing everywhere it appears, or it
    doesn't mean anything reliable at all.
  - CONSIDERED AND REJECTED: **reporting only the part of the script
    that could be statically determined, and silently leaving out
    the rest.** Rejected because a reader would have no way to tell
    what had been left out, and the counts in the report would stop
    actually describing the script the caller wrote. Instead, the
    report states its own limitation explicitly (for example, `3
    statements not statically reachable`) — applying P11's "state the
    limit, don't hide it" rule to the dry-run report itself.

- D75 — A PROMPT BEING ON SCREEN DOES NOT MEAN A COMMAND FINISHED;
  OUTPUT THAT CAN'T BE ATTRIBUTED TO THE COMMAND IS TREATED AS A
  FAILURE — DECIDED (owner, 2026-07-28) and delivered the same day.
  Supports U12, U14, U9; P11.

  `wait_ready` returns as soon as a prompt appears on screen — so if
  `exec`'s completion check only looked for a prompt, it would be
  satisfied by the prompt that was already there from booting, and
  would hand back the boot's own leftover output as if it were the
  command's output. So completion now requires actual evidence that
  **this specific** command finished: either its own echoed text on
  screen, or a screen that has visibly changed since the command was
  sent.

  And in the case where the command's echo was never actually seen
  at all, the rows above the prompt are **refused outright, rather
  than returned as a guess**: returning a plausible-looking but
  wrong batch of somebody else's text is worse than returning an
  error, because nothing further down the line has any way to tell
  that it's wrong.

- D72 — PRINCIPLE P10 IS SHARPENED: WHAT IT FORBIDS IS GUESSING, NOT
  READING; A GUEST TELLING US SOMETHING ABOUT ITSELF COUNTS AS AN
  OBSERVATION — DECIDED (owner, 2026-07-28) and took effect the same
  day. Supports U14, U20; P11, P16.

  P10 forbids **guessing**, not reading. A value the guest itself
  states about itself is an observation, and it is fine to use it;
  what is actually forbidden is inferring something from how it
  looks — for example, guessing a filesystem type from a screen's
  appearance, or guessing a platform from a banner's text. This
  distinction matters because a naive reading of the rule ("never
  ask the guest anything") would also forbid reading things that
  don't involve the guest at all, like a disk image's file format or
  a file's size on the host — which are actually the most reliable
  facts available, since they involve no guessing whatsoever.

- D70 — BLUEPRINT VALIDATION ERRORS NOW REPORT A FILE LOCATION,
  TAKEN DIRECTLY FROM THE PARSED DATA — DECIDED (owner, 2026-07-28)
  and delivered the same day. Supports U4, U11; G6; P6, P8.

  A validation error now names where in the blueprint file the
  problem actually is, and that location comes directly from the
  **already-parsed data structure**, not from a second, separate
  scan of the raw text looking for a matching line number. A second
  scan over the source text to locate a line number could disagree
  with what the parser that actually produced the error saw — and a
  diagnostic that points at the wrong line is worse than one that
  points nowhere at all.

- D69 — RUNNING A BINARY-SEARCH EXPERIMENT TO TUNE THE
  INPUT-PACING DEFAULT IS REJECTED; THE 0.1-SECOND DEFAULT IS A
  DELIBERATE CHOICE, NOT A PLACEHOLDER — DECIDED (owner,
  2026-07-28). Supports U14, U20, U12; G1. **Changes the stated
  reasoning behind D60**.

  **What is rejected here is the *method* of tuning this number, not
  the number itself.** Setting up an experiment that narrows down an
  "ideal" default value through repeated measurement treats the
  pacing delay as if it were an empirical fact about hardware
  timing — when it is actually a floor value chosen for a specific
  reason. The real variability comes from the *readiness mechanism*
  — whether an installer has finished arming its keyboard handler,
  whether a shell has actually entered its input loop — not from how
  fast the screen draws, so measuring paint speed would be measuring
  the wrong thing entirely, while looking scientifically
  authoritative doing it.

  [This entry's reasoning was later amended: it originally left
  nothing responsible for covering variance in paint speed. That is
  now covered by feature **F48**'s `stability=` gate instead —
  leaving this pacing default responsible only for readiness timing,
  which is what makes 0.1 seconds an honest, deliberately chosen
  floor value rather than one pretending to cover more than it
  does.]

- D68 — PRINCIPLE P3 IS SHARPENED TO APPLY ON BOTH SIDES OF THE
  HOST/GUEST BOUNDARY; THE ACTUAL LINE IS "IS IT AN AGENT," NOT
  "WHICH MACHINE IS IT ON" — DECIDED (owner, 2026-07-28) and took
  effect the same day. Supports P3.

  Reliquary only makes use of agents that guests already have
  installed, and **builds none of its own**, on either side of the
  host/guest boundary — what is actually refused is *writing new
  agent software*, not a rule about which machine the code happens
  to run on. Written as a rule about which side of the boundary code
  runs on, the principle would have wrongly forbidden ordinary
  host-side helper code that isn't an agent at all, while wrongly
  allowing a guest-side helper that clearly is one.

  Also rejected here: rewriting P3 speculatively, just to cover a
  hypothetical case with no real example behind it. This sharpening
  was only made because an actual, real case tested the existing
  wording and found it wanting.

- D67 — RULINGS MADE WHILE EXTRACTING THE BACKEND-ADAPTER BOUNDARY:
  A GENERIC WAY TO IDENTIFY A VM, NO NETWORK PORT VISIBLE ABOVE THE
  BOUNDARY, AND A STUB ADAPTER THAT CLAIMS NO CAPABILITIES —
  DECIDED (owner, 2026-07-28). Supports U7, U1; P7, P11, P12.
  Normative in AGENTS.md, under "VM ownership."

  - **Nothing above the adapter boundary is allowed to read a
    network port directly.** Keeping `port=` available as an
    ordinary parameter was rejected: a port number is specific to
    how one particular adapter (QEMU) exposes a connection endpoint,
    and any calling code that can name a port directly is code
    that's really been written against QEMU specifically, not
    against the general adapter interface.
  - **A stub adapter (one not yet fully implemented) claims none of
    the capabilities a real adapter would.** This means backend
    assignment skips over it even when that backend happens to be
    installed on the host. If a stub claimed capabilities it doesn't
    actually have, the failure would only be discovered later, when
    actually trying to create a machine — exactly the kind of
    upfront honesty P11 requires.

- D66 — THE DEFAULT BACKEND PRIORITY ORDER RANKS BACKENDS BY HOW
  SCRIPTABLE THEY ARE WITHOUT A GUEST AGENT — DECIDED (owner,
  2026-07-28). Supports U7, U12, U1; P3, P11. This settles F2's
  "decide first" question, resolved as part of the same act that
  pledged the feature, so the feature reached the pledged shelf with
  no open question left attached.

  THE ORDER: **QEMU, then VirtualBox, then VMware Workstation, then
  Hyper-V**, used for default backend assignment whenever a
  blueprint doesn't specify a `backend` explicitly. This order only
  breaks ties among backends that are already both installed *and*
  capable of running the requested machine — assignment walks down
  the list and picks the first backend that's both — so this
  ordering never substitutes for an actual capability check (P11),
  and specifying `backend` explicitly skips this list entirely.

  WHY THIS RANKS BACKENDS BY AGENTLESS SCRIPTABILITY. The original
  proposal said "best scriptability"; refined, the actual criterion
  is scriptability *without a guest agent installed*, and the reason
  is about *when* the backend choice actually gets made. Backend
  assignment happens at machine creation time, before any guest
  operating system even exists yet, and the installation process
  that follows is necessarily agentless — P3's overall design has
  agentless operation doing the work of preparing a guest, with a
  native agent only taking over once one has actually been installed
  inside it. So a backend's story around agent support is worth
  nothing at the moment assignment happens, and for the guests that
  U12 and U1 actually drive — DOS-era systems — it's worth nothing
  ever, since those systems stay permanently agentless.

  THE RANKING, BACKEND BY BACKEND. QEMU ranks first based on
  evidence, not preference — it's the only adapter with a complete
  control-plane implementation, and feature F2 exists specifically
  because the adapter boundary was designed by reading off QEMU's
  implementation. VirtualBox ranks second: its `VBoxManage`
  command-line tool covers machine lifecycle, keyboard input by
  scancode, screenshots, and serial-port redirection — the closest
  match to the toolset scripts already depend on, with VNC access
  available behind VirtualBox's separate extension pack. VMware
  Workstation ranks third: it exposes VNC, but has no comparably
  rich scancode-based input surface. Hyper-V ranks last, and not out
  of bias — it has no VNC support at all, which is a genuine missing
  capability, not just a different implementation choice — leaving
  it with no agentless way to view or control the display at all,
  which is also why F5 deliberately keeps it last for the same
  reason.

  CONSIDERED AND REJECTED: ranking backends by how commonly they're
  already installed on a typical host. U7's own wording practically
  invites this — it mentions "a Windows laptop with Hyper-V already
  enabled" — but on the single most common host setup, that would
  default to the *least* scriptable backend, which is the wrong
  outcome for the one thing this default has to serve: U1's promise
  of reaching a usable machine with a single command, via U12's
  unattended install process. Host ubiquity is already accounted for
  in the right place — when checking which backends are actually
  available — it just isn't used to break ties among the ones that
  are.

  ALSO REJECTED: having no default at all, and requiring `backend`
  to always be specified explicitly. U7 promises that a machine
  materializes on whatever capable backend the host happens to
  offer, and U1 promises the whole journey is a single short
  command; requiring an explicit backend choice would break both
  promises.

  TWO OF THE FOUR BACKENDS ARE STILL STUBS as of feature F2 (its
  fourth work item raises `NotImplementedError` for them), so the
  tail end of this ordering **records intent now**, ahead of
  actually being working, shipped behavior — the same pattern
  already used for F3's VDI format table, and honest for the same
  reason: the record states what the project intends before the code
  can actually back it up.

  FILES UPDATED: pledged/FEATURES.md (F2's "decide first" question
  becomes settled, final text) and pledged/design/backend-adapter.md
  (the assignment section's open question becomes this ordering,
  along with the reasoning behind each backend's position).

- D65 — A PLEDGED USE CASE MAKES A FEATURE ELIGIBLE TO BE PLEDGED,
  BUT DOESN'T PLEDGE IT AUTOMATICALLY; FEATURE F2 IS PLEDGED AS ONE
  WHOLE PIECE — DECIDED (owner, 2026-07-28). Supports U7 (pledged in
  this same round), P11. Pledging U7 and F2 are themselves routine
  lifecycle steps and don't get their own entries (D63) — U7's
  justification was already written out in its 2026-07-23 draft and
  didn't need to be remade. What follows is the actual rulings made
  while doing this.

  THE SIZE DECISION. F2 was checked against D42's rule that a
  feature must fit in one sprint, and was pledged **as a single
  whole feature**, keeping its original number rather than being
  split up and retired piece by piece. Its scope is bounded in two
  separate ways: by the working code that already exists — QEMU is
  the only backend with a fully implemented control plane, so the
  adapter boundary is being extracted from an existing
  implementation, rather than designed from scratch — and by a clear
  test for when it's done: all QEMU interaction routed through the
  new adapter API, with the FreeDOS install script still passing
  unchanged. Four of its five work items are small (auto-discovering
  backends, default backend assignment, stub adapters for the rest,
  and verifying VM ownership); the adapter API itself is the bulk of
  the work. CONSIDERED AND REJECTED: splitting out just the
  discovery-and-assignment part as a smaller feature on its own.
  This would make the first commitment smaller, but at the cost of
  F2's own number, which backend-adapter.md and several other
  entries already cite — and the pieces aren't independently useful
  anyway: discovering backends with no adapter boundary to assign
  machines into doesn't actually deliver anything on its own.

  NECESSARY, BUT NOT SUFFICIENT. `proposed/FEATURES.md` had said
  that pledging a feature's underlying use case "is what returns the
  feature to a numbered arc" — which reads as though pledging the
  use case is enough on its own. That reading is rejected. Pledging
  a use case only makes a feature **eligible** to be pledged — it
  doesn't pledge the feature itself; each feature still needs its
  own separate decision to move. F3 and F5 both cite use case U7,
  and both stay in `proposed/` even after U7 is pledged — this is
  the rule actually being tested, not an oversight. The reverse rule
  is unchanged, and is why this decision round makes two separate
  moves: a feature still can't be pledged ahead of the use case that
  justifies it — that was the exact mistake D61 corrected, and it's
  why F2 waited five days before being pledged.

  F5's MISSING JUSTIFICATION SHRANK, BUT DIDN'T FULLY CLOSE HERE.
  [It did fully close later, on 2026-08-21: D110 settles U5 as the
  justification for F5's GUI-automation half.] The 2026-07-27 review
  found F5 to be the one feature still lacking full traceability
  back to a use case. Pledging U7 covers part of that gap — U7
  explicitly names Hyper-V, so the last two backend adapters now
  rest on a pledged use case — but it doesn't cover the rest: the
  VNC control plane, the landmark-asset spec, and pointer input all
  still answer to no use case that's either in force or pledged, and
  simply being able to create a machine on the host's hypervisor
  says nothing about being able to drive a graphical installer
  through it. This is recorded here as a finding, not as a full
  ruling: the remaining gap splits exactly where D42's size rule
  would naturally split it, which is left for whoever formally rules
  on F5 to use.

  FILES UPDATED: pledged/USE-CASES.md and pledged/FEATURES.md (U7
  and F2 are added; neither shelf is empty anymore);
  proposed/USE-CASES.md and proposed/FEATURES.md (both entries
  removed; also updated: the shared preamble for F2 through F6, F3's
  and F5's status notes, and F7's two open findings, one of which
  this decision closes); planning/README.md (the directory map's
  design-document rows); `planning/pledged/design/backend-adapter.md`
  (moved from `proposed/design/`, since a design document moves
  along with whatever it documents — D61 — which leaves that
  directory empty as of this decision); and the links to
  backend-adapter.md in root ARCHITECTURE.md and
  planning/design/guest-communication.md.

- D64 — USE CASE U4 DOES NOT COVER U5's PARAMETERIZATION MECHANISM;
  U5 IS SPLIT AT THE POINT WHERE DELIVERY ACTUALLY REACHED —
  DECIDED (owner, 2026-07-28). Supports nothing — ruling on a use
  case is itself what creates demand for other things, not something
  that needs its own supporting citation.

  A use case states **what the user actually needs**, never the
  specific mechanism used to deliver it — so U4 can't be read as
  already covering U5's parameterization feature just because
  parameterization happens to be a good way to serve U4. Instead, U5
  is split at the exact point delivery actually reached: the part
  that was actually delivered becomes its own use case, **U21**,
  while the part still waiting on GUI automation to exist stays in
  `proposed/`. Splitting exactly at the delivery line is what keeps
  the list of active use cases accurate — a use case marked "in
  force" that's only half actually delivered would make the root
  use-case list assert something the code doesn't actually support.

- D63 — A ROUTINE LIFECYCLE STEP DOES NOT GET ITS OWN ENTRY; THE
  PRACTICE OF WRITING "PROMOTION" ENTRIES ENDS — DECIDED (owner,
  2026-07-28). Supports nothing directly — this is a rule about how
  this record itself is kept, not required by any numbered entry;
  it brings this file in line with the project's general
  cross-project governance standard for decision records, which has
  no local number of its own to cite.

  WHAT STARTED THIS (in the owner's words): this record was getting
  large, and *"we need a record of any architecture decisions in
  what they promoted, but I don't think we need a decision record of
  the promotion itself. That status is self evident."* The general
  governance standard already says exactly this — the move itself is
  the act, the commit that makes it is the record, and there's no
  separate log that needs to be kept in sync with it — but this file
  had been keeping one anyway: the group of "promotion" entries
  (D37, D46, D47, D49, D51, D57, plus the pledging- and
  arming-related sections of D61 and D62) runs to roughly 650 lines,
  about a ninth of the whole file, written while this governance
  process was still being figured out, and mostly just restating
  what an item's location and its git history already show.

  THE RULE, GOING FORWARD. Proposing, pledging, promoting, or
  delivering something: none of these get their own entry. Evidence
  that delivery actually happened — the clause-by-clause case that a
  use case is genuinely met, the kind of thing D46 used to do —
  belongs in the commit message of the commit that makes the move,
  right alongside the act it's evidence for. What still earns an
  entry is an actual RULING made along the way: a disputed clause
  read one specific way, with the other reading rejected (like
  D46's ruling on its media-swap clause), a scope deliberately
  widened (like D46 widening from two cases to four), or a pledge
  found to have been made by accident and then withdrawn (the entire
  subject of D61). Record just the ruling, kept short — the entry
  states what was actually decided and never narrates the promotion
  process around it; under this rule, D61 would be twenty lines, not
  150. A decision whose entire conclusion is simply "pledge this" is
  untouched by this rule: that kind of entry is recording an
  argument, and the pledge is just its natural consequence.

  WHAT THIS RULE DOES NOT DO. Nothing written under the old practice
  is moved, retired, or rewritten because of this decision. Those
  existing entries stand exactly as written, under the usual rule
  about preserving spellings, and their numbers stay fully citable
  (D62 still cites D57; D46 still applies D34). D34's rule that
  promotion happens automatically on delivery is also untouched —
  promotion still happens automatically, it just stops being
  separately written up here.

  CONSIDERED AND REJECTED: retroactively shrinking or archiving the
  existing group of promotion entries. Moving an entry to the
  "retired" section keeps it intact and saves no space; rewriting it
  is forbidden by this file's own rule against altering the
  substance of past entries; and deleting it outright would break
  the guarantee that a D-number is a permanent handle. Splitting old
  entries out, whole and with their numbers intact, into a separate
  companion file is the one way this could be shrunk without
  breaking those rules — but that's left as its own, separate
  decision, not made here.

  FILES UPDATED: the cross-project governance standard document (its
  rule about records and its "the move is the act" clause) and its
  DECISIONS.md template; this file's own preamble at the top.
  Nothing else in the repository changes — this rule only governs
  entries written from now on.

- D60 — INPUT PACING IS A CONTROL-PLANE SETTING, NOT A SEPARATE
  `delay` VERB IN THE SCRIPT LANGUAGE — DECIDED (owner, 2026-07-24)
  and delivered 2026-07-27. Supports U14, U20, U12. Normative in
  [script-spec.md](../docs/spec/script-spec.md).

  THE DISTINCTION THAT KEEPS A `delay` VERB OUT OF THE LANGUAGE: a
  `delay` verb would be a pause an author deliberately *inserts as a
  step*, sitting between two other steps, encoding a guess about how
  long something should take. "Pacing," by contrast, is a property
  of *how input gets delivered* — the gap the control plane already
  takes before sending its very first key event, whether or not any
  script ever mentions it. The language adds the ability to tune
  that existing gap, not the ability to insert a new one.

  **The built-in 0.1-second pacing value is a floor, not an estimate
  of typical timing.** The variance it was originally justified by —
  how fast the screen redraws — is not actually what it's meant to
  cover. What actually determines when a guest is ready to *receive*
  input is the readiness mechanism, and no single fixed number can
  serve every possible screen — exactly why the per-phase and
  per-statement override settings carry most of the real weight
  here.

- D61 — EVERYTHING ON THE PLEDGED SHELF IS RE-CHECKED, ONE ENTRY AT
  A TIME, RATHER THAN CARRIED OVER AUTOMATICALLY — DECIDED (owner,
  2026-07-27). Supports U8, U11, U12, U13; P8. **Changes D44** (only
  its sentence about clearing the shelf) and **retires the exception
  D42 made for F1**. As a result of the recheck: F1, U2, and U6 are
  withdrawn; U1 is condensed and promoted.

  THE FINDING THAT MADE THIS AN ENTRY RATHER THAN FOUR ORDINARY
  LIFECYCLE MOVES: **the items on the pledged shelf ended up there
  without anyone actually deciding to pledge them.** Before the
  pledged shelf existed as a concept, each entry recorded its own
  status as a single word, where *accepted* only ever meant "the
  argument for this has been won." When the project restructured
  around a pledged shelf, each old entry was correctly filed
  according to its own word — but feature F1 had no such word to be
  filed under, so it ended up created directly on the pledged shelf
  simply because its work items had nowhere else to go. Then D44
  changed what being on the pledged shelf actually *means* — from
  "there's agreement on this" to "there's a commitment to actually
  deliver this" — and cleared out everyone currently on the shelf in
  a single sentence when it did. Nobody had ever actually decided to
  build the screen recorder that F1 describes. **Whenever what a
  shelf claims about its contents changes, everything already on it
  needs to be individually re-checked against the new meaning — it
  doesn't just carry over automatically.**

  - CONSIDERED AND REJECTED: **retiring U1 as superseded by the
    newer U11 through U13.** Rejected because U1 names a command
    that nothing else currently in force actually names.
  - CONSIDERED AND REJECTED: **pledging U8 first**, as an earlier,
    now-abandoned plan had assumed. Rejected because doing so would
    commit the project to actually building an export feature, which
    nothing currently justifies.

- D59 — EVERY WORKING DIRECTORY REBUILDS CAN LIVE IN ITS OWN
  CONFIGURABLE LOCATION; PRINCIPLES P12 AND P4 ARE UPDATED TO MATCH
  — DECIDED (owner, 2026-07-27) and delivered the same day. Supports
  U17, U14, U4; P4, P6. The six placeable directories and the rules
  for how their locations are derived are normative in
  [asset-resolution.md](../docs/spec/asset-resolution.md) and
  AGENTS.md.

  **The lasting part of this decision is that "containment" stopped
  being about directory structure.** With six independently
  configurable root directories, Reliquary can no longer honestly
  claim that everything it writes lives "under one home directory,"
  so P12 was updated to state only what it can actually still
  guarantee: Reliquary only ever writes to locations it was
  explicitly told to use, never next to its own installed module
  code, and never into a source code repository.

  The part of this decision about automatically seeding files was
  **later retired by D88**, which restored P4 to being an absolute
  rule again; the automatic-seeding alternative that had been kept
  here was itself rejected because it made seeding files a silent
  side effect of simply resolving a name, rather than something
  explicitly requested.

- D58 — THE FOUR ERROR CLASSES APPLY TO EVERY COMMAND, NOT JUST TO
  RUNNING A SCRIPT — DECIDED (owner, 2026-07-27). Supports U9, U14;
  P6, P7, P11. Normative in AGENTS.md.

  What determines which error class applies **never depends on
  whether a script is even involved**: it depends only on whether
  the problem is in the authored input itself (`StaticError`), on
  the surrounding environment not meeting a requirement
  (`PreflightError`), or on the actual work failing while it ran
  (`RunFailure`). So a malformed blueprint file is always a
  `StaticError`, and trying to act on a machine that doesn't exist
  is always a `PreflightError`, no matter which command triggered
  it. If this taxonomy had instead been defined around the phases of
  running a script specifically, every command that isn't about
  running a script would have been left guessing which class applies
  to it by loose analogy.

  A proposed fifth error class, just for cancellation, was rejected,
  because its entire population would be a single kind of event;
  `RunCancelled` is instead a sibling class alongside `RunFailure`,
  never a subclass of it.

- D57 — PRINCIPLE P16 IS PLEDGED; THE TEST FOR IT IS WHETHER A
  CALLER WOULD OTHERWISE HAVE TO REBUILD RELIQUARY'S OWN LOGIC
  THEMSELVES — DECIDED (owner, 2026-07-27). Supports U14, U20; P11.

  THE TEST, which is the reusable part of this decision: a
  capability deserves to become a principle when not having it
  forces **a caller to reproduce Reliquary's own internal model of
  something outside of Reliquary itself.** Not just when it would be
  merely convenient, and not just when Reliquary could plausibly be
  the one to own that logic — the actual bar is that a caller is
  currently forced to re-implement something Reliquary already
  understands internally, and will inevitably get it wrong in ways
  Reliquary itself has no way to see or catch.

  [P16 later gained an explicit exception in **D108**: a machine's
  file content is deliberately out of scope for Reliquary by design,
  so the test above only applies to what a machine actually *is* —
  its lifecycle, its drives, its media, its screen, its input, and
  its returned values.]

- D55 — THE PLAN TO ADD A "REASON" EXPLANATION TO EACH VALIDATION
  RULE IN script-spec.md IS DROPPED — DECIDED (owner, 2026-07-27,
  closing out the Language backlog). Supports P8, P23. An earlier
  spec-writing round on 2026-07-21 had deliberately left one
  editorial idea open: adding a rationale blockquote explaining the
  "why" behind each rule in script-spec.md. That idea is now
  rejected outright rather than finished. This is recorded here so
  it doesn't get raised again as though it had simply been
  forgotten — it was considered and turned down.

  **PART OF THE ARGUMENT IS THAT ITS ORIGINAL DEFINITION IS ALREADY
  LOST.** The entry that first proposed this idea points to *"the
  review output — workflow `wf_ac5f89b4-402` journal"* as its
  source, but a workflow run id like that only resolves within its
  own session — no copy of that journal exists anywhere in this
  repository. Three other entries also depend on those same
  journals, and none of them are readable anymore. So actually
  finishing this sweep would mean inventing what it was supposed to
  look like from scratch, not completing existing work — there
  isn't even a single example `Reason` blockquote anywhere in the
  file to infer the intended format from.

  THE SUBSTANTIVE REASON, which holds up even if that journal turned
  up again tomorrow: **the spec already points to its own
  reasoning.** It already carries eleven D-number citations at the
  places that matter, and a D-number is this project's whole
  citation system, by design. Adding a rationale blockquote to every
  rule would replace that pointer with a *copy* of the reasoning
  instead — and D52 already deleted an entire section of TASKS.md
  over exactly this problem with copies: a summary kept next to the
  thing it summarizes drifts out of sync over time, and a reader has
  no way to tell when that's happened. The cost of doing this scales
  badly too: 51 separate rule sections, no automated test to catch
  drift, and a normative specification document is the worst
  possible place to put prose that can quietly stop being true.

  THE ACTUAL NEED THIS WOULD HAVE SERVED IS REAL, AND IT'S ALREADY
  MET. A reader evaluating a proposed change does need to know why a
  rule exists in the first place — and that's exactly what the
  interface-change process already sends them to this DECISIONS.md
  file to find, which the D-number citations already in the spec
  make reachable in a single click. Wherever a rule's reasoning
  currently *isn't* reachable that way, the right fix is to add a
  citation, not to write a paragraph of prose.

  EVIDENCE FROM THE SIX DAYS SINCE: script-spec.md has since gone
  through a full realignment, three delivered milestones, and this
  week's audits, and nobody has missed having these blockquotes.

  FILES UPDATED: this entry; TASKS.md (the "Language" backlog item
  is dropped, along with the related error-id task it carried — that
  part is a genuine defect and has been re-entered under the
  Defects section, with the actual index still deferred to the 1.0
  release, as the spec's existing wording already states).
  script-spec.md itself is unchanged.

- D54 — WHETHER `@` OR `$` IS USED IS ALREADY OBSERVABLE FROM THE
  RUN'S OWN OUTPUT; DESIGN EXAMPLE 06 IS CLOSED — DECIDED (owner,
  2026-07-27). Supports P5, P8, G6. The last open question in
  [06-media-label-vs-item](design/script-examples/) is now settled,
  and the example file itself is deleted — the design-examples
  catalogue only holds problems that are still genuinely open.

  THE QUESTION. The `insert` script statement takes its media
  reference through either of two sigils — `insert cdrom0
  @freedos-livecd` or `insert floppy1 $supplemental-disk` — and on
  the page, both forms look equally concrete, even though they mean
  different things: `@` names one specific item directly, while `$`
  defers the actual choice to whatever happens at run time. A reader
  has to go find the property's own declaration elsewhere just to
  know which kind of `insert` they're looking at.

  SETTLED EXACTLY AS THE EXAMPLE ITSELF HAD GUESSED IT MIGHT BE:
  **this is inherent to the design, and it's already observable.**
  Deferring the choice is the entire *point* of using a property, so
  the documentation page can never state in advance which media a
  `$`-prefixed insert will actually mount, without eliminating the
  feature that makes properties useful. What the example asked for
  instead — some way to see the actually-resolved item at the moment
  the insert happens — turned out to already exist: the runtime
  resolves the property's binding before it builds the record of
  what the statement did, so `insert floppy1 $supplemental` produces
  an event recorded as `insert floppy1 @win98-cd` — the resolved
  item name, written with the definite `@` sigil. The observability
  half of this question was actually already answered by milestone
  9's run-event stream, without anyone at the time noticing that it
  answered this specific open question.

  THIS WAS MADE OFFICIAL BEFORE THE EXAMPLE WAS DELETED, which is
  why this gets a decision number instead of being a routine
  cleanup. This behavior already shipped, but **nothing had ever
  made it an official, guaranteed rule**, so it remained free to
  change later, and the example couldn't be closed out while
  depending on behavior that wasn't guaranteed. script-spec.md's
  description of the run event stream now states this explicitly as
  a rule: an `insert` statement's recorded event names the media it
  actually mounted, and a `$`-prefixed argument reports the resolved
  item's name, not the property's own name. This is the same
  pattern as D50's promotion of format stability to a rule —
  existing behavior becoming something the implementation is now
  held to (supporting P5: the event stream is where any run-to-run
  difference becomes visible, and no part of the system is allowed
  to report something it doesn't actually carry).

  A GAP IN TEST COVERAGE WAS CLOSED ALONG WITH THIS. Nothing had
  actually tested this behavior before. The test suite had a test
  for an *unbound* `$` insert correctly failing, but no test at all
  for a *bound* one correctly reporting its resolved name — so the
  very behavior the spec now requires had been resting on a single,
  never-examined line of code. It now has a real test.

  THE EXAMPLE'S OTHER TWO OPEN QUESTIONS were already closed
  earlier: the question of splitting "label" from "item" died along
  with embedded media blocks (2026-07-22), and rejecting an
  `@`-reference to a name the media namespace doesn't define was
  resolved on 2026-07-27 as the ordinary preflight-check defect it
  had always really been, rather than as the language-design task it
  had originally been filed under.

  FILES UPDATED: this entry; script-spec.md (the "run event stream"
  section and its bullet about the `insert` action);
  design/script-examples/ (example 06 deleted; the README's table
  and its note about resolved examples updated);
  test_script_runner.py (a new test for reporting the resolved
  name). No CHANGELOG entry: the actual behavior is unchanged, only
  its official status.

- D53 — BARE WORDS IN A SCRIPT STAY TYPED BY THEIR POSITION IN THE
  STATEMENT; TASK [08]'S PROPOSAL IS REJECTED — DECIDED (owner,
  2026-07-27). Supports P8, P23, G6.

  The proposal was to reserve a fixed list of keywords, so that a
  bare word in a script could be understood on its own, without
  needing to know its position in the statement. This is rejected: a
  bare word's position in the statement already, unambiguously,
  tells you what kind of thing it is, and a reserved-keyword list
  would be a piece of language surface that only ever grows over
  time, and would break any existing script that happened to use one
  of those words before it became reserved.

  THE PROCEDURAL POINT THIS ESTABLISHES, since cited elsewhere: **a
  rejected proposal never gets turned into a task.** A rejection is
  one of the possible outcomes a queued item can reach — being in
  the task queue only means the work is pre-approved to be looked
  at, never a guarantee that doing the work is actually the right
  call.

- D52 — EVERY TASK IS REMOVED FROM THE QUEUE ONCE IT'S DONE, WITH NO
  "COMPLETED" OR "REJECTED" SECTION KEPT — DECIDED (owner,
  2026-07-27). Supports P8, P23; **changes D45**.

  `TASKS.md` keeps no "Completed" section and no "Rejected" section:
  this queue only ever holds work that's still waiting to be done,
  and the commit that finishes (or "strikes") an item is that item's
  permanent record. **A rejected proposal never becomes an entry in
  the task queue at all** — it belongs here instead, in this
  decision record, which is the complete record of why it was
  rejected. Leaving finished work sitting in the queue would make
  the queue's length meaningless as a measure of what's actually
  still outstanding, and leaving rejections there too would split
  the safeguard against re-arguing settled questions across two
  separate files.

- D51 — USE CASE U3 IS RETIRED, SUPERSEDED BY U14 — DECIDED (owner,
  2026-07-27). Supports P8; **completes D36**.

  U3 had stated a *preference* for a specific transport mechanism (a
  guest agent). U14 covers the same underlying need — a program
  driving a machine and reading back results — but with **no
  preference at all about the transport mechanism used**, which is
  the entire point of replacing U3 with it: a use case is supposed
  to state what the user actually needs, never the specific
  mechanism used to deliver it, and a mechanism preference baked
  into a use case is really a design decision wearing a use case's
  clothing. The actual preference for a guest-agent transport now
  lives in **P3** instead, a principle, which governs how a native
  agent gets used if one is ever built — without requiring that one
  ever be built.

- D50 — THE UNNUMBERED CHANGES MADE IN THE 2026-07-26 RESTRUCTURE
  ARE FORMALLY RECORDED — DECIDED (owner, 2026-07-27). Supports P8,
  P23; **changes D23** (establishing that pledging is what actually
  moves an item). The restructure dissolved the project roadmap
  into these planning directories, renamed PRINCIPLES.md to root
  ARCHITECTURE.md, and made an item's directory location the
  statement of its status — all of this is now normative, written
  in [README.md](README.md).

  THE ACTUAL RULING HERE, which is why this needed a decision number
  at all: **a change to how the project's own governance machinery
  works can't go unnumbered.** The restructure had originally been
  carried out and treated as routine housekeeping, but housekeeping
  is approved as its own category specifically because it never
  touches anything genuinely arguable — and a change to how the
  project makes decisions is exactly the opposite of that. Assigning
  this decision a number retroactively is what makes the restructure
  itself something later work can properly cite.

- D49 — PRINCIPLE P24 IS RESTATED AND FORMALLY ARMED, AFTER ITS
  ORIGINAL VERSION NEVER ACTUALLY LANDED ANYWHERE — DECIDED (owner,
  2026-07-27). Supports P8, P22, P23; **restores a decision that was
  actually made on 2026-07-27, in commit `42c8c75`, but never
  reached any actual document**, and is the first promotion carried
  out under D48's second bar.

  WHAT WAS LOST, AND HOW IT HAPPENED. That earlier commit's message
  says: *"state P24 in D44 — every enumerated interface carries
  automated tests checking it against its specification, and the
  suite passes on every commit to main — dropping 'to whatever
  extent possible' so the principle can actually be violated, and
  requiring an untestable surface to name its gap."* None of that
  actually landed anywhere: P24 never actually entered
  ARCHITECTURE.md, its D-number was **reused that same day** for
  D44 (the rename of `accepted/` to `pledged/`), and the companion
  edit that commit message describes — adding P24's every-commit
  testing requirement to P22's list of expected exceptions — is also
  missing from P22. The decision existed only inside a commit
  message, nowhere else.

  WHY NOBODY NOTICED — this is the interesting part. The one
  surviving trace of this is [design/audits.md](design/audits.md),
  which refers to P24 as if it were already an established fact —
  *"armed 2026-07-26 … the strongest claim in the list with the
  thinnest verification behind it"* — so the one document that
  actually discusses P24 asserts that it already exists. A dangling
  reference like that is only findable by checking it against
  something real — and this one happened to point at a number that
  had already been silently spent elsewhere, which makes it look
  like a perfectly valid citation to any reader not checking
  closely. This was found while tracing how principles get recorded,
  for D48's purposes — not by deliberately searching for this
  specific problem.

  VERIFIED BEFORE BEING FORMALLY ARMED, using D23's standard:
  checked against the actual code, not against documentation claims.
  Every interface listed in "The interfaces" section does carry real
  test modules: the CLI (`test_cli`), the embedding API
  (`test_machines`, `test_media`, `test_run_script`, `test_core`,
  with `test_old_surface_purge` guarding against deleted surfaces
  coming back), the scripting language (the five `test_script_*`
  modules plus `test_check_script`), the machine blueprint format
  (`test_document` plus `test_conformance_corpus`, which runs one
  shared corpus against both the parser and the schema so the two
  can never silently drift apart), script properties
  (`test_properties`, `test_binding`, `test_credentials`,
  `test_facts`), recorded outputs (`test_events`, `test_errors`),
  and the home directory layout (`test_home`, `test_assets`). The
  full test suite was run at the time of this decision: **768 tests
  passing, 1 skipped** — the opt-in FreeDOS integration test.

  ARMED, BUT NOT FULLY PLEDGED — with the remaining gap filed as its
  own task, which is D48's second bar doing its very first real job
  on the same day it was written. Calling this "pledged" would have
  been a false statement: the tests do exist and the suite is
  passing, so the project genuinely does honor this as a working
  rule today. What it does *not* yet honor evenly is the specific
  phrase *"against its specification"* — most test modules test
  behavior directly, rather than deriving their test cases
  systematically from a written specification, and only the
  blueprint format actually has a true conformance corpus doing
  that. design/audits.md had already identified exactly this gap;
  under D48's rule, a known gap against an already-armed principle
  isn't just an idea for a future audit anymore — it's a **defect**,
  and it's now entered into TASKS.md as one.

  THE SECOND PART OF THIS PRINCIPLE IS HONORED THROUGH DISCIPLINE
  ALONE, STATED PLAINLY. The clause *"the suite passes on every
  commit to main"* has no automated tooling actually enforcing it,
  because P22 already states that this project runs no continuous
  integration — and P22 now separately lists automating this
  specific check as one of the situations expected to eventually
  require attention. That isn't a weakness specific to P24; it's the
  exact same overall posture, just described from the other side.

  FILES UPDATED: this entry; ARCHITECTURE.md (P24 is now stated,
  placed after P23; P22's list of expected future exceptions gains
  this item, the companion edit commit `42c8c75` had originally
  intended to make); design/audits.md (its question about P24 is
  corrected — the principle was actually armed today, not on the
  26th, and the audit it had proposed is now the filed defect
  described above); TASKS.md (the conformance-depth defect is
  entered). No CHANGELOG entry: nothing user-facing actually changed
  as a result of this.

- D48 — A GAP AGAINST AN ALREADY-STANDING PRINCIPLE OR USE CASE IS A
  BUG, NOT JUST UNFINISHED WORK; PROMOTING SOMETHING TO THE ROOT
  LIST NOW REQUIRES CLEARING TWO SEPARATE BARS — DECIDED (owner,
  2026-07-27). Supports P8, P23; **sharpens D34**. Normative in
  [README.md](README.md).

  Promoting something to the root, standing list of principles or
  use cases now requires clearing **two separate bars, not one**: a
  use case is promoted once it is *fully delivered*, and a principle
  is promoted once it is actually *honored as a working rule*, with
  every currently-known exception filed as a defect in that very
  same change. Below the root list, a shortfall just means there's
  unbuilt work remaining; once something is actually on the root
  list, a shortfall is a bug. Treating these the same would let a
  principle get promoted to the root list while someone still merely
  "intends to" fix a known exception later — which would turn the
  standing list into a statement of intent, when the standing list
  is supposed to be the one document in this whole project that has
  to be a plain statement of fact.

- D47 — PRINCIPLES P5, P14, P17, AND P18 ARE PROMOTED TO THE ROOT
  LIST AND TAKE EFFECT — DECIDED (owner, 2026-07-27, the second
  TASKS.md ruling of the day). Supports P8, P10, P11; applies D34's
  promotion rule to principles.

  THE BAR THIS ENTRY EXISTS TO ENFORCE: a principle is armed not by
  everyone simply agreeing with it, but by the code actually
  *honoring it as a working rule*, with every currently-known
  exception filed as a defect in that same change. Below the root
  list, a shortfall just means unfinished work; once something is on
  the root list, the project is asserting the code already honors
  it, so any gap becomes a bug. Promoting a principle while already
  knowing about an unaddressed exception would turn the root list
  into a wish list instead of a factual claim.

- D46 — USE CASE U9 AND THE U11–U13 GROUP OF USE CASES ARE PLEDGED
  AND TAKE EFFECT IMMEDIATELY — DECIDED (owner, 2026-07-27).
  Supports P6, P7, P8.

  A use case can be **pledged and delivered in the same single
  act**, when the code already satisfies it — pledging and
  delivering are two separate events, not something that has to
  happen with a mandatory gap in between, and forcing a wait between
  them would make the root use-case list lie about what the code can
  actually already do.

  THE RULING WITH REAL CONSEQUENCE: **a use case only gets rejected
  by being written down and formally named first.** An unwritten use
  case can never be formally refused, so when a review found that U9
  and U12 had actually already been delivered without ever being
  formally pledged, the right fix was to pledge them properly,
  rather than quietly treating "it's already delivered" as good
  enough on its own — this exact gap is what a proper traceability
  check would have caught the very day milestone 9 shipped.

- D45 — THE HOUSEKEEPING SURFACE TEST APPLIES ONLY TO HOUSEKEEPING;
  A SMALL SURFACE CHANGE CAN STILL BE HANDLED AS A REGULAR TASK —
  DECIDED (owner, 2026-07-27). Supports P8, P23; **completes D43**.
  Normative in [README.md](README.md).

  Housekeeping's surface test exists specifically to make up for one
  particular risk: work that gets approved on sight, by whoever
  happens to be doing it, and lands without any separate written
  entry, with **nobody in a position of authority ever actually
  reviewing it**. The task queue doesn't need that same safeguard,
  because only someone with authority is allowed to write to it in
  the first place, and adding an item to the task queue already *is*
  an act of approval. So these two approval gates aren't the same
  gate applied at different sizes — a small surface change is
  allowed to go through as a regular task; it's only refused from
  going through housekeeping specifically, based on *who reviews
  it*, not based on what it actually touches.

- D44 — THE SECOND SHELF FOR SETTLED WORK IS CALLED `pledged/`, NOT
  `accepted/` — DECIDED (owner, 2026-07-27). Supports P8, P23.
  Normative in [README.md](README.md).

  **Neither shelf's name is based on the act that put something
  there.** Both approval steps need a name for what happens —
  admitting a document into `proposed/` is itself a form of approval
  too — so naming a shelf after the act of approving it would claim
  wording the other shelf's own approval step would then have to
  borrow instead. Both actual names instead describe what the item
  currently *is*: "proposed" means argued for, but not binding
  anything yet; "pledged" means genuinely owed, just with no
  delivery date attached.

  The structural reason that actually settled this: `accepted/` used
  to mean only that an argument had been won. Renaming it to reflect
  an actual commitment to deliver changed what the shelf *claims*
  about everything already sitting on it — which is exactly what
  forced the entry-by-entry recheck carried out later in **D61**. A
  shelf doesn't automatically inherit its existing occupants across
  a change in what it means to be on that shelf.

- D43 — WRITING ANYTHING UNDER `planning/` IS A GOVERNED ACT; HAVING
  AUTHORITY SHORTENS THE STEPS NEEDED, BUT DOESN'T SKIP THEM —
  DECIDED (owner, 2026-07-26). Supports P8, P23; **changes D39**
  (widening it from two queues to three). The three queues and the
  approval gate are normative in [README.md](README.md).

  THE RULING: this approval gate matters most for the **task
  queue**, because an entry in `proposed/` merely admits that an
  argument exists and commits to nothing, and a later promotion is
  just that argument's conclusion, with its reasoning already on
  record — but a task-queue entry *is* the entire review, with
  nothing else behind it. There, having actual authority is the only
  thing standing between legitimate pre-approval and someone simply
  approving their own work. So the third queue (tasks) is restricted
  based on **who is allowed to write to it**, never based on what
  kind of thing it's allowed to contain: a small surface change is
  allowed to go through as a task, and the housekeeping surface test
  only applies within housekeeping itself.

- D42 — THE PROJECT KEEPS NO ROADMAP; FEATURES ARE GIVEN F-NUMBERS
  THAT RETIRE ON DELIVERY, AND EACH MUST FIT WITHIN ONE SPRINT —
  DECIDED (owner, 2026-07-26), completing that day's rebuild of the
  governance process. Supports P9. The resulting process is
  normative in [README.md](README.md).

  WHY THERE'S NO ROADMAP — the part of this that has no other
  natural home to live in: a roadmap organizes things by *when*
  they'll happen, while everything else in this directory is
  organized by *what state it's in* — and a roadmap makes a promise
  about ordering that nothing here actually commits to. Being on the
  `pledged/` shelf means the project genuinely will do the work, and
  says nothing at all about when — a commitment with no date
  attached, which is exactly what lets the shelf stay **honest**: if
  an item turns out to be something nobody actually intends to
  deliver, it gets withdrawn or rejected outright, rather than left
  sitting there as a pledge nobody actually means to keep.

  The one-sprint size limit only applies **at the moment something
  is pledged**, not while it's still in `proposed/` — so a proposal
  is allowed to describe something that would take many sprints, and
  cutting it down to size is part of what happens when it's actually
  pledged. A feature's F-number disappears once it's delivered, and
  is never reused afterward: gaps in the numbering are just history,
  not a promise of something still to come.

- D41 — THE MEDIA-IDENTITY LEDGER IS DELETED; `add-media` NOW
  AUTHORS A DECLARATION INSTEAD OF IMPORTING A FILE — DECIDED
  (owner, 2026-07-26). Supports P4, P8; **changes D22**'s clauses
  about the media cache.

  **The media cache can always be fully regenerated, so nothing
  needs to record where any of its files originally came from.**
  Every file in it arrived there either by downloading it or by
  extracting it from something else, so no command ever needs to ask
  about a file's origin before reusing or reclaiming it — keeping a
  separate ledger of that would just be a second, independent source
  of truth about a directory that can always be rebuilt from scratch
  anyway, and one that would silently go stale over time.

  So `add-media` now *authors a declaration* pointing at a file,
  rather than importing or copying that file: it computes the file's
  sha256 hash and writes an `.rlqb` file that locates the media
  exactly where it already sits on disk, without copying anything.
  Supplying a file this way is an act of authoring, which is why
  this command belongs with blueprint authoring, not with the media
  cache.

- D40 — CANCELLING A RUN NOW ALSO REACHES DOWNLOADS AND EXTRACTIONS
  IN PROGRESS, THROUGH THEIR OWN DEDICATED PARAMETER — DECIDED
  (owner, 2026-07-26). Supports the execution model's ability to be
  safely interrupted at any point; this fixes a gap against a
  promise the project had already made, rather than making a new
  promise, so it's a "a gap against a standing rule is a bug" fix
  (the kind D38 excludes from needing its own justification) — the
  part actually being decided here is the mechanism used to fix it.
  [Retrofitted on 2026-07-28 — Supports U12, U13; P5. The paragraph
  above didn't cite any numbered vision document, and the guarantee
  it's fixing is a promise made in the *spec*
  (docs/spec/script-spec.md — Ctrl-C "leaves the machine as-is"),
  not a principle, so it originally gave this entry nothing citable.
  What this fix actually serves does have numbers: U12's
  long-running operation showing where it is and what it's currently
  waiting on while it runs, U13's downloading and verifying of
  media, and P5's requirement that output be rendered *promptly* — a
  294 MB download that reports nothing for minutes and swallows a
  Ctrl-C fails all three of these at once.]

  THE BUG. `planning/ROADMAP.md` (in its "Cancel ends the run, not
  the machine" section) had already promised that pressing Ctrl-C
  would make "input deliveries atomic, **host transfers abort**."
  They didn't. Cancellation was implemented purely as a
  `threading.Event` flag that only `_check_clocks` ever checked, and
  only at the boundaries between statements — `acquire.py`'s
  file-transfer loops knew nothing about it at all. So a Ctrl-C sent
  during a statement like `insert cdrom0 @…` wasn't actually noticed
  until the download, its SHA-256 check, the extraction, and *its*
  SHA-256 check had all already fully finished. This was reported
  from real-world use as several minutes of an unresponsive Ctrl-C
  while fetching a 294 MB LiveCD image. Making it worse, that same
  statement also wasn't passed an `events` object, so the transfer
  reported no progress at all — several minutes of total silence
  looks exactly like a hang, which is how this bug was actually
  found.

  THE FIX, WHICH IS THE ACTUAL DECISION HERE. Cancellation now
  travels through its own dedicated `cancelled=` keyword argument —
  the run engine's existing `threading.Event` object, threaded
  through `insert_media`, `start_machine`, and `fetch_media`, all
  the way down to the chunk-by-chunk transfer loops, which now check
  it on every single chunk. Passing `None` (which happens for a
  fetch triggered outside of a run) leaves that transfer just as
  uninterruptible as it always was — so this addition has no effect
  anywhere it isn't explicitly passed.

  CONSIDERED AND REJECTED: piggybacking the cancellation signal on
  the existing `EventStream` object, which is already threaded all
  the way through end-to-end, and would have cost roughly 4 lines of
  code instead of touching about 10 function signatures. This was
  rejected because it would tie two completely unrelated concerns to
  a single keyword argument — and that exact kind of unwanted
  coupling is what produced this bug in the first place. One call
  site (`_machine_change`) had already been found to drop the
  `events` argument and silently lose progress reporting as a
  result; under the coupled design, that same omission would have
  also made a multi-minute transfer completely uninterruptible, with
  nothing to safely fail back to, since `events=None` is otherwise a
  perfectly normal, supported state. Keeping these as two separate,
  independent keyword arguments keeps these two different failure
  modes independently diagnosable, and keeps `acquire.py` free of
  any dependency on the run engine's own control flow.

  PRESSING CTRL-C TWICE ESCALATES. A second interrupt restores
  Python's default signal handler and raises immediately. The
  graceful stop is meant as a promise, not a guarantee that traps
  every signal — the previous handler had been swallowing every
  repeated Ctrl-C into the same single flag, so a stop that failed
  to land in time left killing the whole terminal as the only
  remaining way out.

  ALSO FIXED: `urlopen` calls now have a 30-second timeout. A mirror
  server that accepts a connection and then just stalls indefinitely
  is effectively a failed download location, not a good reason to
  hang forever — it now surfaces as an `OSError`, which the existing
  mirror-fallback loop already treats the same as any other location
  failing, so the next mirror in the list gets tried instead.

  AND CLEANUP NOW COVERS THE LEFTOVER SCRATCH FILE TOO. A transfer
  writes to a `<destination>.part` file and only renames it to its
  final name once it's fully complete — so an interrupted transfer
  used to strand that partial file on disk. This used to be rare,
  since interrupting a transfer mid-flight was barely reachable
  before this fix; now that Ctrl-C actually reaches transfers, it's
  the ordinary case. Cleanup logic was applied to *every*
  incomplete-transfer code path, not just to cancellation
  specifically: since there's no resume support at all (the next
  attempt just reopens the file in `"wb"` mode and starts completely
  over), an abandoned partial file is never useful for anything but
  taking up disk space — and a cleanup rule that only applied to one
  specific way a transfer could end would have been the genuinely
  arbitrary choice.

- D39 — TWO QUEUES HANDLE ALL RAW, UNAPPROVED WORK; NOTHING ENTERS
  THE PROJECT ANY OTHER WAY — DECIDED (owner, 2026-07-24). Supports
  P8; completes D38. **Later widened from two queues to three by
  D43.**

  Nothing gets added to this project without first passing through
  one of these queues, with the single exception of a small raw
  change approved directly under the housekeeping bucket. The point
  here isn't really how many queues there are — it's that the set of
  entry points is closed: an idea with no defined door to go through
  is an idea that just gets added by whoever happens to be writing
  the code at the time, and a rejection then has nowhere to actually
  be recorded. That's exactly why a rejected item's reasoning is
  recorded here, in this decision file, rather than in whichever
  queue it was rejected from.

- D38 — HOUSEKEEPING IS A STANDING, PRE-APPROVED BUCKET FOR SMALL
  WORK — DECIDED (owner, 2026-07-24). Supports P8; sharpens the
  vague language TASKS.md previously used — "small ones may simply
  be deemed obvious" — which hadn't actually named any test, any
  specific person doing the "deeming," or any concrete action.

  THE BUCKET, DEFINED. Small code cleanups and small reported
  defects — genuinely tiny in scope **and** unambiguously clear that
  they're a real problem needing a fix — are approved as an entire
  category, in advance. They don't need a use case, a principle, a
  filed issue, or a D-number of their own. Whoever actually does the
  work invokes this pre-approval simply by naming "housekeeping" in
  the commit message; that commit is the whole record (the CHANGELOG
  still follows its own separate, existing rule — a user-visible
  change gets a CHANGELOG entry, invisible internal tidying does
  not).

  WHAT THIS BUCKET IS ACTUALLY FOR: work that has *no other citation
  available to justify it*. Tidying up code with no specific defect
  behind it — dead code, an outdated file path, an awkward help
  string — and defects too minor to be worth filing as a full issue.
  A defect against an **already-standing** principle is deliberately
  **excluded** from this bucket: the principle itself is already the
  justification (under the "a gap against a standing rule is a bug"
  rule), so fixing it needs no separate approval at all — it just
  needs fixing.

  REJECTING SOMETHING FROM THIS BUCKET IS A REQUIRED STEP, NOT
  SOMETHING THAT CAN JUST BE SKIPPED (in the owner's words). Anything
  that fails the test below is **refused** housekeeping status and
  instead routed to the proper governance process — filing an issue,
  proposing a use case or principle, going through the
  interface-change rule, or adding a roadmap item. This is what
  makes the bucket a genuine gate rather than just a shortcut: the
  qualifying question gets asked of every single candidate, and a
  "no" answer always has somewhere else to go. Also never eligible
  for this bucket under any circumstances: amending a use case or a
  principle, or making any kind of design decision.

  THE FIRST TEST IS PURELY MECHANICAL, AND IT IS ABSOLUTE (owner,
  2026-07-24): **anything that changes a documented interface is
  automatically disqualified from being housekeeping.** This
  question is asked first, and it's answered by simple lookup, not
  by judgment — INTERFACES.md literally *lists* every application
  surface, so this is a checklist, not a matter of opinion: the four
  primary interfaces (the CLI, the embedding API, the scripting
  language, and the machine blueprint format) plus the supporting
  user-facing contracts (script properties, the codex library, the
  run's returned output, and the home directory layout). Touch any
  one of these, and the answer is automatically no, no matter how
  small the actual diff looks. This mechanical property is exactly
  what protects this exclusion from the bucket's real failure mode,
  which is self-assessment — "tiny" and "clearly a problem" tend to
  get judged by whoever wants to do the work in the first place, and
  everyone's own proposed change tends to feel like both.

  THE TIE-BREAK, for whatever survives that first mechanical test:
  **any doubt means it escalates out of the bucket. If you have to
  argue your way into calling something housekeeping, it doesn't
  belong in housekeeping.** Both remaining conditions must hold at
  once — being tiny alone isn't enough, and being an obvious problem
  alone isn't enough either.

  THE TRAP THIS RULE IS DESIGNED TO CATCH, illustrated by milestone
  9's own landing. Three changes made that same day were all
  individually small: the codex install script's `press enter` being
  replaced with `select "Yes"` (a genuine small defect fix, touching
  no documented interface — correctly housekeeping); the
  guest-console command family being passed the machine's own
  directory so its identity check could actually pass (restoring
  behavior that had never actually worked — also correctly
  housekeeping); and an output-discipline cleanup that made
  `create-machine` print just `plain-0` instead of the sentence
  "created machine plain-0". This third change felt like the
  smallest of the three, and it was actually the only one of the
  three that changed a genuinely user-facing contract, on every
  single command — it actually needed milestone 9's larger
  deliverable behind it to be justified, and under this rule it
  would correctly be refused housekeeping status. Being small is
  never the test on its own.

  FILES UPDATED: this entry; TASKS.md's introductory section (the
  vague passive sentence is replaced with this actual operative
  rule); INTERFACES.md (the housekeeping exclusion is stated right
  where the interface-change rule itself lives, so this potential
  loophole is closed at the exact door someone would otherwise try
  to walk through).

- D37 — MILESTONE 9 FULLY DELIVERS USE CASES U14 AND U20; BOTH ARE
  PROMOTED TO THE ROOT LIST — DECIDED (2026-07-24, on landing
  milestone 9). Supports P8, P11, P18; applies D34's automatic
  promote-on-delivery rule and D36's reframing of how runs work. The
  milestone landed in full — the "return output rather than store
  it" run model, the error-class taxonomy, live `--progress`
  feedback, and the exec-run mechanics — so under D34, the two use
  cases this milestone had accepted move to their standing lists as
  part of delivering it.

  U14 IS PROMOTED. The workflow it describes runs completely end to
  end against a live FreeDOS machine: work is submitted, run from a
  script the consumer wrote themselves, and the result is read back
  through a machine variable (`get-machine-var`). The matching
  `exec` capability landed alongside it, returning the actual text
  its command produced — the parity between these two that D36 had
  already established as required. [The in-band file-transfer
  commands this entry originally cited as supporting evidence have
  since been removed (**D108**), and U14 no longer claims that a
  file is something it produces — this promotion stands on whatever
  still survives that later change.]

  U20 IS PROMOTED, ITS TRANSPORT MECHANISM PROVEN WORKING. The T1
  exploratory spike ran the full media-swap cycle on QEMU running
  DOS: a live `insert-media --file` swap is genuinely *seen* by DOS
  (the directory listing right after a swap correctly shows the new
  image's contents, never the previous disk's), and a write made by
  the guest actually reaches the host's image file — this was
  verified byte-for-byte after `eject-media`, and again after
  swapping back, with each image correctly containing only the
  writes made during its own time attached. No redesign was needed.

  THE ONE CONDITION THE SPIKE FOUND IS NOW A REAL SAFETY GUARD. A
  floppy drive's storage geometry gets fixed the moment the backend
  attaches it at machine launch, and a live media swap doesn't
  revise that geometry: a drive slot that launched empty defaults to
  QEMU's own 2.88 MB geometry, so live-inserting a 1.44 MB image
  into that slot reaches the guest as "general failure" on every
  single read and write. Reliquary didn't choose that mismatched
  geometry, and it will not silently ship a broken drive to a user
  (P11), so `start` now records the size of whatever medium it
  launched with, and a live insert whose size doesn't match now
  fails outright, naming both sizes involved and how to fix it. This
  safety guard is the entire reason the spike was run in the first
  place — the finding became a permanent guard, not just a footnote
  in a report.

  PRINCIPLES P16, P17, AND P18 ARE NOT PROMOTED HERE. The code does
  actually honor P18 (no readiness script ships built-in, no fixed
  vocabulary for results), but these principles are still only
  **drafted, and awaiting a formal decision**. Promotion presupposes
  that a principle has been formally accepted, which is a decision
  that belongs to the owner, so these stay in
  PRINCIPLE-PROPOSALS.md for now; the implementation landing is
  evidence supporting that eventual decision, not a substitute for
  actually making it. [P17 was later formally armed, and has since
  been struck outright — see **D108**.]

  U3's RETIREMENT IS OVERDUE, BUT NOT ACTUALLY DONE HERE. D36
  already established that U14 supersedes U3 specifically, and U14
  is now fully delivered — but formally retiring a use case is its
  own separate step in the use-case lifecycle, requiring its own
  owner decision, not something that happens automatically as part
  of this delivery. U3 remains waiting in the proposals document,
  with a note about this.

  FILES UPDATED: this entry; USE-CASES.md (U14 and U20 added);
  USE-CASE-PROPOSALS.md (both removed, with no placeholder left
  behind, per D23's rule; U3's note added); the ROADMAP (milestone 9
  marked complete, and with it the whole numbered arc; the spike's
  finding recorded); TASKS.md (tasks T1 through T7 marked landed,
  the spike's result, and two smaller fixes found along the way);
  script-spec.md (the `set` verb, and half of the previously-noted
  file-exchange gap now closed by in-band put/get — but only as a
  CLI/API capability, never as part of the script language itself);
  AGENTS.md; the machine-state schema (`variables`, the anonymous
  medium concept); the README, the CHANGELOG, and both reference
  documents.

- D36 — A RUN RETURNS ITS OUTPUT DIRECTLY TO WHOEVER STARTED IT,
  RATHER THAN WRITING IT SOMEWHERE PERSISTENT — DECIDED (owner,
  2026-07-24). Supports P4, P6, P8, P18; **changes D35**. Normative
  in surface S7 and AGENTS.md.

  A run drives the machine and **returns its output directly to
  whoever started it, storing nothing on disk**. What got deleted as
  part of this — the `run-events.jsonl` file, the `transcript.txt`
  file, the entire `runs/` archive, any retention policy, and the
  run-inspection commands that went with them — was removed because
  nobody had actually demonstrated a need for it, not because it was
  disliked as a design: it existed purely as the underlying
  mechanism for asynchronous runs, and asynchronous runs themselves
  had no demonstrated need either. This capability can come back
  later, through **feature F6**, if use case U19 is ever formally
  pledged.

  [Later narrowed by **D98**: a `--record` capture file is written
  only when a maintainer explicitly names a path for it, and nothing
  at runtime ever reads it back — which is a genuinely different
  thing from using persistence as the underlying mechanism for
  asynchronous runs.]

- D35 — ASYNCHRONOUS (DETACHED) RUNS ARE REMOVED FROM THE PROJECT'S
  PLANNED ARC — DECIDED (owner, 2026-07-24). Supports P8; follows
  the same reasoning D33 already established.

  The requirement to split live feedback from stored results (**P5**)
  is already fully satisfied by having the process that started a
  run watch it live as it happens — so detaching a run to keep
  running in the background, or following a run's progress from a
  different process than the one that started it, is a genuinely
  **separable** capability that no actual use case currently
  describes needing. The actual demand for it exists only as the
  draft of use case U19; formally pledging U19 is what would put
  this work back on the schedule. [**D36** later extended this
  reasoning: the persistent storage a detached run would need to
  work at all was removed along with it.]

- D34 — DELIVERING SOMETHING FULLY AUTOMATICALLY PROMOTES IT —
  DECIDED (owner, 2026-07-24). Supports P8; sharpens D23. THE RULE:
  when a milestone or a task FULLY delivers a use case or a
  principle, moving it from its proposals document to its standing
  (root) list happens automatically, AS PART OF that same delivery —
  it is not a separate decision the owner makes later. D23 had
  already said that "DELIVERY makes it current and moves it over";
  what hadn't been made explicit is that whoever actually lands the
  work is the one who moves it, in that very same change, the moment
  the code actually honors what the entry describes. There's no
  waiting around for a separate, later sign-off.

  WHAT ACTUALLY TRIGGERS THIS IS FULL DELIVERY, NOT MERE ACCEPTANCE.
  A milestone that simply cites a proposal formally accepts it (this
  is D23's "acceptance is scheduling" rule); a milestone whose
  landed code actually honors that proposal in full is what delivers
  it. These two things can diverge from each other: milestone 8
  accepted both use case U5 and principle P13, but only P13 was
  actually fully delivered — U5's core customized-Windows-installation
  scenario still depends on GUI automation that doesn't exist yet, so
  U5 stays in the "accepted, awaiting delivery" state while P13 gets
  promoted. Whoever lands the work makes this call themselves, using
  the exact same test the earlier P1 through P12 promotion pass
  used: does the project, as the code stands today, actually honor
  what this entry describes?

  THE MECHANICS OF A PROMOTION (identical whether it's a use case or
  a principle): add the entry to its standing list, at its normative
  home document (root PRINCIPLES.md or USE-CASES.md), in numerical
  order; DELETE it from the proposals document entirely, leaving no
  placeholder behind (per D23's no-stub rule); and record the move
  here, in this decision file, with the entry's own number serving
  as the search key for anyone auditing the planning documents. An
  entry that's only partly delivered does not get promoted — the
  standing lists are meant to be a factual claim about what's
  actually implemented (D23's "implemented means only what's
  actually implemented" rule), so promoting a half-honored entry
  would make that claim false.

  [D48 later split this single rule into two separate bars: this
  rule, as written, still holds exactly as-is for a use case, while
  a principle instead promotes once it's *honored as a working
  rule*, with every currently-known exception filed as a defect in
  that same change. The tension between these two readings already
  exists inside this very entry — the test described two paragraphs
  above, inherited from the original P1 through P12 promotion pass,
  is already effectively the rule-as-a-working-standard version.]

  THE FIRST TIME THIS RULE WAS ACTUALLY APPLIED: principle P13
  (about property sources) was promoted into PRINCIPLES.md together
  with milestone 8 — the property-binding pipeline, the layered
  source model, custody tracking, and per-resolution provenance
  tracking had all landed (tasks T1 through T5, verified directly
  against the code). FILES UPDATED: this entry; PRINCIPLES.md (P13
  added, placed between P12 and P15); PRINCIPLE-PROPOSALS.md (P13
  removed from the "Drafted" section) and its lifecycle introduction
  section; USE-CASE-PROPOSALS.md's equivalent introduction section;
  the ROADMAP's note on milestone 8 (recording that P13 was
  promoted, while U5 is still waiting on GUI automation to exist).
  U5's own eventual promotion will wait on its own actual delivery,
  under this exact same rule.

- D33 — THE PROJECT'S NUMBERED MILESTONE PLAN ENDS AT MILESTONE 9 —
  DECIDED (owner, 2026-07-23). Supports P8.

  The items planned beyond milestone 9 — additional backend support,
  guest agents, and GUI automation — were **removed from the
  schedule for lack of any use case actually demanding them**, not
  because their designs were bad: their existing designs remain
  settled and stand exactly as written. A milestone number is a
  scheduling commitment, and scheduling work that no actual use case
  is asking for is exactly how a roadmap ends up carrying items
  nobody actually intends to build. Putting any of these back on the
  schedule requires pledging the use case that actually wants it.

- D32 — A MEDIA PATH REFERENCE'S SUB-PATH GOES INSIDE THE `${...}`
  BRACES, NOT AFTER THEM — DECIDED (owner, 2026-07-23, during
  milestone 7's S3 stage). Supports P14; RESOLVES a contradiction
  between D22/D24 and D26/D27. This was found by running the S2 test
  corpus against the first parser actually written to match the
  spec — which is exactly what writing the corpus first was for.

  THE CONTRADICTION. D22 had settled the syntax as
  `${media:<name>}/<path>`, with the path OUTSIDE the closing brace,
  and D24 built directly on that — its rule that "a backslash right
  after `}` is an error, citing the `/` rule" only makes sense if the
  path comes after the brace. But D26's definition of the allowed
  character class justified `/` by saying it "separates the
  containment path (there's exactly one)" — which wouldn't need to
  be true if the path were entirely outside the reference's body —
  and D27's corrected grammar rule spells the reference body as
  `qualifier:media-name[/path]`, with the path INSIDE. Both
  interpretations were actively supported by different entries, and
  the spec document, blueprint-model.md, ended up inheriting both at
  once, in the same document — its location table said "outside,"
  while its closure section said "inside" — WITHOUT THE REWRITE EVER
  NOTICING THE CONFLICT. A spec that contradicts itself about where
  a single character goes is a spec whoever implements it has to
  resolve by guessing.

  DECIDED: THE PATH GOES INSIDE THE BRACES. `${media:outer/cd.iso}`.
  THE DECIDING ARGUMENT IS ABOUT CLOSURE: a qualified reference is
  only ever valid as the entire value of a field, and with the path
  placed inside the braces, "the entire value" simply means the
  string is EXACTLY ONE REFERENCE — the closure check can see the
  whole location in one piece, with nothing trailing after it. With
  the path placed outside the braces instead, the parser would have
  to specially handle trailing text that follows a qualified
  reference, telling apart a path suffix from the kind of
  interpolation the reach rules already forbid in that position —
  that's a second special-case rule, and it would live in exactly
  the place P14 says a second rule must never be allowed to
  accumulate. Keeping the path inside also gives D26's `/` character
  the actual job D26 said it had.

  WHAT THE "PATH OUTSIDE" FORM HAD GOING FOR IT: it was D22's
  original choice, and it's more familiar-looking, since it reads
  like joining a file path onto something. Both of those are real
  advantages, but neither is a structural argument.

  THE BACKSLASH-DETECTION DIAGNOSTIC SURVIVES, which was the
  strongest objection raised against this: `${media:outer\cd.iso}`
  is still the exact same mistake a Windows-habituated author would
  make, and the parser still names the same `/` rule in its error
  message — the only difference is that this mistake is now caught
  while still inside the reference body, rather than just after it,
  and the actual error message is unchanged in substance.

  RECORDED HERE AS A NOTE ON METHOD: running the S2 corpus before S3
  (during that milestone's reassessment) is exactly what surfaced
  this contradiction. A test corpus written directly from the spec,
  run against a parser also written directly from the same spec, is
  really a differential test of the SPEC ITSELF — and it failed on
  exactly the one sentence where the spec disagreed with itself.

  FILES UPDATED: this entry; blueprint-model.md (the location table,
  the path-suffix section, the containment example, and the
  resolution-order example); the S2 test corpus fixtures;
  reliquary/document.py. D22, D24, D26, and D27 all keep their
  original wording unchanged; this entry is the official amendment
  on record.

- D31 — USE-CASES.md MOVES FROM `planning/` TO THE REPOSITORY ROOT —
  DECIDED (owner, 2026-07-23). Supports P8. The use-case list now
  sits alongside PRINCIPLES.md at the repository root.

  THE ARGUMENT IS A DIRECT PARALLEL, already written into both files
  themselves: PRINCIPLES.md lives at the root BECAUSE IT DESCRIBES
  CURRENT REALITY — its own text says "every principle here is real
  — the project honors it as the code stands today (it lives at the
  root for that reason)" — and USE-CASES.md makes the exact same
  claim, in the exact same way: it lists only what's actually
  implemented, with everything not yet delivered kept separately in
  its own proposals document. These two lists share one lifecycle,
  one relationship to the actual code, and one role as the reference
  point every interface change gets checked against (P8, which D28
  had just made apply symmetrically to both). Leaving one of the two
  lists under `planning/` said the opposite of what both files claim
  about themselves: `planning/` holds maintainer-facing plans, and a
  list of what is TRUE TODAY is not a plan. The proposals documents
  themselves stay in `planning/`, for the identical reason — they
  genuinely are plans.

  FILES UPDATED: the actual file move; USE-CASES.md's own internal
  links and its note explaining why it lives at the root;
  PRINCIPLES.md, AGENTS.md, planning/INTERFACES.md,
  planning/ROADMAP.md, planning/USE-CASE-PROPOSALS.md,
  planning/proposed/design/recorder.md, this file's own preamble,
  and the documentation-rules skill's list of file locations. Older
  DECISIONS entries keep their original `planning/USE-CASES.md` path
  references, per the rule that preserves an entry's original
  wording.

- D30 — THE MEDIA LIFECYCLE COMMANDS TREAT THE `.rlqb` DECLARATION
  AS THE REAL OBJECT; TWO UNUSED VERBS ARE REMOVED — DECIDED (owner,
  2026-07-23). Supports U13, P6, P9.

  **There is no `delete-media` command**: removing a media entry
  means editing the `.rlqb` file that declares it. A dedicated
  command that deleted a declaration for you would suggest that the
  blueprint file is no longer the authoritative statement of what
  exists — the media cache itself can always be regenerated, and
  it's the declaration that's the actually-authored artifact, so a
  `delete-media` command would end up editing the wrong one of the
  two things. `add-media` was later handled the same way (**D41**):
  supplying a file is itself an act of authoring a declaration, not
  a separate import step.

- D29 — AN ENTRY ONLY PARTLY OVERRULED STAYS IN PLACE AND GETS A
  NOTE, RATHER THAN BEING REWRITTEN — DECIDED (owner, 2026-07-23).
  Supports P23 — retrofitted into that principle on 2026-07-27.
  This is a convention for how this record itself works, settled
  the very first time this situation came up, rather than waiting
  until it happened a second time.

  D27 corrected one specific clause of D26 — the claim that a
  certain character class was "the whole closure test, and the only
  one needed" — while leaving D26's other parts (A, B, C, and E)
  standing unchanged. The existing rule about preserving an entry's
  original wording didn't actually cover this situation: that rule
  governs retiring an entire entry, or vocabulary drifting out of
  date over time — not a single incorrect clause sitting inside an
  otherwise-still-valid entry.

  THE RULE THIS ESTABLISHES: an entry that's only partly overruled
  STAYS EXACTLY WHERE IT IS, and gets ANNOTATED instead — a short,
  bracketed note right at the affected clause, naming the entry that
  amends it, with every other clause left completely untouched. This
  is really the same instinct behind the "retired entries" section,
  just applied at the level of a single clause instead of a whole
  entry. Actually rewriting the prose in place is NEVER the right
  answer: a mistake and how it was discovered are themselves part of
  the historical record, and in this specific case, that discovery
  is actually the most useful part of the whole entry — D26's part D
  had listed `${key:-x}` as an excluded pattern in the very same
  paragraph that claimed the character class already excluded it,
  which is exactly the argument for why a stated test has to
  actually be testable.

  WHY THE EXISTING "PRESERVE ORIGINAL WORDING" RULE DOESN'T COVER
  THIS: that rule exists to protect the record's faithfulness to the
  moment it was written, and it was never meant as permission to
  leave a genuinely WRONG INSTRUCTION standing where a reader who
  finds it through search would act on it. AN OUTDATED WORD CANNOT
  CAUSE A BUG; A WRONG TEST CAN — and this particular wrong test was
  aimed squarely at what milestone 7 was about to deliver next:
  someone searches for how the closure test works, finds the phrase
  "the only test needed," and ships a parser that incorrectly
  accepts `${mem:-512M}`. This is the mirror image of what this very
  decision round found elsewhere: a boundary that was never stated
  at all can't be checked against, but a boundary that's stated
  incorrectly is actually worse than no boundary at all, because it
  does get checked against, and it wrongly lets the wrong things
  pass.

  FILES UPDATED: this entry; the DECISIONS preamble (this convention
  added alongside the existing rules about retired entries and
  preserved wording); D26's part D (the bracketed note, as the very
  first real use of this rule).

- D28 — THE INTERFACE-CHANGE PROCESS ALSO GOVERNS CHANGES TO
  PRINCIPLES, NOT ONLY TO USE CASES — DECIDED (owner, 2026-07-23).
  Supports P8 (which this decision clarifies). The owner's own
  words: "requests must align to principles or use cases, and a
  change in principles requires vigorous argument, just like the use
  case." HALF OF THIS HAD ACTUALLY BEEN WRITTEN DOWN, AND HALF HAD
  NOT.

  WHAT HAD BEEN WRITTEN DOWN: the demand side. The ROADMAP's
  introduction already required every item to cite either a use case
  (U) or a governing principle (P), noting that a principle "drives
  work just as well" as a use case does. WHAT HAD NOT BEEN WRITTEN
  DOWN: the review/vetting side. The interface-change process itself
  (documented in INTERFACES.md) had been written entirely in
  use-case-shaped language — "the use-case list is where interface
  changes are argued," changes get triaged "by their use-case
  impact," all three review tiers were framed around use cases, and
  even the hardest case described required that "Reliquary's use
  cases change." P8 mirrored this same gap, describing changes as
  "triages by its impact on the use cases." SO A CHANGE THAT
  CONFLICTED WITH A PRINCIPLE, RATHER THAN A USE CASE, HAD NO
  DEFINED PATH THROUGH THIS PROCESS AT ALL — even though
  PRINCIPLES.md itself asserted that amendments to principles "are
  argued like interface changes," PRINCIPLE-PROPOSALS.md said its
  own lifecycle process "mirrors the use-case one," and D25 had
  already amended principle P9 explicitly under this very process.
  The actual practice already existed; the written rule had simply
  never actually authorized it. This gap was live throughout this
  whole decision round: D25, D27's addition of P15, and P14's
  reshaping were all changes at the principle level, made under a
  process that, as written, never even mentioned principles.

  THE FIX: P8 is retitled to "Interface and principle changes are
  vetted," and now triages changes by their impact on both the use
  cases AND the governing principles; a change that conflicts with
  either one must be argued as the amendment it actually requires —
  A PRINCIPLE AMENDMENT ARGUED JUST AS VIGOROUSLY AS A USE-CASE
  AMENDMENT — and never simply justified as a feature on its own
  separate merits. INTERFACES.md's process document gains the
  equivalent "principle" branch throughout: in its framing ("cannot
  be phrased as 'the use cases should say …' or 'the principles
  should say …'"), across all three of its review tiers, and in its
  workflow description, which now names PRINCIPLE-PROPOSALS.md right
  alongside USE-CASE-PROPOSALS.md. One new sentence is added that
  neither document had actually stated before: THE TWO LISTS CARRY
  EQUAL WEIGHT, AND NEITHER ONE IS EVER EDITED JUST TO FIT A FEATURE
  SOMEONE HAS ALREADY DECIDED TO BUILD.

  THIS IS A CLARIFICATION, NOT A REPLACEMENT — and this was decided
  based on actual evidence, not just a preference, using the
  lifecycle process's own test for the difference (a clarification
  is a wording change that no past citation of it would read any
  differently under). P8 has three existing citations; none of them
  reads any differently under the new wording, and one actually
  reads BETTER: D27 cites "Supports P8" for a decision that ADDS AN
  ENTIRELY NEW PRINCIPLE — exactly the kind of case the old wording
  never actually covered. So no principle number is retired, and no
  new number gets spent on this. CONSIDERED AND REJECTED: replacing
  P8 with an entirely new principle number instead (which is the
  lifecycle process's normal path for a change in what something
  fundamentally means) — the retitling and the broadened scope both
  made a case for doing that, but the citation test governs here,
  and spending a new number on a change that nothing actually reads
  differently under would be cost with no real benefit.

  RECORDED HERE AS A NOTE ON METHOD: this entry's own change was
  itself argued for and approved before being made — which is
  exactly the discipline this decision adds to the process.

  FILES UPDATED: this entry; PRINCIPLES.md (P8's text); INTERFACES.md
  (the process's framing, its three review tiers, and its workflow
  description).

- D27 — THE INPUT MODEL, AND CORRECTING D26'S CLOSURE TEST —
  DECIDED (owner, 2026-07-23). Supports P8; **amends D26** (its part
  D) and **adds a new principle, P15**.

  THE CORRECTION IS THE ENTIRE POINT OF THIS ENTRY: D26 had claimed
  the string grammar was fully closed, based on a test that didn't
  actually hold up. A closure argument based on "no author would
  ever write that" isn't really a closure at all — it's just a
  prediction about author behavior — and the grammar has to actually
  refuse every shape its own character class technically allows,
  whether or not anyone would realistically write it. P15 was added
  out of this same realization: a rule that depends on taste or
  prediction is a rule that can't actually be mechanically checked.

- D26 — NARROWING WHAT PROPERTIES CAN REACH, AND CLOSING THE STRING
  GRAMMAR — DECIDED (owner, 2026-07-23, during the format
  re-examination round). Supports U4, U5; P7, P10. **Changes D18**
  (its rejection of HCL2 and its computational-growth rule) and
  **D24** (its reach rule).

  - **HCL2 is rejected on structural grounds, not just "not yet."**
    It moves from D18's "deferred" list to the permanently "closed"
    list. YAML, TOML, and KDL remain rejected for the reasons
    already given earlier.
  - **`sha256` values can still be interpolated.** Refusing to allow
    that was considered and rejected; a pinned hash value supplied
    through a property is a genuine, legitimate way to author a
    blueprint.
  - **`${key:-x}`-style default-value syntax and similar patterns
    are explicitly closed off**: the allowed character class
    technically permits them, so the grammar now explicitly refuses
    them, rather than letting a default-value operator sneak in by
    accident.

- D25 — THE COMPATIBILITY-PROMISE DEADLINE MOVES FROM BETA TO A FULL
  1.0 RELEASE — DECIDED (owner, 2026-07-23). Supports P9 (which this
  decision amends). This is a change to a principle, argued for and
  approved as one, through the interface-change process — the owner
  noted the irony of amending the very root list he'd just ruled was
  "never changed in nature" (D23), and approved it anyway: this
  genuinely is not just a clarification.

  THE RULE: no backward compatibility is guaranteed until a full,
  general-availability 1.0 release (it previously said "at least a
  beta-quality release"). Throughout beta and the rest of the
  pre-1.0 period, SOME effort to avoid breaking users MAY be made
  WHEN IT SEEMS WARRANTED — but this comes with NO PROMISES. This
  gets folded into the project's actual operating rule, and it's
  vetoable at any time: making the effort once creates no
  expectation that it'll happen again next time, a clean break stays
  the default behavior, and any accommodation made is a deliberate,
  individual exception — the owner's own call each time, recorded in
  the CHANGELOG — never something left in the code to just
  accumulate, because an unmaintained compatibility shim nobody
  actually decided to keep is exactly the problem this rule exists
  to prevent.

  WHAT MOVED ALONG WITH THIS: every other deadline that had been
  tied to "beta" specifically because it was really about
  compatibility — format versioning and the `$schema` field syntax
  (the ROADMAP's "Deferred to 1.0" section, machine-blueprint.md,
  blueprint-model.md, instance-model.md, and script-spec.md's
  format-version paragraph) — and the CLI's promise that
  machine-readable output only ever grows additively (cli.md), which
  had promised this starting at beta and now starts at 1.0 instead.
  The underlying reasoning didn't actually change with this move — a
  document written before 1.0 genuinely has no format version to
  speak of, exactly as one written before beta had none either. WHAT
  DIDN'T MOVE: deadlines tied to "beta" for their own independent
  reasons that have nothing to do with compatibility — the error-id
  index (in TASKS.md) is purely documentation polish, and stays
  exactly where it was.

  FILES UPDATED: this entry; AGENTS.md (its normative section, with
  its heading renamed); PRINCIPLES.md's P9; INTERFACES.md's rule
  about what "lands" as a change; the ROADMAP's constraints section
  and its deferral list; api.md, cli.md, machine-blueprint.md,
  media-spec.md, script-spec.md, blueprint-model.md,
  instance-model.md. CHANGELOG entries and older DECISIONS entries
  keep the wording that was accurate at the time they were written.

- D24 — THE REFERENCE GRAMMAR IS PINNED DOWN AS A CLOSED SET OF
  RULES — DECIDED (owner, 2026-07-23, the milestone-7 "decide first"
  item). Supports U1, U4, U5; P11; G3, G6, G7. This grammar is
  normative in [blueprint-model.md](../docs/spec/blueprint-model.md):
  the reference grammar is **closed, made of exactly two grammar
  rules**, the allowed-character check and the two grammar rules
  together decide what's valid, and references are refused outright
  wherever they'd appear in an identity field, a dependency-graph
  field, or one of the closed vocabulary fields.

  The lasting part of this decision is *why* it needs to be closed:
  an open-ended grammar can never say what it refuses, so every
  future extension to it would silently reinterpret text that used
  to parse successfully under the old rules. As one specific
  consequence: a media name is allowed to start with a digit, while
  a property key is not — because the `@` sigil already tells you
  what kind of token it is, while a property key also appears bare,
  on its own, at the point where it's declared, and a leading digit
  there would instead get parsed as a duration value.

- D23 — THE USE-CASE LIFECYCLE IS DEFINED, AND A RETIRED NUMBER
  LEAVES NO PLACEHOLDER — DECIDED (owner,
  2026-07-23). Supports P8, P23. The actual process this settles —
  the three document locations, the clarify/retire/supersede
  actions, and the single global U-numbering sequence — is
  normative in [README.md](README.md) and isn't restated here. Two
  specific rulings from this decision have no other natural home,
  and both get cited by later entries:

  - **NO PLACEHOLDER STUB.** A retired or superseded use-case number
    leaves nothing behind in its place: the resulting gap in the
    numbering sequence *is itself* the history, and whatever
    replaces it names what it's carrying forward, so old citations
    still resolve correctly. This is what "no stub, per D23" refers
    to when cited, and it's why a dead proposal's number is
    permanently spent rather than ever being reused.
  - **The word "deprecated" is rejected** as terminology here. A use
    case is either *retired* (dropped entirely) or *superseded*
    (replaced, with its successor named explicitly); "deprecated"
    implies a grace period that this lifecycle process doesn't
    actually offer.

  CONSIDERED AND REVERSED: creating a separate `planning/ISSUES.md`
  file. The project's issue tracker is already the open door for
  reporting things, and this planning directory is meant to be the
  project's own internal voice — adding a third intake point here
  would have split the triage process across two separate systems.

- D22 — THE BLUEPRINT REVISION ROUND — DECIDED (owner,
  2026-07-23, the second decision round held the same day,
  superseding the earlier four-component design for media and
  composition before any of it was actually implemented). Supports
  U4; P10. The resulting shape is normative
  in [blueprint-model.md](../docs/spec/blueprint-model.md).

  Kept from the earlier design: **containment declared only from
  the child's side** — dropping the earlier batch-style `children`
  list form — was considered and rejected as being sugar on top of
  the one real underlying meaning, rather than a genuinely separate
  meaning of its own, so the `children` form is kept as sugar that
  expands into individual child-declares-parent statements, and
  both spellings remain valid.

- D21 — CODEX ENTRIES ARE NAMED AS GENERIC STARTING POINTS, NEVER
  AS VERSION-SPECIFIC LIBRARY ENTRIES —
  DECIDED (owner, 2026-07-23, closing the open point from the
  generic-blueprint walkthrough). Supports U11; P11 — retrofitted
  2026-07-27. No codex entry names
  a specific version — it's generic `openbsd`, generic `freedos`,
  and so on; "the codex is a launching point for real blueprints
  only" (in the owner's words). Entries
  are named after the system they represent; the actual version
  information lives inside the blueprint file itself, as the source
  component's URL and hash (the "two-field bump" pattern), so
  bumping a codex entry's version is really just a content update
  under an unchanged file name, which only reaches newly seeded
  copies going forward — the never-overwrite
  rule means anyone's existing copy stays entirely theirs, unaffected.
  Running multiple versions side by side, pinning a specific vintage,
  or maintaining variants are all things that belong to the user or
  their project, not to the codex itself:
  seed it, rename it, make it a real project file — this approach
  eliminates the whole need for the codex to support multiple
  coexisting versions of the same entry, which is what had
  originally motivated giving entries version-specific names.
  Scripts are named after the workflow they drive
  (`freedos-install`), never after a specific release: the
  branching-wait design already handles multiple versions through
  direct observation of the screen, and a script's actual supported
  version range is visible just by reading its own handlers. The
  original recommendation had been a split rule (generic by default,
  version-specific only when versions deliberately need to
  coexist) — the owner went further than that: coexistence in the
  codex is simply not supported at all. The `-plain` variant naming
  marker dissolves with it: the launching point IS the plain
  install, and any variants belong entirely to users to create
  themselves. SCOPE, as the owner defined it: entries
  keep nominal version control points where easy — the adjacent
  url+sha knobs, seam comments pointing at them — acknowledging
  version churn; but the codex NEVER promises a comprehensive
  guaranteed-working asset set across systems and versions
  ("impossible!"): an entry is tested as shipped against the
  one release it tracks; a bumped copy is the user's, aided by
  fail-closed verification and observation-driven scripts,
  warranted by nothing. REALIGNMENT STILL TO COME (per
  the no-backward-compatibility rule): `freedos-1.4-plain.rlqb` →
  `freedos.rlqb`,
  `freedos-1.4-plain-install.rlqs` → `freedos-install.rlqs`,
  and the mentions across script-spec (the reference-script
  pointer), machine-blueprint.md, and cli.md follow at
  implementation realignment. FILES UPDATED: codex.md (the naming
  guidance under Naming conventions; the table examples; both
  `run-script` examples).

- D20 — A DECLARED DEFAULT VALUE RANKS BELOW EVERY SUPPLIED SOURCE,
  BUT ABOVE ASKING THE USER INTERACTIVELY — DECIDED (owner,
  2026-07-23), settling the open branches D19 left pending. Supports
  P7, P13. Normative in
  [script-properties.md](../docs/spec/script-properties.md).

  A declared `default=` value ranks **below** every source that
  actually supplies a value, and **above** the fallback of
  interactively asking the user: it's the script author's own
  fallback value, so anything the person actually running the
  machine explicitly supplies beats it, and its whole purpose is to
  make sure the interactive prompt is never even reached when a good
  default exists. Host-provided facts (`rlq.*`) are treated as
  unanswerable when they're empty, rather than as empty strings — a
  blank username isn't a real answer, and silently binding an empty
  string as if it were one just produces a run that fails somewhere
  later on, for a much more confusing reason.

- D19 — HOW A PROPERTY GETS ITS VALUE FOLLOWS A FIXED, CLOSED ORDER,
  AND EVERY STAGE OF IT IS NAMED — DECIDED (owner, 2026-07-23).
  Supports P7, P13, P21.
  Normative in
  [script-properties.md](../docs/spec/script-properties.md).

  **The order in which property sources are checked is fixed and
  closed**, and that's the actual ruling here: where a value came
  from is a fixed sequence that can be stated in full, not an
  open-ended search that just stops as soon as something is found.
  An open-ended search couldn't actually be reported back to the
  user — the dry-run's `describe_sources` output can name exactly
  where each key's value came from only because there is exactly one
  correct answer to give; and someone debugging why a value came out
  wrong needs to know the actual *rule* being followed, not just the
  specific outcome they got.

  The implementation itself is **custom-built, rather than based on
  an existing configuration library**: the layering involved is
  small, its exact behavior is specific to this project, and any
  existing dependency would have had to be bent out of shape to
  match it (P21).

- D18 — BLUEPRINT FORMAT DESIGN: THE RULE FOR HOW COMPUTATIONAL
  FEATURES ARE ALLOWED TO GROW — DECIDED
  (owner, 2026-07-23). Supports U4, U5; G2. **Its original choice of
  JSONC as the format is later superseded by D102; its HCL2
  rejection is changed by D26**, which moved HCL2
  from "deferred" to permanently "closed."

  THE GROWTH RULE, which is the part of this decision that's still
  in force today: a language construct that only *enriches a
  value* — meaning it still expands into plain data that Reliquary
  itself computes — is allowed to be added to the blueprint format;
  **general-purpose computation is never allowed into the JSON data
  tree itself.** If general computation is ever needed, it can only
  arrive as a separate layer that itself produces plain blueprint
  data as its output — either through generation done above the
  format via the embedding API, or through a separately specified
  evaluation layer (Jsonnet being the leading candidate for that, if
  it's ever built).
  In-tree function objects and string templating inside the
  blueprint format itself are permanently rejected: a blueprint
  file that performs computation is a blueprint file that no tool
  can safely read without actually running it first.

- D16 — THE BLUEPRINT `name` FIELD IS REINSTATED — DECIDED (owner, 2026-07-22),
  reversing the drop made on 2026-07-21. Supports U11 — retrofitted
  2026-07-27. `name` comes back as an optional
  human-readable display name for a blueprint, kept entirely separate
  from its file-stem-based identity: the file stem remains the one
  and only key used for selection
  (`--blueprint <stem>`), and a machine's own id stays `<stem>-<n>`
  — so
  `name` never selects anything, never renames anything, and has no
  effect on machine behavior whatsoever. It's simply searched by
  `search` alongside `description`, shown in
  listings wherever a friendlier label than the raw file stem is
  useful, and gets recorded into machine state. WHY: in the owner's
  words — "name should be part of the
  spec, we'll regret not having it at some point" — reserving space
  for a separate display label, distinct from the file stem, is
  cheap to do now, and freezing the naming design is free before a
  1.0 release, but never free after it (this is the same "reserve
  space early"
  principle already recorded elsewhere in this file). The original
  concern that led to dropping the field (a
  second name could drift out of sync with the stem, and
  duplicate what `description` already does) is accepted here as a
  real UX caveat, not as a reason to leave the
  field out entirely — tools simply fall back to showing the stem
  whenever `name` isn't set. FILES UPDATED:
  machine-blueprint-reference.md (a new `name` section added; the
  `description` section's claim that "there is no display-name
  field" is removed, and `search` now matches against `name` too),
  machine-blueprint.schema.json (the `name` property added back).
  The actual
  implementation had never removed `name` in the first place (the
  original drop was only ever a documentation change, never coded),
  so the milestone-6 field-validation task keeps handling it as-is,
  and the codex's
  `freedos-1.4-plain.rlqb` entry's existing `name` field remains
  valid.

- D15 — THE MILESTONE 6 "DECIDE FIRST" QUESTIONS ARE RESOLVED —
  DECIDED (owner, 2026-07-22): Supports U1; P8 — retrofitted into
  that principle on 2026-07-27. These are the three "Decide first"
  questions the ROADMAP had made milestone 6's implementation
  conditional on. Interface review (planning/INTERFACES.md): both
  the machine-state operations and the blueprint format are
  user-facing interfaces; Q1 confirms behavior that was already
  specified and already aligned with a use case (U1's install
  pattern and mid-run media swaps); Q3 tightens validation with no
  impact on any use case (easily approved); Q2 changes no interface
  at all — it's purely internal policy — so none of these require
  amending any use case.
  - Q1, RECONFIGURING A RUNNING MACHINE: `insert`/`eject` work
    whether the machine is running or stopped; `set-boot` and
    `apply` only work on a stopped machine. Making live media
    changes is ALLOWED — running `insert`/`eject` on a running
    machine is a live media change the guest can actually see
    happen; running it on a stopped machine is purely an edit to
    saved state, reconciled the next time the machine starts. This
    CONFIRMS the contract that already existed (script-spec.md's
    "Insert and eject" section already said "Both verbs work on a
    running machine ... and on a stopped one"; cli.md and the CLI
    backlog's item 3 already said "running-or-stopped for
    insert/eject") — it doesn't change that contract. `set-boot`
    stays stopped-only, because it's a launch-time firmware setting
    with no live effect; `apply` stays stopped-only too, since
    memory, CPU count, and drives are all hardware topology
    decisions. Making everything uniformly stopped-only was
    CONSIDERED AND REJECTED (even though it had originally been
    recommended): it would have directly contradicted the
    already-specified running-or-stopped rule, and the script
    language's own live-dispatch design, where a script actively
    drives a running guest and swaps media mid-run. CONSEQUENCE —
    this reveals an implementation gap, not a change to the spec:
    today's `machines.py` currently enforces insert/eject as
    stopped-only (a shortcut taken back in milestone 1), so the
    milestone 6 work needs to add a live-QMP change path (using an
    identity-verified session) for when the machine is actually
    running, and AGENTS.md's current line "all three require a
    stopped machine" reflects that old shortcut, and will be
    corrected once hot insert/eject actually lands.
  - Q2, RUNNING MULTIPLE MACHINES AT ONCE: there's no home-wide
    limit on how many machines can run simultaneously. The
    per-machine lock and the per-start identity-verification model
    already make running things concurrently safe — each machine
    gets its own cache directory, its own backend process, and its
    own auto-allocated network port — so the real, honest limit is
    just whatever host resources are available (memory, free
    ports), which naturally shows up as an ordinary `start` command
    failure when exhausted. A configurable cap on concurrent
    machines was CONSIDERED AND REJECTED: it would just be policy
    surface area with no actual underlying guarantee behind it.
    Files updated: instance-model.md (its "The machine state"
    section).
  - Q3, `size`/`base` ON A CD-ROM DRIVE: rejected. A `cdrom` drive's
    only possible content source is `media` (or nothing at all,
    `null`) — a read-only optical medium has nothing that can be
    resized, diffed against a base, or synthesized, so `size`,
    `base`, and `hostdir` all now require a writable medium type
    (`hdd` or `floppy`) — matching the existing prohibition that
    already applied to `hostdir` on a cdrom drive. This closes an
    open finding from the earlier JSON-schema round (the schema had
    only encoded the explicitly stated rules, and the field
    reference's note that these fields are "meaningful for hdd and
    floppy" hadn't actually prohibited them anywhere else). Leaving
    this permissive was CONSIDERED AND REJECTED (it would have let
    a nonsensical blank/writable-optical-drive combination validate
    successfully). Files updated: machine-blueprint-reference.md
    (the `size` and `base` sections, and the Values rule),
    machine-blueprint.schema.json (the `cdromDrive` schema no
    longer allows `size`/`base`, and now requires `media`). This is
    enforced in `blueprint.py` as part of the
    field-reference-validation task.
  Files updated across all three: planning/TASKS.md (the milestone-6
  task list — task T0 landed), instance-model.md,
  machine-blueprint-reference.md, machine-blueprint.schema.json.

- D14 — A NEW MILESTONE ADDS A LOCAL HTTP SERVER FOR SERVING
  INSTALLER ANSWER FILES — DECIDED (owner, 2026-07-22). Supports U1,
  U4, U5; G1 — retrofitted into that goal on 2026-07-27. A new
  ROADMAP milestone 5 is inserted, adding the same kind of ephemeral
  local HTTP server Packer uses, for serving Kickstart, preseed,
  AutoYaST, `unattend.xml`, and similar installer answer files
  (documented in docs/spec/http-serve.md). The former milestones 5
  through 12 are renumbered to 6 through 13. Interface review
  (planning/INTERFACES.md): this aligns strongly with U1, and with
  U4/U5 wherever these answer files are the installer's own native
  mechanism — easily approved, with no use-case amendment needed.
  Interfaces touched: the scripting language, the CLI/API (the
  server's lifetime is scoped to one run), and the authored-asset
  directory layout. This is distinct from the now-deleted
  property-binding "response file" concept (same term, but THE
  RESPONSE-FILE CONCEPT ITSELF IS DELETED). The ROADMAP's "Procedural
  and declarative" section is updated to match: wherever an
  installer's own answer files already exist, they're now served
  the way Packer serves them, rather than being replaced by
  something competing with them; goal G1 remains the rule that the
  control plane stays agentless — it isn't a ban on using an
  installer's own native answer-file mechanism. Older DECISIONS
  entries keep whatever milestone numbers were accurate at the time
  they were written; forward-looking references in the ROADMAP,
  TASKS, and design status notes are updated to match the
  renumbering. Files updated: the ROADMAP (its synopsis, the
  procedural/declarative section, milestones 5 through 13, the
  Horizon section, and the note closing out guest-communication),
  docs/spec/http-serve.md (newly created), forward references in
  TASKS, and the status notes in backend-adapter,
  guest-communication, and landmarks design documents.

- D13 — THE SCRIPT PARSER USES RELIQUARY'S OWN TOKENIZER FEEDING A
  LARK-BASED PARSER — DECIDED (owner,
  2026-07-22), following the "no JSON in scripts" decision that made
  this possible. Supports P21 — retrofitted into that principle on
  2026-07-27. The grammar itself lives in Reliquary/script_grammar.lark,
  mirroring the normative EBNF grammar already in script-spec.md;
  Reliquary's own tokenizer feeds tokens into it through a custom
  lark lexer. This was decided based on evidence from three separate
  experiments:
  - A lark grammar can express the entire typed EBNF grammar —
    headers, property declarations, phases, branching waits,
    reactive phases, every kind of action — in roughly 45 lines,
    using the LALR(1) parsing algorithm. Before the
    embedded-JSON exception was removed from the language, this
    wasn't even possible — the grammar couldn't parse a script at
    all — which is exactly what changed the answer here.
  - Using lark's OWN built-in lexer instead of Reliquary's custom
    one was CONSIDERED AND REJECTED: its error messages only
    describe things at the raw-token level (like "No terminal
    matches '4'," compared to Reliquary's own "invalid duration:
    '45' (durations carry a unit: ms, s,
    m, or h)"), and in one case it actually mislabeled the word
    `timeout` as if it were a keypress name. Running the
    `match_examples` test against it only correctly recovered 4 of 7
    hand-authored error messages, failing every time the same
    underlying mistake occurred after a different verb — because its
    matching depends on parser state, the number of test cases
    needed grows as mistakes multiplied by contexts, and it silently
    gets worse in the gaps nobody happens to test.
  - The hybrid approach (Reliquary's tokenizer, lark's parser) keeps
    the best of both: it was verified that every one of Reliquary's
    own lexical-level error messages survives unchanged all the way
    through the lark parsing layer.
  - The phrase `press enter` broke the very first implementation
    attempt — `enter` is both a verb name and the name of a key, and
    a lexer that doesn't look at surrounding context has to decide
    which one it is before the parser even knows it's inside
    `press`'s argument list. So keywords are only recognized when
    they appear in the "node name" position — which is exactly what
    script-spec.md already required: "slot, key-name, and
    machine-state values are name tokens whose closed vocabularies
    are checked by validation, not the grammar."
  - THE RULE THIS ESTABLISHES: the grammar itself is only responsible
    for node names and the basic types of positional arguments;
    modifiers are handled uniformly at the grammar level, then
    checked against each specific node's own allowed signature inside
    the transformer code, which can then name the specific node and
    list exactly what it accepts. The separately numbered validation
    rules stay layered above the grammar, not inside it. Trying to
    encode rule S8's "at least two handlers" requirement directly
    into the context-free grammar was attempted and then reverted —
    doing so turned the error message into a generic "Unexpected
    token _BLOCK_CLOSE" pointing at the closing brace, instead of a
    message that actually names the missing wait condition.
    script-spec.md's existing choice to enforce these numbered rules
    "over the parse tree rather than encoded in the grammar" is what
    actually protects the quality of the error messages — it isn't
    just an incidental implementation detail.

- D12 — SCRIPTS NO LONGER CARRY EMBEDDED JSON DATA — DECIDED (owner,
  2026-07-22). Supports U6; G7 — retrofitted into that goal on
  2026-07-27. A script file no longer carries any embedded assets at
  all. Both the `media <label> { ... }` block
  and the `landmark <name> { ... }` block are deleted entirely;
  media definitions (`.rlqm` files) and landmark declarations
  (`.rlql` files, plus their `<name>.<n>.png` image renderings) are
  now their own separate authored files, located next to the script
  using the normal authored-asset
  resolution rules, and referenced from the script by name using
  `@name`. FILES UPDATED:
  script-spec.md (its "Embedded media definitions" and
  "Installation into the media library" sections are deleted, and
  the embedded-data exception is removed from both the core grammar
  and the normative EBNF),
  media-spec.md, landmarks.md (its embedded form deleted),
  the ROADMAP, INTERFACES, use case U6 (amended), and the
  implementation itself (the parser's media-handling code,
  the `EmbeddedMedia` class, and the node layer's special-case
  machinery for embedded data are all deleted). This decision round
  found and recorded the following:
  - WHAT TRIGGERED THIS: the embedded-install design read as an
    awkward add-on. Three separable costs were
    identified — the embedded-JSON exception was
    the *only* exception to an otherwise purely text-based language,
    the actual install protocol involved
    (a five-step transactional write, rules for handling collisions
    and coalescing, partial-overlap errors, a `fetch-media --script`
    command) was itself substantial, and there was an
    unresolved design problem (numbered [06], where the label
    named an installed file while `@` named an item inside it) — a
    confusing split.
  - CONSIDERED AND REJECTED: deleting only the media blocks, while
    keeping the embedded-JSON exception itself. This
    wouldn't have actually removed the underlying exception, since
    embedded landmark blocks (per landmarks.md, "the same JSON
    schema as `.rlql` plus
    inline base64-encoded image data") would have reintroduced it
    anyway at milestone 12,
    and it would have left two very similar kinds of authored assets
    with completely opposite policies on whether they get bundled
    into the script.
  - CONSIDERED AND REJECTED, for the same underlying reason: deleting
    the install protocol while keeping the embedded blocks
    themselves. This removes the protocol's complexity
    but keeps the actual lexical exception in the grammar.
  - THE ARGUMENTS THAT ACTUALLY DECIDED DELETING BOTH: the embedded-data
    exception was the only special case anywhere in the node
    grammar, and removing it makes the entire language
    surface uniform and parseable with a simple LL(1) parser end to
    end. A script file is plain UTF-8
    text, so any embedded binary image data would necessarily have
    to be base64-encoded — measured out, this comes to roughly a
    12-to-1 up to 100-to-1 ratio of encoded-data size to actual
    procedure-code size for a
    twenty-landmark GUI workflow, and the design had already shown
    hesitation about this very problem, via its still-open "trailing
    assets zone"
    question. And embedding data permanently locks in the asset's
    file format, since anything embedded inside a text script can
    never later become a non-text format (keeping the
    `.rlql` landmark format able to become non-text in the future
    only stays possible if landmark declarations live in their own
    separate files).
  - The "avoids needing a second file format" justification
    originally given for embedding was found to have already broken
    down in a small but telling way: `.rlqm` media-definition files
    use the more permissive JSONC format, while the embedded
    version inside a script had to use strict JSON, because tracking
    matching braces could not survive a JSON comment being present —
    meaning the surrounding script format had already
    forced the embedded form to accept less than the separate file
    form did.
  - The property of everything living in a single file was GIVEN UP
    HERE, KNOWINGLY. The evidence originally
    cited to support that property didn't actually hold up: U4
    already describes "the repository carries only blueprints, media
    definitions, and Reliquary scripts" as living side by side in a
    repository, not merged into one file, and U1's single-command
    install path already seeds three entirely separate codex files.
    The real loss here is casual sharing — being able to
    paste one whole workflow into a gist or a bug report — but that
    capability was already lost for anything that used landmarks. A
    separate bundle file format, layered outside the language
    itself, remains available later as a purely additive addition
    (per goal G7).
  - CONSEQUENCES OF THIS DECISION, folded into other documents: the
    "label" concept loses its only remaining purpose,
    which closes out the previously unresolved design problem [06];
    the `fetch-media --script` CLI command and the
    `fetch_media(script=)` API parameter are both deleted;
    check-script's planned validation of embedded media, and its
    special-case allowance for "writing to
    `media/`," both go away; ROADMAP milestone 5
    no longer targets embedded-install as a goal; and the script
    recorder now always emits its draft as script plus asset files —
    one single output mode instead of two different ones.

- D11 — THE JULY 2026 SCRIPT-LANGUAGE REDESIGN — DECIDED (owner,
  2026-07-21). Supports U6; G2, G3, G7. The redesign itself is
  normative
  in [script-spec.md](../docs/spec/script-spec.md), which carries
  the full typed EBNF grammar and every rule this decision round
  actually settled — so the design itself isn't restated here. What
  this entry exists to record is the *shape*
  of the change: the old grammar couldn't even parse the reference
  script, and the fix was replacing the terminal production with an
  entirely new statement model, rather than patching the individual
  grammar rules that were
  failing. Later decisions amended much of the detail (D24 redid the
  reference grammar, D26 redid the reach and string rules, D60 redid
  pacing) — read the spec itself, never this entry, to understand
  what the language actually is today.

- D10 — WORKING THROUGH THE GUIDING-PRINCIPLES BACKLOG — DECIDED
  (owner,
  2026-07-21, a panel checking necessity and sufficiency, worked
  through adversarially, use case by use case). Supports U1, U2, U4,
  U5, U6, U14; G2, G3.
  THE VERDICT, which is the lasting part of this: **the primary
  application surfaces are both necessary and already minimal** —
  every gap this panel actually found
  turned out to be the specification lagging behind the principles,
  never an actually missing surface,
  and each one was closed by updating its own spec during the
  realignment pass. The
  original work list itself is now fully spent; what remains useful
  is the finding itself — explaining why no new surface was ever
  added to close any of these gaps.

- D9 — WORKING THROUGH THE BLUEPRINT-SPEC BACKLOG — DECIDED (owner,
  2026-07-21).
  Supports U2, U4. A work list checked against the media and
  blueprint
  specs: the media spec already tracked the guiding principles
  closely, and the actual gaps
  clustered in the blueprint spec instead. Every item on the list
  was closed by updating
  [blueprint-model.md](../docs/spec/blueprint-model.md) and the
  blueprint guide/reference documents, which are now normative;
  nothing on the list was
  rejected, so nothing else survives beyond what already landed.

- D8 — WORKING THROUGH THE CLI DESIGN BACKLOG — DECIDED (owner,
  2026-07-21).
  Supports U1, U3, U4, U14; P6. THE VERDICT: the two-layer lifecycle
  vocabulary, the parity requirement between CLI and API, the
  failure modes for selecting a machine, and the rule against
  interactive prompts are all sound as designed; the actual gaps
  were just conventions that had never been written down, and every
  one of them has since landed in
  [cli.md](../docs/spec/cli.md). Kept here: the specific alternative
  spellings that were considered and rejected, since each one is a
  plausible thing to get proposed again later.

  - **Renaming `run` to `runs`** — rejected: nothing is gained in
    meaning, and `run`
    already exclusively refers to run records.
  - **Adding a `--format` flag** — rejected as speculative, since
    nobody's asked for it yet ("YAGNI"); converting to this before a
    beta release
    stays free to do later if it's ever actually wanted.
  - **Using `--as` for a new blueprint's name** — rejected because
    `as` is a reserved Python keyword; `--name` was chosen instead,
    which maps cleanly onto a `name=` parameter in every language
    binding.
  - **Both an explicit `--stdin` flag and a hybrid auto-detection
    approach** — rejected: having exactly one spelling and adding
    zero new surface area
    beats supporting two different ways to do the same thing, and a
    secret value should never be passed as a plain command-line
    argument anyway, since it would then be visible in process
    listings and shell history.
  - **The three-flag family** `--blueprint-name` / `--machine-number`
    / `--machine-id` — rejected: removing flags was the better fix
    here than adding more of them.

- D7 — WORKING THROUGH THE API DESIGN BACKLOG — DECIDED (owner,
  2026-07-21).
  Supports U14; P6, P7. THE VERDICT: the rule that a function and
  its CLI command share the same name, the rule that a `--json`
  flag's twin returns the exact same structure, handles that can
  only be read from (never written to) directly, and the rule that
  any deliberate omission must be explicitly named, are all sound as
  designed; the actual
  gaps were unnamed conventions and functions missing their
  CLI-equivalent "twin," all of which have since been documented in
  [api.md](../docs/spec/api.md). Rejected alternatives, kept here
  specifically because a
  later round would otherwise likely propose them again:

  - **A fully mechanical, one-to-one mirror between every CLI flag
    and every API parameter** — rejected: parity binds
    the pair as a whole, not each function alone, so a flag doesn't
    necessarily need to become a parameter of the same name.
  - **Separate `open_run()` / `get_run()` functions** — rejected in
    favor of a single `attach_run()`, which is the verb this
    design's own
    doctrine already uses: a synchronous run is really just an
    asynchronous one plus immediately attaching to it.
  - **A full, deeply nested tree of error classes covering every
    possible domain** — rejected as premature speculation ahead of
    demand; error
    classes are meant to grow additively over time, never as a
    breaking redesign. Strictly requiring every error class name to
    end in
    "Error" was rejected along with this.
  - **Having the CLI itself own a checkpoint that detects a
    mismatch** — rejected: the resulting error only names
    one specific file, while deciding whether to refetch is really
    the calling code's own decision to make.
  - **Automatically calling `cancel()` when a handle object is
    garbage-collected, and Python `with`-block sugar that cancels
    automatically on exit** — both
    rejected: exactly when garbage collection happens carries no
    defined meaning in any language binding, and the `with`-block
    sugar is really the same trap opted into on purpose. A handle
    is meant to only ever follow along with something, never to own
    or control it.

  The asynchronous-run surface these design decisions actually shape
  is **feature F6**, which remains deferred to the backlog and
  unbuilt; these rejections stand ready, waiting for that design.

- D6 — WORKING THROUGH THE GAP-CLOSURE DESIGN BACKLOG — DECIDED
  (owner, 2026-07-21).
  Supports U1, U5, U6, U14; P6, P7; G2. This covers the five
  remaining gaps left open by the earlier guiding-principles
  backlog, worked through in order of highest leverage first. **Most
  of what this decision actually settled has since been deleted
  rather than ever shipped**:
  the run-record half of it — the `transcript.txt` file, the
  run-records archive,
  the `--detach` flag — was removed along with **D36**, and the
  export half of it still sits unbuilt
  on the Horizon — so those specific rulings and their rejected
  alternatives no longer guard anything
  that currently exists. What's still relevant is whatever still has
  a live subject to apply to:

  - **Printing a one-line outcome summary to stdout** — rejected as
    an invitation for scripts to scrape it. The
    discipline this rejection protects now belongs to surface S7
    instead.
  - **Direct access to the console device for prompting the user** —
    rejected as being too
    platform-specific; prompt text is written to stderr instead, and
    the answer is read
    from stdin.
  - **A writable/read-only flag on a host directory drive** —
    rejected, and explicitly recorded as *a capability an AI agent
    invented on its own, that the owner never actually asked for*.
    This is recorded here specifically because the rejection is
    about where the idea came from, rather than about its design: an
    unrequested capability does
    not get added just because it happens to sound plausible.

- D5 — THE RUN-COLLECTION FEATURE IS DROPPED ENTIRELY — DECIDED
  (owner, 2026-07-22, the "out-of-band" decision round; the owner
  revisited gap-closure items 2 and 3, settling the question with
  "what use case cannot be met without it?" — the answer was none;
  this mechanism had only ever been about custody and ergonomics,
  never about capability; use case U6 was double-checked and found
  unaffected — screen-capture recording stays in, transferring
  authored files back out does not). Supports U14 — retrofitted
  into that use case on 2026-07-27; the original entry argued from
  U3, which D51 later retired into U14, and the note "U6 verified
  untouched" is just a sanity check that nothing broke, not a real
  requirement being satisfied.

  DROPPED ENTIRELY: the `results` header, the `stage`/`collect`
  verbs (validation rule S15 goes with them, and they were the
  language's only way of touching the host filesystem at all — this
  also dissolves design example 05's "two worlds" open question,
  since a script's strings are now guest text only), the CLI command
  pair `stage-files`/`collect-files`, and the whole concept of
  Reliquary owning custody of run output — the `runs/<n>/output/`
  directory is no longer part of the record; a "record" is now just
  the event stream, the transcript, and screenshots (INTERFACES.md's
  "Recorded outputs" section is updated to match). FILE EXCHANGE NOW
  HAPPENS OUT-OF-BAND: while a machine is stopped, on every control
  plane, its drives are just plain files/directories on the host (a
  `hostdir`-type drive literally *is* its host directory; a disk
  image file is entirely the user's own business, using their own
  tools). Reliquary neither mediates nor records any of this. The
  rules at the edges of this (a running machine's drives can't be
  touched this way, the media cache is read-only by convention,
  `runs/` is append-only, and machine-state files belong to
  Reliquary alone) are documented in instance-model.md's "The
  machine directory and out-of-band access" section. A NEW QUERY WAS
  ADDED: `get-machine-dir` / `get_machine_dir(machine=|blueprint=)`
  — returns the machine's cache directory as an absolute path; works
  at any phase, using the standard selectors, and `--json` output
  serializes it as a plain string. DEFERRED, WITH A ROUGH SHAPE
  ALREADY SKETCHED (in the ROADMAP's "Horizon" section): in-language
  `list-files`/`get-files`/`put-files` commands (with matching
  `list_files`/`get_files`/`put_files` API functions), addressed as
  `<drive-key>:<path>`, honest about capability at rest on a
  per-call basis, excluding media drives, working recursively, with
  no custody retained; details like `get-files`' default destination
  belong to whatever future milestone actually builds this — the
  value of building it concentrates exactly where the out-of-band
  approach gets thin (non-QEMU backends, which have no `hostdir`
  support, and non-FAT filesystems), so it should be sequenced at or
  soon after the second backend adapter lands. [**That deferred
  feature is now closed and rejected, not merely still pending**:
  the in-band file family actually was built later (D62) and then
  deleted again by **D108**, which placed a machine's file content
  permanently outside Reliquary's scope. The out-of-band door this
  entry created is now the permanent route, not just a temporary
  fallback.] One cost is knowingly accepted and named here: keeping
  a history of artifacts across multiple iterations is now entirely
  the caller's own responsibility to manage (U3 already made the
  calling agent responsible for interpreting results, so this is
  consistent). Use-case review: no amendment needed — this aligns
  strongly with U3 (interpretation happens on the agent's side; the
  record exists as evidence, not as a permanent warehouse). FILES
  UPDATED: script-spec.md (its action list, strings table, header
  table and surrounding prose, its grammar, with S15 removed — S1
  through S14 remain, its severability section, the event-stream
  transfer bullet, the preflight list, a new "File exchange — a
  named omission" section replacing the old stage-and-collect
  section, the run-directory tree diagram, a per-test paragraph, and
  a bundle note), cli.md (a new "The machine directory" section
  replacing "File exchange," the machine-scoped command list, and
  media-naming prose), api.md (the surface table row, and a
  realignment note), the ROADMAP (its "The CLI" state-operations
  paragraph and synopsis, the script-section's offline paragraph,
  the primitive-vocabulary list, a phrase about interaction-run
  custody, spike-8's exclusion list, realignment deliverable 3, a
  control-plane vvfat note, and the Horizon bullet), INTERFACES.md
  (the recorded-outputs section), instance-model.md (a whole new
  section), machine-blueprint.md (the `runs/` directory contents,
  mentioned in two places), machine-blueprint-reference.md (the
  `hostdir` prose and a note on division of labor), codex.md
  (naming-related prose), and planning/design/script-examples/05,
  which is rewritten as a regression note plus a README table row.
  Gap-closure items 2 and 3 (from D6) are annotated above as
  SUPERSEDED IN PART.

- D4 — THE USER-PROPERTIES DESIGN ROUND — DECIDED (owner,
  2026-07-21, a round that compared this design against how Docker
  handles a similar problem). Supports U1, U4, U5,
  U14; P13. The resulting design is normative in
  [script-properties.md](../docs/spec/script-properties.md) and
  cli.md; what's kept here is the list of rejected alternatives,
  each one a guard against it being proposed again, restated in
  today's terminology.

  - **The word "registry" is reserved for future use, not rejected
    outright.** The actual concept being designed here is *user
    properties*; "registry" reads much more like a remote
    artifact-distribution service (the way Docker, npm, or an OCI
    registry work), so that word is kept free for a possible future
    asset-sharing service.
  - **Wiring values only through the blueprint itself** (compose-file
    style, with the script never naming a key) — rejected: every
    single blueprint would then have to re-wire the same universal
    keys over and over. Instead, a script may suggest a key name, and
    a blueprint parameter can override it.
  - **`RELIQUARY_<KEY>_PROPERTY`** (putting the fixed part as a
    suffix) — rejected in favor of the prefix form,
    `RELIQUARY_PROPERTY_<KEY>`: this gives a common prefix that's
    easy to search for, and makes the reserved namespace immediately
    obvious.
  - **One single, packed environment variable holding everything** —
    rejected: it would need its own quoting syntax, it would collide
    with an existing `RELIQUARY_PROPERTIES` variable, it would break
    the "one secret, one environment variable" pattern CI systems
    rely on for injecting secrets, and it risks running into
    platform-specific limits on total environment size.
  - **A configuration layer that sits above the user's home-directory
    file** — rejected: project-level defaults are already the job of
    blueprint parameters, and having `--properties` *entirely
    replace* the home-directory file is exactly the tool needed to
    guarantee a fully isolated ("hermetic") run — so nothing from a
    user's personal environment leaks into a project-controlled run.
  - **Only allowing ordinary (non-secret) values through environment
    variables**, barring secret-bound keys from using them —
    rejected as a restriction people would just find a workaround
    for; an environment variable may carry a secret, but only inside
    a clearly named, explicitly-warned "plaintext" category. A
    command-line argument is never allowed to carry one, under any
    circumstances.
  - **Using JSON or TOML for the properties file format** — rejected:
    every other layer of the property system already speaks plain
    `key=value` syntax, and TOML's dotted-key nesting, plus the need
    to preserve exact formatting when rewriting the file, would
    require pulling in an external dependency. The actual filename
    chosen, `user.properties`, was picked specifically so editors
    would recognize the format automatically — going against this
    same design round's own original recommendation of
    `properties.rlqp`; the spec explicitly notes the caveat that
    this is *not* actually Java's `.properties` format — no Unicode
    escape sequences, no line continuations.
  - **A single file for bulk-loading many values at once** —
    rejected: repeatable command-line flags plus the API's own
    mapping type already cover this need, and the design can still
    grow additively later if that's ever not enough.

- D3 — JSON SCHEMAS FOR THE AUTHORED FILE FORMATS — DECIDED (owner,
  2026-07-21, a design round where all three open questions were
  settled by adopting the original recommendations).
  Supports U4; P9 — retrofitted into that principle on 2026-07-27:
  - planning/design/machine-blueprint.schema.json and
    media-definition.schema.json are AUTHORED (using JSON Schema
    draft 2020-12, fully self-contained, in strict JSON, covered by
    REUSE.toml licensing metadata; every spec example was checked
    against both, 32 out of 32 passing): the two are meant to stay in
    sync with each other — the prose specs remain the actual
    authority, and being schema-valid never by itself means
    something is actually valid (the schema only covers the
    structural subset that applies within one single document; rules
    that span multiple documents, and the capability-tier rules,
    stay defined only in prose). One single media schema covers both
    places media definitions can appear (a standalone library file,
    or an embedded block) — since both use the identical structure.
  - The `$schema` field: authored file formats stay entirely CLOSED
    before the beta release — a pinned schema reference would really
    just be a version field wearing a disguise; editors already bind
    to the correct schema through file-type association, which
    tracks whatever copy of Reliquary is installed. Using `$schema`
    as a versioned URL is recorded as the leading candidate spelling
    for an eventual version field, to be revisited at beta (see the
    ROADMAP's "Decisions still needed" section).
  - The validator: Reliquary's own parser remains the actual source
    of truth for validation (producing fail-closed diagnostics); a
    shared corpus of valid and invalid test fixtures is run against
    both the parser and the schema together — this will happen
    during the realignment pass, alongside the static-conformance
    corpus that's already queued for that same pass.
  - Spec rules that landed as part of this: boot entries must be
    unique by slot; `control-planes` entries must be unique; sha256
    hashes are accepted in either uppercase or lowercase, but written
    out in lowercase as the canonical form.
  - Deferred: the machine-state schema, and the mechanics of actually
    publishing these schemas (tracked as milestone 3, item 6); the
    exact grammar for media/item names, script labels, and input
    names stays an open question, to be settled alongside the
    asset-spec work — for now, the schemas just require a non-empty
    string.
- D1 — RESOLVED (owner, 2026-07-21). Supports (none) — this is
  purely a naming decision; no use case or principle dictates what
  something is called, and naming choices fall outside what the
  traceability rule covers (retrofitted into that understanding on
  2026-07-27).
  [Amended on 2026-07-28 — Supports P18. The naming half of the note
  above still stands — no principle dictates what a thing is
  called — but this entry actually settled more than just a name.
  The word "canon" was rejected because it names an abstract
  authority, whereas "codex" names an actual bound volume that
  things get copied out of — and that distinction is exactly what
  principle P18 states in its own words: a library of examples,
  meant to be read and copied from, never meant to be built on top
  of directly. P18 was clarified the same day to say this explicitly
  about the codex: it's meant to actually work, but it's never
  guaranteed stable, and both its names and its contents are free to
  change in any minor point release — it exists to help a consuming
  project start its own set of assets, not to be depended on
  directly — which is exactly the guarantee this original entry
  never actually made. This later note counts as a
  clarification rather than an amendment (the first exception under
  P23's rule): P18 never claimed the codex was stable in the first
  place, so stating plainly that it isn't doesn't change how any
  earlier decision should be read.] The project's built-in library
  of examples is named THE
  CODEX (it had originally been recorded as "change 'builtin library'
  concept to 'template
  library' ??"; the word "canon" was considered and rejected — a
  codex is the physical artifact, a bound volume that gets copied
  from, where a canon is the
  abstract idea of an authoritative list). FILES UPDATED: INTERFACES,
  USE-CASES, ROADMAP,
  AGENTS, CONTRIBUTING, cli.md, README, and the docs
  (builtin-library.md renamed to codex.md); the `Reliquary/builtins/`
  package directory is renamed to `codex/` at the point of
  implementation realignment.

## Retired decisions

Decisions that have since been fully overruled, or that no longer
apply. A retired decision no longer binds anything — it's kept here
only where it still has **real teeth** — meaning the position it
originally took is something someone could plausibly try to argue
for again, so keeping the record of why it was refused is still
doing useful work. A retired decision whose entire subject no longer
exists at all, or whose one useful insight is already fully captured
by whatever entry overruled it, is deleted outright rather than kept
around as clutter; the resulting gap in the numbering sequence is
itself the history, and the original text is still available in git
history. Reopening a retired decision requires going through the
same surface-change process as anything else.

- D62 — RETIRED (overruled by D108) — THE SET OF IN-LANGUAGE
  FILE-TRANSFER COMMANDS WAS COMPLETE, AND PRINCIPLE P16 WAS ARMED.
  Supports U14, U20; P16.

  **Kept because the position it took is exactly the one someone
  could plausibly argue for again**: that P16 obligates Reliquary to
  carry a file across the host/guest boundary itself, which is what
  armed this principle in the first place, and which D108 later
  specifically rejected. Under D108's exception, a machine's file
  content is now permanently out of Reliquary's scope by design, so
  the five commands this decision introduced are gone, and no
  current use case is asking for them back. This entry's rule about
  addressing files (one shared syntax for both files and
  directories, with the drive's root itself also expressible) died
  along with the drive-letter mapping it was written against, and
  D5's earlier `<drive-key>:<path>` addressing syntax stays dead
  too — nothing addresses a location inside a drive's contents at
  all anymore.

- D91 — RETIRED (overruled by D93 the same day it was decided and
  delivered) — A DEVICE IS A DECLARED MODEL NAME, JUDGED AT THE
  MOMENT A MACHINE IS ASSIGNED TO A BACKEND. Supports U22, U4, U14;
  P8, P10, P11.

  **Kept because both P25 and D93 cite it directly**, and because
  the position it rejected is exactly the one someone could
  plausibly argue for again: a shared device vocabulary being
  accepted into the project just because *one* backend happens to
  support it. D91 had built exactly that mechanism, and D93 removed
  it, replacing that bar with a requirement of general applicability
  across multiple backends — anything only one backend actually
  provides now has to stay behind that backend's own settings
  section, `backend-settings`. The one thing D91 got right about how
  this vocabulary should grow still survives, inside P25: the shared
  vocabulary should only ever contain what real demand has actually
  asked for, never simply whatever one particular backend happens to
  expose.

  D91's own rejection of a specific name still stands, though:
  **`virtio-rng-pci`** is QEMU's own internal bus-addressing
  spelling, not a name that's portable across backends, and
  admitting a device vocabulary built out of one backend's internal
  spellings is exactly the mechanism D93 shut down.

  **Narrowed by D125**: a random-number generator did eventually join
  the portable vocabulary, but under a portable name of its own
  (`virtio-rng`, checked against the assigned backend the same way a
  NIC's `model` is) — never under `virtio-rng-pci`, so this entry's
  objection to that specific spelling is unaffected.
