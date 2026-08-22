<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# The backend adapter API

> **Status:** the design doctrine for Reliquary's backend adapter
> seam (owner, 2026-07-21), **delivered 2026-07-28** as F2 — whose
> number retires with it. It is an internal engineering contract,
> deliberately **not** one of the application surfaces
> (planning/SURFACES.md names those; the watch that would revisit
> this is recorded in planning/TASKS.md), which is why it stays here
> rather than moving to `docs/spec/` on delivery. It travelled from
> `pledged/design/` when F2 left the shelf: a delivered feature
> leaves no feature for its design to sit with.
>
> The doctrine below — the layering, the seam inventory, the
> capability and ownership doctrines, the non-goals — was settled
> before the demand was written (the D33 pattern it exited when U7
> was pledged) and is unchanged by the extraction. **The signatures
> are now recorded**, at the end, per this document's own rule that
> they land with the working code rather than ahead of it.

## What the adapter API is

One API, four adapters — QEMU, VirtualBox, VMware Workstation,
Hyper-V ([ARCHITECTURE.md](../../ARCHITECTURE.md), "The seams"; the
per-backend control-plane inventory is in
[guest-communication.md](guest-communication.md)). It is the
*provider* contract behind Reliquary's semantic surface, and it is
none of the things the primary surfaces are:

- **Never a twin family.** No adapter operation appears on the CLI
  or in the embedding API. Consumers touch backends only through
  blueprint vocabulary (`backend`, `backend-settings`,
  `control-planes`, drives and controllers) and through the
  capability failures preflight reports.
- **Not bound by the C/Java constraint.** Adapters are in-repo
  Python; the binding constraint governs the embedding API, not
  this seam. The constraint that does govern here is honesty:
  **capabilities are reported, never emulated** — a backend that
  cannot provide a declared drive, controller, or control plane
  fails capability preflight by name; nothing is silently
  approximated.
- **In-repo consumers only, for now.** All four adapters ship with
  Reliquary — two built (QEMU, VirtualBox lifecycle) and two stubs.
  If a third-party adapter
  story ever becomes real, the
  seam is elevated into the SURFACES inventory through the
  surface-change rule — that elevation is the recorded watch,
  not the default.

## The three layers

The extraction splits what `machines.py`, `lifecycle.py`, and
`machine.py` mix today:

1. **The machine model — above the seam, unmoved.** Machine ids,
   phases, the state document, media resolution, and the
   `insert_media` / `eject_media` / `set_boot_order` mutations are
   already backend-independent: they edit state that the next
   start consumes. Nothing here crosses the seam.
2. **The adapter — everything that today knows QEMU.** Binary
   discovery, image creation, configuration rendering, owned
   process launch, monitor sessions, identity verification, input
   injection, screen capture and readback.
3. **Control planes — compositions over adapter carriers.** Per
   the settled vocabulary (planning/design/guest-communication.md), a control plane composes carriers and a protocol and
   presents capabilities to platform workflows. The agentless
   display console is the first real one; it receives an adapter
   machine handle exactly as `AgentlessGuestExec` receives a
   `Machine` today, and never opens backend connections of its
   own.

## The seam inventory

Each entry names its extraction source in the working QEMU code.
The inventory is the seam's shape; the signatures land with the
extraction.

- **Discovery.** Probe the host for the backend — binaries on PATH
  and conventional install locations, the Hyper-V service/module —
  and report availability and version. Discovery only establishes
  availability; it never selects a backend and never changes a
  machine's recorded one. (Seed: `lifecycle._find_qemu_tool`.)
- **Capability report.** A named-vocabulary report, judged against
  a whole blueprint at assignment time: supported control planes,
  media kinds (floppy — absent on Hyper-V Generation 2, cdrom,
  vvfat — QEMU-only), controller types, `difference` drive
  support. The vocabulary is the blueprint reference's — controller
  and control-plane support are already specified there as checked
  capabilities — and capability failures name the backend and the
  requirement.
