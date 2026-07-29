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

**This shelf emptied three times on 2026-07-27, by the two exits
it has.** F17 and F23 left by **delivery**, the ordinary one, and
their numbers retire with them (below). **F1 left by withdrawal**
(owner; D61) —
the first use of that exit, and the reverse of the move that is
supposed to fill this file. Nothing was rejected: the recorder's
design stands and its demand is live. What was wrong was the
pledge, which nobody ever made — the 2026-07-26 restructure housed
the feature here because its work items had nowhere else to live,
and D44's rename then converted what this shelf *claims*, from
agreement into a commitment to deliver, without re-testing its
occupants. **U6**, the use case F1 delivers, and **U2** left for
[proposed/USE-CASES.md](../proposed/USE-CASES.md) in the same
round; **U1** left upward, condensed and promoted to the current
list. D44 wrote the remedy — a pledge nobody means is withdrawn or
rejected, never left sitting — and this is its first use.

**It refilled and emptied again on 2026-07-28** (owner), with
**F2**, the backend adapter seam — pledged in the morning and
delivered the same day, so it joins F17 and F23 in leaving by the
ordinary exit rather than becoming the first entry to sit here.
Its demand, **U7**, was pledged in the same act
([USE-CASES.md](USE-CASES.md)) and had to be: F2 waited five days
for it, off the arc since 2026-07-23, and pledging a feature ahead
of the demand that justifies it is the error D61 undid. **U7 does
not travel with it**: the seam is what U7 needed built, and the
case itself is met only when a second adapter can materialize a
machine on the hypervisor a host actually provides. F2 was tested
against the size bound and pledged **whole**, so its number
retires unreused (D65) — the extraction was bounded by working
code and by a regression oracle, not by judgment about how much is
enough.

**It refilled again on 2026-07-29** (owner; D79) with **F24** and
**F25**, the two halves of `--dry-run` — and by the exit no feature
had used before. F11 was **cut on pledge**: too large for D42's
one-sprint bound, so its number retires unreused and a fresh one
comes to each piece, which is the rule this file's own preamble
states and the first occasion to apply it. D65 is the near miss —
F2 was weighed for the same cut a day earlier and pledged whole,
its pieces not being independently useful. These two are: each
lands coherently on its own, and neither waits on the other.

*(F17 — input pacing before guest input — delivered 2026-07-27,
so its number retires unreused. The `pacing` keyword, the
`statement > phase > header > built-in 0.1s` ladder, the
parse-time plan `check-script` reports, and the runtime pause are
recorded in [D60](../DECISIONS.md); the model is normative in
[script-spec.md](../../docs/spec/script-spec.md)'s Timing
section.)*

