<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Roadmap

## Milestone 1 — FreeDOS plain install to hard disk

Script the FreeDOS 1.4 installer's "Plain DOS system" option from the
LiveCD distribution onto a hard-disk image. The goal is a working DOS
boot that demonstrates the full pipeline: media download and
verification, disk image creation, and a scripted installer run
through the machine layer.

### Input

The [FreeDOS 1.4 LiveCD](https://freedos.org/download/) provides the
raw material. The recipe downloads `FD14-LiveCD.zip`, extracts
`FD14LIVE.iso` into the reliquary home
(`<home>/install-media/freedos/`), and deletes the zip; only the ISO
is kept, verified against a pinned SHA-256 on every run. A cached
copy that fails verification is erased and downloaded again.

### Output

A 20 MiB dynamically allocated qcow2 (v3) hard-disk image at
`<home>/machines/freedos-plain/drives/hdd.qcow2` holding an installed
plain FreeDOS system that boots in QEMU through the machine layer and reaches a
native DOS prompt.

### Recipe contract

Each recipe is a module under `reliquary/recipes/`. A recipe module
exports an `install(display=False)` function that resolves its inputs
and outputs
under the reliquary home (see `reliquary/home.py`) and returns a
mapping of the artifacts it produced. Recipe machine directories are
machine homes, so the machine layer can boot the declared drives directly.

The recipe is responsible for:

1. Acquiring and verifying its vendor installation media.
2. Creating the target disk image.
3. Scripting the machine layer to run the vendor installer against the target
   disk (not yet implemented).

### Implementation steps

1. ~~Acquire and hash-verify the LiveCD media; create the blank 20 MiB
   qcow2 target disk; expose `reliquary install freedos-plain`.~~ Done.
2. ~~Extract the LiveCD ISO and boot the machine through the machine layer with
   the ISO and target disk mounted, booting from the CD; block while
   the machine runs and shut it down on any exit, including
   Ctrl-C.~~ Done.
3. Script the installer's "Plain DOS system" path onto the target
   disk (the LiveCD boots to a live `D:\>` prompt; `SETUP.BAT` starts
   the installer). Watch the guest memory size: the LiveCD warns
   about limited RAM at the 16 MiB DOS default.
4. Add a verification pass that boots the installed disk and confirms
   a DOS prompt.

### Decisions still needed

- How the installer's interactive prompts are scripted beyond the
  first-menu `wait_text` / `cursor_menu_select` already in place
  (further screen waits vs. fixed key scripts).
- Whether the CLI supports a `--verify` flag that boots the result
  through the machine layer after installation.

## Design principles

- **One recipe, one target.** Each OS version and edition gets one module.
  Avoid parameterized mega-recipes that mutate behavior based on flags.
- **Installation media is input, disk images are output.** Recipes consume
  vendor media and produce bootable images. They are not runtime
  configuration generators.
- **The machine layer is the guest runtime.** Recipes may use it to
  validate output or to script interactive installers, but recipes do not
  replace its workflows.
- **Stdlib-first.** Avoid dependencies unless a dependency
  justifies itself through real implementation burden.

## Guest communication design

Status: bootstrap direction established. The `GuestExec` protocol, isolated
agentless adapter, and its use by the DOS workflow are implemented; later
adapters and their implementation details remain open. This document does not
by itself authorize further implementation.

### Purpose

reliquary needs to support modern guests without weakening its permanent
agentless DOS path. The current DOS interaction combines QMP keyboard events
with VGA text-memory inspection. Future guests may instead expose a serial
console, a service over virtio-serial, or QEMU Guest Agent (QGA).

These mechanisms should be isolated, but they should not be forced behind one
false "channel" interface. They differ in both shape and capability:

- keyboard input and VGA inspection are independent, host-mediated
  capabilities rather than a duplex byte stream;
- a serial port and a virtio-serial port carry bytes but define no command,
  completion, or file-transfer semantics;
- QGA is a structured request/reply protocol, normally carried over a
  virtio-serial port, with command and file operations defined by the guest
  agent.

QMP remains reliquary's VM control plane. Some communication adapters use QMP
operations, but QMP itself is not a guest communication strategy.

#### Limits of QMP-only automation

QMP-only interaction is not a useful general automation path for Win9x,
Windows NT, Linux, or BSD guests. QMP can still provide lifecycle control,
keyboard and pointing-device input, screenshots, and other machine-level
observations. Those facilities can automate bounded firmware, installer,
recovery, or GUI scenarios when reliquary knows the exact screen sequence.

They do not provide the primitives needed for reliable general guest
automation: a stable textual output stream, command completion and exit
status, structured errors, or live file access. Modern graphical and
framebuffer consoles also cannot be read through the DOS VGA text-memory
technique. Screenshot recognition or OCR could observe them, but would be a
brittle UI-automation adapter rather than a substitute for an OS communication
protocol.

Linux and BSD can be useful through a configured serial console, and modern
guests can be useful through QGA or another guest listener, but those cease to
be QMP-only communication. Accordingly, reliquary should keep QMP-only
interaction for the agentless DOS workflow and bounded machine-level
automation; it should not treat it as the general fallback for modern platform
workflows.

### Vocabulary

Keep three layers distinct:

1. **Carrier** — how bytes or device events cross the VM seam: QMP keyboard
   events, VGA memory, an emulated UART, or a virtio-serial port.
2. **Protocol** — the meaning and framing carried over that mechanism: an
   interactive console or QGA JSON messages. A raw serial carrier has no
   protocol by itself.
3. **Guest integration** — what must exist in the guest: nothing for the
   keyboard/VGA path, an OS-configured serial console or listener for serial,
   a virtio driver plus a QGA-compatible listener, or the upstream QGA
   implementation where the guest supports it.

An **interaction adapter** composes the required carriers and protocol and
presents useful capabilities to a platform workflow. Configuration should
select an interaction adapter, not merely a device type such as
`virtio-serial`.

### Initial adapter families

#### Agentless display console

The existing DOS path is the first real adapter. It combines:

- QMP `send-key` for input;
- VGA text-memory inspection for textual output and completion detection;
- QMP `screendump` as an independent diagnostic capability; and
- vvfat staging and write-back as an independent file-exchange mechanism.

It has no guest prerequisite and remains the DOS default and fallback. It is
not accurately modeled as a stream: output is a sequence of screen snapshots,
and keyboard input is independent of that output.

#### Serial console

An emulated UART connected to a host chardev supplies a duplex byte stream.
Many operating systems already contain UART drivers, so a custom driver is not
inherently required. The guest must nevertheless attach a console, shell, or
listener to the selected port before reliquary can do useful work.

A serial-console protocol may provide text input, streamed text output, and
prompt-based completion. It does not inherently provide structured command
results or file transfer. A custom listener could add those operations, but
that would be a separate protocol carried over serial.

#### Virtio-serial automation

A virtio-serial port supplies a duplex byte stream. It normally requires the
guest's virtio driver and a guest-side listener. Framing, readiness, commands,
results, and file transfer all belong to the protocol implemented by that
listener; none is supplied by virtio-serial itself.

Do not add a bare `virtio-serial` interaction selection. Add a named protocol
only when a concrete guest listener and wire contract exist. The planned use
is to carry the same QGA-compatible profile first proven over an emulated
UART.

#### QEMU Guest Agent

QGA is a structured guest protocol, usually transported over a named
virtio-serial port. Its adapter may expose command execution and file
operations using QGA commands supported by the installed guest agent. QGA
support is optional and must depend only on QEMU's published guest-agent
protocol, never on a particular downstream agent project.

QGA should be named as the selected interaction adapter; its underlying
virtio-serial carrier is an implementation and launch-configuration detail.

### A portable automation agent

A host controller paired with guest-resident agents would provide substantial
automation value, particularly for Win9x, old Windows NT, DOS, and other
systems on which the upstream QGA implementation is unavailable. This is a
well-established architecture rather than a new category of system:

- [QGA](https://www.qemu.org/docs/master/interop/qemu-ga-ref.html) provides
  synchronized request/reply messaging, capability reporting, command
  execution, exit status, and file operations;
- [VirtualBox Guest Control](https://docs.oracle.com/en/virtualization/virtualbox/7.0/user/vboxmanage.html)
  uses Guest Additions for host-initiated process and file operations;
- [Hyper-V integration services](https://learn.microsoft.com/en-us/windows/win32/hyperv_v2/integration-services-classes)
  expose guest services such as host-to-guest file copying;
- [SPICE vdagent](https://www.spice-space.org/agent-protocol.html) defines a
  framed protocol over a named virtio-serial port; and
- [libguestfs](https://libguestfs.org/guestfsd.8.html) uses RPC between a host
  library and `guestfsd` over virtio-serial.

The host side should normally be a client module inside reliquary, not another
long-running host agent. QEMU already owns the carrier endpoint and reliquary owns
the VM lifecycle. The guest side is the resident agent or listener that turns
protocol requests into native OS operations.

#### Chosen target: a QGA-compatible execution profile

The gold-standard execution interface is QGA `guest-exec`. The first guest
implementations should provide a small, portable profile of the published QGA
protocol rather than a reliquary-specific wire protocol. A guest implementation
for an unsupported OS may implement only the profile while reporting its
actual command set through `guest-info`. reliquary then depends on the QGA wire
contract, not on one particular guest implementation, preserving the existing
project constraint.

The initial profile consists of:

- `guest-sync-delimited` for reconnect and stale-stream recovery;
- `guest-ping` and `guest-info` for readiness and capability discovery;
- `guest-exec` and `guest-exec-status` for process completion, output, and
  exit status.

Bounded `guest-file-*` operations are the next capability, not a prerequisite
for proving execution. The existing staged-media path can bootstrap the guest
agent until live file operations exist.

The preferred compatibility level is the actual QGA request and response
shapes over the serial byte stream. A minimal subset is still QGA-compatible:
unsupported commands are omitted or disabled in `guest-info`. A serial-
specific protocol that merely maps to a similar host result is a last resort,
because it would require another host adapter and would not be a drop-in
replacement for QGA.

The same profile could be carried over an emulated UART on systems without
virtio support and over virtio-serial on systems that provide it. QGA itself
already supports both virtio-serial and ISA serial carriers, so this does not
require transport-specific protocol semantics.

#### Serial-to-virtio bootstrap

The development sequence deliberately bootstraps richer guest integration
from the permanent agentless base:

1. The keyboard/VGA and staged-media workflow boots the legacy guest, installs
   the serial listener, and starts it.
2. A minimal guest agent speaks the QGA execution profile over an emulated
   UART. The guest initially needs only its native or purpose-built UART
   support, a QGA message parser, and an OS execution adapter.
3. That channel is used to develop and test the guest's virtio-serial driver.
4. The unchanged QGA message and execution layers are moved onto the
   virtio-serial carrier.
5. Additional QGA commands are added by capability, without changing the
   execution interface or carrier seam.

The guest implementation should therefore have three internal seams:

- a carrier adapter that only reads and writes bytes;
- a QGA profile module that owns framing, synchronization, messages, and
  capability reporting; and
- an OS execution adapter that launches a native command and reports its
  state and result.

The host mirrors this separation: reliquary's QGA client owns protocol behavior,
while lifecycle configuration owns the host chardev and selected UART or
virtio-serial device. Platform workflows consume execution results and do not
need to know which carrier delivered them.

##### Provider topology

At reliquary's guest-execution seam, the waterfall consists of four adapters
satisfying the same `GuestExec` interface:

1. standard QGA guest-exec;
2. the legacy agent over a named virtio-serial port;
3. the legacy agent over an emulated UART; and
4. agentless DOS execution through QMP keyboard input, VGA observation, and
   staged media.

The names above identify adapter roles, not committed Python class or public
configuration names. Each adapter owns its provisioning requirements,
readiness probe, endpoint selection, execution lifecycle, and failure
diagnostics. The waterfall selects the first ready adapter that supplies the
capabilities required by the workflow.

Four interface adapters do not imply four copies of the protocol
implementation. The first three share a deep QGA client module for framing,
synchronization, capability discovery, `guest-exec`, status polling, and
result decoding. The virtio-serial and UART adapters configure different
carriers and endpoints around that shared implementation. The agentless
adapter has a genuinely different implementation behind the same execution
interface.

`GuestExec` is currently a runtime-checkable `typing.Protocol` with
`wait_ready(timeout)` and `execute(command, timeout)`. The first implementation
models the readiness and command-completion semantics already available from
the agentless DOS workflow. Before a QGA adapter is added, extend this narrow
interface with deliberate request and result types covering deadlines,
completion, output, and exit status without exposing QGA transport objects.
Adapter-specific limitations, such as unavailable exit status or separate
standard-error capture, must be explicit capabilities or result states rather
than invented values.

By default, the DOS agent selects its carrier once at startup. It first probes
for the named virtio-serial port and verifies that the port can actually be
opened and used. If that probe fails, it opens the configured UART instead.
Checking only that a virtio driver is resident is insufficient because the
device or named port may be absent or unusable.

During the transition, reliquary configures both guest devices and their host
chardev endpoints. The host QGA client probes the corresponding endpoints in
the same order, synchronizes with the one on which the agent responds, and
locks that carrier for the VM's lifetime. Explicit UART-only and
virtio-serial-only modes remain useful for testing and diagnosis.

Carrier fallback occurs only during startup, before command dispatch. Neither
side switches carriers after a command has begun or retries that command on
the other carrier; doing so would make execution-at-most-once ambiguous. A VM
restart permits a fresh carrier probe.

The DOS guest still has one QGA profile and execution implementation. Its UART
driver is replaced by a virtio-serial driver without replacing the agent above
it.

A minimal DOS listener that conforms to the QGA wire contract is already a
real, limited QGA-compatible guest agent even when it runs over UART. The
long-term goal is the same DOS agent, with a progressively broader QGA command
set, running over native DOS virtio-serial support. Virtio is the preferred
final carrier, not what makes the agent QGA-compatible.

If the serial stepping stone cannot speak the QGA profile and requires a
genuinely different wire protocol, only its reliquary adapter changes; the
`GuestExec` interface and waterfall remain stable. That is the fallback
design, not the target.

Legacy execution semantics must be truthful where the OS cannot implement the
full concurrency model. A single-tasking DOS agent may:

- allow only one command in flight;
- return a synthetic process handle before invoking the child;
- defer status replies while the child owns the machine; and
- capture output through temporary files and return it after completion.

Those limitations should be documented and tested as profile behavior, not
hidden behind optimistic capability claims. Win9x, Windows NT, and
multitasking Unix-like guests can implement the asynchronous process model
more closely.

A new protocol becomes justified only if an implementation experiment proves
that QGA semantics cannot meet essential constraints, such as memory limits on
a 16-bit guest, streaming output, cancellation, or safe recovery after a
mid-command disconnect. In that case, retain the proven elements: framed
requests, correlation identifiers, version and capability negotiation,
bounded payloads, explicit error categories, duplicate-request handling, and
an unambiguous distinction between transport failure and command completion.

Never retry an execution request automatically unless the protocol can prove
that the guest did not begin it. At-most-once execution and reconnect behavior
are part of the protocol interface, not incidental host-client details.

### Capability-oriented platform workflows

Platform workflows own OS meaning: provisioning, readiness, command syntax,
completion, and result collection. Interaction adapters own communication
mechanics and protocol details. The seam between them should be expressed in
terms of the smallest capabilities workflows actually need, not one broad
interface every adapter must pretend to implement.

Candidate capabilities are:

- text or key input;
- screen snapshots;
- a duplex byte stream;
- structured command execution;
- guest file read/write; and
- screenshots for diagnostics.

The list is a design inventory, not a commitment to six public classes. Add a
seam only when two real adapters need to satisfy the same workflow capability.
Until then, keep adapter details private to their platform workflow.

In particular, screenshots remain a machine-level QMP diagnostic regardless
of the selected guest interaction. They are explicitly outside the
`GuestExec` protocol: using QGA for execution does not affect screenshot
availability, and an interaction adapter does not implement or advertise
screenshots. Orchestration may capture them internally when useful, while the
existing direct-use screenshot surface remains independent. File exchange
should not be bundled into a console abstraction: vvfat and QGA file
operations have different lifecycle and consistency rules.

The generic `Machine` exposes its identity-verified QMP session through
`Machine.qmp()`. Raw QMP `cmd()` and HMP `hmp()` operations remain available
to embedding callers. Interaction adapters receive a `Machine` and use this
public seam; they do not connect to QMP directly or duplicate monitor methods
on their own interfaces.

### Configuration and lifecycle

Platform selection and the allowed interaction policy must be explicit through
runner or per-invocation configuration. Reliquary must never infer the platform
from the guest image, screen, or device behavior; capability probes only choose
among adapters already permitted by that policy. The current DOS default
remains the agentless display-console adapter. Once guest-agent support exists,
the intended DOS automatic policy is an explicitly configured ordered
readiness waterfall:

1. probe the standard QGA endpoint;
2. probe the legacy agent's named virtio-serial endpoint;
3. probe the legacy agent's UART endpoint; and
4. fall back to the agentless keyboard/VGA workflow.

The first three candidates may all use the same host QGA-profile client. If a
QGA-compatible DOS agent uses the standard QGA endpoint, the first two steps
collapse: reliquary neither needs nor tries to distinguish the upstream QGA
binary from another conforming implementation.

An endpoint is ready only after `guest-sync-delimited` succeeds and
`guest-info` advertises the commands required by the workflow. A connected
host socket, an attached virtio device, or resident guest driver is not proof
that a compatible listener is servicing the channel. Each unsuccessful probe
uses a bounded part of the overall startup deadline.

The selected candidate is reported in diagnostics and remains fixed after the
first command is dispatched. A timeout or transport failure after dispatch
must surface as an ambiguous execution failure; reliquary must not resend the
command through the next candidate. The agentless final fallback applies only
to platform workflows, currently DOS, that explicitly support keyboard and
screen automation. It is not a general fallback for modern guests.

An adapter may need two lifecycle phases:

1. contribute validated QEMU launch arguments for its carrier and host
   endpoint before QEMU starts; and
2. connect to that endpoint and establish protocol readiness after VM startup.

Endpoint paths and other persistent artifacts must remain under the explicit
reliquary home. QMP identity verification remains mandatory for every QMP
operation, including operations used by the agentless adapter.

Automatic fallback must be conservative. It may select another configured
adapter only before a guest command has been dispatched. Retrying through a
fallback after an ambiguous transport failure could execute a command twice.
The selected adapter and fallback decision should be visible in diagnostics.

### Recommended implementation sequence

1. **Implemented:** name the existing keyboard/VGA composition as the
   agentless display-console adapter internally, preserving the DOS behavior
   and default.
2. **Implemented:** pass that adapter into the DOS workflow so DOS behavior
   stops importing concrete keyboard and screen functions directly.
3. **Implemented:** define the runtime-checkable `GuestExec` protocol in its
   own module and isolate `AgentlessGuestExec` in its own source file.
4. Add the host QGA-profile client with explicit synchronization, readiness,
   and supported-command checks.
5. Build the minimal QGA-compatible serial listener and OS execution adapter;
   use the agentless workflow to stage, start, and test it.
6. Implement the guest virtio-serial driver and move the unchanged profile
   onto that carrier.
7. Add bounded QGA file operations and further commands only as workflows
   require them.
8. Generalize interfaces only from the adapters that now exist. The project is
   pre-release, so prefer a coherent interface over compatibility shims.

### Decisions still needed

- Whether one invocation may configure an ordered adapter preference or only
  one adapter plus the permanent DOS fallback.
- Which platform is the first non-DOS workflow and therefore which shared
  capabilities it actually requires.
- The exact initial `guest-exec` subset, including argument and environment
  support, capture modes, output limits, timeouts, and legacy-OS deviations.
- Whether a separate plain serial-console adapter remains useful once the
  QGA-compatible serial listener exists.
- Which bounded `guest-file-*` operations follow execution, including file
  consistency and atomic replacement semantics.

## Roadmap constraints

Milestone 1 is the permanent agentless base described in AGENTS.md.

The runner surface (see AGENTS.md) is implemented, and the machine's media — floppies, hard disks, and
cdroms, images or virtual FAT directories — are declared by name under `drives/` or through `MachineConfig.drives`
(see "DOS boot and scripting" in AGENTS.md). Further generalization (USB an open question) should extend the same declared-drive
convention — a new medium name — without changing the rest of the surface. New media kinds, controllers, and USB
devices must not first appear as opaque raw `-drive` arguments.

Machine configuration is JSON-only for now. YAML may be added later through a justified parser dependency, but must
normalize through exactly the same `MachineConfig` model and must not introduce YAML-only features. Named profiles,
includes, inheritance, environment interpolation, and multi-file merging are deferred; they would enlarge the
interface without helping describe one machine.

A possible later milestone is an optional QEMU Guest Agent transport over the standard guest-agent protocol. It may
provide `guest-exec` and `guest-file-*` when a DOS guest agent exists, but it must be selectable per invocation and fall back to agentless
behavior. reliquary must depend only on the QEMU-owned protocol, never on a particular downstream agent project.

The bootstrap direction is important: agentless reliquary is the rig used to test the DOS drivers and agent before those
components exist. Once available, the same suites should validate agentless and guest-agent transports with equivalent
results.
