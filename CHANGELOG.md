<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: GPL-3.0-only
-->

# Changelog

All notable changes to Reliquary are documented here. The format is based
on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

- **The interpretation layer has a conformance corpus** (F43), and it
  is the first one whose fixtures nobody wrote: seven `.rlqt`
  captures of real FreeDOS runs against QEMU — the three codex
  scripts and four ordinary commands — replayed in the default suite
  through the
  shipped `control_display`, `interaction_agentless` and script
  dispatch, with no hypervisor. A fixture asserts by being
  replayable: a call the capture never covered is an error, every
  recorded call must be made, and the replay must reach the
  conclusion the capture recorded.

  **Which is how a capture of a wrong answer becomes a fixture**, and
  three of the four command captures are exactly that. `rlq exec`
  today: refuses a command longer than 80 columns
  (`screen.no-echo`, because the echo wraps and no row *ends* with
  it); returns an **empty result with no error** when the output's
  own last line looks like the echo — a file whose last line reads
  `C:\>TYPE C:\ECHOLIKE.TXT` is enough, and the spec's promise of
  "the command's own output or a failure" is broken by it; and never
  completes against a guest whose `PROMPT` has been customized, since
  the prompt pattern admits no suffix. None is fixed here — what
  counts as a DOS prompt, or as an echo, is a decision rather than a
  test fixture's to settle — and each fixture retires itself loudly
  when the gap closes.

- **A stopped-only verb reached running is refused before the run**
  (T27; V17). `set-boot` and F54's scoped `boot` head write a
  launch-time firmware order, which is stopped-only as a property of
  the machine. Reached with the machine up they failed closed and by
  name — at **run** time, and for the shape that provokes them (flip
  the boot device, start, install, stop, flip back) run time means
  after five minutes of installing.

  **The script text already decided it.** The header declares the
  starting state and the language knows exactly which verbs start and
  stop the machine, so the verdict now lands at parse time, exit `2`,
  before anything reaches a guest. A scope's **exit** is checked with
  its entry — the half no author can see coming, since it is reached
  by finishing and by every failure too — which is the check F54
  deferred to this analysis.

  **Bounded by what a static pass can promise, and silent everywhere
  else.** Control reaching a handler body is the guest's decision, so
  nothing inside one is judged and no phase only a handler transfers
  to is analysed — the boundary `reach` already draws. Handler bodies
  are still walked for their *effect* on the machine, and two paths
  that disagree answer nothing at all. A `wait machine=stopped` that
  completed has observed the machine down and leaves it stopped, so
  the shape every script that powers a guest off from inside already
  ends with keeps working. A false refusal would be far worse than
  the late failure this replaces, and the run-time refusal remains
  for everything the plan cannot promise.

  The diagnostic is the machine layer's own id, unchanged —
  `machine.must-be-stopped` — so a consumer switching on it never has
  to know which layer noticed.

- **The scoped machine-state change** (F54; U24, U26, D104). A
  script's `insert`, `eject` and `set-boot` change the machine
  durably and leave it changed; the author writes the undo by hand,
  in a place no failure path reaches. A `with` block gives one such
  change a scope, and **the scope undoes it**:

  ```rlqs
  with boot cdrom0 {
      phase startup { … }
      phase cd-boot { … }
  }
  ```

  The head vocabulary is closed at three names. `insert` and `eject`
  are those verbs written exactly as they are written as statements,
  carrying their own signatures and their own preflight. The third
  is **`boot`, not `set-boot`, and it states a prefix**: the drives
  named come first and the machine's own order follows, so
  `with boot cdrom0` over a machine ordered `["hdd0", "cdrom0"]`
  boots `["cdrom0", "hdd0"]` and an author never restates an order
  they are not changing. `set-boot` is untouched — replacement is
  still what that verb means.

  A block **wraps the enclosing shape's own units** — phases in a
  phased script, statements in a linear one — which is what gives
  the language a word for a *stage*. **The scope is where control
  is, not where the text is**: it holds while control is inside the
  group, is entered by reaching any phase in it including by `goto`
  from outside, and is left by reaching a phase outside it or by the
  run ending; re-entry re-applies. A lexical reading would have
  reverted at the first transition and expressed nothing, every
  phase body ending in one.

  **On exit the target returns to the value it held on entry**, on
  every outcome the runtime reaches — `finish`, a failure, a
  cancellation at a boundary. A **boot restore requires a stopped
  machine**: the boot order is stopped-only as a property of the
  machine, and a restore is not exempted from a rule a second writer
  would erode, so an exit reached with the machine running fails the
  run naming the change it could not undo. Media restores carry no
  such rule. **One scope per target**; scopes on different targets
  nest freely. Entry and restore are on the run event stream
  (`scope.enter`, `scope.restore`), and a failure report names every
  restore performed — what a scope takes back is state a
  diagnostician would otherwise have found.

  **The shipped FreeDOS pair moved with it.** `freedos.rlqb` now
  declares `boot: ["hdd0", "cdrom0"]` — what the machine *is*, a
  system that boots its own disk past an empty optical drive — and
  `freedos-install.rlqs` wraps its phases in `with boot cdrom0`,
  keeping its mid-install `eject`. An interrupted install no longer
  leaves a machine that boots its installer forever.

  Not yet static: a boot restore an exit *provably* reaches with the
  machine running is a run failure rather than an authoring refusal.
  Moving that verdict to parse time is T27's reachability analysis,
  and the check reuses it when it lands.

- **JSON5 blueprints** (F53; D102). `.rlqb` documents accept the
  published JSON5 grammar — comments, trailing commas, unquoted
  keys, single-quoted strings, hexadecimal and signed numbers, and
  the rest — instead of the former project-defined JSONC dialect.
  `NaN`, `Infinity`, and `-Infinity` are refused so parsed values
  remain ordinary JSON data. Source-positioned diagnostics are
  retained. Machine-written files stay strict JSON. The reader lives
  in `json5reader` (Apache-2.0 `json5` package underneath).

- **`restart-machine`** stops a machine if it is running and starts
  it — the ordinary move while a script is being written, which
  until now took two commands. It is **one act rather than two**:
  the per-machine operation lock is held across both halves, so
  nothing can start the machine, change its media or apply a
  blueprint in between. That is not a new kind of guarantee — it is
  the same lock every mutating operation already takes, simply not
  released in the middle — and it is what stops a restart from
  returning to a machine someone else has started and failing as
  `machine.already-running`. A machine that is **already stopped is
  started** rather than refused: the end state asked for is
  *running*, so the answer does not depend on a phase the caller
  need not know, and one caught mid-`stopping` is reconciled first.
  Takes `--display` and a positional id like its siblings; the twin
  is `restart_machine`.

- **`list-backends`** reports the backends discovered on the host and
  their installation home directories. It is CLI-only; `--json`
  returns the same `{backend, home}` records for automation.

- **VirtualBox agentless display and FreeDOS parity** (F52, cut from
  F3 with F50/F51). `keyboardputscancode` input, `screenshotpng`
  capture, live medium change, and `text_screen` via F51's
  recognizer — then `agentless-display` claimed. Opt-in FreeDOS
  integration: `RELIQUARY_INTEGRATION=1` with
  `tests.test_freedos_virtualbox_integration` (pins
  `backend: virtualbox` on the seeded blueprint).

  **Demonstrated against a live VirtualBox on 2026-08-13**: the
  unmodified codex script installs FreeDOS 1.4 from the LiveCD,
  partitions, reboots, formats, installs, boots the installed
  system to `C:\>`, and powers the guest off — then the verify and
  ready scripts reboot it and hand it over. The defects that first
  live run turned up are in this release's Fixed section.

- **Fixed-font text-screen recognition** (F51, cut from F3 with
  F50/F52). `text_recognize` turns a PNG framebuffer into the
  seam's `(rows, attribute tokens)` contract using Reliquary's
  CP437-layout 8×16 glyph bank. Fixtures under
  `tests/fixtures/text_recognize/` round-trip with no hypervisor.

- **VirtualBox lifecycle and VDI materialization** (F50, cut from
  F3 with F51/F52). The first non-QEMU adapter body:
  `backend_virtualbox.py` discovers `VBoxManage`, materializes
  VDI images (`new` / `difference` / `copy`), registers the VM
  under `cache/machines/<id>/virtualbox/` at first start, and
  start/stop with UUID identity verification. The VMware and
  Hyper-V stubs remain.

- **`delete-script`, the script removal command.**
  Removes a home script file under ``scripts/`` and
  fails closed while any blueprint refers to the script,
  naming each referencing blueprint. Error ids
  ``script.unknown`` / ``script.has-blueprints`` mirror
  ``blueprint.unknown`` / ``blueprint.has-machines``.

- **The command manifest.** The package ships
  `schemas/command-manifest.toml`, the normative inventory of the
  command surfaces (P6): every capability declared once, the CLI
  word and the session twin derived from the one name, the
  families and the reasoned parity exceptions as data, every
  public name classified. The suite holds both surfaces to it in
  both directions (`tests/test_command_manifest.py`), and the
  prose specs defer to it for what exists — cli.md and api.md
  stay normative for behavior and design.