*(F23 — in-band listing and whole-tree file transfer — delivered
2026-07-27, the same day it was pledged, so its number retires
unreused. `list-files` / `get-files` / `put-files` and their
twins ship with one guest-terms address vocabulary shared with
`put-file` / `get-file`, a drive root sayable as `A:\`, a flat
listing document whose addresses feed straight back to the file
verbs, and a required `get-files` destination; the round is
[D62](../DECISIONS.md) and the surface is normative in
[cli.md](../../docs/spec/cli.md)'s in-band section.*

***P16 was armed by the same change***, which is the whole point
of the feature: it moved to the standing list with its residue —
an image drive has no in-band route — filed as a defect under
[TASKS.md](../TASKS.md), per D34 and D48.)*

*(F2 — the backend adapter seam — delivered 2026-07-28, the day it
was pledged, so its number retires unreused. One adapter API now
carries every backend operation
([design/backend-adapter.md](../design/backend-adapter.md), which
travelled out of `pledged/design/` with the delivery and records
the signatures it said it would): QEMU's half is
`reliquary/backend_qemu.py` and nothing above the seam names QEMU,
qcow2, QMP or a port; the agentless display console is
`reliquary/control_display.py`, reading the portable text-screen
contract rather than VGA bytes; assignment walks the D66 priority
order at materialization and takes the first backend both
available and capable, naming the backend and the requirement when
none is; VirtualBox, VMware Workstation and Hyper-V ship as stubs
that probe honestly and claim nothing; and the recorded VM
identity generalized to `{backend, backend-id, token, endpoint}`.
The oracle it was pledged against — the FreeDOS install script
passing unchanged — is the opt-in integration test, which is
unchanged by the extraction. The round is
[D67](../DECISIONS.md).*

***The three stubs are not a second backend.*** U7 stays pledged
and F3 stays proposed: what is delivered is the seam U7 demanded,
not the capability, and the order's tail remains intent recorded
(D66).)*

*(F24 — `create-machine --dry-run` — delivered 2026-07-29, the day
it was pledged, so its number retires unreused and the work items
go with it. A create's whole evaluation now runs with nothing
committed: the machine id it would allocate, the backend it would
land on, every drive's resolved plan, and each media reported
`cached` / `would-download` / `would-extract` / `local-present` /
`unbound` without a fetch and without a hash. `--backend` asks the
U7 question about a host one is not standing on, capability alone
deciding. The rulings the build produced — what a dry run refuses
and what it merely reports, why nothing is hashed, and the shape of
the `DryRun` F25 inherits — are [D80](../DECISIONS.md); the surface
is normative in [cli.md](../../docs/spec/cli.md)'s "The dry run".

**U7 stays pledged**, and this is the same distinction F2's
delivery drew: a static answer about a backend is not a machine
materialized on one. What F24 delivers is the question, not the
capability.)*

*(F25 — `run-script --dry-run`, and the end of the check family —
delivered 2026-07-29, the day it was pledged, so its number retires
unreused and the work items go with it. `check-script`, its twin and
its result type are **deleted, not aliased** (P9), and
`test_old_surface_purge.py` keeps them retired; `check_key` went
private with them, closing the P6 residue D79 found. The three
surface collisions landed as the entry read them: the selector is
optional under `--dry-run` alone and its presence chooses the tier,
`--json` becomes legal there while `--progress` and `--display` are
refused, and the positional keeps `run-script`'s own name. The
report now says how much of a script no static pass can promise
will run. The rulings the build produced are
[D81](../DECISIONS.md); the surface is normative in
[cli.md](../../docs/spec/cli.md)'s "The dry run" and
[script-spec.md](../../docs/spec/script-spec.md)'s two checkable
tiers.)*

**This shelf stands empty again**, the day it refilled — both
halves of the cut delivered on the day they were pledged, which is
what a sprint-sized pledge is supposed to look like. The project
owes no unbuilt feature; [USE-CASES.md](USE-CASES.md) still owes
**U7**, which neither half met and neither claimed to. What fills
this file next arrives the way F24 and F25 did: by someone deciding
to build something argued in [proposed/](../proposed/).

**It refilled on 2026-07-29** (owner) with **F26–F28**, exactly
that way — the first fill whose features arrived from outside, a
consuming project's proposal admitted the same day. Each was
tested against D42's bound and pledged whole. The pledge round
did what the entries' own admissions required: **U22** was drafted
([proposed/USE-CASES.md](../proposed/USE-CASES.md)) as the case
F27's entry said must exist first, and **F14 was weighed beside
F26** as that entry directs and stays proposed — the surfaces are
separable (an opt-in outcome channel does not reshape the row
return), and F14's own decide-first, whether full capture is
Reliquary's at all, is unsettled, which is exactly the
pledging-outruns-the-design flaw the reference rule names. F28
cites U22 through F27's hatch clause, F27 being pledged in the
same act, so the reference runs sideways.

## F26 — `exec` reports whether the command failed

> **Entered 2026-07-29** from a consuming project's proposal
> (owner: admitted as a proposal). Demanded by **U14** in force —
> the caller "runs work, reads results back", and for a *setup*
> command the result **is** whether it worked — with **P11**'s
> reasoning beside it, on F14's exact footing: a channel that
> cannot say "it failed" is a limit that does not name itself at
> the point it bites. F14 touches the same return surface from the
> other side (the output's head, this the outcome), so the two
> should be weighed together at pledge.
>
> **Pledged 2026-07-29** (owner). F14 was weighed as directed and
> stays proposed: the surfaces are separable, and its own
> decide-first is unsettled. The error-text refusal
> recommendation below travels unresolved to delivery.
>
> **The spelling is settled** (owner, 2026-07-29, in U22's
> flush-out round): a parameter — `check=True` on the `exec`
> twin, `--check` at the CLI — with a command that signalled
> failure raising `RunFailure` naming the command (exit `4`) and
> the row return unchanged. U22's step 8 is the worked spelling.

`exec` returns the visible screen as rows and deliberately reads no
meaning into it (P18, G2). That honesty leaves a caller running a
setup command — one whose output is nothing and whose success is
everything — with no channel at all: success and failure both come
back as rows. The ask: an **opt-in** way for `exec` to report
whether the command it ran signalled failure.

The mechanism stays on Reliquary's side of its own doctrine. After
the command, the interaction layer probes with `IF ERRORLEVEL 1`
and a sentinel echo of its own composing, and reads its own
sentinel back — `IF ERRORLEVEL` being portable across DOS shells
in a way `%ERRORLEVEL%` expansion is not. That reads no meaning
into the guest's output: the probe's answer is text Reliquary
itself composed, exactly as prompt detection already reads the
screen for Reliquary's own protocol and as the readiness idiom has
a script set a variable and read it back. It belongs to Reliquary
because the DOS interaction surface is Reliquary's — the same
reasoning that moved drive-letter placement out of consumers (P17).

Landing rule: **P6**. `exec` is a CLI command and an API function
today, so the opt-in lands on both twins in one change.

DECIDE FIRST:

- **The spelling** — a parameter on `exec` or a sibling verb. The
  source proposal offered either; one concept should get one
  spelling (the G6 instinct, though `exec` is CLI/API surface
  rather than script language). *Settled — a parameter,
  `check=True` / `--check`; see the pledge annotation above.*
- **The error-text supplement — and this entry argues a refusal.**
  `COMMAND.COM` leaves ERRORLEVEL unchanged on `Bad command or
  file name`, so a mistyped command escapes the probe. The
  recommendation is to decline recognizing the shell's own error
  text and to record the probe's limit honestly in the spec (P11)
  instead: error-text recognition is curating guest output
  spellings — a localized DOS prints localized messages, so the
  set is unbounded — and matching them is P10-shaped guessing
  about what the guest meant. A mistyped command is an authoring
  error, caught in authoring; the probe's honest scope is commands
  that ran and signalled failure.

Work:

1. Land `check=True` / `--check` on both twins in one change
   (P6), the spelling settled above.
2. The probe's honest scope recorded in the normative spec,
   error-text supplement settled per the decide-first (P11).

## F27 — A `devices` axis for the machine blueprint

> **Entered 2026-07-29** from a consuming project's proposal
> (owner: admitted as a proposal). **No use case names the guest's
> hardware as the subject**, said plainly (the F12 posture): the
> nearest are **U14**, whose consumers are exactly who this
> serves, and **U4**/**U16**'s precisely-defined machine, and
> neither reaches a machine whose *device model* is the point — a
> driver under test drives one particular device, and the case
> such a developer would state (the device's presence is the
> machine's whole point, refused by name up front where no host
> can provide it) is drafted nowhere. Pledging this means drafting
> that case first (P8). What *shapes* it is already on the record:
> the standing constraint (root ARCHITECTURE.md) that new devices
> "extend the same convention — a new medium name — not appear as
> opaque raw backend arguments", F5's blueprint-device-growth
> bullet (agnostic vocabulary, capability-checked per backend),
> and **P11**.
>
> **Pledged 2026-07-29** (owner). The case this entry said must be
> drafted first now is: **U22**
> ([proposed/USE-CASES.md](../proposed/USE-CASES.md)), which this
> feature cites as its demand.

What a driver-testing caller means by "the engine must be QEMU" is
not an engine preference — it is "**this machine must contain this
device**", and the blueprint vocabulary cannot say that today.
`Requirements` is closed over `control_planes` / `media` /
`controllers` / `materialize`, so a device need can never reach
`assign()` and can never influence which backend is chosen. The
nearest live mechanism records the wrong fact and over-constrains:
a `backend` pin binds and fails closed by name — correctly — but
forecloses every other backend that could genuinely provide the
device (VirtualBox offers virtio-net), and the device flags it
implies belong in `backend-settings`, which is the wrong home for
a portable need (and today does nothing — F28).

The ask: a `devices` machine field — a **closed, curated
vocabulary**, grown one name at a time as demand arrives, exactly
as the standing constraint already grows media kinds and
controllers — with `devices` tuples on `Requirements` and
`Capabilities`, judged in `unmet()` like every other axis, at
assignment, against the whole blueprint. Each adapter reports what
it can provide and renders what it reported (QEMU: `-device
virtio-rng-pci`); a stub reporting the empty tuple is honest and
free. A machine declaring a device nothing available provides
fails closed at preflight naming the device (P11) — an up-front,
legible refusal — and the declaration keeps the blueprint portable
where a pin cannot: it names the need, and assignment finds any
backend that meets it.

**Not adopted from the source proposal**: its reading of
`Capabilities.vvfat` as "the failure mode to avoid". `vvfat` is
judged where the drive is rendered because a directory-source
media's realized shape is only knowable after resolution — the
late judgment is deliberate, not a defect. Devices are declared
facts, so assignment-time judgment is simply the right home for
*this* axis, not a correction to that one.

DECIDE FIRST:

- **What the names name.** `virtio-rng` is the first name demand
  has arrived for (virtio-console and virtio-net are visible
  behind it) — but is the curated name the device model or an
  abstract class (`rng`)? For driver testing the precise model is
  the point — the driver binds to *that* device — which argues for
  the model name; the standing constraint's "agnostic vocabulary"
  pulls the other way. virtio is itself a cross-hypervisor
  standard, which may dissolve the tension for the first names.
- Whether a declared device the *guest* lacks a driver for is any
  of Reliquary's business. It is not — the backend half is
  checked, the driver half stays the caller's — but the controller
  rule already states that split and this field should state it
  the same way (U22's closing sentence states it as the case).

Work:

1. Settle what the names name (the decide-first above).
2. The `devices` blueprint field: parse, validate against the
   closed vocabulary, schema, machine state.
3. `devices` tuples on `Requirements` / `Capabilities`, judged in
   `unmet()` at assignment against the whole blueprint; a device
   nothing available provides fails closed naming it (P11).
4. QEMU renders what it reported; the stubs report the empty
   tuple.
5. Docs land coherently: blueprint model and reference, the
   standing constraint's citation, tests over the fake adapter.

## F28 — Adapters honor `backend-settings`

> **Entered 2026-07-29** from a consuming project's proposal
> (owner: admitted as a proposal). **No use case demands it**,
> said plainly; what demands it is coherence. The blueprint
> documents sanction the field as *the* escape hatch (the guide's
> "one deliberate exception", the cookbook's worked recipe, the
> http-serve spec's preflight reasoning about
> `backend-settings.qemu.args`), an open question at the front of
> [DECISIONS.md](../DECISIONS.md) already presumes its top-level
> scope live, and **F27's closed vocabulary needs exactly this
> hatch** for whatever it deliberately does not name — without a
> working hatch, a caller needing an unnamed device has no path
> through Reliquary at all until the vocabulary grows a name.
>
> **Pledged 2026-07-29** (owner), citing **U22** through F27's
> hatch clause — a device the vocabulary does not yet name is
> reachable through the backend's own settings section — beside
> the coherence argument above. F27 is pledged in the same act,
> so the reference runs sideways.

The field parses, validates its backend names, and persists into
machine state verbatim — **and no adapter reads its section**. The
QEMU launch renders memory, drives, and boot order, nothing else,
and settings do not narrow assignment. The normative spec is
honest about this — blueprint-model.md names both further rules
"designed and unbuilt … carried through verbatim and none is
validated yet" — but the descriptive reference asserts both as
live ("each backend adapter validates its section and rejects
overlap"; settings "narrow the assignment walk"), which is a
descriptive document outrunning its norm: that class of bug is
the reference's, whatever else is decided here.

The ask, with a strong preference over re-scoping the documents —
implement what is already designed:

1. **QEMU honors its section.** The documented keys (`machine`,
   `args`) render into the launch; the adapter defines and
   validates its key set and rejects overlap with what Reliquary
   owns through first-class fields (memory, drives, boot order,
   CPU count, identity). The overlap rule needs no second backend
   to be real for QEMU's own section.
2. **Sections narrow assignment**, as designed: where no `backend`
   is declared, settings for exactly one backend narrow the walk
   to it.

Re-scoping instead would not merely trim prose: it would delete
the one documented in-Reliquary path for backend-specific need the
portable vocabulary does not yet carry — and the standing
constraint's demand that devices arrive as first-class vocabulary
is tolerable only while the hatch exists for what has not arrived
yet. The hatch must not become the standing *home* of device
declarations; that is the constraint's whole point, and the
pressure runs the other way by design: a settings key in repeated
use across blueprints is demand arriving for a curated F27 name.

Work:

1. The entry's own two numbered items, in order — QEMU's section
   honored (keys validated, overlap refused), then settings
   narrowing assignment where no `backend` is declared.
2. The descriptive reference realigned to the delivered truth in
   the same change — its assertions stop outrunning the norm.
