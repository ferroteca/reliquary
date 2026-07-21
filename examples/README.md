<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Examples

> **Status:** the blueprint and the machine model these scripts use
> (empty removable slots, the `machine:` header, persistent
> `insert`/`eject`) are implemented. The install script's embedded
> `media` block uses the planned self-contained-script format
> ([docs/script-spec.md](../docs/script-spec.md)), which is not
> installed on first run yet; until that lands, also copy the media
> definition as a separate library document (the built-in
> `freedos-1.4-plain` artifacts ship it that way).

A complete, shareable FreeDOS 1.4 plain-install blueprint bundle in
reliquary's document formats. Assets are identified by extension,
so the directories are organizational dressing mirroring the
reliquary home's convention; use the bundle in place as an asset
root, or copy the files into your home:

```text
blueprints/freedos.rlqb             the install machine blueprint
scripts/freedos-plain-install.rlqs   install script + LiveCD definition
scripts/freedos-plain-verify.rlqs    boot the result, confirm C:\>
```

The install script embeds the LiveCD definition. Its first run
installs that block as `freedos-1.4-livecd.rlqm` before creating
the machine, so the verification script and later independent
machine commands resolve the same media through the ordinary
catalog.

Then:

```powershell
reliquary --blueprint freedos script freedos-plain-install
```

With no machine of the blueprint yet, `script` creates one; the blueprint
name then selects that machine on every later command. The blueprint
declares 32 MiB of memory (the FreeDOS LiveCD warns about low RAM
at the 16 MiB DOS default), a blank 20M hard disk, and an **empty**
CD drive (`"cdrom0": null`), booting hard disk first then CD. The
blueprint alone defines the machine's hardware; the install script
supplies the installer medium itself: it declares `machine: stopped`,
inserts the LiveCD into the empty slot, starts the machine, and drives
the installer's "Plain DOS system" path onto the disk. A blank hard
disk fails to boot, so firmware falls through to the inserted CD —
no boot-order change is needed.

The insertion is definitive machine state, persisted in the
machine's state document across stop/start — the machine diverges
from its blueprint while the installer CD is in the drive. The
script's final `eject` restores the blueprint shape, so no blueprint
edit or `apply` is needed before verification: the same
`["hdd0", "cdrom0"]` boot order now boots the installed hard disk.

```powershell
reliquary --blueprint freedos script freedos-plain-verify
```

The verify script also declares `machine: stopped`, issues a plain
`start`, and confirms that the installed system reaches a DOS prompt.
If an interrupted install run left the CD attached, a future
`apply` is the one-command recovery back to the blueprint shape;
until it lands, re-run the install script or recreate the machine.
