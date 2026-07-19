<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Roadmap

## Vision

reliquary automates guest operating systems — installing them from
vendor media, booting them, and scripting them — across multiple
virtualization backends, driven by named machines and a reliquary
scripting language.

The unit of design is the **operation** performed against a
machine: start it, stop it, attach media, send input, run a guest
command, read the screen, transfer a file, take a screenshot. Two
seams stack beneath the operations, and a third concept scopes OS
meaning:

1. **Virtualization backend** — abstracts *across hypervisors*:
   QEMU, VirtualBox, VMware Workstation, or Hyper-V. Each is
   wrapped by a backend adapter; all adapters share the same API,
   and every backend has some way to perform each operation or
   honestly reports that it cannot.
2. **Control plane** — abstracts *within one backend*: when a
   single backend offers several ways to perform the same operation
   (run a command by agentless typing, over a serial console, or
   through a guest agent), each way is a control plane, and
   choosing among them is explicit policy. Lifecycle operations
   (create, start, stop, delete) always have exactly one way per
   backend — the hypervisor's **management interface** (QMP,
   `VBoxManage`, `vmrun`, WMI), a private tool of the adapter — so
   no control-plane choice applies to them. Control planes exist
   only where choice exists: the guest-facing operations. Selection
   is per capability, not per machine — screenshots may come from
   the management interface while execution goes through a guest
   agent.
3. **Guest platform** — the operating system family inside the
   machine: dos, win9x, winnt, and later others. Platform workflows
   own OS meaning: provisioning, readiness, command syntax,
   completion, and result collection.

A machine spec names its guest platform and (optionally) its backend;
neither is ever inferred from an image or a running guest.

## Backend adapters

All virtualization interaction goes through one of four backend
adapters sharing a common API:

- **QEMU** — the existing machine layer, to be reshaped behind the
  adapter API. Control planes: agentless display (QMP `send-key` + VGA
  text memory), serial (chardev), guest agent (QGA over
  virtio-serial or UART), VNC.
