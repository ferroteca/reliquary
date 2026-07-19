# AGENTS.md — repository guidance

This is the canonical, agent-agnostic guidance for working on relict. Human usage documentation belongs
in [README.md](README.md); keep this file focused on repository structure, engineering constraints, verification, and
maintenance context.

## Project state and layout

relict is deliberately a small Python package. It is a generic QEMU runner with DOS as its default and currently only
complete platform workflow:

- `relict/` contains the library and CLI. `__init__.py` preserves the root import surface; `home.py` owns home
  containment, `media.py` parses declared drives, `lifecycle.py` owns QMP, QEMU
  processes, and host-side `qemu-img` helpers, `interaction.py` defines
  capability protocols, `interaction_agentless.py` contains the concrete agentless DOS adapter, `machine.py` provides
  platform-neutral QMP interaction and diagnostics, `platform_dos.py` owns DOS provisioning,
  facades, `workflows.py` orchestrates configured runs, `cli.py` owns command parsing, and `__main__.py` preserves
  `python -m relict` execution.
- `pyproject.toml` packages `relict` as the `relict` command and includes the installable `relict_tests` test
  package.
- `relict_tests/` contains stdlib `unittest` coverage for core helpers, guest program runs, and lifecycle ownership.
- `README.md` is the human guide.
- `CHANGELOG.md` records release-facing changes.
- `ROADMAP.md` contains maintainer-facing design and roadmap for planned interfaces and architecture.

Keep these modules deep: add behavior to the module that owns its invariant, and introduce another module only when a
real interface or maintenance seam justifies it. The package root exposes the intended embedding surface but owns no
implementation.

## Required invariants

### Platform selection

DOS is the compatibility default when no platform is specified. Platform-specific behavior must be selected through
`MachineConfig.platform` or `--platform`, never inferred by inspecting an image or guest screen. The reusable machine
layer may remain platform-neutral, but provisioning, readiness, remote-task execution, and result collection belong to
platform workflows. Until a non-DOS workflow is complete and tested, it must raise `NotImplementedError` rather than
using DOS assumptions.

### Agentless operation

Agentless DOS operation is a permanent requirement. The DOS workflow must continue to work against a guest with no guest agent,
network driver, serial driver, or other cooperating software.

The current transport is:

- QMP `send-key` for input
- VGA text-memory scraping for output
- QEMU vvfat for bidirectional files
- prompt detection for command completion
- QMP `screendump` for screenshots

Never make a feature depend on guest cooperation. A future guest-agent transport may be optional, but agentless behavior
must remain the default and fallback.

### Home-directory containment

All persistent state belongs under the relict home (`Documents/relict` by default, falling back to `~/relict`
when no Documents folder can be determined; overridden by `RELICT_HOME`, `--home`, or `set_home()`; individual
operations accept an explicit `home=` that overrides the process-global home for that call — the `_effective_home()`
seam). Never write beside the module or into the source repository during normal use.

Current home layout:

- `drives/` — the machine's declared drives (images and virtual FAT directories; see "DOS boot and scripting")
- `machine.json` — optional CLI machine configuration (not loaded by Python workflows)
- `screenshots/` — screenshots
- `qemu-stderr.log` — startup diagnostics
- `vm.json` — active VM identity, port, and PID

### VM ownership

Never send a control command to a QMP server until its identity is verified.

`start()` assigns a unique QEMU name, records it with the selected port in
`vm.json`, and returns the port. Every later connection checks `query-name`
against that record. Identity mismatches fail closed; in particular,
`stop()` must never send `quit` to an unrelated VM.

`Machine.qmp()` is the public raw-monitor seam. It yields the
identity-verified QMP session, whose `cmd()` and `hmp()` methods remain
available to callers. Interaction adapters receive a `Machine` and must use
this seam rather than opening QMP connections directly.

When `port=None`, `start()` selects an available local port. An explicit port must be free. Startup failure and timeout
paths must terminate the child so they cannot leave an untracked QEMU process.

The CLI may resolve the active port from `vm.json`; Python workflows should propagate the port returned by `start()`
explicitly.

### DOS boot and scripting

