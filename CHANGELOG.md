<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Changelog

## 0.1.0.dev0 (unreleased)

Initial scaffold: package structure, CLI stub, and recipe module convention.

Added the `freedos-plain` recipe's preparation steps: the FreeDOS 1.4
LiveCD is downloaded and SHA-256 verified into the reliquary home, and
a 20 MiB dynamically allocated qcow2 (v3) target disk is created. The
`reliquary install <recipe>` CLI command runs a recipe by name. The
scripted installer run is not yet implemented.
