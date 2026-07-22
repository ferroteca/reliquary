# AGENTS.md — repository guidance

This is the canonical, agent-agnostic guidance for working on reliquary. Human usage documentation belongs
in [README.md](README.md); keep this file focused on repository structure, engineering constraints, verification, and
maintenance context.

## Project state and layout

reliquary is an OS installation scripter built on its own generic QEMU
runner, with DOS as the default and currently only complete platform
workflow:

- `reliquary/` contains the library and CLI. `__init__.py` preserves the root import surface; `home.py` owns home
  resolution, layout, and containment, `blueprint.py` parses the milestone-1 machine blueprint subset and resolves
  its media references, `drives.py` parses declared drives, `media.py` owns media definitions
  (parsing, name resolution) and hash-verified acquisition of OS installation media into the
  `cache/downloads/` and `cache/media/` caches, `library.py` owns the codex — the built-in seed library
  (`reliquary/builtins/` package data, to be renamed `codex/` at realignment: seed-on-first-reference copy-out, never overwriting home files), `machines.py` owns machine materialization under
  `cache/machines/<blueprint>-<n>/` plus lifecycle (`create` / `start` / `stop` / `destroy` / `list_machines` /
  `resolve_machine`; ids are `<blueprint_name>-<machine_number>` with
  lowest-free reuse and a per-blueprint allocation lock) and persistent machine-state mutations
  (`insert_media` / `eject_media` / `set_boot_order` /
  `mark_stopped` — insert/eject are floppy and cdrom only;
  boot-order keys may name any declared drive; all three require
  a stopped machine and survive stop/start), `lifecycle.py` owns QMP,
  QEMU processes, and host-side `qemu-img` helpers,
  `interaction.py` defines capability protocols, `interaction_agentless.py` contains the concrete agentless DOS
  adapter (prompt-based readiness and command completion), `machine.py` provides platform-neutral QMP interaction
  and diagnostics — keyboard input, VGA text/attribute scraping, cursor-menu selection, and screenshots,
  `platform_dos.py` owns DOS provisioning, facades, `workflows.py` orchestrates configured runs, `script.py`
  parses the milestone-1 `.rlqs` subset (including the `machine: running|stopped` header and
  `insert`/`eject`/`boot`) until the runner retarget replaces it with the redesigned surface's three-layer
  stack — `script_nodes.py` (the lexer and its diagnostics), `script_parser.py` with
  `script_grammar.lark` (the typed tree, node signatures), and `script_validation.py` (the S-numbered
  static rules, each diagnostic citing its id) — `script_runner.py` executes scripts against cached machines and
  wires `script <label>` (resolve via blueprint map, create-if-none, the machine-state header, static
  preflight of insert/eject/boot drive keys, run records under
  `cache/machines/<blueprint>-<n>/runs/`), `cli.py` owns command parsing, and `__main__.py`
  preserves `python -m reliquary` execution.
- `pyproject.toml` packages `reliquary` as the `reliquary` command and includes the installable `reliquary_tests` test
  package.
- `reliquary_tests/` contains stdlib `unittest` coverage for core helpers, guest program runs, lifecycle ownership,
  media acquisition, blueprints, machines, and scripts.
- `README.md` is the human guide.
- `CHANGELOG.md` records release-facing changes.
- `planning/ROADMAP.md` contains maintainer-facing design and roadmap for planned interfaces and architecture.
- `planning/INTERFACES.md` is the governing document for reliquary's world-facing interfaces: it names the interface
  inventory (CLI, embedding API, scripting language, machine blueprints, and media definitions, plus the
  script properties, recorded outputs, and the home layout) and the
  vetting rule every interface-changing decision must follow. The numbered primary use cases — the decision
  surface that rule weighs against — live in `planning/USE-CASES.md`.
- `planning/examples/` contains a complete FreeDOS example in the planned formats: a machine blueprint and scripts, with the
  install script embedding the media definition that its first run installs in the media library. Its README carries
  the status note. Keep the examples synchronized with `planning/design/` when the formats change.
- `docs/` holds user-facing documentation for implemented features
  (CLI reference, Python API reference, blueprint guide, DOS
  automation). Design documents
  and planned interfaces live in `planning/design/` — the directory
  is the classification; file names carry no suffix. The blueprint
  and media-definition JSON Schemas (`*.schema.json`) sit beside
  their specs there and must stay synchronized with them (the prose
  specs are normative). Placement rules
  are in `.agents/skills/documentation-rules.md`.

Keep these modules deep: add behavior to the module that owns its invariant, and introduce another module only when a
real interface or maintenance seam justifies it. The package root exposes the intended embedding surface but owns no
implementation.

## Required invariants

### No backward compatibility before beta

reliquary is evolving rapidly and deliberately maintains **no backward compatibility of any kind** until at
least a beta-quality release: no spec/config format versioning or migration, no API aliasing, no
deprecated-name shims, no compatibility parsing. When an interface changes, change it coherently and
completely — update every caller, document, and test to the new shape and delete the old one. Do not add
transition affordances "to be safe"; stale artifacts (old machine blueprints, homes, embeddings) may simply fail
and users recreate them. Compatibility guarantees, if any, will be defined no earlier than beta.