- **`stability=`, the quiescence gate on observations** (F48, over
  F47's measure). A condition can hold perfectly on a screen that
  is still painting, and that is exactly the screen a wait must not
  act on — `stable=` guards how long a *match* holds, and nothing
  guarded the *frame* the compare ran on. A sample below the gate
  is now not one any condition is judged on; in a branching `wait`
  an unsettled frame evaluates none of the handlers. It is a
  proportion rather than a duration, and it scopes like `timeout`
  — `statement > branching wait > phase > header > built-in 0.99`
  — so it is **written nowhere in an ordinary script**. The
  default follows the geometry: one row of an 80×25 screen is 4%
  of it, so anything looser than 0.96 calls a screen settled while
  a line is being drawn, while furniture (a cursor 1 cell, a clock
  8) costs an order of magnitude less. `stability=0` turns the
  guard off for one observation and costs nothing.

  **This changes when existing waits fire, deliberately** (P8):
  every wait gains a clause its author did not write. Two rules
  bound that. The gate **never causes a failure on its own** —
  where it could not measure at all, the condition is judged on
  what is there, so a short bound still works and "a timeout means
  samples were taken, never that nobody looked" still holds. And
  where it measured a moving screen, the expiry **says so**,
  naming the proportion reached rather than leaving the two ways a
  wait can now expire indistinguishable. It does not retire
  `stable=`: the two answer different questions, and only `stable`
  catches a quiet screen showing text about to be overwritten.

### Changed

- **The suite is pytest-native throughout** (F60, the last of the
  sweeps; D106). The remaining twenty modules convert — the CLI and
  document surface, the core helpers, the home and asset machinery,
  the media path, the guards, and the two that read the repository
  rather than the package. **No `unittest.TestCase` and no `subTest`
  survives anywhere**, so the idiom policy has nothing left to
  exempt, and `python -m unittest tests` loses the hook that made it
  work: with nothing for it to collect it would have reported success
  over an empty run.

  **No assertion changed**, and the suite reports **2,102 tests where
  it reported 2,016** (2,140 before the drive and file family were
  removed, below). Most of the difference is the command
  manifest: its declared capabilities, family
  members and exceptions each report for themselves now, where
  one method reported for all of them — and every example the
  documents teach from is a node named for its document and
  position.

- **The machine and backend suites are pytest-native** (F59, over
  F55; D106). Ten modules — machines, the session veneer, events,
  properties, both backend adapters, the seam, the drive layer,
  screen stability, and the recognizer. The shared construction is fixtures
  now: one `rig` builds the temp home, the adapter double and the
  blueprint writers the machine layer needs, so a test says what it
  is about rather than how its home was built. **No assertion
  changed**, and the suite reports **2,016 tests where it reported
  1,901**.

  **The two backends answer one contract** rather than paired
  near-identical methods (**P25**). What every built adapter owes the
  seam — the name it answers to everywhere, the capability report,
  the image extension, discovery found and absent, the host font it
  reads and caches, and the refusal to command a VM whose recorded
  identity does not match — is written once and run against each
  backend, so a requirement cannot be honored by QEMU's tests and
  quietly missing from VirtualBox's. A backend contributes a
  **driver** — where its executable is found, where its font lives,
  how a mismatched stop is aimed — and a third adapter inherits the
  whole contract by adding one.

- **The script-language suite is pytest-native** (F58, over F55;
  D106). Its seven modules — the runner, the parser, the node layer,
  validation, timing, labeled wiring, and the dry run — are bare
  `assert`s, fixtures where `setUp` was, and `parametrize` where a
  loop or a `subTest` was. **No assertion changed**, and the suite
  now reports **1,901 tests where it reported 1,825**: every one of
  the 76 is a case that was already being checked inside something
  that reported one pass for all of them.

  **The static rules are one case table** rather than a method per
  rule. Each case names the rule it drives and is a collected node
  named for it — `pytest -k V10-goto-undeclared` selects one while it
  is being fixed — and a parametrised check walks the id-to-rule
  map's whole range, so a rule the language gains with no case
  fails as a named missing rule rather than passing as an absence
  nobody counts. That is the same guarantee the conformance corpora
  make over fixtures, made over unit cases.

- **The integration tier is a marker, not a skip** (F57, over F55;
  D106). The two opt-in FreeDOS runs carry
  `@pytest.mark.integration` and are **deselected** unless `pytest
  --integration` asks for the tier, so the default suite reports
  **no skips at all** where it reported two.
  `RELIQUARY_INTEGRATION` retires as the gate;
  `RELIQUARY_INTEGRATION_HOME` stays and is read by the
  `integration_home` fixture rather than at import.

  A skip cannot say whether it was chosen or suffered, which is why
  the suite carried an asserted skip *count* around this tier. The
  marker says it instead, the count stops standing in for it, and a
  skip anywhere is now a defect with nothing to hide behind.
  Selecting the tier on a host without the backend is a failure
  naming the gap rather than a quiet pass — the run was asked for.

- **pytest is the test runner** (F55; D106). The suite runs under
  `pytest`, which joins `jsonschema` in the `dev` dependency group as
  a hard requirement of it, and `python -m unittest tests` stops being
  the entry point. **No test changed**: pytest collects the standing
  `unittest.TestCase` classes unchanged, `unittest.mock` remains the
  mocking library, and the run was the same tests with the same two
  opt-in integration runs held out of it.

  The runner is what the stdlib could not say. A conformance corpus of
  135 fixtures inside `subTest` once ran against the parser and *not*
  the schema while claiming the two cannot drift, because a run of
  that shape looks the same halved as whole; parametrised, each
  fixture is a collected node and the count is the assertion. The
  conversions themselves are separate work.

  The project's `[tool.pytest.ini_options]` turns **plugin autoload
  off** and pins `testpaths`, strict config and marker handling, and a
  pytest floor. The suite ships in the sdist (D105), so it must not
  collect differently in a packager's environment than it does here.

- **The conformance corpora are parametrised** (F56, over F55; D106).
  Every fixture under `tests/fixtures/conformance/` is a collected
  node **named for its file**, in each check that judges it, and each
  bucket's count is **pinned where the fixtures are gathered**. A
  corpus that stops loading is now a collection error rather than a
  green run over nothing, and a fixture being fixed is run on its own
  by name — `pytest tests/test_script_corpus.py -k v7-no-condition`.

  This is the defect the runner was changed for. The blueprint corpus
  ran against the parser and *not* the schema while claiming the two
  cannot drift, because a loop of fixtures inside one `subTest` test
  reports the same single pass whether it checked all of them or half.
  A check that **partitions** a bucket by a marker is the same failure
  in miniature, so `// warns:` and `// schema: rejects` are each
  asserted in both directions by one check over the whole bucket
  rather than by two over its halves.

  Both corpora read through one helper, `tests/corpus.py`, rather than
  a glob apiece — the guarantee belongs to the harness, not to a
  document format, and a third corpus inherits it by calling the same
  two functions. The suite collected **1,827 tests where it had
  collected 1,310**: the checks are the ones it was
  already making, and what changed is how many of them a run can prove
  it made.

- **The source distribution carries the test suite again** (D105).
  An sdist is the artifact a stranger builds *and verifies* from,
  and downstream packagers run the upstream suite at package-build
  time — on platforms and interpreters this project never tests,
  which is the whole of what shipping it buys. Unpack
  `reliquary-<version>.tar.gz` outside the tree, put `src` on
  `PYTHONPATH`, and `pytest` runs **2,048 tests and deselects two** —
  the opt-in FreeDOS integration runs, one per backend, exactly as in
  the repository.

  The suite is grafted **whole**. Setuptools' own sdist rules take
  top-level `tests/*.py` and none of the fixture trees beneath it,
  which would ship a suite that looks runnable and proves nothing,
  so `tools/check_dist.py` now names every fixture tree it must
  carry and fails the release if one stops shipping.

- **The tests that read the repository are separated from the ones
  that test the package**, and only the second kind ships. The new
  `tests/source_tree/` holds the documented-example checks and the
  old-surface sweep: what they read is prose, maintainer records
  and the open-problem catalogue, none of it in a released
  artifact. Shipped, the sweep would have found no `docs/` and no
  `AGENTS.md`, checked a fraction of what it was written to check,
  and reported success — so it is kept where it cannot run rather
  than left to run hollow. Two `skipUnless` guards go with it, and
  the skip count is now the same two wherever the suite runs.

- **`docs/` no longer ships in the source distribution.** The prose
  is the repository's, and what a consumer needs to use the package
  travels in the distribution metadata already. The sdist is 257
  files against the previous release's 280, and carries a suite
  that runs rather than documents nobody builds against.

  Unchanged in both directions: the **wheel** carries no tests —
  59 files, the runtime and its package data — and **`planning/`
  ships in neither artifact**, being maintainer governance rather
  than anything a consumer runs.

- **The machine layer and the CLI entry point are restructured, and
  nothing you use moved.** `machines.py` was two modules and a
  substrate: the drive layer — the drive report and the five in-band
  file verbs, both since removed (below) — became `drives.py`, and
  the ids, directories, locks, `machine.json` and selector
  resolution are `machine_state.py`. `blueprint.py` and `script.py` merge into
  `authoring.py`, the counterpart of `assets.py`. `machine.py`
  becomes `machine_handle.py`, the package spelling its collective
  engine modules in the plural. `cli.py`'s `main()` builds its
  commands through family builders, and the command set it
  recognises is derived from the parser rather than restated beside
  it.

  **Every documented surface is untouched**, and deliberately
  checked rather than assumed: the same 50 root exports, the same
  `Session` methods, the same commands, flags and exit codes, and
  `rlq --help` plus every subcommand help byte-identical. Machine
  state, rule ids and the working-directory layout are unchanged, so
  no home, blueprint or machine needs recreating. An embedder
  reaching *past* the root — importing `reliquary.machine`,
  `reliquary.blueprint` or `reliquary.script` by module path — is
  the one caller affected; those paths are gone, and the names they
  held are where they always were, on the package root and the
  session (P26).

- **`--record` is refused under `--dry-run`** (S1, S2; P11), exit
  `2` with `progress.record-on-a-dry-run`. It was accepted and did
  nothing: a dry run starts no machine and reads no screen, so the
  capture had nothing to write and said so to nobody. It now joins
  `--display`, `--expect` and a non-default `--progress`, which a
  dry run has always refused on that same ground — a flag accepted
  to no effect is exactly the dishonesty P11 exists to forbid. The
  refusal lives in `run_script`, so the CLI flag and the API's
  `record=` get it from one place.

- **CLI list tables use Rich** for consistent terminal-cell alignment and
  wrapping. Long paths, addresses, property values, and other wide data fold
  across lines instead of being truncated. Machine listings lead with machine
  IDs; listings with descriptions place them in a wrapping column on the same
  row. UTF consoles render rounded borders; other encodings fall back to ASCII.

- **Machine-local images now live in `disks/`** rather than `media/`
  below each `cache/machines/<id>/` materialization. The separate
  shared payload cache remains `cache/media/`.

- **`stop-machine` and `destroy-machine` now accept an optional
  positional machine id** (`rlq stop-machine <id>` is a short alias
  for `rlq stop-machine --machine <id>`, and likewise `destroy-machine`
  already had it). `--blueprint` and `--machine` still work as before.

- **`--backend` on `create-machine` now overrides the blueprint's
  `backend` field at materialization**, pinning assignment the same
  way a declared backend does — the named backend must be available
  and capable, failing closed on either count. It is no longer
  restricted to `--dry-run`: with `--dry-run` the question is still
  whether the blueprint would work *there*, so absence is reported
  rather than raised. The old `machine.backend-outside-dry-run`
  guard is deleted.

- **A blueprint's `scripts` map is read at invocation, not recorded
  in machine state** (D101), which is what `docs/spec/cli.md` always
  said — a label resolves against *the blueprint's* map — and the
  premise the blueprint-`parameters` design was written on.
  Previously the map was snapshotted into `machine.json` at create,
  so a machine could not run a label its blueprint gained afterwards
  until an `apply` it had no shape reason to need. A label names
  which instructions to run, not what the machine is, so it now sits
  outside the shape baseline exactly as `parameters` already did.

  **Two observable consequences.** `scripts` is gone from the
  published machine-state schema, and a script-map edit no longer
  marks a machine diverged. Machines created before this change
  carry a digest computed over the removed field, so the first
  `apply` after upgrading reconciles a difference that is not
  really there and re-records the digest — a stale artifact of the
  kind the pre-1.0 compatibility rule covers, not a migration.

- **The menu machinery stops owning a settling measure of its own**
  (F49). `_settled_screen`'s hold-for-two-reads and
  `_menu_baseline`'s learned animation mask were both special cases
  of F47's measure, tuned by hand rather than derived; they are now
  callers of it and the bespoke copies are deleted, leaving one
  implementation in the tree with three consumers. Menu behaviour is
  unchanged — the cursor-menu suite is the acceptance criterion for
  the cut and passes intact — and two things improve by
  construction: a mask needs no quiet moment to be learned in, and
  decoration that *begins* mid-menu is absorbed within a few samples
  where a once-learned mask would never take it. What stays in the
  menu machinery is what was never about settling: whether a
  keypress changed anything at all, and which row the highlight
  moved to.

- **`exec` waits for the screen to settle before reading it**
  (F45, over F47's new stability measure). A DOS prompt can
  arrive mid-scroll, or the bottom row can transiently resemble
  one while output is still drawing; the completion test used to
  accept the first frame that looked right and return output
  sliced at a boundary that never existed — short, plausible and
  wrong. A prompt is now a candidate until the screen under it
  has stopped changing. **What `exec` returns is unchanged where
  it was already right**, and this is a timing change only: the
  spec's "completion means this command finished, not that a
  prompt is visible" is strengthened rather than amended. A
  command costs roughly an extra 200ms of confirmation, and the
  waiting ramp is untouched — dense reads are spent confirming a
  prompt, never waiting for one. A wait that expires having seen
  a prompt now says so, naming the stability it never reached.

- **Listings show their descriptions** (D97, resolving the
  deferral D88 parked as T8). Wherever a listing's noun carries a
  `description` — `list-codex`, both `list-scripts` forms,
  `list-blueprints` — the human listing prints it beneath its
  entry, indented and wrapped, never as a column; an entry
  without one contributes no line. `list-blueprints` rows now
  carry `description` and `platform` in `--json`, so the record
  holds what the human view shows. U11's "read a description" is
  met at the keyboard again, not only through `--json`.

- **The session is the only door** (P26). All embedding-API
  interaction now passes through `reliquary.Session`, opened on a
  home path or a `Context` — which now also carries the selected
  properties file — and refusing construction without a home.
  **This is a breaking change for every embedder, with no aliases
  or shims** (no backward compatibility before 1.0): the
  module-level verbs (`create_machine`, `run_script`,
  `fetch_media`, the property verbs, the listings, …) left the
  package root and are methods of the session; the directory
  globals with their `set_*_dir()` setters and
  `adopt_environment()` are deleted; per-call `context=` and
  `properties_file=` left every public signature for the record
  the session is opened on; and the library reads no environment —
  the CLI honours `RELIQUARY_*_DIR` and `RELIQUARY_PROPERTIES` in
  its own construction step, so programs select everything
  explicitly. First-use `dir.unassigned` retired for the
  construction-time refusal, the id intact. **The CLI is
  unchanged**: same flags, same environment honoring, same default
  home, same exit codes. The types, the errors, `Context`,
  `default_home_dir()`, the free parsers, and the guest-console
  family (`Machine` and its module functions, addressed by a
  machine's own directory) remain importable as before.

### Removed

- **A machine's file content leaves Reliquary, and the volume mapping
  goes with it** (D108). Seven commands and their twins are deleted
  rather than deprecated — `describe-drives`, `refresh-drives`,
  `put-file`, `get-file`, `put-files`, `get-files` and `list-files`
  — together with drive-letter mapping, guest-address parsing, the
  recorded drive report (`volumes` and `geometry` in `machine.json`),
  at-rest disk access, and the `at_rest` / `at_rest_write` backend
  capability flags. Reliquary declares a machine's drives,
  materializes them and moves their media; **what is inside a volume
  is the caller's**, reached with the caller's own tools.

  **Three routes across the boundary remain**, none of which asks
  Reliquary to look inside a filesystem: a directory-source media
  attaching a host directory as a drive, `insert-media --file`
  swapping a whole image live (U20, untouched — its launch-size
  guard is a file size and never read a volume), and the machine
  directory `get-machine-dir` returns, which is now the route rather
  than a convenience.

  **The `remanence` dependency is gone** with the layer that wrapped
  it, and is the tool named for the work: a consumer that needs a
  file out of a drive image uses it directly. The runtime closure is
  now tier 1 throughout except `qemu.qmp`.

  Vision moved with the code: **U14** no longer claims a file as the
  product, **P16** gains a file-content carve-out naming this as a
  boundary rather than a gap, and **P17** and **P27** are struck.
  Pledged **F41** is withdrawn.


- **`Session.set_machine_var` is gone** — removed as a defect,
  not deprecated. Machine variables are the guest's report
  channel: the script `set` verb writes and the host reads
  (`get-machine-var` / `wait-machine-var`), which the CLI spec
  has stated all along — "writing is the script verb's, and the
  host side only reads." The session method was host-side
  writing into that channel, wider than the verb it mirrored: it
  could write outside any run and forge what a boot reported,
  and no script can observe a variable, so it could trigger
  nothing. The engine keeps its internal writer for the runner;
  no public surface writes a machine variable.

### Fixed

- **`--record` now captures what it promised to.** Six defects, all
  in the recorder and all found the only way they could be — by
  taking a real capture of a real FreeDOS install (F43). The
  **`screenshot` verb bypassed the recorder**, building its own
  machine handle, so the one carrier call both codex scripts make was
  missing from every capture. **The machine going away was never
  recorded**: identity is verified while a session is being opened, so
  a guest that powered itself off refuses the session before the
  recording wrapper exists, and a capture therefore ended at the
  shutdown every DOS install finishes with. And **the record pace did
  nothing at all** — the poll intervals took the larger of the pace
  and the production interval, leaving the two-second idle poll the
  pace exists to close, so a five-and-a-half-minute install captured
  536 screens where it now captures 2847. (The other three — the
  wrapper installed on a frozen dataclass, an inverted keyframe test,
  and a collapsed frame counting one sample — were fixed as they were
  found.)

  A recorded run is a **different** run and always was: each QEMU
  sample is a 4000-byte memory dump, and one now taken ten times a
  second makes an install run two to three times longer. Denser
  polling is strictly more information, which is the trade the design
  named; the transcript states the pace it was taken at.

- **A cell that matched nothing no longer passes for one that was
  read.** The recognizer takes the nearest glyph only when it is
  near enough to believe and substitutes a space otherwise, since a
  wrong character is worse for a `wait` than a blank — but the
  substitution was silent, so a screen drawn in a font this host
  does not have arrived looking merely *sparse*. A wait on a word in
  it expired with nothing to show, and the failure report's
  nearest-miss row was measured against text that had never been
  read. That silence is what let the font defect below hide for as
  long as it did.

  `recognize` now returns a `Screen` carrying `unreadable`, the
  `(row, col)` of every substituted cell. It is still the
  `(text_rows, attribute_rows)` pair to everything that unpacks or
  indexes it, so the seam is unchanged and the fact rides to callers
  far from the pixels: `rlq screen` narrates when part of a screen
  could not be read, and a script's failure report says how many
  cells were guesses — turning "it never appeared" into "it may have
  been there and unreadable", which are different problems with
  different fixes. Both are silent at zero, and silent for a backend
  that scrapes resolved characters out of text memory: it recognizes
  nothing, so it can misrecognize nothing. Reading a guest screen is
  a measurement, and one that reports no confidence cannot be told
  from a good one — but it stays a signal and never a verdict, since
  a BIOS splash is unreadable by nature and already a sample the
  waits look past.

- **A screen is read through every font it could have been drawn
  with.** The recognizer read through one bank chosen in advance,
  and there is no right choice: more than one font is painted during
  a run, and a framebuffer does not say which was in the VGA. A VGA
  BIOS installs its bank with an override table applied and draws
  its own messages that way; a DOS guest loads its own font and
  draws with that. The two a stock VirtualBox offers differ in 19
  glyphs — `W`, `m` and `T` among them — so whichever was picked,
  half of every run was misread: `Welcome` as `Uelcooe` through one,
  `Trying next boot device` as `Irying` through the other. Not an
  emulator difference, as it first appeared — both install the same
  font, VirtualBox's stored bank plus its own patch equalling
  QEMU's byte for byte.

  `bank=` now takes one font or many (`as_banks`) and scores a cell
  against all of them. An override table changes a glyph's shape,
  never its meaning, so the nearest match yields the same character
  whichever font drew it — no state, and no guess about what is
  loaded. Shapes the fonts share are unioned rather than
  concatenated, so the cost tracks how much they actually differ:
  275 candidates against 256, about 5% on a read.
  `banks_from_binary` collects every bank a backend's binaries hold
  **plus every variant an override table would install**,
  recognizing a table by shape alone — ascending codes, no blank
  glyph, closed by a zero code byte, with tables for other glyph
  heights stepped over — so a build carrying a different set is read
  on its own terms.

  **Extracted on demand and cached, never vendored**, as
  `cache/support/<backend>/cp437-8x16-banks.bin` holding however many
  fonts an installation offers. It is regenerable like everything
  under that root, so a truncated file is re-extracted rather than
  raised on, and a cache hit never goes near the installation. The
  cache root reaches the adapter as `Machine(cache=)` →
  `adapter.session(vm, cache=)`, which is new on the adapter seam
  and optional: `None` re-extracts, a speed cost and never a
  correctness one. Not vendoring is the licensing policy as much as
  the engineering — the glyphs belong to whatever emulator the host
  installed. A stock QEMU yields one font, its bank shipping with
  the overrides already merged.

- **The shipped glyph bank is the project's own font again.**
  `fonts/cp437_8x16.bin` had become bytes carved out of a host's
  QEMU vgabios while `REUSE.toml` recorded it as Paul Galbraith's,
  `GPL-3.0-only` — ownership claimed over bytes nobody here wrote,
  and material that fails D82's incoming test (*could this ship
  inside a proprietary product?*). It is produced by
  `tools/gen_cp437_font.py` again, which draws its own shapes; the
  extractor that overwrote it is deleted. The authored font had the
  defect that presumably invited the overwrite — 62 codes were never
  drawn, came out blank, collided with the space and could never be
  recognized — so codes nobody drew now get a computed Reed–Muller
  codeword, 64 of 128 pixels from any other: **256 of 256 distinct**,
  against 254 for the dump it replaces. It is `recognize`'s default
  and what `render` draws fixtures with, never what reads a guest,
  and no longer pretends to be a VGA face — `CLASSIC_A` is
  deliberately absent, and a test wanting a findable bank says so
  (`tests/vga_bank.py`).

- **The hypervisor is asked whether a VM is running, not told by a
  failure.** `showvminfo --machinereadable` reports `VMState`, which
  the session fetched for its identity check and discarded — so a
  powered-off VM, still registered and answering as readily as a live
  one, opened a session whose every carrier then failed as
  `machine.backend-failed`. `wait machine=stopped` could therefore
  never be satisfied on VirtualBox: the runner reads
  `machine.vm-unreachable` as the stopped observation and nothing
  raised it, so a script's ordinary ending — power the guest off,
  wait for the machine — aborted the run instead of completing it. A
  session now refuses to open for a VM reported as no longer
  executing, and each carrier re-asks the state when it fails, which
  closes the window where a guest powers off mid-session. The test
  names the **stopped** states (`poweroff`, `aborted`,
  `aborted-saved`, `saved`, `teleported`) rather than the running
  one, so a transitional `starting` is never mistaken for a
  power-off and a booting machine never marked stopped.

  The same question stranded machines outside a run: `stop-machine`
  failed on a guest that had halted itself, `destroy-machine` then
  refused because the phase still said `running`, and with no
  `--force` the only way out was deleting the machine directory by
  hand. An unreachable VM is now an accomplished stop — the adapter
  went looking and there is none, which is the state stop was asked
  to produce — reconciled at the seam so it holds for every backend,
  QEMU's dead QMP port included. An identity mismatch or a port
  answering wrongly is a different condition and still fails closed.

- **A menu with a countdown is pressed before it is studied.**
  `cursor_menu_select` spent `_BASELINE_READS` learning which cells
  repaint on their own before sending its first key — at ~2s a read
  on a screenshot backend, longer than a boot menu's timer, so it
  timed out the very menu it was preparing to steer and surfaced as
  "menu item is not on screen" with a fully booted system in the
  failure screenshot. The edge is sharper than slowness: those reads
  exist because a ticking cell cannot be recognized as furniture in
  fewer, so they are spent learning the countdown that is running
  out. `select` now presses immediately when the wanted item is
  already on screen, taking the full baseline only when it is not.

- **The FreeDOS codex blueprint boots the installer medium first.**
  `boot` becomes `["cdrom0", "hdd0"]`, and the install script ejects
  the CD at the completion dialog rather than at shutdown. The old
  order relied on firmware falling through a disk it cannot boot,
  which is not portable: both backends skip a blank disk and an
  empty optical slot, but only SeaBIOS moves past a disk partitioned
  without an active partition — the state every installer leaves
  before its reboot. VirtualBox stops there, so the install appeared
  to work and hung on its second boot. **A blueprint already seeded
  into a home keeps the old order**, since `seed-blueprint` never
  overwrites: delete `blueprints/freedos.rlqb` and re-seed to pick
  this up. [The blueprint reference](docs/blueprint-reference.md)
  carries the measured behaviour under `boot`, and the four other
  documents that taught the order it replaced now follow it: the
  script spec's FreeDOS example and its `set-boot` guidance, the
  blueprint model's `boot` rule, the CLI spec's installation-machine
  example, and the blueprint cookbook's install recipe.

- **The quiescence guard sizes itself to the cadence it measures.**
  Decoration is recognized by recurrence — three changes to a cell
  inside a one-second window — which was a sample count wearing a
  clock's clothes: a caller reading once per 0.83s fits two samples
  in that window and can never reach three, so the mask stayed
  empty, a blinking bar scored as content, and the screen never read
  settled however long anyone waited (0.98 on a synthetic blink
  against a 0.99 gate, 0.944 on a live guest).

  The **minimum viable cadence** is now stated rather than assumed
  (`viable_cadence`, `viable_window`): one read every ~0.17s, with a
  100% safety margin. A VGA text scrape costs 16ms or less and a
  screenshot interpreted through a glyph bank ~0.83s, so the window
  **widens** to what the observed cadence can see — that cadence
  being the *fastest* gap seen rather than the average, since the
  runtime's 2s idle backoff would otherwise widen the window and
  mask the very redraw the next dense pass exists to catch — after
  rounding up to the grid its noise justifies (1s where screens are
  interpreted, 0.1s where they are scraped). Past
  `MAX_ANIMATION_WINDOW` the widening stops, and a cadence that
  cannot be accommodated reports `Reading.blind` and the gate
  **stands down**: a guard with no verdict must not refuse, and
  blocking would be deadlock rather than caution. Reported once per
  run as `guard.cadence` — a guard that quietly went inactive would
  otherwise be indistinguishable from one that passed. Normative in
  [the script spec](docs/spec/script-spec.md) under `stability`.

- **The menu highlight is followed on a recognized framebuffer.**
  `select` located the selection bar as the rarest attribute on
  screen, which assumes a row wears one attribute — true of VGA
  bytes scraped from text memory, false of tokens recovered from
  pixels, where a blank cell shows one colour and so cannot carry a
  lettered cell's token, and a bar across a dialog reads as two
  tokens whose blank half *is* the backdrop's. Rarity picked the
  wrong row and its own guard then rejected the answer, so every
  `select` on VirtualBox failed with "no menu highlight responded to
  cursor keys". The bar is now found as what a bar is: the attribute
  confined to one row that moved to another — also immune to the
  FreeDOS language chooser rewriting every row per keypress. A
  two-item menu is settled by the cursor key's direction, and
  anything still ambiguous falls back to the frequency reading,
  which continues to serve text-memory screens.

- **A guest's video mode no longer ends the run.** The fixed-font
  recognizer refused any framebuffer that was not an even 80×25 grid
  by raising a `StaticError` — exit `2`, the class reserved for input
  illegal on its face — so on a screenshot-based backend the first
  sample of the first `wait` aborted the whole script, and every
  VirtualBox boot passes through a 640×480 graphics-mode BIOS splash.
  The refusal is now `UnreadableScreen` (a `RunFailure`, exported),
  and a run does not let it escape: the sample is recorded as
  unreadable and the wait keeps polling until the guest reaches a
  text mode, expiring on its own clock if it never does. A failure
  report names the shape that was captured, which the nearest-miss
  row cannot — with no rows at any sample, nothing was ever near the
  target. QEMU never met this, scraping VGA text memory that is
  80×25 whatever mode the guest is in.

- **`--record` and `run_script(record=)` are specified.** D98 ruled
  the `.rlqt` transcript format deliberately outside the application
  surfaces and the *invocation* squarely inside them (S1, S2) — and
  then the invocation was described in neither
  [the CLI spec](docs/spec/cli.md) nor
  [the API spec](docs/spec/api.md). Both now carry it, including the
  rule that a bound secret reaching the guest stops the recording.
  The behaviour is unchanged; it was simply undocumented.

- **`--detach` no longer appears in the `run-script` synopsis.** The
  flag has never existed: detach and the follow surface are
  asynchronous-runs backlog (D35/D36), and a normative synopsis
  offering an invocation `argparse` rejects reads as a promise. Where
  the naming for that capability is settled it stays recorded, in the
  passages scoped to the backlog.

## 0.1.0a1 - 2026-07-31

### Removed

- **Released artifacts carry no tests** (D96). The wheel never did; the
  sdist did, and two-thirds of it was the suite — 187 of 280 files. It
  shipped so a downstream packager could unpack the archive and run the
  suite from it, which is a real thing to want and a poor trade for
  what it cost. The completeness that check bought is now proved
  structurally: `uv build` builds the wheel *from* the sdist, so an
  archive missing anything the build needs fails at build time.
  `planning/design/` goes too — it was grafted only so the suite could
  read the script-example catalogue out of an unpacked sdist, which
  means maintainer governance was being shipped to strangers to serve
  a test run nobody performed. `docs/` still ships. The sdist is 74
  files where it was 280. **The published 0.1.0.dev6 sdist still
  carries the tests** and cannot be changed; this takes effect from the
  next release.

### Changed

- **The supported Python floor is now 3.12** (D95), raised from `3.9`.
  This is a **breaking change for 3.9, 3.10 and 3.11 users**, and the
  honest description is that those versions never worked: the floor was
  published and had never been run. The first run failed on 3.9 and
  3.10, where `keyring` reaches `platform.win32_ver()` — which shells
  out on those versions — and on 3.11, where a `MappingProxyType`
  dataclass default is rejected as unhashable, for 39 errors. 3.12,
  3.13 and 3.14 pass. Fixing rather than dropping was weighed and
  declined; both faults are cheap to fix if demand for a lower floor
  appears. A floor run joins the required checks, so the claim is now
  tested rather than asserted.

- **uv provisions the development environment and publishes releases**
  (D94). `uv sync` replaces the `venv` + `pip install` setup and
  `uv.lock` is committed, so the environment the suite passes in is
  reproducible — which matters because with no CI the local suite *is*
  the gate. `uv build` and `uv publish` replace `python -m build` and
  `twine`, both of which leave the development dependencies, reducing
  them to `jsonschema` alone. `twine check` goes with them: its
  rendering job is an RST problem and this readme is markdown, the
  index validates and rejects bad metadata itself, and
  `tools/check_dist.py` remains the real artifact gate. Maintainer-
  facing apart from the floor above; no shipped surface changes.

### Fixed

- **A relative `local` media path now anchors to the referencing
  file**, as the blueprint model has always specified — the
  implementation resolved it against the process working directory
  instead, so the same blueprint found its file or not depending on
  where the caller happened to stand. `load_document` is the anchor
  point: it has the file, so every relative `local` rung is made
  absolute against that file's directory at load, before any
  cross-document work. A bare value through `parse_document` keeps its
  paths as authored — there is no file to anchor to. One consequence
  is deliberate: two same-named specs carrying one relative spelling
  in two different directories now **collide** as differing specs
  instead of deduping, because anchored they name different bytes —
  the dedup that lets a self-contained blueprint be pasted around
  still holds within a directory and for URL locations. Found wiring
  remanence-lib's FreeDOS rig to a local ISO, where the blueprint's
  documented relative path only worked because the caller chdir'd to
  the blueprints directory first.

## 0.1.0.dev6 - 2026-07-30

### Added

- **Adapters honor `backend-settings`** (D92, delivering F28). The
  field parsed, validated its backend names, and persisted into the
  machine state — and no adapter read a word of it. The documents
  sanctioned it as *the* escape hatch while the launch rendered
  memory, drives and boot order and nothing else, so a blueprint's
  `qemu` section was carried faithfully into the state and silently
  dropped at start. It applies now: QEMU's `machine` key becomes
  `-machine`, its `args` are appended to the launch verbatim, and the
  section renders **last**, so in the command line Reliquary logs your
  own arguments are the tail.

  **The keys are the adapter's vocabulary, and a key it does not
  define is refused** when the machine is materialized — QEMU's are
  `machine` and `args`, and nothing else. **Settings may not restate
  what Reliquary owns**: `-m`, `-smp`, `-boot`, the drive arguments,
  `-machine`/`-M`, and the identity and control-channel arguments are
  refused naming the field that owns each, because two sources for one
  fact is the one thing a hatch must not become. Deliberately still
  yours: `-device`, the documented route to a QEMU device —
  backend-specific hardware has no first-class blueprint spelling
  (P25) — and `-cpu`, which selects a
  CPU model where `cpus` owns only the count. Only the *assigned*
  backend's section is judged; another backend's is preserved as
  written and never examined.

- **`backend-settings` narrows backend assignment** (D92). A
  blueprint that declares no `backend` but carries settings for
  exactly one has already said which backend it is written for, so
  assignment goes there rather than walking past it — and fails closed
  if that backend is unavailable or incapable, saying that the section
  narrowed it rather than claiming a pin the blueprint never wrote.
  Two or more sections narrow nothing: each stays inert until its
  backend wins the ordinary walk. A declared `backend` outranks either
  way.

- **A readiness example in the codex** (T9): `freedos-ready.rlqs`,
  named by the `freedos` blueprint as its `ready` label, so
  `rlq seed-blueprint freedos` brings it with the rest. It boots the
  installed disk, waits for a DOS prompt, sets the machine variable
  `ready`, and **leaves the machine running** — which is the point,
  and the one thing the other two examples do not show: both of those
  end with the guest powered off because each has finished with it,
  while a readiness script hands a live guest to whatever drives it
  next. `rlq run-script ready --blueprint freedos --expect ready=yes`
  is the whole handoff in one command.

  As always, the copy is yours: what "ready" means belongs to the
  workflow being built, and this example's answer — the installed
  system reached a prompt — is the simplest one there is. A workflow
  needing a TSR resident or a driver bound waits for its own evidence
  and sets the variable after.

- **`run-script --expect key=value` / `run_script(expect=)`** (D90,
  delivering F30). Contracts a run on the machine variables it
  leaves: each key is read once the run completes, and one that is
  unset or holds something else raises `RunFailure` naming key,
  wanted and got. Without it, reading a run's scalar outcome took two
  calls with the join left to the caller — and because an unset
  variable and a machine that never ran read alike, a script that
  failed to reach its `set` was silent. It is a **postcondition, not
  a wait**: the run blocks, so its variables are final when it
  returns. Refused under `--dry-run`, which runs nothing.

- **`wait-machine-var` / `wait_machine_var()`** (D90). The polling
  half, for the case a postcondition cannot serve: **another actor
  sets the variable** — a run driven from another thread, or one
  being followed rather than owned. Omitting the value waits for any
  value, which is what the readiness idiom wants. `--timeout`
  (default 120s) and `--interval` (default 1s) bound the wait.

  An expired wait exits `4`, and the twin raises **`WaitExpired`,
  deliberately both a `RunFailure` and Python's `TimeoutError`**: the
  work asked for did not happen, while nothing about the machine went
  wrong and the value may still arrive, so a caller holding the loop
  catches the ordinary timeout and asks again. That reconciles the
  async design's "expiry raises outside the taxonomy" rule with the
  standing invariant that no deliberate raise is a bare builtin —
  two positions the record had held separately since they could not
  yet collide.

- **`exec --check` / `exec(check=True)`** (D89, delivering F26). The
  one thing a command's output cannot tell you: whether it worked. A
  setup command — loading a driver or a TSR — produces nothing worth
  reading and its success is the whole point, so without this success
  and failure come back looking identical and a refused loader
  surfaces later as every subsequent command failing strangely. With
  it, a command that signalled failure raises `RunFailure` naming the
  command (exit `4`), and the row return is unchanged either way.

  On DOS the verdict comes from an `IF ERRORLEVEL 1` probe with a
  sentinel Reliquary composes and reads back — its own text, not the
  guest's, so nothing here reads meaning into guest output. It is
  opt-in because it costs one extra command at the prompt, and **its
  scope is commands that ran and signalled failure**: `COMMAND.COM`
  leaves ERRORLEVEL untouched when it cannot find a program, so a
  mistyped command escapes the probe and reads as success. That limit
  is stated in the spec rather than papered over with error-text
  matching, which would mean curating guest message spellings a
  localized DOS makes unbounded. A probe whose own answer cannot be
  read reports `command.outcome-unreadable` rather than passing.

- **`describe-drives` and `refresh-drives`, with twins
  `describe_drives()` / `refresh_drives()`** (D83). One
  machine-level report of what a machine's drives are and what they
  actually hold — the observation the letter map and the file verbs
  already ran on, now given a window. Per drive, the declared and
  chosen facts (key, medium, slot, media, materialization); per hard
  disk, the at-rest read — the backing standing behind it (`qcow2`,
  `raw`, or a directory served as one FAT volume), the partition
  table as it declares itself, and per volume the filesystem, its
  label where one exists, and the BPB's own geometry where it states
  one, `null` rather than guessed where it does not; and the
  platform's letter map over those facts, letter to (drive key,
  volume index), with every unplaced drive named as undetermined
  carrying the blocking disk's own reason and id — the same words
  the file verbs use, because they are the same facts.

  **The report answers from the record and is never phase-refused.**
  Every `start` reads the disks as its first step, before the
  backend is engaged, so a running machine's report is this boot's
  own starting state — `"recorded": true`, each disk stamped
  `read-at`. `describe-drives` itself reads a disk only when the
  machine is down and the disk has no record yet (the window
  between create and first start); a layout changed behind the
  record is picked up at the next start, or now by
  `refresh-drives`, the explicit stopped-only re-read returning the
  same report fresh. Addressing still never trusts a pre-boot
  count: the file verbs' volume counts stay cleared at every start,
  and the re-read that restores them refreshes this record with
  them. `--json` prints exactly what each twin returns.

### Changed

- **The codex verbs are CLI-only** (D87). `seed_blueprint()` and
  `seed_script()` leave the embedding API, `list-codex` arrives with
  no twin, and `reliquary/__init__.py` exports none of the three. A
  library that changes in a point release is not something a program
  may bind against (P18), so reaching it is a human act — and **P6
  gains its first named exception**, stated as a test rather than a
  list: a capability whose subject is the codex is CLI-only, with the
  asymmetry deciding conflicts (D24 — adding a twin later breaks
  nothing; removing one after callers bind cannot be undone).
- **A dry run refuses a library-only name** rather than reading it
  where it lies, narrowing that clause of D80. With no fallback there
  is nothing to read, so the dry and live halves now resolve
  identically — which is what the rule always said.

- **The at-rest recognition claim narrowed to FAT12, FAT16 and
  FAT16B over standard MBR primary/extended partitioning** (D83).
  FAT32 partition types (`0x0B`/`0x0C`) and FAT32-scale volumes are
  now refused by name like every other unrecognized format, where
  0.1.0.dev5 read them. The claim follows what the DOS workflow's
  guests make; a FAT32 disk still boots and runs — only at-rest
  access (the file verbs, the letter map, the drive report) refuses
  it, naming FAT32 as the reason.

- **The machine-state schema catches up with the state the code
  writes**: the per-drive `volumes` count (read on the host, cleared
  at each start), the floppy `launch-size`, and the new `geometry`
  record are now part of `machine-state.schema.json`, and none of
  the three enters the blueprint digest.

- **Script static-validation rule ids are now `V1`–`V14`, renamed
  from `S1`–`S14`** (D84). The letter changes and the number never
  does, so `S6` is now `V6`; the `S15` retired earlier stays retired
  and no `V15` is issued. Diagnostics, the normative rule list in
  `docs/spec/script-spec.md`, and the conformance corpus (fixture
  `# rule:` headers and filenames alike) all move together — a clean
  pre-1.0 break with no alias and no dual spelling. Anything pinned
  to a rule id (a fixture header, a test, a note citing a rule)
  needs the letter changed.

- **Reliquary's world-facing boundaries are now called the
  application surfaces, and they are itemized `S1`–`S8`** (D85).
  `S1` the CLI, `S2` the embedding API, `S3` the scripting language,
  `S4` the machine blueprint, `S5` the script properties, `S6` the
  codex, `S7` the run's returned output, `S8` the working-directory
  layout — one flat sequence, permanent handles, enumerated in root
  `ARCHITECTURE.md` "The application surfaces". The governing rule
  is the **surface-change rule** and has moved from
  `planning/INTERFACES.md` to `planning/SURFACES.md`. Nothing about
  the surfaces themselves, their specifications, or how a change to
  one is weighed has changed; a change may now cite the surfaces it
  touches by number. The word "interface" keeps its ordinary senses
  throughout (the hypervisor's management interface, a module's
  public interface).

- **Tasks in `planning/TASKS.md` are itemized, carrying `T`-numbers**
  (D86) — issued at entry, evaporating when the task is struck, and
  never reissued. The sequence starts at `T8`, above the historical
  per-list numbering, and that file states the next number to issue.
  Maintainer-facing only; no shipped surface is affected.

- **A first-class blueprint field must generalize across backends**
  (D93), armed as **P25** in root `ARCHITECTURE.md`. The machine
  blueprint's own vocabulary now carries only capability more than
  one backend can honor; what a single backend alone provides
  reaches a machine through that backend's `backend` pin and its
  `backend-settings` section. Demand for a capability is necessary
  and never sufficient — the bar is what stops the portable
  blueprint becoming a union of backend vocabularies in portable
  syntax, one sympathetic case at a time.

  **This retires a `devices` axis that was added and removed inside
  this same unreleased cycle** and therefore never shipped: it is
  absent above rather than reversed, and no released version ever
  carried it. Anyone who tracked `main` between the two commits
  should move `"devices": ["virtio-rng"]` to `"backend": "qemu"`
  with `"backend-settings": {"qemu": {"args": ["-device",
  "virtio-rng-pci"]}}`, which is the spelling that survives.
  `-device` stays deliberately unreserved in the hatch for exactly
  this reason.

### Removed

- **Autoseeding is gone, and nothing resolves out of the built-in
  codex** (D88). `--autoseed` / `--no-autoseed`, `set_autoseed()`,
  `autoseed()` and `Context(autoseed=)` are deleted rather than
  defaulted: the `blueprints` and `scripts` directories are the sole
  sources on both surfaces, and a name they do not hold is refused —
  naming `rlq seed-blueprint <name>` where the library has it, so a
  deleted fallback leaves an instruction rather than a silence. **The
  simplest journey is now two commands**: seed the blueprint, then
  run it (U1). That restores **P4 to an absolute** — the codex does
  not feed automation, no default and no switch — which D59 had
  traded for a knob when it made hermeticity an axis.
- **The search family is deleted** (D88). `search-blueprints` and its
  `search_blueprints()` twin are gone, the unbuilt `search-scripts` /
  `search-media` are retired unbuilt, and no term parameter replaces
  them: filtering a listing is the shell's job and `--json`'s.
  **`list-codex` is the new library-facing verb** — the noun names
  the set, and no verb spans two, so `list-blueprints` /
  `list-scripts` / `list-media` show yours alone and `list-codex`
  shows the library's. Which command you ran is the provenance, so
  the `PROVENANCE` column and its `yes` / `seeded` / `user`
  vocabulary are deleted with it.
- **`--builtin` is gone** from `list-blueprints` and `list-media`,
  and `builtin=` from `list_media()` (D88): a listing of what you
  have should not carry a flag that turns it into a listing of what
  you do not. Nothing replaces the codex media listing — media are
  components inside a `.rlqb` and there is no `seed-media`, so it
  enumerated parts that cannot be ordered.
- **No `list-*` prints a description**, on any noun. The field rides
  the `--json` record instead: unbounded free text dominates a
  fixed-width table, and how a person should see one is deliberately
  unsettled (T8) rather than guessed at.

## 0.1.0.dev5 - 2026-07-29

### Added

- **`create-machine --dry-run`, and the `create_machine(dry_run=True)`
  twin.** Scripts could be checked without running them; machines
  could not, so there was no way to ask "is this blueprint sound, and
  what would it build?" without building it. A dry run performs every
  step that costs nothing and commits nothing, stops at the first step
  that would, and reports what it would have done — the machine id it
  would allocate, the backend it would land on, each drive's resolved
  plan, and where every media would come from.

  **It leaves no state behind**: no machine directory, no
  `machine.json`, no image, no fetched payload, no lock file, and no
  seeded blueprint — a codex-only blueprint is read where it lies
  rather than copied out. And **it never prompts**: a media location
  no concrete source answers is reported as `unbound` with the key
  named, and the report says a real create would ask for it.

  Media resolve and are never fetched, each reported as `cached`,
  `would-download`, `would-extract`, `local-present` or `unbound`.
  Nothing is hashed — `cached` says the file is in the cache, not that
  it is the right one — and a byte total appears only where something
  on the host knows one, so a `would-download` carries its URL and its
  pinned hash and no size.

  It refuses what a create would refuse, where a create would refuse
  it, so a nonzero exit is the verdict. Missing *local* payloads are
  the one class collected rather than raised on sight: every one is
  named at once, because stopping at the first would cost a
  fix-and-rerun for each.

  The twin returns a `DryRun` — `operation`, `report`, `plan` — and
  never a machine id, so a `dry_run=True` result can never pass for
  the real one. `--json` prints that document, under the ordinary rule
  that a command's `--json` is exactly what its twin returns.

- **`create-machine --dry-run --backend NAME`** asks whether a
  blueprint would work on a *named* backend rather than on this host:
  its capability decides, it need not be installed here, and its
  absence is reported as a line in the plan rather than raised. That
  is the capability-not-identity contract checked statically, with
  nothing installed and nothing booted. The flag is legal only with
  `--dry-run` — a machine's backend comes from its blueprint, and a
  flag that changed it at materialization would put that
  configuration outside the blueprint. It is not simulation:
  `--dry-run --backend simulator` validates and stops, while running
  simulated means dropping `--dry-run` and keeping the backend.

- `backends.evaluate(name, requirements)` reports a backend's
  availability and its unmet requirements as two answers rather than
  one verdict, which is what lets the question above be asked at all.
  `assign()` is now expressed over it.

- **`run-script --dry-run` reports how much of a script it could not
  statically reach.** A statement inside a handler runs only if the
  guest puts it there, so the plan says how many statements it cannot
  promise — `10 of 37 statically reachable` on the shipped FreeDOS
  install — rather than implying a completeness it cannot have.

- **A drive image is locked for the length of an at-rest access**,
  so two callers cannot work one disk at once; a second one meeting
  the lock is refused (`image.locked`) rather than made to wait.
  The lock is Reliquary's own and deliberately sits one byte past
  the end of any image: a claim over the image's own bytes is one
  the image server trips on. QEMU's image locking is not what backs
  this — that lives in QEMU's POSIX file driver, and the Windows
  one, on the delivered host, implements none.

- **A partition is read for what it declares itself to be.** The
  partition table is walked in the order the guest sees it —
  primaries, then the logical drives behind a DOS extended
  container (`0x05` and `0x0F`) — and the FAT partition types are
  pinned value by value. A partition whose type this build does not
  read is now **refused by name** rather than skipped:
  `partition 1 holds Linux`, `holds NTFS or exFAT`, `holds a GPT
  protective partition — this disk is GPT, not MBR`. Skipping one
  would renumber every volume after it and answer confidently for a
  drive the caller never addressed. `0x85` is Linux's extended
  container, not DOS's, and is refused with the rest.

- **Drive geometry is readable at rest** — the partition table with
  each entry's declared type, the volume count, and the BPB's own
  heads, sectors-per-track and derived cylinders where a volume
  states them, unanswered rather than guessed where none does. This
  is P10's *read on the host* source, and it is the answer the
  drive-letter map needs; wiring it into that map is not done here.

- **Only qcow2 and raw are claimed for at-rest access.** Any other
  format QEMU could read is refused (`image.format-not-at-rest`)
  rather than served untested.

### Changed

- **BREAKING: Reliquary is now GPL-3.0-only.** The project was
  BSD-3-Clause through `0.1.0.dev4`; every release from here is
  copyleft. Anyone may still run, study, modify, and redistribute it,
  but a distributed work incorporating Reliquary must now also be
  GPL-3.0-only, and it can no longer be taken into a proprietary
  product. Already-published releases are unaffected: what went out
  under BSD stays under BSD, and this changes nothing retroactively.

  `LICENSE` now carries the GPL v3 text, `LICENSES/BSD-3-Clause.txt` is
  replaced by `LICENSES/GPL-3.0-only.txt`, and the SPDX header on every
  file in the repository (127 of them) reads `GPL-3.0-only`, as do
  `REUSE.toml` and the `license` field in `pyproject.toml`.

- **The relicensing reservation is now stated, and it is the reason
  contributions require a copyright assignment.** Paul Galbraith holds
  copyright in the whole work and reserves the right to relicense it on
  any terms. Nothing is planned or in preparation; the reservation
  exists so the option is not lost by default. It takes nothing back —
  every version published under the GPL stays under the GPL
  permanently, which `CLA.md` section 4 makes a binding term rather
  than a promise.

  **New: `CLA.md`**, a copyright assignment with an automatic fallback
  to an exclusive sublicensable licence for jurisdictions that bar
  assignment between living persons, plus a licence-back so a
  contributor keeps full use of their own work. It carries an explicit
  notice that it awaits legal review before the first external
  contribution is accepted under it.

  `CONTRIBUTING.md` gains the terms in human form, including the rule
  that surprises people most: **third-party source cannot be accepted
  at all**, however permissive its licence, because a contributor
  cannot assign title they do not hold. Assignability, not licence
  compatibility, is the test now.

- **`AGENTS.md` gains dependency licence tiers and a corrected prior-art
  record.** Tier 1 is sublicensable and freely dependable, tier 2 is
  arm's-length only (LGPL as an unmodified dependency, GPL as a
  separate process), tier 3 is refused outright. Build-time
  dependencies are out of scope — they are not distributed.

  The tiers are drawn against a stricter bar than the licence itself
  needs. What the project *states* is that relicensing is reserved and
  nothing is planned; what it *vets against* is the strictest realistic
  outcome, a commercial dual licence. So the question asked of any
  external source — dependency or prior-art reference — is "could this
  ship inside a proprietary product?", never "is this GPL-compatible?"
  The GPL arm could absorb a great deal a commercial arm never could,
  and vetting to the looser bar would forfeit the reserved option
  invisibly, at a moment when the judgement was free and long before
  anyone noticed it had been made.

  The prior-art section corrects reasoning that the relicense falsified.
  It previously held that os-autoinst's GPL-2.0-or-later licence *by
  itself* barred porting its code into a BSD project. That was true and
  is now not: GPL-2.0-or-later may be taken under GPLv3, so licence
  compatibility stopped being the obstacle the moment Reliquary became
  copyleft. **The boundary did not move.** It rests where it always
  actually rested — on doctrine, a close translation being a port
  whatever a licence permits — now joined by assignability, which bars
  the same code permanently and for an independent reason. The
  `consoles/VNC.pm` carve-out is corrected on the same grounds. The
  standing invitation to reassess adopting QEMU's in-tree `QEMUMachine`
  is withdrawn: it is GPL-2.0-only and unassignable, so the answer is
  no on licensing grounds regardless of maintenance.

