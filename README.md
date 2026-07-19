# reliquary

reliquary scripts OS installations from standard vendor installation media,
using [relict](https://github.com/anomalyco/relict) for QEMU guest automation.
It produces bootable disk images without manual interaction.

## Installation

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

reliquary depends on relict, which must be installed alongside it.

## Usage

```powershell
reliquary --help
reliquary install freedos-plain
```

`install` runs the whole recipe in the foreground: it fetches and
verifies the vendor media, prepares the target disk, and boots the
installation machine through relict, blocking until the machine
exits. Interrupting reliquary (Ctrl-C) shuts the machine down rather
than leaving it running. Pass `--display` to show the QEMU window
instead of running headless — helpful when debugging a recipe.

Recipes fetch their vendor installation media automatically and cache
it under the reliquary home; the cached media (e.g. an installer ISO
extracted from a distribution zip — the zip itself is not kept) is
verified against a pinned SHA-256 on every run
(`Documents\reliquary` by default; override with `--home` or the
`RELIQUARY_HOME` environment variable). Disk images are created under
`<home>\machines\<recipe>\drives`.

## License

BSD-3-Clause. See [LICENSE](LICENSE).
