# AGENTS.md — repository guidance

This is the canonical, agent-agnostic guidance for working on reliquary. Human
usage documentation belongs in [README.md](README.md); keep this file focused on
repository structure, engineering constraints, verification, and maintenance
context.

## Project state and layout

reliquary is a newly scaffolded OS installation scripter built on relict. It is
almost entirely stubs.

- `reliquary/` contains the library and CLI. `__init__.py` preserves the root
  import surface; `cli.py` owns command parsing; `__main__.py` preserves
  `python -m reliquary` execution; `recipes/` contains OS installation recipes
  (one module per target OS).
- `pyproject.toml` packages `reliquary` as the `reliquary` command and includes
  the installable `reliquary_tests` test package.
- `reliquary_tests/` contains stdlib `unittest` coverage.
- `README.md` is the human guide.
- `CHANGELOG.md` records release-facing changes.
- `ROADMAP.md` contains maintainer-facing design and roadmap.

Keep these modules deep: add behavior to the module that owns its invariant,
and introduce another module only when a real interface or maintenance seam
justifies it. The package root exposes the intended embedding surface but owns
no implementation.

## Dependencies and style

- Runtime code is stdlib-only except for `relict`.
- Support Python 3.9 and newer.
- Keep lines near 79 columns and match existing formatting.
- Prefer small public interfaces with lifecycle complexity kept behind them.
- Preserve useful exception context and actionable diagnostics.

## Licensing

The project is BSD-3-Clause and follows REUSE conventions.

Every new file authored for the project by Paul needs:

```text
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
```

Use the appropriate comment syntax for the file type. Files that cannot or
should not carry headers must be covered by `REUSE.toml`.

## Development environment

Use the project-local `.venv`; do not install development tools globally.

On Windows:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --group dev
python -m pip install -e .
```

The `dev` dependency group contains repository tooling such as the `build`
frontend. Runtime dependencies remain under `[project].dependencies`.

## Required checks

Run checks with the project virtual environment.

```powershell
$pythonFiles = (Get-ChildItem reliquary,reliquary\recipes,reliquary_tests -Filter *.py).FullName
.venv\Scripts\python.exe -m py_compile $pythonFiles
.venv\Scripts\python.exe -m unittest -v reliquary_tests
.venv\Scripts\python.exe -m build
```

Run `git diff --check` before handing work back.

## Test expectations

Use stdlib `unittest` and `unittest.mock` unless a compelling reason justifies
another dependency.
