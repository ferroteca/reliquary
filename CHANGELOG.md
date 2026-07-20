<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Changelog

All notable changes to reliquary are documented here. The format is based
on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 0.1.0.dev0 (unreleased)

The relict project — the agentless QEMU guest automation harness reliquary
was built on — has been folded into reliquary. Its modules now live in the
`reliquary` package (its drive-inventory module renamed to `drives.py`), its
CLI commands are `reliquary` subcommands alongside `install`, and its home,
`RELICT_HOME`/`RELICT_QEMU_HOME` environment variables, and default
`Documents/relict` directory are replaced by the reliquary equivalents
(`RELIQUARY_HOME`, `RELIQUARY_QEMU_HOME`, `Documents/reliquary`). The notes
below merge both projects' unreleased histories with the relict entries
renamed accordingly.

### Recipe layer

Initial scaffold: package structure, CLI stub, and recipe module convention.

The planned `.rqs` scripting language now separates linear scripts
from explicit state machines, uses run-to-completion reactive states,
and adds immutable text, media, and secret inputs bound from JSON
responses, a home-wide user property registry, or interactive prompts.
Ordinary reusable values live in `properties.json`; passwords and
product keys can use secret markers backed by the host credential
store, and script declarations bind them with `property:`. Scripts may
also embed the same JSON media-definition objects used by the shared
library; after preflight, running a script installs missing definitions
into `media/` without overwriting or updating existing files, while
verified artifacts continue to use shared caches. Console input is
expressed with `enter` rather than a separate `run` verb; guest reboot
remains console or menu input, while host power cycling is the explicit
`stop`/`start` pair. Timing, matching, preflight, transcript, and
offline file-exchange semantics are specified consistently ahead of
implementation.

Added the `freedos-plain` recipe's preparation steps: the FreeDOS 1.4
LiveCD ISO is downloaded into the reliquary home (the distribution
zip is deleted after extraction) and SHA-256 verified on every run,
and
a 20 MiB dynamically allocated qcow2 (v3) target disk is created. The
`reliquary install <recipe>` CLI command runs a recipe by name, and
`--display` (the `display` recipe parameter) requests a visible QEMU
window for a recipe's guest steps.

