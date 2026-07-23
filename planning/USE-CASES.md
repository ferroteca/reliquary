<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Use cases

> **Status:** the use-case list — the current state of
> the decision surface of Reliquary's guiding principles,
> [planning/INTERFACES.md](INTERFACES.md). Every use case here is
> in force. Interface decisions are weighed against this list
> and the accepted proposals under the interface-change rule
> there; proposed changes are tracked in
> [planning/USE-CASE-PROPOSALS.md](USE-CASE-PROPOSALS.md) and
> land here only when delivered — every use case here is met
> by the code today, and a settled use case with unimplemented
> demands lives there instead, with no placeholder here (the
> shared U-namespace keeps its citations valid). When this
> list and planning/ROADMAP.md disagree, the guiding
> principles and this list govern.

Interface decisions are weighed against these. They are numbered
so a decision, review, or spec section can cite the use case it
serves — and so a proposed change can be rejected by naming the
use case it costs. This list is the decision surface: significant
interface changes arrive as proposed amendments to it (see the
[interface-change rule](INTERFACES.md#the-interface-change-rule)),
drafted and tracked in
[planning/USE-CASE-PROPOSALS.md](USE-CASE-PROPOSALS.md), and
moved here when delivered — scheduling in the roadmap is
acceptance; delivery makes it current.

This list is an implementation claim: every use case here is
met by the code as it stands today, in full. A use case with
any unimplemented demand — however settled — lives in the
proposals doc instead, and moves here only when its delivery
lands.

A use case in force is never changed in nature. It may be
**clarified** — an in-place wording edit no past citation would
read differently under; clarify, never change, and an
undelivered clarification may park in the proposals doc — or
**retired**: dropped without
replacement, or **superseded** by one or more new use cases that
carry the need forward in a changed shape. Numbers are permanent
and never reused; proposals share this global namespace and keep
their numbers when they move here. A retired use case leaves
this list entirely — no stub, the same as an undelivered one:
its retirement is recorded in [DECISIONS.md](DECISIONS.md), its
full text survives in git history, and successors name the
number they superseded.

- **U4 — A precisely defined test VM, shared through version
  control.** A developer is writing a program that cannot be
  tested in the work environment — it needs a VM, perhaps running
  a proprietary OS like Windows. The test machine must be
  precisely defined, yet nothing proprietary can be distributed:
  the repository carries only blueprints (media included) and
  Reliquary scripts. Another developer picks up the work
  supplying just the two things the repository cannot provide —
  the Windows install ISO and its license — and the checked-in
  definitions provide everything else needed to build the test
  VM, the media hashes verifying theirs is the exact build the
  scripts target. The checked-in artifacts are source: Reliquary
  uses them from the repository in place — nothing is copied into
  a Reliquary home to make them run. The machine is somewhat expensive to build, so
  the developer keeps it for the duration of the work cycle
  rather than tossing it eagerly; day to day, the tests run
  inside it through U3's loop — the same tool that built the rig
  automates the testing in it. When truly finished, the developer
  disposes of the large VM and reclaims the disk space.
