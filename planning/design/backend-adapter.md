<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# The backend adapter API

> **Status:** this document (owner, 2026-07-21) was **delivered
> 2026-07-28** as F2, and F2's number retires with it. It's an
> internal engineering contract, not one of the application surfaces
> (planning/SURFACES.md lists those; the watch that would revisit
> this is recorded in planning/TASKS.md). That's why it stays here
> instead of moving to `docs/spec/` now that it's delivered. It moved
> here from `pledged/design/` when F2 left the shelf: once a feature
> is delivered, there's no more "pledged" feature for its design
> document to sit next to.
>
> Everything below — the three layers, the inventory of what crosses
> between them, the capability and ownership rules, the non-goals —
> was settled before the demand (U7) was even written down (the D33
> pattern it exited when U7 was pledged), and the extraction into
> working code didn't change any of it. **The function signatures are
> recorded at the end**, added on delivery: this document's own rule
> is that signatures get written down once the code exists, not
> guessed at ahead of it.

## What the adapter API is

This document defines the boundary — Reliquary calls it **the seam**
— between Reliquary's own code and the four hypervisors it can drive:
QEMU, VirtualBox, VMware Workstation, Hyper-V
([ARCHITECTURE.md](../../ARCHITECTURE.md), "The seams"; the
per-backend control-plane inventory is in
[guest-communication.md](guest-communication.md)). On Reliquary's
side of the seam, code talks about drives, controllers, and control
planes in Reliquary's own vocabulary. On the other side, one
**adapter** per hypervisor translates that vocabulary into whatever
that specific hypervisor actually needs — a QEMU command line, a
`VBoxManage` call, and so on. One API, four adapters.

This seam is not one of Reliquary's application surfaces (the CLI,
the embedding API). That means:

- **It has no CLI commands or API calls of its own.** Nothing an
  adapter does is directly callable from the CLI or the embedding
  API. Callers reach a backend only through blueprint fields —
  `backend`, `backend-settings`, `control-planes`, drives and
  controllers — and through the capability failures that preflight
  reports back.
- **It isn't held to the C/Java compatibility rule that binds the
  embedding API.** Adapters are ordinary in-repo Python. The rule
  that does apply here is about honesty, not language compatibility:
  **a backend reports its capabilities, it never fakes one it
  doesn't have.** If a backend can't provide a drive, controller, or
  control plane a blueprint asks for, preflight fails and names
  exactly what's missing — nothing is silently approximated.
- **Only Reliquary's own code calls into it, for now.** All four
  adapters ship with Reliquary itself — two are actually built (QEMU,
  and VirtualBox's lifecycle operations) and two are stubs that
  claim no capabilities. If Reliquary ever needs to let outside code
  plug in a third-party adapter, this seam would then need to become
  a listed application surface, following the surface-change rule in
  planning/SURFACES.md. That's a recorded possibility to watch for,
  not something planned now.

## The three layers

Before this extraction, `machines.py`, `lifecycle.py`, and
`machine.py` all mixed together code that talks about machines in
general with code that specifically knows QEMU. The extraction splits
that into three layers:

1. **The machine model, on Reliquary's side of the seam, unmoved.**
   Machine ids, phases, the state document, media resolution, and the
   `insert_media` / `eject_media` / `set_boot_order` mutations were
   already backend-independent — they edit state that the next start
   reads — so none of this code moves. It never crosses into
   hypervisor-specific territory.
2. **The adapter — everything that used to know QEMU specifically.**
   Binary discovery, image creation, configuration rendering, owned
   process launch, monitor sessions, identity verification, input
   injection, screen capture and readback. This is the code that
   moved.
3. **Control planes — built out of what an adapter exposes.** Using
   the vocabulary settled in planning/design/guest-communication.md,
   a control plane combines an adapter's carriers (see "The seam
   inventory" below) with a protocol, and offers the result to
   platform workflows as a capability they can use. The agentless
   display console is the first real one: it receives an adapter's
   machine handle the same way `AgentlessGuestExec` receives a
   `Machine` today, and it never opens a backend connection of its
   own — it only uses what the adapter already opened.

## What crosses the seam

This is the full list of operations every adapter must implement (or
honestly refuse). Each entry names where it came from in the
QEMU-only code before the extraction; the actual function signatures
are recorded later in this document, once they existed.

- **Discovery.** Probe the host for the backend — binaries on PATH
  and the usual install locations, or the Hyper-V service/module —
  and report whether it's available and which version. Discovery
  only answers "is it there"; it never picks a backend for a machine
  and never changes a machine's already-recorded one. (Came from
  `lifecycle._find_qemu_tool`.)
