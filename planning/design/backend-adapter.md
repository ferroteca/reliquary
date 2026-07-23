<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# The backend adapter API

> **Status:** the design doctrine for Reliquary's backend adapter
> seam (owner, 2026-07-21) — an internal engineering contract,
> deliberately **not** one of the world-facing interfaces
> (planning/INTERFACES.md names those; the watch that would revisit
> this is recorded in planning/TASKS.md). This document settles the
> seam's shape: the layering, the seam inventory, the capability
> and ownership doctrines, and the non-goals. Method signatures and
> exact types are deliberately absent: they land at the milestone-10
> extraction, defined by the working QEMU implementation per that
> milestone's own doctrine (planning/ROADMAP.md "Milestone 10 — The
> backend adapter seam").

## What the adapter API is

One API, four adapters — QEMU, VirtualBox, VMware Workstation,
Hyper-V (planning/ROADMAP.md "Backend adapters"). It is the
*provider* contract behind Reliquary's semantic surface, and it is
none of the things the primary interfaces are:

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
  Reliquary. If a third-party adapter story ever becomes real, the
  seam is elevated into the INTERFACES inventory through the
  interface-change rule — that elevation is the recorded watch,
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
   the settled vocabulary (planning/ROADMAP.md "Guest communication
   design"), a control plane composes carriers and a protocol and
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

A control plane may need two phases (planning/ROADMAP.md
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

## Extraction map

The milestone-10 work, stated as movements of working code:

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

Signatures, handle types, and the capability-report schema are
settled in this extraction and recorded here when they land.
