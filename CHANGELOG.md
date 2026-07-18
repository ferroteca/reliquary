# Changelog

All notable changes to relict are documented here. The format is based
on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Project scaffolding: the packaged single-module layout (`relict.py` plus the installable `relict_tests` package),
  BSD-3-Clause licensing with REUSE conventions, and contributor guidelines.
- The stubbed public surface, recording the agreed design ahead of implementation: `Runner`/`RunnerConfig` (a
  configured Windows 9x test machine with `provision(dist_dir)` and `run(exe_path, args, home)`), the module-level
  `install()` / `run_guest_program()` lifecycle, home-directory helpers, and a `relict` CLI skeleton with `install`
  and `run` commands. All operations raise `NotImplementedError`.
- Guest-environment choice validation: a ready `boot_image=` never combines with the install-media options, and
  `media_url=` requires `media_sha256=`. There is deliberately no default Windows 9x environment.
- The staged guest drive is its own drive with a configurable letter (`staged_drive`, default `E:`,
  `--staged-drive` on the CLI) — C: is the boot image's system drive and D: usually the virtual CD-ROM, so letters
  are validated to the D–Z range (D: for machines with no CD-ROM attached).
