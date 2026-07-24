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
milestone notes (the milestone-4, -6, and -7 breakdowns were
pruned 2026-07-23).

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

## Milestone 8 — script properties (complete)

All five stages landed (T1–T5). This breakdown is kept until the
milestone-8 record is folded into the ROADMAP note and pruned like
milestones 4/6/7; the stage markers below are the landing record.

The sprint tasklist, translated from ROADMAP milestone 8. The
roadmap holds the *what* and
[script-properties.md](design/script-properties.md) the
normative detail; this holds the **landing order**, which is not
the deliverable numbering. Only the sequencing argument lives
here.

**What shapes this one:** nothing must land as one piece — the
milestone is new capability over a stub (`properties.py` today
is a JSON file with a `set_property(secret=)` parameter that
does nothing with it), so each stage is independently green.
What does bind the order is that two decisions are expensive to
retrofit: the **credential scope key** (the properties file's
absolute path) and the **rank of a source**. Both are cheap to
get right the first time and silently corrupting to change
later — an orphaned credential nobody can name, or a bundle that
resolves differently than it did last release.

- **T1 — the properties file — DONE.** Deliverable 1. Replace the JSON
  stub with the line-based format: `key = value`, `#` full-line
  comments, blank lines, the `@secret` marker and `@@` literal
  escape, dot-separated letter-initial segments with the `rlq` /
  `reliquary` namespaces refused, comment- and order-preserving
  surgical edits, atomic writes. Invalid files report path and
  line and are never partly rewritten. Pure host-side and fully
  unit-testable — no credential store, no binding. **Gate:** a
  file with comments, blank lines, and a deliberate ordering
  survives a set and an unset with everything but the named line
  untouched.
- **T2 — the credential store and the command family — DONE.**
  Deliverables 2 and 3, **plus `--properties <path>` pulled
  forward from deliverable 4**. Use the `keyring` package rather
  than hand-rolling Credential Manager / Keychain / Secret
  Service; its `(service, username)` model takes the spec's
  scoping directly — properties-file path as service, property
  name as username — behind a thin Reliquary-owned seam, so an
  absent or unusable store fails closed and there is never a
  plaintext fallback. The four commands with their secret rules
  (no-echo prompt on a tty, stdin to EOF otherwise, empty
  rejected; get and list never revealing; prefix filtering by
  dotted descendants, not string prefix; a kind change requiring
  `unset-property` first), the fail-safe update order
  (credential before marker, marker before credential) and
  orphan reporting. API twins in the same commit (P6), including
  the named divergence — `set_property` takes a secret's value
  in-process, because argv is what the CLI's entry channels
  exist to avoid. **Why `--properties` lands here and not in
  T4:** credentials scope by the selected file's absolute path,
  so the scoping rule is untestable without it, and changing a
  scope key after credentials exist orphans every one of them.
  **Gate:** the milestone's own — secrets round-trip with no
  secret material in the file, and an interrupted update can
  leave neither a plaintext value nor a marker whose credential
  was reported bound but is absent.
- **T3 — the binding pipeline — DONE.** Deliverable 4: the flattened
  order minus derivation — flag > parameter > env > file > ask.
  It lands where `script_runner.py` today raises "property
  binding arrives with the property family", and reaches
  preflight (every failure before a media materializes or a
  machine starts), `check-script` (each key's supplying source
  named, never its value), and the runtime secret rules
  (transcripts record key and source only; diagnostics redact;
  failure screenshots suppressed for the rest of a run after
  secret entry). Env mangling with the fail-closed collision
  preflight over the keys a run actually consults; blueprint
  `parameters` direct and redirect (`document.py` already parses
  both). **Gate:** one script bound from each tier in turn, each
  naming its source, and a noninteractive miss failing in
  preflight before the machine is created.
- **T4 — the declared derivation rank — DONE.** Deliverable 5 (D20).
  `default=` candidates in declaration order, first-answerable
  wins, with static cycle detection, dead literal candidates and
  any secret involvement as static errors, and the `rlq.*` facts
  (`host.username` login-normalized, `host.full-name`,
  `rlq.env.<NAME>`; an empty fact is unanswerable by design).
  The grammar already parses the modifier — this is semantics.
  Deliberately after T3: it is a one-rank insertion between file
  and ask, which is the model's own claim (D19 — new tiers land
  at fixed ranks) getting its first real test. **Gate:** a
  derivation-backed key binds with no ask, naming its winning
  candidate as the supplying source.
- **T5 — `${key}` location references — DONE.** Deliverable 6. The
  grammar landed at milestone 7 parsing-only, failing closed
  naming properties; now it binds through T3's order at `create`
  / `apply`, with the resolved location recorded in the state
  and never re-adopted at `start`, no chaining (a resolved value
  that is itself a reference fails closed), and noninteractive
  misses naming both the media and the key. Last because it is
  the only consumer outside scripts and wants the order settled
  under it. **Gate:** a media whose `location` is `${key}`
  materializes, with the resolved location in the machine state.