### Interface changes are vetted

The CLI, the embedding API, the scripting language, the machine blueprint, and the media definition are
reliquary's primary interfaces to the world; the script properties, recorded outputs (run records,
transcripts), and the home layout are world-facing contracts alongside them. Any decision that
changes one follows the rule in [planning/INTERFACES.md](planning/INTERFACES.md): requests triage by their impact on the
numbered primary use cases ([planning/USE-CASES.md](planning/USE-CASES.md)) — no impact or strong alignment is an easy approval, adding a new use case is more work but still
easy, and a change misaligned with the use cases must win the argument for amending the list itself, with
work starting only after the amendment lands — then the change is named across every surface it touches
and landed coherently on all of them. Where planning/ROADMAP.md and planning/INTERFACES.md or planning/USE-CASES.md disagree, the
principles and use cases govern; the roadmap is realigned to them.

### CLI–API parity

The CLI and the embedding API are two presentations of one semantic surface, and keeping them in sync is
extraordinarily important. Every command maps one-to-one onto a public API call with the same semantics;
nothing is CLI-only, and no public capability may be unreachable from the CLI — it is the fallback binding
for every language without a native one. A change to this surface lands on both presentations in the same
change, never deferred to a later pass.

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

All persistent state belongs under the reliquary home (`Documents/reliquary` by default, falling back to `~/reliquary`
when no Documents folder can be determined; overridden by `RELIQUARY_HOME`, `--home`, or `set_home()`; individual
operations accept an explicit `home=` that overrides the process-global home for that call — the `_effective_home()`
seam). Never write beside the module or into the source repository during normal use.

Current home layout (still the active machine model):

- `drives/` — the machine's declared drives (images and virtual FAT directories; see "DOS boot and scripting")
- `machine.json` — optional legacy CLI machine configuration for bare
  `rlq start` without `--blueprint` / `--machine` (not loaded by Python
  workflows)
- `screenshots/` — screenshots
- `qemu-stderr.log` — startup diagnostics
- `vm.json` — active VM identity, port, and PID (legacy root-home path;
  cached machines keep theirs under `cache/machines/<blueprint>-<n>/vm.json`)
- `blueprints/` — machine blueprints (`blueprints_dir`)
- `media/` — shared media definitions (`media_dir`)
- `scripts/` — automation scripts (`scripts_dir`)
- `cache/downloads/` — cached source archives (`downloads_cache_dir`)
- `cache/media/` — cached media payloads (`media_cache_dir`)
- `cache/machines/<blueprint>-<n>/` — machine materializations (`machines_cache_dir`;
  parent via `cache_dir`), each with `reliquary-machine.json`, `drives/`,
  and when running `vm.json` / `qemu-stderr.log`

### VM ownership

Never send a control command to a QMP server until its identity is verified.

`start()` assigns a readable QEMU name plus a fresh per-start `-uuid`,
records both with the selected port in `vm.json`, and returns the port.
Every later connection checks `query-name` **and** `query-uuid` against
that record. The name alone must never authorize a command: same-numbered
machines of one blueprint in different homes share their readable name, so
only the uuid identifies the exact QEMU instance this home started.
Identity mismatches fail closed; in particular, `stop()` must never send
`quit` to an unrelated VM.

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
precede it), and letters below the default are rejected. reliquary uses the letter only for the drive-switch
command. The current DOS platform validates its own 8.3 `.EXE` naming requirement in `platform_dos.py`; generic
workflow orchestration must not impose that rule on other platforms. reliquary attaches no meaning to that output — test-framework semantics (
command-line flags, result parsing) belong to consuming projects. The CppUTest adapter that used to live here was
removed to enforce that boundary; do not reintroduce framework-specific code. Refer to consumers only in the general
instructional sense ("the caller", "consuming projects", generic usage examples) — never name specific downstream
projects; the machine layer stays ignorant of who builds on it. The
media layer (`media.py`, `library.py`) and the script runtime
(`script_runner.py`) are in-repo consumers of that surface and must
drive it only through the same public interfaces available to external
callers.

## The runner surface

