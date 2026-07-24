<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# TASKS

The work queue — and the parking place for non-GitHub issues
(the tracker:
<https://github.com/ferroteca/reliquary/issues>). Tasks flow
from the roadmap and from issues; small one-offs really just
are issues, and a small, obvious, needed fix goes directly to
tasks. A task is either scheduled for the sprint or
backlogged — the [backlog](#backlog) holds the small, obvious
items that just haven't met the bar for scheduling. In theory
every issue points to the use case or principle it serves —
small ones may simply be deemed obvious; principles
([PRINCIPLES.md](../PRINCIPLES.md)) drive tasks just as use cases
do — and an issue can
easily trigger a use-case or principle change, drafted as a
proposal in [USE-CASE-PROPOSALS.md](USE-CASE-PROPOSALS.md) or
[PRINCIPLE-PROPOSALS.md](PRINCIPLE-PROPOSALS.md) through the
interface-change rule (INTERFACES.md), which weighs the two
alike. Large work belongs in
the roadmap; a milestone item is picked up by translating it
into a sprint tasklist here. The adjudicated design-decision
records live in
[DECISIONS.md](DECISIONS.md). Completed milestone
task-breakdowns are pruned once the milestone lands — the
record survives in git history, DECISIONS.md, and the ROADMAP
milestone notes (the milestone-4 and milestone-6 breakdowns
were pruned 2026-07-23).

## Planning docs

- sweep ROADMAP items for demand citations: every item names
  the U-number — in force or proposed — or P-number that
  demands it (the traceability rule, ROADMAP preamble /
  USE-CASE-PROPOSALS.md / PRINCIPLES.md, owner 2026-07-23).
  Many sections already cite U-numbers; the sweep fills the
  gaps.
- retrofit supports onto DECISIONS.md entries D1–D21: each
  names the use cases (U), principles (P), or goals (G) it
  supports (the numbering round, D23, owner 2026-07-23). New
  entries carry supports from the start. D22 is done —
  pulled forward 2026-07-23 by the milestone-7 governing-input
  audit, which found the milestone's whole justification
  sitting in retired D17.

## Milestone 7 — the composed blueprint model

The sprint tasklist, translated from ROADMAP milestone 7 (owner,
2026-07-23). The roadmap holds the *what*; this holds the
**landing order**, which is not the deliverable numbering — the
deliverables are a list of work, and three of them cannot land
apart from each other. Read the roadmap's deliverable text for
each item's substance; only the sequencing argument lives here.

**The constraint that shapes everything:** `resolve.py` is built
on the four kind buckets, `acquire.py` on `Source`/`Archive`, and
the codex blueprints, the example blueprint, and the conformance
fixtures are all authored in the retired shape — `bare-machine`
does not merely need editing, it becomes *invalid* (an untyped
lone object is a media now, D22). The moment `document.py`'s root
changes, every one of them fails together. So the format core is
**one landing**, and stages 0–2 exist to make it as small as it
can honestly be.

- **S0 — the launching-point renames — DONE** (deliverable 8's rename
  half, D21). The codex entries went generic — blueprints
  `freedos` and `openbsd`, media `freedos-livecd` and
  `openbsd-installer`, scripts named for the flow they drive —
  with the mentions across script-spec, machine-blueprint.md,
  cli.md, docs and tests following. Purely mechanical,
  independent of the format, green throughout — and doing it
  first meant S3 re-authors those files without also renaming
  them. (The exact before/after is in D21 and the CHANGELOG;
  this bullet deliberately does not restate the old names,
  having been caught by its own sweep once.)
- **S1 — blueprint-model.md rewritten — DONE** (deliverable 1). Docs
  only. Folds D22, D24, D26, D27 into one normative document,
  replacing the superseded first-round shape its banner
  disclaims.
- **S2 — the conformance corpus re-authored — DONE** (deliverable 6's
  corpus half) against S1's spec, staged in a directory the
  corpus test does not yet walk so the suite stays green. This
  is the parser's acceptance test, written before the parser.
  Cover at least: the typed root array and the lone-object
  sugar; an untyped lone object reading as media; `children`
  batch and child-side `parent`; inline and anonymous media at
  drives; stem-derived names, the repair warning, and the
  unrepairable failure; identity-dedup versus collision; every
  `location` string form and its object desugaring; and the
  reference-grammar refusals — the closed vocabularies, and an
  operator-bearing `${…}` body, which is P14's acceptance test.
- **S3 — the format core, one landing — DONE** (deliverables 2 and 3,
  the corpus wired, the schema, and deliverable 8's re-authoring
  half). `document.py` rewritten; `resolve.py` collapsed from
  four kind buckets to the one catalog with containment
  resolution and two-phase validation; `acquire.py` on
  parent/children with the roster gate; `machines.py` giving the
  anonymous blank its slot name; both codex blueprints and the
  example blueprint re-authored with explicit `type`; the corpus
  moved into place and the old fixtures deleted; the one
  two-variant schema replacing the two (it cannot lag — the
  corpus checks both); `.rlqm` retired and `test_old_surface_purge`
  extended to it and to `sources`/`archives`; and
  test_document / test_resolve / test_acquire / test_assets /
  test_library brought over. **Gate:** the full suite plus the
  FreeDOS install integration run, which is the milestone's own
  "done when" for this half.
- **S4 — the cache rework and its command family — DONE** (deliverable
  4). The single name-keyed `cache/media/` with `cache/archives/`
  retired, the identity ledger, the deterministic preflight
  identity check feeding the on-mismatch contract, and
  `clean-media` / `clean-media <name>` / `prune-media` /
  `add-media` with their API twins. Separable from S3 and the
  milestone's one piece of new capability. **Gate:**
  `prune-media` after the install leaves exactly the attachment
  closure.
- **S5 — the remaining spec realignment — DONE** (deliverable 7).
  These documents legitimately follow the code, INTERFACES.md and
  the AGENTS module paragraph included. Realigned by **dividing the
  job**, not by updating four descriptions of one format:
  blueprint-model.md is the normative model, machine-blueprint.md
  the guide, its reference the per-field detail, media-spec.md
  acquisition and the cache, the cookbook recipes. Restated model
  prose was deleted rather than corrected — D32 is what the
  alternative costs. `test_documented_examples.py` now runs every
  documented example through the parser and the schema, so the
  prose cannot drift from the format silently again.

Deliverable 5 needs no stage: it landed with milestone 6.

## Future implementation hints

- The error taxonomy under parity (ROADMAP milestone 9):
  `ReliquaryError` the root; `StaticError(2)` / `PreflightError(3)`
  / `RunFailure(4)` / `RunCancelled(5)`.
- `user.properties` and the property command family (ROADMAP
  milestone 8): use the `keyring` package for the protected host
  credential store rather than hand-rolling Windows Credential
  Manager / macOS Keychain / Secret Service backends; its
  `(service, username)` model takes the spec's scoping directly —
  the properties-file path as the service, the property name as
  the username.

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
  2. [06]'s remaining half: warn when an `@`-reference matches no
     known item (the label/item split itself is gone with the
     media block — DECISIONS.md, no JSON in scripts)
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

Use case U6 in planning/USE-CASE-PROPOSALS.md (accepted,
awaiting delivery — moved 2026-07-23); design in
planning/design/recorder.md. Work items, in rough
dependency order:

- Reliquary-owned console viewer over the vnc control plane
  (recording prerequisite: backend display-window input is
  invisible to Reliquary)
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
  run-events; the feedback split, PRINCIPLES.md P5, names
  the demand)
- GUI/landmark assets forming a new authored artifact class
  (hardened 2026-07-21: .rlql is the fourth authored extension —
  the INTERFACES listing is due at the asset-spec/realignment
  pass)
- published JSON Schemas elevating `reliquary-machine.json` into a
  public contract (the blueprint and media-definition schemas
  are authored — DECISIONS.md; the state schema and its
  public-contract elevation stay with milestone 6)
- the adapter API becoming world-facing
  (planning/design/backend-adapter.md is INTERNAL by decision,
  owner 2026-07-21 — a real third-party adapter story elevates
  it into the INTERFACES inventory through the interface-change
  rule, never by drift)

## Design

- Media residency vs the download cache AND composable authored
  specs — RESOLVED together (owner, 2026-07-23, the media/composition
  design round), then REVISED same day by the blueprint revision
  round (both in DECISIONS.md; ROADMAP milestone 7 is the
  retargeted implementation): two spec types (machine / media —
  archive absorbed as the container reading), a flat typed root
  array, one schemed `location` field, no source component, no
  composition (identity-dedup instead), and the single name-keyed
  `cache/media/` with the identity ledger (content addressing
  declined in both rounds). blueprint-model.md is now the
  worked design of the revised model, rewritten at milestone 7's
  S1 and normative in the decision entries' place.
- Media lifecycle commands — RESOLVED (owner, 2026-07-23,
  DECISIONS.md D30, run as milestone 7's decide-first round):
  the noun in every media verb is the media, never the owning
  file; `delete-media` and `seed-media` are deleted outright
  (P9 — a command that can only fail and a no-op that "still
  resolves" are the shim the rule names); `list-media` keeps
  its plain name list with owning file, containment parent and
  cache state behind `--verbose`, a dedup'd media showing every
  declaring file on its one row, anonymous inline blanks never
  listed. Component-removal tooling is parked, arriving as its
  own named thing under the interface-change rule if a real
  case appears.

## Backlog

The task backlog — small, obvious, just hasn't met the bar for
scheduling (the section formerly named Wishlist). Parked
non-GitHub issues land here.

- validate declared control-planes at materialization: the
  parser accepts `vnc` / `serial-console` / `guest-agent` as
  `control-planes` values, but nothing refuses them at create
  or start — a blueprint declaring an unimplemented plane is
  accepted silently, against P11 (capability gaps fail closed
  naming themselves). Refuse anything but `agentless-display`
  until the plane exists (found by the P1–P12 delivery pass,
  2026-07-23).

- `download-media` command (owner request, 2026-07-22; shape to
  re-derive under the revised model — milestone 7's `add-media`
  covers its cache-warming half): `rlq download-media
  https://freedos.org/downloads/FreeDOS14.zip` downloads the file
  into `cache/media/`,
  computes its sha256, and scaffolds a standalone `.rlqb` into
  the home library carrying the url + sha256 — a media spec,
  with `children` left for the user to add when the payload is a
  container. A home-mode
  convenience: it warms the cache and writes the committed-source
  stub so the user need not hand-author it and then `fetch`. Open
  shape: members can't be
  inferred, so the stub stops at the container and the user adds
  the extraction tree (with `extract-media`); stem-default naming
  from
  the URL filename; a `--local <file>` variant for
  non-downloadable
  payloads (overlaps `add-media` — reconcile when picked up);
  CLI+API parity (a twin returning the written blueprint
  path).
- `extract-media` command (owner request, 2026-07-23; re-derive
  under the revised model) — the
  incremental companion to `download-media`: `rlq extract-media
  --parent FreeDOS14 FreeDOS14-LiveCD.zip` extracts the child
  from
  the named media,
  computes its sha256, and records it by
  **appending a child** (path + sha256) to the
  existing media spec's `children` (the leaning option)
  rather than writing a separate file — or as a flat
  `${media:…}`-located spec; reconcile when picked up. A child
  that is itself a
  container becomes another node to drill into (`extract` it
  again); a
  payload child is extracted to `cache/media/`. So
  a nested source is hand-authored by walking down it one
  `extract-media` at a time, the `children` tree growing
  in place. Open: new-file vs append-to-existing (lean append);
  node shape (child is itself a container → node with its own
  `children`, else leaf).
- new command diff-blueprint <name>: diff the user blueprint
  against the codex blueprint of the same name
- CLI, from cli help: --version should be `version` with an
  undocumented --version/-v alias; -h should be `help` with
  undocumented -h/--help aliases
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
- CLI clean — RESOLVED by the blueprint revision round
  (DECISIONS.md, 2026-07-23): `clean-media` (blunt + targeted
  eviction) and `prune-media` (attachment-closure prune of
  unneeded entries) land at milestone 7; `clean-archives`
  retires with the single cache dir. Machine-cache cleaning
  remains the open decision in ROADMAP "Decisions still
  needed".