The `drives/` directory declares the whole machine, each entry's name stating its medium, slot, and format — image
content is never interrogated (`_scan_drives()`, `_drive_args()`). Image files `floppy[_<n>].<ext>` (slots 0–1, A:
and B:), `hdd[_<n>].<ext>` (slots 0–3, the IDE bus), and `cdrom[_<n>].<ext>` (`media=cdrom`, placed on the IDE slots
after the hard disks; their `<n>` only orders them) mount as that medium; bare directories `floppy[_<n>]` and
`hdd[_<n>]` mount as virtual FAT drives (cdrom directories are rejected — vvfat emulates no ISO9660). An unindexed
name means slot 0; slot clashes and out-of-range slots fail closed. The extension, kept idiomatic for the format,
declares the format (`_format_options()`): any QEMU-supported image format works, with `*.img` and `*.iso` pinned to
`format=raw` (avoiding QEMU's format-probing warning) and any other extension handed to QEMU to identify.

Memory defaults to 16 MB and the boot order to a best guess from the declared media — the slot-0 floppy image, else
the slot-0 hard-disk image, else any cdrom (`_boot_guess()`); a `-m` or `-boot` in `qemu_args` suppresses the
corresponding default.

`AgentlessGuestExec.wait_ready()` only waits out the boot process to a native DOS prompt, detected generically as a
bare prompt on the bottom-most non-blank screen row. Do not add special boot parameters for ordinary DOS commands. Drive changes, directory changes,
environment variables, and program invocations belong in `AgentlessGuestExec.execute()` scripting.

Higher-level workflows may issue those ordinary commands internally. For example, `run_guest_program()` runs `c:` before
invoking the staged executable.

### Virtual FAT behavior

QEMU snapshots a vvfat staging directory when the drive is attached. Host changes require a stop/start cycle. Guest
writes should be read after QEMU stops so write-back has completed.

Staged directories are declared under `drives/` like any other drive: `hdd[_<n>]` attaches as a vvfat hard disk,
`floppy[_<n>]` as a vvfat 1.44M FAT12 floppy, each at its named slot.

## Guest program runs

`run_guest_program()` is the one-shot lifecycle: stage an executable on the staged guest drive, boot, run it with
its output redirected to a log on that drive, stop, and return the log text. Staging targets the highest staged
directory declared among the hard-disk slots, or `drives/hdd` (the first free slot) created on demand
(`_staged_hdd_plan()`). The guest assigns drive letters by disk order, so `staged_drive` is the caller declaring
where that drive appears; its default assumes one letter per hard-disk slot before the staged one (C: when none
precede it), and letters below the default are rejected. relict uses the letter only for the drive-switch
command. The current DOS platform validates its own 8.3 `.EXE` naming requirement in `platform_dos.py`; generic
workflow orchestration must not impose that rule on other platforms. relict attaches no meaning to that output — test-framework semantics (
command-line flags, result parsing) belong to consuming projects. The CppUTest adapter that used to live here was
removed to enforce that boundary; do not reintroduce framework-specific code. Refer to consumers only in the general
instructional sense ("the caller", "consuming projects", generic usage examples) — never name specific downstream
projects; relict stays ignorant of who builds on it.

## The runner surface

`Runner`/`MachineConfig` is the generic embedding surface (a soft contract with callers): a
`Runner(home=None, config=None)` instance is a configured QEMU test machine bound to one absolute `home`, exposing
`platform` (default "dos") and `config` (frozen dataclass: `platform`, `staged_drive`, `timeout`, `memory`, `qemu`,
`qemu_args`, `drives`, `machine`; every field has a working default), and `run(exe_path, args)`. `machine` is either a non-empty
QEMU machine-type string or an immutable mapping with required `type` and scalar properties; it renders as one
`-machine` argument, with booleans normalized to `on`/`off`, and conflicts with raw `-machine`/`-M` in `qemu_args`.
`memory` is either `None` or a positive integer MiB value. `None` resolves to the platform default: 16 MiB for DOS,
64 MiB for Win9x, and 256 MiB for WinNT. An explicit value conflicts with raw `-m` in `qemu_args`.
Configured drives use canonical keys
`floppy_0..1`, `hdd_0..3`, and `cdrom_0..3`, with `floppy` and `hdd` accepted as slot-zero aliases. Each value is a
source path or a mapping with `source` and `options`; values are normalized and deeply frozen. Files are images,
floppy/hdd directories are vvfat, and cdrom directories fail validation. Configured sources compose with filesystem
declarations by logical slot; two sources for one slot fail closed. `MachineConfig.from_file(path, **overrides)` and
`from_mapping(value, base_dir=None, **overrides)` load the same versioned document shape (`version` required and
must be `1`; not a constructor field). Relative drive sources resolve from the file directory via `from_file`, or
from `base_dir` / the current directory via `from_mapping`. Explicit overrides win: scalars replace (including
`None`), `qemu_args` and `machine` replace wholesale, and `drives` merge by logical slot then by entry field /
option name. Construction and `Runner` do not implicitly load `<home>/machine.json`. The CLI does load
`<effective-home>/machine.json` when present, unless `--machine PATH` selects an explicit file; this is a CLI
convenience and does not apply to Python workflows. Explicit `--platform`, `--qemu`, and raw QEMU arguments
override the loaded file; an omitted `--platform` must not clobber a file platform (so argparse must not
default `--platform` to `"dos"`). `run()` privately ensures that
the resolved inventory declares something bootable — keep present declared media;
never overwrite — before invoking `run_guest_program()` with the runner's home explicit. Machine configuration has no
special boot-image fields: custom media is declared through the same drive inventory as every other image.
The module-level `start()`, `run_task()`, and `run_guest_program()` functions accept one optional `machine_config`
containing a `MachineConfig`, versioned mapping, or path. Machine settings have no parallel individual function
parameters; only operational controls such as display, port, and home remain separate.
There is no public provisioning step. An omitted home resolves the established process default once at construction.
Invariants to preserve: all state for an instance lives under its resolved constructor home; concurrent runs use
distinct `Runner` instances with distinct homes (per-home `vm.json` keeps VM ownership
sound); the stored home must never fall back to the process-global home (`test_runner.py` guards this by making
`home()` unreachable). The project is pre-release; prefer a coherent interface over compatibility shims when its
architecture changes.

## Dependencies and style

- Runtime code is stdlib-only except for `qemu.qmp`.
- Do not add dependencies casually. The hand-written PNG fallback exists to avoid an image-library dependency.
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

Use the appropriate comment syntax for the file type. Files that cannot or should not carry headers must be covered by
`REUSE.toml`.

External contributors retain copyright in accepted contributions and license them under BSD-3-Clause. Their new files
must use accurate contributor copyright notices rather than attributing their work to Paul. Keep the human submission
terms in `CONTRIBUTING.md` synchronized with this policy.

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
$pythonFiles = (Get-ChildItem relict,relict_tests -Filter *.py).FullName
.venv\Scripts\python.exe -m py_compile $pythonFiles
.venv\Scripts\python.exe -m unittest -v relict_tests
.venv\Scripts\python.exe -m build
```

`python -m build` builds an sdist and then a wheel from that sdist, which checks that the source archive is complete.
After packaging metadata changes, inspect `PKG-INFO` for at least the name, version, Python requirement, runtime
dependencies, and the presence of the `relict_tests` package in both built artifacts. For release-facing packaging
changes, install the wheel into a clean environment, change to a directory outside the source tree, and run
`python -m unittest -v relict_tests`. Downstream packagers should be able to run the same command against both their
unpacked source package and installed artifact.

Run `git diff --check` before handing work back.

Hands-on tests require QEMU. Use `--home` with a scratch or deliberately reused test home rather than polluting the
default per-user home.

## Test expectations

Lifecycle changes need focused tests, especially for failure paths. Preserve coverage for these guarantees:

- automatic ports are returned and recorded
- occupied explicit ports fail before launch
- identity mismatch terminates a just-started child
- identity mismatch never reaches `quit`
- stale state produces clear diagnostics and cannot target another VM

Use stdlib `unittest` and `unittest.mock` unless a compelling reason justifies another dependency.

## Documentation maintenance

README.md is a human-facing guide to what relict does, why it exists, and how to use it. Keep it explanatory and
task-oriented. Do not move agent instructions, implementation constraints, roadmap discussion, or maintenance notes into
it.

After changing commands, flags, paths, behavior, or Python interfaces, update README.md, CHANGELOG.md, and this file
wherever affected. Validate documented CLI syntax with `relict --help` and subcommand help.

## Architecture and prior art

relict uses QEMU's published `qemu.qmp` library for protocol handling and implements the machine-lifecycle role
locally. QEMU's in-tree `QEMUMachine`
is not published independently; if that changes, reassess whether replacing local lifecycle code would reduce
maintenance without weakening ownership checks or the public interface.

QEMU's own functional tests validate the broad model of scripting a guest over QMP and asserting on observable state.
relict adds the DOS-specific layer: keyboard conventions, VGA text scraping, prompt
completion, and vvfat staging.

Espressif's `pytest-embedded-qemu` is useful prior art for a future
`pytest-relict` plugin: host pytest orchestration around a native guest test framework. It is not directly reusable
because it assumes Espressif targets, serial output, and Unity result grammar.
