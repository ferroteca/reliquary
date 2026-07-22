<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# TASKS

Small to-do tasks. Large tasks belong in the roadmap; the
adjudicated design-decision records live in
[DECISIONS.md](DECISIONS.md).

## Implementation realignment (ROADMAP milestone 4 — the next work)

Realign the implementation with the redesigned script language
and the July 2026 decisions (DECISIONS.md).
planning/design/script-spec.md is the source of truth (full
typed EBNF) with
planning/design/script-examples/design-install.rlqs the
reference script; ROADMAP milestone 4 owns this work, and no
later milestone starts before it lands. No backward
compatibility: the old surface is deleted entirely, not
bridged. Work items:

- retarget script.py to the node grammar (the parser should
  shrink: colon, comma, expect, ->, and regex-keyword handling
  all disappear)
- retarget script_runner.py: failure diagnostics name the
  expired clock and its source scope; check-script reports the
  resolved timing plan; run records move to the runs/<n>/
  layout (script_runner.py writes the superseded
  <timestamp>-<run_id>/ layout until milestone 7, run records)
- convert the builtin scripts and planning/examples/ scripts to
  the new surface
- update every doc that quotes script syntax (README,
  planning/examples/README); docs/ and docs/cli-reference.md
  follow the CLI renames
- the static-conformance fixture corpus (valid and invalid
  documents), run against both the parsers and the authored
  JSON Schemas (DECISIONS.md, the schema round)
- CLI/API renames under the twin-name identity rule
  (DECISIONS.md, CLI queue item 14): create_from_blueprint →
  create_machine; machines.start/stop/destroy → start_machine /
  stop_machine / destroy_machine (lifecycle.py's legacy
  start_machine(config) collision dies with the root-home
  model); the cli.py SUPPRESS flag-position workaround retires
- the error taxonomy under parity (ROADMAP milestone 7):
  ReliquaryError the root; StaticError(2) / PreflightError(3) /
  RunFailure(4) / RunCancelled(5)
- authored-asset residency (ROADMAP milestone 5): the resolution
  module (--assets / --assets-only), the extension renames
  (.rlqb / .rlqm), the builtins/ → codex/ package-dir rename and
  the codex index, the state blueprint-source field, selection
  scoping, and embedded-install targeting
- shared JSONC reader for authored documents (blueprints,
  standalone media definitions): RFC 8259 + // and /* */
  comments + trailing commas, nothing more (no JSON5 features);
  string-aware tokenizer, comments replaced by spaces so error
  line/col survive; JSON islands in scripts and every
  machine-written file stay strict JSON (user properties speak
  their own line format)
- new media definition surface: definition-level description /
  notes / redistributable-under (the built-in URL
  licensing-assertion field), archive-level local-path;
  sourceless definitions fail resolution with the
  edit-the-definition error
- CLI fetch/clean commands + API parity: fetch_media(script=),
  clean_downloads(), clean_media()
- codex: teaching comments at blueprint seams once the JSONC
  reader lands
- the hostdir drive content source (vvfat on the QEMU adapter)
- user.properties and the property command family (ROADMAP
  milestone 6)

## Language

