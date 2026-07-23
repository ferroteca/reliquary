<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Principles

> **Status:** the itemized governing principles — P-numbered so
> use cases, decisions, designs, and commits can cite them.
> Principles feed into the use cases
> ([planning/USE-CASES.md](planning/USE-CASES.md)) and the
> decisions
> ([planning/DECISIONS.md](planning/DECISIONS.md)); use cases
> and decisions name the principles they serve — and principles
> drive work directly: a roadmap item or task may be demanded
> by a principle just as by a use case, citing its P-number.
> Each entry indexes
> the principle at its normative home — the pointer is where
> the full prose lives. This list is a claim: every principle
> here is real — the project honors it as the code stands
> today (it lives at the root for that reason). A proposed or
> not-yet-honored principle lives in
> [planning/PRINCIPLE-PROPOSALS.md](planning/PRINCIPLE-PROPOSALS.md)
> instead, with no placeholder here, under the same global
> P-numbering; amendments are argued like interface changes
> and recorded in DECISIONS.md.

- **P1 — Machines are ephemeral.** A machine exists to run its
  task and is cheap to destroy and rebuild; the machine is
  never the product. (ROADMAP "Vision"; prose below.)
- **P2 — Agentless operation is permanent.** No feature may
  depend on guest cooperation; agentless is the default and
  the fallback, forever. (AGENTS.md "Agentless operation".)
- **P3 — The control-plane arc.** Agentless operation prepares
  a guest; once a native agent exists inside it, that agent is
  the better work plane. Reliquary consumes native guest
  agents and never builds its own. (Prose below.)
- **P4 — The artifact-residency split.** The home serves human
  CLI convenience; automation artifacts are source code in the
  consuming project's tree and never live in the home; the
  codex never feeds automation. (Prose below.)
- **P6 — One semantic surface.** The CLI and the embedding API
  are twin presentations of one surface: every command is its
  API twin, nothing is CLI-only, and no capability is
  unreachable from the CLI. (AGENTS.md "CLI–API parity";
  INTERFACES.)
- **P7 — The binding constraint.** Nothing may be hard to
  express in a common binding language (C, Java), and the
  CLI — the fallback binding for every unbound language — must
  never be hard to drive from a program. (INTERFACES.)
- **P8 — Interface changes are vetted.** Every
  interface-changing decision triages by its impact on the use
  cases, under the interface-change rule. (INTERFACES.)
- **P9 — No backward compatibility before 1.0.** Changes land
  coherently and completely; the old shape is deleted, never
  bridged. Through beta and the rest of pre-1.0 a cushion may be
  granted when warranted and cheap — never promised, never
  accumulated. (AGENTS.md.)
- **P10 — Nothing is inferred from guests.** Platform and
  backend come from the blueprint; probes select among
  configured control planes, never guess what is inside.
  (AGENTS.md "Platform selection"; ROADMAP "Design
  principles".)
- **P11 — Capability honesty.** Backends and control planes
  report what they can do; nothing is emulated, and a
  capability gap fails closed naming itself. (ROADMAP "Backend
  adapters".)
- **P12 — Home containment.** All persistent state lives under
  the Reliquary home (the cache separable); Reliquary never
  writes beside the module or into a source repository in
  normal use. (AGENTS.md "Home-directory containment".)

## The cross-cutting prose

Moved from the use-case list (2026-07-23; talk of seams, axes,
models, and concepts is principle material, not a use case) —
normative here. "Them" below is the use cases; the U-numbers
cited live in USE-CASES.md and USE-CASE-PROPOSALS.md under the
shared namespace.

Beneath them all sits the ephemeral-machine principle (P1):
machines
are cheap to destroy and rebuild, and the machine is never the
product (planning/ROADMAP.md, "Vision"). Across them runs a control-plane
arc (P3): agentless operation is at its most useful preparing a
machine — installing the OS (U1) and bringing the guest to the
point where an agent exists inside it — and for testing
installations themselves, os-autoinst-style, where the install is the
thing under test and the screen is the assertion surface. Once a
guest holds an agent, that agent is the better work plane (U3);
agentless remains the permanent fallback for guests that can
never cooperate. Reliquary consumes native guest agents and
never builds its own: agents may not exist for some operating
systems, but writing one would be a whole project unto itself,
outside Reliquary's scope.

Alongside it runs an artifact-residency split (P4). Assets in
the
Reliquary home are a convenience for human CLI interaction: users
get a convenient home for shared assets — blueprints, media
definitions, and scripts reused across human-interaction
scenarios — seeded by the codex (U1, U5). The other side of the
coin: for automation, scripts, blueprints, and landmark assets
are source code artifacts — they belong to the consuming
project, live in its source control, and never
live in Reliquary's home (U3, U4). The codex is *never* used for machine
automation — that would be a trap: a blueprint changing outside
the project's source control breaks the project. For automation
the library is at most a place to copy a first draft from; the
copy is committed into the project and evolves there. The first
drafts are likely generated by a person
hand-driving Reliquary (U6), but the output goes into source
control and evolves there. Either way the home remains
Reliquary's own ground — caches, machines, the personal
user-properties file — so a project's artifacts must work in
place: runnable
from the source tree, with nothing copied into a home to make
them usable. One cache artifact is disposable without being
reconstructible: run records are evidence, not regenerable
output. Their contents are delivered live to whoever drives the
run (the feedback split, P5), and the record is retained for
its machine's life; durability beyond the machine is the
consumer's claim — copy the record out while the machine exists
(U3, U4).

Proposed changes to this list — new principles, absorptions,
retirements — are tracked in
[planning/PRINCIPLE-PROPOSALS.md](planning/PRINCIPLE-PROPOSALS.md).