Cross-cutting, every stage: docs and CHANGELOG land with the
code (AGENTS "Documentation maintenance"), and
script-properties.md's status banner — *"None of it is
implemented yet"* — comes off as its sections land. A banner
that outlives the code it disclaims is the wrong-instruction
failure DECISIONS.md's preamble names.

## Milestone 9 — run records

The sprint tasklist, translated from ROADMAP milestone 9 (the
run-records milestone as narrowed by D35 — asynchronous runs
deferred to the backlog for lack of a use case, drafted as U19).
Normative detail lives in script-spec.md "Failure, runs, and
transcripts" / "The run event stream" and api.md (the error
taxonomy); this holds the **landing order**.

**What shapes this one:** the stream is the source of truth and
everything else renders it, so it lands first; the rest are
followers. Two things bind the order beyond that. The **record
layout is a world-facing contract** (`runs/<n>/`, the stream's
shape), and the old `<timestamp>-<id>/` layout dies with it — a
break to make once (P9, no compatibility). And the **error
taxonomy folds milestone 8's debt**: five orphan classes
(`PropertiesError`, `PropertyBindingError`, `CredentialError`,
`ScriptParseError`, `ScriptRuntimeError`) with no common root and
a CLI that collapses everything but a parse error to exit 1; the
taxonomy re-homes them and remaps the exit arms, and the stream's
terminal events *are* its outcome classes, so it lands early
rather than last.

- **T1 — the live stream and record layout.** Deliverable 1.
  `run-events.jsonl` written live (append + flush per event,
  first preflight event to terminal event), the `runs/<n>/`
  record layout with machine-scoped monotonic numbering (the
  `<timestamp>-<run_id>/` layout and the `output/` subdir die),
  and `transcript.txt` rewritten as a pure renderer of the
  stream. A record without a terminal event is an incomplete run
  (the cross-process crashed-run rule waits on async).
  **Gate:** a run writes a growing `run-events.jsonl` under
  `runs/<n>/`, the transcript derives from it line for line, and
  a second run numbers `<n+1>`.
- **T2 — the error taxonomy and exit codes.** Deliverable 3.
  `ReliquaryError` the root every deliberate error subclasses,
  `StaticError` (2) / `PreflightError` (3) / `RunFailure` (4) /
  `RunCancelled` (5) and their exit-code mapping, the milestone-8
  classes folded under the root, and the CLI's except-arms
  remapped from the current everything-is-1 collapse. Foreground
  Ctrl-C writes the `cancelled` terminal event and exits 5.
  Early, because the terminal events are these outcomes and the
  exit codes must settle before renderers assert on them.
  **Gate:** a static failure exits 2, a noninteractive property
  miss exits 3 (not 1 as today), a run failure exits 4, Ctrl-C
  exits 5, and `except ReliquaryError` catches all four.
- **T3 — the `--progress` renderers.** Deliverable 2.
  `--progress (auto | pretty | plain | jsonl)` over the live
  stream on `run-script` and `fetch-media`, jsonl stdout purity
  (the terminal event last, diagnostics to stderr), the output
  discipline across every command, and the noninteractive
  no-prompt rule (a missing input under `plain`/`jsonl` is a
  PREFLIGHT ERROR before the machine starts). The feedback split
  (P5) delivered: pretty for a person, jsonl for a program,
  neither scraped from the other. **Gate:** one install rendered
  live in pretty and, rerun under jsonl, emitting the same stream
  as JSON lines with the terminal event last.
- **T4 — the record-management run verbs.** Deliverable 5.
  `list-runs`, `run status`, `run delete` and the API twins
  (`delete_run()`, and `run_script()` realigned to return what
  the CLI prints), the run number an ordinary positional
  defaulting to the latest (except `run delete`, which never
  defaults), the machine chosen by the ordinary selectors.
  **Gate:** `list-runs` shows a machine's records with their
  drivers, `run status <n>` reports one, and `run delete <n>`
  removes it while refusing an open one.
- **T5 — interaction runs.** Deliverable 4. `begin-run` /
  `end-run` (twins `begin_run` / `end_run`), every
  machine-targeting command appending the execution model's event
  kinds while a run is open, one open run per machine (a second
  `begin-run` or a `run-script` fails closed naming it),
  `end-run` closing with the neutral `ended` terminal event.
  Last, because it appends through the full record + event
  machinery the earlier stages build. **Gate:** a `begin-run` /
  primitives / `end-run` bracket records a primitive-driven
  session as one run record naming its driver, and a `run-script`
  against an open run fails closed.

Cross-cutting, every stage: CLI–API parity lands in the same
change (P6), and docs (README, `docs/api-reference.md`,
`docs/cli-reference.md`) and CHANGELOG land with the code
(AGENTS "Documentation maintenance").

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
