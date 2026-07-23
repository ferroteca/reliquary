<!--
SPDX-FileCopyrightText: 2026 Paul Galbraith
SPDX-License-Identifier: BSD-3-Clause
-->

# TASKS

Small to-do tasks. Large tasks belong in the roadmap; the
adjudicated design-decision records live in
[DECISIONS.md](DECISIONS.md).

## Implementation realignment (ROADMAP milestone 4 — complete)

Realign the implementation with the redesigned script language
and the July 2026 decisions (DECISIONS.md).
planning/design/script-spec.md is the source of truth (full
typed EBNF) with
reliquary/codex/scripts/freedos-1.4-plain-install.rlqs the
reference script; ROADMAP milestone 4 owned this work, and no
later milestone started before it landed. No backward
compatibility: the old surface is deleted entirely, not
bridged.

Numbered tasks, in dependency order — the spine is 1 → 2 →
3/4 → 5 → 6; task 9 runs parallel to the spine; 7/8 start once
the parser stack validates scripts; 10–12 close out:

1. Parser retarget, node grammar: rebuild script.py on the
   typed EBNF's three-production skeleton — every line a node
   of name, positional arguments, name=value properties, and
   an optional brace block; the lexer's five spellings
   ("..." guest text, /.../ regex, @name media references,
   $key / ${key} property references, bare words) plus #
   comments. Colon, comma, expect, ->, and regex-keyword
   handling all deleted — the parser should shrink.
2. Parser retarget, vocabulary and node signatures: phase
   (was state), goto (was ->), finish (was done), expect
   folded into the branching wait { on ... }, always for
   reactive handlers (on only in branching waits), set-boot
   (was boot), no <key> tokens (key names only after press);
   the colon-free noun-first headers with entry and the
   run-level deadline; per-node signature validation.
   LANDED as own-lexer + lark parser (owner, 2026-07-22 —
   DECISIONS.md): script_grammar.lark mirrors the normative
   EBNF, reliquary's tokenizer feeds it through a custom lark
   lexer so the lexical diagnostics stay authored, and
   script_parser.py's transformer checks per-node modifier
   signatures and builds the typed tree. The grammar stays
   permissive where an S-rule owns the diagnostic (S8's
   two-handler minimum, S9's phase purity, S11's terminators),
   so tasks 3-4 can cite ids and name the problem.
3. Static validation, shapes and observation channels: the
   two non-mixing script shapes; phases sequential or
   reactive, never hybrid; every sequential phase ends in
   goto/finish; the two-handler minimum in branching waits;
   the screen-default conditions (a bare string or regex the
   only screen spelling — screen= does not exist;
   machine=stopped the only machine spelling — no bare
   stopped); one condition per observation; unknown or
   wrong-kind channels are validation errors.
   LANDED as script_validation.py (owner, 2026-07-22): the
   rules the grammar deliberately does not carry, checked over
   the typed tree, each diagnostic naming the construct and
   citing its id — S3/S10 (the shapes, entry, goto targets), S5
   (unique phase names), S7 (one condition, known channel, right
   kind), S8 (the branching wait's shape and its one-level depth
   limit), S9 (sequential or reactive, on vs always), S11 (the
   terminating-statement rules). Two grammar consequences: a
   handler's condition became optional so `on machine=stopped`
   parses (the normative EBNF always allowed it — the channel is
   part of `condition`, not a modifier) and a bare word is
   admitted as a condition so S7 can name it (`wait stopped`).
   Non-timing modifiers on an observation are channels, not
   signature errors; the timing set stays the node's own.
4. Static validation, timing model: lexically scoped
   timeout/stable defaults (innermost wins), per-activation
   deadline budgets (fresh per phase entry; the header
   deadline backstops the run, and S12 requires one of a
   cyclable phase graph), and the placement matrix enforced as
   parse errors.
   LANDED as script_timing.py (owner, 2026-07-22): resolve()
   computes the plan up front — each observation's effective
   timeout with the scope that supplied it (innermost-wins:
   statement > branching wait > phase > header > built-in 60s),
   each phase's budget, the run's — so the runner is handed its
   bounds and check-script can report them without running
   anything. A branching wait is a real scope level: the
   observations inside its handler bodies inherit its timeout.
   Budgets resolve trivially because they are never inherited.
   The placement matrix stays in the node signatures (a parse
   error, per the task), but each timing rejection now gives its
   reason and cites S2; S5's positive durations and S12's cycle
   check (reachable phases only, naming the route) are in
   script_validation.py with the other S-rules.
