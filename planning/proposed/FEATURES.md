<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Proposed features

Large unbuilt capabilities — each a milestone's worth of work,
**design settled and intact**, waiting on the demand that schedules
it. Nothing here is worked ([README.md](../README.md)); the move to
[pledged/FEATURES.md](../pledged/FEATURES.md) is the pledge,
and the commit that makes it is the record. An entry here takes
its F-number from the sequence ledger
([SEQUENCES.md](../SEQUENCES.md)) — issue from there and advance
the mark in the same edit.

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
> design, which stands as written; D61 records how the pledge
> arrived without anyone making it.
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
([design/recorder.md](design/recorder.md)). That plane's screen-and-keyboard
half is delivered on QEMU (F63) — and the viewer additionally needs
the pointer input and interactive display still with the GUI era
(**F5**). This entry's former sequencing note claimed a
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
> **The demand adjudication closed 2026-08-21** (D110): **U5**'s
> customized-installation remainder is pledged
> ([../pledged/USE-CASES.md](../pledged/USE-CASES.md)) and
> underwrites the GUI half — the plane, pointer input, landmarks,
> the platform workflows — while **U7** already reached the last
> two adapters (D65). In the same act the first cut left this
> entry: **F63**, the VNC control plane on QEMU, screen and
> keyboard — since **delivered** — this entry keeping its number
> and the remainder under D110's cut ruling. Every deliverable below now stands on pledged
> demand and stays here until pledged — a pledged use case makes
> a feature pledgeable and pledges nothing itself (D65).
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

- The GUI asset spec: **designed in full** (owner rounds,
  2026-07-21 and 2026-08-24 —
  [design/landmarks.md](design/landmarks.md)): the `.rlql` JSON5
  schema (stem-identified, dimensions-only pinning — the mode
  half dropped as unverifiable), the similarity metric
  (pixel-equal fraction, per-region judgment), and reference
  placement — `@name` in every screen-condition position; this
  bullet used to say "landmark-block placement within a script",
  a phrase from before D12 deleted the embedded block.
- Pointer input end to end: **designed** (owner round,
  2026-08-24 — [design/pointer-input.md](design/pointer-input.md)):
  the seam is one carrier method in RFB's `PointerEvent` shape
  (the entry's three primitives collapse into it, key events
  already delivered), composition and pacing control-plane-owned
  above it; `pointing-device` (`tablet` / `mouse`) as a
  first-class machine field under P25's cleared gate, pointer
  verbs refusing a relative-only machine at preflight; and
  `click` as the fifth guest-input verb — observation-bearing
  like `select`, `spot=` with a lone-spot default,
  left-single-click as the whole first cut. Still open here: a
  host-side landmark-cropping convenience (a CLI subcommand,
  never a service). Era note: DOS/9x-era setup GUIs are fixed-mode,
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
- Blueprint device growth: **designed** (owner round,
  2026-08-24 —
  [design/device-growth.md](design/device-growth.md)), and the
  round's product is dispositions, not fields — P25's two gates
  (demand necessary, multi-backend applicability) applied per
  item, each refusal its own argument. Network: host-reachability
  stays derived from the script's `http` block, generalized per
  backend, the NIC model a per-platform default — a first-class
  field waits for machine-shaped demand, and then carries
  attachment vocabulary, never card names. Firmware:
  `bios`/`uefi` designed in full (platform defaults, NVRAM
  varstore residency), admission deferred to the first platform
  needing `uefi`. Display adapter: refused on applicability,
  permanently behind `backend-settings`. Audio: refused on
  demand. USB: a controller is always implied by the device that
  needs it, never a field. Controller defaults go
  per-(platform, medium) by the arrival rule; slot ranges widen
  per controller type at that type's admission (additive, as
  this entry already held); Hyper-V generation is derived —
  `bios` → Gen1, `uefi` → Gen2 — never a pin.
  **A second controller type leaves no declared first disk.**
  Slot order is authoritative only within a type; across types the
  guest's firmware decides how the controllers themselves
  enumerate. That was a live constraint while Reliquary mapped
  drives to guest letters, and **D108 retired the mapping**, so
  what remains is narrower and still real: any future answer about
  which disk a guest sees first is a fact no declaration supplies,
  and P10 forbids guessing at one. Boot order is the exception
  that already works, being stated to the firmware rather than
  read back from it.
