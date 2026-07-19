<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Roadmap

## Milestone 1 — FreeDOS plain install to hard disk

Script the FreeDOS 1.4 installer's "Plain DOS system" option from the
LiveCD distribution onto a hard-disk image. The goal is a working DOS
boot that demonstrates the full pipeline: media download and
verification, disk image creation, and a scripted installer run
through relict.

### Input

The [FreeDOS 1.4 LiveCD](https://freedos.org/download/) provides the
raw material. The recipe downloads `FD14-LiveCD.zip`, extracts
`FD14LIVE.iso` into the reliquary home
(`<home>/install-media/freedos/`), and deletes the zip; only the ISO
is kept, verified against a pinned SHA-256 on every run. A cached
copy that fails verification is erased and downloaded again.

### Output

A 20 MiB dynamically allocated qcow2 (v3) hard-disk image at
`<home>/machines/freedos-plain/drives/hdd.qcow2` holding an installed
plain FreeDOS system that boots in QEMU through relict and reaches a
native DOS prompt.

### Recipe contract

Each recipe is a module under `reliquary/recipes/`. A recipe module
exports an `install(display=False)` function that resolves its inputs
and outputs
under the reliquary home (see `reliquary/home.py`) and returns a
mapping of the artifacts it produced. Recipe machine directories are
relict homes, so relict can boot the declared drives directly.

The recipe is responsible for:

1. Acquiring and verifying its vendor installation media.
2. Creating the target disk image.
3. Scripting relict to run the vendor installer against the target
   disk (not yet implemented).

### Implementation steps

1. ~~Acquire and hash-verify the LiveCD media; create the blank 20 MiB
   qcow2 target disk; expose `reliquary install freedos-plain`.~~ Done.
2. ~~Extract the LiveCD ISO and boot the machine through relict with
   the ISO and target disk mounted, booting from the CD; block while
   the machine runs and shut it down on any exit, including
   Ctrl-C.~~ Done.
3. Script the installer's "Plain DOS system" path onto the target
   disk (the LiveCD boots to a live `D:\>` prompt; `SETUP.BAT` starts
   the installer). Watch the guest memory size: the LiveCD warns
   about limited RAM at relict's 16 MiB DOS default.
4. Add a verification pass that boots the installed disk and confirms
   a DOS prompt.

### Decisions still needed

- How the installer's interactive prompts are scripted beyond the
  first-menu `wait_screen` already in place (further screen waits vs.
  fixed key scripts).
- Whether the CLI supports a `--verify` flag that boots the result
  through relict after installation.

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
