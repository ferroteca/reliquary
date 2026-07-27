---
description: Documentation reality and placement rules
---

<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Documentation rules

## Core principle

Documentation in the repository should primarily reflect **current reality** — what exists and works today — not designs, plans, or aspirations.

## Document placement

### Root directory
Root-level documents (README.md, CONTRIBUTING.md, CHANGELOG.md, etc.) must describe the current state of the project. They may occasionally mention future plans in small, clearly-marked asides, but the focus is on what users can do today.

- `ARCHITECTURE.md` — the architecture in force: the whole-system view (what Reliquary is, the seams) and the standing architectural principles (P-numbers). Everything in it is honored by the code today, which is why it lives at the root; forward-looking edges are marked and point at `planning/`. Drafts live in `planning/proposed/ARCHITECTURE.md` and pledged-but-unhonored ones in `planning/pledged/ARCHITECTURE.md` — three locations for three states, because pledging and delivery are different events and only delivery may put an entry here
- `USE-CASES.md` — the use cases in force (U-numbers): every entry is met by the code today, which is why it lives at the root beside ARCHITECTURE.md. Same three states: `planning/proposed/USE-CASES.md`, then `planning/pledged/USE-CASES.md`, then here on full delivery

### docs/ directory
The `docs/` directory describes **the live situation** — functionality that exists and works in the current codebase. Design documents, planned features, and unimplemented interfaces belong elsewhere. It holds three kinds of document, and they are not interchangeable:

- `docs/spec/` — the **normative specifications** of Reliquary's interfaces. These are the authority the implementation answers to, not a description of it: where a spec and the code disagree, the spec is right and the code has a bug, unless the spec is changed first through the interface-change rule. Maintainer-facing and complete — they state every rule, including ones no user needs. **The banner is the marker, the directory is shelving**: every spec declares its standing in its own status banner, every descriptive document names the norm it defers to, and reclassifying is an edit to that statement first. One norm is split across artifact kinds: the blueprint's structure is normed by the published schema, its semantics by `docs/spec/blueprint-model.md` — the blueprint guide, field reference, and cookbook are descriptive. `docs/spec/README.md` says this in full
- `docs/*-reference.md` — **descriptive**, user-facing documentation of the implemented surface. A reference that disagrees with a spec is the reference's bug
- guides — task-shaped, teaching one job end to end, making no completeness claim

**Machine-readable schemas are not documentation.** They are consumed by code — the test suite validates against them and editors bind them — so they ship inside the package at `reliquary/schemas/`, and `docs/spec/` refers to them. The prose is normative; a schema captures only the structural subset a JSON Schema can express, and schema validity never implies document validity. The shared conformance corpus (`reliquary_tests/fixtures/conformance/`) runs every fixture against both parser and schema so the two cannot drift.

### planning/ directory
The `planning/` directory contains maintainer-facing design and planning documents. **The directories are the classification** — a document's location states its standing, and promotion is done by moving it (the commit is the pledge record). `planning/README.md` is the map and the authority on the machinery; the layout:

- `planning/proposed/` — argued but **not pledged**; nothing is worked from here
  - `planning/proposed/USE-CASES.md` — proposed use cases, undelivered clarifications included (shared U-numbering with the root list; the move out of this file is the pledge, delivery moves the entry to root USE-CASES.md; a dead proposal triggers a planning-doc sweep)
  - `planning/proposed/ARCHITECTURE.md` — proposed architecture: drafted principles (shared P-numbering; same lifecycle and sweep as the use-case proposals; principles drive tasks and features just as use cases do) and model changes argued before pledge
  - `planning/proposed/FEATURES.md` — large unbuilt capability, design settled, waiting on the demand that would schedule it
- `planning/pledged/` — approved, and not yet delivered. It holds the **same three filenames** as `proposed/`, because they are the same three artifacts in a later state
  - `planning/pledged/USE-CASES.md` — pledged use cases the code does not yet meet; work may be done from here
  - `planning/pledged/ARCHITECTURE.md` — pledged architecture the code does not yet honor. Not in force: a shortfall against one is unbuilt work, where a shortfall against the root list is a *bug* — promotion is what arms a principle
  - `planning/pledged/FEATURES.md` — pledged-but-unbuilt capability, each carrying the work items that deliver it

The **planning root** holds what has no lifecycle state, because it never moves between the two directories:

- `planning/README.md` — the map, and the authority on the machinery
- `planning/INTERFACES.md` — governing document for world-facing interfaces and the interface-change rule. It is the test a proposal is judged *by*, so it governs `proposed/` as much as `pledged/`
- `planning/DECISIONS.md` — the adjudication record, spanning every state by design: open questions not yet adjudicated, decisions that pledged something, decisions that **refused** it (TASKS.md's Rejected section is a thin index into this file), and a Retired list binding nothing. Numbered D1…; each generally supports use cases or principles; D-numbers justify design choices and code commits
- `planning/TASKS.md` — the third work input queue, beside GitHub issues and `proposed/`: small, **pre-approved** work (entering it is approving it), in no particular order, so anyone may pick up anything. Feature-specific work lives with its feature instead. Work small and obvious enough needs no entry at all (housekeeping, D38)
- `planning/design/` — open design problems and internal engineering doctrine belonging to **no single feature** (the whole-system view itself is root `ARCHITECTURE.md`; the control-plane doctrine `guest-communication.md` lives here because the adapter seam is internal, not a world-facing interface). Feature-specific design does not live here — it lives with its feature, under `planning/proposed/design/` or `planning/pledged/design/`, so a design and the demand it serves move together and a design for a dead proposal is swept with it. Nothing here describes a delivered interface: once an interface ships, its spec is current truth and belongs in `docs/spec/`

## The CHANGELOG

The CHANGELOG is history, not documentation, and follows its own rule:
**never retroactively edit previously released history.** Everything under
a released version header records what was true at release time and stays
byte-for-byte as released — stale paths, broken links, renamed concepts,
and superseded wording included; they are the historical record, and
"fixing" them falsifies it. Corrections and follow-ups get new entries
under the unreleased section, never edits to released text.

The one exception is removing private or legally problematic content:
redact minimally — replace or drop the problematic text, never reword or
modernize around it — and record the redaction as an entry of its own
release. The unreleased section is freely editable until it ships.

## When writing or editing documentation

1. **Ask yourself**: Does this describe what exists today, or what we plan to build?
   - Exists today, and it is the **normative rule** an interface must obey → `docs/spec/`
   - Exists today, and it teaches or describes it for a **user** → `docs/` or root
   - Planned, and it serves one feature → beside that feature, in `planning/proposed/design/` or `planning/pledged/design/`
   - Planned, and it serves no single feature → `planning/design/`
   - Machine-readable and consumed by code → `reliquary/schemas/`, referred to from `docs/spec/`

2. **Check placement**: Is the document in the right location per the rules above?

3. **Mark aspirations clearly**: When a root or docs/ document must mention future plans, mark it clearly (e.g., "Planned for milestone 3", "Not yet implemented").

4. **Keep design separate**: Never mix design discussion into a document that states current truth. A spec says what an interface *is*; the argument for why, and the alternatives declined, belong in `planning/DECISIONS.md` under a D-number the spec can cite. Speculation about what an interface might become belongs under `planning/`, never in `docs/spec/`.

5. **Normative direction is the point**: a spec binds the implementation, so it is written as a rule, not a report. Prefer "a missing slot fails before anything is touched" to "Reliquary currently fails when the slot is missing". If the code does not yet obey it, that is a bug to file — not a reason to soften the spec into a description.