The recipe now extracts the LiveCD ISO and boots the installation
machine with the ISO and target disk mounted, booting
from the CD. After start it waits for the LiveCD's first install menu
(`Welcome to FreeDOS 1.4 (LiveCD)`), selects "Install to harddisk",
accepts the defaults for preferred language and the installer welcome
screen with Enter, confirms partitioning drive C: and the required
reboot with Yes, accepts the default keyboard layout with Enter,
chooses the "Plain DOS system" package set (excluding the "with
sources" sibling), and confirms with Yes on the ready-to-install
prompt. `install` then blocks while the machine runs and always shuts
it down when it ends — including on Ctrl-C, which the CLI reports as
an interruption instead of a traceback. Further installer scripting
is not yet implemented.

### Machine layer (formerly relict)

### Fixed

- A configured drive source for a slot already declared by a filesystem
  drive now fails closed with a slot-clash error instead of silently
  replacing it. An explicit `enabled: true` on the configured entry
  remains the deliberate way to override the filesystem drive, and
  `enabled: false` still unmounts it.

### Added

- Path helpers for the planned blueprint home layout:
  `blueprints_dir`, `media_dir`, `scripts_dir`, `cache_dir`,
  `downloads_cache_dir`, `media_cache_dir`, and `machines_cache_dir`
  (each accepts optional `home=`). The existing `drives/` /
  `machine.json` / `vm.json` machine model is unchanged.
- `cursor_menu_select(item, timeout=30, exclude=(), port=None,
  home=None)` and the `reliquary menu ITEM [--exclude TEXT]` CLI command
  select an entry in a cursor-key driven text menu (for example a boot
  menu). Rows containing an `exclude` text are never selected. Menus
  that rewrite their rows as the highlight moves (the FreeDOS
  installer's language chooser) are navigated by the row where the
  item last matched. Navigation is feedback-driven:
  reliquary presses the up/down cursor keys, follows the selection
  highlight through the VGA attribute bytes, and presses Enter only
  once the highlight sits on the single screen row matching the given
  text (case-insensitively; an exact row match wins over rows merely
  containing the item, which otherwise must be unique). Also available
  as
  `Machine.cursor_menu_select()`; `machine.vga_screen(qmp)` newly
  exposes the attribute bytes alongside the text rows.
- `create_hdd_image(filename, capacity)` creates a sparse qcow2 v3
  (`compat=1.1`, no preallocation) hard-disk image at the given path.
  Capacity accepts a qemu-img size string (`"2G"`, `"512M"`) or a
  positive integer MiB value. `find_qemu_img()` resolves `qemu-img`
  with the same search order as `find_qemu()`.
- `Machine.screen_text()` and `Machine.wait_text(pattern, timeout=60)`
  read and wait on the guest's VGA text screen directly from a `Machine`,
  so tasks and adapters can block until specific output (for example a
  boot menu) is displayed. The module-level `screen_text()` and
  `wait_text()` now delegate to these methods.
- `documents_dir()` publicly resolves the user's platform Documents
  folder (or `None` when it cannot be determined), so embedding
  projects can anchor their own state directories the same way reliquary
  anchors its home.

### Removed

- The `boot-to-dos` CLI command. Wait for a prompt with `reliquary wait`.
  Programmatic boot readiness remains `AgentlessGuestExec.wait_ready()`.

### Changed

- Keyboard input and screen interaction moved to the platform-neutral
  machine layer, since they need only QMP and VGA text mode, not DOS:
  `char_keys()`, `send_keys()`, `send_text()`, `cursor_menu_select()`,
  `screen_text()`, and `wait_text()` now live in `reliquary.machine`, and
  `Machine` gains `send_keys()`, `send_text()`, and
  `cursor_menu_select()` methods. `interaction_agentless` retains only
  the DOS prompt-driven `AgentlessGuestExec` adapter. Package-level
  imports (`reliquary.send_text`, ...) are unchanged.
- Added an internal, runtime-checkable `GuestExec` protocol and isolated the
  QMP keyboard/VGA implementation as `AgentlessGuestExec`, with the DOS
  workflow and CLI consuming that adapter directly. The former
  `boot_to_dos()` and `run_command()` Python facades were removed; use
  `AgentlessGuestExec.wait_ready()` and `.execute()`.
- Exposed the identity-verified QMP session through `Machine.qmp()` for raw
  `cmd()` and `hmp()` access; interaction adapters now depend on `Machine`
  instead of opening QMP connections themselves.
- One validated `MachineConfig` now threads through the workflow and
  lifecycle layers. `start()`, `run_task()`, and `run_guest_program()` take a
  `MachineConfig`, versioned mapping, or JSON path as their sole machine
  settings input; `Runner.run()` passes its configuration through unchanged,
  and the QEMU launcher consumes that configuration instead of loose hardware
  arguments. The default QEMU argument vector is unchanged.
- The Python API now automatically discovers and loads `<home>/machine.json`
  when no explicit configuration is provided, matching CLI behavior. Explicit
  API values (passed as `MachineConfig`, mapping, or path) override the file
  values; `Runner` likewise loads the file when `config=None`.

### Added

- `--machine PATH` CLI argument for explicit machine configuration file selection; when omitted, the CLI automatically
  loads `<effective-home>/machine.json` if present, otherwise uses the default `MachineConfig()`. Explicit CLI
  overrides (`--platform`, `--qemu`, and raw QEMU arguments) apply on top of the loaded configuration; an omitted
  `--platform` leaves the file's platform unchanged, while `--platform dos` still overrides a non-DOS file value.
- `MachineConfig.from_file()` and `MachineConfig.from_mapping()` load a versioned JSON/mapping machine document
  (`version` must be `1`), normalize it immutably, resolve relative drive sources from the file directory or an
  explicit `base_dir`, and apply field overrides with deterministic merge rules for drives and options.
- Package-based `reliquary/` source layout split into home containment, declared media, ownership-safe lifecycle, generic
  machine interaction, DOS platform behavior, workflow orchestration, and CLI modules while preserving the existing
  root import and command-line interfaces.
- The complete DOS runner from the original implementation: DOS remains the default platform, while
  `MachineConfig(platform=...)` and `--platform` make the platform choice explicit. The reusable QEMU machine layer is
  shared; unimplemented non-DOS platform workflows fail explicitly instead of borrowing DOS assumptions.
- DOS 8.3 executable-name validation now belongs to the DOS platform module rather than generic workflow
  orchestration, so future guest-program workflows are not constrained by DOS naming rules.
- `Runner`/`MachineConfig`: the generic embedding surface for callers driving reliquary as a runner.
  `Runner(home=None, config=None)` is a configured DOS test machine bound to one absolute home (the established
  process default when omitted), and
  `run(exe_path, args)` automatically ensures bootable media before performing the full `run_guest_program()`
  lifecycle. Provisioning is private; callers create distinct runners with distinct homes for concurrent runs, and
  per-home `vm.json` keeps VM ownership sound.
- Removed the `boot_floppy_image` and `boot_hdd_image` configuration shortcuts. Custom boot media uses the ordinary
  declared-drive inventory.
- `MachineConfig.drives` adds immutable configured drive specs using canonical logical slots plus `floppy`/`hdd`
  slot-zero aliases. A spec accepts a source path or `{source, options}` mapping; files mount as images, floppy and
  hard-disk directories mount as vvfat, and CD-ROM directories fail validation. Configured and home-directory media
  resolve into one inventory with slot conflicts rejected before launch.
- `MachineConfig.machine` maps directly to one QEMU `-machine` argument. A string selects the machine type; a mapping
  combines required `type` with immutable scalar properties and renders Boolean values as `on`/`off`. A raw
  `-machine` or `-M` in `qemu_args` conflicts with the structured field.
- `MachineConfig.memory` configures guest memory as a positive integer number of MiB, defaulting to 16 for DOS, 64
  for Win9x, and 256 for WinNT. It maps to one QEMU `-m` argument; an explicit value conflicts with raw `-m` in
  `qemu_args`, while a raw `-m` alone suppresses the platform default.
- The `drives/` directory under the home declares the whole machine by filename, with image content never
  interrogated. Image files `floppy[_<n>].<ext>` (slots 0–1, A: and B:), `hdd[_<n>].<ext>` (slots 0–3, the IDE bus),
  and `cdrom[_<n>].<ext>` (the IDE slots after the hard disks) mount as that medium; bare directories `floppy[_<n>]`
  and `hdd[_<n>]` mount as virtual FAT drives. An unindexed name means slot 0 (so `hdd.img` and `hdd_0.img` clash,
  as do all duplicate slots — fail closed). The idiomatic extension declares the image format: `*.img` and `*.iso`
  are taken as raw and pinned (avoiding QEMU's format-probing warning); any other extension (`hdd.qcow2`,
  `hdd.vmdk`, ...) is handed to QEMU to identify. Memory defaults to 16 MB and the boot order to a best guess from
  the declared media (slot-0 floppy image, else slot-0 hard-disk image, else cdrom); `-m` or `-boot` in the extra
  QEMU arguments overrides the corresponding default.
- The staged guest hard drive's letter is explicit configuration: `staged_drive` on `MachineConfig` and
  `run_guest_program()` (valid C–Z, normalized uppercase; default: match the declared machine, one letter per
  hard-disk slot before the staged drive, so C: on a floppy-boot machine and D: behind a slot-0 hard-disk image;
  letters below the default are rejected) declares where the staged vvfat hard disk appears in the guest — the drive
  reliquary switches to for guest program runs. Staging targets the highest staged directory declared among the
  hard-disk slots, or `drives/hdd` created on demand.
- Explicit `home=` keyword on `download()`, `start()`, `stop()`, `run_guest_program()`, and the `drives_dir` path
  helper, overriding the process-global home per call. The
  existing `set_home()`/`--home` surface is unchanged.
- Installable `reliquary_tests` unit-test package, runnable with
  `python -m unittest -v reliquary_tests` so users and downstream packagers can verify an unpacked source distribution or
  installed wheel.
- Contributor guidelines covering development, verification, pull requests, and BSD-3-Clause contribution licensing.
- agentless DOS-under-QEMU automation harness — boot DOS headless, send keystrokes over QMP, scrape the 80x25 text
  screen from VGA memory, run commands with prompt-based completion detection, take screenshots, stage guest media
  via vvfat, and run guest programs end to end
  (`run_guest_program`, returning the program's redirected output).
- Visible manual VM sessions with `reliquary start --display`: the command returns once QEMU is ready, leaves the DOS VM
  running for direct interaction, and `reliquary stop` closes it through the same ownership-verified lifecycle.
- Bring-your-own boot image: reliquary boots whatever the user declares under `drives/`.
- Test-framework result parsing is out of scope: reliquary hands back raw guest output, and interpreting it belongs to
  the caller.
- QEMU binary discovery: `RELIQUARY_QEMU_HOME` / `QEMU_HOME`, then PATH, then well-known install locations; `--qemu`
  overrides.
- Home directory (boot images, staged guest drives, screenshots) defaulting to `reliquary/` under the user's Documents
  folder (the Windows known Documents folder, `~/Documents` on macOS, `xdg-user-dir DOCUMENTS` on Linux/BSD), falling
  back to `~/reliquary` when no Documents folder can be determined; override with `RELIQUARY_HOME`, `--home`, or
  `set_home()`.
- Native PNG screendump on QEMU >= 7.1 with a zero-dependency PPM-to-PNG fallback for older QEMU.
- Automatic QMP port selection with the selected port returned by
  `start()`, active-VM metadata under the reliquary home for separate CLI invocations, and unique-name verification
  before any VM is controlled.
- DOS startup commands such as switching to C: use the ordinary
  `AgentlessGuestExec.execute()` interface rather than special boot options.
- Screenshot names are constrained to filenames so captured images cannot be written outside the reliquary home.
- The installable test suite uses Python 3.9-compatible syntax, matching the package's declared minimum version.
