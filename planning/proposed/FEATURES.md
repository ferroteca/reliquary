<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Proposed features

Large unbuilt capabilities — each a milestone's worth of work,
**design settled and intact**, waiting on the demand that schedules
it. Nothing here is worked ([README.md](../README.md)); the move to
[pledged/FEATURES.md](../pledged/FEATURES.md) is the pledge,
and the commit that makes it is the record.

F2–F6 left the numbered arc for the same reason (D33, owner,
2026-07-23): **no in-force or pledged use case demands it**. The
numbered arc ran 1 through 9 and ended there, carrying text-mode
DOS on QEMU end to end; generalizing beyond that one vertical is
what waits here. Each names the use case that would schedule it,
and each of those was a draft when this paragraph was written.

**F2 left on 2026-07-28**, the first of the five to go, pledged
together with its demand U7 — which is the shape the paragraph
above describes working — and **delivered the same day**, so its
number retires unreused ([pledged/FEATURES.md](../pledged/FEATURES.md)
carries the record). It settles what a pledged demand does and
does not do: F3 and F5 cite U7 as well and both stay here, because
a pledged use case makes a feature *pledgeable* and pledges
nothing itself. Each feature is still moved by its own decision.
And a delivered seam is not the capability the seam serves: the
adapter API exists now, U7 stays pledged, and F3 below is what
would meet it.

**F7–F10 never were on the arc.** They are governance and tooling
proposals moved out of TASKS.md's legacy Proposed section (D43), and
they cite **principles** rather than use cases, which drive work
just as well. What they share with the rest is the only thing that
matters here: argued, unpledged, and not worked from.

**F11–F16 arrived from outside** (owner, 2026-07-27): one consuming
project's proposal, admitted to this document and nothing further —
entry grants a live argument, exactly as it does for anything else
here. They differ from everything above in where the demand comes
from: an embedding caller reporting what the surface costs it,
rather than the project's own arc. The consumer is not named, per
the doctrine that the machine layer stays ignorant of who builds on
it; its arguments are kept, generalized to "a caller". Several cite
no use case at all, which each entry says plainly rather than
papering over. The source proposal offered its own suggested
delivery order; that order has no standing here (D42 — `proposed/`
is not a queue), and what survives of it is the dependency each
entry records in its own text.

**F11 was the first of the six to go, on 2026-07-29** — and it went
by an exit no entry here had used before. It was not pledged: it
was **cut**, failing D42's one-sprint bound, so its number retired
unreused and F24 and F25 carry the halves to
[pledged/FEATURES.md](../pledged/FEATURES.md). The lesson is about
this file rather than about that feature. An entry here is sized by
nobody — "size is no bar to sitting here" is the rule four
paragraphs down — so what one costs is discovered at the pledge, by
reading the shipped surface it would change. F11 read as a rename
with a new command beside it; the reading found a flag it assumed
into existence, an output discipline that inverts, and a normative
mode the rename would have deleted in silence (D79). Arriving from
outside made none of that worse: the entry was argued in good faith
and the gaps are the ordinary ones.

**F18–F20 arrived from [TASKS.md](../TASKS.md)** (owner,
2026-07-27), by the gate audit of that day. Each adds a CLI command
or changes a CLI spelling — which is **no bar to being a task**
(D45; the housekeeping boundary that excludes a surface change
is housekeeping's alone, and F16 below is where that misreading
started). What holds all three here is the same thing: each
carries an **open shape question** in its own text, and an argument
still to finish is what `proposed/` is for. F17 made the same
journey to `pledged/`, on its size rather than its surface.

**F1 came back from [pledged/FEATURES.md](../pledged/FEATURES.md)**
(owner, 2026-07-27; D61) — the first withdrawal, and the reverse of
every arrival above. It was never pledged by anyone's decision: the
2026-07-26 restructure housed it there because feature-bound work
items had nowhere else to live, and D44's rename then changed what
that shelf claims without re-testing its occupants. **U6**, the use
case it delivers, and **U2** came back to
[USE-CASES.md](USE-CASES.md) in the same round.