This section is the engineering contract agents must preserve for the
implemented binding. The user-facing reference is
`docs/api-reference.md`; the end-goal API design (settled twin names,
conventions, handles) is `planning/design/api.md`.

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
floppy/hdd directories are vvfat, and cdrom directories fail validation. Configured sources compose with filesystem declarations by logical slot; two sources for one slot fail closed, unless the configured entry sets an explicit `enabled: true`, which deliberately replaces the filesystem drive (`enabled: false` unmounts it; an omitted `enabled` is not an override). `MachineConfig.from_file(path, **overrides)` and
`from_mapping(value, base_dir=None, **overrides)` load the same versioned document shape (`version` required and
must be `1`; not a constructor field). Relative drive sources resolve from the file directory via `from_file`, or
from `base_dir` / the current directory via `from_mapping`. Explicit overrides win: scalars replace (including
`None`), `qemu_args` and `machine` replace wholesale, and `drives` merge by logical slot then by entry field /
option name. Construction and `Runner` do not implicitly load `<home>/machine.json`. The CLI loads
`<effective-home>/machine.json` for bare `rlq start` (no `--blueprint` / `--machine`
selector); this is a transitional convenience and does not apply to Python workflows or to
the cached-machine lifecycle (`rlq --blueprint NAME create|start|stop|destroy`,
`rlq list machines`). Explicit `--platform`, `--qemu`, and raw QEMU arguments
override the loaded file on that legacy path; an omitted `--platform` must not clobber a
file platform (so argparse must not default `--platform` to `"dos"`). `run()` privately ensures that
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
architecture changes. The embedding API expects native bindings beyond Python (planning/INTERFACES.md; planning/ROADMAP.md "The
CLI"): when shaping the public surface, never adopt a design that would be difficult to express in a common
binding language such as C or Java. The CLI is under the same constraint as the fallback binding for unbound
languages — never make it difficult to drive from a program.

## Dependencies and style

- Runtime dependencies are welcome when they pull their weight; declare
  them under `[project].dependencies` in `pyproject.toml`. Prefer the
  stdlib only when it serves the need equally well.
- Pillow is the image library: screenshot conversion uses it, and the
  planned landmark assets (decode normalization, pixel comparison, PNG
  text chunks) build on it rather than on hand-written encoders.
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
$pythonFiles = (Get-ChildItem reliquary,reliquary_tests -Filter *.py).FullName
.venv\Scripts\python.exe -m py_compile $pythonFiles
.venv\Scripts\python.exe -m unittest -v reliquary_tests
.venv\Scripts\python.exe -m build
```

`python -m build` builds an sdist and then a wheel from that sdist, which checks that the source archive is complete.
After packaging metadata changes, inspect `PKG-INFO` for at least the name, version, Python requirement, runtime
dependencies, and the presence of the `reliquary_tests` package in both built artifacts. For release-facing packaging
changes, install the wheel into a clean environment, change to a directory outside the source tree, and run
`python -m unittest -v reliquary_tests`. Downstream packagers should be able to run the same command against both their
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
- a name match with a uuid mismatch is an identity mismatch
- a stop refused on identity mismatch leaves the machine phase `running`
- stale state produces clear diagnostics and cannot target another VM

Use stdlib `unittest` and `unittest.mock` unless a compelling reason justifies another dependency.

## Documentation maintenance

README.md is a human-facing guide to what reliquary does, why it exists, and how to use it. Keep it explanatory and
task-oriented. Do not move agent instructions, implementation constraints, roadmap discussion, or maintenance notes into
it.

After changing commands, flags, paths, behavior, or Python interfaces, update README.md, CHANGELOG.md, and this file
wherever affected. CHANGELOG updates land under the unreleased section only: released history is never retroactively
edited — not even for stale paths or renamed concepts (the sole exception, minimal privacy/legal redaction, and the
full rule live in `.agents/skills/documentation-rules.md`). Validate documented CLI syntax with `reliquary --help` and
subcommand help.

## Architecture and prior art

reliquary uses QEMU's published `qemu.qmp` library for protocol handling and implements the machine-lifecycle role
locally. QEMU's in-tree `QEMUMachine`
is not published independently; if that changes, reassess whether replacing local lifecycle code would reduce
maintenance without weakening ownership checks or the public interface.

QEMU's own functional tests validate the broad model of scripting a guest over QMP and asserting on observable state.
reliquary adds the DOS-specific layer: keyboard conventions, VGA text scraping, prompt
completion, and vvfat staging.

SUSE's os-autoinst (the engine under openQA) is the closest prior art to reliquary as a whole: it drives OS
installers by screen matching and key injection over QMP/VNC, with per-operation "consoles" (VNC, serial,
virtio-terminal, ssh) mirroring reliquary's control planes, multiple backends (qemu, svirt, bare metal) mirroring the
adapter seam, command completion over serial via echoed marker strings, per-step screenshot records, and snapshot
"milestones" for resuming long installs. Use it as a **concept reference only** for control-plane and backend implementations — reliquary learns from its
designs (the input event model, needle area types, console seams), never from its code: it is GPL-2.0-or-later, so no
code, needles, or test modules may ever be ported or closely translated into this BSD-3-Clause project. Study the
documentation and the ideas; reimplement from scratch. Deliberate divergences to preserve: VGA text scraping instead of image needles for
text-mode guests, authored step documents instead of Perl test modules, and a local ephemeral-machine tool instead of
a testing service (scheduler, workers, and web UI are permanently out of scope).

Espressif's `pytest-embedded-qemu` is useful prior art for a future
`pytest-reliquary` plugin: host pytest orchestration around a native guest test framework. It is not directly reusable
because it assumes Espressif targets, serial output, and Unity result grammar.
