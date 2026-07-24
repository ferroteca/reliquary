<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Principles

> **Status:** the itemized governing principles — P-numbered so
> use cases, decisions, designs, and commits can cite them.
> Principles feed into the use cases
> ([USE-CASES.md](USE-CASES.md)) and the
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
- **P8 — Interface and principle changes are vetted.** Every
  interface-changing decision triages by its impact on the use
  cases *and the governing principles*, under the
  interface-change rule; a change misaligned with either is
  argued as the amendment it requires — a principle amendment
  as vigorously as a use-case one — never as a feature on its
  own merits. (INTERFACES.)
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
- **P15 — The closed input model.** Everything reaches
  Reliquary through four channels: three authored — **specs**
  carry the data, **scripts** the logic, **properties** the
  values — and one invocation, the **CLI/API** twins, carrying
  the command. The set is closed against *accretion*, not
  against decision: a new input is assigned to an existing
  channel, and a new channel is argued and recorded before it
  exists, never arrived at by naively implementing a small
  request across a stated boundary. (P6 and P7 govern the
  invocation channel; the authored three carry expressive
  ceilings. Prose below; D27.)

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

## The four channels (P15)

Everything reaches Reliquary through four channels and no
others — three authored, one invocation:

| Channel | Carries | Ceiling — what it may say | Closed against |
|---|---|---|---|
| **Specs** `.rlqb` `.rlql` | Topology and content: machines, media, containment, landmarks | Logic-free declarative data; bounded constructs that *enrich values* may be added, expanded by Reliquary | In-tree function objects, string templating, any operator inside `${…}` |
| **Scripts** `.rlqs` | Sequencing, waits, input, branching | A purpose-built line-oriented DSL, growing only under G7 | A second format nested inside it — no JSON islands |
| **Properties** the chain | Values: per-user, per-project, per-run | Declared keys, layered precedence as semantics, repeatable `default=` candidates | Transforms in derivation syntax — permanently out |
| **CLI / API** twins | The command | *Inverted:* every capability reachable, as plain commands and arguments | Not narrowness but cleverness — no capability may need a language to reach it |

The three authored channels are **capped** — each says *no more
than this*, and its failure mode is a language accreting one
justified feature at a time. The invocation channel is
**floored**: P6 requires completeness (no capability
unreachable from the CLI) and P7 requires plainness (never hard
to drive from C, Java, or a shell), so its failure mode is the
opposite — capability that exists but cannot be reached, or
reached only through something too clever to drive from a
program. One principle could not say both, which is why the
authored ceilings and the invocation floor are governed
separately.

All three authored ceilings send computation to the same place,
and that identity is the evidence they are one rule:
**computation lives outside Reliquary, in the caller's own
language.** It is not a Reliquary capability — the embedding
API and the CLI are two doors to it, and the CLI user's host
language is the shell, which P7 already requires be easy to
drive Reliquary from.

The closure is against accretion, not decision. A new input is
assigned to a channel; a new channel is argued and recorded
first. What it guards against is narrow and checkable: **a
small request, implemented naively across a stated boundary,
with the crossing never noticed.** The implementation is not
unskilled — it is *locally correct*, which is exactly why
nothing stops it — but it is naive about the line it crosses.
This is why the lines are written down at all: a boundary
nobody stated cannot be checked against. The precedents all
failed here rather than by decision — nobody set out to build a
template engine — so the principle's work is to manufacture the
moment where the large change is visibly being made, because
that moment does not arrive on its own.

Proposed changes to this list — new principles, absorptions,
retirements — are tracked in
[planning/PRINCIPLE-PROPOSALS.md](planning/PRINCIPLE-PROPOSALS.md).
