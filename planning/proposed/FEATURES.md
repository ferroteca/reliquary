<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Proposed features

Large unbuilt capabilities — each a milestone's worth of work,
**design settled and intact**, waiting on the demand that schedules
it. Nothing here is worked ([README.md](../README.md)); the move to
[accepted/FEATURES.md](../accepted/FEATURES.md) is the acceptance,
and the commit that makes it is the record.

F2–F6 left the numbered arc for the same reason (D33, owner,
2026-07-23): **no in-force or accepted use case demands it**. The
numbered arc ran 1 through 9 and ended there, carrying text-mode
DOS on QEMU end to end; generalizing beyond that one vertical is
what waits here. Each names the drafted use case that would schedule
it — accepting that case is what returns the feature to a numbered
arc.

**F7–F10 never were on the arc.** They are governance and tooling
proposals moved out of TASKS.md's legacy Proposed section (D43), and
they cite **principles** rather than use cases, which drive work
just as well. What they share with the rest is the only thing that
matters here: argued, unaccepted, and not worked from.

A feature that is accepted but not yet built moves to
[accepted/FEATURES.md](../accepted/FEATURES.md) and carries its work
breakdown with it. Small work that is not a feature at all goes
straight to [TASKS.md](../TASKS.md).

Each feature carries an **F-number** (D42; the rules are in
[README.md](../README.md)). **Size is no bar to sitting here** — the
sprint bound bites at acceptance, so every entry below is many
sprints of work, and the "milestone's worth of work" above describes
what these entries *are* rather than a size any may be accepted at.
Cutting one into implementable pieces is part of accepting it.

## F2 — The backend adapter seam

> **Dropped from the numbered arc to the backlog** (owner,
> 2026-07-23): the former Milestone 10, not yet scheduled — the
> multi-backend pillar has no in-force use case demanding it.
> Its demand is the U7 draft
> ([proposed/USE-CASES.md](USE-CASES.md),
> "materialize on the hypervisor the host provides"); accepting
> U7 is what schedules this work back onto the arc, the citing
> item the record. The design is settled and stands as written.

Extract the adapter API from the now-complete QEMU implementation
— the only adapter with a full control plane set — so the seam is
defined by working code, not speculation. The seam's doctrine is
pre-settled in
[design/backend-adapter.md](design/backend-adapter.md)
(layering, seam inventory, ownership and capability doctrines,
extraction map); this milestone defines the signatures and records
them there.

Decide first:

- The backend priority order for default assignment when a
  blueprint names no backend (proposed: QEMU, VirtualBox, VMware
  Workstation, Hyper-V — best scriptability first).

Deliverables:

1. The adapter API: lifecycle, media attachment, input, screen
   access, and control plane endpoints, with honest per-backend
   capability reporting feeding the existing capability checks.
2. Backend autodiscovery (binaries on PATH and conventional
   locations, the Hyper-V service/module) establishing
   availability only.
3. Real default assignment from the prioritized availability
   list, recorded permanently into machine state; a declared
   `backend` pins the choice and fails closed if unavailable or
   incapable.
4. Stub adapters for VirtualBox, VMware Workstation, and Hyper-V
   raising `NotImplementedError`, mirroring platform handling.
5. Generalized ownership verification: no adapter sends a control
   command to a hypervisor object that doesn't match the
   machine's recorded `backend-id`.

Done when: all QEMU interaction flows through the adapter API and
the FreeDOS install script passes unchanged.

## F3 — Second backend: VirtualBox

> **Dropped from the numbered arc to the backlog** (owner,
> 2026-07-23): the former Milestone 11, not yet scheduled on the
> same ground as the seam extraction above — U7 is its demand
> too, and it follows that extraction whenever the pair returns.

The first non-QEMU adapter end to end, proving the adapter API
against a genuinely different hypervisor. VirtualBox is the
candidate: `VBoxManage` covers lifecycle, keyboard scancodes,
screenshots, and serial redirection — the closest match to the
control plane set scripts already rely on.

Deliverables:

1. Lifecycle through `VBoxManage`, with machine files kept inside
   `cache/machines/<id>/` and VDI/differencing materialization
   of the drive triad.
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
> not yet scheduled. No use case demands it: U3's first-class
> demands (granular results, selective re-run) are met by
> milestones 8–9, and the guest-agent plane is that case's
> stated *preference*, not its requirement — its loop runs
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

The arc's endpoint: GUI installer automation, carried by the
VNC/RFB control plane where backends provide it — QEMU natively,
VirtualBox with the extension pack, VMware Workstation — and the
two remaining adapters: VMware Workstation, then Hyper-V,
deliberately last. Hyper-V has no VNC (a capability failure,
never an emulation), so it is the proof that GUI automation
rides capabilities, not one wire.

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
  AGENTS.md prior art for the licensing boundary).