- **Materialize and dispose.** The adapter owns drive-image
  creation in its backend's native format — `new` and
  `difference` media alike (qcow2 under QEMU; VDI/VMDK/VHDX
  and native differencing elsewhere; the blueprint reference makes
  the format Reliquary's per-backend choice) — plus whatever
  registration the backend requires, with every backend file kept
  inside `cache/machines/<id>/` so the cache directory remains the
  whole materialization. Dispose removes the backend's machine
  object; `destroy` then deletes the directory. (Extraction:
  `lifecycle.create_hdd_image` and `find_qemu_img` become
  QEMU-adapter internals.)
- **Raw interchange.** The adapter reads a drive's content out
  as a raw image and materializes a native drive from one — the
  one obligation powering `export-drive`'s raw form and
  cross-target `export-machine` (owner, 2026-07-22): drive
  content travels between formats as raw. Exporters themselves
  are *not* adapter operations: they are their own module family
  beside the adapters (the `--to` vocabulary — virtualbox,
  vmware, hyperv, libvirt, vagrant, ... — probed on the host
  independently of the backend list, sharing discovery helpers
  where the tools coincide), consuming the machine's resolved
  blueprint shape plus this interchange.
- **Start, stop, liveness.** Start consumes the machine's resolved
  state document — Reliquary drive vocabulary in, backend
  configuration out; raw backend arguments never cross the seam
  from callers — accepts control-plane endpoint contributions
  before launch (below), and returns an identity-verified session
  handle. Stop is fail-closed under the ownership doctrine. A
  guest-initiated power-off is observable: the `machine=stopped`
  wait channel and the model's `mark_stopped` reconciliation
  depend on the adapter reporting liveness honestly. (Extraction:
  `lifecycle.launch_owned_qemu` / `stop`; the rendering half of
  `machines.start` and `machines.machine_drive_args`.)
- **Carriers.** Key injection; framebuffer capture (screenshots
  remain a management-interface diagnostic, outside `GuestExec`);
  the text-screen snapshot (below); duplex byte-stream endpoints
  (serial now, guest-agent transports later); and the named native
  escape hatch — today `Machine.qmp()` / `hmp`, always explicitly
  backend-scoped, never generalized. (Extraction: `machine.py`'s
  `char_keys` / `send_keys`, `screenshot`, `vga_screen`.)
- **Ownership.** The recorded-VM-identity doctrine, generalized (below).

## The text-screen contract

Adapters provide carriers: input injection, framebuffer capture,
and native text readback where the backend has it (QEMU's VGA text
memory). The agentless-display control plane composes them — and
where no native text carrier exists, it runs **one shared
fixed-font recognizer** over the captured framebuffer. The
recognizer is written once, not per adapter, and lives with the
control plane, not behind the seam.

**Its whole input is what the host's hypervisor binaries carry** —
the banks a backend's own BIOS ships, read off the installation and
cached, never vendored. So a guest that loads a face of its own is
read through fonts that do not include it, which is **U25**'s
demand: the guest's font among the ones the screen is read through,
taken from the guest where a script can reach a prompt or supplied
by the author where it cannot (**U27**), and named from the point in
the run where the guest takes the screen over.

The snapshot contract that makes this portable: **character rows
plus opaque, equality-comparable per-cell attribute tokens.** The
cursor-menu machinery never interprets attribute values — it
compares them for equality and frequency to find and follow the
selection highlight. VGA attribute bytes satisfy that contract
today; a recognizer that hashes each cell's foreground/background
pair into a token satisfies it identically, and the entire menu
algorithm carries over unchanged. Attribute tokens promise nothing
except "equal tokens mean identically rendered cells".

## The ownership doctrine

The recorded-VM-identity doctrine, generalized to every backend:
the machine's `vm` state section records an identity — the
backend, the backend's own machine identifier (`backend-id`:
QEMU's per-start `-uuid`
with its readable name, a VirtualBox machine UUID, a `.vmx` path,
a Hyper-V VM Id), a per-start token where the carrier is an
addressable endpoint that outlives its owner (a QMP port is
reusable by strangers; a readable name repeats across homes), and
the endpoint itself. Every adapter operation verifies identity
before commanding; a mismatch fails closed and must never reach
the backend's stop/quit path. Stale identity records are removed
only after a failed verification proves them stale.

## Endpoint lifecycle

A control plane may need two phases (planning/design/guest-communication.md
"Configuration and lifecycle"): contribute validated launch
configuration for its carrier before the machine starts, and
connect to the realized endpoint after startup. The adapter
mediates both — endpoint requests go in with start, realized
endpoint paths come out with the session handle — and every
persistent endpoint artifact stays under the machine's cached
materialization.

## Non-goals

- **No emulation.** A missing capability is a named preflight
  failure, never an approximation.
- **No console-bundled file exchange.** vvfat staging and
  guest-agent file operations have different lifecycle and
  consistency rules; file exchange is its own capability, not a
  console feature.