**F26–F28 arrived from outside** (owner, 2026-07-29): a consuming
project's proposal — the second arrival by that door — admitted to
this document and nothing further, exactly as F11–F16 were: entry
grants a live argument. The consumer is not named, per the doctrine
that the machine layer stays ignorant of who builds on it; its
arguments are kept, generalized to "a caller", and the use they
serve — testing a device driver inside a guest — is described as a
use. Every code claim the source proposal made was re-verified
against the tip on admission and held. It asked no sequencing and
no date, so there is no order to record; what one entry needs of
another sits in that entry's own text (F28 is F27's escape hatch).
One sub-item arrives with an argued refusal recommended rather than
adopted (F26's error-text supplement), and one reading was
corrected rather than kept (F27 on `vvfat`) — both recorded in the
entries themselves. **All three were pledged the same day**
(owner, 2026-07-29) and moved to
[pledged/FEATURES.md](../pledged/FEATURES.md), **U22** drafted in
the same act ([USE-CASES.md](USE-CASES.md)) as the case F27's
admission required; F14, which F26's entry directs be weighed at
that pledge, was — and stays here, its own decide-first
unsettled.

A feature that is pledged but not yet built moves to
[pledged/FEATURES.md](../pledged/FEATURES.md) and carries its work
breakdown with it. Small work that is not a feature at all goes
straight to [TASKS.md](../TASKS.md).

Each feature carries an **F-number** (D42; the rules are in
[README.md](../README.md)). **Size is no bar to sitting here** — the
sprint bound bites at pledge, so every entry below is many
sprints of work, and the "milestone's worth of work" above describes
what these entries *are* rather than a size any may be pledged at.
Cutting one into implementable pieces is part of pledging it.

## F1 — The U6 authoring recorder

> **Withdrawn from [pledged/FEATURES.md](../pledged/FEATURES.md)**
> (owner, 2026-07-27; D61), with **U6** — the use case it delivers
> — in the same round. What is withdrawn is the promise, not the
> design, which stands as written; the preamble above records how
> the pledge arrived without anyone making it.
>
> Serves **U6** ([USE-CASES.md](USE-CASES.md)); design in
> [design/recorder.md](design/recorder.md). The one capability the
> numbered arc deliberately did not deliver — it ended at milestone
> 9 with the recorder unbuilt.

**THE WHOLE OF IT RIDES VNC**, which is the ground the withdrawal
was decided on. Recording requires Reliquary to *be* the console:
input typed into a backend's own display window never passes
through Reliquary and cannot be followed, so the Reliquary-owned
viewer over the `vnc` control plane is the recording prerequisite
on **every** backend, QEMU included
([design/recorder.md](design/recorder.md)). That plane arrives with
the GUI era (**F5**). This entry's former sequencing note claimed a
text-mode half depending on nothing unpledged, and **that was wrong
against its own design** — what text mode avoids is the landmark
and click work, which is F5's GUI asset spec and pointer input,
never the viewer.

Decide first:

- **The cut.** The deliverables below are at least seven features
  on the sprint this project runs, and D42 requires the split at
  pledge — retiring F1's number for a fresh one per piece. The
  viewer is the natural first cut line; the text-mode recorder is
  what follows it, needing no new language surface.

Deliverables:

1. Reliquary-owned console viewer over the `vnc` control plane —
   the recording prerequisite, backend display-window input being
   invisible to Reliquary.
2. The text-mode recorder: waits from VGA scrapes, type/press
   actions, generated-comment uncertainty flags. No new language
   surface.
3. Runner run-to-point / breakpoint / human-takeover machinery,
   which is also the failure report's "take over from here"
   suggested next command.
4. Round-trip: fragment emission anchored by playback position,
   with opt-in surgical apply at the anchor — never regenerating,
   never text-merging.
5. The landmark catalog shape, already decided (DECISIONS.md, the
   wrinkle round; [design/landmarks.md](design/landmarks.md)) —
   implementation rides the asset spec work.
6. Run-events handover kinds (script/human control passing), so a
   capture session is one run record with mixed drivers. Milestone
   9 reserved these in the spec and no constant exists in the
   implementation.
7. CLI `record` command family and API twins, landing together
   under parity.

## F3 — Second backend: VirtualBox

> **Dropped from the numbered arc to the backlog** (owner,
> 2026-07-23): the former Milestone 11, not yet scheduled. It left
> on the same ground as the seam extraction — no use case demanded
> the pillar — and **that ground is gone**: U7 is its demand too,
> and U7 was pledged on 2026-07-28 along with the extraction
> itself (**F2**, delivered the same day; its number is retired).
> The seam F3 was waiting behind is built, and its stub adapter is
> already in the tree claiming nothing. What holds F3 here is no
> longer a missing argument or a missing seam but an unmade
> decision: a pledged demand is necessary for a feature and
> sufficient for none, and this one is pledged by its own move.

The first non-QEMU adapter end to end, proving the adapter API
against a genuinely different hypervisor. VirtualBox is the
candidate: `VBoxManage` covers lifecycle, keyboard scancodes,
screenshots, and serial redirection — the closest match to the
control plane set scripts already rely on.

Deliverables:

1. Lifecycle through `VBoxManage`, with machine files kept inside
   `cache/machines/<id>/` and VDI/differencing materialization
   of the drive triad. **VDI is the committed format for this
   backend** — the field reference's backend/format table said so
   before any of it existed, and until 2026-07-27 the code
   contradicted it by materializing qcow2 for a blueprint that
   declared `virtualbox`. `create-machine` now refuses an unwired
   backend outright (P11), so the table is intent recorded here
   rather than a promise the shipped code breaks.
2. The agentless display control plane: `controlvm
   keyboardputscancode` input and `screenshotpng` capture, with
   pixel-level text recognition for fixed-font text modes behind
   the same control plane interface.
3. VirtualBox in autodiscovery and the priority list;
   `recreate-machine`
   as the sanctioned backend move, drives regenerating in native
   formats.

Done when: the FreeDOS install script runs unmodified on both
backends from the same blueprint (minus a pinned backend field).

## F4 — Guest agent communication

> **Dropped from the numbered arc to the backlog** (owner,
> 2026-07-23): the former Milestone 12 — numbered 13 until the
> same-day renumber that followed machine mobility's demotion —
> not yet scheduled. No use case demands it: the first-class
> demands (granular results, selective re-run) are met by
> milestones 8–9, and the guest-agent plane was only ever a
> *preference* stated by U3, not a requirement — U3 has since
> retired (D51) and **U14, which supersedes it, states no such
> preference at all**, so the argument is stronger than when it
> was written. What carries the preference now is **P3**, a
> principle rather than a demand. Its loop runs
> agentlessly on QEMU/DOS today. P3 governs how a native agent
> is consumed if this lands; it does not demand that it land.

Native guest agents as control planes, per
[design/guest-communication.md](../design/guest-communication.md):
Reliquary consumes the agents guests already have
— QGA first — and never builds its own (ARCHITECTURE.md
P3, the control-plane arc). This milestone must not weaken the
permanent agentless DOS path; guests without a native agent
(DOS-era systems included) remain agentless, and where a guest
holds both planes the same suites validate agentless and
guest-agent control planes with equivalent results.

Decide first:

- The exact initial `guest-exec` subset, including argument and
  environment support, capture modes, output limits, and
  timeouts.
- Which bounded `guest-file-*` operations follow execution,
  including file consistency and atomic replacement semantics.
- Whether a separate plain serial-console control plane earns
  its keep alongside the native guest agents and the agentless
  planes.

Deliverables:

1. The host QGA client module: framing, `guest-sync-delimited`,
   `guest-ping`/`guest-info`, `guest-exec`/`guest-exec-status` —
   depending on QEMU's published guest-agent protocol, never on
   one particular guest implementation.
2. The extended `GuestExec` interface: request and result types
   covering deadlines, completion, output, and exit status,
   without exposing transport objects.
3. The configured readiness waterfall with conservative fallback:
   selection before first dispatch only, ambiguous failures never
   retried on another control plane.

Done when: a guest command runs through QGA on QEMU with
truthful capability reporting, and the agentless suite still
passes byte-for-byte.

## F5 — The GUI era: VNC, GUI scripting, and the last backends

> **Dropped from the numbered arc to the backlog** (owner,
> 2026-07-23): the former Milestone 13, not yet scheduled —
> sequenced alongside the Horizon items below when its turn comes.
>
> **This entry cites no demand, and is the only feature that
> doesn't** — confirmed by the demand-citation sweep of
> 2026-07-27, which found it the one live violation across 22
> features and 5 design documents. It is the **D33 pattern in its
> purest form**: a settled design outrunning the argument for it.
> The traceability rule's remedy is *find the demand or delete the
> work*, and neither is an audit's to choose — it is an
> adjudication, left open deliberately rather than papered over
> with a citation written to fit. Two things point at demand
> without being it: **U5**'s customized-Windows scenario waits on
> this feature, and **U6**'s recorder (**F1**) needs the console
> viewer that rides the VNC plane — the whole of F1 does, not the
> GUI half only (D61). Both now sit in `proposed/` alongside this
> entry — U5 as of D64 (2026-07-28), which cut its delivered half
> away as U21 and left exactly the half that waits here — so
> neither reference runs up the lifecycle, the same resolution D61
> reached for F1. Whoever adjudicates starts there.
>
> **The gap narrowed on 2026-07-28 and did not close** (D65). This
> entry is two features wearing one number, and U7's pledge reaches
> only one of them: U7 names Hyper-V outright — "a Windows laptop
> with Hyper-V already enabled" — so the *last two adapters* below
> now stand on pledged demand like F2 and F3 do. **GUI automation
> itself still cites nothing.** The VNC plane, the landmark asset
> spec, and pointer input answer to no use case in force or
> pledged, and U7 does not reach them: materializing on the host's
> hypervisor says nothing about driving a graphical installer. The
> honest reading is that the split D42 would force at pledge is
> also where the demand divides, which is a finding for whoever
> adjudicates rather than the adjudication itself.
>
> **The Hyper-V wire is not missing, only different** (prior-art
> research, 2026-07-28; not adjudicated). The body below drew the
> capability-not-one-wire conclusion from an absence. The
> conclusion holds and sharpens; the premise does not. Hyper-V's
> VM console is reachable over RDP to the *host* on port 2179,
> the VM's GUID carried as an `MS-RDPEPS` preconnection blob —
> host-side, no RDP server in the guest, and serving the console
> before any OS is installed. So GUI automation on Hyper-V is a
> **second display carrier** rather than a hole, which is a
> stronger illustration of the doctrine than an absence was: a
> capability satisfied two ways is the case the seam exists to
> serve. The cost is the open part: RFB hands a client a
> framebuffer, where RDP output is bitmap updates, drawing
> orders, and codecs, so the realistic path is a vendored native
> stack (FreeRDP is Apache-2.0 and implements the blob; no usable
> Python binding exists, and it ships no official Windows
> binary). **This changes no demand** — a newly available wire is
> not a use case, and GUI automation still cites nothing. A
> finding on the same terms as the note above.

The arc's endpoint: GUI installer automation, carried by the
VNC/RFB control plane where backends provide it — QEMU natively,
VirtualBox with the extension pack, VMware Workstation — and the
two remaining adapters: VMware Workstation, then Hyper-V,
deliberately last. Hyper-V has no VNC — a capability failure,
never an emulation — which is what makes it the proof that GUI
automation rides capabilities and not one wire: its console
answers on a different carrier entirely (the note above), so the
capability has to be reachable by more than one.

Decide first:

- The GUI asset spec: the `.rlql` JSON schema, the similarity
  metric, and landmark-block placement within a script (the
  asset shape itself is settled —
  [design/landmarks.md](design/landmarks.md)).
- Pointer input end to end: the machine-blueprint
  pointing-device field, the control-plane input capability, and
  the script verbs — match-and-click with the click point in the
  asset; click owns its search as an observation-bearing action
  and needs its timing-matrix row. The input seam follows the
  two-layer event model: three portable primitives — pointer
  move (x, y), button press/release, key press/release — with
  clicks, drags, chords, and paced typing composed above them,
  and event pacing owned by the control plane. The primitives
  are exactly RFB's PointerEvent/KeyEvent, so the VNC control
  plane implements them with no translation, and
  QMP/VBoxManage/WMI input paths reduce to the same three.
  Synchronization concepts to adopt with them: act-then-confirm
  (an input step optionally asserting the screen changed) and
  screen-stillness waits. Also open: a host-side
  landmark-cropping convenience (a CLI subcommand, never a
  service). Era note: DOS/9x-era setup GUIs are fixed-mode,
  fixed-font, animation-free — asset churn should be far below
  os-autoinst needle churn — and NT-era setup is largely keyboard-drivable, so
  keyboard-first remains the preferred path where it works.
  A future os-autoinst bridge belongs as an external-runner
  adapter or export target — generate an os-autoinst test
  distribution and invoke isotovideo out of process — not as
  Reliquary's native machine engine.
  Throughout, os-autoinst is a **concept reference only** — its
  designs are studied and reimplemented, never its code (see
  AGENTS.md prior art for the boundary, which is doctrine rather
  than merely licensing).
- Blueprint device growth: firmware/boot semantics (BIOS vs
  UEFI) for post-DOS platforms, and when network, display
  adapter, audio, and USB become first-class blueprint fields
  (each following the drives pattern: agnostic vocabulary,
  capability-checked per backend); per-platform controller
  defaults beyond `ide`; whether slot ranges widen for
  multi-device controllers (additive change); and how Hyper-V
  generations surface (a backend setting vs. inferred from
  declared capabilities).
  **A second controller type unfixes every disk letter**, which
  is the one constraint this bullet carries rather than merely
  lists. Slot order is authoritative only within a type; across
  types the guest's firmware decides how the controllers
  themselves enumerate, so not even the first disk is a declared
  fact and P17 requires refusing the address instead of guessing.
  `platform_dos.drive_letters` already refuses across types, and
  that guard is asserted by test though no machine can reach it
  today — so wiring a second type does not silently start
  answering a question there is no fact for. What it *does* need
  is the reverse: a way to say which disk is first when the facts
  do determine it, or DOS machines lose in-band file exchange the
  moment they gain a controller type. That is the design this
  bullet owes, and it was left behind in the field reference as
  prose until 2026-07-27.
- The Hyper-V agentless screen strategy: whether WMI
  thumbnail/keyboard automation is good enough for installer
  scripting, or Hyper-V machines require the serial/agent
  control planes from day one.

Deliverables:

1. The VNC control plane: per-backend endpoint configuration
   contributed to launch config, endpoint artifacts under the
   machine cache, a readiness probe, and an RFB client —
   framebuffer capture, key events, pointer events — behind the
   same input and screen capabilities as agentless display,
   reusing the pixel-level text recognition built for the
   VirtualBox display plane (F3 above).
   `control-planes: ["vnc"]` honored end to end, with a
   capability error naming Hyper-V where it cannot exist.
2. The three portable input primitives exposed at the
   control-plane seam, with pacing control-plane-owned.
3. Landmarks implemented per
   [design/landmarks.md](design/landmarks.md): the `.rlql`
   catalog form, `@landmark`
   matching with fuzzy/ignore modifier regions, the cursor
   normalization contract, and the match-and-click verbs
   composed on the primitives.
4. Win9x/WinNT platform workflows: GUI installer scripting for
   the setup GUIs text scraping cannot reach, keyboard-first
   where NT-era setup allows it.
5. The VMware Workstation adapter.
6. The Hyper-V adapter, last, on its decided screen strategy.

Done when: the FreeDOS install script runs unmodified on QEMU
with the VNC control plane selected in place of agentless
display, pixel-recognition text observation matching the
VGA-scraping results on the same screens; and a GUI-era install
script drives a setup end to end through landmarks on QEMU over
VNC and on Hyper-V through its decided screen strategy.

## F6 — Asynchronous runs

> **Deferred to the backlog** (owner, 2026-07-24, D35; scope
> extended D36): the asynchronous-run pillar leaves the numbered
> arc — milestone 9 delivers the run, and its output, without it.
> No in-force or pledged use case demands it: the feedback split
> (P5) is satisfied by the run's own driver watching it live, and
> detaching a run or following it from a process that did not
> start it is a separable capability no case writes down. Its
> demand is the U19 draft
> ([proposed/USE-CASES.md](USE-CASES.md),
> "start a long run and follow it from elsewhere"); pledging
> U19 is scheduling this work back onto the arc, the citing item
> the record.
>
> **Persistence lives here (D36).** A run another process can
> follow must be written down, so the whole record substrate
> belongs to this pillar and returns with it: the
> `cache/machines/<id>/runs/<n>/` archive with machine-scoped
> monotonic numbering, the persisted `run-events.jsonl` and
> `transcript.txt`, retention and the `list-runs` / `run status`
> / `run delete` verbs, the crashed-run rule (writer identity +
> cross-process liveness), and interaction runs (`begin-run` /
> `end-run`, the primitive-loop bracket and U6's recorder seam).
> Milestone 9 stores nothing; this is where storage comes back.
> The design below and that record model are settled and stand as
> written.

**Sync is async plus attach.** A foreground `run-script` run is
defined as: start the run, immediately attach the live renderer.
One semantic, one code path — and a run started in one terminal
can be observed from another. Ctrl-C on a foreground run cancels
the run; Ctrl-C on a later reattach merely stops tailing. (Until
this lands, milestone 9's foreground run is the simpler shape:
the runner lives in the invoking process and the renderer reads
the stream that process writes, with no cross-process attach.)

**Detach hands off at the machine boundary.** `run-script
--detach` completes parsing, binding, and static and capability
preflight in the foreground (G3 — those failures belong to the
invoker's exit code, never buried in a record), then spawns the
runner and prints the run id. The detached runner is an owned
child exactly as QEMU is: the run record carries writer identity
(pid plus start time), liveness checks verify identity before
any command targets the run, and stale records fail closed — the
vm.json doctrine applied to the runner. This is what makes a
record's missing terminal event a detectable *crashed* run
rather than merely an incomplete one.

**Cancel from another terminal.** `run cancel` requests a stop;
the runner ends at the next event boundary (input deliveries are
atomic, host transfers abort — the execution model's
severability), writes a `cancelled` terminal event, and leaves
the machine as-is per the no-implicit-teardown rule;
`--stop-machine` opts into the visible hard power-off (the flag
mirrors `cancel(stop_machine=)` — flags mirror parameters even
in the run family; owner, 2026-07-21). The `cancelled` outcome
and its exit code (`5`) already exist in milestone 9 for
foreground Ctrl-C; what defers is cancelling a run the current
process did not start.

**The run family's followers.** `run tail` renders a live run's
stream per the progress vocabulary (pretty on a tty, plain and
jsonl for programs); `run wait`'s exit code mirrors the run's
outcome, so unbound languages get results by waiting. Both take
the run number as an ordinary positional argument, defaulting to
the machine's latest run, with the machine chosen by the
ordinary `--machine` / `--blueprint` selectors.

**Two presentations — the async handle.** The embedding API's
twin of `--detach` is `start_script()`, returning a run handle —
`status()`, `events(follow=)` as a blocking iterator,
`wait(timeout=)`, `cancel(stop_machine=)`;
`attach_run(machine=, blueprint=, run=None)` reopens a handle
from a fresh process, the run number defaulting to the machine's
latest exactly as the CLI `run` operations do. The handle is
pull-only: no callbacks, nothing a common binding language
cannot express directly. `wait(timeout=)` completes exactly as
the blocking form — same result, same raises — and expiry raises
outside the error taxonomy (Python: the builtin `TimeoutError`):
nothing failed, the handle stays valid, the call repeats (owner,
2026-07-21). A handle is a follower, never the owner: dropping
one never affects its operation — GC timing carries no semantics
in any binding, and `cancel()` is the only cancellation. A
caller wanting concurrency without any of this still runs the
blocking form on its own thread — computation stays on the
caller's side of the seam.

**Fetch handle.** `start_fetch()` (the same parameters as
`fetch_media()`) returns a pull-only fetch handle — `status()`,
`events(follow=)`, `wait(timeout=)`, `cancel()` (aborts at an
event boundary; the partial download is deleted, no pre-existing
file touched). There is no attach-by-id and no CLI command —
`start_fetch` is the one async starter without one (owner,
2026-07-21): an ephemeral stream is process-local, reattachment
is what run records provide, and a CLI driver backgrounds
`fetch-media` itself, the process being the handle. The handle
form is noninteractive by construction and rejects
`on_mismatch="prompt"` — a background fetch can never hang on a
hidden prompt.

## F7 — Audit design documents against pledged demand

> **Moved here from TASKS.md's legacy Proposed section** (owner,
> 2026-07-26): argued but never approved, and a proposal belongs under
> `proposed/`. Demanded by **P8** (surface and principle changes are
> vetted): the audit checks that a design exists only where demand
> does. No use case asks for it.

**Audit design documents against pledged demand.** Raised
unprompted during the 2026-07-24 traceability audit rather than
requested — a suggestion, not a request — so it waits here.

The findings that motivate it, folded in from
[TASKS.md](../TASKS.md) by the 2026-07-27 gate audit, which found
this item pledged there and proposed here at once and kept the
proposal:

- Two documents cite no U/P/G at all:
  [backend-adapter.md](../design/backend-adapter.md) (230
  lines) and
  [blueprint-cookbook.md](../../docs/blueprint-cookbook.md) (440
  lines, examples — arguably exempt). *The first was fixed on
  2026-07-28 by its pillar being pledged: it named U7 and F2 and
  travelled to `pledged/design/` with them, then back to
  `design/` the same day when F2 delivered and left no feature for
  it to sit with. One finding left.*
- Beyond citation, three designs exist for pillars whose demand was
  never pledged — `backend-adapter.md`,
  [guest-communication.md](../design/guest-communication.md) and
  [design/landmarks.md](design/landmarks.md) — all demoted by D33
  *for lack of use-case backing* after their designs were written.
  *Backend-adapter left this list on 2026-07-28, by the remedy the
  traceability rule names: the demand was found and pledged (U7),
  not the work deleted. Two left.*
  This is the retrospective pass over what predates the current
  shelving, where a design sits with the feature it serves and is
  swept with it.

## F8 — The planning traceability linter

> **Moved here from TASKS.md's legacy Proposed section** (owner,
> 2026-07-26): argued but never approved, and a proposal belongs under
> `proposed/`. Demanded by **P8** and **P23** — it enforces
> mechanically what those principles assert, rather than leaving them
> to whoever happens to grep. Pairs with **F9**, its mirror. No use
> case asks for it.

**A traceability linter over the planning documents.** Check the
invariants the governance rules already assert, in the required
checks, so they are enforced rather than remembered.
THE ARGUMENT: the artifacts are versioned files by necessity —
the standing lists claim every entry is true of the code *at
this commit*, which only something travelling in the commit can
assert, and only a diff can review (this is why architecture
decision records converged on markdown-in-repo, and why their
tooling is indexers over files rather than trackers). What files
do not give is **type and query**: nothing enforces that a
decision carries supports or that delivered work cites pledged
demand. Today those are checked by whoever happens to grep,
which is exactly how U9 and U12 went unnoticed through the
milestone that delivered them.
EACH CHECK EARNED ITS PLACE — the 2026-07-24 hand audit found a
real violation of every one:
* every planning section cites a U/P/G demand — *12 of 34 sections
  in the then-current roadmap cited none; re-run by hand
  2026-07-27 over what replaced it, **2 of 27**, and both already
  known ([F5](#f5--the-gui-era-vnc-gui-scripting-and-the-last-backends)
  and `backend-adapter.md`, the latter closed 2026-07-28). The improvement is not
  vigilance but construction — the restructure wrote each entry
  with its demand — which is the argument for a linter rather than
  against one: what construction fixed once, drift returns*;
* every DECISIONS entry carries supports — *22 lack them, and
  D29 sat outside the range the existing task assumed*;
* no *delivered* work cites *unpledged* demand — *U9 and U12*,
  the sharpest defect of the set, and the one a linter would
  have caught the day milestone 9 landed (closed by hand three
  days later, D46 — which is the argument, not a
  counter-argument: three days is what an unaided grep costs);
* every design document's subject has pledged demand — *three
  designs exist for pillars D33 demoted for lack of it*;
* every cited identifier resolves — *U15 is cited 6 times and
  defined nowhere*;
* no entry appears in both a standing list and its proposals doc
  (D23's no-stub rule).
ONE DESIGN POINT IT RAISES. The U15 result is not simply a bug
to fix: most of those citations are legitimate death-record
references, and the lifecycle deliberately leaves **no stub**
behind a retired number (D23). So a checker cannot distinguish a
proper historical citation from a stale one without a
machine-readable register of retired identifiers — which the
no-stub rule currently forbids anywhere obvious. Reconcile the
two before building: either the register lives in DECISIONS.md's
Retired list in a parseable form, or retirement earns the one
stub the rule otherwise refuses.
SCOPE, deliberately narrow: mechanical invariants only. Whether
a use case is *well argued*, whether a principle is *honored by
the code*, whether a design is *good* — none of that is
checkable, and a linter that pretended otherwise would licence
exactly the box-ticking the governance rules exist to prevent.

Raised 2026-07-24 as a suggestion, not a request.

## F9 — The vision-utility audit

> **Moved here from TASKS.md's legacy Proposed section** (owner,
> 2026-07-26): argued but never approved, and a proposal belongs under
> `proposed/`. Demanded by **P8**. The reverse-citation half of
> **F8**: F8 checks every *citation* resolves, this checks every
> *definition* is cited. Shares F8's design and should be sequenced
> with it. No use case asks for it.

**The vision-utility audit — the reverse-citation check.**
The traceability linter above verifies every *cited*
identifier resolves; this is its mirror — every *defined*
vision statement (a use case, principle, or application surface) is
cited or codified *somewhere*, or is surfaced as suspect. A
statement nothing leans on is suspect of no utility:
legislated but never used.
DISCIPLINE — a look-list, not a kill-list. Finding the orphans
is mechanical (a grep over the numbered handles); the verdict
is a judgment the audit must not pre-empt. Each orphan earns
one question — *guardrail or ballast?* — since a ceiling or
closure cited only when pressure arrives is working, not idle.
Principles get more rope than use cases: some cannot be
codified and are legitimately hard to cite.
DELIVERY — greppable by hand today; a monthly CI run is the
richer eventual form. Per P22 (no CI, at this time),
scheduling that run is itself the argued case for turning CI on
when its day comes, not a breach of it.

Raised 2026-07-25 as a suggestion, not a request.

## F10 — Generated API reference

> **Moved here from TASKS.md's legacy Proposed section** (owner,
> 2026-07-26): argued but never approved, and a proposal belongs under
> `proposed/`. Demand uncited. It serves the descriptive layer's
> accuracy; **P21** (dependencies must pull their weight) is the bar
> it has to clear, not the demand for it.

**Generate the API reference from docstrings** (raised
2026-07-26, the spec/descriptive round; owner asked for it to
be filed with its argument). Adopt a documentation generator
(pdoc / mkdocstrings / Sphinx autodoc) to produce
docs/api-reference.md from the binding's docstrings.
SCOPE, and it is the whole point: **plumbing for the
descriptive layer, never a transfer of authority.** A generated
reference is *mechanically* faithful to the binding — the tool
reads the signatures, so reference-disagrees-with-code becomes
impossible by construction, which automates the apology the
reference's banner already makes. The norm of the surface stays
[docs/spec/api.md](../../docs/spec/api.md): code-as-norm would
invert P8 — an unargued code change would *redefine* the
surface rather than violate it — and the project has already
lived the counterexample: the twin-name realignment settled
names in the spec while the code still said
`create_from_blueprint`, and the code was realigned to the doc.
Parity alone cannot replace that direction: it binds shape, not
semantics, and under twin-name identity the CLI's spellings
derive from the API's names, so code-as-norm would put the
guard downstream of the thing guarded. The multi-binding future
sharpens it — two bindings mean two codes, and "the code is the
norm" stops being well-formed; generation then rightly yields
one descriptive reference *per binding*, all answering to the
one spec.
THE BAR TO CLEAR, before adopting even the plumbing: P21 binds
infrastructure — the surface today is small enough that the
hand-written reference is not obviously losing; without CI
(P22) a generated document needs a local required check to
regenerate, or it goes stale in a new way; and
`test_documented_examples.py` executes fenced examples from the
docs, so generated output must preserve that property or exit
that test deliberately.

Raised 2026-07-26 in the spec/descriptive round; **the owner agreed
it needs to win this argument, not that it has** — so unlike F7–F9
this one was asked for, and still waits on its own case.

*(F11 — `--dry-run`, and the end of the check family — was
**cut on pledge** on 2026-07-29, so its number retires unreused
(D42) and a fresh one came to each piece:
[F24](../pledged/FEATURES.md) is `create-machine --dry-run`, the
gap this entry called worth filling first, and
[F25](../pledged/FEATURES.md) is `run-script --dry-run` with the
check family's end. Both are pledged. This is the first use of
D42's cut-on-pledge rule — D65 weighed F2 for the same cut a day
earlier and pledged it whole — and the rulings the cut produced,
including three surface collisions this entry never named, are in
[D79](../DECISIONS.md).)*

## F12 — The `simulator` backend

> **Entered 2026-07-27** from a consuming project's proposal
> (owner: admitted as a proposal). **No use case demands it, and
> saying which one nearly does is the honest way to put it.** The
> nearest is **U14** — its consumers are exactly who this serves —
> but U14 is about driving a real machine; a caller testing *its own
> Reliquary integration* with no hypervisor present is a use nothing
> in the list names, so pledging this means drafting that case
> first (P8). What *shapes* it is settled: **P11** (a simulated
> result reports itself as one) and **P18** (Reliquary attaches no
> meaning to guest output — so it cannot fabricate it either).

**New values in existing plumbing, not a new seam.** The blueprint
schema already carries `backend`; `create` writes it into machine
state, `start` reads it back, and `_backend_dir()` already
quarantines each backend's artifacts. This is an enum value and the
adapter behind it.

**Reliquary simulates what it owns**: phases and transitions, boot,
drive materialization, the control plane, prompt and timing
behaviour, and the failure modes (`PreflightError` when not running,
timeouts, cancellation). All of that it knows exactly. It must **not
simulate guest output** — a component that disclaims understanding
what a command leaves on the screen cannot coherently fabricate it —
so the guest half is **programmable**: the caller supplies the
responder. That constraint is what makes the feature both honest and
cheap: no transcript format, no recording, no guest modelling. A
hook.

WHY A HOOK AND NOT A RECORDING. A caller's command space can be
combinatorial — a per-test invocation of a guest test runner issues a
distinct command per test, and the set changes whenever a test is
renamed — so nothing recorded keeps up. But the caller knows exactly
what its own program prints, which makes answering trivial *for the
caller* and impossible for Reliquary. What this replaces is real: a
consumer's unit tests monkeypatch `start_machine` / `stop_machine` /
`exec` today, which means asserting against guesses about
Reliquary's behaviour and breaking on a rename. A sanctioned hook
puts the real code path under those tests.

**Simulated results are marked in the return value**, and the marking
is not optional: it is P11 at the value level, and it is what lets a
caller refuse simulated results everywhere outside its own tests —
the guard against exactly the accident `--dry-run` refuses to
enable, and it is the reason the two are documented in the same
breath: the validator shipped 2026-07-29 and deliberately fabricates
nothing.

DECIDE FIRST, and it is a genuine obstacle rather than a detail:
**what shape the responder takes under P6 and P7.** A callback is the
natural Python spelling and one of the harder things to express in C
or Java, and a callback has no CLI presentation at all — so either
the hook takes a form an unbound language and the CLI can both drive,
or this backend is knowingly API-only, which is a P6 exception that
has to be argued and not discovered during implementation.

## F13 — Recorded captures, and the `replay` backend

> **Entered 2026-07-27** from a consuming project's proposal
> (owner: admitted as a proposal). **The two tiers below have
> different demand, and only the first is well-grounded.** Tier 1 is
> the project's own verification and cites **P22** — the suite is
> the gate, and this is what would make that gate real for the
> interpretation layer, which today has no honest way to be tested
> at all. Tier 2 is public surface and shares F12's uncited demand.

**The primary customer is Reliquary itself**, which is why tier 1 is
worth building independently of any consumer. The interpretation
layer is heuristic over real-world text: `_PROMPT_RE` deciding what a
DOS prompt looks like, `_command_output()` finding the echo by
scanning back for a row ending with the command and containing `>`,
`screen_text()`, `wait_text`, `cursor_menu_select`, and everything in
`script_timing`. **That class of logic cannot be credibly unit tested
on fabricated input**, because the fabrication encodes the same
assumptions the heuristic does — you write the screen you believe DOS
draws, and the parser passes on your own belief. Only captured
screens carry the weird spacing, the stray CR, the half-drawn menu,
the prompt that arrived mid-scroll.

**Recording is a debugging tool, not a reward for success.** It is
worth having *before* the heuristics are reliable, not after: capture
the boots where prompt detection fails, and each capture becomes a
regression fixture. The pathological captures are the valuable ones,
and they are most abundant now. It also makes inspectable what is
currently only reasoned about — the honest limit that a command
scrolling more than a screenful leaves only its tail (F14).

TWO TIERS, very different in cost:

1. **Recorded captures as internal test fixtures** — a transcript of
   screens and timings replayed through the interpretation layer. No
   public surface, no enum value, no format stability guarantee.
   Cheap, and justified on its own today.
2. **A public `--backend replay`** — callers run whole flows off a
   transcript. Needs a stable format and full lifecycle fidelity;
   defer, and reuse tier 1's format when it arrives. If it happens,
   the CLI pairing teaches itself —

       rlq run-script install --record install.rlqt   # once, real QEMU
       rlq run-script install --backend replay        # thereafter, free

   and the file joins the existing extension family (`.rlqb`,
   `.rlqs`, `.rlql`) as `.rlqt`.

ONE RULE EITHER TIER NEEDS: **an unmatched request fails loudly.** No
recorded response for a command is an error — never an improvised
answer, never empty (P11). Improvising is how a caller ends up
reporting a pass against a transcript that never covered the case.

TWO DISAMBIGUATIONS, both easy to get wrong. **Against F12**: the
names are precise *because* both exist — alone, `simulator` would
overclaim (it models no guest) and `replay` would be too narrow (it
cannot answer an unrecorded command); side by side each denotes what
the other does not. **Against F1**, the authoring recorder: that one
captures a human session to draft a *script*, and its product is
authored text; this captures screens to test the *parser*, and its
product is a fixture. Shared machinery is possible and shared purpose
is not.

## F14 — Full guest-output capture

> **Entered 2026-07-27** from a consuming project's proposal
> (owner: admitted as a proposal). **The strongest demand of the six,
> and the only one that changes what a caller can do today rather
> than how it is tested.** Demanded by **U14** (in force — granular
> results reaching the caller) and **P11**: `exec` returns the
> visible screen, so output longer than a screenful loses its head,
> and loses it *silently*. A capability limit that does not name
> itself at the point it bites is the P11 half, and it is close
> enough to a standing-principle defect to be worth adjudicating on
> that footing rather than this one.

The limit is documented as an honest one — agentless capture leaves
only a long command's tail on the screen — but **honesty about a
limit in prose is not the same as reporting it in the return.** A
caller enumerating work inside the guest (list what a guest program
offers, then drive each item) enumerates short whenever the listing
outruns the screen, and nothing in what it reads back says so. That
is the difference between in-guest enumeration being usable and not.

TWO SEPARABLE DELIVERABLES, and the cheap one may be the whole
answer:

1. **Say so.** A read that could have lost its head reports that it
   might have. This is the P11 minimum, it needs no new transport,
   and it converts a silent wrong answer into a visible one.
2. **Capture the whole of it.** Scrollback beyond the visible screen
   — a control-plane capability question rather than a scraping one,
   since agentless VGA text memory holds exactly one screen. It is
   either paced reading (drive the guest's own pager and capture per
   page) or a different plane; whatever lands, **P2** binds it — the
   agentless path may not come to depend on guest cooperation.

DECIDE FIRST: **whether (2) is Reliquary's at all.** The competing
answer is (1) plus the value channels that already exist — a guest
program writing its long output to a file the caller retrieves in
band, which is `get_file` today and attaches no meaning to the
content (P18). If that is the answer, this entry shrinks to (1) and
stops being a feature; if it is not, the argument for why belongs
here before any work starts.

## F15 — Host-directory attachment as a first-class operation

> **Entered 2026-07-27** from a consuming project's proposal
> (owner: admitted as a proposal). Demanded by **P17**, in force
> since D47, and **P16**, in force since D62 — P16 because the
> capability is reached today only by a caller reproducing
> Reliquary's internal model outside it, and P17 because the
> answer it owes is an address in the guest's own terms. **Neither
> half of this citation is a hope any more**, and the second
> hardened while this entry sat: both are standing rules now, so a
> gap against either is a defect rather than unbuilt work. Serves
> **U14** and **U20**. **Its address question is already
> answered**: the in-band file family (F23, delivered 2026-07-27
> by D62) settled one guest-terms vocabulary for all five of its
> verbs — a directory addressed exactly as a file is, `A:\` the
> drive root — and D5's `<drive-key>:<path>` shape died there.
> This verb adopts that vocabulary rather than reopening it; what
> it owes is the *answer* — attach this directory, and tell me its
> guest address in those terms.

A caller that needs a host directory visible to a guest **synthesizes
a directory-source drive into the blueprint**, which forces it to
know slot keys, slot limits, and the DOS drive-letter rule — three
pieces of Reliquary's model reproduced outside Reliquary in order to
reach a capability Reliquary supports. "Attach this host directory,
and tell me its guest address" deletes all three: the request is what
the caller actually means, and the answer is what P17 says an address
looks like.

CONSTRAINTS ALREADY SETTLED, which shape the verb rather than block
it. QEMU snapshots a vvfat staging directory when the drive is
attached, so a host-side change needs a stop/start cycle — this is a
**stopped-machine** operation, and the live-iteration path stays
U20's `insert-media` over a running machine. Slot limits and the
directory-on-cdrom refusal stay exactly as they are: the verb hides
the arithmetic, never the rules.

DECIDE FIRST: whether the attachment is **state or request** — a
persisted machine-state mutation in the family of `insert_media` /
`set_boot_order`, or a per-call convenience that composes a blueprint
edit. The first survives a stop/start and shows up in `machine.json`;
the second leaves the blueprint the only durable statement of what a
machine has. The answer decides whether this is one verb or a verb
and its inverse.

## F16 — The public surface a caller copies today

> **Entered 2026-07-27** from a consuming project's proposal
> (owner: admitted as a proposal). Three small exposures with one
> shared argument: each is Reliquary's own knowledge, reproduced
> outside Reliquary because the public surface does not carry it.
> **They are small but they are not housekeeping** — every one adds
> to the embedding API, which the housekeeping boundary excludes
> absolutely ([SURFACES.md](../SURFACES.md)). **That is not why
> they sit here rather than in [TASKS.md](../TASKS.md)**, and this
> entry is where that misreading began: the boundary is
> housekeeping's alone, and a small surface change may be a task
> (D45, which the 2026-07-27 gate audit cited this very sentence as
> precedent for before the reading was caught). What holds them
> here is that two of the three are **unsettled below** — item 2
> asks which artifact owns the answer, item 3 is probably F2's work
> rather than its own. Serves **U14**;
> item 1 cites **P10** and **P17**, item 3 belongs to **F2**.

1. **A public drive-address query.** `platform_dos.drive_letters` is
   not on the root import surface, so a caller needing a guest
   address copies the rule and guards the copy with a test against
   Reliquary's own function. That is a **correctness risk, not
   tidiness**: the mapping shifts when one disk carries several
   volumes, which a copy cannot know. P10 is what makes the function
   the only correct source — it is built from declared facts and
   never from a guest — and P17 is the shape the answer takes.
   Pairs with F15, which needs exactly this to answer with.
2. **Public topology limits.** Slot counts per medium
   (`_SLOT_LIMITS`), so a caller building a blueprint
   programmatically stops carrying its own copied `4`. Blueprint-model
   truth, and arguably the published schema's job rather than the
   API's — settle which before adding a function.
3. **A backend-agnostic availability check.** `backend_available()`
   rather than `find_qemu()`, so a caller gating integration tests
   never has to name an emulator to ask a backend-neutral question.
   Lowest priority of the three, and **probably not its own work**:
   the honest version of it is F2's autodiscovery work item, so
   this is a note against that feature as much as a request — and
   since F2 was pledged on 2026-07-28, that note now has somewhere
   to be filed.

## F18 — The media authoring commands

> Moved from [TASKS.md](../TASKS.md)'s Small items by the
> 2026-07-27 gate audit. Adding a CLI command is no bar to being a
> task (D45); what moved it is that **the shape is not settled** —
> both entries carry their own open question, and D41 has already
> moved the ground under them once, which is an argument to finish
> rather than work to pick up. Serves **U4** in force
> (a repository refers precisely to media it cannot distribute) and
> **U13** (media fetches and verifies itself), in force since D46.

**They are one feature because they share a scaffolder.** D41
settled that `add-media` is the local half already — compute the
sha256, write the declaration, copy nothing — so what is left is
the *download* half and the *drill-down* half of one authoring
motion, and the three should end up siblings over one writer.

**`download-media`** (owner request, 2026-07-22; shape to
re-derive under the revised model). `rlq download-media
https://freedos.org/downloads/FreeDOS14.zip` downloads the file
into `cache/media/`, computes its sha256, and scaffolds a
standalone `.rlqb` into the home library carrying the url and
sha256 — a media spec, with `children` left for the user to add
when the payload is a container. A home-mode convenience: it warms
the cache and writes the committed-source stub, so the user need
not hand-author it and then `fetch`. Open shape: members cannot be
inferred, so the stub stops at the container and the user adds the
extraction tree with `extract-media`; stem-default naming from the
URL filename; no `--local <file>` variant is needed, that being
`add-media`; CLI+API parity, the twin returning the written
blueprint path as `add_media` already does.

**`extract-media`** (owner request, 2026-07-23; re-derive under the
revised model) — the incremental companion. `rlq extract-media
--parent FreeDOS14 FreeDOS14-LiveCD.zip` extracts the child from
the named media, computes its sha256, and records it by **appending
a child** (path + sha256) to the existing media spec's `children` —
the leaning option — rather than writing a separate file, or as a
flat `${media:…}`-located spec; reconcile when picked up. A child
that is itself a container becomes another node to drill into
(`extract` it again); a payload child is extracted to
`cache/media/`. So a nested source is hand-authored by walking down
it one `extract-media` at a time, the `children` tree growing in
place. Open: new-file vs append-to-existing (lean append), and node
shape (a container child is a node with its own `children`, else a
leaf).

## F19 — The home inventory report

> Moved from [TASKS.md](../TASKS.md)'s Small items by the
> 2026-07-27 gate audit. Being a new CLI command is no bar to being
> a task (D45); what moved it is the open shape question below,
> which decides whether this is one command at all. **No
> use case asks for it**, said plainly. It serves **P12** by making
> what home containment holds visible, and **P11** in the reading
> that an orphan the tool cannot account for is a gap it should
> name rather than pass over.

Every item in the home and cache directories itemized in one way or
another, backend implementation files ignored — the presence of a
machine is noticed, its `qemu/` innards are not:

- **orphaned first**, because either you really want to keep it or
  you really should delete it: media declarations (not cached
  payloads), and scripts
- **blueprints**: materialized (online machines, offline machines),
  then unmaterialized
- **media**: referenced
- **scripts**: orphaned, then referenced

Open shape, and it decides whether this is one command at all:
whether the orphans lead the whole report or only their own
section, and whether this is a document of its own or a `--verbose`
column on the existing `list-*` commands.

## F20 — `version` and `help` as commands

> Moved from [TASKS.md](../TASKS.md)'s Small items by the
> 2026-07-27 gate audit. The diff is tiny and the CLI is an
> surface, but neither fact bars it from the task queue (D45 —
> the housekeeping boundary is housekeeping's alone). What moved it
> is the P6 question below, which is the actual work and is
> unsettled. Serves **P6**. No use case asks for it. Raised from
> the CLI's own help text.

`version` and `help` become command words, with `--version` / `-v`
and `-h` / `--help` surviving as undocumented aliases.

**The question is P6's, not cosmetic**, which is why this is a
feature and not a rename. Under the twin-name identity rule a
command *is* its API twin's name, so `version` implies a twin the
embedding API does not have today; settling whether it gains one is
the work, and a command word that maps to no call is exactly the
shape the parity rule exists to catch. `help` may or may not answer
the same way — a CLI presentation with no semantic behind it is the
other possible reading, and naming it a named omission is a
legitimate outcome.
[docs/spec/cli.md](../../docs/spec/cli.md) documents neither
spelling today, so nothing has to be unsaid first.

## F21 — One spelling, two phase kinds

> **Entered 2026-07-27** by the spec audit against the AHK/Python
> failure catalogs, the last of the script-language residuals. It
> is a proposal rather than a task **because the shape is open**,
> which is the same ground that moved F18–F20 out of the queue —
> the argument, not the surface, being what keeps something out of
> a queue of pre-approved work. Serves language goal **G6** (one
> concept, one spelling) and no use case. The owner offered it a
> task entry; it comes here because nobody has yet proposed what
> the fix *is*.

**A sequential phase and a reactive phase are different constructs
sharing one keyword**, and `timeout=` on them names two different
clocks. script-spec.md says both halves plainly:

> "A sequential phase is procedural, a reactive phase is
> declarative, and **both are spelled `phase`**."

and the clock table carries them as separate entries — an
observation `timeout` starting when its observation arms, a
**reactive interval** starting at phase entry *and again each time
dispatch resumes after a handler action*. So a reader meeting
`phase watchful timeout=5m {` cannot tell which clock that is
without scanning the body for whether it holds statements or
handlers.

**WHAT MAKES THIS NEW EVIDENCE** rather than a re-raise of a
settled tradeoff — the spec has already weighed the hybrid and
kept it deliberately ("the hybrid is not hidden; it is the
point"), so it deserves better than an opinion. Two things:

1. **The spec describes this defect twice, and fixes it once.**
   The bullet immediately above the one quoted reads: *"`on` is a
   case in a branching `wait`, `always` a standing rule in a
   reactive phase — one shape, two named lifetimes, **which the
   keyword split resolved**."* The project met this exact problem,
   named it in these words, and split the keyword — for the
   handlers, and not for the containers that give them their
   lifetimes.
2. **An outside study named the pattern independently.** The
   AHK/Python failure catalogs' sharpest import was a
   container-determined-semantics rule: *a construct's lifetime
   should be recoverable from its own text*. It was recorded as
   hitting the old example [04] — which is the `on`/`always` split.
   The audit's finding is that it hits `phase` too, and that the
   earlier weighing did not have this argument in front of it.

**THE PRICE IS ON A CLOCK**, which is the audit's second live
import: *a naming freeze is free before v1 and never after*. Today
the change is nearly free — **no shipped script uses a reactive
phase**, `always` appearing only in
[03-timing-spellings-and-scope](design/../design/script-examples/),
and there is no backward compatibility to honour before 1.0 (P9).
After 1.0 it is unavailable. That asymmetry is the argument for
settling it now rather than when someone is annoyed by it.

**DECIDE FIRST — the shape, which is why this is not a task.**
Three candidates, none costed, and the third is a real answer
rather than a placeholder:

- **A second keyword.** The direct analogue of the `on`/`always`
  split. Costs a word in a vocabulary G6 wants small, and the
  candidates are unexplored — `watch`, `monitor`, `rules`, none
  yet weighed against the existing verbs or against the
  reserved-identifier list.
- **A marker on the phase.** Keep one keyword and make the kind
  explicit at the head, so the text still says which clock it
  declares without a second construct. Cheaper on vocabulary,
  wordier at every use.
- **Neither — improve the reporting instead.** `check-script`
  already resolves and prints the timing plan naming each clock
  and the scope that supplied it, which is the same remedy the
  language accepted for its sibling problem: an observation's
  effective bound is *also* not locally readable, and that was
  settled as tooling's job rather than syntax's. If it was right
  there, the burden is on showing why it is wrong here.

The third candidate is why this needs an argument rather than a
work item: it may be that the honest answer is no change at all,
and the finding's value was in forcing the question while the
answer is still free.

*(F22 — every working directory is placeable — was entered and
delivered on 2026-07-27, so its number retires unreused. The six
`--*-dir` flags, the derivation cascade, the fail-closed
unassigned error, and the `--autoseed` axis that replaced
`--assets` are recorded in [D59](../DECISIONS.md), which also
carries the P12 and P4 amendments it required; the model itself
is normative in
[docs/spec/asset-resolution.md](../../docs/spec/asset-resolution.md).
U17 stays pledged: this serves it and does not on its own
complete it.)*

## Horizon — smaller and later

> **Not a feature, and so unnumbered.** This is a holding list of
> items too small or too unformed to be one. An item leaves it by
> being written up as a feature — taking the next free F-number
> then — or by going to [TASKS.md](../TASKS.md) if it turns out to
> be ordinary small work.
>
> **The traceability rule does not reach here** (settled by the
> 2026-07-27 demand-citation sweep, which would otherwise have
> flagged four items). That rule binds *pledged* items and design
> documents; a Horizon item is neither, and an item too unformed
> to be a feature is too unformed to know what demands it.
> Acquiring a citation is part of being written up — so an
> uncited item here is the list working, and a re-run of that
> sweep should not flag one.

- Machine mobility: clone, export, import — the former
  milestone 12 (the number guest agents inherited in the
  same-day renumber), moved here 2026-07-23 for lack of
  use-case
  backing: clone has no use case at all, export's stands only
  as the U8 draft, and import's U2 loses its scheduled
  delivery with this move. Scheduling it back onto the
  numbered arc is the pledge of those use cases. The
  designs stay settled (owner, 2026-07-22) and their worked text
  is at `git show cf56a0c:docs/spec/cli.md`, the last commit
  before the CLI spec was made normative and the unbuilt commands
  removed from it (2026-07-27 — a spec states what exists):
  `export-drive` / `export-machine` with the decoupled
  exporter vocabulary, `import-vm` with its consent points,
  `clone-machine` as the machine snapshot; the `import-vm`
  scope round (NIC/device translation, untranslatable config,
  named-snapshot targets) remains its decide-first when it
  returns. The durable-artifact exits become meaningful once
  two backends exist — sequence at or after the second
  backend.
- **Host portability: Linux and macOS** (added 2026-07-23, owner).
  Windows is the delivered host — the only one developed on,
  tested on, and claimed in the packaging classifiers (AGENTS.md
  "Dependencies and style"). Host code is written portably and
  the other paths exist, but unexercised is unclaimed under P11.
  Widening is gated on three jobs, each substantial and none of
  them a by-product of ordinary work:
  1. **Secret storage per host** — the credential-store capability
     against a Secret Service provider on Linux and Keychain on
     macOS. The `keyring` seam
     (../design/script-properties.md, "Secret storage") is
     built for exactly this, so the code is likely already right;
     what is missing is *evidence*, and the no-plaintext-fallback
     rule means a wrong guess fails a user's run outright.
  2. **Backend verification per host** — QEMU discovery, process
     ownership, paths, and the agentless display plane proven on
     each host, not assumed from the Windows implementation.
  3. **A place to run them** — CI or real hardware. Every claim
     above rests on a suite actually executing there; U18 (drafted)
     is the case for reaching such a host from this one, which
     would make Reliquary its own answer.
  Demand is uncited today: no use case asks to *run Reliquary on*
  another host — U18 asks to reach another OS as a guest, which is
  a different axis. Sequencing it is the pledge of whatever
  case does.
- `fork-blueprint` (a fire-and-forget authoring convenience;
  `new-blueprint` scaffolding lands in milestone 6) —
  currently unjustified: no use case demands it, and
  `seed-blueprint` already serves the seed-and-customize seam.
- `diff-blueprint <name>` — diff a user blueprint against the codex
  blueprint of the same name (moved from [TASKS.md](../TASKS.md) by
  the 2026-07-27 gate audit). Currently unjustified: no use case
  demands it. It lands here rather than as a feature because one
  line of intent is all there is, and here rather than in the task
  queue because it is a CLI addition.
- Bounded `guest-file-*` operations through a native guest
  agent — distinct verbs, never bundled into a console
  abstraction.
*(The in-band directory operations that sat here left on
2026-07-27 and are done: D57 promoted them to F23, being the two
places the shipped workflow failed P16's test, and D62 delivered
them the same day as `list-files` / `get-files` / `put-files`.
Their sequencing against the second backend was cut with the
promotion — P16 did not wait on it, and the wait would have been
the whole cost.)*

- Media commands beyond `fetch-media` (verify, remove) —
  **split by D46** (2026-07-27), which put U13 in force:
  `verify` now stands on a use case in force ("verifies it is
  exactly the build the scripts target"), so the
  lack-of-demand objection to it is gone and what is left is
  whether a standalone verb earns its place beside the
  verification `fetch-media` already does. `remove` still has
  no demand whatever — it stays unjustified.
- A `pytest-reliquary` plugin (per AGENTS.md prior art) —
  currently unjustified: adjacent to the U14/U15 drafts at
  best, and test-framework semantics belong to consumers (the
  doctrine boundary).
