<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Roadmap

## Milestone 1 — minimal FreeDOS bootable floppy

Build a minimal, self-contained FreeDOS bootable floppy image from the
FreeDOS 1.4 FloppyEdition distribution. The goal is a working DOS boot
that demonstrates the full pipeline: download handling, media extraction,
and image construction through relict.

### Input

The [FreeDOS 1.4 FloppyEdition](https://freedos.org/download/)
download provides the raw material. The distribution includes a bootable
floppy image and packaged utilities; the first milestone will extract only
the kernel, command interpreter, and boot files needed for a minimal
bootable floppy.

### Output

A 1.44 MB raw floppy image (`freedos_min.floppy.img`) that boots FreeDOS in
QEMU through relict and reaches a native DOS prompt.

### Recipe contract

Each recipe is a module under `reliquary/recipes/`. A recipe module exports
an `install(media_dir, output_dir, runner)` function (or similar shape,
to be finalized during milestone 1 implementation). The function receives
the path to the extracted or mounted installation media, a directory for
output artifacts, and a relict `Runner` instance preconfigured for the
target environment.

The recipe is responsible for:

1. Validating that the supplied media contains the expected files.
2. Constructing a bootable disk image in `output_dir`.
3. Optionally scripting relict to verify the image boots, though a
   standalone disk image is sufficient for milestone 1 completion.

### Implementation steps

1. Design and stabilize the recipe module contract (function signature,
   return type, error conditions).
2. Implement `reliquary/recipes/freedos.py`:
   - Parse the FloppyEdition media directory to locate the kernel
     (`KERNEL.SYS`), command interpreter (`COMMAND.COM`), and boot files.
   - Construct a minimal FAT12 filesystem with a boot sector.
   - Write the output floppy image.
3. Implement the CLI `install freedos` subcommand using the recipe.
4. Add a smoke test that verifies the recipe can be imported and produces
   a predictable empty-floppy image, plus a manual integration test that
   boots the result through relict.

### Decisions still needed

- Whether reliquary includes its own FAT12 filesystem builder or delegates
  to an external tool (mtools, a pure-Python FAT library, etc.).
- The exact recipe function signature and return type.
- How media directories are declared: local paths, downloaded archives,
  or both.
- Whether the CLI supports a `--verify` flag that boots the result through
  relict after construction.

## Design principles

- **One recipe, one target.** Each OS version and edition gets one module.
  Avoid parameterized mega-recipes that mutate behavior based on flags.
- **Installation media is input, disk images are output.** Recipes consume
  vendor media and produce bootable images. They are not runtime
  configuration generators.
- **relict is the guest runtime.** Recipes may use relict to validate
  output or to script interactive installers, but recipes do not replace
  relict workflows.
- **Stdlib-first.** Avoid dependencies except relict unless a dependency
  justifies itself through real implementation burden.