- **Screenshots stay diagnostics.** Outside `GuestExec`,
  independent of the selected control plane.
- **No long-running host agents, schedulers, or services.** The
  adapter drives backend tools and endpoints; Reliquary remains a
  local ephemeral-machine tool.
- **Not a general hypervisor library.** The seam covers exactly
  what Reliquary's machine model and control planes need.
- **Accelerators are not backends.** KVM/WHPX/HVF/TCG are the
  QEMU adapter's internal capability choice — host-probed, at
  most a `backend-settings` override — never backend identity
  and never blueprint vocabulary. libvirt likewise is an
  exporter today and would be a distinct adapter if it ever
  became a backend; the two roles are independent (owner,
  2026-07-22).
- **External harnesses are not core backends.** os-autoinst /
  isotovideo, the engine under openQA, may be worth a future
  external-runner adapter or export target: Reliquary could lower
  a scenario into an os-autoinst test distribution, run the GPL
  tool as a separate process, and collect its records. That does
  not make os-autoinst an implementation source for this seam, nor
  part of the default backend list.
- **Orchestrators are handoff targets, not backends.** Vagrant may
  be an exporter/importer vocabulary entry — generating or reading
  a Vagrantfile / box handoff around a provider VM — but it does
  not own the native virtualization capabilities Reliquary needs to
  verify. The real backend remains the provider underneath.
- **Emulators without a management interface are not backends —
  DOSBox-X in particular** (investigated 2026-08-22; the
  evidence and the reopen condition are
  [dosbox-x.md](dosbox-x.md), watched by **R12**). The machine
  half fits — it boots real DOS from floppy, hard-disk and ISO
  images over emulated IDE, and reads raw, VHD and qcow2 with a
  native differencing image of its own. **The control half does
  not exist**: every carrier this seam requires is a host-side
  command against a *running* machine, and DOSBox-X's whole
  external surface is the command line at launch and the SDL
  window after it — no monitor, socket or pipe, so no key
  injection, no screen readback, no medium swap, and no
  identity to verify or fail closed on. The tools that could
  drive it (`AUTOTYPE`, `DX-CAPTURE`, `IMGSWAP`) belong to the
  DOS it supplies, which is the DOS an install replaces.
  Driving the host window instead would be the brittle
  UI-automation plane
  [guest-communication.md](guest-communication.md) refuses, and
  an `agentless-display` *emulated* rather than reported (P11).
  It is a handoff target at the image boundary, like the two
  entries above, rather than a provider.

## Backend assignment

Discovery establishes availability; **assignment** picks the
backend a machine is built on, and happens at materialization
(`create` / `recreate`). Reliquary walks its internal backend
priority list one by one, probing each for availability, and picks
the first available *and capable* backend. Capability is judged
against the whole blueprint: referenced media and image types the
backend must be able to attach, required control planes, and the
settings that apply to that candidate backend.

Backend-specific settings are **conditional, not a selector**: a
blueprint may say "if this materializes on VirtualBox, disable I/O
APIC" without requiring VirtualBox, and candidates without
applicable settings simply ignore that backend's settings block.
Only an explicit `backend` field pins the choice and skips the
walk — that backend is probed alone, and `create` fails closed if
it is unavailable or incapable. The assignment is recorded in the
machine state, so the machine stays on that backend thereafter.

The priority order is **QEMU, VirtualBox, VMware Workstation,
Hyper-V** (owner, 2026-07-28; D66 — the seam extraction's
decide-first, settled with the pledge it travelled on, and F2 now
carries none). It ranks *agentless* scriptability, the capability
every guest gets: QEMU alone has the full control plane set today;
VBoxManage is the closest match to it, covering lifecycle,
scancode input, screenshots and serial redirection; VMware
Workstation exposes VNC but no comparable scancode surface; and
Hyper-V has no VNC at all, leaving it with no agentless display
plane. Order breaks ties among candidates already available and
capable, so it never substitutes for a capability check.

**What the remaining stubs claim is nothing.** Their host probe is
real — knowing whether VMware or Hyper-V is installed costs nothing
and is honest either way — and their capability report is empty, so
the walk passes over them even where the backend is installed (P11:
an untested capability is an unclaimed one). VirtualBox (F50/F52)
claims lifecycle and `agentless-display`. A pinned `backend`
naming an incapable adapter fails
preflight by name; the abstract-method
`NotImplementedError` guards only what assignment can never reach,
because a reachable gap with a message is a PREFLIGHT ERROR under
the error taxonomy (D58).

