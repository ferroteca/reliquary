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

Recipes fetch their vendor installation media automatically, verify it
against a pinned SHA-256, and cache it under the reliquary home
(`Documents\reliquary` by default; override with `--home` or the
`RELIQUARY_HOME` environment variable). Disk images are created under
`<home>\machines\<recipe>\drives`.

## License

BSD-3-Clause. See [LICENSE](LICENSE).
