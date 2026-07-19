<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Changelog

## 0.1.0.dev0 (unreleased)

Initial scaffold: package structure, CLI stub, and recipe module convention.

Added the `freedos-plain` recipe's preparation steps: the FreeDOS 1.4
LiveCD ISO is downloaded into the reliquary home (the distribution
zip is deleted after extraction) and SHA-256 verified on every run,
and
a 20 MiB dynamically allocated qcow2 (v3) target disk is created. The
`reliquary install <recipe>` CLI command runs a recipe by name, and
`--display` (the `display` recipe parameter) requests a visible QEMU
window for a recipe's guest steps.

The recipe now extracts the LiveCD ISO and boots the installation
machine through relict with the ISO and target disk mounted, booting
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
