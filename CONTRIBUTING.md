# Contributing to relict

Thank you for helping improve relict. Bug reports, documentation fixes, tests, and code changes are welcome when they
preserve the project's Windows 9x automation model and BSD licensing.

relict is currently scaffolding: the public surface is stubbed and the implementation has not started. Contributions
that implement a stub should keep its documented signature and semantics.

## Before you start

For a substantial change, open an issue before investing significant work. This gives us a chance to agree on the
problem, scope, and approach. Small, focused fixes may go directly to a pull request.

Keep changes narrowly scoped and avoid unrelated cleanup. New behavior should include focused tests, especially for VM
lifecycle and failure paths.

Never contribute Microsoft software: no Windows images, install media contents, or product keys may enter the
repository, including as test fixtures.

## Development setup

relict supports Python 3.9 and newer. Create and use the project-local virtual environment:

```powershell
cd relict
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --group dev
python -m pip install -e .
```

Runtime code is standard-library-only except for `qemu.qmp`. Please discuss a new dependency before adding it.

## Make and verify a change

- Match the existing style and keep lines near 79 columns.
- Add or update stdlib `unittest` coverage for changed behavior.
- Update README.md and CHANGELOG.md when public behavior changes.
- Add SPDX headers to new files as described below.

Run the required checks from the project virtual environment:

```powershell
.venv\Scripts\python.exe -m py_compile relict.py relict_tests\test_runner.py
.venv\Scripts\python.exe -m unittest -v relict_tests
.venv\Scripts\python.exe -m build
git diff --check
```

## Verifying an installation or downstream package

The unit tests are included in both the source distribution and wheel. Run them from an unpacked source distribution,
or after installing a wheel, to verify relict in that environment without starting QEMU:

```powershell
python -m unittest -v relict_tests
```

The same command works in `sh` environments. Downstream packagers should run it once against their unpacked source
package and once from outside the source tree against the installed package they intend to ship. This checks both the
build environment and the final installed layout.

## Submit a pull request

Describe the problem, the chosen solution, and how you verified it. Keep each pull request reviewable as one coherent
change, and respond to review by updating the same branch.

Maintainer guidance and internal engineering constraints live in
[AGENTS.md](AGENTS.md). Contributors should read it before changing lifecycle, storage, packaging, or licensing
behavior.

## Contribution licensing

relict is licensed under the [BSD 3-Clause License](LICENSE). By submitting a contribution, you agree to license that
contribution under the same BSD-3-Clause terms. You retain copyright in your contribution.

Only submit work that you have the right to contribute on those terms. This means, as applicable, obtaining permission
from an employer or other rights holder and identifying third-party material and its license. Contributions that would
prevent relict from being used or distributed under its existing BSD-3-Clause license cannot be accepted.

Use accurate SPDX copyright information in each new file:

```text
SPDX-FileCopyrightText: YEAR COPYRIGHT HOLDER
SPDX-License-Identifier: BSD-3-Clause
```

Use the appropriate comment syntax for the file type. Files that cannot or should not carry comments must be added to
`REUSE.toml` with their actual copyright holder.