- **Capability report.** What one backend can do, stated in
  Reliquary's own vocabulary, checked against a whole blueprint when
  a machine is assigned to a backend: which control planes it
  supports, which media kinds (floppy — missing on Hyper-V Generation
  2 — cdrom, and vvfat, which only QEMU has), which controller types,
  and whether it supports `difference` drives. The vocabulary is
  already defined in the blueprint reference — controller and
  control-plane support are specified there as checked capabilities
  — and when a capability is missing, the failure names both the
  backend and the specific requirement it couldn't meet.
- **Materialize and dispose.** The adapter creates drive images in
  its backend's own native format — both `new` and `difference`
  media (qcow2 for QEMU; VDI/VMDK/VHDX and native differencing
  images elsewhere — the blueprint reference leaves the exact format
  up to Reliquary, per backend) — plus whatever registration the
  backend needs. Every file a backend creates for a machine stays
  inside `cache/machines/<id>/`, so that directory is the complete
  record of what was materialized. Dispose removes the backend's
  internal machine object; `destroy` then deletes the whole
  directory. (Came from `lifecycle.create_hdd_image` and
  `find_qemu_img`, now QEMU-adapter internals.)
- **Raw interchange.** The adapter can read a drive's content out as
  a plain raw image, and can build a native drive back from one.
  This is what `export-drive`'s raw form and cross-target
  `export-machine` (owner, 2026-07-22) both need: drive content
  moves between formats by passing through raw. Exporters
  themselves are *not* adapter operations — they're their own
  separate family of modules (the `--to` vocabulary: virtualbox,
  vmware, hyperv, libvirt, vagrant, and so on, each probed on the
  host independently of the backend list, sharing discovery code
  where the underlying tools happen to coincide). An exporter
  consumes the machine's resolved blueprint plus this raw
  interchange.
- **Start, stop, liveness.** Start reads the machine's resolved state
  document and turns Reliquary's own drive vocabulary into backend
  configuration — callers never pass raw backend arguments through
  the adapter. Before launch, it accepts endpoint requests from
  control planes (see "Endpoint lifecycle" below), and once the
  machine is running it returns a session handle whose identity has
  already been verified. Stop fails closed, per the ownership rule
  below. If the guest powers itself off, the adapter has to notice:
  the `machine=stopped` wait and the model's `mark_stopped`
  reconciliation both depend on the adapter reporting liveness
  honestly. (Came from `lifecycle.launch_owned_qemu` / `stop`, and
  the rendering half of `machines.start` and
  `machines.machine_drive_args`.)
- **Carriers.** The individual capabilities a control plane builds
  on: injecting keystrokes; capturing the framebuffer (screenshots
  stay a management-interface diagnostic, separate from
  `GuestExec`); reading a text-mode screen (see "The text-screen
  contract" below); duplex byte-stream connections (serial today,
  guest-agent transports later); and a named escape hatch straight
  to the backend's own native interface — today `Machine.qmp()` /
  `hmp` — which is always explicitly tied to one backend and never
  turned into something generic. (Came from `machine.py`'s
  `char_keys` / `send_keys`, `screenshot`, and `vga_screen`.)
- **Ownership.** The rule that a session must be able to prove it's
  still talking to the VM it started, generalized to every backend
  — see "The ownership doctrine" below.

## The text-screen contract

Adapters provide carriers: injecting input, capturing the
framebuffer, and — where the backend has it — reading text straight
out of the guest's memory (QEMU can read its VGA text memory
directly). The agentless-display control plane uses these carriers,
and where there's no native way to read text, it runs **one shared
fixed-font recognizer** over the captured framebuffer instead. That
recognizer is written once, shared by every adapter, and lives with
the control plane rather than being duplicated inside each adapter.

**The recognizer only knows the fonts the host's own hypervisor
binaries ship** — the character-set banks a backend's BIOS carries,
read off the installation and cached, never bundled separately by
Reliquary. So if a guest switches to a font of its own, the
recognizer is reading the screen through fonts that don't include
it. **U25** requires that the guest's actual font be among the ones
the screen is read through: taken from the guest itself when a
script can reach a prompt to ask for it, or supplied by the blueprint
author when it can't (**U27**), and named from the point in the run
where the guest takes over the screen.

