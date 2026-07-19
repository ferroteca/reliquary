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
reliquary install freedos --media <path-to-floppy-edition>
```

## License

BSD-3-Clause. See [LICENSE](LICENSE).