**Backend state stays in the cached materialization.** Each backend
is instructed to keep its machine files (disk images, `.vbox`,
`.vmx`, Hyper-V VM/VHD paths) inside `cache/machines/<id>/`, so a
machine's cache directory is the whole materialization.

## Extraction map

The extraction work, stated as movements of working code:

- `lifecycle.py` discovery, launch, QMP session, and
  identity-verification code → the QEMU adapter.
- `create_hdd_image` / `find_qemu_img` → QEMU-adapter
  materialization internals.
- The rendering half of `machines.start` (`-m`, drive arguments,
  boot-letter mapping) and `machine_drive_args` → the QEMU
  adapter's start path.
- `machine.py`'s input mapping and VGA/screendump access → QEMU
  adapter carriers; `_DisplayConsole`'s menu-following and
  screen-settling logic → the agentless-display control plane,
  shared across adapters via the text-screen contract.

Signatures, handle types, and the capability-report schema were
settled in this extraction and are recorded below.

## The signatures, as extracted

Recorded here on delivery (2026-07-28), from the working code
rather than ahead of it. `src/reliquary/backends.py` holds the
contract; `src/reliquary/backend_qemu.py` and
`src/reliquary/backend_virtualbox.py` implement it (VirtualBox
lifecycle and agentless-display as of F50/F52, 2026-08-03);
`src/reliquary/backend_stubs.py` holds the two that do
not.

**The vocabulary.** Three frozen records, all plain data:

- `Availability(backend, available, version, executable, detail)`
  — what a probe found. `detail` says where it was found, or why
  it was not; a refusal quotes it.
- `Capabilities(backend, control_planes, media, controllers,
  materialize, vvfat)` — the named-vocabulary report, in the
  blueprint's own words.
- `Requirements(control_planes, media, controllers, materialize)`
  — what one whole blueprint asks for, read off the machine at
  assignment time.

**The contract** (`BackendAdapter`), grouped as the inventory
above names it:

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

`unmet()` is the seam's own arithmetic and is shared by every
adapter: a requirement is judged against a report, and what comes
back is the text a preflight failure quotes — so a refusal always
names *which* requirement was refused.

**There is no at-rest drive access in this contract.** An
`open_drive()` was sketched here and never landed, and D108 closed
the question for good by putting a machine's file content outside
Reliquary's purview (**P16**'s carve-out): an adapter creates the
images a machine runs on and exposes nothing that reads inside
one.

**The identity record** (`backends.identity()`) is the ownership
doctrine as data: `{backend, backend-id, token, endpoint, pid?}`.
The machine model persists it verbatim into `machine.json`'s `vm`
section, atomically with the phase, and reads only its generic
core; the endpoint's shape belongs to the adapter, which validates
it when it opens a session.

**The carriers** hang off the session, so a control plane composes
them without ever learning the endpoint behind them:

```text
session.backend                             -> the adapter's name
session.send_keys(combos, delay=0.06)
session.text_screen()                       -> (rows, attribute rows)
session.screenshot(path)                    -> path
session.change_medium(drive_key, path=None)
session.native()                            -> the backend-scoped hatch
```

The key vocabulary crossing this seam is **QEMU's qcode set**
(D103). Its own mapping is therefore the identity — because the
names *are* its own, not because the two happen to agree — and a
backend naming keys differently translates in its own adapter,
keyed by these names. The seam is named for the reference backend
deliberately: the alternative was a third vocabulary no backend
speaks natively, invented only so the seam could avoid saying so.

This is not the *language's* key vocabulary, which is portable and
stays that way (`script_validation.PORTABLE_KEY_NAMES`, resolved
onto the seam's names before a run reaches an adapter). P25 governs
what a blueprint may say, and is untouched by how the seam spells
`enter`.

**Two things the extraction deliberately left out.** Raw
interchange is in the inventory above but has no caller: it lands
with the exporter family that needs it, which is unbuilt. And the
**vvfat** capability is reported but not judged at assignment: a
directory-source media's realized shape is only knowable after
resolution, so the QEMU adapter judges it where the drive is
rendered. Both are named rather than hidden (P11).

**The test seam** is `backends._set_adapter(name, instance)`,
mirroring `credentials._set_provider`: the suite drives the machine
model against a double (`tests/fake_backend.py`) rather
than a hypervisor, so no unit test probes or launches a real
backend.