What makes this portable across backends is the shape of the
snapshot itself: **character rows, plus per-cell attribute tokens
that are opaque but can be compared for equality.** The cursor-menu
code never looks inside an attribute value — it only checks whether
two cells' attributes are equal, and counts how often each value
appears, to find and follow the highlighted selection. QEMU's raw
VGA attribute bytes satisfy that rule today. A recognizer that
instead hashes each cell's foreground/background color pair into a
token satisfies the exact same rule, so the whole menu-following
algorithm works unchanged on either kind of token. An attribute
token promises nothing beyond "two equal tokens mean two identically
rendered cells."

## The ownership doctrine

Every backend now follows the same rule that used to apply only to
QEMU: a machine's `vm` state section records who it is, so a session
can prove it's still talking to the same VM it started. That record
holds: the backend name; the backend's own machine identifier
(`backend-id` — QEMU's per-start `-uuid` plus its readable name, a
VirtualBox machine UUID, a `.vmx` path, or a Hyper-V VM Id); a
per-start token, for the cases where the carrier is an addressable
endpoint that can outlive the machine that opened it (a QMP port can
be reused by a different, unrelated process later; a readable name
can repeat across different machine homes); and the endpoint itself.
Every adapter operation checks this identity before it acts. If the
check fails, the operation refuses rather than risking action on the
wrong machine, and a failed check must never be allowed to reach the
backend's own stop/quit call. A stale identity record is only
removed after a failed verification has actually proven it's stale.

## Endpoint lifecycle

