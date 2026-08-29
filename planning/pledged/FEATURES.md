<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Pledged features

This file lists large capabilities that are **pledged but not yet
built**. Each entry carries the list of work that delivers it. A
feature gets added here by being moved out of
[proposed/FEATURES.md](../proposed/FEATURES.md). That move is what
makes it a pledge, and the git commit that makes the move is the
record of the pledge ([README.md](../README.md)). A feature leaves
this file either by being delivered, or by being **withdrawn** back
to that file, if it turns out nobody actually meant to commit to it
(D44; first used by D61).

This file is not a schedule. Numbered milestones stopped after
milestone 9, so nothing below has a queue position or a date. The
work items under each feature follow the same rules as
[TASKS.md](../TASKS.md) — they're just tasks. They're listed under
their feature instead of in that task queue because they don't make
sense on their own, apart from the feature.

Each feature carries an **F-number** and must fit in **one sprint**
(D42; the rules are in [README.md](../README.md)). If a feature is
too large, it gets split up when it's pledged: the original
F-number is retired, and each resulting piece gets its own new
F-number.

**F-numbers come from the sequence ledger**
([SEQUENCES.md](../SEQUENCES.md); owner, 2026-07-31). When a feature
is added — whether it's first drafted in
[proposed/FEATURES.md](../proposed/FEATURES.md) or added straight to
this file as a pledge — take the next number from that ledger and
update the ledger in the same edit.

