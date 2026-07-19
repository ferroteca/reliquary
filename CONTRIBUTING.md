# Contributing to reliquary

Thank you for helping improve reliquary. Bug reports, documentation fixes,
tests, and code changes are welcome when they preserve the project's BSD
licensing and its role as a relict-based OS installation scripter.

reliquary is currently scaffolding: the public surface is stubbed and no
recipes are implemented. Contributions that implement a recipe should follow
the recipe module convention documented in ROADMAP.md.

## Before you start

For a substantial change, open an issue before investing significant work.
This gives us a chance to agree on the problem, scope, and approach. Small,
focused fixes may go directly to a pull request.

Keep changes narrowly scoped and avoid unrelated cleanup.

## Development setup

reliquary supports Python 3.9 and newer. Create and use the project-local
virtual environment:

```powershell
cd reliquary
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --group dev
python -m pip install -e .
```

Runtime code is standard-library-only except for `relict`. Please discuss a
new dependency before adding it.

## Make and verify a change

- Match the existing style and keep lines near 79 columns.
- Add or update stdlib `unittest` coverage for changed behavior.
- Update README.md, CHANGELOG.md, and ROADMAP.md when public behavior changes.
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

reliquary is licensed under the [BSD 3-Clause License](LICENSE). By submitting
a contribution, you agree to license that contribution under the same
BSD-3-Clause terms. You retain copyright in your contribution.

Only submit work that you have the right to contribute on those terms. This
means, as applicable, obtaining permission from an employer or other rights
holder and identifying third-party material and its license. Contributions
that would prevent reliquary from being used or distributed under its existing
BSD-3-Clause license cannot be accepted.

Use accurate SPDX copyright information in each new file:

```text
SPDX-FileCopyrightText: YEAR COPYRIGHT HOLDER
SPDX-License-Identifier: BSD-3-Clause
```

Use the appropriate comment syntax for the file type. Files that cannot or
should not carry comments must be added to `REUSE.toml` with their actual
copyright holder.