A control plane can need two separate steps (see "Configuration and
lifecycle" in planning/design/guest-communication.md): first, hand
over validated launch configuration for its carrier before the
machine starts; then, connect to the real endpoint once the machine
is actually running. The adapter sits in the middle of both steps —
endpoint requests go in alongside start, and the realized endpoint
paths come back out with the session handle — and any endpoint file
that needs to persist stays inside the machine's cached
materialization directory.

## What this deliberately doesn't do

- **No emulation.** A missing capability is always a named preflight
  failure, never something Reliquary fakes or approximates.
- **No file exchange bundled into the console.** vvfat staging and
  guest-agent file operations have different lifecycle and
  consistency rules from a display console, so file exchange is its
  own capability rather than something the console also does.
- **Screenshots stay a diagnostic tool.** They live outside
  `GuestExec` and don't depend on which control plane is in use.
- **No long-running host agents, schedulers, or services.** The
  adapter drives backend tools and endpoints directly; Reliquary
  stays a local tool for ephemeral machines, not something with its
  own background daemon.
- **Not a general-purpose hypervisor library.** This seam covers
  exactly what Reliquary's machine model and control planes actually
  need — nothing more.
- **CPU accelerators are not backends.** KVM, WHPX, HVF, and TCG are
  an internal choice the QEMU adapter makes for itself — probed on
  the host, and at most overridable through `backend-settings` — not
  a backend identity and not something a blueprint names directly.
  Similarly, libvirt is only an exporter today, and would become its
  own separate adapter if it ever became a backend Reliquary drives
  directly — the two roles (exporter, backend) are independent
  (owner, 2026-07-22).
- **External test harnesses are not core backends.** os-autoinst /
  isotovideo — the engine behind openQA — might someday be worth an
  external-runner adapter or export target: Reliquary could turn a
  scenario into an os-autoinst test distribution, run that GPL tool
  as a separate process, and collect its results. That's a possible
  future feature, not a reason to treat os-autoinst as part of this
  seam or add it to the default backend list today.
- **Orchestrators are handoff targets, not backends.** Vagrant could
  become an exporter/importer entry — generating or reading a
  Vagrantfile or box around a provider VM — but it doesn't own the
  actual virtualization capabilities Reliquary needs to verify (start
  it, stop it, inject input, and so on). The real backend is always
  the provider underneath Vagrant, not Vagrant itself.
- **Emulators with no management interface are not backends —
  DOSBox-X in particular** (investigated 2026-08-22; the evidence and
  the condition that would reopen this are in
  [dosbox-x.md](dosbox-x.md), watched by **R12**). DOSBox-X is a
  plausible *machine*: it boots real DOS from floppy, hard-disk, and
  ISO images over emulated IDE, and it reads raw, VHD, and qcow2
  images, with its own native differencing-image format. But it has
  **no way to control it once it's running.** Every carrier this seam
  requires is a host-side command sent to an already-running machine,
  and DOSBox-X's entire external surface is the command line used to
  launch it and the SDL window that appears afterward — no monitor
  port, no socket, no pipe. That means no key injection, no screen
  readback, no medium swap, and no identity to verify or fail closed
  on. The tools that could do those things —`AUTOTYPE`, `DX-CAPTURE`,
  `IMGSWAP` — belong to the DOS running *inside* DOSBox-X, which is
  the exact DOS an install would be replacing. The alternative,
  driving DOSBox-X's host window through UI automation, is exactly
  the brittle approach [guest-communication.md](guest-communication.md)
  rules out, and it would mean claiming an `agentless-display`
  control plane that's really emulated rather than genuinely reported
  (P11). So DOSBox-X is a handoff target at the disk-image boundary,
  like os-autoinst and Vagrant above — something Reliquary could
  export *to* — not something it can drive as a backend.

## Backend assignment

Discovery only answers whether a backend is installed. **Assignment**
is the separate step that actually picks which backend a machine is
built on, and it happens at materialization (`create` / `recreate`).
Reliquary walks its internal backend priority list one entry at a
time, probes each for availability, and picks the first one that is
both available *and* capable of the whole blueprint. "Capable" is
checked against the whole blueprint at once: the media and image
types it references that the backend must be able to attach, the
control planes it requires, and any settings that apply to that
candidate backend.

Backend-specific settings **narrow behavior on a backend, they don't
select one**: a blueprint can say "if this ends up on VirtualBox,
disable I/O APIC" without that requiring the machine to use
VirtualBox. A candidate backend with no matching settings block just
ignores it. The one thing that does pin the choice is an explicit
`backend` field in the blueprint — that skips the walk entirely, only
that one backend is probed, and `create` fails closed if it's
unavailable or can't meet the blueprint's requirements. Whichever
backend gets assigned is recorded in the machine's state, so the
machine stays on that backend from then on.

The priority order is **QEMU, VirtualBox, VMware Workstation,
Hyper-V** (owner, 2026-07-28; D66). This order was decided before
this extraction happened, as part of the pledge that led to it, and
F2's delivery didn't change it. It's ranked by *agentless*
scriptability — the one capability every guest gets, since assignment
happens before any guest-specific setup exists. QEMU alone has the
full set of control planes today. VBoxManage is the closest match:
lifecycle control, scancode-level key input, screenshots, and serial
redirection. VMware Workstation exposes VNC but nothing comparable
for sending scancodes. Hyper-V has no VNC at all, so it currently has
no agentless display plane whatsoever. This order only breaks ties
among backends that are already both available and capable — it
never substitutes for the capability check itself.

**The two unbuilt stubs (VMware, Hyper-V) claim no capabilities at
all.** Their host probe is real — checking whether VMware or Hyper-V
is installed costs nothing and the answer is honest either way — but
their capability report always comes back empty. That means the
assignment walk skips over them even on a host where the backend
really is installed (per P11: a capability that hasn't been tested
counts as not claimed). VirtualBox (F50/F52) does claim real
capabilities: lifecycle control and `agentless-display`. If a
blueprint pins a `backend` that turns out not to be capable enough,
preflight fails and names the gap; the `NotImplementedError` on the
adapter's abstract methods only guards code paths assignment can
never actually reach, because any gap a caller *can* reach has to
surface as a named PREFLIGHT ERROR under the error taxonomy (D58),
not a crash.

**Backend state lives inside the machine's cache directory.** Every
backend is required to keep its own machine files — disk images,
`.vbox`, `.vmx`, Hyper-V VM/VHD paths, whatever that backend uses —
inside `cache/machines/<id>/`. That means a machine's cache directory
is always the complete materialization, nothing lives outside it.

## Extraction map

Here's exactly which code moved where:

- `lifecycle.py`'s discovery, launch, QMP session, and
  identity-verification code moved into the QEMU adapter.
- `create_hdd_image` / `find_qemu_img` became QEMU-adapter
  materialization internals.
- The rendering half of `machines.start` (`-m`, drive arguments,
  boot-letter mapping) and `machine_drive_args` moved into the QEMU
  adapter's start path.
- `machine.py`'s input mapping and VGA/screendump access became QEMU
  adapter carriers. `_DisplayConsole`'s menu-following and
  screen-settling logic moved into the agentless-display control
  plane, where it's now shared across adapters through the
  text-screen contract above.

The function signatures, handle types, and capability-report schema
were all settled during this extraction, and are recorded below.

## The signatures, as extracted

Recorded here on delivery (2026-07-28), taken from the working code
rather than guessed ahead of it. `src/reliquary/backends.py` holds
the contract; `src/reliquary/backend_qemu.py` and
`src/reliquary/backend_virtualbox.py` implement it (VirtualBox's
lifecycle and agentless-display operations landed as F50/F52,
2026-08-03); `src/reliquary/backend_stubs.py` holds the two adapters
that don't implement anything yet.

**The shared vocabulary.** Three frozen data records:

- `Availability(backend, available, version, executable, detail)` —
  what a probe found. `detail` says where the backend was found, or
  why it wasn't; a refusal quotes it.
- `Capabilities(backend, control_planes, media, controllers,
  materialize, vvfat)` — what one backend can do, in Reliquary's own
  vocabulary.
- `Requirements(control_planes, media, controllers, materialize)` —
  what one whole blueprint needs, read off the machine at assignment
  time.

**The contract** (`BackendAdapter`), grouped the same way as the list
above:

```text
discover()                                  -> Availability
capabilities()                              -> Capabilities
unmet(requirements)                         -> tuple[str, ...]

image_path(root, stem)                      -> path
create_image(path, *, mode, size, base)     -> path
dispose(machine_dir)

start(state, *, machine_dir, backend_dir,
      display=False, current=None)          -> identity record
stop(vm)
session(vm)                                 -> context manager
```

`unmet()` is shared code, not something each adapter reimplements: it
compares a `Requirements` against a `Capabilities` and returns the
text a preflight failure quotes, so a refusal always names exactly
which requirement wasn't met.

**Nothing in this contract reads inside a drive while it's at
rest.** An `open_drive()` method was sketched during design and never
built. D108 settled the question for good, under the carve-out in
**P16**: a machine's file content is outside what Reliquary looks
at. An adapter creates the disk images a machine runs on, but exposes
no way to read what's inside one.

**The identity record** (`backends.identity()`) is the ownership rule
from above, as plain data: `{backend, backend-id, token, endpoint,
pid?}`. The machine model saves it verbatim into `machine.json`'s
`vm` section, atomically with the phase, and only reads its generic
fields back — the endpoint's actual shape belongs to the adapter,
which validates it itself when it opens a session.

**The carriers hang off the session object**, so a control plane can
use them without ever seeing the endpoint underneath:

```text
session.backend                             -> the adapter's name
session.send_keys(combos, delay=0.06)
session.text_screen()                       -> (rows, attribute rows)
session.screenshot(path)                    -> path
session.change_medium(drive_key, path=None)
session.native()                            -> the backend-scoped hatch
```

The key names that cross this seam are **QEMU's own qcode set**
(D103) — QEMU's names are used because they're QEMU's own names, not
because some other backend happens to agree with them. A backend that
spells keys differently translates them inside its own adapter,
keyed against these QEMU names. Naming the seam's vocabulary after
the reference backend was a deliberate choice: the alternative was
inventing a third vocabulary that no backend actually speaks natively,
purely so the seam wouldn't have to admit it borrowed QEMU's names.

That's separate from the *scripting language's* own key vocabulary,
which stays portable across backends
(`script_validation.PORTABLE_KEY_NAMES` is resolved onto this seam's
QEMU-derived names before a run ever reaches an adapter). P25 governs
what a blueprint script is allowed to say, and it doesn't change
depending on how this seam happens to spell `enter`.

**Two things were deliberately left unfinished by this extraction.**
Raw interchange is listed above as something every adapter must
support, but nothing calls it yet — it will be used once the exporter
family that needs it gets built. And the **vvfat** capability is
reported in `Capabilities`, but not actually checked at assignment
time: a directory-backed medium's real shape is only knowable after
resolution runs, so the QEMU adapter checks it later, where the drive
is actually rendered. Both gaps are written down here rather than
hidden, per P11.

**The test seam** is `backends._set_adapter(name, instance)`,
matching the pattern of `credentials._set_provider`: the test suite
runs the machine model against a stand-in adapter
(`tests/fake_backend.py`) instead of a real hypervisor, so no unit
test probes for or launches an actual backend.
