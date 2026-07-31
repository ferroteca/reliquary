<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Pledged architecture — awaiting delivery

> **Status:** principles the project has **pledged** but does not
> yet honor. Nothing here is in force: a principle only binds once
> it reaches the standing list, and a shortfall against an entry
> below is unbuilt work rather than a bug.
>
> That distinction is the point of this file. **Promotion is what
> arms a principle**: before it, an entry is pledged vision; after
> it, root [ARCHITECTURE.md](../../ARCHITECTURE.md) asserts the thing is
> true of the code, so a divergence becomes a *defect* the
> gap-is-a-bug rule can act on — that rule being stated in the
> root document's own banner (D48).
>
> Three locations hold three states. A principle is drafted in
> [proposed/ARCHITECTURE.md](../proposed/ARCHITECTURE.md), moves here
> when it is pledged, and moves to the root list when the code
> actually honors it. All three share one global P-namespace;
> numbers are permanent, never reused, and no placeholder is left
> behind by either move.
>
> The second move is **automatic on full delivery** (D34): whoever
> lands the work that makes the code honor a principle promotes it
> in the same change — adds it to the standing list, deletes it
> here — rather than holding it for a separate sign-off; the moving
> commit is the record, and no [DECISIONS.md](../DECISIONS.md) entry
> marks a promotion (D63). **A principle's bar is
> *honored as a rule*, not full delivery** (D48): it cannot be
> exhaustively proven, and holding it here until it is perfect
> keeps every shortfall invisible, which is the worse outcome.
> The condition is that every known residue is filed as a defect
> in the same change — that conversion being the whole point of
> arming it. (Full delivery remains the bar for a *use case*,
> which is a discrete journey and can be tested end to end.)
>
> A principle in force is clarified, retired, or superseded — never
> changed in nature. One pledged here may still be reshaped, its
> number intact, with work already scheduled against it re-checked
> in the same edit. A dead proposal is recorded in
> [DECISIONS.md](../DECISIONS.md) and triggers the planning-doc sweep,
> its P-number the search key.

- **P26 — The session layer is the only door.** All consumer API
  interaction passes through a **`Session`**, opened on — at the
  minimum — a home directory; the consumer interacts with the
  session and never the underlying implementations. The CLI is
  the session layer's first consumer: every invocation opens one,
  assigning the default home (`Documents/reliquary`, falling back
  to `~/reliquary`) whenever neither a flag nor the environment
  named one, exactly as the existing default-directory mechanism
  has it (D59's defaulting rule, relocated intact). The session
  carries the ambient state every call is handed today, and
  carries it once — the six placeable directories and the
  selected properties file — so the per-call `context=` and
  `properties_file=` threading and the module-level directory
  globals are superseded, and two sessions in one process are
  unremarkable, which the globals could never say. The boundary
  is ambient state, and it is named: whatever resolves a
  directory, touches machine or media state, or reads ambient
  configuration is reachable only through a session, while pure
  data-in/data-out work — parsing and validating a document or
  script handed to it — stays a free function, so tooling never
  invents a home to parse a string. The vocabulary stays
  importable: the types, the errors, the `Context` record (now
  the session's initialization value), and `default_home_dir()`,
  which is what keeps the CLI's defaulting a capability present
  on both surfaces (P6, D87) after `set_*_dir()` and
  `adopt_environment()` leave the public surface — environment
  adoption becomes the CLI's private construction step. The rest
  of D59 stands: all six directories remain individually
  placeable at the session's door, derivation reaches only what
  is still unassigned, and the API assigns no default — demanding
  the home at construction is the same fail-closed safety moved
  to the door, refusing earlier and still naming what is missing,
  and it retires first-use `dir.unassigned` outright, an assigned
  home reaching all six by derivation. (P6's differing-defaults
  tier is preserved — the CLI assigns, the API demands. P7 shapes
  the object: opened on the plain record D59 settled and
  thereafter an opaque handle every verb hangs off, the shape
  that binds from C where per-call keyword threading does not.
  The carrier session — `Machine.session()`, a live connection to
  a running machine — is a different stratum and keeps its name.
  Supersedes D59's carrier mechanism — per-call `context=`, the
  directory globals, first-use `dir.unassigned` — and none of its
  placement, derivation, or defaulting decisions.)

*(The shelf reopened 2026-07-31 for P26, after four days empty.
Empty remains the healthy state: a principle sits here only in the
window between the project owing it and the code honoring it, and
that window is meant to be short.)*