- **VirtualBox** — driven through `VBoxManage`. Control planes: agentless
  display (`controlvm keyboardputscancode` + `controlvm screenshotpng`),
  serial (host pipe/file), guest agent (Guest Additions guest
  control, or reliquary's own agent over serial), VNC where the
  extension pack provides it.
- **VMware Workstation** — driven through `vmrun`/`vmcli` and the
  `.vmx` file. Control planes: agentless display (limited; screenshot via
  `vmrun captureScreen`), serial (named pipe/file), guest agent
  (VMware Tools guest operations, or reliquary's own agent over
  serial), VNC (`RemoteDisplay.vnc.enabled`).
- **Hyper-V** — driven through the PowerShell `Hyper-V` module / WMI
  (`Msvm_*` classes). Control planes: agentless display (WMI keyboard
  injection + thumbnail/screen capture), serial (named pipe), guest
  agent (PowerShell Direct / integration services, or reliquary's
  own agent over serial). No VNC.

Design rules:

- **One API, four adapters.** The adapter API covers machine
  lifecycle (create, start, stop, delete), media attachment, input,
  screen access, and control plane endpoints. Capabilities differ per
  backend; the API reports capabilities honestly rather than
  emulating missing ones.
- **Autodiscovery.** Available backends are discovered by probing
  the host (binaries on PATH and in conventional install locations,
  the Hyper-V service/module). Discovery only establishes
  availability; it never changes a machine's recorded backend.
- **Default backend assignment.** When a machine spec does not name
  a backend, reliquary assigns one from an internal prioritized list
  of the backends actually available, and records the assignment in
  the spec so the machine stays on that backend thereafter.
- **Backend state stays in the machine home.** Each backend is
  instructed to keep its machine files (disk images, `.vbox`,
  `.vmx`, Hyper-V VM/VHD paths) inside the reliquary machine home,
  so a machine directory is the whole machine.
- **The serial-carried reliquary guest agent is backend-portable.**
  Every backend can expose an emulated UART, so the QGA-profile
  agent described below is the one guest-side investment that pays
  off on all four backends.

## The machine model

Machines are referenced by name everywhere. A machine lives in its
machine home:

```text
<reliquary_home>/machines/<name>/
├── reliquary-machine.json   the machine spec
├── drives/                  machine-owned disk/floppy images
├── screenshots/             captured screens
└── ...                      backend state, logs, VM identity
```

### The machine spec — `reliquary-machine.json`

The spec is reliquary's own backend-agnostic format; it must never
be a thin veneer over one backend's configuration. The machine's
name is its directory name; the spec does not repeat it.

The spec is the machine's **single source of truth**, with two
phases of ownership:

1. **Before `create`**, a spec is user-authored input — a file or
   raw JSON handed to `create` describing the intended machine.
   Optional fields may be omitted; `create` resolves them.
2. **After `create`**, the copy in the machine home is reliquary's
   record of the machine, and reliquary maintains it: assigning the
   backend, recording backend identifiers, and updating it whenever
   reliquary reconfigures the machine — mounting drives or media,
   changing memory, reordering boot devices. There is no separate
   "learned" section; resolved facts are written into the same
   fields a user would have declared. The spec always describes the
   machine as it now is.

Hand edits after creation are discouraged, and strongly discouraged
while the machine is running (reliquary rewrites the file as it
manipulates the machine, and the backend will not reflect edits
until a restart at best). The supported way to change a machine is
through reliquary — CLI commands and script steps.

An example spec after `create` has resolved a FreeDOS installation
machine onto QEMU:

```json
{
  "version": 1,
  "platform": "dos",
  "backend": "qemu",
  "backend-id": "reliquary-freedos-plain-5f2c",
  "created": "2026-07-19T18:20:11Z",
  "memory": 32,
  "drives": {
    "hdd_0": {"source": "drives/hdd.qcow2", "size": "20M"},
    "cdrom_0": {"source": "media:FD14LIVE.iso"}
  },
  "boot": ["cdrom_0", "hdd_0"]
}
```

#### Fields

- `version` — required, `1`.
- `platform` — required guest platform: `dos`, `win9x`, `winnt`,
  extended deliberately. Never inferred.
- `backend` — `qemu`, `virtualbox`, `vmware`, `hyperv`. Optional in
  a `create` input: when omitted, `create` assigns one from the
  prioritized list of available backends and writes it into the
  spec. Always present after creation. Changing it afterward is not
  supported — backend state (identifiers, disk formats, VM
  registration) is not portable, so moving a machine to another
  backend means creating a new machine.
- `backend-id` — written by `create`: the backend's identifier for
  the machine (QEMU instance name, VirtualBox UUID, VMware `.vmx`
  path, Hyper-V VM id), the anchor for ownership verification.
  Never valid in a `create` input.
- `created` — creation timestamp, written by `create`.
- `memory` — MiB, defaulting by platform as today (the resolved
  default is written into the spec at creation).
- `cpus` — virtual CPU count, default 1.
- `drives` — the declared-media convention, carried over: keys
  `floppy_0..1`, `hdd_0..3`, `cdrom_0..3` (`floppy`/`hdd`/`cdrom`
  alias slot 0). Each value is a source string or an object:
  - `source` — a path relative to the machine home (images the
    machine owns, conventionally under `drives/`), or a `media:`
    reference naming a file in `<reliquary_home>/media` (shared,
    machine-independent media). Relative paths may not escape the
    machine home; `media:` is the only cross-boundary reference.
  - `size` — optional; when the source file does not exist,
    `create` (or first `start`) creates it at this size in the
    backend's preferred dynamically-allocated format. A `size` on
    an existing image is validated, never applied destructively.
  - `enabled` — optional bool, as today, to disable an entry
    without deleting it.
  - Directory sources (today's vvfat staging) remain declarable but
    are a capability: backends that cannot mount a host directory
    as a drive reject the spec with a capability error rather than
    emulating it.
- `boot` — ordered list of drive keys to try; defaults to the
  current best-guess rule (slot-0 floppy, else slot-0 hdd, else
  cdrom).
- `control-planes` — optional ordered control plane policy for the guest-
  communication waterfall (names per the control plane families below);
  defaults per platform (DOS: agentless display), the resolved
  default written at creation.
- `installed` — whether an install script has completed against
  this machine; written by reliquary, never valid in a `create`
  input.
- `backend-settings` — the explicitly scoped, explicitly
  non-portable escape hatch: one object per backend name (e.g.
  `"backend-settings": {"qemu": {"machine": "pc", "args": [...]}}`).
  Only the section matching the machine's backend applies. This
  replaces today's raw `qemu_args`; it is the only place
  backend-specific configuration may appear, so a spec with no
  `backend-settings` is portable by construction.

#### Rewrite discipline

Reliquary rewrites the spec whenever it changes the machine, in
canonical JSON formatting, atomically (write-temp-and-replace).
Because the file is the single source of truth, reliquary must
update it in the same operation that changes the backend — a spec
that disagrees with the hypervisor's actual configuration is a bug.
On `start`, reliquary verifies the backend machine against the spec
(via `backend-id` and the declared hardware) and fails closed on
drift it cannot reconcile, rather than silently adopting either
side.

#### Validation

Specs fail closed: unknown top-level keys, unknown drive keys, slot
clashes, out-of-range slots, and `backend-settings` for the active
backend containing keys reliquary owns (memory, drives, boot
devices) are errors. Capability mismatches (a directory drive on
Hyper-V, VNC on Hyper-V) are reported as capability errors naming
the backend, not silently degraded.

JSON only for now, as before. YAML may be added later through a
justified parser dependency, must normalize through exactly the same
model, and must not introduce YAML-only features.

### Home layout

```text
<reliquary_home>/
├── machines/<name>/     machine homes (above)
├── scripts/             reliquary automation scripts
└── media/               machine-independent media: ISOs, floppy
                         images, cached+hash-verified vendor
                         installation media
```

The current `install-media/` cache folds into `media/`. The current
root-level `drives/`, `machine.json`, and `vm.json` layout is
superseded by machine homes; the project is pre-release, so this is
a replacement, not a migration.

## The CLI

Machine-scoped commands take the machine by name:

```text
reliquary --machine <name> create <machine_spec>
    (machine_spec: path to a spec JSON file, or a raw JSON string)
reliquary --machine <name> start [--display]
reliquary --machine <name> stop
reliquary --machine <name> delete
reliquary --machine <name> script <script_name> [--display]
```

Lifecycle semantics:

- `script` starts the machine if it is not already running.
- Machines **stay running** until explicitly stopped — by a script
  step or by `stop`. No command implicitly tears the machine down.
- `--display` shows the backend's console window instead of running
  headless.
- Ownership verification generalizes: no adapter sends a control
  command to a hypervisor object until it has verified that the
  object is the one recorded in the machine home (the QMP identity
  check is the QEMU instance of this rule).

## The scripting language

reliquary gets its own scripting language for automating guests.
Scripts are stored in `<reliquary_home>/scripts` and invoked as
`reliquary --machine <name> script <script_name>`.

The primitive vocabulary already exists in today's CLI and Python
surface — it is the proven instruction set the language must cover:

- type text / send keys / run a command and await the prompt;
- wait for screen text (regex) with a timeout;
- select an entry in a cursor-key menu by visible feedback;
- take a screenshot;
- attach/detach media; start, stop, and (from a script) shut down
  the machine;
- stage files to and collect files from the guest.

Language design goals:

- **Backend- and control plane-agnostic at the surface.** A script says
  "wait for this text"; the machine's backend and selected control plane
  decide how that is observed.
- **Deterministic and inspectable.** Failures report the step, the
  screen state, and a screenshot; scripts must be debuggable from
  the transcript alone.
- **Small.** The language exists to sequence guest automation, not
  to be a general-purpose programming language. Anything
  computational belongs in Python via the embedding API, which
  remains a first-class surface.

OS installation recipes become install scripts: the current
`recipes/` Python package retires once the language can express the
FreeDOS plain install end to end. Media acquisition (download,
hash-verify, cache under `media/`) stays a host-side capability the
language can invoke, with pinned hashes kept alongside the script.

## Milestones

### Milestone 1 — FreeDOS plain install to hard disk (finish as-is)

Unchanged in substance and nearly done on the current stack; it
remains the proving ground for scripted installation. Remaining
steps:

1. Script the installer's "Plain DOS system" path onto the target
   disk (the LiveCD boots to a live `D:\>` prompt; `SETUP.BAT`
   starts the installer). Watch guest memory: the LiveCD warns about
   limited RAM at the 16 MiB DOS default.
2. Add a verification pass that boots the installed disk and
   confirms a DOS prompt.

The recipe's current shape (Python module under `recipes/`,
`reliquary install freedos-plain`) is acknowledged as transitional.

### Milestone 2 — The machine model

Machine homes under `machines/<name>`, the `reliquary-machine.json`
spec (declared + learned sections), the `media/` and `scripts/`
home layout, and the machine-scoped CLI grammar (`create`, `start`,
`stop`, `delete`). The QEMU machine layer is re-anchored on machine
homes; `MachineConfig`/root-home `machine.json` are absorbed into
the spec (single source of truth, maintained by reliquary after
creation).

### Milestone 3 — The backend adapter seam

Define the backend adapter API from the reshaped QEMU
implementation (the only adapter with a complete control plane set), add
backend autodiscovery and the prioritized default list, and record
assigned backends into machine specs. Non-QEMU adapters may stub
with `NotImplementedError`, mirroring how platforms are handled.

### Milestone 4 — The scripting language

Design and implement the language MVP covering the primitive
vocabulary above; re-express the FreeDOS plain install as an
install script; retire `recipes/`.

### Milestone 5 — Second backend

Implement the first non-QEMU adapter end to end, proving the
adapter API against a genuinely different hypervisor. VirtualBox is
the recommended candidate: `VBoxManage` covers lifecycle, keyboard
scancodes, screenshots, and serial redirection, which is the
closest match to the control plane set scripts already rely on. The
FreeDOS install script running unmodified on both backends is the
acceptance test.

### Milestone 6 — Guest agent communication

The QGA-profile client and guest agents, per the design below —
now explicitly backend-portable over serial.

## Design principles

- **One script, one target.** Each OS version and edition gets one
  install script. Avoid parameterized mega-scripts that mutate
  behavior based on flags.
- **Installation media is input, disk images are output.** Install
  scripts consume vendor media and produce bootable machines. They
  are not runtime configuration generators.
- **Backends are adapters, never leaky defaults.** No feature may
  work only on one backend without the capability being declared;
  scripts and platform workflows target capabilities, not
  hypervisors.
- **Nothing is inferred from guests.** Platform and backend come
  from the machine spec. Probes choose among configured control planes;
  they never guess what OS is inside.
- **Dependencies must pull their weight** (per AGENTS.md).

## Guest communication design

Status: bootstrap direction established on QEMU. The `GuestExec`
protocol, isolated agentless adapter, and its use by the DOS
workflow are implemented; later adapters and their implementation
details remain open. This section is QEMU-first but its seams are
backend-neutral: `GuestExec` and the control plane vocabulary apply to
every backend adapter, and the serial-carried QGA-profile agent is
the portable piece. This document does not by itself authorize
further implementation.

### Purpose

reliquary needs to support modern guests without weakening its
permanent agentless DOS path. The current DOS interaction combines
QMP keyboard events with VGA text-memory inspection. Future guests
may instead expose a serial console, a service over virtio-serial,
or QEMU Guest Agent (QGA).

These mechanisms should be isolated, but they should not be forced
behind one false "control plane" interface. They differ in both shape and
capability:

- keyboard input and VGA inspection are independent, host-mediated
  capabilities rather than a duplex byte stream;
- a serial port and a virtio-serial port carry bytes but define no
  command, completion, or file-transfer semantics;
- QGA is a structured request/reply protocol, normally carried over
  a virtio-serial port, with command and file operations defined by
  the guest agent.

QMP remains the QEMU adapter's management interface. Some control
planes use QMP operations, but QMP itself is not a guest
communication strategy. Other backends have their own management
interfaces (`VBoxManage`, `vmrun`, WMI) with the same rule: the
management interface and the control planes are distinct.

#### Limits of management-interface-only automation

Management-interface-only interaction (QMP on QEMU, and its analogues
elsewhere) is not a useful general automation path for Win9x,
Windows NT, Linux, or BSD guests. It can provide lifecycle control,
keyboard and pointing-device input, screenshots, and other
machine-level observations, which can automate bounded firmware,
installer, recovery, or GUI scenarios when reliquary knows the
exact screen sequence.

It does not provide the primitives needed for reliable general
guest automation: a stable textual output stream, command
completion and exit status, structured errors, or live file access.
Modern graphical and framebuffer consoles also cannot be read
through the DOS VGA text-memory technique. Screenshot recognition
or OCR could observe them, but would be a brittle UI-automation
control plane rather than a substitute for an OS communication protocol.

Linux and BSD can be useful through a configured serial console,
and modern guests through a guest agent, but those cease to be
management-interface-only communication. reliquary keeps agentless
interaction for the DOS workflow and bounded machine-level
automation; it is not the general fallback for modern platforms.

### Vocabulary

Keep three layers distinct:

1. **Carrier** — how bytes or device events cross the VM seam: QMP
   keyboard events, VGA memory, a VNC connection, an emulated UART,
   or a virtio-serial port.
2. **Protocol** — the meaning and framing carried over that
   mechanism: an interactive console or QGA JSON messages. A raw
   serial carrier has no protocol by itself.
3. **Guest integration** — what must exist in the guest: nothing
   for the keyboard/VGA/VNC paths, an OS-configured serial console
   or listener for serial, a virtio driver plus a QGA-compatible
   listener, or the upstream QGA implementation where the guest
   supports it.

A **control plane** composes the required carriers and protocol and
presents useful capabilities to a platform workflow. Configuration
selects a control plane, not merely a device type such as
`virtio-serial`.

### Control plane families

#### Agentless display console

The existing DOS path is the first real control plane. On QEMU it
combines:

- QMP `send-key` for input;
- VGA text-memory inspection for textual output and completion
  detection;
- QMP `screendump` as an independent diagnostic capability; and
- vvfat staging and write-back as an independent file-exchange
  mechanism.

It has no guest prerequisite and remains the DOS default and
fallback. It is not accurately modeled as a stream: output is a
sequence of screen snapshots, and keyboard input is independent of
that output. VGA text-memory inspection is QEMU-specific; other
backends implement the agentless display control plane with their native
input injection and screenshot capture, which for text readback
means pixel-level recognition — acceptable for fixed-font text
modes, and a per-backend implementation detail behind the same
control plane.

#### VNC

A separate agentless control plane: framebuffer output plus keyboard (and
pointer) input over the VNC protocol. QEMU, VirtualBox (extension
pack), and VMware Workstation can expose VNC servers; Hyper-V
cannot. VNC gives a backend-independent wire for display automation
where available, at the cost of pixel-level text recognition. It is
diagnostic and installer-automation machinery, not a general guest
communication path.

#### Serial console

An emulated UART connected to a host endpoint supplies a duplex
byte stream on every backend. Many operating systems already
contain UART drivers, so a custom driver is not inherently
required. The guest must nevertheless attach a console, shell, or
listener to the selected port before reliquary can do useful work.

A serial-console protocol may provide text input, streamed text
output, and prompt-based completion. It does not inherently provide
structured command results or file transfer. A custom listener
could add those operations, but that would be a separate protocol
carried over serial.

#### Guest agents

Structured guest protocols with command execution and file
operations:

- **QGA** on QEMU, usually over a named virtio-serial port. Support
  must depend only on QEMU's published guest-agent protocol, never
  on a particular downstream agent project.
- **Backend-native agents** — VirtualBox Guest Additions guest
  control, VMware Tools guest operations, Hyper-V PowerShell
  Direct / integration services — wrapped by their backend adapter
  where they earn their keep.
- **The reliquary guest agent** — a portable QGA-compatible profile
  (below) carried over serial, and therefore available on all four
  backends and on guests the native agents do not support.

### A portable automation agent

A host controller paired with guest-resident agents provides
substantial automation value, particularly for Win9x, old Windows
NT, DOS, and other systems on which vendor agents are unavailable.
This is a well-established architecture rather than a new category
of system:

- [QGA](https://www.qemu.org/docs/master/interop/qemu-ga-ref.html)
  provides synchronized request/reply messaging, capability
  reporting, command execution, exit status, and file operations;
- [VirtualBox Guest Control](https://docs.oracle.com/en/virtualization/virtualbox/7.0/user/vboxmanage.html)
  uses Guest Additions for host-initiated process and file
  operations;
- [Hyper-V integration services](https://learn.microsoft.com/en-us/windows/win32/hyperv_v2/integration-services-classes)
  expose guest services such as host-to-guest file copying;
- [SPICE vdagent](https://www.spice-space.org/agent-protocol.html)
  defines a framed protocol over a named virtio-serial port; and
- [libguestfs](https://libguestfs.org/guestfsd.8.html) uses RPC
  between a host library and `guestfsd` over virtio-serial.

The host side should normally be a client module inside reliquary,
not another long-running host agent. The backend owns the carrier
endpoint and reliquary owns the VM lifecycle. The guest side is the
resident agent or listener that turns protocol requests into native
OS operations.

#### Chosen target: a QGA-compatible execution profile

The gold-standard execution interface is QGA `guest-exec`. The
first guest implementations should provide a small, portable
profile of the published QGA protocol rather than a
reliquary-specific wire protocol. A guest implementation for an
unsupported OS may implement only the profile while reporting its
actual command set through `guest-info`. reliquary then depends on
the QGA wire contract, not on one particular guest implementation.

The initial profile consists of:

- `guest-sync-delimited` for reconnect and stale-stream recovery;
- `guest-ping` and `guest-info` for readiness and capability
  discovery;
- `guest-exec` and `guest-exec-status` for process completion,
  output, and exit status.

Bounded `guest-file-*` operations are the next capability, not a
prerequisite for proving execution. The existing staged-media path
can bootstrap the guest agent until live file operations exist.

The preferred compatibility level is the actual QGA request and
response shapes over the serial byte stream. A minimal subset is
still QGA-compatible: unsupported commands are omitted or disabled
in `guest-info`. A serial-specific protocol that merely maps to a
similar host result is a last resort, because it would require
another host adapter and would not be a drop-in replacement for
QGA.

The same profile can be carried over an emulated UART on systems
without virtio support and over virtio-serial where it exists. QGA
itself already supports both virtio-serial and ISA serial carriers,
so this does not require transport-specific protocol semantics.
Because every supported backend can expose an emulated UART, the
serial-carried profile is the backend-portable execution path.

#### Serial-to-virtio bootstrap

The development sequence deliberately bootstraps richer guest
integration from the permanent agentless base:

1. The keyboard/VGA and staged-media workflow boots the legacy
   guest, installs the serial listener, and starts it.
2. A minimal guest agent speaks the QGA execution profile over an
   emulated UART. The guest initially needs only its native or
   purpose-built UART support, a QGA message parser, and an OS
   execution adapter.
3. That control plane is used to develop and test the guest's
   virtio-serial driver.
4. The unchanged QGA message and execution layers are moved onto
   the virtio-serial carrier.
5. Additional QGA commands are added by capability, without
   changing the execution interface or carrier seam.

The guest implementation should therefore have three internal
seams:

- a carrier adapter that only reads and writes bytes;
- a QGA profile module that owns framing, synchronization,
  messages, and capability reporting; and
- an OS execution adapter that launches a native command and
  reports its state and result.

The host mirrors this separation: reliquary's QGA client owns
protocol behavior, while backend lifecycle configuration owns the
host endpoint and selected UART or virtio-serial device. Platform
workflows consume execution results and do not need to know which
carrier delivered them.

##### Provider topology

At reliquary's guest-execution seam, the waterfall consists of
control planes satisfying the same `GuestExec` interface; on QEMU:

1. standard QGA guest-exec;
2. the legacy agent over a named virtio-serial port;
3. the legacy agent over an emulated UART; and
4. agentless DOS execution through keyboard input, screen
   observation, and staged media.

The names above identify control plane roles, not committed Python class
or public configuration names. Each control plane owns its provisioning
requirements, readiness probe, endpoint selection, execution
lifecycle, and failure diagnostics. The waterfall selects the first
ready control plane that supplies the capabilities required by the
workflow. Other backends assemble their own waterfalls from the
control planes they support; the serial-carried profile and the agentless
display control plane are the common members.

Multiple control planes do not imply multiple copies of the protocol
implementation. The QGA-speaking control planes share one deep QGA client
module for framing, synchronization, capability discovery,
`guest-exec`, status polling, and result decoding; they configure
different carriers and endpoints around that shared implementation.
The agentless control plane has a genuinely different implementation
behind the same execution interface.

`GuestExec` is currently a runtime-checkable `typing.Protocol` with
`wait_ready(timeout)` and `execute(command, timeout)`. The first
implementation models the readiness and command-completion
semantics already available from the agentless DOS workflow. Before
a QGA control plane is added, extend this narrow interface with
deliberate request and result types covering deadlines, completion,
output, and exit status without exposing QGA transport objects.
Control-plane-specific limitations, such as unavailable exit status or
separate standard-error capture, must be explicit capabilities or
result states rather than invented values.

By default, the DOS agent selects its carrier once at startup. It
first probes for the named virtio-serial port and verifies that the
port can actually be opened and used. If that probe fails, it opens
the configured UART instead. Checking only that a virtio driver is
resident is insufficient because the device or named port may be
absent or unusable.

During the transition, reliquary configures both guest devices and
their host endpoints. The host QGA client probes the corresponding
endpoints in the same order, synchronizes with the one on which the
agent responds, and locks that carrier for the VM's lifetime.
Explicit UART-only and virtio-serial-only modes remain useful for
testing and diagnosis.

Carrier fallback occurs only during startup, before command
dispatch. Neither side switches carriers after a command has begun
or retries that command on the other carrier; doing so would make
execution-at-most-once ambiguous. A VM restart permits a fresh
carrier probe.

The DOS guest still has one QGA profile and execution
implementation. Its UART driver is replaced by a virtio-serial
driver without replacing the agent above it.

A minimal DOS listener that conforms to the QGA wire contract is
already a real, limited QGA-compatible guest agent even when it
runs over UART. The long-term goal is the same DOS agent, with a
progressively broader QGA command set, running over native DOS
virtio-serial support. Virtio is the preferred final carrier, not
what makes the agent QGA-compatible.

If the serial stepping stone cannot speak the QGA profile and
requires a genuinely different wire protocol, only its reliquary
control plane adapter changes; the `GuestExec` interface and waterfall
remain stable. That is the fallback design, not the target.

Legacy execution semantics must be truthful where the OS cannot
implement the full concurrency model. A single-tasking DOS agent
may:

- allow only one command in flight;
- return a synthetic process handle before invoking the child;
- defer status replies while the child owns the machine; and
- capture output through temporary files and return it after
  completion.

Those limitations should be documented and tested as profile
behavior, not hidden behind optimistic capability claims. Win9x,
Windows NT, and multitasking Unix-like guests can implement the
asynchronous process model more closely.

A new protocol becomes justified only if an implementation
experiment proves that QGA semantics cannot meet essential
constraints, such as memory limits on a 16-bit guest, streaming
output, cancellation, or safe recovery after a mid-command
disconnect. In that case, retain the proven elements: framed
requests, correlation identifiers, version and capability
negotiation, bounded payloads, explicit error categories,
duplicate-request handling, and an unambiguous distinction between
transport failure and command completion.

Never retry an execution request automatically unless the protocol
can prove that the guest did not begin it. At-most-once execution
and reconnect behavior are part of the protocol interface, not
incidental host-client details.

### Capability-oriented platform workflows

Platform workflows own OS meaning: provisioning, readiness, command
syntax, completion, and result collection. Control planes own
communication mechanics and protocol details. The seam between them
should be expressed in terms of the smallest capabilities workflows
actually need, not one broad interface every control plane must pretend
to implement.

Candidate capabilities are:

- text or key input;
- screen snapshots;
- a duplex byte stream;
- structured command execution;
- guest file read/write; and
- screenshots for diagnostics.

The list is a design inventory, not a commitment to six public
classes. Add a seam only when two real control planes need to satisfy the
same workflow capability. Until then, keep control plane details private
to their platform workflow.

In particular, screenshots remain a management-interface
diagnostic regardless of the selected control plane. They are
explicitly outside the `GuestExec` protocol: using QGA for
execution does not affect screenshot availability, and a control plane
does not implement or advertise screenshots. Orchestration may
capture them internally when useful, while the existing direct-use
screenshot surface remains independent. File exchange should not be
bundled into a console abstraction: vvfat and QGA file operations
have different lifecycle and consistency rules.

The QEMU `Machine` exposes its identity-verified QMP session
through `Machine.qmp()`. Raw QMP `cmd()` and HMP `hmp()` operations
remain available to embedding callers. Control planes receive a `Machine`
and use this public seam; they do not connect to QMP directly or
duplicate monitor methods on their own interfaces.

### Configuration and lifecycle

Platform selection and the allowed control plane policy must be explicit
through the machine spec or per-invocation configuration. reliquary
must never infer the platform from the guest image, screen, or
device behavior; capability probes only choose among control planes
already permitted by that policy. The current DOS default remains
the agentless display-console control plane. Once guest-agent support
exists, the intended DOS automatic policy is an explicitly
configured ordered readiness waterfall:

1. probe the standard QGA endpoint;
2. probe the legacy agent's named virtio-serial endpoint;
3. probe the legacy agent's UART endpoint; and
4. fall back to the agentless keyboard/VGA workflow.

The first three candidates may all use the same host QGA-profile
client. If a QGA-compatible DOS agent uses the standard QGA
endpoint, the first two steps collapse: reliquary neither needs nor
tries to distinguish the upstream QGA binary from another
conforming implementation.

An endpoint is ready only after `guest-sync-delimited` succeeds and
`guest-info` advertises the commands required by the workflow. A
connected host socket, an attached device, or resident guest driver
is not proof that a compatible listener is servicing the endpoint.
Each unsuccessful probe uses a bounded part of the overall startup
deadline.

The selected candidate is reported in diagnostics and remains fixed
after the first command is dispatched. A timeout or transport
failure after dispatch must surface as an ambiguous execution
failure; reliquary must not resend the command through the next
candidate. The agentless final fallback applies only to platform
workflows, currently DOS, that explicitly support keyboard and
screen automation. It is not a general fallback for modern guests.

A control plane may need two lifecycle phases:

1. contribute validated backend launch configuration for its
   carrier and host endpoint before the machine starts; and
2. connect to that endpoint and establish protocol readiness after
   startup.

Endpoint paths and other persistent artifacts must remain under the
machine home. Ownership verification remains mandatory for every
management-interface operation, including operations used by the agentless
control plane.

Automatic fallback must be conservative. It may select another
configured control plane only before a guest command has been dispatched.
Retrying through a fallback after an ambiguous transport failure
could execute a command twice. The selected control plane and fallback
decision should be visible in diagnostics.

## Roadmap constraints

Agentless DOS operation on QEMU is the permanent base described in
AGENTS.md; no milestone may weaken it.

The declared-media convention (drives named by medium, slot, and
format) carries over into machine homes and machine specs. New
media kinds, controllers, and USB devices must extend the same
convention — a new medium name — not appear as opaque raw backend
arguments.

The bootstrap direction is important: agentless reliquary is the
rig used to test the DOS drivers and guest agent before those
components exist. Once available, the same suites should validate
agentless and guest-agent control planes with equivalent results.

## Decisions still needed

- **Backend priority order** for default assignment when a spec
  names no backend (proposed: QEMU, VirtualBox, VMware Workstation,
  Hyper-V — best scriptability first).
- **Scripting language shape**: line-oriented imperative DSL,
  structured step documents, or a constrained expression syntax —
  and how timeouts, retries, and conditionals are written.
- **Spec details**: whether per-drive backend settings are ever
  needed beyond the top-level `backend-settings` scope, and how
  running-machine reconfiguration (hot media changes vs.
  stopped-only changes like memory) is surfaced in the CLI and
  script language.
- **Hyper-V agentless screen strategy**: whether WMI thumbnail/
  keyboard automation is good enough for installer scripting or
  Hyper-V machines require the serial/agent control planes from day one.
- **Media catalog shape** under `media/`: whether pinned hashes and
  download URLs live beside install scripts, in a manifest per
  media item, or both.
- **Concurrent machines**: locking per machine home, and whether
  several named machines may run at once from one reliquary home
  (the per-home identity model suggests yes, per-machine).
- The exact initial `guest-exec` subset, including argument and
  environment support, capture modes, output limits, timeouts, and
  legacy-OS deviations.
- Which bounded `guest-file-*` operations follow execution,
  including file consistency and atomic replacement semantics.
- Whether a separate plain serial-console control plane remains useful
  once the QGA-compatible serial listener exists.