- **BREAKING: `check-script` is gone. `run-script --dry-run` is its
  one spelling**, and `check_script()` / `ScriptCheck` go with it —
  deleted, not aliased. A dry run of a script is what `check-script`
  always was, and carrying two names for one semantic is what this
  retires. `run_script(label, dry_run=True)` returns the same `DryRun`
  the create half does.

  Three things change with the merge, none of them a rename:

  - **The selector is optional under `--dry-run` and required for a
    run**, because its presence chooses which tier is checked: without
    one, every legality rule; with one, the machine rules as well.
    Those are the two modes the script spec has always specified, and
    collapsing them would have deleted one in silence.
  - **A dry run is a document, not a stream.** `run-script` rejects
    `--json` because a live run's output is its event stream; under
    `--dry-run` the twin returns a document, so `--json` becomes legal
    and prints exactly it. `--progress` and `--display` are refused
    with `--dry-run` — a plan has no stream to render and no window to
    show.
  - The positional keeps `run-script`'s name, `label`, and resolves
    label-first then bare stem as it always has.

  **Fixed on the way**: `--blueprint` now actually reaches the
  machine tier. The script spec has always said either selector adds
  the machine rules, and `check-script` applied them for `--machine`
  only — so `--blueprint freedos` silently checked less than it
  claimed to, even with `freedos-0` sitting there. The report naming
  its own tier is what caught it. A dry run still stops where a run
  would *create*, so a blueprint with no machine yet reaches the
  static tier and the report says so.

- **BREAKING: `check_key()` is private.** It validated a property key
  and returned it — a predicate on a string, exported from the package
  but named in no parity row and reachable from no command, which made
  it a standing gap in the CLI–API rule. The parser applies it; a
  caller pre-validating a key was a use nobody had.

- **A drive image is no longer copied to be read.** At-rest access
  used to flatten the whole disk to a temporary raw file with
  `qemu-img convert`, work on that, and convert it back — a cost
  proportional to the disk and paid on every call. QEMU now serves
  the image with `qemu-nbd` on the loopback interface and Reliquary
  addresses it directly, so listing one directory costs the sectors
  that listing touches. Nothing about the guest's view changes; the
  same five in-band verbs reach the same drives.

  ```powershell
  rlq get-files "C:\OUT" .\results --machine rig-0   # no longer copies 2 GB
  ```

  **A write now lands in the image itself**, with a qcow2 internal
  snapshot standing behind it as the commit point: taken before the
  first byte moves, discarded when the write completes, and applied
  when it does not. The guarantee is the one staging gave — an
  interrupted, refused or crashed write leaves the disk exactly as
  it was — at the cost of the clusters a write touches rather than
  the size of the disk. A snapshot left behind by a run that never
  finished is reconciled by the next access, the way an interrupted
  machine operation is. An image already **raw** keeps the staged
  copy, having nowhere else to stand an undo, and a differencing
  image is still a difference over the same base afterwards.

### Fixed

- **The drive-letter map no longer assumes what a disk holds.** It
  placed hard disks from `C:` in slot order on the assumption that
  each carried exactly one volume. A guest that repartitioned its
  disk made that **silently wrong** — every letter behind it moved,
  and the map named the wrong drive rather than failing, so a
  `get-file` aimed at `D:` could read a different drive entirely and
  say nothing.

  Each disk now takes **one letter per volume it actually holds**,
  read off the image on the host. A disk partitioned in two takes
  `C:` and `D:`, and the next disk starts at `E:`; both volumes are
  addressable, where a two-volume disk used to be refused outright.
  A disk holding **no** volumes — a blank just materialized, before
  a guest partitions it — takes no letter at all, which is what DOS
  itself does, so the drive behind it is `C:`.

  The count is recorded in the machine's state and **cleared at
  every start**: a guest can repartition a disk and can only do it
  while running, so a count taken before a boot says nothing about
  the one after it. Reading it is affordable because the same change
  stopped copying disks to read them.

  A disk whose volumes Reliquary *cannot* read leaves every letter
  behind it unplaced, and says why in the terms of the thing that
  failed — the backend cannot read a drive image at rest, or the
  image itself is unreadable — rather than reporting the symptom
  that a letter could not be determined.

  `drive.volume-count-unsupported` is retired: a disk holding more
  than one volume is now addressed rather than refused.

## 0.1.0.dev4 - 2026-07-29

### Added

- **Files move to and from an installed disk directly.** All five
  in-band verbs now work a **drive image** while the machine is
  stopped: the host mounts the disk, reads the partition
  table and the FAT volume behind it, and hands the files back in the
  guest's own terms. A consumer whose output landed on an installed
  `C:` no longer has to reach around Reliquary with its own image
  tooling — which is what P16 forbids Reliquary to require.

  ```powershell
  rlq get-files "C:\OUT" .\results --machine rig-0   # the installed disk
  ```

  FAT12, FAT16 and FAT32 are read, partitionless or behind an MBR,
  logical drives in an extended partition included. Turning a
  backend's own format into raw bytes is the adapter's job — QEMU
  uses `qemu-img convert`, which resolves a differencing image's
  whole backing chain and costs a temporary flattened copy for the
  duration of the call.

  **Files go in the same way.** `put-file` and `put-files` write
  into a drive image too, so a script's inputs can be placed on an
  installed `C:` before the machine boots:

  ```powershell
  rlq put-file .\JOB.BAT "C:\JOB.BAT" --machine rig-0
  ```

  A write is **staged and swapped**: it lands in a scratch copy and
  replaces the disk in one step at the end, so an interrupted or
  refused write leaves the image exactly as it was. Allocation
  happens before any byte is written, so a full volume refuses with
  the file untouched; both FAT copies are written from one table, so
  they cannot drift apart; and a **differencing image stays one**,
  rebuilt over its own base rather than silently flattened into a
  standalone disk.

  A guest-side name must be one the guest could type — **8.3, or a
  refusal**. `RESULTS.TAR.GZ` is rejected rather than truncated to
  something you would not find later.

  Three refusals name themselves rather than answering as though a
  drive were empty: `drive.no-at-rest-access` (the backend cannot
  flatten its own image format), `drive.no-at-rest-write` (it can
  read one and not rebuild it), and
  `drive.volume-count-unsupported` (the disk holds more than one
  volume, so the drive-letter map is wrong about it and answering
  would answer for a drive you did not address).

