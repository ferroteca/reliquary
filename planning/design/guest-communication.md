<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Guest communication

> **Status:** this document designs how Reliquary talks to a guest
> operating system. It defines three terms — carrier, protocol, and
> guest integration — sorts the ways of talking to a guest into
> control-plane families, states the rule that Reliquary only ever
> uses guest agents that already exist and never writes its own
> (ARCHITECTURE.md P3), and defines how control planes offer their
> capabilities to platform workflows. The `GuestExec` protocol, the
> isolated agentless adapter, and its use by the DOS workflow are all
> built. Later control planes, and their implementation details,
> remain open questions. This design is QEMU-first but not
> QEMU-only: `GuestExec` and the control-plane vocabulary apply to
> every backend adapter ([backend-adapter.md](backend-adapter.md)).
> Control planes built on native guest agents remain **backlog
> work** (planning/proposed/FEATURES.md F4 "Guest agent
> communication"). The VNC plane's screen-and-keyboard half is
> **delivered on QEMU** (F63; the decisions behind it are recorded
> in D110, and the rule it follows is in
> docs/spec/blueprint-model.md), while pointer input and the rest of
> the GUI era remain proposed (F5). This document does not by itself
> authorize building anything further.

## Purpose

Reliquary needs to support modern guests without weakening its
permanent agentless DOS path. DOS interaction today combines QMP
`send-key` events with reading text straight out of VGA memory.
Future guests may instead expose a serial console, a service running
over virtio-serial, or the QEMU Guest Agent (QGA).

These mechanisms need to stay isolated from each other, but they
shouldn't be forced behind one shared "control plane" interface that
pretends they're all the same shape. They aren't — each differs in
both what it looks like and what it can do:

- Keyboard input and reading VGA memory are independent capabilities
  mediated by the host. Neither is a duplex byte stream.
- A serial port or a virtio-serial port carries raw bytes, but
  defines no notion of a command, its completion, or file transfer —
  those meanings have to come from something built on top.
- QGA is a structured request/reply protocol, normally carried over
  a virtio-serial port, with commands and file operations defined by
  the guest agent itself.

QMP is the QEMU adapter's management interface — the channel it uses
to run the machine. Some control planes happen to use QMP operations,
but QMP itself is not a guest-communication strategy. Other backends
have their own management interfaces (`VBoxManage`, `vmrun`, WMI),
and the same rule holds for each: the management interface and the
control planes built on top of it are two different things.

### What management-interface-only automation can't do

Talking to the guest only through the management interface — QMP on
QEMU, or the equivalent elsewhere — is not a workable general
automation path for Win9x, Windows NT, Linux, or BSD guests. It can
give lifecycle control, keyboard and pointing-device input,
screenshots, and other machine-level observations. That's enough to
automate a bounded firmware, installer, recovery, or GUI scenario
when Reliquary already knows exactly what sequence of screens to
expect.

It does not give what reliable *general* guest automation actually
needs: a stable stream of text output, a way to know when a command
finished and what its exit status was, structured errors, or live
file access. Modern graphical and framebuffer consoles also can't be
read the way DOS's VGA text memory can — you'd need screenshot
recognition or OCR to watch them, and that would be a brittle
UI-automation control plane, not a real substitute for an actual OS
communication protocol.

Linux and BSD guests become genuinely useful once a serial console is
configured, and modern guests once a guest agent is running — but at
that point they've stopped being management-interface-only
communication. Reliquary keeps agentless interaction as the permanent
answer for the DOS workflow and for bounded machine-level automation.
It is not meant as the general fallback for modern platforms.

## Vocabulary

Keep three layers distinct:

1. **Carrier** — how bytes or device events actually reach the guest,
   crossing the boundary between Reliquary and the hypervisor
   (ARCHITECTURE.md, "The seams"): QMP keyboard events, VGA memory,
   a VNC connection, an emulated UART, or a virtio-serial port.
2. **Protocol** — the meaning and framing layered on top of that
   carrier: an interactive console, or QGA's JSON messages. A raw
   serial carrier has no protocol of its own until something is
   layered on it.
3. **Guest integration** — what has to already be running inside the
   guest for this to work: nothing, for the keyboard/VGA/VNC paths;
   an OS-configured serial console or listener, for serial; a virtio
   driver plus a QGA-compatible listener, or the guest's own upstream
   QGA implementation where the guest ships one.

A **control plane** combines the carrier and protocol a workflow
needs, and offers the result to that platform workflow as usable
capabilities. Configuration picks a control plane by name — it's not
enough to just name a device type like `virtio-serial`, because that
alone says nothing about which protocol runs over it.

## Control plane families

### Agentless display console

The existing DOS path is the first real control plane. On QEMU it
combines:

- QMP `send-key` for input;
- reading text straight out of VGA memory, for textual output and
  for detecting when a command has finished;
- QMP `screendump` as an independent diagnostic capability; and
- vvfat for files — a host directory presented to the guest as a
  writable FAT drive, proven for DOS-era write patterns. This is
  what a directory-source medium attaches through: a medium whose
  `location` is a directory, with `materialize: use`.

It needs nothing installed in the guest, and it stays the DOS
default and fallback. It doesn't behave like a data stream: its
output is a sequence of screen snapshots, and keyboard input runs
independently of that output. Reading VGA text memory directly is
QEMU-specific. Other backends supply their own native input
injection and framebuffer capture as adapter carriers, and where
there's no native way to read text, this control plane runs **one
shared fixed-font recognizer** over the captured framebuffer instead
(owner, 2026-07-21) — written once and shared by every backend,
never reimplemented per adapter. The fonts it reads through are the
*host's* own, plus whatever font the script's `font` statement
names — **U25**'s answer to a guest that paints in a face the host
doesn't have on hand: an authored font asset, tried first from the
point in the run where the guest takes over the screen. The portable
snapshot format this relies on — character rows plus per-cell
attribute tokens that are opaque but comparable for equality — is
described in [backend-adapter.md](backend-adapter.md).

### VNC

A separate agentless control plane: framebuffer output plus keyboard
(and pointer) input, carried over the VNC protocol. QEMU, VirtualBox
(with its extension pack), and VMware Workstation can all expose VNC
servers; Hyper-V cannot. Where it's available, VNC gives a
backend-independent way to drive display automation, at the cost of
losing pixel-level text recognition. It's diagnostic and
installer-automation machinery, not a general guest communication
path. Its screen-and-keyboard half is delivered on QEMU (F63): the
in-tree RFB client is `src/reliquary/rfb.py`, the QEMU adapter owns
the endpoint and the carriers, and the order backends are preferred
in is normative in docs/spec/blueprint-model.md. The decisions behind
those calls, and the alternatives rejected along the way, are
recorded under D110. Pointer input and the other backends' VNC
endpoints remain part of F5, not yet built.

### Serial console

An emulated UART connected to a host endpoint gives a duplex byte
stream on every backend. Many operating systems already ship UART
drivers, so this doesn't inherently need a custom driver — but the
guest still has to attach a console, shell, or listener to that port
before Reliquary can do anything useful with it.

A protocol built on top of a serial console can provide text input,
streamed text output, and prompt-based completion. It doesn't
inherently provide structured command results or file transfer — a
custom listener could add those, but that listener would itself be a
separate protocol running over serial, not something serial gives
for free.

**A fast file-transfer mechanism, if one is ever built, comes from
outside Reliquary entirely (backlog; owner, 2026-07-24, D36).** A
directory-source drive reboots the machine on every host-side change.
Live media swap (`insert-media`/`eject-media`, U20) avoids the
reboot, but still pays a swap cost on every round trip. Anything
faster than that needs the guest's cooperation, and building that is
**outside Reliquary's scope entirely, on both the host and guest
sides**: Reliquary supplies the drives a file crosses on, and nothing
about what's inside them (**P16**'s file-content carve-out, D108).
The transfer mechanism itself would have to be sourced from outside
— an existing tool first (Kermit-style serial file transfer is the
leading candidate), another existing alternative next, and only as a
last resort a dedicated project — but never built as part of
Reliquary itself. The directory-source drive stays the built-in
agentless fallback (P2). What's driving demand for something faster
is just the swap/reboot cost. **P3 already states this rule**, and
it applies on both sides equally (D68,
[ARCHITECTURE.md](../../ARCHITECTURE.md)): P3's rule against
Reliquary building its own agent covers a host-side agent exactly as
much as a guest-side one. So scheduling this work only decides which
existing transport gets adopted — it never becomes a question of
whether Reliquary is allowed to write one itself.

