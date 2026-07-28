<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Guest communication

> **Status:** the control-plane design for guest communication:
> the carrier / protocol / guest-integration vocabulary, the
> control plane families, the consume-native-agents-only doctrine
> (ARCHITECTURE.md P3, the control-plane arc), and the
> capability seam between control planes and platform workflows.
> The `GuestExec` protocol, isolated agentless adapter, and its
> use by the DOS workflow are implemented; later control planes
> and their implementation details remain open. QEMU-first but
> backend-neutral: `GuestExec` and the control-plane vocabulary
> apply to every backend adapter
> ([backend-adapter.md](../../planning/pledged/design/backend-adapter.md)). Native-agent
> control planes and the VNC plane are both **backlog work**
> (planning/proposed/FEATURES.md F4 "Guest agent communication" and the GUI
> era), unscheduled since 2026-07-23 (DECISIONS.md D33). This
> document does not by itself
> authorize further implementation.

## Purpose

Reliquary needs to support modern guests without weakening its
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

### Limits of management-interface-only automation

Management-interface-only interaction (QMP on QEMU, and its analogues
elsewhere) is not a useful general automation path for Win9x,
Windows NT, Linux, or BSD guests. It can provide lifecycle control,
keyboard and pointing-device input, screenshots, and other
machine-level observations, which can automate bounded firmware,
installer, recovery, or GUI scenarios when Reliquary knows the
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
management-interface-only communication. Reliquary keeps agentless
interaction for the DOS workflow and bounded machine-level
automation; it is not the general fallback for modern platforms.

## Vocabulary

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

## Control plane families

### Agentless display console

The existing DOS path is the first real control plane. On QEMU it
combines:

- QMP `send-key` for input;
- VGA text-memory inspection for textual output and completion
  detection;
- QMP `screendump` as an independent diagnostic capability; and
- vvfat for files — a host directory presented as a writable
  guest FAT drive, proven for DOS-era write patterns. It is what
  a directory-source media attaches through: a media whose
  `location` is a directory, with `materialize: use`.

It has no guest prerequisite and remains the DOS default and
fallback. It is not accurately modeled as a stream: output is a
sequence of screen snapshots, and keyboard input is independent of
that output. VGA text-memory inspection is QEMU-specific; other
backends supply their native input injection and framebuffer
capture as adapter carriers, and text readback there runs **one
shared fixed-font recognizer** over the captured framebuffer
(owner, 2026-07-21) — a control-plane composition over adapter
carriers, never a per-backend reimplementation. The portable
snapshot contract — character rows plus opaque,
equality-comparable per-cell attribute tokens — is in
[backend-adapter.md](../../planning/pledged/design/backend-adapter.md).

### VNC

A separate agentless control plane: framebuffer output plus keyboard (and
pointer) input over the VNC protocol. QEMU, VirtualBox (extension
pack), and VMware Workstation can expose VNC servers; Hyper-V
cannot. VNC gives a backend-independent wire for display automation
where available, at the cost of pixel-level text recognition. It is
diagnostic and installer-automation machinery, not a general guest
communication path.

### Serial console

An emulated UART connected to a host endpoint supplies a duplex
byte stream on every backend. Many operating systems already
contain UART drivers, so a custom driver is not inherently
required. The guest must nevertheless attach a console, shell, or
listener to the selected port before Reliquary can do useful work.

A serial-console protocol may provide text input, streamed text
output, and prompt-based completion. It does not inherently provide
structured command results or file transfer. A custom listener
could add those operations, but that would be a separate protocol
carried over serial.

**Fast file transport is wholly external (backlog; owner,
2026-07-24, D36).** Agentless vvfat exchange reboots the machine
per file swap; live media swap (`insert-media`/`eject-media`, U20)
avoids the reboot but still pays a swap per round. A transport
faster than that needs guest cooperation and is **outside
Reliquary's scope entirely, host and guest sides alike**:
Reliquary provides only the file-transfer control-plane seam (P17
guest-terms addressing, P11 capability selection), and the
transport itself is sourced externally — an existing tool
(Kermit-style serial file transfer is the candidate) → another
alternative → worst-case a dedicated project — never built here.
vvfat stays the built-in agentless fallback (P2). Demand is the
swap/reboot cost; scheduling it may sharpen P3 from "guest agents"
to "transport agents, host or guest"
([PRINCIPLE-PROPOSALS.md](../../planning/proposed/ARCHITECTURE.md)).