- **In-band file exchange reaches a drive at any letter.** A machine
  with an installed `C:` and a directory-source drive for exchange
  could not address the exchange drive at all: with any hard disk
  declared, only `C:` was mapped and everything after it was
  `drive.letter-undetermined`, because a disk the guest partitioned
  in two shifts every later letter. The documented remedy was to put
  the exchange drive in a floppy slot, which is 1.44 MB.

  The letter map now places every drive — floppies at `A:`/`B:` by
  slot, hard disks from `C:` in slot order, CD-ROMs after them — on
  one stated assumption: **each hard disk holds one volume**. That is
  true of every disk Reliquary materializes, and a guest that
  repartitions can silently contradict it, so it is written into the
  mapping's own documentation and filed as a defect rather than left
  implied. Reading the real volume layout off the image is the work
  that closes it.

  ```powershell
  rlq get-files "D:\OUT" .\results --machine rig-0   # the exchange disk, behind C:
  ```


- **A blueprint diagnostic cites a line and column.** A bad field in a
  `.rlqb` used to report the field and nothing more — `unknown media
  field: drives.hdd0.bogus`, with no hint which of the four `hdd0`
  blocks in a long document it meant. It now reports where it was
  written, in the compiler-style form script diagnostics have always
  used:

  ```text
  rlq: blueprints\dos622.rlqb:8:34: error: unknown media field: drives.hdd0.bogus (field.unknown)
  8 |       "hdd0": { "media": "disk", "bogus": 1 }
                                       ^
  ```

  The breadcrumb stays in the message: it says *which field* where the
  position says *where*, and a reader wants both. Ids, exit codes and
  the message wording are unchanged, so anything switching on
  `rule_id` or on exit `2` is unaffected.

  The gap was structural rather than an omission — the parser
  validated an already-parsed object, so positions were gone before
  the rules ran. `jsonc.loads(..., positions=True)` now records where
  each member was written, in a second pass over the same text that
  `json.loads` already read, so the JSON semantics keep exactly one
  authority. Comment blanking already preserved offsets, which is what
  made a second pass agree with the first.

  **Position is optional and its absence is not a defect**: it comes
  from a document's text, so `load_document(path)` locates every
  diagnostic it raises, and `parse_document(value)` — handed a value
  that never had a position — renders exactly as it did before. Where
  the two passes disagree about shape, positions are dropped for that
  subtree rather than guessed at; a misplaced caret is worse than
  none.

- **The backend adapter seam.** Every backend operation now goes
  through one adapter API (`reliquary/backends.py`), extracted from
  the working QEMU implementation rather than designed ahead of one:
  discovery, a capability report, image materialization, start /
  stop, and the carrier session a control plane composes. QEMU's
  half moved wholesale into `reliquary/backend_qemu.py` — nothing
  above the seam names QEMU, qcow2, QMP or a port — and the
  agentless display console moved to `reliquary/control_display.py`,
  where it reads character rows plus opaque, equality-comparable
  attribute tokens rather than VGA bytes, so the cursor-menu
  machinery is written once for every backend rather than once per
  adapter.

- **Backend assignment, autodiscovery, and honest capability
  refusals.** `create-machine` now probes the host and picks the
  backend at materialization: a declared `backend` pins the choice,
  and otherwise Reliquary walks its priority order — **QEMU,
  VirtualBox, VMware Workstation, Hyper-V**, ranked by *agentless*
  scriptability — and takes the first backend both available and
  capable of the whole blueprint. Capabilities are reported, never
  emulated: an unsupported control plane, drive medium, controller
  or materialization mode fails preflight naming the backend and the
  requirement, before any image work. VirtualBox, VMware Workstation
  and Hyper-V ship as **stub adapters that probe the host honestly
  and claim no capability**, so the walk passes over them even where
  the backend is installed — the order's tail is intent recorded,
  not shipped behavior.

### Changed

- **An image drive now answers "no capability" instead of "wrong kind
  of drive".** With the letter resolving, `C:` really is the installed
  disk and what is missing is the reader, so
  `drive.not-a-host-directory` is retired for
  **`drive.no-at-rest-access`**, which names the remedy: give the
  machine a directory-source drive and have the guest copy to it.
  At-rest access to a drive image — reading and writing a FAT volume
  in an image while the machine is offline — stays unbuilt and stays
  filed.

  An **empty removable slot** was calling itself an image, which
  nobody had met because such a drive was unaddressable; it now
  answers **`drive.slot-empty`** and says to insert a medium.

