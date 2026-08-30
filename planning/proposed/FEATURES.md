<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Proposed features

This file lists large unbuilt capabilities. Each one is roughly a
milestone's worth of work, with its **design settled and finished**,
waiting on demand before it gets scheduled. Nothing listed here is
being worked on yet ([README.md](../README.md)). Moving an entry to
[pledged/FEATURES.md](../pledged/FEATURES.md) is what makes it a
pledge, and the commit that makes that move is the record of the
pledge. An entry here gets its F-number from the sequence ledger
([SEQUENCES.md](../SEQUENCES.md)) — take the next number from there
and update the ledger in the same edit.

A feature that is pledged but not yet built moves to
[pledged/FEATURES.md](../pledged/FEATURES.md) and takes its list of
work with it. Small work that isn't a feature at all goes straight
to [TASKS.md](../TASKS.md).

Each feature carries an **F-number** (D42; the rules are in
[README.md](../README.md)). **There is no size limit for sitting
here** — the one-sprint limit only applies once a feature is
pledged, so every entry below is many sprints of work. "A
milestone's worth of work" above describes the size these entries
actually are, not a size limit for pledging one. Splitting an entry
into pieces that can actually be built is part of pledging it.

## F1 — The U6 authoring recorder

> **Withdrawn from [pledged/FEATURES.md](../pledged/FEATURES.md)**
> (owner, 2026-07-27; D61), together with **U6** — the use case it
> delivers — in the same round. What got withdrawn was the promise
> to build it, not the design, which still stands as written. D61
> records how this got pledged without anyone actually deciding to
> pledge it.
>
> Serves **U6** ([USE-CASES.md](USE-CASES.md)); design in
> [design/recorder.md](design/recorder.md). This is the one
> capability the numbered milestones deliberately did not deliver —
> that work ended at milestone 9 with the recorder still unbuilt.

