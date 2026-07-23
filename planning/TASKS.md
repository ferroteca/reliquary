<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# TASKS

Small to-do tasks. Large tasks belong in the roadmap; the
adjudicated design-decision records live in
[DECISIONS.md](DECISIONS.md). Completed milestone task-breakdowns
are pruned once the milestone lands — the record survives in git
history, DECISIONS.md, and the ROADMAP milestone notes (the
milestone-4 and milestone-6 breakdowns were pruned 2026-07-23).

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

Use case in planning/USE-CASES.md; design in
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
  run-events; the USE-CASES feedback split, 2026-07-21, names
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
  design round): folded into the COMPOSED BLUEPRINT MODEL (DECISIONS.md;
  worked design planning/design/blueprint-model.md). Cache stays
  name-keyed (content addressing declined); the authored surface
  unifies into one `.rlqb` blueprint of composable components
  (machine/media/source/archive), `.rlqm` retiring. The
  spec/schema/codex/example/code realignment enumerated in the
  worked design is the milestone-scale implementation follow-on.
- Media lifecycle commands (`list-media`, `delete-media`, and any
  further definition-level verbs) need careful planning before
  the surface hardens: one media definition (`.rlqm`) can define
  several items (archive form). Open questions to adjudicate and
  record in DECISIONS.md / media-spec / cli.md — what does the
  command noun name (item vs definition stem)? does
  `delete-media` remove the whole file, edit items out, or refuse
  when siblings remain? how should `list-media` present file vs
  item identity (and multi-item provenance)? `seed-media` already
  seeds by item name and copies the whole definition — keep or
  revisit that invariant together with delete/list. The current
  provisional twins (item-name delete of the owning file; list of
  item names) are placeholders pending this round, not settled
  design.

## Wishlist

- `download-media` command (owner request, 2026-07-22; shape refined
  2026-07-23 for the composed model): `rlq download-media
  https://freedos.org/downloads/FreeDOS14.zip` downloads the file
  into `cache/archives/` (a non-archive payload into `cache/media/`),
  computes its sha256, and scaffolds a standalone `.rlqb` blueprint
  into the home library carrying the url + sha256 — an `archive`
  component when the payload is a container, a `source`/`media`
  otherwise. It is smart enough to treat an archive as an archive, so
  the `-media` suffix is a slight misnomer in the container case —
  accepted for family consistency with `extract-media`. A home-mode
  convenience: it warms the cache and writes the committed-source
  stub so the user need not hand-author it and then `fetch`. Open
  shape under the composed model: the archive's members can't be
  inferred, so the stub names the archive and the user adds the
  extraction tree (with `extract-media`); stem-default naming from
  the URL filename; a `--local <file>` variant for non-downloadable
  payloads; CLI+API parity (a twin returning the written blueprint
  path).
- `extract-media` command (owner request, 2026-07-23) — the
  incremental companion to `download-media`: `rlq extract-media
  --archive FreeDOS14 FreeDOS14-LiveCD.zip` extracts the member from
  the named archive,
  computes its sha256, and records it against the archive by
  **appending a `members` node** (member path + sha256) to the
  existing archive blueprint's recursive tree (the leaning option)
  rather than writing a separate file. A member that is itself an
  archive becomes another node to drill into (`extract` it again); a
  payload member becomes a leaf media extracted to `cache/media/`. So
  a nested source is hand-authored by walking down it one
  `extract-media` at a time, the recursive archive tree
  (blueprint-model.md) growing
  in place. Open: new-file vs append-to-existing (lean append);
  leaf-vs-node selection (member is itself a container → node, else
  leaf).
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
- CLI clean, beyond the settled clean-archives / clean-media
  invariants: delete completely unreferenced media? all
  downloads? unreferenced only? (machine-cache cleaning is an
  open decision in ROADMAP "Decisions still needed")
