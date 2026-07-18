# AGENTS.md — repository guidance

This is the canonical, agent-agnostic guidance for working on relict. Human usage documentation belongs
in [README.md](README.md); keep this file focused on repository structure, engineering constraints, verification, and
maintenance context.

## Project state and layout

**relict is scaffolding**: the structure, public surface, and documentation exist, but every operation raises
`NotImplementedError`. The design recorded in the module docstrings is settled; implementation has not started. When
implementing a stub, keep its documented signature and semantics — callers rely on these exact names and parameters
structurally.

relict is deliberately a small, single-module Python project:

- `relict.py` contains the library and CLI.
- `pyproject.toml` packages that module as the `relict` command and includes the installable `relict_tests` test
  package.
- `relict_tests/` contains stdlib `unittest` coverage; today it pins the stub surface (machine shape,
  environment-choice validation, explicit `NotImplementedError` state).
- `README.md` is the human guide.
- `CHANGELOG.md` records release-facing changes.

Do not introduce a package directory or split the module merely for organizational symmetry. Refactor when a real
interface or maintenance seam justifies it.

## Required invariants

### No default guest environment

Windows 9x is proprietary: relict must never download, embed, or default to any Windows image or media. The caller
supplies either a ready bootable hard-disk image or install media (local ISO, or URL with mandatory SHA-256), plus any
product key. An absent environment is a `ValueError` naming the options, never a silent fallback. A `media_url=`
without its `media_sha256=` is always rejected.

### Guest cooperation is baked in, not depended on

The guest runs no separately installed agent, network stack, or serial service. Whatever in-guest mechanics relict
needs to launch the staged program and signal completion (e.g. a run hook installed during the one-time unattended
install) are relict's own business: arranged by relict itself while it builds the image, owned by this project, and
invisible in the public surface. Completion detection is guest-initiated shutdown — Windows 9x has no scrapeable text
screen, so never build behavior on reading one.

### Home-directory containment

All persistent state belongs under the relict home (`Documents/relict` by default, falling back to `~/relict` when no
Documents folder can be determined; overridden by `RELICT_HOME`, `--home`, or `set_home()`; individual operations
accept an explicit `home=` that overrides the process-global home for that call). Never write beside the module or
into the source repository during normal use.

Planned home layout:

- `dist/` — the installed bootable hard-disk image (`boot.img`) and installation artifacts
- `staging/e-drive/` — default staged-drive staging convention (letter-named for the configured `staged_drive`)

### VM ownership

Never send a control command to a QMP server until its identity is verified. When VM lifecycle code is implemented,
it must assign each VM a unique name, record it with the selected port in per-home state, verify `query-name` before
any command, and fail closed on mismatch — in particular, a stop must never reach an unrelated VM. Startup failure and
timeout paths must terminate the child so they cannot leave an untracked QEMU process.

### The staged drive is its own drive

relict never stages onto C:, the boot image's system drive. Staged files appear on a separate virtual FAT guest drive
whose letter is a config parameter (`staged_drive`, default `E`, valid range D–Z — the virtual CD-ROM usually claims
D:, but D: is accepted for machines with no CD-ROM attached); the letter is validated and normalized at configuration
time, never silently remapped later.

## Guest program runs

`run_guest_program()` is the one-shot lifecycle: stage a (8.3-named) executable on the staged virtual FAT guest
drive, boot `dist/boot.img`, run it with its output redirected to a log on that drive, detect completion via
guest-initiated shutdown, stop, and return the log text. relict attaches no meaning to that output — test-framework semantics
(command-line flags, result parsing) belong to consuming projects. Refer to consumers only in the general
instructional sense ("the caller", "consuming projects", generic usage examples) — never name specific downstream
projects; relict stays ignorant of who builds on it.

## The runner surface

`Runner`/`RunnerConfig` is the generic embedding surface (a soft contract with callers): a `Runner(config)` instance
is a configured Windows 9x test machine exposing `platform` ("win9x"), `config` (frozen dataclass: `boot_image`, the
install-media fields, `staged_drive`, `timeout`, `qemu`, `qemu_args`), `provision(dist_dir)` (ensure `dist_dir/boot.img` exists —
keep a present image, copy the configured one, or run the one-time unattended install; never overwrite; raise when
nothing is configured), and `run(exe_path, args, home)` (the full guest-program lifecycle with the home explicit;
provisions `home/dist/boot.img` per the config when absent). Invariants to preserve: instances carry configuration
only — per-run state lives under the explicitly passed home, making concurrent runs in distinct homes safe; the
explicit `home=` path must never fall back to the process-global home; `provision()` is deterministic given the
config and cache-unaware — durable caching of the installed image, and deciding whether provisioning is needed at
all, is the caller's job (an unattended install is slow; relict still never decides retention). Keep the signatures
stable: callers rely on these exact names and parameters structurally.

## Dependencies and style

- Runtime code is stdlib-only except for `qemu.qmp`.
- Do not add dependencies casually.
- Support Python 3.9 and newer.
- Keep lines near 79 columns in Python and match existing formatting.
- Prefer small public interfaces with lifecycle complexity kept behind them.
- Preserve useful exception context and actionable diagnostics.

## Licensing

The project is BSD-3-Clause and follows REUSE conventions.

Every new file authored for the project by Paul needs:

```text
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
```

Use the appropriate comment syntax for the file type. Files that cannot or should not carry headers must be covered by
`REUSE.toml`.

External contributors retain copyright in accepted contributions and license them under BSD-3-Clause. Their new files
must use accurate contributor copyright notices rather than attributing their work to Paul. Keep the human submission
terms in `CONTRIBUTING.md` synchronized with this policy.

relict never ships, downloads, or embeds Microsoft software. Nothing in the repository — including test fixtures — may
contain Windows binaries, media contents, or product keys.

## Development environment

Use the project-local `.venv`; do not install development tools globally.

On Windows:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --group dev
python -m pip install -e .
```

The `dev` dependency group contains repository tooling such as the `build` frontend. Runtime dependencies remain under
`[project].dependencies`.

## Required checks

Run checks with the project virtual environment.

```powershell
.venv\Scripts\python.exe -m py_compile relict.py relict_tests\test_runner.py
.venv\Scripts\python.exe -m unittest -v relict_tests
.venv\Scripts\python.exe -m build
```

`python -m build` builds an sdist and then a wheel from that sdist, which checks that the source archive is complete.
After packaging metadata changes, inspect `PKG-INFO` for at least the name, version, Python requirement, runtime
dependencies, and the presence of the `relict_tests` package in both built artifacts.

Run `git diff --check` before handing work back.

## Test expectations

Use stdlib `unittest` and `unittest.mock` unless a compelling reason justifies another dependency. While the project
is scaffolding, the tests pin the public surface; as stubs become real, replace the `NotImplementedError` expectations
with behavioral coverage — especially for VM lifecycle failure paths and the environment-choice validation.

## Documentation maintenance

README.md is a human-facing guide to what relict does, why it exists, and how to use it. Keep it explanatory and
task-oriented. Do not move agent instructions, implementation constraints, or maintenance notes into it.

After changing commands, flags, paths, behavior, or Python interfaces, update README.md, CHANGELOG.md, and this file
wherever affected. Once the CLI is real, validate documented syntax with `relict --help` and subcommand help.

## Architecture and prior art

relict targets the same shape as its sibling DOS harness, quemados (a generic runner class over an agent-free QEMU
guest, one visible home directory, QMP control with verified VM identity) and follows its conventions where they
apply. The sibling relationship is one-way inspiration: relict imports nothing from it and must work stand-alone.
