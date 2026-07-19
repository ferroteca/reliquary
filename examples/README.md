<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Examples

> **Status:** these documents use the planned machine, media, and
> script formats ([docs/](../docs/)), written ahead of
> implementation. They are the target shape for the FreeDOS plain
> install (today's `reliquary install freedos-plain` recipe) and
> cannot run yet.

A complete, shareable FreeDOS 1.4 plain-install recipe in
reliquary's document formats. The directories mirror the reliquary
home; copy each file into the matching directory of your home:

```text
media/freedos-1.4-livecd.json       the LiveCD media definition
machines/freedos.json               the install machine
scripts/freedos-plain-install.rqs   the install script
scripts/freedos-plain-verify.rqs    boot the result, confirm C:\>
```

Then:

```powershell
reliquary create freedos
reliquary script freedos freedos-plain-install
reliquary script freedos freedos-plain-verify
```

The machine declares a blank 20M hard disk and the LiveCD
attached, booting from CD. The install script drives the
installer's "Plain DOS system" path onto the disk; the verify
script detaches the CD, restarts, and confirms the installed
system reaches a DOS prompt.
