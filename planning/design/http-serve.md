<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Local HTTP server for installer answer files

> **Status:** planned — ROADMAP milestone 5. Packer parity is the
> settled shape; the "Decide first" round in that milestone binds
> the authored form, address expansion, and QEMU reachability into
> reliquary's surfaces. Distinct from the deleted property-binding
> "response file" concept (planning/DECISIONS.md).

## Purpose

Guests whose installers already accept a declarative answer file
— Kickstart, preseed, AutoYaST, Windows `unattend.xml`, and kin —
should consume that path rather than a keystroke script that
reinvents it. Packer's builders solve delivery with an ephemeral
local HTTP server the guest fetches from during the build.
reliquary adopts the same pattern.

This does not compete with those formats, and it does not weaken
agentless keystroke scripting for guests that lack them
(planning/ROADMAP.md "Procedural and declarative"; language goal
G1 is about the control plane, not a ban on the installer's own
answer-file mechanism).

## Packer parity (settled)

As Packer does today:

- Serve either a directory tree (`http_directory`) or an
  in-memory path→content map (`http_content`); the two conflict
  and are never combined.
- Listen on a randomly chosen free port in a configurable
  min/max range (Packer defaults: 8000–9000); setting min=max
  pins a single port.
- Expose the live address to the automation that must tell the
  installer where to fetch (Packer's `{{ .HTTPIP }}` /
  `{{ .HTTPPort }}` in `boot_command`).
- Lifetime is the run: start before the guest needs the file,
  tear down on every terminal path.
- The guest reaches the server over the VM network; the host
  does not push the file into the guest.

## Open (milestone 5 "Decide first")

- Where the directory or content map is declared (script header,
  blueprint field, sibling asset directory under authored-asset
  resolution).
- How scripts bind the live IP and port into `type`/`enter`
  (and any boot-argument path) without becoming computational
  (G2) or selecting control flow (G3).
- Which QEMU network configuration makes the host reachable from
  the guest, and whether that needs a first-class blueprint NIC
  now or a QEMU-default / `backend-settings` interim.
- Whether answer-file bodies may be property-expanded at serve
  time (product keys, passwords), and how transcripts avoid
  leaking them.

## Non-goals

- A reliquary-owned declarative install language.
- Replacing the FreeDOS (or other answer-file-less) keystroke
  path.
- A long-lived or home-wide HTTP service — the server is
  run-scoped only.
- Serving arbitrary host filesystems beyond the declared
  directory or content map.