- The Hyper-V agentless screen strategy: whether WMI
  thumbnail/keyboard automation is good enough for installer
  scripting, or Hyper-V machines require the serial/agent
  control planes from day one.

Deliverables:

1. The VNC control plane beyond **F63**'s delivered QEMU cut: the
   VirtualBox (extension pack) and VMware Workstation endpoint
   configuration behind the same plane, pointer events over the
   in-tree RFB client (the client, framebuffer capture and key
   events are delivered — `src/reliquary/rfb.py` and the QEMU
   adapter's VNC carriers; the adjudicated calls are D110),
   and the capability error naming Hyper-V where the plane cannot
   exist.
2. Pointer input per
   [design/pointer-input.md](design/pointer-input.md): the
   `pointer_event` carrier method, the `pointing-device` machine
   field, and the `click` verb, with pacing and composition
   control-plane-owned.
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

Done when: a GUI-era install script drives a setup end to end
through landmarks on QEMU over VNC and on Hyper-V through its
decided screen strategy. (The FreeDOS-unmodified-over-VNC
criterion, with recognition matching the VGA scrape, went with
F63 as its done-when.)

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
  known ([F5](#f5--the-gui-era-vnc-gui-scripting-and-the-last-backends),
  closed 2026-08-21 by D110, and `backend-adapter.md`, closed
  2026-07-28). The improvement is not
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
program writing its long output to a drive the caller reads on the
host, which Reliquary supplies without reading a byte of it (P18,
and P16's file-content carve-out since D108). If that is the answer,
this entry shrinks to (1) and stops being a feature; if it is not,
the argument for why belongs here before any work starts.

## F15 — Host-directory attachment as a first-class operation

> **Entered 2026-07-27** from a consuming project's proposal
> (owner: admitted as a proposal). Demanded by **P16**, in force,
> because the capability is reached today only by a caller
> reproducing Reliquary's internal model outside it. Serves
> **U14** and **U20**, and **D108 raised its value rather than
> lowering it**: with the in-band file family gone, a
> directory-source drive is one of the two routes Reliquary
> supplies for a file to cross at all, so the arithmetic this verb
> hides is arithmetic every consumer now does. **What it answers
> with changed in the same act.** The guest-terms address the
> original entry promised no longer exists — there is no letter
> map — so the answer is the **drive key** the attachment took,
> which is what `insert-media`, `eject-media` and `set-boot-order`
> already speak and what a blueprint already writes. A demand for
> the letter back is a demand for the mapping back, and is
> argued as that.

A caller that needs a host directory visible to a guest **synthesizes
a directory-source drive into the blueprint**, which forces it to
know slot keys and slot limits — pieces of Reliquary's model
reproduced outside Reliquary in order to reach a capability
Reliquary supports. "Attach this host directory, and tell me the
drive it landed on" deletes both.

CONSTRAINTS ALREADY SETTLED, which shape the verb rather than block
it. QEMU snapshots a vvfat staging directory when the drive is
attached, so a host-side change needs a stop/start cycle — this is a
**stopped-machine** operation, and the live-iteration path stays
U20's `insert-media` over a running machine. Slot limits and the
directory-on-cdrom refusal stay exactly as they are: the verb hides
the arithmetic, never the rules. What the guest calls the drive is
the guest's business and Reliquary states nothing about it.

DECIDE FIRST: whether the attachment is **state or request** — a
persisted machine-state mutation in the family of `insert_media` /
`set_boot_order`, or a per-call convenience that composes a blueprint
edit. The first survives a stop/start and shows up in `machine.json`;
the second leaves the blueprint the only durable statement of what a
machine has. The answer decides whether this is one verb or a verb
and its inverse.

## F16 — The public surface a caller copies today

> **Entered 2026-07-27** from a consuming project's proposal
> (owner: admitted as a proposal). Two small exposures with one
> shared argument: each is Reliquary's own knowledge, reproduced
> outside Reliquary because the public surface does not carry it.
> **They are small but they are not housekeeping** — both add
> to the embedding API, which the housekeeping boundary excludes
> absolutely ([SURFACES.md](../SURFACES.md)). **That is not why
> they sit here rather than in [TASKS.md](../TASKS.md)**, and this
> entry is where that misreading began: the boundary is
> housekeeping's alone, and a small surface change may be a task
> (D45, which the 2026-07-27 gate audit cited this very sentence as
> precedent for before the reading was caught). What holds them
> here is that both are **unsettled below** — item 1
> asks which artifact owns the answer, item 2 is probably F2's work
> rather than its own. Serves **U14**; item 2 belongs to **F2**.
> **A third item died with D108**: the public drive-address query,
> which asked for `platform_dos.drive_letters` on the import
> surface so a caller need not copy the letter rule. There is no
> letter rule to copy any more, and nothing is owed in its place.

1. **Public topology limits.** Slot counts per medium
   (`_SLOT_LIMITS`), so a caller building a blueprint
   programmatically stops carrying its own copied `4`. Blueprint-model
   truth, and arguably the published schema's job rather than the
   API's — settle which before adding a function.
2. **A backend-agnostic availability check.** `backend_available()`
   rather than `find_qemu()`, so a caller gating integration tests
   never has to name an emulator to ask a backend-neutral question.
   Lowest priority of the two, and **probably not its own work**:
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

## F64 — The OpenBSD platform workflow: readiness and `exec`, agentless

> **Entered 2026-08-22** from a consuming project's proposal
> (testaferro's F23, an OpenBSD guest binding — blocked on exactly
> this). Demanded by **U12** (in force: an unattended install ending
> in a *usable* machine — the codex's OpenBSD recipe ends in one no
> verb can touch), **U14** (granular results reaching the caller,
> which on a second platform needs `exec` at all), and **P11**
> (today every guest verb refuses `openbsd` by rule id
> `platform.verb-not-implemented`; that is honest, and it is also
> the install's whole product being inert). Honours **P2**: nothing
> below depends on guest cooperation.

> **Spike 0 ran, 2026-08-22, and found the blocker one layer below
> this entry: the QEMU backend launches `qemu-system-i386` for every
> machine** (`backend_qemu.py`, `_QEMU_BIN`), so the codex's amd64
> kernel triple-faults on load and the machine reboot-loops —
> SeaBIOS → iPXE → CDBOOT → `boot>` about every 13 seconds, which is
> what `openbsd-install`'s `wait "boot>"` was matching and why the
> recipe has never completed. It is not a script defect and not a
> console-mode one. **The same disk and ISO driven by
> `qemu-system-x86_64` reach the installer prompt in about 75
> seconds**, and the dmesg on the way names the fact this entry
> bets on: `wsdisplay0 at vga1 mux 1: console (80x25, vt100
> emulation)`. **That reading was taken off a framebuffer capture,
> and taking it off the text plane instead reverses the conclusion**
> (measured after the fix, below): the console is 80×25 text to the
> *guest*, but wscons attaches `vga1` with an aperture and paints
> through it, so reliquary's VGA **text-memory** scrape freezes at
> the moment the kernel banner ends and never sees the installer
> prompt at all. The same machine on `control-planes: ["vnc"]` reads
> perfectly through the fixed-font recognizer — dmesg, prompt and
> cursor. So **the OpenBSD dialect runs on the VNC plane**, which is
> equally agentless (P2) and already delivered on QEMU (F63); the
> agentless-display default is blind to this guest and the entry's
> text-memory assumption does not survive. Two lesser findings, from
> the same run: the recipe's
> `boot> a` types the installer's answer at the *boot loader*, which
> reads it as a kernel name (`cannot open cd0a:a`) and falls back —
> the loader wants `enter` and the `(A)utoinstall` answer belongs at
> the installer's own prompt; and the header's 30-second default
> reaches every `wait`, including the set extraction, so the long
> ones need their own `timeout=`. **A binary-selection defect blocks
> this feature and is not part of it**: it belongs in the queue as
> its own work, against the platform model AGENTS.md already states,
> and every clause below is written as if it were fixed. Evidence:
> a private home under this session's scratchpad, the failing
> `.rlqt` transcripts, and the x86_64 screendump.

**What exists, and what is unknown.** The codex holds `openbsd`
(7.9 amd64, 512M, a 4G blank), `openbsd-installer` (the pinned
ISO) and `openbsd-install` (autoinstall over the run-scoped HTTP
server, answering root's password, hostname `openbsd`, ssh allowed,
sets from `cd0`). The machine layer materializes and boots it; the
schema admits the platform; the memory floor is recorded. The unit
tier pins the ISO hash and the seed closure — and nothing on record
said the install had ever completed for real, which spike 0 then
measured rather than argued (above): it has not, and the reason is
the backend's hardcoded i386 binary rather than anything in the
recipe or the platform.

**Spike 0, second pass (2026-08-22, after the architecture fix): the
install completes.** With the right system binary launching and the
loader step corrected, the codex recipe's own answers carried a real
autoinstall through to `CONGRATULATIONS! Your OpenBSD install has
been successfully completed!` in about eleven minutes — served from
the run-scoped HTTP server, read from first screen to last over
`control-planes: ["vnc"]`. **The install is no longer the unknown.**
What the same run overturned is the readiness route this entry had
settled (below): the installed machine is kept as the spike's
product (P20), so the next round starts against a real OpenBSD guest
rather than a 700 MB download.

**The transport is the one already built, and that is the whole
bet.** OpenBSD amd64 booted by BIOS on QEMU's `-vga std` takes its
console on `vga(4)` in text mode — wscons over an 80×25 VGA text
screen — so the agentless plane applies unchanged: QMP `send-key`
in, text memory at `0xb8000` out, `screendump` for pictures, the
VNC plane with the fixed-font recognizer as the equally agentless
fallback should the console ever leave text mode. P2 is honoured
with no new carrier, and the dialect is the only thing that
differs — **and spike 0 settled which plane carries it** (above):
not the agentless display's text-memory scrape, which OpenBSD's
wscons leaves frozen at the boot banner, but the **VNC plane**,
where the fixed-font recognizer reads the console exactly as it
reads DOS. The font-recognition stop this entry feared is not in
play; the plane, however, is not the default one, so every clause
below reads over `control-planes: ["vnc"]` and a machine left on the
default plane is blind rather than merely slower.

**What a platform owns is a dialect, not a transport** — the
design is [design/platform-dialect.md](design/platform-dialect.md),
which carries the dialect's shape, the selection rule, the OpenBSD
clauses, the proof and the cut; what follows is the argument. Today
`interaction_agentless.py` is DOS from its first constant
(`_PROMPT_RE`, the `IF ERRORLEVEL` probe, the "DOS prompt"
narration) while its loop — type, catch the echo, wait for the
prompt to come back, settle before believing it (D111, D112,
D115), slice the rows — is platform-neutral and is exactly what
OpenBSD's `ksh` needs too. The seam is therefore a **platform
dialect** behind the existing loop, not a second loop:

- `platform_dos.py` and a new `platform_openbsd.py` each supply
  the prompt shape, the outcome probe and its sentinel, the
  readiness sequence, and the narration words; the loop in
  `interaction_agentless.py` takes a dialect and says "prompt"
  where it now says "DOS prompt".
- `_running_guest()` selects the dialect from the machine's
  recorded `platform` — blueprint-declared, never inferred (P10,
  AGENTS.md "Platform selection") — through a registry of the
  platforms with a delivered workflow; `win9x` and `winnt` keep
  refusing by the same rule id, which is P11 doing its job.
- The scripting language needs nothing new: a `platform openbsd`
  script already parses, and whatever statement drives a command
  routes through the same dispatch.

**The OpenBSD dialect, clause by clause:**

- **Prompt.** Root's default `ksh` prompt is `<hostname># `,
  confirmed by spike 0 against the installed guest (`openbsd#`);
  the shape is a row ending in `# ` or `$ ` after a non-blank head,
  and D113's declared-prompt door carries over for a guest whose
  `.profile` redrew it. The echo discipline is unchanged: the tty
  echoes the typed line where the prompt was. **One wrinkle the VNC
  plane adds**: the guest draws its own cursor, so the recognizer
  reads it as a cell and the bottom row comes back `openbsd# _`. A
  shape anchored at the end of the row misses by that one
  character — a property of the plane rather than of this platform,
  so it is the seam's to settle (the design, "the cursor is a
  glyph").
- **Outcome probe.** `test $? -ne 0 && echo RLQ-EXEC-FAILED` as
  its own line — text reliquary composed and reads back, so G2
  and P18 are untouched exactly as on DOS. One honest difference,
  stated rather than hidden (P11): the shell returns 127 for a
  command it could not find, so the mistyped-command gap the DOS
  probe has (`COMMAND.COM` leaves ERRORLEVEL alone) does **not**
  exist here. The rule ids are the same two.
- **Output.** The rows between the echo and the returned prompt,
  one screen deep, with F14's limit in force unchanged; the value
  channels are the same too — a guest program writes to a drive
  and the caller reads it on the host (P16's carve-out), and
  OpenBSD mounts a vvfat hard disk as `msdos` through
  `mount_msdos(8)`, which is what makes a directory-source media
  usable from this guest without reliquary reading a byte.
- **Readiness.** The one clause DOS never had. DOS boots to a
  prompt; OpenBSD boots to `login:`, and "ready for commands"
  means a shell. Two routes were weighed — *readiness logs in*
  (`wait_ready` recognizes `login:`, types the user, answers
  `Password:` from the property sources and the `credentials`
  module, P13) and *the recipe arranges a prompt* (`/etc/ttys`'
  `ttyC0` line running `/bin/ksh`, so the machine boots to one).
  The design round chose the second, by the installer's own exit to
  a shell — and **spike 0's second pass refuted it: under
  autoinstall the installer never asks.** `Exit to (S)hell, (H)alt
  or (R)eboot` is an *interactive* install's question, so the
  response-file line answering it is inert; the install ends, the
  machine reboots on its own, and the console comes up
  `OpenBSD/amd64 (openbsd.my.domain) (ttyC0)` at `login:`. No
  script ever holds the installer's shell, so nothing is left for
  the `sed` to ride. **Readiness therefore logs in, and it is not
  the later general mechanism but the only one** — measured by hand
  against the installed guest: `login:` → the user → `Password:` →
  the secret → `openbsd#`, which confirms this entry's guess at the
  prompt shape exactly. Two things follow. The **credential is
  load-bearing from the first delivery** rather than deferred with
  a later piece, through P13's sources and never a blueprint field.
  And **what the API carries it as is a surface question this entry
  leaves open** (S2, and S4 if the machine document ever names the
  account): `wait_ready(user=, password=)` is the obvious shape and
  is not settled here — D113's `prompt=`, where the caller declares
  what the guest draws, is where that round starts.

**Surfaces touched** (SURFACES.md, by lookup): **S2** and **S1** —
`exec`, `wait_ready` and `check=` gain a second platform with the
same contract, and `wait_ready --prompt` reads as the shell prompt
there; **S6** — the codex recipe takes the loader-step fix and the
`openbsd` machine gains its `vnc` plane, with an `openbsd-verify`
sibling of `freedos-verify` owed beside them; **S4** if the
credential the login handshake needs takes a name in the machine
document. **S3** and **S7** are unchanged: no statement and no
event gains a meaning. The norms in `docs/spec/` for the verbs say
"DOS is the delivered workflow" and are amended with the delivery.

**Out of scope, by the cut:** ssh as a control plane — the recipe
already allows root over ssh, and a native plane is **P3**'s arc
and F4's territory, not this entry's; guest-file verbs over it for
the same reason; `win9x` and `winnt` (no recipe, no text console
to bet on); any in-guest component; and the GUI era (F5).

**Proof.** Integration, asked for by name as the DOS boots are.
**Spike 0 is done** — the install completes for real, and what it
measured is folded above and into the design. What remains: a boot,
`wait_ready` through the login handshake, `exec "uname -a"` reading
back the kernel line, `exec "false", check=True` raising
`command.signalled-failure` and `exec "nosuch"` raising the same,
a row slice that does not include the boot's output, and the
**agentless DOS suite passing byte-for-byte** — the dialect seam
may not move a DOS reading by one row. P24: every touched surface
tested against its own spelling.

**Sprint bound: too large as one, and the cut is visible.** (a) The
dialect seam, DOS moved behind it with the suite unchanged; (b) the
OpenBSD dialect **with readiness in it**, the platform's `vnc`
default and the recipe's loader fix, proven against the machine
spike 0 installed. The third piece this entry used to carry — route
(1), "if and when a user's own OpenBSD asks for it" — **is gone,
folded into (b)**: the measurement killed the route that would have
avoided a login, and a handshake a dialect cannot reach a prompt
without is not separable from it. Spike 0 no longer precedes the
pledge; it has run.

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

## F39 — The machine-variable channel, both directions

> **Demand: none known — and entered saying so** (owner,
> 2026-08-01). No use case asks for this and none is drafted;
> the owner suspects one will turn up, and this entry holds the
> design questions so the argument is ready when it does.
> Nothing is worked from here, and this proposal in particular
> waits on a demand before pledging is even arguable.
> Provenance: the `Session.set_machine_var` removal — the
> method fell to cli.md's "the host side only reads", and this
> is the capability it gestured at, argued properly instead of
> arriving by stray method.

**The idea.** Machine variables run host→script as well as
script→host: an orchestrator sets a value mid-run
(`set-machine-var`, twin `set_machine_var`), and a running
script retrieves or waits on it. The motivating shape is the
trigger: a long-running script holds at a wait until another
process supplies the go signal.

**The design load**, named now so the eventual round starts
ahead:

- **Two one-way channels, never one shared map.** Guest-set
  variables are the report channel and stay host-read-only —
  "a value is what the current boot produced" is a provenance
  guarantee, and a host writer sharing that namespace could
  forge guest reports. Host-set variables take their own
  namespace or map, invisible to the report readers. The
  symmetry is in the mechanics, never the store.
- **Script-side retrieval is cheap; the surface is not.** The
  runner is host-side, so reading the state document is
  trivial — but a wait channel or interpolation source is
  language surface, governed by the goals and the V-rules, and
  it is the part the round is really about.
- **P19 binds.** Run-specific data never selects a branch, a
  phase, or a path. A host signal may *gate* progress — that is
  what a wait is — but a value that picks a path is refused
  already, and the design must not become the flag-channel P19
  exists to prevent.
- **Properties are bound once, deliberately.** A run today is a
  function of its bound inputs: dry-run's plan and the run
  record both lean on that. A mid-run host input makes outcomes
  timing-dependent. Screen waits already admit timing, but a
  value channel is a bigger step than a signal, and the round
  prices it or narrows to the signal.
- **P6 lands every face together**: the CLI command, the
  session twin, and the script-side read or wait arrive in one
  change, and the command manifest gains the capability in the
  same commit.
- **cli.md's sentence is the gate.** "Writing is the script
  verb's, and the host side only reads" is in force; this
  proposal is an argued amendment of it and lands only through
  the surface-change rule (P23), never by arrival.