### Guest agents

Structured guest protocols with command execution and file
operations:

- **QGA** on QEMU, usually over a named virtio-serial port. Support
  must depend only on QEMU's published guest-agent protocol, never
  on a particular downstream agent project.
- **Backend-native agents** — VirtualBox Guest Additions guest
  control, VMware Tools guest operations, Hyper-V PowerShell
  Direct / integration services — wrapped by their backend adapter
  where they earn their keep.

Guests without a native agent are not a gap to fill: they stay
agentless (ARCHITECTURE.md P3 — writing an agent would be a
whole project unto itself, outside Reliquary's scope).

## Consuming native guest agents

Reliquary consumes the guest agents that already exist —
[QGA](https://www.qemu.org/docs/master/interop/qemu-ga-ref.html),
VirtualBox Guest Additions, VMware Tools, Hyper-V integration
services — and never builds or ships a guest-side agent of its
own (ARCHITECTURE.md P3, the control-plane arc): agents may
not exist for some operating systems, but writing one would be a
whole project unto itself, outside Reliquary's scope. Guests
without a native agent — DOS-era systems above all — are served
by the agentless control planes permanently, U14's loop included.

The host side is a client module inside Reliquary, never another
long-running host agent: the backend adapter owns the carrier
endpoint and Reliquary owns the VM lifecycle. The QGA client
depends on QEMU's published guest-agent protocol — the wire
contract — never on one particular guest implementation, and its
initial command set is small: `guest-sync-delimited` for
reconnect and stale-stream recovery, `guest-ping` / `guest-info`
for readiness and capability discovery, and `guest-exec` /
`guest-exec-status` for process completion, output, and exit
status. Bounded `guest-file-*` operations are a later capability
(planning/proposed/FEATURES.md "Horizon"), never a prerequisite for
execution.
Backend-native agents are wrapped by their backend adapters
where they earn their keep, behind the same capability seam.

Agentless operation is how a guest reaches its agent in the
first place: the OS — and with it the OS's own agent package —
is installed through the agentless workflow, and then the agent
is the better work plane (P3). A control plane reports the
capabilities its agent actually advertises; limitations are
explicit capabilities or result states, never optimistic claims.

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

Never retry an execution request automatically unless the protocol
can prove that the guest did not begin it. At-most-once execution
and reconnect behavior are part of the protocol interface, not
incidental host-client details.

## Capability-oriented platform workflows

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

## Configuration and lifecycle

Platform selection and the allowed control plane policy must be explicit
through the machine blueprint or per-invocation configuration. Reliquary
must never infer the platform from the guest image, screen, or
device behavior; capability probes only choose among control planes
already permitted by that policy. The DOS policy is permanently
the agentless display-console control plane — no native agent
exists for DOS-era guests. For guests that hold a native agent,
the intended automatic policy is an explicitly configured ordered
readiness waterfall — probe the agent's endpoint, fall back to a
permitted agentless plane — selecting the first ready control
plane that supplies the capabilities the workflow requires.

An endpoint is ready only after `guest-sync-delimited` succeeds and
`guest-info` advertises the commands required by the workflow. A
connected host socket, an attached device, or resident guest driver
is not proof that a compatible listener is servicing the endpoint.
Each unsuccessful probe uses a bounded part of the overall startup
deadline.

The selected candidate is reported in diagnostics and remains fixed
after the first command is dispatched. A timeout or transport
failure after dispatch must surface as an ambiguous execution
failure; Reliquary must not resend the command through the next
candidate. The agentless final fallback applies only to platform
workflows, currently DOS, that explicitly support keyboard and
screen automation. It is not a general fallback for modern guests.

A control plane may need two lifecycle phases:

1. contribute validated backend launch configuration for its
   carrier and host endpoint before the machine starts; and
2. connect to that endpoint and establish protocol readiness after
   startup.

Endpoint paths and other persistent artifacts must remain under the
machine's cached materialization. Ownership verification remains
mandatory for every
management-interface operation, including operations used by the agentless
control plane.

Automatic fallback must be conservative. It may select another
configured control plane only before a guest command has been dispatched.
Retrying through a fallback after an ambiguous transport failure
could execute a command twice. The selected control plane and fallback
decision should be visible in diagnostics.