### Guest agents

Structured guest protocols that support running commands and
transferring files:

- **QGA** on QEMU, usually reached over a named virtio-serial port.
  Support for it has to depend only on QEMU's own published
  guest-agent protocol, never on any particular downstream agent
  project built on top of that protocol.
- **Backend-native agents** — VirtualBox Guest Additions' guest
  control, VMware Tools' guest operations, Hyper-V's PowerShell
  Direct / integration services — each wrapped by its own backend
  adapter, where doing so is worth the effort.

A guest with no native agent isn't a gap Reliquary needs to fill: it
just stays agentless (ARCHITECTURE.md P3 — writing an agent would be
a whole separate project, outside Reliquary's scope).

## Consuming native guest agents

Reliquary only uses guest agents that already exist —
[QGA](https://www.qemu.org/docs/master/interop/qemu-ga-ref.html),
VirtualBox Guest Additions, VMware Tools, Hyper-V integration
services — and never builds or ships an agent of its own, on either
the guest or the host side (ARCHITECTURE.md P3): some operating
systems have no agent, but writing one for them would be a whole
separate project, outside Reliquary's scope. Guests with no native
agent — DOS-era systems above all — are served permanently by the
agentless control planes, including U14's loop.

On the host side, Reliquary only ever runs a client module inside its
own process — never a separate, long-running host agent. That's
where P3's rule actually draws its line: not "host vs. guest" but
"no new standalone agent, on either side." The backend adapter owns
the carrier endpoint, and Reliquary owns the VM's lifecycle. The QGA
client depends only on QEMU's published guest-agent protocol — the
wire format — never on one particular guest-side implementation of
it. Its initial command set is small: `guest-sync-delimited` for
reconnecting and recovering from a stale stream; `guest-ping` /
`guest-info` for checking readiness and discovering what the agent
supports; and `guest-exec` / `guest-exec-status` for running a
process and getting back its completion, output, and exit status.
Bounded `guest-file-*` operations are a capability for later
(planning/proposed/FEATURES.md "Horizon"), not something execution
needs first. Backend-native agents get wrapped by their own backend
adapters the same way, when doing so is worth it, and they expose the
same small set of capabilities to platform workflows.

Agentless operation is also how a guest gets an agent in the first
place: the OS — and its own agent package along with it — gets
installed through the agentless workflow, and only after that does
the agent become the better way to work with the guest (P3). A
control plane only reports the capabilities its agent actually
advertises. Any limitation has to show up as an explicit capability
or result state — never as an optimistic claim that turns out to be
wrong.

`GuestExec` is currently a runtime-checkable `typing.Protocol` with
`wait_ready(timeout)` and `execute(command, timeout)`. Its first
implementation models the readiness and command-completion behavior
already available from the agentless DOS workflow. Before a QGA
control plane gets added, this narrow interface needs to grow
deliberate request and result types that cover deadlines, completion,
output, and exit status — without leaking QGA's own transport objects
out through the interface. Anything a specific control plane can't
do — say, no exit status available, or standard error captured
separately — must show up as an explicit capability or result state,
never as a made-up value standing in for the real one.

Never retry an execution request automatically unless the protocol
can prove the guest never actually started it. At-most-once execution
and how reconnects are handled are both part of the protocol
interface itself — not incidental details left to whatever the host
client happens to do.

## Capability-oriented platform workflows

Platform workflows own what the OS means: provisioning, readiness,
command syntax, how completion is detected, and how results are
collected. Control planes own the mechanics of communication and the
protocol details underneath it. The boundary between the two —
Reliquary calls it a **seam** here too, distinct from the
backend/hypervisor seam above — should be expressed in terms of the
smallest set of capabilities a workflow actually needs, not one
broad interface that every control plane has to pretend to
implement in full.

The candidate capabilities are:

- text or key input;
- screen snapshots;
- a duplex byte stream;
- structured command execution;
- guest file read/write; and
- screenshots for diagnostics.

This list is a design inventory, not a promise to ship six public
classes. Add a new capability to this seam only once two real control
planes both need to satisfy the same workflow requirement. Until
then, keep a control plane's details private to the one platform
workflow that uses it.

In particular, screenshots stay a management-interface diagnostic no
matter which control plane is selected. They're explicitly outside
the `GuestExec` protocol: switching to QGA for command execution
doesn't affect whether screenshots are available, and no control
plane implements or advertises screenshots as one of its
capabilities. Orchestration code may capture a screenshot internally
when that's useful, but the existing direct-use screenshot feature
stays independent of that. File exchange shouldn't be folded into a
console abstraction either: a directory-source drive and QGA's file
operations have different lifecycle and consistency rules, and today
Reliquary only offers the first of the two, since it never reaches
inside a volume (D108).

The QEMU `Machine` object exposes its identity-verified QMP session
through `Machine.qmp()`. Raw QMP `cmd()` and HMP `hmp()` calls stay
available to embedding callers directly. Control planes receive a
`Machine` and use these same public methods — they never connect to
QMP on their own, and they never duplicate monitor methods inside
their own interfaces.

## Configuration and lifecycle

Which platform a machine runs, and which control planes are allowed
for it, must always be stated explicitly — through the machine
blueprint or per-invocation configuration. Reliquary must never guess
the platform by looking at the guest image, the screen, or how a
device behaves. Capability probes only choose among the control
planes that configuration has already permitted. For DOS, the policy
is permanently the agentless display-console control plane, since no
native agent exists for DOS-era guests. For a guest that does have a
native agent, the intended automatic policy is an explicitly
configured, ordered list of things to try: probe the agent's
endpoint first, and fall back to a permitted agentless plane if that
fails — picking the first control plane in that order that's both
ready and supplies the capabilities the workflow needs.

An endpoint only counts as ready once `guest-sync-delimited` has
succeeded and `guest-info` advertises the commands the workflow
needs. A connected host socket, an attached device, or a guest driver
being present is not proof that something compatible is actually
listening on the other end. Each failed probe eats into the overall
startup deadline, but only a bounded amount of it.

Whichever control plane gets selected is reported in diagnostics and
stays fixed once the first command has been sent. If a timeout or
transport failure happens after that point, it has to surface as an
ambiguous execution failure — Reliquary must not resend the command
through the next candidate, because that risks running it twice. The
agentless fallback of last resort only applies to platform workflows
— currently just DOS — that explicitly support keyboard and screen
automation. It is not a general fallback for modern guests.

A control plane can need two separate lifecycle steps:

1. hand over validated backend launch configuration for its carrier
   and host endpoint, before the machine starts; and
2. connect to that endpoint and confirm the protocol is ready, after
   the machine has started.

Endpoint paths and any other files that need to persist must stay
inside the machine's cached materialization directory. Verifying
which machine you're actually talking to stays mandatory for every
management-interface operation, including the ones the agentless
control plane uses.

Automatic fallback has to stay conservative. It may only switch to
another configured control plane before a guest command has actually
been sent — falling back after an ambiguous transport failure risks
running that command twice. Which control plane was chosen, and
whether a fallback happened, should both be visible in diagnostics.