- Blueprint device growth: firmware/boot semantics (BIOS vs
  UEFI) for post-DOS platforms, and when network, display
  adapter, audio, and USB become first-class blueprint fields
  (each following the drives pattern: agnostic vocabulary,
  capability-checked per backend); per-platform controller
  defaults beyond `ide`; whether slot ranges widen for
  multi-device controllers (additive change); and how Hyper-V
  generations surface (a backend setting vs. inferred from
  declared capabilities).
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
> No in-force or accepted use case demands it: the feedback split
> (P5) is satisfied by the run's own driver watching it live, and
> detaching a run or following it from a process that did not
> start it is a separable capability no case writes down. Its
> demand is the U19 draft
> ([proposed/USE-CASES.md](USE-CASES.md),
> "start a long run and follow it from elsewhere"); accepting
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

## F7 — Audit design documents against accepted demand

> **Moved here from TASKS.md's legacy Proposed section** (owner,
> 2026-07-26): argued but never approved, and a proposal belongs under
> `proposed/`. Demanded by **P8** (interface and principle changes are
> vetted): the audit checks that a design exists only where demand
> does. No use case asks for it.

**Audit design documents against accepted demand.** Raised
unprompted during the 2026-07-24 traceability audit rather than
requested, so it waits here. Findings that motivate it are
recorded with the audit tasks under Governance in
[Accepted](#accepted).

Raised unprompted during the audit — a suggestion, not a request.

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
decision carries supports or that delivered work cites accepted
demand. Today those are checked by whoever happens to grep,
which is exactly how U9 and U12 went unnoticed through the
milestone that delivered them.
EACH CHECK EARNED ITS PLACE — the 2026-07-24 hand audit found a
real violation of every one:
* every planning section cites a U/P/G demand — *12 of 34 sections
  in the then-current roadmap cited none*;
* every DECISIONS entry carries supports — *22 lack them, and
  D29 sat outside the range the existing task assumed*;
* no *delivered* work cites *unaccepted* demand — *U9 and U12*,
  the sharpest defect of the set, and the one a linter would
  have caught the day milestone 9 landed;
* every design document's subject has accepted demand — *three
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
vision statement (a use case, principle, or interface) is
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
[docs/spec/api.md](../docs/spec/api.md): code-as-norm would
invert P8 — an unargued code change would *redefine* the
interface rather than violate it — and the project has already
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

## Horizon — smaller and later

> **Not a feature, and so unnumbered.** This is a holding list of
> items too small or too unformed to be one. An item leaves it by
> being written up as a feature — taking the next free F-number
> then — or by going to [TASKS.md](../TASKS.md) if it turns out to
> be ordinary small work.

- Machine mobility: clone, export, import — the former
  milestone 12 (the number guest agents inherited in the
  same-day renumber), moved here 2026-07-23 for lack of
  use-case
  backing: clone has no use case at all, export's stands only
  as the U8 draft, and import's U2 loses its scheduled
  delivery with this move. Scheduling it back onto the
  numbered arc is the acceptance of those use cases. The
  designs stay settled ([design/cli.md](../../docs/spec/cli.md); owner,
  2026-07-22):
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
  a different axis. Sequencing it is the acceptance of whatever
  case does.
- `fork-blueprint` (a fire-and-forget authoring convenience;
  `new-blueprint` scaffolding lands in milestone 6) —
  currently unjustified: no use case demands it, and
  `seed-blueprint` already serves the seed-and-customize seam.
- Bounded `guest-file-*` operations through a native guest
  agent — distinct verbs, never bundled into a console
  abstraction.
- In-band file operations against a stopped machine's drives —
  the deferred half of the dropped run-collection model (owner,
  2026-07-22). Rough shape, its own design round before it
  lands: the CLI/API triple `list-files` / `get-files` /
  `put-files` (twins `list_files` / `get_files` / `put_files`),
  addressing `<drive-key>:<path>`; `size`/`base` images reached
  through the adapter's at-rest filesystem access, `hostdir`
  directories directly; capability-honest per call — a drive
  whose filesystem the adapter cannot read fails by name;
  `media` drives excluded; directories recursive; no record
  custody — files land where the caller says (details such as
  `get-files`' destination default are that round's to settle).
  Value concentrates where out-of-band access thins — non-QEMU
  backends (no `hostdir`) and non-FAT guest filesystems — so
  sequence at or soon after the second backend (backlog).
- Media commands beyond `fetch-media` (verify, remove) —
  currently unjustified: no use case demands them; `verify`
  would stand on the U13 draft if accepted.
- A `pytest-reliquary` plugin (per AGENTS.md prior art) —
  currently unjustified: adjacent to the U14/U15 drafts at
  best, and test-framework semantics belong to consumers (the
  doctrine boundary).
