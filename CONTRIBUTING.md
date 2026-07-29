# Contributing to Reliquary

Thank you for helping improve Reliquary. Bug reports, documentation fixes,
tests, and code changes are welcome when they preserve the project's GPL
licensing and its role as a self-contained OS installation scripter
with an agentless QEMU guest automation layer.

Code contributions carry a licensing requirement that is stricter than
most projects': every accepted contribution is assigned to the project
owner. Read [Contribution licensing](#contribution-licensing) before you
write code — it is a real condition, not a formality, and it is better
learned before the work than after.

We know your time is worth something, and we're glad you're spending
some of it here. This project has a firm sense of what it's for and
what it's trying to be, and we weigh contributions against that, to
keep it coherent for everyone who relies on it. Most contributions fit
without any fuss.

And when one doesn't, that's not the end of the conversation. It might
mean the idea's a poor fit — or that our sense of the project is too
narrow and should change. Tell us either way. The most valuable thing
you could hand us isn't a feature or a fix; it's a better sense of what
this should be. That door is wide open.

Reliquary is pre-release. Contributions that add built-in blueprints
(with their media, source, and archive components) or scripts should
follow the repository structure in AGENTS.md and keep user-facing
documentation synchronized.

## Before you start

For a substantial change, open an issue before investing significant work.
This gives us a chance to agree on the problem, scope, and approach. Small,
focused fixes may go directly to a pull request.

Keep changes narrowly scoped and avoid unrelated cleanup.

## Development setup

Reliquary supports Python 3.9 and newer. Create and use the project-local
virtual environment:

```powershell
cd reliquary
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --group dev
python -m pip install -e .
```

Runtime code is standard-library-only except for `qemu.qmp`. Please discuss a
new dependency before adding it.

## Make and verify a change

- Match the existing style and keep lines near 79 columns.
- Add or update stdlib `unittest` coverage for changed behavior.
- Update README.md, CHANGELOG.md, and the affected docs/spec/ specification when public behavior changes.
- Add SPDX headers to new files as described below.

Run the required checks from the project virtual environment:

```powershell
$pythonFiles = (Get-ChildItem reliquary,reliquary_tests -Filter *.py).FullName
.venv\Scripts\python.exe -m py_compile $pythonFiles
.venv\Scripts\python.exe -m unittest -v reliquary_tests
.venv\Scripts\python.exe -m build
git diff --check
```

## Contribution licensing

Reliquary is licensed under the [GNU General Public License v3.0
only](LICENSE). It is copyleft: anyone may run, study, modify, and
redistribute it, and any distributed work incorporating it must also be
GPL-3.0-only. It cannot be taken into a proprietary product.

### The reserved right, stated plainly

Paul Galbraith holds copyright in Reliquary and **reserves the right to
relicense it**, on any terms, at any time. No relicensing is planned or
in preparation. The reservation exists so that the option is not lost by
default — not because there is a plan behind it.

Two things follow, and both are worth being explicit about:

- **Nothing is taken back.** Every version published under the GPL stays
  under the GPL, permanently and irrevocably. A relicensed edition could
  only ever sit *alongside* what has already been released, never replace
  it, and could not reach backwards into published history. Your right to
  use and fork what exists does not depend on the owner's goodwill.
- **The owner would be the only party able to do it.** Relicensing
  requires the licensor to hold rights in the whole work. That is the
  reason for the assignment below, and it is the honest reason — not
  administrative tidiness.

If you are not comfortable with that reservation, that is a legitimate
position and we would rather you know it now than discover it at merge
time. Bug reports, discussion, and review need no assignment at all.

### Copyright assignment

**Copyrightable contributions require a signed copyright assignment**
before they can be merged. This covers code, documentation, blueprints,
scripts, and artwork. It does not cover bug reports, feature requests,
review comments, or discussion.

The instrument is [CLA.md](CLA.md), signed separately and once. A
statement in a pull request or a commit trailer is **not** a substitute:
an assignment must be executed as its own agreement, and the project
keeps a durable record linking each accepted contribution to it.

Where the law of your jurisdiction does not permit copyright to be
assigned between living persons — Germany is the usual example — the
agreement falls back automatically to the fullest exclusive licence that
jurisdiction does allow. You do not need to work out which case you are
in; the document handles both.

If you contributed the work in the course of employment, or anyone else
has a claim on it, **their consent is required too**, on the entity form
in the same document. In most jurisdictions an employer owns what its
employees write, and an individual signature alone would grant nothing.

Contributions whose ownership cannot be established completely and on the
record are declined. This is not a judgement about the contributor — it
is that unclear title cannot be repaired later, and the project prefers a
clean reimplementation by the owner over code it cannot account for.

### Third-party material cannot be accepted

This is the rule most likely to surprise you, and it is stricter than it
was under the project's former BSD licence.

**Do not submit code you did not write**, even when its licence is
permissive and even when it would be GPL-compatible. You cannot assign
copyright in work you do not own, so third-party material — however
freely licensed — cannot pass through this process. That includes
snippets from Stack Overflow, blog posts, other projects, and vendored
files.

This applies with particular force to code from **GPL-licensed
projects**. GPL compatibility is not the test here; assignability is, and
copyleft code from another author fails it.

If a third-party component genuinely belongs in Reliquary, it comes in as
a **declared dependency** with its own licence intact, never as copied
source, and only after discussion. See `AGENTS.md` for the rules
governing which licences may be depended on and on what terms.

### Reference projects and clean-room work

Reliquary studies prior art openly, and os-autoinst in particular. The
boundary is absolute and it is **not** a licensing conclusion:

> Designs may be studied and reimplemented. Code is never read for
> reimplementation, ported, or translated.

A close translation is a port no matter what the source licence permits.
If you have read another project's implementation of something, say so
before submitting work in that area — that is a normal and welcome thing
to disclose, not an accusation to avoid. `AGENTS.md` records the full
doctrine and the specific projects it names.

### The project name

The name **Reliquary** is owned by Paul Galbraith and is not part of the
GPL grant — a reservation the GPL expressly permits at section 7(e).
Forks and redistributions must use a different name; see
[TRADEMARKS.md](TRADEMARKS.md).

### Media components

Codex media components follow an additional
top-priority rule: a media (or its `source`) may include a download
`url` only together with an explicit assertion that the media's own
licensing permits redistribution (see docs/spec/codex.md).
Changes that add or alter URLs in built-in media without that
assertion cannot be accepted; media for non-redistributable payloads
ship hashes only.

Use accurate SPDX copyright information in each new file:

```text
SPDX-FileCopyrightText: YEAR COPYRIGHT HOLDER
SPDX-License-Identifier: GPL-3.0-only
```

Use the appropriate comment syntax for the file type. Files that cannot or
should not carry comments must be added to `REUSE.toml` with their actual
copyright holder.
