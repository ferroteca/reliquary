# relict

relict is a Python automation harness for running Windows 9x programs under QEMU. It boots an installed Windows 9x
guest, runs one program in it, and returns the program's output — intended for automated testing of software built for
Windows 95 and 98.

A *relict* is a survivor: an organism or population persisting from a vanished ecosystem. So too the software this
project runs.

> **Status: scaffolding.** The project structure and public surface exist; the implementation does not. Every operation
> currently raises `NotImplementedError`. The design summarized below is settled; the code is not yet written.

## The model

Windows 9x cannot be automated the way a DOS guest can — there is no text screen to scrape and no prompt to watch. And
unlike FreeDOS, there is no freely distributable default guest. relict therefore works as follows:

- **You supply the environment.** Either a ready bootable hard-disk image (`boot_image=`), or Windows 9x install media —
  a CD ISO path (`install_media=`) or a download URL (`media_url=` plus its mandatory `media_sha256=`) — with whatever
  `product_key=` the installer requires. There is deliberately no default.
- **relict installs once.** From install media, a one-time unattended install builds the bootable hard-disk image
  `dist/boot.img` under the relict home. How relict arranges program execution inside the guest (for example, a run hook
  baked into the image during that install) is its own business, invisible to callers.
- **One run, one boot.** A run stages the (8.3-named) executable on a virtual FAT guest drive, boots the image, executes
  the program with its output redirected to a log on that drive, and detects completion by the guest shutting itself
  down. The log text is returned uninterpreted — interpreting it is the caller's job.
- **The staged drive is its own drive.** C: is the boot image's system drive and D: usually the virtual CD-ROM, so
  staged files appear under a separate letter — E: by default, selectable with `staged_drive=` (`--staged-drive` on the
  command line). Any letter from D: to Z: is accepted; D: works on a machine with no CD-ROM attached.

## Planned surface

Command line:

```text
relict install [--install-media ISO | --media-url URL --media-sha256 HASH] [--product-key KEY]
relict run PROG.EXE [ARGS] [--staged-drive LETTER] [--timeout SECONDS]
```

Python, for callers embedding relict as a runner (mirroring the module-level functions):

```python
import relict

machine = relict.Runner(relict.RunnerConfig(install_media="win98.iso", product_key="KEY-123"))

machine.provision("cache/dist")                      # ensure cache/dist/boot.img exists (one-time install)
log = machine.run("SUITE.EXE", "-v", home="run-42")  # boots run-42/dist/boot.img; state stays under run-42/
```

A `Runner` instance carries configuration only — never per-run state, which lives under a home directory passed
explicitly to each operation — so one machine can serve concurrent runs in distinct homes.

## Requirements

- Python 3.9 or newer
- QEMU with `qemu-system-i386`
- Windows 9x install media or an installed image, and a license for it — relict ships no Microsoft software and cannot
  provide one

## License

relict is distributed under the BSD 3-Clause License. See [LICENSE](LICENSE).

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow and contribution
licensing terms.
