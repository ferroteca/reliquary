# Contributing to Reliquary

Thank you for helping improve Reliquary. Bug reports, documentation fixes,
tests, and code changes are welcome when they preserve the project's BSD
licensing and its role as a self-contained OS installation scripter
with an agentless QEMU guest automation layer.

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
- Update README.md, CHANGELOG.md, and planning/ROADMAP.md when public behavior changes.
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

Reliquary is licensed under the [BSD 3-Clause License](LICENSE). By submitting
a contribution, you agree to license that contribution under the same
BSD-3-Clause terms. You retain copyright in your contribution.

The project name **Reliquary** is owned by Paul Galbraith and is not
part of the BSD grant. Forks and redistributions must use a different
name; see [TRADEMARKS.md](TRADEMARKS.md).

Only submit work that you have the right to contribute on those terms. This
means, as applicable, obtaining permission from an employer or other rights
holder and identifying third-party material and its license. Contributions
that would prevent Reliquary from being used or distributed under its existing
BSD-3-Clause license cannot be accepted.

Codex media components follow an additional
top-priority rule: a media (or its `source`) may include a download
`url` only together with an explicit assertion that the media's own
licensing permits redistribution (see planning/design/codex.md).
Changes that add or alter URLs in built-in media without that
assertion cannot be accepted; media for non-redistributable payloads
ship hashes only.

Use accurate SPDX copyright information in each new file:

```text
SPDX-FileCopyrightText: YEAR COPYRIGHT HOLDER
SPDX-License-Identifier: BSD-3-Clause
```

Use the appropriate comment syntax for the file type. Files that cannot or
should not carry comments must be added to `REUSE.toml` with their actual
copyright holder.
