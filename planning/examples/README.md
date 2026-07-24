<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# Examples

> **Status:** the composed blueprint and the machine model these
> scripts use (empty removable slots, the `machine` header, persistent
> `insert`/`eject`) are implemented, and the scripts speak the
> redesigned script surface
> ([planning/design/script-spec.md](../design/script-spec.md)).

A complete, shareable FreeDOS 1.4 plain-install bundle. Everything the
machine needs — its media, and the archive that media is extracted
from — travels inside one composed `.rlqb` blueprint; only the
automation scripts are separate files. Use the bundle in place as an
asset root, or copy the files into your home:

```text
blueprints/freedos.rlqb              the machine and its media/archive
scripts/freedos-install.rlqs   install script
scripts/freedos-verify.rlqs    boot the result, confirm C:\>
```

One file, named components. The blueprint declares a `machines` entry
(`freedos`), a `media` entry (`blank-20m`), and an `archives` entry
(`freedos-livecd-zip`). A machine drive names a media and nothing more; the
media owns how it materializes. So `hdd0` names `blank-20m` — a `new`
20M blank — and `cdrom0` is an **empty** removable slot
(`"cdrom0": null`). The installer medium is the `freedos-livecd`
media: a `read-only` member (`FD14LIVE.iso`) of the `freedos-livecd-zip`
archive, itself a `url` download with a pinned hash. A script
references that media by name and never carries a definition; Reliquary
resolves the name against the components of whichever asset source
supplies the blueprint.

Then:

```powershell
rlq run-script freedos-install --blueprint freedos
```

With no machine of the blueprint yet, `run-script` creates one; the
blueprint name then selects that machine on every later command. The
blueprint declares 32 MiB of memory (the FreeDOS LiveCD warns about
low RAM at the 16 MiB DOS default), the blank 20M hard disk, and an
empty CD drive, booting hard disk first then CD. The blueprint alone
defines the machine's hardware; the install script supplies the
installer medium itself: it declares `machine stopped`, inserts the
LiveCD into the empty slot, starts the machine, and drives the
installer's "Plain DOS system" path onto the disk. A blank hard disk
fails to boot, so firmware falls through to the inserted CD — no
boot-order change is needed.

The insertion is definitive machine state, persisted in the machine's
state document across stop/start — the machine diverges from its
blueprint while the installer CD is in the drive. The script's final
`eject` restores the blueprint shape, so no blueprint edit or `apply`
is needed before verification: the same `["hdd0", "cdrom0"]` boot order
now boots the installed hard disk.

```powershell
rlq run-script freedos-verify --blueprint freedos
```

The verify script also declares `machine stopped`, issues a plain
`start`, and confirms that the installed system reaches a DOS prompt.
If an interrupted install run left the CD attached, a future `apply`
is the one-command recovery back to the blueprint shape; until it
lands, re-run the install script or recreate the machine.