- **The recorded VM identity is generic, and machines carry no
  port.** A running machine's `vm` section now reads
  `{backend, backend-id, token, endpoint, pid}` — the backend that
  owns the VM, that backend's own machine identifier, a per-start
  token, and an adapter-shaped endpoint (QEMU's is `{port}`) —
  replacing `{port, name, uuid, pid}`. Old machine states will not
  load; recreate them. With the endpoint behind the seam,
  **`start_machine()` returns the machine id** rather than a QMP
  port, `Machine` is `Machine(home=..., deadline=...)` with no
  `port=` (likewise `send_keys` / `send_text` / `screen_text` /
  `wait_text` / `cursor_menu_select` / `screenshot`), and the
  undocumented `--port` option is gone from the guest-console
  commands, which select a machine with `--blueprint` / `--machine`
  like every other command. `machine_drive_args`, `find_qemu`,
  `find_qemu_img`, `create_hdd_image`, `Qmp` and `stop` leave the
  embedding surface: they are the QEMU adapter's internals, and the
  adapter API is an internal engineering contract rather than a
  world-facing interface.

- **The wheel is the runtime; the source package is the whole
  project.** `reliquary_tests` no longer ships in the wheel — an end
  user has no use for 135 conformance fixtures in their
  `site-packages` — and the sdist now carries the suite, `docs/`,
  and `planning/design/` alongside it. The point is the
  spec-conformance tests: they read the normative documents and
  compare them against the code, so without those documents they
  skipped, and a source package that cannot run its own checks is
  not one a downstream packager can verify. Unpacking the sdist and
  running `python -m unittest reliquary_tests` now runs **902 tests
  with one skip** — the opt-in FreeDOS integration test — where it
  previously skipped thirty-three.

- **`tools/check_dist.py` checks the built artifacts.** With the
  suite out of the wheel, nothing running inside the wheel inspects
  it any more, and package data is exactly what goes missing
  silently: a dropped `script_grammar.lark` or `schemas/*.json`
  breaks an installed Reliquary at first use while every
  source-tree test still passes. The script names what each
  artifact must carry — and, for the wheel, what it must not —
  rather than inferring it from a suite that happened to pass. Run
  it after `python -m build`.

### Fixed

- **`exec` could return before the command ran, yielding unrelated
  screen text** ([#6](https://github.com/ferroteca/reliquary/issues/6)).
  The first `exec` after `start_machine` returned the guest's *boot*
  output instead of the command's, silently — no error, just a
  plausible-looking tuple of rows belonging to something else.

  The completion test asked only whether a prompt was on screen, and
  `wait_ready` returns *because* a prompt is on screen. So `exec`
  opened by testing the condition its own predecessor had just
  guaranteed, and the check ran before the guest — still finishing its
  boot script — had echoed anything. Completion now needs evidence
  that *this* command landed: its echo, or failing that a screen that
  has changed since the command was sent.

- **`exec` no longer returns text it cannot attribute to the command.**
  When the echo could not be found, the old code returned everything
  above the prompt, which is right when the output scrolled past its
  own echo and wrong when the command never ran — indistinguishable
  from the final screen alone. `exec` now tracks whether the echo was
  ever seen: if it was, a later absence is scrolling and the visible
  tail is returned as before; if it never appeared, that is
  `screen.no-echo` rather than somebody else's rows.

## 0.1.0.dev3 - 2026-07-27

### Changed

- **Every working directory is placeable.** Reliquary has six —
  `home`, `blueprints`, `scripts`, `cache`, `media`, `machines` —
  and all six are now specifiable through the CLI and the embedding
  API alike, where only `home` and `cache` were before. The other
  four were computed (`<home>/blueprints`, `<cache>/machines`, and
  so on) and unreachable, so a caller wanting machines on a fast
  disk and media on a big one had no way to say so. Each starts
  unassigned and the rest **derive**: `home` gives default
  locations to `blueprints`/`scripts`/`cache`, and `cache`
  — assigned or derived — gives them to `media`/`machines`.
  Derivation reaches only what is still unassigned. Normative:
  `docs/spec/asset-resolution.md` "The working directories".

  **The flags are renamed, and there are no aliases.** `--home`
  becomes `--home-dir` and `--cache` becomes `--cache-dir`, joined
  by `--blueprints-dir`, `--scripts-dir`, `--media-dir` and
  `--machines-dir` — one spelling for all six rather than two
  bare names beside four new suffixed ones. The API twins move
  with them: `set_home()` → `set_home_dir()`, `set_cache()` →
  `set_cache_dir()`, plus `set_blueprints_dir()`,
  `set_scripts_dir()`, `set_media_dir()`, `set_machines_dir()`;
  `media_cache_dir()` → `media_dir()` and `machines_cache_dir()`
  → `machines_dir()`; `home()` → `home_dir()`.

  **`RELIQUARY_HOME` is now `RELIQUARY_HOME_DIR`**, and four new
  variables join it — `RELIQUARY_BLUEPRINTS_DIR`,
  `RELIQUARY_SCRIPTS_DIR`, `RELIQUARY_MEDIA_DIR`,
  `RELIQUARY_MACHINES_DIR` — beside the unchanged
  `RELIQUARY_CACHE_DIR`. The rule is mechanical: `RELIQUARY_` plus
  the flag's own name. **An existing `RELIQUARY_HOME` stops being
  read and is not warned about** (no backward compatibility before
  1.0); rename it.

- **`Context` is now a plain record of the six directories** plus
  `autoseed`, with all resolution moved to `home.py`'s module
  functions. Its keywords are the flag names — `Context(home_dir=,
  blueprints_dir=, scripts_dir=, cache_dir=, media_dir=,
  machines_dir=, autoseed=)` — so the twin surface matches one for
  one, and six nullable strings bind cleanly from C or Java where
  six keyword arguments would not (P7). A bare-string `context=`
  is still shorthand for the home. `Context.home_dir` is now the
  slot rather than `Context.home`, and the `home_dir()` /
  `cache_dir()` methods are gone — call the module functions.

- **Unassigned is a fail-closed error on every surface.** A
  directory with no value when resolution needs it raises
  `StaticError` (`dir.unassigned`) naming that directory and the
  ways to supply it. The error fires at first use rather than at
  `Context` construction, so a context may be built before it is
  filled and the diagnostic names what was actually wanted rather
  than the root of a cascade nobody asked about. The CLI assigns
  the default home whenever neither a flag nor the environment
  named one, so one assignment reaches all six and the error is
  unreachable at the keyboard — a property of that default rather
  than an exemption from the rule. The embedding API assigns
  nothing, and there the error is reachable; that is the safety of
  the design.

- **`P12` is amended, and `P4`'s codex clause with it.** Six
  independently placeable roots make "the home" the name of one of
  them rather than a container, so home containment becomes what
  its safety content always was: Reliquary writes only where it was
  told to, and never beside the module or into a source tree. P4's
  "the codex never feeds automation" becomes a default rather than
  an absolute, since autoseeding is now switchable on both
  surfaces. Both amendments are recorded in `planning/DECISIONS.md`
  with the interface-change triage behind them.

### Removed

- **`--assets` is retired**, along with `assets=`, `set_assets()`,
  `HOME_ASSETS`, and the `HomeSource`/`DirSource` split behind
  them. It existed to name a project asset root because
  `blueprints` and `scripts` could not be named directly, and now
  they can: `--blueprints-dir <dir> --scripts-dir <dir>` says where,
  and one `DirectorySource` reads each kind from its own directory.

  The hermeticity the same flag also declared is now its own axis,
  **`--autoseed` / `--no-autoseed`** (API `autoseed=`): whether a
  name the directories do not hold may come from the built-in
  codex. It is **on at the CLI** and **off in the embedding API**,
  so a person still finds `freedos` on a fresh install and a
  library call still never picks up the codex unasked. Two axes
  where there was one knob, so a project tree may keep the codex
  behind it and a home may refuse it.

  Two consequences worth stating. Autoseeding now follows the
  *surface* rather than the directory, so `rlq --blueprints-dir
  ./project` in CI does seed unless `--no-autoseed` is passed —
  where `--assets ./project` never did. And `seed-blueprint` /
  `seed-script` now write into the assigned `blueprints` /
  `scripts` directory wherever it is, rather than always the home:
  seeding a first draft straight into the project tree you commit
  is now the ordinary way to do it.

- `import-vm` is gone from the CLI. It was a registered command
  whose entire body was `raise NotImplementedError`, while the CLI
  specification described it working in present tense — a synopsis
  with `--platform`, `--hdd-images` and `--snapshot`, prose
  semantics, and a worked PowerShell example — none of which the
  shipped subparser even accepted. Nothing is lost: the design was
  already settled and already recorded as unbuilt in two places
  (planning/proposed/FEATURES.md "Machine mobility", which took it
  off the numbered arc on 2026-07-23, and U2, which says in as many
  words that nothing of it is implemented). Its normative text
  leaves the CLI spec for the same reason the five phantom commands
  did on 2026-07-27 — a spec states what exists — and its end-goal
  design stays in `docs/spec/api.md`, whose banner scopes it to the
  end goal rather than to today.

  That sweep missed this one, and the reason is worth recording:
  its inventory test compares command *words*, and `import-vm`'s
  word was in both the spec and `_COMMANDS`. Only the parity check
  below could see that the word led nowhere.

  The same correction reaches the documents that described it and
  its siblings as working. `docs/spec/cli.md` no longer asserts
  twin identities for four unbuilt mobility verbs; the blueprint
  guide's "Cloning, exporting, importing" section — which
  documented `clone-machine`, `export-drive`, `export-machine` and
  `import-vm` in present tense, none of which exist — now says so
  in a banner and reads as design; and ARCHITECTURE.md no longer
  lists synthesis from a native VM among the ways a blueprint comes
  to be.

### Added

- **`list-files`, `get-files` and `put-files`: the in-band file
  family is complete.** A consumer that needed to know what a
  stopped machine's drive held, or to move a whole tree across the
  boundary, had no verb to ask and had to open the drive directory
  itself. Now: `rlq list-files "A:\"` reports what is there,
  `rlq put-files .\suite "A:\"` places a tree, and
  `rlq get-files "A:\OUT" .\results` takes one back — twins
  `list_files()` / `put_files()` / `get_files()`. Stopped-only over
  a directory-source drive, exactly like the single-file verbs
  they join.

  **One address vocabulary across all five.** A directory is
  addressed the way the guest names it, exactly as a file is;
  the only new thing sayable is the drive itself, as `A:\` or the
  bare `A:`, and a trailing separator is optional (`A:\OUT` and
  `A:\OUT\` are one address). A file address still needs a file.

  `list-files` reports one directory level, or the whole tree with
  `--recursive`. Its `--json` document is a flat array sorted by
  address, one object per entry —
  `{"address", "name", "kind", "size"}`, `size` null for a
  directory — and the addresses it reports are the ones the file
  verbs accept, so a listing feeds the next command directly.

  The plural verbs move a tree's **contents** into the destination
  rather than nesting the source under it: they recurse, create
  what they need, overwrite what is in the way, and delete
  nothing — a copy, never a mirror. `get-files`' destination is
  required and is created if absent; Reliquary invents no location
  to write to. An image drive is refused by name on all five, the
  QEMU adapter having no at-rest filesystem access.

- **`pacing`: a settling gap before guest input.** A script that
  waits for a screen and then types was landing its keystroke on an
  installer that had painted the screen but not yet begun reading
  the keyboard, and the key was swallowed —
  `freedos-install.rlqs` hit exactly this, timing out 30s later at
  the next step while pressing Enter by hand advanced it
  immediately. Every guest-input verb (`enter`, `type`, `press`,
  `select`) now pauses before its first key event; the default is
  **0.1s** and is expected to be revisited.

  The gap is tunable on the same lexical ladder `timeout` uses —
  `statement > phase > header > built-in` — as a `pacing` header,
  a `pacing=` phase modifier, or a `pacing=` on the verb itself.
  There is no branching-`wait` rung: an observation cannot carry
  `pacing`, so a verb inside a handler inherits from its phase.
  Resolution is entirely parse-time, so `check-script` reports a
  `guest input` section naming each verb's gap and the scope that
  supplied it, exactly as it already does for observation
  timeouts.

  **This is not the `delay` verb, and that prohibition stands.**
  The distinction is between a pause an author sequences and a
  pause that is a property of delivering input. Agentlessly a
  guest's *input* readiness is unobservable where its output is
  not, so a control plane that types the instant a screen paints
  asserts something it cannot know; `send_keys` already paced
  *between* key events, and this is the missing pause before the
  first. What the language gained is the ability to tune that gap,
  not to insert one.

  `pacing=0s` is legal and means "this guest is ready, do not
  wait" — the one duration in the language not required to be
  positive. A bound of zero asks for what can never happen, which
  is why `timeout`, `deadline` and `stable` still refuse it; a
  zero *interval* reads perfectly well, and refusing it would only
  produce `pacing=1ms` saying the same thing less honestly.

  Placement is enforced: `pacing` on an observation or on a
  host-side verb (`insert`, `eject`, `set-boot`, `screenshot`,
  `set`, `start`, `stop`, `http`) is a parse error naming why.
  `select` is the one verb in both halves of the model — it
  observes *and* delivers — so it carries a `timeout` for its
  feedback and a `pacing` for its delivery, and appears twice in
  the plan. Normative:
  `docs/spec/script-spec.md` "Timing"; recorded as D60.

- The README's "Blueprints and machines" section now shows the
  model instead of only describing it: a whole 1 MB MS-DOS
  blueprint, two machines created from it, `insert-media` changing
  one and not the other, and a second blueprint for a design that
  genuinely differs. The point the examples exist to make is
  stated once — the blueprint is the design, a machine's own state
  is what has happened to it since — so a reader can tell which of
  the two to edit.

  **README.md joins the documented-examples test.** Every fenced
  blueprint in the teaching documents is run through the real
  parser and the published schema; the README was outside that set
  while it had no examples, and is the document most likely to be
  read first and copied from.

  Three stale claims went with the rewrite: the section called the
  blueprint surface "milestone-1" (the arc ended at nine), the
  status note listed **run records** among what ships (D36 deleted
  them; a run stores nothing), and it said adopting blueprint
  edits means destroy-and-recreate, which predates
  `apply-blueprint` — now described with the limit that actually
  bites, a changed size on an already-materialized image.

- `rlq run-script --help` now explains the command rather than
  restating its name. It covers what LABEL resolves against, where
  the machine comes from and when one is created, what happens
  before the first guest input, the `machine`-header state rules,
  and the fact that a failed run leaves the machine standing for
  inspection because nothing is torn down implicitly. An exit-code
  table follows. `--display` had no help text at all and now says
  that input through the backend's own window is invisible to
  reliquary.

- **The lexer and the grammar carry identifiers too** — the second
  pass over D55, and the last that the script text alone can
  reach. 82 ids now cover everything decided before a machine is
  in scope: the tokenizer (`lex.unterminated-string`,
  `lex.invalid-duration`, …), line and block shape (`syn.`), the
  node signatures, and the static rules.

  Two prefixes were added, as the entry predicted: `lex.` for what
  the tokenizer rejects while reading characters, `syn.` for
  shape. The grammar's own rejections are the coarsest in the
  scheme and deliberately so — `syn.unexpected-token` names a
  token, never a rule, because that is all a parser knows. The
  spec now says as much where it explains why the S-rules sit
  above the CFG.

  **The corpus's unidentified count is zero**, down from six when
  it was written: all 39 invalid fixtures name the diagnostic that
  rejects them. What has no id is preflight and runtime — 30 sites
  that no parse fixture can reach, which is the same reason they
  are the corpus's `invalid-at-preflight/` bucket.

  **A defect the corpus found is now asserted rather than
  described.** A branching `wait` carrying a condition is rejected
  by the grammar, so it reports `syn.unexpected-token` and the
  `wait.branching-condition` arm in `script_validation` is
  unreachable — the exact trade `script_grammar.lark` warns about
  in its own header. The fixture carries a `# caught-by:` marker
  asserted in both directions, so whichever fix lands retires it.

- **Diagnostics carry stable dotted identifiers**, which
  `script-spec.md` has required of *every* one since the surface
  was adopted while none existed. 52 ids across the static rules
  and the node signatures — `obs.two-channels`, the spec's own
  example, is now a thing the code raises rather than a style
  illustration.

  **The scheme is finer than the S-numbers, which is what the
  defect left open to settle.** An S-number names a rule and an id
  names one diagnostic under it: S7 is one restriction with six
  ways to break it. So the two are not competing schemes and no
  renaming was needed — a message carries the id alone, and the
  spec's rule list carries the mapping. The corpus argued this
  before the design did: written against the S-numbers first, it
  worked but could not tell "no condition" from "unknown channel",
  both being S7.

  The id is a **field** on the error, not text in the message, so
  a consumer switches on `rule_id` without parsing prose and the
  beta index can be generated rather than hand-kept. Message
  wording stays uncontracted and free to improve. `RULE_OF` maps
  every id to its rule; three tests hold it, the spec's rule
  lists, and the raised ids together in every direction.

  Existing tests got stronger for free: the validation suite
  asserted rule citations by substring, where `"S1"` matched a
  message mentioning S12. It now goes through the id.

  **The remainder is measured, not estimated.** The lexer,
  preflight and runtime diagnostics have no ids yet; the script
  corpus records exactly which cases that leaves — four fixtures
  carrying `# id: none`, asserted in both directions so the marker
  cannot outlive the gap. The id *index* stays deferred to beta,
  where the spec always put it.

- **A conformance corpus for the `.rlqs` scripting language** —
  58 fixtures in three buckets, written from `script-spec.md` and
  run by `test_script_corpus.py`. This is the half of P24 the
  inventory sweep did not reach: the defect asked what a
  spec-derived *case set* looks like per interface and whether the
  blueprint corpus's pattern generalizes, and a set difference over
  an enumeration is not a case set.

  **It generalizes, and it arrives stronger.** The blueprint corpus
  can assert only that a fixture was rejected; its README names the
  cost — an invalid fixture failing for the wrong reason is a false
  pass, and only a reviewer can catch it. The script language has
  stable rule ids, so a fixture declares the S-id that must reject
  it and the harness checks the diagnostic cites it. That paid on
  the first run: three fixtures were rejected by the wrong rule
  (`finish` in a linear script trips S10 before the S8 or S9 clause
  under test) and would have passed a rejected-or-not assertion,
  then gone on passing after the rules they claimed to exercise
  stopped working.

  **Past a document format it does not generalize**, and the
  blocker has a name. A corpus needs artifacts to feed an
  implementation; for the CLI or the API those would be argv
  vectors or call sequences, which is possible — but with no
  stable diagnostic identifiers outside the S-numbers, such a
  corpus could asserts only an exit code, a six-value alphabet.
  That is why the other eight interfaces got inventory comparisons
  instead, and why the depth available there is bounded by D55
  rather than by effort.

  The corpus measured D55 rather than arguing it: six of 39 invalid
  fixtures cannot name their rule and carry a `# cites: no` line
  saying why — parse errors, header cardinality, duplicate
  modifiers, and S2's signature arm carry no identifier at all,
  though the spec requires one of every diagnostic. The markers are
  asserted in both directions, so one cannot outlive the gap it
  records, and the count is asserted too.

  One finding came out of writing it, recorded in the corpus
  README: `wait "x" { … }` is rejected by the **grammar**, so the
  S8 arm in `script_validation` for that clause is unreachable and
  the diagnostic is an unnamed `'{' is not valid here`. The
  grammar's own header says the S-rules stay above it "where a
  diagnostic can cite its id — encoding them here would trade named
  errors for 'unexpected token'", which is the trade this clause
  makes.

### Fixed

- **The test suite passes against a built artifact, not only the
  source tree.** Eleven tests read `docs/` or `README.md` without
  the source-tree guard the rest of the suite carries, so
  `python -m unittest reliquary_tests` against an installed wheel
  reported four errors and seven failures — none of them a real
  defect, all of them documents that are simply not packaged. The
  documented-example tests now skip as a class when the documents
  are absent, and the four script-corpus tests that read
  `script-spec.md` skip individually, so the fixture checks beside
  them keep running where they can. A downstream packager gets the
  same command working against the unpacked source package and the
  installed artifact alike, which is what the repository has always
  claimed.

- **Every diagnostic Reliquary can raise now names the rule it
  enforces.** `script-spec.md` requires a stable identifier of *every*
  diagnostic; the count is zero remaining, from 288. 284 ids across 26
  subjects, all 26 declared in the spec's prefix list.

  The last pass covered 108 across 13 modules — the machine verbs, the
  VM lifecycle, the guest console, DOS addressing, media acquisition,
  blueprint authoring and the small helpers. No subject needed
  arguing: `machine.`, `drive.`, `media.`, `value.`, `name.` and
  `blueprint.` already existed, and four more model nouns joined for
  things that had none — `image.` for a materialized disk image,
  `screen.` for what the guest displays, `script.` for a script file,
  `assets.` for the asset source. Reuse ran deep: `value.not-a-string`
  answers from nine places, `value.not-an-object` from seven,
  `blueprint.unknown`, `machine.not-running` and `value.not-a-size`
  from five each, `media.file-missing` and `machine.must-be-stopped`
  from four. A rule keeps one id however many layers can notice it.

  **Three assertions keep it closed, so the measurement need not be
  repeated.** Every deliberate raise in the package carries an id —
  405 raise sites inspected, with a narrow, documented exemption for
  faults, private signals and abstract-method stubs. Every id's
  subject is one the spec lists, checked in both directions. And both
  conformance corpora verify that the id a fixture declares is the one
  that fires.

  Writing the first of those found what a `raise`-statement sweep
  structurally cannot: **six diagnostics are *returned* by a helper**
  for a caller to raise, so their raise sites carry no keyword at all.
  Those helpers are exempt at the raise site and asserted at the
  construction instead, which is the only place an id can live for
  them. One had been missed on that account and now carries
  `machine.backend-failed-to-start`.

  It also surfaced a seam in `RULE_OF`, the id-to-S-rule map: it was
  scanned by module, on the assumption that three modules *are* the
  static tier, and `script_parser.py` raises one preflight diagnostic
  too. The map now covers every id the parser stack raises, with
  `None` where no S-number applies — which the `http.` family already
  did for rules predating the numbering — and its docstring says so
  instead of overstating the scope.

- **Every blueprint diagnostic carries a stable identifier, and the
  blueprint conformance corpus asserts it.** `document.py`'s 97 rules
  now name themselves — 73 distinct ids — leaving 108 across 13
  modules, from 205 across 14.

  The subjects come from the blueprint model's own vocabulary rather
  than being invented for the occasion: `ref.` for the `${…}` grammar,
  `value.` for what a field's value has to be, `field.` for the
  document's field vocabulary, `drive.` for drive keys, slots and the
  boot order, and `blueprint.` for the document as a whole. Two
  families took ids that already existed instead — the name charter is
  `name.`, being the same rule wherever a name was written, and media
  semantics are `media.`, including `media.remote-without-hash`, which
  resolution already raised. A single `blueprint.` prefix for all 97
  was refused: it would have made the prefix name the *surface*, which
  the spec forbids, and given 22 already-named rules a second id.

  **The corpus can now assert what its README said it could not.**
  That file stated in as many words that its headers were
  "documentation, not assertions", because an invalid fixture failing
  for the *wrong* reason is a false pass and only a reviewer could
  catch it — and the script corpus's docstring cited exactly that as
  the reason it was the stronger pattern. All 47 invalid fixtures now
  declare the diagnostic that must reject them, the harness compares
  it against the raised `rule_id`, and the marker is asserted in both
  directions so it cannot outlive the gap it records. One difference
  survives and is recorded rather than glossed: the script corpus also
  checks that an id serves the rule a fixture *means* to exercise,
  which it can do because its rules are S-numbered and blueprint rules
  are not.

  Some ids are deliberately coarse where the rule is one rule.
  `ref.not-allowed-here` rejects nine fixtures from three raise
  sites — a reference in `backend`, `control-planes`, `controller`,
  `materialize`, `platform`, `type`, a name, a drive key or a children
  path — because refusing a reference in a closed or identity position
  is a single rule (D26/D27) and the message names the field. A
  consumer switching on the id learns the rule; a person reading the
  message learns the place.

- **Diagnostic ids reach the properties file, the credential store
  and the CLI.** 40 more diagnostics carry one: `properties.py`'s 15,
  `credentials.py`'s 3, `cli.py`'s 13, and 9 sites in `machines.py`
  that raise a rule already named elsewhere. Three modules leave the
  idless list entirely, and the measured remainder is 205 across 14
  modules, down from 245 across 17.

  **The reuse is the point, and applying the scheme to a second
  surface proved it immediately.** Two of the properties file's rules
  were already named on the script surface — a key in the reserved
  `rlq` namespace is `name.property-reserved-namespace` whether a
  script declares it or a file defines it, and a key defined twice is
  `name.duplicate-property` either way. Had the prefix named the
  surface or the tier, those would be four ids for two rules. The same
  held for the CLI: "machine is not running", "select a machine with
  --blueprint or --machine", "is running but has no recorded VM
  identity" and "not implemented for platform" were all rules the
  script surface had already named, so the CLI reuses them and the
  duplicate sites in `machines.py` were brought along — leaving one
  copy of a rule identified and its twin bare is worse than either.
  `machine.not-running` now answers from five places with one id.

  **The subject list is closed and enforced.** The spec said the
  prefix is the subject and gave the list; nothing held the code to
  it, so a new diagnostic could take whatever prefix its author felt
  like — and a namespace that drifts cannot keep one id for a rule
  spanning two surfaces, which is the whole reason the rule exists. A
  test now holds the code's subjects and the spec's list to each other
  in both directions: an unlisted subject fails, and a listed subject
  nothing raises fails too. Both sides currently agree on 17 subjects,
  `platform.`, `progress.` and `store.` having joined with this work.
  The shared ids are asserted as well, so a future change cannot
  quietly give one rule a second name.

- **A blueprint naming an unbuilt backend is refused instead of
  silently getting QEMU.** `"backend": "virtualbox"` was accepted,
  recorded, and then ignored: `create-machine` materialized a
  **qcow2** image and `start-machine` would have launched QEMU, so a
  machine's recorded backend and its actual one disagreed with nobody
  told. `create-machine` and `apply-blueprint` now fail closed naming
  the gap — exit `3`, before any image work — exactly as an unwired
  control plane or a non-`ide` controller already did. Capability
  honesty (P11) asks Reliquary to name a gap rather than work around
  one, and this was the third unbuilt capability of the three not
  doing it.

  The field reference's backend/format table promised VDI for that
  same declaration, which made the document right and the code wrong.
  The table now marks which of its four rows is built and which are
  intent, recorded against the features that would deliver them.

  Found while disposing of a documentation entry, which is the part
  worth recording: the entry asked whether two orphaned rules in the
  descriptive field reference should be promoted to a normative spec.
  Neither should, and for the same reason — both describe capability
  that does not exist, and a spec states what exists. But the two were
  not otherwise alike. The `controller` ordering caveat was correctly
  gated, so it was only ever prose about an unreachable machine; the
  backend/format table was not gated at all, so it was prose the code
  actively contradicted. A rule about unbuilt capability belongs with
  the work that would build it, so both constraints moved to the
  proposed features that own them rather than into a spec or out of
  existence.

- **`put-file` and `get-file` refuse every disk address on a machine
  that mixes controller types**, rather than answering from slot order
  alone. Slot order is authoritative only *within* a controller type;
  across types the guest's firmware decides how the controllers
  themselves enumerate, so not even the first disk is a declared fact,
  and P17 requires failing closed where the declared facts leave an
  address ambiguous. Floppies are unaffected — DOS gives them `A:` and
  `B:` whatever the disks do.

  No machine can reach this today, because a non-`ide` controller is
  refused at creation, and the guard is asserted by test anyway. That
  is the point of it: the invariant belongs to
  `platform_dos.drive_letters`, and leaving it to a capability gate
  three modules away means the day a second controller type is wired,
  the mapping quietly starts answering a question it has no fact for.
  Volume count was the only documented reason a letter could be
  unfixed; this is the second, and it is now in the same docstring.

- **Every diagnostic the script surface can raise now carries a
  stable identifier.** `script-spec.md` requires one of *every*
  diagnostic; the static tier had 82 and the preflight and runtime
  tiers had none, so a consumer switching on `rule_id` got `None` for
  an unbound property, an unknown media, an undeclared slot, or any
  expired clock. 43 diagnostics gained one across property binding,
  media resolution, the script runner and the timing model.

  `rule_id` lives on `ReliquaryError`, the root, rather than on a new
  class per tier. The spec puts every id in one namespace shared
  across the classes, and the field at the root is the code saying
  the same thing — a diagnostic's identity is independent of which
  tier raised it. Every existing class picked it up unchanged, and
  no new machinery was needed: what was missing was only identity.
  *Location* already existed in two shapes, `ScriptParseError`'s line
  and column and the runner's statement citation, and conflating the
  two is what had made this look like a bigger job than it was.

  Two subjects arrived, `media.` and `machine.`, and they are why the
  prefix names the subject rather than the tier: `media.unknown` is
  the same id whether the resolution namespace defines no such media
  or a script's `insert` names one. One condition, one answer for a
  caller. Had the prefix named the tier, that single condition would
  have carried two ids and the caller would have needed to know which
  layer noticed. For the same reason four sites that restate a caught
  error against a script line now **forward the cause's id** instead
  of minting a new one, so `set-boot hdd6` inside a script reports
  the same rule as `rlq set-boot-order hdd6`. Each clock got its own
  id — run deadline, phase deadline, observation timeout, reactive
  interval — since a program that cannot tell which one ran out
  cannot act on it.

  The script conformance corpus stops asserting less than it knows.
  Its `invalid-at-preflight/` bucket previously asserted only that a
  fixture *parses*, which was all it could while preflight
  diagnostics were idless; it now runs preflight — the machine rules,
  then noninteractive binding — and asserts the id that comes out,
  in both directions like the parse bucket, plus that the rejection
  is a PREFLIGHT ERROR rather than merely late. Writing that
  assertion immediately caught a fixture rejected by
  `machine.slot-not-removable` where it claimed `media.unknown`,
  which was the harness's own fabricated machine being wrong — the
  kind of false pass the bucket exists to prevent.

  `RULE_OF` deliberately still maps the static tier alone. It maps an
  id to the S-numbered restriction it enforces, and S-numbers name
  syntactic restrictions only, so a machine rule has no S-number to
  map to; absent from it is correct for those ids rather than a gap,
  and the test that holds it to the spec now says so.

  **This closed one gap and measured a larger one.** Because D58 made
  the error classes describe every surface, the spec's id requirement
  travelled with them: a malformed blueprint is a STATIC ERROR
  exactly as a malformed script is, so it owes an id on the same
  terms. 245 diagnostics across 17 modules do not carry one — 97 in
  the blueprint document parser alone — which is filed as a defect
  with the per-module measurement rather than left to be noticed. The
  scheme needs nothing new for them; the blueprint surface needs its
  subjects argued, which is that work rather than this one.

- **Ordinary mistakes no longer exit `1`, the code reserved for
  Reliquary's own faults.** Five measured cases, five wrong codes:
  naming a media, blueprint, machine or script label that does not
  exist all exited `1` instead of `3`, and malformed blueprint JSON
  exited `1` instead of `2`. The taxonomy was implemented and
  correct the whole time — only the script surface used it, so 242
  raise sites across 19 modules were plain `ValueError`, `KeyError`,
  `RuntimeError` and `FileNotFoundError`, and the CLI had a clause
  naming seven builtins that turned every one of them into a tidy
  one-line exit `1`. A CLI-driving program could not tell "you made
  a typo" from "Reliquary crashed", which U9 rests on being able to
  do and P7 argues from the principle side.

  Every site is now typed, and the four classes are stated to
  describe **every surface** rather than a script run (D58). That is
  a ratification, not a change of direction: milestone 9's in-band
  file exchange already raised `PreflightError` from nine one-shot
  command paths, and *machine X is not running* was raised in three
  places as three different classes — exit 1, exit 1 and exit 3 for
  one condition. What decides a class never mentioned a script: is
  it settled by the authored input alone (STATIC ERROR), does the
  world satisfy that input (PREFLIGHT ERROR), did the work itself
  fail (RUN FAILURE). A capability this build declares but has not
  wired is the third of those — exit 3 rather than a crash, which is
  what capability honesty asks for.

  Exit `1` keeps its meaning and gains a class. `InternalError` is a
  deliberate fault — an invariant Reliquary detected in its own
  state — and subclasses the root so that `except ReliquaryError`
  stays the catch-all the API documents; it falls through to `1`
  alongside a genuine accident that never was a `ReliquaryError`.
  Unfit home state splits by reachability: an interrupted
  `create-machine` or a foreign VM on the port is a world condition
  with a recovery instruction (`3`), while a corrupt state file or an
  unrecognized phase is reachable only through a bug and stays a
  fault.

  Also fixed on the way through, each an ordinary mistake reported
  as a crash: `rlq press <typo>` raised a bare `KeyError` from a
  helper the CLI calls directly; an unreachable QMP socket reported
  `1` where the VM simply is not running (`3`); five bare
  `TimeoutError` raises meant a guest that never responded exited
  `1`, the builtin being reserved for a handle's `wait(timeout=)`
  expiry, where nothing has failed; two helpers *returned* a
  `RuntimeError` for a caller to raise, which no `raise`-site sweep
  would have found; and a malformed properties file and an
  unreachable credential store both said in their own docstrings
  that they sat outside the four classes, so both exited `1` for
  what are plainly a legality error and a machine rule.

  The rule is asserted structurally rather than reviewed: a test
  walks all 393 `raise` statements in the package and fails on a
  forbidden builtin, so the catch-all promise cannot erode. The
  CLI's seven-builtin clause is deleted — it would absorb a missed
  site and print it as a tidy `1` — and what reaches the remaining
  catch-all now prints a traceback and still returns `1`, because a
  fault should be loud rather than tidy. Roughly a hundred tests
  moved from builtin exception types to taxonomy classes in the same
  change, which is also how they came to assert the contract instead
  of an implementation accident; the blueprint conformance corpus's
  three-way `(ValueError, KeyError, TypeError)` collapsed to
  `StaticError` alone.

- `--qemu` is gone from the CLI's flag-arity table. The spec says
  the old global `--qemu`, `--platform` and `--port` "are removed",
  and no subparser has defined `--qemu` for some time, but the
  table still listed it — the code naming an option the spec said
  was gone. `--platform` and `--port` stay: they are live
  per-command options, and their place in that table is the
  position-carries-no-meaning rewrite rather than the removed
  globals.

  Deleting the entry alone would have made the diagnostic worse,
  which is measured rather than reasoned: `rlq --qemu foo
  list-machines` reported `unrecognized arguments: --qemu foo`
  while the arity entry let the reorder carry the pair past the
  command word, and without it argparse blamed the *value* —
  `invalid choice: 'foo'`, never naming the flag that was actually
  wrong. The reorder now looks past an unknown flag's value for a
  real command word, so the useful message is restored. **This is
  better than the state before the deletion**, not merely equal to
  it: the good message previously depended on a flag having an
  arity entry, so it worked for `--qemu` and for nothing else.
  `rlq --qmu foo list-machines` now names `--qmu` too. A bare word
  with no unknown flag ahead of it still stops the scan, so a
  plainly misspelled command is still reported as the invalid
  choice it is.

- `instance-model.md` still listed `clone-machine`, `export-drive`
  and `export-machine` in a command synopsis — the same three
  unbuilt verbs the 2026-07-27 sweep removed from the CLI spec,
  written in the same `rlq ...` shape, contradicting this
  document's own banner, which says clone and export remain
  unbuilt. A neighbouring sentence claimed they "require `ready`".
  Both are gone; the verbs are named as unbuilt with their design
  left where it belongs.

  **The test written to catch exactly this had a blind spot**: the
  command inventory read `docs/spec/cli.md` and nothing else, so a
  second copy of the defect it was written for survived one
  directory over. It now reads every spec. The direction is
  deliberately asymmetric — no spec may write a command that does
  not exist, while "every command is documented" stays cli.md's
  alone, since another spec is free to mention only the commands
  its own subject touches.

  The lifecycle phases are now pinned across all three places they
  are stated: the prose sentence that enumerates them, the
  `machine-state.schema.json` enum AGENTS.md requires to track it,
  and the literals `machines.py` writes. All five agreed.

- Media and the property facts now carry spec-derived tests, and —
  for the first time in this sweep — **found nothing wrong**. The
  `materialize` modes the media spec tabulates are exactly the four
  the parser accepts, and each parses under the table's own "needs"
  column; the `rlq.*` facts the properties spec bullets are exactly
  what `is_fact` admits, with `rlq.host.hostname` correctly named a
  parked candidate rather than a shipped one and the `rlq.env.*`
  family resolved by prefix rather than enumerated. The property
  source order was checked by hand against the spec's numbered list
  and matches: the cascade nests the environment and file tiers
  inside the parameter tier so a redirect can substitute the lookup
  key, which reads like a reordering and is not one.

  Both tests are drift guards rather than fixes, which is what a
  passing inventory is for. Named rather than skipped quietly
  (P24's clause): the media *field* vocabulary stays uncompared.
  Seven of its eleven fields have their own section in the media
  spec and the other four are specified in prose in the blueprint
  model, so comparing against the union would mean hardcoding which
  four live elsewhere — an exemption of exactly the kind the
  principle warns about.

- `asset-resolution.md` had no status banner at all, and had drifted
  in six places behind its absence. It was the one document in
  `docs/spec/` breaking the rule that directory itself states —
  *the banner is the marker; this directory is only shelving* — so
  its standing was undeclared and nothing it said had to be true.
  It now declares itself normative, which is what it always
  intended: its own closing line already called the home layout a
  world-facing contract, and the spec index already listed it under
  "The interfaces".

  What was behind it: `.rlqm` described as a media file kind, when
  media retired as files with the composed model and are specs
  inside a `.rlqb` (D30); `.json` unmentioned though the code
  accepts it as the legacy blueprint spelling; home mode said to
  resolve from a `media/` folder that does not exist and that the
  document's *own* layout diagram did not show; dir mode called
  "*every* embedding-API call" ten lines above the passage
  explaining that the API reaches home mode through an explicit
  marker; and a `landmarks/` folder in the home layout with no
  `landmarks_dir` behind it.

  The sixth was a `.rlql` landmark kind in `KIND_EXTENSIONS` that
  nothing ever requested — only `blueprint` and `script` are asked
  for, and home mode had no folder to resolve a landmark from. It
  is gone from the code and reserved in the banner beside the
  `ObjectSource` third source, the same treatment `screen.read`
  received. Landmarks remain settled design in
  planning/proposed/design/landmarks.md.

  Two tests hold it there: the kind table against the kinds any
  module actually requests, and the home-layout diagram against the
  folders `home.py` resolves — with reserved names read out of the
  banner, so designed-but-unbuilt stays documented without becoming
  a claim.

- The codex spec's status banner called `search-`, `seed-` and the
  provenance column "still planned" while all three shipped. That
  is not a cosmetic slip: by the banner-is-the-marker rule a
  disclaimed document is not claiming to be true, so those sections
  could not be tested against anything — the same failure that hid
  six divergences in the CLI spec, inverted. The banner now says
  what ships, and scopes the index honestly: blueprint names and
  descriptions, nothing else.

  Correcting it made a real divergence visible immediately. The
  provenance table was headed `CODEX` and gave a **blank** third
  value; `search-blueprints` prints a `PROVENANCE` column whose
  third value is the word `user`. A machine consumer of the
  `--json` form, switching on a blank field, would have matched
  nothing. The spec now carries the shipped vocabulary — `yes` /
  `seeded` / `user`, never blank — and a test derives the three
  words from that table and exercises all three paths, so neither
  can move alone. The pre-existing tests asserted each value
  individually and would have passed whatever the spec said, which
  is precisely the gap P24 names.

  `codex.json` also carried a `media` block that nothing read,
  listing two of the four media the codex blueprints declare —
  media are components inside a blueprint (D30) and are derived
  from it, so the block was stale by construction. It is gone, and
  a test pins the index to the blocks that actually ship. A second
  test catches a codex blueprint shipping with no index entry,
  which `list_builtin_blueprints` would otherwise skip silently —
  the existing test only checked the other direction.

- `screen.read` was declared event vocabulary that nothing emitted.
  It had a constant, a rendering arm, and a line in the script
  spec's minimum vocabulary saying it was "emitted by the `screen`
  command" — and `screen` prints its rows straight to stdout and
  never touches a stream, only `run-script` and `fetch-media`
  carrying `--progress` at all, so there was nowhere for the event
  to go. A consumer written against the stream would have waited
  for it forever. It joins the spec's existing reserved bullet,
  beside the `ended` terminal event and the U6 handover kinds, and
  loses its constant and its renderer arm to match: **a reserved
  kind has no constant**, which is now stated in the spec and
  enforced by a test that compares the declared vocabulary against
  what any module actually emits. `events.KINDS` is that declared
  set. Nothing else was dead — 19 kinds, all emitted.

  This is P24's pass over the recorded outputs. The spec gives the
  vocabulary as prose rather than a table, so there is no name set
  to diff against; what is checkable is the claim beneath the
  list, that the stream carries these kinds.

- `fetch_media` was missing from the package's `__all__`. It was
  importable, documented in the API reference, and the twin of a
  shipped command, but absent from the declared embedding surface —
  so `from reliquary import *` did not bring it in and the package
  did not admit to having it. It was the only such omission.

- CLI–API parity is now machine-checked. The twin-name identity
  rule — the CLI command *is* the twin's name, dash-separated, with
  nothing CLI-only — is a required invariant that until now only
  discipline enforced; a test compares `cli._COMMANDS` against the
  package's declared surface in both the has-a-twin and
  is-exported directions. The guest-console family's exemption is
  read out of `docs/spec/api.md` rather than listed in the test, so
  the exemption cannot quietly widen.

  This is P24's pass over the embedding API, and it is deliberately
  not the inventory comparison the other interfaces get:
  `docs/spec/api.md` declares itself the *end-goal design*, so it
  names capability that does not exist by design and cannot be
  diffed against the code. The rule it states about today is what
  is checked instead. Named rather than quietly exempted: only one
  direction is mechanical. "No public capability is unreachable
  from the CLI" needs a curated roster of the non-command surface —
  types, path helpers, parsers, lifecycle seams — which is a design
  round, not a test.

- In-band file exchange no longer guesses a DOS drive letter it
  cannot know. The letter map assumed one volume per hard disk, so a
  guest that partitioned a disk shifted every later letter and
  `put-file "D:\X.TXT"` wrote confidently to the wrong drive. Only
  two things are actually determined by what a blueprint declares:
  floppies, which take A: and B: whatever the disks carry, and the
  first hard disk, which is C: — plus cdroms when no hard disk is
  declared at all, since nothing can shift them. Addressing anything
  else is now a preflight error saying Reliquary cannot determine
  which drive it is, naming the determined letters, the undetermined
  drives, and the fix: address a determined letter, or give the
  exchange drive a floppy slot. It no longer reports "the machine
  declares no drive at D:", which was untrue when a drive was there.
  This is a capability Reliquary has not built rather than one it
  refuses: volume layout is readable from the drive images on the
  host, and the mapping may grow that way (D56).

- Watch patterns are now checked before the run, as **S13** has
  always required — "watch patterns are non-empty and regexes
  compile" — and nothing enforced. `wait /a(b/` parsed cleanly and
  then raised `re.error` from the sample loop, exiting `1` for a
  fault outside the taxonomy, from a defect visible in the script
  text alone; `wait ""` and `wait //` parsed into an observation
  matching every screen, so the wait passed on its first sample
  and waited for nothing. Both are static errors citing S13, the
  regex one naming the compile error and the dialect (Python's
  `re`, which the spec names as the language's contract). A
  pattern that is only a property reference — `wait "${target}"` —
  is not empty: it is text the run binds.

  It was found by asking the spec rather than the code. The
  scripting language now carries the inventory comparisons the CLI
  got with its command list: the S-ids the spec defines against
  the S-ids diagnostics cite, the node vocabulary against the
  lexer's keywords, each node's modifier signature against the
  parser's, and the error classes and exit codes against
  `errors.exit_code`. S13 was the one difference; the other three
  agreed. This is P24's second interface — every enumerated
  interface is to carry tests checking it *against its
  specification*, which is what catches a requirement the spec
  states and the code never implemented.

- Reserved node names are now actually reserved. The script spec has
  always said they "cannot name phases or property keys" — twice, in
  the grammar rules and in **S5** — and nothing enforced it, so
  `phase enter { … }` and `property text press` both parsed. The
  lexer treats a word as a keyword only where a node may start, which
  is deliberate and unchanged; what was missing is validation
  refusing those words as author-chosen identifiers. Both now fail as
  static errors citing S5. **The closed vocabularies stay
  contextual** (D53): a phase may still be named `cdrom0` or `esc`,
  and `press enter` still names the key — syntax words are reserved,
  domain vocabularies are not.

- The CLI specification described five commands that do not exist —
  `clone-machine`, `export-machine`, `export-drive`, `search-media`
  and `search-scripts`, in present tense with worked example
  output — and omitted five that do: `add-media`, `prune-media`,
  `put-file`, `get-file` and `get-machine-var`. Anyone following the
  spec for the first five got `invalid choice`. The unbuilt commands
  are gone from it (their designs stay settled under
  planning/proposed/FEATURES.md), the five real ones are specified,
  and a test now checks both directions so the inventory cannot
  drift again. `clean-archives` went with them, having been removed
  from the code when the single media cache landed.

- Two diagnostics named `hostdir`, a drive field that retired with
  the composed blueprint model. Trying to `insert-media --file` a
  directory now says the directory reaches a guest as "a declared
  media whose location is that directory" instead of "a declared
  hostdir drive", and the in-band file-exchange refusal asks for a
  "directory-source drive" without glossing it by the old name.
  Neither spelling was writable in a blueprint, so both messages
  named a construct the reader could not use. vvfat is unchanged:
  it is still how such a media attaches.

- A script inserting a media the active source does not define now
  fails at preflight instead of part-way through the run. The script
  spec has always required it — preflight rejects "media references
  (`@name`) naming no media the namespace defines" — and nothing
  implemented it, so `insert cdrom0 @typo` started the machine, ran
  as far as that statement, and failed there, possibly after guest
  input. It is now a preflight error (exit 3) raised before the
  machine starts, naming the media and offering the closest declared
  names. `check-script` reports it too. A `$property` media argument
  is unchecked, as it must be: it resolves at binding, not before.
  The slot is still reported first when one statement gets both
  wrong, in the order the author wrote them.

- A blueprint asking for a control plane Reliquary has not built now
  fails closed naming it. The blueprint model's `control-planes`
  vocabulary is four planes and only `agentless-display` is wired, so
  `create-machine` and `apply-blueprint` (twins `create_machine` /
  `apply_blueprint`) refused nothing and recorded a policy promising
  `vnc`, `serial-console` or `guest-agent` — a machine whose state
  claimed planes nothing could probe. The check runs before any image
  work, so a refused create leaves no machine behind and a refused
  apply leaves the machine exactly as it was. The parser still accepts
  the full vocabulary: the model names the planes, and the refusal is
  the capability report.

## 0.1.0.dev2 - 2026-07-26

### Added

- `insert-media` grew a `--file <path>` mode (twin
  `insert_media(slot, media=None, file=None)`) that mounts an image
  you built as an anonymous medium: attached in place, mutable, never
  copied, and never hash-verified — it is yours. On a running machine
  the guest sees the media change live, so a program can mount an
  image, run it, eject, rebuild, and mount again with no reboot
  between rounds.

- A live floppy swap is checked against the geometry the drive was
  launched with. The backend fixes a floppy drive's geometry when it
  attaches the medium at launch and a live change does not revise
  it, so a differently sized image reaches the guest as read and
  write errors rather than as a new disk — and a slot launched empty
  takes the backend's own default, which Reliquary never chose. Both
  now fail closed naming the sizes and the fix (stop, insert, start;
  after that live swaps of the same size work). Found by running the
  swap cycle against FreeDOS on QEMU rather than by reading the
  documentation.

- In-band file exchange, addressed the way the guest names it:
  `put-file <host-path> <guest-address>` and `get-file
  <guest-address> <host-path>` (twins `put_file` / `get_file`) move
  one file across the boundary as `A:\TEST.EXE`, never as a host
  image or staging directory. The drive-letter map is built from the
  machine's declared platform and Reliquary's own drive assignment —
  nothing is inferred by inspecting a guest. Both are stopped-only
  and require a directory-source (`hostdir`) drive; anything else
  fails closed naming the gap. Non-DOS platforms raise
  `NotImplementedError` rather than borrowing DOS assumptions.

- Machine variables — the script-to-host channel for a small value. A
  script's new `set <key> "<value>"` verb records one; `rlq
  get-machine-var <key>` (twin `get_machine_var`) reads it from any
  process, printing nothing (JSON `null`) and still succeeding when
  it is unset, so polling is a plain loop. Variables live in
  `machine.json` under the operation lock and are cleared at each
  `start`, so one always reports what the current boot produced. The
  `rlq` and `reliquary` key namespaces are reserved. Readiness rides
  this channel: your own ready script sets a variable and you poll
  for it — Reliquary ships no readiness script of its own.

- Live progress on the stream-bearing commands: `run-script` and
  `fetch-media` gained `--progress (auto | pretty | plain | jsonl)`
  (twins take `progress=`). `auto` resolves by whether stderr is a
  terminal; `pretty` is an in-place live line showing elapsed time
  against its limit; `plain` is one line per event plus a heartbeat;
  `jsonl` puts the run's event stream on stdout as JSON Lines and
  nothing else, the last line being the terminal event that states
  the outcome. `plain` and `jsonl` never prompt, so an unbound
  property is a preflight failure rather than a program hanging on a
  hidden question. A failed run now reports what was pending, the
  clock that expired and the scope that supplied it, the route
  through the phase graph with revisit counts, the screen row that
  came nearest to matching, an automatic screenshot, and the command
  to try next.

- An error taxonomy with one root: every deliberate Reliquary error
  subclasses `ReliquaryError`, so `except ReliquaryError` is always
  the catch-all. The run surface's four classes carry the CLI's exit
  codes — `StaticError` (2), `PreflightError` (3), `RunFailure` (4),
  and `RunCancelled` (5, which subclasses the root and never
  `RunFailure`: a cancellation is neither success nor failure). Exit
  `1` is now precisely a fault outside the taxonomy rather than the
  bucket everything fell into. Ctrl-C on a foreground run ends it at
  the next event boundary — an input already in flight completes —
  emits a `cancelled` terminal event, exits `5`, and leaves the
  machine exactly as it stands.

- A media `location` (or `sha256`) may reference a property with
  `${key}`, bound at `create-machine` / `recreate-machine` /
  `apply-blueprint` through the property source order — so a
  blueprint can name a non-redistributable ISO by `${windows.iso}`
  and each host supplies its own path or URL via `--property`, a
  blueprint parameter, `RELIQUARY_PROPERTY_*`, the properties file,
  or an interactive ask. Those commands gained `--property` and
  `--properties`. The resolved location is recorded in the machine
  state, so `start` never re-resolves it; an unbound key fails the
  create before any drive is materialized, and a bound value that is
  itself a reference is refused (a location binds once, it does not
  chain). This completes milestone 8.

- A script property can declare its own derivation with repeatable
  `default=` candidates, tried in order — the first whose references
  all resolve supplies the key, sitting between the properties file
  and the interactive ask. A candidate may reference literal text,
  another declared property (`${key}`), or an `rlq.*` host fact:
  `rlq.host.username` (login-normalized), `rlq.host.full-name`, and
  `rlq.env.<NAME>` (verbatim). An empty or unavailable fact is
  unanswerable, so resolution falls through to the next candidate.
  Static checks reject a `secret` with `default=`, a reference to a
  secret or undeclared key, a candidate after a literal one (dead),
  and a cycle among derivations. `check-script` names the derivation
  as a key's source without running it.

- Scripts bind the properties they declare. Before the machine
  starts, each declared property resolves from the first source that
  answers: a repeatable `--property KEY=VALUE` (never a secret —
  argv is not a credential store), a blueprint `parameter` (a direct
  value or a `{"property": "<key>"}` redirect), a
  `RELIQUARY_PROPERTY_*` environment variable (with fail-closed
  collision preflight when two consulted keys mangle alike), the
  properties file (a secret read from the credential store), or — on
  a terminal — an interactive ask. Without a terminal, an unresolved
  property fails before the machine starts, so a program never hangs
  on a hidden prompt. `run-script` and `check-script` gained
  `--property` and `--properties`; `check-script` now names each
  declared property's supplying source, never its value. A `secret`
  property expands only in `enter`/`type`, and its value is redacted
  from the transcript and diagnostics (shown as `«secret»`). The
  declared derivation and `${key}` location references arrive with
  later milestone-8 stages.

- Secret properties are real: `set-property <key> --secret` stores
  the value in the host credential store (via `keyring`, a new
  runtime dependency) and writes only the `@secret` marker to
  `user.properties`. The value never appears on the command line —
  on a terminal the command prompts without echo, otherwise it
  reads stdin to EOF — because process listings and shell history
  are not credential stores. Secrets are scoped by the absolute
  path of the properties file holding the marker, so a
  `--properties` file and the home's never share one. There is no
  plaintext fallback: a host with no usable store fails closed.
  Updates are fail-safe ordered (credential before marker, marker
  before credential), so the only recoverable leftover is an
  orphaned credential, which an ordinary `set-property` refuses to
  overwrite and `unset-property` clears. `get-property` and
  `list-properties` warn on stderr about a marker whose credential
  is missing, leaving the result itself unchanged.
- `--properties <path>` on every property command (API
  `properties_file=`, environment `RELIQUARY_PROPERTIES`) selects a
  properties file that **replaces** the home's for that
  invocation, so a project-committed file makes a run hermetic.

- `user.properties` is now the line-based, user-owned format its
  spec describes: `key = value` lines, `#` comments, blank lines,
  dotted keys validated (segments of letters, digits, `_` and `-`,
  each letter-initial; the `rlq` and `reliquary` namespaces
  reserved), and values taken verbatim as the trimmed remainder of
  the line — no quoting, escapes, or continuations. A leading `@`
  marks a value *kind*: `@secret` is the secret marker, `@@` a
  literal `@`. Property commands edit the file surgically — every
  comment, blank line, and ordering choice outside the named key
  survives — and write atomically. A malformed file is reported
  with its path and line and is never partly rewritten.
  `list-properties` gained its `[PREFIX]` argument, selecting a key
  and its dotted descendants.

- Published the machine-state JSON Schema
  (`planning/design/machine-state.schema.json`) for
  `reliquary-machine.json`, alongside the blueprint and
  media-definition schemas. A shared valid/invalid conformance corpus
  (`reliquary_tests/fixtures/conformance/`) now runs every fixture
  against both the parser and the schema so the two cannot drift
  (schema checks use `jsonschema`, a dev dependency, and skip when it
  or the repo schemas are absent).
- Authored-asset residency: a single global `--assets <dir>` flag
  (API `assets=`) selects where blueprints, media definitions, and
  scripts resolve from. Without it, **home mode** resolves from the
  home's canonical `blueprints/` / `media/` / `scripts/` folders and
  seeds missing names from the codex (the human-CLI convenience).
  With `--assets <dir>`, **dir mode** walks that project root
  recursively by extension as the **sole**, hermetic source — no
  home, no codex, no seeding — for reproducible automation. The
  embedding API has no default source and fails closed until one is
  named, so automation never silently picks up home assets or the
  current directory. `list-blueprints` / `list-scripts` gained API
  twins (`list_blueprints` / `list_scripts`).
- `--blueprint <name>` selection is scoped to the invocation's asset
  resolution: it matches only machines whose recorded
  `blueprint-source` equals the blueprint this invocation resolves,
  so same-named blueprints in different projects never select — and
  `apply` never adopts — each other's machines.
- The cache root (`cache/downloads/`, `cache/media/`,
  `cache/machines/`) resolves independently of the Reliquary home:
  `RELIQUARY_CACHE_DIR`, `--cache`, and `set_cache()` mirror
  `RELIQUARY_HOME` / `--home` / `set_home()`, defaulting to
  `<home>/cache`. Seeding (`seed-blueprint` / `seed-media` /
  `seed-script`) is unaffected — it always targets
  `<home>/blueprints` / `<home>/media` / `<home>/scripts`.
- `Context(home=None, cache=None)`, exported from the package
  root: every function that resolves a path under the home or
  cache now accepts a `context=` parameter (replacing the former
  `home=`). Omitting it uses the process-global default, same as
  before; a bare string is sugar for `Context(home=that_string)`;
  a `Context` instance pins home and cache explicitly, safe to
  vary per call within one embedding process. The CLI only ever
  drives the process-global default via `--home`/`--cache` — scoped
  contexts are an embedding-API-only capability.
- Packaging metadata now declares the project homepage
  (`https://github.com/ferroteca/reliquary`) so PyPI can link to
  the repository.
- ROADMAP milestone 5 is complete: `.rlqs` scripts can declare a
  run-scoped HTTP server for installer answer files, serve named
  inline or script-relative `from=` content, start selected or
  redefined content at `http start`, use the reserved
  `rlq.http.ip` / `rlq.http.port` / `rlq.http.url` bindings, and
  rely on explicit or implied `http stop` teardown.
- Built-in OpenBSD 7.9 amd64 codex assets: an
  `openbsd-7.9-amd64` blueprint, install ISO media definition, and
  install script using OpenBSD autoinstall over the run-scoped HTTP
  server.
- Machine blueprints are now validated against the full field
  reference: `backend`, `cpus`, per-drive `controller`, `base`
  (with `difference`/`duplicate`), `hostdir`, `enabled`,
  `control-planes`, `backend-settings`, and `parameters` join the
  parser, each failing closed and naming the problem. A `cdrom`
  drive accepts only a `media` reference or an empty slot (`size`,
  `base`, and `hostdir` are rejected on optical media); state-only
  fields (`blueprint-digest`, `blueprint-source`, `backend-id`,
  `id`) are rejected in a blueprint by name. Materialization of
  `base`/`hostdir` drives and backend capability checks ride later
  milestone-6 work.
- Media definitions accept the definition-level annotation fields
  `description`, `notes`, and `redistributable-under` (both the
  item and archive forms).
- `create-machine` materializes `base` drives (a differencing qcow2
  backed by the base image, or a full `duplicate` copy) and
  `hostdir` drives (a resolved host directory served over vvfat),
  resolves platform defaults (`memory`, `cpus`, `control-planes`)
  into the machine state, and records the machine's provenance —
  `blueprint-source` (the resolved blueprint path), `blueprint-digest`
  (the resolved-snapshot baseline), and `backend-id`. Non-`ide`
  controllers fail closed pending the adapter seam.
- `insert-media` / `eject-media` now work on a **running** machine,
  not just a stopped one: the medium change is applied live over the
  machine's identity-verified QMP session (each removable drive is
  launched with a stable QMP id) and persisted to the machine state,
  so the change the guest sees and the recorded state stay one
  operation. On a stopped machine they remain a pure state edit
  present at the next `start`. `set-boot-order` stays stopped-only.
- The global `--json` flag prints a command's result as one JSON
  document on stdout — exactly what its API twin returns, with a void
  twin printing `{}` — while diagnostics stay on stderr and exit codes
  are unchanged. The stream-bearing `run-script` and `fetch-media`
  reject `--json`, naming `--progress jsonl` as their machine-readable
  form.
- `search-blueprints` / `search_blueprints()` searches codex and home
  blueprints, matching a term against name, description, and platform
  and reporting provenance (`yes` built-in, `seeded`, or `user`). The
  `seed-blueprint` / `seed-media` / `seed-script` commands gain
  `--only` (API `only=`) to copy just the named file without its
  closure.
- `recreate-machine` / `recreate_machine()` destroys a machine and
  recreates it under the same id (re-resolving the current
  blueprint), and `get-machine-dir` / `get_machine_dir()` prints a
  machine's cache directory as an absolute path — the out-of-band
  file-exchange door, valid in any phase.
- `apply-blueprint` / `apply_blueprint()` adopts the current
  blueprint into a stopped machine (and returns a script-diverged
  machine to its blueprint shape): memory, cpus, boot order, control
  planes, metadata, and added/removed/`media`/`hostdir`/empty drive
  changes are applied and the baseline digest re-recorded, while a
  changed `size` or `base` on an already-materialized image fails
  closed, naming `recreate-machine`.
- Machine lifecycle is crash-safe: every mutating operation takes an
  exclusive per-machine lock and carries an operation generation, and
  the transitional phases `creating` / `stopping` / `destroying` are
  reconciled at the next operation — an interrupted stop completes, an
  interrupted create or destroy rolls forward to removal, and a create
  that fails mid-materialization leaves nothing behind.

### Changed

- **A run returns its output and stores nothing.** `run_script()` now
  returns the run's whole event stream on `ScriptRun.events` (plain
  dicts, in order, the terminal event last) instead of naming a
  directory it wrote. The event stream is live output — rendered as
  `--progress` asks and gone when the run ends — so a caller that
  wants a record keeps the one it was handed. This makes the
  multithreaded case clean: each run returns to its own caller, with
  no shared store to number or lock. `ScriptRun.run_dir` is gone;
  `execute_script` takes `events=` in place of `run_dir=`. A
  screenshot a script asks for now rests under the machine's own
  `screenshots/` directory.

- **The result is stdout; everything else is stderr.** A
  result-bearing command's plain output is now exactly the human
  rendering of what its twin returns — `create-machine` prints
  `freedos-0`, `new-blueprint` prints the path it wrote,
  `start-machine` prints the port — so they pipe clean with no flags.
  Narration ("destroyed machine …", "inserted … into …"), progress,
  and QEMU's own launch notes moved to stderr, and the human
  `--progress` modes leave stdout empty entirely.

- A media-slot preflight failure (`insert`/`eject`/`set-boot` naming
  a drive the machine does not declare) is now a `PreflightError`
  exiting `3` rather than a run failure — it is caught before the
  first guest input, which is what the preflight tier means.

- **Windows is declared as the supported host.** The packaging
  classifier moves from `Operating System :: OS Independent` to
  `Operating System :: Microsoft :: Windows`, and the README says
  so. Nothing about the code changed: host paths for macOS and
  Linux exist and are written portably, but they are untested, and
  an untested platform is an unclaimed capability rather than a
  quiet promise. What widening support would take is itemized in
  the roadmap's Horizon.
- **One media cache, wholly regenerable.** Every cached payload now
  lives in `cache/media/`, keyed by the name of the media it is — a
  container is a media like any other, so `cache/archives/` retires
  along with `clean-archives` / `clean_archives()` and
  `archives_cache_dir()`. Each file is named `<media-name>.<ext>`,
  and that is the whole of its identity: nothing enters the cache
  except by download or extraction, so every payload can be produced
  again and no sidecar record is kept of where it came from.
- **The media cache commands.** `clean-media` reclaims cached
  payloads, skipping anything a running machine holds open;
  `clean-media <name>` evicts one deliberately. `prune-media
  [--dry-run]` keeps the **attachment closure** — what the active
  scope can still attach — and drops what only existed to produce it,
  so after an install the extracted ISO stays and the zip husk goes.
  API twins: `clean_media(name=None)`, `prune_media(dry_run=)`.
- **`add-media` declares a local file instead of caching one.**
  Codex blueprints for commercial systems ship pinned but without a
  URL — Reliquary has no right to distribute a Windows ISO — so they
  name the build their scripts target and leave you to supply it.
  `add-media <name> <file>` now writes `blueprints/<name>.rlqb`
  declaring that media, located at your file and pinned to its
  SHA-256, which it computes for you. The file is not copied or
  moved, and the result is an ordinary blueprint you own and can
  edit. Twin `add_media(name, path)` returns the blueprint path and
  moves from `reliquary.media` to the blueprint-authoring verbs.
- **Codex names are generic, never version-bound.** The codex is a
  launching point for real blueprints, so its entries are named for
  the system and the version lives inside the file as the source
  URL and hash: `freedos-1.4-plain` → `freedos`,
  `openbsd-7.9-amd64` → `openbsd`, with the media following
  (`freedos-1.4-livecd` → `freedos-livecd`,
  `openbsd-7.9-amd64-install` → `openbsd-installer`). Scripts are
  named for the flow they drive, never a release:
  `freedos-1.4-plain-install` → `freedos-install`,
  `freedos-1.4-verify` → `freedos-verify`,
  `openbsd-7.9-install` → `openbsd-install`. The `-plain` variant
  marker goes with them — the launching point *is* the plain
  install, and variants are the user's. A codex version bump is now
  a content update under an unchanged name, and machine ids shorten
  with their blueprints (`freedos-0`). Descriptions still name the
  release each entry is tested against.
- **Composed blueprint model.** Reliquary's two authored JSON formats
  fold into one blueprint `.rlqb`, whose root is an **array of specs**
  of two types — `machine` and `media` — with a lone spec object
  accepted as sugar for the array of one and a bare string as a media
  located by it. `type` defaults to `media`, so an untyped lone object
  is a media and the bare-root-machine reading is gone; a machine that
  forgets `"type": "machine"` gets a did-you-mean naming the machine
  vocabulary it used. There is no `source` or `archive` type: a source
  is a media's `location`, and an archive is just a media that other
  media name as their **parent** — the distinction was never a
  property of the artifact, only of the use.
  A machine's drive names a media, is `null` for a declared-but-empty
  removable slot, carries `{media, controller, enabled}`, or holds a
  media **written in place** — including the content-free blank
  `{"size": "20M"}`, the format's one anonymous citizen, which belongs
  to no namespace and is named for its slot when materialized. The old
  four-way drive content selector (`size` / `base` / `media` /
  `hostdir`) is gone.
  The media owns materialization: `materialize` ∈ `new` /
  `difference` / `copy` / `use` (default `use`), with `size`, one
  `location` field, conditional `sha256`, `read-only`, `extension`,
  and `children`. **Containment is parent/children**: any media may
  declare `children` (recursive batch sugar, a bare string being the
  path) or its `parent` from the child side, and every edge resolves
  to child-declares-parent.
  **Locations follow one law — strings are interpreted, objects are
  explicit**: every accepted string has exactly one object desugaring,
  which is the canonical form. Strings dispatch by scheme (a bare
  path, an http(s) URL, `${media:<name>/<path>}`, `${<key>}`), objects
  are `url` / `local` / `parent`+`path` / `property`, and a list of
  them is a mirror list tried in order. A scheme-shaped string that is
  not recognized is a parse error rather than a silently relative
  path, with a drive-letter exemption for `C:/...`.
  **`${...}` is the one reference syntax.** An unqualified reference
  interpolates anywhere a string is accepted (`\${` is the literal
  escape); a qualified `${media:...}` is whole-value. References are
  refused in identity and graph positions (`name`, `type`, `children`
  paths, drive keys) and in the closed vocabularies (`platform`,
  `backend`, `materialize`, `controller`, `control-planes`), whose
  published-schema enums stay plain so editors can complete them. The
  reference body is closed at two productions and carries no
  operators. Property binding itself arrives with script properties;
  until then a `${key}` parses and then fails closed naming
  properties.
  Validation is **two-phase**: shape at parse, value at resolution —
  which is where the `sha256`-required-once-remote rule now lands,
  since a referenced rung may resolve to a URL.
  Identity is `(name, type)` in one catalog. A name is explicit or
  derived from content (never from the slot or the `.rlqb` filename),
  repaired to the name charter with a warning that names both the
  derived name and its source, and failing closed when it cannot be.
  Names match case-sensitively and collide case-insensitively.
  Canonically identical specs of one identity coexist across files;
  differing ones collide naming both.
- **Machine directory reorganized.** `cache/machines/<id>/` now holds
  `machine.json` (was `reliquary-machine.json`) with the live-VM
  identity folded in as a `vm` section written atomically with
  `phase`; per-machine images move to `media/<media-name>.<ext>` (was
  `drives/<key>.<ext>`, now keyed by media so removable-slot swaps
  never clobber); and backend artifacts (QEMU's captured stderr) move
  into a `<backend>/` subdir. `lifecycle.py` no longer owns a state
  file — `launch_owned_qemu` returns the identity and `machines.py`
  persists it. Every cached payload now lives in the one
  `cache/media/`, keyed by the name of the media it is: a container is
  a media like any other, so there is no separate archive cache.
- The cache-reclaim command `clean-downloads` and its API twin
  `clean_downloads()` are renamed `clean-archives` / `clean_archives`,
  matching the `cache/archives/` cache they reclaim and the composed
  model's `archive` components. No backward-compatible alias (pre-beta).
- **One published schema.** The blueprint and media-definition JSON
  Schemas collapse into a single `reliquary/schemas/blueprint-schema-v1.json`
  (packaged, versioned v1 so editors can bind it), with a two-variant
  root — a machine requiring its declared `type`, a media accepting its
  absence. `.rlqm` retires, and with it the `media` asset kind and the
  `<home>/media` folder; media are specs inside a blueprint.
- `list-blueprints` (local listing) resolves through the active
  asset source: home mode lists the home's canonical `blueprints/`
  folder (recursively within it), and `--assets <dir>` lists the
  project root. It reports each blueprint's identity name alongside
  its full path.
- The blueprint `name` field is the id-safe **identity** (selection
  key, machine-id segment), overriding the filename stem when
  declared — not a display label; human prose belongs in
  `description`. `new-blueprint` no longer writes a `version`
  field — blueprints carry no version pre-beta.
- Media definitions now reject unknown keys (matching the schema's
  `additionalProperties: false` and the blueprint parser), so a
  mis-spelled field is a loud error instead of a silently ignored
  no-op.

### Fixed

- A media declared at a local path that no longer exists now fails
  with a `PreflightError` (exit 3) naming the media and the path,
  rather than reaching the backend as a failure to open a file — or,
  when the media carried no `sha256`, being passed along dead and
  surfacing as an unexplained QEMU error at launch. A local payload
  is used in place, so it has to still be there, and the check runs
  at every fetch: creating a machine, starting one, and
  `fetch-media` alike. Directory sources (vvfat) are unaffected.

- Ctrl-C now stops a run during a large media fetch instead of
  minutes later. Cancellation was only observed at statement
  boundaries, so an `insert` that had to download a LiveCD ran the
  download, its hash check, the extraction, and *its* hash check to
  completion before noticing — against the documented promise that
  input deliveries are atomic while host transfers abort. The run
  engine's cancellation now reaches the transfer loops and is
  checked at every chunk (D40).
- An `insert` that fetches media reports its progress. The statement
  never passed the run's event stream down, so a multi-hundred-
  megabyte download printed one line and then nothing until it
  finished — silence that reads as a hang. Transfer and verify
  events now appear as they happen, like every other fetch (D40).
- A second Ctrl-C interrupts immediately rather than repeating the
  same graceful request. The handler previously folded every repeat
  into one flag, leaving no way out of a stop that would not land
  short of killing the terminal (D40).
- A download that stalls after connecting now fails that location
  instead of hanging forever: `urlopen` has a 30s timeout, and a
  timed-out mirror falls through to the next alternative (D40).
- An interrupted transfer no longer strands its scratch file in
  `cache/media/`. A fetch writes `<name>.part` and renames it only
  once whole, so a cancelled or failed one used to leave the partial
  behind — up to hundreds of megabytes for a LiveCD. There is no
  resume, so the partial is now discarded on every incomplete path
  (D40).
- The built-in FreeDOS install script no longer stalls at the
  installer's first confirmation. It pressed Enter on a menu the
  installer draws *before* it starts reading the keyboard, so the
  keystroke was swallowed and the install timed out at the next
  step; it now uses `select "Yes"`, like every other confirmation
  in that script — `select` is feedback-driven and confirms the
  highlight moved before committing.
- The guest-console commands (`screen`, `type`, `enter`, `press`,
  `exec`, `select`, `wait`, `screenshot`, `hmp`) work again against a
  machine selected with `--machine` / `--blueprint`. They resolved
  the machine's QMP port but not its directory, so the identity check
  looked for the recorded VM in the Reliquary home instead of the
  machine, found nothing, and refused every command as an identity
  mismatch.
- `set-property --secret` no longer writes the secret's value into
  `user.properties` in plaintext; it stores the value in the host
  credential store and records only the marker. (The previous
  behavior accepted `--secret` and ignored it.)
- Usage/help text now names whichever entry point was actually
  invoked (`reliquary -h` says `usage: reliquary ...`, `rlq -h`
  says `usage: rlq ...`) instead of always hardcoding `rlq`.

### Removed

- Run persistence and the verbs that managed it. There is no
  `cache/machines/<id>/runs/` directory, no stored `run-events.jsonl`
  or `transcript.txt`, no retention, and no `list-runs` / `run
  status` / `run delete` / `begin-run` / `end-run`. A stored stream
  existed to be read by a follower in another process, and following
  a run you did not start is asynchronous work that left the arc for
  the backlog — so the file had no reader. The whole record model
  returns only if that work schedules.

- The milestone-1 root-home machine model is gone, absorbed into the
  cached-machine model: `reliquary.Runner`, `MachineConfig`,
  `run_guest_program()`, `run_task()`, and the module-level `start()`
  (all of `workflows.py`), the root-home `machine.json` / `drives/` /
  `vm.json` layout and the `drives_dir()` path helper, the legacy
  filesystem drive auto-discovery (`drives.py`), and bare
  `rlq start-machine` / `rlq stop-machine` without a selector. Machines
  are created and driven through `create-machine` / `start-machine`
  (selector required) and `run-script`. No backward compatibility is
  kept before beta.
- The media-definition `redistributable-under` field is removed as
  overkill: Reliquary attaches no licensing metadata to a definition.
  Whether a codex definition may carry a `url` is now a maintainer
  discipline (the codex may only link to legally redistributable
  downloads), not a per-definition field.
- The dead `downloads_cache_dir` path helper (`Context` method and
  module twin) — a leftover pointer at the retired `cache/downloads/`.
  Its live counterpart `archives_cache_dir` (`cache/archives/`) is now
  exported from the package root in its place.
- `delete-media` / `delete_media()` and `seed-media` / `seed_media()`
  are removed outright. Media are components inside a `.rlqb`, so the
  first could only ever fail and the second could only ever do
  nothing; neither is kept as a shim. Removing a media means editing
  the blueprint that declares it, and seeding a blueprint brings its
  media along inside the same file. The noun in every media command
  is the media itself, never its owning file.

## 0.1.0.dev1 - 2026-07-22

### Added

- [TRADEMARKS.md](TRADEMARKS.md): the name **Reliquary** is owned by
  Paul Galbraith and is not licensed for forks or redistributions;
  the BSD-3-Clause grant covers the software only. Linked from
  README and CONTRIBUTING.
- `list-media` / `list_media()` lists media item names from the
  home library (or `--builtin` / `builtin=True` for the codex).
- `delete-media` / `delete_media(name)` removes a home media
  definition and refuses while any machine drive still references
  an item from that definition.
- `delete-blueprint` / `delete_blueprint(name)` removes a home
  blueprint file and refuses while any machine of it exists,
  naming the machine ids.
- Opt-in FreeDOS install+verify QEMU integration test
  (`reliquary_tests.test_freedos_install_integration`): set
  `RELIQUARY_INTEGRATION=1` (optional
  `RELIQUARY_INTEGRATION_HOME` to keep the media cache). Skipped
  under the default guarded unit suite.

### Fixed

- Script samples treat a guest power-off as `machine=stopped`
  when `lifecycle.qmp_session` raises its "no longer reachable"
  `RuntimeError` after clearing stale `vm.json`. Identity
  mismatches still fail closed. Unblocks FreeDOS install/verify
  shutdown after `fdapm poweroff`.

### Changed

- Milestone 4 (script-surface realignment) is complete: FreeDOS
  `run-script install` / `run-script verify` on
  `--blueprint freedos-1.4-plain` finish end to end, and
  `check-script` reports the timing plan.
- Documentation follows the redesigned script surface and the
  twin-name CLI: `planning/examples/README`, the script-spec and
  related design pages, and `docs/` quote `run-script`, the
  colon-free `machine` header, and `insert`/`eject`/`set-boot`
  rather than the superseded spellings.
- The old script surface and superseded CLI/API names are gone
  from the live tree. `reliquary_tests.test_old_surface_purge`
  fails the suite if they reappear in the package, tests, docs,
  README, AGENTS, examples, or shipped codex scripts.

- CLI/API twin-name identity (ROADMAP milestone 4, task 9): every
  command is its API twin's name, dash-separated. Lifecycle verbs are
  `create-machine` / `start-machine` / `stop-machine` /
  `destroy-machine`; listings are `list-machines` /
  `list-blueprints` / `list-scripts` (the nested `list …` form and
  its singular aliases are gone); media/cache commands include
  `fetch-media`, `clean-downloads`, `clean-media`, `insert-media`,
  `eject-media`, and `set-boot-order`; the guest-console family
  matches the script language (`type` raw / `enter` / `press` /
  `exec` / `select` / `screen`). Flags may appear before or after
  the command word without a parent-parser SUPPRESS twin.
  `--machine` takes the full `<blueprint>-<n>` id exactly — no
  prefix matching and no `--blueprint` + bare-number pair — and is
  mutually exclusive with `--blueprint`. The embedding API names
  match (`create_machine`, `start_machine`, `stop_machine`,
  `destroy_machine`).

### Added

- The redesigned script surface now has a typed parser:
  `reliquary/script_grammar.lark` mirrors the normative EBNF in
  `planning/design/script-spec.md`, and `reliquary.script_parser`
  builds the typed tree from it. Reliquary's own lexer feeds lark's
  LALR(1) parser through a custom lexer, so lexical diagnostics keep
  their authored wording — `lark` joins the runtime dependencies.
  The runtime still consumes the superseded surface; wiring it over
  is ROADMAP milestone 4's runner retarget.
- Static validation of the redesigned surface:
  `reliquary.script_validation` checks the legality rules the
  grammar deliberately does not carry, and each diagnostic names the
  construct and cites its rule id — the two script shapes and what
  belongs to each (S3, S10), unique phase names (S5), one condition
  per observation on a known channel of the right kind (S7), the
  branching `wait`'s shape and depth limit (S8), sequential-or-
  reactive phases (S9), and the terminating-statement rules (S11).
  Parsing a document now applies them.
- The script timing model: `reliquary.script_timing` resolves a
  script's whole timing plan at parse time — every observation's
  effective timeout and the scope that supplied it (innermost-wins
  over statement, branching `wait`, phase, header, and the built-in
  60s), each phase's per-activation budget, and the run's. A
  timing failure can therefore name the clock that expired and
  where it came from, and `check-script` can report the plan
  without running anything. Alongside it, the placement matrix's
  rejections now give their reason and cite S2 — `deadline` on a
  single observation would be a synonym for `timeout`, `timeout`
  on a handler belongs on its container, `stable` needs a match to
  hold — durations must be positive (S5), and a phased script
  whose reachable phase graph can cycle must declare a header
  `deadline` (S12), the diagnostic naming the route that closes
  the cycle.

- The script runtime executes the redesigned surface. `.rlqs` runs now
  walk the phase graph from `entry` to `finish`, dispatch branching
  `wait` blocks by declaration order, and run reactive phases' standing
  `always` handlers to completion — a fired handler consumed for its
  episode, re-arming only after a sample at which its condition no
  longer holds, so a persistent confirmation screen produces input once
  per appearance rather than on every sample. Every clock comes from the
  parse-time timing plan, so a timing failure names the clock that
  expired and the scope that supplied it, and observation timeouts,
  reactive intervals, per-activation phase budgets, and the run deadline
  are all enforced at sample and statement boundaries.
- The shipped scripts speak the redesigned surface: the built-in
  `freedos-1.4-plain-install` and `freedos-1.4-verify`, and the
  `planning/examples/` pair. The install script is the language's
  reference script. Seeding a script still brings the media
  definitions its `insert` statements name — the scan follows the
  `@name` spelling now, and a `$key` property reference names no
  static item to seed.
- Script sessions are identity-verified. Every sample and input verb
  opens its own QMP session through `Machine.qmp()`, so the runtime can
  no longer drive a VM it has not confirmed is the one this home
  started, and no session is held while a handler body runs.
- `check_script()` / `rlq check-script` report a script's resolved
  timing plan without running it: each observation's effective
  timeout and source scope, phase budgets, and the run deadline.
  The check is read-only (no seeding, no machine create). With a
  machine selector it also preflights media slots. Static errors
  exit 2.
- `press` key names are statically checked against the script
  language's closed portable vocabulary (S14). Unknown names, bare
  printable characters, and malformed chords now fail before a
  machine starts; chords such as `ctrl+c` remain valid.

### Removed

- The milestone-one script parser (`reliquary.script`) is gone, with the
  surface it parsed: `state`/`->`/`done`/`expect`, colon headers, comma
  modifiers, the `regex` keyword, bare `stopped`, `<key>` tokens inside
  `type`, and the `boot` verb (now `set-boot`). `parse_script` and
  `load_script` live in `reliquary.script_parser` and speak the new
  surface; the `State` and `ExpectBranch` exports are replaced by
  `Phase`, `Handler`, and `Property`. Scripts written for the old
  surface do not parse — rewrite them; there is no bridge.
- `ScriptRun.final_state` is `ScriptRun.final_phase`, and
  `rlq run-script` prints `final script phase:`.
- Scripts no longer carry embedded JSON. The `media <label> { ... }`
  block is deleted from the language, along with the planned
  `landmark <name> { ... }` block, the install-on-first-run model
  they implied, and `fetch-media --script`. Media definitions
  (`.rlqm`) and landmark declarations (`.rlql`) are authored files
  of their own, resolved beside the script and referenced by
  `@name`. A script that contains a `media` block no longer parses;
  move the definition into its own file beside the script. The
  parser's `EmbeddedMedia` model and the `reliquary.EmbeddedMedia`
  export are gone. Rationale and what was weighed:
  `planning/DECISIONS.md`.

### Changed

- Screenshot conversion uses Pillow in place of a hand-written PNG
  encoder and PPM header parser, so `pillow` joins the runtime
  dependencies. It also underpins the planned landmark image assets:
  decode normalization, pixel comparison, and PNG text chunks for
  capture provenance.
- `rlq list-machines` and `rlq list-blueprints` report an explicit
  `(no ...)` message on an empty result instead of a column header
  over zero rows, matching `list-scripts`, which already did.
  (`#5`)
- `rlq list-scripts --blueprint <name>` heads its first column
  `LABEL`, naming what it lists: the blueprint scripts-map labels used
  as `run-script` verbs. The bare `rlq list-scripts` listing keeps
  `NAME`, which is what it lists: script file stems.
- Scrubbed private project-history references from release-facing
  documentation and package metadata.
- Removed obsolete references to a superseded installation abstraction;
  built-in blueprints, media definitions, and scripts are the documented
  sharing model.
- Reinstated the released 0.1.0.dev0 section of this changelog to its
  exact release-time text — prior-project history included; it is
  real history. Released changelog history is append-only from here
  on: it is never retroactively edited, with minimal privacy/legal
  redaction the sole exception (the rule lives in
  `.agents/skills/documentation-rules.md`).

## 0.1.0.dev0 - 2026-07-20

The relict project — the agentless QEMU guest automation harness Reliquary
was built on — has been folded into Reliquary. Its modules now live in the
`reliquary` package (its drive-inventory module renamed to `drives.py`), its
CLI commands are `reliquary` subcommands alongside `install`, and its home,
`RELICT_HOME`/`RELICT_QEMU_HOME` environment variables, and default
`Documents/relict` directory are replaced by the Reliquary equivalents
(`RELIQUARY_HOME`, `RELIQUARY_QEMU_HOME`, `Documents/reliquary`). The notes
below merge both projects' unreleased histories with the relict entries
renamed accordingly.

### Recipe layer

Initial scaffold: package structure, CLI stub, and recipe module convention.

The planned `.rlqs` scripting language now separates linear scripts
from explicit state machines, uses run-to-completion reactive states,
and adds immutable text, media, and secret inputs bound from JSON
responses, a home-wide user property registry, or interactive prompts.
Ordinary reusable values live in `properties.json`; passwords and
product keys can use secret markers backed by the host credential
store, and script declarations bind them with `property:`. Scripts may
also embed the same JSON media-definition objects used by the shared
library; after preflight, running a script installs missing definitions
into `media/` without overwriting or updating existing files, while
verified artifacts continue to use shared caches. Console input is
expressed with `enter` rather than a separate `run` verb; guest reboot
remains console or menu input, while host power cycling is the explicit
`stop`/`start` pair. Timing, matching, preflight, transcript, and
offline file-exchange semantics are specified consistently ahead of
implementation.

Added the `freedos-plain` recipe's preparation steps: the FreeDOS 1.4
LiveCD ISO is downloaded into the Reliquary home (the distribution
zip is deleted after extraction) and SHA-256 verified on every run,
and
a 20 MiB dynamically allocated qcow2 (v3) target disk is created. The
`reliquary install <recipe>` CLI command runs a recipe by name, and
`--display` (the `display` recipe parameter) requests a visible QEMU
window for a recipe's guest steps.

The recipe now extracts the LiveCD ISO and boots the installation
machine with the ISO and target disk mounted, booting
from the CD. After start it waits for the LiveCD's first install menu
(`Welcome to FreeDOS 1.4 (LiveCD)`), selects "Install to harddisk",
accepts the defaults for preferred language and the installer welcome
screen with Enter, confirms partitioning drive C: and the required
reboot with Yes, accepts the default keyboard layout with Enter,
chooses the "Plain DOS system" package set (excluding the "with
sources" sibling), and confirms with Yes on the ready-to-install
prompt. `install` then blocks while the machine runs and always shuts
it down when it ends — including on Ctrl-C, which the CLI reports as
an interruption instead of a traceback.

The recipe layer has since been retired in favor of the `.rlqs`
install/verify scripts on the blueprint machine model (see the
machine-layer notes below); `rlq install` no longer exists.

### Machine layer (formerly relict)

### Changed

- Machine ids are `<blueprint>-<n>` instead of random UUID hex.
  `create` allocates the lowest free number for the blueprint
  (reused after `destroy`), serialized by a per-blueprint lock.
  Select with `--machine NAME-N`, `--blueprint NAME --machine N`,
  or `--blueprint NAME` when that blueprint has exactly one machine.
  `short_id()` is removed; the id is already the display form.

### Fixed

- An interrupted machine deletion, such as a transient Windows file lock,
  no longer leaves the machine permanently in the `destroying` phase;
  rerunning `rlq destroy` now retries it safely.

- A configured drive source for a slot already declared by a filesystem
  drive now fails closed with a slot-clash error instead of silently
  replacing it. An explicit `enabled: true` on the configured entry
  remains the deliberate way to override the filesystem drive, and
  `enabled: false` still unmounts it.

### Removed

- The recipe layer is retired (milestone-1 Spike 12): the `recipes/`
  package, the `rlq install <recipe>` command, and the recipe-era
  helpers (`ensure_media`, `install-media/` and `machines/<recipe>/`
  home paths) are deleted. The `.rlqs` install/verify scripts on the
  blueprint machine model replace them; there is no migration
  (pre-release).

### Added

- Milestone-1 Spike 13 lands the media-in-script machine model:
  blueprints declare empty removable drives (`"cdrom0": null`) — the
  blueprint alone defines machine topology — and scripts `insert` a
  defined media item to a declared slot and `eject` it, persisted in
  `reliquary-machine.json` across stop/start (`insert_media` /
  `eject_media` on the Python surface; stopped machines only for
  now). The new `machine: running | stopped` script header declares
  the state a script expects: `stopped` scripts start the machine
  themselves after inserting media, and `script` no longer
  unconditionally auto-starts. Insert/eject slots are statically
  preflighted against the machine before any guest input, and a
  guest-initiated power-off observed by `wait stopped` reconciles the
  machine back to phase `ready`. The built-in `freedos-1.4-plain`
  blueprint boots `["hdd0", "cdrom0"]`: a blank hard disk falls
  through to an attached LiveCD for install, then boots the
  installed disk afterward with no boot-order change. Scripts may
  still reorder boot devices with the `boot` verb / `set_boot_order`
  while the machine is stopped.

- Milestone-1 Spike 10 wires `rlq --blueprint|--machine script <label>`:
  resolve the label through the blueprint `scripts` map (bare stem when
  absent), seed a missing script from the built-in library, create a
  machine when `--blueprint` names one with none yet, and execute under
  an append-only run directory
  `cache/machines/<id>/runs/<timestamp>-<run_id>/` with `transcript.txt`,
  `screenshots/`, and `output/`. `run_script()` is the Python surface;
  `--display` forwards to the runtime. A `screenshot` inside a run
  verifies the QMP session against the machine's own `vm.json` while
  writing the image into the run record (`machine.screenshot()` gained
  a `directory` override to separate the destination from the
  identity home). Embedded media blocks,
  `--responses`, and `check-script` remain later spikes.

- Milestone-1 Spike 9 executes FreeDOS-shaped `.rlqs` scripts against a
  cached QEMU/DOS machine: normalized VGA `wait`/`expect`,
  `enter`/`type`/`press`/`select`, `screenshot`, host `start`/`stop`,
  and (with Spike 13) stopped-machine `insert`/`eject`/`boot`,
  starting a ready machine when needed and leaving it running unless the
  script stopped it. `expect` closes its polling QMP session before
  running the matched branch: QEMU's QMP server admits one client at
  a time, so a branch statement opening its own session while the
  polling session was still held would block forever.

- The global `--home` now reaches the `start`/`stop`/`destroy`
  subcommands: their own `--home` options no longer clobber an
  already-parsed global value with their default, which silently
  targeted machines in the default home.

- VM identity is per QEMU instance, not per name: every start passes
  a fresh `-uuid`, records it in `vm.json` beside the name, and every
  session verifies `query-uuid` as well as `query-name`. Same-numbered
  machines of one blueprint in different homes share their readable
  name, so a name match alone can no longer authorize a command
  against the wrong home's VM. The legacy root-home start path now
  uses the readable name `reliquary-machine` instead of a random hex
  suffix, since uniqueness comes from the uuid. A machine stop that
  fails closed on an identity mismatch no longer resets the phase to
  `ready`: the machine's own QEMU may still be running, so the phase
  only reconciles when the recorded VM is actually gone.

- Milestone-1 Spike 8 parses the FreeDOS-shaped `.rlqs` language into an
  immutable script model: headers, embedded media definitions, linear and
  state-machine bodies, `wait`, `expect`, `enter`, `type`, `press`,
  `select`, `screenshot`, `insert`, `eject`, `boot`, `start`, `stop`,
  and explicit transitions report source-located, compiler-style
  syntax and static-validation errors.

- The built-in library seed: blueprints, media definitions, and
  scripts ship inside the package under `reliquary/codex/`
  (included in wheels and sdists, readable from zip-bundled
  installs) and are copied out into the home on first reference —
  resolving an unknown blueprint via `create` seeds
  `blueprints/<name>.json` plus the media definitions and scripts
  it references, and resolving an unknown media name seeds its
  definition. A file already present in the home is never
  overwritten; deleting a copy is how it is refreshed. First
  entries: the `freedos-1.4-plain` blueprint, the
  `freedos-1.4-livecd` media definition (URL carried with an
  explicit redistribution assertion — FreeDOS is GPL free
  software), and the install/verify scripts.
- Machine lifecycle CLI and API for cached machines: `create`
  / `start` / `stop` / `destroy` / `list machines`, with
  `--blueprint` (sole machine of that blueprint),
  `--machine <blueprint>-<n>` (full id or unambiguous prefix), or
  `--blueprint NAME --machine N` (machine number). Machine ids are
  `<blueprint>-<n>` with the lowest free number reused after
  destroy; allocation is serialized per blueprint. `create_from_blueprint()`,
  `list_machines()`, `resolve_machine()`, and `machines.start` /
  `machines.stop` / `destroy` operate on `cache/machines/<id>/`;
  QEMU ownership (`vm.json`) lives under the machine directory.
  Bare `rlq start` / `rlq stop` without a selector still use the
  transitional root-home `MachineConfig` path. `apply`,
  interaction-via-selector, and multi-backend remain later spikes.
- Immutable machine-blueprint parsing for the milestone 1 subset:
  `parse_blueprint()` / `load_blueprint()` accept `platform`, `memory`,
  `drives` (`size` or `media`), `boot`, `name`, `description`, and
  `scripts`; canonicalize drive aliases, sizes, memory, and boot keys;
  resolve media names through the shared media library; and reject
  unknown fields, slot clashes, invalid sources, and undeclared boot
  targets.
- Machine materialization: `create(blueprint)` writes
  `cache/machines/<blueprint>-<n>/reliquary-machine.json`, qcow2
  images for `size` drives, and media payload paths for `media`
  drives; `machine_drive_args()` renders QEMU `-drive` tokens from
  that state.
- Media definitions per docs/media-spec.md: `parse_definition` /
  `load_definition` validate both the item (direct-download) form and
  the archive form (one source archive itemizing payloads, single
  URL), and `resolve_media(name, home=None)` resolves an item by name
  across the `media/` library, failing on duplicates. Mirror URL
  lists and several definitions sharing one archive remain
  unimplemented (milestone 2).
- `fetch_media(name, home=None, on_mismatch="fail")` returns a
  defined item's verified payload on demand, trying the cheapest
  source first: an existing payload that verifies is returned
  untouched, a cached source archive that verifies is re-extracted,
  and only then is the definition's URL downloaded. Source archives
  are cached under `cache/downloads/` and payloads under
  `cache/media/`; every file is SHA-256-verified before use, and a
  missing source is an error naming the item, file, and hashes.
  An existing payload or archive that fails its hash is never
  silently discarded: `on_mismatch` picks between failing fast with
  both hashes (`"fail"`, the default), an interactive
  delete-and-refetch checkpoint (`"prompt"`), and pre-approved
  deletion (`"refetch"`, which the planned `--refetch-mismatched`
  CLI flag will map to). A mismatched file whose definition names no
  source is always kept and reported.
- Path helpers for the planned blueprint home layout:
  `blueprints_dir`, `media_dir`, `scripts_dir`, `cache_dir`,
  `downloads_cache_dir`, `media_cache_dir`, and `machines_cache_dir`
  (each accepts optional `home=`). The existing `drives/` /
  `machine.json` / `vm.json` machine model is unchanged.
- `cursor_menu_select(item, timeout=30, exclude=(), port=None,
  home=None)` and the `Reliquary menu ITEM [--exclude TEXT]` CLI command
  select an entry in a cursor-key driven text menu (for example a boot
  menu). Rows containing an `exclude` text are never selected. Menus
  that rewrite their rows as the highlight moves (the FreeDOS
  installer's language chooser) are navigated by the row where the
  item last matched. Navigation is feedback-driven:
  Reliquary presses the up/down cursor keys, follows the selection
  highlight through the VGA attribute bytes, and presses Enter only
  once the highlight sits on the single screen row matching the given
  text (case-insensitively; an exact row match wins over rows merely
  containing the item, which otherwise must be unique). Each keypress
  waits for the repaint it causes to finish and hold steady rather
  than acting on the first changed read, so slowly repainting menus —
  the FreeDOS language chooser retranslating itself, with mid-repaint
  pauses while translations load — are never acted on half-drawn: a
  difference that shows no row gaining a bar-like (rare) attribute is
  re-observed instead of steered on, since keys sent to a menu that
  is still repainting are lost to its type-ahead flush. Before the
  first keypress the screen must hold still and is then sampled so
  self-repainting cells (clocks, countdowns, blinking indicators) are
  ignored throughout — without the quiet wait, a menu's own initial
  paint would be mistaken for animation and hide the very cells the
  tracking watches. When a keypress produces no classifiable movement
  the animation cells are re-learned and the bar is located directly
  by its attribute, so a keypress at the menu's edge or a briefly
  blinded diff recovers instead of failing. Enter
  is only sent after a fresh read confirms the highlight on the
  target row. Also available
  as
  `Machine.cursor_menu_select()`; `machine.vga_screen(qmp)` newly
  exposes the attribute bytes alongside the text rows.
- `create_hdd_image(filename, capacity)` creates a sparse qcow2 v3
  (`compat=1.1`, no preallocation) hard-disk image at the given path.
  Capacity accepts a qemu-img size string (`"2G"`, `"512M"`) or a
  positive integer MiB value. `find_qemu_img()` resolves `qemu-img`
  with the same search order as `find_qemu()`.
- `Machine.screen_text()` and `Machine.wait_text(pattern, timeout=60)`
  read and wait on the guest's VGA text screen directly from a `Machine`,
  so tasks and adapters can block until specific output (for example a
  boot menu) is displayed. The module-level `screen_text()` and
  `wait_text()` now delegate to these methods.
- `documents_dir()` publicly resolves the user's platform Documents
  folder (or `None` when it cannot be determined), so embedding
  projects can anchor their own state directories the same way Reliquary
  anchors its home.

### Removed

- The `boot-to-dos` CLI command. Wait for a prompt with `reliquary wait`.
  Programmatic boot readiness remains `AgentlessGuestExec.wait_ready()`.

### Changed

- Keyboard input and screen interaction moved to the platform-neutral
  machine layer, since they need only QMP and VGA text mode, not DOS:
  `char_keys()`, `send_keys()`, `send_text()`, `cursor_menu_select()`,
  `screen_text()`, and `wait_text()` now live in `reliquary.machine`, and
  `Machine` gains `send_keys()`, `send_text()`, and
  `cursor_menu_select()` methods. `interaction_agentless` retains only
  the DOS prompt-driven `AgentlessGuestExec` adapter. Package-level
  imports (`reliquary.send_text`, ...) are unchanged.
- Added an internal, runtime-checkable `GuestExec` protocol and isolated the
  QMP keyboard/VGA implementation as `AgentlessGuestExec`, with the DOS
  workflow and CLI consuming that adapter directly. The former
  `boot_to_dos()` and `run_command()` Python facades were removed; use
  `AgentlessGuestExec.wait_ready()` and `.execute()`.
- Exposed the identity-verified QMP session through `Machine.qmp()` for raw
  `cmd()` and `hmp()` access; interaction adapters now depend on `Machine`
  instead of opening QMP connections themselves.
- One validated `MachineConfig` now threads through the workflow and
  lifecycle layers. `start()`, `run_task()`, and `run_guest_program()` take a
  `MachineConfig`, versioned mapping, or JSON path as their sole machine
  settings input; `Runner.run()` passes its configuration through unchanged,
  and the QEMU launcher consumes that configuration instead of loose hardware
  arguments. The default QEMU argument vector is unchanged.
- The Python API now automatically discovers and loads `<home>/machine.json`
  when no explicit configuration is provided, matching CLI behavior. Explicit
  API values (passed as `MachineConfig`, mapping, or path) override the file
  values; `Runner` likewise loads the file when `config=None`.

### Added

- `--machine PATH` CLI argument for explicit machine configuration file selection; when omitted, the CLI automatically
  loads `<effective-home>/machine.json` if present, otherwise uses the default `MachineConfig()`. Explicit CLI
  overrides (`--platform`, `--qemu`, and raw QEMU arguments) apply on top of the loaded configuration; an omitted
  `--platform` leaves the file's platform unchanged, while `--platform dos` still overrides a non-DOS file value.
- `MachineConfig.from_file()` and `MachineConfig.from_mapping()` load a versioned JSON/mapping machine document
  (`version` must be `1`), normalize it immutably, resolve relative drive sources from the file directory or an
  explicit `base_dir`, and apply field overrides with deterministic merge rules for drives and options.
- Package-based `reliquary/` source layout split into home containment, declared media, ownership-safe lifecycle, generic
  machine interaction, DOS platform behavior, workflow orchestration, and CLI modules while preserving the existing
  root import and command-line interfaces.
- The complete DOS runner from the original implementation: DOS remains the default platform, while
  `MachineConfig(platform=...)` and `--platform` make the platform choice explicit. The reusable QEMU machine layer is
  shared; unimplemented non-DOS platform workflows fail explicitly instead of borrowing DOS assumptions.
- DOS 8.3 executable-name validation now belongs to the DOS platform module rather than generic workflow
  orchestration, so future guest-program workflows are not constrained by DOS naming rules.
- `Runner`/`MachineConfig`: the generic embedding surface for callers driving Reliquary as a runner.
  `Runner(home=None, config=None)` is a configured DOS test machine bound to one absolute home (the established
  process default when omitted), and
  `run(exe_path, args)` automatically ensures bootable media before performing the full `run_guest_program()`
  lifecycle. Provisioning is private; callers create distinct runners with distinct homes for concurrent runs, and
  per-home `vm.json` keeps VM ownership sound.
- Removed the `boot_floppy_image` and `boot_hdd_image` configuration shortcuts. Custom boot media uses the ordinary
  declared-drive inventory.
- `MachineConfig.drives` adds immutable configured drive specs using canonical logical slots plus `floppy`/`hdd`
  slot-zero aliases. A spec accepts a source path or `{source, options}` mapping; files mount as images, floppy and
  hard-disk directories mount as vvfat, and CD-ROM directories fail validation. Configured and home-directory media
  resolve into one inventory with slot conflicts rejected before launch.
- `MachineConfig.machine` maps directly to one QEMU `-machine` argument. A string selects the machine type; a mapping
  combines required `type` with immutable scalar properties and renders Boolean values as `on`/`off`. A raw
  `-machine` or `-M` in `qemu_args` conflicts with the structured field.
- `MachineConfig.memory` configures guest memory as a positive integer number of MiB, defaulting to 16 for DOS, 64
  for Win9x, and 256 for WinNT. It maps to one QEMU `-m` argument; an explicit value conflicts with raw `-m` in
  `qemu_args`, while a raw `-m` alone suppresses the platform default.
- The `drives/` directory under the home declares the whole machine by filename, with image content never
  interrogated. Image files `floppy[_<n>].<ext>` (slots 0–1, A: and B:), `hdd[_<n>].<ext>` (slots 0–3, the IDE bus),
  and `cdrom[_<n>].<ext>` (the IDE slots after the hard disks) mount as that medium; bare directories `floppy[_<n>]`
  and `hdd[_<n>]` mount as virtual FAT drives. An unindexed name means slot 0 (so `hdd.img` and `hdd_0.img` clash,
  as do all duplicate slots — fail closed). The idiomatic extension declares the image format: `*.img` and `*.iso`
  are taken as raw and pinned (avoiding QEMU's format-probing warning); any other extension (`hdd.qcow2`,
  `hdd.vmdk`, ...) is handed to QEMU to identify. Memory defaults to 16 MB and the boot order to a best guess from
  the declared media (slot-0 floppy image, else slot-0 hard-disk image, else cdrom); `-m` or `-boot` in the extra
  QEMU arguments overrides the corresponding default.
- The staged guest hard drive's letter is explicit configuration: `staged_drive` on `MachineConfig` and
  `run_guest_program()` (valid C–Z, normalized uppercase; default: match the declared machine, one letter per
  hard-disk slot before the staged drive, so C: on a floppy-boot machine and D: behind a slot-0 hard-disk image;
  letters below the default are rejected) declares where the staged vvfat hard disk appears in the guest — the drive
  Reliquary switches to for guest program runs. Staging targets the highest staged directory declared among the
  hard-disk slots, or `drives/hdd` created on demand.
- Explicit `home=` keyword on `download()`, `start()`, `stop()`, `run_guest_program()`, and the `drives_dir` path
  helper, overriding the process-global home per call. The
  existing `set_home()`/`--home` surface is unchanged.
- Installable `reliquary_tests` unit-test package, runnable with
  `python -m unittest -v reliquary_tests` so users and downstream packagers can verify an unpacked source distribution or
  installed wheel.
- Contributor guidelines covering development, verification, pull requests, and BSD-3-Clause contribution licensing.
- agentless DOS-under-QEMU automation harness — boot DOS headless, send keystrokes over QMP, scrape the 80x25 text
  screen from VGA memory, run commands with prompt-based completion detection, take screenshots, stage guest media
  via vvfat, and run guest programs end to end
  (`run_guest_program`, returning the program's redirected output).
- Visible manual VM sessions with `reliquary start --display`: the command returns once QEMU is ready, leaves the DOS VM
  running for direct interaction, and `reliquary stop` closes it through the same ownership-verified lifecycle.
- Bring-your-own boot image: Reliquary boots whatever the user declares under `drives/`.
- Test-framework result parsing is out of scope: Reliquary hands back raw guest output, and interpreting it belongs to
  the caller.
- QEMU binary discovery: `RELIQUARY_QEMU_HOME` / `QEMU_HOME`, then PATH, then well-known install locations; `--qemu`
  overrides.
- Home directory (boot images, staged guest drives, screenshots) defaulting to `reliquary/` under the user's Documents
  folder (the Windows known Documents folder, `~/Documents` on macOS, `xdg-user-dir DOCUMENTS` on Linux/BSD), falling
  back to `~/reliquary` when no Documents folder can be determined; override with `RELIQUARY_HOME`, `--home`, or
  `set_home()`.
- Native PNG screendump on QEMU >= 7.1 with a zero-dependency PPM-to-PNG fallback for older QEMU.
- Automatic QMP port selection with the selected port returned by
  `start()`, active-VM metadata under the Reliquary home for separate CLI invocations, and unique-name verification
  before any VM is controlled.
- DOS startup commands such as switching to C: use the ordinary
  `AgentlessGuestExec.execute()` interface rather than special boot options.
- Screenshot names are constrained to filenames so captured images cannot be written outside the Reliquary home.
- The installable test suite uses Python 3.9-compatible syntax, matching the package's declared minimum version.
