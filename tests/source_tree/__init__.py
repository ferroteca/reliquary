# SPDX-FileCopyrightText: 2026 Paul Galbraith
# SPDX-License-Identifier: GPL-3.0-only
"""Tests that read the repository, and therefore ship nowhere.

The rest of the suite tests the package and travels with it: it
ships in the sdist so a downstream packager can run it against their
own platform and interpreter (D105). These do not, because what they
read is the repository itself — prose documents, maintainer records,
the open-problem catalogue — and none of it is in a released
artifact.

**The reason to separate them is that they would otherwise pass.**
A sweep over `docs/`, `AGENTS.md` and `ARCHITECTURE.md` run from an
unpacked sdist finds none of those files, checks a fraction of what
it was written to check, and reports success — the same failure the
conformance corpus had when it ran against the parser and not the
schema (D106). A test that cannot do its job outside the repository
should be unable to *run* outside the repository, rather than
quietly doing less.

So `MANIFEST.in` prunes this directory and `tools/check_dist.py`
asserts it is absent, which is what keeps the guards here honest:
every test below may assume the whole repository is present, and
none of them needs a `skipUnless` saying so.
"""
