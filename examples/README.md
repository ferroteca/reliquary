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
machines/freedos.json               the install machine
scripts/freedos-plain-install.rqs   install script + LiveCD definition
scripts/freedos-plain-verify.rqs    boot the result, confirm C:\>
```

The install script embeds the LiveCD definition. Its first run copies
that block to `media/freedos-1.4-livecd.json` before instantiating the
machine, so the verification script and later independent machine
commands resolve the same media through the ordinary library.

Then:

```powershell
reliquary script freedos freedos-plain-install
```

The machine declares a blank 20M hard disk and the LiveCD
attached, booting from CD. The install script drives the
installer's "Plain DOS system" path onto the disk.

Before verification, edit `machines/freedos.json` so the drive and
boot fields are:

```json
{
  "platform": "dos",
  "drives": {
    "hdd": {"size": "20M"},
    "cdrom": {
      "media": "freedos-1.4-livecd",
      "enabled": false
    }
  },
  "boot": ["hdd"]
}
```

This is the post-install form shown in the
[machine cookbook](../docs/machine-spec-cookbook.md#2-an-os-installation-machine).
Then run:

```powershell
reliquary script freedos freedos-plain-verify
```

The next start reconciles the machine to that declaration, and the
verify script confirms that the installed system reaches a DOS
prompt. A runtime `detach` followed by a host stop/start is not used:
`start` would correctly restore the authored declaration and
reattach the CD.