5. Runner retarget: rebuild script_runner.py on the new
   graph — phase transitions, branching-wait dispatch,
   reactive run-to-completion dispatch with the
   once-per-episode rearm rule, the timing runtime honoring
   task 4's scoping. Run records keep the superseded
   <timestamp>-<run_id>/ layout (the runs/<n>/ move is
   milestone 8's, run records).
   LANDED (owner, 2026-07-22): script_runner.py rebuilt on the
   typed tree — the phase graph, branching-wait dispatch,
   reactive run-to-completion with the once-per-episode rearm,
   and the clocks read from the parse-time plan, so failures
   already name the expired clock and its source scope (task 6's
   first half falls out of the model). Consequences:
   - script.py is deleted, not bridged; parse_script and
     load_script moved onto the new stack in script_parser.py
     and the exports follow (State/ExpectBranch out,
     Phase/Handler/Property in). test_script.py went with it.
   - a sample reads every channel together, so a branching wait
     can mix screen and machine=stopped handlers; a sample whose
     session is gone IS the stopped observation, and it
     reconciles the machine phase.
   - sessions go through Machine.qmp(), so the runtime verifies
     VM identity (the old runner opened a raw Qmp(port)) and
     never holds a session while a statement list runs.
   - the engine takes an injected clock/sleep: the dispatch
     tests are deterministic and the suite no longer sleeps.
   - properties parse but do not bind: ${key} and insert $key
     raise a named runtime error until the property family
     (milestone 7).
   - NOT YET: the shipped codex and planning/examples scripts
     are old-surface and no longer parse — task 7.
6. Diagnostics and check-script: failure diagnostics name
   the expired clock and its source scope; check-script
   grows to report the resolved timing plan (each
   observation's effective timeout and source scope).
   LANDED (owner, 2026-07-22): the runner already named clocks
   (task 5); `check_script()` / `rlq check-script` now resolve a
   script read-only (home or builtin, no seeding), print
   `format_plan()` (defaults, phase budgets, every observation's
   timeout and source scope), and with a machine selector also
   run media-slot preflight. Static errors exit 2.
7. Convert the shipped scripts: the codex scripts
   (freedos-1.4-plain-install, freedos-1.4-verify) and
   planning/examples/scripts/ move to the new surface;
   planning/design/script-examples/design-install.rlqs
   retires into the converted codex scripts.
   LANDED (owner, 2026-07-22): all four scripts converted and
   parsing; design-install.rlqs deleted, and
   freedos-1.4-plain-install.rlqs IS the reference script now
   (spec status note, ROADMAP, the script-examples README).
   Two things the conversion caught:
   - library.py's insert-media text scan still expected the
     bare media name and captured `@name` with its sigil, so a
     seeded script no longer brought its definition. Fixed to
     match the `@` form only ($key names no static item), with
     a test.
   - the reference-script tests read design-install.rlqs from
     planning/, which is not packaged; they now resolve the
     builtin through reliquary.__file__, so they pass against an
     installed artifact too.
   The examples' install script needed a header deadline it
   never had: its cd-boot <-> partitioning cycle is exactly what
   S12 requires one for.
8. Confirm the portable key vocabulary (the one in-milestone
   confirmation — ROADMAP milestone 4): check the spec's
   closed press key-name set against what the converted
   scripts actually need; adjudicate any gap.
   LANDED (owner, 2026-07-22): the converted scripts need only
   `enter`, already in the published set, so no vocabulary
   change was needed. The confirmation exposed an enforcement
   gap instead: S14 said the set was checked statically, while
   the runner rejected unknown names only after execution began.
   `script_validation.py` now owns the portable set and rejects
   unknown names, bare printable characters, and malformed chords
   during parsing; chords retain their one-character member
   (`ctrl+c`). The QEMU runner now only translates the validated
   language names to backend spellings.
9. CLI/API renames under the twin-name identity rule
   (DECISIONS.md, CLI queue item 14): run-script,
   fetch-media, the seed- family, new-blueprint, import-vm
   --name, check-script, the dashed list-/search- forms, the
   property family noun-last; create_from_blueprint →
   create_machine; machines.start/stop/destroy →
   start_machine / stop_machine / destroy_machine
   (lifecycle.py's legacy start_machine(config) collision
   dies with the root-home model); id-only --machine
   selectors; uniform flag position (the cli.py SUPPRESS
   workaround retires).
   LANDED (2026-07-22): CLI commands and API twins share one
   name under the dash↔underscore transform; the guest-console
   family matches the script language; `--machine` is id-only
   and mutually exclusive with `--blueprint`; leading flags are
   rewritten onto the subparser so SUPPRESS is gone. Nested
   `list …` and the singular aliases are deleted. `clean-*`
   and the state ops (`insert-media` / `eject-media` /
   `set-boot-order`) land with their twins. search-* twins that
   have no implementation yet stay with later milestones.
10. Documentation sweep: every doc that quotes script syntax
    (README, planning/examples/README); docs/ and
    docs/cli-reference.md follow the CLI renames.
    LANDED (2026-07-22): planning/examples/README and the
    script-spec / media-spec / instance-model / api design pages
    quote `run-script` and the colon-free `machine` header;
    docs/ (cli-reference, api-reference, dos-automation,
    blueprint-guide) and README already follow the twin-name
    CLI. Released CHANGELOG history is left untouched.
11. Test realignment and the old-surface purge: the test
    suite retargeted to the new parser, runner, and command
    names, then a whole-tree sweep for surviving old-surface
    spellings (state, ->, done, expect, bare stopped, <key>
    tokens, boot, superseded command names) — none survive
    anywhere.
    LANDED (2026-07-22): tests speak the twin-name CLI and the
    redesigned surface; `test_old_surface_purge.py` enforces the
    live-tree sweep (package, tests, docs, README, AGENTS,
    planning/examples, shipped codex scripts) — superseded API
    names and CLI commands are absent, old-surface samples fail
    to parse, and forbidden spellings do not appear outside the
    intentional negative-test fixtures. Released CHANGELOG,
    DECISIONS, completed ROADMAP notes, and
    planning/design/script-examples regression notes remain
    historical and are outside the live sweep.
12. Milestone gate: the FreeDOS install and verify scripts
    run end to end on the new surface and check-script
    reports the timing plan (ROADMAP milestone 4's "Done
    when").
    LANDED (2026-07-22): `check-script` prints the timing plan
    for the FreeDOS install/verify scripts; `run-script install
    --blueprint freedos-1.4-plain` and `run-script verify` both
    finished `result: ok` with machine phase `ready` on a
    scratch home. Guest `fdapm poweroff` samples treat
    lifecycle's "no longer reachable" RuntimeError as
    `machine=stopped` (script_runner `_read`), so shutdown
    completes after QEMU exits.

Realignment items riding later milestones (kept here so the
umbrella list stays complete; not milestone 4):

- the static-conformance fixture corpus (ROADMAP milestone 6,
  deliverable 6): valid and invalid documents, run against
  both the parsers and the authored JSON Schemas
  (DECISIONS.md, the schema round)
- the error taxonomy under parity (ROADMAP milestone 8):
  ReliquaryError the root; StaticError(2) / PreflightError(3) /
  RunFailure(4) / RunCancelled(5)
- authored-asset residency (ROADMAP milestone 6): the resolution
  module (--assets / --assets-only), the extension renames
  (.rlqb / .rlqm), the builtins/ → codex/ package-dir rename and
  the codex index, the state blueprint-source field, and
  selection scoping
- shared JSONC reader for authored documents (ROADMAP
  milestone 6) — blueprints, standalone media definitions:
  RFC 8259 + // and /* */
  comments + trailing commas, nothing more (no JSON5 features);
  string-aware tokenizer, comments replaced by spaces so error
  line/col survive; every machine-written file stays strict JSON
  (user properties speak their own line format); survey PyPI first, but the published
  JSONC/JSON5 readers looked either too permissive (JSON5
  features the spec excludes) or position-losing, and the
  comments-become-spaces rule that keeps error line/col exact is
  the unusual requirement to check them against
- new media definition surface (ROADMAP milestone 6):
  definition-level description /
  notes / redistributable-under (the built-in URL
  licensing-assertion field), archive-level local-path;
  sourceless definitions fail resolution with the
  edit-the-definition error
- CLI fetch/clean commands + API parity (ROADMAP milestone 6):
  fetch_media(), clean_downloads(), clean_media()
- codex: teaching comments at blueprint seams once the JSONC
  reader lands (ROADMAP milestone 6)
- the hostdir drive content source (vvfat on the QEMU
  adapter — ROADMAP milestone 6)
- user.properties and the property command family (ROADMAP
  milestone 7) — use the `keyring` package for the protected host
  credential store rather than hand-rolling Windows Credential
  Manager / macOS Keychain / Secret Service backends; its
  (service, username) model takes the spec's scoping directly,
  with the properties-file path as the service and the property
  name as the username

## Milestone 6 — the instance model and machine blueprints

The whole machine model beyond milestone 1's core (ROADMAP
milestone 6, deliverables 1–9). Much of the plumbing already
landed on the realignment: the `builtins/` → `codex/` rename and
`codex.json` index, the JSONC reader (`jsonc.py`), the `.rlqb` /
`.rlqm` extensions, `cache/machines/<id>/` materialization with
atomic `reliquary-machine.json`, the per-blueprint allocation
lock, selector-based console/state ops, and the authored
blueprint / media-definition schemas. What remains is broken into
tasks in dependency order — the spine is T0 → T1 → T2 → T3 → T4 →
T5; T6 and T7 run beside it.

0. Decide-first design round: the three ROADMAP "Decide first"
   questions — running-machine reconfiguration surfacing (hot
   media vs stopped-only), a home-wide concurrent-machine limit,
   and whether `size`/`base` are valid on `cdrom` drives.
   Adjudicate through the interface-change rule and fold into
   DECISIONS.md + the specs. Gates T1 (cdrom size/base) and T3
   (concurrency).
   LANDED (owner, 2026-07-22 — DECISIONS.md, the milestone-6
   decide-first round): Q1 insert/eject running-or-stopped (hot
   media confirmed, matching the existing script-spec/cli
   contract), set-boot and apply stopped-only; Q2 no home-wide
   concurrency limit; Q3 `size`/`base` rejected on `cdrom` (a
   cdrom is `media`-or-empty only). Folded into
   instance-model.md, machine-blueprint-reference.md, and
   machine-blueprint.schema.json. Two consequences ride the
   later tasks: T1 enforces the cdrom rule in `blueprint.py`, and
   T4 grows the hot-insert/eject implementation.
1. Full blueprint field-reference validation (deliverable 1) +
   the remaining media-definition surface (part of deliverable
   9): extend `blueprint.py` past the milestone-1 subset to
   `backend`, `cpus`, per-drive `controller`, `base`
   (difference/duplicate), `hostdir`, `enabled`, `control-planes`,
   `backend-settings`, and `parameters`, with format and
   QEMU-derived capability checks failing closed; add
   definition-level `description` / `notes` /
   `redistributable-under` to `MediaDefinition`.
   LANDED (2026-07-22): `blueprint.py` validates the full field
   reference — all four drive content sources plus
   `controller`/`enabled`, and the top-level `backend` / `cpus` /
   `control-planes` / `backend-settings` / `parameters` — each
   failing closed and naming the problem; the Q3 cdrom rule and
   state-only-field rejection are enforced; `media`/`base.media`
   resolve. Media definitions gained the three annotation fields.
   `new-blueprint` stopped writing the invalid `version` field.
   Scope notes: (a) capability checks are backend-scoped and QEMU
   satisfies the whole vocabulary, so they move to backend
   assignment at materialization (T2 / the m9 adapter seam) — the
   parser stays pure format validation; (b) `base`/`hostdir` drive
   materialization is fail-closed in `create` (a clear
   NotImplementedError) pending T2; (c) full state resolution
   (digest, backend-id, cpus/control-planes into state) is T2.
   The blueprint `name` field was REINSTATED as a display name
   (owner, 2026-07-22 — DECISIONS.md, reversing the 2026-07-21
   drop), so it stays in the parser and the codex `name` stays
   valid.
2. Drive materialization + state provenance (rest of deliverable
   2, part of deliverable 8): qcow2 `base` triad
   (difference/duplicate) and `hostdir` vvfat materialization in
   `create`; record the resolved `blueprint-digest`,
   `blueprint-source` path, and `backend-id` in the state.
   LANDED (2026-07-22): `lifecycle.py` gained
   `create_difference_image` (qcow2 backed by the base, format
   probed for the explicit `-F`), `create_duplicate_image`
   (`qemu-img convert`), and `probe_image_format`; `create`
   materializes `size`/`media`/`base`/`hostdir` drives (a relative
   `hostdir` resolves against the blueprint source dir — the asset
   root supersedes this at T6 — and a missing directory fails
   closed), resolves platform defaults (`memory`/`cpus`/
   `control-planes`) into the state, and records `backend-id`
   (`reliquary-<id>`), `blueprint-digest` (`sha256:` over the
   resolved snapshot with cache paths excluded, so two machines of
   one blueprint share it), and `blueprint-source`. Non-`ide`
   controllers fail closed (the adapter seam owns richer
   topology). Real `qemu-img` difference/duplicate materialization
   smoke-verified. `apply` (T4) consumes the digest.
3. Lifecycle integrity (deliverable 3): operation generations,
   exclusive per-machine operation locks (beyond today's
   allocation lock), and startup detection of interrupted
   transitional phases with safe rollback or explicit recovery
   instructions.
   LANDED (2026-07-22): `machines.py` gained `_machine_lock`
   (`.locks/<id>.op.lock`), held by every mutating op
   (create materialization, start, stop, destroy, insert/eject/
   set-boot, mark_stopped); a `generation` counter in the state
   bumped once per operation; and the transitional phases —
   `create` writes `creating`→`ready` (rolling back a failed
   materialization), `stop` writes `running`→`stopping`→`ready`,
   `destroy` writes `ready`→`destroying`. `_reconcile_phase` runs
   under the lock at each op's start: `stopping` completes the
   interrupted stop (identity-mismatch still fails closed, keeping
   `running`), `creating`/`destroying` roll forward to removal and
   fail closed naming the recovery. `destroy` accepts a
   rolled-back `creating` machine. Atomic JSON replacement was
   already in place.
4. Lifecycle CLI completion + reconciliation + the global
   `--json` flag (deliverable 4, `get-machine-dir` from
   deliverable 5): `apply-blueprint`, `recreate-machine`,
   `search-blueprints` (index + user files, with provenance),
   `seed-blueprint --only`, `get-machine-dir`; grow `start` to
   full baseline/state/backend-identity reconciliation with media
   re-verification; `--json` defined by the twin's-return rule.
   Also lift the milestone-1 stopped-only guard on
   `insert-media`/`eject-media`: a running machine performs the
   media change live over an identity-verified QMP session and
   persists it to the state (T0/Q1); AGENTS.md's "all three
   require a stopped machine" line is corrected here.
   LANDED (2026-07-22), in five sub-commits: SC1 `recreate-machine`
   + `get-machine-dir`; SC2 `search-blueprints` (provenance
   yes/seeded/user) + `seed --only`; SC3 `apply-blueprint`
   (reconcile absorbable diffs, fail closed on changed size/base of
   an existing image, re-record the digest); SC4 the global
   `--json` flag (each command prints its API twin's return, void →
   `{}`, stream commands reject it); SC5 hot `insert`/`eject`
   (removable drives launch with a stable QMP id; a running change
   goes live over HMP `change`/`eject` on the identity-verified
   session, then persists). `start` already reconciles (media
   re-verify + backend regen from state; the baseline is
   deliberately not re-applied at start).
5. Absorb and delete the legacy path (deliverable 2's deletion):
   `MachineConfig`, the root-home `machine.json` / `vm.json`
   layer, and the legacy `Runner` start/stop path fold into the
   cached-machine model and are deleted; AGENTS.md "The runner
   surface" and the tests follow.
   LANDED (2026-07-22, full deletion — DECISIONS-scope owner
   choice): `workflows.py` (`Runner`/`MachineConfig`/
   `run_guest_program`/`run_task`/`start`) and `drives.py` (the
   root-home filesystem auto-discovery) are deleted; `lifecycle.py`
   lost `normalize_machine`/`machine_argument`/`normalize_memory`/
   `_start_configured_machine`; `home.py` lost `drives_dir`;
   `format_options` moved into `machines.py`; the CLI's bare
   `start-machine`/`stop-machine` root-home path and its
   `--port`/`--qemu`/`--platform`/`qemu_args` legacy flags are
   gone (a selector is now required). `test_runner.py` deleted;
   `test_lifecycle.py` ownership guarantees rewritten over
   `launch_owned_qemu`; `test_core.py` scan/staged/guest-program
   tests removed. AGENTS.md ("The runner surface"/"Guest program
   runs"/home layout/DOS-boot), api-reference, and cli-reference
   rewritten. FOLLOW-UP: the README DOS walkthrough + embedding
   sections and docs/dos-automation.md still describe the deleted
   `run_guest_program`/`Runner` surface — a focused rewrite to the
   cached-machine/`run-script` model rides a separate commit.
6. Authored-asset residency (deliverable 8): the resolution
   module (`--assets` / `--assets-only`, API `assets=` /
   `assets_only=`), root-shadows-home, and `--blueprint` selection
   scoped to the invocation's resolution against the recorded
   `blueprint-source`.
7. Published schemas + fixture corpus + examples (deliverables 6,
   7): the machine-state schema authored once the state format
   settles; the shared valid/invalid fixture corpus run against
   both parser and schema; `planning/examples/` audited to the
   implemented shapes.

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
  public-contract elevation stay with milestone 6)
- the adapter API becoming world-facing
  (planning/design/backend-adapter.md is INTERNAL by decision,
  owner 2026-07-21 — a real third-party adapter story elevates
  it into the INTERFACES inventory through the interface-change
  rule, never by drift)

## Design

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
- CLI clean, beyond the settled clean-downloads / clean-media
  invariants: delete completely unreferenced media? all
  downloads? unreferenced only? (machine-cache cleaning is an
  open decision in ROADMAP "Decisions still needed")
