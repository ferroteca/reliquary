# Changelog

All notable changes to relict are documented here. The format is based
on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Package-based `relict/` source layout split into home containment, declared media, ownership-safe lifecycle, generic
  machine interaction, DOS platform behavior, workflow orchestration, and CLI modules while preserving the existing
  root import and command-line interfaces.
- The complete DOS runner from the original implementation: DOS remains the default platform, while
  `MachineConfig(platform=...)` and `--platform` make the platform choice explicit. The reusable QEMU machine layer is
  shared; unimplemented non-DOS platform workflows fail explicitly instead of borrowing DOS assumptions.
- `Runner`/`MachineConfig`: the generic embedding surface for callers driving relict as a runner. A
  `Runner(MachineConfig(...))` instance is a configured DOS test machine — configuration only, no per-run state — with
  `provision(drives_dir)` (ensure something bootable is declared under `drives_dir`: keep a present bootable image,
  copy the configured `boot_floppy_image` or `boot_hdd_image` to its media-typed stem keeping the image's own
  extension, or install the FreeDOS default; never overwrites) and `run(exe_path, args, home)` (the full
  `run_guest_program()` lifecycle with the home explicit). Concurrent runs in distinct homes are safe; per-home
  `vm.json` keeps VM ownership sound.
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
  relict switches to for guest program runs. Staging targets the highest staged directory declared among the
  hard-disk slots, or `drives/hdd` created on demand.
- Explicit `home=` keyword on `download()`, `start()`, `stop()`, `run_guest_program()`, and the `drives_dir` path
  helper, overriding the process-global home per call. The
  existing `set_home()`/`--home` surface is unchanged.
- Installable `relict_tests` unit-test package, runnable with
  `python -m unittest -v relict_tests` so users and downstream packagers can verify an unpacked source distribution or
  installed wheel.
- Contributor guidelines covering development, verification, pull requests, and BSD-3-Clause contribution licensing.
- agentless DOS-under-QEMU automation harness — boot DOS headless, send keystrokes over QMP, scrape the 80x25 text
  screen from VGA memory, run commands with prompt-based completion detection, take screenshots, stage guest media
  via vvfat, and run guest programs end to end
  (`run_guest_program`, returning the program's redirected output).
- Visible manual VM sessions with `relict start --display`: the command returns once QEMU is ready, leaves the DOS VM
  running for direct interaction, and `relict stop` closes it through the same ownership-verified lifecycle.
- Bring-your-own boot image: relict boots whatever the user declares under `drives/`; when nothing bootable is
  declared, the FreeDOS 1.4 boot floppy is installed automatically as `drives/floppy.img` from the ~23 MB
  FloppyEdition archive with SHA-256 verification (the archive itself is not kept).
- Test-framework result parsing is out of scope: relict hands back raw guest output, and interpreting it belongs to
  the caller.
- QEMU binary discovery: `RELICT_QEMU_HOME` / `QEMU_HOME`, then PATH, then well-known install locations; `--qemu`
  overrides.
- Home directory (boot images, staged guest drives, screenshots) defaulting to `relict/` under the user's Documents
  folder (the Windows known Documents folder, `~/Documents` on macOS, `xdg-user-dir DOCUMENTS` on Linux/BSD), falling
  back to `~/relict` when no Documents folder can be determined; override with `RELICT_HOME`, `--home`, or
  `set_home()`.
- Native PNG screendump on QEMU >= 7.1 with a zero-dependency PPM-to-PNG fallback for older QEMU.
- Automatic QMP port selection with the selected port returned by
  `start()`, active-VM metadata under the relict home for separate CLI invocations, and unique-name verification
  before any VM is controlled.
- DOS startup commands such as switching to C: use the ordinary
  `run_command()` scripting interface rather than special boot options.
- Screenshot names are constrained to filenames so captured images cannot be written outside the relict home.
- The installable test suite uses Python 3.9-compatible syntax, matching the package's declared minimum version.