- residual language problems catalogued in
  planning/design/script-examples/*.rlqs (see its README) —
  best-guess priority, fix-cost order, NOT validated against
  real authoring pain; reorder freely once we've actually
  written/debugged scripts under this surface:
  1. [08] reserve the small closed vocabularies (key names,
     drive slots) globally so they can't shadow phase/artifact
     names — mechanical, no spec redesign, also closes most of
     [01]'s asymmetry
  2. [06] default a single-item media block's label to its item
     name; warn when an @-reference doesn't match any known item
  - [03], [05], [07] — provisionally leave as documented
    tradeoffs, not bugs: boundary tax (guest-text escaping) or
    placement-equals-scope consequences, where a "fix" mostly
    just relocates the mush rather than removing it
  - [01], [02], [04], [09] are resolved (DECISIONS.md: milestone
    zero and the observation-channel decisions); their files are
    regression notes
  - note: several of these are the procedural/declarative seam
    showing through the syntax — see "Primary language goals"
    (G1–G7) and "Procedural and declarative" in ./ROADMAP.md
    before proposing fixes, and judge any fix against the goals
    it costs rather than in isolation
- the full Reason-blockquote editorial sweep of script-spec.md
  remains deliberately open (may trail realignment); the
  error-id INDEX is deferred to beta
- resume the spec-audit workflow (wf_1a266a6b-ff8): the
  AHK/Python failure-catalog studies are complete — imports
  recorded in DECISIONS.md — but their spec audits hit the
  session limit

## U6 authoring recorder

Use case in planning/USE-CASES.md; design in
planning/design/recorder.md. Work items, in rough
dependency order:

- reliquary-owned console viewer over the vnc control plane
  (recording prerequisite: backend display-window input is
  invisible to reliquary)
- text-mode recorder first (no new language surface: waits from
  VGA scrapes, type/press actions, generated-comment
  uncertainty flags)
- runner run-to-point / breakpoint / human-takeover machinery
  (also the failure report's "take over from here" suggested
  next command)
- round-trip: fragment emission anchored by playback position;
  opt-in surgical apply at the anchor (never regenerate, never
  text-merge)
- landmark catalog shape: decided (DECISIONS.md, the wrinkle
  round; planning/design/landmarks.md) — implementation rides
  the asset spec work
- run-events: handover event kinds (script/human control
  passing); a capture session is one run record with mixed
  drivers
- CLI record command family + API twins land together (parity)

## Watches (re-ask as these harden)

- live-run progress surface (G4 during the run — ties to
  run-events; the USE-CASES feedback split, 2026-07-21, names
  the demand)
- GUI/landmark assets forming a new authored artifact class
  (hardened 2026-07-21: .rlql is the fourth authored extension —
  the INTERFACES listing is due at the asset-spec/realignment
  pass)
- published JSON Schemas elevating reliquary-machine.json into a
  public contract (the blueprint and media-definition schemas
  are authored — DECISIONS.md; the state schema and its
  public-contract elevation stay with milestone 5)
- the adapter API becoming world-facing
  (planning/design/backend-adapter.md is INTERNAL by decision,
  owner 2026-07-21 — a real third-party adapter story elevates
  it into the INTERFACES inventory through the interface-change
  rule, never by drift)

## Wishlist

- allow specifying the cache location outside the home dir
- 'list-blueprints' should announce the blueprints directory on
  its top line (instead of the home-dir announcement)
- new command diff-blueprint <name>: diff the user blueprint
  against the codex blueprint of the same name
- CLI, from cli help: --version should be `version` with an
  undocumented --version/-v alias; -h should be `help` with
  undocumented -h/--help aliases
- 'reliquary -h' should reflect the command as "reliquary",
  'rlq -h' otherwise
- --qemu → --qemu-home
- CLI help: run-script's text says little more than "runs a
  script on a machine"
- an 'inventory' report: every item in the home and cache dirs
  itemized in one way or another (backend implementation files
  ignored — just the presence of a machine is noticed):
  - orphaned listed first (because either you *really* want to
    keep it, or you really *should* delete it): media
    (definitions, not cached payloads), scripts
  - blueprints: materialized (online machines, offline
    machines), unmaterialized
  - media: referenced
  - scripts: orphaned (listed first??), referenced
- README, blueprints and machines: give several clear examples
  to illustrate the concepts — e.g. a 1 MB MS-DOS blueprint;
  QEMU machine #0; QEMU machine #1; QEMU machine #3 with a
  specific floppy image mounted; QEMU machine #4 with 16 MB of
  memory and a specific cdrom mounted
- CLI clean, beyond the settled clean-downloads / clean-media
  invariants: delete completely unreferenced media? all
  downloads? unreferenced only? (machine-cache cleaning is an
  open decision in ROADMAP "Decisions still needed")
