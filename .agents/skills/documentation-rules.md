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

### docs/ directory
The `docs/` directory contains user-facing documentation for **implemented features**. Every document here must describe functionality that exists and works in the current codebase. Examples include CLI reference guides, platform-specific automation guides, and blueprint usage guides. Design documents, planned features, and unimplemented interfaces belong elsewhere.

### planning/ directory
The `planning/` directory contains maintainer-facing design and planning documents:
- `planning/ROADMAP.md` — architectural context, open design questions, and implementation milestones
- `planning/TASKS.md` — small to-do tasks (large tasks belong in the roadmap)
- `planning/DECISIONS.md` — the adjudicated design-decision record: settled decisions, declined alternatives, and where each folded (the guard against re-litigating)
- `planning/INTERFACES.md` — governing document for world-facing interfaces and the interface-change rule
- `planning/USE-CASES.md` — primary use cases that guide interface decisions (may include unimplemented aspirations)
- `planning/design/` — design documents for specific interfaces and features (end-goal designs, not current truth)
- `planning/examples/` — example blueprints and scripts in planned formats

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
   - If it describes today → root or docs/
   - If it describes plans or designs → planning/design/

2. **Check placement**: Is the document in the right location per the rules above?

3. **Mark aspirations clearly**: When a root or docs/ document must mention future plans, mark it clearly (e.g., "Planned for milestone 3", "Not yet implemented").

4. **Keep design separate**: Never mix implementation documentation with design discussions. Design belongs in `planning/design/`; implementation belongs in docs/ or root.