**THIS ENTIRE FEATURE DEPENDS ON VNC** — that's the reason it was
withdrawn. Recording requires Reliquary itself to be the console:
if someone types into a backend's own display window instead, that
input never passes through Reliquary and can't be recorded. So a
Reliquary-owned viewer, built on the `vnc` control plane, is
required for recording on **every** backend, including QEMU
([design/recorder.md](design/recorder.md)). The screen-and-keyboard
half of that control plane is already delivered on QEMU (F63). The
viewer also needs pointer input, delivered as **F66**, and needs
interactive display, which is still part of the GUI era (**F5**).
An earlier note on this entry claimed a text-mode recorder could be
built depending on nothing else unpledged. **That was wrong, even by
this entry's own design** — what text mode skips is the landmark
and click work (F5's GUI asset spec and pointer input), not the
viewer, which text mode still needs.

Decide first:

- **How to split this up.** The deliverables below add up to at
  least seven features' worth of work for the sprint size this
  project uses, and D42 requires splitting it at pledge time —
  retiring F1's number and giving each resulting piece its own new
  number. The viewer is the natural first piece to cut out; the
  text-mode recorder follows it and needs no new language surface.

Deliverables:

1. A Reliquary-owned console viewer built on the `vnc` control
   plane. This is required for recording, since Reliquary can't see
   input typed into a backend's own display window.
2. The text-mode recorder: it generates `wait` steps from VGA
   screen scrapes, and `type`/`press` steps from keystrokes, and
   flags anything it's unsure about with a generated comment. It
   needs no new language surface.
3. Runner support for running to a point, setting a breakpoint, and
   handing control to a human — the same mechanism the failure
   report's "take over from here" suggested next command needs.
4. Round-trip editing: the recorder emits script fragments anchored
   to the playback position, and a user can opt in to apply them
   surgically at that anchor point. It never regenerates the whole
   script and never does a text merge.
5. The landmark catalog's shape. This was already decided
   (DECISIONS.md, the wrinkle round) and is now **delivered**
   ([docs/spec/landmarks.md](../../docs/spec/landmarks.md)). What
   the recorder still owes is emitting landmarks into that catalog.
6. Run-event kinds for handing control back and forth between a
   script and a human, so a capture session is one run record even
   when control passed between different drivers. Milestone 9
   reserved these in the spec, but no constant for them exists in
   the implementation yet.
7. The CLI `record` command family and its matching API calls,
   shipped together to keep CLI and API in parity.

## F4 — Guest agent communication

> **Dropped from the numbered milestones to the backlog** (owner,
> 2026-07-23): this was Milestone 12 (numbered 13 until the
> same-day renumbering that followed machine mobility being
> dropped down the list), and it is not yet scheduled. No use case
> currently demands it: the requirements that were first-class here
> (granular results, selective re-run) are already met by
> milestones 8-9, and the guest-agent control plane was only ever a
> *preference* stated by U3, not a requirement. U3 has since been
> retired (D51), and **U14, which replaces it, states no such
> preference at all** — so the case for dropping this is even
> stronger now than when it was written. The preference is now
> carried by **P3**, a principle rather than a requirement. The
> loop P3 talks about runs agentlessly on QEMU/DOS today. P3
> governs how a native agent gets used if this feature is built; it
> does not require that it be built.

Use native guest agents as control planes, following
[design/guest-communication.md](../design/guest-communication.md):
Reliquary uses the agents guests already have — QGA (QEMU Guest
Agent) first — and never builds its own (ARCHITECTURE.md P3, the
control-plane section). This work must not weaken the existing
agentless DOS path: guests without a native agent (including
DOS-era systems) keep working agentlessly, and for a guest that
supports both, the same test suites must validate the agentless and
guest-agent control planes and get equivalent results from both.

Decide first:

- Exactly which `guest-exec` calls to support at first, including
  which arguments and environment variables are supported, which
  ways of capturing output, and what output-size and timeout limits
  to enforce.
- Which limited `guest-file-*` operations to support after
  execution lands, including how they keep files consistent and
  how atomic file replacement should work.
- Whether it's worth adding a separate, plain serial-console
  control plane alongside the native guest agents and the existing
  agentless planes.

Deliverables:

1. A host-side QGA client module: it handles QGA's message framing,
   and the `guest-sync-delimited`, `guest-ping`/`guest-info`, and
   `guest-exec`/`guest-exec-status` calls. It depends only on
   QEMU's published guest-agent protocol, never on any one guest's
   particular implementation of it.
2. An extended `GuestExec` interface: request and result types that
   cover deadlines, completion, output, and exit status, without
   exposing any transport-layer objects.
3. A configured order of control planes to try, with a
   conservative fallback: Reliquary picks a control plane once,
   before the first command is sent, and never retries an
   ambiguous failure on a different control plane.

Done when: a guest command runs successfully through QGA on QEMU,
Reliquary reports its capabilities accurately, and the agentless
test suite still passes byte-for-byte.

## F5 — The GUI era: VNC, GUI scripting, and the last backends

> **Dropped from the numbered milestones to the backlog** (owner,
> 2026-07-23): this was Milestone 13, and it is not yet scheduled —
> it will be sequenced alongside the Horizon items below when its
> turn comes.
>
> **The decision on demand for this closed 2026-08-21** (D110): the
> rest of **U5**'s customized-installation work is pledged
> ([../pledged/USE-CASES.md](../pledged/USE-CASES.md)) and provides
> the justification for the GUI half of this feature — the VNC
> control plane, pointer input, landmarks, and the platform
> workflows — while **U7** already covers the last two adapters
> (D65). That same decision cut a piece out of this entry: **F63**,
> the VNC control plane on QEMU (screen and keyboard), which has
> since been **delivered**. F63 kept its own number; this entry
> (F5) kept the rest, under D110's ruling. **A second piece was cut
> out on 2026-08-24**: **F65**, watch-only landmarks — pledged and
> **delivered** the same day. F65's number was retired, and its
> behavior is now the normative spec at
> [docs/spec/landmarks.md](../../docs/spec/landmarks.md). **A third
> piece was cut out on 2026-08-25**: **F66**, pointer input — the
> `pointer_event` call, the `pointing-device` field, and the
> `click` verb — pledged and **delivered**. F66's number was
> retired, and its behavior is now normative at
> [docs/spec/script-spec.md](../../docs/spec/script-spec.md#click),
> [docs/spec/blueprint-model.md](../../docs/spec/blueprint-model.md),
> and [docs/spec/landmarks.md](../../docs/spec/landmarks.md). **A
> fourth piece was cut out on 2026-08-26**: **F67**, the WinNT half
> of the platform-workflows deliverable — the ReactOS codex recipe,
> and proof that F66 works against a real GUI — pledged and
> **delivered**. F67's number was retired. It added no new
> normative spec (a codex recipe is just content, covered by
> [docs/spec/codex.md](../../docs/spec/codex.md)); its record is
> [design/winnt-platform.md](design/winnt-platform.md) and the
> shipped recipe itself. Every deliverable still listed below now
> has pledged demand behind it and stays in this file until it too
> is pledged — a pledged use case makes a feature eligible to be
> pledged, but does not pledge it by itself (D65).
>
> **Hyper-V does have a console wire — it's just a different one
> than expected** (prior-art research, 2026-07-28; not yet
> adjudicated). The text below originally concluded that GUI
> automation must work through capabilities rather than one
> specific wire protocol, reasoning from the fact that Hyper-V
> seemed to have no console access at all. That conclusion still
> holds, and is now better supported — but the reasoning behind it
> was wrong. Hyper-V's VM console is actually reachable over RDP,
> connecting to the *host* (not the guest) on port 2179, with the
> VM identified by a GUID carried in an `MS-RDPEPS` preconnection
> blob. This works host-side, needs no RDP server in the guest, and
> serves the console even before any OS is installed. So GUI
> automation on Hyper-V has a **second way to reach the display**,
> rather than no way at all — which is actually a stronger example
> of the underlying point than "no way at all" was: a capability
> that can be satisfied two different ways is exactly the case this
> design exists to handle. The catch is the cost of building it:
> RFB hands a client a framebuffer, but RDP output is bitmap
> updates, drawing orders, and codecs — so the realistic way to
> support it is to vendor a native library (FreeRDP, which is
> Apache-2.0 licensed and implements this blob; there is no usable
> Python binding for it, and it ships no official Windows binary).
> **This does not change what's pledged** — a newly available
> protocol is not a use case by itself, and nothing currently
> pledged asks for GUI automation on Hyper-V. This finding applies
> on the same terms as the note above.

This is the last piece of work in the plan: GUI installer
automation, carried over the VNC/RFB control plane wherever a
backend provides it — natively on QEMU, on VirtualBox with the
extension pack installed, and on VMware Workstation. Two adapters
are still missing: VMware Workstation, then Hyper-V, deliberately
built last. Hyper-V has no VNC support — Reliquary must report that
capability as missing rather than fake it — which is exactly what
makes Hyper-V the proof that GUI automation works through
capabilities rather than through one specific protocol: its console
answers over a completely different carrier (see the note above),
so the capability needs to be reachable more than one way.

Decide first:

- The GUI asset spec is **delivered** (F65, 2026-08-24 —
  [docs/spec/landmarks.md](../../docs/spec/landmarks.md)). It
  covers: the `.rlql` JSON5 schema, identified by filename stem and
  pinned only by image dimensions (pinning by color mode was
  dropped because it couldn't be verified); the similarity metric,
  which is the fraction of matching pixels judged per region; and
  where references can be placed — `@name` can appear anywhere a
  screen condition can. (This bullet used to say "landmark-block
  placement within a script", which referred to the embedded
  landmark block that D12 removed before this was written. It's
  kept here only to note that the question is already settled; it
  goes away with the rest of this entry.)
- Pointer input, end to end, is **delivered** (F66, 2026-08-25 —
  [docs/spec/script-spec.md](../../docs/spec/script-spec.md#click)).
  It works like this: there is one carrier method, matching RFB's
  `PointerEvent` shape (the three input primitives this entry
  originally planned all collapse into that one call; key events
  were already delivered separately), and composing and pacing
  pointer movements is owned by the control plane above it.
  `pointing-device` (`tablet` or `mouse`) is a first-class machine
  field, now allowed under P25's gate; `click` refuses to run, at
  preflight, on a machine configured with a relative-only pointing
  device. `click` is the fifth guest-input verb — like `select`, it
  can make observations — and takes a `spot=` argument that
  defaults to a single spot, with a plain left click as the entire
  first version. This is kept here only to note the question is
  already settled; it goes away with the rest of this entry.
  **Left open**: a convenience for cropping landmark images on the
  host (as a CLI subcommand, never a background service). Era
  note: DOS- and Windows-9x-era setup GUIs use a fixed screen mode,
  fixed font, and no animation, so landmark images should need far
  fewer updates than os-autoinst's "needle" images typically do;
  NT-era setup can mostly be driven by keyboard alone, so
  keyboard-first stays the preferred approach wherever it works. A
  future bridge to os-autoinst should be built as an
  external-runner adapter or export target — generating an
  os-autoinst test distribution and invoking `isotovideo` as a
  separate process — not folded into Reliquary's own machine
  engine. Throughout this project, os-autoinst is a **reference for
  ideas only**: its designs are studied and reimplemented, never
  its code (see AGENTS.md's prior-art section for that boundary,
  which is a project rule, not just a licensing requirement).
- Growing the blueprint's device model is **designed** (owner
  round, 2026-08-24 — [design/device-growth.md](design/device-growth.md)).
  What that design round produced is a decision for each device
  type, not new fields — each item was checked against P25's two
  gates (is there real demand, and does it apply across multiple
  backends), and each rejection has its own written reason.
  Network: **delivered** (D120/D121/D122, 2026-08-29). `net`
  slots (`net0`, `net1`, …) join `devices` alongside drives, naming
  an attachment (`nat`/`bridged`) — the chipset resolves per
  platform by default, but an optional `model` overrides it (D122),
  since some DOS-era software needs a specific chipset. `http`'s own
  reachability path is unaffected, and still keeps
  being worked out from the script's `http` block, generalized to
  work per backend. Detecting a usable bridge interface for QEMU
  automatically is tracked separately (T32); no automatic bridge
  *creation* is planned at all (D120), since that mutates host
  network configuration.
  Firmware: `bios`/`uefi` support is fully designed (covering
  platform defaults and where the NVRAM variable store lives), but
  will not be added until the first platform that actually needs
  `uefi`. Display adapter: rejected as not broadly applicable,
  staying permanently something you configure through
  `backend-settings` instead. Audio: rejected for lack of demand.
  USB: a USB controller is always implied by whatever device needs
  it — it is never its own field. Controller defaults are chosen
  per platform and per medium type, following the existing arrival
  rule; slot ranges widen for a controller type only once that
  type is added (this stays additive, as this entry already
  required); a Hyper-V VM's generation is derived from the
  firmware choice — `bios` gives Gen1, `uefi` gives Gen2 — never
  set directly. **Adding a second controller type means there is
  no single declared "first disk."** Slot order only determines
  order within one controller type; across different types, it is
  the guest's firmware that decides how the controllers themselves
  get enumerated. This used to matter while Reliquary mapped disks
  to guest drive letters, but **D108 removed that mapping**, so
  what is left is narrower but still real: any future answer about
  which disk a guest sees first is a fact that no declaration in
  the blueprint can supply, and P10 forbids guessing at one. Boot
  order is the one exception that already works cleanly, because
  it is stated to the firmware directly rather than read back from
  it.
- The strategy for reading the Hyper-V screen without a guest
  agent is **designed as a bet, with the condition that would
  prove it wrong written down** (owner round, 2026-08-24 —
  [design/hyperv-screen.md](design/hyperv-screen.md)). Sending
  input is proven by prior art — Packer already drives
  `Msvm_Keyboard` from the host — but that is a blind approach with
  no screen feedback, which Reliquary cannot accept. Reading the
  screen is the open question. The plan is to use WMI thumbnail
  composition, **provided a spike proves it can capture at native
  resolution, unscaled** — RGB565 color is good enough to work
  with, since the recognizer converts images to black-and-white and
  the landmark matcher normalizes its reference images to match
  whatever pixel format the plane reports. If the spike fails,
  Reliquary reports the capability as absent (P11); the RDP carrier
  would then be weighed as its own separate proposal, and a
  serial-console or guest-agent plane is rejected as an answer to
  this specific question (per P3's control-plane rules). The spike
  has to run before this gets pledged, following the same
  precedent F64 set.

Deliverables:

1. Extending the VNC control plane past what **F63** already
   delivered for QEMU: configuring VirtualBox (with the extension
   pack) and VMware Workstation endpoints on the same plane,
   sending pointer events through the in-tree RFB client (the
   client itself, framebuffer capture, and key events are already
   delivered, in `src/reliquary/rfb.py` and the QEMU adapter's VNC
   code; which calls were approved for this is recorded in D110),
   and reporting a capability error that names Hyper-V specifically
   where this plane cannot exist.
2. Pointer input is **delivered, as F66** (owner, 2026-08-25;
   [docs/spec/script-spec.md](../../docs/spec/script-spec.md#click))
   — the `pointer_event` call, the `pointing-device` field, and
   `click`. What is still owed here: the host-side
   landmark-cropping convenience, and every deliverable below that
   builds on this one.
3. Landmarks are **fully delivered** (F65, owner, 2026-08-24,
   watch-only; F66, owner, 2026-08-25, clickable —
   [docs/spec/landmarks.md](../../docs/spec/landmarks.md)): the
   `.rlql` file kind, the image matcher, the `@name` condition, the
   rule for where the cursor parks, the built-in mask for the park
   zone, and the `click` verb built on top of the pointer
   primitive.
4. Windows 9x and Windows NT platform workflows: scripting for the
   setup GUIs that text scraping cannot handle, staying
   keyboard-first wherever NT-era setup allows it. **The WinNT half
   is delivered** (F67, 2026-08-26 —
   [design/winnt-platform.md](design/winnt-platform.md)): the
   ReactOS codex recipe, which uses keyboard-only steps through its
   text-mode setup exactly as this entry's era note predicted, then
   landmarks and `click` through its Win32 Setup Wizard. What is
   still owed here: the Windows 9x half, which is a different
   install flow with no demand yet to distinguish it (a scope call
   the design made), plus any richer pointer vocabulary that a
   future guest turns out to need.
5. The VMware Workstation adapter.
6. The Hyper-V adapter, built last, using whichever screen strategy
   [design/hyperv-screen.md](design/hyperv-screen.md) settles on —
   the spike's outcome, not this entry, decides whether that ends
   up being WMI thumbnail composition or a reported missing
   capability.

Done when: a GUI-era install script can drive a setup wizard end to
end using landmarks, both on QEMU over VNC and on Hyper-V using
whichever screen strategy got decided. (The criterion about running
an unmodified FreeDOS install over VNC, with recognition matching
the VGA scrape, was already delivered as F63's own done-when.)

## F6 — Asynchronous runs

> **Deferred to the backlog** (owner, 2026-07-24, D35; scope
> extended D36): running scripts asynchronously is dropped from the
> numbered milestones — milestone 9 delivers running a script and
> getting its output, without this. No currently active or pledged
> use case asks for it: the feedback-splitting rule (P5) is already
> satisfied by a run's own driver watching it live, and detaching a
> run, or following one from a process that did not start it, is a
> separate capability that no use case currently writes down. The
> closest thing to demand for it is the draft use case U19
> ([proposed/USE-CASES.md](USE-CASES.md), "start a long run and
> follow it from elsewhere"); pledging U19 is what would put this
> work back on the schedule, and the pledge record would cite it.
>
> **Storing run records lives here too (D36).** For another
> process to follow a run, the run has to be written down
> somewhere, so the entire storage design belongs to this feature
> and comes back with it: the `cache/machines/<id>/runs/<n>/`
> archive, numbered per machine with an always-increasing counter;
> the `run-events.jsonl` and `transcript.txt` files that get saved;
> retention rules and the `list-runs` / `run status` / `run delete`
> commands; the rule for detecting a crashed run (checking writer
> identity and whether that process is still alive); and
> interaction runs (`begin-run` / `end-run`, which bracket the
> primitive loop and are also what the U6 recorder needs). Milestone
> 9 stores nothing at all; this is where storage comes back. The
> design below, and this record model, are both settled and stand
> as written.

**Running a script normally is really just: start it async, then
attach to watch it.** A foreground `run-script` run is defined as
starting the run and immediately attaching a live renderer to it.
That is one behavior with one code path, and it means a run started
in one terminal can be watched from another. Pressing Ctrl-C on a
foreground run cancels the run; pressing Ctrl-C after reattaching to
it later only stops watching it. (Until this feature lands,
milestone 9's foreground run works more simply: the runner lives in
the same process that started it, and the renderer reads directly
from the stream that process writes, with no way to attach from a
different process.)

**Detaching hands control off right where the machine takes over.**
`run-script --detach` finishes parsing the script, binding it to a
machine, and running static and capability preflight checks in the
foreground — those failures show up in the invoking command's exit
code, never hidden inside a run record (G3). Only then does it spawn
the runner as a background process and print the run's id. That
detached runner is an owned child process, the same way Reliquary
treats QEMU: the run record stores who is writing to it (process id
plus start time), a liveness check confirms that identity before any
command can act on the run, and a stale record fails closed — the
same rule `vm.json` uses, applied here to the runner. This is what
lets Reliquary tell a genuinely *crashed* run apart from one that is
simply still incomplete: a crashed run's record is missing its
terminal event.

**You can cancel a run from a different terminal than the one that
started it.** `run cancel` sends a stop request; the runner finishes
at the next safe stopping point (input deliveries complete
atomically, but host file transfers can be aborted mid-way — this
follows how the execution model can be safely interrupted), writes a
`cancelled` terminal event, and leaves the machine running, per the
rule against implicit teardown. The `--stop-machine` flag opts into
powering the machine off (it mirrors the `cancel(stop_machine=)`
parameter in the API — CLI flags mirror API parameters throughout
the run commands; owner, 2026-07-21). The `cancelled` outcome and
its exit code (`5`) already exist in milestone 9, for a foreground
Ctrl-C; what is deferred here is cancelling a run that the current
process did not start.

**Commands for watching a run.** `run tail` displays a live run's
output stream, following the standard progress format (a formatted
view on a terminal, plain text or JSON Lines for scripts); `run
wait`'s exit code matches the run's outcome, so a caller in a
language with no Reliquary bindings can still get a result by just
waiting on it. Both commands take the run number as an ordinary
positional argument, defaulting to the machine's most recent run,
with the machine itself chosen using the usual `--machine` /
`--blueprint` options.

**The embedding API has its own version of this: a run handle.** The
API's equivalent of `--detach` is `start_script()`, which returns a
run handle with `status()`, `events(follow=)` (a blocking iterator),
`wait(timeout=)`, and `cancel(stop_machine=)`.
`attach_run(machine=, blueprint=, run=None)` reopens a handle from a
different process, defaulting to the machine's latest run the same
way the CLI `run` commands do. The handle only lets you pull data —
there are no callbacks, nothing that a typical language binding
could not express directly. `wait(timeout=)` behaves exactly like
the blocking version of running a script — same result, same
exceptions — except that timing out raises something outside
Reliquary's normal error types (in Python, the built-in
`TimeoutError`): nothing has failed, the handle is still valid, and
the caller can just call `wait` again (owner, 2026-07-21). A handle
only follows a run; it never owns it — discarding a handle never
affects the run itself. Garbage-collection timing has no effect in
any language binding, and `cancel()` is the only way to actually
cancel a run. A caller who wants concurrency without dealing with
any of this can just run the blocking version of the call on their
own thread — the actual work still happens on the caller's side of
the boundary.

**Fetching media also gets a handle.** `start_fetch()` (which takes
the same parameters as `fetch_media()`) returns a pull-only fetch
handle, with `status()`, `events(follow=)`, `wait(timeout=)`, and
`cancel()` (which aborts at the next safe point, deletes the partial
download, and never touches any file that already existed). There
is no way to attach to a fetch by id later, and no CLI command for
it — `start_fetch` is the only async starter that does not get one
(owner, 2026-07-21): its stream only exists within the process that
started it, since reattaching to a run from elsewhere is what run
records are for, and a CLI script that wants to run `fetch-media` in
the background can just background the whole process, which then
serves as its own handle. Because the handle form has no interactive
prompts, it also refuses `on_mismatch="prompt"` — a background fetch
can never get stuck waiting on a hidden prompt.

## F7 — Audit design documents against pledged demand

> **Moved here from TASKS.md's legacy Proposed section** (owner,
> 2026-07-26): this was discussed but never approved, and a
> proposal belongs under `proposed/`. **P8** requires it (surface
> and principle changes must be vetted): the audit checks that a
> design document exists only where there is demand for it. No use
> case asks for this.

**Audit design documents against pledged demand.** This came up
unprompted during the 2026-07-24 traceability audit — it is a
suggestion, not something anyone requested — so it sits here.

The findings that motivate it were folded in from
[TASKS.md](../TASKS.md) by the 2026-07-27 gate audit, which found
this same item listed as both pledged there and proposed here, and
kept it as a proposal:

- Two documents do not cite any U/P/G number at all:
  [backend-adapter.md](../design/backend-adapter.md) (230
  lines) and
  [blueprint-cookbook.md](../../docs/blueprint-cookbook.md) (440
  lines of examples — arguably exempt). *The first was fixed on
  2026-07-28 when its feature was pledged: it named U7 and F2 and
  moved to `pledged/design/` along with them, then moved back to
  `design/` the same day once F2 was delivered and there was no
  longer a feature for it to sit with. One finding remains.*
- Beyond missing citations, three design documents exist for work
  whose demand was never pledged — `backend-adapter.md`,
  [guest-communication.md](../design/guest-communication.md), and
  the landmarks design — all three demoted by D33 *for lacking
  use-case backing*, after their designs were already written.
  *`backend-adapter.md` left this list on 2026-07-28: the fix the
  traceability rule requires is finding and pledging the demand
  (U7), not deleting the work, and that is what happened. Landmarks
  left the list the same way: U5 was re-pledged (D110, 2026-08-21),
  then pledged as F65 and delivered (2026-08-24), and its design is
  now the normative spec at
  [docs/spec/landmarks.md](../../docs/spec/landmarks.md). One
  remains.*
  This is a one-time retrospective pass over designs written
  before the current rule took hold; going forward, a design
  document stays filed with the feature it serves and gets cleaned
  up along with it.

## F8 — The planning traceability linter

> **Moved here from TASKS.md's legacy Proposed section** (owner,
> 2026-07-26): this was discussed but never approved, and a
> proposal belongs under `proposed/`. **P8** and **P23** require
> it — it enforces by machine what those principles only assert,
> instead of leaving the checking to whoever happens to run a
> grep. It pairs with **F9**, its mirror. No use case asks for
> this.

**Build a linter that checks the planning documents for
traceability.** It would check, as one of the required checks,
the rules the project's governance already claims to enforce — so
they are actually enforced instead of just remembered.
THE REASONING: these planning documents have to be plain versioned
files, because the standing lists claim every entry is true of the
code *at this commit*, and only something that travels inside the
commit can make that claim, and only a diff can be reviewed for it
(this is also why architecture decision records converged on
markdown files kept in the repo, and why their tooling is indexers
over files rather than separate issue trackers). What plain files
do not give you is **type checking and querying**: nothing
currently enforces that a decision entry lists its supporting
reasons, or that delivered work cites demand that was actually
pledged. Today those things only get checked by whoever happens to
run a grep, which is exactly how U9 and U12 went unnoticed all the
way through the milestone that delivered them.
EACH CHECK IS HERE BECAUSE IT CAUGHT A REAL BUG — a hand audit on
2026-07-24 found an actual violation of every one:
* every planning section cites a U/P/G number — *12 of the 34
  sections in the roadmap at the time cited none. Re-checked by
  hand on 2026-07-27, after that roadmap was replaced, only **2 of
  27** sections were missing one, and both were already known about
  ([F5](#f5--the-gui-era-vnc-gui-scripting-and-the-last-backends),
  closed 2026-08-21 by D110, and `backend-adapter.md`, closed
  2026-07-28). That improvement did not come from anyone being more
  careful — it came from restructuring the documents so each entry
  was written with its demand attached. That is actually the
  argument for a linter, not against one: whatever a one-time
  restructuring fixes, ordinary drift will eventually break again*;
* every entry in DECISIONS.md lists its supporting reasons — *22
  entries did not, and D29 fell outside the range an existing
  manual task assumed it needed to check*;
* no *delivered* work cites *unpledged* demand — *U9 and U12* were
  the worst violation found, and it is exactly the kind of case a
  linter would have caught the day milestone 9 shipped (it was
  instead caught and closed by hand three days later, D46 — which
  supports building the linter rather than arguing against it:
  three days is the cost of relying on manual grepping instead);
* every design document's subject has pledged demand behind it —
  *three design documents existed for work that D33 demoted for
  lacking it*;
* every cited identifier actually resolves to something — *U15 was
  cited 6 times and defined nowhere*;
* no entry appears in both a standing list and its corresponding
  proposals document (D23's rule against leaving stubs behind).
ONE DESIGN QUESTION THIS RAISES. The U15 finding above is not
simply a bug to fix: most of those 6 citations are legitimate
references to a retired item's history, and the project's rule
deliberately leaves **no stub** behind a retired number (D23). So a
checker cannot tell a proper historical citation apart from a stale
one, unless there is a machine-readable list of retired identifiers
somewhere — and the no-stub rule currently keeps that list from
existing anywhere obvious. This has to be reconciled before the
linter is built: either that list lives in DECISIONS.md's Retired
section in a format a program can parse, or a retired identifier
gets the one stub the no-stub rule otherwise refuses to allow.
SCOPE is deliberately narrow: only mechanical, checkable rules.
Whether a use case is *well argued*, whether a principle is
*actually honored by the code*, whether a design is *good* — none
of that can be checked by a program, and a linter that pretended it
could would invite exactly the box-ticking that these governance
rules exist to prevent.

Raised on 2026-07-24 as a suggestion, not a request.

## F9 — The vision-utility audit

> **Moved here from TASKS.md's legacy Proposed section** (owner,
> 2026-07-26): this was discussed but never approved, and a
> proposal belongs under `proposed/`. **P8** requires it. This is
> the reverse-citation half of **F8**: F8 checks that every
> *citation* resolves to something; this checks that every
> *definition* gets cited somewhere. It shares F8's design and
> should be scheduled alongside it. No use case asks for this.

**The vision-utility audit — checking citations in reverse.** The
traceability linter above checks that every *cited* identifier
resolves to something real; this is its mirror — it checks that
every *defined* vision statement (a use case, a principle, or an
application surface) is cited or acted on *somewhere*, and flags
it as suspect if not. A statement nothing relies on is suspect of
being useless: written down but never actually used.
DISCIPLINE — this produces a list to look at, not a list of things
to delete. Finding orphaned statements is mechanical (just grep for
the numbered identifiers); deciding what to do about each one is a
judgment call the audit must not make for you. Each orphan deserves
one question — *is this a guardrail, or is it dead weight?* — since
a limit or a closing condition that only gets cited once pressure
actually arrives is doing its job, not sitting idle. Principles get
more benefit of the doubt than use cases: some principles genuinely
can't be tied to a specific citation and are legitimately hard to
reference.
DELIVERY — this can be run by hand with grep today; running it
monthly in CI would be the fuller eventual version. Per P22 (no CI,
for now), scheduling that CI run is itself the argument for turning
CI on when that day comes — not a violation of the current rule
against it.

Raised on 2026-07-25 as a suggestion, not a request.

## F10 — Generated API reference

> **Moved here from TASKS.md's legacy Proposed section** (owner,
> 2026-07-26): this was discussed but never approved, and a
> proposal belongs under `proposed/`. No demand is cited for it. It
> serves the accuracy of the descriptive documentation layer; the
> bar it has to clear is **P21** (a dependency has to pull its
> weight), not proof of demand.

**Generate the API reference from docstrings** (raised 2026-07-26,
during the spec/descriptive round; the owner asked for it to be
filed along with its reasoning). Adopt a documentation generator
(pdoc, mkdocstrings, or Sphinx autodoc) to produce
`docs/api-reference.md` from the Python API's docstrings.
SCOPE, and this is the whole point: **this is plumbing for the
descriptive documentation, never a shift in what has authority.**
A generated reference is *mechanically* faithful to the actual API
code, because the tool reads the real function signatures — so a
reference disagreeing with the code becomes impossible by
construction, which automates the apology the reference's banner
already makes today. What still defines the API surface stays
[docs/spec/api.md](../../docs/spec/api.md): letting the code define
it instead would invert P8 — an unargued code change would then
*redefine* the surface rather than merely violate the spec — and
the project has already lived through the counterexample: the
twin-name realignment settled the API's names in the spec while the
code still said `create_from_blueprint`, and it was the code that
got changed to match the doc, not the other way around. Matching
behavior between code and spec (parity) alone can't replace the
spec's authority here — parity only checks shape, not meaning, and
under the twin-name rule the CLI's command names are derived from
the API's names, so letting code define the surface would put the
safeguard downstream of the very thing it's supposed to guard. The
case for keeping the spec authoritative gets even stronger with
multiple language bindings planned for later — two bindings mean
two separate codebases, and "the code defines the surface" stops
even making sense as a rule; generation would then correctly
produce one descriptive reference *per binding*, each one still
answering to the single spec.
THE BAR TO CLEAR, before adopting even this plumbing: P21 governs
adding infrastructure — today's API surface is small enough that
the hand-written reference isn't obviously worse; without CI (P22),
a generated document needs some local required check to force
someone to regenerate it, or it will simply go stale in a new way;
and `test_documented_examples.py` runs the code examples that
appear in the docs, so generated output has to preserve that
property, or someone has to deliberately turn that test off for it.

Raised on 2026-07-26 in the spec/descriptive round; **the owner
agreed this needs to win the argument, not that it already has** —
so unlike F7-F9, this one was actually requested, and it is still
waiting on someone to make its case.

## F14 — Full guest-output capture

> **Entered 2026-07-27** from a consuming project's proposal
> (owner: admitted as a proposal). **This is the strongest-demand
> item of the six entries added this way, and the only one that
> changes what a caller can do today, rather than just how it's
> tested.** **U14** demands it (in force — the caller needs
> detailed results), and so does **P11**: `exec` only returns
> whatever is currently visible on screen, so output longer than
> one screenful gets its beginning cut off, and it gets cut off
> *silently*. A capability limit that doesn't announce itself at
> the moment it actually bites is a P11 violation, and it's close
> enough to a violation of that standing principle that it's worth
> deciding on that basis rather than needing a separate case made
> here.

This limit is already documented honestly — agentless capture only
keeps whatever tail of a long command's output is still on screen —
but **being honest about a limit in the documentation is not the
same as reporting it in the actual return value.** A caller listing
what's available inside a guest (get a listing, then act on each
item) gets a truncated listing whenever the real listing is longer
than one screen, and nothing in what it reads back says so. That's
the difference between listing things inside a guest being usable
and not.

TWO SEPARATE DELIVERABLES HERE, and the cheap one might be the whole
fix:

1. **Report the risk.** A read that could have lost its beginning
   reports that it might have. This is the minimum P11 requires, it
   needs no new transport mechanism, and it turns a silently wrong
   answer into a visibly uncertain one.
2. **Capture everything, not just the visible screen.** Scrolling
   back past what's currently on screen is a question about what the
   control plane can do, not about scraping technique — the
   agentless approach only has one screen's worth of VGA text memory
   to read from. The fix is either paced reading (drive the guest's
   own pager program and capture output page by page) or using a
   different control plane. Whichever it turns out to be, **P2**
   constrains it: the agentless path must not end up depending on
   the guest cooperating.

DECIDE FIRST: **whether item (2) is even Reliquary's job to solve.**
The competing answer is: just do (1), plus the channels that already
exist for moving data out — a guest program can write its long
output to a drive that the caller then reads back on the host, which
Reliquary already supports without reading a single byte of that
file itself (P18, and the file-content exception to P16 that's
existed since D108). If that's the right answer, this entire entry
shrinks down to just item (1) and stops being a feature at all. If
it's not the right answer, the argument for why needs to be made
here before any of this gets built.

## F15 — Host-directory attachment as a first-class operation

> **Entered 2026-07-27** from a consuming project's proposal
> (owner: admitted as a proposal). **P16** demands it, and is in
> force, because today the only way to reach this capability is for
> a caller to reproduce Reliquary's internal model outside of
> Reliquary. It serves **U14** and **U20**, and **D108 made this
> more valuable, not less**: now that the in-band file family is
> gone, attaching a directory as a drive is one of only two ways
> Reliquary offers to get a file across at all, so the bookkeeping
> this new command would hide is bookkeeping every caller now has to
> do by hand. **What this command would answer with also changed at
> the same time.** The guest-side letter that the original version
> of this entry promised no longer exists — there is no more
> drive-letter mapping — so what it answers with instead is the
> **drive key** the attachment was given, which is the same
> vocabulary `insert-media`, `eject-media`, and `set-boot-order`
> already use, and that a blueprint already writes. Asking for the
> drive letter back is really asking for the old drive-letter
> mapping back, and needs to be argued as that.

A caller that needs a host directory visible to a guest currently has
to **write a directory-source drive into the blueprint by hand**,
which forces it to know Reliquary's slot keys and slot limits —
details of Reliquary's internal model, reproduced outside Reliquary,
just to reach a capability Reliquary already supports. A command like
"attach this host directory, and tell me which drive it landed on"
would remove the need for both.

CONSTRAINTS ALREADY SETTLED, which shape this command rather than
rule it out. QEMU takes a snapshot of a vvfat staging directory when
the drive is attached, so a change on the host side needs a
stop/start cycle — this has to be a **stopped-machine** operation,
and the path for changing media on a running machine stays U20's
`insert-media`. Slot limits, and the rule against attaching a
directory as a CD-ROM, stay exactly as they are: this command hides
the bookkeeping, but never bends the rules. What the guest itself
calls the drive is up to the guest, and Reliquary makes no claim
about it.

DECIDE FIRST: whether the attachment is **state or request** — a
persisted machine-state mutation in the family of `insert_media` /
`set_boot_order`, or a per-call convenience that composes a blueprint
edit. The first survives a stop/start and shows up in `machine.json`;
the second leaves the blueprint the only durable statement of what a
machine has. The answer decides whether this is one verb or a verb
and its inverse.

## F16 — The public surface a caller copies today

> **Entered 2026-07-27** from a consuming project's proposal
> (owner: admitted as a proposal). Two small gaps with one shared
> reason: in both cases, a caller has to reproduce knowledge
> Reliquary already has internally, because the public API doesn't
> expose it. **They're small, but this is not routine housekeeping**
> — both would add to the embedding API, and housekeeping work is
> never allowed to touch that API at all ([SURFACES.md](../SURFACES.md)).
> **That is not the reason they're filed here instead of in
> [TASKS.md](../TASKS.md), though** — this entry is actually where
> that confusion started: the "housekeeping can't touch the API"
> boundary is about housekeeping specifically, and a small API
> change can still legitimately be a task rather than a feature
> (D45 — the 2026-07-27 gate audit even cited this very sentence as
> a precedent for that, before the misreading was caught). What
> actually keeps these two items here is that both are **still
> unsettled**, as described below — item 1 needs a decision about
> which artifact should own the answer, and item 2 is probably F2's
> work rather than a feature of its own. This serves **U14**; item 2
> belongs under **F2**. **A third item here died along with D108**:
> a proposed public query for drive letters, which would have
> exposed `platform_dos.drive_letters` through the import surface so
> a caller wouldn't have to copy the drive-letter rule itself. There
> is no more drive-letter rule to copy, so nothing needs to replace
> this item.

1. **Expose the built-in slot limits publicly.** Slot counts per
   medium type (currently the internal `_SLOT_LIMITS`), so a caller
   building a blueprint in code doesn't have to hardcode its own
   copy of the number `4`. This is really blueprint-model truth, and
   arguably belongs to the published schema rather than to the API
   — that needs to be settled before adding a function for it.
2. **A backend-agnostic way to check availability.** A
   `backend_available()` call, instead of `find_qemu()`, so a caller
   that's gating integration tests never has to name a specific
   emulator just to ask a backend-neutral question. This is the
   lower priority of the two, and **probably isn't its own piece of
   work**: the real fix for it is F2's autodiscovery work item, so
   this is really a note against that feature more than a separate
   request — and since F2 was pledged on 2026-07-28, that note now
   has somewhere to actually be filed.

## F18 — The media authoring commands

> Moved from [TASKS.md](../TASKS.md)'s Small items by the
> 2026-07-27 gate audit. Adding a CLI command doesn't by itself
> disqualify something from being a task (D45); what got this moved
> here is that **the shape of these commands isn't settled** — both
> entries below carry their own open question, and D41 has already
> changed the ground they stand on once, which is an argument that
> this needs to be finished rather than picked up as routine work.
> This serves **U4**, in force (a repository needs to refer
> precisely to media it isn't allowed to distribute), and **U13**
> (media fetches and verifies itself), in force since D46.

**These two commands are one feature because they share a scaffolder.**
D41 already settled that `add-media` handles the local half —
computing the sha256, writing the declaration, copying nothing — so
what's left is the *download* half and the *drill-down* half of the
same authoring workflow, and all three commands should end up as
siblings sharing one writer.

**`download-media`** (owner request, 2026-07-22; its shape needs to
be re-derived to match the revised model). Running `rlq
download-media https://freedos.org/downloads/FreeDOS14.zip`
downloads the file into `cache/media/`, computes its sha256, and
scaffolds a standalone `.rlqb` file into the home library holding
the url and sha256 — a media spec, leaving `children` for the user
to fill in if the payload turns out to be a container. This is a
home-mode convenience: it warms the cache and writes the
committed-source stub for the user, so they don't have to hand-write
it and then call `fetch` separately. Open questions about its shape:
members of a container can't be inferred automatically, so the stub
stops at the container itself and the user adds the extraction tree
with `extract-media`; the default name comes from the URL's filename
stem; there's no need for a `--local <file>` variant, since that's
what `add-media` already is; and it needs CLI/API parity, with the
API twin returning the written blueprint path the same way
`add_media` already does.

**`extract-media`** (owner request, 2026-07-23; also needs
re-deriving under the revised model) is the companion command for
going one level deeper. Running `rlq extract-media --parent
FreeDOS14 FreeDOS14-LiveCD.zip` extracts the named child from the
named media, computes its sha256, and records it by **appending a
child entry** (path plus sha256) to the existing media spec's
`children` list — this is the leaning option, rather than writing a
separate file, or writing a flat spec addressed by
`${media:…}` — that choice still needs reconciling once this is
picked up. A child that is itself a container becomes another node
to drill further into (running `extract-media` on it again); a
child that's a plain payload gets extracted straight to
`cache/media/`. So a deeply nested archive gets hand-authored by
walking down it one `extract-media` call at a time, growing the
`children` tree in place as you go. Still open: whether each
extraction writes a new file or appends to the existing one (leaning
toward append), and the exact shape of a node (a container child is
a node with its own `children`; anything else is a leaf).

## F19 — The home inventory report

> Moved from [TASKS.md](../TASKS.md)'s Small items by the
> 2026-07-27 gate audit. Being a new CLI command doesn't by itself
> disqualify something from being a task (D45); what got this moved
> here is the open question about its shape, below, which decides
> whether this even ends up being one single command. **No use case
> asks for this**, stated plainly. It serves **P12**, by making
> visible what's actually being held inside the home directory, and
> **P11**, under the reading that an item the tool can't account for
> is a gap it should name rather than silently skip.

Every item in the home and cache directories gets itemized one way
or another; backend implementation files are ignored (a machine's
presence is noted, but what's inside its `qemu/` directory is not):

- **orphaned items come first**, because for each one, either you
  really want to keep it or you really should delete it: media
  declarations (not the cached payload files themselves), and
  scripts
- **blueprints**: materialized ones first (running machines, then
  stopped machines), then unmaterialized ones
- **media**: the ones actually referenced by something
- **scripts**: orphaned ones, then referenced ones

Still open, and this decides whether the report ends up being one
single command at all: whether orphaned items lead the whole report
or only appear in their own section, and whether this becomes a
report of its own or just a `--verbose` column added to the existing
`list-*` commands.

## F20 — `version` and `help` as commands

> Moved from [TASKS.md](../TASKS.md)'s Small items by the
> 2026-07-27 gate audit. The code change is tiny, and the CLI counts
> as a public surface, but neither fact rules this out of the task
> queue on its own (D45 — the rule keeping housekeeping work away
> from the public surface only applies to housekeeping specifically).
> What got this moved here is the P6 question described below, which
> is the actual work involved and is still unsettled. This serves
> **P6**. No use case asks for it. It was raised by looking at the
> CLI's own help text.

`version` and `help` become proper command words, with `--version` /
`-v` and `-h` / `--help` continuing to work as undocumented
shortcuts for them.

**The real question here is P6's, not just a cosmetic one** — which
is why this counts as a feature rather than a simple rename. Under
the twin-name rule, a CLI command name *is* the name of its matching
API call, so adding `version` as a command implies it needs a
matching API call, which the embedding API doesn't have today.
Deciding whether to add one is the actual work — a command word with
no matching API call is exactly the mismatch the parity rule exists
to catch. `help` might or might not need the same treatment — it's
possible a CLI-only command with no equivalent API behavior is the
right answer here, and it would be a legitimate outcome to
deliberately leave it out of the API on purpose.
[docs/spec/cli.md](../../docs/spec/cli.md) doesn't document either
spelling today, so there's nothing that needs to be un-said first.

## F21 — One spelling, two phase kinds

> **Entered 2026-07-27** by the spec audit, working against the
> AHK/Python failure catalogs — the last of the leftover
> script-language issues from that review. It's a proposal rather
> than a task **because its shape is still open**, the same reason
> F18-F20 got moved out of the task queue — it's the strength of
> the argument, not whether it touches a public surface, that keeps
> something out of a queue of pre-approved work. This serves
> language goal **G6** (one concept, one spelling) and no use case.
> The owner offered to file it as a task instead; it's here because
> nobody has yet proposed what the actual fix should be.

**A sequential phase and a reactive phase are different constructs
that share one keyword**, and the `timeout=` argument means two
different clocks depending on which kind of phase it's attached to.
script-spec.md says both halves plainly:

> "A sequential phase is procedural, a reactive phase is
> declarative, and **both are spelled `phase`**."

and its clock table lists them as separate entries: an observation's
`timeout` starts counting when that observation is armed, while a
**reactive interval** starts counting when the phase is entered, and
*restarts again every time dispatch resumes after a handler runs*.
So a reader who sees `phase watchful timeout=5m {` can't tell which
of the two clocks that is without reading through the body to see
whether it holds plain statements or event handlers.

**WHY THIS COUNTS AS NEW EVIDENCE** rather than reopening an
already-settled tradeoff: the spec has already weighed this exact
hybrid design and deliberately kept it ("the hybrid is not hidden;
it is the point"), so reopening it needs more than just an opinion.
Two things make it more than that:

1. **The spec describes this same defect twice, but only fixed it
   once.** The bullet right above the one quoted above reads:
   *"`on` is a case in a branching `wait`, `always` a standing rule
   in a reactive phase — one shape, two named lifetimes, **which the
   keyword split resolved**."* So the project already ran into this
   exact problem, described it in almost these words, and fixed it
   by splitting the keyword — but only for the handlers (`on` versus
   `always`), not for the phase containers that give those handlers
   their lifetime in the first place.
2. **An outside study named the same pattern independently.** The
   sharpest lesson from the AHK/Python failure catalogs was a rule
   that a construct's lifetime should be recoverable just from
   reading its own text, without outside context. That study
   recorded this rule as violated by the old example labeled [04] —
   which is exactly the `on`/`always` split described above. This
   spec audit's finding is that `phase` violates the same rule, and
   that the earlier decision to keep the `phase` hybrid was made
   without this argument in front of it.

**THE COST IS TIED TO A CLOCK**, which is the spec audit's second
relevant lesson: *renaming something is free before v1 and never
free after*. Right now, this change costs almost nothing —
**no shipped script uses a reactive phase yet**, `always` currently
appears only in
[03-timing-spellings-and-scope](../design/script-examples/),
and there's no backward compatibility to preserve before 1.0 (P9).
After 1.0 ships, that option disappears. That asymmetry is the
argument for settling this now, rather than waiting until someone
runs into the confusion in practice.

**DECIDE FIRST — what shape the fix takes, which is why this is a
proposal and not a task.** There are three candidate approaches,
none of them costed out yet, and the third is a genuine answer, not
just a placeholder:

- **Add a second keyword.** The direct equivalent of the
  `on`/`always` split, applied to phases. This costs one more word
  in a vocabulary that G6 wants kept small, and the candidate words
  are still unexplored — `watch`, `monitor`, `rules` — none of them
  weighed yet against the language's existing verbs or against the
  list of reserved identifiers.
- **Add a marker on the phase instead of a new keyword.** Keep the
  single `phase` keyword, but make the kind explicit right at the
  top of the phase, so the text still tells you which clock it's
  using without introducing a second construct. Cheaper in
  vocabulary, but wordier every time it's used.
- **Change neither — improve the reporting instead.** `check-script`
  already resolves and prints the full timing plan, naming each
  clock and where its value came from. That's the same fix the
  language already accepted for a related problem: an observation's
  effective time limit is *also* not something you can read directly
  off the page, and the project decided that was tooling's job to
  surface, not syntax's job to make explicit. If that reasoning was
  right there, it's on anyone who disagrees to explain why it
  doesn't apply here too.

That third option is exactly why this needs to be argued out rather
than just turned into a work item: it's possible the honest answer
here is no change at all, and the real value of this finding was
just forcing the question to be asked while the answer is still
free to choose.

## F64 — The OpenBSD platform workflow: readiness and `exec`, agentless

> **Entered 2026-08-22** from a consuming project's proposal
> (testaferro's F23, which needs an OpenBSD guest binding and is
> blocked on exactly this). Demanded by **U12** (in force: an
> unattended install must end in a *usable* machine, but the
> codex's OpenBSD recipe currently ends in a machine no command can
> touch), **U14** (the caller needs detailed results, which on a
> second platform requires `exec` to work at all), and **P11**
> (today every guest command refuses to run against `openbsd`, with
> rule id `platform.verb-not-implemented`; that refusal is honest,
> but it also means the entire install produces nothing usable).
> This honors **P2**: nothing below depends on the guest cooperating.

> **A spike (spike 0) ran on 2026-08-22 and found the real blocker
> one layer below this entry: the QEMU backend launches
> `qemu-system-i386` for every machine**, regardless of platform
> (`backend_qemu.py`, `_QEMU_BIN`), so the codex's amd64 OpenBSD
> kernel crashes on load (a triple fault) and the machine reboot-loops
> — SeaBIOS, then iPXE, then CDBOOT, then a `boot>` prompt, roughly
> every 13 seconds. That's exactly what `openbsd-install`'s
> `wait "boot>"` step was matching, which is why the recipe had never
> actually completed. This isn't a bug in the script or in how the
> console mode is handled. **Launching the exact same disk and ISO
> with `qemu-system-x86_64` instead reaches the installer prompt in
> about 75 seconds**, and along the way, the boot log (dmesg) states
> the exact fact this entry is betting on: `wsdisplay0 at vga1 mux 1:
> console (80x25, vt100 emulation)`. **That first reading came from a
> framebuffer capture; reading the same moment from the text-memory
> plane instead reverses the conclusion** (this was measured after
> the binary fix, described below): the console is 80x25 text as far
> as the *guest* is concerned, but OpenBSD's `wscons` display driver
> attaches to `vga1` through a graphics aperture and draws through
> it, so Reliquary's usual VGA **text-memory** scrape freezes at the
> exact moment the kernel's startup banner ends, and never sees the
> installer prompt at all. The same machine, read instead over
> `control-planes: ["vnc"]`, reads perfectly through the fixed-font
> recognizer — the boot log, the prompt, and the cursor all come
> through correctly. So **the OpenBSD dialect has to run over the VNC
> plane**, which is just as agentless as the text-memory approach
> (satisfying P2) and is already delivered on QEMU (F63); the default
> agentless-display approach simply can't see this guest at all, so
> this entry's original assumption that it could read OpenBSD's
> console from text memory does not hold up. Two smaller findings
> from the same run: the recipe's `boot> a` step types the installer's
> autoinstall answer at the *boot loader* prompt, which reads it as a
> kernel filename (`cannot open cd0a:a`) and falls back to the
> default — the loader actually just wants `enter` pressed, and the
> `(A)utoinstall` answer belongs at the installer's own prompt
> instead; and the script header's default 30-second timeout applies
> to every `wait` step, including package-set extraction, so the
> slower steps need their own explicit `timeout=`. **A separate bug
> in how the emulator binary gets chosen is blocking this feature,
> but is not itself part of it**: it belongs in the task queue as its
> own fix, against the platform model AGENTS.md already describes,
> and every clause below is written assuming that bug is already
> fixed. Evidence for all this: a private home directory under this
> session's scratchpad, the failing `.rlqt` transcripts, and a
> screendump captured from the x86_64 run.

**What already exists, and what was unknown.** The codex already has
`openbsd` (7.9 amd64, 512M memory, a blank 4G disk), `openbsd-installer`
(the pinned installer ISO), and `openbsd-install` (an unattended
install driven over the run-scoped HTTP server, which answers root's
password, sets the hostname to `openbsd`, allows ssh, and installs
packages from `cd0`). The machine layer already creates and boots
it; the schema already allows this platform; the minimum memory is
already recorded. The unit-test tier pins the ISO's hash and the
seed data — but nothing on record actually confirmed the install had
ever completed for real. Spike 0 then measured that directly, rather
than just arguing about it (see above): it had not completed, and
the reason turned out to be the backend's hardcoded i386 binary
choice, not anything wrong with the recipe or the platform.

**Spike 0's second pass (2026-08-22, after fixing the binary choice):
the install actually completes.** With the correct system binary
launching, and the boot-loader step corrected, the codex recipe's own
answers carried a real unattended install all the way through to
`CONGRATULATIONS! Your OpenBSD install has been successfully
completed!` in about eleven minutes — served from the run-scoped HTTP
server, and read from the first screen to the last over
`control-planes: ["vnc"]`. **Whether the install itself works is no
longer an open question.** What this same run overturned instead was
this entry's original plan for how readiness should work (see
below): the spike kept the now-installed machine as its output (P20),
so the next round of work starts from a real, already-installed
OpenBSD guest instead of from a fresh 700 MB download.

**The plan is to reuse the transport Reliquary already has, and
that's the whole bet this entry makes.** OpenBSD amd64, booted by
BIOS on QEMU's `-vga std`, puts its console on `vga(4)` in text
mode — the `wscons` driver drawing an 80x25 VGA text screen — so
Reliquary's existing agentless plane applies unchanged: QMP's
`send-key` sends input, VGA text memory at address `0xb8000` reads
output, `screendump` captures pictures, and the VNC plane with the
fixed-font recognizer serves as an equally agentless fallback if the
console ever leaves text mode. This honors P2 without needing any new
transport mechanism — the only thing that differs per platform is the
dialect. **And spike 0 settled exactly which plane actually carries
that dialect** (see above): not the agentless display's text-memory
scrape, which OpenBSD's `wscons` leaves frozen at the boot banner, but
the **VNC plane**, where the fixed-font recognizer reads the console
exactly the way it already reads DOS. The font-recognition failure
this entry originally worried about never actually happens; but that
VNC plane is not Reliquary's default one, so every clause below
assumes `control-planes: ["vnc"]` is set, and a machine left on the
default plane simply can't see this guest's console at all, not just
more slowly.

**What varies per platform is the dialect, not the transport** — the
design document is
[design/platform-dialect.md](design/platform-dialect.md), which lays
out the dialect's shape, the rule for selecting one, the OpenBSD
clauses, the proof, and what got cut; what follows here is the
reasoning behind it. Today, `interaction_agentless.py` is written for
DOS from its very first constant (`_PROMPT_RE`, the `IF ERRORLEVEL`
probe, the "DOS prompt" wording in its narration), but its actual
loop — type a command, catch its echoed text, wait for the prompt to
reappear, wait a bit longer to be sure it's really settled (D111,
D112, D115), then slice out the relevant rows — is platform-neutral,
and is exactly what OpenBSD's `ksh` shell needs too. So the right fix
is to put a **platform dialect** behind the existing loop, not to
write a second loop:

- `platform_dos.py`, and a new `platform_openbsd.py`, would each
  supply the shape of the prompt, the way to check a command's
  outcome and what to look for, the readiness sequence, and the
  wording used in narration; the loop in `interaction_agentless.py`
  takes whichever dialect applies and says "prompt" in its messages
  where it currently says "DOS prompt".
- `_running_guest()` picks the dialect based on the machine's
  recorded `platform` field — which is always declared in the
  blueprint, never guessed (P10, see AGENTS.md's "Platform
  selection") — by looking it up in a registry of platforms that
  have a delivered workflow; `win9x` and `winnt` keep refusing to run
  commands, using the same rule id as today, which is exactly what
  P11 requires.
- The scripting language itself needs no changes: a script that says
  `platform openbsd` already parses correctly today, and whatever
  statement runs a command routes through the same dispatch code
  regardless of platform.

**The OpenBSD dialect, clause by clause:**

- **Prompt.** Root's default `ksh` prompt is `<hostname># `, which
  spike 0 confirmed against the actually-installed guest (it reads
  `openbsd#`); the shape to match is a row ending in `# ` or `$ `
  after some non-blank text, and D113's rule for a declared prompt
  still applies if a guest's `.profile` redraws it differently. The
  echo behavior is unchanged: the terminal echoes back the typed
  command where the prompt used to be. **One wrinkle the VNC plane
  adds**: the guest draws its own text cursor, so the recognizer
  reads that as a character cell, and the bottom row comes back as
  `openbsd# _`. Matching a shape anchored to the very end of the row
  therefore misses by that one extra character — this is a property
  of the VNC plane, not of this platform, so it needs to be fixed at
  that shared layer (see the design document's "the cursor is a
  glyph" section).
- **Outcome probe.** After each command, Reliquary sends
  `test $? -ne 0 && echo RLQ-EXEC-FAILED` as its own line — plain
  text that Reliquary writes and reads back, so this leaves G2 and
  P18 untouched, exactly as it works on DOS. One honest difference,
  stated here rather than hidden (per P11): the shell returns exit
  code 127 for a command it can't find, so the gap DOS has around
  mistyped commands (where `COMMAND.COM` leaves the error level
  unchanged) does **not** exist on OpenBSD. The same two rule ids
  apply either way.
- **Output.** Reliquary reads the rows between the echoed command and
  the returned prompt, one screen deep, with F14's limit still in
  force unchanged; the same value channels apply too — a guest
  program can write to a drive that the caller then reads back on the
  host (the exception carved out of P16), and OpenBSD mounts a vvfat
  virtual hard disk as `msdos` using `mount_msdos(8)`, which is what
  makes a directory-source drive usable from this guest without
  Reliquary ever reading its contents itself.
- **Readiness.** This is the one clause DOS never needed. DOS boots
  straight to a command prompt; OpenBSD boots to a `login:` prompt,
  and "ready to run commands" means having a logged-in shell. Two
  approaches were weighed: *have readiness log in itself* (`wait_ready`
  recognizes `login:`, types the username, then answers `Password:`
  using the property sources and the `credentials` module, per P13),
  or *have the recipe arrange for a shell to already be running* (by
  editing `/etc/ttys`' `ttyC0` line to run `/bin/ksh` directly, so the
  machine boots straight into a shell). The design round originally
  chose the second option, reasoning that the installer itself exits
  to a shell — but **spike 0's second pass proved that reasoning
  wrong: under an unattended (autoinstall) run, the installer never
  actually asks that question.** `Exit to (S)hell, (H)alt or (R)eboot`
  is a question only an *interactive* install gets asked, so the
  response-file line meant to answer it does nothing; instead, the
  install finishes, the machine reboots on its own, and the console
  comes up showing `OpenBSD/amd64 (openbsd.my.domain) (ttyC0)` at a
  `login:` prompt. No script ever holds open the installer's shell,
  so there's nothing there for the `/etc/ttys` edit to attach to.
  **Readiness therefore has to log in itself, and that's not just the
  fallback option — it's the only one that works.** This was measured
  by hand against the installed guest: `login:`, then the username,
  then `Password:`, then the password, then `openbsd#` — which
  confirms this entry's guess about the prompt's shape exactly. Two
  things follow from this. First, the **login credential is required
  from day one**, not something that can be deferred to a later piece
  of work, and it has to come through P13's credential sources, never
  as a plain blueprint field. Second, **exactly how the API exposes
  it is a question this entry leaves open** (a surface change under
  S2, and under S4 too if the machine document ever names the
  account): `wait_ready(user=, password=)` is the obvious shape, but
  it isn't settled here — that decision should start from D113's
  `prompt=` parameter, where the caller already declares what the
  guest displays.

**Surfaces touched** (looked up in SURFACES.md): **S2** and **S1** —
`exec`, `wait_ready`, and `check=` gain a second platform with the
same contract as DOS, and `wait_ready --prompt` there reads as the
shell prompt; **S6** — the codex recipe gets the boot-loader fix, and
the `openbsd` machine gains its `vnc` plane setting, with an
`openbsd-verify` command still owed as a sibling to `freedos-verify`;
**S4**, if the credential this login handshake needs ends up getting
a name in the machine document. **S3** and **S7** are unchanged:
no new statement and no new event gains a meaning. The specs in
`docs/spec/` for these commands currently say "DOS is the delivered
workflow," and will be updated once this is delivered.

**Out of scope, by deliberate choice:** ssh as a control plane — the
recipe already allows root login over ssh, but building a native
control plane for it belongs to **P3**'s roadmap and to F4's
territory, not to this entry; guest-file commands over ssh, for the
same reason; `win9x` and `winnt` (there's no recipe for them, and no
text console to build this approach on); any component installed
inside the guest; and the GUI era (F5).

**Proof this works.** An integration test, requested by name the same
way the DOS boot tests are. **Spike 0 is already done** — the install
completes for real, and what it found has been folded into the design
above. What's left to prove: a full boot, `wait_ready` completing the
login handshake, `exec "uname -a"` correctly reading back the kernel
version line, `exec "false", check=True` raising
`command.signalled-failure`, `exec "nosuch"` raising the same error,
a row slice that correctly excludes the boot's own output, and the
**existing agentless DOS test suite still passing byte-for-byte** —
adding this dialect must not shift a DOS reading by even one row. Per
P24: every touched surface gets tested using its own exact spelling.

**This is too large for one sprint, and where to cut it is clear.**
(a) Building the platform-dialect layer itself, moving DOS behind it
with the existing test suite unchanged; (b) the OpenBSD dialect
**including readiness**, the platform defaulting to the `vnc` plane,
and the recipe's boot-loader fix, all proven against the machine
spike 0 already installed. A third piece this entry used to carry —
the option of waiting "until a user's own OpenBSD use actually asks
for this" — **is gone, folded into piece (b)**: the measurement above
ruled out the alternative approach that would have avoided needing a
login step, and a dialect that can't even reach a shell prompt
without a login handshake can't be split apart from that handshake.
The spike no longer needs to happen before this gets pledged — it
has already run.

## Horizon — smaller and later

> **This is not a feature, so it has no number.** It's a holding
> list of items too small, or too vaguely defined, to be a feature
> yet. An item leaves this list either by being written up as a full
> feature — taking the next free F-number when that happens — or by
> moving to [TASKS.md](../TASKS.md) if it turns out to be ordinary
> small work instead.
>
> **The traceability rule (requiring a cited use case) does not apply
> to this list** (this was settled by the 2026-07-27 demand-citation
> sweep, which would otherwise have flagged four items here as
> violations). That rule only applies to *pledged* items and to design
> documents; a Horizon item is neither one, and something too
> undeveloped to be a real feature yet is also too undeveloped to know
> what demand it actually serves. Getting an actual citation is part
> of what it means to be written up as a feature — so an item on this
> list without one is the list working as intended, and re-running
> that sweep should never flag one.

- Machine mobility: cloning, exporting, and importing machines. This
  was the former milestone 12 (the number that guest agents later
  inherited in the same-day renumbering), moved to this list on
  2026-07-23 for lack of use-case backing: cloning has no use case at
  all behind it, exporting is backed only by the draft use case U8,
  and importing's U2 loses its scheduled delivery date by this move.
  Putting it back on the numbered milestones means pledging those use
  cases. The designs themselves are still settled (owner, 2026-07-22),
  and the worked-out text for them can be found with
  `git show cf56a0c:docs/spec/cli.md` — the last commit before the CLI
  spec was made normative and had its not-yet-built commands removed
  from it (2026-07-27; a spec should only state what actually exists).
  That text covers: `export-drive` / `export-machine`, using
  vocabulary decoupled from any specific exporter; `import-vm`, with
  its points where the user must consent; and `clone-machine`, as a
  machine snapshot. The open questions for `import-vm`'s scope
  (translating NIC and device settings, handling settings that can't
  be translated, and named-snapshot targets) still need deciding when
  this work resumes. Exporting to a portable file format only becomes
  meaningful once a second backend exists — so this should be
  scheduled at or after that second backend lands.
- **Host portability: running Reliquary itself on Linux and macOS**
  (added 2026-07-23, owner). Windows is the only host platform
  actually delivered today — the only one developed on, tested on, and
  claimed in the packaging metadata (AGENTS.md "Dependencies and
  style"). The host-side code is written to be portable, and the other
  code paths exist, but under P11, an untested path can't be claimed
  as supported. Widening support is gated on three substantial jobs,
  none of which happen automatically as a side effect of ordinary
  work:
  1. **Verifying secret storage on each host** — the credential-store
     capability, tested against the Secret Service provider on Linux
     and Keychain on macOS. The `keyring` integration
     (../design/script-properties.md, "Secret storage") was already
     built with this in mind, so the code is likely already correct;
     what's missing is *proof it actually works*, and the rule against
     falling back to plaintext storage means a wrong guess here would
     make a user's run fail outright.
  2. **Verifying the backend on each host** — QEMU discovery, process
     ownership, file paths, and the agentless display plane all need
     to be proven working on each host, not just assumed to work
     because they work on Windows.
  3. **Somewhere to actually run these tests** — either CI or real
     hardware. Every claim above depends on a test suite actually
     running there; the draft use case U18 is the case for reaching
     such a host from this one, which would let Reliquary provide its
     own test environment.
  No demand is currently cited for this: no use case asks to *run
  Reliquary itself on* a non-Windows host — U18 asks about reaching a
  different OS as a *guest*, which is a separate question. Scheduling
  this host-portability work means pledging whichever use case ends up
  asking for it.
- `fork-blueprint` (a convenience for quickly forking a blueprint
  without further ceremony; `new-blueprint`'s scaffolding already
  lands in milestone 6) — currently has no justification: no use case
  demands it, and `seed-blueprint` already covers the
  seed-and-customize workflow it would be used for.
- `diff-blueprint <name>` — diff a user's blueprint against the codex
  blueprint of the same name (moved here from [TASKS.md](../TASKS.md)
  by the 2026-07-27 gate audit). Currently has no justification: no
  use case demands it. It's on this list rather than written up as a
  feature because there's only one line of intent behind it so far,
  and it's here rather than in the task queue because it would add a
  new CLI command.
- Bounded `guest-file-*` operations reachable through a native guest
  agent — as their own distinct commands, never bundled together into
  a generic console abstraction.
- Media commands beyond `fetch-media`, namely `verify` and `remove` —
  **split apart by D46** (2026-07-27), which put U13 into force:
  `verify` is now backed by an in-force use case ("verifies it is
  exactly the build the scripts target"), so the lack-of-demand
  objection to it is gone, and what's left to decide is only whether a
  standalone `verify` command is worth adding alongside the
  verification `fetch-media` already does. `remove` still has no
  demand behind it at all, and stays unjustified.
- A `pytest-reliquary` plugin (following the prior-art guidance in
  AGENTS.md) — currently has no justification: at best it's adjacent
  to the draft use cases U14 and U15, and test-framework-specific
  behavior belongs to the projects that consume Reliquary, not to
  Reliquary itself (the boundary the project's rules draw here).

## F39 — The machine-variable channel, both directions

> **No demand is currently known for this — and this entry says so
> up front** (owner, 2026-08-01). No use case asks for it, and none
> is even drafted yet; the owner suspects one eventually will, and
> this entry holds the design questions ready so the argument can be
> made quickly when it does. Nothing here is being worked on, and
> this proposal in particular can't even be argued for pledging until
> a demand shows up. Where this came from: the removal of the
> `Session.set_machine_var` method, which conflicted with cli.md's
> rule that "the host side only reads" machine variables. This entry
> is the capability that method was reaching for, now argued for
> properly instead of just showing up unannounced as a stray method.

**The idea.** Machine variables would flow from host to script, not
just from script to host as they do today: an orchestrating process
sets a value mid-run (via `set-machine-var`, with an API twin
`set_machine_var`), and the running script reads it or waits on it.
The motivating use case is a trigger: a long-running script pauses at
a wait step until some other process sends the signal to continue.

**The open design questions**, written down now so the eventual
design round starts with a head start:

- **This needs to be two separate one-way channels, never one shared
  map.** Variables set by the guest are the existing report channel,
  and must stay read-only from the host's side — "a value is exactly
  what this boot actually produced" is a guarantee about where the
  data came from, and a host that could write into that same
  namespace could forge a guest's reports. Host-set variables need
  their own separate namespace or map, invisible to whatever reads
  the guest's reports. Any symmetry here is in how the two channels
  work, never in sharing the same storage.
- **Reading the value from the script side is cheap; deciding the
  language surface for it is the hard part.** The runner already runs
  on the host, so reading a value out of the state document is
  trivial — but adding a wait mechanism or a way to interpolate the
  value into a script is a change to the scripting language itself,
  governed by the language's design goals and its V-numbered rules,
  and that's really what the eventual design round is about.
- **P19 constrains this.** Data specific to one run must never choose
  which branch, phase, or path a script takes. A host-sent signal is
  allowed to *gate* progress — that's what a wait step already does —
  but a value that picks between different paths is already
  disallowed, and this design must not accidentally become the
  flag-passing channel that P19 exists to prevent.
- **Right now, script properties are all bound once, deliberately, at
  the start.** Today a run is entirely a function of the inputs it was
  bound with — both the dry-run plan and the run record depend on
  that being true. A value supplied by the host mid-run would make
  outcomes depend on timing. Screen-based waits already introduce some
  timing dependence, but a full value channel is a bigger change than
  a simple go/no-go signal, and the eventual design round needs to
  either price out that bigger cost or scale this down to just a
  signal.
- **P6 requires every part of this to ship together**: the CLI
  command, its API twin, and the script-side read-or-wait mechanism
  all need to land in one single change, with the command manifest
  gaining the capability in that same commit.
- **The current rule in cli.md is the thing standing in the way.**
  "Writing is the script verb's, and the host side only reads" is in
  force today; this proposal is effectively an argued amendment to
  that rule, and it can only land through the process for changing a
  public surface (P23) — never by quietly showing up unannounced the
  way `set_machine_var` originally did.


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
