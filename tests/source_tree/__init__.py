# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Tests that read the repository itself, and so ship nowhere.

The rest of the suite tests the installed package and travels with it:
it ships in the sdist, so a downstream packager can run it against
their own platform and interpreter (D105). The tests in this directory
don't ship, because what they read is the repository itself — prose
documents, maintainer records, the open-problem catalogue — and none
of that is included in a released package.

**They're kept separate because otherwise they would pass for the
wrong reason.** A sweep over `docs/`, `AGENTS.md`, and `ARCHITECTURE.md`
run from an unpacked sdist would find none of those files, check only a
fraction of what it was written to check, and still report success —
the same failure the conformance corpus had when it ran only against
the parser and not the schema (D106). A test that can't do its job
outside the repository should fail to *run* outside the repository,
rather than quietly running a weaker version of itself.

So `MANIFEST.in` excludes this directory from the sdist, and
`tools/check_dist.py` checks that it's absent from the built package.
That's what keeps the guards in this directory honest: every test here
can assume the whole repository is present, and none of them needs a
`skipUnless` to say so.
"""
